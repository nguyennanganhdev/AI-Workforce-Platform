"""Consumer and independent Phase-B checks using NPD fake/PHH proposals."""

import asyncio

import httpx
import pytest
from fastapi import FastAPI
from sqlalchemy import select

from agentscope.app.workforce.contracts import (
    AsyncProtocolPort,
    ExternalOperation,
    ExternalOperationPort,
    Scope,
)
from agentscope.app.workforce.execution import create_router
from agentscope.app.workforce.execution._utils import (
    ExecutionError,
    digest,
    freeze,
    value,
)
from agentscope.app.workforce.execution.external_operations import (
    ExternalOperationAdapter,
    OperationReconciler,
)
from agentscope.app.workforce.execution.external_operations._protocol import (
    protocol_hash,
)
from agentscope.app.workforce.registry.event_protocols import AsyncToolProtocol
from agentscope.app.workforce.foundation.event_delivery import (
    DurableJobService,
)
from async_partners import ProviderBackend
from execution_fakes import (
    MANAGER,
    SCOPE_A,
    SCOPE_B,
    AUDIENCE,
    approved_call,
    call_fixture,
    harness,
    test_events,
)
from phase_ab_fakes import JobEnqueueRepository, wire_protocols


def run(scenario):
    asyncio.run(scenario())


async def prepare(env):
    wired = await wire_protocols(env)
    call = await approved_call(env)
    await env.gateway.execute(SCOPE_A, call)
    op = (await env.operations.get_for_workflow(SCOPE_A, "workflow-A"))[0]
    return wired, op


def events(op):
    return ProviderBackend.progress_events(
        op["external_job_id"], op["correlation_id"]
    )


async def applied_events(env):
    async with env.repo.transaction() as uow:
        rows = (await uow.execute(select(test_events))).mappings().all()
        return [r for r in rows if r["id"].startswith("apply-")]


def test_pinned_snapshot_and_shared_port_use_canonical_config_hash():
    async def scenario():
        async with harness(tracking=True) as env:
            (config, principal, port, configs, sink, _), op = await prepare(
                env
            )
            assert isinstance(port, AsyncProtocolPort)
            assert op["protocol_hash"] == config.snapshot_ref.schema_hash
            assert op["protocol_hash"] != digest(op["protocol"])
            new_config = value(config)
            new_config.update(protocol_version="2", timeout_seconds=120)
            newer = AsyncToolProtocol.model_validate(new_config)
            configs.append(newer)
            port.protocols[newer.snapshot_ref.schema_hash] = (
                newer.model_dump_json()
            )
            port.current[config.tool_version_id] = newer.snapshot_ref
            new_pin = await env.protocols.get_snapshot(
                Scope.model_validate(SCOPE_A), config.tool_version_id
            )
            assert protocol_hash(new_pin) == newer.snapshot_ref.schema_hash
            assert (
                protocol_hash(op["protocol"])
                == config.snapshot_ref.schema_hash
            )
            receipt = await env.ingress.accept(principal, events(op)[0])
            assert (
                await env.processor.process(receipt["receipt_id"]) == "applied"
            )
            assert (
                sink.seen[-1][0].protocol_schema_hash
                == config.snapshot_ref.schema_hash
            )
            tampered = freeze(op["protocol"])
            tampered["configuration"]["timeout_seconds"] = 1
            with pytest.raises(ExecutionError, match="PIN_MISMATCH"):
                protocol_hash(tampered)
            with pytest.raises(PermissionError):
                await env.protocols.get_snapshot(
                    Scope.model_validate(SCOPE_B), config.tool_version_id
                )

    run(scenario)


