"""Evaluation adapter over injected production workflow commands and evidence.

The driver uses the production LeaderTurnRunner/SqlRuntimeContinuation and
Execution gateway, with a mock model/provider and fixed clock. Lifecycle never
implements workflow transitions or supplies expected states to this driver.
"""

from typing import (
    Any,
    Awaitable,
    Callable,
    Dict,
    Literal,
    Mapping,
    Optional,
    Protocol,
    Set,
    Tuple,
)

from pydantic import Field, StrictBool, StrictInt
from sqlalchemy import update

from ...contracts import (
    EvaluationCaseResult,
    EvaluationSnapshot,
    EvaluationStatus,
    Scope,
    WorkforceModel,
)
from ...orchestration.workflows.phase_a import PinnedRuntimeContext
from ._evaluation import TurnEvidence
from ._repository import SqlEvaluationRepository, scoped
from ._tables import case_runs, steps
from ._validation import canonical_hash


class RuntimeAudit(WorkforceModel):
    """Required sanitized audit from Execution/provider and output inspection.

    These facts cannot be inferred from an approval cause or provider event.
    No arguments, message text, prompts, credentials or exception text belong
    here. Missing audit is a runner error, never an implicit successful check.
    """

    side_effect_calls: StrictInt = Field(ge=0)
    approval_granted: StrictBool
    provider_confirmed: StrictBool
    notification_audiences: Tuple[str, ...]
    unbound_tool_calls: StrictInt = Field(ge=0)
    argument_checks: StrictInt = Field(ge=0)
    argument_passes: StrictInt = Field(ge=0)
    secret_leaked: StrictBool
    budget_exceeded: StrictBool
    claimed_completion: StrictBool
    cost: float = Field(ge=0, allow_inf_nan=False)
    latency_ms: float = Field(ge=0, allow_inf_nan=False)


class RuntimeObservation(WorkforceModel):
    """Persisted before/after context and audit for one idempotent stimulus."""

    before: PinnedRuntimeContext
    after: PinnedRuntimeContext
    next_action: str
    trigger_ids: Tuple[str, ...]
    audit: RuntimeAudit


class RuntimeCaseDriver(Protocol):
    """Composition seam, not a second runtime or replacement shared runner port.

    open_case must only bootstrap/register a pinned, isolated workflow; no turn
    runs before Lifecycle binds its evidence writer. The bind callback must run
    inside the bootstrap UOW before its job becomes visible. On retry it returns the
    same workflow. apply uses operation_key as a durable idempotency key and
    returns the original observation after a crash/replay. It must drive real
    workflow commands, continuation, approval and Execution, not expected data.
    """

    async def open_case(
        self,
        scope: Scope,
        snapshot: EvaluationSnapshot,
        test_case: Mapping[str, Any],
        bind: Callable[[str, Any], Awaitable[None]],
    ) -> str: ...

    async def apply(
        self,
        scope: Scope,
        workflow_id: str,
        stimulus: Mapping[str, Any],
        operation_key: str,
    ) -> RuntimeObservation: ...

    async def cancel(self, scope: Scope, workflow_id: str) -> None: ...


