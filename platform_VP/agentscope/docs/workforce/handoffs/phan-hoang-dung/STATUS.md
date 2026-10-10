# Trạng thái bàn giao — Phan Hoàng Dũng

Cập nhật: 10/10/2026, timezone Asia/Saigon. Baseline ban đầu: `6bc7d60`. Branch: `feat/wf-execution`. Phần Execution trước đã nằm trong commit `383a387`; code contracts Phase A của Chí Hoàng là `1ff8fb6`, merge `a99d506`. Lần bổ sung dưới đây chưa commit/push/deploy.

Đã đọc lần lượt kế hoạch 1.4.3 rồi README cá nhân, các README vùng sở hữu và code SDK/MCP/SQL/UI. Không có AGENTS.md áp dụng trong checkout. Baseline cũ chỉ có README scaffold; lần này **đã nhận DTO/ports/schema/TypeScript contracts Phase A** của Chí Hoàng. STATUS của Chí Hoàng xác nhận chưa có concrete Foundation persistence/auth/worker/migration/composition; Registry/Builder/Lifecycle/Orchestration vẫn chưa có implementation. Execution đã nối phần DTO dùng được, nhưng chưa phải platform production hoặc tích hợp đối tác hoàn chỉnh.

## Bổ sung sau khi nhận Phase A của Chí Hoàng

- PHD-01/02/05/13: dùng Scope/PartnerAudience/ActorContext/PartnerApprovalDecision chung; canonical customer purpose; Registry/MCP nhận Scope DTO. Audience optional null không làm lệch consent cũ, vẫn kiểm tra chính xác user/ticket/chat/residence.
- PHD-03: export thêm `calculator_catalog_descriptor(scope) -> ToolDescriptor` để Đông import vào Registry.
- PHD-13: command claim nhận ActorContext; record_result nhận RequestResult; replay trả lại decision response. Authorize hook và claim aggregate thật vẫn chờ Huy Hoàng.
- PHD-14/09: creation status mới là prepared theo shared enum; gateway/UI vẫn đọc intent cũ.
- PHD-15: validate ProviderEventEnvelope chung, bỏ envelope schema riêng; response ProviderEventReceipt có received_at, không lộ internal error; canonical hash/replay giữ audit inbox cũ. ErrorResponse/PublicError đã có request_id hợp lệ.
- PHD-16: JobPort enqueue được truyền Scope và datetime có timezone đúng signature.

Chi tiết chữ ký chưa khớp và đề xuất cụ thể: [PHD-01 Phase A](INTEGRATION_REQUEST_PHD-01_PHASE_A.md). **153 passed, 50 skipped, 11 subtests passed** cho suite mở rộng gồm Execution/E2E slice, 9 contracts tests của Chí Hoàng và regression SDK; thêm 16 cases kiểm tra DTO. Chưa gỡ bốn gate PostgreSQL/full-platform. Build frontend, ESLint, Ruff và mypy qua.

## Task và phần còn phụ thuộc

