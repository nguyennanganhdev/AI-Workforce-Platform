import { createFileRoute, redirect } from "@tanstack/react-router";
import { previewAccount } from "@/features/vinhomes-operations/auth/demo-access";
import { workPath } from "@/features/vinhomes-operations/workspace/work-items";
export const Route = createFileRoute("/_authed/operations/dispatch")({
  beforeLoad: ({ location }) => {
    const account = previewAccount();
    // A signed-in account has no preview profile: its own start page decides, not the sign-in form.
    if (!account) throw redirect({ to: "/operations", replace: true });
    const ticket = new URLSearchParams(location.searchStr).get("ticket");
    throw redirect({
      href:
        workPath(account.role) +
        (ticket ? `?ticket=${encodeURIComponent(ticket)}` : ""),
      replace: true,
    });
  },
});
