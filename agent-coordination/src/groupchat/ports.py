"""Ports require real authorization and atomic persistence in production."""

from contextlib import AbstractAsyncContextManager
from dataclasses import dataclass
from typing import Protocol

from .models import (
    AgentOutput,
    Context,
    ContextItem,
    Message,
    Participant,
    ParticipantSpec,
    ScopeState,
    Snapshot,
    TaskItem,
)


class ParticipantResolver(Protocol):
    async def authorize(
        self, context: Context, operation: str, room: Snapshot | None
    ) -> None:
        """Verify credential/delegation, current generation, scope and history ACL.

        Called before replay/read and again before accepting completion. A plain
        JSON Context is not a credential. Implementation must use gateway evidence.
        put_task is Supervisor-only; put_context accepts trusted backend data only.
        mention_agent checks user delegation, distinct from Supervisor run_turn.
        Public room queries/results require room-wide read permission.
        """
        ...

    async def resolve(
        self,
        context: Context,
        groupchat_version_id: str,
        spec: ParticipantSpec,
        room: Snapshot | None,
    ) -> Participant:
        """Validate exact evaluated, admin-approved, published version and scope.

        Never substitute latest for the requested pin. Backend attests eligibility
        for this exact version; missing evidence must fail closed.
        Validate mapping, join AND history ACL before admission.

        Provision member-specific binding, isolating memory/workspace per generation.
        Any audience/binding rotation must be atomic in the backend, before return.
        """
        ...

    async def invocation_run(
        self,
        context: Context,
        room: Snapshot,
        participant: Participant,
        operation_id: str,
    ) -> str:
        """Authorize pinned member binding; return backend child run ID (not parent).

        Applies to both authorized user mentions and Supervisor turns. Do not
        require Supervisor role for an already authorized mention. Recheck the
        exact pin and current participation permissions; never upgrade the pin.
        """
        ...


@dataclass(frozen=True)
class Invocation:
    operation_id: str
    fence: int
    context: Context
    room_id: str
    participant: Participant
    source_run_id: str
    transcript: tuple[Message, ...]
    instruction: str
    tasks: tuple[TaskItem, ...] = ()
    ticket_context: tuple[ContextItem, ...] = ()


class AgentInvocationPort(Protocol):
    async def prepare(self, invocation: Invocation) -> None:
        """Preflight only: mapping/config checks; MUST NOT invoke model/tools."""
        ...

    async def invoke(self, invocation: Invocation) -> AgentOutput: ...

    async def cancel(self, invocation: Invocation) -> bool:
        """True ONLY when terminal/cancel confirmed, including remote tools.

        Also suppress any not-yet-dispatched attempt of this stable operation ID;
        cancel may race ahead of invoke. A durable tombstone/remote fence is needed.
        """
        ...


class RoomStatePort(Protocol):
    def transaction(self, context: Context) -> AbstractAsyncContextManager[ScopeState]:
        """Serializable, rollback-on-error transaction for the full scope/generation.

        Atomically persist unique room mapping, operations, transcript, dispatch
        boundary and monotonic fence. Lock across replicas; no I/O dispatch under
        transaction. Fence never reused, including lease takeover. Recovery of a
        committed dispatch boundary MUST pause outcome_unknown; never auto-retry.
        DEV-4 owns leases, durable completion/outbox and framework state reference.
        """
        ...
