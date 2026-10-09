# Resident auth UI

Module chỉ dành cho app cư dân; không import staff UI/auth. CSS dùng prefix `resident-auth`.

## Adapter hiện tại

`auth-service.ts` dùng `identityMode: email`, gọi `/api/business/auth/login`, `/auth/session`, `/auth/register`, `/resident/me` với cookie (`credentials: include`). Trường TypeScript `phone` được giữ vì interface cũ; trong connected mode UI nhận email. Backend kiểm membership/căn hộ; không lấy role hoặc tenant từ form làm quyền.

Kết quả: `membership-pending`, `verification-required`, `ready` hoặc `administration`. Đăng ký không tự cấp quyền cư dân; admin được điều hướng sang Operations. Reset mật khẩu chưa kết nối, không báo đã gửi mã. Preview là lựa chọn riêng, không dùng làm fallback khi API lỗi.

## Quy tắc cần giữ

- Không trim/normalize mật khẩu; không đưa vào URL, localStorage, sessionStorage hoặc log.
- Khóa submit khi pending, chặn double submit; validation/focus/error do form xử lý.
- Bootstrap session/profile từ backend, cô lập dữ liệu theo user và xóa cache khi logout.
- Membership/căn hộ verified và quyền tài nguyên do backend quyết định; cookie/session không thay nghiệp vụ authorization.
- Production cần gateway/origin/cookie policy phù hợp và cơ chế reset/rate-limit được nghiệm thu.

Đối chiếu implementation và tests trong thư mục này.
