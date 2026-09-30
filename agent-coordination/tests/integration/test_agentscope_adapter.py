"""Integration test với AgentScope thật, stub model và fake provider; không gọi mạng."""

import asyncio
from contextlib import asynccontextmanager

import pytest

pytest.importorskip("agentscope", reason="Kiểm thử tích hợp cần cài AgentScope")

from adapters.agentscope_adapter import AgentScopeAdapter, AgentSession
from agentscope.agent import Agent, ModelConfig, ReActConfig
from agentscope.credential import CredentialBase
from agentscope.formatter import OpenAIChatFormatter
from agentscope.message import TextBlock, ThinkingBlock
from agentscope.model import ChatModelBase, ChatResponse
from agentscope.state import AgentState
from agentscope.tool import ToolGroup, Toolkit
from groupchat.models import RoomError, TurnPolicy
from groupchat.ports import Invocation
from support.fakes import make_context

pytestmark = pytest.mark.integration


class StubModel(ChatModelBase):
    def __init__(self):
        super().__init__(
            credential=CredentialBase(),
            model="test-no-network",
            parameters=self.Parameters(),
            stream=False,
            max_retries=0,
        )
        self.formatter = OpenAIChatFormatter()
        self.calls = []
        self.delay = 0
        self.fail = False

    async def _call_api(
        self, model_name, messages, tools=None, tool_choice=None, **kwargs
    ):
        self.calls.append(messages)
        await asyncio.sleep(self.delay)
        if self.fail:
            raise RuntimeError("model unavailable")
        return ChatResponse(
            content=[
                ThinkingBlock(thinking="PRIVATE_REASONING"),
                TextBlock(
                    text='{"content":"@B TeamSay: chờ Điều phối", "follow_up_requests":'
                    '[{"recipient_agent_version_id":"B-v1","content":"Hỏi B"}]}'
                ),
            ],
            is_last=True,
        )


class ExistingAgents:
    def __init__(self):
        self.sessions = {}
        self.saved = {}
        self.confirm_cancel = False

    def register(self, participant):
        model = StubModel()
        agent = Agent(
            name=participant.framework_agent_id,
            system_prompt="Test only",
            model=model,
            model_config=ModelConfig(max_retries=0),
            react_config=ReActConfig(
                max_iters=1, interruption_raise_cancelled_error=True
            ),
        )
        self.sessions[participant.framework_reference] = AgentSession(
            agent, participant.framework_agent_id, participant.framework_reference
        )
        return model

    @asynccontextmanager
    async def session(self, invocation):
        session = self.sessions[invocation.participant.framework_reference]
        yield session
        self.saved[session.framework_reference] = session.agent.state.model_dump(
            mode="json"
        )

    async def cancel(self, invocation):
        return self.confirm_cancel


async def setup_provider(harness):
    _, opened = await harness.open()
    provider = ExistingAgents()
    room = harness.state.records[harness.ctx.scope()].snapshot
    models = [provider.register(p) for p in room.participants]
    harness.service.invocation = AgentScopeAdapter(provider)
    return opened, provider, models


async def test_actual_sdk_external_single_turn_followup_and_private_state(harness):
    opened, provider, models = await setup_provider(harness)
    first = await harness.service.execute(harness.turn(opened.data))
    assert first.status == "completed", first
    assert len(models[0].calls) == 1 and not models[1].calls
    assert (
        first.data.follow_up_requests
        and "PRIVATE_REASONING" not in first.model_dump_json()
    )
    second = await harness.service.execute(harness.turn(first.data, "B-v1"))
    assert second.status == "completed", second
    assert len(models[1].calls) == 1
    assert "@B" in str(models[1].calls[0])
    for saved in provider.saved.values():
        restored = AgentState.model_validate(saved)
        assert restored.session_id and restored.context


