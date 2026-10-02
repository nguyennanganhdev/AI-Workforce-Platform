import assert from "node:assert/strict";
import { test } from "bun:test";
import { createApp } from "../server/src/app.js";
import { loadConfig } from "../server/src/config";

const environment = {
  DATABASE_URL: "postgres://test:test@localhost:5432/test",
  KEY_ENCRYPTION_KEY: "AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA=",
  OPENBOT_SINGLE_USER: "true",
  INTELLIGENCE_API_URL: "http://localhost:7100",
  INTELLIGENCE_GATEWAY_WS_URL: "ws://localhost:7103",
  INTELLIGENCE_API_KEY: "test-only-not-a-real-key",
};
const config = loadConfig(environment);

test("health works without database, runtime or domain implementations", async () => {
  const response = await createApp(config).request("/api/platform/health");
  assert.equal(response.status, 200);
  assert.deepEqual(await response.json(), { status: "ok", mode: "scaffold" });
});

test("unimplemented business routes do not return fake success", async () => {
  const response = await createApp(config).request(
    "/api/domains/vinhomes/actions",
    {
      method: "POST",
      body: "{}",
      headers: { "content-type": "application/json" },
    },
  );
  assert.equal(response.status, 404);
});

test("domain routes use the existing OpenBot authentication guard", async () => {
  const secured = { ...config, singleUser: false };
  const auth = {
    handler: () => new Response(null, { status: 401 }),
    api: { getSession: async () => null },
  };
  const app = createApp(secured, auth, { rolesForUser: async () => ["user"] });
  assert.equal(
    (await app.request("/api/domains/vinhomes/actions", { method: "POST" }))
      .status,
    401,
  );
  assert.equal((await app.request("/api/platform/agents")).status, 401);
  assert.equal((await app.request("/api/platform/health")).status, 200);
  assert.equal((await app.request("/health")).status, 200);
});

test("domain access fails closed when identity is unavailable", async () => {
  const app = createApp({ ...config, singleUser: false });
  assert.equal(
    (await app.request("/api/domains/vinhomes/actions")).status,
    503,
  );
});
