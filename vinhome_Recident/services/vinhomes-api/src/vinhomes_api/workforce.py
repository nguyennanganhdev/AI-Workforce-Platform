"""Durable Reception -> Workforce adapter; HTTP never runs inside the resident transaction."""
import asyncio
import hashlib
import hmac
import json
import logging
import time
from contextlib import asynccontextmanager
from uuid import UUID, uuid4

import httpx
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import text

from .resident_api import Resident
from .resident_contract import BASE, TENANT
from .workforce_config import WorkforceConfig, enabled

log = logging.getLogger(__name__)
router = APIRouter(prefix=BASE + "/workforce", tags=["Resident Workforce"])


def fingerprint(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False, default=str).encode()).hexdigest()


@asynccontextmanager
async def transaction(engine, tenant):
    async with engine.begin() as db:
        await db.execute(text("select set_config('app.tenant_id',:tenant,true)"), {"tenant": str(tenant)})
        yield db


async def enqueue_reception(body, scope, payload_hash):
    from .v3_reception_supervisor import _resident_ticket_snapshot
    config = WorkforceConfig.from_env()
    db, actor = scope
    old = (await db.execute(text(f"select * from vh_workforce_outbox where tenant_id={TENANT} and external_id=:id"),
                            {"id": body.message_id})).mappings().first()
    if old:
        source = old["source"]
        if old["payload_hash"] != payload_hash or source.get("actor") != actor or source.get("ticket_id") != str(body.ticket_id):
            raise HTTPException(409, "Workforce message ID already belongs to another command")
        return {"message": source["message"], "replayed": True, "business_effect": {"workforce_queued": True}}
    ticket = await _resident_ticket_snapshot(scope, body)
    team = (await db.execute(text(f"select client_id from integration_cases where tenant_id={TENANT} and id=:id"),
                             {"id": body.team_id})).scalar_one()
    if team != config.integration_client_id:
        raise HTTPException(409, "Team belongs to another supervisor integration; explicit migration is required")
    if body.message_type in {"plan_approved", "plan_rejected", "plan_change_requested"}:
        raise HTTPException(409, "Use the authenticated Vinhomes plan decision API; chat text cannot approve a business plan or Workforce operation")
    if len(body.file_ids) > 8:
        raise HTTPException(422, "Workforce accepts at most eight images in one turn")
    binding = (await db.execute(text(f"select * from vh_workforce_bindings where tenant_id={TENANT} "
        "and ticket_id=:ticket and generation=:generation for update"),
        {"ticket": body.ticket_id, "generation": body.ticket_generation})).mappings().first()
    if not binding:
        if body.message_type != "ticket_submitted":
            raise HTTPException(409, "No Workforce binding exists for this ticket generation")
        binding = (await db.execute(text(f"""insert into vh_workforce_bindings
            (tenant_id,ticket_id,generation,resident_id,team_id,channel_id,management_ref,residence_id,
             external_ticket_id,external_conversation_id)
            values({TENANT},:ticket,:generation,:resident,:team,:channel,:management,:residence,:external_ticket,:chat)
            returning *"""), {"ticket": body.ticket_id, "generation": body.ticket_generation, "resident": actor,
            "team": body.team_id, "channel": ticket["channel_id"], "management": str(ticket["management_unit_id"]),
            "residence": str(ticket["unit_id"]), "external_ticket": f"{body.ticket_id}:g{body.ticket_generation}",
            "chat": f"{ticket['channel_id']}:{body.ticket_id}:g{body.ticket_generation}"})).mappings().one()
    elif body.message_type == "ticket_submitted":
        raise HTTPException(409, "This ticket generation is already bound to Workforce")
    if binding["resident_id"] != actor or binding["team_id"] != body.team_id or binding["state"] == "closed":
        raise HTTPException(409, "Workforce binding mismatch or tracking closed")
    source = {"actor": actor, "ticket_id": str(body.ticket_id), "message": body.model_dump(mode="json", exclude_unset=True)}
    await db.execute(text(f"""insert into vh_workforce_outbox
        (tenant_id,binding_id,kind,external_id,payload_hash,source) values
        ({TENANT},:binding,'request',:id,:hash,cast(:source as jsonb))"""),
        {"binding": binding["id"], "id": body.message_id, "hash": payload_hash, "source": json.dumps(source)})
    return {"message": source["message"], "replayed": False, "business_effect": {"workforce_queued": True}}


