"""Backend verification and authorized delivery for Reception schema 2.0."""
from __future__ import annotations

import asyncio
import math
from typing import Any, Mapping, Protocol

from .client import BackendClient, ReceptionReceipt
from .errors import AdapterError, ValidationError
from .messages import validate_with
from .reception_messages import ReceptionResolution, message_wire, verified_resolution


class ReceptionAuthentication(Protocol):
    async def headers(self, authentication: object) -> Mapping[str, str]:
        """Bind transport authentication to this request, never to message fields.

        Supply backend-verifiable delegation/source proof in dedicated headers.
        Do not overwrite service credentials or store a mutable current user.
        Reject missing/untrusted proof. Authentication is not JSON message data.
        """
        ...


class ReceptionClient:
    def __init__(
        self, backend: BackendClient, *, authentication: ReceptionAuthentication | None = None,
        timeout: float = 15,
    ) -> None:
        if not math.isfinite(timeout) or timeout <= 0:
            raise ValueError("invalid timeout")
        self._backend, self._authentication, self._timeout = backend, authentication, timeout

    async def resolve(self, message: Any, authentication: object) -> ReceptionResolution:
        wire = message_wire(message)
        if self._authentication is None:
            raise AdapterError("reception_authentication_required")
        try:
            headers = dict(await asyncio.wait_for(
                self._authentication.headers(authentication), self._timeout))
        except AdapterError:
            raise
        except TimeoutError:
            raise AdapterError("verification_unavailable", retryable=True) from None
        except Exception:
            raise AdapterError("reception_not_authorized") from None
        receipt = await self._backend.call_reception(
            "reception.verify", wire, direction="input", authentication_headers=headers)
        try:
            validate_with(self._backend.validator, "reception_verified", receipt.data)
        except AdapterError:
            raise AdapterError("invalid_backend_response", outcome_unknown=True) from None
        return verified_resolution(wire, receipt.data)

    async def send(self, message: Any, context: Any) -> ReceptionReceipt:
        from groupchat.models import Context

        wire = message_wire(message, output=True)
        if isinstance(context, Context):
            context = context.model_dump(mode="json", exclude_none=True)
        if not isinstance(context, Mapping):
            raise ValidationError()
        return await self._backend.call_reception("reception.send",
            {"message": wire, "context": dict(context)}, direction="output")
