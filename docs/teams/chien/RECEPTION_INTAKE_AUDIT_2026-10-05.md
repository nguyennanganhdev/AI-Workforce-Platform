# Kiểm tra luồng tiếp nhận yêu cầu từ Lễ tân — 05/10/2026

Phạm vi: đọc mã nguồn và test trên nhánh `dev_teamChien_HuyDo` (chỉ đọc, không sửa file nào khác).
Cách làm: **đọc code, không chạy dịch vụ, không gọi model, không ghi cơ sở dữ liệu**. Chưa ai tái hiện được
triệu chứng; mọi kết luận dưới đây là "code cho phép điều đó xảy ra", kèm `đường dẫn:dòng`. Việc duy nhất được
chạy là hàm thuần `decide_request` (tách bằng `ast`, không cần DB/mạng/model) để xác nhận điểm F2.

Cập nhật cùng ngày: lỗi đã được tái hiện trên stack Docker local với model thật, và các ca thật trong cơ sở dữ liệu
khớp với F1, F3, F8. Xem mục 4 của [PROJECT_AUDIT_2026-10-05.md](PROJECT_AUDIT_2026-10-05.md). Chế độ đang chạy trên stack là `loop`.

---

## 0. Tình trạng sau khi sửa (05/10/2026, chiều)

Đã sửa trên nhánh `dev_teamChien_HuyDo` (tại thời điểm ghi nhận ban đầu chưa commit). Cách kiểm: test đơn vị, test có PostgreSQL thật, test đầu-cuối
qua HTTP thật cho cả `loop` và `graph` (9/9 mỗi chế độ, model giả cố ý bịa nguyên nhân), và chạy lại đúng ca lỗi trên
stack Docker local với `gpt-6-luna`. Các mục dưới giữ nguyên làm hồ sơ của lỗi lúc phát hiện.

Nơi quyết định mới: `services/vinhomes-api/src/vinhomes_api/reception_intake.py`. Tiêu đề và mô tả của yêu cầu là
nguyên văn tin nhắn cư dân; một chi tiết chỉ được giữ khi tìm thấy trong tin nhắn nó dẫn; sự cố thường chỉ được bàn
giao khi có hiện tượng và có vật hoặc điểm cụ thể, hoặc cư dân nói họ không biết; hỏi hai lần chưa có thì chuyển
nguyên trạng cho người xem.

| Điểm | Tình trạng | Ghi chú |
|---|---|---|
| F1 | Đã sửa | `file_request` không còn nhận tiêu đề, mô tả; backend kiểm và quyết định. Test: `tests/test_reception_intake.py`, `tests/agent/test_intake_tools.py` |
| F2 | Đã sửa | `graph` hỏi câu của backend trước khi bàn giao; `decide_request` hỏi trước khi mở yêu cầu khi model nói chưa có gì để ghi |
| F3 | Đã sửa | Ứng dụng cư dân không gửi "Báo sự cố" thay cư dân, không chạy biểu mẫu song song; biểu mẫu chỉ được mời khi Lễ tân không trả lời được. Test: `resident-app/tests/chat-turn.test.ts`; giao diện kiểm trên trình duyệt |
| F4 | Đã sửa a, b, e; c báo đúng; d giữ theo thiết kế | Chỉ báo "đã chuyển khẩn cấp" khi backend đã nhận, không thì bảo cư dân gọi bảo vệ/BQL. Model vẫn được đề xuất khẩn cấp (để không sót), nhưng nội dung ghi lại là nguyên văn tin nhắn |
| F5 | Sửa phần ảnh rơi khỏi yêu cầu | Ảnh của mọi tin trong cuộc trò chuyện được gắn khi tạo; ảnh gửi sau được gắn qua `follow-up`. **Còn mở:** model chưa xem được ảnh (đã nói rõ với cư dân), màn BQL đọc hội thoại chưa hiện ảnh |
| F6 | Còn mở một phần | Phiên dừng vì model tự chạy lại (mục Supervisor). Tin bị `park` vẫn chỉ là một con số; cư dân không được báo khi phiên dừng |
| F7 | Còn mở | Supervisor vẫn xử lý tuần tự |
| F8 | Đã sửa (`loop`) | Tin cư dân gửi khi Supervisor đang hỏi được chuyển nguyên văn thành câu trả lời |
| F9 | Đã sửa cho `loop`, biểu mẫu cư dân và `follow-up` | `graph._follow_up` còn dùng bản đã lưu |
| F10 | Đã sửa | Đã tạo yêu cầu thì luôn có câu xác nhận |
| F11 | Sửa phần khóa và câu báo lỗi | Bị hỏi lại thì không còn tạo bản nháp; một lần tạo hỏng giữa chừng vẫn để lại bản nháp |
| F12 | Đã sửa | Báo rõ hồ sơ thiếu họ tên hoặc số điện thoại |
| F13 | Sửa phần báo cho BQL | Rơi vào "cần người xem xét" thì mở phiên hỏi BQL. Bộ đếm câu hỏi của graph vẫn không đặt lại |
| F14 | Đã sửa | |
| F15 | Đã sửa | Tin mất lượt được trả lời khi tin kế tiếp tới. Test: `tests/test_reception_follow_up.py` |
| F16 | Đã sửa | Lượt `loop` dừng ở 150 giây |
| F17 | Đã sửa, chưa có test riêng | Không có định danh dịch vụ của workspace thì yêu cầu đi thẳng tới BQL |
| F18 | Đã sửa | Thử lại một lần với 429, 5xx, rớt kết nối |
| F19 | Còn mở | Trong cùng lượt đã bị hỏi lại thì không lách được; ngoài ra vẫn dựa vào model |
| F20 | Đã sửa | Lịch sử dừng ở tin của lượt |
| F21 | Đã sửa, chưa có test riêng | Vòng lặp Supervisor ghi log và chạy tiếp |
| F22 | Đã sửa, chưa có test riêng | Báo mở cuộc trò chuyện mới |

Khẩn cấp có phủ định ("không có mùi khét") không còn bị xếp khẩn cấp. Danh sách từ khóa vẫn cần người có thẩm
quyền duyệt.

Mục 6 (test hợp thức hóa hành vi sai): đã đổi `fake_llm.py`, `test_resident_chat_e2e.py`, `test_loop.py`,
`test_emergency_guidance.py`, `test_image_references.py`, `test_v3_agent_database.py`; thêm
`tests/graph/test_intake_question.py` (có ca `staff_required` cùng câu hỏi). Chưa đổi: bộ đánh giá `tests/evals/run_live.py` vẫn chỉ chấm lời thoại.

---

## 1. Kết luận ngắn

1. Triệu chứng "Nhà tắm của tôi bị rò nước + ảnh → Lễ tân tự thêm chi tiết rồi bàn giao ngay" **không phải lỗi ngẫu
   nhiên của model mà là hành vi code cho phép ở cả hai chế độ**. Chế độ `loop`: prompt bảo tạo yêu cầu khi "rõ việc
   gì và ở đâu", còn `title`/`description` do model tự viết đi thẳng vào ticket, không có cổng nào so với lời cư dân.
   Chế độ `graph`: backend trả `staff_required=true` cho mọi tin được model xếp là "sự cố", và `decide_request` xét
   `staff_required` **trước** `missing_information`, nên graph không bao giờ hỏi lại.
