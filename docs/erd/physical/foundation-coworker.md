# foundation-coworker

Generated from Drizzle. External entities in the diagram are foreign-key targets owned by another module.

```mermaid
erDiagram
  agent_preferences {
    uuid tenant_id FK
    text user_id PK, FK
    text agent_id PK, FK
    timestamp_with_time_zone hidden_at
  }
  platform_tenant ||--o{ agent_preferences : "ownership"
  users ||--o{ agent_preferences : "user_id"
  agents ||--o{ agent_preferences : "agent_id"
  agents ||--o{ agent_preferences : "agent_id"
  agent_profiles {
    uuid tenant_id FK
    text agent_id PK, FK
    text owner_user_id FK
    text title
    text role_description
    text avatar_seed
    agent_visibility visibility
    text callback_token_hash
    timestamp_with_time_zone callback_token_issued_at
    timestamp_with_time_zone deleted_at
    timestamp_with_time_zone created_at
    timestamp_with_time_zone updated_at
  }
  platform_tenant ||--o{ agent_profiles : "ownership"
  agents ||--o| agent_profiles : "agent_id"
  users |o--o{ agent_profiles : "owner_user_id"
  agents ||--o| agent_profiles : "agent_id"
  routine_runs {
    uuid tenant_id FK
    text id PK
    text routine_id FK
    timestamp_with_time_zone started_at
    timestamp_with_time_zone finished_at
    routine_run_status status
    text error
  }
  platform_tenant ||--o{ routine_runs : "ownership"
  routines ||--o{ routine_runs : "routine_id"
  routines ||--o{ routine_runs : "routine_id"
  routine_sweeps {
    text id PK
    timestamp_with_time_zone swept_at
    text owner
  }
  routines {
    uuid tenant_id FK
    text id PK
    text owner_user_id FK
    text agent_id FK
    text channel_id
    text instruction
    text cron
    text timezone
    boolean enabled
    timestamp_with_time_zone next_run_at
    timestamp_with_time_zone last_run_at
    timestamp_with_time_zone created_at
    timestamp_with_time_zone updated_at
  }
  platform_tenant ||--o{ routines : "ownership"
  users ||--o{ routines : "owner_user_id"
  agents ||--o{ routines : "agent_id"
  agents ||--o{ routines : "agent_id"
```

## agent_preferences

Tùy chọn riêng của người dùng đối với agent, như ẩn agent khỏi danh sách.

Tenant RLS: **enabled + forced by integrity migrations 0047/0049/0052**.

| Column | PostgreSQL type | Required | Default | Declared values |
|---|---|---|---|---|
| `tenant_id` | `uuid` | yes | `nullif(current_setting('app.tenant_id', true), '')::uuid` | — |
| `user_id` | `text` | yes | `—` | — |
| `agent_id` | `text` | yes | `—` | — |
| `hidden_at` | `timestamp with time zone` | no | `—` | — |

Primary key: `user_id`, `agent_id`.

Unique keys:

- `agent_preferences_tenant_pk`: (`tenant_id`, `user_id`, `agent_id`).

Foreign keys:

- (`tenant_id`) → `platform_tenant` (`id`); ON DELETE `restrict`.
- (`user_id`) → `users` (`id`); ON DELETE `cascade`.
- (`agent_id`) → `agents` (`id`); ON DELETE `cascade`.
- (`tenant_id`, `agent_id`) → `agents` (`tenant_id`, `id`); ON DELETE `restrict`.

Cross-row rules and application responsibilities: [database design](../01_DATABASE_ERD_IMPLEMENTATION_COMPLETE.md) and [system flow](../02_BUSINESS_ANALYSIS_IMPLEMENTATION.md).

## agent_profiles

Hồ sơ hiển thị, ownership, visibility và callback credential hash của agent.

Tenant RLS: **enabled + forced by integrity migrations 0047/0049/0052**.

| Column | PostgreSQL type | Required | Default | Declared values |
|---|---|---|---|---|
| `tenant_id` | `uuid` | yes | `nullif(current_setting('app.tenant_id', true), '')::uuid` | — |
| `agent_id` | `text` | yes | `—` | — |
| `owner_user_id` | `text` | no | `—` | — |
| `title` | `text` | yes | `—` | — |
| `role_description` | `text` | yes | `—` | — |
| `avatar_seed` | `text` | yes | `—` | — |
| `visibility` | `agent_visibility` | yes | `—` | `public`, `private` |
| `callback_token_hash` | `text` | no | `—` | — |
| `callback_token_issued_at` | `timestamp with time zone` | no | `—` | — |
| `deleted_at` | `timestamp with time zone` | no | `—` | — |
| `created_at` | `timestamp with time zone` | yes | `now()` | — |
| `updated_at` | `timestamp with time zone` | yes | `now()` | — |

Primary key: `agent_id`.

Unique keys:

- `agent_profiles_tenant_pk`: (`tenant_id`, `agent_id`).

Foreign keys:

- (`tenant_id`) → `platform_tenant` (`id`); ON DELETE `restrict`.
- (`agent_id`) → `agents` (`id`); ON DELETE `cascade`.
- (`owner_user_id`) → `users` (`id`); ON DELETE `set null`.
- (`tenant_id`, `agent_id`) → `agents` (`tenant_id`, `id`); ON DELETE `restrict`.

Indexes:

- `agent_profiles_visibility_deleted_idx`: (`visibility`, `deleted_at`).

Cross-row rules and application responsibilities: [database design](../01_DATABASE_ERD_IMPLEMENTATION_COMPLETE.md) and [system flow](../02_BUSINESS_ANALYSIS_IMPLEMENTATION.md).

## routine_runs

Lịch sử kết quả mỗi lần thực hiện routine, gồm thành công/thất bại/bỏ qua.

Tenant RLS: **enabled + forced by integrity migrations 0047/0049/0052**.

| Column | PostgreSQL type | Required | Default | Declared values |
|---|---|---|---|---|
| `tenant_id` | `uuid` | yes | `nullif(current_setting('app.tenant_id', true), '')::uuid` | — |
| `id` | `text` | yes | `—` | — |
| `routine_id` | `text` | yes | `—` | — |
| `started_at` | `timestamp with time zone` | yes | `now()` | — |
| `finished_at` | `timestamp with time zone` | no | `—` | — |
| `status` | `routine_run_status` | no | `—` | `succeeded`, `failed`, `skipped` |
| `error` | `text` | no | `—` | — |

Primary key: `id`.

Unique keys:

- `routine_runs_tenant_pk`: (`tenant_id`, `id`).

Foreign keys:

- (`tenant_id`) → `platform_tenant` (`id`); ON DELETE `restrict`.
- (`routine_id`) → `routines` (`id`); ON DELETE `cascade`.
- (`tenant_id`, `routine_id`) → `routines` (`tenant_id`, `id`); ON DELETE `restrict`.

Indexes:

- `routine_runs_by_routine_idx`: (`routine_id`, `started_at`).

Cross-row rules and application responsibilities: [database design](../01_DATABASE_ERD_IMPLEMENTATION_COMPLETE.md) and [system flow](../02_BUSINESS_ANALYSIS_IMPLEMENTATION.md).

## routine_sweeps

Dấu xử lý lượt quét lịch routine giúp scheduler tránh chạy trùng hoặc bỏ sót.

Tenant RLS: **global identity or deployment infrastructure; application/operator authorization required**.

| Column | PostgreSQL type | Required | Default | Declared values |
|---|---|---|---|---|
| `id` | `text` | yes | `—` | — |
| `swept_at` | `timestamp with time zone` | yes | `now()` | — |
| `owner` | `text` | no | `—` | — |

Primary key: `id`.

Cross-row rules and application responsibilities: [database design](../01_DATABASE_ERD_IMPLEMENTATION_COMPLETE.md) and [system flow](../02_BUSINESS_ANALYSIS_IMPLEMENTATION.md).

## routines

Tác vụ định kỳ của nền sản phẩm: cấu hình lịch chạy và chủ sở hữu.

Tenant RLS: **enabled + forced by integrity migrations 0047/0049/0052**.

| Column | PostgreSQL type | Required | Default | Declared values |
|---|---|---|---|---|
| `tenant_id` | `uuid` | yes | `nullif(current_setting('app.tenant_id', true), '')::uuid` | — |
| `id` | `text` | yes | `—` | — |
| `owner_user_id` | `text` | yes | `—` | — |
| `agent_id` | `text` | yes | `—` | — |
| `channel_id` | `text` | yes | `—` | — |
| `instruction` | `text` | yes | `—` | — |
| `cron` | `text` | yes | `—` | — |
| `timezone` | `text` | yes | `UTC` | — |
| `enabled` | `boolean` | yes | `true` | — |
| `next_run_at` | `timestamp with time zone` | yes | `—` | — |
| `last_run_at` | `timestamp with time zone` | no | `—` | — |
| `created_at` | `timestamp with time zone` | yes | `now()` | — |
| `updated_at` | `timestamp with time zone` | yes | `now()` | — |

Primary key: `id`.

Unique keys:

- `routines_tenant_pk`: (`tenant_id`, `id`).

Foreign keys:

- (`tenant_id`) → `platform_tenant` (`id`); ON DELETE `restrict`.
- (`owner_user_id`) → `users` (`id`); ON DELETE `cascade`.
- (`agent_id`) → `agents` (`id`); ON DELETE `cascade`.
- (`tenant_id`, `agent_id`) → `agents` (`tenant_id`, `id`); ON DELETE `restrict`.

Indexes:

- `routines_due_idx`: (`enabled`, `next_run_at`).
- `routines_by_owner_idx`: (`owner_user_id`, `enabled`).

Cross-row rules and application responsibilities: [database design](../01_DATABASE_ERD_IMPLEMENTATION_COMPLETE.md) and [system flow](../02_BUSINESS_ANALYSIS_IMPLEMENTATION.md).
