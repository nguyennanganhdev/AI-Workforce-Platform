# Chạy Resident và Operations với backend V3

## Chế độ kết nối

Chuẩn bị database, tổ chức và tài khoản quản trị theo [HUONG_DAN_CHAY_API_BACKEND.md](../backend/HUONG_DAN_CHAY_API_BACKEND.md); có launcher [CHAY_KET_NOI_THAT.cmd](../../services/vinhomes-api/launchers/CHAY_KET_NOI_THAT.cmd). Tài khoản local nằm trong cấu hình ignored, không đưa mật khẩu vào tài liệu/Git.

Từ repository root, sau khi cài dependencies:

```powershell
npm run dev:resident
npm run dev:operations
```

Chạy mỗi frontend trong một terminal. Chế độ đăng nhập thật dùng `VITE_ALLOW_DEMO_BACKEND=false`; không chọn tài khoản preview để xác thực.

| Bề mặt | Địa chỉ development |
|---|---|
| Resident và đăng nhập chung | `http://127.0.0.1:3011/` (`/login`) |
| Operations | `http://127.0.0.1:3020/operations` |
| FastAPI / Swagger | `http://127.0.0.1:8000/docs` |

Đăng nhập một lần ở `http://127.0.0.1:3011/login`: cư dân vào app cư dân, staff và admin được chuyển sang `http://127.0.0.1:3020/operations`. Dùng nhất quán `127.0.0.1` hoặc `localhost` cho cả hai ứng dụng; cookie không dùng chung giữa hai hostname này. Hai Vite frontend proxy `/api/business/*` tới FastAPI8000 và bỏ prefix. Production cần gateway cùng origin cho cookie/session; Vite proxy không tự tồn tại trong built app. Triển khai thật dùng nginx trong [deploy/](../../deploy/README.md).

Docker chính dùng `http://localhost:8080`; VPS dùng `https://vinhome-platform.duckdns.org`. `/` là landing page, `/login` là trang đăng nhập chung, `/resident` là ứng dụng cư dân và `/operations/` là ứng dụng staff/admin. Khi logout hoặc hết phiên từ Operations, trình duyệt phải tải tài liệu mới của `/login`, không chỉ đổi route bên trong SPA staff. Danh sách tài khoản hiện tại nằm trong thư mục ignored `deploy/runtime-access-20261015/clean-data/`; không dùng lại danh sách sandbox cũ để suy ra quyền của Docker chính/VPS.

## Nguồn contract và cách kiểm

API đang chạy được sinh từ FastAPI tại `/openapi.json`; source ở `services/vinhomes-api/src/vinhomes_api/v3_*` và các module auth/runtime liên quan. Resident gọi `/resident/chats`, `/resident/tickets`, `/resident/approvals`; Operations gọi `/operations/me`, `/tickets`, `/work-orders` qua prefix proxy.

Luồng mục tiêu: cư dân mô tả → Reception đóng gói ticket và ảnh → outbox bàn giao Platform → Platform giao việc qua MCP → staff nhận/ETA, cập nhật tiến độ, phương án và bằng chứng → Platform tổng hợp → cư dân tự quyết định chi phí, xác nhận hoàn thành hoặc yêu cầu xử lý lại. Không có bước BQL duyệt tiếp nhận ticket thông thường ở Domain. Các điều kiện nghiệp vụ đặc thù và quyền cư dân vẫn được Domain kiểm tra.

Kiểm ID, quyền và trạng thái từ backend; không dùng thành công của preview làm bằng chứng database. Kiểm thử offline dùng database riêng cùng model/transport giả để kiểm tra đóng gói, retry, quyền và sự kiện; kết quả đó không chứng minh Platform thật đã nhận hoặc Agent thật hiểu mọi cách diễn đạt. Theo phạm vi hiện tại, chưa nghiệm thu lại kết nối/key Platform; bridge VPS giữ tắt. Xem [dữ liệu hiện hành](../domain/OPERATING_DATA_NORMALIZATION_ACCEPTANCE_20261016.md) để biết nguồn, số lượng và giới hạn xác nhận vận hành. Các báo cáo nghiệm thu theo ngày là bằng chứng lịch sử, không thay thế trạng thái runtime hiện tại.

Demo fixture chỉ dành cho development, xem [backend README](../../services/vinhomes-api/README.md). Không chạy setup/seed hoặc write-integration tests lên DB đang có dữ liệu vận hành. Preview và backend demo là hai chế độ khác nhau.
