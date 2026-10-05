---
trang_thai: du-lieu-gia-lap-khong-xuat-ban
cap_nhat: 2026-10-05
van_ban: MOCK-PROC-14-v1
issue_code: TECH.ARCH.PAINT_MOISTURE
fixture_only: true
approval_status: not_published
sop_available: false
audience: technician_test_only
version: mock-v1
---
# MOCK-PROC-14 — Quy trình mẫu: sơn bong, vết ố hoặc ẩm mốc

MẪU GIẢ LẬP, không phải SOP Vinhomes hoặc lời khuyên y tế. Không sơn che vết ố khi nguồn ẩm chưa được xử lý.

## Thu thập và phân luồng
Ghi diện tích/vị trí, thời điểm, ảnh theo mốc thời gian, mùi, nước đang rò, vật liệu mềm và người báo triệu chứng sức khỏe. Nước gần điện, trần võng hoặc ẩm lan nhanh phải chuyển người trực; ảnh hưởng sức khỏe cần người phù hợp đánh giá. Không gán nguyên nhân “thấm từ căn trên” chỉ vì vị trí vết ố.

## Điều tra nguồn ẩm
Đối chiếu incident rò nước/điều hòa, outage, lịch sử sửa và bề mặt quanh khu vực. Kỹ thuật viên ghi độ ẩm theo điểm đo với metric/unit/phương pháp/measured_at/by; manual vật liệu và SOP thật quyết định điều kiện thi công. Nếu có mốc/ẩm ở nhiều vị trí, lập phạm vi khảo sát và khắc phục nguồn; không dùng ảnh sau sơn làm bằng chứng đã hết ẩm. Việc tiếp cận căn liên quan phải qua quyền/approval.

## Kết quả
Work order ghi nguồn ẩm đã xác nhận, biện pháp xử lý nguồn, vật liệu thay, số đo và ảnh trước/sau. Sau xử lý phải có mốc theo dõi tái ẩm theo SOP đã duyệt; không bịa thời gian khô hay nồng độ an toàn. Thiếu chứng cứ xử lý nguồn hoặc vẫn có dấu ẩm trả `NEEDS_EVIDENCE`/`HUMAN_REVIEW`, không tự tuyên bố khu vực an toàn.

## Tình huống phân nhánh
- Sơn bong/ố cục bộ: hỏi mốc bắt đầu, vùng mở rộng, ảnh và gần khu vực ẩm/đường ống không; không coi sơn là nguyên nhân.
- Có mùi mốc mạnh, vật liệu rơi hoặc nước gần điện: chuyển nhánh an toàn/sức khỏe, hạn chế tiếp xúc; không đề nghị cạo sơn hoặc phun hóa chất.
- Sơn vừa làm lại đã bong: đối chiếu lịch công việc, điều kiện nền và biên bản nghiệm thu cũ; không tự quy trách nhiệm nhà thầu.

## Hồ sơ tối thiểu và hậu kiểm
Ticket phân biệt triệu chứng bề mặt với nguồn ẩm tiềm ẩn, có ảnh mốc thời gian và diện tích/vị trí. Kỹ thuật viên ghi kết quả khảo sát nền, phép đo ẩm có phương pháp/đơn vị, nguồn nước được kiểm chứng và hạng mục xử lý. Nếu nguồn ẩm chưa xử lý, chỉ ghi can thiệp tạm, không nghiệm thu sơn cuối. Hồ sơ sau phải có ảnh đúng ticket, vật tư/phạm vi sửa, tiêu chí khô nền và quan sát tái ẩm từ SOP được duyệt; không tự đặt thời gian khô từ mẫu này.

## Nguồn
- MOCK-PROC-14-v1: fixture thiết kế từ technical-data/ISSUE_CATALOG.md mục 14 và docs/teams/quang/general.md; không phải văn bản BQL.
