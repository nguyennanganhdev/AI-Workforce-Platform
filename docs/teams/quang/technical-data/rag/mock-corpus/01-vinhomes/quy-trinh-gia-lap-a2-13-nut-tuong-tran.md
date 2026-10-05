---
trang_thai: du-lieu-gia-lap-khong-xuat-ban
cap_nhat: 2026-10-05
van_ban: MOCK-PROC-13-v1
issue_code: TECH.ARCH.CRACK
fixture_only: true
approval_status: not_published
sop_available: false
audience: technician_test_only
version: mock-v1
---
# MOCK-PROC-13 — Quy trình mẫu: nứt tường hoặc trần

MẪU GIẢ LẬP cho POC A2; không phải SOP Vinhomes và không chứng nhận an toàn kết cấu.

## Intake và đánh giá khẩn
Ghi vị trí, chiều/hướng vết nứt, ảnh có thước và captured_at, thời điểm đầu/tái phát, dấu rò/ẩm và ảnh hưởng cửa. Phân biệt số cư dân ước lượng với số kỹ thuật viên đo. Trần võng, vật liệu rơi hoặc vết phát triển nhanh thì chuyển người có chuyên môn; `area_restriction.request` và `vendor_dispatch.request` chỉ ở trạng thái `PENDING_APPROVAL`, không phải đã phong tỏa/đặt thợ.

## Thu thập chứng cứ
Kỹ thuật viên ghi width/length theo vị trí, unit, thiết bị, measured_at/by và ảnh cùng mốc; có thể lặp ở thời điểm sau để theo dõi. Tra hồ sơ cấu kiện/hoàn thiện đúng building, lịch sử và SOP có hiệu lực. Không kết luận nứt kết cấu hay chỉ thẩm mỹ từ ảnh hoặc ngưỡng đo tự đặt. Khi thiếu hồ sơ cấu kiện hoặc các nguồn đo mâu thuẫn, yêu cầu chuyên gia xác nhận bằng văn bản.

## Xử lý và nghiệm thu
Work order/assignment chỉ định phạm vi đánh giá trước phạm vi sửa; kết quả ghi chẩn đoán đã được chuyên gia/nhân viên phù hợp xác nhận, biện pháp đã duyệt, số đo trước/sau và theo dõi. Ảnh vá/sơn không chứng minh cấu kiện an toàn. Nếu thiếu đánh giá chuyên môn bắt buộc, `technical.verify_resolution` trả `HUMAN_REVIEW`; thiếu ảnh/số đo trả `NEEDS_EVIDENCE`. Không tự hạ mức khẩn hay đóng ticket.

## Tình huống phân nhánh
- Vết nứt nhỏ được phát hiện: ghi vị trí, chiều/đường đi và ảnh có mốc thời gian; không chẩn đoán nứt kết cấu chỉ từ ảnh.
- Nứt mở rộng nhanh, trần võng, rơi vật liệu hoặc cửa bị biến dạng cùng lúc: chuyển người trực/đơn vị chuyên môn công trình ngay, hạn chế tiếp cận; không chờ đủ ảnh.
- Nứt gần vệt ẩm: liên kết ca thấm, giữ hai giả thuyết tách biệt cho tới khi khảo sát.

## Hồ sơ tối thiểu và hậu kiểm
Ghi sơ đồ vị trí, tầng, các mốc ảnh, biến đổi theo thời gian, điều kiện xung quanh và người quan sát. Cần chuyên gia có quyền xác định hạng mục kết cấu hay hoàn thiện trước khi ra phương án; kỹ thuật viên thông thường không tự tuyên bố an toàn kết cấu. Phép đo nếu có cần phương pháp, đơn vị, dụng cụ, thời điểm và người đo. Hồ sơ sửa lớp phủ không thay thế đánh giá nguyên nhân. Hậu kiểm yêu cầu quyết định của người có thẩm quyền và lịch theo dõi phù hợp; không dùng kích thước nứt giả lập làm ngưỡng an toàn.

## Nguồn
- MOCK-PROC-13-v1: fixture thiết kế từ technical-data/POC_WORKFLOWS.md POC 4 và ISSUE_CATALOG.md mục 13; không phải văn bản BQL.
