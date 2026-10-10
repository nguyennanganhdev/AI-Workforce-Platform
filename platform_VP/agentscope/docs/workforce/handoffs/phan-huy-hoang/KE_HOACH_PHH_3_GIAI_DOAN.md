# PHH-01–PHH-17: kế hoạch hoàn thành theo 3 giai đoạn

Ngày lập: 10/10/2026. Chủ phần việc: Phan Huy Hoàng.

Danh mục kiểm thử mở rộng hiện hành: [55 kịch bản G1](KICH_BAN_TEST_G1.md), [55 kịch bản G2](KICH_BAN_TEST_G2.md), [55 kịch bản G3](KICH_BAN_TEST_G3.md). Mỗi giai đoạn có 50 ca tự động có ID riêng và 5 ca tích hợp với input/expected/runner/gate. Các checkpoint Gx-Txx bên dưới là yêu cầu cấp cao; không thay thế danh mục chi tiết. Xem STATUS.md và TEST_RESULTS.md cho trạng thái thực tế mới nhất; các mục baseline/khởi đầu trong kế hoạch là lịch sử lúc lập.

## 1. Baseline và phạm vi

- Nguồn yêu cầu: `docs/workforce/KE_HOACH_TRIEN_KHAI.md`, phiên bản 1.4.3; đặc biệt mục 2.6–2.7, 5–6, 11, 15–17.
- Checkout được kiểm tra: nhánh `develop2`, commit `6bc7d60d1bcf0d1bf49ad9214fad22791b29c274`. Branch triển khai theo phân công: `feat/wf-orchestration`; chưa tạo/chuyển branch trong công việc lập kế hoạch này.
- Hiện trạng đã kiểm tra: backend Orchestration, các folder workflow/public event, vùng test và handoff đang có README scaffold; chưa có code/test triển khai trong backend Orchestration. Chưa có bằng chứng PHH nào hoàn thành.
- Tài liệu này chia thứ tự thực hiện và nghiệm thu; không thay đổi contract hoặc quyền sở hữu của kế hoạch chung. Không đánh dấu task hoàn thành từ việc có tài liệu.
- Không đặt deadline cố định trước khi xác nhận dependencies, runner và môi trường. Ba giai đoạn không nhất thiết có effort bằng nhau; giai đoạn 3 có nhiều kiểm thử persistence và chịu lỗi.

| Giai đoạn | Task chính | Kết quả phải bàn giao |
|---|---|---|
| 1 — Nền tảng điều phối | PHH-01–PHH-06 | Conversation/run/state, chọn agent, group/session pin version, Leader/Planner và handoff có trạng thái |
| 2 — Hội thoại và đánh giá | PHH-07–PHH-12 | Mention/reply/direct/manual add, group động, EvaluationRunner và Chat UI hoạt động trên cùng runtime |
| 3 — API đối tác và workflow | PHH-13–PHH-17 | Ingress/binding đúng ticket, ba lifecycle pattern, checkpoint/continuation, SSE/history/snapshot và timeline chịu lỗi |

Hoàn thành một giai đoạn nghĩa là code, kiểm thử, exports và bàn giao đạt gate tương ứng. Nếu core/migration/port thật còn thiếu, ghi rõ `LOCAL_VERIFIED / INTEGRATION_PENDING`; chưa được gọi toàn giai đoạn là hoàn tất tích hợp.

## 2. Quy tắc áp dụng từ đầu đến cuối

1. Mỗi giai đoạn bắt đầu bằng kiểm tra checkout, thay đổi đang có, hợp đồng và STATUS gần nhất. Giữ nguyên phần đã hoàn thành; không viết lại chỉ vì sang giai đoạn mới.
2. Chỉ sửa backend `src/agentscope/app/workforce/orchestration/`, frontend `examples/web_ui/frontend/src/features/workforce/chat/`, test `tests/workforce/orchestration/` và handoff `docs/workforce/handoffs/phan-huy-hoang/`.
3. DTO/ports chung, auth, migration thật, root wiring, shared transport và core hooks thuộc Nguyễn Chí Hoàng. Viết `INTEGRATION_REQUEST_<task-id>.md` nêu signature, schema, điểm nối, mẫu payload và test mong đợi; không tự sửa file của owner khác.
4. Dùng hợp đồng chung duy nhất. Module khác chưa có thì inject test doubles trong test của mình; không tạo package contracts thứ hai, không trả thành công giả trong production.
5. Scope đầy đủ tenant/domain/area/manager lấy từ authenticated context. Actor/audience và quyền phải đi xuyên query, worker, runtime, tool, result và event; payload/LLM không cấp quyền.
6. Published agent definition có thể được dùng lại nhưng group/session/context/approval/operation của các workflow độc lập phải riêng. Builder/batch không xác định roster production.
7. Mọi side effect đi qua ExecutionPort. Không gọi MCP trực tiếp từ Orchestration. Unknown phải giữ trạng thái thật và đối soát; không tự tạo lại giao dịch.
8. Làm từng lát cắt: models/schema → repository/service → adapter/API → UI → fault tests → handoff. Mỗi lát cắt review được trước khi mở rộng.
9. Không tự commit/push/deploy. Không dùng secret trong log, fixture hoặc tài liệu.

