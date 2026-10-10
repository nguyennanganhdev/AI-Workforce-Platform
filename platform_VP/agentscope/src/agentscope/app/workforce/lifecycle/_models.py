"""Lifecycle-owned persistence records; shared DTOs are imported unchanged."""

from datetime import datetime, timezone
from hashlib import sha256
import json
from typing import Any, Dict, List, Optional, Tuple
from uuid import uuid4

from pydantic import Field

from ..contracts import (
    AgentManifest,
    BusinessProfile,
    EvaluationReport,
    EvaluationSnapshot,
    ReuseDecision,
    Scope,
    WorkforceModel,
)


def now() -> datetime:
    return datetime.now(timezone.utc)


def new_id() -> str:
    return str(uuid4())


def canonical_hash(value: Any) -> str:
    """Hash JSON content, independent of mapping insertion order."""
    if isinstance(value, WorkforceModel):
        value = value.model_dump(mode="json")
    return sha256(
        json.dumps(
            value,
            sort_keys=True,
            separators=(",", ":"),
            ensure_ascii=False,
            allow_nan=False,
        ).encode()
    ).hexdigest()


def has_external_schema_ref(value: Any) -> bool:
    """Evaluation must not fetch arbitrary remote JSON Schema references."""
    if isinstance(value, dict):
        for key, item in value.items():
            if key in ("$ref", "$dynamicRef", "$recursiveRef"):
                if not isinstance(item, str) or not item.startswith("#"):
                    return True
            if has_external_schema_ref(item):
                return True
    elif isinstance(value, (list, tuple)):
        return any(has_external_schema_ref(item) for item in value)
    return False


class LifecycleError(Exception):
    def __init__(
        self,
        code: str,
        status: int = 409,
        details: Optional[Dict[str, Any]] = None,
    ) -> None:
        super().__init__(code)
        self.code = code
        self.status = status
        self.details = details or {}


class ValidationReport(WorkforceModel):
    valid: bool
    blockers: Tuple[str, ...] = ()
    tool_snapshot_hash: str
    protocol_hash: str
    dependency_hash: str
    tool_snapshots: Tuple[Dict[str, Any], ...] = ()


class AgentDefinition(WorkforceModel):
    agent_id: str
    scope: Scope
    name: str
    business_key: str
    business_profile: BusinessProfile
    status: str = "draft"
    active_version_id: Optional[str] = None
    draft_id: Optional[str] = None
    revision: int = Field(ge=1)
    legacy_agent_id: Optional[str] = None


class AgentDraft(WorkforceModel):
    draft_id: str
    agent_id: str
    scope: Scope
    revision: int = Field(ge=1)
    manifest: AgentManifest
    manifest_hash: str
    reuse_decision: ReuseDecision
    source_version_id: Optional[str] = None
    batch_id: Optional[str] = None
    validation_report: Optional[ValidationReport] = None
    created_at: datetime
    updated_at: datetime


class PublishedVersion(WorkforceModel):
    version_id: str
    agent_id: str
    scope: Scope
    manifest: AgentManifest
    manifest_hash: str
    source_draft_hash: str
    evaluation_id: str
    published_by: str
    published_at: datetime
    protocol_refs: Tuple[Dict[str, Any], ...] = ()
    policy_snapshot: Dict[str, Any] = Field(default_factory=dict)
    validation: ValidationReport


class Deployment(WorkforceModel):
    deployment_id: str
    agent_id: str
    scope: Scope
    active_version_id: str
    revision: int = Field(ge=1)
    status: str = "active"


class EvaluationRecord(WorkforceModel):
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


class PublishSelection(WorkforceModel):
    draft_id: str
    expected_revision: int = Field(ge=1)
    evaluation_id: str
    manifest_hash: str


def manifest_diff(
    before: AgentManifest, after: AgentManifest
) -> List[Dict[str, Any]]:
    changes: List[Dict[str, Any]] = []

    def walk(left: Any, right: Any, path: str) -> None:
        if isinstance(left, dict) and isinstance(right, dict):
            for key in sorted(set(left).union(right)):
                walk(left.get(key), right.get(key), f"{path}/{key}")
        elif left != right:
            changes.append({"path": path, "before": left, "after": right})

    walk(before.model_dump(mode="json"), after.model_dump(mode="json"), "")
    return changes
