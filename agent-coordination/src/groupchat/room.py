"""Single-turn room orchestration; never selects speakers or retries invocations."""

from __future__ import annotations

import asyncio
import hashlib
import json
from copy import deepcopy

from pydantic import ValidationError

from . import context_builder, mailbox, messaging, task_board
from .models import (
    ActiveOperation,
    AddParticipant,
    AgentOutput,
    AppendMessage,
    CancelTurn,
    CloseRoom,
    Command,
    Error,
    Failure,
    MentionAgent,
    MessageInput,
    OpenRoom,
    OperationRecord,
    ParticipantSpec,
    PutContext,
    PutTask,
    Query,
    RoomData,
    RoomError,
    RunTurn,
    Snapshot,
    Success,
    TerminalInvocationError,
    TurnStatus,
    UpdateTurnPolicy,
    new_id,
)
from .participants import member, validate_resolved
from .ports import AgentInvocationPort, Invocation, ParticipantResolver, RoomStatePort


def error_result(
    request_id: str, code: str, message: str | None = None, turn: RoomData | None = None
) -> Failure:
    return Failure(
        request_id=request_id,
        error=Error(
            code=code,
            message=message or code,
            retryable=code == "DEPENDENCY_UNAVAILABLE",
            details={"turn_result": turn.model_dump(mode="json")} if turn else {},
        ),
    )


