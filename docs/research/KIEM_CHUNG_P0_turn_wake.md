# Kiểm chứng P0: lượt (turn), đánh thức (wake) và tuần tự hóa đầu vào của phiên leader

Ngày 2026-10-10. Nhánh `feat/platform-core`. Tác giả: probe `turn_wake`. Liên quan: `docs/WORKFORCE_V1_DAC_TA_TRIEN_KHAI.md` mục 1, 5, 9; `docs/research/AGENTSCOPE_CHO_WORKFORCE_V1.md` mục 2, 5.

Mọi kết luận dưới đây **đã chạy** (21 test, xanh; 20 test đầu xanh 3 lần liên tiếp, test cuối chạy xanh 1 lần), trên AgentScope vendored thật (`create_app`, trong một tiến trình, bus `InMemoryMessageBus`, SQLite), model giả có kịch bản. Không dùng mã `awp`. Chưa chạy: Redis, Postgres, nhiều tiến trình, model thật (xem "Chưa kiểm").

## Câu hỏi

1. Middleware `on_reply` có thấy `ReplyEndEvent` cho mọi lượt của leader, kể cả lượt do AgentScope tự khởi động (worker `TeamSay` đánh thức leader) và lượt do `POST /chat`? Lượt lỗi hoặc bị ngắt thì quan sát được gì?
2. Đánh thức leader đang rảnh bằng `deliver_to_inbox` (HintBlock) so với `POST /chat` `say()`: cái nào cho đúng một lượt, xác định, cho mỗi đầu vào?
3. `POST /chat` khi phiên đang chạy trong cùng tiến trình: mã trả về, tin nhắn mất hay còn? Cách tuần tự hóa an toàn nhất?
4. Có khe hở giữa "on_reply báo xong" và "phiên thật sự rảnh để nhận `say()` tiếp"? Đo bằng 20 lượt nối tiếp.

## Đã làm

Tệp mới (không sửa tệp nào có sẵn):

- `platform_VP/core/tests/probes/test_p0_turn_wake.py`: 21 test.
- `platform_VP/core/tests/probes/p0_turn_wake_env.py`: `TurnRecorder`, `TurnLog` (mẫu để tái dùng), `SerialDispatcher` (3 chiến lược gửi), `Env` (app AgentScope thật + hàm `say`, `wake`, `queue_message`, `status`...), `ProbeBus` (bus ghi thời điểm khóa phiên được nhả).
- `platform_VP/core/tests/probes/p0_turn_wake_llm.py`: model giả tương thích OpenAI, ghi lại từng lời gọi theo phiên, có thể trễ hoặc lỗi theo kịch bản.
- `platform_VP/core/tests/probes/p0_turn_wake_numbers.json`: số liệu thô của lần chạy cuối (sinh khi đặt `P0_WRITE_NUMBERS=1`).

Chạy: `cd platform_VP/core && PYTHONPATH=src ../agentscope/.venv/Scripts/python.exe -m pytest -q tests/probes/test_p0_turn_wake.py -s` (khoảng 90 giây). Thời gian đo bằng `time.perf_counter()`: đồng hồ `monotonic` trên Windows chỉ có độ phân giải 15,6 ms và `asyncio.sleep(0.01)` thực chất không ngủ, nên các số dưới 16 ms bằng `monotonic` là sai (lần chạy đầu của tôi dính lỗi này và đã sửa).

## Kết quả

### 1. `on_reply` thấy mọi lượt

`TurnRecorder.on_reply` ghi một bản ghi cho mỗi lần `on_reply` được gọi. Một lần `ChatService.run` (giữ khóa phiên một lần) có thể chứa **nhiều lượt**: sau lượt đầu, nếu inbox còn hàng thì vòng lặp trong `run` chạy thêm lượt với `inputs=None`.

