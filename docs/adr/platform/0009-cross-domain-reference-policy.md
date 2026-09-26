# Reference xuyên ranh giới

Status: baseline theo thiết kế nguồn; implementation theo từng phase.

Nguồn: [01_SYSTEM_ERD_COMPLETE.md](../../../docx/01_SYSTEM_ERD_COMPLETE.md).

## Quyết định

Vinhomes chỉ hard FK tới shared tenant/user identity; agent/runtime dùng provenance snapshot và stable references.

## Hệ quả cho code

Domain vẫn chạy khi AI không khả dụng; không join bắt buộc business state với agent_run/workflow_session.

