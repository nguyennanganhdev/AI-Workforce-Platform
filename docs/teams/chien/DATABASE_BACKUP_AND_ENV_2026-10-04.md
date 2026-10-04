# Backup database và cấu hình env cho thành viên

Đối chiếu source và database ngày 04/10/2026. Bản backup chính là **`vinhomes_connected`** (đăng nhập thật); `vinhomes_v3` là database demo. Hai bản không được trộn tenant, role hoặc checkpoint. Chỉ thay tài liệu/file mẫu; không sửa env chứa secret hoặc phần triển khai đang làm.

## 1. Bản backup đã xuất

Thư mục local: `.codex-artifacts/backups/Vinhomes-team-20261004-122855/`. Backup nằm ngoài Git; gửi thư mục hoặc ZIP riêng cho các thành viên cần dữ liệu.

| File | Nội dung |
|---|---|
| `vinhomes_connected.bak` | Bản chính: schema, dữ liệu nghiệp vụ, tài khoản, RAG, owner, grant, trigger, constraint và policy trong database đăng nhập thật |
| `vinhomes_v3.bak` | Bản demo để đối chiếu, không dùng thay bản chính |
| `roles.sql` | Role/thuộc tính role; **không chứa mật khẩu PostgreSQL** |
| `*.inventory.json` | Danh mục, số dòng từng bảng, constraint, table grants và RLS để đối chiếu restore |
| `*.toc.txt`, `MANIFEST.json`, `SHA256SUMS.txt` | Danh mục archive, thông tin snapshot/kiểm tra và checksum |

`.bak` ở đây là **PostgreSQL custom archive (`PGDMP`)**, restore bằng `pg_restore`; không phải backup SQL Server và không chạy qua `psql -f`.

Mỗi bản có **193 bảng `public` + 1 bảng migration trong schema `drizzle`**, **683 FK thuộc `public`** tại lúc xuất. Đã thử restore cả hai vào PostgreSQL 17/pgvector riêng, so khớp catalog, owner, table grants, policy/RLS và số dòng của **194 bảng** với cùng snapshot được dùng để dump. Kiểm tra này không gọi model, không sửa database nguồn và không thay kiểm thử ứng dụng.

Database backup chỉ mang dữ liệu nằm trong PostgreSQL. **File ảnh/PDF/DOCX trên disk hoặc object storage, SQLite checkpoint của Reception/Coordination, env/secret và database ở cluster khác không nằm trong `.bak`.** Muốn chạy lại đầy đủ file cũ phải chuyển cả file root hoặc bucket tương ứng. Password hash tài khoản ứng dụng nằm trong DB; mật khẩu đăng nhập rõ không được xuất thành danh sách.

## 2. Restore trên máy mới

Yêu cầu Docker và image `pgvector/pgvector:pg17` (cùng dòng PostgreSQL 17, pgvector 0.8.6 của nguồn). Chạy PowerShell từ repository root. Các tên container/volume/database dưới đây dành cho **môi trường mới**; không chạy vào container đang chứa dữ liệu cần giữ. Cổng `5544` phải trống; nếu đổi cổng, đổi cả URL trong env.

```powershell
$backupDir = 'E:\duong-dan-ban-nhan\Vinhomes-team-20261004-122855'
$env:POSTGRES_PASSWORD = [System.Net.NetworkCredential]::new('', (Read-Host 'Dat mat khau PostgreSQL admin cho may nay' -AsSecureString)).Password
docker run -d --name vinhomes-team-db --env POSTGRES_PASSWORD -p 127.0.0.1:5544:5432 -v vinhomes-team-data:/var/lib/postgresql/data pgvector/pgvector:pg17
docker exec vinhomes-team-db pg_isready -U postgres
```

Lệnh nhập mật khẩu chạy trên Windows PowerShell 5.1 và PowerShell 7. Chỉ tiếp tục khi PostgreSQL báo `accepting connections`; kiểm tra exit code của từng lệnh, dừng nếu có lỗi.

```powershell
docker cp "$backupDir\roles.sql" vinhomes-team-db:/tmp/roles.sql
docker exec vinhomes-team-db psql -X -v ON_ERROR_STOP=1 -U postgres -f /tmp/roles.sql
docker exec vinhomes-team-db createdb -U postgres --owner=vinhomes_seed vinhomes_connected
docker cp "$backupDir\vinhomes_connected.bak" vinhomes-team-db:/tmp/vinhomes_connected.bak
docker exec vinhomes-team-db pg_restore -U postgres -d vinhomes_connected --exit-on-error --single-transaction /tmp/vinhomes_connected.bak
```

