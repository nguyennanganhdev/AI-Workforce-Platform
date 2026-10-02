---
title: "Đặc tả tool domain kỹ thuật A2"
version: "1.0 Draft"
date: "30/09/2026"
audience: "Backend, Agent, BA, QA và Domain Owner"
document_type: "tool-contract"
---

# Đặc tả tool domain kỹ thuật A2

Tài liệu này là contract để triển khai 14 tool của Technical Agent A2. Nguồn nghiệp vụ là `general.md`; nguồn dữ liệu và các invariant bảo mật là `DB_AI_Platform_Builder_Vinhomes_V3_Triage_Priority.md` cùng catalog tại `server/src/db/design/merged.json`.

Tài liệu không tạo migration và không khẳng định các adapter ngoài database đã tồn tại. Những phần ghi **adapter/mock POC** là interface cần hiện thực hoặc giả lập trước khi tool chạy end-to-end.

## 1. Quy ước chung

### 1.1. Execution context

Business input của tool không nhận `tenant_id`, role, actor hay quyền do model/client tự khai. Tool host phải lấy các giá trị sau từ runtime identity đã xác thực:

- `tenant_id`, `workspace_id`, `principal_id`, role và access scopes;
- `source_run_id`, `trace_id`, `agent_version`;
- `received_at` do server cấp theo UTC;
- capability grant cho đúng tool và resource.

Trước khi đọc hoặc ghi database, service xác minh resource thuộc cùng tenant, đúng building/scope và chạy trong database scope tương ứng. `building_id` trong business input chỉ là điều kiện chọn resource, không phải bằng chứng cấp quyền.

### 1.2. Request metadata

Tool host ghép metadata vào request nội bộ sau khi xác thực. Agent không được tự tạo hoặc ghi đè metadata này.

```json
{
  "$schema": "https://json-schema.org/draft/2020-12/schema",
  "$id": "a2://schemas/runtime-context.json",
  "type": "object",
  "additionalProperties": false,
  "required": ["tenant_id", "principal_id", "source_run_id", "trace_id", "agent_version", "received_at"],
  "properties": {
    "tenant_id": { "type": "string", "format": "uuid" },
    "workspace_id": { "type": "string", "format": "uuid" },
    "principal_id": { "type": "string", "minLength": 1 },
    "source_run_id": { "type": "string", "format": "uuid" },
    "trace_id": { "type": "string", "minLength": 1, "maxLength": 128 },
    "agent_version": { "type": "string", "minLength": 1, "maxLength": 128 },
    "received_at": { "type": "string", "format": "date-time" }
  }
}
```

### 1.3. Response envelope

Mọi tool trả cùng envelope. `data` tuân theo output schema riêng của tool. `missing_fields` chỉ dùng khi có thể tiếp tục sau khi bổ sung dữ liệu. Không đưa secret, credential, presigned URL hoặc nội dung suy luận nội bộ của model vào response/log.

```json
{
  "$schema": "https://json-schema.org/draft/2020-12/schema",
  "$id": "a2://schemas/response-envelope.json",
  "type": "object",
  "additionalProperties": false,
  "required": ["status", "trace_id", "server_time", "data", "errors", "missing_fields", "provenance"],
  "properties": {
    "status": {
      "enum": ["OK", "NEEDS_INPUT", "NOT_FOUND", "FORBIDDEN", "STALE_DATA", "CONFLICT", "PENDING_APPROVAL", "INTERNAL_ERROR"]
    },
    "trace_id": { "type": "string" },
    "server_time": { "type": "string", "format": "date-time" },
    "data": { "type": ["object", "array", "null"] },
    "errors": {
      "type": "array",
      "items": {
        "type": "object",
        "additionalProperties": false,
        "required": ["code", "message", "retryable"],
        "properties": {
          "code": {
            "enum": ["INVALID_INPUT", "NEEDS_INPUT", "NOT_FOUND", "FORBIDDEN", "STALE_DATA", "CONFLICT", "PENDING_APPROVAL", "INTERNAL_ERROR"]
          },
          "message": { "type": "string" },
          "field": { "type": "string" },
          "retryable": { "type": "boolean" }
        }
      }
    },
    "missing_fields": { "type": "array", "items": { "type": "string" }, "uniqueItems": true },
    "provenance": {
      "type": "array",
      "items": {
        "type": "object",
        "additionalProperties": false,
        "required": ["source_system", "retrieved_at"],
        "properties": {
          "source_system": { "type": "string" },
          "source_record_id": { "type": "string" },
          "source_version": { "type": ["string", "integer", "null"] },
          "retrieved_at": { "type": "string", "format": "date-time" }
        }
      }
    }
  }
}
```

### 1.4. Ghi dữ liệu, retry và thời gian

- Mọi write request có `idempotency_key`, unique trong phạm vi operation/resource. Retry cùng key và cùng payload trả kết quả cũ; cùng key nhưng payload khác trả `CONFLICT`.
- Không sửa đè measurement, executor result, maintenance event hoặc evidence đã xác nhận. Sửa sai bằng revision/superseding event có liên kết bản trước.
- `observed_at`, `measured_at` và `captured_at` là thời gian do nguồn cung cấp; `received_at`, `created_at` và `server_time` do server cấp. Không dùng thời gian nguồn làm bằng chứng duy nhất cho bảo mật hoặc thứ tự transaction.
- Read tool chỉ tự retry lỗi hạ tầng tạm thời. Write tool phải đối soát idempotency trước khi retry.
- Không có quyền luôn trả `FORBIDDEN`; không tiết lộ resource có tồn tại ở tenant/scope khác hay không.

## 2. Mapping dữ liệu

- `sop_kb.retrieve`: `knowledge_documents`, `document_versions`, `document_acl`, `document_scopes` và knowledge-base ACL. Chỉ đọc document `published`, active version đã duyệt/ingest và còn hiệu lực.
- `technical.get_active_outage`, `utility_schedule.read`: `service_interruptions` và `interruption_scopes`, join qua `work_orders`/`tickets` khi cần kiểm tra building và domain.
- `technical.submit_executor_result`, `technical.verify_resolution`: `tickets`, `work_orders`, `work_assignments`, `evidence_items`, `work_approvals`, `work_approval_evidence`, `ticket_events`.
- `utility_isolation.request`: với nước, transaction tạo `work_approvals(kind=management_water_shutdown,status=pending)` và `service_interruptions(status=proposed)`; không kích hoạt thiết bị. Với điện, `service_interruptions.utility=power` đã có nhưng enum approval chưa có loại cô lập điện tương ứng, nên phải đi qua shared approval adapter hoặc bổ sung schema ở đầu việc riêng, không dùng sai `customer_repair`.
- `asset.read`, `sensor.read`, `maintenance_history.read`, `maintenance_history.append`, `technical.record_measurement`: adapter/mock POC vì catalog hiện tại chưa có aggregate/bảng domain tương ứng.
- `area_restriction.request`, `apartment_entry.request`, `vendor_dispatch.request`: shared approval/request adapter. Không ép vào `work_approvals` vì enum `kind` hiện tại chưa biểu diễn ba nghiệp vụ này.
- Executor result hiện chưa có bảng riêng. POC có thể lưu qua adapter và liên kết `work_order_id`, `assignment_id`, evidence; không nhét toàn bộ result JSON vào `ticket_events`.

