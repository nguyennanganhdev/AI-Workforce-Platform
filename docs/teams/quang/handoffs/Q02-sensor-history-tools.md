# Báo cáo Q02 (đợt 3) — Tool đọc cảm biến và lịch sử bảo trì

- **Người làm:** Phạm Thành Đạt (Team Quang).
- **Ngày:** 01/10/2026.
- **Task:** Q01 (danh mục tool) và Q02 (tool kỹ thuật), đợt 3.
- **Trạng thái:** xong 6 trong 14 tool — **toàn bộ nhóm tra cứu**. Tool vẫn chưa gọi được từ server đang chạy vì chưa được nối vào `createApp` (việc của Team Chiến).
- **Các đợt trước:** [Q02-outage-schedule-tools.md](Q02-outage-schedule-tools.md), [Q02-sop-asset-tools.md](Q02-sop-asset-tools.md). Quyết định dùng chung đã giải thích ở đó và không nhắc lại.

## 1. Đã xây gì

| Tool | Trả lời câu hỏi | Nguồn dữ liệu | Đặc tả |
|---|---|---|---|
| `sensor.read` | Cảm biến của thiết bị này đang đo được gì, và số đó còn mới không? | Adapter POC (chưa có bảng) | `tools.md` §3.3 |
| `maintenance_history.read` | Thiết bị này đã được bảo trì/sửa những lần nào, lỗi có lặp lại không? | Adapter POC (chưa có bảng) | `tools.md` §3.4 |

Kèm theo:

- **Danh mục metric** ([reference/metrics.ts](../../../../server/src/technical-tools/reference/metrics.ts)): mỗi đại lượng đo được chấp nhận đơn vị nào.
- **Schema khoảng thời gian dùng chung** ([contracts/time-range.ts](../../../../server/src/technical-tools/contracts/time-range.ts)), `utility_schedule.read` cũng chuyển sang dùng.
- **Host kiểm tra output chặt hơn** (mục 3.7).
- **Sửa một lệch đặc tả của đợt 2** ở `asset.read` (mục 3.8).

## 2. Vì sao làm hai tool này tiếp

Đây là hai tool tra cứu cuối cùng. Làm xong thì bot có đủ đầu vào cho bước "đề xuất xử lý" trong luồng chung (`general.md` §6 bước 6): biết thiết bị nào, quy trình nào, cảm biến đang báo gì, và lỗi này đã từng xảy ra chưa.

Cả hai tra theo `asset_id`, nên dựa trực tiếp trên `asset.read` đã làm ở đợt 2.

## 3. Quyết định thiết kế và lý do

### 3.1. Số đo cũ vẫn được trả, nhưng dán nhãn `STALE_DATA`

Số đo mới nhất quá `max_age_seconds` (mặc định 900 giây) → trạng thái `STALE_DATA`, `freshness: "stale"`, **vẫn kèm toàn bộ số đo**. Lời nhắn nói rõ không được dùng để kết luận thiết bị an toàn hay đã sửa xong.

**Lý do:** `tools.md` §3.3 yêu cầu "vẫn có thể kèm readings để hiển thị", và `general.md` §11 yêu cầu "đánh dấu stale và không dùng để kết luận an toàn". Giấu số đo cũ đi thì bot không biết cảm biến đã im lặng từ lúc nào — đó cũng là một phát hiện.

`STALE_DATA` không bị đánh dấu là lỗi (`isError: false`), vì bot hành động được với nó: cử người đến kiểm tra.

### 3.2. Độ mới đo từ cuối khoảng hỏi, không phải luôn từ "bây giờ"

Tuổi của số đo = `min(time_range.to, giờ server)` − thời điểm số đo mới nhất.

**Lý do:** câu hỏi về sự cố hôm qua là "lúc đó cảm biến còn báo không", không phải "bây giờ còn báo không". Nếu luôn so với bây giờ, mọi số đo của hôm qua đều bị coi là cũ, kể cả số đo đúng phút sự cố xảy ra.

