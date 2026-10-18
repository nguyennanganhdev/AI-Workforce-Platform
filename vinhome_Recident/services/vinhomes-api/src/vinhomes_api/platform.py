"""The bridge to the AI platform (Workforce v1): docs/domain/NOI_WORKFORCE_V1.md.

Vinhomes is a partner of the platform and nothing more. A ticket Reception hands over gets a link and a
start command; from then on the platform's coordinator speaks in that chat and the resident's messages go to it.
The API only writes rows here, in the transaction of what the resident did; `platform_sync` sends them and
reads what the platform answered. With VINHOMES_API_PLATFORM_URL unset none of this runs.

    python -m vinhomes_api.platform confirm-routes --route <management_ref>=<route_id>:<revision> ...
    python -m vinhomes_api.platform status      (DATABASE_URL set: also what waits in the tables)
"""

import argparse
import asyncio
import hashlib
import hmac
import json
import os
import re
import sys
import time
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta, timezone

import httpx
from fastapi import APIRouter, HTTPException, Path
from pydantic import BaseModel, ConfigDict
from sqlalchemy import text

from .v3_reception_runtime import append_agent_message, attach_photos, emergency_kind
from .v3_resident import ResidentScope

router = APIRouter(tags=["Platform bridge"])
TENANT = "nullif(current_setting('app.tenant_id',true),'')::uuid"
CLIENT_ID = "platform"
# Links the platform is (or will be) working on.
ACTIVE = "('pending','open')"
TIMEZONE = "Asia/Ho_Chi_Minh"
VN = timezone(timedelta(hours=7))  # Vietnam keeps one offset all year
# A request waits for the coordinator's turn, up to the route's wait_seconds (120 at most); nothing else is slow.
WAIT_SECONDS, QUICK_SECONDS = 130, 15
FAILED_TEXT = "Hệ thống điều phối chưa xử lý được yêu cầu này. Ban quản lý sẽ liên hệ trực tiếp với bạn."
ASK_TEXT = "Trợ lý cần bạn đồng ý trước khi thực hiện bước tiếp theo."
SILENT_TEXT = "Trợ lý chưa có câu trả lời cho tin nhắn này. Bạn vui lòng nhắn lại giúp; nếu cần gấp, hãy liên hệ quầy lễ tân của tòa nhà."
RESOLVED_TEXT = {"approved": "Đã ghi nhận bạn đồng ý.", "rejected": "Đã ghi nhận bạn không đồng ý.",
                 "expired": "Đề nghị này không còn hiệu lực."}
KIND = {"incident": "Sự cố", "service_request": "Yêu cầu dịch vụ"}
PRIORITY = {"low": "Thấp", "normal": "Bình thường", "high": "Cao", "critical": "Khẩn cấp"}
SEVERITY = {"minor": "nhẹ", "moderate": "vừa", "major": "nặng", "critical": "nghiêm trọng"}
# A phone number or a request code never goes into the hand-over.
REDACTED = re.compile(r"\bVH-[A-Z0-9-]+|\+?\d[\d .]{7,}\d")
# v3_reception_runtime.EMERGENCY_KINDS, in the words the coordinator reads.
EMERGENCY = {"fire": "cháy hoặc khói", "gas": "rò khí gas", "electric": "chập điện hoặc giật điện", "elevator": "kẹt thang máy",
             "water": "ngập nước hoặc vỡ ống nước", "structure": "sập trần"}
# What the resident's app should do next, by workflow state (the platform sends the state, not the action, in events).
NEXT_ACTION = {"accepted": "watch_request", "active": "watch_request", "waiting_external_event": "watch_events",
               "awaiting_user": "submit_reply", "awaiting_approval": "submit_approval",
               "awaiting_confirmation": "confirm_close", "needs_attention": "resolve_attention",
               "blocked_authorization": "resolve_attention", "blocked_route_changed": "resolve_attention", "closed": "none"}
# Refusals that pass: an approval being decided, a revision that moved, work the platform still tracks.
RETRY_CODES = {"APPROVAL_PENDING", "REVISION_CONFLICT", "WORKFLOW_NOT_READY_TO_CLOSE"}
# The one close the platform takes while it still tracks work of the workflow (the reason is its fixed word).
STOP_TRACKING = {"reason": "resident_requested_stop_tracking", "stop_tracking_only": True}
# States a reply cannot leave: the platform refuses everything until its operator steps in.
BLOCKED = ("blocked_authorization", "blocked_route_changed")


def enabled() -> bool:
    return bool(os.getenv("VINHOMES_API_PLATFORM_URL", "").strip())


def vn_time(at: datetime) -> str:
    return at.astimezone(VN).strftime("%H:%M %d/%m/%Y")


@dataclass(frozen=True)
class Bridge:
    url: str
    customer_key: str
    provider_key: str
    signing_key_id: str
    signing_secret: str
    # What the platform must present when it calls the tools (the MCP server reads it).
    mcp_token: str

    @classmethod
    def from_env(cls) -> "Bridge | None":
        """None when the bridge is off."""
        value = {name: os.getenv("VINHOMES_API_PLATFORM_" + name, "").strip()
                 for name in ("URL", "CUSTOMER_KEY", "PROVIDER_KEY", "SIGNING_KEY_ID", "SIGNING_SECRET", "MCP_TOKEN")}
        if not value["URL"]:
            return None
        if not value["URL"].startswith(("http://", "https://")):
            raise ValueError("VINHOMES_API_PLATFORM_URL must be HTTP(S)")
        missing = [name for name in ("CUSTOMER_KEY", "PROVIDER_KEY", "SIGNING_KEY_ID", "SIGNING_SECRET") if not value[name]]
        if missing:
            raise ValueError("The platform bridge also needs " + ", ".join("VINHOMES_API_PLATFORM_" + name for name in missing))
        if value["MCP_TOKEN"] and len(value["MCP_TOKEN"]) < 32:
            raise ValueError("VINHOMES_API_PLATFORM_MCP_TOKEN requires at least 32 characters")
        return cls(value["URL"].rstrip("/"), value["CUSTOMER_KEY"], value["PROVIDER_KEY"], value["SIGNING_KEY_ID"],
                   value["SIGNING_SECRET"], value["MCP_TOKEN"])


# ---- the platform's HTTP API --------------------------------------------------------------------------------------

class PlatformError(Exception):
    """The platform refused a call: its error envelope {code, message, details, retryable}."""

    def __init__(self, status: int, code: str, message: str = "", retryable: bool = False, details: dict | None = None):
        super().__init__(f"{code}: {message}"[:500])
        self.status, self.code, self.retryable, self.details = status, code, retryable, details or {}


