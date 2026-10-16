# Kiểm chứng P0: ASK từ middleware có đỗ lượt trong `dont_ask`, và tự resume được không

Ngày 2026-10-10. Nhánh `feat/platform-core`. Câu hỏi thuộc `docs/WORKFORCE_V1_DAC_TA_TRIEN_KHAI.md` §6.1 ("Cần xác minh ở P0") và giả định A4.

## Kết luận

**Xác nhận.** §6.1 đúng như đã viết. Các điểm chi tiết đều có test chạy (15 test, xanh 3 lần liên tiếp). Có 5 chỗ spec cần nói rõ hơn hoặc điều chỉnh, xem mục "Điều chỉnh spec".

## Cách làm

- Dựng một app AgentScope thật bằng `create_app` (SQLite, `InMemoryMessageBus`, `LocalWorkspaceManager`), gắn middleware và tool của probe qua `extra_agent_middlewares` / `extra_agent_tools` (cùng đường lõi `awp` dùng). Phiên tạo và đặt `permission_mode=dont_ask` bằng REST như `AgentScopeClient.new_session`.
- Model là máy chủ OpenAI-compatible giả có kịch bản (`p0_ask_park_llm.py`, mỗi request được ghi lại để biết model thấy gì).
- Không dùng `awp.app.build_app` và không dùng `ToolGateMiddleware`/`Case*` thật: probe chỉ cô lập cơ chế AgentScope. Điểm tương tác với `ToolGateMiddleware` suy từ đọc mã (xem điều chỉnh số 1).
- Chạy: `cd platform_VP/core && PYTHONPATH=src ../agentscope/.venv/Scripts/python.exe -m pytest -q tests/probes/test_p0_ask_park.py` → `15 passed` (chạy 3 lần: 17 s, 17 s, 49 s do máy bận; không test nào chập chờn).

File:
- `platform_VP/core/tests/probes/p0_ask_park_gate.py`: `ApprovalGate`, `confirm_event_from_record`, `canonical`/`args_hash`, kho giả `ApprovalStore`, tool `Charge` (có tác dụng phụ) và `Refund` (đối chứng), `build_probe_app`, `Probe` (bọc REST).
- `platform_VP/core/tests/probes/p0_ask_park_llm.py`: model giả.
- `platform_VP/core/tests/probes/test_p0_ask_park.py`: 15 test.

## Kết quả theo từng câu hỏi

