"""D3 SQL/HTTP acceptance: duplicates, ordering, crash and unknown recovery."""

import asyncio
import json
import unittest
from unittest.mock import patch

from httpx import ASGITransport, AsyncClient
from sqlalchemy import select

from agentscope.app.workforce.foundation import (
    DurableWorkerSupervisor,
    InMemoryMetricSink,
    WORKER_RESTARTS,
)
from agentscope.app.workforce.foundation.event_delivery import (
    JobLeaseLostError,
)
from agentscope.app.workforce.execution.provider_events._tables import (
    provider_event_inbox,
)
from tests.workforce.fixtures.phase_c_e2e import SCOPE, sse_frames
from tests.workforce.fixtures.phase_d_execution import D3CaseDriver
from tests.workforce.fixtures.sql_ticket_slice import SqlTicketSliceSupport
from tests.workforce.fixtures.async_partners.sse_client import parse_sse


class D3RecoveryTests(SqlTicketSliceSupport, unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.driver = D3CaseDriver()
        await self.driver.setup()

    async def asyncTearDown(self):
        await self.driver.cleanup()

    async def state(self, backend, workflow_id, operation):
        driver = self.driver
        return (
            await driver.env.execution_repository.read(
                "operations", SCOPE, operation["id"]
            ),
            await driver.env.workflows_repo.load(SCOPE, workflow_id),
            (await self.history(backend, "raw")).json(),
            await driver.repo.evidence(SCOPE, workflow_id),
        )

    async def _crash_and_recover(self, boundary):
        driver = self.driver
        backend, workflow_id, operation = await self.create_operation()
        before = await self.state(backend, workflow_id, operation)
        calls = driver.model.calls
        event = self.event(operation, "crash-completed", 4, "completed")
        response = await driver.send(event)
        self.assertEqual(202, response.status_code)
        receipt_id = response.json()["receipt_id"]
        jobs_before = len(await self.jobs())
        claims = []
        claim = driver.worker_jobs.claim
        process = driver.processor.process
        write = driver.env.events.write

        async def capture_claim(*args, **kwargs):
            result = await claim(*args, **kwargs)
            claims.append(result)
            return result

        async def interrupted(*args, **kwargs):
            if boundary == "after_commit":
                await process(*args, **kwargs)
            raise asyncio.CancelledError("TEST worker terminated")

        async def interrupted_write(*args, **kwargs):
            await write(*args, **kwargs)
            raise asyncio.CancelledError("TEST terminated before commit")

        target, method, fault = (
            (driver.env.events, "write", interrupted_write)
            if boundary == "before_commit"
            else (driver.processor, "process", interrupted)
        )
        with (
            patch.object(driver.worker_jobs, "claim", capture_claim),
            patch.object(target, method, fault),
        ):
            with self.assertRaises(asyncio.CancelledError):
                await driver.worker.run_once()
        old_claim = claims[0]
        leased = next(
            row
            for row in await self.jobs()
            if row["id"] == old_claim.job.job_id
        )
        self.assertEqual("leased", leased["status"])
        self.assertEqual(1, leased["attempt"])
        committed = await self.state(backend, workflow_id, operation)
        if boundary == "after_commit":
            self.assertEqual(
                operation["revision"] + 1, committed[0]["revision"]
            )
            self.assertEqual(jobs_before + 1, len(await self.jobs()))
            self.assertEqual(
                "applied",
                (await driver.receipt(receipt_id))["ingestion_status"],
            )
        else:
            self.assertEqual(before, committed)
            self.assertEqual(jobs_before, len(await self.jobs()))
            self.assertEqual(
                "accepted",
                (await driver.receipt(receipt_id))["ingestion_status"],
            )
        self.assertEqual(calls, driver.model.calls)

        # Reconnect to the committed file and reclaim the expired DB lease.
        await driver.env.engine.dispose()
        jobs = driver.new_worker(seconds=31)
        driver.cause = "completed"
        # Ordering between ready continuation and reclaimed provider job is
        # repository-owned. Both must finish, irrespective of which is first.
        outcomes = [await driver.worker.run_once() for _ in range(2)]
        self.assertTrue(all(row.status == "succeeded" for row in outcomes))
        final_job = next(
            row
            for row in await self.jobs()
            if row["id"] == old_claim.job.job_id
        )
        self.assertEqual("succeeded", final_job["status"])
        self.assertEqual(2, final_job["attempt"])
        self.assertGreater(final_job["fencing_token"], old_claim.fencing_token)
        with self.assertRaises(JobLeaseLostError):
            await jobs.complete_claim(old_claim, {"late": True})
        final = await self.state(backend, workflow_id, operation)
        self.assertEqual(operation["revision"] + 1, final[0]["revision"])
        self.assertEqual("completed", final[0]["job_status"])
        self.assertFalse(final[0]["pending"])
        self.assertEqual(calls + 1, driver.model.calls)
        self.assertEqual(len(before[3]) + 1, len(final[3]))
        self.assertEqual(1, driver.provider.calls)
        self.assertEqual(jobs_before + 1, len(await self.jobs()))

        duplicate = await driver.send(event)
        self.assertEqual(receipt_id, duplicate.json()["receipt_id"])
        self.assertTrue(duplicate.json()["duplicate"])
        self.assertEqual("idle", (await driver.worker.run_once()).status)
        self.assertEqual(
            final, await self.state(backend, workflow_id, operation)
        )
        # SSE replay after recovery is exactly the committed public log.
        history = final[2]["items"]
        path = (
            "/workforce/v1/partner/conversations/"
            + backend.tickets["raw"]["conversation_id"]
            + "/events"
        )
        messages = await sse_frames(driver.app, path, "raw", len(history))
        self.assertEqual(200, messages[0]["status"])
        wire = b"".join(row.get("body", b"") for row in messages).decode()

        async def lines():
            for line in wire.splitlines():
                yield line

        frames = [frame async for frame in parse_sse(lines())]
        self.assertEqual(
            [row["event_id"] for row in history],
            [frame["event_id"] for frame in frames],
        )

    async def test_crash_after_ack_before_apply_reclaims_lease(self):
        await self._crash_and_recover("before_apply")

    async def test_crash_during_apply_rolls_back_all_modules(self):
        await self._crash_and_recover("before_commit")

    async def test_crash_after_commit_replays_without_second_turn(self):
        await self._crash_and_recover("after_commit")

    async def test_out_of_order_snapshot_conflict_and_terminal_barrier(self):
        driver = self.driver
        backend, workflow_id, operation = await self.create_operation()
        first = await driver.send(
            self.event(operation, "completed-v4", 4, "completed")
        )
        self.assertEqual(202, first.status_code)
        await self.run_job("completed")
        await self.run_job("completed")
        completed = await self.state(backend, workflow_id, operation)
        calls = driver.model.calls
        for event_id, version, status, outcome in (
            ("old-v3", 3, "arrived", "rejected"),
            ("conflict-v4", 4, "assigned", "quarantined"),
            ("late-v5", 5, "on_the_way", "quarantined"),
        ):
            with self.subTest(event=event_id):
                response = await driver.send(
                    self.event(operation, event_id, version, status)
                )
                self.assertEqual(202, response.status_code)
                await self.run_job("completed")
                self.assertEqual(
                    outcome,
                    (await driver.receipt(response.json()["receipt_id"]))[
                        "ingestion_status"
                    ],
                )
                self.assertEqual(
                    completed,
                    await self.state(backend, workflow_id, operation),
                )
                self.assertEqual(
                    "idle", (await driver.worker.run_once()).status
                )
        self.assertEqual(calls, driver.model.calls)
        self.assertEqual(1, driver.provider.calls)

    async def test_inbox_job_commit_failure_returns_500_then_retry_recovers(
        self,
    ):
        driver = self.driver
        backend, workflow_id, operation = await self.create_operation()
        before = await self.state(backend, workflow_id, operation)
        job_count = len(await self.jobs())
        event = self.event(operation, "retry-after-500")
        raw = json.dumps(event).encode()

        async def fail_enqueue(*args, **kwargs):
            raise ConnectionError("TEST job insert failure")

        async with AsyncClient(
            transport=ASGITransport(
                app=driver.app, raise_app_exceptions=False
            ),
            base_url="http://test",
        ) as client:
            with patch.object(
                driver.env.jobs, "enqueue_provider", fail_enqueue
            ):
                response = await client.post(
                    "/workforce/v1/provider/job-events",
                    content=raw,
                    headers=driver.signed(raw),
                )
        self.assertEqual(500, response.status_code)
        self.assertEqual(
            before, await self.state(backend, workflow_id, operation)
        )
        self.assertEqual(job_count, len(await self.jobs()))
        async with driver.env.uows() as tx:
            self.assertEqual(
                [], (await tx.execute(select(provider_event_inbox))).all()
            )
        retry = await driver.send(event)
        self.assertEqual(202, retry.status_code)
        self.assertFalse(retry.json()["duplicate"])
        await self.run_job("assigned")
        await self.run_job("assigned")
        self.assertEqual(
            "applied",
            (await driver.receipt(retry.json()["receipt_id"]))[
                "ingestion_status"
            ],
        )
        self.assertEqual(1, driver.provider.calls)

    async def test_unknown_timeout_recovers_by_event_without_recreate(self):
        driver = self.driver
        backend, workflow_id, operation = await self.create_operation(
            fault="timeout_after_write"
        )
        self.assertEqual("unknown", operation["creation_status"])
        self.assertIsNone(operation["external_job_id"])
        self.assertEqual(
            "unknown",
            (await driver.gateway.execute(SCOPE, driver.call))["status"],
        )
        actual = driver.provider.bookings[operation["correlation_id"]]
        event = self.event(operation, "recover-unknown", 4, "completed")
        event["external_job_id"] = actual["external_job_id"]
        response = await driver.send(event)
        self.assertEqual(202, response.status_code)
        await self.run_job("completed")
        await self.run_job("completed")
        current = (await self.state(backend, workflow_id, operation))[0]
        self.assertEqual("succeeded", current["creation_status"])
        self.assertEqual(actual["external_job_id"], current["external_job_id"])
        self.assertFalse(current["pending"])
        await driver.gateway.execute(SCOPE, driver.call)
        self.assertEqual(1, driver.provider.calls)

    async def test_unknown_recovers_by_durable_query_without_fake_inbox(self):
        driver = self.driver
        _, workflow_id, operation = await self.create_operation(
            fault="timeout_after_write"
        )
        driver.provider.bookings[operation["correlation_id"]]["status"] = (
            "completed"
        )
        async with driver.env.uows() as tx:
            job_id = await driver.reconciler.schedule(
                SCOPE, operation["id"], "d3-query", driver.env.clock(), tx
            )
            await tx.commit()
        await self.run_job("completed")
        await self.run_job("completed")
        query_job = next(
            row for row in await self.jobs() if row["id"] == job_id
        )
        self.assertEqual("applied", query_job["result"]["status"])
        current = await driver.env.execution_repository.read(
            "operations", SCOPE, operation["id"]
        )
        self.assertEqual("succeeded", current["creation_status"])
        self.assertEqual("completed", current["job_status"])
        self.assertFalse(current["pending"])
        before = await driver.env.workflows_repo.load(SCOPE, workflow_id)
        self.assertIn("d3-query", before.applied_query_results)
        async with driver.env.uows() as tx:
            self.assertEqual(
                [], (await tx.execute(select(provider_event_inbox))).all()
            )
        self.assertEqual(
            "terminal",
            await driver.reconciler.reconcile(
                SCOPE, operation["id"], "d3-query"
            ),
        )
        await driver.gateway.execute(SCOPE, driver.call)
        self.assertEqual(1, driver.provider.calls)

    async def test_supervisor_recovers_sql_claim_failure(self):
        driver = self.driver
        _, _, operation = await self.create_operation()
        response = await driver.send(self.event(operation, "supervised"))
        receipt_id = response.json()["receipt_id"]
        driver.cause = "assigned"
        metrics = InMemoryMetricSink()
        claim = driver.worker_jobs.claim
        calls = 0
        done = asyncio.Event()
        run = driver.worker.run_once

        async def fail_once(*args, **kwargs):
            nonlocal calls
            calls += 1
            if calls == 1:
                raise ConnectionError("TEST lost database connection")
            return await claim(*args, **kwargs)

        async def observe():
            outcome = await run()
            if outcome.status == "idle":
                done.set()
            return outcome

        with (
            patch.object(driver.worker_jobs, "claim", fail_once),
            patch.object(driver.worker, "run_once", observe),
        ):
            async with DurableWorkerSupervisor(
                driver.worker,
                idle_seconds=0.01,
                restart_seconds=0.01,
                metrics=metrics,
            ):
                await asyncio.wait_for(done.wait(), timeout=10)
        self.assertEqual(
            1, metrics.value(WORKER_RESTARTS, error_type="ConnectionError")
        )
        self.assertEqual(
            "applied", (await driver.receipt(receipt_id))["ingestion_status"]
        )
        self.assertEqual(1, driver.provider.calls)
