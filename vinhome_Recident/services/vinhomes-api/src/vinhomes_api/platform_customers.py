"""Domain-owned customer consent and short-lived subject grants.

The link credential can only exchange/revoke grants. It is never accepted by
resident/staff routes. Business calls recheck Domain membership and ownership.
"""

import base64
import hashlib
import hmac
import html
import os
import json
import time
import re
import secrets
from contextlib import asynccontextmanager
from contextvars import ContextVar
from urllib.parse import urlencode, parse_qs, urlsplit
from uuid import UUID, uuid4

from fastapi import APIRouter, Depends, HTTPException, Query, Request, Response
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.encoders import jsonable_encoder
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import text

from . import resident_cases as cases
from .resident_contract import CreateRequest

async def enabled():
    if os.getenv("VINHOMES_CUSTOMER_PLATFORM_ENABLED", "false").lower() != "true":
        raise HTTPException(503, "Customer Platform integration disabled")


router = APIRouter(prefix="/platform", tags=["Platform customer identity and cases"], dependencies=[Depends(enabled)])
TENANT = "nullif(current_setting('app.tenant_id',true),'')::uuid"
SOURCE_INTENT = ContextVar("customer_source_intent", default=None)


async def bind_customer_ticket(db, ticket_id):
    """Bind the customer's existing workflow; never enqueue a BQL start."""
    row = (await db.execute(text(f"""SELECT p.*,t.channel_id,m.code AS management_ref FROM tickets t
        JOIN vh_resident_cases c ON c.channel_id=t.channel_id AND c.tenant_id=t.tenant_id
        JOIN platform_customer_cases p ON p.case_id=c.id AND p.tenant_id=c.tenant_id
        JOIN management_units m ON m.id=t.management_unit_id AND m.tenant_id=t.tenant_id
        WHERE t.id=:id AND t.tenant_id={TENANT} AND t.requester_user_id=p.user_id"""), {"id": ticket_id})).mappings().first()
    if row is None:
        return False
    await db.execute(text(f"""INSERT INTO platform_links(ticket_id,tenant_id,channel_id,user_id,management_ref,
        workflow_id,conversation_id,status,origin) VALUES(:id,{TENANT},:channel,:user,:management,:workflow,:case,'open','platform')
        ON CONFLICT(ticket_id) DO NOTHING"""), {"id": ticket_id, "channel": row["channel_id"],
        "user": row["user_id"], "management": row["management_ref"], "workflow": row["platform_workflow_id"], "case": row["platform_case_id"]})
    current = (await db.execute(text("SELECT origin,workflow_id,user_id FROM platform_links WHERE ticket_id=:id"), {"id": ticket_id})).mappings().one()
    if (current["origin"], current["workflow_id"], current["user_id"]) != ("platform", row["platform_workflow_id"], row["user_id"]):
        raise HTTPException(409, "Ticket already bound to another origin")
    return True


def digest(value):
    return hashlib.sha256(value.encode()).hexdigest()


def pkce(value):
    return base64.urlsafe_b64encode(hashlib.sha256(value.encode()).digest()).decode().rstrip("=")


@asynccontextmanager
async def database(request, actor=""):
    engine, settings = request.app.state.engine, request.app.state.settings
    if engine is None or not settings.tenant_id:
        raise HTTPException(503, "Customer authority unavailable")
    async with engine.begin() as db:
        await db.execute(text("select set_config('app.tenant_id',:t,true),set_config('app.user_id',:u,true)"),
            {"t": str(settings.tenant_id), "u": actor})
        yield db


async def client(db, ident, credential=None):
    row = (await db.execute(text(f"SELECT * FROM platform_customer_clients WHERE tenant_id={TENANT} AND client_id=:id AND active"),
        {"id": ident})).mappings().first()
    if not row or (credential is not None and not hmac.compare_digest(row["secret_hash"], digest(credential))):
        raise HTTPException(401, "Unregistered customer client")
    return dict(row)


def resident_request(request):
    from .password_auth import SURFACE
    headers = [(key, value) for key, value in request.scope["headers"] if key.decode().lower() != SURFACE]
    headers.append((SURFACE.encode(), b"resident"))
    return Request({**request.scope, "headers": headers}, request.receive)


LOGIN = """<!doctype html><html lang="vi"><meta charset="utf-8"><title>Liên kết Vinhomes</title>
<h1>Đăng nhập Vinhomes để liên kết</h1><form id="login"><label>Email hoặc số điện thoại <input name="identifier" autocomplete="username" required></label>
<label>Mật khẩu <input name="password" type="password" autocomplete="current-password" required></label><button>Đăng nhập</button></form><p id="error" role="alert"></p>
<script nonce="{nonce}">document.getElementById('login').onsubmit=async e=>{{e.preventDefault();let f=new FormData(e.target);let r=await fetch(new URL('../../auth/login',location.href),{{method:'POST',credentials:'same-origin',headers:{{'Content-Type':'application/json','x-vinhomes-surface':'resident'}},body:JSON.stringify(Object.fromEntries(f))}});if(r.ok)location.reload();else document.getElementById('error').textContent='Không đăng nhập được. Kiểm tra tài khoản hoặc thử lại sau.';}};</script></html>"""


def private_html(body, nonce):
    return HTMLResponse(body, headers={"Cache-Control": "no-store", "Referrer-Policy": "no-referrer",
        "Content-Security-Policy": "default-src 'none'; form-action 'self'; connect-src 'self'; script-src 'nonce-" + nonce + "'; base-uri 'none'; frame-ancestors 'none'"})


