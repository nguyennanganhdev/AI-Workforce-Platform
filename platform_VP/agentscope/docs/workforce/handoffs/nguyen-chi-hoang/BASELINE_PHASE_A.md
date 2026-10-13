# Baseline Phase A — Nguyễn Chí Hoàng

Ngày kiểm tra: 2026-10-10.

## Mốc mã nguồn

- Repository: `platform_VP/agentscope`.
- Branch đang làm việc: `dev_TeamHoang`.
- Commit gốc đã kiểm tra: `7d7ec2cfcaacc91da80e2f2dde97885ac0ce5fce`.
- Alembic head trước khi thêm Workforce persistence: `0008_area_platform`.
- Phase A này không tạo migration, không sửa bảng hiện hữu và không commit/reset thay đổi của người dùng.

## Môi trường đã kiểm tra

- Python: `3.11.15` tại `.venv/Scripts/python.exe`.
- Pydantic: `2.14.0`.
- `alembic.exe` có sẵn và đọc được migration head.
- `pytest` chưa được cài trong `.venv` (`No module named pytest`) dù nằm trong nhóm dependency `dev` của `pyproject.toml`.
- Lệnh `pnpm` chưa có trên `PATH`; `node_modules` frontend và `tsc.cmd` cục bộ vẫn có sẵn để type-check contract.
- Bộ test contract dùng `unittest` chuẩn để chạy ngay, đồng thời vẫn có thể được pytest collect sau khi cài dev dependencies.

## Phạm vi baseline đã khóa

- Một role tương tác duy nhất: `AREA_MANAGER`.
- Owner scope bắt buộc đủ `(tenant_id, domain_id, area_id, manager_account_id)`.
- Credential máy tách purpose `customer_api` và `provider_events`; đây không phải role mới.
- Client không được gửi `group_id`, scope nội bộ hoặc internal ticket/conversation để điều khiển routing.
- Một external user có thể có nhiều ticket/hộp chat, nhưng mỗi cặp ticket/conversation bind riêng tới workflow/conversation/group.
- Build một agent hay nhiều agent đều tạo agent độc lập; group chỉ hình thành khi có request runtime.

## Lệnh xác minh

```powershell
.\.venv\Scripts\alembic.exe -c src\agentscope\app\storage\_sql\_alembic\alembic.ini heads
.\.venv\Scripts\python.exe -m unittest tests.workforce.foundation.test_contracts -v
.\.venv\Scripts\python.exe scripts\workforce\export_contracts.py
& '.\examples\web_ui\frontend\node_modules\.bin\tsc.cmd' --noEmit --skipLibCheck --target ES2022 --module ESNext 'examples/web_ui/frontend/src/features/workforce/shared/contracts/workforce-v1.ts'
git diff --check
```
