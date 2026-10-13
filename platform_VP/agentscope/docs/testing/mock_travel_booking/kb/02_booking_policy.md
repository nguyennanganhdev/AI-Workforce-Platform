# Chính sách booking giả lập DEMO-CONFIRM-7

Áp dụng cho hồ sơ DL-FAM-04. Mã quy tắc xác nhận là **DEMO-CONFIRM-7**.

## Tra cứu trước khi đặt

Các bước tìm kiếm, xem chi tiết, kiểm tra khả dụng và lập dự toán không đồng nghĩa với một booking. ID dịch vụ chỉ được lấy từ MCP. Trước khi gọi book_hotel, book_bus_trip hoặc book_restaurant phải kiểm tra khả dụng tương ứng và nhận xác nhận rõ ràng của người dùng cho phương án cụ thể.

Lời yêu cầu "lập phương án", "tính giá", "có chỗ không" không phải xác nhận đặt. Trước khi gọi cancel_hotel_booking, cancel_bus_booking hoặc cancel_restaurant_booking cũng cần người dùng xác nhận mã booking cần hủy.

## Chống tạo trùng

Mỗi dịch vụ của mỗi lần chạy có một client_reference riêng. Retry cùng một booking giữ nguyên client_reference và nội dung. Khi ngày, dịch vụ hoặc số người thay đổi, hỏi lại xác nhận rồi tạo reference mới; không tái dùng reference cũ cho nội dung khác.

Nếu mất phản hồi sau khi gửi booking, kiểm tra get/list hoặc retry với reference ban đầu trước khi tạo một giao dịch mới.

## Báo kết quả

Chỉ báo đã đặt khi tool trả success=true và có booking_id. Nếu tool báo hết chỗ hoặc lỗi, báo đúng lỗi và đề xuất bước tiếp theo; không bịa mã booking.

Khi báo tổng kết, phân biệt khách sạn, xe, nhà hàng; ghi số người, ngày giờ, trạng thái và điều kiện hủy từ chi tiết dịch vụ. Tên/mã dịch vụ khác với mã booking.

## Giới hạn môi trường

Đây là mock trong RAM: không có thanh toán thật, không gửi email hoặc SMS, không có vé thật. Khởi động lại MCP làm mất booking. Điều kiện hủy do catalog cung cấp là thông tin demo; tool hủy chỉ cập nhật trạng thái và giải phóng tồn, không thu hoặc hoàn tiền thật.

Thiếu dữ liệu KB, thiếu tool hoặc không tìm được dịch vụ phải được báo rõ. Chính sách này không cấp thêm quyền tool và không thay thế xác nhận permission của ứng dụng.
