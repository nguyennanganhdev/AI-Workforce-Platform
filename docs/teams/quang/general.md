---
title: "Đặc tả hệ thống domain kỹ thuật A2"
version: "1.0 Draft"
date: "29/09/2026"
audience: "Nhóm phát triển domain kỹ thuật, BA, QA và Domain Owner"
purpose: "Mô tả đơn giản các chức năng, dữ liệu, tool và luồng xử lý thuộc domain kỹ thuật"
scope: "Technical Agent A2 và các capability kỹ thuật trong POC Vinhomes"
document_type: "technical-specification"
---

# Đặc tả hệ thống domain kỹ thuật A2

POC Agent Factory Platform tại Vinhomes

Tài liệu này giúp nhóm thống nhất phần cần xây cho domain kỹ thuật. Các dịch vụ dùng chung như Orchestrator, Approval, Notification và Work Order Platform chỉ được nhắc đến như hệ thống phụ thuộc; tài liệu không đặc tả cách chúng được xây bên trong.

## Tóm tắt hệ thống

Technical Agent A2 nhận sự cố kỹ thuật đã được chuyển đến đúng phạm vi, kiểm tra dữ liệu, phân loại vấn đề và mức độ, tra cứu thông tin kỹ thuật, đề xuất cách xử lý, hỗ trợ tạo yêu cầu công việc và kiểm tra bằng chứng sau khi kỹ thuật viên thực hiện.

Nhận sự cố

-> Kiểm tra thông tin

-> Phân loại vấn đề và mức độ

-> Tra SOP tài sản lịch sử và dữ liệu vận hành

-> Đề xuất phương án

-> Tạo Work Order nháp qua dịch vụ dùng chung

-> Nhận kết quả kỹ thuật viên

-> Kiểm tra evidence

-> Chuyển người có thẩm quyền xác nhận hoàn tất

Ranh giới quan trọng là Agent chỉ phân tích, đề xuất và tạo yêu cầu. Agent không điều khiển thiết bị, không tự vào căn hộ, không tự ngắt điện hoặc khóa van và không xác nhận an toàn thay kỹ thuật viên.

## 1 Mục tiêu và phạm vi

### 1.1 Mục tiêu

- Chuẩn hóa cách tiếp nhận và phân loại sự cố kỹ thuật.
- Phát hiện sớm tình huống nguy hiểm để chuyển người xử lý.
- Tra cứu đúng SOP, tài sản và lịch sử liên quan.
- Tạo đầu ra đủ thông tin để lập Work Order.
- Theo dõi kết quả và kiểm tra evidence trước khi đề nghị hoàn tất.

### 1.2 Trong phạm vi

- Sự cố điện, nước, điều hòa, thiết bị, cửa, kính, tường, trần, sàn và nội thất cố định.
- Phân loại Level 1, Level 2 và Level 3.
- Tra cứu SOP, asset, sensor, outage và maintenance history.
- Ghi số đo, nhận kết quả kỹ thuật viên và kiểm tra điều kiện hoàn tất.
- Tạo yêu cầu phê duyệt cho cô lập tiện ích, hạn chế khu vực, vào căn hộ và điều động nhà thầu.

### 1.3 Ngoài phạm vi

- Xây dựng Factory, Evaluation hoặc Orchestrator.
- Xây dựng hệ thống notification, approval hoặc Work Order dùng chung.
- Điều khiển trực tiếp thiết bị vật lý.
- Quyết định chi phí, pháp lý hoặc trách nhiệm tài chính.
- Thay kỹ thuật viên xác nhận an toàn hoặc nguyên nhân cuối cùng.

## 2 Người dùng và hệ thống liên quan

