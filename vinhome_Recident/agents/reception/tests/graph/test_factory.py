from copy import deepcopy
from types import SimpleNamespace

import pytest
from langgraph.checkpoint.memory import InMemorySaver
from src.graph import (
    GraphDependencies,
    ReceptionFactoryOptions,
    ToolBinding,
    create_reception_graph_factory,
)
from src.graph.decision import GraphFault, compact_json, parse_decision
from workflow_fixture import REQUEST, ScriptedModel, async_test, resident_resume


def generic(responses, result=None, reconcile=True, **options):
    calls, reconciled = [], []

    class Tools:
        async def invoke(self, call):
            calls.append(call)
            return result or {
                "kind": "success",
                "value": {"id": "ticket", "generation": 0, "aggregateVersion": 1},
            }

    def parse(value):
        if not isinstance(value, dict) or not value.get("id"):
            raise GraphFault("INVALID_TOOL_OUTPUT")
        return value

    async def reconciliation(call):
        reconciled.append(call)
        return {
            "kind": "success",
            "value": {"id": "ticket", "generation": 0, "aggregateVersion": 2},
        }

    binding = ToolBinding(
        "test",
        {},
        lambda v: v,
        parse,
        lambda v: [{"name": "id", "value": v["id"]}],
        lambda v: v,
        reconciliation if reconcile else None,
    )
    deps = GraphDependencies(ScriptedModel(responses), Tools(), InMemorySaver())
    factory = create_reception_graph_factory(
        ReceptionFactoryOptions(bindings={"draft": binding}, **options)
    )
    return SimpleNamespace(
        graph=factory.create(deps),
        factory=factory,
        dependencies=deps,
        calls=calls,
        reconciled=reconciled,
    )


TOOL = compact_json(
    {
        "action": "tool",
        "operation": "draft",
        "input": {},
        "inferences": [{"name": "suspected", "value": "reported"}],
    }
)
COMPLETE = compact_json({"action": "complete", "text": "Đã xác minh."})


@async_test
async def test_generic_real_graph_and_fact_provenance():
    h = generic([TOOL, COMPLETE])
    result = await h.graph.run(REQUEST)
    assert result["status"] == "completed", result
    assert (
        result["state"]["confirmed"][0]["source"]["idempotencyKey"]
        == h.calls[0]["idempotencyKey"]
    )
    assert result["state"]["inferences"][0]["name"] == "suspected"
    assert (await h.factory.create(h.dependencies).read(REQUEST["context"]))["ticket"][
        "id"
    ] == "ticket"


@async_test
async def test_generic_resident_interrupt():
    h = generic([compact_json({"action": "clarify", "text": "Ở đâu?"}), COMPLETE])
    first = await h.graph.run(REQUEST)
    assert first["status"] == "interrupted"
    assert (await h.graph.run(REQUEST))["code"] == "RESUME_REQUIRED"
    result = await h.graph.resume(resident_resume(first))
    assert result["status"] == "completed", result
    assert len(result["state"]["reported"]) == 2


@pytest.mark.parametrize(
    "raw",
    [
        {"kind": "accepted", "operationId": "backend-op"},
        {"kind": "failure", "code": "LOST", "retryable": False, "outcome": "unknown"},
        {"kind": "success", "value": {}},
        {"kind": "malformed"},
    ],
)
@async_test
async def test_generic_unknown_is_reconciled_same_key(raw):
    h = generic([TOOL, COMPLETE], result=raw)
    first = await h.graph.run(REQUEST)
    assert first["status"] == "interrupted", first
    pending = first["state"]["pendingTool"]
    req = {
        "context": REQUEST["context"],
        "operationId": "resume",
        "interruptId": first["interrupts"][0]["id"],
        "source": {
            "kind": "backend",
            "event": {
                "bindingId": REQUEST["context"]["bindingId"],
                "interruptId": first["interrupts"][0]["id"],
                "generation": 0,
                "aggregateVersion": 2,
                "ticketId": "ticket",
            },
        },
    }
    result = await h.graph.resume(req)
    assert result["status"] == "completed", result
    assert len(h.calls) == 1
    assert h.reconciled[0]["idempotencyKey"] == pending["idempotencyKey"]


