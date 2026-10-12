"""The Provider Event API (contract 10): a provider's backend tells the platform how an operation is going.

POST stores the event and answers 202; the platform applies it afterwards (provider_apply.py, provider_sweep.py). Who may send:

  * an ApiKey of kind provider with `publish_job_event` (the integration it belongs to), AND
  * a signature of the raw body made with a signing key of THE SAME integration (contract 5.2).

Replays: a captured request replayed inside the clock window is the same event id with the same body, so it is the
duplicate path (the receipt it already has, nothing applied again); outside the window it is refused. Timestamp and event id
together are the protection; there is no nonce store.
"""
from __future__ import annotations

import hashlib
import hmac
import json
import re
from typing import Any

from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse
from sqlalchemy import func, insert, select
from sqlalchemy.exc import IntegrityError

from . import crypto, provider_sweep, tables as t
from .auth import PartnerPrincipal, authenticate
from .common import iso, now
from .errors import WorkforceError, failed, invalid, json_object, unauthenticated, validated
from .provider_match import find
from .provider_schema import data_errors, rule_of
from .reads import not_found
from .schemas import MAX_EVENT_DATA, ProviderEventIn
from .tables import new_id

BASE = "/workforce/v1/provider/event-receipts"
_STAMP = re.compile(r"^\d{1,12}$")
_SIGNATURE = re.compile(r"^v1=([0-9a-f]{64})$")
ATTEMPTS = 3


def status_url(receipt_id: str) -> str:
    return f"{BASE}/{receipt_id}"


async def verify_signature(ctx, request: Request, p: PartnerPrincipal, raw: bytes) -> None:
    """HMAC-SHA256 over `<timestamp>.<raw body>` with a signing key of the caller's integration, compared in constant
    time; the same refusal for every way the signature can be wrong, so the answer teaches nothing about which keys exist."""
    h = request.headers
    stamp, key_id, signature = h.get("x-partner-timestamp", ""), h.get("x-partner-key-id", ""), h.get("x-partner-signature", "")
    if not (stamp and key_id and signature):
        raise unauthenticated("signature_missing")
    wanted = _SIGNATURE.match(signature)
    if not _STAMP.match(stamp):
        raise unauthenticated("signature_invalid")
    if abs(now() - int(stamp)) > ctx.settings.wf_provider_skew_seconds:
        raise unauthenticated("timestamp_out_of_range")
    async with ctx.db.engine.connect() as conn:
        key = (await conn.execute(select(t.signing_keys).where(
            t.signing_keys.c.key_id == key_id, t.signing_keys.c.integration_id == p.integration_id,
            t.signing_keys.c.status == "active"))).mappings().first()
    try:
        secret = ctx.sealer.open(key["secret_enc"]) if key else "no-such-signing-key"
    except crypto.SecretKeyMissing:
        raise WorkforceError("INTERNAL_ERROR", 503, "Signatures cannot be checked right now; retry.", retryable=True)
    expect = hmac.new(secret.encode(), stamp.encode() + b"." + raw, hashlib.sha256).hexdigest()
    if not (hmac.compare_digest(expect, wanted.group(1) if wanted else "0" * 64) and key and wanted):
        raise unauthenticated("signature_invalid")


def receipt_body(row: Any, duplicate: bool) -> dict:
    return {"receipt_id": row["receipt_id"], "ingestion_status": row["ingestion_status"], "duplicate": duplicate,
            "received_at": iso(row["received_at"]), "status_url": status_url(row["receipt_id"])}


