# -*- coding: utf-8 -*-
"""Check Builder handoff samples against Foundation's real schema export.

The canonical export validates DTO shape. It does not run Pydantic custom
validators, access control, protocol readiness or Lifecycle business rules.
"""

import copy
import json
from pathlib import Path
import unittest

from jsonschema import Draft202012Validator, FormatChecker


ROOT = Path(__file__).resolve().parents[4]
HANDOFF = ROOT / "docs/workforce/handoffs/bui-huu-nghia/phase_a"


class CanonicalBuilderHandoffTest(unittest.TestCase):
    """Use canonical schemas directly rather than copying their definitions."""

    @classmethod
    def setUpClass(cls):
        cls.bundle = json.loads(
            (ROOT / "docs/workforce/contracts/generated/workforce-v1.schema.json")
            .read_text(encoding="utf-8"),
        )
        cls.samples = json.loads(
            (HANDOFF / "canonical_samples.json").read_text(encoding="utf-8"),
        )

    def validator(self, model):
        models = self.bundle["models"]
        if model in models:
            schema = models[model]
        else:
            # Foundation exports these definitions through aggregate schemas.
            aggregate = {
                "ToolBinding": "AgentManifest",
                "BusinessProfile": "AgentManifest",
            }[model]
            definitions = models[aggregate]["$defs"]
            schema = {"$ref": f"#/$defs/{model}", "$defs": definitions}
        return Draft202012Validator(
            schema, format_checker=FormatChecker(),
        )

    def assert_invalid(self, model, data):
        self.assertTrue(list(self.validator(model).iter_errors(data)))

    def test_builder_samples_use_canonical_export(self):
        models = {
            "scope": "Scope", "tool_descriptor": "ToolDescriptor",
            "tool_binding": "ToolBinding", "business_profile": "BusinessProfile",
            "manifest": "AgentManifest",
            "create_decision": "ReuseDecision", "reuse_decision": "ReuseDecision",
            "revise_decision": "ReuseDecision",
        }
        for name, model in models.items():
            with self.subTest(sample=name, model=model):
                self.validator(model).validate(self.samples[name])

    def test_manifest_uses_spec_not_agent(self):
        manifest = copy.deepcopy(self.samples["manifest"])
        manifest["agent"] = manifest.pop("spec")
        self.assert_invalid("AgentManifest", manifest)

    def test_runtime_model_uses_model_config_ref(self):
        manifest = copy.deepcopy(self.samples["manifest"])
        spec = manifest["spec"]
        spec["model_config"] = spec.pop("model_config_ref")
        self.assert_invalid("AgentManifest", manifest)

    def test_generation_selection_is_not_manifest_data(self):
        manifest = copy.deepcopy(self.samples["manifest"])
        manifest["generation_model"] = {"model": "fixture-generation-model"}
        self.assert_invalid("AgentManifest", manifest)

    def test_domain_action_is_not_canonical_tool_effect(self):
        for action in ("booking", "cancel"):
            with self.subTest(action=action):
                descriptor = copy.deepcopy(self.samples["tool_descriptor"])
                descriptor["effect"] = action
                self.assert_invalid("ToolDescriptor", descriptor)

    def test_external_operation_effect_is_available(self):
        descriptor = copy.deepcopy(self.samples["tool_descriptor"])
        descriptor["effect"] = "external_operation"
        self.validator("ToolDescriptor").validate(descriptor)

    def test_revisions_are_integers(self):
        decision = copy.deepcopy(self.samples["reuse_decision"])
        decision["expected_catalog_revision"] = "3"
        self.assert_invalid("ReuseDecision", decision)

    def test_protocol_version_field_is_protocol_version(self):
        if "AsyncProtocolSnapshotRef" not in self.bundle["models"]:
            self.skipTest(
                "Foundation exports the Python DTO but not its JSON Schema yet; BHN-13.",
            )
        self.validator("AsyncProtocolSnapshotRef").validate(
            self.samples["async_protocol_ref"],
        )
        ref = copy.deepcopy(self.samples["async_protocol_ref"])
        ref["version"] = ref.pop("protocol_version")
        self.assert_invalid("AsyncProtocolSnapshotRef", ref)

    def test_review_policy_is_not_a_canonical_typed_policy(self):
        """Document the remaining gap instead of calling open JSON validated."""
        manifest = copy.deepcopy(self.samples["manifest"])
        manifest["spec"]["execution_policy"]["async_handling"] = {
            "tracking": "not-a-valid-mode", "workflow_id": "forbidden-in-policy",
        }
        # This passes because execution_policy is JsonObject in version 1.
        # BHN-12 requests typed validation before production integration.
        self.validator("AgentManifest").validate(manifest)

    def test_binding_and_profile_samples_are_consistent(self):
        manifest = self.samples["manifest"]
        self.assertEqual(manifest["business_profile"], self.samples["business_profile"])
        self.assertEqual(manifest["spec"]["tool_bindings"][0], self.samples["tool_binding"])
        descriptor = self.samples["tool_descriptor"]
        binding = self.samples["tool_binding"]
        for key in ("tool_id", "tool_version_id", "schema_hash"):
            self.assertEqual(binding[key], descriptor[key])
        self.assertIn(binding["required_capability"], descriptor["capabilities"])


if __name__ == "__main__":
    unittest.main()
