import { readdirSync } from "node:fs";
import path from "node:path";
import { spawnSync } from "node:child_process";
import { fileURLToPath } from "node:url";

const root = fileURLToPath(new URL("..", import.meta.url));
const vitest = path.join(root, "node_modules/vitest/vitest.mjs");
const apps = ["resident-web", "staff-web"];
const selected = process.argv.slice(2);
if (selected.some((app) => !apps.includes(app))) {
  throw new Error("Expected resident-web or staff-web");
}

// Each DOM suite owns one process. Portal/global-DOM teardown must not leak into another suite.
for (const app of selected.length ? selected : apps) {
  const cwd = path.join(root, "apps", app);
  const files = ["tests", ...(app === "staff-web" ? ["scripts"] : [])].flatMap(
    (folder) => readdirSync(path.join(cwd, folder), { recursive: true })
      .filter((file) => /\.test\.(ts|tsx|js)$/.test(file))
      .map((file) => path.join(folder, file)),
  ).sort();
  for (const file of files) {
    console.log(`\n${app}: ${file}`);
    const result = spawnSync(process.execPath, [vitest, "run", file], {
      cwd,
      stdio: "inherit",
      env: process.env,
    });
    if (result.error) throw result.error;
    if (result.status !== 0) process.exit(result.status ?? 1);
  }
}
