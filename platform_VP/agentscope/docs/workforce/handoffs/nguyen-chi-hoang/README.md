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

Đọc mục 2.6–2.7, 5.3, 6.7 và toàn bộ mục 17 của [kế hoạch 1.4.3](../../KE_HOACH_TRIEN_KHAI.md). Giữ nguyên scope/mapping v1.3 và contract hai ticket/hộp chat v1.4.3. Mọi response có `workflow_state` + `next_action`: response-only read-only có thể auto-close; interactive dùng reply/approval/explicit close; external-tracking và Provider Event/SSE chỉ dùng khi operation pending. `202` chỉ là HTTP timeout fallback. V1 không có HTTP sender từ platform sang endpoint đối tác.

Owner Nguyễn Chí Hoàng bổ sung **NCH-13–NCH-16**: contracts async, durable jobs/signals, provider auth, SSE transport và tích hợp runtime. Thực hiện cả task cũ còn thiếu và task mới; cập nhật STATUS.md, không đánh dấu hoàn thành từ scaffold.

- [ ] **NCH-13 — Contracts API/event:** Chốt DTO/ports/schema theo mục 17.3–17.4, gồm external_ticket_id, TicketConversationBinding, binding errors và event projection. Mọi request result phải có `workflow_state` + `next_action`; persisted-result/`wait_for_result` trả `200` khi xong và `202/watch_request` khi pending. Contract biểu diễn response-only, interactive và external-tracking mà không có field lĩnh vực cố định; Provider Event là capability tùy chọn. Close trả `200/none`; read-only auto-close theo policy không gọi close. Xuất types/fake hai ticket sớm.
- [ ] **NCH-14 — Durable transport và xác thực:** scoped completion signal cho bounded-wait và SSE notification/recovery; ProviderAuth/event worker chỉ dùng cho integration external-tracking. Kết quả chuẩn đọc DB, không giữ transaction khi chờ. Response-only/interactive không tạo queue/timer/Event dependency giả; không viết HTTP sender tới đối tác.
- [ ] **NCH-15 — Nối runtime và migration:** integrations/async_runtime/ nối worker handlers, RuntimeContinuationPort, AgentScope wake/session/parked HITL và business ticket bridge. Chỉ người này sửa core/lifespan/business/migration thật. Giữ owner/audience, scope revalidation và state qua restart, thống nhất metadata export của các folder con; không ghi trực tiếp bảng inbox/operation/workflow module khác.
- [ ] **NCH-16 — Bàn giao tích hợp và vận hành:** test cả ba pattern, mọi next_action, `200/202`, retry, SSE optional/reconnect và Provider signature ở ca tracking. OpenAPI/sample có read-only, plan/booking sync, async operation và một user có hai external ticket/conversation; schema không nhận internal group/ticket/conversation để route. Proxy timeout lớn hơn `PARTNER_TURN_WAIT_SECONDS`. Nêu rõ mọi endpoint do platform host; đối tác không phải dựng receiver.

Các thư mục v1.4 đã chuẩn bị cho bạn:

- [src/agentscope/app/workforce/contracts/async_api/](../../../../src/agentscope/app/workforce/contracts/async_api/README.md) — DTO/ports/events/schema dùng chung mục 17.4; chỉ chủ folder được sửa.
- [src/agentscope/app/workforce/foundation/event_delivery/](../../../../src/agentscope/app/workforce/foundation/event_delivery/README.md) — Tên scaffold cũ; provider credential guard, durable jobs/triggers, SSE signal/recovery; không HTTP sender outbound.
- [src/agentscope/app/workforce/integrations/async_runtime/](../../../../src/agentscope/app/workforce/integrations/async_runtime/README.md) — Composition và adapter AgentScope/business; core hook/migration chỉ Chí Hoàng tích hợp.
- [examples/web_ui/frontend/src/features/workforce/shared/event_transport/](../../../../examples/web_ui/frontend/src/features/workforce/shared/event_transport/README.md) — Transport fetch-SSE/token refresh/cursor; không chứa quy tắc ticket.
- [examples/web_ui/frontend/src/features/workforce/shell/delivery_monitor/](../../../../examples/web_ui/frontend/src/features/workforce/shell/delivery_monitor/README.md) — Tên scaffold cũ; theo dõi SSE/replay/cursor và event backlog theo manager scope.
- [tests/workforce/foundation/async_api/](../../../../tests/workforce/foundation/async_api/README.md) — Kiểm tra auth/UOW/lease/fence, SSE ownership/replay và migration.
- [scripts/workforce/event_delivery/](../../../../scripts/workforce/event_delivery/README.md) — Tên scaffold cũ; công cụ event replay/retention có dry-run và scope.
- [deploy/workforce/event_delivery/](../../../../deploy/workforce/event_delivery/README.md) — Tên scaffold cũ; runbook SSE/proxy/recovery/rotation/restore.
- [docs/workforce/handoffs/nguyen-chi-hoang/async_api/](async_api/README.md) — OpenAPI/guide cho Customer API, Provider Event API, SSE/history và close.

Bắt đầu bằng đọc hợp đồng 17.3–17.4, viết logic và test với fake port thuộc module mình, rồi bàn giao signature/schema/hook request cho owner cung cấp. Các fake chỉ trong test/demo, production không trả thành công giả. Mỗi người làm trong branch/worktree riêng; migration/core/shared contracts chỉ Chí Hoàng sửa.

