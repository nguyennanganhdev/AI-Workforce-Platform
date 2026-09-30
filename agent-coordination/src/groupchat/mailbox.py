"""Persistent pending delivery in the room aggregate; sending never runs agents."""

from .models import MailItem, Message, Snapshot
from .task_board import can_read


def enqueue(room: Snapshot, message: Message) -> None:
    recipients = (
        [message.recipient_agent_version_id]
        if message.recipient_agent_version_id
        else [p.agent_version_id for p in room.participants]
    )
    recipients = [
        r
        for r in recipients
        if r != message.sender
        and (message.task_id is None or can_read(room.tasks[message.task_id], r))
    ]
    if recipients:
        room.mailbox.append(
            MailItem(
                message=message.model_copy(deep=True),
                pending_agent_version_ids=recipients,
            )
        )


def acknowledge(room: Snapshot, agent_id: str, message_ids: list[str]) -> None:
    delivered = set(message_ids)
    for item in room.mailbox:
        if (
            item.message.message_id in delivered
            and agent_id in item.pending_agent_version_ids
        ):
            item.pending_agent_version_ids.remove(agent_id)
    room.mailbox = [item for item in room.mailbox if item.pending_agent_version_ids]