## 3. Tool tra cứu

### 3.1. `sop_kb.retrieve`

**Mô tả:** Tra SOP kỹ thuật và tiêu chí nghiệm thu theo issue code trong đúng tenant/building scope.

**Gọi khi:** đã có `issue_code`, building đã xác minh và cần hướng dẫn/tiêu chí nghiệm thu. **Không gọi để:** lấy draft, version hết hiệu lực hoặc tài liệu ngoài ACL.

**Quyền:** read-only; capability `sop:read`, document ACL allow và scope địa bàn đồng thời hợp lệ.

**Input schema**

```json
{
  "$schema": "https://json-schema.org/draft/2020-12/schema",
  "type": "object",
  "additionalProperties": false,
  "required": ["building_id", "issue_code", "query"],
  "properties": {
    "building_id": { "type": "string", "format": "uuid" },
    "issue_code": { "type": "string", "pattern": "^TECH\\.[A-Z]+\\.[A-Z0-9_]+$" },
    "query": { "type": "string", "minLength": 3, "maxLength": 1000 },
    "effective_at": { "type": "string", "format": "date-time" },
    "language": { "type": "string", "default": "vi" },
    "limit": { "type": "integer", "minimum": 1, "maximum": 20, "default": 5 }
  }
}
```

**Output data schema**

```json
{
  "type": "object",
  "additionalProperties": false,
  "required": ["documents"],
  "properties": {
    "documents": {
      "type": "array",
      "items": {
        "type": "object",
        "required": ["document_id", "code", "title", "version_no", "effective_from", "source_refs", "acceptance_criteria"],
        "properties": {
          "document_id": { "type": "string", "format": "uuid" },
          "code": { "type": "string" },
          "title": { "type": "string" },
          "version_no": { "type": "integer", "minimum": 1 },
          "effective_from": { "type": "string", "format": "date-time" },
          "effective_to": { "type": ["string", "null"], "format": "date-time" },
          "excerpt": { "type": "string" },
          "acceptance_criteria": { "type": "array", "items": { "type": "string" } },
          "source_refs": { "type": "array", "items": { "type": "string" } }
        }
      }
    }
  }
}
```

**Lỗi và retry:** `NEEDS_INPUT` nếu query không đủ rõ; `NOT_FOUND` nếu không có SOP hợp lệ; `FORBIDDEN` nếu ACL/scope không hợp lệ. Không fallback sang version draft/archived/hết hạn. Retry được khi lỗi đọc tạm thời.

**Ví dụ**

```json
{
  "request": { "building_id": "11111111-1111-4111-8111-111111111111", "issue_code": "TECH.HVAC.CONDENSATION", "query": "tiêu chí nghiệm thu sau xử lý nước ngưng", "limit": 3 },
  "response": { "status": "OK", "trace_id": "tr-a2-001", "server_time": "2026-09-30T09:00:00Z", "data": { "documents": [{ "document_id": "21111111-1111-4111-8111-111111111111", "code": "SOP-HVAC-012", "title": "Xử lý nước ngưng điều hòa", "version_no": 3, "effective_from": "2026-01-01T00:00:00Z", "effective_to": null, "excerpt": "Kiểm tra đường thoát và chụp ảnh sau xử lý.", "acceptance_criteria": ["Không còn rò tại thời điểm kiểm tra"], "source_refs": ["doc:SOP-HVAC-012:v3"] }] }, "errors": [], "missing_fields": [], "provenance": [{ "source_system": "knowledge_db", "source_record_id": "21111111-1111-4111-8111-111111111111", "source_version": 3, "retrieved_at": "2026-09-30T09:00:00Z" }] }
}
```

### 3.2. `asset.read`

**Mô tả:** Đọc hồ sơ tài sản/thiết bị theo ID hoặc vị trí. **Gọi khi:** cần xác định model, location, ownership, warranty hoặc status. **Không gọi để:** tự chọn một asset khi có nhiều kết quả phù hợp.

**Quyền:** read-only; capability `asset:read`, building scope hợp lệ. **Persistence:** asset adapter/mock POC.

**Input schema**

```json
{
  "$schema": "https://json-schema.org/draft/2020-12/schema",
  "type": "object",
  "additionalProperties": false,
  "required": ["building_id"],
  "properties": {
    "building_id": { "type": "string", "format": "uuid" },
    "asset_id": { "type": "string", "minLength": 1 },
    "location": { "type": "string", "minLength": 2, "maxLength": 500 },
    "asset_type": { "type": "string", "maxLength": 100 }
  },
  "oneOf": [{ "required": ["asset_id"] }, { "required": ["location"] }]
}
```

**Output data schema**

```json
{
  "type": "object",
  "required": ["assets"],
  "properties": {
    "assets": {
      "type": "array",
      "items": {
        "type": "object",
        "required": ["asset_id", "type", "location", "status", "updated_at"],
        "properties": {
          "asset_id": { "type": "string" },
          "type": { "type": "string" },
          "model": { "type": ["string", "null"] },
          "location": { "type": "string" },
          "ownership": { "type": ["string", "null"] },
          "warranty_until": { "type": ["string", "null"], "format": "date" },
          "status": { "type": "string" },
          "updated_at": { "type": "string", "format": "date-time" }
        }
      }
    }
  }
}
```

**Lỗi và retry:** zero match trả `NOT_FOUND`; nhiều match mà không thể phân biệt trả `NEEDS_INPUT` cùng danh sách candidate tối thiểu, không tự chọn. Retry được khi adapter timeout.

**Ví dụ**

```json
{
  "request": { "building_id": "11111111-1111-4111-8111-111111111111", "asset_id": "AC-A1-1205-01" },
  "response": { "status": "OK", "trace_id": "tr-a2-002", "server_time": "2026-09-30T09:01:00Z", "data": { "assets": [{ "asset_id": "AC-A1-1205-01", "type": "air_conditioner", "model": "ACME-X1", "location": "A1-1205/phòng khách", "ownership": "resident", "warranty_until": "2027-03-31", "status": "active", "updated_at": "2026-09-20T02:00:00Z" }] }, "errors": [], "missing_fields": [], "provenance": [{ "source_system": "asset_adapter", "source_record_id": "AC-A1-1205-01", "source_version": "etag-17", "retrieved_at": "2026-09-30T09:01:00Z" }] }
}
```

### 3.3. `sensor.read`

**Mô tả:** Đọc số đo BMS/IoT có timestamp, unit và quality. **Gọi khi:** cần dữ liệu vận hành hỗ trợ đánh giá. **Không gọi để:** kết luận an toàn từ dữ liệu stale hoặc chất lượng không đạt.

**Quyền:** read-only; capability `sensor:read`, building/asset scope hợp lệ. **Persistence:** sensor adapter/mock POC.

**Input schema**

