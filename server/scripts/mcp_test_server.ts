/**
 * A small MCP server for trying an external connection of management's agents on one machine.
 *
 *   cd server && MCP_TEST_TOKEN=<any text> bun scripts/mcp_test_server.ts
 *
 * Serves http://127.0.0.1:8799/mcp. It offers one tool that reads (a handbook lookup) and one the
 * server itself marks destructive, so both sides of the administrator's choice can be seen. The tool
 * host reaches a plain http address only when TECHNICAL_CONNECTIONS_HTTP_ORIGINS names it.
 * Not part of any deployment.
 */
import { McpServer } from "@modelcontextprotocol/sdk/server/mcp.js";
import { WebStandardStreamableHTTPServerTransport } from "@modelcontextprotocol/sdk/server/webStandardStreamableHttp.js";
import { z } from "zod";

const token = process.env.MCP_TEST_TOKEN?.trim() ?? "";
const port = Number(process.env.MCP_TEST_PORT ?? 8799);

const handbook: Record<string, string> = {
  "thang máy":
    "Thang máy: bảo trì định kỳ ngày 15 hằng tháng, 09:00-11:00, mỗi lần dừng một thang. Mã quy trình QT-TM-07.",
  "bể bơi":
    "Bể bơi: thay nước và vệ sinh bộ lọc vào thứ Hai đầu tháng, đóng cửa 06:00-12:00. Mã quy trình QT-BB-03.",
  "máy phát":
    "Máy phát điện dự phòng: chạy thử không tải 15 phút vào sáng thứ Bảy hằng tuần. Mã quy trình QT-MP-02.",
};

function server() {
  const mcp = new McpServer({ name: "so-tay-van-hanh", version: "1.0.0" });
  mcp.registerTool(
    "tra_cuu_so_tay",
    {
      description:
        "Tra cứu sổ tay vận hành nội bộ của Ban quản lý theo chủ đề (ví dụ: thang máy, bể bơi, máy phát). Trả về lịch và mã quy trình.",
      inputSchema: { chu_de: z.string().describe("Chủ đề cần tra, bằng tiếng Việt") },
      annotations: { readOnlyHint: true },
    },
    async ({ chu_de }) => {
      const found = Object.entries(handbook).filter(([topic]) =>
        chu_de.toLowerCase().includes(topic),
      );
      return {
        content: [
          {
            type: "text",
            text: found.length
              ? found.map(([, text]) => text).join("\n")
              : `Sổ tay không có mục nào về "${chu_de}".`,
          },
        ],
      };
    },
  );
  mcp.registerTool(
    "xoa_muc_so_tay",
    {
      description: "Xóa một mục khỏi sổ tay vận hành.",
      inputSchema: { chu_de: z.string() },
      annotations: { destructiveHint: true },
    },
    async () => ({
      content: [{ type: "text", text: "Máy chủ thử không xóa gì." }],
      isError: true,
    }),
  );
  return mcp;
}

Bun.serve({
  hostname: "127.0.0.1",
  port,
  async fetch(request) {
    if (new URL(request.url).pathname !== "/mcp")
      return new Response("Not found", { status: 404 });
    if (token && request.headers.get("authorization") !== `Bearer ${token}`)
      return new Response("Unauthorized", { status: 401 });
    // Stateless: one transport and one server per request, as the platform's client expects.
    const transport = new WebStandardStreamableHTTPServerTransport({
      sessionIdGenerator: undefined,
    });
    await server().connect(transport);
    return transport.handleRequest(request);
  },
});
console.log(`MCP test server on http://127.0.0.1:${port}/mcp`);
