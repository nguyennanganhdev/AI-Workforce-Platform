# -*- coding: utf-8 -*-
# pylint: disable=protected-access, using-constant-test
"""ChatService resolves team/channel context once and fans it out."""

from collections.abc import AsyncGenerator
from types import SimpleNamespace
from unittest import IsolatedAsyncioTestCase
from unittest.mock import patch

from agentscope.agent import ContextConfig, ReActConfig
from agentscope.app._bus_ops import deliver_to_inbox
from agentscope.app._service import ChatService
from agentscope.app._service._chat import _team_chat_message
from agentscope.app.message_bus import InMemoryMessageBus, MessageBusKeys
from agentscope.app.storage import (
    AgentData,
    AgentRecord,
    ChatModelConfig,
    SessionConfig,
    SessionRecord,
    TeamData,
    TeamMember,
    TeamRecord,
    TeamSharedContextRecord,
    TeamTurnRecord,
)
from agentscope.event import (
    HintBlockEvent,
    ReplyEndEvent,
    ReplyStartEvent,
    TextBlockDeltaEvent,
    TextBlockEndEvent,
    TextBlockStartEvent,
    ThinkingBlockDeltaEvent,
    ThinkingBlockEndEvent,
    ThinkingBlockStartEvent,
)
from agentscope.message import AssistantMsg, HintBlock, UserMsg
from agentscope.types import ReplyFinishedReason


class _Storage:
    """Serve one worker session + its team/leader, counting team reads."""

    def __init__(
        self,
        sessions: dict[str, SessionRecord],
        agents: dict[str, AgentRecord],
        team: TeamRecord,
    ) -> None:
        self.sessions = sessions
        self.agents = agents
        self.team = team
        self.get_team_calls = 0
        self.primary_shared_reads = 0
        self.shared_context: TeamSharedContextRecord | None = None
        self.team_turn: TeamTurnRecord | None = None
        self.messages = {}

    async def get_session(
        self,
        user_id: str,
        agent_id: str,
        session_id: str,
    ) -> SessionRecord | None:
        """Return a detached copy; ``agent_id`` may be blank for leaders."""
        del user_id, agent_id
        record = self.sessions.get(session_id)
        return record.model_copy(deep=True) if record else None

    async def get_agent(
        self,
        user_id: str,
        agent_id: str,
    ) -> AgentRecord | None:
        """Return a detached agent record."""
        del user_id
        record = self.agents.get(agent_id)
        return record.model_copy(deep=True) if record else None

    async def get_team(self, user_id: str, team_id: str) -> TeamRecord | None:
        """Count every read — the run must need exactly one."""
        del user_id
        self.get_team_calls += 1
        return self.team if team_id == self.team.id else None

    async def update_session_state(self, *_: object, **__: object) -> None:
        """Accept the post-run state persistence."""

    async def upsert_message(self, user_id, session_id, message) -> None:
        self.messages[(session_id, message.id)] = message.model_copy(deep=True)

    async def list_messages(self, *_: object, **__: object) -> tuple[list, bool]:
        """The fixture has no pre-shared customer transcript."""
        return [], False

    async def get_team_shared_context(
        self,
        user_id: str,
        team_id: str,
    ) -> TeamSharedContextRecord | None:
        """Return the detached team context used by the runtime packet."""
        del user_id
        self.primary_shared_reads += 1
        if self.shared_context is None or self.shared_context.team_id != team_id:
            return None
        return self.shared_context.model_copy(deep=True)

    async def upsert_team_shared_context(
        self,
        user_id: str,
        record: TeamSharedContextRecord,
    ) -> TeamSharedContextRecord:
        """Persist the team context for this unit-test fake."""
        del user_id
        self.shared_context = record.model_copy(deep=True)
        return record

    async def compare_and_swap_team_shared_context(
        self, _user_id: str, record: TeamSharedContextRecord, expected_revision: int
    ) -> bool:
        if (self.shared_context.state.revision if self.shared_context else 0) != expected_revision:
            return False
        self.shared_context = record.model_copy(deep=True)
        return True

    async def get_team_turn(self, _user_id: str, _team_id: str):
        return self.team_turn.model_copy(deep=True) if self.team_turn else None

    async def upsert_team_turn(self, _user_id: str, record: TeamTurnRecord):
        self.team_turn = record.model_copy(deep=True)
        return record

    async def list_outstanding_team_handoffs(self, **_kwargs):
        return []


