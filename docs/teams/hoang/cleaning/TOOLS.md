# Tool vệ sinh đối ứng bộ kỹ thuật

Ngày 06/10/2026. Nhánh `dev_TeamHoang_PhanDung`. Chỉ thêm module vệ sinh; không sửa phần hiện hữu.

## Nguyên tắc

Agent vệ sinh thực hiện cùng nghiệp vụ specialist kỹ thuật, đổi đội phụ trách sang vệ sinh. Các đối ứng gọi trực tiếp `source.run` của tool kỹ thuật hiện có qua adapter dữ liệu vệ sinh; không viết lại nghiệp vụ hoặc thêm policy riêng.

Giữ nguyên input/output schema, capability, effect, timeout, approval, idempotency và các kiểm tra nghiệp vụ. Ngoại lệ thuộc đối tượng: SOP nhận `CLEAN.*`; work order/assignment chỉ lấy trong danh mục vệ sinh; specialty nhà thầu phải thuộc vệ sinh theo mapping tin cậy của deployment. Gọi trực tiếp host kỹ thuật hiện có qua wrapper cục bộ, namespace riêng `cleaning.*`; không sửa hoặc sao chép host gốc.

## Đối chiếu đủ 14 tool

| Tool kỹ thuật hiện có | Tool vệ sinh | Implementation |
|---|---|---|
| `technical.get_active_outage` | `cleaning.get_active_outage` | Dùng nguyên tool gốc |
| `utility_schedule.read` | `cleaning.read_utility_schedule` | Dùng nguyên tool gốc |
| `sop_kb.retrieve` | `cleaning.retrieve_sop` | Dùng nguyên tool gốc, nhận mã CLEAN và SOP vệ sinh |
| `asset.read` | `cleaning.read_asset` | Dùng nguyên tool gốc |
| `sensor.read` | `cleaning.read_sensor` | Dùng nguyên tool gốc |
| `maintenance_history.read` | `cleaning.read_maintenance_history` | Dùng nguyên tool gốc |
| `technical.record_measurement` | `cleaning.record_measurement` | Dùng nguyên tool gốc, assignment vệ sinh |
| `technical.submit_executor_result` | `cleaning.submit_executor_result` | Dùng nguyên tool gốc, assignment vệ sinh |
| `technical.verify_resolution` | `cleaning.verify_resolution` | Dùng nguyên tool gốc, work/SOP vệ sinh |
| `maintenance_history.append` | `cleaning.append_maintenance_history` | Dùng nguyên tool gốc, work/SOP vệ sinh |
| `utility_isolation.request` | `cleaning.request_utility_isolation` | Dùng nguyên tool gốc |
| `area_restriction.request` | `cleaning.request_area_restriction` | Dùng nguyên tool gốc |
| `apartment_entry.request` | `cleaning.request_apartment_entry` | Dùng nguyên tool gốc |
| `vendor_dispatch.request` | `cleaning.request_vendor_dispatch` | Dùng nguyên tool gốc, specialty vệ sinh |

Mapping và delegation ở `server/src/cleaning-tools/tools/technical-counterparts.ts`. Adapter scope ở `adapters/technical-dependencies.ts`. Các tool dùng chung như tiện ích/tài sản/cảm biến vẫn đọc dữ liệu hiện có theo scope, không đổi dữ liệu kỹ thuật thành vệ sinh.

## Gọi đội nội bộ và theo dõi công việc

Catalogue có thêm năm entry bọc nghiệp vụ V3 **đã có**, vì catalogue 14 tool kỹ thuật không chứa API phân công/cập nhật trạng thái nội bộ:

| Tool vệ sinh | Nghiệp vụ hiện có |
|---|---|
| `cleaning.list_available_staff` | `v3_operations.available_staff` |
| `cleaning.read_work_order` | V3 ticket/work detail/timeline |
| `cleaning.create_work_order` | `v3_mutations.create_work_order` |
| `cleaning.dispatch_staff` | `v3_mutations.create_assignment` |
| `cleaning.update_work_status` | `v3_mutations.change_work_order_status` |

Tổng cộng 19 entry: 14 đối ứng trực tiếp và 5 entry điều phối nội bộ. Đây là các nghiệp vụ đã có của platform, không tạo hệ thống phân công/trạng thái mới. Nhân viên chỉ được chọn theo category/specialty vệ sinh, đơn vị, ca và tải của API hiện có. Dispatch tạo offer; phản hồi nhận/từ chối vẫn thuộc luồng nhân viên.

Các entry V3 giữ `work_order_id`, `expected_version`, paging `limit/offset` theo contract adapter. `update_work_status` nhận building/work/assignment, version, status, note và idempotency key; không nhận hoặc bắt buộc `result_id`/`sop_document_ids` để complete. Backend giữ quyền, version, consent, transition và evidence. Không tự đặt thêm tiêu chí VERIFIED hoặc cấm tạo công việc cùng mô tả ngoài luật backend.

## Contract và semantics giữ nguyên

- Result dùng đúng contract kỹ thuật: `workorder_id`, `assignment_id`, checklist, measurement/evidence IDs, parts, diagnosis, repair_notes, timestamps, idempotency key. Các trường tùy chọn vẫn tùy chọn; không thêm expected_version/observations/notes hoặc giới hạn riêng.
- Verification dùng `building_id`, `incident_id`, `workorder_id`, `result_id`, SOP IDs tùy chọn. Thiếu SOP trả đề nghị HUMAN_REVIEW theo tool gốc; verify không ghi trạng thái/QC/đóng ticket.
- Submission chỉ ghi qua `ExecutorResultStore` hiện có, không complete. Maintenance append vẫn kiểm verification theo tool gốc, không bỏ kiểm này vì nó vốn có ở kỹ thuật.
- Measurement giữ cả enum nguồn và `measured_by.kind=technician|device` của contract gốc; trong module vệ sinh, user của assignment là nhân viên vệ sinh. Không thêm metric hoặc enum mới.
- Request vẫn PENDING_APPROVAL; không tự duyệt, gọi điện, đặt nhà thầu hoặc trả tiền.

Catalogue/JSON schemas là nguồn contract cho tích hợp. Host không giả actor nhân viên hoặc admin. Không cấp grant, sửa agent/groupchat, mount gateway hoặc tạo bridge backend trong thay đổi này. Dữ liệu/SOP/mapping specialty và các port phải do deployment cung cấp như bên kỹ thuật.
