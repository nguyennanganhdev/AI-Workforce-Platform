"""Authenticated backend events -> durable room inbox (DEV-4/DEV-5 port).

No callback is executed inline after marking an event processed: that loses
work on a crash. enqueue_once must atomically persist dedup + pending delivery.
"""

from __future__ import annotations

import asyncio
import math
from copy import deepcopy
from dataclasses import dataclass
from typing import Any, Literal, Mapping, Protocol

from .errors import AdapterError, ValidationError
from .messages import (
    ContractValidator, JSON, fingerprint, snapshot, validate_context,
    validate_event, validate_payload, validate_with,
)

INBOUND_TYPES = frozenset({
    "ticket.submitted", "resident.message", "approval.responded",
    "assignment.offered", "assignment.responded", "work.completed", "completion.responded",
})


@dataclass(frozen=True)
class ResolvedEvent:
    context: Mapping[str, Any]


class EventVerifier(Protocol):
    async def resolve(
        self, event: Mapping[str, Any], authentication: object
    ) -> ResolvedEvent:
        """Authenticate backend event, then resolve its CURRENT authorized binding.

        Must verify audience/expiry/signature or trusted backend lookup, tenant,
        aggregate link, recipient/sender rights, request/reply correlation,
        generation, plan/result/assignment version, approval stage/expiry and
        committed decision. Reject raw/uncommitted responses and stale events.
        Do not return a context copied from a client body. Fail closed.
        """
        ...


@dataclass(frozen=True)
class PendingDelivery:
    tenant_id: str
    event_id: str
    fingerprint: str
    target: Literal["supervisor", "groupchat"]
    message_type: str
    context: JSON
    event: JSON


class DurableInbox(Protocol):
    async def enqueue_once(self, delivery: PendingDelivery) -> bool:
        """In one durable transaction: dedup and enqueue, scoped by tenant/event ID.

        Return True for a newly persisted pending item, False for an identical
        duplicate. Same ID/different fingerprint -> AdapterError('conflict').
        Handle races atomically and persist across restarts. Recheck current
        generation/version under the transaction/fence; update aggregate ordering
        consistently. Worker delivery/resume must be idempotent by event ID and
        reauthorize at consumption. DEV-4 owns storage/worker implementation.
        """
        ...


@dataclass(frozen=True)
class EventReceipt:
    event_id: str
    queued: bool
    # queued=False is an identical duplicate; queued=True is NOT business success.


class EventIngress:
    def __init__(
        self, *, verifier: EventVerifier, inbox: DurableInbox,
        validator: ContractValidator, event_types: Mapping[str, str], timeout: float = 15,
    ) -> None:
        # Event names belong to the backend catalog. Configure their mapping to
        # documented payload types instead of inventing canonical event names.
        if any(kind not in INBOUND_TYPES for kind in event_types.values()):
            raise ValueError("unsupported inbound payload type")
        if not math.isfinite(timeout) or timeout <= 0:
            raise ValueError("invalid timeout")
        self._verifier = verifier
        self._inbox = inbox
        self._validator = validator
        self._types = dict(event_types)
        self._timeout = timeout

    async def receive(self, event: Mapping[str, Any], *, authentication: object) -> EventReceipt:
        wire = snapshot(event)
        validate_event(wire)
        validate_with(self._validator, "event", wire)
        kind = self._types.get(wire["event_type"])
        if kind is None:
            raise AdapterError("event_not_supported")
        validate_payload(kind, wire["payload"])
        try:
            resolved = await asyncio.wait_for(
                self._verifier.resolve(deepcopy(wire), authentication), self._timeout
            )
        except AdapterError:
            raise
        except TimeoutError:
            raise AdapterError("verification_unavailable", retryable=True) from None
        except Exception:
            raise AdapterError("event_not_authorized") from None
        context = snapshot(resolved.context)
        validate_context(context)
        if context["tenant_id"] != wire["tenant_id"]:
            raise AdapterError("event_not_authorized")
        target = ("groupchat" if kind == "resident.message"
                  and wire["payload"].get("mentioned_agent_id") else "supervisor")
        delivery = PendingDelivery(
            wire["tenant_id"], wire["event_id"], fingerprint(wire), target, kind, context, wire
        )
        try:
            queued = await asyncio.wait_for(self._inbox.enqueue_once(delivery), self._timeout)
        except AdapterError:
            raise
        except (TimeoutError, OSError):
            raise AdapterError("inbox_unavailable", retryable=True, outcome_unknown=True) from None
        if type(queued) is not bool:
            raise AdapterError("invalid_inbox_receipt", outcome_unknown=True)
        return EventReceipt(wire["event_id"], queued)
