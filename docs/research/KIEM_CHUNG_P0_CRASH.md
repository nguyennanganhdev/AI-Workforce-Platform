# Kiểm chứng P0: crash giữa lượt

Ngày 10/10/2026. Nhánh `feat/platform-core`. Mã kiểm: `platform_VP/core/tests/probes/test_p0_crash.py` (18 test) cùng `p0_crash_helpers.py`, `p0_crash_node.py`. Không sửa `src/awp`, `tests/fake_llm.py`, `tests/support.py`, không sửa AgentScope.

## 1. Câu hỏi

Đặc tả mục 9: khi tiến trình chết cứng giữa lượt, lúc một tool có tác dụng phụ đang chạy, thì cái gì còn trên đĩa, tiến trình khởi động lại nhìn thấy gì, và thiết kế phục hồi của ta (bảng của ta ghi dòng intent kèm `client_reference` trước tác dụng phụ, sau restart tool tìm thấy dòng đó và không lặp lại) có đứng vững không.

## 2. Cách làm

- Hai tiến trình HĐH thật ("node") chạy `build_app` đầy đủ, dùng chung các tệp SQLite (`awp.db`, `as.db`) và thư mục workspace. Node 1 bị `Popen.kill()` (TerminateProcess trên Windows, không chạy handler nào) khi tool đang chạy. Node 2 khởi động mới với `InMemoryMessageBus` mới.
- Model là kịch bản (server OpenAI-compatible giả, chạy trong tiến trình test). Leader gọi tool `book_plumber`, rồi `CaseFinalize` trích kết quả tool.
- Tool `book_plumber` ghi một "tác dụng phụ" vào tệp `effects.log` (đại diện thế giới bên ngoài). Có thể treo ở ba điểm: `after_intent` (dòng intent đã commit, chưa gọi bên ngoài), `after_effect` (đã gọi bên ngoài, dòng intent vẫn `intent`), `after_mark` (đã gọi, dòng intent là `sent`, chưa trả kết quả).
- Có/không có "guard": bảng `p0_operations` trong `awp.db` (khóa duy nhất `client_reference`, dẫn xuất từ `case_id|tool|args_hash`).
- Kiểm tra trực tiếp bằng `sqlite3` trên bảng `sessions` và `messages` của AgentScope, bảng `awp_case_items`, bảng intent, qua endpoint `/sessions/{id}/status`, và `POST /chat/` ở node 2.
- Redis: container `awp-test-redis` (`redis:7-alpine`, cổng ngẫu nhiên trên 127.0.0.1), đã xóa sau khi chạy (đã kiểm `docker ps -a`).

## 3. Kết quả (đều có test chạy xanh; cả tệp chạy 3 lần liên tiếp, hai lần đầu 17/17 trước khi thêm test mồ côi approval, lần cuối 18/18 trong 171 giây)

### 3.1 Lượt dở dang không được lưu

| Quan sát | Giá trị |
|---|---|
| `AgentState.context` trong `sessions` khi tool đang chạy | `[]` (rỗng), cả sau khi kill, y hệt |
| Bảng `messages` | chỉ có tin `user` đầu vào (lưu trước khi agent chạy); không có tin assistant/tool |
| Tin mở đầu của vụ (`<case id=...>`) | **không** nằm trong `context`, chỉ trong `messages` |
| `awp_case_items` | chỉ bằng chứng intake (`E1`); vụ vẫn `open`; không có evidence của tool |
| Bảng intent của ta | dòng nằm đó đúng trạng thái lúc chết (`intent` hoặc `sent`) |
| `effects.log` | tác dụng phụ đã xảy ra (1 dòng) |

### 3.2 Node 2 nhìn thấy gì

- `GET /sessions/{id}/status` trả `idle`. Với `InMemoryMessageBus` khóa phiên nằm trong bộ nhớ tiến trình cũ nên mất theo; không có khóa kẹt. (Xác nhận.)
- Không ai tự chạy lại lượt dở: chờ 3 giây, không có lần gọi model hay tool nào mới. AgentScope không có cơ chế khôi phục lượt.
- `POST /chat/` tin mới vào phiên: `200 started`, chạy bình thường. Model của node 2 nhận context chỉ gồm tin mới (và khối `system-reminder` giờ); **không thấy tin mở đầu của vụ, không thấy lần gọi tool trước**. Kịch bản model gọi lại `book_plumber` với `tool_call_id` mới. Model thật hành xử khác chưa biết, nhưng context thì chắc chắn trống như vậy.
- Tin mở đầu lấy lại được từ bảng `messages` (`first_user_text`), nên "xếp lại job cũ" khả thi, nhưng nguồn nên là `wf_jobs.payload` của ta.

