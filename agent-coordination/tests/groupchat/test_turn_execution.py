from groupchat.models import (
    AppendMessage,
    MessageInput,
    TurnPolicy,
    UpdateTurnPolicy,
)
from support.harness import room_args as args


async def test_duplicate_before_version_check_and_payload_conflict(harness):
    _, opened = await harness.open()
    cmd = harness.turn(opened.data, key="same")
    done = await harness.service.execute(cmd)
    cmd.request_id = "retry-request"
    cmd.trace_id = "retry-trace"
    replay = await harness.service.execute(cmd)
    assert replay.data == done.data and replay.request_id == "retry-request"
    assert len(harness.agents.calls) == 1
    cmd.payload.instruction = "different semantics"
    assert (await harness.service.execute(cmd)).error.code == "IDEMPOTENCY_CONFLICT"


async def test_limits_failures_and_dispatcher_message_do_not_reset(harness):
    _, opened = await harness.open(policy=TurnPolicy(max_turns=3))
    one = await harness.service.execute(harness.turn(opened.data))
    harness.agents.fail = True
    failed = await harness.service.execute(harness.turn(one.data))
    assert (
        failed.error.code == "AGENT_FAILURE"
        and "secret" not in failed.model_dump_json()
    )
    snapshot = harness.state.records[harness.ctx.scope()].snapshot
    appended = await harness.service.execute(
        harness.command(
            AppendMessage(
                **args(harness.service.data(snapshot)),
                message=MessageInput(content="Thêm dữ kiện"),
            )
        )
    )
    rejected = await harness.service.execute(harness.turn(appended.data))
    assert rejected.error.code == "CONSECUTIVE_LIMIT"
    assert len(harness.agents.calls) == 2
    harness.agents.fail = False
    last = await harness.service.execute(harness.turn(appended.data, "B-v1"))
    assert last.data.room_state == "paused" and last.data.turns_used == 3
    assert (
        await harness.service.execute(harness.turn(last.data))
    ).error.code == "TURN_LIMIT"
    increased = await harness.service.execute(
        harness.command(
            UpdateTurnPolicy(**args(last.data), turn_policy=TurnPolicy(max_turns=4))
        )
    )
    assert increased.data.turns_used == 3 and increased.data.turns_remaining == 1
    final = await harness.service.execute(harness.turn(increased.data))
    assert final.data.turns_used == 4
    assert harness.state.records[harness.ctx.scope()].snapshot.audit_events


async def test_preflight_reject_never_consumes(harness):
    _, opened = await harness.open()
    harness.agents.preflight_fail = True
    assert (
        await harness.service.execute(harness.turn(opened.data))
    ).error.code == "MAPPING_MISSING"
    room = harness.state.records[harness.ctx.scope()].snapshot
    assert room.turns_used == 0 and room.room_version == 1 and not harness.agents.calls


async def test_maximum_length_idempotency_key_replays(harness):
    _, opened = await harness.open()
    command = harness.turn(opened.data, key="k" * 256)
    result = await harness.service.execute(command)
    assert result.status == "completed"
    assert (await harness.service.execute(command)).data == result.data
    assert len(harness.agents.calls) == 1
