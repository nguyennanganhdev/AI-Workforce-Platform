from . import mailbox
from .models import Message, MessageInput, RoomError, Snapshot, new_id, now
from .participants import member
from .task_board import can_read


def validate_message(room: Snapshot, message: MessageInput) -> None:
    if message.recipient_agent_version_id:
        member(room, message.recipient_agent_version_id)
    if message.task_id:
        task = room.tasks.get(message.task_id)
        if task is None:
            raise RoomError("NOT_FOUND", "Message task is not in this room")
        if message.recipient_agent_version_id and not can_read(
            task, message.recipient_agent_version_id
        ):
            raise RoomError("FORBIDDEN")
    if message.in_reply_to_message_id and not any(
        m.message_id == message.in_reply_to_message_id for m in room.transcript
    ):
        raise RoomError("VALIDATION_ERROR", "Reply message is not in this room")


def append(room: Snapshot, message: MessageInput, sender: str) -> Message:
    validate_message(room, message)
    result = Message(
        **message.model_dump(),
        message_id=new_id(),
        sequence=room.transcript_cursor + 1,
        sender=sender,
        timestamp=now(),
    )
    room.transcript.append(result)
    room.transcript_cursor = result.sequence
    mailbox.enqueue(room, result)
    return result
