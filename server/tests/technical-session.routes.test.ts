import { describe, expect, test } from "bun:test";
import type { VerifiedTechnicalCaller } from "../src/technical-api/routes";
import { technicalEnvelope } from "../src/technical-api/routes";
import { createSessionToolRoutes } from "../src/technical-api/session-routes";

const token = "test-only-session-tool-token-0123456789";
const run = "11111111-1111-4111-8111-111111111111";
const building = "77777777-7777-4777-8777-777777777777";
const caller: VerifiedTechnicalCaller = {
  ok: true,
  botId: "technical-agent",
  actorId: "workspace-principal",
  assertion: {
    botId: "technical-agent",
    actorId: "workspace-principal",
    runId: run,
  },
  session: true,
};

function setup(current = true) {
  const calls: { name: string; args: Record<string, unknown>; run: string }[] =
    [];
  const app = createSessionToolRoutes(
    {
      sessionCaller: async (runId) =>
        current && runId === run ? caller : null,
      call: async (who, tool, args) => {
        calls.push({ name: tool.name, args, run: who.assertion.runId });
        return {
          ...technicalEnvelope("OK", ""),
          errors: [],
          data: { outages: [] },
        };
      },
    },
    token,
  );
  const post = (body: unknown, bearer = token) =>
    app.request("/call", {
      method: "POST",
      headers: {
        authorization: `Bearer ${bearer}`,
        "content-type": "application/json",
      },
      body: JSON.stringify(body),
    });
  return { app, calls, post };
}

describe("Technical tools for a Supervisor session", () => {
  test("only the runtime's service token is accepted", async () => {
    const { app, post, calls } = setup();
    expect((await app.request("/tools")).status).toBe(401);
    expect(
      (
        await post(
          { run_id: run, tool: "technical.get_active_outage", arguments: {} },
          "x".repeat(40),
        )
      ).status,
    ).toBe(401);
    expect(calls).toHaveLength(0);
    expect(() =>
      createSessionToolRoutes(
        {
          sessionCaller: async () => null,
          call: async () => technicalEnvelope("OK", ""),
        },
        "short",
      ),
    ).toThrow();
  });

  test("the catalogue is the fourteen tools, with the name a model may use", async () => {
    const { app } = setup();
    const { tools } = await (
      await app.request("/tools", {
        headers: { authorization: `Bearer ${token}` },
      })
    ).json();
    expect(tools).toHaveLength(14);
    expect(
      tools.find(
        (tool: { name: string }) => tool.name === "technical.get_active_outage",
      ).model_name,
    ).toBe("technical__get_active_outage");
  });

  test("a read tool runs for the current run, under either spelling of its name", async () => {
    const { post, calls } = setup();
    const answer = await post({
      run_id: run,
      tool: "technical__get_active_outage",
      arguments: { building_id: building, service_type: "water" },
    });
    expect(answer.status).toBe(200);
    expect((await answer.json()).status).toBe("OK");
    expect(calls).toEqual([
      {
        name: "technical.get_active_outage",
        args: { building_id: building, service_type: "water" },
        run,
      },
    ]);
  });

  test("a run the database no longer allows is refused before the tool", async () => {
    const { post, calls } = setup(false);
    const answer = await post({
      run_id: run,
      tool: "sop_kb.retrieve",
      arguments: { building_id: building },
    });
    expect(answer.status).toBe(403);
    expect((await answer.json()).status).toBe("FORBIDDEN");
    expect(calls).toHaveLength(0);
  });

  test("tools that write or raise a request are closed to sessions", async () => {
    const { post, calls } = setup();
    for (const tool of [
      "technical.record_measurement",
      "apartment_entry.request",
    ]) {
      const answer = await post({
        run_id: run,
        tool,
        arguments: { building_id: building },
      });
      expect(answer.status).toBe(403);
    }
    expect(calls).toHaveLength(0);
  });

  test("an unknown tool and a malformed request are refused", async () => {
    const { post, calls } = setup();
    expect(
      (await post({ run_id: run, tool: "shell.exec", arguments: {} })).status,
    ).toBe(404);
    expect(
      (await post({ run_id: run, tool: "sop_kb.retrieve", arguments: [] }))
        .status,
    ).toBe(400);
    expect(
      (await post({ tool: "sop_kb.retrieve", arguments: {} })).status,
    ).toBe(400);
    expect(calls).toHaveLength(0);
  });
});
