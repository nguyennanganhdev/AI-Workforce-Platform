# Trạng thái — Phan Huy Hoàng

Ngày cập nhật: **2026-10-12**. Baseline bàn giao C5:
`develop2@830cdacd56f868d509d208b91b9a6bc29d70c935`.

**Trạng thái mới nhất:** C4 đã hoàn thành và merge qua PR #63 tại
`86fa2931bbfd54d064798e00e0998429c6ac9cb5`; output C4 đã được C5 sử dụng.
Hai lỗi acceptance C6 đã xử lý: query sau revoke giữ operation fact và không
phát Workflow/public send; reply sai immutable tuple trả
`409/WORKFLOW_BINDING_MISMATCH` sau kiểm tra quyền. Sai user hoặc grant bị
revoke vẫn trả `403/AUTHORIZATION_DENIED`. Chi tiết và validation mới nhất
tại [PHASE_C_C4.md](PHASE_C_C4.md).

Phase A của cả 6 thành viên đã merge. Phase B của 5 thành viên còn lại cũng đã merge; phần này triển khai mới công việc Phase B của Phan Huy Hoàng trên baseline đó, không lấy hoặc cherry-pick code từ PR #58.

## Phạm vi đã triển khai

Phần độc lập của **PHH-13–PHH-17 trong Phase B** đã có:

- Partner ingress kiểm tra customer actor, route/scope/audience, idempotency và binding bất biến giữa external ticket/conversation với workflow/conversation/group.
- Workflow cho ba pattern `response_only`, `interactive`, `external_tracking`; reply dùng revision/CAS, close có revision guard và chặn message đến muộn.
- Continuation dùng trigger dedupe, lease/fencing, checkpoint, budget guard và không giữ transaction trong lúc model/tool chạy.
- External event dùng operation fact đã được Execution ghi trong cùng UOW; revoke/closed workflow không phát public event hoặc đánh thức runtime.
- Public event log, history, snapshot và SSE replay-first; signal chỉ gửi sau commit và không có outbound webhook sender.
- Timeline web tách state/cursor theo identity + conversation + workflow + external ticket, chống event đi chéo hai hộp chat, dedupe message/event và recovery bằng snapshot.

Chi tiết chữ ký, transaction ordering và giới hạn Phase B: [PHASE_B.md](PHASE_B.md). Việc cần owner khác nối ở Phase C: [INTEGRATION_REQUEST_PHH_PHASE_B.md](INTEGRATION_REQUEST_PHH_PHASE_B.md).

## Kiểm chứng

```powershell
$env:PYTHONPATH=(Resolve-Path src)
.\.venv\Scripts\python.exe -m unittest discover -s tests\workforce\orchestration\async_workflows -p "test_*.py" -v

cd examples\web_ui\frontend
node --experimental-strip-types --test src\features\workforce\chat\ticket_timeline\state.test.mjs
node_modules\.bin\eslint.cmd src\features\workforce\chat\ticket_timeline
npm.cmd run build
```

Kết quả tại lần bàn giao: **14/14 backend tests pass**, **4/4 timeline tests pass**, ESLint vùng PHH pass, TypeScript/Vite build pass và Python compileall pass.

Test bao phủ hai ticket A/B cùng user nhưng khác group/session; retry idempotent; tuple sai không dispatch; reply CAS; response-only auto-close; external-tracking ngủ không tiêu thêm turn; HITL defer external trigger; invalid decision rollback; close/update race; event after-commit; audience/cursor replay; và closed barrier phía UI.

Regression lân cận: Foundation **19/19 pass**, Registry **24/24 pass**. Suite Builder/Lifecycle hiện còn một test Lifecycle `test_builder_query_only_dialect_explicit` fail trong baseline đã merge, không đi qua module PHH. Phase A chạy trực tiếp **241/242 pass**; test còn lại yêu cầu `rfc3339-validator` nhưng môi trường hiện tại không có checker. Execution pytest chưa chạy vì `.venv` không có `pytest`. Các điểm này được ghi nhận, không sửa code owner khác trong lane PHH.

## Chưa thuộc nghiệm thu Phase B

Chưa có PostgreSQL repository/migration, FastAPI route thật, application composition, worker deployment hoặc E2E với Redis/provider thật. Đây là đầu việc Phase C/D và phải dùng integration request, không được hiểu fake test là production persistence. Không sửa shared contracts, migration, global route, dependency hoặc lockfile trong phần triển khai này.

## Điều phối Phase C — gate C4 đã hoàn thành

Phase B của Phan Huy Hoàng và C1–C3 đã merge trước khi C4 bắt đầu. C4 nối
production Customer POST → persisted request/binding/workflow → bounded wait →
Leader continuation → public event log/SSE. Mỗi ticket/hộp chat vẫn có
workflow/group/session riêng; HTTP không chạy model trong transaction. C4 hiện
đã merge và không còn là gate đang chờ.

Bàn giao schema/table/index của request, binding, workflow, checkpoint và event
log cho Chí Hoàng để gom migration C7; dùng injected UOW, không tạo engine hoặc
migration riêng. Runtime/evidence port C4 đã được C5 sử dụng. Theo dõi trạng
thái mới nhất tại [../PHASE_C_SEQUENCE.md](../PHASE_C_SEQUENCE.md).

## Cập nhật Phase C4 — 2026-10-11

C4 đã được triển khai trên baseline `develop2@7bfdc6097fbbd8a5cfeddaf8f84f60b2ddf798c3`.
Đã có SQL repositories/metadata, Customer API router factory, durable workflow
job handler, injected Leader bootstrap/runtime, Execution operation/query hook,
public event replay/SSE và committed-turn evidence cho C5. Kết quả kiểm thử:
**5/5 C4 SQL/HTTP integration** và **14/14 Phase B regression** pass.

Chi tiết: [PHASE_C_C4.md](PHASE_C_C4.md). Điểm nối C5/C6/C7:
[INTEGRATION_REQUEST_PHH_C4.md](INTEGRATION_REQUEST_PHH_C4.md). Không có
migration/global composition/worker deployment trong C4; các phần đó vẫn thuộc
C7. C4 đã merge qua PR #63; C5 sau đó đã hoàn thành và merge qua PR #64.
Handoff C4 hiện là đầu vào trực tiếp cho C6 và C7, không còn trạng thái chờ merge.
