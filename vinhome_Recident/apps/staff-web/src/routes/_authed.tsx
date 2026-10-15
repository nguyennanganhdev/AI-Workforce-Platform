import { createFileRoute, Outlet, redirect } from "@tanstack/react-router";
import {
  isOperationsPreview,
  previewAccount,
} from "../features/vinhomes-operations/auth/demo-access";
import {
  canViewPath,
  landing,
} from "../features/vinhomes-operations/workspace/model";

/** Pages a field worker may open; every other address sends them to their own task list. */
const STAFF_PATHS = [
  "/operations/my-tasks",
  "/operations/work-orders",
  "/operations/completed-tasks",
];

type Identity = { role?: string; dataMode?: string; detail?: { code?: string } };

/**
 * Sign-in gate for every page behind /operations.
 *
 * Only the menu is decided here; what a person may read or change stays enforced by the business
 * API, so a hand-edited address shows an empty page rather than data.
 */
export const Route = createFileRoute("/_authed")({
  beforeLoad: async ({ location }) => {
    // Preview is an explicit UI choice, never a fallback session when the backend is down.
    if (isOperationsPreview()) {
      const account = previewAccount()!;
      if (!canViewPath(account.role, location.pathname)) {
        throw redirect({ href: landing(account.role) });
      }
      return;
    }

    // A local demo backend picks its seeded actor from this header; a real backend ignores it.
    const demoActor =
      import.meta.env.VITE_ALLOW_DEMO_BACKEND === "true"
        ? {
            "X-Demo-Actor":
              sessionStorage.getItem("operations.local-actor") || "management",
          }
        : undefined;
    const response = await fetch("/api/business/operations/me", {
      credentials: "include",
      headers: demoActor,
    });
    if (response.status === 401) throw redirect({ href: "/operations/login" });
    if (response.status === 403) {
      // Signed in at the other staff door: the sign-in page tells them where to go.
      const body = (await response.json().catch(() => null)) as Identity | null;
      if (body?.detail?.code === "WRONG_DOOR") {
        throw redirect({ href: "/operations/login" });
      }
      throw new Error(
        "Tài khoản chưa được cấp quyền Operations trong phạm vi này.",
      );
    }
    if (!response.ok) {
      throw new Error(
        "Không kết nối được dịch vụ xác thực và phân quyền Operations. Kiểm tra backend trước khi đăng nhập.",
      );
    }
    const identity = (await response.json()) as Identity;
    if (
      identity.dataMode !== "database" &&
      import.meta.env.VITE_ALLOW_DEMO_BACKEND !== "true"
    ) {
      throw new Error(
        "Backend đang dùng tài khoản demo. Chế độ hiện tại yêu cầu phiên đăng nhập thật.",
      );
    }
    if (!identity.role || !["admin", "management", "staff"].includes(identity.role)) {
      throw new Error("Tài khoản không có vai trò Operations hợp lệ.");
    }
    if (
      identity.role === "staff" &&
      !STAFF_PATHS.includes(location.pathname.replace(/\/$/, ""))
    ) {
      throw redirect({ href: "/operations/my-tasks" });
    }
  },
  component: Outlet,
});
