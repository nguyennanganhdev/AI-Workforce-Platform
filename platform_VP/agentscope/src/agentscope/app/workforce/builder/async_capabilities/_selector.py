"""Scoped, bounded capability selection and pinned async readiness checks."""

from jsonschema import Draft202012Validator, SchemaError

from ...contracts import (
    AsyncProtocolPort,
    RegistryPort,
    Scope,
    ToolBinding,
    ToolDescriptor,
    ToolEffect,
    WorkforceContractError,
    WorkforceErrorCode,
)
from ._models import Blocker, CapabilitySelection, ProtocolReadinessReader
from ._requirements import AgentRequirement


class CapabilitySelector:
    def __init__(
        self,
        registry: RegistryPort,
        protocols: AsyncProtocolPort,
        readiness: ProtocolReadinessReader | None = None,
        *,
        max_pages: int = 10,
    ):
        if not 1 <= max_pages <= 100:
            raise ValueError("invalid catalog page budget")
        self.registry, self.protocols, self.readiness = registry, protocols, readiness
        self.max_pages = max_pages

    async def _catalog(self, scope: Scope, capability: str):
        cursor = None
        seen = set()
        tools = {}
        for _ in range(self.max_pages):
            page, next_cursor = await self.registry.list_available_tools(
                scope,
                capabilities=(capability,),
                cursor=cursor,
            )
            for tool in page:
                if tool.available and capability in tool.capabilities:
                    tools[tool.tool_version_id] = tool
            if next_cursor is None:
                return tuple(sorted(tools.values(), key=lambda t: t.tool_version_id))
            if next_cursor in seen:
                break
            seen.add(next_cursor)
            cursor = next_cursor
        raise WorkforceContractError(
            WorkforceErrorCode.MISSING_REQUIRED_CAPABILITY,
            "Catalog pagination exceeded budget or repeated cursor",
        )

    async def _check(self, scope: Scope, req: AgentRequirement, tool: ToolDescriptor):
        blockers = []
        tracking = req.tracking_intent == "track_to_completion"
        if tool.effect != req.effect and tool.effect != ToolEffect.READ:
            return (
                [
                    Blocker(
                        code="TOOL_EFFECT_MISMATCH",
                        message="Tool effect differs from requested effect",
                    )
                ],
                None,
                None,
                "none",
            )
        try:
            Draft202012Validator.check_schema(tool.input_schema)
            if tool.output_schema is not None:
                Draft202012Validator.check_schema(tool.output_schema)
        except SchemaError:
            return (
                [Blocker(code="INVALID_TOOL_SCHEMA", message="Tool schema is invalid")],
                None,
                None,
                "none",
            )
        if not tracking or tool.effect == ToolEffect.READ:
            return [], None, None, "none"
        try:
            snapshot = await self.protocols.get_snapshot(scope, tool.tool_version_id)
            if snapshot.tool_version_id != tool.tool_version_id:
                return (
                    [
                        Blocker(
                            code="PROTOCOL_SNAPSHOT_MISMATCH",
                            message="Protocol references another tool version",
                        )
                    ],
                    None,
                    None,
                    "none",
                )
            await self.protocols.validate_capability_coverage(snapshot, ("create",))
            channel = (
                "status_query"
                if req.policy_proposal
                and req.policy_proposal.timeout_behavior == "status_query"
                else (
                    "provider_events"
                    if "receive_status" in snapshot.capabilities
                    else "status_query"
                )
            )
            needed = (
                "receive_status" if channel == "provider_events" else "status_query"
            )
            await self.protocols.validate_capability_coverage(snapshot, (needed,))
        except (LookupError, WorkforceContractError) as exc:
            if (
                isinstance(exc, WorkforceContractError)
                and exc.code != WorkforceErrorCode.MISSING_REQUIRED_CAPABILITY
            ):
                raise
            return (
                [
                    Blocker(
                        code="MISSING_REQUIRED_CAPABILITY",
                        message="Tracking requires create and an available event/status-query path",
                    )
                ],
                None,
                None,
                "none",
            )
        if self.readiness is None:
            return (
                [
                    Blocker(
                        code="PROTOCOL_DETAILS_REQUIRED",
                        message="Pinned correlation/completion metadata is required",
                    )
                ],
                snapshot,
                None,
                channel,
            )
        try:
            details = await self.readiness.read(scope, snapshot)
        except LookupError:
            return (
                [
                    Blocker(
                        code="PROTOCOL_DETAILS_REQUIRED",
                        message="Exact pinned protocol metadata is unavailable",
                    )
                ],
                snapshot,
                None,
                channel,
            )
        if details.snapshot != snapshot:
            return (
                [
                    Blocker(
                        code="PROTOCOL_SNAPSHOT_MISMATCH",
                        message="Detailed protocol is not the exact pinned snapshot",
                    )
                ],
                snapshot,
                details,
                channel,
            )
        if not details.correlation_supported or details.timeout_seconds is None:
            blockers.append(
                Blocker(
                    code="MISSING_REQUIRED_CAPABILITY",
                    message="Tracking correlation or operation timeout is missing",
                )
            )
        if channel == "status_query":
            if not details.status_query_tool_version_id:
                blockers.append(
                    Blocker(
                        code="MISSING_REQUIRED_CAPABILITY",
                        message="Status-query tool version is missing",
                    )
                )
            else:
                try:
                    query = await self.registry.get_tool_snapshot(
                        scope, details.status_query_tool_version_id
                    )
                except LookupError:
                    query = None
                if (
                    query is None
                    or not query.available
                    or query.effect != ToolEffect.READ
                    or query.tool_version_id != details.status_query_tool_version_id
                    or "status_query" not in query.capabilities
                ):
                    blockers.append(
                        Blocker(
                            code="MISSING_REQUIRED_CAPABILITY",
                            message="Status-query tool is unavailable, not read-only, or lacks status_query capability",
                        )
                    )
                elif query is not None:
                    query_errors, _, _, _ = await self._check(scope, req, query)
                    blockers.extend(query_errors)
        policy = req.policy_proposal
        if policy is not None:
            if not set(policy.event_types) <= set(details.event_types):
                blockers.append(
                    Blocker(
                        code="POLICY_EVENT_SEMANTICS_UNRESOLVED",
                        message="Policy event types are not supported by pinned metadata; query-only semantics need agreement",
                    )
                )
            if not set(policy.required_facts) <= set(details.fact_fields):
                blockers.append(
                    Blocker(
                        code="MISSING_REQUIRED_CAPABILITY",
                        message="Protocol does not provide required policy facts",
                    )
                )
            if channel == "provider_events" and any(
                not set(policy.required_facts)
                <= set(details.event_fact_fields.get(event_type, ()))
                for event_type in policy.event_types
            ):
                blockers.append(
                    Blocker(
                        code="MISSING_REQUIRED_CAPABILITY",
                        message="Each policy event must supply its required facts",
                    )
                )
        return blockers, snapshot, details, channel

    async def select(self, scope: Scope, req: AgentRequirement) -> CapabilitySelection:
        bindings, refs, covered, optional, blockers = [], {}, [], [], []
        channel, completion = "none", None
        effect_covered = req.effect == ToolEffect.READ
        if req.clarification_questions or req.tracking_intent == "unspecified":
            blockers.append(
                Blocker(
                    code="CLARIFICATION_REQUIRED",
                    message="Resolve requirement questions before confirming",
                )
            )
        for capability in req.capabilities:
            try:
                candidates = await self._catalog(scope, capability.capability)
            except WorkforceContractError as exc:
                if exc.code != WorkforceErrorCode.MISSING_REQUIRED_CAPABILITY:
                    raise
                candidates = ()
            rejected = []
            chosen = None
            for tool in sorted(
                candidates, key=lambda t: (t.effect != req.effect, t.tool_version_id)
            ):
                errors, snapshot, details, candidate_channel = await self._check(
                    scope, req, tool
                )
                if errors:
                    rejected.extend(errors)
                    continue
                chosen = tool
                if snapshot is not None:
                    refs[snapshot.schema_hash] = snapshot
                if details is not None:
                    completion = details.completion_policy
                if candidate_channel != "none":
                    channel = candidate_channel
                break
            if chosen is None:
                if capability.required:
                    blockers.extend(
                        rejected
                        or [
                            Blocker(
                                code="MISSING_REQUIRED_CAPABILITY",
                                capability=capability.capability,
                                message="Enable a compatible MCP/tool for this required capability",
                            )
                        ]
                    )
                else:
                    optional.append(capability.capability)
                continue
            covered.append(capability.capability)
            effect_covered = effect_covered or chosen.effect == req.effect
            bindings.append(
                ToolBinding(
                    tool_id=chosen.tool_id,
                    tool_version_id=chosen.tool_version_id,
                    schema_hash=chosen.schema_hash,
                    required_capability=capability.capability,
                    selection_reason=f"Available {chosen.effect.value} tool covers {capability.capability}; compatible schema and required tracking checks passed",
                )
            )
            if (
                details is not None
                and candidate_channel == "status_query"
                and details.status_query_tool_version_id
            ):
                query = await self.registry.get_tool_snapshot(
                    scope, details.status_query_tool_version_id
                )
                if not any(
                    b.tool_version_id == query.tool_version_id for b in bindings
                ):
                    bindings.append(
                        ToolBinding(
                            tool_id=query.tool_id,
                            tool_version_id=query.tool_version_id,
                            schema_hash=query.schema_hash,
                            required_capability="status_query",
                            selection_reason="Pinned read-only status-query binding for verified tracking",
                        )
                    )
        if req.policy_proposal is not None and not set(
            req.policy_proposal.capabilities
        ) <= set(covered):
            blockers.append(
                Blocker(
                    code="MISSING_REQUIRED_CAPABILITY",
                    message="Policy capabilities are not all covered by selected bindings",
                )
            )
        if not effect_covered:
            blockers.append(
                Blocker(
                    code="MISSING_REQUIRED_CAPABILITY",
                    message="No selected tool covers the requested side effect",
                )
            )
        if req.tracking_intent == "track_to_completion" and not refs:
            blockers.append(
                Blocker(
                    code="MISSING_REQUIRED_CAPABILITY",
                    message="No selected operation supports verified tracking",
                )
            )
        support = (
            ("external_tracking",)
            if channel != "none"
            else (
                ("response_only",)
                if req.effect == ToolEffect.READ
                else ("interactive",)
            )
        )
        return CapabilitySelection(
            bindings=tuple(bindings),
            protocols=tuple(refs.values()),
            covered=tuple(covered),
            missing_optional=tuple(optional),
            blockers=tuple(blockers),
            support=support,
            tracking_channel=channel,
            completion_policy=completion,
        )

    async def recheck(
        self, scope: Scope, req: AgentRequirement, selection: CapabilitySelection
    ):
        try:
            await self._recheck_bindings(scope, req, selection)
        except LookupError as exc:
            raise WorkforceContractError(
                WorkforceErrorCode.REUSE_DECISION_STALE,
                "Pinned tool or protocol is unavailable; refresh proposal",
            ) from exc

    async def _recheck_bindings(
        self, scope: Scope, req: AgentRequirement, selection: CapabilitySelection
    ):
        await self.registry.check_bindings(scope, selection.bindings)
        effect_covered = req.effect == ToolEffect.READ
        for binding in selection.bindings:
            current = await self.registry.get_tool_snapshot(
                scope, binding.tool_version_id
            )
            if (
                not current.available
                or current.schema_hash != binding.schema_hash
                or current.tool_id != binding.tool_id
                or current.tool_version_id != binding.tool_version_id
                or binding.required_capability not in current.capabilities
            ):
                raise WorkforceContractError(
                    WorkforceErrorCode.REUSE_DECISION_STALE,
                    "Tool binding changed; refresh proposal",
                )
            errors, snapshot, _, _ = await self._check(scope, req, current)
            effect_covered = effect_covered or current.effect == req.effect
            if errors or (snapshot is not None and snapshot not in selection.protocols):
                raise WorkforceContractError(
                    WorkforceErrorCode.REUSE_DECISION_STALE,
                    "Tracking readiness changed; refresh proposal",
                )
        if not effect_covered:
            raise WorkforceContractError(
                WorkforceErrorCode.REUSE_DECISION_STALE,
                "Selected tools no longer cover the requested side effect",
            )
