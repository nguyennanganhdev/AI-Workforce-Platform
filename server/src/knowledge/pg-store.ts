import { sql } from "drizzle-orm";
import type { Database } from "../db/client";
import type { IngestStore, RetrievalStore } from "./types";

type Row = Record<string, unknown>;

/**
 * `drizzle-orm/bun-sql` hands `execute` back as an array of rows. Only the rows are used here, so
 * that is the one place the driver's result type is narrowed.
 */
async function rows(
  executor: Pick<Database, "execute">,
  query: ReturnType<typeof sql>,
): Promise<Row[]> {
  return (await executor.execute(query)) as unknown as Row[];
}

function vectorLiteral(vector: number[]): string {
  return `[${vector.join(",")}]`;
}

/** An array passed as one jsonb parameter, unpacked in SQL, so no driver array encoding is relied on. */
function jsonList(values: string[]) {
  return sql`${JSON.stringify(values)}::text::jsonb`;
}

function one(result: Row[], what: string): Row {
  const first = result[0];
  if (!first)
    throw new Error(`Expected one ${what} row and the query returned none.`);
  return first;
}

/**
 * PostgreSQL implementations of the knowledge ports.
 *
 * The `Database` it is given should be opened with the tenant (`createDatabase(url, { tenantId })`)
 * so row-level security applies; every statement also names the tenant itself, so a connection that
 * forgot to set it fails closed rather than reading across tenants.
 */
