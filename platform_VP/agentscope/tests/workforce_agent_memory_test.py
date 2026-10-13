"""Agent long-term memory and the learning / self-improvement loop."""

from types import SimpleNamespace
from unittest import IsolatedAsyncioTestCase

from agentscope.agent import ContextConfig, ReActConfig
from agentscope.app._agent_learning import AgentLearningService, ticket_succeeded
from agentscope.app._agent_memory import AgentMemoryService, MemoryCandidate, rank
from agentscope.app._agent_spec import AgentSpec, SpecTest
from agentscope.app._shared_context import SharedContextService
from agentscope.app.message_bus import InMemoryMessageBus
from agentscope.app.storage import (
    AgentData,
    AgentMemoryRecord,
    AgentRecord,
    AsyncSQLAlchemyStorage,
    SharedContextEvent,
    SharedTaskState,
    TaskAssignment,
    TeamSharedContextRecord,
)
from agentscope.app.storage._model._team_context import CollaborationBranch
from agentscope.message import TextBlock
from agentscope.model import ChatResponse


class _Model:
    """Scripted structured outputs keyed by schema name."""

    def __init__(self, outputs: dict) -> None:
        self.outputs = outputs
        self.calls: list[str] = []

    async def generate_structured_output(self, messages, structured_model, **_):
        name = structured_model.__name__
        self.calls.append(name)
        value = self.outputs[name]
        return SimpleNamespace(content=value(messages) if callable(value) else value)

    async def __call__(self, messages, tools=None, **_):
        return ChatResponse(content=[TextBlock(text="Khoá van tổng trước.")], is_last=True)


class _Agents:
    def __init__(self) -> None:
        self.agents: dict[str, AgentRecord] = {}

    async def get_agent(self, _user, agent_id):
        record = self.agents.get(agent_id)
        return record.model_copy(deep=True) if record else None

    async def upsert_agent(self, _user, record):
        self.agents[record.id] = record.model_copy(deep=True)
        return record

    async def list_sessions(self, _user, _agent):
        return []

    async def list_mcps(self, _user):
        return []

    async def get_mcp(self, _user, _id):
        return None


class MemoryServiceTest(IsolatedAsyncioTestCase):
    async def asyncSetUp(self) -> None:
        self.storage = AsyncSQLAlchemyStorage("sqlite+aiosqlite:///:memory:", create_tables=True)
        await self.storage.__aenter__()
        self.memory = AgentMemoryService(self.storage)

    async def asyncTearDown(self) -> None:
        await self.storage.__aexit__(None, None, None)

    async def test_add_update_supersedes_and_noop(self) -> None:
        first = await self.memory.consolidate(
            "u",
            "agent-1",
            [MemoryCandidate(content="Rò nước khẩn cấp: hướng dẫn khoá van tổng trước", evidence_event_ids=["e1"])],
            ticket_id="ticket-1",
            model=None,
        )
        self.assertEqual("add", first[0]["action"])
        old_id = first[0]["memory_id"]

        model = _Model(
            {
                "_Decisions": {
                    "decisions": [
                        {
                            "candidate": 0,
                            "action": "update",
                            "target_id": old_id,
                            "content": "Rò nước khẩn cấp: khoá van tổng và ngắt điện khu vực ướt trước",
                        },
                    ],
                },
            },
        )
        second = await self.memory.consolidate(
            "u",
            "agent-1",
            [MemoryCandidate(content="Rò nước: nhớ ngắt điện khu vực ướt cùng lúc khoá van", evidence_event_ids=["e9"])],
            ticket_id="ticket-2",
            model=model,
        )
        self.assertEqual("update", second[0]["action"])
        self.assertEqual(old_id, second[0]["supersedes"])
        stored = {m.id: m for m in await self.storage.list_agent_memories("u", "agent-1")}
        self.assertEqual("superseded", stored[old_id].status)
        self.assertEqual(1, len(await self.memory.active("u", "agent-1")))

        # The exact same wording again is a no-op without asking the model.
        again = await self.memory.consolidate(
            "u",
            "agent-1",
            [MemoryCandidate(content="Rò nước khẩn cấp: khoá van tổng và ngắt điện khu vực ướt trước", evidence_event_ids=["e9"])],
            ticket_id="ticket-3",
            model=model,
        )
        self.assertEqual([], again)

    async def test_recall_ranks_accent_insensitively_and_counts_use(self) -> None:
        for content in (
            "Khách hỏi phí sửa điều hoà: báo phí kiểm tra trước",
            "Rò nước: khoá van tổng trước khi chờ thợ",
            "Lịch vệ sinh toà S1 có ca 20:00 thu gom rác",
        ):
            await self.storage.upsert_agent_memory(
                "u",
                AgentMemoryRecord(user_id="u", agent_id="agent-1", content=content),
            )
        recalled = await self.memory.recall("u", "agent-1", "nha toi bi ro nuoc, khoa van o dau?")

        self.assertEqual("Rò nước: khoá van tổng trước khi chờ thợ", recalled[0].content)
        stored = await self.storage.get_agent_memory("u", "agent-1", recalled[0].id)
        self.assertEqual(1, stored.uses)
        self.assertIn("<agent-memory>", self.memory.render(recalled))
        self.assertEqual([], rank("", recalled))

    async def test_retired_memory_is_no_longer_recalled(self) -> None:
        record = await self.storage.upsert_agent_memory(
            "u",
            AgentMemoryRecord(user_id="u", agent_id="agent-1", content="Rò nước: khoá van tổng"),
        )
        await self.memory.retire("u", "agent-1", record.id)
        self.assertEqual([], await self.memory.recall("u", "agent-1", "rò nước"))


