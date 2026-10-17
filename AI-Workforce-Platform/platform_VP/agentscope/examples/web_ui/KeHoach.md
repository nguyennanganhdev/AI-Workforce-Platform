# Kế hoạch tích hợp `web_ui_new` vào AgentScope Platform

## 1. Mục tiêu

Tích hợp frontend từ `/home/jiuka13a/Coding/Project/web_ui_new` vào frontend hiện tại của `/home/jiuka13a/Coding/Project/AI-Workforce-Platform`, thay thế UI trong `examples/web_ui` nhưng giữ nguyên khả năng hoạt động của AgentScope Platform.

## 2. Quyết định đã chốt

- Dùng React 19 + Vite của `web_ui_new`.
- Ưu tiên UI system, component và design token của `web_ui_new`.
- Giữ nguyên AgentScope FastAPI backend, API contract, auth, session, SSE/streaming và business logic.
- Không thay đổi schema/dữ liệu PostgreSQL/pgvector, Redis và MinIO.
- Không dùng `web_ui_new/backend` Express để thay thế AgentScope backend.
- Giữ React Router và URL/deep link hiện có.
- Giữ React Query và các pattern data-fetching ổn định của UI cũ khi cần.
- Giữ toàn bộ locale hiện có.
- Responsive mobile-first, hỗ trợ modern evergreen browsers.
- Mục tiêu accessibility: WCAG 2.1 AA.
- Chạy được bằng Docker Compose trên máy RAM 8 GB.
- Không commit secrets hoặc file `.env`.
- Mọi thay đổi phải có khả năng rollback.

## 3. Nguyên tắc tích hợp

Không copy đè mù toàn bộ `web_ui_new/frontend/src` lên UI cũ.

1. Tách UI/design system mới khỏi API/domain.
2. Giữ hoặc port API client và domain hooks tương thích với AgentScope backend.
3. Dùng adapter khi request/response shape khác nhau.
4. Tích hợp theo từng nhóm màn hình, mỗi nhóm phải build/test được.
5. Không chỉnh backend để bù lỗi mapping frontend nếu sửa được bằng adapter.
6. Không xóa UI cũ trước khi nhóm tương ứng pass validation.

## 4. Checklist tổng quan

- [x] Đã thảo luận và chốt kế hoạch.
- [x] Xác định đây là frontend replacement, không thay backend.
- [x] Xác định AgentScope FastAPI là backend chính.
- [x] Chốt API, URL, i18n, React Query, Docker và rollback constraints.
- [x] Tạo branch tích hợp (`web-ui-new-integration`).
- [ ] Đóng băng baseline UI hiện tại.
- [x] Audit cấu trúc và API contract (xem `MIGRATION_AUDIT.md`).
- [ ] Hoàn tất adapter/API layer.
- [ ] Hoàn tất shell, auth và routing.
- [ ] Hoàn tất chat và session.
- [ ] Hoàn tất agent và workforce.
- [ ] Hoàn tất task, permission và tool events.
- [ ] Hoàn tất MCP, Skill, Knowledge, Credential, Channel và Schedule.
- [ ] Hoàn tất Docker/Compose/nginx integration.
- [ ] Hoàn tất smoke test và E2E/browser validation.
- [ ] Hoàn tất nghiệm thu parity và chuyển mặc định sang UI mới.

> Sau mỗi phase hoặc batch, phải cập nhật checkbox, commit/hash, build/test và blocker trong file này.

## 5. Phase 0 — Tạo điểm rollback

- [x] Kiểm tra Git status, không có thay đổi local trước khi tích hợp.
- [x] Tạo branch `web-ui-new-integration`.
- [ ] Ghi commit baseline.
- [x] Xác nhận `.env` và secret không nằm trong diff.

## 6. Phase 1 — Đóng băng baseline

Chạy từ `platform_VP/agentscope/examples/web_ui`:

```bash
pnpm install --frozen-lockfile
pnpm --filter frontend build
pnpm --filter backend build
```

Kiểm tra và ghi nhận:

- [ ] Anonymous, landing/auth, register, login, refresh session, logout.
- [ ] Chat, tạo/đổi/rename/xóa session, streaming response.
- [ ] Agent list/detail/create/edit/delete và agent builder.
- [ ] Workforce leader, team activity, task và permission.
- [ ] Tool call/result, upload/workspace.
- [ ] MCP, Skill, Knowledge, Credential, Channel, Schedule.
- [ ] Deep link, locale, responsive và error states.

