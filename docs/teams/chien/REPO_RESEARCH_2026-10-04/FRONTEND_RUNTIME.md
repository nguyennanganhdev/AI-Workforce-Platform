# Frontend, runtime và khả năng phát hành — 2026-10-04

Snapshot đọc: workspace `dev_teamChien_HuyDo`, HEAD `a231575537759845e73b8f4c4124e5ef168b6aff`; remote refs sau fetch ngày 2026-10-04. Đây là audit code và kiểm tra cục bộ có phạm vi, không phải nghiệm thu staging/production. Không checkout nhánh khác, không khởi chạy dịch vụ, không đọc/in bí mật. Không tìm thấy AGENTS.md trong cây repo.

Trong lúc audit có tác nhân khác sửa `services/vinhomes-api/src/vinhomes_api/v3_coordination.py` và test tương ứng. Không đụng/chỉnh/ghi đè các thay đổi đó; commit evidence trong báo cáo vẫn gắn với a231575. Các tests frontend/runtime được liệt kê bên dưới không bao gồm các Python files đang sửa.

## 1. Kết luận từ code hiện tại

**Cư dân và Operations đã có đường chạy kết nối backend thật trong code.** Kết luận cũ “toàn bộ frontend chỉ mock/localStorage” không còn đúng ở snapshot này. `resident-app/src/main.tsx:32` chọn preview rõ ràng hoặc `ConnectedApp`; `resident-app/src/app/ConnectedApp.tsx:4` sử dụng `useConnectedResident`; `app/src/features/vinhomes-operations/layout/operations-layout.tsx:12` chọn preview hoặc `ConnectedOperations`.

Tuy nhiên phần giao diện vẫn chưa phủ toàn bộ nghiệp vụ và đường đóng gói/phát hành hiện tại chưa nối đủ backend Vinhomes. Không có bằng chứng live mới trong audit này để nói dự án đã được nghiệm thu production.

## 2. Các sản phẩm frontend khác nhau

| Package | Vai trò thật | Cổng/script và trạng thái code |
|---|---|---|
| `app` | OpenBot: người dùng, agent, kênh chat, plugins, computer, admin; đồng thời chứa UI Operations | `dev:openbot` 3010, `dev:operations` 3020; TanStack Router/Query, React, CopilotKit; nhiều API `/api/*` kết nối Hono |
| `resident-app` | App riêng cho cư dân: auth, chat Reception, gửi/yêu cầu xử lý, ảnh, trạng thái, xác nhận phương án/kết quả | Vite 3011; default connected, explicit preview riêng |
| `desktop` | Vỏ native Tauri/Rust cài và quản lý OpenBot local/container, chọn provider/harness, xử lý OAuth và lỗi thiết lập | Không thuộc root Bun workspaces; có workflow build riêng Windows/macOS/Linux |
| Các UI Operations preview | Diễn tập quy trình, persona, QC/field flows và layout cũ | `OperationsProvider` + mock datasets + localStorage; chỉ dùng khi người dùng chọn preview |

Root `package.json:7` chỉ khai báo workspaces `app`, `server`, `worker`, `resident-app`. Vì vậy root `typecheck`/`build` không tự bao phủ `desktop`, `supervisor`, `agent-computer` hay các harness ngoài danh sách.

## 3. Cư dân: tích hợp đã có và phần còn thiếu

