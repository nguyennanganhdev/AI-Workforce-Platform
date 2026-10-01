"""Giới hạn đầu vào và lọc theo quyền đọc, tác vụ; không lấy toàn bộ lịch sử phòng."""

from copy import deepcopy
from dataclasses import dataclass
from typing import Optional

from .models import ContextItem, Message, RoomError, Snapshot, TaskItem
from .task_board import can_read


@dataclass(frozen=True)
class AgentContext:
    messages: tuple[Message, ...]
    tasks: tuple[TaskItem, ...]
    ticket: tuple[ContextItem, ...]
    mailbox_message_ids: tuple[str, ...]


def visible(room: Snapshot, message: Message, agent_id: str) -> bool:
    if message.delivery == "direct" and agent_id not in (
        message.sender,
        message.recipient_agent_version_id,
    ):
        return False
    if message.task_id:
        task = room.tasks.get(message.task_id)
        return task is not None and can_read(task, agent_id)
    return True


def build(
    room: Snapshot,
    agent_id: str,
    task_id: Optional[str],
    reply_id: Optional[str] = None,
) -> AgentContext:
    current = room.tasks.get(task_id) if task_id else None
    if current and not can_read(current, agent_id):
        raise RoomError("FORBIDDEN", "Task is outside agent audience")

    def relevant(message: Message) -> bool:
        return visible(room, message, agent_id) and (
            message.task_id is None or message.task_id == task_id
        )

    recent = [m for m in room.transcript if relevant(m)][-20:]
    pending = [
        item.message
        for item in room.mailbox
        if agent_id in item.pending_agent_version_ids and relevant(item.message)
    ][:50]
    selected = {m.message_id: m for m in recent + pending}
    if reply_id:
        reply = next((m for m in room.transcript if m.message_id == reply_id), None)
        if reply is None or not relevant(reply):
            raise RoomError("FORBIDDEN", "Reply context is outside agent scope")
        selected[reply_id] = reply
    # Chia sẻ bảng theo ACL; chỉ kèm tham chiếu kết quả của công việc liên quan.
    tasks = []
    for task in room.tasks.values():
        if can_read(task, agent_id):
            copy = task.model_copy(deep=True)
            if task.task_id != task_id and task.assignee_agent_version_id != agent_id:
                copy.result_refs = []
            tasks.append(copy)
    ticket = [
        item
        for item in room.ticket_context.values()
        if agent_id in item.reader_agent_version_ids
        and (item.task_id is None or item.task_id == task_id)
        and (
            item.task_id is None
            or (
                item.task_id in room.tasks
                and can_read(room.tasks[item.task_id], agent_id)
            )
        )
    ]
    return AgentContext(
        tuple(deepcopy(sorted(selected.values(), key=lambda m: m.sequence))),
        tuple(tasks),
        tuple(deepcopy(ticket)),
        tuple(
            item.message.message_id
            for item in room.mailbox
            if agent_id in item.pending_agent_version_ids
            and item.message.message_id in selected
        ),
    )