async def owned(db, actor, ticket_id):
    result = (await db.execute(text(f"""select b.* from vh_workforce_bindings b join tickets t
        on t.id=b.ticket_id and t.tenant_id=b.tenant_id and t.reopen_count=b.generation
        where b.tenant_id={TENANT} and b.ticket_id=:ticket and b.resident_id=:actor and t.requester_user_id=:actor
          and t.unit_id::text=b.residence_id and t.management_unit_id::text=b.management_ref
          and exists(select 1 from unit_residents ur where ur.tenant_id=t.tenant_id and ur.unit_id=t.unit_id
            and ur.user_id=:actor and ur.verification_status='verified' and ur.valid_from<=now()
            and (ur.valid_to is null or ur.valid_to>now())) for update of b"""),
        {"ticket": ticket_id, "actor": actor})).mappings().first()
    if not result:
        raise HTTPException(404, "Resident Workforce ticket not found")
    return dict(result)


@router.get("/tickets/{ticket_id}")
async def resident_snapshot(ticket_id: UUID, scope: Resident):
    if not enabled():
        raise HTTPException(404, "Workforce integration is disabled")
    binding = await owned(*scope, ticket_id)
    return {"ticket_id": str(ticket_id), "workflow_id": binding["workflow_id"], "state": binding["state"],
            "snapshot": binding["snapshot"], "attention": binding["last_error"]}


class Control(BaseModel):
    model_config = ConfigDict(extra="forbid")
    external_request_id: str = Field(min_length=1, max_length=200)
    expected_revision: int = Field(ge=1)


class Approval(Control):
    decision: str = Field(pattern="^(approve|reject)$")
    arguments_hash: str = Field(min_length=1, max_length=200)
    quote_ref: str = Field(min_length=1, max_length=200)


class Close(Control):
    reason: str = Field(min_length=1, max_length=200)
    stop_tracking_only: bool = False


async def enqueue_control(scope, ticket_id, body, kind, approval_id=None):
    if not enabled():
        raise HTTPException(404, "Workforce integration is disabled")
    db, actor = scope
    await db.execute(text("select pg_advisory_xact_lock(hashtextextended(:key,0))"),
                     {"key": "workforce-control:" + body.external_request_id})
    binding = await owned(db, actor, ticket_id)
    if not binding["workflow_id"]:
        raise HTTPException(409, "Workflow is not bound yet")
    data = {**body.model_dump(), "external_user_id": actor, "external_ticket_id": binding["external_ticket_id"],
        "external_conversation_id": binding["external_conversation_id"]}
    if kind == "approval":
        data["workflow_id"] = binding["workflow_id"]
        endpoint = f"/workforce/v1/partner/approvals/{approval_id}/decision"
    else:
        endpoint = f"/workforce/v1/partner/workflows/{binding['workflow_id']}/close"
    checksum = fingerprint({"endpoint": endpoint, "body": data})
    old = (await db.execute(text(f"select payload_hash from vh_workforce_outbox where tenant_id={TENANT} and external_id=:id"),
                            {"id": body.external_request_id})).scalar()
    if old:
        if old != checksum:
            raise HTTPException(409, "Command ID conflict")
        return {"queued": True, "replayed": True}
    await db.execute(text(f"""insert into vh_workforce_outbox(tenant_id,binding_id,kind,external_id,payload_hash,body,endpoint)
        values({TENANT},:binding,:kind,:id,:hash,cast(:body as jsonb),:endpoint)"""),
        {"binding": binding["id"], "kind": kind, "id": body.external_request_id, "hash": checksum,
         "body": json.dumps(data), "endpoint": endpoint})
    return {"queued": True, "replayed": False}


@router.post("/tickets/{ticket_id}/approvals/{approval_id}/decision", status_code=202)
async def approval(ticket_id: UUID, approval_id: UUID, body: Approval, scope: Resident):
    return await enqueue_control(scope, ticket_id, body, "approval", str(approval_id))


@router.post("/tickets/{ticket_id}/close", status_code=202)
async def close(ticket_id: UUID, body: Close, scope: Resident):
    return await enqueue_control(scope, ticket_id, body, "close")


class PartnerRejected(Exception):
    def __init__(self, code):
        self.code = code


