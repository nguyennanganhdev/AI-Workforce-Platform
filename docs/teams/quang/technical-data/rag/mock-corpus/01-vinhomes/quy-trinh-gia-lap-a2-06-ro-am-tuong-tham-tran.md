---
trang_thai: du-lieu-gia-lap-khong-xuat-ban
cap_nhat: 2026-10-05
van_ban: MOCK-PROC-06-v1
issue_code: TECH.PLUMB.CONCEALED_LEAK
fixture_only: true
approval_status: not_published
sop_available: false
audience: technician_test_only
version: mock-v1
---
# MOCK-PROC-06 — Quy trình mẫu: rò âm tường hoặc thấm trần

MẪU GIẢ LẬP cho POC A2, không phải SOP Vinhomes. Không quy trách nhiệm cho căn khác từ vị trí vết ố.

## Intake, phạm vi và nguy cơ
Ghi vị trí, lần quan sát đầu, ảnh theo thời gian, tốc độ lan, dấu trần mềm/võng/rơi, điện quanh vùng ẩm và căn/tầng có thể liên quan. Nước gần điện hoặc thấm nhanh nhiều căn phải chuyển người trực. Ticket chỉ ghi “nguồn chưa xác định” cho đến khi có kết quả kiểm tra; thông tin từ căn lân cận phải được kiểm tra quyền trước khi đọc. Nếu cần vào căn khác, `apartment_entry.request` chỉ trả `PENDING_APPROVAL`, không biểu thị đã được vào.

## Điều tra và quyết định
Đối chiếu incident cùng building, lịch sử ống/nước ngưng/chống thấm, outage, ảnh gốc và vị trí asset. Kỹ thuật viên được phân công ghi phép đo độ ẩm theo điểm đo, unit, thiết bị, measured_at và người đo; so sánh theo cùng phương pháp khi theo dõi. Mọi đề xuất cô lập nước hoặc mở kết cấu cần approval/work order và chuyên môn đúng phạm vi. Nếu hai nguồn thông tin mâu thuẫn, lưu cả provenance và chuyển `HUMAN_REVIEW`, không chọn một nguồn bằng độ giống RAG.

## Hồ sơ xử lý và hậu kiểm
Work order ghi chẩn đoán được xác nhận, ảnh trước, phạm vi can thiệp, vật tư, ảnh sau, số đo sau xử lý và lịch theo dõi tái ẩm. Nếu nguồn liên quan căn khác, evidence chỉ được liên kết khi đúng consent/ACL; quyền bị thu hồi thì không tiếp tục truy cập. Không nghiệm thu chỉ vì đã sơn/che vệt ố. `technical.verify_resolution` yêu cầu bằng chứng xử lý nguồn và không tái rò theo SOP thật; thiếu bằng chứng trả `NEEDS_EVIDENCE`, chưa rõ nguồn trả `HUMAN_REVIEW`.

## Tình huống phân nhánh
- Vệt ố lan theo ngày: lưu ảnh theo thời gian, vị trí, mốc mưa/sử dụng nước; không quy trách nhiệm cho căn trên chỉ từ tương quan.
- Trần võng, nước gần điện hoặc rơi vật liệu: chuyển người trực trước khi đo đạc.
- Cần vào căn liền kề: tạo request đúng căn; pending không phải được phép. Nếu grant bị thu hồi, dừng mọi truy cập liên căn.

## Hồ sơ tối thiểu và hậu kiểm
Ghi sơ đồ vệt, hướng lan, ảnh từng thời điểm và người quan sát. Mỗi phép đo ẩm cần vị trí điểm đo, dụng cụ, đơn vị, thời gian, người đo, điều kiện bề mặt; một phần trăm đơn lẻ không chỉ ra nguồn rò. Tách giả thuyết khỏi facts, giữ cả hai nguồn nếu mâu thuẫn. Work order khảo sát không phải đã sửa. Sau khi nguồn được chuyên môn xác nhận, tách biên bản xử lý nguồn với phục hồi trần/tường và theo dõi tái ẩm; không nghiệm thu sơn khi vẫn thấm.

## Nguồn
- MOCK-PROC-06-v1: fixture thiết kế từ technical-data/POC_WORKFLOWS.md POC 3 và ISSUE_CATALOG.md mục 06; không phải văn bản BQL.
