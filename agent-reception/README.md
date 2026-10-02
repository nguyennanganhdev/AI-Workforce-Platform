# Reception Agent

Nền tảng PH01 cho Reception bằng Bun/TypeScript. Package và `bun.lock` riêng,
không thuộc root workspaces. Dependency trực tiếp được pin theo sample
`agent-langgraph`; dependency gián tiếp được khóa trong lockfile.

## Setup

Cài [Bun 1.3.14](https://bun.sh/docs/installation) theo `packageManager` của repo.
Chạy từ `agent-reception/`:

```sh
bun install --frozen-lockfile --ignore-scripts
```

Để chạy service, copy `.env.example` thành `.env`, điền key đúng provider.
Không cần `.env`, key thật, backend hoặc database để chạy test/typecheck.
Test dùng credential giả từ fixture; preload tắt remote tracing kể cả khi shell đã bật.

| Biến | Mặc định / yêu cầu |
|---|---|
| `PORT` | `4202`; số nguyên thập phân trong 1–65535 |
| `HOST` | `0.0.0.0`; local có thể đặt `127.0.0.1` |
| `RECEPTION_MODEL_PROVIDER` | `openai`, `anthropic` hoặc `google`; mặc định `openai` |
| `RECEPTION_MODEL` | Để trống dùng mặc định theo provider: `gpt-5.5`, `claude-sonnet-4-5`, `gemini-2.5-flash`; deployment nên đặt model đã được cấp quyền |
| `OPENAI_API_KEY` / `ANTHROPIC_API_KEY` / `GOOGLE_API_KEY` | Chỉ key của provider được chọn là bắt buộc |

Config được validate trước khi mở listener. PH01 kiểm tra cấu hình và tạo SDK
client, chưa kiểm tra model/key có được provider chấp nhận bằng request thật.

## Commands

```sh
bun run dev
bun run start
bun run test
bun run typecheck
```

Phần workflow nghiệp vụ viết bằng Python. Cài dependency cố định rồi chạy test:

```sh
python -m pip install -r requirements.txt
python -m pytest tests
```

Để cài cả công cụ kiểm thử Python với phiên bản cố định:

```sh
python -m pip install -r requirements-test.txt
python -B -m pytest -q -p no:cacheprovider tests
python -m ruff check src/tools tests/tools
python -m ruff format --check src/tools tests/tools
```

`src/tools/backend.py` gọi các endpoint nội bộ có thể cấu hình để thực thi/reconcile
operation. Backend phải xác nhận `linked_file_ids` cho thao tác bổ sung ảnh. URL thật,
service credential và API của Team Chiến không được hard-code trong graph.

`src/persistence/sqlite.py` cung cấp checkpointer SQLite bền vững cho local/test.
Production nhiều replica cần thay bằng checkpointer PostgreSQL tương thích. Khi một
thread chưa có checkpoint, `resolve_session` lấy snapshot ticket/file đã xác minh từ
backend theo contract trong `src/persistence/recovery.py`.

`GET /health` trả HTTP 200 và `{"status":"ok"}`, với `Cache-Control: no-store`.
Đây là liveness của bootstrap, chưa phải readiness của graph/backend/model.
Mọi route/method khác trả 404. Không có run endpoint hoặc mock nghiệp vụ production.

`src/index.ts` export `createReceptionRuntime(config, modelFactory?)` và
`startReceptionService(config?)`. Import không đọc env, tạo model hoặc mở listener.
Chạy trực tiếp mới khởi động service; SIGINT/SIGTERM dừng listener.
PH04 sử dụng model trả về để inject vào graph; test gọi `server.stop(true)` để dọn tài nguyên.

## Runtime service (Python)

`src/runtime/` ghép graph nghiệp vụ với model, backend và nơi lưu phiên thành một service chạy được:

```sh
python -m pip install -r requirements.txt
python -m uvicorn src.runtime.service:create_app --factory --host 127.0.0.1 --port 4202
```

Trên Windows: chép `.env.example` thành `.env`, điền giá trị, rồi chạy `scripts/start_runtime.ps1`
(script nạp `.env` và dùng `.venv` nếu có). Không ghi key thật vào `.env.example`.

Biến môi trường ở `.env.example` (`RECEPTION_SERVICE_TOKEN`, `RECEPTION_BACKEND_URL`, `RECEPTION_MODEL`,
`OPENAI_API_KEY`). Backend bật bằng `VINHOMES_API_RECEPTION_SERVICE_TOKEN`, `VINHOMES_API_RECEPTION_URL` và
`RECEPTION_DELEGATION_KEY` (khóa ký chỉ backend giữ).

- `POST /v1/turns` (Bearer service token): backend gọi sau khi tin nhắn cư dân đã commit. Service chạy một
  lượt graph theo từng cuộc trò chuyện rồi ghi câu trả lời qua `POST /internal/reception/chats/{id}/replies`.
  App cư dân chỉ đọc hội thoại từ backend.
- Ủy quyền: service token chỉ chứng minh lời gọi đến từ backend. Mỗi lượt, backend mở một run gắn với phiên
  của cuộc trò chuyện và gửi kèm token ngắn hạn (`delegation`). Runtime dùng token đó cho mọi lời gọi ngược về
  backend và tìm tri thức; token chỉ giữ trong bộ nhớ, không ghi vào checkpoint, và hết hiệu lực khi lượt kết thúc.
- `runtime/backend.py` là lớp chuyển đổi: hợp đồng backend là chuẩn (draft chưa phải ticket, handoff tạo ticket,
  kết quả phẳng). Graph thấy draft dưới một `ticket_id` ổn định; từng operation được dịch sang
  `/internal/reception/v1/execute`. Backend tự suy ra cư dân, tenant, run từ token.
- Policy (khẩn cấp, cần nhân viên) do backend quyết định ở `/internal/reception/policy/evaluate`; model chỉ đề xuất.
- `runtime/knowledge.py` gọi `search_knowledge` v1 khi có `RECEPTION_KNOWLEDGE_URL` và chỉ trả lời từ passage có trích dẫn.
  Passage phải nói về đúng đối tượng được hỏi (hỏi Masteri mà chỉ có nguồn Sapphire thì coi là không đủ nguồn);
  câu trả lời kết thúc bằng dòng `(Nguồn: <tiêu đề tài liệu>)` do code ghép, không phải model viết.
  Kho tri thức nạp bằng `server/src/knowledge/publish.ts`, dịch vụ tìm kiếm chạy bằng `server/src/knowledge/serve.ts`.
- `runtime/voice.py` viết lại câu trả lời cố định của graph cho tự nhiên; không được thêm dữ kiện hay cam kết.
- Lớp chuyển đổi chỉ ghi vào yêu cầu các dữ kiện cư dân tự nêu (`customer_report`); dữ kiện model tự suy luận bị bỏ,
  vì backend từ chối loại này và cả yêu cầu sẽ bị rơi.
- `runtime/model.py` gọi chat completions kiểu OpenAI với đầu ra JSON.

Chưa có trong runtime: nhận sự kiện từ Supervisor (chưa có Supervisor chạy), trả lời tương tác của Supervisor,
self-help (backend trả 501 nên graph mời hỗ trợ trực tiếp), checkpointer PostgreSQL cho nhiều replica.

Đánh giá hội thoại với model thật: `tests/evals/run_live.py` gửi 52 kịch bản tiếng Việt
(`tests/evals/live_conversations.vi.json`) qua API cư dân rồi chấm bằng dữ kiện từ backend (có tạo yêu cầu
không, mức ưu tiên, có lượt nào hỏng không) và bằng một model chấm độ tự nhiên, độ đúng. Lệnh này tốn lượt gọi
model và tạo yêu cầu thật, nên chỉ chạy trên database tạm:

```sh
python tests/evals/run_live.py --backend http://127.0.0.1:8011 --only emergency
```

Điểm gốc 03/10/2026 (graph cố định, `gpt-5.4-mini`, chấm bằng `gpt-5.4`, hai lần chạy): đạt kiểm tra cứng
85–88%, đạt phát biểu 87–88%, tự nhiên 4,2–4,4/5, trễ trung vị 6 giây. Nhóm yếu nhất: tin nhắn mơ hồ (33%).

Kiểm thử đầu-cuối qua HTTP thật: `tests/runtime/test_resident_chat_e2e.py` (cần backend, runtime và
`tests/runtime/fake_llm.py`; model trong test là stub xác định, không phải LLM thật).

## Internal contracts

`src/contracts/index.ts` là **đề xuất nội bộ `0.1.0-draft.1`**, state schema v1.
Phan Dũng/Dương Dũng và owner C06 cần review trước khi freeze/commit interface.
TypeScript không xác thực payload runtime và tên `VerifiedReceptionContext`
không tự chứng minh quyền; PH02 phải lấy context từ backend đã xác minh.

- Context tách service principal khỏi user khởi tạo, có tenant/binding/run/request và permissions.
- Tool port ràng buộc operation với input/output của catalog do DD01/DD02 cung cấp;
  yêu cầu idempotency key bền vững và timeout, hỗ trợ `AbortSignal`.
  `accepted` khác `success`; lỗi mất response có `outcome: "unknown"` để consumer
  không kết luận mutation chưa xảy ra hoặc tự retry bằng key mới.
- Graph factory nhận model, tool port và `BaseCheckpointSaver` đúng dependency đã pin;
  không có default saver. Có interface read/run/stream/resume, terminal result và interrupt.
  State nghiệp vụ/facts vẫn do PD01 thiết kế trong `src/graph/`.
- Resume tách input cư dân và event backend. PH03 kiểm tra nguồn, binding/interrupt,
  ticket/generation, aggregate version và dedup trước khi thực thi.

Chi tiết semantic, version/migration và việc cần chốt:
[hợp đồng PH01](../docs/teams/hoang/integration/PH01_CONTRACTS.md).

## Tests và phạm vi

- `tests/runtime/`: config, import không side effect, bootstrap HTTP và CLI lỗi;
  `contracts.typecheck.ts` kiểm tra consumer bằng `tsc`, không chạy như test runtime.
- `tests/adapters/`: factory provider và health routing không lộ request/config.
- `tests/support/`: fixture tổng hợp, scripted model/tool và `MemorySaver` chỉ dùng trong test.
- `tests/integration/`: spike capability LangGraph thật với fake ports: checkpoint,
  stream, interrupt/resume và hai thread độc lập trong RAM.

Test này **chưa chứng minh** restart/multi-replica, auth, dedup event hay durability;
đó là PH02/PH03. Chưa có backend/model thật hoặc Reception business graph được nối.

## Reuse và bàn giao

[Kế hoạch reuse sample](../docs/teams/hoang/integration/PH01_REUSE_PLAN.md) ghi module,
giới hạn và task tiếp nhận. [Handoff PH01](../docs/teams/hoang/handoffs/phan-hoang/PH01.md)
ghi bằng chứng kiểm thử. [Request C01/C06/P01 và review nội bộ](../docs/teams/hoang/requests/phan-hoang/PH01_DEPENDENCIES.md)
ghi các dependency còn mở; file request chưa đồng nghĩa đã gửi hoặc được owner chấp thuận.

## Reception tools — PH16

`src/tools/facade.py` cung cấp `ReceptionTools` với 14 method có input/output riêng.
`src/tools/contracts.py` định nghĩa model strict; `src/tools/validation.py` giữ catalog
và kiểm tra từng operation, độc lập với HTTP. `BackendToolPort` dùng chung các bộ
kiểm tra này cho `execute` và `reconcile`; cấu hình đường dẫn HTTP vẫn được giữ.

Đây là **consumer proposal `ph16.draft.1`**, chưa phải OpenAPI đã được Team Chiến
freeze. Supervisor output dùng schema **2.0** đã chốt trong tài liệu liên team.
Graph Python hiện vẫn dùng V1 và generic `invoke`, chưa chuyển sang facade. Không
inject adapter mới vào graph cũ rồi coi là tích hợp hoàn tất. Xem
[request chuyển consumer/API](../docs/teams/hoang/requests/phan-hoang/PH16_TYPED_TOOLS_INTEGRATION.md).

| Method | Input | Giá trị khi `kind=success` |
|---|---|---|
| `create_ticket_draft` | `DraftInput` | `Ticket` |
| `get_verified_resident_context` | `ProfileInput` | `ProfileOutput` |
| `update_ticket_incident` | `IncidentInput` | `IncidentOutput` |
| `submit_ticket_assessment` | `AssessmentInput` | `AssessmentOutput` |
| `resolve_management_destination` | `TicketRef` | `RouteOutput` |
| `handoff_ticket` | `HandoffInput` | `HandoffOutput` |
| `register_supervisor_wait` | `WaitInput` | `WaitOutput` |
| `get_supervisor_event` | `EventInput` | `SupervisorEvent` V2 |
| `append_ticket_information` | `AppendInput` | `AppendOutput` |
| `respond_supervisor_interaction` | `InteractionInput` | `InteractionOutput` |
| `request_ticket_cancellation` | `CancellationInput` | `CancellationOutput` |
| `get_ticket_status` | `TicketRef` | `StatusOutput` |
| `process_self_help` | `SelfHelpInput` | `SelfHelpOutput` |
| `escalate_emergency` | `EmergencyInput` | `EmergencyOutput` |

Mỗi method nhận `context: VerifiedContext` và `idempotency_key` qua keyword-only
arguments. Context phải đến từ resolver đã xác thực, không lấy từ model/browser;
kiểm tra hình dạng context không thay thế kiểm quyền tại backend. Chỉ gửi năm
trường context trong kế hoạch: tenant/principal/binding/run/request; không truyền
checkpoint, permissions hoặc signal vào HTTP.

Các method trả `Success[Output] | Accepted | Failure`. Consumer phải phân nhánh
theo `kind`: `accepted` chưa có kết quả; `failure.outcome=unknown` giữ pending
operation để reconcile bằng cùng input/context/key, không tạo mutation mới.
`ToolContractError` sau khi đã gửi HTTP cũng không chứng minh mutation chưa xảy ra.

```python
from src.tools import ReceptionTools
from src.tools.contracts import DraftInput, VerifiedContext

# tools được runtime inject; context đã resolve; stable_key đã lưu trong pending.
async def create_draft(
    tools: ReceptionTools, context: VerifiedContext, channel_id: str, stable_key: str
):
    return await tools.create_ticket_draft(
        DraftInput(channel_id=channel_id, handoff_reason="needs_staff"),
        context=context,
        idempotency_key=stable_key,
    )
```

Catalog có `visibility="system/internal"`, `LLM_TOOLS` rỗng; không đăng ký facade,
`invoke` hay `reconcile` qua `model.bind_tools`. Input từ chối field ngoài schema,
coercion kiểu dữ liệu và trường quyền/định tuyến tự khai. Backend phải lấy hồ sơ,
triage và đích quản lý đã xác minh để dựng bản tin bàn giao V2. Schema message V2
đầy đủ giữa backend và Supervisor không bị thay bằng input operation tối giản.

`file_ids` được loại trùng, không nhận URL/bytes. Success của update/append và
interaction accepted phải có xác nhận liên kết đủ file. Handoff cần `persisted`
và `enqueued` là boolean `true`, đúng ticket/generation/version/correlation.
Event V2 được kiểm tenant/binding/ticket/correlation; completion cần kết quả
`work_completed`, chưa có nghĩa ticket đã đóng. Backend vẫn chịu trách nhiệm
phân quyền, chống stale mutation và tính hợp lệ của bước đang chờ.

[Handoff PH16](../docs/teams/hoang/handoffs/phan-hoang/PH16.md) ghi kết quả kiểm thử
và phần consumer/backend còn chờ. Fixtures chỉ nằm trong tests; không có backend
giả hoặc model giả trong production path.
