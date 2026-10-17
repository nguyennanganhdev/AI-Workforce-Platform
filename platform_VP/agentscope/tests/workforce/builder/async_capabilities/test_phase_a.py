"""Schema and consumer-boundary tests; all providers are test-only."""

from datetime import UTC, datetime
import json
from pathlib import Path
import unittest

import jsonschema
from pydantic import ValidationError

from agentscope.app.workforce.builder.async_capabilities import BuildRequirements
from agentscope.app.workforce.contracts import (
    AgentManifest, AgentReusePort, AgentSpec, AsyncProtocolPort,
    AsyncProtocolSnapshotRef, DraftPort,
    MatchType, RegistryPort, ReuseAction, ReuseCandidate, ReuseCheck,
    ReuseDecision, ReuseStatus, Scope, ToolDescriptor,
    WorkforceContractError, WorkforceErrorCode,
)


class FakeDrafts:
    """Record canonical handoff arguments without pretending to persist."""

    def __init__(self):
        self.calls = []

    async def create_draft(self, scope, manifest, reuse_decision, batch_id=None):
        self.calls.append((scope, manifest, reuse_decision, batch_id))
        return {"fixture": True, "draft_id": "test-draft"}

    async def get_draft(self, scope, draft_id):
        raise NotImplementedError("No persistence in Phase A")

    async def update_draft(self, scope, draft_id, expected_revision, manifest, reuse_decision):
        raise NotImplementedError("No persistence in Phase A")

    async def validate_draft(self, scope, draft_id):
        raise NotImplementedError("Lifecycle owns validation")


class FakeRegistry:
    def __init__(self, scope, tools):
        self.scope, self.tools = scope, tools

    async def list_available_tools(self, scope, query=None, capabilities=(), cursor=None):
        if scope != self.scope:
            return (), None
        return tuple(t for t in self.tools if t.available and set(capabilities) <= set(t.capabilities)), None

    async def get_tool_snapshot(self, scope, tool_version_id):
        if scope != self.scope:
            raise PermissionError("outside owner scope")
        return next(t for t in self.tools if t.tool_version_id == tool_version_id)

    async def check_bindings(self, scope, bindings):
        for binding in bindings:
            await self.get_tool_snapshot(scope, binding.tool_version_id)

    async def resolve_connection(self, scope, connection_id):
        raise NotImplementedError("Phase A does not resolve credentials")


class FakeProtocols:
    def __init__(self, scope, snapshot):
        self.scope, self.snapshot = scope, snapshot

    async def get_snapshot(self, scope, tool_version_id):
        if scope != self.scope:
            raise PermissionError("outside owner scope")
        if tool_version_id != self.snapshot.tool_version_id:
            raise LookupError(tool_version_id)
        return self.snapshot

    async def validate_capability_coverage(self, protocol_snapshot, required_capabilities):
        if not set(required_capabilities) <= set(protocol_snapshot.capabilities):
            raise WorkforceContractError(WorkforceErrorCode.MISSING_REQUIRED_CAPABILITY, "missing tracking capability")

    async def normalize_verified_event(self, provider_context, protocol_snapshot, envelope):
        raise NotImplementedError("Registry owns event normalization")


class FakeReuse:
    def __init__(self, scope, action):
        self.scope, self.action = scope, action

    async def find_candidates(self, scope, business_profile, include_drafts=True):
        if scope != self.scope:
            raise PermissionError("outside owner scope")
        return ReuseCheck(
            reuse_check_id="check-1", requirement_hash="sample-hash",
            agent_catalog_revision=2, recommended_action=self.action,
            created_at=datetime.now(UTC), candidates=(ReuseCandidate(
                agent_id="existing-agent", version_id="version-1",
                match_type=MatchType.SAME_BUSINESS, reuse_status=ReuseStatus.READY,
                reason="same business", missing_requirements=("receive_status",) if self.action == ReuseAction.REVISE else (),
            ),),
        )

    async def get_candidate(self, scope, agent_id, version_id=None):
        return (await self.find_candidates(scope, None)).candidates[0]

    async def validate_decisions(self, scope, requirements, reuse_decisions, expected_catalog_revision):
        if scope != self.scope:
            raise PermissionError("outside owner scope")
        if expected_catalog_revision != 2:
            raise WorkforceContractError(WorkforceErrorCode.REUSE_DECISION_STALE, "catalog changed")


