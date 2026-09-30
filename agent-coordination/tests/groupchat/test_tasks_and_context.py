"""Kiểm tra bảng tác vụ, quyền đọc và giới hạn ngữ cảnh gửi cho agent."""

import pytest
from groupchat.models import (
    AppendMessage,
    ContextItem,
    MessageInput,
    PutContext,
    PutTask,
    RoomError,
    TaskItem,
)
from support.harness import mention, put
from support.harness import room_args as args


async def test_task_board_current_state_no_automatic_assignment(harness):
    _, opened = await harness.open()
    task = TaskItem(
        task_id="inspect", description="Kiểm tra", assignee_agent_version_id="B-v1"
    )
    data = await put(harness, opened.data, task)
    task.status, task.result_refs = "completed", ["backend-result-1"]
    data = await put(harness, data, task)
    room = harness.state.records[harness.ctx.scope()].snapshot
    assert data.tasks == [task] and list(room.tasks) == ["inspect"]
    assert not room.audit_events and not harness.agents.calls
    done = await harness.service.execute(harness.turn(data, "B-v1"))
    assert done.data.tasks == [
        task
    ]  # Phản hồi agent không thay đổi phân công hoặc trạng thái tác vụ.
    assert harness.agents.calls[-1].tasks == (task,)


@pytest.mark.parametrize("operation", ["put_task", "put_context"])
async def test_task_and_context_commands_require_upstream_permission(
    harness, operation
):
    _, opened = await harness.open()
    original = harness.resolver.authorize

    async def authorize(ctx, requested_operation, room):
        await original(ctx, requested_operation, room)
        if requested_operation == operation:
            raise RoomError("FORBIDDEN")

    harness.resolver.authorize = authorize
    payloads = {
        "put_task": PutTask(
            **args(opened.data),
            task=TaskItem(
                task_id="x", description="Kiểm tra", assignee_agent_version_id="B-v1"
            ),
        ),
        "put_context": PutContext(
            **args(opened.data),
            item=ContextItem(
                item_id="x", content="Dữ kiện", reader_agent_version_ids=["B-v1"]
            ),
        ),
    }
    before = harness.state.records[harness.ctx.scope()].model_copy(deep=True)
    result = await harness.service.execute(harness.command(payloads[operation]))
    assert result.error.code == "FORBIDDEN"
    assert harness.state.records[harness.ctx.scope()] == before


@pytest.mark.parametrize(
    "assignee,readers,code",
    [
        pytest.param("X-v1", [], "NOT_MEMBER", id="unknown-assignee"),
        pytest.param("A-v1", ["B-v1"], "FORBIDDEN", id="assignee-cannot-read"),
    ],
)
async def test_invalid_task_assignee_and_audience_do_not_mutate(
    harness, assignee, readers, code
):
    _, opened = await harness.open()
    task = TaskItem(
        task_id="x",
        description="Kiểm tra",
        assignee_agent_version_id=assignee,
        reader_agent_version_ids=readers,
    )
    before = harness.state.records[harness.ctx.scope()].model_copy(deep=True)
    result = await harness.service.execute(
        harness.command(PutTask(**args(opened.data), task=task))
    )
    assert result.error.code == code
    assert harness.state.records[harness.ctx.scope()] == before


async def test_context_ticket_task_acl_and_related_results(harness):
    _, opened = await harness.open()
    data = await put(
        harness,
        opened.data,
        TaskItem(
            task_id="a",
            description="A task",
            assignee_agent_version_id="A-v1",
            reader_agent_version_ids=["A-v1"],
            result_refs=["SECRET_RESULT"],
        ),
    )
    added = await harness.service.execute(
        harness.command(
            PutContext(
                **args(data),
                item=ContextItem(
                    item_id="fact",
                    content="A_PRIVATE_FACT",
                    task_id="a",
                    reader_agent_version_ids=["A-v1"],
                ),
            )
        )
    )
    denied = await harness.service.execute(mention(harness, added.data, task_id="a"))
    assert denied.error.code == "FORBIDDEN" and not harness.agents.calls
    done = await harness.service.execute(mention(harness, added.data))
    invocation = harness.agents.calls[-1]
    assert not invocation.tasks and not invocation.ticket_context
    await harness.service.execute(mention(harness, done.data, agent="A", task_id="a"))
    assert harness.agents.calls[-1].tasks[0].result_refs == ["SECRET_RESULT"]
    assert harness.agents.calls[-1].ticket_context[0].content == "A_PRIVATE_FACT"


async def test_context_is_bounded_even_with_unread_backlog(harness):
    _, opened = await harness.open()
    data = opened.data
    for n in range(85):
        result = await harness.service.execute(
            harness.command(
                AppendMessage(
                    **args(data), message=MessageInput(content=f"message-{n}")
                )
            )
        )
        data = result.data
    await harness.service.execute(mention(harness, data))
    invocation = harness.agents.calls[-1]
    assert len(invocation.transcript) <= 70
    assert len(harness.state.records[harness.ctx.scope()].snapshot.transcript) > 85
    pending = [
        x
        for x in harness.state.records[harness.ctx.scope()].snapshot.mailbox
        if "B-v1" in x.pending_agent_version_ids
    ]
    assert pending  # Không âm thầm bỏ thư cũ chưa giao.


async def test_reply_reference_cannot_pull_private_message_into_context(harness):
    _, opened = await harness.open()
    result = await harness.service.execute(
        harness.command(
            AppendMessage(
                **args(opened.data),
                message=MessageInput(
                    content="B secret",
                    delivery="direct",
                    recipient_agent_version_id="B-v1",
                ),
            )
        )
    )
    denied = await harness.service.execute(
        mention(
            harness,
            result.data,
            agent="A",
            in_reply_to_message_id=result.data.messages[-1].message_id,
        )
    )
    assert denied.error.code == "FORBIDDEN" and not harness.agents.calls
