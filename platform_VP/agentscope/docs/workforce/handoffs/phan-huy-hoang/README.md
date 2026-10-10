# Bàn giao — Phan Huy Hoàng

Branch đề xuất: `feat/wf-orchestration`. Đầu việc: **PHH-01–PHH-17**.

Phạm vi: Leader chọn group khi có request, chat/@agent và context từ thư viện agent chung.

[Kế hoạch và hợp đồng chung](../../KE_HOACH_TRIEN_KHAI.md) là tài liệu đầu vào cho AI. Gửi cả file kế hoạch và nói rõ: “Tôi là Phan Huy Hoàng”.

Khi triển khai, tạo `STATUS.md` theo mẫu ở mục 16. Mỗi yêu cầu đổi contract/hook/file chung ghi vào `INTEGRATION_REQUEST_<task-id>.md` theo mục 14.

Tiến độ local mới nhất: [STATUS.md](STATUS.md) — Phase B đã có service workflow/continuation/replay/SSE/timeline và test bằng fake ports; chi tiết/bằng chứng local ở STATUS.md và PHASE_B.md. Checklist task bên dưới vẫn là phạm vi implementation của toàn kế hoạch, không được đánh dấu xong chỉ từ schema.

Nguyên tắc batch của bản 1.2 được giữ ở bản 1.3: PHH-02/03/04/12 chọn agent từ toàn bộ thư viện khi có request, tạo group/session lúc đó, không lọc theo batch. Run hiện tại giữ version pin; request mới chọn subset/version phù hợp mà không cần phát hành team. Đọc mục 2.3, 2.5 và 6 của kế hoạch trước khi code; nội dung này thay thế cách hiểu team artifact ở bản trước. Đây là đầu việc cần triển khai, chưa phải tính năng đã hoàn thành.

## Cập nhật bắt buộc theo kế hoạch 1.3

Giữ một role `AREA_MANAGER` và chọn domain/area. Scope là `(tenant_id, domain_id, area_id, manager_account_id)`; partner request phải resolve mapping/grant tới đúng tài khoản đích trước khi chạy Leader, không broadcast theo area. Actor đối tác/cư dân không phải owner platform. Đọc mục 2.6 và hợp đồng mục 6; chỉ dẫn cũ yêu cầu bỏ domain/area không còn hợp lệ.

PHH-13 sở hữu PartnerIngressPort, idempotency, external ticket/conversation/workflow/group binding, dispatch và result/SSE projection. Persist rồi commit trước bounded-wait; start ticket mới tạo đúng một group, reply resolve đúng group trước Leader. Result luôn có workflow_state + next_action. Xong trả `200`, pending `202/watch_request`; retry không tạo group/run/tool call mới. SSE tồn tại nhưng không bắt buộc nếu next_action không yêu cầu. Giữ scope/audience pin và dùng routing/uow của Chí Hoàng.

Các bổ sung này là kế hoạch cần triển khai, không phải xác nhận code hoặc test đã hoàn thành.


## Bổ sung bắt buộc theo kế hoạch 1.4 — API và sự kiện

Đọc mục 2.6–2.7, 5.3, 6.7 và toàn bộ mục 17 của [kế hoạch 1.4.3](../../KE_HOACH_TRIEN_KHAI.md). Giữ nguyên scope/mapping v1.3 và contract hai ticket/hộp chat v1.4.3. Mọi response có `workflow_state` + `next_action`: response-only read-only có thể auto-close; interactive dùng reply/approval/explicit close; external-tracking và Provider Event/SSE chỉ dùng khi operation pending. `202` chỉ là HTTP timeout fallback. V1 không có HTTP sender từ platform sang endpoint đối tác.

Owner Phan Huy Hoàng bổ sung **PHH-14–PHH-17**: workflow ticket, checkpoint/continuation, public event log, SSE/history và chat timeline. Thực hiện cả task cũ còn thiếu và task mới; cập nhật STATUS.md, không đánh dấu hoàn thành từ scaffold.

- [ ] **PHH-14 — Workflow sống qua nhiều lượt, nhiều pattern và nhiều ticket:** triển khai state/next_action cho response-only, interactive và external-tracking. workflow_reply giữ đúng external ticket/conversation/workflow/group/context; hai ticket cùng user có session/pending state riêng dù reuse cùng agent. Auto-close chỉ cho read-only policy, side effect dùng user/approval/confirmation và explicit close, waiting_external_event chỉ cho operation pending có tracking. Không hardcode lifecycle theo domain.
- [ ] **PHH-15 — Tiếp tục runtime đúng nguyên nhân:** Scheduler/continuation trong workflows/ gọi RuntimeContinuationPort và JobPort bằng trigger dedupe, lease/fence/revision. Áp event + checkpoint/message/outbox đúng uow; serialize per workflow/session, xử lý event đến lúc ngủ và pending HITL. Chỉ Leader/member cần thiết chạy, không build hoặc thêm mọi agent; thời gian chờ không tiêu token.
- [ ] **PHH-16 — Event log và API kết quả:** projection/SSE/history/snapshot dùng envelope domain-neutral, project external_ticket_id từ binding; operation status giữ schema/version trong payload, không thành Workflow state mới. POST/SSE dùng cùng message_id; SSE optional theo next_action nhưng stream A/B phải replay/cursor/audience/ticket đúng. Không viết HTTP sender outbound.
- [ ] **PHH-17 — Timeline và kiểm thử workflow:** chat/ticket_timeline/ hiển thị tiến độ ticket, speaker, waiting/blocked/reconnecting, nhiều ticket/hộp chat, đóng đúng ticket và catch-up không trùng bubble. Dùng shared/event_transport và component Execution của Dũng. tests/workforce/orchestration/async_workflows/ kiểm tra fake clock/ports, race close/update/reply, crash/checkpoint, scope/audience, SSE replay và A/B xen kẽ không đi chéo group; không sửa service core ngoài owner.

Các thư mục v1.4 đã chuẩn bị cho bạn:

- [src/agentscope/app/workforce/orchestration/workflows/](../../../../src/agentscope/app/workforce/orchestration/workflows/README.md) — Workflow state/trigger/checkpoint/close/continuation; không lưu provider inbox.
- [src/agentscope/app/workforce/orchestration/partner_events/](../../../../src/agentscope/app/workforce/orchestration/partner_events/README.md) — Public event log, SSE/history/snapshot và notification signal sau commit; không sender outbound.
- [examples/web_ui/frontend/src/features/workforce/chat/ticket_timeline/](../../../../examples/web_ui/frontend/src/features/workforce/chat/ticket_timeline/README.md) — Timeline/close nhiều workflow, reconnect và event/message dedupe.
- [tests/workforce/orchestration/async_workflows/](../../../../tests/workforce/orchestration/async_workflows/README.md) — Workflow transitions/checkpoint/HITL/cursor/isolation/crash windows.

Bắt đầu bằng đọc hợp đồng 17.3–17.4, viết logic và test với fake port thuộc module mình, rồi bàn giao signature/schema/hook request cho owner cung cấp. Các fake chỉ trong test/demo, production không trả thành công giả. Mỗi người làm trong branch/worktree riêng; migration/core/shared contracts chỉ Chí Hoàng sửa.