- HTTP adapter `resident-app/src/services/resident-api.ts:11` gửi cookie qua `credentials: include` đến `/api/business`; lỗi HTTP có status riêng. Không tự chuyển sang mock khi API lỗi.
- `resident-app/src/services/use-connected-resident.ts:48` tải profile, chat, ticket và approvals từ server; profile phải ở database mode nếu không bật demo backend. Polling ở `:211` chạy mỗi 1,25 giây khi đang chờ assistant và khoảng 5 giây khi bình thường; tạm ngừng khi tab ẩn.
- `resident-app/src/app/App.tsx:82` lấy tên/căn hộ từ live profile; `:95` không load preview localStorage khi có adapter live; `:474` gửi draft qua live service; `:521` quyết định kết quả bằng API; `:529` hiển thị phương án cần cư dân đồng ý; `:668` truyền live profile cho màn tài khoản.
- Auth thật qua `/auth/login`, `/auth/session`, `/auth/register`, `/resident/me` (`resident-app/src/features/auth/auth-service.ts:24`). Người chưa được cấp membership được đưa đến trạng thái pending; administrator vào administration. Input UI được chuyển sang email cho backend hiện tại.
- Reset mật khẩu **chưa kết nối**: `resident-app/src/features/auth/auth-service.ts:39` cố ý throw thay vì báo đã gửi OTP/email.
- Danh mục/đặt tiện ích **chưa cung cấp trong connected UI**: `resident-app/src/features/utilities/Utilities.tsx:347` trả empty/unavailable state khi `connected`.
- Thông báo hiện được dựng từ ticket/request events, không đủ để kết luận có hệ thống push notification/feed quản trị độc lập.
- Không dùng số test preview để chứng minh auth/database live. `resident-app/tests/resident-service.test.ts` và `conversations.test.ts` chủ yếu kiểm tra local model; `app/tests/resident-connected-ui.test.tsx:55` render bằng `live` object được dựng trong test.

## 4. Operations: tích hợp đã có và phần chưa nghiệm thu

- `app/src/routes/_authed.tsx:14` preview là lựa chọn rõ ràng; `:23` gọi `/api/business/operations/me`; 401 quay lại login, 403 báo thiếu quyền, API lỗi không tạo admin giả. Staff chỉ đi vào ba trang công việc hợp lệ (`:34`). Tài nguyên và mutation vẫn do API bảo vệ.
- Operations tách khỏi CopilotKit/OpenBot provider (`app/src/routes/_authed.tsx:76`), nên không thể gọi hai UI là một đường agent runtime duy nhất.
- `ConnectedOperations.tsx:180` lấy identity từ server; `:203` tải tickets, catalogs, work orders, dashboard, sessions cần BQL duyệt, inquiries và knowledge candidates; `:224` tải session, hội thoại và ảnh của ticket. Refresh khoảng 5 giây (`:264`).
- UI có ticket inbox/triage, phân công, công việc cá nhân, sửa chữa/phương án, ảnh, chuyển trạng thái, resident consent/handover, QC và session-close approval. Chức năng báo cáo và team chat có live components (`workspace/LiveReportsPage.tsx:36`, `workspace/LiveTeamPage.tsx:8`). Admin accounts có HTTP implementation (`connected/ConnectedAccounts.tsx:8`).
- **Các route còn đánh dấu chưa nối đầy đủ**: security, sanitation, contractor, approvals và evidence (`connected/ConnectedOperations.tsx:340`, `:408`). `accounts` cũng nằm trong danh sách này nhưng được override bằng connected admin accounts nếu role admin, nên không nên báo accounts hoàn toàn thiếu.
- Các chức năng approvals/evidence có thể xuất hiện trong ticket detail; điều đó chưa chứng minh các màn dedicated `/operations/approvals`, `/operations/evidence` hoàn chỉnh.
- Preview giữ bộ rule lớn, QC/field flow và localStorage (`hooks/use-operations-data.ts:47`, `:281`); ảnh preview bị giới hạn để tránh quota. Preview RBAC route guard dựa persona local không thay thế server authorization.
- Polling hiện không có loading lock riêng cho toàn bộ `refresh/load` hoặc AbortSignal timeout trong các HTTP adapters frontend. Đây là điểm cần đo tải và tình huống backend chậm khi nhiều người dùng đồng thời; chưa phải lỗi production được tái hiện trong audit này.

## 5. Tiến độ frontend theo bằng chứng Git

