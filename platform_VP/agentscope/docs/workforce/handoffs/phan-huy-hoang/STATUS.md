# PHH — Phase B

Ngày: 2026-10-10. Owner: Phan Huy Hoàng.
Baseline: origin/develop2 tại 3a6dcaab69d05e3834d976c640b8fba7901eecb1.
Nhánh bàn giao: dev2PHH theo yêu cầu người dùng. Phạm vi lần này là commit/push
Phase B; chưa tạo PR hoặc merge vào develop2.

**Đã triển khai Phase B độc lập theo mục 17.9:** workflow ba pattern,
checkpoint/continuation, request/result bounded wait, public replay/SSE/snapshot
và timeline UI. Kiểm chứng với fake repository/UOW/runtime/operation/signal trong
test, cùng implementation SSE và frontend transport thật của NCH.
Không chuyển sang Phase C/D hoặc xác nhận production readiness.

Yêu cầu mới của người dùng cho phép B, thay thế giới hạn chỉ A ở bàn giao cũ.
B không cần chờ các service thật của owner khác; chữ ký chưa thống nhất được
ghi thành yêu cầu nối adapter ở C. Không đánh dấu toàn bộ PHH-01–17 hoàn thành.

| Phạm vi | Đầu ra Phase B | Phần Phase C còn lại |
|---|---|---|
| PHH-13/14 | PartnerIngressService, WorkflowService, ba pattern, binding/reply/close | HTTP mounting, auth/routing/bootstrap và SQL adapter thật |
| PHH-15 | WorkflowContinuation, cause dedupe, lease/fence/guard, pins/budget/HITL | AgentScope continuation, session và durable worker/lease adapter |
| PHH-16 | PublicEventWriter, ConversationEventService, history/snapshot/NCH SSE, bounded result wait | DB sequence/cursor/retention, ledger và auth/Redis deployment |
| PHH-17 | Timeline, per-binding controller, ApprovalCard import, component/transport tests | Global route, manager JWT/BFF, Execution approval wiring |

Kiểm thử cuối: **112 backend + 36 frontend = 148 kịch bản Phase B**, không
gộp vòng lặp thành nhiều test. **242 ca Phase A** chạy lại kiểm tra hồi quy.
Kết quả/log/lint/build ở [PHASE_B.md](PHASE_B.md); ca kiểm thử ở
[PHASE_B_TEST_MATRIX.md](PHASE_B_TEST_MATRIX.md).

Source chỉ trong orchestration, UI trong chat/ticket_timeline, test trong
tests/workforce/orchestration và tài liệu trong handoff PHH. Không sửa shared
contracts, owner khác, migrations, manifests/lockfile hoặc root UI.

Tiếp theo là Phase C theo
[INTEGRATION_REQUEST_PHH_PHASE_B.md](INTEGRATION_REQUEST_PHH_PHASE_B.md).
Phase A lịch sử giữ ở [PHASE_A.md](PHASE_A.md) và
[phase_a/QA_RESULTS.md](phase_a/QA_RESULTS.md).
