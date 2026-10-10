# Phase B — Phan Huy Hoàng

Baseline: `develop2@848740498c92894c074cf264f6ce6307a2dfb9cc`. Local branch: `dev2PHH-B`. Phạm vi lấy từ kế hoạch 17.9 và ownership 5.3; giới hạn ở nhịp B.

Đã đối chiếu lại source Phase B trước với clone mới, giữ phần phù hợp, sửa lỗi bằng test tái hiện và chuẩn hóa bàn giao. Không merge/cherry-pick lịch sử nhánh cũ vào develop2. Code của Đông và các owner khác trên baseline được giữ nguyên.

## Hành vi và ranh giới

| Task | Phần đã có ở B | Phần còn nối ở C |
|---|---|---|
| PHH-13 request/result | Authenticate context, route/grant recheck, shared command namespace, accept atomic, bounded wait/reload, HTTP status mapper | HTTP router và concrete request/command repositories |
| PHH-14 workflow | Ba pattern; binding/group/session/pin; reply/close/CAS; applied event và trigger | DB constraints, bootstrap từ catalog thật, timer/recovery adapters |
| PHH-15 continuation | Reload pinned context; lease/fence/guard; HITL cause; budget; commit checkpoint/message/result/event cùng UOW | AgentScope concrete adapter và Execution side-effect guard |
| PHH-16 event projection | Payload allowlist, scope/audience, sequence/history/snapshot validation, replay/SSE, signal sau commit | PostgreSQL event repository, retention watermark, HTTP/proxy headers và bridge |
| PHH-17 UI/test | Timeline/status/close callback; approval card hiện có; reconnect/410; event/message dedupe; 246 scenarios, có DOM interaction | Global mounting, manager JWT/BFF, approval feed và browser integration |

Các seam chưa có concrete adapter được inject; production không tạo fake service trả thành công. Không tạo schema dùng chung thứ hai hay tự viết migration. `workflows/phase_a.py` vẫn là aggregate proposal PHH, chờ canonical promotion; B không biến proposal thành contracts được owner duyệt.

## Các chốt đã sửa và kiểm chứng

- Reply tải **binding của request gốc** bằng actor/client/user/workflow đã xác thực; không resolve mapping hiện tại để đổi manager/group. Ref hoặc tuple audience khác bị từ chối trước claim.
- Request/reply/close dùng ledger chung; retry đúng ID/body đọc kết quả đã lưu. Close giữ strict integer revision và boolean stop-tracking; chưa coi operation bên ngoài đã hủy.
- RequestView giữ PublicError đã persist; failed/blocked phải có error đúng request, completed/pending không được có terminal error. Projection request còn pending khi workflow đã đóng trả blocked/none với error WORKFLOW_CLOSED. Repository phải đọc status/result/error nhất quán và chỉ trả chi tiết đã lọc.
- Authorized stop_tracking_only cho phép đóng mọi open state, kể cả pending approval; giữ consent refs làm evidence, không approve/consume/cancel. Completion close vẫn yêu cầu giải quyết approval. Late approval trigger không resume workflow đã đóng.
- Checkpoint giữ operation refs lịch sử; pending_waits chỉ gồm operation đang pending đã create thành công và có receive_status/status_query. Mixed terminal/pending được tiếp tục; all-terminal không được chọn external wait. Terminal refs vẫn phải khớp ID/binding/pin; không bỏ history để né validation.
- Bounded result wait tự giới hạn advisory signal bằng thời gian còn lại sau DB reads; re-read durable result và quyền khi hết slice/deadline. Hủy waiter khi deadline/disconnect; slow cancellation cleanup không kéo dài lượt chờ, late exception được observe. Concrete adapter phải giải phóng subscription khi cancellation; DB/auth/HTTP timeout được nối ở C.
- Close mới kiểm tra revision cả khi workflow đã closed; exact same-ID/body retry qua ledger trả kết quả cũ mà không đụng CAS/emit lại. Direct no-op close cần current revision.
- Snapshot recovery gặp revision cũ do concurrent POST sẽ giữ current state, refetch với backoff 50ms tăng tối đa 1s và cho phép abort. Chỉ stale revision được retry; foreign snapshot, cùng revision khác state hoặc thiếu quyền vẫn fail closed. Cursor chỉ đổi sau snapshot mới hợp lệ.
- Operation còn pending không được chọn `awaiting_confirmation/confirm_close`. Side effect, lease/revision stale, approval cause sai và foreign refs bị chặn.
- Lỗi/hung notification không làm mất durable event: bounded wait, heartbeat và re-read; cancellation vẫn propagate. Heartbeat hữu hạn tối đa 60 giây; public stream/subscription revalidate quyền và binding ngay trước từng event/heartbeat, kể cả trang replay đang bị backpressure. Đóng stream giải phóng iterator bên trong. Auth/DB errors ngoài signal vẫn fail closed.
- History/snapshot revalidate cả object tạo bằng model_copy. Pending approval projection dùng allowlist; không serialize credential/private trace từ copied envelope.
- UI giữ `next_action` của receipt, kiểm tra state/action của snapshot và event payload allowlist. Cùng event ID nhưng khác nội dung là conflict; object key ordering không tạo conflict giả.
- Receipt closed đến trước replay vẫn cho hiển thị event lịch sử. Sau close event đã xử lý, message mới có sequence cao hơn bị chặn. Workflow không reopen.
- REST refresh tối đa một lần trên 401, giữ nguyên serialized command và request ID; abort trong token loading không gửi request của hộp chat đã đóng.
- Follower nhận optional `readCurrentState` để không ghi đè kết quả POST tới xen kẽ SSE. Identity/binding khác bị chặn.

