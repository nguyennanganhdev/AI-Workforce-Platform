# Năm luồng POC có dữ liệu mẫu cần chuẩn bị

Đây là fixture thiết kế, không phải nhật ký vận hành. `SYN-*` là ID giả lập; thời gian/số đo/ảnh bên dưới chỉ là loại bằng chứng phải cung cấp. Mọi SOP giả lập dùng trong test phải có `fixture_only=true`, scope và version. Không publish cho cư dân.

## POC 1 — CB nhảy lặp

**Intake:** ticket `SYN-T-001`, căn giả lập trong building `SYN-B-01`, `TECH.ELEC.BREAKER_TRIP`; mô tả ba lần nhảy, chưa rõ khói/tia lửa/nước gần điện. Cần hỏi tất cả tín hiệu nguy hiểm trước khi gợi ý xử lý. `source_run_id` và actor lấy từ backend.

**Dữ liệu giả lập:** `asset` gồm panel/CB nhánh (model và location rõ), event bảo trì trước đó hoặc `events: []`, outage của building (có/không theo dữ liệu mô phỏng), SOP điện version test. Nhánh hazard có `burning_smell=true` để chứng minh emergency floor và chuyển người. Nhánh thường chỉ tiếp tục sau khi tín hiệu khẩn được xác minh là `false`.

**Luồng:** assessment append-only → policy V3 chọn theo domain/scope → decision applied → work order draft → assignment hợp lệ → kỹ thuật viên ghi checklist và measurement (nếu yêu cầu) → evidence trước/sau → `technical.verify_resolution`.

**Expected:** hazard không chờ ảnh và không bảo cư dân đóng CB; thiếu ảnh/checklist trả `NEEDS_EVIDENCE`; kỹ thuật viên báo lỗi dây nhưng source mâu thuẫn trả `HUMAN_REVIEW`; `VERIFIED` không đóng ticket.

## POC 2 — Điều hòa chảy nước

**Intake:** `SYN-T-002`, `TECH.HVAC.CONDENSATION`, nước gần dàn lạnh; hỏi trần/điện/căn dưới. Asset cần model dàn lạnh, ngày bảo trì, đường nước ngưng liên quan. Tham khảo DK-01 nhưng chỉ dùng manual đúng model làm SOP test.

**Dữ liệu giả lập:** ảnh trước có `captured_at`, file/object ID và hash; work order kiểm tra đường thoát; measurement `drain_flow` có value, `L/min`, người đo, thời gian và nguồn thiết bị; ảnh sau và checklist thử tải. Không tự dựng measurement từ lời model.

**Expected:** nếu `water_near_electricity=true`, chuyển người ngay; nếu ảnh chưa scan/withdrawn không dùng làm evidence; nếu đủ SOP/checklist/ảnh sau và không còn rò trong phép thử thì `VERIFIED` là khuyến nghị.

## POC 3 — Rò nước âm tường/thấm trần

**Intake:** `SYN-T-003`, `TECH.PLUMB.CONCEALED_LEAK`, vệt ố lan, nguồn chưa biết. Cần hai timeline quan sát từ cư dân và đo của kỹ thuật viên; fact “căn trên gây rò” là chưa xác minh.

**Dữ liệu giả lập:** ticket liên quan trong cùng scope, evidence từ hai căn chỉ khi quyền đọc được xác minh, source hash, measurement độ ẩm với vị trí/đơn vị, lịch sử sửa. `apartment_entry.request` trả `PENDING_APPROVAL`, không tạo trạng thái đã vào căn.

**Expected:** nguồn mâu thuẫn cần `HUMAN_REVIEW`; dữ liệu từ căn khác bị từ chối nếu không có scope; retry request cùng key không tạo thêm request; quyền vào căn bị thu hồi thì không tiếp tục.

## POC 4 — Nứt tường/trần

**Intake:** `SYN-T-004`, `TECH.ARCH.CRACK`, ảnh có mốc kích thước và thời gian. Tách số cư dân ước lượng khỏi số kỹ thuật viên đo. Hỏi trần võng, vật liệu rơi, tốc độ phát triển.

**Dữ liệu giả lập:** hai ảnh ở hai thời điểm với metadata; measurement chiều rộng do kỹ thuật viên ký; đánh giá chuyên gia nếu cần; SOP/tiêu chí nghiệm thu của cấu kiện đúng scope.

**Expected:** vật liệu rơi hoặc phát triển nhanh chuyển người; `area_restriction.request` và `vendor_dispatch.request` luôn pending approval; ảnh không đủ để kết luận an toàn kết cấu; thiếu đánh giá chuyên môn trả `HUMAN_REVIEW`.

## POC 5 — Nước thải trào ngược

**Intake:** `SYN-T-005`, `TECH.PLUMB.SEWAGE_BACKFLOW`, vị trí và mức lan, ảnh hưởng căn khác, nước gần điện và có người tiếp xúc hay không. Nước thải không được xử lý như rò nước sạch.

**Dữ liệu giả lập:** sự cố cùng building/outage, evidence trước, công việc xử lý nguồn tắc, checklist vệ sinh/khử nhiễm do người có chuyên môn thực hiện, ảnh sau, xác nhận không còn trào trong phép thử.

**Expected:** lan rộng/điện/phơi nhiễm chuyển người; `area_restriction.request` chỉ pending approval; thiếu checklist vệ sinh trả `NEEDS_EVIDENCE` dù đường thoát đã thông; không tuyên bố khu vực an toàn chỉ từ một ảnh.

## Bộ biến thể bắt buộc cho cả năm luồng

| Biến thể | Kỳ vọng |
| --- | --- |
| Thiếu building hoặc ownership | `NEEDS_INPUT` hoặc `FORBIDDEN` theo bước xác thực; không đoán từ tên tòa |
| Ảnh chưa scan, sai ticket hoặc withdrawn | Không được gắn làm evidence được chấp nhận |
| SOP draft/hết hạn/khác tenant | Không được retrieval hoặc dùng để `VERIFIED` |
| Sensor stale/bad quality/sai unit | Chỉ hiển thị kèm freshness; không dùng làm kết luận an toàn |
| Cùng idempotency key, payload giống/khác | Cùng kết quả / `CONFLICT` tương ứng |
| Assignment khác work order | Từ chối submit executor result |
| Revoked grant giữa run | Tool/read/download tiếp theo bị từ chối |
| Hai nguồn trái nhau | `HUMAN_REVIEW`, giữ provenance từng nguồn |
| Tool timeout sau write | Đối soát operation theo key trước retry |
| Không có policy triage/SLA | Mở review/escalation; không bịa priority hoặc deadline |
