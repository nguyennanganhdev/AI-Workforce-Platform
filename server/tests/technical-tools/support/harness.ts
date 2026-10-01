import {
  type AuditSink,
  type Clock,
  type ContextResolver,
  createInMemoryAssetReadPort,
  createInMemoryExecutorResultStore,
  createInMemoryIdempotencyStore,
  createInMemoryMaintenanceReadPort,
  createInMemoryMaintenanceStore,
  createInMemoryMeasurementStore,
  createInMemorySensorReadPort,
  createInMemorySopProfilePort,
  createTechnicalToolCaller,
  type HostOptions,
  type IdempotencyStore,
  type ResponseEnvelope,
  responseEnvelopeSchema,
  type ToolAuditEntry,
  type ToolCaller,
  type ToolDependencies,
} from "../../../src/technical-tools";
import {
  AGENT_VERSION,
  BUILDING,
  CALLER,
  NOW,
  ROLE_OF,
  SOURCE_RUN_ID,
  TENANT,
  TRACE_ID,
  WORKSPACE,
} from "../fixtures/world";

export const fixedClock: Clock = { now: () => NOW };

/**
 * Stands in for the runtime gateway's resolver (task C06) until that exists.
 *
 * It answers what the real one will: the tenant, run and grant behind a caller the agent callback
 * route has already verified. Technical Agent A2 is granted buildings A1 and A2 and nothing else.
 */
export const CAPABILITIES = [
  "interruption:read",
  "sop:read",
  "asset:read",
  "sensor:read",
  "maintenance:read",
  "measurement:write",
  "executor_result:submit",
  "resolution:verify",
  "maintenance:append",
] as const;

export const fixtureContextResolver: ContextResolver = async (caller) => {
  const identity = {
    tenant_id: TENANT.vinhomes,
    workspace_id: WORKSPACE.vinhomes,
    principal_id: `principal:${caller.actorId}`,
    user_id: caller.actorId,
    // The business role the run acts under, which is what `document_acl` grants are written for.
    ...(ROLE_OF[caller.actorId] ? { role_code: ROLE_OF[caller.actorId] } : {}),
    source_run_id: SOURCE_RUN_ID,
    trace_id: TRACE_ID,
    agent_version: AGENT_VERSION,
    allowed_building_ids: [BUILDING.a1, BUILDING.a2],
  };
  if (caller.botId === CALLER.technicalAgent.botId) {
    return { ...identity, capabilities: [...CAPABILITIES] };
  }
  if (caller.botId === CALLER.ungrantedAgent.botId) {
    return { ...identity, capabilities: [] };
  }
  return null;
};

/**
 * A port a test did not supply.
 *
 * It throws rather than answering nothing, so a test that reaches for data it never set up fails
 * saying so, instead of passing on an empty result that looks like a real answer.
 */
function unconfigured(name: string): never {
  return {
    listCovering: () => {
      throw new Error(`This test did not configure the ${name} port.`);
    },
    listForBuilding: () => {
      throw new Error(`This test did not configure the ${name} port.`);
    },
    getWorkOrder: () => {
      throw new Error(`This test did not configure the ${name} port.`);
    },
    findEvidence: () => {
      throw new Error(`This test did not configure the ${name} port.`);
    },
  } as never;
}

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
  ports: Partial<ToolDependencies>,
  overrides: {
    contextResolver?: ContextResolver;
    audit?: AuditSink;
    idempotency?: IdempotencyStore;
    options?: HostOptions;
  } = {},
) {
  const audit = recordingAudit();
  const caller = createTechnicalToolCaller(
    {
      interruptions: ports.interruptions ?? unconfigured("interruptions"),
      sop: ports.sop ?? unconfigured("sop"),
      sopProfiles: ports.sopProfiles ?? createInMemorySopProfilePort(),
      assets: ports.assets ?? createInMemoryAssetReadPort(),
      sensors: ports.sensors ?? createInMemorySensorReadPort(),
      maintenance: ports.maintenance ?? createInMemoryMaintenanceReadPort(),
      maintenanceStore:
        ports.maintenanceStore ?? createInMemoryMaintenanceStore(),
      workOrders: ports.workOrders ?? unconfigured("workOrders"),
      measurements: ports.measurements ?? createInMemoryMeasurementStore(),
      executorResults:
        ports.executorResults ?? createInMemoryExecutorResultStore(),
      clock: ports.clock ?? fixedClock,
      contextResolver: overrides.contextResolver ?? fixtureContextResolver,
      audit: overrides.audit ?? audit.sink,
      idempotency: overrides.idempotency ?? createInMemoryIdempotencyStore(),
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
