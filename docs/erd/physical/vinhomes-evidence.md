# vinhomes-evidence

Generated from Drizzle. External entities in the diagram are foreign-key targets owned by another module.

```mermaid
erDiagram
  vh_evidence_ref {
    uuid id PK
    uuid tenant_id FK
    uuid project_id FK
    uuid incident_id FK
    uuid task_id FK
    uuid work_order_id FK
    uuid file_id FK
    text kind
    text capture_phase
    jsonb metadata
    text uploaded_by FK
    text visibility
    timestamp_with_time_zone created_at
  }
  platform_tenant ||--o{ vh_evidence_ref : "ownership"
  vh_project ||--o{ vh_evidence_ref : "ownership"
  vh_incident ||--o{ vh_evidence_ref : "incident_id"
  vh_task |o--o{ vh_evidence_ref : "incident_id + task_id"
  vh_work_order |o--o{ vh_evidence_ref : "incident_id + task_id + work_order_id"
  vh_file_object ||--o{ vh_evidence_ref : "file_id"
  users ||--o{ vh_evidence_ref : "uploaded_by"
  vh_qc_result {
    uuid id PK
    uuid tenant_id FK
    uuid project_id FK
    uuid incident_id FK
    uuid task_id FK
    uuid work_order_id FK
    text outcome
    jsonb criteria
    jsonb failed_criteria
    boolean redo_required
    text note
    text checked_by FK
    timestamp_with_time_zone checked_at
    timestamp_with_time_zone created_at
  }
  platform_tenant ||--o{ vh_qc_result : "ownership"
  vh_project ||--o{ vh_qc_result : "ownership"
  vh_incident ||--o{ vh_qc_result : "incident_id"
  vh_task ||--o{ vh_qc_result : "incident_id + task_id"
  vh_work_order ||--o{ vh_qc_result : "incident_id + task_id + work_order_id"
  users ||--o{ vh_qc_result : "checked_by"
  vh_qc_result_evidence {
    uuid tenant_id PK, FK
    uuid project_id FK
    uuid incident_id FK
    uuid qc_result_id PK, FK
    uuid evidence_ref_id PK, FK
    timestamp_with_time_zone created_at
  }
  platform_tenant ||--o{ vh_qc_result_evidence : "ownership"
  vh_project ||--o{ vh_qc_result_evidence : "ownership"
  vh_incident ||--o{ vh_qc_result_evidence : "incident_id"
  vh_qc_result ||--o{ vh_qc_result_evidence : "incident_id + qc_result_id"
  vh_evidence_ref ||--o{ vh_qc_result_evidence : "incident_id + evidence_ref_id"
  vh_root_cause_evidence {
    uuid tenant_id PK, FK
    uuid project_id FK
    uuid root_cause_finding_id PK, FK
    uuid evidence_ref_id PK, FK
    timestamp_with_time_zone created_at
  }
  platform_tenant ||--o{ vh_root_cause_evidence : "ownership"
  vh_project ||--o{ vh_root_cause_evidence : "ownership"
  vh_root_cause_finding ||--o{ vh_root_cause_evidence : "root_cause_finding_id"
  vh_evidence_ref ||--o{ vh_root_cause_evidence : "evidence_ref_id"
  vh_root_cause_finding {
    uuid id PK
    uuid tenant_id FK
    uuid project_id FK
    uuid incident_id FK
    text suspected_domain
    text description
    text status
    text created_by_type
    text created_by_id
    timestamp_with_time_zone created_at
    bigint version
    timestamp_with_time_zone updated_at
  }
  platform_tenant ||--o{ vh_root_cause_finding : "ownership"
  vh_project ||--o{ vh_root_cause_finding : "ownership"
  vh_incident ||--o{ vh_root_cause_finding : "incident_id"
  vh_root_cause_incident {
    uuid tenant_id PK, FK
    uuid project_id FK
    uuid root_cause_finding_id PK, FK
    uuid related_incident_id PK, FK
    text relation_type
    timestamp_with_time_zone created_at
  }
  platform_tenant ||--o{ vh_root_cause_incident : "ownership"
  vh_project ||--o{ vh_root_cause_incident : "ownership"
  vh_root_cause_finding ||--o{ vh_root_cause_incident : "root_cause_finding_id"
  vh_incident ||--o{ vh_root_cause_incident : "related_incident_id"
```

