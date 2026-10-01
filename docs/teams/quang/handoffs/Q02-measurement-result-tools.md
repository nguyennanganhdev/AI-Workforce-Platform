# Báo cáo Q02 (đợt 4) — Tool ghi số đo và nộp kết quả kỹ thuật viên

- **Người làm:** Phạm Thành Đạt (Team Quang).
- **Ngày:** 01/10/2026.
- **Task:** Q01 (danh mục tool) và Q02 (tool kỹ thuật), đợt 4.
- **Trạng thái:** xong 8 trong 14 tool. Đây là đợt đầu tiên có **tool ghi dữ liệu**, nên host có thêm phần chống ghi trùng (`idempotency_key`). Tool vẫn chưa gọi được từ server đang chạy vì chưa được nối vào `createApp` (việc của Team Chiến).
- **Các đợt trước:** [Q02-outage-schedule-tools.md](Q02-outage-schedule-tools.md), [Q02-sop-asset-tools.md](Q02-sop-asset-tools.md), [Q02-sensor-history-tools.md](Q02-sensor-history-tools.md). Quyết định dùng chung đã giải thích ở đó và không nhắc lại.

## 1. Đã xây gì

| Tool | Làm gì | Nguồn dữ liệu | Đặc tả |
|---|---|---|---|
| `technical.record_measurement` | Ghi một số đo kỹ thuật viên vừa đo tại hiện trường, hoặc do một cảm biến đã đăng ký gửi về | Đối chiếu bảng thật; lưu số đo qua adapter POC | `tools.md` §4.2 |
| `technical.submit_executor_result` | Nhận kết quả công việc của kỹ thuật viên (checklist, số đo, vật tư, ảnh) và cho biết đã đủ để xác minh chưa | Đối chiếu bảng thật; lưu kết quả qua adapter POC | `tools.md` §4.3 |

Kèm theo:

- **Chống ghi trùng trong host** ([host.ts](../../../../server/src/technical-tools/host.ts), [idempotency.ts](../../../../server/src/technical-tools/idempotency.ts)): áp dụng cho mọi tool có `effect` khác `read`, gồm cả 6 tool ghi còn lại.
- **Adapter DB đọc work order** ([adapters/db/work-order-read.ts](../../../../server/src/technical-tools/adapters/db/work-order-read.ts)): đọc 6 bảng thật `work_orders`, `tickets`, `work_assignments`, `staff_profiles`, `evidence_items`, `files`. Chỉ đọc, không ghi.
- **Danh mục metric mở rộng** ([reference/metrics.ts](../../../../server/src/technical-tools/reference/metrics.ts)): mỗi metric giờ có đơn vị chuẩn, hệ số quy đổi cho từng đơn vị được chấp nhận, và khoảng giá trị thường gặp.
- **`defineTool` bắt buộc tool ghi khai báo `idempotency_key`**: một tool ghi quên trường này sẽ báo lỗi ngay khi khởi động, không đợi tới lúc chạy.

## 2. Vì sao làm hai tool này tiếp

Đây là bước 9 của luồng chung (`general.md` §6): kỹ thuật viên đo, chụp ảnh, rồi nộp kết quả. Hai tool đi liền nhau: `record_measurement` trả `measurement_id`, `submit_executor_result` dẫn lại các `measurement_id` đó.

Tool ghi còn lại trong nhóm, `maintenance_history.append`, cần một kết quả đã `VERIFIED` từ `technical.verify_resolution`, nên để đợt sau.

## 3. Quyết định thiết kế và lý do

### 3.1. Agent không được tự tạo số đo

Đây là quy tắc quan trọng nhất của đợt này (`general.md` §3.1).

| `measured_by.kind` | Được ghi khi | Ngược lại |
|---|---|---|
| `technician` | `source_id` **trùng `user_id` của người mà run đang phục vụ** (lấy từ danh tính đã xác thực, không lấy từ tham số), **và** người đó có assignment `accepted` trên work order | `FORBIDDEN` |
| `device` | `source_id` là cảm biến đã đăng ký trong đúng tòa nhà, đo đúng `metric` (và gắn đúng `asset_id` nếu có), **và** `source` là `bms`, `iot` hoặc `instrument` | `FORBIDDEN` |

**Lý do:** nếu agent được ghi số đo "do kỹ thuật viên B đo" khi đang phục vụ kỹ thuật viên A, nó có thể bịa bất kỳ con số nào và gán cho một người chưa từng được hỏi. `FORBIDDEN` dùng đúng câu chữ của mọi lần từ chối khác, nên lời từ chối không tiết lộ ai đang làm việc đó.

Một thiết bị không gõ tay số liệu, nên `kind: device` đi kèm `source: manual_entry` cũng bị từ chối.

