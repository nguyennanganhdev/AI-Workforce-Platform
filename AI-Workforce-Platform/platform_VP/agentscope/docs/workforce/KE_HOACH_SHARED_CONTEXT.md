# Kế hoạch và trạng thái triển khai Shared Context cho Agent Group Chat

## Trạng thái thực thi 13/10/2026

Source hiện tại đã triển khai runtime dùng chung, không chỉ mô tả kế hoạch:

- Mỗi team/ticket có một `TeamSharedContextRecord`; event nguồn không bị xóa
  khi summary chạy.
- Trạng thái task, constraint, fact, decision, output, câu hỏi và operation đang
  chờ được lưu có cấu trúc. Agent không thể tự nâng lời báo cáo của mình thành
  `customer_confirmed` hoặc `tool_verified`.
- Summary được tách theo từng `task_id`, chỉ đọc event đã được chia sẻ, bắt buộc
  dẫn `source_event_ids`, kiểm tra đủ nguồn, đo input/output token và retry hữu
  hạn. Summary lỗi không thay mốc đã bao phủ và không xóa dữ liệu gốc.
- Packet hỗ trợ `task`, `references`, `isolated`; kết quả hỗ trợ `caller` và
  `shared`. Direct mention và chat chung giữ cùng task đang trao đổi.
- Với `isolated`/`references`, runtime chụp context trước turn rồi chỉ nạp phần
  message/block mới của chính turn đó. Cách này giữ được cả input khách hàng mới
  lẫn handoff được Inbox gắn vào message cũ, đồng thời không nạp private summary
  hoặc lịch sử riêng trước đó.
- Shared packet chỉ được middleware chèn tại model-call; nó không nằm trong system
  prompt gốc dùng cho private-memory compression. Vì vậy summary riêng không sao chép
  snapshot chung rồi giữ lại một phiên bản đã cũ.
- Trước mỗi model call, runtime đo toàn bộ prompt sau khi filter cùng tool schema,
  dành 10% cửa sổ cho output và dừng bằng lỗi retryable nếu không thể chứa dữ
  liệu bắt buộc. Workforce runtime tắt `compression_fallback_to_truncation` để
  không âm thầm cắt private context khi summary lỗi, đồng thời tắt
  `compression_retry_drop_oldest` để summarizer không được retry bằng một tập source
  đã bỏ các message cũ nhất.
- Metric lưu số token packet/state/history/summary/prompt, số event nguồn/đã
  nạp/đã loại, số attempt, số lần compaction thành công/thất bại và peak prompt.
- Nếu summary lỗi hoặc packet vượt ngưỡng, chỉ event `progress` mang tính tường
  thuật được phép lược theo ranh giới event và packet phải khai báo số lượng,
  khoảng revision cùng hash của các ID đã lược. Customer turn, result, handoff,
  HITL, external event và correction không vừa ngân sách sẽ trả lỗi retryable;
  không tiếp tục bằng một packet thiếu dữ liệu quan trọng.
- Hội thoại có trước tính năng này được bootstrap idempotent từ message
  user/assistant nhìn thấy bởi khách; private reasoning không được đưa sang
  shared context.
- Agent Builder có summary riêng trong `SessionRecord.state`, không ghi vào
  shared context của ticket. Builder giữ toàn bộ raw message trong storage,
  compact theo ranh giới message với source ID, retry hữu hạn, giữ summary cũ
  khi lỗi và đo cả prompt + structured-output schema trước mỗi model call.
- TeamSay ghi shared event trước delivery, dùng idempotency key và marker delivery
  theo recipient để retry thông thường không tạo hai event hoặc hai inbox item.
  `TeamTurnRecord` và `TeamHandoffRecord` giữ reply owner, câu hỏi đang chờ và
  trạng thái `pending/delivered/consumed/failed` trong storage bền vững. Khi
  Redis hoặc worker khởi động lại, dispatcher phát lại theo `handoff_id`; Inbox
  loại trùng và chỉ xác nhận `consumed` sau khi payload được giải mã, chèn thành
  công.
- Luồng chat trực tiếp và `/workforce/v1` dùng cùng `SharedContextService`.
  Request/reply của khách, kết quả Leader, approval, provider event, query
  result và close của API đối tác đều tạo durable projection job trong cùng
  transaction với workflow. Projection phải hoàn tất trước khi continuation
  được kiểm tra quyền và đưa vào hàng đợi Leader. Event tới sai thứ tự vẫn được
  giữ để audit nhưng có cờ `stale`, không được ghi đè structured state hoặc đánh
  thức Leader.
