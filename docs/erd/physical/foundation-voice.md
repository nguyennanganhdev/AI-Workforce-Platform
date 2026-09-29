# foundation-voice

Generated from Drizzle. External entities in the diagram are foreign-key targets owned by another module.

```mermaid
erDiagram
  voice_sessions {
    uuid tenant_id FK
    text id PK
    text channel_id FK
    text user_id FK
    text anchor_message_id
    timestamp_with_time_zone started_at
    timestamp_with_time_zone ended_at
    integer duration_seconds
    jsonb transcript
    text summary
    text summary_status
  }
  platform_tenant ||--o{ voice_sessions : "ownership"
  channels ||--o{ voice_sessions : "channel_id"
  users ||--o{ voice_sessions : "user_id"
  channels ||--o{ voice_sessions : "channel_id"
```

## voice_sessions

Metadata phiên thoại của người dùng/agent trong ứng dụng.

Tenant RLS: **enabled + forced by integrity migrations 0047/0049/0052**.

| Column | PostgreSQL type | Required | Default | Declared values |
|---|---|---|---|---|
| `tenant_id` | `uuid` | yes | `nullif(current_setting('app.tenant_id', true), '')::uuid` | — |
| `id` | `text` | yes | `—` | — |
| `channel_id` | `text` | yes | `—` | — |
| `user_id` | `text` | yes | `—` | — |
| `anchor_message_id` | `text` | no | `—` | — |
| `started_at` | `timestamp with time zone` | yes | `—` | — |
| `ended_at` | `timestamp with time zone` | yes | `—` | — |
| `duration_seconds` | `integer` | yes | `—` | — |
| `transcript` | `jsonb` | yes | `—` | — |
| `summary` | `text` | no | `—` | — |
| `summary_status` | `text` | yes | `failed` | — |

Primary key: `id`.

Unique keys:

- `voice_sessions_tenant_pk`: (`tenant_id`, `id`).

Foreign keys:

- (`tenant_id`) → `platform_tenant` (`id`); ON DELETE `restrict`.
- (`channel_id`) → `channels` (`id`); ON DELETE `cascade`.
- (`user_id`) → `users` (`id`); ON DELETE `cascade`.
- (`tenant_id`, `channel_id`) → `channels` (`tenant_id`, `id`); ON DELETE `restrict`.

Indexes:

- `voice_sessions_channel_started_idx`: (`channel_id`, `started_at`, `id`).

Checks:

- `voice_sessions_duration_check`: `"voice_sessions"."duration_seconds" >= 0`.
- `voice_sessions_summary_check`: `("voice_sessions"."summary_status" = 'ready' AND "voice_sessions"."summary" IS NOT NULL) OR ("voice_sessions"."summary_status" = 'failed' AND "voice_sessions"."summary" IS NULL)`.

Cross-row rules and application responsibilities: [database design](../01_DATABASE_ERD_IMPLEMENTATION_COMPLETE.md) and [system flow](../02_BUSINESS_ANALYSIS_IMPLEMENTATION.md).