## vh_evidence_ref

Bằng chứng file gắn vào incident/task/work order và giai đoạn BEFORE/AFTER/QC.

Tenant RLS: **enabled + forced by integrity migrations 0047/0049/0052**.

| Column | PostgreSQL type | Required | Default | Declared values |
|---|---|---|---|---|
| `id` | `uuid` | yes | `gen_random_uuid()` | — |
| `tenant_id` | `uuid` | yes | `—` | — |
| `project_id` | `uuid` | yes | `—` | — |
| `incident_id` | `uuid` | yes | `—` | — |
| `task_id` | `uuid` | no | `—` | — |
| `work_order_id` | `uuid` | no | `—` | — |
| `file_id` | `uuid` | yes | `—` | — |
| `kind` | `text` | yes | `—` | — |
| `capture_phase` | `text` | yes | `—` | `BEFORE`, `AFTER`, `QC`, `OTHER` |
| `metadata` | `jsonb` | yes | `—` | — |
| `uploaded_by` | `text` | yes | `—` | — |
| `visibility` | `text` | yes | `—` | `INTERNAL`, `RESIDENT_VISIBLE` |
| `created_at` | `timestamp with time zone` | yes | `now()` | — |

Primary key: `id`.

Unique keys:

- `vh_evidence_ref_uq_0`: (`tenant_id`, `id`).
- `vh_evidence_ref_uq_1`: (`tenant_id`, `project_id`, `id`).
- `vh_evidence_ref_uq_2`: (`tenant_id`, `project_id`, `incident_id`, `id`).

Foreign keys:

- (`tenant_id`) → `platform_tenant` (`id`); ON DELETE `restrict`.
- (`tenant_id`, `project_id`) → `vh_project` (`tenant_id`, `id`); ON DELETE `restrict`.
- (`tenant_id`, `project_id`, `incident_id`) → `vh_incident` (`tenant_id`, `project_id`, `id`); ON DELETE `restrict`.
- (`tenant_id`, `project_id`, `incident_id`, `task_id`) → `vh_task` (`tenant_id`, `project_id`, `incident_id`, `id`); ON DELETE `restrict`.
- (`tenant_id`, `project_id`, `incident_id`, `task_id`, `work_order_id`) → `vh_work_order` (`tenant_id`, `project_id`, `incident_id`, `task_id`, `id`); ON DELETE `restrict`.
- (`tenant_id`, `file_id`) → `vh_file_object` (`tenant_id`, `id`); ON DELETE `restrict`.
- (`uploaded_by`) → `users` (`id`); ON DELETE `restrict`.

Indexes:

- `vh_evidence_ref_ix_0`: (`tenant_id`, `project_id`, `incident_id`, `task_id`, `work_order_id`).
- `vh_evidence_ref_ix_1`: (`tenant_id`, `project_id`).
- `vh_evidence_ref_ix_2`: (`tenant_id`, `project_id`, `incident_id`, `task_id`).
- `vh_evidence_ref_ix_3`: (`tenant_id`, `project_id`, `incident_id`).
- `vh_evidence_ref_ix_4`: (`uploaded_by`).
- `vh_evidence_ref_ix_5`: (`tenant_id`, `file_id`).

Checks:

- `vh_evidence_ref_capture_phase_ck`: `"vh_evidence_ref"."capture_phase" in ('BEFORE', 'AFTER', 'QC', 'OTHER')`.
- `vh_evidence_ref_visibility_ck`: `"vh_evidence_ref"."visibility" in ('INTERNAL', 'RESIDENT_VISIBLE')`.
- `vh_evidence_ref_ck_0`: `work_order_id IS NULL OR task_id IS NOT NULL`.

Cross-row rules and application responsibilities: [database design](../01_DATABASE_ERD_IMPLEMENTATION_COMPLETE.md) and [system flow](../02_BUSINESS_ANALYSIS_IMPLEMENTATION.md).

## vh_qc_result