### 3.3 Trùng tác dụng phụ: không guard thì trùng, có guard thì không

| Test | Điểm chết | Cấu hình | `effects.log` |
|---|---|---|---|
| `test_duplicate_side_effect_without_guard[redispatch_original / new_message]` | `after_mark` | không guard | **2 dòng**, cùng `client_reference`, hai pid khác nhau |
| `test_no_duplicate_with_intent_guard_after_mark[...]` | `after_mark` | guard | **1 dòng**; node 2 gọi tool, guard thấy `sent` và trả "đã đặt, không lặp" |
| `test_intent_row_alone_cannot_tell_if_the_effect_happened` | `after_intent` / `after_effect` | guard, chính sách `unknown` (không gọi lại) | 0 / 1 dòng; trạng thái đều là `intent` rồi `unknown`, **không phân biệt được** |
| `test_retry_with_same_reference_is_safe_only_if_provider_is_idempotent` | `after_intent` / `after_effect` | guard, gọi lại cùng `client_reference`, provider chống trùng theo reference | 1 dòng (cả hai) |
| `test_retry_with_same_reference_duplicates_if_provider_is_not_idempotent` | `after_effect` | như trên nhưng provider không chống trùng | **2 dòng** |

Kết luận: dòng intent của ta chỉ đủ khi crash rơi vào cửa sổ sau khi dòng đã thành `sent`. Hai cửa sổ trước (`intent` còn nguyên) thì chỉ từ DB của ta không biết hành động đã xảy ra hay chưa. Muốn "đúng một lần" phải có một trong hai: provider chống trùng theo `client_reference`, hoặc cách tra trạng thái theo reference; nếu không, chỉ còn "không bao giờ trùng nhưng có thể mất hành động" kèm `needs_attention`. Đây chính là mô hình `unknown` của mục 8, nhưng mục 8 cần nói rõ hơn (xem 5).

### 3.4 `tool_call_id` không ổn định qua crash

Lượt dở không được lưu, nên model sinh `tool_call_id` mới (test `test_hard_crash_state_and_restart_view`: hai id khác nhau). Đồng thời, `ToolBase.call` chỉ nhận các tham số của model (đọc `tool/_toolkit.py:305-311`, không có test riêng) nên tool không thấy `tool_call_id`. Khóa chống trùng theo `tool_call_id` sẽ không bao giờ khớp trong kịch bản mất lượt.

### 3.5 Approval và crash

- Dùng `ApprovalGate` (middleware trả ASK từ `on_check_permission`) trên phiên `permission_mode = dont_ask`: phiên đỗ thật, `status = awaiting_permission`, `context` lưu tool call ở trạng thái `asking`. Đây cũng là bằng chứng phụ cho điểm mở ở mục 6.1 (ASK từ middleware có đỗ trong `dont_ask`): có. (Chủ đề P0 riêng có thể xác nhận lại.)
- Cư dân duyệt, tool chạy (đã có tác dụng phụ), crash: bộ nhớ lưu vẫn là `asking` (bước resume không lưu gì), node 2 báo `awaiting_permission`. Gửi lại đúng sự kiện duyệt: framework **chạy tool lần nữa** (`tool_calls.log` có `CALL` thứ hai). Không guard: 2 tác dụng phụ; có guard (`sent`): 1. Test `test_crash_while_approved_tool_runs[False-2 / True-1]`. Ở kịch bản này `tool_call_id` ổn định (lưu trong state).
- Tin mới của cư dân vào phiên đang `awaiting_permission` sau crash: `POST /chat/` trả `200 started` nhưng **không có lần gọi model nào**, phiên vẫn `awaiting_permission`, tin chỉ nằm trong `messages`, không vào `context`; không có lỗi trả về. Xác nhận mục A4 (phải chặn 409 `APPROVAL_PENDING` ở API của ta, vì AgentScope nuốt im lặng). Test `test_new_message_while_parked_after_crash`.
- Crash giữa lúc middleware đã ghi dòng approval của ta và lúc lượt đỗ được lưu: dòng `pending` còn, nhưng phiên `idle` và không có tool call nào để resume (`test_crash_between_our_approval_row_and_the_park_leaves_an_orphan`). Dòng mồ côi thật sự xảy ra; mục 9 nói "đối soát" là đúng và cần làm.

