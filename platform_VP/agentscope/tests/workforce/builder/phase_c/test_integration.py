"""C3 only: C1 UOW + C2 SQL protocols consumed by Phase-B Builder validation."""

import unittest

from agentscope.app.workforce.builder import (
    ProposalService,
    ProtocolBuildValidator,
    RegistryCapabilitySelector,
    RegistryProtocolReadiness,
    RequirementExtractor,
)
from agentscope.app.workforce.builder.async_capabilities import BuildRequirements
from agentscope.app.workforce.contracts import (
    AgentManifest,
    AgentSpec,
    WorkforceContractError,
)
from agentscope.app.workforce.lifecycle.async_evaluation import AsyncDraftValidator
from agentscope.app.workforce.registry.event_protocols import (
    AsyncToolProtocol,
    SqlAsyncProtocolProvider,
)
from agentscope.app.workforce.registry.event_protocols._tables import (
    metadata as protocol_metadata,
)
from tests.workforce.builder.async_capabilities import test_phase_b as phase_b
from tests.workforce.builder.async_capabilities.fakes import (
    Model,
    Registry,
    Reuse,
    tool,
)
from tests.workforce.foundation.phase_c import test_foundation as foundation_tests


class BuilderProtocolTests(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        self.fixture = phase_b.PhaseBTests()
        self.fixture.setUp()
        self.scope = self.fixture.scope
        self.sql = foundation_tests.SqlRepositoryTests()
        self.sql.setUp()
        self.addCleanup(self.sql.tearDown)
        protocol_metadata.create_all(self.sql.engine)
        self.provider = SqlAsyncProtocolProvider(self.sql.uows)
        self.port = self.provider.bind(self.scope, self.no_event_context)
        self.readiness = RegistryProtocolReadiness(self.provider.resolve_detail)
        self.catalog = Registry(self.scope, (tool("create", "external_operation"),))
        self.selector = RegistryCapabilitySelector(
            self.catalog, self.port, self.readiness
        )

    async def no_event_context(self, *args):
        raise AssertionError("Builder must not normalize provider events")

    def service(self, requirements=None):
        return ProposalService(
            RequirementExtractor(Model([self.fixture.build_output(requirements)])),
            self.selector,
            Reuse(self.scope),
        )

    async def proposal(self, requirements=None):
        service = self.service(requirements or self.fixture.tracking)
        proposal = await service.prepare(self.scope, "Create agent", "m")
        return service, proposal

    def manifest(self, item):
        return AgentManifest(
            schema_version="1",
            business_profile=item.requirement.business_profile,
            spec=AgentSpec(
                agent_key=item.requirement.agent_key,
                name="Test agent",
                capabilities=item.selection.covered,
                system_prompt="Use only approved capabilities.",
                model_config_ref={"test_only": True},
                tool_bindings=item.selection.bindings,
            ),
            protocol_snapshot_hashes=tuple(
                pin.schema_hash for pin in item.selection.protocols
            ),
            async_policy_ref=(
                "test-policy" if item.requirement.policy_proposal else None
            ),
        )

    def validator(self, *, policy=None, invalid_policy=False):
        async def resolve_policy(scope, ref):
            if invalid_policy:
                return scope, ref, "pta-phase-a-1", {}
            return (
                scope,
                ref,
                "pta-phase-a-1",
                (
                    policy
                    if policy is not None
                    else self.fixture.tracking.agents[0].policy_proposal.model_dump(
                        mode="json"
                    )
                ),
            )

        lifecycle = AsyncDraftValidator(
            self.catalog,
            self.port,
            self.provider.resolve_detail,
            resolve_policy,
        )
        return ProtocolBuildValidator(self.selector, lifecycle.validate)

    async def test_real_readiness_projects_exact_protocol_metadata(self):
        protocol = self.fixture.protocol(query=True)
        await self.port.publish(protocol)
        details = await self.readiness.read(self.scope, protocol.snapshot_ref)
        self.assertEqual(details.snapshot, protocol.snapshot_ref)
        self.assertTrue(details.correlation_supported)
        self.assertEqual(details.event_types, ("completed",))
        self.assertEqual(details.fact_fields, ("status",))
        self.assertEqual(details.event_fact_fields, {"completed": ("status",)})
        self.assertEqual(details.completion_policy, "explicit_close")
        self.assertEqual(details.timeout_seconds, 3600)
        self.assertEqual(details.status_query_tool_version_id, "query-v1")

    async def test_real_protocol_exact_pin_disable_and_scope(self):
        protocol = self.fixture.protocol()
        await self.port.publish(protocol)
        req = self.fixture.tracking.agents[0]
        selection = await self.selector.select(self.scope, req)
        self.assertFalse(selection.blockers)
        await self.selector.recheck(self.scope, req, selection)
        newer = protocol.model_copy(
            update={"protocol_version": "2", "timeout_seconds": 7200}
        )
        await self.port.publish(newer, protocol.snapshot_ref)
        self.assertEqual(
            (
                await self.readiness.read(self.scope, protocol.snapshot_ref)
            ).timeout_seconds,
            3600,
        )
        with self.assertRaises(WorkforceContractError):
            await self.selector.recheck(self.scope, req, selection)
        await self.port.set_enabled("tool-v1", False, newer.snapshot_ref)
        with self.assertRaises(PermissionError):
            await self.selector.select(self.scope, req)
        self.assertEqual(
            (await self.readiness.read(self.scope, protocol.snapshot_ref)).snapshot,
            protocol.snapshot_ref,
        )
        other = self.scope.model_copy(update={"manager_account_id": "manager-b"})
        with self.assertRaises((LookupError, PermissionError)):
            await self.readiness.read(other, protocol.snapshot_ref)

    async def test_corrupt_resolver_reference_is_rejected(self):
        protocol = self.fixture.protocol()

        async def wrong(scope, ref):
            return protocol.model_copy(update={"timeout_seconds": 999})

        with self.assertRaises(ValueError):
            await RegistryProtocolReadiness(wrong).read(
                self.scope, protocol.snapshot_ref
            )

    async def test_read_only_needs_no_protocol(self):
        self.catalog.tools = (tool(),)
        selected = await self.selector.select(self.scope, self.fixture.sync.agents[0])
        self.assertFalse(selected.blockers)
        self.assertFalse(selected.protocols)
        self.assertEqual(selected.tracking_channel, "none")
        await self.selector.recheck(self.scope, self.fixture.sync.agents[0], selected)

    async def test_terminal_create_only_pins_protocol_without_polling(self):
        protocol = AsyncToolProtocol(
            protocol_id="terminal",
            protocol_version="1",
            tool_version_id="tool-v1",
            provider_integration_id="provider",
            effect="external_operation",
            result_mode="terminal",
            completion_policy="explicit_close",
        )
        await self.port.publish(protocol)
        requirements = BuildRequirements.model_validate(
            self.fixture.samples[1]["payload"]
        )
        service, proposal = await self.proposal(requirements)
        confirmed = await service.confirm(
            self.scope, proposal.proposal_id, proposal.revision
        )
        item = confirmed.items[0]
        self.assertEqual(item.selection.protocols, (protocol.snapshot_ref,))
        self.assertEqual(item.selection.tracking_channel, "none")
        report, _ = await self.validator().validate(
            self.scope, item, self.manifest(item)
        )
        self.assertTrue(report.valid, report.blockers)

    async def test_pending_create_only_is_blocked_without_inventing_policy(self):
        await self.port.publish(self.fixture.protocol())
        req = BuildRequirements.model_validate(
            self.fixture.samples[1]["payload"]
        ).agents[0]
        selected = await self.selector.select(self.scope, req)
        self.assertIn(
            "CREATE_ONLY_PENDING_POLICY_UNRESOLVED", [b.code for b in selected.blockers]
        )

    async def test_real_query_fallback_pins_read_only_query_binding(self):
        req = self.fixture.tracking.agents[0]
        req = req.model_copy(
            update={
                "policy_proposal": req.policy_proposal.model_copy(
                    update={"timeout_behavior": "status_query"}
                )
            }
        )
        self.catalog.tools = (
            tool("create", "external_operation"),
            tool("status_query", version="query-v1"),
        )
        await self.port.publish(self.fixture.protocol(query=True))
        selected = await self.selector.select(self.scope, req)
        self.assertFalse(selected.blockers)
        self.assertEqual(selected.tracking_channel, "status_query")
        self.assertEqual(
            {b.tool_version_id for b in selected.bindings}, {"tool-v1", "query-v1"}
        )
        await self.selector.recheck(self.scope, req, selected)
        self.catalog.tools = (
            self.catalog.tools[0],
            tool("status_query", version="query-v1", available=False),
        )
        with self.assertRaises(WorkforceContractError):
            await self.selector.recheck(self.scope, req, selected)

    async def test_query_only_without_event_semantics_is_blocked(self):
        req = self.fixture.tracking.agents[0]
        req = req.model_copy(
            update={
                "policy_proposal": req.policy_proposal.model_copy(
                    update={"timeout_behavior": "status_query"}
                )
            }
        )
        self.catalog.tools = (
            tool("create", "external_operation"),
            tool("status_query", version="query-v1"),
        )
        await self.port.publish(self.fixture.protocol(query=True, events=False))
        selected = await self.selector.select(self.scope, req)
        self.assertIn(
            "POLICY_EVENT_SEMANTICS_UNRESOLVED", [b.code for b in selected.blockers]
        )

    async def test_missing_required_event_fact_is_blocked_with_real_metadata(self):
        protocol = self.fixture.protocol()
        protocol = protocol.model_copy(
            update={
                "event_mappings": {
                    "completed": protocol.event_mappings["completed"].model_copy(
                        update={"fact_fields": ()}
                    ),
                }
            }
        )
        await self.port.publish(protocol)
        selected = await self.selector.select(
            self.scope, self.fixture.tracking.agents[0]
        )
        self.assertIn(
            "MISSING_REQUIRED_CAPABILITY", [b.code for b in selected.blockers]
        )

    async def test_phase_b_confirm_refreshes_when_real_protocol_pin_changes(self):
        protocol = self.fixture.protocol()
        await self.port.publish(protocol)
        service, proposal = await self.proposal()
        newer = protocol.model_copy(
            update={"protocol_version": "2", "timeout_seconds": 7200}
        )
        await self.port.publish(newer, protocol.snapshot_ref)
        refreshed = await service.confirm(
            self.scope, proposal.proposal_id, proposal.revision
        )
        self.assertEqual(refreshed.status, "ready")
        self.assertEqual(refreshed.revision, 2)
        self.assertEqual(refreshed.items[0].selection.protocols, (newer.snapshot_ref,))
        self.assertTrue(refreshed.notices)
        confirmed = await service.confirm(
            self.scope, refreshed.proposal_id, refreshed.revision
        )
        self.assertEqual(confirmed.status, "confirmed")

    async def test_phase_b_confirm_rejects_disabled_real_protocol(self):
        protocol = self.fixture.protocol()
        await self.port.publish(protocol)
        service, proposal = await self.proposal()
        await self.port.set_enabled("tool-v1", False, protocol.snapshot_ref)
        with self.assertRaises(PermissionError):
            await service.confirm(self.scope, proposal.proposal_id, proposal.revision)

    async def test_prewrite_hook_uses_real_protocol_and_lifecycle_validation(self):
        protocol = self.fixture.protocol()
        await self.port.publish(protocol)
        service, proposal = await self.proposal()
        confirmed = await service.confirm(
            self.scope, proposal.proposal_id, proposal.revision
        )
        item = confirmed.items[0]
        report, evidence = await self.validator().validate(
            self.scope, item, self.manifest(item)
        )
        self.assertTrue(report.valid, report.blockers)
        self.assertEqual(evidence["policy_ref"], "test-policy")
        self.assertEqual(
            evidence["policy"], item.requirement.policy_proposal.model_dump(mode="json")
        )

    async def test_prewrite_hook_rejects_protocol_disabled_after_confirm(self):
        protocol = self.fixture.protocol()
        await self.port.publish(protocol)
        service, proposal = await self.proposal()
        confirmed = await service.confirm(
            self.scope, proposal.proposal_id, proposal.revision
        )
        await self.port.set_enabled("tool-v1", False, protocol.snapshot_ref)
        item = confirmed.items[0]
        with self.assertRaises(PermissionError):
            await self.validator().validate(self.scope, item, self.manifest(item))

    async def test_prewrite_hook_rejects_unconfirmed_binding_or_pin(self):
        await self.port.publish(self.fixture.protocol())
        _, proposal = await self.proposal()
        item = proposal.items[0]
        manifest = self.manifest(item)
        changed = (
            manifest.model_copy(update={"protocol_snapshot_hashes": ()}),
            manifest.model_copy(
                update={"spec": manifest.spec.model_copy(update={"tool_bindings": ()})}
            ),
        )
        for candidate in changed:
            with self.subTest(manifest=candidate):
                with self.assertRaisesRegex(ValueError, "Manifest differs"):
                    await self.validator().validate(self.scope, item, candidate)

    async def test_resolved_policy_cannot_change_proposal_human_confirmation(self):
        await self.port.publish(self.fixture.protocol())
        _, proposal = await self.proposal()
        item = proposal.items[0]
        policy = item.requirement.policy_proposal.model_dump(mode="json")
        policy["human_confirmation"] = not policy["human_confirmation"]
        with self.assertRaisesRegex(ValueError, "Resolved policy differs"):
            await self.validator(policy=policy).validate(
                self.scope, item, self.manifest(item)
            )

    async def test_lifecycle_invalid_report_is_preserved_for_caller_to_block_write(
        self,
    ):
        await self.port.publish(self.fixture.protocol())
        _, proposal = await self.proposal()
        item = proposal.items[0]
        report, _ = await self.validator(invalid_policy=True).validate(
            self.scope, item, self.manifest(item)
        )
        self.assertFalse(report.valid)
        self.assertTrue(report.blockers)
