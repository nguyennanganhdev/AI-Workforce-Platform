import * as c from "../contracts";
import { defineCleaningTool } from "../tool";

export const listStaffTool = defineCleaningTool({
  name: "cleaning.list_available_staff",
  version: "1.0.0",
  effect: "read",
  capability: "cleaning:staff:read",
  timeoutMs: 5000,
  description:
    "Find available cleaning staff in the building's responsible unit and shift. Results do not reserve capacity.",
  inputSchema: c.listStaffInput,
  outputSchema: c.listStaffOutput,
  run: (context, input, deps) =>
    deps.operations.execute(context, "list_available_staff", input),
});
export const readWorkTool = defineCleaningTool({
  name: "cleaning.read_work_order",
  version: "1.0.0",
  effect: "read",
  capability: "cleaning:work:read",
  timeoutMs: 5000,
  description:
    "Read cleaning work, assignments, current versions and optional history by ticket or work order. Does not return technical work.",
  inputSchema: c.readWorkInput,
  outputSchema: c.readWorkOutput,
  run: (context, input, deps) =>
    deps.operations.execute(context, "read_work_order", input),
});
export const createWorkTool = defineCleaningTool({
  name: "cleaning.create_work_order",
  version: "1.0.0",
  effect: "write",
  capability: "cleaning:work:create",
  timeoutMs: 5000,
  description:
    "Create cleaning work through the existing V3 service, retaining its ticket version, authority and plan approval rules.",
  inputSchema: c.createWorkInput,
  outputSchema: c.createWorkOutput,
  run: (context, input, deps) =>
    deps.operations.execute(context, "create_work_order", input),
});
export const dispatchTool = defineCleaningTool({
  name: "cleaning.dispatch_staff",
  version: "1.0.0",
  effect: "write",
  capability: "cleaning:staff:dispatch",
  timeoutMs: 5000,
  description:
    "Offer existing cleaning work to available cleaning staff. The backend checks shift, specialty, load and approval; offered does not mean accepted or contacted.",
  inputSchema: c.dispatchInput,
  outputSchema: c.dispatchOutput,
  run: (context, input, deps) =>
    deps.operations.execute(context, "dispatch_staff", input),
});
export const updateStatusTool = defineCleaningTool({
  name: "cleaning.update_work_status",
  version: "1.0.0",
  effect: "write",
  capability: "cleaning:work:update_status",
  timeoutMs: 5000,
  description:
    "Record an assigned cleaning worker's reported progress under verified caller authority. Never accept work for staff or bypass completion evidence/approval.",
  inputSchema: c.updateStatusInput,
  outputSchema: c.updateStatusOutput,
  run: (context, input, deps) =>
    deps.operations.execute(context, "update_work_status", input),
});
