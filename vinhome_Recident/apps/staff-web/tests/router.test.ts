import { expect, test } from "vitest";
import { router } from "../src/router";

test("provides the staff sign-in page", () => {
  expect(router.routesByPath["/operations/login"]?.fullPath).toBe(
    "/operations/login",
  );
});

test("provides the work pages of every staff role", () => {
  for (const path of [
    "/operations/my-tasks",
    "/operations/work-orders",
    "/operations/completed-tasks",
    "/operations/incidents",
    "/operations/approvals",
    "/operations/kanban",
  ]) {
    expect(router.routesByPath[path as keyof typeof router.routesByPath]?.fullPath).toBe(path);
  }
});

test("keeps no page of the general-purpose chat product or of agent management", () => {
  const paths = Object.keys(router.routesByPath);
  expect(paths.filter((path) => /^\/(channel|admin|settings|sign|onboarding)/.test(path))).toEqual([]);
  expect(paths.filter((path) => /^\/operations\/(agents|ask|models|connections|team)/.test(path))).toEqual([]);
});
