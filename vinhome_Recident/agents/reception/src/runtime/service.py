"""HTTP service that runs one Reception turn per resident message.

Run from agents/reception/:  python -m uvicorn src.runtime.service:create_app --factory --port 4202
The backend posts each committed resident message here; the reply is stored through the
backend, so the resident app only ever reads the conversation from the backend.
"""

from __future__ import annotations

import asyncio
import hmac
import logging
import os
import time
import uuid
from contextlib import asynccontextmanager
from dataclasses import dataclass, field

import httpx
from fastapi import FastAPI, HTTPException, Request
from pydantic import BaseModel, ConfigDict, Field

from ..graph import (
    GraphDependencies,
    WorkflowOptions,
    create_reception_workflow_factory,
)
from ..persistence import open_sqlite_checkpointer
from .backend import BackendClient, BackendOperations, DraftStore, OperationRejected, OperationUnknown, RequestPolicy
from .knowledge import KnowledgeSearch
from .model import ChatCompletionsModel, ModelConfig, model_endpoint, turn_usage, turn_model_config
from ..agent.loop import EMERGENCY_FAILED_REPLY, FILED_REPLY
from ..agent.loop import EMERGENCY_REPLY as AGENT_EMERGENCY_REPLY
from ..agent.loop import run_agent
from ..agent.prompt import system_prompt
from ..agent.tools import Toolbox
from .curator import judge
from .inquiry import to_management, unanswered
from .voice import reword

log = logging.getLogger("reception.runtime")
FAILED_REPLY = "Xin lỗi, tôi chưa xử lý được tin nhắn này. Bạn thử lại sau ít phút hoặc gửi phản ánh bằng biểu mẫu nhé."
# Said only when this turn filed the request under the backend's emergency policy.
EMERGENCY_REPLY = "Mình đã chuyển yêu cầu của bạn đến Ban quản lý ở mức khẩn cấp."
EMPTY_REPLY = "Tôi đã ghi nhận tin nhắn của bạn."
ANSWER_DELIVERED_REPLY = "Mình đã chuyển câu trả lời của bạn tới Ban quản lý."
STALE_REPLY = "Cuộc trò chuyện này không tiếp tục được nữa. Bạn bấm “Chat mới” để mình hỗ trợ tiếp nhé."
# Below the backend's own wait for a turn (180 s): past that it has already told the resident and closed the run.
TURN_SECONDS = 150


def safety_line(policy: dict) -> str:
    """What management approved telling the resident to do meanwhile, word for word; empty until approved."""
    guide = policy.get("safety_guidance")
    approved = isinstance(guide, dict) and guide.get("approved") is True and isinstance(guide.get("answer"), str)
    return "\n" + guide["answer"].strip() if approved and guide["answer"].strip() else ""


@dataclass(frozen=True)
class Settings:
    backend_url: str
    service_token: str = field(repr=False)
    state_path: str
    model: ModelConfig
    knowledge_url: str | None = None
    # "graph": the fixed workflow (src/graph). "loop": the model-led agent (src/agent).
    agent: str = "graph"

    @classmethod
    def from_env(cls) -> Settings:
        token = os.getenv("RECEPTION_SERVICE_TOKEN", "").strip()
        backend = os.getenv("RECEPTION_BACKEND_URL", "").strip()
        if len(token) < 32 or not backend.startswith(("http://", "https://")):
            raise ValueError("RECEPTION_SERVICE_TOKEN (32+ characters) and RECEPTION_BACKEND_URL are required")
        provider, base_url, api_key = model_endpoint("RECEPTION")
        return cls(
            backend_url=backend,
            service_token=token,
            state_path=os.getenv("RECEPTION_STATE_PATH", ".reception-state/reception.sqlite3"),
            knowledge_url=os.getenv("RECEPTION_KNOWLEDGE_URL", "").strip() or None,
            agent="loop" if os.getenv("RECEPTION_AGENT", "").strip() == "loop" else "graph",
            model=ModelConfig(
                model=os.getenv("RECEPTION_MODEL", "").strip(),
                api_key=api_key,
                base_url=base_url,
                provider=provider,
            ),
        )


