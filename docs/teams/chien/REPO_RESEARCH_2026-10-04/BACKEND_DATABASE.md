# Nghiên cứu backend, database, RAG và runtime agent — 04/10/2026

## Kết luận

Checkout hiện tại đã có backend nghiệp vụ V3 thực chất, PostgreSQL chạy local, đăng nhập mật khẩu, Reception có service Python và tích hợp RAG. Nhận định cũ “chỉ có schema / API rỗng / tất cả UI mock” không còn mô tả đúng nhánh này. Tuy nhiên, runtime Supervisor nối Vinhomes vẫn cố ý dùng `NoSpecialists` và các port chưa bind; chuỗi agent chuyên môn tự lập kế hoạch → phê duyệt → dispatch → hoàn thành chưa được chứng minh chạy xuyên suốt. Production chưa được nghiệm thu bằng những kiểm tra trong báo cáo này.

Mốc code chính khi bắt đầu audit: `dev_teamChien_HuyDo`, HEAD `a231575537759845e73b8f4c4124e5ef168b6aff`. Trong lúc audit tác nhân khác sửa rồi commit Coordination producer thành `b2d3f3725ec8e37e5986b13742c9d6211059ba72`, đồng thời tiếp tục sửa WIP `agent-coordination/src/vinhomes/{backend,ports,runtime}.py` và test runtime. Không sửa, không reset các thay đổi đó. Kết luận NoSpecialists/Unbound trong báo cáo là **source committed ở a231575**, không phải khẳng định WIP mới nhất còn nguyên. Các kết luận về catalog specialist và room API được đối chiếu thêm bằng `git show a231575:<path>`; không tính WIP là commit đã giao. Các bảng số liệu local dưới đây được kiểm tra lại read-only trong phiên 04/10, không chỉ sao chép database map đầu ngày.

## 1. Hai backend đang cùng tồn tại

| Thành phần | Trách nhiệm đã có trong code | Nguồn |
|---|---|---|
| Bun/Hono `server/` | Nền tảng OpenBot: identity, agent/runtime, tools/plugins/MCP, chat, work queue; Vinhomes read API, technical A2 và RAG có mount riêng | `server/src/app.ts:336`, `:486`; `server/src/index.ts:1242` |
| Python/FastAPI `services/vinhomes-api/` | Nghiệp vụ Vinhomes V3: ticket/work/approval/QC, resident, Reception delegation, Coordination producer, room, billing, security, reports, learning | `services/vinhomes-api/src/vinhomes_api/main.py:60`, `:150` |
| Vite gateway | Cả Operations và Resident proxy `/api/business` tới FastAPI, mặc định `127.0.0.1:8000` | `app/vite.config.ts:92`; `resident-app/vite.config.ts:4` |

FastAPI đang mount 36 router calls, không phải legacy `vh_incident` router. Tạo OpenAPI không mở DB cho **206 paths, 232 operations** ở thời điểm kiểm tra; có warning route trùng được nêu ở phần phát hiện. Đây là độ rộng contract, không phải 232 flow đã nghiệm thu.

Legacy SQLAlchemy model và Alembic vẫn có trong `services/vinhomes-api/src/vinhomes_api/{db,incidents,work_orders}` và `services/vinhomes-api/migrations`; entrypoint hiện hành dùng các module `v3_*`. Không chạy Alembic legacy vào V3 để cộng thêm bảng. Một số bảng mở rộng V3 cũng mang prefix `vh_*`, nên prefix này không đủ để kết luận là legacy. Nguồn: `services/vinhomes-api/README.md:7`, `main.py:150`; `server/drizzle/README.md:24`.

## 2. Database: kiểm tra live hiện tại

Truy vấn qua `asyncpg`, mỗi lượt trong transaction `readonly=True`, chỉ catalog/aggregate. URL và credential được đọc nội bộ từ config ignored, không xuất trong báo cáo. Không apply migration, seed, tạo/drop database hoặc ghi dữ liệu nghiệp vụ.

