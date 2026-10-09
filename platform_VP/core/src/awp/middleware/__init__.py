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
        mws: list = [
            TierMiddleware(rt, b, profile),
            DigestMiddleware(rt, b, profile),
            EvidenceMiddleware(rt, b, profile),
            ToolGateMiddleware(rt, b, profile, tenant),
            LedgerMiddleware(rt, b, profile, tenant),
            LeaderWatchdog(rt, b, profile),
        ]
        if profile is not None:
            mws.extend(await knowledge_middlewares(rt, user_id, profile))
            mws.extend(memory_middlewares(rt, tenant, profile))
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


def memory_middlewares(rt: Runtime, tenant: str, profile) -> list:
    """Private long-term memory: one folder per tenant and profile, kept across cases."""
    if not profile.memory.enabled:
        return []
    from agentscope.middleware import AgenticMemoryMiddleware

    path = Path(rt.settings.workspace_dir) / "memory" / tenant / profile.key
    path.mkdir(parents=True, exist_ok=True)
    return [AgenticMemoryMiddleware(workdir=str(path))]


def tool_factory(rt: Runtime):
    from ..protocol.tools import CASE_TOOLS

    async def factory(user_id: str, agent_id: str, session_id: str) -> list:
        b = await rt.binding(user_id, agent_id, session_id)
        if b is None:
            return []
        tools = [cls(rt, b) for cls in CASE_TOOLS]
        for make in rt.tool_factories:
            extra = make(rt, b)
            tools.extend(await extra if inspect.isawaitable(extra) else extra)
        return tools

    return factory


__all__ = ["middleware_factory", "tool_factory", "DigestMiddleware", "EvidenceMiddleware",
           "LedgerMiddleware", "LeaderWatchdog", "TierMiddleware", "ToolGateMiddleware"]
