# Intake tách khỏi Incident

Status: baseline theo thiết kế nguồn; implementation theo từng phase.

Nguồn: [02_VINHOMES_DOMAIN_ERD.md](../../../../docx/02_VINHOMES_DOMAIN_ERD.md).

## Quyết định

Case và IssueCandidate là pre-incident; ResidentReport là báo cáo chính thức, nhiều report có thể cùng Incident.

## Hệ quả cho code

AI proposal phải được domain validate trước khi lưu/materialize.