## 3. Giai đoạn 1 — Nền tảng điều phối, PHH-01–PHH-06

### Đầu vào và thứ tự

Đọc Scope, RunContext, conversation/run/state DTO, PublishedCatalogPort, IdentityPort, ExecutionPort và các runtime hooks đã có. Xác nhận engine/UOW, metadata export và adapter TeamRecord/Session hiện hữu; tránh viết runtime thay AgentScope.

Thứ tự: **PHH-01 → PHH-06 → PHH-02 → PHH-03 → PHH-04 → PHH-05**. Làm shared state trước handoff để nội dung phối hợp có context rõ ràng.

| Task | Công việc và sản phẩm |
|---|---|
| PHH-01 | Models/tables/repository/conversation/run; phân biệt conversation lâu dài với từng run; lưu membership, runtime binding và version pins. Ghi schema/constraints để Chí Hoàng tạo migration thật. |
| PHH-06 | Shared state có revision/CAS, user facts, nguồn dữ kiện, candidates/selected IDs, quote refs/expiry, pending questions và budget/reserve. User đổi yêu cầu phải làm proposal cũ mất hiệu lực. |
| PHH-02 | Router chỉ chọn published candidates trong scope từ toàn thư viện; chọn subset theo khả năng, không lọc batch; thiếu/mơ hồ trả blocker hoặc câu hỏi. |
| PHH-03 | Adapter TeamCreate/AgentInvite/TeamSay/inbox; mapping version → record/session riêng; có đường load/recover binding, giữ cấu hình đúng manifest đã pin. |
| PHH-04 | Leader chọn group và route ban đầu; Planner chủ trì ca du lịch, hỏi dữ kiện thiếu và tổng hợp. Không tạo Leader mới theo batch hoặc hardcode đồng đội. |
| PHH-05 | Handoff có task_id/in_reply_to/context refs; phân biệt giao, nhận, hoàn tất, lỗi; xử lý timeout/cancel/late result, giới hạn số bước/đồng thời/token/cost và chặn vòng lặp. |

Thiết kế ID/persistence từ giai đoạn này phải có đường nối workflow/group về sau theo DTO chung. Đó là chuẩn bị schema; chưa đánh dấu PHH-13/14 hoàn thành.

### Checkpoint và kiểm thử

Suite dự kiến trong `tests/workforce/orchestration/`: `test_storage.py`, `test_router.py`, `test_state.py`, `test_team_adapter.py`, `test_handoff.py`. Tên có thể điều chỉnh theo runner thật, nhưng giữ test ID trong báo cáo.

| ID | Input/tình huống | Expected result | Suite / gate |
|---|---|---|---|
| G1-T01 | Thư viện Plan/Hotel/Car/Calculator/Technical; yêu cầu du lịch | Chọn 4 agent cần thiết, bỏ Technical; yêu cầu chỉ tìm hotel có thể chỉ chọn Hotel | router / G1 |
| G1-T02 | Draft, revoked deployment, candidate manager khác | Không được materialize/chạy; không lộ thông tin ngoài scope | router + team adapter / G1 |
| G1-T03 | Hai group dùng Hotel v3; sau đó publish v4 | Session/context riêng; group cũ giữ v3, request mới có thể chọn v4 | storage + team adapter / G1 |
| G1-T04 | Hai state update dùng cùng expected_revision | Chỉ một ghi thành công; update còn lại conflict, không mất user facts | state; PostgreSQL integration / G1 |
| G1-T05 | User đổi budget khi proposal/quote cũ đang tồn tại | Proposal cũ bị đánh dấu stale, không được dùng để booking | state + handoff / G1 |
| G1-T06 | TeamSay gửi task rồi worker ACK nhưng chưa trả kết quả | Task là acknowledged, chưa completed; chỉ kết quả hợp lệ mới hoàn tất | handoff / G1 |
| G1-T07 | Worker timeout/cancel, kết quả đến muộn, handoff lặp | Kết thúc/đối soát có trạng thái xác định; không ghi đè task mới, không loop vô hạn | handoff / G1 |
| G1-T08 | Restart sau lưu runtime binding | Load lại đúng sessions/pins; không tạo agent definition mới hoặc group trùng | storage + runtime integration / G1 |

