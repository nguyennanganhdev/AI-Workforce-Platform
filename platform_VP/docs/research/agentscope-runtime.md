# AgentScope runtime integration

Inspected 2026-10-09 against the local vendored `agentscope` source, version `2.0.10dev`. This note uses that source as the primary authority. Samples describe the checked API; they were not executed in the system Python because `agentscope` is not installed there. No provider requests were made.

## Recommended boundary

Use the SDK `Agent` inside platform-owned workers. Keep authentication, workspace membership, published revisions, task leases, shared messages, evidence, budget reservations and event replay in the platform database. Construct a fresh SDK object for each leased execution, loading only the state keyed by workspace, session, agent revision and task. The SDK is the reasoning/tool execution engine, not the platform scheduler or authorization system.

The constructor accepts name, system prompt, model, toolkit, middleware and `AgentState`; state and model are not global singletons. [Constructor](../../agentscope/src/agentscope/agent/_agent.py#L120), lines 120–143. `AgentState.session_id`, `summary` and `context` are explicitly persisted state fields. [State](../../agentscope/src/agentscope/state/_state.py#L209), lines 209–225.

Do not expose the example application unchanged: its identity dependency returns the arbitrary `X-User-ID` header without verifying credentials. [Identity dependency](../../agentscope/src/agentscope/app/deps.py#L37), lines 37–63. `SecretStr` masks Python display but the framework storage serializer deliberately unwraps secrets. Encrypt platform credentials before database persistence and avoid putting credentials in SDK snapshots. [Secret serialization](../../agentscope/src/agentscope/app/storage/_utils.py#L15), lines 15 onward.

## Exact construction and messages

`OpenAIChatModel` takes an `OpenAICredential` object, not an `api_key` argument. A custom `base_url` belongs to the credential; provider SDK options belong to `client_kwargs`. [Model](../../agentscope/src/agentscope/model/_openai_chat/_model.py#L121), lines 121–192; [credential](../../agentscope/src/agentscope/credential/_openai.py#L16), lines 16–44.

`UserMsg` is a factory returning `Msg`. Strings are wrapped into `TextBlock`; messages carry sender name, role, metadata and ID. `Msg.get_text_content()` concatenates text blocks, while `structured_output` stores validated structured output when available. [Message model](../../agentscope/src/agentscope/message/_base.py#L70), lines 70–121 and 167–171; [UserMsg factory](../../agentscope/src/agentscope/message/_base.py#L541), lines 541 onward.

This complete async example makes a paid request only when invoked with a configured environment. The platform must wrap it with the budget and authorization controls described below.

```python
import asyncio
import os

from agentscope.agent import Agent, ModelConfig, ReActConfig
from agentscope.credential import OpenAICredential
from agentscope.event import TextBlockDeltaEvent
from agentscope.message import Msg, UserMsg
from agentscope.model import OpenAIChatModel
from agentscope.state import AgentState
from agentscope.tool import Toolkit


async def main():
    model = OpenAIChatModel(
        credential=OpenAICredential(
            api_key=os.environ["PLATFORM_LLM_API_KEY"],
            base_url=os.environ.get("PLATFORM_LLM_BASE_URL"),
        ),
        model=os.environ["PLATFORM_LLM_MODEL"],
        parameters=OpenAIChatModel.Parameters(max_tokens=1024),
        max_retries=0,
        client_kwargs={"max_retries": 0, "timeout": 45.0},
        context_size=32768,  # Set from verified model catalog in deployment.
    )
    agent = Agent(
        name="researcher",
        system_prompt="Bạn là chuyên viên nghiên cứu. Nêu rõ điều chưa biết.",
        model=model,
        toolkit=Toolkit(),  # No shell, filesystem or team tools are implicit.
        state=AgentState(session_id="session-example"),
        model_config=ModelConfig(max_retries=0),
        react_config=ReActConfig(max_iters=4, structured_output_grace_iters=1),
    )
    final = None
    try:
        async for item in agent.reply_stream(
            UserMsg("user", "Bạn cần thêm thông tin gì trước khi nghiên cứu?"),
            yield_final_msg=True,
        ):
            if isinstance(item, TextBlockDeltaEvent):
                print(item.delta, end="", flush=True)
            elif isinstance(item, Msg):
                final = item
        snapshot = agent.state.model_dump(mode="json")
        restored = AgentState.model_validate(snapshot)
        assert restored.session_id == "session-example"
        assert final is not None
    finally:
        await model.client.close()


if __name__ == "__main__":
    asyncio.run(main())
```

The toolkit constructor starts from the explicitly supplied tools, skills and MCP clients; `Agent` also creates an internal compression tool, whose exposure is controlled by context configuration. [Toolkit](../../agentscope/src/agentscope/tool/_toolkit.py#L89), lines 89–151; [agent compression tool](../../agentscope/src/agentscope/agent/_agent.py#L205), lines 205–216; [configuration](../../agentscope/src/agentscope/agent/_config.py#L177), lines 177–186.

## Streaming, structured output and persistence

`reply_stream(inputs, structured_schema=None, yield_final_msg=False)` emits SDK events. Set `yield_final_msg=True` to also receive the final `Msg`; otherwise it is filtered out. `reply(...)` consumes the stream and returns that final message. `observe(...)` adds observations to state but does not itself run the model. [Public methods](../../agentscope/src/agentscope/agent/_agent.py#L288), lines 288–393.

Event payloads are Pydantic models and can be serialized with `model_dump(mode="json")`. Useful public events include `TEXT_BLOCK_DELTA` with `.delta`, `MODEL_CALL_END` with token counters, and `REPLY_END` with terminal reason and optional error. Thinking events are separate and should not be forwarded to the ordinary user-facing context inspector. [Event schema](../../agentscope/src/agentscope/event/_event.py#L67), lines 67–85, 111–155 and 170–182.

Always inspect `finished_reason`: a final message can represent an error, interruption or iteration limit; mere presence of text does not mean a task succeeded. `structured_output` may be `None` on those paths. [Msg terminal fields](../../agentscope/src/agentscope/message/_base.py#L108), lines 108–125.

Structured output uses a builtin `GenerateStructuredOutput` tool. It validates the supplied Pydantic schema, records the validated dictionary in `state.reply_context.structured_output`, and reports validation errors to the model. Reloaded JSON state preserves the JSON schema but cannot preserve arbitrary Python validators; revalidate the final result with the platform's current pinned result model before acceptance. [Structured output implementation](../../agentscope/src/agentscope/agent/_structured_output_tool.py#L100), lines 100–156.

```python
from pydantic import BaseModel, Field


class Claim(BaseModel):
    text: str
    evidence_ids: list[str] = Field(default_factory=list)


class Result(BaseModel):
    answer: str
    claims: list[Claim] = Field(default_factory=list)
    unknowns: list[str] = Field(default_factory=list)


async def structured_reply(agent, message):
    final = await agent.reply(message, structured_schema=Result)
    if final.finished_reason != "completed" or final.structured_output is None:
        raise RuntimeError("Reply did not complete with structured output")
    return Result.model_validate(final.structured_output)
```

State is a Pydantic model: use `agent.state.model_dump(mode="json")` and `AgentState.model_validate(snapshot)`, then pass `state=` into a new `Agent`. There is no need to invent a `state_dict()` API. Persist snapshot, consumed inbox IDs, outcome and platform events atomically under the active lease generation. Tools that cause effects also require their own deduplication keys because saving a snapshot after the effect cannot make the external effect transactional. The latter transaction design is a platform recommendation derived from the stateful SDK boundary, not a capability promised by the SDK. [State](../../agentscope/src/agentscope/state/_state.py#L209), lines 209 onward.

## Tool registration and authorization

`FunctionTool` wraps sync/async functions and automatically derives a JSON schema from type annotations/docstrings, or accepts an explicit schema. Its default permission is **ASK**, not ALLOW. Explicitly grant only the platform tools whose server-side authorization has already been enforced. [FunctionTool](../../agentscope/src/agentscope/tool/_adapters.py#L57), lines 57–133.

```python
from agentscope.message import TextBlock, ToolResultState
from agentscope.permission import PermissionBehavior, PermissionDecision
from agentscope.tool import FunctionTool, ToolChunk, Toolkit


async def read_board() -> ToolChunk:
    """Read the authorized session's task board."""
    # Replace this example value with the server-bound scoped repository call.
    # Do not accept workspace/session identity from model arguments.
    return ToolChunk(
        content=[TextBlock(text='{"revision":1,"tasks":[]}')],
        state=ToolResultState.SUCCESS,
    )


toolkit = Toolkit(tools=[FunctionTool(
    read_board,
    name="read_board",
    is_read_only=True,
    permission=PermissionDecision(
        behavior=PermissionBehavior.ALLOW,
        message="Read-only tool bound to the authorized session.",
    ),
)])
```

`ToolChunk.state` defaults to RUNNING, so explicitly use SUCCESS/ERROR for final outcomes. [Tool result schema](../../agentscope/src/agentscope/tool/_response.py#L28), lines 28–44. Enforce agent tool grants, document ACLs, task ownership and effect approval inside repository/tool code. A prompt cannot replace those checks. This is the platform security boundary; the function adapter only controls whether the SDK invokes the registered tool.

MCP is a native capability: `MCPClient(name=..., is_stateful=False, mcp_config=HttpMCPConfig(url=...), enable_tools=[...], execution_timeout=...)`. HTTP may be stateless; STDIO must be stateful and requires connect/close lifecycle. Toolkit rejects unconnected stateful clients. Use explicit tool allowlists and administrator-owned endpoints; remote MCP URLs/headers must not bypass platform network policy. [MCP client](../../agentscope/src/agentscope/mcp/_mcp_client.py#L33), lines 33–84 and 101–140; [config](../../agentscope/src/agentscope/mcp/_config.py#L47), lines 47 onward; [toolkit lifecycle check](../../agentscope/src/agentscope/tool/_toolkit.py#L155), lines 155 onward.

## Budget and context edge cases

There are multiple retry layers: `Agent.ModelConfig.max_retries`, provider model `.max_retries`, and the provider SDK's own retries. `OpenAIChatModel.client_kwargs` reaches `openai.AsyncClient`; set its `max_retries=0` as well when the platform owns retries. [Agent retry loop](../../agentscope/src/agentscope/agent/_agent.py#L3303), lines 3303–3391; [model retry loop](../../agentscope/src/agentscope/model/_base.py#L182), lines 182–249; [OpenAI client](../../agentscope/src/agentscope/model/_openai_chat/_model.py#L182), lines 182–192.

`MiddlewareBase.on_model_call` receives `current_model`, `messages`, `tools`, `tool_choice`, and an awaitable `next_handler`. It can reserve cost before calling the provider and wrap the returned async generator to reconcile usage on the final `ChatResponse`. The outer SDK retry/fallback loop re-enters that middleware for each outer attempt. [Middleware contract](../../agentscope/src/agentscope/middleware/_base.py#L220), lines 220–246; [call chain](../../agentscope/src/agentscope/agent/_agent.py#L3329), lines 3329–3371. Reservations need durable error/timeout states: no usage response does not establish zero bill.

**Important:** automatic context compression calls `self.model.generate_structured_output()` directly, outside `on_model_call`. Therefore a budget middleware around normal reasoning is insufficient if automatic compression can call the provider. `compression_tool_enabled=False` only hides the explicit compression tool; it does not disable automatic compression. [Compression calls](../../agentscope/src/agentscope/agent/_agent.py#L639), lines 639–685; [context config](../../agentscope/src/agentscope/agent/_config.py#L51), lines 51–70 and 177–186.

Recommended platform implementation: bound prompt construction explicitly and install `on_compress_context` middleware that performs deterministic scoped selection/truncation without invoking its `next_handler`; preserve discarded source events/evidence in the platform store. Alternatively place reservation/accounting at every provider I/O call, including structured-generation strategies. Do not set a fictitiously huge model context size to hide the issue. [Compression middleware contract](../../agentscope/src/agentscope/middleware/_base.py#L241), lines 241 onward.

`ReActConfig.max_iters` defaults to 50, and structured output has **five additional grace iterations** by default. Configure both and enforce a hard budget independently; max iterations alone is not a money limit. [ReAct configuration](../../agentscope/src/agentscope/agent/_config.py#L362), lines 362–385. Native compression summary and `state.tasks_context` are per-agent state, so the shared board and durable inbox must be platform tools rather than independent per-agent planning copies. [State fields](../../agentscope/src/agentscope/state/_state.py#L283), lines 283?291.

## Jev shadow classifier

The local adapter is `JevClassifierModel`, a classifier model, not a chat model. It requires `typesafe-sdk` (optional `agentscope[classifier-jev]` dependency), constructs `AsyncTypeSafeClient`, and accepts typed questions over a string or JSON state. Default model alias is `jev-latest`; platform configuration should instead pin an explicitly evaluated version. [Adapter](../../agentscope/src/agentscope/classifier/_jev/_model.py#L70), lines 70–135 and 137–181. `TypeSafeCredential` explicitly rejects chat-model construction. [Credential](../../agentscope/src/agentscope/credential/_typesafe.py#L16), lines 16–39.

```python
from agentscope.classifier import JevClassifierModel, ChoiceQuestion
from agentscope.credential import TypeSafeCredential


async def shadow_decision(api_key: str, redacted_state: dict):
    model = JevClassifierModel(
        credential=TypeSafeCredential(api_key=api_key),
        model="jev-1.13.0",  # Explicit evaluated pin; never auto-follow latest.
        timeout=10,
        max_retries=0,
    )
    response = await model(
        state=redacted_state,
        questions={"route": ChoiceQuestion(
            instructions="Classify the next action using the supplied state.",
            criteria={
                "tool": "Need a tool to obtain missing evidence",
                "clarify": "Need user clarification",
                "answer": "Enough evidence to draft an answer",
            },
        )},
    )
    answer = response.content["route"]
    return {
        "model": response.model,
        "choice": answer.choice,
        "confidence": answer.confidence,
        "probabilities": answer.probabilities,
        "usage": response.usage,
    }
```

BinaryQuestion maps to TypeSafe Noul; Choice/Score retain confidence and probabilities. The local mapping has no calibrated acceptance threshold. Log the complete distribution and decision version, compare against deterministic baseline and Vietnamese held-out labels, and leave shadow output unable to grant tools, accept claims or mutate the selected production route. [Question mapping](../../agentscope/src/agentscope/classifier/_jev/_model.py#L30), lines 30–66; [answer schemas](../../agentscope/src/agentscope/classifier/_response.py#L13), lines 13–79. These are implementation recommendations; a confidence number is not evidence of factual correctness.

The example pin above matches the previously researched provider version; this local-source investigation does not independently verify external availability, pricing or provider retention guarantees. Recheck official provider documentation before enabling paid Jev traffic.
