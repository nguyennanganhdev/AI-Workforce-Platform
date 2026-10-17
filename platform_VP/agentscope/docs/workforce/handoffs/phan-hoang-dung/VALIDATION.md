# Kiểm chứng Execution — Phan Hoàng Dũng

Ghi chép lịch sử trước baseline `53a139b`. Kết quả/lệnh hiện tại sau code PHH
và hoàn thiện Phase A/B được ghi ở [PHASE_B.md](PHASE_B.md) và [STATUS.md](STATUS.md).

Ngày 10/10/2026; baseline cũ `6bc7d60`, lần nối contracts Phase A dựa trên HEAD `383a387`, branch `feat/wf-execution`. Đã kiểm tra output Chí Hoàng ở `1ff8fb6`/`a99d506`. Đây là kiểm chứng module/DTO interoperability và regression SDK, chưa nghiệm thu toàn platform. Phạm vi và đầu ra còn thiếu: [STATUS.md](STATUS.md).

## Kết quả đã chạy

| Kiểm tra | Kết quả | Giới hạn |
|---|---|---|
| Suite cuối: Execution/E2E slice + shared contracts tests + regression Toolkit/Permission/MCP headers | **153 passed, 50 skipped, 11 subtests passed**, 17.38 giây | Có 9 contract tests của Chí Hoàng; 4 skip thuộc lane Dũng, 46 skip do Windows/Unix/Bash/symlink của suite SDK hiện có |
| Execution/E2E subset trong suite cuối | **64 passed, 4 skipped** | Thêm 16 cases DTO interoperability; SQLite/fake adapters và mock MCP stdio thực, chưa production composition |
| Kết quả trước Phase A, lưu đối chiếu | 48 passed/4 skipped riêng; 128 passed/50 skipped/11 subtests khi kèm SDK | Kết quả lịch sử; không dùng thay cho suite cuối |
| Ruff E/F, line length 79 | All checks passed | Chỉ source/test trong lane |
| mypy | Success, 23 source files | Kiểm tra typed definitions; các port còn dùng `Any` chờ DTO/Protocol chung |
| ESLint feature approvals | Exit 0 | Bao gồm demo và external operation component |
| TypeScript `tsc -b` | Exit 0 | Frontend project |
| Frontend production build | Exit 0 | Có cảnh báo Vite về `mime-types`/`path` browser externalization và chunk lớn; không sửa ngoài lane |
| Browser UI smoke | **Chưa chạy** | Browser inventory trả `apps=[]`, `browsers=[]`; Vite đã khởi chạy và dừng |
| PostgreSQL races, full-platform E2E, provider sandbox | **Chưa chạy** | Chưa đủ môi trường/implementation/credential được bàn giao |

Suite cuối chạy sau các thay đổi logic/tests Phase A. Frontend build và ESLint cũng đã chạy lại sau chỉnh creation status. Không gọi model trả phí, không booking thật, không gửi event sang backend đối tác thật. Đã kiểm tra lại Docker: pipe dockerDesktopLinuxEngine không tồn tại; WORKFORCE_TEST_POSTGRES_URL chưa được đặt.

DTO mới đã được test từ package contracts thực: Scope, ActorContext, PartnerAudience, ToolDescriptor, PartnerApprovalDecision, RequestResult, ProviderEventEnvelope/Receipt và ErrorResponse. Các fake adapter không thay concrete auth/routing/jobs của Foundation. Xem [PHD-01 Phase A](INTEGRATION_REQUEST_PHD-01_PHASE_A.md) cho chữ ký còn thiếu/khác.

## Chạy lại

Working directory: `platform_VP/agentscope`. Python 3.11; môi trường tạm `%TEMP%\wf-execution-venv` đã cài project với extras `service,storage-sql`, `pytest`, `aiosqlite`, `asyncpg`. Do editable install gặp encoding đường dẫn Windows, dùng wheel dependencies và `PYTHONPATH=src` để kiểm tra source checkout.

