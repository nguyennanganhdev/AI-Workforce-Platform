from groupchat.models import (
    Command,
    MentionAgent,
    MessageInput,
    OpenRoom,
    ParticipantSpec,
    PutTask,
    RunTurn,
    TurnPolicy,
    new_id,
)
from groupchat.room import RoomService

from support.fakes import FakeAgents, FakeResolver, make_context
from support.state_fake import InMemoryState


class Harness:
    def __init__(self):
        self.resolver, self.agents, self.state = (
            FakeResolver(),
            FakeAgents(),
            InMemoryState(),
        )
        self.service = RoomService(self.resolver, self.agents, self.state)
        self.ctx = make_context()

    def command(self, payload, key=None, context=None):
        return Command(
            request_id=new_id(),
            trace_id=new_id(),
            idempotency_key=key or new_id(),
            context=context or self.ctx,
            payload=payload,
        )

    async def open(self, context=None, policy=None):
        command = self.command(
            OpenRoom(
                groupchat_version_id="test-group-v1",
                participants=[
                    ParticipantSpec(agent_version_id=x, role="advisor")
                    for x in ("A-v1", "B-v1")
                ],
                turn_policy=policy or TurnPolicy(),
                initial_message=MessageInput(content="Phân tích ticket"),
            ),
            context=context,
        )
        return command, await self.service.execute(command)

    def turn(self, data, speaker="A-v1", key=None, context=None):
        return self.command(
            RunTurn(
                room_id=data.room_id,
                expected_room_version=data.room_version,
                turn_id=new_id(),
                task_id="backend-task",
                correlation_id="backend-correlation",
                speaker_agent_version_id=speaker,
                instruction="Đề xuất bước tiếp theo",
            ),
            key,
            context,
        )


def room_args(data):
    """Lấy định danh và phiên bản phòng cho lệnh tiếp theo."""
    return {"room_id": data.room_id, "expected_room_version": data.room_version}


def mention(harness, data, agent="B", **kwargs):
    return harness.command(
        MentionAgent(
            **room_args(data),
            mentioned_agent_id=agent,
            instruction="Hỏi trực tiếp",
            **kwargs,
        )
    )


async def put(harness, data, task):
    result = await harness.service.execute(
        harness.command(PutTask(**room_args(data), task=task))
    )
    assert result.status == "completed", result
    return result.data
