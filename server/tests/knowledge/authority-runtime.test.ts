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