class PhaseATests(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        self.samples = json.loads(Path(__file__).with_name("samples.json").read_text(encoding="utf-8"))
        self.scope = Scope(tenant_id="t", domain_id="d", area_id="a", manager_account_id="manager-a")

    def test_valid_samples_and_roundtrip(self):
        for sample in self.samples["valid"]:
            with self.subTest(name=sample["name"]):
                value = BuildRequirements.model_validate(sample["payload"])
                self.assertEqual(value, BuildRequirements.model_validate_json(value.model_dump_json()))
                jsonschema.validate(value.model_dump(mode="json"), BuildRequirements.model_json_schema())

    def test_invalid_samples(self):
        for sample in self.samples["invalid"]:
            with self.subTest(name=sample["name"]), self.assertRaises(ValidationError):
                BuildRequirements.model_validate(sample["payload"])

    def test_schema_has_no_runtime_or_scope_fields(self):
        schema = BuildRequirements.model_json_schema()
        for definition in schema["$defs"].values():
            self.assertTrue(definition.get("additionalProperties") is False or "properties" not in definition)
        properties = schema["$defs"]["HandlingPolicyProposal"]["properties"]
        self.assertFalse(set(properties) & {"scope", "workflow_id", "job_id", "endpoint", "roster", "credential"})

    async def test_registry_query_uses_existing_requirement_capabilities(self):
        req = BuildRequirements.model_validate(self.samples["valid"][0]["payload"]).agents[0]
        tool = ToolDescriptor(tool_id="tool", tool_version_id="v1", source_kind="builtin", provider_tool_name="lookup", llm_alias="lookup", input_schema={}, schema_hash="hash", capabilities=("lookup",), effect="read", available=True)
        registry = FakeRegistry(self.scope, (tool,))
        self.assertIsInstance(registry, RegistryPort)
        tools, cursor = await registry.list_available_tools(self.scope, capabilities=[c.capability for c in req.capabilities if c.required])
        self.assertEqual(tools, (tool,))
        other = self.scope.model_copy(update={"manager_account_id": "manager-b"})
        self.assertEqual(await registry.list_available_tools(other), ((), None))

    async def test_create_only_does_not_require_status_channel(self):
        protocol = AsyncProtocolSnapshotRef(protocol_id="p", protocol_version="1", schema_hash="hash", tool_version_id="v1", capabilities=("create",))
        fake = FakeProtocols(self.scope, protocol)
        self.assertIsInstance(fake, AsyncProtocolPort)
        await fake.validate_capability_coverage(protocol, ("create",))
        with self.assertRaises(WorkforceContractError) as raised:
            await fake.validate_capability_coverage(protocol, ("create", "receive_status"))
        self.assertEqual(raised.exception.code, WorkforceErrorCode.MISSING_REQUIRED_CAPABILITY)
        fallback = protocol.model_copy(update={"capabilities": ("create", "status_query")})
        await fake.validate_capability_coverage(fallback, ("create", "status_query"))

    async def test_reuse_revise_preserves_identity_and_revision(self):
        profile = BuildRequirements.model_validate(self.samples["valid"][0]["payload"]).agents[0].business_profile
        for action in (ReuseAction.REUSE, ReuseAction.REVISE):
            fake = FakeReuse(self.scope, action)
            self.assertIsInstance(fake, AgentReusePort)
            check = await fake.find_candidates(self.scope, profile)
            decision = ReuseDecision(agent_key="agent", action=action, reuse_check_id=check.reuse_check_id, agent_id=check.candidates[0].agent_id, version_id="version-1", reason="same identity", expected_catalog_revision=2)
            self.assertEqual(decision.agent_id, "existing-agent")
            await fake.validate_decisions(self.scope, (profile,), (decision,), 2)
            with self.assertRaises(WorkforceContractError):
                await fake.validate_decisions(self.scope, (profile,), (decision,), 1)

    async def test_protocol_and_reuse_reject_other_manager_same_area(self):
        other = self.scope.model_copy(update={"manager_account_id": "manager-b"})
        protocol = AsyncProtocolSnapshotRef(protocol_id="p", protocol_version="1", schema_hash="hash", tool_version_id="v1")
        with self.assertRaises(PermissionError):
            await FakeProtocols(self.scope, protocol).get_snapshot(other, "v1")
        profile = BuildRequirements.model_validate(self.samples["valid"][0]["payload"]).agents[0].business_profile
        with self.assertRaises(PermissionError):
            await FakeReuse(self.scope, ReuseAction.REUSE).find_candidates(other, profile)

    async def test_manifest_and_revise_handoff_use_canonical_draft_port(self):
        requirement = BuildRequirements.model_validate(self.samples["valid"][0]["payload"]).agents[0]
        manifest = AgentManifest(
            schema_version="1", business_profile=requirement.business_profile,
            spec=AgentSpec(agent_key=requirement.agent_key, name="Lookup",
                           capabilities=("lookup",), system_prompt="Look up information.",
                           model_config_ref={"fixture": True}),
        )
        decision = ReuseDecision(agent_key=requirement.agent_key, action="revise",
                                 reuse_check_id="check-1", agent_id="existing-agent",
                                 version_id="version-1", reason="add capability",
                                 expected_catalog_revision=2)
        drafts = FakeDrafts()
        self.assertIsInstance(drafts, DraftPort)
        await drafts.create_draft(self.scope, manifest, decision, "test-batch")
        self.assertEqual(drafts.calls[0][2].agent_id, "existing-agent")
        self.assertIsNone(manifest.async_policy_ref)
        self.assertNotIn("group_id", manifest.model_dump())


if __name__ == "__main__":
    unittest.main()
