import json
from pathlib import Path
import unittest

from jsonschema import Draft202012Validator, ValidationError

from agentscope.app.workforce.contracts import EvaluationSnapshot
from agentscope.app.workforce.lifecycle import EvaluationRecord
from agentscope.app.workforce.lifecycle.async_evaluation import (
    phase_a_schema_bundle,
)
from agentscope.app.workforce.lifecycle.async_evaluation._validation import (
    validate_policy,
)


class PhaseAContractsTests(unittest.TestCase):
    def test_handoff_artifact_has_no_schema_drift(self) -> None:
        root = Path(__file__).resolve().parents[4]
        artifact = (
            root / "docs/workforce/handoffs/pho-tien-anh/phase_a/schemas.json"
        )
        self.assertEqual(
            json.loads(artifact.read_text()), phase_a_schema_bundle()
        )

    def test_export_uses_current_shared_snapshot(self) -> None:
        bundle = phase_a_schema_bundle()
        schemas = bundle["schemas"]
        self.assertEqual(
            schemas["EvaluationSnapshot"],
            EvaluationSnapshot.model_json_schema(),
        )
        self.assertEqual(
            schemas["EvaluationRecord"], EvaluationRecord.model_json_schema()
        )
        for schema in schemas.values():
            Draft202012Validator.check_schema(schema)
        scope = schemas["EvaluationSnapshot"]["$defs"]["Scope"]
        self.assertEqual(
            set(scope["required"]),
            {"tenant_id", "domain_id", "area_id", "manager_account_id"},
        )
        required = schemas["EvaluationRecord"]["required"]
        for field in (
            "snapshot",
            "report",
            "validation",
            "test_context",
            "runtime_profile",
            "suite_hash",
            "gate_config",
        ):
            self.assertIn(field, required)

    def test_policy_proposal_matches_supported_validation(self) -> None:
        schema = phase_a_schema_bundle()["schemas"][
            "AsyncHandlingPolicyProposal"
        ]
        validator = Draft202012Validator(schema)
        policy = {
            "schema_version": "1",
            "capabilities": ["repair.track"],
            "event_types": ["completed"],
            "required_facts": ["status"],
            "completion_condition": "status == completed",
            "human_confirmation": True,
            "timeout_behavior": "needs_attention",
        }
        validator.validate(policy)
        self.assertEqual(validate_policy(policy, ("repair.track",)), ())
        self.assertIn(
            "ASYNC_CAPABILITY_COVERAGE",
            validate_policy(policy, ("unavailable",)),
        )
        for field, value in (
            ("schema_version", "2"),
            ("event_types", []),
            ("human_confirmation", "yes"),
            ("timeout_behavior", "retry_create"),
            ("ticket_id", "runtime-ticket"),
        ):
            with self.subTest(field=field):
                invalid = dict(policy, **{field: value})
                with self.assertRaises(ValidationError):
                    validator.validate(invalid)
                self.assertTrue(validate_policy(invalid, ("repair.track",)))
