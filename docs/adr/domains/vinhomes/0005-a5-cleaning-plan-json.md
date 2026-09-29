# A5 dùng versioned CleaningPlan JSON

Status: baseline theo thiết kế nguồn; implementation theo từng phase.

Nguồn: [Database P0](../../../erd/01_DATABASE_ERD_IMPLEMENTATION_COMPLETE.md).

## Quyết định

A5 là Vinhomes workflow; CleaningPlan có version lưu trong Task.domain_data cho POC.

## Hệ quả cho code

Không tạo Agent A5, microservice A5 hoặc bảng cleaning_plan riêng ở phase này.

