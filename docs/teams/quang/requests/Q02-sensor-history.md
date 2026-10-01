# Q02 (đợt 3) — Yêu cầu tích hợp cho tool đọc cảm biến và lịch sử bảo trì

- **Từ:** Team Quang (tool kỹ thuật), task Q01/Q02.
- **Gửi:** Team Chiến (mục 1–2), Domain Owner (mục 3), anh Quang (mục 4).
- **Ngày:** 01/10/2026.
- **Liên quan:** `sensor.read`, `maintenance_history.read` (`docs/teams/quang/tools.md` §3.3, §3.4).
- **Các đợt trước:** [Q02-interruptions.md](Q02-interruptions.md), [Q02-sop-asset.md](Q02-sop-asset.md). Các yêu cầu ở đó vẫn còn nguyên; file này chỉ nêu phần thêm.

## 1. Capability mới

**Owner:** Chiến (C06 — runtime gateway).

`ContextResolver` cần cấp thêm hai capability cho technical agent: `sensor:read` và `maintenance:read`. Hợp đồng `ResolvedIdentity` không đổi so với đợt 2.

## 2. Bảng còn thiếu

**Owner:** Chiến (`server/src/db/**`). Cả hai tool đang chạy trên adapter POC; adapter **không tự chứa dữ liệu**, phải được nạp từ bên ngoài, mặc định rỗng. Không deployment nào trả số đo hay lịch sử bịa như dữ liệu thật.

### 2.1. Cảm biến và số đo

Trường tối thiểu `sensor.read` cần:

| Bảng đề xuất | Trường |
|---|---|
| `sensors` | `sensor_id`, `tenant_id`, `building_id`, `asset_id?` (null cho cảm biến đo một vị trí), `metric`, `unit`, `status` |
| `sensor_readings` | `sensor_id`, `tenant_id`, `metric`, `value`, `unit`, `observed_at`, `quality` (`good`/`uncertain`/`bad`/`unknown`), `received_at` |

**Ghi chú:**

- Mỗi số đo cần mang **đơn vị riêng**, không chỉ đơn vị khai báo của cảm biến. Cảm biến cấu hình sai chính là cái có số đo khác đơn vị khai báo, và tool dùng chênh lệch đó để hạ chất lượng.
- Nên có index `(tenant_id, sensor_id, observed_at)`. Tool đọc theo khoảng thời gian và từ chối khi quá 200 số đo.
- Có thể nguồn thật là một BMS/IoT gateway bên ngoài thay vì bảng. Khi đó chỉ cần một adapter mới theo `SensorReadPort`; tool không phải sửa.

### 2.2. Sự kiện bảo trì

| Bảng đề xuất | Trường |
|---|---|
| `maintenance_events` | `event_id`, `tenant_id`, `building_id`, `asset_id`, `incident_id?` (ticket), `workorder_id?`, `occurred_at`, `outcome`, `source_refs`, `supersedes_event_id?`, `recorded_by`, `created_at` |

**Ghi chú:**

- **Chỉ thêm, không sửa** (`tools.md` §1.4). Bản ghi sai được thay bằng bản mới trỏ `supersedes_event_id`. Nên có trigger append-only như các bảng lịch sử khác trong baseline (`app_append_only`).
- `incident_id` là cách duy nhất phân biệt sửa chữa do sự cố với bảo trì định kỳ; `repeat_count` dựa vào nó.
- Tool `maintenance_history.append` ở đợt sau sẽ ghi vào bảng này, nên cần chốt bảng trước khi làm tool đó.

## 3. Cần Domain Owner quyết

`general.md` §14 để mở "các loại sensor và metric nào được đưa vào demo". Danh mục metric hiện có ([reference/metrics.ts](../../../../server/src/technical-tools/reference/metrics.ts)) chỉ gồm các metric mà luồng kỹ thuật đang dùng:

| Metric | Đơn vị chấp nhận |
|---|---|
| `condensate_level` | mm |
| `outlet_temperature` | C, °C |
| `leakage_current` | mA |
| `surface_moisture` | % |
| `flow_rate`, `drain_flow` | L/min |
| `supply_pressure` | bar |
| `crack_width`, `door_gap` | mm |

Cần xác nhận danh sách này và **ngưỡng cũ** cho từng metric. Hiện mặc định 900 giây cho mọi metric; nhưng ví dụ độ ẩm tường thay đổi chậm, có thể chấp nhận số đo cũ hơn nhiều so với dòng rò điện.

Metric ngoài danh mục không bị từ chối; chỉ là đơn vị của nó không được kiểm tra.

## 4. Điểm cần anh Quang chốt trong `tools.md`

`tools.md` chưa nói rõ các điểm sau. Đợt này chọn như cột phải:

| # | Vấn đề | Đang làm |
|---|---|---|
| 4.1 | Độ mới so với mốc nào | So với `min(time_range.to, giờ server)`. Luôn so với "bây giờ" thì mọi số đo hôm qua đều cũ, kể cả số đo đúng lúc sự cố |
| 4.2 | Cảm biến có nhưng không có số đo trong khoảng hỏi | `OK`, `readings: []`, `freshness: "unknown"`. Không phải `NOT_FOUND`, vì "cảm biến im lặng" khác "không có cảm biến" |
| 4.3 | Quá nhiều số đo | Quá 200 → `NEEDS_INPUT` yêu cầu thu hẹp `time_range`. Output schema không có trường báo "đã cắt bớt", nên cắt âm thầm là không trung thực |
| 4.4 | Số đo sai đơn vị | Trả nguyên giá trị và đơn vị, hạ `quality` thành `bad` |
| 4.5 | `repeat_count` đếm gì | Chỉ sự kiện có `incident_id`, trên cả khoảng hỏi. Ví dụ §3.4 của `tools.md` khớp với cách hiểu này |
| 4.6 | `last_maintenance_at` có bị giới hạn bởi `time_range.from` không | Không. Chỉ giới hạn bởi `time_range.to` |
| 4.7 | Thứ tự `events` | Mới nhất trước |
| 4.8 | `provenance` của cảm biến | Mỗi cảm biến một dòng, kể cả cảm biến không gửi số đo nào |

## Dữ liệu mẫu và test

- Dữ liệu: `server/tests/technical-tools/fixtures/sensors.ts` (10 cảm biến) và `fixtures/maintenance.ts` (32 sự kiện).
- Test: 388 test trong `server/tests/technical-tools/`, đã chạy trên cả PGlite và PostgreSQL 17.11.

```
bun test server/tests/technical-tools
```
