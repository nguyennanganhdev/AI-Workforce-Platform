# Chạy Resident và Operations với backend V3

> **Cập nhật:** mặc định hai frontend từ chối backend demo và tắt preview. Dùng [hướng dẫn/trạng thái kết nối thật](../../docs/TRANG_THAI_KET_NOI_THAT_2026-10-01.md) và `services/CHAY_KET_NOI_THAT.cmd`. Các lệnh bên dưới là hướng dẫn **demo local trước đây**, không phải triển khai thật đã hoàn tất.

Trạng thái ngày 01/10/2026: luồng ticket cốt lõi đã nối PostgreSQL local; các giới hạn được ghi trong [báo cáo triển khai](../../docs/BAO_CAO_TRIEN_KHAI_2026-10-01.md).

## Cài và khởi động

Từ repository root, Python >=3.11, Bun và Docker Linux engine:

```powershell
py -3.11 -m venv services/vinhomes-api/.venv
services/vinhomes-api/.venv/Scripts/python.exe -m pip install -e './services/vinhomes-api[test]'
bun install --frozen-lockfile
powershell -ExecutionPolicy Bypass -File services/vinhomes-api/scripts/setup_demo_database.ps1
```

Setup tạo database riêng `vinhomes_v3` trên 5544, migration bằng ledger `server/drizzle`, tài khoản fixture và cấu hình trong `.local-v3-faker` đã gitignore. Chạy setup một lần; những lần sau dùng `docker compose -p vinhomes-faker-v3 -f services/vinhomes-api/docker-compose.demo.yml up -d --wait`, không cần seed lại.

Mở ba terminal:

```powershell
powershell -ExecutionPolicy Bypass -File services/vinhomes-api/scripts/start_demo.ps1
```

```powershell
bun run dev:resident
```

```powershell
bun run dev:operations
```

- Resident: http://127.0.0.1:3011/
- Operations: http://127.0.0.1:3020/operations
- OpenAPI: http://127.0.0.1:8000/docs
- Readiness: http://127.0.0.1:8000/ready

Hai Vite proxy `/api/business/*` tới FastAPI 8000 (bỏ prefix); `/api/*` còn lại tới platform 3001. Biến đổi target: `VINHOMES_API_URL`, `PLATFORM_API_URL` (resident); Operations giữ `SERVER_PORT` cho platform.

## Thử luồng

1. Resident: Chat mới → Lập phản ánh → chọn căn hộ, Technical, mô tả/vị trí/contact, ảnh → Kiểm tra nội dung → Gửi phản ánh.
2. Operations local chọn Ban quản lý → chọn cùng mã ticket → tiếp nhận/tạo phiếu → chọn nhân viên → phân công.
3. Chọn Nhân viên kỹ thuật → nhận việc → di chuyển → đến hiện trường → nhập phương án ở Ghi chú → gửi phương án cho cư dân.
4. Resident mở yêu cầu và đồng ý phương án.
5. Nhân viên bắt đầu xử lý → upload bằng chứng → gửi kết quả.
6. BQL nghiệm thu đạt. Khi tất cả phiếu đạt, resident nhận quyền xác nhận.
7. Resident xác nhận hoàn tất hoặc nêu lý do làm lại. Hai phía đọc lại cùng ID trên database.

Chọn identity ở Operations chỉ xuất hiện khi `/health` báo backend demo. Không dùng header demo cho xác thực production. Màn preview localStorage cũ vẫn qua nút trải nghiệm ở login.

## Kiểm thử

```powershell
$env:VINHOMES_INTEGRATION_URL='http://127.0.0.1:8000'
services/vinhomes-api/.venv/Scripts/python.exe -m pytest services/vinhomes-api/tests -q
bun run --cwd resident-app build
bun run --cwd app typecheck
bun run --cwd app build
bun run --cwd server db:verify
```

Integration test ghi fixture vào database local demo; không chạy trên môi trường production. Các request đi qua role runtime có RLS. Lệnh không có `VINHOMES_INTEGRATION_URL` sẽ skip test database.

## Đấu môi trường thật

Tắt `VINHOMES_API_DEMO_MODE`, bỏ `VINHOMES_API_DEV_USER_ID`. Cấu hình URL database runtime (không bypass RLS), tenant UUID và `VINHOMES_API_AUTH_URL` tới session endpoint platform đáng tin cậy; endpoint trả `{user:{id}}`. Reverse proxy phục vụ auth và business API cùng origin để cookie session được gửi đúng. Cấu hình `VINHOMES_API_ALLOWED_ORIGINS` theo các origin frontend được phép, phân cách bằng dấu phẩy.

Không trỏ auth URL tới endpoint single-user development tự cấp admin. Cần tài khoản active, tenant membership, unit_residents verified và scoped roles/assignments hợp lệ. Tài khoản chưa có căn hộ không được tự gán căn mẫu. Cần bổ sung cấu hình storage production trước khi nghiệm thu ảnh phía nhân viên. Form phone/OTP chưa được nối; sử dụng SSO/platform hoặc hoàn tất provider phone theo quyết định triển khai.

Contract đang chạy được sinh từ FastAPI tại `/openapi.json`; các tài liệu 01–06 là đề xuất/handoff cũ, không dùng tên endpoint trong đó để suy ra API đang tồn tại. API thực dùng `/resident/chats`, `/resident/tickets`, `/resident/approvals`, `/operations/me`, `/tickets`, `/work-orders`… dưới proxy `/api/business` của frontend.
