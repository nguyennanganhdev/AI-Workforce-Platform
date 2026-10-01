# Luồng tài khoản — phạm vi FE/UI

Hai nhóm người dùng có giao diện riêng. Không import component/CSS/service auth chéo giữa hai app.

| Nội dung | Resident | Operations |
|---|---|---|
| URL đăng nhập | `http://localhost:3011/login` | `http://localhost:3020/operations/login` |
| Tạo tài khoản | Cư dân tự đăng ký tại `/register` | Admin cấp; không có đăng ký công khai |
| Định danh UI | Số điện thoại | Tài khoản được cấp (BE chốt mã nhân viên hay email) |
| Hỗ trợ | `/forgot-password` | Hướng dẫn liên hệ quản trị viên trên trang login |
| Trải nghiệm | Chủ động bấm “Khám phá bản trải nghiệm” | Chủ động bấm “Xem bản trải nghiệm” |

## Resident

Mở app khi chưa chọn trải nghiệm đưa về login. Đăng ký gồm họ tên, số điện thoại,
mật khẩu, xác nhận mật khẩu; không có chọn vai trò và không tự cấp quyền căn hộ.

Adapter `ResidentAuthService` nhận/trả view model FE, không phải HTTP contract đã chốt:

```ts
type ResidentAuthResult = {
  nextStep: "verification-required" | "membership-pending" | "ready";
};
```

- `verification-required`: hiển thị cần xác minh; chưa tự khẳng định đã gửi OTP/email.
- `membership-pending`: hiển thị chờ xác nhận thông tin cư dân và liên kết căn hộ.
- `ready`: gọi callback `onAuthenticated` do lớp tích hợp cung cấp để bootstrap phiên thật.
  Nếu chưa truyền callback, UI báo chưa kết nối phiên, không mở dữ liệu mẫu như đăng nhập thật.
- Reset mật khẩu dùng thông báo chung nếu adapter thành công, không xác nhận số điện thoại tồn tại.

Mặc định adapter chưa kết nối và luôn báo lỗi rõ ràng, không có tài khoản nào được tạo.
Password chỉ tồn tại trong state của form; được xóa khi chuyển trang/trả trạng thái tiếp theo.

Hai URL phục vụ review giao diện trạng thái, luôn có nhãn xem trước:

- `/account-status?preview=verification-required`
- `/account-status?preview=membership-pending`

Không lấy query string này làm trạng thái thực của user. Khi tích hợp, trạng thái do server trả về.

## Chế độ trải nghiệm và phiên thật

Cờ `resident.ui-preview` / `operations.ui-preview` nằm trong sessionStorage của tab,
chỉ dùng mở UI mock; không phải token. Hai app vẫn giữ dữ liệu mẫu riêng và có nút thoát trải nghiệm.
Thoát trải nghiệm không xóa lịch sử demo; chức năng đặt lại dữ liệu vẫn riêng biệt.

Phiên thật, hết hạn phiên, đăng xuất thật, xác minh OTP, membership và quyền nhân viên
cần contract BE trước khi nối. Khi nối BE, thay entry/guard demo bằng bootstrap phiên,
giữ lỗi mạng khác với chưa đăng nhập và không gán admin khi API lỗi.

Chi tiết nhân viên: [Operations auth](../../app/src/features/vinhomes-operations/auth/README.md).
Admin tạo/duyệt/khóa/xóa hồ sơ đã có UI mẫu tại `/operations/accounts`, xem [05-workspace-fe-handoff.md](05-workspace-fe-handoff.md). Cấp tài khoản thật và đổi mật khẩu lần đầu vẫn cần backend.
