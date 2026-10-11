# -*- coding: utf-8 -*-
"""Phase-C SQL and Execution-boundary tests for Registry protocols."""

from __future__ import annotations

from datetime import UTC, datetime
import json
from pathlib import Path
import unittest

from sqlalchemy import create_engine
from sqlalchemy.dialects import postgresql, sqlite
from sqlalchemy.schema import CreateTable

from agentscope.app.workforce.contracts import (
    ActorContext,
    ProviderEventEnvelope,
    Scope,
    WorkforceContractError,
    WorkforceErrorCode,
)
from agentscope.app.workforce.execution.external_operations import (
    ExecutionProtocolAdapter,
)
from agentscope.app.workforce.foundation import (
    SqlAlchemyUnitOfWorkFactory,
)
from agentscope.app.workforce.registry.event_protocols import (
    AsyncToolProtocol,
    SqlAsyncProtocolProvider,
)
from agentscope.app.workforce.registry.event_protocols._tables import (
    async_protocol_heads,
    async_protocol_versions,
    metadata,
)


NOW = datetime(2026, 10, 11, 10, 0, tzinfo=UTC)


class SyncAsyncSession:
    """Async facade for deterministic repository tests without a DB driver."""

    def __init__(self, engine):
        self.bind = engine
        self.connection = engine.connect()
        self.commits = 0
        self.rollbacks = 0

    async def execute(self, statement, params=None):
        if params is None:
            return self.connection.execute(statement)
        return self.connection.execute(statement, params)

    async def scalar(self, statement, params=None):
        result = await self.execute(statement, params)
        return result.scalar()

    async def commit(self):
        self.connection.commit()
        self.commits += 1

    async def rollback(self):
        self.connection.rollback()
        self.rollbacks += 1

    async def close(self):
        self.connection.close()

    def get_bind(self):
        return self.bind


class ProtocolSqlSchemaTests(unittest.TestCase):
    def test_tables_compile_and_expose_database_uniqueness(self):
        for dialect in (postgresql.dialect(), sqlite.dialect()):
            for table in (async_protocol_versions, async_protocol_heads):
                ddl = str(CreateTable(table).compile(dialect=dialect))
                self.assertIn(table.name, ddl)
        version_constraints = {
            constraint.name
            for constraint in async_protocol_versions.constraints
        }
        head_constraints = {
            constraint.name for constraint in async_protocol_heads.constraints
        }
        self.assertIn(
            "uq_wf_proto_version_identity",
            version_constraints,
        )
        self.assertIn("uq_wf_proto_head_scope_tool", head_constraints)
        self.assertIn(
            "fk_wf_proto_head_current_version",
            head_constraints,
        )


