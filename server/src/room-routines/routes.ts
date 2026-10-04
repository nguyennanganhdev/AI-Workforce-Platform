import { timingSafeEqual } from "node:crypto";
import { and, eq, inArray } from "drizzle-orm";
import { Hono } from "hono";
import { workOwner } from "../../../shared/work-owner";
import type { Database } from "../db/client";
import { routineRuns, routines } from "../db/schema";
import {
  createRoutineStore,
  RoutineNotFoundError,
  RoutineRefusedError,
} from "../routines/store";
import {
  dispatchClaimedRoutines,
  offerDueRoutines,
  ROUTINE_FIRE_KIND,
} from "../routines/sweep";
import { repeatAfterEach, type Repeating } from "../work/loop";
import { createWorkQueue } from "../work/queue";

function sameToken(expected: string, offered: string): boolean {
  const a = Buffer.from(expected);
  const b = Buffer.from(offered);
  return a.length === b.length && timingSafeEqual(a, b);
}

/**
 * Schedules for management's agents: "every weekday at 08:00, ask the report agent for yesterday's
 * numbers in our room".
 *
 * The platform's own routine store and sweep do the work (routines/store.ts, routines/sweep.ts,
 * work/queue.ts): the floor of fifteen minutes, the cap per person, one firing per due minute. What
 * is different here is how a firing runs. The platform runs a turn through its own runtime
 * (routines/run-turn.ts); this deployment has no such runtime, so a firing is handed to the business
 * API, which posts the instruction in the room as its owner, mentioning the agent. The Supervisor
 * answers that mention like any other, and the API closes the run with what became of it.
 *
 * The business API decides who may schedule what and names the owner; this service only keeps the
 * schedule. The database passed in must name the tenant on its connection: the store writes no
 * tenant of its own.
 *
 * Its own service and database role (serve.ts), not the technical tool host's: that host refuses to
 * work under a role that may update or delete, and a schedule is updated on every firing.
 */
export function createRoutineRoutes(serviceToken: string, database: Database) {
  const store = createRoutineStore(database);
  const app = new Hono();
  app.use("*", async (c, next) => {
    c.header("Cache-Control", "no-store");
    const offered = c.req.header("authorization") ?? "";
    if (
      !offered.startsWith("Bearer ") ||
      !sameToken(serviceToken, offered.slice(7))
    )
      return c.json({ error: "Invalid service credential." }, 401);
    await next();
  });

  /** The store's refusals are sentences (a schedule too frequent, the cap, a room not shared). */
  const answer = async (work: () => Promise<Response>) => {
    try {
      return await work();
    } catch (error) {
      if (error instanceof RoutineRefusedError)
        return Response.json({ error: error.message }, { status: 422 });
      if (error instanceof RoutineNotFoundError)
        return Response.json({ error: error.message }, { status: 404 });
      throw error;
    }
  };
  const named = (body: Record<string, unknown>, ...fields: string[]) =>
    fields.every((field) => typeof body[field] === "string" && body[field]);

  app.post("/", async (c) => {
    const body = await c.req.json().catch(() => ({}));
    if (!named(body, "ownerUserId", "agentId", "channelId", "instruction", "cron", "timezone"))
      return c.json({ error: "A routine needs an owner, an agent, a room, an instruction, a schedule and a timezone." }, 422);
    return answer(async () => {
      const made = await store.create({
        ownerUserId: body.ownerUserId,
        agentId: body.agentId,
        channelId: body.channelId,
        instruction: body.instruction,
        cron: body.cron,
        timezone: body.timezone,
      });
      return Response.json({ id: made.id, nextRunAt: made.nextRunAt }, { status: 201 });
    });
  });
  app.post("/:id/enabled", async (c) => {
    const body = await c.req.json().catch(() => ({}));
    if (!named(body, "ownerUserId") || typeof body.enabled !== "boolean")
      return c.json({ error: "An owner and enabled (true or false) are required." }, 422);
    return answer(async () => {
      await store.setEnabled(body.ownerUserId, c.req.param("id"), body.enabled);
      return Response.json({ ok: true });
    });
  });
  app.post("/:id/update", async (c) => {
    const body = await c.req.json().catch(() => ({}));
    if (!named(body, "ownerUserId", "instruction", "cron"))
      return c.json({ error: "An owner, an instruction and a schedule are required." }, 422);
    return answer(async () => {
      // The store recomputes the next run from the new schedule, in the routine's own timezone.
      const changed = await store.update(body.ownerUserId, c.req.param("id"), {
        instruction: body.instruction,
        cron: body.cron,
      });
      return Response.json({ id: changed.id, nextRunAt: changed.nextRunAt });
    });
  });
  app.post("/:id/remove", async (c) => {
    const body = await c.req.json().catch(() => ({}));
    if (!named(body, "ownerUserId"))
      return c.json({ error: "An owner is required." }, 422);
    return answer(async () => {
      // In this schema a routine's runs do not go with it, so they are removed first, and only for
      // a routine this owner has.
      await database.delete(routineRuns).where(
        inArray(
          routineRuns.routineId,
          database
            .select({ id: routines.id })
            .from(routines)
            .where(and(eq(routines.id, c.req.param("id")), eq(routines.ownerUserId, body.ownerUserId))),
        ),
      );
      await store.remove(body.ownerUserId, c.req.param("id"));
      return Response.json({ ok: true });
    });
  });
  return app;
}

