"""Shared-context bridge acceptance tests for partner workflow traffic."""

from __future__ import annotations

import json
import unittest
from datetime import UTC, datetime
from types import SimpleNamespace

from agentscope.app._workforce_policy import (
    BUSINESS_AGENT_EVIDENCE_POLICY,
    WORKFORCE_LEADER_PROMPT,
)
from agentscope.app.storage import (
    SharedTaskState,
    TeamSharedContextRecord,
)
from agentscope.app.workforce.contracts import (
    PartnerAudience,
    Scope,
    WorkflowRecord,
    WorkflowState,
)
from agentscope.app.workforce.foundation import DurableJob, JobOwnerKind
from agentscope.app.workforce.orchestration import SqlRuntimeContinuation
from agentscope.app.workforce.orchestration.workflows import (
    WorkflowAggregate,
    WorkflowPattern,
    WorkforceSharedContextProjector,
    projection_payload,
)
from agentscope.app.workforce.orchestration.workflows.phase_a import (
    AgentVersionPin,
    UsedBudget,
    WorkflowCheckpoint,
)


class _Context:
    def __init__(self, order: list[str], *, stale: bool = False) -> None:
        self.order = order
        self.stale = stale
        self.bindings: list[dict] = []
        self.events: list[dict] = []

    async def bind_scope(self, user_id, team_id, **scope):
        self.order.append("bind")
        self.bindings.append({"user_id": user_id, "team_id": team_id, **scope})

    async def append_event(self, **event):
        self.order.append("append")
        self.events.append(event)
        return SimpleNamespace(
            id=event["event_id"],
            task_id=event["task_id"],
            revision=4,
            stale=self.stale,
        )


class _Jobs:
    def __init__(self, order: list[str]) -> None:
        self.order = order
        self.calls: list[tuple] = []

    async def enqueue_trigger(self, *args):
        self.order.append("enqueue")
        self.calls.append(args)
        return "continuation-job"


class _WorkflowRepository:
    def __init__(self, aggregate: WorkflowAggregate) -> None:
        self.aggregate = aggregate

    async def load(self, scope, workflow_id):
        del scope
        if workflow_id != self.aggregate.workflow.workflow_id:
            raise KeyError(workflow_id)
        return self.aggregate


class _CheckpointRepository:
    def __init__(self, checkpoint: WorkflowCheckpoint) -> None:
        self.checkpoint = checkpoint

    async def load(self, scope, checkpoint_ref):
        del scope
        if checkpoint_ref != "checkpoint-1":
            raise KeyError(checkpoint_ref)
        return self.checkpoint


class _SharedStorage:
    def __init__(self, record: TeamSharedContextRecord) -> None:
        self.record = record

    async def get_team_shared_context(self, user_id, team_id):
        if user_id == self.record.user_id and team_id == self.record.team_id:
            return self.record
        return None


class _PreparedContext:
    def __init__(self, record: TeamSharedContextRecord) -> None:
        self.storage = _SharedStorage(record)
        self.calls: list[dict] = []

    async def prepare_packet(self, **kwargs):
        self.calls.append(kwargs)
        task_id = kwargs["task_id"]
        return (
            json.dumps(
                {
                    "schema": "agentscope.shared-context.v1",
                    "team_id": self.storage.record.team_id,
                    "revision": self.storage.record.state.revision,
                    "mode": "task",
                    "active_task_id": task_id,
                    "authoritative_state": {
                        "tasks": [
                            self.storage.record.state.tasks[task_id].model_dump(
                                mode="json",
                            ),
                        ],
                        "items": [],
                    },
                    "summary": None,
                    "history_omission": None,
                    "recent_events": [],
                },
            ),
            41,
        )


class _PacketModel:
    async def count_tokens(self, messages, tools):
        del messages, tools
        return 1


class _PacketModelResolver:
    async def resolve(self, scope, workflow, checkpoint):
        del scope, workflow, checkpoint
        return _PacketModel()


def _scope() -> Scope:
    return Scope(
        tenant_id="tenant-1",
        domain_id="domain-1",
        area_id="area-1",
        manager_account_id="manager-1",
    )


def _workflow(state: WorkflowState = WorkflowState.ACTIVE) -> WorkflowRecord:
    now = datetime.now(UTC)
    return WorkflowRecord(
        workflow_id="workflow-1",
        scope=_scope(),
        audience=PartnerAudience(
            partner_client_id="partner-1",
            external_user_id="customer-1",
            external_ticket_id="ticket-1",
            external_conversation_id="chat-1",
        ),
        conversation_id="conversation-1",
        ticket_id="internal-ticket-1",
        route_id="route-1",
        route_revision=1,
        state=state,
        revision=2,
        group_id="runtime-group-1",
        created_at=now,
        updated_at=now,
    )


def _job(payload: dict[str, object]) -> DurableJob:
    now = datetime.now(UTC)
    scope = _scope()
    return DurableJob(
        job_id="projection-job-1",
        owner_kind=JobOwnerKind.SCOPE,
        scope=scope,
        tenant_id=scope.tenant_id,
        job_type="workforce.shared_context.project",
        payload=payload,
        idempotency_key="projection-1",
        not_before=now,
        created_at=now,
        updated_at=now,
    )


