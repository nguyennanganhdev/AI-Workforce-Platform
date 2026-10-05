---
trang_thai: du-lieu-gia-lap-khong-xuat-ban
cap_nhat: 2026-10-05
van_ban: MOCK-PROC-09-v1
issue_code: TECH.PLUMB.TRAP_ODOR
fixture_only: true
approval_status: not_published
sop_available: false
audience: technician_test_only
version: mock-v1
---
# MOCK-PROC-09 — Quy trình mẫu: mùi cống hoặc bẫy nước

MẪU GIẢ LẬP cho kiểm thử nội bộ; không phải SOP Vinhomes. Mùi chưa rõ nguồn không được mặc định là cống.

## Tiếp nhận và an toàn
Ghi vị trí/mốc giờ mùi, drain liên quan, phạm vi một căn hay nhiều căn, thoát chậm/trào nước thải, triệu chứng sức khỏe và điều kiện thông gió. Hỏi tách biệt mùi gas, khói và mùi nước thải; nghi gas hoặc nhiều người khó chịu thì chuyển người trực theo quy trình khẩn có thẩm quyền. Không bảo cư dân mở hố ga, trục kỹ thuật hoặc tiếp xúc nước bẩn.

## Kiểm tra và xác minh nguồn
Đối chiếu incident/outage cùng building, sơ đồ hệ thoát được cấp quyền, lịch sử sửa và ảnh/ghi nhận hiện trường. Kỹ thuật viên phân biệt bẫy nước, ống thông hơi, tắc đường thoát hoặc nguồn ngoài khu vệ sinh; nếu không có bằng chứng thì giữ diagnosis `unknown`. Work order ghi điểm kiểm tra, phép thử được SOP cho phép, kết quả và tình trạng trước xử lý. Không dùng kết quả RAG để khẳng định nồng độ khí hoặc an toàn sức khỏe.

## Hậu kiểm
Ghi việc đã làm, thử thoát và quan sát mùi theo thời gian do SOP phê duyệt, thời điểm và người xác nhận. Nếu mùi tái xuất hiện, ảnh hưởng nhiều căn hoặc nguồn chưa chắc, mở review/điều tra mở rộng; không đóng sự cố chỉ vì lúc kiểm tra không còn mùi. Thiếu evidence thì `NEEDS_EVIDENCE`, chẩn đoán xung đột thì `HUMAN_REVIEW`.

## Tình huống phân nhánh
- Mùi thoát nước từng lúc: hỏi vị trí, thời gian, điểm thoát ít sử dụng, nhiều căn cùng bị hay không; không suy ngay bẫy nước khô hoặc tắc ống.
- Mùi nghi khí gas, chóng mặt, khó thở hoặc trào nước thải: không gộp vào ca mùi cống thông thường; chuyển người trực khẩn theo quy trình an toàn phù hợp.
- Mùi quay lại sau vệ sinh: so khớp ticket cũ, lịch sự cố hệ thống chung và điều kiện xuất hiện; không lấy kết luận cũ thay khảo sát mới.

## Hồ sơ tối thiểu và hậu kiểm
Ghi khu vực phát mùi, thời điểm, tần suất, ảnh/ghi chú nếu có, triệu chứng sức khỏe và phạm vi nhiều căn. Asset có thể là siphon, điểm thoát hoặc tuyến chung nhưng phải xác định trước khi tác nghiệp. Kỹ thuật viên ghi kết quả khảo sát, nguyên nhân được xác minh, hạng mục đã xử lý, điều kiện thử theo SOP, chứng cứ trước/sau và kế hoạch theo dõi. Mùi không cảm nhận được tại một thời điểm không chứng minh nguồn đã xử lý. Không khuyên cư dân đổ hóa chất hoặc tự mở đường cống.

## Nguồn
- MOCK-PROC-09-v1: fixture thiết kế từ technical-data/ISSUE_CATALOG.md mục 09 và docs/teams/quang/general.md; không phải văn bản BQL.
