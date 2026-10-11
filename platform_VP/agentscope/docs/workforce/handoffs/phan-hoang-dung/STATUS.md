# Trạng thái — Phan Hoàng Dũng

Cập nhật **11/10/2026**, Asia/Saigon. Nhánh **`feat/wf-execution`**.
Commit đầu vào **`69e21f7`**, đã chứa C1–C5; C5 merge tại `830cdac`.

## Kết luận mới nhất

**Đã triển khai bộ E2E C6 trong phạm vi Dũng. Chưa nghiệm thu C6 hoàn toàn:**
test query sau revoke phát hiện lỗi tại hook Orchestration của Phan Huy Hoàng.
Không tính `xfail` hoặc các gate cần môi trường là pass. Chi tiết triển khai:
[PHASE_C_C6.md](PHASE_C_C6.md); yêu cầu xử lý:
[INTEGRATION_REQUEST_PHD_C6.md](INTEGRATION_REQUEST_PHD_C6.md).

- Phase A/B và lane C3 đã bàn giao; giữ tài liệu lịch sử
  [PHASE_A.md](PHASE_A.md), [PHASE_B.md](PHASE_B.md),
  [PHASE_C_C3.md](PHASE_C_C3.md).
- C4/C5 đã có và đã tiêu thụ. Không còn báo thiếu Workflow sink, query hook
  hoặc SQL runtime evidence/evaluation của các bước này.
- C6 nối Customer HTTP → SQL command/job → continuation/Execution → provider
  HTTP ký HMAC → SQL inbox/job/processor/Registry → Workflow apply cùng UOW →
  continuation/evidence → public history/SSE → explicit close.
- Timer đi qua durable query job, `OperationReconciler` và canonical query hook;
  không tạo inbox/cause provider giả.
- Consent HTTP dùng command ledger C4 thật và adapter composition trong fixture;
  ACK consent và kết quả continuation có command riêng, cùng caller UOW.

## Phạm vi thay đổi C6

Chỉ `tests/workforce/e2e/**`, `tests/workforce/fixtures/**` và thư mục handoff
này. Không thay source của Foundation, Registry, Builder, Lifecycle,
Orchestration, contracts, root composition, migration hoặc CI. Không thêm
bảng/cột production và không đổi frontend. Không tạo NEXT_STEPS.

## Những gì bộ C6 kiểm tra

- Consent HTTP đúng audience, retry trước/sau consume không gọi create lần hai.
- Raw HMAC xác thực body; ACK chỉ sau inbox/job commit; receipt không lộ owner.
- Worker tạo lại đọc inbox đã commit; operation, Workflow/checkpoint, event log
  và continuation job rollback cùng nhau nếu sink lỗi.
- Duplicate/conflicting ID, stale version, correlation không bind, credential
  revoke sau ACK; close/revoke route giữ provider fact và ngăn public send.
- Current protocol đổi/disable không thay exact pin của workflow đang chạy.
- Hai chat cùng user có workflow/conversation/group/session/approval/cursor
  riêng; reply xen kẽ; stop/close A không làm đổi B.
- HTTP SSE thật, disconnect/reconnect bằng Last-Event-ID khớp durable history.
- Năm case C5 chạy trên runtime SQL với raw provider và query jobs C6;
  report/evidence lưu SQL, release check và replay không gọi model/provider lại.

Lệnh chạy, kết quả và giới hạn môi trường được ghi tại
[PHASE_C_C6.md](PHASE_C_C6.md).

Validation C6 cuối lượt: **10 tests đạt, 1 strict xfail, 1 PostgreSQL skip**.
Regression các module khác ngoài C6: **274 passed, 9 skipped,
178 subtests passed**. Orchestration: **260 passed, 1 failed,
97 subtests passed**; failure là test bounded wait 1 giây có sẵn nhận 202
thay vì 200, cũng tái hiện khi chạy riêng. Ruff E/F 79 cột: pass.

## Điểm còn chặn và owner

1. **Phan Huy Hoàng:** `WorkflowService.apply_query_result` sau route revoke
   gọi enqueue trigger, authorization ném `PermissionError` và rollback cả
   operation fact. Cần giữ fact đã xác minh, không phát Workflow/public send,
   tương tự `apply_external_event`. Có strict xfail tái hiện; sau fix phải bỏ
   marker và chạy lại để nghiệm thu.
2. **Nguyễn Chí Hoàng / môi trường test:** chưa có dedicated PostgreSQL DSN;
   Docker CLI có nhưng Linux engine không chạy. Gate PostgreSQL C6 đã viết,
   chưa kiểm chứng locks/race bằng SQLite.
3. **Nguyễn Chí Hoàng, C7:** mount routers/handlers, approval authorizer và
   continuation bridge trong composition thật; migration additive và CI.
   `WORKFORCE_E2E_FACTORY` chưa có; ba gate application factory cũ vẫn skip.

Leader/model, catalog/runtime authority, quote/HITL, API-key resolver,
secret resolver và MCP/provider là test dependencies có dữ liệu kiểm soát.
DB/UOW/identity/routing/HMAC/jobs/Registry/Execution/Workflow/history/SSE/
Lifecycle evidence là implementations đã bàn giao. Không kết luận đã chạy
live model/provider, DB production hay composition toàn ứng dụng.

## Bàn giao trước đó

[INTEGRATION_REQUEST_PHD_C3.md](INTEGRATION_REQUEST_PHD_C3.md) giữ tiêu chí C3
và migration notes; phần sink C4 đã được giải quyết. Các quyết định shared
contract còn lại theo
[INTEGRATION_REQUEST_PHD-01_PHASE_A.md](INTEGRATION_REQUEST_PHD-01_PHASE_A.md).
Request mới nhất và thứ tự gỡ blocker nằm trong request C6; không tự mở C7
hoặc cập nhật gate của cả đội.
