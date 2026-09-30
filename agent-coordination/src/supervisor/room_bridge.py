"""DEV-2 public API only. Never complete a turn or enqueue its follow-up mail."""
from groupchat.models import Command, Failure, Query, RoomData
from groupchat.room import RoomService
from .models import Action, SupervisorError, require


class RoomBridge:
    def __init__(self, room: RoomService):
        self.room = room

    async def read(self, context, room_id: str) -> RoomData:
        first = await self.room.query(Query(request_id="supervisor-read", context=context,
                                           room_id=room_id, limit=500))
        if isinstance(first, Failure):
            raise SupervisorError(first.error.code)
        data = first.data.model_copy(deep=True)
        # Stop at this snapshot's cursor. A concurrent mention invalidates the read;
        # do not mix pages from different room versions in one planner input.
        while data.messages and data.messages[-1].sequence < data.transcript_cursor:
            page = await self.room.query(Query(request_id="supervisor-page", context=context,
                                               room_id=room_id, operation="list_messages",
                                               after_sequence=data.messages[-1].sequence, limit=500))
            if isinstance(page, Failure):
                raise SupervisorError(page.error.code)
            require(page.data.room_version == data.room_version, "STALE_VERSION")
            require(bool(page.data.messages), "incomplete_transcript")
            data.messages.extend(page.data.messages)
        return data

    async def dispatch(self, action: Action) -> dict:
        command = Command.model_validate(action.wire)
        require(command.payload.operation == action.operation, "action_operation_mismatch")
        return (await self.room.execute(command)).model_dump(mode="json")

    async def terminal(self, action: Action) -> dict:
        # Only accepted operations are known to exist. Exact replay retrieves the
        # operation record before the room-version check; idle query is NOT proof.
        require(action.status == "accepted", "reconciliation_required")
        return await self.dispatch(action)
