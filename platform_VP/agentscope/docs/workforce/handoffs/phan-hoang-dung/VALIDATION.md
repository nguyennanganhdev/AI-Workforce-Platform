# Kiểm chứng Execution — Phan Hoàng Dũng

Ngày 10/10/2026; baseline `6bc7d60`, branch `feat/wf-execution`. Đây là kiểm chứng module độc lập và regression SDK, chưa nghiệm thu toàn platform. Phạm vi và đầu ra còn thiếu: [STATUS.md](STATUS.md).

## Kết quả đã chạy

| Kiểm tra | Kết quả | Giới hạn |
|---|---|---|
| Suite riêng Execution + E2E slice | **48 passed, 4 skipped**, 6.09 giây | SQLite, fake ports và mock provider; có MCP stdio thực qua SDK |
| Suite trên cùng regression Toolkit/Permission/MCP headers | **128 passed, 50 skipped, 11 subtests passed**, 10.60 giây | 4 skip thuộc lane Dũng, 46 skip thuộc suite SDK hiện có; không coi skip là pass |
| Ruff E/F, line length 79 | All checks passed | Chỉ source/test trong lane |
| mypy | Success, 23 source files | Kiểm tra typed definitions; các port còn dùng `Any` chờ DTO/Protocol chung |
| ESLint feature approvals | Exit 0 | Bao gồm demo và external operation component |
| TypeScript `tsc -b` | Exit 0 | Frontend project |
| Frontend production build | Exit 0 | Có cảnh báo Vite về `mime-types`/`path` browser externalization và chunk lớn; không sửa ngoài lane |
| Browser UI smoke | **Chưa chạy** | Browser inventory trả `apps=[]`, `browsers=[]`; Vite đã khởi chạy và dừng |
| PostgreSQL races, full-platform E2E, provider sandbox | **Chưa chạy** | Chưa đủ môi trường/implementation/credential được bàn giao |

Lần suite riêng cuối thực hiện sau các cập nhật cuối của source/tests. Regression rộng chạy sau các thay đổi logic cuối; sau đó chỉ chỉnh style, tên test và tài liệu. Không gọi model trả phí, không booking thật, không gửi event sang backend đối tác thật.

## Chạy lại

Working directory: `platform_VP/agentscope`. Python 3.11; môi trường tạm `%TEMP%\wf-execution-venv` đã cài project với extras `service,storage-sql`, `pytest`, `aiosqlite`, `asyncpg`. Do editable install gặp encoding đường dẫn Windows, dùng wheel dependencies và `PYTHONPATH=src` để kiểm tra source checkout.

```powershell
$env:PYTHONIOENCODING = 'utf-8'
$env:PYTHONPATH = (Join-Path (Get-Location) 'src')
& "$env:TEMP\wf-execution-venv\Scripts\python.exe" -m pytest tests/workforce/execution tests/workforce/e2e -q -rs -p no:cacheprovider --basetemp "$env:TEMP\wf-execution-pytest-final-owned"

& "$env:TEMP\wf-execution-venv\Scripts\python.exe" -m pytest tests/workforce/execution tests/workforce/e2e tests/toolkit_test.py tests/permission_engine_test.py tests/permission_mode_test.py tests/mcp_runtime_headers_test.py -q -p no:cacheprovider --basetemp "$env:TEMP\wf-execution-pytest-release"

python -m ruff check src/agentscope/app/workforce/execution tests/workforce/execution tests/workforce/e2e tests/workforce/fixtures --select E,F --line-length 79
python -m mypy src/agentscope/app/workforce/execution --follow-imports=skip --ignore-missing-imports --disallow-untyped-defs --disallow-incomplete-defs
pnpm.cmd --dir examples/web_ui/frontend exec eslint src/features/workforce/approvals
pnpm.cmd --dir examples/web_ui/frontend exec tsc -b
pnpm.cmd --dir examples/web_ui/frontend build
```

Ruff/mypy dùng Python tooling có sẵn của workspace. Dependencies frontend được cài theo frozen lockfile, ignore scripts; không đổi package manifest/lockfile. Trên Windows sandbox này, mock MCP stdio cần subprocess/named pipe và Vite build cần native subprocess; đã chạy ngoài sandbox sau khi được cấp quyền.

## Bốn test còn gate

1. `test_postgres_parallel_consent_execution_and_inbox_apply_once`: cần `WORKFORCE_TEST_POSTGRES_URL` là dedicated test DSN. Test tạo schema UUID riêng và chỉ drop schema do chính test tạo. Docker CLI có nhưng daemon không chạy trong phiên này. SQLite không chứng minh row locks, race hoặc commit order trên PostgreSQL.
2. `test_case_79_read_only_auto_close_without_tracking`.
3. `test_cases_80_84_85_86_ticket_context_and_mismatch`.
4. `test_case_87_parallel_start_has_one_binding_and_group`.

Ba test cuối cần `WORKFORCE_E2E_FACTORY=module:function` từ composition thật: app, DB, worker, auth/mapping và Registry/Builder/Lifecycle/Orchestration. Chi tiết interface và coverage cases 56–88 ở [PHD-11](INTEGRATION_REQUEST_PHD-11.md). Không tạo Customer API hoặc runtime giả để làm các test này pass.

## Bằng chứng và phần chưa xác minh

Đã kiểm tra guard/effect/pins, calculator integer, quote/TTL/audience/decider, approval consume, intent trước network, lỗi sau provider write thành unknown, sync reconciliation không recreate, early event/correlation, durable inbox ACK, dedupe/conflict, stale query CAS, delta ordering/quarantine, atomic Workflow sink rollback, closed/revoked fact persistence và hai group/ticket tách state. Có kiểm tra `.call`, `__call__` và assembly Toolkit bằng SDK thực; HTTP tests dùng ASGI app và SQL repository thực của module.

Tests với fake Workflow/Job/Auth/Registry ports chỉ chứng minh hợp đồng và atomicity trong cùng session fixture. Chưa chứng minh worker lease fencing, production auth/signature/rate limits, migrations của Foundation, SSE server replay/live/retention, checkpoint-close race, dynamic agent selection, batch build/publish hoặc recovery toàn hệ thống. Những phần này cần owner bàn giao trước khi nghiệm thu PHD-11/12/13/17 toàn chuỗi.

Demo UI riêng: chạy Vite và mở `/src/features/workforce/approvals/demo/index.html`. Cần browser để kiểm tra loading, lỗi gửi, expiry, double click, đổi ticket khi callback pending và unknown/partial. Demo gắn nhãn giả lập, không nối app router hoặc provider/API production.
