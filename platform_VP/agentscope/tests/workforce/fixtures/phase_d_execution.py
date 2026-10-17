"""TEST ONLY D3 faults around SQL, signed HTTP and C7 command/job adapters.

Leader/catalog/quote/MCP remain controlled test ports from the C6 fixture.
Restart creates new job/processor instances and reconnects the SQLite file;
this does not claim a process kill, PostgreSQL failover or live provider test.
"""

from datetime import timedelta

from agentscope.app.workforce.execution.provider_events import (
    ProviderEventProcessor,
)
from agentscope.app.workforce.foundation import (
    DurableJobService,
    DurableJobWorker,
    SqlDurableJobRepository,
)
from agentscope.app.workforce.integrations.async_runtime import (
    ApprovalContinuationCommandAdapter,
    OperationReconcileJobHandler,
)
from agentscope.app.workforce.orchestration import (
    SqlPartnerRequestRepository,
    WorkflowContinuationJobHandler,
)
from tests.workforce.fixtures.phase_c_e2e import RawProviderCaseDriver, SCOPE


class D3CaseDriver(RawProviderCaseDriver):
    async def setup(self):
        await super().setup()
        authorize = self.partner_approvals.commands.authorize_approval

        async def tenant(actor, uow):
            if actor.partner_client_id != self.env.actor.partner_client_id:
                raise PermissionError("test customer tenant mismatch")
            return SCOPE.tenant_id

        commands = SqlPartnerRequestRepository(
            self.env.uows,
            tenant,
            approval_authorizer=authorize,
            clock=self.env.clock,
            ids=self.env.ids,
        )
        self.partner_approvals.commands = ApprovalContinuationCommandAdapter(
            commands, self.env.workflow_service
        )
        self.new_worker()

    def new_worker(self, *, seconds=0):
        """No in-memory claim state is carried to the replacement worker."""
        now = self.env.clock() + timedelta(seconds=seconds)
        jobs = DurableJobService(
            SqlDurableJobRepository(self.env.uows),
            clock=lambda: now,
            id_factory=self.env.ids,
        )
        self.processor = ProviderEventProcessor(
            self.provider_ingress, self.workflow_adapter
        )
        continuation = WorkflowContinuationJobHandler(
            self.continuation, worker_id="d3-turn"
        )
        self.worker = DurableJobWorker(
            jobs,
            {
                "provider_event": self.processor.handle_job,
                continuation.job_type: continuation,
                "operation_reconcile": OperationReconcileJobHandler(
                    self.reconciler
                ),
            },
            worker_id="d3-worker-" + str(seconds),
        )
        self.worker_jobs = jobs
        return jobs
