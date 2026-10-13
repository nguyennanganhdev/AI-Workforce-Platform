"""D3 missing-capability and pin faults against real SQL protocol providers."""

from agentscope.app.workforce.builder import RegistryCapabilitySelector
from agentscope.app.workforce.builder.async_capabilities import BuildRequirements
from agentscope.app.workforce.contracts import WorkforceContractError
from tests.workforce.builder.async_capabilities.fakes import Registry, tool
from ._fixtures import BuilderCase, Gate, write_after_validation


class MissingCapabilityTests(BuilderCase):
    async def test_missing_required_at_prepare_and_deleted_before_confirm(self):
        for tools in ((), (tool(available=False),)):
            with self.subTest(tools=tools):
                self.catalog.tools = tools
                service = self.service()
                proposal = await self.prepare(service)
                self.assertEqual(proposal.status, "needs_input")
                self.assertFalse(proposal.can_confirm)
                self.assertIn("MISSING_REQUIRED_CAPABILITY", self.codes(proposal))
                with self.assertRaises(ValueError):
                    await service.confirm(self.scope, proposal.proposal_id, 1)
        self.catalog.tools = (tool(),)
        service = self.service()
        proposal = await self.prepare(service)
        self.catalog.tools = ()
        refreshed = await service.confirm(self.scope, proposal.proposal_id, 1)
        self.assertEqual((refreshed.revision, refreshed.status), (2, "needs_input"))
        self.assertEqual(proposal.items[0].selection.covered, ("lookup",))

    @staticmethod
    def codes(proposal):
        return [b.code for i in proposal.items for b in i.selection.blockers]

    async def test_repeated_or_exhausted_cursor_fails_closed_with_bounded_queries(self):
        class CursorRegistry(Registry):
            async def list_available_tools(self, scope, **kwargs):
                self.queries.append(kwargs)
                cursor = kwargs.get("cursor")
                return (), "loop" if repeated else str(int(cursor or 0) + 1)

        for repeated in (True, False):
            with self.subTest(repeated=repeated):
                registry = CursorRegistry(self.scope, ())
                selector = RegistryCapabilitySelector(
                    registry, self.port, self.readiness, max_pages=3
                )
                service = self.service(selector=selector)
                proposal = await self.prepare(service)
                self.assertFalse(proposal.can_confirm)
                self.assertIn("MISSING_REQUIRED_CAPABILITY", self.codes(proposal))
                self.assertLessEqual(len(registry.queries), 3)

    async def test_query_dependency_faults_refresh_and_keep_tracking_requirement(self):
        req = self.fixture.tracking.agents[0]
        req = req.model_copy(
            update={
                "policy_proposal": req.policy_proposal.model_copy(
                    update={"timeout_behavior": "status_query"}
                )
            }
        )
        requirements = BuildRequirements(mode="single", agents=(req,))
        original = self.fixture.protocol(query=True)
        await self.port.publish(original)
        operation = tool("create", "external_operation")
        for changed in (
            (),
            (tool("status_query", version="query-v1", available=False),),
            (tool("unrelated", version="query-v1"),),
            (tool("status_query", "write", version="query-v1"),),
            (tool("status_query", version="query-v2"),),
        ):
            with self.subTest(changed=changed):
                self.catalog.tools = (
                    operation,
                    tool("status_query", version="query-v1"),
                )
                service = self.service(requirements)
                proposal = await self.prepare(service)
                self.assertTrue(proposal.can_confirm)
                self.catalog.tools = (operation, *changed)
                refreshed = await service.confirm(self.scope, proposal.proposal_id, 1)
                self.assertEqual(
                    (refreshed.revision, refreshed.status), (2, "needs_input")
                )
                self.assertEqual(refreshed.items[0].requirement, req)
                self.assertIn("MISSING_REQUIRED_CAPABILITY", self.codes(refreshed))

    async def test_disable_at_each_gate_preserves_old_pin_without_write(self):
        original = self.fixture.protocol()
        await self.port.publish(original)
        for stage in ("prepare", "confirm", "prewrite"):
            with self.subTest(stage=stage):
                await self.port.set_enabled("tool-v1", True, original.snapshot_ref)
                service = self.service(self.fixture.tracking)
                proposal = None
                if stage != "prepare":
                    proposal = await self.prepare(service)
                if stage == "prewrite":
                    proposal = await service.confirm(
                        self.scope, proposal.proposal_id, 1
                    )
                await self.port.set_enabled("tool-v1", False, original.snapshot_ref)
                drafts = self.drafts()
                with self.assertRaises(PermissionError):
                    if stage == "prepare":
                        await self.prepare(service)
                    elif stage == "confirm":
                        await service.confirm(self.scope, proposal.proposal_id, 1)
                    else:
                        # Replay confirmation is not a new pre-write authorization.
                        replay = await service.confirm(
                            self.scope, proposal.proposal_id, 1
                        )
                        item = replay.items[0]
                        await write_after_validation(
                            self.seam.validator(),
                            self.scope,
                            item,
                            self.seam.manifest(item),
                            drafts,
                        )
                self.assertEqual(drafts.calls, [])
                exact = await self.readiness.read(self.scope, original.snapshot_ref)
                self.assertEqual(exact.snapshot, original.snapshot_ref)
                self.assertEqual(exact.event_types, ("completed",))

    async def test_mapping_drift_refreshes_pin_and_requires_confirmation(self):
        original = self.fixture.protocol()
        await self.port.publish(original)
        service = self.service(self.fixture.tracking)
        proposal = await self.prepare(service)
        data = original.model_dump(mode="json")
        data["protocol_version"] = "2"
        data["event_mappings"]["completed"]["fact_fields"] = ["status", "extra"]
        # Canonical hash includes mapping; normalization stays outside Builder.
        revised = type(original).model_validate(data)
        self.assertNotEqual(
            original.snapshot_ref.schema_hash, revised.snapshot_ref.schema_hash
        )
        await self.port.publish(revised, original.snapshot_ref)
        refreshed = await service.confirm(self.scope, proposal.proposal_id, 1)
        self.assertEqual((refreshed.status, refreshed.revision), ("ready", 2))
        self.assertTrue(refreshed.notices)
        self.assertEqual(
            proposal.items[0].selection.protocols, (original.snapshot_ref,)
        )
        self.assertEqual(
            refreshed.items[0].selection.protocols, (revised.snapshot_ref,)
        )
        with self.assertRaises(WorkforceContractError):
            await service.confirm(self.scope, proposal.proposal_id, 1)
        confirmed = await service.confirm(self.scope, proposal.proposal_id, 2)
        self.assertEqual(confirmed.status, "confirmed")

    async def test_ordering_only_drift_keeps_old_metadata_and_blocks_stale_prewrite(
        self,
    ):
        original = self.fixture.protocol()
        await self.port.publish(original)
        service = self.service(self.fixture.tracking)
        proposal = await self.prepare(service)
        confirmed = await service.confirm(self.scope, proposal.proposal_id, 1)
        revised = type(original).model_validate(
            original.model_dump(mode="json")
            | {"protocol_version": "2", "ordering": "provider_version"}
        )
        await self.port.publish(revised, original.snapshot_ref)
        exact = await self.seam.provider.resolve_detail(
            self.scope, original.snapshot_ref
        )
        self.assertEqual(exact.ordering, "transition_only")
        self.assertNotEqual(
            exact.snapshot_ref.schema_hash, revised.snapshot_ref.schema_hash
        )
        item = confirmed.items[0]
        drafts = self.drafts()
        with self.assertRaises(WorkforceContractError):
            await write_after_validation(
                self.seam.validator(),
                self.scope,
                item,
                self.seam.manifest(item),
                drafts,
            )
        self.assertEqual(drafts.calls, [])

    async def test_invalid_schema_and_wrong_effect_are_not_confirmable(self):
        for descriptor, code in (
            (
                tool().model_copy(update={"input_schema": {"type": "invalid-type"}}),
                "INVALID_TOOL_SCHEMA",
            ),
            (tool(effect="write"), "TOOL_EFFECT_MISMATCH"),
        ):
            with self.subTest(code=code):
                self.catalog.tools = (descriptor,)
                proposal = await self.prepare(self.service())
                self.assertFalse(proposal.can_confirm)
                self.assertIn(code, self.codes(proposal))

    async def test_drift_after_confirm_stops_test_caller_before_draft_handoff(self):
        original = self.fixture.protocol()
        await self.port.publish(original)
        service = self.service(self.fixture.tracking)
        proposal = await self.prepare(service)
        confirmed = await service.confirm(self.scope, proposal.proposal_id, 1)
        item = confirmed.items[0]
        manifest = self.seam.manifest(item)
        revised = original.model_copy(
            update={"protocol_version": "2", "timeout_seconds": 7200}
        )
        await self.port.publish(revised, original.snapshot_ref)
        drafts = self.drafts()
        with self.assertRaises(WorkforceContractError):
            await write_after_validation(
                self.seam.validator(), self.scope, item, manifest, drafts
            )
        self.assertEqual(drafts.calls, [])
        self.assertEqual(
            manifest.protocol_snapshot_hashes, (original.snapshot_ref.schema_hash,)
        )

    async def test_invalid_report_stops_caller_and_valid_report_passes_exact_decision(
        self,
    ):
        await self.port.publish(self.fixture.protocol())
        service = self.service(self.fixture.tracking)
        proposal = await self.prepare(service)
        confirmed = await service.confirm(self.scope, proposal.proposal_id, 1)
        item = confirmed.items[0]
        manifest = self.seam.manifest(item)
        drafts = self.drafts()
        with self.assertRaises(ValueError):
            await write_after_validation(
                self.seam.validator(invalid_policy=True),
                self.scope,
                item,
                manifest,
                drafts,
            )
        self.assertEqual(drafts.calls, [])
        await write_after_validation(
            self.seam.validator(), self.scope, item, manifest, drafts
        )
        self.assertEqual(
            drafts.calls, [(self.scope, manifest, item.reuse_decision, None)]
        )

    async def test_scope_dimensions_and_forged_hash_are_rejected(self):
        original = self.fixture.protocol()
        await self.port.publish(original)
        for field in ("tenant_id", "domain_id", "area_id", "manager_account_id"):
            with self.subTest(field=field):
                other = self.scope.model_copy(update={field: "other"})
                with self.assertRaises(PermissionError):
                    await self.port.get_snapshot(other, "tool-v1")
                with self.assertRaises(LookupError):
                    await self.readiness.read(other, original.snapshot_ref)
        forged = original.snapshot_ref.model_copy(update={"schema_hash": "forged"})
        with self.assertRaises(ValueError):
            await self.readiness.read(self.scope, forged)

    async def test_protocol_drift_during_dependency_reads_is_not_hidden(self):
        original = self.fixture.protocol()
        await self.port.publish(original)
        gate = Gate()
        resolve = self.seam.provider.resolve_detail

        async def delayed(scope, ref):
            await gate.wait()
            return await resolve(scope, ref)

        from agentscope.app.workforce.builder import RegistryProtocolReadiness

        selector = RegistryCapabilitySelector(
            self.catalog, self.port, RegistryProtocolReadiness(delayed)
        )
        service = self.service(self.fixture.tracking, selector=selector)
        pending = await self.start(self.prepare(service))
        await gate.reached()
        revised = original.model_copy(
            update={"protocol_version": "2", "timeout_seconds": 7200}
        )
        await self.port.publish(revised, original.snapshot_ref)
        gate.release.set()
        (proposal,) = await self.finish(pending)
        self.assertEqual(
            proposal.items[0].selection.protocols, (original.snapshot_ref,)
        )
        refreshed = await service.confirm(self.scope, proposal.proposal_id, 1)
        self.assertEqual(refreshed.revision, 2)
        self.assertEqual(
            refreshed.items[0].selection.protocols, (revised.snapshot_ref,)
        )
