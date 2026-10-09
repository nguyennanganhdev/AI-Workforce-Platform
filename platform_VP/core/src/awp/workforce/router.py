"""Workforce v1 surface; partner bodies cannot select execution identities."""
import asyncio
import json
import time

from fastapi import APIRouter, Query, Request
from fastapi.responses import JSONResponse, StreamingResponse
from sqlalchemy import insert, select, update

from . import events, lifecycle
from . import models as m
from . import schema as s
from .service import Fault, Workforce, digest, row, stamp, uid


def build_router(service: Workforce):
    r = APIRouter(prefix="/workforce/v1")

    async def auth(request, operation, purpose="customer"):
        client = await service.authenticate(request.headers.get("authorization"), operation, purpose)
        checked = getattr(request.state, "rate_checked", set())
        if operation not in checked:
            await service.rate_limit(f"client:{client['id']}:{operation}", 600 if request.method == "POST" else 3000)
            request.state.rate_checked = checked | {operation}
        return client

    def admin(request):
        principal = getattr(request.state, "principal", None)
        if not principal or not principal.admin:
            raise Fault(403, "ADMIN_REQUIRED")
        return principal

    @r.post("/admin/knowledge/documents", status_code=201)
    async def knowledge_publish(body: m.KnowledgeDocument, request: Request):
        from .knowledge import publish
        principal = admin(request)
        return await publish(service, principal.tenant, body, principal.actor)

    @r.get("/admin/knowledge/documents")
    async def knowledge_list(request: Request):
        principal = admin(request)
        async with service.rt.db.engine.connect() as conn:
            records = (await conn.execute(select(s.knowledge).where(s.knowledge.c.tenant == principal.tenant)
                .order_by(s.knowledge.c.created.desc()).limit(1000))).mappings().all()
        return {"items": [dict(x) for x in records]}

    @r.post("/admin/knowledge/documents/{document_id}/revoke")
    async def knowledge_revoke(document_id: str, request: Request):
        principal = admin(request)
        async with service.tx() as conn:
            result = await conn.execute(update(s.knowledge).where(s.knowledge.c.id == document_id,
                s.knowledge.c.tenant == principal.tenant).values(status="revoked"))
            if not result.rowcount:
                raise Fault(404, "NOT_FOUND")
            await service.audit(conn, principal.tenant, principal.actor, "knowledge.revoke", document_id)
        return {"revoked": True}

    @r.post("/admin/clients", status_code=201)
    async def client_create(body: m.ClientCreate, request: Request):
        principal = admin(request)
        provider_ops = {"publish_job_event", "read_event_receipt"}
        if (body.purpose == "customer" and provider_ops.intersection(body.operations)) or (
                body.purpose == "provider" and set(body.operations) - provider_ops):
            raise Fault(422, "INVALID_PURPOSE_OPERATIONS")
        return await service.create_client(principal.tenant, body, principal.actor)

    @r.get("/admin/clients")
    async def clients(request: Request):
        principal = admin(request)
        async with service.rt.db.engine.connect() as conn:
            records = (await conn.execute(select(s.clients).where(s.clients.c.tenant == principal.tenant))).mappings()
            return {"items": [{k: x[k] for k in ("id", "purpose", "status", "expires", "operations")} for x in records]}

    @r.post("/admin/clients/{client_id}/revoke")
    async def revoke(client_id: str, request: Request):
        principal = admin(request)
        async with service.tx() as conn:
            result = await conn.execute(update(s.clients).where(s.clients.c.id == client_id,
                s.clients.c.tenant == principal.tenant).values(status="revoked"))
            if not result.rowcount:
                raise Fault(404, "NOT_FOUND")
            await service.audit(conn, principal.tenant, principal.actor, "client.revoke", client_id)
        return {"revoked": True}

    @r.post("/admin/clients/{client_id}/rotate")
    async def rotate(client_id: str, request: Request):
        import secrets
        principal = admin(request)
        secret = secrets.token_urlsafe(32)
        signing = secrets.token_urlsafe(32)
        async with service.tx() as conn:
            client = await row(conn, s.clients, s.clients.c.id == client_id, s.clients.c.tenant == principal.tenant, lock=True)
            if not client or client["status"] != "active":
                raise Fault(404, "NOT_FOUND")
            config = dict(client["settings"])
            if client["purpose"] == "provider":
                config.update(signing_key_id="sign-" + uid(), encrypted_signing_secret=service.cipher().encrypt(signing.encode()).decode())
            await conn.execute(update(s.clients).where(s.clients.c.id == client_id).values(key_hash=digest(secret.encode()), settings=config))
            await service.audit(conn, principal.tenant, principal.actor, "client.rotate", client_id)
        return {"client_id": client_id, "api_key": f"dp_{client_id}.{secret}",
                "signing_key_id": config.get("signing_key_id"), "signing_secret": signing if client["purpose"] == "provider" else None}

    @r.get("/admin/audit")
    async def audit(request: Request, limit: int = Query(100, ge=1, le=500)):
        principal = admin(request)
        async with service.rt.db.engine.connect() as conn:
            items = (await conn.execute(select(s.audit).where(s.audit.c.tenant == principal.tenant)
                .order_by(s.audit.c.created.desc()).limit(limit))).mappings().all()
        return {"items": [dict(item) for item in items]}

    @r.post("/admin/routes", status_code=201)
    async def route_create(body: m.RouteCreate, request: Request):
        principal = admin(request)
        async with service.tx() as conn:
            client = await row(conn, s.clients, s.clients.c.id == body.client_id,
                               s.clients.c.tenant == principal.tenant, s.clients.c.purpose == "customer")
            if not client:
                raise Fault(404, "NOT_FOUND")
            if await row(conn, s.routes, s.routes.c.client_id == client["id"], s.routes.c.external_ref == body.external_management_ref):
                raise Fault(409, "ROUTE_CONFLICT")
            route_id = uid()
            await conn.execute(insert(s.routes).values(id=route_id, client_id=client["id"],
                external_ref=body.external_management_ref, status="pending", revision=1, config=body.model_dump()))
            await service.audit(conn, principal.tenant, principal.actor, "route.create", route_id)
        return {"route_id": route_id, "revision": 1, "status": "pending"}

    @r.put("/admin/routes/{route_id}")
    async def route_revise(route_id: str, body: m.ReviseRoute, request: Request):
        principal = admin(request)
        async with service.tx() as conn:
            client = await row(conn, s.clients, s.clients.c.id == body.client_id, s.clients.c.tenant == principal.tenant)
            route = await row(conn, s.routes, s.routes.c.id == route_id, s.routes.c.client_id == body.client_id, lock=True)
            if not route or not client:
                raise Fault(404, "NOT_FOUND")
            if route["revision"] != body.expected_revision:
                raise Fault(409, "REVISION_CONFLICT")
            if route["external_ref"] != body.external_management_ref:
                raise Fault(422, "ROUTE_REFERENCE_IMMUTABLE")
            await conn.execute(update(s.routes).where(s.routes.c.id == route_id).values(
                config=body.model_dump(exclude={"expected_revision"}), revision=route["revision"] + 1, status="pending"))
            await service.audit(conn, principal.tenant, principal.actor, "route.revise", route_id,
                                {"revision": route["revision"] + 1})
        return {"route_id": route_id, "revision": route["revision"] + 1, "status": "pending"}

    @r.get("/admin/routes")
    async def routes(request: Request):
        principal = admin(request)
        async with service.rt.db.engine.connect() as conn:
            records = (await conn.execute(select(s.routes).join(s.clients, s.routes.c.client_id == s.clients.c.id)
                .where(s.clients.c.tenant == principal.tenant))).mappings().all()
        return {"items": [dict(x) for x in records]}

    @r.post("/admin/integrations", status_code=201)
    async def integration_create(body: m.IntegrationCreate, request: Request):
        principal = admin(request)
        config = body.model_dump(exclude={"id", "headers", "context_signing_key"})
        config["encrypted_headers"] = service.cipher().encrypt(json.dumps(body.headers).encode()).decode()
        config["encrypted_context_key"] = service.cipher().encrypt(body.context_signing_key.encode()).decode()
        async with service.tx() as conn:
            if await row(conn, s.integrations, s.integrations.c.id == body.id):
                raise Fault(409, "INTEGRATION_ALREADY_EXISTS")
            if any(p.tracks_events for p in body.tools.values()):
                provider = await row(conn, s.clients, s.clients.c.id == body.id,
                    s.clients.c.tenant == principal.tenant, s.clients.c.purpose == "provider", s.clients.c.status == "active")
                if not provider or not provider["settings"].get("event_map"):
                    raise Fault(422, "PROVIDER_TRACKING_NOT_CONFIGURED")
            await conn.execute(insert(s.integrations).values(id=body.id, tenant=principal.tenant,
                status="active", revision=1, config=config))
            await service.audit(conn, principal.tenant, principal.actor, "integration.create", body.id)
        return {"id": body.id, "status": "active", "revision": 1}

    @r.get("/admin/integrations")
    async def integrations(request: Request):
        principal = admin(request)
        async with service.rt.db.engine.connect() as conn:
            records = (await conn.execute(select(s.integrations).where(s.integrations.c.tenant == principal.tenant))).mappings().all()
        return {"items": [{"id": x["id"], "status": x["status"], "revision": x["revision"],
            "url": x["config"]["url"], "tools": x["config"]["tools"]} for x in records]}

    @r.post("/admin/integrations/{integration_id}/revoke")
    async def integration_revoke(integration_id: str, request: Request):
        principal = admin(request)
        async with service.tx() as conn:
            result = await conn.execute(update(s.integrations).where(s.integrations.c.id == integration_id,
                s.integrations.c.tenant == principal.tenant).values(status="revoked", revision=s.integrations.c.revision + 1))
            if not result.rowcount:
                raise Fault(404, "NOT_FOUND")
            await service.audit(conn, principal.tenant, principal.actor, "integration.revoke", integration_id)
        return {"revoked": True}

    @r.get("/admin/workflows")
    async def workflows(request: Request, limit: int = Query(100, ge=1, le=500)):
        principal = admin(request)
        async with service.rt.db.engine.connect() as conn:
            records = (await conn.execute(select(s.workflows).join(s.conversations,
                s.conversations.c.id == s.workflows.c.conversation_id).join(s.clients,
                s.clients.c.id == s.conversations.c.client_id).where(s.clients.c.tenant == principal.tenant)
                .order_by(s.workflows.c.updated.desc()).limit(limit))).mappings().all()
        return {"items": [dict(x) for x in records]}

    @r.get("/admin/workflows/{workflow_id}")
    async def inspect_workflow(workflow_id: str, request: Request):
        principal = admin(request)
        async with service.rt.db.engine.connect() as conn:
            flow = await row(conn, s.workflows, s.workflows.c.id == workflow_id)
            if not flow or flow["snapshot"]["tenant"] != principal.tenant:
                raise Fault(404, "NOT_FOUND")
            result = {"workflow": flow}
            for key, table in [("jobs", s.jobs), ("operations", s.operations), ("approvals", s.approvals), ("reservations", s.reservations)]:
                values = (await conn.execute(select(table).where(table.c.workflow_id == workflow_id).limit(500))).mappings().all()
                result[key] = [{k: v for k, v in x.items() if k not in ("data", "payload", "owner")} for x in values]
        return result

    @r.post("/admin/operations/{operation_id}/reconcile")
    async def reconcile(operation_id: str, body: m.Reconcile, request: Request):
        principal = admin(request)
        async with service.tx() as conn:
            op = await row(conn, s.operations, s.operations.c.id == operation_id)
            flow = await row(conn, s.workflows, s.workflows.c.id == op["workflow_id"], lock=True) if op else None
            if not flow or flow["snapshot"]["tenant"] != principal.tenant:
                raise Fault(404, "NOT_FOUND")
            op = await row(conn, s.operations, s.operations.c.id == operation_id, lock=True)
            if op["status"] != body.expected_status:
                raise Fault(409, "REVISION_CONFLICT")
            if body.status == "pending" and not body.external_job_id:
                raise Fault(422, "TRACKING_REFERENCE_REQUIRED")
            if body.status == "pending" and not op["data"].get("policy", {}).get("tracks_events"):
                raise Fault(422, "PROVIDER_TRACKING_NOT_CONFIGURED")
            op.update(status=body.status, external_job_id=body.external_job_id or op["external_job_id"],
                      data={**op["data"], "reconciliation": body.evidence})
            await conn.execute(update(s.operations).where(s.operations.c.id == operation_id).values(
                status=op["status"], external_job_id=op["external_job_id"], data=op["data"]))
            if flow["state"] != "closed":
                await service.transition(conn, flow, "waiting_external_event" if body.status == "pending" else
                    "needs_attention" if body.status == "failed" else "awaiting_confirmation")
                await service.event(conn, flow, "operation.status_changed", {"operation_id": operation_id, "status": body.status})
                await lifecycle.resume_after_operation(service, conn, flow, op)
            await service.audit(conn, principal.tenant, principal.actor, "operation.reconcile", operation_id,
                                {"status": body.status, "evidence": body.evidence})
        return {"operation_id": operation_id, "status": body.status}

    @r.post("/partner/routes/{route_id}/confirm")
    async def confirm(route_id: str, body: m.RouteConfirm, request: Request):
        client = await auth(request, "confirm_route")
        async with service.tx() as conn:
            route = await row(conn, s.routes, s.routes.c.id == route_id, s.routes.c.client_id == client["id"], lock=True)
            if not route or route["external_ref"] != body.external_management_ref:
                raise Fault(403, "ROUTE_NOT_AUTHORIZED")
            if route["status"] == "active" and route["revision"] == body.expected_revision + 1:
                pass  # replay of the original confirmation
            elif route["status"] != "pending" or route["revision"] != body.expected_revision:
                raise Fault(409, "ROUTE_CONFLICT")
            else:
                route.update(status="active", revision=route["revision"] + 1)
                await conn.execute(update(s.routes).where(s.routes.c.id == route_id).values(
                    status="active", revision=route["revision"]))
        return {"route_id": route_id, "external_management_ref": route["external_ref"],
                "status": route["status"], "revision": route["revision"], "allowed_operations": client["operations"]}

    @r.put("/partner/residences/{residence_id}")
    async def residence_put(residence_id: str, body: m.Residence, request: Request):
        client = await auth(request, "sync_residence")
        async with service.tx() as conn:
            route = await service.route(conn, client, body.external_management_ref)
            old = await row(conn, s.residences, s.residences.c.client_id == client["id"],
                            s.residences.c.residence_id == residence_id, s.residences.c.user_id == body.external_user_id, lock=True)
            expected = old["revision"] if old else 0
            replay = old and old["revision"] == body.expected_revision + 1 and (
                old["route_id"], old["status"]) == (route["id"], body.status)
            if not replay and expected != body.expected_revision:
                raise Fault(409, "REVISION_CONFLICT")
            if replay:
                data = old
            else:
                data = {"client_id": client["id"], "residence_id": residence_id, "user_id": body.external_user_id,
                            "route_id": route["id"], "status": body.status, "revision": expected + 1, "updated": time.time()}
                if old:
                    await conn.execute(update(s.residences).where(s.residences.c.client_id == client["id"],
                        s.residences.c.residence_id == residence_id, s.residences.c.user_id == body.external_user_id).values(**data))
                else:
                    await conn.execute(insert(s.residences).values(**data))
        return JSONResponse({"residence_id": residence_id, "external_user_id": body.external_user_id,
            "external_management_ref": body.external_management_ref, "status": data["status"],
            "revision": data["revision"], "updated_at": stamp(data["updated"])}, status_code=200 if old else 201)

    @r.post("/partner/requests", response_model=m.RequestResult,
            responses={202: {"model": m.RequestResult, "description": "Durably accepted; poll status or consume events"}})
    async def submit(body: m.Command, request: Request):
        client = await auth(request, "submit_request" if body.command_type == "start_workflow" else "reply")
        request_id = await service.submit(client, body)
        status, representation = await service.wait_result(client, request_id, body.external_user_id)
        return JSONResponse(representation, status_code=status)

    @r.get("/partner/requests/{request_id}", response_model=m.RequestResult)
    async def get_request(request_id: str, request: Request, external_user_id: str = Query(min_length=1)):
        client = await auth(request, "read_result")
        _, result = await service.representation(client, request_id, external_user_id)
        return result

    @r.get("/partner/conversations/{conversation_id}")
    async def get_snapshot(conversation_id: str, request: Request, external_user_id: str = Query(min_length=1)):
        client = await auth(request, "read_result")
        return await events.snapshot(service, client, conversation_id, external_user_id)

    @r.get("/partner/conversations/{conversation_id}/event-history")
    async def get_history(conversation_id: str, request: Request, external_user_id: str = Query(min_length=1),
                          after_cursor: str | None = None, limit: int = Query(100, ge=1, le=500)):
        client = await auth(request, "receive_events")
        await auth(request, "read_result")
        return await events.history(service, client, conversation_id, external_user_id, after_cursor, limit)

    @r.get("/partner/conversations/{conversation_id}/events")
    async def stream(conversation_id: str, request: Request, external_user_id: str = Query(min_length=1),
                     after_cursor: str | None = None):
        client = await auth(request, "receive_events")
        await auth(request, "read_result")
        header = request.headers.get("last-event-id")
        if header and after_cursor and header != after_cursor:
            raise Fault(409, "EVENT_CURSOR_CONFLICT")
        cursor = header or after_cursor
        first = await events.history(service, client, conversation_id, external_user_id, cursor)

        async def generate():
            nonlocal cursor
            page, heartbeat = first, time.monotonic()
            while not await request.is_disconnected():
                for item in page["items"]:
                    cursor = item["event_id"]
                    yield f"id: {cursor}\nevent: {item['event_type']}\ndata: {json.dumps(item, ensure_ascii=False)}\n\n"
                if time.monotonic() - heartbeat >= 15:
                    yield ": heartbeat\n\n"
                    heartbeat = time.monotonic()
                await asyncio.sleep(.25)
                try:
                    client_now = await auth(request, "receive_events")
                    await auth(request, "read_result")
                    page = await events.history(service, client_now, conversation_id, external_user_id, cursor)
                except Fault:
                    return  # Headers already sent: reconnect performs full auth/cursor checks.
        return StreamingResponse(generate(), media_type="text/event-stream",
                                 headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"})

    @r.post("/partner/workflows/{workflow_id}/close")
    async def close_workflow(workflow_id: str, body: m.Close, request: Request):
        client = await auth(request, "close_workflow")
        return await lifecycle.close(service, client, workflow_id, body)

    @r.post("/partner/approvals/{approval_id}/decision", status_code=202)
    async def approval(approval_id: str, body: m.Decision, request: Request):
        client = await auth(request, "submit_consent")
        return await lifecycle.decide(service, client, approval_id, body)

    @r.post("/provider/job-events", status_code=202)
    async def provider_event(body: m.ProviderEvent, request: Request):
        from .provider import ingest
        client = await auth(request, "publish_job_event", "provider")
        return await ingest(service, client, body, await request.body(), request.headers)

    @r.get("/provider/event-receipts/{receipt_id}")
    async def receipt(receipt_id: str, request: Request):
        client = await auth(request, "read_event_receipt", "provider")
        async with service.rt.db.engine.connect() as conn:
            record = await row(conn, s.receipts, s.receipts.c.id == receipt_id, s.receipts.c.integration_id == client["id"])
        if not record:
            raise Fault(404, "NOT_FOUND")
        return {"receipt_id": record["id"], "external_event_id": record["external_id"],
                "ingestion_status": record["status"], "received_at": stamp(record["received"]),
                "applied_at": stamp(record["applied"]), "error": record["error"]}

    @r.post("/partner/assets/uploads", status_code=201)
    async def upload(body: m.Upload, request: Request):
        from .assets import create_upload
        client = await auth(request, "upload_asset")
        return await create_upload(service, client, body)

    @r.post("/partner/assets/{asset_id}/complete")
    async def finalize_asset(asset_id: str, request: Request, external_user_id: str = Query(min_length=1)):
        from .assets import finalize
        client = await auth(request, "upload_asset")
        return await finalize(service, client, asset_id, external_user_id)

    @r.get("/partner/assets/{asset_id}/content")
    async def content(asset_id: str, request: Request, external_user_id: str = Query(min_length=1)):
        from .assets import content
        client = await auth(request, "read_result")
        data, mime = await content(service, client, asset_id, external_user_id)
        from fastapi import Response
        return Response(data, media_type=mime, headers={"Cache-Control": "private, no-store", "X-Content-Type-Options": "nosniff"})

    @r.get("/partner/assets/{asset_id}")
    async def asset_metadata(asset_id: str, request: Request, external_user_id: str = Query(min_length=1)):
        from .assets import owned
        client = await auth(request, "read_result")
        asset = await owned(service, client, asset_id, external_user_id)
        return {"asset_id": asset_id, "status": asset["status"], "workflow_id": asset["workflow_id"],
                **{k: asset["metadata"][k] for k in ("content_type", "size", "sha256")}}

    return r
