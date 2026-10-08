# Hướng dẫn chạy Vinhomes API backend

Hướng dẫn này dành cho nhánh `dev_TeamChien-beHuy` và chạy trên PowerShell. Service dùng FastAPI, Python 3.11 trở lên và mặc định lắng nghe tại `127.0.0.1:8000`.

## 1. Lấy code và cài thư viện

Tại thư mục gốc repository:

```powershell
git switch dev_TeamChien-beHuy
git pull
cd services/vinhomes-api
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -e .
```

Nếu PowerShell không cho chạy `Activate.ps1`, có thể gọi trực tiếp `.\.venv\Scripts\python.exe` thay cho `python` ở các lệnh tiếp theo.

## 2. Mở Swagger để xem API

```powershell
python -m vinhomes_api
```

Mở <http://127.0.0.1:8000/docs>. Tài liệu OpenAPI dạng JSON ở <http://127.0.0.1:8000/openapi.json>. Có thể đổi cổng bằng `$env:VINHOMES_API_PORT = "8001"` trước khi chạy; khi đó dùng `/docs` trên cổng mới.

Trang Swagger và `GET /health` có thể hoạt động khi chưa kết nối database. Điều đó **không** có nghĩa các API nghiệp vụ đã sẵn sàng. Dừng service bằng `Ctrl+C`.

## 3. Cấu hình để gọi API nghiệp vụ

Cần một PostgreSQL chứa schema V3 của dự án và các migration trong `server/drizzle`, gồm `0001_vinhomes_operations.sql` và `0002_vinhomes_qc_redo.sql`. Nếu cần áp dụng migration của server, cấu hình `DATABASE_URL` trong file `.env` ở thư mục gốc, cài Bun và dependencies của repository, rồi chạy từ thư mục gốc:

```powershell
bun install
bun run --filter server db:migrate
```

Không chạy Alembic `vh_*` của service này trên database V3; đó là các migration legacy không được `main.py` sử dụng.

Trong PowerShell chạy service, đặt các biến môi trường phù hợp với database của bạn:

```powershell
$env:VINHOMES_API_DATABASE_URL = "postgresql+asyncpg://USER:PASSWORD@HOST:5432/DATABASE_V3"
$env:VINHOMES_API_TENANT_ID = "UUID_TENANT_V3"
$env:VINHOMES_API_AUTH_URL = "http://127.0.0.1:3001/api/me"
python -m vinhomes_api
```

Có thể dùng `VINHOMES_API_TENANT_KEY` thay cho `VINHOMES_API_TENANT_ID` nếu triển khai đang dùng khóa tenant tương ứng. `VINHOMES_API_AUTH_URL` phải trỏ đến endpoint `/api/me` của platform đang chạy để xác thực phiên đăng nhập. Tài khoản cần có quyền phù hợp trên tenant và database role của API cần quyền truy cập các bảng V3.

Để thử cục bộ trên loopback, có thể dùng ID của một user V3 đang hoạt động thay cho `VINHOMES_API_AUTH_URL`:

```powershell
Remove-Item Env:VINHOMES_API_AUTH_URL -ErrorAction SilentlyContinue
$env:VINHOMES_API_DEV_USER_ID = "USER_ID_V3"
python -m vinhomes_api
```

Chỉ dùng **một** trong hai cách xác thực. `VINHOMES_API_DEV_USER_ID` chỉ được chấp nhận khi host là `127.0.0.1`, `localhost` hoặc `::1`; quyền của user vẫn được kiểm tra trong database.

## 4. Kiểm tra sau khi chạy

Mở lần lượt:

- <http://127.0.0.1:8000/health>: process đang chạy nếu trả `status: ok`.
- <http://127.0.0.1:8000/ready>: database và các bảng V3 cần thiết đã sẵn sàng nếu trả `status: ready`. HTTP 503 nghĩa là thiếu cấu hình, không kết nối được database hoặc thiếu migration.
- <http://127.0.0.1:8000/docs>: chọn endpoint, bấm **Try it out** rồi **Execute** để thử API.

Nếu `python -m vinhomes_api` báo thiếu module, kiểm tra đã kích hoạt `.venv` và chạy `python -m pip install -e .` trong `services/vinhomes-api`. Nếu cổng 8000 đã được sử dụng, đặt `VINHOMES_API_PORT` sang cổng khác.
