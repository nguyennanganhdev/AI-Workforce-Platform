"""Lifecycle validation against owner-provided immutable dependency payloads."""

import hashlib
import json
from typing import Any, Awaitable, Callable, Dict, Mapping, Optional, Sequence, Tuple

from jsonschema import Draft202012Validator, ValidationError

from ...builder.async_capabilities import HandlingPolicyProposal
from ...contracts import (
    AgentManifest,
    AsyncProtocolPort,
    AsyncProtocolSnapshotRef,
    RegistryPort,
    Scope,
    ToolDescriptor,
    ToolEffect,
)
from ...registry.event_protocols import AsyncToolProtocol
from .._models import ValidationReport
from ._schema import phase_a_schema_bundle


def canonical_hash(value: Any) -> str:
    """Hash JSON evidence, rejecting non-finite numbers and ambiguous encoding."""
    return hashlib.sha256(
        json.dumps(
            value,
            sort_keys=True,
            separators=(",", ":"),
            ensure_ascii=False,
            allow_nan=False,
        ).encode("utf-8")
    ).hexdigest()


def validate_async_draft(
    scope: Scope,
    manifest: AgentManifest,
    tools: Sequence[ToolDescriptor],
    protocols: Sequence[AsyncToolProtocol],
    policy: Optional[Mapping[str, Any]] = None,
    policy_scope: Optional[Scope] = None,
    policy_ref: Optional[str] = None,
    policy_schema: str = "pta-phase-a-1",
) -> Tuple[ValidationReport, Dict[str, Any]]:
    """Validate resolved inputs. Caller must obtain them through scoped ports.

    Full protocol payloads use Registry's public model. Policy proposals remain
    proposals; the explicit dialect avoids silently translating timeout semantics.
    Returned evidence is detached JSON, never a live pointer into provider state.
    """
    blockers = []
    tool_map = {tool.tool_version_id: tool for tool in tools}
    protocol_map = {item.tool_version_id: item for item in protocols}
    if len(tool_map) != len(tools) or len(protocol_map) != len(protocols):
        blockers.append("DUPLICATE_DEPENDENCY")
    bindings = manifest.spec.tool_bindings
    if set(tool_map) != {item.tool_version_id for item in bindings}:
        blockers.append("TOOL_SNAPSHOT_SET_MISMATCH")
    external_versions = set()
    for binding in bindings:
        tool = tool_map.get(binding.tool_version_id)
        if tool is None:
            blockers.append("MISSING_TOOL_SNAPSHOT")
            continue
        if not tool.available:
            blockers.append("TOOL_UNAVAILABLE")
        if (tool.tool_id, tool.schema_hash) != (binding.tool_id, binding.schema_hash):
            blockers.append("TOOL_SCHEMA_DRIFT")
        if binding.required_capability not in tool.capabilities:
            blockers.append("MISSING_REQUIRED_CAPABILITY")
        if tool.effect == ToolEffect.EXTERNAL_OPERATION:
            external_versions.add(tool.tool_version_id)
            if tool.tool_version_id not in protocol_map:
                blockers.append("MISSING_PROTOCOL")
    for version, protocol in protocol_map.items():
        tool = tool_map.get(version)
        if tool is None or tool.effect != protocol.effect:
            blockers.append("PROTOCOL_TOOL_MISMATCH")
    refs = [item.snapshot_ref.model_dump(mode="json") for item in protocols]
    hashes = [item["schema_hash"] for item in refs]
    if len(set(hashes)) != len(hashes) or sorted(hashes) != sorted(
        manifest.protocol_snapshot_hashes
    ):
        blockers.append("PROTOCOL_HASH_DRIFT")
    pending = [item for item in protocols if item.result_mode == "pending"]
    policy_data: Dict[str, Any] = {}
    if manifest.async_policy_ref is not None:
        if policy is None or policy_ref != manifest.async_policy_ref:
            blockers.append("POLICY_UNRESOLVED")
        elif policy_scope != scope:
            blockers.append("POLICY_SCOPE_MISMATCH")
        else:
            policy_data = json.loads(json.dumps(dict(policy), allow_nan=False))
            try:
                if policy_schema == "pta-phase-a-1":
                    Draft202012Validator(
                        phase_a_schema_bundle()["schemas"][
                            "AsyncHandlingPolicyProposal"
                        ]
                    ).validate(policy_data)
                elif policy_schema == "bhn-phase-a-1":
                    Draft202012Validator(
                        HandlingPolicyProposal.model_json_schema()
                    ).validate(policy_data)
                    HandlingPolicyProposal.model_validate(policy_data)
                else:
                    raise ValueError("unsupported policy dialect")
                names = policy_data["capabilities"]
                if any(not name.strip() for name in names) or len(set(names)) != len(
                    names
                ):
                    raise ValueError("blank or duplicate capability")
                external_capabilities = {
                    binding.required_capability
                    for binding in bindings
                    if binding.tool_version_id in external_versions
                }
                if not external_capabilities.issubset(names):
                    blockers.append("POLICY_BINDING_COVERAGE")
                if not set(names).issubset(manifest.business_profile.capabilities):
                    blockers.append("POLICY_BUSINESS_COVERAGE")
                if policy_data["timeout_behavior"] in ("status_query", "query_status"):
                    if not pending or any(
                        not p.status_query_tool_version_id for p in pending
                    ):
                        blockers.append("MISSING_STATUS_QUERY")
                for protocol in pending:
                    if not (
                        protocol.event_mappings or protocol.status_query_tool_version_id
                    ):
                        blockers.append("MISSING_TRACKING_CAPABILITY")
                    if not set(policy_data["event_types"]).issubset(
                        protocol.event_mappings
                    ):
                        blockers.append("POLICY_EVENT_COVERAGE")
                    for event_type in policy_data["event_types"]:
                        mapping = protocol.event_mappings.get(event_type)
                        if mapping and not set(policy_data["required_facts"]).issubset(
                            mapping.fact_fields
                        ):
                            blockers.append("POLICY_FACT_COVERAGE")
                    if (
                        protocol.requires_approval
                        and not policy_data["human_confirmation"]
                    ):
                        blockers.append("MISSING_HUMAN_CONFIRMATION")
            except (ValueError, KeyError, TypeError, ValidationError):
                blockers.append("INVALID_POLICY")
    elif policy is not None:
        blockers.append("UNREFERENCED_POLICY")
    if pending and not manifest.async_policy_ref:
        blockers.append("MISSING_ASYNC_POLICY")
    if manifest.async_policy_ref and not pending:
        blockers.append("UNUSED_ASYNC_POLICY")
    tool_data = [
        tool.model_dump(mode="json")
        for tool in sorted(tools, key=lambda item: item.tool_version_id)
    ]
    protocol_data = [
        item.model_dump(mode="json")
        for item in sorted(protocols, key=lambda item: item.tool_version_id)
    ]
    evidence = {
        "scope": scope.model_dump(mode="json"),
        "tools": tool_data,
        "protocols": protocol_data,
        "protocol_refs": sorted(refs, key=lambda item: item["tool_version_id"]),
        "policy": policy_data,
        "policy_ref": manifest.async_policy_ref,
        "policy_schema": policy_schema,
    }
    return (
        ValidationReport(
            valid=not blockers,
            blockers=tuple(sorted(set(blockers))),
            tool_snapshot_hash=canonical_hash(tool_data),
            protocol_hash=canonical_hash(protocol_data),
            dependency_hash=canonical_hash(evidence),
            tool_snapshots=tuple(tool_data),
        ),
        evidence,
    )


