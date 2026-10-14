"""Backend side of the Reception runtime: request policy, catalog, replies and dispatch.

The Reception agent runs in its own service. The backend opens a run for each resident
message and the runtime reaches these routes with that run's delegation (see
reception_delegation); the model never decides policy.
"""

import json
import logging
import re
from contextlib import AsyncExitStack, asynccontextmanager
from datetime import UTC, datetime
from typing import Any, Literal
from uuid import NAMESPACE_URL, UUID, uuid5

import httpx
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncConnection, create_async_engine
from sqlalchemy.pool import NullPool

from .reception_delegation import DelegatedScope as Scope
from .reception_delegation import finish_run, reception_client, start_run
from .reception_intake import assess, conversation, fold, negated
from .v3_reception_supervisor import WIRE_TICKET, current_wire
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


# Everyday uses of "cháy" that are a broken part or burnt food, not a fire. Removed before matching, so
# "bóng đèn bị cháy, có mùi khét và bốc khói" is still an emergency through its other terms.
BENIGN_TERMS = ("cháy bóng", "cháy cầu chì", "cơm bị cháy", "cơm cháy", "nấu ăn bị cháy", "đồ ăn bị cháy", "cháy nắng")
# A bulb or a fuse that burnt out: a whole clause that names the lamp, then "cháy", and around them only the words
# below (who asks, where the lamp is, "bị", "rồi"). Any other word leaves "cháy" a fire: a verb ("đèn bắt cháy"),
# something else that burns ("cạnh cột đèn có xe máy cháy"), how it burns ("cháy dữ dội", "cháy lan sang rèm").
# A wrong guess must fall on the side of the fire.
_ASKING = "nhà|tôi|em|mình|anh|chị|cái|chiếc|mấy|các|nhờ|xin|cần|thay|sửa|giúp|báo|ban|quản|lý|bql|thợ|kỹ|thuật|cho|ơi|dạ|ạ|chào"
_PLACE = (r"đèn|led|tuýp|trần|ngủ|chùm|bàn|sưởi|tổng|tủ|điện|phòng|khách|bếp|tắm|vệ|sinh|nhà|hành|lang|ban|công|tầng|ở|trong|ngoài"
          r"|của|tôi|em|mình|số|\w*\d\w*|bị|đã|lại|hay|vừa|mới")
_AFTER = (r"rồi|mất|luôn|hỏng|nữa|ạ|à|nhé|nha|nhờ|xin|cần|thay|sửa|giúp|kiểm|tra|ban|quản|lý|bql|thợ|kỹ|thuật|cho|em|tôi|mình|với"
          r"|mới|được|không|từ|sáng|tối|hôm|qua|nay|cái|bóng|\d+")
BURNT_OUT = re.compile(rf"((?:^|[.,;:!?]) ?(?:(?:{_ASKING}) )*(?:bóng|đèn|cầu chì)(?: (?:{_PLACE}))* )cháy"
                       rf"((?: (?:{_AFTER}))* ?(?=$|[.,;:!?]))")
# Said anywhere in the message, these mean the lamp did more than burn out.
FLAMES = re.compile(r"\b(?:lửa|khói|bén)\b")