| # | Câu hỏi | Kết quả | Test |
|---|---|---|---|
| 1 | Đối chứng: ASK do tool/engine trong `dont_ask` | Bị đổi thành DENIED, không đỗ. Đúng như đọc mã. | `test_control_engine_ask_in_dont_ask_is_denied_not_parked` |
| 2 | ASK từ `on_check_permission` của middleware có đỗ trong `dont_ask`? | **Có.** Tool không chạy, state `ASKING` được lưu vào `AgentState.context`, `permission_context.mode` vẫn `dont_ask`. Model chỉ được gọi 1 lần. | `test_middleware_ask_parks_in_dont_ask` |
| 3 | `GET /sessions/{id}/status` khi đỗ | `awaiting_permission` (sau khi khóa phiên nhả). Lúc lượt còn chạy là `running` (đọc từ mã; test chỉ chờ qua trạng thái này). Tối ưu hơn là đọc `wf_approvals` của ta, đừng dùng status làm nguồn sự thật. | cùng test trên, `settle()` |
| 4 | `on_reply` thấy gì khi đỗ | Chuỗi item: `ReplyStartEvent, HintBlockEvent, ModelCallStartEvent, ToolCall*Event, ModelCallEndEvent, RequireUserConfirmEvent, Msg`. **Không có `ReplyEndEvent`.** Item cuối là một `Msg` ("I'm waiting for your permission..."), generator kết thúc bình thường. Cách nhận biết: thấy `RequireUserConfirmEvent` và không thấy `ReplyEndEvent`. | cùng test trên |
| 5 | Resume bằng `UserConfirmResultEvent` do ta dựng từ dữ liệu đã lưu, qua `POST /chat` | Đạt. `POST /chat` trả `200 {"status":"started"}`; tool chạy đúng 1 lần; model nhận kết quả `charged 550000`; lượt resume kết thúc `ReplyEndEvent(COMPLETED)`; tool call chuyển `finished`. Không có allow-rule nào còn lại trong `permission_context`. | `test_resume_approve_via_post_chat_runs_tool_once_and_asks_once` |
| 6 | Resume từ chối | Kết quả tool là `DENIED`, tool không chạy, model được báo "denied" và đi tiếp (mặc định `stop_on_reject=False`). Call bị từ chối không qua `on_check_permission` lần nữa. | `test_resume_reject_returns_denied_and_tool_never_runs` |
| 7 | Resume bằng `enqueue_run_trigger(kind="resume")` (không HTTP) | Đạt, cùng kết quả. | `test_resume_via_enqueue_run_trigger` |
| 8 | Call đã `ALLOWED` có qua `on_check_permission` của ta lần nữa, có hỏi hai lần không | Có qua, và không hỏi lại. Nhật ký gate: `[("pending","ask"), ("allowed","pass")]`, một dòng approval duy nhất. | test 5 |
| 9 | Đổi tham số lúc resume | AgentScope **ghi đè** `tool_call.input` bằng giá trị trong sự kiện rồi chạy. Gate của probe so `sha256` của input ở lần `ALLOWED` với hash đã lưu; khác thì DENY, tool không chạy. | `test_tampered_resume_input_is_refused_by_the_gate` |
| 10 | Tin nhắn bình thường POST lúc đang đỗ (A4) | Xem bên dưới. | `test_user_message_while_parked_...` |
| 11 | Duyệt tool của worker (team member) | Đạt, cả hai đường: (a) POST thẳng vào `agent_id`/`session_id` của worker lấy từ bản ghi approval; (b) POST vào phiên leader, AgentScope tự định tuyến theo `reply_id`. Gate chạy trên worker như trên leader (factory middleware được gọi cho mọi agent). Leader nhận thẻ phản chiếu `subagent_require_user_confirm` và nhận `subagent_user_confirm_result` khi xong. Leader không bị đỗ. | `test_worker_tool_call_parks_and_can_be_resumed[worker|leader]` |
| 12 | Hỏi lại cùng một call (chạy lại lượt mất) | Khóa `(session_id, tool_call.id)` cho đúng một dòng. | `test_asking_again_for_the_same_call_...` |
| 13 | Hai tool call cần đồng ý trong cùng một reply | Đỗ ở call đầu; call thứ hai nằm `PENDING`. Chỉ sau khi quyết định call đầu thì lượt resume mới chạy tiếp và **đỗ lần nữa** ở call thứ hai (một approval mới). Từ chối call thứ hai thì lượt kết thúc `COMPLETED`. | `test_two_gated_calls_in_one_reply_park_one_at_a_time` |
| 14 | Hủy approval treo (A9 hết hạn) | `enqueue_run_trigger(kind="resume", inputs=UserInterruptEvent(reply_id=...))`: tool call thành `INTERRUPTED`, lượt kết thúc `ReplyEndEvent(INTERRUPTED)`, **model không được gọi**, phiên rảnh và nhận tin mới bình thường. | `test_cancel_a_parked_approval_with_user_interrupt` |
| 15 | Quyết định gửi ngay khi dòng approval vừa xuất hiện (lượt đỗ chưa nhả khóa) | Đạt: dispatcher chờ khóa nhả rồi chạy; tool chạy đúng 1 lần. | `test_resume_posted_before_the_parked_turn_has_released_the_session` |
| 16 | Gửi trùng cùng một quyết định | Lượt resume thứ hai lỗi `ValueError: Agent is not waiting for user confirmation...` (có traceback trong log); tool không chạy lần hai; phiên về `idle`. Đây là lưới an toàn dưới idempotency của ta, không thay nó. | `test_same_approval_sent_twice_runs_the_tool_once` |
| 17 | Thứ tự middleware | Middleware đứng đầu danh sách là lớp ngoài cùng. Một DENY ở lớp ngoài thắng, gate (trong) không thấy call. | `test_first_middleware_in_the_list_is_outermost_...` |

