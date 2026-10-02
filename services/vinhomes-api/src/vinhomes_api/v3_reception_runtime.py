"""Backend side of the Reception runtime: request policy, catalog, replies and dispatch.

The Reception agent runs in its own service. The backend opens a run for each resident
message and the runtime reaches these routes with that run's delegation (see
reception_delegation); the model never decides policy.
"""

import json
import logging
import unicodedata
from contextlib import asynccontextmanager
from typing import Any
from uuid import UUID

import httpx
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncConnection

from .reception_delegation import DelegatedScope as Scope
from .reception_delegation import finish_run, reception_agent, start_run
from .v3_resident import _owned_chat

log = logging.getLogger(__name__)
router = APIRouter(tags=["Reception runtime API"])
TENANT = "nullif(current_setting('app.tenant_id',true),'')::uuid"
POLICY_VERSION = "vinhomes-reception-policy-1"
UNAVAILABLE_REPLY = "Trợ lý lễ tân tạm thời chưa phản hồi được. Bạn có thể gửi phản ánh bằng biểu mẫu trong cuộc trò chuyện này."

# Danger to people or the building. Matched with diacritics: without them "cháy" (fire)
# and "chảy" (leaking) are the same letters, and a leak must not page as an emergency.
EMERGENCY_TERMS = (
    "cháy", "bốc khói", "khói đen", "mùi gas", "mùi ga", "rò gas", "rò rỉ gas", "chập điện", "giật điện",
    "tia lửa", "nổ lớn", "kẹt thang máy", "kẹt trong thang", "ngập nước", "vỡ ống nước", "sập trần",
)


# Everyday uses of "cháy" that are a broken part, not a fire. Removed before matching, so
# "bóng đèn bị cháy, có mùi khét và bốc khói" is still an emergency through its other terms.
BENIGN_TERMS = ("cháy bóng", "bóng đèn bị cháy", "bóng đèn cháy", "bóng bị cháy", "đèn bị cháy", "cháy cầu chì", "cầu chì bị cháy")


class PolicyRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    message_text: str = Field(max_length=16384)
    assessment: dict[str, Any] | None = None


@router.get("/internal/reception/catalog", summary="Service categories the Reception runtime may choose from")
async def catalog(scope: Scope) -> dict[str, object]:
    rows = await scope[0].execute(text("select id,code,name from service_categories where enabled order by name"))
    return {"categories": [dict(r) for r in rows.mappings()]}


@router.post("/internal/reception/policy/evaluate", summary="Authoritative request policy for one resident turn")
async def evaluate_policy(body: PolicyRequest, scope: Scope) -> dict[str, object]:
    message = unicodedata.normalize("NFC", body.message_text.lower())
    for term in BENIGN_TERMS:
        message = message.replace(term, " ")
    emergency = any(term in message for term in EMERGENCY_TERMS)
    proposal = body.assessment or {}
    declined, failed = proposal.get("self_help_declined") is True, proposal.get("self_help_failed") is True
    staff_required = emergency or declined or failed or proposal.get("explicit_staff_request") is True \
        or proposal.get("intent") in {"incident", "service_request"}
    return {
        "policy_version": POLICY_VERSION,
        "emergency": emergency,
        "staff_required": staff_required,
        # No reviewed self-help procedure is published yet, so none may be offered.
        "self_help_allowed": False,
        "missing_information": [],
        "handoff_reason": "emergency" if emergency else "self_help_declined" if declined
        else "self_help_failed" if failed else "needs_staff",
    }


