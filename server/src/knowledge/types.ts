/**
 * Shared contracts for the knowledge (RAG) module.
 *
 * Everything that touches PostgreSQL, storage or the embedding provider is a port here, so the
 * ingestion and retrieval logic can be tested without any of them and so Chiến's services (authz,
 * storage) can be plugged in without this module reaching into their tables.
 */

/**
 * The default embedding space. `knowledge_embeddings.embedding` is `vector(1536)` and the
 * `embedding_dimension` trigger rejects any model that is not 1536 / cosine, so changing the
 * dimension or metric is a schema request to Chiến, not an edit here.
 *
 * `text-embedding-3-large`, shortened to 1536, chosen over `-small` on the Q06 evaluation
 * (ocean-park-v1, 93 questions, 01/10/2026): recall@1 82.4% vs 73.5%, all five questions typed
 * without diacritics found vs three, and off-topic questions separable by similarity at all.
 */
export const EMBEDDING_MODEL = {
  provider: "openai",
  modelName: "text-embedding-3-large",
  modelRevision: "v1",
  dimension: 1536,
  distanceMetric: "cosine",
} as const;

/**
 * OpenAI models that can produce the 1536 dimensions the schema requires. `text-embedding-3-large`
 * is natively 3072 and is shortened by the API's `dimensions` parameter; vectors of different
 * models are never mixed, each has its own `embedding_models` row and its own vectors.
 */
export const SUPPORTED_EMBEDDING_MODELS = [
  "text-embedding-3-small",
  "text-embedding-3-large",
] as const;
export type SupportedEmbeddingModel =
  (typeof SUPPORTED_EMBEDDING_MODELS)[number];

export type EmbeddingModelSpec = {
  provider: string;
  modelName: string;
  modelRevision: string;
  dimension: number;
  distanceMetric: string;
};

export interface Embedder {
  readonly model: EmbeddingModelSpec;
  /** One vector per input, same order, each exactly `model.dimension` long. */
  embed(texts: string[]): Promise<number[][]>;
}

export const PARSER_VERSION = "md-frontmatter-1";
export const CHUNKER_VERSION = "md-scope-3";

export type Chunk = {
  ordinal: number;
  headingPath: string;
  text: string;
  textHash: string;
  tokenCount: number;
};

/** Where a write happens: every query runs under one tenant. */
export type TenantContext = { tenantId: string };

export type IngestInput = {
  tenantId: string;
  knowledgeBaseId: string;
  categoryId: string;
  /** Stable key of the document inside its knowledge base, e.g. its repository path. */
  code: string;
  title: string;
  language?: string;
  /** Raw file text, front matter included. */
  raw: string;
  /** `files.id` of the stored original; `document_versions.file_id` is NOT NULL. */
  fileId: string;
  submittedBy: string;
  /** `access_scopes.id` the document is published to. */
  scopeIds: string[];
  /** Extra provenance copied into `document_versions.extraction_config`. */
  source?: Record<string, unknown>;
  /** Scope line put in front of every chunk before embedding, e.g. `Vinhomes > sapphire > S1.01`. */
  scopePath?: string;
  /** Filterable facts about the document (operator, building, kind, status), returned with hits. */
  metadata?: Record<string, unknown>;
};

export type IngestResult =
  | {
      status: "ingested";
      documentId: string;
      versionId: string;
      chunks: number;
    }
  | { status: "unchanged"; documentId: string; versionId: string }
  | { status: "skipped"; reason: "empty" };

export type DocumentRecord = {
  id: string;
  activeVersion: { id: string; contentHash: string } | null;
};

export type ChunkWithEmbedding = Chunk & {
  /** What `search_tsv` is built from: scope, headings, text, and an unaccented copy. */
  searchText: string;
  embeddingHash: string;
  embedding: number[];
};

