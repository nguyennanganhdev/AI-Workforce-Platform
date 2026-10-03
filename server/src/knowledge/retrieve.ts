import { keywordQuery, reliabilityOf } from "./source-metadata";
import {
  type CandidateChunk,
  type Embedder,
  RETRIEVAL_POLICY_VERSION,
  type Reliability,
  type RetrievalRequest,
  type RetrievalResult,
  type RetrievalStore,
  type RetrievedChunk,
} from "./types";

export type RetrieveDeps = { store: RetrievalStore; embedder: Embedder };

const DEFAULT_TOP_K = 5;
const MAX_TOP_K = 20;
/** Each of the vector and keyword lists contributes this many before fusion. */
const CANDIDATES = 20;
/**
 * Cosine similarity below which a hit is kept for audit but not handed to the model, so a question
 * nothing answers comes back as `insufficientSources`. Set from the Q06 evaluation with
 * text-embedding-3-large (ocean-park-v1): at 0.35, 13 of 14 off-topic questions are refused and 2
 * of 68 answerable ones are, both scoring 0.31–0.34. Tied to the model: re-run the evaluation
 * before keeping it for any other model or a much larger corpus.
 */
export const DEFAULT_MIN_SIMILARITY = 0.35;

/*
 * Adjustments on top of the fused score. Fused scores of neighbouring ranks differ by only one or two
 * percent, so these are kept small: they settle near-ties in favour of the more specific scope, the
 * better-sourced passage and the newer file, without lifting a passage about a burst pipe above the
 * one about a stuck lift. Uncalibrated; the Q06 evaluation set is what should tune them.
 */
const LEVEL_WEIGHT: Record<string, number> = {
  toa: 1.03,
  cum: 1.02,
  phan_khu: 1.01,
  don_vi: 1,
  do_thi: 1,
};
const RELIABILITY_WEIGHT: Record<Reliability, number> = {
  van_ban_bql: 1.02,
  ghi_nhan_team: 1,
  khong_ro: 1,
  web: 0.98,
};
/** Files still being collected hold "no data yet" facts: worth finding, not worth ranking first. */
const NOT_COLLECTED_WEIGHT = 0.9;
const RECENT_DAYS = 180;
const RECENT_WEIGHT = 1.01;

function adjust(
  hit: CandidateChunk,
  now: number,
): { score: number; reliability: Reliability } {
  const reliability = reliabilityOf(hit.text);
  let score = hit.fusedScore;
  score *= LEVEL_WEIGHT[String(hit.metadata.cap)] ?? 1;
  score *= RELIABILITY_WEIGHT[reliability];
  if (hit.metadata.trang_thai === "chua-thu-thap")
    score *= NOT_COLLECTED_WEIGHT;
  const updated = Date.parse(String(hit.metadata.cap_nhat ?? ""));
  if (!Number.isNaN(updated) && now - updated <= RECENT_DAYS * 86_400_000) {
    score *= RECENT_WEIGHT;
  }
  return { score, reliability };
}

/**
 * How far ahead in similarity the closest passage must be to lead regardless of fusion.
 *
 * Rank fusion counts a keyword match on common words ("xe", "hàng", "cư dân") as much as a close
 * semantic match, so a passage that restates the question (similarity 0.78 against 0.52 for the
 * next) could fall out of the top five because it missed the keyword list. A margin, rather than
 * an absolute similarity, keeps this independent of the embedding model.
 */
const CLEAR_MATCH_MARGIN = 0.15;

/** Put the passage that is clearly the closest in meaning first; leave every other order as fused. */
function leadClearMatch<T extends { similarity: number }>(sorted: T[]): T[] {
  const bySimilarity = [...sorted].sort((a, b) => b.similarity - a.similarity);
  const [best, next] = bySimilarity;
  if (!best || !next || best.similarity - next.similarity < CLEAR_MATCH_MARGIN) return sorted;
  return [best, ...sorted.filter((hit) => hit !== best)];
}

/**
 * Retrieval is: embed the question and build its keyword query, let the store narrow to what this
 * caller may read and run both searches within that, fuse, adjust for scope level, sourcing, status
 * and recency, then write the audit row. Nothing here filters after the fact, and the authority
 * arrives as `AuthorizedContext` from the backend rather than from the agent's own claims.
 */
export async function retrieve(
  { store, embedder }: RetrieveDeps,
  request: RetrievalRequest,
): Promise<RetrievalResult> {
  const started = Date.now();
  const query = request.query.normalize("NFC").trim();
  const topK = Math.min(Math.max(request.topK ?? DEFAULT_TOP_K, 1), MAX_TOP_K);
  const minSimilarity = request.minSimilarity ?? DEFAULT_MIN_SIMILARITY;

  const model = await store.ensureEmbeddingModel(embedder.model);
  const [queryEmbedding] = query === "" ? [] : await embedder.embed([query]);

  const found = queryEmbedding
    ? await store.searchAuthorized({
        context: request.context,
        knowledgeBaseId: request.knowledgeBaseId,
        modelId: model.id,
        queryEmbedding,
        keywordQuery: keywordQuery(query),
        candidates: Math.max(CANDIDATES, topK),
      })
    : { authorizedDocumentIds: [], hits: [] };

  const now = Date.now();
  const ranked = leadClearMatch(
    found.hits
      .map((hit) => ({ ...hit, ...adjust(hit, now) }))
      .sort((a, b) => b.score - a.score),
  )
    .slice(0, topK)
    .map((hit, index) => ({
      ...hit,
      rank: index + 1,
      included: hit.similarity >= minSimilarity,
    }));

  const run = await store.recordRun({
    context: request.context,
    knowledgeBaseId: request.knowledgeBaseId,
    modelId: model.id,
    // The query text is stored as asked; redaction belongs to the caller's PII policy (Q05/Q07).
    queryRedacted: query,
    topK,
    policyVersion: RETRIEVAL_POLICY_VERSION,
    latencyMs: Date.now() - started,
    authorizedDocumentIds: found.authorizedDocumentIds,
    hits: ranked.map(({ chunkId, rank, similarity, included }) => ({
      chunkId,
      rank,
      similarity,
      included,
    })),
  });

  const hits: RetrievedChunk[] = ranked
    .filter((hit) => hit.included)
    .map(({ included: _included, ...hit }) => hit);
  return {
    retrievalRunId: run.id,
    hits,
    insufficientSources: hits.length === 0,
  };
}
