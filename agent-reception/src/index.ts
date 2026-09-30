import {
  loadConfig,
  ReceptionConfigError,
  type ReceptionConfig,
} from "./config";
import { createChatModel } from "./adapters/model/factory";
import { handleReceptionRequest } from "./adapters/transport/health";

/** Explicit construction: no env reads, network calls or listeners at import. */
export function createReceptionRuntime(
  config: ReceptionConfig,
  modelFactory: typeof createChatModel = createChatModel,
) {
  return {
    model: modelFactory(config),
    fetch: handleReceptionRequest,
  };
}

/** PH04 can inject the returned model into the graph; PH01 only mounts health. */
export function startReceptionService(config: ReceptionConfig = loadConfig()) {
  const runtime = createReceptionRuntime(config);
  const server = Bun.serve({
    hostname: config.host,
    port: config.port,
    fetch: runtime.fetch,
  });
  return { ...runtime, server };
}

if (import.meta.main) {
  try {
    const { server } = startReceptionService();
    console.info(`Reception health service listening on port ${server.port}`);
    const stop = () => {
      void server.stop();
    };
    process.once("SIGINT", stop);
    process.once("SIGTERM", stop);
  } catch (error) {
    console.error(
      error instanceof ReceptionConfigError
        ? error.message
        : "Reception could not start. Check configuration and port availability.",
    );
    process.exitCode = 1;
  }
}