### 3.2. Số đo bất thường được ghi và gắn cờ, không bị từ chối

| Tình huống | Kết quả |
|---|---|
| Giá trị ngoài khoảng thường gặp (ví dụ dòng rò 180 mA) | Vẫn ghi, gắn cờ `out_of_expected_range` |
| `measured_at` cũ hơn 24 giờ | Vẫn ghi, gắn cờ `late_entry` |
| `measured_at` muộn hơn giờ server quá 5 phút | `INVALID_INPUT` |
| Đơn vị không được chấp nhận cho metric (`psi` cho `drain_flow`) | `INVALID_INPUT`, `field: "unit"` |
| Metric không có trong danh mục | `INVALID_INPUT`, `field: "metric"` |

**Lý do:** ở ca Level 1 cầu dao tóe lửa, số 180 mA chính là số người trực cần thấy nhất. Một tool từ chối nó vì "bất thường" sẽ làm mất đúng dữ liệu cần cho quyết định an toàn.

Đơn vị lạ thì khác: số đo đã ghi trở thành bằng chứng rằng việc sửa đạt yêu cầu, và một con số không quy đổi được về đơn vị đã biết không được trở thành bằng chứng. Điều này khác `sensor.read` ở đợt 3, nơi số đo lạ đơn vị chỉ bị hạ chất lượng, vì đọc thì chỉ hiển thị, còn ghi thì người khác sẽ dựa vào.

Giá trị được quy đổi về đơn vị chuẩn (`0.18 A` → `180 mA`, `250 kPa` → `2.5 bar`); giá trị và đơn vị gốc được giữ trong bản ghi, đúng như `tools.md` §4.2 yêu cầu.

### 3.3. Nộp kết quả: điều kiện để được nộp

Nếu bất kỳ điều kiện nào sai, **cả lần nộp bị từ chối và không lưu gì**:

| Kiểm tra | Sai thì |
|---|---|
| Work order có trong tòa được hỏi | `NOT_FOUND` — như nhau cho work order ở tòa khác và work order không tồn tại |
| `assignment_id` thuộc work order đó và đang `accepted` | `CONFLICT`, `field: "assignment_id"` |
| Người nộp là kỹ thuật viên của assignment, hoặc có vai trò `management` | `FORBIDDEN` |
| Mọi `measurement_ids` tồn tại và thuộc đúng work order | `CONFLICT`, `field: "measurement_ids"` |
| Mọi `evidence_ids` là ảnh đã đăng ký, còn `active`, file `ready`, cùng ticket | `CONFLICT`, `field: "evidence_ids"` |

Mỗi vấn đề là một lỗi riêng, nên kỹ thuật viên biết hết những gì cần sửa trong một lần trả lời.

**Lý do không bỏ qua id lỗi rồi lưu phần còn lại:** một kết quả âm thầm mất một ảnh sẽ bị đánh giá với ít bằng chứng hơn những gì kỹ thuật viên nghĩ mình đã gửi.

### 3.4. Ảnh còn đang tải không phải là bằng chứng

Database không cho một file thành `evidence_items` khi chưa `ready` (trigger `app_validate_evidence`). Vì vậy, lúc ảnh đang tải, agent chỉ cầm được **id của file**, không phải id của ảnh đã đăng ký.

Adapter phân biệt hai trường hợp:

- Id không trỏ tới gì → "evidence X does not exist".
- Id là một file có thật nhưng chưa đăng ký → "evidence X is an upload that has not been registered as evidence (file staged)".

**Lý do:** báo "không tồn tại" thì agent hiểu là mình bịa id. Báo rõ là đang tải thì agent biết phải đợi. Đây là ca L1-17.

### 3.5. `validation_status` không có nghĩa là xong việc

Kết quả hợp lệ được lưu, kèm `validation_status` xét theo thứ tự cố định, không dùng LLM:

| Điều kiện | `validation_status` |
|---|---|
| Có mục checklist `failed`, hoặc số đo được dẫn có cờ `out_of_expected_range`, hoặc `completed_at` trước lúc nhận việc | `HUMAN_REVIEW`, liệt kê trong `conflicts` |
| Không có ảnh `after` nào | `NEEDS_EVIDENCE`, `missing_evidence: ["after_photo"]` |
| Còn lại | `ACCEPTED` |

`missing_evidence` vẫn được báo kể cả khi đã là `HUMAN_REVIEW`, để kỹ thuật viên biết cả hai điều trong một lần.

**Tool không đổi trạng thái work order hay ticket.** `ACCEPTED` chỉ nghĩa là hồ sơ đủ để xác minh. Kết luận việc đã xong là việc của `technical.verify_resolution` và người có thẩm quyền. Test luồng đọc lại work order từ database sau khi nộp để chứng minh điều này.

