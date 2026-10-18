import { createFileRoute } from "@tanstack/react-router";
import { WorkPage } from "@/features/vinhomes-operations/workspace/WorkPage";
export const Route = createFileRoute("/_authed/operations/my-tasks")({
  validateSearch: (
    s: Record<string, unknown>,
  ): { ticket?: string; job?: string; task?: string; view?: "history" } => ({
    ...(typeof s.ticket === "string" ? { ticket: s.ticket } : {}),
    ...(typeof s.job === "string" ? { job: s.job } : {}),
    ...(typeof s.task === "string" ? { task: s.task } : {}),
    ...(s.view === "history" ? { view: "history" as const } : {}),
  }),
  component: WorkPage,
});