def emergency_kind(message_text: str) -> str | None:
    """The danger a message reports. "Không có mùi khét" reports none: a denied term does not count."""
    message = fold(message_text)
    for term in BENIGN_TERMS:
        message = message.replace(term, " ")
    if not FLAMES.search(message):
        message = BURNT_OUT.sub(r"\1\2", message)
    for name, terms in EMERGENCY_KINDS.items():
        for term in terms:
            start = message.find(term)
            while start >= 0:
                if not negated(message, start):
                    return name
                start = message.find(term, start + 1)
    return None


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
    proposal = body.assessment or {}
    # The keyword list cannot cover every phrasing. The model may raise an emergency;
    # it can never lower one the keywords found.
    kind = emergency_kind(body.message_text)
    emergency = kind is not None or proposal.get("proposed_action") == "emergency_handoff"
    # Safety advice is only ever text someone approved for this kind of emergency. This deployment holds
    # none yet (the knowledge pack will), so the Reception agent offers no self-help procedure.
    guidance = None
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
        insert into messages(tenant_id,channel_id,seq,sender_kind,sender_client_id,visibility,body,reply_to_id)
        values ({TENANT},:channel,:seq,'agent',:agent,:visibility,cast(:body as jsonb),:reply_to)
        returning id,seq
    """), {"channel": channel_id, "seq": seq, "agent": agent, "visibility": visibility,
           "body": json.dumps(body, ensure_ascii=False), "reply_to": reply_to})
    return dict(created.mappings().one())


async def write_reply(db: AsyncConnection, channel_id: str, reply: str, reply_to: UUID,
                      clarification: str | None = None, experience: dict | None = None) -> dict[str, object]:
    """One agent reply per resident message; a retry returns the stored reply."""
    agent = await reception_client(db)
    # Serialized on the conversation row, so a retry sees the stored reply.
    await db.execute(text("select 1 from channels where id=:id for update"), {"id": channel_id})
    old = (await db.execute(text("""
        select id,seq from messages where channel_id=:channel and reply_to_id=:reply_to and sender_client_id=:agent
    """), {"channel": channel_id, "reply_to": reply_to, "agent": agent})).mappings().first()
    if old:
        return dict(old)
    # A question the intake rules asked is marked, so a later turn knows how often it was asked.
    body = {"text": reply, **({"clarification": clarification} if clarification else {}),
            **({"reception":experience} if experience else {})}
    created = await append_agent_message(db, channel_id, agent, "customer", body, reply_to)
    await db.execute(text(f"""insert into notification_deliveries
        (tenant_id,user_id,message_id,channel,dedupe_key,payload,status,available_at)
        select {TENANT},c.created_by,:message,'in_app',:key,cast(:payload as jsonb),'pending',now()
        from channels c where c.id=:channel
        on conflict(tenant_id,user_id,channel,dedupe_key) do nothing"""),
        {"channel":channel_id,"message":created['id'],"key":"reception:"+str(created['id']),
         "payload":json.dumps({"type":"reception.message","channelId":channel_id,
                               "title":"Trợ lý cư dân đã phản hồi","message":reply[:200]},ensure_ascii=False)})
    return created


def _own_channel(channel_id: str, run: dict[str, Any]) -> None:
    if channel_id != run["channel_id"]:
        raise HTTPException(403, "Channel differs from delegated binding")


async def _open_request(db: AsyncConnection, channel_id: str, actor: str):
    """The conversation's request still being worked on, with what the Supervisor received and waits for."""
    return (await db.execute(text(f"""
        select t.id,t.code,t.status,{WIRE_TICKET},
          (select s.payload from vh_reception_supervisor_messages s
            where s.ticket_id=t.id and s.tenant_id=t.tenant_id and s.message_type='ticket_submitted'
            order by s.created_at desc limit 1) as submitted,
          (select p.pending_kind from vh_reception_supervisor_pending p
            where p.ticket_id=t.id and p.tenant_id=t.tenant_id and p.ticket_generation=t.reopen_count) as pending
        from tickets t where t.channel_id=:channel and t.tenant_id={TENANT} and t.requester_user_id=:actor
          and t.status not in ('closed','cancelled') order by t.created_at desc limit 1
    """), {"channel": channel_id, "actor": actor})).mappings().first()


@router.get("/internal/reception/chats/{channel_id}/context",
            summary="What an agent needs to continue this conversation: its recent messages and open request")
async def conversation_context(channel_id: str, scope: Scope, message_id: UUID | None = None) -> dict[str, object]:
    db, run = scope
    _own_channel(channel_id, run)
    # Up to the message this turn answers: one sent while the turn runs belongs to its own turn.
    # A message of photos alone has no text and is still part of the conversation.
    messages = await db.execute(text(f"""
        select id,sender_kind,coalesce(body->>'text','') as text,
               jsonb_array_length(coalesce(body->'fileIds','[]'::jsonb)) as photos
        from messages
        where channel_id=:channel and tenant_id={TENANT} and visibility in ('room','customer')
          and (coalesce(body->>'text','')<>'' or jsonb_array_length(coalesce(body->'fileIds','[]'::jsonb))>0)
          and seq<=coalesce((select seq from messages where id=:message and channel_id=:channel), 2147483647)
        order by seq desc limit 30
    """), {"channel": channel_id, "message": message_id})
    history = [{"id": str(m["id"]), "role": "resident" if m["sender_kind"] == "user" else "reception", "text": m["text"],
                "photos": m["photos"]} for m in messages.mappings()][::-1]
    request = await _open_request(db, channel_id, run["user_id"])
    # The resident's own earlier requests: what the agent may remember about them across conversations.
    past = await db.execute(text(f"""
        select t.id,t.title,t.status,c.name as category,t.created_at::date as created_on
        from tickets t left join service_categories c on c.id=t.category_id
        where t.tenant_id={TENANT} and t.requester_user_id=:actor and t.id is distinct from cast(:open as uuid)
        order by t.created_at desc limit 5
    """), {"actor": run["user_id"], "open": str(request["id"]) if request else None})
    open_request = None
    if request:
        open_request = {name: request[name] for name in ("id", "code", "title", "status", "version", "priority")}
        # As the ticket is now: management may have reclassified it since it was handed over.
        open_request["submitted"] = current_wire(request["submitted"], request) if request["submitted"] else None
        # "information": the Supervisor asked the resident something. "plan_approval": a plan waits for their decision.
        open_request["pending"] = request["pending"]
    return {"history": history, "open_request": open_request,
            "past_requests": [{**dict(row), "id": str(row["id"])} for row in past.mappings()]}