def retryable(exc: Exception) -> bool:
    """Worth sending again unchanged: the platform was not reached, is busy, or said to come back."""
    if isinstance(exc, httpx.HTTPError):
        return True
    return exc.status >= 500 or exc.status in (408, 429) or exc.retryable or exc.code in RETRY_CODES


def sign(secret: str, timestamp: str, raw: bytes) -> str:
    """HMAC-SHA256 over "<timestamp>.<the exact bytes sent>"."""
    return "v1=" + hmac.new(secret.encode(), timestamp.encode() + b"." + raw, hashlib.sha256).hexdigest()


class Platform:
    def __init__(self, bridge: Bridge, transport: httpx.AsyncBaseTransport | None = None):
        self.bridge = bridge
        self.http = httpx.AsyncClient(base_url=bridge.url + "/workforce/v1", transport=transport,
                                      timeout=httpx.Timeout(QUICK_SECONDS, connect=5))
        self.upload_http = httpx.AsyncClient(transport=transport, timeout=30, follow_redirects=False)

    async def aclose(self) -> None:
        await self.http.aclose()
        await self.upload_http.aclose()

    async def upload_asset(self, identity: dict, filename: str, mime: str, data: bytes) -> str:
        from urllib.parse import quote, urlsplit
        session = await self._call("POST", "/partner/assets/upload-sessions", json={
            "schema_version": "1", **identity, "filename": filename, "content_type": mime, "byte_size": len(data)})
        url = urlsplit(session.get("upload_url", ""))
        headers = session.get("required_headers") or {}
        if (session.get("upload_method") != "PUT" or url.scheme not in ("http", "https") or not url.netloc
                or url.username or url.password or url.fragment or not isinstance(headers, dict)
                or not isinstance(session.get("asset_id"), str) or not session["asset_id"]
                or any(not isinstance(key, str) or not isinstance(value, str) or key.lower() in ("authorization", "cookie", "proxy-authorization")
                       for key, value in headers.items())):
            raise PlatformError(502, "ASSET_UPLOAD_SESSION_INVALID", retryable=True)
        # A separate client has no partner credentials/cookies. Do not follow storage redirects.
        uploaded = await self.upload_http.put(session["upload_url"], content=data, headers=headers)
        if not 200 <= uploaded.status_code < 300:
            raise PlatformError(503, "ASSET_STORAGE_UPLOAD_FAILED", retryable=True)
        asset_id = str(session["asset_id"])
        complete = await self._call("POST", "/partner/assets/" + quote(asset_id, safe="") + "/complete",
            params={key: identity[key] for key in ("external_user_id", "external_ticket_id", "external_conversation_id")})
        if complete.get("asset_id") != asset_id or complete.get("status") != "active":
            raise PlatformError(502, "ASSET_NOT_ACTIVE", retryable=True)
        return asset_id

    async def _call(self, method: str, path: str, *, key: str | None = None, headers: dict | None = None, **how) -> dict:
        response = await self.http.request(method, path, **how, headers={
            "Authorization": "ApiKey " + (key or self.bridge.customer_key), **(headers or {})})
        try:
            body = response.json()
        except ValueError:
            # Not the platform's own answer (a proxy's page, a cut connection): nothing was learnt, ask again.
            raise PlatformError(response.status_code, f"HTTP_{response.status_code}", "the answer is not JSON", True) from None
        if response.status_code < 300:
            return body
        error = body.get("error") if isinstance(body, dict) and isinstance(body.get("error"), dict) else {}
        raise PlatformError(response.status_code, error.get("code") or f"HTTP_{response.status_code}",
                            str(error.get("message") or ""), error.get("retryable") is True, error.get("details"))

    async def request(self, body: dict) -> dict:
        """start_workflow or workflow_reply. 200 when the turn ended in time, 202 (result null) when it did not: same body."""
        return await self._call("POST", "/partner/requests", json=body, timeout=httpx.Timeout(WAIT_SECONDS, connect=5))

    async def result(self, request_id: str, user_id: str) -> dict:
        return await self._call("GET", f"/partner/requests/{request_id}", params={"external_user_id": user_id})

    async def decide(self, approval_id: str, body: dict) -> dict:
        return await self._call("POST", f"/partner/approvals/{approval_id}/decision", json=body)

    async def close(self, workflow_id: str, body: dict) -> dict:
        return await self._call("POST", f"/partner/workflows/{workflow_id}/close", json=body)

    async def history(self, conversation_id: str, user_id: str, cursor: str | None, limit: int = 200) -> dict:
        return await self._call("GET", f"/partner/conversations/{conversation_id}/event-history", params={
            "external_user_id": user_id, "limit": limit, **({"after_cursor": cursor} if cursor else {})})

    async def snapshot(self, conversation_id: str, user_id: str) -> dict:
        return await self._call("GET", f"/partner/conversations/{conversation_id}", params={"external_user_id": user_id})

    async def confirm_route(self, route_id: str, management_ref: str, revision: int) -> dict:
        return await self._call("POST", f"/partner/routes/{route_id}/confirm", json={
            "schema_version": "1", "external_management_ref": management_ref, "expected_revision": revision})

    async def job_event(self, raw: bytes) -> dict:
        """One staff progress event. `raw` is signed and sent as it is."""
        stamp = str(int(time.time()))
        return await self._call("POST", "/provider/job-events", key=self.bridge.provider_key, content=raw, headers={
            "Content-Type": "application/json", "X-Partner-Timestamp": stamp,
            "X-Partner-Key-Id": self.bridge.signing_key_id,
            "X-Partner-Signature": sign(self.bridge.signing_secret, stamp, raw)})

    async def receipt(self, receipt_id: str) -> dict:
        return await self._call("GET", f"/provider/event-receipts/{receipt_id}", key=self.bridge.provider_key)


# ---- what the API writes for the worker to send -----------------------------------------------------------------------

async def command(db, ticket_id, kind: str, body: dict) -> None:
    origin = (await db.execute(text(f"SELECT origin FROM platform_links WHERE ticket_id=:id AND tenant_id={TENANT}"),
        {"id": ticket_id})).scalar_one_or_none()
    if origin == "platform":
        return  # Customer runtime consumes canonical case progress, not BQL partner commands.
    await db.execute(text(f"""
        insert into platform_commands(tenant_id,ticket_id,kind,body) values ({TENANT},:ticket,:kind,cast(:body as jsonb))
    """), {"ticket": ticket_id, "kind": kind, "body": json.dumps(body, ensure_ascii=False)})


