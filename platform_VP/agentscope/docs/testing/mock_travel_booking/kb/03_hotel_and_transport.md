# Quy tắc khách sạn và xe cho DL-FAM-04

Tài liệu này là yêu cầu của nhóm test. Giá, danh mục hiện hành và tồn kho lấy từ Mock Travel Booking MCP.

## Khách sạn

- Thành phố: Đà Lạt.
- Một phòng cho bốn người lớn, nhận 2026-11-20 và trả 2026-11-22.
- Giá trần: **1.800.000 VND/phòng/đêm**.
- Cần **wifi**, **đỗ xe** và **vườn**.
- Không chấp nhận một phòng tối đa hai người cho cả nhóm bốn người. Phải đối chiếu max_guests của loại phòng.
- Nếu có bungalow đáp ứng sức chứa và ngân sách thì ưu tiên bungalow. Không đổi sang hai phòng đôi để làm số tiền trông rẻ hơn.
- Chọn từ kết quả search_hotels; đọc get_hotel_details và check_hotel_availability trước khi báo phương án/đặt.

Khi đặt, special_requests có thể ghi "Hồ sơ DL-FAM-04, nhóm bốn người lớn, ưu tiên phòng yên tĩnh". Chỉ ghi như yêu cầu của khách, không cam kết nhà cung cấp đã đáp ứng.

## Xe

- Chiều đi: Hồ Chí Minh đến Đà Lạt, ngày 2026-11-20.
- Bốn ghế cho bốn người có tên trong hồ sơ.
- Ưu tiên chuyến cabin 07:00 đến Đà Lạt cùng ngày; không lấy chuyến 23:00 chỉ vì giá rẻ hơn.
- Điểm đón mong muốn: **Bến xe Miền Đông mới**.
- Điểm trả mong muốn: **Chợ Đà Lạt**.
- Giá trần: **450.000 VND/ghế**.
- Chỉ dùng điểm đón/trả nằm trong danh sách của chuyến xe. Phải kiểm tra số ghế còn trước khi đặt.

Nếu không có phương án hợp lệ, báo rõ điều kiện nào không đáp ứng; không tự thêm tuyến vé về hoặc tự đổi giờ đi. Khách sạn và xe phải chia sẻ ngày đến với chuyên viên nhà hàng qua Leader/TeamSay để tránh lệch lịch.
