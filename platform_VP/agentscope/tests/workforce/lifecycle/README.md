# Lifecycle — Contract tests Phase A

Chủ sở hữu: Phó Tiến Anh.

Kiểm tra schema artifact, DTO shared, scope bốn trường và mẫu dữ liệu
validation/evaluation/policy trong `async_evaluation/test_phase_a.py`.

Từ thư mục `platform_VP/agentscope`:

```bash
PYTHONPATH=src .venv/bin/python -m pytest tests/workforce/lifecycle -q
```

Các kiểm thử hành vi validation, runner, publish và retention thuộc mốc triển khai tiếp theo.
