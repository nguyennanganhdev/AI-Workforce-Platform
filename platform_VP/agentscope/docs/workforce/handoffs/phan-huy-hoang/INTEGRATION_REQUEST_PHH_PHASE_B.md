# IR PHH Phase B — các adapter cần nối ở Phase C

Ngày 2026-10-10; baseline develop2 3a6dcaa. B đã triển khai/test độc lập;
các request dưới đây không chặn Phase B.

| ID / owner | Hợp đồng cần nối/chốt | Điều kiện kiểm tra ở C |
|---|---|---|
| B01 — NCH/PHH | WorkflowRepository, EventRepository, RequestRepository + shared UOW | Unique ticket/chat theo scope/client; command ledger tenant/client/external_request_id; revision/fence/closed CAS; unique sequence/event ID; snapshot/cursor một consistent read; injected UOW không tự commit |
| B02 — NCH/PHH | WorkflowAuthorization.authorize/authorize_trigger và Bootstrap.prepare | Reload identity/grant/route/audience từ DB; durable cause đúng workflow, approval thật, timer đến hạn; select published subset, group/session riêng; không public scope/group/agent |
| B03 — NCH/PHH | RuntimeContinuationPort load/invoke/persist | Pinned WorkflowRecord/checkpoint; durable request text/provider facts theo cause; Leader/member cần thiết, không rebuild team; model/provider ngoài UOW; ExecutionGuard.check(effect) trước mỗi side effect; session/result/outbox atomic |
| B04 — PHD/NPD/PHH | OperationLookup.get/is_pending/accept_event | Canonical operation ID, pinned protocol terminal/capability; hash/version/inbox CAS + fact update chung UOW; event sau close audit/dedupe ở Execution, không chạy Leader/chat |
| B05 — NCH/PHH/PHD | CommandClaimResult/TurnPlan/WorkflowBundle promotion hoặc adapter | Chung ledger cho close/request/reply/approval; attach + record_result nhất quán. Close pending approval hiện từ chối; muốn cancel cần Execution invalidation atomically trước closed |
| B06 — NCH/PHH | HTTP composition accept → bounded wait, GET result/conversation/events/event-history, close | Prefix /workforce/v1/partner, external_user_id query, public permission/CAS/cursor/closed errors; 200 completed, 202 chỉ hết deadline; close 200 sau final event commit |
| B07 — NCH/PHD/PHH | Global UI route, manager JWT/BFF, approval rich projection | Import PHH barrel; abort follower khi binding/identity đổi; approved auth surface, không browser machine key. Snapshot approval có workflow_id/approval_id; rich quote/decision từ Execution. Shared transport hook EOF/error để báo reconnect ngay |
| B08 — NCH | Strict revision/time invariants từ IR-PHH-A05 | PHH paths kiểm strict/aware; HTTP parse strict body trước canonical coercion; promote guard vào shared contract nếu thống nhất |

WorkflowRepository.save kiểm revision/fence/closed cùng transaction với
checkpoint/message/result/event. valid_lease trước commit không thay DB CAS.
Lease claim serialize cả workflow/session refs; turn dài cần renew/heartbeat
adapter ở C. Turn hết lease bị bỏ, không lưu kết quả muộn.

Bootstrap chỉ chuẩn bị allocation/pins trong caller UOW, không khởi động runtime
hoặc tạo external side effect. PartnerIngress claim idempotency trước bootstrap.
create_unique phải reserve đồng thời ticket và chat, trả BindingReservation
với is_new; record_input trả is_new và từ chối cùng key khác nội dung. Start mới
vào binding đã có phải rollback và yêu cầu workflow_reply. Prepared allocation
thua retry cần cleanup trong transaction/adapter. Chỉ initial checkpoint_ref
attach trong UOW creation được giữ revision 1; save sau đó phải tăng revision.

ExecutionGuard không hoàn tác call đã gửi: Execution persist operation intent/
idempotency trước call và reconcile thật dù workflow đóng. Orchestration chặn
publication/reopen, không báo giao dịch đã hủy. Provider ingress và grants thật
vẫn do owner hiện tại giữ.

Event append là internal port, không public write endpoint. Repository phải
nhìn reservation mới trong chính UOW và kiểm access. Snapshot message/approval
đúng binding, redaction/limits theo public DTO Execution; cursor expiry map 410.

Runtime/checkpoint aggregate vẫn phh-phase-a-1; đổi/promote shape thì cập nhật
adapter/test theo contract đã chốt. Không copy private Execution service hoặc
sửa Builder/Lifecycle/shared files để hoàn tất B.
