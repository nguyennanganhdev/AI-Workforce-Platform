"""Release-candidate mock system for the full-platform acceptance tests.

The fixture deliberately composes production SQL repositories, HTTP routes,
ticket binding, durable jobs and workflow continuation.  Only the model answer
and external provider are deterministic test doubles.  It is therefore useful
for the D5 mock E2E gate without pretending that a partner sandbox was used.
"""

from __future__ import annotations

import asyncio
from contextlib import asynccontextmanager, suppress

from fastapi import FastAPI, Request
from httpx import ASGITransport, AsyncClient
from sqlalchemy import func, select

from agentscope.app.workforce.contracts import (
    AssistantMessage,
    RequestResult,
    WorkflowState,
)
from agentscope.app.workforce.foundation._tables import durable_jobs
from agentscope.app.workforce.orchestration import (
    LeaderBootstrapSeed,
    LeaderWorkflowBootstrap,
    create_router,
)
from agentscope.app.workforce.orchestration._tables import workflow_bindings
from agentscope.app.workforce.orchestration.workflows import TurnDecision
from agentscope.app.workforce.orchestration.workflows.phase_a import (
    RuntimeTurnResult,
)
from tests.workforce.orchestration.phase_c.test_c4_sql_slice import (
    SCOPE,
    C4SqlSliceTests,
)


class _ReleaseBootstrapResolver:
    """Choose lifecycle policy from the test ticket, not a domain name."""

    def __init__(self, ids) -> None:
        self._ids = ids

    async def resolve(self, scope, actor, audience, uow):
        del scope, actor, uow
        read_only = audience.external_ticket_id == "READ-ONLY"
        return LeaderBootstrapSeed(
            leader_agent_id="platform-leader",
            leader_version_id="leader-v1",
            group_id=self._ids(),
            session_ref=self._ids(),
            shared_state_ref=self._ids(),
            pattern="response_only" if read_only else "interactive",
            published_read_only=read_only,
        )


class _ReleaseLeader:
    """Deterministic model boundary; workflow transitions remain production."""

    def __init__(self, clock) -> None:
        self._clock = clock
        self.calls = 0

    async def invoke_turn(self, scope, trigger, context, execution_guard):
        del scope
        await execution_guard.check("read")
        self.calls += 1
        is_read_only = (
            context.workflow.audience.external_ticket_id == "READ-ONLY"
        )
        checkpoint = context.checkpoint.model_copy(
            update={
                "state_revision": context.workflow.revision + 1,
                "used_budget": context.checkpoint.used_budget.model_copy(
                    update={
                        "model_turns": (
                            context.checkpoint.used_budget.model_turns + 1
                        )
                    }
                ),
            }
        )
        return TurnDecision(
            candidate=RuntimeTurnResult(
                trigger_id=trigger["trigger_id"],
                expected_state_revision=context.workflow.revision,
                checkpoint=checkpoint,
                result=RequestResult(
                    messages=(
                        AssistantMessage(
                            message_id=f"rc-message-{self.calls}",
                            workflow_id=context.workflow.workflow_id,
                            text="TEST release-candidate response",
                            created_at=self._clock(),
                        ),
                    )
                ),
            ),
            next_state=(
                WorkflowState.CLOSED
                if is_read_only
                else WorkflowState.AWAITING_USER
            ),
        )


class ReleaseCandidateSystem:
    """Interface consumed by ``test_full_platform``."""

    def __init__(self) -> None:
        self._slice = C4SqlSliceTests(methodName="runTest")
        self._worker_task: asyncio.Task | None = None
        self._stopping = asyncio.Event()

    async def start(self) -> ReleaseCandidateSystem:
        await self._slice.asyncSetUp()
        self.management_ref = "tower-a"
        self.customer_headers = {"x-test-user": "resident-123"}
        self.leader = _ReleaseLeader(self._slice.clock)
        self._slice.runtime._leader = self.leader
        self._slice.workflow_service.bootstrap = LeaderWorkflowBootstrap(
            _ReleaseBootstrapResolver(self._slice.ids),
            clock=self._slice.clock,
            ids=self._slice.ids,
        )

        async def customer(request: Request):
            external_user_id = request.headers.get(
                "x-test-user", "resident-123"
            )
            return self._slice.actor.model_copy(
                update={"external_user_id": external_user_id}
            )

        app = FastAPI()
        app.include_router(
            create_router(
                self._slice.ingress,
                self._slice.event_service,
                customer,
                bounded_wait_seconds=2.0,
            )
        )
        self.client = AsyncClient(
            transport=ASGITransport(app=app),
            base_url="https://platform.test",
        )
        self._worker_task = asyncio.create_task(self._worker_loop())
        return self

    async def close(self) -> None:
        self._stopping.set()
        if self._worker_task is not None:
            self._worker_task.cancel()
            with suppress(asyncio.CancelledError):
                await self._worker_task
        if hasattr(self, "client"):
            await self.client.aclose()
        await self._slice.asyncTearDown()

    async def _worker_loop(self) -> None:
        while not self._stopping.is_set():
            outcome = await self._slice.worker.run_once()
            if outcome.status == "idle":
                await asyncio.sleep(0.005)

    async def count_operations(self, workflow_id: str) -> int:
        from agentscope.app.workforce.execution.external_operations._tables import (
            external_operations,
        )

        async with self._slice.uows() as uow:
            value = await uow.execute(
                select(func.count())
                .select_from(external_operations)
                .where(external_operations.c.workflow_id == workflow_id)
            )
            return int(value.scalar_one())

    async def count_tracking_jobs(self, workflow_id: str) -> int:
        del workflow_id
        async with self._slice.uows() as uow:
            value = await uow.execute(
                select(func.count())
                .select_from(durable_jobs)
                .where(
                    durable_jobs.c.job_type.in_(
                        ("provider_event", "operation_reconcile")
                    )
                )
            )
            return int(value.scalar_one())

    async def runtime_state(self, workflow_id: str) -> dict:
        aggregate = await self._slice.workflows_repo.load(SCOPE, workflow_id)
        return {
            "group_id": aggregate.workflow.group_id,
            "session_ids": list(aggregate.checkpoint.session_refs),
        }

    async def model_tool_counts(self) -> tuple[int, int]:
        from agentscope.app.workforce.execution.external_operations._tables import (
            external_operations,
        )

        async with self._slice.uows() as uow:
            value = await uow.execute(
                select(func.count()).select_from(external_operations)
            )
            operations = int(value.scalar_one())
        return self.leader.calls, operations

    async def count_bindings(
        self, external_user_id: str, external_ticket_id: str
    ) -> int:
        async with self._slice.uows() as uow:
            value = await uow.execute(
                select(func.count())
                .select_from(workflow_bindings)
                .where(
                    workflow_bindings.c.external_user_id
                    == external_user_id,
                    workflow_bindings.c.external_ticket_id
                    == external_ticket_id,
                )
            )
            return int(value.scalar_one())


@asynccontextmanager
async def factory():
    """Build one isolated mock platform for an acceptance scenario."""

    system = await ReleaseCandidateSystem().start()
    try:
        yield system
    finally:
        await system.close()


__all__ = ["ReleaseCandidateSystem", "factory"]