async def link_ticket(db, ticket_id) -> None:
    """Hand a new ticket to the platform, in the transaction that created it. Called again for the same ticket: nothing."""
    from .platform_customers import bind_customer_ticket
    if await bind_customer_ticket(db, ticket_id):
        return
    from .platform_settings import connection_enabled, lock
    await lock(db)
    if not await connection_enabled(db):
        return
    ticket = (await db.execute(text(f"""
        select t.channel_id,t.requester_user_id,t.title,t.description,t.request_kind,t.priority,t.severity,t.is_emergency,t.created_at,t.version,t.response_due_at,t.resolution_due_at,
          mu.code as management_ref,c.name as category,c.code as category_code,u.code as unit,b.name as building,z.name as zone,
          resident.name as resident_name,
          (select ur.relation from unit_residents ur where ur.tenant_id=t.tenant_id and ur.unit_id=t.unit_id
            and ur.user_id=t.requester_user_id and ur.verification_status='verified' and ur.valid_from<=now()
            and (ur.valid_to is null or ur.valid_to>now()) order by ur.verified_at desc,ur.id limit 1) as resident_relation,
          (select count(*) from ticket_files f where f.ticket_id=t.id and f.tenant_id=t.tenant_id) as photos,
          (select e.payload->'assessment'->>'reason' from ticket_events e where e.ticket_id=t.id and e.tenant_id=t.tenant_id
             and e.event_type='ticket.created' order by e.seq limit 1) as reception_reason
          ,(select coalesce(jsonb_agg(f.file_id::text order by f.created_at,f.file_id),'[]'::jsonb)
            from ticket_files f where f.ticket_id=t.id and f.tenant_id=t.tenant_id
              and f.purpose='issue' and f.uploaded_by=t.requester_user_id) as file_ids
        from tickets t
        join users resident on resident.id=t.requester_user_id
        join management_units mu on mu.id=t.management_unit_id and mu.tenant_id=t.tenant_id
        join units u on u.id=t.unit_id and u.tenant_id=t.tenant_id
        join buildings b on b.id=t.building_id and b.tenant_id=t.tenant_id
        left join zones z on z.id=t.zone_id and z.tenant_id=t.tenant_id
        left join service_categories c on c.id=t.category_id and c.tenant_id=t.tenant_id
        where t.id=:id and t.tenant_id={TENANT}
    """), {"id": ticket_id})).mappings().one()
    if not await connection_enabled(db, ticket['management_ref']):
        return
    # Every handed-over category reaches the platform. Receiving a session does not grant
    # permission to dispatch guards or bypass the domain's business approval rules.
    fresh = await db.execute(text(f"""
        insert into platform_links(ticket_id,tenant_id,channel_id,user_id,management_ref)
        values (:ticket,{TENANT},:channel,:user,:ref) on conflict (ticket_id) do nothing returning ticket_id
    """), {"ticket": ticket_id, "channel": ticket["channel_id"], "user": ticket["requester_user_id"],
           "ref": ticket["management_ref"]})
    if fresh.first() is None:
        return
    # All the platform ever receives about the ticket. Its tools take the ticket_id back, so the line must stay exact.
    # No phone number and no VH code: the coordinator repeats what it reads to the resident.
    # How urgent Reception judged it: the local emergency handling runs whatever the coordinator does.
    kind = EMERGENCY.get(emergency_kind(f"{ticket['title']}\n{ticket['description']}"))
    urgency = ("KHẨN CẤP" + (f" ({kind})" if kind else "")) if ticket["is_emergency"] else "không khẩn cấp"
    if ticket["severity"] in SEVERITY:
        urgency += f"; mức độ nghiêm trọng: {SEVERITY[ticket['severity']]}"
    lines = [f"ticket_id: {ticket_id}","handover_version: v1.1",f"ticket_version: {ticket['version']}",
             "Cư dân: " + " ".join((ticket["resident_name"] or "cư dân").split()),
             "Quan hệ cư trú: " + {"owner":"chủ hộ","tenant":"người thuê","household":"thành viên trong hộ"}.get(ticket["resident_relation"],"chưa xác định"),
             "Loại yêu cầu: " + " - ".join(part for part in (KIND.get(ticket["request_kind"]), ticket["category"]) if part),
             f"Tiêu đề: {ticket['title']}", f"Mô tả của cư dân: {ticket['description']}", f"Căn: {ticket['unit']}",
             f"Tòa: {ticket['building']}", f"Phân khu: {ticket['zone'] or 'không có'}",
             f"Mức ưu tiên: {PRIORITY.get(ticket['priority'], ticket['priority'])}",
             f"Mức khẩn cấp do Lễ tân đánh giá: {urgency}",
             # Reception's own reasoning about the report, worded without codes or phone numbers.
             "Đánh giá của Lễ tân: " + " ".join(REDACTED.sub("", ticket["reception_reason"] or "không có").split()),
             f"Số ảnh: {ticket['photos']}",
              f"Giờ tạo: {vn_time(ticket['created_at'])}",f"category_code: {ticket['category_code'] or 'unknown'}",
              f"response_due_at: {ticket['response_due_at'].isoformat() if ticket['response_due_at'] else 'unknown'}",
              f"resolution_due_at: {ticket['resolution_due_at'].isoformat() if ticket['resolution_due_at'] else 'unknown'}",
              'Quyền thao tác phải đọc lại từ policy của vh_ticket_get; snapshot bàn giao không cấp thêm quyền.',
              'Không xác định lại cư dân/căn hộ. Ảnh đính kèm qua Asset API được gắn đúng yêu cầu.']
    files = list(ticket["file_ids"] or [])
    await command(db, ticket_id, "start_workflow", {"text": "\n".join(lines), **({"file_ids": files[:10]} if files else {})})
    for offset in range(10, len(files), 10):
        await command(db, ticket_id, "workflow_reply", {"text": "Ảnh cư dân bổ sung cho cùng yêu cầu.",
            "file_ids": files[offset:offset + 10], "own": True})


async def notice(db,ticket_id,key,message_text):
    """Use the existing text reply contract, not a new unregistered provider event type."""
    await db.execute(text(f"""insert into platform_commands(tenant_id,ticket_id,kind,body)
        select {TENANT},ticket_id,'workflow_reply',cast(:body as jsonb) from platform_links
        where tenant_id={TENANT} and ticket_id=:ticket and origin='domain' and status='open' and coalesce(state,'')<>'closed'
        on conflict do nothing"""),{'ticket':ticket_id,'body':json.dumps({'text':message_text,'own':True,'domain_notice_key':key},ensure_ascii=False)})


