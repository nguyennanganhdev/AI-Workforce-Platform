import type { BuildingAccessPort, ExecutionContext } from "./context";
import type {
  AssetPort,
  InterruptionPort,
  MaintenancePort,
  SensorPort,
  SopPort,
} from "./ports";
import { runTechnicalTool } from "./runner";

/** Host binds production or POC ports and passes authenticated context per call. */
export function createTechnicalReadTools(
  access: BuildingAccessPort,
  ports: {
    asset: AssetPort;
    sensor: SensorPort;
    maintenance: Pick<MaintenancePort, "read">;
    interruption?: InterruptionPort;
    sop?: SopPort;
  },
) {
  return {
    sopRetrieve: (input: unknown, context: ExecutionContext) =>
      runTechnicalTool(
        "sop_kb.retrieve",
        input,
        context,
        access,
        (parsed, trusted) => {
          if (!ports.sop) throw new Error("SOP port is not configured.");
          return ports.sop.retrieve(trusted, parsed);
        },
      ),
    assetRead: (input: unknown, context: ExecutionContext) =>
      runTechnicalTool(
        "asset.read",
        input,
        context,
        access,
        (parsed, trusted) => ports.asset.read(trusted, parsed),
      ),
    sensorRead: (input: unknown, context: ExecutionContext) =>
      runTechnicalTool(
        "sensor.read",
        input,
        context,
        access,
        (parsed, trusted) => ports.sensor.read(trusted, parsed),
      ),
    maintenanceRead: (input: unknown, context: ExecutionContext) =>
      runTechnicalTool(
        "maintenance_history.read",
        input,
        context,
        access,
        (parsed, trusted) => ports.maintenance.read(trusted, parsed),
      ),
    getActiveOutage: (input: unknown, context: ExecutionContext) =>
      runTechnicalTool(
        "technical.get_active_outage",
        input,
        context,
        access,
        (parsed, trusted) => {
          if (!ports.interruption)
            throw new Error("Interruption port is not configured.");
          return ports.interruption.getActiveOutages(trusted, parsed);
        },
      ),
    utilityScheduleRead: (input: unknown, context: ExecutionContext) =>
      runTechnicalTool(
        "utility_schedule.read",
        input,
        context,
        access,
        (parsed, trusted) => {
          if (!ports.interruption)
            throw new Error("Interruption port is not configured.");
          return ports.interruption.readSchedule(trusted, parsed);
        },
      ),
  };
}
