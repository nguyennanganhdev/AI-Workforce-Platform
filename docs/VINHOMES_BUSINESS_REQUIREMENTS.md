# Yêu cầu nghiệp vụ Vinhomes

Gộp ngày 04/10/2026 từ ghi chú `my-docs/nghiep_vu_moi.md`. Đây là yêu cầu sản phẩm và các đề xuất ban đầu, **không phải danh sách chức năng đã hoàn thành**. Trạng thái triển khai đọc ở [báo cáo repo](teams/chien/REPO_RESEARCH_2026-10-04/README.md); phần cần nối tiếp ở [checklist tích hợp](teams/chien/SYSTEM_FLOW_AND_MAINTENANCE_2026-10-04/INTEGRATION_CHECKLIST.md).

## Tài khoản và giao diện

- Cư dân đăng ký họ tên, số điện thoại, mật khẩu và căn hộ. Tài khoản BQL/nhân viên do admin cấp; yêu cầu phê duyệt tài khoản trước khi sử dụng cần được kiểm tra theo luồng đăng nhập hiện hành.
- Backend xác định vai trò và phạm vi; UI điều hướng về trang tương ứng. Admin quản lý việc kích hoạt, tạm khóa và xóa tài khoản theo chính sách.
- Cư dân có nhiều hội thoại, gửi văn bản/ảnh, xem thẻ ticket, lịch sử tiến độ và thông báo. Một tin nhắn có thể chứa nhiều sự cố: Reception cần hỏi rõ trước khi tách ticket.
- BQL xem ticket, phương án, phê duyệt và phòng làm việc; có thể mention agent và yêu cầu báo cáo. Nhân viên xem việc được giao, xác nhận nhận việc và cập nhật kết quả.

## Reception và điều phối

- Reception trả lời FAQ, nội quy và dịch vụ bằng tri thức được phép truy cập; hỏi lại khi thiếu thông tin, không tự suy đoán.
- Xác định cư dân, thông tin liên hệ, căn hộ, tòa và domain để chuyển đúng BQL/phòng. Một người có nhiều ticket, một ticket có nhiều event; cập nhật phải gắn đúng ticket.
- Các nhu cầu tool ban đầu: `load_resident_context`, `resolve_management_destination`, `create_ticket_draft`, `answer_or_escalate`. Đây là tên đề xuất; contract thực tế đọc ở [schema Reception–Supervisor](SCHEMA_RECEPTION_SUPERVISOR_V1.md).
- Reception thông báo khi đã tiếp nhận, khi cần cư dân duyệt phương án và khi có kết quả. Chờ event nghiệp vụ để tiếp tục hội thoại; lưu trạng thái chờ bền vững.
- Supervisor phân rã task, giao agent chuyên môn, theo dõi Task Board và tổng hợp kết quả. Các agent có context riêng và có thể trao đổi trực tiếp/broadcast.
- Mention `@agent` cần Context Builder lấy đúng lịch sử phòng, ticket/task và kết quả liên quan; agent trả lời vào cùng phòng. Framework không thay việc chọn context và kiểm quyền của backend.

## Luồng có người phê duyệt

Luồng mong muốn: Reception tạo ticket → Supervisor đề xuất phương án → BQL duyệt → cư dân xác nhận phương án → giao việc → nhân viên xác nhận nhận việc → ghi ảnh trước/sau và kết quả → nghiệm thu theo quyền → Reception báo cư dân → cư dân xác nhận hoặc yêu cầu xử lý lại.

Các thao tác nguy hiểm, phê duyệt và trạng thái chính thức do backend/người có quyền kiểm soát. Không dùng nội dung chat làm trạng thái nghiệp vụ chính thức. Thứ tự và điều kiện cụ thể phải đối chiếu contract/API hiện hành.

## Các domain chuyên môn

### Kỹ thuật

- Sự cố đơn giản: hướng dẫn cư dân tự xử lý; nếu không giải quyết được thì chuyển điều phối.
- Sự cố cần đến hiện trường: chọn nhân viên đúng chuyên môn, ca và phạm vi. Không có người rảnh thì đưa vào hàng chờ và thông báo cư dân.
- Điện/cơ sở vật chất: nhân viên xác nhận hiện trường, thực hiện theo phương án đã duyệt, gửi bằng chứng và kết quả.
- Nước: nếu cần khóa van khu vực thì BQL duyệt, thông báo cư dân, thực hiện khóa/mở lại nước, rồi kiểm tra điều kiện hoàn tất.
- Agent tra SOP, tài sản, sensor, lịch sử bảo trì, outage; ghi số đo/kết quả và đề nghị các quyền đặc biệt. Tra cứu [catalog tool](teams/quang/tools.md) và [Technical API](teams/quang/TECHNICAL_API.md).

### An ninh