| Chỉ số | `vinhomes_v3` | `vinhomes_connected` |
|---|---:|---:|
| Bảng ứng dụng `public` | 193 | 193 |
| FK constraint trong `public` | 682 | 682 |
| Bảng bật RLS | 175 | 175 |
| Bảng FORCE RLS | 175 | 175 |
| Dòng journal `drizzle.__drizzle_migrations` | 13 | 14 |
| Knowledge documents published | 115 | 115 |
| Knowledge chunks | 279 | 279 |
| Knowledge embeddings | 279 | 279 |
| Retrieval runs | 0 | 0 |
| Memory publications | 0 | 0 |

Nguồn kiểm tra hiện tại: `services/vinhomes-api/.local-v3-faker/migration.env`, `.local-connected/migration.env` chỉ để chọn connection; SQL trên `pg_tables`, `pg_constraint`, `pg_class`, `pg_namespace`, journal và aggregate RAG. Không dump bản ghi của cư dân. Catalog artifact trước đó: [schema-live.json](../DATABASE_MAP_2026-10-04/schema-live.json), commit artifact `d463f1a9db4a313422eb984a7d23357a5be617f1`.

Các tầng schema không cùng số bảng:

| Nguồn | Số bảng | Ý nghĩa |
|---|---:|---|
| `server/src/db/design/merged.json` | 148 | Baseline design, đếm lại số top-level table definitions |
| Registry Drizzle export | 154 | `tables.ts` + `security.ts`; kiểm tra lại bằng schema generation |
| Migration SQL / live catalog | 193 | Bao gồm SQL extensions truy vấn trực tiếp từ FastAPI |
| Runtime SQLite | 9 | 2 checkpoint + 1 adapter Reception; 6 Coordination |

**39 bảng live ngoài registry ORM không tự động là bảng thừa**: SQL extension có tài liệu riêng và được FastAPI truy vấn. Các file `schema/core.ts`, `work.ts`... còn tồn tại nhưng registry canonical `schema/index.ts` chỉ export `tables` và `security`. Nguồn: `server/src/db/schema/index.ts:1`, `server/drizzle/README.md:24`; danh sách 39 bảng trong [database map](../DATABASE_MAP_2026-10-04/README.md).

Đọc lại SQLite bằng URI `mode=ro` xác nhận:

- `agent-reception/.reception-state/reception.sqlite3`: `checkpoints`, `writes`.
- `agent-reception/.reception-state/reception.sqlite3.records`: `reception_records`.
- `agent-coordination/.coordination-state/connected.sqlite3`: `acknowledgements`, `checkpoints`, `cursors`, `inbox`, `ledger`, `records`.

Không cộng hai PostgreSQL deployment giống nhau thành 386 bảng thiết kế. Một deployment + các runtime đã kiểm tra = **193 + 9 = 202 bảng ứng dụng/runtime**; journal tính riêng. SQLite không cung cấp FK xuyên sang PostgreSQL; IDs, scope proofs và backend re-verification giữ ranh giới đó.

### Journal có một lệch cần giải trình

Repo có 13 migration entries `0000`–`0012`. Hash tất cả 13 SQL hiện tại khớp journal `vinhomes_v3`; cả CRLF/LF được xét để tránh nhầm do checkout Windows.

`vinhomes_connected` có thêm một row journal `id=4`, timestamp `1790750000002`, hash prefix `336f2e48ffe2`, không khớp SQL hiện tại; 13 row còn lại khớp repo. Đây là dấu hiệu lịch sử migration local khác nhau, **không đủ kết luận schema bị hỏng**: hai DB vẫn cùng số bảng/FK. Cần truy nguyên migration đã áp dụng thêm trước khi chuẩn hóa deployment/upgrade; audit không sửa journal.

### ORM generation và constraints

`bun run --cwd server db:check`: PASS, **154 tables / 1089 statements**. Lệnh chỉ sinh `.codex-artifacts/schema-check/`, không sinh migration dự án.

