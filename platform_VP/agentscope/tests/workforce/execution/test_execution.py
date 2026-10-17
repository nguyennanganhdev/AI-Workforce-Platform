"""Behavioral tests of real Execution services against scoped fake ports."""

import asyncio

import pytest

from agentscope.app.workforce.execution import ExecutionError, calculate
from agentscope.app.workforce.execution._reconciliation import summarize
from execution_fakes import (
    AUDIENCE,
    SCOPE_A,
    SCOPE_B,
    SCOPE_C,
    SCOPE_D,
    approved_call,
    call_fixture,
    harness,
)


def run(test):
    """Keep async tests independent of an undeclared pytest plugin."""
    return asyncio.run(test())


def test_calculator_integer_money_and_reserve():
    result = calculate(
        {
            "currency": "VND",
            "budget_minor": 10000000,
            "reserve_minor": 2000000,
            "items": [
                {
                    "label": "hotel",
                    "amount_minor": 5000000,
                    "quantity": 1,
                    "fees_minor": 0,
                },
                {
                    "label": "car",
                    "amount_minor": 2500000,
                    "quantity": 1,
                    "fees_minor": 100000,
                },
            ],
        }
    )
    assert result == {
        "currency": "VND",
        "total_minor": 7600000,
        "reserve_minor": 2000000,
        "remaining_minor": 400000,
        "within_budget": True,
    }


@pytest.mark.parametrize("bad", [1.5, True, -1, "1000", float("nan")])
def test_calculator_rejects_non_integer_or_negative_money(bad):
    with pytest.raises(ExecutionError, match="TOOL_INPUT_INVALID"):
        calculate(
            {
                "currency": "VND",
                "budget_minor": bad,
                "reserve_minor": 0,
                "items": [],
            }
        )


def test_guard_unbound_unavailable_version_and_unknown_effect():
    async def scenario():
        async with harness() as env:
            call = call_fixture()
            for mutation, code in [
                ({"version_id": "v2"}, "AGENT_VERSION_NOT_PINNED"),
                ({"tool_version_id": "technical.v1"}, "TOOL_UNAVAILABLE"),
            ]:
                with pytest.raises(ExecutionError, match=code):
                    await env.gateway.execute(SCOPE_A, {**call, **mutation})
            env.descriptor["available"] = False
            with pytest.raises(ExecutionError, match="TOOL_UNAVAILABLE"):
                await env.gateway.execute(SCOPE_A, call)
            env.descriptor["available"] = True
            env.descriptor["effect"] = "unknown"
            with pytest.raises(ExecutionError, match="TOOL_EFFECT_UNREVIEWED"):
                await env.gateway.execute(SCOPE_A, call)
            assert env.provider.calls == 0

    run(scenario)


@pytest.mark.parametrize("scope", [SCOPE_B, SCOPE_C, SCOPE_D])
def test_all_owner_dimensions_enforced(scope):
    async def scenario():
        async with harness() as env:
            with pytest.raises(ExecutionError, match="RESOURCE_NOT_FOUND"):
                await env.gateway.execute(scope, call_fixture())
            assert env.provider.calls == 0

    run(scenario)


def test_booking_requires_consent_and_replay_returns_same_result():
    async def scenario():
        async with harness() as env:
            call = await approved_call(env)
            assert env.provider.calls == 0
            result = await env.gateway.execute(SCOPE_A, call)
            assert result["status"] == "succeeded"
            assert result["output"]["status"] == "confirmed"
            replay = await env.gateway.execute(SCOPE_A, call)
            assert replay == result and env.provider.calls == 1
            approval = await env.repo.read(
                "approvals", SCOPE_A, call["approval_id"]
            )
            assert approval["status"] == "consumed"
            booking = await env.repo.read("bookings", SCOPE_A, call["call_id"])
            assert booking["status"] == "succeeded"

    run(scenario)


def test_changed_arguments_quote_expired_consent_rejected():
    async def scenario():
        async with harness() as env:
            call = await approved_call(env)
            with pytest.raises(ExecutionError, match="IDEMPOTENCY_CONFLICT"):
                await env.gateway.execute(
                    SCOPE_A, {**call, "arguments": {"room": "other"}}
                )
            env.quotes.quote["amount"]["amount_minor"] += 1
            with pytest.raises(
                ExecutionError, match="APPROVAL_CONTENT_CHANGED"
            ):
                await env.gateway.execute(SCOPE_A, call)
            env.quotes.quote["amount"]["amount_minor"] -= 1
            env.clock.advance(901)
            with pytest.raises(ExecutionError, match="APPROVAL_EXPIRED"):
                await env.gateway.execute(SCOPE_A, call)
            assert env.provider.calls == 0

    run(scenario)