async def test_actual_sdk_two_rooms_same_configuration_isolated(harness):
    opened, provider, models = await setup_provider(harness)
    other_ctx = make_context("SECOND")
    _, other = await harness.open(context=other_ctx)
    other_room = harness.state.records[other_ctx.scope()].snapshot
    other_models = [provider.register(p) for p in other_room.participants]
    a, b = await asyncio.gather(
        harness.service.execute(harness.turn(opened.data)),
        harness.service.execute(harness.turn(other.data, context=other_ctx)),
    )
    assert a.status == b.status == "completed"
    assert len(models[0].calls) == len(other_models[0].calls) == 1
    sessions = list(provider.sessions.values())
    assert len({x.agent.state.session_id for x in sessions}) == 4
    assert sessions[0].agent.state is not sessions[2].agent.state


async def test_actual_sdk_timeout_does_not_claim_remote_cancel(harness):
    opened, _provider, models = await setup_provider(harness)
    models[0].delay = 0.2
    async with harness.state.transaction(harness.ctx) as record:
        record.snapshot.policy = TurnPolicy(timeout_seconds=0.01)
    result = await harness.service.execute(harness.turn(opened.data))
    assert result.error.code == "OUTCOME_UNKNOWN"
    assert harness.state.records[harness.ctx.scope()].snapshot.active_operation
    assert len(models[0].calls) == 1


async def test_actual_sdk_mapping_retry_profile_and_no_tools(harness):
    _opened, provider, models = await setup_provider(harness)
    room = harness.state.records[harness.ctx.scope()].snapshot
    participant = room.participants[0]
    invocation = Invocation(
        "op", 1, harness.ctx, room.room_id, participant, "child-run", (), "hello"
    )
    session = provider.sessions[participant.framework_reference]
    session.framework_agent_id = "wrong"
    with pytest.raises(RoomError, match="MAPPING_MISSING"):
        await harness.service.invocation.prepare(invocation)
    session.framework_agent_id = participant.framework_agent_id
    models[0].max_retries = 1
    with pytest.raises(RoomError, match="Disable model retries"):
        await harness.service.invocation.prepare(invocation)
    models[0].max_retries = 0
    # Reject cả tool trong inactive group trước dispatch.
    from agentscope.tool import FunctionTool

    def TeamSay(text: str) -> str:
        """Disallowed scheduler tool."""
        raise AssertionError("must never execute")

    session.agent.toolkit = Toolkit(
        tool_groups=[
            ToolGroup(
                name="inactive",
                description="Test forbidden tools",
                tools=[FunctionTool(TeamSay)],
            )
        ]
    )
    with pytest.raises(RoomError, match="no registered tools"):
        await harness.service.invocation.prepare(invocation)
    assert not models[0].calls


async def test_actual_sdk_rebuilds_context_after_fact_acl_changes(harness):
    from groupchat.models import ContextItem, MentionAgent, PutContext
    from support.harness import room_args as args

    opened, _provider, models = await setup_provider(harness)
    fact = ContextItem(
        item_id="private",
        content="REVOKED_FACT_MARKER",
        reader_agent_version_ids=["B-v1"],
    )
    added = await harness.service.execute(
        harness.command(PutContext(**args(opened.data), item=fact))
    )
    first = await harness.service.execute(
        harness.command(
            MentionAgent(
                **args(added.data), mentioned_agent_id="B", instruction="Question one"
            )
        )
    )
    assert first.status == "completed"
    assert "REVOKED_FACT_MARKER" in str(models[1].calls[-1])
    fact.reader_agent_version_ids = ["A-v1"]
    changed = await harness.service.execute(
        harness.command(PutContext(**args(first.data), item=fact))
    )
    second = await harness.service.execute(
        harness.command(
            MentionAgent(
                **args(changed.data), mentioned_agent_id="B", instruction="Question two"
            )
        )
    )
    assert second.status == "completed"
    assert "REVOKED_FACT_MARKER" not in str(models[1].calls[-1])
    assert "task_board" in str(models[1].calls[-1])