Kết quả cần lưu: commit/tag baseline, lệnh build, flow đã kiểm tra và issue pre-existing.

## 7. Phase 2 — Audit và mapping source

### Build/config

- [ ] So sánh `package.json`, `pnpm-lock.yaml`, `pnpm-workspace.yaml`.
- [ ] So sánh `vite.config.ts`, `tsconfig.*`, `Dockerfile`, `nginx.conf`.
- [ ] Loại dependency chỉ phục vụ Express backend khỏi frontend build.

### API và hooks

- [ ] Mapping `api/client.ts`, `auth.ts`, `chat.ts`, `session.ts`, `agent.ts`.
- [ ] Mapping `workforce.ts`, `workspace.ts`, `mcp.ts`, `skill.ts`.
- [ ] Mapping `knowledgeBase.ts`, `credential.ts`, `channel.ts`, `schedule.ts`.
- [ ] Kiểm tra access token, HttpOnly refresh cookie và retry 401.
- [ ] Kiểm tra SSE/streaming, abort, upload/multipart và error mapping.
- [ ] Mapping `useAgents`, `useSessions`, `useMessages`, `useWorkspace`.
- [ ] Mapping `useTeamActivity`, `useChannels`, `useKnowledgeBases`.
- [ ] Mapping `useMCPs`, `useSkills`, `useCredentials`, `useSchedules`.

### Routing phải giữ hoặc có mapping

```text
/
/chat
/chat/:agentId?
/chat/:agentId?/:sessionId?/:memberId?
/workforce/leader
/workforce/builder
/workforce/agents
/workforce/agents/:agentId
/schedule
/channel
/credential
/mcp
/mcp/:hubId
/skill
/skill/:hubId
/knowledge
/knowledge/:kbId
/settings
/agents/*
/setup
```

Kết quả cần lưu: bảng old UI → new UI, API/hook cần giữ, adapter cần viết, route mapping và rủi ro.

## 8. Phase 3 — Adapter/API layer

- [ ] Chuẩn hóa API base URL dev/Docker.
- [ ] Xác nhận không sinh `/api/api/...`.
- [ ] Giữ login/register/refresh/logout/me, cookie credentials và access token.
- [ ] Giữ request/response types, SSE event parsing và upload.
- [ ] Mapping 401/403/404/409/500/timeout.
- [ ] Viết adapter cho khác biệt hook/UI.
- [ ] Dùng type guard, không dùng `any` để bỏ qua lỗi.

Tiêu chí: compile pass, không request sai path, auth/session restore hoạt động, streaming không treo/mất event.

## 9. Phase 4 — Shell, auth và routing

- [ ] Chuyển design system/token của `web_ui_new`.
- [ ] Tích hợp app shell/layout/navigation.
- [ ] Giữ landing/auth flow cho anonymous nếu đang dùng.
- [ ] Giữ redirect sau login, logout và redirect anonymous.
- [ ] Giữ deep link khi refresh và route error boundary.
- [ ] Kiểm tra responsive và keyboard/focus.

## 10. Phase 5 — Chat và session

- [ ] Chat layout, session list và session CRUD.
- [ ] Gửi message, streaming, abort/cancel.
- [ ] Markdown/code/mermaid.
- [ ] Tool call/result.
- [ ] Upload attachment.
- [ ] Restore sau reload.
- [ ] Empty/loading/error states.

## 11. Phase 6 — Agent và workforce

- [ ] Agent list/detail/create/edit/delete.
- [ ] Agent builder.
- [ ] Leader, team/workforce roster, team activity.
- [ ] Workforce events.
- [ ] Agent office/graph nếu nằm trong phạm vi UI mới.
- [ ] Permission và capability policy.

## 12. Phase 7 — Task, permission và tool events

- [ ] Create task/work.
- [ ] Required tracking checks và verified status.
- [ ] Approve/reject/bypass operation.
- [ ] External operation status.
- [ ] Timeout và yêu cầu xử lý bổ sung.
- [ ] Không mất event khi stream reconnect.

## 13. Phase 8 — Module còn lại

- [ ] MCP hub browse/install/configure.
- [ ] Skill hub browse/install/use.
- [ ] Knowledge base CRUD, upload/indexing/status.
- [ ] Credential CRUD.
- [ ] Channel CRUD.
- [ ] Schedule CRUD.
- [ ] Admin/domain/area nếu UI mới thay thế.
- [ ] i18n locale/fallback.

## 14. Phase 9 — Docker, nginx và Compose

