# event_delivery — API/event/workflow v1.4

Chủ sở hữu: **Nguyễn Chí Hoàng**. Branch: `feat/wf-foundation`.
Task bổ sung của owner: **NCH-13–NCH-16**; chọn phần tương ứng phạm vi folder dưới đây.

Đọc [kế hoạch triển khai](../../../../../../docs/workforce/KE_HOACH_TRIEN_KHAI.md) và [bàn giao cá nhân](../../../../../../docs/workforce/handoffs/nguyen-chi-hoang/README.md) trước khi code. Đặc tả chung nằm ở mục 17; ranh giới ownership ở 5.3 và task chi tiết trong phần mang tên owner. Các đường dẫn link tính từ folder này.

Phạm vi: Tên folder là scaffold cũ. Triển khai provider credential guard, durable jobs/triggers, SSE notification/recovery và transport auth; không lưu workflow của Huy Hoàng và không gửi HTTP outbound tới đối tác.

File dự kiến khi triển khai: `_auth.py`, `_signals.py`, `_worker.py`, `_recovery.py`, `_repository.py`, `_tables.py`. Đây chỉ là gợi ý chia file; chưa có code được tạo trong folder.

Nguyên tắc triển khai:

- Một role AREA_MANAGER, Scope đủ tenant/domain/area/manager và audience cư dân; không route theo payload tự khai.
- Dùng DTO/ports chung; không import private service hoặc ghi bảng module khác. uow đi xuyên inbox → workflow/public event → trigger khi cần atomicity.
- Customer request/reply POST ưu tiên `200`, chỉ `202/watch_request` khi hết thời gian chờ; response luôn có `workflow_state` và `next_action`. Response-only read-only có thể auto-close; interactive dùng reply/approval/explicit close; Provider Event/SSE tracking chỉ dùng khi operation thật sự pending.
- DB public event log là nguồn bền vững; Redis/outbox chỉ đánh thức worker/SSE reader. Không xây subscription endpoint, HTTP sender hoặc retry delivery tới backend đối tác.
- Tự viết test trong vùng test được giao, dùng fake port khi module khác chưa có. Chỉ đánh dấu live integration khi có bằng chứng thật.
- Cần đổi contract/migration/core/global frontend thì ghi INTEGRATION_REQUEST trong handoff; Chí Hoàng tích hợp file chung.

## Trạng thái Phase B

Đã triển khai phần độc lập của NCH-14:

- `DurableJobService` và `DurableJobWorker`: enqueue idempotent theo owner,
  `not_before`, claim/reclaim lease, fencing token, heartbeat, retry và handler
  isolation. Persistence đi qua `DurableJobRepository`; fake chỉ nằm trong
  `tests/`. PostgreSQL repository và migration thuộc Phase C.
- `JobPort.enqueue_provider(...)`: đường enqueue additive cho provider event
  đã xác thực khi operation chưa resolve ra manager Scope. Namespace bắt buộc
  có `tenant_id` và `provider_integration_id`, không đọc từ public payload.
- `MessageBusPublicEventSignal` và
  `MessageBusRequestCompletionSignal`: channel được hash từ đủ manager Scope
  và resource ID. Signal chỉ đánh thức; event/result chuẩn phải đọc lại từ DB.
- `ConversationSseService`: replay-first qua `ConversationEventPort`, sau đó
  đợi signal và định kỳ catch-up; heartbeat không mang business event ID.
  `SseFrame` encode UTF-8 và chặn newline injection ở `id`/`event`.

Chưa có ở Phase B: Alembic/SQL repository, FastAPI route, provider signature,
retention/410 repository và composition root. Không có HTTP sender outbound.
