"""Execution C3: real C1 auth/UOW/jobs and C2 SQL protocol provider."""

import asyncio
from datetime import timedelta

import httpx
import pytest
from fastapi import FastAPI
from sqlalchemy import update

from agentscope.app.workforce.contracts import (
    Scope,
    VerifiedProviderContext,
)
from agentscope.app.workforce.execution import create_router
from agentscope.app.workforce.execution.external_operations import (
    OperationReconciler,
)
from agentscope.app.workforce.execution._utils import (
    ExecutionError,
    freeze,
    instant,
    value,
)
from agentscope.app.workforce.execution.provider_events._context import (
    PersistedProviderEventContext,
)
from agentscope.app.workforce.foundation import DurableJobWorker
from agentscope.app.workforce.foundation._tables import (
    durable_jobs,
    provider_credentials,
)
from agentscope.app.workforce.registry.event_protocols import AsyncToolProtocol
from async_partners import ProviderBackend
from execution_fakes import AUDIENCE, SCOPE_A, SCOPE_B, test_events
from phase_c_fakes import c3_harness, principal, signed, table_rows


def run(scenario):
    asyncio.run(scenario())


def events(env):
    op = env.operation
    return ProviderBackend.progress_events(
        op["external_job_id"], op["correlation_id"]
    )


def app_for(env):
    app = FastAPI()
    app.include_router(
        create_router(None, None, None, env.ingress, None, None, env.auth)
    )
    return app


def test_signed_http_to_real_durable_worker_and_persisted_protocol_loader():
    async def scenario():
        async with c3_harness() as env:
            worker = DurableJobWorker(
                env.jobs,
                {"provider_event": env.processor.handle_job},
                worker_id="TEST-C3-worker",
            )
            async with httpx.AsyncClient(
                transport=httpx.ASGITransport(app=app_for(env)),
                base_url="http://test",
            ) as client:
                for event in events(env):
                    raw, headers = signed(env, event)
                    response = await client.post(
                        "/workforce/v1/provider/job-events",
                        content=raw,
                        headers=headers,
                    )
                    assert response.status_code == 202, response.text
                    receipt = response.json()
                    duplicate = await client.post(
                        "/workforce/v1/provider/job-events",
                        content=raw,
                        headers=headers,
                    )
                    assert duplicate.json()["duplicate"]
                    assert (
                        duplicate.json()["receipt_id"] == receipt["receipt_id"]
                    )
                    async with env.repo.transaction() as uow:
                        row = await env.repo.get(
                            "inbox", receipt["receipt_id"], uow
                        )
                    stored = VerifiedProviderContext.model_validate(
                        row["provider_ref"]
                    )
                    assert stored.credential_id == "TEST-api-credential"
                    assert stored.signing_key_id == "TEST-signing-key"
                    assert stored.authenticated_at == env.clock()
                    jobs = await table_rows(env, durable_jobs)
                    assert len(jobs) == len(env.typed_workflow.seen) + 1
                    assert jobs[-1]["owner_kind"] == "provider"
                    assert jobs[-1]["manager_account_id"] is None
                    assert (await worker.run_once()).status == "succeeded"
                    _, receipt_headers = signed(env)
                    current = await client.get(
                        "/workforce/v1/provider/event-receipts/"
                        + receipt["receipt_id"],
                        headers=receipt_headers,
                    )
                    assert current.status_code == 200
                    assert current.json()["ingestion_status"] == "applied"
                    assert set(current.json()) == {
                        "receipt_id",
                        "ingestion_status",
                        "duplicate",
                        "received_at",
                    }
            operation = await env.repo.read(
                "operations", SCOPE_A, env.operation["id"]
            )
            assert operation["job_status"] == "completed"
            assert not operation["pending"]
            assert len(env.typed_workflow.seen) == 4
            for normalized, _ in env.typed_workflow.seen:
                assert (
                    normalized.protocol_schema_hash
                    == env.config.snapshot_ref.schema_hash
                )
            assert (await worker.run_once()).status == "idle"

    run(scenario)