```json
{
  "$schema": "https://json-schema.org/draft/2020-12/schema",
  "type": "object",
  "additionalProperties": false,
  "required": ["building_id", "metric", "time_range"],
  "properties": {
    "building_id": { "type": "string", "format": "uuid" },
    "sensor_id": { "type": "string" },
    "asset_id": { "type": "string" },
    "metric": { "type": "string", "minLength": 1, "maxLength": 100 },
    "time_range": {
      "type": "object",
      "additionalProperties": false,
      "required": ["from", "to"],
      "properties": { "from": { "type": "string", "format": "date-time" }, "to": { "type": "string", "format": "date-time" } }
    },
    "max_age_seconds": { "type": "integer", "minimum": 1, "maximum": 86400, "default": 900 }
  },
  "oneOf": [{ "required": ["sensor_id"] }, { "required": ["asset_id"] }]
}
```

**Output data schema**

```json
{
  "type": "object",
  "required": ["readings", "freshness"],
  "properties": {
    "freshness": { "enum": ["fresh", "stale", "unknown"] },
    "readings": {
      "type": "array",
      "items": {
        "type": "object",
        "required": ["sensor_id", "metric", "value", "unit", "observed_at", "quality"],
        "properties": {
          "sensor_id": { "type": "string" }, "asset_id": { "type": ["string", "null"] }, "metric": { "type": "string" },
          "value": { "type": "number" }, "unit": { "type": "string" }, "observed_at": { "type": "string", "format": "date-time" },
          "quality": { "enum": ["good", "uncertain", "bad", "unknown"] }
        }
      }
    }
  }
}
```

**Lỗi và retry:** dữ liệu quá `max_age_seconds` trả `STALE_DATA` nhưng vẫn có thể kèm readings để hiển thị; unit không tương thích hoặc quality `bad` không được dùng làm căn cứ xác minh. Retry được khi adapter timeout.

**Ví dụ**

```json
{
  "request": { "building_id": "11111111-1111-4111-8111-111111111111", "asset_id": "AC-A1-1205-01", "metric": "condensate_level", "time_range": { "from": "2026-09-30T08:00:00Z", "to": "2026-09-30T09:00:00Z" }, "max_age_seconds": 900 },
  "response": { "status": "OK", "trace_id": "tr-a2-003", "server_time": "2026-09-30T09:02:00Z", "data": { "freshness": "fresh", "readings": [{ "sensor_id": "SNS-009", "asset_id": "AC-A1-1205-01", "metric": "condensate_level", "value": 12.4, "unit": "mm", "observed_at": "2026-09-30T08:58:00Z", "quality": "good" }] }, "errors": [], "missing_fields": [], "provenance": [{ "source_system": "bms_adapter", "source_record_id": "SNS-009", "source_version": null, "retrieved_at": "2026-09-30T09:02:00Z" }] }
}
```

### 3.4. `maintenance_history.read`

**Mô tả:** Đọc sự kiện bảo trì và lỗi lặp của asset. Ghi chú cũ là lịch sử, không phải kết luận hiện tại.

**Quyền:** read-only; capability `maintenance:read`, asset/building scope hợp lệ. **Persistence:** maintenance adapter/mock POC.

**Input schema**

```json
{
  "$schema": "https://json-schema.org/draft/2020-12/schema",
  "type": "object",
  "additionalProperties": false,
  "required": ["building_id", "asset_id", "time_range"],
  "properties": {
    "building_id": { "type": "string", "format": "uuid" }, "asset_id": { "type": "string" },
    "time_range": { "type": "object", "required": ["from", "to"], "properties": { "from": { "type": "string", "format": "date-time" }, "to": { "type": "string", "format": "date-time" } } },
    "limit": { "type": "integer", "minimum": 1, "maximum": 100, "default": 20 }
  }
}
```

**Output data schema**

```json
{
  "type": "object",
  "required": ["events", "repeat_count"],
  "properties": {
    "events": { "type": "array", "items": { "type": "object", "required": ["event_id", "asset_id", "occurred_at", "outcome", "source_refs"], "properties": { "event_id": { "type": "string" }, "asset_id": { "type": "string" }, "incident_id": { "type": ["string", "null"] }, "workorder_id": { "type": ["string", "null"] }, "occurred_at": { "type": "string", "format": "date-time" }, "outcome": { "type": "string" }, "source_refs": { "type": "array", "items": { "type": "string" } } } } },
    "last_maintenance_at": { "type": ["string", "null"], "format": "date-time" },
    "repeat_count": { "type": "integer", "minimum": 0 }
  }
}
```

**Lỗi và retry:** `NOT_FOUND` khi asset không tồn tại; lịch sử rỗng trả `OK` với `events: []`. Retry được khi adapter timeout.

**Ví dụ**

```json
{
  "request": { "building_id": "11111111-1111-4111-8111-111111111111", "asset_id": "AC-A1-1205-01", "time_range": { "from": "2026-01-01T00:00:00Z", "to": "2026-09-30T09:00:00Z" } },
  "response": { "status": "OK", "trace_id": "tr-a2-004", "server_time": "2026-09-30T09:03:00Z", "data": { "events": [{ "event_id": "ME-102", "asset_id": "AC-A1-1205-01", "incident_id": "31111111-1111-4111-8111-111111111111", "workorder_id": "41111111-1111-4111-8111-111111111111", "occurred_at": "2026-07-02T04:00:00Z", "outcome": "cleaned_drain_line", "source_refs": ["workorder:41111111-1111-4111-8111-111111111111"] }], "last_maintenance_at": "2026-07-02T04:00:00Z", "repeat_count": 1 }, "errors": [], "missing_fields": [], "provenance": [{ "source_system": "maintenance_adapter", "source_record_id": "AC-A1-1205-01", "source_version": "rev-8", "retrieved_at": "2026-09-30T09:03:00Z" }] }
}
```

### 3.5. `technical.get_active_outage`

**Mô tả:** Tìm gián đoạn dịch vụ đang ảnh hưởng building tại thời điểm sự cố. Không tự suy đoán ETA.

**Quyền:** read-only; capability `interruption:read`, building scope hợp lệ. **DB:** `service_interruptions`, `interruption_scopes`.

**Input schema**

```json
{
  "$schema": "https://json-schema.org/draft/2020-12/schema",
  "type": "object", "additionalProperties": false,
  "required": ["building_id", "service_type", "occurred_at"],
  "properties": {
    "building_id": { "type": "string", "format": "uuid" },
    "service_type": { "enum": ["water", "power"] },
    "occurred_at": { "type": "string", "format": "date-time" }
  }
}
```

**Output data schema**

```json
{
  "type": "object", "required": ["outages"],
  "properties": { "outages": { "type": "array", "items": { "type": "object", "required": ["outage_id", "service_type", "status", "scope_ids", "started_at"], "properties": { "outage_id": { "type": "string", "format": "uuid" }, "service_type": { "enum": ["water", "power"] }, "status": { "enum": ["approved", "notified", "active", "restored"] }, "scope_ids": { "type": "array", "items": { "type": "string", "format": "uuid" } }, "started_at": { "type": "string", "format": "date-time" }, "ended_at": { "type": ["string", "null"], "format": "date-time" }, "published_eta": { "type": ["string", "null"], "format": "date-time" } } } } }
}
```