| Đối tượng | Vai trò đối với domain kỹ thuật |
| --- | --- |
| Cư dân | Cung cấp mô tả, vị trí, ảnh và phản hồi sau xử lý |
| Technical Agent A2 | Phân loại, tra cứu, đề xuất, theo dõi và kiểm tra evidence |
| Kỹ thuật viên | Kiểm tra hiện trường, đo đạc, thực hiện và gửi kết quả |
| Quản lý kỹ thuật | Phê duyệt hoặc xác nhận các bước cần thẩm quyền |
| SOP Knowledge Base | Cung cấp hướng dẫn và tiêu chí nghiệm thu |
| Asset System | Cung cấp hồ sơ thiết bị và tài sản |
| Work Order System | Lưu yêu cầu công việc và trạng thái thực hiện |
| BMS hoặc IoT | Cung cấp số đo và trạng thái thiết bị nếu có |

## 3 Mức độ và quy tắc an toàn

| Mức | Ý nghĩa | Cách xử lý |
| --- | --- | --- |
| Level 1 | Có nguy cơ tức thời tới người hoặc tài sản | Chuyển người trực ngay; không chờ đủ thông tin mới chuyển |
| Level 2 | Sự cố đang lan hoặc ảnh hưởng đáng kể | Ưu tiên xử lý, thu thập dữ kiện và theo dõi chặt |
| Level 3 | Sự cố thông thường, chưa có dấu hiệu nguy hiểm | Xử lý theo SOP và quy trình bình thường |

### 3.1 Quy tắc bắt buộc

- Có khói, tia lửa, điện giật hoặc nước gần điện phải nâng lên Level 1.
- Có kính, cánh cửa, tủ hoặc vật liệu có nguy cơ rơi phải chuyển người xử lý ngay.
- Agent không hướng dẫn cư dân mở tủ điện hoặc tự sửa thiết bị nguy hiểm.
- Agent không được tạo số đo hoặc evidence giả.
- Khi dữ liệu chưa đủ, Agent phải nói rõ điều chưa xác minh.
- Các hành động rủi ro chỉ tạo yêu cầu chờ phê duyệt.

## 4 Danh mục vấn đề kỹ thuật

Mã vấn đề được dùng để chọn SOP, tool, mức độ mặc định và bộ test. Điều kiện nguy hiểm luôn được ưu tiên hơn mức mặc định.

### `TECH.ELEC.BREAKER_TRIP` — CB hoặc cầu dao nhảy liên tục

- **Mức:** L2
- **Nâng Level 1 khi:** Khói, tia lửa, điện giật hoặc nước gần điện

### `TECH.ELEC.FIXTURE_FAILURE` — Ổ cắm, công tắc hoặc đèn không hoạt động

- **Mức:** L3
- **Nâng Level 1 khi:** Nóng, cháy xém hoặc tóe lửa

### `TECH.PLUMB.WATER_HEATER` — Máy nước nóng không nóng hoặc rò

- **Mức:** L3
- **Nâng Level 1 khi:** Nguy cơ điện hoặc rò nước lớn

### `TECH.PLUMB.WATER_FILTER_LOW_FLOW` — Máy lọc nước chạy yếu

- **Mức:** L3
- **Nâng Level 1 khi:** Có rò hoặc chất lượng nước bất thường

### `TECH.HVAC.CONDENSATION` — Điều hòa đọng hoặc chảy nước

- **Mức:** L2
- **Nâng Level 1 khi:** Nước gần điện hoặc trần có nguy cơ rơi

### `TECH.PLUMB.CONCEALED_LEAK` — Rò âm tường hoặc thấm trần

- **Mức:** L2
- **Nâng Level 1 khi:** Ngập nhanh hoặc nước gặp điện

### `TECH.PLUMB.SHOWER_SEAL` — Vách phòng tắm hở

- **Mức:** L3
- **Nâng Level 1 khi:** Thấm lan hoặc rò lớn

### `TECH.PLUMB.TOILET_LEAK` — Bồn cầu rỉ nước

- **Mức:** L3
- **Nâng Level 1 khi:** Tràn nước thải

### `TECH.PLUMB.TRAP_ODOR` — Mùi cống hoặc bẫy nước không hiệu quả

- **Mức:** L3
- **Nâng Level 1 khi:** Có dấu hiệu khí nguy hiểm

