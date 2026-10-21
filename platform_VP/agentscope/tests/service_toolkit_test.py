# -*- coding: utf-8 -*-
# pylint: disable=protected-access
"""Tests for :func:`get_toolkit` — the single entry point that assembles
the per-chat-turn :class:`Toolkit` from every tool source the framework
manages.

Verifies the assembly rules:

- workspace builtins are always included;
- the four ``Task*`` planning tools are always included;
- :class:`ToolStop` (from ``BackgroundTaskManager``) is always included;
- the four ``Schedule*`` tools only when ``session.config.chat_model_config``
  is set (they need a model to fire new runs with);
- team tools are identity- and role-gated: only the fixed leader can manage a
  team; business agents get ``TeamSay`` only while in a team. ``AgentCreate``
  is never exposed in chat runtime;
- caller-supplied ``extra_factory`` results land at the end.
"""
from types import SimpleNamespace
from typing import Any
import os
from unittest import IsolatedAsyncioTestCase
from unittest.mock import AsyncMock, patch

from utils import FakeWorkspaceManager

from agentscope.agent import ContextConfig, ReActConfig
from agentscope.app._manager import (
    BackgroundTaskManager,
    SchedulerManager,
)
from agentscope.app._service import ResourceAccessService, get_toolkit
from agentscope.app._shared_context import SharedContextService
from agentscope.app.access import DenyAllResourceAccessPolicy
from agentscope.app.storage import (
    AgentData,
    AgentRecord,
    ChatModelConfig,
    InviteConfig,
    SessionConfig,
    SessionRecord,
)
from agentscope.mcp import HttpMCPConfig, MCPClient
from agentscope.message import ToolCallBlock, ToolResultState
from agentscope.state import AgentState
from agentscope.tool import Bash, Edit, Glob, Grep, PowerShell, Read, ToolBase, Write


class _FakeWorkspace:
    """Stand-in for a resolved :class:`WorkspaceBase` — only the three
    methods :func:`get_toolkit` calls are implemented."""

    def __init__(
        self,
        tools: list[ToolBase] | None = None,
        skills: list | None = None,
        mcps: list | None = None,
    ) -> None:
        self._tools = tools or []
        self._skills = skills or []
        self._mcps = mcps or []

    async def list_tools(self) -> list[ToolBase]:
        """Return the configured workspace tools."""
        return list(self._tools)

    async def list_skills(
        self,
        agent_id: str,  # pylint: disable=unused-argument
    ) -> list:
        """Return the configured workspace skills."""
        return list(self._skills)

    async def list_mcps(
        self,
        agent_id: str,  # pylint: disable=unused-argument
        session_id: str,  # pylint: disable=unused-argument
    ) -> list:
        """Return the configured workspace MCP descriptors."""
        return list(self._mcps)


class _NullBus:
    """``MessageBus`` placeholder. Team tools only carry the reference;
    nothing in :func:`get_toolkit` actually awaits it."""


def _make_agent(*, source: str = "user", name: str = "A") -> AgentRecord:
    """Build a minimal :class:`AgentRecord`."""
    return AgentRecord(
        user_id="u",
        source=source,
        data=AgentData(
            name=name,
            system_prompt=f"You are {name}.",
            context_config=ContextConfig(),
            react_config=ReActConfig(),
        ),
    )


def _make_session(
    *,
    user_id: str,
    agent_id: str,
    with_model: bool,
    team_id: str | None = None,
) -> SessionRecord:
    """Build a minimal :class:`SessionRecord`, optionally with a chat
    model config."""
    cfg = SessionConfig(
        workspace_id="ws",
        chat_model_config=(
            ChatModelConfig(
                type="dashscope_credential",
                credential_id="c",
                model="m",
                parameters={},
            )
            if with_model
            else None
        ),
    )
    return SessionRecord(
        user_id=user_id,
        agent_id=agent_id,
        config=cfg,
        team_id=team_id,
    )