### Gate G1

- PHH-01–06 có code/exports và tests hành vi, failure paths.
- Có demo Leader → Planner → member → kết quả với adapter AgentScope; ghi rõ Execution/catalog đang fake hay thật.
- Constraints/CAS/persistence được kiểm tra trên PostgreSQL khi nghiệm thu tích hợp; fake pass chỉ đủ gate local.
- Migration/core hooks đã được owner nối để đạt gate tích hợp, hoặc được liệt kê chính xác là pending.
- Handoff nêu schema, port signatures, test results, cách chạy lại và bước tiếp theo của giai đoạn 2.

## 4. Giai đoạn 2 — Hội thoại và đánh giá, PHH-07–PHH-12

### Đầu vào và thứ tự

Gate local G1 đạt; API/export của conversation/state/team adapter ổn định. PublishedCatalogPort và ExecutionPort thật là đầu vào cần nối để nghiệm thu tích hợp. Import ApprovalCard từ owner Execution; shared UI/transport từ Foundation.

Thứ tự: **PHH-12 → PHH-07 → PHH-08 → PHH-09 → PHH-10 → PHH-11**. UI phát triển theo từng lát cắt tương ứng, không để toàn bộ UI tới cuối.

| Task | Công việc và sản phẩm |
|---|---|
| PHH-12 | Group động từ toàn thư viện, membership history và lý do chọn; add member khi cần, giữ pending task/approval; agent usage API. Xóa group không xóa agent. |
| PHH-07 | Autocomplete gửi target_agent_id, kiểm tra membership/ownership, route vào đúng session/context; tên trùng hỏi làm rõ. |
| PHH-08 | Project speaker/pending question, route reply về người hỏi/task; resolve “khách sạn đó” theo reply_to/selected entity, hỏi lại khi mơ hồ. |
| PHH-09 | Direct chat có context riêng; chuyển context từ group chỉ khi user chọn rõ; manual add kiểm tra published/scope và không thêm trùng. |
| PHH-10 | EvaluationRunnerPort dùng cùng runtime và guard production, inject fixed clock/mock execution; transcript/tool traces/cost/cancel đúng contract. Backend quyết định eval mode. |
| PHH-11 | Chat UI: timeline/members/speaker/@autocomplete/entity quote/pending question/partial/cancel/resume/manual add/direct. Render component approval qua public export của Dũng. |

### Checkpoint và kiểm thử

Suites: `test_mentions.py`, `test_group_replies.py`, `test_direct_chat.py`, `test_dynamic_members.py`, `test_evaluation_runner.py`; UI behavioral tests trong vùng chat, runner do Chí Hoàng tích hợp. Build/lint không thay thế UI tests.

