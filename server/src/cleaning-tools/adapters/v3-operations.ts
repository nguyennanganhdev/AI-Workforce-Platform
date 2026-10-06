import { z } from "zod";
import type { ToolContext } from "../../technical-tools/contracts/context";
import type { ToolOutcome } from "../../technical-tools/tool";
import {
  conflict,
  forbidden,
  notFound,
  provenanceOf,
} from "../../technical-tools/tools/outcomes";
import {
  createWorkInput,
  dispatchInput,
  listStaffInput,
  readWorkInput,
  updateStatusInput,
} from "../contracts";
import {
  CleaningBackendError,
  type CleaningBackend,
  type BackendRequest,
} from "../ports/backend";
import type { CleaningOperations } from "../ports/operations";

const id = z.uuid();
const date = z.iso.datetime({ offset: true }).nullable();
const category = z.object({ id, parent_id: id.nullable(), code: z.string() });
const catalogSchema = z.object({
  serviceCategories: z.array(category),
  buildings: z.array(z.object({ id, site_id: id })),
  sites: z.array(z.object({ id, domain_id: id })),
});
const orderSchema = z.object({
  id,
  ticket_id: id,
  category_id: id,
  required_specialty_id: id,
  description: z.string(),
  status: z.string(),
  version: z.number().int().nonnegative(),
});
const assignmentSchema = z.object({
  id,
  staff_id: id,
  status: z.string(),
  eta_at: date,
  accepted_at: date,
});
const ticketSchema = z.object({
  id,
  building_id: id,
  management_unit_id: id,
  version: z.number().int().nonnegative(),
});
const ticketDetailSchema = z.object({
  ticket: ticketSchema,
  workOrders: z.array(orderSchema),
  events: z.array(
    z.object({
      id,
      event_type: z.string(),
      occurred_at: z.iso.datetime({ offset: true }),
      from_status: z.string().nullable(),
      to_status: z.string().nullable(),
    }),
  ),
});
const detailSchema = z.object({
  workOrder: orderSchema,
  assignments: z.array(assignmentSchema),
});
const staffSchema = z.object({
  id,
  employee_code: z.string(),
  management_unit_id: id,
  active_jobs: z.coerce.number().int().nonnegative(),
  max_concurrent_jobs: z.number().int().nonnegative(),
});