async def divert(db, actor_id: str, channel_id: str, message_text: str, file_ids=(),source_message_id=None) -> bool:
    """True when this resident message went to the platform instead of Reception.

    An emergency goes both ways: Reception handles it here, at once, as before, and the coordinator is told.
    A message written after the request or its workflow ended is Reception's alone.
    """
    from .platform_settings import connection_enabled
    if not await connection_enabled(db):
        return False
    ticket = (await db.execute(text(f"""
        select l.ticket_id from platform_links l join tickets t on t.id=l.ticket_id and t.tenant_id=l.tenant_id
        where l.channel_id=:channel and l.tenant_id={TENANT} and l.status in {ACTIVE} and l.state is distinct from 'closed'
          and t.status not in ('closed','cancelled')
        order by l.created_at desc limit 1
    """), {"channel": channel_id})).mappings().first()
    if ticket is None:
        return False
    # The photos become the request's own, so staff and the coordinator's look-up see them. The platform itself
    # takes only words: of photos it is told how many were added (spec section 9). Also while the result waits
    # for the resident's answer: a photo of what is still wrong is what the next technician needs.
    photos = await attach_photos(db, actor_id, ticket["ticket_id"], list(file_ids))
    kind = emergency_kind(message_text)
    # Only what is known here: whether management was reached is Reception's turn, which has not run yet.
    said = "\n".join(part for part in (
        f"Cư dân vừa báo tình huống khẩn cấp ({EMERGENCY[kind]}). Lời cư dân:" if kind else "",
        message_text, f"Cư dân gửi thêm {len(photos)} ảnh." if photos else "") if part)
    if not said:
        return True  # only photos the request already holds: nothing new to tell
    if source_message_id:
        said += f"\nsource_message_id: {source_message_id}"
    # `own`: Reception answers an emergency in the chat itself, so a silent coordinator leaves nobody unanswered.
    await command(db, ticket["ticket_id"], "workflow_reply", {"text": said,
        **({"file_ids": [str(file_id) for file_id in photos[:10]]} if photos else {}),
        **({"source_message_id": str(source_message_id)} if source_message_id else {}),
        **({"own": True} if kind else {})})
    for offset in range(10, len(photos), 10):
        await command(db, ticket["ticket_id"], "workflow_reply", {
            "text": "Ảnh cư dân bổ sung cho cùng yêu cầu." + (f"\nsource_message_id: {source_message_id}" if source_message_id else ""),
            "file_ids": [str(file_id) for file_id in photos[offset:offset + 10]], "own": True,
            **({"source_message_id": str(source_message_id)} if source_message_id else {})})
    return kind is None


async def completion_acceptance(db, ticket_id) -> dict | None:
    """Read resident acceptance from Domain records; never infer it from model text."""
    from .v3_mutations import UNRESOLVED_QC

    row = (await db.execute(text(f"""
        select t.id,t.version,t.requester_user_id,a.id as approval_id,a.decided_event_id
        from tickets t join work_orders w on w.ticket_id=t.id and w.tenant_id=t.tenant_id
        join work_approvals a on a.work_order_id=w.id and a.tenant_id=w.tenant_id
        join ticket_events e on e.id=a.decided_event_id and e.ticket_id=t.id and e.tenant_id=t.tenant_id
        where t.id=:id and t.tenant_id={TENANT} and t.status='closed' and t.closed_at is not null
          and w.status='completed' and a.kind='customer_completion' and a.status='approved'
          and a.decided_by=t.requester_user_id and a.requested_to_user_id=t.requester_user_id
          and e.actor_user_id=t.requester_user_id and e.event_type='work_approval.decided'
          and e.payload->>'status'='approved'
        order by a.decided_at desc,a.id desc limit 1 for share of t
    """), {"id": ticket_id})).mappings().first()
    if row is None:
        return None
    unfinished = (await db.execute(text(f"""
        select w.id from work_orders w where w.ticket_id=:id and w.tenant_id={TENANT}
          and w.status not in ('cancelled','rejected')
          and (w.status<>'completed' or {UNRESOLVED_QC}) limit 1
    """), {"id": ticket_id})).first()
    pending = (await db.execute(text(f"""
        select a.id from work_approvals a join work_orders w on w.id=a.work_order_id and w.tenant_id=a.tenant_id
        where w.ticket_id=:id and w.tenant_id={TENANT} and a.status='pending' limit 1
    """), {"id": ticket_id})).first()
    if unfinished is not None or pending is not None:
        return None
    jobs = (await db.execute(text(f"""
        select id from work_orders where ticket_id=:id and tenant_id={TENANT} and status='completed' order by id
    """), {"id": ticket_id})).scalars().all()
    return {"external_ticket_id": str(row["id"]), "external_user_id": row["requester_user_id"],
            "ticket_status": "closed", "ticket_version": row["version"],
            "approval_id": str(row["approval_id"]), "decided_event_id": str(row["decided_event_id"]),
            "work_order_ids": [str(job) for job in jobs]}


async def completion_decided(db, ticket_id, closed: bool, approved: bool, note: str) -> None:
    """The resident answered the completion request of a ticket: tell its workflow, if it has one."""
    linked = await db.execute(text(f"select 1 from platform_links where ticket_id=:id and tenant_id={TENANT} and status in {ACTIVE}"),
                              {"id": ticket_id})
    if linked.first() is None:
        return
    if closed:
        if not approved or await completion_acceptance(db, ticket_id) is None:
            raise HTTPException(409, "Domain resident acceptance and completed work required")
        await command(db, ticket_id, "close", {"reason": "resident_confirmed"})
    elif not approved:
        # The ticket is open again: the coordinator has to send someone back.
        # `own`: the bridge's words, not a chat message the resident waits to see answered (platform_sync).
        await command(db, ticket_id, "workflow_reply", {
            "text": f"Tôi chưa đồng ý với kết quả xử lý, đề nghị làm lại. Lý do: {note.strip()}", "own": True})


class Decision(BaseModel):
    model_config = ConfigDict(extra="forbid")

    approve: bool


@router.post("/resident/platform/approvals/{approval_id}/decision",
             summary="Agree or not to what the platform's coordinator asked me in my chat")
