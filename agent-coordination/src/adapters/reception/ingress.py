"""Mountable V2 input adapter. DEV-5 mounts it; DEV-4 implements durable inbox."""
from __future__ import annotations

import asyncio
import math
from dataclasses import dataclass
from typing import Mapping, Protocol

from adapters.backend.errors import AdapterError
from adapters.backend.messages import fingerprint
from adapters.backend.reception_messages import message_wire
from .reception_gateway import ReceptionGateway


@dataclass(frozen=True)
class PendingReception:
    tenant_id: str
    message_id: str
    fingerprint: str
    message: dict
    context: dict
    supervisor_run_id: str
    room_command: dict | None


class ReceptionInbox(Protocol):
    async def enqueue_once(self, item: PendingReception) -> bool:
        """Atomically store dedup + pending delivery, by tenant/message identity.

        Same ID/content returns False; changed content conflicts. Persist accepted
        resolution and prevent semantic decisions from creating duplicate work.
        Consumption reauthorizes current context/version before calling DEV-1 or
        DEV-2. Do not ACK before durable commit. DEV-4 owns implementation.
        """
        ...


class ReceptionIngress:
    def __init__(self, gateway: ReceptionGateway, *, inbox: ReceptionInbox, timeout: float = 15):
        if not math.isfinite(timeout) or timeout <= 0:
            raise ValueError("invalid inbox timeout")
        self._gateway, self._inbox, self._timeout = gateway, inbox, timeout

    async def receive(self, message: Mapping, *, authentication: object) -> dict:
        wire = message_wire(message)
        resolved = await self._gateway.resolve(wire, authentication)
        verified = resolved.verified
        item = PendingReception(wire["tenant_id"], wire["message_id"], fingerprint(wire), wire,
            verified.context.model_dump(mode="json", exclude_none=True), verified.supervisor_run_id,
            resolved.room_command.model_dump(mode="json", exclude_none=True) if resolved.room_command else None)
        try:
            queued = await asyncio.wait_for(self._inbox.enqueue_once(item), self._timeout)
        except AdapterError:
            raise
        except (TimeoutError, OSError):
            raise AdapterError("inbox_unavailable", retryable=True, outcome_unknown=True) from None
        if type(queued) is not bool:
            raise AdapterError("invalid_inbox_receipt", outcome_unknown=True)
        return {"message_id": item.message_id, "status": "accepted", "queued": queued}
