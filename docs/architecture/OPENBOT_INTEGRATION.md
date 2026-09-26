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

Đã hoàn tất tải source, kiểm tra manifest/layout/license và ghi baseline. **Chưa cài dependency, tạo `.env`, chạy Docker, migration, build/test upstream hoặc ghép code vào repo sản phẩm.** Clone source không yêu cầu model key hay tài khoản dịch vụ.

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

## 3. Mapping cần triển khai

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

Scaffold sản phẩm hiện dùng Node 24/npm, một root package và strict import boundaries. Upstream dùng Bun workspace, có thư viện/auth/schema riêng. Bước nhập source phải xử lý các khác biệt này; `npm ci` ở repo sản phẩm chưa cài được OpenBot trong checkout bên cạnh.

Các bảng/logic Vinhomes, Qdrant memory theo thiết kế dự án và AgentScope adapter vẫn là nhiệm vụ của các team. Không đồng nhất cơ chế memory/identity/governance upstream với toàn bộ mô hình đích mà chưa có mapping.

## 4. Làm việc với bản nguồn

Mở `E:\openbot-upstream` trong cửa sổ IDE riêng để tra cứu. Làm feature và gửi PR ở `E:\AI-Workforce-Platform`. Bản upstream đang detached để giữ baseline; việc port code thực hiện trên nhánh tích hợp của repo sản phẩm.

Các thành viên khác clone cùng URL và checkout cùng SHA theo [README sản phẩm](../../README.md#openbot). Không cần có checkout này để chạy scaffold hiện tại; sau tích hợp, sản phẩm cũng phải build độc lập, không tham chiếu `file:../openbot-upstream`.

Mỗi lần cập nhật baseline cần ghi SHA cũ/mới, phần đã port và kiểm thử liên quan. Git clone đã hoàn tất; cài/chạy upstream và nhập source là các mốc triển khai tiếp theo, chưa được đánh dấu hoàn thành.
