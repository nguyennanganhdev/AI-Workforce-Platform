# Báo cáo: 4 vấn đề của platform Workforce và kế hoạch xử lý

Ngày 13/10/2026 · Nhánh `develop2@f495ec00` · Người đọc: PM và trưởng các lane

Tài liệu đi kèm: [NGHIEN_CUU_GIAI_PHAP_4_VAN_DE_2026-10-13.md](NGHIEN_CUU_GIAI_PHAP_4_VAN_DE_2026-10-13.md)
(bên ngoài người ta làm thế nào, có dẫn nguồn).

---

## 0. Tóm tắt một trang

| # | Vấn đề anh thấy | Nguyên nhân gốc (đã kiểm trong code) | Hướng xử lý chính |
|---|---|---|---|
| 1 | Agent hỏi đáp nhau kém khi Leader gọi vào session | Giao thức phối hợp nằm **trong prompt** để model tự nhớ: tool `TeamSay` có 14 tham số, 9 loại tin, 3 chế độ context, 3 kiểu kết thúc. Prompt Leader chứa luật riêng của case du lịch. Model mặc định là `gpt-4o-mini`. Chưa có lần chạy thật với model nào cho bản 13/10. | Chuyển giao thức sang **runtime** (sổ nhiệm vụ do server giữ), cho agent 4 tool nhỏ (hỏi, trả lời, báo kết quả, cần khách bổ sung), thêm vòng **phản biện** có giới hạn, đo bằng bộ kịch bản chạy model thật. |
| 2 | Không rõ đã tối ưu token, memory, context chưa | **Context ngắn hạn làm tốt** (Shared Context có cấu trúc, tóm tắt có nguồn, đo token trước mỗi lần gọi, ngân sách). **Prompt caching chưa được tận dụng**: gói context chung bị gắn vào system prompt nên mỗi lần đổi là mất cache cả lịch sử. **Long-term memory chưa chạy**: ReMe/mem0/AgenticMemory có sẵn trong AgentScope nhưng không được nối; API duyệt memory theo khu vực có nhưng không agent nào gọi, không có màn hình. | Sắp lại thứ tự prompt cho cache, đo tỉ lệ cache hit; nối memory thành 4 tầng (làm việc, case, kinh nghiệm, tri thức) với luồng **đề xuất → kiểm → duyệt → dùng**. |
| 3 | Agent Builder cứng, không tiếp thu ý muốn | Builder là **pipeline 2 bước một-phát** (outline → generate), không phải hội thoại: bước outline **bắt buộc trả ≥1 agent, không có đường hỏi lại**; chỉ sinh được tên, mục tiêu, prompt, tool, 1 skill; "đánh giá" chỉ là kiểm prompt ≥80 ký tự, skill ≥40 ký tự, và cho qua nếu giống agent cũ ≥0,72. Module Builder/Evaluation/Release của team (Nghĩa, Tiến Anh) **chưa được nối vào màn hình**. | Builder làm việc trên một **bản đặc tả agent (Agent Spec)** có cấu trúc: mỗi câu của người dùng thành một bản vá spec + tối đa 1–3 câu hỏi đúng chỗ thiếu; hiện khác biệt trước khi áp; sinh ca kiểm thử từ spec và chạy thật trước khi phát hành. |
| 4 | Thiếu trang quản lý agent dạng giao diện (không phải chat) | Hiện chỉ có trang Builder: khung chat + danh sách agent với **một nút bật/tắt phát hành**. Không có trang chi tiết, sửa, phiên bản, thử nghiệm. Backend phiên bản/rollback (D4) đã có nhưng UI không dùng. | Trang **Quản lý agent**: danh sách → chi tiết agent dạng form theo các tab (Hướng dẫn, Công cụ, Kiến thức, Phối hợp, Kiểm thử, Phiên bản, Hoạt động) + **Builder copilot** ở cột phải sửa cùng một spec. |

Ba việc nên làm ngay, trước mọi tính năng mới:

1. Sửa CI đang đỏ của `develop2` (gate còn đòi Alembic head `0011`, code đã lên `0015`).
2. Chạy bộ kịch bản phối hợp với **model thật** để có số đo gốc (hiện mọi bằng chứng đều từ model giả).
3. Chốt **Agent Spec** làm định dạng chung cho Builder, trang quản lý và runtime — đây là điểm nối của vấn đề 3 và 4.

---

## 1. Tình trạng nhánh `develop2` hôm nay