2. **Model không bao giờ nhìn thấy ảnh.** Bộ nối model chỉ gửi chuỗi văn bản. Ở `loop` model còn không biết có ảnh;
   tin chỉ có ảnh được ứng dụng cư dân gửi kèm câu giả "Đính kèm ảnh phản ánh".
3. Ứng dụng cư dân chạy **hai đường tạo yêu cầu song song**: biểu mẫu nháp cục bộ (tự hỏi "Sự cố xảy ra ở đâu?")
   và Lễ tân. Lễ tân tạo ticket trước; khi cư dân bấm gửi biểu mẫu thì nhận `409 This chat already has a ticket`,
   còn vị trí vừa gõ không vào ticket.
4. Đường khẩn cấp ở `loop` có ba chỗ hỏng: báo "đã chuyển ở mức khẩn cấp" khi **chưa tạo được gì**; cư dân có 2 căn
   hộ không báo khẩn cấp được; ticket đang `resolved` thì trả câu lỗi chung. Ngoài ra model tự nâng khẩn cấp luôn
   được "policy xác nhận".
5. Sau khi bàn giao, cư dân **không nhận thêm tin nào** cho tới khi Supervisor hỏi hoặc BQL duyệt phương án. Mọi
   kiểu dừng của Supervisor (không có chuyên viên, model lỗi, tin bị "parked") đều im lặng với cư dân.
6. Supervisor xử lý **một tin một lúc, tuần tự cho mọi ticket**; trong lúc xử lý cũng không đọc hộp thư.
7. Bộ test hiện tại hợp thức hóa đúng các hành vi sai trên (mục 6); bộ đánh giá "live" chỉ chấm lời Lễ tân nói,
   không đọc nội dung ticket và không có kịch bản nào có ảnh.
8. Phán quyết 11 điểm nghi ngờ: 8 CONFIRMED, 3 PARTLY, 0 REFUTED (mục 2).

---

## 2. Mười một điểm nghi ngờ

| # | Điểm nghi ngờ | Phán quyết | Bằng chứng |
|---|---|---|---|
| 1 | `agent/prompt.py`: "việc gì và ở đâu" là đủ | **CONFIRMED** | `agent-reception/src/agent/prompt.py:11-12`: "khi đã rõ là việc gì và ở đâu trong nhà thì gọi file_request. Nếu còn mơ hồ ("nhà tôi có vấn đề", "hỏng rồi", "nước có vấn đề") thì hỏi MỘT câu". "Nhà tắm" + "rò nước" thỏa cả hai. Ví dụ tiêu đề trong mô tả công cụ `tools.py:36` là "Vòi nước bếp bị rò" (có tên thiết bị) nên model có xu hướng tự điền thiết bị. `prompt.py:23-24` còn bảo "ghi điều này vào description" từ `yeu_cau_truoc_day` (tiêu đề 5 yêu cầu cũ, `prompt.py:56-57`). |
| 2 | `agent/tools.py`: `_file_request` không có cổng nội dung | **CONFIRMED** | `tools.py:143-157` chỉ kiểm: có yêu cầu đang mở, `title`/`description` khác rỗng (`:146`), danh mục/ưu tiên hợp lệ (`:148-150`), căn hộ (`:151-154`). `_file` gửi thẳng: `"title": title.strip()[:300], "description": description.strip()[:10000]` và `"facts": []` (`tools.py:119-120`). |
| 3 | `agent/loop.py`: không xử lý kết quả công cụ đòi hỏi lại; chặn công cụ này vẫn bàn giao bằng công cụ khác | **CONFIRMED** | Vòng lặp chỉ nối kết quả vào hội thoại rồi `continue` (`loop.py:77-88`); mọi `tool_calls` trong một câu trả lời đều được chạy lần lượt (`loop.py:77`). `report_emergency` gửi `"assessment": {"proposed_action": "emergency_handoff"}` (`tools.py:161-162`) và backend tính `emergency = kind is not None or proposal.get("proposed_action") == "emergency_handoff"` (`v3_reception_runtime.py:74`) nên **luôn được xác nhận**; nhánh `not_an_emergency_by_policy` (`tools.py:163-164`) không bao giờ chạy. `ask_management` chỉ cần `self.searched` (`tools.py:206`), tức gọi `search_knowledge` một lần là chuyển được. `if toolbox.emergency: return EMERGENCY_REPLY` (`loop.py:85-87`). |
| 4 | `prompts/workflow.py`: "không bịa" chỉ là lời | **CONFIRMED** | `prompts/workflow.py:12` "Không bịa facts…", `:87` "Chỉ trích nội dung cư dân đã nói", `:95` "Không bịa title/description khi chưa có". Phía code chỉ có `parse_turn` kiểm `source_message_id` thuộc tập cho phép (điểm 6). |
| 5 | `graph/workflow.py`: `_collect_incident_details` lấy nội dung từ `_extract` | **CONFIRMED** (riêng `_active_ticket_dialogue`: PARTLY) | `workflow.py:617-626`: `"title": prior["title"] or turn.get("title", "")`, `"description": "\n".join(filter(None, [prior["description"], turn.get("description")]))`, `"facts": prior["facts"] + turn["facts"]`, rồi `update_ticket_incident` (`:627-632`). `_active_ticket_dialogue` gửi lời thật của cư dân `"message": data["message"]["text"]` nhưng `"facts": turn["facts"]` là của model (`workflow.py:778-789`). |
| 6 | `graph/workflow_validation.py`: kiểm schema không chứng minh nội dung | **CONFIRMED** | `parse_turn` (`workflow_validation.py:296-334`) chỉ kiểm khóa hợp lệ, kiểu dữ liệu, và `fact["source_message_id"] not in allowed_message_ids` (`:317-322`). Không dòng nào so `value`/`title`/`description` với văn bản tin nhắn. Tác dụng phụ: `text()` ném lỗi với chuỗi rỗng (`:18-21`, dùng ở `:331`), nên model trả `"title": ""` (đúng tinh thần "không bịa") lại làm hỏng cả lượt. |
| 7 | `runtime/backend.py`: lọc fact theo nhãn, `missing_fields` chỉ xét rỗng | **CONFIRMED** | `backend.py:263`: `reported = [fact for fact in incident["facts"] if fact.get("source") == "customer_report"]` — nhãn do chính model gán. `backend.py:275-276`: `"missing_fields": [name for name, text in (("title", title), ("description", description)) if not text]`. Chú thích `:258` nói câu đầu của description "is the resident's own words" là sai: đó là câu model viết. |
| 8 | `runtime/service.py`: chọn chế độ, truyền lịch sử, `reword()` | **PARTLY** | Chọn chế độ: `service.py:76` `agent="loop" if os.getenv("RECEPTION_AGENT", "").strip() == "loop" else "graph"`. Lịch sử `loop`: lấy từ backend mỗi lượt (`service.py:169`, `:183`); `graph`: trong checkpoint, cắt 24 mục (`workflow.py:122`, `:299`). `reword()` **chỉ chạy ở `graph`** (`service.py:286-287`), không chạy ở `loop` (`service.py:255-268`). Ở `graph` nó có thể đổi câu hỏi làm rõ (xem điểm 9). |
| 9 | `runtime/voice.py`: viết lại có thể thêm dữ kiện / biến câu hỏi thành "đã chuyển" | **PARTLY** | Chốt duy nhất: JSON hợp lệ, `len(written) > 700` (`voice.py:37`), và `reply.count("?") > written.count("?")` (`voice.py:40`). Không kiểm dữ kiện mới hay cụm "đã chuyển/đã ghi nhận". Nhiều câu hỏi cố định của graph **không có dấu "?"**, ví dụ "Bạn mô tả rõ vị trí và biểu hiện sự cố nhé." (`workflow.py:1052`), nên chốt "?" không áp dụng. Chỉ ảnh hưởng `graph`. Docstring `voice.py:4` "It cannot change the outcome" là quá lời. |
| 10 | `v3_reception_operations.py`: bên thực thi tin nội dung model cấp | **CONFIRMED** | Không có cờ "đủ chi tiết" nào; `_handoff_draft` chỉ đòi các trường khác `None` và có `assessment` (`v3_reception_operations.py:815-832`). `_update_incident` chỉ kiểm schema `DraftFields` (`:312-317`, `v3_reception.py:49-65`). `_submit_assessment` nhận `priority/severity/is_emergency/reason` của bên gọi (`:343-357`), không đối chiếu với policy của chính backend. Kiểm tra nguồn duy nhất là "id tin nhắn có thật và của cư dân" (`v3_reception_supervisor.py:397-409`). |
| 11 | `v3_reception_runtime.py`: Lễ tân thực nhận gì | **CONFIRMED** (yếu như nghi ngờ) | Lượt chạy nhận `{"id", "text", "fileIds"}` của **một** tin (`v3_resident.py:198-199`, `v3_reception_runtime.py:197`). Ngữ cảnh: 30 tin gần nhất **có chữ**, chỉ `id, role, text` (`v3_reception_runtime.py:127-133`) — không có `fileIds`, không có thời gian, không đánh dấu tin hiện tại; tin Supervisor/BQL chuyển vào được gắn nhãn `"reception"` (`:132`). Thêm `open_request` (`:135-142`) và 5 `past_requests` (`:144-151`). |

