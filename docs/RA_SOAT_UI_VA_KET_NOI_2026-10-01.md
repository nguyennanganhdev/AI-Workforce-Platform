# Rà soát UI và kết nối backend/PostgreSQL — 01/10/2026

Kết nối local hoạt động; UI và toàn bộ flow nghiệp vụ chưa hoàn chỉnh.


## Rà soát toàn bộ nhóm màn hình sau phản hồi CSS

### Lỗi giao diện đã xác nhận và sửa

Ảnh màn đăng ký có gradient, icon, input và nút theo CSS gốc; không phải mất toàn bộ stylesheet. `AuthPage.tsx` còn khối `.auth-notice` được chèn từ luồng platform cũ, chứa chữ đã hỏng dấu trong source và link `localhost:3010/sign`. Khối này không có style tương ứng ở form hiện tại. Đã xóa khối cũ khỏi cả login/register/forgot-password, đổi icon trường email sang phong bì, sửa hướng dẫn khôi phục và không render form gửi mã khi backend chưa hỗ trợ. Giữ thiết kế và breakpoint CSS gốc.

Đã tái hiện bằng test render form đăng ký: assertion không có link 3010 thất bại trước sửa và đạt sau sửa. Bổ sung test cả ba route auth để lỗi không quay lại. Không chỉ dựa vào HTTP 200 để kết luận UI đúng.

### Phạm vi kiểm tra và giới hạn

- Kiểm tra source của nhóm màn cư dân và toàn bộ 18 đường dẫn Operations (kể cả login), CSS/import, API được gọi, nhánh fallback/preview và guard.
- Resident và Operations trả HTTP 200; stylesheet auth, Operations, workspace và stylesheet chính đều trả 200. Đây chỉ là bằng chứng Vite phục vụ tài nguyên, không chứng minh mọi màn đã render và thao tác đúng.
- CUA trả `apps=[]`, `browsers=[]`; chưa thể kiểm tra ảnh chụp desktop/mobile, overflow, focus và tương tác bằng trình duyệt thật. Không đánh dấu visual QA hoàn tất.
- Quét source không tìm thêm khối chữ hỏng cùng dạng với khối platform đã xóa trong hai nhóm UI được kiểm tra; không coi quét regex là kiểm chứng mọi bản dịch.

### Ma trận màn hình

| Màn hình | Kết nối hiện có | Chưa hoàn tất |
| --- | --- | --- |
| Cư dân `/login`, `/register` | Form/CSS gốc → password API → PostgreSQL; trạng thái chờ duyệt/xác minh | Kiểm tra trình duyệt thật; liên kết căn hộ từ dữ liệu vận hành |
| Cư dân `/forgot-password` | Màn hướng dẫn hỗ trợ, không giả báo gửi mã | Dịch vụ reset, token hết hạn và kênh gửi |
| Cư dân chờ duyệt/xác minh | Hiển thị theo session membership hoặc thiếu căn hộ verified | Quy trình gửi hồ sơ, duyệt và xác minh căn hộ |
| Cư dân trợ lý/hội thoại | Tạo/đọc/gửi chat, đọc cursor, upload ảnh qua API | Chưa có AI provider thật; chưa có push; bản nháp ở RAM |
| Cư dân yêu cầu/chi tiết | Ticket, timeline, ảnh, yêu cầu đồng ý sửa chữa/xác nhận kết quả | Chưa nghiệm thu trọn luồng với cư dân có căn hộ thật |
| Cư dân thông báo | Tin chưa đọc hội thoại và cập nhật tổng hợp từ danh sách yêu cầu | Chưa dùng `/my/notifications` và API đánh dấu đã đọc; không phải đầy đủ thông báo hệ thống |
| Cư dân hồ sơ | User/căn hộ đọc PostgreSQL | Điều khiển đổi mật khẩu/đăng xuất chưa gắn vào UI gốc; chỉnh hồ sơ/liên kết căn hộ |
| Cư dân tòa nhà | Tên dự án/tòa từ căn hộ | Danh bạ BQL, giờ làm việc, tài liệu nội quy chưa nối |
| Cư dân tiện ích | Màn danh mục chưa công bố | Các ô bể bơi/phòng tập/công viên ở trang tiện ích vẫn là mục điều hướng cố định; chưa có danh mục/đặt lịch thật |
| Operations login | UI gốc → login + `/operations/me`; chuyển màn theo quyền server | Quản lý phiên/đổi mật khẩu trên UI gốc; reset |
| Operations tổng quan | Component gốc, tổng hợp ticket/work order/approval/catalog | Không phải bộ KPI vận hành đầy đủ; số phiếu completed chưa tương đương hàng chờ QC độc lập |
| Operations triage/incidents | Dùng danh sách gốc với bộ lọc và panel thao tác API | Chưa phục hồi đầy đủ workspace phân loại/incident chuyên biệt |
| Operations kanban/dispatch | Danh sách/bảng tiến độ gốc; chi tiết, tạo phiếu, phân công qua API | Chưa có nhân viên/chuyên môn/ca làm thật; chưa đủ xử lý lỗi từng bước xuyên luồng |
| Operations my-tasks/work-orders/completed-tasks | Công việc và trạng thái từ API, nhận việc/ETA/di chuyển/đề xuất/ảnh | Các màn kỹ thuật chuyên biệt gốc chưa nối; lịch sử hiện dựa vào trạng thái ticket, không phải toàn bộ lịch sử từng phiếu; my-work-orders giới hạn 100 |
| Operations QC | Lọc phiếu completed, nút pass/fail/redo gọi backend | Chưa nối màn kiểm định đầy đủ; tiêu chí đang đơn giản, chưa nghiệm thu độc lập toàn quy trình |
| Operations team | TeamView gốc, API phòng/tin nhắn/agent; chống gửi lặp | Chưa có workspace/phòng/thành viên thật; tạo/cấu hình agent và worker AI chưa triển khai |
| Operations reports | Form gốc; API incident-frequency/issued-revenue và DOCX | Chưa có tòa nhà/hóa đơn để nghiệm thu số liệu; không phải báo cáo tiền đã thu |
| Operations accounts | Tạo/duyệt/đổi quyền/khóa qua PostgreSQL | Chưa tích hợp hết UI quản trị gốc; danh sách tối đa 200; chưa có phân phạm vi chi tiết và hồ sơ nhân viên/căn hộ |
| Operations evidence/approvals/security/sanitation/contractor | Nhánh runtime hiện trả thông báo chưa nối đầy đủ | Cần nối từng màn gốc với API tương ứng; không thể coi route HTTP 200 là đã có chức năng |
| OpenBot ngoài `/operations` | Cơ chế riêng của package `app` | Không nằm trong xác thực password Operations; chưa kiểm thử các màn OpenBot trong đợt này |

