"""Các port yêu cầu authorization thật và atomic persistence trong production."""

from contextlib import AbstractAsyncContextManager
from dataclasses import dataclass
from typing import Optional, Protocol

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
        self, context: Context, operation: str, room: Optional[Snapshot]
    ) -> None:
        """Kiểm tra credential/delegation, current generation, scope và history ACL.

        Gọi trước replay/read và trước khi chấp nhận completion. JSON Context không
        phải credential; implementation phải dùng evidence từ gateway.
        put_task chỉ dành cho Supervisor; put_context chỉ nhận trusted backend data.
        mention_agent kiểm tra user delegation, tách biệt với Supervisor run_turn.
        Public room query/result yêu cầu room-wide read permission.
        """
        ...

    async def resolve(
        self,
        context: Context,
        groupchat_version_id: str,
        spec: ParticipantSpec,
        room: Optional[Snapshot],
    ) -> Participant:
        """Validate đúng evaluated, admin-approved, published version và scope.

        Không substitute latest cho requested pin. Backend phải attest eligibility
        cho đúng version; thiếu evidence thì fail closed.
        Validate mapping, join và history ACL trước admission.

        Provision member-specific binding, isolate memory/workspace theo generation.
        Audience/binding rotation phải atomic ở backend trước khi return.
        """
        ...

    async def invocation_run(
        self,
        context: Context,
        room: Snapshot,
        participant: Participant,
        operation_id: str,
    ) -> str:
        """Authorize pinned member binding; trả về backend child run ID.

        Áp dụng cho authorized user mention và Supervisor turn. Không yêu cầu
        Supervisor role cho mention đã được authorize. Recheck exact pin và current
        participation permission; không upgrade pin.
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
    groupchat_version_id: Optional[str] = None
    artifact_hash: Optional[str] = None


class AgentInvocationPort(Protocol):
    async def prepare(self, invocation: Invocation) -> None:
        """Chỉ preflight mapping/config; KHÔNG invoke model/tool."""
        ...

    async def invoke(self, invocation: Invocation) -> AgentOutput: ...

    async def cancel(self, invocation: Invocation) -> bool:
        """Chỉ trả True khi terminal/cancel đã confirm, gồm cả remote tools.

        Đồng thời suppress attempt chưa dispatch của stable operation ID này;
        cancel có thể race trước invoke. Cần durable tombstone hoặc remote fence.
        """
        ...


class RoomStatePort(Protocol):
    def transaction(self, context: Context) -> AbstractAsyncContextManager[ScopeState]:
        """Serializable, rollback-on-error transaction cho toàn scope/generation.

        Atomically persist unique room mapping, operation, transcript, dispatch
        boundary và monotonic fence. Lock across replicas; không dispatch I/O trong
        transaction. Không reuse fence, kể cả lease takeover. Recovery của committed
        dispatch boundary phải pause ở outcome_unknown; không auto-retry.
        Storage layer quản lý lease, durable completion/outbox và framework state reference.
        """
        ...
