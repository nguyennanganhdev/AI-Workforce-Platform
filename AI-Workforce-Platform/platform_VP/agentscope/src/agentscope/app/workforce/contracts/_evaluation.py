# -*- coding: utf-8 -*-
"""Evaluation snapshots and reports for a single agent draft."""

from datetime import datetime
from enum import StrEnum

from pydantic import Field

from ._base import JsonObject, OpaqueId, WorkforceModel
from ._identity import Scope
from ._manifest import AgentManifest


class EvaluationStatus(StrEnum):
    QUEUED = "queued"
    RUNNING = "running"
    PASSED = "passed"
    FAILED = "failed"
    CANCELLED = "cancelled"
    ERROR = "error"


class EvaluationSnapshot(WorkforceModel):
    snapshot_id: OpaqueId
    scope: Scope
    agent_id: OpaqueId
    draft_id: OpaqueId
    draft_revision: int = Field(ge=1)
    source_draft_hash: str = Field(min_length=1, max_length=200)
    candidate_version_id: OpaqueId
    manifest: AgentManifest
    manifest_hash: str = Field(min_length=1, max_length=200)
    tool_snapshot_hash: str = Field(min_length=1, max_length=200)
    test_context_hash: str = Field(min_length=1, max_length=200)
    created_at: datetime


class EvaluationCaseResult(WorkforceModel):
    case_id: OpaqueId
    status: EvaluationStatus
    metrics: JsonObject = Field(default_factory=dict)
    hard_gate_failures: tuple[str, ...] = ()
    transcript_ref: OpaqueId | None = None
    tool_trace_ref: OpaqueId | None = None
    error_code: str | None = Field(default=None, max_length=100)


class EvaluationReport(WorkforceModel):
    evaluation_id: OpaqueId
    agent_id: OpaqueId
    draft_id: OpaqueId
    draft_revision: int = Field(ge=1)
    manifest_hash: str = Field(min_length=1, max_length=200)
    snapshot_id: OpaqueId
    suite_version: str = Field(min_length=1, max_length=100)
    runtime_profile_hash: str = Field(min_length=1, max_length=200)
    tool_snapshot_hash: str = Field(min_length=1, max_length=200)
    test_context_hash: str = Field(min_length=1, max_length=200)
    status: EvaluationStatus
    metrics: JsonObject = Field(default_factory=dict)
    hard_gate_failures: tuple[str, ...] = ()
    cases: tuple[EvaluationCaseResult, ...] = ()
    started_at: datetime | None = None
    finished_at: datetime | None = None