class RoomService:
    def __init__(
        self,
        resolver: ParticipantResolver,
        invocation: AgentInvocationPort,
        state: RoomStatePort,
    ):
        self.resolver, self.invocation, self.state = resolver, invocation, state

    @staticmethod
    def data(
        room: Snapshot,
        active: ActiveOperation | None = None,
        status: TurnStatus | None = None,
        output: AgentOutput | None = None,
    ) -> RoomData:
        active = active or room.active_operation
        payload = active.command.payload if active else None
        return RoomData(
            room_id=room.room_id,
            ticket_id=room.scope.ticket_id,
            ticket_generation=room.scope.ticket_generation,
            room_version=room.room_version,
            room_state=room.room_state,
            pause_reason=room.pause_reason,
            operation_id=active.operation_id if active else None,
            turn_id=payload.turn_id if isinstance(payload, RunTurn) else None,
            task_id=payload.task_id
            if isinstance(payload, (RunTurn, MentionAgent))
            else None,
            source_run_id=active.source_run_id if active else None,
            speaker_agent_version_id=active.participant.agent_version_id
            if active
            else room.last_speaker,
            turn_status=status,
            messages=deepcopy(room.transcript),
            follow_up_requests=output.follow_up_requests if output else [],
            turns_used=room.turns_used,
            turns_remaining=max(0, room.policy.max_turns - room.turns_used),
            consecutive_turns=room.consecutive_turns,
            participants=[
                ParticipantSpec(agent_version_id=p.agent_version_id, role=p.role)
                for p in room.participants
            ],
            transcript_cursor=room.transcript_cursor,
            tasks=deepcopy(list(room.tasks.values())),
            needs_dispatcher_decision=room.room_state != "running",
        )

    @staticmethod
    def _invocation(room: Snapshot, active: ActiveOperation) -> Invocation:
        payload = active.command.payload
        assert isinstance(payload, (RunTurn, MentionAgent))
        context = context_builder.build(
            room,
            active.participant.agent_version_id,
            payload.task_id,
            payload.in_reply_to_message_id,
        )
        return Invocation(
            active.operation_id,
            active.fence,
            active.command.context,
            room.room_id,
            active.participant,
            active.source_run_id,
            context.messages,
            payload.instruction,
            context.tasks,
            context.ticket,
        )

    async def execute(self, raw: Command | dict) -> Success | Failure:
        request_id = (
            raw.request_id
            if isinstance(raw, Command)
            else str(raw.get("request_id") or "invalid")[:256]
        )
        try:
            command = Command.model_validate(raw)
            return await self._execute(command)
        except ValidationError:
            return error_result(
                request_id, "VALIDATION_ERROR", "Invalid command shape or field value"
            )
        except RoomError as exc:
            return error_result(request_id, exc.code, str(exc))
        except asyncio.CancelledError:
            raise  # committed dispatch remains fenced; DEV-4 recovery must reconcile
        except Exception:  # noqa: BLE001 - sanitize dependency errors; uncertain dispatch stays fenced
            return error_result(
                request_id,
                "DEPENDENCY_UNAVAILABLE",
                "Dependency failed; inspect operation before retry",
            )

    async def _execute(self, command: Command) -> Success | Failure:
        ctx, p = command.context, command.payload
        result: Success | Failure
        await self.resolver.authorize(ctx, p.operation, None)
        # Tracing IDs are excluded; authority/binding changes are semantic.
        semantic = {
            "payload": p.model_dump(mode="json"),
            "context": ctx.model_dump(mode="json"),
        }
        digest = hashlib.sha256(
            json.dumps(semantic, sort_keys=True, separators=(",", ":")).encode()
        ).hexdigest()
        # Bound internal key length even when the caller uses the full 256-char key.
        key_hash = hashlib.sha256(command.idempotency_key.encode()).hexdigest()
        key = f"{p.operation}:{key_hash}"
        async with self.state.transaction(ctx) as state:
            room = state.snapshot
            await self.resolver.authorize(ctx, p.operation, room)
            if room and not room.scope.same_room_scope(ctx):
                raise RoomError("SCOPE_MISMATCH")
            if key in state.operations:
                record = state.operations[key]
                if record.semantic_hash != digest:
                    raise RoomError("IDEMPOTENCY_CONFLICT")
                return record.result.model_copy(
                    update={"request_id": command.request_id}, deep=True
                )
            if isinstance(p, OpenRoom):
                if room:
                    if p.room_id and p.room_id != room.room_id:
                        raise RoomError("SCOPE_MISMATCH")
                    if (
                        p.groupchat_version_id != room.groupchat_version_id
                        or p.participants
                        != [
                            ParticipantSpec(
                                agent_version_id=x.agent_version_id, role=x.role
                            )
                            for x in room.participants
                        ]
                    ):
                        raise RoomError("VERSION_MISMATCH")
                else:
                    if p.room_id:
                        raise RoomError(
                            "NOT_FOUND", "Cannot create a caller-selected room ID"
                        )
                    room = Snapshot(
                        room_id=new_id(),
                        scope=ctx,
                        groupchat_version_id=p.groupchat_version_id,
                        participants=[],
                        policy=p.turn_policy,
                    )
                    for spec in p.participants:
                        resolved = await self.resolver.resolve(
                            ctx, p.groupchat_version_id, spec, room
                        )
                        validate_resolved(spec, resolved, room)
                        room.participants.append(resolved)
                    for item in p.ticket_context:
                        task_board.put_context(room, item)
                    messaging.append(room, p.initial_message, ctx.principal_id)
                    state.snapshot = room
                result = Success(
                    request_id=command.request_id,
                    status="completed",
                    data=self.data(room),
                )
                state.operations[key] = OperationRecord(
                    semantic_hash=digest, result=result
                )
                return result
            if not room or room.room_id != p.room_id:
                raise RoomError("NOT_FOUND")
            if room.active_operation and not isinstance(p, CancelTurn):
                raise RoomError(
                    "ROOM_BUSY" if room.room_state == "running" else "ROOM_PAUSED"
                )
            if room.room_version != p.expected_room_version:
                raise RoomError("STALE_VERSION")
            if room.room_state == "closed":
                raise RoomError("ROOM_CLOSED")
            if isinstance(p, CancelTurn):
                active = room.active_operation
                if not active or active.operation_id != p.target_operation_id:
                    raise RoomError("VALIDATION_ERROR", "No matching active operation")
                invocation = self._invocation(room, active)
                result = Success(
                    request_id=command.request_id,
                    status="accepted",
                    data=self.data(room),
                )
            else:
                if room.active_operation:
                    raise RoomError(
                        "ROOM_BUSY" if room.room_state == "running" else "ROOM_PAUSED"
                    )
                if isinstance(p, (RunTurn, MentionAgent)):
                    if room.room_state == "paused" and isinstance(p, RunTurn):
                        raise RoomError(
                            "TURN_LIMIT"
                            if room.pause_reason == "max_turns"
                            else "ROOM_PAUSED"
                        )
                    if isinstance(p, MentionAgent):
                        if p.task_id and p.task_id not in room.tasks:
                            raise RoomError(
                                "NOT_FOUND", "Mention task is not in this room"
                            )
                        participant = next(
                            (
                                x
                                for x in room.participants
                                if x.platform_agent_id == p.mentioned_agent_id
                            ),
                            None,
                        )
                        if participant is None:
                            raise RoomError("NOT_MEMBER")
                    else:
                        participant = member(room, p.speaker_agent_version_id)
                    if isinstance(p, RunTurn) and p.turn_id in room.used_turn_ids:
                        raise RoomError("IDEMPOTENCY_CONFLICT", "turn_id already used")
                    if (
                        isinstance(p, RunTurn)
                        and room.turns_used >= room.policy.max_turns
                    ):
                        raise RoomError("TURN_LIMIT")
                    if (
                        isinstance(p, RunTurn)
                        and room.last_speaker == participant.agent_version_id
                        and room.consecutive_turns >= room.policy.max_consecutive_turns
                    ):
                        raise RoomError("CONSECUTIVE_LIMIT")
                    messaging.validate_message(
                        room,
                        MessageInput(
                            content=p.instruction,
                            in_reply_to_message_id=p.in_reply_to_message_id,
                        ),
                    )
                    operation_id = new_id()
                    run_id = await self.resolver.invocation_run(
                        ctx, room, participant, operation_id
                    )
                    active = ActiveOperation(
                        operation_id=operation_id,
                        dedup_key=key,
                        fence=state.fence + 1,
                        command=command,
                        participant=participant,
                        source_run_id=run_id,
                    )
                    selected = context_builder.build(
                        room,
                        participant.agent_version_id,
                        p.task_id,
                        p.in_reply_to_message_id,
                    )
                    active.mailbox_message_ids = list(selected.mailbox_message_ids)
                    invocation = self._invocation(room, active)
                    await self.invocation.prepare(invocation)
                    if isinstance(p, MentionAgent):
                        # Preserve the question for room readers; it was already sent as instruction.
                        messaging.append(
                            room,
                            MessageInput(
                                content=p.instruction,
                                delivery="direct",
                                recipient_agent_version_id=participant.agent_version_id,
                                in_reply_to_message_id=p.in_reply_to_message_id,
                                task_id=p.task_id if p.task_id in room.tasks else None,
                            ),
                            ctx.principal_id,
                        )
                        active.mailbox_message_ids.append(
                            room.transcript[-1].message_id
                        )
                    # Durable dispatch boundary; only Supervisor turns consume its budget.
                    state.fence += 1
                    if isinstance(p, RunTurn):
                        room.turns_used += 1
                        room.consecutive_turns = (
                            room.consecutive_turns + 1
                            if room.last_speaker == participant.agent_version_id
                            else 1
                        )
                        room.last_speaker = participant.agent_version_id
                        room.used_turn_ids.append(p.turn_id)
                    room.active_operation = active
                    room.room_state, room.pause_reason = "running", None
                    room.room_version += 1
                    result = Success(
                        request_id=command.request_id,
                        status="accepted",
                        data=self.data(room),
                    )
                else:
                    if isinstance(p, AppendMessage):
                        messaging.append(room, p.message, ctx.principal_id)
                    elif isinstance(p, PutTask):
                        task_board.put(room, p.task)
                    elif isinstance(p, PutContext):
                        task_board.put_context(room, p.item)
                    elif isinstance(p, AddParticipant):
                        resolved = await self.resolver.resolve(
                            ctx, room.groupchat_version_id, p.participant, room
                        )
                        validate_resolved(p.participant, resolved, room)
                        room.participants.append(resolved)
                    elif isinstance(p, UpdateTurnPolicy):
                        room.audit_events.append(
                            {
                                "event": "turn_policy_updated",
                                "principal_id": ctx.principal_id,
                                "before": room.policy.model_dump(),
                                "after": p.turn_policy.model_dump(),
                            }
                        )
                        room.policy = p.turn_policy
                        room.room_state = (
                            "paused"
                            if room.turns_used >= room.policy.max_turns
                            else "idle"
                        )
                        room.pause_reason = (
                            "max_turns" if room.room_state == "paused" else None
                        )
                    elif isinstance(p, CloseRoom):
                        room.room_state, room.pause_reason = "closed", None
                    room.room_version += 1
                    result = Success(
                        request_id=command.request_id,
                        status="completed",
                        data=self.data(room),
                    )
            state.operations[key] = OperationRecord(semantic_hash=digest, result=result)
            if not isinstance(p, (RunTurn, MentionAgent, CancelTurn)):
                return result
            timeout = room.policy.timeout_seconds
        # Framework/network I/O MUST be outside storage transaction.
        if isinstance(p, CancelTurn):
            confirmed = await self._cancel(invocation)
            await self.complete(
                invocation, "cancel" if confirmed else "outcome_unknown"
            )
            async with self.state.transaction(ctx) as state:
                assert state.snapshot
                await self.resolver.authorize(ctx, p.operation, state.snapshot)
                assert active is not None
                target = state.operations[active.dedup_key].result
                result = target.model_copy(
                    update={"request_id": command.request_id}, deep=True
                )
                state.operations[key].result = result
                return result
        task = asyncio.create_task(self.invocation.invoke(invocation))
        try:
            done, _ = await asyncio.wait({task}, timeout=timeout)
            if done:
                try:
                    output = task.result()
                except asyncio.CancelledError:
                    await self.complete(invocation, "outcome_unknown")
                except TerminalInvocationError:
                    await self.complete(invocation, "failure")
                except Exception:  # noqa: BLE001 - sanitize dependency errors; uncertain dispatch stays fenced
                    await self.complete(invocation, "outcome_unknown")
                else:
                    await self.complete(invocation, "success", output)
            else:
                confirmed = await self._cancel(invocation)
                # Detach from caller without interpreting local cancellation as remote proof.
                task.cancel()
                task.add_done_callback(self._consume_task)
                await self.complete(
                    invocation, "timeout" if confirmed else "outcome_unknown"
                )
        except asyncio.CancelledError:
            task.cancel()
            task.add_done_callback(self._consume_task)
            await asyncio.shield(self.complete(invocation, "outcome_unknown"))
            raise
        async with self.state.transaction(ctx) as state:
            await self.resolver.authorize(ctx, p.operation, state.snapshot)
            return state.operations[key].result.model_copy(deep=True)

    @staticmethod
    def _consume_task(task: asyncio.Task) -> None:
        if not task.cancelled():
            task.exception()

    async def _cancel(self, invocation: Invocation) -> bool:
        try:
            async with asyncio.timeout(5):
                return await self.invocation.cancel(invocation)
        except Exception:  # noqa: BLE001 - sanitize dependency errors; uncertain dispatch stays fenced
            return False

    async def complete(
        self,
        invocation: Invocation,
        status: TurnStatus,
        output: AgentOutput | None = None,
    ) -> bool:
        """Trusted adapter/DEV-4 callback only; context + operation + fence checked.

        outcome_unknown retains slot. A later verified terminal callback can release
        it once; retired generation, stale fence and double completion are rejected.
        """
        try:
            await self.resolver.authorize(invocation.context, "complete_turn", None)
            async with self.state.transaction(invocation.context) as state:
                room = state.snapshot
                if (
                    not room
                    or room.room_id != invocation.room_id
                    or not room.scope.same_room_scope(invocation.context)
                ):
                    return False
                await self.resolver.authorize(invocation.context, "complete_turn", room)
                active = room.active_operation
                if (
                    not active
                    or active.operation_id != invocation.operation_id
                    or active.fence != invocation.fence
                    or state.fence != invocation.fence
                ):
                    return False
                if status == "success":
                    if output is None:
                        raise RoomError("VALIDATION_ERROR")
                    try:
                        for follow in output.follow_up_requests:
                            member(room, follow.recipient_agent_version_id)
                            payload = active.command.payload
                            assert isinstance(payload, (RunTurn, MentionAgent))
                            messaging.validate_message(
                                room,
                                MessageInput(
                                    content=follow.content,
                                    delivery="direct",
                                    recipient_agent_version_id=follow.recipient_agent_version_id,
                                    task_id=payload.task_id
                                    if payload.task_id in room.tasks
                                    else None,
                                ),
                            )
                    except RoomError:
                        status, output = "failure", None
                if status == "success":
                    assert output is not None
                    p = active.command.payload
                    assert isinstance(p, (RunTurn, MentionAgent))
                    messaging.append(
                        room,
                        MessageInput(
                            content=output.content,
                            in_reply_to_message_id=p.in_reply_to_message_id,
                            task_id=p.task_id if p.task_id in room.tasks else None,
                        ),
                        active.participant.agent_version_id,
                    )
                    mailbox.acknowledge(
                        room,
                        active.participant.agent_version_id,
                        active.mailbox_message_ids,
                    )
                    for follow in output.follow_up_requests:
                        messaging.append(
                            room,
                            MessageInput(
                                content=follow.content,
                                delivery="direct",
                                recipient_agent_version_id=follow.recipient_agent_version_id,
                                task_id=p.task_id if p.task_id in room.tasks else None,
                            ),
                            active.participant.agent_version_id,
                        )
                if status == "outcome_unknown":
                    room.room_state, room.pause_reason = "paused", "outcome_unknown"
                else:
                    room.active_operation = None
                    room.room_state = (
                        "paused" if room.turns_used >= room.policy.max_turns else "idle"
                    )
                    room.pause_reason = (
                        "max_turns" if room.room_state == "paused" else None
                    )
                room.room_version += 1
                data = self.data(room, active, status, output)
                result = (
                    Success(
                        request_id=active.command.request_id,
                        status="completed",
                        data=data,
                    )
                    if status in ("success", "cancel")
                    else error_result(
                        active.command.request_id,
                        {
                            "failure": "AGENT_FAILURE",
                            "timeout": "AGENT_TIMEOUT",
                            "outcome_unknown": "OUTCOME_UNKNOWN",
                        }[status],
                        turn=data,
                    )
                )
                state.operations[active.dedup_key].result = result
                return True
        except RoomError:
            return False

    async def query(self, query: Query) -> Success | Failure:
        try:
            await self.resolver.authorize(query.context, query.operation, None)
            async with self.state.transaction(query.context) as state:
                room = state.snapshot
                await self.resolver.authorize(query.context, query.operation, room)
                if not room or room.room_id != query.room_id:
                    raise RoomError("NOT_FOUND")
                if not room.scope.same_room_scope(query.context):
                    raise RoomError("SCOPE_MISMATCH")
                data = self.data(room)
                data.messages = [
                    m for m in data.messages if m.sequence > query.after_sequence
                ][: query.limit]
                return Success(
                    request_id=query.request_id, status="completed", data=data
                )
        except RoomError as exc:
            return error_result(query.request_id, exc.code)

        except Exception:  # noqa: BLE001 - public boundary must not expose dependency secrets
            return error_result(
                query.request_id,
                "DEPENDENCY_UNAVAILABLE",
                "Query dependency unavailable",
            )
