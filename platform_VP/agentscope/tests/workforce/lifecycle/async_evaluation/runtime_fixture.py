"""TEST ONLY model/provider composition around C1/C2/C4 SQL and Execution.

No Lifecycle expectations or FakeRunner are imported here. The scripted model
reacts to input and persisted provider facts; production decides and commits
workflow transitions, validates pins/consent/tools and records turn evidence.
"""

from contextlib import asynccontextmanager
from typing import Any, Awaitable, Callable, Dict, Mapping, Tuple

from agentscope.app.workforce.contracts import (
    AssistantMessage,
    EvaluationSnapshot,
    NormalizedJobEvent,
    Scope,
    WorkflowState,
)
from agentscope.app.workforce.execution import (
    ApprovalService,
    ExecutionGateway,
    ExecutionPolicy,
    TransactionService,
)
from agentscope.app.workforce.execution._mcp_adapter import McpAdapter
from agentscope.app.workforce.execution._utils import ExecutionError
from agentscope.app.workforce.execution.external_operations import (
    ExecutionProtocolAdapter,
    ExternalOperationService,
)
from agentscope.app.workforce.foundation import DurableJobWorker
from agentscope.app.workforce.lifecycle.async_evaluation import (
    RuntimeAudit,
    RuntimeObservation,
    SqlEvaluationRepository,
    SqlRuntimeEvidenceWriter,
    canonical_hash,
    get_metadata,
)
from agentscope.app.workforce.orchestration import (
    LeaderBootstrapSeed,
    LeaderWorkflowBootstrap,
    WorkflowContinuationJobHandler,
)
from agentscope.app.workforce.orchestration.workflows import (
    TurnDecision,
    WorkflowContinuation,
    WorkflowQueryResult,
    next_action,
)
from agentscope.app.workforce.orchestration.workflows.phase_a import (
    PinnedRuntimeContext,
    RuntimeTurnResult,
)
from agentscope.app.workforce.registry.event_protocols import SqlAsyncProtocolProvider
from agentscope.app.workforce.registry.event_protocols._tables import (
    metadata as registry_metadata,
)
from tests.workforce.fixtures import execution_fakes as ef
from tests.workforce.orchestration.phase_c import test_c4_sql_slice as c4
from tests.workforce.lifecycle.async_evaluation.test_phase_b import fixture, seal


class _Bootstrap:
    def __init__(self, driver: "SqlCaseDriver") -> None:
        self.driver = driver

    async def resolve(self, scope: Scope, actor: Any, audience: Any, uow: Any) -> Any:
        driver = self.driver
        return LeaderBootstrapSeed(
            leader_agent_id=driver.snapshot.agent_id,
            leader_version_id=driver.snapshot.candidate_version_id,
            group_id=driver.env.ids(),
            session_ref=driver.env.ids(),
            shared_state_ref=driver.env.ids(),
            pattern=driver.pattern,
            published_read_only=driver.pattern == "response_only",
        )

    async def prepare(
        self, scope: Scope, actor: Any, audience: Any, message: Any, uow: Any
    ) -> Any:
        aggregate = await LeaderWorkflowBootstrap(
            self, clock=self.driver.env.clock, ids=self.driver.env.ids
        ).prepare(scope, actor, audience, message, uow)
        await self.driver.bind_case(aggregate.workflow.workflow_id, uow)
        return aggregate.model_copy(
            update={
                "checkpoint": aggregate.checkpoint.model_copy(
                    update={"protocol_pins": (self.driver.protocol.snapshot_ref,)}
                )
            }
        )


