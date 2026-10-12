# AgentScope cho Workforce v1: cái có sẵn, cái ghép được, cái phải tự làm

Ngày 2026-10-10. Nhánh `feat/platform-core`. Chỉ đọc mã vendored `platform_VP/agentscope/src/agentscope` và lõi `platform_VP/core/src/awp`; không chạy thử gì, không sửa mã.
Đối chiếu với `CONTRACT_TICH_HOP_DOI_TAC.md` bản 1.3-draft.

Quy ước đường dẫn trong tài liệu này:
- `AS/` = `platform_VP/agentscope/src/agentscope/`
- `CORE/` = `platform_VP/core/src/awp/`

Nhãn: **CÓ SẴN** (dùng nguyên), **CÓ THỂ GHÉP** (dùng được qua điểm mở rộng, cần mã của ta), **PHẢI TỰ LÀM** (AgentScope không có). Chỗ nào không chắc ghi **chưa xác minh**. Mọi nhận định về hành vi đều dựa trên đọc mã, chưa có test chạy thật.

Hiện trạng lõi cần nhớ khi đọc (từ `CORE/app.py`, `CORE/intake/agentscope_client.py`):
- Lõi gọi AgentScope qua REST trong tiến trình (ASGITransport), dùng bus `InMemoryMessageBus` mặc định (`CORE/app.py:58`), `enable_scheduler=False` (`CORE/app.py:70`).
- Mỗi phiên tạo xong bị đặt `permission_mode = dont_ask` (`CORE/intake/agentscope_client.py:96-100`).
- Lõi đã có middleware bắt `ReplyEndEvent` trong `on_reply` (`CORE/middleware/room.py:275-287`, `LeaderWatchdog`) và cổng tool + `on_check_permission` (`CORE/middleware/room.py:161-228`, `ToolGateMiddleware`).

---

## 1. MCP của đối tác

**Kết luận.**
- Đăng ký và gắn MCP: **CÓ SẴN** nhưng ở mức workspace, khóa theo `(agent_id, session_id)`; không có khái niệm tenant hay route. Người dùng sở hữu bản ghi MCP là user của AgentScope (lõi dùng `awp:{tenant}`), tên MCP duy nhất theo user.
- Xác thực: chỉ có header tĩnh. Không có OAuth. Transport: stdio, streamable HTTP, SSE.
- Cấu hình MCP riêng theo tenant/route và cho cả worker do `AgentCreate` tạo: **CÓ THỂ GHÉP** qua `extra_agent_tools` (factory chạy cho mọi agent, kể cả worker). Nếu dựa vào `/workspace/mcp` thì worker không thừa hưởng MCP của leader.
- `is_mcp`/`mcp_name` không ảnh hưởng permission; permission của tool MCP do chính `MCPTool.check_permissions` và engine quyết định. Với lõi đang chạy `dont_ask`, tool MCP không đánh dấu read-only sẽ bị DENY nếu ta không chen vào.

**Bằng chứng.**

Đăng ký và mức gắn:
- Thư viện MCP mức user: `GET/PATCH/DELETE /mcp` (`AS/app/_router/_mcp.py:22-147`); cài từ hub tạo `MCPRecord` (`AS/app/_router/_hub.py:134-203`). Tên duy nhất theo user (`AS/app/storage/_sql/_storage.py:838-851`; `AS/app/storage/_model/_mcp.py:36-47`).
- Gắn vào một phiên: `POST /workspace/mcp?agent_id&session_id` (body là `MCPClient`) và `POST /workspace/mcp/from-library` (`AS/app/_router/_workspace.py:99-192`).
- Khai báo theo `(agent_id, session_id)`, phiên chưa từng sửa thì lấy `default_mcps` của workspace (`AS/workspace/_base.py:584-601`). Dựng client lười khi `list_mcps` (`AS/workspace/_base.py:603-657`).
- `default_mcps` đặt ở `LocalWorkspaceManager(default_mcps=...)` (`AS/app/workspace_manager/_local_workspace_manager.py:29,50`), áp toàn cục.
- Toolkit của mỗi lượt lấy MCP từ workspace (`AS/app/_service/_toolkit.py:273-276`). Tool từ `extra_agent_tools` vào nhóm `basic` (`AS/app/_service/_toolkit.py:252-257`).

Transport và xác thực:
- `StdioMCPConfig`, `HttpMCPConfig` (chỉ `url`, `headers`, `timeout=30`) ở `AS/mcp/_config.py:9-64`. Stdio bắt buộc stateful (`AS/mcp/_mcp_client.py:155-159`).
- HTTP là SSE nếu path kết thúc `/sse` hoặc `/messages/`, ngược lại streamable HTTP (`AS/mcp/_mcp_client.py:222-229`). Stateful hoặc stateless chọn bằng `is_stateful`.
- `set_runtime_headers` thay header cho các request kế tiếp, chỉ cho streamable HTTP, không lưu xuống `model_dump` (`AS/mcp/_mcp_client.py:262-317`). Vì workspace dựng lại client bằng `model_validate(model_dump)` (`AS/workspace/_base.py:640-642`) nên header runtime chỉ sống khi ta tự giữ instance (đường `extra_agent_tools`).
- Không OAuth: `auth: Literal["none","inputs"]`, "reserved ... oauth flow can be added later" (`AS/app/hub/_mcp/_card.py:140-150`).

Tên tool và permission:
- Tên model thấy: `mcp__{mcp_name}__{tool}`; ký tự ngoài `[a-zA-Z0-9_-]` trong tên tool đổi thành `x` (`AS/tool/_adapters.py:239-247`); `mcp_name` phải khớp `^[a-zA-Z0-9_-]+$` (`AS/mcp/_mcp_client.py:146-153`).
- `is_mcp=True` chỉ dùng để cấm tiêm `_agent_state` (`AS/tool/_toolkit.py:305-309`, `AS/tool/_adapters.py:202-204`). Không có đoạn nào trong `AS/permission/` đọc `is_mcp` hay `mcp_name`.
- `MCPTool.check_permissions`: `readOnlyHint` true thì ALLOW, còn lại ASK (`AS/tool/_adapters.py:270-273,293-314`). Read-only còn qua fast path của engine ở mọi mode (`AS/permission/_engine.py:659-692`).
- Rule khớp theo `tool.name`; `rule_content=None` nghĩa là cả tool (`AS/permission/_engine.py:49-75,721-773`; `AS/tool/_base.py:322-347`).
- Mode `dont_ask` đổi mọi ASK thành DENY (`AS/permission/_engine.py:491-592`); `bypass` thì ALLOW phần còn lại (`AS/permission/_engine.py:395-489`). Lõi: `ToolGateMiddleware` chỉ ALLOW sẵn nhóm `OWN_TOOLS`, phần còn lại đi tiếp vào engine (`CORE/middleware/room.py:164,214-228`). Mẫu lọc tool theo `fnmatch` nên pattern `mcp__<tên>__*` dùng được cho profile.
- `MCPTool.is_concurrency_safe = False` nên gọi tuần tự (`AS/tool/_adapters.py:267`).

