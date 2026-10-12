# Trạng thái — Phan Hoàng Dũng

Cập nhật **12/10/2026**, Asia/Saigon. Thực hiện trên working tree hiện tại;
không commit, merge hoặc thao tác Git.

## Kết luận mới nhất — Phase D / D3 lượt 1

**Đã hoàn thành D3 lượt 1 trong môi trường SQL/mock hiện có:**
8 E2E mới và 3 regression Execution mới pass, **zero xfail**.
Ba PostgreSQL crash gates đã viết nhưng skip vì chưa có dedicated DSN.
Không coi skip hoặc SQLite là bằng chứng PostgreSQL concurrency/failover.

Theo xác nhận của người dùng, Phase C và D2 đã xong; D3 tiêu thụ output C7/D1,
Registry D2 và Orchestration D2 trong code hiện tại. Không sửa bảng điều phối
chung hoặc kết luận trạng thái merge của đội.

Chi tiết file, assertions, lệnh chạy và giới hạn:
[PHASE_D_D3.md](PHASE_D_D3.md). Bàn giao D4/CI:
[INTEGRATION_REQUEST_PHD_D3.md](INTEGRATION_REQUEST_PHD_D3.md).

## Phạm vi D3 đã thực hiện

- Duplicate, out-of-order snapshot và terminal barrier.
- Crash sau ACK/trước apply, trong UOW trước commit, sau commit/trước complete
  job; reconnect SQL, worker/service mới, lease reclaim và old-fence rejection.
- Unknown sau timeout-after-write: event hoặc durable query phục hồi operation
  mà không gọi provider create lần hai, không tạo inbox giả cho query.
- Delta gap qua query theo exact pin đã disable; quarantine recovery bằng
  explicit durable job sau khi xác minh/bổ sung dependency.
- Bốn owner xử lý xen kẽ; chống read/query khác manager/area/domain/tenant,
  correlation chéo và job namespace giả.
- Supervisor phục hồi lỗi claim; history/SSE/evidence sau recovery khớp DB.

Chỉ thay đổi `tests/workforce/execution/**`, `tests/workforce/e2e/**`,
`tests/workforce/fixtures/**` và handoff cá nhân. Không phát hiện lỗi production
cần sửa qua các ca D3 này; không thay source của owner khác, contracts,
metadata/migration, CI, root composition, frontend hoặc dependency manifests.
Không tạo NEXT_STEPS.

Các file Python bàn giao:

- `tests/workforce/fixtures/sql_ticket_slice.py`
- `tests/workforce/fixtures/phase_d_execution.py`
- `tests/workforce/fixtures/phase_c_fakes.py`
- `tests/workforce/e2e/async_tickets/test_phase_c_c6.py`
- `tests/workforce/e2e/async_tickets/test_phase_d_d3.py`
- `tests/workforce/e2e/async_tickets/test_phase_d_d3_postgres.py`
- `tests/workforce/execution/provider_events/test_phase_d_d3.py`

## Validation mới nhất

| Suite | Kết quả |
|---|---|
| D3 E2E SQLite + PostgreSQL gate | **8 passed, 3 skipped, 3 subtests passed** |
| Execution toàn bộ, gồm 3 tests D3 mới | **112 passed, 1 PostgreSQL skipped** |
| Foundation Phase C/D1 + Registry D2 + Orchestration D2 | **44 passed, 1 PostgreSQL skipped, 76 subtests passed** |
| C6 sau khi tách helpers dùng chung | **11/11 pass**, PostgreSQL C6 skip |
| Ruff E/F 79 cột trên 7 Python files thay đổi | **Pass** |

Ba lỗi decode SSE trong test D3 mới ở lượt ghép đầu đã sửa; toàn bộ D3 E2E
sau sửa đạt 8/8. Không có lỗi còn mở hoặc strict xfail trong các ca D3 local.
Không cộng các tests deselected vào kết quả pass.

## Còn cần output/môi trường

1. **Nguyễn Chí Hoàng / CI:** thêm D3 và PostgreSQL gates vào workflow chung.
   CI hiện chưa chạy các files D3 mới; DSN local chưa có. Signature/lệnh và
   điều kiện nghiệm thu tại request D3, không tự sửa CI ngoài ownership.
2. **Phó Tiến Anh / D4:** tiêu thụ fixtures và bằng chứng fault/pin/unknown;
   tiếp tục publish pin, long wait, stale evaluation, archive/rollback trong
   Lifecycle. D3 của Hữu Nghĩa và D4 không thuộc kết luận hoàn thành này.
3. **Live/sandbox:** chưa có endpoint/credential/kịch bản provider được cấp.
   Không nghiệm thu MD hoặc production từ mock tests.

Crash harness dùng cancellation tại fault boundaries và SQL reconnect, chưa
phải kill/restart cả app process hoặc DB server. Recovery quarantine trong
bằng chứng là explicit JobPort dispatch; không tuyên bố periodic scanner/TTL
cleanup đã được triển khai. Leader/catalog/quote/HITL/MCP/auth credential
resolver là test ports; SQL/HMAC/Registry/Execution/Workflow/jobs/history/SSE
và evidence chạy implementations đã bàn giao.

## Lịch sử bàn giao

- Phase A/B: [PHASE_A.md](PHASE_A.md), [PHASE_B.md](PHASE_B.md).
- C3: [PHASE_C_C3.md](PHASE_C_C3.md),
  [INTEGRATION_REQUEST_PHD_C3.md](INTEGRATION_REQUEST_PHD_C3.md).
- C6 đã đạt 11 tests, zero xfail sau sửa query-after-revoke và binding mismatch:
  [PHASE_C_C6.md](PHASE_C_C6.md). C7 hiện đã có approval continuation/query
  handler và composition; yêu cầu CI/PostgreSQL mới theo request D3.
