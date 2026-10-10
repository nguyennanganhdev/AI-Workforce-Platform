# Trạng thái — Nguyễn Phương Đông

Ngày kiểm tra: 2026-10-10. Branch: `dev/TeamDong/dongnpp`.
Commit được kiểm tra: `ae0f3ccb457cb06a48db005dd4dd7c209927ee1e`.

## Tiến độ

**Dừng ở Bước 1 của kế hoạch endpoint MCP để chờ bàn giao contracts/SDK từ Nguyễn Chí Hoàng**, theo yêu cầu của người dùng: dừng nếu cần phần việc của người khác hoặc vượt phạm vi. Chưa đánh dấu hoàn thành NPD-01–NPD-12.

Đã đối chiếu kế hoạch endpoint được cung cấp với code và handoff trong checkout này:

- `pyproject.toml` vẫn yêu cầu `mcp<2.0.0`.
- Wrapper `agentscope.mcp.MCPClient` đã có HTTP/SSE/STDIO, connect/close/reconnect và runtime headers. `list_raw_tools()` hiện đọc một trang; chưa có public API cho protocol/capability negotiation, `skills/list`, `skills/get`, `resources/read`.
- Contracts đã có `Scope`, `ToolDescriptor`, `RegistryPort`, `AsyncProtocolPort`, `JobPort` và `UnitOfWork`. Chưa có DTO/port đọc skill, `SecretStorePort`; `McpConnection.mcp_id` còn bắt buộc, chưa biểu diễn connection nhập endpoint riêng không thuộc catalog chung.
- Foundation chưa có implementation session/uow/jobs/secret store/outbound policy trong checkout này. Frontend `shared/` mới có contracts, chưa có transport/token provider. MCP mock HTTP chung và truy vấn impact của Lifecycle chưa được bàn giao ở đây.

Các thiếu hụt Foundation/UI/mock là điểm chờ của các bước sau; không yêu cầu hoàn thành toàn bộ các module đó để bắt đầu lại Bước 1 sau khi contracts/SDK sẵn sàng.

## Phạm vi và cách tiếp tục

Chỉ sửa backend `registry/`, frontend `features/workforce/integrations/`, tests `tests/workforce/registry/` và handoff cá nhân. Không sửa contracts, core MCP, dependency, migration, root routing hoặc fixture chung.

Tái sử dụng `MCPClient`/`HttpMCPConfig`, `MCPCard`/`render_mcp()` qua adapter, DTO/ports chung, SQL session của Foundation, `SchemaForm` và UI primitives hiện có. Không tạo transport MCP, secret store, token refresh hay bộ contracts thay thế.

Yêu cầu tích hợp và điều kiện tiếp tục: [INTEGRATION_REQUEST_NPD_ENDPOINT.md](INTEGRATION_REQUEST_NPD_ENDPOINT.md).

## Bằng chứng và phần còn thiếu

- Thay đổi lượt này chỉ gồm README, STATUS và integration request trong handoff của Đông; chưa sửa code production hoặc test.
- Đã kiểm tra Git status, ownership, các exports/implementation hiện có và `git diff --check`.
- Chưa chạy unit/regression, frontend build/lint, HTTP mock/E2E hoặc PostgreSQL vì triển khai đã dừng tại dependency gate. Không có bằng chứng endpoint → discovery → UI; không coi scaffold hoặc kiểm tra tĩnh là hoàn thành tích hợp.

Tiếp tục từ Bước 1 khi contracts/SDK đã được bàn giao và có trong checkout; kiểm tra lại diff/exports trước khi code. Các yêu cầu bên dưới là tài liệu bàn giao, chưa gửi thông báo cho thành viên khác.
