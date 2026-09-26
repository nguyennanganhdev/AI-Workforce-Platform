# security-mcp

Owner: **Vinhomes / Integrations**.

Tool nghiệp vụ security. Chưa có MCP server chạy được.

Khi triển khai: `src/index.ts` đăng ký transport; `src/tools.ts` khai báo tool;
`src/client.ts` gọi service API; `src/providers/` chứa mock-provider và real-provider.
Mock phải được chọn rõ trong môi trường test, không làm fallback khi production lỗi.

Không truy cập PostgreSQL/Qdrant trực tiếp. Dùng service credentials.
WRITE phải xác thực execution grant do domain cấp (tenant, action, payload binding,
expiry, replay/idempotency); tool không tự quyết approval.