### 3.6. Chống ghi trùng trong host

| Tình huống | Kết quả |
|---|---|
| Lần đầu với khóa này | Chạy tool, lưu kết quả kèm hash của payload |
| Gọi lại cùng khóa, cùng payload | Trả **đúng kết quả cũ**, không ghi lần hai; audit ghi `idempotent_replay: true` |
| Cùng khóa, payload khác | `CONFLICT`, `field: "idempotency_key"`, `retryable: false` |
| Hai lời gọi cùng khóa chạy đồng thời | Chỉ một cái chạy; cái kia `CONFLICT`, `retryable: true` |
| Tool từ chối (`FORBIDDEN`, `INVALID_INPUT`, `NOT_FOUND`, `CONFLICT`) | Không giữ khóa |
| Tool lỗi giữa chừng | Giải phóng khóa |
| Host từ chối trước khi tới tool (thiếu quyền, sai schema, tòa ngoài quyền) | Không đụng tới khóa |

Khóa có phạm vi `(tenant, tên tool, idempotency_key)`. Hash là SHA-256 của input đã sắp xếp khóa, bỏ `idempotency_key`.

**Vì sao lời gọi bị từ chối không giữ khóa:** nó chưa ghi gì. Giữ khóa thì agent phải bịa khóa mới chỉ để gửi lại yêu cầu đã sửa, trong khi gửi lại cùng khóa chính là điều cơ chế này cho phép.

**Vì sao sắp xếp khóa trước khi hash:** framework của agent không bắt buộc giữ thứ tự thuộc tính. Một lần retry tình cờ đổi thứ tự mà bị coi là yêu cầu khác thì sẽ bị từ chối oan.

**Khi timeout, khóa đi theo lần chạy, không theo lời gọi.** Nếu agent thôi chờ ở mốc timeout, lần ghi vẫn có thể hoàn tất ngay sau đó. Giải phóng khóa lúc ấy thì lần retry sẽ ghi lần thứ hai. Vì vậy khóa chỉ được hoàn tất hoặc giải phóng khi lần chạy thật sự kết thúc; retry trong khoảng giữa nhận `CONFLICT` `retryable: true`. Đây là điểm cần anh Quang xác nhận (xem [yêu cầu](../requests/Q02-measurement-result.md) mục 4).

## 4. Dữ liệu mẫu

Mốc thời gian vẫn là 30/09/2026 09:00 UTC.

### 4.1. Seed vào database thật (`fixtures/work-orders.ts`, `support/seed-db.ts`)

Seed đi qua đúng các trigger của baseline (`app_assignment_capacity`, `app_validate_evidence`), nên dữ liệu mẫu chỉ hợp lệ khi chính database chấp nhận.

| Mã | Ticket / tòa | Kỹ thuật viên | Assignment | Ảnh | Dùng cho |
|---|---|---|---|---|---|
| WO-AC | điều hòa A1-1205 chảy nước | KT-001 | `accepted` 07:30 | `before`, `after`, một ảnh `withdrawn` | Level 3 thuận |
| WO-LEAK | rò âm tường A1-1205 | KT-001 | `accepted` 07:40 | chỉ `before` | `NEEDS_EVIDENCE`, ảnh ticket khác |
| WO-BREAKER | cầu dao A1-1205 tóe lửa | KT-002 | `accepted` 08:00 | `after` + 1 file còn `staged` | Level 1, ảnh đang tải |
| WO-OLD | cửa sổ A1-1205 | KT-001 | `released` | — | assignment hết hiệu lực |
| WO-B1 | điều hòa B1-0501 | KT-003 | `accepted` | `after` | work order ngoài tòa được hỏi |

Không dùng assignment `offered`, vì trigger so hạn của lời mời với đồng hồ thật của database chứ không phải mốc `NOW` của test.

### 4.2. Ca theo mức độ (`measurement-result.flow.test.ts`)

| Ca | Mức | Tình huống | Kết quả |
|---|---|---|---|
| L3-14 | 3 | Đo lưu lượng thoát nước 1.2 L/min sau vệ sinh | `OK`, không cờ |
| L3-15 | 3 | Cùng số đo, đơn vị viết `l/min` | `OK`, quy về `L/min`, giữ đơn vị gốc |
| L3-16 | 3 | Nộp kết quả đầy đủ, dẫn số đo của L3-14 | `ACCEPTED` |
| L2-16 | 2 | Tường thấm, độ ẩm 35% | `OK`, cờ `out_of_expected_range` |
| L2-17 | 2 | Nộp khi chưa có ảnh sau sửa chữa | `NEEDS_EVIDENCE`, `after_photo` |
| L2-18 | 2 | Một mục checklist không đạt | `HUMAN_REVIEW` |
| L1-16 | 1 | Dòng rò 180 mA | `OK`, ghi nguyên 180, cờ `out_of_expected_range` |
| L1-17 | 1 | Nộp khi một ảnh còn đang tải | `CONFLICT`, không lưu gì; ảnh xong thì nộp lại cùng khóa được |
| L1-18 | 1 | Agent ghi số đo nhân danh kỹ thuật viên khác | `FORBIDDEN` |
| L1-19 | 1 | Ghi số đo nhân danh thiết bị không hợp lệ (5 biến thể) | `FORBIDDEN` |