### 3.3. Không số đo khác với không có cảm biến

| Tình huống | Kết quả |
|---|---|
| Không có cảm biến nào đo `metric` đó cho thiết bị | `NOT_FOUND` |
| Có cảm biến, nhưng không gửi gì trong khoảng hỏi | `OK`, `readings: []`, `freshness: "unknown"` |

**Lý do:** hai câu trả lời dẫn tới hai hành động khác nhau. "Không có cảm biến" nghĩa là phải kiểm tra tại chỗ. "Cảm biến im lặng" nghĩa là chính cảm biến có vấn đề. Cảm biến im lặng vẫn được ghi trong `provenance`, vì sự im lặng của nó là phát hiện.

### 3.4. Số đo xấu không bị giấu, số đo sai đơn vị bị hạ chất lượng

- `quality` của nguồn (`good` / `uncertain` / `bad` / `unknown`) được giữ nguyên. Tool **không lọc bỏ** số đo xấu.
- Số đo có đơn vị không nằm trong danh mục của metric đó (ví dụ độ ẩm tường tính bằng `C`) vẫn được trả nguyên giá trị và đơn vị, nhưng `quality` bị hạ thành `bad`.
- Metric không có trong danh mục thì không kiểm tra đơn vị.

**Lý do:** ở ca Level 1 ổ cắm tóe lửa, cảm biến dòng rò báo một giá trị 180 mA mà chính nó đánh dấu `bad`. Giấu đi thì bot chỉ thấy các số bình thường trước đó và có thể nói "dòng rò ổn". Còn với đơn vị sai, tool không tự quy đổi vì như thế là đoán ý cảm biến; chỉ đánh dấu để không ai dựa vào nó.

Metric ngoài danh mục không bị hạ chất lượng vì danh mục ngắn là khoảng trống cho Domain Owner lấp (`general.md` §14), không phải lỗi của dữ liệu.

### 3.5. Quá nhiều số đo thì yêu cầu thu hẹp, không cắt bớt

Quá 200 số đo trong khoảng hỏi → `NEEDS_INPUT`, `missing_fields: ["time_range"]`, không kèm dữ liệu.

**Lý do:** danh sách bị cắt còn 200 dòng trông giống hệt một danh sách đầy đủ. Bot sẽ lập luận từ nửa buổi sáng như thể đó là cả buổi. Output schema của `tools.md` không có trường nào báo "đã bị cắt", nên cách trung thực duy nhất là từ chối và yêu cầu khoảng hẹp hơn.

### 3.6. Lịch sử bảo trì: ba quy tắc

**Bản ghi đã bị sửa không được trả về.** Lịch sử chỉ được thêm, không sửa (`tools.md` §1.4). Bản ghi sai vẫn nằm đó, bản sửa trỏ tới nó qua `supersedes_event_id`. Tool chỉ trả bản sửa. Trong dữ liệu mẫu, một bản ghi nói "đã thay bơm thoát nước" và bản sửa nói "chỉ vệ sinh đường thoát" — trả cả hai thì bot sẽ nói với kỹ thuật viên rằng bơm đã được thay.

**`repeat_count` chỉ đếm sự kiện phát sinh từ sự cố** (có `incident_id`), đếm trên cả khoảng hỏi chứ không chỉ trang đã cắt theo `limit`. Bảo trì định kỳ không phải lỗi lặp; đếm cả nó thì một chiếc điều hòa được chăm sóc tốt trông như sắp hỏng. Đếm theo trang thì con số phụ thuộc vào `limit`.

**`last_maintenance_at` không bị `time_range.from` giới hạn.** Hỏi "30 ngày gần đây" với cầu dao được thay từ tháng 11 năm ngoái: `events` rỗng, nhưng `last_maintenance_at` vẫn là ngày tháng 11. Nếu giới hạn theo `from`, câu trả lời sẽ là `null`, và bot có thể nói với người trực rằng thiết bị chưa từng được bảo trì.