async def decide_approval(body: Decision, scope: ResidentScope,
                          approval_id: str = Path(min_length=1, max_length=200)) -> dict[str, object]:
    db, actor_id = scope
    approval = (await db.execute(text(f"""
        select a.ticket_id,a.status,a.arguments_hash,a.expected_revision,a.quote_ref,
          a.expires_at is null or a.expires_at>now() as unexpired
        from platform_approvals a join platform_links l on l.ticket_id=a.ticket_id and l.tenant_id=a.tenant_id
        where a.approval_id=:id and l.user_id=:actor and a.tenant_id={TENANT} for update of a
    """), {"id": approval_id, "actor": actor_id})).mappings().first()
    if approval is None:
        raise HTTPException(404, "Approval not found")
    status = "approved" if body.approve else "rejected"
    if approval["status"] == status:
        return {"approval_id": approval_id, "status": status}
    if approval["status"] != "pending" or not approval["unexpired"]:
        raise HTTPException(409, "Approval is no longer pending")
    await db.execute(text("update platform_approvals set status=:status where approval_id=:id"), {"status": status, "id": approval_id})
    # The platform checks the answer against exactly what it asked: the hash, the quote and the revision it gave.
    await command(db, approval["ticket_id"], "approval_decision", {
        "approval_id": approval_id, "decision": "approve" if body.approve else "reject",
        "arguments_hash": approval["arguments_hash"], "expected_revision": approval["expected_revision"],
        "quote_ref": approval["quote_ref"]})
    return {"approval_id": approval_id, "status": status}


# ---- what the platform says, written into the domain ---------------------------------------------------------------

async def platform_client(db) -> str:
    """The platform's coordinator as the sender of chat messages; registered the first time it is needed."""
    await db.execute(text(f"""
        insert into integration_clients(tenant_id,id,name,kind,status,accepts_cases)
        values ({TENANT},:id,'Trợ lý Ban quản lý','platform','active',false) on conflict (tenant_id,id) do nothing
    """), {"id": CLIENT_ID})
    return CLIENT_ID


async def post_chat(db, link, platform_id: str, body: dict) -> bool:
    """Write one chat line for one platform id. The inbox row is the claim: a retry, the same message arriving
    again as an event, or a second worker finds it taken and writes nothing."""
    claimed = await db.execute(text(f"""
        insert into platform_inbox(tenant_id,platform_id,ticket_id) values ({TENANT},:id,:ticket)
        on conflict (tenant_id,platform_id) do nothing returning platform_id
    """), {"id": platform_id, "ticket": link["ticket_id"]})
    if claimed.first() is None:
        return False
    message = await append_agent_message(db, link["channel_id"], await platform_client(db), "customer", body)
    await db.execute(text(f"update platform_inbox set chat_message_id=:message where platform_id=:id and tenant_id={TENANT}"),
                     {"message": message["id"], "id": platform_id})
    return True


async def set_state(db, link, state: str, revision: int, reason: str | None = None) -> None:
    """Follow the workflow. An older picture (a slow answer after newer events) changes nothing. A workflow that
    closed does not close the link: the reader does, once it has the rest of the log (platform_sync._read)."""
    moved = await db.execute(text(f"""
        update platform_links set state=:state,next_action=:next,revision=:revision
        where ticket_id=:ticket and tenant_id={TENANT} and coalesce(revision,-1)<=:revision returning 1
    """), {"ticket": link["ticket_id"], "state": state, "next": NEXT_ACTION.get(state, "watch_request"), "revision": revision})
    if moved.first() is not None and (state in BLOCKED or reason == "engine_error"):
        # The coordinator cannot go on (its turn failed for good, or the route was taken away): people take over.
        await fail_link(db, link)


def _card(approval_id: str, status: str, summary: dict, expires_at: str | None = None) -> dict:
    """body.platform of an approval message, as the resident's app draws it: the question and, when it is about a
    cost, the amounts in whole dong. The tool's name and its arguments (ids) stay in platform_approvals."""
    shown: dict[str, object] = {"text": str(summary.get("text") or "").strip() or ASK_TEXT}
    items, total = summary.get("items"), str(summary.get("total", "")).strip()
    if isinstance(items, list) and items and all(isinstance(item, dict) and str(item.get("amount", "")).strip().isdigit() for item in items):
        shown["arguments"] = {"items": [{"label": str(item.get("label", "")), "amount": int(str(item["amount"]).strip())} for item in items],
                              **({"total": int(total)} if total.isdigit() else {})}
    return {"kind": "approval", "approval_id": approval_id, "status": status, "summary": shown,
            **({"expires_at": expires_at} if expires_at else {})}


async def ask_approval(db, link, approval: dict) -> None:
    """The coordinator needs the resident's agreement: keep what the answer must carry and show a card in the chat."""
    summary = approval.get("summary") if isinstance(approval.get("summary"), dict) else {}
    await db.execute(text(f"""
        insert into platform_approvals(approval_id,tenant_id,ticket_id,summary,arguments_hash,quote_ref,expected_revision,expires_at)
        values (:id,{TENANT},:ticket,cast(:summary as jsonb),:hash,:quote,:revision,:expires) on conflict (approval_id) do nothing
    """), {"id": approval["approval_id"], "ticket": link["ticket_id"], "summary": json.dumps(summary, ensure_ascii=False),
           "hash": approval["arguments_hash"], "quote": approval.get("quote_ref"), "revision": approval["expected_revision"],
           "expires": datetime.fromisoformat(approval["expires_at"]) if approval.get("expires_at") else None})
    card = _card(approval["approval_id"], "pending", summary, approval.get("expires_at"))
    await post_chat(db, link, approval["approval_id"], {"text": card["summary"]["text"], "platform": card})


async def apply_event(db, link, event: dict) -> None:
    """One event of the conversation's log (spec 5.2 step 2). Safe to apply again."""
    kind, payload = event["event_type"], event.get("payload") or {}
    if kind == "assistant.message":
        if str(payload.get("text") or "").strip():
            await post_chat(db, link, payload["message_id"], {"text": payload["text"]})
    elif kind.startswith("workflow."):
        await set_state(db, link, payload["state"], payload["revision"], payload.get("reason"))
    elif kind == "approval.required":
        await ask_approval(db, link, payload)
    elif kind == "approval.resolved":
        # The platform also withdraws (cancelled) and lets expire; for the resident both mean it is over.
        status = payload["status"] if payload["status"] in ("approved", "rejected") else "expired"
        known = (await db.execute(text(f"update platform_approvals set status=:status where approval_id=:id and tenant_id={TENANT} returning summary"),
                                  {"status": status, "id": payload["approval_id"]})).first()
        if known is not None:
            # The same card again with its outcome: the app shows the latest message of an approval.
            await post_chat(db, link, event["event_id"], {"text": RESOLVED_TEXT[status],
                                                          "platform": _card(payload["approval_id"], status, known[0])})