class PartnerSharedContextProjectionTests(unittest.IsolatedAsyncioTestCase):
    async def test_projection_precedes_durable_leader_continuation(self) -> None:
        order: list[str] = []
        context = _Context(order)
        jobs = _Jobs(order)
        projector = WorkforceSharedContextProjector(context, jobs)
        payload = projection_payload(
            _workflow(),
            event_id="request-1",
            kind="customer_message",
            content="A domain-neutral customer request",
            artifact_refs=("asset-1",),
        )
        payload["continuation"] = {
            "trigger_id": "trigger-1",
            "workflow_id": "workflow-1",
            "cause": {
                "kind": "request",
                "request_id": "request-1",
                "asset_ids": ["asset-1"],
            },
        }

        result = await projector(_job(payload))

        self.assertEqual(["bind", "append", "enqueue"], order)
        self.assertEqual("runtime-group-1", context.bindings[0]["team_id"])
        self.assertEqual("workflow-1", context.events[0]["task_id"])
        self.assertEqual("customer_message", context.events[0]["kind"])
        self.assertEqual("workflow-1", jobs.calls[0][1]["workflow_id"])
        self.assertEqual("request-1", result["event_id"])

    async def test_waiting_user_message_becomes_one_pending_question(self) -> None:
        order: list[str] = []
        context = _Context(order)
        projector = WorkforceSharedContextProjector(context, _Jobs(order))
        payload = projection_payload(
            _workflow(WorkflowState.AWAITING_USER),
            event_id="assistant-question-1",
            kind="customer_reply",
            content="Please clarify the missing requirement.",
        )

        await projector(_job(payload))

        event = context.events[0]
        self.assertEqual("requires_user_input", event["kind"])
        self.assertEqual("waiting_user", event["delta"].status)
        self.assertEqual("workflow-1", event["thread_id"])
        self.assertEqual("conversation-1", event["source_session_id"])

    async def test_invalid_continuation_cannot_write_partial_context(self) -> None:
        order: list[str] = []
        context = _Context(order)
        projector = WorkforceSharedContextProjector(context, _Jobs(order))
        payload = projection_payload(
            _workflow(),
            event_id="request-1",
            kind="customer_message",
            content="request",
        )
        payload["continuation"] = {
            "trigger_id": "trigger-1",
            "workflow_id": "another-workflow",
            "cause": {"kind": "request", "request_id": "request-1"},
        }

        with self.assertRaisesRegex(ValueError, "workflow mismatch"):
            await projector(_job(payload))

        self.assertEqual([], context.bindings)
        self.assertEqual([], context.events)

    async def test_stale_projection_never_schedules_a_leader_turn(self) -> None:
        order: list[str] = []
        context = _Context(order, stale=True)
        jobs = _Jobs(order)
        projector = WorkforceSharedContextProjector(context, jobs)
        payload = projection_payload(
            _workflow(),
            event_id="late-event-1",
            kind="external_event",
            content="A valid but obsolete provider result",
        )
        payload["continuation"] = {
            "trigger_id": "trigger-late-1",
            "workflow_id": "workflow-1",
            "cause": {
                "kind": "external_event",
                "cause_event_id": "late-event-1",
                "operation_id": "operation-1",
            },
        }

        result = await projector(_job(payload))

        self.assertEqual(["bind", "append"], order)
        self.assertEqual([], jobs.calls)
        self.assertTrue(result["stale"])

    async def test_runtime_loads_the_scoped_snapshot_for_partner_leader(self) -> None:
        workflow = _workflow()
        workflow = workflow.model_copy(
            update={"checkpoint_ref": "checkpoint-1", "version_pins": ("v1",)},
        )
        checkpoint = WorkflowCheckpoint(
            workflow_id=workflow.workflow_id,
            state_revision=workflow.revision,
            session_refs=("leader-session",),
            agent_version_pins=(AgentVersionPin(agent_id="leader", version_id="v1"),),
            shared_state_ref=workflow.group_id,
            used_budget=UsedBudget(
                model_turns=0,
                tool_calls=0,
                input_tokens=0,
                output_tokens=0,
            ),
        )
        aggregate = WorkflowAggregate(
            workflow=workflow,
            checkpoint=checkpoint,
            pattern=WorkflowPattern.INTERACTIVE,
        )
        shared = TeamSharedContextRecord(
            id=workflow.group_id,
            user_id=workflow.scope.manager_account_id,
            team_id=workflow.group_id,
            tenant_id=workflow.scope.tenant_id,
            domain_id=workflow.scope.domain_id,
            area_id=workflow.scope.area_id,
            manager_account_id=workflow.scope.manager_account_id,
            workflow_id=workflow.workflow_id,
        )
        shared.state.revision = 7
        shared.state.active_task_id = workflow.workflow_id
        shared.state.tasks[workflow.workflow_id] = SharedTaskState(
            id=workflow.workflow_id,
            objective="Generic ticket objective",
        )
        prepared_context = _PreparedContext(shared)
        runtime = SqlRuntimeContinuation(
            _WorkflowRepository(aggregate),
            _CheckpointRepository(checkpoint),
            object(),
            prepared_context,
            _PacketModelResolver(),
        )

        context = await runtime.load_pinned_context(
            workflow.scope,
            "checkpoint-1",
        )

        self.assertEqual(7, context.shared_context_revision)
        self.assertEqual(41, context.shared_context_tokens)
        self.assertEqual(workflow.workflow_id, prepared_context.calls[0]["task_id"])
        self.assertEqual(workflow.group_id, context.shared_context["team_id"])
        self.assertEqual(
            WORKFORCE_LEADER_PROMPT,
            context.leader_system_prompt,
        )
        self.assertEqual(
            BUSINESS_AGENT_EVIDENCE_POLICY,
            context.business_agent_evidence_policy,
        )
        self.assertEqual(
            workflow.workflow_id,
            context.shared_context["authoritative_state"]["tasks"][0]["id"],
        )


if __name__ == "__main__":
    unittest.main()
