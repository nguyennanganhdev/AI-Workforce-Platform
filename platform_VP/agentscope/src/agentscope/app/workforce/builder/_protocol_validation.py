"""C3 pre-write protocol validation; draft persistence stays with Lifecycle."""

from ..contracts import AgentManifest, Scope
from .async_capabilities._models import AgentProposal
from .async_capabilities._selector import CapabilitySelector


class ProtocolBuildValidator:
    """Validate server-held proposal pins before canonical DraftPort writes.

    Composition injects Lifecycle's existing AsyncDraftValidator.validate.
    This hook never generates manifests, stores policies, or writes drafts.
    Callers must check report.valid and must not trust proposal data from UI.
    """

    def __init__(self, selector: CapabilitySelector, validate_manifest):
        self.selector = selector
        self.validate_manifest = validate_manifest

    async def validate(
        self, scope: Scope, item: AgentProposal, manifest: AgentManifest
    ):
        item = item.model_copy(deep=True)
        manifest = AgentManifest.model_validate_json(manifest.model_dump_json())
        if (
            item.blockers
            or item.selection.blockers
            or item.requirement.clarification_questions
        ):
            raise ValueError("Resolve Builder blockers before protocol validation")
        if (
            manifest.spec.agent_key != item.requirement.agent_key
            or manifest.spec.capabilities != item.selection.covered
            or manifest.spec.tool_bindings != item.selection.bindings
            or sorted(manifest.protocol_snapshot_hashes)
            != sorted(pin.schema_hash for pin in item.selection.protocols)
        ):
            raise ValueError(
                "Manifest differs from Builder capability/binding/protocol pins"
            )
        await self.selector.recheck(scope, item.requirement, item.selection)
        report, evidence = await self.validate_manifest(scope, manifest)
        policy = item.requirement.policy_proposal
        if (
            report.valid
            and policy is not None
            and (
                evidence.get("policy") != policy.model_dump(mode="json")
                or evidence.get("policy_ref") != manifest.async_policy_ref
            )
        ):
            raise ValueError("Resolved policy differs from Builder proposal")
        return report, evidence
