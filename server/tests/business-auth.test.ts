import { describe, expect, test } from "bun:test";
import { businessAuthority, createBusinessAuth } from "../src/auth/business";

describe("business authentication authority", () => {
  test("uses the same verified identity, rechecks revocation and never forwards unrelated secrets", async () => {
    const requests: RequestInit[] = [];
    let active = true;
    const request = (async (_url: string | URL | Request, init?: RequestInit) => {
      requests.push(init!);
      return active ? Response.json({ user: { id: "canonical-user", email: "user@example.test", name: "User" }, membershipStatus: "active" })
        : new Response(null, { status: 401 });
    }) as typeof fetch;
    const auth = createBusinessAuth("http://api:8000", ["http://localhost:3020"], request);
    const headers = new Headers({ cookie: `other=secret; vinhomes_session=${"a".repeat(43)}`, authorization: "Bearer never-forward" });
    expect(await auth.api.getSession({ headers })).toEqual({ user: { id: "canonical-user", email: "user@example.test", name: "User" } });
    expect(new Headers(requests[0]!.headers).get("cookie")).toBe(`vinhomes_session=${"a".repeat(43)}`);
    expect(new Headers(requests[0]!.headers).get("authorization")).toBeNull();
    active = false;
    expect(await auth.api.getSession({ headers })).toBeNull();
    expect(requests).toHaveLength(2);
    expect(await auth.api.getSession({ headers: new Headers({ cookie: "vinhomes_session=forged" }) })).toBeNull();
    expect(requests).toHaveLength(2);
  });

  test("pending memberships and an unavailable authority fail closed", async () => {
    const pending = createBusinessAuth("http://api:8000", [], (async () => Response.json({ user: { id: "pending", email: "x@example.test" }, membershipStatus: "pending" })) as typeof fetch);
    const headers = new Headers({ cookie: `vinhomes_session=${"a".repeat(43)}` });
    expect(await pending.api.getSession({ headers })).toBeNull();
    const unavailable = createBusinessAuth("http://api:8000", [], (async () => new Response(null, { status: 503 })) as typeof fetch);
    expect(unavailable.api.getSession({ headers })).rejects.toThrow("unavailable");
  });

  test("sign-out checks the browser origin and revokes the authority's cookie", async () => {
    let calls = 0;
    const auth = createBusinessAuth("http://api:8000", ["http://localhost:3020"], (async () => {
      calls++;
      return Response.json({ ok: true }, { headers: { "set-cookie": "vinhomes_session=; Max-Age=0; Path=/; HttpOnly" } });
    }) as typeof fetch);
    expect((await auth.handler(new Request("http://localhost/api/auth/sign-out", { method: "POST", headers: { origin: "https://attacker.test" } }))).status).toBe(403);
    expect(calls).toBe(0);
    const response = await auth.handler(new Request("http://localhost/api/auth/sign-out", { method: "POST", headers: { origin: "http://localhost:3020" } }));
    expect(response.headers.get("set-cookie")).toContain("Max-Age=0");
    expect(calls).toBe(1);
  });

  test("authority is deployment-owned and cannot redirect credentials to arbitrary HTTP hosts", () => {
    expect(businessAuthority("https://auth.example.test")).toBe("https://auth.example.test");
    for (const value of ["http://evil.test", "https://user:password@auth.test", "https://auth.test/path", "https://auth.test?target=x"])
      expect(() => businessAuthority(value)).toThrow();
  });
});
