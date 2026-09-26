# WorkOrder, redo và QC

Status: baseline theo thiết kế nguồn; implementation theo từng phase.

Nguồn: [02_VINHOMES_DOMAIN_ERD.md](../../../../docx/02_VINHOMES_DOMAIN_ERD.md).

## Quyết định

WorkOrder lưu lần thực thi; redo liên kết bản gốc, không ghi đè evidence/QC cũ.

## Hệ quả cho code

QC fail tạo xử lý lại; Incident resolved/closed theo business rule và xác nhận cư dân.