/** Calls the existing work-order services. This adapter never reimplements their state machine. */
export function createV3CleaningOperations(
  backend: CleaningBackend,
): CleaningOperations {
  const request = (context: ToolContext, r: BackendRequest) =>
    backend.request(context, r);

  async function catalogue(context: ToolContext, buildingId: string) {
    const catalog = catalogSchema.parse(
      await request(context, { method: "GET", path: "/catalogs" }),
    );
    const roots = catalog.serviceCategories.filter(
      (c) => c.code === "cleaning",
    );
    if (roots.length !== 1) throw new CleaningBackendError(404);
    const root = roots[0]!;
    const categories = new Set([root.id]);
    // Descendants inherit cleaning scope, but arbitrary categories never do.
    let changed = true;
    while (changed) {
      changed = false;
      for (const c of catalog.serviceCategories) {
        if (
          c.parent_id &&
          categories.has(c.parent_id) &&
          !categories.has(c.id)
        ) {
          categories.add(c.id);
          changed = true;
        }
      }
    }
    const building = catalog.buildings.find((b) => b.id === buildingId);
    const site = catalog.sites.find((s) => s.id === building?.site_id);
    if (!site) throw new CleaningBackendError(404);
    const coverage = z.object({ managementUnitId: id }).parse(
      await request(context, {
        method: "GET",
        path: "/management-units/resolve",
        query: {
          buildingId,
          domainId: site.domain_id,
          serviceCategoryId: root.id,
        },
      }),
    );
    return { root, categories, managementId: coverage.managementUnitId };
  }

  async function ticket(
    context: ToolContext,
    ticketId: string,
    buildingId: string,
    managementId: string,
  ) {
    const detail = ticketDetailSchema.parse(
      await request(context, { method: "GET", path: `/tickets/${ticketId}` }),
    );
    if (
      detail.ticket.building_id !== buildingId ||
      detail.ticket.management_unit_id !== managementId
    )
      throw new CleaningBackendError(403);
    return detail;
  }

  async function work(
    context: ToolContext,
    workId: string,
    buildingId: string,
    scope: Awaited<ReturnType<typeof catalogue>>,
  ) {
    const detail = detailSchema.parse(
      await request(context, { method: "GET", path: `/work-orders/${workId}` }),
    );
    if (!scope.categories.has(detail.workOrder.category_id))
      throw new CleaningBackendError(403);
    const t = await ticket(
      context,
      detail.workOrder.ticket_id,
      buildingId,
      scope.managementId,
    );
    return { detail, ticket: t };
  }

  async function staff(
    context: ToolContext,
    managementId: string,
    categoryId: string,
  ) {
    return z
      .object({ items: z.array(staffSchema) })
      .parse(
        await request(context, {
          method: "GET",
          path: "/staff/available",
          query: { managementUnitId: managementId, categoryId },
        }),
      )
      .items.filter(
        (s) =>
          s.management_unit_id === managementId &&
          s.active_jobs < s.max_concurrent_jobs,
      );
  }

  return {
    async execute(context, operation, args): Promise<ToolOutcome<unknown>> {
      try {
        const buildingId = id.parse(args.building_id);
        const scope = await catalogue(context, buildingId);
        let data: unknown;
        let sourceId = buildingId;

        if (operation === "list_available_staff") {
          const input = listStaffInput.parse(args);
          const existing = input.work_order_id
            ? await work(context, input.work_order_id, buildingId, scope)
            : null;
          let all = await staff(
            context,
            scope.managementId,
            existing?.detail.workOrder.category_id ?? scope.root.id,
          );
          if (
            existing &&
            existing.detail.workOrder.required_specialty_id !==
              existing.detail.workOrder.category_id
          ) {
            const specialists = new Set(
              (
                await staff(
                  context,
                  scope.managementId,
                  existing.detail.workOrder.required_specialty_id,
                )
              ).map((s) => s.id),
            );
            all = all.filter((s) => specialists.has(s.id));
          }
          const page = all.slice(input.offset, input.offset + input.limit);
          data = {
            staff: page.map((s) => ({
              staff_id: s.id,
              employee_code: s.employee_code,
              management_unit_id: s.management_unit_id,
              active_jobs: s.active_jobs,
              max_concurrent_jobs: s.max_concurrent_jobs,
            })),
            next_offset:
              input.offset + page.length < all.length
                ? input.offset + page.length
                : null,
          };
        } else if (operation === "read_work_order") {
          const input = readWorkInput.parse(args);
          const existing = input.work_order_id
            ? await work(context, input.work_order_id, buildingId, scope)
            : null;
          const t =
            existing?.ticket ??
            (await ticket(
              context,
              input.ticket_id!,
              buildingId,
              scope.managementId,
            ));
          const all = existing
            ? [existing.detail.workOrder]
            : t.workOrders.filter((w) => scope.categories.has(w.category_id));
          const page = all.slice(input.offset, input.offset + input.limit);
          const details = await Promise.all(
            page.map(
              async (w) =>
                existing?.detail ??
                (await work(context, w.id, buildingId, scope)).detail,
            ),
          );
          // Only work events explicitly linked to cleaning work are returned; ticket-wide history
          // can contain technical assignments or other information outside this tool's purpose.
          const history =
            input.include_history && page.length
              ? z
                  .object({
                    items: z.array(
                      z.object({
                        id,
                        event_type: z.string(),
                        occurred_at: z.iso.datetime({ offset: true }),
                        from_status: z.string().nullable(),
                        to_status: z.string().nullable(),
                        payload: z.record(z.string(), z.unknown()),
                      }),
                    ),
                  })
                  .parse(
                    await request(context, {
                      method: "GET",
                      path: `/tickets/${t.ticket.id}/timeline`,
                    }),
                  )
                  .items.filter((e) =>
                    page.some((w) => w.id === e.payload.workOrderId),
                  )
                  .slice(input.offset, input.offset + input.limit)
                  .map(({ payload: _payload, ...e }) => e)
              : [];
          data = {
            ticket_id: t.ticket.id,
            ticket_version: t.ticket.version,
            work_orders: details.map(({ workOrder: w, assignments }) => ({
              work_order_id: w.id,
              ticket_id: w.ticket_id,
              category_id: w.category_id,
              description: w.description,
              status: w.status,
              version: w.version,
              assignments: assignments.map((a) => ({
                assignment_id: a.id,
                staff_id: a.staff_id,
                status: a.status,
                accepted_at: a.accepted_at,
                eta_at: a.eta_at,
              })),
            })),
            history,
            next_offset:
              input.offset + page.length < all.length
                ? input.offset + page.length
                : null,
          };
          sourceId = t.ticket.id;
        } else if (operation === "create_work_order") {
          const input = createWorkInput.parse(args);
          if (
            context.role_code !== "management" &&
            context.role_code !== "admin"
          )
            return forbidden();
          if (!scope.categories.has(input.required_specialty_id))
            return forbidden();
          await ticket(
            context,
            input.ticket_id,
            buildingId,
            scope.managementId,
          );
          const result = z
            .object({
              id,
              ticket_id: id,
              status: z.string(),
              version: z.number().int(),
            })
            .parse(
              await request(context, {
                method: "POST",
                path: `/tickets/${input.ticket_id}/work-orders`,
                idempotencyKey: input.idempotency_key,
                body: {
                  category_id: scope.root.id,
                  required_specialty_id: input.required_specialty_id,
                  description: input.description,
                  ticket_version: input.ticket_version,
                },
              }),
            );
          data = {
            work_order_id: result.id,
            ticket_id: result.ticket_id,
            status: result.status,
            version: result.version,
          };
          sourceId = result.id;
        } else if (operation === "dispatch_staff") {
          const input = dispatchInput.parse(args);
          if (
            context.role_code !== "management" &&
            context.role_code !== "admin"
          )
            return forbidden();
          const w = await work(context, input.work_order_id, buildingId, scope);
          if (w.detail.workOrder.version !== input.expected_version)
            return conflict(["Work version changed."], "expected_version");
          if (
            Date.parse(input.offer_expires_at) <=
            Date.parse(context.received_at)
          )
            return conflict(
              ["Offer must expire in the future."],
              "offer_expires_at",
            );
          const candidates = await staff(
            context,
            scope.managementId,
            w.detail.workOrder.category_id,
          );
          if (!candidates.some((s) => s.id === input.staff_id))
            return forbidden();
          if (
            w.detail.workOrder.required_specialty_id !==
              w.detail.workOrder.category_id &&
            !(
              await staff(
                context,
                scope.managementId,
                w.detail.workOrder.required_specialty_id,
              )
            ).some((s) => s.id === input.staff_id)
          )
            return forbidden();
          const a = z
            .object({
              id,
              work_order_id: id,
              staff_id: id,
              status: z.literal("offered"),
            })
            .parse(
              await request(context, {
                method: "POST",
                path: `/work-orders/${input.work_order_id}/assignments`,
                idempotencyKey: input.idempotency_key,
                body: {
                  staff_id: input.staff_id,
                  work_order_version: input.expected_version,
                  offer_expires_at: input.offer_expires_at,
                },
              }),
            );
          data = {
            assignment_id: a.id,
            work_order_id: a.work_order_id,
            staff_id: a.staff_id,
            assignment_status: a.status,
            work_order_status: "offered",
            version: input.expected_version + 1,
          };
          sourceId = a.id;
        } else {
          const input = updateStatusInput.parse(args);
          const w = await work(context, input.work_order_id, buildingId, scope);
          const a = w.detail.assignments.find(
            (a) => a.id === input.assignment_id,
          );
          if (!a || a.status !== "accepted")
            return conflict(["Accepted assignment required."], "assignment_id");
          // Existing V3 transition endpoint verifies the caller is the assigned worker/admin,
          // resident consent, state machine, and completion evidence under its own locks.
          const result = z
            .object({ id, status: z.string(), version: z.number().int() })
            .parse(
              await request(context, {
                method: "PATCH",
                path: `/work-orders/${input.work_order_id}/status`,
                idempotencyKey: input.idempotency_key,
                body: {
                  version: input.expected_version,
                  status: input.status,
                  note: input.note,
                },
              }),
            );
          data = {
            work_order_id: result.id,
            assignment_id: a.id,
            staff_id: a.staff_id,
            status: result.status,
            version: result.version,
          };
          sourceId = result.id;
        }
        return {
          status: "OK",
          data,
          provenance: provenanceOf(
            [{ id: sourceId }],
            context.received_at,
            "business_api",
          ),
        };
      } catch (error) {
        if (!(error instanceof CleaningBackendError)) throw error;
        if (error.status === 401 || error.status === 403) return forbidden();
        if (error.status === 404)
          return notFound("No cleaning resource is available in this scope.");
        if (error.status === 409)
          return conflict(
            ["Work state or approval changed; reload before continuing."],
            "work_order_id",
          );
        if (error.status === 400 || error.status === 422)
          return {
            status: "INVALID_INPUT",
            data: null,
            errors: [
              {
                code: "INVALID_INPUT",
                message: "Backend rejected the business input.",
                retryable: false,
              },
            ],
          };
        throw error;
      }
    },
  };
}
