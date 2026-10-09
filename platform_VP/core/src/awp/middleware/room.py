"""Agent middlewares that put an agent inside a case.

Five small hooks, each doing one job:
  TierMiddleware      run the agent on the model tier its profile asks for
  DigestMiddleware    tell the agent what the others did since it last looked
  EvidenceMiddleware  give every tool result an evidence id; keep reports honest
  ToolGateMiddleware  show and allow only the tools the profile grants
  LedgerMiddleware    record the cost of every model call
"""
from __future__ import annotations

import copy
import fnmatch
import json
import logging
from typing import Any, AsyncGenerator

from agentscope.event import HintBlockEvent, ReplyEndEvent
from agentscope.message import AssistantMsg, HintBlock, TextBlock, ToolResultState
from agentscope.middleware import MiddlewareBase
from agentscope.permission import PermissionBehavior, PermissionDecision
from agentscope.tool import ToolResponse
from agentscope.types import ReplyFinishedReason

from ..casefile import build_view, render_digest
from ..profiles import WRAP_UP_TOOLS, AgentProfile, tool_patterns
from ..profiles.compile import LEADER_TOOLS, WORKER_TOOLS
from ..runtime import Binding, Runtime

log = logging.getLogger("awp")

_BUDGET_HINT = (
    "<system-reminder>The budget for this case is spent. Wrap up now: report what you have "
    "and what you could not verify. The leader finishes with CaseFinalize "
    "(outcome needs_human if anything is unverified).</system-reminder>")


def _inject(agent: Any, hint: str, label: str) -> HintBlock:
    block = HintBlock(hint=hint, source=json.dumps({"label": label}, ensure_ascii=False))
    ctx = agent.state.context
    if ctx and ctx[-1].role == "assistant" and ctx[-1].name == agent.name:
        ctx[-1].content.append(block)
    else:
        ctx.append(AssistantMsg(id=agent.state.reply_id, name=agent.name, content=[block]))
    return block


def _tool_name(schema: dict) -> str:
    return (schema.get("function") or {}).get("name") or schema.get("name", "")


class _Base(MiddlewareBase):
    def __init__(self, rt: Runtime, b: Binding, profile: AgentProfile | None) -> None:
        self.rt, self.b, self.profile = rt, b, profile


class TierMiddleware(_Base):
    async def on_reply(self, agent, input_kwargs, next_handler) -> AsyncGenerator:
        spec = self.rt.catalog.pick(self.profile.model_tier) if self.profile else None
        original = agent.model
        if spec is not None:
            try:
                agent.model = self.rt.catalog.build(spec)
            except Exception:  # missing SDK or bad config: keep the session's model
                log.exception("cannot build model %s; using the session model", spec.id)
        try:
            async for event in next_handler(**input_kwargs):
                yield event
        finally:
            agent.model = original


class DigestMiddleware(_Base):
    def __init__(self, *a: Any, **kw: Any) -> None:
        super().__init__(*a, **kw)
        self._budget_told = False

    async def on_reasoning(self, agent, input_kwargs, next_handler) -> AsyncGenerator:
        blocks = []
        if self.b.case_id in self.rt.wrap_up and not self._budget_told:
            self._budget_told = True
            blocks.append(_inject(agent, _BUDGET_HINT, "budget"))
        text = await self._digest()
        if text:
            blocks.append(_inject(agent, text, "room"))
        for block in blocks:
            yield HintBlockEvent(reply_id=agent.state.reply_id, block_id=block.id,
                                 source=block.source, hint=block.hint)
        async for event in next_handler(**input_kwargs):
            yield event

    async def _digest(self) -> str:
        cases = self.rt.cases
        key = f"{self.b.session_id}"
        cursor = await cases.get_cursor(self.b.case_id, key)
        items = await cases.items(self.b.case_id)
        if not items or items[-1].id <= cursor:
            return ""
        case = await cases.get_case(self.b.case_id)
        text = render_digest(
            case_id=self.b.case_id,
            summary=(case or {}).get("intake", {}).get("summary", ""),
            viewer=self.b.agent_name, role=self.b.role, view=build_view(items),
            new_items=[i for i in items if i.id > cursor],
            members=await cases.sessions_of_case(self.b.case_id),
            max_chars=self.rt.settings.digest_max_chars,
            max_rounds=self.rt.settings.max_challenge_rounds)
        await cases.set_cursor(self.b.case_id, key, items[-1].id)
        return text


