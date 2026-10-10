# PHH Phase B — implementation và kiểm chứng local

Owner: Phan Huy Hoàng. Ngày 2026-10-10.
Baseline develop2: 3a6dcaab69d05e3834d976c640b8fba7901eecb1.
Nhánh bàn giao: dev2PHH theo yêu cầu người dùng. Phạm vi lần này là commit/push
Phase B; chưa tạo PR hoặc merge vào develop2.

Phạm vi theo mục 17.9, cột Huy Hoàng: workflow/replay/SSE/UI với fake
operation/signal; kiểm thử và bàn giao theo PHH-13–17/mục 16. Demo riêng và
ảnh demo đã loại khỏi bản bàn giao theo yêu cầu thu gọn phạm vi.

## Hành vi đã có

- POST/reply qua authenticated actor, route revalidation, scope active, command
  ledger chung và commit trước bounded wait. Retry POST không bootstrap/group/job
  lần nữa. Pending ở deadline ánh xạ 202/watch_request; completed ánh xạ 200
  với workflow_state/next_action. GET có external_user_id.
- Workflow giữ scope/audience/ticket/chat/workflow/group/session/version/protocol
  pins. Hai ticket cùng user/agent vẫn có phiên riêng. Response-only cần published
  read-only policy; interactive không auto-close; external wait chỉ cho operation
  pending đã tạo thành công, có capability tracking theo pinned protocol.
- Continuation dùng JobPort, key băm tuple workflow/cause, lease/fence/revision,
  pinned snapshot, budget và ExecutionGuard. Model turn ngoài UOW. Candidate
  không được đổi pins, xóa cause/budget/operation cũ hay giải quyết approval khác.
- Provider status là fact và operation.status_changed có protocol ID/version,
  không biến thành WorkflowState. Provider/hash/correlation phải khớp; duplicate
  khác hash bị chặn, version cũ không áp lại. Pending HITL giữ state/approval;
  external/timer trigger không giả làm người dùng hoặc consent, không tốn token.
- Close bình thường cần awaiting_confirmation; stop_tracking_only cho phép dừng
  sớm với đúng quyền/binding. Pending approval chặn close. Checkpoint/state/final
  event commit chung; turn đến muộn không phát message hoặc mở lại workflow.
  Close không hủy giao dịch bên ngoài; queued trigger sau close không chạy model.
- Public event dùng payload allowlist, không dump raw facts/checkpoint. Durable
  result/event có cùng message_id. Notify chỉ after_commit; mất signal không mất
  kết quả. History/snapshot/replay kiểm lại grant/audience/workflow/ticket/cursor
  và thứ tự sequence. SSE dùng public ConversationSseService của NCH.
- Timeline key gồm identity/conversation/workflow/ticket/user/chat; POST/SSE
  dedupe message, status card riêng, cursor sau apply thành công. 410 phục hồi
  snapshot, auth denied dừng stream, abort không cập nhật chat đã rời.
  WorkforceApprovalCard nhập qua barrel Execution, lọc approval đúng chat.

## Adapter và ownership

Source nằm trong orchestration/_ingress.py,
workflows/{_boundary,_service,_continuation}.py, partner_events/_service.py
và public exports trong các __init__.py thuộc PHH. Các repository/authorization/
bootstrap/operation/request seam là Protocol, constructor yêu cầu dependency;
không có fake storage/provider trả thành công trong source production.
WorkflowBundle/TurnPlan vẫn là aggregate PHH dùng canonical DTO + proposal A,
chưa promote sang contracts chung.

UI nằm trong chat/ticket_timeline; index.ts xuất component/state/API/follower.
Browser chỉ dùng manager JWT/BFF token được phê duyệt, không machine API key.
HTTP và global UI mounting, approved auth surface cùng adapter thật thuộc C.
Root router chưa mount timeline: tsc kiểm type mọi source, Vite root build chưa
chứng minh bundle timeline; SSR tests kiểm component thực tế riêng.

## Kiểm chứng

