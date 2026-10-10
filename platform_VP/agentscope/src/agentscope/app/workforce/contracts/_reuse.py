# -*- coding: utf-8 -*-
"""Agent business-equivalence and reuse decision contracts."""

from datetime import datetime
from enum import StrEnum

from pydantic import Field

from ._base import OpaqueId, WorkforceModel


class MatchType(StrEnum):
    SAME_BUSINESS = "same_business"
    PARTIAL_OVERLAP = "partial_overlap"
    DIFFERENT = "different"
    UNCERTAIN = "uncertain"


class ReuseStatus(StrEnum):
    READY = "ready"
    DRAFT = "draft"
    BLOCKED = "blocked"
    INACTIVE = "inactive"


class ReuseAction(StrEnum):
    REUSE = "reuse"
    RESUME = "resume"
    REVISE = "revise"
    CREATE = "create"
    CLARIFY = "clarify"
    REPAIR = "repair"


class ReuseCandidate(WorkforceModel):
    agent_id: OpaqueId
    version_id: OpaqueId | None = None
    draft_id: OpaqueId | None = None
    match_type: MatchType
    reuse_status: ReuseStatus
    covered_requirements: tuple[str, ...] = ()
    missing_requirements: tuple[str, ...] = ()
    differences: tuple[str, ...] = ()
    blockers: tuple[str, ...] = ()
    reason: str = Field(min_length=1, max_length=4000)


class ReuseCheck(WorkforceModel):
    reuse_check_id: OpaqueId
    requirement_hash: str = Field(min_length=1, max_length=200)
    agent_catalog_revision: int = Field(ge=0)
    candidates: tuple[ReuseCandidate, ...]
    recommended_action: ReuseAction
    created_at: datetime


class ReuseDecision(WorkforceModel):
    agent_key: str = Field(min_length=1, max_length=200)
    action: ReuseAction
    reuse_check_id: OpaqueId
    agent_id: OpaqueId | None = None
    version_id: OpaqueId | None = None
    draft_id: OpaqueId | None = None
    reason: str = Field(min_length=1, max_length=4000)
    expected_catalog_revision: int = Field(ge=0)
