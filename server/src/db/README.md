# Database ownership

Owner hạ tầng: **Data/DevOps**. Owner schema: **Platform / Vinhomes**.
PostgreSQL là source of truth. Chưa chọn ORM hoặc tạo migration/table chạy thật.

| Thư mục | File sẽ thêm theo feature | Logical schemas |
|---|---|---|
| `schema/platform` | identity, domains, agents, capabilities, evaluation, runtime, memory, audit | `platform_identity`, `platform_domain`, `platform_agent`, `platform_capability`, `platform_evaluation`, `platform_runtime`, `platform_memory`, `platform_audit` |
| `schema/domains/vinhomes` | property, intake, operations, evidence, services | `vh_property`, `vh_intake`, `vh_operations`, `vh_content`, `vh_services` |

Các tên file trên có đuôi `.ts`; tạo schema thật khi chọn ORM theo OpenBot upstream.
Domain schema chỉ được FK tới tenant/user identity ở platform. Không FK tới agent/runtime tables.
Cross-tenant constraint, transaction/outbox và optimistic version cần kiểm tra ở database test khi triển khai.

`migrations/platform` và `migrations/domains/vinhomes` tách ownership; migration runner duy nhất
phải sắp thứ tự identity → domain và giữ một migration ledger. Không chạy hai runner độc lập
cùng ghi schema dùng chung. Snapshot ERD tham chiếu ở `docs/erd/README.md`.
