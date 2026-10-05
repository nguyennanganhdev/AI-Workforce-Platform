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
      // A local demo backend picks its seeded actor from this header; real backends ignore it.
      const demoActor = import.meta.env.VITE_ALLOW_DEMO_BACKEND === 'true'
        ? { 'X-Demo-Actor': sessionStorage.getItem('operations.local-actor') || 'management' }
        : undefined;
      const response = await fetch('/api/business/operations/me', { credentials: 'include', headers: demoActor });
      if (response.status === 401) throw redirect({ href: '/operations/login' });
      if (response.status === 403) {
        // Signed in before this address was kept for the other staff: the sign-in page tells them where to go.
        if ((await response.json().catch(() => null))?.detail?.code === 'WRONG_DOOR') throw redirect({ href: '/operations/login' });
        throw new Error('Tài khoản chưa được cấp quyền Operations trong phạm vi này.');
      }
      if (!response.ok) throw new Error('Không kết nối được dịch vụ xác thực và phân quyền Operations. Kiểm tra backend trước khi đăng nhập.');
      const identity = await response.json() as { role?: string; dataMode?: string };
      if (identity.dataMode !== 'database' && import.meta.env.VITE_ALLOW_DEMO_BACKEND !== 'true') {
        throw new Error('Backend đang dùng tài khoản demo. Chế độ hiện tại yêu cầu phiên đăng nhập thật.');
      }
      if (!identity.role || !['admin', 'management', 'staff'].includes(identity.role)) {
        throw new Error('Tài khoản không có vai trò Operations hợp lệ.');
      }
      if (identity.role === 'staff') {
        const staffPaths = ['/operations/my-tasks', '/operations/work-orders', '/operations/completed-tasks'];
        if (!staffPaths.includes(location.pathname.replace(/\/$/, ''))) {
          throw redirect({ href: '/operations/my-tasks' });
        }
      }
      // Menu access is checked here; resource scope and mutations remain enforced by the API.
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
