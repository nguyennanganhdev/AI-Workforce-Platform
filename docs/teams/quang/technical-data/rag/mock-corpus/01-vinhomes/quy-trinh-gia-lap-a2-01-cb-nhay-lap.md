---
trang_thai: du-lieu-gia-lap-khong-xuat-ban
cap_nhat: 2026-10-05
van_ban: MOCK-PROC-01-v1
issue_code: TECH.ELEC.BREAKER_TRIP
fixture_only: true
approval_status: not_published
sop_available: false
audience: technician_test_only
version: mock-v1
---
# MOCK-PROC-01 — Quy trình mẫu: CB nhảy lặp

MẪU GIẢ LẬP để thử RAG và luồng A2; không phải SOP Vinhomes, không được hướng dẫn cư dân thao tác điện. Chỉ mô tả điểm quyết định và hồ sơ mà kỹ thuật viên có thẩm quyền cần ghi.

## Tiếp nhận và điều kiện dừng
Ghi ticket, building đã xác minh, nhánh hay CB tổng, số lần và thời điểm nhảy, thiết bị đang dùng, phạm vi một căn hay nhiều căn. Hỏi rõ khói, tia lửa, mùi khét, vỏ nóng, điện giật và nước gần điện; giá trị chưa biết phải lưu `unknown`. Có bất kỳ dấu hiệu nguy hiểm nào thì chuyển người trực ngay, giữ nguyên hiện trạng và không yêu cầu cư dân đóng CB thử. Nếu chưa có người đủ quyền hoặc chưa xác định asset/ownership thì không mở work order thao tác.

## Kiểm tra có kiểm soát
Người điều phối đối chiếu outage và lịch sử nhánh cấp; `asset.read` xác định panel/CB thuộc căn hay phần chung và model thực tế. SOP/manual đúng asset còn hiệu lực là điều kiện trước khi kỹ thuật viên khảo sát. Kỹ thuật viên ghi nhận tình trạng tại hiện trường, xác nhận phạm vi cô lập qua quy trình phê duyệt riêng nếu cần; công cụ `utility_isolation.request` chỉ tạo yêu cầu chờ duyệt, không cắt điện. Chẩn đoán quá tải, lỗi thiết bị hay lỗi dây phải dựa trên phép đo và biên bản của người có chuyên môn, không suy từ lời kể.

## Work order và xác minh
Work order liên kết ticket, asset, assignment, checklist an toàn, kết quả đo có metric/unit/measured_at/by và evidence trước/sau đúng ticket. `technical.submit_executor_result` ghi việc thực hiện, vật tư và thử chức năng theo SOP đúng model; mọi kết quả thiếu hoặc mâu thuẫn trả `NEEDS_EVIDENCE` hoặc `HUMAN_REVIEW`. `technical.verify_resolution` chỉ khuyến nghị, người có quyền mới xác nhận hoàn tất; không tự đóng ticket. Không gán ngưỡng dòng điện hoặc thời gian thử từ mẫu này.

## Tình huống phân nhánh
- Một CB nhảy khi bật thiết bị: ghi số lần, vị trí CB, thiết bị liên quan và thời điểm; chưa kết luận quá tải hay hỏng dây. Không yêu cầu cư dân bật lại để tái hiện.
- Có mùi khét, tia lửa, vỏ nóng, điện giật hoặc nước gần điện: chuyển người trực ngay, không chờ ảnh và không hướng dẫn thao tác tủ điện.
- Nhiều căn cùng mất điện: đối chiếu outage đúng tòa và sơ đồ cấp điện theo quyền; dữ liệu outage cũ hoặc mâu thuẫn phải được xác minh bởi người trực.

## Hồ sơ tối thiểu và hậu kiểm
Ticket cần nguồn của từng dữ kiện, thời điểm, phạm vi, trạng thái nguy hiểm true/false/unknown. Work order cần asset, model, owner, người được giao và SOP còn hiệu lực. Kết quả khảo sát phải có phép đo kèm metric, unit, measured_at, measured_by, dụng cụ và điều kiện đo; ảnh trước/sau phải đúng ticket và là file đã kiểm tra. Thiếu quyền, SOP, phép đo hoặc kết quả mâu thuẫn thì không xác nhận đã sửa. Thử chức năng và tiêu chí đạt phải lấy từ SOP đúng model; mẫu này không đặt ngưỡng dòng điện hay số lần thử.

## Nguồn
- MOCK-PROC-01-v1: fixture thiết kế từ docs/teams/quang/general.md mục 10.1 và technical-data/POC_WORKFLOWS.md POC 1; không phải văn bản BQL.