@pytest.mark.parametrize(
    "failure", ["signature", "timestamp", "scope", "operation"]
)
def test_bad_provider_http_never_creates_inbox_or_job(failure):
    async def scenario():
        async with c3_harness() as env:
            event = events(env)[0]
            if failure == "scope":
                event["scope"] = SCOPE_B
            raw, headers = signed(env, event)
            if failure == "signature":
                headers["x-partner-signature"] = "v1=" + "0" * 64
            elif failure == "timestamp":
                headers["x-partner-timestamp"] = "0"
            elif failure == "operation":
                async with env.repo.transaction() as uow:
                    await uow.execute(
                        update(provider_credentials).values(
                            allowed_operations=["read_event_receipt"]
                        )
                    )
            async with httpx.AsyncClient(
                transport=httpx.ASGITransport(app=app_for(env)),
                base_url="http://test",
            ) as client:
                response = await client.post(
                    "/workforce/v1/provider/job-events",
                    content=raw,
                    headers=headers,
                )
            expected = {"scope": 422, "operation": 403}.get(failure, 401)
            assert response.status_code == expected
            assert "signature mismatch" not in response.text
            assert await table_rows(env, durable_jobs) == []
            async with env.repo.transaction() as uow:
                assert await env.repo.find("inbox", {}, uow) == []

    run(scenario)


def test_revoke_before_worker_retry_preserves_original_inbox_and_facts():
    async def scenario():
        async with c3_harness() as env:
            event = events(env)[0]
            verified = await principal(env, event)
            receipt = await env.ingress.accept(verified, event)
            async with env.repo.transaction() as uow:
                await uow.execute(
                    update(provider_credentials).values(status="revoked")
                )
            with pytest.raises(PermissionError):
                await env.processor.process(receipt["receipt_id"])
            assert env.typed_workflow.seen == []
            async with env.repo.transaction() as uow:
                row = await env.repo.get("inbox", receipt["receipt_id"], uow)
                assert row["ingestion_status"] == "accepted"
                assert row["provider_ref"] == value(verified)
                await uow.execute(
                    update(provider_credentials).values(status="active")
                )
            assert (
                await env.processor.process(receipt["receipt_id"]) == "applied"
            )
            normalized = env.typed_workflow.seen[-1][0]
            assert normalized.inbox_event_id == receipt["receipt_id"]
            assert normalized.received_at == instant(receipt["received_at"])
            async with env.repo.transaction() as uow:
                await uow.execute(
                    update(provider_credentials).values(status="revoked")
                )
            with pytest.raises(PermissionError):
                await env.processor.process(receipt["receipt_id"])
            assert len(env.typed_workflow.seen) == 1

    run(scenario)


def test_sql_enqueue_failure_rolls_back_before_ack():
    async def scenario():
        async with c3_harness() as env:
            enqueue = env.jobs._repository.enqueue_once

            async def fail_after_insert(job, uow=None):
                await enqueue(job, uow)
                raise RuntimeError("TEST enqueue failed after SQL insert")

            env.jobs._repository.enqueue_once = fail_after_insert
            event = events(env)[0]
            with pytest.raises(RuntimeError):
                await env.ingress.accept(await principal(env, event), event)
            assert await table_rows(env, durable_jobs) == []
            async with env.repo.transaction() as uow:
                assert await env.repo.find("inbox", {}, uow) == []

    run(scenario)


def test_canonical_uow_rolls_back_sink_sql_and_runs_signal_only_after_commit():
    async def scenario():
        async with c3_harness() as env:
            baseline = await table_rows(env, test_events)
            event = events(env)[1]
            receipt = await env.ingress.accept(
                await principal(env, event), event
            )
            original = env.typed_workflow.apply_external_event
            signals = []
            fail = True

            async def sink(scope, operation_ref, normalized, uow=None):
                result = await original(scope, operation_ref, normalized, uow)
                uow.add_after_commit(
                    lambda: signals.append(normalized.inbox_event_id)
                )
                if fail:
                    raise RuntimeError("TEST sink failed after SQL insert")
                assert not signals
                return result

            env.typed_workflow.apply_external_event = sink
            with pytest.raises(RuntimeError):
                await env.processor.process(receipt["receipt_id"])
            assert signals == []
            assert await table_rows(env, test_events) == baseline
            operation = await env.repo.read(
                "operations", SCOPE_A, env.operation["id"]
            )
            assert operation["job_status"] == "assigned"
            fail = False
            assert (
                await env.processor.process(receipt["receipt_id"]) == "applied"
            )
            assert signals == [receipt["receipt_id"]]
            assert (
                await env.processor.process(receipt["receipt_id"]) == "applied"
            )
            assert len(signals) == 1
            assert len(await table_rows(env, test_events)) == len(baseline) + 1

    run(scenario)