class WorkforceClient:
    def __init__(self, config, transport=None):
        self.config = config
        self.http = httpx.AsyncClient(base_url=config.url.rstrip("/"), timeout=35, transport=transport)

    async def call(self, method, path, body=None, provider=False, params=None):
        key = self.config.provider_key if provider else self.config.customer_key
        headers = {"Authorization": "ApiKey " + key}
        raw = json.dumps(body, ensure_ascii=False, separators=(",", ":")).encode() if body is not None else None
        if raw is not None:
            headers["Content-Type"] = "application/json"
        if provider and raw is not None:
            timestamp = str(int(time.time()))
            signature = hmac.new(self.config.signing_secret.encode(), timestamp.encode() + b"." + raw, hashlib.sha256).hexdigest()
            headers.update({"X-Partner-Timestamp": timestamp, "X-Partner-Key-Id": self.config.signing_key_id,
                            "X-Partner-Signature": "v1=" + signature})
        response = await self.http.request(method, path, content=raw, headers=headers, params=params)
        if response.status_code in (429, 502, 503, 504):
            raise httpx.TransportError("Partner temporarily unavailable")
        if response.is_error:
            try:
                code = response.json().get("error", {}).get("code", "PARTNER_REJECTED")
            except ValueError:
                code = "PARTNER_REJECTED"
            raise PartnerRejected(code)
        return response.json()


async def prepare_request(db, binding, outbox):
    source = outbox["source"]["message"]
    command = "start_workflow" if source["message_type"] == "ticket_submitted" else "workflow_reply"
    if command == "workflow_reply" and not binding["workflow_id"]:
        raise httpx.TransportError("Waiting for initial workflow binding")
    return {"command_type": command, "external_request_id": outbox["external_id"],
        "external_management_ref": binding["management_ref"], "external_user_id": binding["resident_id"],
        "external_ticket_id": binding["external_ticket_id"], "external_conversation_id": binding["external_conversation_id"],
        "residence_id": binding["residence_id"], "timezone": "Asia/Ho_Chi_Minh",
        **({"workflow_id": binding["workflow_id"]} if command == "workflow_reply" else {}),
        "message": {"text": source["message_type"] + ": " + source["message"], "asset_ids": []}}


async def transfer_assets(engine, tenant, client, binding, source):
    from . import storage
    from .v3_files import FILE_ROOT
    ids = []
    for file_id in source.get("file_ids", []):
        async with transaction(engine, tenant) as db:
            prior = (await db.execute(text(f"select asset_id from vh_workforce_assets where tenant_id={TENANT} and binding_id=:binding and file_id=cast(:file as uuid)"),
                {"binding": binding["id"], "file": file_id})).scalar()
            if prior:
                ids.append(prior)
                continue
            file = (await db.execute(text(f"""select o.object_key,o.sha256,o.mime_type,o.size_bytes
                from files f join file_objects o on o.id=f.accepted_object_id and o.tenant_id=f.tenant_id
                join storage_locations l on l.id=o.location_id and l.tenant_id=o.tenant_id
                where f.tenant_id={TENANT} and f.id=cast(:file as uuid) and f.status='ready' and f.deleted_at is null
                  and o.status='ready' and o.scan_status='clean' and o.verified_at is not null and l.provider=:provider
                  and ((f.channel_id=:channel and f.uploaded_by=:resident) or exists(select 1 from ticket_files tf
                    where tf.tenant_id=f.tenant_id and tf.file_id=f.id and tf.ticket_id=:ticket))"""),
                {"file": file_id, "channel": binding["channel_id"], "resident": binding["resident_id"],
                 "ticket": binding["ticket_id"], "provider": storage.provider()})).mappings().first()
        if not file or file["mime_type"] not in {"image/jpeg", "image/png", "image/webp"} or file["size_bytes"] > 10485760:
            raise PartnerRejected("SOURCE_IMAGE_NOT_AUTHORIZED")
        def read_image(object_key):
            # Bound reads even if the stored object changes after verification.
            if storage.provider() == "s3":
                response = storage.client().get_object(storage.bucket(), object_key)
                try:
                    return response.read(10485761)
                finally:
                    response.close()
                    response.release_conn()
            with storage.at(FILE_ROOT, object_key).open("rb") as handle:
                return handle.read(10485761)
        raw = await asyncio.to_thread(read_image, file["object_key"])
        if len(raw) != file["size_bytes"] or hashlib.sha256(raw).hexdigest() != file["sha256"]:
            raise PartnerRejected("SOURCE_IMAGE_CHECKSUM_MISMATCH")
        upload = await client.call("POST", "/workforce/v1/partner/assets/uploads", {
            "external_management_ref": binding["management_ref"], "external_user_id": binding["resident_id"],
            "external_ticket_id": binding["external_ticket_id"], "external_conversation_id": binding["external_conversation_id"],
            "content_type": file["mime_type"], "size": len(raw), "sha256": file["sha256"]})
        # Destination is the configured platform's upload service; no URL comes from model/user text.
        if upload["status"] != "ready":
            response = await client.http.post(upload["upload_url"], data=upload["fields"],
                                              files={"file": ("image", raw, file["mime_type"])})
            response.raise_for_status()
            await client.call("POST", f"/workforce/v1/partner/assets/{upload['asset_id']}/complete",
                              params={"external_user_id": binding["resident_id"]})
        async with transaction(engine, tenant) as db:
            await db.execute(text(f"""insert into vh_workforce_assets(tenant_id,binding_id,file_id,asset_id)
                values({TENANT},:binding,cast(:file as uuid),:asset) on conflict do nothing"""),
                {"binding": binding["id"], "file": file_id, "asset": upload["asset_id"]})
        ids.append(upload["asset_id"])
    return ids


