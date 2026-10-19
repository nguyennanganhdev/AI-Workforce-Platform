# -*- coding: utf-8 -*-
# pylint: disable=protected-access
"""Unit tests for :class:`TeamMemberLoopMiddleware`.

The middleware is exercised against a real :class:`Agent` driven by a
mock model and a stand-in ``TeamSay`` tool, so the reasoning-acting
loop is genuine while nothing touches the app service layer.
"""

import itertools
import json
from typing import Any
from unittest.async_case import IsolatedAsyncioTestCase

from utils import MockModel

from agentscope.agent import Agent, InjectionConfig, ReActConfig
from agentscope.app._tool._team_say import STALE_CONTEXT_RESULT
from agentscope.app.middleware import TeamMemberLoopMiddleware
from agentscope.event import ReplyEndEvent, TextBlockDeltaEvent, ToolResultTextDeltaEvent
from agentscope.message import TextBlock, ToolCallBlock, ToolResultState, UserMsg
from agentscope.model import ChatResponse
from agentscope.permission import (
    PermissionBehavior,
    PermissionContext,
    PermissionDecision,
)
from agentscope.tool import ToolBase, ToolChunk, Toolkit
from agentscope.types import ReplyFinishedReason


class _FakeTeamSay(ToolBase):
    """Stand-in for the real ``TeamSay`` — records calls, never fails."""

    name: str = "TeamSay"
    description: str = "Report to the team leader."
    input_schema: dict = {
        "type": "object",
        "properties": {
            "to": {"type": "string"},
            "content": {"type": "string"},
            "kind": {"type": "string"},
        },
        "required": ["content"],
    }
    is_concurrency_safe: bool = True
    is_read_only: bool = True
    is_state_injected: bool = False
    is_external_tool: bool = False
    is_mcp: bool = False
    mcp_name: str | None = None

    def __init__(
        self,
        state: ToolResultState = ToolResultState.SUCCESS,
        output: str = "delivered",
    ):
        super().__init__()
        self.calls: list[dict] = []
        self._state = state
        self._output = output
        self.metadata = {}

    async def check_permissions(
        self,
        tool_input: dict[str, Any],
        context: PermissionContext,
    ) -> PermissionDecision:
        """Always allow."""
        return PermissionDecision(
            behavior=PermissionBehavior.ALLOW,
            message="allowed",
        )

    async def __call__(
        self, content: str, to: str | None = None, kind: str | None = None
    ) -> ToolChunk:
        """Record the call and answer with the configured state."""
        self.calls.append({"to": to, "content": content})
        if kind:
            self.calls[-1]["kind"] = kind
        return ToolChunk(
            content=[TextBlock(text=self._output)],
            state=self._state,
            metadata=self.metadata,
        )


class _OtherTool(_FakeTeamSay):
    """A non-``TeamSay`` tool, used to invalidate an earlier report."""

    name: str = "Note"
    description: str = "Write a note."

    async def __call__(self, content: str, to: str | None = None) -> ToolChunk:
        """Answer successfully without reporting anywhere."""
        self.calls.append({"to": to, "content": content})
        return ToolChunk(content=[TextBlock(text="noted")])


def _text(text: str) -> ChatResponse:
    """A plain text reply — ends the reasoning-acting loop."""
    return ChatResponse(content=[TextBlock(text=text)], is_last=True)


_CALL_SEQ = itertools.count()


def _call(tool: str, **kwargs: Any) -> ChatResponse:
    """A single tool call reply; ``input`` is the raw JSON string."""
    return ChatResponse(
        content=[
            ToolCallBlock(
                type="tool_call",
                id=f"call-{tool}-{next(_CALL_SEQ)}",
                name=tool,
                input=json.dumps(kwargs),
            ),
        ],
        is_last=True,
    )


