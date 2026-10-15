import { afterEach, expect, test, vi } from "vitest";
import { isRedirect } from "@tanstack/react-router";
import { Route } from "../src/routes/operations.login";

afterEach(() => { vi.unstubAllGlobals(); vi.unstubAllEnvs(); });

test("leaving the staff app loads the resident login document on the same host", () => {
  vi.stubEnv("VITE_ENABLE_UI_PREVIEW", "false");
  vi.stubGlobal("location", new URL("https://nha.example.vn/operations/login"));
  let caught: unknown;
  try { Route.options.beforeLoad!({} as never); } catch (error) { caught = error; }
  expect(isRedirect(caught)).toBe(true);
  if (!isRedirect(caught)) throw new Error("Expected the login redirect");
  expect(caught.options.href).toBe("https://nha.example.vn/login");
  expect(caught.options.reloadDocument).toBe(true);
});

test("explicit preview keeps its staff login page", () => {
  vi.stubEnv("VITE_ENABLE_UI_PREVIEW", "true");
  expect(Route.options.beforeLoad!({} as never)).toBeUndefined();
});
