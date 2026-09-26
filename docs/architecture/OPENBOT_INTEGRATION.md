# OpenBot — nguồn đã clone và baseline tích hợp

## 1. Checkout đã hoàn tất

| Thuộc tính | Giá trị |
|---|---|
| Repository sản phẩm | `https://github.com/nguyennanganhdev/AI-Workforce-Platform.git` |
| Repository nguồn | [CopilotKit/OpenBot](https://github.com/CopilotKit/OpenBot) |
| Clone URL | `https://github.com/CopilotKit/OpenBot.git` |
| Đường dẫn local | `E:\openbot-upstream` |
| Nhánh nguồn lúc clone | `main` |
| Commit ghim | `3c73cf00efba46122dfd0447485e2b61f1d6a2cd` |
| Ngày commit | 2026-09-23 |
| Ngày clone | 2026-09-26 |
| Package version | `0.0.15` |
| Checkout hiện tại | Detached HEAD tại commit ghim |
| License source | MIT, Copyright 2026 CopilotKit; file `LICENSE` trong checkout |
| Kiểm chứng | Remote đúng URL; working tree sạch; `git fsck --connectivity-only --no-dangling` thành công |

Nguồn này khớp React/Vite, Hono và AG-UI mà thiết kế dự án yêu cầu. Đây là bản source nguyên gốc có Git history; chưa có chỉnh sửa trong checkout upstream.

**Đã nhập source vào repo sản phẩm trên nhánh `chore/import-openbot`.** Giữ baseline ở checkout riêng để đối chiếu; sản phẩm không phụ thuộc checkout đó. Dependency root đã cài bằng Bun 1.3.14. Chưa tạo `.env`/credential, chạy migration hoặc vận hành toàn stack với AI thật.

## 2. Toolchain và thành phần đã đối chiếu

Các dữ kiện dưới đây lấy từ file tại commit ghim, không suy ra từ layout scaffold:

| File/vùng upstream | Dữ kiện |
|---|---|
| `package.json` | Package manager `bun@1.3.14`; workspaces `app`, `server`, `worker` |
| `bun.lock` | Dependency lockfile của root workspace |
| `app/package.json` | React, Vite, TanStack Router, CopilotKit UI; build/dev dùng Bun |
| `server/package.json` | Hono, CopilotKit runtime, Better Auth, Drizzle ORM và PostgreSQL client |
| `server/src/db/` | DB client và schema có sẵn; cần đối chiếu identity/domain trước khi nhập |
| `shared/` | Shared implementation/helper hiện có, không phải toàn bộ là DTO thuần |
| `worker/` | Workspace riêng cần khảo sát vai trò trước quyết định tích hợp |
| `supervisor/`, `agent-computer/` | Hạ tầng computer/browser của OpenBot |
| `agent-*` | Các agent implementation/mẫu; không thay thế quyết định AgentScope P0 của dự án |
| `docker-compose.yml`, `Dockerfile`, `charts/openbot/` | Deployment assets có thật; chart version `0.1.2`, appVersion `0.0.15` |
| `README.md`, `.env.example`, `docs/` | Hướng dẫn upstream về config, CopilotKit Intelligence, model và vận hành |

Để chạy upstream theo quickstart của nó cần Bun, Docker, cấu hình CopilotKit Intelligence và model credential tương ứng. Việc chạy toàn bộ hệ thống chưa được thực hiện trong bước clone này. Các giá trị cấu hình cần đọc từ `.env.example` và tài liệu đúng baseline; không đưa secret vào hồ sơ tích hợp.

Nguồn để đối chiếu: [manifest tại commit ghim](https://github.com/CopilotKit/OpenBot/blob/3c73cf00efba46122dfd0447485e2b61f1d6a2cd/package.json), [README upstream](https://github.com/CopilotKit/OpenBot/blob/3c73cf00efba46122dfd0447485e2b61f1d6a2cd/README.md), [LICENSE](https://github.com/CopilotKit/OpenBot/blob/3c73cf00efba46122dfd0447485e2b61f1d6a2cd/LICENSE).

## 3. Mapping baseline đã nhập và công việc tiếp theo

| Source trong `E:\openbot-upstream` | Target trong repo sản phẩm | Công việc tiếp theo |
|---|---|---|
| `app/` | `app/` | Nhập shell, router, assets và auth UI; giữ feature platform/Vinhomes hiện tại |
| `server/src/` | `server/src/` | Hợp nhất bootstrap/middleware, sau đó phân loại generic code; không copy đè toàn server |
| `server/src/db/` và migration config | `server/src/db/` | Review identity/schema/ledger theo ERD; chưa chạy migration vào database sản phẩm |
| `shared/` | Shared contract hoặc implementation module đúng owner | Không chép toàn bộ helper vào `shared/platform` vì boundary hiện tại chỉ cho contract độc lập |
| Root manifest, `bun.lock`, TS/config/scripts | Root tooling | Chốt chuyển sang Bun hay adapter tooling; cập nhật lockfile, resolver, test discovery và CI cùng PR |
| `worker/` | Chưa chốt | Xác định chức năng cần dùng, owner và process boundary trước khi nhập |
| `supervisor/`, `agent-computer/` | Chưa chốt | Chỉ nhập nếu cần OpenBot computer/browser execution; bảo toàn governance boundary |
| Agent mẫu | Reference cho AG-UI | Bọc AgentScope trong `agent-runtime`; không thay runtime P0 bằng agent mẫu một cách ngầm định |
| Docker/Compose/Helm | Deployment assets root và `charts/openbot/` | Sửa build context/service topology sau khi hợp nhất executable |
| `LICENSE` và attribution | Đi kèm source được nhập | Giữ thông tin giấy phép khi sao chép phần mã nguồn tương ứng |

Sản phẩm đã chuyển sang Bun workspace app/server/worker, thay package-lock.json bằng bun.lock. Code upstream giữ ở vị trí gốc; khung Platform/Vinhomes và shared contracts được giữ cùng tree. Shared helper upstream ở root không bị coi là pure DTO. Checker resolve theo tsconfig workspace, tiếp tục chặn dependency domain/platform và UI/MCP vào backend/database.

Hai router custom được compose trong Hono `server/src/app.ts`, sử dụng guard OpenBot. GET platform health công khai; domain routes và các route platform còn lại yêu cầu auth. Đây chưa phải implementation tenant/subject authorization nghiệp vụ.

Giữ source desktop, worker, agent mẫu, computer/supervisor và deployment assets để tránh cắt dependency. Không nhập upstream `.github` workflows hoặc `.claude`; CI dự án chạy check/build/tests, không có release/publish tự động. LICENSE và OPENBOT_README.md giữ attribution/hướng dẫn nguồn.

Các bảng/logic Vinhomes, Qdrant memory theo thiết kế dự án và AgentScope adapter vẫn là nhiệm vụ của các team. Không đồng nhất cơ chế memory/identity/governance upstream với toàn bộ mô hình đích mà chưa có mapping.

## 4. Làm việc với bản nguồn

Mở `E:\openbot-upstream` trong cửa sổ IDE riêng để tra cứu. Làm feature và gửi PR ở `E:\AI-Workforce-Platform`. Bản upstream đang detached để giữ baseline; việc port code thực hiện trên nhánh tích hợp của repo sản phẩm.

Các thành viên khác clone cùng URL và checkout cùng SHA theo [README sản phẩm](../../README.md#openbot). Không cần có checkout này để chạy scaffold hiện tại; sau tích hợp, sản phẩm cũng phải build độc lập, không tham chiếu `file:../openbot-upstream`.

Mỗi lần cập nhật baseline cần ghi SHA cũ/mới, phần đã port và kiểm thử liên quan. Source integration đã hoàn tất; cấu hình deployment và business features là các mốc tiếp theo.

## 5. Validation của nhánh tích hợp

- Bun frozen install, typecheck app/server/worker và Workforce strict typecheck: qua.
- Import boundary, Python Protocol smoke và 12 tests Workforce (route/auth/alias boundary): qua.
- Build app/server/worker: qua. Vite còn cảnh báo externalized Node modules từ dependencies và một số chunk lớn; chưa coi đây là chứng nhận runtime UI end-to-end.
- Full suite Windows chỉ root install: 3932 pass, 27 skip, 133 fail, 70 errors. Môi trường này thiếu test database, dependencies package ngoài workspace và có lỗi Windows path/symlink/subprocess; không báo full suite xanh.
- CI Linux có pgvector/PostgreSQL, migration và installs agent-bot/agent-langgraph/agent-mastra/desktop theo upstream để kiểm full suite đúng môi trường.
- Docker daemon local chưa chạy, credential Intelligence/model chưa cấu hình; chưa kiểm thử live chat, provider, database migration hay toàn bộ stack.

Kết quả CI trên commit được push là nguồn bổ sung cho validation; nhánh tích hợp cần review trước merge.
