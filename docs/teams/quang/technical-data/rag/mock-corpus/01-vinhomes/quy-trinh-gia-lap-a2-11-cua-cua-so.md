---
trang_thai: du-lieu-gia-lap-khong-xuat-ban
cap_nhat: 2026-10-05
van_ban: MOCK-PROC-11-v1
issue_code: TECH.ARCH.DOOR_WINDOW
fixture_only: true
approval_status: not_published
sop_available: false
audience: technician_test_only
version: mock-v1
---
# MOCK-PROC-11 — Quy trình mẫu: cửa hoặc cửa sổ lỏng, hở

MẪU GIẢ LẬP cho kiểm thử nội bộ; không phải SOP Vinhomes.

## Intake và chặn nguy cơ
Ghi loại cửa, vị trí, bản lề/khóa/khung/kính liên quan, tình trạng mở đóng, gió/nước lọt, ảnh toàn cảnh và cận cảnh. Hỏi cánh/kính có nguy cơ rơi, người bị kẹt, cửa thoát hiểm/an ninh không sử dụng được. Những trường hợp này cần người trực và đánh giá hạn chế khu vực; `area_restriction.request` chỉ tạo yêu cầu chờ duyệt.

## Khảo sát theo asset
Tra model/phụ kiện, lịch sử sửa, ownership và manual. Kỹ thuật viên xác định điểm lỏng/lệch thật, phân biệt lỗi chốt, bản lề, gioăng, khung hay kính; không siết/chỉnh bộ phận khi chưa rõ tải và liên kết. Work order ghi phạm vi tác động, vật tư đúng loại, tình trạng cấu kiện xung quanh và bằng chứng trước. Nếu cửa là tuyến thoát hiểm, cần quy trình và người nghiệm thu phù hợp, không áp dụng tiêu chí cửa thông thường.

## Kiểm chứng
Ghi thử mở/đóng/khóa theo SOP, kiểm tra liên kết ổn định và độ kín khi có yêu cầu. Evidence sau phải thể hiện đúng cửa và vị trí đã sửa; số đo khe hở chỉ hợp lệ nếu manual quy định phương pháp/giới hạn. Cánh vẫn có nguy cơ rơi hoặc lối thoát chưa dùng được thì `HUMAN_REVIEW`, không tuyên bố an toàn từ một ảnh.

## Tình huống phân nhánh
- Cửa kẹt hoặc khó khóa: hỏi loại cửa, vị trí, thời điểm, có người bị kẹt và lối thoát khác không; không đoán lệch bản lề.
- Cửa sổ lỏng, kính nứt hoặc nguy cơ rơi từ cao: ưu tiên cô lập khu vực và chuyển người trực; không hướng dẫn cư dân tự giữ/kéo thử cánh.
- Nước hắt qua cửa: ghi mưa/gió, điểm xâm nhập, ảnh theo thời điểm và dấu hiệu thấm khác; không tự kết luận ron hỏng.

## Hồ sơ tối thiểu và hậu kiểm
Asset record cần model, cấu hình, tầng/vị trí và owner, đặc biệt nếu thuộc mặt ngoài/tài sản chung. Ghi ảnh khung, cánh, khóa, kính, vị trí ướt và quyền tiếp cận. Kỹ thuật viên theo SOP/manual và quy định làm việc trên cao nếu có, ghi nguyên nhân, vật tư, thử đóng mở/khóa hoặc kín nước theo phương pháp được duyệt. Việc cửa mở được một lần không đủ xác minh nếu vẫn có nguy cơ rơi, kẹt hoặc hở nước. Hậu kiểm bởi người được ủy quyền.

## Nguồn
- MOCK-PROC-11-v1: fixture thiết kế từ technical-data/ISSUE_CATALOG.md mục 11 và docs/teams/quang/general.md; không phải văn bản BQL.
