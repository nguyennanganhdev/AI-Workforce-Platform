# Database ownership

Owner hạ tầng: **Data/DevOps**. Owner schema: **Platform / Vinhomes**.
PostgreSQL là source of truth. Schema workforce đã bổ sung 152 bảng bên cạnh 38 bảng
OpenBot. Identity dùng lại users.id text; prefix vật lý platform_* / vh_* trong public.
Thiết kế logic bên dưới được ánh xạ theo module, không chuyển bảng shell sang schema mới.

| Thư mục | File sẽ thêm theo feature | Logical schemas |
|---|---|---|
| `schema/platform` | identity, domains, agents, capabilities, evaluation, runtime, memory, audit | `platform_identity`, `platform_domain`, `platform_agent`, `platform_capability`, `platform_evaluation`, `platform_runtime`, `platform_memory`, `platform_audit` |
| `schema/domains/vinhomes` | property, intake, operations, evidence, services | `vh_property`, `vh_intake`, `vh_operations`, `vh_content`, `vh_services` |

Các module thực tế chi tiết hơn bảng tổng quan; xem [ERD và catalog](../../../docs/erd/README.md).
Common columns/JSONB nằm ở schema/columns.ts. Schema mới phải thêm vào drizzle.config.ts,
barrel export và exporter ERD. Chạy `bun run --filter server db:erd` sau khi đổi schema.
Domain schema chỉ được FK tới tenant/user identity ở platform. Không FK tới agent/runtime tables.
Cross-tenant FK/RLS, version, immutable history, booking/payment và governance có
PostgreSQL integration tests trong server/tests/workforce-database.integration.test.ts.

Upstream đang dùng `server/drizzle/` và Drizzle migration runner. Các thư mục
`migrations/platform` và `migrations/domains/vinhomes` hiện chỉ là khung ownership, chưa được runner đọc.
Runner duy nhất là server/scripts/migrate.ts: 0046 tạo bảng/policies; 0047 cài
trigger/exclusion/FORCE RLS; 0048/0049 bổ sung coordination/field; 0050 thêm queue indexes.
Không chạy hai runner độc lập ghi schema chung.
Xem [runbook](../../../docs/erd/MIGRATION_RUNBOOK.md) cho migration, runtime role và tenant context.