## 5. Kiểm thử

**561 test trong `server/tests/technical-tools/`, tất cả đều qua** (đợt trước 388, đợt này thêm 173).

| File | Số test | Kiểm tra |
|---|---|---|
| `idempotency.test.ts` | 25 | 6 ca I-1…I-6 bằng tool ghi giả đưa thẳng vào host; hash không phụ thuộc thứ tự khóa; timeout giữ khóa tới khi chạy xong; tool đọc không đụng tới kho khóa; tool ghi thiếu `idempotency_key` không định nghĩa được |
| `measurement-result.contract.test.ts` | 23 | Hai ví dụ mẫu `tools.md` qua schema; trường bắt buộc khớp đặc tả; độ dài khóa; `completed_at` trước `started_at`; `quantity` ≤ 0; checklist rỗng; `tenant_id` tự thêm |
| `measurement-result.rules.test.ts` | 54 | Quy đổi từng metric; biên của cờ; ai được ghi số đo; từng loại ảnh lỗi; thứ tự quyết định `validation_status` |
| `measurement-result.db.test.ts` | 25 | Adapter trên schema thật: work order ngoài tòa, assignment `released`, ảnh `withdrawn` / ticket khác / file `staged`, RLS theo tenant, role chỉ đọc không sửa được gì |
| `measurement-result.flow.test.ts` | 43 | 10 ca theo mức độ, chống ghi trùng trên tool thật, work order không đổi sau khi nộp, quyền, audit không chứa giá trị đo |

Cập nhật test có sẵn: `catalog.test.ts` (8 tool; tool ghi phải yêu cầu `idempotency_key`), `host.test.ts` (thêm các port mới), `outage-schedule.db.test.ts` (role runtime giờ được đọc `tickets`, nên ca "không được đọc bảng không liên quan" chuyển sang `invoices`).

Đã chạy trên hai môi trường:

- **PGlite** (mặc định): 27 giây.
- **PostgreSQL 17** thật qua `TEST_DATABASE_URL`: 92 giây, cùng 561 test.

Test đã bắt được **một lỗi thật trong code**: `normalize` tra hệ số quy đổi bằng `units[unit]`, nên `"constructor"` hay `"__proto__"` lọt qua như một đơn vị hợp lệ và cho ra `NaN`. Đã sửa bằng `Object.hasOwn`.

Đã thử cố ý phá năm quy tắc để xác nhận test bắt được:

| Phá gì | Số test đỏ |
|---|---|
| Bỏ kiểm tra "người đo phải là người đang gọi" | 2 |
| Bỏ so sánh hash — cùng khóa khác payload vẫn chạy | 3 |
| Chấp nhận file `staged` làm bằng chứng | 5 |
| `ACCEPTED` khi không có ảnh `after` | 6 |
| Không giải phóng khóa khi tool lỗi | 2 |

```
bun test server/tests/technical-tools
bun run --filter server typecheck
bunx biome check server/src/technical-tools server/tests/technical-tools
```

Cả ba lệnh đều sạch.

## 6. Còn lại

- **6 tool chưa có code:** `maintenance_history.append`, `technical.verify_resolution`, và 4 tool yêu cầu rủi ro.
- **Số đo, kết quả và khóa chống trùng đang ở bộ nhớ** (adapter POC): mất khi khởi động lại, và khóa không có tác dụng giữa nhiều tiến trình. Xem [Q02-measurement-result.md](../requests/Q02-measurement-result.md).
- **Ba việc chặn bot dùng tool** (nối vào server, `ContextResolver` thật, nơi ghi audit) vẫn như các đợt trước. Với đợt này, `ContextResolver` thật còn phải trả đúng `user_id` của người mà run phục vụ, vì quy tắc 3.1 dựa vào nó.

## 7. Phạm vi thay đổi

Chỉ tạo và sửa file trong vùng của Team Quang: `server/src/technical-tools/**`, `server/tests/technical-tools/**`, `docs/teams/quang/**`. Không sửa schema, migration, `app.ts`, `index.ts`, `package.json` hay lockfile.
