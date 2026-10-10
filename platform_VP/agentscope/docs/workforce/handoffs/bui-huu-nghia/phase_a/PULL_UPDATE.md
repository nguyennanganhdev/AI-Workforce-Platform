# Đối chiếu sau pull — Foundation Phase A

Ngày kiểm tra: 10/10/2026. HEAD `a99d506` (merge #38), implementation Foundation ở commit `1ff8fb6`. Không xóa các file handoff/test đang chưa commit của Nghĩa.

## Đã có đầu vào mới

Foundation cung cấp Python contracts/ports, JSON Schema bundle version 1 và TypeScript. Nguồn canonical là `agentscope.app.workforce.contracts`; schema export ở [workforce-v1.schema.json](../../../contracts/generated/workforce-v1.schema.json). Không copy các DTO này vào Builder.

Đã bổ sung [canonical_samples.json](canonical_samples.json) với Scope, ToolDescriptor, ToolBinding, BusinessProfile, AgentManifest và quyết định create/reuse/revise; các mẫu này được kiểm tra bằng schema export trực tiếp, không bằng định nghĩa tương tự do Builder tự tạo. Mẫu AsyncProtocolSnapshotRef mới đối chiếu source Python vì DTO này chưa có trong bundle JSON Schema. Đây là mẫu contract giả, chưa provision model/tool/agent thật.

## Khác biệt cần áp dụng khi code

| Đề xuất/cách hiểu trước | Contract đã pull | Hành động của Builder |
|---|---|---|
| Manifest có agent/model_config | AgentManifest.spec; AgentSpec.model_config_ref | Dùng field canonical; không gửi alias cũ |
| BusinessProfile.execution_policy là object tùy ý | Enum read_only/require_approval/allow_within_policy | Dùng enum từ contract; AgentSpec.execution_policy vẫn là JsonObject khác field này |
| booking/cancel được xem như ToolEffect | ToolEffect=read/write/external_operation | Booking/cancel chỉ là ý định nghiệp vụ trong schema extraction; descriptor effect phải lấy từ Registry, không ép mapping theo tên hành động |
| Revision catalog là opaque string | Catalog/reuse revision là int >=0 | Giữ riêng tool catalog revision và agent catalog revision |
| Snapshot trả toàn bộ protocol | AsyncProtocolSnapshotRef chỉ có protocol_id/protocol_version/schema_hash/tool_version_id/provider_integration_id/capabilities | Ref không chứng minh correlation, readiness, mapping/ordering/timeout chi tiết |
| validate_coverage(scope, requirements, bindings, policy, revision) trả report | validate_capability_coverage(protocol_snapshot, required_capabilities) -> None | Dùng signature hiện tại. Report richer vẫn chỉ là yêu cầu additive, không gọi method chưa có |
| validate_decisions nhận requirements extraction | requirements: Sequence[BusinessProfile] | Map yêu cầu đã làm rõ sang BusinessProfile trước khi gọi; không truyền dict extraction |
| Registry list trả {items,next_cursor} | tuple[tuple[ToolDescriptor,...], cursor] | Service caller unpack tuple; representation HTTP do adapter riêng |

ReuseDecision/ReusedCandidate và BuildItem đã có shape, nhưng nhiều aggregate returns như DraftPort/get_candidate vẫn là object. Chưa đủ để giả định có AgentDraft API thật hay agent catalog service đã chạy.

## Các đầu việc Phase A đã tiến thêm

1. Bàn giao BusinessProfile + manifest + create/reuse/revise samples theo yêu cầu mới của Chí Hoàng ở INTEGRATION_REQUEST_NCH_PHASE_A.md.
2. Có test kiểm tra mẫu DTO bằng export canonical, bắt lỗi agent/spec, model_config/model_config_ref và ToolEffect. Ca protocol_version skip rõ lý do: AsyncProtocolSnapshotRef chưa được đưa vào schema bundle.
3. Cập nhật integration requests từ “chưa có port” thành chữ ký hiện tại → đề xuất phần còn thiếu.
4. Giữ schema extraction/policy local là review artifact vì chưa có counterpart canonical. Không bỏ schema đề xuất rồi coi execution_policy JsonObject đã kiểm tra async policy.

## Chưa được giải quyết bởi pull này

- Chưa có DTO AsyncHandlingPolicy/requirement extraction/model-selection Builder, typed validator hoặc canonical policy persistence/ref semantics. AgentManifest mới chỉ có async_policy_ref và protocol_snapshot_hashes.
- Chưa có BuildModelPort/core adapter ngân sách và credential theo Workforce Scope.
- AsyncProtocolSnapshotRef có Python export nhưng thiếu JSON Schema export; BHN-13 đã bổ sung yêu cầu để kiểm tra mẫu protocol bằng cùng schema chung.
- Registry/Lifecycle vẫn là README; chưa có fake protocol, detailed protocol snapshot, coverage implementation, reuse/draft services.
- AsyncProtocolPort.get_snapshot không khai báo null; tool đồng bộ không có protocol cần owner chốt lỗi/semantics. Builder không gọi port này cho mọi lookup rồi giả định kết quả null hợp lệ.
- validate_capability_coverage không nhận scope; chỉ truyền snapshot do get_snapshot(scope, ...) trả từ scope đã xác minh, không dùng snapshot client gửi. Interface này chỉ kiểm tra capability subset; readiness/correlation/policy compatibility còn cần contracts/implementation của Đông.

## Bằng chứng và bước tiếp theo

Test command từ `platform_VP/agentscope`:

```powershell
& "$env:TEMP\wf-bhn-phase-a-venv\Scripts\python.exe" -B -m unittest discover -s tests/workforce/builder/async_capabilities -p "test_*.py" -v
```

Chạy cả schema proposal và canonical handoff checks. JSON Schema export không chứa mọi Pydantic model_validator hoặc semantic checks; kết quả này không chứng minh auth, uniqueness, readiness, side effect hoặc service runtime. Không chạy lại export script vì file shared/generated do Chí Hoàng sở hữu.

Có thể chuẩn bị/triển khai phần độc lập của một agent bằng public DTO và fake ports trong test ở bước sau. Gate policy/fake liên module vẫn cần owner bổ sung theo BHN-05/12/13; không chờ lại phần DTO Foundation đã cung cấp. Chưa mở rộng sang UI/runtime Phase B trong lần đối chiếu này.
