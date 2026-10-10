# Trạng thái — Phan Hoàng Dũng

Ngày: **10/10/2026**, Asia/Saigon. Nhánh: **feat/wf-execution**.
Baseline code mới: **53a139b** — đã fast-forward origin/develop2, nhận commit
PHH `7a8e356`, giữ các thay đổi handoff đang có. Thay đổi lane Dũng lần này
chưa commit/push.

## Phase A/B đã làm và giới hạn nghiệm thu

- **Phase A của Dũng:** đã có operation/inbox schema + provider-event fixtures;
  bổ sung adapters và consumer tests dùng fake port thật của Đông, schemas/
  claim DTO thật của Huy Hoàng. Chi tiết [PHASE_A.md](PHASE_A.md).
- **Phase B độc lập của Dũng:** đã hoàn thiện provider ingress, correlation,
  reconciliation, fake technician backend và các adapter ranh giới. Chi tiết
  [PHASE_B.md](PHASE_B.md), gồm lệnh chạy và giới hạn kiểm chứng.
- **MA chung chưa xác nhận:** verified inbox context/detailed resolver/promotion
  DTO/hook và shared strict validation còn cần NCH/NPD/PHH duyệt.
- **MB/MC/MD chưa nghiệm thu:** chưa có runtime Workflow/Customer API/worker
  production composition/PostgreSQL/SSE server/sandbox để chạy toàn chuỗi.
  Không đánh dấu toàn bộ PHD-01–17 hoàn thành.

Không còn chờ Huy Hoàng bàn giao schema Phase A: gói này đã nhận và chạy kiểm tra.
PHH chưa triển khai Phase B runtime; không viết thay owner.

## Phạm vi bàn giao Phase A/B

Theo mục 17.9 của kế hoạch; các Task IDs bên dưới chỉ tính phần thuộc A/B,
không đánh dấu hoàn thành toàn task trong kế hoạch tổng.

| Phase | Tasks liên quan | Đầu ra đã có | Điểm còn cần chốt trong A/B |
|---|---|---|---|
| A | PHD-14/15/17 | Operation/inbox schema, provider-event fixtures và pinned protocol/normalized DTO consumer tests | Verified inbox context, exact-detail resolver signature, manager-only audience và shared strict validation |
| B | PHD-14/15 | Provider ingress, correlation, atomic inbox apply và shared Workflow adapter với fake sink | Session/UOW contract và fake, hook/cause DTO review |
| B | PHD-07/16 | Reconciliation/query timer/CAS, job conflict và query version handling | Query-result schema, fact allowlist/version semantics và query hook/fake |
| B | PHD-17 | Fake technician backend assigned/on_the_way/arrived/completed, hai ticket xen kẽ | Không thay fake backend bằng bằng chứng runtime toàn platform |
| A/B, consumer compatibility | PHD-01/02/05/06/13 | Canonical protocol pin, shared operation projection, typed command claim và consent replay/revoke tests | Reviewed tool metadata, authorize/attention/result signatures và fake |

## Code và exports thay đổi trong lượt này

Chỉ sửa owned paths `src/agentscope/app/workforce/execution/**`,
`tests/workforce/{execution,fixtures}/**` và handoff cá nhân.
Code owner khác được nhận nguyên trạng từ merge baseline, không chỉnh lại.

- Mới: `external_operations/_protocol.py` — ExecutionProtocolAdapter,
  exact resolve_snapshot, canonical pin validation và projected create/query mapping.
- Mới: `external_operations/_adapter.py` — ExternalOperationAdapter,
  shared DTO output/Scope filtering/optional UOW.
- Mới: `provider_events/_workflow.py` — WorkflowEventAdapter, provider DTO/
  original binding validation, explicit query/attention/result hook injection.
- Chỉnh gateway/operation service dùng canonical config hash cho pin mới,
  giữ digest cũ khi record legacy không có snapshot_ref.
- Chỉnh ingress giữ ActorContext identity đã xác minh; processor truyền
  persisted inbox ID/time vào normalizer, không sinh mới khi retry.
- Chỉnh reconciliation kiểm tra job namespace/conflict trước update; query
  giữ timer cause/observation/source hash, không tự tạo provider inbox identity.
  Query cùng business facts vẫn persist version/job binding mới, không emit status trùng.
