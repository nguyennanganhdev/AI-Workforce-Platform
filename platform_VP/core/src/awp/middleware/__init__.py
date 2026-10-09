"""Factories AgentScope calls each time it assembles an agent."""
from __future__ import annotations

import inspect
import logging
from pathlib import Path

from ..runtime import Runtime
from .room import (DigestMiddleware, EvidenceMiddleware, LeaderWatchdog, LedgerMiddleware,
                   TierMiddleware, ToolGateMiddleware)

log = logging.getLogger("awp")


def middleware_factory(rt: Runtime):
    async def factory(user_id: str, agent_id: str, session_id: str) -> list:
        b = await rt.binding(user_id, agent_id, session_id)
        if b is None:  # not a case session: leave the agent as it is
            return []
        case = await rt.cases.get_case(b.case_id)
        tenant = case["tenant"] if case else ""
        profile, _ = await rt.profile_of(user_id, agent_id, tenant)
        scoped = {}
        wf = await rt.workforce.workflow_of_case(b.case_id) if rt.workforce else None
        if wf:
            from ..workforce.execution import current_fence, FenceMiddleware
            b.fence = await current_fence(rt.workforce, b.case_id, session_id, user_id, agent_id)
        from ..profiles import to_template
        if b.role == "leader":
            records = await rt.profiles.list(tenant, "published")
            if wf:
                records = [await rt.profiles.get(tenant, key, version)
                           for key, version in wf["snapshot"]["profiles"].items()]
            scoped = {rec.key: to_template(rec.profile, rec.version, rt.settings)
                      for rec in records if rec and rec.profile.role == "specialist"}
        gate = ToolGateMiddleware(rt, b, profile, tenant)
        gate.scoped_templates = scoped
        if wf:
            gate.workforce_integrations = set(wf["snapshot"].get("integration_ids", []))
        mws: list = [
            TierMiddleware(rt, b, profile),
            DigestMiddleware(rt, b, profile),
            EvidenceMiddleware(rt, b, profile),
            gate,
            LedgerMiddleware(rt, b, profile, tenant),
            LeaderWatchdog(rt, b, profile),
        ]
        if wf:
            mws.insert(0, FenceMiddleware(rt.workforce, b.fence))
        if profile is not None:
            if not wf:
                mws.extend(await knowledge_middlewares(rt, user_id, profile))
            if not wf:
                mws.extend(memory_middlewares(rt, tenant, profile, b))
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


def memory_middlewares(rt: Runtime, tenant: str, profile, binding=None) -> list:
    """Private runtime memory; reviewed reusable knowledge is attached separately."""
    if not profile.memory.enabled:
        return []
    from agentscope.middleware import AgenticMemoryMiddleware

    import hashlib
    # Runtime cases are private by default; reusable team knowledge belongs in reviewed KBs.
    scope = binding.case_id if binding is not None else "unbound"
    parts = [hashlib.sha256(str(x).encode()).hexdigest()[:24] for x in (tenant, profile.key, scope)]
    path = Path(rt.settings.workspace_dir) / "memory" / Path(*parts)
    path.mkdir(parents=True, exist_ok=True)
    return [AgenticMemoryMiddleware(workdir=str(path))]


def tool_factory(rt: Runtime):
    from ..protocol.calc import calc_sum
    from ..protocol.tools import CASE_TOOLS, CaseRequest

    async def factory(user_id: str, agent_id: str, session_id: str) -> list:
        b = await rt.binding(user_id, agent_id, session_id)
        if b is None:
            return []
        if rt.workforce is not None and await rt.workforce.workflow_of_case(b.case_id):
            from ..workforce.execution import current_fence
            b.fence = await current_fence(rt.workforce, b.case_id, session_id, user_id, agent_id)
        tools = [cls(rt, b) for cls in CASE_TOOLS] + [calc_sum()]
        case = await rt.cases.get_case(b.case_id)
        kinds = rt.request_kinds.get(case["domain"], {}) if case else {}
        if kinds:
            tools.append(CaseRequest(rt, b, kinds))
        for make in rt.tool_factories:
            extra = make(rt, b)
            tools.extend(await extra if inspect.isawaitable(extra) else extra)
        if rt.workforce is not None and await rt.workforce.workflow_of_case(b.case_id):
            from ..workforce.tools import CaseSay
            from ..workforce.mcp import tools_for_case
            tools.append(CaseSay(rt, b))
            tools.extend(await tools_for_case(rt.workforce, b))
            from ..workforce.knowledge import SearchKnowledge
            tools.append(SearchKnowledge(rt.workforce, b))
            from ..workforce.memory import MemoryRecall, MemoryRemember
            tools.extend([MemoryRecall(rt.workforce, b), MemoryRemember(rt.workforce, b)])
        return tools

    return factory


__all__ = ["middleware_factory", "tool_factory", "DigestMiddleware", "EvidenceMiddleware",
           "LedgerMiddleware", "LeaderWatchdog", "TierMiddleware", "ToolGateMiddleware"]
