import type { BuildingAccessPort, ExecutionContext } from "./context";
import type { MaintenancePort } from "./ports";
import { runTechnicalTool } from "./runner";

/** Host binds an authorized, durable port before enabling the write tool in production. */
export function createTechnicalWriteTools(
  access: BuildingAccessPort,
  maintenance: MaintenancePort,
) {
  return {
    maintenanceAppend: (input: unknown, context: ExecutionContext) =>
      runTechnicalTool(
        "maintenance_history.append",
        input,
        context,
        access,
        (parsed, trusted) => maintenance.appendVerified(trusted, parsed),
      ),
  };
}
