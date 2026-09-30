"""Kiểm tra lưu thư, giao đúng người nhận và xác nhận đã xử lý."""

from groupchat.models import (
    AgentOutput,
    AppendMessage,
    FollowUp,
    MessageInput,
    ScopeState,
)
from groupchat.room import RoomService
from support.harness import mention
from support.harness import room_args as args


async def test_mail_waits_for_recipient_and_survives_restart(harness):
    _, opened = await harness.open()
    a = await harness.service.execute(harness.turn(opened.data))
    room = harness.state.records[harness.ctx.scope()].snapshot
    follow = next(
        item
        for item in room.mailbox
        if item.message.sender == "A-v1" and item.message.delivery == "direct"
    )
    assert (
        follow.pending_agent_version_ids == ["B-v1"] and len(harness.agents.calls) == 1
    )
    harness.state.records[harness.ctx.scope()] = ScopeState.model_validate_json(
        harness.state.records[harness.ctx.scope()].model_dump_json()
    )
    harness.service = RoomService(harness.resolver, harness.agents, harness.state)
    done = await harness.service.execute(harness.turn(a.data, "B-v1"))
    assert follow.message in harness.agents.calls[-1].transcript
    assert all(
        follow.message.message_id != x.message.message_id
        for x in harness.state.records[harness.ctx.scope()].snapshot.mailbox
    )
    assert done.data.turns_used == 2


async def test_mail_failure_retains_pending_and_success_acknowledges(harness):
    _, opened = await harness.open()
    harness.agents.fail = True
    await harness.service.execute(harness.turn(opened.data, "B-v1"))
    room = harness.state.records[harness.ctx.scope()].snapshot
    assert "B-v1" in room.mailbox[0].pending_agent_version_ids
    harness.agents.fail = False
    await harness.service.execute(mention(harness, harness.service.data(room)))
    room = harness.state.records[harness.ctx.scope()].snapshot
    assert "B-v1" not in room.mailbox[0].pending_agent_version_ids


async def test_direct_message_never_enters_other_agent_context(harness):
    _, opened = await harness.open()
    sent = await harness.service.execute(
        harness.command(
            AppendMessage(
                **args(opened.data),
                message=MessageInput(
                    content="ONLY_B_SECRET",
                    delivery="direct",
                    recipient_agent_version_id="B-v1",
                ),
            )
        )
    )
    a = await harness.service.execute(harness.turn(sent.data))
    assert "ONLY_B_SECRET" not in str(harness.agents.calls[-1].transcript)
    await harness.service.execute(mention(harness, a.data))
    assert "ONLY_B_SECRET" in str(harness.agents.calls[-1].transcript)


async def test_invalid_followup_does_not_publish_partial_output(harness):
    _, opened = await harness.open()

    async def invoke(invocation):
        return AgentOutput(
            content="must not publish",
            follow_up_requests=[
                FollowUp(recipient_agent_version_id="not-member", content="invalid")
            ],
        )

    harness.agents.invoke = invoke
    result = await harness.service.execute(harness.turn(opened.data))
    assert result.error.code == "AGENT_FAILURE"
    room = harness.state.records[harness.ctx.scope()].snapshot
    assert len(room.transcript) == 1
    assert "A-v1" in room.mailbox[0].pending_agent_version_ids
