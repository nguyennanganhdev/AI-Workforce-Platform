# PHD-11/12/13/17 — E2E composition và các gate đang chờ

Người gửi: Phan Hoàng Dũng. Người nhận: Nguyễn Chí Hoàng, Bùi Hữu Nghĩa, Phó Tiến Anh, Phan Huy Hoàng; Đông cung cấp Registry/protocol adapter.

Chưa có code module khác để kiểm thử chuỗi enable MCP → build → eval → publish → request/group/@agent → consent/booking → Settings/rollback. Không thể triển khai thay các owner trong lane này. Bộ mock MCP/client đã có để các owner dùng ngay; không coi fake business implementation là full-platform pass.

## Test factory đề xuất

Chí Hoàng composition app/worker/test DB + seeded MCP fixtures. `WORKFORCE_E2E_FACTORY=module:function` trả async context manager với:

- client: httpx AsyncClient của app **thật** đã include Customer/Execution/Provider routes;
- customer_headers: machine credential test, management_ref: grant test được xác minh;
- count_operations(workflow_id), count_tracking_jobs(workflow_id), count_bindings(external_user_id, ticket_id);
- runtime_state(workflow_id): group_id/session_ids và các observation state từ DB test, không thêm API public trả raw runtime;
- model_tool_counts(): bộ đếm fake model/provider, zero mutation khi mismatch;
- worker drain/restart/lease clock hooks cho các bước integration mở rộng; không fake apply workflow khi dùng full-platform suite.

`tests/workforce/e2e/async_tickets/test_full_platform.py` đã có ba tests read-only, hai chat/reply mismatch, và parallel start. Chưa có factory thì **skip**, không trả success giả. Dũng tiếp tục các assertions/cases còn lại khi owner cung cấp các ports thật. Tests Execution/ASGI/SQL/MCP slice chạy độc lập không cần factory.

## Đầu vào owner và phạm vi kiểm tra còn thiếu

| Owner | Output cần có | Task/cases bị chặn |
|---|---|---|
| Chí Hoàng | Shared DTOs/UOW/migration, identity/routes/residence, jobs lease/fence/not_before, bootstrap/legacy bridge, provider auth, test PostgreSQL/proxy harness | PHD-01/05/06/08/11/13/15–17; concurrent commit/worker/result/download isolation, signature/replay, stream revoke/proxy |
| Đông | Registry/connection snapshots, reviewed effects, pinned AsyncProtocol normalizer, query/quote adapters, calculator registration | PHD-02/03/04/07/14–17; protocol drift/domains/status query/live provider semantics |
| Hữu Nghĩa | Build/reuse decision pipeline, race-aware draft allocation and capability requirements | PHD-11/12/17; same business renamed/partial/draft pending/disabled MCP, missing tracking case 74 |
| Tiến Anh | Canonical identity uniqueness, immutable eval/publish/version/batch, settings/rollback, async suites | PHD-11/12/17; no duplicate agent/version on reuse, publish partial batch, pin v1 while v2 publish |
| Huy Hoàng | Customer API/binding/groups/context/Leader, Workflow/HITL/commands/events/history/SSE/close | PHD-01/05/08/09/11–17; context/approval/operation/cursor isolation, close/reply/event race và replay/live gap |

Case coverage hiện tại:

- Execution-level facts/tests đóng góp cho 59–63, 67–69, 72, 77, 81–84: duplicate/conflict/order/gap, intent correlation, unknown no recreate, atomic apply rollback, namespace, consent và closed/revoked sink, query. **Chưa là toàn case E2E** vì adjacent ports là fake.
- Client-level contract tests đóng góp 64–66/73/75/84–85/88: parser, POST message dedupe, handler failure cursor, per-ticket binding. **Chưa có server SSE/replay/retention behavior thật**.
- 56–58/64–66/68–78/79–88 đầy đủ cần orchestration/DB worker/auth/proxy/retention integration. Full-platform tests 79/80/84–87 sẵn gated; cases khác có matrix và sẽ nối khi dependencies có.

PostgreSQL gate: `WORKFORCE_TEST_POSTGRES_URL` phải trỏ DB test chuyên dụng; test tạo schema ngẫu nhiên và drop **chỉ schema đó** trong finally. Không đọc .env cá nhân, không tự dùng DB production. Hiện máy có docker CLI nhưng daemon không hoạt động, không có DSN được cấp. Browser tooling cũng không có apps/tabs để chạy UI interaction.

Fixtures early handoff: `tests/workforce/fixtures/mock_mcp.py`, `execution_fakes.py`, `reuse_scenarios.json`, `async_partners/` và DEMO.md. Backend đối tác thật ngoài repo, credentials/sandbox chưa cấp; MD/live production chưa đạt.