class _NoOpStorage:
    """Storage placeholder. ``get_toolkit`` itself does not call any
    storage method — the team tools bind a reference for later use.

    Exceptions: since :class:`AgentInvite` landed, ``get_toolkit`` calls
    ``ResourceAccessService.list_resource`` at assembly time to build
    the invitable pool, which fans out to
    :meth:`StorageBase.list_agents` under the hood. Return an empty
    list — the toolkit tests care about which team tools are attached,
    not about the pool contents; the non-empty case is covered by the
    ``AgentInvite`` tests in ``service_team_tools_test.py``.
    """

    async def list_agents(self, _user_id: str) -> list:
        """List agents for a team."""
        return []

    async def list_mcps(self, _user_id: str) -> list:
        """Library records, read for signed-in MCPs' current OAuth tokens
        whenever the workspace holds MCPs. None are signed in here."""
        return []


class _AgentListStorage(_NoOpStorage):
    """Storage stub exposing a controlled runtime agent catalog."""

    def __init__(self, agents: list[AgentRecord]) -> None:
        self._agents = agents

    async def list_agents(self, _user_id: str) -> list[AgentRecord]:
        return self._agents


def _make_access(storage: Any) -> ResourceAccessService:
    """Build a :class:`ResourceAccessService` bound to ``storage`` with a
    deny-all policy for ``get_toolkit`` tests.

    ``list_resource(AGENT)`` therefore fans out to
    ``storage.list_agents(user_id)`` alone — matching the pre-share
    behaviour the toolkit tests were written against.
    """
    return ResourceAccessService(
        storage=storage,
        policy=DenyAllResourceAccessPolicy(),
    )


def _tool_names(toolkit: Any) -> list[str]:
    """Extract every registered tool name from a :class:`Toolkit`,
    walking its tool groups."""
    return [t.name for group in toolkit.tool_groups for t in group.tools]


class _StubTool(ToolBase):
    """Minimal :class:`ToolBase` subclass that satisfies the abstract
    methods so :func:`get_toolkit` can register the instance.

    Sub-classes override ``name`` and ``description``; nothing in the
    tests actually calls the tool, so the implementations are no-ops.
    """

    name: str = "stub"
    description: str = "stub tool"
    input_schema: dict = {}
    is_concurrency_safe: bool = True
    is_read_only: bool = False
    is_state_injected: bool = False
    is_external_tool: bool = False
    is_mcp: bool = False
    mcp_name: str | None = None

    async def check_permissions(self, *args: Any, **kwargs: Any) -> None:
        """No-op permission check — the tests do not exercise it."""

    async def __call__(self, *args: Any, **kwargs: Any) -> None:
        """No-op invocation — the tests never execute the tool."""


