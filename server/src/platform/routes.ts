import { Hono } from "hono";

export function platformRoutes() {
  const routes = new Hono();
  // Liveness only. This does not report DB/runtime readiness.
  routes.get("/health", (c) =>
    c.json({ status: "ok", mode: "scaffold" } as const),
  );
  return routes;
}
