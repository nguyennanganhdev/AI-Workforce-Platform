# vinhomes-intake

Generated from Drizzle. External entities in the diagram are foreign-key targets owned by another module.

```mermaid
erDiagram
  vh_case {
    uuid id PK
    uuid tenant_id FK
    uuid project_id FK
    text resident_user_id FK
    uuid apartment_id FK
    uuid opened_by_membership_id FK
    text status
    text summary
    timestamp_with_time_zone opened_at
    timestamp_with_time_zone closed_at
    timestamp_with_time_zone created_at
    bigint version
    timestamp_with_time_zone updated_at
  }
  platform_tenant ||--o{ vh_case : "ownership"
  vh_project ||--o{ vh_case : "ownership"
  users ||--o{ vh_case : "resident_user_id"
  vh_apartment |o--o{ vh_case : "apartment_id"
  vh_property_membership ||--o{ vh_case : "opened_by_membership_id"
  vh_property_membership ||--o{ vh_case : "resident_user_id + opened_by_membership_id"
  vh_property_membership |o--o{ vh_case : "apartment_id + opened_by_membership_id"
  vh_feedback {
    uuid id PK
    uuid tenant_id FK
    uuid project_id FK
    uuid report_id FK
    text author_user_id FK
    integer rating
    text comment
    timestamp_with_time_zone created_at
  }
  platform_tenant ||--o{ vh_feedback : "ownership"
  vh_project ||--o{ vh_feedback : "ownership"
  vh_resident_report ||--o{ vh_feedback : "report_id"
  users ||--o{ vh_feedback : "author_user_id"
  vh_resident_report ||--o| vh_feedback : "author_user_id + report_id"
  vh_issue_candidate {
    uuid id PK
    uuid tenant_id FK
    uuid project_id FK
    uuid case_id FK
    uuid source_request_id FK
    text domain
    text category
    text severity
    text normalized_summary
    jsonb location_json
    numeric confidence
    text identified_by_type
    text identified_by_id
    text status
    jsonb required_fields_json
    jsonb missing_fields_json
    timestamp_with_time_zone created_at
    bigint version
    timestamp_with_time_zone updated_at
  }
  platform_tenant ||--o{ vh_issue_candidate : "ownership"
  vh_project ||--o{ vh_issue_candidate : "ownership"
  vh_case ||--o{ vh_issue_candidate : "case_id"
  vh_resident_request |o--o{ vh_issue_candidate : "case_id + source_request_id"
  vh_issue_relation {
    uuid tenant_id PK, FK
    uuid project_id FK
    uuid source_issue_id PK, FK
    uuid target_issue_id PK, FK
    text relation_type PK
    text reason
    timestamp_with_time_zone created_at
  }
  platform_tenant ||--o{ vh_issue_relation : "ownership"
  vh_project ||--o{ vh_issue_relation : "ownership"
  vh_issue_candidate ||--o{ vh_issue_relation : "source_issue_id"
  vh_issue_candidate ||--o{ vh_issue_relation : "target_issue_id"
  vh_resident_confirmation {
    uuid id PK
    uuid tenant_id FK
    uuid project_id FK
    uuid report_id FK
    uuid incident_id FK
    bigint resolution_version
    text response
    text note
    text confirmed_by_user_id FK
    timestamp_with_time_zone created_at
  }
  platform_tenant ||--o{ vh_resident_confirmation : "ownership"
  vh_project ||--o{ vh_resident_confirmation : "ownership"
  vh_resident_report ||--o{ vh_resident_confirmation : "report_id"
  vh_incident ||--o{ vh_resident_confirmation : "incident_id"
  users ||--o{ vh_resident_confirmation : "confirmed_by_user_id"
  vh_resident_report ||--o{ vh_resident_confirmation : "incident_id + confirmed_by_user_id + report_id"
  vh_resident_report {
    uuid id PK
    uuid tenant_id FK
    uuid project_id FK
    uuid case_id FK
    uuid issue_candidate_id FK
    uuid incident_id FK
    text reporter_id FK
    uuid reporter_membership_id FK
    uuid apartment_id FK
    text category
    text description
    jsonb location_json
    text status
    timestamp_with_time_zone created_at
    bigint version
    timestamp_with_time_zone updated_at
  }
  platform_tenant ||--o{ vh_resident_report : "ownership"
  vh_project ||--o{ vh_resident_report : "ownership"
  vh_case ||--o{ vh_resident_report : "case_id"
  vh_issue_candidate |o--o{ vh_resident_report : "case_id + issue_candidate_id"
  vh_incident |o--o{ vh_resident_report : "incident_id"
  users ||--o{ vh_resident_report : "reporter_id"
  vh_property_membership ||--o{ vh_resident_report : "reporter_membership_id"
  vh_apartment |o--o{ vh_resident_report : "apartment_id"
  vh_property_membership ||--o{ vh_resident_report : "reporter_id + reporter_membership_id"
  vh_property_membership |o--o{ vh_resident_report : "apartment_id + reporter_membership_id"
  vh_resident_request {
    uuid id PK
    uuid tenant_id FK
    uuid project_id FK
    uuid case_id FK
    text channel
    text request_type
    text raw_content_ref
    text sanitized_content
    text idempotency_key
    text submitted_by FK
    timestamp_with_time_zone created_at
  }
  platform_tenant ||--o{ vh_resident_request : "ownership"
  vh_project ||--o{ vh_resident_request : "ownership"
  vh_case ||--o{ vh_resident_request : "case_id"
  users ||--o{ vh_resident_request : "submitted_by"
```

