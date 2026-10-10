# -*- coding: utf-8 -*-
"""Production service/normalizer exercised through test-only dependencies."""

from datetime import timedelta
from unittest.mock import AsyncMock
import unittest

from pydantic import ValidationError

from agentscope.app.workforce.contracts import (
    AsyncProtocolPort,
    Scope,
    WorkforceContractError,
    WorkforceErrorCode,
)
from agentscope.app.workforce.registry.event_protocols import (
    AsyncProtocolService,
    AsyncToolProtocol,
)
from fakes import FakeAsyncProtocolRepository
import test_protocols


class ProtocolServiceTests(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        test_protocols.ProtocolTests.setUp(self)
        self.repository = FakeAsyncProtocolRepository()
        self.metadata = (
            self.scope.tenant_id,
            "provider-demo",
            "inbox-1",
            self.fake.received_at,
        )
        self.loader = AsyncMock(return_value=self.metadata)
        self.service = AsyncProtocolService(
            self.repository,
            self.scope,
            self.loader,
        )

    async def asyncSetUp(self):
        for protocol in self.protocols.values():
            await self.service.publish(protocol)

    async def normalize(self, event=None, ref=None, actor=None):
        return await self.service.normalize_verified_event(
            actor or self.provider,
            ref or self.protocol.snapshot_ref,
            event or self.event,
        )

    async def test_shared_port_and_all_modes(self):
        self.assertIsInstance(self.service, AsyncProtocolPort)
        for protocol in self.protocols.values():
            ref = await self.service.get_snapshot(
                self.scope,
                protocol.tool_version_id,
            )
            self.assertEqual(ref, protocol.snapshot_ref)
            await self.service.validate_capability_coverage(
                ref,
                ref.capabilities,
            )
        with self.assertRaises(WorkforceContractError) as raised:
            await self.service.validate_capability_coverage(
                self.protocols["create_only"].snapshot_ref,
                ["receive_status"],
            )
        self.assertEqual(
            raised.exception.code,
            WorkforceErrorCode.MISSING_REQUIRED_CAPABILITY,
        )

    async def test_all_scope_dimensions_isolate_current_and_pinned(self):
        for field in Scope.model_fields:
            with self.subTest(field=field):
                other = Scope.model_validate(
                    self.scope.model_dump() | {field: "other"},
                )
                with self.assertRaises(PermissionError):
                    await self.service.get_snapshot(
                        other,
                        self.protocol.tool_version_id,
                    )
                isolated = AsyncProtocolService(
                    self.repository,
                    other,
                    self.loader,
                )
                with self.assertRaises(KeyError):
                    await isolated.get_detailed_snapshot(
                        self.protocol.snapshot_ref,
                    )

    async def test_publish_idempotency_conflict_and_stale_revision(self):
        old = self.protocol.snapshot_ref
        await self.service.publish(self.protocol)
        conflict = AsyncToolProtocol.model_validate(
            self.protocol.model_dump() | {"timeout_seconds": 7200},
        )
        with self.assertRaises(WorkforceContractError) as raised:
            await self.service.publish(conflict, old)
        self.assertEqual(
            raised.exception.code,
            WorkforceErrorCode.IDEMPOTENCY_CONFLICT,
        )
        revised = AsyncToolProtocol.model_validate(
            conflict.model_dump() | {"protocol_version": "2"},
        )
        with self.assertRaises(WorkforceContractError):
            await self.service.publish(revised)
        new = await self.service.publish(revised, old)
        with self.assertRaises(WorkforceContractError):
            await self.service.set_enabled(old.tool_version_id, False, old)
        self.assertEqual(
            await self.service.get_snapshot(self.scope, old.tool_version_id),
            new,
        )
        self.assertEqual(
            (await self.normalize(ref=old)).protocol_schema_hash,
            old.schema_hash,
        )

    async def test_disable_blocks_new_calls_but_preserves_old_events(self):
        ref = self.protocol.snapshot_ref
        await self.service.set_enabled(ref.tool_version_id, False, ref)
        with self.assertRaises(PermissionError):
            await self.service.get_snapshot(self.scope, ref.tool_version_id)
        self.assertEqual(
            (await self.normalize()).normalized_status,
            "on_the_way",
        )
        revised = AsyncToolProtocol.model_validate(
            self.protocol.model_dump() | {"protocol_version": "2"},
        )
        new = await self.service.publish(revised, ref)
        with self.assertRaises(PermissionError):
            await self.service.get_snapshot(self.scope, ref.tool_version_id)
        await self.service.set_enabled(new.tool_version_id, True, new)
        self.assertEqual(
            await self.service.get_snapshot(self.scope, new.tool_version_id),
            new,
        )

    async def test_forged_pins_and_caller_mutation_cannot_rewrite_content(
        self,
    ):
        ref = self.protocol.snapshot_ref
        detailed = await self.service.get_detailed_snapshot(ref)
        detailed.event_mappings.clear()
        self.protocol.event_mappings.clear()
        self.assertEqual(
            (await self.normalize(ref=ref)).normalized_status,
            "on_the_way",
        )
        for change in (
            {"schema_hash": "forged"},
            {"capabilities": ("create",)},
            {"provider_integration_id": "other"},
        ):
            with self.subTest(change=change):
                with self.assertRaises(ValueError):
                    await self.service.validate_capability_coverage(
                        ref.model_copy(update=change),
                        [],
                    )

    async def test_inbox_metadata_is_loaded_per_event_and_retry_is_stable(
        self,
    ):
        first = await self.normalize()
        self.assertEqual(first, await self.normalize())
        self.assertEqual(
            first,
            await self.fake.normalize_verified_event(
                self.provider,
                self.protocol.snapshot_ref,
                self.event,
            ),
        )
        self.assertEqual(first.facts, {"eta_minutes": 20})
        self.loader.assert_awaited_with(self.provider, self.event)
        self.loader.return_value = self.metadata[:2] + (
            "inbox-2",
            self.metadata[3] + timedelta(seconds=1),
        )
        second = await self.normalize(
            self.event.model_copy(
                update={"external_event_id": "event-004"},
            ),
        )
        self.assertEqual(second.inbox_event_id, "inbox-2")
        self.assertNotEqual(first.received_at, second.received_at)
        self.assertEqual(self.loader.await_count, 3)

    async def test_actor_namespace_and_missing_metadata_fail_closed(self):
        for change in (
            {"kind": "manager"},
            {"credential_purpose": "customer_api"},
        ):
            with self.assertRaises(PermissionError):
                await self.normalize(
                    actor=self.provider.model_copy(
                        update=change,
                    ),
                )
        self.loader.assert_not_awaited()
        for metadata in (
            ("other-tenant", *self.metadata[1:]),
            (self.metadata[0], "other-provider", *self.metadata[2:]),
        ):
            self.loader.return_value = metadata
            with self.assertRaises(PermissionError):
                await self.normalize()
        for metadata in (
            (*self.metadata[:2], "", self.metadata[3]),
            (*self.metadata[:3], self.metadata[3].replace(tzinfo=None)),
            None,
        ):
            self.loader.return_value = metadata
            with self.assertRaises(ValidationError):
                await self.normalize()
        self.loader.side_effect = PermissionError("grant revoked")
        with self.assertRaises(PermissionError):
            await self.normalize()

    async def test_normalizer_preserves_order_and_rejects_invalid_events(self):
        for version in (4, 2, 3, 3):
            normalized = await self.normalize(
                self.event.model_copy(
                    update={"provider_version": version},
                ),
            )
            self.assertEqual(normalized.provider_version, version)
        for change in (
            {"provider_version": True},
            {"provider_version": 3.0},
            {"occurred_at": self.event.occurred_at.replace(tzinfo=None)},
            {"data": {"eta_minutes": float("nan")}},
        ):
            with self.subTest(change=change):
                with self.assertRaises(ValueError):
                    await self.normalize(self.event.model_copy(update=change))

    async def test_injected_uow_is_forwarded_without_commit(self):
        uow = AsyncMock()
        ref = self.protocol.snapshot_ref
        revised = AsyncToolProtocol.model_validate(
            self.protocol.model_dump() | {"protocol_version": "2"},
        )
        new = await self.service.publish(revised, ref, uow)
        await self.service.set_enabled(new.tool_version_id, False, new, uow)
        self.assertEqual(self.repository.uows[-2:], [uow, uow])
        uow.commit.assert_not_awaited()


if __name__ == "__main__":
    unittest.main()
