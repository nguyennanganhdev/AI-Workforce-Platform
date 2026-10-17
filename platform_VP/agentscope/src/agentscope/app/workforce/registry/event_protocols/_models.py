# -*- coding: utf-8 -*-
"""Registry-owned protocol configuration; wire DTOs remain in contracts."""

import hashlib
import json
from typing import Literal

from jsonschema import Draft202012Validator, SchemaError
from pydantic import Field, model_validator
from referencing import Registry
from referencing.exceptions import Unresolvable
from referencing.jsonschema import DRAFT202012

from ...contracts import (
    AsyncProtocolSnapshotRef,
    JsonObject,
    OpaqueId,
    ShortCode,
    ToolEffect,
    WorkforceModel,
)


class EventMapping(WorkforceModel):
    """Map one provider event type to a status and allowlisted facts."""

    status: ShortCode
    data_schema: JsonObject
    fact_fields: tuple[ShortCode, ...] = ()

    @model_validator(mode="after")
    def validate_schema(self) -> "EventMapping":
        try:
            Draft202012Validator.check_schema(self.data_schema)
            root = DRAFT202012.create_resource(self.data_schema)
            # Resolve only bundled schemas; configuration never fetches URLs.
            pending = [(root, Registry().resolver_with_root(root))]
            while pending:
                resource, resolver = pending.pop()
                if isinstance(resource.contents, dict):
                    for keyword in ("$ref", "$dynamicRef"):
                        if keyword in resource.contents:
                            target = resolver.lookup(
                                resource.contents[keyword],
                            )
                            if not isinstance(target.contents, (dict, bool)):
                                raise ValueError(
                                    "reference must target a schema",
                                )
                pending.extend(
                    (child, resolver.in_subresource(child))
                    for child in resource.subresources()
                )
        except (SchemaError, Unresolvable) as exc:
            raise ValueError("invalid event data schema") from exc
        return self


class AsyncToolProtocol(WorkforceModel):
    """Versioned integration metadata configured outside prompts."""

    protocol_id: OpaqueId
    protocol_version: str = Field(min_length=1, max_length=100)
    tool_version_id: OpaqueId
    provider_integration_id: OpaqueId | None = None
    effect: ToolEffect
    result_mode: Literal["terminal", "pending"]
    completion_policy: Literal["read_only_auto_close", "explicit_close"]
    requires_approval: bool = False
    # shortcut: mappings name top-level fields; add paths for nested providers.
    client_reference_field: ShortCode | None = None
    external_job_id_field: ShortCode | None = None
    status_field: ShortCode | None = None
    status_query_tool_version_id: OpaqueId | None = None
    event_schema_version: Literal["1"] = "1"
    event_mappings: dict[ShortCode, EventMapping] = Field(default_factory=dict)
    ordering: Literal[
        "provider_version",
        "transition_only",
    ] = "transition_only"
    event_mode: Literal["snapshot", "delta"] = "snapshot"
    transitions: dict[ShortCode, tuple[ShortCode, ...]] = Field(
        default_factory=dict,
    )
    terminal_statuses: tuple[ShortCode, ...] = ()
    timeout_seconds: int | None = Field(default=None, gt=0)

    @model_validator(mode="after")
    def validate_protocol(self) -> "AsyncToolProtocol":
        if self.completion_policy == "read_only_auto_close" and (
            self.effect != ToolEffect.READ
            or self.result_mode != "terminal"
            or self.requires_approval
        ):
            raise ValueError(
                "auto-close requires terminal read without approval",
            )
        if self.result_mode == "terminal":
            if any(
                (
                    self.client_reference_field,
                    self.external_job_id_field,
                    self.status_field,
                    self.status_query_tool_version_id,
                    self.event_mappings,
                    self.transitions,
                    self.terminal_statuses,
                    self.timeout_seconds,
                ),
            ):
                raise ValueError("terminal result must not configure tracking")
        else:
            if not (
                self.provider_integration_id
                and (self.external_job_id_field or self.client_reference_field)
                and self.status_field
                and self.terminal_statuses
                and self.timeout_seconds
            ):
                raise ValueError(
                    "pending result requires provider, correlation, status, "
                    "terminal statuses and timeout",
                )
            states = set(self.transitions) | set(self.terminal_statuses)
            for source, targets in self.transitions.items():
                if not set(targets) <= states:
                    raise ValueError("transition target is not declared")
                if source in self.terminal_statuses and targets:
                    raise ValueError("terminal status must not transition")
            if any(
                m.status not in states for m in self.event_mappings.values()
            ):
                raise ValueError("event status is not declared")
        if self.event_mode == "delta" and self.ordering != "provider_version":
            raise ValueError("delta events require provider_version ordering")
        return self

    @property
    def snapshot_ref(self) -> AsyncProtocolSnapshotRef:
        """Hash all configuration, including mappings and completion policy."""
        capabilities = [
            "create" if self.result_mode == "pending" else "terminal",
        ]
        if self.event_mappings:
            capabilities.append("receive_status")
        if self.status_query_tool_version_id:
            capabilities.append("status_query")
        if self.requires_approval:
            capabilities.append("approval")
        canonical = json.dumps(
            self.model_dump(mode="json"),
            sort_keys=True,
            separators=(",", ":"),
            ensure_ascii=False,
            allow_nan=False,
        )
        return AsyncProtocolSnapshotRef(
            protocol_id=self.protocol_id,
            protocol_version=self.protocol_version,
            schema_hash=hashlib.sha256(canonical.encode()).hexdigest(),
            tool_version_id=self.tool_version_id,
            provider_integration_id=self.provider_integration_id,
            capabilities=tuple(capabilities),
        )
