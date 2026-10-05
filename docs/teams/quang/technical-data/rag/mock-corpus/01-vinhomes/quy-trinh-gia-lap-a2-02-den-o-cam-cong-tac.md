---
trang_thai: du-lieu-gia-lap-khong-xuat-ban
cap_nhat: 2026-10-05
van_ban: MOCK-PROC-02-v1
issue_code: TECH.ELEC.FIXTURE_FAILURE
fixture_only: true
approval_status: not_published
sop_available: false
audience: technician_test_only
version: mock-v1
---
# MOCK-PROC-02 — Quy trình mẫu: đèn, ổ cắm, công tắc không hoạt động

MẪU GIẢ LẬP chỉ cho kiểm thử nội bộ; không phải SOP Vinhomes hay hướng dẫn cư dân sửa điện.

## Tiếp nhận và chặn nguy cơ
Ghi đúng vị trí điểm hỏng, trong căn hay khu chung, một điểm hay cả nhánh, thời điểm bắt đầu và thiết bị khác bị ảnh hưởng. Hỏi về nóng, cháy xém, tiếng nổ, tia lửa, nước/ẩm gần điểm điện và đèn thoát hiểm. Khi có dấu hiệu điện nguy hiểm hoặc lối thoát thiếu chiếu sáng, chuyển người trực và bảo đảm quy trình an toàn khu vực do nhân viên thực hiện; không bảo cư dân tháo mặt ổ hoặc thử dây.

## Khảo sát và quyết định
Đối chiếu outage, bản đồ mạch nếu được cấp quyền, asset fixture/panel và lịch sử sửa. Nếu nhiều điểm cùng mất thì mở incident phạm vi chung; nếu chỉ một fixture thì ghi asset riêng. Kỹ thuật viên được phân công kiểm tra theo SOP/manual đúng loại thiết bị, ghi phép đo hợp lệ nếu SOP đòi hỏi; kết quả đo không có người/thiết bị/đơn vị là không hợp lệ. Việc cô lập điện hoặc hạn chế lối đi phải qua yêu cầu phê duyệt, không suy rằng đã thực thi khi trạng thái còn pending.

## Kết quả và evidence
Executor result phải chỉ ra điểm lỗi đã xác nhận, bộ phận được sửa/thay, checklist an toàn, ảnh trước/sau có quyền đọc và thử chức năng sau xử lý. Nếu đèn thoát hiểm liên quan, cần người có quyền nghiệm thu khả năng sử dụng lối thoát; ảnh bóng sáng đơn lẻ không đủ. Thiếu bằng chứng trả `NEEDS_EVIDENCE`; nguyên nhân chưa khớp kết quả hoặc vùng ảnh hưởng chưa được xử lý trả `HUMAN_REVIEW`. Không đóng ticket tự động.

## Tình huống phân nhánh
- Một đèn không sáng: hỏi lỗi chỉ ở bóng, phòng hay nhiều ổ; ghi thời điểm và trạng thái CB. Không đoán bóng hỏng.
- Ổ nóng, sẫm màu, có tia lửa hoặc mùi khét: chuyển người trực ngay; không đề nghị chạm, tháo ổ hay cắm thiết bị khác để thử.
- Lỗi tái phát sau sửa: liên kết work order cũ để đối chiếu, nhưng hồ sơ cũ không thay thế chứng cứ của lần này.

## Hồ sơ tối thiểu và hậu kiểm
Ghi nhãn/vị trí asset, triệu chứng cụ thể, có người bị điện giật hay không, ảnh tự nguyện và thời điểm. Xác minh owner, quyền vào căn, manual/SOP và vật tư phù hợp trước công việc. Người được giao ghi nguyên nhân được kiểm chứng, kết quả đo, mã vật tư, ảnh trước/sau cùng ticket. Hậu kiểm phải tách triệu chứng ban đầu, thao tác thực hiện và kết quả thử theo SOP. Nếu vẫn nóng, vẫn mùi khét, thiếu đo hoặc cư dân báo tái phát thì chuyển đánh giá người, không đóng ticket.

## Nguồn
- MOCK-PROC-02-v1: fixture thiết kế từ docs/teams/quang/general.md mục 10 và technical-data/ISSUE_CATALOG.md mục 02; không phải văn bản BQL.
