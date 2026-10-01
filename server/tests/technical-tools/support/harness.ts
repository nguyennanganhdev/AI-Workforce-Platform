import {
  type AuditSink,
  type BuildingAccessPort,
  type Clock,
  type ContextResolver,
  createInMemoryApprovalRequestStore,
  createInMemoryAssetReadPort,
  createInMemoryExecutorResultStore,
  createInMemoryIdempotencyStore,
  createInMemoryMaintenanceReadPort,
  createInMemoryMaintenanceStore,
  createInMemoryMeasurementStore,
  createInMemoryScopeReadPort,
  createInMemorySensorReadPort,
  createInMemorySopProfilePort,
  createInMemoryVendorCatalog,
  createScopeBuildingAccess,
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
  BUILDINGS,
  CALLER,
  NOW,
  ROLE_OF,
  SCOPE,
  SCOPES,
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
 * route has already verified. Technical Agent A2 holds every capability over the scopes of
 * buildings A1 and A2, and nothing else.
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
  "utility_isolation:request",
  "area_restriction:request",
  "apartment_entry:request",
  "vendor_dispatch:request",
] as const;

/** The access scopes every capability is granted over: buildings A1 and A2. */
export const GRANTED_SCOPES = [SCOPE.buildingA1, SCOPE.buildingA2] as const;

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
  };
  if (caller.botId === CALLER.technicalAgent.botId) {
    return {
      ...identity,
      grants: CAPABILITIES.map((capability) => ({
        capability,
        scope_ids: [...GRANTED_SCOPES],
      })),
    };
  }
  if (caller.botId === CALLER.ungrantedAgent.botId) {
    return { ...identity, grants: [] };
  }
  return null;
};

/** The sample estate's buildings and scopes, for hosts with no database behind them. */
export const fixtureScopes = createInMemoryScopeReadPort(
  BUILDINGS.map((building) => ({
    tenantId: building.tenantId,
    buildingId: building.id,
    zoneId: building.zoneId,
    siteId: building.siteId,
  })),
  SCOPES.map((scope) => ({
    tenantId: scope.tenantId,
    id: scope.id,
    kind: scope.kind,
    buildingId: "buildingId" in scope ? scope.buildingId : null,
    zoneId: "zoneId" in scope ? scope.zoneId : null,
    siteId: "siteId" in scope ? scope.siteId : null,
  })),
);

/** Building access answered from the sample estate's scopes. */
export const fixtureBuildingAccess = createScopeBuildingAccess(fixtureScopes);

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
    getTicket: () => {
      throw new Error(`This test did not configure the ${name} port.`);
    },
    listWorkOrders: () => {
      throw new Error(`This test did not configure the ${name} port.`);
    },
    findUnit: () => {
      throw new Error(`This test did not configure the ${name} port.`);
    },
    residents: () => {
      throw new Error(`This test did not configure the ${name} port.`);
    },
    placement: () => {
      throw new Error(`This test did not configure the ${name} port.`);
    },
    findScopes: () => {
      throw new Error(`This test did not configure the ${name} port.`);
    },
    findOpen: () => {
      throw new Error(`This test did not configure the ${name} port.`);
    },
    createWaterIsolation: () => {
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
    buildingAccess?: BuildingAccessPort;
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
      scopes: ports.scopes ?? unconfigured("scopes"),
      isolations: ports.isolations ?? unconfigured("isolations"),
      approvalRequests:
        ports.approvalRequests ?? createInMemoryApprovalRequestStore(),
      units: ports.units ?? unconfigured("units"),
      vendors: ports.vendors ?? createInMemoryVendorCatalog(),
      executorResults:
        ports.executorResults ?? createInMemoryExecutorResultStore(),
      clock: ports.clock ?? fixedClock,
      contextResolver: overrides.contextResolver ?? fixtureContextResolver,
      audit: overrides.audit ?? audit.sink,
      idempotency: overrides.idempotency ?? createInMemoryIdempotencyStore(),
      buildingAccess: overrides.buildingAccess ?? fixtureBuildingAccess,
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