- Runtime đối tác bắt buộc nhận `SharedContextService`, kiểm tra đầy đủ
  tenant/domain/area/manager/workflow, rồi pin snapshot và revision vào
  `PinnedRuntimeContext`. Model resolver của deployment phải trả đúng model đã
  pin cho Leader; runtime gọi `prepare_packet` bằng model đó nên cùng cơ chế đo
  token/summary/budget được áp dụng cho API đối tác, không truyền thẳng toàn bộ
  JSON history vào Leader. Hai ticket phải có `group_id` khác nhau; nếu một group
  bị tái sử dụng cho workflow khác, scope binding từ chối thay vì trộn dữ liệu.
  `create_app` cũng fail-fast nếu direct chat và Workforce bootstrap không dùng
  đúng cùng một `shared_context_storage` instance.
- Kết quả MCP đồng bộ thông thường được backend tự ghi thành fact
  `tool_verified`; không phụ thuộc model nhớ gọi TeamSay. Tool call/result lỗi
  vẫn được lưu làm event lỗi nhưng không được nâng thành fact xác nhận.
- OpenAI/OpenAI-compatible dùng `tiktoken` theo model, có fallback
  `o200k_base` được ghi rõ trong metric. Provider chưa có tokenizer cục bộ dùng
  fallback tương thích có nhãn `estimated:utf8-bytes-div-4`, tuyệt đối không
  được trình bày như token billing chính xác. Preflight đo packet, private
  prompt, tool schema, output reserve và safety margin; nếu không vừa thì dừng
  rõ ràng, không âm thầm cắt dữ liệu bắt buộc.
- SQL storage và chuỗi migration `0013` → `0014` →
  `0015_shared_context_backfill` đã có. `0014` bổ sung DB-level CAS, immutable
  snapshot, scope, durable turn/handoff; `0015` sửa revision và tạo baseline
  snapshot cho record `0013` đã tồn tại. Dữ liệu chạy ở
  PostgreSQL hay Redis phụ thuộc `StorageBase` mà deployment cấu hình. App mẫu
  tách `shared_context_storage` khỏi storage agent/session: mặc định dùng SQL khi
  có `AGENTSCOPE_SQL_URL`, còn Redis vẫn giữ agent/session và message bus. Phải
  chạy Alembic tới head sau khi pull phiên bản này; không được hiểu việc đã chạy
  `0013`/`0014` trước đó là database đã tự có `0015`.

Lưu ý composition: app chỉ có route `/workforce/v1` khi deployment truyền một
`WorkforceBootstrap` hoàn chỉnh vào `create_app`. Source cố ý không dựng Leader,
auth, MCP hay evaluator giả trong app local. Production composition sẽ từ chối
khởi động nếu thiếu canonical `SharedContextService`; vì vậy không tồn tại chế
độ API đối tác chạy nhưng âm thầm bỏ qua Shared Context.

Các checklist thiết kế cũ bên dưới được giữ làm lịch sử. Contract Python và test
hiện hành trong source là chuẩn thực thi khi nội dung cũ khác với mục trạng thái
này.

> Ghi chú triển khai ban đầu 12/10/2026: runtime cốt lõi được triển khai bằng
> `TeamSharedContextRecord`, `SharedContextService`, ba chế độ đọc
> `task/references/isolated`, hai phạm vi kết quả `caller/shared`, summary có
> đo token, migration `0013_team_shared_context` và phép đo tổng prompt trước
> model call. Các mục checklist cũ bên dưới được giữ làm lịch sử thiết kế;
> contract trong source code hiện hành là chuẩn thực thi.

## 1. Mục tiêu

Triển khai cơ chế để một agent được gọi sau có đủ ngữ cảnh đã được các agent
trước xác nhận, ví dụ:

```text
Leader giao task T1 cho Agent A
    -> A hỏi Agent B
    -> B trả kết quả cho A
    -> A giao tiếp Agent C
    -> C nhận mục tiêu + kết quả A/B + câu hỏi còn mở
    -> C xử lý và trả kết quả đúng task T1
```

Kế hoạch này dành cho **một người thực hiện tuần tự**. Mục tiêu là mở rộng các
thành phần hiện có, không xây lại cơ chế chat, session, queue hoặc workflow.

## 2. Kết quả cần đạt

Sau khi hoàn thành:

1. Mỗi agent vẫn có `SessionRecord` và `AgentState.context` riêng.
2. Agent giao tiếp bằng `TeamSay` như hiện tại.
3. Mỗi trao đổi có thể mang `task_id`, `thread_id`, `in_reply_to` và
   `context_ref`.
4. PostgreSQL lưu handoff và các snapshot shared context bền vững.
5. Redis tiếp tục chỉ làm inbox, wake-up và realtime delivery.
6. Khi Agent C được gọi, backend tự tải đúng snapshot và ghép phần liên quan vào
   `HintBlock` trước khi đưa vào inbox của C.