def test_provider_http_lifecycle_uses_shared_event_and_phh_trigger_schema():
    async def scenario():
        async with harness(tracking=True) as env:
            (config, _, _, _, sink, _), op = await prepare(env)

            async def manager():
                return {"scope": SCOPE_A, "actor": MANAGER}

            app = FastAPI()
            app.include_router(
                create_router(
                    env.gateway,
                    env.approvals,
                    None,
                    env.ingress,
                    manager,
                    None,
                    env.auth,
                )
            )
            async with httpx.AsyncClient(
                transport=httpx.ASGITransport(app=app), base_url="http://test"
            ) as client:
                backend = ProviderBackend(
                    client, {"authorization": "Bearer TEST-ONLY-PROVIDER"}
                )
                for envelope in events(op):
                    receipt = await backend.send(envelope)
                    assert receipt["ingestion_status"] == "accepted"
                    retry = await backend.send(envelope)
                    assert retry["duplicate"]
                    assert retry["receipt_id"] == receipt["receipt_id"]
                    assert (
                        await env.processor.process(receipt["receipt_id"])
                        == "applied"
                    )
                    current = await backend.receipt(
                        envelope["external_event_id"]
                    )
                    assert current["ingestion_status"] == "applied"
            assert len(sink.seen) == len(await applied_events(env)) == 4
            for normalized, trigger in sink.seen:
                assert (
                    normalized.protocol_schema_hash
                    == config.snapshot_ref.schema_hash
                )
                assert normalized.facts == {"eta_minutes": 0}
                assert trigger.workflow_id == op["workflow_id"]
                assert trigger.cause.operation_id == op["id"]
                assert (
                    trigger.cause.cause_event_id == normalized.inbox_event_id
                )
            stored = await env.repo.read("operations", SCOPE_A, op["id"])
            assert (
                stored["job_status"] == "completed" and not stored["pending"]
            )
            assert stored["creation_status"] == "succeeded"
            assert env.provider.calls == 1

    run(scenario)


@pytest.mark.parametrize("mutation", ["namespace", "actor", "schema", "facts"])
def test_invalid_verified_event_is_quarantined_without_workflow_apply(
    mutation,
):
    async def scenario():
        async with harness(tracking=True) as env:
            (_, principal, _, _, _, _), op = await prepare(env)
            envelope = events(op)[0]
            if mutation == "namespace":
                principal["provider_integration_id"] = "other-integration"
            elif mutation == "actor":
                principal["actor"]["actor_id"] = "other-actor"
            elif mutation == "schema":
                envelope["data"]["eta_minutes"] = -1
            else:
                envelope["data"]["private_injected_field"] = "NOT ALLOWED"
            receipt = await env.ingress.accept(principal, envelope)
            assert (
                await env.processor.process(receipt["receipt_id"])
                == "quarantined"
            )
            assert await applied_events(env) == []

    run(scenario)


@pytest.mark.parametrize(
    "mutation", ["inbox", "time", "hash", "status", "facts"]
)
def test_normalizer_cannot_replace_persisted_identity_or_mapped_facts(
    mutation,
):
    async def scenario():
        async with harness(tracking=True) as env:
            (_, principal, _, _, _, _), op = await prepare(env)
            original = env.protocols.event_port_factory

            def wrong(context):
                port = original(context)
                normalize = port.normalize_verified_event

                async def poisoned(*args):
                    dto = value(await normalize(*args))
                    if mutation == "inbox":
                        dto["inbox_event_id"] = "new-id-on-retry"
                    elif mutation == "time":
                        dto["received_at"] = "2026-10-11T00:00:00Z"
                    elif mutation == "hash":
                        dto["protocol_schema_hash"] = "LATEST-NOT-PINNED"
                    elif mutation == "status":
                        dto["normalized_status"] = "completed"
                    else:
                        dto["facts"] = {"note": "PRIVATE NOTE"}
                    return dto

                port.normalize_verified_event = poisoned
                return port

            env.protocols.event_port_factory = wrong
            receipt = await env.ingress.accept(principal, events(op)[0])
            assert (
                await env.processor.process(receipt["receipt_id"])
                == "quarantined"
            )
            assert await applied_events(env) == []

    run(scenario)


