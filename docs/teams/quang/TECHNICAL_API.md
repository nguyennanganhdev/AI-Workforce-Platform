# API Endpoint cho Technical Agent A2

Tài liệu tham chiếu HTTP cho Technical Agent A2 dùng **14 technical tool** ([catalog tool](tools.md)). Chuyển từ `my-docs/rag/endpoint_call_technical_tool.md` ngày 04/10/2026 để tập trung tài liệu vào `docs`.

Phần contract và kết quả kiểm tra bên dưới được ghi nhận ngày 02/10/2026; số test và dữ liệu seed là bằng chứng tại thời điểm đó, không phải kiểm tra lại hôm nay. Khi sửa API, đối chiếu [routes](../../../server/src/technical-api/routes.ts), [runtime](../../../server/src/technical-api/runtime.ts) và [database adapter](../../../server/src/technical-api/database.ts).

Logic của từng tool đã có sẵn trong `server/src/technical-tools/` (Team Quang). Mỗi endpoint chỉ cần:

1. Gom path param, query param và body thành `args` của tool.
2. Gọi tool tương ứng qua host của Team Quang.
3. Trả về envelope của tool, kèm HTTP status đúng bảng ở mục 2.4.

---

## 1. Tổng quan

### 1.1. Base URL

```text
https://<domain>/api/technical/v1
```

Ví dụ local: `http://localhost:3001/api/technical/v1`

### 1.2. Danh sách endpoint

| # | Method | Path | Tool | Mục đích |
|:---:|---|---|---|---|
| 0 | `GET` | `/tools` | — | Danh mục 14 tool, kèm JSON Schema |
| 1 | `GET` | `/buildings/{building_id}/outages/active` | `technical.get_active_outage` | Có đang cúp điện/nước tại thời điểm sự cố không |
| 2 | `GET` | `/buildings/{building_id}/utility-schedules` | `utility_schedule.read` | Lịch cúp điện/nước trong khoảng thời gian |
| 3 | `GET` | `/buildings/{building_id}/sops` | `sop_kb.retrieve` | Tra SOP đã duyệt theo mã sự cố |
| 4 | `GET` | `/buildings/{building_id}/assets` | `asset.read` | Tìm thiết bị theo mã hoặc vị trí |
| 5 | `GET` | `/buildings/{building_id}/sensor-readings` | `sensor.read` | Số đo cảm biến |
| 6 | `GET` | `/buildings/{building_id}/assets/{asset_id}/maintenance-history` | `maintenance_history.read` | Lịch sử bảo trì thiết bị |
| 7 | `POST` | `/buildings/{building_id}/work-orders/{workorder_id}/measurements` | `technical.record_measurement` | Ghi số đo |
| 8 | `POST` | `/buildings/{building_id}/work-orders/{workorder_id}/executor-results` | `technical.submit_executor_result` | Nộp kết quả công việc |
| 9 | `POST` | `/buildings/{building_id}/work-orders/{workorder_id}/executor-results/{result_id}/verification` | `technical.verify_resolution` | Xác minh kết quả (chỉ đọc, không ghi) |
| 10 | `POST` | `/buildings/{building_id}/assets/{asset_id}/maintenance-events` | `maintenance_history.append` | Ghi lịch sử bảo trì |
| 11 | `POST` | `/buildings/{building_id}/utility-isolation-requests` | `utility_isolation.request` | Đề nghị khóa nước/cắt điện |
| 12 | `POST` | `/buildings/{building_id}/area-restriction-requests` | `area_restriction.request` | Đề nghị rào chắn khu vực |
| 13 | `POST` | `/buildings/{building_id}/apartment-entry-requests` | `apartment_entry.request` | Xin vào căn hộ vắng chủ |
| 14 | `POST` | `/buildings/{building_id}/vendor-dispatch-requests` | `vendor_dispatch.request` | Đề nghị gọi nhà thầu ngoài |

Không có `PUT`, `PATCH` hay `DELETE`:
- Dữ liệu kỹ thuật **chỉ thêm, không sửa, không xóa** (`tools.md` §1.4). Sửa sai bằng một bản ghi mới thay bản cũ (ví dụ `supersedes_event_id`).
- Agent **không được** duyệt, hủy hay thực hiện đề nghị. Việc đó thuộc service phê duyệt của người có thẩm quyền, không nằm trong API này.

`#9` dùng `POST` dù không ghi gì, vì body có thể chứa danh sách SOP dài và kết quả được tính lại mỗi lần gọi.

---

## 2. Quy ước chung

### 2.1. Header bắt buộc

