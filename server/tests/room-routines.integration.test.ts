/**
 * Schedules of management's agents, against a migrated, seeded Vinhomes database and the schedule
 * service's own role (scripts/grant_routines_role.sql).
 *
 *   ROUTINES_TEST_DATABASE_URL=postgresql://vinhomes_routines:…@127.0.0.1:5599/vinhomes_v3
 *   ROUTINES_TEST_TENANT_ID=<the seeded tenant>
 *
 * Skipped without them: the seed (a management room, a member, an agent in the room) is the business
 * API's, not this package's.
 */
import { afterAll, expect, test } from "bun:test";
import { eq } from "drizzle-orm";
import { createDatabase } from "../src/db/client";
import { routineRuns, routines, workItems } from "../src/db/schema";
import { createRoutineRoutes, sweepRoutines } from "../src/room-routines/routes";

const url = process.env.ROUTINES_TEST_DATABASE_URL;
const tenantId = process.env.ROUTINES_TEST_TENANT_ID;
const TOKEN = "t".repeat(40);
const OWNER = "local-v3-management";
const ROOM = "management-room";
const AGENT = "demo-report";
const database = url ? createDatabase(url, { max: 2, tenantId }) : null;
const headers = { authorization: `Bearer ${TOKEN}`, "content-type": "application/json" };
const made: string[] = [];

afterAll(async () => {
  if (!database) return;
  for (const id of made) {
    await database.delete(routineRuns).where(eq(routineRuns.routineId, id));
    await database.delete(routines).where(eq(routines.id, id));
  }
  await database.$client.end({ timeout: 5 });
});

test.skipIf(!database)("a schedule is kept for its owner, fires once per due minute through the business API, and is removed with its runs", async () => {
  const app = createRoutineRoutes(TOKEN, database!);
  const post = (path: string, body: unknown, auth = headers) =>
    app.request(path, { method: "POST", headers: auth, body: JSON.stringify(body) });
  const routine = { ownerUserId: OWNER, agentId: AGENT, channelId: ROOM, instruction: "Tóm tắt yêu cầu hôm qua.", cron: "0 8 * * 1-5", timezone: "Asia/Ho_Chi_Minh" };

  expect((await post("/", routine, { ...headers, authorization: "Bearer wrong" })).status).toBe(401);
  // The platform's own rules answer in sentences: too frequent, a room the owner is not in.
  const frequent = await post("/", { ...routine, cron: "*/5 * * * *" });
  expect(frequent.status).toBe(422);
  expect(((await frequent.json()) as { error: string }).error).toContain("15 minutes");
  expect((await post("/", { ...routine, ownerUserId: "local-v3-resident" })).status).toBe(422);

  const created = await post("/", routine);
  expect(created.status).toBe(201);
  const { id, nextRunAt } = (await created.json()) as { id: string; nextRunAt: string };
  made.push(id);
  // 08:00 in Ho Chi Minh City is 01:00 UTC.
  expect(new Date(nextRunAt).getUTCHours()).toBe(1);

  // Nobody else switches it off or removes it.
  expect((await post(`/${id}/enabled`, { ownerUserId: "local-v3-resident", enabled: false })).status).toBe(404);
  expect((await post(`/${id}/enabled`, { ownerUserId: OWNER, enabled: false })).status).toBe(200);
  expect((await post(`/${id}/enabled`, { ownerUserId: OWNER, enabled: true })).status).toBe(200);

  // Due now. Whole seconds, as every stamp the schedule itself writes.
  const due = new Date(Math.floor(Date.now() / 1000) * 1000 - 60_000);
  await database!.update(routines).set({ nextRunAt: due }).where(eq(routines.id, id));
  const handed: string[] = [];
  const api = (async (input: string | URL | Request, init?: RequestInit) => {
    expect((init?.headers as Record<string, string>).authorization).toBe(`Bearer ${TOKEN}`);
    handed.push(String(input));
    return Response.json({ posted: true });
  }) as typeof fetch;
  const first = await sweepRoutines(database!, "http://api.test", TOKEN, api);
  expect(first.fired).toContain(id);
  const runs = await database!.select().from(routineRuns).where(eq(routineRuns.routineId, id));
  expect(runs.length).toBe(1);
  // The run is left open: the business API closes it when the agent has answered in the room.
  expect(runs[0]!.status).toBeNull();
  expect(handed.filter((path) => path === `http://api.test/internal/routines/v1/runs/${runs[0]!.id}/fire`).length).toBe(1);
  // The clock moved on to the next weekday morning, and a second pass has nothing to fire.
  const [after] = await database!.select().from(routines).where(eq(routines.id, id));
  expect(after!.nextRunAt.getTime()).toBeGreaterThan(Date.now());
  expect((await sweepRoutines(database!, "http://api.test", TOKEN, api)).fired).not.toContain(id);

  // An API that is down is tried again later; nothing is recorded as done.
  await database!.update(routines).set({ nextRunAt: new Date(due.getTime() - 60_000) }).where(eq(routines.id, id));
  const down = (async () => new Response("no", { status: 503 })) as unknown as typeof fetch;
  const failed = await sweepRoutines(database!, "http://api.test", TOKEN, down);
  expect(failed.skipped.map((skip) => skip.routineId)).toContain(id);

  expect((await post(`/${id}/remove`, { ownerUserId: "local-v3-resident" })).status).toBe(404);
  expect((await post(`/${id}/remove`, { ownerUserId: OWNER })).status).toBe(200);
  expect((await database!.select().from(routines).where(eq(routines.id, id))).length).toBe(0);
  await database!.delete(workItems).where(eq(workItems.kind, "routine.fire"));
});
