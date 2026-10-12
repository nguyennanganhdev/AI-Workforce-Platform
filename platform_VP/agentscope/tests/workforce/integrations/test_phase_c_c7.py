# -*- coding: utf-8 -*-
"""C7 migration, composition and application-boundary acceptance tests."""

from __future__ import annotations

from datetime import UTC, datetime
import importlib.util
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from alembic.migration import MigrationContext
from alembic.operations import Operations
from fastapi import APIRouter
from sqlalchemy import create_engine, inspect

from agentscope.app.message_bus import InMemoryMessageBus
from agentscope.app.workforce.contracts import Scope
from agentscope.app.workforce.contracts import ActorContext, RequestResult
from agentscope.app.workforce.execution import (
    get_metadata as execution_metadata,
)
from agentscope.app.workforce.lifecycle.async_evaluation import (
    get_metadata as evaluation_metadata,
)
from agentscope.app.workforce.orchestration import (
    get_metadata as orchestration_metadata,
)
from agentscope.app.workforce.registry.event_protocols._tables import (
    metadata as registry_metadata,
)
from agentscope.app.workforce.foundation import (
    DurableJob,
    JobOwnerKind,
)
from agentscope.app.workforce.integrations.async_runtime import (
    ApprovalContinuationCommandAdapter,
    OperationReconcileJobHandler,
    PHASE_C_JOB_TYPES,
    PhaseCRuntimeDependencies,
    WorkforceBootstrap,
    WorkforceRuntimeAssembly,
    build_phase_c_runtime,
    compose_phase_c_runtime,
)


class RuntimeMigrationTests(unittest.TestCase):
    def test_migration_matches_all_four_owner_metadata_bundles(self) -> None:
        path = (
            Path(__file__).resolve().parents[3]
            / "src/agentscope/app/storage/_sql/_alembic/versions"
            / "0010_workforce_runtime.py"
        )
        spec = importlib.util.spec_from_file_location(
            "wf_runtime_migration", path
        )
        self.assertIsNotNone(spec)
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)

        expected = set().union(
            registry_metadata.tables,
            execution_metadata().tables,
            orchestration_metadata().tables,
            evaluation_metadata().tables,
        )
        self.assertEqual(expected, set(module.metadata.tables))
        owner_metadata = (
            registry_metadata,
            execution_metadata(),
            orchestration_metadata(),
            evaluation_metadata(),
        )
        for bundle in owner_metadata:
            for name, owner_table in bundle.tables.items():
                migrated = module.metadata.tables[name]
                self.assertEqual(
                    list(owner_table.c.keys()),
                    list(migrated.c.keys()),
                    name,
                )
                self.assertEqual(
                    {item.name for item in owner_table.constraints},
                    {item.name for item in migrated.constraints},
                    name,
                )
                self.assertEqual(
                    {item.name for item in owner_table.indexes},
                    {item.name for item in migrated.indexes},
                    name,
                )

        engine = create_engine("sqlite://")
        with engine.begin() as connection:
            module.op = Operations(MigrationContext.configure(connection))
            module.upgrade()
            self.assertEqual(
                expected, set(inspect(connection).get_table_names())
            )
            module.downgrade()
            self.assertFalse(
                expected.intersection(inspect(connection).get_table_names())
            )
        engine.dispose()


class _Processor:
    async def handle_job(self, job):
        del job
        return {}


class _Handler:
    async def __call__(self, job):
        del job
        return {}


class _Reconciler:
    def __init__(self) -> None:
        self.calls = []

    async def reconcile(self, scope, operation_id, timer_id):
        self.calls.append((scope, operation_id, timer_id))
        return "applied"


class _Commands:
    def __init__(self) -> None:
        self.calls = []

    async def record_result(self, request_id, result, uow=None):
        self.calls.append(("result", request_id, result, uow))

    async def claim_or_read(
        self,
        actor,
        external_id,
        command_kind,
        target_ref,
        payload_hash,
        uow=None,
    ):
        self.calls.append(
            (
                "claim",
                actor,
                external_id,
                command_kind,
                target_ref,
                payload_hash,
                uow,
            )
        )
        return type("Claim", (), {"request_id": "continuation-row-1"})()


class _Workflows:
    def __init__(self) -> None:
        self.calls = []

    async def enqueue_trigger(self, scope, trigger, uow=None):
        self.calls.append((scope, trigger, uow))