- [ ] Giữ context Compose tại `examples/web_ui`.
- [ ] Không thêm backend Express vào Compose chính.
- [ ] Giữ `app` AgentScope, Redis, PostgreSQL và MinIO.
- [ ] Nginx proxy `/api/` tới `app:8000`.
- [ ] Kiểm tra cookie path và credentials.
- [ ] Xác nhận `VITE_API_BASE_URL` không gây CORS hoặc `/api/api`.
- [ ] Tối ưu build cho RAM 8 GB.
- [ ] Không commit `.env`.

```bash
docker compose config --quiet
docker compose build web
docker compose up -d web
curl -I http://localhost:5173
curl http://localhost:8000/health
```

Tiêu chí: container build pass, app shell trả 200, `/api/*` proxy đúng, cookie/deep link hoạt động và không cần Express backend.

## 15. Phase 10 — Build, lint và test

```bash
pnpm install --frozen-lockfile
pnpm --filter frontend build
pnpm --filter backend build
pnpm format:check
```

- [ ] TypeScript build pass.
- [ ] Frontend lint/format pass.
- [ ] Backend package không bị ảnh hưởng.
- [ ] Test hiện có pass theo chính sách must-pass.
- [ ] Phân loại lỗi pre-existing và lỗi do migration.

## 16. Phase 11 — Smoke/E2E/browser validation

- [ ] Anonymous mở landing/auth.
- [ ] Register/login/refresh/logout.
- [ ] Chat một agent và nhận streaming.
- [ ] Tạo/đổi/xóa session.
- [ ] Tạo/sửa/xóa agent.
- [ ] Agent builder và workforce/team.
- [ ] Task, approve/reject/bypass permission.
- [ ] Tool call/result và upload file.
- [ ] MCP/Skill/Knowledge.
- [ ] Credential/Channel/Schedule.
- [ ] Deep link, responsive, locale.
- [ ] Không lỗi console nghiêm trọng.
- [ ] Không API 404 do mapping sai.
- [ ] Không mất cookie/session.
- [ ] Không treo SSE.

Tiêu chí cuối: feature parity với baseline và smoke/E2E flow chính pass.

## 17. Phase 12 — Nghiệm thu và chuyển mặc định

- [ ] Đối chiếu checklist baseline với UI mới.
- [ ] Đóng tất cả blocker.
- [ ] Xác nhận Compose chạy trên RAM 8 GB.
- [ ] Xác nhận rollback procedure.
- [ ] Chuyển build/Compose mặc định sang UI mới.
- [ ] Giữ branch/commit fallback UI cũ.
- [ ] Cập nhật hướng dẫn chạy dự án.
- [ ] Ghi commit tích hợp và kết quả nghiệm thu.

## 18. Rollback plan

1. Dừng rollout UI mới.
2. Giữ nguyên backend và dữ liệu.
3. Revert commit frontend integration hoặc checkout baseline.
4. Build lại image `web`.
5. Khởi động lại riêng service `web`.
6. Kiểm tra `/health`, login và chat.
7. Ghi nguyên nhân và xử lý vào file này.

Không xóa volume PostgreSQL, Redis hoặc MinIO khi rollback.

## 19. Nhật ký thực thi

| Ngày | Phase/batch | Thay đổi chính | Build/test | Commit | Blocker |
|---|---|---|---|---|---|
| 2026-10-17 | Lập kế hoạch | Chốt thay frontend, giữ backend/API/data | Chưa chạy integration | Chưa có | Chưa có |
| 2026-10-17 | Phase 0-4 / frontend overlay | Chuyển design system, chat UI, locale, assets và các module UI mới; giữ router, workforce adapter/page và các module AgentScope-only | `git diff --check` pass; chưa thể build do môi trường không có Node/pnpm/Docker/WSL | Chưa commit | Thiếu toolchain để build, lint, Compose và browser smoke test |

## 20. Quy tắc bàn giao

Agent tiếp theo phải:

> Hướng dẫn thao tác chi tiết cho máy RAM 8 GB: `HANDOFF_8GB.md`.

1. Đọc file này trước khi sửa code.
2. Kiểm tra Git status.
3. Xem checklist phase đang làm.
4. Chỉ xử lý batch được giao.
5. Sau khi xong cập nhật checkbox, nhật ký, build/test, commit/hash và blocker.
6. Không đọc hoặc commit secrets từ `.env`.
7. Không thay backend/data nếu batch không yêu cầu rõ ràng.
