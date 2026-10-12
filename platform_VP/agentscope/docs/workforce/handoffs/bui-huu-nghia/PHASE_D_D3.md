# Bàn giao D3 — Bùi Hữu Nghĩa

Ngày: **2026-10-12**. Branch `feat/wf-builder`.
Baseline: `278ea4a3a4a62b79b290d2e9fc6bf24d33ba06a7` (PR #68, có C7/D0–D2).
**D3 consumer theo [PLAN_D3.md](PLAN_D3.md) đã merge vào `develop2`.**
Implementation commit `f1f195f`; PR [#71](https://github.com/nguyennanganhdev/AI-Workforce-Platform/pull/71)
đã merge tại `58c00f2`. Builder D3 đã được bổ sung vào workflow Phase D sau
merge. Không từ đó suy diễn PostgreSQL canonical-write hoặc toàn Phase D đã
hoàn thành.

## Kết quả và thay đổi

- Thêm **34 backend regression tests**, tái dùng fixtures/schema và SQL consumer
  seam A/B/C3; không copy test C3 hay provider của owner khác.
- Test missing-capability/pin drift/disable tại prepare, confirm và prewrite;
  kiểm tra current vs exact old pin, query fallback, mapping/ordering hash,
  forged reference và đủ 4 chiều Scope. Builder loader raise nếu gọi normalization.
- Test reuse/resume/revise/repair/clarify, thiếu metadata, mixed batch,
  availability thay đổi; spy assert Scope/profile/policy/revision truyền port.
- Test concurrency qua `asyncio.Event` và bounded wait: idempotency, hai edit,
  confirm replay, edit/confirm/cancel xen kẽ, failure/cancel/timeout retry và
  hai instance phản ứng với các conflict canonical port.
- Thêm **4 case browser D3**, dùng lại 4 behavior tests A/B: refresh cần confirm
  lại, permission failure, optional missing, late response sau cancel. Demo
  client mới chỉ trong `builder/tests/`, không export vào production.

### Lỗi Builder được tái hiện và sửa

`ReuseMatcher` gặp candidate `reuse_status=draft`, `draft_id=None`:

1. Nếu candidate còn old published `version_id`, trước fix đề xuất **reuse**.
2. Nếu candidate còn thiếu capability, trước fix đề xuất **revise**.
3. Cả hai có thể khiến proposal được confirm dù chưa có reference để tiếp tục
   draft đang xây.

Fix tối thiểu trong `_reuse_matcher.py`: trạng thái draft phải có `draft_id` mới
resume. Nếu thiếu thì **clarify + CANDIDATE_METADATA_REQUIRED**, giữ agent_id cũ
và block confirm. Không sửa DTO/port, provider Lifecycle hoặc canonical writer.
Regression có ba biến thể: thiếu toàn bộ reference, còn old version, thiếu capability.

## Files và API

Đường dẫn từ `platform_VP/agentscope/`:

- Backend: `src/agentscope/app/workforce/builder/_reuse_matcher.py`.
- Tests: `tests/workforce/builder/phase_d/`: `__init__.py`, `_fixtures.py`,
  `test_missing_capability.py`, `test_reuse.py`, `test_concurrent_build.py`, `test_ui.py`.
- Demo: frontend `src/features/workforce/builder/tests/fakeClient.ts`, `demo.tsx`.
- Handoff: `PLAN_D3.md`, `TEST_MATRIX_D3.md`, `PHASE_D_D3.md`,
  `INTEGRATION_REQUEST_BHN_D3.md`, README và STATUS trong thư mục Nghĩa.

**Không thêm public export/API/DB table/migration/dependency.** Production UI
Builder không đổi; chỉ mở rộng test/demo client. Core Builder import vẫn không
eager-load SQLAlchemy. Toàn bộ diff thuộc Nghĩa.

## Cách chạy và bằng chứng

Từ `platform_VP/agentscope`, dùng môi trường `.venv` đã có:

```powershell
.\.venv\Scripts\python.exe -m unittest tests.workforce.builder.phase_d.test_missing_capability tests.workforce.builder.phase_d.test_reuse tests.workforce.builder.phase_d.test_concurrent_build -v
.\.venv\Scripts\python.exe -m unittest tests.workforce.builder.async_capabilities.test_phase_a tests.workforce.builder.async_capabilities.test_phase_b tests.workforce.builder.phase_c.test_integration tests.workforce.builder.phase_d.test_missing_capability tests.workforce.builder.phase_d.test_reuse tests.workforce.builder.phase_d.test_concurrent_build tests.workforce.foundation.test_contracts -q
.\.venv\Scripts\python.exe -m unittest tests.workforce.registry.event_protocols.test_protocols tests.workforce.registry.event_protocols.test_phase_b tests.workforce.registry.event_protocols.test_phase_c tests.workforce.registry.event_protocols.test_phase_c_postgres tests.workforce.foundation.phase_d.test_runtime_resilience -q
.\.venv\Scripts\python.exe -m black --check src/agentscope/app/workforce/builder/_reuse_matcher.py tests/workforce/builder/phase_d
.\.venv\Scripts\python.exe -m compileall -q src/agentscope/app/workforce/builder tests/workforce/builder
git diff --check
```

Browser demo, từ `examples/web_ui/frontend`, dùng Node/toolchain đã cài:

```powershell
node node_modules/vite/bin/vite.js --config src/features/workforce/builder/tests/vite.demo.config.mjs --configLoader native --host 127.0.0.1 --port 5183 --strictPort
```

Ở terminal khác, từ `platform_VP/agentscope`:

```powershell
$env:BUILDER_UI_TEST_URL='http://127.0.0.1:5183/src/features/workforce/builder/tests/demo.html'
.\.venv\Scripts\python.exe -m unittest tests.workforce.builder.phase_d.test_ui.BuilderD3UiTests -v
```

Browser suite dùng Playwright đã cài + Microsoft Edge headless, không tải browser
mới. Ban đầu sandbox chặn subprocess (`WinError 5`, 0 test); đã chạy lại ngoài
sandbox theo approval và **8/8 pass**. Không ghi đè screenshot Phase B.

Checks frontend từ frontend root:

```powershell
node node_modules/eslint/bin/eslint.js src/features/workforce/builder/tests/fakeClient.ts src/features/workforce/builder/tests/demo.tsx
node node_modules/typescript/bin/tsc --ignoreConfig --noEmit --jsx react-jsx --module ESNext --target ES2022 --moduleResolution bundler --resolveJsonModule --allowSyntheticDefaultImports --skipLibCheck src/features/workforce/builder/tests/fakeClient.ts
```

| Kiểm tra | Kết quả |
|---|---|
| Backend D3 | **34 pass** (11 missing/pin + 11 reuse + 12 concurrency) |
| Builder A/B/C3/D3 + Foundation contracts | **100 pass** |
| Browser D3/demo | **8 pass**, gồm 4 new cases và 4 reused behavioral checks |
| Registry + D1 | **32 pass, 1 PostgreSQL skip** (30 Registry + 2 D1) |
| Black changed Python / compileall / import core / ESLint / focused TypeScript | Pass |
| Whitespace / owned-path audit | Pass; chỉ 4 vùng Nghĩa |

TypeScript 6 yêu cầu `--ignoreConfig` khi truyền file trực tiếp; lần chạy đầu
thiếu cờ này báo TS5112, đã sửa lệnh và pass. Không thay tsconfig chung để chạy.
Không chạy/install pytest, không đổi package/lockfile của team.

## Giới hạn bàn giao

1. **Scope D3 là consumer Builder.** Proposal session/lock vẫn process-local,
   confirm không tạo draft/agent và không reserve canonical identity.
2. Hai-instance tests dùng contract double để mô phỏng writer bên ngoài thắng
   và trả `AGENT_ALREADY_EXISTS` / `AGENT_BUILD_IN_PROGRESS` / `REUSE_DECISION_STALE`.
   Evidence chứng minh refresh/reconfirm, không chứng minh unique constraint DB.
3. Protocol provider, SQL repository, C1 UOW và Lifecycle validator chạy thật
   qua SQLite facade của C3. Catalog/reuse/model/policy resolver và caller/draft
   spy vẫn test-only; không có production fake mới.
4. Chưa có PostgreSQL test DSN; local environment checker vẫn thiếu `aiosqlite`
   và `pytest` như khi lập plan. Không tuyên bố PostgreSQL concurrency/CAS hoặc
   migration/CI pass từ SQLite/tests này.
5. Current pin recheck không atomic với canonical draft-write, không phát hiện
   mọi ABA/disable→enable giữa hai lần đọc. Writer Lifecycle/composition phải
   giữ transaction/identity invariants; Nghĩa không viết hộ writer.
6. PermissionError còn dùng chung cho disable/wrong Scope: consumer chặn;
   không phân loại bằng message, không chuyển wrong Scope thành “bật MCP rồi tiếp tục”.
7. Browser evidence là demo fake, không xác nhận Builder HTTP production. Không
   chạy lại C6 full E2E/production runtime, không nhận task D3 của Dũng hay D4 của Anh.

Không cần chờ output D4 của Anh để review D3 consumer này. Các request phối hợp
(CI/canonical writer evidence) nằm trong [INTEGRATION_REQUEST_BHN_D3.md](INTEGRATION_REQUEST_BHN_D3.md).

## Output cho lượt kế tiếp

- **Tiến Anh/D4**: dùng ma trận reuse/metadata/canonical-conflict và pin prewrite
  để chạy publish/long-wait/stale-evaluation/rollback của Lifecycle. DRAFT thiếu
  reference sẽ bị Builder block, provider cần trả metadata đầy đủ.
- **Dũng/D3/E2E**: dùng controlled schedules/repro và invariants ở
  [TEST_MATRIX_D3.md](TEST_MATRIX_D3.md); full actual writes/recovery thuộc lane owner.
- **Chí Hoàng**: owner suite Builder D3 đã được thêm vào CI sau khi PR #71
  merge; vẫn cần cung cấp môi trường PostgreSQL nếu nghiệm thu canonical-write DB.

Trạng thái Git hiện hành: implementation `f1f195f` đã merge qua PR #71 vào
`develop2` tại `58c00f2`; tài liệu này là nguồn bàn giao đã đồng bộ sau merge.
