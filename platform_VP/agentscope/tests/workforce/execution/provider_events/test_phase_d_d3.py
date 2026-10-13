"""D3 regression with real SQL/Registry/HMAC and a typed test sink."""

import asyncio
from datetime import timedelta

import pytest

from agentscope.app.workforce.execution import ExecutionError
from agentscope.app.workforce.execution.external_operations import (
    OperationReconciler,
)
from agentscope.app.workforce.execution.provider_events import (
    ProviderEventProcessor,
)
from agentscope.app.workforce.foundation import DurableJobWorker
from agentscope.app.workforce.foundation.event_delivery import DurableJob
from execution_fakes import SCOPE_A, SCOPE_B, SCOPE_C, SCOPE_D
from async_partners import ProviderBackend
from phase_c_fakes import c3_harness, principal


def test_delta_gap_recovers_after_query_with_exact_disabled_pin():
    async def scenario():
        async with c3_harness(event_mode="delta") as env:
            operation = env.operation
            events = ProviderBackend.progress_events(
                operation["external_job_id"], operation["correlation_id"]
            )
            first = await env.ingress.accept(
                await principal(env, events[0]), events[0]
            )
            assert (
                await env.processor.process(first["receipt_id"]) == "applied"
            )
            gap = await env.ingress.accept(
                await principal(env, events[2]), events[2]
            )
            assert (
                await env.processor.process(gap["receipt_id"]) == "quarantined"
            )
            before = await env.repo.read(
                "operations", SCOPE_A, operation["id"]
            )
            assert before["last_provider_version"] == 1
            assert before["job_status"] == "assigned"
            await env.registry_service.set_enabled(
                env.config.tool_version_id, False, env.config.snapshot_ref
            )

            class Queries:
                async def query(self, scope, op, timer):
                    assert (
                        op["protocol_hash"]
                        == env.config.snapshot_ref.schema_hash
                    )
                    return {
                        "external_job_id": op["external_job_id"],
                        "status": "on_the_way",
                        "provider_version": 2,
                    }

            reconciler = OperationReconciler(
                env.repo,
                Queries(),
                env.protocols,
                env.workflow_adapter,
                env.jobs,
            )
            assert (
                await reconciler.reconcile(
                    SCOPE_A, operation["id"], "d3-gap-query"
                )
                == "applied"
            )
            processor = ProviderEventProcessor(
                env.ingress, env.workflow_adapter
            )
            assert await processor.process(gap["receipt_id"]) == "applied"
            after = await env.repo.read("operations", SCOPE_A, operation["id"])
            assert after["job_status"] == "arrived"
            assert after["last_provider_version"] == 3
            assert after["protocol_hash"] == operation["protocol_hash"]
            count = len(env.typed_workflow.seen)
            assert await processor.process(gap["receipt_id"]) == "applied"
            assert len(env.typed_workflow.seen) == count
            assert env.provider.calls == 1

    asyncio.run(scenario())


def test_quarantined_unbound_event_recovers_via_durable_recovery_job():
    async def scenario():
        async with c3_harness() as env:
            # The job-only event arrives before the provider creation reply
            # binds this second intent. No payload owner is trusted.
            context = dict(env.runtime.contexts["run-A"])
            context.update(
                workflow_id="workflow-recovery",
                conversation_id="conversation-recovery",
                group_id="group-recovery",
            )
            protocol = env.operation["protocol"]
            async with env.repo.transaction() as tx:
                operation = await env.operations.prepare(
                    SCOPE_A,
                    context,
                    {"call_id": "call-recovery"},
                    protocol,
                    tx,
                )
            event = ProviderBackend.progress_events(
                "TEST-recovered-job", operation["correlation_id"]
            )[0]
            event.pop("client_reference")
            verified = await principal(env, event)
            receipt = await env.ingress.accept(verified, event)
            worker = DurableJobWorker(
                env.jobs,
                {"provider_event": env.processor.handle_job},
                worker_id="d3",
            )
            assert (await worker.run_once()).status == "succeeded"
            assert (
                await env.ingress.read_receipt(verified, receipt["receipt_id"])
            )["ingestion_status"] == "quarantined"
            assert env.typed_workflow.seen == []
            async with env.repo.transaction() as tx:
                await env.operations.bind_result(
                    SCOPE_A,
                    operation["id"],
                    {
                        "creation_status": "succeeded",
                        "external_job_id": "TEST-recovered-job",
                        "job_status": "assigned",
                        "pending": True,
                    },
                    tx,
                )
                # Explicit recovery dispatch through Foundation's JobPort.
                # HTTP replay retains the original receipt and does not mint
                # another ingestion job or conceal the quarantine outcome.
                await env.jobs.enqueue_provider(
                    verified.model_dump(mode="json"),
                    "provider_event",
                    {"receipt_id": receipt["receipt_id"]},
                    "d3-recovery-1",
                    uow=tx,
                )
            duplicate = await env.ingress.accept(
                await principal(env, event), event
            )
            assert duplicate["duplicate"]
            assert duplicate["receipt_id"] == receipt["receipt_id"]
            processor = ProviderEventProcessor(
                env.ingress, env.workflow_adapter
            )
            replacement = DurableJobWorker(
                env.jobs,
                {"provider_event": processor.handle_job},
                worker_id="d3-restart",
            )
            assert (await replacement.run_once()).status == "succeeded"
            assert (
                await env.ingress.read_receipt(verified, receipt["receipt_id"])
            )["ingestion_status"] == "applied"
            assert len(env.typed_workflow.seen) == 1
            assert (await replacement.run_once()).status == "idle"

    asyncio.run(scenario())