| Header | Bắt buộc | Ý nghĩa |
|---|---|---|
| `X-OpenBot-Agent-Token` | Mọi endpoint | Token của agent. Dùng cùng cơ chế với `/api/agent-tools/call` hiện có |
| `X-OpenBot-Run` | Mọi endpoint | Run assertion đã ký: Bot nào, chạy thay ai |
| `Idempotency-Key` | Mọi `POST` trừ `#9` | 8–128 ký tự. Gửi lại cùng khóa + cùng body thì nhận lại kết quả cũ, không ghi lần hai |
| `Content-Type: application/json` | Mọi `POST` | |

**Không bao giờ** nhận `tenant_id`, `user_id`, `role` hay quyền từ path, query hoặc body. Backend lấy các thông tin đó từ `X-OpenBot-Run` đã xác minh. Body có trường lạ thì trả `400 INVALID_INPUT`.

### 2.2. Định dạng thời gian và id

- Thời gian: ISO 8601 có múi giờ, ví dụ `2026-09-30T08:30:00Z` hoặc `2026-09-30T15:30:00+07:00`.
- `building_id`, `workorder_id`, `incident_id`, `unit_id`, `scope_id`: UUID.
- `asset_id`, `sensor_id`, `result_id`: chuỗi.

### 2.3. Response chung (envelope)

Mọi endpoint, kể cả khi lỗi, trả cùng một dạng:

```json
{
  "status": "OK",
  "trace_id": "tr-a2-005",
  "server_time": "2026-09-30T09:04:00Z",
  "data": { },
  "errors": [],
  "missing_fields": [],
  "provenance": [
    { "source_system": "application_db", "source_record_id": "…", "source_version": 1, "retrieved_at": "2026-09-30T09:04:00Z" }
  ]
}
```

Khi lỗi:

```json
{
  "status": "CONFLICT",
  "trace_id": "tr-a2-009",
  "server_time": "2026-09-30T09:08:00Z",
  "data": null,
  "errors": [
    { "code": "CONFLICT", "message": "evidence … is an upload that has not been registered as evidence (file staged)", "field": "evidence_ids", "retryable": false }
  ],
  "missing_fields": [],
  "provenance": []
}
```

### 2.4. Ánh xạ `status` → HTTP status code

| `status` trong envelope | HTTP | Agent nên làm gì |
|---|:---:|---|
| `OK` | `200` (`201` cho `POST` tạo bản ghi: `#7`, `#8`, `#10`) | Dùng `data` |
| `STALE_DATA` | `200` | Hiển thị được, không dùng để kết luận an toàn |
| `NEEDS_INPUT` | `200` | Hỏi thêm theo `missing_fields` |
| `PENDING_APPROVAL` | `202` | Báo đang chờ duyệt; không nói là đã làm |
| `INVALID_INPUT` | `400` | Sửa request |
| `FORBIDDEN` | `403` | Dừng. Cùng một câu cho mọi lý do, không tiết lộ tài nguyên có tồn tại hay không |
| `NOT_FOUND` | `404` | Không đoán |
| `CONFLICT` | `409` | Đọc lại trạng thái; nếu `retryable: true` thì chờ rồi gửi lại cùng `Idempotency-Key` |
| `INTERNAL_ERROR` | `500` | `GET`: thử lại. `POST`: gửi lại cùng `Idempotency-Key` để đối soát |

### 2.5. Gửi lại (idempotency)

| Tình huống | Kết quả |
|---|---|
| Cùng `Idempotency-Key`, cùng body, lần trước đã thành công | Trả lại đúng response cũ, không ghi lần hai |
| Cùng khóa, lần trước vẫn đang chạy | `409`, `retryable: true` |
| Cùng khóa, lần trước bị từ chối (`400`, `403`, `404`, `409` nghiệp vụ) | Được dùng lại khóa sau khi sửa body |
| Cùng khóa, body khác | `409`, `retryable: false`, phải dùng khóa mới |

Không cần endpoint `reconcile` riêng: muốn đối soát thì gửi lại đúng request cũ.

---

## 3. Chi tiết từng endpoint

### 0. Danh mục tool

```http
GET /api/technical/v1/tools
```

**Response `200`:**

```json
{
  "tools": [
    {
      "name": "technical.record_measurement",
      "model_name": "technical__record_measurement",
      "version": "1.0.0",
      "description": "Record a measurement a technician took on site …",
      "side_effect": "write",
      "required_capability": "measurement:write",
      "timeout_ms": 5000,
      "requires_idempotency_key": true,
      "input_schema": { "type": "object", "…": "…" },
      "output_schema": { "type": "object", "…": "…" }
    }
  ]
}
```

Cài đặt: trả `describeTechnicalTools()` từ module `technical-tools`.

---

### 1. Lịch cúp điện/nước tại thời điểm sự cố

```http
GET /api/technical/v1/buildings/{building_id}/outages/active?service_type=water&occurred_at=2026-09-30T08:30:00Z
```