`node server/scripts/verify-baseline.mjs`: PASS, **18 isolated PostgreSQL/WASM checks**: cross-tenant FK, published policy immutable, excluded overlapping policy, thread owner, memory owner, applied/stale triage projection, submitted assessment immutable, object key tenant prefix, evidence hash immutable, audit truncate forbidden. Đây là PGlite + generated schema/invariants; **không phải nghiệm thu live toàn bộ 193-table migration chain**. Nguồn: `server/scripts/check-schema-generation.ts:1`, `server/scripts/verify-baseline.mjs:1`.

## 3. Quyền và authentication

FastAPI có ba đường identity được tách rõ trong code:

1. Password login PostgreSQL của Vinhomes (`password_auth.py`). Password dùng scrypt; opaque session token chỉ lưu SHA256-prefixed hash; cookie HttpOnly/SameSite Lax, Secure khi request HTTPS; session TTL 8 giờ. Đăng ký tự tạo membership pending, thay quyền thu hồi session. Nguồn: `password_auth.py:27`, `:44`, `:115`, `:237`, `:247`.
2. Platform session qua `VINHOMES_API_AUTH_URL`; forward cookie, lấy `user.id` từ server auth, không tin `X-Demo-Actor` trong mode này. Nguồn: `v3_auth.py:14`.
3. Demo/fixed dev actor chỉ trên loopback; grants vẫn lấy từ DB. Nguồn: `v3_auth.py:18`, `v3_config.py:57`.

Business query đặt transaction-local `app.tenant_id`, `app.user_id`, đòi user active + tenant membership/scoped role hợp lệ; ticket visibility thêm scope và quan hệ assignment/delivery của staff. Resident kiểm ownership riêng. Nguồn: `v3_auth.py:58`, `:103`, `:138`.

RLS không thay operation authorization; 175/193 bảng bật RLS không có nghĩa 18 bảng còn lại là public. Runtime role từ `.local-v3-faker/api.env` được query live: **`rolsuper=false`, `rolbypassrls=false`**. Không có `api.env` cùng tên trong `.local-connected`, nên audit này không gán kết quả role faker cho password deployment.

Origin guard từ chối cross-site mutation; ResidentBoundary có policy riêng. Liveness `/health` chỉ báo process, `/ready` của FastAPI kiểm tra DB/tables. Không dùng hai endpoint đó để khẳng định auth/model/storage đầy đủ. Nguồn: `main.py:97`, `:111`, `:117`.

Password limiter `_attempts` và hash semaphore là in-process; code tự ghi cần shared limiter trước khi scale workers (`password_auth.py:56`). Đây là giới hạn triển khai hiện tại, không phủ nhận auth đã có thật.

## 4. Nghiệp vụ ticket → xử lý → QC → cư dân

| Luồng | Đã có trong implementation | Nguồn |
|---|---|---|
| Intake | Verified residence, chat/messages, file links, draft khác ticket, handoff resolve coverage và notify | `v3_resident.py`; `v3_reception_operations.py`; `reception_runtime_api.py:15` |
| Triage | Assessment, authoritative decisions, review; version/scope checks | `v3_triage.py:51`, `:173`; `v3_mutations.py:275` |
| Dispatch | Work orders, approve plan, choose staff, offer/accept; version check và capacity constraints | `v3_mutations.py:316`, `:546`, `:642` |
| Nhân viên | Accepted assignment mới chuyển status; repair consent; before/after evidence; water/permission completion gates | `v3_mutations.py:445` |
| QC/redo | Management scope, independent reviewer, completed work; redo liên kết failed QC | `v3_specialized.py:86`, `:137` |
| Kết quả | Direct flow chỉ publish khi work completed + QC pass; resident completion approval riêng | `v3_completion.py:7`; `v3_operations.py:294` |
| BQL session | Ticket conversation, closure approval, inquiry unanswered → management answer | `v3_session.py:100`, `:139`, `:183`, `:268` |