| Task | Phần đã thực hiện trong lane | Chưa thể nghiệm thu / đầu ra cần nhận |
|---|---|---|
| PHD-01 | Guard reload runtime; scope đủ bốn trường; agent/version pin; binding/schema/capability/effect; Toolkit chỉ chứa wrapper được bind; revalidate ngay trước provider send | Runtime/PublishedCatalog/Identity/route ports thật; Chí Hoàng nối core legacy tool assembly để mọi đường production đi qua gateway |
| PHD-02 | MCPClient.get_tool qua ToolBase; client lifetime riêng; resolve credential lúc call với Scope DTO; schema drift/input/output checks; projector bắt buộc; idempotency field server-owned theo cấu hình adapter | Đông cung cấp connection/tool snapshots; Chí Hoàng SecretStore adapter theo environment; projector/credential/query adapter của từng provider. Hiện đã test MCP stdio **giả**, chưa sandbox provider thật |
| PHD-03 | Calculator integer minor units, reserve/fees/budget; thêm canonical ToolDescriptor export | Đông đăng ký `calculator_catalog_descriptor(scope)` vào catalog và nối reviewed-effect metadata; không tự sửa Registry |
| PHD-04 | Policy hiệu ứng read/write/booking/cancel/communicate/ask_user, unknown/unreviewed bị chặn, không suy từ HTTP/provider annotations | Cờ reviewed effect cần được owner Registry/contracts chốt; production không tự cấp cho tool mới |
| PHD-05 | Approval lưu DB, arguments/quote hashes, expiry, decider/audience/run/call/group/workflow, decision history; HITL adapter cùng UOW; đã nhận shared audience/decision DTO | Migration; approval aggregate/quote DTO và verification thật; bridge events/projector HITL hiện có |
| PHD-06 | Unique execution key theo owner+run, intent trước call, approval consume atomic, persist external result, no blind write retry | PostgreSQL concurrency gate; Alembic/UOW integration; worker lease/fence và recovery scanner thật |
| PHD-07 | Unknown/partial trung thực; BookingReconciler query unknown sync; operation query pending/unknown; không tự compensate | Provider query/idempotency semantics thật. Provider không query được phải needs_attention; không cam kết exactly-once ngoài platform |
| PHD-08 | Cancellation recheck trước send; call đã gửi lưu kết quả thật; persisted approval resume qua repository restart; expired consent bị chặn | Worker cancel/resume/HITL bridge và lease-expiry authorization thật của Foundation/Orchestration |
| PHD-09 | ApprovalCard, ExecutionStatus, external progress, loading/error/expiry/decider controls, API transport injection, demo riêng; build và lint qua | Huy Hoàng import vào Chat; Chí Hoàng shared transport/types. Browser tool trả apps/browsers rỗng nên chưa test thao tác giao diện thật |
| PHD-10 | Mock Hotel/Car/Technical MCP stdio, inventory hữu hạn, duplicate, failure-after-write, network, price-change/credential fixtures; integer calculator dataset | **Đã bàn giao bộ mock độc lập.** Không liên hệ provider/model thật |
| PHD-11 | Có runner test Execution + HTTP/SQL/MCP mock và các full-platform acceptance tests có gate | Chưa có toàn chuỗi enable MCP → build/eval/publish → group/@agent → booking → Settings/rollback. Cần các owner bàn giao code và composition test factory |
| PHD-12 | Reuse scenarios JSON; kiểm tra cùng agent definition trong hai group không dùng chung approval/correlation/local idempotency | Builder/Lifecycle canonical identity/concurrent build/batch/reuse/publish và Orchestration dynamic selection chưa có; không dựng bản fake business service thay các owner |
| PHD-13 | Partner approval endpoint riêng, exact ticket/workflow/audience/decider; shared command-port claim/result; replay trước revision check; fake A/B/C/D, revoke/remap/cancel/credential tests | Grant/residence/worker/legacy ticket/memory/download/vector isolation toàn chuỗi cần Chí Hoàng + Huy Hoàng; namespace thật phải dùng wf_inbound_requests qua port |
| PHD-14 | ExternalOperation intent/protocol snapshot/hash/correlation trước call; bind job; early event/unknown; creation prepared theo enum chung, tách progress | Đã có AsyncProtocolSnapshotRef nhưng thiếu detailed protocol/normalizers/terminal policy; Registry snapshot thật; aggregate adapter, migration và composition |
| PHD-15 | Provider raw-body auth trước parse; dùng shared envelope/receipt; inbox+job commit trước 202; receipt filtering; dedupe/conflict; atomic processor gọi WorkflowPort | Auth/signature/replay/rate limit thật; ActorContext chưa có verified provider namespace; JobPort thiếu provider enqueue; normalized-event/Workflow signatures cần owner chốt. Không có auth fake mặc định |
| PHD-16 | Query timer schedule/handler, stale-query CAS, delta gaps quarantine/reprocess, closed/revoked fact persistence via workflow sink, needs_attention escalation và UI | Worker not_before/retry/lease; query adapters; Workflow attention/result hooks; PostgreSQL gate và protocol timeout policy thật |
| PHD-17 | Fake customer/provider clients, SSE/history parser/dedupe/cursor, hai ticket xen kẽ; HTTP/SQL/provider integration slice; full-platform cases 79/80/84–87 sẵn nhưng gated | Các cases 56–88 cần Customer API/Workflow/SSE/checkpoint/retention/auth/worker thật. Không báo MB/MC/MD/full E2E pass từ test slice/fake ports |