async def deliver(db, binding, item):
    payload = item["payload"]
    event_id = "message:" + payload["message_id"] if item["event_type"] == "assistant.message" else item["event_id"]
    accepted = (await db.execute(text(f"""insert into vh_workforce_deliveries(tenant_id,binding_id,event_id,event_sequence,payload)
        values({TENANT},:binding,:id,:sequence,cast(:payload as jsonb)) on conflict do nothing returning event_id"""),
        {"binding": binding["id"], "id": event_id, "sequence": item.get("sequence", 0), "payload": json.dumps(item)})).first()
    if accepted and item["event_type"] == "assistant.message":
        from .v3_reception_runtime import append_agent_message
        await append_agent_message(db, binding["channel_id"], WorkforceConfig.from_env().integration_client_id, "customer",
            {"text": payload["text"], "workforce": {"workflow_id": binding["workflow_id"],
             "ticket_id": str(binding["ticket_id"]), "event_id": item["event_id"], "source": "platform_supervisor"}})


async def poll_binding(engine, tenant, client, binding):
    async with transaction(engine, tenant) as db:
        binding = await owned(db, binding["resident_id"], binding["ticket_id"])
    params = {"external_user_id": binding["resident_id"]}
    path = "/workforce/v1/partner/conversations/" + binding["conversation_id"]
    try:
        page = await client.call("GET", path + "/event-history", params={**params, "after_cursor": binding["cursor"]} if binding["cursor"] else params)
    except PartnerRejected as exc:
        if exc.code != "EVENT_CURSOR_EXPIRED":
            raise
        page = None
    snapshot = await client.call("GET", path, params=params)
    async with transaction(engine, tenant) as db:
        current = (await db.execute(text(f"select cursor,state from vh_workforce_bindings where tenant_id={TENANT} and id=:id for update"), {"id": binding["id"]})).mappings().one()
        if current["cursor"] != binding["cursor"] or current["state"] == "closed":
            return  # Another poller has already advanced this page.
        for item in (page["items"] if page else []):
            await deliver(db, binding, item)
        if page is None:
            if snapshot.get("messages_truncated"):
                raise PartnerRejected("SNAPSHOT_HISTORY_TRUNCATED")
            for msg in snapshot["messages"]:
                await deliver(db, binding, {"event_type": "assistant.message", "payload": msg, "event_id": "snapshot:" + msg["message_id"]})
        flow = next((x for x in snapshot["workflows"] if x["workflow_id"] == binding["workflow_id"]), None)
        if not flow:
            raise PartnerRejected("WORKFLOW_BINDING_MISMATCH")
        await db.execute(text(f"""update vh_workforce_bindings set state=:state,snapshot=cast(:snapshot as jsonb),
            cursor=:cursor,next_poll=now()+interval '2 seconds',updated_at=now(),last_error=null where tenant_id={TENANT} and id=:id"""),
            {"state": flow["state"], "snapshot": json.dumps(snapshot), "cursor": page["next_cursor"] if page else snapshot["snapshot_cursor"], "id": binding["id"]})