@router.get("/link/authorize", response_class=HTMLResponse)
async def authorize(request: Request, client_id: str = Query(max_length=100), redirect_uri: str = Query(max_length=2000),
                    state: str = Query(min_length=32, max_length=255), code_challenge: str = Query(min_length=43, max_length=43),
                    platform_user_id: str = Query(min_length=1, max_length=255),
                    code_challenge_method: str = "S256", response_type: str = "code", scope: str = "self requests"):
    if code_challenge_method != "S256" or response_type != "code" or set(scope.split()) != {"self", "requests"} or not re.fullmatch(r"[A-Za-z0-9_-]{43}", code_challenge):
        raise HTTPException(422, "Unsupported link request")
    async with database(request) as db:
        registered = await client(db, client_id)
        if registered["redirect_uri"] != redirect_uri:
            raise HTTPException(400, "Unregistered redirect URI")
    from .password_auth import authenticated_user
    nonce = secrets.token_urlsafe(24)
    try:
        user = await authenticated_user(resident_request(request))
    except HTTPException as exc:
        if exc.status_code == 401:
            return private_html(LOGIN.format(nonce=nonce), nonce)
        raise
    ident, csrf = uuid4(), secrets.token_urlsafe(32)
    async with database(request, user["id"]) as db:
        # A live, verified residence is required before linking a resident identity.
        if not (await db.execute(text(cases.RESIDENCE + " limit 1"), {"actor": user["id"]})).first():
            raise HTTPException(403, "Verified residence required")
        count = (await db.execute(text(f"SELECT count(*) FROM platform_customer_codes WHERE tenant_id={TENANT} AND user_id=:u AND expires_at>now()"), {"u": user["id"]})).scalar_one()
        if count >= 20:
            raise HTTPException(429, "Too many link attempts")
        await db.execute(text(f"""INSERT INTO platform_customer_codes
            (id,tenant_id,client_id,user_id,platform_user_id,state,challenge,redirect_uri,csrf_hash,expires_at)
            VALUES (:id,{TENANT},:c,:u,:p,:s,:challenge,:redirect,:csrf,now()+interval '5 minutes')"""),
            {"id": ident, "c": client_id, "u": user["id"], "p": platform_user_id, "s": state,
             "challenge": code_challenge, "redirect": redirect_uri, "csrf": digest(csrf)})
    body = f'''<!doctype html><html lang="vi"><meta charset="utf-8"><title>Đồng ý liên kết Vinhomes</title>
<h1>Liên kết tài khoản Vinhomes</h1><p>{html.escape(user['name'])}, cho phép Platform đọc hồ sơ cư trú và tạo/theo dõi yêu cầu của chính bạn. Các quyết định cần xác nhận vẫn do bạn thực hiện. Có thể thu hồi liên kết bất cứ lúc nào.</p>
<form method="post"><input type="hidden" name="transaction" value="{ident}"><input type="hidden" name="csrf" value="{csrf}"><button name="decision" value="allow">Đồng ý</button><button name="decision" value="deny">Từ chối</button></form></html>'''
    response = private_html(body, nonce)
    response.set_cookie("vin_link_csrf_" + ident.hex, csrf, max_age=300, httponly=True,
        secure=request.url.scheme == "https", samesite="lax", path="/")
    return response


@router.post("/link/authorize")
async def consent(request: Request):
    form = await request.form()
    try:
        ident = UUID(str(form.get("transaction")))
    except ValueError as exc:
        raise HTTPException(400, "Invalid consent transaction") from exc
    csrf = str(form.get("csrf", ""))
    if not csrf or not hmac.compare_digest(csrf, request.cookies.get("vin_link_csrf_" + ident.hex, "")):
        raise HTTPException(403, "Consent CSRF failed")
    from .password_auth import authenticated_user
    user = await authenticated_user(resident_request(request))
    code = secrets.token_urlsafe(48)
    async with database(request, user["id"]) as db:
        row = (await db.execute(text(f"SELECT * FROM platform_customer_codes WHERE tenant_id={TENANT} AND id=:id AND user_id=:u AND expires_at>now() AND used_at IS NULL FOR UPDATE"),
            {"id": ident, "u": user["id"]})).mappings().first()
        if not row or row["code_hash"] or not hmac.compare_digest(row["csrf_hash"], digest(csrf)):
            raise HTTPException(409, "Consent expired or consumed")
        if form.get("decision") != "allow":
            await db.execute(text("UPDATE platform_customer_codes SET used_at=now() WHERE id=:id"), {"id": ident})
            params = {"error": "access_denied", "state": row["state"]}
        else:
            await db.execute(text("UPDATE platform_customer_codes SET code_hash=:h,expires_at=now()+interval '60 seconds' WHERE id=:id"),
                {"h": digest(code), "id": ident})
            params = {"code": code, "state": row["state"]}
        uri = row["redirect_uri"]
    response = RedirectResponse(uri + ("&" if "?" in uri else "?") + urlencode(params), status_code=303,
        headers={"Cache-Control": "no-store", "Referrer-Policy": "no-referrer"})
    response.delete_cookie("vin_link_csrf_" + ident.hex)
    return response


class Strict(BaseModel):
    model_config = ConfigDict(extra="forbid")


class ExchangeCode(Strict):
    grant_type: str
    client_id: str
    client_secret: str = Field(min_length=16, max_length=512)
    code: str = Field(min_length=32, max_length=255)
    code_verifier: str = Field(min_length=43, max_length=128)
    redirect_uri: str
    platform_user_id: str


