/**
 * Retrieval evaluation (Q06): run every question of a dataset through retrieval as a resident of its
 * scope, then report recall, MRR, scope leakage, and how candidate "insufficient sources" rules
 * trade refusing off-topic questions against refusing answerable ones.
 *
 *   cd server
 *   bun --env-file=../.env src/knowledge/eval.ts [--dataset <file>] [--k 5] [--out report.json]
 *                                                [--model text-embedding-3-small]
 *
 * Uses the same local development fixture and database as the CLI (see `dev-fixture.ts`), so the
 * knowledge base must have been loaded with the CLI first. Every question is embedded once (a few
 * hundred tokens in all) and leaves one `retrieval_runs` audit row, like any other search.
 */
import { join } from "node:path";
import { SQL } from "bun";
import { createDatabase } from "../db/client";
import {
  createScopeResolver,
  databaseUrl,
  devContext,
  resolveIds,
  seed,
} from "./dev-fixture";
import { createOpenAIEmbedder } from "./embedder";
import {
  cosineRule,
  type EvalDataset,
  type EvalSummary,
  evaluate,
  type Observation,
  sweepRejectionRules,
} from "./eval-metrics";
import { createRetrievalStore } from "./pg-store";
import { DEFAULT_MIN_SIMILARITY, retrieve } from "./retrieve";
import { EMBEDDING_MODEL, type SupportedEmbeddingModel } from "./types";

function parseArgs(argv: string[]) {
  const args = {
    dataset: join(
      import.meta.dir,
      "../../tests/knowledge/eval/ocean-park.v1.json",
    ),
    k: 5,
    out: "",
    db: "",
    tenant: "",
    user: "",
    model: EMBEDDING_MODEL.modelName as string,
  };
  for (let i = 0; i < argv.length; i++) {
    const arg = argv[i];
    const next = () => argv[++i] ?? "";
    if (arg === "--dataset") args.dataset = next();
    else if (arg === "--k") args.k = Number(next()) || args.k;
    else if (arg === "--out") args.out = next();
    else if (arg === "--db") args.db = next();
    else if (arg === "--tenant") args.tenant = next();
    else if (arg === "--user") args.user = next();
    else if (arg === "--model") args.model = next();
  }
  return args;
}

const percent = (value: number) => `${(value * 100).toFixed(1)}%`;

function print(summary: EvalSummary) {
  const { answer, noData, offTopic, leakage } = summary;
  console.log(`\nQuy tắc "thiếu nguồn": ${summary.rule}  (k = ${summary.k})`);
  console.log(
    `  Câu có đáp án (${answer.cases}): recall@1 ${percent(answer.recallAt1)} · recall@3 ${percent(answer.recallAt3)} · recall@${summary.k} ${percent(answer.recallAtK)} · MRR ${answer.mrr.toFixed(3)} · từ chối nhầm ${answer.falseRejections}`,
  );
  console.log(
    `  Câu thiếu dữ liệu (${noData.cases}): xử lý đúng ${noData.handled}/${noData.cases}`,
  );
  console.log(
    `  Câu lạc đề (${offTopic.cases}): từ chối đúng ${offTopic.rejected}/${offTopic.cases}`,
  );
  console.log(
    `  Lấy nhầm phạm vi: ${leakage.hits}/${leakage.totalHits} đoạn, ${leakage.casesWithLeak} câu`,
  );
}

