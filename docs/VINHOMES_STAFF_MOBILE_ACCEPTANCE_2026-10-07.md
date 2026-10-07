# UI nhân viên, phân việc và hàng đợi — 07/10/2026

## Phạm vi đã hoàn tất

Nhánh `dev_TeamChien`: UI nhân viên trên runtime V3 hiện tại và backend giao việc. Supervisor tách phiếu theo chuyên môn kỹ thuật/vệ sinh; API từ chối giao nhân viên không có chuyên môn tương ứng. UI hiển thị từng work order, chỉ dùng assignment của tài khoản hiện tại và bỏ offer hết hạn/từ chối.

- Việc đang di chuyển, đã đến, chờ duyệt hoặc đang xử lý nằm ở **Đang làm**. Offer mới và việc đã nhận nhưng chưa bắt đầu nằm ở **Hàng đợi**.
- Việc mới đến không làm mất bản nháp đang nhập. Nút “Tiếp tục việc đang làm” dẫn về đúng phiếu. UI và backend cùng chặn bắt đầu hai việc đồng thời.
- Sau hoàn tất/hủy/từ chối, backend thử offer các phiếu Supervisor đang chờ cùng đơn vị/chuyên môn.
- Ảnh trước/sau phải thuộc đúng work order. Ảnh của bộ phận khác trong cùng ticket không mở nút gửi kết quả.
- Phương án đã duyệt cho phép bắt đầu tại hiện trường; báo giá phát sinh phải được duyệt. Báo giá bị từ chối có thể sửa và gửi lại.
- Danh sách và chi tiết phân biệt đã gửi kết quả, chờ cư dân, hoàn tất và đã hủy. Phiếu hủy không hiện nhầm cư dân đã xác nhận.
- Mobile: tabs hai cột, tên/nội dung dài xuống dòng, input 16px, mục tiêu chạm 44px, safe area, menu tài khoản và trạng thái tải/mất kết nối/thử lại.

**Sức chứa hàng đợi:** `max_concurrent_jobs` hiện giới hạn tổng phiếu còn giữ chỗ (offer/đã nhận), còn khóa bắt đầu đảm bảo chỉ một phiếu đang thực hiện. Tài khoản có sức chứa 1 sẽ không nhận offer thứ hai khi đang làm; phiếu mới chờ ở hàng đợi phân công. Muốn giao trước một phiếu tiếp theo vào hàng đợi cá nhân, tài khoản cần sức chứa ít nhất 2. Không thay đổi hàng loạt cấu hình nhân sự trong commit này.

## Nghiệm thu

Ca Docker local `9ffb9b9f-2b52-5b4d-960a-f545b29ef6ac`:

| Thành phần | Kết quả |
| --- | --- |
| Supervisor | Gọi Agent Kỹ thuật A2 và Agent Vệ sinh & Cảnh quan; tạo hai phiếu khác chuyên môn |
| Kỹ thuật | Phiếu `40f9f158-bacf-4cff-9413-ae8bf58b18fc`, `completed` |
| Vệ sinh | Phiếu `e4c12ad6-0232-4491-9bad-a83e89b3a064`, `completed` |
| Cư dân | Hai `customer_completion` đều `approved` |
| Ticket / phiên | `closed` / `completed` sau BQL duyệt đóng |

Kỹ thuật được offer tự động; vệ sinh lúc đầu giữ `queued` vì đầy sức chứa. Để chạy cùng ca UI, giao đúng nhân viên vệ sinh demo qua API BQL với sức chứa tăng tạm. Ca hàng đợi cũng dùng sức chứa demo tăng tạm. Sau thử đã khôi phục hai tài khoản về 1 và hủy các fixture phụ; không sửa hoặc hoàn tất việc cũ. Ảnh là synthetic: kiểm chứng quy trình phần mềm, không chứng minh thi công ngoài hiện trường.

- Backend coordination/staff dispatch: **24 tests PostgreSQL pass** trên database tách biệt ở lượt nghiệm thu.
- UI field sau rà soát cuối: **15 pass, 81 assertions**; UI connected/auth: **6 pass, 37 assertions**. Chạy hai nhóm trong tiến trình riêng để tránh xung đột fixture happy-dom.
- TypeScript và build Operations pass. API/Operations/Resident chạy Docker local.
- Chi tiết hàng đợi và hai màn báo cáo: kiểm tra `320×740`, `375×812`, `390×844`, `768×1024`, `844×390`; không tràn ngang và các nút/link/input nhìn thấy đạt tối thiểu 44px. Lượt nghiệm thu không ghi nhận lỗi JavaScript.
- Kiểm tra trước commit: form `QuoteForm` thật render riêng với CSS từ build Operations, thêm vật tư và kiểm tra cả light/dark tại năm viewport trên; 10 cấu hình đạt kích thước chạm và không tràn ngang. Điều hướng bàn phím tới tiền công đúng. Kiểm tra live điều hướng và giữ bản nháp qua polling đạt; không ghi nhận lỗi JavaScript.
- Lint của `connected/field` và `layout/field-shell.tsx` pass. Các file UI dùng chung vẫn còn lỗi lint tại các đoạn có sẵn (dependency reset theo route, nút legacy, array index key và label của form BQL); không gọi lint toàn frontend là pass.

Bằng chứng local đầy đủ: [STAFF_UI_ACCEPTANCE.md](../.codex-artifacts/staff-mobile-20261007/STAFF_UI_ACCEPTANCE.md), cùng JSON, log và screenshots trong `.codex-artifacts/staff-mobile-20261007/`. Thư mục artifact bị Git ignore; báo cáo này đi cùng commit để giữ kết quả và giới hạn.

## Còn thiếu so với đặc tả nghiệp vụ

Luồng V3 đã nghiệm thu không đồng nghĩa hoàn tất toàn bộ [đặc tả nhân viên](vinhomes-operations-staff-field-flow.md):

1. **Kỹ thuật:** checklist, chữ ký sau sửa, snapshot/báo cáo bất biến, tự hoàn tất sau 72 giờ và xử lý yêu cầu làm lại trong mốc này chưa nối vào runtime V3.
2. **Vệ sinh/cảnh quan:** đặc tả có luồng riêng (biển cảnh báo trước lau, tạm dừng/xin hỗ trợ, hoàn tất ngay khi gửi; không chờ cư dân/72 giờ). Ca V3 hiện dùng xác nhận cư dân cho cả hai phiếu; chưa coi là tuân thủ đầy đủ luồng riêng đó.
3. **Offline:** có cảnh báo mất mạng và giữ bản nháp khi polling; chưa có lưu bền vững ảnh/checklist/chữ ký và đồng bộ sau khi khôi phục kết nối.
4. **Điều phối:** chưa có scheduler thử offer lại theo hết hạn/chuyển ca; retry đang chạy theo sự kiện hoàn tất/hủy/từ chối. Lượt sửa phương án thử đầu bị runtime dừng `model_unavailable`, chẩn đoán tại thời điểm thử chỉ ra giới hạn budget; lỗi nhãn/budget ngoài phạm vi commit này.
5. **Môi trường:** chưa triển khai hoặc nghiệm thu production. Luồng Supervisor đã duyệt chuyển kết quả cho cư dân; ca này không chứng minh một bước QC độc lập đã đạt.

Các mục trên cần triển khai và nghiệm thu riêng; không bật cơ chế ký/tự đóng chỉ bằng UI khi backend chưa bảo đảm hợp đồng dữ liệu và chuyển trạng thái.
