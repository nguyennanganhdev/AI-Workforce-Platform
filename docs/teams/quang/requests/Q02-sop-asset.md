# Q02 (đợt 2) — Yêu cầu tích hợp cho tool tra SOP và đọc hồ sơ thiết bị

- **Từ:** Team Quang (tool kỹ thuật), task Q01/Q02.
- **Gửi:** Team Chiến (mục 1–4), anh Quang (mục 5).
- **Ngày:** 01/10/2026.
- **Liên quan:** `sop_kb.retrieve`, `asset.read` (`docs/teams/quang/tools.md` §3.1, §3.2).
- **Đợt trước:** [Q02-interruptions.md](Q02-interruptions.md). Các yêu cầu ở đó (nối caller vào `createApp`, nơi ghi audit, quyền database) vẫn còn nguyên; file này chỉ nêu phần thêm.

## 1. `ContextResolver` cần thêm hai trường

**Owner:** Chiến (C06 — runtime gateway). Đây là **thay đổi so với hợp đồng ở đợt trước**.

```ts
type ResolvedIdentity = {
  tenant_id: string;
  workspace_id?: string;
  principal_id: string;
  user_id?: string;                                            // MỚI
  role_code?: "admin" | "management" | "staff" | "customer";   // MỚI
  source_run_id: string;
  trace_id: string;
  agent_version: string;
  capabilities: string[];
  allowed_building_ids: string[];
};
```

**Vì sao cần:** `document_acl` cấp quyền theo `principal_kind` là `role`, `user` hoặc `workspace`. Không có `role_code` và `user_id` thì tool không đánh giá được ACL của tài liệu, và mọi lần tra SOP sẽ bị từ chối.

**Yêu cầu:**

- `role_code` là vai trò nghiệp vụ trong scope, lấy từ `scoped_user_roles` còn hiệu lực — không phải role snapshot cũ.
- `user_id` là `users.id` mà run đang phục vụ (`on_behalf_of_user_id` của `agent_runs`).
- Cả hai để tùy chọn vì job chạy theo lịch có service principal và không có người đứng sau. Khi thiếu, tool coi là **không grant nào khớp**, tức là từ chối — không phải mở.

**Capability mới:** `sop:read` và `asset:read`, bên cạnh `interruption:read` đã có.

## 2. Quyền database bổ sung

**Owner:** Chiến + Team 5 (P02).

Role runtime cần thêm `SELECT` trên 5 bảng: `knowledge_bases`, `knowledge_documents`, `document_versions`, `document_scopes`, `document_acl`.

**Không cần** quyền trên `files` và `file_objects`. Tool chỉ đọc metadata tài liệu; nội dung tệp là việc của file service. Test đã kiểm chứng role runtime bị từ chối khi đọc `file_objects`.

## 3. Nguồn dữ liệu còn là POC

**Owner:** Chiến (`server/src/db/**`). Trong lúc chờ, tool chạy trên adapter POC và adapter đó **không tự chứa dữ liệu** — phải được nạp từ bên ngoài, mặc định rỗng, để không deployment nào trả dữ liệu bịa như dữ liệu thật.

### 3.1. Liên kết mã sự cố ↔ tài liệu

`knowledge_documents` không có cột nào nói tài liệu này áp dụng cho mã sự cố nào. Hiện `sop_kb.retrieve` lấy liên kết từ SOP profile (POC).

**Đề xuất:** bảng liên kết `knowledge_document_issue_codes(tenant_id, document_id, issue_code)`, hoặc một cột mảng trên `document_versions` nếu liên kết thay đổi theo phiên bản. Team Quang thiên về bảng liên kết vì một tài liệu phục vụ nhiều mã (ví dụ S3 phục vụ cả rò âm tường và nước thải trào ngược).

### 3.2. Tiêu chí nghiệm thu có cấu trúc

Tiêu chí nghiệm thu hiện nằm trong nội dung tệp trên object storage, không có cột nào. `technical.verify_resolution` sẽ cần chúng ở dạng máy chấm được, không phải văn xuôi.

**Đề xuất:** lưu theo `document_version_id`, mỗi tiêu chí có `id`, `text` và một `check` dạng JSONB theo schema có version. Bốn loại check đang dùng: `checklist` (mã mục checklist), `evidence` (loại ảnh + số tối thiểu), `measurement` (metric, phép so, giá trị, đơn vị), `manual` (chỉ người quyết).

**Vì sao không để LLM đọc văn xuôi:** `general.md` §3.1 cấm agent tự tạo số đo hoặc evidence. Nếu tiêu chí chỉ là câu văn thì kết luận `VERIFIED` rơi vào tay model.

