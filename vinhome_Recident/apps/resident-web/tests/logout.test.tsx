import { afterAll, afterEach, beforeAll, expect, test, vi } from "vitest";
import { GlobalRegistrator } from "@happy-dom/global-registrator";
import { signOutResident } from "../src/features/auth/auth-service";

let render: typeof import("@testing-library/react")["render"];
let cleanup: typeof import("@testing-library/react")["cleanup"];
let fireEvent: typeof import("@testing-library/react")["fireEvent"];
beforeAll(async () => {
  GlobalRegistrator.register({ url: "http://localhost:3011/resident" });
  ({ render, cleanup, fireEvent } = await import("@testing-library/react/pure"));
});
afterEach(() => { cleanup(); vi.unstubAllGlobals(); });
afterAll(() => GlobalRegistrator.unregister());

test("resident logout revokes the server session before replacing the document", async () => {
  const replace = vi.fn();
  vi.stubGlobal("location", { replace });
  const fetch = vi.fn(async () => { expect(replace).not.toHaveBeenCalled(); return Response.json({}); });
  vi.stubGlobal("fetch", fetch);
  await signOutResident();
  expect(fetch).toHaveBeenCalledWith("/api/business/auth/logout", expect.objectContaining({ method: "POST", credentials: "include" }));
  expect(replace).toHaveBeenCalledWith("/login");
});

test("resident can retry a failed logout instead of seeing a false signed-out state", async () => {
  const replace = vi.fn();
  vi.stubGlobal("location", { replace });
  vi.stubGlobal("fetch", vi.fn(async () => Response.json({ detail: "Mất kết nối" }, { status: 503 })));
  const { Profile } = await import("../src/features/utilities/Utilities");
  const view = render(<Profile connected onReset={() => {}} />);
  fireEvent.click(view.getByRole("button", { name: "Đăng xuất" }));
  await vi.waitFor(() => expect(view.getByRole("alert").textContent).toContain("Mất kết nối"));
  expect(replace).not.toHaveBeenCalled();
  expect((view.getByRole("button", { name: "Đăng xuất" }) as HTMLButtonElement).disabled).toBe(false);
});
