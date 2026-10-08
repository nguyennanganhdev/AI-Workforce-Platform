# Vinhomes — cư dân và nhân viên

Gói này chứa riêng phần Vinhomes của nền tảng AI Workforce: giao diện cư dân, giao diện nhân viên (Ban quản lý và nhân viên hiện trường), backend nghiệp vụ và agent tiếp nhận (Reception) trả lời cư dân. Nó không chứa mã chung của nền tảng (chat OpenBot, quản trị OpenBot, Supervisor). Mã gốc lấy từ nhánh `dev_TeamChien` (commit b5e4940).

## Cấu trúc

```
vinhome_Recident/
├── apps/
│   ├── resident-web/   Giao diện cư dân        (React + Vite, cổng 3011)
│   └── staff-web/      Giao diện nhân viên/BQL (React + Vite, cổng 3020)
├── services/
│   └── vinhomes-api/   Backend nghiệp vụ       (FastAPI + PostgreSQL, cổng 8000)
├── agents/
│   └── reception/      Agent tiếp nhận cư dân  (Python, cổng 4202)
├── packages/
│   └── shared/         Mã dùng chung của hai app (upload ảnh, đính kèm, kiểu ticket)
├── deploy/             Đóng gói: Dockerfile.web, nginx, compose.yml, deployment.env.example
└── docs/               Hướng dẫn chạy và API (resident-web/, backend/)
```

`apps/` là thứ người dùng mở trên trình duyệt, `services/` là backend, `agents/` là agent chạy riêng, `packages/` là mã dùng chung không chạy một mình, `deploy/` là đóng gói. Mã mới đặt vào đúng thư mục theo nghĩa đó.

## Công cụ

Phần web dùng **Node 22 trở lên và npm**, phần Python dùng Python 3.12. Không cần Bun.

Gói từng dùng Bun vì nó thừa kế từ repo nền tảng, nơi Bun chạy máy chủ OpenBot. Ở gói này Bun chỉ làm ba việc đều thay được: chạy test (nay là Vitest), chạy máy chủ production tự viết bằng `Bun.serve` (nay là nginx, giống app cư dân) và vài script phụ (nay là Node). Vite, TypeScript và Python không phụ thuộc Bun.

Ngoại lệ: một số script trong `services/vinhomes-api/scripts/` (`start_knowledge`, `start_routines`, `start_technical_tools`, `setup_*`, `provision_*`, `publish_learned`) khởi chạy các công cụ của `server/` thuộc nền tảng, viết bằng Bun. Chúng cần Bun nhưng cũng cần `server/`, vốn không nằm trong gói.

## Chạy khi phát triển

```powershell
npm install
npm run dev:resident      # http://127.0.0.1:3011
npm run dev:operations    # http://127.0.0.1:3020
```

Cả hai app chuyển `/api/business/*` tới backend (`VINHOMES_API_URL`, mặc định `http://127.0.0.1:8000`). Cách dựng backend và agent: [services/vinhomes-api/README.md](services/vinhomes-api/README.md), [agents/reception/README.md](agents/reception/README.md).

| Lệnh | Việc làm |
|---|---|
| `npm run typecheck` | Kiểm tra TypeScript của cả hai app và `packages/shared` |
| `npm test` | Test Vitest của cả ba workspace |
| `npm run build` | Build cả hai app |

Test Python: `python -m pytest tests` trong `agents/reception/` và `services/vinhomes-api/` (xem README của từng phần).

## Đóng gói

Năm thành phần của domain đóng thành năm container: `api`, `reception`, `resident`, `operations`, `field`. Hai app web dùng chung một Dockerfile ([deploy/Dockerfile.web](deploy/Dockerfile.web)), chạy sau nginx; `operations` và `field` là cùng một image, khác nhau ở `VINHOMES_SURFACE`.

```powershell
cd deploy
copy deployment.env.example deployment.env      # điền giá trị, không commit
docker compose --env-file deployment.env up -d --build
```

Compose không khởi động các dịch vụ của nền tảng mà API gọi tới (Supervisor, tìm kiếm tri thức, tool host, lịch chạy, agent factory, kho S3) và không có job migration. Cần có sẵn một PostgreSQL đã migrate và khai báo địa chỉ các dịch vụ kia bằng biến `*_URL` trong `deployment.env`. Chi tiết trong [deploy/README.md](deploy/README.md).

## Phần chưa nằm trong gói

- `server/` (nền tảng): schema database V3 (`server/drizzle`) và các công cụ khởi tạo nằm ở đó. Backend cần database đã có schema này; test `services/vinhomes-api/tests` dựng database thật cũng cần nó.
- Supervisor (`agent-coordination`), tìm kiếm tri thức, tool host: các dịch vụ API gọi tới; có ở nhánh `dev_TeamChien`.
- Nhiều tài liệu trong `agents/` và `services/` trỏ tới `docs/teams/...`; các tài liệu đó cũng nằm ở `dev_TeamChien`.
- `GET /api/vinhomes/tickets` (tab "Yêu cầu hệ thống", tab mặc định của Ban quản lý trong màn Phản ánh & Sự cố) là endpoint của máy chủ nền tảng (`server/src/app.ts`), không phải của `vinhomes-api`. Đặt `PLATFORM_API_URL` để tab này có dữ liệu; nếu không, nó báo lỗi tải và các tab khác vẫn dùng bình thường.