Worker do AgentCreate:
- Worker dùng chung `workspace_id` của leader (`AS/app/_tool/_agent_create.py:447`, ghi chú "a worker inherits the leader's workspace" ở dòng 205) nhưng là phiên và agent mới. MCP khai báo theo `(agent_id, session_id)` nên worker chỉ nhận `default_mcps`, không nhận MCP leader gắn qua `/workspace/mcp`.
- `extra_agent_tools(user_id, agent_id, session_id)` chạy cho mọi lần dựng agent (`AS/app/_service/_chat.py:1075-1089` gọi `get_toolkit`; factory ở `AS/app/_service/_toolkit.py:252-257`), nên là chỗ đúng để gắn MCP theo route từ DB của ta (lõi đã dùng `tool_factory(rt)` ở `CORE/app.py:74`, `CORE/middleware/__init__.py:68`).

Lỗi và timeout:
- `McpError` thành `ToolChunk` ERROR "Error occurred when calling MCP tool: ..." (`AS/tool/_toolkit.py:343-353`); exception khác thành ERROR với `str(e)` (`AS/tool/_toolkit.py:355-370`); hủy thành INTERRUPTED (`AS/tool/_toolkit.py:374-385`). Kết quả `isError` của server cũng thành ERROR (`AS/tool/_adapters.py:350-355`).
- `execution_timeout` mặc định `None` (`AS/mcp/_mcp_client.py:122`; `AS/tool/_adapters.py:280-283`); `HttpMCPConfig.timeout=30` (`AS/mcp/_config.py:60-64`). Việc 30 giây này có giới hạn thời gian của một lần `call_tool` hay không: **chưa xác minh** (phụ thuộc SDK `mcp`).
- Cùng tool cùng tham số lỗi liên tiếp `tool_retries_limit` (3) lần thì chèn lời nhắc "đừng thử lại y nguyên" (`AS/agent/_agent.py:1306-1363`; `AS/agent/_config.py:260-272`). Không có retry hay khóa idempotency ở tầng framework.

**Rủi ro.**
1. **`list_tools` qua mạng ở mỗi bước.** `Toolkit._get_available_tools` gọi `client.list_tools()` mỗi lần (`AS/tool/_toolkit.py:522-526`), và `list_raw_tools` luôn gọi server (`AS/mcp/_mcp_client.py:424-467`). Nó chạy ở mỗi lần lấy schema (`AS/agent/_agent.py:3270`), mỗi `get_tool` (`AS/agent/_agent.py:2096-2113`, `AS/tool/_toolkit.py:602-618`), mỗi `check_tool_available` (`AS/tool/_toolkit.py:556-600`) và `call_tool`. Với client stateless mỗi lần là mở kết nối mới + initialize (`AS/mcp/_mcp_client.py:439-449`). Với ngân sách 25 giây của POST, đây là độ trễ và tải lên MCP của đối tác. Đường `extra_agent_tools` (tạo `MCPTool` một lần, cache danh sách) tránh được.
2. **MCP lỗi lúc liệt kê thì tool biến mất im lặng**: chỉ `logger.warning` rồi bỏ qua (`AS/tool/_toolkit.py:527-535`); model nhận "ToolNotFound" thay vì lỗi rõ.
3. **Stateful MCP chết không tự nối lại**: workspace chỉ dựng lại khi tên chưa có trong `live` (`AS/workspace/_base.py:634-635`). Dùng stateless cho MCP HTTP của đối tác.
4. **`structuredContent` bị bỏ**: bộ chuyển chỉ đọc `result.content` (`AS/tool/_adapters.py:350-420`), không có đoạn nào xử lý `structuredContent`. Nếu MCP trả `operation_id` chỉ trong structured thì platform không thấy; bắt MCP đưa `operation_id`/`client_reference` vào text content, hoặc bọc `MCPTool` để bóc.
5. **Secret nằm plaintext**: header MCP nằm trong `MCPRecord.client.mcp_config` ("The secret is already ... in plaintext", `AS/app/storage/_model/_mcp.py:65-72`) và trong file `.mcp` của workspace (`AS/workspace/_base.py:895-919`). Đường `extra_agent_tools` giữ secret trong DB/secret store của ta, không đi qua đó.
6. **Tên MCP duy nhất theo user**: hai route trong cùng tenant dùng chung user `awp:{tenant}` nên phải đặt tên khác (ví dụ `rt_<route>`), tên này lộ vào tên tool model thấy. Giới hạn độ dài tên tool của nhà cung cấp model: **chưa xác minh** (mã không kiểm).
7. **Đang chạy `dont_ask`** nên mọi tool ghi (đặt thợ, booking) bị DENY mặc định; cần `on_check_permission` của ta trả ALLOW/ASK có chủ đích (xem mục 3). Tool tra cứu cần MCP server gắn `readOnlyHint=true`.

---

## 2. Phiên chạy agent và "một lượt"

**Kết luận.**
- Lượt kết thúc phát `ReplyEndEvent` (COMPLETED, EXCEED_MAX_ITERS, INTERRUPTED, ERROR). **Ngoại lệ quan trọng:** khi agent đỗ chờ xác nhận (HITL) thì không có `ReplyEndEvent`, chỉ có `RequireUserConfirmEvent`/`RequireExternalExecutionEvent`.
- `POST /chat` chỉ khởi động và trả `{"status":"started"}`, không trả mã lượt và không chờ. Phải **tự làm** cơ chế "chờ tối đa 25 giây": **CÓ THỂ GHÉP** bằng `on_reply` middleware (đã có mẫu ở lõi) + một bảng lượt + chờ với timeout.
- Chạy đồng thời nhiều session: **CÓ SẴN** (mỗi lượt là một asyncio task, khóa phân tán theo session). Ngắt: **CÓ SẴN** `POST /sessions/{id}/interrupt`.

**Bằng chứng.**

Sự kiện kết thúc lượt:
- `ReplyEndEvent` có `finished_reason`, `error` (`AS/event/_event.py:111-124`). Phát khi `_next_action` trả `Exit` có `exit_events` (`AS/agent/_agent.py:3500-3750`; trường hợp COMPLETED ở dòng 3685-3700).
- Đỗ chờ xác nhận/thực thi ngoài: `Exit(exit_events=None, ...)` và `_reply_impl` chỉ `yield exit_msg; return` (`AS/agent/_agent.py:3534-3545`, `AS/agent/_agent.py:1149-1156`) nên không có `ReplyEndEvent`.
- Lỗi giữa chừng: `ChatService` tự tạo `ReplyEndEvent(ERROR)` (`AS/app/_service/_chat.py:434-486`); lỗi trước khi bắt đầu thì phát cặp start/end ERROR (`AS/app/_service/_chat.py:574-650`).