| Nguồn lượt | `inputs` thấy trong `on_reply` | `ReplyEndEvent` | Ghi chú đo được |
|---|---|---|---|
| `POST /chat` với `Msg` | `Msg`, giữ nguyên `id` ta đặt (`msg_id` trả về đúng) | có, `completed` | tương quan lượt-việc bằng `Msg.id` |
| Worker `TeamSay` khi leader rảnh | `None` | có | 2 lần `run` cho leader (khóa lấy 2 lần); lượt thứ hai có `HintBlockEvent` chứa báo cáo |
| Worker `TeamSay` khi leader đang chạy | `None` | có | **1 lần `run`**, 2 lượt (vòng lặp trong `run`); khóa lấy 1 lần |
| Model lỗi (HTTP 500) | `Msg` | **không**: `on_reply` nhận **ngoại lệ** `openai.InternalServerError` | `ChatService` tự tạo `ReplyEndEvent(ERROR)` *sau đó*, ngoài chuỗi middleware; `GET .../messages` có tin assistant `finished_reason=error`, `error.type=upstream` |
| Ngắt `POST /sessions/{id}/interrupt` | `Msg` | có, `interrupted`, `on_reply` thấy ngay (dưới 10 ms sau yêu cầu ngắt) | `CancelledError` không lọt ra `on_reply` (mặc định `interruption_raise_cancelled_error=False`) |
| Lỗi **trước** khi lượt bắt đầu (credential bị xóa nên không dựng được agent) | `on_reply` **không bao giờ chạy** | không (ChatService phát cặp start/end ERROR trên bus) | `POST /chat` vẫn trả 200; **tin nhắn người dùng không được lưu**; chỉ có tin assistant lỗi (`invalid_request`) |

Điểm cần nhớ: mô hình lỗi mất rất lâu. Một lời gọi model hỏng tốn **12 lời gọi HTTP và 8,3 đến 8,9 giây** (AgentScope thử 4 lần, mỗi lần SDK OpenAI thử thêm 2 lần, nghỉ 1 giây giữa các lần) trước khi `on_reply` thấy ngoại lệ.

Đề xuất `TurnRecorder` (đã chạy trong probe): bọc `async for` bằng `try/except/finally`; ghi `trigger` (`message` | `continue`), `Msg.id`, các `HintBlockEvent.hint` (để tương quan lượt đánh thức với job qua dấu hiệu `job_id` ta nhúng vào hint), `finished_reason`, và `left` (`end_event` | `parked` | `exception:<Lớp>` | `cancelled` | `closed`). Trạng thái lưu = `parked` nếu thấy `RequireUserConfirmEvent`/`RequireExternalExecutionEvent`; `error` nếu `left` là ngoại lệ hoặc `finished_reason=error`; `interrupted`; `completed`. Phần `parked` chỉ đọc theo mã, không do probe này kiểm (probe `ask_park` lo).

### 2. Đánh thức (inbox) so với `say()` trên phiên rảnh

| Phép đo | `say()` (`POST /chat`) | `deliver_to_inbox` (wake) |
|---|---|---|
| 20 lần tuần tự, phiên rảnh | 20/20: đúng 1 lượt, 1 lời gọi model, thấy đúng văn bản | 20/20: đúng 1 lượt, 1 lời gọi model, hint nằm trong sự kiện và trong prompt |
| Độ trễ tới khi lượt xong (trung vị / tối đa) | 65 / 245 ms | 55 / 393 ms |
| 3 đầu vào bắn liên tiếp (model 0,4 s) | trả `200, 409, 409`: chỉ đầu vào đầu được xử lý, hai đầu vào sau **mất hẳn** | 8 lần thử: 4 lần đúng 1 lượt; **4 lần ra 3 lượt (2 lượt rỗng, vẫn tốn 1 lời gọi model mỗi lượt)**; cả 3 hint luôn được giao đúng một lần, không mất, không nhân đôi |
| Đầu vào đến giữa lúc `run` đang chạy | 409 | thả sau 0,02 và 0,1 giây: hint được nuốt vào lượt đang chạy **và** sinh thêm một `run` rỗng; thả sau 0,4 và 0,7 giây: 1 `run`, lượt thứ hai mang hint, không rỗng |