Không dùng `--no-acl` hoặc `--no-owner` cho cách restore này: ứng dụng cần đúng quyền/RLS và owner ban đầu. `vinhomes_seed` là owner/admin phục vụ migration, **không dùng để chạy API/RAG/tools**. `roles.sql` giữ role admin đó để restore; import file một lần vào cluster mới. Với cluster đã có các role cùng tên, cần đối chiếu role/grant trước khi áp dụng, không bỏ qua lỗi restore.

Đặt mật khẩu mới cho hai role runtime trên máy nhận (nhập trong prompt, không ghi vào SQL/file mẫu):

```powershell
docker exec -it vinhomes-team-db psql -U postgres -d vinhomes_connected
```

Trong `psql`:

```text
\password vinhomes_connected_api
\password vinhomes_connected_technical_api
\q
```

Kiểm tra bằng `psql`:

```sql
SELECT count(*) FROM pg_tables WHERE schemaname='public'; -- 193
SELECT count(*) FROM pg_constraint
WHERE contype='f' AND connamespace='public'::regnamespace; -- 683
SELECT extname, extversion FROM pg_extension;
SELECT id FROM tenants;
SELECT id, tenant_id FROM knowledge_bases;
SELECT model_name, dimension, active FROM embedding_models;
```

Trong bản connected này, tenant là `d360eea1-cd1d-436a-8769-67c7e1598e8b`. Knowledge service hiện chọn kho `22841926-724a-4021-a0e2-f79cac995704`; còn một kho khác trong DB, không lấy kho bất kỳ. Model embedding đang active: `text-embedding-3-large`, **1536 chiều**. Giữ cùng model khi tìm kiếm dữ liệu đã restore.

Nếu cần bản demo, tạo database `vinhomes_v3` thuộc `vinhomes_seed` rồi dùng cùng quy trình với `vinhomes_v3.bak`. Role/tenant của demo khác connected. Sau khi restore, không chạy lại script tạo database/seed chỉ để có env: chúng có thể provision lại hoặc thay dữ liệu/cấu hình. Tạo env từ các file mẫu dưới đây.

## 3. Ngoài OpenAI key cần điền gì?

| Nhóm | Biến và trách nhiệm |
|---|---|
| Business DB | `VINHOMES_API_DATABASE_URL` dùng `postgresql+asyncpg://vinhomes_connected_api:MAT_KHAU_DA_URL_ENCODE@127.0.0.1:5544/vinhomes_connected` |
| Tenant | `VINHOMES_API_TENANT_ID`, `KNOWLEDGE_TENANT_ID`, `TECHNICAL_API_TENANT_ID` cùng tenant đã restore |
| RAG | `KNOWLEDGE_DATABASE_URL` dùng `postgresql://vinhomes_connected_api:...`; `KNOWLEDGE_BASE_ID`; `KNOWLEDGE_EMBEDDING_MODEL`; `RECEPTION_API_URL` trỏ API authority |
| Tools | `TECHNICAL_API_DATABASE_URL` dùng role riêng `vinhomes_connected_technical_api`, URL `postgresql://...`; role phải giữ SELECT/INSERT, không cấp UPDATE/DELETE rộng |
| Reception ↔ API | `VINHOMES_API_RECEPTION_SERVICE_TOKEN` **bằng** `RECEPTION_SERVICE_TOKEN`; `VINHOMES_API_RECEPTION_URL` và `RECEPTION_BACKEND_URL` trỏ đúng service |
| Delegation | `RECEPTION_DELEGATION_KEY`: ít nhất 32 byte random dạng hex, nằm ở backend để ký delegation; khác Reception token |
| Supervisor ↔ API | `VINHOMES_API_COORDINATION_SERVICE_TOKEN` **bằng** `COORDINATION_SERVICE_TOKEN`; phải **khác** Reception token |
| Supervisor ↔ Tools | `TECHNICAL_TOOLS_SERVICE_TOKEN` **bằng** `COORDINATION_TOOLS_TOKEN`; `COORDINATION_TOOLS_URL` kết thúc bằng `/internal/technical/v1` |
| Supervisor ↔ OpenBot | `MANAGED_AGENT_TOKEN` cùng giá trị ở hai process; `COORDINATION_MODEL` và `COORDINATION_OPENBOT_URL` đặt cùng nhau; `COORDINATION_OPENBOT_MODEL` chọn model specialist |
| Khóa ký / browser | `VINHOMES_API_RESIDENT_SIGNING_KEY` dạng hex 32 byte; `VINHOMES_API_ALLOWED_ORIGINS` và `VINHOMES_API_RESIDENT_ALLOWED_ORIGINS` đúng origin frontend |
| Storage runtime | SQLite cần path/volume bền vững. `COORDINATION_DATABASE_URL` là lựa chọn PostgreSQL checkpoint trong adapter đang có ở working tree; phải dùng DB riêng, owner không superuser, không trỏ business DB |
| Gateway model | `OPENAI_BASE_URL` cho Reception/RAG/OpenBot; planner đọc riêng `COORDINATION_MODEL_BASE_URL`. Để trống thì dùng OpenAI mặc định; gateway phải hỗ trợ embedding model/1536 chiều nếu dùng cho RAG |

