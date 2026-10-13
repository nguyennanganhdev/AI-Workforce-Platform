# Lifecycle — Tests Phase A/B/C5

Chủ sở hữu: Phó Tiến Anh.

Phase A kiểm tra schema artifact, DTO shared và scope bốn trường. Phase B
kiểm tra validation, grading và release gates. C5 kiểm tra SQL persistence,
durable jobs và evidence từ Workflow/Execution với model/provider giả lập.
Xem [chi tiết và giới hạn kiểm chứng](async_evaluation/README.md).

Từ thư mục `platform_VP/agentscope`:

```bash
PYTHONPATH=src:tests/workforce/fixtures:tests/workforce/registry/event_protocols:tests/workforce/orchestration/async_workflows .venv/bin/python -m pytest tests/workforce/lifecycle --import-mode=importlib -q
```

Full-platform E2E, production composition và retention Phase D cần kiểm chứng
ở các mốc tiếp theo; kết quả C5 không thay thế các kiểm chứng đó.