Tài liệu trái với code (ghi nhận kèm): `agent-reception/README.md` (bảng hai chế độ) viết "khẩn cấp do policy backend
xác nhận" và chú thích `tools.py:160` "The backend's policy confirms; the model only raised it" — code cho thấy đề xuất
của model tự nó đã đủ (điểm 3).

---

## 3. Ảnh có tới model không

**Không.** Chỉ có id file đi theo, và ở `loop` model còn không thấy cả id.

- `agent-reception/src/runtime/model.py:92-98` (`ainvoke`) và `:119` (`complete`) gửi `content` là chuỗi; trong
  `agent-reception/src` không có `image_url`, `base64` hay phần ảnh nào (đã tìm bằng `git grep`).
- `loop`: lịch sử là `item["text"]` (`loop.py:65-68`); backend trả lịch sử không có `fileIds`
  (`v3_reception_runtime.py:127-133`). Prompt và mô tả công cụ không nhắc tới ảnh. Model chỉ "biết" có ảnh nếu
  cư dân tự viết ra.
- Tin chỉ có ảnh: backend bắt buộc `text` khác rỗng (`v3_resident.py:54-65`), nên ứng dụng cư dân tự điền
  `const content = text.trim() || "Đính kèm ảnh phản ánh";` (`resident-app/src/services/use-connected-resident.ts:316`).
  Model nhận câu này như lời cư dân.
- `graph`: `data["message"]` (có danh sách `fileIds`) được đưa vào prompt dạng JSON (`workflow.py:263`, `:381`) —
  model thấy chuỗi id, không thấy ảnh.
- Lễ tân vẫn có thể nói như đã xem ảnh: bộ chặn câu trả lời `violations()` (`loop.py:28-48`) chỉ xét từ nội bộ, cụm
  "đã xong", "đã ghi nhận/đã chuyển", lời hứa thời gian và con số; **không có luật nào về ảnh**. Nội dung ghi vào
  ticket thì không qua bộ chặn nào.
- Nơi duy nhất ảnh thật tới model là phía Supervisor, khi BQL hỏi chuyên viên trong phiên
  (`agent-coordination/src/vinhomes/runtime.py:426-430`, `ports.py:278-280`), không phải lúc tiếp nhận.

---

## 4. Đường đi của một tin nhắn (kèm `file:dòng`)

```
[1] Ứng dụng cư dân
    resident-app/src/services/use-connected-resident.ts:294-359  send(): tải ảnh lên trước (:319-320), POST tin (:322-329)
    :316  tin chỉ có ảnh -> text = "Đính kèm ảnh phản ánh"
    :352-358  có ảnh -> tự mở nháp cục bộ ở bước "location" (UI hỏi "Sự cố xảy ra ở đâu?", Assistant.tsx:274-279)
        |
[2] Backend nhận tin   services/vinhomes-api/src/vinhomes_api/v3_resident.py:148-212
    :161-171 trùng client_message_id -> trả bản cũ, KHÔNG dispatch lại
    :172-178 giới hạn 30 tin/phút (đếm mọi tin sender_kind='user', gồm cả bản nháp ticket)
    :195-199 background.add_task(dispatch_turn, ...)  (trong tiến trình, không có hàng đợi bền)
        |
[3] Mở lượt chạy + gọi runtime   v3_reception_runtime.py:184-216
    :190 start_run -> token ủy quyền 600 giây (reception_delegation.py:103-170)
    :192-198 POST {reception_url}/v1/turns, timeout=180
    :212-214 không nhận 200 -> ghi UNAVAILABLE_REPLY;  :113-118 mỗi tin cư dân chỉ một câu trả lời
        |
[4] Runtime Lễ tân   agent-reception/src/runtime/service.py:235-297
    :251 khóa theo hội thoại (trong bộ nhớ);  :255 loop  /  :269 graph
    loop:  agent_turn (:165-184): GET context, get_verified_resident_context, GET catalog, POST policy
           policy khẩn cấp -> emergency_request (:176-179); còn lại -> run_agent (loop.py:62-108, tối đa 6 bước)
    graph: run_turn (:145-162) -> receive_message -> assess_request -> ... (workflow.py), rồi reword (:286-287)
    :263-265 / :292-294  POST /internal/reception/chats/{id}/replies
        |
[5] Tạo và bàn giao ticket (5 lệnh HTTP rời nhau, mỗi lệnh một giao dịch)
    loop:  tools.py:111-131  create_ticket_draft -> update_ticket_incident -> submit_ticket_assessment
           -> resolve_management_destination -> handoff_ticket
    graph: workflow.py:566-678 qua runtime/backend.py:182-334
    backend: reception_runtime_api.py:46-51 -> v3_reception_operations.py:1203-1232 (execute, biên nhận idempotency :146-194)
             bản nháp là một dòng messages của cư dân: v3_reception.py:131-142
             _handoff_draft :802-1097 -> commit_draft (v3_reception.py:177-229) -> create_resident_ticket (v3_resident.py:225-427)
             gắn ảnh :902-905 (v3_conversation_images.py:310-372);  tạo agent_teams 'queued' :977-1007
             tin V2 ticket_submitted :1029-1082 -> submit_reception_message (v3_reception_supervisor.py:481-595)
        |
[6] Supervisor   agent-coordination/src/vinhomes/runtime.py
    :577-583 vòng lặp;  :523-529 round = poll rồi work cho tới hết
    :193-218 poll -> backend GET /inbox (v3_coordination.py:216-228) -> chép vào hộp thư SQLite cục bộ
    :470-521 work: nhận 1 tin, thuê 60 giây;  :220-271 handle
    verify (v3_coordination.py:238-261) -> receive() phát "accepted" (supervisor/reception_flow.py:98-99)
    -> resume(): mở phòng, giao việc, chạy chuyên viên, lập phương án (supervisor/service.py:629-704, ports.py:447-490)
        |
[7] Tin đầu tiên quay lại cư dân   v3_coordination.py:264-284
    :62 RESIDENT_FACING = {information_requested, plan_approval_requested, completed, failed, cancelled}
    "accepted"/"in_progress" chỉ vào phòng BQL (:277-279); cư dân chỉ nhận khi Supervisor hỏi hoặc BQL đã duyệt phương án
    Cư dân trả lời bằng biểu mẫu ở trang yêu cầu: resident-app/src/app/App.tsx:530-531 -> v3_resident_interactions.py:40-82
```

