# Đóng gói domain Vinhomes

Năm container: `api`, `reception`, `resident`, `operations`, `field`. Hai app web build từ cùng một recipe, hai cổng của app nhân viên dùng chung một image.

| Container | Image build từ | Cổng mặc định | Ghi chú |
|---|---|---|---|
| `api` | `services/vinhomes-api/Dockerfile` | 8000 | Backend nghiệp vụ. Cần PostgreSQL đã migrate. |
| `reception` | `agents/reception/Dockerfile` | 4202 (nội bộ) | Agent tiếp nhận cư dân; gọi `api`. |
| `resident` | `deploy/Dockerfile.web` với `APP=resident-web` | 3011 | nginx: file tĩnh và `/api/business` → `api`. |
| `operations` | `deploy/Dockerfile.web` với `APP=staff-web` | 3020 | Ban quản lý và quản trị viên. |
| `field` | cùng image với `operations` | 3023 | Nhân viên hiện trường; chỉ các trang `/operations`. |

## Chạy

```powershell
cd deploy
copy deployment.env.example deployment.env     # điền giá trị; file này không được commit
docker compose --env-file deployment.env up -d --build
```

Thiếu biến bắt buộc thì compose dừng ngay và nêu tên biến. Chỉ in tên biến khi kiểm tra, không in giá trị.

## Một image, hai cổng đăng nhập

`operations` và `field` chạy cùng image. Biến `VINHOMES_SURFACE` do nginx điền vào lúc khởi động quyết định hai điều:

- nginx gửi `X-Vinhomes-Surface` tới API với giá trị đó (và bỏ giá trị trình duyệt tự gửi), để API giữ một phiên đăng nhập riêng cho mỗi cổng;
- ở `field`, mọi địa chỉ ngoài `/operations` chuyển về `/operations/my-tasks`, và `/api/` của nền tảng trả 404.

## Những gì compose không làm

- **Không có job migration.** Schema database V3 do `server/drizzle` của nền tảng tạo; database phải được chuẩn bị trước, và `VINHOMES_API_DATABASE_URL` trỏ tới nó bằng một role có quyền hạn chế.
- **Không khởi động dịch vụ nền tảng** mà API gọi: Supervisor (`COORDINATION_URL`), tìm kiếm tri thức (`KNOWLEDGE_URL`), tool host (`TECHNICAL_TOOLS_URL`), lịch chạy (`ROUTINES_URL`), agent factory (`FACTORY_URL`), kho S3 (`S3_ENDPOINT`). Đặt địa chỉ của chúng trong `deployment.env`, hoặc nối project này vào network nơi chúng đang chạy.
- **`PLATFORM_API_URL`**: API của nền tảng mà tab "Yêu cầu hệ thống" của Ban quản lý đọc. Không đặt thì tab đó báo lỗi tải, phần còn lại vẫn chạy.

## Build riêng từng image

```powershell
docker build -f deploy/Dockerfile.web --build-arg APP=resident-web -t vinhomes-domain-resident .
docker build -f deploy/Dockerfile.web --build-arg APP=staff-web    -t vinhomes-domain-operations .
docker build -t vinhomes-domain-api       services/vinhomes-api
docker build -t vinhomes-domain-reception agents/reception
```

Lệnh `docker build` của hai app web chạy từ thư mục gốc `vinhome_Recident` (context cần thấy `package-lock.json` và `packages/`). Image web cài dependency bằng `npm ci` theo workspace nên chỉ tải gói của app đang build.
