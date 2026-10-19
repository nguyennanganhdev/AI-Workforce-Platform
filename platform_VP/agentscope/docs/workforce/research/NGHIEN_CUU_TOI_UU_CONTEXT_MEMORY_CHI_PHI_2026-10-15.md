# Nghiên cứu tối ưu context, memory, chất lượng và chi phí token cho nền tảng Workforce

> Đối chiếu phần đã thực hiện bằng [báo cáo P2 ngày 16/10](../BAO_CAO_HOAN_THANH_P2_2026-10-16.md).
> Tài liệu này là nghiên cứu, không phải bằng chứng production acceptance.

Ngày nghiên cứu: 15/10/2026. Phạm vi: chỉ nguồn gốc (tài liệu chính thức của OpenAI/Anthropic/Google, blog kỹ thuật của chính hãng, bài báo arXiv của tác giả, tài liệu/README chính thức của framework). Mỗi khẳng định có kèm URL. Ngày của nguồn ghi trong ngoặc khi nguồn có ghi.

Quy ước:
- **[chưa xác minh]**: chỉ thấy qua kết quả tìm kiếm hoặc nguồn thứ cấp, chưa đọc được trang gốc. Độ tin cậy thấp hơn.
- **[mã nguồn local]**: đọc trong `platform_VP/agentscope/src` của nhánh develop2.
- **[ước tính]**: phép tính của nhóm dựa trên bảng giá chính thức và số đo cũ của mình, không phải số của hãng.
- Số liệu là số do hãng/tác giả công bố, nhóm chưa kiểm chứng lại.

Bối cảnh: Leader (gpt-5.5) điều phối room gồm các member (gpt-5.4-mini) qua TeamCreate/AgentInvite/TeamSay. Member gọi MCP của đối tác, kết quả mang nhãn E1, E2…; Leader trích dẫn trong một tin nhắn duy nhất gửi người dùng, server từ chối con số không có trong evidence được trích. Shared Context (blackboard) mỗi room: event log + items có mức thẩm quyền (`tool_verified` / `agent_reported` / `customer_confirmed`), packet 12k token chèn vào mỗi lần gọi model, tóm tắt bằng LLM khi vượt ngân sách. Long-term memory theo agent: sau ticket thành công, model mạnh trích memory (kèm event id) → hợp nhất; recall top-5 / 2.400 ký tự mỗi lượt. Số đo trước khi thiết kế lại: 9–15 lần gọi model mạnh/ticket, ~13–15k input token/lần, cache 58–71%.

---

## 0. Năm điều cần biết trước

1. **OpenAI Evals (dashboard + API) sẽ tắt ngày 30/11/2026**, chỉ đọc từ 31/10/2026. Prompt optimizer dạng dataset cũng bị bỏ cùng. Nguồn: https://developers.openai.com/api/docs/deprecations và https://developers.openai.com/api/docs/guides/prompt-optimizer. → Bộ test Agent Studio tự viết là hướng đúng, không nên chuyển sang OpenAI Evals.
2. **Fine-tuning tự phục vụ (gồm RFT) đang bị thu hẹp**: từ 07/05/2026 tổ chức chưa từng fine-tune không tạo job được nữa; 06/01/2027 dừng hẳn với cả khách cũ. RFT trên trang hướng dẫn chỉ hỗ trợ `o4-mini`. Nguồn: https://developers.openai.com/api/docs/deprecations, https://developers.openai.com/api/docs/guides/reinforcement-fine-tuning. → Với đội ta, "học" chỉ còn là prompt/memory/rule, không phải trọng số.
3. **OpenAI Responses API đã có compaction phía server** (`context_management` với `compact_threshold`) và endpoint `/responses/compact`. Nguồn: https://developers.openai.com/api/docs/guides/compaction.
4. **`previous_response_id` không làm rẻ hơn**: "all previous input tokens for responses in the chain are billed as input tokens". Nguồn: https://developers.openai.com/api/docs/guides/conversation-state.
5. **Với gpt-5.5, cache ghi theo mốc 2.048 token** và cached input rẻ hơn 10 lần ($0,50 so với $5,00/1M). Thứ đắt nhất trong một ticket là phần input chưa cache + output (kể cả reasoning). Nguồn: https://developers.openai.com/api/docs/guides/prompt-caching, https://developers.openai.com/api/docs/pricing.

---

## 1. Context engineering cho agent

### 1.1 Bằng chứng về "context rot"

| Nguồn | Phát hiện |
|---|---|
| Chroma, "Context Rot" (14/07/2025): https://www.trychroma.com/research/context-rot | Thử 18 model (GPT-4.1, Claude 4, Gemini 2.5, Qwen3). Hiệu năng "grows increasingly unreliable as input length grows" kể cả với tác vụ đơn giản. Một đoạn gây nhiễu cùng chủ đề đã làm giảm độ chính xác, bốn đoạn giảm thêm. (Báo cáo của một hãng vector DB, không phải hãng model: độ tin cậy trung bình.) |
| Liu et al., "Lost in the Middle" (07/2023, TACL): https://arxiv.org/abs/2307.03172 | Hiệu năng cao nhất khi thông tin liên quan ở đầu hoặc cuối context, giảm rõ khi nằm giữa. |
| Anthropic, "Effective context engineering for AI agents" (29/09/2025): https://www.anthropic.com/engineering/effective-context-engineering-for-ai-agents | Context là tài nguyên hữu hạn có "attention budget"; "Every new token introduced depletes this budget". Mục tiêu: "the smallest possible set of high-signal tokens". |

### 1.2 Anthropic khuyến nghị gì (29/09/2025)

Nguồn: https://www.anthropic.com/engineering/effective-context-engineering-for-ai-agents

| Kỹ thuật | Nội dung | Khi nào dùng |
|---|---|---|
| System prompt "đúng độ cao" | Tránh cả logic hard-code giòn lẫn hướng dẫn mơ hồ; chia section; bắt đầu tối thiểu rồi thêm theo lỗi quan sát được. | Luôn luôn |
| Tool gọn | Tool "self-contained, robust to error, and extremely clear"; tránh bộ tool chồng chức năng; kết quả trả về tiết kiệm token. | Luôn luôn |
| Just-in-time retrieval | Giữ "lightweight identifiers (file paths, stored queries, web links…)" và chỉ nạp nội dung khi cần; hybrid (nạp trước một ít + tự khám phá) thường tốt nhất. | Dữ liệu lớn |
| Compaction | Tóm tắt hội thoại sắp đầy context để mở cửa sổ mới; tinh chỉnh prompt tóm tắt trước cho recall, rồi mới cho precision. | Hội thoại qua lại dài |
| Tool result clearing | Dạng compaction "nhẹ tay nhất": kết quả tool đã dùng xong ở sâu trong lịch sử có thể bỏ. | Agent gọi tool nhiều |
| Structured note-taking | Agent ghi chú ra bộ nhớ ngoài context (ví dụ NOTES.md) và đọc lại khi cần. | Việc lặp có mốc rõ |
| Sub-agent | Sub-agent làm việc trong context sạch, có thể dùng hàng chục nghìn token nhưng chỉ trả về bản tóm tắt cô đọng **~1.000–2.000 token**. | Việc song song, nghiên cứu |

