# Trạng thái — Phó Tiến Anh

Ngày kiểm tra: 10/10/2026.

Tên thành viên / branch: Phó Tiến Anh / `feat/wf-lifecycle` /

## Phase A — đầu ra phần Tiến Anh

Đã hoàn thiện schema handoff và consumer contract tests trong lane:
[BASELINE_PHASE_A.md](BASELINE_PHASE_A.md),
[schema bundle](phase_a/schemas.json), export `phase_a_schema_bundle()`.
Schema sinh từ shared DTO/owned aggregates hiện tại; policy chi tiết là proposal
cho owner chung, không thêm DTO production song song. Full protocol payload,
shared policy DTO và provider port promotion chưa được owner xác nhận merge.

Kiểm tra hiện tại: `PYTHONPATH=src .venv/bin/python -m pytest
 tests/workforce/lifecycle -q`: **45 passed, 12 subtests passed**.
Phase B logic đã có; Phase C wiring/runtime thật và Phase D nghiệm thu tích hợp
vẫn chưa hoàn tất. Phase A toàn nhóm chưa được xác nhận chấp thuận contract.

## Phần việc đã triển khai trong lane

| Task | Implementation và bằng chứng |
|---|---|
| PTA-01 | SQL repository/metadata, scoped identity/draft/version/deployment, canonical hash, CAS/catalog fencing, immutable inserts; tests PostgreSQL |
| PTA-02 | Static validation schema/capability/binding/effect/model reference, resource port cho credential/KB/skill/policy; reject secret/roster và drift |
| PTA-03 | Owner-controlled immutable golden case content; suite version/hash; lifecycle-patterns-v1 và travel-v1, mock peer/test context tách manifest |
| PTA-04 | Enqueue eval + snapshot atomic qua JobPort UoW; report/case persist từng bước, stable isolated case_run_id; restart/cancel/error tests |
| PTA-05 | Deterministic trace/schema/approval/budget/audience/provider assertions; optional quality judge sau hard gates; cost/latency/repeat variance |
| PTA-06 | Gate v1 versioned: completion >= 90%, tool/argument checks >= 95%, zero hard-gate violations; thiếu evidence fail closed |
| PTA-07 | Explicit single/selected publish, gate regrade, snapshot/revision/hash/profile/tool/policy/resource checks, immutable candidate ID, atomic deployment/outbox và idempotency |
| PTA-08 | Fork/settings/edit/diff/history/re-eval/rollback; deployment pointer đổi, version cũ còn nguyên |
| PTA-09 | PublishedCatalogPort lấy toàn thư viện manager, không filter batch; candidate unavailable/archived bị loại |
| PTA-10 | Ba pages + batch component + async report; Settings cấu hình JSON có prompt/model/tool/KB/skill/policy; polling, lỗi stale, selection và idempotent retry; 6 UI tests |
| PTA-11 | AgentReusePort, canonical catalog, ready/draft/inactive/blocked/uncertain, legacy mapping qua verified-owner adapter; không clone/publish legacy để bypass eval |
| PTA-12 | Server-side profile/business key, scope unique constraint, decision revision recheck, same identity revise và pending draft resume; concurrency tests PostgreSQL |
| PTA-13 | BuildBatchPort, independent item state/draft/eval, all-reuse không thêm identity/version, atomic selections và history delete giữ agent/version |
| PTA-14 | Validate policy/protocol coverage, freeze policy/full protocol/tool/resource evidence trong evaluation và version; reject stale eval |
| PTA-15 | Golden response-only/interactive/external-tracking/unknown/two-ticket cases; deterministic per-turn gates cho state/next_action/parked/duplicate/order/audience; fake runner tests |
| PTA-16 | Immutable pins, retention/usage port, archive chỉ ngăn chọn mới; disable/revoke và dependency drift chặn continuation; restart/publish/rollback/pin tests |

Các dòng trên đánh dấu **implementation và tests trong module sở hữu**.
PTA-01–PTA-16 chưa được coi là tích hợp production hoàn tất: không có Alembic
migration/bootstrap/shared UI route và concrete runtime/Registry/Foundation
adapters trong baseline. Không đánh dấu đủ gate tổng thể M1–M5/MA–MD.

## Files, public exports và API

- Backend: `src/agentscope/app/workforce/lifecycle/` và `async_evaluation/`.
  Public exports trong `lifecycle/__init__.py`, optional SQL/FastAPI lazy import.
  `LifecycleService` conform DraftPort/BuildBatchPort/AgentReusePort/
  PublishedCatalogPort có sẵn; không sửa contracts Phase A.
- UI: `examples/web_ui/frontend/src/features/workforce/agents/`; exports trong
  `index.ts`. API dùng injected shared transport, không tạo token store riêng.