| Query | Bắt buộc | Kiểu |
|---|:---:|---|
| `service_type` | ✔ | `water` \| `power` |
| `occurred_at` | ✔ | thời gian |

**Response `200`:**

```json
{
  "status": "OK",
  "data": {
    "outages": [
      {
        "outage_id": "51111111-1111-4111-8111-111111111111",
        "service_type": "water",
        "status": "active",
        "scope_ids": ["11111111-1111-4111-8111-111111111111"],
        "started_at": "2026-09-30T08:00:00Z",
        "ended_at": null,
        "published_eta": null
      }
    ]
  }
}
```

Không có lịch nào thì `outages: []`. Lịch cúp ở trạng thái `proposed` (mới là đề nghị) **không bao giờ** được trả về như đang cúp.

---

### 2. Lịch cúp điện/nước trong khoảng thời gian

```http
GET /api/technical/v1/buildings/{building_id}/utility-schedules?utility_type=power&from=2026-10-01T00:00:00Z&to=2026-10-02T00:00:00Z
```

| Query | Bắt buộc | Kiểu |
|---|:---:|---|
| `utility_type` | ✔ | `water` \| `power` |
| `from`, `to` | ✔ | thời gian, `from` < `to` |

**Response `200`:**

```json
{
  "status": "OK",
  "data": {
    "schedules": [
      {
        "schedule_id": "…",
        "utility_type": "power",
        "status": "notified",
        "planned_start": "2026-10-01T02:00:00Z",
        "planned_end": "2026-10-01T04:00:00Z",
        "scope_ids": ["…"]
      }
    ]
  }
}
```

---

### 3. Tra SOP

```http
GET /api/technical/v1/buildings/{building_id}/sops?issue_code=TECH.HVAC.CONDENSATION&query=điều hòa chảy nước&language=vi&limit=5
```

| Query | Bắt buộc | Kiểu |
|---|:---:|---|
| `issue_code` | ✔ | dạng `TECH.<NHÓM>.<MÃ>` |
| `query` | ✔ | 3–1000 ký tự |
| `effective_at` | | thời gian, mặc định là bây giờ |
| `language` | | mặc định `vi` |
| `limit` | | 1–20, mặc định 5 |

**Response `200`:**

```json
{
  "status": "OK",
  "data": {
    "documents": [
      {
        "document_id": "…",
        "code": "SOP-HVAC-012",
        "title": "Xử lý nước ngưng điều hòa chảy ra sàn",
        "version_no": 3,
        "effective_from": "2026-01-01T00:00:00Z",
        "effective_to": null,
        "excerpt": "Vệ sinh đường thoát nước ngưng, kiểm tra độ dốc ống và thử tải 30 phút.",
        "acceptance_criteria": ["Không còn rò tại thời điểm kiểm tra", "Có ảnh trước và sau khi vệ sinh đường thoát"],
        "source_refs": ["doc:SOP-HVAC-012:v3"]
      }
    ]
  }
}
```

Không có SOP đã duyệt và còn hiệu lực → `404`. Không bao giờ trả bản nháp hay bản hết hạn.

---

### 4. Tìm thiết bị

```http
GET /api/technical/v1/buildings/{building_id}/assets?asset_id=AC-A1-1205-01
GET /api/technical/v1/buildings/{building_id}/assets?location=căn 1205 phòng khách&asset_type=air_conditioner
```

Truyền **đúng một** trong `asset_id` hoặc `location`.

**Response `200`:**

```json
{
  "status": "OK",
  "data": {
    "assets": [
      {
        "asset_id": "AC-A1-1205-01",
        "type": "air_conditioner",
        "model": "Daikin FTKC35",
        "location": "A1-1205, phòng khách",
        "ownership": "resident",
        "warranty_until": "2027-03-01",
        "status": "in_service",
        "updated_at": "2026-09-01T00:00:00Z"
      }
    ]
  }
}
```

Nhiều thiết bị khớp → `200` với `status: "NEEDS_INPUT"`, `missing_fields: ["asset_id"]`, `data.assets` là danh sách để chọn. API không tự chọn hộ.

---

### 5. Số đo cảm biến

```http
GET /api/technical/v1/buildings/{building_id}/sensor-readings?asset_id=AC-A1-1205-01&metric=condensate_level&from=2026-09-30T08:00:00Z&to=2026-09-30T09:00:00Z&max_age_seconds=900
```

Truyền **đúng một** trong `sensor_id` hoặc `asset_id`. `max_age_seconds` mặc định 900.

**Response `200`:**