class TestGetToolkitBaseAssembly(IsolatedAsyncioTestCase):
    """User-owned agent (``source="user"``) gets the full set."""

    async def test_legacy_business_agents_do_not_receive_host_tools(self):
        host_tools = {"Bash", "PowerShell", "Read", "Write", "Edit", "Glob", "Grep"}
        mcp = MCPClient(
            name="hotel", is_stateful=False,
            mcp_config=HttpMCPConfig(url="https://example.test/mcp"),
        )
        for lifecycle, team_role in (("draft", "worker"), ("published", None)):
            with self.subTest(lifecycle=lifecycle, team_role=team_role):
                agent = _make_agent()
                agent.data.lifecycle_state = lifecycle
                self.assertIsNone(agent.data.execution_mode)
                self.assertEqual(agent.data.tool_bindings, [])
                storage = _NoOpStorage()
                toolkit = await get_toolkit(
                    storage=storage,
                    workspace=_FakeWorkspace(
                        tools=[Bash(), PowerShell(), Read(), Write(), Edit(), Glob(), Grep()],
                        mcps=[mcp],
                    ),
                    workspace_manager=FakeWorkspaceManager(),
                    scheduler_manager=SchedulerManager(
                        storage=storage, message_bus=_NullBus(),
                        workspace_manager=FakeWorkspaceManager(),
                    ),
                    background_task_manager=BackgroundTaskManager(message_bus=_NullBus()),
                    message_bus=_NullBus(),
                    user_id="u", agent_record=agent,
                    session_record=_make_session(
                        user_id="u", agent_id=agent.id, with_model=True,
                    ),
                    middlewares=[], resource_access_service=_make_access(storage),
                    team_role=team_role,
                )
                names = set(_tool_names(toolkit))
                self.assertTrue(host_tools.isdisjoint(names))
                self.assertTrue(
                    {"TaskCreate", "TaskList", "TaskGet", "TaskUpdate", "ToolStop",
                     "ScheduleCreate", "ScheduleList", "ScheduleView", "ScheduleDelete"}
                    .isdisjoint(names),
                )
                self.assertEqual("TeamSay" in names, team_role == "worker")
                self.assertEqual(toolkit.tool_groups[0].mcps, [mcp])

    async def test_workforce_runtime_omits_unrelated_coding_and_task_tools(self):
        for leader in (False, True):
            agent = _make_agent()
            agent.data.system_role = "leader" if leader else "business"
            if not leader:
                agent.data.tool_bindings = [{"mcp_id": "m", "tool_name": "lookup"}]
            storage = _NoOpStorage()
            toolkit = await get_toolkit(
                storage=storage,
                workspace=_FakeWorkspace(tools=[_StubTool()]),
                workspace_manager=FakeWorkspaceManager(),
                scheduler_manager=SchedulerManager(
                    storage=storage,
                    message_bus=_NullBus(),
                    workspace_manager=FakeWorkspaceManager(),
                ),
                background_task_manager=BackgroundTaskManager(
                    message_bus=_NullBus(),
                ),
                message_bus=_NullBus(),
                user_id="u",
                agent_record=agent,
                session_record=_make_session(
                    user_id="u",
                    agent_id=agent.id,
                    with_model=True,
                ),
                middlewares=[],
                resource_access_service=_make_access(storage),
                team_role=None if leader else "worker",
                shared_context_service=SharedContextService(storage, _NullBus()),
            )
            names = set(_tool_names(toolkit))
            self.assertTrue(
                names.isdisjoint(
                    {
                        "stub",
                        "TaskCreate",
                        "TaskUpdate",
                        "ScheduleCreate",
                        "ToolStop",
                    },
                ),
            )
            self.assertIn("TeamSay", names)
            self.assertIn("SharedContextRead", names)
            manager_tools = {"TeamCreate", "TeamDelete", "AgentInvite"}
            if leader:
                self.assertTrue({"TeamCreate", "TeamDelete"} <= names)
            else:
                self.assertTrue(manager_tools.isdisjoint(names))
            self.assertNotIn("AgentCreate", names)

    async def test_toolless_builder_agent_keeps_restricted_runtime(self):
        agent = _make_agent()
        agent.data.execution_mode = "context_only"
        agent.data.evaluation = {
            "passed": True,
            "execution_mode": "context_only",
        }
        storage = _NoOpStorage()
        default_mcp = MCPClient(
            name="default-search",
            is_stateful=False,
            mcp_config=HttpMCPConfig(url="https://example.test/mcp"),
        )
        toolkit = await get_toolkit(
            storage=storage,
            workspace=_FakeWorkspace(
                tools=[_StubTool()],
                mcps=[default_mcp],
            ),
            workspace_manager=FakeWorkspaceManager(),
            scheduler_manager=SchedulerManager(
                storage=storage,
                message_bus=_NullBus(),
                workspace_manager=FakeWorkspaceManager(),
            ),
            background_task_manager=BackgroundTaskManager(message_bus=_NullBus()),
            message_bus=_NullBus(),
            user_id="u",
            agent_record=agent,
            session_record=_make_session(
                user_id="u",
                agent_id=agent.id,
                with_model=True,
            ),
            middlewares=[],
            resource_access_service=_make_access(storage),
            team_role="worker",
        )

        names = set(_tool_names(toolkit))
        self.assertTrue(
            names.isdisjoint(
                {"stub", "TaskCreate", "TaskUpdate", "ScheduleCreate", "ToolStop"},
            ),
        )
        self.assertIn("TeamSay", names)
        self.assertEqual(toolkit.tool_groups[0].mcps, [])

    async def _user_agent_tool_names(self) -> set:
        """Tool names a standalone user agent gets from a workspace whose
        only tool is a stub shell."""
        agent = _make_agent(source="user")
        session = _make_session(user_id="u", agent_id=agent.id, with_model=True)

        class _WsTool(_StubTool):
            name: str = "ws-bash"
            description: str = "stub workspace tool"

        toolkit = await get_toolkit(
            storage=_NoOpStorage(),  # type: ignore[arg-type]
            workspace=_FakeWorkspace(tools=[_WsTool()]),  # type: ignore[arg-type]
            workspace_manager=FakeWorkspaceManager(),
            scheduler_manager=SchedulerManager(
                storage=_NoOpStorage(),  # type: ignore[arg-type]
                message_bus=_NullBus(),  # type: ignore[arg-type]
                workspace_manager=FakeWorkspaceManager(),
            ),
            background_task_manager=BackgroundTaskManager(
                message_bus=_NullBus(),  # type: ignore[arg-type]
            ),
            message_bus=_NullBus(),  # type: ignore[arg-type]
            user_id="u",
            agent_record=agent,
            session_record=session,
            extra_factory=None,
            middlewares=[],
            resource_access_service=_make_access(_NoOpStorage()),
        )
        return set(_tool_names(toolkit))

    @patch.dict(os.environ, {"AGENT_WORKSPACE_TOOLS": ""})
    async def test_user_agent_gets_no_host_tools_by_default(self) -> None:
        """Shell/file tools run on the host, so an open platform hands out
        none of them (nor ToolStop, which only controls them)."""
        names = await self._user_agent_tool_names()

        self.assertNotIn("ws-bash", names)
        self.assertNotIn("ToolStop", names)
        self.assertTrue({"TaskCreate", "TaskList", "TaskGet", "TaskUpdate"} <= names)

    @patch.dict(os.environ, {"AGENT_WORKSPACE_TOOLS": "true"})
    async def test_user_agent_gets_all_sources(self) -> None:
        """A user-owned agent receives workspace, planning, scheduling,
        and ToolStop, but no team tools while standalone. (Host tools are
        enabled here, as on a trusted single-tenant host.)"""
        agent = _make_agent(source="user")
        session = _make_session(
            user_id="u",
            agent_id=agent.id,
            with_model=True,
        )

        class _WsTool(_StubTool):
            """Stub workspace tool registered through ``_FakeWorkspace``."""

            name: str = "ws-bash"
            description: str = "stub workspace tool"

        ws_tool = _WsTool()
        workspace = _FakeWorkspace(tools=[ws_tool])

        toolkit = await get_toolkit(
            storage=_NoOpStorage(),  # type: ignore[arg-type]
            workspace=workspace,  # type: ignore[arg-type]
            workspace_manager=FakeWorkspaceManager(),
            scheduler_manager=SchedulerManager(
                storage=_NoOpStorage(),  # type: ignore[arg-type]
                message_bus=_NullBus(),  # type: ignore[arg-type]
                workspace_manager=FakeWorkspaceManager(),
            ),
            background_task_manager=BackgroundTaskManager(
                message_bus=_NullBus(),  # type: ignore[arg-type]
            ),
            message_bus=_NullBus(),  # type: ignore[arg-type]
            user_id="u",
            agent_record=agent,
            session_record=session,
            extra_factory=None,
            middlewares=[],
            resource_access_service=_make_access(_NoOpStorage()),
        )

        names = set(_tool_names(toolkit))
        # Workspace tool present.
        self.assertIn("ws-bash", names)
        # Planning tools present.
        self.assertTrue(
            {"TaskCreate", "TaskList", "TaskGet", "TaskUpdate"} <= names,
        )
        # Background task control present.
        self.assertIn("ToolStop", names)
        # Schedule control present (model_config is set).
        self.assertTrue(
            {
                "ScheduleCreate",
                "ScheduleView",
                "ScheduleDelete",
                "ScheduleList",
            }
            <= names,
        )
        # A standalone business agent cannot create or coordinate a team.
        self.assertTrue(
            {"TeamCreate", "TeamSay", "TeamDelete", "AgentInvite"}.isdisjoint(
                names,
            ),
        )
        self.assertNotIn("AgentCreate", names)


