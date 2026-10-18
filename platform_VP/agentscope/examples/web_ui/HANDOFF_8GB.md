# Bàn giao tích hợp `web_ui_new` — máy RAM 8 GB

> Cập nhật tiếp quản Fuq-export: snapshot ban đầu clean tại `a82f400` trên `main`.
> Các đoạn trạng thái cũ bên dưới được giữ làm lịch sử. Native build, lint,
> backend build và browser fixture smoke đã pass; xem mục 21 của `KeHoach.md`
> và `MIGRATION_RUNBOOK.md`. Chưa nghiệm thu với FastAPI thật. Không dùng
> thông tin “chưa có Node/pnpm” hoặc “toàn bộ chưa commit” bên dưới làm trạng thái hiện tại.

Ngày bàn giao: 2026-10-17  
Nhánh làm việc: `web-ui-new-integration`  
Thư mục: `AI-Workforce-Platform/platform_VP/agentscope/examples/web_ui`

## 1. Trạng thái hiện tại

- Frontend từ `web_ui_new/frontend` đã được overlay vào frontend AgentScope.
- Đã giữ lại backend FastAPI, API/domain cũ và các file chỉ có trong AgentScope.
- Không copy hoặc sử dụng `web_ui_new/backend` Express.
- Đã bổ sung dependency và cập nhật `pnpm-lock.yaml`.
- Đã thêm kiểu `RoomEntry`, `RoomParticipant`, `RoomView` và adapter
  `workforceApi.room()` để các component chat/team mới compile được.
- `git diff --check` và parse JSON đã pass.
- Chưa chạy TypeScript build, lint, backend build, Docker hoặc browser test vì máy
  thực hiện migration không có Node.js/pnpm/Docker/WSL.
- Toàn bộ thay đổi đang **chưa commit**. Không dùng `git reset --hard`, không xóa
  file untracked và không chuyển sang nhánh khác trước khi lưu thay đổi.

Đọc thêm:

- `KeHoach.md`: checklist và nguyên tắc tích hợp.
- `MIGRATION_AUDIT.md`: ranh giới backend và các quyết định compatibility.

## 2. Blocker quan trọng

FastAPI hiện tại không có các contract mà một số màn hình mới yêu cầu:

```text
/admin/*
/workforce/console/studio/*
/workforce/console/builder/evaluate
/workforce/console/builder/conversations/{id}/progress
/workforce/console/sessions/{id}/room
```

Quy tắc xử lý:

1. Không đưa Express backend vào Compose.
2. Ưu tiên viết adapter frontend dùng endpoint FastAPI hiện có.
3. Nếu không thể map đầy đủ, giữ màn hình/flow AgentScope cũ và ẩn chức năng mới.
4. Chỉ bổ sung endpoint FastAPI khi đã xác nhận đó là yêu cầu sản phẩm, không sửa
   schema PostgreSQL/Redis/MinIO để né lỗi frontend.
5. `workforceApi.room()` hiện là chức năng tùy chọn; hook UI đã bắt lỗi và fallback
   về `null` nếu endpoint trả 404.

## 3. Thứ tự công việc còn lại

### Batch A — build frontend

1. Cài Node.js 22 LTS và pnpm qua Corepack.
2. Cài dependency theo chế độ ít song song.
3. Chạy TypeScript/Vite build.
4. Sửa hết lỗi compile trước khi chạy dev server.

PowerShell:

```powershell
cd C:\Users\huynx25\Coding\Fuq\AI-Workforce-Platform\platform_VP\agentscope\examples\web_ui
corepack enable
corepack prepare pnpm@latest --activate
$env:NODE_OPTIONS='--max-old-space-size=2048'
pnpm install --frozen-lockfile --child-concurrency=1 --network-concurrency=4
pnpm --filter frontend build
```

Nếu build bị thiếu RAM, đóng VS Code extensions/browser không cần thiết và thử:

```powershell
$env:NODE_OPTIONS='--max-old-space-size=1536'
pnpm --filter frontend exec tsc -b
pnpm --filter frontend exec vite build
```

