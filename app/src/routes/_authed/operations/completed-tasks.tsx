import { createFileRoute, redirect } from "@tanstack/react-router";
import { previewAccount } from "@/features/vinhomes-operations/auth/demo-access";
import { workPath } from "@/features/vinhomes-operations/workspace/work-items";

export const Route = createFileRoute("/_authed/operations/completed-tasks")({
  beforeLoad: () => {
    const a = previewAccount();
    if (!a) throw redirect({ to: "/operations/login" });
    throw redirect({ href: `${workPath(a.role)}?view=history`, replace: true });
  },
});
