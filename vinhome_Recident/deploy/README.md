# Đóng gói domain Vinhomes

Năm container: `api`, `reception`, `resident`, `operations`, `field`. Hai app web build từ cùng một recipe, hai cổng của app nhân viên dùng chung một image.

| Container | Image build từ | Cổng mặc định | Ghi chú |
|---|---|---|---|
| `migrate` | cùng image với `api` | không | Job một lần: tạo/cập nhật schema rồi dừng. |
| `api` | `services/vinhomes-api/Dockerfile` | 8000 | Backend nghiệp vụ; chờ `migrate` xong. |
| `reception` | `agents/reception/Dockerfile` | 4202 (nội bộ) | Agent lễ tân; gọi `api`. |
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
- ở `field`, mọi địa chỉ ngoài `/operations` chuyển về `/operations/my-tasks`.

## Những gì compose không làm

- **Không khởi động kho S3.** Khai báo `S3_*` trỏ tới dịch vụ có sẵn.
- **Không khởi động PostgreSQL**, nhưng có job `migrate` chạy trước API: tạo schema trong database trống hoặc nâng database cũ. Nó dùng `MIGRATION_DATABASE_URL` (chủ database); API chạy bằng role riêng không có quyền vượt RLS (`VINHOMES_API_DATABASE_URL`), tạo một lần bằng `python -m vinhomes_api.database role`.
- **Không có dịch vụ tri thức.** Đặt `RECEPTION_KNOWLEDGE_URL` khi đã có; để trống thì Reception không trả lời câu hỏi thông tin từ nguồn nào.

## Build riêng từng image

```powershell
docker build -f deploy/Dockerfile.web --build-arg APP=resident-web -t vinhomes-domain-resident .
docker build -f deploy/Dockerfile.web --build-arg APP=staff-web    -t vinhomes-domain-operations .
docker build -t vinhomes-domain-api       services/vinhomes-api
docker build -t vinhomes-domain-reception agents/reception
```

Lệnh `docker build` của hai app web chạy từ thư mục gốc `vinhome_Recident` (context cần thấy `package-lock.json` và `packages/`). Image web cài dependency bằng `npm ci` theo workspace nên chỉ tải gói của app đang build.
