# Kiểm chứng P0: client MCP đối tác trên SDK `mcp` (spec mục 8)

Ngày 2026-10-10. Test: `platform_VP/core/tests/probes/test_p0_mcp_sdk.py` (33 test). Helper cùng thư mục: `p0_mcp_sdk_server.py` (FastMCP thật, streamable HTTP, uvicorn trong thread), `p0_mcp_sdk_client.py` (**prototype `PartnerMCP`**), `p0_mcp_sdk_tool.py` (`PartnerTool(ToolBase)`, pack và stack thử), `p0_mcp_sdk_llm.py` (model giả có kịch bản). Không sửa `agentscope/src`, `src/awp`, `fake_llm.py`, `support.py`.

Chạy: `cd platform_VP/core && PYTHONPATH=src ../agentscope/.venv/Scripts/python.exe -m pytest -q tests/probes/test_p0_mcp_sdk.py -p no:cacheprovider`. Kết quả: **33 passed, 3 lần liên tiếp** (75 s mỗi lần, phần lớn là chờ server restart/timeout). Thêm `-s` để xem số đo. SDK `mcp` 1.30.0, Python 3.11.9, Windows 11, localhost.

## 1. Câu hỏi

Dựng client MCP đối tác tối thiểu bọc thành tool AgentScope: độ trễ `list_tools`, annotation/schema, `call_tool` với timeout (có cắt không, server còn chạy không), `structuredContent` so với `content`, `isError`, tái dùng kết nối so với phiên mới mỗi lần (và khi server restart), header tĩnh, server chết; rồi chứng minh tool bọc chạy trong lượt agent thật, kết quả thành bằng chứng, hành động không bị gọi lần hai.

## 2. Kết quả theo câu hỏi (tất cả đã chạy, trừ khi ghi khác)

