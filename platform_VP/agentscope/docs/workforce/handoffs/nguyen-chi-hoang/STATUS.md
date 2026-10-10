# Trạng thái — Nguyễn Chí Hoàng

Tên thành viên / branch / commit được kiểm tra (nếu có): Nguyễn Chí Hoàng / `dev_TeamHoang` / `7d7ec2cfcaacc91da80e2f2dde97885ac0ce5fce`.

Task IDs đã hoàn thành: NCH-01; phần contract khởi động của NCH-02; phần Phase A của NCH-13.

Task IDs đang làm / chưa làm: phần service/persistence/UI còn lại của NCH-02–NCH-16 chưa làm; NCH-03 trở đi chưa được đánh dấu hoàn thành.

Files và thư mục đã sửa: `src/agentscope/app/workforce/contracts/`, package root Workforce, schema export script, TypeScript shared contracts, contract tests, tài liệu baseline/status/integration request.

Public exports, API và contract version: Python exports tại `agentscope.app.workforce.contracts`; JSON Schema và TypeScript version `1`. Chưa đăng ký FastAPI endpoint trong Phase A.

V1.4: API/protocol/event samples, invariants đã test và event IDs dùng đối soát: DTO có request/reply/close, request result, public event, provider event, operation snapshot, binding hai ticket. `event_id` và `external_event_id` tách riêng. Detailed provider protocol đang chờ Registry owner.

V1.4: inbox/checkpoint/outbox/replay/close/restart tests: chưa chạy vì Phase A chưa triển khai persistence/worker/SSE. Contract validation và multi-ticket isolation fixture đã pass.

V1.4: provider/backend đối tác thật hay mock, điều kiện onboarding còn thiếu: chưa gọi hệ thống thật; chưa có credential/route/provider sandbox. Phase A chỉ có DTO/ports và local fixtures.

Cách chạy demo hoặc test:

```powershell
.\.venv\Scripts\python.exe -m unittest tests.workforce.foundation.test_contracts -v
.\.venv\Scripts\python.exe scripts\workforce\export_contracts.py
```

Kết quả test: 9 contract tests pass bằng Python 3.11.15; compileall pass; schema export pass; TypeScript contract type-check pass bằng `tsc.cmd`; `git diff --check` pass. Pytest chưa chạy do `.venv` thiếu package pytest; `pnpm` chưa có trên PATH.

Schema/migration/dependency requests: Alembic head hiện tại `0008_area_platform`; Phase A chưa tạo migration. Cần cài nhóm dev nếu CI bắt buộc dùng pytest.

Đầu vào module khác đã dùng (fake hay thật): chưa dùng implementation module khác; các port là boundary/fake-ready.

Integration requests còn mở: xem `INTEGRATION_REQUEST_NCH_PHASE_A.md`; các yêu cầu này phục vụ phase sau và không chặn contract hiện tại.

Live verification còn thiếu: toàn bộ FastAPI, PostgreSQL transaction/uniqueness, Redis signal, SSE, provider signature, AgentScope continuation và UI runtime.

Việc tiếp theo AI cần làm: Phase kế tiếp triển khai Identity/PartnerRouting/Foundation persistence theo NCH-03/NCH-04/NCH-12, sau đó durable delivery NCH-14; chỉ nối concrete DTO của module khác khi owner đã bàn giao output và tests.
