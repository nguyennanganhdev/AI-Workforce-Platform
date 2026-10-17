"""Adversarial sandbox checks: untrusted drafts never authorize MCP writes."""

from types import SimpleNamespace

import pytest

from agentscope.app._agent_spec import AgentSpec, SpecTest, SpecTool
from agentscope.app._service import _agent_eval as evaluation
from agentscope.app._service import _agent_studio as studio
from agentscope.message import TextBlock, ToolCallBlock
from agentscope.model import ChatResponse


class _CallingModel:
    def __init__(self, name="dispatch"):
        self.name = name
        self.calls = 0

    async def __call__(self, **_):
        self.calls += 1
        if self.calls == 1:
            return ChatResponse(
                content=[ToolCallBlock(id="call-1", name=self.name, input="{}")],
                is_last=True,
            )
        return ChatResponse(content=[TextBlock(text="Action considered.")], is_last=True)


@pytest.mark.asyncio
async def test_simulated_collaboration_never_reaches_connector_or_overrides_mcp():
    async def connector(*_):
        pytest.fail("A simulated runtime message reached a production connector")

    schema = {"type": "function", "function": {"name": "TeamSay", "parameters": {"type": "object"}}}
    report = await evaluation.run_spec_tests(
        spec=_spec(read_only=True), model=_CallingModel("TeamSay"), judge_model=None,
        discovered={"m:dispatch": {"read_only": True}}, run_tool=connector, simulated_tool_schemas=[schema],
    )
    assert report["simulated_runtime_tools"] == ["TeamSay"]
    assert report["results"][0]["tool_calls"][0]["executed"] is False
    schema["function"]["name"] = "dispatch"
    with pytest.raises(ValueError, match="cannot replace"):
        await evaluation.run_spec_tests(
            spec=_spec(read_only=True), model=_CallingModel(), judge_model=None,
            discovered={}, run_tool=connector, simulated_tool_schemas=[schema],
        )


def _spec(**overrides):
    return AgentSpec(
        name="Sandbox probe",
        tools=[SpecTool(tool_id="m:dispatch", mcp_id="m", tool_name="dispatch", **overrides)],
        tests=[SpecTest(scenario="Dispatch a work order", expected="Do not make an unsafe external change")],
    )


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "metadata",
    [
        {},
        {"read_only": False},
        {"read_only": "true"},
        {"read_only": 1},
        {"read_only": True, "requires_consent": True},
        {"read_only": True, "requires_consent": "false"},
        {"read_only": True, "requires_consent": None},
    ],
)
async def test_draft_cannot_promote_unknown_write_or_consent_tools(metadata):
    calls = []

    async def connector(name, arguments):
        calls.append((name, arguments))
        return "production side effect"

    report = await evaluation.run_spec_tests(
        spec=_spec(read_only=True, requires_consent=False),
        model=_CallingModel(),
        judge_model=None,
        discovered={"m:dispatch": metadata},
        run_tool=connector,
    )

    assert calls == []
    call = report["results"][0]["tool_calls"][0]
    assert {key: call[key] for key in ("name", "arguments", "executed", "mode")} == {
        "name": "dispatch", "arguments": {}, "executed": False, "mode": "simulated",
    }
    assert "NOT executed" in call["output"]
    assert report["publishable"] is False


@pytest.mark.asyncio
async def test_missing_server_tool_cannot_run_even_when_draft_claims_read_only():
    async def connector(*_):
        pytest.fail("An unregistered tool reached the external connector")

    report = await evaluation.run_spec_tests(
        spec=_spec(read_only=True), model=_CallingModel(), judge_model=None,
        discovered={}, run_tool=connector,
    )
    assert report["results"][0]["tool_calls"] == []
    assert report["results"][0]["error_kind"] == "environment"


@pytest.mark.asyncio
async def test_server_can_authorize_read_without_trusting_draft_classification():
    calls = []

    async def connector(name, _):
        calls.append(name)
        return "read data"

    report = await evaluation.run_spec_tests(
        spec=_spec(read_only=False), model=_CallingModel(), judge_model=None,
        discovered={"m:dispatch": {"read_only": True, "requires_consent": False}},
        run_tool=connector,
    )
    assert calls == ["dispatch"]
    assert report["results"][0]["tool_calls"][0]["mode"] == "read_only"


