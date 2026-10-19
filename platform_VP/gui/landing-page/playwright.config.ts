import { defineConfig } from "@playwright/test";

export default defineConfig({
  testDir: "./tests",
  outputDir: "./.artifacts/playwright",
  timeout: 30_000,
  workers: 1,
  reporter: [
    ["list"],
    ["json", { outputFile: ".artifacts/playwright-results.json" }],
  ],
  use: {
    baseURL: process.env.LANDING_BASE_URL || "http://127.0.0.1:5180",
    browserName: "chromium",
    viewport: { width: 1440, height: 900 },
    trace: "retain-on-failure",
    screenshot: "only-on-failure",
  },
});