async def process_one(engine, tenant, client, owner):
    async with transaction(engine, tenant) as db:
        task = (await db.execute(text(f"""select o.* from vh_workforce_outbox o
            where o.tenant_id={TENANT} and o.status in ('queued','leased') and o.available<=now()
              and (o.lease_until is null or o.lease_until<now())
              and not exists(select 1 from vh_workforce_outbox earlier where earlier.tenant_id=o.tenant_id
                and earlier.binding_id=o.binding_id and earlier.id!=o.id and earlier.status in ('queued','leased')
                and (earlier.created_at,earlier.id)<(o.created_at,o.id))
            order by o.created_at,o.id limit 1 for update of o skip locked"""))).mappings().first()
        if not task:
            return False
        task = dict(task)
        task["generation"] += 1
        await db.execute(text(f"update vh_workforce_outbox set status='leased',owner=:owner,generation=:generation,lease_until=now()+interval '120 seconds',attempts=attempts+1 where tenant_id={TENANT} and id=:id"),
                         {"owner": owner, "generation": task["generation"], "id": task["id"]})
        binding = (await db.execute(text(f"select * from vh_workforce_bindings where tenant_id={TENANT} and id=:id"), {"id": task["binding_id"]})).mappings().first() if task["binding_id"] else None
        body = task["body"]
    async def heartbeat():
        while True:
            await asyncio.sleep(20)
            async with transaction(engine, tenant) as db:
                result = await db.execute(text(f"""update vh_workforce_outbox set lease_until=now()+interval '120 seconds'
                    where tenant_id={TENANT} and id=:id and owner=:owner and generation=:generation
                    and status='leased' and lease_until>now()"""),
                    {"id": task["id"], "owner": owner, "generation": task["generation"]})
                if not result.rowcount:
                    return
    beat = asyncio.create_task(heartbeat())
    try:
        if binding:
            async with transaction(engine, tenant) as db:
                current = await owned(db, binding["resident_id"], binding["ticket_id"])
                if (current["management_ref"], current["residence_id"], current["generation"]) != (binding["management_ref"], binding["residence_id"], binding["generation"]):
                    raise PartnerRejected("DOMAIN_BINDING_CHANGED")
                if task["kind"] == "request" and not body:
                    body = await prepare_request(db, binding, task)
        if task["kind"] == "request" and not task["body"]:
            await client.call("PUT", "/workforce/v1/partner/residences/" + binding["residence_id"],
                {"external_user_id": binding["resident_id"], "external_management_ref": binding["management_ref"], "status": "active", "expected_revision": 0})
            body["message"]["asset_ids"] = await transfer_assets(engine, tenant, client, binding, task["source"]["message"])
            async with transaction(engine, tenant) as db:
                await db.execute(text(f"update vh_workforce_outbox set body=cast(:body as jsonb) where tenant_id={TENANT} and id=:id and owner=:owner and generation=:generation"),
                    {"body": json.dumps(body), "id": task["id"], "owner": owner, "generation": task["generation"]})
        endpoint = task["endpoint"] or ("/workforce/v1/provider/job-events" if task["kind"] == "provider" else "/workforce/v1/partner/requests")
        response = await client.call("POST", endpoint, body, provider=task["kind"] == "provider")
        async with transaction(engine, tenant) as db:
            changed = await db.execute(text(f"""update vh_workforce_outbox set status='submitted',response=cast(:response as jsonb),
                request_id=:request,receipt_id=:receipt,owner=null,lease_until=null,last_error=null
                where tenant_id={TENANT} and id=:id and owner=:owner and generation=:generation"""),
                {"response": json.dumps(response), "request": response.get("request_id"), "receipt": response.get("receipt_id"),
                 "id": task["id"], "owner": owner, "generation": task["generation"]})
            if changed.rowcount and binding and response.get("workflow_id"):
                if binding["workflow_id"] not in (None, response["workflow_id"]):
                    raise PartnerRejected("WORKFLOW_BINDING_MISMATCH")
                await db.execute(text(f"""update vh_workforce_bindings set workflow_id=:workflow,
                    conversation_id=coalesce(:conversation,conversation_id),updated_at=now(),next_poll=now()
                    where tenant_id={TENANT} and id=:id"""),
                    {"workflow": response["workflow_id"], "conversation": response.get("conversation_id"), "id": binding["id"]})
    except (httpx.HTTPError, PartnerRejected, HTTPException) as exc:
        permanent = isinstance(exc, (PartnerRejected, HTTPException))
        code = exc.code if isinstance(exc, PartnerRejected) else "DOMAIN_AUTHORIZATION_REVOKED" if permanent else "TRANSPORT_RETRY"
        async with transaction(engine, tenant) as db:
            await db.execute(text(f"""update vh_workforce_outbox set status=:status,last_error=:error,owner=null,lease_until=null,
                available=now()+interval '5 seconds' where tenant_id={TENANT} and id=:id and owner=:owner and generation=:generation"""),
                {"status": "blocked" if permanent else "queued", "error": code,
                 "id": task["id"], "owner": owner, "generation": task["generation"]})
            if binding:
                await db.execute(text(f"update vh_workforce_bindings set last_error=:error where tenant_id={TENANT} and id=:id"),
                    {"error": code, "id": binding["id"]})
    finally:
        beat.cancel()
        await asyncio.gather(beat, return_exceptions=True)
    return True