- Thiếu vị trí/mức độ thì hỏi cư dân qua Reception. Nội quy/đăng ký khách có thể trả lời bằng tri thức được phép.
- P2/P3: kiểm tra camera gần vị trí và trạng thái online/offline, đề xuất điều bảo vệ có phạm vi phù hợp; nếu không rảnh thì xếp hàng chờ, báo cư dân và chuyển trưởng ca khi quá hạn.
- Nếu tình hình nghiêm trọng hơn thì nâng mức độ; nếu không cần điều động nữa thì đề xuất hủy có lý do và phê duyệt.
- P0/P1: lấy quy trình và danh sách liên hệ khẩn cấp, điều người theo chính sách, theo dõi xác nhận đã nhận cảnh báo. Gửi lỗi/không ai xác nhận thì chuyển người tiếp theo; không coi sự cố đã hoàn tất.
- Bảo vệ ghi diễn biến/bằng chứng; BQL xác nhận kết quả theo quy trình. Mức P0–P3 trong yêu cầu phải ánh xạ sang enum API thực tế.

### Vệ sinh và kế toán

- Vệ sinh: điều phối nhân viên, ghi ảnh trước/sau và kiểm tra kết quả.
- Kế toán: xác định trách nhiệm chi trả, dự toán, tiền thực tế và quản lý giao dịch. Các nội dung này là phạm vi đề xuất, cần contract và dữ liệu nguồn trước khi triển khai.

### Báo cáo

BQL chọn kỳ, tòa/phân khu, nhóm sự cố và nhân viên trong phạm vi được xem. Báo cáo phải có bản ghi nguồn để giải thích số liệu, phân trang và kiểm quyền khi xuất file.

| Tool đề xuất | Kết quả mong muốn |
|---|---|
| `get_report_filter_options` | Bộ lọc có ID/tên hợp lệ, đúng phạm vi |
| `get_employee_performance_summary` | Việc giao/hoàn thành, đúng hạn, thời gian xử lý, làm lại, điểm và lượt đánh giá |
| `get_employee_feedback_details` | Điểm, phản hồi, ngày và tham chiếu ticket/công việc |
| `get_repair_revenue_summary` | Tiền tính phí/thực thu/còn phải thu; tiền công/vật tư nếu có dữ liệu |
| `get_incident_frequency_summary` | Số ticket, tỷ trọng, xu hướng, phân bố theo tòa/loại sự cố |
| `get_report_supporting_records` | Ticket, công việc hoặc giao dịch đứng sau chỉ số |
| `create_report_export` | `report_id`, `job_id`, trạng thái; định dạng thực tế DOCX/PDF/XLSX |
| `get_report_export_status` | Trạng thái/lỗi và đường tải có kiểm quyền |

Tên tool trong bảng là yêu cầu ban đầu, không chứng minh đã có endpoint tương ứng.

## Tạo agent và duyệt tri thức

- BQL mô tả agent chuyên môn; Factory tạo spec, system prompt, bộ tool được cấp và cấu hình kho tri thức.
- Evaluation tạo test case (ghi chú ban đầu đề xuất khoảng 6), chạy sandbox và đánh giá bằng quy tắc/code cùng LLM judge. Factory sửa trong số vòng giới hạn; model judge khác provider là đề xuất, chưa phải tiêu chí đã chốt.
- Agent đạt kiểm tra được gửi admin/người có quyền review trước publish. Cách trả sửa/từ chối phải được định nghĩa; ghi chú gốc còn để mở.
- Cách chia vector DB theo agent hay domain cũng chưa được chốt trong ghi chú gốc; đối chiếu [RAG map](teams/chien/RAG_DATABASE_MAP_2026-10-04/README.md).
- Nội dung học từ xử lý sự cố phải qua review trước khi đưa vào long-term memory/tri thức dùng lại.

## Ảnh trong hội thoại

Ảnh cần được lưu ngay khi gửi, trước cả khi Reception hỏi bổ sung, để không mất tham chiếu khi tiếp tục hoặc khởi động lại.

| API/tool đề xuất | Trách nhiệm |
|---|---|
| `initiate_image_upload` | Kiểm quyền, loại/kích thước; tạo `file_id` và URL upload S3/MinIO |
| `complete_image_upload` | Xác minh object, kích thước/checksum; đánh dấu sẵn sàng |
| `get_conversation_images` | Khôi phục ảnh gắn với message/hội thoại |
| `attach_images_to_ticket` | Kiểm quyền/trạng thái và liên kết ảnh vào ticket; retry không tạo trùng |
| `get_image_read_access` | Cấp quyền đọc tạm thời cho UI/runtime/model |

Đây là chức năng mong muốn; tên endpoint thực tế và storage hiện tại có thể khác. Đọc [Backend V3](../services/vinhomes-api/README.md) và checklist tích hợp trước khi nối.