Nguyên nhân lượt rỗng (đọc mã `_bus_ops.deliver_to_inbox`, `_wakeup_dispatcher`, và khớp với số đo): producer chỉ bỏ qua việc xếp wake khi đã có "consumer" đăng ký, mà `run` chỉ đăng ký sau khi dựng xong agent. Hint đến trước lúc đó vừa được rút ở bước suy luận đầu, vừa để lại một lệnh wake; lệnh wake chạy sau khi nhả khóa, thấy inbox rỗng, và vẫn gọi model với ngữ cảnh kết thúc bằng tin assistant của chính nó. Với model thật, lượt rỗng này tốn tiền và có thể sinh một câu thừa.

Kết luận: **`say()` cho đúng một lượt xác định cho mỗi `Msg`** (tương quan bằng `Msg.id`) miễn là gửi khi phiên rảnh; **wake bằng inbox đúng một lần về nội dung nhưng không xác định về số lượt** và không cho khóa tương quan.

### 3. `POST /chat` khi phiên đang chạy (cùng tiến trình)

- Trả **409**, `{"detail": "Session '<id>' already has an active chat run in this process."}`.
- **Tin nhắn không được lưu** (không có trong `GET /sessions/{id}/messages`) và model không bao giờ thấy nó; không có lượt thứ hai. Gửi lại khi rảnh thì chạy bình thường. Nghĩa là 409 là mất mát có thể phát hiện được và an toàn để thử lại (không trùng).
- Phụ: mỗi 409 để lại cảnh báo "coroutine 'ChatService.run' was never awaited" (vô hại).
- Mô phỏng "đang chạy ở tiến trình khác" (giữ khóa phiên bằng tay, registry của tiến trình này trống): `POST /chat` trả **200 ngay (1 ms)**, `run` chờ khóa; trong lúc chờ **chưa có lượt, chưa gọi model, tin nhắn chưa được lưu**. Khi nhả khóa thì `run` chạy đúng một lần. Như vậy 200 không có nghĩa "đã nhận bền vững": nếu tiến trình chết trong lúc chờ thì mất tin. Chỉ mô phỏng bằng bus bộ nhớ, chưa chạy với Redis.
- `enqueue_run_trigger(kind="message")` (bus xếp hàng, dispatcher thử lại sau 0,1 s khi phiên bận): 5 tin xếp cùng lúc đều được xử lý hết, nhưng **thứ tự bị xáo** (ví dụ `q-0, q-2, q-1, q-3, q-4`). Không dùng để thay hàng đợi của ta.

### 4. Khe hở giữa "lượt xong" và "phiên rảnh"

`on_reply` báo xong **trước** khi `run` lưu tin trả lời và trạng thái phiên (và trước cả bước tự đặt tên phiên nếu có) rồi mới nhả khóa. Đo 20 lượt nối tiếp, model tức thì:

| Chiến lược gửi tiếp | 409 lần gửi đầu | POST tổng | Khe `on_reply` xong → khóa nhả (ms) trung vị / p90 / tối đa | Tổng 20 job |
|---|---|---|---|---|
| Gửi ngay trong hook kết thúc lượt (xấu nhất) | **19/19** | | 14,4 / 15,8 / 17,4 | |
| `say_retry`: gửi khi lượt xong, gặp 409 thì thử lại sau 20 ms | 34 | 54 | 14,4 / 15,9 / 38,9 | 2,50 s |
| `say_idle`: chờ khóa nhả rồi mới `say()` | **0** | 20 | 22,7 / 37,4 / 45,1 | 2,67 s |
| `bus_message`: để dispatcher của AgentScope xếp hàng | 0 | 20 | 27,2 / 46,5 / 56,6 | 3,29 s |

