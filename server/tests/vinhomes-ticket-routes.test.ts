import { describe, expect, test } from "bun:test";
import { Hono, type MiddlewareHandler } from "hono";
import type { AppVariables } from "../src/auth/guards";
import { createTicketRoutes } from "../src/business/ticket-routes";
import type { TicketReader } from "../src/business/tickets";

const reader: TicketReader = {
  async listForManagement(userId, isPlatformAdmin) {
    return [
      {
        id: "ticket-1",
        code: `${userId}-${isPlatformAdmin}`,
        title: "Rò rỉ nước",
        status: "new",
        priority: null,
        severity: "unknown",
        triageStatus: "pending",
        createdAt: "2026-09-30T00:00:00.000Z",
      },
    ];
  },
};

function appFor(role?: AppVariables["actor"]["role"]) {
  const authenticate: MiddlewareHandler<{ Variables: AppVariables }> = async (
    context,
    next,
  ) => {
    if (!role) return context.json({ error: "Authentication required." }, 401);
    context.set("actor", { id: "user-1", email: "user@example.test", role });
    await next();
  };
  return new Hono().route(
    "/api/vinhomes",
    createTicketRoutes(reader, authenticate),
  );
}

describe("Vinhomes ticket list", () => {
  test("requires a session and a management role", async () => {
    expect((await appFor().request("/api/vinhomes/tickets")).status).toBe(401);
    expect(
      (await appFor("staff").request("/api/vinhomes/tickets")).status,
    ).toBe(403);
    expect(
      (await appFor("customer").request("/api/vinhomes/tickets")).status,
    ).toBe(403);
  });

  test("passes the authenticated actor to the scoped reader", async () => {
    const management = await appFor("management").request(
      "/api/vinhomes/tickets",
    );
    expect(management.status).toBe(200);
    expect((await management.json()).tickets[0].code).toBe("user-1-false");

    const admin = await appFor("admin").request("/api/vinhomes/tickets");
    expect(admin.status).toBe(200);
    expect((await admin.json()).tickets[0].code).toBe("user-1-true");
  });
});
