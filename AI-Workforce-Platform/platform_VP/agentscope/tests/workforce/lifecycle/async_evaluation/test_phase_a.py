"""Structural acceptance tests for the Phase A handoff contract."""

from copy import deepcopy
import json
from pathlib import Path
import unittest

from jsonschema import Draft202012Validator, ValidationError

from agentscope.app.workforce.contracts import (
    AsyncProtocolSnapshotRef,
    EvaluationCaseResult,
    EvaluationReport,
    EvaluationSnapshot,
)
from agentscope.app.workforce.lifecycle import (
    EvaluationRecord,
    ValidationReport,
)
from agentscope.app.workforce.lifecycle.async_evaluation import (
    phase_a_schema_bundle,
)

HANDOFF = (
    Path(__file__).resolve().parents[4]
    / "docs/workforce/handoffs/pho-tien-anh/phase_a"
)


class PhaseAContractsTests(unittest.TestCase):
    def setUp(self) -> None:
        self.schemas = phase_a_schema_bundle()["schemas"]
        self.samples = json.loads((HANDOFF / "samples.json").read_text())

    def test_handoff_artifact_has_no_schema_drift(self) -> None:
        self.assertEqual(
            json.loads((HANDOFF / "schemas.json").read_text()),
            phase_a_schema_bundle(),
        )

    def test_export_uses_shared_dtos_and_proposed_aggregates(self) -> None:
        for model in (
            EvaluationSnapshot,
            EvaluationCaseResult,
            EvaluationReport,
            AsyncProtocolSnapshotRef,
            EvaluationRecord,
            ValidationReport,
        ):
            with self.subTest(model=model.__name__):
                self.assertEqual(
                    self.schemas[model.__name__], model.model_json_schema()
                )
                model.model_validate(self.samples[model.__name__])

    def test_each_schema_is_valid_and_accepts_its_sample(self) -> None:
        self.assertEqual(set(self.schemas), set(self.samples))
        for name, schema in self.schemas.items():
            with self.subTest(schema=name):
                Draft202012Validator.check_schema(schema)
                Draft202012Validator(schema).validate(self.samples[name])

    def test_snapshot_requires_complete_manager_scope(self) -> None:
        validator = Draft202012Validator(self.schemas["EvaluationSnapshot"])
        for field in (
            "tenant_id",
            "domain_id",
            "area_id",
            "manager_account_id",
        ):
            with self.subTest(field=field):
                sample = deepcopy(self.samples["EvaluationSnapshot"])
                del sample["scope"][field]
                with self.assertRaises(ValidationError):
                    validator.validate(sample)

    def test_evaluation_requires_frozen_context_and_validation(self) -> None:
        validator = Draft202012Validator(self.schemas["EvaluationRecord"])
        for field in (
            "snapshot",
            "report",
            "validation",
            "test_context",
            "runtime_profile",
            "suite_hash",
            "gate_config",
        ):
            with self.subTest(field=field):
                sample = deepcopy(self.samples["EvaluationRecord"])
                del sample[field]
                with self.assertRaises(ValidationError):
                    validator.validate(sample)

    def test_snapshot_rejects_invalid_revision_and_missing_hashes(
        self,
    ) -> None:
        validator = Draft202012Validator(self.schemas["EvaluationSnapshot"])
        for field, value in (
            ("draft_revision", 0),
            ("manifest_hash", ""),
            ("tool_snapshot_hash", ""),
            ("test_context_hash", ""),
        ):
            with self.subTest(field=field):
                sample = dict(self.samples["EvaluationSnapshot"])
                sample[field] = value
                with self.assertRaises(ValidationError):
                    validator.validate(sample)

    def test_policy_proposal_rejects_invalid_structure(self) -> None:
        validator = Draft202012Validator(
            self.schemas["AsyncHandlingPolicyProposal"]
        )
        for field, value in (
            ("schema_version", "2"),
            ("capabilities", []),
            ("event_types", []),
            ("required_facts", [""]),
            ("completion_condition", ""),
            ("human_confirmation", "yes"),
            ("timeout_behavior", "retry_create"),
            ("ticket_id", "ticket-1"),
            ("job_id", "job-1"),
            ("workflow_id", "workflow-1"),
            ("group_id", "group-1"),
            ("endpoint", "provider-endpoint"),
            ("roster", ["agent-1"]),
        ):
            with self.subTest(field=field):
                sample = dict(self.samples["AsyncHandlingPolicyProposal"])
                sample[field] = value
                with self.assertRaises(ValidationError):
                    validator.validate(sample)

    def test_policy_proposal_requires_all_declared_fields(self) -> None:
        validator = Draft202012Validator(
            self.schemas["AsyncHandlingPolicyProposal"]
        )
        for field in self.schemas["AsyncHandlingPolicyProposal"]["required"]:
            with self.subTest(field=field):
                sample = dict(self.samples["AsyncHandlingPolicyProposal"])
                del sample[field]
                with self.assertRaises(ValidationError):
                    validator.validate(sample)
