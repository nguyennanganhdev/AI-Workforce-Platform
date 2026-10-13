"""Interrupted runs, provider result persistence and isolated idempotency."""

import asyncio


from agentscope.app.workforce.execution import ExecutionError
from agentscope.app.workforce.execution._reconciliation import (
    BookingReconciler,
)
from agentscope.app.workforce.execution.external_operations import (
    OperationReconciler,
)
from execution_fakes import (
    AUDIENCE,
    SCOPE_A,
    approved_call,
    call_fixture,
    harness,
)


def test_cancellation_after_provider_write_keeps_actual_result():
    async def scenario():
        async with harness() as env:
            call = await approved_call(env)

            async def cancel_after_write(arguments, result):
                env.runtime.contexts["run-A"]["status"] = "cancelled"

            env.provider.after_write = cancel_after_write
            result = await env.gateway.execute(SCOPE_A, call)
            assert result["status"] == "succeeded" and env.provider.calls == 1
            assert (await env.repo.read("bookings", SCOPE_A, "call-A"))[
                "status"
            ] == "succeeded"

    asyncio.run(scenario())


def test_same_idempotency_key_in_distinct_groups_does_not_share_state():
    async def scenario():
        async with harness() as env:
            env.runtime.add_run(
                "run-B",
                audience={
                    **AUDIENCE,
                    "external_ticket_id": "TICKET-B",
                    "external_conversation_id": "CHAT-B",
                },
            )
            a, b = (
                call_fixture("call-A", "run-A"),
                call_fixture("call-B", "run-B"),
            )
            a["idempotency_key"] = b["idempotency_key"] = "same-local-key"
            a, b = await approved_call(env, a), await approved_call(env, b)
            assert a["approval_id"] != b["approval_id"]
            ra, rb = (
                await env.gateway.execute(SCOPE_A, a),
                await env.gateway.execute(SCOPE_A, b),
            )
            assert ra["id"] != rb["id"] and ra["group_id"] != rb["group_id"]
            assert env.provider.calls == 2

    asyncio.run(scenario())


def test_crash_after_intent_is_unknown_until_reconciled_never_recreate():
    async def scenario():
        async with harness(tracking=True) as env:
            call = await approved_call(env)
            context, descriptor = await env.gateway.policy.check(SCOPE_A, call)
            quote = await env.approvals.verified_quote(
                SCOPE_A, context, call, descriptor
            )
            async with env.repo.transaction() as uow:
                _, dispatch = await env.transactions.reserve(
                    SCOPE_A, context, call, descriptor, quote, uow
                )
                op = await env.operations.prepare(
                    SCOPE_A, context, call, env.protocol, uow
                )
            assert dispatch and env.provider.calls == 0
            result = await env.transactions.recover_abandoned(
                SCOPE_A, call["call_id"]
            )
            assert result["status"] == "unknown"
            replay = await env.gateway.execute(SCOPE_A, call)
            assert replay["status"] == "unknown" and env.provider.calls == 0
            reconciler = OperationReconciler(
                env.repo, None, env.protocols, env.workflow, env.jobs
            )
            assert (
                await reconciler.escalate(
                    SCOPE_A, op["id"], "SLA-expired", "PROVIDER_UNKNOWN"
                )
                == "needs_attention"
            )
            assert (
                await reconciler.escalate(
                    SCOPE_A, op["id"], "SLA-expired", "PROVIDER_UNKNOWN"
                )
                == "needs_attention"
            )
            current = await env.repo.read("operations", SCOPE_A, op["id"])
            assert current["pending"] and current["job_status"] is None

    asyncio.run(scenario())


def test_last_moment_revocation_after_secret_resolution_stops_send():
    async def scenario():
        async with harness() as env:
            call = await approved_call(env)
            original = env.secrets.resolve_for_execution

            async def revoked_after_resolve(scope, credential_ref, mode):
                credential = await original(scope, credential_ref, mode)
                env.runtime.active = False
                return credential

            env.secrets.resolve_for_execution = revoked_after_resolve
            result = await env.gateway.execute(SCOPE_A, call)
            assert (
                result["status"] == "failed"
                and result["error"] == "AUTHORIZATION_REVOKED"
            )
            assert env.provider.calls == 0

    asyncio.run(scenario())


def test_invalid_creation_result_is_unknown_and_drops_output():
    async def scenario():
        async with harness(tracking=True) as env:
            call = await approved_call(env)

            async def bad_result(protocol, output):
                raise ExecutionError("PROVIDER_RESPONSE_INVALID", 422)

            env.protocols.normalize_creation_result = bad_result
            result = await env.gateway.execute(SCOPE_A, call)
            assert result["status"] == "unknown" and result["output"] is None
            assert env.provider.calls == 1

    asyncio.run(scenario())


def test_sync_unknown_queries_provider_reference_without_async_operation():
    async def scenario():
        async with harness() as env:
            call = await approved_call(env)
            env.provider.fault = "timeout_after_write"
            await env.gateway.execute(SCOPE_A, call)

            class Queries:
                async def query_booking(
                    self, scope, booking, stored_call, cause_id
                ):
                    assert booking["provider_reference"] == call["call_id"]
                    return {
                        "provider_reference": booking["provider_reference"],
                        "status": "succeeded",
                        "output": {"status": "confirmed"},
                        "external_transaction_id": "FAKE-booking-1",
                    }

            reconciler = BookingReconciler(env.repo, Queries(), env.workflow)
            assert (
                await reconciler.reconcile(SCOPE_A, call["call_id"], "query-1")
                == "succeeded"
            )
            assert (
                await reconciler.reconcile(SCOPE_A, call["call_id"], "query-1")
                == "succeeded"
            )
            assert (
                await env.operations.get_for_workflow(SCOPE_A, "workflow-A")
                == []
            )
            assert env.provider.calls == 1

    asyncio.run(scenario())