class _WorkspaceManager:
    """Return a minimal workspace handle."""

    async def get_workspace(self, *_: object, **__: object) -> object:
        """Return an inert workspace."""
        return SimpleNamespace(workdir="/tmp/agentscope-run-ctx-test")


class _SharedStorage:
    """Dedicated canonical store used only by SharedContextService."""

    def __init__(self) -> None:
        self.record: TeamSharedContextRecord | None = None
        self.reads = 0
        self.team_turn: TeamTurnRecord | None = None

    async def get_team_shared_context(
        self,
        user_id: str,
        team_id: str,
    ) -> TeamSharedContextRecord | None:
        del user_id
        self.reads += 1
        if self.record is None or self.record.team_id != team_id:
            return None
        return self.record.model_copy(deep=True)

    async def upsert_team_shared_context(
        self,
        user_id: str,
        record: TeamSharedContextRecord,
    ) -> TeamSharedContextRecord:
        del user_id
        self.record = record.model_copy(deep=True)
        return record

    async def compare_and_swap_team_shared_context(
        self, _user_id: str, record: TeamSharedContextRecord, expected_revision: int
    ) -> bool:
        if (self.record.state.revision if self.record else 0) != expected_revision:
            return False
        self.record = record.model_copy(deep=True)
        return True

    async def get_team_turn(self, _user_id: str, _team_id: str):
        return self.team_turn.model_copy(deep=True) if self.team_turn else None

    async def upsert_team_turn(self, _user_id: str, record: TeamTurnRecord):
        self.team_turn = record.model_copy(deep=True)
        return record

    async def list_outstanding_team_handoffs(self, **_kwargs):
        return []