7. Không đưa toàn bộ transcript hoặc chain-of-thought của A/B vào prompt C.
8. Context luôn bị giới hạn bởi tenant, domain, area, manager, workflow và
   group; hai ticket hoặc hai group không đọc chéo dữ liệu.
9. Retry, restart backend hoặc message gửi trùng không tạo hai handoff logic.

## 3. Không thuộc phạm vi phiên bản đầu

- Không cho tất cả agent dùng chung một `AgentState.context`.
- Không broadcast toàn bộ mọi message cho tất cả thành viên.
- Không lưu chain-of-thought hoặc reasoning nội bộ.
- Không embedding từng tin nhắn vào pgvector.
- Không dùng MinIO để lưu message text hoặc shared state nhỏ.
- Không thay `TeamSay` bằng một message bus mới.
- Không viết một runtime Leader/Builder/Eval khác song song với runtime hiện có.
- Summary chung dùng một model call có schema, retry hữu hạn và kiểm tra kích
  thước bằng `model.count_tokens`. Summary chỉ nén lịch sử đã chia sẻ, không
  thay thế trạng thái nghiệp vụ có cấu trúc và không xóa sự kiện nguồn.

## 4. Thành phần hiện có phải tái sử dụng

| Thành phần hiện có | Cách tái sử dụng | Thay đổi tối thiểu |
|---|---|---|
| `TeamRecord` và roster | Xác định sender/recipient thực sự thuộc cùng team | Không đổi cơ chế membership |
| `TeamSay` | Kênh agent-to-agent hiện tại | Thêm các tham số có cấu trúc nhưng vẫn tương thích lời gọi cũ |
| `deliver_to_inbox` | Gửi payload và đánh thức session đích | Giữ nguyên |
| `MessageBusKeys.inbox` | Queue realtime theo session | Giữ nguyên; không dùng làm source of truth |
| `InboxMiddleware` | Đưa `HintBlock` đã hydrate vào context agent | Giữ nguyên ở MVP |
| `SessionRecord`/`AgentState` | Context riêng và lịch sử riêng của từng agent | Giữ nguyên |
| `TeamMemberLoopMiddleware` | Buộc worker báo kết quả về Leader | Giữ nguyên; chỉ cập nhật mô tả nếu cần |
| `WorkflowCheckpoint.shared_state_ref` | Pin snapshot context đang dùng | Trỏ tới ID snapshot PostgreSQL |
| `pending_task_ids` | Theo dõi task chưa hoàn tất | Tái sử dụng thay vì tạo danh sách pending thứ hai |
| Workforce `Scope` | Cách ly tenant/domain/area/manager | Bắt buộc trên mọi repository query |
| Foundation UOW/job | Transaction và retry bền vững | Dùng cho persist/re-delivery; không tự tạo engine |
| Workspace và MinIO/S3 | Chia sẻ file/artifact lớn | Shared context chỉ giữ object key/asset ID |

Các điểm nối chính:

- `src/agentscope/app/_tool/_team_say.py`
- `src/agentscope/app/_bus_ops.py`
- `src/agentscope/app/middleware/_inbox_middleware.py`
- `src/agentscope/app/_service/_toolkit.py`
- `src/agentscope/app/_service/_chat.py`
- `src/agentscope/app/workforce/orchestration/_tables.py`
- `src/agentscope/app/workforce/orchestration/_repository.py`
- `src/agentscope/app/workforce/orchestration/workflows/phase_a.py`
- `src/agentscope/app/workforce/integrations/async_runtime/_composition.py`

## 5. Kiến trúc đích

```text
Agent A gọi TeamSay(to=C, task_id=T1, ...)
        |
        v
TeamSay kiểm tra membership và resolve session C
        |
        v
HandoffService
  1. đọc shared-context snapshot gần nhất của T1
  2. áp dụng context_delta bằng CAS/revision
  3. ghi handoff bất biến vào PostgreSQL
  4. tạo context packet có giới hạn token
        |
        v
HintBlock hiện có + deliver_to_inbox hiện có
        |
        v
Redis inbox của session C + wake-up hiện có
        |
        v
InboxMiddleware hiện có đưa HintBlock vào context riêng của C
        |
        v
Agent C suy luận và trả kết quả bằng TeamSay
```

PostgreSQL là nguồn dữ liệu chuẩn. Redis chỉ chuyển payload đã chuẩn bị và đánh
thức agent. Nếu Redis bị mất, handoff `pending_delivery` vẫn có thể được phát lại.

## 6. Hợp đồng dữ liệu

### 6.1. `HandoffEnvelope`

Tạo model trong `orchestration/_handoff.py`:

