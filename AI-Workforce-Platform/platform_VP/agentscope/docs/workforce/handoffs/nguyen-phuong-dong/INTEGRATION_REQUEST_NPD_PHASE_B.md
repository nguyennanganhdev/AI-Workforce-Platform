# Integration request — NPD Phase B → C

Ngày: 2026-10-10. Producer: Registry / Nguyễn Phương Đông.
Baseline: develop2@53a139b. Output độc lập: [PHASE_B.md](PHASE_B.md).
Đây là yêu cầu nối composition, chưa xác nhận shared contract đã được đổi.

## Chí Hoàng — persistence và composition

- Adapter `AsyncProtocolRepository` nhận full Scope, kiểm tra unique immutable
  key/hash, atomic CAS current pointer/enable và dùng session/UOW chung.
  Không commit UOW caller. Publish không tự enable hoặc xóa pin của job cũ.
- Metadata migration đã ghi trong PHASE_B; Registry không tạo migration hoặc
  dùng fake repo trong production khi session/UOW chưa được chốt.
- Giữ shared AsyncProtocolPort; inject callback async
  `load_event_context(ActorContext, ProviderEventEnvelope)` trả tuple
  `(tenant_id, provider_integration_id, inbox_event_id, received_at)` từ server.
  Callback phải authorize actor với scope/integration đã bind và kiểm tra đúng
  envelope persisted. Không lấy metadata từ body hoặc seed một inbox cho mọi event.
- Context DTO đề xuất ở request Phase A vẫn chờ chốt. Khi owner bổ sung shared
  DTO/ports/schema/types, thay adapter; không công bố context wire song song.

## Dũng — adapter Execution/Registry

- Sau resolve operation, bind service bằng Scope trên operation. Đọc policy
  qua `get_detailed_snapshot(operation.protocol_snapshot)`; exact version/hash,
  không lấy current config thay pin cũ.
- Normalizer trả shared NormalizedJobEvent. Processor còn dictionary status/
  order_mode/terminal và hooks normalize_creation_result/validate_envelope/
  validate_transition ngoài port; cần chốt adapter/policy trước thay fake runtime.
- Order/event_mode/transitions/terminal/timeout nằm trong detailed snapshot;
  Registry không tự apply/buffer/quarantine hoặc cập nhật workflow.
- Integration tests cần inbox ID/time persisted, hai tenant/integration trùng
  external_job_id, grant revoked, forged hash, disable/drift với job cũ và retry
  giữ metadata. Phase B chỉ dùng fake persistence/auth deps.

## Chí Hoàng / frontend — readiness và shell

- UI export EventChannelsPanel/EventChannelView tại event_channels/index.ts;
  inject channels/loading/error/onRetry. Không có route/transport/token provider mới.
- Chốt API projection create_ready/provider_events_ready/status_query_ready/
  correlation_ready/blockers với auth/binding thật. View model không thay DTO shared.
- Không render credential/raw provider error; reception cho job đã pin độc lập
  enable call mới. Không suy readiness chỉ từ capabilities.

Không gửi thông báo sang chat/thành viên khác trong lượt này. Gate endpoint MCP/
SDK/Skills giữ nguyên; Phase B protocol không tự gỡ gate đó.