Quyết định kiểm tra chất lượng bất biến cho một work order, gồm tiêu chí không đạt và yêu cầu redo.

Tenant RLS: **enabled + forced by integrity migrations 0047/0049/0052**.

| Column | PostgreSQL type | Required | Default | Declared values |
|---|---|---|---|---|
| `id` | `uuid` | yes | `gen_random_uuid()` | — |
| `tenant_id` | `uuid` | yes | `—` | — |
| `project_id` | `uuid` | yes | `—` | — |
| `incident_id` | `uuid` | yes | `—` | — |
| `task_id` | `uuid` | yes | `—` | — |
| `work_order_id` | `uuid` | yes | `—` | — |
| `outcome` | `text` | yes | `—` | `PASS`, `FAIL`, `INCONCLUSIVE` |
| `criteria` | `jsonb` | yes | `—` | — |
| `failed_criteria` | `jsonb` | yes | `—` | — |
| `redo_required` | `boolean` | yes | `—` | — |
| `note` | `text` | no | `—` | — |
| `checked_by` | `text` | yes | `—` | — |
| `checked_at` | `timestamp with time zone` | yes | `—` | — |
| `created_at` | `timestamp with time zone` | yes | `now()` | — |

Primary key: `id`.

Unique keys:

- `vh_qc_result_uq_0`: (`tenant_id`, `id`).
- `vh_qc_result_uq_1`: (`tenant_id`, `project_id`, `id`).
- `vh_qc_result_uq_2`: (`tenant_id`, `project_id`, `incident_id`, `id`).

Foreign keys:

- (`tenant_id`) → `platform_tenant` (`id`); ON DELETE `restrict`.
- (`tenant_id`, `project_id`) → `vh_project` (`tenant_id`, `id`); ON DELETE `restrict`.
- (`tenant_id`, `project_id`, `incident_id`) → `vh_incident` (`tenant_id`, `project_id`, `id`); ON DELETE `restrict`.
- (`tenant_id`, `project_id`, `incident_id`, `task_id`) → `vh_task` (`tenant_id`, `project_id`, `incident_id`, `id`); ON DELETE `restrict`.
- (`tenant_id`, `project_id`, `incident_id`, `task_id`, `work_order_id`) → `vh_work_order` (`tenant_id`, `project_id`, `incident_id`, `task_id`, `id`); ON DELETE `restrict`.
- (`checked_by`) → `users` (`id`); ON DELETE `restrict`.

Indexes:

- `vh_qc_result_ix_0`: (`tenant_id`, `project_id`, `incident_id`, `task_id`, `work_order_id`).
- `vh_qc_result_ix_1`: (`tenant_id`, `project_id`).
- `vh_qc_result_ix_2`: (`tenant_id`, `project_id`, `incident_id`, `task_id`).
- `vh_qc_result_ix_3`: (`tenant_id`, `project_id`, `incident_id`).
- `vh_qc_result_ix_4`: (`checked_by`).

Checks:

- `vh_qc_result_outcome_ck`: `"vh_qc_result"."outcome" in ('PASS', 'FAIL', 'INCONCLUSIVE')`.
- `vh_qc_result_ck_0`: `NOT redo_required OR outcome = 'FAIL'`.

Cross-row rules and application responsibilities: [database design](../01_DATABASE_ERD_IMPLEMENTATION_COMPLETE.md) and [system flow](../02_BUSINESS_ANALYSIS_IMPLEMENTATION.md).

## vh_qc_result_evidence

Liên kết quyết định QC với bằng chứng hỗ trợ.

Tenant RLS: **enabled + forced by integrity migrations 0047/0049/0052**.

| Column | PostgreSQL type | Required | Default | Declared values |
|---|---|---|---|---|
| `tenant_id` | `uuid` | yes | `—` | — |
| `project_id` | `uuid` | yes | `—` | — |
| `incident_id` | `uuid` | yes | `—` | — |
| `qc_result_id` | `uuid` | yes | `—` | — |
| `evidence_ref_id` | `uuid` | yes | `—` | — |
| `created_at` | `timestamp with time zone` | yes | `now()` | — |

Primary key: `tenant_id`, `qc_result_id`, `evidence_ref_id`.

