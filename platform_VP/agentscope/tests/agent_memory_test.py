# -*- coding: utf-8 -*-
"""Agent memory: proposals, approval, decay and what reaches the prompt."""
from datetime import UTC, datetime, timedelta
from unittest import TestCase
from unittest.mock import AsyncMock

from fastapi import HTTPException
from service_team_tools_test import _AgentInviteTestBase

from agentscope.app._router import _agent_memory as router
from agentscope.app._service import _agent_memory as memory
from agentscope.app._tool import MemoryPropose
from agentscope.message import ToolResultState


class PriorityTest(TestCase):
    def _data(self, days_ago: float, **extra):
        stamp = (datetime.now(UTC) - timedelta(days=days_ago)).isoformat()
        return memory.MemoryData(content="x", status="approved", proposed_at=stamp, approved_at=stamp, **extra)

    def test_priority_halves_every_half_life_and_pinned_stays_full(self):
        self.assertAlmostEqual(memory.priority(self._data(0)), 1.0, places=3)
        self.assertAlmostEqual(memory.priority(self._data(memory.HALF_LIFE_DAYS)), 0.5, places=3)
        self.assertLess(memory.priority(self._data(70)), memory.ACTIVE_MIN)
        self.assertEqual(memory.priority(self._data(365, pinned=True)), 1.0)

    def test_a_new_confirmation_restores_priority(self):
        data = self._data(90, last_confirmed_at=datetime.now(UTC).isoformat())
        self.assertAlmostEqual(memory.priority(data), 1.0, places=3)

    def test_proposals_have_no_priority(self):
        data = memory.MemoryData(content="x", proposed_at=datetime.now(UTC).isoformat())
        self.assertEqual(memory.priority(data), 0.0)


class MemoryFlowTest(_AgentInviteTestBase):
    async def asyncSetUp(self):
        await super().asyncSetUp()
        self.agent = self.monday_agent

    async def _propose(self, content, reason=""):
        return await memory.propose(self.storage, self.user_id, self.agent.id, content, reason, "s1")

    async def test_proposals_wait_for_approval_then_reach_the_prompt(self):
        outcome, record = await self._propose("Khách thường bay từ Hà Nội.", "Khách nói vậy")
        self.assertEqual(outcome, "proposed")
        self.assertEqual(await memory.memory_prompt(self.storage, self.user_id, self.agent.id), "")
        self.assertEqual((await self._propose("khách thường bay từ hà nội"))[0], "duplicate")

        await router.approve_memory(
            agent_id=self.agent.id, memory_id=record.id,
            body=router.ApproveMemoryRequest(content="Khách thường bay từ Hà Nội (Nội Bài)."),
            user_id=self.user_id, storage=self.storage,
        )
        prompt = await memory.memory_prompt(self.storage, self.user_id, self.agent.id)
        self.assertIn("APPROVED MEMORY", prompt)
        self.assertIn("Khách thường bay từ Hà Nội (Nội Bài).", prompt)

        outcome, again = await self._propose("Khách thường bay từ Hà Nội (Nội Bài).")
        self.assertEqual((outcome, again.id), ("reinforced", record.id))
        self.assertEqual(again.data["confirmations"], 1)

    async def test_sensitive_content_is_never_stored(self):
        for content in ("Mật khẩu của khách là abc123", "Số thẻ 4111 1111 1111 1111", "OTP là 123456"):
            with self.assertRaises(memory.MemoryRejected):
                await self._propose(content)
        with self.assertRaises(HTTPException) as error:
            await router.add_memory(
                agent_id=self.agent.id, body=router.AddMemoryRequest(content="password: hunter2"),
                user_id=self.user_id, storage=self.storage,
            )
        self.assertEqual(error.exception.status_code, 422)
        self.assertEqual(await self.storage.list_agent_artifacts(self.user_id, self.agent.id, "memory"), [])

    async def test_review_actions_and_listing_order(self):
        _, proposal = await self._propose("Khách thích ghế cạnh cửa sổ.")
        _, rejected = await self._propose("Khách đi Đà Nẵng 15/11.")
        added = await router.add_memory(
            agent_id=self.agent.id, body=router.AddMemoryRequest(content="Khách là hội viên vàng."),
            user_id=self.user_id, storage=self.storage,
        )
        await router.reject_memory(agent_id=self.agent.id, memory_id=rejected.id, user_id=self.user_id, storage=self.storage)
        listed = await router.list_memories(agent_id=self.agent.id, user_id=self.user_id, storage=self.storage)
        self.assertEqual([(m["id"], m["status"]) for m in listed], [(proposal.id, "proposed"), (added["id"], "approved")])

        pinned = await router.update_memory(
            agent_id=self.agent.id, memory_id=added["id"], body=router.UpdateMemoryRequest(pinned=True, confirm=True),
            user_id=self.user_id, storage=self.storage,
        )
        self.assertTrue(pinned["pinned"] and pinned["active"])
        self.assertEqual(pinned["confirmations"], 1)
        with self.assertRaises(HTTPException) as error:
            await router.update_memory(
                agent_id=self.agent.id, memory_id=proposal.id, body=router.UpdateMemoryRequest(pinned=True),
                user_id=self.user_id, storage=self.storage,
            )
        self.assertEqual(error.exception.status_code, 409)
        with self.assertRaises(HTTPException) as error:
            await router.delete_memory(agent_id="other", memory_id=added["id"], user_id=self.user_id, storage=self.storage)
        self.assertEqual(error.exception.status_code, 404)
        await router.delete_memory(agent_id=self.agent.id, memory_id=added["id"], user_id=self.user_id, storage=self.storage)
        self.assertEqual(await memory.memory_prompt(self.storage, self.user_id, self.agent.id), "")

    async def test_fading_memories_leave_the_prompt_and_the_prompt_is_capped(self):
        for index in range(memory.PROMPT_LIMIT + 2):
            await router.add_memory(
                agent_id=self.agent.id, body=router.AddMemoryRequest(content=f"Sự thật số {index}."),
                user_id=self.user_id, storage=self.storage,
            )
        records = await self.storage.list_agent_artifacts(self.user_id, self.agent.id, "memory")
        old = (datetime.now(UTC) - timedelta(days=120)).isoformat()
        records[0].data.update(approved_at=old, last_confirmed_at=old)
        await self.storage.upsert_agent_artifact(self.user_id, records[0])
        prompt = await memory.memory_prompt(self.storage, self.user_id, self.agent.id)
        self.assertEqual(prompt.count("\n- "), memory.PROMPT_LIMIT)
        self.assertNotIn("Sự thật số 0.", prompt)

    async def test_the_tool_reports_each_outcome(self):
        tool = MemoryPropose(storage=self.storage, user_id=self.user_id, agent_id=self.agent.id, session_id="s1")
        first = await tool(content="Khách đi một mình.")
        self.assertEqual(first.state, ToolResultState.SUCCESS)
        self.assertIn("người dùng sẽ duyệt", first.content[0].text)
        refused = await tool(content="mật khẩu là 1234")
        self.assertEqual(refused.state, ToolResultState.ERROR)

    async def test_an_unreadable_memory_store_never_breaks_a_reply(self):
        storage = AsyncMock()
        storage.list_agent_artifacts.side_effect = NotImplementedError
        self.assertEqual(await memory.memory_prompt(storage, "u", "a"), "")
