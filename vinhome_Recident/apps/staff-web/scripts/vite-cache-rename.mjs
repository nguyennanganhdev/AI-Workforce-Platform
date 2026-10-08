import path from "node:path";

// Keep the atomic rename: never copy over a live cache or suppress an error.
export function cacheRenameWithRetry(rename, cacheRoot, options = {}) {
  const timeoutMs = options.timeoutMs ?? 60_000;
  const intervalMs = options.intervalMs ?? 250;
  const root = path.resolve(cacheRoot);
  const isCachePath = (value) =>
    typeof value === "string" &&
    path.dirname(path.resolve(value)) === root &&
    /^deps(?:_temp_[a-z0-9]+)?$/.test(path.basename(value));

  return function (from, to, callback) {
    if (!isCachePath(from) || !isCachePath(to)) {
      return rename(from, to, callback);
    }
    const started = Date.now();
    let announced = false;
    const attempt = () =>
      rename(from, to, (error) => {
        if (
          error &&
          ["EPERM", "EACCES", "EBUSY"].includes(error.code) &&
          Date.now() - started < timeoutMs
        ) {
          if (!announced) {
            announced = true;
            console.info(
              "[vite] Waiting for Windows to release the dependency cache...",
            );
          }
          setTimeout(attempt, intervalMs);
          return;
        }
        if (error) console.error("[vite] Cache rename failed:", error);
        callback(error);
      });
    return attempt();
  };
}