### `TECH.PLUMB.SUPPLY_DRAIN_JOINT` — Nước yếu, thoát chậm hoặc rò đầu nối

- **Mức:** L3
- **Nâng Level 1 khi:** Tràn hoặc rò liên tục

### `TECH.ARCH.DOOR_WINDOW` — Cửa hoặc cửa sổ lỏng, hở

- **Mức:** L3
- **Nâng Level 1 khi:** Kính hoặc cánh có nguy cơ rơi

### `TECH.ARCH.CABINET_SAG` — Tủ bếp xệ hoặc cánh lệch

- **Mức:** L3
- **Nâng Level 1 khi:** Có nguy cơ rơi

### `TECH.ARCH.CRACK` — Nứt tường hoặc trần

- **Mức:** L3
- **Nâng Level 1 khi:** Võng, rơi vật liệu hoặc nứt nhanh

### `TECH.ARCH.PAINT_MOISTURE` — Sơn bong, vết ố hoặc ẩm mốc

- **Mức:** L3
- **Nâng Level 1 khi:** Nguồn ẩm vẫn tiếp diễn

### `TECH.ARCH.FLOOR_DAMAGE` — Sàn trầy, phồng hoặc bong

- **Mức:** L3
- **Nâng Level 1 khi:** Có nguy cơ vấp ngã

### `TECH.PLUMB.SEWAGE_BACKFLOW` — Nước thải trào ngược

- **Mức:** L2
- **Nâng Level 1 khi:** Lan rộng, gần điện hoặc ảnh hưởng sức khỏe

## 5 Yêu cầu chức năng

### `A2-FR-001` — Nhận sự cố

- **Yêu cầu:** Hệ thống nhận Incident có `incident_id`, `building_id`, mô tả và nguồn gửi.

### `A2-FR-002` — Kiểm tra phạm vi

- **Yêu cầu:** Hệ thống từ chối dữ liệu không thuộc tòa nhà được cấp quyền.

### `A2-FR-003` — Kiểm tra dữ liệu

- **Yêu cầu:** Hệ thống xác định trường còn thiếu trước khi lập kế hoạch.

### `A2-FR-004` — Phân loại

- **Yêu cầu:** Hệ thống gán issue code và mức xử lý cho Incident.

### `A2-FR-005` — Phát hiện nguy hiểm

- **Yêu cầu:** Hệ thống phát hiện trigger Level 1 và chuyển người xử lý.

### `A2-FR-006` — Tra SOP

- **Yêu cầu:** Hệ thống chỉ sử dụng SOP đã được duyệt và còn hiệu lực.

### `A2-FR-007` — Tra tài sản

- **Yêu cầu:** Hệ thống đọc đúng asset theo building và location.

### `A2-FR-008` — Tra lịch sử

- **Yêu cầu:** Hệ thống đọc được lịch sử bảo trì và lỗi lặp.

### `A2-FR-009` — Đề xuất xử lý

- **Yêu cầu:** Hệ thống tạo kế hoạch gồm công việc, mức ưu tiên, chuyên môn và lưu ý an toàn.

### `A2-FR-010` — Work Order

- **Yêu cầu:** Hệ thống chỉ yêu cầu tạo Work Order ở trạng thái nháp hoặc chờ duyệt.

### `A2-FR-011` — Nhận kết quả

- **Yêu cầu:** Hệ thống nhận checklist, số đo, linh kiện và evidence từ kỹ thuật viên.

### `A2-FR-012` — Xác minh

- **Yêu cầu:** Hệ thống trả VERIFIED, NEEDS_EVIDENCE hoặc HUMAN_REVIEW.

### `A2-FR-013` — Hành động rủi ro

- **Yêu cầu:** Hệ thống chỉ tạo request và không thực hiện hành động vật lý.

### `A2-FR-014` — Truy vết

- **Yêu cầu:** Mọi lần gọi tool phải có `trace_id`, `agent_version` và thời điểm.

## 6 Luồng xử lý chung