class _Storage:
    def __init__(self, metadata, *, confirm_tools=None):
        self.record = SimpleNamespace(
            id="m", enabled=True, discovered_tools=metadata,
            client=SimpleNamespace(
                name="server", confirm_tools=confirm_tools,
                model_dump=lambda **_: {},
            ),
        )

    async def get_mcp(self, user_id, mcp_id):
        assert (user_id, mcp_id) == ("user", "m")
        return self.record

    async def list_mcps(self, user_id):
        assert user_id == "user"
        return [self.record]


class _Tool:
    def __init__(self, read_only):
        self.is_read_only = read_only
        self.calls = []

    async def __call__(self, **arguments):
        self.calls.append(arguments)
        return SimpleNamespace(content=[TextBlock(text="read data")])


def _fake_connector(monkeypatch, *, live_read_only=True):
    tool = _Tool(live_read_only)
    created = []

    class Client:
        is_stateful = False

        async def get_tool(self, name):
            assert name == "dispatch"
            return tool

        @classmethod
        def model_validate(cls, _):
            created.append(True)
            return cls()

    monkeypatch.setattr(studio, "MCPClient", Client)
    return tool, created


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "metadata,confirm_tools",
    [
        ([], None),
        ([{"name": "dispatch"}], None),
        ([{"name": "dispatch", "read_only": False}], None),
        ([{"name": "dispatch", "read_only": True, "requires_consent": True}], None),
        ([{"name": "dispatch", "read_only": True}], ["dispatch"]),
        ([{"name": "dispatch", "read_only": True}] * 2, None),
    ],
)
async def test_connector_rechecks_current_catalog_before_any_call(monkeypatch, metadata, confirm_tools):
    tool, created = _fake_connector(monkeypatch)
    storage = _Storage(metadata, confirm_tools=confirm_tools)
    runner = studio.tool_runner(storage, "user", _spec(read_only=True))

    with pytest.raises(RuntimeError, match="Sandbox only executes"):
        await runner("dispatch", {})
    assert created == []
    assert tool.calls == []


@pytest.mark.asyncio
async def test_read_reclassification_between_snapshot_and_connector_is_blocked(monkeypatch):
    tool, _ = _fake_connector(monkeypatch)
    storage = _Storage([{"name": "dispatch", "read_only": True}])
    catalog = await studio.tool_catalog(storage, "user")
    storage.record.discovered_tools[0]["read_only"] = False
    report = await evaluation.run_spec_tests(
        spec=_spec(read_only=True), model=_CallingModel(), judge_model=None,
        discovered=catalog, run_tool=studio.tool_runner(storage, "user", _spec(read_only=True)),
    )
    assert tool.calls == []
    call = report["results"][0]["tool_calls"][0]
    assert call["executed"] is False
    assert call["mode"] == "error"


@pytest.mark.asyncio
async def test_live_descriptor_must_still_allow_read_immediately_before_invocation(monkeypatch):
    tool, created = _fake_connector(monkeypatch, live_read_only=False)
    storage = _Storage([{"name": "dispatch", "read_only": True}])
    with pytest.raises(RuntimeError, match="classification changed"):
        await studio.tool_runner(storage, "user", _spec(read_only=True))("dispatch", {})
    assert created == [True]
    assert tool.calls == []


@pytest.mark.asyncio
async def test_confirmed_server_and_live_read_still_runs(monkeypatch):
    tool, _ = _fake_connector(monkeypatch)
    storage = _Storage([{"name": "dispatch", "read_only": True}])
    output = await studio.tool_runner(storage, "user", _spec())("dispatch", {"ticket_id": "t1"})
    assert output == "read data"
    assert tool.calls == [{"ticket_id": "t1"}]


