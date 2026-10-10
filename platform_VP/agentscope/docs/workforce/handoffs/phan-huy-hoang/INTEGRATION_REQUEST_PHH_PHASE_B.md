# Integration requests — PHH Phase B

Baseline `8487404`; branch local `dev2PHH-B`. Các yêu cầu dưới đây phục vụ Phase C; không chặn việc làm độc lập Phase B và chưa tự áp dụng sang module người khác.

| ID | Owner phối hợp | Đầu vào/export cần nối | Điều kiện nghiệm thu C |
|---|---|---|---|
| IR-PHH-B01 | PHH repository; NCH migration/composition | WorkflowRepository/EventRepository/RequestRepository và shared command ledger | PostgreSQL unique ticket/chat binding, command namespace không thêm kind, revision/CAS/fence, sequence theo commit; checkpoint/result/message/event/outbox cùng UOW |
| IR-PHH-B02 | PHH repository; NCH auth/HTTP | RequestRepository.resolve_workflow_binding(actor, workflow_id, external_user_id, uow=None) -> InboundRequest gốc | Internal lookup trong tenant/client/user từ principal; original scope/route/group/audience bất biến; reply không remap theo management_ref mới; resource không có quyền trả lỗi không lộ nội dung |
| IR-PHH-B03 | NCH runtime/composition; PHH bootstrap; PTA catalog | WorkflowBootstrap.prepare, RuntimeContinuationPort và ExecutionGuard | Published catalog/pins và session thật; invoke ngoài transaction; guard trước mỗi tool; persist/checkpoint + request result nguyên tử; không resume HITL bằng cause khác |
| IR-PHH-B04 | PHD Execution; NPD protocol | OperationLookup.get/is_pending/accept_event và NormalizedJobEvent đã xác minh | Correlation/provider/protocol đúng pinned operation; inbox hash/version/terminal handling do Execution; update fact + workflow/public event + trigger cùng UOW; job fact sau close không reopen/chat thường |
| IR-PHH-B05 | NCH HTTP/composition | PartnerIngressService + ConversationEventService.stream/snapshot/list_after | Customer credential purpose/grant; POST accept rồi wait có deadline; 200/202 đúng persisted request; error mapping; expired cursor 410; no cursor replay đầu log; bounded auth/queue/proxy handling |
| IR-PHH-B06 | NCH UI root/shared transport; PHD approvals | TicketTimeline/WorkflowStatus/API/followTimeline + WorkforceApprovalCard | Mount theo identity + binding; abort khi đổi hộp; snapshot/410; synchronous current-state ref cho concurrent POST/SSE; stable external_request_id khi retry; authenticated quote/approval feed và browser behavior tests |

## Chữ ký mới cần chú ý

`RequestView(request, result=None, error=None)` phải được đọc nhất quán. Với failed/blocked, persist PublicError cùng status/completed_at; error.request_id phải khớp request được đọc. Với pending/completed, error phải null. Chỉ giữ message/details public đã lọc; không đưa exception stack, credential hoặc provider payload vào error. WORKFLOW_CLOSED cho pending request là projection deterministic, không ghi đè persisted outcome.

HTTP SSE phải gọi `ConversationEventService.stream`/`subscribe`; helper Foundation raw SSE không thay guard public. PHH revalidate trước từng frame và reject binding thay đổi trong stream; handler/proxy vẫn cần timeout/bounded queue để ngắt kết nối bị backpressure. Stop-tracking close giữ pending consent refs, không tự quyết định approval; Execution phải recheck closed-state guard trước late decision/side effect khi nối C.

`RequestRepository.resolve_workflow_binding(actor, workflow_id, external_user_id, uow=None)` trả **InboundRequest đầu tiên đã persist** của workflow trong namespace actor đã xác thực. Không trả request của manager khác, không chọn ticket gần nhất, không resolve lại route hiện hành. Ingress đối chiếu management_ref, audience và workflow_id rồi revalidate grant/current membership trên route gốc trong UOW. Concrete repo thuộc PHH; NCH chỉ nối identity guard/router/composition.

`followTimeline(api, initial, onChange, abortSignal, cursorStore?, readCurrentState?)`: host dùng ref đồng bộ chứa state hiện tại. POST cập nhật qua applyReceipt vào cùng ref; onChange cũng cập nhật ref trước React render. Mỗi binding có follower/cursor riêng. Không đưa API key máy đối tác vào browser; host cung cấp manager JWT/BFF contract đã chốt.

Snapshot pending approvals hiện chỉ cho public keys `workflow_id, approval_id, summary, expires_at, status`; field khác bị chặn. Cần thống nhất projection này với PHD/NCH khi promotion; chi tiết quote/decision lấy bằng feed Execution đã kiểm tra audience. Không mở object generic để lộ credential/tool arguments/raw provider payload.

Workflow checkpoint.operation_refs giữ cả history; workflow.pending_waits chỉ chứa active pending operations. OperationLookup phải trả đúng operation_id được hỏi và quyết định is_pending riêng cho từng operation theo pinned protocol; terminal A không được làm mất trạng thái pending B. Exact close retry đi qua command ledger trước revision CAS; direct/new close luôn kiểm tra revision, kể cả workflow closed.

Bounded result wait tự giới hạn advisory signal và cancel waiter khi deadline/disconnect; không await cleanup chậm. Completion signal adapter phải cooperative cancellation và đóng subscription/resource, kể cả khi port báo lỗi. Concrete DB/auth queries và HTTP handler vẫn cần timeout theo deadline ở C; không suy ra timeout toàn bộ HTTP từ fake signal test. Follower refetch stale snapshot khi POST làm tăng revision, với abortable backoff tối đa 1s; host vẫn cần synchronous current-state ref và snapshot/cursor cùng DB snapshot.

## Điều kiện tích hợp còn mở

- Promote aggregate/trigger/checkpoint/event payload proposal Phase A vào canonical contract theo IR-PHH-A; B vẫn dùng source proposal của PHH và DTO shared hiện có.
- Concrete UOW/repositories phải giữ guarantee atomicity trong Protocol; test fake không thay PostgreSQL lock/constraint/commit-order tests.
- Timer cancellation, worker completion, restart scanner và lease renewal cần nối với Foundation. Closed-state guard đã có ở B; chưa chứng minh cancellation trên jobs DB thật.
- Event/history/snapshot cursor anchor/retention phải cùng DB snapshot/watermark. No cursor sau purge không được trả lịch sử thiếu âm thầm.
- HTTP mapper phải phân biệt foreign/unknown cursor với expired cursor; no secrets trong PublicError; deadline trước proxy timeout và disconnect không hủy request đã nhận.
- Run/ticket legacy bridge do owner tích hợp; không dual-write bảng tickets rời workflow transaction rồi báo hai bên đã hoàn tất.
- Kiểm thử PostgreSQL, HTTP/proxy, browser, restart/process race và sandbox provider thuộc C/D. Global MB/MC/MD chưa PASS từ gói B local này.

Đây là file bàn giao trong repo, chưa gửi message hoặc tự chỉnh code của các owner liên quan.