1. Nhận Incident đã được chuyển cho domain kỹ thuật.
2. Kiểm tra building, vị trí, mô tả và evidence hiện có.
3. Phân loại issue code và mức độ.
4. Nếu có dấu hiệu Level 1, chuyển người trực và dừng các hướng dẫn có thể gây nguy hiểm.
5. Nếu thiếu thông tin, gửi danh sách câu hỏi cần bổ sung qua dịch vụ dùng chung.
6. Tra SOP, asset, outage, sensor hoặc maintenance history phù hợp.
7. Tạo đề xuất xử lý và dữ liệu đầu vào cho Work Order.
8. Yêu cầu Work Order System tạo bản nháp hoặc trạng thái chờ phê duyệt.
9. Nhận kết quả, số đo và evidence từ kỹ thuật viên.
10. Kiểm tra điều kiện hoàn tất và chuyển người có thẩm quyền quyết định đóng hồ sơ.

## 7 Dữ liệu của domain kỹ thuật

### `Technical Incident`

- **Trường tối thiểu:** `incident_id`, `issue_code`, severity, `building_id`, `unit_id`, description, evidence
- **Mục đích:** Hồ sơ sự cố

### `Asset`

- **Trường tối thiểu:** `asset_id`, type, model, location, ownership, warranty, status
- **Mục đích:** Xác định thiết bị hoặc hạng mục

### `SOP`

- **Trường tối thiểu:** `document_id`, version, status, `effective_from`, source
- **Mục đích:** Hướng dẫn và tiêu chí nghiệm thu

### `Measurement`

- **Trường tối thiểu:** metric, value, unit, `measured_at`, `measured_by`, source
- **Mục đích:** Lưu số đo có căn cứ

### `Executor Result`

- **Trường tối thiểu:** `workorder_id`, executor, checklist, measurements, parts, evidence
- **Mục đích:** Kết quả hiện trường

### `Maintenance Event`

- **Trường tối thiểu:** `asset_id`, `incident_id`, `workorder_id`, outcome, `source_refs`
- **Mục đích:** Lịch sử bảo trì

### `Outage`

- **Trường tối thiểu:** `service_type`, scope, status, `started_at`, source
- **Mục đích:** Sự cố hoặc gián đoạn chung

### 7.1 Quy tắc dữ liệu

- Mọi dữ liệu phải gắn `building_id` và nguồn tạo.
- Số đo phải có value, unit, `measured_at` và `measured_by`.
- Evidence phải có source, `captured_at` và integrity reference.
- Không lưu token, secret hoặc credential trong prompt và log.
- Thông tin của căn khác chỉ được truy cập khi có quyền và nhu cầu nghiệp vụ rõ ràng.

## 8 Tool riêng của domain kỹ thuật

Các dịch vụ dùng chung như clarification, approval, handoff, notification, incident và Work Order không được đặc tả chi tiết ở đây. Domain kỹ thuật chỉ xác định lúc nào cần gọi và dữ liệu kỹ thuật phải truyền.

### `sop_kb.retrieve`

- **Mục đích:** Tra SOP kỹ thuật và tiêu chí nghiệm thu
- **Input chính:** `issue_code`, query, `building_id`
- **Output chính:** Danh sách SOP có phiên bản và hiệu lực
- **Ràng buộc:** Không dùng tài liệu hết hiệu lực

### `asset.read`

- **Mục đích:** Đọc hồ sơ tài sản và thiết bị
- **Input chính:** `asset_id` hoặc location, `building_id`
- **Output chính:** Model, vị trí, bảo hành và trạng thái
- **Ràng buộc:** Không đọc tài sản ngoài phạm vi tòa nhà

### `sensor.read`

- **Mục đích:** Đọc dữ liệu BMS hoặc IoT
- **Input chính:** `sensor_id` hoặc `asset_id`, metric, `time_range`
- **Output chính:** Số đo, đơn vị, thời điểm và chất lượng
- **Ràng buộc:** Không kết luận từ dữ liệu quá cũ

### `maintenance_history.read`

