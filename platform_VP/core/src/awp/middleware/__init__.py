"""Factories AgentScope calls each time it assembles an agent."""
from __future__ import annotations

import inspect
import logging
from pathlib import Path

from ..evals.sandbox import Trace, only_fixtures, pin_of
from ..profiles import tool_patterns
from ..profiles.compile import LEADER_TOOLS, WORKER_TOOLS
from ..runtime import Runtime
from ..workforce.lookup import workflow_of_case
from ..workforce.partner_tools import partner_tools
from ..workforce.turns import TurnRecorder
from ..workforce.uploads import can_attach
from ..workforce.watch import WorkerWatch
from .room import (DigestMiddleware, EvidenceMiddleware, LedgerMiddleware, TierMiddleware,
                   ToolGateMiddleware)

log = logging.getLogger("awp")


def middleware_factory(rt: Runtime):
    async def factory(user_id: str, agent_id: str, session_id: str) -> list:
        b = await rt.binding(user_id, agent_id, session_id)
        if b is None:  # not a case session: leave the agent as it is
            return []
        case = await rt.cases.get_case(b.case_id)
        tenant = case["tenant"] if case else ""
        profile, _ = await rt.profile_of(user_id, agent_id, tenant, case)
        # Every case belongs to a workflow. Its leader is recorded turn by turn and settled by the engine; a
        # specialist that stops without reporting is noticed by WorkerWatch.
        case_wf = await workflow_of_case(rt.db, b.case_id)
        if case_wf is None:
            return []  # not a workflow's case: leave the agent as it is
        wf = case_wf if b.role == "leader" else None
        pin = pin_of(case)
        mws: list = [
            TierMiddleware(rt, b, profile),
            DigestMiddleware(rt, b, profile, workflow_id=wf["id"] if wf else None),
            EvidenceMiddleware(rt, b, profile),
            ToolGateMiddleware(rt, b, profile, tenant, draft=pin["type"] if pin and pin["role"] == "specialist" else None),
            LedgerMiddleware(rt, b, profile, tenant),
        ]
        if wf:
            mws.insert(0, TurnRecorder(rt, wf["id"]))  # outermost: sees the run as AgentScope emits it
        else:
            mws.insert(0, WorkerWatch(rt, b))  # a specialist that stops without reporting ends the wait
        if pin is not None:
            mws.append(Trace(rt, b))  # an evaluation reads what its agents called
        if profile is not None:
            mws.extend(await knowledge_middlewares(rt, user_id, profile))
            mws.extend(memory_middlewares(rt, tenant, profile, case_wf["id"]))
        return mws

    return factory


async def knowledge_middlewares(rt: Runtime, user_id: str, profile) -> list:
    """Retrieval over the knowledge bases the platform user attached to the profile."""
    ids = profile.knowledge.knowledge_base_ids
    if not ids or rt.kb_manager is None:
        return []
    from agentscope.middleware import RAGMiddleware

    handles = []
    for kb_id in ids:
        try:
            handles.append(await rt.kb_manager.get_knowledge(user_id, kb_id))
        except Exception:  # a deleted or unreachable base must not stop the case
            log.exception("knowledge base %s skipped for profile %s", kb_id, profile.key)
    if not handles:
        return []
    return [RAGMiddleware(knowledge_bases=handles, parameters=RAGMiddleware.Parameters())]


def memory_middlewares(rt: Runtime, tenant: str, profile, workflow_id: str) -> list:
    """Private long-term memory. A workflow serves one resident of a partner, so its notes live in a folder of
    its own (tenant, profile, workflow): what one resident said never reaches another."""
    if not profile.memory.enabled:
        return []
    from agentscope.middleware import AgenticMemoryMiddleware

    path = Path(rt.settings.workspace_dir) / "memory" / tenant / profile.key / workflow_id
    path.mkdir(parents=True, exist_ok=True)
    return [AgenticMemoryMiddleware(workdir=str(path))]


def tool_factory(rt: Runtime):
    from ..protocol.assetlink import CaseAssetLink
    from ..protocol.calc import calc_sum
    from ..protocol.consent import CaseAskConsent
    from ..protocol.say import CaseSay
    from ..protocol.tools import CASE_TOOLS

    async def factory(user_id: str, agent_id: str, session_id: str) -> list:
        b = await rt.binding(user_id, agent_id, session_id)
        if b is None:
            return []
        wf = await workflow_of_case(rt.db, b.case_id)
        if wf is None:
            return []
        tools = [cls(rt, b) for cls in CASE_TOOLS] + [calc_sum()]
        if b.role == "leader":
            tools += [CaseSay(rt, b), CaseAskConsent(rt, b)]
            if getattr(rt, "assets", None) is not None and await can_attach(rt.db, wf["client_id"]):
                tools.append(CaseAssetLink(rt, b))  # images (spec A3): only where the client may send any
        for make in rt.tool_factories:
            extra = make(rt, b)
            tools.extend(await extra if inspect.isawaitable(extra) else extra)
        tools = only_fixtures(tools)
        # the route's partner tools, to every agent of the workflow that its profile lets have them
        case = await rt.cases.get_case(b.case_id)
        profile, _ = await rt.profile_of(user_id, agent_id, case["tenant"] if case else "", case)
        patterns = tool_patterns(profile) if profile is not None else list(
            LEADER_TOOLS if b.role == "leader" else WORKER_TOOLS)
        ours = {getattr(x, "name", None) for x in tools}
        for tool in await partner_tools(rt, wf, patterns):
            if tool.name in ours:  # AgentScope would let the later tool replace ours: the platform's own stays
                log.warning("partner tool %s of route %s has the name of a platform tool and is left out", tool.name, wf["route_id"])
                continue
            tools.append(tool)
        return tools

    return factory


__all__ = ["middleware_factory", "tool_factory", "DigestMiddleware", "EvidenceMiddleware",
           "LedgerMiddleware", "TierMiddleware", "ToolGateMiddleware"]
