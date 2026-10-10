# VP Agent Platform

Platform cộng tác agent độc lập, dùng AgentScope vendored làm reasoning runtime. Không import service, database, tài khoản hoặc quy trình Vinhomes.

## Workspace Workforce hiện tại

Giao diện đang phát triển trên `dev_platform` nằm tại **http://localhost:8089/console**, nối trực tiếp với runtime `core/awp`. Xem [hướng dẫn khởi động và kiểm thử](core/README.md). Tài khoản nằm trong `core/.local/accounts.txt` (ignored).

Luồng sử dụng: cấu hình model → tạo/công bố hồ sơ agent → chọn supervisor mặc định trong Thiết lập → Giao việc. Người giao việc không chọn team; supervisor mời chuyên viên theo quyền của hồ sơ. Màn hình công việc hiển thị trao đổi, phối hợp agent, bằng chứng, memory riêng và chi phí thực tế. Các công việc đối tác được quan sát tại đây; reply/consent của cư dân đi qua ứng dụng đối tác.

Các mục bên dưới mô tả stack `vp` đời trước trên cổng 3080. Stack đó chưa được chuyển sang Workforce và không phải giao diện nghiệm thu cho luồng supervisor mới.

## Chạy local

```powershell
cd E:\AI-Workforce-Platform-dev_platform\platform_VP\deploy
# Chỉ chạy lần đầu, không ghi đè khóa mã hóa đã có:
.\init-local.ps1
docker compose up -d --build
docker compose ps
```

Mở **http://localhost:3080**. Tài khoản được sinh tại `platform_VP/.local/accounts.txt`, không đưa vào Git. API: http://localhost:3080/api/docs. PostgreSQL riêng: localhost:5588; Redis và Qdrant chỉ mở trong mạng Compose.

Sau đăng nhập: **Khóa kết nối → Model & provider → Tri thức/Kỹ năng → Đội ngũ agent → Sessions**. Mỗi agent cần model hỗ trợ tools và structured output; tạo draft, kiểm tra chính sách, công bố revision rồi chọn vào team. Agent đầu tiên là coordinator, tối đa hai specialist. Có thể dùng một agent, nhưng kết quả tự xác nhận sẽ được giữ để review.

Không kèm model, khóa API hoặc agent giả trong dữ liệu chạy thật. Ollama cần một máy chủ và model hỗ trợ tool thực sự; nếu chạy trong Docker, `localhost` là container. Endpoint nội bộ chỉ được mở bằng `VP_ALLOW_PRIVATE_ENDPOINTS=true` trong môi trường tin cậy.

## Thành phần

| Đường dẫn | Trách nhiệm |
|---|---|
| `agentscope/` | SDK gốc, giữ nguyên source |
| `services/platform-api/vp/` | Auth/RBAC, revision, session, durable queue, context, evidence, money, tools, RAG, automation |
| `apps/platform-web/` | Console tiếng Việt, hội thoại, inspector, quản trị và đánh giá |
| `deploy/` | Stack và script local độc lập |
| `docs/SPEC.md` | Mô hình thực thi và giới hạn |
| `docs/RUNBOOK.md` | Vận hành, kiểm thử, phục hồi |
| `docs/ACCEPTANCE.md` | Bằng chứng đã kiểm tra và phần cần nghiệm thu với provider thật |
| `docs/research/` | Phân tích mã nguồn AgentScope, durability và Jev |

## Kiểm tra

```powershell
cd platform_VP\services\platform-api
uv sync --frozen
uv run ruff check vp tests
uv run pytest -q
# PostgreSQL: tạo vp_platform_test trong stack local một lần, rồi:
..\..\deploy\test-postgres.ps1
cd ..\..\apps\platform-web
pnpm install --frozen-lockfile
pnpm build
pnpm exec playwright install chromium --only-shell
pnpm test
```

SQLite phục vụ phát triển và browser acceptance. Nghiệm thu concurrency phải chạy PostgreSQL; test từ chối database PostgreSQL không có hậu tố `_test`. Browser test dùng DB riêng trong `.local/`, API/AgentScope thật và thay riêng provider I/O bằng fixture, không tiêu tiền API.