**112/112 Python unit tests, 36/36 frontend tests, 242/242 Phase A regression**;
0 fail/skip. Matrix có ID/input/scenario/expected/suite. Fake clock, store/UOW,
lease, runtime, operation và signals chỉ trong test; implementation PHH,
canonical DTO, NCH SSE/transport và Execution ApprovalCard là source thật.

B106 chạy trọn chuỗi request → assigned → on_the_way → arrived → completed →
awaiting_confirmation → explicit close; kiểm group/session/pins, sequence/status
và ticket B không đổi. Các ca khác kiểm concurrent claim, close trong turn,
guard, lease/fence expiry, signal loss, rollback/crash/retry, revocation,
duplicate/hash/version/correlation mismatch, shared close/request idempotency,
POST/SSE message identity và opaque-ID delimiter collision. B112 chặn start mới
trên ticket đã có workflow; retry không tạo checkpoint thừa.
Restart/crash ở đây dùng fake worker/store, chưa kill process/DB thật.

Log cuối:

- [phase-b-test-results.txt](phase-b-test-results.txt)
- [phase-b-ui-test-results.txt](phase-b-ui-test-results.txt)
- [phase-b-phase-a-regression.txt](phase-b-phase-a-regression.txt)
- [phase-b-quality-results.txt](phase-b-quality-results.txt)
- [phase-b-frontend-quality-results.txt](phase-b-frontend-quality-results.txt)
- [phase-b-build-results.txt](phase-b-build-results.txt)

Black 23.3.0, 79 cột và Flake8 6.1.0 theo repo (extend-ignore E203); AST parse
14 Python files B. Frontend lint riêng lane PHH, tsc/Vite build toàn frontend.
Build giữ cảnh báo chunk lớn/path browser của dependency có sẵn.

Từ platform_VP/agentscope:

```powershell
python tests/workforce/orchestration/async_workflows/run_phase_b.py --isolated-imports --dependency-path .venv/Lib/site-packages
bun test tests/workforce/orchestration/async_workflows/timeline.test.ts tests/workforce/orchestration/async_workflows/timeline-render.test.tsx
python tests/workforce/orchestration/phase_a/run_phase_a.py --isolated-imports --dependency-path .venv/Lib/site-packages
python tests/workforce/orchestration/async_workflows/verify_phase_b.py --dependency-path .venv/Lib/site-packages
```

Python thực tế là bundled 3.12.14; Windows Application Control chặn interpreter
venv nên không dùng hoặc thay chính sách máy. Async loop/package symlink cần
chạy ngoài sandbox. isolated-imports bỏ initializer agentscope/app nhưng import
real workforce modules; không phải application bootstrap/full repo regression.
Format/matrix có cờ riêng --format/--export-matrix; suite không tái tạo expected
artifact. Bun config chỉ trong test folder, không đổi shared manifests/lockfile.

Một lệnh Bun thử với --tsconfig-override ở sai vị trí đã gọi test script dự án
cha và tạo lại C:/Users/hoang/app/src/lib/generated/application-config.ts.
Đã dừng và kiểm tra đúng file: không có thay đổi tracked Git, đây là file
generated bị ignore. Không có snapshot trước lệnh để xác nhận nội dung cũ;
không xóa file để tránh mất cấu hình có sẵn. Các lượt test cuối chỉ dùng config
trong thư mục test PHH, không chạy script cha.

## Phần còn lại

Phase C/D chưa triển khai: SQL constraints/CAS/sequence và atomic cross-owner UOW;
AgentScope/provider/protocol resolver; HTTP/middleware/global UI; Redis/worker;
reconciliation/approval cancellation/retention/proxy/restart/sandbox thật.
Chưa CI hoặc production. Không xác nhận MA/MC/MD, full PHH-01–17 hay auth thật từ
fakes. Port/DTO hiện có đủ để làm B; yêu cầu C ở
[INTEGRATION_REQUEST_PHH_PHASE_B.md](INTEGRATION_REQUEST_PHH_PHASE_B.md).