async def write_reply(db: AsyncConnection, channel_id: str, reply: str, reply_to: UUID) -> dict[str, object]:
    """One agent reply per resident message; a retry returns the stored reply."""
    agent = await reception_agent(db)
    # Serialized on the conversation row, so a retry sees the stored reply.
    await db.execute(text("select 1 from channels where id=:id for update"), {"id": channel_id})
    old = (await db.execute(text("""
        select id,seq from messages where channel_id=:channel and reply_to_id=:reply_to and sender_agent_id=:agent
    """), {"channel": channel_id, "reply_to": reply_to, "agent": agent})).mappings().first()
    if old:
        return dict(old)
    seq = (await db.execute(text("""
        update channels set next_message_seq=next_message_seq+1,last_message=:preview,last_message_at=now(),updated_at=now()
        where id=:id returning next_message_seq-1
    """), {"id": channel_id, "preview": reply[:200]})).scalar_one()
    created = await db.execute(text(f"""
        insert into messages(tenant_id,channel_id,seq,sender_kind,sender_agent_id,visibility,body,reply_to_id)
        values ({TENANT},:channel,:seq,'agent',:agent,'customer',cast(:body as jsonb),:reply_to)
        returning id,seq
    """), {"channel": channel_id, "seq": seq, "agent": agent,
           "body": json.dumps({"text": reply}, ensure_ascii=False), "reply_to": reply_to})
    return dict(created.mappings().one())


class ReplyCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    text: str = Field(min_length=1, max_length=10000)
    reply_to_id: UUID


@router.post("/internal/reception/chats/{channel_id}/replies", status_code=201,
             summary="Store the Reception reply to one resident message")
async def create_reply(channel_id: str, body: ReplyCreate, scope: Scope) -> dict[str, object]:
    db, run = scope
    if channel_id != run["channel_id"]:
        raise HTTPException(403, "Channel differs from delegated binding")
    await _owned_chat((db, run["user_id"]), channel_id, lock=True)
    source = await db.execute(text("""
        select 1 from messages where id=:id and channel_id=:channel and sender_kind='user' and sender_user_id=:actor
    """), {"id": body.reply_to_id, "channel": channel_id, "actor": run["user_id"]})
    if source.first() is None:
        raise HTTPException(422, "reply_to_id must be a resident message in this conversation")
    return await write_reply(db, channel_id, body.text, body.reply_to_id)


@asynccontextmanager
async def _resident_transaction(app, actor_id: str):
    async with app.state.engine.begin() as db:
        await db.execute(text("select set_config('app.tenant_id', :tenant, true), set_config('app.user_id', :user, true)"),
                         {"tenant": str(app.state.settings.tenant_id), "user": actor_id})
        yield db


async def dispatch_turn(app, actor_id: str, channel_id: str, message: dict[str, object]) -> None:
    """Run after the resident message is committed; the runtime stores its own reply."""
    settings = app.state.settings
    run_id, delivered = None, False
    try:
        async with _resident_transaction(app, actor_id) as db:
            delegation = await start_run(db, actor_id, channel_id, str(message["id"]), POLICY_VERSION)
        run_id = delegation["context"]["runId"]
        async with httpx.AsyncClient(timeout=180) as client:
            response = await client.post(
                f"{settings.reception_url}/v1/turns",
                # The service token only proves this call comes from the backend.
                headers={"Authorization": f"Bearer {settings.reception_service_token}"},
                json={"user_id": actor_id, "channel_id": channel_id, "message": message, "delegation": delegation},
            )
        delivered = response.status_code == 200
        if not delivered:
            log.warning("Reception runtime returned HTTP %s", response.status_code)
    except httpx.HTTPError as exc:
        log.warning("Reception runtime is unreachable: %s", type(exc).__name__)
    except Exception:  # noqa: BLE001 - the resident still gets the fallback reply below
        log.exception("Could not open the Reception run")
    try:
        async with _resident_transaction(app, actor_id) as db:
            if run_id:
                await finish_run(db, run_id, delivered)
            if not delivered:
                # The resident must not be left without an answer when the runtime is down.
                await write_reply(db, channel_id, UNAVAILABLE_REPLY, UUID(str(message["id"])))
    except Exception:  # noqa: BLE001 - a failed fallback must not crash the background task
        log.exception("Could not close the Reception run")
