# Q02 (đợt 5) — Yêu cầu tích hợp cho tool xác minh và ghi lịch sử bảo trì

- **Từ:** Team Quang (tool kỹ thuật), task Q01/Q02.
- **Gửi:** Team Chiến (mục 1–3), anh Quang (mục 4).
- **Ngày:** 01/10/2026.
- **Liên quan:** `technical.verify_resolution`, `maintenance_history.append` (`docs/teams/quang/tools.md` §5.1, §4.1).
- **Các đợt trước:** [Q02-interruptions.md](Q02-interruptions.md), [Q02-sop-asset.md](Q02-sop-asset.md), [Q02-sensor-history.md](Q02-sensor-history.md), [Q02-measurement-result.md](Q02-measurement-result.md). Các yêu cầu ở đó vẫn còn nguyên; file này chỉ nêu phần thêm.

## 1. Capability mới

**Owner:** Chiến (C06 — runtime gateway).

Cấp thêm hai capability cho technical agent: `resolution:verify` và `maintenance:append`.

Không cần thêm quyền đọc database: hai tool dùng lại các bảng đã xin ở đợt 2 (SOP) và đợt 4 (work order, assignment, ảnh).

## 2. Bảng lịch sử bảo trì: ghi được, chống phân nhánh

**Owner:** Chiến (`server/src/db/**`).

Bảng `maintenance_events` đã đề xuất ở [Q02-sensor-history.md](Q02-sensor-history.md) mục 2.2. Có tool ghi rồi, cần thêm:

| Bổ sung | Lý do |
|---|---|
| `recorded_by`, `created_at`, `source_run_id` | Ai ghi, lúc nào, trong lần chạy nào — lấy từ server, không từ agent |
| **Unique index trên `(tenant_id, supersedes_event_id)`** | Hai bản sửa cùng lúc của một event chỉ được một bản vào. Đây là cách database làm điều kho POC đang làm trong một bước; kiểm tra rồi mới ghi thì cả hai cùng lọt |
| Trigger append-only | Không sửa, không xóa event (`tools.md` §1.4) |
| Ghi cùng transaction với khóa chống trùng (`tool_idempotency_keys`, đợt 4) | Server sập giữa hai bước thì retry sẽ ghi event lần hai |

Interface [`MaintenanceStore`](../../../../server/src/technical-tools/ports/maintenance-store.ts) đã chốt hành vi: `append` trả `already_superseded` thay vì ghi. Có bảng thì chỉ cần adapter mới; tool không phải sửa.

## 3. Liên kết work order ↔ thiết bị

**Owner:** Chiến.

`work_orders` không có cột thiết bị, và chưa có bảng nào nối work order với thiết bị. Hiện `append` chỉ kiểm tra được thiết bị **có trong tòa**, không kiểm tra được thiết bị **thuộc work order đó**. Một agent có thể ghi việc sửa điều hòa vào lịch sử của máy nước nóng cùng căn hộ.

Đề xuất: cột `asset_id` trên `work_orders`, hoặc bảng `work_order_assets(work_order_id, asset_id)` nếu một việc có thể chạm nhiều thiết bị. Việc này phụ thuộc bảng thiết bị (đã xin ở [Q02-sop-asset.md](Q02-sop-asset.md)).

## 4. Điểm cần anh Quang chốt trong `tools.md`

| # | Vấn đề | Đang làm |
|---|---|---|
| 4.1 | `append` có tin `verified_result_id` không | **Không.** Tự chạy lại phép xác minh với các SOP dẫn trong `source_refs` (`doc:<mã>:v<n>`); không có SOP thì không ghi. **Hệ quả:** ví dụ mẫu tr-a2-007 (`source_refs` không có `doc:`) đúng hình dạng nhưng sẽ bị từ chối khi chạy. Đề xuất sửa ví dụ thêm `"doc:SOP-HVAC-012:v3"` |
| 4.2 | Không có SOP để đối chiếu | `HUMAN_REVIEW`. Input của verify không có mã sự cố nên không tự tìm SOP được |
| 4.3 | Tiêu chí `manual` | Luôn dẫn tới `HUMAN_REVIEW` |
| 4.4 | Xác minh có tin trạng thái lưu lúc nộp không | Không. Luôn tính lại từ ảnh, số đo, SOP hiện tại; ảnh rút sau khi nộp thì không còn tính |
| 4.5 | Quyền đọc SOP khi xác minh / ghi | Như `sop_kb.retrieve`: không đọc được SOP thì không xác minh theo nó được. **Hệ quả:** quản lý không ghi lịch sử theo SOP-HVAC-012 được, vì SOP đó chỉ cấp cho `staff`. Cần xác nhận đây là ý đồ, hay ACL của SOP cần thêm `management` |
| 4.6 | Sửa một event đã bị sửa | `CONFLICT`; phải sửa bản mới nhất. `revision` = vị trí trong chuỗi sửa |
| 4.7 | `incident_id` của event ghi mới | Là ticket của work order, để `repeat_count` coi đây là sự cố lặp lại |
| 4.8 | Kết quả của work order khác | `NOT_FOUND` ở cả hai tool, không phân biệt với id không tồn tại |

## Dữ liệu mẫu và test

- Không seed thêm database. Dùng lại work order, ảnh, SOP và lịch sử bảo trì của các đợt trước.
- Test: 651 test trong `server/tests/technical-tools/`, đã chạy trên cả PGlite và PostgreSQL 17.

```
bun test server/tests/technical-tools
```