```json
{
  "status": "OK",
  "data": {
    "freshness": "fresh",
    "readings": [
      {
        "sensor_id": "SNS-009",
        "asset_id": "AC-A1-1205-01",
        "metric": "condensate_level",
        "value": 12.4,
        "unit": "mm",
        "observed_at": "2026-09-30T08:58:00Z",
        "quality": "good"
      }
    ]
  }
}
```

Số đo cũ hơn `max_age_seconds` → `200` với `status: "STALE_DATA"`, vẫn kèm `readings`.

---

### 6. Lịch sử bảo trì

```http
GET /api/technical/v1/buildings/{building_id}/assets/{asset_id}/maintenance-history?from=2026-01-01T00:00:00Z&to=2026-09-30T09:00:00Z&limit=20
```

**Response `200`:**

```json
{
  "status": "OK",
  "data": {
    "events": [
      {
        "event_id": "ME-102",
        "asset_id": "AC-A1-1205-01",
        "incident_id": "31111111-1111-4111-8111-111111111111",
        "workorder_id": "41111111-1111-4111-8111-111111111111",
        "occurred_at": "2026-07-02T04:00:00Z",
        "outcome": "cleaned_drain_line",
        "source_refs": ["workorder:41111111-1111-4111-8111-111111111111"]
      }
    ],
    "last_maintenance_at": "2026-07-02T04:00:00Z",
    "repeat_count": 1
  }
}
```

---

### 7. Ghi số đo

```http
POST /api/technical/v1/buildings/{building_id}/work-orders/{workorder_id}/measurements
Idempotency-Key: measure-WO-4111-flow-1
```

**Body:**

```json
{
  "asset_id": "AC-A1-1205-01",
  "metric": "drain_flow",
  "value": 1.2,
  "unit": "L/min",
  "measured_at": "2026-09-30T08:48:00Z",
  "measured_by": { "kind": "technician", "source_id": "<user_id của kỹ thuật viên>" },
  "source": "instrument",
  "evidence_ids": ["<evidence uuid>"]
}
```

**Response `201`:**

```json
{
  "status": "OK",
  "data": {
    "measurement_id": "MS-701",
    "metric": "drain_flow",
    "normalized_value": 1.2,
    "normalized_unit": "L/min",
    "created_at": "2026-09-30T09:07:00Z",
    "quality_flags": []
  }
}
```

`measured_by.source_id` phải là chính người mà run đang phục vụ (hoặc một cảm biến đã đăng ký), nếu không trả `403`. Giá trị bất thường vẫn được ghi, kèm cờ `out_of_expected_range`.

---

### 8. Nộp kết quả công việc

```http
POST /api/technical/v1/buildings/{building_id}/work-orders/{workorder_id}/executor-results
Idempotency-Key: executor-WO-4111-v1
```

**Body:**

```json
{
  "assignment_id": "71111111-1111-4111-8111-111111111111",
  "checklist": [{ "item_code": "DRAIN_CLEAR", "status": "passed", "note": "Dòng thoát ổn định" }],
  "measurement_ids": ["MS-701"],
  "parts": [],
  "evidence_ids": ["<before uuid>", "<after uuid>"],
  "diagnosis": "Tắc nhẹ đường nước ngưng",
  "repair_notes": "Đã vệ sinh và thử tải",
  "started_at": "2026-09-30T08:20:00Z",
  "completed_at": "2026-09-30T08:55:00Z"
}
```

**Response `201`:**

```json
{
  "status": "OK",
  "data": {
    "result_id": "ER-9001",
    "validation_status": "ACCEPTED",
    "created_at": "2026-09-30T09:08:00Z",
    "missing_evidence": [],
    "conflicts": []
  }
}
```

`validation_status`: `ACCEPTED` | `NEEDS_EVIDENCE` | `HUMAN_REVIEW`. **Không** đổi trạng thái work order hay ticket. Ảnh còn đang tải → `409`.

---

### 9. Xác minh kết quả

```http
POST /api/technical/v1/buildings/{building_id}/work-orders/{workorder_id}/executor-results/{result_id}/verification
```

**Body:**

```json
{
  "incident_id": "31111111-1111-4111-8111-111111111111",
  "sop_document_ids": ["<document uuid của SOP-HVAC-012>"]
}
```

**Response `200`:**

```json
{
  "status": "OK",
  "data": {
    "verification_status": "VERIFIED",
    "checks": [
      { "criterion": "SOP-HVAC-012 v3: Không còn rò tại thời điểm kiểm tra", "status": "passed", "source_refs": ["doc:SOP-HVAC-012:v3", "result:ER-9001"] }
    ],
    "required_actions": ["Chuyển người có thẩm quyền xác nhận hoàn tất"],
    "source_refs": ["result:ER-9001", "doc:SOP-HVAC-012:v3"]
  }
}
```

Chỉ đọc: không đóng ticket, không ghi lịch sử. Không có `Idempotency-Key`.