Sinh **một secret mới cho mỗi nhóm**, sau đó sao chép giá trị cho đúng hai đầu của nhóm đó:

```powershell
python -c "import secrets; print(secrets.token_hex(32))"
```

Lệnh tạo 64 ký tự hex, dùng được cho khóa ký hoặc service token (các service token cần tối thiểu 32 ký tự). Không lấy OpenAI key làm service token. Mật khẩu có ký tự đặc biệt phải URL-encode khi đưa vào connection URL. Không đặt secret trong biến `VITE_*`.

## 4. File env từng service

Các launcher local **không tự đọc toàn bộ `.env` gốc**. File gốc chứa cấu hình platform; mỗi runtime đọc file riêng:

| File mẫu | Copy thành | Nội dung cần điền |
|---|---|---|
| [connected.env.example](../../../services/vinhomes-api/connected.env.example) | `services/vinhomes-api/.env.connected` | DB, tenant, password auth, signing/delegation key, hai token service và origins |
| [agent-reception/.env.example](../../../agent-reception/.env.example) | `agent-reception/.env` | OpenAI key/model, Reception token/backend, knowledge URL; `RECEPTION_AGENT=graph` hoặc `loop` |
| [agent-coordination/.env.example](../../../agent-coordination/.env.example) | `agent-coordination/.env` | Backend/token; bỏ dấu `#` ở các dòng model/OpenBot/tool cần dùng và điền secret |
| [knowledge.env.example](../../../services/vinhomes-api/knowledge.env.example) | `services/vinhomes-api/.local-connected/knowledge.env` | DB, tenant, kho/model, API authority và port RAG |
| [technical-api.env.example](../../../services/vinhomes-api/technical-api.env.example) | `services/vinhomes-api/.local-connected/technical-api.env` | Role tools, tenant, token tools và port |
| [.env.example](../../../.env.example) | `.env` gốc | Platform Hono/OpenBot, Intelligence, credential vault, OAuth và biến proxy/frontend theo profile sử dụng |

`start_connected.ps1` còn đọc `.local-connected/coordination.env` và `.local-connected/reception.env` nếu có; bản connected nhận ưu tiên khi file cấu hình chính đặt cùng biến. Để tránh fallback sang cấu hình demo, đặt đầy đủ URL/token/delegation key trong `.env.connected`. `start_vinhomes.ps1 -Connected` tự đọc token tools từ `technical-api.env`; model key từ `agent-reception/.env`. `start_openbot.ps1` đọc `MANAGED_AGENT_TOKEN` từ `agent-coordination/.env`.

Các biến `COORDINATION_CONFIG`, `COORDINATION_INGRESS_TOKEN`, `COORDINATION_MODEL_KEY`, `COORDINATION_REPORT_ROOT/HASH` đầu file Coordination thuộc **entrypoint generic**, không phải biến thay thế cho runtime `python -m vinhomes`.

Với Docker Compose mới trong `deploy/vinhomes/`, dùng file mẫu của deployment và đối chiếu mapping trong compose: các tên `RESIDENT_SIGNING_KEY`, `RECEPTION_SERVICE_TOKEN`, `COORDINATION_SERVICE_TOKEN`, `VINHOMES_TENANT_ID` được map sang biến cụ thể từng container. Cấu hình triển khai này đang là WIP; hướng dẫn hiện tại không khẳng định toàn bộ Compose đã được nghiệm thu. Trong container, `127.0.0.1` chỉ container đó; dùng tên service hoặc host thực của DB.

