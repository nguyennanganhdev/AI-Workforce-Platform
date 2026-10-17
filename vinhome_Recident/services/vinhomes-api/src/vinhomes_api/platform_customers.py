"""Domain-owned customer consent and short-lived subject grants.

The link credential can only exchange/revoke grants. It is never accepted by
resident/staff routes. Business calls recheck Domain membership and ownership.
"""

import base64
import hashlib
import hmac
import html
import os
import re
import secrets
from contextlib import asynccontextmanager
from urllib.parse import urlencode
from uuid import UUID, uuid4

from fastapi import APIRouter, Depends, HTTPException, Query, Request, Response
from fastapi.responses import HTMLResponse, RedirectResponse
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import text

from . import resident_cases as cases
from .resident_contract import CreateRequest

async def enabled():
    if os.getenv("VINHOMES_CUSTOMER_PLATFORM_ENABLED", "false").lower() != "true":
        raise HTTPException(503, "Customer Platform integration disabled")


router = APIRouter(prefix="/platform", tags=["Platform customer identity and cases"], dependencies=[Depends(enabled)])
TENANT = "nullif(current_setting('app.tenant_id',true),'')::uuid"


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
            await db.execute(text("UPDATE platform_customer_links SET token_hash=:h,active=true,expires_at=now()+interval '30 days' WHERE id=:id"), {"h": digest(token), "id": link_id})
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
async def get_request(ident: UUID, request: Request, scope=Depends(customer_scope)):
    row, _ = await owned_case(*scope, ident, request.state.platform_customer)
    return await cases.public_detail(scope, row, request)


class Decision(Strict):
    action: str
    expected_version: int = Field(ge=1)
    payload: dict
    platform_case_id: str
    source_event_id: str


@router.post("/customer/requests/{ident}/decisions")
async def decide(ident: UUID, body: Decision, request: Request, scope=Depends(customer_scope)):
    row, binding = await owned_case(*scope, ident, request.state.platform_customer)
    if binding["platform_case_id"] != body.platform_case_id or len(body.source_event_id) > 255:
        raise HTTPException(403, "Source intent mismatch")
    key = request.headers.get("idempotency-key", "")
    if not 16 <= len(key) <= 128:
        raise HTTPException(400, "Idempotency-Key required")
    fingerprint = body.model_dump(mode="json")
    previous = await cases.receipt(scope, "platform-intent", str(ident), key, fingerprint)
    if previous:
        return previous["response_body"]
    # Serialize source decisions with Domain's canonical case mutations.
    row = await cases.lock_case(scope, ident)
    cases.check_version(row, body.expected_version)
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
    else:
        raise HTTPException(409, "Action requires a ticket-bound consent; not supported for this case")
    await cases.save_receipt(scope, "platform-intent", str(ident), key, fingerprint, result, 200, ident)
    return result
