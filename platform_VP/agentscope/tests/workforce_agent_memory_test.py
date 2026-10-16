"""Agent long-term memory and the learning / self-improvement loop."""

from types import SimpleNamespace
from datetime import UTC, datetime, timedelta
import hashlib
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


def verified_memory(**kwargs):
    content = kwargs["content"]
    kwargs.setdefault("source_ticket", "training-case")
    kwargs.setdefault("source_event_ids", ["verified-tool"])
    kwargs.setdefault("expires_at", datetime.now(UTC) + timedelta(days=14))
    kwargs.setdefault("provenance", {"policy": "agent-memory-evidence-v2", "supported": True, "safe_to_transfer": True,
                                    "content_sha256": hashlib.sha256(content.encode()).hexdigest()})
    return AgentMemoryRecord(**kwargs)


async def source(storage, ticket, event_id, content):
    record = TeamSharedContextRecord(user_id="u", team_id=ticket)
    task = SharedTaskState(id="task", objective="Verified repair")
    task.assignments["worker"] = TaskAssignment(agent_id="agent-1", goal="Repair", status="verified")
    record.state.active_task_id = task.id
    record.state.tasks[task.id] = task
    record.state.events = [SharedContextEvent(id=event_id, revision=1, task_id=task.id,
        kind="external_event", content=content, source_agent_id="agent-1", source_session_id="worker")]
    await storage.upsert_team_shared_context("u", record)


class _Model:
    """Scripted structured outputs keyed by schema name."""

    def __init__(self, outputs: dict) -> None:
        self.outputs = outputs
        self.calls: list[str] = []

    async def generate_structured_output(self, messages, structured_model, **_):
        name = structured_model.__name__
        self.calls.append(name)
        value = self.outputs.get(name, {"supported": True, "safe_to_transfer": True, "reason": "scripted evidence verifier"})
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
        await source(self.storage, "ticket-1", "e1", "R? n??c kh?n c?p: h??ng d?n kho? van t?ng tr??c")
        await source(self.storage, "ticket-2", "e9", "R? n??c: nh? ng?t ?i?n khu v?c ??t c?ng l?c kho? van")
        first = await self.memory.consolidate(
            "u",
            "agent-1",
            [MemoryCandidate(content="Rò nước khẩn cấp: hướng dẫn khoá van tổng trước", evidence_event_ids=["e1"])],
            ticket_id="ticket-1",
            model=_Model({}),
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
            [MemoryCandidate(content="Rò nước: nhớ ngắt điện khu vực ướt cùng lúc khoá van", evidence_event_ids=["e9"])],
            ticket_id="ticket-2",
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
                verified_memory(user_id="u", agent_id="agent-1", content=content),
            )
        recalled = await self.memory.recall("u", "agent-1", "nha toi bi ro nuoc, khoa van o dau?")

        self.assertEqual("Rò nước: khoá van tổng trước khi chờ thợ", recalled[0].content)
        stored = await self.storage.get_agent_memory("u", "agent-1", recalled[0].id)
        self.assertEqual(1, stored.uses)
        self.assertIn("<agent-memory>", self.memory.render(recalled))
        self.assertEqual([], rank("", recalled))

    async def test_a_memory_that_keeps_coming_with_rejected_results_is_retired(self) -> None:
        good = await self.storage.upsert_agent_memory(
            "u", verified_memory(user_id="u", agent_id="agent-1", content="Rò nước: khoá van tổng trước"),
        )
        bad = await self.storage.upsert_agent_memory(
            "u", verified_memory(user_id="u", agent_id="agent-1", content="Rò nước: hẹn thợ ngày mai"),
        )
        for ticket, success in (("t-1", False), ("t-2", False), ("t-3", True)):
            recalled = await self.memory.recall("u", "agent-1", "rò nước", ticket=ticket)
            self.assertIn(ticket, recalled[0].used_in)
            # The good item helped every time; the bad one only in rejected tickets.
            for memory in await self.memory.active("u", "agent-1"):
                if memory.id == good.id and not success:
                    memory.used_in = [m for m in memory.used_in if m != ticket]
                    await self.storage.upsert_agent_memory("u", memory)
            retired = await self.memory.record_outcome("u", ["agent-1"], ticket, success)
        self.assertEqual([], retired)
        stored = await self.storage.get_agent_memory("u", "agent-1", bad.id)
        self.assertEqual(("rejected", 2, 0), (stored.status, stored.failures, stored.successes))
        self.assertIn("phiếu người dùng chê", stored.reason)
        kept = await self.storage.get_agent_memory("u", "agent-1", good.id)
        self.assertEqual(("active", 1), (kept.status, kept.successes))

    def test_track_record_lowers_the_rank(self) -> None:
        tried = verified_memory(user_id="u", agent_id="a", content="Rò nước: khoá van", failures=3)
        fresh = verified_memory(user_id="u", agent_id="a", content="Rò nước: khoá van")
        self.assertIs(fresh, rank("rò nước khoá van", [tried, fresh])[0][1])

    async def test_retired_memory_is_no_longer_recalled(self) -> None:
        record = await self.storage.upsert_agent_memory(
            "u",
            verified_memory(user_id="u", agent_id="agent-1", content="Rò nước: khoá van tổng"),
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
                SpecTest(scenario=f"Kịch bản {i}", expected="Hướng dẫn an toàn", safety_critical=i == 0) for i in range(3)
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
                        {"kind": "lesson", "content": "Rò nước: hướng dẫn khoá van tổng ngay", "evidence_event_ids": ["t1"]},
                        {"kind": "fact", "content": "Mã sự cố rò nước là PLB-LEAK", "evidence_event_ids": ["t1", "invented"]},
                        {"kind": "fact", "content": "Vỡ ống luôn là khẩn cấp", "evidence_event_ids": ["r1"]},
                    ],
                    "rule": {"text": "Hỏi vị trí van tổng nếu khách không biết", "reason": "khách lúng túng", "evidence_event_ids": ["t1"]},
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
        # Kept: the lesson and the fact from a tool result (its invented id is
        # stripped). Dropped: the "fact" resting only on an agent's report.
        self.assertEqual(1, len(result["memories"]))
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


class RedisMemoryStorageTest(IsolatedAsyncioTestCase):
    async def test_redis_backend_stores_lists_and_filters_memories(self) -> None:
        import fakeredis.aioredis

        from agentscope.app.storage import RedisStorage

        storage = RedisStorage.__new__(RedisStorage)
        RedisStorage.__init__(storage)
        storage._client = fakeredis.aioredis.FakeRedis(decode_responses=True)
        memory = AgentMemoryService(storage)
        await source(storage, "t", "e1", "R? n??c: kho? van t?ng")
        added = await memory.consolidate(
            "u",
            "agent-1",
            [MemoryCandidate(content="Rò nước: khoá van tổng", evidence_event_ids=["e1"])],
            ticket_id="t",
            model=_Model({}),
        )
        await memory.retire("u", "agent-1", added[0]["memory_id"])
        await storage.upsert_agent_memory(
            "u",
            verified_memory(user_id="u", agent_id="agent-1", content="Mất điện: ngắt cầu dao"),
        )

        self.assertEqual(2, len(await storage.list_agent_memories("u", "agent-1")))
        self.assertEqual(
            ["Mất điện: ngắt cầu dao"],
            [m.content for m in await storage.list_agent_memories("u", "agent-1", status="active")],
        )
