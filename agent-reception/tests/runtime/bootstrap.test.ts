import { expect, test } from "bun:test";
import { fileURLToPath } from "node:url";
import { loadConfig } from "../../src/config";
import { createReceptionRuntime, startReceptionService } from "../../src/index";
import { FakeListChatModel } from "@langchain/core/utils/testing";

// Child processes get no developer credentials, tracing config or .env files.
function childEnvironment() {
  return {
    PATH: process.env.PATH ?? "",
    SystemRoot: process.env.SystemRoot ?? "",
    TEMP: process.env.TEMP ?? "",
    RECEPTION_MODEL_PROVIDER: "invalid-provider-secret",
  };
}

async function runChild(args: string[]) {
  const child = Bun.spawn([process.execPath, "--no-env-file", ...args], {
    env: childEnvironment(),
    stdout: "pipe",
    stderr: "pipe",
  });
  const timer = setTimeout(() => child.kill(), 8_000);
  try {
    const [exitCode, stdout, stderr] = await Promise.all([
      child.exited,
      new Response(child.stdout).text(),
      new Response(child.stderr).text(),
    ]);
    return { exitCode, stdout, stderr };
  } finally {
    clearTimeout(timer);
  }
}

test("importing the entrypoint neither reads config nor starts a server", async () => {
  const entrypoint = new URL("../../src/index.ts", import.meta.url).href;
  const result = await runChild([
    "-e",
    `
    Bun.serve = () => { throw new Error("server opened during import"); };
    await import(${JSON.stringify(entrypoint)});
    console.log("import-ok");
  `,
  ]);
  expect(result).toEqual({ exitCode: 0, stdout: "import-ok\n", stderr: "" });
}, 15_000);

test("CLI rejects invalid config without printing raw values", async () => {
  const result = await runChild([
    fileURLToPath(new URL("../../src/index.ts", import.meta.url)),
  ]);
  expect(result.exitCode).toBe(1);
  expect(result.stderr).toContain("RECEPTION_MODEL_PROVIDER must be");
  expect(result.stderr).not.toContain("invalid-provider-secret");
  expect(result.stdout).toBe("");
}, 15_000);

test("runtime retains the injected model for later graph composition", () => {
  const model = new FakeListChatModel({ responses: ["test-only"] });
  const runtime = createReceptionRuntime(
    loadConfig({ OPENAI_API_KEY: "test-key" }),
    () => model,
  );
  expect(runtime.model).toBe(model);
});

test("service answers over HTTP and releases its listener", async () => {
  const runtime = startReceptionService({
    ...loadConfig({ HOST: "127.0.0.1", OPENAI_API_KEY: "do-not-expose" }),
    port: 0, // Ephemeral test port; CLI config still requires 1..65535.
  });
  try {
    const response = await fetch(
      new URL("/health?key=do-not-expose", runtime.server.url),
    );
    expect(response.status).toBe(200);
    expect(await response.text()).toBe('{"status":"ok"}');
    expect(
      (await fetch(new URL("/run", runtime.server.url), { method: "POST" }))
        .status,
    ).toBe(404);
  } finally {
    await runtime.server.stop(true);
  }
});