### 3.3. Bảng cho tài sản

Chưa có bảng nào cho thiết bị. Trường tối thiểu `asset.read` cần: `asset_id`, `tenant_id`, `building_id`, `unit_id?`, `type`, `model?`, `location`, `ownership?`, `warranty_until?`, `status`, `updated_at`, và một mốc phiên bản (`etag` hoặc `updated_at`) để ghi provenance.

Ba tool sắp tới (`sensor.read`, `maintenance_history.read`, `maintenance_history.append`) đều tra theo `asset_id`, nên đây là khoảng trống chặn nhiều tool nhất.

### 3.4. Seed 16 mã sự cố

16 mã `TECH.*` của `general.md` §4 hiện là dữ liệu tham chiếu trong code Team Quang ([reference/issue-codes.ts](../../../../server/src/technical-tools/reference/issue-codes.ts)). Đề xuất seed thành `incident_types` để ticket mang được mã này, và để triage policy tham chiếu tới cùng một danh mục.

## 4. Ghi chú về schema tài liệu

Không phải lỗi, nhưng ảnh hưởng cách tool đọc:

- **`document_versions.file_id` là NOT NULL** và trigger `app_validate_file` không cho file ở trạng thái `ready` mà thiếu object gốc đã scan và verify. Nên mỗi phiên bản tài liệu cần một chuỗi storage location → file → file object. Phần seed của test làm đúng chuỗi này; nếu sau này có luồng "nội dung nhân viên gõ trực tiếp" thì cần bàn lại (tài liệu `THIET_KE_HOC_KINH_NGHIEM_SELF_HELP_GIA.md` §5.2 cũng nêu điểm này).
- **`document_scopes.applies_to_descendants`** là cách duy nhất phân biệt "hướng dẫn cho riêng tòa này" với "hướng dẫn cho cả khu". Tool tôn trọng nó. Cần Chiến xác nhận UI cấu hình tài liệu có cho người dùng đặt cột này, vì mặc định là `true` và người cấu hình dễ để nguyên.
- **`knowledge_bases.status`** được tool kiểm tra: tài liệu `published` trong bộ `archived` không được coi là hướng dẫn. Cần xác nhận đây là ý định thiết kế.

## 5. Điểm cần anh Quang chốt trong `tools.md`

| # | Vấn đề | Đang làm |
|---|---|---|
| 5.1 | §3.1 nói `NEEDS_INPUT` khi "query không đủ rõ" nhưng không định nghĩa thế nào là không đủ rõ | Trả `NEEDS_INPUT` khi câu hỏi không còn từ khóa nào sau khi bỏ dấu câu và từ nối |
| 5.2 | Có quy trình hợp lệ nhưng ACL từ chối → `FORBIDDEN`; điều này cho người gọi biết quy trình đó tồn tại | Theo §3.1, trả `FORBIDDEN`. Người gọi đã tự cung cấp mã sự cố và tòa nhà nên không tiết lộ gì thêm. Nếu muốn che thì đổi sang `NOT_FOUND` |
| 5.3 | Nhiều tài liệu cùng mã sự cố nhưng câu hỏi không khớp từ nào | Vẫn trả về, xếp cuối. Bỏ đi sẽ khiến bot không còn hướng dẫn nào |
| 5.4 | §3.2 nói `NEEDS_INPUT` "cùng danh sách candidate tối thiểu" nhưng output schema chỉ có `assets` | Đặt danh sách ứng viên vào `data.assets`, cùng `missing_fields: ["asset_id"]` |
| 5.5 | `asset.read` chấp nhận `asset_type` một mình (không có `asset_id` hay `location`) | Từ chối `INVALID_INPUT`: đó là liệt kê cả tòa, không phải tra cứu |
| 5.6 | Thiết bị `retired` có nên trả về không | Vẫn trả về, kèm `status`. Che đi thì bot không biết máy đã ngừng dùng |

## Dữ liệu mẫu và test

- Dữ liệu: `server/tests/technical-tools/fixtures/sop.ts` (16 tài liệu) và `fixtures/assets.ts` (11 thiết bị).
- Test: 284 test trong `server/tests/technical-tools/`.

```
bun test server/tests/technical-tools
```

Mặc định chạy trên PGlite nạp nguyên baseline. Khi có `TEST_DATABASE_URL`, cùng bộ test chạy trên PostgreSQL thật. Đã chạy qua cả hai (PostgreSQL 17.11).
