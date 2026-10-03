"""Remote event verification; server owns committed state and current routing."""
from __future__ import annotations

import asyncio
import math
from typing import Mapping

from .client import BackendClient
from .errors import AdapterError
from .events import ResolvedEvent
from .messages import fingerprint, snapshot, validate_context, validate_event


class BackendEventVerifier:
    def __init__(self, backend: BackendClient, *, authentication, timeout: float = 15):
        if authentication is None or not math.isfinite(timeout) or timeout <= 0:
            raise ValueError("event authentication/deadline required")
        self._backend, self._auth, self._timeout = backend, authentication, timeout

    async def resolve(self, event: Mapping, authentication: object) -> ResolvedEvent:
        from adapters.reception.authentication import proof_headers

        wire = snapshot(event)
        validate_event(wire)
        try:
            headers = await asyncio.wait_for(
                proof_headers(self._auth, authentication, wire, purpose="event"), self._timeout)
        except AdapterError:
            raise
        except TimeoutError:
            raise AdapterError("verification_unavailable", retryable=True) from None
        except Exception:
            raise AdapterError("event_not_authorized") from None
        data = await self._backend.call_contract("event.verify", wire,
            request_schema="event", response_schema="event_verification_response",
            identity="event_id", authentication_headers=headers)
        try:
            if (set(data) != {"context", "event_fingerprint", "committed"}
                    or data["committed"] is not True
                    or data["event_fingerprint"] != fingerprint(wire)):
                raise ValueError()
            validate_context(data["context"])
            from groupchat.models import Context
            Context.model_validate(data["context"], strict=True)
            if data["context"]["tenant_id"] != wire["tenant_id"]:
                raise ValueError()
        except Exception:
            raise AdapterError("invalid_backend_response", outcome_unknown=True) from None
        return ResolvedEvent(snapshot(data["context"]))