| ID | Input/tình huống | Expected result | Suite / gate |
|---|---|---|---|
| G2-T01 | @Hotel đang được chọn, có selected hotel/quote | Đúng member/session nhận context hiện có; không mở session trắng | mentions / G2 |
| G2-T02 | target_agent_id ngoài group hoặc manager khác; hai member trùng tên | Request sai bị chặn; fallback tên mơ hồ hỏi lại, không đoán | mentions / G2 |
| G2-T03 | Planner hỏi preference; user reply không mention | Reply tới Planner/pending question đúng; nhiều pending question thì làm rõ | group replies / G2 |
| G2-T04 | “Khách sạn đó” khi có một rồi nhiều candidate | Resolve theo explicit reference; thiếu reference rõ thì hỏi lại | group replies / G2 |
| G2-T05 | Direct chat, manual add và private context của group khác | Context direct riêng; chỉ chia sẻ phần user cho phép, không lộ private history | direct + dynamic members / G2 |
| G2-T06 | Plan/Car từ batch A, Hotel từ batch B; add cùng member hai lần | Chọn chéo batch; một membership duy nhất, không làm mất task đang chờ | dynamic members / G2 |
| G2-T07 | Eval và production adapter xử lý cùng fixture; client tự gửi eval mode | Cùng runtime/guards; eval dùng mock theo backend; client không bypass policy | evaluation runner / G2 |
| G2-T08 | Eval cancel/worker failure | Case có trạng thái kết thúc, traces/cost phản ánh thực tế, không giả PASS | evaluation runner / G2 |
| G2-T09 | UI loading/error/refresh/mention/approval/partial/cancel-resume | Hiện đúng speaker/state; không thông báo thành công chỉ vì enqueue | chat UI / G2 |
| G2-T10 | Xóa group đang/đã dùng agent | Agent vẫn ở thư viện; việc hủy pending task tuân policy đã chốt | dynamic members / G2 |

### Gate G2

- PHH-07–12 hoàn tất code/API/UI/tests; regression G1 còn pass.
- Case du lịch đầy đủ hỏi khách → phối hợp → phương án → mention → lựa chọn/approval chạy trên cùng runtime.
- Budget/reserve và tổng tiền dùng kết quả xác định của Execution/Calculator; Orchestration không lấy tính nhẩm của LLM làm số cuối.
- Đã nối runtime hooks, PublishedCatalogPort, ExecutionPort và ApprovalCard thật để đạt gate tích hợp; fixture provider vẫn phải được ghi là mock.
- Có bằng chứng UI hành vi và báo cáo eval; frontend build/lint pass khi môi trường và shared wiring đã sẵn sàng.

## 5. Giai đoạn 3 — API đối tác và workflow, PHH-13–PHH-17

### Đầu vào và thứ tự

G1/G2 cung cấp conversation/run/group/session/context. Chốt contracts mục 17.3–17.4 trước code: UOW, PartnerRoutingPort, PartnerCommandPort, WorkflowPort, ConversationEventPort, RuntimeContinuationPort, JobPort và PublicEventSignalPort.

Thứ tự: **PHH-14 (models/state/binding) → PHH-13 (ingress/idempotency) → PHH-16 (event repository/projection) → PHH-15 (scheduler/continuation) → PHH-16 (SSE/history/snapshot API) → PHH-17 (timeline + resilience tests)**. PHH-16 được làm hai lượt vì continuation cần log bền vững trước khi mở streaming.

| Task | Công việc và sản phẩm |
|---|---|
| PHH-13 | Request command namespace/hash/idempotency, resolve route/audience, immutable ticket/conversation/workflow/group binding, persist+enqueue cùng UOW, commit rồi bounded-wait. Result 200/202 luôn có workflow_state/next_action. |
| PHH-14 | Ba lifecycle pattern theo policy/effect/tool output; response-only auto-close khi được phép, interactive và external-tracking giữ context/pins. Close CAS/commit state+event, không tự hủy operation ngoài hoặc reopen workflow. |
| PHH-15 | Trigger dedupe/lease/fence/revision, checkpoint/continuation và serialize workflow/session; không giữ LLM/DB transaction trong lúc chờ; event không phá pending HITL. |
| PHH-16 | Public event projection domain-neutral, audience/binding guards; POST/SSE/history dùng cùng message_id; DB replay/cursor/consistent snapshot/retention errors và signal catch-up. Không outbound webhook. |
| PHH-17 | Ticket timeline, waiting/blocked/reconnecting, nhiều hộp chat, close đúng ticket, dedupe bubble; test restart/race/isolation và tích hợp fixture hai backend do Dũng sở hữu. |

### Ba lát cắt phải nghiệm thu

1. **Response-only:** start_workflow read-only → kết quả lượt xử lý → `200/closed/none`; không ép provider tracking hoặc POST close.
2. **Interactive:** đề xuất → `awaiting_user/submit_reply` → approval khi có side effect → tool terminal → `awaiting_confirmation/confirm_close` → explicit close.
3. **External-tracking:** create operation pending → `waiting_external_event/watch_events` → event/status-query đúng operation → continuation đúng workflow → user xác nhận close.