@router.post("/link/token")
async def exchange_code(body: ExchangeCode, request: Request, response: Response):
    if body.grant_type != "authorization_code":
        raise HTTPException(422, "Unsupported grant")
    token, link_id = "vcl_" + secrets.token_urlsafe(48), uuid4()
    async with database(request) as db:
        registered = await client(db, body.client_id, body.client_secret)
        code = (await db.execute(text(f"SELECT * FROM platform_customer_codes WHERE tenant_id={TENANT} AND code_hash=:h AND used_at IS NULL AND expires_at>now() FOR UPDATE"),
            {"h": digest(body.code)})).mappings().first()
        if not code or (code["client_id"], code["redirect_uri"], code["platform_user_id"]) != (body.client_id, body.redirect_uri, body.platform_user_id) or not hmac.compare_digest(code["challenge"], pkce(body.code_verifier)):
            raise HTTPException(401, "Code exchange rejected")
        await db.execute(text("select set_config('app.user_id',:u,true)"), {"u": code["user_id"]})
        if not (await db.execute(text(cases.RESIDENCE + " limit 1"), {"actor": code["user_id"]})).first():
            raise HTTPException(403, "Verified residence required")
        previous = (await db.execute(text(f"SELECT * FROM platform_customer_links WHERE tenant_id={TENANT} AND client_id=:c AND user_id=:u FOR UPDATE"),
            {"c": body.client_id, "u": code["user_id"]})).mappings().first()
        if previous and previous["platform_user_id"] != body.platform_user_id:
            raise HTTPException(409, "Subject already linked; account recovery required")
        if previous:
            link_id = previous["id"]
            await db.execute(text("DELETE FROM platform_customer_grants WHERE link_id=:id"), {"id": link_id})
            await db.execute(text("UPDATE platform_customer_links SET token_hash=:h,active=true,revision=revision+1,expires_at=now()+interval '30 days' WHERE id=:id"), {"h": digest(token), "id": link_id})
        else:
            await db.execute(text(f"""INSERT INTO platform_customer_links
                (id,tenant_id,client_id,user_id,platform_user_id,token_hash,scopes,expires_at)
                VALUES (:id,{TENANT},:c,:u,:p,:h,ARRAY['self','requests'],now()+interval '30 days')"""),
                {"id": link_id, "c": body.client_id, "u": code["user_id"], "p": body.platform_user_id, "h": digest(token)})
        await db.execute(text("UPDATE platform_customer_codes SET used_at=now() WHERE id=:id"), {"id": code["id"]})
    response.headers["Cache-Control"] = "no-store"
    return {"issuer": registered["issuer"], "subject": code["user_id"], "platform_user_id": body.platform_user_id,
        "link_id": str(link_id), "link_token": token, "scopes": ["self", "requests"], "consent_version": "1"}


class LinkCredential(Strict):
    client_id: str
    client_secret: str = Field(min_length=16, max_length=512)
    link_token: str = Field(min_length=32, max_length=255)


async def active_link(db, body):
    await client(db, body.client_id, body.client_secret)
    row = (await db.execute(text(f"""SELECT l.* FROM platform_customer_links l JOIN users u ON u.id=l.user_id
        WHERE l.tenant_id={TENANT} AND l.client_id=:c AND l.token_hash=:h AND l.active AND l.expires_at>now()
        AND u.status='active' AND EXISTS(SELECT 1 FROM tenant_memberships m WHERE m.tenant_id=l.tenant_id AND m.user_id=l.user_id AND m.status='active') FOR UPDATE OF l"""),
        {"c": body.client_id, "h": digest(body.link_token)})).mappings().first()
    if not row:
        raise HTTPException(401, "Link revoked or expired")
    await db.execute(text("select set_config('app.user_id',:u,true)"), {"u": row["user_id"]})
    if not (await db.execute(text(cases.RESIDENCE + " limit 1"), {"actor": row["user_id"]})).first():
        raise HTTPException(403, "Verified residence required")
    return row


@router.post("/customer/grants")
async def issue_subject_grant(body: LinkCredential, request: Request, response: Response):
    token = "vcu_" + secrets.token_urlsafe(32)
    async with database(request) as db:
        link = await active_link(db, body)
        await db.execute(text(f"""INSERT INTO platform_customer_grants(id,tenant_id,link_id,token_hash,expires_at)
            VALUES (:id,{TENANT},:link,:h,now()+interval '5 minutes')"""), {"id": uuid4(), "link": link["id"], "h": digest(token)})
    response.headers["Cache-Control"] = "no-store"
    return {"access_token": token, "expires_in": 300, "subject": link["user_id"]}


@router.post("/customer/revoke")
async def revoke(body: LinkCredential, request: Request):
    async with database(request) as db:
        await client(db, body.client_id, body.client_secret)
        await db.execute(text(f"UPDATE platform_customer_links SET active=false WHERE tenant_id={TENANT} AND client_id=:c AND token_hash=:h"),
            {"c": body.client_id, "h": digest(body.link_token)})
    return {"revoked": True}