class EvidenceMiddleware(_Base):
    async def on_acting(self, agent, input_kwargs, next_handler) -> AsyncGenerator:
        call = input_kwargs["tool_call"]
        name = call.name
        if name.startswith("Case") or name in ("TeamCreate", "AgentCreate", "AgentInvite", "TeamDelete"):
            async for item in next_handler(**input_kwargs):
                yield item
            return
        report_text = None
        if name == "TeamSay":
            case = await self.rt.cases.get_case(self.b.case_id)
            if self.b.role == "worker" and case and case["status"] != "open":
                # Late report on a closed case: accept it without waking the leader.
                yield ToolResponse(content=[TextBlock(text="The case is closed; no report is needed.")],
                                   state=ToolResultState.SUCCESS)
                return
            args = self._args(call)
            if self.b.role == "worker":
                leader = await self.rt.leader_name(self.b.case_id)
                # Broadcasts wake every member; reports go to the leader only.
                if leader and args.get("to") is None:
                    call = call.model_copy(update={"input": json.dumps(
                        {**args, "to": leader}, ensure_ascii=False)})
                    input_kwargs = {**input_kwargs, "tool_call": call}
                    args = {**args, "to": leader}
                if args.get("to") == leader:
                    report_text = str(args.get("content", ""))
        async for item in next_handler(**input_kwargs):
            if isinstance(item, ToolResponse) and item.state == ToolResultState.SUCCESS:
                if report_text is not None:
                    await self.rt.cases.add(self.b.case_id, "report", self.b.agent_name,
                                            {"summary": report_text[:800]})
                elif name != "TeamSay":
                    text = "\n".join(b.text for b in item.content if isinstance(b, TextBlock))
                    ev = await self.rt.cases.add(
                        self.b.case_id, "evidence", self.b.agent_name,
                        {"tool": name, "input": call.input[:300], "text": text[:20000]})
                    item.content.append(TextBlock(text=f"[evidence {ev.ref}]"))
            yield item

    @staticmethod
    def _args(call: Any) -> dict:
        try:
            value = json.loads(call.input or "{}")
            return value if isinstance(value, dict) else {}
        except ValueError:
            return {}


class ToolGateMiddleware(_Base):
    # Tools of the platform itself: allowed without asking anyone. Every other
    # tool the profile grants still goes through AgentScope's permission engine.
    OWN_TOOLS = ("Case", "Team", "AgentCreate", "AgentInvite")

    def __init__(self, rt: Runtime, b: Binding, profile: AgentProfile | None, tenant: str = "") -> None:
        super().__init__(rt, b, profile)
        self.tenant = tenant

    def _patterns(self) -> list[str]:
        if self.b.case_id in self.rt.wrap_up:
            return list(WRAP_UP_TOOLS)
        if self.profile is not None:
            return tool_patterns(self.profile)
        return list(LEADER_TOOLS if self.b.role == "leader" else WORKER_TOOLS)

    def allowed(self, name: str) -> bool:
        return any(fnmatch.fnmatchcase(name, p) for p in self._patterns())

    def creatable(self) -> list[str]:
        """Specialist types this leader may create: its own team, else its tenant's."""
        mine = {k for k, t in self.rt.template_tenant.items() if t == self.tenant}
        if self.profile is not None and self.profile.team:
            return [k for k in self.profile.team if k in mine]
        return sorted(mine)

    def _narrow_agent_create(self, schema: dict) -> dict:
        schema = copy.deepcopy(schema)
        prop = schema["function"]["parameters"]["properties"].get("subagent_type")
        if prop is not None:
            allowed = self.creatable()
            prop["enum"] = allowed
            # AgentScope lists every template in the description; show only ours.
            lines = [f"- ``{k!r}`` - {self.rt.templates[k].description}"
                     for k in allowed if k in self.rt.templates]
            prop["description"] = ("The type of sub-agent to create. Available types:"
                                   + "\n\n" + "\n".join(lines))
        return schema

    async def on_model_call(self, agent, input_kwargs, next_handler):
        tools = []
        offered = input_kwargs.get("tools") or []
        for schema in offered:
            name = _tool_name(schema)
            if not self.allowed(name):
                continue
            tools.append(self._narrow_agent_create(schema) if name == "AgentCreate" else schema)
        m = self.rt.metrics
        m["model_calls"] += 1
        m["tool_chars_offered"] += len(json.dumps(offered))
        m["tool_chars_sent"] += len(json.dumps(tools))
        return await next_handler(**{**input_kwargs, "tools": tools})

    async def on_check_permission(self, agent, input_kwargs, next_handler):
        name = input_kwargs["tool_call"].name
        if not self.allowed(name):
            return PermissionDecision(behavior=PermissionBehavior.DENY,
                                      message=f"{name} is not available to you in this case")
        if name == "AgentCreate":
            wanted = (input_kwargs.get("tool_input") or {}).get("subagent_type", "default")
            if wanted not in self.creatable():
                return PermissionDecision(
                    behavior=PermissionBehavior.DENY,
                    message=f"you cannot create {wanted!r}; choose one of {self.creatable()}")
        if name.startswith(self.OWN_TOOLS):
            return PermissionDecision(behavior=PermissionBehavior.ALLOW,
                                      message=f"{name} is granted by the profile")
        return await next_handler(**input_kwargs)


