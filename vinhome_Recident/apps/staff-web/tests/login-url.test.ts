import { afterEach, describe, expect, test, vi } from "vitest";
import { loginUrl } from "../src/features/vinhomes-operations/auth/login-url";

function at(href: string) {
  vi.stubGlobal("location", new URL(href));
}
afterEach(() => {
  vi.unstubAllGlobals();
  vi.unstubAllEnvs();
});

describe("the one sign-in page", () => {
  test("in a deployment it is /login on the host people are already on", () => {
    at("https://nha.example.vn/operations/kanban?x=1#top");
    expect(loginUrl()).toBe("https://nha.example.vn/login");
  });
  test("in development it is the resident dev server beside this one", () => {
    at("http://127.0.0.1:3020/operations/my-tasks");
    expect(loginUrl()).toBe("http://127.0.0.1:3011/login");
  });
  test("an explicit address wins", () => {
    vi.stubEnv("VITE_LOGIN_URL", "https://dang-nhap.example.vn/login");
    at("http://127.0.0.1:3020/operations");
    expect(loginUrl()).toBe("https://dang-nhap.example.vn/login");
  });
});
