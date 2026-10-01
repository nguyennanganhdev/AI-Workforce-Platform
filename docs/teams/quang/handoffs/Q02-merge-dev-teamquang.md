# Gộp hai bộ khung technical tools trên `dev_TeamQuang`

- **Người làm:** Phạm Thành Đạt (Team Quang).
- **Ngày:** 01/10/2026.
- **Nhánh:** `technical_tool_Dat_merge` = `technical_tool_Dat` + `dev_TeamQuang` (`3e16450`).
- **Cần review:** Giáp Hoàng Thịnh, anh Quang.

## 1. Vì sao phải gộp

Hai người đã làm song song cùng một phần việc trong `server/src/technical-tools/`:

| | Thịnh (`17e5826`, PR #12) | Đạt (`technical_tool_Dat`) |
|---|---|---|
| Tool | 7 (mục 3.1–3.6 và 4.1 của `tools.md`) | 14 |
| Test | 15, chạy trên schema rút gọn | 852, chạy trên baseline thật + PostgreSQL 17 |

Trùng 7 tool, khác kiến trúc, cùng tên file `catalog.ts`, `index.ts`. Team quyết định **lấy bản 14 tool làm nền** và đưa các ý tốt của bản kia vào.

## 2. Đã làm gì

| Commit | Nội dung |
|---|---|
| `merge: bring dev_TeamQuang …` | Giữ `catalog.ts`, `index.ts` của bản 14 tool; gỡ 13 file khung và 4 test trùng khỏi kết quả merge (vẫn còn trong lịch sử ở `17e5826`); giữ 2 file docs |
| `refactor: … tenant session …` | Ý `TenantReadSessionPort` của Thịnh: mọi adapter DB chạy trong `TenantSession` do backend cấp, thay vì tự mở transaction |
| `feat!: … access scopes …` | Ý quyền theo scope và `BuildingAccessPort` của Thịnh: `ResolvedIdentity.grants` thay cho `capabilities` + `allowed_building_ids`; host kiểm tra scope của **đúng capability** tool cần |
| `docs: …` | `requests/Q02-backend-ports.md` gộp bản bàn giao backend của Thịnh; cập nhật hợp đồng `ResolvedIdentity` trong các file yêu cầu cũ |

Kết quả: **882 test**, đều qua trên PGlite và PostgreSQL 17 (852 cũ + 3 test session + 27 test quyền theo scope).

## 3. Những điểm trong bản 7 tool đã được bản 14 tool xử lý

Ghi lại để reviewer thấy vì sao không giữ code đó. Mỗi điểm đã có test ở bản hiện tại.

| # | Tool | Bản 7 tool | Bản hiện tại |
|---|---|---|---|
| 1 | `maintenance_history.read` | `repeat_count` đếm mọi sự kiện, kể cả bảo trì định kỳ | Chỉ đếm sự kiện phát sinh từ sự cố |
| 2 | `maintenance_history.read` | Không ẩn bản ghi đã bị sửa | Chỉ trả bản mới nhất |
| 3 | `maintenance_history.read` | `last_maintenance_at` chỉ tính trong khoảng hỏi | Không bị giới hạn bởi điểm đầu khoảng hỏi |
| 4 | `sop_kb.retrieve` | SOP đúng mã sự cố nhưng không khớp từ khóa bị loại | Vẫn trả, xếp sau |
| 5 | `sop_kb.retrieve` | Mock; quyền theo danh sách principal | Đọc DB thật; `document_acl` theo vai trò, người dùng, workspace |
| 6 | `sensor.read` | Không có số đo → `NOT_FOUND` | `OK`, `freshness: "unknown"`; `NOT_FOUND` chỉ khi không có cảm biến |
| 7 | `sensor.read` | Không kiểm tra đơn vị, không giới hạn số lượng | Sai đơn vị → `bad`; quá 200 → `NEEDS_INPUT` |
| 8 | `asset.read` | Tìm vị trí không bỏ dấu tiếng Việt | Bỏ dấu |
| 9 | `maintenance_history.append` | Tin trạng thái `VERIFIED` có sẵn | Tự xác minh lại |
| 10 | `maintenance_history.append` | Sửa được bản ghi đã bị sửa | Từ chối |
| 11 | `maintenance_history.append` | So payload bằng `JSON.stringify` | Hash sau khi sắp xếp khóa, ở tầng host |
| 12 | Runner | Lỗi không rõ luôn `retryable: true` | Tool ghi `retryable: false` |
| 13 | Runner | Không audit, timeout, chống ghi trùng | Có ở host |
| 14 | Context | Không có `user_id`, `role_code` | Có |
| 15 | Test | Bảng tự tạo, không RLS | Baseline 148 bảng, RLS, role không phải superuser |

## 4. Cần chốt

1. **Anh Quang:** `status` của envelope có `INVALID_INPUT` không? `tools.md` §1.3 không có, nhưng §7 và từng tool đều nói "trả `INVALID_INPUT`". Bản hiện tại thêm vào; bản 7 tool chuyển thành `NEEDS_INPUT` (dễ khiến agent hỏi lại người dùng thay vì sửa request).
2. **Chiến:** mount qua `/api/agent-tools/call` (đã có sẵn) hay `/internal/tools/*` (kế hoạch tổng)?
3. **Anh Quang và Thịnh:** chia việc tiếp theo để không trùng nữa. Ví dụ Thịnh nhận adapter nguồn dữ liệu thật (asset, cảm biến, bảo trì) hoặc RAG Q03/Q04.