Bắt từ ngoài app:
- Middleware `on_reply` thấy mọi item của lượt, kể cả `ReplyEndEvent` (và cả `Msg` cuối khi đỗ chờ). Lõi đã làm đúng việc này: `CORE/middleware/room.py:275-287`. Middleware nhận `input_kwargs["inputs"]` (là `Msg` đầu vào hoặc sự kiện resume) (`AS/middleware/_base.py:68-98`), nên gắn được mã yêu cầu của ta vào `Msg.id` (do ta đặt, `AS/message/_base.py:84`).
- Bus: mọi sự kiện lượt được `publish_session_event` (log + pub/sub) (`AS/app/_bus_ops.py:40-66`; `AS/app/_service/_chat.py:1265-1272`).
- SSE `/sessions/{id}/stream` (`AS/app/_router/_session.py:776-927`): phát lại toàn bộ log hiện có (tối đa 1000, `AS/app/message_bus/_keys.py:126`) rồi live; frame chỉ `data: ...`, không có `id:` nên không có Last-Event-ID (`AS/app/_router/_session.py:826-830,915`); heartbeat 30 giây (`AS/app/_router/_session.py:717`).
- Thăm dò trạng thái: `GET /sessions/{id}/status` trả `running` / `idle` / `awaiting_permission` / `awaiting_external_result` (`AS/app/_service/_session.py:61-209`); `running` là khóa phiên đang giữ (`AS/app/_service/_session.py:196-199`), phần còn lại suy ra từ đuôi `AgentState.context` đã lưu.

Chờ có thời hạn từ handler khác (đề xuất ghép, chưa chạy):
- Trong `on_reply` của ta ghi vào bảng `turns` (khóa theo `Msg.id`/`request_id`): trạng thái `completed|parked|error|interrupted`, `reply_id`, văn bản trả lời; sau đó `bus.publish("awp:turn:<id>", ...)` làm tín hiệu đánh thức (bus có Mode D generic `publish/subscribe` với khóa tùy ý, `AS/app/message_bus/_base.py` phần Mode D).
- Handler POST: ghi `request` trước, gọi `/chat`, rồi chờ `turns` (DB là nguồn sự thật, pub/sub chỉ để dậy sớm) tối đa 25 giây; hết hạn thì trả 202.
- Mẫu thăm dò khóa có hạn đã có trong mã: `SessionService.cancel_session_run` poll `is_locked` đến deadline (`AS/app/_service/_session.py:255-320`).

Chạy đồng thời:
- Mỗi lượt là một asyncio task trong `ChatRunRegistry`, tối đa một task mỗi session trong tiến trình (`AS/app/_manager/_chat_run_registry.py:36-92`); toàn cụm một lượt mỗi session nhờ khóa `acquire_lock(session_lock)` (`AS/app/_service/_chat.py:797-800`), TTL 600 giây có heartbeat (`AS/app/message_bus/_keys.py:140`; `AS/app/message_bus/_redis_message_bus.py:629-701`).
- `POST /chat` với tin mới khi cùng tiến trình đang chạy lượt đó trả 409 (`AS/app/_router/_chat.py:142-156`); nếu lượt đang chạy ở tiến trình khác thì lượt mới chờ khóa trong `ChatService.run` (blocking) chứ không báo 409. Hành vi này suy từ mã, **chưa xác minh bằng chạy**.
- Resume (xác nhận) và wake đi qua hàng đợi `wakeups` + `WakeupDispatcher`, đợi khóa nhả rồi spawn (`AS/app/_manager/_wakeup_dispatcher.py:211-353`; backoff 0,1 giây dòng 62).
- Nhiều tool call trong một lượt: tool không "concurrency safe" (mọi `MCPTool`) chạy tuần tự (`AS/agent/_agent.py:2096-2135`).

Ngắt phiên:
- `POST /sessions/{id}/interrupt?agent_id=` trả 202 (`AS/app/_router/_session.py:411-451`) gọi `ChatService.interrupt` (`AS/app/_service/_chat.py:663-720`). Đang chạy: phát lên kênh interrupt, `CancelDispatcher` hủy task cục bộ (`AS/app/_manager/_cancel_dispatcher.py:204-246`), agent dọn: đóng tool call chưa xong bằng kết quả INTERRUPTED, phát `ReplyEndEvent(INTERRUPTED)` + tin dự phòng (`AS/agent/_agent.py:970-1033,1271-1305`). Đang đỗ: xếp hàng `UserInterruptEvent` (`AS/app/_service/_chat.py:713-720`; `AS/agent/_agent.py:1084-1094`). Đang rảnh: không làm gì.
- Hủy cả task nền của phiên (khi xóa phiên): `SessionService.cancel_session_run` (`AS/app/_service/_session.py:255-320`).

**Rủi ro.**
1. **Không có ReplyEnd khi đỗ chờ xác nhận**: chỉ chờ `ReplyEndEvent` sẽ treo POST đến hết hạn ở mọi workflow có approval. Phải coi `RequireUserConfirmEvent` hoặc bản ghi `parked` trong `on_reply` là điểm kết thúc lượt (khi đó trả `awaiting_approval`).
2. **Reply mới khi phiên đang đỗ bị lỗi**: `_check_incoming_event` ném `ValueError` nếu còn tool call ASKING mà không có sự kiện (`AS/agent/_agent.py:1867-1890`); `ChatService` đã lưu tin người dùng vào storage trước khi gọi agent (`AS/app/_service/_chat.py:1244-1250`) nên tin vào DB mà không vào ngữ cảnh. API `workflow_reply` phải kiểm trạng thái và buộc hủy/từ chối approval trước (hoặc trả `409`).
3. **Ngắt giữa lúc gọi MCP có tác dụng phụ**: task bị hủy phía client, bên đối tác có thể đã nhận lệnh; kết quả thành INTERRUPTED, không có cơ chế hủy hay hỏi lại trạng thái. Hạn chế: tool ghi phải trả `client_reference` và có tool tra trạng thái theo tham chiếu.
4. **Khóa phiên sau crash**: nếu tiến trình chết, khóa còn tới khoảng 600 giây (TTL, heartbeat mỗi 300 giây) nên `status` còn `running` và lượt mới phải chờ (`AS/app/_service/_session.py:173-178`).
5. **Tin nhắn người dùng chen vào lúc leader còn chạy** (cùng tiến trình) bị 409: lớp POST của ta phải xếp hàng hoặc báo 202, không đẩy thẳng vào `/chat`.
6. **Exception trong `ChatService.run` bị nuốt và chỉ ghi log** (`AS/app/_service/_chat.py:267-340`, nuốt ở khối `except` quanh dòng 323-340); người chờ phải dựa vào `ReplyEndEvent(ERROR)` tổng hợp hoặc bảng `turns`, đừng dựa vào ngoại lệ.

