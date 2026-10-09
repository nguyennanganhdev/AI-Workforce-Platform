# Tài khoản nhân viên — FE/UI

## Quy tắc sản phẩm

- Nhân viên chỉ đăng nhập bằng tài khoản admin cấp; không có đăng ký công khai.
- `/operations/login` là route công khai, nằm ngoài layout và guard `_authed`. Ngoài chế độ trải nghiệm, nó chuyển về trang đăng nhập chung `/login` của app cư dân (`login-url.ts`); trang này chỉ còn hiện form khi bật `VITE_ENABLE_UI_PREVIEW`.
- Form dùng nhãn “Tài khoản được cấp”; mã nhân viên/email chỉ là gợi ý UI, BE cần chốt định danh.
- Quên mật khẩu/chưa được cấp tài khoản mở hướng dẫn liên hệ quản trị viên. Chưa gửi yêu cầu hoặc OTP.
- Có validation, hiện/ẩn mật khẩu, pending, sai thông tin, bị khóa và lỗi kết nối.
- Nhân viên không chọn quyền khi đăng nhập thật. Bộ chọn tài khoản trong khu vực trải nghiệm chỉ phục vụ review UI; sidebar hiển thị vai trò đã cấp, không cho đổi persona.

## Phạm vi hiện tại

`auth-service.ts` là adapter FE, mặc định luôn báo chưa kết nối khi submit hợp lệ.
Không lưu tài khoản, mật khẩu, token hoặc giả lập đăng nhập thành công. Adapter không có hàm register.
Component nhận `service` qua prop để kiểm thử các phản hồi khác nhau.

Nút “Xem bản trải nghiệm” ghi cờ `operations.ui-preview` vào sessionStorage của tab,
mở workspace mock. Banner luôn ghi dữ liệu mẫu; “Thoát trải nghiệm” xóa cờ và trở về login.
Guard này chỉ điều hướng bản UI, không phải lớp bảo mật hay phiên đăng nhập production.
Không dùng cờ preview để truy cập API có xác thực.

Guard Operations không còn gọi `/api/me` để tự lấy admin demo khi backend lỗi.
Gói này không còn trang `/sign` của OpenBot: mọi đăng nhập đi qua `/operations/login`.

## Bàn giao BE / bước tích hợp tiếp theo

1. Chốt định danh và API đăng nhập; map mã lỗi sang `StaffAuthError` để có nội dung UI phù hợp.
2. Cung cấp phiên thật, hồ sơ, quyền/menu và bộ phận. Thay profile/persona mock bằng thông tin server xác nhận.
3. Khi đăng nhập thành công, bootstrap phiên và đưa người dùng về trang được cấp quyền.
   Hiện UI chỉ thông báo thiếu tích hợp phiên nếu một adapter thử nghiệm trả thành công; không tự mở demo.
4. Khi backend yêu cầu đổi mật khẩu lần đầu, bổ sung màn tương ứng. Không suy đoán mọi tài khoản đều cần bước này.
5. Khi phiên hết hạn, điều hướng về login; khi logout, gọi API kết thúc phiên và xóa cache riêng của user.
6. Backend kiểm tra quyền trên từng API. Ẩn menu phía FE không thay thế kiểm quyền server.

Màn admin tạo/duyệt/khóa/xóa hồ sơ mẫu đã có ở `/operations/accounts`; tài khoản thật vẫn cần API provisioning.
Trang `/admin/people` hiện tại chưa phải flow cấp tài khoản bằng mật khẩu.

## Kiểm tra

- `npm test -w @vinhomes/staff-web -- operations-auth`
- `node apps/staff-web/scripts/auth-browser-smoke.ts` khi hai FE chạy và Chrome debug profile riêng ở 9333.
- `npm run typecheck -w @vinhomes/staff-web` và `npm run build -w @vinhomes/staff-web`.
