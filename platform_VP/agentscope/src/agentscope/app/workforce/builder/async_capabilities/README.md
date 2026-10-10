# async_capabilities — API/event/workflow v1.4

Chủ sở hữu: **Bùi Hữu Nghĩa**. Branch: `feat/wf-builder`.
Task bổ sung của owner: **BHN-12–BHN-14**; chọn phần tương ứng phạm vi folder dưới đây.

Đọc [kế hoạch triển khai](../../../../../../docs/workforce/KE_HOACH_TRIEN_KHAI.md) và [bàn giao cá nhân](../../../../../../docs/workforce/handoffs/bui-huu-nghia/README.md) trước khi code. Đặc tả chung nằm ở mục 17; ranh giới ownership ở 5.3 và task chi tiết trong phần mang tên owner. Các đường dẫn link tính từ folder này.

Phạm vi: Requirements và sinh policy theo dõi; reuse/revise, missing capability.

Code hiện có: `_requirements.py` (schema policy theo Tiến Anh), `_models.py` (local readiness/proposal views), `_selector.py` (capability/policy validation, pinned selection và recheck). Root Builder có extraction/reuse/proposal service; không sửa owner khác.

## Phase A — schema nội bộ Builder

`_requirements.py` đã bổ sung `BuildRequirements`, `AgentRequirement`, `CapabilityRequirement` và `HandlingPolicyProposal`. Đây là schema đề xuất nội bộ, tái sử dụng `BusinessProfile`/`WorkforceModel`; chưa thay thế DTO production chung và chưa có selector/service/runtime. `tracking_intent` diễn tả yêu cầu năng lực, không quyết định trạng thái workflow thực tế.

Samples và test nằm tại `tests/workforce/builder/async_capabilities/`. Các điểm cần chốt với owner hợp đồng nằm trong `docs/workforce/handoffs/bui-huu-nghia/INTEGRATION_REQUEST_BHN_PHASE_A.md`.

Nguyên tắc triển khai:

- Một role AREA_MANAGER, Scope đủ tenant/domain/area/manager và audience cư dân; không route theo payload tự khai.
- Dùng DTO/ports chung; không import private service hoặc ghi bảng module khác. uow đi xuyên inbox → workflow/public event → trigger khi cần atomicity.
- Customer request/reply POST ưu tiên `200`, chỉ `202/watch_request` khi hết thời gian chờ; response luôn có `workflow_state` và `next_action`. Response-only read-only có thể auto-close; interactive dùng reply/approval/explicit close; Provider Event/SSE tracking chỉ dùng khi operation thật sự pending.
- Tự viết test trong vùng test được giao, dùng fake port khi module khác chưa có. Chỉ đánh dấu live integration khi có bằng chứng thật.
- Cần đổi contract/migration/core/global frontend thì ghi INTEGRATION_REQUEST trong handoff; Chí Hoàng tích hợp file chung.

Phase B đã có capability checks/UI với fake ports. Query-only chưa có policy event metadata vẫn bị block; không tự đặt event name. Detailed readiness là injected local boundary đang chờ shared accessor. Chưa triển khai HTTP API, worker, migration hoặc tích hợp production. Xem `docs/workforce/handoffs/bui-huu-nghia/PHASE_B.md` để chạy demo/test và đọc điểm nối còn mở.