def test_interleaved_scopes_cannot_read_query_or_rebind_other_owner():
    async def scenario():
        async with c3_harness() as env:
            operations = [env.operation]
            scopes = [SCOPE_A, SCOPE_B, SCOPE_C, SCOPE_D]
            for index, scope in enumerate(scopes[1:], 1):
                await env.protocols.bind(scope).port.publish(env.config)
                protocol = await env.protocols.get_snapshot(
                    scope, env.config.tool_version_id
                )
                context = dict(env.runtime.contexts["run-A"])
                context.update(
                    workflow_id=f"workflow-scope-{index}",
                    conversation_id=f"conversation-scope-{index}",
                    group_id=f"group-scope-{index}",
                )
                async with env.repo.transaction() as tx:
                    operations.append(
                        await env.operations.prepare(
                            scope,
                            context,
                            {"call_id": f"call-scope-{index}"},
                            protocol,
                            tx,
                        )
                    )
            for index in (2, 0, 3, 1):
                scope, operation = scopes[index], operations[index]
                event = ProviderBackend.progress_events(
                    operation["external_job_id"] or f"TEST-scope-job-{index}",
                    operation["correlation_id"],
                    prefix=f"scope-{index}",
                )[0]
                receipt = await env.ingress.accept(
                    await principal(env, event), event
                )
                assert (
                    await env.processor.process(receipt["receipt_id"])
                    == "applied"
                )
                current = await env.repo.read(
                    "operations", scope, operation["id"]
                )
                assert current["job_status"] == "assigned"
                assert current["scope"] == scope
                for other_scope in scopes + [
                    {**SCOPE_A, "tenant_id": "other-tenant"}
                ]:
                    if other_scope == scope:
                        continue
                    with pytest.raises(
                        ExecutionError, match="RESOURCE_NOT_FOUND"
                    ):
                        await env.repo.read(
                            "operations", other_scope, operation["id"]
                        )
                    with pytest.raises(
                        ExecutionError, match="RESOURCE_NOT_FOUND"
                    ):
                        await OperationReconciler(
                            env.repo,
                            None,
                            env.protocols,
                            env.workflow_adapter,
                            env.jobs,
                        ).reconcile(
                            other_scope, operation["id"], "wrong-owner-query"
                        )
            assert len(env.typed_workflow.seen) == 4
            states = [
                await env.repo.read("operations", scope, op["id"])
                for scope, op in zip(scopes, operations)
            ]
            conflict = ProviderBackend.progress_events(
                states[0]["external_job_id"],
                states[1]["correlation_id"],
                prefix="cross-scope-conflict",
            )[0]
            receipt = await env.ingress.accept(
                await principal(env, conflict), conflict
            )
            assert (
                await env.processor.process(receipt["receipt_id"])
                == "quarantined"
            )
            assert states == [
                await env.repo.read("operations", scope, op["id"])
                for scope, op in zip(scopes, operations)
            ]
            assert len(env.typed_workflow.seen) == 4
            for event, trigger in env.typed_workflow.seen:
                operation = next(
                    op
                    for op in operations
                    if op["workflow_id"] == trigger.workflow_id
                )
                assert event.protocol_schema_hash == operation["protocol_hash"]
                assert trigger.cause.operation_id == operation["id"]
                assert event.client_reference == operation["correlation_id"]
            # A leased job cannot substitute another provider namespace even
            # when its receipt ID is known.
            claim = await env.jobs.claim("d3-forged", timedelta(seconds=30))
            forged = DurableJob.model_validate(
                claim.job.model_dump()
            ).model_copy(update={"tenant_id": "other-tenant"})
            with pytest.raises(ExecutionError, match="RESOURCE_NOT_FOUND"):
                await env.processor.handle_job(forged)
            assert len(env.typed_workflow.seen) == 4

    asyncio.run(scenario())
