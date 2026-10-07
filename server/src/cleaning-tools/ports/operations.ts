import type { ToolContext } from "../../technical-tools/contracts/context";
import type { ToolOutcome } from "../../technical-tools/tool";

/** Caller-owned backend boundary. Mutations must use the existing authorized work-order service. */
export type CleaningOperations = {
  execute(
    context: ToolContext,
    operation:
      | "list_available_staff"
      | "read_work_order"
      | "create_work_order"
      | "dispatch_staff"
      | "update_work_status",
    input: Record<string, unknown>,
  ): Promise<ToolOutcome<unknown>>;
};