---

## 5. Các điểm lỗi thực, xếp theo mức độ

Ký hiệu chế độ: **[loop]**, **[graph]**, **[cả hai]**, **[app]**, **[supervisor]**, **[backend]**.

### Mức 1 — sai nội dung hoặc mất an toàn, xảy ra trên đường chính

**F1. [loop] Không có cổng nội dung trước khi tạo yêu cầu; mô tả do model viết vào thẳng ticket.**
- Người dùng thấy: cư dân viết "Nhà tắm của tôi bị rò nước", Lễ tân trả "đã ghi nhận và chuyển"; BQL và Supervisor
  đọc ticket có tiêu đề/mô tả chứa chi tiết cư dân chưa hề nói.
- Bằng chứng: điểm 1, 2 ở mục 2 (`prompt.py:11-12`, `tools.py:143-157`, `tools.py:119-120`). Mô tả đó cũng là nội
  dung gửi Supervisor: `message=str(call.input.get("handoff_message") or snapshot["description"])`
  (`v3_reception_operations.py:1043`). Thêm một nguồn chi tiết lạ: tiêu đề 5 yêu cầu cũ của chính cư dân nằm trong
  system prompt (`prompt.py:56-57`) kèm chỉ dẫn "ghi điều này vào description" (`prompt.py:23-24`); và `violations()`
  coi cả system prompt là nguồn hợp lệ (`loop.py:70`).
- Test: không có test nào cho `Toolbox` thật (`src/agent/tools.py`) ngoài đường khẩn cấp
  (`tests/runtime/test_emergency_guidance.py`). `test_loop.py` dùng `Toolbox` giả.
- Sửa nhỏ nhất: trong `_file_request`, không nhận `description` của model làm nguồn — ghép mô tả từ nguyên văn các tin
  cư dân trong lượt này (backend đã có `history`), `title` cắt từ đó; và từ chối với `error: "clarify_first"` khi tin
  cư dân chưa nêu vật/vị trí cụ thể.

**F2. [graph] Backend ép `start_ticket` cho mọi "sự cố", graph không thể hỏi lại.**
- Người dùng thấy: giống F1 — bàn giao ngay, không có câu hỏi làm rõ, dù model đã liệt kê `missing_information`.
- Bằng chứng: `v3_reception_runtime.py:78-79` `staff_required = ... or proposal.get("intent") in {"incident", "service_request"}`
  và `:86` `"missing_information": []`. `agent-reception/src/graph/assessment.py:116-117`
  `elif policy["staff_required"]: action = "start_ticket"` đứng **trước** nhánh `missing_information` (`:118-123`).
  Đã chạy riêng `decide_request` với `intent=incident`, `proposed_action=ask_clarification`,
  `missing_information=[một câu hỏi]`, `staff_required=True` → kết quả `start_ticket`; đổi `staff_required=False` →
  `ask_clarification`. Sau đó `_collect_incident_details` lấy title/description của model (điểm 5) và
  `missing_fields` chỉ xét rỗng (điểm 7).
- Test: `tests/graph/test_assessment.py::test_clarification_reassesses_with_question_and_previous_message_history`
  chỉ qua được vì `Policy()` của test mặc định `staff_required=False` — giá trị backend thật không bao giờ trả cho sự cố.
- Sửa nhỏ nhất: trong `decide_request` đưa nhánh `missing_information` lên trước `staff_required` (trừ khẩn cấp và
  `explicit_staff_request`).

**F3. [app] Hai đường tạo yêu cầu chạy song song: biểu mẫu nháp cục bộ và Lễ tân.**
- Người dùng thấy: gửi "Nhà tắm của tôi bị rò nước" kèm ảnh → giao diện hiện "Sự cố xảy ra ở đâu? Nhập tầng, căn hộ
  hoặc vị trí cụ thể." **đồng thời** Lễ tân trả "đã chuyển". Cư dân gõ vị trí → Lễ tân đáp "đã ghi nhận" (không ghi vào
  ticket). Thẻ xem lại hiện ra, bấm gửi → lỗi tiếng Anh "This chat already has a ticket". Nút "Báo sự cố" cũng đi đúng
  vòng này.
- Bằng chứng: `use-connected-resident.ts:352-358` (`else if (photos.length) changeDraft({ step: "location", ... })`),
  `:332-338` ("Báo sự cố" vừa gửi chữ này cho Lễ tân vừa mở nháp), `Assistant.tsx:274-279` (câu hỏi vị trí),
  `use-connected-resident.ts:365-400` (`submit` gọi `POST /resident/chats/{id}/tickets`),
  `v3_resident.py:254-259` (`raise HTTPException(409, "This chat already has a ticket")`).
  Nếu biểu mẫu thắng cuộc đua thì ticket chỉ được `ensure_session` tạo phiên `queued` (`v3_session.py:61-88`) mà
  **không có** tin `ticket_submitted`; hộp thư Supervisor chỉ đọc `vh_reception_supervisor_messages`
  (`v3_coordination.py:220-226`) nên phiên đó không bao giờ được xử lý.
- Test: không có (`resident-app/tests/` chỉ có `auth-service`, `conversations`, `resident-service`).
- Sửa nhỏ nhất: khi đã nối backend có Lễ tân, bỏ nháp cục bộ (`changeDraft`) trong `send()`; để Lễ tân là nơi duy nhất
  hỏi vị trí.

**F4. [loop] Đường khẩn cấp báo sai hoặc bỏ rơi cư dân.**
- (a) Báo "đã chuyển ở mức khẩn cấp" khi chưa tạo được gì. `tools.py:169` đặt `self.emergency = True` **ngay dòng đầu**,
  trước mọi kiểm tra; `:172-173` trả `{"error": "no_single_verified_home"}`, `:178-179` trả lỗi của `_file`; lỗi backend
  bị bắt ở `tools.py:87-90`. Sau đó `loop.py:85-87` `if toolbox.emergency: return EMERGENCY_REPLY`.
  Cư dân đọc "Mình đã chuyển yêu cầu của bạn đến Ban quản lý ở mức khẩn cấp." trong khi BQL không nhận được gì.
