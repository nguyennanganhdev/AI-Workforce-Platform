from collections.abc import AsyncIterator
from typing import Protocol

from contracts.runtime import (
    RuntimeCheckpoint,
    RuntimeEvent,
    RuntimePlan,
    RuntimeSessionRef,
    RuntimeStep,
)


class RuntimeAdapter(Protocol):
    """AgentScope 2.0 is the P0 implementation, selected at the composition root.

    Service authentication and tenant/session authorization are mandatory at the
    transport boundary. A session reference alone does not confer permission.
    """

    async def create_session(self, plan: RuntimePlan) -> RuntimeSessionRef: ...

    async def execute_step(self, step: RuntimeStep) -> None: ...

    async def checkpoint(self, session: RuntimeSessionRef) -> RuntimeCheckpoint: ...

    async def resume(self, session: RuntimeSessionRef) -> None: ...

    async def cancel(self, session: RuntimeSessionRef) -> None: ...

    def stream_events(self, session: RuntimeSessionRef) -> AsyncIterator[RuntimeEvent]: ...
