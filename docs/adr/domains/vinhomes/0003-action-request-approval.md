# Approval thuộc domain action

Status: baseline theo thiết kế nguồn; implementation theo từng phase.

Nguồn: [02_VINHOMES_DOMAIN_ERD.md](../../../../docx/02_VINHOMES_DOMAIN_ERD.md).

## Quyết định

ActionRequest → RuleDecision → Approval nếu cần → Execution Grant.

## Hệ quả cho code

Approval có expiry/scope; một Task chờ approval không chặn toàn Incident.