class ProtocolSqlRepositoryTests(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        sample_path = (
            Path(__file__).resolve().parents[4]
            / "docs/workforce/handoffs/nguyen-phuong-dong"
            / "phase_a_samples.json"
        )
        samples = json.loads(sample_path.read_text(encoding="utf-8"))
        self.protocol = AsyncToolProtocol.model_validate(
            samples["protocols"]["provider_event"],
        )
        self.event = ProviderEventEnvelope.model_validate(
            samples["provider_event"],
        )
        self.scope = Scope(
            tenant_id="tenant-1",
            domain_id="domain-1",
            area_id="area-1",
            manager_account_id="manager-1",
        )
        self.actor = ActorContext(
            kind="partner",
            actor_id="provider-demo",
            partner_client_id="provider-client",
            credential_id="provider-credential",
            credential_purpose="provider_events",
            authentication_source="phase_c_test",
        )
        self.engine = create_engine("sqlite://")
        metadata.create_all(self.engine)
        self.sessions = []

        def sessions():
            session = SyncAsyncSession(self.engine)
            self.sessions.append(session)
            return session

        self.uows = SqlAlchemyUnitOfWorkFactory(sessions)
        self.provider = SqlAsyncProtocolProvider(self.uows)

        async def load_context(actor, envelope):
            self.assertEqual(self.actor, actor)
            self.assertEqual(self.event, envelope)
            return (
                self.scope.tenant_id,
                "provider-demo",
                "inbox-1",
                NOW,
            )

        self.service = self.provider.bind(self.scope, load_context)

    def tearDown(self):
        self.engine.dispose()

    async def test_publish_disable_revision_and_exact_old_pin(self):
        original = await self.service.publish(self.protocol)
        self.assertEqual(
            original,
            await self.service.get_snapshot(
                self.scope,
                self.protocol.tool_version_id,
            ),
        )
        await self.service.publish(self.protocol)
        await self.service.set_enabled(
            original.tool_version_id,
            False,
            original,
        )
        with self.assertRaises(PermissionError):
            await self.service.get_snapshot(
                self.scope,
                original.tool_version_id,
            )

        revised = AsyncToolProtocol.model_validate(
            self.protocol.model_dump()
            | {
                "protocol_version": "2",
                "timeout_seconds": 7200,
            },
        )
        current = await self.service.publish(revised, original)
        with self.assertRaises(PermissionError):
            await self.service.get_snapshot(
                self.scope,
                current.tool_version_id,
            )
        self.assertEqual(
            original,
            (await self.service.get_detailed_snapshot(original)).snapshot_ref,
        )
        await self.service.set_enabled(
            current.tool_version_id,
            True,
            current,
        )
        self.assertEqual(
            current,
            await self.service.get_snapshot(
                self.scope,
                current.tool_version_id,
            ),
        )

    async def test_scope_version_and_revision_conflicts_fail_closed(self):
        original = await self.service.publish(self.protocol)
        conflicting_content = AsyncToolProtocol.model_validate(
            self.protocol.model_dump() | {"timeout_seconds": 7200},
        )
        with self.assertRaises(WorkforceContractError) as conflict:
            await self.service.publish(conflicting_content, original)
        self.assertEqual(
            WorkforceErrorCode.IDEMPOTENCY_CONFLICT,
            conflict.exception.code,
        )
        revised = AsyncToolProtocol.model_validate(
            self.protocol.model_dump() | {"protocol_version": "2"},
        )
        current = await self.service.publish(revised, original)
        stale = AsyncToolProtocol.model_validate(
            self.protocol.model_dump() | {"protocol_version": "3"},
        )
        with self.assertRaises(WorkforceContractError) as revision:
            await self.service.publish(stale, original)
        self.assertEqual(
            WorkforceErrorCode.REVISION_CONFLICT,
            revision.exception.code,
        )
        forged = current.model_copy(update={"capabilities": ("create",)})
        with self.assertRaises(ValueError):
            await self.provider.resolve_detail(self.scope, forged)
        other = self.scope.model_copy(update={"manager_account_id": "other"})
        with self.assertRaises(KeyError):
            await self.provider.resolve_detail(other, current)

    async def test_injected_uow_is_not_committed_by_repository(self):
        async with self.uows() as uow:
            await self.service.publish(self.protocol, uow=uow)
            self.assertEqual(0, uow.session.commits)
        with self.assertRaises(KeyError):
            await self.service.get_snapshot(
                self.scope,
                self.protocol.tool_version_id,
            )

        reference = await self.service.publish(self.protocol)
        async with self.uows() as uow:
            await self.service.set_enabled(
                reference.tool_version_id,
                False,
                reference,
                uow=uow,
            )
            self.assertEqual(0, uow.session.commits)
        self.assertEqual(
            reference,
            await self.service.get_snapshot(
                self.scope,
                reference.tool_version_id,
            ),
        )

    async def test_execution_adapter_uses_sql_registry_and_resolver(self):
        reference = await self.service.publish(self.protocol)
        adapter = ExecutionProtocolAdapter(
            self.service,
            self.provider.resolve_detail,
        )
        resolved = await adapter.get_snapshot(
            self.scope,
            self.protocol.tool_version_id,
        )
        self.assertEqual(
            reference.schema_hash,
            resolved["snapshot_ref"]["schema_hash"],
        )
        principal = {
            "tenant_id": self.scope.tenant_id,
            "provider_integration_id": "provider-demo",
            "actor_id": self.actor.actor_id,
            "purpose": "provider_events",
            "actor": self.actor.model_dump(mode="json"),
        }
        normalized = await adapter.normalize_verified_event(
            principal,
            resolved,
            self.event.model_dump(mode="json"),
            inbox_event_id="inbox-1",
            received_at=NOW.isoformat(),
        )
        self.assertEqual("on_the_way", normalized["status"])
        self.assertEqual({"eta_minutes": 20}, normalized["facts"])


if __name__ == "__main__":
    unittest.main()