| Ref/commit | Bằng chứng đóng góp | Giới hạn diễn giải |
|---|---|---|
| `origin/frontendNgoDinhKhanh` = `c400a45bb2886c22f13c27e7a1749672c5e2c60d` | Commit của Viet Anh Vu: neutral shadcn redesign; trước đó `a9ffb24` responsive mobile, `623eb78` field staff/BQL/inbox, `741d3d4` incident coordination chat | Tên nhánh không chứng minh author là Ngô Đình Khánh. `operations-layout` trên ref này vẫn bọc OperationsProvider mock; không được gán kết nối ở nhánh tích hợp cho branch này |
| `origin/frondendVuVietAnh` = `f760830e0bfa45482cb817ac7b9c03e277d23ded` | Merge develop V3 do ChienhocIT; commits chức năng `1b480ad`, `1e07aff`, `dee2a10`, `69352af`, `0ad5b80` do Viet Anh Vu về A5/history, role flows, tách entrypoint/cổng, invariant/QC | Có code/workflow demo nhưng merge DB không đồng nghĩa runtime API đã nối |
| `origin/frontend/ft-resident` = `e1b1c4db7c4132df1cc2d508338b30bd32a60e0a` | Có bootstrap ConnectedApp, auth, demo separation; nhánh đạt điểm tích hợp core trước các cải tiến sau đó | Không chứa toàn bộ cải tiến agent/repair flow mới của nhánh hiện tại |
| `d9cad41`, `2b9230d` — Huy-Nguyen-Chualambo | Conversations và role-based Operations, thống nhất work management và tài liệu handoff | Đây là commit evidence; không tự khẳng định nghiệm thu live |
| `ca48f46` — ChienhocIT | Nối core resident/operations với PostgreSQL V3 | Khởi đầu tích hợp; phải xem các commit tiếp theo |
| `c72e8a8`, `2324e74`, `499967a` — ChienhocIT | Password authentication; Reception và repair flow; hoàn thiện flow trong browser | Code tích hợp có thật, kiểm tra browser lịch sử cần đối chiếu artifact riêng |
| `4bea88f`, `67bae8f`, `d7ff712`, `db32a6a`, `034e41b` — ChienhocIT | BQL trả lời resident inquiry; knowledge review; safety guidance emergency; organisation/first accounts; Supervisor nhận handover | Có bước nối thêm Reception–BQL–Supervisor sau tích hợp core |
| `a231575` — ChienhocIT | Admin approval publish specialist và cung cấp cho Supervisor theo ticket category | HEAD workspace; cao hơn develop ở tính năng nối composition |

`git diff --stat origin/develop...HEAD -- app resident-app desktop supervisor agent-computer .github` chỉ cho 30 dòng bổ sung ở hai file frontend connected. Phần lớn frontend integration đã nằm trong `develop` được merge; không được coi là chỉ tồn tại ở nhánh riêng.

## 6. Runtime OpenBot và các vai trò dễ nhầm

**`supervisor/` khác Supervisor nghiệp vụ trong `agent-coordination/`.** `supervisor/src/index.ts:20` là container supervisor chỉ nhận ensure/stop/reset/list computer theo Bot, giữ Docker socket; không điều phối ticket cư dân. Supervisor nghiệp vụ phòng điều phối được UI đọc qua `/tickets/{id}/session` và `/sessions/*`.