class _ModelLeader:
    def __init__(self, driver: "SqlCaseDriver") -> None:
        self.driver = driver
        self.calls = 0
        self.use_guard = True

    async def invoke_turn(
        self,
        scope: Scope,
        trigger: Dict[str, Any],
        context: PinnedRuntimeContext,
        execution_guard: Any,
    ) -> Any:
        if self.use_guard:
            await execution_guard.check("read")
        self.calls += 1
        driver = self.driver
        cause = driver.cause
        fields: Dict[str, Any] = {}
        tool_calls = 0
        if cause == "request":
            state = WorkflowState.CLOSED
        elif cause == "plan":
            state = WorkflowState.AWAITING_USER
        elif cause == "selection":
            proposed = await driver.gateway.execute(scope, driver.call)
            fields["pending_approval_ids"] = (proposed["approval_id"],)
            driver.call["approval_id"] = proposed["approval_id"]
            state = WorkflowState.AWAITING_APPROVAL
        elif cause in {"approval", "create-pending", "create-timeout"}:
            if cause != "approval":
                proposed = await driver.gateway.execute(scope, driver.call)
                driver.call["approval_id"] = proposed["approval_id"]
                await driver.approve(scope)
            await execution_guard.check("booking")
            result = await driver.gateway.execute(scope, driver.call)
            tool_calls = 1
            fields["pending_approval_ids"] = ()
            if driver.pattern == "external_tracking":
                operations = await driver.operations.get_for_workflow(
                    scope, context.workflow.workflow_id
                )
                fields["operation_refs"] = tuple(op["id"] for op in operations)
                state = (
                    WorkflowState.NEEDS_ATTENTION
                    if result["status"] == "unknown"
                    else WorkflowState.WAITING_EXTERNAL_EVENT
                )
            else:
                state = WorkflowState.AWAITING_CONFIRMATION
        else:
            operations = await driver.operations.get_for_workflow(
                scope, context.workflow.workflow_id
            )
            state = (
                WorkflowState.AWAITING_CONFIRMATION
                if operations and not operations[0]["pending"]
                else WorkflowState.WAITING_EXTERNAL_EVENT
            )
        budget = context.checkpoint.used_budget
        checkpoint = context.checkpoint.model_copy(
            update={
                **fields,
                "state_revision": context.workflow.revision + 1,
                "used_budget": budget.model_copy(
                    update={
                        "model_turns": budget.model_turns + 1,
                        "tool_calls": budget.tool_calls + tool_calls,
                        "input_tokens": budget.input_tokens + 10,
                        "output_tokens": budget.output_tokens + 5,
                    }
                ),
            }
        )
        return TurnDecision(
            candidate=RuntimeTurnResult(
                trigger_id=trigger["trigger_id"],
                expected_state_revision=context.workflow.revision,
                checkpoint=checkpoint,
                result={
                    "messages": (
                        AssistantMessage(
                            message_id=driver.env.ids(),
                            workflow_id=context.workflow.workflow_id,
                            text="Fixture response",
                            created_at=driver.env.clock(),
                        ),
                    )
                },
            ),
            next_state=state,
        )


