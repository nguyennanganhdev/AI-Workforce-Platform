# Phase B — Phó Tiến Anh

Ngày: 10/10/2026. Phạm vi mục 17.9: **Async validation/suites với fake runner**.

## Phần đã triển khai

- PTA-14: đối soát binding/tool version/schema/availability/capability;
  protocol chi tiết dùng public `Registry.AsyncToolProtocol`, hash dùng
  `snapshot_ref` của owner Đông. Thiếu protocol, drift hoặc thiếu coverage
  chặn evaluation. Policy reference phải resolve đúng Scope bốn trường.
- `AsyncDraftValidator` inject `RegistryPort` và `AsyncProtocolPort` dùng chung.
  Callable resolve detail/policy là đề xuất integration rõ ràng, không port
  shared thứ hai, không đọc bảng module khác. Resolver lỗi được giữ là lỗi.
- Snapshot được serialize thành JSON kèm content hash: thay đổi dict lồng nhau
  trên manifest/tool/policy/test context không đổi đầu vào đã đóng băng.
  Đối soát manifest/source/tool/test-context/dependency hash trước khi chạy.
- PTA-03/05/06/15 phần Phase B: suite `pta-lifecycle-1` và gate `pta-gate-1`.
  Completion ≥90%, argument checks ≥95%, không vi phạm hard gates. Không có
  LLM judge giả. Grader không tin điểm chất lượng hoặc trạng thái passed do
  runner tự báo nếu evidence thiếu/sai.
- `AsyncEvaluationService` gọi shared `EvaluationRunnerPort` trong mode `mock`;
  production code không có fake runner. Fake clock/runner chỉ trong tests.
  Runner nhận stimuli, không nhận đáp án ExpectedTurn. Report dùng shared DTO;
  mỗi lượt có workflow_state/next_action/counts/cost/latency và blocker.
- Guard `check_release_evidence` đối soát report/snapshot/suite/runtime/policy/
  dependency và chấm lại cases; không tự publish hay ghi deployment.
- Component `EvaluationReport` trong lane frontend của PTA hiển thị case,
  pattern, từng lượt, chi phí, latency, hard gates, loading/error/empty state.
  Chưa gắn route/API shell; không có nút báo publish thành công giả.

## Các suite

| Case | Trigger và điều kiện |
|---|---|
| response-only | request → closed/none; zero tracking |
| interactive-booking | plan → selection → approval → booking confirmed → close; zero tracking |
| external-events | create pending → idle → assigned → on_the_way → duplicate → arrived → completed → late event → close |
| unknown-reconciliation | timeout unknown → idle → timer query → completed → close; không create lại |
| audience-isolation | ticket B event/approval không resume ticket A, không gửi notification sang B |

Đây là hợp đồng kiểm tra nhiều lượt; fake chứng minh grader bắt vi phạm,
không chứng minh runtime thật đã dedupe/order/reconcile đúng. Không viết runtime
thứ hai trong Lifecycle. Mỗi runtime runner Phase C phải thực hiện stimuli bằng
runtime thật và execution mock, tự thu evidence; không copy đáp án suite.

## Policy compatibility

Không sửa artifact Phase A. Hai dialect được chọn **tường minh**:

- `pta-phase-a-1`: schema proposal Phase A của PTA, `status_query` /
  `needs_attention`, event_types/required_facts không rỗng.
- `bhn-phase-a-1`: public schema `HandlingPolicyProposal` của BHN,
  `query_status` / `request_attention`, timeout_seconds >0, hỗ trợ query-only
  không có event_types. Chỉ chấp nhận sau JSON Schema và model validation.

Không tự dịch tên field/value, không coi proposal là canonical production DTO.
Completion condition là dữ liệu đóng băng, không chạy chuỗi như code. Query
fallback yêu cầu protocol có query reference; availability/auth của query tool
thực tế cần resolver/Execution guard được nối ở Phase C.

## Kiểm chứng

Từ `platform_VP/agentscope`:

```bash
PYTHONPATH=src:tests/workforce/registry/event_protocols .venv/bin/python -m pytest tests/workforce/lifecycle tests/workforce/foundation tests/workforce/builder tests/workforce/registry --import-mode=importlib -q
.venv/bin/python -m flake8 --jobs=1 --max-line-length=88 src/agentscope/app/workforce/lifecycle/async_evaluation tests/workforce/lifecycle/async_evaluation/test_phase_b.py
.venv/bin/python -m black --check src/agentscope/app/workforce/lifecycle/async_evaluation tests/workforce/lifecycle/async_evaluation/test_phase_b.py
```

Kết quả: **66 passed, 153 subtests passed**; Flake8 pass; Black formatted.
Frontend: `node_modules/.bin/tsc -b` và ESLint component/export pass.
Pytest cần importlib do file test_phase_a/test_phase_b trùng basename giữa lanes;
Registry fixture hiện import `fakes` top-level nên thêm đúng fixture path.
Không sửa test của owner khác để giải quyết collection.

## Các phần chưa thuộc bằng chứng Phase B

PTA-01/04/07–13 persistence/jobs/API/publish/Settings/catalog/reuse/batch chưa
triển khai. PTA-16 runtime usage/checkpoint/pin/archive/disable/revoke/purge
thuộc C/D; hiện chỉ có input pin và guard stale eval, không có retention service.
Không ghi `wf_workflows`, không tạo migration/core/shared contract. Chưa test
PostgreSQL/Redis/HTTP/SSE/provider/model thật hoặc workflow restart thật;
reload frozen evaluation chỉ là kiểm tra serialization. Frontend compile/lint
không thay thế kiểm thử trình duyệt; component chưa được visual/browser QA.

Bàn giao tích hợp: [INTEGRATION_REQUEST_PTA_PHASE_B.md](INTEGRATION_REQUEST_PTA_PHASE_B.md).

UI SSR smoke pass: loading/error/empty, failed case, từng lượt và escaping HTML.
`git diff --check` phần PTA sửa pass; full-tree check báo blank line EOF trong
README bàn giao đã có sẵn, giữ nguyên theo yêu cầu user.

## Rà soát lần hai — 10/10/2026

Đã tái hiện ba lỗi bằng test trước khi sửa:

1. Manifest đổi binding/schema sau validation nhưng được hash lại có thể
   freeze bằng validation report cũ. Freeze hiện parse dependency bằng model
   owner và chạy lại validation trên chính manifest; report/evidence phải khớp.
2. Runner trả status passed kèm error_code vẫn pass grader. Hiện có error_code
   hoặc status error tạo RUNNER_ERROR; queued/running/cancelled tạo
   RUNNER_NOT_COMPLETED, không được dùng như kết quả đánh giá hoàn tất.
3. Release guard trước đó đòi mọi case passed, khác gate ≥90%. Hiện chấm lại
   từng case, yêu cầu zero hard-gate failures và completion đạt ngưỡng đã pin;
   đối soát completion/cost/latency tổng với evidence, không tin metrics tự sửa.

Regression có suite 10 case: 9 pass, 1 quality fail không vi phạm hard gates
được gate chấp nhận; sửa completion_rate thành 1.0 bị từ chối. Suite mặc định
5 case vẫn cần cả 5 pass để đạt ≥90%. Đây là kiểm tra guard, không atomic publish.
Backend liên module: 66 tests, 153 subtests pass. Black --check, Flake8,
TypeScript build, scoped ESLint và diff check phần đã sửa pass.
