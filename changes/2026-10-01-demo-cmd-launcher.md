# Mở demo API bằng CMD

- Ngày: 2026-10-01
- Yêu cầu: một file CMD khởi động hệ thống giao diện demo API.

## Thay đổi

- Thêm `CHAY_DEMO_API.cmd` tại gốc dự án, gọi script PowerShell điều phối.
- Script khởi động Docker Desktop nếu cần, chờ engine, chạy PostgreSQL bằng Docker Compose, chạy FastAPI ẩn rồi mở `/demo/ui` khi API/database/trang đã sẵn sàng.
- Lần đầu thiếu cấu hình: tạo venv, cài dependency, chạy migration và seed bằng setup hiện có. Các lần thường chỉ chạy container, giữ dữ liệu nghiệp vụ.
- Tái sử dụng API demo đang chạy; từ chối service khác trên cổng 8000. Lỗi giữ cửa sổ CMD để đọc.

## File/module chính

- `CHAY_DEMO_API.cmd` — entry point double-click.
- `services/vinhomes-api/scripts/launch_demo.ps1` — điều phối các service, log API trong thư mục local bị gitignore.
- `my-docs/HUONG_DAN_GIAO_DIEN_DEMO_API_V3.md` — thêm cách mở bằng CMD.

## Quyết định & giả định

- Giao diện demo được FastAPI phục vụ cùng cổng; không cần chạy frontend hoặc Hono riêng.
- Máy cần Docker Desktop/Linux engine; lần đầu cần Python >=3.11, Bun và dependency của server cho migration.
- Không thêm dependency, không reset volume, không commit/push.

## Xác minh

- PowerShell parser: cú pháp hợp lệ. `git diff --check`: thành công (cảnh báo LF/CRLF).
- Chưa chạy thử launcher bằng double-click; không thêm hoặc chạy test.

## Rủi ro / việc còn lại

- Docker/WSL hoặc cổng 8000 có thể chặn khởi động; launcher báo lỗi để xử lý.
- API và database tiếp tục chạy sau khi đóng cửa sổ CMD.