### Kiểm tra runtime/database hiện tại

- PostgreSQL `vinhomes_connected`: **1 user**, **1 storage location**.
- `domains`, `sites`, `buildings`, `units`, `unit_residents`, `staff_profiles`, `staff_specialties`, `staff_shifts`, `management_units`, `management_coverage`, `workspaces`, `channels`, `tickets`, `work_orders`: **0 dòng** tại thời điểm rà soát. Đây là lý do danh mục và công việc trống, không phải bằng chứng API không nối.
- Session không cookie qua cả hai proxy trả 401. Đăng nhập admin bằng thông tin cấu hình local trả 200; các endpoint session, me, catalogs, dashboard, tickets, work-orders, rooms, approvals, accounts và resident đọc được (200). Phiên kiểm tra đã đăng xuất.
- Kiểm thử mới: 6 UI + 15 auth/work-items/resident regression đạt; 11 Python đạt, gồm 3 integration HTTP/PostgreSQL thật. Resident typecheck/build đạt. Build Operations đã đạt ở lượt tích hợp trước; đợt sửa này chỉ thay UI auth cư dân và tests.
- Dữ liệu tạm của integration được dọn sau chạy. Chưa tạo danh mục/nghiệp vụ giả làm dữ liệu vận hành.

### Thứ tự công việc tiếp theo

1. **Hoàn thiện vận hành tài khoản:** đổi mật khẩu/đăng xuất trong UI gốc, trạng thái mất phiên nhất quán; giữ reset ở trạng thái chưa hỗ trợ tới khi có kênh gửi thật.
2. **Nhập và quản lý dữ liệu nền:** tenant/dự án/tòa/căn hộ, cư dân verified, đơn vị quản lý/phạm vi, nhân viên/chuyên môn/ca làm, workspace/phòng/thành viên. Cần nguồn dữ liệu thật hoặc màn quản trị cho người dùng tự nhập; không suy diễn địa chỉ và danh tính.
3. **Nghiệm thu một luồng sửa chữa đầy đủ:** cư dân đăng nhập → tạo phản ánh + ảnh → BQL tiếp nhận/tạo phiếu/phân công → nhân viên nhận/đến/đề xuất → cư dân đồng ý → xử lý + bằng chứng → QC → cư dân xác nhận/đóng hoặc yêu cầu làm lại. Kiểm tra ghi DB, phiên bản, quyền ngoài phạm vi và refresh sau từng bước.
4. **Nối thông báo và các màn chuyên biệt:** API thông báo/đã đọc, evidence, approvals, QC đầy đủ, cắt nước, an ninh, vệ sinh, nhà thầu; mỗi màn có tiêu chí nghiệm thu riêng.
5. **Nghiệm thu giao diện bằng browser:** login/register, pending/403/401, empty/error/loading, desktop/mobile; sau đó mới nghiệm thu báo cáo với dữ liệu có đối soát và chuẩn bị HTTPS/backup/storage/AI production.

Không có cơ sở để báo “connect hoàn chỉnh” trước khi hoàn thành mục 2–4 và kiểm tra giao diện ở mục 5.


### Sửa điều hướng admin trên form cư dân

Form cư dân trước đây xét căn hộ cho mọi người dùng nên admin bị hiện xác minh. Session hiện trả cờ `administrator` được truy vấn từ `platform_admins`; admin active đăng nhập qua form cư dân chuyển sang `/operations/accounts`. Local giữ nguyên hostname và chuyển port 3011 → 3020 để cookie phiên tiếp tục dùng được. Deployment khác có thể cấu hình `VITE_OPERATIONS_URL`. Quyền tài nguyên vẫn do API kiểm tra; không tạo căn hộ hay bỏ xác minh cư dân. Kiểm thử hồi quy tái hiện lỗi trước sửa và đạt sau sửa; resident build đạt.
