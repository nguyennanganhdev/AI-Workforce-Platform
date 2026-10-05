---
trang_thai: du-lieu-gia-lap-khong-xuat-ban
cap_nhat: 2026-10-05
van_ban: MOCK-PROC-03-v1
issue_code: TECH.PLUMB.WATER_HEATER
fixture_only: true
approval_status: not_published
sop_available: false
audience: technician_test_only
version: mock-v1
---
# MOCK-PROC-03 — Quy trình mẫu: máy nước nóng không nóng hoặc rò

MẪU GIẢ LẬP cho kỹ thuật viên kiểm thử; không phải SOP Vinhomes. Không hướng dẫn cư dân mở nắp, thử điện, thử gas hoặc tự sửa thiết bị.

## Intake và phân luồng
Ghi model, loại cấp năng lượng, vị trí rò, mã lỗi/đèn báo, không nóng hay nóng yếu, một vòi hay toàn căn, ngày lắp/bảo trì nếu có. Hỏi nước gần điện, mùi gas, khói, vỏ nóng, bỏng hoặc rò mạnh. Dấu hiệu nguy hiểm chuyển người trực và nhân viên có chuyên môn phù hợp; trường chưa rõ lưu `unknown`, không coi là an toàn.

## Xác định nguồn và quyền thao tác
`asset.read` trả đúng model, ownership, bảo hành và manual version; kiểm tra outage điện/nước, lịch sử và sự cố liên quan. Nếu không có manual/SOP đúng model, dừng hướng dẫn kỹ thuật chi tiết và yêu cầu chuyên gia. Kỹ thuật viên xác định điểm lỗi bằng phép kiểm tra được SOP cho phép, phân biệt nguồn cấp, bộ gia nhiệt, van/đường ống và nguồn nước chung. Bất kỳ cô lập nguồn nào phải theo approval thật; request pending không có nghĩa nguồn đã cô lập.

## Hồ sơ hoàn tất
Work order giữ assignment, checklist thao tác an toàn, vật tư đúng model, ảnh trước/sau và số đo nhiệt độ/lưu lượng nếu SOP yêu cầu với đơn vị, người đo và thời điểm. Thử chức năng sau sửa theo điều kiện được phê duyệt; theo dõi điểm rò thay vì chỉ ghi “đã nóng”. Evidence thiếu hoặc mâu thuẫn thì `NEEDS_EVIDENCE`/`HUMAN_REVIEW`; chỉ người được ủy quyền xác nhận kết quả cuối. Không dùng ngưỡng nhiệt độ từ fixture này.

## Tình huống phân nhánh
- Nước không nóng: hỏi model, nguồn cấp, thời điểm bắt đầu, một hay nhiều điểm dùng; không suy ngay bộ gia nhiệt hỏng.
- Rò nước, mùi khét hoặc cảm giác tê điện: chuyển người trực an toàn; không hướng dẫn mở vỏ, sửa điện hoặc vận hành thử.
- Thiết bị thuộc nhà cung cấp/bảo hành: xác minh owner và phạm vi can thiệp; work order có thể là khảo sát hoặc chuyển vendor, không mặc định được sửa.

## Hồ sơ tối thiểu và hậu kiểm
Lưu model/serial nếu có thể cung cấp an toàn, vị trí lắp đặt, dấu hiệu nước/điện, các điểm dùng bị ảnh hưởng. Asset record và hợp đồng xác nhận ai có quyền sửa. Kỹ thuật viên ghi SOP đúng model, quyền cô lập, phép đo hợp lệ, nguyên nhân đã kiểm chứng, vật tư và ảnh trước/sau. Booking vendor ở trạng thái pending không phải lịch đã xác nhận. Chỉ đề xuất hoàn tất khi thử chức năng theo SOP, evidence đúng ticket và người có quyền nghiệm thu; không đặt nhiệt độ hoặc thời gian thử giả định.

## Nguồn
- MOCK-PROC-03-v1: fixture thiết kế từ docs/teams/quang/general.md và technical-data/ISSUE_CATALOG.md mục 03; không phải văn bản BQL.