class TeamMemberLoopMiddlewareTest(IsolatedAsyncioTestCase):
    """The nudge / release / give-up decisions of the middleware."""

    async def asyncSetUp(self) -> None:
        """Build a worker agent wired to the middleware."""
        self.model = MockModel()
        self.team_say = _FakeTeamSay()
        self.extra_tools: list = []

    async def _run(
        self,
        responses: list,
        *,
        max_iters: int = 5,
        max_nudges: int = 3,
        extra_tools: list | None = None,
        pending_question=None,
    ) -> list:
        """Drive one reply and return the streamed items."""
        toolkit = Toolkit(tools=[self.team_say, *(extra_tools or [])])
        self.model.set_responses(responses)
        agent = Agent(
            name="worker",
            system_prompt="You are a worker.",
            model=self.model,
            toolkit=toolkit,
            react_config=ReActConfig(max_iters=max_iters),
            middlewares=[
                TeamMemberLoopMiddleware(
                    leader_name="Leader",
                    max_nudges=max_nudges,
                    pending_question=pending_question,
                ),
            ],
            injection_config=InjectionConfig(inject_runtime_state=False),
        )
        items = []
        async for item in agent.reply_stream(UserMsg("user", "do it")):
            items.append(item)
        return items

    async def test_waiting_for_user_never_calls_model_or_tools(self):
        async def question():
            return "Which location?"

        items = await self._run([], pending_question=question)
        self.assertEqual(self.model.cnt, 0)
        self.assertEqual(self.team_say.calls, [])
        self.assertEqual(
            self._end_events(items)[0].finished_reason, ReplyFinishedReason.COMPLETED
        )

    async def test_personal_result_is_streamed_once_without_another_model_call(self):
        answer = "No matching options were returned."
        self.team_say.metadata = {"kind": "result", "customer_reply": answer}
        items = await self._run([_call("TeamSay", kind="result", content=answer)])
        public = "".join(item.delta for item in items if isinstance(item, TextBlockDeltaEvent))
        self.assertEqual(answer, public)
        self.assertEqual(1, self.model.cnt)
        self.assertEqual(1, len(self._end_events(items)))

    async def test_progress_is_not_a_terminal_report(self):
        items = await self._run(
            [
                _call("TeamSay", to="Leader", kind="progress", content="Checking"),
                _text("Please wait"),
                _call(
                    "TeamSay",
                    to="Peer",
                    kind="question",
                    content="Return the verified options",
                ),
                _text("Waiting for peer"),
            ]
        )
        self.assertEqual(2, len(self.team_say.calls))
        self.assertEqual("Peer", self.team_say.calls[-1]["to"])
        self.assertEqual(
            ReplyFinishedReason.COMPLETED, self._end_events(items)[0].finished_reason
        )

    async def test_unchanged_repeated_tool_is_not_executed_again(self):
        tool = _OtherTool()
        tool.name = "mcp__test__lookup"
        items = await self._run(
            [
                _call(tool.name, content="same"),
                _call(tool.name, content="same"),
                _call(tool.name, content="same"),
                _call(tool.name, content="same"),  # even a model ignoring tool_choice
                _call("TeamSay", to="Leader", content="No matching external ID"),
                _text("reported"),
            ],
            extra_tools=[tool],
            max_iters=10,
        )
        self.assertEqual(len(tool.calls), 3)
        self.assertEqual(
            self._end_events(items)[0].finished_reason, ReplyFinishedReason.COMPLETED
        )

    @staticmethod
    def _end_events(items: list) -> list[ReplyEndEvent]:
        """The reply-end events that escaped the middleware."""
        return [_ for _ in items if isinstance(_, ReplyEndEvent)]

    async def test_successful_report_passes_through(self) -> None:
        """A final successful ``TeamSay`` to the leader ends the reply."""
        items = await self._run(
            [
                _call("TeamSay", to="Leader", content="done"),
                _text("reported"),
            ],
        )
        ends = self._end_events(items)
        self.assertDictEqual(
            {
                "model_calls": self.model.cnt,
                "reasons": [_.finished_reason for _ in ends],
                "team_say_calls": self.team_say.calls,
            },
            {
                "model_calls": 1,
                "reasons": [ReplyFinishedReason.COMPLETED],
                "team_say_calls": [{"to": "Leader", "content": "done"}],
            },
        )

    async def test_untargeted_result_is_a_routed_report(self) -> None:
        """Workers omit ``to`` for results; the runtime routes them to the
        reply owner, so a successful untargeted result ends the reply."""
        items = await self._run(
            [
                _call("TeamSay", kind="result", content="done"),
                _text("reported"),
            ],
        )
        self.assertListEqual(
            [_.finished_reason for _ in self._end_events(items)],
            [ReplyFinishedReason.COMPLETED],
        )
        self.assertListEqual(
            self.team_say.calls,
            [{"to": None, "kind": "result", "content": "done"}],
        )

    async def test_report_to_other_member_is_not_accepted(self) -> None:
        """A report addressed to another worker does not end the reply."""
        items = await self._run(
            [
                _call("TeamSay", to="OtherWorker", content="fyi"),
                _text("done"),
                _call("TeamSay", to="Leader", content="done"),
                _text("reported"),
            ],
        )
        self.assertListEqual(
            [_.finished_reason for _ in self._end_events(items)],
            [ReplyFinishedReason.COMPLETED],
        )
        self.assertListEqual(
            self.team_say.calls,
            [
                {"to": "OtherWorker", "content": "fyi"},
                {"to": "Leader", "content": "done"},
            ],
        )

    async def test_failed_report_is_not_accepted(self) -> None:
        """A ``TeamSay`` that errored does not count as a report."""
        self.team_say = _FakeTeamSay(state=ToolResultState.ERROR)
        items = await self._run(
            [
                _call("TeamSay", to="Leader", content="done"),
                _text("done"),
                _text("still not reporting"),
                _text("nor now"),
                _text("nor now either"),
            ],
            max_nudges=2,
        )
        ends = self._end_events(items)
        self.assertListEqual(
            [_.finished_reason for _ in ends],
            [ReplyFinishedReason.ERROR],
        )

    async def test_stale_report_stops_turn_instead_of_repeating_it(self) -> None:
        """A fresh run must reload shared context before another TeamSay."""

        self.team_say = _FakeTeamSay(
            state=ToolResultState.ERROR,
            output=STALE_CONTEXT_RESULT,
        )
        items = await self._run(
            [
                _call("TeamSay", to="Leader", content="stale answer"),
                _text("retry the same stale answer"),
                _call("TeamSay", to="Leader", content="must not run"),
            ],
        )
        ends = self._end_events(items)

        self.assertEqual(self.model.cnt, 2)
        self.assertEqual(len(self.team_say.calls), 1)
        self.assertEqual(ends[-1].finished_reason, ReplyFinishedReason.ERROR)
        self.assertIn("fresh worker turn", ends[-1].error.message)

    async def test_silent_worker_is_failed_after_max_nudges(self) -> None:
        """A worker that never reports fails instead of looping."""
        items = await self._run(
            [_text(f"turn {i}") for i in range(10)],
            max_nudges=2,
        )
        ends = self._end_events(items)
        self.assertDictEqual(
            {
                "reasons": [_.finished_reason for _ in ends],
                "error_type": ends[-1].error.type if ends[-1].error else None,
                "team_say_calls": self.team_say.calls,
                # 1 initial reply + 2 nudged retries, then give up
                "model_calls": self.model.cnt,
            },
            {
                "reasons": [ReplyFinishedReason.ERROR],
                "error_type": "internal",
                "team_say_calls": [],
                "model_calls": 3,
            },
        )

    async def test_exceed_max_iters_is_nudged_then_failed(self) -> None:
        """The EXCEED ending is nudged too, and also bounded."""
        note = _OtherTool()
        items = await self._run(
            [_call("Note", content=f"n{i}") for i in range(10)],
            max_iters=2,
            max_nudges=1,
            extra_tools=[note],
        )
        self.assertListEqual(
            [_.finished_reason for _ in self._end_events(items)],
            [ReplyFinishedReason.ERROR],
        )

    async def test_completed_on_the_last_iteration_does_not_raise(
        self,
    ) -> None:
        """A COMPLETED ending exactly at ``max_iters`` must not trip the
        agent's swallow-without-progress guard.

        Without freeing an iteration the next decision would be
        EXCEED_MAX_ITERS with no reasoning in between, and swallowing
        that raises inside the agent.
        """
        items = await self._run(
            [
                _text("done early"),
                _call("TeamSay", to="Leader", content="done"),
                _text("reported"),
            ],
            max_iters=1,
        )
        self.assertDictEqual(
            {
                "reasons": [_.finished_reason for _ in self._end_events(items)],
                "team_say_calls": self.team_say.calls,
            },
            {
                # The nudged round spends the freed iteration, so the
                # released ending is the EXCEED one.
                "reasons": [ReplyFinishedReason.EXCEED_MAX_ITERS],
                "team_say_calls": [{"to": "Leader", "content": "done"}],
            },
        )

    async def test_registered_customer_question_is_emitted_without_model_text(
        self,
    ) -> None:
        items = await self._run(
            [
                _call(
                    "TeamSay",
                    to="null",
                    kind="requires_user_input",
                    content="Bạn xuất phát từ đâu và có bao nhiêu người?",
                ),
                _text("Đã đăng ký câu hỏi."),
            ],
        )

        self.assertIn(
            "Bạn xuất phát từ đâu và có bao nhiêu người?",
            [item.delta for item in items if isinstance(item, TextBlockDeltaEvent)],
        )
        self.assertEqual(
            ReplyFinishedReason.COMPLETED,
            self._end_events(items)[0].finished_reason,
        )

    async def test_partial_peer_batch_ends_without_retrying_or_losing_requests(self):
        class _PartialTeamSay(_FakeTeamSay):
            async def __call__(self, content, to=None, kind=None):
                result = await super().__call__(content, to, kind)
                if to == "Missing":
                    result.state = ToolResultState.ERROR
                return result

        self.team_say = _PartialTeamSay()
        batch = ChatResponse(content=[
            *_call("TeamSay", to="Peer", kind="question", content="Find options").content,
            *_call("TeamSay", to="Missing", kind="question", content="Find alternatives").content,
        ], is_last=True)
        items = await self._run([batch, _text("should not run")])
        self.assertEqual(self.model.cnt, 1)
        self.assertEqual(len(self.team_say.calls), 2)
        self.assertEqual(self._end_events(items)[0].finished_reason, ReplyFinishedReason.COMPLETED)

    async def test_successful_report_prevents_another_model_round(self) -> None:
        """A successful report releases the run before another tool is planned."""
        note = _OtherTool()
        items = await self._run(
            [
                _call("TeamSay", to="Leader", content="done"),
                _call("Note", content="afterthought"),
                _text("finished"),
                _call("TeamSay", to="Leader", content="really done"),
                _text("reported"),
            ],
            extra_tools=[note],
        )
        self.assertListEqual(
            [_.finished_reason for _ in self._end_events(items)],
            [ReplyFinishedReason.COMPLETED],
        )
        self.assertEqual(len(self.team_say.calls), 1)
        self.assertEqual(self.model.cnt, 1)

    async def test_explicit_peer_answer_result_and_error_end_without_leader_report(self):
        for kind in ("answer", "result", "error"):
            with self.subTest(kind=kind):
                self.team_say = _FakeTeamSay()
                await self._run([
                    _call("TeamSay", to="Peer", kind=kind, content="Bounded response"),
                    _call("TeamSay", to="Leader", content="Must not repeat the peer report"),
                ])
                self.assertEqual(len(self.team_say.calls), 1)
                self.assertEqual(self.team_say.calls[0]["to"], "Peer")

    async def test_pause_during_model_call_streams_the_tool_blocker(self):
        checks = 0

        async def question():
            nonlocal checks
            checks += 1
            return None if checks == 1 else "awaiting_user_input"

        items = await self._run(
            [_call("TeamSay", to="Peer", kind="question", content="Find options")],
            pending_question=question,
        )
        self.assertEqual([], self.team_say.calls)
        self.assertTrue(any(
            "waiting for customer input" in str(event.delta)
            for event in items if isinstance(event, ToolResultTextDeltaEvent)
        ))
