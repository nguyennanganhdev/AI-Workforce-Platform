import asyncio
from dataclasses import replace

import pytest
from groupchat.models import (
    AgentOutput,
    AppendMessage,
    CancelTurn,
    Failure,
    MessageInput,
    TurnPolicy,
)
from support.fakes import make_context
from support.harness import room_args as args


async def test_concurrent_duplicate_busy_and_cas(harness):
    _, opened = await harness.open()
    harness.agents.delay = 0.08
    cmd = harness.turn(opened.data)
    running = asyncio.create_task(harness.service.execute(cmd))
    await harness.agents.started.wait()
    dup = await harness.service.execute(cmd)
    assert dup.status == "accepted"
    assert (
        await harness.service.execute(harness.turn(dup.data, "B-v1"))
    ).error.code == "ROOM_BUSY"
    done = await running
    assert done.data.turns_used == 1 and len(harness.agents.calls) == 1
    one = harness.command(
        AppendMessage(**args(done.data), message=MessageInput(content="one"))
    )
    two = harness.command(
        AppendMessage(**args(done.data), message=MessageInput(content="two"))
    )
    results = await asyncio.gather(
        harness.service.execute(one), harness.service.execute(two)
    )
    assert sorted(x.status for x in results) == ["completed", "error"]
    assert (
        next(x for x in results if isinstance(x, Failure)).error.code == "STALE_VERSION"
    )


async def test_two_rooms_concurrent_isolated(harness):
    _, a = await harness.open()
    ctx2 = make_context("ROOM-2")
    _, b = await harness.open(context=ctx2)
    harness.agents.delay = 0.03
    ra, rb = await asyncio.gather(
        harness.service.execute(harness.turn(a.data)),
        harness.service.execute(harness.turn(b.data, "B-v1", context=ctx2)),
    )
    assert ra.data.room_id != rb.data.room_id
    assert (
        ra.data.messages[-1].sender == "A-v1" and rb.data.messages[-1].sender == "B-v1"
    )
    assert len(harness.agents.history) == 2


@pytest.mark.parametrize(
    "confirmed,code,status",
    [(False, "OUTCOME_UNKNOWN", "outcome_unknown"), (True, "AGENT_TIMEOUT", "timeout")],
)
async def test_timeout_cancel_confirmation(harness, confirmed, code, status):
    _, opened = await harness.open(policy=TurnPolicy(timeout_seconds=0.01))
    harness.agents.delay = 0.1
    harness.agents.cancel_confirmed = confirmed
    result = await harness.service.execute(harness.turn(opened.data))
    assert result.error.code == code
    assert result.error.details["turn_result"]["turn_status"] == status
    room = harness.state.records[harness.ctx.scope()].snapshot
    assert room.turns_used == 1
    assert (room.active_operation is None) == confirmed
    if not confirmed:
        assert room.room_state == "paused"
        blocked = await harness.service.execute(
            harness.turn(harness.service.data(room), "B-v1")
        )
        assert blocked.error.code == "ROOM_PAUSED"


async def test_cancel_unknown_then_confirm_and_no_double_complete(harness):
    _, opened = await harness.open(policy=TurnPolicy(timeout_seconds=0.01))
    harness.agents.delay = 0.1
    harness.agents.cancel_confirmed = False
    cmd = harness.turn(opened.data)
    await harness.service.execute(cmd)
    room = harness.state.records[harness.ctx.scope()].snapshot
    active = room.active_operation
    stale = replace(harness.agents.calls[0], fence=999)
    assert not await harness.service.complete(
        stale, "success", AgentOutput(content="stale")
    )
    harness.agents.cancel_confirmed = True
    cancel = harness.command(
        CancelTurn(
            **args(harness.service.data(room)), target_operation_id=active.operation_id
        )
    )
    done = await harness.service.execute(cancel)
    assert done.data.turn_status == "cancel" and done.data.room_state == "idle"
    assert (await harness.service.execute(cmd)).data.turn_status == "cancel"
    assert not await harness.service.complete(
        harness.agents.calls[0], "success", AgentOutput(content="late")
    )
    assert len(harness.state.records[harness.ctx.scope()].snapshot.transcript) == 1


