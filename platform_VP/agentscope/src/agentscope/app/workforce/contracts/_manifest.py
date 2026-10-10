# -*- coding: utf-8 -*-
"""Canonical single-agent manifest contracts."""

from enum import StrEnum

from pydantic import Field

from ._base import JsonObject, OpaqueId, WorkforceModel
from ._catalog import ToolBinding


class SideEffectPolicy(StrEnum):
    READ_ONLY = "read_only"
    REQUIRE_APPROVAL = "require_approval"
    ALLOW_WITHIN_POLICY = "allow_within_policy"


class BusinessProfile(WorkforceModel):
    profile_schema_version: str = Field(min_length=1, max_length=32)
    objective: str = Field(min_length=1, max_length=4000)
    responsibilities: tuple[str, ...]
    capabilities: tuple[str, ...]
    input_contract: JsonObject
    output_contract: JsonObject
    business_scope: str = Field(min_length=1, max_length=2000)
    required_constraints: tuple[str, ...] = ()
    execution_policy: SideEffectPolicy
    knowledge_requirements: tuple[str, ...] = ()


class AgentSpec(WorkforceModel):
    agent_key: str = Field(min_length=1, max_length=200)
    name: str = Field(min_length=1, max_length=200)
    description: str = Field(default="", max_length=4000)
    capabilities: tuple[str, ...]
    system_prompt: str = Field(min_length=1)
    model_config_ref: JsonObject
    context_config: JsonObject = Field(default_factory=dict)
    react_config: JsonObject = Field(default_factory=dict)
    tool_bindings: tuple[ToolBinding, ...] = ()
    knowledge_bindings: tuple[OpaqueId, ...] = ()
    skill_bindings: tuple[OpaqueId, ...] = ()
    collaboration_policy: JsonObject = Field(default_factory=dict)
    execution_policy: JsonObject = Field(default_factory=dict)


class AgentManifest(WorkforceModel):
    schema_version: str = Field(min_length=1, max_length=32)
    business_profile: BusinessProfile
    spec: AgentSpec
    async_policy_ref: OpaqueId | None = None
    protocol_snapshot_hashes: tuple[str, ...] = ()


class AgentReuseRef(WorkforceModel):
    agent_id: OpaqueId
    version_id: OpaqueId
    manifest_hash: str = Field(min_length=1, max_length=200)
