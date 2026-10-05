---
trang_thai: du-lieu-gia-lap-khong-xuat-ban
cap_nhat: 2026-10-05
van_ban: MOCK-PROC-08-v1
issue_code: TECH.PLUMB.TOILET_LEAK
fixture_only: true
approval_status: not_published
sop_available: false
audience: technician_test_only
version: mock-v1
---
# MOCK-PROC-08 — Quy trình mẫu: bồn cầu rỉ hoặc chảy liên tục

MẪU GIẢ LẬP cho kiểm thử A2, không phải SOP Vinhomes.

## Thu thập và phân biệt triệu chứng
Ghi nước rò ra sàn hay chảy trong lòng bồn, có tràn/nước bẩn không, tiếng nước liên tục, vị trí cấp/thoát và model nếu biết. Hỏi nước gần điện, sàn trơn, căn dưới bị ảnh hưởng và vật liệu bồn có nứt hay không. Nước thải tràn thì chuyển sang luồng `TECH.PLUMB.SEWAGE_BACKFLOW`; nước rò mạnh hoặc gần điện thì chuyển người trực.

## Khảo sát đúng asset
Kỹ thuật viên đối chiếu model và manual, ảnh vị trí cấp/thoát, lịch sử thay linh kiện. Phân biệt van cấp, bộ xả, đầu nối, chân bồn và đường thoát bằng quan sát/kiểm tra được phép; không thay gioăng chỉ vì sàn ướt. Work order ghi chẩn đoán, nguồn nước sạch hay thải, vật tư tương thích và tình trạng trước xử lý. Nếu cần cô lập nước chung, request chỉ pending cho tới khi có phê duyệt.

## Nghiệm thu và theo dõi
Executor result có checklist, thử xả có giám sát theo SOP, ảnh/số đo nếu yêu cầu, ghi sàn và điểm nối sau thử. Cần tách tiêu chí “nước ngừng chảy trong lòng bồn” và “không còn rò ra sàn”; đạt một tiêu chí không chứng minh tiêu chí kia. Bằng chứng sai ticket hoặc thiếu thử lại dẫn tới `NEEDS_EVIDENCE`; nguồn rò chưa rõ dẫn tới `HUMAN_REVIEW`.

## Tình huống phân nhánh
- Nước rỉ liên tục trong lòng bồn: hỏi âm thanh cấp nước, rò sau xả hay liên tục; phân biệt với nước rò ra sàn.
- Rò tại chân bồn hoặc nước thải ra nền: đánh dấu nguy cơ vệ sinh, tránh tiếp xúc và chuyển kỹ thuật viên. Trào nhiều điểm cần xét nhánh thoát chung.
- Nhiều căn cùng báo: đối chiếu đường thoát và sự cố chung theo quyền; không thay linh kiện từng bồn trước khi xác định phạm vi.

## Hồ sơ tối thiểu và hậu kiểm
Ticket lưu vị trí rò, màu/mùi nước, thời điểm và ảnh. Xác minh asset và owner. Kỹ thuật viên ghi chẩn đoán, vật tư, phép thử và evidence đúng ticket theo SOP. Nếu nghi nước thải, phương án vệ sinh/khử nhiễm cần được người có quyền duyệt; không trộn với rò nước sạch. Đối chiếu vị trí rò cũ trong điều kiện thử được duyệt và ghi nhận tái phát; một ảnh sàn khô không đủ để xác minh.

## Nguồn
- MOCK-PROC-08-v1: fixture thiết kế từ technical-data/ISSUE_CATALOG.md mục 08 và docs/teams/quang/general.md; không phải văn bản BQL.