Bổ sung từ bài multi-agent research (13/06/2025): https://www.anthropic.com/engineering/multi-agent-research-system
- "Subagents call tools to store their work in external systems, then pass lightweight references back to the coordinator."
- Lead lưu kế hoạch vào memory vì context >200.000 token bị cắt; agent "summarize completed work phases and store essential information in external memory before proceeding".
- Hệ đa agent tốn ~15 lần token so với chat, chỉ đáng với tác vụ giá trị cao.

### 1.3 Các tính năng API của Anthropic (để đối chiếu thiết kế)

Nguồn: https://platform.claude.com/docs/en/docs/build-with-claude/context-editing, https://platform.claude.com/docs/en/agents-and-tools/tool-use/memory-tool, https://claude.com/blog/context-management (29/09/2025)

- **Context editing** (beta, header `context-management-2025-06-27`), chạy phía server trước khi prompt tới model, client vẫn giữ lịch sử đầy đủ.
  - `clear_tool_uses_20250919`: xoá kết quả tool cũ nhất trước, thay bằng placeholder. Tham số: `trigger` (mặc định 100.000 input token), `keep` (mặc định 3 tool use gần nhất), `clear_at_least` (chỉ xoá khi giải phóng đủ N token, "useful for justifying a cache invalidation"), `exclude_tools`, `clear_tool_inputs`.
  - `clear_thinking_20251015`: quản lý thinking block cũ.
  - Lưu ý cache: xoá tool result **làm mất prefix đã cache** tại điểm xoá, vì vậy dùng `clear_at_least` để mỗi lần xoá đáng giá.
- **Memory tool** (`memory_20250818`): chạy phía client, Claude yêu cầu thao tác file trong `/memories` (view/create/str_replace/insert/delete/rename), ứng dụng tự lưu. Khi gần ngưỡng xoá, Claude được cảnh báo để ghi điều quan trọng vào memory. Tài liệu khuyên giới hạn kích thước file, xoá memory lâu không truy cập, chặn path traversal.
- **Compaction phía server** (`compact_20260112`) là chiến lược chính được khuyến nghị; compaction phía SDK (`compaction_control`) đã deprecated.
- Số liệu Anthropic công bố (29/09/2025): memory + context editing **+39%** so với baseline trên eval tìm kiếm agentic nội bộ; context editing riêng **+29%**; trên eval tìm web 100 lượt, context editing **giảm 84% token**.

### 1.4 OpenAI Responses API: cái gì thực sự tồn tại

| Tính năng | Sự thật theo tài liệu | Nguồn |
|---|---|---|
| `previous_response_id` | Nối chuỗi hội thoại không phải gửi lại lượt cũ. **Không giảm tiền**: mọi input token trước đó vẫn tính là input. Response lưu 30 ngày mặc định; `store: false` để tắt. | https://developers.openai.com/api/docs/guides/conversation-state |
| Conversations API | Đối tượng hội thoại bền, không chịu TTL 30 ngày; chứa message, tool call, tool output. | như trên |
| Reasoning items | OpenAI "highly recommend you pass back any reasoning items returned with the last function call"; với `store: false` dùng `encrypted_content`. Reasoning token tính như output token. | https://developers.openai.com/api/docs/guides/reasoning |
| Lợi ích reasoning items (cookbook, đã lưu trữ) | Truyền lại reasoning items: ~**+3%** SWE-bench cùng prompt; chuyển Completions → Responses tăng cache utilization **40% → 80%** (số của tác giả cookbook, thời điểm ~05/2025). | https://developers.openai.com/cookbook/examples/responses_api/reasoning_items |
| Compaction phía server | `context_management: [{type: "compaction", compact_threshold: N}]`; khi vượt ngưỡng, server sinh **compaction item mã hoá** (không đọc được) và cắt context trong cùng stream. Dùng với input-array (bỏ được các item trước compaction item) hoặc `previous_response_id`. ZDR-friendly với `store: false`. Trang không nêu danh sách model hỗ trợ và giá. | https://developers.openai.com/api/docs/guides/compaction |
| `/responses/compact` | Compaction chủ động, stateless; trả về cửa sổ mới đã nén để đưa nguyên vào lần gọi sau. | như trên |
| Hướng dẫn compaction cho GPT-5.5 | Khi tự nén, giữ: "completed actions, active assumptions, IDs, tool outcomes, unresolved blockers, and the next concrete goal". | https://developers.openai.com/api/docs/guides/gpt-5.5 |
| Tham số `truncation` | Trang conversation-state không mô tả; chỉ nói token vượt context window "may be truncated". **[chưa xác minh]** chi tiết `truncation: "auto"`. | https://developers.openai.com/api/docs/guides/conversation-state |

Hạn chế quan trọng với hệ ta: compaction item của OpenAI **mã hoá, không đọc được**. Hệ ta cần tóm tắt **đọc được và trích dẫn được** (case file, nhãn E, mức thẩm quyền) nên compaction của OpenAI chỉ hợp cho context riêng của từng agent, không thay được blackboard.

### 1.5 OpenAI cookbook: trimming và summarization

Nguồn: https://developers.openai.com/cookbook/examples/agents_sdk/session_memory (không ghi ngày)
- **Trimming** (giữ N lượt cuối): tất định, không thêm độ trễ, nhưng "Forgets long-range context abruptly".
- **Summarization**: giữ trí nhớ dài nhưng tốn thêm lần gọi và "Details can be dropped or misweighted". Cảnh báo: "If a bad fact enters the summary, it can **poison** future behavior". Khuyên kiểm tra mâu thuẫn và đánh dấu điều chưa chắc là UNVERIFIED.
- Mẫu tóm tắt ≤200 từ theo tiêu đề cố định: vấn đề, các bước đã thử + kết quả, **định danh**, mốc thời gian, trạng thái/vướng mắc, bước tiếp theo.
- Đánh giá tóm tắt: so baseline trước/sau, LLM-as-judge, phát lại transcript và kiểm tra lượt sau còn đúng ID/thực thể không, theo dõi lỗi "mất ràng buộc" và "gọi tool lặp".

### 1.6 Ý nghĩa với hệ ta

- Thiết kế hiện tại (packet có ngân sách + tóm tắt + nén tool fact) khớp đúng hướng của cả hai hãng. Chỗ cần sửa là **cách** làm, không phải **có** làm hay không:
  - Tóm tắt nên theo **mẫu tiêu đề cố định** và **không bao giờ nâng mức thẩm quyền** (một fact `agent_reported` đi qua tóm tắt vẫn là `agent_reported`). Đây là cách chặn "context poisoning" mà cookbook cảnh báo.
  - Kết quả MCP thô nên nằm trong case log (đã có, `_PARTNER_FACT_CHARS = 1200` chỉ là preview, **[mã nguồn local]** `app/_service/_chat.py`), packet chỉ giữ nhãn E + tóm lược. Đây chính là "lightweight references" của Anthropic.
  - Member trả về Leader nên là bản **cô đọng có cấu trúc** (kết luận + nhãn E + điều chưa chắc), cỡ 1–2k token như Anthropic mô tả, không chuyển nguyên transcript.

