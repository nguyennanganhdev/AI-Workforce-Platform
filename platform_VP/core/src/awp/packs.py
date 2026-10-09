"""What a domain pack gives the core. The core never imports a pack by name."""
from __future__ import annotations

import inspect
from typing import Protocol

from .guard import Rules
from .intake.models import CaseResult
from .intake.service import IntakeService
from .profiles import AgentProfile
from .runtime import Binding, Runtime


class DomainPack(Protocol):
    domain: str
    default_leader: str  # key of the leader profile used when a case names none

    def profiles(self) -> list[AgentProfile]: ...

    def rules(self) -> Rules: ...

    def tools(self, rt: Runtime, binding: Binding) -> list: ...

    async def deliver_result(self, case: dict, result: CaseResult) -> None:
        """Send a finished case back to the domain. Raise to have it retried."""

    async def start(self, rt: Runtime, intake: IntakeService, tenant: str) -> None:
        """Begin any connector (for example polling the domain's inbox)."""

    async def stop(self) -> None: ...


async def install_pack(rt: Runtime, intake: IntakeService, pack: DomainPack, tenant: str) -> None:
    """Seed the pack's profiles, add its rules and tools, start its connector."""
    for profile in pack.profiles():
        if await rt.profiles.get_published(tenant, profile.key) is None:
            rec = await rt.profiles.create_draft(tenant, profile)
            await rt.profiles.publish(tenant, profile.key, rec.version)
    await rt.sync_templates()
    rt.rules_by_domain[pack.domain] = pack.rules()
    intake.default_leader[pack.domain] = pack.default_leader
    intake.deliverers[pack.domain] = pack.deliver_result

    async def make_tools(runtime: Runtime, binding: Binding) -> list:
        case = await runtime.cases.get_case(binding.case_id)
        if case is None or case["domain"] != pack.domain:
            return []
        result = pack.tools(runtime, binding)
        return await result if inspect.isawaitable(result) else result

    rt.tool_factories.append(make_tools)
    await pack.start(rt, intake, tenant)