```powershell
$env:PYTHONIOENCODING = 'utf-8'
$env:PYTHONPATH = (Join-Path (Get-Location) 'src')
& "$env:TEMP\wf-execution-venv\Scripts\python.exe" -m pytest tests/workforce/execution tests/workforce/e2e -q -rs -p no:cacheprovider --basetemp "$env:TEMP\wf-execution-pytest-final-owned"

& "$env:TEMP\wf-execution-venv\Scripts\python.exe" -m pytest tests/workforce/execution tests/workforce/e2e tests/workforce/foundation/test_contracts.py tests/toolkit_test.py tests/permission_engine_test.py tests/permission_mode_test.py tests/mcp_runtime_headers_test.py -q -p no:cacheprovider --basetemp "$env:TEMP\wf-execution-phase-a-verified"

python -m ruff check src/agentscope/app/workforce/execution tests/workforce/execution tests/workforce/e2e tests/workforce/fixtures --select E,F --line-length 79
python -m mypy src/agentscope/app/workforce/execution --follow-imports=skip --ignore-missing-imports --disallow-untyped-defs --disallow-incomplete-defs
pnpm.cmd --dir examples/web_ui/frontend exec eslint src/features/workforce/approvals
pnpm.cmd --dir examples/web_ui/frontend exec tsc -b
pnpm.cmd --dir examples/web_ui/frontend build
```

Ruff/mypy dùng Python tooling có sẵn của workspace. Dependencies frontend được cài theo frozen lockfile, ignore scripts; không đổi package manifest/lockfile. Lần triển khai trước cần cấp quyền ngoài sandbox cho subprocess/named pipe; lần nối Phase A chạy với permission profile disabled do user cung cấp, không xin thêm quyền.

## Bốn test còn gate

1. `test_postgres_parallel_consent_execution_and_inbox_apply_once`: cần `WORKFORCE_TEST_POSTGRES_URL` là dedicated test DSN. Test tạo schema UUID riêng và chỉ drop schema do chính test tạo. Docker CLI có nhưng daemon không chạy trong phiên này. SQLite không chứng minh row locks, race hoặc commit order trên PostgreSQL.
2. `test_case_79_read_only_auto_close_without_tracking`.
3. `test_cases_80_84_85_86_ticket_context_and_mismatch`.
4. `test_case_87_parallel_start_has_one_binding_and_group`.

Ba test cuối cần `WORKFORCE_E2E_FACTORY=module:function` từ composition thật: app, DB, worker, auth/mapping và Registry/Builder/Lifecycle/Orchestration. Chi tiết gate/factory đã gộp vào [PHASE_B.md](PHASE_B.md). Không tạo Customer API hoặc runtime giả để làm các test này pass.

## Bằng chứng và phần chưa xác minh

Đã kiểm tra guard/effect/pins, calculator integer, quote/TTL/audience/decider, approval consume, intent trước network, lỗi sau provider write thành unknown, sync reconciliation không recreate, early event/correlation, durable inbox ACK, dedupe/conflict, stale query CAS, delta ordering/quarantine, atomic Workflow sink rollback, closed/revoked fact persistence và hai group/ticket tách state. Có kiểm tra `.call`, `__call__` và assembly Toolkit bằng SDK thực; HTTP tests dùng ASGI app và SQL repository thực của module.

Tests với fake Workflow/Job/Auth/Registry ports chỉ chứng minh hợp đồng và atomicity trong cùng session fixture. Chưa chứng minh worker lease fencing, production auth/signature/rate limits, migrations của Foundation, SSE server replay/live/retention, checkpoint-close race, dynamic agent selection, batch build/publish hoặc recovery toàn hệ thống. Những phần này cần owner bàn giao trước khi nghiệm thu PHD-11/12/13/17 toàn chuỗi.

Demo UI riêng: chạy Vite và mở `/src/features/workforce/approvals/demo/index.html`. Cần browser để kiểm tra loading, lỗi gửi, expiry, double click, đổi ticket khi callback pending và unknown/partial. Demo gắn nhãn giả lập, không nối app router hoặc provider/API production.