Có hai đường xử lý: ticket có plan và ticket direct. Code completion của planned flow khác direct flow; không mô tả tất cả work_order completed là ticket closed. Ví dụ direct completion nằm ở `v3_completion.py`; planned completion tạo customer approval ở `v3_mutations.py:526`.

Backend còn có cleaning/contractor/budget, security emergency/checkpoint/handover/cameras/contact, water interruptions, accountant invoice/payment, technical asset/measurement/permissions, task board/mailbox, reports JSON/DOCX, account management. Các module mount thực sự tại `main.py:150`–`:186`; route contract lớn không thay thế dữ liệu vận hành và nghiệm thu integration.

Test DB integration đã được viết: `tests/test_resident_contract.py` tạo PostgreSQL disposable từ 13 migration + seed, dùng NOSUPERUSER/NOBYPASSRLS role, test concurrent/ownership/idempotency/public-resolution paths; `test_v3_agent_database.py` và `test_v3_coordination.py` mở rộng producer/delegation/room/billing/security. **Không chạy các write integration này trong audit read-only**. `test_resident_integration.py` yêu cầu local demo URL; `test_password_database.py` opt-in local password deployment. Không tính test bị opt-in/skipped thành nghiệm thu.

## 5. Reception: bootstrap TypeScript và service Python khác nhau

`agent-reception/src/index.ts` là bootstrap PH01 TypeScript: tạo SDK model và phục vụ health. Chạy `bun start` riêng ở package không tự chạy workflow Python. Nguồn: `index.ts:11`, `:22`; `README.md:63`.

Workflow chạy được là `agent-reception/src/runtime/service.py`: `/v1/turns` nhận message đã commit, service token kiểm caller, delegation ngắn hạn kiểm quyền từng run; ghi reply về backend để resident UI đọc DB. Có hai chế độ `graph` (LangGraph workflow) và `loop` (bounded tool-calling agent). Nguồn: `service.py:185`, `:218`, `:233`; `agent/loop.py`; `README.md:114`.

Backend mint delegation gắn principal/binding/run/channel; runtime token chỉ trong memory, bỏ sau turn; authority được đối chiếu lại tại FastAPI. Nguồn: `reception_delegation.py:38`, `:62`, `:103`, `:183`; `reception_runtime_api.py:15`; `service.py:251`, `:265`, `:296`.

Khẩn cấp do policy backend và/hoặc proposal nâng mức, model không được hạ trường hợp keyword phát hiện. Safety guidance phải là câu BQL đã approve đúng địa bàn. Nguồn: `v3_reception_runtime.py:64`; `tests/runtime/test_emergency_guidance.py`.

**Self-help chưa mở**: policy trả `self_help_allowed=False` (`v3_reception_runtime.py:85`); operation `process_self_help` vẫn HTTP **501** (`v3_reception_operations.py:1193`). RAG hỏi đáp đã có không đồng nghĩa self-help workflow đã được cho phép.

Checkpoint SQLite là triển khai local, không phải proof multi-replica production. `agent-reception/README.md:59` ghi production cần checkpointer PostgreSQL phù hợp.

## 6. Supervisor/Coordination: producer backend đi trước runtime consumer

Backend API ở commit HEAD đã có bearer coordination service, canonical team/run/member/binding authority, Reception inbox verify/send/reconcile/status, catalog specialist theo ticket category, admit/run/release/mirror room. Nguồn committed: `git show a231575:services/vinhomes-api/src/vinhomes_api/v3_coordination.py`, `:57`, `:167`, `:192`, `:345`, `:369`, `:406`, `:430`, `:491`.

Agent admin approval ở **local-only `a231575`** tạo immutable `agent_versions` và published `agent_releases`; specialist catalog chỉ lấy agent active, purpose specialist, release published và category phù hợp. Đây là tiến độ backend publication/catalog. Module tự ghi “Accept evaluation records and admin decisions; no evaluator or model runtime”: submission nhận evaluation cases, không tự chạy model/evaluation thật. Nguồn: `v3_agent_reviews.py:1`, `:124`, `:200`, `:250`; HEAD `v3_coordination.py:167`.