## vh_case

Hồ sơ tiếp nhận hỗ trợ có thể chứa nhiều yêu cầu và nhiều vấn đề trước khi thành incident.

Tenant RLS: **enabled + forced by integrity migrations 0047/0049**.

| Column | PostgreSQL type | Required | Default | Declared values |
|---|---|---|---|---|
| `id` | `uuid` | yes | `gen_random_uuid()` | — |
| `tenant_id` | `uuid` | yes | `—` | — |
| `project_id` | `uuid` | yes | `—` | — |
| `resident_user_id` | `text` | yes | `—` | — |
| `apartment_id` | `uuid` | no | `—` | — |
| `opened_by_membership_id` | `uuid` | yes | `—` | — |
| `status` | `text` | yes | `—` | `OPEN`, `CLARIFYING`, `READY`, `TICKETED`, `CLOSED`, `CANCELLED` |
| `summary` | `text` | yes | `—` | — |
| `opened_at` | `timestamp with time zone` | yes | `—` | — |
| `closed_at` | `timestamp with time zone` | no | `—` | — |
| `created_at` | `timestamp with time zone` | yes | `now()` | — |
| `version` | `bigint` | yes | `1` | — |
| `updated_at` | `timestamp with time zone` | yes | `now()` | — |

Primary key: `id`.

Unique keys:

- `vh_case_uq_0`: (`tenant_id`, `id`).
- `vh_case_uq_1`: (`tenant_id`, `project_id`, `id`).

Foreign keys:

- (`tenant_id`) → `platform_tenant` (`id`); ON DELETE `restrict`.
- (`tenant_id`, `project_id`) → `vh_project` (`tenant_id`, `id`); ON DELETE `restrict`.
- (`resident_user_id`) → `users` (`id`); ON DELETE `restrict`.
- (`tenant_id`, `project_id`, `apartment_id`) → `vh_apartment` (`tenant_id`, `project_id`, `id`); ON DELETE `restrict`.
- (`tenant_id`, `project_id`, `opened_by_membership_id`) → `vh_property_membership` (`tenant_id`, `project_id`, `id`); ON DELETE `restrict`.
- (`tenant_id`, `project_id`, `resident_user_id`, `opened_by_membership_id`) → `vh_property_membership` (`tenant_id`, `project_id`, `user_id`, `id`); ON DELETE `restrict`.
- (`tenant_id`, `project_id`, `apartment_id`, `opened_by_membership_id`) → `vh_property_membership` (`tenant_id`, `project_id`, `apartment_id`, `id`); ON DELETE `restrict`.

