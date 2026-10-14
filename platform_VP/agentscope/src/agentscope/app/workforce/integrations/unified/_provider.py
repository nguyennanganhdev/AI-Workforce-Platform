"""Provider events of unified mode (contract section 10).

The integration's event schema comes from the partner declaration::

    {"job.accepted": {"status": "accepted", "rank": 20, "public_status": ...,
                      "public_fields": [...], "field_types": {...},
                      "message": "... {staff_name} ...", "wake": bool,
                      "evidence": bool, "terminal": bool, "outcome": ...}}

One event is: authenticated (API key + HMAC), checked against the schema,
deduplicated by ``external_event_id``, matched to the operation the tool call
started (``client_reference`` / ``external_job_id``), ignored when its rank
is below what the operation already reached (``STALE_EVENT``), and applied:
a template message goes straight to the end user, evidence is logged for the
leader to cite, ``wake`` events start a leader turn, terminal events end the
operation. No model takes part in routing.
"""

from __future__ import annotations

import hashlib
import json
from collections.abc import Callable
from datetime import UTC, datetime
from typing import Any
from uuid import uuid4

from pydantic import ValidationError
from sqlalchemy import insert, select, update

from ...contracts import (
    ActorContext,
    ActorKind,
    CredentialPurpose,
    ProviderEventEnvelope,
    Scope,
)
from ...orchestration.workflows._models import parse_aggregate
from ._case import CaseStore
from ._tables import case_sessions, integrations, operations, receipts


class ProviderError(Exception):
    def __init__(self, status: int, code: str, details: dict | None = None) -> None:
        super().__init__(code)
        self.status, self.code, self.details = status, code, details or {}


def _now() -> datetime:
    return datetime.now(UTC)


def _iso(value: datetime | None) -> str | None:
    if value is None:
        return None
    if value.tzinfo is None:
        value = value.replace(tzinfo=UTC)
    return value.isoformat()


def _render(template: str, data: dict) -> str:
    class _Missing(dict):
        def __missing__(self, key):  # a field the schema does not require
            return ""

    return template.format_map(_Missing({k: v for k, v in data.items() if isinstance(v, (str, int, float))}))


def check_event(schema: dict, event_type: str, data: dict) -> dict:
    """The schema entry of ``event_type``; raises 422 for what it forbids."""

    events = (schema or {}).get("events") or {}
    entry = events.get(event_type)
    if entry is None:
        raise ProviderError(422, "EVENT_TYPE_UNKNOWN", {"event_type": event_type})
    types = entry.get("field_types") or {}
    problems = []
    for field in entry.get("public_fields") or []:
        value = data.get(field)
        if value is None or value == "" or value == []:
            problems.append(f"{field}: required")
        elif types.get(field) == "count" and (not isinstance(value, int) or isinstance(value, bool) or value < 0):
            problems.append(f"{field}: whole number expected")
    if problems:
        raise ProviderError(422, "EVENT_DATA_INVALID", {"fields": problems})
    return entry