class IntakeCheck(BaseModel):
    model_config = ConfigDict(extra="forbid")

    message_id: UUID
    details: dict[str, str] = Field(default_factory=dict, max_length=20)
    kind: Literal["incident", "service_request"] = "incident"
    emergency: bool = False


@router.post("/internal/reception/chats/{channel_id}/intake",
             summary="What would be recorded for these details, and the question to ask when one is missing")
async def intake_check(channel_id: str, body: IntakeCheck, scope: Scope) -> dict[str, object]:
    db, run = scope
    _own_channel(channel_id, run)
    messages, asked = await conversation(db, channel_id, run["user_id"])
    claims = [{"key": key, "value": value} for key, value in body.details.items()]
    return assess(messages, claims, source_message_id=str(body.message_id), kind=body.kind,
                  emergency=body.emergency, asked=asked)


async def attach_photos(db: AsyncConnection, actor: str, ticket_id, file_ids: list) -> list:
    """Photos of a chat message become photos of the request, with the ticket event staff see; returns the new ones."""
    held = await db.execute(text("select file_id from ticket_files where ticket_id=:ticket"), {"ticket": ticket_id})
    known = {str(row[0]) for row in held}
    photos = [file_id for file_id in file_ids if str(file_id) not in known]
    if not photos:
        return []
    from .v3_conversation_images import AttachImages, attach

    await attach(ticket_id, AttachImages(file_ids=photos), (db, actor))
    return photos


class FollowUp(BaseModel):
    model_config = ConfigDict(extra="forbid")

    message_id: UUID


@router.post("/internal/reception/chats/{channel_id}/follow-up",
             summary="Add a resident message to the open request: its photos, and its words as the answer the Supervisor waits for")
async def follow_up(channel_id: str, body: FollowUp, scope: Scope) -> dict[str, object]:
    db, run = scope
    actor = run["user_id"]
    _own_channel(channel_id, run)
    request = await _open_request(db, channel_id, actor)
    message = (await db.execute(text(f"""
        select coalesce(body->>'text','') as text,coalesce(body->'fileIds','[]'::jsonb) as file_ids from messages
        where id=:id and channel_id=:channel and tenant_id={TENANT} and sender_kind='user' and sender_user_id=:actor
    """), {"id": body.message_id, "channel": channel_id, "actor": actor})).mappings().first()
    if request is None or message is None:
        raise HTTPException(404, "No open request or resident message in this conversation")
    # A request whose result waits for the resident's answer takes no photo from Reception: the answer comes first.
    photos = [] if request["status"] == "resolved" else await attach_photos(db, actor, request["id"], message["file_ids"])
    delivered = False
    if request["pending"] == "information" and request["submitted"] and message["text"].strip():
        from .v3_reception_supervisor import ReceptionToSupervisorMessage, submit_reception_message

        # Read again: attaching the photos moved the ticket's version.
        ticket = (await db.execute(text(f"select {WIRE_TICKET} from tickets t where t.id=:id"),
                                   {"id": request["id"]})).mappings().one()
        wire = {**current_wire(request["submitted"], ticket),
                "message_id": str(uuid5(NAMESPACE_URL, f"reception-follow-up:{body.message_id}")),
                "message_type": "information_provided", "message": message["text"].strip()[:10000],
                "sent_at": datetime.now(UTC).isoformat(), "source_message_id": str(body.message_id),
                "facts": [], "file_ids": list(message["file_ids"])}
        await submit_reception_message(ReceptionToSupervisorMessage.model_validate(wire), (db, actor))
        delivered = True
    return {"attached": len(photos), "delivered": delivered, "pending": request["pending"]}


PublicStage = Literal["context", "searching", "request", "status", "responding"]


class ProgressCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")
    stage: PublicStage


@router.post("/internal/reception/chats/{channel_id}/progress")
async def report_progress(channel_id: str, body: ProgressCreate, scope: Scope):
    db,run=scope
    _own_channel(channel_id,run)
    await db.execute(text(f"""update delegations set resident_progress=resident_progress ||
        jsonb_build_array(jsonb_build_object('stage',cast(:stage as text),'at',now()))
        where tenant_id={TENANT} and id=:id and jsonb_array_length(resident_progress)<24"""),
        {"id":run['run_id'],"stage":body.stage})
    return {"ok":True}


