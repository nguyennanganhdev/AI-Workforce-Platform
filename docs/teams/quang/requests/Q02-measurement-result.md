# Q02 (đợt 4) — Yêu cầu tích hợp cho tool ghi số đo và nộp kết quả

- **Từ:** Team Quang (tool kỹ thuật), task Q01/Q02.
- **Gửi:** Team Chiến (mục 1–3), anh Quang (mục 4).
- **Ngày:** 01/10/2026.
- **Liên quan:** `technical.record_measurement`, `technical.submit_executor_result` (`docs/teams/quang/tools.md` §4.2, §4.3), và phần chống ghi trùng trong host (`tools.md` §1.4).
- **Các đợt trước:** [Q02-interruptions.md](Q02-interruptions.md), [Q02-sop-asset.md](Q02-sop-asset.md), [Q02-sensor-history.md](Q02-sensor-history.md). Các yêu cầu ở đó vẫn còn nguyên; file này chỉ nêu phần thêm.

## 1. Danh tính và capability

**Owner:** Chiến (C06 — runtime gateway).

- Cấp thêm hai capability cho technical agent: `measurement:write` và `executor_result:submit`.
- **`user_id` trong `ResolvedIdentity` phải là `users.id` thật của người mà run đang phục vụ.** Đợt này lần đầu có quy tắc dựa vào nó: kỹ thuật viên chỉ được ghi số đo dưới tên chính mình, và tool so `user_id` với `staff_profiles.user_id` của assignment. Nếu resolver trả một id khác (ví dụ id của bot), mọi số đo `technician` sẽ bị `FORBIDDEN`.
- `role_code` cần trả `management` cho quản lý tòa nhà. Đây là cách duy nhất để quản lý nộp kết quả thay kỹ thuật viên.

## 2. Quyền đọc cho role runtime

**Owner:** Chiến (`server/src/db/**`).

Role mà tool chạy dưới cần thêm `SELECT` trên 6 bảng sau. Tool chỉ đọc, không ghi bảng nào trong số này:

```sql
GRANT SELECT ON tickets, work_orders, work_assignments, staff_profiles, evidence_items, files
  TO <runtime_role>;
```

Không cần quyền trên `file_objects` (nội dung lưu trữ của file). Test xác nhận role vẫn bị từ chối khi đọc bảng đó, và khi sửa `work_orders`, `evidence_items`, `work_assignments`.

## 3. Bảng còn thiếu

**Owner:** Chiến (`server/src/db/**`). Cả ba thứ dưới đây đang chạy trên adapter POC trong bộ nhớ: **mất khi khởi động lại**, và kho khóa không có tác dụng khi có nhiều tiến trình server.

### 3.1. Số đo

| Bảng đề xuất | Trường |
|---|---|
| `measurements` | `id`, `tenant_id`, `building_id`, `work_order_id`, `asset_id?`, `metric`, `raw_value`, `raw_unit`, `normalized_value`, `normalized_unit`, `measured_at`, `measured_by_kind` (`technician`/`device`), `measured_by_source_id`, `source` (`manual_entry`/`instrument`/`bms`/`iot`), `evidence_ids`, `quality_flags`, `created_at`, `source_run_id` |

### 3.2. Kết quả kỹ thuật viên

`tools.md` §2 ghi rõ không nhét JSON kết quả vào `ticket_events`, nên cần bảng riêng.

| Bảng đề xuất | Trường |
|---|---|
| `executor_results` | `id`, `tenant_id`, `building_id`, `work_order_id`, `assignment_id`, `submitted_by`, `checklist` (jsonb), `measurement_ids`, `parts` (jsonb), `evidence_ids`, `diagnosis?`, `repair_notes?`, `started_at`, `completed_at`, `validation_status` (`ACCEPTED`/`NEEDS_EVIDENCE`/`HUMAN_REVIEW`), `missing_evidence`, `conflicts`, `created_at`, `source_run_id` |

### 3.3. Khóa chống ghi trùng