class SqlCaseDriver:
    """Explicit test driver; commands/checkpoints/guards/tools are production code."""

    async def setup(self) -> None:
        self.env = c4.C4SqlSliceTests()
        await self.env.asyncSetUp()
        async with self.env.engine.begin() as connection:
            await connection.run_sync(get_metadata().create_all)
            await connection.run_sync(registry_metadata.create_all)
            await connection.run_sync(ef.test_metadata.create_all)
        data = fixture()
        data.update(
            scope=c4.SCOPE,
            policy_scope=c4.SCOPE,
            snapshot=data["snapshot"].model_copy(update={"scope": c4.SCOPE}),
        )
        self.protocol = data["protocols"][0].model_copy(
            update={
                "external_job_id_field": "external_job_id",
                "transitions": {
                    "pending": ("assigned", "completed"),
                    "assigned": ("on_the_way",),
                    "on_the_way": ("arrived",),
                    "arrived": ("completed",),
                },
            }
        )
        data["protocols"] = [self.protocol]
        data["manifest"] = data["manifest"].model_copy(
            update={
                "protocol_snapshot_hashes": (self.protocol.snapshot_ref.schema_hash,)
            }
        )
        self.frozen = seal(data)
        self.snapshot = EvaluationSnapshot.model_validate(
            self.frozen.read(c4.SCOPE)["snapshot"]
        )
        self.repo = SqlEvaluationRepository(self.env.uows)
        self.registry_provider = SqlAsyncProtocolProvider(self.env.uows)
        await self.registry_provider.repository.publish(c4.SCOPE, self.protocol, None)

        async def no_inbox(*args: Any) -> Any:
            raise AssertionError(
                "C5 stimuli use normalized facts; provider HTTP belongs to C6"
            )

        self.protocols = ExecutionProtocolAdapter(
            self.registry_provider.bind(c4.SCOPE, no_inbox),
            self.registry_provider.resolve_detail,
        )
        self.operations = ExternalOperationService(
            self.env.execution_repository, self.env.clock
        )
        self.descriptor = data["tools"][0].model_dump(mode="json")
        self.descriptor.update(
            effect="booking", effect_reviewed=True, credential_ref="TEST-ONLY-ref"
        )
        self.runtime_authority = ef.Runtime(self.descriptor)
        self.runtime_authority.spec["tool_bindings"] = [
            item.model_dump() for item in self.snapshot.manifest.spec.tool_bindings
        ]
        self.approvals = ApprovalService(
            self.env.execution_repository,
            self.runtime_authority,
            ef.Quotes(self.env.clock),
            ef.Hitl(),
            self.env.clock,
        )
        self.provider = ef.FakeMcpProvider(self.descriptor["input_schema"])
        self.provider.rooms = 100

        async def after_write(arguments: Any, result: Dict[str, Any]) -> None:
            if self.pattern == "external_tracking":
                result["status"] = "pending"

        self.provider.after_write = after_write

        @asynccontextmanager
        async def client_factory(*args: Any) -> Any:
            yield self.provider

        secrets = ef.Secrets()
        secrets.owner = c4.SCOPE.model_dump()
        mcp = McpAdapter(
            secrets,
            client_factory,
            ef.Projector(),
            idempotency_fields={"repair-v1": "idempotency_key"},
        )
        self.gateway = ExecutionGateway(
            ExecutionPolicy(self.runtime_authority, ef.Registry(self.descriptor)),
            TransactionService(
                self.env.execution_repository, self.approvals, self.env.clock
            ),
            mcp,
            self.operations,
            self.protocols,
        )
        self.model = _ModelLeader(self)
        self.env.runtime._leader = self.model
        self.env.workflow_service.bootstrap = _Bootstrap(self)
        self.writer = SqlRuntimeEvidenceWriter(self.repo, c4.SCOPE)
        self.continuation = WorkflowContinuation(
            self.env.workflow_service,
            self.env.requests,
            self.env.ingress.completion_signals,
            evidence=self.writer,
        )
        handler = WorkflowContinuationJobHandler(self.continuation, worker_id="c5-turn")

        async def checked_job(job: Any) -> Any:
            try:
                return await handler(job)
            except Exception as error:
                self.last_turn_error = error
                raise

        self.worker = DurableJobWorker(
            self.env.jobs,
            {handler.job_type: checked_job},
            worker_id="c5-driver",
        )
        self.opened: Dict[str, Tuple[Any, Any]] = {}
        self.observations: Dict[str, RuntimeObservation] = {}
        self.event_keys: Dict[Tuple[str, str], str] = {}
        self.apply_calls = 0

    async def open_case(
        self,
        scope: Scope,
        snapshot: EvaluationSnapshot,
        test_case: Mapping[str, Any],
        bind: Callable[[str, Any], Awaitable[None]],
    ) -> str:
        case_id = test_case["case_id"]
        self.pattern = test_case["pattern"]
        self.snapshot = snapshot
        self.bind_case = bind
        if case_id in self.opened:
            self.actor, receipt = self.opened[case_id]
            async with self.env.uows() as tx:
                await bind(receipt.workflow_id, tx)
                await tx.commit()
        else:
            self.actor = self.env.actor.model_copy(update={"external_user_id": case_id})
            envelope = self.env.envelope(case_id, "ticket-A", "chat-" + case_id)
            receipt = await self.env.ingress.accept(
                self.actor, envelope.model_copy(update={"external_user_id": case_id})
            )
            self.opened[case_id] = (self.actor, receipt)
        aggregate = await self.env.workflows_repo.load(scope, receipt.workflow_id)
        self.call = {
            "call_id": "call-" + case_id,
            "run_id": receipt.workflow_id,
            "agent_id": snapshot.agent_id,
            "version_id": snapshot.candidate_version_id,
            "tool_version_id": "repair-v1",
            "arguments": {"room": "TEST-room"},
            "idempotency_key": "call-" + case_id,
        }
        self.runtime_authority.contexts[receipt.workflow_id] = {
            "run_id": receipt.workflow_id,
            "scope": scope.model_dump(),
            "mode": "evaluation",
            "workflow_id": receipt.workflow_id,
            "conversation_id": receipt.conversation_id,
            "ticket_id": aggregate.workflow.ticket_id,
            "group_id": aggregate.workflow.group_id,
            "partner_audience": aggregate.workflow.audience.model_dump(),
            "allowed_decider": {
                "kind": "manager",
                "actor_id": scope.manager_account_id,
            },
            "status": "running",
            "route_revision": 1,
            "version_pins": [
                {
                    "agent_id": snapshot.agent_id,
                    "version_id": snapshot.candidate_version_id,
                }
            ],
        }
        if self.pattern == "external_tracking":
            self.descriptor["async_protocol_hash"] = (
                self.protocol.snapshot_ref.schema_hash
            )
        else:
            self.descriptor.pop("async_protocol_hash", None)
        return receipt.workflow_id

    async def approve(self, scope: Scope) -> None:
        approval = await self.env.execution_repository.read(
            "approvals", scope, self.call["approval_id"]
        )
        await self.approvals.decide_approval(
            scope,
            approval["id"],
            "approve",
            {"kind": "manager", "actor_id": scope.manager_account_id},
            arguments_hash=approval["arguments_hash"],
            quote_hash=approval["quote_hash"],
        )

    async def apply(
        self,
        scope: Scope,
        workflow_id: str,
        stimulus: Mapping[str, Any],
        operation_key: str,
    ) -> RuntimeObservation:
        if operation_key in self.observations:
            return self.observations[operation_key]
        self.apply_calls += 1
        self.cause = stimulus["cause"]
        before = await self.env.workflows_repo.load(scope, workflow_id)
        evidence_before = await self.repo.evidence(scope, workflow_id)
        provider_calls = self.provider.calls
        if self.cause == "selection":
            async with self.env.uows() as tx:
                claim = await self.env.requests.claim_or_read(
                    self.actor,
                    operation_key,
                    "workflow_reply",
                    workflow_id,
                    canonical_hash(stimulus),
                    tx,
                )
                await self.env.workflow_service.accept_reply(
                    scope,
                    self.actor,
                    before.workflow.audience,
                    workflow_id,
                    {
                        "request_id": claim.request_id,
                        "text": "Select TEST-room",
                        "expected_revision": before.workflow.revision,
                    },
                    tx,
                )
                await tx.commit()
        elif self.cause == "approval":
            await self.approve(scope)
            async with self.env.uows() as tx:
                claim = await self.env.requests.claim_or_read(
                    self.actor,
                    operation_key,
                    "approval",
                    workflow_id,
                    canonical_hash(stimulus),
                    tx,
                )
                await self.env.workflow_service.enqueue_trigger(
                    scope,
                    {
                        "trigger_id": operation_key,
                        "workflow_id": workflow_id,
                        "cause": {
                            "kind": "approval",
                            "request_id": claim.request_id,
                            "approval_id": self.call["approval_id"],
                        },
                    },
                    tx,
                )
                await tx.commit()
        elif self.cause == "close":
            audience = before.workflow.audience
            await self.env.workflow_service.close(
                scope,
                self.actor,
                audience,
                {
                    "workflow_id": workflow_id,
                    "expected_revision": before.workflow.revision,
                    "external_request_id": operation_key,
                    "external_user_id": audience.external_user_id,
                    "external_ticket_id": audience.external_ticket_id,
                    "external_conversation_id": audience.external_conversation_id,
                    "reason": "TEST-complete",
                    "schema_version": "1",
                },
            )
        elif self.cause == "ticket-B-event":
            operation = (await self.operations.get_for_workflow(scope, workflow_id))[0]
            try:
                await self.env.workflow_service.apply_external_event(
                    scope,
                    operation["id"],
                    NormalizedJobEvent(
                        inbox_event_id=operation_key,
                        provider_integration_id=operation["provider_integration_id"],
                        external_event_id=operation_key,
                        client_reference="ticket-B-correlation",
                        normalized_status="completed",
                        facts={"confirmed": True},
                        protocol_schema_hash=self.protocol.snapshot_ref.schema_hash,
                        source_hash=operation_key,
                        occurred_at=self.env.clock(),
                        received_at=self.env.clock(),
                    ),
                )
            except PermissionError:
                pass
            else:
                raise AssertionError("foreign provider correlation was accepted")
        elif self.cause == "ticket-B-approval":
            approval = await self.env.execution_repository.read(
                "approvals", scope, self.call["approval_id"]
            )
            try:
                await self.approvals.decide_approval(
                    scope,
                    approval["id"],
                    "approve",
                    {"kind": "manager", "actor_id": "manager-B"},
                    arguments_hash=approval["arguments_hash"],
                    quote_hash=approval["quote_hash"],
                )
            except ExecutionError as error:
                if error.code != "APPROVAL_DECIDER_FORBIDDEN":
                    raise
            else:
                raise AssertionError("foreign approval decider was accepted")
            try:
                await self.env.workflow_service.accept_reply(
                    scope,
                    self.actor,
                    before.workflow.audience.model_copy(
                        update={"external_ticket_id": "ticket-B"}
                    ),
                    workflow_id,
                    {
                        "request_id": operation_key,
                        "text": "TEST",
                        "expected_revision": before.workflow.revision,
                    },
                )
            except PermissionError:
                pass
            else:
                raise AssertionError("foreign audience was accepted")
        elif self.cause not in {
            "request",
            "plan",
            "create-pending",
            "create-timeout",
            "idle-before-timer",
            "ticket-B-event",
        }:
            await self.provider_fact(scope, before, operation_key)
        if self.cause == "create-timeout":
            self.provider.fault = "timeout_after_write"
        if self.cause not in {
            "idle-before-timer",
            "ticket-B-event",
            "ticket-B-approval",
            "close",
        }:
            job = await self.worker.run_once()
            if job.status not in {"succeeded", "idle"}:
                raise self.last_turn_error
        self.provider.fault = None
        after = await self.env.workflows_repo.load(scope, workflow_id)
        evidence_after = await self.repo.evidence(scope, workflow_id)
        trigger_ids = tuple(
            item.trigger_id
            for item in evidence_after
            if item.trigger_id not in {e.trigger_id for e in evidence_before}
        )
        ops = await self.operations.get_for_workflow(scope, workflow_id)
        effects = self.provider.calls - provider_calls
        async with self.env.uows() as tx:
            call_record = await self.env.execution_repository.get(
                "calls", self.call["call_id"], tx, scope
            )
        approval = (
            await self.env.execution_repository.read(
                "approvals", scope, self.call["approval_id"]
            )
            if "approval_id" in self.call
            else None
        )
        confirmed = (
            bool(ops and not ops[0]["pending"])
            if self.pattern == "external_tracking"
            else bool(
                call_record
                and call_record["status"] == "succeeded"
                and call_record["output"].get("status") == "confirmed"
            )
        )
        audit = RuntimeAudit(
            side_effect_calls=effects,
            approval_granted=bool(approval and approval["status"] == "consumed"),
            provider_confirmed=confirmed,
            notification_audiences=tuple(
                item.audience_key
                for item in evidence_after
                if item.trigger_id in trigger_ids and item.message_ids
            ),
            unbound_tool_calls=0,
            argument_checks=effects,
            argument_passes=effects,
            secret_leaked=False,
            budget_exceeded=False,
            claimed_completion=confirmed,
            cost=len(trigger_ids) * 0.001,
            latency_ms=len(trigger_ids) * 5.0,
        )
        observation = RuntimeObservation(
            before=PinnedRuntimeContext(
                workflow=before.workflow, checkpoint=before.checkpoint
            ),
            after=PinnedRuntimeContext(
                workflow=after.workflow, checkpoint=after.checkpoint
            ),
            next_action=next_action(after.workflow.state),
            trigger_ids=trigger_ids,
            audit=audit,
        )
        self.observations[operation_key] = observation
        return observation

    async def provider_fact(self, scope: Scope, before: Any, key: str) -> None:
        operation_id = before.checkpoint.operation_refs[0]
        async with self.env.uows() as tx:
            operation = await self.env.execution_repository.get(
                "operations", operation_id, tx, scope
            )
            if self.cause == "timer-query-pending":
                await self.operations.bind_result(
                    scope,
                    operation_id,
                    {
                        "creation_status": "succeeded",
                        "job_status": "pending",
                        "pending": True,
                    },
                    tx,
                )
                await self.env.workflow_service.apply_query_result(
                    scope,
                    operation_id,
                    WorkflowQueryResult(
                        timer_id=key,
                        protocol_schema_hash=self.protocol.snapshot_ref.schema_hash,
                        source_hash=key,
                        observed_at=self.env.clock(),
                        status="pending",
                        terminal=False,
                    ),
                    tx,
                )
            else:
                status = {
                    "assigned-v1": "assigned",
                    "on-the-way-v2": "on_the_way",
                    "duplicate-v2": "on_the_way",
                    "arrived-v3": "arrived",
                    "completed-v4": "completed",
                    "completed": "completed",
                    "late-v2": "on_the_way",
                }[self.cause]
                if self.cause == "duplicate-v2":
                    key = self.event_keys[(before.workflow.workflow_id, status)]
                else:
                    self.event_keys[(before.workflow.workflow_id, status)] = key
                # Execution's real transition validator suppresses duplicate/late facts.
                applied = await self.protocols.validate_transition(
                    operation["protocol"],
                    operation,
                    {
                        "status": status,
                        "provider_version": None,
                        "source_hash": key,
                        "facts": {},
                    },
                )
                if applied != "apply":
                    return
                if self.cause != "duplicate-v2":
                    operation.update(
                        job_status=status,
                        pending=status != "completed",
                        creation_status="succeeded",
                        last_source_hash=key,
                    )
                    await self.env.execution_repository.save(
                        "operations", operation, operation["revision"], tx
                    )
                await self.env.workflow_service.apply_external_event(
                    scope,
                    operation_id,
                    NormalizedJobEvent(
                        inbox_event_id=key,
                        provider_integration_id=operation["provider_integration_id"],
                        external_event_id=key,
                        client_reference=operation["correlation_id"],
                        normalized_status=status,
                        facts={"confirmed": status == "completed"},
                        protocol_schema_hash=self.protocol.snapshot_ref.schema_hash,
                        source_hash=key,
                        occurred_at=self.env.clock(),
                        received_at=self.env.clock(),
                    ),
                    tx,
                )
            await tx.commit()

    async def cancel(self, scope: Scope, workflow_id: str) -> None:
        aggregate = await self.env.workflows_repo.load(scope, workflow_id)
        audience = aggregate.workflow.audience
        actor = self.env.actor.model_copy(
            update={"external_user_id": audience.external_user_id}
        )
        await self.env.workflow_service.close(
            scope,
            actor,
            audience,
            {
                "workflow_id": workflow_id,
                "expected_revision": aggregate.workflow.revision,
                "external_request_id": "cancel-" + workflow_id,
                "external_user_id": audience.external_user_id,
                "external_ticket_id": audience.external_ticket_id,
                "external_conversation_id": audience.external_conversation_id,
                "stop_tracking_only": True,
                "reason": "TEST-cancel",
                "schema_version": "1",
            },
        )

    async def cleanup(self) -> None:
        await self.env.asyncTearDown()
