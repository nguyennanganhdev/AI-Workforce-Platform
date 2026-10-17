# Async evaluation — Contract, grading và SQL runtime integration

`test_phase_a.py` kiểm schema Draft 2020-12, tính nhất quán artifact và
shared DTO, mẫu hợp lệ và mẫu vi phạm các trường bắt buộc.

`test_phase_b.py` kiểm validation/frozen input và grader với fake runner.
`test_phase_c.py` dùng canonical UOW/jobs C1, Registry SQL C2, Workflow SQL C4
và real Execution approval/policy/gateway. `runtime_fixture.py` chỉ nằm trong
tests: scripted model/provider/catalog/quote/HITL là test dependencies, không
được import vào production.

```bash
PYTHONPATH=src:tests/workforce/fixtures .venv/bin/python -m pytest tests/workforce/lifecycle/async_evaluation --import-mode=importlib -q
```

SQLite/SQL reload và injected cancellation không chứng minh PostgreSQL
concurrency, process kill/restart hoặc production Leader session. Chi tiết tại
`docs/workforce/handoffs/pho-tien-anh/PHASE_C_C5.md`.
