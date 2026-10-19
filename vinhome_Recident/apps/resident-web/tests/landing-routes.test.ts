import { describe, expect, test } from "vitest";
import { isLandingRoute } from "../src/features/landing/routes";

describe("Public landing and existing resident bookmarks", () => {
  test("public home and landing section anchors do not open the private resident app", () => {
    for (const hash of ["", "#dich-vu", "#bat-dau", "#giai-dap"])
      expect(isLandingRoute("/", hash)).toBe(true);
  });
  test("authentication, resident entry and existing deep links retain their application routes", () => {
    for (const path of ["/resident", "/login", "/register", "/forgot-password", "/account-status"])
      expect(isLandingRoute(path, "")).toBe(false);
    for (const hash of ["#/", "#/chat/chat-id", "#/requests/ticket-id", "#/utilities", "#/login"])
      expect(isLandingRoute("/", hash)).toBe(false);
  });
});