export function createIngestStore(database: Database): IngestStore {
  return {
    async ensureEmbeddingModel(spec) {
      const result = await rows(
        database,
        sql`
          INSERT INTO embedding_models (provider, model_name, model_revision, dimension, distance_metric)
          VALUES (${spec.provider}, ${spec.modelName}, ${spec.modelRevision}, ${spec.dimension}, ${spec.distanceMetric})
          ON CONFLICT (provider, model_name, model_revision, dimension)
          DO UPDATE SET active = true
          RETURNING id`,
      );
      return { id: String(one(result, "embedding model").id) };
    },

    async upsertDocument(input) {
      return database.transaction(async (tx) => {
        const upserted = await rows(
          tx,
          sql`
            INSERT INTO knowledge_documents
              (tenant_id, knowledge_base_id, category_id, code, title, status, language)
            VALUES
              (${input.tenantId}, ${input.knowledgeBaseId}, ${input.categoryId}, ${input.code},
               ${input.title}, 'draft', ${input.language})
            ON CONFLICT (knowledge_base_id, code)
            DO UPDATE SET title = EXCLUDED.title, language = EXCLUDED.language
            RETURNING id, active_version_id`,
        );
        const document = one(upserted, "document");
        const documentId = String(document.id);

        for (const scopeId of input.scopeIds) {
          await tx.execute(
            sql`
              INSERT INTO document_scopes (tenant_id, document_id, scope_id, applies_to_descendants)
              VALUES (${input.tenantId}, ${documentId}, ${scopeId}, true)
              ON CONFLICT DO NOTHING`,
          );
        }

        const activeId = document.active_version_id
          ? String(document.active_version_id)
          : null;
        if (activeId === null) return { id: documentId, activeVersion: null };
        const version = one(
          await rows(
            tx,
            sql`SELECT id, content_hash FROM document_versions
                WHERE tenant_id = ${input.tenantId} AND id = ${activeId}`,
          ),
          "active version",
        );
        return {
          id: documentId,
          activeVersion: {
            id: String(version.id),
            contentHash: String(version.content_hash),
          },
        };
      });
    },

    async findVersion({
      tenantId,
      documentId,
      contentHash,
      modelId,
      chunkerVersion,
    }) {
      const found = await rows(
        database,
        sql`
          SELECT v.id,
                 EXISTS (
                   SELECT 1 FROM ingestion_jobs j
                   WHERE j.tenant_id = v.tenant_id AND j.version_id = v.id
                     AND j.embedding_model_id = ${modelId} AND j.status = 'completed'
                 ) AS embedded
          FROM document_versions v
          WHERE v.tenant_id = ${tenantId} AND v.document_id = ${documentId}
            AND v.content_hash = ${contentHash}
            AND v.extraction_config ->> 'chunker' = ${chunkerVersion}
          ORDER BY v.version_no DESC
          LIMIT 1`,
      );
      const row = found[0];
      return row
        ? { id: String(row.id), embedded: row.embedded === true }
        : null;
    },

    async createVersion(input) {
      const created = await rows(
        database,
        sql`
          INSERT INTO document_versions
            (tenant_id, document_id, version_no, file_id, content_hash, effective_from,
             submitted_by, extraction_config)
          VALUES
            (${input.tenantId}, ${input.documentId},
             (SELECT coalesce(max(version_no), 0) + 1 FROM document_versions
              WHERE tenant_id = ${input.tenantId} AND document_id = ${input.documentId}),
             ${input.fileId}, ${input.contentHash}, now(), ${input.submittedBy},
             ${JSON.stringify(input.extractionConfig)}::text::jsonb)
          RETURNING id`,
      );
      return { id: String(one(created, "version").id) };
    },

    async startJob(input) {
      const job = await rows(
        database,
        sql`
          INSERT INTO ingestion_jobs
            (tenant_id, version_id, embedding_model_id, status, idempotency_key,
             parser_version, chunker_version, attempts, expected_chunks)
          VALUES
            (${input.tenantId}, ${input.versionId}, ${input.modelId}, 'embedding',
             ${input.idempotencyKey}, ${input.parserVersion}, ${input.chunkerVersion}, 1,
             ${input.expectedChunks})
          ON CONFLICT (tenant_id, idempotency_key)
          DO UPDATE SET status = 'embedding', error_code = NULL,
                        attempts = ingestion_jobs.attempts + 1,
                        expected_chunks = EXCLUDED.expected_chunks
          RETURNING id`,
      );
      return { id: String(one(job, "ingestion job").id) };
    },

    async saveChunks(input) {
      await database.transaction(async (tx) => {
        for (const chunk of input.chunks) {
          // A retry after a crash between this call and `completeJob` meets chunks that are already
          // there. Chunks are append-only, so they are kept and only matched up again.
          await tx.execute(
            sql`
              INSERT INTO knowledge_chunks
                (tenant_id, version_id, ordinal, text_content, text_hash, token_count,
                 heading_path, search_tsv)
              VALUES
                (${input.tenantId}, ${input.versionId}, ${chunk.ordinal}, ${chunk.text},
                 ${chunk.textHash}, ${chunk.tokenCount}, ${chunk.headingPath || null},
                 to_tsvector('simple', ${chunk.searchText}))
              ON CONFLICT (version_id, ordinal) DO NOTHING`,
          );
          await tx.execute(
            sql`
              INSERT INTO knowledge_embeddings (tenant_id, chunk_id, model_id, embedding, content_hash)
              SELECT ${input.tenantId}, c.id, ${input.modelId}, ${vectorLiteral(chunk.embedding)}::vector,
                     ${chunk.embeddingHash}
              FROM knowledge_chunks c
              WHERE c.tenant_id = ${input.tenantId} AND c.version_id = ${input.versionId}
                AND c.ordinal = ${chunk.ordinal}
              ON CONFLICT (chunk_id, model_id) DO NOTHING`,
          );
        }
        await tx.execute(
          sql`UPDATE ingestion_jobs SET completed_chunks = ${input.chunks.length}
              WHERE tenant_id = ${input.tenantId} AND id = ${input.jobId}`,
        );
      });
    },

    async completeJob(tenantId, jobId) {
      await database.execute(
        sql`UPDATE ingestion_jobs SET status = 'completed', error_code = NULL
            WHERE tenant_id = ${tenantId} AND id = ${jobId}`,
      );
    },

    async failJob(tenantId, jobId, errorCode) {
      await database.execute(
        sql`UPDATE ingestion_jobs SET status = 'failed', error_code = ${errorCode}
            WHERE tenant_id = ${tenantId} AND id = ${jobId}`,
      );
    },

    async activateVersion(input) {
      await database.transaction(async (tx) => {
        await tx.execute(
          sql`UPDATE document_versions SET effective_to = now()
              WHERE tenant_id = ${input.tenantId} AND document_id = ${input.documentId}
                AND id <> ${input.versionId} AND effective_to IS NULL`,
        );
        await tx.execute(
          sql`UPDATE document_versions SET effective_to = NULL
              WHERE tenant_id = ${input.tenantId} AND id = ${input.versionId}`,
        );
        await tx.execute(
          sql`UPDATE knowledge_documents
              SET active_version_id = ${input.versionId}, status = 'published'
              WHERE tenant_id = ${input.tenantId} AND id = ${input.documentId}`,
        );
      });
    },

    async tombstone(tenantId, documentId) {
      await database.transaction(async (tx) => {
        await tx.execute(
          sql`UPDATE document_versions SET effective_to = now()
              WHERE tenant_id = ${tenantId} AND document_id = ${documentId}
                AND effective_to IS NULL`,
        );
        await tx.execute(
          sql`UPDATE knowledge_documents SET status = 'archived'
              WHERE tenant_id = ${tenantId} AND id = ${documentId}`,
        );
      });
    },

    async listDocuments(tenantId, knowledgeBaseId) {
      const found = await rows(
        database,
        sql`SELECT id, code, status FROM knowledge_documents
            WHERE tenant_id = ${tenantId} AND knowledge_base_id = ${knowledgeBaseId}`,
      );
      return found.map((row) => ({
        id: String(row.id),
        code: String(row.code),
        status: String(row.status),
      }));
    },
  };
}

