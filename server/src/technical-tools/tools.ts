import type { BuildingAccessPort, ExecutionContext } from "./context";
import type {
  AssetPort,
  InterruptionPort,
  MaintenancePort,
  SensorPort,
  SopPort,
} from "./ports";
import { createTechnicalReadTools } from "./read-tools";
import { createTechnicalWriteTools } from "./write-tools";

/** All seven handlers, ready for Chiến to register at the authenticated tool gateway. */
export function createSevenTechnicalTools(
  access: BuildingAccessPort,
  ports: {
    sop: SopPort;
    asset: AssetPort;
    sensor: SensorPort;
    maintenance: MaintenancePort;
    interruption: InterruptionPort;
  },
) {
  const reads = createTechnicalReadTools(access, ports);
  const writes = createTechnicalWriteTools(access, ports.maintenance);
  return {
    "sop_kb.retrieve": reads.sopRetrieve,
    "asset.read": reads.assetRead,
    "sensor.read": reads.sensorRead,
    "maintenance_history.read": reads.maintenanceRead,
    "technical.get_active_outage": reads.getActiveOutage,
    "utility_schedule.read": reads.utilityScheduleRead,
    "maintenance_history.append": writes.maintenanceAppend,
  } satisfies Record<
    string,
    (input: unknown, context: ExecutionContext) => Promise<unknown>
  >;
}
