# -*- coding: utf-8 -*-
"""The owner's per-tool policy: auto / ask / deny on top of the
platform's own check, in interactive and unattended runs, and the route
that sets it."""
from types import SimpleNamespace
from unittest import IsolatedAsyncioTestCase
from unittest.mock import AsyncMock

from fastapi import HTTPException
from utils import MockModel

from agentscope.app._router._agent import ToolPolicyRequest, set_tool_policy
from agentscope.app._service._chat import _current_tool_policies
from agentscope.app.middleware import ToolPolicyMiddleware
from agentscope.app.storage import AgentData, AgentRecord
from agentscope.agent import Agent, InjectionConfig
from agentscope.message import TextBlock, ToolCallBlock, ToolCallState, UserMsg
from agentscope.model import ChatResponse
from agentscope.tool import ToolBase, ToolChunk, Toolkit
from agentscope.permission import (
    PermissionBehavior,
    PermissionContext,
    PermissionDecision,
    PermissionEngine,
    PermissionMode,
    PermissionRule,
)

BOOK = "mcp__hotel__book_room"
SAFETY_ASK = PermissionDecision(
    behavior=PermissionBehavior.ASK,
    message="sensitive",
    bypass_immune=True,
)
ALLOW = PermissionDecision(behavior=PermissionBehavior.ALLOW, message="low risk")


class _Tool:
    def __init__(self, name: str) -> None:
        self.name = name

    async def match_rule(self, rule_content: str, input_data: dict) -> bool:
        del rule_content, input_data
        return True


def _agent(mode: PermissionMode = PermissionMode.DEFAULT, deny: bool = False) -> SimpleNamespace:
    engine = PermissionEngine(PermissionContext(mode=mode))
    if deny:
        engine.add_rule(
            PermissionRule(tool_name=BOOK, rule_content=None, behavior=PermissionBehavior.DENY, source="user"),
        )
    return SimpleNamespace(_engine=engine)


async def _check(
    policies: dict,
    platform: PermissionDecision,
    *,
    tool: str = BOOK,
    agent: SimpleNamespace | None = None,
    confirmed: bool = False,
) -> tuple[PermissionDecision, int]:
    calls = []

    async def next_handler(**_kwargs: object) -> PermissionDecision:
        calls.append(1)
        return platform

    call = ToolCallBlock(id="c1", name=tool, input="{}")
    if confirmed:
        call.state = ToolCallState.ALLOWED
    middleware = ToolPolicyMiddleware(AsyncMock(return_value=policies))
    decision = await middleware.on_check_permission(
        agent=agent or _agent(),
        input_kwargs={"tool_call": call, "tool": _Tool(tool), "tool_input": {}},
        next_handler=next_handler,
    )
    return decision, len(calls)


class ToolPolicyMiddlewareTest(IsolatedAsyncioTestCase):

    async def test_without_a_policy_the_platform_decides(self) -> None:
        decision, calls = await _check({}, SAFETY_ASK)
        self.assertIs(decision, SAFETY_ASK)
        self.assertEqual(calls, 1)

    async def test_deny_never_runs_the_tool(self) -> None:
        decision, _ = await _check({BOOK: "deny"}, ALLOW)
        self.assertIs(decision.behavior, PermissionBehavior.DENY)

    async def test_auto_skips_the_sensitive_action_prompt(self) -> None:
        decision, _ = await _check({BOOK: "auto"}, SAFETY_ASK)
        self.assertIs(decision.behavior, PermissionBehavior.ALLOW)

    async def test_auto_also_runs_in_a_scheduled_run(self) -> None:
        decision, _ = await _check({BOOK: "auto"}, SAFETY_ASK, agent=_agent(PermissionMode.DONT_ASK))
        self.assertIs(decision.behavior, PermissionBehavior.ALLOW)

    async def test_an_explicit_deny_rule_beats_auto(self) -> None:
        decision, _ = await _check({BOOK: "auto"}, SAFETY_ASK, agent=_agent(deny=True))
        self.assertIs(decision.behavior, PermissionBehavior.DENY)

    async def test_ask_asks_even_for_a_low_risk_tool(self) -> None:
        decision, _ = await _check({BOOK: "ask"}, ALLOW)
        self.assertIs(decision.behavior, PermissionBehavior.ASK)

    async def test_ask_does_not_ask_twice_for_a_confirmed_call(self) -> None:
        decision, _ = await _check({BOOK: "ask"}, ALLOW, confirmed=True)
        self.assertIs(decision.behavior, PermissionBehavior.ALLOW)

    async def test_ask_with_nobody_to_ask_refuses(self) -> None:
        decision, _ = await _check({BOOK: "ask"}, ALLOW, agent=_agent(PermissionMode.DONT_ASK))
        self.assertIs(decision.behavior, PermissionBehavior.DENY)

    async def test_only_mcp_tools_have_policies(self) -> None:
        decision, _ = await _check({"Bash": "auto"}, SAFETY_ASK, tool="Bash")
        self.assertIs(decision, SAFETY_ASK)


