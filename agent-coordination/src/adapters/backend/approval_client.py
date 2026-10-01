"""Management approval through backend; resident exchanges use Reception V2."""

from typing import Any, Mapping

from .client import BackendClient, BackendResult
from .errors import AdapterError
from .operations import send


class ApprovalClient:
    def __init__(self, backend: BackendClient) -> None:
        self._backend = backend

    async def request_plan(self, request: Mapping[str, Any]) -> BackendResult:
        """Backend persists the canonical plan/cost and requests management approval."""
        return await send(self._backend, "approval.request", "approval.requested", request)

    async def respond_plan(self, request: Mapping[str, Any]) -> BackendResult:
        """Backend checks authenticated actor, expiry, plan version and generation."""
        return await send(self._backend, "approval.respond", "approval.responded", request)

    async def request_completion(self, request: Mapping[str, Any]) -> BackendResult:
        """Reject the old bridge operation; retained only for DEV-1 bridge binding.

        No request is sent. V2 uses ReceptionGateway.send(completed); backend owns
        resident confirmation/closure. DEV-1 may remove its obsolete bridge entry.
        """
        raise AdapterError("reception_protocol_not_supported")
