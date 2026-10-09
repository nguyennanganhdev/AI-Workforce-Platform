"""Scoped MCP adapter over Vinhomes commands. No arbitrary SQL/REST tool is exposed."""
import base64
import hashlib
import hmac
import json
import os
import time
from contextlib import asynccontextmanager
from datetime import datetime
from uuid import UUID

from fastapi.encoders import jsonable_encoder
from sqlalchemy import text
from sqlalchemy.ext.asyncio import create_async_engine

from .resident_contract import TENANT
from .workforce import fingerprint, transaction
from .workforce_config import WorkforceConfig


def verify_context(config, headers, tool, arguments):
    token = headers.get("x-workforce-context", "")
    signature = headers.get("x-workforce-signature", "")
    if len(token) > 8192 or not hmac.compare_digest(signature,
            hmac.new(config.mcp_context_key.encode(), token.encode(), hashlib.sha256).hexdigest()):
        raise ValueError("Invalid Workforce context signature")
    try:
        claims = json.loads(base64.urlsafe_b64decode(token))
        now = int(time.time())
        if not now < claims["expires"] <= now + 120 or claims["audience"] != config.mcp_audience:
            raise ValueError()
        if claims["tool"] != tool or claims["arguments_hash"] != fingerprint(arguments):
            raise ValueError()
        if not isinstance(claims["user_id"], str) or len(claims["user_id"]) > 200:
            raise ValueError()
        return claims
    except (ValueError, TypeError, KeyError):
        raise ValueError("Expired or mismatched Workforce context") from None


async def authority(db, claims, ticket_id, tool, write=False):
    ticket = (await db.execute(text(f"""select t.* from tickets t where t.tenant_id={TENANT} and t.id=:id
        and t.requester_user_id=:resident and cast(t.management_unit_id as text)=:management
        and exists(select 1 from users u join tenant_memberships m on m.user_id=u.id and m.tenant_id=t.tenant_id
            where u.id=:resident and u.status='active' and m.status='active')
        and exists(select 1 from unit_residents ur where ur.tenant_id=t.tenant_id and ur.unit_id=t.unit_id
            and ur.user_id=:resident and ur.verification_status='verified' and ur.valid_from<=now()
            and (ur.valid_to is null or ur.valid_to>now())) for update of t"""),
        {"id": UUID(ticket_id), "resident": claims["user_id"], "management": claims["management_ref"]})).mappings().first()
    if not ticket or claims.get("external_ticket_id") != f"{ticket['id']}:g{ticket['reopen_count']}":
        raise ValueError("Ticket is outside current resident/management scope")
    binding = (await db.execute(text(f"""select * from vh_workforce_bindings where tenant_id={TENANT}
        and ticket_id=:ticket and generation=:generation and resident_id=:resident for update"""),
        {"ticket": ticket["id"], "generation": ticket["reopen_count"], "resident": claims["user_id"]})).mappings().first()
    if not binding or binding["state"] == "closed" or binding["workflow_id"] not in (None, claims["workflow_id"]):
        raise ValueError("Workflow binding is unavailable")
    if not binding["workflow_id"]:
        await db.execute(text(f"update vh_workforce_bindings set workflow_id=:workflow where tenant_id={TENANT} and id=:id and workflow_id is null"),
                         {"workflow": claims["workflow_id"], "id": binding["id"]})
    scope = None
    if write or tool == "get_staff_availability":
        grant = (await db.execute(text(f"""select g.* from vh_workforce_management_grants g join users u on u.id=g.service_actor
            where g.tenant_id={TENANT} and g.management_unit_id=:management and g.active and u.status='active'"""),
            {"management": ticket["management_unit_id"]})).mappings().first()
        if not grant or tool not in grant["tools"]:
            raise ValueError("Domain management has not granted this operation")
        scope = (db, grant["service_actor"], False)
        from .v3_mutations import management_access
        if not await management_access(scope, dict(ticket)):
            raise ValueError("Management service actor lost its business role")
        if write and not claims.get("consent_approval_id") and ticket["category_id"] not in grant["auto_categories"]:
            raise ValueError("A verified approval is required; automatic dispatch is disabled for this category")
    return dict(ticket), scope


