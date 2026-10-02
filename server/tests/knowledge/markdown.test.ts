import { describe, expect, test } from "bun:test";
import {
  chunkDocument,
  chunkMarkdown,
  embeddingInput,
  parseFrontMatter,
} from "../../src/knowledge/markdown";

const long = (label: string) =>
  `${label} ${"nội dung đủ dài để không bị gộp. ".repeat(6)}`;

describe("parseFrontMatter", () => {
  test("reads the YAML block and returns the body after it", () => {
    const parsed = parseFrontMatter(
      "---\ntrang_thai: da-thu-thap-mot-phan\nphan_khu: The Sapphire\n---\n\n# Tiêu đề\nNội dung",
    );
    expect(parsed.meta.trang_thai).toBe("da-thu-thap-mot-phan");
    expect(parsed.body).toContain("# Tiêu đề");
    expect(parsed.body).not.toContain("trang_thai");
  });

  test("a file with no front matter has empty metadata", () => {
    expect(parseFrontMatter("# Chỉ có nội dung").meta).toEqual({});
  });

  test("broken YAML does not throw", () => {
    expect(parseFrontMatter("---\n: : [\n---\nnội dung").meta).toEqual({});
  });

  test("decomposed Vietnamese is normalised to NFC", () => {
    const decomposed = "phí".normalize("NFD");
    expect(decomposed).not.toBe("phí");
    expect(parseFrontMatter(decomposed).body).toBe("phí");
  });
});

describe("chunkDocument", () => {
  test("splits by heading and keeps the heading path", () => {
    const chunks = chunkMarkdown(
      `# Xử lý\n\n## Thang máy\n${long("Giữ liên lạc cabin.")}\n\n## Mùi gas\n${long("Không bật công tắc.")}`,
    );
    expect(chunks.map((chunk) => chunk.headingPath)).toEqual([
      "Xử lý > Thang máy",
      "Xử lý > Mùi gas",
    ]);
    expect(chunks.map((chunk) => chunk.ordinal)).toEqual([0, 1]);
  });

  test("a short section joins the chunk before it with its heading inline", () => {
    const chunks = chunkMarkdown(
      `## Thang máy\n${long("Giữ liên lạc cabin.")}\n\n## Mùi gas\nKhông bật công tắc.`,
    );
    expect(chunks).toHaveLength(1);
    expect(chunks[0]?.text).toContain("Mùi gas: Không bật công tắc.");
  });

  test("an empty template yields no chunk", () => {
    expect(
      chunkMarkdown("# Hướng dẫn agent\n\n## Fact\n\n-\n\n## Nguồn\n\n-\n"),
    ).toEqual([]);
  });

  test("to-do sections are dropped, conflict notes are kept", () => {
    const { chunks } = chunkDocument(
      "## Fact\nChưa có sơ đồ.\n\n## Cần thu thập\n- Ảnh sơ đồ thoát nạn\n\n## Việc team phải thu\n- Số trực\n\n## Thông tin vận hành cần bổ sung\n| Bể bơi | |\n\n## Chưa thống nhất / còn thiếu\n- Số tầng R1.03 khác nhau giữa Z1 và Z3.",
    );
    const text = chunks.map((chunk) => chunk.text).join("\n");
    expect(text).not.toContain("Ảnh sơ đồ");
    expect(text).not.toContain("Số trực");
    expect(text).not.toContain("Bể bơi");
    expect(text).toContain("Số tầng R1.03 khác nhau");
  });

  test("bullets under Nguồn are citations; a paragraph pasted there is still a fact", () => {
    const { chunks, sources } = chunkDocument(
      `# Số trực — S1.01\n\n## Cách gọi\n${long("Ứng dụng.")}\n\n## Nguồn\n\n- Ghi nhận team 29/09/2026\n- thuenhavinhomesoceanpark.com\n\nAn ninh cao tầng: 0858 001 080.`,
      { minChars: 0 },
    );
    expect(sources).toEqual([
      "Ghi nhận team 29/09/2026",
      "thuenhavinhomesoceanpark.com",
    ]);
    const fact = chunks.find((chunk) => chunk.text.includes("0858 001 080"));
    expect(fact?.headingPath).toBe("Số trực — S1.01");
    expect(
      chunks.some((chunk) => chunk.text.includes("Ghi nhận team 29/09")),
    ).toBe(false);
  });

  test("a long section is cut under the budget and nothing is lost", () => {
    const lines = Array.from(
      { length: 40 },
      (_, i) => `Dòng số ${i} có nội dung.`,
    );
    const chunks = chunkMarkdown(`## Dài\n${lines.join("\n")}`, {
      maxChars: 200,
      minChars: 0,
    });
    expect(chunks.length).toBeGreaterThan(1);
    expect(chunks.every((chunk) => chunk.text.length <= 200)).toBe(true);
    expect(chunks.map((chunk) => chunk.text).join("\n")).toContain(
      "Dòng số 39",
    );
  });

  test("a heading inside a code fence is not a heading", () => {
    const chunks = chunkMarkdown("## Thật\n```\n# giả\n```\nnội dung");
    expect(chunks).toHaveLength(1);
    expect(chunks[0]?.headingPath).toBe("Thật");
  });
});

describe("embeddingInput", () => {
  test("puts scope, title and section in front of the text without repeating the title", () => {
    const [chunk] = chunkMarkdown(
      "# Số trực — S1.01\n\n## Đầu mối khác\nHồ sơ, thẻ, phí → quầy S1.03",
    );
    expect(
      embeddingInput(
        chunk!,
        "Số trực — S1.01",
        "Vinhomes > sapphire > sapphire-1 > S1.01",
      ),
    ).toBe(
      "[Vinhomes > sapphire > sapphire-1 > S1.01 | Số trực — S1.01 | Đầu mối khác]\nHồ sơ, thẻ, phí → quầy S1.03",
    );
  });
});
