"""Personal team collaboration without a mandatory Leader relay (no model calls)."""
from unittest import IsolatedAsyncioTestCase
from tests import team_collaboration_test as collaboration


class TestPersonalTeam(IsolatedAsyncioTestCase):
    tool = collaboration.TestCollaboration.tool
    say = collaboration.TestCollaboration.say
    branch = collaboration.TestCollaboration.branch

    async def asyncSetUp(self):
        await collaboration.TestCollaboration.asyncSetUp(self)
        self.storage.team.data = self.storage.team.data.model_copy(
            update={"collaboration_mode": "peer"}
        )

    async def test_member_publishes_result_without_waking_leader(self):
        result = await self.say("worker", kind="result", content="No matching options were returned.")
        self.assertEqual("No matching options were returned.", result.metadata.get("customer_reply"))
        self.assertFalse(any(h.recipient_session_id == "leader-session"
                             and not h.payload.get("collaboration_intent")
                             for h in self.storage.handoffs.values()))

    async def test_specialist_resumes_and_publishes_after_customer_question(self):
        from agentscope.app._team_turn import start_team_turn
        await self.say("worker", kind="requires_user_input", content="Which option do you choose?", question_key="choice")
        self.assertEqual("worker-session", self.storage.turn.reply_owner_session_id)
        blocked = await self.tool("worker")(kind="result", content="No matching options were returned.")
        self.assertEqual("error", blocked.state)
        await start_team_turn(self.bus, "ticket-1", reply_owner_session_id="worker-session",
            reply_owner_agent_id="worker", customer_session_id="leader-session", mode="specialist_question",
            task_id=self.task, storage=self.storage, user_id="u")
        result = await self.say("worker", kind="result", content="No matching options were returned.")
        self.assertEqual("No matching options were returned.", result.metadata.get("customer_reply"))
        self.assertEqual("worker-session", self.storage.turn.reply_owner_session_id)

    async def test_peer_answer_remains_internal(self):
        question = await self.say("worker", kind="question", to="Peer", content="Look up the available options")
        answer = await self.say("peer", kind="answer", to="Worker", content="No matching options were returned.", in_reply_to=question.metadata["handoff_id"])
        self.assertNotIn("customer_reply", answer.metadata)

    async def test_member_cannot_publish_while_waiting_for_peer(self):
        await self.say("worker", kind="question", to="Peer", content="Look up the available options")
        result = await self.tool("worker")(kind="result", content="No matching options were returned.")
        self.assertEqual("error", result.state)

    async def test_member_cannot_publish_invented_price(self):
        result = await self.tool("worker")(kind="result", content="Hotel Aurora costs 900000 VND per night.")
        self.assertEqual("error", result.state)