@pytest.mark.parametrize(
    "wrong_response", ["failure", "workflow", "audience", "group"]
)
def test_sink_failure_or_wrong_workflow_response_rolls_back_all_facts(
    wrong_response,
):
    async def scenario():
        async with harness(tracking=True) as env:
            (_, principal, _, _, sink, _), op = await prepare(env)
            receipt = await env.ingress.accept(principal, events(op)[1])
            env.workflow.fail = wrong_response == "failure"
            sink.wrong_workflow = wrong_response == "workflow"
            sink.wrong_audience = wrong_response == "audience"
            sink.wrong_group = wrong_response == "group"
            with pytest.raises((ExecutionError, RuntimeError)):
                await env.processor.process(receipt["receipt_id"])
            current = await env.repo.read("operations", SCOPE_A, op["id"])
            assert current["last_source_hash"] is None
            assert current["job_status"] == "assigned"
            inbox = await env.ingress.read_receipt(
                principal, receipt["receipt_id"]
            )
            assert inbox["ingestion_status"] == "accepted"
            assert await applied_events(env) == []
            env.workflow.fail = sink.wrong_workflow = False
            sink.wrong_audience = sink.wrong_group = False
            assert (
                await env.processor.process(receipt["receipt_id"]) == "applied"
            )
            assert len(await applied_events(env)) == 1

    run(scenario)


def test_early_event_binds_correlation_and_preserves_creation_result():
    async def scenario():
        async with harness(tracking=True) as env:
            _, principal, _, _, _, _ = await wire_protocols(env)
            call = await approved_call(env)

            async def early(arguments, output):
                output["status"] = "assigned"
                op = (
                    await env.operations.get_for_workflow(
                        SCOPE_A, "workflow-A"
                    )
                )[0]
                assert op["external_job_id"] is None
                envelope = ProviderBackend.progress_events(
                    output["external_job_id"], arguments["client_reference"]
                )[-1]
                receipt = await env.ingress.accept(principal, envelope)
                assert (
                    await env.processor.process(receipt["receipt_id"])
                    == "applied"
                )

            env.provider.after_write = early
            result = await env.gateway.execute(SCOPE_A, call)
            assert result["status"] == "succeeded"
            op = (
                await env.operations.get_for_workflow(SCOPE_A, "workflow-A")
            )[0]
            assert op["job_status"] == "completed" and not op["pending"]
            assert op["external_job_id"] == "FAKE-job-1"

    run(scenario)


def test_delta_gap_reprocess_and_terminal_regression():
    async def scenario():
        async with harness(tracking=True) as env:
            _, principal, _, _, _, _ = await wire_protocols(env, mode="delta")
            call = await approved_call(env)
            await env.gateway.execute(SCOPE_A, call)
            op = (
                await env.operations.get_for_workflow(SCOPE_A, "workflow-A")
            )[0]
            receipts = [
                await env.ingress.accept(principal, e) for e in events(op)
            ]
            assert (
                await env.processor.process(receipts[1]["receipt_id"])
                == "quarantined"
            )
            assert (
                await env.processor.process(receipts[0]["receipt_id"])
                == "applied"
            )
            for receipt in receipts[1:]:
                assert (
                    await env.processor.process(receipt["receipt_id"])
                    == "applied"
                )
            late = {
                **events(op)[0],
                "external_event_id": "late",
                "provider_version": 5,
            }
            receipt = await env.ingress.accept(principal, late)
            assert (
                await env.processor.process(receipt["receipt_id"])
                == "quarantined"
            )
            assert (await env.repo.read("operations", SCOPE_A, op["id"]))[
                "job_status"
            ] == "completed"

    run(scenario)


@pytest.mark.parametrize("conflict", [False, True])
def test_query_uses_pinned_mapping_and_refuses_another_external_job(conflict):
    async def scenario():
        async with harness(tracking=True) as env:
            (_, _, _, _, sink, bridge), op = await prepare(env)

            class Queries:
                async def query(self, scope, operation, timer_id):
                    return {
                        "external_job_id": "OTHER-job"
                        if conflict
                        else op["external_job_id"],
                        "status": "completed",
                        "provider_version": 4,
                    }

            reconciler = OperationReconciler(
                env.repo, Queries(), env.protocols, bridge, env.jobs
            )
            if conflict:
                with pytest.raises(
                    ExecutionError, match="CORRELATION_CONFLICT"
                ):
                    await reconciler.reconcile(SCOPE_A, op["id"], "timer-1")
                assert await applied_events(env) == []
            else:
                assert (
                    await reconciler.reconcile(SCOPE_A, op["id"], "timer-1")
                    == "applied"
                )
                query_result, trigger = sink.query_seen[-1]
                assert trigger.cause.kind == "timer"
                assert query_result["timer_id"] == "timer-1"
                assert "inbox_event_id" not in query_result
                assert query_result["facts"] == {}
                assert (
                    await reconciler.reconcile(SCOPE_A, op["id"], "timer-1")
                    == "terminal"
                )

    run(scenario)