async def apply_result(db, link, answer: dict) -> None:
    """The answer to a command: the platform's ids, where the workflow stands, and the coordinator's messages.
    The same messages come again as events; the chat gets each once."""
    await db.execute(text(f"""
        update platform_links set conversation_id=coalesce(:conversation,conversation_id),workflow_id=coalesce(:workflow,workflow_id),
          status=case when status='pending' then 'open' else status end
        where ticket_id=:ticket and tenant_id={TENANT}
    """), {"ticket": link["ticket_id"], "conversation": answer.get("conversation_id"), "workflow": answer.get("workflow_id")})
    state, revision = answer.get("workflow_state") or answer.get("state"), answer.get("workflow_revision", answer.get("revision"))
    if state and revision is not None:
        await set_state(db, link, state, revision)
    for message in (answer.get("result") or {}).get("messages") or []:
        if str(message.get("text") or "").strip():
            await post_chat(db, link, message["message_id"], {"text": message["text"]})


async def apply_snapshot(db, link, snapshot: dict) -> str | None:
    """Catch up from the whole conversation when the event cursor is gone; returns the cursor to go on from."""
    for workflow in snapshot.get("workflows") or []:
        if workflow["workflow_id"] == link["workflow_id"]:
            await set_state(db, link, workflow["state"], workflow["revision"])
    for message in snapshot.get("messages") or []:
        if message.get("sender") == "assistant" and str(message.get("text") or "").strip():
            await post_chat(db, link, message["message_id"], {"text": message["text"]})
    # Each carries its approval.required payload; one with only its id cannot be decided, so it shows no card.
    for approval in snapshot.get("pending_approvals") or []:
        if "summary" in approval:
            await ask_approval(db, link, approval)
    return snapshot.get("snapshot_cursor")


async def fail_link(db, link, status: str = "failed") -> None:
    """The platform will not work on this request: the chat goes back to Reception and the resident is told, once,
    in words that promise only what is true. A workflow that simply ended (`closed`) is no failure to tell of:
    what still waited to be sent is dropped, and the reader closes the link (platform_sync._read)."""
    if status == "failed":
        await db.execute(text(f"update platform_links set status='failed' where ticket_id=:ticket and tenant_id={TENANT} and status in {ACTIVE}"),
                         {"ticket": link["ticket_id"]})
    await db.execute(text(f"""
        update platform_commands set status='failed',last_error=coalesce(last_error,'the link is '||:status)
        where ticket_id=:ticket and tenant_id={TENANT} and status='pending'
    """), {"status": status, "ticket": link["ticket_id"]})
    if status == "failed":
        await post_chat(db, link, f"failed:{link['ticket_id']}", {"text": FAILED_TEXT})


# ---- the repair quote, shown to the resident by the domain itself --------------------------------------------------

def _dong(amount: int) -> str:
    return f"{amount:,}".replace(",", ".") + " đồng"


def quote_card(quote) -> dict:
    """The chat message of one quote: the bill in words, for a client that draws no card, and the same bill as data.
    The technician's own note stays out: it was not written for the resident."""
    detail = quote["detail"]
    lines = [{"name": line["name"], "quantity": float(line["quantity"]) if float(line["quantity"]) % 1 else int(float(line["quantity"])),
              "unit": line["unit"], "unit_price": line["unit_price"], "amount": line["amount"]} for line in detail.get("lines") or []]
    labor, months = detail.get("labor_cost") or 0, detail.get("warranty_months") or 0
    total = sum(line["amount"] for line in lines) + labor
    words = ["Báo giá sửa chữa của nhân viên:",
             *(f"- {line['name']} ({line['quantity']} {line['unit']}): {_dong(line['amount'])}" for line in lines),
             *([f"- Tiền công: {_dong(labor)}"] if labor else []),
             f"Tổng cộng: {_dong(total)}." + (f" Bảo hành {months} tháng." if months else ""),
             "Bạn xem rồi bấm Đồng ý hoặc Không đồng ý trên thẻ báo giá này."]
    return {"text": "\n".join(words), "platform": {
        "kind": "quote", "approval_id": str(quote["id"]), "lines": lines, "labor_cost": labor, "warranty_months": months,
        "total": total, "expires_at": quote["expires_at"].isoformat() if quote["expires_at"] else None}}


async def quote_states(db, messages: list[dict]) -> None:
    """Adds platform.status to every quote card among these chat messages: where the quote stands now, read from the
    quote itself and never stored in the message. A quote that was withdrawn reads as expired."""
    cards = [m["body"]["platform"] for m in messages
             if isinstance(m["body"], dict) and isinstance(m["body"].get("platform"), dict) and m["body"]["platform"].get("kind") == "quote"]
    if not cards:
        return
    rows = await db.execute(text(f"""
        select cast(id as text),case when status='pending' and expires_at<=now() then 'expired'
          when status in ('pending','approved','rejected') then status else 'expired' end
        from work_approvals where cast(id as text)=any(:ids) and tenant_id={TENANT}
    """), {"ids": [card["approval_id"] for card in cards]})
    states = dict(rows.all())
    for card in cards:
        card["status"] = states.get(card["approval_id"], "expired")


# ---- an amenity booking, confirmed by the resident's own tap ---------------------------------------------------------

BOOKING_MINUTES = 15  # how long a card may be confirmed: after that the slot is asked for again


def booking_card(card_id: str, amenity: dict, wanted, total: int) -> dict:
    """The chat message that offers one booking. It books nothing: see confirm_booking."""
    when = f"{vn_time(wanted.start_at)} đến {wanted.end_at.astimezone(VN):%H:%M}"
    words = [f"Đặt {amenity['name']} ({wanted.area_code}): {when}, {wanted.guests} người.",
             f"Phí: {_dong(total)}." if total else "Miễn phí.", "Bạn bấm Xác nhận đặt chỗ trên thẻ này để giữ chỗ."]
    return {"text": "\n".join(words), "platform": {
        "kind": "booking", "card_id": card_id, "amenity_id": str(amenity["id"]), "amenity": amenity["name"], "area": wanted.area_code,
        "unit_id": str(wanted.unit_id), "start_at": wanted.start_at.isoformat(), "end_at": wanted.end_at.isoformat(), "guests": wanted.guests,
        "total": total, "expires_at": (datetime.now(UTC) + timedelta(minutes=BOOKING_MINUTES)).isoformat()}}