class RuntimeCompositionTests(unittest.IsolatedAsyncioTestCase):
    async def test_production_builder_wires_all_phase_c_services(self) -> None:
        async def authenticate_api_key(value):
            del value
            return object()

        async def dependency():
            return object()

        async def tenant_resolver(actor, uow):
            del actor, uow
            return "tenant-1"

        async def approval_authorizer(actor, approval_id, body, uow=None):
            del actor, approval_id, body, uow
            return {}

        deps = PhaseCRuntimeDependencies(
            tenant_resolver=tenant_resolver,
            approval_authorizer=approval_authorizer,
            workflow_authorization=object(),
            leader_bootstrap_resolver=object(),
            leader=object(),
            runtime_authority=object(),
            tool_registry=object(),
            quote_provider=object(),
            hitl=object(),
            mcp=object(),
            operation_queries=object(),
            evaluation_runner=object(),
            customer_dependency=dependency,
            manager_dependency=dependency,
        )
        with TemporaryDirectory() as directory:
            database = Path(directory) / "production-builder.db"
            bootstrap = WorkforceBootstrap(
                database_url=(
                    f"sqlite+aiosqlite:///{database.as_posix()}"
                ),
                message_bus=InMemoryMessageBus(),
                authenticate_provider_api_key=authenticate_api_key,
                resolve_provider_signing_secret=lambda reference: b"s" * 48,
                runtime_factory=lambda foundation: build_phase_c_runtime(
                    foundation, deps
                ),
            )
        runtime = bootstrap._prepared.runtime
        self.assertEqual(2, len(runtime.routers))
        self.assertEqual(PHASE_C_JOB_TYPES, set(runtime.job_handlers))
        self.assertIs(runtime.services["uows"], bootstrap._prepared.uows)

    async def test_approved_result_and_wakeup_share_one_uow(self) -> None:
        commands = _Commands()
        workflows = _Workflows()
        adapter = ApprovalContinuationCommandAdapter(commands, workflows)
        scope = Scope(
            tenant_id="tenant-1",
            domain_id="domain-1",
            area_id="area-1",
            manager_account_id="manager-1",
        )
        actor = ActorContext(
            kind="partner",
            actor_id="customer-1",
            partner_client_id="partner-1",
            credential_id="key-1",
            credential_purpose="customer_api",
            external_user_id="resident-1",
            authentication_source="c7-test",
        )
        transaction = object()
        await adapter.record_approval_result(
            actor,
            {"scope": scope.model_dump(mode="json")},
            "approval-command-row-1",
            RequestResult(
                data={
                    "status": "approved",
                    "workflow_id": "workflow-1",
                    "approval_id": "approval-1",
                }
            ),
            uow=transaction,
        )
        self.assertEqual("result", commands.calls[0][0])
        self.assertEqual("claim", commands.calls[1][0])
        self.assertEqual(transaction, commands.calls[1][-1])
        self.assertEqual(transaction, workflows.calls[0][-1])
        cause = workflows.calls[0][1]["cause"]
        self.assertEqual("continuation-row-1", cause["request_id"])
        self.assertEqual("approval-1", cause["approval_id"])

    async def test_bootstrap_exposes_stable_router_and_one_uow(self) -> None:
        with TemporaryDirectory() as directory:
            database = Path(directory) / "runtime.db"
            seen = {}

            def factory(foundation):
                router = APIRouter()

                @router.get("/workforce-test")
                async def endpoint():
                    return {"ok": True}

                seen["uows"] = foundation.uows
                return WorkforceRuntimeAssembly(
                    services={"uows": foundation.uows},
                    routers=(router,),
                )

            bootstrap = WorkforceBootstrap(
                database_url=f"sqlite+aiosqlite:///{database.as_posix()}",
                message_bus=InMemoryMessageBus(),
                runtime_factory=factory,
            )
            self.assertEqual(1, len(bootstrap.routers))
            async with bootstrap:
                self.assertIs(seen["uows"], bootstrap.components.uows)
                self.assertIs(
                    bootstrap.components.runtime.services["uows"],
                    bootstrap.components.uows,
                )
                async with bootstrap.components.uows() as uow:
                    self.assertIsNotNone(uow.session)

    async def test_phase_c_registration_is_complete_and_scoped(self) -> None:
        foundation = object.__new__(type("Foundation", (), {}))
        foundation.uows = object()
        reconciler = _Reconciler()
        assembly = compose_phase_c_runtime(
            foundation,
            services={"uows": foundation.uows},
            routers=(object(), object()),
            provider_event_processor=_Processor(),
            workflow_continuation_handler=_Handler(),
            operation_reconciler=reconciler,
            evaluation_handler=_Handler(),
        )
        self.assertEqual(PHASE_C_JOB_TYPES, set(assembly.job_handlers))

        now = datetime.now(UTC)
        scope = Scope(
            tenant_id="tenant-1",
            domain_id="domain-1",
            area_id="area-1",
            manager_account_id="manager-1",
        )
        job = DurableJob(
            job_id="job-1",
            owner_kind=JobOwnerKind.SCOPE,
            scope=scope,
            tenant_id=scope.tenant_id,
            job_type="operation_reconcile",
            payload={"operation_id": "operation-1", "timer_id": "timer-1"},
            idempotency_key="timer-1",
            not_before=now,
            created_at=now,
            updated_at=now,
        )
        result = await OperationReconcileJobHandler(reconciler)(job)
        self.assertEqual("applied", result["status"])
        self.assertEqual(
            (scope, "operation-1", "timer-1"), reconciler.calls[0]
        )

    async def test_phase_c_registration_rejects_another_uow(self) -> None:
        foundation = object.__new__(type("Foundation", (), {}))
        foundation.uows = object()
        with self.assertRaisesRegex(ValueError, "foundation.uows"):
            compose_phase_c_runtime(
                foundation,
                services={"uows": object()},
                routers=(object(), object()),
                provider_event_processor=_Processor(),
                workflow_continuation_handler=_Handler(),
                operation_reconciler=_Reconciler(),
                evaluation_handler=_Handler(),
            )


if __name__ == "__main__":
    unittest.main()