def fingerprint(data: dict) -> str:
    return "sha256:" + hashlib.sha256(json.dumps(data, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode()).hexdigest()


async def _store(ctx, p: PartnerPrincipal, integ: Any, data: dict, ev: ProviderEventIn, sig_key_id: str) -> tuple[Any, bool]:
    """One transaction: the event dedupe and the inbox row (the row is also the queue the applier reads)."""
    async with ctx.db.engine.begin() as conn:
        found = (await conn.execute(select(t.provider_inbox).where(
            t.provider_inbox.c.integration_id == integ["id"],
            t.provider_inbox.c.external_event_id == ev.external_event_id))).mappings().first()
        digest = fingerprint(data)
        if found is not None:
            if found["payload_hash"] != digest:
                raise WorkforceError("EVENT_ID_CONFLICT", 409, "This external_event_id was used with different content.")
            return found, True
        match = await find(conn, integ["client_id"], integ["id"], ev.client_reference, ev.external_job_id, p.routes)
        if match.mismatch:
            raise WorkforceError("JOB_CORRELATION_MISMATCH", 409,
                                 "external_job_id and client_reference point at different operations.")
        if match.op is None:  # it will wait: one integration may not fill the waiting room for the others (contract 6.2: 429)
            waiting = (await conn.execute(select(func.count()).select_from(t.provider_inbox).where(
                t.provider_inbox.c.integration_id == integ["id"],
                t.provider_inbox.c.ingestion_status == "quarantined"))).scalar_one()
            if waiting >= ctx.settings.wf_quarantine_max:
                raise WorkforceError("RATE_LIMITED", 429, "Too many events of this integration wait for an operation they "
                                     "do not match yet; retry later.", retryable=True, headers={"Retry-After": "60"})
        stamp = now()
        row = dict(receipt_id=new_id("rcpt"), integration_id=integ["id"], external_event_id=ev.external_event_id,
                   key_id=p.key_id, sig_key_id=sig_key_id, payload_hash=digest, event_type=ev.event_type, payload=data,
                   operation_id=match.op["id"] if match.op else None,
                   workflow_id=match.op["workflow_id"] if match.op else None,
                   ingestion_status="accepted" if match.op else "quarantined",
                   normalized_status=(integ["event_schema"]["events"][ev.event_type]["status"]),
                   provider_version=str(ev.provider_version) if ev.provider_version is not None else None,
                   received_at=stamp)
        await conn.execute(insert(t.provider_inbox).values(**row))
        return row, False


def build_provider(r: APIRouter, ctx: Any) -> None:
    @r.post("/provider/job-events")
    async def publish(request: Request):
        p = await authenticate(request, "provider", "publish_job_event")
        await verify_signature(ctx, request, p, await request.body())
        data = await json_object(request)
        try:  # text that cannot be written as UTF-8 (a lone surrogate escape) is not valid JSON text, and is not stored
            json.dumps(data, ensure_ascii=False).encode()
            size = len(json.dumps(data.get("data"), ensure_ascii=False).encode())
        except UnicodeEncodeError:
            raise invalid("Body is not valid UTF-8 JSON.")
        if size > MAX_EVENT_DATA:
            raise WorkforceError("PAYLOAD_TOO_LARGE", 413, "data is larger than 64 KiB.", {"limit_bytes": MAX_EVENT_DATA})
        ev = validated(data, ProviderEventIn)
        async with ctx.db.engine.connect() as conn:
            integ = (await conn.execute(select(t.integrations).where(t.integrations.c.id == p.integration_id))).mappings().one()
        rule = rule_of(integ["event_schema"], ev.event_type)
        if rule is None:
            raise WorkforceError("UNKNOWN_EVENT_TYPE", 422, "The event type is not in this integration's event schema.",
                                 {"event_type": ev.event_type})
        wrong = data_errors(rule, ev.data)
        if wrong:
            raise failed("data does not fit the event schema.", wrong)
        for attempt in range(ATTEMPTS):
            try:
                row, duplicate = await _store(ctx, p, integ, data, ev, request.headers.get("x-partner-key-id", ""))
                break
            except IntegrityError:  # the same event arrived twice at once: the winner's row is the answer
                if attempt == ATTEMPTS - 1:
                    raise
        if not duplicate and row["ingestion_status"] == "accepted":
            provider_sweep.schedule(ctx, row["receipt_id"])
        return JSONResponse(receipt_body(row, duplicate), status_code=202)

    @r.get("/provider/event-receipts/{receipt_id}")
    async def receipt(receipt_id: str, request: Request):
        p = await authenticate(request, "provider", "read_event_receipt")
        async with ctx.db.engine.connect() as conn:
            row = (await conn.execute(select(t.provider_inbox).where(
                t.provider_inbox.c.receipt_id == receipt_id,
                t.provider_inbox.c.integration_id == p.integration_id))).mappings().first()
        if row is None:  # another integration's receipt answers like one that never existed
            raise not_found()
        return {"receipt_id": row["receipt_id"], "external_event_id": row["external_event_id"],
                "ingestion_status": row["ingestion_status"], "normalized_status": row["normalized_status"],
                "received_at": iso(row["received_at"]), "applied_at": iso(row["applied_at"]), "error": row["error"],
                "note": row["note"]}