async def customer_scope(request: Request):
    scheme, _, token = request.headers.get("authorization", "").partition(" ")
    if scheme.lower() != "bearer" or not token.startswith("vcu_"):
        raise HTTPException(401, "Customer grant required")
    async with database(request) as db:
        link = (await db.execute(text(f"""SELECT l.*,g.id AS grant_id FROM platform_customer_grants g
            JOIN platform_customer_links l ON l.id=g.link_id AND l.tenant_id=g.tenant_id
            JOIN platform_customer_clients c ON c.tenant_id=l.tenant_id AND c.client_id=l.client_id
            JOIN users u ON u.id=l.user_id
            WHERE g.tenant_id={TENANT} AND g.token_hash=:h AND g.expires_at>now() AND g.calls<120
              AND l.active AND l.expires_at>now() AND c.active AND u.status='active'
              AND EXISTS(SELECT 1 FROM tenant_memberships m WHERE m.tenant_id=l.tenant_id AND m.user_id=l.user_id AND m.status='active')
            FOR UPDATE OF g"""), {"h": digest(token)})).mappings().first()
        if not link:
            raise HTTPException(401, "Customer grant expired or revoked")
        await db.execute(text("UPDATE platform_customer_grants SET calls=calls+1 WHERE id=:id"), {"id": link["grant_id"]})
        await db.execute(text("select set_config('app.user_id',:u,true)"), {"u": link["user_id"]})
        if not (await db.execute(text(cases.RESIDENCE + " limit 1"), {"actor": link["user_id"]})).first():
            raise HTTPException(403, "Verified residence required")
        request.state.platform_customer = dict(link)
        yield db, link["user_id"]


class PlatformRequest(Strict):
    platform_case_id: str = Field(min_length=1, max_length=255)
    platform_workflow_id: str = Field(min_length=1, max_length=255)
    request: CreateRequest


@router.post("/customer/requests", status_code=201)
async def create_request(body: PlatformRequest, request: Request, scope=Depends(customer_scope)):
    key = request.headers.get("idempotency-key", "")
    if not 16 <= len(key) <= 128:
        raise HTTPException(400, "Idempotency-Key required")
    link, db = request.state.platform_customer, scope[0]
    result = await cases.create_case(scope, body.request, request, key)
    await db.execute(text(f"""INSERT INTO platform_customer_cases
        (tenant_id,client_id,platform_case_id,platform_workflow_id,case_id,user_id,link_id)
        VALUES ({TENANT},:c,:p,:w,:case,:u,:link) ON CONFLICT DO NOTHING"""),
        {"c": link["client_id"], "p": body.platform_case_id, "w": body.platform_workflow_id,
         "case": UUID(result["id"]), "u": scope[1], "link": link["id"]})
    bound = (await db.execute(text(f"SELECT * FROM platform_customer_cases WHERE tenant_id={TENANT} AND client_id=:c AND platform_case_id=:p"),
        {"c": link["client_id"], "p": body.platform_case_id})).mappings().first()
    if not bound or str(bound["case_id"]) != result["id"] or bound["platform_workflow_id"] != body.platform_workflow_id:
        raise HTTPException(409, "Platform case binding conflict")
    return result



async def owned_case(db, actor, ident, link):
    row = await cases.case_row((db, actor), ident)
    binding = (await db.execute(text(f"SELECT * FROM platform_customer_cases WHERE tenant_id={TENANT} AND case_id=:id AND client_id=:c AND user_id=:u"),
        {"id": ident, "c": link["client_id"], "u": actor})).mappings().first()
    if not binding:
        raise HTTPException(404, "Customer case not found")
    return row, binding


@router.get("/customer/requests/{ident}")
async def get_request(ident: UUID, request: Request, events_cursor: str | None = Query(None, max_length=1024), scope=Depends(customer_scope)):
    row, _ = await owned_case(*scope, ident, request.state.platform_customer)
    details = await cases.public_detail(scope, row, request, events_cursor)
    return {**details, **await customer_projection(scope, ident, row)}