Không chạy `pnpm dev`, backend và Docker cùng lúc trong batch này.

### Batch B — lint và test nhẹ

Chạy tuần tự, không chạy song song:

```powershell
pnpm --filter frontend lint
pnpm --filter frontend exec node --test tests/chat-events.test.mjs
pnpm --filter frontend exec node --test tests/client.test.mjs
pnpm --filter frontend exec node --test tests/session-office.test.mjs
pnpm --filter frontend exec node --test tests/session-presentation.test.mjs
pnpm --filter backend build
```

Ghi riêng lỗi có sẵn và lỗi do migration. Không dùng `eslint --fix` trên toàn bộ
repository trước khi xem diff.

### Batch C — API compatibility

Đối chiếu lần lượt:

- `src/api/client.ts`: base URL, refresh 401, cookie, timeout và abort signal.
- `src/api/session.ts`, `useMessages.ts`, `useSessions.ts`: session CRUD, SSE,
  reconnect và interrupt.
- `src/api/workforce.ts`: builder/leader dùng FastAPI hiện có.
- `src/api/studio.ts`, `src/api/admin.ts`: không được để UI chính gọi endpoint 404.
- Upload workspace/knowledge phải giữ multipart và progress hiện tại.

Quyết định rõ cho `/workforce/agents`:

- Viết adapter từ Studio UI sang `agentApi`/`workforceApi` hiện có; hoặc
- route về màn hình AgentScope tương thích và để Studio UI sau feature flag.

Không đánh dấu phase này hoàn tất nếu tab Agent management còn trả API 404.

### Batch D — smoke test không Docker

Chỉ khởi động frontend và FastAPI cần thiết. Kiểm tra tối thiểu:

- Landing, đăng ký, đăng nhập, restore session và đăng xuất.
- Chat, streaming, cancel và session CRUD.
- Upload, tool call/result và reload session.
- Workforce leader/builder.
- MCP, Skill, Knowledge, Credential, Channel và Schedule.
- Deep link và ba locale `vi`, `en`, `zh`.
- Không có request `/api/api/...`.

### Batch E — Docker/Compose cuối cùng

Máy 8 GB chỉ chạy batch này sau khi native build pass. Tắt dev server trước khi
build image và chạy từng lệnh:

```powershell
cd C:\Users\huynx25\Coding\Fuq\AI-Workforce-Platform\platform_VP\agentscope
docker compose config --quiet
docker compose build
docker compose up -d
```

Nếu Docker Desktop làm máy thiếu RAM, chuyển Compose/E2E sang CI hoặc máy mạnh hơn;
không tăng pagefile rồi chạy đồng thời IDE, browser và toàn bộ service.

## 4. Tiêu chí được phép commit

- Frontend build pass.
- Backend package không bị ảnh hưởng.
- `git diff --check` pass.
- Không có `.env`, token, key hoặc credential trong diff.
- Các route chính không gọi endpoint chưa tồn tại.
- Ít nhất smoke test login, chat streaming và session CRUD pass.
- Cập nhật checkbox và nhật ký trong `KeHoach.md` với lệnh/kết quả thực tế.

Sau đó commit theo batch nhỏ, ví dụ:

```text
feat(web-ui): integrate new frontend shell and chat UI
fix(web-ui): adapt workforce UI to FastAPI contracts
test(web-ui): validate migrated frontend flows
```

## 5. Rollback

Baseline trước migration là commit `af66bae`. Nhánh hiện tại được tạo từ baseline
đó. Không xóa volume PostgreSQL, Redis hoặc MinIO khi rollback. Vì thay đổi hiện
chưa commit, hãy tạo commit tích hợp sau khi build pass trước khi thử các thay đổi
rủi ro tiếp theo.

## 6. Báo cáo khi bàn giao tiếp

Ghi vào `KeHoach.md`:

- Commit hash.
- Lệnh đã chạy và kết quả pass/fail.
- Lỗi pre-existing và lỗi migration.
- Endpoint nào đã adapter, endpoint nào còn blocker.
- Flow nào đã smoke test.
- Cấu hình RAM/Node/Docker đã sử dụng.