**Lỗi và retry:** chỉ trả outage có scope bao phủ building và status hợp lệ; không trả `proposed` như outage đang hoạt động. Không có kết quả trả `OK` với mảng rỗng. Retry được khi lỗi đọc tạm thời.

**Ví dụ**

```json
{
  "request": { "building_id": "11111111-1111-4111-8111-111111111111", "service_type": "water", "occurred_at": "2026-09-30T08:30:00Z" },
  "response": { "status": "OK", "trace_id": "tr-a2-005", "server_time": "2026-09-30T09:04:00Z", "data": { "outages": [{ "outage_id": "51111111-1111-4111-8111-111111111111", "service_type": "water", "status": "active", "scope_ids": ["11111111-1111-4111-8111-111111111111"], "started_at": "2026-09-30T08:00:00Z", "ended_at": null, "published_eta": null }] }, "errors": [], "missing_fields": [], "provenance": [{ "source_system": "application_db", "source_record_id": "51111111-1111-4111-8111-111111111111", "source_version": "2026-09-30T08:05:00Z", "retrieved_at": "2026-09-30T09:04:00Z" }] }
}
```

### 3.6. `utility_schedule.read`

**Mô tả:** Đọc lịch cắt điện/nước đã được phê duyệt hoặc công bố trong khoảng thời gian. Bỏ lịch cancelled và không coi proposal là lịch chính thức.

**Quyền:** read-only; capability `interruption:read`, building scope hợp lệ. **DB:** `service_interruptions`, `interruption_scopes`.

**Input schema**

```json
{
  "$schema": "https://json-schema.org/draft/2020-12/schema",
  "type": "object", "additionalProperties": false,
  "required": ["building_id", "utility_type", "time_range"],
  "properties": {
    "building_id": { "type": "string", "format": "uuid" }, "utility_type": { "enum": ["water", "power"] },
    "time_range": { "type": "object", "required": ["from", "to"], "properties": { "from": { "type": "string", "format": "date-time" }, "to": { "type": "string", "format": "date-time" } } }
  }
}
```

**Output data schema**

```json
{
  "type": "object", "required": ["schedules"],
  "properties": { "schedules": { "type": "array", "items": { "type": "object", "required": ["schedule_id", "utility_type", "status", "planned_start", "planned_end", "scope_ids"], "properties": { "schedule_id": { "type": "string", "format": "uuid" }, "utility_type": { "enum": ["water", "power"] }, "status": { "enum": ["approved", "notified", "active", "restored"] }, "planned_start": { "type": "string", "format": "date-time" }, "planned_end": { "type": "string", "format": "date-time" }, "scope_ids": { "type": "array", "items": { "type": "string", "format": "uuid" } } } } } }
}
```

**Lỗi và retry:** khoảng thời gian đảo ngược trả `INVALID_INPUT`; lịch hết hạn không giao với time range không được trả về. Retry được khi lỗi đọc tạm thời.

**Ví dụ**

```json
{
  "request": { "building_id": "11111111-1111-4111-8111-111111111111", "utility_type": "power", "time_range": { "from": "2026-10-01T00:00:00Z", "to": "2026-10-02T00:00:00Z" } },
  "response": { "status": "OK", "trace_id": "tr-a2-006", "server_time": "2026-09-30T09:05:00Z", "data": { "schedules": [{ "schedule_id": "61111111-1111-4111-8111-111111111111", "utility_type": "power", "status": "notified", "planned_start": "2026-10-01T02:00:00Z", "planned_end": "2026-10-01T04:00:00Z", "scope_ids": ["11111111-1111-4111-8111-111111111111"] }] }, "errors": [], "missing_fields": [], "provenance": [{ "source_system": "application_db", "source_record_id": "61111111-1111-4111-8111-111111111111", "source_version": "2026-09-29T07:00:00Z", "retrieved_at": "2026-09-30T09:05:00Z" }] }
}
```

## 4. Tool ghi nhận kết quả

### 4.1. `maintenance_history.append`

**Mô tả:** Append kết quả bảo trì đã được xác nhận vào lịch sử asset. **Không gọi khi:** executor result chưa được xác minh hoặc work order chưa thuộc asset/building.

**Quyền:** write; capability `maintenance:append`, staff assignment hợp lệ hoặc management đúng scope. **Persistence:** maintenance adapter/mock POC.

**Input schema**

```json
{
  "$schema": "https://json-schema.org/draft/2020-12/schema",
  "type": "object", "additionalProperties": false,
  "required": ["building_id", "asset_id", "workorder_id", "verified_result_id", "outcome", "source_refs", "idempotency_key"],
  "properties": {
    "building_id": { "type": "string", "format": "uuid" }, "asset_id": { "type": "string" },
    "workorder_id": { "type": "string", "format": "uuid" }, "verified_result_id": { "type": "string" },
    "outcome": { "type": "string", "minLength": 1, "maxLength": 4000 },
    "source_refs": { "type": "array", "minItems": 1, "uniqueItems": true, "items": { "type": "string" } },
    "occurred_at": { "type": "string", "format": "date-time" },
    "supersedes_event_id": { "type": "string" },
    "idempotency_key": { "type": "string", "minLength": 8, "maxLength": 128 }
  }
}
```

**Output data schema**

```json
{
  "type": "object", "required": ["maintenance_event_id", "created_at", "revision"],
  "properties": { "maintenance_event_id": { "type": "string" }, "created_at": { "type": "string", "format": "date-time" }, "revision": { "type": "integer", "minimum": 1 }, "supersedes_event_id": { "type": ["string", "null"] } }
}
```

**Tác động và lỗi:** append-only. Xác minh `verified_result_id`, work order, asset và actor trước ghi. Chưa VERIFIED trả `CONFLICT`; key trùng payload khác trả `CONFLICT`. Retry sau đối soát idempotency.

**Ví dụ**

```json
{
  "request": { "building_id": "11111111-1111-4111-8111-111111111111", "asset_id": "AC-A1-1205-01", "workorder_id": "41111111-1111-4111-8111-111111111111", "verified_result_id": "ER-9001", "outcome": "Đã vệ sinh đường thoát nước ngưng và kiểm tra không còn rò.", "source_refs": ["result:ER-9001", "evidence:EV-22"], "occurred_at": "2026-09-30T08:50:00Z", "idempotency_key": "mh-WO-4111-v1" },
  "response": { "status": "OK", "trace_id": "tr-a2-007", "server_time": "2026-09-30T09:06:00Z", "data": { "maintenance_event_id": "ME-103", "created_at": "2026-09-30T09:06:00Z", "revision": 1, "supersedes_event_id": null }, "errors": [], "missing_fields": [], "provenance": [{ "source_system": "maintenance_adapter", "source_record_id": "ME-103", "source_version": 1, "retrieved_at": "2026-09-30T09:06:00Z" }] }
}
```

### 4.2. `technical.record_measurement`

