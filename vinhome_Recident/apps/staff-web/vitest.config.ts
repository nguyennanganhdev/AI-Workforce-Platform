import path from "node:path";
import { defineConfig } from "vitest/config";

export default defineConfig({
  resolve: {
    alias: { "@": path.resolve(import.meta.dirname, "src") },
  },
  test: {
    // Several DOM suites run in parallel; the slowest needs more than the 5 s default on a busy machine.
    testTimeout: 15_000,
    include: ["tests/**/*.test.{ts,tsx}", "scripts/**/*.test.js"],
    // Evaluates Base UI once while a DOM exists; see tests/preload.ts.
    setupFiles: ["tests/preload.ts"],
  },
});
