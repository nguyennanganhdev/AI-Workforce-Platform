---
trang_thai: du-lieu-gia-lap-khong-xuat-ban
cap_nhat: 2026-10-05
van_ban: MOCK-PROC-16-v1
issue_code: TECH.PLUMB.SEWAGE_BACKFLOW
fixture_only: true
approval_status: not_published
sop_available: false
audience: technician_test_only
version: mock-v1
---
# MOCK-PROC-16 — Quy trình mẫu: nước thải trào ngược

MẪU GIẢ LẬP cho POC A2; không phải SOP Vinhomes hay hướng dẫn cư dân xử lý nước thải.

## Tiếp nhận và chuyển người
Ghi vị trí thoát, loại nước nghi là thải, mức/tốc độ lan, căn/khu chung ảnh hưởng, nước gần điện, người tiếp xúc và triệu chứng sức khỏe. Trào rộng, gần điện hoặc có phơi nhiễm thì chuyển người trực ngay; không chờ ảnh. Giữ nước thải tách khỏi luồng “rò nước sạch”; không yêu cầu cư dân thông tắc, dùng hóa chất hoặc vệ sinh vùng nhiễm bẩn. `area_restriction.request` chỉ tạo yêu cầu chờ duyệt.

## Xác định nguồn và xử lý có kiểm soát
Tra incident/outage cùng building và lịch sử tắc; kỹ thuật viên đúng chuyên môn xác định cục bộ hay tuyến chung, ghi vị trí và bằng chứng trước. Work order bao gồm phương án xử lý nguồn, kiểm soát tiếp xúc và phối hợp vệ sinh theo quy trình được phê duyệt; không mặc định thông tuyến xong là khu vực sạch. Nếu cần cô lập nước/giới hạn khu vực, trạng thái request pending chưa phải hành động thực địa.

## Điều kiện kiểm chứng
Executor result cần evidence sau xử lý đúng ticket, thử thoát theo SOP, checklist vệ sinh/khử nhiễm do người được giao xác nhận, thời điểm và phạm vi. Nếu chỉ có ảnh miệng thoát sạch hoặc nước ngừng trào nhưng thiếu checklist vệ sinh, trả `NEEDS_EVIDENCE`. Nếu còn nguồn trào, nguy cơ sức khỏe hoặc lời báo mâu thuẫn, trả `HUMAN_REVIEW`; người có quyền mới xác nhận an toàn và hoàn tất.

## Tình huống phân nhánh
- Nước thải trào tại một điểm: ghi vị trí, thời điểm, diện tích và có tiếp xúc với người/điện không; chuyển người trực ưu tiên vệ sinh và an toàn.
- Nhiều căn hoặc nhiều điểm thoát cùng trào: đối chiếu mạng thoát chung và outage/sự kiện building đúng quyền, phối hợp điều phối; không khẳng định do hành vi một căn.
- Có nước thải gần nguồn điện hoặc người có triệu chứng sức khỏe: nhánh khẩn, không chờ thu đủ ảnh hoặc hướng dẫn cư dân tự xử lý đường ống.

## Hồ sơ tối thiểu và hậu kiểm
Ticket ghi phạm vi nhiễm bẩn, nguồn từng nhận định, căn/khu vực ảnh hưởng và các yêu cầu vào căn; không xem dữ liệu căn khác khi chưa có grant. Asset và work order xác định tuyến thoát, owner, người thực hiện, biện pháp an toàn và SOP được duyệt. Kỹ thuật viên ghi vị trí tắc/rò đã kiểm chứng, công việc, evidence, biên bản vệ sinh/khử nhiễm và thử thoát nước theo quy trình. Chỉ hết trào trong một lần quan sát chưa đủ nghiệm thu; cần xác nhận nguồn, chức năng, vệ sinh và người có quyền chấp nhận. Không tự khẳng định môi trường đã an toàn.

## Nguồn
- MOCK-PROC-16-v1: fixture thiết kế từ technical-data/POC_WORKFLOWS.md POC 5 và ISSUE_CATALOG.md mục 16; không phải văn bản BQL.
