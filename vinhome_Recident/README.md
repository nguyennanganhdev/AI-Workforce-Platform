# Vinhomes — Domain cư dân và nhân viên

Domain độc lập gồm landing, auth, ứng dụng cư dân, staff/admin, API nghiệp vụ và Reception. **BQL dùng Platform** để điều phối session, gọi MCP, quản lý tiến độ và phản hồi cư dân. Domain giữ dữ liệu, quyền, trạng thái nghiệp vụ và bằng chứng.

| Thư mục | Trách nhiệm |
|---|---|
| `apps/resident-web` | Landing, auth, chat, yêu cầu, thông báo và quyết định cư dân |
| `apps/staff-web` | Staff nhận việc/ETA/tiến độ/bằng chứng; admin quản lý tài khoản, phạm vi và kết nối Platform |
| `services/vinhomes-api` | FastAPI, PostgreSQL/pgvector, RLS, nghiệp vụ, MCP, scheduler và outbox |
| `agents/reception` | Tiếp nhận CSKH, tra cứu tri thức, tạo yêu cầu có ngữ cảnh cư dân |
| `packages/shared` | Upload/attachment và hợp đồng frontend dùng chung |
| `deploy` | Compose, gateway, backup, TLS, bộ dữ liệu đầu vào và sandbox |

Ranh giới module và nguyên tắc bảo trì: [ARCHITECTURE.md](ARCHITECTURE.md). Domain không import/build code `platform_VP`.

## Phát triển và kiểm tra

Node 22 trở lên (CI Node 24), npm, Python 3.12 và Docker Linux.

```powershell
npm ci --ignore-scripts --no-audit --no-fund
npm run dev:resident
npm run dev:operations
npm run typecheck
npm test
npm run build
```

`npm test` chạy từng file DOM test trong process riêng; có thể chọn app bằng `npm test -- resident-web` hoặc `npm test -- staff-web`. Hai dev server proxy `/api/business` đến `VINHOMES_API_URL`, mặc định `http://127.0.0.1:8000`.

Trong `services/vinhomes-api`: cài `python -m pip install -e '.[test]'`, chạy `python -m pytest -q`. Test PostgreSQL cần `RESIDENT_TEST_ADMIN_URL` và `RESIDENT_TEST_RUNTIME_URL` trỏ tới PostgreSQL test loopback. Xem [API README](services/vinhomes-api/README.md).

Trong `agents/reception`: cài `requirements-test.txt`, rồi chạy offline contracts bằng `python -m pytest -q tests/runtime/test_model_endpoint.py tests/runtime/test_cskh_contract.py`. Kết quả này không thay thế nghiệm thu Agent thật.

## Docker và dữ liệu

```powershell
deploy\new-env.ps1
# Điền cấu hình riêng trong deploy/deployment.env; giữ secret của volume đang có.
docker compose --env-file deploy/deployment.env -f deploy/compose.yml up -d --build
```

Compose có PostgreSQL, MinIO, init/migration, API, scheduler, platform-sync, Reception, hai app web, gateway và backup. `/` mở landing; `/login` đăng nhập chung; `/resident` và `/operations` mở app theo quyền. Chi tiết: [deploy/README.md](deploy/README.md).

Production mặc định không tạo người/căn/giao dịch giả (`VINHOMES_SAMPLE_WORLD=0`) hoặc tự nạp lại tri thức (`VINHOMES_LOAD_KNOWLEDGE=0`). Owner template/proposal/reference giữ provenance và hiệu lực; hồ sơ cư trú/nhân sự/giá/SLA mô phỏng không phải xác nhận của operator.

Sandbox dùng [compose.sandbox.yml](deploy/compose.sandbox.yml) với marker/volume riêng: [SANDBOX_LOCAL.md](deploy/SANDBOX_LOCAL.md). Không tạo env mới để thay mật khẩu của volume cũ.

## Platform và tương thích

MCP Streamable HTTP tại `/mcp` có **16 tool**: 7 ticket/work order, 2 ngữ cảnh dịch vụ/availability và 7 Travel mock. Catalog không đồng nghĩa mọi tool được cấp cho mọi tuyến. Backend giữ bootstrap token; model dùng grant giới hạn ticket/workflow/đơn vị. Không cung cấp tool tạo lại ticket/cư trú hoặc xuất hồ sơ cá nhân hàng loạt.

Domain admin lưu cấu hình và xác nhận tuyến trước khi bật bridge. Cấu hình database ưu tiên env; khi clone DB phải giữ cấu hình của môi trường đích và khóa mã hóa tương ứng, không sao chép ciphertext giữa hai khóa khác nhau. Xem [platform/README.md](deploy/platform/README.md) và [NOI_WORKFORCE_V1.md](docs/domain/NOI_WORKFORCE_V1.md).

`/integration/v1` và endpoint có tên `supervisor` còn phục vụ tương thích/test legacy, không phải Platform/Supervisor chạy kèm Domain. Preview chỉ dùng phát triển; production tắt `VITE_ALLOW_DEMO_BACKEND` và `VITE_ENABLE_UI_PREVIEW`.

CI kiểm tra schema/RLS, tài khoản, API, grant/MCP, bridge với transport giả, HTTP closure/rework, Reception offline và frontend. CI/container healthy chưa chứng minh Agent thật, route hai chiều, dữ liệu được operator xác nhận hoặc tải production. Chưa expose cấp/hủy thẻ, đăng ký khách, booking tiện ích, thanh toán/xóa nợ hoặc duyệt cải tạo qua MCP.

Secret, account export, dump và log riêng nằm ngoài Git. PR vào `develop2` chỉ gồm Domain và CI liên quan; không thay Platform trên nhánh đích.
