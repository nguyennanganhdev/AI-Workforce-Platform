---
trang_thai: du-lieu-gia-lap-khong-xuat-ban
cap_nhat: 2026-10-05
van_ban: MOCK-PROC-05-v1
issue_code: TECH.HVAC.CONDENSATION
fixture_only: true
approval_status: not_published
sop_available: false
audience: technician_test_only
version: mock-v1
---
# MOCK-PROC-05 — Quy trình mẫu: điều hòa chảy nước

MẪU GIẢ LẬP để chạy POC A2; không phải SOP Vinhomes hay hướng dẫn cư dân tự sửa.

## Tiếp nhận và dừng nguy cơ
Ghi asset/model dàn lạnh, nơi nước xuất hiện, thời điểm khi chạy máy, mức lan, ảnh trước và căn dưới nếu có. Hỏi nước gần ổ/đèn, trần võng/rơi, rò lan nhiều căn. Có nguy cơ điện hoặc trần rơi thì chuyển người trực, không chờ ảnh và không yêu cầu cư dân mở dàn lạnh. Trường điện chưa biết giữ `unknown`.

## Điều tra có kiểm soát
Đối chiếu asset, manual đúng model, bảo trì gần nhất, incident thấm trần và outage nước/điện nếu liên quan. Kỹ thuật viên phân biệt nước ngưng từ khay/ống với nguồn thấm khác; chỉ theo SOP hợp lệ mới kiểm tra đường thoát, khay và tình trạng thiết bị. Evidence ảnh trước phải có file/object ID, captured_at, ticket/work order và trạng thái scan/quyền phù hợp. Đo `drain_flow` nếu manual yêu cầu, gồm value, `L/min`, measured_at/by và nguồn thiết bị; LLM không tạo số đo.

## Work order và nghiệm thu
Executor result ghi chẩn đoán xác nhận, checklist, việc làm, vật tư, số đo và ảnh sau. Thử hoạt động theo manual/model và ghi quan sát tại thời điểm thử, bao gồm khu vực từng ướt và căn dưới nếu có quyền kiểm tra. Nước còn gần điện hoặc ảnh chưa sẵn sàng thì không xác minh. Thiếu ảnh/checklist trả `NEEDS_EVIDENCE`; nguồn nước chưa rõ hoặc mâu thuẫn trả `HUMAN_REVIEW`. `VERIFIED` là khuyến nghị, không đóng ticket.

## Tình huống phân nhánh
- Dàn lạnh nhỏ nước: hỏi thời điểm, chế độ vận hành, vị trí chảy và căn dưới có bị ảnh hưởng không; không kết luận tắc ống.
- Nước gần ổ điện hoặc trần võng: chuyển người trực khẩn; không yêu cầu cư dân mở dàn lạnh hoặc tháo trần.
- Rò tái phát sau vệ sinh: đối chiếu work order và model; xem đường thoát, lắp đặt, đọng sương là giả thuyết cần kiểm chứng.

## Hồ sơ tối thiểu và hậu kiểm
Ticket cần vị trí, phạm vi ướt, dấu hiệu điện/trần và ảnh; dữ kiện căn dưới để unknown nếu chưa xác minh. Asset xác định dàn lạnh, model, owner. Kỹ thuật viên ghi khảo sát theo SOP, phép đo có đơn vị/phương pháp và evidence trước/sau đúng ticket. Muốn vào căn khác phải có grant riêng. Hậu kiểm tại điểm rò cũ theo điều kiện/thời gian của SOP thật; số đo fixture không phải chuẩn an toàn. Thiếu ảnh sau, SOP hoặc nguồn nước chưa rõ thì giữ mở.

## Nguồn
- MOCK-PROC-05-v1: fixture thiết kế từ technical-data/POC_WORKFLOWS.md POC 2 và ISSUE_CATALOG.md mục 05; không phải văn bản BQL.
