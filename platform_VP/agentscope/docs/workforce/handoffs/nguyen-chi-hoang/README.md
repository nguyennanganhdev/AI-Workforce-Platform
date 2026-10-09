# Bàn giao — Nguyễn Chí Hoàng

Branch đề xuất: `feat/wf-foundation`. Đầu việc: **NCH-01–NCH-16**.

Phạm vi: contracts single/batch, AREA_MANAGER + domain/area/account, partner mapping/grant và tích hợp AgentScope.

[Kế hoạch và hợp đồng chung](../../KE_HOACH_TRIEN_KHAI.md) là tài liệu đầu vào cho AI. Gửi cả file kế hoạch và nói rõ: “Tôi là Nguyễn Chí Hoàng”.

Khi triển khai, tạo `STATUS.md` theo mẫu ở mục 16. Mỗi yêu cầu đổi contract/hook/file chung ghi vào `INTEGRATION_REQUEST_<task-id>.md` theo mục 14.

Hiện tại chưa có task được đánh dấu hoàn thành; việc tạo thư mục này không chứng minh module đã được code/test.

Nguyên tắc batch của bản 1.2 được giữ ở bản 1.3: Contracts phân biệt AgentManifest của một agent, AgentBuildBatch theo dõi nhiều agent và RunGroup chỉ hình thành khi có request. Tích hợp BuildBatchPort; không tạo team template/version/deployment từ Builder. Đọc mục 2.3, 2.5 và 6 của kế hoạch trước khi code; nội dung này thay thế cách hiểu team artifact ở bản trước. Đây là đầu việc cần triển khai, chưa phải tính năng đã hoàn thành.

## Cập nhật bắt buộc theo kế hoạch 1.3

Giữ một role `AREA_MANAGER` và chọn domain/area. Scope là `(tenant_id, domain_id, area_id, manager_account_id)`; partner request phải resolve mapping/grant tới đúng tài khoản đích trước khi chạy Leader, không broadcast theo area. Actor đối tác/cư dân không phải owner platform. Đọc mục 2.6 và hợp đồng mục 6; chỉ dẫn cũ yêu cầu bỏ domain/area không còn hợp lệ.

NCH-03/04 giữ AREA_MANAGER và chọn domain/area; NCH-12 sở hữu verification, PartnerRoutingPort, grant/xác nhận mapping, UI shell/partner-routes và legacy business bridge. Không viết dispatch/run của Huy Hoàng. NCH-02/08/11 cập nhật Scope/ActorContext, uow, migration/backfill và uniqueness theo tài khoản.

Các bổ sung này là kế hoạch cần triển khai, không phải xác nhận code hoặc test đã hoàn thành.


## Bổ sung bắt buộc theo kế hoạch 1.4 — API và sự kiện

Đọc mục 2.7, 5.3, 6.7 và toàn bộ mục 17 của [kế hoạch 1.4](../../KE_HOACH_TRIEN_KHAI.md). Giữ nguyên scope/mapping v1.3. POST nhận việc rồi kết thúc; workflow chờ bằng checkpoint trong DB, callback nối đúng job/ticket/chat, public event log hỗ trợ replay và outbox chịu retry thông báo. ACK hoặc ngắt SSE không đóng ticket.

Owner Nguyễn Chí Hoàng bổ sung **NCH-13–NCH-16**: contracts async, delivery/outbox, auth hai chiều, SSE transport và tích hợp runtime. Thực hiện cả task cũ còn thiếu và task mới; cập nhật STATUS.md, không đánh dấu hoàn thành từ scaffold.

