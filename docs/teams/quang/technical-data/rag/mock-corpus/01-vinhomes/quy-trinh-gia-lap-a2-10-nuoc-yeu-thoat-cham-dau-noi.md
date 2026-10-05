---
trang_thai: du-lieu-gia-lap-khong-xuat-ban
cap_nhat: 2026-10-05
van_ban: MOCK-PROC-10-v1
issue_code: TECH.PLUMB.SUPPLY_DRAIN_JOINT
fixture_only: true
approval_status: not_published
sop_available: false
audience: technician_test_only
version: mock-v1
---
# MOCK-PROC-10 — Quy trình mẫu: nước yếu, thoát chậm hoặc rò đầu nối

MẪU GIẢ LẬP cho POC; không phải SOP Vinhomes. Ba nhóm triệu chứng này phải được tách trong assessment dù cùng một issue code.

## Intake và phạm vi
Ghi nhánh `low_supply`, `slow_drain` hoặc `joint_leak`, điểm xuất hiện, thời điểm, một thiết bị hay nhiều căn, mức nước lan và ảnh. Hỏi nước bẩn/trào, nước gần điện, rò liên tục hay mất nước diện rộng; có nguy cơ thì chuyển người trực. Không gộp “nước yếu” vào chẩn đoán tắc cống, hoặc coi “rò đầu nối” là cùng nguyên nhân với outage.

## Đối chiếu dữ liệu
`technical.get_active_outage` kiểm tra nước cấp chung đúng thời điểm; `asset.read` xác định vòi/ống/đầu nối, ownership và lịch sử. Kỹ thuật viên đo áp lực/lưu lượng nếu SOP yêu cầu, có metric, unit, measured_at/by và thiết bị; phép thử thoát phải được ghi riêng. Kiểm tra điểm nối và nguồn rò theo manual; nếu nhiều asset khớp, hỏi thêm location/model thay vì tự chọn. Cô lập nguồn dùng request và approval phù hợp.

## Work order và kết quả
Work order phải có diagnosis cụ thể và repair scope đúng nhánh triệu chứng. Executor result ghi bộ phận/vật tư, phép thử trước/sau tương ứng và evidence đúng ticket. Nước cấp đạt không chứng minh thoát tốt; nước thoát tốt không chứng minh đầu nối khô. `technical.verify_resolution` kiểm tra từng tiêu chí, thiếu một nhánh trả `NEEDS_EVIDENCE`; nguồn chung/riêng mâu thuẫn trả `HUMAN_REVIEW`.

## Tình huống phân nhánh
- Nước cấp yếu: hỏi một vòi, cả căn hay nhiều căn; đối chiếu lịch cấp nước và cảm biến hợp lệ đúng tòa, không suy lỗi vòi.
- Thoát chậm: ghi điểm thoát, thời điểm, có trào ngược và mùi nước thải không; trào ngược chuyển nhánh nguy cơ vệ sinh.
- Đầu nối rò: ghi vị trí ướt, gần điện không, phần cấp hay thoát; không đề nghị siết thử khi chưa xác định vật tư và quyền.

## Hồ sơ tối thiểu và hậu kiểm
Ba triệu chứng phải là ba nhánh chẩn đoán riêng trong ticket dù cùng mã issue; ghi nguồn cấp, vị trí thoát và asset/ownership của đầu nối. Dữ liệu cảm biến stale hoặc quality bad không chứng minh áp lực hiện tại. Kỹ thuật viên ghi phép đo áp lực/lưu lượng, thời gian thoát hoặc điểm rò theo phương pháp được duyệt, đơn vị, người đo và hình ảnh. Hậu kiểm đối chiếu từng triệu chứng ban đầu; xử lý một nhánh không tự hoàn tất hai nhánh còn lại. Thiếu xác nhận nguồn hoặc phạm vi building thì chuyển đánh giá người.

## Nguồn
- MOCK-PROC-10-v1: fixture thiết kế từ technical-data/ISSUE_CATALOG.md mục 10 và docs/teams/quang/general.md; không phải văn bản BQL.