---

## 3. HITL và approval

**Kết luận.**
- Cơ chế đỗ + resume **CÓ SẴN** và bền (trạng thái `ASKING` nằm trong `AgentState.context`, lưu cuối mỗi lượt). Dùng được làm "khung" cho approval.
- Nhưng AgentScope không có `approval_id`, hạn dùng, audience, `expected_revision`, `quote_ref`, `arguments_hash`. Chúng **PHẢI TỰ LÀM** (bảng approvals + API). `arguments` có sẵn để băm: `ToolCallBlock.input` là chuỗi JSON.
- Nên **GHÉP**: tự phát ASK từ `on_check_permission` của ta (có điều kiện theo tool/route/policy), ghi bản ghi approval ở đó, và tự dựng `UserConfirmResultEvent` từ bản ghi đã lưu khi người duyệt quyết định.

**Bằng chứng.**
- Luồng: quyết định ASK → `ToolCallState.ASKING` → `RequireUserConfirmEvent(tool_calls=[call])` (`AS/agent/_agent.py:2531-2579`); `ToolCallBlock` có `id`, `name`, `input` (chuỗi JSON), `state`, `suggested_rules` (`AS/message/_block.py:138-178`).
- Resume: `POST /chat` với `UserConfirmResultEvent` được xếp hàng `resume` và định tuyến về đúng worker nếu là HITL của worker (`AS/app/_router/_chat.py:113-136`); dispatcher chờ khóa nhả rồi chạy (`AS/app/_manager/_wakeup_dispatcher.py:211-353`). Từ Python có thể gọi thẳng `enqueue_run_trigger(bus, user_id, session_id, agent_id, kind="resume", inputs=...)` (`AS/app/_bus_ops.py:72-136`).
- Agent áp quyết định: xác nhận thì state `ALLOWED` và **ghi đè `tool_call.name`/`tool_call.input` bằng giá trị trong sự kiện** (`AS/agent/_agent.py:1954-1990`); từ chối thì tool result `DENIED` (`AS/agent/_agent.py:1990-2000`). `ConfirmResult.rules` có thể thêm rule cho phiên (`AS/event/_event.py:468-479`).
- `on_check_permission`: chạy sau khi tool đã resolve và input đã validate; có thể trả ASK/ALLOW/DENY mà không gọi `next_handler`; nhận bản sao nên không đổi được lời gọi thật (`AS/agent/_agent.py:2340-2410`; `AS/middleware/_base.py:170-210`). Quyết định của middleware được dùng thẳng, không qua engine, nên **ASK từ middleware vẫn đỗ ngay cả khi mode là `dont_ask`** (conversion chỉ nằm trong `_check_dont_ask`, `AS/permission/_engine.py:491-592`; xử lý ASK ở `AS/agent/_agent.py:2531-2579`). Đây là suy luận từ mã, **chưa xác minh bằng chạy**.
- Call đã `ALLOWED` vẫn đi qua chuỗi middleware khi resume, chỉ bỏ qua engine (`AS/agent/_agent.py:2340-2345,2424-2429`): middleware của ta phải nhận ra `tool_call.state == ALLOWED` và không hỏi lại.
- Trạng thái lưu bền: `AgentState` gồm `summary`, `context` (kèm state từng tool call), `reply_context` (`reply_id`, `cur_iter`, `structured_schema`), `permission_context` (mode, rules), `tool_context`, `tasks_context`, `middle_context` (dict cho middleware, `AS/state/_state.py:209-296`). Ghi bằng `update_session_state` cuối mỗi lượt, trong phần `_persist` được shield khỏi hủy và hoàn tất trước khi nhả khóa (`AS/app/_service/_chat.py:1456-1480`; `AS/app/storage/_sql/_storage.py:1283-1300`). Phiên đang đỗ suy ra `awaiting_permission` từ ngữ cảnh đã lưu (`AS/app/_service/_session.py:211-253`).
- Hủy approval treo: `UserInterruptEvent` đóng mọi tool call đang chờ bằng kết quả INTERRUPTED (`AS/event/_event.py:495-518`; `AS/agent/_agent.py:1084-1094`). Từ chối rồi agent có tiếp tục lập luận hay không do `stop_on_reject` (mặc định `False`, `AS/agent/_config.py:387-393`).

**Rủi ro.**
1. **Đổi tham số lúc resume**: vì sự kiện xác nhận ghi đè `input` (`AS/agent/_agent.py:1976-1978`), nếu để client gửi nguyên sự kiện thì `arguments_hash` vô nghĩa. Server phải: đọc `ToolCallBlock` đã lưu (từ `AgentState` hoặc từ bản ghi approval ghi trong middleware), so `sha256` của `input` chuẩn hóa với hash đã trình bày, so hash client gửi, rồi tự dựng `UserConfirmResultEvent` từ bản đã lưu.
2. **Không có hạn dùng / audience / revision**: toàn bộ ràng buộc (cư dân đúng, ticket đúng, `expected_revision`, `quote_ref`, hết hạn, idempotency) là của ta. Đỗ vô hạn nếu không ai duyệt; cần sweeper gửi `UserInterruptEvent` hoặc từ chối.
3. **Trạng thái chỉ lưu cuối lượt**: crash trước `_persist` thì mất `ASKING` chưa lưu (và cả sự kiện, xem mục 5). Bản ghi approval ta ghi trong middleware có thể mồ côi; khóa theo `(session_id, tool_call.id)` và đối soát khi khởi động.
4. **Id tool call do model sinh**: dùng làm khóa phụ chấp nhận được vì nằm trong state bền, nhưng đừng đưa ra ngoài làm `approval_id`.
5. **Worker trong team**: HITL của worker hiện lên phiên leader qua `SubagentHitlProjector` (hash bền trong bus) và `POST /chat` tự định tuyến (`AS/app/_router/_chat.py:113-136`; `AS/app/_service/_projectors/_subagent_hitl.py`). Nếu gọi `enqueue_run_trigger` trực tiếp phải dùng đúng session/agent của worker. Phần tiêm projector mở rộng không với tới được từ `create_app` (xem mục 4).
6. **Quy tắc `allow` mà người duyệt thêm** (`ConfirmResult.rules`) sẽ tồn tại trong `permission_context` của phiên và bỏ qua hỏi lần sau: với approval nghiệp vụ không bao giờ truyền `rules`.

---

## 4. Event và SSE: có tái dùng làm nguồn public event được không

