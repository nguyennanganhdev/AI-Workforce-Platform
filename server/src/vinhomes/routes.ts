import { and, desc, eq, sql } from "drizzle-orm";
import { Hono, type MiddlewareHandler } from "hono";
import type { AppVariables } from "../auth/guards";
import type { Database } from "../db/client";
import { withDatabaseScope } from "../db/deployment-scope";
import {
  ticketAssessments,
  ticketEvents,
  ticketTriageDecisions,
  tickets,
  workApprovals,
  workAssignments,
  workOrders,
} from "../db/schema";

const uuidPattern = /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i;

function pageLimit(value: string | undefined) {
  const parsed = value === undefined ? 50 : Number(value);
  return Number.isInteger(parsed) && parsed >= 1 && parsed <= 100 ? parsed : null;
}

function pageOffset(value: string | undefined) {
  const parsed = value === undefined ? 0 : Number(value);
  return Number.isInteger(parsed) && parsed >= 0 && parsed <= 100_000 ? parsed : null;
}

/** RLS protects the tenant. This predicate enforces the actor's actual business grant. */
function visibleTicket(actor: AppVariables["actor"]) {
  if (actor.role === "admin") return eq(tickets.tenantId, sql`nullif(current_setting('app.tenant_id', true), '')::uuid`);
  return sql`exists (
    select 1 from scoped_user_roles r
    join tenant_memberships m on m.id = r.membership_id and m.tenant_id = r.tenant_id
    join access_scopes s on s.id = r.scope_id and s.tenant_id = r.tenant_id
    where m.user_id = ${actor.id} and m.status = 'active'
      and r.role_code in ('management', 'staff')
      and r.valid_from <= now() and (r.valid_to is null or r.valid_to > now())
      and r.tenant_id = ${tickets.tenantId}
      and (
        s.kind = 'tenant'
        or (s.kind = 'management' and s.management_unit_id = ${tickets.managementUnitId})
        or (s.kind = 'site' and s.site_id = ${tickets.siteId})
        or (s.kind = 'zone' and s.zone_id = ${tickets.zoneId})
        or (s.kind = 'building' and s.building_id = ${tickets.buildingId})
      )
  )`;
}

const ticketFields = {
  id: tickets.id,
  code: tickets.code,
  requestKind: tickets.requestKind,
  title: tickets.title,
  description: tickets.description,
  status: tickets.status,
  priority: tickets.priority,
  severity: tickets.severity,
  triageStatus: tickets.triageStatus,
  isEmergency: tickets.isEmergency,
  siteId: tickets.siteId,
  zoneId: tickets.zoneId,
  buildingId: tickets.buildingId,
  managementUnitId: tickets.managementUnitId,
  categoryId: tickets.categoryId,
  assignedTeamId: tickets.assignedTeamId,
  responseDueAt: tickets.responseDueAt,
  resolutionDueAt: tickets.resolutionDueAt,
  createdAt: tickets.createdAt,
  updatedAt: tickets.updatedAt,
  version: tickets.version,
};