---

### 10. Ghi lịch sử bảo trì

```http
POST /api/technical/v1/buildings/{building_id}/assets/{asset_id}/maintenance-events
Idempotency-Key: mh-WO-4111-v1
```

**Body:**

```json
{
  "workorder_id": "41111111-1111-4111-8111-111111111111",
  "verified_result_id": "ER-9001",
  "outcome": "Đã vệ sinh đường thoát nước ngưng và kiểm tra không còn rò.",
  "source_refs": ["result:ER-9001", "doc:SOP-HVAC-012:v3"],
  "occurred_at": "2026-09-30T08:55:00Z",
  "supersedes_event_id": null
}
```

**Response `201`:**

```json
{
  "status": "OK",
  "data": {
    "maintenance_event_id": "ME-103",
    "created_at": "2026-09-30T09:06:00Z",
    "revision": 1,
    "supersedes_event_id": null
  }
}
```

Tool tự xác minh lại kết quả; chưa `VERIFIED` → `409`, không ghi gì. `source_refs` phải có `result:<verified_result_id>` và SOP dạng `doc:<mã>:v<n>`.

---

### 11. Đề nghị khóa nước / cắt điện

```http
POST /api/technical/v1/buildings/{building_id}/utility-isolation-requests
Idempotency-Key: isolate-WO-4111-v1
```

**Body:**

```json
{
  "incident_id": "31111111-1111-4111-8111-111111111111",
  "workorder_id": "41111111-1111-4111-8111-111111111111",
  "utility_type": "water",
  "scope_ids": ["<access_scope uuid của tòa>"],
  "reason": "Cần khóa nước để xử lý rò đường ống chính",
  "planned_start": "2026-09-30T10:00:00Z",
  "planned_end": "2026-09-30T11:00:00Z",
  "evidence_ids": ["<evidence uuid>"]
}
```

**Response `202`:**

```json
{
  "status": "PENDING_APPROVAL",
  "data": {
    "request_id": "81111111-1111-4111-8111-111111111111",
    "interruption_id": "91111111-1111-4111-8111-111111111111",
    "approval_status": "PENDING_APPROVAL",
    "required_scope_id": "<scope rộng nhất trong scope_ids>",
    "created_at": "2026-09-30T09:10:00Z"
  }
}
```

Nước: ghi `work_approvals` (`pending`) + `service_interruptions` (`proposed`) + `interruption_scopes` trong **một transaction**. Điện: lưu ở adapter phê duyệt cho tới khi DB có loại phê duyệt cho cắt điện.

---

### 12. Đề nghị rào chắn khu vực

```http
POST /api/technical/v1/buildings/{building_id}/area-restriction-requests
Idempotency-Key: restrict-INC-3111-v1
```

**Body:**

```json
{
  "incident_id": "31111111-1111-4111-8111-111111111111",
  "workorder_id": null,
  "area": "Hành lang tầng 12, tháp A1",
  "hazard": "Mảng trần có dấu hiệu võng",
  "reason": "Hạn chế người qua lại đến khi kỹ sư kết cấu kiểm tra",
  "requested_until": "2026-09-30T15:00:00Z",
  "evidence_ids": ["<evidence uuid>"]
}
```

**Response `202`:**

```json
{
  "status": "PENDING_APPROVAL",
  "data": {
    "request_id": "AR-1001",
    "approval_status": "PENDING_APPROVAL",
    "required_approver_scope": "building_management",
    "created_at": "2026-09-30T09:11:00Z"
  }
}
```

---

### 13. Xin vào căn hộ vắng chủ

```http
POST /api/technical/v1/buildings/{building_id}/apartment-entry-requests
Idempotency-Key: entry-INC-3111-unit-a-v1
```

**Body:**

```json
{
  "incident_id": "31111111-1111-4111-8111-111111111111",
  "unit_id": "a1111111-1111-4111-8111-111111111111",
  "reason": "Cần kiểm tra nguồn rò có thể ảnh hưởng căn phía dưới",
  "contact_attempts": [
    { "channel": "app", "attempted_at": "2026-09-30T08:00:00Z", "outcome": "delivered", "reference_id": "msg-880" },
    { "channel": "phone", "attempted_at": "2026-09-30T08:30:00Z", "outcome": "no_answer" }
  ],
  "requested_window": { "from": "2026-09-30T10:00:00Z", "to": "2026-09-30T12:00:00Z" },
  "evidence_ids": ["<evidence uuid>"]
}
```

**Response `202`:**

```json
{
  "status": "PENDING_APPROVAL",
  "data": {
    "request_id": "AE-1001",
    "approval_status": "PENDING_APPROVAL",
    "required_approvals": ["resident_or_authorized_management"],
    "created_at": "2026-09-30T09:12:00Z"
  }
}
```

