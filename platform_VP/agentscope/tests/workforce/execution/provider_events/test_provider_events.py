"""Provider durability, correlation, ordering and namespace behavior."""

import asyncio

import pytest
from sqlalchemy import select

from agentscope.app.workforce.execution import ExecutionError
from execution_fakes import (
    PROVIDER,
    SCOPE_A,
    approved_call,
    event_fixture,
    harness,
    test_events,
)


def run(test):
    return asyncio.run(test())


async def operation(env):
    call = await approved_call(env)
    await env.gateway.execute(SCOPE_A, call)
    return (await env.operations.get_for_workflow(SCOPE_A, "workflow-A"))[0]


def test_duplicate_receipt_and_id_conflict():
    async def scenario():
        async with harness(tracking=True) as env:
            op = await operation(env)
            event = event_fixture(
                job_id=op["external_job_id"], correlation=op["correlation_id"]
            )
            receipt = await env.ingress.accept(PROVIDER, event)
            duplicate = await env.ingress.accept(PROVIDER, event)
            assert (
                receipt["receipt_id"] == duplicate["receipt_id"]
                and duplicate["duplicate"]
            )
            with pytest.raises(ExecutionError, match="EVENT_ID_CONFLICT"):
                await env.ingress.accept(
                    PROVIDER, {**event, "provider_version": 2}
                )
            assert (
                await env.processor.process(receipt["receipt_id"]) == "applied"
            )
            assert (
                await env.processor.process(receipt["receipt_id"]) == "applied"
            )
            async with env.repo.transaction() as uow:
                events = (
                    (await uow.execute(select(test_events))).mappings().all()
                )
                assert sum(r["id"].startswith("apply-") for r in events) == 1

    run(scenario)


def test_ack_rolls_back_if_job_cannot_commit():
    async def scenario():
        async with harness(tracking=True) as env:
            env.jobs.fail = True
            with pytest.raises(RuntimeError, match="TEST commit failure"):
                await env.ingress.accept(
                    PROVIDER, event_fixture(correlation="not-bound")
                )
            async with env.repo.transaction() as uow:
                assert await env.repo.find("inbox", {}, uow) == []
            env.jobs.fail = False
            receipt = await env.ingress.accept(
                PROVIDER, event_fixture(correlation="not-bound")
            )
            assert (
                await env.processor.process(receipt["receipt_id"])
                == "quarantined"
            )

    run(scenario)


def test_crash_after_apply_rolls_back_fact_inbox_and_workflow():
    async def scenario():
        async with harness(tracking=True) as env:
            op = await operation(env)
            receipt = await env.ingress.accept(
                PROVIDER,
                event_fixture(
                    job_id=op["external_job_id"],
                    version=2,
                    status="on_the_way",
                ),
            )
            env.workflow.fail = True
            with pytest.raises(RuntimeError):
                await env.processor.process(receipt["receipt_id"])
            unchanged = await env.repo.read("operations", SCOPE_A, op["id"])
            assert unchanged["job_status"] == "assigned"
            assert (
                await env.ingress.read_receipt(PROVIDER, receipt["receipt_id"])
            )["ingestion_status"] == "accepted"
            env.workflow.fail = False
            assert (
                await env.processor.process(receipt["receipt_id"]) == "applied"
            )

    run(scenario)


def test_early_event_resolves_precommitted_intent_after_unknown():
    async def scenario():
        async with harness(tracking=True) as env:

            async def early(arguments, result):
                receipt = await env.ingress.accept(
                    PROVIDER,
                    event_fixture(
                        job_id=result["external_job_id"],
                        correlation=arguments["client_reference"],
                        version=2,
                        status="completed",
                    ),
                )
                assert (
                    await env.processor.process(receipt["receipt_id"])
                    == "applied"
                )

            env.provider.after_write = early
            env.provider.fault = "timeout_after_write"
            call = await approved_call(env)
            result = await env.gateway.execute(SCOPE_A, call)
            assert result["status"] == "unknown"
            op = (
                await env.operations.get_for_workflow(SCOPE_A, "workflow-A")
            )[0]
            assert (
                op["creation_status"] == "succeeded"
                and op["job_status"] == "completed"
            )
            assert not op["pending"] and env.provider.calls == 1

    run(scenario)


