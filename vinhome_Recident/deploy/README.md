# Đóng gói domain Vinhomes

Sáu container: `api`, `reception`, `resident`, `operations`, `gateway` (và job `migrate`, dịch vụ `scheduler`). Hai app web build từ cùng một recipe. Người dùng chỉ biết **một địa chỉ**, của `gateway`.

| Container | Image build từ | Cổng mặc định | Ghi chú |
|---|---|---|---|
| `migrate` | cùng image với `api` | không | Job một lần: tạo/cập nhật schema rồi dừng. |
| `api` | `services/vinhomes-api/Dockerfile` | 8000 | Backend nghiệp vụ; chờ `migrate` xong. |
| `reception` | `agents/reception/Dockerfile` | 4202 (nội bộ) | Agent lễ tân; gọi `api`. |
| `resident` | `deploy/Dockerfile.web` với `APP=resident-web` | 3011 (nội bộ) | Ứng dụng cư dân và trang đăng nhập chung `/login`. |
| `operations` | `deploy/Dockerfile.web` với `APP=staff-web` | 3020 (nội bộ) | Ban quản lý, quản trị viên và nhân viên hiện trường; mỗi vai trò thấy trang của mình. |
| `gateway` | `nginx` + `nginx/gateway.conf.template` | 8080 | Địa chỉ duy nhất: `/` và `/login` là app cư dân, `/operations` là app nhân viên, `/api/business` là API. |

## Chạy

```powershell
cd deploy
copy deployment.env.example deployment.env     # điền giá trị; file này không được commit
docker compose --env-file deployment.env up -d --build
```

Thiếu biến bắt buộc thì compose dừng ngay và nêu tên biến. Chỉ in tên biến khi kiểm tra, không in giá trị.

## Một địa chỉ, một lần đăng nhập

Mọi người đăng nhập ở `/login` (app cư dân). Sau khi đăng nhập, `GET /auth/session` cho biết người đó dùng không gian nào (`audiences`) và vai trò vận hành (`operationsRole`): cư dân vào `/`, quản lý vào `/operations/kanban`, nhân viên hiện trường vào `/operations/my-tasks`, quản trị viên vào `/operations/accounts`; tài khoản vừa là cư dân vừa là nhân viên được hỏi chọn. Cả ba nơi dùng chung một cookie `vinhomes_session`.

- `gateway` không gửi `X-Vinhomes-Surface` tới API (và bỏ giá trị trình duyệt tự gửi), nên API dùng một cookie duy nhất.
- Quyền vẫn do vai trò trong API quyết định, không do địa chỉ truy cập; app nhân viên chỉ hiện trang hợp với vai trò (nhân viên hiện trường chỉ thấy ba trang việc).
- Tài nguyên của app nhân viên nằm ở `/staff-assets/` để không đè `/assets/` của app cư dân.
- `VINHOMES_ALLOWED_ORIGINS` chỉ còn địa chỉ của `gateway` (kèm https khi có).

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

## Tác vụ định kỳ và đăng ký platform

- Dịch vụ `scheduler` chạy `python -m vinhomes_api.jobs sweep` mỗi phút (cảnh báo và báo quá hạn xử lý, cho đặt chỗ chưa thanh toán và lượt khách không tới hết hạn). Dùng cùng vai trò hạn chế của API.
- Đăng ký platform một lần, ở máy có `DATABASE_URL` của chủ database: `python -m vinhomes_api.database client --id platform --kind platform --accepts-cases`. Lệnh in bí mật một lần; chạy lại là xoay bí mật.
