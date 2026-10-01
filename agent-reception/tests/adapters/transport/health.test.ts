import { describe, expect, test } from "bun:test";
import { handleReceptionRequest } from "../../../src/adapters/transport/health";

describe("health transport", () => {
  test("returns liveness without reflecting request data or credentials", async () => {
    const response = handleReceptionRequest(
      new Request("http://localhost/health?token=secret", {
        headers: { Authorization: "Bearer secret" },
      }),
    );
    expect(response.status).toBe(200);
    expect(response.headers.get("Cache-Control")).toBe("no-store");
    expect(await response.json()).toEqual({ status: "ok" });
  });

  test.each([
    ["POST", "/health"],
    ["GET", "/"],
    ["POST", "/run"],
    ["GET", "/ready"],
  ])("does not expose %s %s in PH01", async (method, path) => {
    expect(
      handleReceptionRequest(new Request(`http://localhost${path}`, { method }))
        .status,
    ).toBe(404);
  });
});
