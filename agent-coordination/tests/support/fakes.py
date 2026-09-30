"""Test doubles cho participant resolver và agent invocation."""

import asyncio

from groupchat.models import (
    AgentOutput,
    Context,
    FollowUp,
    Participant,
    RoomError,
    TerminalInvocationError,
)


class FakeResolver:
    def __init__(self):
        self.revoked = False
        self.history_allowed = True
        self.generations: dict[tuple, int] = {}
        self.calls = []

    async def authorize(self, context, operation, room):
        if (
            self.revoked
            or context.principal_id != "test-dispatcher"
            or context.tenant_id != "test-tenant"
        ):
            raise RoomError("FORBIDDEN")
        if context.ticket_generation != self.generations.get(
            context.scope()[:-1], context.ticket_generation
        ):
            raise RoomError("STALE_GENERATION")
        if room and not room.scope.same_room_scope(context):
            raise RoomError("SCOPE_MISMATCH")
        if not self.history_allowed:
            raise RoomError("HISTORY_DENIED")

    async def resolve(self, context, groupchat_version_id, spec, room):
        if not self.history_allowed:
            raise RoomError("HISTORY_DENIED")
        if groupchat_version_id != "test-group-v1" or spec.agent_version_id not in (
            "A-v1",
            "B-v1",
            "C-v1",
        ):
            raise RoomError("MAPPING_MISSING")
        suffix = (
            f"{context.ticket_id}-g{context.ticket_generation}-{spec.agent_version_id}"
        )
        return Participant(
            **spec.model_dump(),
            platform_agent_id=spec.agent_version_id[0],
            member_id=f"member-{suffix}",
            binding_id=f"binding-{suffix}",
            binding_generation=1,
            framework_agent_id=f"sdk-{spec.agent_version_id[0]}",
            framework_reference=f"session-{suffix}",
        )

    async def invocation_run(self, context, room, participant, operation_id):
        await self.authorize(context, "run_turn", room)
        self.calls.append(participant.binding_id)
        return f"child-run-{operation_id}"


class FakeAgents:
    def __init__(self):
        self.calls = []
        self.cancel_confirmed = True
        self.delay = 0.01
        self.fail = False
        self.preflight_fail = False
        self.started = asyncio.Event()
        self.history = {}
        self.tasks = {}
        self.cancelled_operations = set()

    async def prepare(self, invocation):
        if self.preflight_fail:
            raise RoomError("MAPPING_MISSING")

    async def invoke(self, invocation):
        if invocation.operation_id in self.cancelled_operations:
            raise asyncio.CancelledError
        self.calls.append(invocation)
        self.started.set()
        self.history[invocation.participant.framework_reference] = invocation.transcript
        self.tasks[invocation.operation_id] = asyncio.current_task()
        try:
            await asyncio.sleep(self.delay)
        finally:
            self.tasks.pop(invocation.operation_id, None)
        if self.fail:
            raise TerminalInvocationError("secret exception must not escape")
        speaker = invocation.participant.agent_version_id
        follow = (
            [
                FollowUp(
                    recipient_agent_version_id="B-v1", content="B hãy kiểm tra thêm."
                )
            ]
            if speaker == "A-v1"
            else []
        )
        return AgentOutput(
            content=f"{speaker}: đã đọc {len(invocation.transcript)} tin. "
            + (
                "@B chỉ là đề nghị; chờ Điều phối."
                if follow
                else "Đề xuất để Điều phối xem xét."
            ),
            follow_up_requests=follow,
        )

    async def cancel(self, invocation):
        if self.cancel_confirmed:
            self.cancelled_operations.add(invocation.operation_id)
            task = self.tasks.get(invocation.operation_id)
            if task:
                task.cancel()
                try:
                    await task
                except asyncio.CancelledError:
                    pass
        return self.cancel_confirmed


def make_context(ticket="TEST-1", generation=0):
    return Context(
        tenant_id="test-tenant",
        principal_id="test-dispatcher",
        domain_id="test-domain",
        workspace_id="test-workspace",
        ticket_id=ticket,
        ticket_generation=generation,
        binding_id=f"dispatcher-binding-{ticket}-g{generation}",
        run_id=f"parent-{ticket}-g{generation}",
    )
