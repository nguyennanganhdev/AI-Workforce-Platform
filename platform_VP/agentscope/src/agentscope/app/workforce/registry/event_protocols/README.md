# event_protocols — API/event/workflow v1.4

Chủ sở hữu: **Nguyễn Phương Đông**. Branch: `feat/wf-registry`.
Task bổ sung của owner: **NPD-10–NPD-12**; chọn phần tương ứng phạm vi folder dưới đây.

Đọc [kế hoạch triển khai](../../../../../../docs/workforce/KE_HOACH_TRIEN_KHAI.md) và [bàn giao cá nhân](../../../../../../docs/workforce/handoffs/nguyen-phuong-dong/README.md) trước khi code. Đặc tả chung nằm ở mục 17; ranh giới ownership ở 5.3 và task chi tiết trong phần mang tên owner. Các đường dẫn link tính từ folder này.

Phạm vi: Protocol snapshots/capabilities và deterministic normalization; không nhận HTTP Provider Event request hoặc ghi inbox.

Files hiện có: `_models.py`, `_repository.py` (persistence boundary),
`_normalizer.py`, `_service.py`. SQL tables/migration/composition được nối Phase C.

Nguyên tắc triển khai:

- Một role AREA_MANAGER, Scope đủ tenant/domain/area/manager và audience cư dân; không route theo payload tự khai.
- Dùng DTO/ports chung; không import private service hoặc ghi bảng module khác. uow đi xuyên inbox → workflow/public event → trigger khi cần atomicity.
- Customer request/reply POST ưu tiên `200`, chỉ `202/watch_request` khi hết thời gian chờ; response luôn có `workflow_state` và `next_action`. Response-only read-only có thể auto-close; interactive dùng reply/approval/explicit close; Provider Event/SSE tracking chỉ dùng khi operation thật sự pending.
- Tự viết test trong vùng test được giao, dùng fake port khi module khác chưa có. Chỉ đánh dấu live integration khi có bằng chứng thật.
- Cần đổi contract/migration/core/global frontend thì ghi INTEGRATION_REQUEST trong handoff; Chí Hoàng tích hợp file chung.

Phase A đã export `AsyncToolProtocol`, `EventMapping`: cấu hình có validation,
snapshot reference/hash và schema/samples. Xem
[PHASE_A.md](../../../../../../docs/workforce/handoffs/nguyen-phuong-dong/PHASE_A.md).
Fake `AsyncProtocolPort` và contract tests nằm trong lane test Registry.
Phase B bổ sung `AsyncProtocolService`, `AsyncProtocolRepository` và deterministic
normalizer production. Service nhận Scope đã resolve và callback đọc metadata inbox
đã xác minh, không tự tạo metadata. Fake repository chỉ trong tests; PostgreSQL,
auth/inbox adapter, API/worker/migration/composition được nối ở Phase C. Xem
[PHASE_B.md](../../../../../../docs/workforce/handoffs/nguyen-phuong-dong/PHASE_B.md).
