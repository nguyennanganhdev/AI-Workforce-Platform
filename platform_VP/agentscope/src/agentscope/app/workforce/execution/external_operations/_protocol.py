# -*- coding: utf-8 -*-
"""Adapt Registry's public configuration and shared port to Execution."""

from typing import Any

from ...contracts import (
    ActorContext,
    AsyncProtocolSnapshotRef,
    NormalizedJobEvent,
    ProviderEventEnvelope,
    Scope,
)
from .._utils import ExecutionError, digest, freeze, instant, value


def protocol_config(protocol: Any) -> Any:
    """Revalidate immutable content; never resolve the latest configuration."""
    from ...registry.event_protocols import AsyncToolProtocol

    try:
        config = AsyncToolProtocol.model_validate(protocol["configuration"])
        ref = AsyncProtocolSnapshotRef.model_validate(protocol["snapshot_ref"])
        if config.snapshot_ref != ref:
            raise ValueError
        return config
    except (KeyError, ValueError, TypeError):
        raise ExecutionError("ASYNC_PROTOCOL_PIN_MISMATCH", 403) from None


def protocol_hash(protocol: Any) -> str:
    """Preserve old record hashes while pinning new Registry content hashes."""
    if "snapshot_ref" in protocol:
        return protocol_config(protocol).snapshot_ref.schema_hash
    return digest(protocol)


