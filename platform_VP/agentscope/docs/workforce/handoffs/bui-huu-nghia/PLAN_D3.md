# Kế hoạch D3 — Bùi Hữu Nghĩa

Ngày lập: **2026-10-12**. Owner: **Bùi Hữu Nghĩa**.
Branch triển khai: `feat/wf-builder`. Trạng thái: **đã merge vào `develop2`**.
Baseline đã kiểm tra: `278ea4a3a4a62b79b290d2e9fc6bf24d33ba06a7`
(merge PR #68, chứa commit `bbd6d9a` C7/D0–D2 và `3aabceb` sửa C3 của Nghĩa).
Implementation commit `f1f195f`; PR [#71](https://github.com/nguyennanganhdev/AI-Workforce-Platform/pull/71)
đã merge vào `develop2` tại `58c00f2`. Baseline `278ea4a` phía trên là đầu vào
khi triển khai, không phải HEAD hiện hành.

Kết quả implementation: **34 backend D3 pass**, **8 browser pass**; regression
Builder A/B/C3/D3 + shared contracts **100 pass**, Registry/D1 **32 pass, 1 skip**.
Sửa một lỗi DRAFT thiếu draft_id trong ReuseMatcher. Code/test/tài liệu đã
commit, push và merge. [PHASE_D_D3.md](PHASE_D_D3.md) ghi kết quả hiện hành;
[TEST_MATRIX_D3.md](TEST_MATRIX_D3.md) map mọi ID bên dưới với evidence.

D3.0–D3.6 đã thực hiện trong phạm vi consumer; các phần khảo sát/kế hoạch bên
dưới giữ lại để giải thích quyết định. PostgreSQL canonical-write/CI/production
Builder vẫn chưa xác minh, không mở rộng sang provider/migration/D4.

## 1. Mục tiêu và nguồn quy tắc

**D3 của Nghĩa = missing-capability / reuse / concurrent-build regressions
ở phía Builder, tiêu thụ output D2 của Phương Đông.**

Áp dụng trình tự D0 → D1 → D2 → D3 → D4 do người dùng cung cấp cùng:

- [Kế hoạch chung](../../KE_HOACH_TRIEN_KHAI.md): mục 2.5 (reuse/concurrency),
  5 (ownership), 6 (DTO/ports/persistence), 9 (BHN), 14 (chống conflict),
  15.3 (test/PR), 17.9 (Phase D).
- [Trình tự Phase D](../PHASE_D_SEQUENCE.md),
  [D1 của Chí Hoàng](../nguyen-chi-hoang/PHASE_C_C7_VA_PHASE_D_D1.md),
  [D2 của Đông](../nguyen-phuong-dong/PHASE_D_D2.md).
- [C3 của Nghĩa](PHASE_C_C3.md), [Phase B](PHASE_B.md), README backend,
  frontend và tests Builder.

Task liên quan: BHN-03/07 (selection/validation), BHN-09/10/11 (reuse,
recheck/concurrency), BHN-12/13/14 (async requirement, readiness và hiển thị).
Đây là phần regression của các task, không đánh dấu toàn bộ BHN-01–14 hoàn thành.

Trong checkout không tìm thấy `AGENTS.md`. Nếu baseline tiếp theo bổ sung file
này, phải đọc trước khi triển khai.

## 2. Hiện trạng đã đối chiếu với mã nguồn

Đã đọc mã backend Builder, luồng UI Builder và các test/fixture A/B/C3; đối chiếu
contracts, Registry SQL/service/provider, Lifecycle validator, Foundation UOW,
D1 harness, C7 composition và workflow CI. Đây là khảo sát luồng phục vụ D3;
không phải chứng nhận mọi tính năng của toàn bộ AgentScope đã được kiểm thử.

Các đường dẫn dưới đây tính từ `platform_VP/agentscope/`.

| Thành phần có sẵn | Tận dụng trong D3 / giới hạn hiện tại |
|---|---|
| `builder/_requirements.py`, `async_capabilities/_requirements.py` | Extraction có giới hạn/retry; policy theo schema Tiến Anh; không sinh runtime ID/Scope từ LLM |
| `async_capabilities/_selector.py` | Filter capability/effect/schema, pagination budget, pin, query fallback, dedup theo tool version và recheck cả capability phụ |
| `async_capabilities/_protocol_adapter.py` | Exact resolver, kiểm tra protocol effect/result mode/tool version từ C3; read-only không đòi protocol |
| `builder/_reuse_matcher.py` | Quyết định reuse/resume/revise/create/clarify/repair qua `AgentReusePort`; `business_key()` chỉ là key so profile trong proposal, không thay canonical DB business key |
| `builder/_service.py` | `prepare/confirm/cancel`, scope ownership, revision, idempotency và refresh khi catalog stale; `_entries/_messages/asyncio.Lock` chỉ trong một instance/process |
| `builder/_protocol_validation.py` | So manifest với selection server-held, recheck và gọi `AsyncDraftValidator`; không tạo draft, không giữ reservation, không chứng minh atomic check + write |
| UI `BuilderPanel`, `CapabilityPanel`, `state.ts` | Blocker, action reuse, notice/revision, confirm và cancel đã có; dùng `BuilderClient` inject, demo fake không phải HTTP production |
| `tests/workforce/builder/async_capabilities/` | Samples, model/catalog/reuse doubles, A/B và optional browser tests; tiếp tục tái sử dụng |
| `tests/workforce/builder/phase_c/test_integration.py` | 26 test với C1 UOW + C2 SQL protocol + Lifecycle validator thật; tool catalog/reuse/policy resolver vẫn là test doubles |
| Registry D2 | Test drift/disable giữ exact old pin đã có; service và SQL provider không cần viết lại |
| Foundation D1 | Supervisor restart test, metric convention, environment checker; chưa có harness Builder concurrency chuyên dụng để lấy nguyên dùng |

Những điểm cần phản ánh đúng trong test:

1. `AsyncProtocolService.get_snapshot()` dùng `PermissionError` cho cả wrong Scope
   và disable. Builder hiện chặn bằng exception; **không parse message để đoán lỗi**,
   không biến mọi permission failure thành thiếu capability rồi cho đi tiếp.
2. Ref protocol không mang head revision. Recheck so current pin không phát hiện
   mọi chu kỳ A → B → A hay disable → enable giữa hai lần đọc; không hứa CAS xuyên
   Registry/Lifecycle bằng kiểm tra ở Builder.
3. `confirm()` đã confirmed có đường trả lại idempotent; kiểm tra trước write vẫn
   bắt buộc ở `ProtocolBuildValidator` và canonical writer. Không dùng replay
   confirm như giấy phép bỏ recheck khi tạo draft sau đó.
4. Repo hiện có contract `AgentReusePort`/`DraftPort`, nhưng chưa tìm thấy provider
   production canonical create/reuse identity trong Workforce. C7 runtime graph
   không bổ sung draft writer hay durable Builder session. Test fake xử lý conflict
   không được gọi là bằng chứng chống duplicate identity trên PostgreSQL.
5. Handoff C3/D1/D2 có câu trạng thái cũ “chưa commit/merge”. Git tại baseline trên
   đã chứa các commit đó. Dùng SHA và kết quả kiểm tra làm căn cứ; không sửa tài liệu
   chung hoặc handoff người khác để đồng bộ trạng thái trong PR D3 của Nghĩa.

## 3. Output cần nhận và mức sẵn sàng

| Nguồn | Output cụ thể | Đánh giá ở baseline hiện tại |
|---|---|---|
| D0 | Baseline C đã merge, kết quả E2E C6 và commit dùng chạy | Code có trong `278ea4a`; handoff D0 ghi 11/11 E2E C6 pass. Chưa chạy lại C6 trong lượt lập plan này |
| D1 — Chí Hoàng | Canonical UOW/test environment, migration head, cách chạy PostgreSQL, quy ước fault/metrics | Có script kiểm tra, head `0010_workforce_runtime`, supervisor tests và CI. Local thiếu `aiosqlite`, `pytest`, chưa cấu hình PostgreSQL test DSN |
| D2 — Đông | Current enabled snapshot; exact old-pin resolver; publish/disable; schema hash; lỗi/scope/ordering invariants và regression evidence | Đã có trong baseline merge PR #68; Registry hiện chạy 30 pass, 1 PostgreSQL skip |
| Phase B/C — Tiến Anh | Contracts reuse/draft và validator/policy đã chốt | Dùng lại ngay; provider nào chưa có dùng test double đúng contract, ghi giới hạn |
| D2 — Huy Hoàng / D3 — Dũng | SSE, workflow, provider recovery | Không là dependency trực tiếp của test Builder D3; không nhận triển khai các lane này |
| D4 — Tiến Anh | Publish pin, stale eval, long wait, archive/rollback | Nhận output D3 sau; Nghĩa không chờ Anh làm D4 rồi mới làm D3 |

**Đủ code đầu vào D2 để bắt đầu D3 của Builder.** Trước nghiệm thu phải ghi link/run
CI hoặc bằng chứng PostgreSQL từ owner nếu có yêu cầu DB concurrency; merge không
tự chứng minh CI pass. Các phần consumer/unit/SQL functional có thể làm ngay với
môi trường hiện có. Không tự pull/rebase/merge, cài dependency hoặc sửa cấu hình
chung trong lượt lập plan.

Checklist tiêu thụ D2 khi bắt đầu triển khai:

- [x] Ghi SHA D0/D1/D2 và public exports thực tế sau khi chốt baseline.
- [x] Dùng `SqlAsyncProtocolProvider(uows)`, `bind(scope, loader)` và
  `resolve_detail(scope, ref)`; không đọc/ghi Registry tables từ business code.
- [x] Fixture `loader` của test Builder phải raise nếu được gọi: Builder không
  normalize provider event hay dùng inbox của Dũng.
- [x] Phân biệt current head cho build mới với immutable pin phục vụ operation
  cũ. Old pin đọc được không đồng nghĩa build mới được dùng protocol đã disable.
- [x] Giữ semantics lỗi hiện hành; nếu D2 bổ sung typed error/head revision,
  chỉ dùng sau khi shared contract/public API đã được owner bàn giao.

## 4. Ranh giới chỉnh sửa

Allowlist cho implementation sau này:

```text
src/agentscope/app/workforce/builder/**
tests/workforce/builder/**
docs/workforce/handoffs/bui-huu-nghia/**
examples/web_ui/frontend/src/features/workforce/builder/**
```

Ưu tiên test trước; chỉ sửa production Builder khi test chứng minh lỗi thuộc
consumer. Không refactor đồng loạt hoặc viết lại selector/reuse/service đã có.
Frontend chỉ sửa nếu regression D3 yêu cầu đổi hành vi hiển thị/confirm.

Không sửa Registry/Execution/Lifecycle/Orchestration/Foundation/contracts,
`integrations/`, core app/auth/storage, shared frontend, dependency/lockfile,
migration, CI, `scripts/workforce/`, test fixtures/E2E chung hoặc handoff người khác.
Không xây SQL build session, generator, draft journal, worker hay HTTP production
chỉ để hoàn thành bộ regression này.

Nếu lỗi nằm ở provider/shared contract: giữ reproducer trong tests của Nghĩa,
ghi `INTEGRATION_REQUEST_BHN_D3.md` với owner, trigger, public signature, expected/
actual và test chứng minh; tiếp tục các case độc lập. Không copy provider vào
Builder, không nới assertion hoặc trả fake success trong production.

## 5. Trình tự thực hiện

### D3.0 — Chốt baseline và phân loại coverage

1. Kiểm tra branch/status/merge state; giữ nguyên thay đổi có sẵn của người dùng.
2. Đối chiếu baseline SHA, chạy Builder A/B/C3 và Registry bằng runner đang có.
3. Map test hiện có với bảng ở mục 6; case đã đủ thì tham chiếu kết quả, chỉ thêm
   biến thể còn thiếu. Không copy 26 test C3 sang folder D3.
4. Ghi `TEST_MATRIX_D3.md`: ID case, task BHN, fixture thật/fake, điểm fault,
   expected result, test path, pass/fail/skip/not-run và lý do.

### D3.1 — Fixture điều khiển drift và concurrency trong vùng test Nghĩa

- Thêm package `tests/workforce/builder/phase_d/`; tái dùng samples/fakes A/B và
  seam SQL protocol C3. Helper dùng chung chỉ tách trong test Builder khi thực sự cần.
- Test doubles mới chỉ thêm khả năng đổi catalog/reuse revision, trả một trong
  ba conflict code, đếm lời gọi và điều khiển thứ tự qua `asyncio.Event`/barrier.
- Dùng `asyncio.wait_for` để test lỗi timeout rõ; giải phóng/cancel tasks ở cleanup.
  Không dựa vào sleep ngẫu nhiên để “tạo race”.
- Có hai nhóm: cùng `ProposalService` để kiểm tra local serialization; hai
  instance để kiểm tra xử lý catalog/reuse thay đổi qua port. Không gọi lock
  trong một process là distributed lock.
- Dùng protocol config hợp lệ để tái hiện drift; dữ liệu cố ý hỏng metadata chỉ
  ở test corruption riêng. Không monkeypatch private Registry/Lifecycle để
  giả rằng đã tích hợp provider thật.

### D3.2 — Missing capability và pin drift

Triển khai nhóm M/P của mục 6. Kiểm tra tại prepare, confirm và pre-write tương
ứng. Assert cả blocker/state/revision/pin/coverage, không chỉ “có exception”.
Đối với request bị từ chối, assert không chuyển sang confirmed thành công,
không tự giảm tracking và không tự thay pin trong proposal cũ.

Nếu phát hiện lỗi selector/readiness/prewrite, sửa tối thiểu trong file Builder
tương ứng. Giữ regression effect/mode/tool version và dedup C3 luôn pass.
Disable hiện dùng permission exception vẫn là đường từ chối hợp lệ; thông báo
UI có thể chung, không được diễn giải nhầm wrong Scope thành MCP đã tắt.

### D3.3 — Reuse/revise/resume và batch

Triển khai nhóm R. Reuse phải dùng cùng identity/version tham chiếu; thiếu tracking
thì revise cùng identity hoặc repair khi unavailable, không clone. Bổ sung port
spy để kiểm tra đúng Scope/profile/policy/revision gửi đi.

Phân biệt stale reuse catalog với đổi protocol: reuse decision và capability
selection đều phải được kiểm tra. Chỉ xác nhận proposal mới sau khi user thấy
thay đổi; không tự chọn candidate khác rồi giữ trạng thái confirmed cũ.

### D3.4 — Concurrent build ở ranh giới Builder

Triển khai nhóm C. Lịch chạy phải có barrier và outcome cụ thể:

1. Hai lời gọi cùng message/payload vào một service → cùng proposal, extraction
   một lần; payload khác dùng cùng message ID → `IDEMPOTENCY_CONFLICT`.
2. Hai edit cùng revision → một edit thắng, một `REVISION_CONFLICT`.
3. Edit/confirm/cancel xen kẽ → kết quả theo thao tác được serialize trước;
   thao tác sau không hồi sinh proposal đã hủy hoặc ghi đè revision mới.
4. Hai service đã prepare ở cùng catalog revision. Test double mô phỏng một
   canonical write bên ngoài đã thắng, rồi làm `validate_decisions` bên còn lại
   trả conflict. Builder phải refresh candidates/revision và yêu cầu confirm lại.
   Chạy riêng `AGENT_ALREADY_EXISTS`, `AGENT_BUILD_IN_PROGRESS`, `REUSE_DECISION_STALE`.
5. Drift/disable sau confirm nhưng trước pre-write → hook chặn exception/invalid
   report; caller test spy không gọi `DraftPort` khi gate chưa hợp lệ.

**Hai proposal cùng nghiệp vụ có thể cùng tồn tại.** Hai confirm chỉ xác nhận
đề xuất, không reserve identity. Không viết test yêu cầu chỉ một proposal hoặc
một confirm trên toàn hệ thống khi contract chưa cam kết như vậy.

Test caller/spy chỉ chứng minh cách dùng hook/port, không chứng minh production
draft writer đã được nối. Nếu cần nghiệm thu “hai actual writes → một identity”,
dùng canonical provider và PostgreSQL do Lifecycle/Foundation cung cấp, qua public
port; thiếu thì ghi rõ chưa xác minh và chuyển owner. Không phát sinh dependency
vào D4 mới để hoàn tất phần consumer D3, và không nhận xây writer/DB uniqueness.

### D3.5 — Kiểm tra hiển thị của UI đang có

- Tái dùng demo/client/test UI hiện có cho missing required, optional missing,
  reuse all, revise, catalog refresh và confirm revision cũ.
- Người dùng thấy phần thiếu và notice; không hiển thị “đã tạo agent” chỉ vì confirm.
- Disabled/wrong Scope phải giữ trạng thái lỗi, không biến thành success khi retry;
  cancel không nhận response cũ ghi đè proposal mới.
- Sửa code UI và thêm case chỉ nếu có lỗi thuộc D3; browser test dùng demo phải
  ghi rõ fake. Không thêm root route, API client chung hoặc runner/dependency mới.

### D3.6 — Regression, kiểm tra ownership và bàn giao

Chạy test theo mục 7, rà diff theo allowlist, cập nhật STATUS/README và
`PHASE_D_D3.md`. Bàn giao consumer evidence cho Tiến Anh (D4), fixture/repro cho
Dũng (D3/E2E), commands/CI request cho Chí Hoàng. Đây là tài liệu trong thư mục
Nghĩa; không tự gửi tin nhắn, commit, push hoặc merge.

## 6. Ma trận nghiệm thu dự kiến

Mỗi ID là một hành vi cần evidence; có thể dùng subtests. Số ID không phải số
test đã viết/pass. A/B/C3 đã phủ nhiều case cơ bản, D3 tập trung biến thể drift/race.

| ID | Kịch bản | Kết quả bắt buộc / điểm assert |
|---|---|---|
| M01 | Không có tool bắt buộc / tool unavailable / bị xóa | `MISSING_REQUIRED_CAPABILITY`, needs_input, không confirm |
| M02 | Chỉ thiếu optional | `missing_optional` đúng, không tự thêm optional vào covered, không block nếu các điều kiện khác đủ |
| M03 | Catalog nhiều trang, cursor lặp/quá budget | Tìm đủ các trang trong budget; khi không thể xác minh thì chặn, không loop vô hạn |
| M04 | Sai schema/effect/tool version/protocol effect/mode | Blocker sớm; giữ 10 regression bổ sung sau review C3 |
| M05 | Pending thiếu correlation/timeout/event facts/query tool | Chặn ở schema hoặc readiness đúng tầng; không bịa metadata, không giảm tracking |
| M06 | Query fallback đổi version/mất capability/disable/đổi sang write | Recheck chặn; query binding phải read-only, đúng version và status_query |
| M07 | Read-only / terminal create-only / pending create-only / query-only chưa đủ semantics | Hai ca đầu hợp lệ không bị ép polling; hai ca sau giữ blocker đã chốt với Lifecycle |
| M08 | Một tool phủ nhiều capability, kể cả query fallback | Một binding/version; coverage đầy đủ; capability phụ mất thì confirm/prewrite chặn |
| P01 | v1 ở proposal, publish v2 trước confirm | Refresh revision và notice; old proposal giữ pin v1; muốn dùng v2 phải confirm lại |
| P02 | Drift sau confirm, trước validate manifest | Prewrite chặn pin/hash không khớp; không tự rewrite manifest sang current |
| P03 | Disable trước prepare/confirm/prewrite | Không có kết quả ready/confirmed/write mới thành công qua gate bị disable; permission failure không bị nuốt |
| P04 | Read exact v1 sau v2/disable | Resolver giữ nguyên ref/hash/metadata v1; không dùng khả năng đọc old pin để vượt new-build availability check |
| P05 | Wrong Scope theo từng tenant/domain/area/manager; forged ref | Từ chối, không rò candidate/proposal/policy của scope khác |
| P06 | Đổi mapping/ordering làm hash thay đổi | Consumer thấy pin drift theo D2, không tự normalize hoặc thử xử lý out-of-order event |
| R01 | Same business, published đủ coverage và policy | Reuse identity/version cũ; all-reused → `completed_reused`, không generate thêm |
| R02 | Same business, draft/eval đang có | Resume draft hợp lệ; không clone, không coi draft là published/runtime-ready |
| R03 | Same business thiếu tracking/capability/policy compatibility | Revise cùng agent_id, nêu phần thiếu; không reuse quyền rộng hơn yêu cầu |
| R04 | Inactive/blocked/credential/tool unavailable | Repair/block theo port, giữ identity; không chuyển create để né lỗi |
| R05 | Nhiều candidate same-business hoặc uncertain/partial overlap | Clarify, không tự gộp theo tên/similarity; metadata thiếu không là success |
| R06 | Different business dù trùng tên / cùng nghiệp vụ khác Scope | Create được khi độc lập hợp lệ; không reuse chéo tài khoản cùng area |
| R07 | Batch có duplicate item/khác policy/câu hỏi | Gộp chỉ khi tương đương; conflict/câu hỏi không bị mất; mixed reuse/create giữ đúng từng item |
| R08 | Catalog/candidate đổi sau proposal | Refresh candidates/decision/revision; user xác nhận lại, không đổi tên/ID để retry mù |
| C01 | Same message, same/different payload đồng thời | Idempotent cùng proposal / `IDEMPOTENCY_CONFLICT` đúng phạm vi instance |
| C02 | Hai edit cùng expected_revision | Một cập nhật; bên thua `REVISION_CONFLICT`, không lost update |
| C03 | Hai confirm cùng revision | Kết quả idempotent; không coi hai lần confirm là hai lần tạo agent |
| C04 | Edit ↔ confirm; cancel ↔ prepare/confirm | Outcome theo thứ tự lock; stale request không làm sống lại/chỉnh proposal đã kết thúc |
| C05 | Hai instance, reuse port báo một writer ngoài đã thắng | Refresh đúng từng conflict code; giữ reference owner cung cấp, không retry create mù |
| C06 | Protocol/query drift đúng giữa các bước đọc | Gate từ chối khi quan sát mismatch; ghi rõ khoảng check → write chưa atomic |
| C07 | Timeout/exception/cancel trong extraction hoặc port | Không lưu proposal thành công dở dang; retry hợp lệ, lock/tasks được giải phóng |
| C08 | Cùng IDs/nghiệp vụ ở hai Scope, cùng service | Idempotency/state cô lập; thao tác scope A không sửa/hủy/xác nhận proposal B |
| U01 | Missing/reuse/revise/refresh/error/cancel qua UI | Label, blocker, button và revision đúng; evidence browser nếu chạy, không suy ra từ TypeScript build |

Kiểm tra no-side-effect theo seam thực tế: `ProposalService` không gọi provider
event/runtime; hook không persist. Spy tại caller test ghi số call draft chỉ khi
đang kiểm thử flow gọi draft. Không gắn spy không được inject rồi coi “0 calls”
là bằng chứng production không sinh agent/group/job.

## 7. Chiến lược chạy kiểm tra

### Bằng chứng đã chạy khi lập plan (2026-10-12, baseline 278ea4a)

| Kiểm tra | Kết quả thực tế |
|---|---|
| Builder A/B/C3 qua unittest | **57 pass** (31 A/B + 26 C3) |
| Registry A/B/C2/D2 qua tên module đầy đủ | **30 pass, 1 skip** PostgreSQL do thiếu DSN |
| D1 `test_runtime_resilience` | **2 pass** |
| `check_phase_d_environment.py` | **Failed**: thiếu `aiosqlite`, `pytest`; Python 3.12.10, head đúng `0010_workforce_runtime`; PostgreSQL not_configured |
| C6 E2E / CI PostgreSQL / browser / D3 mới | Chưa chạy trong lượt lập plan; D3 chưa viết |

Lệnh Registry discovery không có package context đã gặp lỗi relative import;
đã chạy lại thành công bằng tên module đầy đủ bên dưới. Không sửa test Registry.
Kết quả 11/11 C6 trong handoff D0 là bằng chứng owner bàn giao, không phải lần
chạy mới của Nghĩa. Lỗi Lifecycle legacy từng ghi ở C3 phải kiểm tra lại nếu chạy
suite đó trên baseline mới, không tự mang kết luận cũ sang D3.

### Lệnh dùng được ở môi trường hiện tại

Chạy từ `platform_VP/agentscope`:

```powershell
.\.venv\Scripts\python.exe -m unittest tests.workforce.builder.async_capabilities.test_phase_a tests.workforce.builder.async_capabilities.test_phase_b tests.workforce.builder.phase_c.test_integration -q
.\.venv\Scripts\python.exe -m unittest tests.workforce.registry.event_protocols.test_protocols tests.workforce.registry.event_protocols.test_phase_b tests.workforce.registry.event_protocols.test_phase_c tests.workforce.registry.event_protocols.test_phase_c_postgres -q
.\.venv\Scripts\python.exe -m unittest tests.workforce.foundation.phase_d.test_runtime_resilience -q
.\.venv\Scripts\python.exe scripts/workforce/check_phase_d_environment.py
```

### Lệnh dự kiến sau khi đã viết test D3

```powershell
.\.venv\Scripts\python.exe -m unittest tests.workforce.builder.phase_d.test_missing_capability tests.workforce.builder.phase_d.test_reuse tests.workforce.builder.phase_d.test_concurrent_build -v
.\.venv\Scripts\python.exe -m compileall -q src/agentscope/app/workforce/builder tests/workforce/builder
git diff --check
git diff --name-only
git ls-files --others --exclude-standard
```

Tên file ở lệnh D3 là dự kiến; không chạy trước khi file tồn tại. Nếu dùng pytest
trong môi trường D1 đã đủ dependencies, chạy từng owner suite riêng để tránh
trùng tên module test. Sau khi PR #71 merge, owner Chí Hoàng đã thêm lệnh chạy
Builder D3 vào `.github/workflows/workforce-phase-d.yml` ở repo root. D3 test
mặc định không gọi model/MCP trả phí hoặc booking thật.

PostgreSQL test chỉ dùng `WORKFORCE_TEST_POSTGRES_URL` trỏ DB test riêng theo D1,
không đọc/in DSN/secret từ `.env`, không reset DB. Database concurrency phải có
bằng chứng PostgreSQL; SQLite SQL functional và test doubles được ghi đúng loại.
Nghĩa không cần viết lại Registry CAS test của Đông.

Nếu thay UI, dùng `BUILDER_UI_TEST_URL` và browser suite hiện có; build/lint chỉ
phạm vi Builder với toolchain sẵn có. Thiếu runner/dependency thì ghi rõ hoặc
chuyển yêu cầu môi trường cho Chí Hoàng, không sửa package/lockfile của team.

## 8. File dự kiến và lý do sửa

| File | Mục đích / điều kiện |
|---|---|
| `tests/workforce/builder/phase_d/__init__.py`, `_fixtures.py` | Package và doubles/barriers D3, chỉ thêm helper thật sự cần |
| `phase_d/test_missing_capability.py` | Nhóm M/P, tái dùng SQL provider thật và samples |
| `phase_d/test_reuse.py` | Nhóm R; full Scope/profile/policy/candidate assertions |
| `phase_d/test_concurrent_build.py` | Nhóm C; local race + inter-instance consumer conflict |
| Builder `_service.py`, `_reuse_matcher.py`, `_protocol_validation.py`, selector/adapter/models | Chỉ file chứa lỗi D3 được tái hiện; giữ public exports/contracts cũ nếu không cần đổi |
| UI Builder và test/demo của Builder | Chỉ nếu U01 phát hiện lỗi/thiếu evidence cần bổ sung |
| Handoff `TEST_MATRIX_D3.md`, `PHASE_D_D3.md`, `STATUS.md`, `README.md` | Evidence, limits, reproduction và output cho người tiếp theo |
| Handoff `INTEGRATION_REQUEST_BHN_D3.md` | Chỉ tạo khi có request thật cho provider/CI/shared boundary |

## 9. Điều kiện bàn giao và điểm dừng đúng scope

- [x] Nhóm M/P/R/C có mapping đến test cũ/mới; mọi case chưa xác minh có lý do.
- [x] Builder tiêu thụ output D2 thật cho drift/disable/exact pin; no normalization.
- [x] Thiếu bắt buộc hoặc stale dependency không đi tiếp bằng success; không mất
  coverage sau dedup, không tự giảm phạm vi hoặc clone identity để né reuse.
- [x] Các conflict reuse/catalog được refresh và yêu cầu user confirm lại; race
  test có thứ tự kiểm soát, timeout, cleanup và assertion theo public behavior.
- [x] A/B/C3 không regression; format file sửa, compile và diff ownership pass.
- [x] Evidence phân biệt test double / SQLite / PostgreSQL / browser / CI;
  không gọi consumer tests là full concurrent-build DB hay runtime E2E pass.
- [x] Nếu cần sửa owner khác, request có reproducer và owner rõ; không ghi
  “D3 đầy đủ không giới hạn” khi còn case bắt buộc của consumer bị fail.
- [x] Handoff ghi baseline/fix SHA khi đã có commit, file sửa, exports, commands,
  kết quả và trạng thái commit/push/PR đúng thực tế; không ghi số pass dự kiến.

Output cho **Tiến Anh/D4**: ma trận missing/reuse/race, quy tắc pin trước write,
case `AGENT_ALREADY_EXISTS`/`AGENT_BUILD_IN_PROGRESS`/`REUSE_DECISION_STALE`,
policy coverage và giới hạn canonical-write atomicity. Không yêu cầu Anh làm D4
trước để mở D3.

Output cho **Dũng**: fixtures/repro consumer có thể gọi lại trong E2E; Dũng sở hữu
assertion actual concurrent writes, provider recovery và toàn lát cắt. Output cho
**Chí Hoàng**: lệnh Builder D3 đã được thêm vào CI; điều kiện test
PostgreSQL/canonical-write vẫn là giới hạn môi trường riêng chưa được chứng minh.

Kết thúc ở **D3 của Bùi Hữu Nghĩa**. Publish/rollback/evaluation pin thuộc D4 của
Anh; SSE/workflow/replay thuộc Huy Hoàng; provider recovery/order thuộc Dũng/Đông;
worker/proxy/migration/CI/composition thuộc Chí Hoàng.
