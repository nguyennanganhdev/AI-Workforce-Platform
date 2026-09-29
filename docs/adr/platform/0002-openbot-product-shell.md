# OpenBot là nền mã nguồn của sản phẩm

Status: updated by [ADR 0013](0013-unified-openbot-database.md).

OpenBot đã được nhập vào repo. Sản phẩm sửa và phát triển trực tiếp từ nền này, dùng một registry agent/channel/tool/skill và một hệ thống identity. Các module Platform/Vinhomes là ranh giới trong cùng sản phẩm.

Nghiệp vụ Vinhomes có service và bảng riêng theo trách nhiệm. Runtime framework qua adapter, không sở hữu Incident/Task. Không duy trì hai platform rồi đồng bộ registry.

[Database hiện hành](../../erd/01_DATABASE_ERD_IMPLEMENTATION_COMPLETE.md) và [điều kiện tích hợp](../../erd/MIGRATION_RUNBOOK.md) thay thế các giả định trong tài liệu nhập nguồn ban đầu.
