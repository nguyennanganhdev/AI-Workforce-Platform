"""Full ChatService turns with scripted models, real tools/storage/bus; no keys."""
import json
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

from tests import service_team_tools_test as fixtures
from tests.team_member_middleware_test import _call, _text
from tests.utils import MockModel
from agentscope.app._service import ChatService, ResourceAccessService
from agentscope.app._bus_ops import publish_session_event
from agentscope.app.access import DenyAllResourceAccessPolicy
from agentscope.app._shared_context import SharedContextService
from agentscope.app._team_turn import get_team_turn, start_team_turn
from agentscope.app._tool import TeamCreate, AgentInvite, TeamSay, SharedContextRead
from agentscope.app.storage import SessionConfig, ChatModelConfig
from agentscope.message import UserMsg, ThinkingBlock, TextBlock
from agentscope.tool import Toolkit


class TestPersonalTeamRuntime(fixtures._TeamToolsTestBase):
    async def test_create_invite_peer_question_customer_answer_and_direct_final(self):
        self.leader_agent.data.system_role = "leader"
        await self.storage.upsert_agent(self.user_id, self.leader_agent)
        models = {}
        workers = []
        for name in ("Research", "Verifier"):
            record = fixtures._make_agent_record(self.user_id, name)
            record.data.lifecycle_state = "published"
            record.data.invite_config.invitable = True
            record.data.invite_config.invite_description = name
            await self.storage.upsert_agent(self.user_id, record)
            workers.append(record)
        for record in (self.leader_agent, *workers):
            cfg = SessionConfig(workspace_id="ws-" + record.id,
                chat_model_config=ChatModelConfig(type="mock", credential_id="offline", model=record.data.name, parameters={}))
            if record.id == self.leader_agent.id:
                # Keep the existing root session identity.
                await self.storage.upsert_session(user_id=self.user_id, agent_id=record.id,
                    session_id=self.leader_session.id, config=cfg)
            else:
                await self.storage.upsert_session(user_id=self.user_id, agent_id=record.id, config=cfg)
            models[record.data.name] = MockModel(context_size=200_000)
        research, verifier = [f"{a.data.name}@{a.id[:8]}" for a in workers]
        models[self.leader_agent.data.name].set_responses([
            _call("TeamCreate", name="Customer request", description="Compare the supplied choices"),
            _call("AgentInvite", target=research, prompt="Compare the supplied choices", additional_assignments=[
                {"target": verifier, "prompt": "Verify the supplied choices", "standby": True}]),
            _text("Các thành viên đang xử lý yêu cầu."),
        ])
        models["Research"].set_responses([
            _call("TeamSay", to=verifier, kind="question", content="Check whether any options were supplied."),
            _call("TeamSay", kind="requires_user_input", content="Which option do you choose?"),
            _call("TeamSay", kind="result", content="No matching options were returned."),
        ])
        models["Research"].mock_chat_responses[-1].content.insert(0, ThinkingBlock(thinking="PRIVATE-MEMBER-REASONING"))
        models["Research"].mock_chat_responses[-1].content.insert(1, TextBlock(text="PRIVATE-UNVERIFIED-DRAFT"))
        models["Verifier"].set_responses([
            _call("TeamSay", to=research, kind="answer", content="No matching options were returned."),
        ])
        workspace = SimpleNamespace(workdir="/tmp/offline-personal-team", default_mcps=[],
            list_mcps=AsyncMock(return_value=[]), add_mcp=AsyncMock(), remove_mcp=AsyncMock())
        self.workspace_manager.get_workspace = AsyncMock(return_value=workspace)
        shared = SharedContextService(self.storage, self.bus)
        access = ResourceAccessService(self.storage, DenyAllResourceAccessPolicy())
        captured = []

        async def toolkit(**kwargs):
            captured.append(kwargs)
            base = dict(storage=self.storage, message_bus=self.bus, workspace_manager=self.workspace_manager,
                user_id=self.user_id, session_id=kwargs["session_record"].id,
                agent_id=kwargs["agent_record"].id, shared_context_service=shared,
                peer_collaboration=kwargs["peer_collaboration"])
            tools = [TeamSay(**base, role=kwargs["team_role"] or "leader"), SharedContextRead(**base)]
            if kwargs["agent_record"].id == self.leader_agent.id:
                tools += [TeamCreate(**base), AgentInvite(**base, invitable_pool=workers)]
            return Toolkit(tools=tools)

        async def model(_user, config, _access):
            return models[config.model]

        service = ChatService(storage=self.storage, workspace_manager=self.workspace_manager,
            scheduler_manager=object(), background_task_manager=object(), message_bus=self.bus,
            resource_access_service=access, shared_context_storage=self.storage)
        # The tool factory shares the exact canonical context used by ChatService.
        service._shared_context = shared
        with (patch("agentscope.app._service._chat.get_toolkit", toolkit),
              patch("agentscope.app._service._chat.get_model", model),
              patch("agentscope.app._service._chat.publish_session_event", wraps=publish_session_event) as publisher):
            request = UserMsg("Customer", "Compare the supplied choices; ask me if anything is missing.")
            await service._run_impl(self.user_id, self.leader_session.id, self.leader_agent.id, request)
            root = await self.storage.get_session(self.user_id, "", self.leader_session.id)
            self.assertIsNotNone(root.team_id)
            team = await self.storage.get_team(self.user_id, root.team_id)
            self.assertEqual("peer", team.data.collaboration_mode)
            sessions = {m.agent_id: m.session_id for m in team.data.members}
            self.assertEqual(2, len(sessions))
            # Even a legacy standby brief starts immediately in personal mode.
            wakeups = await self.bus.dequeue_wakeups(max_count=10)
            self.assertEqual(set(sessions.values()), {w["session_id"] for w in wakeups})
            for record in (workers[0], workers[1], workers[0]):
                await service._run_impl(self.user_id, sessions[record.id], record.id, None)
            turn = await get_team_turn(self.bus, team.id, storage=self.storage, user_id=self.user_id)
            self.assertEqual("awaiting_user_input", turn.status)
            self.assertEqual(sessions[workers[0].id], turn.reply_owner_session_id)
            messages, _ = await self.storage.list_messages(self.user_id, root.id, limit=100)
            self.assertTrue(any("Which option do you choose?" in (m.get_text_content() or "") for m in messages))
            # Reassemble the runtime from durable state before the customer replies.
            shared = SharedContextService(self.storage, self.bus)
            service = ChatService(storage=self.storage, workspace_manager=self.workspace_manager,
                scheduler_manager=object(), background_task_manager=object(), message_bus=self.bus,
                resource_access_service=access, shared_context_storage=self.storage)
            service._shared_context = shared
            await start_team_turn(self.bus, team.id, reply_owner_session_id=turn.reply_owner_session_id,
                reply_owner_agent_id=turn.reply_owner_agent_id, customer_session_id=root.id,
                mode="specialist_question", task_id=turn.task_id, storage=self.storage, user_id=self.user_id)
            await service._run_impl(self.user_id, sessions[workers[0].id], workers[0].id, UserMsg("Customer", "I have no options yet."))
            models["Research"].mock_chat_responses.append(
                _call("TeamSay", kind="result", content="No alternatives were returned."))
            await start_team_turn(self.bus, team.id, reply_owner_session_id=sessions[workers[0].id],
                reply_owner_agent_id=workers[0].id, customer_session_id=root.id,
                mode="direct_mention", task_id=turn.task_id, storage=self.storage, user_id=self.user_id)
            await service._run_impl(self.user_id, sessions[workers[0].id], workers[0].id, UserMsg("Customer", "Any alternatives?"))
        messages, _ = await self.storage.list_messages(self.user_id, root.id, limit=100)
        finals = [m for m in messages if "No matching options were returned." == (m.get_text_content() or "").strip()]
        self.assertEqual(1, len(finals), [(m.name, m.get_text_content()) for m in messages])
        self.assertEqual("Research", finals[0].name)
        self.assertEqual(3, models[self.leader_agent.data.name].cnt)
        self.assertEqual(4, models["Research"].cnt)
        self.assertEqual(1, sum((m.get_text_content() or "").strip() == "No alternatives were returned." for m in messages))
        self.assertEqual(1, models["Verifier"].cnt)
        customer_events = [call.args[2] for call in publisher.call_args_list if call.args[1] == root.id]
        self.assertNotIn("PRIVATE-MEMBER-REASONING", json.dumps(customer_events))
        self.assertNotIn("PRIVATE-UNVERIFIED-DRAFT", json.dumps(customer_events))
        self.assertTrue(all(k["peer_collaboration"] for k in captured))
        snapshot = await self.storage.get_team_shared_context(self.user_id, team.id)
        self.assertTrue(any(e.kind == "result" and e.source_agent_id == workers[0].id for e in snapshot.state.events))