Runtime `agent-coordination/src/vinhomes/runtime.py` đã poll backend → durable SQLite inbox/cursor → verify → checkpoint → Supervisor state → báo trạng thái; có lease heartbeat, retry/reconcile unknown outcome, park definite failure. Nguồn: `runtime.py:121`, `:137`, `:163`, `:205`.

Nhưng concrete composition hiện tại là:

```text
Planner(NoSpecialists())
UnboundEvents("backend_events")
UnboundResolver("participants")
UnboundInvocation("agent_invocation")
UnboundBackendActions("backend_actions")
```

Nguồn: `agent-coordination/src/vinhomes/runtime.py:114`–`:119`; `ports.py:88`–`:144`. `NoSpecialists.generate()` trả pause `no_specialist_available`, không gọi provider. Backend specialist catalog mới được xuất bản không tự bind các port consumer này. **Không kết luận Supervisor đã gọi specialist thực tế**, dù API room/records và tests producer đã có.

`/ready` của Vinhomes poller chỉ thử đọc backend inbox (`runtime.py:240`), do đó có thể ready trong khi specialist/action ports vẫn unbound. Generic `agent-coordination/src/runtime/service.py` nghiêm hơn: yêu cầu storage/authority/event_verifier/releases/openbot/model/delegation/schemas, không có production bindings thì 503 (`:17`, `:99`, `:124`). Hai service entrypoints cần được phân biệt.

Generic runtime/team Đông đã triển khai RoomService, Supervisor state machine/action journal, durable ingress/worker, publication/release consumer, tool boundary, budget/ledger, evaluation và report/contribution consumer ports. Production cần factory cấp external canonical producer bindings; test fixtures không thay thế deployment. Nguồn: `agent-coordination/src/runtime/composition.py:30`, `:59`; `README.md:19`.

## 7. Technical A2: không còn chỉ là PoC adapters

Catalog có **14 tools**: outage/schedule/SOP/asset/sensor/history, measurement/result/verify, append maintenance, utility isolation/area restriction/apartment entry/vendor dispatch. Nguồn: `server/src/technical-tools/catalog.ts:19`.

Hono `/api/technical/v1` có HTTP endpoints, strict envelopes/body/path/idempotency checks; runtime dùng per-agent token + signed run assertion, actor grants/scope, restricted DB role, audit và replay receipts trong transaction. Nguồn: `server/src/technical-api/routes.ts:64`, `:129`; `runtime.ts:28`, `:36`, `:131`, `:147`.

`databasePorts()` thực sự đọc/ghi `vh_assets`, sensor/measurement/executor-result/maintenance/approval tables; không bind các `adapters/poc` mặc định. Nguồn: `server/src/technical-api/database.ts:70`, `:190`, `:321`; migration `0009_technical_agent_api.sql`. Enable qua `TECHNICAL_API_DATABASE_URL` + `TECHNICAL_API_TENANT_ID`; không cấu hình thì không mount runtime (`server/src/index.ts:1242`, `:1333`).

Đối chiếu `git show a231575:server/src/index.ts` xác nhận production entrypoint đã inject conditional object vào `createApp` ở `:1333`–`:1341`; không chỉ có optional constructor dùng trong tests. Vì đây là positional object, tìm riêng identifier lowercase `technicalApi` trong `index.ts` sẽ bỏ sót wiring. Audit chưa xác minh biến enable đã được bật trong process local hoặc deployment remote.

Có code và selected contract/rule tests pass, nhưng audit này chưa gọi technical tool end-to-end với signed released agent trong deployment thật.

## 8. RAG và learned knowledge

RAG triển khai gồm parse Markdown/frontmatter, chunk theo headings, dedup source/scope, idempotent ingest/version/job, embeddings, publication, ACL-first hybrid keyword/vector retrieval, rank adjustments, citations và audit. Nguồn: `server/src/knowledge/markdown.ts`, `source-directory.ts`, `ingest.ts`, `pg-store.ts`, `retrieve.ts`, `contract.ts`.