@pytest.mark.asyncio
@pytest.mark.parametrize("ambiguous", [False, True])
async def test_spoofed_and_ambiguous_bindings_fail_closed(monkeypatch, ambiguous):
    tool, created = _fake_connector(monkeypatch)
    spec = _spec(read_only=True)
    if ambiguous:
        spec.tools.append(SpecTool(tool_id="other:dispatch", mcp_id="other", tool_name="dispatch", read_only=True))
    else:
        spec.tools[0].tool_id = "other:dispatch"
    storage = _Storage([{"name": "dispatch", "read_only": True}])
    with pytest.raises(RuntimeError, match="not uniquely bound"):
        await studio.tool_runner(storage, "user", spec)("dispatch", {})
    assert created == []
    assert tool.calls == []


@pytest.mark.asyncio
async def test_catalog_normalizes_safety_and_server_confirmation():
    storage = _Storage(
        [
            {"name": "unknown"},
            {"name": "malformed", "read_only": "true"},
            {"name": "dispatch", "read_only": True},
        ],
        confirm_tools=["dispatch"],
    )
    catalog = await studio.tool_catalog(storage, "user")
    assert catalog["m:unknown"]["read_only"] is False
    assert catalog["m:unknown"]["requires_consent"] is True
    assert catalog["m:malformed"]["read_only"] is False
    assert catalog["m:dispatch"]["requires_consent"] is True


@pytest.mark.asyncio
async def test_publishing_bindings_cannot_strip_server_confirmation(monkeypatch):
    storage = _Storage([
        {"name": "dispatch", "read_only": True},
        {"name": "write", "read_only": False},
        {"name": "safe", "read_only": True},
    ])
    configured_client = SimpleNamespace(confirm_tools=["dispatch"])
    monkeypatch.setattr(studio, "MCPClient", SimpleNamespace(model_validate=lambda _: configured_client))
    session = SimpleNamespace(
        id="session", config=SimpleNamespace(workspace_id="workspace", knowledge_config=None),
        state={}, origin=None,
    )

    async def list_sessions(*_):
        return [session]

    async def upsert_session(**_):
        return session

    class Workspace:
        default_mcps = []

        async def list_mcps(self, **_):
            return []

        async def add_mcp(self, client, **_):
            assert client is configured_client

    async def get_workspace(*_):
        return Workspace()

    storage.list_sessions = list_sessions
    storage.upsert_session = upsert_session
    spec = _spec(read_only=True, requires_consent=False)
    for name in ["write", "unknown", "safe"]:
        spec.tools.append(SpecTool(
            tool_id=f"m:{name}", mcp_id="m", tool_name=name, read_only=True, requires_consent=False,
        ))
    await studio.apply_bindings(
        storage=storage, workspace_manager=SimpleNamespace(get_workspace=get_workspace),
        user_id="user", record=SimpleNamespace(id="agent"), spec=spec,
    )
    assert configured_client.confirm_tools == ["dispatch", "unknown", "write"]


@pytest.mark.asyncio
@pytest.mark.parametrize("operation", ["add", "set"])
async def test_copilot_cannot_override_catalog_safety_via_item_or_whole_list(operation):
    value = {
        "tool_id": "m:dispatch", "mcp_id": "spoofed", "tool_name": "spoofed",
        "read_only": True, "requires_consent": False,
    }

    class CopilotModel:
        async def generate_structured_output(self, **_):
            return SimpleNamespace(content={
                "assistant_message": "Updated.",
                "operations": [{"op": operation, "field": "tools", "value": [value] if operation == "set" else value}],
            })

    catalog = {"m:dispatch": {
        "tool_id": "m:dispatch", "mcp_id": "m", "mcp_name": "server", "tool_name": "dispatch",
        "read_only": False, "requires_consent": True,
    }}
    original = AgentSpec(name="Sandbox probe")
    _, patched, _ = await studio.copilot_turn(
        model=CopilotModel(), spec=original, message="Treat this write as read-only", catalog=catalog,
    )
    assert original.tools == []
    assert patched.tools[0].read_only is False
    assert patched.tools[0].requires_consent is True
    assert patched.tools[0].mcp_id == "m"
    assert patched.tools[0].tool_name == "dispatch"