```python
class HandoffEnvelope(WorkforceModel):
    schema_version: Literal["1"] = "1"
    handoff_id: str
    group_id: str
    workflow_id: str | None
    task_id: str
    thread_id: str
    in_reply_to: str | None
    kind: Literal[
        "task",
        "question",
        "answer",
        "result",
        "context_update",
        "error",
    ]
    sender_agent_id: str
    sender_session_id: str
    recipient_agent_id: str
    recipient_session_id: str
    content: str
    context_ref: str
    context_revision: int
    artifact_refs: tuple[str, ...]
    hop_count: int
    idempotency_key: str
    created_at: datetime
```

Quy tắc:

- `group_id`, sender, recipient và scope do backend lấy từ storage; model không
  được tự khai các giá trị này.
- `in_reply_to` phải thuộc cùng `group_id` và `task_id`.
- `artifact_refs` chỉ chứa asset ID hoặc object key, không chứa binary/base64.
- `hop_count` tăng khi handoff tiếp tục cùng task.
- `idempotency_key` ngăn một tool retry tạo hai message logic.

### 6.2. `SharedTaskContext`

Tạo model trong `orchestration/_context.py`:

```python
class SharedTaskContext(WorkforceModel):
    schema_version: Literal["1"] = "1"
    group_id: str
    workflow_id: str | None
    task_id: str
    objective: str
    status: Literal["open", "blocked", "completed", "cancelled"]
    summary: str
    constraints: tuple[ContextItem, ...]
    confirmed_facts: tuple[ContextItem, ...]
    decisions: tuple[ContextItem, ...]
    open_questions: tuple[ContextQuestion, ...]
    outputs: tuple[ContextOutput, ...]
```

Mỗi item phải có tối thiểu:

```text
item_id
text hoặc value
source_handoff_id
source_agent_id
created_at
```

Không có trường chứa reasoning nội bộ. Facts và decisions luôn có nguồn để Agent
C biết thông tin đến từ đâu.

### 6.3. `ContextDelta`

`TeamSay` không được cho model ghi đè toàn bộ context. Model chỉ gửi thay đổi:

```python
class ContextDelta(WorkforceModel):
    summary: str | None = None
    add_constraints: tuple[str, ...] = ()
    add_confirmed_facts: tuple[str, ...] = ()
    add_decisions: tuple[str, ...] = ()
    add_open_questions: tuple[str, ...] = ()
    resolve_question_ids: tuple[str, ...] = ()
    add_outputs: tuple[ContextOutputInput, ...] = ()
    status: Literal["open", "blocked", "completed", "cancelled"] | None = None
```

Backend gắn source, ID và timestamp. Không cho agent tự sửa `source_agent_id`,
revision hoặc scope.

## 7. Thiết kế database tối thiểu

### 7.1. Bảng `wf_shared_context_snapshots`

Snapshot bất biến, không update payload cũ:

| Cột | Ý nghĩa |
|---|---|
| `id` | ID snapshot; được dùng làm `shared_state_ref` |
| scope columns | `tenant_id`, `domain_id`, `area_id`, `manager_account_id` |
| `workflow_id` | Workflow sở hữu, nullable cho generic team |
| `group_id` | Team/group sở hữu |
| `task_id` | Task trong group |
| `revision` | Revision tăng dần theo task |
| `parent_snapshot_id` | Snapshot trước đó |
| `payload_hash` | Kiểm tra nội dung/idempotency |
| `payload` | `JSONB` trên PostgreSQL, `JSON` ở metadata portable |
| `created_at` | Thời điểm tạo |

Ràng buộc/index:

```text
UNIQUE(group_id, task_id, revision)
INDEX(scope..., group_id, task_id, revision)
INDEX(workflow_id)
```

Update đồng thời được xử lý bằng insert revision mới. Nếu unique conflict, service
reload revision mới nhất, merge lại và retry tối đa 3 lần. Không cần thêm bảng
head ở phiên bản đầu.

### 7.2. Bảng `wf_group_handoffs`

Append-only audit log:

| Cột | Ý nghĩa |
|---|---|
| `id` | `handoff_id` |
| scope columns | Cách ly tenant/domain/area/manager |
| `workflow_id`, `group_id`, `task_id`, `thread_id` | Routing nội bộ |
| `in_reply_to` | Message cha |
| sender/recipient agent + session | Đích đã resolve từ roster |
| `kind` | task/question/answer/result/context_update/error |
| `content` | Nội dung công khai giữa agent |
| `context_ref`, `context_revision` | Snapshot dùng lúc nhận |
| `artifact_refs` | JSON array các asset reference |
| `hop_count` | Chống vòng lặp |
| `idempotency_key` | Chống retry trùng |
| `delivery_status` | pending/delivered/failed/cancelled |
| timestamps | created/delivered |

Ràng buộc/index:

