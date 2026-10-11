"""C6 gates using SQL runtime and signed raw provider HTTP (no env factory)."""

import json
import unittest
from unittest.mock import patch

import pytest
from sqlalchemy import select, update

from agentscope.app.workforce.contracts import EvaluationStatus
from agentscope.app.workforce.lifecycle.async_evaluation import (
    AsyncEvaluationService,
    RuntimeEvaluationRunner,
    canonical_hash,
    check_persisted_release,
    lifecycle_suite,
)
from agentscope.app.workforce.lifecycle.async_evaluation._tables import (
    case_runs,
)
from agentscope.app.workforce.foundation._tables import (
    durable_jobs,
    partner_manager_routes,
    provider_credentials,
)
from tests.workforce.fixtures.async_partners.customer_backend import (
    CustomerBackend,
)
from tests.workforce.fixtures.async_partners.sse_client import parse_sse
from tests.workforce.fixtures.phase_c_e2e import (
    RawProviderCaseDriver,
    SCOPE,
    sse_frames,
)


class C6SliceTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.driver = RawProviderCaseDriver()
        await self.driver.setup()

    async def asyncTearDown(self):
        await self.driver.cleanup()

    async def run_job(self, cause):
        self.driver.cause = cause
        outcome = await self.driver.worker.run_once()
        if outcome.status != "succeeded" and hasattr(
            self.driver, "last_turn_error"
        ):
            raise self.driver.last_turn_error
        self.assertEqual(outcome.status, "succeeded")

    async def open_ticket(
        self, name="raw", pattern="external_tracking", user=None
    ):
        driver = self.driver

        async def bind(workflow_id, uow):
            await driver.repo.put(
                case_runs,
                SCOPE,
                {
                    "snapshot_id": driver.snapshot.snapshot_id,
                    "case_id": name,
                },
                {
                    "workflow_id": workflow_id,
                    "input_hash": canonical_hash(name),
                },
                uow,
            )

        workflow_id = await driver.open_case(
            SCOPE,
            driver.snapshot,
            {
                "case_id": name,
                "pattern": pattern,
                "external_user_id": user or name,
                "external_ticket_id": name,
            },
            bind,
        )
        backend = CustomerBackend(
            driver.client,
            {"x-test-user": user or name},
            user or name,
            "tower-a",
        )
        receipt = driver.opened[name][1]
        backend._remember(
            name, "chat-" + name, receipt.model_dump(mode="json")
        )
        # Consent belongs to the original customer; the catalog is a test port.
        driver.runtime_authority.contexts[workflow_id]["allowed_decider"] = {
            "kind": "partner",
            "actor_id": driver.actor.actor_id,
            "partner_client_id": driver.actor.partner_client_id,
            "external_user_id": driver.actor.external_user_id,
        }
        await self.run_job("request" if pattern == "response_only" else "plan")
        await backend.read_request(name)
        return backend, workflow_id

    async def create_operation(self, name="raw"):
        backend, workflow_id = await self.open_ticket(name)
        await backend.reply(
            name, "Select TEST-room", request_id=name + "-select"
        )
        await self.run_job("selection")
        approval = await self.driver.env.execution_repository.read(
            "approvals", SCOPE, self.driver.call["approval_id"]
        )
        approval = {**approval, "approval_id": approval["id"]}
        first = await backend.approve(
            name, approval, request_id=name + "-approve"
        )
        duplicate = await backend.approve(
            name, approval, request_id=name + "-approve"
        )
        self.assertEqual(first.status_code, 202)
        self.assertEqual(first.json(), duplicate.json())
        await self.run_job("approval")
        replay = await backend.approve(
            name, approval, request_id=name + "-approve"
        )
        self.assertEqual(first.json(), replay.json())
        await backend.read_request(name)
        self.assertEqual(
            backend.tickets[name]["workflow_state"], "waiting_external_event"
        )
        operation = (
            await self.driver.operations.get_for_workflow(SCOPE, workflow_id)
        )[0]
        return backend, workflow_id, operation

    def event(self, operation, event_id="raw-1", version=1, status="assigned"):
        return {
            "schema_version": "1",
            "external_event_id": event_id,
            "external_job_id": operation["external_job_id"],
            "client_reference": operation["correlation_id"],
            "event_type": status,
            "provider_version": version,
            "occurred_at": self.driver.env.clock().isoformat(),
            "data": {
                "confirmed": status == "completed",
                "private_note": "TEST PRIVATE PROVIDER NOTE",
            },
        }

    async def history(self, backend, name):
        return await backend.client.get(
            "/workforce/v1/partner/conversations/"
            + backend.tickets[name]["conversation_id"]
            + "/event-history",
            headers=backend.headers,
            params={
                "external_user_id": backend.external_user_id,
                "limit": 100,
            },
        )

    async def jobs(self):
        async with self.driver.env.uows() as tx:
            return (await tx.execute(select(durable_jobs))).mappings().all()

    async def test_c5_grading_with_raw_provider_and_query_jobs(self):
        driver = self.driver
        runner = RuntimeEvaluationRunner(driver.repo, driver)
        payload = driver.frozen.read(SCOPE)
        suite = lifecycle_suite()
        for case in suite.cases:
            await runner.run_case(
                SCOPE,
                driver.snapshot,
                {
                    **suite.runner_input(case),
                    "runtime_profile": payload["runtime_profile"],
                    "test_context": payload["test_context"],
                    "protocol_refs": payload["dependencies"]["protocol_refs"],
                },
                "mock",
            )
        service = AsyncEvaluationService(runner, driver.env.clock)
        record = await service.run(SCOPE, driver.frozen, "eval-C6")
        self.assertEqual(
            record.report.hard_gate_failures, (), record.model_dump_json()
        )
        self.assertEqual(record.report.status, EvaluationStatus.PASSED)
        self.assertEqual(driver.provider.calls, 4)
        self.assertEqual(len(driver.queries.calls), 1)
        evidence = []
        for _, receipt in driver.opened.values():
            evidence += await driver.repo.evidence(SCOPE, receipt.workflow_id)
        self.assertEqual(
            sum(e.model_turns for e in evidence), driver.model.calls
        )
        self.assertEqual(sum(e.tool_calls for e in evidence), 4)
        self.assertTrue(any(e.provider_cause for e in evidence))
        self.assertTrue(any(e.cause_kind == "timer" for e in evidence))
        for actor, receipt in driver.opened.values():
            aggregate = await driver.env.workflows_repo.load(
                SCOPE, receipt.workflow_id
            )
            if aggregate.pattern != "external_tracking":
                self.assertEqual(
                    await driver.operations.get_for_workflow(
                        SCOPE, receipt.workflow_id
                    ),
                    [],
                )
        async with driver.env.execution_repository.transaction() as tx:
            inbox = await driver.env.execution_repository.find("inbox", {}, tx)
        timer_ids = {timer for _, _, timer in driver.queries.calls}
        self.assertTrue(inbox)
        self.assertTrue(
            all(row["external_event_id"] not in timer_ids for row in inbox)
        )
        self.assertNotIn(
            "TEST PRIVATE PROVIDER NOTE", record.model_dump_json()
        )
        await driver.repo.register(SCOPE, "eval-C6", driver.frozen)
        await driver.repo.save_record(record)
        self.assertEqual(
            await check_persisted_release(
                driver.repo, SCOPE, "eval-C6", driver.frozen
            ),
            record,
        )
        # Completed SQL replay invokes neither a model nor a provider.
        calls = (driver.model.calls, driver.provider.calls)
        replay = await service.run(SCOPE, driver.frozen, "eval-C6-replay")
        self.assertEqual(
            replay.report.model_dump(exclude={"evaluation_id"}),
            record.report.model_dump(exclude={"evaluation_id"}),
        )
        self.assertEqual((driver.model.calls, driver.provider.calls), calls)

    async def test_http_consent_provider_history_sse_reconnect_and_close(self):
        driver = self.driver
        backend, workflow_id, operation = await self.create_operation()
        self.assertEqual(driver.provider.calls, 1)
        for version, status in enumerate(
            ("assigned", "on_the_way", "arrived", "completed"), 1
        ):
            response = await driver.send(
                self.event(operation, f"raw-{version}", version, status)
            )
            self.assertEqual(response.status_code, 202)
            receipt_id = response.json()["receipt_id"]
            self.assertEqual(
                (await driver.receipt(receipt_id))["ingestion_status"],
                "accepted",
            )
            driver.restart_worker()
            await self.run_job(status)
            self.assertEqual(
                (await driver.receipt(receipt_id))["ingestion_status"],
                "applied",
            )
            await self.run_job(status)
        await backend.read_request("raw")
        self.assertEqual(
            backend.tickets["raw"]["next_action"], "confirm_close"
        )
        history = await self.history(backend, "raw")
        self.assertEqual(history.status_code, 200)
        events = history.json()["items"]
        self.assertTrue(
            any(e["event_type"] == "operation.status_changed" for e in events)
        )
        for event in events:
            self.assertEqual(event["workflow_id"], workflow_id)
            self.assertEqual(event["external_ticket_id"], "raw")
        self.assertNotIn("TEST PRIVATE PROVIDER NOTE", history.text)
        self.assertNotIn("c6-api-key", history.text)
        self.assertNotIn("group_id", history.text)
        path = (
            "/workforce/v1/partner/conversations/"
            + operation["conversation_id"]
            + "/events"
        )

        async def frames(cursor=None):
            messages = await sse_frames(driver.app, path, "raw", 2, cursor)
            self.assertEqual(messages[0]["status"], 200)
            self.assertIn(
                (b"content-type", b"text/event-stream; charset=utf-8"),
                messages[0]["headers"],
            )
            raw = b"".join(m.get("body", b"") for m in messages).decode()

            async def lines():
                for line in raw.splitlines():
                    yield line

            return [frame async for frame in parse_sse(lines())]

        first = await frames()
        second = await frames(first[-1]["event_id"])
        self.assertEqual([f["data"] for f in first + second], events[:4])
        # Disconnect does not implicitly close or cancel a provider operation.
        aggregate = await driver.env.workflows_repo.load(SCOPE, workflow_id)
        self.assertEqual(aggregate.workflow.state, "awaiting_confirmation")
        response = await backend.close("raw", request_id="raw-close")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(backend.tickets["raw"]["workflow_state"], "closed")
        self.assertEqual(driver.provider.calls, 1)

    async def test_atomic_cross_module_rollback_then_worker_retry(self):
        driver = self.driver
        backend, workflow_id, operation = await self.create_operation()
        before = await driver.env.workflows_repo.load(SCOPE, workflow_id)
        history = (await self.history(backend, "raw")).json()
        evidence = await driver.repo.evidence(SCOPE, workflow_id)
        response = await driver.send(self.event(operation))
        receipt_id = response.json()["receipt_id"]
        jobs = len(await self.jobs())
        write = driver.env.events.write

        async def fail_after_write(*args, **kwargs):
            await write(*args, **kwargs)
            raise RuntimeError("TEST crash after public event insert")

        with patch.object(driver.env.events, "write", fail_after_write):
            with self.assertRaisesRegex(RuntimeError, "TEST crash"):
                await driver.processor.process(receipt_id)
        self.assertEqual(
            await driver.env.execution_repository.read(
                "operations", SCOPE, operation["id"]
            ),
            operation,
        )
        self.assertEqual(
            await driver.env.workflows_repo.load(SCOPE, workflow_id), before
        )
        self.assertEqual((await self.history(backend, "raw")).json(), history)
        self.assertEqual(
            await driver.repo.evidence(SCOPE, workflow_id), evidence
        )
        self.assertEqual(len(await self.jobs()), jobs)
        self.assertEqual(
            (await driver.receipt(receipt_id))["ingestion_status"], "accepted"
        )
        driver.restart_worker()
        await self.run_job("assigned")
        await self.run_job("assigned")
        self.assertEqual(
            (await driver.receipt(receipt_id))["ingestion_status"], "applied"
        )
        self.assertEqual(driver.provider.calls, 1)

    async def test_duplicate_late_conflict_and_bad_signature(self):
        driver = self.driver
        backend, workflow_id, operation = await self.create_operation()
        event = self.event(operation, "complete", 4, "completed")
        raw = json.dumps(event).encode()
        headers = driver.signed(raw)
        bad = await driver.client.post(
            "/workforce/v1/provider/job-events",
            content=raw + b" ",
            headers=headers,
        )
        self.assertEqual(bad.status_code, 401)
        self.assertNotIn("TEST-ONLY", bad.text)
        response = await driver.send(event)
        await self.run_job("completed")
        await self.run_job("completed")
        before = await driver.env.workflows_repo.load(SCOPE, workflow_id)
        calls = driver.model.calls
        duplicate = await driver.send(event)
        self.assertTrue(duplicate.json()["duplicate"])
        self.assertEqual(
            duplicate.json()["receipt_id"], response.json()["receipt_id"]
        )
        conflict = await driver.send({**event, "data": {"confirmed": False}})
        self.assertEqual(conflict.status_code, 409)
        late = await driver.send(
            self.event(operation, "late-2", 2, "on_the_way")
        )
        await self.run_job("late-v2")
        self.assertEqual(
            (await driver.receipt(late.json()["receipt_id"]))[
                "ingestion_status"
            ],
            "rejected",
        )
        self.assertEqual((await driver.worker.run_once()).status, "idle")
        self.assertEqual(
            await driver.env.workflows_repo.load(SCOPE, workflow_id), before
        )
        self.assertEqual(driver.model.calls, calls)
        self.assertEqual(driver.provider.calls, 1)

    async def test_closed_workflow_keeps_late_fact_without_public_send(self):
        driver = self.driver
        backend, workflow_id, operation = await self.create_operation()
        await backend.close(
            "raw", stop_tracking_only=True, request_id="stop-raw"
        )
        before = await driver.env.workflows_repo.load(SCOPE, workflow_id)
        history = (await self.history(backend, "raw")).json()
        calls = driver.model.calls
        response = await driver.send(
            self.event(operation, "after-close", 4, "completed")
        )
        await self.run_job("completed")
        current = await driver.env.execution_repository.read(
            "operations", SCOPE, operation["id"]
        )
        self.assertEqual(current["job_status"], "completed")
        self.assertEqual(
            (await driver.receipt(response.json()["receipt_id"]))[
                "ingestion_status"
            ],
            "applied",
        )
        self.assertEqual(
            await driver.env.workflows_repo.load(SCOPE, workflow_id), before
        )
        self.assertEqual((await self.history(backend, "raw")).json(), history)
        self.assertEqual(driver.model.calls, calls)
        self.assertEqual((await driver.worker.run_once()).status, "idle")

    async def test_revoked_route_suppresses_send_but_preserves_fact(self):
        driver = self.driver
        backend, workflow_id, operation = await self.create_operation()
        before = await driver.env.workflows_repo.load(SCOPE, workflow_id)
        calls = driver.model.calls
        async with driver.env.uows() as tx:
            await tx.execute(
                update(partner_manager_routes).values(status="revoked")
            )
            await tx.commit()
        response = await driver.send(
            self.event(operation, "revoked-route", 4, "completed")
        )
        await self.run_job("completed")
        self.assertEqual(
            (await driver.receipt(response.json()["receipt_id"]))[
                "ingestion_status"
            ],
            "applied",
        )
        current = await driver.env.execution_repository.read(
            "operations", SCOPE, operation["id"]
        )
        self.assertEqual(current["job_status"], "completed")
        self.assertEqual(
            await driver.env.workflows_repo.load(SCOPE, workflow_id), before
        )
        self.assertEqual((await self.history(backend, "raw")).status_code, 403)
        self.assertEqual(driver.model.calls, calls)
        self.assertEqual((await driver.worker.run_once()).status, "idle")

    async def test_two_chats_same_user_keep_sql_bindings_and_cursors(self):
        driver = self.driver
        a, workflow_a = await self.open_ticket("A", "interactive", "same-user")
        call_a = self.driver.call
        aggregate_a = await driver.env.workflows_repo.load(SCOPE, workflow_a)
        b, workflow_b = await self.open_ticket("B", "interactive", "same-user")
        call_b = self.driver.call
        aggregate_b = await driver.env.workflows_repo.load(SCOPE, workflow_b)
        for field in ("workflow_id", "conversation_id", "group_id"):
            self.assertNotEqual(
                getattr(aggregate_a.workflow, field),
                getattr(aggregate_b.workflow, field),
            )
        self.assertNotEqual(
            aggregate_a.checkpoint.session_refs,
            aggregate_b.checkpoint.session_refs,
        )
        hist_a = (await self.history(a, "A")).json()
        hist_b = (await self.history(b, "B")).json()
        cursor_a = hist_a["items"][-1]["event_id"]
        wrong = await driver.client.get(
            "/workforce/v1/partner/conversations/"
            + aggregate_b.workflow.conversation_id
            + "/event-history",
            headers=b.headers,
            params={"external_user_id": "same-user", "after_cursor": cursor_a},
        )
        self.assertEqual(wrong.status_code, 410)
        calls = driver.model.calls
        bad = a._base("A", "chat-B", "bad-binding")
        response = await driver.client.post(
            "/workforce/v1/partner/requests",
            headers=a.headers,
            json={
                **bad,
                "command_type": "workflow_reply",
                "workflow_id": workflow_a,
                "message": {"type": "text", "text": "TEST"},
            },
        )
        self.assertEqual(response.status_code, 403)
        self.assertEqual(driver.model.calls, calls)
        for event in hist_a["items"]:
            self.assertEqual(event["external_ticket_id"], "A")
        for event in hist_b["items"]:
            self.assertEqual(event["external_ticket_id"], "B")
        for aggregate in (aggregate_a, aggregate_b):
            path = (
                "/workforce/v1/partner/conversations/"
                + aggregate.workflow.conversation_id
                + "/events"
            )
            messages = await sse_frames(driver.app, path, "same-user", 2)
            self.assertEqual(messages[0]["status"], 200)
            body = b"".join(m.get("body", b"") for m in messages).decode()
            public = [
                json.loads(line[6:])
                for line in body.splitlines()
                if line.startswith("data: ")
            ]
            self.assertGreaterEqual(len(public), 2)
            for event in public:
                self.assertEqual(
                    event["workflow_id"], aggregate.workflow.workflow_id
                )
        # Interleave real replies on the two bindings, without consenting yet.
        for backend, name, call in ((a, "A", call_a), (b, "B", call_b)):
            driver.call = call
            await backend.reply(name, "Select TEST-room", name + "-reply")
            await self.run_job("selection")
            await backend.read_request(name)
        current_a = await driver.env.workflows_repo.load(SCOPE, workflow_a)
        current_b = await driver.env.workflows_repo.load(SCOPE, workflow_b)
        self.assertNotEqual(
            current_a.checkpoint.pending_approval_ids,
            current_b.checkpoint.pending_approval_ids,
        )
        self.assertEqual(driver.provider.calls, 0)
        before_b = (await self.history(b, "B")).json()
        await a.close("A", stop_tracking_only=True, request_id="close-A-only")
        self.assertEqual(
            await driver.env.workflows_repo.load(SCOPE, workflow_b), current_b
        )
        self.assertEqual((await self.history(b, "B")).json(), before_b)
        self.assertEqual((await driver.worker.run_once()).status, "idle")

    async def test_unbound_event_is_quarantined_without_workflow_dispatch(
        self,
    ):
        driver = self.driver
        _, workflow_id, operation = await self.create_operation()
        before = await driver.env.workflows_repo.load(SCOPE, workflow_id)
        event = self.event(operation)
        event.update(
            external_job_id="foreign-job", client_reference="foreign-reference"
        )
        response = await driver.send(event)
        self.assertEqual(response.status_code, 202)
        await self.run_job("assigned")
        receipt = await driver.receipt(response.json()["receipt_id"])
        self.assertEqual(receipt["ingestion_status"], "quarantined")
        self.assertEqual(
            set(receipt),
            {"receipt_id", "ingestion_status", "duplicate", "received_at"},
        )
        self.assertEqual(
            await driver.env.workflows_repo.load(SCOPE, workflow_id), before
        )
        self.assertEqual((await driver.worker.run_once()).status, "idle")

    async def test_protocol_current_drift_does_not_change_running_pin(self):
        driver = self.driver
        _, workflow_id, operation = await self.create_operation()
        original_pin = driver.protocol.snapshot_ref
        changed = driver.protocol.model_copy(
            update={"protocol_version": "2", "timeout_seconds": 120}
        )
        await driver.registry_provider.repository.publish(
            SCOPE, changed, original_pin
        )
        await driver.registry_provider.repository.set_enabled(
            SCOPE, "repair-v1", False, changed.snapshot_ref
        )
        response = await driver.send(
            self.event(operation, "old-pin", 4, "completed")
        )
        await self.run_job("completed")
        await self.run_job("completed")
        current = await driver.env.workflows_repo.load(SCOPE, workflow_id)
        self.assertEqual(current.checkpoint.protocol_pins, (original_pin,))
        self.assertEqual(current.workflow.state, "awaiting_confirmation")
        self.assertEqual(
            (await driver.receipt(response.json()["receipt_id"]))[
                "ingestion_status"
            ],
            "applied",
        )
        self.assertEqual(driver.provider.calls, 1)

    async def test_credential_revoked_after_ack_blocks_worker_apply(self):
        driver = self.driver
        _, workflow_id, operation = await self.create_operation()
        response = await driver.send(self.event(operation))
        before = await driver.env.workflows_repo.load(SCOPE, workflow_id)
        async with driver.env.uows() as tx:
            await tx.execute(
                update(provider_credentials).values(status="revoked")
            )
            await tx.commit()
        with self.assertRaises(PermissionError):
            await driver.processor.process(response.json()["receipt_id"])
        self.assertEqual(
            await driver.env.workflows_repo.load(SCOPE, workflow_id), before
        )
        self.assertEqual(
            await driver.env.execution_repository.read(
                "operations", SCOPE, operation["id"]
            ),
            operation,
        )

    @pytest.mark.xfail(
        strict=True,
        raises=PermissionError,
        reason="IR PHD C6: C4 query hook rolls back fact after revoke",
    )
    async def test_query_after_route_revoke_keeps_fact_without_send(self):
        driver = self.driver
        _, workflow_id, operation = await self.create_operation()
        before = await driver.env.workflows_repo.load(SCOPE, workflow_id)
        async with driver.env.uows() as tx:
            await tx.execute(
                update(partner_manager_routes).values(status="revoked")
            )
            await tx.commit()
        # Required invariant matches provider-event handling: retain verified
        # operation fact, suppress workflow/public sends. C4 currently raises
        # at enqueue_trigger, rolling back the fact in the caller UOW.
        try:
            outcome = await driver.reconciler.reconcile(
                SCOPE, operation["id"], "query-after-revoke"
            )
        except PermissionError:
            # Verify the baseline defect before recording known failure.
            self.assertEqual(
                await driver.env.execution_repository.read(
                    "operations", SCOPE, operation["id"]
                ),
                operation,
            )
            self.assertEqual(
                await driver.env.workflows_repo.load(SCOPE, workflow_id),
                before,
            )
            raise
        self.assertEqual(
            outcome,
            "applied",
        )
        current = await driver.env.execution_repository.read(
            "operations", SCOPE, operation["id"]
        )
        self.assertEqual(current["revision"], operation["revision"] + 1)
        self.assertEqual(
            await driver.env.workflows_repo.load(SCOPE, workflow_id), before
        )
        self.assertEqual((await driver.worker.run_once()).status, "idle")
