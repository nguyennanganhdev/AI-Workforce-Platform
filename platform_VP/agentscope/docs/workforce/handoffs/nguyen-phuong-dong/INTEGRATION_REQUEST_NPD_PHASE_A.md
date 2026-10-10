# Integration request — NPD Phase A

Ngày: 2026-10-10. Producer: Registry / Nguyễn Phương Đông.
Trạng thái: schema/fake đã bàn giao trong [PHASE_A.md](PHASE_A.md);
các thay đổi shared contract dưới đây **là đề xuất chưa được tích hợp**.

## Chí Hoàng + Dũng — context cho normalization

Signature hiện có được giữ nguyên trong fake:

```python
async def normalize_verified_event(
    provider_context: ActorContext,
    protocol_snapshot: AsyncProtocolSnapshotRef,
    envelope: ProviderEventEnvelope,
) -> NormalizedJobEvent: ...
```

`ActorContext` có partner client/credential purpose, chưa có tenant/integration
namespace được xác minh. `NormalizedJobEvent` bắt buộc inbox_event_id/received_at,
nhưng method chưa nhận hai giá trị từ inbox. Không thể tự tạo ID/thời gian mới
khi retry hoặc đồng nhất actor/partner/tool name với provider integration.

Đề nghị owner chốt context chung (tên đề nghị `VerifiedProviderEventContext`)
gồm verified actor + tenant_id + provider_integration_id + inbox_event_id +
received_at; thay type provider_context trong signature trên bằng context này.
Execution tạo context từ provider grant và inbox đã persist; Registry kiểm tra
namespace với protocol đã pin. Không thêm các field này vào provider payload.

Ví dụ context nội bộ hợp lệ: tenant-1/provider-demo/inbox-1, actor purpose
provider_events, received_at từ inbox; snapshot provider-demo. Snapshot của
provider-other phải bị từ chối dù external_job_id đều là job-123. Context purpose
customer_api, hoặc ID inbox do payload tự khai, không được chấp nhận.

Compatibility trên nền `develop2` tại `3270ef3`: chưa có service Registry
production, nhưng đã có các caller trong Execution:

- `execution/_gateway.py`: gọi `get_snapshot` và `normalize_creation_result`.
- `execution/provider_events/_ingress.py`: gọi `validate_envelope`.
- `execution/provider_events/_processor.py`: gọi `normalize_verified_event`
  và `validate_transition`.

Các caller này dùng dictionary cho principal/protocol/envelope và đòi kết quả
normalization có `status`, `facts`, `provider_version`, `order_mode`, `terminal`;
`AsyncProtocolPort` chung hiện dùng DTO và trả `NormalizedJobEvent` với
`normalized_status`, chưa có `order_mode`/`terminal` hoặc ba method bổ sung
`normalize_creation_result`, `validate_envelope`, `validate_transition`.
Fake Phase A chưa thay trực tiếp được protocol fake của Execution. Chí Hoàng/Dũng
cần chốt contract và cập nhật callers/tests tại nhịp B/C trước khi nối runtime;
không đổi interface chỉ dựa vào việc tests hai module chạy riêng đều pass.

Fake hiện seed context qua constructor chỉ cho test. Đề xuất context trên chưa
yêu cầu migration Registry; owner Execution chốt persistence inbox và đánh giá
ảnh hưởng khi cập nhật contract. PR này không sửa callers hoặc shared contracts.

## Chí Hoàng + Dũng/Nghĩa/Anh — detailed snapshot

`get_snapshot(scope, tool_version_id)` hiện trả `AsyncProtocolSnapshotRef` chỉ
gồm IDs/hash/capabilities; `NormalizedJobEvent` cũng chưa chứa ordering/event_mode.
Execution cần ordering, snapshot/delta, transition map, terminal statuses và timeout
để kiểm tra version/gap đúng bản đã pin. Đề nghị chốt export DTO chi tiết theo
[phase_a_protocol.schema.json](phase_a_protocol.schema.json), hoặc accessor port
đọc chi tiết theo exact ref/hash. Không đọc private Registry table hoặc tra config
hiện hành thay bản cũ. Registry-owned config hiện dùng DTO chung cho wire output,
không tự sửa `contracts/` hay TypeScript của owner khác.

Production storage cần append-only key `(scope, tool_version_id, protocol_id,
protocol_version)` với immutable hash/content; cùng key khác hash là conflict.
Current pointer riêng; disable/resync không xóa snapshot đã được operation pin.
Schema/repository/migration sẽ bàn giao ở nhịp B/C sau khi session/uow sẵn sàng;
Phase A không tạo bảng hoặc migration giả.

## Người nhận và checks bàn giao

- Nghĩa/Anh: dùng capabilities `create`, `receive_status`, `status_query`,
  `terminal`, `approval`; thiếu coverage trả MISSING_REQUIRED_CAPABILITY.
  Các samples sync/interactive/create-only/provider-event/query-only đã có.
- Dũng: dùng fake deterministic normalization và event mapping; ID inbox/thời gian
  được seed rõ. Chốt context và detailed snapshot trước production normalization.
- Chí Hoàng: schema/ref/hash/samples sẵn sàng để đối chiếu shared exports; root
  routing, migrations, auth, transport, core MCP không bị sửa trong lane này.

Tests kiểm tra scope isolation, namespace/purpose, schema sai, missing version,
order metadata, drift/pinned snapshot, coverage và hash. Chưa test DB apply,
duplicate/quarantine persistence, delta reconciliation, HTTP hay MCP thật.
Các yêu cầu này chỉ được ghi file; chưa gửi thông báo cho chat/thành viên khác.