Ngoài ra, thiết bị được tra qua `asset.read` trước: `asset_id` không có trong tòa → `NOT_FOUND`, không phải lịch sử rỗng. "Không có lần sửa nào" cho một thiết bị không tồn tại là câu bot sẽ nhắc lại với cư dân.

### 3.7. Host kiểm tra output mỗi khi có dữ liệu, không chỉ khi `OK`

Trước đợt này host chỉ kiểm tra output schema khi trạng thái là `OK`. Giờ kiểm tra mỗi khi `data` khác null.

**Lý do:** `NEEDS_INPUT` của `asset.read` mang danh sách ứng viên, `STALE_DATA` của `sensor.read` mang số đo cũ. Bot đọc những dữ liệu đó kỹ không kém một kết quả `OK`, nên dữ liệu sai hình dạng ở đó cũng gây hiểu sai không kém. Đây là khoảng trống mình để lại ở đợt 1.

### 3.8. Sửa lệch đặc tả của `asset.read` (đợt 2)

`tools.md` §3.2 ghi `oneOf` cho `asset_id` / `location`, nghĩa là **đúng một**. Code đợt 2 chấp nhận cả hai cùng lúc. Giờ truyền cả hai → `INVALID_INPUT` ("Give exactly one of asset_id or location."). `sensor.read` áp dụng cùng quy tắc cho `sensor_id` / `asset_id`.

**Lý do:** cho cả hai thì không rõ cái nào quyết định khi chúng chỉ tới hai thiết bị khác nhau.

## 4. Dữ liệu mẫu

Mốc thời gian vẫn là 30/09/2026 09:00 UTC. Thêm máy lọc nước `WF-A1-1205-01` vào danh sách thiết bị (12 thiết bị).

### 10 cảm biến (`fixtures/sensors.ts`)

| Cảm biến | Để chứng minh |
|---|---|
| SNS-AC1-COND | luồng thuận: 6 số đo trong giờ trước, mực nước ngưng tăng dần |
| SNS-AC2-COND | 360 số đo mỗi phút, quá nhiều cho một câu trả lời |
| SNS-WH1-TEMP | im lặng từ 07:30 → `STALE_DATA` |
| SNS-WF1-FLOW | chỉ có số đo hôm qua → hôm nay rỗng, `unknown` |
| SNS-BP12-CUR | số đo mới nhất bị cảm biến đánh dấu `bad` |
| SNS-BP1-CUR-A, -B | hai cảm biến trên cùng một tủ điện |
| SNS-1205-HUM | đo tường, không gắn thiết bị; một số đo gửi sai đơn vị |
| SNS-B1-COND, SNS-X1-COND | tòa ngoài quyền, tenant khác |

### 32 sự kiện bảo trì (`fixtures/maintenance.ts`)

- **Điều hòa phòng khách A1-1205:** hai lần vệ sinh đường thoát do sự cố (7 và 8/2026), một lần bảo trì định kỳ, và một bản ghi sai đã được sửa → `repeat_count = 2`.
- **Cầu dao A1-1205:** chỉ một lần thay từ 11/2025.
- **Điều hòa A1-1105:** 25 sự kiện cách nhau 10 ngày, 13 trong số đó do sự cố → trang 20 dòng, `repeat_count` vẫn là 13.
- **Máy nước nóng, máy lọc nước:** không có lịch sử.
- **Tòa B1 và tenant khác:** mỗi nơi một sự kiện, để chứng minh không lọt ra.

### 15 ca theo mức độ

Trong `sensor-history.flow.test.ts`: L3-11…L3-13, L2-11…L2-15, L1-11…L1-15. Mỗi ca gồm tình huống cư dân báo, lời gọi tool và kết quả phải ra.

## 5. Kiểm thử

**388 test trong `server/tests/technical-tools/`, tất cả đều qua** (đợt trước 284, đợt này thêm 104).