Foreign keys:

- (`tenant_id`) → `platform_tenant` (`id`); ON DELETE `restrict`.
- (`tenant_id`, `project_id`) → `vh_project` (`tenant_id`, `id`); ON DELETE `restrict`.
- (`tenant_id`, `project_id`, `incident_id`) → `vh_incident` (`tenant_id`, `project_id`, `id`); ON DELETE `restrict`.
- (`tenant_id`, `project_id`, `incident_id`, `qc_result_id`) → `vh_qc_result` (`tenant_id`, `project_id`, `incident_id`, `id`); ON DELETE `restrict`.
- (`tenant_id`, `project_id`, `incident_id`, `evidence_ref_id`) → `vh_evidence_ref` (`tenant_id`, `project_id`, `incident_id`, `id`); ON DELETE `restrict`.

Indexes:

- `vh_qc_result_evidence_ix_0`: (`tenant_id`, `project_id`, `incident_id`, `evidence_ref_id`).
- `vh_qc_result_evidence_ix_1`: (`tenant_id`, `project_id`, `incident_id`, `qc_result_id`).
- `vh_qc_result_evidence_ix_2`: (`tenant_id`, `project_id`).
- `vh_qc_result_evidence_ix_3`: (`tenant_id`, `project_id`, `incident_id`).

Cross-row rules and application responsibilities: [database design](../01_DATABASE_ERD_IMPLEMENTATION_COMPLETE.md) and [system flow](../02_BUSINESS_ANALYSIS_IMPLEMENTATION.md).

## vh_root_cause_evidence

Bằng chứng hỗ trợ nhận định nguyên nhân gốc.

Tenant RLS: **enabled + forced by integrity migrations 0047/0049/0052**.

| Column | PostgreSQL type | Required | Default | Declared values |
|---|---|---|---|---|
| `tenant_id` | `uuid` | yes | `—` | — |
| `project_id` | `uuid` | yes | `—` | — |
| `root_cause_finding_id` | `uuid` | yes | `—` | — |
| `evidence_ref_id` | `uuid` | yes | `—` | — |
| `created_at` | `timestamp with time zone` | yes | `now()` | — |

Primary key: `tenant_id`, `root_cause_finding_id`, `evidence_ref_id`.

Foreign keys:

- (`tenant_id`) → `platform_tenant` (`id`); ON DELETE `restrict`.
- (`tenant_id`, `project_id`) → `vh_project` (`tenant_id`, `id`); ON DELETE `restrict`.
- (`tenant_id`, `project_id`, `root_cause_finding_id`) → `vh_root_cause_finding` (`tenant_id`, `project_id`, `id`); ON DELETE `restrict`.
- (`tenant_id`, `project_id`, `evidence_ref_id`) → `vh_evidence_ref` (`tenant_id`, `project_id`, `id`); ON DELETE `restrict`.

Indexes:

- `vh_root_cause_evidence_ix_0`: (`tenant_id`, `project_id`, `evidence_ref_id`).
- `vh_root_cause_evidence_ix_1`: (`tenant_id`, `project_id`).
- `vh_root_cause_evidence_ix_2`: (`tenant_id`, `project_id`, `root_cause_finding_id`).

Cross-row rules and application responsibilities: [database design](../01_DATABASE_ERD_IMPLEMENTATION_COMPLETE.md) and [system flow](../02_BUSINESS_ANALYSIS_IMPLEMENTATION.md).

## vh_root_cause_finding

Nhận định nguyên nhân gốc của sự cố, có trạng thái xác nhận và chủ thể tạo.

Tenant RLS: **enabled + forced by integrity migrations 0047/0049/0052**.

