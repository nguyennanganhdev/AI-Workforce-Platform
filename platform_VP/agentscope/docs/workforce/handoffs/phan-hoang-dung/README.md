# Bàn giao — Phan Hoàng Dũng

Branch đề xuất: `feat/wf-execution`. Đầu việc: **PHD-01–PHD-17**.

Phạm vi: tool execution, booking approval, idempotency, mocks và E2E.

[Kế hoạch và hợp đồng chung](../../KE_HOACH_TRIEN_KHAI.md) là tài liệu đầu vào cho AI. Gửi cả file kế hoạch và nói rõ: “Tôi là Phan Hoàng Dũng”.

Khi triển khai, tạo `STATUS.md` theo mẫu ở mục 16. Mỗi yêu cầu đổi contract/hook/file chung ghi vào `INTEGRATION_REQUEST_<task-id>.md` theo mục 14.

Kết quả triển khai ngày 10/10/2026: xem [STATUS.md](STATUS.md) để đối chiếu từng task PHD-01–17, phần đã có code/test và phần còn chờ owner khác; xem [VALIDATION.md](VALIDATION.md) để chạy lại kiểm tra. Các integration requests nằm cùng thư mục. Chưa nghiệm thu tích hợp production hoặc E2E toàn platform.

Đã đối chiếu và nối tiếp các DTO dùng được sau khi nhận contracts Phase A của Nguyễn Chí Hoàng (`1ff8fb6`). Chi tiết phần đã gỡ phụ thuộc và port còn thiếu: [PHD-01 Phase A](INTEGRATION_REQUEST_PHD-01_PHASE_A.md).

Nguyên tắc batch của bản 1.2 được giữ ở bản 1.3: PHD-12 kiểm tra batch tạo các agent độc lập, không tạo group production trước request; Leader chọn subset/chọn chéo batch, reuse không tăng agent/version và approval/booking state không lẫn giữa group. Đọc mục 2.3, 2.5 và 6 của kế hoạch trước khi code; nội dung này thay thế cách hiểu team artifact ở bản trước. Đây là đầu việc cần triển khai, chưa phải tính năng đã hoàn thành.

## Cập nhật bắt buộc theo kế hoạch 1.3

Giữ một role `AREA_MANAGER` và chọn domain/area. Scope là `(tenant_id, domain_id, area_id, manager_account_id)`; partner request phải resolve mapping/grant tới đúng tài khoản đích trước khi chạy Leader, không broadcast theo area. Actor đối tác/cư dân không phải owner platform. Đọc mục 2.6 và hợp đồng mục 6; chỉ dẫn cũ yêu cầu bỏ domain/area không còn hợp lệ.

PHD-01/05/13 kiểm tra manager Scope, route/grant và audience ở từng tool call/consent. Partner approval có endpoint/allowed_decider riêng, không giả danh manager. E2E gồm A/B cùng area, cross-domain, hai cư dân, revoke/remap/replay, worker/result/download isolation.

Các bổ sung này là kế hoạch cần triển khai, không phải xác nhận code hoặc test đã hoàn thành.


## Bổ sung bắt buộc theo kế hoạch 1.4 — API và sự kiện

Đọc mục 2.6–2.7, 5.3, 6.7 và toàn bộ mục 17 của [kế hoạch 1.4.3](../../KE_HOACH_TRIEN_KHAI.md). Giữ nguyên scope/mapping v1.3 và contract hai ticket/hộp chat v1.4.3. Mọi response có `workflow_state` + `next_action`: response-only read-only có thể auto-close; interactive dùng reply/approval/explicit close; external-tracking và Provider Event/SSE chỉ dùng khi operation pending. `202` chỉ là HTTP timeout fallback. V1 không có HTTP sender từ platform sang endpoint đối tác.

Owner Phan Hoàng Dũng bổ sung **PHD-14–PHD-17**: Provider Event API/inbox, external job correlation, reconciliation và E2E hai backend gọi platform. Thực hiện cả task cũ còn thiếu và task mới; cập nhật STATUS.md, không đánh dấu hoàn thành từ scaffold.

- [ ] **PHD-14 — External operation trước gọi tool:** execution/external_operations/ triển khai ExternalOperationPort; persist intent/correlation/protocol pin trước network call, propagate client_reference/idempotency khi provider hỗ trợ, bind kết quả job ID. Creation succeeded tách job completed; timeout unknown không retry create mù, event provider đến sớm xác minh theo correlation và integration.
- [ ] **PHD-15 — Provider Event API và inbox tùy chọn:** chỉ external-tracking nhận event; POST provider trả `202` sau inbox+job commit. Normalize bằng protocol versioned, resolve operation/scope và map status domain-specific mà không hardcode ngành vào Workflow. Tool terminal sync không tạo inbox/timer giả.
- [ ] **PHD-16 — Đối soát và trạng thái thao tác:** external_operations/ triển khai query fallback qua MCP tool/timer handler nếu protocol có hỗ trợ, gap/late/unknown reconciliation, event sau close/revoke và correlation conflict; approvals/external_operations/ hiển thị creation result khác job progress, pending/unknown/failed. Timer do JobPort schedule, không agent polling. tests/workforce/execution/provider_events/ kiểm tra concurrency, ordering và retry với PostgreSQL khi cần.
- [ ] **PHD-17 — Mocks và E2E lifecycle đa lĩnh vực/nhiều ticket:** fake customer backend cho request/reply/approval/close và SSE tùy next_action; fake provider chỉ cho operation async. Fake customer mở hai hộp chat cùng user, lưu hai bộ external ticket/conversation/workflow/conversation IDs và gửi xen kẽ. Chạy cases 56–88: read-only auto-close, plan/booking sync không Event, booking pending, sửa chữa external-tracking, next_action, crash/replay/order/close và ticket/group isolation. Không gọi dịch vụ thật hoặc sửa app đối tác ngoài repo.

Các thư mục v1.4 đã chuẩn bị cho bạn:

- [src/agentscope/app/workforce/execution/provider_events/](../../../../src/agentscope/app/workforce/execution/provider_events/README.md) — Provider Event API do platform host, receipt/inbox/dedupe/ordering; không private workflow writes.
- [src/agentscope/app/workforce/execution/external_operations/](../../../../src/agentscope/app/workforce/execution/external_operations/README.md) — Intent/correlation/job binding/progress/unknown/status-query; tạo intent trước tool call.
- [examples/web_ui/frontend/src/features/workforce/approvals/external_operations/](../../../../examples/web_ui/frontend/src/features/workforce/approvals/external_operations/README.md) — Component job progress/unknown/creation result để Chat UI import.
- [tests/workforce/execution/provider_events/](../../../../tests/workforce/execution/provider_events/README.md) — Signature dependency, provider event đến sớm, unknown, integration isolation và races.
- [tests/workforce/fixtures/async_partners/](../../../../tests/workforce/fixtures/async_partners/README.md) — Fake Customer API cho ba pattern; fake provider/SSE chỉ cho external-tracking.
- [tests/workforce/e2e/async_tickets/](../../../../tests/workforce/e2e/async_tickets/README.md) — E2E cases 56–88; ba lifecycle pattern và hai ticket/hộp chat với database/worker/mock transport thật.

Bắt đầu bằng đọc hợp đồng 17.3–17.4, viết logic và test với fake port thuộc module mình, rồi bàn giao signature/schema/hook request cho owner cung cấp. Các fake chỉ trong test/demo, production không trả thành công giả. Mỗi người làm trong branch/worktree riêng; migration/core/shared contracts chỉ Chí Hoàng sửa.

