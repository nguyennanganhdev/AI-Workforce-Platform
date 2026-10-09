"""Signed, deduplicated provider inbox. External progress is data, never instructions."""
import hashlib
import hmac
import time
from datetime import datetime

from sqlalchemy import insert, select, update

from . import schema as s
from .service import Fault, digest, row, stamp, uid


async def ingest(service, client, body, raw, headers):
    settings = client["settings"]
    timestamp = headers.get("x-partner-timestamp", "")
    try:
        if abs(time.time() - int(timestamp)) > 300:
            raise ValueError()
    except ValueError:
        raise Fault(401, "INVALID_SIGNATURE_TIMESTAMP")
    if headers.get("x-partner-key-id") != settings.get("signing_key_id"):
        raise Fault(401, "INVALID_SIGNATURE_KEY")
    secret = service.cipher().decrypt(settings["encrypted_signing_secret"].encode())
    expected = "v1=" + hmac.new(secret, timestamp.encode() + b"." + raw, hashlib.sha256).hexdigest()
    if not hmac.compare_digest(expected, headers.get("x-partner-signature", "")):
        raise Fault(401, "INVALID_SIGNATURE")
    mapping = settings.get("event_map", {}).get(body.event_type)
    if not mapping:
        raise Fault(422, "UNKNOWN_EVENT_TYPE")
    from jsonschema import ValidationError, validate
    try:
        validate(body.data, mapping.get("schema", {"type": "object", "additionalProperties": False}))
    except ValidationError:
        raise Fault(422, "INVALID_EVENT_DATA")
    payload = body.model_dump(mode="json")
    async with service.tx() as conn:
        await row(conn, s.clients, s.clients.c.id == client["id"], lock=True)
        prior = await row(conn, s.receipts, s.receipts.c.integration_id == client["id"],
                          s.receipts.c.external_id == body.external_event_id)
        if prior:
            if prior["payload_hash"] != digest(payload):
                raise Fault(409, "EVENT_ID_CONFLICT")
            return {"receipt_id": prior["id"], "ingestion_status": prior["status"], "duplicate": True,
                    "received_at": stamp(prior["received"]),
                    "status_url": f"/workforce/v1/provider/event-receipts/{prior['id']}"}
        receipt_id = uid()
        await conn.execute(insert(s.receipts).values(id=receipt_id, integration_id=client["id"],
            external_id=body.external_event_id, payload_hash=digest(payload), status="accepted",
            body=payload, policy={"event_map": settings.get("event_map", {}), "transitions": settings.get("transitions", {})},
            received=time.time(), applied=None, error=None))
        await conn.execute(insert(s.jobs).values(id=uid(), workflow_id="provider:" + client["id"], request_id=receipt_id,
            kind="provider", status="queued", payload={"receipt_id": receipt_id}, lease_until=0,
            generation=0, attempts=0, available=time.time()))
    return {"receipt_id": receipt_id, "ingestion_status": "accepted", "duplicate": False,
            "received_at": stamp(time.time()), "status_url": f"/workforce/v1/provider/event-receipts/{receipt_id}"}