class Citation(BaseModel):
    model_config = ConfigDict(extra="forbid")
    title: str = Field(min_length=1,max_length=500)
    excerpt: str = Field(default="",max_length=1200)
    documentId: UUID | None = None
    status: Literal["approved","reference"] = "reference"
    effectiveFrom: str | None = Field(default=None,max_length=40)
    documentReference: str | None = Field(default=None,max_length=200)


class ReplyCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    text: str = Field(min_length=1, max_length=10000)
    reply_to_id: UUID
    clarification: Literal["symptom", "item"] | None = None
    citations: list[Citation] = Field(default_factory=list,max_length=3)
    latency_ms: int | None = Field(default=None,ge=0,le=600000)


@router.post("/internal/reception/chats/{channel_id}/replies", status_code=201,
             summary="Store the Reception reply to one resident message")
async def create_reply(channel_id: str, body: ReplyCreate, scope: Scope) -> dict[str, object]:
    db, run = scope
    _own_channel(channel_id, run)
    await _owned_chat((db, run["user_id"]), channel_id, lock=True)
    source = await db.execute(text("""
        select 1 from messages where id=:id and channel_id=:channel and sender_kind='user' and sender_user_id=:actor
    """), {"id": body.reply_to_id, "channel": channel_id, "actor": run["user_id"]})
    if source.first() is None:
        raise HTTPException(422, "reply_to_id must be a resident message in this conversation")
    steps = (await db.execute(text("select resident_progress from delegations where id=:id"),
                              {"id":run['run_id']})).scalar_one()
    experience = {"citations":[c.model_dump(mode='json') for c in body.citations],
                  "steps":steps,"latencyMs":body.latency_ms}
    return await write_reply(db, channel_id, body.text, body.reply_to_id, body.clarification,experience)


@asynccontextmanager
async def _resident_transaction(app, actor_id: str):
    async with app.state.engine.begin() as db:
        await db.execute(text("select set_config('app.tenant_id', :tenant, true), set_config('app.user_id', :user, true)"),
                         {"tenant": str(app.state.settings.tenant_id), "user": actor_id})
        yield db


@asynccontextmanager
async def _one_turn(app, channel_id: str):
    """One Reception turn per conversation at a time, whichever copy of the API sent it and whichever copy of
    Reception runs it: a second message waits here for the reply to the first.

    The lock is PostgreSQL's, held on a connection of its own for the length of the turn: the pool stays free for
    the calls the runtime makes back, and a process that dies lets go of the lock with its connection.
    """
    engine = create_async_engine(app.state.settings.database_url, poolclass=NullPool)
    try:
        async with engine.connect() as held:
            await held.execution_options(isolation_level="AUTOCOMMIT")
            await held.execute(text("select pg_advisory_lock(hashtextextended(:key, 0))"), {"key": "reception-turn:" + channel_id})
            yield
    finally:
        await engine.dispose()


async def dispatch_turn(app, actor_id: str, channel_id: str, message: dict[str, object]) -> None:
    """Run after the resident message is committed; the runtime stores its own reply."""
    settings = app.state.settings
    run_id, delivered, usage = None, False, None
    async with AsyncExitStack() as held:
        try:
            # Before anything else: the turns of one conversation run one after the other.
            await held.enter_async_context(_one_turn(app, channel_id))
            async with _resident_transaction(app, actor_id) as db:
                # A turn that died with the process left its message unanswered for good: the resident is
                # told so now. Four minutes is past any turn still running (the wait below is three).
                lost = await db.execute(text(f"""
                    select m.id from messages m
                    where m.channel_id=:channel and m.tenant_id={TENANT} and m.sender_kind='user' and m.sender_user_id=:actor
                      and m.id<>:current and m.created_at between now()-interval '1 day' and now()-interval '4 minutes'
                      and coalesce(m.body->>'type','')<>'ticket_draft' and not m.body ? 'supervisorResponse'
                      and not exists(select 1 from messages r where r.channel_id=m.channel_id and r.reply_to_id=m.id)
                      and m.seq>coalesce((select max(a.seq) from messages a where a.channel_id=m.channel_id and a.sender_kind='agent'),0)
                    order by m.seq
                """), {"channel": channel_id, "actor": actor_id, "current": UUID(str(message["id"]))})
                for row in lost.all():
                    await write_reply(db, channel_id, UNAVAILABLE_REPLY, row[0])
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
        # Still inside the lock: the next turn of this conversation starts after this one's reply is stored.
        try:
            async with _resident_transaction(app, actor_id) as db:
                if run_id:
                    await finish_run(db, run_id, delivered, usage if isinstance(usage, dict) else None)
                if not delivered:
                    # The resident must not be left without an answer when the runtime is down.
                    await write_reply(db, channel_id, UNAVAILABLE_REPLY, UUID(str(message["id"])))
        except Exception:  # noqa: BLE001 - a failed fallback must not crash the background task
            log.exception("Could not close the Reception run")