## 5. Tính năng nào cần thêm key/provider?

- **Luồng Vinhomes standalone** (FastAPI + Reception + Coordination + RAG/tools + `agent-bot`): không bắt buộc key CopilotKit/Composio/OAuth chỉ để gọi luồng này. DB, grants, published agent và cấu hình tương ứng vẫn phải đủ.
- **Platform Hono đầy đủ (`server/src/index.ts`)**: code hiện bắt buộc `INTELLIGENCE_API_URL`, `INTELLIGENCE_GATEWAY_WS_URL`, `INTELLIGENCE_API_KEY`; OpenAI key không thay project key CopilotKit Intelligence. `KEY_ENCRYPTION_KEY` phải là base64 của 32 byte để mã hóa credential; muốn giải mã credential đã restore thì cần **khóa cũ tương ứng**, nhận riêng qua kênh secret, không sinh khóa mới rồi mong dữ liệu cũ dùng được.
- **Đăng nhập platform bằng OAuth**: cấu hình provider Google/Microsoft/Okta, `BETTER_AUTH_URL`, `BETTER_AUTH_SECRET`, `TRUSTED_ORIGINS`, `INITIAL_ADMIN_EMAILS` theo `.env.example`. Vinhomes password auth không yêu cầu OAuth; `OPENBOT_SINGLE_USER=true` trong mẫu gốc là chế độ local, không chứng minh người dùng đã đăng nhập.
- **Connector ngoài**: `COMPOSIO_API_KEY` khi dùng connector Composio; OAuth riêng nếu connector yêu cầu. Không bắt buộc cho technical tools nội bộ.
- **BQL publish agent qua CLI**: cần tài khoản quản lý; bước approve cần tài khoản admin. Module `vinhomes.publish` đọc `PUBLISH_MANAGEMENT_EMAIL/PASSWORD`, `PUBLISH_ADMIN_EMAIL/PASSWORD`. Launcher `publish_agent.ps1 -Connected` hiện lấy từ `accounts.txt`/`initial-admin.txt`; hai file mật khẩu đó **không nằm trong backup**. Chọn tài khoản được cấp quyền trên máy nhận hoặc gọi module với credential phù hợp, không giả việc restore DB đã cấp thêm quyền.
- **Ảnh/tệp/báo cáo**: cần storage đã provision và bytes tệp tương ứng. Python API hiện dùng `VINHOMES_RESIDENT_FILE_ROOT`/storage record cho local disk; không tự thêm biến MinIO/S3 rồi coi các biến đó đã được API tiêu thụ.

Chỉ khi tạo credential vault mới, sinh `KEY_ENCRYPTION_KEY` đúng định dạng bằng `python -c "import base64,secrets; print(base64.b64encode(secrets.token_bytes(32)).decode())"`. Lệnh hex ở mục 3 không thay cho định dạng base64 này.

## 6. Khởi động và kiểm tra

Sau khi cài dependencies từng package và điền các file trên, chạy mỗi service trong terminal riêng từ repo root:

```powershell
powershell -File services/vinhomes-api/scripts/start_connected.ps1
powershell -File services/vinhomes-api/scripts/start_knowledge.ps1 -Connected
powershell -File services/vinhomes-api/scripts/start_technical_tools.ps1 -Connected
powershell -File agent-reception/scripts/start_runtime.ps1
powershell -File agent-coordination/scripts/start_openbot.ps1
powershell -File agent-coordination/scripts/start_vinhomes.ps1 -Connected
```

Frontend: `bun run dev:resident` (3011), `bun run dev:operations` (3020). Proxy `VINHOMES_API_URL` mặc định `http://127.0.0.1:8000`; giữ `VITE_ALLOW_DEMO_BACKEND=false`, `VITE_ENABLE_UI_PREVIEW=false` khi kiểm tra dữ liệu thật.

Kiểm tra `/ready` của API (8000) và Coordination (4300), `/health` của Reception (4202), knowledge (8787), tools (8788), OpenBot (4200). Sau đó đăng nhập thật, hỏi một câu RAG, gửi ticket, xem room/specialist và thử tool đúng quyền. Health/restore thành công không tự chứng minh toàn bộ flow đã hoạt động.
