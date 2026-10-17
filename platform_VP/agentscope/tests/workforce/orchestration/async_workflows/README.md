# async_workflows — PHH Phase B tests

Owner: **Phan Huy Hoàng**. Fake ports chỉ dùng cho test, không được import vào production.

Suite kiểm tra binding hai ticket A/B, idempotency, reply CAS, continuation/checkpoint, response-only, external tracking, HITL, invalid decision rollback, close race, public event after-commit, cursor/audience isolation và SSE replay.

```powershell
$env:PYTHONPATH=(Resolve-Path src)
.\.venv\Scripts\python.exe -m unittest discover -s tests\workforce\orchestration\async_workflows -p "test_*.py" -v
```
