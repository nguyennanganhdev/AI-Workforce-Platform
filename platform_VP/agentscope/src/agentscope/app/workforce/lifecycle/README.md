# Lifecycle — validation, evaluation và release

Chủ sở hữu: Phó Tiến Anh.

Phạm vi: đặc tả validation và evaluation snapshot theo mục 17.9 của
[kế hoạch triển khai](../../../../../docs/workforce/KE_HOACH_TRIEN_KHAI.md).

`ValidationReport` và `EvaluationRecord` là aggregate đề xuất của Lifecycle,
nhập DTO shared từ `workforce/contracts`. Export JSON Schema nằm trong
[async_evaluation/](async_evaluation/README.md).

[Hồ sơ bàn giao](../../../../../docs/workforce/handoffs/pho-tien-anh/README.md)
gồm baseline, schema, mẫu dữ liệu và kết quả contract tests.

Phase B/C5 nối validation/grading với SQL runtime evidence và durable jobs tại
[async_evaluation/](async_evaluation/README.md). D4 thêm atomic publish,
immutable version, rollback, catalog/availability và pin authorization tại
[releases/](releases/README.md), cùng regression long-wait/restart.
Migration/composition do Foundation ghép theo bàn giao; không có runtime
create_all hoặc test double trong production.