Runtime bật opt-in `KNOWLEDGE_ENABLED=1`, validate required tenant/base/DB/key/model, kiểm DB role NOSUPERUSER/NOBYPASSRLS, gọi backend delegation authority trước retrieval. Nguồn: `runtime.ts:50`; `routes.ts:81`; `reception_runtime_api.py:62`.

Authorization xác minh agent knowledge grant + verified current residence; nhiều nơi ở chưa chọn scope trả 409 choices. SQL lọc tenant/base/document published/active version effective window/target scope hoặc ancestor/deny ACL/allow ACL trước vector và keyword search. Nguồn: `reception_runtime_api.py:63`; `pg-store.ts:278`–`:330`.

Ngữ nghĩa ACL giữa hai API đang khác:

- Internal RAG: không có allow ACL thì người đã qua scope rule được đọc; deny thắng (`pg-store.ts:281`, `:323`).
- Operations keyword `/knowledge/search`: yêu cầu exists allow ACL (`v3_knowledge.py:41`).

Vì vậy 0 document ACL không được suy ra “public” hoặc hai endpoint trả giống nhau. Đây là contract cần thống nhất theo đối tượng sử dụng.

Embedder yêu cầu **1536 dimensions**, default `text-embedding-3-large`, có lựa chọn `-small`, kiểm response dimension; retrieval chỉ chọn embedding model active đã tồn tại. Default similarity threshold **0.35**. Nguồn: `types.ts:18`; `embedder.ts:63`; `pg-store.ts:332`; `retrieve.ts:26`.

Code/doc ghi evaluation `ocean-park-v1` 93 câu ngày 01/10, recall@1 82.4% large vs 73.5% small. Đây là kết quả được ghi ở commit, **không được đo lại với provider thật trong audit**; corpus/model thay đổi cần đánh giá lại. Nguồn: `server/src/knowledge/types.ts:15`; `docs/teams/quang/requests/2026-10-01-rag-ingestion-retrieval.md:48`.

Live cả hai DB có 115 published docs / 279 chunks / 279 vectors, nhưng **0 retrieval_runs** tại lúc audit. Chứng minh nạp dữ liệu, chưa chứng minh traffic retrieval audited tại hai DB này; không suy ra hệ thống chưa từng query ở DB/environment khác.

Learning lấy câu BQL trả lời thành memory candidate, curator phân loại general/PII/high-risk, approval, export Markdown rồi `publish.ts` nạp lại. Live `memory_publications=0` không chứng minh canonical publication lineage đã đầy đủ. Nguồn: `v3_learning.py:1`; `scripts/export_learned_knowledge.py:38`; `server/src/knowledge/publish.ts:1`.

Publisher đăng ký **một staged source file đại diện folder**, originals vẫn ở data repo, chưa đưa từng file vào object store (`publish.ts:68`). Retrieval field tên `queryRedacted` hiện lưu nguyên query normalized, redaction được giao caller (`retrieve.ts:133`). Đây là giới hạn storage/provenance và PII policy cần được phản ánh trong production contract.

## 9. Storage và các giới hạn triển khai

Upload evidence/resident ảnh hiện local filesystem, loopback-only và explicit opt-in; validate JPEG/PNG/WebP decode, giới hạn 10 MB, chống path escape, kiểm ticket/unit ownership. Nguồn: `v3_files.py:29`, `:35`, `:60`; `resident_photos.py:103`.

Metadata local upload gán `scan_status='clean'` sau image validation, không chứng minh có malware scanner. README yêu cầu verified object store/scanning trước production uploads (`services/vinhomes-api/README.md:34`). File API local sẽ từ chối trên host non-loopback, vì vậy triển khai remote upload cần storage adapter/acceptance riêng.

## 10. Kiểm tra đã chạy trong audit

