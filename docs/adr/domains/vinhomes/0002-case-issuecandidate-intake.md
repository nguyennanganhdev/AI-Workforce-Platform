# Intake tách khỏi Incident

Status: baseline theo thiết kế nguồn; implementation theo từng phase.

Nguồn: [Database P0](../../../erd/01_DATABASE_ERD_IMPLEMENTATION_COMPLETE.md).

## Quyết định

Case và IssueCandidate là pre-incident; ResidentReport là báo cáo chính thức, nhiều report có thể cùng Incident.

## Hệ quả cho code

AI proposal phải được domain validate trước khi lưu/materialize.