def _booking_cards(messages: list[dict]) -> list[dict]:
    return [m["body"]["platform"] for m in messages
            if isinstance(m["body"], dict) and isinstance(m["body"].get("platform"), dict) and m["body"]["platform"].get("kind") == "booking"]


async def booking_states(db, actor_id: str, messages: list[dict]) -> None:
    """Adds platform.status to every booking card among these chat messages: `booked` once the resident confirmed it
    (with where the booking stands), else `pending` or `expired`. Read from the bookings, never stored in the message."""
    cards = _booking_cards(messages)
    if not cards:
        return
    rows = await db.execute(text(f"select idempotency_key,status from amenity_bookings where idempotency_key=any(:keys) and tenant_id={TENANT}"),
                            {"keys": [f"{actor_id}:{card['card_id']}" for card in cards]})
    made = dict(rows.all())
    for card in cards:
        booking = made.get(f"{actor_id}:{card['card_id']}")
        card["status"] = "booked" if booking else "expired" if datetime.fromisoformat(card["expires_at"]) <= datetime.now(UTC) else "pending"
        if booking:
            card["booking_status"] = booking


@router.post("/resident/platform/bookings/{card_id}/confirm", summary="Book what the coordinator's card in my chat offers")
async def confirm_booking(scope: ResidentScope, card_id: str = Path(min_length=8, max_length=200)) -> dict[str, object]:
    db, actor_id = scope
    found = (await db.execute(text(f"""
        select m.body,l.ticket_id from platform_inbox i
        join platform_links l on l.ticket_id=i.ticket_id and l.tenant_id=i.tenant_id
        join messages m on m.id=i.chat_message_id and m.tenant_id=i.tenant_id and m.channel_id=l.channel_id
        where i.platform_id=:id and l.user_id=:actor and i.tenant_id={TENANT}
    """), {"id": "booking:" + card_id, "actor": actor_id})).mappings().first()
    if found is None:
        raise HTTPException(404, "Booking card not found")
    card = found["body"]["platform"]
    from .resident_services import BookingCreate, book

    already = (await db.execute(text(f"select 1 from amenity_bookings where idempotency_key=:key and tenant_id={TENANT}"),
                                {"key": f"{actor_id}:{card_id}"})).first()
    if already is None and datetime.fromisoformat(card["expires_at"]) <= datetime.now(UTC):
        raise HTTPException(409, "Thẻ đặt chỗ đã hết hạn. Bạn nhắn lại để được đặt lượt khác.")
    # The resident's own booking, under every rule of the amenity; the card id makes a second tap the same booking.
    made = await book(BookingCreate(unit_id=card["unit_id"], amenity_id=card["amenity_id"], area_code=card["area"],
                                    start_at=card["start_at"], end_at=card["end_at"], guests=card["guests"]), (db, actor_id), card_id)
    if already is None:
        waits = made["status"] == "pending_payment"
        # `own`: the bridge's words, so that the coordinator knows and can tell the resident what comes next.
        await command(db, found["ticket_id"], "workflow_reply", {"own": True, "text":
                      f"Tôi đã bấm xác nhận đặt {card['amenity']} ({card['area']}), {vn_time(made['start_at'])}. "
                      + ("Lượt đặt đang chờ thanh toán." if waits else "Lượt đặt đã được xác nhận.")})
    return {"card_id": card_id, "status": "booked", "booking_status": made["status"]}


# ---- staff progress, as the platform's provider events (spec section 7) --------------------------------------------

def _quote(context: dict) -> dict:
    """Materials line by line and labour as its own line, in whole dong, so the total is the sum of the amounts."""
    detail = context["quote"]["detail"]
    items = [{"label": f"{line['name']} ({line['quantity']} {line['unit']})", "amount": line["amount"]}
             for line in detail.get("lines") or []]
    if detail.get("labor_cost"):
        items.append({"label": "Tiền công", "amount": detail["labor_cost"]})
    return {"items": items, "total": sum(item["amount"] for item in items), "currency": "VND", "warranty_months": detail.get("warranty_months", 0),
            **({"approval_id": str(context["quote"]["id"])} if context["quote"].get("id") else {})}


def _staff(context: dict) -> dict:
    return {"staff_name": context.get("staff_name") or "Nhân viên kỹ thuật"}


def _responded(payload: dict, context: dict):
    if payload.get("status") == "rejected":
        return "job.declined", {}
    eta = context.get("eta_at")
    return "job.accepted", {**_staff(context), **({"eta": vn_time(eta)} if eta else {})}


def _status_changed(payload: dict, context: dict):
    # The staff member's own note stays in the domain: it was not written for the resident.
    return {"en_route": ("job.en_route", _staff(context)), "arrived": ("job.arrived", _staff(context)),
            "in_progress": ("job.started", {}), "completed": ("job.completed", {}),
            "cancelled": ("job.cancelled", {"reason": "Yêu cầu được hủy theo đề nghị của cư dân" if payload.get("cancelledBy") == "resident"
                                            else "Nhân viên báo không thực hiện được việc này"})}.get(payload.get("status"))


def _decided(payload: dict, context: dict):
    quote = context.get("quote")
    # A completion answer ends the workflow by a command, not by a progress event.
    if not quote or quote["kind"] != "customer_repair" or payload.get("status") not in ("approved", "rejected"):
        return None
    # Two event types: the platform's message template cannot say one thing or the other.
    return "job.quote_" + payload["status"], {}


def _published(payload: dict, context: dict):
    # The event is about the ticket; context["result"] is the finished job it reports (platform_sync._context).
    result = context.get("result")
    if not result:
        return None
    # The technician's acceptance report with what they wrote for the resident, or management's own inspection.
    reporter, note = result["reported_by"], " ".join((result["note"] or "").split())
    summary = "Nhân viên đã làm xong và gửi kết quả nghiệm thu." if reporter else "Công việc đã làm xong và Ban quản lý đã nghiệm thu."
    if reporter and note:
        summary = f"{summary} Ghi chú của nhân viên: {note}"
    return "job.result_published", {"summary": summary if len(summary) <= 200 else summary[:199] + "…",
                                    "photo_count": int(result["photo_count"]), "reported_by": reporter or "Ban quản lý"}


def result_text(data: dict) -> str:
    """The chat line of a published result, from the same data the platform is sent (job.result_published)."""
    return (f"{data['summary']}\nNgười gửi: {data['reported_by']}. Số ảnh của nhân viên: {data['photo_count']}.\n"
            "Bạn xem rồi bấm Xác nhận hoàn thành hoặc Chưa đạt ngay trong hộp chat này.")