def test_scope_decider_and_call_consent_isolation():
    async def scenario():
        async with harness() as env:
            proposed = await env.gateway.execute(SCOPE_A, call_fixture())
            approval = await env.repo.read(
                "approvals", SCOPE_A, proposed["approval_id"]
            )
            with pytest.raises(
                ExecutionError, match="APPROVAL_DECIDER_FORBIDDEN"
            ):
                await env.approvals.decide_approval(
                    SCOPE_A,
                    approval["id"],
                    "approve",
                    {"kind": "manager", "actor_id": "B"},
                    arguments_hash=approval["arguments_hash"],
                    quote_hash=approval["quote_hash"],
                )
            env.runtime.add_run(
                "run-B",
                audience={
                    **AUDIENCE,
                    "external_ticket_id": "TICKET-B",
                    "external_conversation_id": "CHAT-B",
                },
            )
            call_b = call_fixture("call-B", "run-B")
            await env.gateway.execute(SCOPE_A, call_b)
            with pytest.raises(ExecutionError, match="APPROVAL_CALL_MISMATCH"):
                await env.gateway.execute(
                    SCOPE_A, {**call_b, "approval_id": approval["id"]}
                )
            assert env.provider.calls == 0

    run(scenario)


@pytest.mark.parametrize("change", ["revoke", "remap", "cancel", "disable"])
def test_revalidation_prevents_new_calls(change):
    async def scenario():
        async with harness() as env:
            call = await approved_call(env)
            if change == "revoke":
                env.runtime.active = False
            if change == "remap":
                env.runtime.revision = 2
            if change == "cancel":
                env.runtime.contexts["run-A"]["status"] = "cancelled"
            if change == "disable":
                env.descriptor["available"] = False
            with pytest.raises(ExecutionError):
                await env.gateway.execute(SCOPE_A, call)
            assert env.provider.calls == 0

    run(scenario)


def test_timeout_after_write_is_unknown_and_never_retried():
    async def scenario():
        async with harness(tracking=True) as env:
            call = await approved_call(env)
            env.provider.fault = "timeout_after_write"
            first = await env.gateway.execute(SCOPE_A, call)
            second = await env.gateway.execute(SCOPE_A, call)
            assert first["status"] == second["status"] == "unknown"
            assert env.provider.calls == 1
            operations = await env.operations.get_for_workflow(
                SCOPE_A, "workflow-A"
            )
            assert operations[0]["creation_status"] == "unknown"
            assert operations[0]["external_job_id"] is None
            assert "FAKE committed" not in str(first)

    run(scenario)


def test_sync_booking_and_calculator_have_no_tracking_objects():
    async def scenario():
        async with harness() as env:
            call = await approved_call(env)
            await env.gateway.execute(SCOPE_A, call)
            assert (
                await env.operations.get_for_workflow(SCOPE_A, "workflow-A")
                == []
            )
            async with env.repo.transaction() as uow:
                assert await env.repo.find("inbox", {}, uow) == []
        async with harness(calculator=True) as env:
            call = call_fixture(calculator=True)
            call["arguments"] = {
                "currency": "VND",
                "budget_minor": 10000000,
                "reserve_minor": 2000000,
                "items": [],
            }
            result = await env.gateway.execute(SCOPE_A, call)
            assert result["output"]["remaining_minor"] == 8000000
            assert env.provider.calls == 0
            assert (
                await env.operations.get_for_workflow(SCOPE_A, "workflow-A")
                == []
            )

    run(scenario)


def test_evaluation_credentials_and_live_schema_drift_blocked():
    async def scenario():
        async with harness() as env:
            call = await approved_call(env)
            env.runtime.contexts["run-A"]["mode"] = "evaluation"
            env.secrets.environment = "production"
            result = await env.gateway.execute(SCOPE_A, call)
            assert result["status"] == "failed"
            assert result["error"] == "EVAL_PRODUCTION_CREDENTIAL_FORBIDDEN"
            assert env.provider.calls == 0
        async with harness() as env:
            call = await approved_call(env)
            env.provider.schema = {"type": "object"}
            result = await env.gateway.execute(SCOPE_A, call)
            assert (
                result["error"] == "MCP_SCHEMA_DRIFT"
                and env.provider.calls == 0
            )

    run(scenario)


def test_partial_outcomes_do_not_cancel_successful_booking():
    result = summarize(
        [
            {"status": "succeeded", "call_id": "hotel"},
            {"status": "unknown", "call_id": "car"},
        ]
    )
    assert result["status"] == "partial" and result["requires_attention"]
    assert result["automatic_compensation"] is False


def test_persisted_approval_survives_repository_restart(tmp_path):
    async def scenario():
        url = "sqlite+aiosqlite:///" + str(
            tmp_path / "execution.sqlite3"
        ).replace("\\", "/")
        async with harness(url) as env:
            call = await approved_call(env)
        async with harness(url) as restarted:
            result = await restarted.gateway.execute(SCOPE_A, call)
            assert (
                result["status"] == "succeeded"
                and restarted.provider.calls == 1
            )

    run(scenario)
