---
trang_thai: du-lieu-gia-lap-khong-xuat-ban
cap_nhat: 2026-10-05
van_ban: MOCK-PROC-15-v1
issue_code: TECH.ARCH.FLOOR_DAMAGE
fixture_only: true
approval_status: not_published
sop_available: false
audience: technician_test_only
version: mock-v1
---
# MOCK-PROC-15 — Quy trình mẫu: sàn trầy, phồng hoặc bong

MẪU GIẢ LẬP cho kiểm thử; không phải SOP Vinhomes.

## Intake và an toàn lối đi
Ghi loại sàn, diện tích, cạnh vênh/cạnh sắc, nước dưới lớp sàn, tình trạng lún, vị trí trên lối đi và ảnh có mốc. Hỏi người vấp ngã, nước gần điện, rò gần đây; có nguy cơ đi lại hoặc vật liệu rơi thì chuyển người, đề nghị hạn chế khu vực qua approval chứ không tự tuyên bố đã chặn lối đi.

## Chẩn đoán theo vật liệu
Tra asset/vật liệu, bảo hành, lịch sử thấm/rò và manual thi công. Kỹ thuật viên xác định chỉ trầy bề mặt hay mất ổn định/nền ẩm; đo độ phẳng/ẩm theo SOP đúng vật liệu khi cần. Không kết luận “chỉ thẩm mỹ” từ ảnh. Work order ghi điểm lỗi, nguồn ẩm nếu có, phạm vi tháo/sửa đã duyệt, vật tư và evidence trước.

## Nghiệm thu
Executor result có ảnh sau, checklist bề mặt ổn định và không còn cạnh/nguy cơ vấp, số đo theo phương pháp đã duyệt, bằng chứng nguồn ẩm đã xử lý nếu có. Thiếu tiêu chuẩn vật liệu hoặc còn sàn phồng/rò thì `HUMAN_REVIEW`; thiếu ảnh/số đo bắt buộc thì `NEEDS_EVIDENCE`. Người có quyền xác nhận trả lại lối đi, không để agent tự quyết.

## Tình huống phân nhánh
- Gạch lỏng hoặc sàn phồng: hỏi vị trí lối đi, diện tích quan sát, mốc xuất hiện, có tiếng rỗng/ướt không; không kết luận do keo hay nền.
- Mép sắc, gạch vỡ, sàn trơn hoặc nguy cơ vấp ngã: cảnh báo tránh khu vực và chuyển người trực; không yêu cầu cư dân bóc gạch để chụp ảnh.
- Sàn hỏng cùng rò nước: liên kết ticket nguồn nước và quyền khảo sát; sửa bề mặt trước khi xử lý nguồn ẩm có thể tái hỏng.

## Hồ sơ tối thiểu và hậu kiểm
Ghi vật liệu hoàn thiện, vị trí, diện tích, mức cản lối đi, ảnh và owner/bảo hành. Kỹ thuật viên kiểm tra nền, ẩm, vật tư tương thích và phương án theo SOP; công việc có bụi/ồn hoặc ảnh hưởng lối đi phải có phối hợp phù hợp. Ghi vật tư, phạm vi xử lý, evidence trước/sau và thời điểm bàn giao. Hậu kiểm gồm an toàn đi lại, bề mặt ổn định và nguyên nhân ẩm đã được xử lý hoặc theo dõi; không nghiệm thu chỉ vì ảnh trông phẳng.

## Nguồn
- MOCK-PROC-15-v1: fixture thiết kế từ technical-data/ISSUE_CATALOG.md mục 15 và docs/teams/quang/general.md; không phải văn bản BQL.