def _record(policies: dict | None = None) -> AgentRecord:
    return AgentRecord(
        id="agent-1",
        user_id="owner",
        data=AgentData.model_validate(
            {
                "name": "Lễ tân",
                "system_prompt": "x",
                "react_config": {},
                "context_config": {},
                "tool_policies": policies or {},
            },
        ),
    )


class ToolPolicyRouteTest(IsolatedAsyncioTestCase):

    def setUp(self) -> None:
        self.saved: list[AgentRecord] = []
        self.record = _record()

        async def upsert_agent(_owner: str, record: AgentRecord) -> None:
            self.saved.append(record)

        async def get_agent(_owner: str, _agent_id: str) -> AgentRecord:
            return self.saved[-1] if self.saved else self.record

        self.storage = SimpleNamespace(upsert_agent=upsert_agent, get_agent=get_agent)
        self.access = SimpleNamespace(resolve_for_edit=AsyncMock(side_effect=lambda *_: ("owner", self.record)))

    async def test_always_allow_is_stored_and_read_by_the_next_check(self) -> None:
        result = await set_tool_policy(
            "agent-1", ToolPolicyRequest(tool_name=BOOK, policy="auto"), "owner", self.storage, self.access,
        )
        self.assertEqual(result, {"tool_policies": {BOOK: "auto"}})
        self.assertEqual(await _current_tool_policies(self.storage, "owner", "agent-1"), {BOOK: "auto"})

        cleared = await set_tool_policy(
            "agent-1", ToolPolicyRequest(tool_name=BOOK, policy=None), "owner", self.storage, self.access,
        )
        self.assertEqual(cleared, {"tool_policies": {}})

    async def test_only_mcp_tools_and_only_editors(self) -> None:
        with self.assertRaises(HTTPException) as error:
            await set_tool_policy(
                "agent-1", ToolPolicyRequest(tool_name="Bash", policy="auto"), "owner", self.storage, self.access,
            )
        self.assertEqual(error.exception.status_code, 422)

        self.access.resolve_for_edit.side_effect = HTTPException(status_code=403, detail="read only")
        with self.assertRaises(HTTPException) as error:
            await set_tool_policy(
                "agent-1", ToolPolicyRequest(tool_name=BOOK, policy="auto"), "viewer", self.storage, self.access,
            )
        self.assertEqual(error.exception.status_code, 403)
        self.assertEqual(self.saved, [])

    def test_policies_survive_storage(self) -> None:
        record = _record({BOOK: "ask"})
        again = AgentRecord.model_validate(record.model_dump(mode="json"))
        self.assertEqual(again.data.tool_policies, {BOOK: "ask"})


class _BookRoom(ToolBase):
    """A sensitive MCP-like tool: the platform asks before it runs."""

    name: str = BOOK
    description: str = "Book a hotel room"
    input_schema: dict = {"type": "object", "properties": {"room": {"type": "string"}}}
    is_concurrency_safe: bool = False
    is_read_only: bool = False
    is_external_tool: bool = False
    is_mcp: bool = True

    def __init__(self) -> None:
        super().__init__()
        self.calls = 0

    async def check_permissions(self, tool_input: dict, context: PermissionContext) -> PermissionDecision:
        return PermissionDecision(
            behavior=PermissionBehavior.ASK,
            message="sensitive",
            decision_reason="Sensitive MCP operation",
            bypass_immune=True,
        )

    async def __call__(self, room: str = "", **kwargs: object) -> ToolChunk:
        self.calls += 1
        return ToolChunk(content=[TextBlock(text=f"booked {room}")])


class ToolPolicyInAgentRunTest(IsolatedAsyncioTestCase):
    """The middleware in a real agent loop, with a scripted model."""

    async def _run(self, policies: dict) -> tuple[list[str], int]:
        tool = _BookRoom()
        call = ToolCallBlock(id="c1", name=BOOK, input='{"room": "101"}')
        done = [ChatResponse(content=[TextBlock(text="Xong")], is_last=True)]
        model = MockModel()
        model.set_responses([[ChatResponse(content=[call], is_last=True)], done])
        agent = Agent(
            name="Friday",
            system_prompt="x",
            model=model,
            toolkit=Toolkit(tools=[tool]),
            injection_config=InjectionConfig(inject_runtime_state=False),
            middlewares=[ToolPolicyMiddleware(AsyncMock(return_value=policies))],
        )
        types = [event.type async for event in agent.reply_stream(UserMsg(name="user", content="Đặt phòng 101"))]
        return [str(t) for t in types], tool.calls

    async def test_without_a_policy_the_booking_waits_for_approval(self) -> None:
        types, calls = await self._run({})
        self.assertIn("REQUIRE_USER_CONFIRM", " ".join(types))
        self.assertEqual(calls, 0)

    async def test_always_allowed_the_booking_runs_without_a_card(self) -> None:
        types, calls = await self._run({BOOK: "auto"})
        self.assertNotIn("REQUIRE_USER_CONFIRM", " ".join(types))
        self.assertEqual(calls, 1)

    async def test_denied_the_booking_never_runs(self) -> None:
        types, calls = await self._run({BOOK: "deny"})
        self.assertNotIn("REQUIRE_USER_CONFIRM", " ".join(types))
        self.assertEqual(calls, 0)