**Mô tả:** Ghi số đo do kỹ thuật viên hoặc thiết bị xác thực cung cấp. Agent không được tự tạo giá trị.

**Quyền:** write; capability `measurement:write`; technician phải có assignment hợp lệ, device phải map với asset/building. **Persistence:** measurement adapter/mock POC.

**Input schema**

```json
{
  "$schema": "https://json-schema.org/draft/2020-12/schema",
  "type": "object", "additionalProperties": false,
  "required": ["building_id", "workorder_id", "metric", "value", "unit", "measured_at", "measured_by", "source", "idempotency_key"],
  "properties": {
    "building_id": { "type": "string", "format": "uuid" }, "workorder_id": { "type": "string", "format": "uuid" },
    "asset_id": { "type": "string" }, "metric": { "type": "string", "minLength": 1, "maxLength": 100 },
    "value": { "type": "number" }, "unit": { "type": "string", "minLength": 1, "maxLength": 32 },
    "measured_at": { "type": "string", "format": "date-time" },
    "measured_by": { "type": "object", "additionalProperties": false, "required": ["kind", "source_id"], "properties": { "kind": { "enum": ["technician", "device"] }, "source_id": { "type": "string" } } },
    "source": { "enum": ["manual_entry", "instrument", "bms", "iot"] },
    "evidence_ids": { "type": "array", "uniqueItems": true, "items": { "type": "string" } },
    "idempotency_key": { "type": "string", "minLength": 8, "maxLength": 128 }
  }
}
```

**Output data schema**

```json
{
  "type": "object", "required": ["measurement_id", "metric", "normalized_value", "normalized_unit", "created_at"],
  "properties": { "measurement_id": { "type": "string" }, "metric": { "type": "string" }, "normalized_value": { "type": "number" }, "normalized_unit": { "type": "string" }, "created_at": { "type": "string", "format": "date-time" }, "quality_flags": { "type": "array", "items": { "type": "string" } } }
}
```

**Tác động và lỗi:** append-only; chuẩn hóa unit theo metric allowlist nhưng giữ raw input trong adapter audit. Actor/source không xác thực trả `FORBIDDEN`; unit không hợp lệ trả `INVALID_INPUT`. Retry sau đối soát idempotency.

**Ví dụ**

```json
{
  "request": { "building_id": "11111111-1111-4111-8111-111111111111", "workorder_id": "41111111-1111-4111-8111-111111111111", "asset_id": "AC-A1-1205-01", "metric": "drain_flow", "value": 1.2, "unit": "L/min", "measured_at": "2026-09-30T08:48:00Z", "measured_by": { "kind": "technician", "source_id": "staff-204" }, "source": "instrument", "evidence_ids": ["EV-22"], "idempotency_key": "measure-WO-4111-flow-1" },
  "response": { "status": "OK", "trace_id": "tr-a2-008", "server_time": "2026-09-30T09:07:00Z", "data": { "measurement_id": "MS-701", "metric": "drain_flow", "normalized_value": 1.2, "normalized_unit": "L/min", "created_at": "2026-09-30T09:07:00Z", "quality_flags": [] }, "errors": [], "missing_fields": [], "provenance": [{ "source_system": "measurement_adapter", "source_record_id": "MS-701", "source_version": 1, "retrieved_at": "2026-09-30T09:07:00Z" }] }
}
```

### 4.3. `technical.submit_executor_result`

**Mô tả:** Nhận checklist, số đo, vật tư và evidence từ kỹ thuật viên cho một work order. Không đồng nghĩa work order/ticket đã hoàn tất.

**Quyền:** write; capability `executor_result:submit`; executor phải là assignment được phép của work order hoặc management đúng scope. **DB/adapter:** đối chiếu `work_orders`, `work_assignments`, `evidence_items`; lưu result qua adapter riêng.

**Input schema**

```json
{
  "$schema": "https://json-schema.org/draft/2020-12/schema",
  "type": "object", "additionalProperties": false,
  "required": ["building_id", "workorder_id", "assignment_id", "checklist", "started_at", "completed_at", "idempotency_key"],
  "properties": {
    "building_id": { "type": "string", "format": "uuid" }, "workorder_id": { "type": "string", "format": "uuid" }, "assignment_id": { "type": "string", "format": "uuid" },
    "checklist": { "type": "array", "minItems": 1, "items": { "type": "object", "required": ["item_code", "status"], "properties": { "item_code": { "type": "string" }, "status": { "enum": ["passed", "failed", "not_applicable"] }, "note": { "type": "string" } } } },
    "measurement_ids": { "type": "array", "uniqueItems": true, "items": { "type": "string" } },
    "parts": { "type": "array", "items": { "type": "object", "required": ["name", "quantity"], "properties": { "name": { "type": "string" }, "quantity": { "type": "number", "exclusiveMinimum": 0 }, "unit": { "type": "string" } } } },
    "evidence_ids": { "type": "array", "uniqueItems": true, "items": { "type": "string" } },
    "diagnosis": { "type": "string", "maxLength": 4000 }, "repair_notes": { "type": "string", "maxLength": 8000 },
    "started_at": { "type": "string", "format": "date-time" }, "completed_at": { "type": "string", "format": "date-time" },
    "idempotency_key": { "type": "string", "minLength": 8, "maxLength": 128 }
  }
}
```

**Output data schema**

```json
{
  "type": "object", "required": ["result_id", "validation_status", "created_at"],
  "properties": { "result_id": { "type": "string" }, "validation_status": { "enum": ["ACCEPTED", "NEEDS_EVIDENCE", "HUMAN_REVIEW"] }, "created_at": { "type": "string", "format": "date-time" }, "missing_evidence": { "type": "array", "items": { "type": "string" } }, "conflicts": { "type": "array", "items": { "type": "string" } } }
}
```

**Tác động và lỗi:** validate assignment, work order version, evidence active/ready và quan hệ cùng ticket. Evidence chưa ready trả `CONFLICT` hoặc `NEEDS_INPUT`; không giả completion. Retry sau đối soát idempotency.

**Ví dụ**

```json
{
  "request": { "building_id": "11111111-1111-4111-8111-111111111111", "workorder_id": "41111111-1111-4111-8111-111111111111", "assignment_id": "71111111-1111-4111-8111-111111111111", "checklist": [{ "item_code": "DRAIN_CLEAR", "status": "passed", "note": "Dòng thoát ổn định" }], "measurement_ids": ["MS-701"], "parts": [], "evidence_ids": ["EV-21", "EV-22"], "diagnosis": "Tắc nhẹ đường nước ngưng", "repair_notes": "Đã vệ sinh và thử tải", "started_at": "2026-09-30T08:20:00Z", "completed_at": "2026-09-30T08:55:00Z", "idempotency_key": "executor-WO-4111-v1" },
  "response": { "status": "OK", "trace_id": "tr-a2-009", "server_time": "2026-09-30T09:08:00Z", "data": { "result_id": "ER-9001", "validation_status": "ACCEPTED", "created_at": "2026-09-30T09:08:00Z", "missing_evidence": [], "conflicts": [] }, "errors": [], "missing_fields": [], "provenance": [{ "source_system": "executor_result_adapter", "source_record_id": "ER-9001", "source_version": 1, "retrieved_at": "2026-09-30T09:08:00Z" }] }
}
```

