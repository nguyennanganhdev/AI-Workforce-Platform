# Integration request — NPD endpoint MCP, discovery và skills

Ngày: 2026-10-10. Producer: Registry / Nguyễn Phương Đông.
Baseline: `ae0f3ccb457cb06a48db005dd4dd7c209927ee1e`.
Trạng thái: **chờ bàn giao; chưa triển khai**. Đề xuất dưới đây chưa phải contract đã chốt.

## Gate hiện tại — Nguyễn Chí Hoàng

Liên quan NPD-01/03/07/10–12 và Bước 1 của kế hoạch endpoint được người dùng cung cấp.

### SDK/core MCP

- Repo đang pin `mcp<2.0.0`. Cần owner nâng SDK theo kế hoạch, cập nhật các caller bắt buộc và giữ interface công khai của wrapper AgentScope. Registry sẽ dùng wrapper đó, không import session private hoặc dựng transport thứ hai.
- Bàn giao API công khai để đọc protocol/capabilities đã negotiate, discovery tools đủ trang, `skills/list`, `skills/get` và `resources/read`. Registry tạo client không có `enable_tools`/`disable_tools` của agent. Hiện `list_raw_tools()` chỉ gọi `session.list_tools()` một lần, nên chưa đủ cho discovery phân trang.
- Kiểm chứng HTTP/SSE/STDIO, reconnect/cleanup, runtime headers, tool adapters và workspace callers trước bàn giao. Có sẵn các regression tại `tests/mcp_*_test.py`, `tests/service_mcp_render_test.py` và workspace tests để tái sử dụng.

Nguồn đã đối chiếu: [MCP Python SDK migration guide](https://py.sdk.modelcontextprotocol.io/migration/) mô tả thay đổi types/client API/pagination của v2; [Skills Extension](https://skills.extensions.modelcontextprotocol.io/specification/stable/skills) quy định base protocol `2026-07-28` trở lên. Không chỉ đổi pin dependency rồi coi migration đã hoàn tất.

### Contracts dùng chung

Owner cập nhật Python exports, schema và TypeScript tương ứng; Đông chỉ tiêu thụ sau bàn giao.

- Hiện `McpConnection.mcp_id: OpaqueId` bắt buộc. Đề nghị `mcp_id: OpaqueId | None = None`: `null` cho connection endpoint riêng; ID có giá trị vẫn tham chiếu definition catalog. Không tạo definition toàn hệ thống cho endpoint nhập tay. Owner chốt metadata tên/cấu hình endpoint và response protocol/capability status, tool/skill counts.
- Hiện `ConnectionStatus` chưa có `auth_required`/`degraded`; đề nghị bổ sung để API phản ánh kết quả thật theo kế hoạch.
- Hiện `RegistryPort` chưa có API skill. Đề nghị bổ sung DTO snapshot/detail và hai phương thức, giữ nguyên các phương thức tool đang có:

```python
async def list_connection_skills(
    self, scope: Scope, connection_id: OpaqueId,
    cursor: OpaqueId | None = None,
) -> tuple[tuple[SkillDescriptor, ...], OpaqueId | None]: ...

async def get_skill_detail(
    self, scope: Scope, connection_id: OpaqueId, uri: str,
) -> SkillDetail: ...
```

`SkillDescriptor`/`SkillDetail` là tên đề nghị, hiện chưa tồn tại. Metadata cần connection nguồn + URI, name/description, snapshot version/hash, manifest resources với digest/size khi có và trạng thái nội dung dynamic. Detail đọc qua MCP, không dùng URI làm URL tải tùy ý; không tự kích hoạt skill trong agent.

Ví dụ đầu vào đề nghị cho endpoint riêng (không phải response/DTO đã được export):

```json
{"name":"Demo MCP","endpoint":"http://localhost:8765/mcp"}
```

Ví dụ bị từ chối: cùng body trên nhưng thêm `manager_account_id` của người khác. Scope luôn lấy từ identity đã xác minh, không nhận owner từ body. Endpoint local chỉ được phép theo outbound policy của Foundation trong demo và phải truy cập được từ backend.

Điều kiện bàn giao cần tests: connection nhập endpoint không làm tăng catalog chung; cùng area khác manager không đọc connection/skill/credential của nhau; hai server trùng tên skill vẫn tách theo connection + URI; tools-only server vẫn hoạt động; unknown fields/URI ngoài connection bị từ chối; API/log không lộ secret. Đây là checks cần thực hiện khi triển khai, chưa chạy trong lượt rà soát này.

## Các gate sau — chờ tại bước sử dụng, không làm thay owner

- **Chí Hoàng / Foundation — Bước 1–2:** SQL engine/session/uow và migration Registry thật; `SecretStorePort.put(scope, secret_input) -> credential_ref`, `resolve(scope, credential_ref)`, `revoke(scope, credential_ref)` theo mục 6.7; outbound URL policy; durable `JobPort`/worker registration và cơ chế publish sau commit. `JobPort` hiện mới có interface. Cần transaction persist connection/revision + enqueue, không giữ transaction khi chờ network và chặn job cũ ghi đè config/disable mới. Schema Registry sẽ được Đông bàn giao khi có đầu vào session/contracts; chưa đề nghị migration cho schema chưa tồn tại.
- **Chí Hoàng / frontend — Bước 5:** export transport/token provider từ `features/workforce/shared/`; tích hợp root route sau khi Đông bàn giao `WorkforceIntegrationsPage` qua `index.ts`. Không bê transport/token refresh cũ vào feature hoặc sửa global routing từ lane Registry.
- **Dũng — nghiệm thu HTTP:** bàn giao mock MCP process/service `/mcp`, dataset tools + Skills Extension tương thích, pagination/failure cases, chọn port/readiness và hướng dẫn local/Docker. Registry không sửa `tests/workforce/fixtures/` hay `e2e/` chung. Fake port unit test không thay bằng chứng network.
- **Tiến Anh — Bước 4:** export truy vấn đọc tham chiếu tool/version theo scope để Registry hiển thị agent bị ảnh hưởng. Chờ owner chốt chữ ký; Registry không đọc trực tiếp bảng Lifecycle.

Không thêm `workflow_state`/`next_action` vào response MCP/tool/skill: các field đó thuộc Customer request/reply. Registry tiếp tục export `create_router(...)`, triển khai `RegistryPort`/`AsyncProtocolPort` trong lane của mình sau khi các gate tương ứng sẵn sàng; không nhận Provider Event HTTP, lưu inbox hoặc cập nhật workflow.

## Điều kiện tiếp tục

Bước 1 bắt đầu lại khi gate SDK/core và contracts ở trên đã được owner bàn giao/tích hợp vào checkout, kèm exports/version và regression tương ứng. Sau đó triển khai Registry bằng thành phần hiện có và tests thuộc lane Đông; đến gate Foundation/UI/mock/impact nào chưa sẵn sàng thì dừng tại đó theo chỉ dẫn của người dùng. Không cần đổi phạm vi sở hữu hoặc tự cherry-pick công việc của owner khác để vượt gate.