async function main() {
  const args = parseArgs(process.argv.slice(2));
  const dataset = (await Bun.file(args.dataset).json()) as EvalDataset;
  const url = databaseUrl(args.db);
  const admin = new SQL(url);
  const ids = await resolveIds(admin, args.tenant, args.user);
  await seed(admin, ids);
  const [{ documents }] = await admin`
    select count(*)::int as documents from knowledge_documents
    where tenant_id = ${ids.tenant} and knowledge_base_id = ${ids.kb} and status = 'published'`;
  if (documents === 0) {
    throw new Error(
      "Kho tri thức đang trống. Nạp dữ liệu bằng CLI trước: cli.ts <thư-mục-Data-Vinhome>",
    );
  }

  const scopeId = createScopeResolver(admin, ids);
  const database = createDatabase(url, { max: 3, tenantId: ids.tenant });
  const deps = {
    store: createRetrievalStore(database),
    embedder: createOpenAIEmbedder({
      apiKey: process.env.OPENAI_API_KEY ?? "",
      baseUrl: process.env.OPENAI_BASE_URL,
      model: args.model as SupportedEmbeddingModel,
    }),
  };

  console.log(
    `Bộ ${dataset.version}: ${dataset.cases.length} câu, kho ${documents} tài liệu, model ${deps.embedder.model.modelName}.`,
  );
  const observations: Observation[] = [];
  for (const [index, evalCase] of dataset.cases.entries()) {
    const result = await retrieve(deps, {
      context: await devContext(ids, scopeId, evalCase.scope),
      knowledgeBaseId: ids.kb,
      query: evalCase.query,
      topK: args.k,
      // Every candidate is kept; rejection rules are applied afterwards so they can be compared.
      minSimilarity: -1,
    });
    observations.push({
      case: evalCase,
      hits: result.hits.map((hit) => ({
        rank: hit.rank,
        title: hit.documentTitle,
        text: hit.text,
        similarity: hit.similarity,
        keywordRank: hit.keywordRank,
        operator: String(hit.metadata.don_vi ?? "do_thi"),
        buildings: Array.isArray(hit.metadata.toa)
          ? hit.metadata.toa.map(String)
          : [],
      })),
    });
    process.stdout.write(`\r  ${index + 1}/${dataset.cases.length}`);
  }
  console.log();

  const current = evaluate(
    observations,
    cosineRule(DEFAULT_MIN_SIMILARITY),
    args.k,
  );
  print(current);

  const misses = current.results.filter(
    (r) => r.expect === "answer" && r.firstRelevantRank === null,
  );
  if (misses.length > 0) {
    console.log(`\nCâu có đáp án nhưng không tìm thấy trong top ${args.k}:`);
    for (const miss of misses) {
      console.log(
        `  ${miss.id}  "${miss.query}"  [${miss.scope}]  → #1: ${miss.topTitle}`,
      );
    }
  }
  const leaked = current.results.filter((r) => r.leakedHits > 0);
  if (leaked.length > 0) {
    console.log("\nCâu bị lấy nhầm phạm vi:");
    for (const r of leaked) {
      console.log(
        `  ${r.id}  "${r.query}"  [${r.scope}]  ${r.leakedHits} đoạn`,
      );
    }
  }
  const missedOffTopic = current.results.filter(
    (r) => r.expect === "off_topic" && !r.rejected,
  );
  if (missedOffTopic.length > 0) {
    console.log(
      "\nCâu lạc đề chưa bị từ chối (cosine cao nhất, có khớp từ khóa?):",
    );
    for (const r of missedOffTopic) {
      console.log(
        `  ${r.id}  "${r.query}"  cosine ${r.topSimilarity.toFixed(2)}  từ khóa ${r.anyKeyword ? "có" : "không"}`,
      );
    }
  }

  const sweep = sweepRejectionRules(observations, args.k);
  console.log(
    `\nQuét quy tắc "thiếu nguồn" (${offTopicCount(current)} câu lạc đề, ${current.answer.cases} câu có đáp án), 5 quy tắc tốt nhất:`,
  );
  for (const row of sweep.slice(0, 5)) {
    console.log(
      `  từ chối đúng ${row.offTopicRejected}/${offTopicCount(current)} · từ chối nhầm ${row.falseRejections}/${current.answer.cases}  ←  ${row.rule}`,
    );
  }
  console.log(
    "\nKết quả quét chỉ là gợi ý trên một bộ nhỏ; cần xác nhận khi bộ câu hỏi lớn hơn trước khi đổi mặc định.",
  );

  if (args.out) {
    await Bun.write(
      args.out,
      `${JSON.stringify({ dataset: dataset.version, current, sweep: sweep.slice(0, 20) }, null, 2)}\n`,
    );
    console.log(`Đã ghi báo cáo: ${args.out}`);
  }
  await admin.close();
  process.exit(0);
}

function offTopicCount(summary: EvalSummary): number {
  return summary.offTopic.cases;
}

try {
  await main();
} catch (error) {
  console.error(
    `Lỗi: ${error instanceof Error ? error.message : String(error)}`,
  );
  process.exit(1);
}
