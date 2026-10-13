"""TEST ONLY: wire real NPD fake ports and PHH schemas into Execution."""

import importlib.util
import json
from pathlib import Path

from sqlalchemy import insert, select

from agentscope.app.workforce.contracts import (
    ActorContext,
    NormalizedJobEvent,
    Scope,
    WorkflowRecord,
)
from agentscope.app.workforce.execution.external_operations import (
    ExecutionProtocolAdapter,
)
from agentscope.app.workforce.execution.provider_events import (
    WorkflowEventAdapter,
)
from agentscope.app.workforce.execution._utils import digest, freeze, value
from agentscope.app.workforce.foundation.event_delivery import DurableJob
from agentscope.app.workforce.orchestration.workflows.phase_a import (
    ExternalEventCause,
    TimerCause,
    WorkflowTrigger,
)
from agentscope.app.workforce.registry.event_protocols import AsyncToolProtocol
from execution_fakes import PROVIDER, SCOPE_A, test_events

ROOT = Path(__file__).resolve().parents[3]
SAMPLES = ROOT / "docs/workforce/handoffs"
_spec = importlib.util.spec_from_file_location(
    "npd_execution_consumer_fake",
    ROOT / "tests/workforce/registry/event_protocols/fakes.py",
)
_module = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_module)
FakeAsyncProtocolPort = _module.FakeAsyncProtocolPort


def sample_protocol(mode="snapshot"):
    samples = json.loads(
        (SAMPLES / "nguyen-phuong-dong/phase_a_samples.json").read_text(
            encoding="utf-8"
        )
    )
    config = samples["protocols"]["provider_event"]
    config.update(
        tool_version_id="hotel.book.v1",
        provider_integration_id=PROVIDER["provider_integration_id"],
        external_job_id_field="external_job_id",
        status_query_tool_version_id="technical.status.v1",
        event_mode=mode,
    )
    return AsyncToolProtocol.model_validate(config)


class TypedWorkflow:
    """Only an atomic test sink, not a replacement Workflow service."""

    def __init__(self, env):
        self.env, self.seen = env, []
        self.query_seen = []
        self.wrong_workflow = False
        self.wrong_audience = False
        self.wrong_group = False

    async def apply_external_event(
        self, scope, operation_ref, event, uow=None
    ):
        assert isinstance(scope, Scope)
        assert isinstance(operation_ref, str)
        assert isinstance(event, NormalizedJobEvent)
        op = await self.env.repo.get("operations", operation_ref, uow, scope)
        cause = ExternalEventCause(
            kind="external_event",
            cause_event_id=event.inbox_event_id,
            operation_id=operation_ref,
        )
        trigger = WorkflowTrigger(
            trigger_id="trigger-" + event.inbox_event_id,
            workflow_id=op["workflow_id"],
            cause=cause,
        )
        await self.env.workflow.apply_external_event(
            value(scope),
            op,
            {
                "inbox_event_id": event.inbox_event_id,
                "status": event.normalized_status,
            },
            uow,
        )
        self.seen.append((event, trigger))
        return self.record(scope, op)

    async def apply_query_result(self, scope, operation_ref, event, uow=None):
        op = await self.env.repo.get("operations", operation_ref, uow, scope)
        trigger = WorkflowTrigger(
            trigger_id="trigger-" + event["timer_id"],
            workflow_id=op["workflow_id"],
            cause=TimerCause(kind="timer", timer_id=event["timer_id"]),
        )
        assert "inbox_event_id" not in event
        await self.env.workflow.apply_external_event(
            value(scope), op, event, uow
        )
        self.query_seen.append((event, trigger))
        return self.record(scope, op)

    def record(self, scope, op):
        samples = json.loads(
            (SAMPLES / "phan-huy-hoang/phase_a/samples.json").read_text(
                encoding="utf-8"
            )
        )
        record = samples["models"]["WorkflowRecord"]
        record.update(
            scope=value(scope),
            audience=op["audience_ref"],
            workflow_id="workflow-WRONG"
            if self.wrong_workflow
            else op["workflow_id"],
            conversation_id=op["conversation_id"],
            group_id=op["group_id"],
            state="closed"
            if op["workflow_id"] in self.env.workflow.closed
            else "waiting_external_event",
        )
        if self.wrong_audience:
            record["audience"] = {
                **record["audience"],
                "external_user_id": "OTHER-USER",
            }
        if self.wrong_group:
            record["group_id"] = "group-OTHER"
        return WorkflowRecord.model_validate(record)


async def wire_protocols(env, mode="snapshot"):
    config = sample_protocol(mode)
    actor = ActorContext(
        kind="partner",
        actor_id=PROVIDER["actor_id"],
        partner_client_id="provider-client",
        credential_id="TEST-ONLY-PROVIDER",
        credential_purpose="provider_events",
        authentication_source="verified_test_fixture",
    )
    principal = {**PROVIDER, "actor": value(actor)}
    configs = [config]

    def factory(context):
        return FakeAsyncProtocolPort(
            context["scope"],
            configs,
            context["actor"],
            context["provider_integration_id"],
            context["inbox_event_id"],
            context["received_at"],
        )

    port = factory(
        {
            "scope": Scope.model_validate(SCOPE_A),
            "actor": actor,
            "provider_integration_id": config.provider_integration_id,
            "inbox_event_id": "placeholder",
            "received_at": env.clock(),
        }
    )

    async def detail(scope, ref):
        assert scope == Scope.model_validate(SCOPE_A)
        return next(c for c in configs if c.snapshot_ref == ref)

    adapter = ExecutionProtocolAdapter(port, detail, factory)
    env.descriptor["async_protocol_hash"] = config.snapshot_ref.schema_hash
    env.protocols = env.gateway.protocols = env.ingress.protocols = adapter

    async def assigned(arguments, output):
        output["status"] = "assigned"

    env.provider.after_write = assigned
    base_authenticate = env.auth.authenticate

    async def authenticate(raw, headers):
        await base_authenticate(raw, headers)
        return freeze(principal)

    env.auth.authenticate = authenticate
    typed_workflow = TypedWorkflow(env)
    workflow_adapter = WorkflowEventAdapter(
        env.repo, typed_workflow, query_sink=typed_workflow.apply_query_result
    )
    env.processor.workflow = workflow_adapter
    return config, principal, port, configs, typed_workflow, workflow_adapter


class JobEnqueueRepository:
    """SQL test double for enqueue only, not a worker repository."""

    def __init__(self, fail=False):
        self.fail = fail

    async def enqueue_once(self, job, uow=None):
        assert uow is not None
        key = "shared-job-" + digest(
            {
                "owner_kind": job.owner_kind,
                "tenant_id": job.tenant_id,
                "integration": job.provider_integration_id,
                "scope": value(job.scope),
                "key": job.idempotency_key,
            }
        )
        result = await uow.execute(
            select(test_events).where(test_events.c.id == key)
        )
        row = result.mappings().first()
        if row is not None:
            return DurableJob.model_validate(row["payload"])
        await uow.execute(
            insert(test_events).values(id=key, payload=value(job))
        )
        if self.fail:
            raise RuntimeError("TEST enqueue failure after insert")
        return job
