import { readdir, readFile } from "node:fs/promises";
import { join, posix, relative, sep } from "node:path";
import {
  type IngestDeps,
  ingestDocument,
  type PreparedDocument,
  prepareDocument,
} from "./ingest";
import { parseFrontMatter, sha256 } from "./markdown";
import { BUILDING_FOLDER, scopeKeyOf, sourceMetadata } from "./source-metadata";
import type { IngestResult } from "./types";

export type SourceDocument = {
  /**
   * Path relative to the root, with `/` separators, and the document code. A document standing for
   * several identical building files is coded `parent/{M1,M2,M3}/file.md`.
   */
  code: string;
  title: string;
  raw: string;
  /** Folders whose scopes the document is published to; one per building for a folded document. */
  scopeKeys: string[];
  /** Set for a folded document: the buildings it stands for. */
  buildings?: string[];
};

/**
 * Files that exist to run the repository or to track what is still to be collected. They hold no
 * facts for a resident, and indexing them would let "what documents are missing" outrank real answers.
 */
const NOT_KNOWLEDGE = [
  /^readme\.md$/i,
  /^agents\.md$/i,
  /^nguon\.md$/i,
  /^danh-muc-/i,
  /^danh-sach-tai-lieu-can-thu-thap\.md$/i,
  /^ra-soat-du-lieu\.md$/i,
];
const NOT_KNOWLEDGE_FOLDERS = new Set(["luu-tru"]);

async function* walk(directory: string): AsyncGenerator<string> {
  for (const entry of await readdir(directory, { withFileTypes: true })) {
    if (entry.name.startsWith(".")) continue;
    const path = join(directory, entry.name);
    if (entry.isDirectory()) {
      if (!NOT_KNOWLEDGE_FOLDERS.has(entry.name)) yield* walk(path);
    } else if (entry.isFile() && entry.name.toLowerCase().endsWith(".md")) {
      yield path;
    }
  }
}

function titleOf(body: string, fallback: string): string {
  const heading = /^#\s+(.+?)\s*$/m.exec(body);
  return heading?.[1] ?? fallback;
}

function escapeRegExp(value: string): string {
  return value.replace(/[.*+?^${}()|[\]\\]/g, "\\$&");
}

/** Every standalone mention of a building code, but not `M1` inside `M12` or `S1.01` inside `S1.012`. */
function buildingPattern(code: string): RegExp {
  return new RegExp(
    `(?<![\\p{L}\\p{N}])${escapeRegExp(code)}(?![\\p{N}]|\\.\\d)`,
    "gu",
  );
}

/**
 * Fold sibling building files that are the same apart from their own building code (the Masteri
 * M1/M2/M3 and H1/H2/H3 placeholders) into one document published to every one of those buildings.
 * Indexed separately they fill the top results with copies of one passage.
 */
function foldIdenticalBuildings(documents: SourceDocument[]): SourceDocument[] {
  const groups = new Map<string, SourceDocument[]>();
  const out: SourceDocument[] = [];
  for (const document of documents) {
    const segments = document.code.split("/");
    const file = segments.at(-1) ?? "";
    const building = segments.at(-2) ?? "";
    if (!BUILDING_FOLDER.test(building)) {
      out.push(document);
      continue;
    }
    const parent = segments.slice(0, -2).join("/");
    const signature = sha256(
      document.raw.replace(buildingPattern(building), "\u0000"),
    );
    const key = `${parent}\u0001${file}\u0001${signature}`;
    groups.set(key, [...(groups.get(key) ?? []), document]);
  }
  for (const members of groups.values()) {
    const first = members[0] as SourceDocument;
    if (members.length === 1) {
      out.push(first);
      continue;
    }
    const segments = first.code.split("/");
    const buildings = members.map(
      (member) => member.code.split("/").at(-2) as string,
    );
    const own = segments.at(-2) as string;
    const joined = buildings.join("/");
    out.push({
      code: `${segments.slice(0, -2).join("/")}/{${buildings.join(",")}}/${segments.at(-1)}`,
      title: first.title.replace(buildingPattern(own), joined),
      raw: first.raw.replace(buildingPattern(own), joined),
      scopeKeys: members.flatMap((member) => member.scopeKeys),
      buildings,
    });
  }
  return out.sort((a, b) => a.code.localeCompare(b.code));
}