| # | Câu hỏi | Kết quả quan sát |
|---|---|---|
| 1 | Độ trễ | connect + `initialize` 130 đến 190 ms; `list_tools` 8 đến 12 ms (localhost) |
| 2 | Annotation / schema | `annotations` đến đủ (`readOnlyHint`, `destructiveHint`, `idempotentHint`, `title`); tool không khai báo thì `annotations=None` (=> **không** read-only). `inputSchema` là JSON schema dùng thẳng được. `outputSchema` chỉ có với kiểu trả về có kiểu (pydantic, hoặc `str` bọc `{"result":..}`); dict trơn và `CallToolResult` thì `None` |
| 3 | `content` và `structuredContent` | (a) trả `CallToolResult(content=[], structuredContent={...})`: `content` **rỗng**, dữ liệu chỉ nằm ở `structuredContent`; (b) pydantic: cả hai, cùng dữ liệu; (c) dict trơn: chỉ text JSON, `structuredContent=None`; (d) `str`: text, kèm bản sao `structuredContent={"result": text}` (không được hiện hai lần). `merge_text` xử lý cả bốn |
| 4 | `isError` | Exception phía server, thiếu tham số, tool không tồn tại đều về `isError=True` + text ("Error executing tool boom: partner exploded: ledger locked"), **không** ném exception. Lỗi giao thức JSON-RPC mới ném `McpError`. Text lỗi của server lộ nguyên văn tới agent: cần lọc nếu không muốn agent thấy chi tiết nội bộ của đối tác |
| 5 | `read_timeout_seconds` | **Cắt đúng giờ** (0,50 s cho yêu cầu 0,5 s), ném `McpError` code **408** "Timed out while waiting for response". **Server vẫn chạy tiếp tới hết**: dòng ghi sổ của tool chậm có `side_effect=True`, lúc timeout chưa có `t_end`, 1,5 s sau có `t_end`, không có hủy, cả stateless lẫn stateful. Session vẫn dùng tiếp được sau timeout. => timeout là `unknown`, không phải `failed` |
| 6 | Không đặt timeout | `call_tool` chờ bao lâu server muốn (`timeout=` của transport không giới hạn một câu trả lời stream). Xem mục 3.4 cho trường hợp xấu hơn |
| 7 | Phiên mới mỗi lần so với tái dùng | Phiên mới tự dựng httpx client mới: **median 140 ms** mỗi lần. Phiên mới nhưng **dùng chung httpx client (pool)**: **13 đến 14 ms**. Phiên dùng chung: 4 đến 5 ms. Một lần gọi phiên mới = 3 POST (`initialize`, `notifications/initialized`, `tools/call`). Chi phí 140 ms là dựng client httpx (TLS context), không phải giao thức |
| 8 | Server restart, session cache | **Stateless**: session cache sống qua restart (không có trạng thái). **Stateful**: mọi lời gọi sau đó trả `McpError("Session terminated")` (HTTP 404) **vĩnh viễn**, không tự nối lại; yêu cầu không được chạy (server không ghi nhận). `PartnerMCP` (shared) nối lại một lần cho tra cứu (attempts=2, kết quả OK); hành động luôn dùng phiên riêng nên không dính chuyện này |
| 9 | Header tĩnh | `Authorization` và `X-Tenant` đến server ở **mọi** request (`initialize`, `initialized`, `tools/list`, `tools/call`); không đặt thì không có |
| 10 | Server tắt | Từ chối kết nối: `ExceptionGroup[ConnectError]`, **~2,2 s** để thất bại (đặc thù loopback Windows; mạng thật sẽ khác). Map `failed/connect`, `sent=False` |
| 11 | Server bị kill giữa lúc gọi | SDK **không nhận ra** kết nối rơi; chỉ `read_timeout` kết thúc việc chờ. Map `unknown/timeout` (không bao giờ `failed`). Stateful còn mất thêm ~2 s đóng session trên server chết: backstop `asyncio.timeout(timeout + 0.5)` giữ tổng 2,7 đến 3,0 s cho timeout 2,5 s |
| 12 | 401 / 5xx | 401 từ cổng: `failed/auth`, `sent=False` (không có tác dụng phụ). HTTP 500 trên `tools/call`: `unknown/http` (đối tác có thể đã chạy), không thử lại |

## 3. Phát hiện quan trọng (cái spec chưa nói hoặc nói chưa đủ)

### 3.1 `ClientSession.call_tool` không dùng được cho hành động
Mã `mcp/client/session.py:386-478` (và đã chạy): lần đầu mỗi tên tool trong một session, `call_tool` **gửi thêm `tools/list` ẩn ngay sau lần gọi đầu** (ghi nhận trên dây cho hai lần gọi cùng tool: `initialize, initialized, tools/call, tools/list, tools/call`). Quan trọng hơn: **sau khi server đã chạy xong tool**, nó kiểm `structuredContent` với `outputSchema` và **ném `RuntimeError("Invalid structured content ...")`** nếu không khớp. Test `typed_lying`: server chạy 1 lần (tác dụng phụ đã xảy ra), client ném lỗi, kết quả mất. Với hành động đặt thợ, đó là "đã làm mà không biết". `PartnerMCP` gọi `session.send_request(CallToolRequest...)` (`send_call`): cùng lời gọi trên dây, không `tools/list` ẩn, không kiểm sau. Cùng lý do, `MCPTool` của AgentScope (dùng `call_tool`) cũng chịu: mỗi lần gọi qua client stateless = initialize + initialized + list + call.

### 3.2 `streamablehttp_client` đã deprecated
Dùng `streamable_http_client(url, http_client=...)` cùng `create_mcp_http_client(headers, timeout)` (cả hai là API công khai của SDK 1.30). Tự giữ httpx client là chỗ đặt header, timeout và pool. SDK ghi chú: redirect chỉ theo khi cùng origin, ngược lại raise `HTTPStatusError` (theo docstring, **chưa chạy thử**).

