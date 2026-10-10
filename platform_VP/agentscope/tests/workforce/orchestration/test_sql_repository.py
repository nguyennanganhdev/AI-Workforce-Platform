"""SQLite persistence smoke tests; explicitly not PostgreSQL lock/race proof."""

import unittest
from tempfile import TemporaryDirectory
from pathlib import Path

import _support
from _support import FakeIdentity, SCOPE
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from wf_orchestration_under_test import ConversationService, SharedStateService
from wf_orchestration_under_test._models import OrchestrationError
from wf_orchestration_under_test._sql_repository import SQLOrchestrationRepository
from wf_orchestration_under_test._tables import metadata
from wf_orchestration_under_test.workflows._ingress import TicketIngress
from test_ingress import FakePartnerGuard


class SQLRepositoryTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.directory = TemporaryDirectory()
        self.url = f"sqlite+aiosqlite:///{Path(self.directory.name) / 'phh.db'}"
        self.engine = create_async_engine(self.url)
        async with self.engine.begin() as connection:
            await connection.run_sync(metadata.create_all)
        self.identity = FakeIdentity()
        self.repository = SQLOrchestrationRepository(async_sessionmaker(self.engine))

    async def asyncTearDown(self):
        await self.engine.dispose()
        self.directory.cleanup()

    async def test_storage_survives_engine_recreation(self):
        service = ConversationService(self.repository, self.identity)
        conversation = await service.create(SCOPE)
        await SharedStateService(self.repository, self.identity).patch_facts(
            SCOPE, conversation.conversation_id, 0, {"destination": "Ha Long"},
            source_kind="user", source_ref="message-1")
        await self.engine.dispose()
        self.engine = create_async_engine(self.url)
        new_repository = SQLOrchestrationRepository(async_sessionmaker(self.engine))
        state = await ConversationService(new_repository, self.identity).read_state(SCOPE, conversation.conversation_id)
        self.assertEqual(state.facts, {"destination": "Ha Long"})
        self.assertEqual(state.state_revision, 1)

    async def test_scope_filtered_and_stale_revision_rejected(self):
        conversation = await ConversationService(self.repository, self.identity).create(SCOPE)
        other = {**SCOPE, "manager_account_id": "other"}
        with self.assertRaisesRegex(OrchestrationError, "RESOURCE_NOT_FOUND"):
            await ConversationService(self.repository, self.identity).read_state(other, conversation.conversation_id)
        state = SharedStateService(self.repository, self.identity)
        await state.patch_facts(SCOPE, conversation.conversation_id, 0, {"budget": 10}, source_kind="user", source_ref="m")
        with self.assertRaisesRegex(OrchestrationError, "REVISION_CONFLICT"):
            await state.patch_facts(SCOPE, conversation.conversation_id, 0, {"budget": 20}, source_kind="user", source_ref="m2")

    async def test_exception_rolls_back_json_and_revision(self):
        conversation = await ConversationService(self.repository, self.identity).create(SCOPE)
        with self.assertRaisesRegex(OrchestrationError, "RESERVE_EXCEEDS_BUDGET"):
            await SharedStateService(self.repository, self.identity).patch_facts(
                SCOPE, conversation.conversation_id, 0, {"budget": 5, "reserve": 10}, source_kind="user", source_ref="m")
        state = await ConversationService(self.repository, self.identity).read_state(SCOPE, conversation.conversation_id)
        self.assertEqual((state.facts, state.state_revision), ({}, 0))

    async def test_ticket_command_binding_survives_reopen_and_replay(self):
        class SQLJobs:
            async def enqueue(inner, scope, kind, payload, idempotency_key, *, uow):
                self.assertTrue(uow.in_transaction())

        envelope = {"schema_version": "1", "command_type": "start_workflow", "external_request_id": "req",
                    "external_management_ref": "management", "external_user_id": "user",
                    "external_ticket_id": "ticket", "external_conversation_id": "chat",
                    "message": {"type": "text", "text": "question"}}
        ingress = TicketIngress(self.repository, FakePartnerGuard(), SQLJobs())
        first = await ingress.accept("authenticated-test-actor", envelope)
        await self.engine.dispose()
        self.engine = create_async_engine(self.url)
        repository = SQLOrchestrationRepository(async_sessionmaker(self.engine))
        second = await TicketIngress(repository, FakePartnerGuard(), SQLJobs()).accept("authenticated-test-actor", envelope)
        self.assertEqual(first, second)

    async def test_postgresql_metadata_compiles_without_creating_real_migration(self):
        from sqlalchemy.dialects import postgresql
        from sqlalchemy.schema import CreateTable
        ddl = "\n".join(str(CreateTable(table).compile(dialect=postgresql.dialect())) for table in metadata.sorted_tables)
        self.assertIn("JSONB", ddl)
        self.assertIn("wf_inbound_requests", ddl)
        self.assertIn("UNIQUE (tenant_id, partner_client_id, external_request_id)", ddl)

    async def test_repository_rejects_mutation_of_identity_fields(self):
        conversation = await ConversationService(self.repository, self.identity).create(SCOPE)
        with self.assertRaisesRegex(OrchestrationError, "IMMUTABLE_BINDING_CHANGED"):
            async with self.repository.transaction() as uow:
                record = await self.repository.get("conversation", conversation.scope, conversation.conversation_id, uow)
                record.mode = "direct"
                await self.repository.save("conversation", record, record.state_revision, uow)

    async def test_pending_membership_recovers_same_operation_and_session_after_reopen(self):
        from _support import FakeCatalog
        from wf_orchestration_under_test import CapabilityRouter, MemberService, RunService, TeamRuntimeAdapter

        catalog = FakeCatalog()
        router = CapabilityRouter(catalog, self.identity)
        bindings = {}
        fail = False

        async def provision(scope, run, *, idempotency_key):
            binding = {"group_id": run.group_id, "leader_session_id": run.leader_session_id,
                       "members": [{k: m[k] for k in ("agent_id", "version_id", "session_id", "manifest_hash")}
                                   for m in run.members]}
            bindings.setdefault(idempotency_key, binding)
            if fail:
                raise TimeoutError("lost ACK")
            return bindings[idempotency_key]

        async def never_send(*args, **kwargs):
            self.fail("recovery must not send tasks")

        runtime = TeamRuntimeAdapter(identity=self.identity, provision_pinned_group=provision, send_team_task=never_send)
        conversation = await ConversationService(self.repository, self.identity).create(SCOPE)
        run = await RunService(self.repository, self.identity, router, runtime).start(
            SCOPE, conversation.conversation_id, ("hotel",), expected_revision=0)
        candidate = next(c for c in catalog.items if c["agent_id"] == "Car")
        fail = True
        with self.assertRaises(TimeoutError):
            await MemberService(self.repository, self.identity, router, runtime).add(
                SCOPE, run.run_id, candidate, expected_revision=run.revision, reason="need car")
        async with self.repository.transaction() as uow:
            pending = await self.repository.get("run", run.scope, run.run_id, uow)
        keys = set(bindings)
        await self.engine.dispose()
        self.engine = create_async_engine(self.url)
        self.repository = SQLOrchestrationRepository(async_sessionmaker(self.engine))
        fail = False
        recovered = await RunService(self.repository, self.identity, router, runtime).resume_materialization(SCOPE, run.run_id)
        self.assertEqual(recovered.status, "running")
        self.assertEqual(recovered.members, pending.members + pending.pending_members)
        self.assertEqual(recovered.pending_members, [])
        self.assertIsNone(recovered.membership_operation_id)
        self.assertEqual(set(bindings), keys)
