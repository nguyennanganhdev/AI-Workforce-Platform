"""Task ledger, dependency release and the runtime-filled TeamSay surface."""

from unittest import IsolatedAsyncioTestCase

from agentscope.agent import ContextConfig, ReActConfig
from agentscope.app._shared_context import SharedContextService
from agentscope.app._tool import TeamSay
from agentscope.app.message_bus import InMemoryMessageBus, MessageBusKeys
from agentscope.app.storage import (
    AgentData,
    AgentRecord,
    SessionConfig,
    SessionRecord,
    TaskAssignment,
    TeamData,
    TeamHandoffRecord,
    TeamMember,
    TeamRecord,
    TeamSharedContextRecord,
    TeamTurnRecord,
)

WORKERS = ("hotel", "car", "cost")


def _agent(agent_id: str, name: str, source: str = "team") -> AgentRecord:
    return AgentRecord(
        id=agent_id,
        user_id="u",
        source=source,
        data=AgentData(
            name=name,
            context_config=ContextConfig(),
            react_config=ReActConfig(),
        ),
    )


class _Storage:
    def __init__(self) -> None:
        self.agents = {"leader": _agent("leader", "Leader", "user")}
        self.sessions = {
            "leader-session": SessionRecord(
                id="leader-session",
                user_id="u",
                agent_id="leader",
                team_id="ticket-1",
                config=SessionConfig(workspace_id="w"),
            ),
        }
        members = []
        for worker in WORKERS:
            self.agents[worker] = _agent(worker, worker.title())
            self.sessions[f"{worker}-session"] = SessionRecord(
                id=f"{worker}-session",
                user_id="u",
                agent_id=worker,
                team_id="ticket-1",
                config=SessionConfig(workspace_id="w"),
            )
            members.append(
                TeamMember(
                    owner_id="u",
                    agent_id=worker,
                    session_id=f"{worker}-session",
                    role="created",
                ),
            )
        self.team = TeamRecord(
            id="ticket-1",
            user_id="u",
            session_id="leader-session",
            leader_agent_id="leader",
            data=TeamData(name="Trip", members=members),
        )
        self.context: TeamSharedContextRecord | None = None
        self.turn: TeamTurnRecord | None = None
        self.handoffs: dict[str, TeamHandoffRecord] = {}

    async def get_session(self, _user, _agent, session):
        return self.sessions.get(session)

    async def get_team(self, _user, team):
        return self.team if team == self.team.id else None

    async def get_agent(self, _user, agent):
        return self.agents.get(agent)

    async def get_team_shared_context(self, _user, team):
        if self.context is None or self.context.team_id != team:
            return None
        return self.context.model_copy(deep=True)

    async def upsert_team_shared_context(self, _user, record):
        self.context = record.model_copy(deep=True)
        return record

    async def compare_and_swap_team_shared_context(self, _user, record, expected_revision):
        if (self.context.state.revision if self.context else 0) != expected_revision:
            return False
        self.context = record.model_copy(deep=True)
        return True

    async def get_team_turn(self, _user, _team):
        return self.turn.model_copy(deep=True) if self.turn else None

    async def upsert_team_turn(self, _user, record):
        self.turn = record.model_copy(deep=True)
        return record

    async def get_team_handoff(self, _user, record_id):
        value = self.handoffs.get(record_id)
        return value.model_copy(deep=True) if value else None

    async def upsert_team_handoff(self, _user, record):
        self.handoffs[record.id] = record.model_copy(deep=True)
        return record

    async def list_outstanding_team_handoffs(self, **_kwargs):
        return [value.model_copy(deep=True) for value in self.handoffs.values()]


