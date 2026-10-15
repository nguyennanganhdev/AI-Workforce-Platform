# Travel mock: Reception → Domain → Platform

## Phạm vi và nguồn

Nguồn người dùng cung cấp: `mock_travel_booking_mcp.zip`. Gói gốc có 23 tool, 5 khách sạn, 5 chuyến xe và 5 nhà hàng giả lập; booking lưu trong RAM. Domain chỉ tích hợp `data.py`, `service.py`, `__init__.py` đã rà soát, lưu hash gói nguồn tại `vinhomes_api/mock_travel/PROVENANCE.json`. Không chép `.env`, `.venv`, cache, server MCP độc lập hoặc calculator từ ZIP; không chạy lệnh cài đặt trong README của gói.

**Chỉ mô phỏng.** Tên, địa chỉ, giá, giờ, chính sách và tồn chỗ từ ZIP không phải dữ liệu dịch vụ thật hoặc đối tác đã xác nhận của Vinhomes. Không có thanh toán/hoàn tiền, email/SMS hoặc API nhà cung cấp thật. Mọi kết quả có `provider_mode=mock`, `is_simulation=true`, `real_booking=false`; `mock_confirmed` không phải đặt chỗ thật.

Booking và tồn chỗ được lưu/khôi phục từ PostgreSQL, tách khỏi tài khoản/cư trú/nhân sự và danh mục dịch vụ vận hành thật. Mỗi tenant có mock inventory riêng; khóa transaction PostgreSQL tuần tự hóa kiểm tra/đặt/hủy giữa các worker. Không dùng RAM làm nguồn dữ liệu bền.

## Reception và route

- Thêm danh mục `travel` — “Du lịch/đặt chỗ (mô phỏng)”. Reception tra kho tri thức để giới thiệu đúng chế độ, tiếp nhận nhu cầu nguyên văn bằng `service_request`, không tự đặt/hủy.
- Có 48 tài liệu mock dành cho cư dân, phân phạm vi riêng OP1/2/3: 3 giới thiệu chức năng và 45 tài liệu mô tả sản phẩm mock. Mỗi đoạn ghi rõ MÔ PHỎNG, vẫn `unverified=true`; không nâng thành chính sách/giá thật.
- Route riêng `external_management_ref=travel-mock`, tên “Nhà cung cấp Travel MÔ PHỎNG”, có scope theo 3 site. Đây không phải pháp nhân quản lý tòa thật và không tạo tài khoản BQL tại Domain.
- Route hoạt động trong Domain không chứng minh đã nối Platform. Platform phải khai báo/ánh xạ đúng `travel-mock` và cấu hình bridge tại admin Domain. Khi bridge chưa bật, chưa nghiệm thu được session/Agent thật trên Platform.
- Ticket travel không dùng tool giao nhân viên hoặc tạo work order kỹ thuật. Booking đang confirmed phải được hủy đúng luồng trước khi MCP cho phép hủy ticket. Platform giữ luồng hoạt động khi cư dân còn cần đổi/hủy booking và làm mới grant khi hết hạn.

## MCP cung cấp sang Platform

Endpoint giữ nguyên `https://vinhome-platform.duckdns.org/mcp`, transport `streamable_http`. Tổng 14 tool: giữ 7 tool xử lý ticket hiện có và thêm:

| Tool | Vai trò |
|---|---|
| `vh_travel_catalog` | Thành phố, tuyến và nhóm dịch vụ mock để hình thành truy vấn |
| `vh_travel_search` | Tìm khách sạn/chuyến xe/nhà hàng theo điều kiện |
| `vh_travel_details` | Đọc chi tiết một mã sản phẩm từ kết quả tìm |
| `vh_travel_availability` | Kiểm tra chỗ và giá mock theo ngày/giờ/số lượng |
| `vh_travel_prepare` | Chuẩn bị phương án đặt/hủy trong 15 phút; chưa thực hiện booking |
| `vh_travel_commit` | Thực hiện đúng phương án mà cư dân đã đồng ý |
| `vh_travel_bookings` | Booking của riêng ticket đang được cấp quyền |

Không cung cấp tool tra toàn bộ booking theo số điện thoại, tool xác định lại cư dân/căn hộ hoặc tool tạo ticket. Không đưa calculator của ZIP vào MCP nghiệp vụ Domain.

Token khởi tạo giữ nguyên, chỉ dùng discovery và control-plane. Platform backend gọi `POST /api/business/platform/mcp-grants` với các tham chiếu `ticket_id`, `external_request_id`, `workflow_id`, `grant_request_id` đã bàn giao để nhận Bearer grant riêng. `tools` chỉ cấp các tên thực sự cần; hạn mức schema đã hỗ trợ cả 14 tên. Grant cũ không tự được mở thêm quyền travel. Không đưa token control-plane cho model và không dùng key trong `.env` của ZIP.

Tất cả tool travel kiểm tra: grant có đúng tool/ticket, ticket đã bàn giao còn hoạt động, category=`travel`, cờ `VINHOMES_TRAVEL_MOCK_ENABLED=1`. Tool đặt/hủy không nhận `customer_name`, `customer_phone`, `customer_email` từ Platform; Domain lấy liên hệ đã có trong ticket. Kết quả loại các trường danh tính này.

## Luồng đặt/hủy và sự đồng ý