class LearningLoopTest(IsolatedAsyncioTestCase):
    async def asyncSetUp(self) -> None:
        self.shared_storage = AsyncSQLAlchemyStorage("sqlite+aiosqlite:///:memory:", create_tables=True)
        await self.shared_storage.__aenter__()
        self.shared = SharedContextService(self.shared_storage, InMemoryMessageBus())
        self.agents = _Agents()
        spec = AgentSpec(
            name="Kỹ thuật",
            tests=[
                SpecTest(scenario=f"Kịch bản {i}", expected="Hướng dẫn an toàn") for i in range(3)
            ],
        )
        self.agents.agents["agent-1"] = AgentRecord(
            id="agent-1",
            user_id="u",
            data=AgentData(
                name="Kỹ thuật",
                context_config=ContextConfig(),
                react_config=ReActConfig(),
                system_role="business",
                lifecycle_state="published",
                spec=spec.model_dump(mode="json"),
                published_version=1,
                versions=[{"version": 1, "spec": spec.model_dump(mode="json"), "author": "manager", "created_at": "2026-10-01T00:00:00+00:00"}],
                evaluation={"score": 0.67},
            ),
        )
        record = TeamSharedContextRecord(user_id="u", team_id="ticket-1")
        task = SharedTaskState(id="task-1", objective="Sửa ống nước")
        task.assignments["worker-session"] = TaskAssignment(agent_id="agent-1", goal="Xử lý rò nước", status="verified")
        task.collaboration["worker-session"] = CollaborationBranch(status="completed")
        record.state.tasks["task-1"] = task
        record.state.active_task_id = "task-1"
        for revision, (event_id, kind, content) in enumerate(
            [
                ("c1", "customer_message", "Nhà tôi vỡ ống nước"),
                ("t1", "external_event", '{"code": "PLB-LEAK", "first_aid": "Khoá van tổng"}'),
                ("r1", "result", "Khẩn cấp: khoá van tổng trước"),
            ],
            start=1,
        ):
            record.state.events.append(
                SharedContextEvent(
                    id=event_id,
                    revision=revision,
                    task_id="task-1",
                    kind=kind,
                    content=content,
                    source_session_id="worker-session" if kind != "customer_message" else "leader",
                    source_agent_id="agent-1" if kind != "customer_message" else None,
                ),
            )
        record.state.revision = 1
        await self.shared_storage.compare_and_swap_team_shared_context("u", record, 0)
        self.learning = AgentLearningService(self.agents, self.shared, object())

    async def asyncTearDown(self) -> None:
        await self.shared_storage.__aexit__(None, None, None)

    def _models(self, *, judge_pass: bool = True):
        model = _Model(
            {
                "_Learning": {
                    "memories": [
                        {"kind": "lesson", "content": "Rò nước: hướng dẫn khoá van tổng ngay", "evidence_event_ids": ["t1", "r1"]},
                        {"kind": "fact", "content": "Một điều không có nguồn", "evidence_event_ids": ["invented"]},
                    ],
                    "rule": {"text": "Hỏi vị trí van tổng nếu khách không biết", "reason": "khách lúng túng"},
                },
                "_Judgement": {"passed": judge_pass, "reason": "ok"},
            },
        )

        async def factory():
            return model, model

        return factory

    async def test_successful_ticket_adds_sourced_memory_and_self_publishes_rule(self) -> None:
        outcome = await self.learning.learn("u", "ticket-1", self._models())

        result = outcome["agents"]["agent-1"]
        self.assertEqual(1, len(result["memories"]))  # the unsourced one is dropped
        self.assertTrue(result["rule"]["applied"])
        agent = self.agents.agents["agent-1"]
        self.assertEqual(2, agent.data.published_version)
        self.assertEqual("agent", agent.data.versions[-1]["author"])
        self.assertIn("Hỏi vị trí van tổng", agent.data.system_prompt)
        learned = [r for r in agent.data.spec["rules"] if r["source"] == "agent"]
        self.assertEqual("ticket ticket-1", learned[0]["learned_from"])

        again = await self.learning.learn("u", "ticket-1", self._models())
        self.assertFalse(again["learned"])

    async def test_failing_tests_keep_the_published_version(self) -> None:
        outcome = await self.learning.learn("u", "ticket-1", self._models(judge_pass=False))

        self.assertFalse(outcome["agents"]["agent-1"]["rule"]["applied"])
        self.assertEqual(1, self.agents.agents["agent-1"].data.published_version)

    async def test_manager_draft_is_never_overwritten(self) -> None:
        agent = self.agents.agents["agent-1"]
        agent.data.draft_spec = agent.data.spec
        agent.data.draft_meta = {"author": "manager"}

        outcome = await self.learning.learn("u", "ticket-1", self._models())

        self.assertEqual("manager draft in progress", outcome["agents"]["agent-1"]["rule"]["reason"])

    def test_only_fully_verified_tickets_count_as_success(self) -> None:
        task = SharedTaskState(id="t", objective="x")
        self.assertFalse(ticket_succeeded(task))
        task.assignments["a"] = TaskAssignment(goal="g", status="verified")
        task.assignments["b"] = TaskAssignment(goal="g", status="failed")
        self.assertFalse(ticket_succeeded(task))
        task.assignments["b"].status = "accepted"
        self.assertTrue(ticket_succeeded(task))