class UnifiedProviderEvents:
    def __init__(
        self,
        uows: Callable[[], Any],
        auth: Any,
        store: CaseStore,
        workflows: Any,
        events: Any,
        ids: Callable[[], str] = lambda: uuid4().hex,
        requests: Any = None,
    ) -> None:
        self._uows = uows
        self._auth = auth
        self._store = store
        self._requests = requests
        self._workflows = workflows
        self._events = events
        self._ids = ids

    async def _principal(self, raw: bytes, headers: dict) -> Any:
        if self._auth is None:
            raise ProviderError(503, "PROVIDER_EVENTS_DISABLED")
        try:
            return await self._auth.authenticate(raw, headers)
        except RuntimeError:
            raise
        except Exception as exc:  # bad/expired key, signature, timestamp
            raise ProviderError(401, "PROVIDER_AUTH_FAILED", {"reason": str(exc)[:200]}) from exc

    async def accept(self, raw: bytes, headers: dict) -> tuple[int, dict]:
        principal = await self._principal(raw, headers)
        try:
            envelope = ProviderEventEnvelope.model_validate(json.loads(raw))
        except (ValueError, ValidationError) as exc:
            raise ProviderError(422, "PROVIDER_EVENT_INVALID") from exc
        if envelope.external_job_id is None and envelope.client_reference is None:
            raise ProviderError(422, "EVENT_CORRELATION_REQUIRED")
        integration_id = principal.provider_integration_id
        canonical = envelope.model_dump(mode="json")
        payload_hash = hashlib.sha256(
            json.dumps(canonical, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode(),
        ).hexdigest()
        async with self._uows() as uow:
            seen = (
                await uow.execute(
                    select(receipts).where(
                        receipts.c.integration_id == integration_id,
                        receipts.c.external_event_id == envelope.external_event_id,
                    ),
                )
            ).mappings().first()
        if seen is not None:
            if seen["payload_hash"] != payload_hash:
                raise ProviderError(409, "EVENT_ID_CONFLICT")
            return 202, self._accepted(seen, duplicate=True)
        async with self._uows() as uow:
            integration = (
                await uow.execute(select(integrations).where(integrations.c.integration_id == integration_id))
            ).mappings().first()
        if integration is None:
            raise ProviderError(403, "INTEGRATION_NOT_CONFIGURED")
        entry = check_event(integration["event_schema"], envelope.event_type, envelope.data)
        return 202, await self._apply(integration_id, envelope, entry, payload_hash)

    @staticmethod
    def _accepted(row: dict, duplicate: bool = False) -> dict:
        return {
            "receipt_id": row["receipt_id"],
            "ingestion_status": row["ingestion_status"],
            "duplicate": duplicate,
            "received_at": _iso(row["received_at"]),
            "status_url": f"/workforce/v1/provider/event-receipts/{row['receipt_id']}",
        }

    async def _operation(self, uow, integration_id: str, envelope: ProviderEventEnvelope) -> dict | None:
        clauses = []
        if envelope.client_reference is not None:
            clauses.append(operations.c.client_reference == envelope.client_reference)
        else:
            clauses.append(operations.c.external_job_id == envelope.external_job_id)
            clauses.append(operations.c.integration_id == integration_id)
        row = (await uow.execute(select(operations).where(*clauses).with_for_update())).mappings().first()
        if row is None:
            return None
        if row["integration_id"] not in (None, integration_id):
            raise ProviderError(403, "INTEGRATION_MISMATCH")
        if (
            envelope.external_job_id is not None
            and row["external_job_id"] is not None
            and row["external_job_id"] != envelope.external_job_id
        ):
            raise ProviderError(409, "CORRELATION_MISMATCH")
        return dict(row)

    async def _apply(self, integration_id, envelope, entry, payload_hash) -> dict:
        now = _now()
        receipt = {
            "receipt_id": "rcpt_" + self._ids(),
            "integration_id": integration_id,
            "external_event_id": envelope.external_event_id,
            "payload_hash": payload_hash,
            "ingestion_status": "applied",
            "normalized_status": entry.get("status"),
            "error_code": None,
            "operation_id": None,
            "received_at": now,
            "applied_at": now,
        }
        async with self._uows() as uow:
            operation = await self._operation(uow, integration_id, envelope)
            if operation is None:
                receipt.update(ingestion_status="quarantined", applied_at=None, error_code="OPERATION_NOT_FOUND")
                await uow.execute(insert(receipts).values(**receipt))
                await uow.commit()
                return self._accepted(receipt)
            receipt["operation_id"] = operation["operation_id"]
            rank = int(entry.get("rank") or 0)
            if operation["terminal"] or rank < operation["rank"]:
                receipt.update(ingestion_status="rejected", error_code="STALE_EVENT")
                await uow.execute(insert(receipts).values(**receipt))
                await uow.commit()
                return self._accepted(receipt)
            await uow.execute(
                update(operations)
                .where(operations.c.operation_id == operation["operation_id"])
                .values(
                    status=str(entry.get("status") or envelope.event_type)[:64],
                    rank=rank,
                    terminal=bool(entry.get("terminal")),
                    outcome=entry.get("outcome"),
                    external_job_id=operation["external_job_id"] or envelope.external_job_id,
                    integration_id=integration_id,
                    updated_at=now,
                ),
            )
            await uow.execute(insert(receipts).values(**receipt))
            await self._effects(uow, operation, envelope, entry, receipt["receipt_id"])
            await uow.commit()
        return self._accepted(receipt)

    async def _effects(self, uow, operation, envelope, entry, receipt_id) -> None:
        session = (
            await uow.execute(
                select(case_sessions).where(case_sessions.c.workflow_id == operation["workflow_id"]),
            )
        ).mappings().first()
        if session is None:
            return
        scope = Scope.model_validate(session["scope"])
        aggregate = parse_aggregate(
            await self._workflows.repository.load(scope, operation["workflow_id"], uow),
        )
        workflow = aggregate.workflow
        if workflow.state.value == "closed":
            return
        public = {
            key: value
            for key, value in envelope.data.items()
            if key in (entry.get("public_fields") or [])
        }
        await self._events.write(
            workflow,
            "operation.status_changed",
            {
                "operation_type": operation["tool_name"],
                "status_schema": "1",
                "status": str(entry.get("public_status") or entry.get("status") or envelope.event_type),
                "external_reference": operation["external_job_id"] or envelope.external_job_id,
            },
            uow,
            receipt_id,
        )
        if entry.get("message"):
            await self._events.write(
                workflow,
                "assistant.message",
                {"message_id": f"evt_{receipt_id}", "text": _render(entry["message"], public)},
                uow,
                receipt_id,
            )
        described = (
            f"Sự kiện {envelope.event_type} của {operation['tool_name']}"
            f" (trạng thái {entry.get('status')})"
            + (f": {json.dumps(public, ensure_ascii=False)}" if public else "")
        )
        if entry.get("wake") or entry.get("evidence"):
            await self._store.append(
                operation["workflow_id"],
                "event" if entry.get("wake") else "evidence",
                described,
                uow,
                pending=bool(entry.get("wake")),
            )
        if entry.get("wake"):
            # A wake is a platform-made request of the workflow's own end user:
            # the shared engine defers external-event causes while a workflow
            # waits for that user, and the leader must speak now.
            audience = workflow.audience
            actor = ActorContext(
                kind=ActorKind.PARTNER,
                actor_id=f"{audience.partner_client_id}:{audience.external_user_id}"[:200],
                partner_client_id=audience.partner_client_id,
                credential_id=receipt_id,
                credential_purpose=CredentialPurpose.CUSTOMER_API,
                external_user_id=audience.external_user_id,
                authentication_source="provider_event",
            )
            claim = await self._requests.claim_or_read(
                actor,
                f"provider-event-{receipt_id}",
                "provider_event",
                operation["workflow_id"],
                hashlib.sha256(receipt_id.encode()).hexdigest(),
                uow,
            )
            await self._workflows.enqueue_trigger(
                scope,
                {
                    "trigger_id": "evt-" + receipt_id,
                    "workflow_id": operation["workflow_id"],
                    "cause": {"kind": "request", "request_id": claim.request_id},
                },
                uow,
            )

    async def receipt(self, receipt_id: str, headers: dict) -> dict:
        """Contract 10.2: the provider key alone reads its receipts."""

        principal = await self._api_principal(headers)
        async with self._uows() as uow:
            row = (
                await uow.execute(select(receipts).where(receipts.c.receipt_id == receipt_id))
            ).mappings().first()
        if row is None or row["integration_id"] not in principal:
            raise ProviderError(404, "RESOURCE_NOT_FOUND")
        return {
            "receipt_id": row["receipt_id"],
            "external_event_id": row["external_event_id"],
            "ingestion_status": row["ingestion_status"],
            "normalized_status": row["normalized_status"],
            "received_at": _iso(row["received_at"]),
            "applied_at": _iso(row["applied_at"]),
            "error": {"code": row["error_code"]} if row["error_code"] else None,
        }

    async def _api_principal(self, headers: dict) -> set[str]:
        """Integrations whose provider credential uses this API key."""

        from ...foundation._tables import provider_credentials

        if self._auth is None:
            raise ProviderError(503, "PROVIDER_EVENTS_DISABLED")
        authorization = {k.lower(): v for k, v in headers.items()}.get("authorization", "")
        scheme, _, key = authorization.partition(" ")
        if scheme.lower() != "apikey" or not key:
            raise ProviderError(401, "PROVIDER_AUTH_FAILED")
        try:
            principal = await self._auth._authenticate_api_key(key.strip())  # pylint: disable=protected-access
        except Exception as exc:
            raise ProviderError(401, "PROVIDER_AUTH_FAILED") from exc
        async with self._uows() as uow:
            rows = (
                await uow.execute(
                    select(provider_credentials.c.provider_integration_id).where(
                        provider_credentials.c.api_credential_id == principal.key_id,
                        provider_credentials.c.status == "active",
                    ),
                )
            ).all()
        return {row[0] for row in rows}


__all__ = ["ProviderError", "UnifiedProviderEvents", "check_event"]
