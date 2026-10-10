# Phan Huy Hoàng — trạng thái triển khai PHH

Ngày kiểm tra: 10/10/2026. Nhánh bàn giao theo yêu cầu người dùng: `dev2PHH`, từ phần triển khai local `feat/wf-orchestration`, baseline `develop2@6bc7d60d1bcf0d1bf49ad9214fad22791b29c274`. Người dùng đã yêu cầu commit/push lên nhánh riêng; chưa merge/deploy. Việc công bố nhánh không thay thế các gate tích hợp còn thiếu.

## Kết luận

Đã triển khai và kiểm thử các lát cắt local của 3 giai đoạn. **Chưa có giai đoạn nào đạt đầy đủ gate tích hợp/nghiệm thu**. Không đánh dấu PHH-01–17 hoàn thành end-to-end từ các kết quả local.

Python sau khi bổ sung danh mục kịch bản: **227 tests PASS, 14 subtests PASS**, 0 failure. Trong đó có 150 ca mới chạy độc lập (50/G1, 50/G2, 50/G3) và 1 kiểm tra tính toàn vẹn danh mục. React ở lượt trước: **7 behavioral tests PASS**; TypeScript strict PASS cho 2 component PHH; không đổi UI trong lượt này. Bằng chứng Python hiện tại: `PYTEST_RESULTS.xml`. SQL smoke tests dùng SQLite; PostgreSQL chỉ compile DDL, chưa chạy database thật. Docker daemon chưa được xác minh lại trong lượt này.

Danh mục có **55 kịch bản mỗi giai đoạn**: [G1](KICH_BAN_TEST_G1.md), [G2](KICH_BAN_TEST_G2.md), [G3](KICH_BAN_TEST_G3.md). Mỗi danh mục gồm 50 ca tự động PASS local và 5 ca tích hợp NOT_RUN với điều kiện/runner cần có. Tổng 165 kịch bản; không đếm 15 ca NOT_RUN vào số pass. Tài liệu được sinh từ catalog và JUnit để giữ ID/input/expected/status đồng bộ; không tạo lại bản phản biện đã xóa.

## Theo giai đoạn

| Giai đoạn | Đã có code và bằng chứng | Phần còn thiếu trước gate |
|---|---|---|
| G1 / PHH-01–06 | Conversation/run internal models; SQL repository+CAS; capability selection; version/session intent; runtime adapter boundary; role context; handoff/ACK/complete/timeout/cancel/limits; fact provenance/stale quote guards | Schema normalization/migration theo contract; concrete Foundation/catalog/Execution/AgentScope hooks; model-driven Leader/Planner flow; proposal/state đầy đủ; PostgreSQL concurrency/restart; chưa coi prompt/context builder là Leader thực sự đã chạy |
| G2 / PHH-07–12 | ID/name/pending-question routing; entity reference; manager message persist/retry/dedupe; selected facts helper; direct target guard; member-add/recovery; eval facade; Chat UI và tests | HTTP routes, actual delivery/eval/tool guards, full pending-question/message projector, membership history/usage API, context transfer API, backend cancel/resume, @ autocomplete hoàn chỉnh; ApprovalCard/shared transport thật, toàn app build/lint |
| G3 / PHH-13–17 | Ticketed ingress+immutable binding/idempotency/UOW enqueue; SQL storage proposal; lifecycle policy; checkpoint fence/cause-dedupe/HITL/close pure logic; public projection/cursor validation/SSE encoding; ticket UI | Non-ticketed ingress, bounded-wait/GET-result/auth, worker/lease/timers/runtime continuation, public event DB log/replay/SSE/history/snapshot, atomic close/checkpoint/event commits, unique conflict handling PostgreSQL, E2E hai backend/proxy/retention/recovery |

## Files và exports

- Backend: chỉ `src/agentscope/app/workforce/orchestration/**`.
- Frontend: chỉ `examples/web_ui/frontend/src/features/workforce/chat/**`.
- Tests: chỉ `tests/workforce/orchestration/**`.
- Docs/handoff: chỉ `docs/workforce/handoffs/phan-huy-hoang/**`.
- Public Python services: ConversationService, CapabilityRouter, RunService, SharedStateService, HandoffService, TeamRuntimeAdapter, MessageService, MemberService, EvaluationRunner. SQL repository import riêng để pure package không buộc tải SQLAlchemy.
- TicketIngress import từ workflows/_ingress.py; chưa đăng ký Customer API hoặc Provider Event API.
- Component: WorkforceChat, TicketTimeline. Props do host cung cấp; không có fake backend/data mặc định.
- Shared DTO/Scope: chưa tạo package thay thế. Internal dataclasses là persistence values của PHH, seam signatures cần composition bridge tới DTO/ports dùng chung.

## Những tình huống đã kiểm tra

Lượt kiểm tra lại bổ sung 3 tests: hai recovery worker chạy đồng thời chỉ commit một membership; message tới pending member bị chặn nhưng member cũ giữ session; router đồng hạng với coverage chồng lấn một phần không phụ thuộc thứ tự ID. Ca router mới FAIL trước sửa; đã sửa bằng kiểm tra overlap trên toàn bộ nhóm ứng viên đồng hạng cao nhất, vẫn cho phép các năng lực bổ sung không chồng lấn. Tổng suite sau sửa: 76 tests và 14 subtests PASS. Không tạo lại bản Markdown phản biện.

