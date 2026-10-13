# Quy tắc ăn tối và ngân sách cho DL-FAM-04

Áp dụng cho nhóm bốn người lớn trong hồ sơ DL-FAM-04. Dữ liệu này là chính sách test; giá bữa ăn cần lấy lại từ MCP.

## Bữa tối

- Đặt một bữa tối tại Đà Lạt ngày **2026-11-20**, lúc **18:30**, cho **bốn người**.
- Ưu tiên món nướng, không có yêu cầu ăn chay hoặc dị ứng trong hồ sơ này.
- Ngân sách tối đa **500.000 VND/người** theo giá trung bình của nhà hàng.
- Không chọn slot 17:30. Nếu 18:30 hết chỗ, hỏi người dùng trước khi đổi giờ.
- Lấy restaurant_id từ kết quả search_restaurants, đọc chi tiết và check_restaurant_availability trước khi đặt.
- Estimated_total là **dự toán**, không phải hóa đơn thực tế hoặc khoản tiền đã thanh toán.

## Cách tính ngân sách

Tổng dự toán dịch vụ bằng tiền khách sạn cho hai đêm cộng tiền xe một chiều cho bốn người cộng dự toán một bữa tối cho bốn người.

Khoản dự phòng bằng **10% tổng dự toán dịch vụ**. Tổng ngân sách cần giữ bằng tổng dự toán dịch vụ cộng khoản dự phòng. Trần tổng ngân sách là **8.000.000 VND cho cả nhóm**, không phải mỗi người.

Travel Budget nhận giá từ các chuyên viên, dùng tool calculator để tính, rồi báo các khoản riêng. Không cộng dự phòng vào giá MCP trả về và không nói khoản dự phòng đã được thu. Không tự áp mã giảm giá, thuế hoặc phụ phí mà dữ liệu dịch vụ không cung cấp.

Nếu tổng vượt trần, đưa phương án điều chỉnh và hỏi người dùng; không tự đổi sức chứa phòng, số ghế, ngày hoặc bỏ khoản dự phòng để tuyên bố đạt ngân sách.

## Phối hợp và xác nhận

Chuyên viên khách sạn, xe và nhà hàng báo ID dịch vụ, lịch và số tiền về Leader qua TeamSay. Travel Budget kiểm tra phép tính và cảnh báo phần thiếu. Người dùng chỉ xác nhận booking sau khi đã xem phương án có đủ các khoản và điều kiện hủy.
