# Kiểm chứng P0: `ToolOffloadMiddleware` và quyết định A8

Ngày 2026-10-10. Test: `platform_VP/core/tests/probes/test_p0_offload.py`, helper `p0_offload_stack.py` (cùng thư mục). Không sửa `agentscope/src`, `src/awp`, `fake_llm.py`, `support.py`.

## 1. Câu hỏi

Spec A8 (`WORKFORCE_V1_DAC_TA_TRIEN_KHAI.md` mục 3, dòng "A8 giới hạn gọi MCP"): tool bọc MCP có `call_timeout` mặc định 8 s, tối đa 9 s, dưới ngưỡng 10 s của `ToolOffloadMiddleware`, để tool có tác dụng phụ không bị đẩy xuống nền không bền. Cần kiểm bằng chạy thật:

1. Tool `ToolBase` (kiểu wrapper của ta, không phải `MCPTool`) ngủ 3 s có không bị offload, model nhận kết quả thật?
2. Ngủ 12 s: model nhận đúng chữ gì, kết quả thật đến khi nào và bằng đường nào, mất gì khi bị hủy?
3. Có đổi được ngưỡng 10 s hoặc tránh middleware cho từng tool mà không sửa `agentscope/src`?
4. Từ đó xác nhận hay bác A8.

## 2. Cách làm

`agentscope.app.create_app` thật (ChatService, WakeupDispatcher, CancelDispatcher, InboxMiddleware, `ToolOffloadMiddleware` do ChatService tự cài), bus trong bộ nhớ, SQLite, model giả OpenAI-compatible có kịch bản (viết riêng trong helper; chỉ ghi lại mọi request kèm thời điểm). Tool thử `PartnerBook(ToolBase)` có sổ ghi `LEDGER` (start / side_effect_done / cancelled) để so "điều thực sự xảy ra" với "điều model được báo". Không dùng gì từ `awp`. Cấu hình `permission` mặc định, tool trả ALLOW.

Chạy: `cd platform_VP/core && PYTHONPATH=src ../agentscope/.venv/Scripts/python.exe -m pytest -q tests/probes/test_p0_offload.py -W ignore` cho 11 test pass, 105 s. Bỏ các test chậm (8 đến 15 s mỗi cái, đánh dấu `slow`): thêm `-m "not slow"` (còn 3 test, 16 s).

## 3. Kết quả

### (1) 3 s: không offload — XÁC NHẬN
Model nhận đúng `BOOKED ref=BK-3s` làm tool result, sau 3.x s. Không có bg task, không có lượt đánh thức thứ hai, chỉ 2 request tới model.

### (2) 12 s: bị offload — XÁC NHẬN, và chi tiết
- Tại **10.38 s** (10 s tính từ lúc vào `on_acting`, cộng chút chi phí) model nhận làm tool result đúng chuỗi này, không có chữ nào của kết quả thật:
  `<system-reminder>Tool 'partner_book' is running in background (id=<task_id>) for over 10.0s. You will be notified automatically when it finishes, so **DO NOT** poll, query, or wait ... You have exactly two valid options: 1. Continue with other independent tasks ...; or 2. If there is nothing else to do, simply give a text reply without calling any tool, which ends the current reasoning loop ...</system-reminder>`
- Model giả theo lựa chọn 2 và trả text "Done." Lượt kết thúc. Trong hệ thật, đây là câu mà lượt trả ra cho cư dân nếu ta không chặn (đúng điều research mục 7 đã dự đoán).
- Tool vẫn chạy ở nền (`bg_tasks()` có 1 task, tool_name `partner_book`), xong lúc 12.27 s. Ngay sau đó kết quả thật đến dưới dạng **HintBlock trong inbox** + wakeup; session đang rảnh nên WakeupDispatcher chạy lượt mới lúc **12.44 s**. Model thấy một message role user: `<system-notification>Tool 'partner_book' running in background (id=call_xxxx) has completed.\n\nResult:\n\nBOOKED ref=BK-12s</system-notification>`. Lưu ý id trong hint là `tool_call.id`, id trong placeholder là `task_id`: hai id khác nhau cho cùng một việc.
- Lịch sử lưu: tool result của lượt gốc mãi mãi là placeholder; giá trị thật chỉ nằm trong tin hint.
- Khi hint chưa được tiêu thụ mà bị mất (drain tối đa một lần, bus bộ nhớ) thì không có đường nào khác để model biết kết quả.

