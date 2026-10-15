# Chạy Vinhomes API

Service dùng FastAPI, Python 3.11 trở lên, mặc định nghe ở `127.0.0.1:8000`. Database là của riêng domain Vinhomes và được dựng bằng công cụ trong gói (xem [deploy/README.md](../../deploy/README.md) và [SPEC_DATABASE_DOMAIN.md](../domain/SPEC_DATABASE_DOMAIN.md)).

## 1. Cài đặt

```powershell
cd services/vinhomes-api
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -e .
```

## 2. Dựng database

Cần một PostgreSQL 16 trở lên. Ba lệnh dưới tạo database trống, áp migration và tạo role runtime (không phải superuser, không bypass RLS):

```powershell
python -m vinhomes_api.database create  --admin-url postgresql://USER:PASSWORD@HOST:5432/postgres --name vinhomes
python -m vinhomes_api.database migrate --url postgresql://USER:PASSWORD@HOST:5432/vinhomes
$env:API_DB_PASSWORD = "mật khẩu mạnh"
python -m vinhomes_api.database role    --url postgresql://USER:PASSWORD@HOST:5432/vinhomes --role vinhomes_api --password-env API_DB_PASSWORD
```

Dữ liệu mẫu (tùy chọn, cần role chủ sở hữu): `python -m vinhomes_api.database seed --url …`. Để có sẵn database demo cục bộ dùng `scripts/setup_demo_database.ps1`; để có database trống kèm quản trị viên đầu tiên dùng `scripts/setup_password_database.py`.

## 3. Chạy service

```powershell
$env:VINHOMES_API_DATABASE_URL = "postgresql+asyncpg://vinhomes_api:PASSWORD@HOST:5432/vinhomes"
$env:VINHOMES_API_TENANT_ID = "UUID_TENANT"
$env:VINHOMES_API_PASSWORD_AUTH = "1"
python -m vinhomes_api
```

Đăng nhập bằng mật khẩu (`VINHOMES_API_PASSWORD_AUTH=1`) là cách dùng thật. Để thử cục bộ trên loopback có thể đặt `VINHOMES_API_DEV_USER_ID` bằng ID của một user đang hoạt động thay cho đăng nhập; cấu hình này bị từ chối nếu service bind ra mạng. Hai cách không dùng chung được.

## 4. Kiểm tra

- <http://127.0.0.1:8000/health>: process đang chạy nếu trả `status: ok`.
- <http://127.0.0.1:8000/ready>: database và các bảng cần thiết đã sẵn sàng nếu trả `status: ready`; HTTP 503 nghĩa là thiếu cấu hình, không kết nối được hoặc thiếu migration.
- <http://127.0.0.1:8000/docs>: Swagger. Có thể đổi cổng bằng `VINHOMES_API_PORT`.