- (b) Cư dân có 0 hoặc từ 2 căn hộ xác minh không báo khẩn cấp được: `_home(None)` trả `None` khi nhiều căn
  (`tools.py:136`). Đi theo từ khóa: `service.py:178-179` → `FAILED_REPLY` ("Xin lỗi, tôi chưa xử lý được tin nhắn này.
  Bạn thử lại sau ít phút…"); đi theo model: rơi vào (a).
- (c) Yêu cầu đang `resolved` (chờ cư dân xác nhận) vẫn là `open_request` (`v3_reception_runtime.py:141`
  `t.status not in ('closed','cancelled')`), nhưng backend từ chối nâng khẩn cấp
  (`v3_reception_operations.py:687-688` `409 "A final ticket cannot be emergency-escalated"`). Ở đường từ khóa,
  `emergency_request` được gọi ngoài `Toolbox.call` (`service.py:178`) nên ngoại lệ thành `FAILED_REPLY`
  (`service.py:261-262`). Cư dân báo "có mùi gas" trong hội thoại đó nhận câu "thử lại sau ít phút".
- (d) Model tự nâng khẩn cấp luôn thành công (điểm 3): ticket `critical` với tiêu đề/mô tả do model viết
  (`tools.py:170`, `:175`), trả lời bằng câu cố định, không qua `violations()`.
- (e) Ticket khẩn cấp mới tạo không có sự kiện `ticket.emergency_escalated`: tạo ra đã `is_emergency`, nên lệnh nâng
  trả `alreadyEscalated` với `notificationQueued: False` (`v3_reception_operations.py:707-719`); BQL chỉ có thông báo
  `ticket.created` thường (`v3_resident.py:382-405`).
- Test: `tests/runtime/test_emergency_guidance.py` chỉ có ca thành công một căn hộ;
  `tests/agent/test_loop.py::test_emergency_is_acknowledged_with_the_fixed_sentence` dùng `Toolbox` giả đặt
  `emergency = True` bất kể kết quả. Backend không có test cho `escalate_emergency` của Lễ tân.
- Sửa nhỏ nhất: chỉ đặt `self.emergency = True` sau khi `_file`/`escalate_emergency` thành công; khi không tạo được thì
  trả câu cố định kiểu "chưa chuyển được, gọi ngay số an ninh" thay cho `FAILED_REPLY`; nhiều căn hộ thì vẫn tạo ticket
  ở căn đầu và ghi rõ cần xác nhận căn.

**F5. [cả hai] Ảnh: model không thấy, và ảnh dễ rơi khỏi ticket.**
- Người dùng thấy: Lễ tân có thể nói/ghi như đã xem ảnh (mục 3). Nếu sau này sửa cho Lễ tân hỏi lại trước khi tạo yêu
  cầu, ảnh gửi ở tin đầu **sẽ không vào ticket** ở `loop`. Ảnh gửi sau khi đã có yêu cầu không vào ticket; BQL cũng
  không thấy trong phần hội thoại.
- Bằng chứng: `tools.py:120` `"file_ids": self.message.get("fileIds", [])` (chỉ tin hiện tại); lịch sử không có
  `fileIds` (`v3_reception_runtime.py:127-133`); `loop` không có công cụ bổ sung thông tin (`tools.py:30-49`);
  màn BQL đọc hội thoại chỉ lấy `id, seq, sender_kind, text` (`v3_session.py:106-110`).
  Ở `graph`, `_append_ticket_information` trả `"linked_file_ids": value.get("file_ids", [])` kể cả khi backend từ chối
  409 và `delivered = False` (`runtime/backend.py:371-381`), nên graph đánh dấu ảnh "đã gắn" (`workflow.py:1112-1118`)
  trong khi không có gì được gắn.
- Test: `tests/graph/test_image_references.py::test_image_after_handoff_is_appended_to_same_ticket` dùng cổng giả luôn
  trả `delivered: True`. Không có test `loop` nào có ảnh.
- Sửa nhỏ nhất: backend trả `fileIds` trong `history`; `_file` gom mọi `fileIds` của tin cư dân chưa gắn trong hội
  thoại; thêm một lệnh gắn ảnh vào ticket đang mở (đã có `attach`, `v3_conversation_images.py:310`).

### Mức 2 — cư dân/BQL bị bỏ lửng hoặc nhận câu trả lời sai với thực tế

**F6. [supervisor/backend] Sau bàn giao, mọi kiểu dừng của Supervisor đều im lặng với cư dân.**
- Người dùng thấy: cư dân đọc "đã chuyển" rồi không còn gì. BQL thấy ticket, phiên ở `queued` hoặc `running` với
  `pauseReason` trong phần quan sát.
- Bằng chứng: `v3_coordination.py:62`, `:280-284` (chỉ 5 loại tin tới cư dân); không có chuyên viên cho danh mục →
  `return self._pause("no_specialist_available")` (`ports.py:448-450`); chưa cấu hình model → `:452-453`; model lỗi →
  `SupervisorError("model_timeout"/"model_unavailable")` (`supervisor/planner.py:79-82`) → `pause(state, exc.code)`
  (`supervisor/service.py:697`); trạng thái chỉ ghi "Observability only" (`v3_coordination.py:390-395`). Tin bị từ chối
  dứt khoát → `park` (`runtime.py:510-513`), chuyển `status='blocked'`, không tự thử lại
  (`persistence/sql.py:167-178`), chỉ lộ ra ở `/sessions` dưới dạng một con số (`runtime.py:145`, `:155`).
- Test: `tests/runtime/test_resident_chat_e2e.py::test_the_supervisor_receives_the_ticket_reception_handed_over` khẳng
  định đúng sự im lặng này (mục 6).
- Sửa nhỏ nhất: khi phiên `paused` vì lý do không tự hồi phục, hoặc tin bị `park`, backend ghi một thông báo cho BQL
  (đã có bảng `notification_deliveries`).

**F7. [supervisor] Một worker, một tin một lúc, cho mọi ticket.**
- Người dùng thấy: ticket thứ hai nằm `queued` cho tới khi ticket thứ nhất phân tích xong; câu trả lời của cư dân và
  quyết định của BQL cho ticket khác cũng phải chờ.
- Bằng chứng: `runtime.py:523-529` (`await self.poll()` rồi `while await self.work(): pass`), `:472` nhận một tin,
  `persistence/sql.py:118` `ORDER BY rowid LIMIT 1`; một tin có thể chạy tới `MAX_STEPS = 40` bước
  (`runtime.py:62`), mỗi lượt chuyên viên tới 150 giây (`:65`), planner 60 giây (`ports.py:414`). Trong lúc đó
  `poll()` không chạy. `handle` còn nạp lại **mọi** checkpoint cho mỗi tin (`runtime.py:232`, `:141-155`).
- Test: không có test tải/đồng thời.
- Sửa nhỏ nhất: tách việc gửi "accepted" khỏi phần phân tích (trả `SETTLE_SECONDS` sau bước nhận) để tin mới được
  nhận ngay; về lâu dài mới cần nhiều worker.

**F8. [loop] Cư dân trả lời câu hỏi của Supervisor bằng chat thì câu trả lời không tới Supervisor.**
- Người dùng thấy: câu hỏi của Supervisor hiện trong chat như lời Lễ tân; cư dân trả lời ngay tại đó; Lễ tân đáp
  "đã ghi nhận"; phiên vẫn chờ mãi. Câu trả lời chỉ được nhận nếu cư dân vào trang yêu cầu và điền biểu mẫu.
- Bằng chứng: câu hỏi được ghi vào hội thoại cư dân (`v3_coordination.py:280-284`); `loop` không có công cụ gửi
  `information_provided` (`tools.py:30-49`); prompt bảo "chỉ cần xác nhận đã ghi nhận" (`prompt.py:20`); bộ chặn cho
  phép vì `acted` đúng khi có `open_request` (`tools.py:69-71`, `loop.py:36-37`); biểu mẫu nằm ở trang chi tiết yêu
  cầu (`resident-app/src/app/App.tsx:530-531`).
- Test: `tests/agent/test_loop.py::test_guard_rules` (`:116-119`) coi "Mình đã ghi nhận…" là hợp lệ chỉ vì
  `acted = True`.
- Sửa nhỏ nhất: `conversation_context` trả thêm `pending_kind`; khi đang có câu hỏi chờ, `agent_turn` gửi thẳng tin
  cư dân thành `information_provided` (đường `v3_resident_interactions.respond` đã có) trước khi gọi model.

**F9. [backend] Tin V2 theo sau dựng từ ảnh chụp cũ nên bị 409 sau khi ticket đổi ưu tiên.**
- Người dùng thấy: sau khi BQL phân loại lại (đổi ưu tiên/mức độ) hoặc sau khi Lễ tân nâng khẩn cấp, cư dân không gửi
  được đề nghị hủy qua Lễ tân, và biểu mẫu trả lời Supervisor/duyệt phương án báo lỗi.
- Bằng chứng: `tools.py:198-202` (`**submitted`), `runtime/backend.py:358-364` (`**submitted`),
  `v3_resident_interactions.py:67-69` (`{**original, ...}`) đều chép `request.priority/severity/is_emergency` của lúc
  bàn giao; `_check_snapshot` so từng trường với ticket **hiện tại** và ném
  `409 "V2 ticket snapshot is stale or mismatched: ..."` (`v3_reception_supervisor.py:279-318`). Hai nơi đổi các
  trường này sau khi tạo: `v3_reception_operations.py:722` và `v3_triage.py:232`.
- Test: không thấy test nào cho "phân loại lại rồi mới trả lời/hủy".
- Sửa nhỏ nhất: khi dựng tin theo sau, lấy khối `request` từ ticket hiện tại thay vì từ `ticket_submitted`.

**F10. [loop] Ticket đã tạo nhưng cư dân nhận câu "chưa có thông tin" hoặc "chưa xử lý được".**
- Người dùng thấy: thẻ yêu cầu xuất hiện, nhưng lời Lễ tân là "Mình chưa có thông tin chính thức về việc này…" hoặc
  "Xin lỗi, tôi chưa xử lý được tin nhắn này. Bạn thử lại…". Thử lại thì bị "đã có yêu cầu đang mở".
- Bằng chứng: câu trả lời sau khi tạo bị bộ chặn loại hai lần, hoặc hết 6 bước → `return SAFE_REPLY`
  (`loop.py:102-108`); model lỗi ở bước viết câu trả lời → `ModelUnavailable` (`model.py:129-130`) →
  `reply = FAILED_REPLY` (`service.py:261-262`). `agent_turn` trả `toolbox.filed_code` nhưng nơi gọi bỏ đi
  (`service.py:259` `reply, _ = ...`). Chỉ cần câu trả lời có một con số không nằm trong nguồn (`loop.py:42-47`) hay
  cụm "trong vòng" (`loop.py:17`) là bị loại.
- Test: `tests/agent/test_loop.py::test_the_loop_stops_after_its_step_budget` khẳng định `SAFE_REPLY` bất kể đã làm gì.
- Sửa nhỏ nhất: nếu `toolbox.filed_code` có giá trị mà câu trả lời không dùng được thì trả câu cố định "Mình đã ghi
  nhận và chuyển yêu cầu của bạn đến Ban quản lý."

**F11. [loop] Chuỗi tạo yêu cầu 5 bước không nguyên tử; thử lại trong cùng lượt luôn bị 409.**
- Người dùng thấy: Lễ tân báo không tạo được; cư dân phải nhắn lại. Mỗi lần hỏng để lại một bản nháp mồ côi trong hội
  thoại (là một dòng `messages` của chính cư dân).
- Bằng chứng: khóa idempotency chỉ theo (hội thoại, id tin, tên bước): `tools.py:73-77`; backend từ chối cùng khóa
  khác nội dung: `v3_reception_operations.py:172-173` `raise HTTPException(409, "IDEMPOTENCY_KEY_REUSED")`. Vậy lần gọi
  `file_request` thứ hai trong cùng lượt với `category_code`/`title` khác sẽ hỏng ở bước `incident`.
  Danh mục không có vùng phủ quản lý → `{"available": False, "missingFields": ["management_coverage"]}`
  (`v3_reception_operations.py:465-470`) → Lễ tân nhận `no_management_unit` với ghi chú "Chưa xác định được Ban quản
  lý phụ trách căn hộ này." (`tools.py:123-124`) — sai nguyên nhân: lỗi ở danh mục, không ở căn hộ.
  Bản nháp: `v3_reception.py:131-142` (`sender_kind='user'`, `visibility='customer'`), và bị đếm vào giới hạn 30
  tin/phút của cư dân (`v3_resident.py:172-178`).
- Test: backend có `test_v3_agent_database.py::test_reception_draft_handoff_and_durable_retry` cho thử lại **cùng nội
  dung**; không có test cho "thử lại khác nội dung trong cùng lượt" hay cho bản nháp mồ côi.
- Sửa nhỏ nhất: thêm số lần thử vào khóa (`step + ":" + n`) cho các bước sau `draft`; đổi ghi chú lỗi thành "danh mục
  này chưa có Ban quản lý phụ trách, chọn mã khác".

**F12. [loop] Không kiểm tra họ tên/số điện thoại trước khi tạo; backend từ chối mà không nói lý do.**
- Người dùng thấy: cư dân chưa có số điện thoại trong hồ sơ nhắn bao nhiêu lần cũng không tạo được yêu cầu, không ai
  bảo họ cập nhật hồ sơ.
- Bằng chứng: backend trả `accepted: False, missingFields: ["verified_resident_name", "verified_resident_phone"]`
  (`v3_reception_operations.py:846-855`); `loop` đổi thành `raise OperationRejected("HANDOFF_REJECTED")`
  (`tools.py:127-128`) → model chỉ thấy `{"error": "refused", "detail": "HANDOFF_REJECTED"}` (`tools.py:87-88`).
  `graph` thì có kiểm tra này (`runtime/backend.py:200-202`).
- Test: không có.
- Sửa nhỏ nhất: trả `handoff.get("missingFields")` trong kết quả công cụ, kèm ghi chú cho từng trường.

**F13. [graph] Câu "cần người có thẩm quyền xem xét" không báo cho ai cả, và rất dễ rơi vào.**
- Người dùng thấy: "Yêu cầu cần người có thẩm quyền xem xét; chưa có xác nhận xử lý hoàn tất." — nhưng không có
  người nào được báo.
- Bằng chứng: `_review` chỉ đổi trạng thái và câu trả lời (`workflow.py:175-183`); `_human_review` chỉ chờ tin tiếp
  (`workflow.py:1284-1288`); `service.py:269-294` không có nhánh nào gửi gì cho BQL. Các đường dẫn tới đây: model lỗi
  hoặc trả JSON sai (`workflow.py:406-412`, `:590-596`); model trả `"title": ""` hoặc sai `source_message_id`
  (điểm 6); model đề xuất danh mục không hợp lệ (`runtime/backend.py:242-243` → `workflow.py:1242-1247`); câu hỏi lặp
  lại hoặc đã hỏi đủ 4 lần **trong cả đời hội thoại** (`workflow.py:186-190`, `workflow_contracts.py:118`; bộ đếm
  không bao giờ đặt lại); không định tuyến được (`workflow.py:1077-1078`).
- Test: `tests/graph/test_workflow_failures.py::test_unresolved_route_and_repeated_questions_stop` và
  `::test_not_applied_backend_error_requires_review` khẳng định câu này là kết quả đúng.
- Sửa nhỏ nhất: khi vào `_review`, gọi lệnh mở phiên hỏi BQL đã có (`/internal/reception/chats/{id}/inquiries`) với
  nguyên văn tin cư dân; đặt lại `question_attempts` sau mỗi lần bàn giao.

### Mức 3 — hạ tầng và trường hợp biên

**F14. [graph] Tin bổ sung có một fact `agent_inference` thì cả tin bị từ chối.** `_follow_up` gửi nguyên `facts` của
model (`runtime/backend.py:364`), không lọc như lúc tạo (`:263`); backend đòi `agent_inference` phải dẫn tới tin của
agent (`v3_reception_supervisor.py:422-423`, kiểm ở `:374-381` trước cả kiểm "đang chờ thông tin"); lỗi 422 không nằm
trong nhánh bắt 409 (`runtime/backend.py:374-376`) → `_review`. Test: không có (ca "có vẻ" của `fake_llm.py:35-37` chỉ
phủ tin đầu). Sửa: lọc `customer_report` trong `_follow_up`.

**F15. [backend] Gửi lượt chạy bằng `BackgroundTasks`, không có hàng đợi bền.** Tiến trình API dừng giữa lúc đã lưu
tin và lúc gọi runtime thì tin đó không bao giờ được trả lời (`v3_resident.py:195-199`); gửi lại cùng
`client_message_id` chỉ trả bản cũ (`:161-171`), không gọi lại. Ứng dụng hiện "Trợ lý đang trả lời…" tối đa 180 giây
rồi thôi (`use-connected-resident.ts:139-142`). Test: không có. Sửa: khi mở lượt mới của hội thoại, nếu còn tin cư dân
chưa có câu trả lời thì ghi `UNAVAILABLE_REPLY` cho tin đó.

**F16. [backend/loop] Quá 180 giây thì backend ghi câu "tạm thời chưa phản hồi" và vô hiệu token giữa chừng.**
`timeout=180` (`v3_reception_runtime.py:192`); một lượt `loop` có thể dài hơn: 6 bước model × 40 giây
(`loop.py:10`, `model.py:69`) cộng các lệnh backend 20 giây (`runtime/backend.py:95`), và lượt thứ hai của cùng hội
thoại còn phải chờ khóa (`service.py:251`). Khi quá hạn: `finish_run(..., delivered=False)` đặt lượt thành `failed`
(`reception_delegation.py:173-180`), mọi lệnh sau của runtime bị 403 vì `authority` đòi `r.status='running'`
(`reception_delegation.py:76`) — có thể dừng giữa chuỗi 5 bước của F11; câu trả lời thật đến muộn bị bỏ
(`v3_reception_runtime.py:113-118`). Test: `test_resident_is_told_when_the_runtime_is_down` chỉ phủ trường hợp runtime
tắt hẳn. Sửa: đặt tổng thời hạn một lượt ở runtime thấp hơn 180 giây.

**F17. [backend/supervisor] Bàn giao được chấp nhận nhưng Supervisor không xác minh được.** Điều kiện bàn giao
(`v3_reception_operations.py:553-599`) chỉ cần Supervisor đang hoạt động và có bản phát hành; `team_authority` còn
đòi `execution_principals ... kind='workspace_service'` đang hoạt động (`v3_coordination.py:112-117`), thiếu thì 403
→ `Refused(403)` → không phải 409 nên ném lại (`runtime.py:238-240`) → `park` (`runtime.py:510-513`). Cư dân đã được
báo "đã chuyển". Test: không có cho trường hợp thiếu principal. Sửa: `_resolve_destination` kiểm thêm điều kiện này
và trả `available: False`.

**F18. [cả hai] Model lỗi/429/quá giờ: không có lần thử lại nào.** `model.py:105-107`, `:129-130` gộp mọi lỗi thành
`ModelUnavailable`; `loop` → `FAILED_REPLY` (`service.py:261-262`); `graph` → câu của F13. Test: không có. Sửa: thử
lại một lần với 429/5xx trước khi bỏ cuộc.

**F19. [loop] Sự cố có thể bị chuyển thành "câu hỏi" không có ticket.** `ask_management` chỉ cần đã gọi
`search_knowledge` (`tools.py:206-209`); backend mở phiên hỏi với nguyên văn tin cư dân (`v3_session.py:304-365`) —
không ticket, không ảnh, không danh mục — và Lễ tân được phép nói "đã chuyển" vì `forwarded` (`tools.py:69-71`).
Test: không có ca nào kiểm "sự cố không được đi đường này". Sửa: từ chối `ask_management` khi `policy.staff_required`.

**F20. [loop] Hai tin gửi liền nhau: lượt của tin đầu trả lời cho tin sau.** Lịch sử không bị chặn ở tin của lượt
(`v3_reception_runtime.py:127-131`, không có điều kiện `seq <=`), mà `run_agent` trả lời "the last resident message
in `history`" (`loop.py:63`) trong khi `toolbox.message` (id, ảnh, policy) vẫn là tin đầu (`service.py:172-175`).
Kết quả: hai câu trả lời cho cùng một ý, ảnh của tin sau không được gắn. Test: không có. Sửa: thêm
`and seq <= (seq của tin đang xử lý)` vào truy vấn lịch sử.

**F21. [supervisor] Vòng lặp chính có thể chết im lặng.** `loop()` không có `try` (`runtime.py:577-583`); `round()`
chỉ bắt `AdapterError` quanh `poll()` (`runtime.py:524-527`), còn `self.store.claim` nằm ngoài `try` của `work()`
(`runtime.py:472`). Một ngoại lệ khác loại là tác vụ dừng hẳn, trong khi `/health` vẫn trả `ok`
(`runtime.py:592-595`) và `/ready` chỉ thử đọc hộp thư (`:597-602`). Test: không có. Sửa: bọc `runtime.round()` trong
`try/except Exception` có ghi log.

**F22. [graph] Đổi `WORKFLOW_VERSION` làm chết mọi hội thoại cũ.** `workflow.py:1312-1316` ném
`WORKFLOW_MIGRATION_REQUIRED` → `service.py:272-274` → `FAILED_REPLY` mãi mãi, câu "thử lại sau ít phút" là sai.
Test: `tests/graph/test_assessment.py::test_old_python_topology_is_rejected_without_reset` khẳng định hành vi này.
Sửa: với mã lỗi này trả câu "mở cuộc trò chuyện mới".

---

## 6. Test đang hợp thức hóa hành vi sai

| Test (đường dẫn::tên) | Hợp thức hóa điều gì |
|---|---|
| `agent-reception/tests/graph/test_image_references.py::test_image_only_message_is_valid_and_reaches_ticket` (`:67-79`) | Tin `"text": ""` chỉ có ảnh; model (kịch bản) trả tiêu đề "Rò nước tại bếp", mô tả "Vòi nước tại bếp bị rò." và fact `location=bếp` gắn nhãn `customer_report` dẫn tới chính tin không có chữ; test đòi phải bàn giao. |
| `agent-reception/tests/runtime/fake_llm.py` (`assessment` `:11-23`, `turn` `:26-38`, `agent_step` `:47-75`) | Model giả cho cả bộ e2e: thấy "hỏng/rò/sửa…" là `file_request` ngay, `missing_information` luôn rỗng. Không có nhánh hỏi lại. |
| `agent-reception/tests/runtime/test_resident_chat_e2e.py::test_incident_chat_creates_a_ticket_management_can_work_on` (`:41-68`) | Một tin là có ticket; chỉ kiểm tiêu đề bắt đầu bằng lời cư dân vì model giả chép nguyên văn — không phản ánh model thật. |
| `…/test_resident_chat_e2e.py::test_a_model_guess_among_the_facts_does_not_lose_the_request` (`:71-74`) | "Ổ điện bếp bị hỏng, có vẻ do chập." → mục tiêu của test là phỏng đoán của model **không được cản** việc tạo yêu cầu. |
| `…/test_resident_chat_e2e.py::test_the_supervisor_receives_the_ticket_reception_handed_over` (`:149-167`) | Phiên dừng ở `planner:no_specialist_available` và "the resident hears from Reception once" được coi là kết quả đúng (F6). |
| `agent-reception/tests/agent/test_loop.py::test_claiming_to_have_passed_something_on_requires_a_tool_that_did` (`:101-109`) | Lịch sử là câu hỏi phí gửi xe, vậy mà `file_request` với "Hàng xóm gây ồn / Khoan tường sau 22 giờ" được chấp nhận: nội dung yêu cầu không cần có trong hội thoại. Còn dạy rằng bị nhắc "chưa gọi công cụ" thì cách sửa là **tạo yêu cầu**, không phải hỏi lại. |
| `…/test_loop.py::test_guard_rules` (`:112-125`) | "Mình đã ghi nhận vòi nước rò ở căn 1201." hợp lệ chỉ vì `acted = True` (F8). |
| `…/test_loop.py::test_emergency_is_acknowledged_with_the_fixed_sentence` (`:89-91`) và `Toolbox` giả (`:22-23`) | Cứ gọi `report_emergency` là `emergency = True`, bất kể kết quả (F4a). |
| `…/test_loop.py::test_the_loop_stops_after_its_step_budget` (`:94-98`) | `SAFE_REPLY` là kết quả đúng dù trước đó đã làm gì (F10). |
| `agent-reception/tests/graph/test_assessment.py::test_policy_and_active_ticket_override_llm` (`:99-105`) | `staff_required=True` → `start_ticket`; không có hàng nào thử `staff_required` cùng `missing_information` (F2). |
| `…/test_assessment.py::test_clarification_reassesses_with_question_and_previous_message_history` (`:163-191`) | Hỏi lại "chạy được" nhờ `Policy()` giả có `staff_required=False`, khác backend thật. |
| `agent-reception/tests/graph/workflow_fixture.py` (`:298-312`, `:314-334`) | Policy và model giả của cả bộ graph: `missing_information: []`, sự cố → `start_ticket`. |
| `services/vinhomes-api/tests/test_v3_agent_database.py::test_reception_policy_and_reply_are_backend_decisions` (`:213-215`, `:220-221`) | "Vòi nước bị chảy nhỏ giọt" (không có vị trí) + `intent: incident` → `staff_required`; và chỉ cần `proposed_action: emergency_handoff` là `emergency` đúng (F2, F4d). Tên test nói "backend decisions" nhưng cả hai đều do model quyết. |
| `agent-reception/tests/graph/test_image_references.py::test_image_after_handoff_is_appended_to_same_ticket` (`:82-96`) | Cổng giả luôn `delivered: True`; bộ nối thật báo ảnh đã gắn cả khi bị 409 (F5). |
| `agent-reception/tests/evals/run_live.py` (`converse` `:57-77`, `JUDGE_PROMPT` `:40-48`) + `live_conversations.vi.json` | Chỉ chấm lời thoại; không lấy tiêu đề/mô tả ticket để so với lời cư dân; không kịch bản nào gửi `file_ids`; không có ca "có phòng + hiện tượng nhưng chưa rõ vật bị hỏng". |

---

## 7. Những gì chưa xác minh được

- **Chưa tái hiện triệu chứng.** Không gọi model nên không biết `gpt-6-luna` thực tế viết gì; F1/F2 chỉ chứng minh
  code không ngăn.
- **Chế độ đang chạy.** Yêu cầu kiểm tra nói stack cục bộ và Docker chạy `loop`. Mặc định trong code và compose là
  `graph` (`service.py:76`, `deploy/vinhomes/compose.yml:95`, `agent-reception/.env.example:14`). Giá trị thật nằm
  trong `agent-reception/.env` và `deploy/vinhomes/deployment.env`, hai file này không được mở.
- **Giả thuyết nguồn của chi tiết bịa**: tiêu đề các yêu cầu cũ của tài khoản thử (`yeu_cau_truoc_day`) lọt vào mô tả.
  Cơ chế có trong code (`prompt.py:23-24`, `:56-57`); dữ liệu thật của tài khoản thì chưa xem.
- **F9, F16, F17**: suy ra từ đọc code hai phía, chưa chạy. F17 còn phụ thuộc dữ liệu seed có principal
  `workspace_service` hay không.
- **Nâng khẩn cấp một ticket đã bàn giao có làm kẹt phiên Supervisor không**: `record_event` tăng `tickets.version`
  (`v3_mutations.py:101-104`), kết quả của Supervisor mang phiên bản cũ sẽ bị
  `409 "Supervisor result is stale…"` (`v3_reception_supervisor.py:660-668`) và `_dispatch` chuyển thành `pause`
  (`supervisor/service.py:581-589`). Chưa lần hết mọi chỗ Supervisor làm mới `ticket_version`
  (`supervisor/service.py:169-171`, `runtime.py:245-251`) nên chưa kết luận.
- **Tin độc trong hộp thư Supervisor**: `store.accept` ném `conflict` khi cùng khóa khác nội dung
  (`persistence/sql.py:101-104`) và làm hỏng cả vòng `poll` (`runtime.py:524-527`). Chưa xác minh backend có trả cùng
  một mục với nội dung thay đổi giữa hai lần đọc hay không.
- **Mất SQLite ở `graph`** (checkpoint và `DraftStore`, `service.py:193-194`): compose có volume `reception-state`
  (`deploy/vinhomes/compose.yml`), stack cục bộ thì chưa kiểm. Hệ quả khi mất (hội thoại đã có ticket không tiếp tục
  được) mới lần theo một phần.
- **Graph không nhận sự kiện từ Supervisor**: `BackendOperations` không có `_get_supervisor_event` và
  `_respond_supervisor_interaction` (`runtime/backend.py`), nên các nhánh `pending_interaction` của graph có vẻ là mã
  chết; chưa chạy để khẳng định.
- **`plan_required: False`** ở cả hai chế độ (`tools.py:126`, `runtime/backend.py:324`) so với luồng "Supervisor đề
  xuất phương án → BQL duyệt → cư dân duyệt": chưa lần xem cờ này ảnh hưởng gì tới việc lưu phương án.
- **Ảnh có bị tải trùng** khi cư dân gửi biểu mẫu sau khi đã gửi ảnh trong chat
  (`use-connected-resident.ts:320`, `:376`): `store()` có khóa idempotency theo ảnh (`:55-61`), chưa lần hết.
- Không chạy bộ test nào: Python hệ thống thiếu `langgraph.checkpoint.sqlite`; không dùng `.venv` để tránh đụng
  môi trường của phiên khác.