/** As the platform's own runner (routines/runner.ts): ten failed firings in a row switch a routine off. */
const FATIGUE_LIMIT = 10;
const SWITCHED_OFF = "Đã tắt lịch này sau 10 lần chạy lỗi liên tiếp.";

/**
 * One pass: what is due is offered, what this process can claim is handed to the business API.
 * Returns what the pass did, for the log and for tests.
 */
export async function sweepRoutines(
  database: Database,
  /** The business API's origin, e.g. http://api:8000. */
  apiUrl: string,
  serviceToken: string,
  send: typeof fetch = fetch,
) {
  const routineStore = createRoutineStore(database);
  const queue = createWorkQueue(database);
  const dispatch = async (runId: string) => {
    const run = await routineStore.runContext(runId);
    if (!run) return;
    if ((await routineStore.consecutiveFailures(run.routineId)) >= FATIGUE_LIMIT) {
      await routineStore.finishRun(runId, "skipped", SWITCHED_OFF);
      await routineStore.markUnschedulable(run.routineId, SWITCHED_OFF);
      return;
    }
    const reply = await send(
      `${apiUrl}/internal/routines/v1/runs/${encodeURIComponent(runId)}/fire`,
      {
        method: "POST",
        headers: { authorization: `Bearer ${serviceToken}` },
        signal: AbortSignal.timeout(30_000),
      },
    );
    // Accepted: the API posted the mention, or closed the run itself with the reason it could not.
    if (reply.ok) return;
    // Anything else may work next time; the queue retries, and a run nobody closes is reaped as skipped.
    throw new Error(`the business API answered ${reply.status} when handed a routine run`);
  };
  const options = { routineStore, queue, dispatch, owner: workOwner("routines") };
  const { offered } = await offerDueRoutines(options);
  const report = await dispatchClaimedRoutines(options);
  // A finished item is what stops its minute being fired twice; a day is long enough for that.
  await queue.purge({ kind: ROUTINE_FIRE_KIND, olderThanMs: 24 * 60 * 60 * 1000 });
  return { offered, fired: report.fired, skipped: report.skipped };
}

/** Sweep once a minute for as long as this process runs. One pass at a time (work/loop.ts). */
export function startRoutineSweeps(
  database: Database,
  apiUrl: string,
  serviceToken: string,
): Repeating {
  return repeatAfterEach(async () => {
    try {
      const pass = await sweepRoutines(database, apiUrl, serviceToken);
      if (pass.offered.length || pass.fired.length || pass.skipped.length)
        console.info(JSON.stringify({ type: "routine-sweep", ...pass }));
    } catch (error) {
      console.error(JSON.stringify({ type: "routine-sweep-failed", reason: String(error) }));
    }
  }, 60_000);
}
