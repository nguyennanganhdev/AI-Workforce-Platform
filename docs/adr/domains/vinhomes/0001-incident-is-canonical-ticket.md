# Incident là canonical Ticket

Status: baseline theo thiết kế nguồn; implementation theo từng phase.

Nguồn: [02_VINHOMES_DOMAIN_ERD.md](../../../../docx/02_VINHOMES_DOMAIN_ERD.md).

## Quyết định

Chỉ một aggregate vh_incident; Ticket là nhãn UI.

## Hệ quả cho code

Incident status NEW/OPEN/RESOLVED/CLOSED; WAITING_APPROVAL không phải status Incident.

