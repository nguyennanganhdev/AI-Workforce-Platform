import { createFileRoute, redirect } from "@tanstack/react-router";
import { previewAccount } from "@/features/vinhomes-operations/auth/demo-access";
import { workPath } from "@/features/vinhomes-operations/workspace/work-items";
export const Route = createFileRoute("/_authed/operations/dispatch")({
  beforeLoad: ({ location }) => {
    const account = previewAccount();
    if (!account) throw redirect({ to: "/operations/login" });
    const ticket = new URLSearchParams(location.searchStr).get("ticket");
    throw redirect({
      href:
        workPath(account.role) +
        (ticket ? `?ticket=${encodeURIComponent(ticket)}` : ""),
      replace: true,
    });
  },
});