- [ ] **NCH-13 — Contracts API/event:** Trong contracts/async_api/ chốt DTO/ports, error codes, event envelope, signature samples, uow và JSON Schema theo mục 17.3–17.4. Mở rộng request/reply/close và grant operations; xuất types qua shared/contracts. Bàn giao ngay để năm người code bằng fake; không định nghĩa provider protocol thay Đông.
- [ ] **NCH-14 — Durable delivery và xác thực:** foundation/event_delivery/ triển khai ProviderAuthPort, DeliveryPort, subscription/verified endpoint, outbound signing/rotation, worker lease/fence/retry/dead-letter, scheduled jobs và recovery scan. Dùng wf_outbox/JobPort đã có theo thiết kế, không tạo queue riêng thiếu transaction. shell/delivery_monitor/ và shared/event_transport/ cung cấp UI delivery theo scope và fetch-SSE/cursor/refresh transport chung; không viết public conversation event store của Huy Hoàng.
- [ ] **NCH-15 — Nối runtime và migration:** integrations/async_runtime/ nối worker handlers, RuntimeContinuationPort, AgentScope wake/session/parked HITL và business ticket bridge. Chỉ người này sửa core/lifespan/business/migration thật. Giữ owner/audience, scope revalidation và state qua restart, thống nhất metadata export của các folder con; không ghi trực tiếp bảng inbox/operation/workflow module khác.
- [ ] **NCH-16 — Bàn giao tích hợp và vận hành:** tests/workforce/foundation/async_api/ kiểm tra auth/signature/uow/fence/delivery race và migration. scripts/workforce/event_delivery/, deploy/workforce/event_delivery/ có dry-run replay/retention, health/metrics/proxy/rollback runbook; cấu hình .env.example/compose khi triển khai. docs/workforce/handoffs/nguyen-chi-hoang/async_api/ chứa OpenAPI guide, sample clients và nghĩa ACK/reconnect/close. Nêu rõ app đối tác phải tự triển khai receiver.

Các thư mục v1.4 đã chuẩn bị cho bạn:

- [src/agentscope/app/workforce/contracts/async_api/](../../../../src/agentscope/app/workforce/contracts/async_api/README.md) — DTO/ports/events/schema dùng chung mục 17.4; chỉ chủ folder được sửa.
- [src/agentscope/app/workforce/foundation/event_delivery/](../../../../src/agentscope/app/workforce/foundation/event_delivery/README.md) — Provider credential guard, durable delivery/outbox, signing/retry/recovery; không lưu workflow của Huy Hoàng.
- [src/agentscope/app/workforce/integrations/async_runtime/](../../../../src/agentscope/app/workforce/integrations/async_runtime/README.md) — Composition và adapter AgentScope/business; core hook/migration chỉ Chí Hoàng tích hợp.
- [examples/web_ui/frontend/src/features/workforce/shared/event_transport/](../../../../examples/web_ui/frontend/src/features/workforce/shared/event_transport/README.md) — Transport fetch-SSE/token refresh/cursor; không chứa quy tắc ticket.
- [examples/web_ui/frontend/src/features/workforce/shell/delivery_monitor/](../../../../examples/web_ui/frontend/src/features/workforce/shell/delivery_monitor/README.md) — Subscription và trạng thái gửi lỗi/retry theo manager scope.
- [tests/workforce/foundation/async_api/](../../../../tests/workforce/foundation/async_api/README.md) — Kiểm tra auth/UOW/lease/fence/retry, subscription ownership và migration.
- [scripts/workforce/event_delivery/](../../../../scripts/workforce/event_delivery/README.md) — Công cụ replay/retention có dry-run và scope; không tự chạy xóa dữ liệu.
- [deploy/workforce/event_delivery/](../../../../deploy/workforce/event_delivery/README.md) — Runbook/proxy/retry/rotation/restore; giá trị thật cấu hình khi triển khai.
- [docs/workforce/handoffs/nguyen-chi-hoang/async_api/](async_api/README.md) — Hướng dẫn đối tác từ contracts/OpenAPI: POST/webhook/SSE/history/ACK/close.

Bắt đầu bằng đọc hợp đồng 17.3–17.4, viết logic và test với fake port thuộc module mình, rồi bàn giao signature/schema/hook request cho owner cung cấp. Các fake chỉ trong test/demo, production không trả thành công giả. Mỗi người làm trong branch/worktree riêng; migration/core/shared contracts chỉ Chí Hoàng sửa.

