import { expect, test } from "bun:test";
import { createBackendKnowledgeAuthorization } from "../../src/knowledge/runtime";

const settings = { tenantId: "tenant", knowledgeBaseId: "knowledge" };

test("knowledge authority rejects public HTTP and credentials even with the compose opt-in", () => {
  for (const baseUrl of ["http://example.com", "http://api.example.com", "http://user:password@api:8000", "http://api:8000?token=value"]) {
    expect(() => createBackendKnowledgeAuthorization({ ...settings, baseUrl, internalHttpHost: "api" })).toThrow();
  }
  expect(() => createBackendKnowledgeAuthorization({ ...settings, baseUrl: "http://api:8000" })).toThrow();
});

test("compose's explicit private service origin still requires resident delegation", async () => {
  const authorize = createBackendKnowledgeAuthorization({ ...settings, baseUrl: "http://api:8000", internalHttpHost: "api",
    fetch: async () => { throw new Error("An unauthenticated request must never contact the backend"); } });
  expect(await authorize(new Request("http://knowledge/search"), { query: "phí gửi xe", topK: 5 })).toMatchObject({ ok: false, status: 401 });
});

test("a specialist's run is accepted with no acting user: in a Supervisor session it works for its unit", async () => {
  const id = (n: number) => `00000000-0000-4000-8000-00000000000${n}`;
  const context = { tenantId: id(1), userId: null, roleCodes: ["management"], targetScopeId: id(2), ancestorScopeIds: [id(3)],
    agentRunId: id(4), principalId: id(5), bindingId: id(6) };
  let offered = "";
  const authorize = createBackendKnowledgeAuthorization({ tenantId: id(1), knowledgeBaseId: id(7), baseUrl: "http://api:8000", internalHttpHost: "api",
    fetch: (async (_url: unknown, init?: RequestInit) => {
      offered = (init!.headers as Record<string, string>).authorization;
      return Response.json({ ok: true, knowledgeBaseId: id(7), context });
    }) as unknown as typeof fetch });
  const request = new Request("http://knowledge/search", { headers: { authorization: "Bearer run.abc.def" } });
  expect(await authorize(request, { scopeId: id(2) })).toEqual({ ok: true, knowledgeBaseId: id(7), context });
  // The credential goes to the backend as it came: the backend made it and is the only one who can read it.
  expect(offered).toBe("Bearer run.abc.def");
});