| Lệnh/phạm vi | Kết quả | Bằng chứng và giới hạn |
|---|---|---|
| `bun run --cwd server db:check` | PASS: 154 tables / 1089 statements | Schema generation, không live migration |
| `node server/scripts/verify-baseline.mjs` | PASS: 18 checks | Isolated PGlite baseline/invariants |
| FastAPI `test_real_session`, `test_browser_origin`, `test_local_storage` | **8 PASS** | No-DB tests; 1 Starlette/httpx deprecation warning |
| 7 RAG test files + Vinhomes ticket routes/scope + migration journal | **66 PASS / 1 FAIL** | `migration-journal.test.ts:30` yêu cầu snapshot cho mọi entry |
| Reception `tools/test_contracts`, `graph/test_factory`, `runtime/test_emergency_guidance` | **154 PASS** | Fixtures/mocked dependencies, không live provider |
| Coordination hardening/tool_boundary/ingress_worker/Vinhomes runtime, Windows default encoding | **45 PASS / 3 FAIL** | `UnicodeDecodeError` cp1252 tại `runtime/reporting.py:23` |
| Cùng Coordination selection với `python -X utf8` | **48 PASS** | Xác nhận nguyên nhân UTF8/default encoding; không sửa nguồn |
| Technical API transport + host/catalog/idempotency/verification rules | **104 PASS**, 5 files | Contract/rules, không live released-agent E2E |

Không chạy full suite, không lập tỷ lệ completion từ số test, không tính rerun 45+48 thành 93 distinct tests. Không dùng unit tests thay staging/production/real-provider acceptance. Commands dùng `.venv` riêng từng Python package, `-p no:cacheprovider`, không chạm business DB.

Lệnh tái lập selected checks (chạy root trừ package Python ghi chú):

```powershell
bun run --cwd server db:check
node server/scripts/verify-baseline.mjs
.\services\vinhomes-api\.venv\Scripts\python.exe -m pytest services/vinhomes-api/tests/test_real_session.py services/vinhomes-api/tests/test_browser_origin.py services/vinhomes-api/tests/test_local_storage.py -q -p no:cacheprovider
bun --no-env-file test server/tests/knowledge/embedder.test.ts server/tests/knowledge/source-directory.test.ts server/tests/knowledge/source-metadata.test.ts server/tests/knowledge/routes.test.ts server/tests/knowledge/pipeline.test.ts server/tests/knowledge/eval-metrics.test.ts server/tests/knowledge/markdown.test.ts server/tests/vinhomes-ticket-scope.test.ts server/tests/vinhomes-ticket-routes.test.ts server/tests/migration-journal.test.ts
bun --no-env-file test server/tests/technical-api.routes.test.ts server/tests/technical-tools/host.test.ts server/tests/technical-tools/catalog.test.ts server/tests/technical-tools/idempotency.test.ts server/tests/technical-tools/verification.rules.test.ts
# CWD agent-reception:
.\.venv\Scripts\python.exe -B -m pytest -q -p no:cacheprovider tests/tools/test_contracts.py tests/graph/test_factory.py tests/runtime/test_emergency_guidance.py
# CWD agent-coordination; lần đầu bỏ -X utf8 để tái hiện encoding failure:
.\.venv\Scripts\python.exe -X utf8 -B -m pytest -q -p no:cacheprovider tests/runtime/test_hardening.py tests/runtime/test_tool_boundary.py tests/runtime/test_ingress_worker.py tests/vinhomes/test_runtime.py
```

## 11. Phát hiện cần xử lý trước nghiệm thu

