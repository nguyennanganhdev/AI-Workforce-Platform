"""Business validation through scoped Registry and resource ports."""

from typing import Any, Dict, Protocol, Tuple
from jsonschema import Draft202012Validator, SchemaError

from ..contracts import (
    AgentManifest,
    AsyncProtocolPort,
    RegistryPort,
    Scope,
    SideEffectPolicy,
    ToolEffect,
)
from ._models import ValidationReport, canonical_hash, has_external_schema_ref


class ResourceValidationPort(Protocol):
    """Foundation adapter checks credential/KB/skill scope and
    compatibility."""

    async def validate_resources(
        self, scope: Scope, manifest: AgentManifest
    ) -> Dict[str, Any]: ...


class AsyncPolicyPort(Protocol):
    """Additive port request; policy remains owned by Builder/contracts."""

    async def get_policy(
        self, scope: Scope, policy_ref: str
    ) -> Dict[str, Any]: ...


class ManifestValidator:
    def __init__(
        self,
        registry: RegistryPort,
        resources: ResourceValidationPort,
        protocols: AsyncProtocolPort,
        policies: AsyncPolicyPort,
    ) -> None:
        self.registry = registry
        self.resources = resources
        self.protocols = protocols
        self.policies = policies

    async def freeze(
        self, scope: Scope, manifest: AgentManifest
    ) -> Tuple[ValidationReport, Tuple[Dict[str, Any], ...], Dict[str, Any]]:
        blockers = []
        spec = manifest.spec
        declared = set(spec.capabilities)
        if not set(manifest.business_profile.capabilities).issubset(declared):
            blockers.append("CAPABILITY_COVERAGE")
        model = spec.model_config_ref
        if not isinstance(model.get("model_id"), str) or not isinstance(
            model.get("credential_ref"),
            str,
        ):
            blockers.append("MODEL_REFERENCE_REQUIRED")
        forbidden = {"api_key", "password", "secret", "access_token", "token"}

        def inspect(value: Any) -> None:
            if isinstance(value, dict):
                if forbidden.intersection(key.casefold() for key in value):
                    blockers.append("INLINE_SECRET_FORBIDDEN")
                for item in value.values():
                    inspect(item)
            elif isinstance(value, (list, tuple)):
                for item in value:
                    inspect(item)

        inspect(manifest.model_dump(mode="json"))
        if set(spec.collaboration_policy).intersection(
            {"roster", "members", "team_id", "group_id", "workflow_id"},
        ):
            blockers.append("FIXED_RUNTIME_ROSTER_FORBIDDEN")
        allowed = spec.collaboration_policy.get("allowed_capabilities", [])
        if not isinstance(allowed, list) or any(
            not isinstance(x, str) for x in allowed
        ):
            blockers.append("COLLABORATION_POLICY_INVALID")
        await self.registry.check_bindings(scope, spec.tool_bindings)
        tools = []
        protocol_refs = []
        external = []
        seen = set()
        for binding in spec.tool_bindings:
            if binding.tool_version_id in seen:
                blockers.append("DUPLICATE_TOOL_BINDING")
            seen.add(binding.tool_version_id)
            tool = await self.registry.get_tool_snapshot(
                scope, binding.tool_version_id
            )
            if (
                not tool.available
                or tool.tool_id != binding.tool_id
                or tool.schema_hash != binding.schema_hash
            ):
                blockers.append("TOOL_SNAPSHOT_UNAVAILABLE")
            if (
                binding.required_capability not in tool.capabilities
                or binding.required_capability not in declared
            ):
                blockers.append("TOOL_CAPABILITY_MISMATCH")
            tools.append(tool.model_dump(mode="json"))
            if has_external_schema_ref(
                tool.input_schema
            ) or has_external_schema_ref(tool.output_schema):
                blockers.append("EXTERNAL_SCHEMA_REFERENCE_FORBIDDEN")
            try:
                Draft202012Validator.check_schema(tool.input_schema)
                if tool.output_schema is not None:
                    Draft202012Validator.check_schema(tool.output_schema)
            except SchemaError:
                blockers.append("TOOL_SCHEMA_INVALID")
            if tool.effect != ToolEffect.READ:
                if (
                    manifest.business_profile.execution_policy
                    == SideEffectPolicy.READ_ONLY
                ):
                    blockers.append("READ_ONLY_SIDE_EFFECT")
                if spec.execution_policy.get("require_approval") is not True:
                    blockers.append("SIDE_EFFECT_APPROVAL_REQUIRED")
            if tool.effect == ToolEffect.EXTERNAL_OPERATION:
                protocol = await self.protocols.get_snapshot(
                    scope, tool.tool_version_id
                )
                if protocol.tool_version_id != tool.tool_version_id:
                    blockers.append("PROTOCOL_TOOL_MISMATCH")
                await self.protocols.validate_capability_coverage(
                    protocol,
                    (binding.required_capability,),
                )
                external.append(binding.required_capability)
                protocol_refs.append(protocol.model_dump(mode="json"))
        dependencies = await self.resources.validate_resources(scope, manifest)
        if dependencies.get("valid") is not True:
            blockers.append("RESOURCE_UNAVAILABLE")
        policy: Dict[str, Any] = {}
        if manifest.async_policy_ref:
            policy = await self.policies.get_policy(
                scope, manifest.async_policy_ref
            )
            from .async_evaluation._validation import validate_policy

            blockers.extend(validate_policy(policy, tuple(external)))
        elif external:
            blockers.append("ASYNC_POLICY_REQUIRED")
        actual_hashes = tuple(
            sorted(ref["schema_hash"] for ref in protocol_refs)
        )
        if tuple(sorted(manifest.protocol_snapshot_hashes)) != actual_hashes:
            blockers.append("PROTOCOL_SNAPSHOT_DRIFT")
        return (
            ValidationReport(
                valid=not blockers,
                blockers=tuple(sorted(set(blockers))),
                tool_snapshot_hash=canonical_hash(
                    sorted(tools, key=lambda x: x["tool_version_id"])
                ),
                protocol_hash=canonical_hash(
                    {"refs": protocol_refs, "policy": policy}
                ),
                dependency_hash=canonical_hash(dependencies),
                tool_snapshots=tuple(
                    sorted(tools, key=lambda x: x["tool_version_id"])
                ),
            ),
            tuple(protocol_refs),
            policy,
        )

    async def validate(
        self, scope: Scope, manifest: AgentManifest
    ) -> ValidationReport:
        return (await self.freeze(scope, manifest))[0]