Indexes:

- `vh_case_ix_0`: (`tenant_id`, `project_id`, `opened_by_membership_id`).
- `vh_case_ix_1`: (`resident_user_id`).
- `vh_case_ix_2`: (`tenant_id`, `project_id`, `apartment_id`).
- `vh_case_ix_3`: (`tenant_id`, `project_id`).

Checks:

- `vh_case_status_ck`: `"vh_case"."status" in ('OPEN', 'CLARIFYING', 'READY', 'TICKETED', 'CLOSED', 'CANCELLED')`.
- `vh_case_ck_0`: `version > 0`.

Additional cross-row/temporal rules: [integrity matrix](../DATABASE_DESIGN.md#integrity-matrix) and [coordination review](../COMPLETENESS_REVIEW.md).

## vh_feedback

Đánh giá của cư dân về phản ánh, độc lập với lệnh thay đổi trạng thái incident.

Tenant RLS: **enabled + forced by integrity migrations 0047/0049**.

| Column | PostgreSQL type | Required | Default | Declared values |
|---|---|---|---|---|
| `id` | `uuid` | yes | `gen_random_uuid()` | — |
| `tenant_id` | `uuid` | yes | `—` | — |
| `project_id` | `uuid` | yes | `—` | — |
| `report_id` | `uuid` | yes | `—` | — |
| `author_user_id` | `text` | yes | `—` | — |
| `rating` | `integer` | yes | `—` | — |
| `comment` | `text` | no | `—` | — |
| `created_at` | `timestamp with time zone` | yes | `now()` | — |

Primary key: `id`.

Unique keys:

- `vh_feedback_uq_0`: (`tenant_id`, `report_id`, `author_user_id`).
- `vh_feedback_uq_1`: (`tenant_id`, `id`).
- `vh_feedback_uq_2`: (`tenant_id`, `project_id`, `id`).

Foreign keys:

- (`tenant_id`) → `platform_tenant` (`id`); ON DELETE `restrict`.
- (`tenant_id`, `project_id`) → `vh_project` (`tenant_id`, `id`); ON DELETE `restrict`.
- (`tenant_id`, `project_id`, `report_id`) → `vh_resident_report` (`tenant_id`, `project_id`, `id`); ON DELETE `restrict`.
- (`author_user_id`) → `users` (`id`); ON DELETE `restrict`.
- (`tenant_id`, `author_user_id`, `report_id`) → `vh_resident_report` (`tenant_id`, `reporter_id`, `id`); ON DELETE `restrict`.

Indexes:

- `vh_feedback_ix_0`: (`author_user_id`).
- `vh_feedback_ix_1`: (`tenant_id`, `project_id`, `report_id`).
- `vh_feedback_ix_2`: (`tenant_id`, `project_id`).

Checks:

- `vh_feedback_ck_0`: `rating BETWEEN 1 AND 5`.

Additional cross-row/temporal rules: [integrity matrix](../DATABASE_DESIGN.md#integrity-matrix) and [coordination review](../COMPLETENESS_REVIEW.md).

## vh_issue_candidate

Vấn đề được phát hiện/làm rõ trước khi materialize thành phản ánh chính thức.

Tenant RLS: **enabled + forced by integrity migrations 0047/0049**.

| Column | PostgreSQL type | Required | Default | Declared values |
|---|---|---|---|---|
| `id` | `uuid` | yes | `gen_random_uuid()` | — |
| `tenant_id` | `uuid` | yes | `—` | — |
| `project_id` | `uuid` | yes | `—` | — |
| `case_id` | `uuid` | yes | `—` | — |
| `source_request_id` | `uuid` | no | `—` | — |
| `domain` | `text` | yes | `—` | — |
| `category` | `text` | yes | `—` | — |
| `severity` | `text` | yes | `—` | `LOW`, `MEDIUM`, `HIGH`, `CRITICAL` |
| `normalized_summary` | `text` | yes | `—` | — |
| `location_json` | `jsonb` | yes | `—` | — |
| `confidence` | `numeric` | no | `—` | — |
| `identified_by_type` | `text` | yes | `—` | `HUMAN`, `SYSTEM`, `AGENT` |
| `identified_by_id` | `text` | yes | `—` | — |
| `status` | `text` | yes | `—` | `DETECTED`, `NEEDS_CLARIFICATION`, `READY`, `MERGED`, `DISCARDED`, `MATERIALIZED` |
| `required_fields_json` | `jsonb` | yes | `—` | — |
| `missing_fields_json` | `jsonb` | yes | `—` | — |
| `created_at` | `timestamp with time zone` | yes | `now()` | — |
| `version` | `bigint` | yes | `1` | — |
| `updated_at` | `timestamp with time zone` | yes | `now()` | — |

Primary key: `id`.

Unique keys:

- `vh_issue_candidate_uq_0`: (`tenant_id`, `id`).
- `vh_issue_candidate_uq_1`: (`tenant_id`, `project_id`, `id`).
- `vh_issue_candidate_uq_2`: (`tenant_id`, `project_id`, `case_id`, `id`).

Foreign keys:

- (`tenant_id`) → `platform_tenant` (`id`); ON DELETE `restrict`.
- (`tenant_id`, `project_id`) → `vh_project` (`tenant_id`, `id`); ON DELETE `restrict`.
- (`tenant_id`, `project_id`, `case_id`) → `vh_case` (`tenant_id`, `project_id`, `id`); ON DELETE `restrict`.
- (`tenant_id`, `project_id`, `case_id`, `source_request_id`) → `vh_resident_request` (`tenant_id`, `project_id`, `case_id`, `id`); ON DELETE `restrict`.

Indexes:

- `vh_issue_candidate_ix_0`: (`tenant_id`, `project_id`, `case_id`, `source_request_id`).
- `vh_issue_candidate_ix_1`: (`tenant_id`, `case_id`, `status`).
- `vh_issue_candidate_ix_2`: (`tenant_id`, `project_id`, `case_id`).
- `vh_issue_candidate_ix_3`: (`tenant_id`, `project_id`).

Checks:

- `vh_issue_candidate_severity_ck`: `"vh_issue_candidate"."severity" in ('LOW', 'MEDIUM', 'HIGH', 'CRITICAL')`.
- `vh_issue_candidate_identified_by_type_ck`: `"vh_issue_candidate"."identified_by_type" in ('HUMAN', 'SYSTEM', 'AGENT')`.
- `vh_issue_candidate_status_ck`: `"vh_issue_candidate"."status" in ('DETECTED', 'NEEDS_CLARIFICATION', 'READY', 'MERGED', 'DISCARDED', 'MATERIALIZED')`.
- `vh_issue_candidate_ck_0`: `confidence IS NULL OR (confidence >= 0 AND confidence <= 1)`.
- `vh_issue_candidate_ck_1`: `version > 0`.

Additional cross-row/temporal rules: [integrity matrix](../DATABASE_DESIGN.md#integrity-matrix) and [coordination review](../COMPLETENESS_REVIEW.md).

## vh_issue_relation

Quan hệ tách/gộp/liên quan/phụ thuộc giữa các issue candidate.

Tenant RLS: **enabled + forced by integrity migrations 0047/0049**.

| Column | PostgreSQL type | Required | Default | Declared values |
|---|---|---|---|---|
| `tenant_id` | `uuid` | yes | `—` | — |
| `project_id` | `uuid` | yes | `—` | — |
| `source_issue_id` | `uuid` | yes | `—` | — |
| `target_issue_id` | `uuid` | yes | `—` | — |
| `relation_type` | `text` | yes | `—` | `SPLIT_FROM`, `MERGED_INTO`, `RELATED`, `DEPENDS_ON` |
| `reason` | `text` | yes | `—` | — |
| `created_at` | `timestamp with time zone` | yes | `now()` | — |

Primary key: `tenant_id`, `source_issue_id`, `target_issue_id`, `relation_type`.

Foreign keys:

- (`tenant_id`) → `platform_tenant` (`id`); ON DELETE `restrict`.
- (`tenant_id`, `project_id`) → `vh_project` (`tenant_id`, `id`); ON DELETE `restrict`.
- (`tenant_id`, `project_id`, `source_issue_id`) → `vh_issue_candidate` (`tenant_id`, `project_id`, `id`); ON DELETE `restrict`.
- (`tenant_id`, `project_id`, `target_issue_id`) → `vh_issue_candidate` (`tenant_id`, `project_id`, `id`); ON DELETE `restrict`.

Indexes:

- `vh_issue_relation_ix_0`: (`tenant_id`, `project_id`, `target_issue_id`).
- `vh_issue_relation_ix_1`: (`tenant_id`, `project_id`).
- `vh_issue_relation_ix_2`: (`tenant_id`, `project_id`, `source_issue_id`).

Checks:

- `vh_issue_relation_relation_type_ck`: `"vh_issue_relation"."relation_type" in ('SPLIT_FROM', 'MERGED_INTO', 'RELATED', 'DEPENDS_ON')`.
- `vh_issue_relation_ck_0`: `source_issue_id <> target_issue_id`.

Additional cross-row/temporal rules: [integrity matrix](../DATABASE_DESIGN.md#integrity-matrix) and [coordination review](../COMPLETENESS_REVIEW.md).

## vh_resident_confirmation

Ý kiến chấp nhận/yêu cầu mở lại của reporter theo đúng vòng resolution hiện tại.

Tenant RLS: **enabled + forced by integrity migrations 0047/0049**.

| Column | PostgreSQL type | Required | Default | Declared values |
|---|---|---|---|---|
| `id` | `uuid` | yes | `gen_random_uuid()` | — |
| `tenant_id` | `uuid` | yes | `—` | — |
| `project_id` | `uuid` | yes | `—` | — |
| `report_id` | `uuid` | yes | `—` | — |
| `incident_id` | `uuid` | yes | `—` | — |
| `resolution_version` | `bigint` | yes | `—` | — |
| `response` | `text` | yes | `—` | `ACCEPTED`, `REOPEN_REQUESTED` |
| `note` | `text` | no | `—` | — |
| `confirmed_by_user_id` | `text` | yes | `—` | — |
| `created_at` | `timestamp with time zone` | yes | `now()` | — |

Primary key: `id`.

Unique keys:

- `vh_resident_confirmation_uq_0`: (`tenant_id`, `report_id`, `resolution_version`).
- `vh_resident_confirmation_uq_1`: (`tenant_id`, `id`).
- `vh_resident_confirmation_uq_2`: (`tenant_id`, `project_id`, `id`).

Foreign keys:

- (`tenant_id`) → `platform_tenant` (`id`); ON DELETE `restrict`.
- (`tenant_id`, `project_id`) → `vh_project` (`tenant_id`, `id`); ON DELETE `restrict`.
- (`tenant_id`, `project_id`, `report_id`) → `vh_resident_report` (`tenant_id`, `project_id`, `id`); ON DELETE `restrict`.
- (`tenant_id`, `project_id`, `incident_id`) → `vh_incident` (`tenant_id`, `project_id`, `id`); ON DELETE `restrict`.
- (`confirmed_by_user_id`) → `users` (`id`); ON DELETE `restrict`.
- (`tenant_id`, `incident_id`, `confirmed_by_user_id`, `report_id`) → `vh_resident_report` (`tenant_id`, `incident_id`, `reporter_id`, `id`); ON DELETE `restrict`.

Indexes:

- `vh_resident_confirmation_ix_0`: (`tenant_id`, `incident_id`, `resolution_version`).
- `vh_resident_confirmation_ix_1`: (`tenant_id`, `project_id`).
- `vh_resident_confirmation_ix_2`: (`tenant_id`, `project_id`, `incident_id`).
- `vh_resident_confirmation_ix_3`: (`confirmed_by_user_id`).
- `vh_resident_confirmation_ix_4`: (`tenant_id`, `project_id`, `report_id`).

Checks:

- `vh_resident_confirmation_response_ck`: `"vh_resident_confirmation"."response" in ('ACCEPTED', 'REOPEN_REQUESTED')`.
- `vh_resident_confirmation_ck_0`: `resolution_version > 0`.

Additional cross-row/temporal rules: [integrity matrix](../DATABASE_DESIGN.md#integrity-matrix) and [coordination review](../COMPLETENESS_REVIEW.md).

## vh_resident_report

Phản ánh chính thức của một cư dân; có thể được gắn vào incident chung với nhiều phản ánh.

Tenant RLS: **enabled + forced by integrity migrations 0047/0049**.

| Column | PostgreSQL type | Required | Default | Declared values |
|---|---|---|---|---|
| `id` | `uuid` | yes | `gen_random_uuid()` | — |
| `tenant_id` | `uuid` | yes | `—` | — |
| `project_id` | `uuid` | yes | `—` | — |
| `case_id` | `uuid` | yes | `—` | — |
| `issue_candidate_id` | `uuid` | no | `—` | — |
| `incident_id` | `uuid` | no | `—` | — |
| `reporter_id` | `text` | yes | `—` | — |
| `reporter_membership_id` | `uuid` | yes | `—` | — |
| `apartment_id` | `uuid` | no | `—` | — |
| `category` | `text` | yes | `—` | — |
| `description` | `text` | yes | `—` | — |
| `location_json` | `jsonb` | yes | `—` | — |
| `status` | `text` | yes | `—` | `SUBMITTED`, `LINKED`, `WITHDRAWN` |
| `created_at` | `timestamp with time zone` | yes | `now()` | — |
| `version` | `bigint` | yes | `1` | — |
| `updated_at` | `timestamp with time zone` | yes | `now()` | — |

Primary key: `id`.

Unique keys:

- `vh_resident_report_uq_0`: (`tenant_id`, `issue_candidate_id`).
- `vh_resident_report_uq_1`: (`tenant_id`, `id`).
- `vh_resident_report_uq_2`: (`tenant_id`, `project_id`, `id`).
- `vh_resident_report_uq_3`: (`tenant_id`, `incident_id`, `reporter_id`, `id`).
- `vh_resident_report_uq_4`: (`tenant_id`, `reporter_id`, `id`).
- `vh_resident_report_uq_5`: (`tenant_id`, `incident_id`, `id`).

Foreign keys:

- (`tenant_id`) → `platform_tenant` (`id`); ON DELETE `restrict`.
- (`tenant_id`, `project_id`) → `vh_project` (`tenant_id`, `id`); ON DELETE `restrict`.
- (`tenant_id`, `project_id`, `case_id`) → `vh_case` (`tenant_id`, `project_id`, `id`); ON DELETE `restrict`.
- (`tenant_id`, `project_id`, `case_id`, `issue_candidate_id`) → `vh_issue_candidate` (`tenant_id`, `project_id`, `case_id`, `id`); ON DELETE `restrict`.
- (`tenant_id`, `project_id`, `incident_id`) → `vh_incident` (`tenant_id`, `project_id`, `id`); ON DELETE `restrict`.
- (`reporter_id`) → `users` (`id`); ON DELETE `restrict`.
- (`tenant_id`, `project_id`, `reporter_membership_id`) → `vh_property_membership` (`tenant_id`, `project_id`, `id`); ON DELETE `restrict`.
- (`tenant_id`, `project_id`, `apartment_id`) → `vh_apartment` (`tenant_id`, `project_id`, `id`); ON DELETE `restrict`.
- (`tenant_id`, `project_id`, `reporter_id`, `reporter_membership_id`) → `vh_property_membership` (`tenant_id`, `project_id`, `user_id`, `id`); ON DELETE `restrict`.
- (`tenant_id`, `project_id`, `apartment_id`, `reporter_membership_id`) → `vh_property_membership` (`tenant_id`, `project_id`, `apartment_id`, `id`); ON DELETE `restrict`.

Indexes:

- `vh_resident_report_ix_0`: (`tenant_id`, `reporter_id`, `created_at`).
- `vh_resident_report_ix_1`: (`tenant_id`, `project_id`, `case_id`, `issue_candidate_id`).
- `vh_resident_report_ix_2`: (`tenant_id`, `project_id`).
- `vh_resident_report_ix_3`: (`tenant_id`, `project_id`, `incident_id`).
- `vh_resident_report_ix_4`: (`reporter_id`).
- `vh_resident_report_ix_5`: (`tenant_id`, `project_id`, `case_id`).
- `vh_resident_report_ix_6`: (`tenant_id`, `project_id`, `apartment_id`).
- `vh_resident_report_ix_7`: (`tenant_id`, `project_id`, `reporter_membership_id`).

Checks:

- `vh_resident_report_status_ck`: `"vh_resident_report"."status" in ('SUBMITTED', 'LINKED', 'WITHDRAWN')`.
- `vh_resident_report_ck_0`: `(status = 'LINKED') = (incident_id IS NOT NULL)`.
- `vh_resident_report_ck_1`: `version > 0`.

Additional cross-row/temporal rules: [integrity matrix](../DATABASE_DESIGN.md#integrity-matrix) and [coordination review](../COMPLETENESS_REVIEW.md).

## vh_resident_request

Một thông điệp/đầu vào đã làm sạch của cư dân trong Case, có idempotency key.

Tenant RLS: **enabled + forced by integrity migrations 0047/0049**.

| Column | PostgreSQL type | Required | Default | Declared values |
|---|---|---|---|---|
| `id` | `uuid` | yes | `gen_random_uuid()` | — |
| `tenant_id` | `uuid` | yes | `—` | — |
| `project_id` | `uuid` | yes | `—` | — |
| `case_id` | `uuid` | yes | `—` | — |
| `channel` | `text` | yes | `—` | — |
| `request_type` | `text` | yes | `—` | — |
| `raw_content_ref` | `text` | no | `—` | — |
| `sanitized_content` | `text` | yes | `—` | — |
| `idempotency_key` | `text` | yes | `—` | — |
| `submitted_by` | `text` | yes | `—` | — |
| `created_at` | `timestamp with time zone` | yes | `now()` | — |

Primary key: `id`.

Unique keys:

- `vh_resident_request_uq_0`: (`tenant_id`, `idempotency_key`).
- `vh_resident_request_uq_1`: (`tenant_id`, `id`).
- `vh_resident_request_uq_2`: (`tenant_id`, `project_id`, `id`).
- `vh_resident_request_uq_3`: (`tenant_id`, `project_id`, `case_id`, `id`).

Foreign keys:

- (`tenant_id`) → `platform_tenant` (`id`); ON DELETE `restrict`.
- (`tenant_id`, `project_id`) → `vh_project` (`tenant_id`, `id`); ON DELETE `restrict`.
- (`tenant_id`, `project_id`, `case_id`) → `vh_case` (`tenant_id`, `project_id`, `id`); ON DELETE `restrict`.
- (`submitted_by`) → `users` (`id`); ON DELETE `restrict`.

Indexes:

- `vh_resident_request_ix_0`: (`tenant_id`, `project_id`, `case_id`).
- `vh_resident_request_ix_1`: (`tenant_id`, `case_id`, `created_at`).
- `vh_resident_request_ix_2`: (`tenant_id`, `project_id`).
- `vh_resident_request_ix_3`: (`submitted_by`).

Additional cross-row/temporal rules: [integrity matrix](../DATABASE_DESIGN.md#integrity-matrix) and [coordination review](../COMPLETENESS_REVIEW.md).
