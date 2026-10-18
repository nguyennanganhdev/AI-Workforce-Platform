# Hoàn thiện domain và thu gọn MCP cho platform — 13/10/2026

## Phạm vi đã chốt với chủ dự án

- Làm tại dự án chính trên `dev_Vinhome`, không tạo worktree.
- Ignore phần `platform_VP` chưa tracked; không untrack hoặc sửa source platform đã tracked. Giữ các thay đổi platform của người khác ngoài commit domain.
- Triển khai onboarding cư dân/staff, phân trang account, khôi phục mật khẩu, mobile, Docker/VPS và MCP.
- **Không test Agent, không gọi model, không chạy hội thoại AI hay workflow leader thật.** Cấu hình provider giữ nguyên để chủ dự án tự cấu hình/test sau.
- Không can thiệp account cư dân đã được nêu trong audit. Test bằng account mới trên dữ liệu riêng.
- Khôi phục mật khẩu: hoàn thiện API/UI và test bằng hộp thư giả; SMTP thật cấu hình sau, không gửi email thật trong đợt này.
- Platform được thực thi nghiệp vụ trong ticket đã bàn giao, tuân thủ phân quyền và các bước duyệt hiện có.

## 1. Ranh giới domain và platform

Domain sở hữu identity, membership, quan hệ cư trú và bước tiếp nhận. Reception/ứng dụng cư dân lấy thông tin từ phiên đã xác thực, lập ticket và bàn giao ticket đủ ngữ cảnh. Platform điều phối xử lý ticket đó; không tạo lại ticket, không chọn lại cư dân/căn hộ và không có quyền duyệt thay cư dân.

Tại baseline, `/mcp` cung cấp 23 tool; **không có tool tạo ticket** trong danh mục này. Vấn đề là catalog và lời dặn leader mở rộng sang xác định cư dân/căn hộ, khách/thẻ/booking và dịch vụ không thuộc điều phối ticket. Tool tạo ticket của Reception là interface nội bộ khác và không được đưa sang `/mcp`.

### Catalog platform sau maintain: 7 tool

| Tool | Vai trò | Điều kiện |
|---|---|---|
| `vh_ticket_get` | Đọc trạng thái mới nhất, work order, báo giá, ảnh và kết quả | Ticket đã bàn giao trong tenant được cấu hình; dùng để theo dõi thay đổi, không xác định lại identity |
| `vh_knowledge_search` | Tra tài liệu cần cho xử lý ticket | Scope suy từ ticket; không chấp nhận cư dân/căn hộ do platform tự chọn |
| `vh_staff_available` | Tìm nhân viên phù hợp | Chuyên môn, ca làm, đơn vị và năng lực theo nghiệp vụ domain |
| `vh_work_order_dispatch` | Tạo/giao work order của ticket | Không phải tạo ticket; các giới hạn chuyên môn, phương án và quyền nghiệp vụ vẫn áp dụng |
| `vh_work_order_reschedule` | Đổi lịch công việc chưa bắt đầu | Giờ hẹn hợp lệ và trạng thái cho phép |
| `vh_ticket_cancel` | Hủy theo yêu cầu, khi còn được phép | Không hủy việc đã đến nơi/đang xử lý để bỏ qua quy trình |
| `vh_ticket_add_note` | Ghi bổ sung thông tin cho xử lý | Không tạo ticket mới, không thay quyết định báo giá/đóng việc |

Loại khỏi public `/mcp`: `vh_resident_context`, `vh_home_rules`, `vh_debit_notes`, `vh_announcements`, `vh_visitor_list`, `vh_cards`, `vh_amenities`, `vh_amenity_availability`, `vh_service_requests`, `vh_construction`, `vh_my_requests`, `vh_visitor_cancel`, `vh_card_report_lost`, `vh_amenity_book`, `vh_amenity_cancel`, `vh_visitor_register`.

Không xóa chức năng cư dân/Reception tương ứng khỏi ứng dụng. Các hàm backend cũ có thể còn tồn tại để giữ dữ liệu/hành vi tương thích; việc không đăng ký vào MCP mới là ranh giới public.

### Gói bàn giao và quyền

- Bàn giao gồm `ticket_id`, nội dung yêu cầu, tên cư dân/quan hệ cư trú, căn/tòa/phân khu, loại yêu cầu, ưu tiên, mức khẩn cấp, số ảnh và giờ tạo. Không bổ sung số điện thoại hoặc credential vào gói.
- Platform sao chép đúng `ticket_id`. Các tool suy scope từ ticket phía server; không nhận tùy ý `user_id`/`unit_id` để mở rộng phạm vi.
- Bearer hiện tại thuộc integration/tenant đã cấu hình, không phải token riêng cho từng workflow. Server kiểm tra ticket đã có link bàn giao pending/open. Không tuyên bố đã có cơ chế khóa token vào duy nhất một workflow.
- Lệnh ghi giữ `client_reference`, idempotency và transaction. Dùng lại reference cho thao tác khác bị từ chối.
- Báo giá và xác nhận hoàn thành vẫn do chính cư dân quyết định bằng phiên cư dân. Platform không có tool duyệt thay, tự QC hay tự đóng ticket thay xác nhận.
- Catalog server, declaration, tài liệu và cấu hình handoff phải khớp. Khi platform được nối, bên nhận cần refresh catalog/grants và loại grant cũ; domain từ chối tool đã loại dù bên nhận còn cache.