---

## 2. Shared context (blackboard) cho đa agent

### 2.1 Các mô hình tham khảo

**Google ADK, "Architecting efficient context-aware multi-agent framework for production" (04/12/2025)**: https://developers.googleblog.com/architecting-efficient-context-aware-multi-agent-framework-for-production/
- "Context is a compiled view over a richer stateful system." Bốn tầng: *working context* (prompt mỗi lần gọi, tính lại mỗi lần), *session* (event log bền), *memory* (tri thức dài hạn tìm kiếm được), *artifacts* (dữ liệu lớn, tham chiếu theo tên + version).
- Compaction ở tầng session: LLM tóm tắt các event cũ theo cửa sổ trượt (interval + overlap), ghi lại thành **một event mới** có cờ compaction; event gốc có thể bị bỏ hoặc hạ ưu tiên.
- Cache: chia context thành **stable prefix** (instruction, danh tính, tóm tắt dài hạn) và **variable suffix** (lượt mới, tool output mới). "static instruction" giữ system prompt bất biến để prefix cache còn hiệu lực.
- Artifact: mặc định agent chỉ thấy tên + tóm tắt, gọi `LoadArtifactsTool` khi cần, rồi nội dung bị gỡ lại sau đó ("ephemeral expansion"). "Agents must reach for more information explicitly via tools, rather than being flooded by default."
- Handoff: agent-as-tool nhận prompt tập trung, không có lịch sử; `include_contents="none"` để sub-agent không thấy lịch sử. "Narrative casting": tin nhắn của agent khác được đóng khung lại kiểu "[For context]: Agent B said…" để agent mới không nhầm là lời của chính mình; tool call được gắn với agent đã gọi.

**Letta, shared memory blocks**: https://docs.letta.com/guides/agents/multi-agent-shared-memory
- Một block gắn vào nhiều agent, một agent sửa thì tất cả thấy ngay. Có `read_only`.
- Về đồng thời: `memory_insert` append-only an toàn; `memory_replace` có thể lỗi khi văn bản đích đã đổi; `memory_rethink` last-writer-wins, có thể mất cập nhật. Khuyên: **một agent làm chủ việc sửa lớn**, agent khác chỉ append; mỗi agent sửa section riêng.
- Lưu ý: tài liệu ghi đây là API v1 legacy, Letta khuyên chuyển sang "shared memory repositories"/MemFS.

**Anthropic multi-agent research system** (13/06/2025): https://www.anthropic.com/engineering/multi-agent-research-system: subagent ghi kết quả ra hệ thống ngoài, trả tham chiếu nhẹ cho lead.

**Bài báo blackboard**
- Han & Zhang, bMAS (07/2025): https://arxiv.org/abs/2507.01701. Agent chia sẻ thông tin qua blackboard, agent hành động được chọn theo nội dung blackboard; báo cáo cạnh tranh với MAS SOTA và "spend less tokens" (con số cụ thể chưa đọc được: **[chưa xác minh]** mức tiết kiệm).
- Salemi et al., Google Cloud AI Research (30/09/2025, sửa 31/01/2026): https://arxiv.org/abs/2510.01285. Agent tự quyết có đóng góp hay không thay vì đợi controller giao; theo tóm tắt tìm kiếm, F1 tương đối +9% **[chưa xác minh]**.

**Cognition, "Don't Build Multi-Agents" (12/06/2025)**: https://cognition.com/blog/dont-build-multi-agents (blog của chính tác giả, quan điểm, không phải thực nghiệm). "Actions carry implicit decisions": agent có giả định xung đột cho ra kết quả tồi → phải chia sẻ **quyết định**, không chỉ tin nhắn.

### 2.2 Nên đặt gì vào shared packet, gì để riêng

Tổng hợp từ các nguồn trên (đây là đề xuất của nhóm, mỗi dòng ghi nguồn gốc ý):

| Nội dung | Shared packet | Context riêng của agent | Căn cứ |
|---|---|---|---|
| Mục tiêu ticket, ràng buộc, quyết định đã chốt | Có, đầy đủ | – | Cognition (chia sẻ quyết định), ADK (stable prefix) |
| Fact `tool_verified` / `customer_confirmed` | Có, dạng 1 dòng + nhãn E | – | Anthropic (references), ADK (artifact handle) |
| Kết quả MCP thô | Không; chỉ nhãn E + preview | Nạp khi cần (just-in-time) | Anthropic JIT, ADK ephemeral expansion |
| Phân công: ai làm gì, đang chờ gì | Có | – | MAST FM-1.3 lặp bước, FM-2.4 giấu thông tin (mục 5.3) |
| Câu hỏi còn mở / điều chưa chắc | Có, đánh dấu rõ | – | Cookbook (UNVERIFIED), MAST FM-2.2 |
| Suy luận trung gian, nháp, lần thử tool thất bại | Không | Có, xoá khi xong | Anthropic tool result clearing |
| Tin nhắn của agent khác | Chỉ bản tóm lược có ghi người nói | – | ADK narrative casting |
| Memory dài hạn của từng agent | Không | Có, top-k theo truy vấn | ADK memory reactive/proactive |

### 2.3 Giữ prompt thân thiện với cache

