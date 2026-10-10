# PHD-02/03/04/14–16 — Registry và provider adapters

Người gửi: Phan Hoàng Dũng. Người nhận: Nguyễn Phương Đông; phối hợp Chí Hoàng cho contracts/credentials. Phạm vi nhận: registry, event_protocols; không yêu cầu sửa Execution từ branch Registry.

Hiện trạng: chỉ scaffold. ExecutionPolicy dùng `RegistryPort.get_tool_snapshot(scope, tool_version_id)` đúng tên mục 6.3; snapshot available được check với binding tool_id/version/schema_hash/capability đã pin. Runtime.authorize_tool kiểm tra connection/credential/actor policy hiện hành. Scope không phải field bắt buộc mới của ToolDescriptor: scoped port phải authorize; nếu adapter đính kèm scope nội bộ thì Execution cũng so khớp.

Đầu ra cần bàn giao:

- Tool snapshots immutable cùng observed MCP input/output schema và aliases duy nhất. `effect_reviewed` là **metadata nội bộ đề xuất**, mặc định thiếu là bị chặn; effect không đoán từ HTTP hoặc readOnlyHint. Cần chốt với contracts. Registry chỉ discovery, không call write/booking để test.
- Import descriptor `execution.calculator_descriptor(scope)`: tool builtin.money.v1, capability calculate_money, JSON schema integer minor units. Builder chỉ thấy khi đã đăng ký rõ trong catalog.
- MCP connection/credential adapter và reviewed `idempotency_fields={tool_version_id: provider_field}` inject vào `McpAdapter`. Gateway/ToolBase ẩn server field khỏi input model; adapter gửi call_id (sync) hoặc correlation_id (async) đã persist. Provider không hỗ trợ key không được claim exactly-once. Không lấy field/key từ model hay annotation chưa duyệt.
- Mandatory MCP output projector: `project(scope, descriptor, ToolChunk) -> sanitized JSON`, validate business outcome từ dữ kiện provider; không persist raw response/credential/private note. SDK MCPTool hiện chuyển content thành ToolChunk, nên projector provider cần parse JSON content thật; không giả cấu trúc structuredContent mà SDK không export.
- Quote port `validate(scope, context, call, descriptor)` xác minh giá/ngày/số người/option từ quote/version thật; trả quote_ref/quote_version/provider/option/dates/amount/fees/cancellation_terms/expires_at. Model không tự cấp quote.
- Query adapters cho sync unknown (`query_booking(scope, stored_booking, stored_call, cause_id)`) và async (`query(scope, stored_operation, timer_id)`), scoped/pinned read-only credentials. Unknown không có đường query thì needs_attention/manual, không create lại.

AsyncProtocolPort implementation được inject; representation hiện tại trong fixture là **contract proposal**, cần canonical shared DTO do Chí Hoàng export:

```text
get_snapshot(scope, tool_version_id) -> protocol snapshot
validate_envelope(verified_provider, envelope) -> validation only, no mutation
normalize_verified_event(provider, pinned_protocol, envelope) ->
  status, facts(sanitized), provider_version?, order_mode=snapshot|delta|transition, terminal
validate_transition(pinned_protocol, current_operation, normalized_event) -> apply|stale|conflict
normalize_creation_result(pinned_protocol, sanitized_output) ->
  creation_status=succeeded|failed|unknown, external_job_id?, job_status?, pending
normalize_query_result(pinned_protocol, query_output) -> normalized status/facts/version/terminal
```

Snapshot hiện Execution cần protocol_id/version/schema_hash/provider_integration_id/capability=external_tracking/provider_events/status_query/order_mode/initial_version/create_fields. create_fields chỉ map client_reference/idempotency_key vào tên argument. Descriptor async_protocol_hash pin hash toàn snapshot. Cần shared canonical hash/schema shape, không tự đổi field khi merge; map adapter nếu DTO cuối khác. Protocol normalize deterministic, không LLM, không ghi workflow/ticket.

Execution xử lý version monotonic/delta gap/same-version conflict; transition map/terminal/correction là trách nhiệm protocol. Tests fixture `Protocols` ghi rõ TEST ONLY, không hardcode repair/hotel status trong core. Nhiều integration phải có namespace job ID riêng.

Validation: fake MCP stdio thật và schema drift; quote changed; credential mismatch/evaluation block; early/unknown event, snapshot ordering, delta gap; timer query. Đường live sandbox còn thiếu credential/endpoint/protocol/signature/grant, không tự gọi booking thật.