Không đánh dấu toàn bộ PHD-01–17 hoàn thành. Các phần độc lập đã có code/test; các dòng cần đầu ra khác tiếp tục chờ theo các integration requests bên dưới.

## File, API và exports

Chỉ thay đổi `src/agentscope/app/workforce/execution/**`, `examples/web_ui/frontend/src/features/workforce/approvals/**`, `tests/workforce/{execution,e2e,fixtures}/**`, và handoff cá nhân này. Không sửa contracts, core, module owner khác, package/lockfile, global UI routes hoặc migration.

- `ExecutionPolicy`, `ExecutionGateway` (`prepare_toolkit`, `execute`, `decide_approval`, `get_call`), `ApprovalService`, `PartnerApprovalService`, `TransactionService`, `ExecutionError`, `calculate`, `calculator_catalog_descriptor`, `calculator_descriptor`, `create_router`, `create_repository`, `get_metadata` từ execution.
- `ExternalOperationService`, `OperationReconciler` từ external_operations; `BookingReconciler`, `summarize` từ `_reconciliation`.
- `ProviderEventIngress.accept/read_receipt` và `ProviderEventProcessor.process` từ provider_events. Composition inject hai service tương ứng vào HTTP và job handler; không để HTTP chạy LLM/process synchronous.
- Router prefix `/workforce/v1`: manager approvals list/decision, execution/booking reads; partner approval decision **202**; provider job-events **202** và receipt **GET**. Không có public endpoint execute arbitrary tool.
- Frontend exports `WorkforceApprovalCard`, `WorkforceExecutionStatus`, `WorkforceExternalOperationStatus`, `createApprovalApi`. Types hiện là view models riêng component, không tạo bộ shared DTO thứ hai.

Đã import các DTO chung dùng được từ contracts Phase A; `value()` vẫn chuyển DTO sang JSON tại ranh giới record nội bộ. Các port-specific extensions/metadata còn **đề xuất**, không tự thêm vào contracts. Không tạo Scope/Actor/Workflow/Agent DTO production thứ hai. `Any` còn tại aggregate/ports chưa chốt; chưa tuyên bố ExternalOperationService/ProviderEventProcessor conformant toàn bộ shared ports. Các khác biệt cụ thể được ghi trong request Phase A.

## Kiểm tra và cách chạy

Môi trường: Python 3.11, virtualenv tạm `%TEMP%\wf-execution-venv`; repo service/storage-sql dependencies + pytest/aiosqlite/asyncpg cài tại đây. Editable install lỗi encoding đường dẫn tiếng Việt; đã dùng wheel và `PYTHONPATH=src` để test source checkout. Frontend dependencies cài bằng frozen lockfile, ignore scripts; không thay manifests/lock.

```powershell
$env:PYTHONPATH = (Join-Path (Get-Location) 'src')
& "$env:TEMP\wf-execution-venv\Scripts\python.exe" -m pytest tests/workforce/execution tests/workforce/e2e -q -p no:cacheprovider
pnpm.cmd --dir examples/web_ui/frontend build
pnpm.cmd --dir examples/web_ui/frontend exec eslint src/features/workforce/approvals
```

Kết quả suite cuối và regression được ghi trong [VALIDATION.md](VALIDATION.md). Bốn skip thuộc lane này: một PostgreSQL concurrency test (chưa có dedicated DSN, Docker daemon không chạy) và ba full-platform acceptance tests (chưa có composition/worker factory). SQLite chỉ kiểm tra persistence/rollback/repository và hành vi service; **không chứng minh PostgreSQL locks/concurrency/commit order**.