- Chỉnh partner consent nhận typed claim/result, pending result fail closed.
- Mới: `tests/workforce/fixtures/phase_ab_fakes.py`,
  `tests/workforce/execution/provider_events/test_phase_ab.py`.
  Chỉnh consent tests, legacy fixture signature và fake technician progress_events.

Exports cũ giữ nguyên. Exports mới nằm trong subpackages external_operations
và provider_events, không sửa root Workforce barrel/shared ports.
Contract dùng shared DTO Phase A và provider envelope schema_version=1;
protocol config theo schema/hash thật của Đông, PHH proposals `phh-phase-a-1`.

## Đầu vào module khác đã dùng

| Owner | Đã dùng / còn thiếu |
|---|---|
| NCH | Shared DTO/ports; DurableJobService.enqueue_provider thật với SQL enqueue test double; Phase B jobs/worker/signals/SSE transport có code, production persistence/bootstrap/auth chưa có |
| NPD | AsyncToolProtocol/EventMapping, real snapshot hash/samples; FakeAsyncProtocolPort thật cho consumer tests; resolver/normalizer production chưa có |
| PHH | WorkflowRecord sample, WorkflowTrigger/ExternalEventCause/TimerCause/CommandClaimResult proposal thật; Workflow test sink do Dũng sở hữu, không có PHH runtime giả production |
| BHN/PTA | Requirement/policy/validation/eval schema đã merge; production build/reuse/eval/publish chưa có |

## Bằng chứng kiểm tra hiện tại

- Execution/E2E slice + Foundation contracts + Registry Phase A:
  **113 passed, 4 skipped, 62 subtests passed**.
- Foundation Phase B chạy riêng: **10 passed**.
- PHH Phase A runner: **242 passed**, không fail/error/skip.
- Ruff E/F 79 cột: pass; mypy: **26 source files**, pass.
- Không chạy lại frontend/browser trong lượt này vì không đổi frontend.
  Kết quả lint/build cũ chỉ là lịch sử ở VALIDATION.md.

Bốn skip: một PostgreSQL concurrency test cần dedicated DSN, ba full-platform
tests cần WORKFORCE_E2E_FACTORY. Lỗi collection Foundation default import mode
và thiếu RFC3339 checker của lần chạy đầu đã khắc phục; lệnh chuẩn ở PHASE_B.md.
Không sửa test config hoặc dependency manifests của owner khác.

| Invariant | Đã kiểm tra | Chưa chứng minh bằng hệ thống thật |
|---|---|---|
| Inbox + job, apply + sink | SQLite atomic rollback; job service NCH thật với repository double | PostgreSQL commit/race/fencing, durable worker |
| Pins/normalization | Old pin khi current v2 đổi; namespace/hash/identity/time/fact allowlist, early event | Registry persistence/resolver/auth signature thật |
| Order/reconciliation | Duplicate/delta gap/reprocess/terminal/stale-query/job conflict | Worker retry/recovery/timer scheduling production |
| Workflow/binding/close | Shared DTO boundary, wrong sink response rollback, hai workflow xen kẽ và fake closed sink giữ fact | Checkpoint/outbox/trigger runtime, real close race/retention/restart |
| Replay/client/UI | Consent replay/revoke; client SSE parser/dedupe lịch sử | Server SSE replay/live/410/proxy và Chat browser |
| Onboarding | Mock MCP/HTTP provider/customer; A1–A4/B1–B4 đối soát | Endpoint/credential/grant/signing/idempotency/query sandbox |

Schema/metadata/record samples ở PHASE_A.md; lệnh chạy và giới hạn kiểm chứng ở PHASE_B.md.
Không gọi model trả phí, booking thật hoặc backend đối tác ngoài repo.

## Integration requests còn mở

Chỉ giữ [Contract và fake Phase A/B](INTEGRATION_REQUEST_PHD-01_PHASE_A.md):
context/resolver/query-result/manager-only semantics, UOW, hook và strict
validation review với NCH/NPD/PHH. Các yêu cầu triển khai ngoài A/B đã loại bỏ;
không còn backlog production trong integration request của lần bàn giao này.

