/**
 * Developer tool: ask the knowledge base questions from the terminal, optionally ingesting a
 * Markdown folder first. Works on the local `openbot` database (DATABASE_URL) by default.
 *
 *   cd server
 *   bun --env-file=../.env src/knowledge/cli.ts                 # ask what is already loaded
 *   bun --env-file=../.env src/knowledge/cli.ts <data-dir>      # load or refresh a folder, then ask
 *   bun --env-file=../.env src/knowledge/cli.ts --serve 8787    # serve POST /internal/knowledge/search
 *
 * Options: --db <name> another database on the same server; --tenant <code> when there is more
 * than one tenant; --user <id> which existing user the dev principal acts as; --skip-ingest;
 * --model text-embedding-3-small to load and search with that model's vectors instead.
 *
 * `--serve` stands in for the server until the route is mounted there, so agent runtimes can be
 * built against the real contract. Its authorization is a dev stub: the scope comes from the
 * `x-dev-scope` header (a folder such as 01-vinhomes/sapphire/sapphire-1/S1.01), which the real
 * backend will instead derive from the resident's account. Never expose it beyond localhost.
 *
 * What it writes to the database is described in `dev-fixture.ts`. Not a production entry point.
 */
import { stdin, stdout } from "node:process";
import { createInterface } from "node:readline";
import { SQL } from "bun";
import { Hono } from "hono";
import { createDatabase } from "../db/client";
import {
  createScopeResolver,
  databaseUrl,
  devContext,
  folderScopes,
  type Ids,
  loadedScopes,
  PREFIX,
  resolveIds,
  seed,
} from "./dev-fixture";
import { createOpenAIEmbedder } from "./embedder";
import { createIngestStore, createRetrievalStore } from "./pg-store";
import {
  DEFAULT_MIN_SIMILARITY,
  type RetrieveDeps,
  retrieve,
} from "./retrieve";
import { type AuthorizeKnowledgeSearch, createKnowledgeRoutes } from "./routes";
import { ingestDirectory } from "./source-directory";
import { EMBEDDING_MODEL, type SupportedEmbeddingModel } from "./types";

/** Set once in `main`, after the tenant is known. */
let ids: Ids;

function parseArgs(argv: string[]) {
  const args = {
    dataDir: "",
    db: "",
    tenant: "",
    user: "",
    model: EMBEDDING_MODEL.modelName as string,
    skipIngest: false,
    serve: 0,
  };
  for (let i = 0; i < argv.length; i++) {
    const arg = argv[i] as string;
    if (arg === "--db") args.db = argv[++i] ?? "";
    else if (arg === "--tenant") args.tenant = argv[++i] ?? "";
    else if (arg === "--user") args.user = argv[++i] ?? "";
    else if (arg === "--model") args.model = argv[++i] ?? "";
    else if (arg === "--skip-ingest") args.skipIngest = true;
    else if (arg === "--serve") args.serve = Number(argv[++i]) || 8787;
    else if (!arg.startsWith("--")) args.dataDir = arg;
  }
  return args;
}

/** The dev stand-in for the server route; see the file comment for what its authorization is not. */
async function serve(
  port: number,
  allScopes: string[],
  scopeId: (key: string) => Promise<string>,
  retrieval: RetrieveDeps,
) {
  const keyById = new Map<string, string>();
  for (const key of allScopes) keyById.set(await scopeId(key), key);

  const authorize: AuthorizeKnowledgeSearch = async (request, ask) => {
    const requested = ask.scopeId ? keyById.get(ask.scopeId) : undefined;
    const key = request.headers.get("x-dev-scope") ?? requested;
    if (!key) {
      return {
        ok: false,
        status: 409,
        code: "scope_required",
        message: "Set x-dev-scope, or pass one of these scopeIds.",
        choices: [...keyById]
          .slice(0, 20)
          .map(([id, label]) => ({ scopeId: id, label })),
      };
    }
    if (!allScopes.includes(key)) {
      return {
        ok: false,
        status: 403,
        code: "forbidden",
        message: `Unknown scope ${key}.`,
      };
    }
    return {
      ok: true,
      knowledgeBaseId: ids.kb,
      context: await devContext(ids, scopeId, key),
    };
  };

  const app = new Hono();
  app.route(
    "/internal/knowledge",
    createKnowledgeRoutes({
      authorize,
      retrieval,
      onError: (error) => console.error(error),
    }),
  );
  Bun.serve({ hostname: "127.0.0.1", port, fetch: app.fetch });
  console.log(
    `Đang phục vụ http://127.0.0.1:${port}/internal/knowledge/search (Ctrl+C để dừng)`,
  );
  console.log(
    `Thử: curl -s http://127.0.0.1:${port}/internal/knowledge/search -H 'content-type: application/json' -H 'x-dev-scope: 01-vinhomes/sapphire/sapphire-1/S1.01' -d '{"query":"số an ninh tòa mình"}'`,
  );
  await new Promise(() => {});
}

