# Báo cáo Q02 (đợt 7, cuối) — Tool xin vào căn hộ và gọi nhà thầu, tổng kết 14/14 tool

- **Người làm:** Phạm Thành Đạt (Team Quang).
- **Ngày:** 01/10/2026.
- **Task:** Q01 (danh mục tool) và Q02 (tool kỹ thuật), đợt 7.
- **Trạng thái:** **xong 14/14 tool** của Technical Agent A2 trong `docs/teams/quang/tools.md`. Tool vẫn chưa gọi được từ server đang chạy vì chưa được nối vào `createApp` (việc của Team Chiến).
- **Các đợt trước:** [đợt 1](Q02-outage-schedule-tools.md), [đợt 2](Q02-sop-asset-tools.md), [đợt 3](Q02-sensor-history-tools.md), [đợt 4](Q02-measurement-result-tools.md), [đợt 5](Q02-verify-append-tools.md), [đợt 6](Q02-isolation-restriction-tools.md).

## 1. Đã xây gì

| Tool | Làm gì | Nguồn | Đặc tả |
|---|---|---|---|
| `apartment_entry.request` | Xin vào căn hộ có cư dân không liên lạc được | Bảng thật `units`, `unit_residents`, `tickets`; đề nghị lưu ở adapter phê duyệt POC (đợt 6) | `tools.md` §6.3 |
| `vendor_dispatch.request` | Đề nghị gọi nhà thầu ngoài, kèm danh sách nhà thầu đủ điều kiện | Danh mục nhà thầu POC; đề nghị lưu ở adapter phê duyệt POC | `tools.md` §6.4 |

Cả hai luôn trả **`PENDING_APPROVAL`**. Không cửa nào được mở, không nhà thầu nào được gọi, đặt lịch hay trả tiền vì một lời gọi tool.

Kèm theo:

- **Adapter DB đọc căn hộ** ([adapters/db/unit-read.ts](../../../../server/src/technical-tools/adapters/db/unit-read.ts)): căn thuộc tòa nào, ai đang ở.
- **Danh mục nhà thầu POC** ([adapters/poc/vendor-catalog.ts](../../../../server/src/technical-tools/adapters/poc/vendor-catalog.ts)): chỉ có `findBySpecialty`, **không có hàm đặt lịch / hợp đồng / thanh toán**.
- `getTicket` trả thêm căn hộ, cờ khẩn cấp, mức ưu tiên; thêm `listWorkOrders` theo ticket.

## 2. Quyết định thiết kế và lý do

Rủi ro của đợt này là **vào nhà người khác khi họ vắng mặt** và **tiêu tiền khi chưa ai quyết**.

### 2.1. Phải liên hệ chủ nhà đủ trước khi xin vào

| Tình huống | Đủ khi |
|---|---|
| Ticket khẩn (`tickets.is_emergency`, do triage đặt) | ≥ 1 lần liên hệ trong 24 giờ |
| Chủ nhà đã trả lời (đồng ý hoặc từ chối) | Đủ |
| Còn lại | ≥ 2 lần trong 24 giờ, lần đầu và lần cuối cách nhau ≥ 15 phút |

Chưa đủ → `NEEDS_INPUT`, `missing_fields: ["contact_attempts"]`, không lưu gì. **Lý do:** "gọi một lần lúc 08:59 rồi xin vào nhà lúc 09:00" không phải là "không liên lạc được". Cờ khẩn cấp lấy từ ticket do triage đặt, không phải từ lời agent nói, nên agent không tự nâng mức khẩn để lách luật được.

`attempted_at` muộn hơn giờ server quá 5 phút → `INVALID_INPUT`: lịch sử liên hệ không được bịa trước.

### 2.2. Tool quyết ai phải duyệt, không phải agent

| Tình huống | `required_approvals` |
|---|---|
| Chủ nhà từ chối (lần trả lời gần nhất) | `management_override` **và** `safety_officer` |
| Chủ nhà đồng ý (theo lời agent kể) | `resident_written_confirmation` |
| Không trả lời, căn có cư dân đã xác minh, còn hiệu lực | `resident_or_authorized_management` |
| Không trả lời, căn không có cư dân hợp lệ | `authorized_management` |

**Lý do:**
- **Chủ nhà từ chối:** vẫn cho đề nghị (rò nước, chập điện có thể nguy hiểm cho căn khác) nhưng cần hai người, vì vào nhà trái ý chủ là việc nghiêm trọng.
- **Chủ nhà "đồng ý qua điện thoại":** lời đồng ý agent kể lại không phải giấy phép ai đó có thể đưa ra sau này, nên cần chủ nhà xác nhận bằng văn bản.
- **Cư dân hợp lệ** là bản ghi `verified` còn trong khoảng `valid_from`–`valid_to`. Người đã chuyển đi hoặc chưa được xác minh không tính.

### 2.3. Không nhận, không lưu, không trả mã khóa