**Kết luận.** **PHẢI TỰ LÀM** bảng event công khai (có `sequence`, `event_id`, cursor, retention, lọc audience). Log phiên của AgentScope không đáp ứng: không bền, không có Last-Event-ID, không có cursor hết hạn, chứa dữ liệu nội bộ. Bus pub/sub dùng được làm tín hiệu đánh thức SSE (đúng ý hợp đồng: "Redis/pub-sub chỉ báo có dữ liệu mới; database là nguồn replay").

**Bằng chứng.**
- Log phiên là bộ đệm phát lại của một lượt chạy: ghi bằng `log_append(..., max_len=1000)` (`AS/app/_bus_ops.py:40-66`) và **bị xóa hết khi lượt kết thúc** (`log_trim(events_key)` trong `_persist`, `AS/app/_service/_chat.py:1470`).
- Nội dung là mọi `AgentEvent` thô (thinking, tool call delta, tool result, hint, usage) (`AS/event/_event.py:25-70`, danh sách lớp), chứa tham số tool, nội dung hệ thống; hợp đồng cấm gửi prompt và raw tool trace (hợp đồng mục 9.7).
- SSE của AgentScope: xác thực theo `X-User-ID`, kiểm tra chủ phiên (`AS/app/_router/_session.py:807-822`); không lọc audience; đọc log rồi mới subscribe nên có khe hở giữa hai bước (`AS/app/_router/_session.py:826-830` rồi `890-905`): sự kiện phát giữa hai bước có thể mất; payload bị bỏ `_entry_id` nên client không có cursor (`AS/app/_router/_session.py:892-894`).
- InMemory: log, hàng đợi, khóa đều trong tiến trình, "no persistence" (`AS/app/message_bus/_in_memory_message_bus.py:3-14`); id dạng `"<seq>-0"` không so sánh theo chữ được (`AS/app/message_bus/_in_memory_message_bus.py:49-55`); `log_append` bỏ qua `ttl_secs` (dòng 219-220).
- Redis: log là Redis Stream, đọc bằng `XRANGE` với biên loại trừ `(id` (cần Redis 6.2+) (`AS/app/message_bus/_redis_message_bus.py:197-219,350-384`), cắt xấp xỉ `MAXLEN ~` (dòng 339), xóa khi `log_trim`. Bền đến đâu phụ thuộc cấu hình persistence của máy chủ Redis (AOF/RDB): **ngoài mã, chưa xác minh**. Pub/sub là best-effort, không giữ lịch sử (`AS/app/message_bus/_base.py` phần Mode D).
- Lịch sử bền thật của AgentScope là bảng `messages` (mỗi lượt trả lời một dòng `Msg`, `upsert_message`/`list_messages` có phân trang theo `before`) (`AS/app/storage/_sql/_storage.py:1675-1790`; `GET /sessions/{id}/messages`, `AS/app/_router/_session.py:574-654`). Nó chứa cả khối thinking/tool call (`AS/message/_base.py:243-330`), không có `sequence` theo hội thoại, không lọc audience.
- Điểm mở rộng sự kiện: `EventProjector` có trong `ChatService(extra_projectors=...)` (`AS/app/_service/_chat.py:163,262-264`) nhưng `lifespan` không truyền và `create_app` không có tham số tương ứng (`AS/app/_lifespan.py:165-181`; `AS/app/_app.py` danh sách tham số): không với tới được từ ngoài nếu không sửa mã hoặc tự dựng lifespan. Vì vậy dùng `on_reply`/`on_acting` middleware để phát sinh sự kiện công khai (mẫu: `StateChangeMiddleware` đẩy `CustomEvent` lên bus, `AS/app/middleware/_state_change_middleware.py:117-196`).

Cách ghép đề xuất:
1. Public event = bản ghi ta ghi ở bảng riêng trong cùng giao dịch với thay đổi workflow; `sequence` cấp theo hội thoại; `event_id` ổn định.
2. Nguồn phát sinh: `on_reply`/`on_acting`/`on_check_permission` middleware của lõi và các API đồng bộ (close, approval, provider event).
3. SSE của ta: đọc DB theo `Last-Event-ID`/`after_cursor`, `bus.publish` làm tín hiệu dậy; heartbeat 15 giây theo hợp đồng.

**Rủi ro.**
1. Dùng log phiên làm replay sẽ mất sự kiện sau mỗi lượt và lộ nội bộ; không dùng.
2. Với bus InMemory, tín hiệu dậy chỉ tới subscriber cùng tiến trình; nhiều tiến trình bắt buộc Redis (hoặc polling DB định kỳ làm đường dự phòng, nên làm luôn).
3. Retention (≥ 90 ngày sau close, hợp đồng mục 12) và lỗi 410 cursor hết hạn là việc của bảng ta; AgentScope không có.

---

## 5. Lưu trữ và triển khai nhiều tiến trình

**Kết luận.**
- Cần: bus Redis (`RedisMessageBus`) + storage SQL (Postgres). Mã có nhánh Postgres (upsert theo dialect), nhưng test của AgentScope dùng SQLite và README lõi ghi Postgres "chưa thử"; coi Postgres là **chưa xác minh**.
- Dispatcher wakeup an toàn đa tiến trình **nếu và chỉ nếu** dùng Redis bus (drain nguyên tử bằng Lua + khóa phiên phân tán). Scheduler APScheduler **không** an toàn đa tiến trình theo thiết kế: chỉ bật ở đúng một tiến trình.
- Restart mất nhiều thứ (bảng dưới). Phải có lớp phục hồi của ta.

