"""Lưu trạng thái tác vụ hiện tại; Supervisor quyết định việc phân công."""

from .models import ContextItem, RoomError, Snapshot, TaskItem
from .participants import member


def can_read(task: TaskItem, agent_id: str) -> bool:
    return (
        not task.reader_agent_version_ids or agent_id in task.reader_agent_version_ids
    )


def put(room: Snapshot, task: TaskItem) -> None:
    member(room, task.assignee_agent_version_id)
    for version in task.reader_agent_version_ids:
        member(room, version)
    if not can_read(task, task.assignee_agent_version_id):
        raise RoomError("FORBIDDEN", "Assignee must be allowed to read the task")
    room.tasks[task.task_id] = task.model_copy(deep=True)


def put_context(room: Snapshot, item: ContextItem) -> None:
    for version in item.reader_agent_version_ids:
        member(room, version)
    if item.task_id and item.task_id not in room.tasks:
        raise RoomError("NOT_FOUND", "Context task is not in this room")
    room.ticket_context[item.item_id] = item.model_copy(deep=True)