- Tests: `tests/workforce/lifecycle/`, `async_evaluation/`, `frontend/`.
  Fake chỉ trong tests. Không có production fake success/TODO service.
- Router factory có toàn bộ endpoint Lifecycle ở mục 6.6, thêm owned
  history/diff/availability/retention. Router chưa include vào app chung.
- Local lifecycle aggregates bổ sung schema chi tiết mà port Phase A hiện trả
  `object`; đề xuất promotion trong bàn giao Phase A, không tạo package contracts thứ hai.
- Type hints Python dùng `typing.Optional/Tuple/List/Dict/Sequence/Protocol/...`,
  không dùng PEP 604 `|`. Không sửa `.env`, không đọc/in secret.

## Tests đã chạy và kết quả

Môi trường thực tế: Python 3.14.4, Pydantic 2.13.5, SQLAlchemy 2.1.4,
PostgreSQL 16 trong container test riêng. Cài pytest/aiosqlite/asyncpg và
black/flake8/mypy vào `.venv` local để kiểm tra; không sửa manifests/lockfiles.

- `PYTHONPATH=src .venv/bin/python -m pytest tests/workforce -q`:
  **51 passed, 7 subtests passed** với SQLite test file riêng từng case.
- Cùng suite với `WORKFORCE_LIFECYCLE_TEST_DSN` trỏ PostgreSQL test riêng:
  **51 passed, 7 subtests passed**. Mỗi case tạo schema UUID riêng, drop đúng
  schema đó sau test. Unique/CAS/UoW/atomicity đã chạy PostgreSQL thật;
  đây không phải Alembic migration hoặc runtime E2E.
- UI DOM tests: **6 passed** — library/settings/error, revision save,
  stale publish/idempotency retry, hard-gate block, selected batch.
- Full frontend TypeScript check và production build pass trong copy tạm.
  `node_modules` hiện hữu có symlink thiếu đích; dependencies được cài bằng
  package.json hiện tại trong `/tmp`, không sửa lockfile/node_modules của repo.
  Build còn warning Vite/chunk size thuộc app hiện hữu.
- ESLint vùng agents, Black 79, Flake8 và Mypy theo flags repo: pass.
- Python compile/type-annotation scan và `git diff --check`: pass.

Container PostgreSQL test đã dừng/xóa; thư mục frontend validation tạm đã dọn.
HEAD giữ nguyên baseline, không có commit mới.

Lệnh backend từ `platform_VP/agentscope`:

```bash
PYTHONPATH=src .venv/bin/python -m pytest tests/workforce -q
# Chỉ dùng PostgreSQL test DB đã được cấp; mỗi case tạo/drop schema riêng.
WORKFORCE_LIFECYCLE_TEST_DSN="$YOUR_TEST_DSN" \
  PYTHONPATH=src .venv/bin/python -m pytest tests/workforce/lifecycle -q
bash tests/workforce/lifecycle/frontend/run_tests.sh
git diff --check
```

Script UI cài dependencies trong thư mục tạm rồi tự dọn; không gọi model,
MCP hay provider thật. Cần mạng/npm cho toolchain tạm.

## V1.4: bằng chứng và phần chưa xác minh

Đã test: policy/protocol freeze, cả ba pattern, `workflow_state`/`next_action`,
no-trigger/duplicate/out-of-order không được chạy LLM/side effect, unknown không
recreate job, cross-audience/two-ticket hard gates, stale eval, immutable pins,
restart partial evaluation và availability trước continuation.

`case_run_id` ổn định từ evaluation ID/case ID; snapshot/candidate version ID,
job ID, release event ID và protocol reference dùng đối soát. Lifecycle không
sinh Provider Event/SSE runtime IDs hay ghi workflow/inbox/public event log.

Chưa test live: inbox/checkpoint/outbox delivery/replay/SSE/close của runtime,
worker lease recovery của Foundation, Provider Event signature/normalization,
mock end-to-end AgentScope, booking/MCP/model sandbox, UI qua app router thật.
Turn evidence trong test đến từ fake runner; không chứng minh runtime thực sự
ngủ/đánh thức hoặc booking thật. Fixture travel chung của Dũng còn chờ.

## Việc tiếp theo

Các phần còn cần owner tương ứng tích hợp gồm DTO/migration dùng chung,
composition/router, Registry protocol/availability, Builder batch flow,
runtime checkpoint/usage và mock E2E trước sandbox.

Không tự sửa folder của owner khác để vượt các điểm chờ trên. Rollout sau
migration/adapters: include router/worker có auth, nối shared transport và
pages, chạy mock E2E/restart/isolation, rồi sandbox được cấp credential.
Rollback deployment chỉ ảnh hưởng lựa chọn mới, vẫn giữ version/protocol/
history/pin cũ; không downgrade schema hoặc hard-delete pending references.
