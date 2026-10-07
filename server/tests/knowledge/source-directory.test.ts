import { afterAll, beforeAll, describe, expect, test } from "bun:test";
import { mkdir, mkdtemp, rm, writeFile } from "node:fs/promises";
import { tmpdir } from "node:os";
import { dirname, join } from "node:path";
import {
  ingestDirectory,
  readSourceDocuments,
} from "../../src/knowledge/source-directory";
import { EMBEDDING_MODEL, type IngestStore } from "../../src/knowledge/types";

let root: string;

async function put(path: string, content: string) {
  await mkdir(dirname(join(root, path)), { recursive: true });
  await writeFile(join(root, path), content);
}

const pccc = (code: string) =>
  `---\ntoa: ${code}\n---\n# PCCC — ${code}\n\n## Fact\nChưa có sơ đồ thoát nạn ${code}.\n`;

beforeAll(async () => {
  root = await mkdtemp(join(tmpdir(), "kb-"));
  await put("README.md", "# repo");
  await put("02-masterise/RA-SOAT-DU-LIEU.md", "# review");
  await put("02-masterise/luu-tru/old.md", "# archived");
  await put("02-masterise/mw/miami/M1/pccc.md", pccc("M1"));
  await put("02-masterise/mw/miami/M2/pccc.md", pccc("M2"));
  await put(
    "02-masterise/mw/miami/M3/pccc.md",
    `${pccc("M3")}\nRiêng M3 có tầng lánh nạn 15.\n`,
  );
  await put("01-vinhomes/sapphire/sapphire-1/S1.01/pccc.md", pccc("S1.01"));
  await put("01-vinhomes/sapphire/sapphire-1/S1.02/pccc.md", pccc("S1.02"));
  await put(
    "01-vinhomes/sapphire/sapphire-1/S1.02/thong-tin.md",
    "# S1.012 khác\nS1.02 có 39 tầng.",
  );
});

afterAll(async () => {
  await rm(root, { recursive: true, force: true });
});

describe("readSourceDocuments", () => {
  test("drops repository files and the archive folder", async () => {
    const codes = (await readSourceDocuments(root)).map((d) => d.code);
    expect(codes.some((code) => code.endsWith("README.md"))).toBe(false);
    expect(codes.some((code) => code.includes("RA-SOAT"))).toBe(false);
    expect(codes.some((code) => code.includes("luu-tru"))).toBe(false);
  });

  test("identical sibling building files fold into one document published to each building", async () => {
    const documents = await readSourceDocuments(root);
    const folded = documents.find(
      (d) => d.code === "02-masterise/mw/miami/{M1,M2}/pccc.md",
    );
    expect(folded?.buildings).toEqual(["M1", "M2"]);
    expect(folded?.scopeKeys).toEqual([
      "02-masterise/mw/miami/M1",
      "02-masterise/mw/miami/M2",
    ]);
    expect(folded?.raw).toContain("Chưa có sơ đồ thoát nạn M1/M2.");
    expect(folded?.title).toBe("PCCC — M1/M2");
    // M3 says something the others do not, so it stays its own document.
    expect(
      documents.some((d) => d.code === "02-masterise/mw/miami/M3/pccc.md"),
    ).toBe(true);
  });

  test("folding works for dotted codes and leaves different files alone", async () => {
    const codes = (await readSourceDocuments(root)).map((d) => d.code);
    expect(codes).toContain(
      "01-vinhomes/sapphire/sapphire-1/{S1.01,S1.02}/pccc.md",
    );
    expect(codes).toContain(
      "01-vinhomes/sapphire/sapphire-1/S1.02/thong-tin.md",
    );
  });
});

describe("ingestDirectory pruning", () => {
  test("retires what the folder no longer has, except documents another publisher keeps", async () => {
    const empty = await mkdtemp(join(tmpdir(), "kb-empty-"));
    const retired: string[] = [];
    const store = {
      listDocuments: async () => [
        { id: "resident-doc", code: "00-do-thi/cu.md", status: "published" },
        { id: "bql-doc", code: "bql/ve-sinh/dieu-7.md", status: "published" },
      ],
      tombstone: async (_tenant: string, id: string) => {
        retired.push(id);
      },
    } as unknown as IngestStore;
    try {
      const report = await ingestDirectory(
        { store, embedder: { model: { ...EMBEDDING_MODEL }, embed: async () => [] } },
        {
          root: empty,
          tenantId: "tenant",
          knowledgeBaseId: "kb",
          categoryId: "category",
          submittedBy: "user",
          resolveScopeId: async () => "scope",
          registerFile: async () => "file",
          prune: true,
          keep: (code) => code.startsWith("bql/"),
        },
      );
      expect(retired).toEqual(["resident-doc"]);
      expect(report.retired).toBe(1);
    } finally {
      await rm(empty, { recursive: true, force: true });
    }
  });
});
