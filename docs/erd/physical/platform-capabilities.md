# platform-capabilities

Generated from Drizzle. External entities in the diagram are foreign-key targets owned by another module.

```mermaid
erDiagram
  platform_capability {
    uuid id PK
    uuid tenant_id FK
    text code
    text name
    text type
    text description
    text risk_level
    text owner_id FK
    text status
    timestamp_with_time_zone created_at
    bigint version
    timestamp_with_time_zone updated_at
  }
  platform_tenant ||--o{ platform_capability : "ownership"
  users ||--o{ platform_capability : "owner_id"
  platform_mcp_server {
    uuid id PK
    uuid tenant_id FK
    text name
    text endpoint_ref
    text owner_id FK
    text status
    timestamp_with_time_zone created_at
    bigint version
    timestamp_with_time_zone updated_at
  }
  platform_tenant ||--o{ platform_mcp_server : "ownership"
  users ||--o{ platform_mcp_server : "owner_id"
  platform_mcp_server_version {
    uuid id PK
    uuid tenant_id FK
    uuid mcp_server_id FK
    integer version_no
    text schema_hash
    text fingerprint
    text security_status
    timestamp_with_time_zone created_at
    bigint version
    timestamp_with_time_zone updated_at
  }
  platform_tenant ||--o{ platform_mcp_server_version : "ownership"
  platform_mcp_server ||--o{ platform_mcp_server_version : "mcp_server_id"
  platform_model_profile {
    uuid id PK
    uuid tenant_id FK
    text code
    text provider_ref
    text model_ref
    jsonb config_json
    text status
    timestamp_with_time_zone created_at
    bigint version
    timestamp_with_time_zone updated_at
  }
  platform_tenant ||--o{ platform_model_profile : "ownership"
  platform_skill {
    uuid id PK
    uuid tenant_id FK
    text name
    text owner_id FK
    text status
    timestamp_with_time_zone created_at
    bigint version
    timestamp_with_time_zone updated_at
  }
  platform_tenant ||--o{ platform_skill : "ownership"
  users ||--o{ platform_skill : "owner_id"
  platform_skill_version {
    uuid id PK
    uuid tenant_id FK
    uuid skill_id FK
    integer version_no
    text content_ref
    text checksum
    timestamp_with_time_zone created_at
  }
  platform_tenant ||--o{ platform_skill_version : "ownership"
  platform_skill ||--o{ platform_skill_version : "skill_id"
  platform_tool {
    uuid id PK
    uuid tenant_id FK
    text code
    text name
    text effect_type
    text risk_level
    timestamp_with_time_zone created_at
    bigint version
    timestamp_with_time_zone updated_at
  }
  platform_tenant ||--o{ platform_tool : "ownership"
  platform_tool_version {
    uuid id PK
    uuid tenant_id FK
    uuid tool_id FK
    uuid mcp_server_version_id FK
    integer version_no
    jsonb input_schema
    jsonb output_schema
    text fingerprint
    text status
    timestamp_with_time_zone created_at
    bigint version
    timestamp_with_time_zone updated_at
  }
  platform_tenant ||--o{ platform_tool_version : "ownership"
  platform_tool ||--o{ platform_tool_version : "tool_id"
  platform_mcp_server_version |o--o{ platform_tool_version : "mcp_server_version_id"
```

## platform_capability

Danh mục năng lực được quản trị trong tenant, kèm loại và mức rủi ro.

Tenant RLS: **enabled + forced by integrity migrations 0047/0049**.

| Column | PostgreSQL type | Required | Default | Declared values |
|---|---|---|---|---|
| `id` | `uuid` | yes | `gen_random_uuid()` | — |
| `tenant_id` | `uuid` | yes | `—` | — |
| `code` | `text` | yes | `—` | — |
| `name` | `text` | yes | `—` | — |
| `type` | `text` | yes | `—` | — |
| `description` | `text` | no | `—` | — |
| `risk_level` | `text` | yes | `—` | `LOW`, `MEDIUM`, `HIGH`, `CRITICAL` |
| `owner_id` | `text` | yes | `—` | — |
| `status` | `text` | yes | `—` | `ACTIVE`, `SUSPENDED`, `RETIRED` |
| `created_at` | `timestamp with time zone` | yes | `now()` | — |
| `version` | `bigint` | yes | `1` | — |
| `updated_at` | `timestamp with time zone` | yes | `now()` | — |

Primary key: `id`.

Unique keys:

- `platform_capability_uq_0`: (`tenant_id`, `code`).
- `platform_capability_uq_1`: (`tenant_id`, `id`).

