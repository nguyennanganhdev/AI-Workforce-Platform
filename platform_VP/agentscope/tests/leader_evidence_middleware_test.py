"""Runtime evidence-gate tests for the fixed Workforce Leader."""

import json
from types import SimpleNamespace
from unittest import IsolatedAsyncioTestCase
from unittest.mock import AsyncMock, patch

from agentscope.agent import ReActConfig
from agentscope.app.middleware import LeaderEvidenceMiddleware
from agentscope.event import (
    ReplyEndEvent,
    TextBlockDeltaEvent,
    TextBlockEndEvent,
    TextBlockStartEvent,
)
from agentscope.message import ToolCallBlock, ToolResultBlock, ToolResultState
from agentscope.state import AgentState


class _Storage:
    async def get_session(self, user_id: str, agent_id: str, session_id: str):
        del user_id, agent_id, session_id
        return SimpleNamespace(team_id="team-1", state=AgentState(), id="session-1")

    async def get_team(self, user_id, team_id):
        return None


class _SharedContext:
    def __init__(self, status: tuple[int, int, int, bool]) -> None:
        self.status = status

    async def team_evidence_status(self, *args, **kwargs):
        del args, kwargs
        return self.status


def _text_round(reply_id: str, block_id: str, text: str):
    yield TextBlockStartEvent(reply_id=reply_id, block_id=block_id)
    yield TextBlockDeltaEvent(
        reply_id=reply_id,
        block_id=block_id,
        delta=text,
    )
    yield TextBlockEndEvent(reply_id=reply_id, block_id=block_id)
    yield ReplyEndEvent(session_id="session-1", reply_id=reply_id)


class TestLeaderEvidenceMiddleware(IsolatedAsyncioTestCase):
    async def test_pending_consent_parks_without_evidence_failure(self) -> None:
        middleware = LeaderEvidenceMiddleware(
            _Storage(),
            _SharedContext((0, 0, 0, False)),
            "user-1",
            "leader-agent",
            "session-1",
            wait_seconds=0,
        )
        agent = self._agent(dispatched=True)

        async def next_handler(**kwargs):
            for event in _text_round("reply-1", "placeholder", "Waiting for booking"):
                yield event

        with patch.object(middleware, "_pending_consent", AsyncMock(return_value=True)):
            output = [
                event async for event in middleware.on_reply(agent, {}, next_handler)
            ]

        self.assertEqual(len(output), 1)
        self.assertIsInstance(output[0], ReplyEndEvent)
        self.assertIsNone(output[0].error)
        self.assertFalse(
            any(message.get_content_blocks("hint") for message in agent.state.context)
        )

    def _agent(self, *, dispatched: bool) -> SimpleNamespace:
        state = AgentState(session_id="session-1")
        state.reply_id = "reply-1"
        if dispatched:
            state.append_context(
                "Leader",
                [
                    ToolCallBlock(
                        id="invite-1",
                        name="AgentInvite",
                        input=json.dumps(
                            {"target": "Hotel Agent@12345678", "prompt": "find"},
                        ),
                    ),
                    ToolResultBlock(
                        id="invite-1",
                        name="AgentInvite",
                        output="invited",
                        state=ToolResultState.SUCCESS,
                    ),
                ],
            )
        return SimpleNamespace(
            name="Leader",
            state=state,
            react_config=ReActConfig(max_iters=5),
        )

    async def test_delegation_placeholder_is_replaced_after_worker_result(
        self,
    ) -> None:
        middleware = LeaderEvidenceMiddleware(
            _Storage(),  # type: ignore[arg-type]
            _SharedContext((1, 0, 1, False)),  # type: ignore[arg-type]
            "user-1",
            "leader-agent",
            "session-1",
            wait_seconds=0,
        )
        agent = self._agent(dispatched=True)

        async def next_handler(**kwargs):
            del kwargs
            for event in _text_round(
                "reply-1",
                "before-evidence",
                "Tôi đã gửi yêu cầu và đang chờ.",
            ):
                yield event
            for event in _text_round(
                "reply-1",
                "after-evidence",
                "Khách sạn A còn phòng theo kết quả agent.",
            ):
                yield event

        output = [
            event
            async for event in middleware.on_reply(
                agent,  # type: ignore[arg-type]
                {},
                next_handler,
            )
        ]
        streamed = "".join(
            event.delta for event in output if isinstance(event, TextBlockDeltaEvent)
        )

        self.assertNotIn("đang chờ", streamed)
        self.assertIn("Khách sạn A", streamed)

    async def test_unsupported_factual_answer_is_replaced_by_clarification(
        self,
    ) -> None:
        middleware = LeaderEvidenceMiddleware(
            _Storage(),  # type: ignore[arg-type]
            _SharedContext((0, 0, 0, False)),  # type: ignore[arg-type]
            "user-1",
            "leader-agent",
            "session-1",
            wait_seconds=0,
        )
        agent = self._agent(dispatched=False)

        async def next_handler(**kwargs):
            del kwargs
            for event in _text_round(
                "reply-1",
                "invented",
                "Khách sạn A giá 2.000.000 VNĐ và còn phòng.",
            ):
                yield event
            for event in _text_round(
                "reply-1",
                "clarify",
                "Bạn muốn ở khu vực nào?",
            ):
                yield event

        output = [
            event
            async for event in middleware.on_reply(
                agent,  # type: ignore[arg-type]
                {},
                next_handler,
            )
        ]
        streamed = "".join(
            event.delta for event in output if isinstance(event, TextBlockDeltaEvent)
        )

        self.assertNotIn("2.000.000", streamed)
        self.assertEqual(streamed, "Bạn muốn ở khu vực nào?")
