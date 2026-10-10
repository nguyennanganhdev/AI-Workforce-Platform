# Phase A — Protocol fields, ordering và mapping

Ngày: 2026-10-10. Phạm vi: nhịp A mục 17.9, phần của Nguyễn Phương Đông.
Đã có cấu hình kiểm tra được bằng code, schema, samples và fake port cho
Nghĩa/Anh/Dũng. Đây chưa phải hoàn thành NPD-10–12 hoặc tích hợp runtime.

## Public exports và dữ liệu bàn giao

- Production: `agentscope.app.workforce.registry.event_protocols` export
  `AsyncToolProtocol`, `EventMapping`. Đây là metadata cấu hình do Registry sở
  hữu; DTO/port liên module vẫn dùng nguyên `agentscope.app.workforce.contracts`.
- `AsyncToolProtocol.model_json_schema()` → [phase_a_protocol.schema.json](phase_a_protocol.schema.json).
- [phase_a_samples.json](phase_a_samples.json) có 5 protocol, snapshot reference
  với hash thật, một `ToolDescriptor` và một `ProviderEventEnvelope` hợp lệ.
  Tool descriptor là dữ liệu demo; `schema_hash` của tool khác hash protocol.
- Fake tại `tests/workforce/registry/event_protocols/fakes.py` triển khai đúng
  ba signature của `AsyncProtocolPort` hiện hành. Chỉ dùng trong test/demo.
  Chưa export production `RegistryPort`, router hoặc service/persistence.

Không thêm dependency vào repo: dùng `WorkforceModel`, `ToolEffect`, DTO/ports
chung, Pydantic, `jsonschema` đã có và `hashlib/json` của Python.

## Ý nghĩa cấu hình

`protocol_id` + `protocol_version` xác định bản metadata; `tool_version_id` pin
tool nguồn. `provider_integration_id` là namespace đã onboarding, không phải
tên tool, manager hay `partner_client_id`. Scope do Registry repository kiểm
tra đủ tenant/domain/area/manager; không nhận scope từ event.

`effect`, `result_mode`, `requires_approval`, `completion_policy` tách tác dụng
tool, terminal/pending, consent và đóng workflow. Chỉ terminal read không cần
approval được `read_only_auto_close`. Terminal không cấu hình timer/tracking.
Approval không được thay bằng provider event; Registry không cập nhật workflow.

Mapping v1 dùng **tên field cấp đầu**, không phải URL/JSONPath:

- `client_reference_field`: field input gửi correlation do platform tạo trước
  call; không lấy correlation từ prompt làm quyền truy cập.
- `external_job_id_field`, `status_field`: field result chứa job ID/status.
- `status_query_tool_version_id`: tool version MCP để query; dùng cùng mapping
  job/status. Quyền gọi/binding/credential cần recheck qua Registry ở phase sau.
- `event_mappings[event_type]`: status chuẩn hóa, JSON Schema Draft 2020-12 cho
  `data`, và allowlist `fact_fields`. Không gọi LLM hoặc biến provider notes thành
  instruction; field không được chọn không đi vào normalized facts.
  `$ref`/`$dynamicRef` phải resolve được trong schema đã bàn giao, gồm `$defs`,
  anchors và schema con có `$id`; thiếu đích hoặc cần tải ngoài bị từ chối ngay
  khi cấu hình. Validation không tải schema từ mạng.
- `transitions`: cạnh trạng thái cho phép; `terminal_statuses`: trạng thái cuối,
  không có cạnh đi ra. Status từ result/event phải thuộc tập đã khai báo.
- `timeout_seconds`: thời hạn nghiệp vụ của pending operation. Hết hạn cần query
  khi có khả năng, còn lại `needs_attention`; không giả completed hoặc retry create.

Capabilities của `snapshot_ref` được **suy ra từ cấu hình**, không nhập tự do:

