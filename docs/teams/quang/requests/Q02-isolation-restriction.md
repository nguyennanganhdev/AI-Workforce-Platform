# Q02 (đợt 6) — Yêu cầu tích hợp cho tool đề nghị cô lập và rào chắn

- **Từ:** Team Quang (tool kỹ thuật), task Q01/Q02.
- **Gửi:** Team Chiến (mục 1–4), anh Quang (mục 5).
- **Ngày:** 01/10/2026.
- **Liên quan:** `utility_isolation.request`, `area_restriction.request` (`docs/teams/quang/tools.md` §6.1, §6.2).
- **Các đợt trước:** [Q02-interruptions.md](Q02-interruptions.md), [Q02-sop-asset.md](Q02-sop-asset.md), [Q02-sensor-history.md](Q02-sensor-history.md), [Q02-measurement-result.md](Q02-measurement-result.md), [Q02-verify-append.md](Q02-verify-append.md). Các yêu cầu ở đó vẫn còn nguyên.

## 1. Capability và quyền ghi

**Owner:** Chiến (C06 runtime gateway, `server/src/db/**`).

- Capability mới: `utility_isolation:request`, `area_restriction:request`.
- Role của tool cần thêm quyền, **chỉ INSERT, không UPDATE, không DELETE**:

```sql
GRANT SELECT, INSERT ON work_approvals TO <runtime_role>;
GRANT INSERT ON service_interruptions, interruption_scopes TO <runtime_role>;
```

Việc không có UPDATE là **chủ đích**: đó là lớp chặn cuối cùng để agent không thể tự phê duyệt hay tự kích hoạt lịch cắt, kể cả khi bị prompt injection. Test `isolation-writer.db.test.ts` kiểm tra điều này; nếu grant thay đổi thì test sẽ đỏ.

## 2. Trigger chặn kích hoạt khi chưa được duyệt — QUAN TRỌNG

Baseline hiện **không có trigger nào** ngăn `service_interruptions` chuyển sang `approved`/`notified`/`active` khi `work_approvals` tương ứng chưa `approved`. Mình đã tìm trong `0000_grey_blockbuster.sql`: chỉ có trigger `touch updated_at`.

`tools.md` §8 mục 13 yêu cầu "cả hai không thể active khi approval chưa approved". Hiện điều này chỉ đúng nhờ role của tool không có quyền UPDATE. Một service khác có quyền UPDATE (hoặc một lỗi trong service đó) vẫn có thể kích hoạt lịch cắt khi chưa có ai duyệt.

Đề xuất trigger `BEFORE UPDATE OF status ON service_interruptions`: khi `NEW.status` thuộc `approved`, `notified`, `active` thì yêu cầu `work_approvals.status = 'approved'` cho `approval_id` đó.

## 3. Phê duyệt cho cắt điện và rào chắn

**Owner:** Chiến.

| Thiếu | Hệ quả hiện tại | Đề xuất |
|---|---|---|
| `work_approvals.kind` cho cắt điện | Interruption điện không vào `service_interruptions` được (vì `approval_id` bắt buộc); cả hai nằm trong adapter POC, mất khi khởi động lại | Thêm kind `management_power_isolation` |
| Loại request cho rào chắn | Nằm trong adapter POC | Bảng request chung (dùng cho cả `apartment_entry` và `vendor_dispatch` ở đợt sau) hoặc kind mới, không ép vào `work_approvals` |

Interface [`ApprovalRequestStore`](../../../../server/src/technical-tools/ports/request-ports.ts) đã chốt: chỉ `create` và `listOpen`. Adapter thật cũng **không được** có đường duyệt.

## 4. Ràng buộc chống trùng và bằng chứng

- **Chống trùng đồng thời:** hai đề nghị khóa nước cùng work order, trùng giờ, khác `idempotency_key`, gửi đúng cùng lúc có thể cùng lọt. Đề xuất exclusion constraint (`btree_gist` đã có trong baseline) trên `(tenant_id, work_order_id, utility, tstzrange(planned_start, planned_end))` cho các dòng chưa `cancelled`/`restored`.
- **`work_approval_evidence`:** cần `original_object_id` và `sha256_snapshot`, nằm ở `file_objects` mà role không được đọc. Đề xuất: service phê duyệt tự chụp snapshot khi tạo approval, hoặc cấp role đọc đúng hai cột đó. Hiện ảnh nằm trong `request_detail.evidence_ids`.

## 5. Điểm cần anh Quang chốt

| # | Vấn đề | Đang làm |
|---|---|---|
| 5.1 | Phạm vi được nhắm tới | Chỉ tòa, zone hoặc site chứa tòa. Không tòa bên cạnh, không cả tenant |
| 5.2 | Người duyệt | Phạm vi rộng nhất trong đề nghị (`required_scope_id`) |
| 5.3 | Ai được đề nghị cắt nước/điện | Kỹ thuật viên đang nhận work order, hoặc `management` |
| 5.4 | Ai được đề nghị rào chắn | Mọi người có capability và quyền với tòa: ai thấy nguy hiểm cũng phải báo được |
| 5.5 | Thế nào là trùng | Nước/điện: cùng loại, cùng work order, chưa `cancelled`/`restored`, trùng giờ. Rào chắn: cùng sự cố, cùng khu vực (bỏ hoa thường, dấu, khoảng trắng, dấu câu), đang chờ |
| 5.6 | Thời hạn rào chắn | Tối đa 7 ngày, phải ở tương lai |
| 5.7 | Khung giờ cắt đã bắt đầu | Được, miễn `planned_end` chưa qua (sự cố khẩn có thể cần cắt ngay) |
| 5.8 | Nhánh điện | Trong adapter POC cho tới khi có kind phù hợp (mục 3) |

## Dữ liệu mẫu và test

- Không seed thêm. Test ghi chạy trên database riêng (`technicalToolsTestDatabase({ isolated: true })`).
- Test: 748 test trong `server/tests/technical-tools/`, đã chạy trên cả PGlite và PostgreSQL 17.

```
bun test server/tests/technical-tools
```
