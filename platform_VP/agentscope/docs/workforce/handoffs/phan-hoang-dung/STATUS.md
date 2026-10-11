# Trạng thái — Phan Hoàng Dũng

Cập nhật **12/10/2026**, Asia/Saigon. Nhánh **`feat/wf-execution`**.
Commit đầu vào **`69e21f7`**, đã chứa C1–C5; C5 merge tại `830cdac`.

## Kết luận mới nhất

**C6 hoàn thành trong môi trường kiểm thử hiện có: 11 passed, zero xfail.**
Query sau revoke giữ operation fact và không phát Workflow/public send;
binding mismatch của caller đã được xác thực trả `409/WORKFLOW_BINDING_MISMATCH`.
PostgreSQL gate skip vì chưa có dedicated DSN, không tính là pass.
Chi tiết triển khai: [PHASE_C_C6.md](PHASE_C_C6.md); bàn giao C7:
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

Phần E2E gồm `tests/workforce/e2e/**`, `tests/workforce/fixtures/**` và handoff
này. Output Orchestration được mô tả trong handoff PHH C4. Foundation,
Registry, Builder, Lifecycle, contracts, root composition, migration và CI
không thay đổi. Không thêm bảng/cột production hoặc NEXT_STEPS.

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

Validation C6 cuối lượt: **11 passed, 0 xfail, 1 PostgreSQL skip**.
Regression các module khác ngoài C6: **274 passed, 9 skipped,
178 subtests passed**. Orchestration: **262 passed, 97 subtests passed**.
Ruff E/F pass trên tám file Python thay đổi; lệnh kiểm thử xem
[PHASE_C_C6.md](PHASE_C_C6.md).

## Đã xử lý và giới hạn môi trường

1. **Query-after-revoke và binding mismatch đã xử lý.** Strict xfail đã bỏ;
   test kiểm tra fact commit, Workflow/history/evidence không đổi, worker idle
   và không thêm model call. Bàn giao Orchestration tại
   [PHH C4](../phan-huy-hoang/PHASE_C_C4.md).
2. **Nguyễn Chí Hoàng / môi trường test:** chưa có dedicated PostgreSQL DSN;
   gate PostgreSQL C6 đã viết nhưng chưa chạy. Không dùng SQLite để kết luận
   locks/race PostgreSQL đã được kiểm chứng.
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
Các yêu cầu composition/migration/CI còn lại nằm trong request C6.
Không thực hiện commit, merge hoặc thao tác Git trong lượt này.