/** Reciprocal rank fusion constant; 60 is the usual choice and damps the top few ranks. */
const RRF_K = 60;

/**
 * Documents the caller may read. A document must be published, serving a version inside its
 * effective window, published to the question's scope (directly, or to descendants from an ancestor),
 * not denied to the caller, and, when it lists any `allow` rows, allowed by one of them. A document
 * with no ACL rows is open to anyone the scope rule admits. That last default is an assumption to
 * confirm with Chiến (see docs/teams/quang/requests).
 */
function authorizedDocuments(
  context: {
    tenantId: string;
    userId: string;
    roleCodes: string[];
    workspaceId?: string;
    targetScopeId: string;
    ancestorScopeIds: string[];
  },
  knowledgeBaseId: string,
) {
  const principalMatches = sql`(
    (a.principal_kind = 'role' AND a.role_code IN (SELECT jsonb_array_elements_text(${jsonList(context.roleCodes)})))
    OR (a.principal_kind = 'user' AND a.user_id = ${context.userId})
    OR (a.principal_kind = 'workspace' AND a.workspace_id = ${context.workspaceId ?? null}::uuid)
  )`;
  return sql`
    SELECT d.id, d.title, d.active_version_id, v.extraction_config
    FROM knowledge_documents d
    JOIN document_versions v ON v.tenant_id = d.tenant_id AND v.id = d.active_version_id
    WHERE d.tenant_id = ${context.tenantId}
      AND d.knowledge_base_id = ${knowledgeBaseId}
      AND d.status = 'published'
      AND v.effective_from <= now()
      AND (v.effective_to IS NULL OR v.effective_to > now())
      AND EXISTS (
        SELECT 1 FROM document_scopes s
        WHERE s.tenant_id = d.tenant_id AND s.document_id = d.id
          AND (s.scope_id = ${context.targetScopeId}
               OR (s.applies_to_descendants
                   AND s.scope_id::text IN (SELECT jsonb_array_elements_text(${jsonList(context.ancestorScopeIds)}))))
      )
      AND NOT EXISTS (
        SELECT 1 FROM document_acl a
        WHERE a.tenant_id = d.tenant_id AND a.document_id = d.id AND a.effect = 'deny'
          AND ${principalMatches}
      )
      AND (
        NOT EXISTS (
          SELECT 1 FROM document_acl a
          WHERE a.tenant_id = d.tenant_id AND a.document_id = d.id AND a.effect = 'allow')
        OR EXISTS (
          SELECT 1 FROM document_acl a
          WHERE a.tenant_id = d.tenant_id AND a.document_id = d.id AND a.effect = 'allow'
            AND ${principalMatches})
      )`;
}