async def test_late_terminal_reconcile_and_fence(harness):
    _, opened = await harness.open(policy=TurnPolicy(timeout_seconds=0.01))
    harness.agents.delay, harness.agents.cancel_confirmed = 0.1, False
    await harness.service.execute(harness.turn(opened.data))
    invocation = harness.agents.calls[0]
    assert await harness.service.complete(
        invocation, "success", AgentOutput(content="terminal confirmed")
    )
    assert not await harness.service.complete(
        invocation, "success", AgentOutput(content="duplicate")
    )
    room = harness.state.records[harness.ctx.scope()].snapshot
    assert room.turns_used == 1 and len(room.transcript) == 2


async def test_reopen_rejects_old_generation_callback(harness):
    _, opened = await harness.open(policy=TurnPolicy(timeout_seconds=0.01))
    harness.agents.delay, harness.agents.cancel_confirmed = 0.1, False
    await harness.service.execute(harness.turn(opened.data))
    old = harness.agents.calls[0]
    harness.resolver.generations[harness.ctx.scope()[:-1]] = 1
    ctx = make_context(generation=1)
    _, reopened = await harness.open(context=ctx)
    assert reopened.data.room_id != opened.data.room_id
    assert not await harness.service.complete(
        old, "success", AgentOutput(content="old generation")
    )
    assert reopened.data.turns_used == 0


async def test_live_cancel_confirmed_and_new_turn_no_overlap(harness):
    _, opened = await harness.open()
    harness.agents.delay = 0.5
    command = harness.turn(opened.data)
    running = asyncio.create_task(harness.service.execute(command))
    await harness.agents.started.wait()
    room = harness.state.records[harness.ctx.scope()].snapshot
    cancelled = await harness.service.execute(
        harness.command(
            CancelTurn(
                **args(harness.service.data(room)),
                target_operation_id=room.active_operation.operation_id,
            )
        )
    )
    assert cancelled.data.turn_status == "cancel"
    await running
    assert not harness.agents.tasks
    harness.agents.delay = 0
    done = await harness.service.execute(harness.turn(cancelled.data, "B-v1"))
    assert done.data.turns_used == 2


async def test_lease_takeover_fence_rejects_old_worker(harness):
    _, opened = await harness.open(policy=TurnPolicy(timeout_seconds=0.01))
    harness.agents.delay, harness.agents.cancel_confirmed = 0.1, False
    await harness.service.execute(harness.turn(opened.data))
    async with harness.state.transaction(harness.ctx) as record:
        record.fence += 1  # Mô phỏng tiếp quản lease; KHÔNG gửi lại khi chưa đối soát.
    assert not await harness.service.complete(
        harness.agents.calls[0], "success", AgentOutput(content="old lease")
    )
    assert harness.state.records[harness.ctx.scope()].snapshot.room_state == "paused"


async def test_cancel_before_invocation_io_suppresses_future_dispatch(harness):
    _, opened = await harness.open()
    entered, release = asyncio.Event(), asyncio.Event()
    invoke = harness.agents.invoke

    async def delayed_transport(invocation):
        entered.set()
        await release.wait()
        return await invoke(invocation)

    harness.agents.invoke = delayed_transport
    running = asyncio.create_task(harness.service.execute(harness.turn(opened.data)))
    await entered.wait()
    room = harness.state.records[harness.ctx.scope()].snapshot
    cancelled = await harness.service.execute(
        harness.command(
            CancelTurn(
                **args(harness.service.data(room)),
                target_operation_id=room.active_operation.operation_id,
            )
        )
    )
    release.set()
    result = await running
    assert cancelled.data.turn_status == result.data.turn_status == "cancel"
    assert not harness.agents.calls
    assert result.data.turns_used == 1  # Mốc gửi được ghi nhận thận trọng.


async def test_serialized_state_preserves_dedup_after_new_service(harness):
    from groupchat.models import ScopeState
    from groupchat.room import RoomService

    _, opened = await harness.open()
    command = harness.turn(opened.data)
    done = await harness.service.execute(command)
    harness.state.records[harness.ctx.scope()] = ScopeState.model_validate_json(
        harness.state.records[harness.ctx.scope()].model_dump_json()
    )
    restarted = RoomService(harness.resolver, harness.agents, harness.state)
    assert (await restarted.execute(command)).data == done.data
    assert len(harness.agents.calls) == 1