# Domain event -> (provider event, the fields the resident may see), or None when it says nothing to the platform.
PROGRESS = {
    "work_order.offered": lambda payload, context: ("job.offered", {}),
    "work_assignment.responded": _responded,
    "work_assignment.expired": lambda payload, context: ("job.offer_expired", {}),
    "work_order.unassigned": lambda payload, context: ("job.unassigned", {}),
    "work_order.rescheduled": lambda payload, context: ("job.rescheduled", {"appointment": vn_time(datetime.fromisoformat(payload["appointmentAt"]))}),
    "work_order.status_changed": _status_changed,
    "work_order.repair_proposed": lambda payload, context: ("job.quote_ready", _quote(context)) if context.get("quote") else None,
    "work_approval.decided": _decided,
    "ticket.resolution_published": _published,
}


def provider_events(event: dict, context: dict) -> dict | None:
    """The progress event one ticket event becomes. Pure: everything it needs is in its arguments.

    event: a ticket_events row (id, ticket_id, seq, event_type, payload, occurred_at).
    context: work_order_id the event is about; operations {work_order_id: client_reference} of the work the platform
      dispatched on this ticket; staff_name and eta_at of the assignment; quote {id, kind, detail} of the approval;
      result {photo_count, reported_by (the technician who sent the acceptance report; None after management's
      inspection), note} of the finished job when the ticket's result was published.
    None: nothing to send. That includes work the platform did not dispatch (no operation for its work order).
    """
    mapped = PROGRESS.get(event["event_type"])
    made = mapped(event.get("payload") or {}, context) if mapped else None
    work = str(context.get("work_order_id") or "")
    reference = (context.get("operations") or {}).get(work)
    if made is None or reference is None:
        return None
    return {"event_type": made[0], "client_reference": reference, "external_job_id": work, "data": made[1]}


def event_body(row) -> bytes:
    """The bytes of one platform_outbox row. Built from the stored row alone, so sending again sends the same bytes."""
    return json.dumps({
        "schema_version": "1", "external_event_id": str(row["event_id"]), "external_job_id": row["external_job_id"],
        "client_reference": row["client_reference"], "event_type": row["event_type"],
        "provider_version": row["provider_version"],
        "occurred_at": row["occurred_at"].astimezone(UTC).strftime("%Y-%m-%dT%H:%M:%S.%fZ"), "data": row["data"],
    }, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode()


# ---- operator commands -------------------------------------------------------------------------------------------

async def _operator_bridge() -> Bridge | None:
    url = os.environ.get('DATABASE_URL')
    if not url:
        return Bridge.from_env()
    from sqlalchemy.ext.asyncio import create_async_engine
    from .platform_settings import load_bridge
    from .database import TENANT as DEFAULT_TENANT
    engine = create_async_engine(url.replace('postgresql://', 'postgresql+asyncpg://', 1))
    try:
        async with engine.begin() as db:
            await db.execute(text("SELECT set_config('app.tenant_id',:tenant,true)"),
                             {'tenant': os.getenv('VINHOMES_API_TENANT_ID') or DEFAULT_TENANT})
            return await load_bridge(db)
    finally:
        await engine.dispose()


async def _confirm_routes(routes: list[str]) -> int:
    bridge = await _operator_bridge()
    if bridge is None:
        raise SystemExit('Platform bridge is disabled')
    platform, failed = Platform(bridge), 0
    try:
        for item in routes:
            management_ref, _, rest = item.partition("=")
            route_id, _, revision = rest.rpartition(":")
            if not management_ref or not route_id or not revision.isdigit():
                raise SystemExit(f"--route {item}: expected <management_ref>=<route_id>:<revision>")
            try:
                done = await platform.confirm_route(route_id, management_ref, int(revision))
                print(management_ref, route_id, done["status"], "revision", done["revision"])
            except (httpx.HTTPError, PlatformError) as exc:
                failed += 1
                print(management_ref, route_id, "FAILED", exc if isinstance(exc, PlatformError) else type(exc).__name__)
    finally:
        await platform.aclose()
    return 1 if failed else 0


async def _status() -> int:
    bridge = await _operator_bridge()
    if bridge is None:
        print("bridge: off (disabled in admin settings or environment)")
        return 0
    print("bridge: on,", bridge.url, "| MCP token:", "set" if bridge.mcp_token else "not set")
    platform = Platform(bridge)
    try:
        # A key the platform knows gets 404 for a thing that does not exist; an unknown key gets 401.
        for name, call in (("customer key", lambda: platform.snapshot("status-check", "status-check")),
                           ("provider key", lambda: platform.receipt("status-check"))):
            try:
                await call()
                print(name + ": accepted")
            except PlatformError as exc:
                print(name + ":", "accepted" if exc.status == 404 else f"refused ({exc.code})")
            except httpx.HTTPError as exc:
                print(name + ": platform not reached", f"({type(exc).__name__})")
    finally:
        await platform.aclose()
    url = os.environ.get("DATABASE_URL")
    if url:
        from sqlalchemy.ext.asyncio import create_async_engine
        engine = create_async_engine(url.replace("postgresql://", "postgresql+asyncpg://", 1))
        try:
            async with engine.connect() as probe:
                tenants = [str(row[0]) for row in await probe.execute(text("select id from tenants where status='active'"))]
            for tenant in tenants:
                async with engine.begin() as db:
                    await db.execute(text("select set_config('app.tenant_id',:t,true)"), {"t": tenant})
                    counts = await db.execute(text("""
                        select 'links' as what,status,count(*) from platform_links group by status
                        union all select 'commands',status,count(*) from platform_commands group by status
                        union all select 'progress events',status,count(*) from platform_outbox group by status order by 1,2
                    """))
                    print(tenant, ", ".join(f"{what} {status}: {n}" for what, status, n in counts) or "nothing yet")
        finally:
            await engine.dispose()
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="python -m vinhomes_api.platform")
    commands = parser.add_subparsers(dest="command", required=True)
    confirm = commands.add_parser("confirm-routes", help="confirm the platform's routes with the customer key")
    confirm.add_argument("--route", action="append", required=True, metavar="<management_ref>=<route_id>:<revision>")
    commands.add_parser("status", help="is the bridge configured, are the keys accepted, what waits")
    args = parser.parse_args(argv)
    if args.command == "status":
        return asyncio.run(_status())
    return asyncio.run(_confirm_routes(args.route))


if __name__ == "__main__":
    sys.exit(main())