`OperationLookup.accept_event` là seam của Execution: adapter thật phải dedupe/normalize/order/update fact trong cùng UOW; PHH không sở hữu provider inbox, correlation resolver hoặc provider status machine.

## Public exports

| Module | Export chính |
|---|---|
| `orchestration` | PartnerIngressService, RequestRepository, RequestView, receipt_http_status |
| `orchestration.workflows` | WorkflowService, WorkflowContinuation, WorkflowBundle, WorkflowRepository, WorkflowBootstrap, WorkflowAuthorization, OperationLookup, TurnPlan, TurnLease, WorkflowConflict, WorkflowClosed |
| `orchestration.partner_events` | ConversationEventService, EventRepository, ConversationAccess, PublicEventWriter, EventCursorExpired |
| `chat/ticket_timeline` | TicketTimeline, WorkflowStatus, createTimeline, applyReceipt, applyEvent, applySnapshot, createTimelineApi, followTimeline |

Model/provider calls nằm ngoài UOW. Side effect phải gọi ExecutionGuard trước mỗi call; checkpoint/event/request completion chỉ commit khi revision/fence còn hợp lệ. Repository/UOW adapters phải thực hiện atomic guarantees mô tả trong Protocol; fake tests không chứng minh DB guarantees đó.

## Chạy lại

Từ `platform_VP/agentscope`, dùng Python đã có Pydantic, jsonschema, rfc3339-validator. Black 23.3.0 và Flake8 6.1.0 dùng cho quality checker. Trên máy này dùng bundled Python 3.12.14; tooling cài local ở `.venv/Lib/site-packages` và không đổi dependency manifest.

```powershell
python tests/workforce/orchestration/async_workflows/run_phase_b.py --isolated-imports --dependency-path .venv/Lib/site-packages
python tests/workforce/orchestration/phase_a/run_phase_a.py --isolated-imports --dependency-path .venv/Lib/site-packages
python tests/workforce/orchestration/async_workflows/run_dependency_regressions.py --suite registry --dependency-path .venv/Lib/site-packages
python tests/workforce/orchestration/async_workflows/run_dependency_regressions.py --suite foundation --dependency-path .venv/Lib/site-packages
python tests/workforce/orchestration/async_workflows/verify_phase_b.py --dependency-path .venv/Lib/site-packages
pnpm --dir tests/workforce/orchestration/async_workflows install --ignore-workspace --ignore-scripts --frozen-lockfile
bun test ./tests/workforce/orchestration/async_workflows/timeline.test.ts ./tests/workforce/orchestration/async_workflows/timeline-render.test.tsx ./tests/workforce/orchestration/async_workflows/timeline-interaction.test.tsx
pnpm --dir examples/web_ui/frontend build
pnpm --dir examples/web_ui/frontend exec eslint src/features/workforce/chat/ticket_timeline
```

Môi trường thực tế: bundled Python `C:/Users/hoang/.cache/codex-runtimes/codex-primary-runtime/dependencies/python/python.exe`; Bun `C:/Users/hoang/.bun/bin/bun.exe`; pnpm 11.25.0 theo runtime. Python async test/Bun/build cần quyền chạy local ngoài sandbox mặc định của phiên này. Không đổi Application Control/chính sách hệ thống.

Runner B từ chối dưới 50 scenario, ID trùng và skip. Quality checker chạy Flake8 serial trên Windows và E203 exclusion đúng config Black của repo. `--format`/ `--export-matrix` là thao tác chủ động riêng; chạy test không tự tái tạo expected artifacts.

## Kết quả và bàn giao

**175 backend + 71 UI = 246 test riêng B; 522 test tổng gồm regression.** UI gồm 11 case React mount/click trong Happy DOM 20.14.6; dependency/lockfile chỉ thuộc PHH test folder. Logs, trước/sau sửa và matrix ở [STATUS](STATUS.md). Build qua với cảnh báo application bundle lớn; chưa gọi provider thật, chạy DB hoặc browser integration.

Global MA/MB/MC/MD chưa được chứng nhận bởi bộ test này. B106 là lát cắt lifecycle với fake dependencies của PHH. Xem [integration request](INTEGRATION_REQUEST_PHH_PHASE_B.md) để nối đúng owner/transaction ở C.