class TurnMessage(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: str = Field(min_length=1, max_length=200)
    text: str = Field(max_length=16384)
    fileIds: list[str] = Field(default_factory=list, max_length=20)


class DelegationContext(BaseModel):
    model_config = ConfigDict(extra="forbid")

    tenantId: str = Field(min_length=1, max_length=200)
    runId: str = Field(min_length=1, max_length=200)
    bindingId: str = Field(min_length=1, max_length=200)
    principalId: str = Field(min_length=1, max_length=200)


class Delegation(BaseModel):
    """Issued by the backend for this turn only; it expires and dies with the run."""

    model_config = ConfigDict(extra="forbid")

    token: str = Field(min_length=1, max_length=4096, repr=False)
    expiresAt: int
    context: DelegationContext


class Curation(BaseModel):
    model_config = ConfigDict(extra="forbid")

    question: str = Field(min_length=1, max_length=4000)
    answer: str = Field(min_length=1, max_length=4000)


class Turn(BaseModel):
    model_config = ConfigDict(extra="forbid")

    user_id: str = Field(min_length=1, max_length=200)
    channel_id: str = Field(min_length=1, max_length=200)
    message: TurnMessage
    delegation: Delegation


def turn_context(turn: Turn) -> dict:
    """Identity comes from the backend that authenticated the resident, never from the model."""
    bound = turn.delegation.context
    return {
        "tenantId": bound.tenantId,
        "principalId": bound.principalId,
        "initiatedBy": turn.user_id,
        "bindingId": bound.bindingId,
        "checkpoint": {"namespace": "reception", "threadId": turn.channel_id},
        "runId": bound.runId,
        "requestId": turn.message.id,
        "permissions": [],
        "channelId": turn.channel_id,
    }


async def run_turn(graph, context: dict, message: dict) -> dict:
    """Start or resume the conversation's graph with one resident message."""
    snapshot, data, waits = await graph._snapshot(context)
    if data and (data.get("pending") or snapshot.next) and not waits:
        # A previous turn stopped mid-operation; settle it with the same idempotency key first.
        await graph.recover({"context": context})
        snapshot, data, waits = await graph._snapshot(context)
    if waits and data.get("pending"):
        ticket = data.get("ticket") or {}
        await graph.resume({"context": context, "interruptId": waits[0].id, "source": {"kind": "backend", "event": {
            "eventId": "reconcile:" + str(uuid.uuid4()), "aggregateVersion": ticket.get("aggregate_version", 0),
            "generation": ticket.get("ticket_generation", 0), "bindingId": context["bindingId"],
            "interruptId": waits[0].id, "ticketId": ticket.get("ticket_id")}}})
        snapshot, data, waits = await graph._snapshot(context)
    if waits:
        return await graph.resume({"context": context, "interruptId": waits[0].id, "operationId": message["id"],
                                   "source": {"kind": "resident", "message": message}})
    return await graph.run({"context": context, "message": message, "operationId": message["id"]})


async def agent_turn(backend: BackendClient, client: httpx.AsyncClient, model, knowledge_url: str | None,
                     context: dict, message: dict) -> tuple[str, str | None]:
    """One turn of the model-led agent. Returns the reply and, when it is a question of the intake rules, the detail asked for."""
    channel = context["channelId"]
    turn = await backend.call("GET", f"/internal/reception/chats/{channel}/context?message_id={message['id']}", context)
    resident = await backend.execute(context, "get_verified_resident_context", {}, "agent-context:" + message["id"])
    categories = (await backend.call("GET", "/internal/reception/catalog", context))["categories"]
    policy = await backend.call("POST", "/internal/reception/policy/evaluate", context,
                                {"message_text": message["text"], "assessment": None})
    toolbox = Toolbox(backend, client, knowledge_url, context, message, turn["open_request"],
                      {"homes": resident["residences"]}, categories)
    if policy.get("emergency") is True:
        # The policy's keywords decide before any model runs.
        outcome = await toolbox.emergency_request()
        return (AGENT_EMERGENCY_REPLY + safety_line(policy) if "error" not in outcome else EMERGENCY_FAILED_REPLY), None
    added = None
    request = turn["open_request"]
    if request and (message.get("fileIds") or request.get("pending") == "information"):
        # Photos and an awaited answer go to the open request as the resident sent them; the model words only the reply.
        try:
            added = await backend.call("POST", f"/internal/reception/chats/{channel}/follow-up", context,
                                       {"message_id": message["id"]})
        except (OperationRejected, OperationUnknown):
            log.warning("follow-up of a resident message was not stored")
        if added and added.get("delivered") is True:
            # The backend passed this message on as the awaited answer. That is what the resident is told:
            # a model reading the same words as "another incident" would deny what just happened.
            return ANSWER_DELIVERED_REPLY, None
    try:
        reply = await run_agent(model, toolbox, system_prompt(
            resident["resident"], resident["residences"], request, categories,
            turn.get("past_requests", []), added), turn["history"])
    except Exception:
        if not toolbox.filed_code:
            raise
        # The request exists: the resident is told so, whatever went wrong with the wording.
        log.exception("turn failed after the request was filed")
        reply = FILED_REPLY
    return reply, toolbox.clarification if reply == toolbox.question else None


def create_app(settings: Settings | None = None, model=None) -> FastAPI:
    settings = settings or Settings.from_env()
    locks: dict[str, asyncio.Lock] = {}

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        async with httpx.AsyncClient() as client, open_sqlite_checkpointer(settings.state_path) as checkpointer:
            store = await DraftStore.open(settings.state_path + ".records")
            try:
                backend = BackendClient(settings.backend_url, client)
                chat_model = model or ChatCompletionsModel(settings.model, client)
                tools = BackendOperations(backend, store, chat_model)

                async def resolve_session(context, signal):
                    return {"channel_id": context["channelId"], "reception_session_id": context["bindingId"]}

                app.state.backend, app.state.tools, app.state.model = backend, tools, chat_model
                app.state.client = client
                app.state.graph = create_reception_workflow_factory(WorkflowOptions(
                    intake=KnowledgeSearch(settings.knowledge_url, backend, client, chat_model),
                    resolve_session=resolve_session, reconcile=tools.invoke,
                    request_policy=RequestPolicy(backend), timeout_ms=60000,
                )).create(GraphDependencies(model=chat_model, tools=tools, checkpointer=checkpointer))
                yield
            finally:
                await store.close()

    app = FastAPI(title="Reception runtime", lifespan=lifespan)

    @app.get("/health")
    async def health() -> dict[str, str]:
        # Which model answers residents, for the administrator's screen. Never the key or the address.
        return {"status": "ok", "model": settings.model.model, "provider": settings.model.provider}

    def backend_only(request: Request) -> None:
        bearer = request.headers.get("authorization", "")
        if not bearer.startswith("Bearer ") or not hmac.compare_digest(bearer[7:].encode(), settings.service_token.encode()):
            raise HTTPException(401, "Invalid service credential")

    @app.post("/v1/curations")
    async def curation(body: Curation, request: Request) -> dict:
        """Is this answer from management knowledge for other residents? The backend decides what to do with it."""
        backend_only(request)
        try:
            return await judge(request.app.state.model, body.question, body.answer)
        except Exception:  # noqa: BLE001 - no verdict: the backend keeps the candidate for a person
            raise HTTPException(502, "Curator unavailable") from None

    @app.post("/v1/turns")
    async def turn(body: Turn, request: Request) -> dict:
        backend_only(request)
        context = turn_context(body)
        started = time.monotonic()
        usage = {"input_tokens": 0, "output_tokens": 0, "model_calls": 0}
        turn_usage.set(usage)

        def measured() -> dict:
            usage["latency_ms"] = int((time.monotonic() - started) * 1000)
            # One line per turn for cost and latency tracking; no message text, no identifiers of the resident.
            log.info("turn agent=%s model_calls=%s input_tokens=%s output_tokens=%s latency_ms=%s", settings.agent,
                     usage["model_calls"], usage["input_tokens"], usage["output_tokens"], usage["latency_ms"])
            return usage
        message = body.message.model_dump(exclude_defaults=True) | {"id": body.message.id, "text": body.message.text}
        # One turn at a time per conversation: the graph state is a single thread.
        async with locks.setdefault(body.channel_id, asyncio.Lock()):
            tools, backend = request.app.state.tools, request.app.state.backend
            tools.handoffs.pop(body.channel_id, None)
            backend.tokens[body.channel_id] = body.delegation.token
            async def configured_model():
                if model is not None:
                    return
                chosen = (await backend.call('GET', '/internal/reception/v1/model-config', context)).get('config')
                turn_model_config.set(ModelConfig(model=chosen['model_name'], api_key=chosen['api_key'],
                    base_url=chosen['base_url'], provider=chosen['provider']) if chosen else None)
            if settings.agent == "loop":
                try:
                    try:
                        await configured_model()
                        reply, asked = await asyncio.wait_for(agent_turn(
                            backend, request.app.state.client, request.app.state.model,
                            settings.knowledge_url, context, message), TURN_SECONDS)
                    except Exception:  # noqa: BLE001 - the resident still gets an answer
                        # Why it failed is the only trace of it: the reply itself says nothing.
                        log.exception("Reception turn failed")
                        reply, asked = FAILED_REPLY, None
                    await backend.call(
                        "POST", f"/internal/reception/chats/{body.channel_id}/replies", context,
                        {"text": reply[:10000], "reply_to_id": body.message.id, **({"clarification": asked} if asked else {})})
                finally:
                    turn_model_config.set(None)
                    backend.tokens.pop(body.channel_id, None)
                return {"status": "completed", "reply": reply, "usage": measured()}
            try:
                clarification = None
                try:
                    await configured_model()
                    result = await run_turn(request.app.state.graph, context, message)
                except Exception as error:  # noqa: BLE001 - the resident still gets an answer
                    log.exception("Reception turn failed")
                    # A conversation kept by an older workflow cannot continue: "try again later" would never be true.
                    result = {"status": "ok", "state": {"reply": STALE_REPLY}} \
                        if getattr(error, "code", None) == "WORKFLOW_MIGRATION_REQUIRED" else {"status": "failed"}
                reply = FAILED_REPLY if result["status"] in ("failed", "cancelled") else result["state"].get("reply") or EMPTY_REPLY
                state = result.get("state") or {}
                ok = result["status"] not in ("failed", "cancelled") and bool(state.get("reply"))
                answered = (state.get("intake") or {}).get("kind") == "answer"
                asked = tools.questions.pop(body.channel_id, None)
                handed_over = None
                if ok and not answered and (state.get("decision") or {}).get("next_action") == "retrieve_knowledge":
                    # No source answers the question: it goes to the management session, or it is out of scope.
                    handed_over = await unanswered(request.app.state.model, backend, context, body.channel_id, message)
                elif state.get("phase") == "review":
                    # "A person will look at this" is only true once a person was told.
                    handed_over = await to_management(backend, context, body.channel_id, message)
                if asked and asked["question"] in reply:
                    # The intake rules' own question goes out as it is: rewording may not add to it or soften it.
                    reply, clarification = asked["question"], asked["field"] if asked["field"] in ("symptom", "item") else "symptom"
                elif handed_over:
                    reply = handed_over
                # Cited answers are already written from their sources, and an emergency
                # must not wait for wording; everything else is reworded for the resident.
                elif ok and not answered and reply != STALE_REPLY and state.get("handoff_reason") != "emergency":
                    reply = await reword(request.app.state.model, body.message.text, reply)
                code = tools.handoffs.pop(body.channel_id, None)
                if code and state.get("handoff_reason") == "emergency":
                    # The graph keeps only guidance its policy check accepted as approved.
                    reply = EMERGENCY_REPLY + ("\n" + state["safety_reply"] if state.get("safety_reply") else "")
                await backend.call(
                    "POST", f"/internal/reception/chats/{body.channel_id}/replies", context,
                    {"text": reply[:10000], "reply_to_id": body.message.id,
                     **({"clarification": clarification} if clarification else {})})
            finally:
                turn_model_config.set(None)
                backend.tokens.pop(body.channel_id, None)
        return {"status": result["status"], "reply": reply, "usage": measured()}

    return app
