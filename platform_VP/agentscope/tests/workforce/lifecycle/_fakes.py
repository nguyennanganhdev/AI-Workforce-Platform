"""Test-only ports; production Lifecycle has no successful fake adapters."""

import asyncio
from typing import Any, Dict, Optional, Sequence, Tuple

from sqlalchemy import Column, JSON, MetaData, String, Table, insert

from agentscope.app.workforce.contracts import (
    AgentManifest,
    AgentSpec,
    AsyncProtocolSnapshotRef,
    BusinessProfile,
    EvaluationCaseResult,
    EvaluationStatus,
    ReuseAction,
    ReuseDecision,
    Scope,
    SideEffectPolicy,
    ToolBinding,
    ToolDescriptor,
    ToolEffect,
)
from agentscope.app.workforce.lifecycle import (
    LifecycleRepository,
    LifecycleService,
    ManifestValidator,
    SuiteCatalog,
)
from agentscope.app.workforce.lifecycle._graders import VIOLATIONS
from agentscope.app.workforce.lifecycle._models import LifecycleError, new_id
from agentscope.app.workforce.lifecycle.async_evaluation import lifecycle_suite

job_metadata = MetaData()
jobs_table = Table(
    "fake_jobs",
    job_metadata,
    Column("id", String, primary_key=True),
    Column("payload", JSON, nullable=False),
)


def scope(manager: str = "manager-A") -> Scope:
    return Scope(
        tenant_id="tenant",
        domain_id="domain",
        area_id="area",
        manager_account_id=manager,
    )


def manifest(
    name: str = "Hotel", capability: str = "lookup", external: bool = False
) -> AgentManifest:
    profile = BusinessProfile(
        profile_schema_version="1",
        objective=f"{name} business",
        responsibilities=("answer",),
        capabilities=(capability,),
        input_contract={"type": "object"},
        output_contract={"type": "object"},
        business_scope="managed business",
        execution_policy=(
            SideEffectPolicy.REQUIRE_APPROVAL
            if external
            else SideEffectPolicy.READ_ONLY
        ),
    )
    return AgentManifest(
        schema_version="1",
        business_profile=profile,
        spec=AgentSpec(
            agent_key=name.lower(),
            name=name,
            capabilities=(capability,),
            system_prompt="Answer safely",
            model_config_ref={
                "model_id": "model",
                "credential_ref": "credential",
            },
            tool_bindings=(
                ToolBinding(
                    tool_id=capability,
                    tool_version_id=capability,
                    schema_hash="schema-v1",
                    required_capability=capability,
                    selection_reason="Required capability",
                ),
            ),
            execution_policy={"require_approval": external},
        ),
        async_policy_ref="policy" if external else None,
        protocol_snapshot_hashes=("protocol-v1",) if external else (),
    )


class FakeIdentity:
    active = True

    async def check_scope_active(self, owner: Scope, uow: Any = None) -> None:
        if not self.active:
            raise LifecycleError("MANAGER_INACTIVE", 403)


class FakeRegistry:
    available = True
    schema_hash = "schema-v1"
    effect = ToolEffect.READ

    async def check_bindings(
        self, owner: Scope, bindings: Sequence[ToolBinding]
    ) -> None:
        pass

    async def get_tool_snapshot(
        self, owner: Scope, tool_version_id: str
    ) -> ToolDescriptor:
        return ToolDescriptor(
            tool_id=tool_version_id,
            tool_version_id=tool_version_id,
            source_kind="builtin",
            provider_tool_name=tool_version_id,
            llm_alias=tool_version_id,
            input_schema={"type": "object"},
            schema_hash=self.schema_hash,
            capabilities=(tool_version_id,),
            effect=self.effect,
            available=self.available,
        )


class FakeResources:
    valid = True
    revision = 1

    async def validate_resources(
        self, owner: Scope, value: AgentManifest
    ) -> Dict[str, Any]:
        return {
            "valid": self.valid,
            "revision": self.revision,
            "credential_id": "credential",
        }


class FakeProtocols:
    schema_hash = "protocol-v1"

    async def get_snapshot(
        self, owner: Scope, tool_version_id: str
    ) -> AsyncProtocolSnapshotRef:
        return AsyncProtocolSnapshotRef(
            protocol_id="protocol",
            protocol_version="1",
            schema_hash=self.schema_hash,
            tool_version_id=tool_version_id,
            capabilities=(tool_version_id,),
        )

    async def validate_capability_coverage(
        self, snapshot: AsyncProtocolSnapshotRef, required: Sequence[str]
    ) -> None:
        if not set(required).issubset(snapshot.capabilities):
            raise LifecycleError("ASYNC_CAPABILITY_COVERAGE")