Đã sửa ba lỗi membership/router: thêm agent dùng `pending_members` riêng, giữ run đang chạy để task cũ ACK/complete; add/recovery đối soát đúng session/version/hash để trả thành công khi cùng thao tác đã hoàn tất; router trả ambiguous khi hai agent có cùng năng lực liên quan đến yêu cầu dù năng lực ngoài yêu cầu khác nhau. `membership_operation_id` được persist và giữ nguyên qua retry, không dùng run revision làm khóa provisioning. Có 10 test mới (9 membership/router, 1 SQLite reopen), gồm cancel trong lúc add, pending member không nhận task, retry sau task update, không thay pending intent và không chấp nhận session khác. Bản Markdown phản biện đã được xóa theo yêu cầu; chưa có thay đổi triển khai HTTP/runtime thật.

Lượt kiểm thử bổ sung ngày 10/10: 4 ca đầu tiên FAIL trước sửa, tương ứng 3 nhóm lỗi (retry message vào run đã hủy; task completion/ACK sau run hủy; eval thiếu/khác scope). Đã sửa và bổ sung tổng cộng 9 test hồi quy trong `test_adversarial_review.py`: retry không chuyển run/group, session bị gỡ không nhận message pending, receipt đã delivered/completed vẫn idempotent sau cancel, cleanup cancellation vẫn được phép. Không skip/xfail để che lỗi.

Message pending mới persist run_id/group_id; message cũ thiếu binding bị chặn MESSAGE_BINDING_REQUIRED, không suy ra run mới để gửi. Integration adapter vẫn phải revalidate run/session/fence ở thời điểm thực thi để xử lý race cancel sau khi transaction kiểm tra đã đóng; test fake local không chứng minh race xuyên process.

G1: chọn đúng subset, draft/revoked/foreign scope bị chặn, candidate version/hash/capability tamper, hai group giữ session/pin riêng, CAS cạnh tranh bằng fake, rollback/fact protection, stale/expired quote, ACK không complete, unauthorized task actor, late result/cancel/loop/budgets, recovery sau provisioning timeout, ACK/result race và capacity khi task hết hạn.

G2: mention ID giữ session, unknown/trùng tên, pending question/mơ hồ, selected entity, không copy private history, direct target guard, add cross-batch/duplicate/recovery, evaluation mode/backend guard/failure/cancel, message timeout/retry cùng ID. UI loading/error/dedupe/pending/approval slot, retry cùng client ID, direct/add/quote/cancel/resume callbacks, expired quote và close đúng workflow/revision.

G3 local: read-only/interactive/tracking continuation và unknown, request retry/conflict, cùng ticket concurrent bằng fake, A1/B1/A2/B2 vào group đã bind, tuple sai/thiếu reference/closed/authority fields bị chặn, remap không đổi chủ, rollback ingress khi enqueue lỗi, fencing/cause duplicate, status không phá HITL, projection bỏ secret, cursor scope/expired, close pure CAS không reopen. SQLite chứng minh lưu conversation/command/binding qua engine reopen; chưa chứng minh PostgreSQL transaction/race semantics.

## Cách chạy lại

Từ `platform_VP/agentscope`:

```powershell
.\.venv\Scripts\python.exe -m pytest tests/workforce/orchestration -q
node tests/workforce/orchestration/check_ui.cjs "$env:TEMP\phh-ui-check-20261010"
```

Môi trường Python local .venv đã cài SQLAlchemy/aiosqlite/asyncpg/pytest/tzdata; không sửa pyproject/dependency chung. ensurepip khởi tạo ban đầu lỗi; môi trường được bổ sung packages vào .venv/Lib/site-packages bằng bundled pip. Node UI dependencies ở thư mục TEMP của host khi chạy ngoài sandbox; gồm TypeScript 6.0.2/React 19.2.6/@types/react 19.2.14 và React Testing Library/jsdom. Không thay package.json/pnpm lock dùng chung.

Trong host này asyncio Windows bị treo trong sandbox; test đã chạy ngoài sandbox với quyền chạy local. UI runner cũng dùng host TEMP ngoài sandbox. Test loader `_support.py` import module PHH độc lập, không tải app bootstrap/FastAPI của toàn hệ thống; kết quả này chưa xác minh production import/bootstrap.

## Requests đang mở và việc tiếp theo

Xem `INTEGRATION_REQUEST_PHH_FOUNDATION.md`: shared contracts/UOW, schema/migration, pinned runtime hooks, routing/auth, JobPort/result/event signal, real catalog/Execution/Evaluation, UI wiring. Chưa gửi message tới thành viên hoặc sửa vùng của họ.

Ưu tiên tiếp: chốt contracts và schema với owner, hoàn thiện local G1 còn thiếu rồi nối adapter thật, chạy PostgreSQL gates; sau đó nghiệm thu G2 và hoàn thiện durable G3/API/SSE. Chưa chạy CI, provider sandbox hoặc production; không có credential/booking thật được gọi.
