import { z } from "zod";

const uuid = z.uuid();
const timestamp = z.iso.datetime({ offset: true });
const nonEmpty = z.string().min(1);

export const timeRangeSchema = z
  .strictObject({ from: timestamp, to: timestamp })
  .refine((value) => Date.parse(value.from) < Date.parse(value.to), {
    message: "from must be before to",
    path: ["to"],
  });

export const sopRetrieveInput = z.strictObject({
  building_id: uuid,
  issue_code: z.string().regex(/^TECH\.[A-Z]+\.[A-Z0-9_]+$/),
  query: z.string().min(3).max(1000),
  effective_at: timestamp.optional(),
  language: nonEmpty.default("vi"),
  limit: z.number().int().min(1).max(20).default(5),
});

export const assetReadInput = z
  .strictObject({
    building_id: uuid,
    asset_id: nonEmpty.optional(),
    location: z.string().min(2).max(500).optional(),
    asset_type: z.string().max(100).optional(),
  })
  .refine((value) => Boolean(value.asset_id) !== Boolean(value.location), {
    message: "Provide exactly one of asset_id or location",
    path: ["asset_id"],
  });

export const sensorReadInput = z
  .strictObject({
    building_id: uuid,
    sensor_id: nonEmpty.optional(),
    asset_id: nonEmpty.optional(),
    metric: z.string().min(1).max(100),
    time_range: timeRangeSchema,
    max_age_seconds: z.number().int().min(1).max(86400).default(900),
  })
  .refine((value) => Boolean(value.sensor_id) !== Boolean(value.asset_id), {
    message: "Provide exactly one of sensor_id or asset_id",
    path: ["sensor_id"],
  });

export const maintenanceReadInput = z.strictObject({
  building_id: uuid,
  asset_id: nonEmpty,
  time_range: timeRangeSchema,
  limit: z.number().int().min(1).max(100).default(20),
});

export const outageInput = z.strictObject({
  building_id: uuid,
  service_type: z.enum(["water", "power"]),
  occurred_at: timestamp,
});

export const scheduleInput = z.strictObject({
  building_id: uuid,
  utility_type: z.enum(["water", "power"]),
  time_range: timeRangeSchema,
});

export const maintenanceAppendInput = z.strictObject({
  building_id: uuid,
  asset_id: nonEmpty,
  workorder_id: uuid,
  verified_result_id: nonEmpty,
  outcome: z.string().min(1).max(4000),
  source_refs: z
    .array(nonEmpty)
    .min(1)
    .refine(
      (items) => new Set(items).size === items.length,
      "source_refs must be unique",
    ),
  occurred_at: timestamp.optional(),
  supersedes_event_id: nonEmpty.optional(),
  idempotency_key: z.string().min(8).max(128),
});

export const sopRetrieveOutput = z.strictObject({
  documents: z.array(
    z.strictObject({
      document_id: uuid,
      code: z.string(),
      title: z.string(),
      version_no: z.number().int().min(1),
      effective_from: timestamp,
      effective_to: timestamp.nullable().optional(),
      excerpt: z.string().optional(),
      acceptance_criteria: z.array(z.string()),
      source_refs: z.array(z.string()),
    }),
  ),
});

export const assetReadOutput = z.strictObject({
  assets: z.array(
    z.strictObject({
      asset_id: z.string(),
      type: z.string(),
      model: z.string().nullable().optional(),
      location: z.string(),
      ownership: z.string().nullable().optional(),
      warranty_until: z.iso.date().nullable().optional(),
      status: z.string(),
      updated_at: timestamp,
    }),
  ),
});

export const sensorReadOutput = z.strictObject({
  freshness: z.enum(["fresh", "stale", "unknown"]),
  readings: z.array(
    z.strictObject({
      sensor_id: z.string(),
      asset_id: z.string().nullable().optional(),
      metric: z.string(),
      value: z.number(),
      unit: z.string(),
      observed_at: timestamp,
      quality: z.enum(["good", "uncertain", "bad", "unknown"]),
    }),
  ),
});

export const maintenanceReadOutput = z.strictObject({
  events: z.array(
    z.strictObject({
      event_id: z.string(),
      asset_id: z.string(),
      incident_id: z.string().nullable().optional(),
      workorder_id: z.string().nullable().optional(),
      occurred_at: timestamp,
      outcome: z.string(),
      source_refs: z.array(z.string()),
    }),
  ),
  last_maintenance_at: timestamp.nullable().optional(),
  repeat_count: z.number().int().min(0),
});

export const outageOutput = z.strictObject({
  outages: z.array(
    z.strictObject({
      outage_id: uuid,
      service_type: z.enum(["water", "power"]),
      status: z.enum(["approved", "notified", "active", "restored"]),
      scope_ids: z.array(uuid),
      started_at: timestamp,
      ended_at: timestamp.nullable().optional(),
      published_eta: timestamp.nullable().optional(),
    }),
  ),
});

export const scheduleOutput = z.strictObject({
  schedules: z.array(
    z.strictObject({
      schedule_id: uuid,
      utility_type: z.enum(["water", "power"]),
      status: z.enum(["approved", "notified", "active", "restored"]),
      planned_start: timestamp,
      planned_end: timestamp,
      scope_ids: z.array(uuid),
    }),
  ),
});

export const maintenanceAppendOutput = z.strictObject({
  maintenance_event_id: z.string(),
  created_at: timestamp,
  revision: z.number().int().min(1),
  supersedes_event_id: z.string().nullable().optional(),
});

export const toolSchemas = {
  "sop_kb.retrieve": { input: sopRetrieveInput, output: sopRetrieveOutput },
  "asset.read": { input: assetReadInput, output: assetReadOutput },
  "sensor.read": { input: sensorReadInput, output: sensorReadOutput },
  "maintenance_history.read": {
    input: maintenanceReadInput,
    output: maintenanceReadOutput,
  },
  "technical.get_active_outage": { input: outageInput, output: outageOutput },
  "utility_schedule.read": { input: scheduleInput, output: scheduleOutput },
  "maintenance_history.append": {
    input: maintenanceAppendInput,
    output: maintenanceAppendOutput,
  },
} as const;

export type TechnicalToolName = keyof typeof toolSchemas;
