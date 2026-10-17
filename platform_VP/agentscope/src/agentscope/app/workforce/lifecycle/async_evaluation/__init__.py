"""Validation, grading and lazily loaded SQL/runtime evaluation adapters."""

from importlib import import_module
from typing import Any

from ._schema import phase_a_schema_bundle, phase_c_schema_bundle
from ._validation import AsyncDraftValidator, canonical_hash, validate_async_draft
from ._suites import ExpectedTurn, LifecycleCase, LifecycleSuite, lifecycle_suite
from ._evaluation import (
    AsyncEvaluationService,
    FrozenEvaluation,
    TurnEvidence,
    check_release_evidence,
    freeze_evaluation,
    grade_case,
)

__all__ = [
    "phase_a_schema_bundle",
    "phase_c_schema_bundle",
    "AsyncDraftValidator",
    "canonical_hash",
    "validate_async_draft",
    "ExpectedTurn",
    "LifecycleCase",
    "LifecycleSuite",
    "lifecycle_suite",
    "AsyncEvaluationService",
    "FrozenEvaluation",
    "TurnEvidence",
    "check_release_evidence",
    "freeze_evaluation",
    "grade_case",
    "get_metadata",
    "SqlEvaluationRepository",
    "SqlRuntimeEvidenceWriter",
    "RuntimeAudit",
    "RuntimeObservation",
    "RuntimeCaseDriver",
    "RuntimeEvaluationRunner",
    "EvaluationJobService",
    "EvaluationJobHandler",
    "check_persisted_release",
]


def __getattr__(name: str) -> Any:
    modules = {
        "get_metadata": "_tables",
        "SqlEvaluationRepository": "_repository",
        "SqlRuntimeEvidenceWriter": "_repository",
        "RuntimeAudit": "_runtime",
        "RuntimeObservation": "_runtime",
        "RuntimeCaseDriver": "_runtime",
        "RuntimeEvaluationRunner": "_runtime",
        "EvaluationJobService": "_jobs",
        "EvaluationJobHandler": "_jobs",
        "check_persisted_release": "_jobs",
    }
    if name not in modules:
        raise AttributeError(name)
    return getattr(import_module("." + modules[name], __name__), name)
