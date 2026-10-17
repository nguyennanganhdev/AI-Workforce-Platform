# Lifecycle release — D4

Owner: Phó Tiến Anh

`SqlReleaseService(uows, validator, identity, clock=...)` yêu cầu Foundation
UOW/IdentityPort và `ReleaseValidator` cụ thể. Validator phải đọc current
tool/protocol/policy trong UOW được truyền vào và lock/CAS dependency heads
đến commit. Không dùng independent read của AsyncDraftValidator để tuyên bố
publish atomic với thay đổi Registry. Không gọi model/provider trong callback.

- `stage_candidate(scope, frozen, expected_revision=None, uow=None)` nhận
  snapshot của canonical draft đã được authorize. Update dùng revision CAS;
  khi truyền UOW thì không tự commit. Canonical draft writer phải gọi hook
  này trong **cùng transaction với mọi thay đổi draft**, hoặc dùng bảng
  candidate này làm nguồn revision chuẩn; không để một mirror cập nhật trễ.
- `publish_selected(scope, selections, current_server_context, command_id)`
  chỉ publish đúng danh sách, một selection/agent. Khóa deployment/draft và
  evaluation cases, validate lại dependency và committed evidence, giữ nguyên
  candidate version ID/hash rồi ghi version/deployment/command cùng commit.
- `rollback(scope, agent_id, version_id, expected_revision, context, command_id)`
  kiểm tra ownership và retained evaluation/current compatibility. Không tạo
  version mới và không thay checkpoint/pin của workflow.
- `set_availability(..., archived=..., enabled=...)`: archive ngăn chọn mới;
  enabled=False là disable/revoke agent và chặn continuation. Không xóa version,
  snapshot, report hoặc protocol.
- `list_candidates/get_version/get_deployment` cung cấp PublishedCatalogPort.
  Catalog chỉ trả current published version đúng Scope, đủ capability và current
  dependency còn hợp lệ. Exact version lookup vẫn đọc được sau archive/disable.
- `PinnedVersionAuthorization(delegate, releases)` bọc WorkflowAuthorization:
  giữ kiểm tra actor/route/consent của delegate, kiểm tra mọi agent/version và
  toàn bộ protocol refs từ checkpoint, cho archive/old pin tiếp tục; disable
  chặn model/tool. Khi PHH truyền UOW ở final commit, giữ deployment lock đến
  commit. Provider fact sau revoke vẫn persist qua Execution nhưng không phát
  public message/wakeup. Execution vẫn kiểm tra binding/tool/credential riêng.
- `retention_references(scope, version_id, usage_reader)` hỏi usage qua port
  do PHH cung cấp. Không truy cập bảng workflow/checkpoint của PHH. Bản D4 giữ
  toàn bộ version/evaluation vô thời hạn và không có purge/TTL API; việc rút
  ngắn retention cần usage/replay/audit policy riêng và review của owner.

`ReleaseContext` lấy từ cấu hình hiện hành phía server; resolve manager Scope
bằng `IdentityPort.resolve_manager` và enforce owner action trước gọi mutation.
Không nhận Scope/context do partner/client tự khai. Service recheck membership
trong transaction, kể cả idempotent replay.

`get_release_metadata()` trả bốn bảng additive riêng. Không tự create_all trong
production; Foundation tạo migration và wiring. `phase_d_schema_bundle()` là
schema local `pta-release-1`, chưa promote shared DTO. Deployment ID trong seam
này chính là stable agent ID và revision bắt đầu từ 0 khi chưa publish.

Seam này không hiện thực toàn bộ DraftPort/AgentReusePort/BuildBatchPort hay
business-key deduplication. Không coi candidate staging là canonical identity
reservation. Xem [bàn giao D4](../../../../../../docs/workforce/handoffs/pho-tien-anh/PHASE_D_D4.md)
và [yêu cầu tích hợp](../../../../../../docs/workforce/handoffs/pho-tien-anh/INTEGRATION_REQUEST_PTA_D4.md).
