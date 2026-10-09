"""Shared services every middleware and tool reads from.

One `Runtime` per process. It resolves which case a session belongs to, finds
an agent's profile, delivers messages to a teammate and keeps the live
sub-agent template registry in step with published profiles.
"""
from __future__ import annotations

import json
from dataclasses import dataclass, field
from typing import Any, Awaitable, Callable

from .casefile import CaseStore
from .config import Settings
from .cost import CostService
from .db import Database
from .guard import Rules, SupportJudge
from .profiles import MARKER, AgentProfile, ProfileStore, to_template
from .providers import ModelCatalog


@dataclass
class Binding:
    """Who a running agent is, inside which case."""

    case_id: str
    session_id: str
    agent_id: str
    agent_name: str
    role: str  # leader | worker
    user_id: str


@dataclass
class Runtime:
    settings: Settings
    db: Database
    cases: CaseStore
    profiles: ProfileStore
    catalog: ModelCatalog
    cost: CostService
    storage: Any  # agentscope StorageBase
    bus: Any  # agentscope MessageBus
    judge: SupportJudge | None = None
    rules: Rules = field(default_factory=Rules)  # default for domains without their own
    rules_by_domain: dict[str, Rules] = field(default_factory=dict)
    # The live dict AgentScope reads sub-agent templates from (mutated in place).
    templates: dict = field(default_factory=dict)
    # Domain packs add tools: each factory gets (runtime, binding) -> list[ToolBase].
    tool_factories: list[Callable[["Runtime", Binding], list]] = field(default_factory=list)
    # Cases whose budget is spent: agents may only wrap up.
    wrap_up: set[str] = field(default_factory=set)
    # Counters for ops: what the tool filter saved. Not a billing source.
    metrics: dict = field(default_factory=lambda: {"model_calls": 0, "tool_chars_offered": 0, "tool_chars_sent": 0})
    kb_manager: Any = None  # AgentScope knowledge base manager, when the feature is on
    fail_hook: Callable[[str, str], Awaitable[None]] | None = None
    # (case_id, status, result) -> True when this call closed the case
    close_hook: Callable[[str, str, dict], Awaitable[bool]] | None = None
    # domain -> request kind key -> RequestKind
    request_kinds: dict[str, dict] = field(default_factory=dict)
    template_tenant: dict[str, str] = field(default_factory=dict)
    _profile_cache: dict = field(default_factory=dict)

    # ---- who is this agent? -------------------------------------------
    async def binding(self, user_id: str, agent_id: str, session_id: str) -> Binding | None:
        found = await self.cases.session_binding(session_id)
        if found:
            return Binding(found["case_id"], session_id, agent_id,
                           found["agent_name"], found["role"], user_id)
        session = await self.storage.get_session(user_id, agent_id, session_id)
        if session is None or not session.team_id:
            return None
        team = await self.storage.get_team(user_id, session.team_id)
        if team is None:
            return None
        leader = await self.cases.session_binding(team.session_id)
        if leader is None:
            return None
        agent = await self.storage.get_agent(user_id, agent_id)
        name = agent.data.name if agent else agent_id
        await self.cases.bind_session(leader["case_id"], session_id, agent_id, name, "worker")
        return Binding(leader["case_id"], session_id, agent_id, name, "worker", user_id)

    async def profile_of(self, user_id: str, agent_id: str, tenant: str) -> tuple[AgentProfile | None, int]:
        agent = await self.storage.get_agent(user_id, agent_id)
        if agent is None:
            return None, 0
        m = MARKER.search(agent.data.system_prompt or "")
        if not m:
            return None, 0
        key, version = m.group(1), int(m.group(2))
        cached = self._profile_cache.get((tenant, key, version))
        if cached is None:
            rec = await self.profiles.get(tenant, key, version)
            if rec is None:
                return None, 0
            cached = rec.profile
            self._profile_cache[(tenant, key, version)] = cached
        return cached, version

    def rules_for(self, domain: str) -> Rules:
        return self.rules_by_domain.get(domain, self.rules)

    async def case_rules(self, case_id: str) -> Rules:
        case = await self.cases.get_case(case_id)
        return self.rules_for(case["domain"]) if case else self.rules

    async def leader_name(self, case_id: str) -> str | None:
        for s in await self.cases.sessions_of_case(case_id):
            if s["role"] == "leader":
                return s["agent_name"]
        return None

    # ---- talking to a teammate ----------------------------------------
    async def deliver(self, case_id: str, to_name: str, tag: str, sender: str, text: str) -> bool:
        """Put a message in a teammate's inbox (wakes them if idle)."""
        from agentscope.app._bus_ops import deliver_to_inbox
        from agentscope.message import HintBlock

        target = next((s for s in await self.cases.sessions_of_case(case_id)
                       if s["agent_name"] == to_name), None)
        case = await self.cases.get_case(case_id)
        if target is None or case is None:
            return False
        hint = HintBlock(
            hint=f'<case-message from="{sender}" {tag}>\n{text}\n</case-message>',
            source=json.dumps({"label": "case", "sublabel": sender}, ensure_ascii=False),
        )
        await deliver_to_inbox(
            self.bus, user_id=case["user_id"], session_id=target["session_id"],
            agent_id=target["agent_id"], payload=hint.model_dump(mode="json"))
        return True

    # ---- templates -----------------------------------------------------
    async def sync_templates(self) -> list[str]:
        """Make the live template registry equal the published specialists."""
        published = [r for r in await self.profiles.all_published()
                     if r.profile.role == "specialist"]
        keep = {r.key for r in published}
        for r in published:
            self.templates[r.key] = to_template(r.profile, r.version, self.settings)
            self.template_tenant[r.key] = r.tenant
        for key in [k for k in self.templates if k not in keep and k != "default"]:
            del self.templates[key]
            self.template_tenant.pop(key, None)
        self._profile_cache.clear()
        return sorted(keep)

    async def fail(self, case_id: str, reason: str) -> None:
        if self.fail_hook is not None:
            await self.fail_hook(case_id, reason)

    async def close(self, case_id: str, status: str, result: dict) -> bool:
        """Close an open case with its result. False if it was already closed."""
        assert self.close_hook is not None, "no intake service is attached"
        return await self.close_hook(case_id, status, result)