export function createRetrievalStore(database: Database): RetrievalStore {
  return {
    ensureEmbeddingModel: createIngestStore(database).ensureEmbeddingModel,

    async searchAuthorized(input) {
      const authorized = authorizedDocuments(
        input.context,
        input.knowledgeBaseId,
      );
      const documents = await rows(
        database,
        sql`SELECT id FROM (${authorized}) AS allowed`,
      );
      const query = vectorLiteral(input.queryEmbedding);
      const keyword = input.keywordQuery
        ? sql`to_tsquery('simple', ${input.keywordQuery.any})`
        : sql`NULL::tsquery`;
      const codesMatch = input.keywordQuery?.codes
        ? sql`(search_tsv @@ to_tsquery('simple', ${input.keywordQuery.codes}))`
        : // An expression, not a literal: PostgreSQL refuses a constant in ORDER BY.
          sql`coalesce(search_tsv @@ NULL::tsquery, false)`;
      // Both lists rank inside `allowed`, so neither can surface a document the caller may not read,
      // and fusion happens over those two bounded lists rather than the whole corpus.
      const found = await rows(
        database,
        sql`
          WITH allowed AS (${authorized}),
          candidate AS (
            SELECT c.id, c.version_id, c.heading_path, c.text_content, c.search_tsv,
                   e.embedding, allowed.id AS document_id, allowed.title,
                   allowed.extraction_config
            FROM allowed
            JOIN knowledge_chunks c
              ON c.tenant_id = ${input.context.tenantId} AND c.version_id = allowed.active_version_id
            JOIN knowledge_embeddings e
              ON e.tenant_id = c.tenant_id AND e.chunk_id = c.id AND e.model_id = ${input.modelId}
          ),
          by_vector AS (
            SELECT id, row_number() OVER (ORDER BY embedding <=> ${query}::vector) AS rank
            FROM candidate
            ORDER BY embedding <=> ${query}::vector
            LIMIT ${input.candidates}
          ),
          by_keyword AS (
            SELECT id, row_number() OVER (
                     ORDER BY ${codesMatch} DESC, ts_rank_cd(search_tsv, ${keyword}) DESC
                   ) AS rank
            FROM candidate
            WHERE search_tsv @@ ${keyword}
            ORDER BY ${codesMatch} DESC, ts_rank_cd(search_tsv, ${keyword}) DESC
            LIMIT ${input.candidates}
          )
          SELECT c.id AS chunk_id, c.document_id, c.version_id, c.title AS document_title,
                 c.heading_path, c.text_content, c.extraction_config,
                 1 - (c.embedding <=> ${query}::vector) AS similarity,
                 v.rank AS vector_rank, k.rank AS keyword_rank,
                 coalesce(1.0 / (${RRF_K} + v.rank), 0) + coalesce(1.0 / (${RRF_K} + k.rank), 0)
                   AS fused_score
          FROM candidate c
          LEFT JOIN by_vector v ON v.id = c.id
          LEFT JOIN by_keyword k ON k.id = c.id
          WHERE v.id IS NOT NULL OR k.id IS NOT NULL
          ORDER BY fused_score DESC`,
      );
      return {
        authorizedDocumentIds: documents.map((row) => String(row.id)),
        hits: found.map((row) => {
          // Depending on the driver path jsonb arrives parsed or as text; accept both.
          const raw = row.extraction_config;
          const config = (
            typeof raw === "string" ? JSON.parse(raw) : (raw ?? {})
          ) as { metadata?: Record<string, unknown>; sources?: unknown };
          return {
            chunkId: String(row.chunk_id),
            documentId: String(row.document_id),
            versionId: String(row.version_id),
            documentTitle: String(row.document_title),
            headingPath:
              row.heading_path === null ? null : String(row.heading_path),
            text: String(row.text_content),
            similarity: Number(row.similarity),
            vectorRank:
              row.vector_rank === null ? null : Number(row.vector_rank),
            keywordRank:
              row.keyword_rank === null ? null : Number(row.keyword_rank),
            fusedScore: Number(row.fused_score),
            metadata: config.metadata ?? {},
            sources: Array.isArray(config.sources)
              ? config.sources.map(String)
              : [],
          };
        }),
      };
    },

    async recordRun(input) {
      return database.transaction(async (tx) => {
        const run = one(
          await rows(
            tx,
            sql`
              INSERT INTO retrieval_runs
                (tenant_id, agent_run_id, actor_user_id, knowledge_base_id, model_id,
                 query_text_redacted, metadata_filter, authorized_document_ids, top_k,
                 policy_version, latency_ms, principal_id, binding_id)
              VALUES
                (${input.context.tenantId}, ${input.context.agentRunId}, ${input.context.userId},
                 ${input.knowledgeBaseId}, ${input.modelId}, ${input.queryRedacted},
                 ${JSON.stringify({ targetScopeId: input.context.targetScopeId })}::text::jsonb,
                 ${JSON.stringify(input.authorizedDocumentIds)}::text::jsonb, ${input.topK},
                 ${input.policyVersion}, ${input.latencyMs}, ${input.context.principalId},
                 ${input.context.bindingId})
              RETURNING id`,
          ),
          "retrieval run",
        );
        const runId = String(run.id);
        for (const hit of input.hits) {
          await tx.execute(
            sql`
              INSERT INTO retrieval_hits
                (tenant_id, retrieval_run_id, chunk_id, rank, similarity, included)
              VALUES
                (${input.context.tenantId}, ${runId}, ${hit.chunkId}, ${hit.rank},
                 ${hit.similarity}, ${hit.included})`,
          );
        }
        return { id: runId };
      });
    },
  };
}
