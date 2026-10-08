import fs from "node:fs";
import { fileURLToPath } from "node:url";
import { cacheRenameWithRetry } from "./vite-cache-rename.mjs";

if (process.platform === "win32") {
  fs.rename = cacheRenameWithRetry(
    fs.rename.bind(fs),
    fileURLToPath(new URL("../node_modules/.vite", import.meta.url)),
  );
}

await import(new URL("../node_modules/vite/bin/vite.js", import.meta.url));