class AsyncDraftValidator:
    """Resolve dependencies through shared scoped ports before local validation.

    Detailed protocol and policy resolver callables are explicit integration
    proposals pending their owners' shared port promotion. They must read exact
    immutable references, never latest config. No fallback success is provided.
    """

    def __init__(
        self,
        registry: RegistryPort,
        protocol_port: AsyncProtocolPort,
        resolve_protocol: Callable[
            [Scope, AsyncProtocolSnapshotRef], Awaitable[AsyncToolProtocol]
        ],
        resolve_policy: Callable[
            [Scope, str], Awaitable[Tuple[Scope, str, str, Dict[str, Any]]]
        ],
    ) -> None:
        self.registry = registry
        self.protocol_port = protocol_port
        self.resolve_protocol = resolve_protocol
        self.resolve_policy = resolve_policy

    async def validate(
        self, scope: Scope, manifest: AgentManifest
    ) -> Tuple[ValidationReport, Dict[str, Any]]:
        tools = []
        protocols = []
        for binding in manifest.spec.tool_bindings:
            tool = await self.registry.get_tool_snapshot(scope, binding.tool_version_id)
            tools.append(tool)
            if tool.effect == ToolEffect.EXTERNAL_OPERATION:
                ref = await self.protocol_port.get_snapshot(
                    scope, binding.tool_version_id
                )
                protocol = await self.resolve_protocol(scope, ref)
                if protocol.snapshot_ref != ref:
                    raise ValueError("PROTOCOL_REFERENCE_DRIFT")
                protocols.append(protocol)
        policy = None
        policy_scope = None
        policy_ref = None
        dialect = "pta-phase-a-1"
        if manifest.async_policy_ref is not None:
            policy_scope, policy_ref, dialect, policy = await self.resolve_policy(
                scope, manifest.async_policy_ref
            )
        return validate_async_draft(
            scope,
            manifest,
            tools,
            protocols,
            policy,
            policy_scope,
            policy_ref,
            dialect,
        )