| File | Số test | Kiểm tra |
|---|---|---|
| `sensor-history.contract.test.ts` | 26 | Hai ví dụ mẫu của `tools.md` qua được schema; `oneOf`; giới hạn `max_age_seconds`, `limit`; khoảng thời gian đảo ngược |
| `sensor-history.rules.test.ts` | 27 | Độ mới tại biên ngưỡng; mốc so `min(to, now)`; giữ số đo mọi chất lượng; đơn vị sai; bỏ bản ghi bị sửa; `repeat_count`; `last_maintenance_at` |
| `sensor-history.adapter.test.ts` | 15 | Adapter mặc định rỗng; không trả dữ liệu tòa khác, tenant khác kể cả khi biết đúng id |
| `sensor-history.flow.test.ts` | 28 | 15 ca theo mức độ, ca không tồn tại, phân trang, quyền, provenance, audit, gọi qua `createTechnicalToolCaller` |
| `host.test.ts` | 5 | Dữ liệu sai hình dạng dưới `OK`, `STALE_DATA`, `NEEDS_INPUT` đều thành `INTERNAL_ERROR` |

Cập nhật test có sẵn: `catalog.test.ts` (6 tool), `sop-asset.contract.test.ts` (ca truyền cả `asset_id` lẫn `location`).

Đã chạy trên hai môi trường:

- **PGlite** (mặc định): 13 giây.
- **PostgreSQL 17.11** thật qua `TEST_DATABASE_URL`: 43 giây, cùng 388 test. Chạy lại để chắc phần sửa `host.ts` không làm hỏng 4 tool cũ.

Test đã bắt được **hai lỗi trong kỳ vọng của chính mình**:

- Mình kỳ vọng mã `ME-103` (bản ghi sai) không xuất hiện ở đâu trong câu trả lời. Nhưng bản sửa `ME-104` đúng ra **phải** ghi `correction:ME-103` trong `source_refs` — đó là dấu vết của lần sửa. Đã sửa test cho đúng: `ME-103` không xuất hiện *như một sự kiện*.
- Một test kiểm tra câu trả lời không chứa chữ `"not"`, nhưng câu thông báo lỗi chuẩn có sẵn "could not complete". Đã đổi sang chuỗi đánh dấu riêng.

Đã thử cố ý phá năm quy tắc để xác nhận test bắt được:

| Phá gì | Số test đỏ |
|---|---|
| Số đo cũ báo là `fresh` | 6 |
| Lọc bỏ số đo `quality=bad` | 2 |
| `repeat_count` đếm cả bảo trì định kỳ | 4 |
| Trả cả bản ghi đã bị sửa | 6 |
| Host chỉ kiểm tra output khi `OK` (hành vi cũ) | 2 |

Lần đầu thử "lọc bỏ số đo `bad`" chỉ có 1 test đỏ. Quy tắc này quan trọng nên mình thêm một test ở tầng luật; giờ là 2.

```
bun test server/tests/technical-tools
bun run --filter server typecheck
bunx biome lint server/src/technical-tools server/tests/technical-tools
```

Cả ba lệnh đều sạch.

## 6. Còn lại

- **8 tool chưa có code:** 3 tool ghi nhận (`technical.record_measurement`, `technical.submit_executor_result`, `maintenance_history.append`), 1 tool xác minh (`technical.verify_resolution`), 4 tool yêu cầu rủi ro.
- **Host chưa có idempotency.** Đây là việc phải làm đầu tiên ở đợt sau, vì cả 7 tool còn lại đều ghi dữ liệu.
- **Nguồn dữ liệu cảm biến và bảo trì** là POC. Xem [Q02-sensor-history.md](../requests/Q02-sensor-history.md).
- **Ba việc chặn bot dùng tool** (nối vào server, `ContextResolver` thật, nơi ghi audit) vẫn như các đợt trước.

## 7. Phạm vi thay đổi

Chỉ tạo và sửa file trong vùng của Team Quang: `server/src/technical-tools/**`, `server/tests/technical-tools/**`, `docs/teams/quang/**`. Không sửa schema, migration, `app.ts`, `index.ts`, `package.json` hay lockfile.
