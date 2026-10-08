# Giao diện nhân viên (Operations / Field)

React + Vite cho Ban quản lý, quản trị viên và nhân viên hiện trường. Gọi backend nghiệp vụ `services/vinhomes-api` qua `/api/business` (và một danh sách ticket qua API nền tảng, xem bên dưới); đăng nhập tại `/operations/login` bằng tài khoản thật. Hướng dẫn chạy kết nối: [docs/resident-web/07-connected-runtime.md](../../docs/resident-web/07-connected-runtime.md). Chế độ trải nghiệm dùng dữ liệu mẫu riêng, không chứng minh quyền hoặc ghi dữ liệu backend.

## Chạy

Từ thư mục gốc `vinhome_Recident` (cần Node 22 trở lên):

```powershell
npm install
npm run dev:operations     # http://127.0.0.1:3020
```

Một cổng cho mọi vai trò: Ban quản lý vào Điều phối, nhân viên hiện trường vào "Việc của tôi" trong khung dành cho điện thoại. Biến môi trường của máy chủ dev:

| Biến | Ý nghĩa | Mặc định |
|---|---|---|
| `APP_PORT` | Cổng lắng nghe (`--port` cũng được) | `3020` |
| `VINHOMES_API_URL` | Nơi backend nghiệp vụ chạy | `http://127.0.0.1:8000` |
| `PLATFORM_API_URL` | API của nền tảng; chỉ danh sách "Yêu cầu hệ thống" (`/api/vinhomes/tickets`) đọc từ đây | `http://127.0.0.1:3001` |
| `VINHOMES_API_ORIGIN` | Origin gửi tới API, khi API chỉ nhận origin của bản triển khai riêng của nó | của trình duyệt |
| `VINHOMES_SURFACE` | Cổng đăng nhập: `operations` hoặc `field` | không gửi |

Backend giữ một phiên đăng nhập riêng cho mỗi cổng, nên hai cổng cùng máy không ghi đè phiên của nhau. Triển khai dùng chung một image cho cả hai cổng, phân biệt bằng `VINHOMES_SURFACE` (xem [deploy/](../../deploy/)).

## Lệnh

| Lệnh (từ thư mục gốc) | Việc làm |
|---|---|
| `npm run typecheck -w @vinhomes/staff-web` | Kiểm tra TypeScript |
| `npm test -w @vinhomes/staff-web` | Test bằng Vitest |
| `npm run build -w @vinhomes/staff-web` | Build vào `apps/staff-web/dist` (sinh lại `src/routeTree.gen.ts`) |

`src/routeTree.gen.ts` do TanStack Router sinh ra khi chạy dev hoặc build; commit file này cùng thay đổi route.

## Windows và cache của Vite

Trên Windows, Vite có thể báo `error while updating dependencies: undefined` khi đổi tên `deps_temp_*` thành `deps` gặp khóa file tạm thời (`EPERM`). Lệnh dev đi qua `scripts/vite.mjs`, cho phép thử lại thao tác này tối đa 60 giây, cách nhau 250 ms. Chỉ áp dụng cho cache optimizer trong `apps/staff-web/node_modules/.vite`; không sửa package Vite, không đổi quyền truy cập. Lỗi không liên quan đến khóa file được trả ngay. Tránh chạy hai Vite server của app này cùng lúc khi đang tái tạo cache.

## Cấu trúc

- `src/features/vinhomes-operations/`: toàn bộ màn hình và logic nghiệp vụ (BQL, nhân viên hiện trường, quản trị, agent).
- `src/routes/`: route TanStack Router; mọi trang nằm dưới `/operations`.
- `src/components/ui/`, `src/lib/`: thành phần giao diện và truy vấn dùng chung.
- `tests/`: test Vitest; `scripts/`: kiểm thử trình duyệt qua Chrome DevTools Protocol (`node scripts/<tên>.ts`).