Với model chậm 50 ms: khe trung vị 11,5 / 13,4 / 19,4 ms (lần lượt theo ba chiến lược dưới), tối đa 16 / 36 / 61 ms; `say_idle` vẫn 0 lần 409.

Trong 3 chiến lược của `SerialDispatcher` và cả hai độ trễ model: đúng 20 lượt cho 20 job, đúng thứ tự gửi, không lượt nào chồng lên lượt khác (`started` sau `ended` của lượt trước), không lời gọi model nào chứa hai job. Chiến lược hook chỉ kiểm: đủ 20 lượt, mỗi `Msg.id` đúng một lần (thứ tự không bảo đảm vì gửi song song).

Vậy **có khe**: trung vị 12 đến 27 ms, tối đa 61 ms ở lần chạy cuối (một lần chạy trước đó của cùng test từng đo tới 145 ms, nên đừng tin vào mức trần). Khe này gồm ghi tin nhắn và trạng thái phiên. Phiên không đặt `name` còn thêm một lời gọi model để đặt tiêu đề (cùng khóa), khe 31 ms so với 9 ms, và hóa đơn thêm 1 lời gọi (ở đây fake khiến nó lặp 3 lần). `awp` luôn truyền `name` khi tạo phiên nên không dính; giữ như vậy.

`GET /sessions/{id}/status` trả `running` đúng khi giữ khóa, `idle` chỉ sau khi tin trả lời đã lưu (test `status_endpoint`); dùng được làm kiểm tra "an toàn để gửi" thay vì `bus.is_locked` (cùng nguồn).

## Hệ quả cho đặc tả `docs/WORKFORCE_V1_DAC_TA_TRIEN_KHAI.md` (không tự sửa)

**Mục 9, gạch đầu dòng "Hàng đợi `wf_jobs`"** ("xong khi lượt kết thúc và `settle` chạy") sai ở hai chỗ:
- Job xong khi (a) mọi lượt do nó khởi phát đã kết thúc **và** (b) phiên rảnh (khóa phiên đã nhả: `bus.is_locked(MessageBusKeys.session_lock(sid))` là false, hoặc `GET /sessions/{id}/status` = `idle`). Chỉ (a) là chưa đủ: gửi ngay sau `on_reply` bị 409 tới 100% số lần.
- Khâu dispatch `AgentScopeClient.say` hiện ném `RuntimeError` cho mọi mã >= 300 (`intake/agentscope_client.py:108`). Cần ngoại lệ riêng cho 409 (`SessionBusy`), xử lý: chờ rảnh rồi gửi lại (an toàn, không trùng vì 409 không lưu gì). Dù đã chờ rảnh vẫn có thể gặp 409 (worker `TeamSay` bắt đầu một `run` đúng lúc ấy), nên vòng lặp thử lại là bắt buộc, không phải tùy chọn.
- Không coi HTTP 200 là "đã nhận". Có hai đường 200 mà tin vẫn mất: lỗi dựng agent (tin không lưu, `on_reply` không chạy) và khóa đang giữ ở nơi khác (chưa lưu). Xác nhận bằng cách thấy lượt có đúng `Msg.id` của job trong `wf_turns` trong một thời hạn; quá hạn thì gửi lại cùng `Msg.id` hoặc `needs_attention`.

**Mục 9 / A6, đường đánh thức cho `provider_wake` và `nudge`:** dùng `say()` với `Msg` (văn bản bọc `<provider-event job="...">` như mục 6 đã định) thay vì `Runtime.deliver`/`deliver_to_inbox`. Lý do: một `Msg` = đúng một lượt, có `Msg.id` để tương quan, 409 phát hiện được; còn wake bằng inbox cho lượt rỗng (4/8 lần khi bắn 3 hint liên tiếp; 2/4 thời điểm khi hint đến giữa lúc `run` đang dựng), không có khóa tương quan, và thất bại không có tín hiệu. Chỉ dùng inbox cho thứ ta không kiểm soát (worker `TeamSay`, `AgentCreate`, báo lỗi worker). Mục 5 khoản 6 ("watchdog nhắc tối đa 2 lần") cũng nên thành job `nudge` đi qua hàng đợi, không phải `LeaderWatchdog._after` gọi `Runtime.deliver` như hiện nay.