**Bằng chứng.**
- Tham số `create_app`: `storage`, `message_bus`, `workspace_manager`, `enable_scheduler`, `enable_channel_worker`, `enable_index_worker`, `download_secret` (`AS/app/_app.py:73-105` chữ ký và docstring; `download_secret` phải đặt cố định sau load balancer).
- `RedisMessageBus(host, port, db, password, connection_pool, **kwargs)`; cần gói `redis` (`AS/app/message_bus/_redis_message_bus.py:100-160`; extra `storage-redis` trong `platform_VP/agentscope/pyproject.toml`). Hàng đợi là Redis Stream, drain `XRANGE`+`XDEL` trong một Lua (`AS/app/message_bus/_redis_message_bus.py:21-29,257-291`) nên mỗi mục tới đúng một người nhận, nhưng giao theo kiểu **tối đa một lần** (người nhận chết sau khi drain thì mất mục; `AS/app/message_bus/_base.py` mô tả `queue_drain`).
- Khóa phân tán: `SET NX EX` + heartbeat gia hạn mỗi `ttl/2`, nhả bằng so token (`AS/app/message_bus/_redis_message_bus.py:629-701`).
- `AsyncSQLAlchemyStorage(url, create_tables=True, auto_migrate=False, engine_kwargs=...)`: URL ví dụ `postgresql+asyncpg://...`; `create_all` lúc khởi động; `auto_migrate` "không khuyến nghị cho nhiều replica" vì các bản sao đua migration, nên chạy `alembic upgrade head` như một bước triển khai riêng (`AS/app/storage/_sql/_storage.py:120-215`; scripts ở `AS/app/storage/_sql/_alembic`). Driver (`asyncpg`) tự cài (`pyproject.toml` ghi rõ). Upsert hỗ trợ postgresql/sqlite/mysql (`AS/app/storage/_sql/_storage.py:306-336`). Bảng dùng cột `JSON` thuần (không JSONB), đọc-sửa-ghi cả payload khi `update_session_state` (`AS/app/storage/_sql/_tables.py:9-24`; `AS/app/storage/_sql/_storage.py:1283-1300`).
- `WakeupDispatcher` mỗi tiến trình một cái, drain khi khởi động + mỗi tín hiệu (`AS/app/_manager/_wakeup_dispatcher.py:113-131,157-209`); tránh va chạm bằng kiểm tra `is_locked` rồi `spawn`, nếu bận thì đặt lại hàng sau 0,1 giây (`AS/app/_manager/_wakeup_dispatcher.py:275-353`); loại trừ thật sự do khóa phiên trong `ChatService.run` (`AS/app/_service/_chat.py:797`).
- Scheduler: "jobstore is in-memory, so every node holding them fires every cron tick ... set False on all but one" (`AS/app/_manager/_scheduler/_scheduler_manager.py:44-50`; `AS/app/_app.py` mô tả `enable_scheduler`); đối soát với DB mỗi 60 giây (dòng 55), `misfire_grace_time=300` (dòng 527). Lõi đã đặt `enable_scheduler=False` (`CORE/app.py:70`) và có vòng quét riêng `expire_stalled`/`deliver_pending` (`CORE/app.py:95-103`).
- Gắn sự kiện ngoài vào agent đang ngủ: `deliver_to_inbox` (đẩy `HintBlock` vào inbox phiên + xếp hàng wake nếu không có run nào đang tiêu thụ) (`AS/app/_bus_ops.py:163-203`); `InboxMiddleware` rút inbox ở đầu mỗi bước suy luận và nhét vào ngữ cảnh (`AS/app/middleware/_inbox_middleware.py:57-135`). Đây chính là đường **CÓ SẴN** cho "Provider event làm agent chạy lại". Phiên đang đỗ HITL thì wake bị bỏ qua, inbox giữ đến khi resume (`AS/app/_service/_chat.py:722-761`).

Những gì mất khi restart (đọc từ mã):

| Thứ | Đang ở đâu | Khi tiến trình dừng êm | Khi crash / kill -9 |
|---|---|---|---|
| Lượt đang chạy | task asyncio + `AgentState` trong bộ nhớ | `ChatRunRegistry.__aexit__` hủy task, agent dọn thành INTERRUPTED và `_persist` được shield (`AS/app/_manager/_chat_run_registry.py:116-134`; `AS/app/_service/_chat.py:1456-1480`) | **Mất toàn bộ thay đổi của lượt** (state và tin trả lời chỉ ghi cuối lượt); khóa phiên còn tới ~600 giây |
| Inbox đã drain nhưng chưa lưu | hàng đợi bus, drain xóa ngay | tương tự dòng trên | **Mất** (drain tối đa một lần) |
| Hàng đợi wakeup/resume | bus | Redis: còn nếu Redis bền; InMemory: mất | Giống vậy |
| Task nền do `ToolOffloadMiddleware` | asyncio task trong `BackgroundTaskManager` | Bị hủy khi thoát (`AS/app/_manager/_background_task_manager.py:454-470`) | Mất; sổ đăng ký bg trong bus còn 24 giờ (`AS/app/message_bus/_keys.py:282`) và agent đã được hứa "sẽ được báo" |
| Kết nối MCP stateful | bộ nhớ workspace | Dựng lại lười | Dựng lại lười |
| Log sự kiện phiên | bus | Redis: còn đến khi `log_trim`; InMemory: mất | Giống vậy |
| Hẹn giờ scheduler | bộ nhớ | Đối soát lại từ DB trong ≤60 giây | Giống vậy |
| Workspace local (`.mcp`, offload ngữ cảnh) | đĩa máy chạy | Còn | Còn nhưng chỉ trên máy đó |

**Rủi ro.**
1. **Mô hình "lưu cuối lượt"** là rủi ro lớn nhất cho yêu cầu "worker restart khi chờ không tạo job mới" (hợp đồng mục 13.9): tool đã gọi (đặt thợ) rồi crash trước khi lưu thì lần chạy lại thấy state cũ và có thể gọi lần hai. Bắt buộc: bảng "operation" của ta ghi `client_reference` **trước** khi gọi tool (hợp đồng mục 7) và tool/MCP idempotent theo `client_reference`; khi resume kiểm tra trước khi cho gọi tiếp.
2. **Tool `ALLOWED` chưa có kết quả bị chạy lại** khi lượt khôi phục: `_next_action` lấy các call `ALLOWED` chưa có `tool_result` để thực thi (`AS/agent/_agent.py:3510-3532`). Thực tế chỉ xảy ra nếu state `ALLOWED` đã được lưu mà tool chưa xong (ví dụ sau xác nhận); không có khóa idempotency ở tầng framework.
3. **Lock TTL 600 giây** làm chậm phục hồi sau crash; cân nhắc đặt thủ công khóa/`unlock` có kiểm soát ở bước khởi động (chưa có API công khai cho việc này cho `acquire_lock`; **chưa xác minh** cách an toàn).
4. **Workspace local không dùng chung giữa các máy**: offload ngữ cảnh/tool result và file `.mcp` nằm trên đĩa của manager (`AS/workspace/_base.py:723-766`; `AS/agent/_agent.py:715-725`). Nhiều máy cần workspace manager dùng chung (Docker/K8s/…) hoặc đĩa chung; **chưa xác minh** từng manager.
5. **`create_tables` + nhiều replica** đua nhau; dùng Alembic trước khi khởi chạy.
6. **Redis nên bật persistence** và nằm ngoài phạm vi mã; nếu bus chứa hàng wake/resume không bền, ta cần đối soát từ DB của ta (workflow ở `waiting_external_event` hoặc có approval treo) khi khởi động.

---

## 6. Ngữ cảnh dài hạn (workflow sống nhiều ngày)

