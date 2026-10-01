import { createFileRoute, Outlet, redirect, useMatches } from "@tanstack/react-router";
import { currentUserQueryOptions, needsOnboarding } from "../lib/auth/queries";
import { CopilotProvider } from "../lib/copilot/provider";
import { AppHotkeys } from "../lib/hotkeys/app-hotkeys";
import { isOperationsPreview } from "../features/vinhomes-operations/auth/demo-access";
import { previewAccount } from "../features/vinhomes-operations/auth/demo-access";
import { canViewPath, landing } from "../features/vinhomes-operations/workspace/model";

export const Route = createFileRoute("/_authed")({
  beforeLoad: async ({ context, location }) => {
    if (location.pathname === "/operations" || location.pathname.startsWith("/operations/")) {
      // Workspaces currently contain mock data. Preview is an explicit UI choice,
      // not a fallback administrator session when the backend is unavailable.
      if (isOperationsPreview()) {
        const account=previewAccount()!;
        if(!canViewPath(account.role,location.pathname))throw redirect({href:landing(account.role)});
        return;
      }
      // The connected layout bootstraps identity through the V3 API; every query is authorized server-side.
      return;
    }
    if (typeof window !== "undefined" && window.location.port === "3020" && location.pathname === "/") {
      throw redirect({ to: "/operations/login" });
    }
    const user = await context.queryClient.ensureQueryData(
      currentUserQueryOptions(),
    );
    if (!user) {
      throw redirect({ to: "/sign" });
    }
    /*
     * Somebody who has not finished onboarding goes there and nowhere else. Here rather than in
     * `_app`, so admin and settings are behind the same gate; checked against the destination so
     * the onboarding route itself stays reachable.
     */
    if (needsOnboarding(user) && location.pathname !== "/onboarding") {
      throw redirect({ to: "/onboarding" });
    }
  },
  // Mounted INSIDE the authed boundary, not at the root: the runtime endpoint requires a session, so
  // a provider above the sign-in gate would open a run for a visitor who has not signed in yet.
  component: AuthedComponent,
});

function AuthedComponent() {
  const matches = useMatches();
  const isOperations = matches.some((match) => match.pathname.startsWith("/operations"));

  // Operations Platform runs independently without CopilotKit providers or OpenBot hotkeys
  if (isOperations) {
    return <Outlet />;
  }

  return (
    <CopilotProvider>
      <AppHotkeys />
      <Outlet />
    </CopilotProvider>
  );
}
