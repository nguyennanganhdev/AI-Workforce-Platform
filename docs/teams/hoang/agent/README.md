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
- **Từ 07/10/2026 (bản 3) kiêm kế toán vận hành**, tên giữ nguyên. Thêm tool `knowledge.search` để tra tài liệu kế toán
  của BQL (xem mục "Tài liệu BQL" bên dưới): hạch toán theo TT99/2025 (kế toán doanh nghiệp chung, không phải quy trình
  Vinhomes), Quy chế nhà chung cư về thu chi, kinh phí vận hành và bảo trì (bản gốc 2024), giá vật tư tham khảo quý
  II/2026 Hà Nội. Không tự đặt mức phí; câu hỏi biểu phí của dự án được trả lời là chưa có tài liệu.

## Đóng gói

- **Tool:** đã đóng gói. Job `catalogue` của bản triển khai đăng ký 4 tool này; cổng tool của API chạy chúng trong phạm vi
  tòa nhà của đơn vị quản lý.
- **Agent:** là dữ liệu của từng phòng nhóm. Job `report-bootstrap` đóng gói [report-agent.md](report-agent.md), tự cài
  preset với 4 tool, chạy sáu ca bằng model đã cấu hình và chỉ phát hành khi đạt. Admin tạo đơn vị trên UI cũng có sẵn
  preset nháp. Job không ghi đè agent đã chỉnh sửa/phát hành/thu hồi; gọi lại không tạo bản trùng. Khi model lỗi, preset
  giữ nháp và job trả lỗi; không coi đó là đã nghiệm thu. Xem `deploy/vinhomes/run-local.ps1` và README triển khai.

## Cấu hình để tạo lại

- Định nghĩa đầy đủ (mô tả, tool, mười ca đánh giá): [report-agent.json](report-agent.json); chỉ dẫn:
  [report-agent.md](report-agent.md). Bản 3 đạt 10/10 ca trên server ngày 07/10/2026.
- Sáu ca gốc (job `report-bootstrap` vẫn dùng đúng sáu ca này; bốn ca kế toán nằm trong file JSON):

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

# Agent Vệ sinh & Cảnh quan (từ 07/10/2026)

Ghi bởi Team Chiến khi nối bộ tool vệ sinh của Team Hoàng (`server/src/cleaning-tools`, commit `91e1389` trên
`dev_TeamHoang`) vào phiên Supervisor.

- **Định tuyến.** Danh mục dịch vụ `cleaning` ("Vệ sinh & cảnh quan"). Lễ tân chọn danh mục này cho phản ánh vệ sinh,
  rác, côn trùng, cây xanh; yêu cầu đến đơn vị quản lý phụ trách `cleaning` của tòa; Supervisor mời agent khai danh mục
  này; việc được mời cho nhân viên có chuyên môn `cleaning`. Dữ liệu (không thêm bảng):
  `services/vinhomes-api/scripts/add_cleaning_service.py` thêm danh mục, phạm vi phụ trách ở mọi nơi đơn vị đang phụ
  trách `technical`, và một nhân viên vệ sinh của BQL Sapphire (`VS-SAPPHIRE-01`). Chạy lại an toàn.
- **Tool trong phiên.** Tool host phục vụ 14 tool đối ứng `cleaning.*` dưới server `cleaning-tools` (job `upgrade`
  đăng ký); như bên kỹ thuật, chỉ tool đọc chạy được trong phiên. Năm tool điều phối V3 của module (tìm nhân viên,
  đọc/tạo việc, phân công, cập nhật trạng thái) **chưa** phục vụ: chúng cần cầu nối tới API mà phiên chưa có. Việc
  tạo việc và mời nhân viên do luồng Supervisor hiện có làm. Chuyên môn nhà thầu chưa có ánh xạ tin cậy sang vệ sinh,
  nên `cleaning.request_vendor_dispatch` luôn bị từ chối.
- **Agent.** [cleaning-agent.md](cleaning-agent.md) (chỉ dẫn, 13 mã `CLEAN.*` do Team Chiến soạn bản đầu) và
  [cleaning-agent.json](cleaning-agent.json) (4 tool: `cleaning.retrieve_sop`, `knowledge.search`,
  `cleaning.get_active_outage`, `cleaning.read_utility_schedule`; 8 ca). Đạt 8/8 ca trên server, phát hành ở phòng
  `bql-sapphire` của stack Docker local. Đã chạy thật một phản ánh "rác tràn phòng rác tầng 12" từ app cư dân đến
  lúc việc được mời cho `VS-SAPPHIRE-01`.

Việc cần Team Hoàng: rà bộ mã `CLEAN.*` và mức độ; nạp SOP vệ sinh thật (`vh_technical_sop_profiles` với mã
`CLEAN.*` và tài liệu cấp cho workspace), vì hiện `cleaning.retrieve_sop` luôn trả `NOT_FOUND`; quyết định có cần nối
năm tool điều phối cho phiên hay không.

# Tài liệu BQL trong kho tri thức (từ 07/10/2026)

`server/src/knowledge/publish-bql.ts` nạp tài liệu chỉ agent của BQL đọc: mã `bql/<chủ đề>/<tệp>` trong kho tri thức của
khu, phạm vi là từng đơn vị quản lý. Tìm kiếm của cư dân không bao giờ gồm phạm vi đơn vị nên Lễ tân không thấy các tài
liệu này; `publish.ts` (dữ liệu cư dân) không xóa chúng khi chạy lại. Đã nạp 41 tệp `rag_ready` của gói `cleaning_kb`
và `accounting_kb` (12 điều TT05 cho vệ sinh; 6 điều Quy chế về tài chính, 9 mục TT99, 14 bảng giá tham khảo cho kế
toán). Tiêu đề mỗi tài liệu nói rõ nguồn và giới hạn của nó vì đó là thứ agent đọc được trong kết quả. Gói nguồn không
còn trong repo; đơn vị quản lý tạo sau cần chạy `publish-bql.ts --rescope --site <khu>` để đọc được các tài liệu này.
