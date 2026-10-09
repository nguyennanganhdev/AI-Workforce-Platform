"""The agent profile: everything an agent needs to know about itself."""
from __future__ import annotations

import re
from typing import Literal

from pydantic import BaseModel, Field, field_validator

MARKER = re.compile(r'<awp-profile key="([^"]+)" v="(\d+)"/>')


class KnowledgeRef(BaseModel):
    """Knowledge the platform user attached to this agent.

    `knowledge_base_ids` are AgentScope knowledge bases (documents the user
    uploaded). MCP servers and skills are listed by name and are granted to
    the agent through `tools_allow` patterns (`mcp__<server>__*`).
    """

    knowledge_base_ids: list[str] = Field(default_factory=list)
    mcp_servers: list[str] = Field(default_factory=list)
    skills: list[str] = Field(default_factory=list)


class MemoryConfig(BaseModel):
    enabled: bool = False
    # private: this agent only; team: shared read-only notes of the domain
    scope: Literal["private", "team"] = "private"


class AgentProfile(BaseModel):
    key: str = Field(pattern=r"^[a-z][a-z0-9_]{1,40}$")
    name: str
    role: Literal["leader", "specialist"] = "specialist"
    # Who am I and what do I do (one or two sentences).
    mission: str
    handles: list[str] = Field(default_factory=list)
    refuses: list[str] = Field(default_factory=list)
    # Domain instructions in the domain's language.
    instructions: str = ""
    # Extra tool name patterns on top of the role defaults, e.g. "search_knowledge".
    tools_allow: list[str] = Field(default_factory=list)
    # Leader only: specialist keys it may bring into a case.
    team: list[str] = Field(default_factory=list)
    knowledge: KnowledgeRef = Field(default_factory=KnowledgeRef)
    memory: MemoryConfig = Field(default_factory=MemoryConfig)
    model_tier: Literal["cheap", "standard", "strong"] = "standard"
    max_iters: int = Field(default=12, ge=2, le=40)
    # Shown to the leader when it chooses whom to bring in.
    invite_description: str = ""
    # When to stop and ask a person.
    escalate_when: list[str] = Field(default_factory=list)

    @field_validator("team")
    @classmethod
    def _leader_only(cls, v, info):
        if v and info.data.get("role") == "specialist":
            raise ValueError("only a leader can have a team")
        return v


class ProfileRecord(BaseModel):
    id: str
    tenant: str
    key: str
    version: int
    status: Literal["draft", "published", "retired"]
    profile: AgentProfile
    created_at: float
