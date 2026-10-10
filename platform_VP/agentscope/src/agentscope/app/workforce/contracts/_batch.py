# -*- coding: utf-8 -*-
"""Contracts for creating one or many independent agents."""

from datetime import datetime
from enum import StrEnum

from pydantic import Field, model_validator

from ._base import OpaqueId, WorkforceModel
from ._manifest import AgentSpec
from ._reuse import ReuseAction


class BuildSource(StrEnum):
    CREATE = "create"
    REUSE = "reuse"
    REVISE = "revise"


class BuildItemStatus(StrEnum):
    PROPOSED = "proposed"
    GENERATING = "generating"
    VALIDATING = "validating"
    EVALUATING = "evaluating"
    PASSED = "passed"
    FAILED = "failed"
    PUBLISHED = "published"
    COMPLETED_REUSED = "completed_reused"
    BLOCKED = "blocked"


class BuildBatchStatus(StrEnum):
    PROPOSED = "proposed"
    RUNNING = "running"
    PARTIALLY_READY = "partially_ready"
    READY = "ready"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


class BuildItem(WorkforceModel):
    item_id: OpaqueId
    agent_key: str = Field(min_length=1, max_length=200)
    source: BuildSource
    reuse_action: ReuseAction
    spec: AgentSpec | None = None
    reuse_agent_id: OpaqueId | None = None
    reuse_version_id: OpaqueId | None = None
    target_agent_id: OpaqueId | None = None
    source_version_id: OpaqueId | None = None
    draft_id: OpaqueId | None = None
    evaluation_id: OpaqueId | None = None
    status: BuildItemStatus
    error_code: str | None = Field(default=None, max_length=100)

    @model_validator(mode="after")
    def validate_source_payload(self) -> "BuildItem":
        """Prevent reuse from silently carrying a mutable copied spec."""
        if self.source == BuildSource.REUSE:
            if self.spec is not None:
                raise ValueError("reuse item must not contain a copied spec")
            if self.reuse_agent_id is None or self.reuse_version_id is None:
                raise ValueError("reuse item requires agent and version refs")
        elif self.spec is None:
            raise ValueError("create/revise item requires a spec")
        if self.source == BuildSource.REVISE and self.target_agent_id is None:
            raise ValueError("revise item requires target_agent_id")
        return self


class AgentBuildBatch(WorkforceModel):
    batch_id: OpaqueId
    build_session_id: OpaqueId
    revision: int = Field(ge=1)
    items: tuple[BuildItem, ...]
    status: BuildBatchStatus
    created_at: datetime
    updated_at: datetime
