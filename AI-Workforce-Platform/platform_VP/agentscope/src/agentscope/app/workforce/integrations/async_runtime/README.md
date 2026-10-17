# async_runtime — API/event/workflow v1.4

Chủ sở hữu: **Nguyễn Chí Hoàng**. Branch: `feat/wf-foundation`.
Task bổ sung của owner: **NCH-13–NCH-16**; chọn phần tương ứng phạm vi folder dưới đây.

Đọc [kế hoạch triển khai](../../../../../../docs/workforce/KE_HOACH_TRIEN_KHAI.md) và [bàn giao cá nhân](../../../../../../docs/workforce/handoffs/nguyen-chi-hoang/README.md) trước khi code. Đặc tả chung nằm ở mục 17; ranh giới ownership ở 5.3 và task chi tiết trong phần mang tên owner. Các đường dẫn link tính từ folder này.

Phạm vi: Composition và adapter AgentScope/business; core hook/migration chỉ Chí Hoàng tích hợp.

Đã có `_bootstrap.py`: mở Workforce SQL pool, tạo canonical UOW, identity,
route/grant, durable jobs, provider auth và hai signal adapters; app lifespan
nhận bootstrap qua tham số opt-in. `_runtime_adapter.py`,
`_business_bridge.py`, `_workers.py` vẫn là output của C4–C7 sau khi các owner
bàn giao production adapters.

Nguyên tắc triển khai:

- Một role AREA_MANAGER, Scope đủ tenant/domain/area/manager và audience cư dân; không route theo payload tự khai.
- Dùng DTO/ports chung; không import private service hoặc ghi bảng module khác. uow đi xuyên inbox → workflow/public event → trigger khi cần atomicity.
- Customer request/reply POST ưu tiên `200`, chỉ `202/watch_request` khi hết thời gian chờ; response luôn có `workflow_state` và `next_action`. Response-only read-only có thể auto-close; interactive dùng reply/approval/explicit close; Provider Event/SSE tracking chỉ dùng khi operation thật sự pending.
- Tự viết test trong vùng test được giao, dùng fake port khi module khác chưa có. Chỉ đánh dấu live integration khi có bằng chứng thật.
- Cần đổi contract/migration/core/global frontend thì ghi INTEGRATION_REQUEST trong handoff; Chí Hoàng tích hợp file chung.

Bootstrap C1 không tự mount endpoint và không khởi động fake worker. Production
API/worker chỉ được bật sau các gate tuần tự ghi trong handoff Phase C.

## Composition sau Phase D/D4

`build_phase_c_runtime` hiện ghép production graph C1–D4 với cùng
`foundation.uows` và mount ba router: workflow, execution và manager release.
Deployer phải cấp thêm ba dependency không được phép dùng fake:

- `release_tool_resolver(scope, tool_version_id, uow)`;
- `release_policy_resolver(scope, policy_ref, uow)`;
- `release_context_resolver(scope)`.

Hai resolver đầu phải đọc/lock canonical owner record qua đúng UOW được truyền.
Context release lấy từ cấu hình server, không lấy từ request body. Manager
release API nằm dưới `/workforce/v1/manager/agent-releases`; đây không phải API
đối tác. Bootstrap Leader chỉ chấp nhận current published/enabled/non-archived
version, còn workflow đã chạy tiếp tục dùng exact version/protocol pin đã lưu.
Retention reader đối chiếu cả workflow, checkpoint và durable tool-call; group
được sở hữu bởi workflow, còn operation hiện không mang agent version riêng.
`evaluation_jobs` trong runtime là `ReleaseAwareEvaluationJobService`: đăng ký
frozen evaluation, release candidate và durable evaluation job trong cùng UOW.
Khi sửa draft đã có candidate, caller truyền `expected_candidate_revision`;
revision cũ bị từ chối bằng CAS, không ghi đè candidate mới hơn.

Alembic head tương ứng là `0011_workforce_releases`. Gate và trạng thái tích hợp
nằm tại `docs/workforce/handoffs/nguyen-chi-hoang/PHASE_D_D4_INTEGRATION.md`.
