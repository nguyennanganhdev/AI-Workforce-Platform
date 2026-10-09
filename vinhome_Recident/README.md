# Vinhomes — cư dân và nhân viên

Gói domain Vinhomes, đứng riêng, không chứa mã của platform: giao diện cư dân, giao diện nhân viên (Ban quản lý và nhân viên hiện trường), backend nghiệp vụ và agent lễ tân (Reception) trả lời cư dân. Về sau platform sẽ nối vào gói này như một khách hàng; Reception là đầu nối duy nhất từ Vinhomes sang platform.

## Cấu trúc

```
vinhome_Recident/
├── apps/
│   ├── resident-web/   Giao diện cư dân        (React + Vite, cổng 3011)
│   └── staff-web/      Giao diện nhân viên/BQL (React + Vite, cổng 3020)
├── services/
│   └── vinhomes-api/   Backend nghiệp vụ       (FastAPI + PostgreSQL, cổng 8000)
├── agents/
│   └── reception/      Agent lễ tân cho cư dân (Python, cổng 4202)
├── packages/
│   └── shared/         Mã dùng chung của hai app (upload ảnh, đính kèm)
├── deploy/             Đóng gói: Dockerfile.web, nginx, compose.yml, deployment.env.example
└── docs/               Hướng dẫn chạy và API (resident-web/, backend/)
```

`apps/` là thứ người dùng mở trên trình duyệt, `services/` là backend, `agents/` là agent chạy riêng, `packages/` là mã dùng chung không chạy một mình, `deploy/` là đóng gói. Mã mới đặt vào đúng thư mục theo nghĩa đó.

## Công cụ

Phần web dùng **Node 22 trở lên và npm** (build bằng Vite, test bằng Vitest); phần Python dùng Python 3.12. Không cần Bun.

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

Các thành phần của domain đóng thành container: `api`, `reception`, `resident`, `operations` và `gateway`, địa chỉ duy nhất phía trước. Hai app web dùng chung một Dockerfile ([deploy/Dockerfile.web](deploy/Dockerfile.web)); cư dân và nhân viên cùng đăng nhập ở `/login` rồi được chuyển sang đúng app.

```powershell
cd deploy
copy deployment.env.example deployment.env      # điền giá trị, không commit
docker compose --env-file deployment.env up -d --build
```

Compose không khởi động PostgreSQL và kho S3; job `migrate` tự tạo schema trong database trống. Chi tiết trong [deploy/README.md](deploy/README.md).

## Đã bỏ và còn dang dở

Gói này đã bỏ toàn bộ phần Supervisor, quản lý agent (builder, đánh giá, model, kết nối MCP, lịch chạy, phòng chat của agent), học tri thức và tool gateway, cùng các màn hình tương ứng trong app nhân viên. Còn lại:

- **Database đã thuộc gói** (`services/vinhomes-api/src/vinhomes_api/schema/`: 9 migration, dữ liệu mẫu, quyền role) và **bề mặt cho platform** (`/integration/v1`). Đọc theo thứ tự: nghiệp vụ [docs/domain/NGHIEP_VU_VINHOMES.md](docs/domain/NGHIEP_VU_VINHOMES.md) → 12 kịch bản kiểm thu [docs/domain/KICH_BAN_VANG.md](docs/domain/KICH_BAN_VANG.md) → hợp đồng với platform [docs/domain/HOP_DONG_TICH_HOP.md](docs/domain/HOP_DONG_TICH_HOP.md) → cách nạp dữ liệu [docs/domain/NAP_DU_LIEU.md](docs/domain/NAP_DU_LIEU.md) → quyết định về database [docs/domain/SPEC_DATABASE_DOMAIN.md](docs/domain/SPEC_DATABASE_DOMAIN.md) và kế hoạch [docs/domain/KE_HOACH_TRIEN_KHAI.md](docs/domain/KE_HOACH_TRIEN_KHAI.md).
- **Đường nối Reception ⇄ "Supervisor".** Reception giao ticket bằng hợp đồng `schema_v2`: hộp thư, kết quả trả về và câu hỏi gửi lại cư dân (`v3_reception_supervisor`, `v3_resident_interactions`, `/resident/supervisor-interactions`). Chưa có ai đọc hộp thư này; tên gọi và hợp đồng sẽ đổi khi nối sang platform.
- **Lớp xem thử dữ liệu mẫu trong app nhân viên** vẫn còn khái niệm phòng và agent (`hooks/use-operations-data.ts`, `mock/`, `workspace/`).
- **Nội dung an toàn khẩn cấp và tri thức** hiện để trống: Reception không đưa lời khuyên tự xử lý và không có nguồn trả lời câu hỏi thông tin cho đến khi có gói tri thức (`RECEPTION_KNOWLEDGE_URL`).