- `agent-computer/`: browser Playwright, screenshot/live screen, shell/files workspace, per-Bot identity/profile, human take-wheel state. `authorisation.ts:54` chỉ mở health không cần auth; token được kiểm tra; `:86` tập acting paths chặn khi người đang giữ quyền điều khiển. Đây là runtime thực trong source, không phải chỉ hình minh họa.
- `supervisor/`: token bắt buộc (`index.ts:52`), tên/nhãn ownership (`docker.ts:175`), readiness thực qua health check thay vì chỉ container Running (`docker.ts:53`), networking/memory/PID controls (`docker.ts:446`). Không có passthrough Docker tổng quát.
- `environmentFor` chỉ chuyển các biến cần cho computer, không truyền toàn bộ server secrets (`supervisor/src/environment.ts:11`).
- Docker Compose giữ browser profiles/workspace bằng volumes, bind cổng loopback; gVisor/SPIRE có cấu hình. `COMPUTER_RUNTIME` để trống nghĩa là ordinary container chia sẻ kernel; không thể nói mọi môi trường đã bật gVisor/workload identity.
- `worker/src/index.ts:2` là vòng quét routines chạy mỗi 30 giây, dispatch về server và dọn queue; không phải worker tổng quát đã tự chạy toàn bộ ingestion/Reception/coordination/RAG. Ingestion directory job có module riêng nhưng sự tồn tại module không chứng minh nó được recurring worker entrypoint gọi.
- OpenBot chat chạy `/api/copilotkit` với session cookie (`app/src/lib/copilot/provider.tsx:31`), cần server config + Intelligence/provider thực tế. Các harness/Dockerfile có nhiều framework; source có nhiều lựa chọn không chứng minh đã acceptance từng provider.
- Live smoke opt-in: `tests/smoke/journey.test.ts:45` cần OPENBOT_SMOKE và credentials; computer live screen `agent-computer/tests/live-screen.test.ts:31` cần OPENBOT_LIVE_SCREEN. Docker lifecycle integration tự skip nếu engine unavailable (`supervisor/tests/docker.integration.test.ts:18`). Root test xanh có thể chưa chạy các checks này.

## 7. Chặn đóng gói và phát hành

### 7.1 Đường `/api/business` hiện phụ thuộc Vite proxy

`app/vite.config.ts:92` và `resident-app/vite.config.ts:4` proxy `/api/business` sang FastAPI 8000, bỏ prefix. App serve production/local desktop lại gửi mọi `/api/*` sang Hono 3001 (`app/serve.ts:221`). `server/src/app.ts:486` mount `/api/vinhomes`, `:490` mount `/api/vinhomes/v3`, nhưng không có mount/proxy `/api/business` tương ứng.

Chart ingress đang chỉ trỏ về service server (`charts/openbot/templates/ingress.yaml:37`); source chart không cung cấp route FastAPI Vinhomes/resident riêng. Với cấu hình checked-in đang đọc, built Operations dùng `/api/business` thiếu gateway đã thấy ở Vite. Có thể môi trường ngoài repo bổ sung reverse proxy, nhưng audit này chưa có bằng chứng đó.

### 7.2 Artifact chưa đóng gói resident/backend business đầy đủ

`server/Dockerfile:37` build `app`; `:60` copy `app/dist`. Root Dockerfile cũng copy app/dist (`Dockerfile:154`). Không có build/copy resident-app/dist vào hai image này; copy resident package.json để Bun workspace resolve không phải đóng gói resident site.

`services/vinhomes-api/docker-compose.demo.yml:1` chỉ có PostgreSQL pgvector service; không tự chạy API. Root docker-compose không có `vinhomes-api`/Reception business service. Cần composition/deployment story đầy đủ cho sản phẩm cư dân + Operations + agent nghiệp vụ.

### 7.3 CI tổng thể đang bị comment toàn bộ

`.github/workflows/ci.yml` có **0 dòng noncomment có nội dung**; các static/test/build/migration/image checks chỉ còn văn bản comment. `git log -- .github/workflows/ci.yml` có `0e48cd9` (DungPhanHoangg05) và snapshot `df8b4aa` (NguyenHoang151216); audit này không suy diễn trách nhiệm cá nhân cho tình trạng CI từ hai commit đó.

`publish-release.yml:111` vẫn dùng `uses: $/.github/workflows/ci.yml` cho gate release. Đây không phải cấu trúc local workflow `./.github/workflows/...` và file đích đang fully commented; chưa có cơ sở coi release gate này vận hành. Không chạy/publish release trong audit.