### 3.3 `CancelledError` rò ra từ session chết
Session cache mà server chết: transport task group sập và **hủy task đang chờ bằng `CancelledError` dù không ai hủy** (cả khi gọi lúc server đang tắt, cả sau khi server sống lại; session chết vĩnh viễn). Nếu để lọt, AgentScope hiểu là INTERRUPTED. `PartnerMCP` phân biệt bằng `current_task().cancelling()`: hủy của chính task thì ném lại (test `own_cancellation_is_not_swallowed`), hủy lạ thì thành kết quả `unknown/failed`.

### 3.4 Câu "30 giây" của AgentScope (research mục 1, dòng 56 "chưa xác minh") — ĐÃ XÁC MINH, và xấu
`HttpMCPConfig.timeout=30` thành `httpx.Timeout(30)` cho cả connect **lẫn read** (`AS/mcp/_mcp_client.py:240-244`), còn `execution_timeout` (tức `read_timeout_seconds`) mặc định `None`. Tái hiện bằng httpx read timeout 0,7 s với tool chạy 2 s, không đặt `read_timeout_seconds`:
- server trả SSE (mặc định FastMCP): `call_tool` **không bao giờ trả về** (4 s khi test bị `wait_for` cắt; thử tay 25 s vẫn treo), lỗi ReadTimeout bị nuốt;
- server trả JSON (`json_response=True`): sau 0,71 s `CancelledError` rò ra (mục 3.3), session chết, `ReadTimeout` nổ ở lúc đóng.
Kết luận: không dựa vào `MCPClient`/`/workspace/mcp` của AgentScope cho đối tác (xác nhận lựa chọn của spec mục 8); client của ta luôn đặt `read_timeout_seconds` và `httpx.Timeout(read >= timeout + 5)`.

### 3.5 Tác dụng phụ tới EvidenceMiddleware
`EvidenceMiddleware` (`room.py:140-149`) chỉ tạo bằng chứng khi `ToolResponse.state == SUCCESS`. Vì vậy: `ok` và `pending` => `SUCCESS` (pending thành bằng chứng "đã gửi, tham chiếu op-7781"); `failed` và `unknown` => `ERROR` (không thành bằng chứng; dấu vết nằm ở `wf_operations`). Đã chạy: hai bằng chứng `partner_lookup_ticket`, `partner_book_plumber` được trích bởi `CaseFact`, case `finalized` có đáp án chứa `op-7781`.

## 4. Chạy trong lượt agent thật

`PartnerTool(ToolBase)` dựng từ `ToolSpec` trong danh sách cache (không chạm mạng khi dựng); pack kiểu `DomainPack.tools()` async trả `PartnerTool` => đi qua `install_pack` thành `rt.tool_factories` => `tool_factory` => `extra_agent_tools` (đúng đường ở `middleware/__init__.py:68-86`). Quan sát:
- Hai agent (leader, worker "tech") dựng, nhiều bước model, nhưng server chỉ nhận **1** `tools/list` (cache).
- Chỉ worker có `tools_allow=["partner_*"]` mới thấy tool; leader thì không (cổng tool của hồ sơ chạy đúng).
- `client_reference` được **tiêm** và **ẩn khỏi schema** model thấy (schema chỉ còn `slot`); giá trị là hash xác định của (tool, tham số) và server nhận đúng giá trị đó.
- Header `Authorization` tĩnh đến server cho mọi lời gọi của agent.
- Tool hành động có `check_permissions=ASK`: core chạy `dont_ask` nên agent nhận đúng chữ `Permission denied for partner_book_plumber (dont_ask mode - user not available)`, server **0 lời gọi** `book_plumber`. Tool read-only (`readOnlyHint=true`) ALLOW. Tool không có hint bị coi là hành động.

## 5. Lỗi spec / việc phải làm khác đi

