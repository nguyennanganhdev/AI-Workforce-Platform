"""Project Registry's public exact resolver into Builder readiness views."""

from collections.abc import Awaitable, Callable

from ...contracts import (
    AsyncProtocolSnapshotRef,
    Scope,
    ToolEffect,
    WorkforceContractError,
    WorkforceErrorCode,
)
from ...registry.event_protocols import AsyncToolProtocol
from ._models import ProtocolReadiness, Blocker
from ._selector import CapabilitySelector


class RegistryProtocolReadiness:
    def __init__(
        self,
        resolve_detail: Callable[
            [Scope, AsyncProtocolSnapshotRef], Awaitable[AsyncToolProtocol]
        ],
    ):
        self._resolve = resolve_detail

    async def read(self, scope: Scope, snapshot: AsyncProtocolSnapshotRef):
        protocol = await self._resolve(scope, snapshot)
        # Revalidate/copy mutable schema dictionaries before projecting evidence.
        protocol = AsyncToolProtocol.model_validate_json(protocol.model_dump_json())
        if protocol.snapshot_ref != snapshot:
            raise ValueError("Protocol detail does not match the exact snapshot")
        return ProtocolReadiness(
            snapshot=snapshot,
            correlation_supported=bool(
                protocol.client_reference_field or protocol.external_job_id_field
            ),
            event_types=tuple(protocol.event_mappings),
            fact_fields=tuple(
                sorted(
                    {
                        fact
                        for mapping in protocol.event_mappings.values()
                        for fact in mapping.fact_fields
                    }
                )
            ),
            event_fact_fields={
                name: mapping.fact_fields
                for name, mapping in protocol.event_mappings.items()
            },
            completion_policy=protocol.completion_policy,
            timeout_seconds=protocol.timeout_seconds,
            status_query_tool_version_id=protocol.status_query_tool_version_id,
        )


class RegistryCapabilitySelector(CapabilitySelector):
    """C3 also pins terminal external protocols for Lifecycle validation.

    Read-only tools still require no async metadata. A pending create-only
    request is blocked until Lifecycle's pending-policy semantics are agreed;
    it is never silently promoted to tracking or given a fabricated policy.
    """

    async def _check(self, scope, req, tool):
        checked = await super()._check(scope, req, tool)
        if (
            checked[0]
            or req.tracking_intent != "create_only"
            or tool.effect != ToolEffect.EXTERNAL_OPERATION
        ):
            return checked
        try:
            snapshot = await self.protocols.get_snapshot(scope, tool.tool_version_id)
            if snapshot.tool_version_id != tool.tool_version_id:
                raise LookupError("Protocol references another tool")
            if "terminal" not in snapshot.capabilities:
                return (
                    [
                        Blocker(
                            code="CREATE_ONLY_PENDING_POLICY_UNRESOLVED",
                            message="Pending create-only policy semantics need Lifecycle agreement",
                        )
                    ],
                    None,
                    None,
                    "none",
                )
            await self.protocols.validate_capability_coverage(snapshot, ("terminal",))
            if self.readiness is None:
                raise LookupError("Exact metadata reader is required")
            details = await self.readiness.read(scope, snapshot)
            if details.snapshot != snapshot:
                raise LookupError("Protocol detail pin differs")
            return [], snapshot, details, "none"
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
                        message="External draft requires an available exact terminal protocol",
                    )
                ],
                None,
                None,
                "none",
            )
