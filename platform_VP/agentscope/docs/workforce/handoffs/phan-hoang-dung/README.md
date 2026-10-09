# Bàn giao — Phan Hoàng Dũng

Branch đề xuất: `feat/wf-execution`. Đầu việc: **PHD-01–PHD-17**.

Phạm vi: tool execution, booking approval, idempotency, mocks và E2E.

[Kế hoạch và hợp đồng chung](../../KE_HOACH_TRIEN_KHAI.md) là tài liệu đầu vào cho AI. Gửi cả file kế hoạch và nói rõ: “Tôi là Phan Hoàng Dũng”.

Khi triển khai, tạo `STATUS.md` theo mẫu ở mục 16. Mỗi yêu cầu đổi contract/hook/file chung ghi vào `INTEGRATION_REQUEST_<task-id>.md` theo mục 14.

Hiện tại chưa có task được đánh dấu hoàn thành; việc tạo thư mục này không chứng minh module đã được code/test.

Nguyên tắc batch của bản 1.2 được giữ ở bản 1.3: PHD-12 kiểm tra batch tạo các agent độc lập, không tạo group production trước request; Leader chọn subset/chọn chéo batch, reuse không tăng agent/version và approval/booking state không lẫn giữa group. Đọc mục 2.3, 2.5 và 6 của kế hoạch trước khi code; nội dung này thay thế cách hiểu team artifact ở bản trước. Đây là đầu việc cần triển khai, chưa phải tính năng đã hoàn thành.

## Cập nhật bắt buộc theo kế hoạch 1.3

Giữ một role `AREA_MANAGER` và chọn domain/area. Scope là `(tenant_id, domain_id, area_id, manager_account_id)`; partner request phải resolve mapping/grant tới đúng tài khoản đích trước khi chạy Leader, không broadcast theo area. Actor đối tác/cư dân không phải owner platform. Đọc mục 2.6 và hợp đồng mục 6; chỉ dẫn cũ yêu cầu bỏ domain/area không còn hợp lệ.

PHD-01/05/13 kiểm tra manager Scope, route/grant và audience ở từng tool call/consent. Partner approval có endpoint/allowed_decider riêng, không giả danh manager. E2E gồm A/B cùng area, cross-domain, hai cư dân, revoke/remap/replay, worker/result/download isolation.

Các bổ sung này là kế hoạch cần triển khai, không phải xác nhận code hoặc test đã hoàn thành.


## Bổ sung bắt buộc theo kế hoạch 1.4 — API và sự kiện

Đọc mục 2.7, 5.3, 6.7 và toàn bộ mục 17 của [kế hoạch 1.4](../../KE_HOACH_TRIEN_KHAI.md). Giữ nguyên scope/mapping v1.3. POST nhận việc rồi kết thúc; workflow chờ bằng checkpoint trong DB, callback nối đúng job/ticket/chat, public event log hỗ trợ replay và outbox chịu retry thông báo. ACK hoặc ngắt SSE không đóng ticket.

Owner Phan Hoàng Dũng bổ sung **PHD-14–PHD-17**: provider webhook/inbox, external job correlation, reconciliation và E2E hai phía. Thực hiện cả task cũ còn thiếu và task mới; cập nhật STATUS.md, không đánh dấu hoàn thành từ scaffold.

- [ ] **PHD-14 — External operation trước gọi tool:** execution/external_operations/ triển khai ExternalOperationPort; persist intent/correlation/protocol pin trước network call, propagate client_reference/idempotency khi provider hỗ trợ, bind kết quả job ID. Creation succeeded tách job completed; timeout unknown không retry create mù, callback sớm xác minh theo correlation và integration.
- [ ] **PHD-15 — Webhook thợ và inbox:** execution/provider_events/ triển khai provider router/ProviderEventIngressPort, raw signature dependency từ Foundation, schema/hash/dedupe/receipt/quarantine. ACK chỉ sau inbox+job commit; processor normalize qua port Đông, resolve owner từ operation, apply ordering/state rồi gọi WorkflowPort cùng uow. Không dùng staff payload chọn manager/chat, không tự làm Leader routing.
- [ ] **PHD-16 — Đối soát và trạng thái thao tác:** external_operations/ triển khai query fallback/timer handler, gap/late/unknown reconciliation, callback sau close/revoke và correlation conflict; approvals/external_operations/ hiển thị creation result khác job progress, pending/unknown/failed. Timer do JobPort schedule, không agent polling. tests/workforce/execution/provider_events/ kiểm tra concurrency, ordering và retry với PostgreSQL khi cần.
- [ ] **PHD-17 — Mocks và E2E ticket bất đồng bộ:** tests/workforce/fixtures/async_partners/ cung cấp fake customer backend, technician/provider, outbound receiver có signature/ACK/retry/order faults; tests/workforce/e2e/async_tickets/ chạy cases 56–78. Kiểm tra toàn chuỗi và crash windows, reconnect, duplicate/out-of-order, provider create timeout, close, remap/revoke, wrong audience. Bàn giao fake sớm; không cần gọi booking thật hoặc sửa app đối tác ngoài repo.

Các thư mục v1.4 đã chuẩn bị cho bạn:

- [src/agentscope/app/workforce/execution/provider_events/](../../../../src/agentscope/app/workforce/execution/provider_events/README.md) — Webhook nhận sự kiện thợ, receipt/inbox/dedupe/ordering; không private workflow writes.
- [src/agentscope/app/workforce/execution/external_operations/](../../../../src/agentscope/app/workforce/execution/external_operations/README.md) — Intent/correlation/job binding/progress/unknown/status-query; tạo intent trước tool call.
- [examples/web_ui/frontend/src/features/workforce/approvals/external_operations/](../../../../examples/web_ui/frontend/src/features/workforce/approvals/external_operations/README.md) — Component job progress/unknown/creation result để Chat UI import.
- [tests/workforce/execution/provider_events/](../../../../tests/workforce/execution/provider_events/README.md) — Signature dependency, early callback, unknown, integration isolation và races.
- [tests/workforce/fixtures/async_partners/](../../../../tests/workforce/fixtures/async_partners/README.md) — Mock hai phía/provider và receiver; dữ liệu giả, inject faults và fake clock.
- [tests/workforce/e2e/async_tickets/](../../../../tests/workforce/e2e/async_tickets/README.md) — E2E cases 56–78; database/worker/mock transport thật trong môi trường test.

Bắt đầu bằng đọc hợp đồng 17.3–17.4, viết logic và test với fake port thuộc module mình, rồi bàn giao signature/schema/hook request cho owner cung cấp. Các fake chỉ trong test/demo, production không trả thành công giả. Mỗi người làm trong branch/worktree riêng; migration/core/shared contracts chỉ Chí Hoàng sửa.