/** Read every knowledge Markdown file under `root`, in a stable order, identical buildings folded. */
export async function readSourceDocuments(
  root: string,
): Promise<SourceDocument[]> {
  const documents: SourceDocument[] = [];
  for await (const path of walk(root)) {
    const code = relative(root, path).split(sep).join("/");
    const name = posix.basename(code);
    if (NOT_KNOWLEDGE.some((pattern) => pattern.test(name))) continue;
    const raw = (await readFile(path, "utf8")).normalize("NFC");
    documents.push({
      code,
      title: titleOf(parseFrontMatter(raw).body, name.replace(/\.md$/i, "")),
      raw,
      scopeKeys: [scopeKeyOf(code)],
    });
  }
  documents.sort((a, b) => a.code.localeCompare(b.code));
  return foldIdenticalBuildings(documents);
}

export type DocumentPreview = PreparedDocument & {
  code: string;
  title: string;
  scopeKeys: string[];
  scopePath: string;
  metadata: Record<string, unknown>;
};

/**
 * What `ingestDirectory` would index, document by document, without embedding or storing anything.
 * A document with no chunks is one ingestion skips as empty.
 */
export async function previewDirectory(
  root: string,
): Promise<DocumentPreview[]> {
  const previews: DocumentPreview[] = [];
  for (const document of await readSourceDocuments(root)) {
    const metadata = sourceMetadata(
      document.code,
      parseFrontMatter(document.raw).meta,
      document.buildings,
    );
    previews.push({
      code: document.code,
      title: document.title,
      scopeKeys: document.scopeKeys,
      scopePath: metadata.duong_dan,
      metadata,
      ...prepareDocument({
        raw: document.raw,
        title: document.title,
        scopePath: metadata.duong_dan,
        metadata,
      }),
    });
  }
  return previews;
}

export type DirectoryIngestOptions = {
  root: string;
  tenantId: string;
  knowledgeBaseId: string;
  categoryId: string;
  submittedBy: string;
  /** Map a folder (`01-vinhomes/sapphire`) to its `access_scopes.id`, creating it if the caller owns that. */
  resolveScopeId(scopeKey: string): Promise<string>;
  /** Store the original through the storage service and return `files.id`. */
  registerFile(document: SourceDocument): Promise<string>;
  /**
   * Retire documents of this knowledge base that the directory no longer yields (deleted, emptied,
   * or folded into a combined building document). Only for a knowledge base this directory owns.
   */
  prune?: boolean;
};

export type DirectoryIngestReport = {
  ingested: number;
  unchanged: number;
  skipped: number;
  retired: number;
  failed: { code: string; error: string }[];
};

/**
 * Ingest a folder of Markdown. One bad file is reported and the rest still go in, so a single
 * failure (a provider hiccup, a bad scope key) does not leave the whole corpus half indexed with no
 * way to tell which half.
 */
export async function ingestDirectory(
  deps: IngestDeps,
  options: DirectoryIngestOptions,
): Promise<DirectoryIngestReport> {
  const report: DirectoryIngestReport = {
    ingested: 0,
    unchanged: 0,
    skipped: 0,
    retired: 0,
    failed: [],
  };
  /** Codes still backed by a file. A failed file counts, so a transient error never retires it. */
  const present = new Set<string>();
  for (const document of await readSourceDocuments(options.root)) {
    let result: IngestResult;
    try {
      const metadata = sourceMetadata(
        document.code,
        parseFrontMatter(document.raw).meta,
        document.buildings,
      );
      result = await ingestDocument(deps, {
        tenantId: options.tenantId,
        knowledgeBaseId: options.knowledgeBaseId,
        categoryId: options.categoryId,
        code: document.code,
        title: document.title,
        raw: document.raw,
        fileId: await options.registerFile(document),
        submittedBy: options.submittedBy,
        scopeIds: await Promise.all(
          document.scopeKeys.map(options.resolveScopeId),
        ),
        scopePath: metadata.duong_dan,
        metadata,
        source: { path: document.code },
      });
    } catch (error) {
      present.add(document.code);
      report.failed.push({
        code: document.code,
        error: error instanceof Error ? error.message : String(error),
      });
      continue;
    }
    if (result.status === "skipped") {
      report.skipped++;
      continue;
    }
    present.add(document.code);
    if (result.status === "ingested") report.ingested++;
    else report.unchanged++;
  }

  if (options.prune) {
    const known = await deps.store.listDocuments(
      options.tenantId,
      options.knowledgeBaseId,
    );
    for (const document of known) {
      if (present.has(document.code) || document.status === "archived")
        continue;
      await deps.store.tombstone(options.tenantId, document.id);
      report.retired++;
    }
  }
  return report;
}