- Liên hệ chủ nhà chưa đủ → `200` với `status: "NEEDS_INPUT"`, `missing_fields: ["contact_attempts"]`.
- Body chứa mã cửa / mật khẩu → `400`, không lưu.
- Căn hộ không thuộc tòa → `403`.

---

### 14. Đề nghị gọi nhà thầu

```http
POST /api/technical/v1/buildings/{building_id}/vendor-dispatch-requests
Idempotency-Key: vendor-INC-3111-v1
```

**Body:**

```json
{
  "incident_id": "31111111-1111-4111-8111-111111111111",
  "workorder_id": "41111111-1111-4111-8111-111111111111",
  "service": "Kiểm định vết nứt kết cấu",
  "reason": "Cần kỹ sư kết cấu có chứng chỉ đánh giá tại hiện trường",
  "urgency": "soon",
  "required_specialty_code": "STRUCTURAL_ENGINEER",
  "evidence_ids": ["<evidence uuid>"]
}
```

**Response `202`:**

```json
{
  "status": "PENDING_APPROVAL",
  "data": {
    "request_id": "VD-1001",
    "approval_status": "PENDING_APPROVAL",
    "eligible_vendors": [
      { "vendor_id": "VEN-21", "display_name": "Đơn vị kiểm định A", "qualification_status": "eligible" }
    ],
    "created_at": "2026-09-30T09:13:00Z"
  }
}
```

Không đặt lịch, không ký hợp đồng, không trả tiền. `urgency` không đổi mức ưu tiên ticket. Không trả số điện thoại hay giá của nhà thầu.

---

## 4. Cách cài đặt một endpoint

Mỗi route chỉ làm 3 việc: xác thực, gom `args`, gọi tool. Ví dụ endpoint `#7`:

```ts
import { createTechnicalToolHost, findTechnicalTool } from "./technical-tools";

const host = createTechnicalToolHost(technicalToolDependencies); // mục 5

app.post(
  "/api/technical/v1/buildings/:building_id/work-orders/:workorder_id/measurements",
  async (c) => {
    // 1. Xác thực: cùng hàm authoriseAgentCall mà /api/agent-tools/call đang dùng
    const verdict = await authoriseAgent(c); // trả { botId, actorId, initiator }
    if (!verdict.ok) return c.json({ error: verdict.reason }, verdict.status);

    // 2. Gom args: path + body + Idempotency-Key
    const body = await c.req.json();
    const args = {
      ...body,
      building_id: c.req.param("building_id"),
      workorder_id: c.req.param("workorder_id"),
      idempotency_key: c.req.header("Idempotency-Key"),
    };

    // 3. Gọi tool, trả envelope với HTTP status theo bảng 2.4
    const tool = findTechnicalTool("technical.record_measurement")!;
    const envelope = await host.call(verdict, tool, args);
    return c.json(envelope, httpStatusOf(envelope.status, "create"));
  },
);
```

Với `GET`, `args` lấy từ path và query. Riêng `time_range` của tool `#2`, `#5`, `#6` gom từ hai query `from`, `to`:

```ts
time_range: { from: c.req.query("from"), to: c.req.query("to") }
```

Host của Team Quang đã tự kiểm tra quyền, validate schema, chống ghi trùng và ghi audit, nên route **không cần** làm lại các việc đó.

---

## 5. Port Team Chiến cần cấp cho host

| Port | Việc | Ghi chú |
|---|---|---|
| `contextResolver` | Từ `botId`/`actorId` trả `tenant_id`, `user_id`, `role_code`, `source_run_id`, `grants` | `grants: { capability, scope_ids }[]` |
| `buildingAccess` | Scope của capability có bao phủ tòa không | Có sẵn `createScopeBuildingAccess(createDbScopeReadPort(db))` |
| `audit` | Ghi mọi lời gọi, kể cả bị từ chối | |
| Các adapter dữ liệu | Đọc/ghi bảng | Đã có adapter DB cho work order, ảnh, SOP, lịch cúp, căn hộ, phạm vi; phần còn lại là POC chờ bảng (xem `docs/teams/quang/requests/Q02-backend-ports.md`) |

Quyền DB cho role chạy tool: chỉ `SELECT`, và `INSERT` trên `work_approvals`, `service_interruptions`, `interruption_scopes`. **Không `UPDATE`, không `DELETE`.**

---

## 6. Checklist

