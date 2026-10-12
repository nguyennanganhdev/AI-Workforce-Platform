"""D3 conservative reuse, missing metadata and mixed-batch regressions."""

from agentscope.app.workforce.builder._reuse_matcher import (
    ReuseMatcher,
    requirement_profile,
)
from agentscope.app.workforce.builder.async_capabilities import BuildRequirements
from agentscope.app.workforce.contracts import ReuseCandidate, WorkforceContractError
from tests.workforce.builder.async_capabilities.fakes import tool
from ._fixtures import BuilderCase, ControlledReuse


class ReuseTests(BuilderCase):
    def setUp(self):
        super().setUp()
        self.catalog.tools = (tool(),)

    def candidate(self, **changes):
        return ReuseCandidate.model_validate(
            {
                "agent_id": "existing",
                "version_id": "published",
                "match_type": "same_business",
                "reuse_status": "ready",
                "covered_requirements": ("lookup",),
                "reason": "Canonical scope-bound business comparison",
                **changes,
            }
        )

    async def test_all_reused_preserves_identity_and_exact_validation_arguments(self):
        reuse = ControlledReuse(self.scope, match="same_business")
        service = self.service(reuse=reuse)
        proposal = await self.prepare(service)
        confirmed = await service.confirm(self.scope, proposal.proposal_id, 1)
        self.assertEqual(confirmed.status, "completed_reused")
        decision = confirmed.items[0].reuse_decision
        self.assertEqual(
            (decision.action, decision.agent_id, decision.version_id),
            ("reuse", "existing", "published"),
        )
        self.assertEqual(
            reuse.validations,
            [
                (
                    self.scope,
                    (requirement_profile(self.fixture.sync.agents[0]),),
                    (decision,),
                    1,
                )
            ],
        )
        replay = await service.confirm(self.scope, proposal.proposal_id, 1)
        self.assertEqual(replay, confirmed)
        self.assertEqual(len(reuse.validations), 1)

    async def test_missing_capability_or_policy_revises_same_identity(self):
        req = self.fixture.tracking.agents[0]
        for options, missing in (
            ({"fully_covered": False}, "async_handling_policy"),
            ({"missing": ("extra_tracking",)}, "extra_tracking"),
        ):
            with self.subTest(options=options):
                decision, candidates, blockers = await ReuseMatcher(
                    ControlledReuse(self.scope, match="same_business", **options)
                ).propose(self.scope, req)
                self.assertEqual(
                    (decision.action, decision.agent_id), ("revise", "existing")
                )
                self.assertIn(missing, candidates[0].missing_requirements)
                self.assertFalse(blockers)

    async def test_candidate_missing_required_capability_is_revised_with_diagnosis(
        self,
    ):
        reuse = ControlledReuse(self.scope)
        reuse.candidates = (self.candidate(covered_requirements=()),)
        proposal = await self.prepare(self.service(reuse=reuse))
        item = proposal.items[0]
        self.assertEqual(
            (item.reuse_decision.action, item.reuse_decision.agent_id),
            ("revise", "existing"),
        )
        self.assertIn("lookup", item.candidates[0].missing_requirements)

    async def test_draft_resume_does_not_mark_result_as_completed_reused(self):
        reuse = ControlledReuse(self.scope, match="same_business", status="draft")
        service = self.service(reuse=reuse)
        proposal = await self.prepare(service)
        decision = proposal.items[0].reuse_decision
        self.assertEqual(
            (decision.action, decision.agent_id, decision.draft_id),
            ("resume", "existing", "draft"),
        )
        self.assertIsNone(decision.version_id)
        confirmed = await service.confirm(self.scope, proposal.proposal_id, 1)
        self.assertEqual(confirmed.status, "confirmed")

    async def test_draft_candidate_without_draft_reference_blocks_even_with_old_version(
        self,
    ):
        for version, missing in ((None, ()), ("published", ()), (None, ("lookup",))):
            with self.subTest(version=version, missing=missing):
                reuse = ControlledReuse(self.scope)
                reuse.candidates = (
                    self.candidate(
                        reuse_status="draft",
                        version_id=version,
                        draft_id=None,
                        missing_requirements=missing,
                    ),
                )
                service = self.service(reuse=reuse)
                proposal = await self.prepare(service)
                self.assertEqual(proposal.items[0].reuse_decision.action, "clarify")
                self.assertFalse(proposal.can_confirm)
                self.assertIn(
                    "CANDIDATE_METADATA_REQUIRED",
                    [b.code for b in proposal.items[0].blockers],
                )
                with self.assertRaises(ValueError):
                    await service.confirm(self.scope, proposal.proposal_id, 1)

    async def test_blocked_inactive_and_missing_published_metadata_never_create_clone(
        self,
    ):
        for changes, action, code in (
            ({"reuse_status": "inactive"}, "repair", "REUSE_BLOCKED"),
            ({"reuse_status": "blocked"}, "repair", "REUSE_BLOCKED"),
            ({"blockers": ("credential_unavailable",)}, "repair", "REUSE_BLOCKED"),
            ({"version_id": None}, "clarify", "CANDIDATE_METADATA_REQUIRED"),
        ):
            with self.subTest(changes=changes):
                reuse = ControlledReuse(self.scope)
                reuse.candidates = (self.candidate(**changes),)
                proposal = await self.prepare(self.service(reuse=reuse))
                item = proposal.items[0]
                self.assertEqual(
                    (item.reuse_decision.action, item.reuse_decision.agent_id),
                    (action, "existing"),
                )
                self.assertFalse(proposal.can_confirm)
                self.assertIn(code, [b.code for b in item.blockers])

    async def test_ambiguous_partial_and_uncertain_candidates_require_clarification(
        self,
    ):
        first = self.candidate()
        for candidates, code in (
            (
                (first, first.model_copy(update={"agent_id": "other"})),
                "AMBIGUOUS_REUSE",
            ),
            ((self.candidate(match_type="partial_overlap"),), "CLARIFICATION_REQUIRED"),
            ((self.candidate(match_type="uncertain"),), "CLARIFICATION_REQUIRED"),
        ):
            with self.subTest(code=code):
                reuse = ControlledReuse(self.scope)
                reuse.candidates = candidates
                proposal = await self.prepare(self.service(reuse=reuse))
                self.assertFalse(proposal.can_confirm)
                self.assertEqual(proposal.items[0].reuse_decision.action, "clarify")
                self.assertIsNone(proposal.items[0].reuse_decision.agent_id)
                self.assertIn(code, [b.code for b in proposal.items[0].blockers])

    async def test_different_business_is_not_reused_from_display_similarity(self):
        reuse = ControlledReuse(self.scope)
        reuse.candidates = (self.candidate(match_type="different"),)
        proposal = await self.prepare(self.service(reuse=reuse))
        decision = proposal.items[0].reuse_decision
        self.assertEqual(decision.action, "create")
        self.assertIsNone(decision.agent_id)
        self.assertTrue(proposal.can_confirm)

    async def test_mixed_batch_keeps_reuse_create_and_duplicate_coverage_separate(self):
        first = self.fixture.sync.agents[0]
        second = first.model_copy(
            update={
                "agent_key": "independent",
                "business_profile": first.business_profile.model_copy(
                    update={"objective": "Different responsibility"}
                ),
            }
        )
        batch = BuildRequirements(
            mode="batch",
            agents=(
                first,
                first.model_copy(update={"agent_key": "duplicate"}),
                second,
            ),
        )

        class MixedReuse(ControlledReuse):
            async def find_candidates(self, scope, profile, include_drafts=True):
                check = await super().find_candidates(scope, profile, include_drafts)
                if profile.objective == "Different responsibility":
                    return check.model_copy(update={"candidates": ()})
                return check

        reuse = MixedReuse(self.scope, match="same_business")
        service = self.service(batch, reuse=reuse)
        proposal = await self.prepare(service)
        self.assertEqual(len(proposal.items), 2)
        self.assertEqual(proposal.items[0].duplicate_keys, ("duplicate",))
        self.assertEqual(
            [i.reuse_decision.action for i in proposal.items], ["reuse", "create"]
        )
        self.assertEqual(
            [i.selection.covered for i in proposal.items], [("lookup",), ("lookup",)]
        )
        confirmed = await service.confirm(self.scope, proposal.proposal_id, 1)
        self.assertEqual(confirmed.status, "confirmed")
        self.assertEqual(len(reuse.validations), 2)

    async def test_conflicting_batch_policy_is_not_collapsed_or_confirmed(self):
        first = self.fixture.sync.agents[0]
        second = first.model_copy(
            update={
                "agent_key": "different-policy",
                "business_profile": type(first.business_profile).model_validate(
                    first.business_profile.model_dump(mode="json")
                    | {"execution_policy": "require_approval"}
                ),
            }
        )
        proposal = await self.prepare(
            self.service(BuildRequirements(mode="batch", agents=(first, second)))
        )
        self.assertEqual(len(proposal.items), 2)
        self.assertFalse(proposal.can_confirm)
        for item in proposal.items:
            self.assertIn("BATCH_REQUIREMENT_CONFLICT", [b.code for b in item.blockers])

    async def test_changed_reuse_availability_refreshes_to_repair_not_create(self):
        reuse = ControlledReuse(self.scope, match="same_business")
        service = self.service(reuse=reuse)
        proposal = await self.prepare(service)
        reuse.status, reuse.revision = "inactive", 2
        refreshed = await service.confirm(self.scope, proposal.proposal_id, 1)
        self.assertEqual((refreshed.revision, refreshed.status), (2, "needs_input"))
        self.assertEqual(refreshed.items[0].reuse_decision.agent_id, "existing")
        self.assertEqual(refreshed.items[0].reuse_decision.action, "repair")
        self.assertEqual(proposal.items[0].reuse_decision.action, "reuse")
        with self.assertRaises(WorkforceContractError):
            await service.confirm(self.scope, proposal.proposal_id, 1)