export function createVinhomesRoutes(
  database: Database,
  tenantId: string,
  requireUser: MiddlewareHandler<{ Variables: AppVariables }>,
) {
  const app = new Hono<{ Variables: AppVariables }>();
  app.use("/*", requireUser);
  app.use("/*", async (context, next) => {
    if (context.var.actor.role === "customer") {
      return context.json({ error: "Operations access required" }, 403);
    }
    await next();
  });


  app.get("/tickets", async (context) => {
    const limit = pageLimit(context.req.query("limit"));
    const offset = pageOffset(context.req.query("offset"));
    if (limit === null) return context.json({ error: "limit must be an integer from 1 to 100" }, 400);
    if (offset === null) return context.json({ error: "offset must be an integer from 0 to 100000" }, 400);
    const actor = context.var.actor;
    const items = await withDatabaseScope(database, { tenantId, userId: actor.id }, (tx) =>
      tx.select(ticketFields).from(tickets)
        .where(visibleTicket(actor))
        .orderBy(desc(tickets.createdAt), desc(tickets.id)).limit(limit).offset(offset),
    );
    return context.json({ items, nextOffset: items.length === limit ? offset + items.length : null });
  });

  app.get("/tickets/:id", async (context) => {
    const id = context.req.param("id");
    if (!uuidPattern.test(id)) return context.json({ error: "Invalid ticket ID" }, 400);
    const actor = context.var.actor;
    const result = await withDatabaseScope(database, { tenantId, userId: actor.id }, async (tx) => {
      const [ticket] = await tx.select(ticketFields).from(tickets)
        .where(and(eq(tickets.id, id), visibleTicket(actor))).limit(1);
      if (!ticket) return null;
      const events = await tx.select({
        id: ticketEvents.id,
        seq: ticketEvents.seq,
        eventType: ticketEvents.eventType,
        fromStatus: ticketEvents.fromStatus,
        toStatus: ticketEvents.toStatus,
        occurredAt: ticketEvents.occurredAt,
        payload: ticketEvents.payload,
      }).from(ticketEvents).where(eq(ticketEvents.ticketId, id))
        .orderBy(desc(ticketEvents.seq)).limit(100);
      const orders = await tx.select().from(workOrders).where(eq(workOrders.ticketId, id))
        .orderBy(desc(workOrders.createdAt)).limit(100);
      return { ticket, events, workOrders: orders };
    });
    return result ? context.json(result) : context.json({ error: "Ticket not found" }, 404);
  });

  app.get("/tickets/:id/triage", async (context) => {
    const id = context.req.param("id");
    if (!uuidPattern.test(id)) return context.json({ error: "Invalid ticket ID" }, 400);
    const actor = context.var.actor;
    const result = await withDatabaseScope(database, { tenantId, userId: actor.id }, async (tx) => {
      const [ticket] = await tx.select({ id: tickets.id, version: tickets.version, triageStatus: tickets.triageStatus })
        .from(tickets).where(and(eq(tickets.id, id), visibleTicket(actor))).limit(1);
      if (!ticket) return null;
      const assessments = await tx.select().from(ticketAssessments)
        .where(eq(ticketAssessments.ticketId, id))
        .orderBy(desc(ticketAssessments.createdAt)).limit(100);
      const decisions = await tx.select().from(ticketTriageDecisions)
        .where(eq(ticketTriageDecisions.ticketId, id))
        .orderBy(desc(ticketTriageDecisions.createdAt)).limit(100);
      return { ticket, assessments, decisions };
    });
    return result ? context.json(result) : context.json({ error: "Ticket not found" }, 404);
  });

  app.get("/work-orders", async (context) => {
    const limit = pageLimit(context.req.query("limit"));
    const offset = pageOffset(context.req.query("offset"));
    if (limit === null) return context.json({ error: "limit must be an integer from 1 to 100" }, 400);
    if (offset === null) return context.json({ error: "offset must be an integer from 0 to 100000" }, 400);
    const ticketId = context.req.query("ticketId");
    if (ticketId && !uuidPattern.test(ticketId)) return context.json({ error: "Invalid ticket ID" }, 400);
    const actor = context.var.actor;
    const items = await withDatabaseScope(database, { tenantId, userId: actor.id }, (tx) =>
      tx.select({ workOrder: workOrders, ticketCode: tickets.code })
        .from(workOrders).innerJoin(tickets, eq(workOrders.ticketId, tickets.id))
        .where(and(visibleTicket(actor), ticketId ? eq(tickets.id, ticketId) : undefined))
        .orderBy(desc(workOrders.createdAt), desc(workOrders.id)).limit(limit).offset(offset),
    );
    return context.json({ items, nextOffset: items.length === limit ? offset + items.length : null });
  });

  app.get("/work-orders/:id", async (context) => {
    const id = context.req.param("id");
    if (!uuidPattern.test(id)) return context.json({ error: "Invalid work order ID" }, 400);
    const actor = context.var.actor;
    const result = await withDatabaseScope(database, { tenantId, userId: actor.id }, async (tx) => {
      const [row] = await tx.select({ workOrder: workOrders, ticketCode: tickets.code })
        .from(workOrders).innerJoin(tickets, eq(workOrders.ticketId, tickets.id))
        .where(and(eq(workOrders.id, id), visibleTicket(actor))).limit(1);
      if (!row) return null;
      const assignments = await tx.select().from(workAssignments)
        .where(eq(workAssignments.workOrderId, id))
        .orderBy(desc(workAssignments.createdAt)).limit(100);
      const approvals = await tx.select().from(workApprovals)
        .where(eq(workApprovals.workOrderId, id))
        .orderBy(desc(workApprovals.createdAt)).limit(100);
      return { ...row, assignments, approvals };
    });
    return result ? context.json(result) : context.json({ error: "Work order not found" }, 404);
  });

  return app;
}