@pytest.mark.parametrize(
    "mutation",
    [
        "actor",
        "credential",
        "hash",
        "body",
        "inbox",
        "time",
        "scope",
        "integration",
        "pin",
        "uow",
    ],
)
def test_loader_rejects_forged_context_before_registry_normalization(mutation):
    async def scenario():
        async with c3_harness() as env:
            event = events(env)[0]
            verified = await principal(env, event)
            receipt = await env.ingress.accept(verified, event)
            async with env.repo.transaction() as uow:
                context = {
                    "provider_context": value(verified),
                    "scope": Scope.model_validate(SCOPE_A),
                    "provider_integration_id": (
                        verified.provider_integration_id
                    ),
                    "protocol_snapshot": env.config.snapshot_ref,
                    "inbox_event_id": receipt["receipt_id"],
                    "received_at": instant(receipt["received_at"]),
                    "uow": uow,
                }
                actor = verified.actor
                if mutation == "actor":
                    actor = actor.model_copy(update={"actor_id": "wrong"})
                elif mutation == "credential":
                    context["provider_context"]["signing_key_id"] = "wrong"
                elif mutation == "hash":
                    row = await env.repo.get(
                        "inbox", receipt["receipt_id"], uow
                    )
                    row["payload_hash"] = "0" * 64
                    await env.repo.save("inbox", row, row["revision"], uow)
                elif mutation == "body":
                    event["data"]["eta_minutes"] = 15
                elif mutation == "inbox":
                    context["inbox_event_id"] = "missing"
                elif mutation == "time":
                    context["received_at"] = instant("2020-01-01T00:00:00Z")
                elif mutation == "scope":
                    context["scope"] = Scope.model_validate(SCOPE_B)
                elif mutation == "integration":
                    context["provider_integration_id"] = "wrong"
                elif mutation == "pin":
                    context["protocol_snapshot"] = (
                        env.config.snapshot_ref.model_copy(
                            update={"schema_hash": "0" * 64}
                        )
                    )
                else:
                    context["uow"] = None
                loader = PersistedProviderEventContext(
                    env.repo, env.auth, env.operations, context
                )
                with pytest.raises(PermissionError):
                    await loader(actor, event)
            assert env.typed_workflow.seen == []

    run(scenario)


def test_current_disable_and_drift_preserve_exact_old_event_create_query_pin():
    async def scenario():
        async with c3_harness() as env:
            newer = AsyncToolProtocol.model_validate(
                value(env.config)
                | {"protocol_version": "2", "status_field": "new_status"}
            )
            await env.registry_service.publish(newer, env.config.snapshot_ref)
            await env.registry_service.set_enabled(
                newer.tool_version_id, False, newer.snapshot_ref
            )
            with pytest.raises(PermissionError):
                await env.protocols.get_snapshot(
                    SCOPE_A, newer.tool_version_id
                )
            pinned = env.operation["protocol"]
            output = {
                "external_job_id": env.operation["external_job_id"],
                "status": "completed",
                "provider_version": 4,
            }
            assert (
                await env.protocols.normalize_creation_result(pinned, output)
            )["pending"] is False
            query = await env.protocols.normalize_query_result(pinned, output)
            assert query["terminal"]
            event = events(env)[-1]
            receipt = await env.ingress.accept(
                await principal(env, event), event
            )
            assert (
                await env.processor.process(receipt["receipt_id"]) == "applied"
            )
            assert (
                env.typed_workflow.seen[-1][0].protocol_schema_hash
                == env.config.snapshot_ref.schema_hash
            )
            wrong = freeze(pinned)
            wrong["scope"] = SCOPE_B
            with pytest.raises(KeyError):
                await env.protocols.normalize_query_result(wrong, output)

    run(scenario)