| Mức ưu tiên | Phát hiện | Hành động cần / nguồn |
|---|---|---|
| P0 cho autonomous-agent acceptance | Supervisor Vinhomes vẫn NoSpecialists/Unbound ports | Bind published specialist resolver, invocation, backend action/event ports rồi E2E qua approvals; `agent-coordination/src/vinhomes/runtime.py:114` |
| P0 cho CI acceptance | `.github/workflows/ci.yml` toàn bộ nội dung comment | Không có active `on/jobs` ở file này; kiểm remote Actions riêng. Workflow release/security khác vẫn active; không coi workflow đã chạy và pass chỉ vì file tồn tại |
| P1 | Migration consistency test đỏ | Snapshot thiếu cho `0001`, `0002`, `0007`–`0012`; cần reconcile policy custom SQL/snapshots và test. Không tạo snapshot giả chỉ để xanh; `server/tests/migration-journal.test.ts:30` |
| P1 | Connected journal có một hash không có SQL hiện tại | Truy lịch sử migration/baseline deployment; không sửa applied journal tùy tiện |
| P1 | Upload production chỉ có local adapter/image validation | Object store, scanner, access expiry và lifecycle acceptance |
| P1 | RAG live audit 0 + memory publications 0 | Chạy authenticated retrieval, kiểm audit/ACL/scopes; kiểm lineage học → review → publication theo contract |
| P1 | Self-help 501 | Giữ disabled cho đến khi published reviewed procedure + runtime path được nghiệm thu |
| P2 | Windows ReportArtifacts đọc UTF8 bằng default encoding | `runtime/reporting.py:23` cần explicit encoding hoặc quy chuẩn process UTF8; audit chứng minh -X utf8 hết 3 failures |
| P2 | Route GET room agents được khai báo hai lần | `v3_rooms.py:77` và `v3_room_agents.py:40`; `main.py:159`, `:166` cùng mount. OpenAPI duplicate Operation ID; runtime registration và schema có thể không đại diện cùng handler. Cần consolidate contract |
| P2 | README API có đoạn agent protected port “cannot yet call” đã cũ | Delegation/runtime API đã có thật; cập nhật `services/vinhomes-api/README.md:46` theo code |

P0/P1 ở đây là thứ tự nghiên cứu/nghiệm thu đề xuất, không phải xác nhận bug bảo mật khai thác được hay ticket priority trong DB.

## 12. Tiến độ nên báo cho quản lý dự án

| Hạng mục | Đánh giá có bằng chứng |
|---|---|
| Database/schema | Đã triển khai local 193 bảng, 682 FK, RLS175; design/ORM/migration intentionally khác tầng; còn journal history và test consistency |
| Backend nghiệp vụ | Rộng và có code thực; identity/grants/version/evidence/QC/approval gates; chưa rerun write integrations hay staging acceptance trong audit |
| Reception | Có workflow/runtime/durable local state/delegation/knowledge adapter; self-help chưa mở; chưa xác minh real-provider E2E hiện tại |
| RAG | Pipeline/query/auth/citations/audit implemented, 115 docs/279 vectors live; no current retrieval audit on hai DB đã kiểm |
| Technical tools | 14 tools + real DB API/auth/audit/idempotency; deployment enable/agent invocation chưa nghiệm thu trong audit |
| Agent Factory/admin publish | HEAD a231575 có publish release + category catalog, evaluation records; chưa tự evaluator/invocation proof; commit local-only theo git audit parent |
| Coordination/Supervisor | Core Team Đông substantial; Vinhomes poller durable connected but specialist/action/event bindings incomplete |
| Production | Chưa đủ bằng chứng: full automatic CI, migrations reconciled, multi-replica storage/limiter, production uploads, live provider and cross-service business acceptance |

Mốc commit giúp truy trách nhiệm, không gán toàn module cho một người: `9d65f9f`, `d68b9c7` (Phuc Nguyen, RAG); `2324e74`, `8f4c55a`, `67bae8f`, `725bb3e` (ChienhocIT, integration/learning/publication); `89cbcc0`, `034e41b` (ChienhocIT, producer + Supervisor intake); `a231575` (ChienhocIT, specialist approval/catalog). Team Hoàng có graph/contract, Team Đông có coordination core và Team Quang có technical/RAG; mapping chi tiết team/branch phải dựa kế hoạch, commit và remote refs trong báo cáo tổng hợp, không chỉ tên author gần nhất.
