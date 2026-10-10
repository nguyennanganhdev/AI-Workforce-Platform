# -*- coding: utf-8 -*-
"""Phase-A executable protocol handoff and fake-port contract checks."""

from datetime import UTC, datetime
import json
from pathlib import Path
import unittest

from jsonschema import Draft202012Validator, ValidationError as SchemaError
from pydantic import ValidationError

from agentscope.app.workforce.contracts import (
    ActorContext,
    AsyncProtocolPort,
    ProviderEventEnvelope,
    Scope,
    ToolDescriptor,
    WorkforceContractError,
    WorkforceErrorCode,
)
from agentscope.app.workforce.registry.event_protocols import (
    AsyncToolProtocol,
    EventMapping,
)
from fakes import FakeAsyncProtocolPort


class ProtocolTests(unittest.IsolatedAsyncioTestCase):
    def setUp(self) -> None:
        sample_path = (
            Path(__file__).resolve().parents[4]
            / "docs/workforce/handoffs/nguyen-phuong-dong/phase_a_samples.json"
        )
        self.samples = json.loads(sample_path.read_text(encoding="utf-8"))
        self.schema_path = sample_path.with_name(
            "phase_a_protocol.schema.json",
        )
        self.protocols = {
            name: AsyncToolProtocol.model_validate(config)
            for name, config in self.samples["protocols"].items()
        }
        self.protocol = self.protocols["provider_event"]
        self.scope = Scope(
            tenant_id="tenant-1",
            domain_id="domain-1",
            area_id="area-1",
            manager_account_id="manager-1",
        )
        self.provider = ActorContext(
            kind="partner",
            actor_id="machine-1",
            partner_client_id="partner-1",
            credential_id="credential-1",
            credential_purpose="provider_events",
            authentication_source="verified_test_fixture",
        )
        self.event = ProviderEventEnvelope.model_validate(
            self.samples["provider_event"],
        )
        self.fake = FakeAsyncProtocolPort(
            self.scope,
            tuple(self.protocols.values()),
            self.provider,
            "provider-demo",
            "inbox-1",
            datetime(2026, 10, 10, 8, 0, 1, tzinfo=UTC),
        )

    def test_samples_validate_with_exported_schema_and_shared_dtos(
        self,
    ) -> None:
        schema = AsyncToolProtocol.model_json_schema()
        self.assertEqual(
            json.loads(self.schema_path.read_text(encoding="utf-8")),
            schema,
        )
        Draft202012Validator.check_schema(schema)
        for name, config in self.samples["protocols"].items():
            Draft202012Validator(schema).validate(config)
            self.assertEqual(
                self.samples["snapshot_refs"][name],
                self.protocols[name].snapshot_ref.model_dump(mode="json"),
            )
        tool = ToolDescriptor.model_validate(self.samples["tool_descriptor"])
        self.assertEqual(tool.tool_version_id, self.protocol.tool_version_id)
        self.assertNotIn(
            "workflow_state",
            self.protocol.snapshot_ref.model_dump(),
        )

    def test_capabilities_distinguish_all_five_modes(self) -> None:
        expected = {
            "sync": ("terminal",),
            "interactive": ("terminal", "approval"),
            "create_only": ("create",),
            "provider_event": ("create", "receive_status"),
            "query_only": ("create", "status_query"),
        }
        for name, capabilities in expected.items():
            with self.subTest(name=name):
                self.assertEqual(
                    self.protocols[name].snapshot_ref.capabilities,
                    capabilities,
                )

    def test_invalid_configuration_fails_closed(self) -> None:
        cases = [
            ("sync", {"effect": "write"}),
            ("sync", {"requires_approval": True}),
            ("sync", {"timeout_seconds": 60}),
            ("sync", {"callback_url": "https://untrusted.example"}),
            ("sync", {"manager_account_id": "other-manager"}),
            ("create_only", {"provider_integration_id": None}),
            (
                "create_only",
                {
                    "external_job_id_field": None,
                    "client_reference_field": None,
                },
            ),
            ("create_only", {"status_field": None}),
            ("create_only", {"timeout_seconds": 0}),
            ("create_only", {"terminal_statuses": []}),
            ("create_only", {"transitions": {"pending": ["undeclared"]}}),
            ("create_only", {"transitions": {"completed": ["completed"]}}),
            ("create_only", {"event_mode": "delta"}),
            (
                "provider_event",
                {
                    "event_mappings": {
                        "job.bad": {"status": "undeclared", "data_schema": {}},
                    },
                },
            ),
            (
                "provider_event",
                {
                    "event_mappings": {
                        "job.bad": {
                            "status": "assigned",
                            "data_schema": {"type": "invalid"},
                        },
                    },
                },
            ),
        ]
        for name, change in cases:
            with self.subTest(name=name, change=change):
                with self.assertRaises(ValidationError):
                    AsyncToolProtocol.model_validate(
                        self.samples["protocols"][name] | change,
                    )

    def test_unresolvable_schema_references_fail_at_configuration(
        self,
    ) -> None:
        for schema in (
            {"$ref": "#/$defs/missing"},
            {"properties": {"eta_minutes": {"$ref": "#/$defs/missing"}}},
            {"allOf": [{"$ref": "#missing"}]},
            {"$dynamicRef": "#missing"},
            {"$ref": "https://untrusted.example/schema.json"},
            {
                "$defs": {"count": {"minimum": 0}},
                "$ref": "#/$defs/count/minimum",
            },
        ):
            with self.subTest(schema=schema):
                with self.assertRaises(ValidationError):
                    EventMapping(status="assigned", data_schema=schema)

    async def test_local_schema_references_normalize_without_network(
        self,
    ) -> None:
        for schema in (
            {
                "$defs": {"count": {"type": "integer", "minimum": 0}},
                "properties": {"eta_minutes": {"$ref": "#/$defs/count"}},
            },
            {
                "$defs": {"count": {"$anchor": "count", "type": "integer"}},
                "properties": {"eta_minutes": {"$ref": "#count"}},
            },
            {
                "$id": "https://schemas.example/event",
                "$defs": {"count": {"$id": "count", "type": "integer"}},
                "properties": {"eta_minutes": {"$ref": "count"}},
            },
            {"examples": [{"$ref": "literal data, not a schema reference"}]},
        ):
            with self.subTest(schema=schema):
                config = self.protocol.model_dump(mode="json")
                config["event_mappings"][self.event.event_type][
                    "data_schema"
                ] = schema
                protocol = AsyncToolProtocol.model_validate(config)
                fake = FakeAsyncProtocolPort(
                    self.scope,
                    [protocol],
                    self.provider,
                    "provider-demo",
                    "inbox-1",
                    self.fake.received_at,
                )
                event = await fake.normalize_verified_event(
                    self.provider,
                    protocol.snapshot_ref,
                    self.event,
                )
                self.assertEqual(event.facts, {"eta_minutes": 20})

    def test_hash_is_canonical_and_detects_mapping_or_policy_drift(
        self,
    ) -> None:
        config = self.protocol.model_dump(mode="json")
        reordered = AsyncToolProtocol.model_validate(
            dict(reversed(config.items())),
        )
        self.assertEqual(self.protocol.snapshot_ref, reordered.snapshot_ref)
        for change in (
            {"timeout_seconds": 7200},
            {"event_mode": "delta"},
            {"requires_approval": True},
            {"event_mappings": {}},
        ):
            with self.subTest(change=change):
                changed = AsyncToolProtocol.model_validate(config | change)
                self.assertNotEqual(
                    self.protocol.snapshot_ref.schema_hash,
                    changed.snapshot_ref.schema_hash,
                )

    async def test_fake_implements_shared_port_and_checks_all_scope_fields(
        self,
    ) -> None:
        self.assertIsInstance(self.fake, AsyncProtocolPort)
        snapshot = await self.fake.get_snapshot(
            self.scope,
            self.protocol.tool_version_id,
        )
        self.assertEqual(snapshot, self.protocol.snapshot_ref)
        for field in Scope.model_fields:
            with self.subTest(field=field):
                other = Scope.model_validate(
                    self.scope.model_dump() | {field: "other"},
                )
                with self.assertRaises(PermissionError):
                    await self.fake.get_snapshot(
                        other,
                        self.protocol.tool_version_id,
                    )
        with self.assertRaises(KeyError):
            await self.fake.get_snapshot(self.scope, "missing-tool")

    async def test_create_only_cannot_claim_tracking_coverage(self) -> None:
        ref = self.protocols["create_only"].snapshot_ref
        await self.fake.validate_capability_coverage(ref, ["create"])
        with self.assertRaises(WorkforceContractError) as raised:
            await self.fake.validate_capability_coverage(
                ref,
                ["receive_status", "status_query"],
            )
        self.assertEqual(
            raised.exception.code,
            WorkforceErrorCode.MISSING_REQUIRED_CAPABILITY,
        )
        self.assertIn("receive_status", str(raised.exception))
        self.assertIn("status_query", str(raised.exception))

    async def test_pinned_snapshot_survives_caller_mutation(self) -> None:
        ref = self.protocol.snapshot_ref
        self.protocol.event_mappings.clear()
        event = await self.fake.normalize_verified_event(
            self.provider,
            ref,
            self.event,
        )
        self.assertEqual(event.normalized_status, "on_the_way")
        for change, error in (
            ({"schema_hash": "forged"}, KeyError),
            ({"capabilities": ("create",)}, ValueError),
        ):
            with self.subTest(change=change):
                with self.assertRaises(error):
                    await self.fake.validate_capability_coverage(
                        ref.model_copy(update=change),
                        [],
                    )

    async def test_protocol_drift_keeps_old_snapshot_resolvable(self) -> None:
        old = self.protocol.snapshot_ref
        revised = AsyncToolProtocol.model_validate(
            self.protocol.model_dump()
            | {"protocol_version": "2", "timeout_seconds": 7200},
        )
        fake = FakeAsyncProtocolPort(
            self.scope,
            [self.protocol, revised],
            self.provider,
            "provider-demo",
            "inbox-1",
            self.fake.received_at,
        )
        current = await fake.get_snapshot(self.scope, old.tool_version_id)
        self.assertEqual(current, revised.snapshot_ref)
        event = await fake.normalize_verified_event(
            self.provider,
            old,
            self.event,
        )
        self.assertEqual(event.protocol_schema_hash, old.schema_hash)

    async def test_normalization_is_deterministic_and_projects_only_facts(
        self,
    ) -> None:
        ref = self.protocol.snapshot_ref
        first = await self.fake.normalize_verified_event(
            self.provider,
            ref,
            self.event,
        )
        second = await self.fake.normalize_verified_event(
            self.provider,
            ref,
            self.event,
        )
        self.assertEqual(first, second)
        self.assertEqual(first.facts, {"eta_minutes": 20})
        self.assertEqual(first.inbox_event_id, "inbox-1")
        self.assertEqual(first.external_event_id, self.event.external_event_id)
        self.assertEqual(first.external_job_id, self.event.external_job_id)
        self.assertEqual(first.client_reference, self.event.client_reference)
        self.assertEqual(first.provider_version, 3)
        self.assertEqual(first.protocol_schema_hash, ref.schema_hash)
        self.assertNotIn("scope", first.model_dump())
        self.assertNotEqual(first.occurred_at, first.received_at)

    async def test_normalization_keeps_order_metadata(
        self,
    ) -> None:
        for event_type, mapping in self.protocol.event_mappings.items():
            for version in (4, 2, 3, 3):
                with self.subTest(event_type=event_type, version=version):
                    event = self.event.model_copy(
                        update={
                            "event_type": event_type,
                            "provider_version": version,
                        },
                    )
                    normalized = await self.fake.normalize_verified_event(
                        self.provider,
                        self.protocol.snapshot_ref,
                        event,
                    )
                    self.assertEqual(
                        normalized.normalized_status,
                        mapping.status,
                    )
                    self.assertEqual(normalized.provider_version, version)

    async def test_wrong_namespace_or_credential_purpose_is_rejected(
        self,
    ) -> None:
        for change in (
            {"actor_id": "other-provider"},
            {"credential_purpose": "customer_api"},
        ):
            with self.subTest(change=change):
                with self.assertRaises(PermissionError):
                    await self.fake.normalize_verified_event(
                        self.provider.model_copy(update=change),
                        self.protocol.snapshot_ref,
                        self.event,
                    )
        other_config = self.protocol.model_dump() | {
            "provider_integration_id": "other-namespace",
        }
        other = AsyncToolProtocol.model_validate(other_config)
        fake = FakeAsyncProtocolPort(
            self.scope,
            [other],
            self.provider,
            "provider-demo",
            "inbox-1",
            self.fake.received_at,
        )
        with self.assertRaises(PermissionError):
            await fake.normalize_verified_event(
                self.provider,
                other.snapshot_ref,
                self.event,
            )

    async def test_bad_event_schema_unknown_type_and_missing_version_fail(
        self,
    ) -> None:
        for change, error in (
            ({"data": {"eta_minutes": -1}}, SchemaError),
            ({"data": {"manager_account_id": "injected"}}, SchemaError),
            ({"event_type": "unknown"}, KeyError),
            ({"provider_version": None}, ValueError),
        ):
            with self.subTest(change=change):
                with self.assertRaises(error):
                    await self.fake.normalize_verified_event(
                        self.provider,
                        self.protocol.snapshot_ref,
                        self.event.model_copy(update=change),
                    )


if __name__ == "__main__":
    unittest.main()