Spec `WORKFORCE_V1_DAC_TA_TRIEN_KHAI.md` mục 8 đúng hướng, nhưng cần sửa/bổ sung (tôi không sửa spec):
1. Câu "giữ kết nối/stateless": nên ghi **phiên mới mỗi lần gọi trên httpx client dùng chung (pool), không giữ session**. 13 ms localhost, không có chuyện session chết/đổi server, hành động luôn dưới cùng một đường. Phiên dùng chung chỉ là tối ưu cho tra cứu (mất 2 lần thử khi server stateful restart). Server đối tác nên là stateless; nếu stateful thì phải có đường nối lại.
2. Thêm quy tắc cứng: **không dùng `ClientSession.call_tool`**; dùng `send_request(CallToolRequest)` (mục 3.1). Ghi vào mục 8 và vào research AgentScope (mục 1 lỗi số 1 còn thiếu chuyện `call_tool` ẩn và `RuntimeError` sau thực thi).
3. Bảng map kết quả chốt: `connect/401/403/404-Session terminated` trước khi gửi => `failed` (`sent=False`); `isError` hoặc status `failed|rejected` => `failed`; hết giờ, rơi kết nối giữa chừng, 5xx trên `tools/call`, hành động trả không có `status` đọc được => `unknown` (không thử lại). Chỉ tra cứu read-only mới được thử lại đúng một lần, và chỉ khi session chết (không thử lại khi timeout).
4. A8 (timeout 8 s, tối đa 9 s): `timeout` phải là ngân sách cả lần gọi, không chỉ thời gian chờ trả lời; cần `asyncio.timeout(timeout + ~0.5)` bao ngoài (đóng session trên server chết tốn tới ~2 s). Đã làm trong `PartnerMCP.close_grace`. Prototype mặc định `call_timeout=20` chỉ để test, bản thật phải 8.
5. "kết quả thành bằng chứng": làm đúng cho `ok` và `pending`; `failed`/`unknown` không thành bằng chứng qua `EvidenceMiddleware` (chỉ SUCCESS) => dấu vết phải ở `wf_operations` và agent nhận chữ `FAILED:`/`UNKNOWN:` do tool tự dựng.
6. `readOnlyHint` thiếu nghĩa là KHÔNG read-only (đã chạy). Spec đã đúng, nhưng nhớ rằng MCP FastMCP thường không đặt hint: route phải cấu hình `read_only` cho tool tra cứu, nếu không tool tra cứu bị DENY trong `dont_ask`.
7. Chặn SSRF và redirect: tự giữ httpx client là chỗ duy nhất để áp (chưa kiểm thử ở đây).

## 6. Giới hạn của kiểm chứng

- Chỉ localhost, một tiến trình, không TLS, không mạng thật, không đối tác thật; số ms chỉ có nghĩa tương đối. Loopback Windows làm "server tắt" mất 2,2 s, Linux thường tức thì.
- Server thử là FastMCP của cùng SDK; server tự viết (Node, Java, gateway) có thể trả khác (SSE hay JSON, 404 hay 400 khi hết session, có `outputSchema` sai...).
- Model là kịch bản giả: chỉ chứng minh đường ống, không nói gì về cách model thật chọn tool hay đọc `PENDING`/`UNKNOWN`.
- Không chạy: nhiều lời gọi đồng thời trên một session dùng chung (`is_concurrency_safe=False` nên AgentScope tuần tự hóa), OAuth, SSE transport cũ, server MCP phân trang `list_tools`, `tools/list_changed`, redirect cross-origin, Redis/Postgres.
- Phần `resumption` của transport (tự nối lại SSE) chỉ đọc qua hằng số, không phân tích; lý do chính xác của việc "treo" ở mục 3.4 (SSE) là suy ra từ quan sát (không trả về trong 25 s), chưa lần ra dòng mã.
- Test của `PartnerTool` dùng mode `dont_ask` mặc định của core; cổng approval thật (mục 6.1 spec) là việc của probe khác.