| Column | PostgreSQL type | Required | Default | Declared values |
|---|---|---|---|---|
| `id` | `uuid` | yes | `gen_random_uuid()` | — |
| `tenant_id` | `uuid` | yes | `—` | — |
| `project_id` | `uuid` | yes | `—` | — |
| `incident_id` | `uuid` | yes | `—` | — |
| `suspected_domain` | `text` | yes | `—` | `TECHNICAL`, `SECURITY`, `PROCESS`, `SANITATION`, `UNKNOWN` |
| `description` | `text` | yes | `—` | — |
| `status` | `text` | yes | `—` | `PROPOSED`, `CONFIRMED`, `REJECTED` |
| `created_by_type` | `text` | yes | `—` | `HUMAN`, `SYSTEM`, `AGENT` |
| `created_by_id` | `text` | yes | `—` | — |
| `created_at` | `timestamp with time zone` | yes | `now()` | — |
| `version` | `bigint` | yes | `1` | — |
| `updated_at` | `timestamp with time zone` | yes | `now()` | — |

Primary key: `id`.

Unique keys:

- `vh_root_cause_finding_uq_0`: (`tenant_id`, `id`).
- `vh_root_cause_finding_uq_1`: (`tenant_id`, `project_id`, `id`).

Foreign keys:

- (`tenant_id`) → `platform_tenant` (`id`); ON DELETE `restrict`.
- (`tenant_id`, `project_id`) → `vh_project` (`tenant_id`, `id`); ON DELETE `restrict`.
- (`tenant_id`, `project_id`, `incident_id`) → `vh_incident` (`tenant_id`, `project_id`, `id`); ON DELETE `restrict`.

Indexes:

- `vh_root_cause_finding_ix_0`: (`tenant_id`, `project_id`).
- `vh_root_cause_finding_ix_1`: (`tenant_id`, `project_id`, `incident_id`).

Checks:

- `vh_root_cause_finding_suspected_domain_ck`: `"vh_root_cause_finding"."suspected_domain" in ('TECHNICAL', 'SECURITY', 'PROCESS', 'SANITATION', 'UNKNOWN')`.
- `vh_root_cause_finding_status_ck`: `"vh_root_cause_finding"."status" in ('PROPOSED', 'CONFIRMED', 'REJECTED')`.
- `vh_root_cause_finding_created_by_type_ck`: `"vh_root_cause_finding"."created_by_type" in ('HUMAN', 'SYSTEM', 'AGENT')`.
- `vh_root_cause_finding_ck_0`: `version > 0`.

Cross-row rules and application responsibilities: [database design](../01_DATABASE_ERD_IMPLEMENTATION_COMPLETE.md) and [system flow](../02_BUSINESS_ANALYSIS_IMPLEMENTATION.md).

## vh_root_cause_incident

Những incident liên quan tới một nhận định nguyên nhân gốc.

Tenant RLS: **enabled + forced by integrity migrations 0047/0049/0052**.

| Column | PostgreSQL type | Required | Default | Declared values |
|---|---|---|---|---|
| `tenant_id` | `uuid` | yes | `—` | — |
| `project_id` | `uuid` | yes | `—` | — |
| `root_cause_finding_id` | `uuid` | yes | `—` | — |
| `related_incident_id` | `uuid` | yes | `—` | — |
| `relation_type` | `text` | yes | `—` | — |
| `created_at` | `timestamp with time zone` | yes | `now()` | — |

Primary key: `tenant_id`, `root_cause_finding_id`, `related_incident_id`.

Foreign keys:

- (`tenant_id`) → `platform_tenant` (`id`); ON DELETE `restrict`.
- (`tenant_id`, `project_id`) → `vh_project` (`tenant_id`, `id`); ON DELETE `restrict`.
- (`tenant_id`, `project_id`, `root_cause_finding_id`) → `vh_root_cause_finding` (`tenant_id`, `project_id`, `id`); ON DELETE `restrict`.
- (`tenant_id`, `project_id`, `related_incident_id`) → `vh_incident` (`tenant_id`, `project_id`, `id`); ON DELETE `restrict`.

Indexes:

- `vh_root_cause_incident_ix_0`: (`tenant_id`, `project_id`, `related_incident_id`).
- `vh_root_cause_incident_ix_1`: (`tenant_id`, `project_id`).
- `vh_root_cause_incident_ix_2`: (`tenant_id`, `project_id`, `root_cause_finding_id`).

Cross-row rules and application responsibilities: [database design](../01_DATABASE_ERD_IMPLEMENTATION_COMPLETE.md) and [system flow](../02_BUSINESS_ANALYSIS_IMPLEMENTATION.md).