async def reconcile_outbox(engine, tenant, client):
    async with transaction(engine, tenant) as db:
        items = [dict(x) for x in (await db.execute(text(f"""select o.*,b.resident_id from vh_workforce_outbox o
            left join vh_workforce_bindings b on b.id=o.binding_id and b.tenant_id=o.tenant_id
            where o.tenant_id={TENANT} and o.status='submitted' and o.available<=now()
            order by o.available limit 20"""))).mappings()]
    for item in items:
        try:
            if item["kind"] == "provider":
                result = await client.call("GET", "/workforce/v1/provider/event-receipts/" + item["receipt_id"], provider=True)
                state = result["ingestion_status"]
                terminal = state in {"applied", "duplicate", "rejected", "needs_attention"}
                status = "blocked" if state in {"rejected", "needs_attention"} else "done" if terminal else "submitted"
            else:
                result = await client.call("GET", "/workforce/v1/partner/requests/" + item["request_id"], params={"external_user_id": item["resident_id"]})
                status = "blocked" if result["request_status"] == "blocked" else "done" if result["request_status"] == "completed" else "submitted"
            async with transaction(engine, tenant) as db:
                await db.execute(text(f"update vh_workforce_outbox set status=:status,response=cast(:response as jsonb),available=now()+interval '3 seconds' where tenant_id={TENANT} and id=:id and status='submitted'"),
                    {"status": status, "response": json.dumps(result), "id": item["id"]})
        except (httpx.HTTPError, PartnerRejected) as exc:
            async with transaction(engine, tenant) as db:
                await db.execute(text(f"""update vh_workforce_outbox set last_error=:error,
                    status=:status,available=now()+interval '10 seconds'
                    where tenant_id={TENANT} and id=:id and status='submitted'"""),
                    {"id": item["id"], "error": exc.code if isinstance(exc, PartnerRejected) else "TRANSPORT_RETRY",
                     "status": "blocked" if isinstance(exc, PartnerRejected) else "submitted"})


async def loop(engine, tenant, stop, config=None):
    client = WorkforceClient(config or WorkforceConfig.from_env())
    owner = str(uuid4())
    try:
        while not stop.is_set():
            try:
                from .workforce_provider import collect
                await collect(engine, tenant)
                await asyncio.gather(*(process_one(engine, tenant, client, owner + f":{i}") for i in range(20)))
                await reconcile_outbox(engine, tenant, client)
                async with transaction(engine, tenant) as db:
                    bindings = [dict(x) for x in (await db.execute(text(f"select * from vh_workforce_bindings where tenant_id={TENANT} and conversation_id is not null and state!='closed' and next_poll<=now() order by next_poll limit 20"))).mappings()]
                async def poll(binding):
                    try:
                        await poll_binding(engine, tenant, client, binding)
                    except (httpx.HTTPError, PartnerRejected, HTTPException) as exc:
                        code = exc.code if isinstance(exc, PartnerRejected) else "DOMAIN_AUTHORIZATION_REVOKED" if isinstance(exc, HTTPException) else "TRANSPORT_RETRY"
                        async with transaction(engine, tenant) as db:
                            await db.execute(text(f"update vh_workforce_bindings set last_error=:error,next_poll=now()+interval '10 seconds' where tenant_id={TENANT} and id=:id"), {"id": binding["id"], "error": code})
                await asyncio.gather(*(poll(binding) for binding in bindings))
            except Exception as exc:  # noqa: BLE001 -- durable adapter boundary retries after infrastructure failures
                log.error("Workforce adapter iteration failed (%s)", type(exc).__name__)
            try:
                await asyncio.wait_for(stop.wait(), 1)
            except TimeoutError:
                pass
    finally:
        await client.http.aclose()
