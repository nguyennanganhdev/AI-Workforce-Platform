import { Hono } from "hono";
import type { MiddlewareHandler } from "hono";
import type { AppVariables } from "../auth/guards";
import type { TicketReader } from "./tickets";

export function createTicketRoutes(
  reader: TicketReader,
  requireUser: MiddlewareHandler<{ Variables: AppVariables }>,
) {
  const app = new Hono<{ Variables: AppVariables }>();
  app.get("/tickets", requireUser, async (context) => {
    const actor = context.var.actor;
    if (actor.role !== "management" && actor.role !== "admin") {
      return context.json({ error: "Management access required." }, 403);
    }
    return context.json({
      tickets: await reader.listForManagement(actor.id, actor.role === "admin"),
    });
  });
  return app;
}
