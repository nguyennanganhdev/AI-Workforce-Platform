"""Workforce orchestration services for partner ticket workflows.

SQL/FastAPI adapters are lazy so the base AgentScope package keeps its
optional-dependency boundary.
"""

from importlib import import_module
from typing import Any

from ._ingress import (
    PartnerIngressService,
    RequestRepository,
    RequestView,
    receipt_http_status,
)

__all__ = [
    "ExecutionOperationReader",
    "LeaderBootstrapResolver",
    "LeaderBootstrapSeed",
    "LeaderTurnRunner",
    "LeaderWorkflowBootstrap",
    "PartnerIngressService",
    "RequestRepository",
    "RequestView",
    "SqlCheckpointRepository",
    "SqlEventRepository",
    "SqlPartnerRequestRepository",
    "SqlRuntimeContinuation",
    "SqlWorkflowRepository",
    "WorkflowContinuationJobHandler",
    "create_router",
    "get_metadata",
    "receipt_http_status",
]


_LAZY_EXPORTS = {
    "ExecutionOperationReader": ("._execution", "ExecutionOperationReader"),
    "LeaderBootstrapResolver": ("._runtime", "LeaderBootstrapResolver"),
    "LeaderBootstrapSeed": ("._runtime", "LeaderBootstrapSeed"),
    "LeaderTurnRunner": ("._runtime", "LeaderTurnRunner"),
    "LeaderWorkflowBootstrap": ("._runtime", "LeaderWorkflowBootstrap"),
    "SqlCheckpointRepository": ("._repository", "SqlCheckpointRepository"),
    "SqlEventRepository": ("._repository", "SqlEventRepository"),
    "SqlPartnerRequestRepository": (
        "._repository",
        "SqlPartnerRequestRepository",
    ),
    "SqlRuntimeContinuation": ("._runtime", "SqlRuntimeContinuation"),
    "SqlWorkflowRepository": ("._repository", "SqlWorkflowRepository"),
    "WorkflowContinuationJobHandler": (
        "._runtime",
        "WorkflowContinuationJobHandler",
    ),
    "create_router": ("._router", "create_router"),
}


def get_metadata() -> Any:
    """Return C4 additive metadata for Foundation's C7 Alembic revision."""
    from ._tables import metadata

    return metadata


def __getattr__(name: str):
    target = _LAZY_EXPORTS.get(name)
    if target is None:
        raise AttributeError(name)
    module_name, attribute = target
    value = getattr(import_module(module_name, __name__), attribute)
    globals()[name] = value
    return value