1. Platform đọc `vh_ticket_get`, dùng các tool tra cứu phù hợp. `kind` là `hotel`, `bus` hoặc `restaurant`. Không coi availability là giữ chỗ.
2. Gọi `vh_travel_prepare` với `operation=book` hoặc `cancel`, `client_reference` ổn định và `expected_ticket_version` hiện tại. `cancel` dùng `booking_ref` của ticket và lý do. Chuyến xe phải có điểm đón/trả được cư dân chọn; không tự đoán danh tính hoặc điểm đi.
3. Kết quả có `intent_id`, `approval_request.quote_ref`, `arguments_hash`, `summary`, `expires_at`. Platform dùng luồng **`approval.required` hiện có** để gửi thẻ xác nhận về chat Domain, chép nguyên các trường trên và đặt `approval_id`/`expected_revision` theo workflow của Platform. Tóm tắt phải giữ nhãn MÔ PHỎNG, lựa chọn và giá/điều kiện cần đồng ý.
4. Cư dân bấm đồng ý/từ chối trên thẻ. Endpoint Domain hiện có `/resident/platform/approvals/{approval_id}/decision` ghi trạng thái và xếp `approval_decision` gửi Platform. Không có bước BQL duyệt thay cư dân.
5. Nếu đồng ý, Platform gọi `vh_travel_commit` với đúng `intent_id`, `approval_id`, reference và phiên bản ticket hiện tại. Domain yêu cầu **cả** approval khớp quote/hash **và** quyết định cư dân do endpoint Domain ghi; sự kiện `approval.resolved` của Platform một mình không đủ.
6. Domain kiểm tra lại tồn chỗ, giá và điều kiện đã duyệt, ghi booking/receipt bền trong cùng transaction. Retry giữ nguyên reference trả cùng kết quả nghiệp vụ; correlation ID của mỗi lượt gọi vẫn khác. Không gọi lại bằng reference mới khi kết quả chưa rõ.
7. Domain xếp `workflow_reply` có `own=true` và khóa thông báo ổn định để Platform tổng hợp/phản hồi cư dân. Tool thành công/xếp hàng gửi không chứng minh Platform đã nhận hoặc đã thông báo cư dân.
8. Hủy cũng phải prepare → thẻ xác nhận → cư dân quyết định → commit. Hủy mock giải phóng tồn phòng/ghế/sức chứa; không mô phỏng quyết toán tiền.

## Các tham số thường dùng

| Loại | Tìm kiếm | Lựa chọn đặt |
|---|---|---|
| `hotel` | `city`, `check_in`, `check_out`, `guests`, `rooms`; tùy chọn ngân sách/sao/tiện ích | `hotel_id`, `room_type_id`, `check_in`, `check_out`, `guests`, `rooms`, tùy chọn `special_requests` |
| `bus` | `origin`, `destination`, `travel_date`, `passengers`; tùy chọn giá/loại ghế | `trip_id`, `travel_date`, `seats`, `pickup_point`, `dropoff_point` |
| `restaurant` | `city`, `reservation_date`, `reservation_time`, `party_size`; tùy chọn món/đánh giá/ngân sách | `restaurant_id`, `reservation_date`, `reservation_time`, `party_size`, tùy chọn `special_requests` |

Ngày `YYYY-MM-DD`, giờ `HH:MM`; chọn giờ có trong kết quả chi tiết nhà hàng. Đầu vào giới hạn độ dài/số lượng và từ chối trường không được phép. Truy vấn sai ngày/giờ/sức chứa trả lỗi nghiệp vụ, không tự sửa lựa chọn cư dân.

Lỗi chính: `TICKET_SCOPE_FORBIDDEN`, `TRAVEL_TICKET_REQUIRED`, `TRAVEL_DISABLED`, `TRAVEL_INPUT_INVALID`, `TRAVEL_RESIDENT_APPROVAL_REQUIRED`, `TRAVEL_QUOTE_EXPIRED`, `TRAVEL_QUOTE_CHANGED`, `TRAVEL_SOLD_OUT`, `REFERENCE_CONFLICT`, `TRAVEL_USE_BOOKING_TOOLS`, `TRAVEL_CANCEL_BOOKINGS_FIRST`. Lỗi dùng `isError=true` và trường structured `error.code/message/retryable` theo MCP v2 hiện có.

## Cấu hình và bảo trì

- Mặc định file env example giữ `VINHOMES_TRAVEL_MOCK_ENABLED=0`; bật rõ ràng sau khi provision mock bằng `python -m vinhomes_api.travel_seed --enable-mock` với `DATABASE_URL` owner ở file riêng. Không chạy seed sample-world hoặc tạo tài khoản demo cho người dùng.
- Seed chỉ thêm danh mục/route/knowledge mock và giữ dữ liệu booking hiện có. Cần sao lưu trước khi cập nhật nguồn mock; các quote đã chuẩn bị phải được kiểm tra lại theo giá/điều kiện hiện hành.
- `owner_review` là công cụ riêng nhập 113 mục đã được người dùng duyệt triển khai, lưu dấu vết/hash và dữ kiện còn thiếu. Nó không biến bảng giá mock thành phí vận hành hoặc tự xác minh cư trú/nhân sự.
- Khi dùng nhà cung cấp thật, cần adapter/API, hợp đồng, quyền chia sẻ dữ liệu, quy trình thanh toán/hủy/hoàn và nghiệm thu riêng. Schema hiện ép `provider_mode=mock`; không đổi nhãn để coi mô phỏng là giao dịch thật.