def build_mcp(settings, config=None, engine=None):
    from mcp.server.fastmcp import Context, FastMCP
    from mcp.server.transport_security import TransportSecuritySettings
    from mcp.types import ToolAnnotations
    config = config or WorkforceConfig.from_env()

    @asynccontextmanager
    async def lifespan(server):
        db_engine = engine or create_async_engine(settings.database_url, pool_pre_ping=True)
        try:
            yield {"engine": db_engine}
        finally:
            if engine is None:
                await db_engine.dispose()

    server = FastMCP("Vinhomes Workforce MCP", stateless_http=True, json_response=True, lifespan=lifespan,
        max_request_body_size=262144, transport_security=TransportSecuritySettings(
            enable_dns_rebinding_protection=True,
            allowed_hosts=os.getenv("VINHOMES_WORKFORCE_MCP_HOSTS", "127.0.0.1:*,localhost:*,host.docker.internal:*,domain-mcp:*").split(","),
            allowed_origins=[]))

    async def run(ctx, tool, arguments, ticket_id, action, write=False):
        claims = verify_context(config, ctx.request_context.request.headers, tool, arguments)
        async with transaction(ctx.request_context.lifespan_context["engine"], settings.tenant_id) as db:
            reference = claims.get("client_reference")
            if write:
                if not reference or reference != claims.get("idempotency_key"):
                    raise ValueError("A signed operation reference is required")
                await db.execute(text("select pg_advisory_xact_lock(hashtextextended(:reference,0))"),
                                 {"reference": str(settings.tenant_id) + ":" + reference})
            ticket, scope = await authority(db, claims, ticket_id, tool, write)
            if write:
                old = (await db.execute(text(f"select * from vh_workforce_mcp_intents where tenant_id={TENANT} and client_reference=:reference"),
                                        {"reference": reference})).mappings().first()
                if old:
                    if (old["arguments_hash"], old["tool"], old["workflow_id"]) != (claims["arguments_hash"], tool, claims["workflow_id"]):
                        raise ValueError("Operation idempotency conflict")
                    return old["response"]
            result = jsonable_encoder(await action(db, ticket, scope, claims))
            if write:
                if result.get("external_job_id"):
                    await db.execute(text(f"""insert into vh_workforce_provider_jobs(tenant_id,external_job_id,client_reference,ticket_id)
                        values({TENANT},:job,:reference,:ticket)"""),
                        {"job": result["external_job_id"], "reference": reference, "ticket": ticket["id"]})
                await db.execute(text(f"""insert into vh_workforce_mcp_intents
                    (tenant_id,client_reference,workflow_id,ticket_id,tool,arguments_hash,response)
                    values({TENANT},:reference,:workflow,:ticket,:tool,:hash,cast(:response as jsonb))"""),
                    {"reference": reference, "workflow": claims["workflow_id"], "ticket": ticket["id"], "tool": tool,
                     "hash": claims["arguments_hash"], "response": json.dumps(result)})
            return result

    @server.tool(annotations=ToolAnnotations(readOnlyHint=True))
    async def get_ticket(ticket_id: str, ctx: Context) -> dict:
        """Read the bound ticket, work, plans, QC and resident completion approvals. Completed work still needs independent QC; resolved is not resident-confirmed/closed. Workflow closure is separate."""
        async def action(db, ticket, scope, claims):
            orders = [dict(x) for x in (await db.execute(text(f"select id,status,version,description,required_specialty_id,category_id from work_orders where tenant_id={TENANT} and ticket_id=:ticket order by created_at"), {"ticket": ticket["id"]})).mappings()]
            plans = [dict(x) for x in (await db.execute(text(f"select id,title,status,version,steps,estimated_amount from vh_ticket_plans where tenant_id={TENANT} and ticket_id=:ticket order by created_at"), {"ticket": ticket["id"]})).mappings()]
            qc = [dict(x) for x in (await db.execute(text(f"""select q.id,q.work_order_id,q.outcome,q.redo_required,q.checked_at
                from vh_qc_results q join work_orders w on w.id=q.work_order_id and w.tenant_id=q.tenant_id
                where w.tenant_id={TENANT} and w.ticket_id=:ticket order by q.checked_at"""), {"ticket": ticket["id"]})).mappings()]
            approvals = [dict(x) for x in (await db.execute(text(f"""select a.id,a.work_order_id,a.kind,a.status,a.request_detail
                from work_approvals a join work_orders w on w.id=a.work_order_id and w.tenant_id=a.tenant_id
                where w.tenant_id={TENANT} and w.ticket_id=:ticket and a.kind in ('customer_repair','customer_completion')"""), {"ticket": ticket["id"]})).mappings()]
            return {"ticket": {k: ticket[k] for k in ("id", "code", "status", "version", "title", "description", "category_id", "management_unit_id", "is_emergency")},
                    "work_orders": orders, "plans": plans, "qc_results": qc, "resident_approvals": approvals}
        return await run(ctx, "get_ticket", {"ticket_id": ticket_id}, ticket_id, action)

    @server.tool(annotations=ToolAnnotations(readOnlyHint=True))
    async def get_staff_availability(ticket_id: str, category_id: str, ctx: Context) -> dict:
        """Read staff in the responsible management unit. Dispatch rechecks specialty, shift, availability and load atomically."""
        async def action(db, ticket, scope, claims):
            rows = (await db.execute(text(f"""select sp.id,sp.availability,sp.max_concurrent_jobs,
                (select count(*) from work_assignments a join work_orders w on w.id=a.work_order_id and w.tenant_id=a.tenant_id
                  where a.staff_id=sp.id and a.status='accepted' and w.status not in ('completed','cancelled','rejected')) as active_jobs
                from staff_profiles sp where sp.tenant_id={TENANT} and sp.active and sp.management_unit_id=:management
                and exists(select 1 from staff_specialties ss where ss.staff_id=sp.id and ss.tenant_id=sp.tenant_id and ss.category_id=cast(:category as uuid) and ss.active)
                and exists(select 1 from staff_shifts sh where sh.staff_id=sp.id and sh.tenant_id=sp.tenant_id and sh.status='available' and sh.starts_at<=now() and sh.ends_at>now())
                order by sp.id limit 100"""), {"management": ticket["management_unit_id"], "category": category_id})).mappings()
            return {"staff": [dict(x) for x in rows]}
        return await run(ctx, "get_staff_availability", {"ticket_id": ticket_id, "category_id": category_id}, ticket_id, action)

    @server.tool(annotations=ToolAnnotations(readOnlyHint=False, idempotentHint=True))
    async def propose_plan(ticket_id: str, title: str, steps: list[dict], estimated_amount: str, ticket_version: int, ctx: Context) -> dict:
        """Propose a business plan. Management and resident approvals remain mandatory domain actions; this tool approves neither."""
        args = {"ticket_id": ticket_id, "title": title, "steps": steps, "estimated_amount": estimated_amount, "ticket_version": ticket_version}
        async def action(db, ticket, scope, claims):
            from .v3_plans import PlanCreate, propose
            plan = await propose(UUID(ticket_id), PlanCreate(**{k: v for k, v in args.items() if k != "ticket_id"}, idempotency_key=claims["client_reference"]), scope)
            return {"status": "pending", "external_job_id": "plan:" + str(plan["id"]), "plan_id": str(plan["id"]), "business_status": plan["status"]}
        return await run(ctx, "propose_plan", args, ticket_id, action, True)

    @server.tool(annotations=ToolAnnotations(readOnlyHint=False, idempotentHint=True))
    async def create_work_order(ticket_id: str, category_id: str, required_specialty_id: str, description: str, ticket_version: int, ctx: Context) -> dict:
        """Create a queued work order if Vinhomes permits it. A queued order has no accepted employee. Plan-required tickets use propose_plan first."""
        args = {"ticket_id": ticket_id, "category_id": category_id, "required_specialty_id": required_specialty_id, "description": description, "ticket_version": ticket_version}
        async def action(db, ticket, scope, claims):
            from .v3_mutations import WorkOrderCreate
            from .v3_mutations import create_work_order as create
            order = await create(UUID(ticket_id), WorkOrderCreate(**{k: v for k, v in args.items() if k != "ticket_id"}), scope)
            return {"status": "confirmed", "work_order_id": str(order["id"]), "business_status": order["status"], "version": order["version"]}
        return await run(ctx, "create_work_order", args, ticket_id, action, True)

    @server.tool(annotations=ToolAnnotations(readOnlyHint=False, idempotentHint=True))
    async def offer_assignment(ticket_id: str, work_order_id: str, staff_id: str, offer_expires_at: str, work_order_version: int, ctx: Context) -> dict:
        """Offer a work order to staff. offered does not mean accepted. Domain guards enforce all approvals, capacity, shift and specialty."""
        args = {"ticket_id": ticket_id, "work_order_id": work_order_id, "staff_id": staff_id, "offer_expires_at": offer_expires_at, "work_order_version": work_order_version}
        async def action(db, ticket, scope, claims):
            from .v3_mutations import AssignmentCreate, create_assignment
            owner = (await db.execute(text(f"select ticket_id from work_orders where tenant_id={TENANT} and id=cast(:id as uuid)"), {"id": work_order_id})).scalar()
            if owner != ticket["id"]:
                raise ValueError("Work order belongs to another ticket")
            result = await create_assignment(UUID(work_order_id), AssignmentCreate(staff_id=UUID(staff_id),
                offer_expires_at=datetime.fromisoformat(offer_expires_at), work_order_version=work_order_version), scope)
            return {"status": "offered", "external_job_id": "work_order:" + work_order_id, "assignment_id": str(result["id"]), "business_status": result["status"]}
        return await run(ctx, "offer_assignment", args, ticket_id, action, True)

    app = server.streamable_http_app()

    class ServiceAuth:
        def __init__(self, inner):
            self.inner = inner

        async def __call__(self, scope, receive, send):
            if scope["type"] == "http":
                key = dict(scope["headers"]).get(b"authorization", b"").decode("latin-1")
                if not hmac.compare_digest(key.encode(), ("Bearer " + config.mcp_service_key).encode()):
                    await send({"type": "http.response.start", "status": 401, "headers": []})
                    await send({"type": "http.response.body", "body": b"Unauthorized"})
                    return
            await self.inner(scope, receive, send)
    return ServiceAuth(app)


if __name__ == "__main__":
    import uvicorn

    from .v3_config import V3Settings
    uvicorn.run(build_mcp(V3Settings.from_env()), host=os.getenv("VINHOMES_WORKFORCE_MCP_HOST", "127.0.0.1"),
                port=int(os.getenv("VINHOMES_WORKFORCE_MCP_PORT", "8810")))