class TaskLedgerTest(IsolatedAsyncioTestCase):
    async def asyncSetUp(self) -> None:
        self.storage = _Storage()
        self.bus = InMemoryMessageBus()
        self.shared = SharedContextService(self.storage, self.bus)  # type: ignore[arg-type]
        self.task_id = await self.shared.active_task_id("u", "ticket-1")

    def _tool(self, session: str, agent: str, role: str) -> TeamSay:
        return TeamSay(
            storage=self.storage,  # type: ignore[arg-type]
            message_bus=self.bus,
            workspace_manager=object(),
            user_id="u",
            session_id=session,
            agent_id=agent,
            shared_context_service=self.shared,
            role=role,
        )

    async def _inbox(self, session: str) -> list:
        return await self.bus.queue_drain(MessageBusKeys.inbox(session), max_count=20)

    async def _tool_fact(self, worker: str, content: str) -> None:
        await self.shared.append_event(
            user_id="u",
            team_id="ticket-1",
            kind="external_event",
            content=content,
            source_session_id=f"{worker}-session",
            source_agent_id=worker,
        )

    async def _ledger(self) -> dict[str, TaskAssignment]:
        record = await self.storage.get_team_shared_context("u", "ticket-1")
        return record.state.tasks[self.task_id].assignments

    async def test_untargeted_worker_result_reaches_leader_and_updates_ledger(self) -> None:
        await self.shared.record_assignments(
            "u",
            "ticket-1",
            {"hotel-session": TaskAssignment(agent_id="hotel", goal="Find hotels")},
        )
        await self._tool_fact("hotel", '{"name": "DEMO Song Han", "price_vnd": 1200000}')

        result = await self._tool("hotel-session", "hotel", "worker")(
            kind="result",
            content="DEMO Song Han 1200000 VND per night",
        )

        self.assertNotEqual("error", result.state, result.content)
        self.assertEqual(1, len(await self._inbox("leader-session")))
        self.assertEqual("reported", (await self._ledger())["hotel-session"].status)

    async def test_dependent_assignment_starts_when_its_dependency_reports(self) -> None:
        await self.shared.record_assignments(
            "u",
            "ticket-1",
            {
                "hotel-session": TaskAssignment(agent_id="hotel", goal="Find hotels"),
                "cost-session": TaskAssignment(
                    agent_id="cost",
                    agent_name="Cost",
                    goal="Total the trip",
                    depends_on=("hotel-session",),
                    status="queued",
                    pending_payload={"type": "hint", "hint": "Total the trip"},
                ),
            },
        )
        pending = await self.shared.collaboration_review("u", "ticket-1", "leader-session")
        self.assertIn("cost-session", pending)
        self.assertEqual([], await self._inbox("cost-session"))

        await self._tool_fact("hotel", '{"name": "DEMO Song Han", "price_vnd": 1200000}')
        await self._tool("hotel-session", "hotel", "worker")(
            kind="result",
            content="DEMO Song Han 1200000 VND per night",
        )

        released = await self._inbox("cost-session")
        self.assertEqual(1, len(released))
        self.assertEqual("assigned", (await self._ledger())["cost-session"].status)
        self.assertIsNone((await self._ledger())["cost-session"].pending_payload)

    async def test_failed_dependency_releases_waiter_with_missing_input_note(self) -> None:
        await self.shared.record_assignments(
            "u",
            "ticket-1",
            {
                "car-session": TaskAssignment(agent_id="car", agent_name="Car", goal="Find a car"),
                "cost-session": TaskAssignment(
                    agent_id="cost",
                    goal="Total the trip",
                    depends_on=("car-session",),
                    status="queued",
                    pending_payload={"type": "hint", "hint": "Total the trip"},
                ),
            },
        )
        await self._tool("car-session", "car", "worker")(
            kind="error",
            content="No car matches the route",
        )

        released = await self._inbox("cost-session")
        self.assertEqual(1, len(released))
        self.assertIn("did not deliver a result: Car", str(released[0]))
        self.assertEqual("failed", (await self._ledger())["car-session"].status)

    async def test_answer_without_target_returns_to_the_asker(self) -> None:
        asked = await self._tool("cost-session", "cost", "worker")(
            kind="question",
            to="Hotel",
            content="Which hotel price should I use?",
        )
        self.assertNotEqual("error", asked.state, asked.content)
        await self._inbox("hotel-session")

        await self._tool_fact("hotel", '{"name": "DEMO Song Han", "price_vnd": 1200000}')
        answer = await self._tool("hotel-session", "hotel", "worker")(
            kind="answer",
            content="DEMO Song Han 1200000 VND per night",
        )

        self.assertNotEqual("error", answer.state, answer.content)
        self.assertEqual(1, len(await self._inbox("cost-session")))
        record = await self.storage.get_team_shared_context("u", "ticket-1")
        branch = record.state.tasks[self.task_id].collaboration["cost-session"]
        self.assertEqual({}, branch.waiting_for)

    async def test_review_challenge_then_accept_with_runtime_evidence(self) -> None:
        await self.shared.record_assignments(
            "u",
            "ticket-1",
            {"hotel-session": TaskAssignment(agent_id="hotel", goal="Find hotels", done_when="price per night")},
        )
        await self._tool_fact("hotel", '{"name": "DEMO Song Han"}')
        hotel = self._tool("hotel-session", "hotel", "worker")
        await hotel(kind="result", content="DEMO Song Han is available")
        leader = self._tool("leader-session", "leader", "leader")

        challenge = await leader(
            kind="review",
            to="Hotel",
            decision="challenge",
            content="done_when needs the price per night",
        )
        self.assertNotEqual("error", challenge.state, challenge.content)
        ledger = await self._ledger()
        self.assertEqual("challenged", ledger["hotel-session"].status)
        self.assertEqual(1, ledger["hotel-session"].challenges)
        feedback = await self._inbox("hotel-session")
        self.assertIn("price per night", str(feedback))

        await self._tool_fact("hotel", '{"name": "DEMO Song Han", "price_vnd": 1200000}')
        await hotel(kind="result", content="DEMO Song Han 1200000 VND per night")
        accepted = await leader(kind="review", to="Hotel", decision="accept", content="ok")

        self.assertNotEqual("error", accepted.state, accepted.content)
        record = await self.storage.get_team_shared_context("u", "ticket-1")
        task = record.state.tasks[self.task_id]
        self.assertEqual("completed", task.collaboration["hotel-session"].status)
        self.assertEqual("accepted", task.assignments["hotel-session"].status)

    async def test_review_requires_member_and_decision(self) -> None:
        result = await self._tool("leader-session", "leader", "leader")(
            kind="review",
            content="looks fine",
        )
        self.assertEqual("error", result.state)

    async def test_ask_customer_question_key_is_derived_and_deduplicated(self) -> None:
        leader = self._tool("leader-session", "leader", "leader")
        first = await leader(kind="ask_customer", content="Bạn đi mấy người?")
        second = await leader(kind="ask_customer", content="  bạn đi mấy   người? ")

        self.assertIn("registered", first.content[0].text)
        self.assertIn("already registered", second.content[0].text)

    def test_model_facing_schema_is_small_per_role(self) -> None:
        leader = self._tool("leader-session", "leader", "leader")
        worker = self._tool("hotel-session", "hotel", "worker")

        self.assertEqual(
            {"kind", "to", "content", "done_when", "decision"},
            set(leader.input_schema["properties"]),
        )
        self.assertEqual({"kind", "to", "content"}, set(worker.input_schema["properties"]))


def test_number_ends_a_proper_name_anchor() -> None:
    from agentscope.app._evidence_claims import unsupported_claim_anchors

    evidence = ['{"name": "DEMO Song Han", "price_vnd": 1200000}']
    assert unsupported_claim_anchors("DEMO Song Han 1200000 VND per night", evidence) == ()
