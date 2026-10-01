# Q02 (đợt 7) — Yêu cầu tích hợp cho tool xin vào căn hộ và gọi nhà thầu

- **Từ:** Team Quang (tool kỹ thuật), task Q01/Q02.
- **Gửi:** Team Chiến (mục 1–4), Domain Owner (mục 5), anh Quang (mục 6).
- **Ngày:** 01/10/2026.
- **Liên quan:** `apartment_entry.request`, `vendor_dispatch.request` (`docs/teams/quang/tools.md` §6.3, §6.4).
- **Các đợt trước:** [Q02-interruptions.md](Q02-interruptions.md), [Q02-sop-asset.md](Q02-sop-asset.md), [Q02-sensor-history.md](Q02-sensor-history.md), [Q02-measurement-result.md](Q02-measurement-result.md), [Q02-verify-append.md](Q02-verify-append.md), [Q02-isolation-restriction.md](Q02-isolation-restriction.md). Các yêu cầu ở đó vẫn còn nguyên.

## 1. Capability và quyền đọc

**Owner:** Chiến.

- Capability mới: `apartment_entry:request`, `vendor_dispatch:request`.
- Quyền đọc, chỉ SELECT:

```sql
GRANT SELECT ON units, unit_residents TO <runtime_role>;
```

Role **không** cần và **không được** có UPDATE trên `tickets`, `unit_residents`: đó là cách bảo đảm `urgency: immediate` không thể đổi ưu tiên ticket, và tool không thể "xác minh" một cư dân. Test `unit-read.db.test.ts` kiểm tra cả hai.

## 2. Bảng nhà thầu

**Owner:** Chiến. Hiện danh mục nhà thầu là adapter POC, không tự chứa dữ liệu.

| Bảng đề xuất | Trường |
|---|---|
| `vendors` | `id`, `tenant_id`, `display_name`, `status` (`active`/`suspended`), `contact_phone`, … |
| `vendor_specialties` | `vendor_id`, `specialty_code` |
| `vendor_service_areas` | `vendor_id`, `site_id` |
| `vendor_qualifications` | `vendor_id`, `kind` (`license`/`insurance`), `expires_at`, `verified_at` |

Có bảng thì chỉ cần adapter mới theo [`VendorCatalogPort`](../../../../server/src/technical-tools/ports/entry-vendor-ports.ts). Port này chỉ đọc; adapter thật cũng **không được** có đường đặt lịch / ký hợp đồng / thanh toán.

## 3. Kiểm chứng lịch sử liên hệ

**Owner:** Chiến (dịch vụ thông báo / tin nhắn).

`reference_id` của mỗi lần liên hệ hiện chỉ được lưu, **chưa được kiểm chứng**. Agent có thể khai "đã gọi 2 lần" mà không có cuộc gọi nào. Đề xuất: một hàm đọc `notification_deliveries` / `messages` theo id, trả về kênh, thời điểm gửi và người nhận, để tool đối chiếu:
- người nhận là cư dân của căn;
- thời điểm khớp với `attempted_at`.

## 4. Bảng request chung

Bốn loại đề nghị (cắt điện, rào chắn, vào căn hộ, gọi nhà thầu) đang ở adapter phê duyệt POC, mất khi khởi động lại. Như đã đề xuất ở [Q02-isolation-restriction.md](Q02-isolation-restriction.md) mục 3: một bảng request chung có `kind`, `status` (chỉ service phê duyệt được đổi), `required_approvals`, `detail` (jsonb), `request_hash`, `requested_by`, `source_run_id`.

## 5. Cần Domain Owner quyết

| # | Vấn đề | Giá trị đang dùng |
|---|---|---|
| 5.1 | Danh sách mã chuyên môn nhà thầu | `STRUCTURAL_ENGINEER`, `WATERPROOFING`, `HV_ELECTRICAL` (chỉ là dữ liệu mẫu) |
| 5.2 | Ngưỡng chứng chỉ sắp hết hạn | 30 ngày |
| 5.3 | Ai là `safety_officer` khi vào nhà trái ý chủ | Chưa có vai trò này trong hệ thống |

## 6. Điểm cần anh Quang chốt

| # | Vấn đề | Đang làm |
|---|---|---|
| 6.1 | Thế nào là đã liên hệ đủ | 2 lần trong 24 giờ, cách ≥ 15 phút; ticket khẩn 1 lần; chủ nhà đã trả lời thì đủ |
| 6.2 | Chủ nhà từ chối | Vẫn cho đề nghị, cần hai người duyệt (quản lý + an toàn) |
| 6.3 | Chủ nhà đồng ý theo lời agent kể | Cần chủ nhà xác nhận bằng văn bản |
| 6.4 | Căn khác tòa | `FORBIDDEN`, theo §6.3 |
| 6.5 | Khung giờ vào nhà | Tối đa 8 giờ |
| 6.6 | Nhận diện mã khóa | Từ khóa mật khẩu đi kèm dãy ≥ 3 chữ số → từ chối, không lưu, không nhắc lại |
| 6.7 | Không nêu chuyên môn | Danh sách nhà thầu rỗng, không đoán từ chữ |
| 6.8 | Đề nghị trùng | Vào nhà: cùng căn + sự cố. Nhà thầu: cùng sự cố + chuyên môn (hoặc `service` khi không có mã) |
| 6.9 | `immediate` | Chỉ lưu trong đề nghị; không đổi ưu tiên ticket |

## Dữ liệu mẫu và test

- Dữ liệu: `fixtures/units.ts` (5 căn, 5 cư dân), `fixtures/vendors.ts` (7 nhà thầu), ticket mẫu gắn căn hộ và cờ khẩn.
- Test: 852 test trong `server/tests/technical-tools/`, đã chạy trên cả PGlite và PostgreSQL 17.

```
bun test server/tests/technical-tools
```
