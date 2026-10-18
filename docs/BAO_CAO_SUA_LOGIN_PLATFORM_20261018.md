# Sửa lỗi kết nối đăng nhập Platform — 18/10/2026

Đã deploy bản web `c30303184dcc8f6059d66f8e164f8c8439f8bf3b` lên VPS và local. Backend vẫn dùng `d6693197-no-jev-20261017`, giữ nguyên container, thời điểm khởi động và dữ liệu.

Nguyên nhân đã xác nhận trên file JavaScript thực tế được tải qua HTTPS: bản web trước nhúng API mặc định `http://localhost:8000`. Trình duyệt mở `https://vagen-platform.duckdns.org/login` vì vậy gửi request directory/login về máy người dùng và gặp lỗi CORS. Đây là lỗi đóng gói frontend; kiểm tra health backend trước đó chưa phát hiện được. Giá trị `server_url` cũ cũng có thể ghi đè cấu hình bundled frontend.

Bản sửa:

- Build web với `/api`; đặt mặc định Dockerfile và Compose về `/api`.
- Khi bản bundled frontend dùng đường dẫn API tương đối, giữ cấu hình đó thay vì dùng `server_url` lưu từ lần chạy standalone. Bản standalone dùng địa chỉ tuyệt đối vẫn hỗ trợ server riêng.
- Bổ sung test artifact JavaScript đã build; Docker build với `/api` phải qua kiểm tra không nhúng địa chỉ loopback.

Kiểm chứng: 6 test offline đạt; test artifact từ bản lỗi thất bại đúng vì chứa loopback, bản mới đạt. ESLint, TypeScript và production build đạt. Qua HTTPS thật: login 200, đọc tài khoản 200, refresh cookie 200, logout 204. Hash HTML và chunk API đang được phục vụ khớp bản mới; không còn loopback API trong chunk. Kiểm tra lại VPS sau deploy: backend healthy, cả app/web không restart; ổ đĩa còn khoảng 11,57 GB.

Không gọi API model/embedding thật. Chưa thao tác trực tiếp trên trình duyệt người dùng vì không có browser kết nối; kiểm chứng đăng nhập được thực hiện qua HTTP HTTPS, cookie và API thật. Sau khi mở lại trang, dùng Ctrl+F5 để nạp bundle mới.

Release: `E:/AWP-Releases/platform-login-c3030318-20261017`. Gói Docker cập nhật mang tên `AWP-Platform-c3030318-login-fixed-complete.tar`; cần dùng bản này thay gói rollback trước có cấu hình API sai. Env/credential riêng tư không nằm trong gói. Nhánh làm việc `dev_Chien` và các tài liệu đang sửa được giữ nguyên; source fix đã push lên `develop2`.
