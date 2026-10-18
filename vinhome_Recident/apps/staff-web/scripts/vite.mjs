import fs from "node:fs";
import { createRequire } from "node:module";
import path from "node:path";
import { fileURLToPath, pathToFileURL } from "node:url";
import { cacheRenameWithRetry } from "./vite-cache-rename.mjs";

if (process.platform === "win32") {
  fs.rename = cacheRenameWithRetry(
    fs.rename.bind(fs),
    fileURLToPath(new URL("../node_modules/.vite", import.meta.url)),
  );
}

// With npm workspaces Vite is installed at the repository root, not under this app, so it is found
// the way Node finds any package instead of by a fixed path.
const viteRoot = path.dirname(
  createRequire(import.meta.url).resolve("vite/package.json"),
);
await import(pathToFileURL(path.join(viteRoot, "bin", "vite.js")).href);
