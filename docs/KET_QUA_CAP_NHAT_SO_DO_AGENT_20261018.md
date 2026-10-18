# Cập nhật sơ đồ agent, 18/10/2026

Đã phát hành riêng web tại https://vagen-platform.duckdns.org/workforce/agents.

- Worktree: `E:/AI-Workforce-Platform-review`, nhánh `feat/review-plan-20261018`.
- Commit giao diện: `bb292f387e0641acc8d143059c734f34a6b22858`, đã push.
- Image: `agentscope-platform-web:bb292f38-agent-map-20261018`.
- Image config trên VPS: `sha256:d2209eb41894557098a612d2e879cd7c08d17bbc4d7221607b9d13adae55ff1e`.
- Docker Desktop lưu thêm OCI index digest `sha256:f2e95373716a1ed5eb4ef8aade86f804cb9112fb0669c14a73e62c66ff9c271a`; đây là digest khác với image config.
- Kiểm tra HTTPS hoàn tất lúc `2026-10-18T16:20:28Z`.

## Giao diện

- Thay khối màu bằng nhân vật robot 3D nhám, có thiết bị nhận diện vai trò như mũ kỹ thuật, tai nghe và bảng báo cáo. Chân dung trên nhãn dùng cùng bộ asset với danh sách.
- Leader nổi bật; nền sáng và bóng nhẹ; camera căn đội ngũ vừa khung. Nhãn tên và trạng thái đặt dưới nhân vật; số phiếu, chi phí và các đối tác nằm trong bảng chi tiết khi chọn.
- Đường nối dựa trên dữ liệu phối hợp có thật. Bỏ kết nối cư dân/BQL giả và hiệu ứng chạy trên lịch sử khiến người xem hiểu nhầm là agent đang làm việc.
- Có tìm kiếm không phân biệt dấu, lọc trạng thái, bật/tắt nhãn và liên kết phối hợp, căn giữa camera và đặt lại bố cục.
- Giữ chọn giữa sơ đồ/danh sách, mở agent, kéo thả, lưu vị trí và di chuyển bằng phím mũi tên.
- Mobile giữ sơ đồ 3D, mở đội ngũ bằng Sheet và gom thao tác phụ vào Tác vụ. Cue giữ giao diện sáng nhất quán khi hệ điều hành dùng dark mode.
- Render theo nhu cầu; có reduced motion và giao diện dự phòng khi WebGL không khả dụng. Lỗi tải danh sách có nút thử lại.

## Kiểm chứng

- TypeScript, ESLint các file TSX thay đổi và production build đạt.
- 34/34 test frontend đạt; không bỏ qua.
- 17/17 kiểm tra trình duyệt đạt trên chính artifact lấy từ Docker image. Dữ liệu/API đều giả lập, không gọi model.
- Kiểm tra WebGL thật bằng Chromium/SwiftShader tại 1440, 1024, 440 và 390px; chọn hai chiều, kéo nhân vật, phím mũi tên, lưu và đặt lại, tìm/lọc, URL/history, Sheet/Popover mobile, theme và WebGL fallback đều đạt.
- Đã xem lại ảnh desktop/mobile. Không có page/console error; còn cảnh báo deprecation từ Three và bundle lớn có sẵn.
- Docker từ chối tham số lỗi `C:/Program Files/Git/api` trước Vite. Artifact đóng gói nhúng `/api` đúng.
- Qua HTTPS: HTML, renderer và client chunk khớp SHA-256 của image; health và directory trả 200. Refresh không có cookie và đăng nhập bằng thông tin giả trả 401 đúng. Không dùng credential thật để kiểm tra đăng nhập.
- Không có workflow tự chạy cho push nhánh feature này; kết quả trên là kiểm chứng local/image/HTTPS, không được ghi thành CI mới đạt.

## Phạm vi phát hành và phục hồi

Chỉ thay container web. ID, image và StartedAt của app, PostgreSQL, Redis, MinIO và landing được so sánh trước/sau và giữ nguyên. Không đổi Domain, schema, dữ liệu hoặc model key. Cấu hình runtime chỉ cập nhật `WEB_IMAGE`; có khóa deploy và tự quay lại nếu kiểm tra thất bại.

Image trước: `agentscope-platform-web:ff9cf617-review-20261018-fix1`. Đã giữ tag `agentscope-platform-web:rollback-bb292f38-agent-map-20261018`.

Tái sử dụng bản sao lưu bốn kho lúc `2026-10-18T14:36:35Z`, không gọi đây là backup mới. Checksum đạt. Rehearsal độc lập đã xác nhận PostgreSQL, Redis, MinIO và workspace. Kiểm tra Redis đếm tuyệt đối ban đầu trượt do 5 khóa đã hết TTL; lần kiểm tra có xét TTL xác nhận 785 bản ghi vật lý, 780 khóa còn hiệu lực, nội dung/expiry của cả 780 và 481 khóa không hết hạn đều khớp. Giữ nguyên log kiểm tra ban đầu và bằng chứng kiểm tra TTL; không sửa công cụ backup production trong phạm vi này.

Thư mục VPS: `/opt/awp-platform/releases/agent-map-ui-20261018-1608/`.

Quay lại riêng web trên VPS:

```bash
cd /opt/awp-platform/app
sed -i 's|^WEB_IMAGE=.*|WEB_IMAGE=agentscope-platform-web:rollback-bb292f38-agent-map-20261018|' .env
docker compose -p awp-platform --env-file .env -f compose.yaml -f compose.vps.yaml up -d --no-deps --no-build --pull never web
```

Gói local: `E:/AWP-Releases/agent-map-bb292f38-20261018/`, gồm image, source web, manifest, script phát hành/kiểm tra và ảnh cùng kết quả browser QA. Gói không chứa file env hoặc credential.

Kiểm tra này xác nhận giao diện, artifact và kết nối API; không thay thế nghiệm thu nghiệp vụ hay chất lượng trả lời của model. Không gọi model/embedding hoặc gửi tin qua bot/OA để kiểm thử.
