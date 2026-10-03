# Resident auth UI

Module chỉ dành cho app cư dân. Không import/sửa component, route, hook hoặc
service auth của `app/` (nhân viên). Tất cả CSS bắt đầu bằng `resident-auth`;
không có rule global cho button/input/body.

## Route và hành vi

- `/login`: điện thoại + mật khẩu, hiện/ẩn mật khẩu, liên kết quên mật khẩu/đăng ký.
- `/register`: họ tên, điện thoại, mật khẩu, nhập lại mật khẩu.
- `/forgot-password`: nhập điện thoại để đề nghị khôi phục.
- `#/profile`: có đường dẫn vào đăng nhập/đăng ký.
- Auth có layout riêng, không render sidebar hoặc bottom navigation của trợ lý.
- Nút “Khám phá bản trải nghiệm” mở `/#/` và đánh dấu chế độ UI mẫu trong sessionStorage; đây không phải thao tác đăng nhập.
- Mở app chưa chọn trải nghiệm đưa về `/login`; trang hồ sơ có nút thoát trải nghiệm.
- Các trang được chọn tại `src/main.tsx`, bên ngoài `App` cư dân; chuyển trang bằng URL riêng và bỏ dữ liệu form đang nhập.
- URL cũ `#/login`, `#/register`, `#/forgot-password` chuyển sang URL mới tương ứng.
- Khi deploy, cấu hình hosting trả `index.html` cho `/login`, `/register`, `/forgot-password` để mở trực tiếp hoặc tải lại trang hoạt động (Vite đã hỗ trợ khi phát triển).

## Trạng thái tích hợp

Đây là UI và validation, **chưa phải xác thực production**. App demo vẫn truy cập
được ở `#/` sau khi chủ động chọn trải nghiệm. Không tạo tài khoản, gửi OTP, đặt cookie, lưu password/token hoặc giả
chấp nhận credentials. Adapter hiện tại chủ động báo “chưa kết nối” khi submit hợp lệ.
Validation frontend chỉ hỗ trợ nhập liệu, không thay thế validation/rate limit phía server.

`auth-service.ts` định nghĩa port `ResidentAuthService` để BE/FE kết nối sau này.
`AuthPage` nhận service qua prop để test/thay adapter. Không đoán các endpoint từ mẫu UI.
Kết quả đăng nhập/đăng ký gồm `nextStep`: `verification-required`, `membership-pending`, `ready`.
Hai trạng thái đầu hiển thị giao diện hướng dẫn; `ready` gọi `onAuthenticated` nếu có.
Nếu chưa có callback, không tự chuyển vào dữ liệu demo. Chi tiết tại [tài liệu auth UI](../../../docs/04-auth-ui.md).
Callback success trong form chỉ dành cho adapter thật; trước khi bật adapter cần làm
session bootstrap, profile thật và membership, không chuyển user thật vào dữ liệu demo.

## Quy tắc form

- Điện thoại: 10 chữ số bắt đầu bằng 0; chấp nhận `+84` và các dấu cách phân tách,
  chuẩn hóa tại boundary. BE phải chốt định dạng chuẩn lưu trữ/E.164.
- Đăng ký: tên 2–100 ký tự sau trim; mật khẩu 8–128 ký tự, xác nhận trùng khớp.
- Đăng nhập: mật khẩu bắt buộc, tối đa 128 ký tự; không áp chính sách đăng ký mới cho
  mật khẩu của tài khoản cũ. Không trim/normalize mật khẩu.
- Nút submit khóa khi pending; ref chặn double submit trước khi React render lại.
- Lỗi theo field sau blur/submit; focus field lỗi đầu tiên; lỗi adapter có `role=alert`.
- Mật khẩu chỉ ở React state, không vào URL, localStorage, sessionStorage hoặc log.

## Team BE cần chốt

1. Provider đăng nhập bằng điện thoại/mật khẩu và việc dùng lại Better Auth server.
2. OTP xác minh số điện thoại, khôi phục mật khẩu, giới hạn thử và chống enumeration.
3. Cookie/session, CSRF, CORS và logout; dùng HttpOnly cookie nếu contract chọn session cookie.
4. Tạo tài khoản khác với cấp membership căn hộ; đăng ký không tự cấp quyền cư dân.
5. Response đăng ký/khôi phục phải mô tả bước tiếp theo; bổ sung màn OTP nếu contract yêu cầu.
6. Hoàn thiện `GET /me`, cô lập cache/draft theo user và xóa dữ liệu nhạy cảm khi logout.

Không tự thêm HTTP API vào OpenAPI domain chỉ vì đã có form. Identity thuộc hệ thống
auth chung; API cư dân tiếp tục kiểm tenant/membership của caller ở server.
