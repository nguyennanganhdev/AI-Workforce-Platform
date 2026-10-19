"""Members hand work and results to each other without a Leader relay.

Scripted storage and bus only; no model or provider calls.
"""
import json
import os
from types import SimpleNamespace
from unittest import IsolatedAsyncioTestCase
from unittest.mock import patch

from agentscope.app._tool import TeamSay
from agentscope.app.storage._model._team import TeamData, direct_routing_default
from tests import team_collaboration_test as collaboration


class _Base(IsolatedAsyncioTestCase):
    tool = collaboration.TestCollaboration.tool
    say = collaboration.TestCollaboration.say
    branch = collaboration.TestCollaboration.branch
    mode = "collaborative"

    async def asyncSetUp(self):
        await collaboration.TestCollaboration.asyncSetUp(self)
        self.storage.team.data = self.storage.team.data.model_copy(
            update={
                "collaboration_mode": "peer" if self.mode == "peer" else "reviewed",
                "direct_member_routing": self.mode == "collaborative",
            }
        )

    def recipients(self, result):
        handoff_id = result.metadata["handoff_id"]
        return {
            h.recipient_session_id
            for h in self.storage.handoffs.values()
            if h.handoff_id == handoff_id
        }


class TestCollaborativeTeam(_Base):
    async def test_worker_hands_part_to_peer_and_result_returns_without_leader(self):
        handoff = await self.say(
            "worker", kind="handoff", to="Peer",
            content="Look up the available options for the customer's dates",
        )
        self.assertEqual({"peer-session"}, self.recipients(handoff))
        self.assertEqual(
            "waiting_peer",
            await self.service.collaboration_pause("u", "ticket-1", "worker-session"),
        )
        ledger = self.storage.context.state.tasks[self.task].assignments
        self.assertIn("peer-session", ledger)

        # The peer omits ``to``: its result goes back to the worker that
        # handed the part over, and the Leader gets no copy.
        result = await self.say("peer", kind="result", content="No matching options were returned.")
        self.assertEqual({"worker-session"}, self.recipients(result))
        self.assertIsNone(
            await self.service.collaboration_pause("u", "ticket-1", "worker-session")
        )

        # The worker then reports its own assignment to the Leader.
        final = await self.say("worker", kind="result", content="No matching options were returned.")
        self.assertEqual({"leader-session"}, self.recipients(final))

    async def test_result_with_teammate_recipient_skips_leader_but_counts_as_done(self):
        result = await self.say(
            "worker", kind="result", to="Peer",
            content="No matching options were returned.",
        )
        self.assertEqual({"peer-session"}, self.recipients(result))
        completed, errors, _facts, _waiting = await self.service.team_evidence_status(
            "u", "ticket-1", leader_session_id="leader-session",
        )
        self.assertEqual((1, 0), (completed, errors))

    async def test_error_still_reaches_the_leader(self):
        error = await self.say("worker", kind="error", content="The lookup tool is unavailable.")
        self.assertIn("leader-session", self.recipients(error))

    async def test_handoff_needs_a_teammate_not_the_leader(self):
        to_leader = await self.tool("worker")(kind="handoff", to="Leader", content="Finish this")
        self.assertEqual("error", to_leader.state)
        missing = await self.tool("worker")(kind="handoff", content="Finish this")
        self.assertEqual("error", missing.state)
        unknown = await self.tool("worker")(kind="handoff", to="Nobody", content="Finish this")
        self.assertEqual("error", unknown.state)

    async def test_worker_cannot_resolve_with_a_handoff(self):
        result = await self.tool("worker")(
            kind="handoff", to="Peer", content="Done", resolution="complete",
        )
        self.assertEqual("error", result.state)

    async def test_handoff_entry_names_the_teammate(self):
        await self.say("worker", kind="handoff", to="Peer", content="Look up options")
        entry = self.storage.context.state.tasks[self.task].assignments["peer-session"]
        self.assertEqual(("peer", "Peer", "worker-session"),
                         (entry.agent_id, entry.agent_name, entry.assigned_by))

    async def test_worker_with_two_jobs_must_name_the_recipient(self):
        from agentscope.app.storage._model._team_context import TaskAssignment
        await self.service.record_assignments(
            "u", "ticket-1", {"peer-session": TaskAssignment(goal="Own Leader task")},
        )
        await self.say("worker", kind="handoff", to="Peer", content="Look up options")
        ambiguous = await self.tool("peer")(kind="result", content="No matching options were returned.")
        self.assertEqual("error", ambiguous.state)
        explicit = await self.say(
            "peer", kind="result", to="Worker", content="No matching options were returned.",
        )
        self.assertEqual({"worker-session"}, self.recipients(explicit))

    async def test_rollback_switch_turns_off_existing_collaborative_team(self):
        with patch.dict(os.environ, {"WORKFORCE_TEAM_COLLABORATION": "reviewed"}):
            handoff = await self.tool("worker")(kind="handoff", to="Peer", content="Look up options")
            self.assertEqual("error", handoff.state)
            result = await self.say(
                "worker", kind="result", to="Peer", content="No matching options were returned.",
            )
            self.assertEqual({"peer-session", "leader-session"}, self.recipients(result))

    async def test_peer_question_and_answer_are_unchanged(self):
        question = await self.say("worker", kind="question", to="Peer", content="Provide the price")
        answer = await self.say("peer", kind="answer", content="The price was not returned")
        self.assertEqual({"worker-session"}, self.recipients(answer))
        self.assertEqual(question.metadata["handoff_id"], next(
            e.in_reply_to for e in self.storage.context.state.events
            if e.id == answer.metadata["handoff_id"]
        ))