- Hợp đồng `strict`: không có trường `door_code`, `access_code`; mỗi lần liên hệ chỉ có kênh, thời điểm, kết quả và `reference_id`, **không có nội dung tin nhắn**.
- `reason` hoặc `reference_id` chứa từ khóa mật khẩu đi kèm dãy số (`mã cửa là 4821#`, `pin:4821`, `mật khẩu 998877`) → `INVALID_INPUT`. Đề nghị không được lưu, và thông báo lỗi **không nhắc lại** đoạn văn. Test kiểm tra "4821" không có trong câu trả lời lẫn audit.
- Không bắt nhầm câu mô tả bình thường: "Cần thợ mở khóa cửa", "Pin cảm biến khói hết, thay pin 9V" vẫn qua.

### 2.4. Căn hộ ngoài tòa → `FORBIDDEN`

Theo đúng `tools.md` §6.3. Căn tòa khác, căn của tenant khác và căn không tồn tại trả **cùng một** câu `FORBIDDEN`, nên không lộ căn nào có thật.

### 2.5. Nhà thầu: chỉ khớp, không thuê

| Tình trạng | Kết quả |
|---|---|
| Đang hoạt động, chứng chỉ còn > 30 ngày, bảo hiểm đã xác minh | `eligible` |
| Chứng chỉ còn ≤ 30 ngày, hoặc bảo hiểm chưa xác minh | `needs_review` |
| Hết hạn, bị đình chỉ, không phục vụ site này, tenant khác | Không xuất hiện |

- Thứ tự: `eligible` trước, rồi theo tên.
- Không nêu `required_specialty_code` → danh sách rỗng. Tool không đoán chuyên môn từ câu `service`.
- Output chỉ có `vendor_id`, `display_name`, `qualification_status`. Danh mục có số điện thoại và giá; test xác nhận cả hai không bao giờ xuất hiện trong câu trả lời.
- Input không nhận `budget`, `approved_cost`, `booking_time`, `vendor_id` chỉ định.

### 2.6. `immediate` không vượt qua triage

`urgency` chỉ được lưu trong đề nghị. Test đọc lại ticket sau đề nghị `immediate`: `priority` vẫn `normal`, `is_emergency` vẫn `false`. Port không có hàm ghi ticket, và role của tool không có quyền UPDATE `tickets` (có test DB).

### 2.7. Điều kiện khác

- Người đề nghị: kỹ thuật viên có assignment `accepted` trên một work order của sự cố, hoặc `management`.
- Đề nghị trùng → `CONFLICT`, nêu id cũ:
  - vào nhà: cùng căn, cùng sự cố, đang chờ;
  - gọi nhà thầu: cùng sự cố, cùng chuyên môn (hoặc cùng `service` khi không có mã chuyên môn), đang chờ.
- Khung giờ vào nhà: kết thúc ở tương lai, dài tối đa 8 giờ.
- Ảnh (nếu có) phải dùng được và thuộc cùng ticket.

## 3. Dữ liệu mẫu

**Seed thêm vào database:**
- 5 căn hộ:
  - A1-1205: căn báo sự cố.
  - A1-1305: căn phía trên, nguồn rò — ví dụ §6.3.
  - A1-1105: chỉ có người đã chuyển đi và người chưa xác minh.
  - A2-0803: căn tòa khác.
  - X1-0101: căn của tenant khác.
- 5 bản ghi cư dân.
- Ticket mẫu nay gắn căn A1-1205. Ticket cầu dao (WO-BREAKER) là **khẩn**, `priority = critical`; các ticket khác `normal`.

**Danh mục nhà thầu** (`fixtures/vendors.ts`), mỗi nhà thầu cho một trường hợp:

| Nhà thầu | Trường hợp |
|---|---|
| VEN-21 | Hợp lệ |
| VEN-22 | Chứng chỉ còn 10 ngày |
| VEN-23 | Chứng chỉ hết hạn |
| VEN-24 | Bảo hiểm chưa xác minh |
| VEN-25 | Bị đình chỉ |
| VEN-26 | Phục vụ site khác |
| VEN-X1 | Tenant khác |

### Ca theo mức độ bẫy (`entry-vendor.flow.test.ts`)

