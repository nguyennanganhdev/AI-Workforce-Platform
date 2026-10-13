# -*- coding: utf-8 -*-
"""Phase-C tests that do not require a live PostgreSQL service."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
import hashlib
import hmac
import importlib.util
from pathlib import Path
import unittest

from alembic.migration import MigrationContext
from alembic.operations import Operations
from sqlalchemy import Column, MetaData, String, Table, create_engine, inspect
from sqlalchemy.dialects import postgresql, sqlite
from sqlalchemy.schema import CreateTable

from agentscope.app.workforce.contracts import (
    ActorContext,
    CredentialPurpose,
    PartnerAudience,
    PartnerOperation,
    Scope,
    VerifiedProviderContext,
)
from agentscope.app.workforce.foundation import (
    DurableJobService,
    HmacProviderAuth,
    SqlAlchemyUnitOfWork,
    SqlAlchemyUnitOfWorkFactory,
    SqlDurableJobRepository,
    SqlIdentityPort,
    SqlPartnerRoutingPort,
)
from agentscope.app.workforce.foundation._provider_auth import (
    ProviderCredentialSnapshot,
)
from agentscope.app.workforce.foundation._tables import (
    durable_jobs,
    manager_memberships,
    partner_manager_routes,
    provider_credentials,
    metadata as foundation_metadata,
)


NOW = datetime(2026, 10, 11, 9, 0, tzinfo=UTC)
SECRET = b"s" * 48


class FakeSession:
    def __init__(self) -> None:
        self.commits = 0
        self.rollbacks = 0
        self.closes = 0

    async def commit(self) -> None:
        self.commits += 1

    async def rollback(self) -> None:
        self.rollbacks += 1

    async def close(self) -> None:
        self.closes += 1

    def get_bind(self):
        return object()


class SyncAsyncSession:
    """Tiny async facade used to exercise SQL repositories without a driver."""

    def __init__(self, engine):
        self.bind = engine
        self.connection = engine.connect()

    async def execute(self, statement, params=None):
        if params is None:
            return self.connection.execute(statement)
        return self.connection.execute(statement, params)

    async def scalar(self, statement, params=None):
        result = await self.execute(statement, params)
        return result.scalar()

    async def commit(self):
        self.connection.commit()

    async def rollback(self):
        self.connection.rollback()

    async def close(self):
        self.connection.close()

    def get_bind(self):
        return self.bind


@dataclass(frozen=True)
class ApiPrincipal:
    key_id: str = "api-credential-1"
    tenant_id: str = "tenant-1"
    client_id: str = "partner-1"


class FakeCredentials:
    def __init__(self) -> None:
        self.active = True

    async def get_active(self, api_id, signing_id, uow=None):
        del uow
        if (
            not self.active
            or api_id != "api-credential-1"
            or signing_id != "signing-1"
        ):
            return None
        return ProviderCredentialSnapshot(
            credential_id="provider-credential-1",
            api_credential_id=api_id,
            signing_key_id=signing_id,
            provider_integration_id="provider-1",
            tenant_id="tenant-1",
            partner_client_id="partner-1",
            secret_ref="secret/provider-1/signing-1",
            purpose="provider_events",
            allowed_operations=(
                "publish_job_event",
                "read_event_receipt",
            ),
            expires_at=NOW + timedelta(days=1),
        )


class UnitOfWorkTests(unittest.IsolatedAsyncioTestCase):
    async def test_callback_runs_only_after_explicit_commit(self):
        session = FakeSession()
        calls = []
        async with SqlAlchemyUnitOfWork(lambda: session) as uow:
            uow.add_after_commit(lambda: calls.append("committed"))
            self.assertEqual([], calls)
            await uow.commit()
            self.assertEqual(["committed"], calls)
        self.assertEqual(1, session.commits)
        self.assertEqual(0, session.rollbacks)
        self.assertEqual(1, session.closes)

    async def test_context_without_commit_rolls_back_and_drops_callback(self):
        session = FakeSession()
        calls = []
        async with SqlAlchemyUnitOfWork(lambda: session) as uow:
            uow.add_after_commit(lambda: calls.append("must-not-run"))
        self.assertEqual([], calls)
        self.assertEqual(1, session.rollbacks)
        self.assertEqual(1, session.closes)


class FoundationSchemaTests(unittest.TestCase):
    def test_foundation_tables_compile_for_postgres_and_sqlite(self):
        tables = (
            manager_memberships,
            partner_manager_routes,
            provider_credentials,
            durable_jobs,
        )
        for dialect in (postgresql.dialect(), sqlite.dialect()):
            for table in tables:
                ddl = str(CreateTable(table).compile(dialect=dialect))
                self.assertIn(table.name, ddl)

    def test_job_and_route_uniqueness_are_database_constraints(self):
        job_constraints = {item.name for item in durable_jobs.constraints}
        route_constraints = {
            item.name for item in partner_manager_routes.constraints
        }
        self.assertIn("uq_wf_job_owner_idempotency", job_constraints)
        self.assertIn("uq_wf_route_client_management_ref", route_constraints)

    def test_migration_upgrades_and_downgrades_on_sqlite(self):
        engine = create_engine("sqlite://")
        prerequisites = MetaData()
        Table(
            "auth_users",
            prerequisites,
            Column("id", String(255), primary_key=True),
            Column("tenant_id", String(255), nullable=False),
            Column("domain_id", String(64)),
            Column("area_id", String(64)),
            Column("role", String(32), nullable=False),
        )
        for name in ("business_domains", "areas", "partner_api_clients"):
            Table(
                name,
                prerequisites,
                Column("id", String(255), primary_key=True),
            )
        Table(
            "partner_api_credentials",
            prerequisites,
            Column("id", String(255), primary_key=True),
        )
        migration_path = (
            Path(__file__).resolve().parents[4]
            / "src/agentscope/app/storage/_sql/_alembic/versions"
            / "0009_workforce_foundation.py"
        )
        spec = importlib.util.spec_from_file_location(
            "workforce_foundation_migration",
            migration_path,
        )
        self.assertIsNotNone(spec)
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        with engine.begin() as connection:
            prerequisites.create_all(connection)
            connection.execute(
                prerequisites.tables["auth_users"].insert().values(
                    id="manager-1",
                    tenant_id="tenant-1",
                    domain_id="domain-1",
                    area_id="area-1",
                    role="AREA_MANAGER",
                ),
            )
            module.op = Operations(MigrationContext.configure(connection))
            module.upgrade()
            names = set(inspect(connection).get_table_names())
            self.assertIn("wf_durable_jobs", names)
            pending = connection.exec_driver_sql(
                "SELECT status FROM wf_manager_memberships",
            ).scalar_one()
            self.assertEqual("pending_verification", pending)
            module.downgrade()
            names = set(inspect(connection).get_table_names())
            self.assertNotIn("wf_durable_jobs", names)


class SqlRepositoryTests(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        self.engine = create_engine("sqlite://")
        external_metadata = MetaData()
        self.domains = Table(
            "business_domains",
            external_metadata,
            Column("id", String(64), primary_key=True),
            Column("tenant_id", String(255), nullable=False),
            Column("status", String(32), nullable=False),
        )
        self.areas = Table(
            "areas",
            external_metadata,
            Column("id", String(64), primary_key=True),
            Column("domain_id", String(64), nullable=False),
            Column("status", String(32), nullable=False),
        )
        self.users = Table(
            "auth_users",
            external_metadata,
            Column("id", String(255), primary_key=True),
            Column("tenant_id", String(255), nullable=False),
            Column("domain_id", String(64), nullable=False),
            Column("area_id", String(64), nullable=False),
            Column("role", String(32), nullable=False),
            Column("status", String(32), nullable=False),
        )
        self.residences = Table(
            "partner_residences",
            external_metadata,
            Column("id", String(255), primary_key=True),
            Column("partner_client_id", String(255), nullable=False),
            Column("external_user_id", String(255), nullable=False),
            Column("residence_id", String(255), nullable=False),
            Column("domain_id", String(64), nullable=False),
            Column("area_id", String(64), nullable=False),
            Column("status", String(32), nullable=False),
        )
        external_metadata.create_all(self.engine)
        foundation_metadata.create_all(self.engine)
        self.uows = SqlAlchemyUnitOfWorkFactory(
            lambda: SyncAsyncSession(self.engine),
        )

    def tearDown(self):
        self.engine.dispose()

    async def test_durable_job_idempotency_claim_and_completion(self):
        identifiers = iter(("job-1", "job-2", "job-3"))
        jobs = DurableJobService(
            SqlDurableJobRepository(self.uows),
            clock=lambda: NOW,
            id_factory=lambda: next(identifiers),
        )
        scope = Scope(
            tenant_id="tenant-1",
            domain_id="domain-1",
            area_id="area-1",
            manager_account_id="manager-1",
        )
        first = await jobs.enqueue(scope, "workflow", {"value": 1}, "key-1")
        duplicate = await jobs.enqueue(
            scope,
            "workflow",
            {"value": 1},
            "key-1",
        )
        self.assertEqual(first, duplicate)
        with self.assertRaises(ValueError):
            await jobs.enqueue(
                scope,
                "workflow",
                {"value": 2},
                "key-1",
            )
        claim = await jobs.claim("worker-1", timedelta(seconds=30))
        self.assertIsNotNone(claim)
        self.assertEqual(1, claim.fencing_token)
        await jobs.complete_claim(claim, {"ok": True})

    async def test_identity_and_route_use_verified_manager_account(self):
        scope = Scope(
            tenant_id="tenant-1",
            domain_id="domain-1",
            area_id="area-1",
            manager_account_id="manager-1",
        )
        with self.engine.begin() as connection:
            connection.execute(
                self.domains.insert().values(
                    id="domain-1",
                    tenant_id="tenant-1",
                    status="active",
                ),
            )
            connection.execute(
                self.areas.insert().values(
                    id="area-1",
                    domain_id="domain-1",
                    status="active",
                ),
            )
            connection.execute(
                self.users.insert().values(
                    id="manager-1",
                    tenant_id="tenant-1",
                    domain_id="domain-1",
                    area_id="area-1",
                    role="AREA_MANAGER",
                    status="active",
                ),
            )
            connection.execute(
                manager_memberships.insert().values(
                    id="membership-1",
                    **scope.model_dump(mode="python"),
                    status="verified",
                    revision=2,
                    verified_by="provisioning",
                    verified_at=NOW,
                    created_at=NOW,
                    updated_at=NOW,
                ),
            )
            connection.execute(
                partner_manager_routes.insert().values(
                    id="route-1",
                    **scope.model_dump(mode="python"),
                    partner_client_id="partner-1",
                    external_management_ref="tower-a",
                    status="active",
                    revision=3,
                    membership_revision=2,
                    allowed_operations=["submit_request", "read_result"],
                    granted_by="manager-1",
                    confirmed_by_client_id="partner-1",
                    created_at=NOW,
                    updated_at=NOW,
                ),
            )
            connection.execute(
                self.residences.insert().values(
                    id="residence-row-1",
                    partner_client_id="partner-1",
                    external_user_id="resident-1",
                    residence_id="residence-1",
                    domain_id="domain-1",
                    area_id="area-1",
                    status="active",
                ),
            )

        @dataclass(frozen=True)
        class ManagerPrincipal:
            user_id: str = "manager-1"
            tenant_id: str = "tenant-1"
            role: str = "AREA_MANAGER"
            domain_id: str = "domain-1"
            area_id: str = "area-1"

        identity = SqlIdentityPort(self.uows)
        self.assertEqual(
            scope,
            await identity.resolve_manager(ManagerPrincipal()),
        )
        actor = ActorContext(
            kind="partner",
            actor_id="customer-backend",
            partner_client_id="partner-1",
            credential_id="customer-key-1",
            credential_purpose="customer_api",
            external_user_id="resident-1",
            authentication_source="test",
        )
        routes = SqlPartnerRoutingPort(self.uows, clock=lambda: NOW)
        resolved = await routes.resolve(
            actor,
            {
                "external_management_ref": "tower-a",
                "external_user_id": "resident-1",
                "residence_id": "residence-1",
            },
        )
        self.assertEqual(scope, resolved.scope)
        await routes.revalidate(
            scope,
            resolved.route_id,
            resolved.route_revision,
            actor,
            PartnerAudience(
                partner_client_id="partner-1",
                external_user_id="resident-1",
                external_conversation_id="chat-1",
                external_ticket_id="ticket-1",
                residence_id="residence-1",
            ),
            PartnerOperation.SUBMIT_REQUEST,
        )

class ProviderAuthenticationTests(unittest.IsolatedAsyncioTestCase):
    def setUp(self) -> None:
        self.credentials = FakeCredentials()

        async def authenticate(api_key: str):
            if api_key != "dp_api-credential-1.secret-value-long-enough":
                raise PermissionError("invalid API key")
            return ApiPrincipal()

        self.auth = HmacProviderAuth(
            self.credentials,
            authenticate,
            lambda ref: SECRET,
            clock=lambda: NOW,
        )

    @staticmethod
    def headers(body: bytes, timestamp: int | None = None):
        timestamp_text = str(timestamp or int(NOW.timestamp()))
        signature = hmac.new(
            SECRET,
            timestamp_text.encode("ascii") + b"." + body,
            hashlib.sha256,
        ).hexdigest()
        return {
            "Authorization": (
                "ApiKey dp_api-credential-1.secret-value-long-enough"
            ),
            "X-Partner-Timestamp": timestamp_text,
            "X-Partner-Key-Id": "signing-1",
            "X-Partner-Signature": f"v1={signature}",
        }

    async def test_raw_body_signature_produces_server_only_context(self):
        body = b'{"external_event_id":"event-1"}'
        context = await self.auth.authenticate(body, self.headers(body))
        self.assertIsInstance(context, VerifiedProviderContext)
        self.assertEqual("provider-1", context.provider_integration_id)
        self.assertEqual(
            CredentialPurpose.PROVIDER_EVENTS,
            context.actor.credential_purpose,
        )
        await self.auth.authorize_integration(
            context,
            PartnerOperation.PUBLISH_JOB_EVENT,
        )
        await self.auth.authorize_integration(context, "process_job_event")

    async def test_tampered_body_and_expired_timestamp_are_rejected(self):
        body = b'{"external_event_id":"event-1"}'
        with self.assertRaises(PermissionError):
            await self.auth.authenticate(body + b" ", self.headers(body))
        old = int((NOW - timedelta(minutes=6)).timestamp())
        with self.assertRaises(PermissionError):
            await self.auth.authenticate(body, self.headers(body, old))

    async def test_revalidation_blocks_revoked_credential(self):
        body = b"{}"
        context = await self.auth.authenticate(body, self.headers(body))
        self.credentials.active = False
        with self.assertRaises(PermissionError):
            await self.auth.authorize_integration(
                context,
                PartnerOperation.READ_EVENT_RECEIPT,
            )


if __name__ == "__main__":
    unittest.main()
