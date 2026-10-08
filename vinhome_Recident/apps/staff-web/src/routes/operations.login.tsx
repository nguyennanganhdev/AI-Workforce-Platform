import { createFileRoute } from "@tanstack/react-router";
import { StaffLoginPage } from "@/features/vinhomes-operations/auth/StaffLoginPage";

export const Route = createFileRoute("/operations/login")({
  component: StaffLoginPage,
});