class LedgerMiddleware(_Base):
    def __init__(self, rt: Runtime, b: Binding, profile: AgentProfile | None, tenant: str) -> None:
        super().__init__(rt, b, profile)
        self.tenant = tenant

    async def on_model_call(self, agent, input_kwargs, next_handler):
        model = input_kwargs.get("current_model")
        result = await next_handler(**input_kwargs)
        if isinstance(result, AsyncGenerator):
            return self._tee(result, model)
        await self._record(result, model)
        return result

    async def _tee(self, gen: AsyncGenerator, model: Any) -> AsyncGenerator:
        usage_chunk = None
        async for chunk in gen:
            if getattr(chunk, "usage", None) is not None:
                usage_chunk = chunk
            yield chunk
        await self._record(usage_chunk, model)

    async def _record(self, response: Any, model: Any) -> None:
        usage = getattr(response, "usage", None)
        if usage is None:
            return
        await self.rt.cost.record(
            tenant=self.tenant, case_id=self.b.case_id, session_id=self.b.session_id,
            agent_id=self.b.agent_id, agent_name=self.b.agent_name,
            model=getattr(model, "model", "unknown"),
            input_tokens=usage.input_tokens, output_tokens=usage.output_tokens,
            cache_read=usage.cache_input_tokens, cache_write=usage.cache_creation_input_tokens)
        await self._check_budget()

    async def _check_budget(self) -> None:
        case = await self.rt.cases.get_case(self.b.case_id)
        if case is None:
            return
        totals = await self.rt.cost.case_totals(self.b.case_id)
        usd, toks = case["budget_usd"], case["budget_tokens"]
        spent_tokens = totals["input_tokens"] + totals["output_tokens"]
        if (usd and totals["cost_usd"] >= usd) or (toks and spent_tokens >= toks):
            self.rt.wrap_up.add(self.b.case_id)


class LeaderWatchdog(_Base):
    """A leader that stops without finalizing is nudged twice, then the case fails."""

    MAX_NUDGES = 2

    async def on_reply(self, agent, input_kwargs, next_handler) -> AsyncGenerator:
        end = None
        async for event in next_handler(**input_kwargs):
            if isinstance(event, ReplyEndEvent):
                end = event
            yield event
        if end is not None and self.b.role == "leader":
            await self._after(end)

    async def _after(self, end: ReplyEndEvent) -> None:
        cases, cid = self.rt.cases, self.b.case_id
        case = await cases.get_case(cid)
        if case is None or case["status"] != "open":
            return
        if end.finished_reason == ReplyFinishedReason.ERROR:
            await self.rt.fail(cid, "the leader stopped with an error")
            return
        view = build_view(await cases.items(cid))
        workers = [s for s in await cases.sessions_of_case(cid) if s["role"] == "worker"]
        waiting = [w for w in workers if w["agent_name"] not in view.reports]
        if waiting or view.open_questions() or view.open_challenges():
            return  # members are still working; their report wakes the leader
        nudges = sum(1 for n in await cases.items(cid, kinds=("note",))
                     if n.data.get("type") == "nudge")
        if nudges >= self.MAX_NUDGES:
            await self.rt.fail(cid, "the leader did not finalize the case")
            return
        await cases.add(cid, "note", "platform", {"type": "nudge"})
        await self.rt.deliver(
            cid, self.b.agent_name, 'ref="nudge"', "platform",
            "The case is not finalized. Call CaseFinalize now (outcome needs_human if anything is unverified).")
