"""Kiểm tra lời nhắc trực tiếp, phiên bản thành viên và hạn mức lượt."""

import asyncio

import pytest
from groupchat.models import (
    AddParticipant,
    ParticipantSpec,
    RoomError,
    TurnPolicy,
)
from support.harness import mention
from support.harness import room_args as args


async def test_mention_immediate_pinned_id_replay_and_no_supervisor_budget(harness):
    _, opened = await harness.open(policy=TurnPolicy(max_turns=1))
    exhausted = await harness.service.execute(harness.turn(opened.data))
    command = mention(harness, exhausted.data)
    done = await harness.service.execute(command)
    assert done.status == "completed" and done.data.speaker_agent_version_id == "B-v1"
    assert done.data.turns_used == 1 and done.data.room_state == "paused"
    assert harness.agents.calls[-1].participant.agent_version_id == "B-v1"
    assert done.data.messages[-1].sender == "B-v1"
    assert (await harness.service.execute(command)).data == done.data
    assert len(harness.agents.calls) == 2


@pytest.mark.parametrize("agent", ["unknown", "B-v2", "B-v1", "@B"])
async def test_mention_unknown_id_never_invites(harness, agent):
    _, opened = await harness.open()
    result = await harness.service.execute(mention(harness, opened.data, agent=agent))
    assert result.error.code == "NOT_MEMBER" and not harness.agents.calls
    assert len(harness.state.records[harness.ctx.scope()].snapshot.participants) == 2


async def test_mention_denied_member_never_invokes(harness):
    _, opened = await harness.open()

    async def deny(*args):
        raise RoomError("FORBIDDEN")

    harness.resolver.invocation_run = deny
    result = await harness.service.execute(mention(harness, opened.data))
    assert result.error.code == "FORBIDDEN" and not harness.agents.calls
    assert harness.state.records[harness.ctx.scope()].snapshot.room_version == 1


async def test_mention_busy_is_explicit_not_queued_to_supervisor(harness):
    _, opened = await harness.open()
    harness.agents.delay = 0.05
    running = asyncio.create_task(harness.service.execute(harness.turn(opened.data)))
    await harness.agents.started.wait()
    room = harness.state.records[harness.ctx.scope()].snapshot
    result = await harness.service.execute(mention(harness, harness.service.data(room)))
    assert result.error.code == "ROOM_BUSY"
    await running
    assert len(harness.agents.calls) == 1


async def test_existing_pin_cannot_be_replaced_and_no_resolve_on_mention(harness):
    _, opened = await harness.open()
    original = harness.resolver.resolve

    async def resolve(ctx, group, spec, room):
        if spec.agent_version_id == "B-v2":
            old = await original(
                ctx,
                group,
                ParticipantSpec(agent_version_id="B-v1", role=spec.role),
                room,
            )
            return old.model_copy(update={"agent_version_id": "B-v2"})
        return await original(ctx, group, spec, room)

    harness.resolver.resolve = resolve
    rejected = await harness.service.execute(
        harness.command(
            AddParticipant(
                **args(opened.data),
                participant=ParticipantSpec(agent_version_id="B-v2", role="advisor"),
            )
        )
    )
    assert rejected.error.code == "VERSION_MISMATCH"

    async def cannot_resolve(*args):
        raise AssertionError("must use existing pin")

    harness.resolver.resolve = cannot_resolve
    assert (
        await harness.service.execute(mention(harness, opened.data))
    ).status == "completed"
    assert harness.agents.calls[-1].participant.agent_version_id == "B-v1"
