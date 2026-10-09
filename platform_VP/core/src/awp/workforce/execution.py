"""Fence every turn and reserve its model spend before making any provider call."""
import copy
import json
import math
import time
from dataclasses import dataclass
from datetime import UTC

from agentscope.middleware import MiddlewareBase
from agentscope.model import ChatModelBase
from sqlalchemy import func, insert, select, update

from . import schema as s
from .service import Fault, row, uid


@dataclass(frozen=True)
class Fence:
    job_id: str
    owner: str
    generation: int

    async def check(self, service, conn=None):
        if conn is None:
            async with service.rt.db.engine.connect() as connection:
                return await self.check(service, connection)
        job = await row(conn, s.jobs, s.jobs.c.id == self.job_id)
        if not job or (job["owner"], job["generation"], job["status"]) != (
                self.owner, self.generation, "leased") or job["lease_until"] <= time.time():
            raise Fault(409, "STALE_EXECUTION")
        wf = await row(conn, s.workflows, s.workflows.c.id == job["workflow_id"])
        if not wf or wf["state"] == "closed":
            raise Fault(409, "WORKFLOW_CLOSED")
        conv = await row(conn, s.conversations, s.conversations.c.id == wf["conversation_id"])
        client = await row(conn, s.clients, s.clients.c.id == conv["client_id"])
        if client["status"] != "active" or (client["expires"] and client["expires"] <= time.time()):
            raise Fault(403, "CREDENTIAL_REVOKED_OR_EXPIRED")
        await service.binding(conn, client, wf["id"], conv["user_id"])
        return wf


async def current_fence(service, case_id, session_id=None, user_id=None, agent_id=None):
    wf = await service.workflow_of_case(case_id)
    if not wf:
        return None
    async with service.rt.db.engine.connect() as conn:
        epoch = await row(conn, s.session_fences, s.session_fences.c.id == session_id) if session_id else None
    if session_id and not epoch:
        session = await service.rt.storage.get_session(user_id, agent_id, session_id)
        team = await service.rt.storage.get_team(user_id, session.team_id) if session and session.team_id else None
        async with service.tx() as conn:
            parent = await row(conn, s.session_fences, s.session_fences.c.id == team.session_id, lock=True) if team else None
            if not parent:
                raise Fault(409, "SESSION_EXECUTION_NOT_BOUND")
            epoch = {**parent, "id": session_id, "role": "worker"}
            if not await row(conn, s.session_fences, s.session_fences.c.id == session_id):
                await conn.execute(insert(s.session_fences).values(**epoch))
    if epoch:
        fence = Fence(epoch["job_id"], epoch["owner"], epoch["generation"])
        current = await fence.check(service)
        if current["id"] != wf["id"]:
            raise Fault(409, "SESSION_EXECUTION_NOT_BOUND")
        return fence
    async with service.rt.db.engine.connect() as conn:
        job = await row(conn, s.jobs, s.jobs.c.workflow_id == wf["id"],
                        s.jobs.c.kind == "agent", s.jobs.c.status == "leased")
    if not job:
        raise Fault(409, "NO_ACTIVE_REQUEST")
    return Fence(job["id"], job["owner"], job["generation"])


class FenceMiddleware(MiddlewareBase):
    def __init__(self, service, fence):
        self.service, self.fence = service, fence

    async def on_reply(self, agent, input_kwargs, next_handler):
        await self.fence.check(self.service)
        async for event in next_handler(**input_kwargs):
            yield event

    async def on_acting(self, agent, input_kwargs, next_handler):
        await self.fence.check(self.service)
        async for event in next_handler(**input_kwargs):
            yield event


async def reserve(service, fence, tokens, micros):
    async with service.tx() as conn:
        wf = await fence.check(service, conn)
        ceiling = service.rt.settings.workforce_monthly_budget_usd
        if ceiling > 0:
            from datetime import datetime

            from sqlalchemy import text

            from .service import digest
            tenant = wf["snapshot"]["tenant"]
            if conn.dialect.name == "postgresql":
                await conn.execute(text("SELECT pg_advisory_xact_lock(:key)"),
                    {"key": int(digest(["monthly-budget", tenant])[:15], 16)})
            month = datetime.now(UTC).replace(day=1, hour=0, minute=0, second=0, microsecond=0).timestamp()
            spent = (await conn.execute(select(func.coalesce(func.sum(s.reservations.c.micros), 0))
                .join(s.workflows, s.workflows.c.id == s.reservations.c.workflow_id)
                .join(s.conversations, s.conversations.c.id == s.workflows.c.conversation_id)
                .join(s.clients, s.clients.c.id == s.conversations.c.client_id)
                .where(s.clients.c.tenant == tenant, s.reservations.c.created >= month))).scalar_one()
            if spent + micros > int(ceiling * 1_000_000):
                raise Fault(409, "MONTHLY_BUDGET_EXHAUSTED")
        await row(conn, s.workflows, s.workflows.c.id == wf["id"], lock=True)
        totals = (await conn.execute(select(func.coalesce(func.sum(s.reservations.c.micros), 0),
            func.coalesce(func.sum(s.reservations.c.tokens), 0)).where(
                s.reservations.c.workflow_id == wf["id"]))).one()
        if totals[0] + micros > wf["snapshot"]["budget_micros"] or totals[1] + tokens > wf["snapshot"]["budget_tokens"]:
            raise Fault(409, "BUDGET_EXHAUSTED")
        rid = uid()
        await conn.execute(insert(s.reservations).values(id=rid, workflow_id=wf["id"], status="reserved",
            micros=micros, tokens=tokens, created=time.time()))
        return rid