- **Mục đích:** Đọc lịch sử bảo trì và lỗi lặp
- **Input chính:** `asset_id`, `time_range`
- **Output chính:** Danh sách sự kiện và lần bảo trì gần nhất
- **Ràng buộc:** Không coi ghi chú cũ là kết luận hiện tại

### `maintenance_history.append`

- **Mục đích:** Ghi kết quả đã xác nhận vào lịch sử
- **Input chính:** `asset_id`, `workorder_id`, kết quả, nguồn
- **Output chính:** Mã sự kiện bảo trì
- **Ràng buộc:** Chỉ ghi sau khi có kết quả được xác nhận

### `technical.get_active_outage`

- **Mục đích:** Kiểm tra sự cố hoặc gián đoạn dịch vụ đang hoạt động
- **Input chính:** `building_id`, `service_type`, `occurred_at`
- **Output chính:** Danh sách outage và phạm vi ảnh hưởng
- **Ràng buộc:** Không tự suy đoán thời gian khôi phục

### `technical.record_measurement`

- **Mục đích:** Ghi số đo kỹ thuật
- **Input chính:** metric, value, unit, `measured_at`, `measured_by`
- **Output chính:** Measurement ID và giá trị chuẩn hóa
- **Ràng buộc:** Agent không được tự tạo số đo

### `technical.submit_executor_result`

- **Mục đích:** Nhận kết quả từ kỹ thuật viên
- **Input chính:** `workorder_id`, executor, checklist, thời gian
- **Output chính:** Result ID và trạng thái kiểm tra
- **Ràng buộc:** Phải xác thực người gửi

### `technical.verify_resolution`

- **Mục đích:** Kiểm tra evidence và điều kiện hoàn tất
- **Input chính:** `incident_id`, `workorder_id`, `result_id`
- **Output chính:** VERIFIED, NEEDS_EVIDENCE hoặc HUMAN_REVIEW
- **Ràng buộc:** Không tự đóng Incident

### `utility_schedule.read`

- **Mục đích:** Đọc lịch cắt điện hoặc nước
- **Input chính:** `building_id`, `utility_type`, `time_range`
- **Output chính:** Lịch đã công bố và trạng thái
- **Ràng buộc:** Không dùng lịch đã hủy hoặc hết hiệu lực

### `utility_isolation.request`

- **Mục đích:** Đề nghị khóa van hoặc ngắt điện
- **Input chính:** `incident_id`, phạm vi, lý do, evidence
- **Output chính:** Yêu cầu chờ phê duyệt
- **Ràng buộc:** Không gửi lệnh trực tiếp tới thiết bị

### `area_restriction.request`

- **Mục đích:** Đề nghị rào chắn hoặc hạn chế khu vực
- **Input chính:** `incident_id`, area, hazard, evidence
- **Output chính:** Yêu cầu chờ phê duyệt
- **Ràng buộc:** Không tự khóa cửa hoặc dừng thiết bị

### `apartment_entry.request`

- **Mục đích:** Xin quyền vào căn hộ vắng chủ
- **Input chính:** `incident_id`, `unit_id`, lý do, lịch sử liên hệ
- **Output chính:** Yêu cầu và danh sách phê duyệt
- **Ràng buộc:** Agent không được nhận mã khóa hoặc credential

### `vendor_dispatch.request`

- **Mục đích:** Đề nghị điều động nhà thầu ngoài
- **Input chính:** `incident_id`, dịch vụ, lý do, mức khẩn
- **Output chính:** Yêu cầu và nhà thầu phù hợp
- **Ràng buộc:** Không cam kết chi phí hoặc tự gọi nhà thầu

## 9 Đặc tả ngắn cho từng nhóm tool

### 9.1 Nhóm tra cứu

Gồm `sop_kb.retrieve`, `asset.read`, `sensor.read`, `maintenance_history.read`, `technical.get_active_outage` và `utility_schedule.read`. Các tool này không thay đổi dữ liệu nguồn.

- Input phải có `building_id` và điều kiện tìm kiếm rõ ràng.
- Output phải có source, version hoặc `updated_at`.
- Dữ liệu sensor phải có đơn vị, chất lượng và thời điểm lấy mẫu.
- Nếu nhiều asset phù hợp, tool phải trả NEEDS_INPUT thay vì tự chọn.