@async_test
async def test_generic_missing_reconcile_keeps_wait():
    h = generic(
        [TOOL], result={"kind": "accepted", "operationId": "op"}, reconcile=False
    )
    first = await h.graph.run(REQUEST)
    req = {
        "context": REQUEST["context"],
        "operationId": "resume",
        "interruptId": first["interrupts"][0]["id"],
        "source": {
            "kind": "backend",
            "event": {
                "bindingId": REQUEST["context"]["bindingId"],
                "interruptId": first["interrupts"][0]["id"],
                "generation": 0,
                "aggregateVersion": 2,
            },
        },
    }
    assert (await h.graph.resume(req))["code"] == "RECONCILIATION_UNAVAILABLE"
    assert (await h.graph.read(REQUEST["context"]))["pendingTool"]


@pytest.mark.parametrize(
    "bad",
    [
        "not json",
        "[]",
        '{"action":"complete","text":"x","ticket_id":"fake"}',
        '{"action":"tool","operation":"draft"}',
        '{"action":"complete","text":" "}',
    ],
)
def test_model_decision_rejects_authority_and_malformed(bad):
    with pytest.raises(GraphFault):
        parse_decision(bad)


@async_test
async def test_generic_limits_and_unknown_operation():
    h = generic([compact_json({"action": "tool", "operation": "forged", "input": {}})])
    assert (await h.graph.run(REQUEST))["code"] == "TOOL_NOT_ALLOWED"
    assert not h.calls
    h = generic([TOOL], max_steps=1)
    result = await h.graph.run(REQUEST)
    assert result["state"]["phase"] == "handoff"
    assert len(h.calls) == 1


@async_test
async def test_generic_not_applied_requires_review():
    h = generic(
        [TOOL],
        result={
            "kind": "failure",
            "code": "REJECTED",
            "retryable": False,
            "outcome": "not_applied",
        },
    )
    result = await h.graph.run(REQUEST)
    assert result["state"]["phase"] == "handoff"
    assert result["state"]["pendingTool"] is None


@async_test
async def test_generic_rejects_ts_state_and_wrong_owner():
    h = generic([COMPLETE])
    await h.graph.run(REQUEST)
    wrong = deepcopy(REQUEST["context"])
    wrong["principalId"] = "other"
    with pytest.raises(GraphFault, match="CONTEXT_MISMATCH"):
        await h.graph.read(wrong)
    data = await h.graph.read(REQUEST["context"])
    data.pop("runtime_version")
    await h.graph.compiled.aupdate_state(
        h.graph._config(REQUEST["context"]), {"data": data}
    )
    with pytest.raises(GraphFault, match="STATE_VERSION_UNSUPPORTED"):
        await h.graph.read(REQUEST["context"])


@pytest.mark.parametrize("action", ["clarify", "await_resident"])
@async_test
async def test_generic_clarification_limit(action):
    h = generic(
        [compact_json({"action": action, "text": "Ở đâu?"})], max_clarifications=1
    )
    first = await h.graph.run(REQUEST)
    final = await h.graph.resume(resident_resume(first))
    assert final["state"]["phase"] == "handoff"
    assert not h.calls


@async_test
async def test_generic_stream_has_one_result_and_sanitizes_model_errors():
    h = generic([RuntimeError("secret-token")])
    events = [item async for item in h.graph.stream(REQUEST)]
    assert len(events) == 1 and events[0]["type"] == "result"
    assert events[0]["result"]["code"] == "GRAPH_EXECUTION_FAILED"
    assert "secret-token" not in str(events)
    h = generic([compact_json({"action": "clarify", "text": "Ở đâu?"}), COMPLETE])
    first = await h.graph.run(REQUEST)
    events = [item async for item in h.graph.stream(resident_resume(first))]
    assert [e["type"] for e in events] == ["text_delta", "result"]


@async_test
async def test_generic_empty_read_preabort_and_separate_namespaces():
    from src.graph.budget import CancellationToken

    h = generic([COMPLETE])
    assert await h.graph.read(REQUEST["context"]) is None
    token = CancellationToken()
    token.abort()
    assert (await h.graph.run({**REQUEST, "signal": token}))["status"] == "cancelled"
    assert await h.graph.read(REQUEST["context"]) is None
    first = await h.graph.run(REQUEST)
    other = deepcopy(REQUEST)
    other["context"]["checkpoint"]["namespace"] = "another"
    other["message"]["text"] = "Tin nhắn khác"
    await h.graph.run(other)
    assert (await h.graph.read(REQUEST["context"]))["message"] == first["state"][
        "message"
    ]


@pytest.mark.parametrize("key", ["timeout_ms", "max_steps", "max_clarifications"])
@pytest.mark.parametrize("value", [0, -1, True])
def test_factory_requires_positive_integer_limits(key, value):
    with pytest.raises(GraphFault):
        generic([COMPLETE], **{key: value})