## 5. Tool xác minh

### 5.1. `technical.verify_resolution`

**Mô tả:** Đối chiếu executor result, SOP, checklist và evidence để đưa ra khuyến nghị nghiệm thu. Tool không chuyển ticket/work order sang `completed` hoặc `closed`.

**Quyền:** read-only đối với trạng thái nghiệp vụ; capability `resolution:verify`, quyền đọc ticket/work order/evidence/SOP đúng scope.

**Input schema**

```json
{
  "$schema": "https://json-schema.org/draft/2020-12/schema",
  "type": "object", "additionalProperties": false,
  "required": ["building_id", "incident_id", "workorder_id", "result_id"],
  "properties": {
    "building_id": { "type": "string", "format": "uuid" }, "incident_id": { "type": "string", "format": "uuid" },
    "workorder_id": { "type": "string", "format": "uuid" }, "result_id": { "type": "string" },
    "sop_document_ids": { "type": "array", "uniqueItems": true, "items": { "type": "string", "format": "uuid" } }
  }
}
```

**Output data schema**

```json
{
  "type": "object", "required": ["verification_status", "checks", "required_actions", "source_refs"],
  "properties": {
    "verification_status": { "enum": ["VERIFIED", "NEEDS_EVIDENCE", "HUMAN_REVIEW"] },
    "checks": { "type": "array", "items": { "type": "object", "required": ["criterion", "status"], "properties": { "criterion": { "type": "string" }, "status": { "enum": ["passed", "failed", "unknown", "conflict"] }, "source_refs": { "type": "array", "items": { "type": "string" } } } } },
    "required_actions": { "type": "array", "items": { "type": "string" } },
    "source_refs": { "type": "array", "minItems": 1, "items": { "type": "string" } }
  }
}
```

**Quy tắc kết luận:** `VERIFIED` chỉ khi mọi tiêu chí bắt buộc có evidence/SOP hợp lệ; `NEEDS_EVIDENCE` khi thiếu ảnh, measurement hoặc checklist; `HUMAN_REVIEW` khi nguồn mâu thuẫn, SOP thiếu/hết hiệu lực hoặc cần phán đoán chuyên môn. Kết quả không tự đóng hồ sơ và không ghi maintenance history.

**Ví dụ**

```json
{
  "request": { "building_id": "11111111-1111-4111-8111-111111111111", "incident_id": "31111111-1111-4111-8111-111111111111", "workorder_id": "41111111-1111-4111-8111-111111111111", "result_id": "ER-9001", "sop_document_ids": ["21111111-1111-4111-8111-111111111111"] },
  "response": { "status": "OK", "trace_id": "tr-a2-010", "server_time": "2026-09-30T09:09:00Z", "data": { "verification_status": "VERIFIED", "checks": [{ "criterion": "Không còn rò tại thời điểm kiểm tra", "status": "passed", "source_refs": ["evidence:EV-22", "measurement:MS-701"] }], "required_actions": ["Chuyển người có thẩm quyền xác nhận hoàn tất"], "source_refs": ["result:ER-9001", "doc:SOP-HVAC-012:v3"] }, "errors": [], "missing_fields": [], "provenance": [{ "source_system": "application_db", "source_record_id": "41111111-1111-4111-8111-111111111111", "source_version": 4, "retrieved_at": "2026-09-30T09:09:00Z" }] }
}
```

## 6. Tool tạo yêu cầu có rủi ro

Mọi tool trong nhóm này chỉ tạo request `PENDING_APPROVAL`. Agent không được tự phê duyệt, kích hoạt thiết bị, mở khóa, vào căn hộ, gọi nhà thầu hoặc cam kết chi phí.

### 6.1. `utility_isolation.request`

**Mô tả:** Đề nghị cô lập nước/điện trong phạm vi và thời gian xác định.

**Quyền:** write; capability `utility_isolation:request`; ticket/work order và evidence cùng scope. **DB:** nhánh nước dùng `work_approvals` + `service_interruptions` + `interruption_scopes` trong một transaction, kèm event/outbox theo service. Nhánh điện dùng shared approval adapter cho đến khi database có approval kind đúng nghĩa.

**Input schema**

```json
{
  "$schema": "https://json-schema.org/draft/2020-12/schema",
  "type": "object", "additionalProperties": false,
  "required": ["building_id", "incident_id", "workorder_id", "utility_type", "scope_ids", "reason", "planned_start", "planned_end", "evidence_ids", "idempotency_key"],
  "properties": {
    "building_id": { "type": "string", "format": "uuid" }, "incident_id": { "type": "string", "format": "uuid" }, "workorder_id": { "type": "string", "format": "uuid" },
    "utility_type": { "enum": ["water", "power"] }, "scope_ids": { "type": "array", "minItems": 1, "uniqueItems": true, "items": { "type": "string", "format": "uuid" } },
    "reason": { "type": "string", "minLength": 10, "maxLength": 2000 }, "planned_start": { "type": "string", "format": "date-time" }, "planned_end": { "type": "string", "format": "date-time" },
    "evidence_ids": { "type": "array", "minItems": 1, "uniqueItems": true, "items": { "type": "string" } },
    "idempotency_key": { "type": "string", "minLength": 8, "maxLength": 128 }
  }
}
```

**Output data schema**

```json
{
  "type": "object", "required": ["request_id", "interruption_id", "approval_status", "created_at"],
  "properties": { "request_id": { "type": "string", "format": "uuid" }, "interruption_id": { "type": "string", "format": "uuid" }, "approval_status": { "const": "PENDING_APPROVAL" }, "required_scope_id": { "type": "string", "format": "uuid" }, "created_at": { "type": "string", "format": "date-time" } }
}
```

**Tác động và lỗi:** với nước, tạo approval `management_water_shutdown/pending` và interruption `proposed`; với điện, tạo approval qua adapter rồi liên kết interruption `proposed`. `planned_end` phải sau `planned_start`. Chỉ service có thẩm quyền mới chuyển interruption sang active sau approval. Retry sau đối soát idempotency.

**Ví dụ**

```json
{
  "request": { "building_id": "11111111-1111-4111-8111-111111111111", "incident_id": "31111111-1111-4111-8111-111111111111", "workorder_id": "41111111-1111-4111-8111-111111111111", "utility_type": "water", "scope_ids": ["11111111-1111-4111-8111-111111111111"], "reason": "Cần khóa nước để xử lý rò đường ống chính", "planned_start": "2026-09-30T10:00:00Z", "planned_end": "2026-09-30T11:00:00Z", "evidence_ids": ["EV-31"], "idempotency_key": "isolate-WO-4111-v1" },
  "response": { "status": "PENDING_APPROVAL", "trace_id": "tr-a2-011", "server_time": "2026-09-30T09:10:00Z", "data": { "request_id": "81111111-1111-4111-8111-111111111111", "interruption_id": "91111111-1111-4111-8111-111111111111", "approval_status": "PENDING_APPROVAL", "required_scope_id": "11111111-1111-4111-8111-111111111111", "created_at": "2026-09-30T09:10:00Z" }, "errors": [], "missing_fields": [], "provenance": [{ "source_system": "application_db", "source_record_id": "81111111-1111-4111-8111-111111111111", "source_version": 1, "retrieved_at": "2026-09-30T09:10:00Z" }] }
}
```

