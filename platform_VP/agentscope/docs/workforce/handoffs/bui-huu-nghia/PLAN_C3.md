# Kế hoạch C3 — Bùi Hữu Nghĩa

Cập nhật **2026-10-11** theo yêu cầu chỉ thực hiện C3 trong trình tự chung.
Owner: **Bùi Hữu Nghĩa**. Branch: `feat/wf-builder`.
Baseline: `67ff8715e4a40a37538b727442b3b66f2c9223e1`, chứa C1 `a4c2fdd` và C2
`b9feee2` (merge PR #60). Code C3 ban đầu đã commit/push tại `304c39a`, mở
[PR #62](https://github.com/nguyennanganhdev/AI-Workforce-Platform/pull/62).
Bản sửa review chưa commit/push; chỉ sửa trong vùng Nghĩa, chờ review lại.

## 1. Phạm vi đã chốt

Nguồn: [trình tự Phase C](../PHASE_C_SEQUENCE.md) và mục 17.9 của
[kế hoạch chung](../../KE_HOACH_TRIEN_KHAI.md):

**C3 của Nghĩa = Protocol validation ↔ Builder.** Dùng protocol thật của C2
trên UOW/database C1, nối vào selector/proposal Phase B và cung cấp hook kiểm
tra protocol trước thao tác tạo/sửa draft qua Lifecycle port.

Đầu vào bắt buộc đã có:

| Nguồn | Output sử dụng |
|---|---|
| C1 — Chí Hoàng | Canonical UOW/database; Scope được xác minh ở composition boundary |
| C2 — Phương Đông | `SqlAsyncProtocolProvider`, `AsyncProtocolPort`, exact `resolve_detail(scope, ref)` |
| Baseline Phase B | Requirements/policy, selector, proposal/reuse và `AsyncDraftValidator` |

Không cần chờ C3 Execution của Dũng, C4, C5 của Anh hoặc C7 để hoàn thiện và
bàn giao consumer C3 này. Các port khác chưa có provider được dùng fake trong
test theo hợp đồng; phải ghi rõ phần thật/fake, không tuyên bố full production.

## 2. Ownership và phần không làm trong lượt C3

Chỉ sửa trong các vùng Nghĩa được giao, tính từ `platform_VP/agentscope/`:

- `src/agentscope/app/workforce/builder/`
- `tests/workforce/builder/`
- `docs/workforce/handoffs/bui-huu-nghia/`
- Frontend `examples/web_ui/frontend/src/features/workforce/builder/` chỉ khi
  protocol view cần đổi; C3 hiện không cần thay UI Phase B.

Không sửa contracts, Foundation, Registry, Lifecycle, Execution, root router,
migration, CI, dependency/lockfile hoặc tài liệu của owner khác. Chỉ đọc/gọi
public exports và viết test fixtures trong vùng test của Nghĩa.

Không triển khai SQL build session, manifest generation, policy storage,
Draft/Reuse/Batch provider, draft journal/recovery, API/auth/UI composition hoặc
runtime/E2E. Không nhận task Phase D; kiểm tra pin/disable phục vụ validation
C3 không đồng nghĩa triển khai toàn bộ bộ chịu lỗi Phase D.

Plan trước đã gộp các hạng mục Builder rộng hơn vào gate C3. Bản này thay thế
plan đó. Code session/generator/journal và DDL mới thêm đã được gỡ; logic
service/reuse Phase B được giữ nguyên.

## 3. Các bước thực hiện

### C3.0 — Đọc hợp đồng và xác nhận đầu vào

- [x] Đối chiếu mục 2.5–2.7, 5, 6, 14, 17.9 và trình tự chung.
- [x] Xác nhận baseline có C1/C2, branch và phạm vi diff thuộc Nghĩa.
- [x] Kiểm tra public exports C1/C2 và validator đã có từ Phase B.

### C3.1 — Protocol thật vào readiness/selector

- [x] `RegistryProtocolReadiness` dùng public exact resolver, đối chiếu toàn bộ
  ref/hash, chuyển correlation, event/fact metadata, completion, timeout/query.
- [x] `RegistryCapabilitySelector` tận dụng selector Phase B, đọc current enabled
  protocol qua `get_snapshot` và `validate_capability_coverage`.
- [x] Giữ pin/version/hash, không đổi old pin thành current pointer.
- [x] Theo review PR #62: giữ effect/result_mode trong readiness, so với tool và
  tracking intent; mismatch có blocker trước confirm. Dedup binding theo tool
  version, lưu coverage từng tool và recheck capability phụ.
- [x] Read-only không đòi protocol; terminal create-only pin protocol để validator
  chấp nhận, không thêm polling. Pending/query-only thiếu semantics bị chặn rõ.

### C3.2 — Validation trong luồng build và trước draft write

- [x] Inject selector thật vào `ProposalService` Phase B. Confirm recheck pin;
  drift tạo revision mới và yêu cầu xem/xác nhận lại bằng logic hiện có.
- [x] Export `ProtocolBuildValidator.validate(scope, item, manifest)` để caller
  gọi trước `DraftPort.create_draft` hoặc `update_draft`.
- [x] Hook so capability/binding/protocol hashes với proposal server-held,
  recheck current protocol và gọi `AsyncDraftValidator.validate` được inject.
- [x] Policy được resolve phải khớp proposal; report không hợp lệ/lỗi phải chặn
  draft write. Hook không tự generate, persist hay dispatch draft.
- [x] Scope lấy từ principal/membership C1 ở composition, không nhận Scope hoặc
  selection do UI/LLM tự khai làm bằng chứng authorization/confirmation.

### C3.3 — Test tích hợp đúng lát cắt

- [x] C1 UOW + C2 SQL protocol thật qua SQLite; loader normalization raise nếu
  bị gọi để chứng minh Builder không đi vào ingress.
- [x] Exact old pin/current pin, disable, wrong Scope và resolver lệch hash.
- [x] Protocol metadata/facts/query binding, read-only/terminal/pending/query-only.
- [x] Proposal Phase B confirm refresh khi protocol đổi; pre-write hook với
  validator Lifecycle thật, manifest/policy mismatch và invalid report.
- [x] Chạy regression Builder A/B, related suites, compile/format/import/ownership.
  PostgreSQL chưa có dedicated DSN được ghi unverified như baseline C2.

### C3.4 — Bàn giao

- [x] Ghi output, signatures/wiring, commands/results và giới hạn thật/fake tại
  [PHASE_C_C3.md](PHASE_C_C3.md); cập nhật STATUS/README của Nghĩa.
- [x] Bỏ các request provider/production composition khỏi blocker C3; ghi các
  lưu ý hiện hữu tại [INTEGRATION_REQUEST_BHN_C3.md](INTEGRATION_REQUEST_BHN_C3.md).
- [x] Commit/push C3 ban đầu và mở PR #62 (`304c39a`).
- [x] Sửa 3 vấn đề review: validation sớm, dedup/coverage và trạng thái handoff;
  10 regression tests bổ sung (26 test C3 tổng cộng).
- [ ] Commit/push bản sửa, review lại và merge theo quy trình team. Phiên sửa
  hiện tại chưa được yêu cầu commit/push/merge.

## 4. Tiêu chí bàn giao C3

C3 code/test sẵn sàng review khi Builder tiêu thụ protocol SQL C2 đúng Scope,
exact pin được giữ, recheck/validation chặn dependency không phù hợp trước write,
regression liên quan được kiểm tra và diff thuộc Nghĩa. Test doubles được khai
báo rõ; không yêu cầu full Builder production, migration/root C7 hay C5 runtime.

Lệnh từ `platform_VP/agentscope`:

```powershell
.\.venv\Scripts\python.exe -m unittest tests.workforce.builder.phase_c.test_integration -v
.\.venv\Scripts\python.exe -m unittest tests.workforce.builder.async_capabilities.test_phase_a tests.workforce.builder.async_capabilities.test_phase_b -q
.\.venv\Scripts\python.exe -m compileall -q src/agentscope/app/workforce/builder tests/workforce/builder
git diff --check
```

Trạng thái hiện tại: implementation/test đúng C3 đã có; xem bằng chứng và giới
hạn trong handoff. Không đánh dấu full BHN-01–14 hoặc Phase D hoàn thành.