## 2. Thứ tự và tiêu chí thực hiện

| Mốc | Thay đổi | Kiểm tra bắt buộc |
|---|---|---|
| M1 | Duyệt cư dân + căn hộ, quan hệ và xác minh | Pending → duyệt → phiên cũ hết hiệu lực → đăng nhập lại → đúng căn hộ; rollback nếu căn sai; retry không trùng |
| M2 | Staff có hồ sơ, đơn vị, chuyên môn và ca | Staff mới vào catalog đúng scope và nhận việc; mã trùng/ca chồng lấn bị từ chối; khóa account giữ lịch sử |
| M3 | Account phân trang/tìm kiếm server | Fixture >200 account; tìm được trang cuối, tổng/bộ lọc đúng, không lẫn tenant |
| M4 | Khôi phục mật khẩu + UI trạng thái | Hộp thư giả nhận link; token hash, 15 phút, một lần; password/session cũ bị vô hiệu; thiếu SMTP báo chưa cấu hình |
| M5 | MCP 7 tool và hợp đồng bàn giao | Discovery đúng catalog; tool bị loại không gọi được; sai token và sai ticket bị từ chối; declaration đồng bộ |
| M6 | UI/mobile và hồi quy | TypeScript, UI tests, các form/trạng thái tại mobile/desktop; không tác động landing/login cũ |
| M7 | Docker và hosting HTTPS | Image/tag/asset khớp source, dữ liệu được backup; kiểm tra HTTPS/cookie/public endpoint và rollback |

Các thay đổi dùng bảng hiện có; thêm migration mới cho token khôi phục và hash nội dung receipt MCP. Không sửa migration đã áp. Role runtime được cấp quyền đúng các bảng phát sinh, vẫn không có BYPASSRLS. Receipt cũ không có hash giữ hành vi replay cũ; receipt mới từ chối thay nội dung dưới cùng reference.

## 3. Luồng nghiệm thu không có Agent

1. Đăng ký cư dân mới bằng password riêng, kiểm tra pending và không có quyền admin/operations.
2. Admin chọn đúng căn hộ và quan hệ, xác minh; thử căn hộ không hợp lệ và xác nhận transaction không cấp quyền dở dang.
3. Cư dân đăng nhập lại, đọc được đúng căn hộ; thử truy cập ngoài phạm vi bị từ chối.
4. Tạo staff mới có đơn vị/chuyên môn/ca; đăng nhập và kiểm tra catalog.
5. Cư dân tạo ticket qua API nghiệp vụ, không gửi chat message hoặc gọi Reception.
6. BQL lập work order và giao staff mới; staff nhận, đang đến, đã đến, lập báo giá.
7. Cư dân quyết định báo giá; staff xử lý, bổ sung ảnh trước/sau; thiếu bằng chứng không được hoàn tất.
8. BQL QC; cư dân xác nhận đóng; retry cùng idempotency key không ghi trùng, version cũ bị từ chối.
9. Chạy nhánh cư dân không đạt → triaging/làm lại và giữ lịch sử.
10. Kiểm tra MCP bằng request protocol/DB có kiểm soát; không gọi Agent/platform leader/model.

Test ghi dữ liệu chạy trên PostgreSQL/MinIO riêng; production chủ yếu kiểm tra đọc, auth và discovery. Nếu cần account trên production để chủ dự án tự test, cung cấp account riêng trong file ignored, không đưa password vào báo cáo.

## 4. Phát hành và vận hành

- Backup DB, object storage, state và cấu hình riêng trước thay đổi; không seed/reset production.
- Build API và hai frontend theo tag release. Không rebuild/recreate Reception chỉ để test hoặc đổi provider.
- Nghiệm thu image ứng viên trước; áp migration bổ sung và cấp quyền runtime; recreate dịch vụ chịu ảnh hưởng.
- HTTPS dùng Nginx hiện có và chứng chỉ tự động, không đưa Caddy trở lại. HTTP challenge phải truy cập từ ngoài được trước khi cấp chứng chỉ; không mặc định nguyên nhân timeout do nhà cung cấp.
- Bật Secure cookie sau khi HTTPS public đã hoạt động; cập nhật allowed origins/MCP URL tương ứng.
- Ghi SHA, image digest và asset đang phục vụ. Kiểm tra landing/login, các vai trò và catalog MCP trên bản thực tế.
- Giữ manifest/image/env bản trước. Rollback image không đồng nghĩa rollback DB; không restore đè dữ liệu mới nếu chưa có quyết định riêng.
- Giữ SMTP thật tắt và bridge platform tắt khi chưa có thông tin. Báo cáo ghi rõ phần đó chưa nghiệm thu thay vì tính là hoàn tất.

## 5. Trạng thái và đầu ra

Tài liệu là kế hoạch/phạm vi đã chốt, không phải chứng nhận nghiệm thu. Kết quả cuối đợt phải tách: đã sửa source, đã test, đã build Docker, đã deploy VPS, và phần chủ dự án tự test sau.

Phần cần chủ dự án kiểm tra sau: chất lượng/hành vi Agent, credential provider thật, SMTP thật khi được cấu hình, và workflow platform thật khi có kết nối. Account cư dân trong báo lỗi cũ được giữ nguyên theo yêu cầu mới.
