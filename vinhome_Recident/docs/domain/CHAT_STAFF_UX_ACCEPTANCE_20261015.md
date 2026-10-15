# Chat cư dân và giao diện staff — nghiệm thu UX ngày 15/10/2026

Phạm vi: Domain trên nhánh `dev_Vinhome`; không thay backend nghiệp vụ, schema, quyền MCP, provider/model hoặc mã Platform. Dùng karpathy-guidelines và ui-ux-pro-max, giữ ngôn ngữ thiết kế Vinhomes hiện có.

## Thay đổi

- Chat dùng tiêu đề hội thoại thực tế; bỏ nhãn và lời chào lặp trong hội thoại đã có tin nhắn. Mở hội thoại tại phần cuối, giữ hành vi theo dõi tin mới khi người dùng chưa cuộn lên đọc lịch sử.
- Nội dung, ảnh và thẻ quyết định là phần chính. Nguồn, đoạn trích, trạng thái xác nhận/tham khảo, latency và hoạt động được giữ trong mục thu gọn “Nguồn & chi tiết”; không hiển thị suy luận nội bộ của model.
- Giữ trạng thái “Đã gửi/Đã phản hồi”; không tự tuyên bố người nhận đã đọc. Thông báo, xóa/khôi phục hội thoại và các thẻ phương án/hoàn thành giữ luồng hiện có.
- Chỉ hiện “Xem tiến độ” khi hội thoại có yêu cầu liên kết; mở trực tiếp đúng yêu cầu, không gọi thêm Agent. Biểu mẫu tiếp tục chỉ hiện khi luồng Reception đề nghị.
- Ô gửi có khóa chống gửi đồng thời, phản hồi khi đang gửi, giữ text/ảnh khi lỗi và hỗ trợ gửi lại. Không xóa nội dung đang soạn khi gửi thất bại. Mục đính kèm/sao chép/mở chi tiết đủ vùng bấm; chữ trong ô nhập 16px trên mobile.
- Staff có tìm kiếm theo nội dung/vị trí cho mọi danh sách dài, đếm kết quả và xóa tìm kiếm khi không tìm thấy. Hàng đợi/đang làm ưu tiên khẩn cấp trước; cùng mức ưu tiên dùng thời điểm cập nhật, lịch sử theo cập nhật gần nhất.
- Danh sách staff hai cột trên desktop, một cột trên mobile. Chi tiết tách khu vực thao tác và thông tin công việc trên desktop; giữ một luồng dọc trên mobile. Nhận việc/ETA/từ chối/phương án/ảnh trước-sau/nghiệm thu giữ nguyên contract và điều kiện nghiệp vụ.
- Khóa các trường báo cáo/lý do khi đang lưu. Chỉnh mô tả luồng nghiệm thu sang bộ phận điều phối; không thêm bước duyệt BQL trong Domain.

## Kiểm tra

- **169 kiểm thử frontend đạt:** 44 resident, 125 staff. Bộ resident bao gồm chat, citations, gửi lỗi/gửi trùng, thông báo, archive, approval, booking, quote, recovery và auth. Bộ staff bao gồm toàn bộ 21 file kiểm thử hiện có.
- Một kỳ vọng auth cũ còn cho BQL vào `/operations/kanban`, trái quyết định đã bỏ role này. Thay ca giả lập đó bằng ca backend từ chối tài khoản BQL và frontend hiển thị lý do, không tiếp tục tải session/profile. Không thay logic auth production trong đợt này.
- Typecheck và build production cả hai app đạt; build tắt demo backend/UI preview.
- Chrome headless: **20 tổ hợp màn hình/kích thước** cho chat, danh sách staff, nhận việc và đang xử lý; 375×812, 390×844, 768×1024, 1280×900, 812×375. Không tràn ngang, không lỗi JavaScript; kiểm tra thu gọn/mở nguồn, tìm theo căn hộ, vùng bấm chat và mở hội thoại ở tin cuối. Có kiểm tra với reduced motion.
- Fixture UI riêng, chặn gọi API và mạng ngoài; **0 API nghiệp vụ, 0 Agent/model thật**. Fixture đã chuyển ra ngoài workspace; không đóng gói vào production. Ảnh và bằng chứng ở `E:\Vinhomes-Deploy\ui-audit-20261015`.

## Docker và triển khai

Tag frontend: **`ux-chat-staff-20261015-101b920d2b48`**.

- Resident image: `sha256:2e8889d8fbd8c704c25697556d25e9c8d0a0fcc42dfbbc9ade9bf9f36ad9e6a8`.
- Staff image: `sha256:317d44e123f496d078a88c8709e5d663c9eb186ce240dfbda25a92a9cd565f4e`.
- Đã cập nhật hai frontend trên local `http://localhost:8080` và VPS `https://vinhome-platform.duckdns.org`; hai container healthy.
- Đối chiếu **31 file resident + 58 file staff** trong từng môi trường với bundle đã build: khớp. HTML công khai `/`, `/login`, `/operations/` trên cả hai môi trường HTTP 200, hash khớp image mới.
- Sao lưu env/tags trước thay đổi; chỉ recreate resident/operations và reload gateway. Backend, PostgreSQL/MinIO, scheduler/platform-sync, Reception, backup giữ nguyên container và cấu hình. Không ghi/chuyển database hoặc tạo tài khoản test.
- Bằng chứng VPS: `/opt/vinhomes/releases/ux-chat-staff-20261015-101b920d2b48/`.

Nghiệm thu này chứng minh UI, contract giả lập và artifact đã triển khai; không thay thế nghiệm thu hội thoại Agent thật, gửi ảnh/ticket tới Platform thật hoặc thiết bị mobile thật. Giữ nguyên trạng thái cấu hình tích hợp hiện có.

## Git

Giữ riêng 5 thay đổi có từ trước: `.gitignore`, `platform_VP/agentscope/examples/web_ui/frontend/package.json`, `platform_VP/agentscope/examples/web_ui/pnpm-lock.yaml`, việc xóa `vinhome_Recident/deploy/Caddyfile` và `vinhome_Recident/docs/domain/PLATFORM_OWNED_SERVICE_ACCEPTANCE_20261014.md`. Không đưa chúng vào commit UX này.