const HELP = `
Lệnh:
  /scope <thư mục>   chọn phạm vi câu hỏi, ví dụ /scope 01-vinhomes/sapphire/sapphire-1/S1.01
  /scopes [lọc]      liệt kê các phạm vi có thể chọn
  /k <số>            số kết quả (mặc định 5)
  /min <số>          ngưỡng cosine tối thiểu (mặc định 0.35)
  /full              bật/tắt hiển thị toàn văn đoạn
  /help              hiện trợ giúp
  /quit              thoát
Gõ câu hỏi bất kỳ để tìm.`;

async function main() {
  const args = parseArgs(process.argv.slice(2));
  const url = databaseUrl(args.db);
  const apiKey = process.env.OPENAI_API_KEY ?? "";
  const baseUrl = process.env.OPENAI_BASE_URL;

  const admin = new SQL(url);
  ids = await resolveIds(admin, args.tenant, args.user);
  await seed(admin, ids);
  console.log(
    `Database ${new URL(url).pathname.slice(1)}, tenant ${ids.tenant}, user ${ids.user}, kho ${PREFIX}-ocean-park.`,
  );
  const scopeId = createScopeResolver(admin, ids);

  const database = createDatabase(url, { max: 3, tenantId: ids.tenant });
  const embedder = createOpenAIEmbedder({
    apiKey,
    baseUrl,
    model: args.model as SupportedEmbeddingModel,
  });
  console.log(`Model embedding: ${embedder.model.modelName}.`);

  if (args.dataDir !== "" && !args.skipIngest) {
    console.log(
      `Đang nạp ${args.dataDir} … (lần đầu khoảng 1 phút; lần sau chỉ nạp file đổi)`,
    );
    const started = Date.now();
    const report = await ingestDirectory(
      { store: createIngestStore(database), embedder },
      {
        root: args.dataDir,
        tenantId: ids.tenant,
        knowledgeBaseId: ids.kb,
        categoryId: ids.category,
        submittedBy: ids.user,
        resolveScopeId: scopeId,
        registerFile: async () => ids.file,
        prune: true,
      },
    );
    console.log(
      `Xong sau ${((Date.now() - started) / 1000).toFixed(1)}s: mới ${report.ingested}, không đổi ${report.unchanged}, bỏ qua ${report.skipped}, lưu trữ ${report.retired}, lỗi ${report.failed.length}`,
    );
    for (const failure of report.failed)
      console.log(`  lỗi ${failure.code}: ${failure.error}`);
  }

  const allScopes =
    args.dataDir === ""
      ? await loadedScopes(admin, ids)
      : await folderScopes(args.dataDir);
  if (allScopes.length === 0) {
    throw new Error(
      "Chưa có dữ liệu trong database. Chạy kèm thư mục dữ liệu một lần: cli.ts <thư-mục-dữ-liệu>",
    );
  }
  console.log(`Đang dùng dữ liệu đã nạp: ${allScopes.length} phạm vi.`);
  if (args.serve > 0) {
    await serve(args.serve, allScopes, scopeId, {
      store: createRetrievalStore(database),
      embedder,
    });
    return;
  }

  let scope = "01-vinhomes/sapphire";
  let topK = 5;
  let minSimilarity = DEFAULT_MIN_SIMILARITY;
  let full = false;
  const store = createRetrievalStore(database);

  console.log(HELP);
  const rl = createInterface({
    input: stdin,
    output: stdout,
    terminal: stdin.isTTY,
  });
  // Piped input closes the interface at end of input while buffered lines are still being handled.
  let closed = false;
  rl.on("close", () => {
    closed = true;
  });
  const prompt = () => {
    if (closed) return;
    rl.setPrompt(`\n[${scope}] > `);
    rl.prompt();
  };
  /** One line of input; false means quit. */
  const handle = async (line: string): Promise<boolean> => {
    const [command, ...rest] = line.split(/\s+/);
    const value = rest.join(" ");
    if (command === "/quit" || command === "/exit") return false;
    if (command === "/help") {
      console.log(HELP);
      return true;
    }
    if (command === "/scopes") {
      for (const key of allScopes.filter((k) => k.includes(value)))
        console.log(`  ${key}`);
      return true;
    }
    if (command === "/scope") {
      if (!allScopes.includes(value)) {
        console.log(`Không có thư mục "${value}". Dùng /scopes để xem.`);
      } else scope = value;
      return true;
    }
    if (command === "/k") {
      topK = Number(value) || topK;
      console.log(`k = ${topK}`);
      return true;
    }
    if (command === "/min") {
      minSimilarity = Number.isNaN(Number(value))
        ? minSimilarity
        : Number(value);
      console.log(`min = ${minSimilarity}`);
      return true;
    }
    if (command === "/full") {
      full = !full;
      console.log(`toàn văn: ${full ? "bật" : "tắt"}`);
      return true;
    }
    if (command?.startsWith("/")) {
      console.log("Lệnh không rõ. Gõ /help.");
      return true;
    }

    const context = await devContext(ids, scopeId, scope);
    const started = Date.now();
    const result = await retrieve(
      { store, embedder },
      { context, knowledgeBaseId: ids.kb, query: line, topK, minSimilarity },
    );
    console.log(
      `\n${result.hits.length} kết quả, ${Date.now() - started}ms, thiếu nguồn: ${result.insufficientSources ? "CÓ" : "không"}, run ${result.retrievalRunId}`,
    );
    for (const hit of result.hits) {
      const meta = hit.metadata;
      const toa =
        Array.isArray(meta.toa) && meta.toa.length > 0
          ? `/${meta.toa.join(",")}`
          : "";
      const flags = [
        meta.chua_xac_minh ? "CHƯA XÁC MINH" : "",
        meta.trang_thai === "chua-thu-thap" ? "chưa thu thập" : "",
      ].filter(Boolean);
      console.log(
        `\n#${hit.rank}  điểm ${hit.score.toFixed(4)}  cosine ${hit.similarity.toFixed(2)}  vector #${hit.vectorRank ?? "-"}  từ khóa #${hit.keywordRank ?? "-"}`,
      );
      console.log(
        `    [${meta.don_vi}/${meta.cap}${toa}] ${hit.reliability}${flags.length ? ` · ${flags.join(" · ")}` : ""} · cập nhật ${meta.cap_nhat ?? "?"}`,
      );
      console.log(`    ${hit.headingPath ?? hit.documentTitle}`);
      const text = full
        ? hit.text
        : hit.text.replace(/\s+/g, " ").slice(0, 220);
      console.log(
        `    ${text.replace(/\n/g, "\n    ")}${!full && hit.text.length > 220 ? " …" : ""}`,
      );
      if (full && hit.sources.length > 0)
        console.log(`    Nguồn: ${hit.sources.join(" | ")}`);
    }
    return true;
  };

  // Read with the line iterator rather than `question`: piped input arrives before a question is
  // asked, and `question` drops lines it was not waiting for.
  try {
    prompt();
    for await (const raw of rl) {
      const line = raw.trim();
      if (!stdin.isTTY && line !== "") console.log(line);
      if (line !== "" && !(await handle(line))) break;
      prompt();
    }
  } finally {
    rl.close();
    await admin.close();
  }
  process.exit(0);
}

try {
  await main();
} catch (error) {
  console.error(
    `Lỗi: ${error instanceof Error ? error.message : String(error)}`,
  );
  process.exit(1);
}
