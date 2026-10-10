"""Opt-in Workforce Lifecycle; optional SQL/FastAPI imports stay lazy."""

from typing import Any

__all__ = [
    "LifecycleService",
    "LifecycleRepository",
    "ManifestValidator",
    "SuiteCatalog",
    "EvaluationSuite",
    "create_router",
    "metadata",
    "AgentDefinition",
    "AgentDraft",
    "PublishedVersion",
    "Deployment",
    "EvaluationRecord",
    "ValidationReport",
    "PublishSelection",
    "ResourceValidationPort",
    "AsyncPolicyPort",
    "VersionUsagePort",
    "QualityJudgePort",
]


def __getattr__(name: str) -> Any:
    if name in (
        "AgentDefinition",
        "AgentDraft",
        "PublishedVersion",
        "Deployment",
        "EvaluationRecord",
        "ValidationReport",
        "PublishSelection",
    ):
        from . import _models

        return getattr(_models, name)
    if name in ("ResourceValidationPort", "AsyncPolicyPort"):
        from . import _validation

        return getattr(_validation, name)
    if name == "VersionUsagePort":
        from ._versions import VersionUsagePort

        return VersionUsagePort
    if name == "QualityJudgePort":
        from ._judges import QualityJudgePort

        return QualityJudgePort
    if name == "LifecycleService":
        from ._service import LifecycleService

        return LifecycleService
    if name == "LifecycleRepository":
        from ._repository import LifecycleRepository

        return LifecycleRepository
    if name == "ManifestValidator":
        from ._validation import ManifestValidator

        return ManifestValidator
    if name in ("SuiteCatalog", "EvaluationSuite"):
        from ._suites import EvaluationSuite, SuiteCatalog

        return {
            "SuiteCatalog": SuiteCatalog,
            "EvaluationSuite": EvaluationSuite,
        }[name]
    if name == "create_router":
        from ._router import create_router

        return create_router
    if name == "metadata":
        from ._tables import metadata

        return metadata
    raise AttributeError(name)