### 3.6 Rủi ro 2 của tài liệu nghiên cứu (tool `ALLOWED` chưa có kết quả)

Trong mọi kịch bản crash cứng đã chạy, kho **không bao giờ** chứa call ở `ALLOWED`: trạng thái đó chỉ tồn tại trong bộ nhớ giữa hai lần lưu. Cái bị chạy lại là call `ASKING` sau khi duyệt lại (3.5), không phải `ALLOWED`. Cũng không có gì chạy lại tự động khi khởi động. Tôi **không** dựng trạng thái `ALLOWED` giả trong kho để thử; phần `_next_action` chạy các call `PENDING/ALLOWED` chưa có kết quả (`agent/_agent.py:3510-3532`) vẫn chỉ là đọc mã.

### 3.7 Tool chạy quá 10 giây (offload)

Test `test_tool_over_10_seconds_is_offloaded_then_lost_on_crash`: sau 10 giây `ToolOffloadMiddleware` kết thúc lượt với kết quả giữ chỗ, và lượt này **được lưu**: tool call `finished`, kết quả `state=success` với nội dung "running in background ... You will be notified automatically". Task nền chết cùng tiến trình; dòng intent kẹt ở `sent` mãi; sau restart không có thông báo nào đến, không có gì chạy lại. Quan sát trong lần chạy thăm dò: kết quả giữ chỗ không được `EvidenceMiddleware` gắn evidence, và leader kịch bản không kết thúc vụ nên watchdog đẩy vụ sang `failed`. Xác nhận lý do của A8 (`call_timeout` tối đa 9 giây).

### 3.8 Ngắt êm khác với crash

`POST /sessions/{id}/interrupt` (test `test_graceful_interrupt_...`): lượt **được lưu**, tool call đóng bằng kết quả `interrupted`, nhưng tác dụng phụ đã xảy ra và dòng intent vẫn `sent`. Tức là ngay cả đường êm cũng cần guard.

### 3.9 Bus Redis: khóa sống lâu hơn tiến trình

Test `test_redis_bus_lock_survives_a_hard_crash` (Redis thật trong Docker):
- Sau khi kill, khóa `agentscope:session:lock:<sid>` còn trong Redis, TTL trong khoảng (300, 600] giây; log sự kiện phiên cũng còn (không bị `log_trim`).
- Node 2 báo `running`. `POST /chat/` trả `200 started` nhưng lượt chờ khóa: sau 6 giây không có lần gọi model nào.
- Xóa khóa bằng tay (`DEL`): lượt chờ chạy ngay, guard chặn tác dụng phụ trùng (1 dòng).
- Với `InMemory` không có hiện tượng này (3.2). Vậy P5 chạy Redis sẽ bị đứng tối đa ~10 phút mỗi phiên sau crash nếu không có bước giải phóng khóa.

### 3.10 Bộ quét cũ

`test_old_stall_sweeper_fails_the_orphaned_case_after_restart`: với `case_stall_seconds` nhỏ, `expire_stalled` của node 2 chuyển vụ mồ côi sang `failed` ("no activity for N seconds") trong khi booking vẫn tồn tại ngoài đời. Nếu không có bước xếp lại job trước, mặc định 900 giây là hạn chót của phục hồi.

## 4. Kết luận về thiết kế phục hồi

Đúng, với bổ sung:
1. Nguồn sự thật là DB của ta: đúng. AgentScope không giữ gì dùng được của lượt dở (context rỗng, tin mở đầu ngoài context).
2. Dòng intent ghi trước tác dụng phụ ngăn trùng, nhưng chỉ khi crash xảy ra sau khi dòng thành `sent`. Hai cửa sổ còn lại cần provider idempotent theo `client_reference` hoặc tra trạng thái.
3. Không thể dựa vào AgentScope để chạy lại hay báo lỗi: mọi chạy lại phải do `wf_jobs` của ta xếp, và khi chạy lại model không nhớ gì về lần trước (phải tiêm từ DB, đúng với mục 6).