def test_workflow_bridge_rejects_mixed_binding_before_sink():
    async def scenario():
        async with harness(tracking=True) as env:
            (_, principal, _, _, sink, bridge), op = await prepare(env)
            receipt = await env.ingress.accept(principal, events(op)[0])
            async with env.repo.transaction() as uow:
                row = await env.repo.get("inbox", receipt["receipt_id"], uow)
                event = await env.protocols.normalize_verified_event(
                    row["provider_ref"],
                    op["protocol"],
                    row["envelope"],
                    inbox_event_id=row["id"],
                    received_at=row["received_at"],
                )
                with pytest.raises(ExecutionError, match="BINDING_MISMATCH"):
                    await bridge.apply_external_event(
                        SCOPE_A,
                        {**op, "workflow_id": "workflow-B"},
                        event,
                        uow,
                    )
            assert sink.seen == [] and await applied_events(env) == []

    run(scenario)


@pytest.mark.parametrize("fail", [False, True])
def test_foundation_provider_enqueue_joins_execution_transaction(fail):
    async def scenario():
        async with harness(tracking=True) as env:
            (_, principal, _, _, _, _), op = await prepare(env)
            env.ingress.jobs = DurableJobService(
                JobEnqueueRepository(fail), clock=env.clock
            )
            if fail:
                with pytest.raises(RuntimeError, match="enqueue failure"):
                    await env.ingress.accept(principal, events(op)[0])
            else:
                receipt = await env.ingress.accept(principal, events(op)[0])
                retry = await env.ingress.accept(principal, events(op)[0])
                assert receipt["receipt_id"] == retry["receipt_id"]
            async with env.repo.transaction() as uow:
                inbox = await env.repo.find("inbox", {}, uow)
                rows = (
                    (await uow.execute(select(test_events))).mappings().all()
                )
                jobs = [
                    r["payload"]
                    for r in rows
                    if r["id"].startswith("shared-job-")
                ]
                if fail:
                    assert jobs == inbox == []
                else:
                    assert len(jobs) == len(inbox) == 1
                    assert jobs[0]["owner_kind"] == "provider"
                    assert jobs[0]["scope"] is None
                    assert (
                        jobs[0]["provider_integration_id"]
                        == principal["provider_integration_id"]
                    )
                    assert jobs[0]["payload"] == {"receipt_id": inbox[0]["id"]}

    run(scenario)


def test_interleaved_workflows_keep_closed_facts_isolated():
    async def scenario():
        async with harness(tracking=True) as env:
            (_, principal, _, _, sink, _), op_a = await prepare(env)
            env.runtime.add_run(
                "run-B",
                audience={
                    **AUDIENCE,
                    "external_ticket_id": "TICKET-B",
                    "external_conversation_id": "CHAT-B",
                },
            )
            call = await approved_call(env, call_fixture("call-B", "run-B"))
            await env.gateway.execute(SCOPE_A, call)
            op_b = (
                await env.operations.get_for_workflow(SCOPE_A, "workflow-B")
            )[0]
            a = ProviderBackend.progress_events(
                op_a["external_job_id"], op_a["correlation_id"], "A"
            )
            b = ProviderBackend.progress_events(
                op_b["external_job_id"], op_b["correlation_id"], "B"
            )
            for index, pair in enumerate(zip(a, b)):
                if index == 3:
                    env.workflow.closed.add("workflow-A")
                for envelope in pair:
                    receipt = await env.ingress.accept(principal, envelope)
                    assert (
                        await env.processor.process(receipt["receipt_id"])
                        == "applied"
                    )
            for op in (op_a, op_b):
                current = await env.repo.read("operations", SCOPE_A, op["id"])
                assert current["job_status"] == "completed"
                assert current["external_job_id"] == op["external_job_id"]
            counts = {}
            for row in await applied_events(env):
                key = row["payload"]["workflow_id"]
                counts[key] = counts.get(key, 0) + 1
            assert counts == {"workflow-A": 3, "workflow-B": 4}
            assert len(sink.seen) == 8
            mixed = {
                **a[0],
                "external_event_id": "MIXED",
                "client_reference": op_b["correlation_id"],
            }
            receipt = await env.ingress.accept(principal, mixed)
            assert (
                await env.processor.process(receipt["receipt_id"])
                == "quarantined"
            )
            assert len(sink.seen) == 8

    run(scenario)