Desktop, desktop-signing và security/zizmor workflow còn nội dung active. Desktop workflow định nghĩa 3 OS, Tauri build, Rust tests (`desktop.yml:54`, `:103`, `:139`) và artifacts; sự tồn tại YAML không chứng minh GitHub Actions run thành công hay installer đã được người dùng nghiệm thu.

## 8. Kiểm tra đã chạy trong audit này

- `bun test resident-app/tests app/tests/connected-operations-ui.test.tsx app/tests/resident-connected-ui.test.tsx app/tests/operations-auth.test.ts app/tests/connected-accounts-list.test.tsx app/tests/operations-workspace.test.ts app/tests/operations-work-items.test.ts supervisor/tests/environment.test.ts supervisor/tests/environment-hardening.test.ts supervisor/tests/names.test.ts agent-computer/tests/authorisation.test.ts agent-computer/tests/egress.test.ts`: **90 pass, 0 fail, 320 assertions, 14 files**, khoảng 7,39 giây.
- `resident-app`: `bun run typecheck` pass.
- `app`: `bun x tsc --noEmit` pass (gọi trực tiếp để không chạy pretypecheck generate config).
- Connected UI tests dùng happy-dom, fake fetch hoặc object live dựng trong test (`app/tests/connected-operations-ui.test.tsx:52`, `app/tests/resident-connected-ui.test.tsx:55`). Các assertions kiểm tra contract/rendering/error handling, **không xác nhận request chạy qua Vite→FastAPI→PostgreSQL hoặc browser thật**.
- Chưa chạy frontend production build, native Tauri build, Docker build/lifecycle, live screen, provider smoke, live DB hoặc staging/browser end-to-end. Không mở dịch vụ chỉ để audit.

## 9. Bước tiếp theo để nghiệm thu

1. Bật lại CI thật và sửa gate reusable workflow trước khi coi release được bảo vệ.
2. Chốt deployment cùng origin cho resident + Operations + FastAPI `/api/business`, đóng gói resident site và agent business services; kiểm tra built app với cấu hình đó.
3. Chạy flow hai tài khoản/two browsers qua live PostgreSQL: resident submit → Reception handover → Supervisor/specialist → staff work → resident consent/confirmation → BQL closure; giữ request IDs, audit/state versions và DB proof.
4. Nghiệm thu riêng auth/membership/scope từ server, stale version/retry, file access, reset password và missing-feature routes.
5. Chạy Docker/computer lifecycle/provider smoke và đo tải polling/backend; không thay acceptance bằng unit tests hoặc sơ đồ ERD.

## 10. Kiểm tra bổ sung tại HEAD b2d3f37

Trong lúc nghiên cứu, tác nhân khác commit backend fixes khiến HEAD tiến từ `a231575` lên `b2d3f3725ec8e37e5986b13742c9d6211059ba72`. Phần audit ban đầu vẫn gắn với snapshot a231575. Kiểm tra bổ sung bên dưới đọc source/runtime và chạy suite ở checkout b2d3f37; `agent-coordination/src/vinhomes/backend.py` và `ports.py` đang WIP, không được sửa/ghi đè và không thuộc app test suite.

### 10.1 Computer resource và readiness chưa đủ làm production proof