```text
UNIQUE(scope tenant, idempotency_key)
INDEX(scope..., group_id, task_id, created_at)
INDEX(recipient_session_id, delivery_status)
FOREIGN/logic check in_reply_to thuộc cùng group/task
```

Không dùng bảng `messages` hiện có làm group transcript vì bảng đó được thiết kế
theo một `session_id`. Việc join message từ nhiều session sẽ làm mất ranh giới
task/thread và khó kiểm tra scope. `messages` vẫn giữ lịch sử riêng của từng
session; `wf_group_handoffs` chỉ lưu phần được chủ động chia sẻ.

### 7.3. Migration

- Thêm table metadata vào `orchestration/_tables.py`.
- Tạo Alembic revision mới nối sau revision head tại thời điểm bắt đầu code;
  không sửa các migration `0010`, `0011`, `0012` đã có.
- `upgrade()` chỉ tạo hai bảng/index mới.
- `downgrade()` xóa theo thứ tự handoff trước, snapshot sau.
- Chạy migration trên PostgreSQL local và kiểm tra upgrade/downgrade/upgrade.

## 8. Thay đổi `TeamSay` theo hướng tương thích ngược

Giữ nguyên hai tham số hiện tại:

```python
content: str
to: str | None = None
```

Thêm tham số optional:

```python
task_id: str | None = None
thread_id: str | None = None
in_reply_to: str | None = None
kind: HandoffKind = "task"
context_ref: str | None = None
context_delta: ContextDelta | None = None
artifact_refs: list[str] = []
idempotency_key: str | None = None
```

Hai chế độ:

1. Không có `task_id`: chạy đúng hành vi legacy hiện tại.
2. Có `task_id`: chạy structured handoff qua `HandoffService`, sau đó vẫn gọi
   `deliver_to_inbox` hiện có.

Không tin `to` như một identity. `TeamSay` tiếp tục resolve tên qua roster hiện
có để lấy `agent_id/session_id`; HandoffService chỉ nhận identity đã resolve.

Thêm optional dependency vào constructor:

```python
handoff_service: HandoffService | None = None
```

Nếu service chưa được cấu hình, lời gọi legacy vẫn hoạt động. Structured call
phải trả lỗi cấu hình rõ ràng thay vì âm thầm gửi không persist.

## 9. Context hydration

Không sửa cách `InboxMiddleware` chạy trong MVP. `HandoffService` tạo sẵn
`HintBlock.hint` như sau:

```xml
<team-message
  from="agent-a"
  handoff-id="h-123"
  task-id="task-1"
  thread-id="thread-1"
  in-reply-to="h-120">

<shared-context ref="ctx-9" revision="4">
Objective: Kiểm tra ticket sự cố Ocean Park 1.
Summary: A đã phân loại; B đã xác nhận mức độ high.
Constraints:
- Chưa tạo yêu cầu sửa chữa khi chưa được Area Manager duyệt.
Confirmed facts:
- Sự cố ở khu vực chung.
- Mức độ high.
Open questions:
- Có bao nhiêu tòa nhà bị ảnh hưởng?
Relevant outputs:
- B kết luận dữ liệu hiện tại chưa đủ để tạo ticket.
</shared-context>

<current-request>
Kiểm tra danh sách dữ liệu còn thiếu.
</current-request>
</team-message>
```

Payload này tiếp tục đi qua `deliver_to_inbox` và `InboxMiddleware` hiện có.

### Quy tắc chọn context

Theo thứ tự ưu tiên:

1. Objective và constraints: luôn giữ.
2. Confirmed facts và decisions: giữ theo thứ tự mới nhất/có liên quan.
3. Open questions: luôn giữ nếu chưa resolved.
4. Outputs liên quan đến `in_reply_to` hoặc current recipient.
5. Tối đa N handoff gần nhất trong cùng task/thread.
6. Artifact chỉ đưa metadata và reference, không tải binary vào prompt.

Giới hạn cấu hình ban đầu:

```text
SHARED_CONTEXT_PACKET_MAX_TOKENS=3000
SHARED_CONTEXT_HISTORY_BUDGET_TOKENS=2000
SHARED_CONTEXT_SUMMARY_TRIGGER_RATIO=0.80
SHARED_CONTEXT_RECENT_HISTORY_RATIO=0.10
SHARED_CONTEXT_SUMMARY_MAX_RATIO=0.25
SHARED_CONTEXT_SUMMARY_ATTEMPTS=2
SHARED_CONTEXT_OUTPUT_RESERVE_RATIO=0.10
```

Đây không phải biến bí mật. Có thể đặt default trong settings và chỉ đưa vào
`.env.example` nếu cần điều chỉnh khi deploy.

Nếu vượt ngân sách:

