import {
  chunkDocument,
  embeddingInput,
  parseFrontMatter,
  sha256,
} from "./markdown";
import { searchText } from "./source-metadata";
import {
  CHUNKER_VERSION,
  type Embedder,
  type IngestInput,
  type IngestResult,
  type IngestStore,
  PARSER_VERSION,
} from "./types";

export type IngestDeps = { store: IngestStore; embedder: Embedder };

function errorCode(error: unknown): string {
  const code = (error as { code?: unknown } | null)?.code;
  return typeof code === "string" && code !== "" ? code : "ingest_failed";
}

/**
 * Parse, chunk, embed and publish one document.
 *
 * Files still marked `chua-thu-thap` are ingested too: their few facts ("no evacuation plan for
 * R1.02 yet") are what lets an answer say data is missing instead of inventing it. Their status
 * travels in the metadata and retrieval ranks them down; empty templates produce no chunks and are
 * skipped.
 *
 * Re-running with unchanged content and the same chunker changes nothing: the version is found by
 * content hash and chunker, and the job by its idempotency key. Anything else becomes a new version
 * with new chunks, because chunks are append-only. The version only becomes the served one after its
 * vectors are saved, so a failure part-way leaves the previous version answering.
 */
export async function ingestDocument(
  { store, embedder }: IngestDeps,
  input: IngestInput,
): Promise<IngestResult> {
  const parsed = parseFrontMatter(input.raw);
  const { chunks, sources } = chunkDocument(parsed.body);
  if (chunks.length === 0) return { status: "skipped", reason: "empty" };

  const scopePath = input.scopePath ?? "";
  // Scope and metadata are part of what is indexed, so a change to either is a new version too.
  const contentHash = sha256(
    `${scopePath}\n${JSON.stringify(input.metadata ?? {})}\n${input.raw.normalize("NFC")}`,
  );
  const model = await store.ensureEmbeddingModel(embedder.model);
  const document = await store.upsertDocument({
    tenantId: input.tenantId,
    knowledgeBaseId: input.knowledgeBaseId,
    categoryId: input.categoryId,
    code: input.code,
    title: input.title,
    language: input.language ?? "vi",
    scopeIds: input.scopeIds,
  });

  const existing = await store.findVersion({
    tenantId: input.tenantId,
    documentId: document.id,
    contentHash,
    modelId: model.id,
    chunkerVersion: CHUNKER_VERSION,
  });
  if (existing?.embedded) {
    if (document.activeVersion?.id !== existing.id) {
      await store.activateVersion({
        tenantId: input.tenantId,
        documentId: document.id,
        versionId: existing.id,
      });
    }
    return {
      status: "unchanged",
      documentId: document.id,
      versionId: existing.id,
    };
  }

  const version =
    existing ??
    (await store.createVersion({
      tenantId: input.tenantId,
      documentId: document.id,
      fileId: input.fileId,
      contentHash,
      submittedBy: input.submittedBy,
      extractionConfig: {
        parser: PARSER_VERSION,
        chunker: CHUNKER_VERSION,
        frontMatter: parsed.meta,
        scopePath,
        metadata: input.metadata ?? {},
        sources,
        ...input.source,
      },
    }));

  const job = await store.startJob({
    tenantId: input.tenantId,
    versionId: version.id,
    modelId: model.id,
    idempotencyKey: `ingest:${version.id}:${model.id}:${PARSER_VERSION}:${CHUNKER_VERSION}`,
    parserVersion: PARSER_VERSION,
    chunkerVersion: CHUNKER_VERSION,
    expectedChunks: chunks.length,
  });

  try {
    const inputs = chunks.map((chunk) =>
      embeddingInput(chunk, input.title, scopePath),
    );
    const vectors = await embedder.embed(inputs);
    await store.saveChunks({
      tenantId: input.tenantId,
      jobId: job.id,
      versionId: version.id,
      modelId: model.id,
      chunks: chunks.map((chunk, index) => ({
        ...chunk,
        searchText: searchText([
          scopePath,
          input.title,
          // The notice number lives in front matter (`van_ban`) more often than in the passage.
          typeof input.metadata?.van_ban === "string"
            ? input.metadata.van_ban
            : "",
          chunk.headingPath,
          chunk.text,
        ]),
        embeddingHash: sha256(inputs[index] as string),
        embedding: vectors[index] as number[],
      })),
    });
    await store.completeJob(input.tenantId, job.id);
  } catch (error) {
    await store.failJob(input.tenantId, job.id, errorCode(error));
    throw error;
  }

  await store.activateVersion({
    tenantId: input.tenantId,
    documentId: document.id,
    versionId: version.id,
  });
  return {
    status: "ingested",
    documentId: document.id,
    versionId: version.id,
    chunks: chunks.length,
  };
}
