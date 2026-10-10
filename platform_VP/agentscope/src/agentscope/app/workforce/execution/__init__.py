# -*- coding: utf-8 -*-
"""
Execution exports. SQL/SDK/FastAPI dependencies are loaded only when used.
"""

from typing import Any

from ._approvals import ApprovalService
from ._calculator import (
    calculate,
    calculator_catalog_descriptor,
    calculator_descriptor,
)
from ._gateway import ExecutionGateway
from ._partner_approval import PartnerApprovalService
from ._policy import ExecutionPolicy
from ._router import create_router
from ._transactions import TransactionService
from ._utils import ExecutionError


def get_metadata() -> Any:
    """
    Foundation merges this metadata into its single Alembic migration chain.
    """
    from ._repository import metadata

    return metadata


def create_repository(session_factory: Any) -> Any:
    """Reuse Foundation's session factory instead of a second engine."""
    from ._repository import ExecutionRepository

    return ExecutionRepository(session_factory)


__all__ = [
    "ApprovalService",
    "ExecutionGateway",
    "ExecutionPolicy",
    "ExecutionError",
    "PartnerApprovalService",
    "TransactionService",
    "calculate",
    "calculator_catalog_descriptor",
    "calculator_descriptor",
    "create_router",
    "create_repository",
    "get_metadata",
]
