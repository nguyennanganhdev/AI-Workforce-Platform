# -*- coding: utf-8 -*-
"""Validate BHN review artifacts, not production or shared DTO contracts.

No AgentScope runtime import, network request or provider operation occurs.
Promote these cases to Foundation's exported schema after owner agreement.
"""

import copy
import json
from pathlib import Path
import unittest

from jsonschema import Draft202012Validator, FormatChecker


ARTIFACTS = (
    Path(__file__).resolve().parents[4]
    / "docs/workforce/handoffs/bui-huu-nghia/phase_a"
)


class PhaseASchemaTest(unittest.TestCase):
    """Exercise the proposed schema with positive and adversarial payloads."""

    @classmethod
    def setUpClass(cls):
        cls.schema = json.loads(
            (ARTIFACTS / "builder.schema.json").read_text(encoding="utf-8"),
        )
        cls.samples = json.loads(
            (ARTIFACTS / "samples.json").read_text(encoding="utf-8"),
        )

    def validator(self, definition):
        """Resolve every definition locally; no external schema retrieval."""
        return Draft202012Validator(
            {
                "$schema": self.schema["$schema"],
                "$ref": f"#/$defs/{definition}",
                "$defs": self.schema["$defs"],
            },
            format_checker=FormatChecker(),
        )

    def assert_invalid(self, definition, payload):
        self.assertTrue(
            list(self.validator(definition).iter_errors(payload)),
            f"Unexpectedly accepted {definition}: {payload}",
        )

    def policy(self, name):
        return copy.deepcopy(self.samples["policies"][name])

    def test_schema_is_well_formed(self):
        Draft202012Validator.check_schema(self.schema)

    def test_generation_request(self):
        self.validator("GenerationRequest").validate(
            self.samples["generation_request"],
        )

    def test_single_agent_output(self):
        self.validator("SingleAgentRequirements").validate(
            self.samples["single_agent_requirements"],
        )

    def test_all_policy_samples(self):
        for name, policy in self.samples["policies"].items():
            with self.subTest(name=name):
                self.validator("AsyncHandlingPolicy").validate(policy)

    def test_sync_lookup_without_event_channel(self):
        policy = self.samples["single_agent_requirements"]["policy_candidate"]
        self.assertEqual(policy["tracking"], "none")
        self.assertEqual(policy["event_types"], [])
        self.validator("AsyncHandlingPolicy").validate(policy)

    def test_confirmed_booking_without_polling(self):
        policy = self.policy("booking_confirmed")
        self.assertEqual(policy["tracking"], "none")
        self.assertIsNone(policy["max_wait_seconds"])
        self.validator("AsyncHandlingPolicy").validate(policy)

    def test_query_only_without_provider_event(self):
        policy = self.policy("pending_query_only")
        self.assertEqual(policy["event_types"], [])
        self.validator("AsyncHandlingPolicy").validate(policy)

    def test_interactive_read_does_not_force_auto_close(self):
        policy = self.policy("interactive_read")
        self.validator("AsyncHandlingPolicy").validate(policy)

    def test_side_effect_cannot_auto_close(self):
        for effect in ("write", "booking", "cancel"):
            with self.subTest(effect=effect):
                policy = copy.deepcopy(
                    self.samples["single_agent_requirements"]["policy_candidate"],
                )
                policy["effect"] = effect
                self.assert_invalid("AsyncHandlingPolicy", policy)

    def test_unknown_effect_not_publishable_policy(self):
        policy = self.policy("booking_confirmed")
        policy["effect"] = "unknown"
        self.assert_invalid("AsyncHandlingPolicy", policy)

    def test_pending_tracking_cannot_claim_create_is_completion(self):
        policy = self.policy("pending_provider_event")
        policy["completion"]["kind"] = "operation_accepted"
        self.assert_invalid("AsyncHandlingPolicy", policy)

    def test_tracking_requires_positive_timeout(self):
        for seconds in (None, 0, -1, True, "3600"):
            with self.subTest(seconds=seconds):
                policy = self.policy("pending_provider_event")
                policy["max_wait_seconds"] = seconds
                self.assert_invalid("AsyncHandlingPolicy", policy)

    def test_tracking_requires_verified_facts(self):
        policy = self.policy("pending_provider_event")
        policy["required_facts"] = []
        self.assert_invalid("AsyncHandlingPolicy", policy)

    def test_provider_events_require_event_types(self):
        policy = self.policy("pending_provider_event")
        policy["event_types"] = []
        self.assert_invalid("AsyncHandlingPolicy", policy)

    def test_query_fallback_requires_query_channel(self):
        policy = self.policy("pending_provider_event")
        policy["timeout_behavior"] = "query_then_attention"
        self.assert_invalid("AsyncHandlingPolicy", policy)

    def test_sync_policy_cannot_contain_tracking_timer(self):
        policy = self.policy("booking_confirmed")
        policy["max_wait_seconds"] = 3600
        self.assert_invalid("AsyncHandlingPolicy", policy)

    def test_terminal_success_requires_predicate(self):
        policy = self.policy("booking_confirmed")
        policy["completion"]["all_of"] = []
        self.assert_invalid("AsyncHandlingPolicy", policy)

    def test_policy_rejects_runtime_identity_and_endpoint(self):
        for field in (
            "workflow_id", "job_id", "ticket_id", "group_id",
            "external_ticket_id", "endpoint", "roster",
        ):
            with self.subTest(field=field):
                policy = self.policy("pending_provider_event")
                policy[field] = "forbidden"
                self.assert_invalid("AsyncHandlingPolicy", policy)

    def test_completion_does_not_accept_executable_expression(self):
        policy = self.policy("booking_confirmed")
        policy["completion"]["expression"] = "eval(untrusted_payload)"
        self.assert_invalid("AsyncHandlingPolicy", policy)

    def test_body_rejects_client_scope_or_secret(self):
        for field in ("scope", "manager_account_id", "api_key"):
            with self.subTest(field=field):
                body = copy.deepcopy(self.samples["generation_request"])
                body[field] = "forbidden"
                self.assert_invalid("GenerationRequest", body)

    def test_generation_model_selection_is_required(self):
        body = copy.deepcopy(self.samples["generation_request"])
        del body["generation_model"]
        self.assert_invalid("GenerationRequest", body)

    def test_model_output_cannot_overwrite_generation_selection(self):
        output = copy.deepcopy(self.samples["single_agent_requirements"])
        output["generation_model"] = self.samples["generation_request"][
            "generation_model"
        ]
        self.assert_invalid("SingleAgentRequirements", output)

    def test_model_selection_rejects_embedded_secret_at_top_level(self):
        body = copy.deepcopy(self.samples["generation_request"])
        body["generation_model"]["api_key"] = "forbidden"
        self.assert_invalid("GenerationRequest", body)

    def test_invalid_id_revision_or_blank_message(self):
        for field, value in (
            ("client_message_id", "not-a-uuid"),
            ("expected_revision", -1),
            ("expected_revision", True),
            ("message", "   "),
        ):
            with self.subTest(field=field, value=value):
                body = copy.deepcopy(self.samples["generation_request"])
                body[field] = value
                self.assert_invalid("GenerationRequest", body)

    def test_batch_not_accepted_by_single_slice(self):
        body = copy.deepcopy(self.samples["generation_request"])
        body["mode"] = "batch"
        self.assert_invalid("GenerationRequest", body)

    def test_clarification_can_leave_policy_unresolved(self):
        output = copy.deepcopy(self.samples["single_agent_requirements"])
        output.update(
            intent="clarify", policy_candidate=None,
            questions=["Chỉ tạo công việc hay theo dõi đến hoàn tất?"],
        )
        output["requirements"][0]["tracking_goal"] = "unspecified"
        self.validator("SingleAgentRequirements").validate(output)

    def test_clarification_requires_question(self):
        output = copy.deepcopy(self.samples["single_agent_requirements"])
        output.update(intent="clarify", policy_candidate=None, questions=[])
        self.assert_invalid("SingleAgentRequirements", output)

    def test_build_cannot_hide_unresolved_requirement(self):
        output = copy.deepcopy(self.samples["single_agent_requirements"])
        output["requirements"][0]["tracking_goal"] = "unspecified"
        self.assert_invalid("SingleAgentRequirements", output)

    def test_unknown_objective_does_not_force_invented_agent_metadata(self):
        output = copy.deepcopy(self.samples["single_agent_requirements"])
        output.update(
            intent="clarify", name=None, description=None, objective=None,
            responsibilities=[], requirements=[], resource_selections=[],
            runtime_model_option_id=None, policy_candidate=None,
            questions=["Bạn muốn agent hỗ trợ công việc gì?"],
        )
        self.validator("SingleAgentRequirements").validate(output)
        output.update(intent="build", questions=[])
        self.assert_invalid("SingleAgentRequirements", output)

    def test_runtime_request_can_be_classified_without_build(self):
        output = copy.deepcopy(self.samples["single_agent_requirements"])
        output.update(
            intent="runtime_request", policy_candidate=None,
            resource_selections=[],
        )
        self.validator("SingleAgentRequirements").validate(output)
        output["policy_candidate"] = self.policy("booking_confirmed")
        self.assert_invalid("SingleAgentRequirements", output)

    def test_sample_references_are_internally_consistent(self):
        """Check sample integrity only; this does not verify real tool access."""
        output = self.samples["single_agent_requirements"]
        ids = {item["requirement_id"] for item in output["requirements"]}
        self.assertEqual(len(ids), len(output["requirements"]))
        for resource in output["resource_selections"]:
            self.assertTrue(set(resource["covers_requirements"]) <= ids)
        for policy in self.samples["policies"].values():
            self.assertTrue(
                {item["fact"] for item in policy["completion"]["all_of"]}
                <= set(policy["required_facts"]),
            )


if __name__ == "__main__":
    unittest.main()
