import { technicalTools } from "../../technical-tools/catalog";
import type { TechnicalTool } from "../../technical-tools/tool";
import { forbidden } from "../../technical-tools/tools/outcomes";
import { cleaningTechnicalDependencies } from "../adapters/technical-dependencies";
import { retrieveSopInput } from "../contracts";
import { defineCleaningTool } from "../tool";

/** Every technical capability has an explicit cleaning counterpart; no business rules are copied. */
export const cleaningNames: Readonly<Record<string, string>> = {
  "technical.get_active_outage": "cleaning.get_active_outage",
  "utility_schedule.read": "cleaning.read_utility_schedule",
  "sop_kb.retrieve": "cleaning.retrieve_sop",
  "asset.read": "cleaning.read_asset",
  "sensor.read": "cleaning.read_sensor",
  "maintenance_history.read": "cleaning.read_maintenance_history",
  "technical.record_measurement": "cleaning.record_measurement",
  "technical.submit_executor_result": "cleaning.submit_executor_result",
  "technical.verify_resolution": "cleaning.verify_resolution",
  "maintenance_history.append": "cleaning.append_maintenance_history",
  "utility_isolation.request": "cleaning.request_utility_isolation",
  "area_restriction.request": "cleaning.request_area_restriction",
  "apartment_entry.request": "cleaning.request_apartment_entry",
  "vendor_dispatch.request": "cleaning.request_vendor_dispatch",
};

export function reuseTechnicalTool(source: TechnicalTool, name: string) {
  return defineCleaningTool({
    ...source,
    name,
    description: source.description
      .replaceAll("technical.verify_resolution", "cleaning.verify_resolution")
      .replaceAll("technician", "cleaning worker")
      .replaceAll("technical issue", "cleaning issue"),
    // Same schema except that the specialist's issue codes are CLEAN.* instead of TECH.*.
    inputSchema:
      source.name === "sop_kb.retrieve" ? retrieveSopInput : source.inputSchema,
    async run(context, input, deps) {
      const fields = input as Record<string, unknown>;
      if (
        source.name === "vendor_dispatch.request" &&
        typeof fields.required_specialty_code === "string" &&
        !(await deps.isCleaningSpecialty(
          context.tenant_id,
          fields.required_specialty_code,
        ))
      )
        return forbidden();
      return source.run(context, input, cleaningTechnicalDependencies(deps));
    },
  });
}

export const cleaningTechnicalTools = technicalTools.map((source) => {
  const name = cleaningNames[source.name];
  if (!name) throw new Error(`Missing cleaning counterpart for ${source.name}`);
  return reuseTechnicalTool(source, name);
});