**Mất gì khi hủy** (4 test):

| Tình huống | Tool | Model biết kết quả? |
|---|---|---|
| Interrupt lượt khi tool còn trong 10 s đầu (chưa offload) | **Không bị hủy**, chạy đến hết, tác dụng phụ xảy ra (6.41 s), không đăng ký bg task nên ToolStop không dừng được | **Không**: không ai đọc queue nữa, không hint, không lượt nào |
| Interrupt lượt sau khi tool đã offload | Tool nền không bị đụng, xong 12.27 s | Có, hint vẫn đến và đánh thức. (Tool thứ hai đang chạy dở trong lượt bị hủy thì rơi vào hàng trên: chạy hết, kết quả mất) |
| `cancel_session_tasks` (cùng đường ToolStop / hủy session) | Bị hủy (`CancelledError` trong tool) | Có hint, nhưng **nội dung là** `The tool call has been interrupted by the user.` chứ không im lặng. Docstring trong mã nói "no result is delivered" là sai với hành vi thật: `Toolkit.call_tool` bắt `CancelledError` và đổi thành kết quả INTERRUPTED |
| Tắt tiến trình (lifespan exit) | Bị hủy | Task nền mất; lịch sử còn lời hứa "you will be notified". Hint "interrupted by the user" vẫn được đẩy vào inbox trước khi bus đóng (thấy trong queue bộ nhớ). Với bus bền (Redis) hint này có thể sống qua restart và đánh thức session bằng một câu sai sự thật: đối tác có thể đã tạo thợ. **Chỉ suy từ mã + quan sát bus bộ nhớ, chưa chạy với Redis.** |

### (3) Tránh hoặc chỉnh middleware mà không sửa `agentscope/src` — tìm được 2 cách
- **Chỉ đọc + chứng minh**: `extra_agent_middlewares` KHÔNG giúp được. Thứ tự thật in ra: `InboxMiddleware, StateChangeMiddleware, ToolOffloadMiddleware, <extra của ta>`. Middleware của ta nằm *trong* offload, nên không giữ được đồng hồ (test `test_extra_agent_middlewares_run_inside_the_offload_not_before_it`). Không có cờ cấu hình nào cho ngưỡng (`timeout_secs` không được `ChatService` truyền).
- **Cách A, `is_state_injected = True`** trên tool wrapper (test `test_state_injected_flag_bypasses_offload`): tool 12 s chạy đồng bộ, model nhận `BOOKED ref=BK-inj` lúc 12.22 s, không bg task. Ưu: không cần mã hạ tầng. Nhược: (i) tool nhận `AgentState` sống qua tham số `_agent_state` (phải nhận và bỏ qua; đã thấy `seen_state == ['AgentState']`); (ii) dựa vào một guard mà chính mã gốc ghi "for now ... should become a hard RuntimeError" (`_tool_offload_middleware.py:148-152`), nên có thể bị siết khi nâng cấp AgentScope; (iii) lạm dụng nghĩa của cờ.
- **Cách B (sạch nhất), `custom_agent_cls`** (test `test_agent_subclass_changes_threshold_and_exempts_a_tool`): lớp con `Agent` bọc middleware đã cài bằng `OffloadPolicy`: tool nào khai `allow_offload = False` thì đi thẳng `next_handler`, còn lại giao cho `ToolOffloadMiddleware` gốc. Chứng minh: ngưỡng đặt 1.5 s thì tool 3 s bị offload với chữ "for over 1.5s"; tool `allow_offload=False` 3 s không bị offload. Chỉ chạm một thuộc tính private (`inner._timeout_secs`) và chỉ khi muốn đổi ngưỡng; bỏ qua theo tool thì không cần chạm gì. `build_app(**create_app_kwargs)` của ta đã chuyển được `custom_agent_cls`.
- Không thử: `is_external_tool` (đỗ lượt chờ kết quả bên ngoài, sai ngữ nghĩa với gọi đối tác), `MCPTool` thật (không có trong test; theo mã nó không thuộc hai nhóm được miễn nên bị offload).

### (4) Quyết định A8 — XÁC NHẬN, kèm 3 chỉnh
Chặn trần trong tool rồi trả `pending/unknown` hoạt động đúng (`test_own_cap_below_10s_...`): partner 12 s, cap 8 s, model nhận `PENDING: ...` lúc 8.22 s, không bg task, không lượt đánh thức thừa, coroutine gọi đối tác bị hủy (kết quả phía đối tác là *không biết*, không phải *thất bại*). Nhưng:

