# Database ownership

Một sản phẩm phát triển từ OpenBot; 186 bảng, cùng public schema và ledger. Nền identity/channel/agent dùng chung; platform_* mở rộng quản trị/runtime; vh_* giữ nghiệp vụ Vinhomes.

| Nơi sửa | Trách nhiệm |
|---|---|
| schema/core.ts, coworker.ts, plugins.ts | User/auth, agent/channel, credential/tool/skill nền |
| schema/tenant.ts, tenant-scope.ts, platform/identity.ts | Tenant root và policy, membership/role |
| schema/platform | Version, evaluation, deployment, workflow, transcript, knowledge/memory |
| schema/domains/vinhomes | Property, intake, operations, hiện trường và dịch vụ |
| schema/columns.ts, json.ts | Kiểu/cột chung, JSONB tương thích driver |

Tenant root không import core; identity membership dùng users từ core. FK callback cho phép core tham chiếu membership mà không tạo registry mới. Domain chỉ FK sang shared identity, không FK sang runtime.

Nguồn đọc chính: [business map](../../../docs/erd/02_BUSINESS_ANALYSIS_IMPLEMENTATION.md), [catalog](../../../docs/erd/physical/TABLE_CATALOG.md), [thiết kế](../../../docs/erd/01_DATABASE_ERD_IMPLEMENTATION_COMPLETE.md).

Schema mới phải có trong drizzle.config.ts, barrel và exporter. `bun run --cwd server db:erd` sinh tài liệu. meta chỉ có JSON; hướng dẫn đặt ở [drizzle/README](../../drizzle/README.md).

Một ledger duy nhất; CLI dev và server/scripts/migrate.ts dùng cùng ledger. Không dùng thư mục migrations/platform hoặc migrations/domains làm runner thứ hai. SQL 0051 hợp nhất schema; 0052 bổ sung integrity. **Tenant context và chat/runtime integration chưa hoàn tất**, xem [runbook](../../../docs/erd/MIGRATION_RUNBOOK.md) trước khi migrate ứng dụng.