### Câu 10: tin nhắn thường khi đang đỗ (A4), chi tiết chính xác

Quan sát được khi `POST /chat` với `Msg` lúc phiên đang `awaiting_permission`:
- `POST /chat` trả **`200 {"status":"started"}`**, không có lỗi cho người gọi (fire-and-forget).
- Trong agent: `_check_incoming_event` ném `ValueError: Agent is waiting for 1 tool calls and external execution results for 0 tool calls, but received no event.` `on_reply` của ta thấy ngoại lệ này đi qua; **không có item nào được phát** (không `ReplyStart`/`ReplyEnd`); model **không** được gọi.
- Tin của người dùng **được lưu** vào bảng `messages` (`role=user`) vì `ChatService` upsert trước khi gọi agent, nhưng **không** nằm trong `state.context` và model không bao giờ thấy nó (kiểm cả sau khi resume: chuỗi "joke" không có trong request model).
- `ChatService` thêm một tin `assistant` rỗng (`content=[]`, id mới, không đè tin của lượt đỗ) và phát lên kênh phiên cặp `REPLY_START` + `REPLY_END(finished_reason="error", error.type="setup")` với reply_id mới. Thông báo lỗi kèm theo là câu chung chung "The session could not be prepared".
- Phiên **vẫn đỗ** (`ASKING` còn nguyên) và vẫn resume được bình thường sau đó.

Hệ quả: không thể dựa vào AgentScope để trả `409 APPROVAL_PENDING`. Lớp API của ta phải kiểm trạng thái workflow/approval *trước khi* gọi `/chat`, và không bao giờ đẩy tin cư dân vào phiên đang đỗ.

## Điều chỉnh spec

Không có điểm nào làm sai §6.1. Các điều chỉnh là bổ sung:

1. **§6.1 và `ToolGateMiddleware` (đọc `awp/middleware/room.py:214-228`, chưa chạy).** `on_check_permission` hiện trả `ALLOW` ngay cho mọi tool có tiền tố `Case`/`Team`/`AgentCreate`/`AgentInvite` mà không gọi `next_handler`. `CaseAskConsent` bắt đầu bằng `Case` nên sẽ bị cho qua trước khi tới cổng approval. Cách làm: đặt logic consent *bên trong* `ToolGateMiddleware.on_check_permission`, sau kiểm `allowed(name)` và trước nhánh `OWN_TOOLS`; hoặc đặt `ApprovalGate` trong danh sách *sau* `ToolGateMiddleware` và sửa nhánh `OWN_TOOLS` để không trả sớm với tool cần đồng ý. Test 17 xác nhận middleware đầu danh sách là lớp ngoài cùng.
2. **§6.1 bước "ghi `wf_approvals`... khóa theo `(session_id, tool_call.id)`".** Giữ nguyên, kiểm chứng đạt (test 12). Thêm: ở lần `ALLOWED`, gate phải kiểm dòng đã `approved` **và** `sha256(input)` bằng `arguments_hash` đã lưu, nếu không thì DENY (test 9). Lý do: AgentScope ghi đè input bằng input trong sự kiện.
3. **§5 `settle` và §9 job `approval_resume`.** Một lượt resume có thể **đỗ lần nữa** (hai tool cần đồng ý trong cùng một reply, test 13) và khi đó cũng không có `ReplyEndEvent`. `settle` phải coi `RequireUserConfirmEvent` (hoặc dòng approval `pending` mới) là điểm kết thúc lượt ở *mọi* lượt, không riêng lượt đầu; workflow lại là `awaiting_approval` với approval mới, `workflow_revision` tăng.
4. **A4, câu "AgentScope lỗi khi nhận tin mới lúc đang đỗ".** Đúng, nhưng lỗi **không** hiện ra ở `POST /chat` (200) mà ở agent, kèm tin người dùng bị lưu vào `messages`, một tin trợ lý rỗng và một cặp REPLY_START/END(error) lên kênh phiên (mục câu 10). Vì vậy `409 APPROVAL_PENDING` phải do ta quyết định trước khi ghi job, và không được relay kênh phiên của AgentScope ra ngoài (đã là quyết định của spec).
5. **A9 hết hạn approval.** Dùng `UserInterruptEvent` qua `enqueue_run_trigger(kind="resume", ...)`. `POST /chat` **không** nhận được `UserInterruptEvent` (`ChatRequest.input` chỉ có `Msg`, `list[Msg]`, `UserConfirmResultEvent`, `ExternalExecutionResultEvent`, `None`), nên phải gọi hàm Python (nằm ở module `agentscope.app._bus_ops`, tên có gạch dưới: phụ thuộc nội bộ, cần ghi nhận) hoặc `POST /sessions/{id}/interrupt` (chưa kiểm ở đây). Lượt hủy không gọi model, nên sau hủy platform phải tự xếp một job đánh thức leader để báo "approval hết hạn" nếu muốn leader nói với cư dân.

