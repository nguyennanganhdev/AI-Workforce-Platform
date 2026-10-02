"""Submit approvals/confirmations to backend; never advance a room from an ACK."""

from typing import Any, Mapping

from .client import BackendClient, BackendResult
from .operations import send


class ApprovalClient:
    def __init__(self, backend: BackendClient) -> None:
        self._backend = backend

    async def request_plan(self, request: Mapping[str, Any]) -> BackendResult:
        """Backend verifies management approval before delivering resident_plan.

        It persists the canonical plan/cost and delivers to the authorized UI or
        Reception. This is one idempotent backend operation, not two local sends.
        """
        return await send(self._backend, "approval.request", "approval.requested", request)

    async def respond_plan(self, request: Mapping[str, Any]) -> BackendResult:
        """Backend checks authenticated actor, expiry, plan version and generation."""
        return await send(self._backend, "approval.respond", "approval.responded", request)

    async def request_completion(self, request: Mapping[str, Any]) -> BackendResult:
        """Backend checks evidence/QC and recipient before delivering the result."""
        return await send(self._backend, "completion.request", "completion.requested", request)

    async def respond_completion(self, request: Mapping[str, Any]) -> BackendResult:
        """Neither confirmed nor an API receipt is permission to close a ticket."""
        return await send(self._backend, "completion.respond", "completion.responded", request)
