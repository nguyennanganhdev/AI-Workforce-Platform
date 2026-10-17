"""TEST ONLY shared SQL ticket/consent helpers for C6 and D3 acceptance."""

from sqlalchemy import select

from agentscope.app.workforce.foundation._tables import durable_jobs
from agentscope.app.workforce.lifecycle.async_evaluation import canonical_hash
from agentscope.app.workforce.lifecycle.async_evaluation._tables import (
    case_runs,
)
from tests.workforce.fixtures.async_partners.customer_backend import (
    CustomerBackend,
)
from tests.workforce.fixtures.phase_c_e2e import SCOPE


class SqlTicketSliceSupport:
    """Uses unittest assertions and an initialized RawProviderCaseDriver."""

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

    async def create_operation(self, name="raw", *, fault=None):
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
        self.driver.provider.fault = fault
        try:
            await self.run_job("approval")
        finally:
            self.driver.provider.fault = None
        replay = await backend.approve(
            name, approval, request_id=name + "-approve"
        )
        self.assertEqual(first.json(), replay.json())
        await backend.read_request(name)
        self.assertEqual(
            backend.tickets[name]["workflow_state"],
            "needs_attention" if fault else "waiting_external_event",
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