def test_ordering_snapshots_terminal_late_and_version_conflict():
    async def scenario():
        async with harness(tracking=True) as env:
            op = await operation(env)
            for event_id, version, status, expected in [
                ("v4", 4, "completed", "applied"),
                ("v3", 3, "on_the_way", "ignored"),
                ("v4-conflict", 4, "assigned", "quarantined"),
                ("v5-late", 5, "on_the_way", "ignored"),
            ]:
                receipt = await env.ingress.accept(
                    PROVIDER,
                    event_fixture(
                        event_id,
                        job_id=op["external_job_id"],
                        version=version,
                        status=status,
                    ),
                )
                assert (
                    await env.processor.process(receipt["receipt_id"])
                    == expected
                )
            current = await env.repo.read("operations", SCOPE_A, op["id"])
            assert (
                current["job_status"] == "completed"
                and current["last_provider_version"] == 4
            )

    run(scenario)


def test_delta_gap_is_durable_quarantine_then_reprocessed():
    async def scenario():
        async with harness(tracking=True) as env:
            env.protocol["order_mode"] = "delta"
            from agentscope.app.workforce.execution._utils import digest

            env.descriptor["async_protocol_hash"] = digest(env.protocol)
            op = await operation(env)
            gap = await env.ingress.accept(
                PROVIDER,
                event_fixture(
                    "two",
                    job_id=op["external_job_id"],
                    version=2,
                    status="on_the_way",
                ),
            )
            assert (
                await env.processor.process(gap["receipt_id"]) == "quarantined"
            )
            first = await env.ingress.accept(
                PROVIDER,
                event_fixture("one", job_id=op["external_job_id"], version=1),
            )
            assert (
                await env.processor.process(first["receipt_id"]) == "applied"
            )
            assert await env.processor.process(gap["receipt_id"]) == "applied"

    run(scenario)


def test_wrong_integration_conflicting_refs_and_receipt_isolation():
    async def scenario():
        async with harness(tracking=True) as env:
            op = await operation(env)
            event = event_fixture(
                job_id=op["external_job_id"], correlation="wrong-correlation"
            )
            receipt = await env.ingress.accept(PROVIDER, event)
            assert (
                await env.processor.process(receipt["receipt_id"])
                == "quarantined"
            )
            other = {**PROVIDER, "provider_integration_id": "provider-2"}
            with pytest.raises(ExecutionError, match="RESOURCE_NOT_FOUND"):
                await env.ingress.read_receipt(other, receipt["receipt_id"])
            receipt2 = await env.ingress.accept(
                other, event_fixture(job_id=op["external_job_id"])
            )
            assert (
                await env.processor.process(receipt2["receipt_id"])
                == "quarantined"
            )

    run(scenario)


@pytest.mark.parametrize("suppression", ["closed", "revoked"])
def test_event_after_close_or_revoke_keeps_fact_without_send(suppression):
    async def scenario():
        async with harness(tracking=True) as env:
            op = await operation(env)
            getattr(env.workflow, suppression).add("workflow-A")
            receipt = await env.ingress.accept(
                PROVIDER,
                event_fixture(
                    job_id=op["external_job_id"], version=2, status="completed"
                ),
            )
            assert (
                await env.processor.process(receipt["receipt_id"]) == "applied"
            )
            current = await env.repo.read("operations", SCOPE_A, op["id"])
            assert current["job_status"] == "completed"
            async with env.repo.transaction() as uow:
                events = (
                    (await uow.execute(select(test_events))).mappings().all()
                )
                assert not any(r["id"].startswith("apply-") for r in events)

    run(scenario)