async def customer_projection(scope, ident, row):
    tickets = [dict(r) for r in (await scope[0].execute(text(f"""SELECT t.id,t.status,t.version,t.is_emergency
        FROM tickets t JOIN vh_resident_case_tickets ct ON ct.ticket_id=t.id AND ct.tenant_id=t.tenant_id
        WHERE ct.case_id=:case AND t.tenant_id={TENANT} ORDER BY t.id"""), {"case": ident})).mappings()]
    approvals = [dict(r) for r in (await scope[0].execute(text(f"""SELECT a.id,a.work_order_id,a.kind,a.status,
        a.request_detail,a.expires_at,t.version AS ticket_version FROM work_approvals a
        JOIN work_orders w ON w.id=a.work_order_id AND w.tenant_id=a.tenant_id
        JOIN tickets t ON t.id=w.ticket_id AND t.tenant_id=w.tenant_id
        JOIN vh_resident_case_tickets ct ON ct.ticket_id=t.id AND ct.tenant_id=t.tenant_id
        WHERE ct.case_id=:case AND a.tenant_id={TENANT} AND a.requested_to_user_id=:u
          AND a.kind IN ('customer_repair','customer_completion') AND a.status='pending'
        ORDER BY a.id"""), {"case": ident, "u": scope[1]})).mappings()]
    orders = [dict(r) for r in (await scope[0].execute(text(f"""SELECT w.id,w.status,w.scheduled_at,w.version
        FROM work_orders w JOIN vh_resident_case_tickets ct ON ct.ticket_id=w.ticket_id AND ct.tenant_id=w.tenant_id
        WHERE ct.case_id=:case AND w.tenant_id={TENANT} ORDER BY w.created_at,w.id"""), {"case": ident})).mappings()]
    statuses = {t["status"] for t in tickets}
    photos = [dict(r) for r in (await scope[0].execute(text(f"""SELECT DISTINCT f.id,f.original_name AS name
        FROM evidence_items e JOIN work_orders w ON w.id=e.work_order_id AND w.tenant_id=e.tenant_id
        JOIN vh_resident_case_tickets ct ON ct.ticket_id=w.ticket_id AND ct.tenant_id=w.tenant_id
        JOIN files f ON f.id=e.file_id AND f.tenant_id=e.tenant_id
        WHERE ct.case_id=:case AND e.tenant_id={TENANT} AND e.status='active'
          AND e.purpose IN ('after','verification') AND w.status='completed'
          AND f.status='ready' AND f.deleted_at IS NULL ORDER BY f.id"""), {"case": ident})).mappings()]
    if tickets and statuses <= {"closed", "cancelled"}:
        status, action = ("cancelled" if statuses == {"cancelled"} else "closed"), None
    elif any(t["is_emergency"] for t in tickets):
        status, action = "needs_human", "contact_domain_emergency_support"
    elif approvals or row["public_status"] == "confirmation":
        status, action = "waiting_for_customer", "review_current_decision"
    else:
        status, action = ("in_progress", "follow_progress") if tickets else ("received", "select_service_category")
    projection = jsonable_encoder({"domain_request_id": str(ident), "canonical_version": row["public_version"],
        "service_status": status, "next_action": action, "tickets": tickets,
        "status": row["public_status"], "pending_decisions": approvals, "work_orders": orders, "result_photos": photos,
        "as_of": row["public_updated_at"]})
    fingerprint = hashlib.sha256(json.dumps(projection, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode()).hexdigest()
    return {**projection, "projection_hash": fingerprint}


class ProjectionAck(Strict):
    canonical_version: int = Field(ge=1)
    content_hash: str = Field(pattern=r"^[a-f0-9]{64}$")


@router.post("/customer/requests/{ident}/projection-acks")
async def projection_ack(ident: UUID, body: ProjectionAck, request: Request, scope=Depends(customer_scope)):
    row, _ = await owned_case(*scope, ident, request.state.platform_customer)
    row = await cases.lock_case(scope, ident)
    current = await customer_projection(scope, ident, row)
    if body.canonical_version != row["public_version"] or body.content_hash != current["projection_hash"]:
        raise HTTPException(409, "Projection changed; refresh before acknowledgement")
    await scope[0].execute(text(f"""INSERT INTO platform_customer_projection_acks
        (tenant_id,case_id,link_id,link_revision,canonical_version,content_hash) VALUES({TENANT},:case,:link,:revision,:version,:hash)
        ON CONFLICT(tenant_id,case_id,link_id,link_revision,canonical_version)
        DO UPDATE SET content_hash=excluded.content_hash,applied_at=now()"""), {"case": ident, "link": request.state.platform_customer["id"],
        "revision": request.state.platform_customer["revision"], "version": body.canonical_version, "hash": body.content_hash})
    return {"ingestion_status": "applied", "canonical_version": body.canonical_version, "content_hash": body.content_hash}


@router.get("/customer/requests/{ident}/photos/{file_id}")
async def customer_photo(ident: UUID, file_id: UUID, request: Request, scope=Depends(customer_scope)):
    row, _ = await owned_case(*scope, ident, request.state.platform_customer)
    detail = await cases.public_detail(scope, row, request)
    allowed = [*detail["photos"], *((detail.get("resolution") or {}).get("photos") or [])]
    photo = next((p for p in allowed if p["id"] == str(file_id)), None)
    if photo is None:
        projection = await customer_projection(scope, ident, row)
        if not any(p["id"] == str(file_id) for p in projection["result_photos"]):
            raise HTTPException(404, "Customer photo not found")
        link = request.state.platform_customer
        applied = (await scope[0].execute(text(f"""SELECT 1 FROM platform_customer_projection_acks
            WHERE tenant_id={TENANT} AND case_id=:case AND link_id=:link AND link_revision=:revision
              AND canonical_version=:version AND content_hash=:hash"""), {"case": ident, "link": link["id"],
            "revision": link["revision"], "version": row["public_version"], "hash": projection["projection_hash"]})).first()
        if not applied:
            raise HTTPException(409, "Customer projection not applied")
        from .resident_photos import verified_file, file_response
        return file_response(await verified_file(scope, file_id))
    from .resident_photos import content
    access = parse_qs(urlsplit(photo["url"]).query)["access"][0]
    return await content(scope, file_id, request, access)


@router.get("/customer/me")
async def self_context(scope=Depends(customer_scope)):
    from .resident_api import me
    profile = await me(scope)
    categories = (await scope[0].execute(text(f"SELECT id,code,name FROM service_categories WHERE tenant_id={TENANT} AND enabled ORDER BY name,id"))).mappings().all()
    return {**profile, "service_categories": [dict(row) for row in categories]}


class CustomerEval(Strict):
    run_id: str = Field(pattern=r"^[a-z0-9][a-z0-9_-]{0,63}$")
    count: int = Field(default=5, ge=1, le=20)


@router.post("/customer/eval-fixtures")
async def eval_fixtures(body: CustomerEval, request: Request, scope=Depends(customer_scope)):
    from .eval_fixture import enabled, create_eval_tickets, EvalFixtureRefused
    if not enabled():
        raise HTTPException(404, "Evaluation fixtures disabled")
    try:
        # Reuse PR #99, including its synthetic DB marker and isolated grants.
        # A real resident ID never substitutes for a synthetic sandbox subject.
        namespace = hashlib.sha256((request.state.platform_customer["client_id"] + ":" +
            request.state.platform_customer["platform_user_id"] + ":" + body.run_id).encode()).hexdigest()
        tickets = await create_eval_tickets(scope[0], namespace, body.count, resident_user_id=scope[1])
    except EvalFixtureRefused as exc:
        raise HTTPException(409, str(exc)) from None
    return {"tickets": tickets, "data_mode": "synthetic_test", "run_namespace": namespace, "subject": scope[1]}


@router.post("/customer/eval-fixtures/cleanup")
async def cleanup_eval(body: CustomerEval, request: Request, scope=Depends(customer_scope)):
    from .eval_fixture import retire_eval_tickets, EvalFixtureRefused
    namespace = hashlib.sha256((request.state.platform_customer["client_id"] + ":" +
        request.state.platform_customer["platform_user_id"] + ":" + body.run_id).encode()).hexdigest()
    try:
        return await retire_eval_tickets(scope[0], namespace, scope[1])
    except EvalFixtureRefused as exc:
        raise HTTPException(409, str(exc)) from None


@router.get("/customer/requests/{ident}/events")
async def case_events(ident: UUID, request: Request, after: int = Query(0, ge=0), limit: int = Query(50, ge=1, le=100), scope=Depends(customer_scope)):
    row, binding = await owned_case(*scope, ident, request.state.platform_customer)
    rows = list((await scope[0].execute(text(f"""SELECT e.id,e.sequence,e.canonical_version,e.label,e.note,e.occurred_at,o.event_type
        FROM vh_resident_public_events e LEFT JOIN vh_resident_outbox o ON o.event_id=e.id AND o.tenant_id=e.tenant_id
        WHERE e.tenant_id={TENANT} AND e.case_id=:id AND e.sequence>:after ORDER BY e.sequence LIMIT :limit"""),
        {"id": ident, "after": after, "limit": limit + 1})).mappings())
    items = [{"schema_version": "vin-case-1", "event_id": str(e["id"]), "case_id": binding["platform_case_id"],
        "sequence": e["sequence"], "canonical_version": e["canonical_version"],
        "event_type": e["event_type"] or "resident.case.progress", "occurred_at": e["occurred_at"], "audience": "customer",
        "data": {"label": e["label"], "note": e["note"], "domain_request_id": str(ident), "origin": "platform"}}
        for e in rows[:limit]]
    return {"items": items, "next_cursor": items[-1]["sequence"] if items else after,
        "has_more": len(rows) > limit, "last_sequence": row["event_sequence"],
        "canonical_version": row["public_version"], "status": row["public_status"]}


class CustomerTicket(Strict):
    category_id: UUID
    expected_version: int = Field(ge=1)


@router.post("/customer/requests/{ident}/tickets", status_code=201)
async def materialize(ident: UUID, body: CustomerTicket, request: Request, scope=Depends(customer_scope)):
    row, _ = await owned_case(*scope, ident, request.state.platform_customer)
    key = request.headers.get("idempotency-key", "")
    if not 16 <= len(key) <= 128:
        raise HTTPException(400, "Idempotency-Key required")
    payload = body.model_dump(mode="json")
    previous = await cases.receipt(scope, "customer-ticket", str(ident), key, payload)
    if previous:
        return previous["response_body"]
    row = await cases.lock_case(scope, ident)
    cases.check_version(row, body.expected_version)
    existing = (await scope[0].execute(text(f"SELECT ticket_id FROM vh_resident_case_tickets WHERE case_id=:id AND tenant_id={TENANT}"), {"id": ident})).first()
    if existing or row["public_status"] == "completed":
        raise HTTPException(409, "Case already materialized or completed")
    person = (await scope[0].execute(text("SELECT name,phone_e164 FROM users WHERE id=:u"), {"u": scope[1]})).mappings().one()
    if not person["phone_e164"]:
        raise HTTPException(422, "Domain contact phone required")
    from .v3_resident import ResidentTicketCreate, create_resident_ticket
    from .v3_reception_runtime import emergency_kind
    emergency = emergency_kind(row["description"])
    assessment = {"priority": "critical", "severity": "critical", "is_emergency": True,
        "reason": "Domain emergency rule: " + emergency} if emergency else None
    ticket = await create_resident_ticket(row["channel_id"], ResidentTicketCreate(
        domain_id=row["domain_id"], building_id=row["building_id"], unit_id=row["unit_id"], category_id=body.category_id,
        title=row["title"], description=row["description"], location=row["location_description"],
        contact_name=person["name"], contact_phone=person["phone_e164"], request_kind="incident",
        idempotency_key="customer-case:" + str(ident)), scope, assessment=assessment, requires_plan=False, link_case=False)
    await scope[0].execute(text(f"""INSERT INTO vh_resident_case_tickets(tenant_id,case_id,ticket_id,linked_by)
        VALUES({TENANT},:case,:ticket,:actor)"""), {"case": ident, "ticket": ticket["id"], "actor": scope[1]})
    await scope[0].execute(text(f"UPDATE vh_resident_cases SET status='processing',version=version+1,updated_at=now() WHERE id=:id AND tenant_id={TENANT}"), {"id": ident})
    await cases.event(scope[0], ident, "Đã chuyển yêu cầu đến bộ phận xử lý", "resident.case.routed")
    result = {"ticket_id": str(ticket["id"]), "origin": "platform", "requires_immediate_human_response": bool(emergency),
        "request": await cases.public_detail(scope, await cases.case_row(scope, ident), request)}
    await cases.save_receipt(scope, "customer-ticket", str(ident), key, payload, result, 201, ident)
    return result


class TicketGrant(Strict):
    ticket_id: UUID
    tools: list[str] = Field(min_length=1, max_length=8)


@router.post("/customer/requests/{ident}/ticket-grants")
async def ticket_grant(ident: UUID, body: TicketGrant, request: Request, response: Response, scope=Depends(customer_scope)):
    _, binding = await owned_case(*scope, ident, request.state.platform_customer)
    allowed = {"vh_ticket_get", "vh_knowledge_search", "vh_staff_available", "vh_work_order_dispatch",
        "vh_operation_get", "vh_ticket_add_note", "vh_service_context", "vh_amenity_availability"}
    if set(body.tools) - allowed or len(body.tools) != len(set(body.tools)):
        raise HTTPException(403, "Tool not delegated to customer agent")
    link = request.state.platform_customer
    ticket = (await scope[0].execute(text(f"""SELECT t.id,l.management_ref FROM tickets t
        JOIN vh_resident_case_tickets ct ON ct.ticket_id=t.id AND ct.tenant_id=t.tenant_id
        JOIN platform_links l ON l.ticket_id=t.id AND l.tenant_id=t.tenant_id AND l.origin='platform'
        WHERE ct.case_id=:case AND t.id=:ticket AND t.tenant_id={TENANT} AND t.requester_user_id=:u
          AND l.workflow_id=:workflow AND t.status NOT IN ('closed','cancelled')"""),
        {"case": ident, "ticket": body.ticket_id, "u": scope[1], "workflow": binding["platform_workflow_id"]})).mappings().first()
    if not ticket:
        raise HTTPException(404, "Customer ticket not found")
    token, grant_id = "vhm_" + secrets.token_urlsafe(32), uuid4()
    await scope[0].execute(text(f"""INSERT INTO platform_mcp_grants
        (id,tenant_id,ticket_id,management_ref,workflow_id,token_hash,tools,expires_at,customer_link_id,customer_link_revision)
        VALUES(:id,{TENANT},:ticket,:management,:workflow,:hash,:tools,now()+interval '5 minutes',:link,:revision)"""),
        {"id": grant_id, "ticket": body.ticket_id, "management": ticket["management_ref"],
         "workflow": binding["platform_workflow_id"], "hash": digest(token), "tools": body.tools, "link": link["id"], "revision": link["revision"]})
    response.headers["Cache-Control"] = "no-store"
    return {"grant_id": str(grant_id), "ticket_id": str(body.ticket_id), "workflow_id": binding["platform_workflow_id"],
        "bearer_token": token, "expires_in": 300, "tools": body.tools}


class Decision(Strict):
    action: str
    expected_version: int = Field(ge=1)
    payload: dict
    platform_case_id: str
    source_event_id: str
    intent_proof: dict
    intent_signature: str = Field(min_length=64, max_length=64)


@router.post("/customer/requests/{ident}/decisions")
async def decide(ident: UUID, body: Decision, request: Request, scope=Depends(customer_scope)):
    row, binding = await owned_case(*scope, ident, request.state.platform_customer)
    if binding["platform_case_id"] != body.platform_case_id or len(body.source_event_id) > 255:
        raise HTTPException(403, "Source intent mismatch")
    link = request.state.platform_customer
    registered = await client(scope[0], link["client_id"])
    expected = {"client_id": link["client_id"], "platform_user_id": link["platform_user_id"],
        "domain_link_id": str(link["id"]), "request_id": str(ident), "platform_case_id": body.platform_case_id,
        "source_event_id": body.source_event_id, "action": body.action,
        "expected_version": body.expected_version, "payload": body.payload,
        "expires_at": body.intent_proof.get("expires_at")}
    expiry = expected["expires_at"]
    signature = hmac.new(bytes.fromhex(registered["secret_hash"]),
        json.dumps(expected, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode(), hashlib.sha256).hexdigest()
    if body.intent_proof != expected or not isinstance(expiry, int) or not time.time() < expiry <= time.time() + 301 or not hmac.compare_digest(signature, body.intent_signature):
        raise HTTPException(403, "Source intent invalid or expired")
    key = request.headers.get("idempotency-key", "")
    if not 16 <= len(key) <= 128:
        raise HTTPException(400, "Idempotency-Key required")
    fingerprint = body.model_dump(mode="json", exclude={"intent_proof", "intent_signature"})
    previous = await cases.receipt(scope, "platform-intent", str(ident), key, fingerprint)
    if previous:
        return previous["response_body"]
    # Serialize source decisions with Domain's canonical case mutations.
    row = await cases.lock_case(scope, ident)
    cases.check_version(row, body.expected_version)
    projection = await customer_projection(scope, ident, row)
    if not (await scope[0].execute(text(f"""SELECT 1 FROM platform_customer_projection_acks WHERE tenant_id={TENANT}
        AND case_id=:case AND link_id=:link AND link_revision=:revision AND canonical_version=:version AND content_hash=:hash"""),
        {"case": ident, "link": link["id"], "revision": link["revision"], "version": row["public_version"], "hash": projection["projection_hash"]})).first():
        raise HTTPException(409, "Customer projection not applied")
    if body.action in {"confirm", "reopen"}:
        from .resident_contract import ResolutionCommand, ReworkCommand
        contract = ReworkCommand if body.action == "reopen" else ResolutionCommand
        payload = contract.model_validate({**body.payload, "expectedVersion": body.expected_version})
        result = await cases.decide(scope, ident, payload, request, key, body.action)
    elif body.action == "plan-decision":
        from .resident_api import decide_plan
        from .resident_contract import ResidentPlanDecision
        try:
            plan_id = UUID(body.payload["plan_id"])
        except (ValueError, KeyError, TypeError) as exc:
            raise HTTPException(422, "plan_id required") from exc
        # Plan and case have different canonical revisions.
        payload = ResidentPlanDecision.model_validate({k: v for k, v in body.payload.items() if k != "plan_id"})
        result = await decide_plan(ident, plan_id, payload, request, scope)
    elif body.action == "work-approval":
        from .v3_resident import decide_resident_approval, ResidentApprovalDecision
        try:
            approval_id = UUID(body.payload["approval_id"])
        except (KeyError, ValueError, TypeError) as exc:
            raise HTTPException(422, "approval_id required") from exc
        permitted = (await scope[0].execute(text(f"""SELECT a.id FROM work_approvals a JOIN work_orders w
            ON w.id=a.work_order_id AND w.tenant_id=a.tenant_id JOIN vh_resident_case_tickets ct
            ON ct.ticket_id=w.ticket_id AND ct.tenant_id=w.tenant_id WHERE ct.case_id=:case AND a.id=:approval
            AND a.tenant_id={TENANT} AND a.requested_to_user_id=:u"""),
            {"case": ident, "approval": approval_id, "u": scope[1]})).first()
        if not permitted:
            raise HTTPException(404, "Customer approval not found")
        payload = ResidentApprovalDecision.model_validate({k: v for k, v in body.payload.items() if k != "approval_id"})
        result = await decide_resident_approval(approval_id, payload, request, scope)
    elif body.action in {"cancel", "reschedule"}:
        from . import platform_work as work
        ticket = (await scope[0].execute(text(f"""SELECT t.id,t.version FROM tickets t JOIN vh_resident_case_tickets ct
            ON ct.ticket_id=t.id AND ct.tenant_id=t.tenant_id WHERE ct.case_id=:case AND t.tenant_id={TENANT}
            AND t.requester_user_id=:u ORDER BY t.id"""), {"case": ident, "u": scope[1]})).mappings().all()
        if len(ticket) != 1:
            raise HTTPException(409, "Exactly one ticket required for this decision")
        token = SOURCE_INTENT.set({"ticket_id": str(ticket[0]["id"]), "user_id": scope[1], "source_event_id": body.source_event_id})
        try:
            if body.action == "cancel":
                if set(body.payload) - {"reason"}:
                    raise HTTPException(422, "Unexpected cancel arguments")
                result = await work.cancel(scope[0], ticket[0]["id"], body.payload.get("reason"), body.source_event_id,
                    ticket[0]["version"], body.source_event_id)
            else:
                if set(body.payload) - {"reason", "appointment_at"} or not isinstance(body.payload.get("appointment_at"), str):
                    raise HTTPException(422, "appointment_at required")
                result = await work.reschedule(scope[0], ticket[0]["id"], body.payload["appointment_at"], body.payload.get("reason"),
                    body.source_event_id, ticket[0]["version"], body.source_event_id)
        finally:
            SOURCE_INTENT.reset(token)
    else:
        raise HTTPException(409, "Action requires a ticket-bound consent; not supported for this case")
    await cases.save_receipt(scope, "platform-intent", str(ident), key, fingerprint, result, 200, ident)
    return result

def main():
    """Provision a registered client with the DB operator, outside runtime API."""
    import argparse
    import asyncio
    parser = argparse.ArgumentParser(description=main.__doc__)
    parser.add_argument("--tenant", required=True, type=UUID)
    parser.add_argument("--client-id", required=True)
    parser.add_argument("--issuer", required=True)
    parser.add_argument("--redirect-uri", required=True)
    parser.add_argument("--secret-env", default="VIN_CUSTOMER_CLIENT_SECRET")
    parser.add_argument("--enable", action="store_true")
    args = parser.parse_args()
    secret = os.getenv(args.secret_env, "")
    if len(secret) < 32 or not re.fullmatch(r"[a-zA-Z0-9_-]{1,100}", args.client_id):
        parser.error("Client ID or client secret configuration invalid")
    for value in (args.issuer, args.redirect_uri):
        parsed = urlsplit(value)
        if parsed.username or parsed.password or parsed.fragment or not parsed.netloc or (
            parsed.scheme != "https" and not (parsed.scheme == "http" and parsed.hostname in {"localhost", "127.0.0.1", "::1"})):
            parser.error("Registered endpoints must use HTTPS or loopback HTTP")

    async def provision():
        import asyncpg
        from .database import _url
        db = await asyncpg.connect(_url(os.environ["DATABASE_URL"]))
        try:
            async with db.transaction():
                await db.execute("SELECT set_config('app.tenant_id',$1,true)", str(args.tenant))
                await db.execute("""INSERT INTO platform_customer_clients(tenant_id,client_id,secret_hash,issuer,redirect_uri,active)
                    VALUES($1,$2,$3,$4,$5,$6) ON CONFLICT(tenant_id,client_id) DO UPDATE
                    SET secret_hash=excluded.secret_hash,issuer=excluded.issuer,redirect_uri=excluded.redirect_uri,active=excluded.active""",
                    args.tenant, args.client_id, digest(secret), args.issuer, args.redirect_uri, args.enable)
        finally:
            await db.close()
    asyncio.run(provision())
    print("Customer client configured; no credential printed")


if __name__ == "__main__":
    main()
