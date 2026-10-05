# Dữ liệu cần để chạy 14 tool A2

Contract input/output/quyền nằm tại [`../tools.md`](../tools.md). Bảng này là checklist nguồn dữ liệu. `mock` nghĩa là fixture do dự án tạo để kiểm thử; không là dữ liệu vận hành thật.

| Tool | Nguồn cần có | Dữ liệu hiện có trong thư mục | Điều kiện trước khi chạy thật |
| --- | --- | --- | --- |
| `sop_kb.retrieve` | SOP published, document version, issue code, hiệu lực, ACL/scope, acceptance criteria | 16 profile `draft` ở `rag/mock/PROCEDURE_PROFILES.jsonl` và 16 Markdown giả lập; **không eligible** cho tool thật | Xin SOP BQL/manual đúng model, review/publish, ingest có citation/version |
| `asset.read` | Asset ID/model/location/ownership/warranty/status theo building | 5 asset giả lập có ID/model/location trong `rag/mock/POC_LIFECYCLE.jsonl` | Export CMMS/asset thật và mapping building/scope |
| `sensor.read` | Sensor ID, metric/unit, value, observed_at, quality, max age | 3 bản ghi giả lập fresh/stale/bad ở `rag/mock/TOOL_DATA_FIXTURES.jsonl` | Adapter BMS/IoT hoặc mock có timestamp/quality rõ |
| `maintenance_history.read` | Asset events, work order, outcome, thời điểm và source refs | 3 event giả lập cho AC, gồm scheduled, pending và correction draft | Export lịch sử ẩn danh đúng asset/building |
| `technical.get_active_outage` | Service interruptions, utility, scope và thời gian hiệu lực | 4 interruption giả lập: proposed/notified/cancelled/active khác building | Nguồn outage từ BQL hoặc bảng nghiệp vụ đã được cập nhật |
| `utility_schedule.read` | Lịch gián đoạn đã công bố, hủy/đổi lịch, phạm vi | Một lịch `notified` tương lai, một `cancelled` và một `proposed` phải loại | Thông báo chính thức có version/effective/scope; không suy ETA |
| `maintenance_history.append` | Verified executor result, asset, outcome, source refs, idempotency key | Event pending và correction draft để test **không append/không overwrite** trước xác minh | Adapter lịch sử + quyền ghi + revision và audit |
| `technical.record_measurement` | Value/unit/metric, thiết bị, measured_at/by, work order/evidence | Các loại metric cần thu | Người/thiết bị đo xác thực, unit allowlist và chống trùng |
| `technical.submit_executor_result` | Assignment, checklist, parts, measurements, evidence, start/end | 5 work order/assignment giả lập, 1 executor result mô phỏng đã submit và 4 ca chưa hoàn tất trong `rag/mock/POC_LIFECYCLE.jsonl` | Kỹ thuật viên có quyền, evidence ready và result adapter |
| `technical.verify_resolution` | SOP acceptance criteria, result, checklist, evidence, conflict | 16 bộ acceptance criteria mock; 5 expected result/biến thể POC, đều không phải nghiệm thu thật | Source của mọi tiêu chí; tool không đóng ticket |
| `utility_isolation.request` | Ticket/order/evidence/scope, khoảng thời gian, approval route | Hazard cases điện/nước và một interruption `proposed` không được đọc như outage thật | Approval kind đúng; nước dùng work approval + interruption, điện cần adapter riêng |
| `area_restriction.request` | Hazard, phạm vi khu vực, evidence, approval route | Hai request pending cho crack và sewage, `physical_action_done=false` | Shared approval adapter; không có side effect vật lý trước duyệt |
| `apartment_entry.request` | Incident, unit, lý do, lịch sử liên hệ, quyền/cơ chế duyệt | Một request pending cho rò âm tường, chưa có quyền vào căn bên cạnh | Xác minh unit và approval; không nhận mã khóa/credential |
| `vendor_dispatch.request` | Chuyên môn, urgency, scope, candidate vendor đủ điều kiện | Crack POC và một vendor candidate giả lập chưa booking/chưa có giá | Adapter nhà thầu/approval; không booking hoặc cam kết giá |

Không có dòng nào được tự động hoàn thành chỉ vì source public hoặc file fixture tồn tại. “Đã gọi tool” và “đã thực hiện ngoài hiện trường” là hai trạng thái khác nhau; kết quả `PENDING_APPROVAL` không phải hành động đã thi hành.
