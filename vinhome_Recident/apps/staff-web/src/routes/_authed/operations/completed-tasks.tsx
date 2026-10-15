import { createFileRoute, redirect } from "@tanstack/react-router";
import { previewAccount } from "@/features/vinhomes-operations/auth/demo-access";
import { WorkPage } from "@/features/vinhomes-operations/workspace/WorkPage";
import { workPath } from "@/features/vinhomes-operations/workspace/work-items";
export const Route = createFileRoute("/_authed/operations/completed-tasks")({
  // The preview workspace keeps its history on the work page. A signed-in account has no preview
  // profile and the connected layout draws this page itself: sending it to the login page put a
  // technician in front of the sign-in form when opening "Công việc đã hoàn thành".
  beforeLoad: () => {
    const a = previewAccount();
    if (a) throw redirect({ href: `${workPath(a.role)}?view=history`, replace: true });
  },
  component: WorkPage,
});