**Kết luận.** Phiên và `AgentState` bền trong DB; một workflow nhiều ngày là một phiên sống lâu, được đánh thức bằng inbox. **CÓ SẴN** phần lưu và nén ngữ cảnh. Nhưng nén là tóm tắt do model viết (mất chi tiết), nên dữ kiện nghiệp vụ (mã job, `client_reference`, thời điểm hẹn, đã duyệt gì) **PHẢI nằm ở kho dữ liệu của ta** và được tiêm lại, không được chỉ nằm trong ngữ cảnh. Lõi đã có hướng này (case file + digest, `CORE/casefile`, `CORE/middleware/room.py:73-111`).

**Bằng chứng.**
- Phiên lưu `AgentState` trong một cột JSON `payload` của bảng session, ghi lại cả khối ở cuối mỗi lượt (`AS/app/storage/_sql/_storage.py:1283-1300`); mọi tin trả lời lưu thêm ở bảng `messages` (không bị xóa khi nén) (`AS/app/storage/_sql/_storage.py:1675-1700`).
- Nén: khi token ≥ `trigger_ratio` (mặc định 0,8) × cửa sổ model thì tóm tắt phần cũ bằng một lần gọi model theo `summary_schema`, giữ `reserve_ratio` (0,1) phần mới nhất (`AS/agent/_config.py:51-77`, `AS/agent/_agent.py:490-560`). Kết quả vào `state.summary`, ngữ cảnh cũ được đẩy ra workspace nếu có (`AS/agent/_agent.py:700-760`). Prompt nén yêu cầu giữ ID/URL/lệnh nguyên văn, đổi mốc thời gian tương đối thành tuyệt đối, và ghi các tool nền còn chờ (`AS/agent/_config.py:82-109`).
- Nén lỗi thì mặc định cắt bỏ phần cũ nhất (`compression_fallback_to_truncation=True`) (`AS/agent/_config.py:156-166`; `AS/agent/_agent.py:640-690`).
- Kết quả tool dài bị cắt ở `tool_result_limit` (50.000 token) và phần cắt đẩy ra file (`AS/agent/_config.py:146-154`; `AS/agent/_agent.py:2641-2690`).
- Tiêm trạng thái chạy (giờ hiện tại, tasks) mỗi khi quá `time_interval` (0,5 giờ) nên agent biết thời gian trôi sau nhiều ngày (`AS/agent/_config.py:195-245`).
- Số vòng suy luận mỗi lượt tối đa `max_iters` (50) và đặt lại mỗi lượt mới (`AS/agent/_config.py:365-370`; `AS/agent/_agent.py:1114-1120`).
- `middle_context` là dict bền để middleware giữ dữ liệu giữa các lượt (`AS/state/_state.py:291-296`).
- Workspace local bị đẩy khỏi bộ nhớ sau 3600 giây rảnh và dựng lại từ đĩa (`AS/app/workspace_manager/_local_workspace_manager.py:50-80`), nên MCP stateful nối lại lười.

**Rủi ro.**
1. **Tóm tắt của tóm tắt** làm mờ dần dữ kiện; một lần nén lỗi là mất phần cũ. Cần: dữ kiện nghiệp vụ ở bảng của ta, tiêm bản tóm tắt cố định mỗi lượt (như `DigestMiddleware`), và kiểm thử nén với workflow dài.
2. **Chi phí cố định mỗi lần đánh thức**: mỗi sự kiện provider là một lượt gọi model trên cả ngữ cảnh hiện có (đã nén). Workflow có nhiều cập nhật tiến độ sẽ tốn token; cân nhắc chỉ đánh thức model khi sự kiện đáng nói, còn lại chỉ cập nhật trạng thái trong DB (hợp đồng cho phép: "một lượt cần thiết").
3. **Kích thước dòng session** tăng theo ngữ cảnh và được ghi nguyên khối mỗi lượt; ghi đồng thời từ nơi khác (ví dụ PATCH phiên) có thể chồng lên nhau (mã tự ghi chú, `AS/app/_router/_session.py:523-528`).
4. **Không có hết hạn phiên** trong AgentScope: nếu cần dọn workflow đã đóng phải tự xóa phiên (`purge_session` xóa offload và khai báo MCP, `AS/workspace/_base.py:723-766`) theo chính sách retention của ta.
5. **Chất lượng nén với model rẻ** và việc "agent quên đã hứa gì" là rủi ro chất lượng, không đo được từ mã; liên quan phản hồi của sếp về bộ nhớ/ngữ cảnh.

---

## 7. Tool trả "operation" bất đồng bộ

**Kết luận.** AgentScope **không có** khái niệm tool khai báo kết quả "pending operation". Cái có sẵn là:
- `ToolOffloadMiddleware`: chuyển **bất kỳ** tool chạy quá 10 giây xuống nền và báo lại bằng inbox. Dựa trên thời gian, trong tiến trình, không bền. **Không nên dùng làm cơ chế operation.**
- Tool ngoài (`is_external_tool`): đỗ lượt (`SUBMITTED`) đến khi có `ExternalExecutionResultEvent`. Bền (nằm trong state) nhưng đỗ cả phiên, chặn tin mới.
- Kết quả: operation pending nên là **kết quả tool bình thường** (tool trả JSON có `operation_id`, `client_reference`, `status=pending`); lượt kết thúc; sự kiện sau đó vào qua `deliver_to_inbox`. Phần ghi nhận operation, đối soát, trạng thái `waiting_external_event` **PHẢI TỰ LÀM** (GHÉP với `deliver_to_inbox`).

**Bằng chứng.**
- `ToolOffloadMiddleware` luôn có trong mọi lượt (`AS/app/_service/_chat.py:968-981`); hết `timeout_secs=10` thì tạo asyncio task nền, trả placeholder "running in background ... You will be notified automatically" (`AS/app/middleware/_tool_offload_middleware.py:374-396`), khi xong đẩy kết quả thành `HintBlock` vào inbox + wake (`AS/app/middleware/_tool_offload_middleware.py:239-350`). Không áp cho tool `is_state_injected` hoặc `is_external_tool` (dòng 156-162). `MCPTool` không thuộc hai nhóm đó nên bị offload.
- `BackgroundTaskManager`: giữ task asyncio cục bộ + sổ đăng ký bus (TTL 24 giờ) để `ToolStop` hủy chéo tiến trình; không lưu kết quả (`AS/app/_manager/_background_task_manager.py:233-330`); hủy hết khi thoát (dòng 454-470).
- Tool ngoài: `is_external_tool` làm agent phát `RequireExternalExecutionEvent` và đỗ (`AS/agent/_agent.py:2605-2620`); kết quả quay lại bằng `ExternalExecutionResultEvent`, có thể kiểm schema qua `metadata_schema`/`check_external_result` (`AS/tool/_base.py:122-129,273-300`; `AS/agent/_agent.py:2001-2033`). `AskUser` là tool ngoài dựng sẵn nhưng không được đưa vào toolkit của app (`AS/tool/_builtin/_ask_user.py:166-211`; không có tham chiếu trong `AS/app/`).
- Đường đánh thức: `deliver_to_inbox` + `InboxMiddleware` (mục 5). `SchedulerManager` cũng dùng đúng đường này (`AS/app/_manager/_scheduler/_scheduler_manager.py:36-50`).
- Mẫu có sẵn trong lõi cho "chờ trả lời bên ngoài": `CaseRequest` + trả lời có cấu trúc đánh thức agent đã gửi, quá `AWP_REQUEST_TIMEOUT_HOURS` (72) thì `needs_human` (`CORE/requests.py`; README lõi dòng 17).