class FakePolicies:
    def __init__(self) -> None:
        self.policy = {
            "schema_version": "1",
            "capabilities": ["lookup"],
            "event_types": ["status"],
            "required_facts": ["verified_status"],
            "completion_condition": "provider_terminal",
            "human_confirmation": True,
            "timeout_behavior": "status_query",
        }

    async def get_policy(
        self, owner: Scope, policy_ref: str
    ) -> Dict[str, Any]:
        return dict(self.policy)


class FakeJobs:
    fail = False

    async def enqueue(
        self,
        owner: Scope,
        job_type: str,
        payload: Dict[str, Any],
        idempotency_key: str,
        uow: Any = None,
        not_before: Any = None,
    ) -> str:
        job_id = new_id()
        await uow.session.execute(
            insert(jobs_table).values(id=job_id, payload=payload)
        )
        if self.fail:
            raise RuntimeError("enqueue failed")
        return job_id


def evidence(case: Dict[str, Any]) -> Dict[str, Any]:
    return {
        "violations": {key: 0 for key in VIOLATIONS},
        "tool_calls": [],
        "tool_checks": 0,
        "tool_checks_passed": 0,
        "cost": "0.01",
        "latency_ms": 5,
        "network_calls": 0,
        "live_provider_calls": 0,
        "mock_transport_verified": True,
        "turns": [
            dict(
                turn,
                llm_calls=(
                    0
                    if turn["trigger"] in ("none", "duplicate", "out_of_order")
                    else 1
                ),
                side_effect_calls=0,
                audience_verified=True,
                tracking_created=turn["operation_pending"],
            )
            for turn in case.get("turns", [])
        ],
        "create_calls": 1 if case.get("max_create_calls") else 0,
        "ticket_isolation_verified": True,
        "transcript": ["A safe, redacted response"],
    }


class FakeRunner:
    def __init__(self) -> None:
        self.calls = []
        self.results = {}
        self.crash_case: Optional[str] = None
        self.mutate = None
        self.cancelled = []

    async def run_case(
        self, owner: Scope, snapshot: Any, case: Dict[str, Any], mode: str
    ) -> EvaluationCaseResult:
        assert mode == "mock"
        assert case["test_context"]["execution_mode"] == "mock"
        if self.crash_case == case["case_id"]:
            self.crash_case = None
            raise asyncio.CancelledError()
        self.calls.append(
            (case["case_id"], case["case_run_id"], case["sandbox_namespace"])
        )
        if case["case_run_id"] not in self.results:
            metrics = evidence(case)
            if self.mutate:
                self.mutate(case, metrics)
            self.results[case["case_run_id"]] = EvaluationCaseResult(
                case_id=case["case_id"],
                status=EvaluationStatus.PASSED,
                metrics=metrics,
            )
        return self.results[case["case_run_id"]]

    async def cancel_case(self, owner: Scope, case_run_id: str) -> None:
        self.cancelled.append(case_run_id)


class FakeUsage:
    async def get_version_references(
        self, owner: Scope, version_id: str
    ) -> Tuple[Dict[str, Any], ...]:
        return (
            {
                "workflow_id": "waiting-ticket",
                "version_id": version_id,
                "state": "waiting_external_event",
            },
        )


class Harness:
    def __init__(self, factory: Any) -> None:
        self.registry = FakeRegistry()
        self.resources = FakeResources()
        self.protocols = FakeProtocols()
        self.policies = FakePolicies()
        self.identity = FakeIdentity()
        self.jobs = FakeJobs()
        self.runner = FakeRunner()
        self.service = LifecycleService(
            LifecycleRepository(factory),
            ManifestValidator(
                self.registry, self.resources, self.protocols, self.policies
            ),
            self.identity,
            self.jobs,
            self.runner,
            SuiteCatalog([lifecycle_suite()]),
            FakeUsage(),
            runtime_profile={"version": "runtime-v1"},
            peer_fixtures={"peer": "mock-v1"},
            redact=lambda data: data,
        )

    async def draft(
        self,
        value: Optional[AgentManifest] = None,
        owner: Optional[Scope] = None,
        batch_id: Optional[str] = None,
    ) -> Any:
        value, owner = value or manifest(), owner or scope()
        check = await self.service.find_candidates(
            owner, value.business_profile
        )
        decision = ReuseDecision(
            agent_key=value.spec.agent_key,
            action=ReuseAction.CREATE,
            reuse_check_id=check.reuse_check_id,
            reason="Create missing business",
            expected_catalog_revision=check.agent_catalog_revision,
        )
        return await self.service.create_draft(
            owner, value, decision, batch_id
        )

    async def evaluated(
        self, draft: Any, owner: Optional[Scope] = None
    ) -> Any:
        owner = owner or scope()
        record = await self.service.start_evaluation(
            owner,
            draft.draft_id,
            draft.revision,
            "lifecycle-patterns-v1",
            new_id(),
        )
        return await self.service.run_evaluation(
            owner, record.report.evaluation_id
        )