1. **Cap phải bao cả thân tool, không chỉ cuộc gọi đối tác.** Đồng hồ 10 s chạy từ khi vào `on_acting`. Test `test_cap_that_forgets_preparation_time...`: 3 s chuẩn bị (ghi dòng operation, kiểm idempotency) + cap 8 s trên cuộc gọi = 11 s, bị offload lúc 10.31 s dù đã có cap, và câu `PENDING` chỉ tới model qua hint. Phải dùng một deadline duy nhất ngoài cùng (`asyncio.timeout`) cho cả hàm `call`, ngân sách còn lại cho đối tác = 8 s trừ phần đã dùng.
2. **Interrupt lượt không hủy tool trong 10 s đầu** (hàng 1 bảng trên). Vì vậy tool wrapper phải tự ghi kết quả vào bảng operation (trong chính hàm `call`, kể cả nhánh timeout, kể cả khi không ai nhận chunk trả về), không để kết quả chỉ sống trong giá trị trả về.
3. **Phòng thủ chiều sâu**: nên thêm Cách B với `allow_offload = False` cho mọi tool đối tác, để nếu lỡ vượt 10 s (lỗi trong cap) thì không âm thầm thành task nền không bền với câu "You will be notified" (và, với Redis, hint "interrupted by the user" sai sự thật). Cap trong tool vẫn là cơ chế chính; Cách B không thay cap, vì tool bị miễn offload mà không có deadline sẽ chặn lượt vô hạn.

## 4. Giới hạn của kiểm chứng

- Model là kịch bản giả; chỉ chứng minh đường ống. Không nói gì về cách model thật phản ứng với placeholder hay `PENDING`.
- Tool kiểu wrapper tự viết (`ToolBase`), không phải `MCPTool` và không có HTTP/MCP thật. `call_timeout` của HTTP MCP (research mục 1(c)) vẫn **chưa** kiểm.
- Một tiến trình, bus bộ nhớ, SQLite. Chưa chạy Redis, nhiều worker, restart thật (chỉ mô phỏng bằng thoát lifespan).
- Thời gian đo trên máy dev có độ lệch vài trăm ms; test dùng khoảng, không giá trị chính xác. Marker `slow` chưa đăng ký trong cấu hình pytest (không được sửa `pyproject.toml` ở bước này), chỉ cảnh báo vô hại; test đã tắt cảnh báo bằng `-W ignore` / `filterwarnings`.
- `OffloadPolicy` đọc `agent.toolkit.get_tool(name)` y như middleware gốc, và phụ thuộc chữ ký `Agent.__init__(middlewares=...)` và `ToolOffloadMiddleware.on_acting`: là API nội bộ của app layer, cần test lại khi nâng AgentScope.

## 5. Tác động lên spec

- Mục 3, **A8**: giữ "8 s mặc định, tối đa 9 s", sửa thành: (a) deadline này bao toàn bộ thân tool (chuẩn bị + ghi operation + gọi đối tác), đo từ lúc tool bắt đầu, không phải chỉ `call_timeout` của cuộc gọi MCP; (b) hết hạn thì hủy cuộc gọi và trả `unknown/pending`, ghi operation `unknown` chờ đối soát, không ghi `failed`; (c) kết quả luôn được tool tự ghi vào bảng operation, vì lượt bị interrupt không hủy tool và không ai đọc giá trị trả về; (d) mọi tool đối tác đặt `allow_offload = False` và `build_app` truyền `custom_agent_cls` dùng `OffloadPolicy` (code trong `p0_offload_stack.py`, `OffloadPolicy` và `agent_cls_with`), không dùng `is_state_injected`.
- Mục tool bọc MCP / test: thêm test yêu cầu "không bao giờ thấy chữ `running in background` trong context của leader" và "tool có chuẩn bị 3 s vẫn không bị offload".
- Research `AGENTSCOPE_CHO_WORKFORCE_V1.md` mục 7 và điểm (e) cuối file: đã kiểm, có đường tắt middleware bằng `custom_agent_cls` (khả thi); mục 5 nên bổ sung hàng "hủy tool nền = hint INTERRUPTED, không im lặng".