| Bảng đề xuất | Trường |
|---|---|
| `tool_idempotency_keys` | `tenant_id`, `tool`, `idempotency_key`, `payload_hash`, `state` (`in_progress`/`completed`), `outcome` (jsonb), `created_at`, `completed_at?` — khóa chính `(tenant_id, tool, idempotency_key)` |

**Ghi chú cho cả ba bảng:**

- **Bản ghi và khóa phải được ghi trong cùng một transaction.** Nếu ghi riêng, server sập giữa lúc ghi số đo và lúc đánh dấu khóa xong sẽ để lại một số đo mà lần retry sau ghi lại lần nữa. Interface [`IdempotencyStore`](../../../../server/src/technical-tools/ports/idempotency-store.ts) đã ghi chú điều này.
- `reserve` phải giữ khóa và báo trạng thái cũ **trong một bước** (ví dụ `INSERT … ON CONFLICT DO NOTHING RETURNING`), không được "đọc rồi mới ghi". Đọc rồi ghi thì hai lần retry đồng thời đều thấy khóa trống và cùng ghi.
- `measurements` và `executor_results` **chỉ thêm, không sửa** (`tools.md` §1.4). Nên có trigger append-only như các bảng lịch sử khác trong baseline.
- Có bảng thì chỉ cần viết adapter mới theo các port đã có (`MeasurementStore`, `ExecutorResultStore`, `IdempotencyStore`); tool không phải sửa.

## 4. Điểm cần anh Quang chốt trong `tools.md`

`tools.md` chưa nói rõ các điểm sau. Đợt này chọn như cột phải:

| # | Vấn đề | Đang làm |
|---|---|---|
| 4.1 | Người đo `technician` được là ai | Chỉ chính người mà run đang phục vụ, và người đó phải có assignment `accepted` trên work order. Agent không được ghi số đo nhân danh người khác |
| 4.2 | Metric ngoài danh mục khi **ghi** | Từ chối (`INVALID_INPUT`). Khác với khi **đọc** (đợt 3), nơi metric lạ chỉ không được kiểm tra đơn vị: số đo đã ghi trở thành bằng chứng, nên phải quy đổi được |
| 4.3 | Số đo ngoài khoảng thường gặp | Ghi và gắn cờ `out_of_expected_range`, không từ chối. Khoảng hiện tại là giá trị làm việc, cần Domain Owner duyệt (`general.md` §14) |
| 4.4 | Work order không có trong tòa được hỏi | `NOT_FOUND`, giống hệt nhau dù work order ở tòa khác hay không tồn tại |
| 4.5 | Quy tắc `validation_status` | Có mục `failed`, số đo có cờ ngoài khoảng, hoặc `completed_at` trước lúc nhận việc → `HUMAN_REVIEW`; nếu không, thiếu ảnh `after` → `NEEDS_EVIDENCE`; còn lại → `ACCEPTED` |
| 4.6 | Lời gọi bị từ chối có giữ khóa chống trùng không | Không. Lời gọi bị từ chối chưa ghi gì, nên agent được sửa yêu cầu rồi gửi lại cùng khóa |
| 4.7 | Timeout với tool ghi | **Lệch nhẹ so với cách hiểu thông thường:** khóa được giữ tới khi lần chạy thật sự kết thúc, không giải phóng lúc agent thôi chờ. Retry trong khoảng đó nhận `CONFLICT` `retryable: true`. Lý do: lần ghi có thể hoàn tất ngay sau timeout, giải phóng sớm thì retry sẽ ghi hai lần |

## Dữ liệu mẫu và test

- Dữ liệu: `server/tests/technical-tools/fixtures/work-orders.ts` (5 work order, 6 ảnh, 1 file đang tải), seed vào database qua `support/seed-db.ts`.
- Test: 561 test trong `server/tests/technical-tools/`, đã chạy trên cả PGlite và PostgreSQL 17.

```
bun test server/tests/technical-tools
```