`202/watch_request` là fallback khi lượt hiện tại quá HTTP deadline ở bất kỳ pattern nào; không phải tên loại workflow. Timeout/disconnect không tạo lại công việc hoặc hủy operation đã nhận.

### Checkpoint và kiểm thử

Suites trong `tests/workforce/orchestration/async_workflows/`: `test_ingress.py`, `test_ticket_binding.py`, `test_lifecycle_patterns.py`, `test_continuation.py`, `test_event_replay.py`, `test_close_races.py`. PostgreSQL + worker/mock transport integration bắt buộc cho transaction/race/restart. E2E chung thuộc Dũng, PHH ghi yêu cầu và tái sử dụng qua public fixture export.

| ID | Input/tình huống | Expected result | Suite / gate |
|---|---|---|---|
| G3-T01 | Read-only terminal và lượt vượt HTTP deadline | Lượt xong 200/closed/none; lượt pending 202/watch_request, sau đó đọc cùng persisted result | lifecycle + ingress / G3 |
| G3-T02 | Interactive booking terminal và operation pending có protocol | Chọn continuation theo tool/policy; chỉ pending tracking mới watch_events | lifecycle / G3 |
| G3-T03 | Retry cùng external_request_id/body; cùng ID khác body | Cùng receipt/result, không group/run/tool call mới; payload khác trả conflict | ingress; PostgreSQL / G3 |
| G3-T04 | Hai start_workflow đồng thời cho cùng external ticket | Chỉ một binding/group; cùng request trả cùng IDs, request mới cho ticket đã bind trả TICKET_ALREADY_BOUND | ticket binding; PostgreSQL / G3 |
| G3-T05 | A1/B1/A2/B2 cùng khách, cùng agent/version nhưng hai ticket/hộp chat | A và B giữ group/session/context/approval/operation riêng; stream A không có event B | binding + continuation + replay / G3 |
| G3-T06 | workflow-A ghép ticket-B/chat-B; thiếu workflow_id/ticket_id | Lỗi binding/required theo contract trước dispatch, zero model/tool call | ticket binding / G3 |
| G3-T07 | Route remap/revoke hoặc credential/grant hết hạn trước worker/result/stream | Chặn theo policy, không chuyển owner/history sang manager mới, revalidate trước công bố | ingress + continuation + replay / G3 |
| G3-T08 | Provider event duplicate, đến sớm, đảo thứ tự; create timeout unknown | Dùng normalized facts/correlation từ Execution; không create lại, không lùi progress, conflict cần đối soát | continuation + fixture integration / G3 |
| G3-T09 | Event tới đúng lúc ngủ; crash sau commit trước signal; lease hết hạn | Không mất trigger/event; recovery từ DB, worker stale bị fence, một kết quả được commit | continuation; PostgreSQL/worker / G3 |
| G3-T10 | Event tiến độ khi session đang ASKING/SUBMITTED | Lưu status đúng quyền; không giả user reply hoặc execution result để phá HITL | continuation / G3 |
| G3-T11 | SSE reconnect/notification mất, POST và SSE tới đảo thứ tự | DB catch-up, event_id/message_id dedupe, không mất/trùng bubble | event replay + timeline / G3 |
| G3-T12 | Cursor conversation khác, expired cursor, snapshot cạnh tranh update | Cursor sai bị chặn; expired trả 410; snapshot+cursor cùng consistent snapshot | event replay; PostgreSQL / G3 |
| G3-T13 | Close đua reply/status/model turn; provider event sau close | CAS/state/event atomic; không reopen/gửi chat thường sau close; operation fact còn được lưu đúng quyền | close races; PostgreSQL/worker / G3 |
| G3-T14 | Chờ lâu với fake clock, restart, slow SSE consumer, token revoke | Không gọi model khi ngủ; timer durable; queue bounded; quyền stream được thu hồi trong mục tiêu 60 giây | continuation + replay + proxy integration / G3 |

### Gate G3

- PHH-13–17 và regression G1/G2 pass; đủ ba pattern và hai ticket A/B xen kẽ.
- Có migration và wiring thật do Chí Hoàng nối; DB/worker/proxy/restart/race/replay có bằng chứng chạy thật trong môi trường test.
- Customer API dùng đúng prefix `/workforce/v1`; guide/sample khớp contract, không tự thêm API trùng hoặc endpoint outbound.
- E2E hai backend mock và phần thuộc PHH đạt nghiệm thu; ghi riêng trạng thái sandbox/production và điều kiện đối tác còn thiếu.
- Rollout/rollback request được bàn giao: dừng request mới khi rollback nhưng giữ xử lý/audit/history cho workflow mở; không xóa dữ liệu pending.