class TestGetToolkitPublishedAgentCatalog(IsolatedAsyncioTestCase):
    """Leader runtime can invite only Builder-published business agents."""

    async def test_invite_catalog_excludes_draft_and_withdrawn_agents(
        self,
    ) -> None:
        caller = _make_agent(source="user", name="Leader")
        caller.data.system_role = "leader"
        published = _make_agent(source="user", name="Published")
        draft = _make_agent(source="user", name="Draft")
        withdrawn = _make_agent(source="user", name="Withdrawn")
        for agent, lifecycle in (
            (published, "published"),
            (draft, "draft"),
            (withdrawn, "withdrawn"),
        ):
            agent.data.lifecycle_state = lifecycle
            agent.data.invite_config = InviteConfig(
                invitable=True,
                invite_description=f"{agent.data.name} capability",
            )
        storage = _AgentListStorage([caller, published, draft, withdrawn])
        session = _make_session(
            user_id="u",
            agent_id=caller.id,
            with_model=True,
        )

        toolkit = await get_toolkit(
            storage=storage,  # type: ignore[arg-type]
            workspace=_FakeWorkspace(),  # type: ignore[arg-type]
            workspace_manager=FakeWorkspaceManager(),
            scheduler_manager=SchedulerManager(
                storage=storage,  # type: ignore[arg-type]
                message_bus=_NullBus(),  # type: ignore[arg-type]
                workspace_manager=FakeWorkspaceManager(),
            ),
            background_task_manager=BackgroundTaskManager(
                message_bus=_NullBus(),  # type: ignore[arg-type]
            ),
            message_bus=_NullBus(),  # type: ignore[arg-type]
            user_id="u",
            agent_record=caller,
            session_record=session,
            extra_factory=None,
            middlewares=[],
            resource_access_service=_make_access(storage),
        )

        invite = next(
            tool
            for group in toolkit.tool_groups
            for tool in group.tools
            if tool.name == "AgentInvite"
        )
        self.assertEqual(
            invite.input_schema["properties"]["target"]["enum"],
            [f"Published@{published.id[:8]}"],
        )
        self.assertNotIn("AgentCreate", _tool_names(toolkit))


