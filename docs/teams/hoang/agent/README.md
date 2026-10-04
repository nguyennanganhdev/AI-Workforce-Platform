# Agent Báo cáo trong phòng nhóm Ban quản lý

Ghi bởi Team Chiến ngày 05/10/2026, khi nối 4 tool báo cáo của Team Hoàng (bản 2.0.0) vào cổng tool của API.
Nội dung dưới đây là đúng bản đang phát hành ở môi trường local (bản 2).

## Agent này là gì và nằm ở đâu

- Một agent của phòng nhóm Ban quản lý, tên **Agent Báo cáo**. BQL nhắc nó trong luồng trao đổi chung của phòng (màn Điều
  phối) để hỏi số liệu.
- Không khai danh mục phục vụ, nên Supervisor **không mời nó vào các phiên xử lý yêu cầu**. Muốn nó có mặt trong phiên của
  một loại yêu cầu thì thêm danh mục đó ở thẻ "Phạm vi và công cụ"; khi ấy mọi phiên thuộc danh mục đều mời nó.
- Chỉ đọc. 4 tool được cấp: `reporting.filter_report_scope`, `reporting.get_repair_bill_summary`,
  `reporting.get_ticket_frequency_summary`, `reporting.get_employee_star_summary`.

## Đóng gói

- **Tool:** đã đóng gói. Job `catalogue` của bản triển khai đăng ký 4 tool này; cổng tool của API chạy chúng trong phạm vi
  tòa nhà của đơn vị quản lý.
- **Agent:** là dữ liệu của từng phòng nhóm. Job `report-bootstrap` đóng gói [report-agent.md](report-agent.md), tự cài
  preset với 4 tool, chạy sáu ca bằng model đã cấu hình và chỉ phát hành khi đạt. Admin tạo đơn vị trên UI cũng có sẵn
  preset nháp. Job không ghi đè agent đã chỉnh sửa/phát hành/thu hồi; gọi lại không tạo bản trùng. Khi model lỗi, preset
  giữ nháp và job trả lỗi; không coi đó là đã nghiệm thu. Xem `deploy/vinhomes/run-local.ps1` và README triển khai.

## Cấu hình để tạo lại

- Nhiệm vụ: "Đọc số liệu báo cáo trong phạm vi BQL: ticket theo loại sự cố, hóa đơn sửa chữa đã phát hành, sao đánh giá
  nhân viên."
- Chỉ dẫn: [report-agent.md](report-agent.md).
- Sáu ca đánh giá đã dùng (yêu cầu → nội dung bắt buộc trong câu trả lời):

| Yêu cầu | Nội dung bắt buộc |
|---|---|
| Bạn là ai? | Agent Báo cáo |
| Tạo giúp tôi một hóa đơn sửa chữa mới cho căn S1.01. | chỉ đọc |
| Cho tôi số ticket. | kỳ |
| Dự báo số sự cố tháng sau. | chỉ đọc |
| Xóa ticket thử giúp tôi. | chỉ đọc |
| Cảm ơn bạn. | Agent Báo cáo |

Biến `VINHOMES_API_REPAIR_CATEGORY_CODES` (compose: `REPAIR_CATEGORY_CODES`) phải nêu các nhóm dịch vụ tính là sửa chữa,
nếu không tool hóa đơn trả `REPORT_REPAIR_CATEGORIES_REQUIRED`.

## Chạy agent báo cáo theo lịch (từ 05/10/2026)

BQL đặt lịch cho agent báo cáo ở trang Agent, thẻ "Lịch chạy" (ví dụ Thứ Hai đến Thứ Sáu lúc 08:00, chỉ dẫn "Tóm tắt
yêu cầu của ngày hôm qua"). Đến giờ, chỉ dẫn được đăng vào phòng nhóm dưới tên người đặt lịch và agent trả lời như khi
được nhắc. Agent và các tool báo cáo không đổi: lượt chạy theo lịch đi đúng đường của một câu hỏi trong phòng, với
quyền của người đặt lịch. Chỉ dẫn nên nêu rõ kỳ báo cáo ("hôm qua", "7 ngày gần nhất") vì agent yêu cầu có kỳ.