- [x] `GET /tools`
- [x] 6 endpoint `GET` tra cứu (`#1`–`#6`)
- [x] 4 endpoint `POST` ghi nhận / xác minh (`#7`–`#10`)
- [x] 4 endpoint `POST` đề nghị rủi ro (`#11`–`#14`): trả `202` khi tạo đề nghị thành công; lỗi hoặc thiếu dữ liệu vẫn theo bảng 2.4
- [x] Header `X-OpenBot-Agent-Token`, `X-OpenBot-Run`, `Idempotency-Key`
- [x] Ánh xạ `status` → HTTP code theo bảng 2.4
- [x] `contextResolver`, `buildingAccess`, `audit`
- [x] Quyền DB và các bảng thay POC
- [x] Chạy `bun test server/tests/technical-tools` (882 test) sau khi nối

---

## 7. Kết quả triển khai ngày 02/10/2026

### 7.1. API và luồng xử lý

Đã triển khai đủ 15 route trong `server/src/technical-api/routes.ts`, gắn vào Hono tại `/api/technical/v1` trong `server/src/app.ts`. Cổng mặc định của Hono trong repository là **3001**, nên URL local là **`http://localhost:3001/api/technical/v1`**. Cổng local được thống nhất là 3001; cổng 8000 vẫn thuộc service FastAPI hiện có.

Luồng:

1. Backend xác minh token callback của agent và chữ ký/thời hạn của run assertion trong header.
2. Tra agent đang active, phiên bản, membership người yêu cầu và quyền đã cấp trong PostgreSQL. Quyền agent được giao với quyền người yêu cầu theo scope; role management chỉ dùng khi scope của role đó bao phủ tòa nhà được gọi.
3. Route chuyển path/query/body thành input đúng schema. Không nhận tenant, người gọi, role hay run từ body. JSON tối đa 128 KiB; query trùng, field lạ hoặc ghi đè path bị từ chối.
4. Gọi `createTechnicalToolHost()` của Team Quang. Host kiểm tra capability, tòa nhà, input và output, rồi gọi port dữ liệu.
5. Adapter đọc/ghi PostgreSQL, ghi audit, lưu response cho idempotency; dữ liệu nghiệp vụ, audit và receipt thành công nằm trong cùng transaction. Lỗi rollback dữ liệu và ghi audit từ chối riêng.
6. Trả envelope cho agent đọc `status`, `data`, `errors`, `missing_fields`, `provenance` và quyết định bước tiếp theo. `/tools` trả catalogue `{ "tools": [...] }` như phần 3.0.

API không gọi LLM và không chạy agent. Logic tool đã được lấy nguyên bản từ nhánh `dev_TeamQuang`, commit `6094b53`; phần mới là HTTP transport, xác thực và adapter PostgreSQL. Việc kiểm tra checklist, số đo và evidence là kiểm tra quy tắc xác định sẵn. API không tự đóng ticket/work order hay duyệt/thực hiện các đề nghị.

### 7.2. Dữ liệu thật và seed giả

Migration `server/drizzle/0009_technical_agent_api.sql` thêm 11 bảng có tenant RLS:

| Bảng | Chức năng |
|---|---|
| `vh_technical_agent_grants` | Capability và scope được cấp cho agent |
| `vh_technical_sop_profiles` | Issue code, trích đoạn và tiêu chí có cấu trúc của một phiên bản SOP |
| `vh_technical_sensors` | Sensor đã đăng ký, tòa, tài sản, metric, đơn vị |
| `vh_technical_sensor_samples` | Mẫu đo BMS/IoT |
| `vh_technical_measurement_records` | Số đo ghi qua API, nguồn, người/thiết bị đo và evidence |
| `vh_technical_executor_results` | Checklist, vật tư, số đo, evidence và kết quả nhân viên gửi |
| `vh_technical_maintenance_events` | Lịch sử đã xác minh; sửa sai bằng bản ghi thay thế |
| `vh_technical_approval_requests` | Đề nghị ngắt điện, hạn chế khu vực, vào căn hộ, nhà thầu |
| `vh_technical_vendors` | Danh mục nhà thầu và điều kiện phù hợp |
| `vh_technical_api_receipts` | Payload hash, outcome và toàn bộ response để trả lại khi retry |
| `vh_technical_api_audit` | Nhật ký gọi API, gồm cả từ chối |

Hồ sơ tài sản đọc từ `vh_assets`; work order, assignment, evidence, căn hộ, cư dân, SOP, outage và lịch cắt dịch vụ đọc các bảng V3 hiện có. Đề nghị khóa nước ghi `work_approvals` + `service_interruptions` trạng thái `proposed` + `interruption_scopes` trong một transaction. Các đề nghị khác ghi adapter approval, trạng thái `pending`.

Role `vinhomes_technical_api` chỉ có SELECT/INSERT cần thiết. Runtime từ chối role superuser, BYPASSRLS hoặc có UPDATE/DELETE trên bảng public. Bảng số đo, kết quả, lịch sử, receipt và audit có trigger ngăn UPDATE/DELETE.

