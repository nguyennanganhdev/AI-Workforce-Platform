# Q02 — Danh sách port backend cần nối cho 14 technical tools (bản gộp)

- **Từ:** Team Quang (tool kỹ thuật), task Q01/Q02.
- **Gửi:** Team Chiến.
- **Ngày:** 01/10/2026.
- **Thay cho:** [technical-tools-backend-ports.md](technical-tools-backend-ports.md) (Giáp Hoàng Thịnh, bản cho 7 tool đầu). Bản đó viết cho bộ khung đã được gộp vào bộ khung hiện tại; mọi ý của nó được giữ dưới đây, ánh xạ sang tên port đang có trong code.
- **Chi tiết từng đợt:** các file `Q02-*.md` khác trong thư mục này.

Module export mọi thứ tại `server/src/technical-tools/index.ts`. Điểm vào duy nhất là `createTechnicalToolCaller(dependencies)`, trả về hàm nhận `{ name, args, botId, actorId }` và trả envelope dạng chuỗi JSON.

## 1. Port bắt buộc

| # | Port | Trong code | Việc Chiến cần làm | Ý từ bản của Thịnh |
|---|---|---|---|---|
| 1 | Danh tính đã xác thực | `ContextResolver` → `ResolvedIdentity` (`contracts/context.ts`) | Từ `botId`/`actorId` đã xác minh, trả tenant, workspace, principal, `user_id`, `role_code`, run, trace và **`grants`** | Không lấy tenant/actor/role từ input của agent |
| 2 | Quyền theo scope | `BuildingAccessPort` (`ports/building-access.ts`) | Có thể dùng sẵn `createScopeBuildingAccess(createDbScopeReadPort(session))`, hoặc thay bằng resolver của backend | `BuildingAccessPort` |
| 3 | Phiên DB theo tenant | `TenantSession` (`adapters/db/tenant-session.ts`) | Cấp `read`/`write` chạy trong transaction đã đặt `app.tenant_id`, trên role chỉ có các quyền ở mục 3 | `TenantReadSessionPort` |
| 4 | Phạm vi bao phủ tòa nhà | `ScopeReadPort` (`createDbScopeReadPort`) | Không cần làm thêm nếu cấp `SELECT` trên `buildings`, `access_scopes` | `CoveringScopesPort` |
| 5 | Ghi audit | `AuditSink` | Ghi mỗi lời gọi, kể cả lời gọi bị từ chối; lỗi ghi audit thì tool không trả dữ liệu | Gateway có audit |
| 6 | Mount | `createTechnicalToolCaller` | Nối vào `/api/agent-tools/call` (đã có sẵn chỗ `DeploymentToolCaller`) **hoặc** `/internal/tools/*` theo kế hoạch tổng — **cần Chiến chốt một đường** | Gateway `/internal/tools/*` |

`grants` có dạng:

```ts
grants: { capability: string; scope_ids: string[] }[]
// scope_ids là access_scopes.id: tòa, zone, site, hoặc cả tenant
```

Host chỉ dùng scope của **đúng capability tool cần**. Có quyền đọc SOP trên cả site không có nghĩa là đọc được lịch cắt điện ở đó.

## 2. Nguồn dữ liệu còn là POC

| Port | Đang dùng | Cần thay bằng | Ý từ bản của Thịnh |
|---|---|---|---|
| `AssetReadPort`, `SensorReadPort`, `MaintenanceReadPort` | adapter in-memory, không tự chứa dữ liệu | bảng hoặc adapter BMS/IoT, theo `Q02-sop-asset.md`, `Q02-sensor-history.md` | Mục 6 |
| `SopProfilePort` | in-memory | mã sự cố và tiêu chí nghiệm thu trong schema | Mục 5 (truy xuất SOP đã đọc DB thật) |
| `MaintenanceStore`, `MeasurementStore`, `ExecutorResultStore`, `IdempotencyStore` | in-memory | bảng ghi **cùng transaction** với khóa chống trùng, theo `Q02-measurement-result.md`, `Q02-verify-append.md` | Mục 7 |
| `ApprovalRequestStore`, `VendorCatalogPort` | in-memory | bảng request chung, bảng nhà thầu, theo `Q02-isolation-restriction.md`, `Q02-entry-vendor.md` | — |

## 3. Quyền của role chạy tool

```sql
GRANT SELECT ON buildings, access_scopes, service_interruptions, interruption_scopes,
  knowledge_bases, knowledge_documents, document_versions, document_scopes, document_acl,
  tickets, work_orders, work_assignments, staff_profiles, evidence_items, files,
  units, unit_residents, work_approvals TO <runtime_role>;
GRANT INSERT ON work_approvals, service_interruptions, interruption_scopes TO <runtime_role>;
```

Không UPDATE, không DELETE trên bảng nào. Đây là lớp chặn cuối cùng để agent không thể tự duyệt đề nghị, tự kích hoạt lịch cắt hay tự đổi ưu tiên ticket. Các test DB kiểm tra từng điều này.

## 4. Kiểm thử

882 test trong `server/tests/technical-tools/`, chạy trên PGlite (baseline thật) và PostgreSQL 17:

```
bun test server/tests/technical-tools
TEST_DATABASE_URL=postgres://... bun test server/tests/technical-tools
```
