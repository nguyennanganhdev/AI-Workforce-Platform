# Integration request — PHH Phase B

Trạng thái: **OPEN cho Phase C composition/persistence**. Đây không phải thay đổi kế hoạch và không phải contract gửi đối tác.

## IR-PHH-B01 — persistence và constraint (owner: Nguyễn Chí Hoàng)

Cần adapter production cho `WorkflowRepository`, `RequestRepository`, `EventRepository` và `OperationReader` cùng UOW chuẩn. Constraint tối thiểu:

- hai unique binding riêng theo `(tenant, partner client, external user, external ticket)` và `(tenant, partner client, external user, external conversation)`; cùng ticket không được trỏ hai conversation và ngược lại;
- unique workflow cause, command idempotency key, public event ID và event sequence trong conversation;
- workflow revision CAS và lease fencing token;
- checkpoint/result/event/job chỉ visible cùng commit; after-commit callback không được chạy khi rollback;
- event cursor đã prune phải trả lỗi phân biệt để map `410`.

Không sửa service PHH để commit một injected UOW. Adapter repository chịu trách nhiệm isolation và atomic constraint thật.

## IR-PHH-B02 — HTTP/composition (owner: Nguyễn Chí Hoàng)

Đăng ký route từ contract đối tác tới `PartnerIngressService` và `ConversationEventService`:

- POST request/reply và POST close: status từ `receipt_http_status`;
- GET request result, event history, snapshot;
- GET SSE với `text/event-stream`, `Last-Event-ID`/cursor và `410` khi cursor hết hạn.

Composition inject route/identity/command/UOW thật, Foundation `JobPort` + signal, Execution operation reader và runtime continuation adapter. HTTP handler không chạy Leader trong transaction và không tạo outbound webhook sender.

Shared TypeScript `InboundReceipt` hiện thiếu field `error` đang có trong Python canonical DTO. Owner shared cần thêm field optional tương ứng trong lần export contract kế tiếp; PHH không sửa file shared trong lane này.

## IR-PHH-B03 — runtime result (owner: Builder/Lifecycle/Execution)

Runtime adapter phải trả `TurnDecision(RuntimeTurnResult, next_state)` với checkpoint revision tăng đúng một, giữ nguyên session/agent/protocol pins và gọi `ExecutionGuard.check(effect)` ngay trước từng model/tool side effect. Builder/Lifecycle cung cấp pattern/policy đã publish; không để LLM tự khai read-only hay tự chọn group ID.

Execution processor gọi `WorkflowService.apply_external_event()` sau khi operation fact đã được update, truyền cùng UOW và `NormalizedJobEvent` canonical. Không gọi lại tool provider trong PHH service.

Khi Execution tạo hoặc resolve approval, composition phải dùng `PublicEventWriter` trong cùng UOW để phát `approval.required`/`approval.resolved`; snapshot repository đọc approval pending đúng workflow/audience. Không để UI tự suy approval từ text của agent.

## IR-PHH-B04 — query/attention/result hooks (owner: Nguyễn Chí Hoàng + Phan Hoàng Dũng + Phan Huy Hoàng)

Adapter Execution hiện có ba extension `query_sink`, `attention_sink`, `execution_result_sink` nhưng shared contract chưa có DTO/chữ ký canonical. Phase C cần chốt query result có `timer_id`, operation/protocol pin, observed time, status/facts/source hash; attention/result phải mang cause id và immutable workflow binding. Sau đó nối thành timer trigger hoặc workflow transition bằng cùng UOW. Không giả `NormalizedJobEvent` hoặc provider inbox ID cho kết quả status-query nội bộ.

## Điều kiện đóng các IR

Đóng khi có PostgreSQL migration/repository, application wiring, route tests và E2E restart/replay chạy trên composition thật. Test fake Phase B không đủ để tự đóng các yêu cầu này.