def test_external_operation_port_returns_shared_dto_and_honors_caller_uow():
    async def scenario():
        async with harness(tracking=True) as env:
            (config, _, _, _, _, _), op = await prepare(env)
            port = ExternalOperationAdapter(env.operations, env.protocols)
            assert isinstance(port, ExternalOperationPort)
            projected = (await port.get_for_workflow(SCOPE_A, "workflow-A"))[0]
            assert isinstance(projected, ExternalOperation)
            assert projected.protocol_snapshot == config.snapshot_ref
            assert projected.correlation_id == op["correlation_id"]
            assert await port.get_for_workflow(SCOPE_B, "workflow-A") == ()
            context = env.runtime.contexts["run-A"]
            new_call = call_fixture("call-PORT", "run-A")
            with pytest.raises(RuntimeError, match="TEST rollback"):
                async with env.repo.transaction() as uow:
                    created = await port.prepare(
                        SCOPE_A, context, new_call, config.snapshot_ref, uow
                    )
                    assert created.creation_status == "prepared"
                    await port.bind_result(
                        SCOPE_A,
                        created.operation_id,
                        {
                            "creation_status": "succeeded",
                            "external_job_id": "PORT-job",
                            "job_status": "assigned",
                            "pending": True,
                        },
                        uow,
                    )
                    raise RuntimeError("TEST rollback")
            assert len(await port.get_for_workflow(SCOPE_A, "workflow-A")) == 1
            created = await port.prepare(
                SCOPE_A, context, new_call, config.snapshot_ref
            )
            assert created.creation_status == "prepared"
            with pytest.raises(
                ExecutionError, match="PARTNER_AUDIENCE_INVALID"
            ):
                await port.prepare(
                    SCOPE_A,
                    {**context, "partner_audience": None},
                    call_fixture("call-NO-AUDIENCE"),
                    config.snapshot_ref,
                )

    run(scenario)


def test_unchanged_query_advances_version_without_emitting_duplicate_status():
    async def scenario():
        async with harness(tracking=True) as env:
            _, principal, _, _, sink, bridge = await wire_protocols(
                env, "delta"
            )
            call = await approved_call(env)
            await env.gateway.execute(SCOPE_A, call)
            op = (
                await env.operations.get_for_workflow(SCOPE_A, "workflow-A")
            )[0]
            first = {**events(op)[0], "data": {}}
            receipt = await env.ingress.accept(principal, first)
            assert (
                await env.processor.process(receipt["receipt_id"]) == "applied"
            )

            class Queries:
                async def query(self, scope, operation, timer_id):
                    return {
                        "external_job_id": op["external_job_id"],
                        "status": "assigned",
                        "provider_version": 2,
                    }

            reconciler = OperationReconciler(
                env.repo, Queries(), env.protocols, bridge, env.jobs
            )
            assert (
                await reconciler.reconcile(SCOPE_A, op["id"], "timer-2")
                == "unchanged"
            )
            current = await env.repo.read("operations", SCOPE_A, op["id"])
            assert current["last_provider_version"] == 2
            assert len(sink.seen) == 1 and sink.query_seen == []
            following = {**events(op)[1], "provider_version": 3}
            receipt = await env.ingress.accept(principal, following)
            assert (
                await env.processor.process(receipt["receipt_id"]) == "applied"
            )

    run(scenario)
