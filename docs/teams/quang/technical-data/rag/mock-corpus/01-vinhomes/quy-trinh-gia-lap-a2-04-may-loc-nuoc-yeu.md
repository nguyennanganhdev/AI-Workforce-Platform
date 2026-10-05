---
trang_thai: du-lieu-gia-lap-khong-xuat-ban
cap_nhat: 2026-10-05
van_ban: MOCK-PROC-04-v1
issue_code: TECH.PLUMB.WATER_FILTER_LOW_FLOW
fixture_only: true
approval_status: not_published
sop_available: false
audience: technician_test_only
version: mock-v1
---
# MOCK-PROC-04 — Quy trình mẫu: máy lọc nước chảy yếu

MẪU GIẢ LẬP cho kiểm thử nội bộ, không phải SOP Vinhomes hoặc khuyến nghị chất lượng nước uống.

## Thu thập dữ kiện
Ghi lưu lượng yếu tại vòi lọc hay mọi vòi, model máy/lõi, thời điểm thay lõi, tình trạng bơm/van theo lời báo và ảnh vị trí rò nếu có. Nước đổi màu, mùi bất thường hoặc nghi nhiễm bẩn là tín hiệu chuyển người kiểm tra chất lượng; không khẳng định nước uống an toàn. Nước gần điện hoặc rò lan phải ưu tiên an toàn trước chẩn đoán.

## Kiểm tra và xử lý có thẩm quyền
Tra outage nguồn nước, asset/model/manual đúng loại lõi, lịch sử thay và yêu cầu bảo hành. Kỹ thuật viên đo lưu lượng/áp lực trước xử lý nếu quy trình thiết bị quy định, ghi metric, unit, measured_at, thiết bị và người đo. Phân biệt nguồn cấp chung yếu, tắc lõi, van hoặc ống gập; không kết luận “phải thay lõi” từ triệu chứng đơn lẻ. Việc thay vật tư hay can thiệp bơm chỉ do người đủ quyền theo manual thực hiện, ghi mã vật tư và lý do.

## Kiểm chứng
Ghi phép đo sau xử lý cùng điều kiện so sánh, thử rò quanh đầu nối, nhật ký thay lõi và ảnh trước/sau. Nếu không có tiêu chí lưu lượng của đúng model, chỉ ghi kết quả quan sát và yêu cầu người có chuyên môn kết luận; không tự đặt ngưỡng. Cần bằng chứng chất lượng nước riêng khi có khiếu nại về nước uống. `technical.verify_resolution` không tự đóng ticket.

## Tình huống phân nhánh
- Lưu lượng giảm: hỏi mốc thay lõi, nguồn đầu vào, chỉ vòi sau lọc hay nhiều vòi; không suy lõi bẩn.
- Nước có mùi/màu lạ hoặc rò gần điện: ngừng dùng để uống và chuyển đánh giá phù hợp; không tuyên bố nước độc hay an toàn từ lời kể.
- Nhà cung cấp quản lý máy: kiểm tra bảo hành trước thay linh kiện, tạo yêu cầu phối hợp nếu cần.

## Hồ sơ tối thiểu và hậu kiểm
Ghi model/serial, điểm cấp nước, mùi/màu/vị, thời điểm và ảnh. Liên kết lịch bảo trì với ticket nhưng không dùng maintenance cũ như chẩn đoán. Kỹ thuật viên ghi phép đo lưu lượng/áp lực theo phương pháp đã duyệt, tình trạng lõi/đường nước, vật tư và ảnh. Phải tách nghiệm thu chức năng thiết bị khỏi đánh giá chất lượng nước. Nước chảy mạnh trở lại không chứng minh uống an toàn; thiếu xét nghiệm/phê duyệt khi có nghi ngờ thì vẫn cần người có chuyên môn đánh giá.

## Nguồn
- MOCK-PROC-04-v1: fixture thiết kế từ technical-data/ISSUE_CATALOG.md mục 04 và docs/teams/quang/general.md; không phải văn bản BQL.