## 6. Dependencies và bàn giao cho đúng owner

| Owner | Cần cung cấp / nối | Thời điểm |
|---|---|---|
| Nguyễn Chí Hoàng | DTO/ports chung, Scope/identity/UOW, metadata/migration, runtime hooks và root wiring | Chốt signature/schema từ G1; nối từng lát cắt trước gate tích hợp |
| Phó Tiến Anh | PublishedCatalogPort/get_version/get_deployment; eval contract và immutable version snapshot | G1 router/pins, G2 EvaluationRunner |
| Phan Hoàng Dũng | ExecutionPort/approval/Calculator, public UI exports; operation/progress/correlation và fixture/E2E exports | G1–G2 runtime/tool guard; G3 event/operation và E2E |
| Nguyễn Chí Hoàng | PartnerRoutingPort/JobPort/RuntimeContinuationPort/PublicEventSignalPort, shared event transport/proxy/recovery | Chốt trước G3, nối trước gate chịu lỗi |
| Nguyễn Phương Đông | Async protocol/normalized events/capabilities qua public contract | Chốt trước G3 external-tracking |

Handoff “đã gửi” không có nghĩa dependency đã được tích hợp. Ghi owner, signature/version, trạng thái đã nhận/đã nối và kiểm thử xác nhận; thiếu dependency vẫn có thể làm logic bằng fake nhưng gate tích hợp còn pending.

## 7. Cách ghi tiến độ và chứng minh hoàn thành

Sau mỗi checkpoint cập nhật `STATUS.md` theo mục 16 kế hoạch chung và một báo cáo `GIAI_DOAN_1.md`, `GIAI_DOAN_2.md`, `GIAI_DOAN_3.md` khi thực sự nghiệm thu. Báo cáo gồm:

- Task/subtask hoàn thành, đang làm và còn thiếu; commit/branch được kiểm tra.
- Files đã sửa; API/public exports, schema/contract version.
- Với mỗi test ID: runner/suite, input, expected, actual, PASS/FAIL/SKIP/NOT_RUN, log/artifact và lý do skip.
- Các dependency dùng fake hay thật; integration requests và owner còn pending.
- Migration/runtime/PostgreSQL/UI/CI/sandbox/production: trạng thái riêng và bằng chứng tương ứng.
- Cách chạy lại, rủi ro còn tồn tại, rollback nếu cần và đầu vào cho giai đoạn sau.

Trước mỗi lần chạy xác minh interpreter, dependency và runner thực tế. Các lệnh mục tiêu từ gốc `platform_VP/agentscope`:

```powershell
.\.venv\Scripts\python.exe -m pytest tests/workforce/orchestration -q
.\.venv\Scripts\python.exe -m pytest tests/workforce/orchestration/async_workflows -q
pnpm --dir examples/web_ui/frontend build
pnpm --dir examples/web_ui/frontend lint
git diff --check
```

Nếu chưa có interpreter/UI runner/dependency hoặc test DB, ghi NOT_RUN cùng điều kiện cần bổ sung. Không coi collection lỗi, zero tests, skip hoặc fake pass là bằng chứng integration pass. Không tự tải dependency, gọi model trả phí hoặc booking ngoài để làm checklist xanh.

## 8. Trạng thái khởi đầu và việc tiếp theo

- Lập kế hoạch ba giai đoạn: đã hoàn thành.
- Giai đoạn 1: chưa triển khai/chưa chạy test.
- Giai đoạn 2: chưa triển khai/chưa chạy test.
- Giai đoạn 3: chưa triển khai/chưa chạy test.

Việc đầu tiên khi bắt đầu code: xác nhận branch triển khai và hợp đồng hiện có, lập STATUS baseline cùng integration requests cần thiết, rồi thực hiện PHH-01/PHH-06 và bộ G1-T01–G1-T08 theo thứ tự trên. Chốt gate G1 trước khi nghiệm thu G2; chốt gate G2 trước khi nghiệm thu G3. Có thể gửi schema/port requests cho giai đoạn sau sớm để owner chuẩn bị, nhưng không bỏ qua gate hoặc báo task chưa kiểm chứng là hoàn thành.
