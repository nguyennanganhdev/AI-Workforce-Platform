import { expect, test } from "bun:test";
import path from "node:path";
import { cacheRenameWithRetry } from "./vite-cache-rename.mjs";

const root = path.resolve("app/node_modules/.vite");
const from = path.join(root, "deps_temp_abc123");
const to = path.join(root, "deps");
const run = (rename, source = from, destination = to) =>
  new Promise((resolve) => rename(source, destination, resolve));

test("retries a transient cache lock and completes once", async () => {
  let calls = 0;
  const rename = cacheRenameWithRetry(
    (_from, _to, cb) => {
      calls++;
      cb(calls < 3 ? { code: "EPERM" } : null);
    },
    root,
    { intervalMs: 1, timeoutMs: 1000 },
  );
  expect(await run(rename)).toBeNull();
  expect(calls).toBe(3);
});

test("does not retry unrelated files or similarly named directories", async () => {
  for (const source of [
    path.join(root, "config.json"),
    path.join(root + "-other", "deps_temp_abc123"),
  ]) {
    let calls = 0;
    const error = { code: "EPERM" };
    const rename = cacheRenameWithRetry((_from, _to, cb) => {
      calls++;
      cb(error);
    }, root);
    expect(await run(rename, source)).toBe(error);
    expect(calls).toBe(1);
  }
});

test("does not hide permanent errors", async () => {
  const error = { code: "ENOENT" };
  let calls = 0;
  const rename = cacheRenameWithRetry((_from, _to, cb) => {
    calls++;
    cb(error);
  }, root);
  expect(await run(rename)).toBe(error);
  expect(calls).toBe(1);
});

test("stops retrying when the deadline expires", async () => {
  const error = { code: "EPERM" };
  let calls = 0;
  const rename = cacheRenameWithRetry(
    (_from, _to, cb) => {
      calls++;
      cb(error);
    },
    root,
    { intervalMs: 2, timeoutMs: 10 },
  );
  expect(await run(rename)).toBe(error);
  expect(calls).toBeGreaterThan(1);
  expect(calls).toBeLessThan(20);
});