## 5. Việc cần làm đối với đặc tả (`docs/WORKFORCE_V1_DAC_TA_TRIEN_KHAI.md`; tôi không sửa tệp này)

- **Mục 8, tool hành động.** Câu "Gặp lại cùng `(workflow, tool, args_hash, tool_call_id)`" sai: bỏ `tool_call_id` khỏi khóa. Dùng `(workflow, tool, args_hash)` và `client_reference` dẫn xuất xác định từ đó. Thêm luật: lời gọi giống hệt khi dòng cũ chưa terminal (`intent|sent|pending|unknown`) thì trả dòng cũ, không gọi mới; chỉ cho phép thao tác mới cùng tham số khi dòng cũ đã terminal (chưa kiểm bằng test, suy luận).
- **Mục 8, trạng thái `intent` sau restart.** Thêm quy tắc: gặp `intent` quá hạn thì không biết đã gửi hay chưa. Nếu `wf_tools.idempotency_arg` có (provider chống trùng theo reference) thì gửi lại cùng `client_reference`. Nếu không, nếu có `status_query` thì tra rồi quyết, còn không thì `unknown` và `needs_attention`. Việc chèn dòng phải nguyên tử (`INSERT` khóa duy nhất, rẽ nhánh theo kết quả); mã probe kiểm-rồi-chèn không an toàn khi hai node đua nhau, cái này chưa kiểm.
- **Mục 9, phục hồi khi khởi động.** Viết rõ thành các bước: (a) quét `wf_jobs` hết lease và xếp lại đúng job (payload gốc), vì AgentScope không tự làm; (b) với bus Redis, chỉ sau khi lease của job (hoặc node) đã hết hạn mới xóa khóa phiên `agentscope:session:lock:<sid>` của phiên đó, không xóa bừa vì node khác có thể đang giữ khóa thật; (c) đối soát `wf_approvals pending` với trạng thái phiên: nếu phiên không `awaiting_permission` thì huỷ dòng approval (hoặc xếp lại job); nếu phiên `awaiting_permission` mà ta không có approval pending thì gửi `UserInterruptEvent`; (d) chặn `expire_stalled` cũ cho workflow có job đang chờ khôi phục.
- **Mục 6.1.** Ghi thêm: sự kiện duyệt gửi lại sau crash sẽ chạy tool lần nữa; guard intent là bắt buộc cho `requires_consent`, không chỉ cho tool bất đồng bộ. Điểm mở "ASK trong `dont_ask`" đã có bằng chứng chạy là đỗ.
- **A4** giữ nguyên và có thêm lý do: sau crash, tin mới vào phiên đang đỗ bị nuốt im lặng.
- **A8** giữ nguyên, có bằng chứng chạy.
- **Mục 10, tiêu chí P5** "crash giả lập giữa lượt chờ không tạo job/operation mới": test hiện có chỉ kiểm với SQLite; phải thêm trường hợp khóa Redis kẹt.
- **Tài liệu nghiên cứu `AGENTSCOPE_CHO_WORKFORCE_V1.md`**: mục 5 rủi ro 2 nên đổi thành "call `ALLOWED` không bao giờ được lưu giữa lượt; cái chạy lại là call `ASKING` sau khi duyệt lại"; rủi ro 4 (khóa 600 giây) đúng cho Redis và không xảy ra với InMemory.

## 6. Hạn chế

- Chỉ SQLite, một máy Windows. Kill giữa lúc DB đang ghi dở chưa thử (mọi lần kill đều rơi vào lúc tool đang treo, DB rảnh).
- Model là kịch bản; không nói gì về cách model thật phản ứng với context trống, cũng như chất lượng tiếng Việt.
- Tool, guard và provider là mã probe của tôi, không phải `PartnerTool` thật. Chưa thử hai node chạy đồng thời cùng một vụ.
- Tool treo ở `asyncio.sleep`, không phải lời gọi MCP thật qua mạng.
- Redis: chỉ kiểm khóa phiên và log sự kiện. Hàng đợi wakeup/inbox, SSE và cấu hình persistence của Redis chưa kiểm.
- Chưa kiểm Postgres, chưa kiểm SIGTERM êm của uvicorn (chỉ kiểm `interrupt` API).
- Tuyên bố "tool không thấy `tool_call_id`" lấy từ đọc mã, không có test riêng.