### 6.2. `area_restriction.request`

**Mô tả:** Đề nghị rào chắn/hạn chế một khu vực có hazard; không tự khóa cửa hay dừng thiết bị.

**Quyền:** write; capability `area_restriction:request`, ticket/building scope hợp lệ. **Persistence:** shared approval/request adapter; DB hiện chưa có request kind phù hợp.

**Input schema**

```json
{
  "$schema": "https://json-schema.org/draft/2020-12/schema",
  "type": "object", "additionalProperties": false,
  "required": ["building_id", "incident_id", "area", "hazard", "reason", "evidence_ids", "idempotency_key"],
  "properties": {
    "building_id": { "type": "string", "format": "uuid" }, "incident_id": { "type": "string", "format": "uuid" }, "workorder_id": { "type": "string", "format": "uuid" },
    "area": { "type": "string", "minLength": 2, "maxLength": 500 }, "hazard": { "type": "string", "minLength": 3, "maxLength": 1000 }, "reason": { "type": "string", "minLength": 10, "maxLength": 2000 },
    "requested_until": { "type": "string", "format": "date-time" }, "evidence_ids": { "type": "array", "minItems": 1, "uniqueItems": true, "items": { "type": "string" } },
    "idempotency_key": { "type": "string", "minLength": 8, "maxLength": 128 }
  }
}
```

**Output data schema**

```json
{
  "type": "object", "required": ["request_id", "approval_status", "created_at"],
  "properties": { "request_id": { "type": "string" }, "approval_status": { "const": "PENDING_APPROVAL" }, "required_approver_scope": { "type": "string" }, "created_at": { "type": "string", "format": "date-time" } }
}
```

**Tác động và lỗi:** adapter phải xác minh evidence thuộc incident và không thi hành hạn chế trước approval. Key trùng payload khác trả `CONFLICT`.

**Ví dụ**

```json
{
  "request": { "building_id": "11111111-1111-4111-8111-111111111111", "incident_id": "31111111-1111-4111-8111-111111111111", "area": "Hành lang tầng 12, tháp A1", "hazard": "Mảng trần có dấu hiệu võng", "reason": "Hạn chế người qua lại đến khi kỹ sư kết cấu kiểm tra", "requested_until": "2026-09-30T15:00:00Z", "evidence_ids": ["EV-41"], "idempotency_key": "restrict-INC-3111-v1" },
  "response": { "status": "PENDING_APPROVAL", "trace_id": "tr-a2-012", "server_time": "2026-09-30T09:11:00Z", "data": { "request_id": "AR-1001", "approval_status": "PENDING_APPROVAL", "required_approver_scope": "building_management", "created_at": "2026-09-30T09:11:00Z" }, "errors": [], "missing_fields": [], "provenance": [{ "source_system": "approval_adapter", "source_record_id": "AR-1001", "source_version": 1, "retrieved_at": "2026-09-30T09:11:00Z" }] }
}
```

### 6.3. `apartment_entry.request`

**Mô tả:** Xin quyền vào căn hộ vắng chủ sau khi có lý do nghiệp vụ và lịch sử liên hệ. Tool không nhận/trả mã khóa hoặc credential.

**Quyền:** write; capability `apartment_entry:request`, incident và unit cùng tenant/building. **Persistence:** shared approval/request adapter; DB hiện chưa có request kind phù hợp.

**Input schema**

```json
{
  "$schema": "https://json-schema.org/draft/2020-12/schema",
  "type": "object", "additionalProperties": false,
  "required": ["building_id", "incident_id", "unit_id", "reason", "contact_attempts", "idempotency_key"],
  "properties": {
    "building_id": { "type": "string", "format": "uuid" }, "incident_id": { "type": "string", "format": "uuid" }, "unit_id": { "type": "string", "format": "uuid" },
    "reason": { "type": "string", "minLength": 10, "maxLength": 2000 },
    "contact_attempts": { "type": "array", "minItems": 1, "items": { "type": "object", "required": ["channel", "attempted_at", "outcome"], "properties": { "channel": { "enum": ["phone", "message", "app", "other"] }, "attempted_at": { "type": "string", "format": "date-time" }, "outcome": { "enum": ["no_answer", "delivered", "rejected", "approved", "unknown"] }, "reference_id": { "type": "string" } } } },
    "requested_window": { "type": "object", "required": ["from", "to"], "properties": { "from": { "type": "string", "format": "date-time" }, "to": { "type": "string", "format": "date-time" } } },
    "evidence_ids": { "type": "array", "uniqueItems": true, "items": { "type": "string" } },
    "idempotency_key": { "type": "string", "minLength": 8, "maxLength": 128 }
  }
}
```

**Output data schema**

```json
{
  "type": "object", "required": ["request_id", "approval_status", "required_approvals", "created_at"],
  "properties": { "request_id": { "type": "string" }, "approval_status": { "const": "PENDING_APPROVAL" }, "required_approvals": { "type": "array", "minItems": 1, "items": { "type": "string" } }, "created_at": { "type": "string", "format": "date-time" } }
}
```

**Tác động và lỗi:** chỉ lưu reference lịch sử liên hệ cần thiết, không sao chép credential/nội dung nhạy cảm vào request. Unit khác building hoặc không có quyền trả `FORBIDDEN`.

**Ví dụ**

```json
{
  "request": { "building_id": "11111111-1111-4111-8111-111111111111", "incident_id": "31111111-1111-4111-8111-111111111111", "unit_id": "a1111111-1111-4111-8111-111111111111", "reason": "Cần kiểm tra nguồn rò có thể ảnh hưởng căn phía dưới", "contact_attempts": [{ "channel": "app", "attempted_at": "2026-09-30T08:00:00Z", "outcome": "delivered", "reference_id": "msg-880" }, { "channel": "phone", "attempted_at": "2026-09-30T08:30:00Z", "outcome": "no_answer" }], "requested_window": { "from": "2026-09-30T10:00:00Z", "to": "2026-09-30T12:00:00Z" }, "evidence_ids": ["EV-51"], "idempotency_key": "entry-INC-3111-unit-a-v1" },
  "response": { "status": "PENDING_APPROVAL", "trace_id": "tr-a2-013", "server_time": "2026-09-30T09:12:00Z", "data": { "request_id": "AE-1001", "approval_status": "PENDING_APPROVAL", "required_approvals": ["resident_or_authorized_management"], "created_at": "2026-09-30T09:12:00Z" }, "errors": [], "missing_fields": [], "provenance": [{ "source_system": "approval_adapter", "source_record_id": "AE-1001", "source_version": 1, "retrieved_at": "2026-09-30T09:12:00Z" }] }
}
```

### 6.4. `vendor_dispatch.request`

