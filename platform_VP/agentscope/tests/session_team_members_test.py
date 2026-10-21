# -*- coding: utf-8 -*-
"""Manual membership reuses invitations without giving roster control to the leader."""
from unittest.mock import AsyncMock, patch

from fastapi import FastAPI, HTTPException
from httpx import ASGITransport, AsyncClient
from service_team_tools_test import _AgentInviteTestBase
from service_toolkit_test import _FakeWorkspace, _tool_names

from agentscope.app._router._schema import AddTeamMemberRequest
from agentscope.app._router._session import add_team_member, remove_team_member, session_router
from agentscope.app.deps import (
    get_current_user_id, get_message_bus, get_resource_access_service,
    get_shared_context_storage, get_storage, get_workspace_manager,
)
from agentscope.app._service import ResourceAccessService, SessionService, SessionStatus, get_toolkit
from agentscope.app._tool import AgentInvite, TeamDelete
from agentscope.app.access import DenyAllResourceAccessPolicy
from agentscope.app.message_bus import MessageBusKeys
from agentscope.message import ToolResultState


class TestManualTeamMembers(_AgentInviteTestBase):
    async def asyncSetUp(self):
        await super().asyncSetUp()
        self.leader_agent.data.system_role = "leader"
        await self.storage.upsert_agent(self.user_id, self.leader_agent)
        self.access = ResourceAccessService(
            storage=self.storage, policy=DenyAllResourceAccessPolicy(),
        )

    async def _add(self, **overrides):
        kwargs = dict(
            session_id=self.leader_session.id,
            body=AddTeamMemberRequest(agent_id=self.monday_agent.id),
            agent_id=self.leader_agent.id,
            user_id=self.user_id, storage=self.storage, access=self.access,
            message_bus=self.bus, workspace_manager=self.workspace_manager,
            shared_storage=self.storage,
        )
        return await add_team_member(**{**kwargs, **overrides})

    def _invite_tool(self):
        return AgentInvite(
            storage=self.storage, message_bus=self.bus,
            workspace_manager=self.workspace_manager, user_id=self.user_id,
            session_id=self.leader_session.id, agent_id=self.leader_agent.id,
            invitable_pool=[self.monday_agent], resource_access_service=self.access,
        )

    async def _remove(self, **overrides):
        kwargs = dict(
            session_id=self.leader_session.id, member_id=self.monday_agent.id,
            agent_id=self.leader_agent.id, user_id=self.user_id,
            storage=self.storage, access=self.access, message_bus=self.bus,
        )
        return await remove_team_member(**{**kwargs, **overrides})

    async def test_remove_preserves_agent_and_sessions_and_allows_reinvitation(self):
        added = await self._add()
        borrowed_id = added.members[0].session_id
        before = await self.storage.get_session(self.user_id, self.monday_agent.id, borrowed_id)
        events_before = await self.bus.log_read(MessageBusKeys.session_events(self.leader_session.id))
        removed = await self._remove()
        self.assertEqual(removed.members, [])
        self.assertEqual(removed.team.data.member_ids, [])
        self.assertTrue(removed.team.data.manual_membership)
        self.assertIsNotNone(await self.storage.get_agent(self.user_id, self.monday_agent.id))
        primary = await self.storage.get_session(self.user_id, self.monday_agent.id, self.monday_session.id)
        self.assertIsNotNone(primary)
        borrowed = await self.storage.get_session(self.user_id, self.monday_agent.id, borrowed_id)
        self.assertIsNotNone(borrowed)
        self.assertIsNone(borrowed.team_id)
        self.assertEqual(borrowed.state, before.state)
        saved = await self.storage.get_team(self.user_id, removed.team.id)
        self.assertEqual(saved.data.members, [])
        self.assertEqual(saved.data.member_ids, [])
        events = await self.bus.log_read(MessageBusKeys.session_events(self.leader_session.id))
        self.assertGreater(len(events), len(events_before))
        self.assertEqual(events[-1][1].get("name"), "team_updated")
        readded = await self._add()
        self.assertEqual([m.agent.id for m in readded.members], [self.monday_agent.id])

    async def test_remove_rejects_running_leader_or_member_and_releases_own_locks(self):
        added = await self._add()
        leader_key = MessageBusKeys.session_lock(self.leader_session.id)
        member_key = MessageBusKeys.session_lock(added.members[0].session_id)
        for key in (leader_key, member_key):
            async with self.bus.acquire_lock(key):
                with self.assertRaises(HTTPException) as error:
                    await self._remove()
                self.assertEqual(error.exception.status_code, 409)
                self.assertTrue(await self.bus.is_locked(key))
            self.assertFalse(await self.bus.is_locked(leader_key))
            self.assertFalse(await self.bus.is_locked(member_key))
        team = await self.storage.get_team(self.user_id, added.team.id)
        self.assertEqual(len(team.data.members), 1)

    async def test_remove_rejects_member_with_pending_confirmation(self):
        added = await self._add()
        with patch.object(SessionService, "derive_parked_status", return_value=SessionStatus.AWAITING_PERMISSION):
            with self.assertRaises(HTTPException) as error:
                await self._remove()
        self.assertEqual(error.exception.status_code, 409)
        member = await self.storage.get_session(
            self.user_id, self.monday_agent.id, added.members[0].session_id,
        )
        self.assertEqual(member.team_id, added.team.id)
        for sid in (self.leader_session.id, member.id):
            self.assertFalse(await self.bus.is_locked(MessageBusKeys.session_lock(sid)))

    async def test_remove_rejects_foreign_session_nonmembers_and_leader(self):
        added = await self._add()
        for overrides, expected in (
            ({"user_id": "other-user"}, 404),
            ({"agent_id": self.monday_agent.id}, 404),
            ({"member_id": self.leader_agent.id}, 404),
            ({"member_id": "nonmember"}, 404),
            ({"session_id": added.members[0].session_id, "agent_id": self.monday_agent.id}, 403),
        ):
            with self.subTest(overrides=overrides):
                with self.assertRaises(HTTPException) as error:
                    await self._remove(**overrides)
                self.assertEqual(error.exception.status_code, expected)
        team = await self.storage.get_team(self.user_id, added.team.id)
        self.assertEqual(len(team.data.members), 1)

    async def test_remove_only_detaches_this_room(self):
        first = await self._add()
        other_session = await self.storage.upsert_session(
            user_id=self.user_id, agent_id=self.leader_agent.id,
            config=self.leader_session.config,
        )
        other = await self._add(session_id=other_session.id)
        await self._remove()
        other_team = await self.storage.get_team(self.user_id, other.team.id)
        self.assertEqual(len(other_team.data.members), 1)
        other_member = await self.storage.get_session(
            self.user_id, self.monday_agent.id, other.members[0].session_id,
        )
        self.assertEqual(other_member.team_id, other.team.id)
        self.assertNotEqual(first.team.id, other.team.id)

    async def test_http_endpoint_accepts_member_id_and_returns_team_detail(self):
        app = FastAPI()
        app.include_router(session_router)
        def override(value):
            async def resolve():
                return value
            return resolve

        app.dependency_overrides = {
            dependency: override(value) for dependency, value in (
                (get_current_user_id, self.user_id),
                (get_storage, self.storage),
                (get_shared_context_storage, self.storage),
                (get_message_bus, self.bus),
                (get_resource_access_service, self.access),
                (get_workspace_manager, self.workspace_manager),
            )
        }
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            response = await client.post(
                f"/sessions/{self.leader_session.id}/team/members",
                params={"agent_id": self.leader_agent.id},
                json={"agent_id": self.monday_agent.id},
            )
            removed = await client.delete(
                f"/sessions/{self.leader_session.id}/team/members/{self.monday_agent.id}",
                params={"agent_id": self.leader_agent.id},
            )
        self.assertEqual(response.status_code, 200, response.text)
        self.assertTrue(response.json()["team"]["data"]["manual_membership"])
        self.assertEqual(response.json()["members"][0]["agent"]["id"], self.monday_agent.id)
        self.assertEqual(removed.status_code, 200, removed.text)
        self.assertEqual(removed.json()["members"], [])

    async def test_adds_dormant_member_and_persists_manual_mode(self):
        with patch("agentscope.app._bus_ops.enqueue_run_trigger", new_callable=AsyncMock) as wake:
            detail = await self._add()
        wake.assert_not_awaited()
        self.assertTrue(detail.team.data.manual_membership)
        self.assertEqual([m.agent.id for m in detail.members], [self.monday_agent.id])
        borrowed = await self.storage.get_session(
            self.user_id, self.monday_agent.id, detail.members[0].session_id,
        )
        self.assertEqual(borrowed.team_id, detail.team.id)
        self.assertNotEqual(borrowed.id, self.monday_session.id)
        saved = await self.storage.get_team(self.user_id, detail.team.id)
        self.assertTrue(saved.data.manual_membership)
        self.assertFalse(await self.bus.is_locked(MessageBusKeys.session_lock(self.leader_session.id)))
        events = await self.bus.log_read(MessageBusKeys.session_events(self.leader_session.id))
        self.assertTrue(any(e.get("name") == "team_updated" for _, e in events))

    async def test_repeated_manual_add_keeps_one_borrowed_session(self):
        first = await self._add()
        second = await self._add()
        self.assertEqual(len(second.members), 1)
        self.assertEqual(first.members[0].session_id, second.members[0].session_id)

    async def test_user_can_add_another_member_without_replacing_existing_members(self):
        first = await self._add()
        second = self.monday_agent.model_copy(deep=True)
        second.id = "second-specialist"
        second.data.name = "Another specialist"
        await self.storage.upsert_agent(self.user_id, second)
        detail = await self._add(body=AddTeamMemberRequest(agent_id=second.id))
        self.assertEqual([m.agent.id for m in detail.members], [self.monday_agent.id, second.id])
        self.assertEqual(detail.members[0].session_id, first.members[0].session_id)
        self.assertTrue(detail.team.data.manual_membership)

    async def test_tool_captured_before_manual_add_cannot_invite_afterwards(self):
        tool = self._invite_tool()
        await self._add()
        result = await tool(
            target=f"Monday@{self.monday_agent.id[:8]}", prompt="Start work",
        )
        self.assertEqual(result.state, ToolResultState.ERROR)
        self.assertIn("user controls", result.content[0].text)

    async def test_leader_cannot_dissolve_manual_roster(self):
        detail = await self._add()
        result = await TeamDelete(
            storage=self.storage, message_bus=self.bus,
            workspace_manager=self.workspace_manager, user_id=self.user_id,
            session_id=self.leader_session.id, agent_id=self.leader_agent.id,
        )()
        self.assertEqual(result.state, ToolResultState.ERROR)
        self.assertIsNotNone(await self.storage.get_team(self.user_id, detail.team.id))

    async def test_toolkit_hides_management_tools_only_after_manual_add(self):
        for manual in (False, True):
            if manual:
                await self._add()
            session = await self.storage.get_session(
                self.user_id, self.leader_agent.id, self.leader_session.id,
            )
            toolkit = await get_toolkit(
                storage=self.storage, workspace=_FakeWorkspace(),
                workspace_manager=self.workspace_manager,
                scheduler_manager=AsyncMock(), background_task_manager=AsyncMock(),
                message_bus=self.bus, middlewares=[], user_id=self.user_id,
                agent_record=self.leader_agent, session_record=session,
                resource_access_service=self.access,
            )
            names = _tool_names(toolkit)
            self.assertIn("TeamSay", names)
            for name in ("AgentInvite", "TeamDelete"):
                self.assertEqual(name in names, not manual)

    async def test_teamless_leader_can_add_before_first_chat(self):
        session = await self.storage.upsert_session(
            user_id=self.user_id, agent_id=self.leader_agent.id,
            config=self.leader_session.config,
        )
        detail = await self._add(session_id=session.id)
        self.assertEqual(detail.team.session_id, session.id)
        self.assertTrue(detail.team.data.manual_membership)

    async def test_running_leader_rejects_manual_add(self):
        key = MessageBusKeys.session_lock(self.leader_session.id)
        async with self.bus.acquire_lock(key):
            with self.assertRaises(HTTPException) as error:
                await self._add()
            self.assertEqual(error.exception.status_code, 409)
            self.assertTrue(await self.bus.is_locked(key))

    async def test_inaccessible_agent_and_foreign_session_are_rejected(self):
        for overrides in (
            {"body": AddTeamMemberRequest(agent_id="private-agent")},
            {"user_id": "other-user"},
            {"session_id": self.monday_session.id},
        ):
            with self.subTest(overrides=overrides):
                with self.assertRaises(HTTPException) as error:
                    await self._add(**overrides)
                self.assertEqual(error.exception.status_code, 404)

    async def test_unpublished_agent_does_not_change_roster_mode(self):
        self.monday_agent.data.lifecycle_state = "draft"
        await self.storage.upsert_agent(self.user_id, self.monday_agent)
        with self.assertRaises(HTTPException) as error:
            await self._add()
        self.assertEqual(error.exception.status_code, 400)
        session = await self.storage.get_session(
            self.user_id, self.leader_agent.id, self.leader_session.id,
        )
        team = await self.storage.get_team(self.user_id, session.team_id)
        self.assertFalse(team.data.manual_membership)
        self.assertEqual(team.data.members, [])

    async def test_failed_invite_releases_lock_and_does_not_lock_roster(self):
        with patch.object(AgentInvite, "invite_member", side_effect=RuntimeError("workspace unavailable")):
            with self.assertRaisesRegex(RuntimeError, "workspace unavailable"):
                await self._add()
        self.assertFalse(await self.bus.is_locked(MessageBusKeys.session_lock(self.leader_session.id)))
        session = await self.storage.get_session(
            self.user_id, self.leader_agent.id, self.leader_session.id,
        )
        team = await self.storage.get_team(self.user_id, session.team_id)
        self.assertFalse(team.data.manual_membership)

    async def test_failed_first_invite_does_not_leave_an_empty_team(self):
        session = await self.storage.upsert_session(
            user_id=self.user_id, agent_id=self.leader_agent.id,
            config=self.leader_session.config,
        )
        with patch.object(AgentInvite, "invite_member", side_effect=RuntimeError("workspace unavailable")):
            with self.assertRaisesRegex(RuntimeError, "workspace unavailable"):
                await self._add(session_id=session.id)
        session = await self.storage.get_session(self.user_id, self.leader_agent.id, session.id)
        self.assertIsNone(session.team_id)
        teams = await self.storage.list_teams(self.user_id)
        self.assertFalse([team for team in teams if team.session_id == session.id])

    async def test_rejected_first_invite_returns_400_and_removes_the_team(self):
        session = await self.storage.upsert_session(
            user_id=self.user_id, agent_id=self.leader_agent.id,
            config=self.leader_session.config,
        )
        from agentscope.message import TextBlock
        from agentscope.tool import ToolChunk
        rejected = ToolChunk(content=[TextBlock(text="Agent is busy.")], state=ToolResultState.ERROR)
        with patch.object(AgentInvite, "invite_member", AsyncMock(return_value=rejected)):
            with self.assertRaises(HTTPException) as error:
                await self._add(session_id=session.id)
        self.assertEqual(error.exception.status_code, 400)
        session = await self.storage.get_session(self.user_id, self.leader_agent.id, session.id)
        self.assertIsNone(session.team_id)
