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
- **Agent:** là dữ liệu của từng phòng nhóm, không nằm trong image. Một bản triển khai mới chưa có Agent Báo cáo: BQL tạo
  agent ở trang Agent, dán chỉ dẫn trong [report-agent.md](report-agent.md), chọn 4 tool, chạy đánh giá rồi phát hành.
  Chưa có lệnh tự tạo agent này khi cài đặt (`agent-coordination/scripts/publish_agent.ps1` mới đọc được tool kỹ thuật).

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