**Mô tả:** Đề nghị điều động nhà thầu ngoài khi cần chuyên môn/năng lực chưa có. Tool không tự gọi nhà thầu, đặt lịch hay cam kết chi phí.

**Quyền:** write; capability `vendor_dispatch:request`, incident/work order scope hợp lệ. **Persistence:** vendor/shared approval adapter; DB hiện chưa có request aggregate phù hợp.

**Input schema**

```json
{
  "$schema": "https://json-schema.org/draft/2020-12/schema",
  "type": "object", "additionalProperties": false,
  "required": ["building_id", "incident_id", "service", "reason", "urgency", "idempotency_key"],
  "properties": {
    "building_id": { "type": "string", "format": "uuid" }, "incident_id": { "type": "string", "format": "uuid" }, "workorder_id": { "type": "string", "format": "uuid" },
    "service": { "type": "string", "minLength": 2, "maxLength": 200 }, "reason": { "type": "string", "minLength": 10, "maxLength": 2000 },
    "urgency": { "enum": ["routine", "soon", "immediate"] }, "required_specialty_code": { "type": "string", "maxLength": 100 },
    "evidence_ids": { "type": "array", "uniqueItems": true, "items": { "type": "string" } },
    "idempotency_key": { "type": "string", "minLength": 8, "maxLength": 128 }
  }
}
```

**Output data schema**

```json
{
  "type": "object", "required": ["request_id", "approval_status", "eligible_vendors", "created_at"],
  "properties": { "request_id": { "type": "string" }, "approval_status": { "const": "PENDING_APPROVAL" }, "eligible_vendors": { "type": "array", "items": { "type": "object", "required": ["vendor_id", "display_name", "qualification_status"], "properties": { "vendor_id": { "type": "string" }, "display_name": { "type": "string" }, "qualification_status": { "enum": ["eligible", "needs_review"] } } } }, "created_at": { "type": "string", "format": "date-time" } }
}
```

**Tác động và lỗi:** candidate list chỉ là kết quả matching; không tạo booking/contract/payment. `immediate` không tự biến thành priority chính thức và không vượt quy trình emergency/triage. Retry sau đối soát idempotency.

**Ví dụ**

```json
{
  "request": { "building_id": "11111111-1111-4111-8111-111111111111", "incident_id": "31111111-1111-4111-8111-111111111111", "workorder_id": "41111111-1111-4111-8111-111111111111", "service": "Kiểm định vết nứt kết cấu", "reason": "Cần kỹ sư kết cấu có chứng chỉ đánh giá tại hiện trường", "urgency": "soon", "required_specialty_code": "STRUCTURAL_ENGINEER", "evidence_ids": ["EV-61"], "idempotency_key": "vendor-INC-3111-v1" },
  "response": { "status": "PENDING_APPROVAL", "trace_id": "tr-a2-014", "server_time": "2026-09-30T09:13:00Z", "data": { "request_id": "VD-1001", "approval_status": "PENDING_APPROVAL", "eligible_vendors": [{ "vendor_id": "VEN-21", "display_name": "Đơn vị kiểm định A", "qualification_status": "eligible" }], "created_at": "2026-09-30T09:13:00Z" }, "errors": [], "missing_fields": [], "provenance": [{ "source_system": "vendor_adapter", "source_record_id": "VD-1001", "source_version": 1, "retrieved_at": "2026-09-30T09:13:00Z" }] }
}
```

## 7. Error contract và transaction

- `INVALID_INPUT`: schema hoặc ràng buộc chéo trường sai; không retry nếu request không đổi.
- `NEEDS_INPUT`: thiếu dữ kiện nghiệp vụ hoặc có nhiều candidate; trả `missing_fields`, không tự đoán.
- `NOT_FOUND`: không tìm thấy resource trong scope được phép. Resource ngoài scope trả `FORBIDDEN`, không xác nhận sự tồn tại.
- `FORBIDDEN`: identity/capability/tenant/building/scope không hợp lệ; ghi security audit phù hợp.
- `STALE_DATA`: dữ liệu nguồn quá cũ để kết luận; có thể đọc để tham khảo nhưng phải gắn freshness.
- `CONFLICT`: version, trạng thái, evidence, assignment hoặc idempotency không còn phù hợp; caller đọc lại state trước retry.
- `PENDING_APPROVAL`: request đã được tạo, chưa có hành động thực địa.
- `INTERNAL_ERROR`: lỗi hạ tầng không lộ chi tiết nhạy cảm; read có thể retry backoff, write phải đối soát key.

Write tool phải commit record, audit event và outbox cần thiết trong cùng transaction nếu chúng nằm cùng database. Side effect ngoài DB chạy sau commit và dedupe theo operation key; không tuyên bố exactly-once I/O.

## 8. Kiểm thử và nghiệm thu contract

Tối thiểu phải có contract test cho từng tool và các kịch bản sau:

1. Validate happy path request/response theo JSON Schema và từ chối additional property.
2. Thiếu required field trả `INVALID_INPUT` hoặc `NEEDS_INPUT` đúng ngữ cảnh.
3. Resource thuộc tenant/building khác trả `FORBIDDEN` và không lộ dữ liệu.
4. `asset.read` nhiều match trả `NEEDS_INPUT`, không tự chọn.
5. SOP draft, archived hoặc hết hiệu lực không xuất hiện trong kết quả.
6. Sensor stale/bad quality không được dùng để kết luận an toàn.
7. Retry write cùng key/cùng payload trả cùng ID; cùng key/khác payload trả `CONFLICT`.
8. Evidence chưa ready, withdrawn hoặc khác ticket không được chấp nhận.
9. Executor result có assignment sai hoặc timestamp đảo ngược bị từ chối.
10. `maintenance_history.append` từ result chưa VERIFIED bị từ chối và không tạo event.
11. `technical.verify_resolution` trả đúng ba giá trị `VERIFIED`, `NEEDS_EVIDENCE`, `HUMAN_REVIEW` và không đổi trạng thái ticket/work order.
12. Bốn request rủi ro luôn trả `PENDING_APPROVAL`; không tạo side effect vật lý.
13. Isolation nước tạo approval pending và interruption proposed nguyên tử; isolation điện dùng approval adapter cho đến khi có DB kind tương ứng; cả hai không thể active khi approval chưa approved.
14. Response/log không chứa token, credential, presigned URL, mã khóa hoặc chain-of-thought.

## 9. Definition of Done khi code tool

- Tool implementation sinh từ hoặc tương thích với schema trong tài liệu này và dùng validation runtime như Zod.
- Authorization lấy từ execution context, không lấy tenant/role/actor từ business input.
- DB query có tenant + scope guard; adapter ngoài có mapping identity/scope tương đương.
- Write operation có idempotency, audit, version/conflict handling và test retry.
- Provenance đủ để truy ngược nguồn/version nhưng không chứa secret.
- Các adapter/mock POC được gắn nhãn rõ và có contract test giống production adapter.
- Domain Owner xác nhận field nghiệp vụ, unit allowlist, ngưỡng stale, approval routing và năm luồng POC trước khi bật production.