class BudgetModel(ChatModelBase):
    """Use the SDK's normal/structured paths; both reach this guarded _call_api.

    Lost usage keeps the full reservation. A crash never releases an ambiguous charge.
    """
    def __init__(self, service, fence, binding, spec, inner):
        self.service, self.fence, self.binding, self.spec = service, fence, binding, spec
        self.inner = copy.copy(inner)
        provider_client = getattr(inner, "client", None)
        if provider_client is not None and hasattr(provider_client, "with_options"):
            # OpenAI/Anthropic SDK retries happen below ChatModelBase; disable
            # them too so an ambiguous billed attempt keeps one reservation.
            self.inner.client = provider_client.with_options(max_retries=0, timeout=60)
        params = inner.parameters.model_copy(deep=True)
        self.output_limit = params.max_tokens or 2048
        params.max_tokens = self.output_limit
        if getattr(params, "thinking_budget", None) and params.thinking_budget >= self.output_limit:
            raise Fault(422, "THINKING_EXCEEDS_OUTPUT_LIMIT")
        self.inner.parameters = params
        self.formatter = inner.formatter
        super().__init__(inner.credential, inner.model, params, stream=inner.stream,
                         max_retries=0, context_size=inner.context_size)

    def _get_disable_thinking_kwargs(self):
        return self.inner._get_disable_thinking_kwargs()

    async def _call_api(self, model_name, messages, tools=None, tool_choice=None, **kwargs):
        # UTF-8 bytes form a conservative text bound, including non-English text.
        payload = [m.model_dump(mode="json") for m in messages]
        image_count = 0
        for message in payload:
            for block in message.get("content", []) if isinstance(message.get("content"), list) else []:
                if block.get("type") == "data":
                    image_count += 1
                    block["source"] = {"type": "image"}
        serial = json.dumps(payload, ensure_ascii=False)
        input_bound = max(await self.inner.count_tokens(messages, tools),
                          len(serial.encode()) + len(json.dumps(tools or []).encode()) + 512
                          + image_count * self.spec.vision_tokens_per_image)
        tokens = input_bound + self.output_limit
        if not self.spec.priced:
            raise Fault(503, "MODEL_PRICE_NOT_CONFIGURED")
        input_price = max(self.spec.price_in, self.spec.price_cache_read or 0, self.spec.price_cache_write or 0)
        micros = math.ceil(input_bound * input_price + self.output_limit * self.spec.price_out)
        rid = await reserve(self.service, self.fence, tokens, micros)
        result = await self.inner._call_api(model_name=model_name, messages=messages,
            tools=tools, tool_choice=tool_choice, **kwargs)
        if hasattr(result, "__aiter__"):
            return self._stream(result, rid)
        await self.settle(rid, result)
        return result

    async def _stream(self, stream, rid):
        last_usage = None
        async for chunk in stream:
            if getattr(chunk, "usage", None) is not None:
                last_usage = chunk
            yield chunk
        await self.settle(rid, last_usage)

    async def settle(self, rid, response):
        usage = getattr(response, "usage", None)
        if usage is None:
            return
        actual = math.ceil(self.spec.cost(usage.input_tokens, usage.output_tokens,
            usage.cache_input_tokens, usage.cache_creation_input_tokens) * 1_000_000)
        tokens = usage.input_tokens + usage.output_tokens
        if not self.spec.input_includes_cache:
            tokens += usage.cache_input_tokens + usage.cache_creation_input_tokens
        async with self.service.tx() as conn:
            reserved = await row(conn, s.reservations, s.reservations.c.id == rid, lock=True)
            if reserved["status"] == "settled":
                return
            await conn.execute(update(s.reservations).where(s.reservations.c.id == rid).values(
                status="settled", micros=actual, tokens=tokens, actual_micros=actual, actual_tokens=tokens))
            from ..db import ledger
            wf = await row(conn, s.workflows, s.workflows.c.id == reserved["workflow_id"])
            await conn.execute(insert(ledger).values(tenant=wf["snapshot"]["tenant"], case_id=self.binding.case_id,
                session_id=self.binding.session_id, agent_id=self.binding.agent_id, agent_name=self.binding.agent_name,
                model=self.spec.model, tier=self.spec.tier, input_tokens=usage.input_tokens,
                output_tokens=usage.output_tokens, cache_read_tokens=usage.cache_input_tokens,
                cache_write_tokens=usage.cache_creation_input_tokens, cost_usd=actual / 1_000_000, priced=1, created_at=time.time()))