- `terminal`: kết quả đồng bộ; `approval` bổ sung khi cần consent.
- `create`: kết quả pending có namespace/correlation/status/timeout.
- `receive_status`: có mapping Provider Event. Không có nghĩa HTTP ingress đã chạy.
- `status_query`: có tool version query. Không có nghĩa binding hiện đang available.

Create-only chỉ có `create`, không đủ để Builder hứa theo dõi tiến độ. Query-only
không cần Provider Event API; sync/interactive không cần tracking. Kiểm tra một
tập capability là phép AND; lựa chọn `receive_status` **hoặc** `status_query`
do Builder/Lifecycle quyết định theo requirement, không truyền cả hai khi chỉ cần một.

Hash SHA-256 bao phủ toàn bộ JSON cấu hình với key sort, UTF-8,
`separators=(",", ":")`, không NaN. Đổi schema/mapping/policy/namespace tạo hash
mới; phải tăng protocol version khi onboarding bản mới. Job cũ giữ cả ref/hash
và nội dung bản cũ. Disable/drift chỉ chặn call mới, không tự xóa protocol đã pin
hoặc quyền nhận event hợp lệ cho job cũ.

## Ordering và điểm nối Execution

Normalizer chỉ validate/map và giữ nguyên provider version; không đọc/ghi
operation, không sắp theo timestamp, không tự cấp conversation sequence.
Execution xử lý sau khi resolve operation đúng namespace, trong uow:

1. `ordering=provider_version`: version bắt buộc. Version thấp hơn bỏ qua; cùng
   version/cùng nội dung nghiệp vụ là duplicate, khác nội dung là quarantine.
   Không dùng event ID hoặc thời gian transport để so bằng nội dung trạng thái.
2. `event_mode=snapshot`: snapshot mới có thể vượt gap nếu transition và schema
   cho phép. `event_mode=delta`: bắt buộc version; gap phải buffer/reconcile qua
   query hoặc needs_attention trước khi apply. Fake giữ metadata, không giả đã
   buffer/reconcile hoặc áp dụng thành công.
3. `ordering=transition_only`: occurred_at không chứng minh thứ tự. Chỉ đi cạnh
   đã khai báo; event mơ hồ hoặc terminal conflict cần query/needs_attention.
4. Terminal không lùi bởi event đến muộn. V1 không khai báo correction/reopen;
   integration cần nghiệp vụ đó phải chốt version mới với owner trước khi dùng.
5. Idempotency/correlation conflict, inbox persist, transition CAS và trigger
   thuộc Execution/Orchestration; Registry không đánh dấu event đã applied.

Sample minh họa `pending → assigned → on_the_way → arrived → completed`.
Các tên này chỉ nằm trong cấu hình demo, không hardcode vào core/workflow.
Event ID `event-003`, job `job-123`, correlation `correlation-001` chỉ để đối soát.

## Chạy kiểm tra / dùng fake

Từ `platform_VP/agentscope`, với environment đã cài repo và service dependencies:

```bash
python -m unittest discover -s tests/workforce/registry/event_protocols -p 'test_*.py' -v
python -m pytest tests/workforce/registry/event_protocols tests/workforce/foundation/test_contracts.py -q
```

Consumer test thêm `tests/workforce/registry/event_protocols` vào test import
path rồi `from fakes import FakeAsyncProtocolPort`; không import fake từ production.
Constructor nhận `scope`, danh sách config (bản mới sau bản cũ), verified actor,
integration ID đã xác minh, inbox ID và received_at cố định. Fake serialize config
để không bị caller sửa; giữ các bản cũ theo hash và lookup hiện hành theo tool version.
Hai reference có cùng job ID nhưng khác integration không được dùng lẫn.

Điểm thiếu của contract để tích hợp thật được ghi ở
[INTEGRATION_REQUEST_NPD_PHASE_A.md](INTEGRATION_REQUEST_NPD_PHASE_A.md).
Gate endpoint/SDK cũ vẫn độc lập; xem [INTEGRATION_REQUEST_NPD_ENDPOINT.md](INTEGRATION_REQUEST_NPD_ENDPOINT.md).
