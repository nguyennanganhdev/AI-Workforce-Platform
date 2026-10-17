# -*- coding: utf-8 -*-
"""MCP connection and tool catalog contracts."""

from datetime import datetime
from enum import StrEnum

from pydantic import Field

from ._base import JsonObject, OpaqueId, WorkforceModel
from ._identity import Scope


class ConnectionStatus(StrEnum):
    CONNECTING = "connecting"
    SYNCING = "syncing"
    READY = "ready"
    ERROR = "error"
    DISABLED = "disabled"


class ToolEffect(StrEnum):
    READ = "read"
    WRITE = "write"
    EXTERNAL_OPERATION = "external_operation"


class PartnerMcpDefinition(WorkforceModel):
    mcp_id: OpaqueId
    partner_id: OpaqueId
    name: str = Field(min_length=1, max_length=200)
    description: str = Field(default="", max_length=4000)
    catalog_version: str = Field(min_length=1, max_length=100)
    transport: str = Field(min_length=1, max_length=64)
    connection_schema: JsonObject
    endpoint_template: str | None = Field(default=None, max_length=2048)
    status: str = Field(min_length=1, max_length=64)


class McpConnection(WorkforceModel):
    connection_id: OpaqueId
    mcp_id: OpaqueId
    scope: Scope
    desired_enabled: bool
    status: ConnectionStatus
    credential_ref: OpaqueId | None = None
    catalog_revision: int = Field(ge=0)
    last_sync_at: datetime | None = None
    last_error_code: str | None = Field(default=None, max_length=100)


class ToolDescriptor(WorkforceModel):
    tool_id: OpaqueId
    tool_version_id: OpaqueId
    connection_id: OpaqueId | None = None
    source_kind: str = Field(pattern="^(mcp|builtin)$")
    provider_tool_name: str = Field(min_length=1, max_length=200)
    llm_alias: str = Field(min_length=1, max_length=200)
    description: str = Field(default="", max_length=8000)
    input_schema: JsonObject
    output_schema: JsonObject | None = None
    schema_hash: str = Field(min_length=1, max_length=200)
    capabilities: tuple[str, ...] = ()
    effect: ToolEffect
    available: bool


class ToolBinding(WorkforceModel):
    tool_id: OpaqueId
    tool_version_id: OpaqueId
    schema_hash: str = Field(min_length=1, max_length=200)
    required_capability: str = Field(min_length=1, max_length=200)
    selection_reason: str = Field(min_length=1, max_length=4000)