**Rủi ro.**
1. **Offload 10 giây trùng với MCP có tác dụng phụ**: tool đặt thợ chạy quá 10 giây bị chuyển nền; lượt kết thúc với câu "đang chạy nền" (đây sẽ là `result.messages` của POST 200 nếu ta không chặn), kết quả thật đến sau qua inbox. Restart giữa chừng thì task nền mất mà agent đã được hứa sẽ được báo (xem bảng mục 5), bên đối tác có thể đã tạo thợ. Cần: hoặc tắt offload cho tool MCP của ta (không có cờ cấu hình; middleware cố định trong `ChatService`, muốn bỏ phải qua `custom_agent_cls` hoặc sửa mã: **chưa xác minh khả thi**), hoặc bọc MCP trong tool của ta trả ngay `pending` + `client_reference` (khuyến nghị) và chạy gọi thật với deadline/lưu operation trước.
2. **Tool trả `pending` mà agent không biết chờ**: cần chỉ dẫn hồ sơ và tiêm trạng thái operation vào ngữ cảnh mỗi lượt từ bảng của ta; không dựa vào trí nhớ của model.
3. **HintBlock từ provider là dữ liệu không tin cậy** nhưng được nhét vào ngữ cảnh model như một khối hệ thống (`AS/app/middleware/_inbox_middleware.py:99-123`); phải làm sạch, chỉ chuyển trường đã qua schema (hợp đồng mục 10: `data` không chứa chỉ thị cho agent).
4. **Wake chỉ khi phiên không đỗ HITL; sau close ta phải tự chặn** việc đánh thức (hợp đồng: sự kiện đến sau close chỉ audit). Kiểm tra trạng thái workflow trước khi gọi `deliver_to_inbox`.

---

## Phụ lục: những việc vặt rút ra, theo mức ưu tiên

1. Khóa idempotency + ghi operation **trước** khi gọi MCP (mục 5, rủi ro 1; mục 7).
2. Quyết định cách gắn MCP: `extra_agent_tools` có cache (mục 1), không dùng `/workspace/mcp`.
3. Middleware `on_check_permission` phát ASK + bảng approvals + tự dựng `UserConfirmResultEvent` (mục 3).
4. `on_reply` ghi bảng `turns`, xử lý trường hợp đỗ HITL (mục 2).
5. Bảng event công khai riêng + bus chỉ làm tín hiệu (mục 4).
6. Redis bus + Postgres + Alembic tách bước + đối soát khi khởi động (mục 5).
7. Chặn `workflow_reply` khi phiên đang `awaiting_permission` (mục 2, rủi ro 2).

## Bảng tóm tắt

| # | Chủ đề | CÓ SẴN | CÓ THỂ GHÉP | PHẢI TỰ LÀM |
|---|---|---|---|---|
| 1 | MCP đối tác | Đăng ký và gắn MCP mức session/workspace; stdio, streamable HTTP, SSE; header tĩnh; tên `mcp__{mcp}__{tool}`; lỗi MCP thành tool result lỗi | MCP theo tenant/route và cho worker qua `extra_agent_tools` (có cache, giữ secret ở DB ta); ALLOW/ASK qua `on_check_permission` | OAuth; retry/idempotency khi gọi MCP; xử lý `structuredContent`; quản lý secret |
| 2 | Lượt chạy | `ReplyEndEvent`; chạy đồng thời nhiều session (khóa phân tán); interrupt API | Chờ 25 giây qua `on_reply` + bảng `turns` + pub/sub; xử lý lượt đỗ HITL không có ReplyEnd | Mã lượt/yêu cầu gắn với POST; hàng đợi khi phiên bận hoặc đang đỗ; 202/200 và idempotency |
| 3 | HITL / approval | Đỗ + resume bền, trạng thái `ASKING` lưu trong `AgentState`; `UserInterruptEvent` | Phát ASK từ `on_check_permission`; tự dựng sự kiện resume từ bản đã lưu | `approval_id`, hạn dùng, audience, `arguments_hash`, `expected_revision`, `quote_ref`, sweeper hết hạn |
| 4 | Event / SSE | Pub/sub bus làm tín hiệu | Middleware của lõi làm nguồn phát sinh sự kiện | Bảng event công khai (sequence, cursor, retention, 410, lọc audience, Last-Event-ID, SSE theo hợp đồng) |
| 5 | Lưu trữ / triển khai | Redis bus; SQL storage (có nhánh Postgres); dispatcher wake an toàn nhiều tiến trình khi dùng Redis; `deliver_to_inbox` | Scheduler đúng một tiến trình; phục hồi khi khởi động từ DB của ta | Phục hồi sau crash (lưu trạng thái giữa lượt, khóa phiên, inbox mất); Alembic tách bước; kiểm thử Postgres |
| 6 | Ngữ cảnh dài hạn | Phiên + `AgentState` bền; nén có tóm tắt, offload ngữ cảnh; tiêm thời gian | Tiêm lại dữ kiện từ case file/DB mỗi lượt (`DigestMiddleware`) | Nguồn sự thật nghiệp vụ ngoài ngữ cảnh; retention/dọn phiên; đo chất lượng nén |
| 7 | Operation bất đồng bộ | Đường đánh thức inbox (`deliver_to_inbox`); tool ngoài đỗ lượt (không phù hợp chờ nhiều ngày) | Tool bọc MCP trả `pending` ngay + `deliver_to_inbox` khi có sự kiện | Khái niệm operation (bảng, đối soát, `client_reference`, trạng thái); chặn offload 10 giây cho tool có tác dụng phụ; làm sạch dữ liệu provider |

Ghi chú trung thực về mức chắc chắn: toàn bộ kết luận trên đọc từ mã; chưa chạy lần nào. Các điểm đánh dấu **chưa xác minh** nên được kiểm bằng test ngắn trước khi chốt thiết kế: (a) ASK từ middleware có đỗ trong `dont_ask`; (b) `POST /chat` khi phiên đang chạy ở tiến trình khác; (c) `timeout=30` của HTTP MCP có cắt `call_tool`; (d) Postgres end-to-end; (e) tắt `ToolOffloadMiddleware` cho tool cụ thể.