### 9.2 Nhóm ghi nhận kết quả

Gồm `technical.record_measurement`, `technical.submit_executor_result` và `maintenance_history.append`.

- Người hoặc nguồn gửi phải được xác thực.
- Request ghi dữ liệu phải có idempotency key để chống trùng.
- Bản ghi đã xác nhận không sửa trực tiếp; thay đổi phải tạo revision hoặc sự kiện thay thế.
- `maintenance_history.append` chỉ chạy sau khi kết quả đã được xác nhận.

### 9.3 Nhóm xác minh

`technical.verify_resolution` kiểm tra checklist, SOP và evidence. Tool chỉ đưa ra kết luận hỗ trợ quyết định.

- VERIFIED khi đủ điều kiện theo SOP và evidence.
- NEEDS_EVIDENCE khi thiếu ảnh, số đo hoặc checklist bắt buộc.
- HUMAN_REVIEW khi có mâu thuẫn hoặc cần xác nhận chuyên môn.
- Tool không chuyển Incident hoặc Work Order sang CLOSED.

### 9.4 Nhóm yêu cầu rủi ro

Gồm `utility_isolation.request`, `area_restriction.request`, `apartment_entry.request` và `vendor_dispatch.request`.

- Chỉ tạo yêu cầu PENDING_APPROVAL.
- Phải có `incident_id`, lý do, phạm vi và evidence.
- Không được cấp credential điều khiển cho Agent.
- Không có phê duyệt thì không được chuyển thành hành động thực địa.

## 10 Các luồng POC

### 10.1 Cầu dao nhảy liên tục

1. Thu thập vị trí, số lần nhảy, thiết bị liên quan và dấu hiệu nguy hiểm.
2. Nếu có khói, tia lửa, điện giật hoặc nước gần điện thì nâng Level 1 và chuyển người trực.
3. Nếu không có dấu hiệu Level 1, tra SOP, asset và lịch sử liên quan.
4. Tạo đề xuất xử lý và yêu cầu Work Order nháp.
5. Nhận checklist và evidence từ kỹ thuật viên trước khi xác minh.

### 10.2 Điều hòa chảy nước

1. Thu thập asset, vị trí nước, mức lan và ảnh.
2. Nâng Level 1 nếu nước gần điện hoặc trần có nguy cơ rơi.
3. Tra SOP, asset và maintenance history.
4. Tạo yêu cầu xử lý và nhận ảnh trước sau.
5. Chỉ kết luận VERIFIED khi đủ evidence theo SOP.

### 10.3 Rò nước âm tường

1. Xác định căn, khu vực, tốc độ lan và căn có thể bị ảnh hưởng.
2. Kiểm tra incident liên quan, ownership và lịch sử sửa chữa.
3. Nếu cần vào căn khác, chỉ tạo `apartment_entry.request`.
4. Ghi số đo độ ẩm nếu kỹ thuật viên cung cấp.
5. Theo dõi evidence đến khi có đủ căn cứ xác minh.

### 10.4 Nứt tường hoặc trần

1. Thu thập vị trí, kích thước ước lượng, ảnh và thời điểm xuất hiện.
2. Nâng Level 1 nếu có võng, rơi vật liệu hoặc vết nứt phát triển nhanh.
3. Nếu nguy hiểm, tạo `area_restriction.request` và chuyển người có chuyên môn.
4. Số đo chính thức chỉ được ghi từ kỹ thuật viên hoặc thiết bị được xác thực.
5. Có thể tạo `vendor_dispatch.request` khi cần chuyên gia kết cấu.

### 10.5 Nước thải trào ngược

1. Xác định vị trí, mức lan, khu vực ảnh hưởng và dấu hiệu sức khỏe.
2. Kiểm tra outage và các incident tương tự.
3. Nâng Level 1 khi lan rộng, gần điện hoặc ảnh hưởng sức khỏe.
4. Tạo yêu cầu hạn chế khu vực khi cần.
5. Kết quả xử lý phải có checklist vệ sinh và evidence phù hợp.