class TestRunContextResolution(IsolatedAsyncioTestCase):
    """Team identity is read once and shared by toolkit + middleware."""

    def test_team_projection_marks_customer_reply_owner(self):
        reply = AssistantMsg(name="Hotel", content="Visible answer")

        projected = _team_chat_message(
            reply,
            "worker",
            "worker-session",
            is_reply_owner=True,
        )

        self.assertIs(projected.metadata["team_reply_owner"], True)
        self.assertEqual(projected.get_text_content(), "Visible answer")

    async def test_completed_turn_drops_automatic_leader_wakeup(self):
        leader = AgentRecord(
            id="leader",
            user_id="u",
            data=AgentData(
                name="Leader",
                context_config=ContextConfig(),
                react_config=ReActConfig(),
            ),
        )
        config = SessionConfig(
            workspace_id="ws",
            chat_model_config=ChatModelConfig(
                type="test",
                credential_id="cred",
                model="test",
                parameters={},
            ),
        )
        session = SessionRecord(
            id="leader-session",
            user_id="u",
            agent_id=leader.id,
            team_id="team",
            config=config,
        )
        team = TeamRecord(
            id="team",
            user_id="u",
            session_id=session.id,
            data=TeamData(name="Team"),
        )
        storage = _Storage({session.id: session}, {leader.id: leader}, team)
        shared_storage = _SharedStorage()
        shared_storage.team_turn = TeamTurnRecord(
            id=team.id,
            user_id="u",
            team_id=team.id,
            turn_id="finished-turn",
            reply_owner_session_id=session.id,
            reply_owner_agent_id=leader.id,
            customer_session_id=session.id,
            status="completed",
        )
        agent_was_built = False

        class _Agent:
            def __init__(self, **_kwargs):
                nonlocal agent_was_built
                agent_was_built = True

        class _Access:
            async def resolve_agent(self, *_args):
                return leader.model_copy(deep=True)

        service = ChatService(
            storage=storage,
            workspace_manager=_WorkspaceManager(),
            scheduler_manager=object(),
            background_task_manager=object(),
            message_bus=InMemoryMessageBus(),
            resource_access_service=_Access(),
            custom_agent_cls=_Agent,
            shared_context_storage=shared_storage,  # type: ignore[arg-type]
        )

        await service._run_impl("u", session.id, leader.id, None)

        self.assertFalse(agent_was_built)
        self.assertEqual({}, storage.messages)

    async def test_worker_feed_is_shared_and_racing_reply_starts_fresh_run(self):
        worker = AgentRecord(id="worker", user_id="u", data=AgentData(
            name="Hotel", context_config=ContextConfig(), react_config=ReActConfig(),
        ))
        leader = AgentRecord(id="leader", user_id="u", data=AgentData(
            name="Leader", context_config=ContextConfig(), react_config=ReActConfig(),
        ))
        config = SessionConfig(workspace_id="ws", chat_model_config=ChatModelConfig(
            type="test", credential_id="cred", model="test", parameters={},
        ))
        worker_session = SessionRecord(id="worker-session", user_id="u", agent_id=worker.id,
                                       team_id="team", config=config)
        leader_session = SessionRecord(id="leader-session", user_id="u", agent_id=leader.id,
                                       team_id="team", config=config)
        team = TeamRecord(id="team", user_id="u", session_id=leader_session.id,
                          data=TeamData(name="Trip", members=[TeamMember(
                              owner_id="u", agent_id=worker.id, session_id=worker_session.id,
                              role="created", description="Hotels",
                          )]))
        storage = _Storage({s.id: s for s in (worker_session, leader_session)},
                           {a.id: a for a in (worker, leader)}, team)
        shared_storage = _SharedStorage()
        bus = InMemoryMessageBus()
        reply_count = 0

        class _Agent:
            def __init__(self, *, state, **kwargs):
                self.state = state
                self.name = "Hotel"

            async def reply_stream(self, inputs):
                nonlocal reply_count
                reply_count += 1
                yield ReplyStartEvent(session_id=worker_session.id, reply_id="reply", name="Hotel")
                yield HintBlockEvent(reply_id="reply", block_id="hint", hint="private assignment")
                yield ThinkingBlockStartEvent(reply_id="reply", block_id="thinking")
                yield ThinkingBlockDeltaEvent(reply_id="reply", block_id="thinking", delta="private reasoning")
                yield ThinkingBlockEndEvent(reply_id="reply", block_id="thinking")
                yield TextBlockStartEvent(reply_id="reply", block_id="text")
                yield TextBlockDeltaEvent(reply_id="reply", block_id="text", delta="Hotel options ready")
                yield TextBlockEndEvent(reply_id="reply", block_id="text", text="Hotel options ready")
                # A fast peer responds before this run releases the consumer.
                await deliver_to_inbox(bus, user_id="u", session_id=worker_session.id,
                                       agent_id=worker.id, payload=HintBlock(hint="peer response").model_dump(mode="json"))
                yield ReplyEndEvent(session_id=worker_session.id, reply_id="reply")

        class _Model:
            context_size = 100_000

            async def count_tokens(self, messages, tools):
                return sum(len(msg.get_text_content() or "") for msg in messages)

        class _Access:
            async def resolve_agent(self, *args):
                return worker.model_copy(deep=True)

        async def _model(*args, **kwargs):
            return _Model()

        async def _toolkit(**kwargs):
            return object()

        service = ChatService(storage=storage, workspace_manager=_WorkspaceManager(),
                              scheduler_manager=object(), background_task_manager=object(),
                              message_bus=bus, resource_access_service=_Access(),
                              custom_agent_cls=_Agent, shared_context_storage=shared_storage)
        with patch("agentscope.app._service._chat.get_toolkit", new=_toolkit), \
             patch("agentscope.app._service._chat.get_model", new=_model):
            await service._run_impl("u", worker_session.id, worker.id, None)

        self.assertEqual(reply_count, 1)
        projected = storage.messages[(leader_session.id, "reply")]
        self.assertEqual(projected.name, "Hotel")
        self.assertEqual(projected.get_text_content(), "Hotel options ready")
        self.assertEqual(projected.metadata["team_agent_id"], worker.id)
        self.assertIs(projected.metadata["team_reply_owner"], False)
        self.assertFalse(projected.get_content_blocks("thinking"))
        self.assertFalse(projected.get_content_blocks("hint"))
        feed = [payload for _, payload in await bus.log_read(MessageBusKeys.session_events(leader_session.id))]
        self.assertEqual(feed[0]["type"], "REPLY_START")
        self.assertIs(feed[0]["metadata"]["team_reply_owner"], False)
        reply_events = [event for event in feed if event.get("reply_id") == "reply"]
        self.assertEqual(reply_events[-1]["type"], "REPLY_END")
        self.assertFalse(any(event["type"].startswith("THINKING") or event["type"] == "HINT_BLOCK" for event in feed))
        wakeups = await bus.queue_drain(MessageBusKeys.wakeup_queue())
        self.assertEqual(len(wakeups), 1)
        self.assertEqual(wakeups[0][1]["session_id"], worker_session.id)
        self.assertFalse(await bus.is_locked(MessageBusKeys.session_lock(worker_session.id)))

    async def test_worker_run_fetches_team_once(self) -> None:
        """One ``get_team`` read serves both consumers of the role."""
        user_id = "user-1"
        worker_agent = AgentRecord(
            id="agent-w",
            user_id=user_id,
            source="team",
            data=AgentData(
                name="worker",
                context_config=ContextConfig(),
                react_config=ReActConfig(),
            ),
        )
        leader_agent = AgentRecord(
            id="agent-l",
            user_id=user_id,
            data=AgentData(
                name="Leader",
                context_config=ContextConfig(),
                react_config=ReActConfig(),
            ),
        )
        peer_agent = AgentRecord(
            id="agent-p",
            user_id=user_id,
            source="team",
            data=AgentData(
                name="pricing",
                context_config=ContextConfig(),
                react_config=ReActConfig(),
            ),
        )
        config = SessionConfig(
            workspace_id="ws-1",
            chat_model_config=ChatModelConfig(
                type="test",
                credential_id="cred-1",
                model="m",
                parameters={},
            ),
        )
        worker_session = SessionRecord(
            id="session-w",
            user_id=user_id,
            agent_id=worker_agent.id,
            team_id="team-1",
            config=config,
        )
        leader_session = SessionRecord(
            id="session-l",
            user_id=user_id,
            agent_id=leader_agent.id,
            team_id="team-1",
            config=config,
        )
        team = TeamRecord(
            id="team-1",
            user_id=user_id,
            session_id=leader_session.id,
            data=TeamData(
                name="team",
                members=[
                    TeamMember(
                        owner_id=user_id,
                        agent_id=worker_agent.id,
                        session_id=worker_session.id,
                        role="created",
                        description="Finds inventory.",
                    ),
                    TeamMember(
                        owner_id=user_id,
                        agent_id=peer_agent.id,
                        session_id="session-p",
                        role="created",
                        description="Calculates and compares prices.",
                    ),
                ],
            ),
        )
        storage = _Storage(
            sessions={s.id: s for s in (worker_session, leader_session)},
            agents={
                a.id: a for a in (worker_agent, leader_agent, peer_agent)
            },
            team=team,
        )
        shared_storage = _SharedStorage()
        equipped: list[list] = []
        equipped_context_configs: list[ContextConfig] = []
        equipped_system_prompts: list[str] = []

        class _Agent:
            """Capture the middlewares; reply without doing anything."""

            def __init__(
                self,
                *,
                middlewares: list,
                context_config: ContextConfig,
                system_prompt: str,
                **_: object,
            ) -> None:
                equipped.append(middlewares)
                equipped_context_configs.append(context_config)
                equipped_system_prompts.append(system_prompt)

            async def reply_stream(
                self,
                inputs: object,
            ) -> AsyncGenerator[object, None]:
                """Yield nothing."""
                del inputs
                if False:
                    yield object()

        toolkit_kwargs: dict = {}

        async def _get_toolkit(**kwargs: object) -> object:
            toolkit_kwargs.update(kwargs)
            return object()

        class _Model:
            context_size = 100_000

            async def count_tokens(self, messages: list, tools: object) -> int:
                del tools
                return sum(len(msg.get_text_content() or "") for msg in messages)

        async def _get_model(*_: object, **__: object) -> object:
            return _Model()

        class _Access:
            """Resolve the one worker agent."""

            async def resolve_agent(self, *_: object) -> AgentRecord:
                """Return a detached copy."""
                return worker_agent.model_copy(deep=True)

        service = ChatService(
            storage=storage,
            workspace_manager=_WorkspaceManager(),
            scheduler_manager=object(),
            background_task_manager=object(),
            message_bus=InMemoryMessageBus(),
            resource_access_service=_Access(),
            custom_agent_cls=_Agent,
            shared_context_storage=shared_storage,  # type: ignore[arg-type]
        )
        with (
            patch(
                "agentscope.app._service._chat.get_toolkit",
                new=_get_toolkit,
            ),
            patch("agentscope.app._service._chat.get_model", new=_get_model),
        ):
            await service._run_impl(
                user_id,
                worker_session.id,
                worker_agent.id,
                None,
            )

        self.assertDictEqual(
            {
                "get_team_calls": storage.get_team_calls,
                "team_role": toolkit_kwargs["team_role"],
                "channel_tools": toolkit_kwargs["channel_tools"],
                "fallback_to_truncation": equipped_context_configs[
                    0
                ].compression_fallback_to_truncation,
                "retry_drop_oldest": equipped_context_configs[
                    0
                ].compression_retry_drop_oldest,
                "shared_packet_in_private_system_prompt": (
                    "<shared-context-packet" in equipped_system_prompts[0]
                ),
                "leader_names": [
                    mw._leader_name
                    for mws in equipped
                    for mw in mws
                    if hasattr(mw, "_leader_name")
                ],
            },
            {
                "get_team_calls": 1,
                "team_role": "worker",
                "channel_tools": [],
                "fallback_to_truncation": True,
                "retry_drop_oldest": False,
                "shared_packet_in_private_system_prompt": False,
                "leader_names": ["Leader"],
            },
        )
        self.assertGreater(shared_storage.reads, 0)
        self.assertIn('"source": "platform_chat"', equipped_system_prompts[0])
        self.assertIn(leader_session.id, equipped_system_prompts[0])
        self.assertIn("person typing here IS the user", equipped_system_prompts[0])
        self.assertIn("Finds inventory.", equipped_system_prompts[0])
        self.assertIn("Calculates and compares prices.", equipped_system_prompts[0])
        self.assertIn('"handle": "pricing"', equipped_system_prompts[0])
        self.assertEqual(storage.primary_shared_reads, 0)

    async def test_first_leader_reply_creates_turn_without_false_customer_wait(
        self,
    ) -> None:
        """An empty delegation reply must not pause peer wakeups as customer intake."""
        user_id = "user-1"
        leader_agent = AgentRecord(
            id="agent-l",
            user_id=user_id,
            data=AgentData(
                name="Leader",
                context_config=ContextConfig(),
                react_config=ReActConfig(),
            ),
        )
        config = SessionConfig(
            workspace_id="ws-1",
            chat_model_config=ChatModelConfig(
                type="test",
                credential_id="cred-1",
                model="m",
                parameters={},
            ),
        )
        leader_session = SessionRecord(
            id="session-l",
            user_id=user_id,
            agent_id=leader_agent.id,
            config=config,
        )
        team = TeamRecord(
            id="team-1",
            user_id=user_id,
            session_id=leader_session.id,
            data=TeamData(name="team"),
        )
        storage = _Storage(
            sessions={leader_session.id: leader_session},
            agents={leader_agent.id: leader_agent},
            team=team,
        )
        shared_storage = _SharedStorage()

        class _Agent:
            """Create the team during the first Leader reply."""

            def __init__(self, *, state: object, **_: object) -> None:
                self.state = state

            async def reply_stream(
                self,
                inputs: object,
            ) -> AsyncGenerator[object, None]:
                del inputs
                storage.sessions[leader_session.id].team_id = team.id
                yield ReplyStartEvent(
                    reply_id="reply-1",
                    session_id=leader_session.id,
                    name="Leader",
                )
                yield ReplyEndEvent(
                    reply_id="reply-1",
                    session_id=leader_session.id,
                    name="Leader",
                    finished_reason=ReplyFinishedReason.COMPLETED,
                )

        async def _get_toolkit(**_: object) -> object:
            return object()

        class _Model:
            context_size = 100_000

            async def count_tokens(self, messages: list, tools: object) -> int:
                del tools
                return sum(len(msg.get_text_content() or "") for msg in messages)

        async def _get_model(*_: object, **__: object) -> object:
            return _Model()

        class _Access:
            async def resolve_agent(self, *_: object) -> AgentRecord:
                return leader_agent.model_copy(deep=True)

        service = ChatService(
            storage=storage,
            workspace_manager=_WorkspaceManager(),
            scheduler_manager=object(),
            background_task_manager=object(),
            message_bus=InMemoryMessageBus(),
            resource_access_service=_Access(),
            custom_agent_cls=_Agent,
            shared_context_storage=shared_storage,  # type: ignore[arg-type]
        )
        with (
            patch(
                "agentscope.app._service._chat.get_toolkit",
                new=_get_toolkit,
            ),
            patch("agentscope.app._service._chat.get_model", new=_get_model),
        ):
            await service._run_impl(
                user_id,
                leader_session.id,
                leader_agent.id,
                UserMsg("user", "plan my trip"),
            )

        self.assertIsNotNone(shared_storage.record)
        self.assertIsNotNone(shared_storage.team_turn)
        assert shared_storage.record is not None
        assert shared_storage.team_turn is not None
        self.assertEqual(shared_storage.team_turn.status, "running")
        self.assertEqual(
            shared_storage.team_turn.task_id,
            shared_storage.record.state.active_task_id,
        )
        customer_events = [
            event
            for event in shared_storage.record.state.events
            if event.kind == "customer_message"
        ]
        self.assertEqual(len(customer_events), 1)
