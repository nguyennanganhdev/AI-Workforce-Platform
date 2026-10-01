import type { Database } from "../../../../server/src/db/client";
import {
  createIngestStore,
  createOpenAIEmbedder,
  type DirectoryIngestOptions,
  type DirectoryIngestReport,
  ingestDirectory,
} from "../../../../server/src/knowledge";

export type IngestDirectoryJobDeps = {
  database: Database;
  openaiApiKey: string;
  openaiBaseUrl?: string;
};

/**
 * Handler factory for the knowledge ingestion job. It opens nothing and starts no loop on import:
 * the worker entrypoint (Team 5) builds the dependencies and decides when to call it.
 */
export function createIngestDirectoryJob(deps: IngestDirectoryJobDeps) {
  const store = createIngestStore(deps.database);
  const embedder = createOpenAIEmbedder({
    apiKey: deps.openaiApiKey,
    baseUrl: deps.openaiBaseUrl,
  });
  return (options: DirectoryIngestOptions): Promise<DirectoryIngestReport> =>
    ingestDirectory({ store, embedder }, options);
}