class TestReviewedTeam(_Base):
    mode = "reviewed"

    async def test_handoff_between_members_is_rejected(self):
        result = await self.tool("worker")(kind="handoff", to="Peer", content="Look up options")
        self.assertEqual("error", result.state)
        self.assertIn("kind='question'", result.content[0].text)

    async def test_result_to_a_teammate_still_copies_the_leader(self):
        result = await self.say(
            "worker", kind="result", to="Peer",
            content="No matching options were returned.",
        )
        self.assertEqual({"peer-session", "leader-session"}, self.recipients(result))


class TestPeerTeam(_Base):
    mode = "peer"

    async def test_handed_part_returns_to_teammate_not_the_customer(self):
        await self.say("worker", kind="handoff", to="Peer", content="Look up options")
        result = await self.say("peer", kind="result", content="No matching options were returned.")
        self.assertNotIn("customer_reply", result.metadata)
        self.assertEqual({"worker-session"}, self.recipients(result))


class TestWorkerToolSurface(IsolatedAsyncioTestCase):
    def _tool(self, **kwargs):
        return TeamSay(
            storage=object(), message_bus=object(), workspace_manager=object(),
            user_id="u", session_id="s", agent_id="a", role="worker", **kwargs,
        )

    def test_direct_team_shows_handoff_and_recipient_for_results(self):
        tool = self._tool(direct_collaboration=True)
        self.assertIn("handoff", tool.input_schema["properties"]["kind"]["enum"])
        self.assertIn("Optional for result", tool.input_schema["properties"]["to"]["description"])

    def test_reviewed_team_keeps_the_question_only_surface(self):
        tool = self._tool()
        self.assertNotIn("handoff", tool.input_schema["properties"]["kind"]["enum"])


class TestDefaultMode(IsolatedAsyncioTestCase):
    def test_new_teams_collaborate_unless_reviewed_is_configured(self):
        with patch.dict(os.environ, {"WORKFORCE_TEAM_COLLABORATION": ""}):
            self.assertTrue(direct_routing_default())
        with patch.dict(os.environ, {"WORKFORCE_TEAM_COLLABORATION": "reviewed"}):
            self.assertFalse(direct_routing_default())

    def test_an_older_release_can_read_a_collaborative_team(self):
        from typing import Literal

        from pydantic import BaseModel

        class OldTeamData(BaseModel):
            name: str
            collaboration_mode: Literal["reviewed", "peer"] = "reviewed"

        stored = TeamData(name="Room", direct_member_routing=True).model_dump(mode="json")
        self.assertEqual("reviewed", OldTeamData.model_validate(stored).collaboration_mode)