## 11 Xử lý lỗi

| Tình huống | Hành vi của hệ thống |
| --- | --- |
| Thiếu thông tin | Trả danh sách trường thiếu và yêu cầu bổ sung |
| Không tìm thấy asset | Không tự chọn; yêu cầu vị trí hoặc model rõ hơn |
| SOP không tồn tại | Dừng hướng dẫn chi tiết và chuyển người có chuyên môn |
| SOP hết hiệu lực | Không sử dụng; tìm phiên bản hiện hành hoặc chuyển người |
| Sensor quá cũ | Đánh dấu stale và không dùng để kết luận an toàn |
| Tool timeout | Retry theo cấu hình; write tool phải đối soát trước khi retry |
| Không có quyền | Từ chối, ghi audit và không mở rộng scope |
| Thiếu evidence | Trả NEEDS_EVIDENCE với danh sách nội dung cần bổ sung |
| Dữ liệu mâu thuẫn | Trả HUMAN_REVIEW và nêu các nguồn mâu thuẫn |

## 12 Kiểm thử và nghiệm thu

### 12.1 Nhóm kiểm thử

- Happy path cho từng vấn đề kỹ thuật.
- Thiếu thông tin bắt buộc.
- Có dấu hiệu Level 1.
- Asset không tồn tại hoặc thuộc tòa nhà khác.
- SOP hết hiệu lực.
- Sensor stale hoặc sai đơn vị.
- Tool timeout và retry.
- Thiếu evidence sau xử lý.
- Agent cố thực hiện hành động vật lý hoặc vượt quyền.

### 12.2 Điều kiện nghiệm thu

- Phân loại đúng 16 issue code trong bộ dữ liệu chuẩn.
- Không bỏ sót trigger Level 1 bắt buộc.
- Mọi kết luận có liên kết tới SOP, dữ liệu hoặc evidence.
- Không truy cập dữ liệu ngoài building scope.
- Không tạo số đo hoặc evidence giả.
- Các hành động rủi ro chỉ tạo request chờ phê duyệt.
- `technical.verify_resolution` không tự đóng hồ sơ.
- Năm luồng POC chạy được từ đầu đến kết quả kiểm tra cuối.

## 13 Phân chia công việc cho nhóm

| Nhóm việc | Nội dung | Kết quả |
| --- | --- | --- |
| Nghiệp vụ | Issue code, severity, SOP và năm luồng POC | Dataset và expected result |
| Dữ liệu | Asset, measurement, maintenance và evidence model | Schema và seed data |
| Tool đọc | SOP, asset, sensor, history, outage và schedule | Adapter và mock |
| Tool ghi | Measurement, executor result và maintenance append | API có chống trùng |
| An toàn và test | Verify, high-risk request, lỗi và evaluation cases | Policy tests và acceptance suite |

## 14 Các quyết định cần chốt

- Định nghĩa thời gian phản hồi mong muốn cho Level 1, Level 2 và Level 3.
- Hệ thống asset và Work Order thật sẽ dùng trong POC hay dùng mock.
- Các loại sensor và metric nào được đưa vào demo.
- Ai phê duyệt isolation, restriction, apartment entry và vendor dispatch.
- Ai có quyền đóng Incident sau khi A2 trả VERIFIED.
- Năm use case demo cuối cùng và dữ liệu mẫu tương ứng.

## 15 Definition of Done

- Có schema cho Incident, Asset, Measurement, Executor Result và Maintenance Event.
- Mỗi tool kỹ thuật có input, output, error và quyền rõ ràng.
- Có mock hoặc adapter chạy được cho các tool thuộc POC.
- Có test cho happy path, thiếu dữ liệu, lỗi tool và vượt quyền.
- Năm luồng POC chạy được với trace và evidence đầy đủ.
- Domain Owner xác nhận cách phân loại, mức độ và đầu ra nghiệp vụ.