async def apply(service, receipt_id):
    async with service.tx() as conn:
        receipt = await row(conn, s.receipts, s.receipts.c.id == receipt_id, lock=True)
        if not receipt or receipt["status"] in ("applied", "rejected", "duplicate"):
            return True
        client = await row(conn, s.clients, s.clients.c.id == receipt["integration_id"])
        if not client or client["status"] != "active" or (client["expires"] and client["expires"] <= time.time()):
            await conn.execute(update(s.receipts).where(s.receipts.c.id == receipt_id).values(status="rejected"))
            return True
        body = receipt["body"]
        matches = []
        for key in ("external_job_id", "client_reference"):
            if body.get(key):
                found = await row(conn, s.operations, s.operations.c.integration_id == client["id"],
                                   getattr(s.operations.c, key) == body[key])
                if found:
                    matches.append(found)
        if not matches:
            await conn.execute(update(s.receipts).where(s.receipts.c.id == receipt_id).values(status="quarantined"))
            return False
        if len({x["id"] for x in matches}) > 1 or (body.get("external_job_id") and matches[0]["external_job_id"]
                and matches[0]["external_job_id"] != body["external_job_id"]) or (
                body.get("client_reference") and matches[0]["client_reference"] != body["client_reference"]):
            await conn.execute(update(s.receipts).where(s.receipts.c.id == receipt_id).values(
                status="rejected", error={"code": "CORRELATION_CONFLICT"}))
            return True
        op = matches[0]
        wf = await row(conn, s.workflows, s.workflows.c.id == op["workflow_id"], lock=True)
        op = await row(conn, s.operations, s.operations.c.id == op["id"], lock=True)
        if op["status"] in ("awaiting_approval", "queued", "started"):
            # Keep early progress until the external-call outcome has been persisted.
            await conn.execute(update(s.receipts).where(s.receipts.c.id == receipt_id).values(status="quarantined"))
            return False
        settings = receipt["policy"]
        mapping = settings["event_map"][body["event_type"]]
        version = body.get("provider_version")
        state = mapping["status"]
        prior_hash = op["data"].get("last_event_hash")
        event_hash = digest({"event_type": body["event_type"], "data": body["data"]})
        error, receipt_state = None, "applied"
        if version and version == op["provider_version"] and prior_hash and prior_hash != event_hash:
            error, receipt_state = {"code": "PROVIDER_VERSION_CONFLICT"}, "needs_attention"
        elif version and version <= op["provider_version"]:
            receipt_state = "duplicate"
        elif version and mapping.get("mode", "snapshot") == "delta" and version != op["provider_version"] + 1:
            await conn.execute(update(s.receipts).where(s.receipts.c.id == receipt_id).values(status="quarantined"))
            return False
        elif state not in settings.get("transitions", {}).get(op["status"], []):
            error, receipt_state = {"code": "INVALID_OPERATION_TRANSITION"}, "needs_attention"
        if receipt_state == "applied":
            data = {**op["data"], "last_event_hash": event_hash, "last_event_id": receipt["external_id"],
                    "provider_data": body["data"]}
            await conn.execute(update(s.operations).where(s.operations.c.id == op["id"]).values(
                status=state, provider_version=version or op["provider_version"], data=data,
                external_job_id=op["external_job_id"] or body.get("external_job_id")))
            op.update(status=state, data=data)
            if wf["state"] != "closed":
                public = {k: body["data"][k] for k in mapping.get("public_fields", []) if k in body["data"]}
                await service.event(conn, wf, "operation.status_changed", {"operation_id": op["id"], "status": state, **public},
                                    datetime.fromisoformat(body["occurred_at"]).timestamp())
                if state in ("completed", "confirmed"):
                    other = (await conn.execute(select(s.operations.c.id).where(s.operations.c.workflow_id == wf["id"],
                        s.operations.c.id != op["id"], s.operations.c.status.not_in(["completed", "confirmed", "cancelled", "failed", "rejected"])))).first()
                    if not other:
                        from .lifecycle import resume_after_operation
                        if await resume_after_operation(service, conn, wf, op):
                            await conn.execute(update(s.receipts).where(s.receipts.c.id == receipt_id).values(
                                status=receipt_state, applied=time.time(), error=error))
                            return True
                        await service.transition(conn, wf, "awaiting_confirmation")
                        await service.event(conn, wf, "assistant.message", {"message_id": uid(), "workflow_id": wf["id"],
                            "sender": "assistant", "text": "Công việc đã được hệ thống nghiệp vụ báo hoàn thành. Bạn xác nhận kết quả giúp tôi.",
                            "created_at": stamp(time.time())})
                elif state in ("failed", "cancelled"):
                    await service.transition(conn, wf, "needs_attention")
        await conn.execute(update(s.receipts).where(s.receipts.c.id == receipt_id).values(
            status=receipt_state, applied=time.time(), error=error))
        if error and wf["state"] != "closed":
            await service.transition(conn, wf, "needs_attention")
            await service.event(conn, wf, "workflow.needs_attention", {"reason": error["code"], "revision": wf["revision"]})
        return True