**Mục 5, `settle`:** không giả định "một lượt kết thúc = một việc xong". Có hai loại lượt không do job nào khởi phát: lượt do báo cáo của worker (có thật, cần `settle`) và lượt rỗng do wake thừa (vô hại nhưng tốn một lời gọi model). `TurnRecorder` phải ghi cả hai với `job_id = null`. Tại thời điểm `on_reply` kết thúc ta chưa biết còn lượt tiếp trong cùng `run` hay không (vòng lặp kiểm tra inbox chạy sau). Đề xuất: ghi lượt ngay (trong `on_reply`, ghi DB nhanh), còn `settle` và chuyển `request` sang `completed` chạy khi phiên đã rảnh (cùng điều kiện (b) ở trên), và chạy lại ở lần rảnh kế tiếp nếu có lượt mới; `settle` phải idempotent.

**Mục 5 / 7.2 "Chờ lượt" 25 giây:** một lượt lỗi model chiếm khoảng 8 đến 9 giây và 12 lời gọi HTTP trước khi thấy lỗi; khi model sập, mỗi job ăn ngần ấy trước khi thành `failed`. Lỗi thấy được dưới dạng **ngoại lệ trong `on_reply`** (không có `ReplyEndEvent`), nên `TurnRecorder` phải bắt ngoại lệ, không chỉ chờ `ReplyEndEvent`. Cân nhắc đặt `max_retries` thấp cho SDK (tùy chọn cấu hình model, chưa thử).

**Mục 6.1:** không đổi. Lượt đỗ HITL không do probe này kiểm.

Không cần sửa `docs/WORKFORCE_V1_DAC_TA_TRIEN_KHAI.md` ở mục 1 (sơ đồ) hay 4 (bảng `wf_turns`): cột `status` (`running|completed|parked|error|interrupted`) đủ. Gợi ý thêm cột nhẹ cho `wf_turns`: `trigger` (`message`|`continue`), `msg_id` (nullable) để tương quan, và cho phép `job_id` null.

## Mã tái dùng

`platform_VP/core/tests/probes/p0_turn_wake_env.py`:
- `TurnRecorder` (middleware, ghi qua `TurnLog.begin/end`; ở engine thay `TurnLog` bằng ghi `wf_turns`);
- `SerialDispatcher` (một job một lúc; chiến lược `say_idle` là chiến lược nên dùng; thêm vòng thử lại 409);
- `Env.wait_idle`, `ProbeBus.lock_events` (đo thời điểm nhả khóa chính xác).

## Chưa kiểm / hạn chế

- Chỉ SQLite và `InMemoryMessageBus`. Với Redis, khóa phiên là khóa phân tán có TTL và heartbeat; khe nhả khóa và độ trễ wake qua Redis có thể khác. "Khóa giữ ở tiến trình khác" chỉ mô phỏng bằng giữ khóa tay.
- Model giả: không nói gì về lượt rỗng với model thật (có thể trả câu thừa hay không).
- Lượt đỗ HITL (ASK) và `RequireUserConfirmEvent` trong `TurnRecorder`: chỉ viết mã, không có test trong probe này.
- `TeamMemberLoopMiddleware` của worker có thể nuốt `ReplyEndEvent` (đọc mã); probe chỉ thấy lượt worker đơn giản kết thúc bình thường. Leader không có middleware đó.
- `exceed_max_iters`, nhiều worker đồng thời, offload 10 giây, sập tiến trình giữa lượt: không thuộc probe này.
- Số đo thời gian từ máy Windows dev, sự kiện trong cùng một event loop và httpx ASGITransport, nên tuyệt đối không đại diện cho môi trường triển khai; chỉ so sánh tương đối và bậc độ lớn đáng tin.