class TestGetToolkitWorkerVariant(IsolatedAsyncioTestCase):
    """A session passed ``team_role="worker"`` only gets ``TeamSay``;
    the role is resolved by the caller, not looked up here."""

    async def test_worker_only_gets_team_say(self) -> None:
        """A worker session receives only ``TeamSay`` from the team
        toolset."""
        agent = _make_agent(source="team", name="worker")
        session = _make_session(
            user_id="u",
            agent_id=agent.id,
            with_model=True,
            team_id="t1",
        )
        toolkit = await get_toolkit(
            storage=_NoOpStorage(),  # type: ignore[arg-type]
            workspace=_FakeWorkspace(),  # type: ignore[arg-type]
            workspace_manager=FakeWorkspaceManager(),
            scheduler_manager=SchedulerManager(
                storage=_NoOpStorage(),  # type: ignore[arg-type]
                message_bus=_NullBus(),  # type: ignore[arg-type]
                workspace_manager=FakeWorkspaceManager(),
            ),
            background_task_manager=BackgroundTaskManager(
                message_bus=_NullBus(),  # type: ignore[arg-type]
            ),
            message_bus=_NullBus(),  # type: ignore[arg-type]
            user_id="u",
            agent_record=agent,
            session_record=session,
            extra_factory=None,
            middlewares=[],
            resource_access_service=_make_access(_NoOpStorage()),
            team_role="worker",
            is_reply_owner=True,
        )
        team_say = next(
            schema for schema in await toolkit.get_tool_schemas()
            if schema["function"]["name"] == "TeamSay"
        )
        self.assertIn("resolution", team_say["function"]["parameters"]["properties"])
        names = set(_tool_names(toolkit))
        # Only TeamSay from the team toolset.
        self.assertIn("TeamSay", names)
        for missing in (
            "TeamCreate",
            "AgentCreate",
            "TeamDelete",
            "AgentInvite",
        ):
            self.assertNotIn(missing, names)