Quy tắc từ OpenAI: https://developers.openai.com/api/docs/guides/prompt-caching
- "Static first, volatile last": instruction và tài liệu tham chiếu ở đầu; timestamp, nội dung theo người dùng ở cuối hoặc ở message sau.
- "Append, don't rewrite": tóm tắt, cắt bớt hay compaction đều có thể làm mất khả năng tái dùng cache. **Kéo dài một message có sẵn** (thay vì thêm message mới) có thể phá việc tái dùng mốc cũ.
- Giữ tool ổn định: không gỡ tool definition; dùng `tool_choice: "none"` hoặc `allowed_tools`; tool search với `defer_loading` thêm tool vào **cuối** context nên giữ cache (https://developers.openai.com/api/docs/guides/tools-tool-search).
- Đổi `text.format`, `reasoning.effort`, `text.verbosity` có thể làm prefix khác đi.
- Theo dõi tỉ lệ hit = cached tokens ÷ tổng input tokens.

Áp vào packet 12k token của ta, thứ tự đề xuất trong mỗi lần gọi:

```
[1] System prompt + vai trò + chính sách (bất biến)                ← cache
[2] Tool schemas (bất biến, không thêm/bớt giữa chừng)             ← cache
[3] Packet phần ỔN ĐỊNH: mục tiêu, ràng buộc, quyết định, fact đã   ← cache, chỉ append
    xác minh — chỉ thêm dòng mới, không viết lại dòng cũ
[4] Tóm tắt event cũ (chỉ viết lại khi vượt ngưỡng, có trễ)          ← mất cache từ đây khi viết lại
[5] Lịch sử hội thoại của agent (append)                            ← cache đến lượt trước
[6] Phần BIẾN ĐỘNG: event mới, trạng thái phân công, ngân sách,     ← không cache
    thời gian, memory recall của lượt này
```

Lý do: với gpt-5.5, mốc cache ngầm định nằm ở các khoảng **2.048 token** (https://developers.openai.com/api/docs/guides/prompt-caching), nên mọi thay đổi ở giữa prompt làm mất toàn bộ phần sau. Nếu packet đang được **render lại toàn bộ** mỗi lần (ví dụ sắp xếp lại items, chèn timestamp ở đầu, hoặc memory recall nằm trước lịch sử), đó là nguyên nhân hợp lý nhất của cache chỉ 58–71%. Cần kiểm chứng bằng cách so hai prompt liên tiếp của cùng một agent (diff byte-by-byte).

---

## 3. Long-term memory

### 3.1 Phân loại và cách hình thành

LangMem conceptual guide: https://langchain-ai.github.io/langmem/concepts/conceptual_guide/
- **Semantic** (fact, tri thức): lưu dạng *profile* (một tài liệu trạng thái hiện tại, cập nhật tại chỗ) hoặc *collection* (nhiều bản ghi, tìm khi chạy, phải đối soát xung đột).
- **Episodic** (trải nghiệm): "preserves successful interactions as learning examples", gồm context, lập luận, kết quả.
- **Procedural** (cách hành xử): lưu thành rule trong prompt, tinh chỉnh qua phản hồi (`create_prompt_optimizer`).
- Hình thành **hot path** (trong hội thoại, thêm độ trễ) hoặc **background** ("between interactions… without impacting response time"). Trích quá nhiều giảm precision, quá ít giảm recall.

Letta/MemGPT: memory block "in-context (pinned to the system prompt)", agent tự sửa qua tool; mọi thứ lưu DB, lấy lại được sau khi bị đẩy khỏi context: https://docs.letta.com/guides/agents/memory. "Sleep-time compute" (17/04/2025): https://arxiv.org/abs/2504.13171. Xử lý trước khi có truy vấn giảm ~5 lần compute lúc test cho cùng độ chính xác; chia sẻ cho nhiều truy vấn liên quan giảm chi phí trung bình 2,5 lần (trên benchmark toán có trạng thái, không phải ticket).

### 3.2 Hợp nhất, khử trùng lặp, xung đột

| Cơ chế | Mô tả | Nguồn |
|---|---|---|
| Mem0 update phase | Với mỗi fact ứng viên, lấy top-*s*=10 memory tương tự (embedding), LLM chọn **ADD / UPDATE / DELETE / NOOP** qua function calling. UPDATE chỉ khi fact mới mang nhiều thông tin hơn; DELETE khi mâu thuẫn. | https://arxiv.org/html/2504.19413v1 (28/04/2025) |
| Mem0g (đồ thị) | Quan hệ lỗi thời được **đánh dấu invalid thay vì xoá**, giữ lịch sử để lập luận theo thời gian. | như trên |
| Zep/Graphiti | Knowledge graph có nhận thức thời gian, giữ quan hệ lịch sử. DMR 94,8% so với MemGPT 93,4%; LongMemEval tăng tới 18,5% độ chính xác, giảm 90% độ trễ. | https://arxiv.org/abs/2501.13956 (20/01/2025) |
| A-MEM | Note kiểu Zettelkasten (mô tả, keyword, tag), tự liên kết với note cũ; "memory evolution" cập nhật thuộc tính note cũ khi có note mới. NeurIPS 2025. Abstract không nêu chi phí token. | https://arxiv.org/abs/2502.12110 |
| LangMem | Collection phải đối soát; có thể xoá/vô hiệu memory lỗi thời hoặc gộp. | https://langchain-ai.github.io/langmem/concepts/conceptual_guide/ |

### 3.3 Chấm điểm khi truy hồi

Generative Agents (Park et al., 2023): https://arxiv.org/abs/2304.03442 (chi tiết đọc ở https://ar5iv.labs.arxiv.org/html/2304.03442)
- điểm = recency + importance + relevance, mỗi thành phần chuẩn hoá min-max về [0,1], trọng số đều bằng 1;
- recency: suy giảm mũ, hệ số **0,995** mỗi giờ (giờ trong game) kể từ lần truy hồi gần nhất;
- importance: LLM chấm 1–10 lúc tạo memory;
- relevance: cosine giữa embedding của memory và truy vấn.

Google ADK có hai kiểu: *reactive* (agent tự gọi `load_memory_tool`) và *proactive* (pre-processor tìm tương tự theo input mới rồi chèn trước khi gọi model): https://developers.googleblog.com/architecting-efficient-context-aware-multi-agent-framework-for-production/. Hệ ta đang dùng kiểu proactive (top-5 / 2.400 ký tự mỗi lượt).

### 3.4 Quên và chất lượng memory: bằng chứng quan trọng nhất

Xiong et al., "How Memory Management Impacts LLM Agents" (21/05/2025, sửa 10/10/2025): https://arxiv.org/abs/2505.16067, số liệu ở https://arxiv.org/html/2505.16067v2
- **Experience-following**: input mới giống input đã lưu thì agent bắt chước output đã lưu, nên **memory sai sẽ lan lỗi**. Có cả "misaligned experience replay": lần chạy trông đúng nhưng là kinh nghiệm có hại.
- **Chỉ thêm memory đã qua bộ chấm nghiêm** (so với thêm tất cả), Bảng 1: +15,5 điểm (RegAgent 55,5→71,0), +25,5 (EHRAgent 13,1→38,5), +18,7 (AgentDriver), +25,5 (CIC-IoT), đồng thời bộ nhớ nhỏ đi 14–58%.
- **Xoá theo lịch sử** (bỏ memory hay đi kèm thất bại) giúp thêm ở một số tác vụ (EHRAgent +8,8%), nhưng **chỉ khi bộ chấm đáng tin**: với GPT-4o-mini làm bộ chấm xoá, AgentDriver bị kém đi. Kết luận: "naive, unbounded memory growth is unnecessary".
- Anthropic memory tool cũng khuyên định kỳ xoá memory lâu không truy cập và giới hạn kích thước file: https://platform.claude.com/docs/en/agents-and-tools/tool-use/memory-tool.

### 3.5 Hiệu quả và chi phí token: số đo công bố

| Hệ | Chất lượng | Token / độ trễ | Nguồn |
|---|---|---|---|
| Full context (LOCOMO) | J = 72,90% (**cao nhất**) | ~26k token/hội thoại; p95 17,1 s | https://arxiv.org/html/2504.19413v1 |
| Mem0 | J = 66,88% | ~7k token; p95 1,44 s | như trên |
| Mem0g | J = 68,44% | ~14k token; p95 2,59 s | như trên |
| Zep | J = 65,99% | >600k token bộ nhớ; p95 2,93 s | như trên |
| OpenAI memory (baseline của bài) | J = 52,90% | – | như trên |
| Anthropic memory + context editing | +39% so với baseline (eval nội bộ) | context editing −84% token trên eval 100 lượt | https://claude.com/blog/context-management |

Đọc kỹ: memory **không** hơn full context về độ chính xác. Nó đổi ~6 điểm chính xác lấy ~73% ít token hơn và độ trễ thấp hơn nhiều. Số 26% của Mem0 là so với memory của OpenAI, không phải so với full context. Lưu ý thêm: đây là benchmark hội thoại cá nhân (LOCOMO), không phải ticket nghiệp vụ.

### 3.6 Ý nghĩa với hệ ta

- Thiết kế hiện tại (chỉ trích sau ticket **thành công**, có provenance event id) đã là dạng "selective addition". Nên siết thêm: chỉ nhận memory mà mọi event nguồn có mức `tool_verified` hoặc `customer_confirmed`; memory chỉ dựa trên `agent_reported` thì không lưu hoặc lưu với cờ thấp.
- Bước hợp nhất nên theo mẫu Mem0: lấy top-10 tương tự → LLM chọn ADD/UPDATE/DELETE/NOOP. Với mâu thuẫn thì **đánh dấu invalid + thời điểm** (Mem0g/Zep) thay vì xoá, để còn audit.
- Truy hồi: thêm recency + importance vào điểm (Generative Agents), và ghi lại memory nào được recall trong ticket nào để sau này **xoá theo lịch sử** (memory liên tục đi kèm ticket thất bại).
- Việc trích memory là việc nền, không ai chờ → chạy bằng **Flex** (giá bằng Batch, rẻ 50%) hoặc Batch (mục 6.6).

---

## 4. Học từ phản hồi / tự cải thiện

### 4.1 Các hướng có bằng chứng

| Hướng | Cơ chế | Bằng chứng | Nguồn |
|---|---|---|---|
| Reflexion | Tự phản tỉnh bằng lời sau phản hồi, lưu vào episodic buffer, không đổi trọng số. | HumanEval pass@1 91% so với GPT-4 80% (2023). | https://arxiv.org/abs/2303.11366 |
| GEPA | Lấy trajectory (lập luận, tool call, tool output), phản tỉnh bằng ngôn ngữ để đề xuất sửa prompt, giữ Pareto frontier các ứng viên. | Hơn GRPO trung bình 6%, tới 20%, dùng **ít hơn tới 35 lần rollout**; hơn MIPROv2 >10%. ICLR 2026 oral. | https://arxiv.org/abs/2507.19457 |
| DSPy GEPA | Metric trả `dspy.Prediction(score, feedback)`; cần `trainset`, `valset` tuỳ chọn; dừng khi hết ngân sách rollout/metric. | – | https://dspy.ai/current/api/optimizers/GEPA/overview/ |
| LangMem prompt optimizer | Sinh lại system prompt từ trajectory + điểm phản hồi (procedural memory). | – | https://langchain-ai.github.io/langmem/concepts/conceptual_guide/ |
| OpenAI cookbook "Self-Evolving Agents" (Bain + OpenAI, đã lưu trữ) | Grader (python, text_similarity, score_model) → metaprompt agent viết lại prompt → chạy lại; `VersionedPrompt` có `revert_to_version`; GEPA làm phương án thay thế (`reflection_lm="gpt-5"`); ngưỡng "pass" ≥75% grader đạt hoặc điểm TB ≥0,85; khuyên người duyệt trước khi triển khai (code mẫu chưa cài). | – | https://developers.openai.com/cookbook/examples/partners/self_evolving_agents/autonomous_agent_retraining |

### 4.2 Lựa chọn của OpenAI: cái gì còn dùng được (10/2026)

| Lựa chọn | Tình trạng | Nguồn |
|---|---|---|
| Prompt optimizer dạng chat trong dashboard | Còn | https://developers.openai.com/api/docs/guides/prompt-optimizer |
| Prompt optimizer dạng dataset + grader | Bỏ cùng Evals (chỉ đọc 31/10/2026, tắt 30/11/2026). Tài liệu cũng cảnh báo prompt tối ưu "perform worse than your original on specific inputs". | như trên |
| Evals API / dashboard | Tắt 30/11/2026; OpenAI chỉ hướng chuyển sang Promptfoo. | https://developers.openai.com/api/docs/deprecations, https://developers.openai.com/cookbook/examples/evaluation/moving-from-openai-evals-to-promptfoo |
| SFT / RFT | Không cho tổ chức mới từ 07/05/2026; dừng hẳn 06/01/2027. RFT chỉ `o4-mini`. | https://developers.openai.com/api/docs/deprecations, https://developers.openai.com/api/docs/guides/reinforcement-fine-tuning |
| Reusable prompts (`v1/prompts`) | Tắt 30/11/2026, chuyển prompt vào code. | https://developers.openai.com/api/docs/deprecations |
| Agent Builder | Tắt 30/11/2026, chuyển sang Agents SDK. | như trên |
| Trace grading | Trang hướng dẫn không ghi deprecation, nhưng chạy trong dashboard Traces và gắn với hệ eval; nên coi là rủi ro. | https://developers.openai.com/api/docs/guides/trace-grading |

### 4.3 Khả thi cho đội nhỏ

| Cách | Khả thi | Ghi chú |
|---|---|---|
| Rule/procedural memory do LLM đề xuất, **gác cổng bằng bộ test riêng** (đang có `self_improve`) | Cao | Đúng mẫu cookbook: version + revert + ngưỡng + người duyệt. |
| GEPA/DSPy chạy offline trên bộ scenario của Agent Studio | Trung bình | Cần metric có *feedback bằng lời* (lý do judge chấm trượt); rollout tốn tiền model thật → chạy bằng Flex/Batch. |
| Reflexion trong một ticket (thử lại sau khi server từ chối số liệu) | Cao | Phản hồi của bộ kiểm tra evidence là tín hiệu rất tốt và miễn phí. |
| RFT/SFT trên OpenAI | **Không** | Platform đóng với tổ chức mới. |
| OpenAI Evals làm cổng | **Không** | Tắt 30/11/2026. |

Cổng an toàn (tổng hợp từ cookbook + Anthropic evals): mỗi thay đổi prompt/rule/memory đều có version; chạy **bộ regression** (phải ~100%) + **bộ capability**; so với baseline trên cùng scenario, nhiều trial (pass^k); có người duyệt; có revert một nút; triển khai dần (Anthropic dùng "rainbow deployments", https://www.anthropic.com/engineering/multi-agent-research-system).

---

## 5. Đánh giá, cổng chất lượng và metric

### 5.1 Nguyên tắc (Anthropic, "Demystifying evals for AI agents", 09/01/2026)

Nguồn: https://www.anthropic.com/engineering/demystifying-evals-for-ai-agents
- Khái niệm: task, trial, grader, transcript, **outcome** (trạng thái cuối của môi trường, ví dụ đặt chỗ có thật trong DB, không phải agent *nói* đã đặt).
- "grade what the agent produced, not the path it took". Kiểm tra cứng thứ tự bước sẽ phạt cách làm hợp lệ.
- **pass@k** (ít nhất 1 lần đúng trong k) và **pass^k** (đúng cả k lần). Ví dụ 75%/trial → pass^3 ≈ 42%. Với agent gặp khách hàng thì pass^k mới là số quan trọng. Metric gốc từ τ-bench (17/06/2024): gpt-4o <50% tác vụ, pass^8 <25% ở miền retail; chấm bằng **so trạng thái DB cuối** với trạng thái đích: https://arxiv.org/abs/2406.12045.
- Bắt đầu với **20–50 task lấy từ lỗi thật**; tách *capability eval* (đang thấp, để leo) và *regression eval* (phải ~100%).
- Ba loại grader: code (nhanh, rẻ, giòn), model (linh hoạt, cần hiệu chỉnh với người), người (chuẩn vàng, đắt). "Read the transcripts!": CORE-Bench từ 42% lên 95% sau khi sửa lỗi grader và spec mơ hồ.
- Nhiều lớp: eval tự động, giám sát production, A/B, phản hồi người dùng, đọc transcript thủ công.

### 5.2 OpenAI

- Agent evals: bắt đầu bằng trace (model call, tool call, guardrail, handoff của một lần chạy), tạo grader trên trace, rồi chuyển sang dataset + eval run lặp lại được: https://developers.openai.com/api/docs/guides/agent-evals, https://developers.openai.com/api/docs/guides/trace-grading.
- Cảnh báo: phần dataset/eval run nằm trong Evals platform sắp tắt (mục 4.2) → giữ harness eval ở phía ta.

### 5.3 Phân loại lỗi đa agent (MAST)

Cemri et al., "Why Do Multi-Agent LLM Systems Fail?" (v1 17/03/2025, v3 26/10/2025): https://arxiv.org/abs/2503.13657, bảng ở https://arxiv.org/html/2503.13657. 1.642 trace từ 7 framework; người với người đồng thuận κ=0,88; bộ chấm LLM (o1, few-shot) accuracy 0,94, κ=0,77.

| Mã | Lỗi | Tỉ lệ | Ở hệ ta nên đo bằng |
|---|---|---|---|
| FM-1.1 | Không tuân thủ đặc tả task | 11,8% | Judge kiểm tra yêu cầu ticket |
| FM-1.2 | Không tuân thủ vai trò | 1,5% | Member gọi tool ngoài phạm vi |
| FM-1.3 | Lặp bước | 15,7% | Cùng MCP + cùng tham số gọi ≥2 lần/ticket |
| FM-1.4 | Mất lịch sử hội thoại | 2,8% | Hỏi lại điều đã có trong packet |
| FM-1.5 | Không biết điều kiện dừng | 12,4% | Số lượt Leader vượt ngân sách |
| FM-2.1 | Reset hội thoại | 2,2% | – |
| FM-2.2 | Không hỏi lại khi mơ hồ | 6,8% | Judge |
| FM-2.3 | Lạc đề | 7,4% | Judge |
| FM-2.4 | Giấu thông tin | 0,85% | Fact member có nhưng không lên blackboard |
| FM-2.5 | Bỏ qua input agent khác | 1,9% | Leader không trích E của member |
| FM-2.6 | Lập luận và hành động lệch nhau | 13,2% | Judge trên trace |
| FM-3.1 | Kết thúc sớm | 6,2% | Trả lời khi còn câu hỏi mở |
| FM-3.2 | Không/thiếu kiểm chứng | 8,2% | **Bộ kiểm tra evidence của server** (đã có) |
| FM-3.3 | Kiểm chứng sai | 9,1% | Số trích dẫn sai nhãn E |

Can thiệp trong bài: sửa đặc tả vai trò/quy trình ChatDev **+9,4%** tỉ lệ thành công; thêm bước kiểm chứng mục tiêu cấp cao **+15,6%**.

### 5.4 Bộ metric đề xuất cho hệ ta

| Metric | Định nghĩa | Căn cứ |
|---|---|---|
| Tỉ lệ giải quyết (outcome) | Ticket đạt trạng thái cuối đúng (kiểm bằng DB/MCP đọc), không dựa vào lời agent | Anthropic outcome; τ-bench |
| pass^k trên scenario | Chạy mỗi scenario k=3–5 lần | Anthropic, τ-bench |
| Groundedness | % con số/khẳng định trong tin nhắn cuối khớp evidence được trích; số lần server từ chối | Bộ kiểm tra đã có; MAST FM-3.2/3.3 |
| Độ chính xác tool call | % tool call hợp lệ / cần thiết; số call lặp | OpenAI agent evals; MAST FM-1.3 |
| **Chi phí / ticket giải quyết** | (input chưa cache × giá + cached × giá + output × giá) ÷ số ticket đạt | Bảng giá OpenAI |
| Cache hit rate | cached_tokens ÷ input_tokens, theo agent và theo vai trò | OpenAI prompt caching |
| Số lần gọi model mạnh / ticket | Đang 9–15 | Số đo nội bộ |
| Độ trễ p50/p95 tới tin nhắn đầu tiên và tin nhắn cuối | – | OpenAI cost/latency guide |
| Tỉ lệ lỗi MAST | Judge gán nhãn trên mẫu trace hằng tuần | MAST |

### 5.5 Giám sát online

- Lưu trace đầy đủ cho mọi ticket (đã có token accounting theo agent). Anthropic: tracing production giúp chẩn đoán lỗi có hệ thống, và họ theo dõi *mẫu quyết định* thay vì đọc nội dung hội thoại để bảo vệ riêng tư: https://www.anthropic.com/engineering/multi-agent-research-system.
- Hằng tuần lấy mẫu trace → judge gán nhãn MAST → lỗi mới vào bộ capability eval (vòng "20–50 task từ lỗi thật").

---

## 6. Đòn bẩy chi phí token trên OpenAI (ngoài prompt caching)

### 6.1 Giá hiện hành (USD / 1M token, mức Standard, <272K context)

Nguồn: https://developers.openai.com/api/docs/pricing

| Model | Input | Cached | Output | Batch / Flex |
|---|---|---|---|---|
| gpt-5.5 (Leader) | 5,00 | 0,50 | 30,00 | −50% |
| gpt-5.4 | 2,50 | 0,25 | 15,00 | −50% |
| gpt-5.4-mini (member) | 0,75 | 0,075 | 4,50 | −50% |
| gpt-5.4-nano | 0,20 | 0,02 | 1,25 | −50% |
| gpt-5.6-sol | 4,00 | 0,40 | 20,00 | −50% |
| gpt-5.6-terra | 2,00 | 0,20 | 12,00 | −50% |
| gpt-5.6-luna | 0,20 | 0,02 | 1,20 | −50% |

Mức "Fast" (trước là Priority) đắt hơn khoảng 2 lần, riêng input gpt-5.5 là 2,5 lần. Endpoint xử lý theo vùng cộng thêm 10% với model ra từ 05/03/2026. Nguồn: như trên.

### 6.2 Ước tính chi phí model mạnh cho một ticket **[ước tính]**

Giả định: 12 lần gọi gpt-5.5 × 14.000 input token, cache 65%, **output trung bình 800 token/lần kể cả reasoning** (giả định, cần lấy số thật từ token accounting).
- Input: 58.800 chưa cache × $5 + 109.200 cached × $0,5 ≈ $0,29 + $0,05 = **$0,35**
- Output: 9.600 × $30 ≈ **$0,29**
- Tổng ≈ **$0,64/ticket** (dải 9–15 lần gọi, cache 58–71%: khoảng $0,48–$0,99).
- Cache từ 65% lên 90%: tiết kiệm ≈ $0,19/ticket (~30%). Giảm số lần gọi từ 12 xuống 6: tiết kiệm ≈ 50%. Giảm output/reasoning 30%: tiết kiệm ≈ $0,09.
- Kết luận: **số lần gọi model mạnh** và **phần input chưa cache** là hai đòn bẩy lớn nhất; output là đòn bẩy thứ ba.

### 6.3 Quy tắc prompt cache áp cho gpt-5.5 / gpt-5.4-mini

Nguồn: https://developers.openai.com/api/docs/guides/prompt-caching
- gpt-5.5: mốc cache ngầm ở các khoảng **2.048 token**. Với prompt 14k mà chỉ phần cuối thay đổi, trần thực tế ~85–88% (phần sau mốc cuối không cache). Mức tối thiểu tuỳ cấu hình request.
- Model trước GPT-5.6: dùng `prompt_cache_key` ổn định. Một key chỉ nên ~**15 request/phút**; vượt thì chia key theo ánh xạ tất định. Hệ ta đặt key `workforce:{agent_id}` (**[mã nguồn local]** `_apply_prompt_cache_key`, bật bằng `WORKFORCE_PROMPT_CACHE_KEY`). Nếu một Leader phục vụ nhiều room cùng lúc thì có thể vượt 15 RPM/key → cân nhắc `workforce:{agent_id}:{hash(room) % N}`.
- Retention: `prompt_cache_retention` = `in_memory` (5–10 phút, tối đa 1 giờ) hoặc `24h`. `24h` có cho gpt-5.5, gpt-5.4 (danh sách **không** ghi gpt-5.4-mini). Tổ chức không bật ZDR **mặc định đã là `24h`**.
- GPT-5.6+ khác hẳn: tối thiểu 1.024 token, đọc cache 0,1×, **ghi cache 1,25×**, TTL 30 phút, routing tự động, có chế độ breakpoint tường minh. Nếu chuyển model phải tính lại.
- Mã local cho thấy model OpenAI có cả đường Chat Completions (`_openai_chat`, gọi `chat.completions.create`) và Responses (`_openai_response`), key gắn qua `extra_body` **[mã nguồn local]**. Cần xác nhận Leader đang chạy đường nào. Nếu là Chat Completions thì reasoning items **không** được truyền lại giữa các lần gọi tool, trái với khuyến nghị ở mục 1.4.

### 6.4 `reasoning.effort`, `text.verbosity`, `max_output_tokens`

Nguồn: https://developers.openai.com/api/docs/guides/gpt-5.5, https://developers.openai.com/api/docs/guides/reasoning
- gpt-5.5 nhận `none`, `low`, `medium` (mặc định), `high`, `xhigh`. "Higher reasoning effort isn't automatically better", chỉ tăng khi eval cho thấy lợi. Với tool/đa bước, thử `low` trước `none`.
- `text.verbosity` mặc định `medium`; `low` thường là điểm khởi đầu tốt hơn cho câu trả lời ngắn, và trên gpt-5.5 ngắn hơn rõ so với gpt-5.4.
- Reasoning token tính như output và chiếm context. `max_output_tokens` giới hạn chung reasoning + output; chạm trần thì `status: incomplete`, có thể chưa có chữ nào. OpenAI gợi ý chừa ≥25.000 token khi mới bắt đầu, nên đặt trần thấp là rủi ro, phải đo trước.
- Đổi effort/verbosity giữa các lần gọi có thể làm khác prefix cache (mục 2.3) → cố định theo vai trò, không đổi theo lượt.
- Hướng dẫn GPT-5.5 cũng khuyên: prompt theo **kết quả** (outcome, tiêu chí thành công, hành động được phép, quy tắc evidence, dạng đầu ra), đặt điều kiện dừng rõ, bỏ schema đầu ra khỏi prompt và dùng Structured Outputs, không cần chèn ngày hiện tại.

### 6.5 Định tuyến model / cascade

- FrugalGPT (09/05/2023): cascade đạt hiệu năng GPT-4 với chi phí thấp hơn tới 98%: https://arxiv.org/abs/2305.05176.
- RouteLLM (06/2024, v4 02/2025): router học từ dữ liệu preference giảm chi phí "over 2 times" mà không giảm chất lượng: https://arxiv.org/abs/2406.18665.
- OpenAI: chọn model nhỏ nhất đạt độ chính xác chấp nhận được, giảm số request: https://developers.openai.com/api/docs/guides/cost-optimization.
- Với hệ ta: Leader chỉ cần model mạnh ở bước **lập kế hoạch** và **soạn tin nhắn cuối**. Các bước trung gian (đọc báo cáo member, quyết định mời ai, kiểm tra đủ evidence chưa) có thể chạy model nhỏ hơn hoặc `reasoning.effort=low`, sau khi đo bằng eval.
- Bảng giá cho thấy gpt-5.6-luna ($0,20/$1,20) rẻ hơn gpt-5.4-mini ($0,75/$4,50) khoảng 73%, và gpt-5.6-sol ($4/$20) rẻ hơn gpt-5.5 ($5/$30). Đây chỉ là **ứng viên**, phải chạy bộ test Agent Studio trước khi đổi; chưa có nguồn nào so chất lượng các model này trên tác vụ như của ta.

### 6.6 Batch và Flex

- Batch: rẻ 50%, xong trong 24 giờ, hỗ trợ `/v1/responses`, rate limit riêng, tối đa 50.000 request/batch: https://developers.openai.com/api/docs/guides/batch.
- Flex: `service_tier: "flex"`, tính **giá Batch**, chậm hơn, có thể lỗi 429 "Resource Unavailable" (không tính tiền), khi đó thử lại hoặc chuyển `auto`: https://developers.openai.com/api/docs/guides/flex-processing.
- Áp dụng: trích/hợp nhất memory sau ticket, đề xuất rule `self_improve`, chạy bộ test Agent Studio, judge chấm trace hằng tuần. Không dùng cho đường trả lời khách.

### 6.7 Structured Outputs, kích thước tool schema, tool search

- Structured Outputs đảm bảo tuân thủ JSON Schema, đỡ phải retry khi parse lỗi. Request đầu với schema mới có thêm độ trễ, các request sau thì không: https://developers.openai.com/api/docs/guides/structured-outputs. Hợp cho báo cáo member gửi Leader và cho bước trích memory.
- Tool search (`tool_search` + `defer_loading`, chỉ gpt-5.4 trở lên trên Responses API): model chỉ thấy tên + mô tả, schema nạp khi cần; tool mới thêm ở **cuối** context nên giữ cache; khuyên mỗi namespace <10 hàm: https://developers.openai.com/api/docs/guides/tools-tool-search. Hữu ích khi member có nhiều MCP tool của đối tác.

### 6.8 Predicted Outputs: không áp dụng

Chỉ hỗ trợ GPT-4o, GPT-4o-mini, GPT-4.1, GPT-4.1-mini, GPT-4.1-nano, **không dùng được với `tools`**, và token dự đoán bị loại vẫn tính tiền: https://developers.openai.com/api/docs/guides/predicted-outputs. Không hợp với hệ ta.

---

## 7. Áp dụng cho dự án

Thang: Tác động / Công sức / Rủi ro = Cao (C), Trung bình (TB), Thấp (T). Xếp theo thứ tự ưu tiên.

| # | Thay đổi | Thành phần | Tác động | Công sức | Rủi ro | Nguồn chính | Metric chứng minh |
|---|---|---|---|---|---|---|---|
| 1 | Sắp lại prompt mỗi lần gọi theo bố cục mục 2.3: phần bất biến → packet ổn định chỉ append → lịch sử → phần biến động (event mới, recall, thời gian) ở cuối. Kiểm tra bằng diff hai prompt liên tiếp. | Shared Context packet, prompt builder | C | T–TB | T | OpenAI prompt caching; Google ADK | Cache hit model mạnh từ 58–71% lên ≥85%; $ input/ticket |
| 2 | Tóm tắt event cũ chỉ khi vượt ngưỡng **và** giải phóng đủ N token (có trễ, kiểu `clear_at_least`); tóm tắt theo mẫu tiêu đề cố định; không bao giờ nâng mức thẩm quyền. | LLM summarization của blackboard | C | T | T | Anthropic context editing; OpenAI session memory cookbook | Số lần viết lại tóm tắt/ticket; cache hit; số lần bị từ chối evidence không tăng |
| 3 | Giảm số lần gọi Leader: member trả báo cáo **cô đọng có cấu trúc** (Structured Outputs: kết luận, nhãn E, điều chưa chắc, ≤1–2k token); Leader đợi gom đủ rồi mới gọi model. | TeamSay / AgentInvite, Leader loop | C | TB | TB | Anthropic multi-agent + context engineering; OpenAI structured outputs | Lần gọi model mạnh/ticket từ 9–15 xuống ≤6; tỉ lệ giải quyết không giảm |
| 4 | Cố định `reasoning.effort` và `text.verbosity` theo vai trò; thử `verbosity=low` cho Leader, `effort=low` cho các bước trung gian, có eval kiểm. | Model config Leader/member | TB–C | T | TB | OpenAI GPT-5.5 guide; reasoning guide | Output token/ticket; pass^k trên scenario |
| 5 | Kiểm tra đường API của Leader; nếu là Chat Completions thì chuyển sang Responses và truyền lại reasoning items (`encrypted_content` khi `store=false`) giữa các lần gọi tool. | `_openai_chat` / `_openai_response` | TB | TB | TB | OpenAI reasoning guide; reasoning items cookbook | Cache hit; reasoning token/ticket; chất lượng không giảm |
| 6 | Lọc memory chặt: chỉ lưu khi event nguồn là `tool_verified`/`customer_confirmed`; hợp nhất kiểu ADD/UPDATE/DELETE/NOOP với top-10 tương tự; mâu thuẫn thì đánh dấu invalid + thời điểm. | Long-term memory extraction | C (chất lượng) | TB | T | Xiong et al. 2505.16067; Mem0 2504.19413; Zep | Kích thước memory; pass rate scenario có/không memory; ticket lặp lỗi cũ |
| 7 | Ghi memory nào được recall ở ticket nào; định kỳ bỏ memory hay đi kèm ticket thất bại hoặc lâu không dùng; thêm recency/importance vào điểm truy hồi. | Memory recall | TB | TB | TB (bộ chấm yếu có thể xoá nhầm) | Xiong et al.; Generative Agents; Anthropic memory tool | Precision recall (judge); pass rate |
| 8 | Chạy việc nền bằng Flex: trích memory, `self_improve`, bộ test Agent Studio, judge trace. | Memory, self_improve, Agent Eval | TB (−50% phần đó) | T | T | OpenAI Flex, Batch, pricing | $ việc nền/tuần |
| 9 | Coi mọi thay đổi prompt/rule/memory là một bản phát hành: version + regression (~100%) + capability + pass^k + người duyệt + revert; không phụ thuộc OpenAI Evals/prompt optimizer dạng dataset. | Agent Studio tests, self_improve | C (an toàn) | TB | T | Anthropic evals; OpenAI self-evolving cookbook; OpenAI deprecations | Không có regression lọt; thời gian revert |
| 10 | Judge gán nhãn MAST hằng tuần trên mẫu trace; lỗi mới thành task eval (20–50 task từ lỗi thật). | Trace / token accounting | TB | TB | T | MAST 2503.13657; Anthropic evals | Phân bố lỗi theo FM; xu hướng FM-1.3, FM-3.x |
| 11 | Dashboard metric mục 5.4, trọng tâm **chi phí / ticket giải quyết** và pass^k. | Token accounting | TB | T–TB | T | Anthropic evals; τ-bench; OpenAI pricing | Chính các metric đó, theo tuần |
| 12 | GEPA/DSPy offline cho prompt Leader và member trên bộ scenario, metric trả kèm lý do trượt. | Agent Studio | TB–C | C | TB | GEPA 2507.19457; DSPy GEPA | Pass rate scenario trước/sau; không regression |
| 13 | Chia `prompt_cache_key` khi một agent vượt ~15 RPM (ví dụ hash room % N). | `_apply_prompt_cache_key` | T (demo) / TB (tải thật) | T | T | OpenAI prompt caching | Cache hit lúc cao điểm |
| 14 | Đánh giá model rẻ hơn (gpt-5.6-luna cho member, gpt-5.6-sol cho Leader) bằng bộ test trước khi đổi; lưu ý luật cache GPT-5.6 khác (ghi 1,25×, TTL 30 phút). | Model routing | C ($) | T–TB | TB–C | OpenAI pricing; prompt caching | Chi phí/ticket giải quyết với pass^k không giảm |
| 15 | Tool search / `defer_loading` khi member có nhiều MCP tool. | Member tool list | T–TB | TB | T | OpenAI tool search | Input token/lần gọi của member |

**Không nên làm lúc này**
- RFT/SFT trên OpenAI: platform đã đóng với tổ chức mới (mục 4.2).
- Chuyển bộ test sang OpenAI Evals hoặc dựa vào prompt optimizer dạng dataset: tắt 30/11/2026.
- Dùng compaction mã hoá của OpenAI thay blackboard: không đọc được nên không trích dẫn/audit được (mục 1.4). Có thể dùng sau này cho context riêng của từng agent.
- Predicted Outputs: không hỗ trợ model GPT-5.x và không dùng được với tools.
- Tăng `reasoning.effort` cho Leader khi chưa có eval chứng minh lợi.

**Thứ tự gợi ý trước demo 22/10**: #1, #2, #4, #8, #11 (rủi ro thấp, đo được ngay). Sau demo: #3, #5, #6, #9, #10. Khi có bộ scenario ổn định: #12, #14.
