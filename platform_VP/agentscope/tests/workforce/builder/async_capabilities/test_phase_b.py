"""Behavioral Phase-B checks with real shared DTOs and Registry's handed-off fake."""

import asyncio
import json
from datetime import UTC, datetime
from pathlib import Path
import unittest

import jsonschema
from pydantic import ValidationError

from agentscope.app.workforce.builder import (
    CapabilitySelector,
    ExtractionError,
    ProposalService,
    RequirementExtractor,
)
from agentscope.app.workforce.builder._reuse_matcher import ReuseMatcher
from agentscope.app.workforce.builder.async_capabilities import (
    BuildRequirements,
    HandlingPolicyProposal,
)
from agentscope.app.workforce.contracts import (
    ActorContext,
    Scope,
    WorkforceContractError,
)
from agentscope.app.workforce.lifecycle.async_evaluation import phase_a_schema_bundle
from agentscope.app.workforce.registry.event_protocols import (
    AsyncToolProtocol,
    EventMapping,
)
from tests.workforce.registry.event_protocols.fakes import FakeAsyncProtocolPort
from tests.workforce.builder.async_capabilities.fakes import (
    Details,
    Model,
    Registry,
    Reuse,
    tool,
)


class PhaseBTests(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        self.scope = Scope(
            tenant_id="t", domain_id="d", area_id="a", manager_account_id="manager-a"
        )
        self.samples = json.loads(
            Path(__file__).with_name("samples.json").read_text(encoding="utf-8")
        )["valid"]
        self.sync = BuildRequirements.model_validate(self.samples[0]["payload"])
        self.tracking = BuildRequirements.model_validate(self.samples[2]["payload"])

    def protocol(self, *, events=True, query=False):
        return AsyncToolProtocol(
            protocol_id="p",
            protocol_version="1",
            tool_version_id="tool-v1",
            provider_integration_id="provider",
            effect="external_operation",
            result_mode="pending",
            completion_policy="explicit_close",
            client_reference_field="client_reference",
            external_job_id_field="job",
            status_field="status",
            terminal_statuses=("completed",),
            transitions={"pending": ("completed",)},
            timeout_seconds=3600,
            event_mappings=(
                {
                    "completed": EventMapping(
                        status="completed",
                        data_schema={"type": "object"},
                        fact_fields=("status",),
                    )
                }
                if events
                else {}
            ),
            status_query_tool_version_id="query-v1" if query else None,
        )

    def selector(self, protocol=None, *, details=True, tools=None):
        configs = [protocol] if protocol else []
        actor = ActorContext(
            kind="partner",
            actor_id="actor",
            partner_client_id="client",
            credential_id="key",
            credential_purpose="provider_events",
            authentication_source="fixture",
        )
        fake = FakeAsyncProtocolPort(
            self.scope, configs, actor, "provider", "inbox", datetime.now(UTC)
        )
        registry = Registry(
            self.scope,
            tools or (tool("create", "external_operation") if protocol else tool(),),
        )
        self.registry, self.protocols = registry, fake
        return CapabilitySelector(
            registry, fake, Details(self.scope, configs) if details else None
        )

    def build_output(self, requirements=None):
        return {
            "intent": "build",
            "requirements": (requirements or self.sync).model_dump(mode="json"),
        }

    def test_policy_matches_anh_and_rejects_old_fields(self):
        policy = self.tracking.agents[0].policy_proposal.model_dump(mode="json")
        schema = phase_a_schema_bundle()["schemas"]["AsyncHandlingPolicyProposal"]
        jsonschema.validate(policy, schema)
        for updates in (
            {"timeout_behavior": "query_status"},
            {"human_confirmation": "true"},
            {"timeout_seconds": 60},
            {"event_types": []},
            {"required_facts": [""]},
        ):
            invalid = {**policy, **updates}
            with self.subTest(updates=updates), self.assertRaises(ValidationError):
                HandlingPolicyProposal.model_validate(invalid)
        with self.assertRaises(ValidationError):
            HandlingPolicyProposal.model_validate(
                {k: v for k, v in policy.items() if k != "schema_version"}
            )

    async def test_extraction_retry_runtime_and_clarification(self):
        model = Model([{"intent": "build"}, self.build_output()])
        result = await RequirementExtractor(model).extract("Tạo agent tra cứu")
        self.assertEqual(result.intent, "build")
        self.assertEqual(len(model.calls), 2)
        for output in (
            {"intent": "runtime"},
            {"intent": "clarify", "questions": ["Tạo agent hay thực hiện công việc?"]},
        ):
            extracted = await RequirementExtractor(Model([output])).extract(
                "Đặt chuyến đi"
            )
            self.assertIsNone(extracted.requirements)
        with self.assertRaises(ExtractionError):
            await RequirementExtractor(Model([{}, {}])).extract("Tạo agent")

    async def test_extraction_timeout_and_input_budget(self):
        with self.assertRaises(ExtractionError):
            await RequirementExtractor(
                Model([self.build_output()], delay=0.05), timeout_seconds=0.001
            ).extract("Tạo agent")
        with self.assertRaises(ExtractionError):
            await RequirementExtractor(Model([]), max_input_chars=3).extract("too long")

    async def test_sync_and_immediate_create_need_no_protocol(self):
        for index, descriptor in (
            (0, tool()),
            (1, tool("create", "external_operation")),
        ):
            selector = self.selector(tools=(descriptor,))
            result = await selector.select(
                self.scope,
                BuildRequirements.model_validate(self.samples[index]["payload"]).agents[
                    0
                ],
            )
            self.assertFalse(result.blockers)
            self.assertEqual(result.tracking_channel, "none")
            self.assertFalse(result.protocols)

    async def test_pending_events_and_pinned_details(self):
        selector = self.selector(self.protocol())
        selected = await selector.select(self.scope, self.tracking.agents[0])
        self.assertFalse(selected.blockers)
        self.assertEqual(selected.tracking_channel, "provider_events")
        self.assertEqual(selected.completion_policy, "explicit_close")
        await selector.recheck(self.scope, self.tracking.agents[0], selected)

    async def test_tracking_create_only_missing_details_and_facts(self):
        for protocol, details, code in (
            (self.protocol(events=False), True, "MISSING_REQUIRED_CAPABILITY"),
            (self.protocol(), False, "PROTOCOL_DETAILS_REQUIRED"),
        ):
            selector = self.selector(protocol, details=details)
            selected = await selector.select(self.scope, self.tracking.agents[0])
            self.assertIn(code, [b.code for b in selected.blockers])
        req = self.tracking.agents[0]
        req = req.model_copy(
            update={
                "policy_proposal": req.policy_proposal.model_copy(
                    update={"required_facts": ("missing_fact",)}
                )
            }
        )
        selected = await self.selector(self.protocol()).select(self.scope, req)
        self.assertTrue(selected.blockers)

    async def test_status_query_binding_and_query_only_semantics(self):
        req = self.tracking.agents[0]
        req = req.model_copy(
            update={
                "policy_proposal": req.policy_proposal.model_copy(
                    update={"timeout_behavior": "status_query"}
                )
            }
        )
        tools = (
            tool("create", "external_operation"),
            tool("status_query", version="query-v1"),
        )
        selected = await self.selector(self.protocol(query=True), tools=tools).select(
            self.scope, req
        )
        self.assertFalse(selected.blockers)
        self.assertEqual(selected.tracking_channel, "status_query")
        selected = await self.selector(
            self.protocol(events=False, query=True), tools=tools
        ).select(self.scope, req)
        self.assertIn(
            "POLICY_EVENT_SEMANTICS_UNRESOLVED", [b.code for b in selected.blockers]
        )
        selected = await self.selector(
            self.protocol(query=True),
            tools=(tools[0], tool("status_query", version="query-v1", available=False)),
        ).select(self.scope, req)
        self.assertTrue(selected.blockers)

    async def test_pagination_optional_coverage_and_disabled_tools(self):
        selector = self.selector(
            tools=(tool(version="a", available=False), tool(version="b"))
        )
        result = await selector.select(self.scope, self.sync.agents[0])
        self.assertFalse(result.blockers)
        self.assertEqual(result.bindings[0].tool_version_id, "b")
        self.assertEqual(len(self.registry.queries), 2)
        missing = await self.selector(tools=(tool(available=False),)).select(
            self.scope, self.sync.agents[0]
        )
        self.assertEqual(missing.blockers[0].code, "MISSING_REQUIRED_CAPABILITY")

    async def test_reuse_choices_preserve_identity(self):
        for options, action in (
            ({"match": "same_business"}, "reuse"),
            ({"match": "same_business", "missing": ("tracking",)}, "revise"),
            ({"match": "same_business", "status": "draft"}, "resume"),
            ({"match": "uncertain"}, "clarify"),
            ({"match": "same_business", "status": "inactive"}, "repair"),
            ({}, "create"),
        ):
            decision, _, _ = await ReuseMatcher(Reuse(self.scope, **options)).propose(
                self.scope, self.sync.agents[0]
            )
            self.assertEqual(decision.action, action)
            if action in ("reuse", "revise", "resume", "repair"):
                self.assertEqual(decision.agent_id, "existing")
        decision, _, _ = await ReuseMatcher(
            Reuse(self.scope, match="same_business", fully_covered=False)
        ).propose(self.scope, self.tracking.agents[0])
        self.assertEqual(decision.action, "revise")

    async def test_proposal_confirmation_idempotency_scope_and_reuse(self):
        model = Model([self.build_output()])
        service = ProposalService(
            RequirementExtractor(model),
            self.selector(),
            Reuse(self.scope, match="same_business"),
        )
        proposal = await service.prepare(self.scope, "Tạo agent", "message")
        again = await service.prepare(self.scope, "Tạo agent", "message")
        self.assertEqual(proposal, again)
        self.assertEqual(len(model.calls), 1)
        with self.assertRaises(WorkforceContractError):
            await service.prepare(self.scope, "khác", "message")
        other = self.scope.model_copy(update={"manager_account_id": "manager-b"})
        with self.assertRaises(PermissionError):
            await service.confirm(other, proposal.proposal_id, 1)
        confirmed = await service.confirm(self.scope, proposal.proposal_id, 1)
        self.assertEqual(confirmed.status, "completed_reused")
        self.assertEqual(
            await service.confirm(self.scope, proposal.proposal_id, 1), confirmed
        )

    async def test_confirmation_drift_refresh_requires_reconfirmation(self):
        reuse = Reuse(self.scope)
        service = ProposalService(
            RequirementExtractor(Model([self.build_output()])), self.selector(), reuse
        )
        proposal = await service.prepare(self.scope, "Tạo agent", "message")
        reuse.revision = 2
        refreshed = await service.confirm(self.scope, proposal.proposal_id, 1)
        self.assertEqual(refreshed.revision, 2)
        self.assertEqual(refreshed.status, "ready")
        self.assertTrue(refreshed.notices)
        with self.assertRaises(WorkforceContractError):
            await service.confirm(self.scope, proposal.proposal_id, 1)
        confirmed = await service.confirm(self.scope, proposal.proposal_id, 2)
        self.assertEqual(confirmed.status, "confirmed")

    async def test_tool_drift_blocks_confirmation_and_cancel_is_scoped(self):
        selector = self.selector()
        service = ProposalService(
            RequirementExtractor(Model([self.build_output()])),
            selector,
            Reuse(self.scope),
        )
        proposal = await service.prepare(self.scope, "Tạo agent", "message")
        self.registry.tools = (tool(available=False),)
        refreshed = await service.confirm(self.scope, proposal.proposal_id, 1)
        self.assertEqual(refreshed.status, "needs_input")
        with self.assertRaises(ValueError):
            await service.confirm(self.scope, proposal.proposal_id, 2)
        await service.cancel(self.scope, proposal.proposal_id)
        with self.assertRaises(PermissionError):
            await service.confirm(self.scope, proposal.proposal_id, 2)

    async def test_identical_batch_items_collapse_and_concurrent_confirm_is_safe(self):
        agent = self.sync.agents[0]
        batch = BuildRequirements(
            mode="batch",
            agents=(agent, agent.model_copy(update={"agent_key": "duplicate"})),
        )
        service = ProposalService(
            RequirementExtractor(Model([self.build_output(batch)])),
            self.selector(),
            Reuse(self.scope),
        )
        proposal = await service.prepare(self.scope, "Tạo hai agent", "message")
        self.assertEqual(len(proposal.items), 1)
        self.assertEqual(proposal.items[0].duplicate_keys, ("duplicate",))
        confirmations = await asyncio.gather(
            *(service.confirm(self.scope, proposal.proposal_id, 1) for _ in range(2))
        )
        self.assertEqual(confirmations[0], confirmations[1])
        self.assertNotIn("group_id", confirmations[0].model_dump())

    async def test_revisioned_chat_edit_uses_previous_requirements(self):
        model = Model([self.build_output(), self.build_output()])
        service = ProposalService(
            RequirementExtractor(model), self.selector(), Reuse(self.scope)
        )
        original = await service.prepare(self.scope, "Tạo agent tra cứu", "one")
        edited = await service.prepare(
            self.scope,
            "Thêm phạm vi dữ liệu",
            "two",
            proposal_id=original.proposal_id,
            expected_revision=1,
        )
        self.assertEqual(edited.revision, 2)
        self.assertIn("Previous build requirements", str(model.calls[-1][0]))
        with self.assertRaises(WorkforceContractError):
            await service.prepare(
                self.scope,
                "stale",
                "three",
                proposal_id=original.proposal_id,
                expected_revision=1,
            )

    async def test_protocol_hash_drift_requires_refresh(self):
        selector = self.selector(self.protocol())
        selected = await selector.select(self.scope, self.tracking.agents[0])
        old = self.protocols.current["tool-v1"]
        self.protocols.current["tool-v1"] = old.model_copy(
            update={"schema_hash": "changed"}
        )
        # A metadata reader must not quietly resolve current content for the old pin.
        with self.assertRaises((WorkforceContractError, LookupError)):
            await selector.recheck(self.scope, self.tracking.agents[0], selected)

    async def test_optional_capability_is_visible_without_blocking(self):
        req = self.sync.agents[0].model_dump(mode="json")
        req["business_profile"]["capabilities"].append("optional")
        req["capabilities"].append(
            {"capability": "optional", "required": False, "reason": "nice to have"}
        )
        requirements = BuildRequirements.model_validate(
            {"mode": "single", "agents": [req]}
        )
        selected = await self.selector().select(self.scope, requirements.agents[0])
        self.assertFalse(selected.blockers)
        self.assertEqual(selected.missing_optional, ("optional",))

    async def test_build_level_questions_block_confirmation(self):
        output = self.build_output()
        output["questions"] = ["Which data scope should this agent use?"]
        service = ProposalService(
            RequirementExtractor(Model([output])), self.selector(), Reuse(self.scope)
        )
        proposal = await service.prepare(self.scope, "Create agent", "one")
        self.assertEqual(proposal.questions, tuple(output["questions"]))
        self.assertFalse(proposal.can_confirm)
        with self.assertRaises(ValueError):
            await service.confirm(self.scope, proposal.proposal_id, 1)

    async def test_duplicate_item_questions_are_not_discarded(self):
        agent = self.sync.agents[0]
        question = "Which data scope should this agent use?"
        batch = BuildRequirements(
            mode="batch",
            agents=(
                agent,
                agent.model_copy(
                    update={
                        "agent_key": "duplicate",
                        "clarification_questions": (question,),
                    }
                ),
            ),
        )
        service = ProposalService(
            RequirementExtractor(Model([self.build_output(batch)])),
            self.selector(),
            Reuse(self.scope),
        )
        proposal = await service.prepare(self.scope, "Create agents", "one")
        self.assertIn(question, proposal.questions)
        self.assertFalse(proposal.can_confirm)

    async def test_capability_drift_with_same_hash_refreshes_proposal(self):
        service = ProposalService(
            RequirementExtractor(Model([self.build_output()])),
            self.selector(),
            Reuse(self.scope),
        )
        proposal = await service.prepare(self.scope, "Create agent", "one")
        self.registry.tools = (tool("unrelated"),)
        refreshed = await service.confirm(self.scope, proposal.proposal_id, 1)
        self.assertEqual(refreshed.revision, 2)
        self.assertEqual(refreshed.status, "needs_input")

    async def test_returned_proposal_cannot_mutate_session_requirements(self):
        service = ProposalService(
            RequirementExtractor(Model([self.build_output()])),
            self.selector(),
            Reuse(self.scope),
        )
        proposal = await service.prepare(self.scope, "Create agent", "one")
        original = proposal.model_copy(deep=True)
        proposal.items[0].requirement.business_profile.input_contract["injected"] = True
        replay = await service.prepare(self.scope, "Create agent", "one")
        self.assertEqual(replay, original)
        replay.items[0].requirement.business_profile.output_contract["injected"] = True
        confirmed = await service.confirm(self.scope, proposal.proposal_id, 1)
        self.assertEqual(confirmed.items, original.items)
        confirmed.items[0].requirement.business_profile.input_contract[
            "injected"
        ] = True
        again = await service.confirm(self.scope, proposal.proposal_id, 1)
        self.assertEqual(again.items, original.items)

    async def test_deleted_tool_refreshes_instead_of_failing_confirmation(self):
        service = ProposalService(
            RequirementExtractor(Model([self.build_output()])),
            self.selector(),
            Reuse(self.scope),
        )
        proposal = await service.prepare(self.scope, "Create agent", "one")
        self.registry.tools = ()
        refreshed = await service.confirm(self.scope, proposal.proposal_id, 1)
        self.assertEqual(refreshed.revision, 2)
        self.assertEqual(refreshed.status, "needs_input")

    async def test_query_tool_must_advertise_status_query_capability(self):
        req = self.tracking.agents[0]
        req = req.model_copy(
            update={
                "policy_proposal": req.policy_proposal.model_copy(
                    update={"timeout_behavior": "status_query"}
                )
            }
        )
        selector = self.selector(
            self.protocol(query=True),
            tools=(
                tool("create", "external_operation"),
                tool("unrelated", version="query-v1"),
            ),
        )
        selected = await selector.select(self.scope, req)
        self.assertTrue(selected.blockers)

    async def test_effect_drift_cannot_confirm_a_read_only_create_binding(self):
        requirements = BuildRequirements.model_validate(self.samples[1]["payload"])
        service = ProposalService(
            RequirementExtractor(Model([self.build_output(requirements)])),
            self.selector(tools=(tool("create", "external_operation"),)),
            Reuse(self.scope),
        )
        proposal = await service.prepare(self.scope, "Create booking agent", "one")
        self.assertTrue(proposal.can_confirm)
        self.registry.tools = (tool("create", "read"),)
        refreshed = await service.confirm(self.scope, proposal.proposal_id, 1)
        self.assertEqual(refreshed.revision, 2)
        self.assertEqual(refreshed.status, "needs_input")


if __name__ == "__main__":
    unittest.main()
