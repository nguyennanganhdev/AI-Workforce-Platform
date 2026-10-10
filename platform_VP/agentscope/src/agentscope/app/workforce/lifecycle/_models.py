"""Phase A proposals for validation evidence and evaluation snapshots.

Shared DTOs remain owned by Foundation. These aggregates describe the
Lifecycle handoff contract; they do not implement persistence or execution.
"""

from typing import Any, Dict, Optional, Tuple

from pydantic import Field

from ..contracts import (
    EvaluationReport,
    EvaluationSnapshot,
    Scope,
    WorkforceModel,
)


class ValidationReport(WorkforceModel):
    """Validation outcome and dependency evidence for one agent draft."""

    valid: bool
    blockers: Tuple[str, ...] = ()
    tool_snapshot_hash: str
    protocol_hash: str
    dependency_hash: str
    tool_snapshots: Tuple[Dict[str, Any], ...] = ()


class EvaluationRecord(WorkforceModel):
    """Proposed aggregate joining shared evaluation DTOs and frozen context."""

    scope: Scope
    revision: int = Field(ge=1)
    snapshot: EvaluationSnapshot
    report: EvaluationReport
    suite_hash: str
    runtime_profile: Dict[str, Any]
    test_context: Dict[str, Any]
    validation: ValidationReport
    protocol_refs: Tuple[Dict[str, Any], ...] = ()
    policy_snapshot: Dict[str, Any] = Field(default_factory=dict)
    gate_config: Dict[str, Any]
    job_id: Optional[str] = None
    artifacts: Dict[str, Any] = Field(default_factory=dict)
