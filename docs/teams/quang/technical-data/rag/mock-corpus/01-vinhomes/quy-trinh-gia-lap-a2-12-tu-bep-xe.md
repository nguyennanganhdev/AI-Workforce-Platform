---
trang_thai: du-lieu-gia-lap-khong-xuat-ban
cap_nhat: 2026-10-05
van_ban: MOCK-PROC-12-v1
issue_code: TECH.ARCH.CABINET_SAG
fixture_only: true
approval_status: not_published
sop_available: false
audience: technician_test_only
version: mock-v1
---
# MOCK-PROC-12 — Quy trình mẫu: tủ bếp xệ hoặc cánh lệch

MẪU GIẢ LẬP cho kiểm thử A2; không phải SOP Vinhomes hoặc hướng dẫn cư dân tháo tủ.

## Tiếp nhận và an toàn
Ghi tủ treo/đứng, cánh hay toàn thân xệ, vị trí lắp, đồ bên trong, tiếng rạn, liên kết tường và ảnh toàn cảnh/điểm neo. Tủ hoặc cánh có nguy cơ rơi, cạnh sắc hoặc trẻ nhỏ ở gần cần người kiểm tra ngay và giữ người khỏi vùng nguy hiểm; hạn chế khu vực là request chờ duyệt chứ không phải hành động của agent.

## Phân biệt nguyên nhân
Tra bản vẽ/model hoặc hướng dẫn lắp đặt, lịch sử sửa và dấu ẩm/rò quanh tủ. Kỹ thuật viên phân biệt bản lề lệch với cả thân tủ mất neo, nền tường yếu hoặc quá tải. Nếu là hư hỏng điểm neo, không nghiệm thu bằng việc chỉ chỉnh cánh. Work order ghi phạm vi sửa, vật tư/điểm liên kết và người có chuyên môn thực hiện; không dùng số tải giả lập để khẳng định an toàn.

## Kết quả
Executor result lưu checklist điểm neo, thử mở/đóng theo tải và điều kiện được duyệt, ảnh trước/sau. Tiêu chí chịu tải thuộc thiết kế/manual thật; nếu không có, yêu cầu người có thẩm quyền xác nhận. Tủ còn rung/lệch hoặc thiếu ảnh điểm neo thì `NEEDS_EVIDENCE`/`HUMAN_REVIEW`; `VERIFIED` không tự đóng ticket.

## Tình huống phân nhánh
- Cánh tủ xệ: hỏi cánh nào, độ lệch quan sát được, bản lề/ốc rơi chưa, có trẻ nhỏ hoặc đồ nặng bên dưới không; không chỉ định tự siết.
- Tủ treo tách tường hoặc có nguy cơ rơi: chuyển người trực và tránh khu vực; không yêu cầu cư dân đỡ tủ hay tháo đồ trong vùng nguy hiểm.
- Hỏng sau sửa: liên kết work order cũ và xác minh tường/nền neo, model phụ kiện, tải sử dụng bằng chuyên môn; không mặc định lỗi lắp đặt.

## Hồ sơ tối thiểu và hậu kiểm
Ghi vị trí, dạng tủ, ảnh mối nối/cánh/khung, mốc phát hiện và phạm vi nguy hiểm. Asset/owner, điều kiện bảo hành và quyền tiếp cận cần xác minh. Kỹ thuật viên ghi vật liệu nền, loại phụ kiện theo manual, hạng mục xử lý và thử chức năng theo SOP. Không đặt tải trọng thử hoặc loại neo từ fixture. Hậu kiểm gồm ổn định, đóng mở, không còn bộ phận lỏng và evidence sau đúng ticket; thiếu xác nhận nền neo hoặc còn nguy cơ rơi thì giữ mở.

## Nguồn
- MOCK-PROC-12-v1: fixture thiết kế từ technical-data/ISSUE_CATALOG.md mục 12 và docs/teams/quang/general.md; không phải văn bản BQL.
