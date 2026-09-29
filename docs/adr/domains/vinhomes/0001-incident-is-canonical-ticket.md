# Incident là canonical Ticket

Status: baseline theo thiết kế nguồn; implementation theo từng phase.

Nguồn: [Database P0](../../../erd/01_DATABASE_ERD_IMPLEMENTATION_COMPLETE.md).

## Quyết định

Chỉ một aggregate vh_incident; Ticket là nhãn UI.

## Hệ quả cho code

Incident status NEW/OPEN/RESOLVED/CLOSED; WAITING_APPROVAL không phải status Incident.