1. Bỏ handoff cũ trước.
2. Bỏ output đã superseded.
3. Giữ facts/decisions/open questions.
4. Khi lịch sử đạt 80% ngân sách H, summary cũ và các sự kiện chưa được bao phủ
   được nén; giữ nguyên các sự kiện gần nhất theo ranh giới sự kiện.
5. Nếu summary thất bại, giữ nguyên summary cũ và dữ liệu nguồn; chỉ dựng packet
   nhỏ hơn khi vẫn đủ trạng thái bắt buộc, nếu không trả lỗi budget retryable.

## 10. Persistence và delivery ordering

Thứ tự bắt buộc:

```text
validate scope/membership
    -> load/insert context snapshot
    -> insert handoff(pending_delivery)
    -> commit PostgreSQL
    -> deliver_to_inbox
    -> mark delivered
```

Không gửi Redis trước khi PostgreSQL commit vì backend crash sẽ tạo message mà
không có audit/context source.

Nếu commit xong nhưng Redis delivery lỗi:

- Handoff còn `pending_delivery`.
- Enqueue durable retry job bằng Foundation job service hiện có.
- Retry dùng cùng `handoff_id/idempotency_key`.
- Recipient dedupe theo `handoff_id` trước khi inject.

MVP có thể phát đồng bộ ngay sau commit; durable retry vẫn phải có trước khi coi
chức năng production-ready.

## 11. Bảo mật và cách ly dữ liệu

Mọi thao tác phải kiểm tra:

1. Scope trong request/runtime khớp snapshot và handoff.
2. Sender session thuộc group tại thời điểm gửi.
3. Recipient session thuộc group tại thời điểm gửi.
4. `in_reply_to` và `context_ref` thuộc cùng group/task/scope.
5. Workflow chưa đóng hoặc bị revoke.
6. Artifact reference thuộc cùng scope và caller có quyền đọc.
7. Không đưa credential, token, system prompt hoặc tool secret vào payload.

Không nhận các giá trị sau trực tiếp từ model rồi tin tưởng:

```text
tenant_id
domain_id
area_id
manager_account_id
sender_agent_id
sender_session_id
recipient_agent_id
recipient_session_id
workflow owner
```

Backend phải derive từ session, team roster và workflow binding.

## 12. Chống vòng lặp và runaway agents

- `hop_count` tối đa mặc định 12 cho một task.
- Không cho gửi lại cùng `(sender, recipient, content_hash, context_revision)`
  trong một cửa sổ ngắn nếu không có `in_reply_to` mới.
- Một handoff chỉ được resolve một lần.
- Task `completed/cancelled` không nhận task mới trừ khi Leader reopen bằng
  revision mới.
- Giới hạn số handoff đang chạy đồng thời trong một group.
- Worker vẫn phải báo Leader khi kết thúc; giao tiếp peer-to-peer không thay vai
  trò tổng hợp của Leader.
- Khi vượt giới hạn, tạo `error` handoff về Leader, không tiếp tục tự gọi agent.

## 13. Các bước triển khai tuần tự cho một người

### Giai đoạn 0 — Khóa baseline và test hiện trạng

- [ ] Chạy test hiện có cho `TeamCreate`, `AgentCreate`, `TeamSay`, inbox và
  team-member middleware.
- [ ] Ghi lại hành vi legacy của `TeamSay(content, to)` để chống regression.
- [ ] Kiểm tra Alembic head thực tế trước khi đặt tên revision mới.
- [ ] Không sửa/chạm vào các thay đổi chưa commit không liên quan trong working
  tree.

**Hoàn thành khi:** có danh sách lệnh test baseline và kết quả lưu trong ghi chú
triển khai.

### Giai đoạn 1 — Contract thuần Python

- [ ] Tạo `_handoff.py` với `HandoffEnvelope`, `ContextDelta`, enum trạng thái.
- [ ] Tạo `_context.py` với `SharedTaskContext` và context item models.
- [ ] Validation độ dài content, số artifact, hop count và relation fields.
- [ ] Unit test model validation; chưa đụng database/tool/runtime.

**Hoàn thành khi:** schema JSON ổn định và unit test không cần Redis/PostgreSQL.

### Giai đoạn 2 — SQL tables và repository

- [ ] Thêm hai bảng vào `_tables.py`.
- [ ] Viết `SqlSharedContextRepository` và `SqlHandoffRepository`, tái sử dụng
  `_scope_values`, `_scope_where`, `_json_hash`, `_sql_uow` hiện có.
- [ ] Implement `get_latest`, `get_by_ref`, `append_snapshot`, `append_handoff`,
  `mark_delivered`, `list_pending_delivery`, `list_relevant_handoffs`.