class TestGetToolkitSchedulingGuard(IsolatedAsyncioTestCase):
    """``Schedule*`` tools are only attached when the session has a
    model configured."""

    async def test_no_schedule_tools_without_model_config(self) -> None:
        """Without a ``chat_model_config`` on the session, the four
        ``Schedule*`` tools are omitted from the toolkit."""
        agent = _make_agent(source="user")
        session = _make_session(
            user_id="u",
            agent_id=agent.id,
            with_model=False,
        )
        toolkit = await get_toolkit(
            storage=_NoOpStorage(),  # type: ignore[arg-type]
            workspace=_FakeWorkspace(),  # type: ignore[arg-type]
            workspace_manager=FakeWorkspaceManager(),
            scheduler_manager=SchedulerManager(
                storage=_NoOpStorage(),  # type: ignore[arg-type]
                message_bus=_NullBus(),  # type: ignore[arg-type]
                workspace_manager=FakeWorkspaceManager(),
            ),
            background_task_manager=BackgroundTaskManager(
                message_bus=_NullBus(),  # type: ignore[arg-type]
            ),
            message_bus=_NullBus(),  # type: ignore[arg-type]
            user_id="u",
            agent_record=agent,
            session_record=session,
            extra_factory=None,
            middlewares=[],
            resource_access_service=_make_access(_NoOpStorage()),
        )
        names = set(_tool_names(toolkit))
        for missing in (
            "ScheduleCreate",
            "ScheduleView",
            "ScheduleDelete",
            "ScheduleList",
        ):
            self.assertNotIn(missing, names)


class TestGetToolkitExtraFactory(IsolatedAsyncioTestCase):
    """Tools returned by ``extra_factory`` end up in the final toolkit."""

    async def test_extra_factory_tools_are_attached(self) -> None:
        """Tools returned by ``extra_factory`` end up in the final
        toolkit alongside the framework-builtin ones."""

        class _ExtraTool(_StubTool):
            """Stub tool emitted by the ``extra_factory`` callback."""

            name: str = "my-extra"
            description: str = "stub extra tool"
            input_schema = {"type": "object", "properties": {}}

        extra_tool = _ExtraTool()

        class _RenamedBash(Bash):
            name = "host_command"

        host_tools = [Bash(), PowerShell(), Read(), Write(), Edit(), Glob(), Grep(), _RenamedBash()]

        async def factory(
            _user_id: str,
            _agent_id: str,
            _session_id: str,
        ) -> list[ToolBase]:
            """Stub extra-factory that always returns ``extra_tool``."""
            return [extra_tool, *host_tools]

        agent = _make_agent()
        session = _make_session(
            user_id="u",
            agent_id=agent.id,
            with_model=True,
        )
        toolkit = await get_toolkit(
            storage=_NoOpStorage(),  # type: ignore[arg-type]
            workspace=_FakeWorkspace(tools=host_tools),
            workspace_manager=FakeWorkspaceManager(),
            scheduler_manager=SchedulerManager(
                storage=_NoOpStorage(),  # type: ignore[arg-type]
                message_bus=_NullBus(),  # type: ignore[arg-type]
                workspace_manager=FakeWorkspaceManager(),
            ),
            background_task_manager=BackgroundTaskManager(
                message_bus=_NullBus(),  # type: ignore[arg-type]
            ),
            message_bus=_NullBus(),  # type: ignore[arg-type]
            user_id="u",
            agent_record=agent,
            session_record=session,
            extra_factory=factory,
            middlewares=[
                SimpleNamespace(list_tools=AsyncMock(return_value=host_tools)),
            ],
            channel_tools=host_tools,
            resource_access_service=_make_access(_NoOpStorage()),
        )
        self.assertIn("my-extra", _tool_names(toolkit))
        with patch("asyncio.create_subprocess_exec", new_callable=AsyncMock) as spawn:
            for tool in host_tools:
                self.assertNotIn(tool.name, _tool_names(toolkit))
                results = [result async for result in toolkit.call_tool(
                    ToolCallBlock(id="blocked-call", name=tool.name, input='{"command":"sudo id"}'),
                    AgentState(),
                )]
                self.assertEqual(results[-1].state, ToolResultState.ERROR)
            spawn.assert_not_awaited()