| Mức | Ca |
|---|---|
| **Level 3** | L3-23 rò từ căn trên, đã nhắn và gọi → chờ chủ nhà hoặc quản lý; L3-24 kiểm định kết cấu → VEN-21 `eligible`, VEN-22 `needs_review`; L3-25 gửi lại sau mất mạng |
| **Level 2** | L2-30…32 liên hệ chưa đủ (1 lần, 2 lần cách 5 phút, từ hôm qua) → `NEEDS_INPUT`; L2-33 căn không có cư dân hợp lệ; L2-34 xin vào trùng; căn khác cùng sự cố thì được; L2-35 chống thấm; chuyên môn không ai phục vụ; L2-36 không nêu chuyên môn; L2-37 gọi nhà thầu trùng |
| **Level 1** | L1-39 cầu dao tóe lửa, ticket khẩn, 1 lần là đủ, vẫn chỉ đề nghị; L1-40 chủ nhà từ chối → 2 người duyệt; L1-41 "chủ nhà đồng ý qua điện thoại"; L1-42 mã cửa trong lý do / trong mã tham chiếu; L1-43 trường mã khóa, trạng thái; L1-44 căn ngoài tòa (3 biến thể); L1-45 liên hệ bịa ở tương lai; L1-46 `immediate` không đổi ưu tiên; L1-47 ngân sách / giá / lịch / chỉ định nhà thầu; L1-48 không lộ số điện thoại, giá; L1-49 kỹ thuật viên không thuộc sự cố |

## 4. Kiểm thử

**852 test trong `server/tests/technical-tools/`, tất cả đều qua** (đợt trước 748, đợt này thêm 104).

| File | Số test | Kiểm tra |
|---|---|---|
| `entry-vendor.rules.test.ts` | 27 | Đủ liên hệ (biên 15 phút, 24 giờ, khẩn); người duyệt; cư dân hiện tại; nhận diện mã khóa (6 ca bắt, 4 ca không bắt nhầm); khung giờ; phân loại nhà thầu (biên 30 ngày) |
| `entry-vendor.contract.test.ts` | 20 | Hai ví dụ mẫu; trường bắt buộc; không trường mã khóa / chi phí / trạng thái nào được nhận; output không thêm được số điện thoại |
| `vendor-catalog.test.ts` | 4 | Rỗng mặc định; cách ly tenant; không có hàm đặt lịch |
| `unit-read.db.test.ts` | 13 | Căn hộ và cư dân trên schema thật; ticket khẩn / thường; RLS; role không sửa được cư dân hay ưu tiên ticket |
| `entry-vendor.flow.test.ts` | 38 | Toàn bộ ca ở mục 3 qua `createTechnicalToolCaller` |

Cập nhật: `catalog.test.ts` (14 tool), harness, `host.test.ts`, `idempotency.test.ts`, seed và quyền đọc `units`, `unit_residents`.

Đã chạy trên hai môi trường:

- **PGlite**: 37 giây.
- **PostgreSQL 17** thật: 130 giây, cùng 852 test.

Test bắt được **một lỗi trong dữ liệu test của chính mình**: khóa `entry-1` chỉ có 7 ký tự, dưới mức tối thiểu 8, nên host từ chối trước khi tới tool. Đã đổi sang khóa dài hơn.

Đã thử cố ý phá năm quy tắc:

| Phá gì | Số test đỏ |
|---|---|
| Bỏ yêu cầu cách nhau 15 phút | 2 |
| Chủ nhà từ chối mà chỉ cần một người duyệt | 3 |
| Bỏ bộ lọc mã khóa | 8 |
| Nhà thầu hết hạn vẫn được liệt kê | 2 |
| Coi mọi ticket là khẩn cấp | 3 |

Kế hoạch dự định phá thử "`immediate` ghi đè ưu tiên", nhưng tool không có đường nào để ghi ticket (port không có hàm ghi, role không có quyền UPDATE). Nên mình thay bằng "coi mọi ticket là khẩn" — cách lách luật liên hệ gần nhất với nó.

## 5. Tổng kết 14/14 tool

| Nhóm | Tool | Đợt |
|---|---|---|
| Tra cứu | `technical.get_active_outage`, `utility_schedule.read` | 1 |
| | `sop_kb.retrieve`, `asset.read` | 2 |
| | `sensor.read`, `maintenance_history.read` | 3 |
| Ghi nhận | `technical.record_measurement`, `technical.submit_executor_result` | 4 |
| Xác minh + ghi lịch sử | `technical.verify_resolution`, `maintenance_history.append` | 5 |
| Yêu cầu rủi ro | `utility_isolation.request`, `area_restriction.request` | 6 |
| | `apartment_entry.request`, `vendor_dispatch.request` | 7 |

**Nền dùng chung:**
- Host kiểm tra danh tính, capability, tòa nhà, schema vào/ra; chống ghi trùng; ghi audit.
- Danh mục JSON Schema cho runtime Python.
- 852 test, chạy trên cả PGlite và PostgreSQL 17.

**Để bot dùng được thật, còn chờ:**
- Team Chiến: nối vào `createApp`, `ContextResolver` thật, nơi ghi audit, các bảng thay adapter POC, quyền DB.
- Anh Quang: chốt các giả định ghi trong 7 file yêu cầu.

## 6. Phạm vi thay đổi

Chỉ tạo và sửa file trong vùng của Team Quang: `server/src/technical-tools/**`, `server/tests/technical-tools/**`, `docs/teams/quang/**`. Không sửa schema, migration, `app.ts`, `index.ts`, `package.json` hay lockfile.