Đã kiểm tra SDK ToolBase cả `.call` và `__call__`, assembly không thêm builtin ngầm, mock MCP stdio thật, ASGI error/auth/receipt/consent; không có model trả phí hay booking thật. Các tests dùng fake clock cho quote TTL; test SQL restart dùng file SQLite tạm. Public receipts không lộ scope/raw payload; output/error đi qua projector và sanitized code.

Browser smoke: Vite localhost khởi chạy được rồi đã dừng; browser inventory rỗng nên **chưa chạy thao tác UI**. Demo: `pnpm.cmd --dir examples/web_ui/frontend dev --host 127.0.0.1 --port 5175`, mở `/src/features/workforce/approvals/demo/index.html`. Demo có label GIẢ LẬP, không import vào app router/index, không gọi API/provider. Test loading, lỗi gửi, expiry, double click, đổi ticket khi callback pending và unknown/partial cần thực hiện khi có browser.

## API/event samples và đối soát

Mock event envelope: `event_fixture('A2', job_id='FAKE-job-1', correlation=<operation.correlation_id>, version=2, status='completed')`; schema_version=1, event_type=`FAKE.progress`. Provider identity chỉ lấy từ injected auth; không nhận owner/conversation/agent/callback_url trong payload. ExternalOperation snapshot được pin lúc prepare. Receipt ID do UUID server cấp, external IDs fixture `A1/B1/A2/B2` được giữ nguyên.

Các invariants đã có test: zero provider call trước approval; changed args/quote/expiry/wrong decider bị chặn; intent trước network; timeout-after-write không recreate; early event nối correlation; inbox+job rollback khi job lỗi; apply+workflow rollback cùng UOW; duplicate apply một lần; snapshot out-of-order/terminal không lùi; delta gap quarantine rồi reprocess; provider namespace/receipt isolation; closed/revoked sink chỉ giữ facts; query không overwrite event mới; hai group riêng operation/approval và cùng local key không chia state. Các invariant thuộc Orchestration như SSE replay/live gap, cursor retention, lease fencing, checkpoint-close race vẫn chưa được xác minh bằng code thật.

## Requests còn mở và bước tiếp

1. [PHD-01 — contracts, migration, auth, UOW, jobs và core integration](INTEGRATION_REQUEST_PHD-01.md) — Nguyễn Chí Hoàng.
2. [PHD-02 — Registry/AsyncProtocol, effects, credential/provider adapters](INTEGRATION_REQUEST_PHD-02.md) — Nguyễn Phương Đông, phối hợp Chí Hoàng.
3. [PHD-13 — runtime/binding/HITL/commands/workflow và Chat imports](INTEGRATION_REQUEST_PHD-13.md) — Phan Huy Hoàng, phối hợp Chí Hoàng.
4. [PHD-11 — composition E2E, batch/reuse và acceptance gates](INTEGRATION_REQUEST_PHD-11.md) — Chí Hoàng, Hữu Nghĩa, Tiến Anh, Huy Hoàng.
5. [PHD-01 Phase A — phần DTO đã nối và chữ ký còn thiếu/khác](INTEGRATION_REQUEST_PHD-01_PHASE_A.md) — Chí Hoàng, Đông, Huy Hoàng. Dùng request này cập nhật hiện trạng của các request trước; không còn coi toàn bộ contracts là scaffold.

Sau khi nhận các ports: giữ owner scope và provider namespace, thay fake bằng adapter thật qua composition; merge additive migration; chạy PostgreSQL concurrency/race/recovery; nối full-platform factory và cases 56–88; kiểm tra UI trong Chat; mới đi sandbox được cấp. Rollout/rollback production và live booking chưa thực hiện. Đối tác thật còn thiếu endpoint sandbox/MCP credential, idempotency/query semantics, protocol event schema/version/ordering/transition, signing policy và mapping/grant onboarding.