Seed nằm trong `server/scripts/seed_technical_api.sql`. Tất cả dữ liệu demo được lưu vào PostgreSQL Docker local `vinhomes_v3`, port 5544; không dùng kho POC trong bộ nhớ. Seed có agent `demo-technical-a2`, capability grants, SOP thoát nước, asset `ASSET-DEMO-1`, sensor `SENSOR-DEMO-SUPPLY-PRESSURE`, căn hộ demo và vendor. Metric số đo áp lực đúng contract là **`supply_pressure`**, đơn vị `bar` hoặc `kPa`; không dùng `pressure` cho API ghi số đo.

### 7.3. Cấu hình và chạy

Chạy từ thư mục gốc dự án sau khi database demo đã có seed V3:

```powershell
docker start vinhomes-faker-v3-postgres-1
& services/vinhomes-api/scripts/upgrade_demo_database.ps1
& services/vinhomes-api/.venv/Scripts/python.exe server/scripts/setup_technical_api_demo.py
```

Script setup tạo role giới hạn quyền, seed dữ liệu và lưu hai biến cấu hình trong file **đã được gitignore** `services/vinhomes-api/.local-v3-faker/technical-api.env`:

- `TECHNICAL_API_DATABASE_URL`: kết nối PostgreSQL của role dành riêng cho Technical API.
- `TECHNICAL_API_TENANT_ID`: tenant V3 phục vụ deployment.

Nạp file đó rồi chạy Hono bằng cấu hình backend hiện có:

```powershell
Get-Content services/vinhomes-api/.local-v3-faker/technical-api.env | ForEach-Object {
  if ($_ -and !$_.StartsWith('#')) {
    $parts = $_.Split('=', 2)
    [Environment]::SetEnvironmentVariable($parts[0], $parts[1], 'Process')
  }
}
bun run --cwd server dev
```

Hai biến phải có cùng nhau; tenant phải là UUID. Nếu không cấu hình cả hai, module Technical API chưa được bật. PostgreSQL chính, khóa ký và các biến backend Hono hiện có vẫn cần cấu hình để khởi động toàn bộ server.

Agent cần token callback thật đã được backend cấp và một run assertion do backend ký bằng `KEY_ENCRYPTION_KEY`. Token phải thuộc cùng agent được ghi trong assertion; agent và người yêu cầu phải tồn tại trong tenant V3 với scope được cấp. Seed database không tự cấp một token production và không tạo agent runtime. Khi triển khai, cấp các dòng `vh_technical_agent_grants` cho **ID agent thực tế** của backend và scope được phép. Không chuyển khóa ký hay URL database cho frontend/model.

### 7.4. Kiểm tra đã chạy

| Kiểm tra | Kết quả |
|---|---|
| TypeScript `bun run --cwd server typecheck` | Thành công |
| Bộ test Team Quang qua PGlite, nạp đủ migration V3 | 882 pass, 0 fail |
| Bộ test Team Quang trên PostgreSQL Docker, mỗi fixture có database riêng | 882 pass, 0 fail |
| Test HTTP boundary `bun test server/tests/technical-api.routes.test.ts` | 5 pass, 0 fail |
| `bun server/scripts/verify_technical_api_demo.ts` | Thành công trên PostgreSQL Docker local |

Script demo chạy trực tiếp Hono router bằng `app.request`, với token và khóa ký tạm trong tiến trình để kiểm tra transport, host và PostgreSQL; không cần chạy AI hay giả lập response nghiệp vụ. Nó không kiểm tra việc đăng ký/cấp token trong màn hình quản trị và không phải một server đang lắng nghe cổng 3001.

Đã thử đủ 15 route: lookup trả 200; ghi số đo, kết quả và lịch sử trả 201; verification trả dữ liệu đánh giá; đề nghị hợp lệ trả 202. Gọi lại một đề nghị đã pending bằng key mới có thể trả 409 đúng quy tắc. Thử lại cùng key/body trả đúng toàn bộ response gốc và không thêm bản ghi; đổi body cùng key trả 409; chèn tenant vào body trả 400; thiếu xác thực trả 403. Trạng thái work order trước và sau luồng vẫn giữ nguyên.

Để chạy lại kiểm tra demo:

```powershell
bun test server/tests/technical-api.routes.test.ts
bun server/scripts/verify_technical_api_demo.ts
```

Script kiểm tra chỉ chấp nhận địa chỉ `127.0.0.1` và database `vinhomes_v3`. Nó ghi thêm dữ liệu giả để thử luồng, không xóa dữ liệu đã có. Lần đầu tạo các đề nghị trả 202; lần sau có thể trả 409 vì đề nghị tương ứng vẫn chờ duyệt.
