# Approval thuộc domain action

Status: baseline theo thiết kế nguồn; implementation theo từng phase.

Nguồn: [Database P0](../../../erd/01_DATABASE_ERD_IMPLEMENTATION_COMPLETE.md).

## Quyết định

ActionRequest → RuleDecision → Approval nếu cần → Execution Grant.

## Hệ quả cho code

Approval có expiry/scope; một Task chờ approval không chặn toàn Incident.