class ExecutionProtocolAdapter:
    """No Registry storage or auth: callers inject authorized resolvers.

    detail_resolver(scope, ref) returns the exact public AsyncToolProtocol.
    event_port_factory(context), when supplied, binds persisted inbox identity
    to an AsyncProtocolPort without changing shared signatures. It must be
    request-local, never a mutation of a shared normalizer's context.
    """

    def __init__(
        self,
        protocol_port: Any,
        detail_resolver: Any,
        event_port_factory: Any = None,
    ) -> None:
        self.port = protocol_port
        self.resolve_detail = detail_resolver
        self.event_port_factory = event_port_factory

    async def get_snapshot(self, scope: Any, tool_version_id: str) -> Any:
        scope = Scope.model_validate(scope)
        ref = AsyncProtocolSnapshotRef.model_validate(
            await self.port.get_snapshot(scope, tool_version_id)
        )
        if ref.tool_version_id != tool_version_id:
            raise ExecutionError("ASYNC_PROTOCOL_PIN_MISMATCH", 403)
        return await self.resolve_snapshot(scope, ref)

    async def resolve_snapshot(self, scope: Any, ref: Any) -> Any:
        """Resolve an exact old or current pin through an authorized port."""
        scope = Scope.model_validate(scope)
        ref = AsyncProtocolSnapshotRef.model_validate(ref)
        config = await self.resolve_detail(scope, ref)
        protocol = {
            "snapshot_ref": value(ref),
            "configuration": value(config),
        }
        config = protocol_config(protocol)
        if config.result_mode != "pending":
            raise ExecutionError("TRACKING_PROTOCOL_REQUIRED", 422)
        await self.port.validate_capability_coverage(ref, ("create",))
        fields = {}
        if config.client_reference_field:
            fields["client_reference"] = config.client_reference_field
        return {
            **protocol,
            "scope": value(scope),
            "provider_integration_id": config.provider_integration_id,
            "capability": "external_tracking",
            "provider_events": bool(config.event_mappings),
            "status_query": bool(config.status_query_tool_version_id),
            "order_mode": config.event_mode
            if config.ordering == "provider_version"
            else "transition",
            "create_fields": fields,
        }

    async def validate_envelope(self, principal: Any, envelope: Any) -> None:
        """Only structural validation before operation/pinned policy lookup."""
        from ..provider_events._ingress import canonical_envelope

        canonical_envelope(envelope)
        if (
            principal.get("purpose") != "provider_events"
            or not principal.get("tenant_id")
            or not principal.get("provider_integration_id")
        ):
            raise ExecutionError("PROVIDER_AUTH_REQUIRED", 403)

    async def normalize_verified_event(
        self,
        principal: Any,
        protocol: Any,
        envelope: Any,
        *,
        inbox_event_id: str,
        received_at: str,
    ) -> Any:
        from jsonschema import ValidationError as SchemaError

        config = protocol_config(protocol)
        ref = config.snapshot_ref
        try:
            actor = ActorContext.model_validate(principal["actor"])
            if (
                actor.kind != "partner"
                or actor.credential_purpose != "provider_events"
                or actor.actor_id != principal["actor_id"]
                or principal["purpose"] != "provider_events"
                or principal["tenant_id"] != protocol["scope"]["tenant_id"]
                or principal["provider_integration_id"]
                != ref.provider_integration_id
            ):
                raise ValueError
            received = instant(received_at)
            dto = ProviderEventEnvelope.model_validate(envelope)
            context = {
                "actor": actor,
                "scope": Scope.model_validate(protocol["scope"]),
                "provider_integration_id": ref.provider_integration_id,
                "inbox_event_id": inbox_event_id,
                "received_at": received,
            }
            port = self.port
            if self.event_port_factory is not None:
                port = self.event_port_factory(context)
            normalized = await port.normalize_verified_event(actor, ref, dto)
            event = NormalizedJobEvent.model_validate(value(normalized))
            if (
                event.inbox_event_id != inbox_event_id
                or event.received_at != received
                or event.provider_integration_id != ref.provider_integration_id
                or event.external_event_id != dto.external_event_id
                or event.external_job_id != dto.external_job_id
                or event.client_reference != dto.client_reference
                or event.provider_version != dto.provider_version
                or event.occurred_at != dto.occurred_at
                or event.protocol_schema_hash != ref.schema_hash
                or event.source_hash != digest(value(dto))
            ):
                raise ValueError
            mapping = config.event_mappings[dto.event_type]
            if event.normalized_status != mapping.status or event.facts != {
                k: dto.data[k] for k in mapping.fact_fields if k in dto.data
            }:
                raise ValueError
        except (KeyError, ValueError, TypeError, PermissionError, SchemaError):
            raise ExecutionError(
                "PROVIDER_NORMALIZATION_INVALID", 422
            ) from None
        return {
            "status": event.normalized_status,
            "facts": event.facts,
            "provider_version": event.provider_version,
            "order_mode": config.event_mode
            if config.ordering == "provider_version"
            else "transition",
            "terminal": event.normalized_status in config.terminal_statuses,
            "normalized_event": value(event),
        }

    async def validate_transition(
        self, protocol: Any, operation: Any, event: Any
    ) -> str:
        config = protocol_config(protocol)
        current, target = operation["job_status"], event["status"]
        states = set(config.transitions) | set(config.terminal_statuses)
        if target not in states:
            return "conflict"
        if current in config.terminal_statuses:
            content = digest({"status": target, "facts": event["facts"]})
            return (
                "stale"
                if current == target
                and content == operation["last_source_hash"]
                else "conflict"
            )
        if current is None or current == target:
            return "apply"
        targets = set(config.transitions.get(current, ()))
        # A complete, versioned snapshot can skip intermediate states. Deltas
        # and unversioned updates must follow one explicitly declared edge.
        if (
            config.ordering == "provider_version"
            and config.event_mode == "snapshot"
        ):
            pending = list(targets)
            while pending:
                state = pending.pop()
                for following in config.transitions.get(state, ()):
                    if following not in targets:
                        targets.add(following)
                        pending.append(following)
        return "apply" if target in targets else "conflict"

    async def normalize_creation_result(
        self, protocol: Any, output: Any
    ) -> Any:
        config = protocol_config(protocol)
        output = freeze(output)
        if not isinstance(output, dict):
            raise ExecutionError("CREATION_RESULT_INVALID", 422)
        job_id = output.get(config.external_job_id_field)
        status = output.get(config.status_field)
        states = set(config.transitions) | set(config.terminal_statuses)
        if (
            not isinstance(status, str)
            or status not in states
            or (config.external_job_id_field and not job_id)
            or (job_id is not None and not isinstance(job_id, str))
        ):
            raise ExecutionError("CREATION_RESULT_INVALID", 422)
        return {
            "creation_status": "succeeded",
            "external_job_id": job_id,
            "job_status": status,
            "pending": status not in config.terminal_statuses,
        }

    async def normalize_query_result(self, protocol: Any, output: Any) -> Any:
        """Adapt projected query output; no provider call or Registry write."""
        config = protocol_config(protocol)
        if not config.status_query_tool_version_id:
            raise ExecutionError("STATUS_QUERY_UNAVAILABLE")
        result = await self.normalize_creation_result(protocol, output)
        version = output.get("provider_version")
        if version is not None and (type(version) is not int or version < 0):
            raise ExecutionError("PROVIDER_VERSION_REQUIRED", 422)
        if config.ordering == "provider_version" and version is None:
            raise ExecutionError("PROVIDER_VERSION_REQUIRED", 422)
        # Query projection has no event mapping; do not allow arbitrary facts.
        return {
            "status": result["job_status"],
            "facts": {},
            "provider_version": version,
            "terminal": not result["pending"],
            "source_hash": digest(output),
        }