**Đã pull:** local `develop2` lên `f495ec00` (+3 commit, PR #74, #75 của `dev_TeamHoang`).
Mở ở worktree riêng `E:\AI-Workforce-Platform-develop2`, không đụng nhánh `dev_Vinhome` đang làm.

**Tiến độ theo kế hoạch** (`docs/workforce/KE_HOACH_TRIEN_KHAI.md`, các mốc M0–M10, phase A–D):

| Hạng mục | Trạng thái | Bằng chứng |
|---|---|---|
| Phase A, B, C (contract, registry MCP, builder, lifecycle, orchestration, execution) | Đã merge | STATUS của 6 thành viên, PR #63–#73 |
| D1–D4 (fault harness, SSE, protocol pin, builder regression, publish/rollback) | Đã merge vào `develop2@35cec29` | `handoffs/PHASE_D_SEQUENCE.md` |
| D5–D7 (E2E chịu lỗi, CI, runbook, Release Candidate) | Code xong; **Release Candidate chưa chốt** | Local: 647 pass, 22 skip; D7 không cho skip |
| Shared Context + phối hợp ngang (13/10) | Mới merge (PR #75) | `KE_HOACH_SHARED_CONTEXT.md`, `RUNTIME_COLLABORATION.md`: 421 pass, **1 fail** (artifact Phase A lệch schema) |
| Chạy với model / MCP thật | **Chưa có** | Tài liệu tự ghi: "Chưa có xác nhận chạy end-to-end với model/MCP thật" |
| Sandbox đối tác | **NOT_VERIFIED** | Chưa được cấp endpoint/credential |

**CI:** run mới nhất trên `develop2` (merge PR #75, 13/10 22:05) **đỏ** ở bước đầu:
`unexpected Alembic heads: ['0015_shared_context_backfill']` — gate trong
`.github/workflows/workforce-phase-d.yml` vẫn đòi đúng một head `0011_workforce_releases`.
Vì bước này fail nên không bộ test nào chạy và không có JUnit. Đây là lỗi gate, không phải lỗi code; sửa một dòng.

**Hai điểm cần biết khi đọc "đã xong":**

- Đường API đối tác (`/workforce/v1`) cần một `LeaderTurnRunner` để chạy Leader thật. Trong source **chỉ có interface**
  (`orchestration/_runtime.py:75`), không có bản cài đặt. Nghĩa là phối hợp agent qua API đối tác mới được thử bằng adapter giả.
- Có **hai đường song song** cho cùng một chức năng: màn hình console (`_router/_workforce_console.py`, cái người dùng thấy)
  và các module của team (`workforce/builder`, `workforce/lifecycle`). Console tự làm builder, tự đánh giá, tự bật/tắt phát hành;
  không gọi `ProposalService`, `async_evaluation` hay `releases`. Vấn đề 3 và 4 phần lớn nằm ở khoảng hở này.

---

## 2. Vấn đề 1 — Agent tương tác, hỏi đáp nhau chưa tốt

### 2.1 Hiện trạng

Luồng: Leader tạo team cho ticket → mời agent đã phát hành (`AgentInvite`) → giao việc bằng `TeamSay(kind=handoff)` →
worker làm, có thể hỏi đồng đội (`kind=question` / `answer`) → báo kết quả về Leader → Leader kết thúc từng nhánh
bằng `resolution=complete|verify|stop` kèm id bằng chứng → Leader trả lời khách.

Phần runtime khá chắc: hàng đợi bền, chống trùng, phát lại sau crash, phát hiện vòng A→B→A, ngân sách theo lượt
(24 trao đổi, 16 lần gọi model, 200k token, 180 giây, 2 lần kiểm chứng).

### 2.2 Vì sao vẫn kém — nguyên nhân gốc

| # | Nguyên nhân | Ở đâu | Tác động |
|---|---|---|---|
| a | **Giao thức nằm trong prompt, model phải tự tuân thủ.** `TeamSay` có 14 tham số (`kind` 9 giá trị, `context_mode` 3, `result_scope` 2, `resolution` 3, `thread_id`, `in_reply_to`, `reference_event_ids`, `context_delta`, `hop_count`, `question_key`, ...). Muốn kết thúc đúng một nhánh, Leader phải tự điền đúng id sự kiện bằng chứng. | `_tool/_team_say.py:56-150` | Model nhỏ hay chọn sai `kind`, quên `in_reply_to`, gửi "đang tìm..." thay vì kết quả. Runtime chặn → agent thử lại → tốn lượt và token, cuộc trao đổi trông "lạc nhau". |
| b | **Prompt dài và lẫn luật của một nghiệp vụ.** Prompt Leader ≈2.400 token, chính sách worker ≈1.750 token, mô tả + schema `TeamSay` ≈1.600 token (ước lượng bytes/4). Trong đó có nhiều luật riêng của case du lịch: ngân sách trừ dự phòng, khách sạn, xe, giờ nhận phòng... | `_workforce_policy.py` | Mỗi lần sửa một lỗi kịch bản lại thêm một luật vào prompt chung. Model phải lọc nhiều luật không liên quan; platform không còn trung lập với domain. |
| c | **Vá hành vi bằng từ khoá.** Nhận diện tin "chỉ là tiến độ" bằng danh sách cụm từ ("đang tìm", "please wait"...); nhận diện yêu cầu tính toán bằng ("tinh chi phi", "du phong"...). | `_team_say.py:38-52`, `_agent_invite.py:66-125` | Sai khi người dùng/agent diễn đạt khác; chỉ hiểu tiếng Việt/Anh; gắn với case du lịch. |
| d | **Không có bước phản biện thật.** Worker chỉ báo về reply owner; Leader được dặn "không trả lời báo cáo của member trừ khi có yêu cầu mới". `conflict` đòi trích ≥2 id sự kiện — model hiếm khi làm đúng. Không có tiêu chí nghiệm thu cho từng việc để so. | `_workforce_policy.py`, `RUNTIME_COLLABORATION.md` | Đúng với nhận xét của sếp 07/10: các agent không "thách thức" nhau, kết quả sai không ai bắt. |
| e | **Model yếu cho bài toán điều phối.** Model mặc định của Workforce là `gpt-4o-mini`; Leader, worker, tóm tắt dùng chung một model. | `_router/_workforce_console.py:70-75` | Điều phối nhiều bước là phần khó nhất, đang giao cho model rẻ nhất. |
| f | **Chưa đo bằng model thật.** Toàn bộ 421 test phối hợp dùng model giả theo kịch bản. | `RUNTIME_COLLABORATION.md` | Không biết lỗi nào thực sự xảy ra, bao nhiêu phần trăm. |

### 2.3 Hướng giải pháp

**Nguyên tắc: runtime giữ giao thức, model chỉ làm phần cần suy nghĩ.**

1. **Sổ nhiệm vụ (task ledger) do server giữ.** Khi nhận yêu cầu, Leader gọi **một** lần có cấu trúc để lập kế hoạch:
   danh sách việc, mỗi việc có `owner` (agent), `phụ thuộc`, `tiêu chí xong` (acceptance). Runtime lưu sổ này trong
   Shared Context (đã có chỗ: task state), tự giao việc theo thứ tự phụ thuộc, tự chuyển kết quả cho việc phụ thuộc,
   tự đánh dấu chờ/xong. Leader không cần nhớ `thread_id`, `in_reply_to`, id bằng chứng.
   Mỗi vòng, Leader chỉ trả lời 5 câu của *progress ledger* (xong chưa / có lặp / có tiến triển / ai làm tiếp /
   chỉ dẫn gì); không tiến triển 2 vòng liên tiếp thì lập lại kế hoạch (mẫu Magentic-One, mục 6).
   Mỗi lần giao việc bắt buộc 4 trường: mục tiêu, định dạng đầu ra, tool/nguồn được dùng, ranh giới.
2. **Thay `TeamSay` bằng 4 tool nhỏ cho worker** (giữ `TeamSay` cũ cho tương thích):

   | Tool | Tham số model phải điền | Runtime tự điền |
   |---|---|---|
   | `ask_peer(to, question)` | người nhận, câu hỏi | task, thread, hop, idempotency, trạng thái chờ |
   | `reply(answer)` | nội dung | `in_reply_to`, nguồn = các tool result trong lượt |
   | `report_result(summary, status)` | tóm tắt; `done`/`blocked` | bằng chứng = tool result trong lượt; chuyển cho việc phụ thuộc |
   | `need_customer_info(question, key)` | câu hỏi đề xuất | gom, khử trùng, chuyển reply owner duyệt |

   Bằng chứng lấy tự động từ các tool call thành công trong lượt (đã có: kết quả MCP được backend tự ghi thành fact
   `tool_verified`) — không bắt model chép id.
3. **Vòng phản biện có giới hạn.** Khi một việc báo `done`, runtime chạy bước kiểm: Leader (hoặc một agent "reviewer"
   rẻ) so kết quả với `tiêu chí xong` và các fact đã xác minh, trả `accept` hoặc `challenge(lý do, cần bổ sung gì)`.
   Challenge quay về đúng owner, tối đa 1–2 vòng (đã có `COLLABORATION_MAX_VERIFICATIONS=2`). Hết vòng mà vẫn
   chưa đạt → báo rõ phần chưa đạt, không bịa đồng thuận. Mẫu này là "orchestrator–worker + evaluator" trong các tài
   liệu bên ngoài (xem tài liệu nghiên cứu, mục 1).
4. **Tách luật domain khỏi platform.** Luật ngân sách/dự phòng, khách sạn, xe... chuyển vào skill/spec của agent du lịch
   hoặc "domain pack". Prompt Leader chỉ còn luật điều phối chung (mục tiêu ≤ 800 token). Bỏ các bộ nhận diện từ khoá
   khi đã có `report_result(status=...)` có cấu trúc.
5. **Chọn model theo vai.** Leader lập kế hoạch + reviewer dùng model mạnh hơn (ví dụ `gpt-5.4`/`gpt-5.5`); worker
   tra cứu và bước tóm tắt dùng model mini. Cấu hình theo vai, không theo agent. Fork đã có
   `ModelRouterMiddleware` (`middleware/_model_router.py`) để làm việc này, chưa được nối vào app.
6. **Đo trước, sửa sau.** Bộ 10–15 kịch bản phối hợp chạy model thật (case du lịch hiện có + 2–3 case dịch vụ khác),
   chấm tự động: hoàn thành đúng, số tin trao đổi, số lần runtime chặn, câu hỏi peer không được trả lời, token/case.
   Chạy trước và sau mỗi thay đổi.

**Không nên làm:** viết thêm luật vào prompt cho từng lỗi; cho tất cả agent đọc toàn bộ hội thoại của nhau
(tốn token, lạc hướng — chính tài liệu Shared Context của team đã loại trừ đúng điều này).

---

## 3. Vấn đề 2 — Token, context, memory, cập nhật tri thức

### 3.1 Đã làm tốt (giữ nguyên)

- **Context chung theo ticket** (`TeamSharedContextRecord`): trạng thái có cấu trúc (task, ràng buộc, fact, quyết định,
  câu hỏi mở); agent không tự nâng lời mình thành "đã xác minh"; kết quả MCP tự thành fact `tool_verified`.
- **Context riêng** của từng agent (`AgentState.context`) tách khỏi context chung; agent tham gia sau đọc gói context
  chung, không đọc lịch sử riêng của người khác.
- **Tóm tắt có nguồn** theo từng task, bắt buộc dẫn `source_event_ids`, không xoá dữ liệu gốc, lỗi thì giữ bản cũ.
- **Đo token trước mỗi lần gọi model**, chừa 10% cho output; không âm thầm cắt dữ liệu bắt buộc.
- **Ngân sách** mỗi nhánh việc (lượt, model call, token, thời gian) và chặn lặp nội dung.

### 3.2 Chỗ hở

| # | Chỗ hở | Bằng chứng | Hậu quả |
|---|---|---|---|
| a | **Prompt caching bị phá.** Gói context chung được nối vào **cuối system message** và làm mới mỗi khi có sự kiện mới. OpenAI chỉ cache phần đầu giống hệt nhau, nên mỗi lần gói đổi thì toàn bộ lịch sử phía sau mất cache. | `middleware/_shared_context_middleware.py:150-160` | Trả giá đầy đủ cho phần lặp lại (policy + tool schema + lịch sử) ở mọi lượt. Với ~5k token cố định mỗi lần gọi của Leader, đây là phần tiết kiệm lớn nhất bị bỏ lỡ. |
| b | **Không đo cache.** Model client đã đọc `cached_tokens` từ provider, nhưng app không ghi vào metric. | `model/_openai_chat/_model.py:368-380`; không có chỗ dùng trong `app/` | Không trả lời được câu "đã tối ưu chưa" bằng số. |
| c | **Long-term memory chưa chạy.** `ReMeMiddleware`, `Mem0Middleware`, `AgenticMemoryMiddleware` có trong AgentScope nhưng chỉ dùng ở `examples/long_term_memory`. | `middleware/_longterm_memory/` | Agent không nhớ gì qua các ticket. |
| d | **Luồng duyệt memory có API nhưng không ai dùng.** `memory_candidates` → quản lý khu vực duyệt → embed → tìm bằng pgvector. Không agent tool nào tạo đề xuất hay tìm memory; không có màn hình duyệt. | `business/_service.py:798-1110`, `_router/_business.py:274-333` | "Agent tự cập nhật kiến thức" = 0 trong thực tế. |
| e | **Builder không gắn được Knowledge Base cho agent.** RAG theo session đã có (`knowledge_config`), nhưng agent do Builder sinh chỉ có tên/mục tiêu/prompt/tool/skill. | `_router/_workforce_console.py:90-99` | Tri thức nghiệp vụ phải nhét vào prompt → prompt dài, tốn token, khó cập nhật. |
| f | **Một model cho mọi việc**, kể cả tóm tắt. Chi phí tóm tắt tính riêng, chưa gộp; không có sổ chi phí theo ticket. | `RUNTIME_COLLABORATION.md` | Không có báo cáo "mỗi case tốn bao nhiêu". |

### 3.3 Hướng giải pháp

**A. Token và cache (làm được ngay, rủi ro thấp)**

1. Sắp prompt theo thứ tự **ổn định → thay đổi**: `[policy chung + vai trò + tool schema]` → `[lịch sử riêng]` →
   `[gói context chung mới nhất]` (đặt như một message gần cuối, không sửa system message). Giữ thứ tự tool cố định.
2. Gửi `prompt_cache_key` theo `agent_id + version` (OpenAI dùng nó để định tuyến cache) nếu gateway hỗ trợ;
   giữ danh sách tool cố định, bật/tắt bằng `allowed_tools` thay vì thêm/bớt tool (đổi tool làm mất cache).
3. Ghi `cached_input_tokens` vào metric hiện có, hiển thị tỉ lệ cache hit theo agent và theo ticket.
4. Tool result lớn: đã có `ToolOffloadMiddleware`; bổ sung **dọn kết quả tool cũ** trong context riêng sau khi đã thành
   fact trong Shared Context (giữ tham chiếu id).
5. Model theo vai: tóm tắt/trích xuất dùng model rẻ nhất; chỉ Leader/reviewer dùng model mạnh.

**B. Memory 4 tầng**

| Tầng | Chứa gì | Phạm vi | Hiện có? | Việc cần làm |
|---|---|---|---|---|
| 1. Làm việc | Lịch sử lượt hiện tại của một agent | 1 agent, 1 session | Có | Giữ |
| 2. Case | Fact, quyết định, kết quả của ticket | 1 ticket, cả nhóm | Có (Shared Context) | Sửa cache (A.1) |
| 3. Kinh nghiệm | "Case tương tự đã xử lý thế nào, lỗi gì, khách thích gì" | Khu vực / agent | Bảng + API có, chưa dùng | Khi ticket đóng: tự trích 1–3 bài học có nguồn → `memory_candidates` |
| 4. Tri thức | Quy trình, chính sách, bảng giá, SOP | Khu vực / agent | RAG có, chưa gắn vào agent | Builder/trang quản lý gắn KB cho agent; agent đọc qua tool `search_knowledge` |

**C. Cập nhật tri thức an toàn (agent "tự học" nhưng không bịa)**

```text
Agent/ticket đóng ──► đề xuất memory (nội dung + nguồn: ticket, event id, tool result)
        │
        ▼
Kiểm tự động: trùng? mâu thuẫn với memory cũ? có nguồn xác minh?   (embedding + 1 lần gọi model rẻ)
        │
        ├─ loại thấp rủi ro (sở thích khách, mẹo tra cứu) ──► tự duyệt, có hạn dùng
        └─ loại ảnh hưởng nghiệp vụ (quy trình, giá, chính sách) ──► BQL duyệt trên màn hình
        │
        ▼
Dùng: đầu mỗi case, runtime lấy top-k memory liên quan trong giới hạn token, gắn nhãn "memory, nguồn X, ngày Y"
Khi mâu thuẫn mới: bản cũ đánh dấu thay thế, không xoá (giữ lịch sử)
```

Điểm quan trọng: memory **không bao giờ** được coi ngang với kết quả tool hiện tại; chính sách bằng chứng hiện có vẫn đứng trên.

---

## 4. Vấn đề 3 — Agent Builder quá cứng

### 4.1 Hiện trạng (màn `/workforce/builder`)

Mỗi tin nhắn của người dùng đi qua `prepare_builder`:

1. **Outline**: một lần gọi có cấu trúc trả danh sách agent (tên, mục tiêu, tool gợi ý).
2. Người dùng bấm xác nhận → **Generate**: một lần gọi sinh `name, objective, system_prompt, selected_tool_ids, skill`.
3. **"Đánh giá"**: kiểm prompt ≥80 ký tự, skill ≥40 ký tự, tool hợp lệ, không trùng tool;
   **qua luôn nếu mô tả giống agent cũ ≥0,72** (so trùng từ).
4. Phát hành = đổi `lifecycle_state` và `invitable`.

### 4.2 Vì sao "cứng"

| # | Nguyên nhân | Ở đâu |
|---|---|---|
| a | Bước outline **bắt buộc trả ≥1 agent** (`min_length=1`), không có trường câu hỏi → không thể hỏi lại người dùng trước khi đề xuất; luôn "đoán rồi đưa". | `BuilderOutline`, `_workforce_console.py:117-120` |
| b | Mỗi lượt sinh lại từ đầu thay vì **sửa đúng chỗ** người dùng yêu cầu ("đổi giọng thân thiện hơn", "thêm: không báo giá khi chưa có ảnh"). | `_generate`, `_workforce_console.py:541` |
| c | Phạm vi được sinh quá hẹp: không có giọng điệu, đối tượng phục vụ, điều được/không được làm, khi nào chuyển người, kiến thức, agent phối hợp, ví dụ hội thoại, ca kiểm thử. Ý muốn của người dùng chỉ còn đường đi vào một khối prompt tự do. | `GeneratedAgent`, `_workforce_console.py:90-99` |
| d | Gợi ý trong prompt Builder gắn với du lịch ("hotel search", "transport", "calculation"). | `_outline`, `_workforce_console.py:454` |
| e | Không có đánh giá hành vi thật; module `async_evaluation` và `releases` của team đã làm nhưng không được gọi. | `_workforce_console.py:1316-1330` |
| f | Không sửa được agent đã có (tạo mới hoặc tái dùng, không có "phiên bản 2"). | `publish_builder` |

### 4.3 Hướng giải pháp: Builder làm việc trên **Agent Spec**

**Agent Spec** = một tài liệu có cấu trúc, là nguồn sự thật duy nhất của một agent (Builder, trang quản lý và runtime cùng đọc):

```yaml
identity:     { name, mô tả ngắn, đối tượng phục vụ, ngôn ngữ, giọng điệu }
mission:      { mục tiêu, phạm vi làm, ngoài phạm vi }
rules:        [ { luật, mức: bắt buộc|nên, lý do } ]          # do / don't
escalation:   [ { khi nào, chuyển cho ai (người/agent) } ]
tools:        [ { tool_id, dùng khi nào, cần xác nhận? } ]
knowledge:    [ { kb_id, dùng cho việc gì } ]
collaborates: [ { agent/capability, hỏi họ khi nào } ]
examples:     [ { người dùng nói, agent nên làm } ]
tests:        [ { kịch bản, kỳ vọng, tiêu chí chấm } ]
model_tier:   standard | strong                                 # BQL chọn mức, platform chọn model
```

Prompt chạy thật được **dựng từ spec bằng template cố định** + phần văn do model viết; chính sách bằng chứng của
platform vẫn gắn cuối như hiện nay.

**Vòng làm việc của Builder (mỗi tin nhắn):**

1. Hiểu ý → trả **bản vá spec** (thêm/sửa/xoá từng trường) + **tối đa 3 câu hỏi**, chỉ hỏi chỗ thiếu ảnh hưởng hành vi
   (ví dụ: "Khi cư dân hỏi giá, agent được báo giá tham khảo hay phải chuyển kỹ thuật?").
2. Hiện **khác biệt** (trước/sau) cho người dùng duyệt; người dùng sửa tay ngay trên form nếu muốn.
3. Tự sinh 5–10 ca kiểm thử từ `rules` + `examples` + `escalation`; người dùng thêm/bớt.
4. **Chạy thử thật** (model thật, tool giả/sandbox) qua `async_evaluation` của team; xem kết quả từng ca.
5. Phát hành qua `releases` (phiên bản bất biến, phiên đang chạy giữ bản cũ, rollback được).
6. Sửa agent đã phát hành = mở spec → vá → kiểm thử → phiên bản mới.

**Kỹ thuật:** Builder là một agent có tool (`get_spec`, `patch_spec`, `list_tools`, `list_knowledge`, `suggest_tests`,
`run_tests`) thay vì hai lần gọi structured cố định. Bỏ gợi ý du lịch trong prompt Builder; template theo ngành (dịch vụ
cư dân, du lịch...) để ở thư viện mẫu.

---

## 5. Vấn đề 4 — Trang quản lý agent (giao diện, không phải chat)

### 5.1 Hiện trạng

Frontend (`examples/web_ui/frontend`) có: `/workforce/leader` (chat với Leader), `/workforce/builder` (chat Builder +
danh sách agent, mỗi agent một nút phát hành/bản nháp), cùng các trang MCP, Skill, Knowledge, Credential chung của
AgentScope. Không có trang chi tiết agent, không sửa form, không xem phiên bản, không thử nghiệm.

### 5.2 Đề xuất màn hình

**Agent → Danh sách**

| Cột | Ghi chú |
|---|---|
| Tên, mô tả ngắn | |
| Trạng thái | Bản nháp / Đang phát hành / Đã thu hồi |
| Phiên bản | v3 (đang chạy) · v4 nháp |
| Kết quả kiểm thử gần nhất | 9/10 ca đạt |
| Sử dụng 7 ngày | số ticket, chi phí, tỉ lệ hoàn thành |

Nút: **Tạo agent** (3 cách: mô tả bằng lời → Builder điền form; chọn mẫu ngành; nhân bản agent có sẵn).

**Agent → Chi tiết** (form bên trái, Builder copilot bên phải)

| Tab | Nội dung | Map vào spec |
|---|---|---|
| Tổng quan | tên, đối tượng, ngôn ngữ, giọng, mục tiêu, phạm vi | `identity`, `mission` |
| Hướng dẫn | danh sách luật (thêm/xoá/kéo thứ tự), khi nào chuyển người | `rules`, `escalation` |
| Công cụ | chọn tool từ kho MCP, ghi "dùng khi nào", đánh dấu cần xác nhận | `tools` |
| Kiến thức | gắn KB, xem tài liệu, memory đã duyệt của agent | `knowledge` |
| Phối hợp | agent nào được hỏi, hỏi khi nào | `collaborates` |
| Kiểm thử | danh sách ca + nút chạy; khung **chat thử** (playground) | `tests` |
| Phiên bản | lịch sử, so sánh 2 phiên bản, phát hành, rollback | `releases` |
| Hoạt động | ticket gần đây, token/chi phí, cache hit, lỗi | metric |

**Builder copilot** ở cột phải: người dùng gõ "thêm luật không báo giá khi chưa có ảnh" → copilot đề xuất bản vá →
form tô sáng trường thay đổi → người dùng bấm Áp dụng. Form và chat sửa **cùng một spec**, nên dùng cách nào cũng được.

**Memory chờ duyệt** (cho BQL): danh sách đề xuất memory với nguồn (ticket, trích đoạn), nút Duyệt / Từ chối / Sửa.

---

## 6. Bên ngoài người ta làm thế nào (tóm tắt)

Chi tiết và nguồn: [NGHIEN_CUU_GIAI_PHAP_4_VAN_DE_2026-10-13.md](NGHIEN_CUU_GIAI_PHAP_4_VAN_DE_2026-10-13.md).

| Vấn đề | Họ làm thế nào | Áp dụng cho mình |
|---|---|---|
| 1. Phối hợp | **Magentic-One / Microsoft Agent Framework**: Leader giữ *task ledger* (fact, giả định, kế hoạch) và *progress ledger* trả lời 5 câu mỗi vòng: xong chưa? có lặp không? có tiến triển không? ai làm tiếp? chỉ dẫn gì? Không tiến triển quá 2 vòng thì lập lại kế hoạch; có giới hạn vòng. **Anthropic** (hệ multi-agent research): mỗi lần giao việc phải có mục tiêu, định dạng đầu ra, tool/nguồn được dùng, ranh giới; giao mơ hồ → agent làm trùng nhau. **Cognition**: agent "nói lệch nhau" vì giả định ẩn → bắt nêu bằng chứng và giả định. Nghiên cứu lỗi multi-agent (arXiv 2503.13657): lặp bước 15,7%, dừng sai lúc 12,4%, thiếu/kiểm sai. | Sổ nhiệm vụ + sổ tiến độ do runtime giữ (mục 2.3); mẫu giao việc 4 trường bắt buộc; kịch bản kiểm thử nhắm đúng 3 loại lỗi trên. |
| 1. (công cụ có sẵn) | AgentScope 2.0 upstream có **`TeamPipeline`**: Leader giao việc qua tool `TeamAssign(member, prompt)`, mỗi member làm trong context riêng và chỉ trả kết quả cuối. Bản fork của mình **đã có file này** (`pipeline/_team_pipeline.py`) nhưng app không dùng. | Tham khảo cách làm "tool nhỏ, runtime lo phần còn lại". Không thay hẳn được vì `TeamPipeline` không cho member hỏi nhau, còn mình cần `ask_peer`. |
| 2. Token/cache | **OpenAI prompt caching**: cache theo *tiền tố giống hệt*, tối thiểu 1.024 token; giữ danh sách tool cố định (bật/tắt bằng `allowed_tools`), dữ liệu thay đổi để cuối, lịch sử chỉ nối thêm; có `prompt_cache_key`. Đọc cache rẻ hơn nhiều so với token thường. **Anthropic**: dọn kết quả tool cũ trước khi tóm tắt giảm 84% token trong thử nghiệm của họ. | Đúng các bước ở mục 3.3 A. **Chưa kiểm**: gateway của mình có chuyển tham số cache và trả `cached_tokens` không — làm ở P0. |
| 2. Memory | **Mem0**: mỗi fact mới được quyết ADD/UPDATE/DELETE/NOOP so với memory cũ; ~7k token so với ~26k khi nhồi toàn bộ hội thoại. **Graphiti/Zep**: fact cũ đánh dấu hết hiệu lực thay vì xoá, giữ nguồn gốc. **LangMem, Letta**: ghi memory ở nền (không chặn lượt trả lời), có bước duyệt. AgentScope có `ModelRouterMiddleware` để dồn việc nhỏ (định tuyến, tóm tắt) sang model rẻ — **có trong fork, chưa dùng**. | Luồng đề xuất → kiểm (ADD/UPDATE/NOOP, mâu thuẫn) → duyệt → dùng ở mục 3.3 C; model theo vai dùng `ModelRouterMiddleware`. |
| 3. Builder | **Agentforce, Gemini Enterprise**: hỏi làm rõ trước khi sinh. **Copilot Studio**: tool/kiến thức do AI gợi ý là *đề xuất* người dùng chấp nhận/bỏ từng cái, và họ đo tỉ lệ chấp nhận làm chỉ số chất lượng. **Dify**: mỗi lần sinh là một phiên bản, có so sánh. Spec có cấu trúc khớp 1-1 với form. **OpenAI AgentKit Agent Builder và Evals sẽ ngừng ngày 30/11/2026** → không phụ thuộc. | Agent Spec + bản vá + diff + ca kiểm thử bắt buộc (mục 4.3); thêm chỉ số "tỉ lệ đề xuất được chấp nhận". |
| 4. Trang quản lý | **Gemini, Agentforce**: 3 cột — chat builder, form agent, xem trước, đồng bộ nhau. **Agentforce**: Nháp → Commit → Live, một bản live; rollback = khôi phục bản cũ thành nháp rồi phát hành lại. Thử nghiệm 2 chế độ: *Simulate* (không ghi dữ liệu) và *Live* có trace từng bước. **Relevance AI, n8n**: mức duyệt theo từng tool (tự chạy / cần duyệt / agent tự quyết). **Intercom Fin**: menu Train → Test → Deploy → Analyze; AI gợi ý sửa kiến thức, người duyệt. | Bố cục mục 5.2; thêm mức duyệt theo tool trong tab Công cụ; playground có chế độ Simulate. |

Phần chưa kiểm được trong nghiên cứu: trang trợ giúp OpenAI về GPT Builder trả lỗi 403 (chỉ dựa kết quả tìm kiếm);
tài liệu memory của Letta vừa đổi cấu trúc; cơ chế phiên bản của Copilot Studio chưa đọc.

---

## 7. Kế hoạch đề xuất

Giả định (cần anh xác nhận, xem mục 8): làm trên `develop2`, theo lane sở hữu hiện có; mốc demo 22/10, đóng băng tính năng từ 19/10.

| Giai đoạn | Ngày | Việc | Lane gợi ý | Xong khi |
|---|---|---|---|---|
| **P0 — Đo và gỡ chặn** | 14/10 | Sửa gate Alembic head trong CI; sửa test artifact Phase A lệch | Nguyễn Chí Hoàng | CI xanh trên `develop2` |
| | 14/10 | Bộ 10–15 kịch bản phối hợp + chấm tự động, chạy model thật, lưu số đo gốc | Phan Hoàng Dũng | Có bảng: tỉ lệ đạt, token/case, số tin, số lần bị chặn |
| | 14/10 | Ghi `cached_tokens` vào metric | Nguyễn Chí Hoàng | Thấy tỉ lệ cache hit theo agent |
| **P1 — Phối hợp v2 + token** | 15–17/10 | Sổ nhiệm vụ do runtime giữ; 4 tool nhỏ; tự gắn bằng chứng | Phan Huy Hoàng | Kịch bản P0 tăng tỉ lệ đạt, giảm số tin bị chặn |
| | 15–16/10 | Vòng phản biện (accept/challenge ≤2 vòng) | Phan Huy Hoàng | Ca có lỗi cài sẵn bị bắt |
| | 15/10 | Đổi chỗ gói context chung ra cuối, cố định thứ tự tool | Phan Huy Hoàng | Cache hit tăng (so P0) |
| | 15/10 | Tách luật du lịch khỏi prompt Leader sang skill agent du lịch; model theo vai | Phan Huy Hoàng + Nghĩa | Prompt Leader ≤ 800 token, kịch bản du lịch vẫn đạt |
| **P2 — Spec, Builder, trang quản lý** | 14/10 | Chốt schema Agent Spec (họp 1 giờ) | Nghĩa + Tiến Anh | Schema + ví dụ được 2 lane ký |
| | 15–17/10 | Builder v2 (patch spec, ≤3 câu hỏi, diff, sinh ca kiểm thử) | Bùi Hữu Nghĩa | 5 yêu cầu sửa kiểu "đổi giọng/thêm luật" được áp đúng chỗ |
| | 15–18/10 | Trang Quản lý agent (danh sách, chi tiết, kiểm thử, phiên bản) nối `async_evaluation` + `releases` | Phó Tiến Anh (+ người frontend) | Tạo → sửa → kiểm thử → phát hành v2 → rollback chạy trên UI |
| | 16–17/10 | Builder copilot trong trang chi tiết | Nghĩa | Sửa bằng chat hoặc form ra cùng spec |
| **P3 — Memory** | 16–18/10 | Tool `search_knowledge`; gắn KB từ spec | Nguyễn Phương Đông | Agent trả lời từ KB có trích nguồn |
| | 17–18/10 | Trích bài học khi đóng ticket → memory candidate; màn duyệt; tool `recall` đầu case | Đông + Tiến Anh | 1 case thứ hai dùng đúng bài học case thứ nhất |
| **Đóng băng** | 19–21/10 | Chỉ sửa lỗi; chạy lại bộ kịch bản; chuẩn bị demo | Cả nhóm | Số đo P0 vs. sau cải tiến cho báo cáo |

Nếu không đủ người/thời gian, thứ tự ưu tiên: **P0 → P1 (phối hợp + cache) → P2 (spec + trang quản lý cơ bản) → P3**.
Memory kinh nghiệm (P3 phần 2) là phần dễ cắt nhất mà vẫn còn câu chuyện demo nhờ KB.

**Chỉ số để báo cáo sếp** (đúng điểm 6 của buổi review 07/10: tối ưu context/memory/chi phí, không bịa):

| Chỉ số | Đo ở đâu |
|---|---|
| Tỉ lệ case hoàn thành đúng | bộ kịch bản P0 |
| Token và chi phí mỗi case, % token được cache | metric + `cached_tokens` |
| Số câu khẳng định không có nguồn | chấm tự động trên kết quả cuối |
| Số tin nhắn giữa agent mỗi case, số lần bị runtime chặn | Shared Context metrics |
| Thời gian tạo một agent đạt kiểm thử bằng Builder | đo thủ công trên UI |

---

## 8. Cần anh quyết định

1. **Ai làm?** Giao theo lane của 6 thành viên như bảng trên, hay muốn tôi làm trực tiếp một phần trên `develop2` (ví dụ P0 + sửa cache + bộ kịch bản)?
2. **Mốc thời gian:** `develop2` có phải là bản đem demo 22/10 không? (Có bản platform core `awp` song song trên nhánh khác.)
3. **Model:** được dùng model mạnh hơn mini cho Leader/reviewer không (chi phí tăng ở 1–2 lần gọi mỗi case)?
4. **Duyệt memory:** BQL duyệt mọi memory, hay cho tự duyệt loại thấp rủi ro (sở thích khách, mẹo tra cứu)?
5. **Builder cho BQL:** có cho BQL xem/sửa trực tiếp prompt đã dựng không, hay chỉ sửa qua form spec?
6. **Luật du lịch** trong prompt Leader: đồng ý chuyển sang skill của agent du lịch (platform trung lập domain)?
