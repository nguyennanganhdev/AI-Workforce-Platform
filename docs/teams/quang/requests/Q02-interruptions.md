# Q02 — Yêu cầu tích hợp cho hai tool gián đoạn điện nước

- **Từ:** Team Quang (tool kỹ thuật), task Q01/Q02.
- **Gửi:** Team Chiến (mục 1–5), anh Quang (mục 6).
- **Ngày:** 30/09/2026.
- **Liên quan:** `technical.get_active_outage`, `utility_schedule.read` (`docs/teams/quang/tools.md` §3.5, §3.6).

Hai tool đã chạy được và có test trên schema thật. Các mục dưới đây là phần nằm ngoài vùng sở hữu của team Quang nên team không tự sửa. Không mục nào chặn việc làm tiếp 12 tool còn lại.

## 1. Nối tool vào server

**Owner:** Chiến (`server/src/index.ts`).

`createApp` đã có tham số `deploymentToolCaller?: DeploymentToolCaller` (`server/src/app.ts:308`), và route `/api/agent-tools/call` gọi nó trước khi rơi xuống plugin store. Team Quang cung cấp đúng kiểu đó:

```ts
import {
  createDbInterruptionReadPort,
  createTechnicalToolCaller,
  systemClock,
  technicalToolsDatabase,
} from "./technical-tools";

const technicalTools = createTechnicalToolCaller({
  interruptions: createDbInterruptionReadPort(technicalToolsDatabase(database)),
  clock: systemClock,
  contextResolver, // mục 2
  audit,           // mục 3
});
```

Hàm trả `null` khi tên tool không thuộc team Quang, nên nếu sau này có thêm caller khác thì nối chuỗi: gọi lần lượt, lấy kết quả khác `null` đầu tiên.

Tên tool: model được chào tên `technical__get_active_outage` và `utility_schedule__read` (tên model không được chứa dấu chấm). Route hiện tại đổi `__` đầu tiên thành `/`; tool nhận cả ba cách viết. Test `outage-schedule.contract.test.ts` dùng chính `parseAgentToolCallInput` để giữ hai bên khớp nhau.

Danh mục tool dạng JSON Schema cho runtime Python của Đông: `describeTechnicalTools()`.

## 2. `ContextResolver` thật

**Owner:** Chiến (C06 — runtime gateway).

```ts
type ContextResolver = (caller: {
  botId: string;
  actorId: string;
  initiator?: AuditInitiator;
}) => Promise<ResolvedIdentity | null>;

type ResolvedIdentity = {
  tenant_id: string;            // UUID
  workspace_id?: string;        // UUID
  principal_id: string;
  source_run_id: string;        // UUID, agent_runs.id
  trace_id: string;             // 1..128 ký tự
  agent_version: string;        // 1..128 ký tự
  grants: {                     // cập nhật 01/10/2026, xem Q02-backend-ports.md
    capability: string;         // ví dụ "interruption:read"
    scope_ids: string[];        // UUID trong access_scopes: tòa, zone, site hoặc cả tenant
  }[];
};
```

Yêu cầu:

- `botId`/`actorId` đã được route xác minh bằng token agent và run assertion; resolver suy ra tenant, run và quyền từ đó, không từ body.
- Trả `null` khi không xác định được danh tính. Host sẽ từ chối `FORBIDDEN` và vẫn ghi audit.
- `grants`: mỗi capability lấy từ tool grant của agent release đang chạy, kèm các `access_scopes` mà principal có quyền (tính từ `scoped_user_roles` còn hiệu lực). Host hỏi `BuildingAccessPort` xem scope của **đúng capability tool cần** có bao phủ `building_id` trong input không; quyền của capability này không cho mượn sang capability khác.

Trong test, vai trò này do `server/tests/technical-tools/support/harness.ts` đóng thế. Đây là chỗ giả lập duy nhất trong đường chạy.

## 3. Ghi audit

**Owner:** Chiến (`server/src/audit.ts`).

Mỗi lời gọi tool sinh một `ToolAuditEntry` (`server/src/technical-tools/ports/audit-sink.ts`): tên và phiên bản tool, trạng thái, `trace_id`, `agent_version`, tenant, principal, run, bot, actor, initiator, `building_id`, số bản ghi trả về, thời lượng, thời điểm. Không chứa dữ liệu kết quả.

`auditEventTypes` là danh sách đóng và chưa có loại cho tool kỹ thuật. Đề xuất thêm ba loại:

| Loại | Khi nào |
|---|---|
| `technical_tool.called` | trạng thái `OK`, `NEEDS_INPUT`, `STALE_DATA`, `PENDING_APPROVAL` |
| `technical_tool.refused` | `FORBIDDEN`, `INVALID_INPUT` |
| `technical_tool.failed` | `INTERNAL_ERROR`, `NOT_FOUND`, `CONFLICT` |

Lưu ý hành vi: nếu ghi audit thất bại, host trả `INTERNAL_ERROR` và **không trả dữ liệu**, theo đúng nguyên tắc của gateway hiện có là không có hành động nào thiếu dòng audit.

## 4. Quyền database của runtime

**Owner:** Chiến + Team 5 (P02).

Hai tool chỉ cần `SELECT` trên bốn bảng: `buildings`, `access_scopes`, `service_interruptions`, `interruption_scopes`. Role kết nối phải không phải superuser và không có `BYPASSRLS`, vì RLS không áp dụng cho superuser kể cả khi đã `FORCE`.

Adapter đặt `app.tenant_id` trong một transaction chỉ đọc cho mỗi lời gọi, theo cách `withDatabaseScope` đang làm. Test đã kiểm chứng: bỏ bước này thì role runtime không đọc được dòng nào.

## 5. Khoảng trống schema

**Owner:** Chiến (`server/src/db/**`). Team Quang không tự sửa; tool đã xử lý phòng thủ ở phía mình.

| # | Hiện trạng | Hệ quả | Đề xuất |
|---|---|---|---|
| 5.1 | `service_interruptions` chỉ có CHECK cho `utility` và `status`. Quy tắc `planned_end > planned_start` chỉ nằm trong từ điển dữ liệu | Có thể tồn tại dòng kết thúc trước khi bắt đầu. Tool đang bỏ qua các dòng này | Thêm CHECK bằng migration tăng dần |
| 5.2 | Không có ràng buộc "phải có approval đã duyệt trước khi `active`" | Database không chặn được một đợt cắt `active` với approval còn `pending` | Trigger hoặc kiểm tra ở service |
| 5.3 | `work_approvals.kind` chỉ có `customer_repair`, `management_water_shutdown`, `customer_completion` | Đợt cắt **điện** phải gắn vào approval loại nước. Dữ liệu mẫu đang làm vậy và ghi chú rõ | Thêm loại cho cô lập điện |
| 5.4 | `work_order_id` và `approval_id` đều NOT NULL | Lịch bảo trì chung của tòa nhà buộc phải có work order mang | Xác nhận đây là chủ ý, hoặc cho phép lịch không gắn work order |
| 5.5 | Không có cột giờ khôi phục đã công bố | Tool trả `published_eta` = `planned_end` | Xác nhận cách hiểu này, hoặc thêm cột |

Mục 5.3 và 5.4 cũng là lý do nhánh điện của `utility_isolation.request` chưa thể tạo dòng `service_interruptions` như `tools.md` §6.1 mô tả.

## 6. Điểm cần anh Quang chốt trong `tools.md`

| # | Vấn đề | Đang làm |
|---|---|---|
| 6.1 | Enum `status` ở §1.3 không có `INVALID_INPUT`, trong khi §3.6 và §7 nói input sai "trả `INVALID_INPUT`" | Đã thêm `INVALID_INPUT` vào enum status |
| 6.2 | `get_active_outage` với đợt `approved`/`notified` có khung giờ dự kiến phủ thời điểm hỏi | Trả về với đúng trạng thái đó, không đổi thành `active` |
| 6.3 | `get_active_outage` với đợt `active` đã quá `planned_end` mà chưa khôi phục | Vẫn trả về; `published_eta` giữ nguyên giờ đã công bố |
| 6.4 | Tòa nhà ngoài quyền, thuộc tenant khác, hoặc không tồn tại | Cả ba trả `FORBIDDEN` giống hệt nhau |

## Dữ liệu mẫu và test

- Dữ liệu: `server/tests/technical-tools/fixtures/` — thế giới mẫu (2 tenant, 4 tòa), 10 đợt cắt, 10 ca theo mức độ 1/2/3.
- Test: 125 test trong `server/tests/technical-tools/`.

```
bun test server/tests/technical-tools
```

Mặc định chạy trên PGlite nạp nguyên baseline `0000_grey_blockbuster.sql`, không cần cài gì thêm. Khi có `TEST_DATABASE_URL`, cùng bộ test chạy trên PostgreSQL thật: tự tạo một database tạm bên cạnh, migrate bằng migrator của Drizzle, đọc qua `createDatabase` của server, rồi xóa database tạm. Đã chạy qua cả hai cách (PostgreSQL 17.11).
