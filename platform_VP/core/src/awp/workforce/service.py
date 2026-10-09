"""Transactional partner commands, authorization, bindings and public projections."""
from __future__ import annotations

import asyncio
import hashlib
import hmac
import json
import secrets
import time
import uuid
from contextlib import asynccontextmanager
from dataclasses import asdict
from datetime import UTC, datetime

from sqlalchemy import func, insert, select, update

from . import schema as s


def uid():
    return str(uuid.uuid4())


def digest(value):
    raw = value if isinstance(value, bytes) else json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode()
    return hashlib.sha256(raw).hexdigest()


def stamp(value):
    return datetime.fromtimestamp(value, UTC).isoformat().replace("+00:00", "Z") if value is not None else None


class Fault(Exception):
    def __init__(self, status, code, message=None):
        self.status, self.code = status, code
        self.message = message or code.replace("_", " ").capitalize()


async def row(conn, table, *where, lock=False):
    query = select(table).where(*where)
    if lock:
        query = query.with_for_update()
    value = (await conn.execute(query)).mappings().first()
    return dict(value) if value else None


class Workforce:
    def __init__(self, rt, intake):
        self.rt, self.intake = rt, intake
        self.wait_seconds = rt.settings.workforce_wait_seconds
        self.worker_tasks = set()
        self.runner = None  # tests may inject a scripted runner, never chosen by partner payload

    @asynccontextmanager
    async def tx(self):
        async with self.rt.db.engine.connect() as conn:
            if conn.dialect.name == "sqlite":
                await conn.exec_driver_sql("BEGIN IMMEDIATE")
            else:
                await conn.begin()
            try:
                yield conn
                await conn.commit()
            except BaseException:
                await conn.rollback()
                raise

    async def authenticate(self, authorization, operation, purpose="customer"):
        if not authorization or not authorization.startswith("ApiKey dp_"):
            raise Fault(401, "INVALID_CREDENTIAL")
        key = authorization[10:]
        key_id, sep, secret = key.partition(".")
        if not sep or not secret:
            raise Fault(401, "INVALID_CREDENTIAL")
        async with self.rt.db.engine.connect() as conn:
            client = await row(conn, s.clients, s.clients.c.id == key_id)
        if not client or not hmac.compare_digest(client["key_hash"], digest(secret.encode())):
            raise Fault(401, "INVALID_CREDENTIAL")
        if client["status"] != "active" or (client["expires"] and client["expires"] <= time.time()):
            raise Fault(401, "CREDENTIAL_REVOKED_OR_EXPIRED")
        if client["purpose"] != purpose or operation not in client["operations"]:
            raise Fault(403, "OPERATION_NOT_AUTHORIZED")
        return client

    def cipher(self):
        from cryptography.fernet import Fernet
        key = self.rt.settings.workforce_secret_key
        if not key:
            raise Fault(503, "SECRET_STORAGE_NOT_CONFIGURED")
        return Fernet(key.encode())

    async def rate_limit(self, key, maximum):
        window = int(time.time()) // 60
        async with self.tx() as conn:
            # A fixed set of client rows serializes first creation across processes.
            if key.startswith("client:"):
                await row(conn, s.clients, s.clients.c.id == key.split(":")[1], lock=True)
            elif conn.dialect.name == "postgresql":
                from sqlalchemy import text
                await conn.execute(text("SELECT pg_advisory_xact_lock(:key)"), {"key": int(digest(key.encode())[:15], 16)})
            entry = await row(conn, s.rate_limits, s.rate_limits.c.id == key, lock=True)
            count = entry["count"] if entry and entry["window"] == window else 0
            if count >= maximum:
                raise Fault(429, "RATE_LIMITED")
            values = {"window": window, "count": count + 1}
            if entry:
                await conn.execute(update(s.rate_limits).where(s.rate_limits.c.id == key).values(**values))
            else:
                await conn.execute(insert(s.rate_limits).values(id=key, **values))

    async def audit(self, conn, tenant, actor, action, resource, data=None):
        await conn.execute(insert(s.audit).values(id=uid(), tenant=tenant, actor=actor,
            action=action, resource=resource, data=data or {}, created=time.time()))

    async def create_client(self, tenant, body, actor="machine-admin"):
        secret = secrets.token_urlsafe(32)
        settings = dict(body.settings)
        # Signing secret is independent of the API secret and is shown once.
        signing = secrets.token_urlsafe(32) if body.purpose == "provider" else None
        if signing:
            settings["signing_key_id"] = "sign-" + body.id
            settings["encrypted_signing_secret"] = self.cipher().encrypt(signing.encode()).decode()
        async with self.tx() as conn:
            if await row(conn, s.clients, s.clients.c.id == body.id):
                raise Fault(409, "CLIENT_ALREADY_EXISTS")
            await conn.execute(insert(s.clients).values(id=body.id, tenant=tenant, purpose=body.purpose,
                key_hash=digest(secret.encode()), status="active", expires=body.expires,
                operations=body.operations, settings=settings))
            await self.audit(conn, tenant, actor, "client.create", body.id)
        return {"client_id": body.id, "api_key": f"dp_{body.id}.{secret}",
                "signing_key_id": settings.get("signing_key_id"), "signing_secret": signing}

    async def route(self, conn, client, ref, active=True):
        result = await row(conn, s.routes, s.routes.c.client_id == client["id"],
                           s.routes.c.external_ref == ref, lock=True)
        if not result or (active and result["status"] != "active"):
            raise Fault(403, "ROUTE_NOT_AUTHORIZED")
        return result

    async def event(self, conn, workflow, kind, payload, occurred=None):
        conv = await row(conn, s.conversations, s.conversations.c.id == workflow["conversation_id"], lock=True)
        seq = conv["sequence"] + 1
        event = {"id": uid(), "conversation_id": conv["id"], "workflow_id": workflow["id"], "sequence": seq,
                     "event_type": kind, "payload": payload, "occurred": occurred or time.time(), "recorded": time.time()}
        await conn.execute(insert(s.events).values(**event))
        await conn.execute(update(s.conversations).where(s.conversations.c.id == conv["id"]).values(sequence=seq,
                                                                                                 latest_event_id=event["id"]))
        if kind == "assistant.message":
            await conn.execute(insert(s.messages).values(id=payload["message_id"], conversation_id=conv["id"],
                workflow_id=workflow["id"], sequence=seq, payload=payload))
        return event

    async def transition(self, conn, wf, state, reason=None):
        if wf["state"] == "closed" and state != "closed":
            raise Fault(409, "WORKFLOW_CLOSED")
        wf.update(state=state, revision=wf["revision"] + 1, updated=time.time())
        if state == "closed":
            wf["closed_at"] = time.time()
        await conn.execute(update(s.workflows).where(s.workflows.c.id == wf["id"]).values(
            state=state, revision=wf["revision"], updated=wf["updated"], closed_at=wf.get("closed_at")))
        payload = {"state": state, "revision": wf["revision"]}
        if state == "closed":
            payload.update(closed_at=stamp(wf["closed_at"]), reason=reason or "read_only_completed")
        kind = {"closed": "workflow.closed", "awaiting_user": "workflow.awaiting_user",
                "needs_attention": "workflow.needs_attention"}.get(state, "workflow.status_changed")
        await self.event(conn, wf, kind, payload)

    async def binding(self, conn, client, workflow_id, user, ticket=None, conversation=None):
        wf = await row(conn, s.workflows, s.workflows.c.id == workflow_id, lock=True)
        if not wf:
            raise Fault(404, "NOT_FOUND")
        conv = await row(conn, s.conversations, s.conversations.c.id == wf["conversation_id"])
        if conv["client_id"] != client["id"] or conv["user_id"] != user:
            raise Fault(404, "NOT_FOUND")
        if (ticket is not None and conv["external_ticket_id"] != ticket) or (
                conversation is not None and conv["external_conversation_id"] != conversation):
            raise Fault(409, "WORKFLOW_BINDING_MISMATCH")
        route = await row(conn, s.routes, s.routes.c.id == conv["route_id"])
        if not route or route["status"] != "active":
            raise Fault(403, "ROUTE_NOT_AUTHORIZED")
        if wf["snapshot"]["route_revision"] != route["revision"] and wf["state"] != "closed":
            raise Fault(409, "ROUTE_CHANGED")
        if wf["snapshot"].get("residence_id"):
            membership = await row(conn, s.residences, s.residences.c.client_id == client["id"],
                s.residences.c.user_id == user, s.residences.c.residence_id == wf["snapshot"]["residence_id"],
                s.residences.c.route_id == route["id"], s.residences.c.status == "active")
            if not membership:
                raise Fault(403, "RESIDENCE_NOT_AUTHORIZED")
        return wf, conv

    async def replay(self, conn, client, external_id, payload):
        old = await row(conn, s.requests, s.requests.c.client_id == client["id"],
                        s.requests.c.external_id == external_id, lock=True)
        if old:
            if old["payload_hash"] != digest(payload):
                raise Fault(409, "IDEMPOTENCY_CONFLICT")
            await self.binding(conn, client, old["workflow_id"], payload["external_user_id"])
        return old

    async def add_request(self, conn, client, wf, payload, command, status="queued"):
        req = {"id": uid(), "client_id": client["id"], "external_id": payload["external_request_id"],
                   "payload_hash": digest(payload), "command": command, "workflow_id": wf["id"], "status": status,
                   "body": payload, "result": None, "error": None, "created": time.time(), "completed": None}
        await conn.execute(insert(s.requests).values(**req))
        return req

    async def enqueue(self, conn, wf, req, kind="agent", payload=None):
        await conn.execute(insert(s.jobs).values(id=uid(), workflow_id=wf["id"], request_id=req["id"],
            kind=kind, status="queued", payload=payload or {}, lease_until=0, generation=0, attempts=0,
            available=time.time()))

    async def submit(self, client, command):
        data = command.model_dump(mode="json")
        async with self.tx() as conn:
            # Serializes the client's common command-ID namespace on PostgreSQL too.
            await row(conn, s.clients, s.clients.c.id == client["id"], lock=True)
            old = await self.replay(conn, client, command.external_request_id, data)
            if old:
                return old["id"]
            route = await self.route(conn, client, command.external_management_ref)
            config = route["config"]
            if config["ticket_binding_mode"] == "required" and not command.external_ticket_id:
                raise Fault(422, "EXTERNAL_TICKET_REQUIRED")
            if command.timezone:
                from zoneinfo import ZoneInfo, ZoneInfoNotFoundError
                try:
                    ZoneInfo(command.timezone)
                except ZoneInfoNotFoundError:
                    raise Fault(422, "INVALID_TIMEZONE")
            if command.command_type == "start_workflow":
                if config["require_residence"]:
                    residence = await row(conn, s.residences, s.residences.c.client_id == client["id"],
                        s.residences.c.residence_id == command.residence_id,
                        s.residences.c.user_id == command.external_user_id,
                        s.residences.c.route_id == route["id"], s.residences.c.status == "active")
                    if not residence:
                        raise Fault(403, "RESIDENCE_NOT_AUTHORIZED")
                ext_ticket = command.external_ticket_id or "conversation:" + command.external_conversation_id
                if await row(conn, s.conversations, s.conversations.c.client_id == client["id"],
                             s.conversations.c.external_ticket_id == ext_ticket):
                    raise Fault(409, "TICKET_ALREADY_BOUND")
                if await row(conn, s.conversations, s.conversations.c.client_id == client["id"],
                             s.conversations.c.external_conversation_id == command.external_conversation_id):
                    raise Fault(409, "CONVERSATION_ALREADY_BOUND")
                profile = await self.rt.profiles.get_published(client["tenant"], config["leader_profile"])
                if not profile or profile.profile.role != "leader":
                    raise Fault(422, "LEADER_NOT_PUBLISHED")
                manifest, models, integration_versions = {profile.key: profile.version}, {}, {}
                for key in profile.profile.team:
                    specialist = await self.rt.profiles.get_published(client["tenant"], key)
                    if not specialist or specialist.profile.role != "specialist":
                        raise Fault(422, "SPECIALIST_NOT_PUBLISHED")
                    manifest[key] = specialist.version
                for key, version in manifest.items():
                    rec = await self.rt.profiles.get(client["tenant"], key, version)
                    spec = self.rt.catalog.specs.get(rec.profile.model_id) if rec.profile.model_id else self.rt.catalog.pick(rec.profile.model_tier)
                    if spec:
                        models[key] = asdict(spec)
                for key in config["integration_ids"]:
                    integration = await row(conn, s.integrations, s.integrations.c.id == key,
                        s.integrations.c.tenant == client["tenant"], s.integrations.c.status == "active")
                    if not integration:
                        raise Fault(422, "INTEGRATION_NOT_ACTIVE")
                    integration_versions[key] = integration["revision"]
                from .knowledge import manifest as knowledge_manifest
                documents = await knowledge_manifest(conn, client["tenant"], config.get("knowledge_base_ids", []))
                count = (await conn.execute(select(func.count()).select_from(s.workflows.join(
                    s.conversations, s.workflows.c.conversation_id == s.conversations.c.id)).where(
                    s.conversations.c.route_id == route["id"], s.workflows.c.state != "closed"))).scalar_one()
                if count >= config["max_active_workflows"]:
                    raise Fault(429, "WORKFLOW_CAPACITY_REACHED")
                conv_id = uid()
                await conn.execute(insert(s.conversations).values(id=conv_id, client_id=client["id"],
                    route_id=route["id"], user_id=command.external_user_id, external_ticket_id=ext_ticket,
                    external_conversation_id=command.external_conversation_id, sequence=0, purged_through=0))
                wf = {"id": uid(), "conversation_id": conv_id, "state": "accepted", "revision": 1,
                    "snapshot": {**config, "tenant": client["tenant"], "route_revision": route["revision"],
                              "leader_version": profile.version, "route_id": route["id"],
                              "profiles": manifest, "models": models, "integrations": integration_versions,
                              "knowledge_documents": documents,
                              "residence_id": command.residence_id if config["require_residence"] else None,
                              "external_user_id": command.external_user_id, "external_ticket_id": ext_ticket},
                    "case_id": None, "created": time.time(), "updated": time.time(), "closed_at": None}
                await conn.execute(insert(s.workflows).values(**wf))
            else:
                if not command.workflow_id:
                    raise Fault(422, "WORKFLOW_REFERENCE_REQUIRED")
                wf, conv = await self.binding(conn, client, command.workflow_id, command.external_user_id,
                                              command.external_ticket_id, command.external_conversation_id)
                if conv["route_id"] != route["id"]:
                    raise Fault(409, "WORKFLOW_BINDING_MISMATCH")
                if wf["state"] == "closed":
                    raise Fault(409, "WORKFLOW_CLOSED")
                if wf["state"] == "awaiting_approval":
                    raise Fault(409, "APPROVAL_DECISION_REQUIRED")
            for asset_id in command.message.asset_ids:
                asset = await row(conn, s.assets, s.assets.c.id == asset_id, lock=True)
                if not config["asset_capability"]:
                    raise Fault(422, "UNSUPPORTED_MESSAGE_PART")
                if not asset or asset["status"] != "ready" or asset["client_id"] != client["id"] or (
                    asset["user_id"], asset["external_ticket_id"], asset["external_conversation_id"], asset["route_id"]
                ) != (command.external_user_id, command.external_ticket_id, command.external_conversation_id, route["id"]):
                    raise Fault(403, "ASSET_NOT_AUTHORIZED")
                if asset["workflow_id"] not in (None, wf["id"]):
                    raise Fault(409, "ASSET_ALREADY_BOUND")
                await conn.execute(update(s.assets).where(s.assets.c.id == asset_id).values(workflow_id=wf["id"]))
            req = await self.add_request(conn, client, wf, data, command.command_type)
            await self.audit(conn, client["tenant"], client["id"], command.command_type, wf["id"], {"request_id": req["id"]})
            await self.event(conn, wf, "request.accepted", {"request_id": req["id"]})
            await self.enqueue(conn, wf, req)
        return req["id"]

    @staticmethod
    def next_action(wf, pending=False):
        if pending:
            return "watch_request"
        return {"closed": "none", "awaiting_user": "submit_reply", "awaiting_approval": "submit_approval",
                "awaiting_confirmation": "confirm_close", "waiting_external_event": "watch_events",
                "needs_attention": "resolve_attention", "blocked_authorization": "resolve_attention",
                "blocked_route_changed": "resolve_attention", "active": "watch_request", "accepted": "watch_request"}[wf["state"]]

    async def representation(self, client, request_id, user):
        async with self.rt.db.engine.connect() as conn:
            req = await row(conn, s.requests, s.requests.c.id == request_id, s.requests.c.client_id == client["id"])
            if not req:
                raise Fault(404, "NOT_FOUND")
            wf, conv = await self.binding(conn, client, req["workflow_id"], user)
            pending = req["status"] in ("accepted", "queued", "running")
            return (202 if pending else 200), {"request_id": req["id"], "request_status": req["status"],
                "external_ticket_id": req["body"].get("external_ticket_id"), "conversation_id": conv["id"],
                "workflow_id": wf["id"], "workflow_state": wf["state"], "workflow_revision": wf["revision"],
                "next_action": self.next_action(wf, pending), "ticket_id": None,
                "result": req["result"], "error": req["error"], "accepted_at": stamp(req["created"]),
                "completed_at": stamp(req["completed"]),
                "status_url": f"/workforce/v1/partner/requests/{req['id']}",
                "conversation_url": f"/workforce/v1/partner/conversations/{conv['id']}",
                "event_stream_url": f"/workforce/v1/partner/conversations/{conv['id']}/events"}

    async def wait_result(self, client, request_id, user):
        deadline = time.monotonic() + self.wait_seconds
        while True:
            status, body = await self.representation(client, request_id, user)
            if status == 200 or time.monotonic() >= deadline:
                return status, body
            await asyncio.sleep(min(.1, max(0, deadline - time.monotonic())))

    async def workflow_of_case(self, case_id):
        async with self.rt.db.engine.connect() as conn:
            return await row(conn, s.workflows, s.workflows.c.case_id == case_id)

    async def finalize_case(self, case_id, result, fence=None):
        wf = await self.workflow_of_case(case_id)
        if wf is None:
            return None
        from .lifecycle import complete
        error = None if result.get("outcome") == "resolved" and not result.get("unknowns") else {
            "code": "NEEDS_HUMAN", "retryable": False}
        return await complete(self, wf["id"], result["answer"], error=error, fence=fence)