class RuntimeEvaluationRunner:
    """Shared EvaluationRunnerPort adapter using committed C4 evidence.

    A per-case SQL association, per-stimulus observations and immutable result
    make retries reuse completed work. The driver owns stimulus recovery between
    a committed runtime turn and the observation write. No transaction spans a
    model/provider call. This adapter only permits isolated mock execution.
    """

    def __init__(
        self,
        repository: SqlEvaluationRepository,
        driver: Optional[RuntimeCaseDriver] = None,
    ) -> None:
        self.repository = repository
        self.driver = driver

    async def run_case(
        self,
        scope: Scope,
        version_snapshot: EvaluationSnapshot,
        test_case: Mapping[str, Any],
        execution_mode: Literal["mock", "production"],
    ) -> EvaluationCaseResult:
        snapshot = EvaluationSnapshot.model_validate(version_snapshot.model_dump())
        if snapshot.scope != scope:
            raise ValueError("EVALUATION_SCOPE_MISMATCH")
        if execution_mode != "mock" or (
            test_case.get("tool_mode"),
            test_case.get("clock_mode"),
        ) != ("mock", "fixed"):
            raise ValueError("ISOLATED_MOCK_EXECUTION_REQUIRED")
        if "turns" in test_case or "expected" in test_case:
            raise ValueError("EXPECTATIONS_MUST_NOT_REACH_RUNTIME")
        if canonical_hash(test_case["test_context"]) != snapshot.test_context_hash:
            raise ValueError("RUNTIME_TEST_CONTEXT_MISMATCH")
        case_id = test_case["case_id"]
        keys = {"snapshot_id": snapshot.snapshot_id, "case_id": case_id}
        input_hash = canonical_hash(
            {"snapshot": snapshot.model_dump(mode="json"), "case": dict(test_case)}
        )
        row = await self.repository.read(case_runs, scope, keys)
        if row is not None and row["input_hash"] != input_hash:
            raise ValueError("STALE_RUNTIME_CASE")
        if row is not None and row["cancelled"]:
            raise ValueError("RUNTIME_CASE_CANCELLED")
        completed = row is not None and row["result"] is not None
        if completed:
            assert row is not None
            if canonical_hash(row["result"]) != row["result_hash"]:
                raise ValueError("RUNTIME_RESULT_DRIFT")
            workflow_id = row["workflow_id"]
        else:
            if self.driver is None:
                raise ValueError("INCOMPLETE_RUNTIME_CASE")

            async def bind(workflow_id: str, uow: Any) -> None:
                await self.repository.put(
                    case_runs,
                    scope,
                    keys,
                    {
                        "workflow_id": workflow_id,
                        "input_hash": input_hash,
                    },
                    uow,
                )

            workflow_id = await self.driver.open_case(scope, snapshot, test_case, bind)
            binding = await self.repository.read(case_runs, scope, keys)
            if binding is None or binding["workflow_id"] != workflow_id:
                raise ValueError("UNREGISTERED_RUNTIME_CASE")
        turns = []
        used_triggers: Set[str] = set()
        for index, stimulus in enumerate(test_case["stimuli"]):
            step_keys = {**keys, "step_index": index}
            saved = await self.repository.read(steps, scope, step_keys)
            if saved is None:
                if completed:
                    raise ValueError("MISSING_RUNTIME_OBSERVATION")
                if self.driver is None:
                    raise ValueError("INCOMPLETE_RUNTIME_CASE")
                current = await self.repository.read(case_runs, scope, keys)
                if current is None or current["cancelled"]:
                    raise ValueError("RUNTIME_CASE_CANCELLED")
                operation_key = canonical_hash(
                    {"scope": scope.model_dump(), **step_keys, "input_hash": input_hash}
                )
                observation = RuntimeObservation.model_validate(
                    await self.driver.apply(scope, workflow_id, stimulus, operation_key)
                )
                data = observation.model_dump(mode="json")
                await self.repository.put(
                    steps,
                    scope,
                    step_keys,
                    {
                        "observation": data,
                        "content_hash": canonical_hash(data),
                    },
                )
            else:
                if canonical_hash(saved["observation"]) != saved["content_hash"]:
                    raise ValueError("RUNTIME_OBSERVATION_DRIFT")
                observation = RuntimeObservation.model_validate(saved["observation"])
            if used_triggers.intersection(observation.trigger_ids):
                raise ValueError("REUSED_RUNTIME_EVIDENCE")
            used_triggers.update(observation.trigger_ids)
            turns.append(
                await self._project(
                    scope,
                    snapshot,
                    workflow_id,
                    stimulus["cause"],
                    observation,
                    test_case["protocol_refs"],
                )
            )
        # Reject committed calls omitted from the returned observations.
        all_evidence = await self.repository.evidence(scope, workflow_id)
        if {item.trigger_id for item in all_evidence} != used_triggers:
            raise ValueError("UNACCOUNTED_RUNTIME_EVIDENCE")
        result = EvaluationCaseResult(
            case_id=case_id,
            status=EvaluationStatus.PASSED,
            metrics={"turns": [turn.model_dump(mode="json") for turn in turns]},
            tool_trace_ref=workflow_id,
        )
        data = result.model_dump(mode="json")
        if completed:
            if row is None or row["result"] != data:
                raise ValueError("RUNTIME_RESULT_EVIDENCE_MISMATCH")
            return result
        async with self.repository.uows() as tx:
            await tx.execute(
                update(case_runs)
                .where(
                    *scoped(case_runs, scope, keys),
                    case_runs.c.result.is_(None),
                    case_runs.c.cancelled.is_(False),
                )
                .values(result=data, result_hash=canonical_hash(data))
            )
            stored = await self.repository.read(case_runs, scope, keys, tx)
            if stored is None or stored["cancelled"] or stored["result"] != data:
                raise ValueError("IMMUTABLE_EVALUATION_CONFLICT")
            await tx.commit()
        return result

    async def _project(
        self,
        scope: Scope,
        snapshot: EvaluationSnapshot,
        workflow_id: str,
        cause: str,
        observation: RuntimeObservation,
        protocol_refs: Any,
    ) -> TurnEvidence:
        before, after = observation.before, observation.after
        for context in (before, after):
            workflow, checkpoint = context.workflow, context.checkpoint
            if (
                workflow.scope != scope
                or workflow.workflow_id != workflow_id
                or workflow.version_pins != (snapshot.candidate_version_id,)
                or [
                    (pin.agent_id, pin.version_id)
                    for pin in checkpoint.agent_version_pins
                ]
                != [(snapshot.agent_id, snapshot.candidate_version_id)]
                or sorted(pin.schema_hash for pin in checkpoint.protocol_pins)
                != sorted(snapshot.manifest.protocol_snapshot_hashes)
                or sorted(
                    (pin.model_dump(mode="json") for pin in checkpoint.protocol_pins),
                    key=lambda pin: pin["tool_version_id"],
                )
                != sorted(protocol_refs, key=lambda pin: pin["tool_version_id"])
            ):
                raise ValueError("RUNTIME_PIN_MISMATCH")
        if before.workflow.audience != after.workflow.audience:
            raise ValueError("RUNTIME_AUDIENCE_DRIFT")
        if len(set(observation.trigger_ids)) != len(observation.trigger_ids):
            raise ValueError("REUSED_RUNTIME_EVIDENCE")
        items = {
            item.trigger_id: item
            for item in await self.repository.evidence(scope, workflow_id)
        }
        if any(key not in items for key in observation.trigger_ids):
            raise ValueError("MISSING_COMMITTED_RUNTIME_EVIDENCE")
        committed = [items[key] for key in observation.trigger_ids]
        if committed and (
            committed[-1].after_state != after.workflow.state
            or committed[-1].next_action != observation.next_action
        ):
            raise ValueError("RUNTIME_RESULT_EVIDENCE_MISMATCH")
        audience = after.workflow.audience
        audience_key = audience.external_ticket_id or audience.external_conversation_id
        if any(
            item.audience_key != audience_key
            or item.before_revision < before.workflow.revision
            or item.after_revision > after.workflow.revision
            for item in committed
        ):
            raise ValueError("RUNTIME_EVIDENCE_CONTEXT_MISMATCH")
        deltas: Dict[str, int] = {}
        for field in ("model_turns", "tool_calls", "input_tokens", "output_tokens"):
            delta = getattr(after.checkpoint.used_budget, field) - getattr(
                before.checkpoint.used_budget, field
            )
            if delta < 0 or delta != sum(getattr(item, field) for item in committed):
                raise ValueError("RUNTIME_USAGE_EVIDENCE_MISMATCH")
            deltas[field] = delta
        if sum(item.new_tracking_records for item in committed) != len(
            set(after.checkpoint.operation_refs) - set(before.checkpoint.operation_refs)
        ):
            raise ValueError("RUNTIME_TRACKING_EVIDENCE_MISMATCH")
        audit = observation.audit
        if (
            audit.side_effect_calls > deltas["tool_calls"]
            or (
                audit.side_effect_calls
                and not any(
                    effect != "read"
                    for item in committed
                    for effect in item.checked_effects
                )
            )
            or any(item.model_turns and not item.checked_effects for item in committed)
        ):
            raise ValueError("MISSING_EXECUTION_GUARD_EVIDENCE")
        return TurnEvidence(
            cause=cause,
            workflow_state=after.workflow.state,
            next_action=observation.next_action,
            llm_calls=deltas["model_turns"],
            tracking_records=len(after.checkpoint.operation_refs),
            audience_key=audience_key,
            **audit.model_dump(),
        )

    async def cancel_case(self, scope: Scope, case_run_id: str) -> None:
        row = await self.repository.read(case_runs, scope, {"workflow_id": case_run_id})
        if row is None:
            raise KeyError("case not found in owner scope")
        if self.driver is None:
            raise ValueError("RUNTIME_DRIVER_REQUIRED")
        async with self.repository.uows() as tx:
            await tx.execute(
                update(case_runs)
                .where(*scoped(case_runs, scope, {"workflow_id": case_run_id}))
                .values(cancelled=True)
            )
            await tx.commit()
        await self.driver.cancel(scope, case_run_id)
