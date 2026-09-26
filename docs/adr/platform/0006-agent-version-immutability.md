# AgentVersion bất biến

Status: baseline theo thiết kế nguồn; implementation theo từng phase.

Nguồn: [03_PLATFORM_ERD.md](../../../docx/03_PLATFORM_ERD.md).

## Quyết định

AgentVersion/spec snapshot bất biến khi vào formal evaluation/publish lifecycle.

## Hệ quả cho code

Thay specification tạo version mới; deployment pin version đã publish. Lifecycle status vẫn có thể suspend/retire theo policy.