Foreign keys:

- (`tenant_id`) → `platform_tenant` (`id`); ON DELETE `restrict`.
- (`owner_id`) → `users` (`id`); ON DELETE `restrict`.

Indexes:

- `platform_capability_ix_0`: (`owner_id`).

Checks:

- `platform_capability_risk_level_ck`: `"platform_capability"."risk_level" in ('LOW', 'MEDIUM', 'HIGH', 'CRITICAL')`.
- `platform_capability_status_ck`: `"platform_capability"."status" in ('ACTIVE', 'SUSPENDED', 'RETIRED')`.
- `platform_capability_ck_0`: `version > 0`.

Additional cross-row/temporal rules: [integrity matrix](../DATABASE_DESIGN.md#integrity-matrix) and [coordination review](../COMPLETENESS_REVIEW.md).

## platform_mcp_server

Danh tính MCP endpoint được quản trị bởi tenant, tách khỏi phiên bản schema tool.

Tenant RLS: **enabled + forced by integrity migrations 0047/0049**.

| Column | PostgreSQL type | Required | Default | Declared values |
|---|---|---|---|---|
| `id` | `uuid` | yes | `gen_random_uuid()` | — |
| `tenant_id` | `uuid` | yes | `—` | — |
| `name` | `text` | yes | `—` | — |
| `endpoint_ref` | `text` | yes | `—` | — |
| `owner_id` | `text` | yes | `—` | — |
| `status` | `text` | yes | `—` | `ACTIVE`, `SUSPENDED`, `RETIRED` |
| `created_at` | `timestamp with time zone` | yes | `now()` | — |
| `version` | `bigint` | yes | `1` | — |
| `updated_at` | `timestamp with time zone` | yes | `now()` | — |

Primary key: `id`.

Unique keys:

- `platform_mcp_server_uq_0`: (`tenant_id`, `id`).

Foreign keys:

- (`tenant_id`) → `platform_tenant` (`id`); ON DELETE `restrict`.
- (`owner_id`) → `users` (`id`); ON DELETE `restrict`.

Indexes:

- `platform_mcp_server_ix_0`: (`owner_id`).

Checks:

- `platform_mcp_server_status_ck`: `"platform_mcp_server"."status" in ('ACTIVE', 'SUSPENDED', 'RETIRED')`.
- `platform_mcp_server_ck_0`: `version > 0`.

Additional cross-row/temporal rules: [integrity matrix](../DATABASE_DESIGN.md#integrity-matrix) and [coordination review](../COMPLETENESS_REVIEW.md).

## platform_mcp_server_version

Snapshot schema/fingerprint của MCP server và trạng thái kiểm duyệt bảo mật.

Tenant RLS: **enabled + forced by integrity migrations 0047/0049**.

| Column | PostgreSQL type | Required | Default | Declared values |
|---|---|---|---|---|
| `id` | `uuid` | yes | `gen_random_uuid()` | — |
| `tenant_id` | `uuid` | yes | `—` | — |
| `mcp_server_id` | `uuid` | yes | `—` | — |
| `version_no` | `integer` | yes | `—` | — |
| `schema_hash` | `text` | yes | `—` | — |
| `fingerprint` | `text` | yes | `—` | — |
| `security_status` | `text` | yes | `—` | `PENDING`, `APPROVED`, `REJECTED`, `REVOKED` |
| `created_at` | `timestamp with time zone` | yes | `now()` | — |
| `version` | `bigint` | yes | `1` | — |
| `updated_at` | `timestamp with time zone` | yes | `now()` | — |

Primary key: `id`.

Unique keys:

- `platform_mcp_server_version_uq_0`: (`tenant_id`, `mcp_server_id`, `version_no`).
- `platform_mcp_server_version_uq_1`: (`tenant_id`, `id`).

Foreign keys:

- (`tenant_id`) → `platform_tenant` (`id`); ON DELETE `restrict`.
- (`tenant_id`, `mcp_server_id`) → `platform_mcp_server` (`tenant_id`, `id`); ON DELETE `restrict`.

Indexes:

- `platform_mcp_server_version_ix_0`: (`tenant_id`, `mcp_server_id`).

Checks:

- `platform_mcp_server_version_security_status_ck`: `"platform_mcp_server_version"."security_status" in ('PENDING', 'APPROVED', 'REJECTED', 'REVOKED')`.
- `platform_mcp_server_version_ck_0`: `version_no > 0`.
- `platform_mcp_server_version_ck_1`: `version > 0`.

Additional cross-row/temporal rules: [integrity matrix](../DATABASE_DESIGN.md#integrity-matrix) and [coordination review](../COMPLETENESS_REVIEW.md).

## platform_model_profile

Cấu hình model/provider được phép dùng, không chứa API key.

Tenant RLS: **enabled + forced by integrity migrations 0047/0049**.

| Column | PostgreSQL type | Required | Default | Declared values |
|---|---|---|---|---|
| `id` | `uuid` | yes | `gen_random_uuid()` | — |
| `tenant_id` | `uuid` | yes | `—` | — |
| `code` | `text` | yes | `—` | — |
| `provider_ref` | `text` | yes | `—` | — |
| `model_ref` | `text` | yes | `—` | — |
| `config_json` | `jsonb` | yes | `—` | — |
| `status` | `text` | yes | `—` | `ACTIVE`, `SUSPENDED`, `RETIRED` |
| `created_at` | `timestamp with time zone` | yes | `now()` | — |
| `version` | `bigint` | yes | `1` | — |
| `updated_at` | `timestamp with time zone` | yes | `now()` | — |

Primary key: `id`.

Unique keys:

- `platform_model_profile_uq_0`: (`tenant_id`, `code`).
- `platform_model_profile_uq_1`: (`tenant_id`, `id`).

Foreign keys:

- (`tenant_id`) → `platform_tenant` (`id`); ON DELETE `restrict`.

Checks:

- `platform_model_profile_status_ck`: `"platform_model_profile"."status" in ('ACTIVE', 'SUSPENDED', 'RETIRED')`.
- `platform_model_profile_ck_0`: `version > 0`.

Additional cross-row/temporal rules: [integrity matrix](../DATABASE_DESIGN.md#integrity-matrix) and [coordination review](../COMPLETENESS_REVIEW.md).

## platform_skill

Danh tính skill được quản lý bởi tenant/chủ sở hữu.

Tenant RLS: **enabled + forced by integrity migrations 0047/0049**.

| Column | PostgreSQL type | Required | Default | Declared values |
|---|---|---|---|---|
| `id` | `uuid` | yes | `gen_random_uuid()` | — |
| `tenant_id` | `uuid` | yes | `—` | — |
| `name` | `text` | yes | `—` | — |
| `owner_id` | `text` | yes | `—` | — |
| `status` | `text` | yes | `—` | `ACTIVE`, `SUSPENDED`, `RETIRED` |
| `created_at` | `timestamp with time zone` | yes | `now()` | — |
| `version` | `bigint` | yes | `1` | — |
| `updated_at` | `timestamp with time zone` | yes | `now()` | — |

Primary key: `id`.

Unique keys:

- `platform_skill_uq_0`: (`tenant_id`, `id`).

Foreign keys:

- (`tenant_id`) → `platform_tenant` (`id`); ON DELETE `restrict`.
- (`owner_id`) → `users` (`id`); ON DELETE `restrict`.

Indexes:

- `platform_skill_ix_0`: (`owner_id`).

Checks:

- `platform_skill_status_ck`: `"platform_skill"."status" in ('ACTIVE', 'SUSPENDED', 'RETIRED')`.
- `platform_skill_ck_0`: `version > 0`.

Additional cross-row/temporal rules: [integrity matrix](../DATABASE_DESIGN.md#integrity-matrix) and [coordination review](../COMPLETENESS_REVIEW.md).

## platform_skill_version

Nội dung skill bất biến qua content reference và checksum.

Tenant RLS: **enabled + forced by integrity migrations 0047/0049**.

| Column | PostgreSQL type | Required | Default | Declared values |
|---|---|---|---|---|
| `id` | `uuid` | yes | `gen_random_uuid()` | — |
| `tenant_id` | `uuid` | yes | `—` | — |
| `skill_id` | `uuid` | yes | `—` | — |
| `version_no` | `integer` | yes | `—` | — |
| `content_ref` | `text` | yes | `—` | — |
| `checksum` | `text` | yes | `—` | — |
| `created_at` | `timestamp with time zone` | yes | `now()` | — |

Primary key: `id`.

Unique keys:

- `platform_skill_version_uq_0`: (`tenant_id`, `skill_id`, `version_no`).
- `platform_skill_version_uq_1`: (`tenant_id`, `id`).

Foreign keys:

- (`tenant_id`) → `platform_tenant` (`id`); ON DELETE `restrict`.
- (`tenant_id`, `skill_id`) → `platform_skill` (`tenant_id`, `id`); ON DELETE `restrict`.

Indexes:

- `platform_skill_version_ix_0`: (`tenant_id`, `skill_id`).

Checks:

- `platform_skill_version_ck_0`: `version_no > 0`.

Additional cross-row/temporal rules: [integrity matrix](../DATABASE_DESIGN.md#integrity-matrix) and [coordination review](../COMPLETENESS_REVIEW.md).

## platform_tool

Danh tính tool, loại hiệu ứng READ/WRITE/external và mức rủi ro.

Tenant RLS: **enabled + forced by integrity migrations 0047/0049**.

| Column | PostgreSQL type | Required | Default | Declared values |
|---|---|---|---|---|
| `id` | `uuid` | yes | `gen_random_uuid()` | — |
| `tenant_id` | `uuid` | yes | `—` | — |
| `code` | `text` | yes | `—` | — |
| `name` | `text` | yes | `—` | — |
| `effect_type` | `text` | yes | `—` | `READ`, `WRITE`, `EXTERNAL_SIDE_EFFECT` |
| `risk_level` | `text` | yes | `—` | `LOW`, `MEDIUM`, `HIGH`, `CRITICAL` |
| `created_at` | `timestamp with time zone` | yes | `now()` | — |
| `version` | `bigint` | yes | `1` | — |
| `updated_at` | `timestamp with time zone` | yes | `now()` | — |

Primary key: `id`.

Unique keys:

- `platform_tool_uq_0`: (`tenant_id`, `code`).
- `platform_tool_uq_1`: (`tenant_id`, `id`).

Foreign keys:

- (`tenant_id`) → `platform_tenant` (`id`); ON DELETE `restrict`.

Checks:

- `platform_tool_effect_type_ck`: `"platform_tool"."effect_type" in ('READ', 'WRITE', 'EXTERNAL_SIDE_EFFECT')`.
- `platform_tool_risk_level_ck`: `"platform_tool"."risk_level" in ('LOW', 'MEDIUM', 'HIGH', 'CRITICAL')`.
- `platform_tool_ck_0`: `version > 0`.

Additional cross-row/temporal rules: [integrity matrix](../DATABASE_DESIGN.md#integrity-matrix) and [coordination review](../COMPLETENESS_REVIEW.md).

## platform_tool_version

Phiên bản tool với input/output schema và fingerprint để agent ghim chính xác.

Tenant RLS: **enabled + forced by integrity migrations 0047/0049**.

| Column | PostgreSQL type | Required | Default | Declared values |
|---|---|---|---|---|
| `id` | `uuid` | yes | `gen_random_uuid()` | — |
| `tenant_id` | `uuid` | yes | `—` | — |
| `tool_id` | `uuid` | yes | `—` | — |
| `mcp_server_version_id` | `uuid` | no | `—` | — |
| `version_no` | `integer` | yes | `—` | — |
| `input_schema` | `jsonb` | yes | `—` | — |
| `output_schema` | `jsonb` | yes | `—` | — |
| `fingerprint` | `text` | yes | `—` | — |
| `status` | `text` | yes | `—` | `DRAFT`, `APPROVED`, `REVOKED` |
| `created_at` | `timestamp with time zone` | yes | `now()` | — |
| `version` | `bigint` | yes | `1` | — |
| `updated_at` | `timestamp with time zone` | yes | `now()` | — |

Primary key: `id`.

Unique keys:

- `platform_tool_version_uq_0`: (`tenant_id`, `tool_id`, `version_no`).
- `platform_tool_version_uq_1`: (`tenant_id`, `id`).

Foreign keys:

- (`tenant_id`) → `platform_tenant` (`id`); ON DELETE `restrict`.
- (`tenant_id`, `tool_id`) → `platform_tool` (`tenant_id`, `id`); ON DELETE `restrict`.
- (`tenant_id`, `mcp_server_version_id`) → `platform_mcp_server_version` (`tenant_id`, `id`); ON DELETE `restrict`.

Indexes:

- `platform_tool_version_ix_0`: (`tenant_id`, `mcp_server_version_id`).
- `platform_tool_version_ix_1`: (`tenant_id`, `tool_id`).

Checks:

- `platform_tool_version_status_ck`: `"platform_tool_version"."status" in ('DRAFT', 'APPROVED', 'REVOKED')`.
- `platform_tool_version_ck_0`: `version_no > 0`.
- `platform_tool_version_ck_1`: `version > 0`.

Additional cross-row/temporal rules: [integrity matrix](../DATABASE_DESIGN.md#integrity-matrix) and [coordination review](../COMPLETENESS_REVIEW.md).
