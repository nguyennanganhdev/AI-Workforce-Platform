# -*- coding: utf-8 -*-
"""Agent artifacts (eval cases, eval runs, memories) on Redis and SQL."""
import os
import tempfile
from contextlib import AsyncExitStack
from unittest.async_case import IsolatedAsyncioTestCase

from storage_redis_test import make_agent_record, make_storage

from agentscope.app.storage import AgentArtifactRecord, AsyncSQLAlchemyStorage


class _ArtifactContract:
    """Behaviour both storages must share."""

    storage = None

    async def test_round_trip_and_listing_by_agent_and_kind(self) -> None:
        agent = make_agent_record("u1")
        await self.storage.upsert_agent("u1", agent)
        case = AgentArtifactRecord(user_id="u1", agent_id=agent.id, kind="eval_case", data={"scenario": "a"})
        memory = AgentArtifactRecord(user_id="u1", agent_id=agent.id, kind="memory", data={"content": "m"})
        for record in (case, memory):
            await self.storage.upsert_agent_artifact("u1", record)

        self.assertEqual((await self.storage.get_agent_artifact("u1", case.id)).data, {"scenario": "a"})
        self.assertEqual([r.id for r in await self.storage.list_agent_artifacts("u1", agent.id, "eval_case")], [case.id])
        self.assertEqual([r.id for r in await self.storage.list_agent_artifacts("u1", agent.id, "memory")], [memory.id])

        case.data = {"scenario": "b"}
        await self.storage.upsert_agent_artifact("u1", case)
        listed = await self.storage.list_agent_artifacts("u1", agent.id, "eval_case")
        self.assertEqual([r.data for r in listed], [{"scenario": "b"}])

    async def test_other_users_cannot_read_or_delete(self) -> None:
        record = AgentArtifactRecord(user_id="u1", agent_id="a", kind="memory")
        await self.storage.upsert_agent_artifact("u1", record)
        self.assertIsNone(await self.storage.get_agent_artifact("u2", record.id))
        self.assertFalse(await self.storage.delete_agent_artifact("u2", record.id))
        self.assertTrue(await self.storage.delete_agent_artifact("u1", record.id))
        self.assertIsNone(await self.storage.get_agent_artifact("u1", record.id))
        self.assertEqual(await self.storage.list_agent_artifacts("u1", "a", "memory"), [])

    async def test_deleting_the_agent_deletes_its_artifacts(self) -> None:
        agent = make_agent_record("u1")
        await self.storage.upsert_agent("u1", agent)
        record = AgentArtifactRecord(user_id="u1", agent_id=agent.id, kind="eval_run")
        await self.storage.upsert_agent_artifact("u1", record)
        await self.storage.delete_agent("u1", agent.id)
        self.assertIsNone(await self.storage.get_agent_artifact("u1", record.id))


class RedisAgentArtifactTest(_ArtifactContract, IsolatedAsyncioTestCase):
    async def asyncSetUp(self) -> None:
        self.storage = make_storage()


class SQLAgentArtifactTest(_ArtifactContract, IsolatedAsyncioTestCase):
    async def asyncSetUp(self) -> None:
        self._stack = AsyncExitStack()
        self.storage = await self._stack.enter_async_context(
            AsyncSQLAlchemyStorage("sqlite+aiosqlite:///:memory:", create_tables=True),
        )

    async def asyncTearDown(self) -> None:
        await self._stack.aclose()

    async def test_migration_alone_creates_the_table(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            url = f"sqlite+aiosqlite:///{os.path.join(tmp, 'as.db')}"
            async with AsyncSQLAlchemyStorage(url, auto_migrate=True, create_tables=False) as storage:
                record = AgentArtifactRecord(user_id="u1", agent_id="a", kind="memory")
                await storage.upsert_agent_artifact("u1", record)
                self.assertEqual(len(await storage.list_agent_artifacts("u1", "a", "memory")), 1)