export interface IngestStore {
  ensureEmbeddingModel(spec: EmbeddingModelSpec): Promise<{ id: string }>;
  upsertDocument(input: {
    tenantId: string;
    knowledgeBaseId: string;
    categoryId: string;
    code: string;
    title: string;
    language: string;
    scopeIds: string[];
  }): Promise<DocumentRecord>;
  /**
   * A version of this document with this content hash cut by this chunker, if one exists. Chunks are
   * append-only, so a new chunker needs a new version rather than new chunks on the old one.
   */
  findVersion(input: {
    tenantId: string;
    documentId: string;
    contentHash: string;
    modelId: string;
    chunkerVersion: string;
  }): Promise<{ id: string; embedded: boolean } | null>;
  createVersion(input: {
    tenantId: string;
    documentId: string;
    fileId: string;
    contentHash: string;
    submittedBy: string;
    extractionConfig: Record<string, unknown>;
  }): Promise<{ id: string }>;
  /** Idempotent on `idempotencyKey`; an existing job is returned, not duplicated. */
  startJob(input: {
    tenantId: string;
    versionId: string;
    modelId: string;
    idempotencyKey: string;
    parserVersion: string;
    chunkerVersion: string;
    expectedChunks: number;
  }): Promise<{ id: string }>;
  /** Chunks and vectors land together or not at all. */
  saveChunks(input: {
    tenantId: string;
    jobId: string;
    versionId: string;
    modelId: string;
    chunks: ChunkWithEmbedding[];
  }): Promise<void>;
  completeJob(tenantId: string, jobId: string): Promise<void>;
  failJob(tenantId: string, jobId: string, errorCode: string): Promise<void>;
  /** Make `versionId` the one retrieval serves and close the previous version's window. */
  activateVersion(input: {
    tenantId: string;
    documentId: string;
    versionId: string;
  }): Promise<void>;
  /** Stop serving a document without deleting its history. */
  tombstone(tenantId: string, documentId: string): Promise<void>;
  /** Every document in a knowledge base, so a directory sync can retire what disappeared. */
  listDocuments(
    tenantId: string,
    knowledgeBaseId: string,
  ): Promise<{ id: string; code: string; status: string }[]>;
}

/**
 * The caller's authority, already worked out by the backend (Chiến's authz service). Retrieval never
 * widens it and never takes a list of document ids from the agent.
 */
export type AuthorizedContext = {
  tenantId: string;
  userId: string;
  roleCodes: string[];
  workspaceId?: string;
  /** The scope the question is about, e.g. one building. */
  targetScopeId: string;
  /** That scope's ancestors, so a document published "to descendants" higher up still applies. */
  ancestorScopeIds: string[];
  /** Audit identity, required by `retrieval_runs`. */
  agentRunId: string;
  principalId: string;
  bindingId: string;
};

export type RetrievalRequest = {
  context: AuthorizedContext;
  knowledgeBaseId: string;
  query: string;
  topK?: number;
  /** Hits below this cosine similarity are returned as not included. */
  minSimilarity?: number;
};

export type Reliability = "van_ban_bql" | "ghi_nhan_team" | "web" | "khong_ro";

/** One candidate as the store finds it, before boosting. */
export type CandidateChunk = {
  chunkId: string;
  documentId: string;
  versionId: string;
  documentTitle: string;
  headingPath: string | null;
  text: string;
  /** Cosine similarity. A closeness score, not a measure of whether the answer is right. */
  similarity: number;
  /** 1-based position in the vector list, null when only the keyword search found it. */
  vectorRank: number | null;
  /** 1-based position in the keyword list, null when only the vector search found it. */
  keywordRank: number | null;
  /** Reciprocal rank fusion of the two lists. */
  fusedScore: number;
  /** `extraction_config.metadata` of the version: operator, building, kind, status, update date. */
  metadata: Record<string, unknown>;
  /** Citation lines from the document's source sections. */
  sources: string[];
};

export type RetrievedChunk = CandidateChunk & {
  /** How well this passage is sourced; anything below a management notice needs confirming. */
  reliability: Reliability;
  /** Fused score after scope-level, reliability, status and recency adjustments. */
  score: number;
  rank: number;
};

export type RetrievalResult = {
  retrievalRunId: string;
  hits: RetrievedChunk[];
  /** True when nothing authorized matched well enough; the caller must say data is missing. */
  insufficientSources: boolean;
};

export interface RetrievalStore {
  ensureEmbeddingModel(spec: EmbeddingModelSpec): Promise<{ id: string }>;
  /**
   * Nearest chunks among documents the context may read. The authorization predicate is part of
   * this query, so it narrows the candidate set BEFORE the nearest-neighbour ordering and the limit.
   */
  searchAuthorized(input: {
    context: AuthorizedContext;
    knowledgeBaseId: string;
    modelId: string;
    queryEmbedding: number[];
    /** A `to_tsquery('simple', …)` expression, or null to skip the keyword list. */
    keywordQuery: { any: string; codes: string | null } | null;
    /** How many each of the vector and keyword lists contribute before fusion. */
    candidates: number;
  }): Promise<{
    authorizedDocumentIds: string[];
    hits: CandidateChunk[];
  }>;
  recordRun(input: {
    context: AuthorizedContext;
    knowledgeBaseId: string;
    modelId: string;
    queryRedacted: string;
    topK: number;
    policyVersion: string;
    latencyMs: number;
    authorizedDocumentIds: string[];
    hits: {
      chunkId: string;
      rank: number;
      similarity: number;
      included: boolean;
    }[];
  }): Promise<{ id: string }>;
}

export const RETRIEVAL_POLICY_VERSION = "acl-first-hybrid-3";