class TestHandedPartIsNotOwnWork(_Base):
    async def asyncSetUp(self):
        await super().asyncSetUp()
        from agentscope.app.storage._model._team_context import TaskAssignment
        await self.service.record_assignments("u", "ticket-1", {
            "peer-session": TaskAssignment(goal="Own Leader task"),
            "worker-session": TaskAssignment(goal="Worker Leader task"),
        })

    async def test_returning_a_handed_part_keeps_own_assignment_open(self):
        await self.say("worker", kind="handoff", to="Peer", content="Look up options")
        await self.say("peer", kind="result", to="Worker", content="No matching options were returned.")
        ledger = self.storage.context.state.tasks[self.task].assignments
        self.assertEqual("assigned", ledger["peer-session"].status)
        self.assertNotIn(self.branch("peer").status, {"review", "completed"})
        pending = await self.service.collaboration_review("u", "ticket-1", "leader-session", working_only=True)
        self.assertIn("peer-session", pending)
        completed, _errors, _facts, _waiting = await self.service.team_evidence_status(
            "u", "ticket-1", leader_session_id="leader-session",
        )
        self.assertEqual(0, completed)

    async def test_own_result_still_counts_afterwards(self):
        await self.say("worker", kind="handoff", to="Peer", content="Look up options")
        await self.say("peer", kind="result", to="Worker", content="No matching options were returned.")
        await self.say("peer", kind="result", content="My own task found no matching options.")
        ledger = self.storage.context.state.tasks[self.task].assignments
        self.assertEqual("reported", ledger["peer-session"].status)


class TestLeaderDoesNotPoll(_Base):
    """19/10 incident: a peer Leader sent 7 reminders in 15 s, accepted work
    that was never done, and the member was put to sleep without running."""

    mode = "peer"

    async def asyncSetUp(self):
        await super().asyncSetUp()
        from agentscope.app.storage._model._team_context import TaskAssignment
        await self.service.record_assignments("u", "ticket-1", {"peer-session": TaskAssignment(goal="Find bus trips")})

    async def test_reminder_to_a_working_member_is_refused(self):
        reminder = await self.tool("leader")(kind="handoff", to="Peer", content="Any update on the bus trips?")
        self.assertEqual("error", reminder.state)
        self.assertIn("end your turn", reminder.content[0].text)
        self.assertEqual("assigned", self.storage.context.state.tasks[self.task].assignments["peer-session"].status)

    async def test_unreported_work_cannot_be_accepted(self):
        accept = await self.tool("leader")(kind="review", to="Peer", decision="accept", content="Looks done")
        self.assertEqual("error", accept.state)
        self.assertNotEqual("completed", self.storage.context.state.tasks[self.task].collaboration.get(
            "peer-session", SimpleNamespace(status="running")).status)

    async def test_reported_work_can_be_accepted_and_followed_up(self):
        await self.say("peer", kind="result", to="Leader", content="No bus trips were returned for that date.")
        await self.say("leader", kind="review", to="Peer", decision="accept", content="Accepted")
        await self.say("leader", kind="handoff", to="Peer", content="Now check the next day as well.")

    async def test_a_new_customer_message_allows_a_new_handoff(self):
        await self.service.append_event(user_id="u", team_id="ticket-1", kind="customer_message",
                                        content="Actually make it 3 passengers", event_id="customer-2")
        await self.say("leader", kind="handoff", to="Peer", content="Redo the search for 3 passengers.")


class TestPeerLeaderStopsAfterDispatch(_Base):
    mode = "peer"

    async def test_leader_answers_without_tools_after_a_handoff(self):
        from agentscope.agent import Agent, InjectionConfig, ReActConfig
        from agentscope.app.middleware._peer_leader_middleware import (
            PeerLeaderDispatchMiddleware,
        )
        from agentscope.message import TextBlock, ToolCallBlock, UserMsg
        from agentscope.model import ChatResponse
        from agentscope.tool import Toolkit
        from tests.utils import MockModel

        seen = []

        class Recording(MockModel):
            async def _call_api(self, *args, **kwargs):
                seen.append(kwargs.get("tool_choice"))
                return await super()._call_api(*args, **kwargs)

        model = Recording()
        model.set_responses([
            ChatResponse(content=[ToolCallBlock(id="h", name="TeamSay", input=json.dumps(
                {"kind": "handoff", "to": "Peer", "content": "Find bus trips Hanoi to Da Nang on 20/10 for 2"}))], is_last=True),
            ChatResponse(content=[TextBlock(text="Peer is handling it; the answer will appear here.")], is_last=True),
        ])
        agent = Agent(name="Leader", system_prompt="Lead", model=model,
                      toolkit=Toolkit(tools=[self.tool("leader")]), react_config=ReActConfig(max_iters=6),
                      middlewares=[PeerLeaderDispatchMiddleware()],
                      injection_config=InjectionConfig(inject_runtime_state=False))
        async for _ in agent.reply_stream(UserMsg("user", "Bus from Hanoi to Da Nang on 20/10 for 2")):
            pass
        self.assertEqual(2, model.cnt)
        self.assertEqual("none", getattr(seen[-1], "mode", None))
