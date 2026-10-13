"""D3 deterministic local races and two-instance canonical-port conflicts."""

import asyncio

from agentscope.app.workforce.builder import (
    ExtractionError,
    ProposalService,
    RequirementExtractor,
)
from agentscope.app.workforce.contracts import (
    WorkforceContractError,
    WorkforceErrorCode,
)
from tests.workforce.builder.async_capabilities.fakes import Model, Registry, tool
from ._fixtures import BuilderCase, ControlledReuse, Gate, GatedModel


class ConcurrentBuildTests(BuilderCase):
    def setUp(self):
        super().setUp()
        self.catalog.tools = (tool(),)

    def output(self):
        return self.fixture.build_output(self.fixture.sync)

    async def test_same_message_serializes_and_conflicting_payload_is_rejected(self):
        for other_message in ("Build agent", "Different input"):
            with self.subTest(other_message=other_message):
                gate = Gate()
                model = GatedModel([self.output()], gate)
                service = self.service(model=model)
                first = await self.start(self.prepare(service))
                await gate.reached()
                second = await self.start(
                    service.prepare(self.scope, other_message, "message")
                )
                gate.release.set()
                original, replay = await self.finish(first, second)
                self.assertEqual(len(model.calls), 1)
                if other_message == "Build agent":
                    self.assertEqual(original, replay)
                else:
                    self.assertIsInstance(replay, WorkforceContractError)
                    self.assertEqual(
                        replay.code, WorkforceErrorCode.IDEMPOTENCY_CONFLICT
                    )

    async def test_two_edits_same_revision_have_one_winner(self):
        model = Model([self.output()])
        service = self.service(model=model)
        proposal = await self.prepare(service)
        gate = Gate()
        edited_model = GatedModel([self.output()], gate)
        service.extractor = RequirementExtractor(edited_model)
        kwargs = {"proposal_id": proposal.proposal_id, "expected_revision": 1}
        first = await self.start(self.prepare(service, "edit-a", **kwargs))
        await gate.reached()
        second = await self.start(self.prepare(service, "edit-b", **kwargs))
        gate.release.set()
        updated, conflict = await self.finish(first, second)
        self.assertEqual(updated.revision, 2)
        self.assertIsInstance(conflict, WorkforceContractError)
        self.assertEqual(conflict.code, WorkforceErrorCode.REVISION_CONFLICT)
        self.assertEqual(len(edited_model.calls), 1)
        current = await service.confirm(self.scope, proposal.proposal_id, 2)
        self.assertEqual(current.items, updated.items)

    async def test_two_confirms_replay_one_reuse_validation(self):
        reuse = ControlledReuse(self.scope, match="same_business")
        reuse.gate = Gate()
        service = self.service(reuse=reuse)
        proposal = await self.prepare(service)
        first = await self.start(service.confirm(self.scope, proposal.proposal_id, 1))
        await reuse.gate.reached()
        second = await self.start(service.confirm(self.scope, proposal.proposal_id, 1))
        reuse.gate.release.set()
        winner, replay = await self.finish(first, second)
        self.assertEqual(winner, replay)
        self.assertEqual(winner.status, "completed_reused")
        self.assertEqual(len(reuse.validations), 1)

    async def test_edit_then_confirm_old_revision_does_not_overwrite(self):
        service = self.service()
        proposal = await self.prepare(service)
        gate = Gate()
        service.extractor = RequirementExtractor(GatedModel([self.output()], gate))
        edit = await self.start(
            self.prepare(
                service, "edit", proposal_id=proposal.proposal_id, expected_revision=1
            )
        )
        await gate.reached()
        confirm = await self.start(service.confirm(self.scope, proposal.proposal_id, 1))
        gate.release.set()
        updated, stale = await self.finish(edit, confirm)
        self.assertEqual((updated.revision, updated.status), (2, "ready"))
        self.assertEqual(stale.code, WorkforceErrorCode.REVISION_CONFLICT)

    async def test_confirm_then_edit_cannot_modify_confirmed_proposal(self):
        reuse = ControlledReuse(self.scope)
        reuse.gate = Gate()
        model = Model([self.output()])
        service = self.service(reuse=reuse, model=model)
        proposal = await self.prepare(service)
        confirm = await self.start(service.confirm(self.scope, proposal.proposal_id, 1))
        await reuse.gate.reached()
        edit = await self.start(
            self.prepare(
                service, "edit", proposal_id=proposal.proposal_id, expected_revision=1
            )
        )
        reuse.gate.release.set()
        confirmed, conflict = await self.finish(confirm, edit)
        self.assertEqual(confirmed.status, "confirmed")
        self.assertEqual(conflict.code, WorkforceErrorCode.REVISION_CONFLICT)
        self.assertEqual(len(model.calls), 1)

    async def test_cancel_queued_before_confirm_does_not_resurrect_proposal(self):
        service = self.service()
        proposal = await self.prepare(service)
        gate = Gate()
        service.extractor = RequirementExtractor(GatedModel([self.output()], gate))
        edit = await self.start(
            self.prepare(
                service, "edit", proposal_id=proposal.proposal_id, expected_revision=1
            )
        )
        await gate.reached()
        cancel = await self.start(service.cancel(self.scope, proposal.proposal_id))
        confirm = await self.start(service.confirm(self.scope, proposal.proposal_id, 2))
        gate.release.set()
        updated, cancelled, rejected = await self.finish(edit, cancel, confirm)
        self.assertEqual(updated.revision, 2)
        self.assertIsNone(cancelled)
        self.assertIsInstance(rejected, PermissionError)
        with self.assertRaises(PermissionError):
            await service.confirm(self.scope, proposal.proposal_id, 2)

    async def test_confirm_then_cancel_removes_entry_without_extra_confirmation(self):
        reuse = ControlledReuse(self.scope)
        reuse.gate = Gate()
        service = self.service(reuse=reuse)
        proposal = await self.prepare(service)
        confirm = await self.start(service.confirm(self.scope, proposal.proposal_id, 1))
        await reuse.gate.reached()
        cancel = await self.start(service.cancel(self.scope, proposal.proposal_id))
        reuse.gate.release.set()
        confirmed, cancelled = await self.finish(confirm, cancel)
        self.assertEqual(confirmed.status, "confirmed")
        self.assertIsNone(cancelled)
        with self.assertRaises(PermissionError):
            await service.confirm(self.scope, proposal.proposal_id, 1)
        self.assertEqual(len(reuse.validations), 1)

    async def test_cancel_queued_before_edit_does_not_recreate_removed_proposal(self):
        reuse = ControlledReuse(self.scope)
        reuse.gate = Gate()
        model = Model([self.output()])
        service = self.service(reuse=reuse, model=model)
        proposal = await self.prepare(service)
        confirm = await self.start(service.confirm(self.scope, proposal.proposal_id, 1))
        await reuse.gate.reached()
        cancel = await self.start(service.cancel(self.scope, proposal.proposal_id))
        edit = await self.start(
            self.prepare(
                service, "edit", proposal_id=proposal.proposal_id, expected_revision=1
            )
        )
        reuse.gate.release.set()
        confirmed, cancelled, rejected = await self.finish(confirm, cancel, edit)
        self.assertEqual(confirmed.status, "confirmed")
        self.assertIsNone(cancelled)
        self.assertIsInstance(rejected, PermissionError)
        self.assertEqual(len(model.calls), 1)
        with self.assertRaises(PermissionError):
            await service.confirm(self.scope, proposal.proposal_id, 1)

    async def test_two_instances_refresh_each_canonical_conflict_and_require_reconfirmation(
        self,
    ):
        for code, status, action, result_status in (
            (
                WorkforceErrorCode.AGENT_ALREADY_EXISTS,
                "ready",
                "reuse",
                "completed_reused",
            ),
            (
                WorkforceErrorCode.AGENT_BUILD_IN_PROGRESS,
                "draft",
                "resume",
                "confirmed",
            ),
            (
                WorkforceErrorCode.REUSE_DECISION_STALE,
                "ready",
                "reuse",
                "completed_reused",
            ),
        ):
            with self.subTest(code=code):
                reuse = ControlledReuse(self.scope)
                first, second = self.service(reuse=reuse), self.service(reuse=reuse)
                a, b = await self.finish(
                    await self.start(self.prepare(first)),
                    await self.start(self.prepare(second)),
                )
                self.assertNotEqual(a.proposal_id, b.proposal_id)
                self.assertEqual(a.items[0].reuse_decision.action, "create")
                reuse.gate = Gate()
                confirming = await self.start(
                    second.confirm(self.scope, b.proposal_id, 1)
                )
                await reuse.gate.reached()
                # An external canonical writer has won; this double writes no DB rows.
                reuse.match, reuse.status, reuse.revision = "same_business", status, 2
                reuse.conflict = code
                reuse.gate.release.set()
                (refreshed,) = await self.finish(confirming)
                self.assertEqual((refreshed.status, refreshed.revision), ("ready", 2))
                self.assertTrue(refreshed.notices)
                self.assertEqual(
                    (
                        refreshed.items[0].reuse_decision.action,
                        refreshed.items[0].reuse_decision.agent_id,
                    ),
                    (action, "existing"),
                )
                self.assertEqual(
                    refreshed.items[0].reuse_decision.expected_catalog_revision, 2
                )
                with self.assertRaises(WorkforceContractError) as stale:
                    await second.confirm(self.scope, b.proposal_id, 1)
                self.assertEqual(
                    stale.exception.code, WorkforceErrorCode.REVISION_CONFLICT
                )
                confirmed = await second.confirm(self.scope, b.proposal_id, 2)
                self.assertEqual(confirmed.status, result_status)
                self.assertEqual(a.items[0].reuse_decision.action, "create")

    async def test_extraction_cancel_failure_and_timeout_allow_same_message_retry(self):
        gate = Gate()
        service = self.service(model=GatedModel([self.output()], gate))
        pending = await self.start(self.prepare(service))
        await gate.reached()
        pending.cancel()
        (cancelled,) = await self.finish(pending)
        self.assertIsInstance(cancelled, asyncio.CancelledError)
        service.extractor = RequirementExtractor(Model([{}, {}, self.output()]))
        with self.assertRaises(ExtractionError):
            await self.prepare(service)
        timeout_gate = Gate()
        service.extractor = RequirementExtractor(
            GatedModel([self.output()], timeout_gate), timeout_seconds=0.01
        )
        with self.assertRaises(ExtractionError):
            await self.prepare(service)
        service.extractor = RequirementExtractor(Model([self.output()]))
        proposal = await self.prepare(service)
        self.assertEqual((proposal.revision, proposal.status), (1, "ready"))

    async def test_port_failure_during_prepare_does_not_cache_success(self):
        reuse = ControlledReuse(self.scope)
        reuse.find_failure = ConnectionError("test repository unavailable")
        model = Model([self.output(), self.output()])
        service = self.service(reuse=reuse, model=model)
        with self.assertRaises(ConnectionError):
            await self.prepare(service)
        reuse.find_failure = None
        proposal = await self.prepare(service)
        self.assertEqual(proposal.status, "ready")
        self.assertEqual(len(model.calls), 2)

    async def test_scope_isolation_for_same_message_and_business_in_one_service(self):
        from agentscope.app.workforce.builder import RegistryCapabilitySelector

        other = self.scope.model_copy(update={"manager_account_id": "manager-b"})
        catalogs = {
            self.scope.manager_account_id: Registry(self.scope, (tool(),)),
            other.manager_account_id: Registry(other, (tool(),)),
        }
        reuses = {
            self.scope.manager_account_id: ControlledReuse(
                self.scope, match="same_business"
            ),
            other.manager_account_id: ControlledReuse(other),
        }

        class ScopedRegistry:
            def __getattr__(inner, name):
                async def call(scope, *args, **kwargs):
                    return await getattr(catalogs[scope.manager_account_id], name)(
                        scope, *args, **kwargs
                    )

                return call

        class ScopedReuse:
            def __getattr__(inner, name):
                async def call(scope, *args, **kwargs):
                    return await getattr(reuses[scope.manager_account_id], name)(
                        scope, *args, **kwargs
                    )

                return call

        service = ProposalService(
            RequirementExtractor(Model([self.output(), self.output()])),
            RegistryCapabilitySelector(ScopedRegistry(), self.port, self.readiness),
            ScopedReuse(),
        )
        a = await self.prepare(service)
        b = await service.prepare(other, "Build agent", "message")
        self.assertNotEqual(a.proposal_id, b.proposal_id)
        self.assertEqual(
            [a.items[0].reuse_decision.action, b.items[0].reuse_decision.action],
            ["reuse", "create"],
        )
        for proposal, wrong in ((a, other), (b, self.scope)):
            with self.assertRaises(PermissionError):
                await service.confirm(wrong, proposal.proposal_id, 1)
            with self.assertRaises(PermissionError):
                await service.cancel(wrong, proposal.proposal_id)
        await service.cancel(self.scope, a.proposal_id)
        confirmed = await service.confirm(other, b.proposal_id, 1)
        self.assertEqual(confirmed.status, "confirmed")
