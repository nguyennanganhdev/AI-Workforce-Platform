import { createHash } from "node:crypto";
import { parse as parseYaml } from "yaml";
import type { Chunk } from "./types";

export function sha256(text: string): string {
  return createHash("sha256").update(text, "utf8").digest("hex");
}

export type ParsedMarkdown = {
  meta: Record<string, unknown>;
  body: string;
};

/**
 * Split a leading `---` YAML block from the body. A file without one has empty metadata.
 *
 * The text is normalised to NFC first: Vietnamese can be typed precomposed or with combining marks,
 * and two spellings of the same word would otherwise never match as keywords.
 */
export function parseFrontMatter(raw: string): ParsedMarkdown {
  const text = raw.replace(/^﻿/, "").normalize("NFC");
  const match = /^---\r?\n([\s\S]*?)\r?\n---\r?\n?/.exec(text);
  if (!match) return { meta: {}, body: text };
  let meta: unknown;
  try {
    meta = parseYaml(match[1] ?? "");
  } catch {
    meta = {};
  }
  return {
    meta:
      meta !== null && typeof meta === "object" && !Array.isArray(meta)
        ? (meta as Record<string, unknown>)
        : {},
    body: text.slice(match[0].length),
  };
}

/** Rough size estimate; Vietnamese text runs well under 4 characters per token. */
export function estimateTokens(text: string): number {
  return Math.max(1, Math.ceil(text.length / 3));
}

const DEFAULT_MAX_CHARS = 1200;
/** Sections shorter than this are folded into the chunk before them. */
const DEFAULT_MIN_CHARS = 150;

/**
 * Sections that are the collecting team's to-do lists. They are full of the very words a resident
 * asks about ("số trực", "sơ đồ thoát nạn") and contain no answer, so left in they win retrieval.
 *
 * Sections about conflicting or unconfirmed data ("cần xác minh", "cần kiểm chứng", "chưa thống
 * nhất") are kept on purpose: an answer must be able to say the sources disagree.
 */
const TODO_HEADING =
  /(cần thu|cần bổ sung|còn phải thu|việc team phải|việc cần thu|thiếu gì so với|chứng cứ cần bổ sung|vận hành còn thiếu)/i;
/** Source sections: their bullets are citations, not facts. */
const SOURCE_HEADING = /^(nguồn|nguồn bổ sung|sổ nguồn|nguồn và cách lưu)$/i;

/** A line that carries no fact: blank, or the bare `-` the empty templates leave behind. */
function isPlaceholder(line: string): boolean {
  return /^\s*(?:[-*]\s*)?$/.test(line);
}

function isBullet(line: string): boolean {
  return /^\s*[-*]\s+\S/.test(line);
}

type Section = { headingPath: string; title: string; lines: string[] };

function sections(body: string): Section[] {
  const out: Section[] = [];
  const stack: { level: number; title: string }[] = [];
  let current: Section = { headingPath: "", title: "", lines: [] };
  let fenced = false;

  for (const line of body.split(/\r?\n/)) {
    if (/^\s*```/.test(line)) fenced = !fenced;
    const heading = fenced ? null : /^(#{1,6})\s+(.+?)\s*#*\s*$/.exec(line);
    if (heading) {
      out.push(current);
      const level = heading[1]?.length ?? 1;
      while (stack.length > 0 && (stack.at(-1)?.level ?? 0) >= level) {
        stack.pop();
      }
      const title = heading[2] ?? "";
      stack.push({ level, title });
      current = {
        headingPath: stack.map((entry) => entry.title).join(" > "),
        title,
        lines: [],
      };
    } else {
      current.lines.push(line);
    }
  }
  out.push(current);
  return out;
}

/** Pack lines into pieces of at most `maxChars`, breaking on line boundaries where it can. */
function pack(lines: string[], maxChars: number): string[] {
  const pieces: string[] = [];
  let buffer: string[] = [];
  let size = 0;
  const flush = () => {
    const text = buffer.join("\n").trim();
    if (text !== "") pieces.push(text);
    buffer = [];
    size = 0;
  };
  for (const line of lines) {
    // A single line longer than the budget is cut rather than dropped or left to blow the limit.
    for (let start = 0; start === 0 || start < line.length; start += maxChars) {
      const part = line.slice(start, start + maxChars);
      if (size + part.length + 1 > maxChars && size > 0) flush();
      buffer.push(part);
      size += part.length + 1;
    }
  }
  flush();
  return pieces;
}

export type ChunkedDocument = {
  chunks: Chunk[];
  /** Citation lines collected from source sections, kept for the answer, not for the index. */
  sources: string[];
};

type Draft = { headingPath: string; text: string };

/**
 * Chunk Markdown by heading.
 *
 * - Each chunk keeps its heading path so a citation can point at a section.
 * - Sections with no facts (empty templates) and to-do sections produce nothing.
 * - In a source section, bullets are citations and go to `sources`; any plain paragraph there is a
 *   fact that was pasted under the wrong heading, and is indexed under the section's parent.
 * - A section shorter than `minChars` joins the chunk before it, its heading kept inline.
 */
export function chunkDocument(
  body: string,
  options: { maxChars?: number; minChars?: number } = {},
): ChunkedDocument {
  const maxChars = options.maxChars ?? DEFAULT_MAX_CHARS;
  const minChars = options.minChars ?? DEFAULT_MIN_CHARS;
  const drafts: Draft[] = [];
  const sources: string[] = [];

  for (const section of sections(body)) {
    if (TODO_HEADING.test(section.title)) continue;

    let lines = section.lines;
    let headingPath = section.headingPath;
    let label = section.title;
    if (SOURCE_HEADING.test(section.title)) {
      label = "";
      for (const line of lines) {
        if (isBullet(line))
          sources.push(line.replace(/^\s*[-*]\s+/, "").trim());
      }
      lines = lines.filter((line) => !isBullet(line));
      headingPath = headingPath.split(" > ").slice(0, -1).join(" > ");
    }
    if (lines.every(isPlaceholder)) continue;

    for (const piece of pack(lines, maxChars)) {
      if (piece.split("\n").every(isPlaceholder)) continue;
      const previous = drafts.at(-1);
      const inline = label === "" ? piece : `${label}: ${piece}`;
      if (
        piece.length < minChars &&
        previous &&
        previous.text.length + inline.length + 2 <= maxChars
      ) {
        previous.text = `${previous.text}\n\n${inline}`;
      } else {
        drafts.push({ headingPath, text: piece });
      }
    }
  }

  return {
    chunks: drafts.map((draft, ordinal) => ({
      ordinal,
      headingPath: draft.headingPath,
      text: draft.text,
      textHash: sha256(draft.text),
      tokenCount: estimateTokens(draft.text),
    })),
    sources,
  };
}

export function chunkMarkdown(
  body: string,
  options: { maxChars?: number; minChars?: number } = {},
): Chunk[] {
  return chunkDocument(body, options).chunks;
}

/**
 * What the embedding model sees. The scope line comes first: a chunk that only says "hồ sơ, thẻ,
 * phí → quầy S1.03" means nothing until the vector also knows it belongs to Sapphire 1, S1.01.
 */
export function embeddingInput(
  chunk: Chunk,
  documentTitle: string,
  scopePath = "",
): string {
  const heading = chunk.headingPath.startsWith(`${documentTitle} > `)
    ? chunk.headingPath.slice(documentTitle.length + 3)
    : chunk.headingPath === documentTitle
      ? ""
      : chunk.headingPath;
  const header = [scopePath, documentTitle, heading]
    .filter((part) => part !== "")
    .join(" | ");
  return `[${header}]\n${chunk.text}`;
}