- [ ] Thêm Alembic revision additive sau head hiện tại.
- [ ] Test SQLite cho logic chung và PostgreSQL cho JSONB/concurrency/index.

**Hoàn thành khi:** hai update đồng thời không ghi đè nhau và query khác scope
không trả dữ liệu.

### Giai đoạn 3 — `SharedContextService`

- [ ] Merge `ContextDelta` theo quy tắc append/resolve; backend gắn provenance.
- [ ] Insert snapshot revision mới; retry unique conflict tối đa 3 lần.
- [ ] Build context packet theo token budget.
- [ ] Validate context/artifact references.
- [x] Không dùng embedding; dùng LLM summarizer có schema và giới hạn token,
  không dùng summary làm nguồn sự thật nghiệp vụ.

**Hoàn thành khi:** từ snapshot A/B có thể sinh deterministic packet cho C.

### Giai đoạn 4 — `HandoffService`

- [ ] Resolve task/thread/default context.
- [ ] Persist context snapshot và handoff trong cùng UOW.
- [ ] Tạo `HintBlock` theo XML envelope thống nhất.
- [ ] Commit trước, sau đó gọi `deliver_to_inbox` hiện có.
- [ ] Mark delivery; tạo retry job khi delivery lỗi.
- [ ] Dedupe bằng idempotency key và handoff ID.

**Hoàn thành khi:** backend restart sau commit/trước Redis delivery vẫn phát lại
được đúng một handoff logic.

### Giai đoạn 5 — Mở rộng `TeamSay`

- [ ] Thêm các optional field, giữ nguyên `content`/`to`.
- [ ] Nhánh legacy giữ nguyên code path hiện tại.
- [ ] Nhánh structured gọi `HandoffService` sau khi roster đã resolve.
- [ ] Không thay `deliver_to_inbox` và `InboxMiddleware`.
- [ ] Cập nhật tool description để agent biết gửi summary/facts/decisions thay vì
  reasoning nội bộ.

**Hoàn thành khi:** toàn bộ test TeamSay cũ vẫn pass và structured call đến đúng
session.

### Giai đoạn 6 — Wiring vào runtime hiện có

- [ ] Thêm optional dependency qua `_app.py` -> `ChatService` -> `get_toolkit`
  -> `TeamSay`.
- [ ] Trong Workforce Phase-C composition, tạo repository/service bằng UOW và
  job service hiện có rồi inject.
- [ ] `WorkflowCheckpoint.shared_state_ref` nhận snapshot ID mới nhất sau turn.
- [ ] Đồng bộ `pending_task_ids` với trạng thái task, không tạo pending registry
  cạnh tranh.
- [ ] Generic team không có workflow vẫn dùng `group_id/task_id` và scope owner.

**Hoàn thành khi:** cả UI chat thường và partner workflow dùng cùng TeamSay
implementation, không có hai shared-context engine.

### Giai đoạn 7 — Prompt/skill guidance

- [ ] Bổ sung hướng dẫn ngắn vào template worker hiện có:
  - dùng `task_id` xuyên suốt;
  - khi gọi agent mới phải gửi current request rõ ràng;
  - chỉ đưa confirmed facts/decisions/open questions vào context delta;
  - không gửi private reasoning;
  - kết quả cuối vẫn báo Leader.
- [ ] Không nhồi toàn bộ quy trình vào system prompt. Nếu hướng dẫn dài, tạo một
  skill `structured-team-handoff` và gắn cho Leader/worker.

**Hoàn thành khi:** agent tạo structured handoff ổn định mà không cần người dùng
viết tay JSON.

### Giai đoạn 8 — UI quan sát tối thiểu

- [ ] Project event đã sanitize: sender, recipient, task, status, timestamp.
- [ ] Không phát raw shared context hoặc internal group ID ra partner API.
- [ ] Timeline manager có thể xem handoff/task progress trong đúng workflow.
- [ ] UI không phải điều kiện để agent runtime hoạt động.

**Hoàn thành khi:** Area Manager xem được A -> B -> A -> C và trạng thái task,
nhưng không thấy chain-of-thought.

### Giai đoạn 9 — E2E và hardening

- [ ] Chạy scenario A/B/C đầy đủ.
- [ ] Kiểm tra concurrent updates, retry, restart, duplicate và loop limit.
- [ ] Kiểm tra hai group cùng dùng một agent version không lẫn context.
- [ ] Kiểm tra hai ticket của cùng external user không lẫn context.
- [ ] Kiểm tra revoke/close workflow ngăn delivery mới.
- [ ] Đo prompt size và latency trước/sau.
- [ ] Viết runbook dọn retention và xử lý pending delivery.

## 14. Test matrix bắt buộc

