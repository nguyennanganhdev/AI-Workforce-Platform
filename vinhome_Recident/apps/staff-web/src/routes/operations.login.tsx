import { createFileRoute, redirect } from "@tanstack/react-router";
import { StaffLoginPage } from "@/features/vinhomes-operations/auth/StaffLoginPage";
import { loginUrl } from "@/features/vinhomes-operations/auth/login-url";

export const Route = createFileRoute("/operations/login")({
  // Everyone signs in on the same page. This one is kept only for the UI preview.
  beforeLoad: () => {
    if (import.meta.env.VITE_ENABLE_UI_PREVIEW !== "true") throw redirect({ href: loginUrl() });
  },
  component: StaffLoginPage,
});