Ngoài ra, không cần sửa `docs/WORKFORCE_V1_DAC_TA_TRIEN_KHAI.md` ở phần dòng "Cần xác minh ở P0 ... Nếu không, thay bằng cách khác": phương án thay thế **không cần**. Nên cập nhật dòng đó thành "đã xác minh bằng test, xem `docs/research/KIEM_CHUNG_P0_ask_park.md`".

## Dùng lại

- `ApprovalGate.on_check_permission` và `on_reply` trong `tests/probes/p0_ask_park_gate.py`: bản tối thiểu của cổng. Khi chuyển vào `awp`, thay `ApprovalStore` (bộ nhớ) bằng ghi `wf_approvals` + event + `revision` trong một giao dịch (§6.1 bước 2) và thay tập `consent` cố định bằng "CaseAskConsent + `wf_tools.requires_consent` của route".
- `confirm_event_from_record(rec, confirmed)`: dựng `UserConfirmResultEvent` từ `ToolCallBlock` đã lưu (`tool_call.model_dump(mode="json")` lúc ASK) với `input` là JSON chuẩn hóa đã lưu, `rules=None`, `reply_id` lấy từ `agent.state.reply_id` lúc ASK.
- `Probe` (bọc REST: tạo agent/phiên, `say`, `chat_event`, `status`, `settle`, `tail_events`) cho các test engine giả/thật sau này.

## Chưa kiểm / hạn chế (nói thẳng)

- Chỉ chạy một tiến trình, `InMemoryMessageBus`, SQLite, model giả có kịch bản. Không có Redis/Postgres, không có nhiều tiến trình. Hành vi "resume ở tiến trình khác" và khóa phiên phân tán không được kiểm.
- Không kiểm crash: nếu tiến trình chết sau khi ghi dòng approval nhưng trước khi lưu `AgentState` (cuối lượt) thì dòng approval mồ côi và state `ASKING` mất (đã nêu trong `AGENTSCOPE_CHO_WORKFORCE_V1.md` §3 rủi ro 3); chưa có test.
- Không dùng `awp.app.build_app`, `ToolGateMiddleware`, `Binding`, `Case*` thật. Điều chỉnh số 1 là suy ra từ đọc mã, chưa chạy.
- Chưa chạy trường hợp truyền `ConfirmResult.rules`: chỉ khẳng định (từ mã) rằng rule sẽ ở lại `permission_context` của phiên; test chỉ kiểm rằng khi không truyền `rules` thì `allow_rules` rỗng sau approve.
- `POST /sessions/{id}/interrupt` cho phiên đang đỗ chưa chạy; chỉ kiểm đường `enqueue_run_trigger` với `UserInterruptEvent`.
- Chỉ thử công cụ `Charge` có `is_concurrency_safe=False`; công cụ concurrency-safe cần ASK (nhiều ASK cùng lúc trong một batch song song, có khử trùng lặp theo `kept_rules`) không được thử.
- Chưa thử `permission_mode` khác `dont_ask` (ví dụ `bypass`); theo mã, quyết định ASK của middleware được dùng trực tiếp ở mọi mode nhưng điều này không được test.
- Phiên bản test chỉ chứng minh cơ chế. Hành vi model thật (có thể gọi tool theo cách khác, gọi hai tool một lúc, hay bỏ cuộc sau DENIED) không được đo.
