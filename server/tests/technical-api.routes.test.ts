import { describe, expect, test } from "bun:test";
import {
  createTechnicalApiRoutes,
  technicalEnvelope,
} from "../src/technical-api/routes";
import type { VerifiedTechnicalCaller } from "../src/technical-api/routes";

const caller: VerifiedTechnicalCaller = {
  ok: true,
  botId: "demo",
  actorId: "actor",
  assertion: {
    botId: "demo",
    actorId: "actor",
    runId: "11111111-1111-4111-8111-111111111111",
  },
};
function setup(allowed = true) {
  const calls: { name: string; args: Record<string, unknown> }[] = [];
  const app = createTechnicalApiRoutes({
    authorise: async () => (allowed ? caller : null),
    refusal: async () => {},
    call: async (_caller, tool, args) => {
      calls.push({ name: tool.name, args });
      const parsed = tool.inputSchema.safeParse(args);
      return parsed.success
        ? { ...technicalEnvelope("OK", ""), errors: [], data: {} }
        : technicalEnvelope("INVALID_INPUT", "Invalid fields");
    },
  });
  return { app, calls };
}
const building = "77777777-7777-4777-8777-777777777777";
describe("Technical A2 HTTP transport", () => {
  test("catalogue exposes exactly fourteen tools behind authentication", async () => {
    expect(
      (await (await setup().app.request("/tools")).json()).tools,
    ).toHaveLength(14);
    expect((await setup(false).app.request("/tools")).status).toBe(403);
  });
  test("converts numeric query fields and nests the time range", async () => {
    const { app, calls } = setup();
    const response = await app.request(
      `/buildings/${building}/sensor-readings?sensor_id=s&metric=pressure&from=2026-10-01T00:00:00Z&to=2026-10-02T00:00:00Z&max_age_seconds=900`,
    );
    expect(response.status).toBe(200);
    expect(calls[0]?.args.max_age_seconds).toBe(900);
    expect(calls[0]?.args.time_range).toEqual({
      from: "2026-10-01T00:00:00Z",
      to: "2026-10-02T00:00:00Z",
    });
  });
  test("rejects identity injection and duplicate query fields", async () => {
    const { app } = setup();
    expect(
      (
        await app.request(
          `/buildings/${building}/assets?asset_id=p&tenant_id=${building}`,
        )
      ).status,
    ).toBe(400);
    expect(
      (await app.request(`/buildings/${building}/assets?asset_id=p&asset_id=q`))
        .status,
    ).toBe(400);
  });
  test("requires JSON and refuses overriding the path or idempotency header", async () => {
    const { app, calls } = setup();
    const path = `/buildings/${building}/utility-isolation-requests`;
    expect(
      (await app.request(path, { method: "POST", body: "{}" })).status,
    ).toBe(400);
    expect(
      (
        await app.request(path, {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ building_id: building }),
        })
      ).status,
    ).toBe(400);
    expect(calls).toHaveLength(0);
  });
  test("limits the request body before parsing JSON", async () => {
    const response = await setup().app.request(
      `/buildings/${building}/area-restriction-requests`,
      {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ reason: "x".repeat(140000) }),
      },
    );
    expect(response.status).toBe(400);
  });
});
