from groupchat.models import (
    AppendMessage,
    CloseRoom,
    MessageInput,
    Query,
    Snapshot,
)
from support.harness import room_args as args


async def test_open_append_followup_no_auto_trigger(harness):
    _, opened = await harness.open()
    assert not harness.agents.calls
    result = await harness.service.execute(
        harness.command(
            AppendMessage(
                **args(opened.data),
                message=MessageInput(
                    content="@B TeamSay AgentInvite",
                    delivery="direct",
                    recipient_agent_version_id="B-v1",
                ),
            )
        )
    )
    assert not harness.agents.calls and len(result.data.messages) == 2
    a = await harness.service.execute(harness.turn(result.data))
    assert a.data.follow_up_requests[0].recipient_agent_version_id == "B-v1"
    assert len(harness.agents.calls) == 1
    b = await harness.service.execute(harness.turn(a.data, "B-v1"))
    assert len(harness.agents.calls) == 2
    assert b.data.source_run_id != harness.ctx.run_id
    assert harness.resolver.calls[-1].endswith("B-v1")
    assert [m.sequence for m in b.data.messages] == [
        1,
        2,
        3,
        4,
        5,
    ]  # Lời nhờ phản hồi được lưu thành thư bền vững.
    assert b.data.messages[-1].sender == "B-v1"


async def test_open_replay_and_new_key_no_duplicate_initial(harness):
    command, opened = await harness.open()
    assert (await harness.service.execute(command)).data == opened.data
    command.idempotency_key = "new-key"
    assert len((await harness.service.execute(command)).data.messages) == 1
    assert len(harness.state.records) == 1


async def test_snapshot_roundtrip_close_and_pagination(harness):
    _, opened = await harness.open()
    done = await harness.service.execute(harness.turn(opened.data))
    snap = harness.state.records[harness.ctx.scope()].snapshot
    assert Snapshot.model_validate_json(snap.model_dump_json()) == snap
    assert "framework_reference" not in done.model_dump_json()
    query = Query(
        request_id="page",
        context=harness.ctx,
        room_id=done.data.room_id,
        after_sequence=1,
        limit=1,
    )
    assert len((await harness.service.query(query)).data.messages) == 1
    closed = await harness.service.execute(
        harness.command(CloseRoom(**args(done.data)))
    )
    assert closed.data.room_state == "closed"
    assert (
        await harness.service.execute(harness.turn(closed.data))
    ).error.code == "ROOM_CLOSED"
