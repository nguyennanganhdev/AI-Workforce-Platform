"""D4 consumes D3's raw HTTP/SQL driver; no production test doubles added."""

from datetime import timedelta
from typing import Any
import unittest
from unittest.mock import patch

from agentscope.app.workforce.lifecycle.releases import (
    PinnedVersionAuthorization,
    SqlReleaseService,
)
from tests.workforce.fixtures.phase_d_execution import D3CaseDriver
from tests.workforce.fixtures.sql_ticket_slice import SqlTicketSliceSupport
from tests.workforce.lifecycle.releases._fixture import ReleaseSupport, SCOPE
from tests.workforce.orchestration.phase_c import test_c4_sql_slice as c4


class LongWaitTests(
    ReleaseSupport, SqlTicketSliceSupport, unittest.IsolatedAsyncioTestCase
):
    async def asyncSetUp(self) -> None:
        self.driver = D3CaseDriver()
        await self.driver.setup()
        await self.setup_release()
        await self.publish()
        self.delegate = self.driver.env.workflow_service.authorization
        self.authorization = PinnedVersionAuthorization(self.delegate, self.releases)
        self.driver.env.workflow_service.authorization = self.authorization
        self.driver.snapshot = self.initial_snapshot

    async def asyncTearDown(self) -> None:
        await self.driver.cleanup()

    async def test_200_day_wait_publish_rollback_archive_protocol_drift_and_restart(
        self,
    ) -> None:
        backend, workflow_id, operation = await self.create_operation()
        before = await self.driver.env.workflows_repo.load(SCOPE, workflow_id)
        old_id = self.initial_snapshot.candidate_version_id
        second = self.next_candidate()
        await self.releases.stage_candidate(
            SCOPE, second, self.initial_snapshot.draft_revision
        )
        # Isolated candidate evals use C5 authorization; the catalog guard is
        # for published production workflows, not unpublished eval candidates.
        self.driver.env.workflow_service.authorization = self.delegate
        try:
            await self.evaluate(second, "eval-v2")
        finally:
            self.driver.env.workflow_service.authorization = self.authorization
        new_id = (
            await self.releases.publish_selected(
                SCOPE,
                [
                    self.selection(
                        frozen=second, evaluation_id="eval-v2", deployment_revision=1
                    )
                ],
                self.context,
                "publish-v2",
            )
        )[0]
        self.assertEqual(
            (await self.releases.list_candidates(SCOPE, ()))[0].version_id, new_id
        )
        self.assertEqual(
            await self.releases.rollback(
                SCOPE,
                self.initial_snapshot.agent_id,
                old_id,
                2,
                self.context,
                "rollback",
            ),
            old_id,
        )
        await self.releases.set_availability(
            SCOPE, self.initial_snapshot.agent_id, 3, archived=True, enabled=True
        )
        old_protocol = self.driver.protocol
        revised = old_protocol.model_copy(
            update={"protocol_version": "2", "ordering": "provider_version"}
        )
        await self.driver.registry_provider.repository.publish(
            SCOPE, revised, old_protocol.snapshot_ref
        )
        await self.driver.registry_provider.repository.set_enabled(
            SCOPE, "repair-v1", False, revised.snapshot_ref
        )

        # C4's injected clock is shared by SQL/HTTP/HMAC/services in this
        # fixture. Advancing it does not change or rewrite persisted pins.
        with patch.object(c4, "NOW", c4.NOW + timedelta(days=200)):
            await self.driver.env.engine.dispose()
            self.driver.new_worker()
            service = SqlReleaseService(
                self.driver.env.uows,
                self.validator,
                self.driver.env.ingress.identity,
                clock=self.driver.env.clock,
            )
            self.authorization.releases = service
            self.assertFalse(await service.list_candidates(SCOPE, ()))
            self.assertEqual(
                (await service.get_version(SCOPE, old_id)).frozen, self.frozen
            )
            await service.assert_usable(SCOPE, old_id, self.initial_snapshot.agent_id)
            loaded = await self.driver.env.workflows_repo.load(SCOPE, workflow_id)
            self.assertEqual(loaded, before)

            class Usage:
                async def references(inner, scope: Any, version_id: str) -> Any:
                    aggregate = await self.driver.env.workflows_repo.load(
                        scope, workflow_id
                    )
                    return (
                        (workflow_id, aggregate.workflow.checkpoint_ref)
                        if version_id in aggregate.workflow.version_pins
                        else ()
                    )

            self.assertEqual(
                await service.retention_references(SCOPE, old_id, Usage()),
                (workflow_id, before.workflow.checkpoint_ref),
            )
            counts = (self.driver.model.calls, self.driver.provider.calls)
            self.assertEqual((await self.driver.worker.run_once()).status, "idle")
            self.assertEqual(
                counts, (self.driver.model.calls, self.driver.provider.calls)
            )
            response = await self.driver.send(
                self.event(operation, "d4-completed", 4, "completed")
            )
            self.assertEqual(response.status_code, 202, response.text)
            await self.run_job("completed")
            await self.run_job("completed")
            resumed = await self.driver.env.workflows_repo.load(SCOPE, workflow_id)
            self.assertEqual(resumed.workflow.state, "awaiting_confirmation")
            self.assertEqual(resumed.workflow.version_pins, (old_id,))
            self.assertEqual(
                resumed.checkpoint.agent_version_pins,
                before.checkpoint.agent_version_pins,
            )
            self.assertEqual(
                resumed.checkpoint.protocol_pins, before.checkpoint.protocol_pins
            )
            self.assertEqual(
                resumed.checkpoint.session_refs, before.checkpoint.session_refs
            )
            self.assertEqual(self.driver.provider.calls, counts[1])
            self.assertEqual(self.driver.model.calls, counts[0] + 1)
            history = await self.history(backend, "raw")
            duplicate = await self.driver.send(
                self.event(operation, "d4-completed", 4, "completed")
            )
            self.assertEqual(
                duplicate.json()["receipt_id"], response.json()["receipt_id"]
            )
            self.assertTrue(duplicate.json()["duplicate"])
            self.assertEqual(duplicate.json()["ingestion_status"], "applied")
            self.assertEqual((await self.driver.worker.run_once()).status, "idle")
            self.assertEqual(
                (await self.history(backend, "raw")).json(), history.json()
            )

    async def test_disable_after_approval_enqueue_stops_model_and_tool_before_resume(
        self,
    ) -> None:
        backend, workflow_id = await self.open_ticket(
            "approval-wait", pattern="interactive"
        )
        await backend.reply("approval-wait", "Select TEST-room", request_id="select-D4")
        await self.run_job("selection")
        approval = await self.driver.env.execution_repository.read(
            "approvals", SCOPE, self.driver.call["approval_id"]
        )
        response = await backend.approve(
            "approval-wait",
            {**approval, "approval_id": approval["id"]},
            request_id="approve-D4",
        )
        self.assertEqual(response.status_code, 202, response.text)
        before = await self.driver.env.workflows_repo.load(SCOPE, workflow_id)
        counts = (self.driver.model.calls, self.driver.provider.calls)
        await self.releases.set_availability(
            SCOPE, self.initial_snapshot.agent_id, 1, archived=False, enabled=False
        )
        self.driver.cause = "approval"
        # PHH commits a business blocked state; the durable handler completed
        # its job successfully without invoking the model or provider.
        self.assertEqual((await self.driver.worker.run_once()).status, "succeeded")
        self.assertEqual(counts, (self.driver.model.calls, self.driver.provider.calls))
        after = await self.driver.env.workflows_repo.load(SCOPE, workflow_id)
        self.assertEqual(after.workflow.state, "blocked_authorization")
        self.assertEqual(after.checkpoint.used_budget, before.checkpoint.used_budget)
        self.assertEqual(
            after.checkpoint.agent_version_pins, before.checkpoint.agent_version_pins
        )
        self.assertEqual(
            after.checkpoint.protocol_pins, before.checkpoint.protocol_pins
        )
        self.assertEqual(after.workflow.version_pins, before.workflow.version_pins)

    async def test_revoke_keeps_provider_fact_suppresses_public_message_and_wakeup(
        self,
    ) -> None:
        backend, workflow_id, operation = await self.create_operation()
        before = await self.driver.env.workflows_repo.load(SCOPE, workflow_id)
        history = (await self.history(backend, "raw")).json()
        counts = (self.driver.model.calls, self.driver.provider.calls)
        await self.releases.set_availability(
            SCOPE, self.initial_snapshot.agent_id, 1, archived=False, enabled=False
        )
        response = await self.driver.send(
            self.event(operation, "revoked-completed", 4, "completed")
        )
        self.assertEqual(response.status_code, 202)
        await self.run_job("completed")
        self.assertEqual((await self.driver.worker.run_once()).status, "idle")
        fact = await self.driver.env.execution_repository.read(
            "operations", SCOPE, operation["id"]
        )
        self.assertEqual(fact["job_status"], "completed")
        self.assertFalse(fact["pending"])
        self.assertEqual(
            await self.driver.env.workflows_repo.load(SCOPE, workflow_id), before
        )
        self.assertEqual((await self.history(backend, "raw")).json(), history)
        self.assertEqual(counts, (self.driver.model.calls, self.driver.provider.calls))

    async def test_forged_protocol_reference_with_same_hash_is_rejected(self) -> None:
        _, workflow_id, _ = await self.create_operation()
        aggregate = await self.driver.env.workflows_repo.load(SCOPE, workflow_id)
        forged = aggregate.model_copy(
            update={
                "checkpoint": aggregate.checkpoint.model_copy(
                    update={
                        "protocol_pins": (
                            aggregate.checkpoint.protocol_pins[0].model_copy(
                                update={"protocol_version": "forged"}
                            ),
                        )
                    }
                )
            }
        )
        with self.assertRaisesRegex(ValueError, "PROTOCOL_PIN_MISMATCH"):
            await self.authorization._pins(forged)