def test_provider_job_cannot_point_to_another_integration_receipt():
    async def scenario():
        async with c3_harness() as env:
            event = events(env)[0]
            receipt = await env.ingress.accept(
                await principal(env, event), event
            )
            job = (
                await env.jobs.claim("TEST-worker", timedelta(seconds=30))
            ).job
            forged = job.model_copy(
                update={"provider_integration_id": "other"}
            )
            with pytest.raises(ExecutionError, match="RESOURCE_NOT_FOUND"):
                await env.processor.handle_job(forged)
            assert env.typed_workflow.seen == []
            assert (await env.processor.handle_job(job))[
                "receipt_id"
            ] == receipt["receipt_id"]

    run(scenario)


def test_scoped_registry_services_do_not_mix_two_interleaved_owners():
    async def scenario():
        async with c3_harness() as env:
            config_b = AsyncToolProtocol.model_validate(
                value(env.config) | {"protocol_version": "owner-B"}
            )
            await env.protocols.bind(SCOPE_B).port.publish(config_b)
            protocol_b = await env.protocols.get_snapshot(
                SCOPE_B, config_b.tool_version_id
            )
            env.runtime.add_run(
                "run-B",
                scope=SCOPE_B,
                audience={**AUDIENCE, "external_ticket_id": "TICKET-B"},
            )
            async with env.repo.transaction() as uow:
                op_b = await env.operations.prepare(
                    SCOPE_B,
                    env.runtime.contexts["run-B"],
                    {"call_id": "call-B"},
                    protocol_b,
                    uow,
                )
            b_events = ProviderBackend.progress_events(
                "TEST-job-B", op_b["correlation_id"], prefix="B"
            )
            # B's first event arrives before its creation response binds job.
            for event in (
                b_events[0],
                events(env)[0],
                b_events[-1],
                events(env)[-1],
            ):
                receipt = await env.ingress.accept(
                    await principal(env, event), event
                )
                assert (
                    await env.processor.process(receipt["receipt_id"])
                    == "applied"
                )
            a = await env.repo.read("operations", SCOPE_A, env.operation["id"])
            b = await env.repo.read("operations", SCOPE_B, op_b["id"])
            assert a["job_status"] == b["job_status"] == "completed"
            assert b["external_job_id"] == "TEST-job-B"
            assert a["protocol_hash"] != b["protocol_hash"]
            for normalized, trigger in env.typed_workflow.seen:
                expected = b if trigger.workflow_id == "workflow-B" else a
                assert (
                    normalized.protocol_schema_hash
                    == expected["protocol_hash"]
                )
            with pytest.raises(ExecutionError, match="RESOURCE_NOT_FOUND"):
                await env.repo.read("operations", SCOPE_A, op_b["id"])

    run(scenario)


def test_registry_pin_query_schedules_scoped_timer_without_inbox():
    async def scenario():
        async with c3_harness() as env:

            class Queries:
                async def query(self, scope, operation, timer_id):
                    assert (
                        operation["protocol_hash"]
                        == env.config.snapshot_ref.schema_hash
                    )
                    return {
                        "external_job_id": operation["external_job_id"],
                        "status": "completed",
                        "provider_version": 4,
                    }

            reconciler = OperationReconciler(
                env.repo,
                Queries(),
                env.protocols,
                env.workflow_adapter,
                env.jobs,
            )
            async with env.repo.transaction() as uow:
                await reconciler.schedule(
                    SCOPE_A,
                    env.operation["id"],
                    "TEST-query-timer",
                    env.clock(),
                    uow,
                )
            jobs = await table_rows(env, durable_jobs)
            assert len(jobs) == 1
            assert jobs[0]["owner_kind"] == "scope"
            assert (
                jobs[0]["manager_account_id"] == SCOPE_A["manager_account_id"]
            )
            await env.registry_service.set_enabled(
                env.config.tool_version_id, False, env.config.snapshot_ref
            )
            assert (
                await reconciler.reconcile(
                    SCOPE_A, env.operation["id"], "TEST-query-timer"
                )
                == "applied"
            )
            event, trigger = env.typed_workflow.query_seen[-1]
            assert (
                event["protocol_schema_hash"]
                == env.config.snapshot_ref.schema_hash
            )
            assert trigger.cause.kind == "timer"
            assert "inbox_event_id" not in event
            async with env.repo.transaction() as uow:
                assert await env.repo.find("inbox", {}, uow) == []

    run(scenario)
