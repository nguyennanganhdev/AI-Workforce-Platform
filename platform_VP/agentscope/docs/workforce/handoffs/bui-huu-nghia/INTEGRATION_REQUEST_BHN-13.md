# BHN-13 — AsyncProtocolPort coverage và fake protocol

- **Task ID:** BHN-13; liên quan BHN-03/07/12/14.
- **Người gửi / người nhận:** Bùi Hữu Nghĩa → Nguyễn Phương Đông; Nguyễn Chí Hoàng chốt export DTO/port chung.
- **Trạng thái:** chờ review và fake protocol nhịp A của Đông; không sửa Registry hoặc fixture chung.

## Hiện trạng và lý do

Cập nhật sau pull `a99d506`: port đã có get_snapshot(scope, tool_version_id) -> AsyncProtocolSnapshotRef và validate_capability_coverage(protocol_snapshot, required_capabilities) -> None. Chữ ký dưới đây là đề xuất mở rộng additive, chưa callable. Ref hiện chỉ có ID/version/hash/capabilities, chưa chứa readiness/correlation/ordering; Registry implementation và fake vẫn chưa có.

AsyncProtocolSnapshotRef đã export Python nhưng chưa có trong SCHEMA_MODELS/JSON Schema bundle. Đề nghị Chí Hoàng bổ sung export schema (và TypeScript tương ứng nếu cần) để mẫu protocol trong canonical_samples.json được kiểm tra bằng schema chung; test protocol hiện skip có lý do, không tạo schema copy tại Builder.

Registry implementation hiện là scaffold; Foundation đã chốt boundary kiểm tra capability subset. Builder còn cần kiểm tra create + tracking và readiness trên metadata thật, không dùng prompt làm bằng chứng.

## File/module của người nhận cần sửa

- `registry/event_protocols/`: snapshot/coverage implementation và fake exports theo ownership.
- `contracts/async_api/`: Chí Hoàng hiện thực interface/DTO sau khi thống nhất.
- Handoff Đông chứa protocol requirements/mapping và sample snapshots để Nghĩa/Anh/Dũng dùng; test double của Nghĩa sẽ nằm trong `tests/workforce/builder/`.

## Port/export/hook đề xuất

Giữ `async get_snapshot(scope, tool_version_id) -> AsyncProtocolSnapshotRef` canonical. Boundary hiện không khai báo null; semantics no-protocol cho tool đồng bộ vẫn cần owner chốt (null sẽ là thay đổi signature). Không đồng nhất no-protocol với inaccessible/stale/error. Builder chỉ lấy snapshot khi cần, không ép tool terminal-only có protocol.

Method mới đề xuất:

```text
async validate_coverage(
    scope, requirements, bindings, policy_candidate, expected_catalog_revision
) -> CapabilityCoverageReport
```

`expected_catalog_revision` ở đây là **tool catalog revision**. Report đề xuất:

```text
catalog_revision: int >= 0
required_covered: bool
checks[]:
  requirement_id: str
  satisfied: bool
  reason: str
  tool_version_ids: UUID[]
  protocol_refs[]: {protocol_id, protocol_version, schema_hash, tool_version_id}
missing_required[]: requirement_id
missing_optional[]: requirement_id
blockers[]: {code, requirement_id?, tool_version_id?, message}
```

Lists missing là kết quả đánh giá chứ không sửa requirements. Report không có raw secret/payload; schema hash và references không thay scope authorization. Không coi required_covered=true là bằng chứng mọi lần gọi provider tương lai thành công.

## Input/output + error + scope

Snapshot cần đủ protocol ID/version/hash, tool version, capability và effect đã kiểm tra, create/result mapping để phân biệt terminal/pending/unknown, correlation/client_reference support, channel readiness (Provider Event/status-query), event schemas/facts, ordering/transition và timeout constraints. Trường canonical do Đông + Chí Hoàng chốt, Builder không tạo AsyncToolProtocol riêng.

- Terminal-only lookup hoặc booking confirmed: không buộc có protocol tracking/event channel.
- Có thể pending + cam kết until_terminal/until_user_close: cần correlation và ít nhất một channel đúng scope thực sự sẵn sàng; chỉ tool create thì missing tracking.
- Event-only dùng needs_attention khi timeout nếu không có query; query-only hợp lệ không cần provider push. Event+query fallback phải có cả hai capability.
- Protocol drift/disabled connection/stale revision có blocker rõ. Optional missing được tách khỏi required missing. Error inaccessible không tiết lộ tài nguyên scope khác.
- MISSING_REQUIRED_CAPABILITY cho thiếu capability bắt buộc; code stale/protocol drift chưa có export cần thống nhất. Không sửa pin operation cũ vì catalog mới thay đổi.

## Transaction / retry / concurrency

Snapshot/coverage read không tạo operation/workflow hoặc gọi tool ghi. Report ghi revision để Builder recheck bindings trước draft; Lifecycle revalidate khi ghi/publish. Registry snapshot không được mutate tại chỗ. Không retry tạo tool/provider job để thử protocol.

## Ví dụ caller trong module của tôi

```python
report = await async_protocol_port.validate_coverage(
    scope, requirements, bindings, policy_candidate, tool_catalog_revision,
)
if not report.required_covered:
    # Store a blocked proposal; present missing capabilities for user action.
    # Do not create a draft or silently reduce the tracking goal.
    ...
```

Pseudo-caller phía trên là method additive chưa có. Caller theo boundary hiện tại phải lấy ref bằng get_snapshot(scope, tool_version_id), rồi gọi validate_capability_coverage(ref, required_capabilities); method không nhận scope nên không được dùng ref client cung cấp. Check subset này không thay thế readiness/correlation/policy checks còn chờ Đông.

## Test chứng minh yêu cầu / fake cần bàn giao

Đề nghị fake/snapshot examples có các ca dưới đây, dùng cùng interface/DTO canonical. Không cần service đối tác thật để bàn giao nhịp A:

| Fake input | Kết quả cần quan sát |
|---|---|
| Read terminal-only, requirement lookup | covered, không yêu cầu event/query |
| Booking terminal-only, requirement confirmed | covered, explicit close, không ép polling |
| Create-only, requirement create_only | covered, không cam kết terminal |
| Create-only, requirement tracking | missing_required tracking |
| Pending + event-ready + correlation | covered với event protocol ref/hash |
| Pending + status-query-ready + correlation | covered query-only, không cần provider push |
| Pending + event-ready, thiếu correlation | blocked/missing, không đoán owner từ payload |
| Pending + event và query fallback | covered; snapshot giữ cả hai đường |
| Tool/protocol disabled hoặc revision drift | blocker/stale, không reuse khả dụng giả |
| Tài nguyên manager khác cùng area | bị từ chối, không lộ metadata |

## Phần đã hoàn thành và đang chờ

Đã có [policy samples](phase_a/samples.json) và test schema độc lập trong vùng Nghĩa; đây không phải fake Registry/AsyncProtocolPort đã được chứng nhận. Chờ snapshot/coverage contract và fake của Đông để Phase B implement semantic checks. Chưa thực hiện normalize event, ingress hoặc runtime worker.
