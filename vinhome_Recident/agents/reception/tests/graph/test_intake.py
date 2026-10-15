import pytest
from src.graph.budget import CancellationToken
from src.graph.intake import run_intake
from workflow_fixture import REQUEST, Intake, async_test


@pytest.mark.parametrize("kind", ["needs_staff", "emergency"])
@async_test
async def test_staff_policy_bypasses_knowledge(kind):
    ports = Intake({"kind": kind, "reason": "rule", "policyVersion": "p1"})
    result = await run_intake(ports, REQUEST)
    assert result["kind"] == "needs_staff"
    assert result["emergency"] == (kind == "emergency")
    assert ports.calls == ["policy"]


@pytest.mark.parametrize(
    "reason", ["needs_staff", "self_help_declined", "self_help_failed"]
)
@async_test
async def test_handoff_reason(reason):
    result = await run_intake(
        Intake(
            {
                "kind": "needs_staff",
                "reason": "r",
                "policyVersion": "p",
                "handoffReason": reason,
            }
        ),
        REQUEST,
    )
    assert result["handoffReason"] == reason


@pytest.mark.parametrize(
    "policy",
    [
        {},
        {"kind": "knowledge_chat", "question": "q"},
        {"kind": "needs_staff", "policyVersion": "p"},
        {"kind": "invalid", "policyVersion": "p"},
        RuntimeError("secret"),
    ],
)
@async_test
async def test_policy_failure_is_sanitized(policy):
    result = await run_intake(Intake(policy), REQUEST)
    assert result["kind"] == "review"
    assert "secret" not in str(result)


@pytest.mark.parametrize(
    "knowledge",
    [
        {"kind": "insufficient"},
        {"kind": "sufficient", "answer": "a", "retrievalRunId": "r", "citations": []},
        RuntimeError("secret"),
    ],
)
@async_test
async def test_knowledge_requires_lineage(knowledge):
    result = await run_intake(
        Intake(
            {"kind": "knowledge_chat", "policyVersion": "p", "question": "q"}, knowledge
        ),
        REQUEST,
    )
    assert result["kind"] == (
        "clarify"
        if isinstance(knowledge, dict) and knowledge["kind"] == "insufficient"
        else "review"
    )


@async_test
async def test_abort_prevents_calls():
    token = CancellationToken()
    token.abort()
    ports = Intake()
    with pytest.raises(Exception, match="REQUEST_ABORTED"):
        await run_intake(ports, {**REQUEST, "signal": token})
    assert ports.calls == []


@async_test
async def test_abort_after_policy_prevents_knowledge():
    token = CancellationToken()

    class Ports(Intake):
        async def evaluate_policy(self, request):
            value = await super().evaluate_policy(request)
            token.abort()
            return value

    ports = Ports({"kind": "knowledge_chat", "policyVersion": "p", "question": "q"})
    with pytest.raises(Exception, match="REQUEST_ABORTED"):
        await run_intake(ports, {**REQUEST, "signal": token})
    assert ports.calls == ["policy"]