| Mã | Tình huống | Kết quả mong đợi |
|---|---|---|
| SC-01 | Legacy `TeamSay(content,to)` | Hành vi không đổi |
| SC-02 | A hỏi B, B trả A, A gọi C | C nhận objective + facts/kết quả liên quan |
| SC-03 | C chưa từng nhận message trước | C vẫn hiểu nhờ snapshot hydration |
| SC-04 | A và B cập nhật context đồng thời | Hai thay đổi được merge hoặc một bên retry, không lost update |
| SC-05 | Retry cùng idempotency key | Một handoff logic duy nhất |
| SC-06 | Crash sau DB commit, trước Redis | Pending handoff được phát lại |
| SC-07 | Message Redis bị lặp | Context C chỉ inject một handoff ID |
| SC-08 | Agent ngoài group được chọn | Từ chối trước persistence/delivery |
| SC-09 | Context ref của group khác | Từ chối, không rò dữ liệu |
| SC-10 | Hai ticket cùng user | Context hoàn toàn tách biệt |
| SC-11 | Hop count vượt giới hạn | Dừng và báo Leader |
| SC-12 | Task đã cancelled/completed | Không tiếp tục tự giao task |
| SC-13 | Artifact thuộc scope khác | Từ chối reference |
| SC-14 | Context vượt token budget | C vẫn nhận constraints/facts/questions quan trọng |
| SC-15 | Workflow bị revoke/closed | Không phát handoff mới |
| SC-16 | PostgreSQL restart | Snapshot/handoff còn đủ để resume |

## 15. Acceptance scenario chính

Input:

```text
Leader -> A:
Phân tích yêu cầu mất điện tại Ocean Park 1.

A -> B:
Hãy xác định mức độ sự cố theo quy định.

B -> A:
Mức độ high; cần biết số tòa bị ảnh hưởng.

A -> C:
Kiểm tra dữ liệu có đủ tạo ticket hay chưa.
```

Context thực tế của C phải chứa ít nhất:

```text
Objective: Phân tích yêu cầu mất điện tại Ocean Park 1.
Confirmed fact: Mức độ high.
Open question: Số tòa bị ảnh hưởng.
Current request: Kiểm tra dữ liệu có đủ tạo ticket hay chưa.
Source: handoff của B -> A và A -> C.
```

C không được nhận:

- Toàn bộ lịch sử riêng của session A hoặc B.
- Reasoning nội bộ của A/B.
- Message thuộc ticket/group khác.
- Credential, system prompt hoặc dữ liệu ngoài scope.

## 16. Thứ tự commit đề xuất

Một người thực hiện theo các commit nhỏ, có thể rollback độc lập:

1. `test(team): lock current TeamSay and inbox behavior`
2. `feat(workforce): add shared-context and handoff contracts`
3. `feat(workforce): add shared-context SQL repositories`
4. `db: add shared-context and handoff tables`
5. `feat(workforce): build deterministic context packets`
6. `feat(team): add optional structured TeamSay handoffs`
7. `feat(runtime): wire handoff service into existing toolkit`
8. `feat(workforce): pin shared context in workflow checkpoints`
9. `test(workforce): cover A-B-A-C context continuation`
10. `docs(workforce): add shared-context operations runbook`

Không gom migration, repository, TeamSay, runtime wiring và UI vào một commit.

## 17. Ước lượng cho một người

| Giai đoạn | Ước lượng |
|---|---:|
| Baseline + contracts | 1–2 ngày |
| SQL + migration + repository | 2–3 ngày |
| Context/Handoff services | 2–3 ngày |
| TeamSay + runtime wiring | 2 ngày |
| E2E, race/retry/security | 2–3 ngày |
| UI quan sát và tài liệu | 1–2 ngày |

Tổng dự kiến: **10–15 ngày làm việc** cho một người, tùy mức hoàn thiện của
concrete `LeaderTurnRunner` tại thời điểm bắt đầu tích hợp.

## 18. Definition of Done

Chỉ coi hoàn thành khi:

- [ ] Agent C hiểu được kết quả trao đổi A/B mà không đọc toàn transcript A/B.
- [ ] Shared context tồn tại sau restart và được pin đúng revision/snapshot.
- [ ] Redis không phải nguồn dữ liệu duy nhất.
- [ ] Không có cross-tenant/domain/area/manager/group/ticket leakage.
- [ ] Không lưu chain-of-thought.
- [ ] Legacy TeamSay và các test team hiện có vẫn pass.
- [ ] Duplicate/retry/concurrency không làm mất hoặc nhân đôi logic handoff.
- [ ] Context packet nằm trong token budget cấu hình.
- [ ] Leader nhận được kết quả cuối hoặc lỗi có cấu trúc từ worker.
- [ ] PostgreSQL migration chạy được upgrade/downgrade/upgrade trên local.