- **Memory cap chỉ là tùy chọn ở Docker supervisor**: `supervisor/src/computer-memory-bytes.ts:4` và `:12` nói rõ unset/empty -> `bytes: undefined`; `supervisor/src/docker.ts:454` chỉ tạo HostConfig.Memory khi có memoryBytes. Không có cap không có nghĩa Docker hiện tại đã được inspect và thấy RAM=0; đây là kết luận từ đường cấu hình source.
- Root `docker-compose.yml` phần supervisor không truyền `COMPUTER_MEMORY_BYTES`; chỉ env_file `egress.env` và danh sách environment đã khai báo. Đặt biến này trong shell/.env của Compose mà không mapping/override tương ứng chưa đủ để supervisor container nhận cap. Không thay đổi compose trong audit.
- Không áp dụng kết luận này cho mọi triển khai: chart Kubernetes đã có `computers.resources.requests.memory: 1Gi` và `limits.memory: 4Gi` (`charts/openbot/values.yaml:283`).
- **Supervisor health không phải Docker readiness**: `supervisor/src/index.ts:86` trả `context.json({status: "ok", docker: await reachable()})` không đổi HTTP status khi Docker unavailable. Do đó source cho phép HTTP200 với `docker:false`; root Compose healthcheck (`docker-compose.yml:253`) chỉ `await fetch(...)`, không kiểm tra response.ok hay body.docker. Process có thể bị coi healthy dù không tạo được computer. Chưa chạy Docker hoặc tái hiện runtime trong audit.
- Per-computer readiness đã tốt hơn: `agent-computer/Dockerfile` và `supervisor/src/docker.ts:53` health command kiểm `r.ok`, supervisor chờ engine health trước khi handout. Điều đó không khắc phục health của container supervisor kể trên.
- Tests parser hiện tại chạy thêm: `bun test supervisor/tests/computer-memory-bytes.test.ts` **3 pass, 0 fail, 10 assertions**, bao gồm explicit assertion rằng unset/empty nghĩa là không có cap. Không đo RAM/tải, không inspect container thật.

### 10.2 Full app test suite vẫn fail; baseline cũ không được coi là số hiện tại

Chạy `bun test app/tests` trên Windows, Bun 1.3.14, HEAD b2d3f37; đặt `OPENBOT_SMOKE=0`, `OPENBOT_LIVE_SCREEN=0`, `OPENBOT_LIVE_COMPOSIO=0`. Scan app/tests trước khi chạy không thấy test gọi model/provider hoặc live DB; các serve tests dùng child/test fixture và loopback ports, được test cleanup. Không gọi root pretest/generate config, không sửa source và không fix các lỗi vừa thấy.

**Kết quả mới: 894 pass, 33 fail, 3.065 assertions; 927 tests/116 files; 102,43 giây; exit code 1.** Log đầy đủ: [app-tests-full.log](./app-tests-full.log). Con số lịch sử 48 failures/993 tests không tái hiện đúng; không dùng nó làm số hiện tại hoặc tính tỷ lệ dự án hoàn thành.

Breakdown từ failed-test list:

- **5 failures ở connected-operations-ui.test.tsx**: work list, team composer, report form, resident registration, staff login. Cùng 6 tests của file này đã pass trong lần chạy tập trung trước đó, và connected resident tests vẫn pass trong full suite. Kết quả phụ thuộc cách chạy nên cần điều tra test isolation/global DOM/fetch/module interactions; chưa đủ bằng chứng kết luận cả 5 hành vi sản phẩm đều bị lỗi runtime.
- **28 failures ở serve.test.ts**: port probes, path assertions, proxy/WebSocket startup. Log có lỗi child `Module not found "serve.ts"`. `app/tests/serve.test.ts:42` dùng `import.meta.dir.replace(/\/tests$/, "")` để chọn cwd: regex chỉ loại `/tests`, không loại `\tests` trong đường dẫn Windows hiện tại. Một nhóm assertion path trông đợi `/dist/...` trong khi source dùng node:path join trên Windows. Các proxy tests báo `proxy did not start`. Đây là bằng chứng test/portability failure; audit không sửa và chưa chứng minh serve product trên Linux có lỗi tương ứng.

Focused tests pass ở mục 8 vẫn là bằng chứng hẹp hợp lệ, nhưng **không được tổng quát hóa thành full frontend suite pass**. Full app suite hiện chưa xanh trên máy này.
