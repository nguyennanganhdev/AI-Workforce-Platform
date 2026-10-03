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
from .v3_learning import approved_guidance
from .v3_resident import _owned_chat

log = logging.getLogger(__name__)
router = APIRouter(tags=["Reception runtime API"])
TENANT = "nullif(current_setting('app.tenant_id',true),'')::uuid"
POLICY_VERSION = "vinhomes-reception-policy-1"
UNAVAILABLE_REPLY = "Trợ lý lễ tân tạm thời chưa phản hồi được. Bạn có thể gửi phản ánh bằng biểu mẫu trong cuộc trò chuyện này."

# Danger to people or the building. Matched with diacritics: without them "cháy" (fire)
# and "chảy" (leaking) are the same letters, and a leak must not page as an emergency.
# Grouped by what the resident should do meanwhile: management approves safety guidance per kind.
EMERGENCY_KINDS = {
    "fire": ("cháy", "bốc khói", "khói bốc", "khói đen", "mùi khét", "tia lửa", "nổ lớn"),
    "gas": ("mùi gas", "mùi ga", "rò gas", "rò rỉ gas"),
    "electric": ("chập điện", "giật điện"),
    "elevator": ("kẹt thang máy", "kẹt trong thang"),
    "water": ("ngập nước", "vỡ ống nước"),
    "structure": ("sập trần",),
}
EMERGENCY_TERMS = tuple(term for terms in EMERGENCY_KINDS.values() for term in terms)


# Everyday uses of "cháy" that are a broken part, not a fire. Removed before matching, so
# "bóng đèn bị cháy, có mùi khét và bốc khói" is still an emergency through its other terms.
BENIGN_TERMS = ("cháy bóng", "bóng đèn bị cháy", "bóng đèn cháy", "bóng bị cháy", "đèn bị cháy", "cháy cầu chì", "cầu chì bị cháy",
                "cơm bị cháy", "cơm cháy", "nấu ăn bị cháy", "đồ ăn bị cháy", "cháy nắng")


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
    proposal = body.assessment or {}
    # The keyword list cannot cover every phrasing. The model may raise an emergency;
    # it can never lower one the keywords found.
    kind = next((name for name, terms in EMERGENCY_KINDS.items() if any(term in message for term in terms)), None)
    emergency = kind is not None or proposal.get("proposed_action") == "emergency_handoff"
    # Safety advice is only ever the text management approved for this kind at the resident's home.
    guidance = await approved_guidance(scope[0], scope[1]["user_id"], kind) if kind else None
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
        **({"safety_guidance": guidance} if guidance else {}),
    }


async def append_agent_message(db: AsyncConnection, channel_id: str, agent: str, visibility: str,
                               body: dict[str, object], reply_to: UUID | None = None) -> dict[str, object]:
    seq = (await db.execute(text("""
        update channels set next_message_seq=next_message_seq+1,last_message=:preview,last_message_at=now(),updated_at=now()
        where id=:id returning next_message_seq-1
    """), {"id": channel_id, "preview": str(body.get("text", ""))[:200]})).scalar_one()
    created = await db.execute(text(f"""
        insert into messages(tenant_id,channel_id,seq,sender_kind,sender_agent_id,visibility,body,reply_to_id)
        values ({TENANT},:channel,:seq,'agent',:agent,:visibility,cast(:body as jsonb),:reply_to)
        returning id,seq
    """), {"channel": channel_id, "seq": seq, "agent": agent, "visibility": visibility,
           "body": json.dumps(body, ensure_ascii=False), "reply_to": reply_to})
    return dict(created.mappings().one())


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
    return await append_agent_message(db, channel_id, agent, "customer", {"text": reply}, reply_to)


@router.get("/internal/reception/chats/{channel_id}/context",
            summary="What an agent needs to continue this conversation: its recent messages and open request")
async def conversation_context(channel_id: str, scope: Scope) -> dict[str, object]:
    db, run = scope
    if channel_id != run["channel_id"]:
        raise HTTPException(403, "Channel differs from delegated binding")
    messages = await db.execute(text(f"""
        select id,sender_kind,body->>'text' as text from messages
        where channel_id=:channel and tenant_id={TENANT} and visibility in ('room','customer') and body->>'text'<>''
        order by seq desc limit 30
    """), {"channel": channel_id})
    history = [{"id": str(m["id"]), "role": "resident" if m["sender_kind"] == "user" else "reception", "text": m["text"]}
               for m in messages.mappings()][::-1]
    # The conversation's request still being worked on, with the message the Supervisor received for it.
    request = (await db.execute(text(f"""
        select t.id,t.code,t.title,t.status,t.version,t.priority,
          (select s.payload from vh_reception_supervisor_messages s
            where s.ticket_id=t.id and s.tenant_id=t.tenant_id and s.message_type='ticket_submitted'
            order by s.created_at desc limit 1) as submitted
        from tickets t where t.channel_id=:channel and t.tenant_id={TENANT} and t.requester_user_id=:actor
          and t.status not in ('closed','cancelled') order by t.created_at desc limit 1
    """), {"channel": channel_id, "actor": run["user_id"]})).mappings().first()
    # The resident's own earlier requests: what the agent may remember about them across conversations.
    past = await db.execute(text(f"""
        select t.id,t.title,t.status,c.name as category,t.created_at::date as created_on
        from tickets t left join service_categories c on c.id=t.category_id
        where t.tenant_id={TENANT} and t.requester_user_id=:actor and t.id is distinct from cast(:open as uuid)
        order by t.created_at desc limit 5
    """), {"actor": run["user_id"], "open": str(request["id"]) if request else None})
    return {"history": history, "open_request": dict(request) if request else None,
            "past_requests": [{**dict(row), "id": str(row["id"])} for row in past.mappings()]}


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
    run_id, delivered, usage = None, False, None
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
        if delivered:
            usage = response.json().get("usage")
        if not delivered:
            log.warning("Reception runtime returned HTTP %s", response.status_code)
    except httpx.HTTPError as exc:
        log.warning("Reception runtime is unreachable: %s", type(exc).__name__)
    except Exception:  # noqa: BLE001 - the resident still gets the fallback reply below
        log.exception("Could not open the Reception run")
    try:
        async with _resident_transaction(app, actor_id) as db:
            if run_id:
                await finish_run(db, run_id, delivered, usage if isinstance(usage, dict) else None)
            if not delivered:
                # The resident must not be left without an answer when the runtime is down.
                await write_reply(db, channel_id, UNAVAILABLE_REPLY, UUID(str(message["id"])))
    except Exception:  # noqa: BLE001 - a failed fallback must not crash the background task
        log.exception("Could not close the Reception run")
