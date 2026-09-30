import {
  type AuditSink,
  type Clock,
  type ContextResolver,
  createTechnicalToolCaller,
  type HostOptions,
  type InterruptionReadPort,
  type ResponseEnvelope,
  responseEnvelopeSchema,
  type ToolAuditEntry,
  type ToolCaller,
} from "../../../src/technical-tools";
import {
  AGENT_VERSION,
  BUILDING,
  CALLER,
  NOW,
  SOURCE_RUN_ID,
  TENANT,
  TRACE_ID,
} from "../fixtures/world";

export const fixedClock: Clock = { now: () => NOW };

/**
 * Stands in for the runtime gateway's resolver (task C06) until that exists.
 *
 * It answers what the real one will: the tenant, run and grant behind a caller the agent callback
 * route has already verified. Technical Agent A2 is granted buildings A1 and A2 and nothing else.
 */
export const fixtureContextResolver: ContextResolver = async (caller) => {
  const identity = {
    tenant_id: TENANT.vinhomes,
    principal_id: `principal:${caller.actorId}`,
    source_run_id: SOURCE_RUN_ID,
    trace_id: TRACE_ID,
    agent_version: AGENT_VERSION,
    allowed_building_ids: [BUILDING.a1, BUILDING.a2],
  };
  if (caller.botId === CALLER.technicalAgent.botId) {
    return { ...identity, capabilities: ["interruption:read"] };
  }
  if (caller.botId === CALLER.ungrantedAgent.botId) {
    return { ...identity, capabilities: [] };
  }
  return null;
};

export function recordingAudit() {
  const entries: ToolAuditEntry[] = [];
  const sink: AuditSink = {
    record: async (entry) => {
      entries.push(entry);
    },
  };
  return { entries, sink };
}

/**
 * The technical tools as the server would mount them, with every call's answer parsed back out.
 *
 * `call` goes through `createTechnicalToolCaller`, the function `/api/agent-tools/call` is handed,
 * so a test exercises the same path a Bot's tool call takes after the route has verified it.
 */
export function technicalToolHarness(
  interruptions: InterruptionReadPort,
  overrides: {
    contextResolver?: ContextResolver;
    audit?: AuditSink;
    options?: HostOptions;
  } = {},
) {
  const audit = recordingAudit();
  const caller = createTechnicalToolCaller(
    {
      interruptions,
      clock: fixedClock,
      contextResolver: overrides.contextResolver ?? fixtureContextResolver,
      audit: overrides.audit ?? audit.sink,
    },
    overrides.options,
  );

  async function call(
    name: string,
    args: Record<string, unknown>,
    as: ToolCaller = CALLER.technicalAgent,
  ) {
    const answer = await caller({ name, args, ...as });
    if (!answer) throw new Error(`${name} is not a technical tool.`);
    // Every answer must be a valid envelope, so a malformed one fails here rather than in a test
    // that happened to look at the broken field.
    const envelope: ResponseEnvelope = responseEnvelopeSchema.parse(
      JSON.parse(answer.text),
    );
    return { ...answer, envelope };
  }

  return { caller, call, auditEntries: audit.entries };
}
