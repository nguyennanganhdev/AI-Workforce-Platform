# D4 regression checks

Tái dùng `SqlCaseDriver` C5, `D3CaseDriver`, `SqlTicketSliceSupport`, Foundation
SQL UOW, Registry current/exact protocol, PHH continuation/checkpoint/guard và
Execution approval/gateway/provider inbox. Scripted Leader/MCP, tool/policy
catalog và usage adapter chỉ nằm trong tests. Không import test code vào production.

```bash
PYTHONPATH=src:tests/workforce/fixtures .venv/bin/python -m pytest tests/workforce/lifecycle/releases --import-mode=importlib -q -rs
```

`test_phase_d.py`: atomic selections, explicit publish, current dependency/
policy/runtime/suite/context, stale draft/eval, cancellation/evidence integrity,
CAS/concurrent retry/edit/cancel, crash trước commit và mất response sau commit,
scope, archive/disable/rollback, schema/DDL.

`test_long_wait.py`: raw signed Provider Event HTTP + SQL, clock tiến 200 ngày,
publish v2/rollback/archive, revise/disable protocol, pool reconnect/worker mới,
resume bằng exact v1 pin, idle/duplicate không tăng calls, disable sau enqueue,
revoke giữ fact nhưng không public message/wakeup, forged full protocol ref.
Clock advance/pool reconnect không phải chờ thật 200 ngày hoặc kill process.

`test_postgres.py`: bốn gates dùng `WORKFORCE_TEST_POSTGRES_URL` test riêng;
schema ngẫu nhiên được cleanup chính xác. Không có DSN thì skip rõ. SQLite
kiểm tra serialization của writer; không thay bằng chứng PostgreSQL row lock.
