# Nghiên cứu giải pháp cho 4 vấn đề của nền tảng Workforce

Ngày nghiên cứu: 13/10/2026. Phạm vi: các nguồn gốc (tài liệu chính thức, blog kỹ thuật của chính hãng, mã nguồn GitHub, bài báo). Mỗi khẳng định có kèm URL. Ngày của nguồn ghi trong ngoặc khi nguồn có ghi.

Quy ước:
- **[chưa xác minh]**: chỉ thấy qua kết quả tìm kiếm hoặc nguồn thứ cấp, chưa đọc được trang gốc.
- **[mã nguồn local]**: đọc trong `platform_VP/agentscope/src` (AgentScope `2.0.10dev`, bản fork của nhóm). Khi khác với upstream thì ghi rõ.
- Số liệu là số do chính hãng/tác giả công bố, chưa được nhóm kiểm chứng lại.

Bối cảnh: Supervisor mở một phiên cho một hồ sơ khách hàng và mời các agent chuyên môn vào. Agent Builder tạo agent qua chat cho người dùng nghiệp vụ của văn phòng quản lý toà nhà. Model đi qua gateway tương thích OpenAI (gpt-5.x-mini).

---

## 1. Cộng tác đa agent trong phiên do Supervisor dẫn

### 1.1 Các nguồn nói gì

**Anthropic: "How we built our multi-agent research system" (13/06/2025)**: https://www.anthropic.com/engineering/multi-agent-research-system
- Kiến trúc orchestrator–worker: agent dẫn dắt (lead) lập kế hoạch rồi tạo các subagent chạy song song. Subagent trả kết quả về để lead tổng hợp.
- Mỗi bản giao việc cho subagent cần có: **mục tiêu, định dạng đầu ra, hướng dẫn về công cụ/nguồn nên dùng, và ranh giới nhiệm vụ rõ ràng**. Khi giao việc mơ hồ, các subagent làm trùng việc nhau. Ví dụ trong bài: hai subagent cùng điều tra chuỗi cung ứng 2025, trong khi một subagent khác lại đi nghiên cứu khủng hoảng chip 2021.
- Quy tắc co giãn công sức (effort scaling) được đưa thẳng vào prompt:
  - tra cứu đơn giản: 1 agent, 3–10 lần gọi tool;
  - so sánh trực tiếp: 2–4 subagent, mỗi subagent 10–15 lần gọi;
  - nghiên cứu phức tạp: hơn 10 subagent, mỗi subagent một phần việc riêng.
- Chi phí: agent tốn khoảng 4 lần token so với chat; hệ đa agent khoảng 15 lần. Riêng lượng token dùng giải thích 80% phương sai hiệu năng trên BrowseComp. Cộng thêm số lần gọi tool và lựa chọn model thì giải thích được 95%.
- Hiệu năng: lead Opus 4 cùng subagent Sonnet 4 hơn agent đơn Opus 4 là 90,2% trên bộ eval nghiên cứu nội bộ.
- Lead lưu kế hoạch vào Memory, vì context bị cắt khi vượt 200.000 token.
- Để tránh hiện tượng "tam sao thất bản", subagent ghi kết quả ra hệ thống ngoài (artifact) rồi chỉ trả về tham chiếu nhẹ cho lead.
- Song song hoá: lead chạy 3–5 subagent cùng lúc, mỗi subagent gọi từ 3 tool song song. Nhờ đó thời gian nghiên cứu giảm tới 90% với truy vấn phức tạp.
- Lỗi gặp ở các bản đầu: sinh 50 subagent cho câu hỏi đơn giản; tìm mãi những nguồn không tồn tại; các agent cập nhật cho nhau quá nhiều làm nhau xao nhãng.
- Cách đánh giá: bắt đầu với khoảng 20 truy vấn lấy từ cách dùng thực tế. Một LLM judge chấm điểm 0,0–1,0 kèm pass/fail bằng một prompt duy nhất. Con người kiểm thử thêm để bắt các lỗi mà tự động không bắt được.
- Hạn chế: thực thi đồng bộ. Lead phải chờ cả lượt subagent xong nên không điều phối được giữa chừng.

**Anthropic: "Building effective agents" (19/12/2024)**: https://www.anthropic.com/engineering/building-effective-agents
- Phân biệt *workflow* (đường đi định sẵn trong code) với *agent* (LLM tự điều khiển quá trình của mình).
- Các mẫu: prompt chaining, routing, parallelization (sectioning/voting), orchestrator-workers, evaluator-optimizer (một LLM sinh, một LLM phê bình, lặp đến khi đạt tiêu chí).
- Lời khuyên: bắt đầu từ giải pháp đơn giản nhất. Đầu tư vào ACI (giao diện agent–máy) ngang với UI. Dùng nguyên tắc "poka-yoke" khi thiết kế tham số tool. Luôn đặt điều kiện dừng, ví dụ số vòng lặp tối đa.

**Cognition (Walden Yan): "Don't Build Multi-Agents" (12/06/2025)**: https://cognition.com/blog/dont-build-multi-agents
- Nguyên tắc 1: chia sẻ context, cụ thể là chia sẻ **toàn bộ trace của agent, không chỉ từng message**.
- Nguyên tắc 2: **hành động mang theo quyết định ngầm**. Các agent có giả định xung đột nhau sẽ cho ra kết quả tồi. Ví dụ Flappy Bird: subagent 1 làm nền theo phong cách Mario, subagent 2 làm con chim không khớp.
- Mặc định nên dùng agent đơn luồng tuyến tính. Với tác vụ dài, thêm một model nén lịch sử thành các sự kiện và quyết định chính.
- Nhận xét về subagent của Claude Code (6/2025): chúng chủ yếu trả lời câu hỏi hẹp, không viết code song song. Lợi ích là phần điều tra không làm bẩn lịch sử của agent chính.

**OpenAI Agents SDK**: https://openai.github.io/openai-agents-python/multi_agent/ và https://openai.github.io/openai-agents-python/handoffs/
- *Agents as tools* (`Agent.as_tool()`): manager giữ quyền hội thoại và tổng hợp kết quả. Dùng khi một agent phải sở hữu câu trả lời cuối hoặc khi cần áp guardrail chung.
- *Handoffs*: chuyển hẳn quyền điều khiển cho chuyên gia. Mỗi handoff là một tool `transfer_to_<agent>`.
  - Mặc định agent nhận thấy toàn bộ lịch sử. `input_filter` lọc những gì agent sau được thấy.
  - `input_type` là schema metadata do model sinh, ví dụ `reason`. Trạng thái ứng dụng phải đặt trong `RunContextWrapper.context`, và kiểm tra quyền trong `on_handoff`.
  - `nest_handoff_history` (beta, mặc định tắt) gói lịch sử cũ thành tóm tắt. Nó **không** che dữ liệu nhạy cảm.
- Điều phối bằng code "deterministic và predictable hơn" về tốc độ, chi phí và hiệu năng. Các cách: structured output để phân loại, chain, vòng `while` giữa agent làm và agent đánh giá, `asyncio.gather`.

**OpenAI: "A practical guide to building agents" (PDF)**: https://cdn.openai.com/business-guides-and-resources/a-practical-guide-to-building-agents.pdf
- Ưu tiên tận dụng tối đa một agent trước. Chỉ tách agent khi logic có quá nhiều nhánh if-else hoặc khi tool bị quá tải.
- "Vấn đề không chỉ là số lượng tool mà là độ giống/chồng lấn". Có hệ thống chạy tốt với hơn 15 tool rõ ràng, có hệ thống vướng với dưới 10 tool chồng lấn.
- Hai mẫu: *manager* (cạnh của đồ thị là tool call) và *decentralized* (cạnh là handoff).
- Đưa con người vào khi vượt ngưỡng thất bại, hoặc khi hành động rủi ro cao, không đảo ngược được.
- (Ngày phát hành không in rõ trong phần text trích ra; nhiều khả năng là 2025, **[chưa xác minh]**.)

**LangChain/LangGraph**: https://docs.langchain.com/oss/python/langchain/multi-agent
- Năm mẫu: Subagents (supervisor gọi agent như tool), Handoffs, Skills, Router, Custom workflow. Trang này coi context engineering là "trung tâm của thiết kế multi-agent". Subagent không giữ trạng thái và chạy trong context cô lập.
- Bảng so sánh của LangChain (không ghi ngày):

  | Mẫu | Gọi lần đầu | Lặp lại yêu cầu (lượt 2 / tổng) | Đa miền: lần gọi / token |
  |---|---|---|---|
  | Subagents | 4 | 4 / 8 | 5 / ~9K |
  | Handoffs | 3 | 2 / 5 | 7+ / ~14K+ |
  | Skills | 3 | 2 / 5 | 3 / ~15K |
  | Router | 3 | 3 / 6 | 5 / ~9K |

- `langgraph-supervisor`: https://github.com/langchain-ai/langgraph-supervisor-py
  - Có `output_mode` = `full_history` hoặc `last_message`.
  - Có tool `forward_message` để chuyển nguyên văn câu trả lời của worker, tránh supervisor diễn giải lại và đỡ tốn token.
  - Hỗ trợ supervisor nhiều cấp.
  - README nay **không còn khuyến nghị thư viện này** cho đa số trường hợp mà khuyên tự cài pattern supervisor bằng tool để kiểm soát context tốt hơn.
- `langgraph-swarm`: https://github.com/langchain-ai/langgraph-swarm-py. Các agent tự handoff cho nhau, và hệ thống nhớ agent active cuối (cần checkpointer).

**Microsoft Magentic-One / Agent Framework**
- Bài gốc (04/11/2024): https://www.microsoft.com/en-us/research/articles/magentic-one-a-generalist-multi-agent-system-for-solving-complex-tasks/. Paper: https://arxiv.org/html/2411.04468v1
  - Vòng ngoài là **Task Ledger**, gồm facts, educated guesses và plan.
  - Vòng trong là **Progress Ledger**. Mỗi bước trả lời 5 câu hỏi:
    1. yêu cầu đã thoả mãn chưa;
    2. có đang lặp lại không;
    3. có tiến triển không;
    4. ai nói tiếp;
    5. giao chỉ dẫn hay câu hỏi gì cho người đó.
  - Bộ đếm stall vượt ngưỡng (≤2 trong thí nghiệm) thì thoát ra vòng ngoài để phản tư và lập lại kế hoạch. Task ledger được cập nhật chứ không xoá. Context của các agent được reset sau mỗi lần cập nhật kế hoạch.
- AutoGen đã vào **chế độ bảo trì**. README ghi: "New users should start with Microsoft Agent Framework" (https://github.com/microsoft/autogen).
- Microsoft Agent Framework (trang Magentic, ms.date 04/09/2026): https://learn.microsoft.com/en-us/agent-framework/user-guide/workflows/orchestrations/magentic
  - `MagenticBuilder(max_round_count=10, max_stall_count=3, max_reset_count=2)`.
  - Có `enable_plan_review`: con người duyệt hoặc sửa kế hoạch (Python mặc định tắt, .NET mặc định bật).
  - Sự kiện `PLAN_CREATED`, `REPLANNED`, `PROGRESS_LEDGER_UPDATED`. Ledger có các trường `is_request_satisfied`, `is_in_loop`, `is_progress_being_made`, `next_speaker`, `instruction_or_question`.
  - `progress_ledger_prompt` tuỳ biến phải giữ nguyên JSON schema.
  - Có cảnh báo: chưa kiểm chứng hiệu quả khi dùng ngoài thiết kế Magentic-One gốc.
- AutoGen SelectorGroupChat: https://microsoft.github.io/autogen/stable/user-guide/agentchat-user-guide/selector-group-chat.html
  - Model chọn người nói tiếp dựa trên `name`/`description` và lịch sử.
  - Mặc định không cho cùng một agent nói hai lượt liền.
  - `selector_func`/`candidate_func` cho phép áp luật bằng code. Có thể cho planning agent nói đầu tiên và quay lại sau mỗi lượt chuyên gia.
- Điều kiện dừng có thể ghép bằng `|` và `&`: MaxMessage, TextMention, TokenUsage, Timeout, Handoff, SourceMatch, External, StopMessage, FunctionCall, Functional… (https://microsoft.github.io/autogen/stable/user-guide/agentchat-user-guide/tutorial/termination.html)

**CrewAI hierarchical process**: https://docs.crewai.com/en/learn/hierarchical-process
- Cần `manager_llm` hoặc `manager_agent`. Manager giao việc theo vai trò, khả năng và tool của từng agent, rồi kiểm tra kết quả (trang không mô tả cơ chế kiểm tra).
- `allow_delegation` mặc định tắt.

**AgentScope (khung nền đang dùng)**
- Tài liệu v1.0: https://doc.agentscope.io/tutorial/task_pipeline.html và https://doc.agentscope.io/tutorial/workflow_multiagent_debate.html
  - `MsgHub(participants, announcement)` phát lời của mỗi participant tới các participant khác qua `observe`. Có `add`/`delete`/`broadcast`; thành viên mới không nhận lại tin cũ.
  - `sequential_pipeline` và `fanout_pipeline` (`asyncio.gather`).
  - Ví dụ debate: Alice và Bob tranh luận trong MsgHub, moderator đứng **ngoài** hub. Moderator trả structured output `JudgeModel{finished: bool, correct_answer}`. Ví dụ **không có giới hạn số vòng**.
- AgentScope 2.0 (README, tin 2026-09): https://github.com/agentscope-ai/agentscope
  - `TeamPipeline` cho leader giao việc cho thành viên.
  - `ModelRouterMiddleware`.
  - `A2AAgent`.
  - Phần Agent Service có "Agent Team: leader–worker orchestration and task planning".
- `TeamPipeline` (upstream https://raw.githubusercontent.com/agentscope-ai/agentscope/main/src/agentscope/pipeline/_team_pipeline.py, đã đối chiếu **[mã nguồn local]**):
  - Leader có một tool ngoài `TeamAssign(member, prompt)`. Mô tả tham số `prompt` ghi: "It cannot see your context, so include everything it needs".
  - Member chạy trong context riêng, và leader **chỉ thấy câu trả lời cuối**.
  - Các lượt giao trong cùng một round chạy song song; nếu giao cho cùng một member thì chạy tuần tự.
  - **Member không nói chuyện trực tiếp với nhau.**
  - `reset_members=True` (mặc định) xoá context của member sau mỗi lần leader trả lời.
  - Hỗ trợ HITL theo `reply_id`.
- `GoalPipeline` (upstream `_goal_pipeline.py`): executor và verifier chạy vòng lặp. Verifier trả `pass | fail | impossible` kèm message; dừng khi đạt `max_iters`. Lưu ý: `max_retries` được lưu nhưng không được dùng.

**Google A2A**: https://a2a-protocol.org/latest/specification/
- Bản 1.0.0, có tin "A2A joins the Agentic AI Foundation" ngày 27/08/2026.
- Đối tượng chính: Agent Card, Task (có trạng thái), Message, Part (text/file/data), Artifact, `contextId`.
- Trạng thái Task: submitted, working, input-required, auth-required, completed, failed, canceled, rejected. Đây là bộ trạng thái chuẩn có thể mượn cho các "lời mời" agent trong phiên.

**Nghiên cứu về lỗi đa agent**
- MAST: "Why Do Multi-Agent LLM Systems Fail?" (3/2025, v3 10/2025): https://arxiv.org/abs/2503.13657, bảng tần suất tại https://arxiv.org/html/2503.13657v3
  - Hơn 1.600 trace, 7 framework, 14 failure mode, κ = 0,88.
  - Các mode đáng chú ý cho vấn đề "nói lướt qua nhau":

    | Mode | Tần suất |
    |---|---|
    | Step repetition | 15,7% |
    | Reasoning-action mismatch | 13,2% |
    | Unaware of termination conditions | 12,4% |
    | Disobey task specification | 11,8% |
    | Incorrect verification | 9,1% |
    | No/incomplete verification | 8,2% |
    | Task derailment | 7,4% |
    | Fail to ask for clarification | 6,8% |
    | Premature termination | 6,2% |
    | Ignored other agent's input | 1,9% |
    | Information withholding | 0,85% |

- Multiagent debate (Du và cộng sự, 5/2023): https://arxiv.org/abs/2305.14325. Nhiều bản model đề xuất đáp án rồi tranh luận qua nhiều vòng để hội tụ. Bài báo ghi nhận cải thiện về suy luận và tính đúng sự thật (nguồn cũ, dùng làm nền tảng).

### 1.2 Mẫu áp dụng được
- **Supervisor = orchestrator duy nhất, chuyên gia = tool.** Dùng đúng `TeamPipeline`/`TeamAssign` của AgentScope 2.0. Không cho chuyên gia chat tự do trong một hub chung. Chỉ dùng MsgHub cho vòng phản biện (debate) có giới hạn.
- **Bản giao việc có cấu trúc** (theo Anthropic, và tham số `prompt` của TeamAssign): `objective`, `case_facts` (trích từ hồ sơ, không chuyển nguyên văn cuộc chat), `expected_output_schema`, `tools_allowed`, `boundaries/không làm`, `deadline/budget`.
- **Sổ cái dùng chung (blackboard) theo Magentic**: gắn vào hồ sơ vụ việc.
  - *Task ledger*: facts đã xác minh (có nguồn), giả định, kế hoạch.
  - *Progress ledger*: 5 trường như trên, cập nhật sau mỗi lượt.
  - Các agent chỉ đọc ledger cùng bản giao việc của mình, không đọc toàn bộ transcript. Điều này giải quyết cả cảnh báo của Cognition (thiếu context) lẫn chi phí token.
- **Schema thông điệp giữa agent**: `type ∈ {question, answer, claim, objection, handoff_request}`, `claim` + `evidence[] (source_id, trích dẫn)`, `confidence`, `assumptions[]` (để lộ "quyết định ngầm" theo Cognition), `open_questions[]`. Supervisor từ chối câu `answer` hay `claim` nào không có evidence.
- **Lượt nói**: Supervisor chọn người nói tiếp (như SelectorGroupChat/Magentic). Không cho cùng một agent nói hai lượt liền, trừ khi đang chờ kết quả tool.
- **Vòng phản biện có giới hạn**: chỉ bật cho quyết định rủi ro, ví dụ đền bù hay phạt. Cấu hình 1–2 vòng: chuyên gia A đưa claim, chuyên gia B (hoặc verifier) phản biện, judge trả structured `{finished, verdict, unresolved}`. Bắt buộc có `max_rounds`, vì ví dụ debate của AgentScope không có.
- **Điều kiện dừng ghép**: `request_satisfied` OR `max_rounds` OR `token_budget` OR `stall_count > 2` (thì lập lại kế hoạch, sau `max_reset` thì chuyển cho người) OR handoff sang người.
- **Co giãn công sức** ghi thẳng trong prompt Supervisor: số chuyên gia và số lần gọi tool tối đa theo độ phức tạp của vụ việc. Đề phòng lỗi "50 subagent".
- **Chuyên gia trả artifact cùng tham chiếu** (ghi vào hồ sơ vụ việc) thay vì đổ văn bản dài vào context của Supervisor. Khi cần trả nguyên văn câu trả lời của chuyên gia cho người dùng thì dùng kiểu `forward_message`.
- **Đánh giá theo MAST**: viết test/eval cho các lỗi lặp bước, không biết khi nào dừng, không hỏi lại khi thiếu thông tin, và xác minh sai.
- Dùng trạng thái A2A (`input-required`, `rejected`…) cho vòng đời của lời mời chuyên gia.

---

## 2. Tối ưu token/chi phí, context và bộ nhớ

### 2.1 Prompt caching

**OpenAI** (trang hiện hành, không ghi ngày): https://developers.openai.com/api/docs/guides/prompt-caching
- Ngưỡng tối thiểu: **GPT-5.6 trở lên cần 1.024 token "visible"**. Các model cũ hơn thì ngưỡng thay đổi theo tools, ảnh, schema, reasoning effort…, không có một con số chung. GPT-5.5 có breakpoint ngầm định mỗi 2.048 token.
- Thời gian sống của cache:
  - GPT-5.6 trở lên: `prompt_cache_options.ttl="30m"`.
  - Model cũ hơn: `prompt_cache_retention` = `in_memory` (khoảng 5–10 phút, tối đa 1 giờ) hoặc `24h`. Tổ chức không bật ZDR mặc định là `24h`.
- Giá với GPT-5.6 trở lên: ghi cache 1,25×, đọc cache 0,1×. Trang ghi "giảm tới 95%" chi phí input đã cache.
- `prompt_cache_key`:
  - Với model cũ, khoá này giúp định tuyến. Nên giữ khoảng 15 request/phút cho mỗi key, vì vượt 15 req/phút sẽ bị tràn sang máy khác.
  - Với GPT-5.6 trở lên, khoá này dùng để hạch toán riêng.
- Định tuyến dựa trên hash các token đầu, kể cả định nghĩa tool.
- Đọc `usage.input_tokens_details.cached_tokens` và `cache_write_tokens` để biết mức cache.
- Khuyến nghị:
  - nội dung tĩnh đặt đầu, nội dung động (thời gian, dữ liệu người dùng) đặt cuối;
  - chỉ append message, không viết lại lịch sử. Compaction hay cắt bớt sẽ làm mất khả năng tái dùng cache;
  - **giữ nguyên danh sách tool**, dùng `allowed_tools`/`tool_choice` thay vì bỏ tool;
  - đổi `text.format` hay `reasoning.effort` sẽ làm đổi prefix.

**Anthropic**: https://platform.claude.com/docs/en/docs/build-with-claude/prompt-caching
- Tối đa 4 breakpoint `cache_control`. Có chế độ automatic caching với `cache_control` ở top-level.
- Thứ tự prefix: tools → system → messages. Cửa sổ lookback là 20 block.
- TTL mặc định 5 phút; có tuỳ chọn 1 giờ.
- Hệ số giá: ghi 1,25× (5 phút) hoặc 2× (1 giờ); đọc 0,1×.
- Ngưỡng tối thiểu tuỳ model, từ 512 đến 4.096 token.

### 2.2 Context engineering, compaction, dọn tool result

**Anthropic: "Effective context engineering for AI agents" (29/09/2025)**: https://www.anthropic.com/engineering/effective-context-engineering-for-ai-agents
- *Context rot*: context là tài nguyên hữu hạn, càng thêm token thì lợi ích biên càng giảm.
- System prompt ở "độ cao vừa phải" (right altitude). Tool tối thiểu, không chồng lấn. Vài ví dụ chuẩn mực thay vì liệt kê hết edge case.
- *Just-in-time retrieval*: giữ định danh nhẹ (đường dẫn, id, truy vấn) và chỉ nạp khi cần. Có thể kết hợp nạp một phần từ đầu.
- Kỹ thuật cho tác vụ dài:
  - **compaction**: tóm tắt rồi khởi động lại; **dọn tool result** là dạng nhẹ nhất;
  - **ghi chú có cấu trúc** ngoài context (NOTES.md);
  - **sub-agent** khám phá với hàng chục nghìn token nhưng chỉ trả về bản tóm tắt khoảng **1.000–2.000 token**.

**Anthropic context editing và memory tool (29/09/2025)**: https://claude.com/blog/context-management
- Memory tool cộng context editing cải thiện 39% so với baseline (eval agentic search nội bộ). Riêng context editing được +29%.
- Trong eval web search 100 lượt, context editing **giảm 84% token**.
- Tài liệu context editing: https://platform.claude.com/docs/en/build-with-claude/context-editing
  - `clear_tool_uses_20250919` mặc định `trigger` = 100.000 input token và `keep` = 3 tool use gần nhất. Có thêm `clear_at_least` (để mỗi lần dọn đủ đáng so với việc phá cache), `exclude_tools`, `clear_tool_inputs`.
  - Mỗi lần dọn **làm vô hiệu cache prefix**.
  - Tài liệu khuyến nghị compaction phía server (`compact_20260112`) là chiến lược chính.
- Memory tool: https://platform.claude.com/docs/en/agents-and-tools/tool-use/memory-tool
  - Chạy phía client, thư mục `/memories`, các lệnh view/create/str_replace/insert/delete/rename.
  - Prompt tự chèn: "ASSUME INTERRUPTION…".
  - An toàn: lọc dữ liệu nhạy cảm, giới hạn kích thước file, **xoá file lâu không truy cập (expiration)**, chống path traversal.

**OpenAI**
- Compaction cho Responses API: https://developers.openai.com/api/docs/guides/compaction
  - Phía server: `context_management.compact_threshold` sinh compaction item đã mã hoá.
  - Hoặc gọi riêng endpoint `/responses/compact`.
  - (Chỉ dùng được nếu gateway hỗ trợ Responses API, **[chưa xác minh]** với gateway của dự án.)
- Cookbook session memory: https://developers.openai.com/cookbook/examples/agents_sdk/session_memory
  - So sánh *trimming* N lượt cuối (rẻ, ổn định, nhưng "mất trí nhớ" đột ngột) với *summarization* (giữ được quyết định và ID, nhưng có rủi ro "context poisoning").
  - Prompt tóm tắt nên: kiểm tra mâu thuẫn, sắp theo thời gian (bản mới đè bản cũ), **đánh dấu UNVERIFIED** thay vì đoán, dùng các mục cố định, khoảng 200 từ, trích nguyên văn mã lỗi.
  - Ghi log cả input lẫn output của bước tóm tắt.

**AgentScope 2.0 `ContextConfig`** (upstream: https://raw.githubusercontent.com/agentscope-ai/agentscope/main/src/agentscope/agent/_config.py)
- Các tham số: `trigger_ratio=0.8`, `reserve_ratio=0.1`, `context_buffer_ratio=0.2` (báo cho agent biết sắp compaction, tính từ 60%), `tool_result_limit=50000` token, `compression_tool_enabled=False` (tool `CompressContext`), `max_image_num=5`, `compression_fallback_to_truncation=True`.
- `SummarySchema` gồm 5 trường: `task_overview`, `current_state`, `important_discoveries`, `next_steps`, `context_to_preserve`.
- Prompt compaction mặc định yêu cầu chuyển mọi mốc thời gian tương đối thành ngày tuyệt đối, giữ nguyên ID/đường dẫn, và ghi lại việc còn dang dở kèm owner và trạng thái.
- **[mã nguồn local]**: bản fork có thêm `compression_retry_drop_oldest` (cho "audited runtimes"). Trường này **không có ở upstream**.

### 2.3 Kiến trúc bộ nhớ

**MemGPT/Letta**
- Sleep-time compute (21/04/2025): https://www.letta.com/blog/sleep-time-compute
  - Tạo 2 agent: agent chính trò chuyện và **không có quyền sửa core memory**; agent sleep-time có quyền sửa các memory block của agent chính.
  - Ví dụ cặp model: gpt-4o-mini cho agent chính, model lớn hơn cho sleep-time.
  - Số liệu nằm ở paper arXiv 2504.13171 (**[chưa xác minh]** con số).
- Tài liệu hiện hành:
  - https://docs.letta.com/guides/agents/memory: memory block được ghim vào context, có thể chia sẻ block giữa nhiều agent; mọi message được lưu và truy hồi được sau compaction.
  - https://docs.letta.com/guides/agents/architectures/sleeptime: tính năng nay gọi là "dreaming". Nó chạy sau N bước hoặc khi compaction, và có tuỳ chọn "Agent reviews before applying" (một agent khác duyệt các thay đổi bộ nhớ trước khi áp dụng).
- Core / archival / recall và các tool `memory_insert`, `memory_replace`, `memory_rethink`, `archival_memory_insert/search` chỉ thấy qua kết quả tìm kiếm của docs Letta (**[chưa xác minh]** trên trang hiện hành, vì docs đã đổi cấu trúc).

**Mem0 (paper, 28/04/2025)**: https://arxiv.org/abs/2504.19413 và https://arxiv.org/html/2504.19413v1
- Pha trích xuất dùng bản tóm tắt hội thoại (làm mới bất đồng bộ) cộng m = 10 message gần nhất.
- Pha cập nhật lấy s = 10 ký ức tương tự nhất. LLM chọn **ADD / UPDATE / DELETE / NOOP** bằng function call.
- Mem0g (đồ thị) đánh dấu quan hệ lỗi thời là **invalid thay vì xoá**.
- Số liệu trên LOCOMO:
  - +26% so với memory của OpenAI (LLM-as-judge);
  - p95 latency giảm 91% so với full-context (1,44 s so với 17,12 s);
  - tiết kiệm hơn 90% token (khoảng 7k token mỗi hội thoại so với khoảng 26k của full-context);
  - Mem0g khoảng 14k token và cao hơn khoảng 2%.
- Lưu ý: paper đo Zep hơn 600k token. Đây là số đo của đối thủ, cần đọc thận trọng.

**Zep / Graphiti**
- Paper (20/01/2025): https://arxiv.org/abs/2501.13956. DMR 94,8% so với MemGPT 93,4%; LongMemEval chính xác hơn tới 18,5% và latency giảm 90% (số của Zep).
- Graphiti: https://github.com/getzep/graphiti
  - Theo dõi song thời gian (bi-temporal). Fact có cửa sổ hiệu lực; khi thông tin đổi thì fact cũ bị **invalidate, không xoá**.
  - Cập nhật tăng dần, không cần tính lại theo lô.
  - Tìm kiếm lai: semantic, BM25 và duyệt đồ thị.
  - **Mọi entity/quan hệ truy được về "episode" gốc (provenance).**

**LangMem**: https://langchain-ai.github.io/langmem/concepts/conceptual_guide/
- Phân loại bộ nhớ:
  - semantic, dạng *collection* (nhiều bản ghi) hoặc *profile* (một tài liệu cập nhật tại chỗ, dễ cho người dùng xem và sửa);
  - episodic (ví dụ thành công);
  - procedural (prompt được tối ưu từ feedback).
- *Hot path* (ghi ngay trong lượt, thêm độ trễ) so với *background* (phản tư sau hội thoại, không chậm, nhưng cập nhật trễ).
- Namespace phân cấp, ví dụ `(org, user_id, app)`.

**AgentScope long-term memory**: https://doc.agentscope.io/tutorial/task_long_term_memory.html (v1.0)
- Hai lớp `Mem0LongTermMemory` và `ReMePersonalLongTermMemory`.
- `long_term_memory_mode` = `agent_control` (dùng tool `record_to_memory`/`retrieve_from_memory`), `static_control` (developer gọi `record`/`retrieve`) hoặc `both`.
- Bản 2.0 chuyển sang middleware `_longterm_memory/{_mem0,_reme,_agentic_memory}` **[mã nguồn local]**.
- Short-term memory dùng "marks" (ví dụ `hint`). Compaction dựa trên mark: https://doc.agentscope.io/tutorial/task_memory.html
- ReMe: https://github.com/agentscope-ai/ReMe
  - Bộ nhớ dạng file Markdown, phân lớp `session/ → daily/ → digest/{personal, procedure, wiki}`.
  - `auto_dream` chạy định kỳ, có thể tạo, corroborate (củng cố), refine hoặc correct các node.
  - Tìm kiếm BM25 cộng vector bằng RRF.
  - Tự báo: LongMemEval-s 89,4%.

### 2.4 Định tuyến model
- OpenAI practical guide (PDF ở trên): prototype bằng model mạnh nhất để có baseline, sau đó **thay dần bằng model nhỏ** ở các bước như truy hồi hay phân loại intent, kèm eval.
- Anthropic research system: lead dùng Opus, subagent dùng Sonnet (link 1.1). Claude Code cho phép mỗi subagent dùng `model` riêng, ví dụ Haiku để giảm chi phí: https://code.claude.com/docs/en/sub-agents
- AgentScope 2.0 `ModelRouterMiddleware` (tin 2026-09 trong README upstream; **[mã nguồn local]** `middleware/_model_router.py`):
  - Một classifier chọn `ChatModelCandidate(name, model, description)` cho mỗi lượt trả lời.
  - Quyết định giữ nguyên khi lượt đó resume.
  - Nếu classifier lỗi thì dùng model mặc định.

### 2.5 Tự cập nhật tri thức một cách an toàn (tổng hợp từ các nguồn trên)
- **Thao tác rời rạc thay vì ghi tự do**: ADD/UPDATE/DELETE/NOOP (Mem0) đối chiếu với top-k ký ức tương tự.
- **Không xoá, chỉ invalidate kèm cửa sổ hiệu lực** (Graphiti, Mem0g) để còn suy luận theo thời gian và kiểm toán được.
- **Provenance**: mọi fact trỏ về episode hoặc nguồn gốc (Graphiti). Nếu tóm tắt không chắc thì đánh dấu UNVERIFIED (OpenAI cookbook).
- **Duyệt trước khi áp dụng**: Letta "Agent reviews before applying" (duyệt bằng agent); Intercom Fin "Suggestions" và Optimize dashboard (AI đề xuất, con người approve; xem mục 4).
- **Ghi nền thay vì trên hot path** (LangMem; Letta sleep-time/dreaming; ReMe `auto_dream`).
- **Decay và hết hạn**: xoá ký ức lâu không truy cập, giới hạn kích thước (Anthropic memory tool).
- **Tách quyền**: agent phục vụ khách không tự sửa core memory, chỉ agent nền mới sửa (Letta sleep-time).

### 2.6 Mẫu áp dụng được
- **Cấu trúc prompt để tận dụng cache** với gateway gpt-5.x-mini, theo thứ tự:
  1. system tĩnh của nền tảng;
  2. hồ sơ agent (persona, guardrail);
  3. **danh sách tool cố định** (bật/tắt bằng `allowed_tools` chứ không thêm/bớt);
  4. tóm tắt hồ sơ vụ việc;
  5. lịch sử append-only;
  6. dữ liệu động (thời gian, người dùng) đặt ở cuối.

  Đặt `prompt_cache_key` theo `agent_id` (hoặc `agent_id:tenant`). Đo `cached_tokens` trong mỗi lần gọi. **[chưa xác minh]**: gateway có chuyển tiếp `prompt_cache_key`/`prompt_cache_retention` và trả về `cached_tokens` hay không. Cần kiểm tra thực tế, vì quy tắc còn tuỳ phiên bản gpt-5.x.
- **Ngân sách context theo ContextConfig của AgentScope**: giữ mặc định 0,8/0,1/0,2, dùng `SummarySchema` 5 trường, `tool_result_limit` thấp hơn cho tool trả dữ liệu lớn (danh sách ticket…). Bổ sung trường "facts đã xác minh kèm nguồn" vào summary để chống ảo giác.
- **Dọn tool result trước, tóm tắt sau**: tool result cũ thay bằng placeholder cộng ID để truy lại (just-in-time). Gộp nhiều lần dọn thành một (giống `clear_at_least`) để không phá cache liên tục.
- **Cô lập context của chuyên gia** (TeamPipeline): chuyên gia nhận bản giao việc và trả bản tóm tắt khoảng 1–2k token cùng tham chiếu artifact. `reset_members=True` giữa các lượt.
- **Bộ nhớ 3 tầng cho mỗi tenant**:
  - (a) *profile* có cấu trúc (khách hàng, căn hộ, sở thích; dạng profile của LangMem, người dùng sửa được);
  - (b) *episodic*: các vụ việc đã giải quyết, dùng làm ví dụ;
  - (c) *procedural/knowledge* cấp văn phòng: quy trình, quy định toà nhà.

  Namespace `(org, building, customer)`.
- **Ghi tri thức có kiểm soát**: agent chỉ *đề xuất* (ADD/UPDATE/INVALIDATE kèm nguồn và trích dẫn). Một tác vụ nền (model nhỏ) gộp và khử trùng lặp, sau đó đưa vào **hàng đợi duyệt** cho quản trị viên văn phòng với tri thức dùng chung. Ký ức cá nhân rủi ro thấp có thể tự áp dụng. Fact lỗi thời thì invalidate, không xoá. Thêm TTL/decay cho ký ức không được truy cập.
- **Định tuyến model**: model nhỏ cho phân loại intent, chọn chuyên gia, tóm tắt và trích xuất ký ức. Model chính cho quyết định cuối. Dùng `ModelRouterMiddleware`, và có eval chứng minh trước khi hạ cấp model.

---

## 3. Agent Builder: từ yêu cầu ngôn ngữ tự nhiên đến agent đúng ý

### 3.1 Các nguồn nói gì

**OpenAI**
- AgentKit/Agent Builder (06/10/2025): https://openai.com/index/introducing-agentkit/ (trang trả 403 khi tải; thông tin dưới đây lấy từ kết quả tìm kiếm của chính trang đó).
  - Canvas trực quan có versioning, Connector Registry, ChatKit, Evals (datasets, trace grading, tối ưu prompt tự động).
  - **Cập nhật 03/06/2026: OpenAI dừng Agent Builder và Evals, ngừng hẳn từ 30/11/2026**, khuyên dùng Agents SDK (code) và *Workspace Agents* trong ChatGPT (ngôn ngữ tự nhiên).
- Docs Agent Builder: https://developers.openai.com/api/docs/guides/agent-builder
  - Xác nhận lịch ngừng 30/11/2026.
  - Có template, Preview chạy thử theo từng node, tự lưu, **Publish tạo major version (snapshot)** và có thể pin API vào bản cũ. Tab Evaluate có trace grader.
  - Không có chức năng sinh workflow từ ngôn ngữ tự nhiên.
- Workspace Agents (2026): mô tả workflow trong chat thì ChatGPT tự định nghĩa các bước, gắn tool, thêm skill và thử nghiệm. Có test trước khi publish, chọn model và reasoning effort, chia sẻ, lập lịch, và admin quy định hành động nào cần duyệt.
  - Trang help https://help.openai.com/en/articles/20001143 trả 403; thông tin lấy qua kết quả tìm kiếm, **[chưa xác minh]** chi tiết.
- GPT Builder: tab *Create* (trò chuyện với builder) và tab *Configure* (name, description, instructions, conversation starters, knowledge, capabilities). Có preview, và bản nháp tự lưu.
  - Nguồn: https://help.openai.com/en/articles/8554397-creating-a-gpt (403, **[chưa xác minh]** qua kết quả tìm kiếm).
  - Theo kết quả tìm kiếm, việc tạo GPT mới nay chỉ dành cho workspace Business/Enterprise/Edu.

**Anthropic: subagents và skills**
- Subagent của Claude Code: https://code.claude.com/docs/en/sub-agents
  - Agent là **file Markdown kèm YAML frontmatter**. Bắt buộc `name`, `description`; tuỳ chọn `tools`, `disallowedTools`, `model`, `permissionMode`, `maxTurns`, `skills`, `mcpServers`, `hooks`, `memory`, `effort`…
  - **`description` quyết định khi nào agent được giao việc tự động.** Mô tả nên ngắn; cảnh báo khi tổng các mô tả vượt 15.000 token.
  - Cách tạo được khuyến nghị: nhờ Claude viết file từ mô tả, rồi người dùng xem và chỉnh.
- Agent Skills (16/10/2025; trở thành open standard 18/12/2025): https://www.anthropic.com/engineering/equipping-agents-for-the-real-world-with-agent-skills
  - Thư mục có `SKILL.md` (frontmatter `name`, `description`).
  - *Progressive disclosure* 3 mức: metadata trong system prompt, thân SKILL.md khi liên quan, file liên kết khi cần.
  - Nguyên tắc "đánh giá trước": chạy agent trên các tác vụ đại diện, tìm chỗ yếu, rồi viết skill bù.
  - Chỉ cài skill từ nguồn tin cậy.

**Microsoft Copilot Studio**
- Tạo agent bằng mô tả (ms.date 31/08/2026): https://learn.microsoft.com/en-us/microsoft-copilot-studio/authoring-first-bot
  - Người dùng nhập mô tả tối đa 1.024 ký tự. AI sinh **name, description, instructions** và **gợi ý** trigger, kênh, nguồn tri thức, tool. Người dùng chọn Add hoặc Dismiss từng gợi ý (kèm thumbs-down và feedback). Gợi ý không lưu sau phiên.
  - Giới hạn: name 42 ký tự, description 1.024, instructions 8.000.
- FAQ (12/2025): https://learn.microsoft.com/en-us/microsoft-copilot-studio/faqs-agent-creation
  - Tính năng được đánh giá trên **250 đầu vào ngôn ngữ tự nhiên**, chấm 0–100 rồi gộp thành chỉ số có trọng số. Có đo **tỉ lệ chấp nhận/bỏ qua gợi ý** trên traffic thật.
  - Không sinh suggested prompts, và không gợi ý tool ngoài các connector có sẵn.
- Generative orchestration (ms.date 26/08/2026): https://learn.microsoft.com/en-us/microsoft-copilot-studio/advanced-generative-actions
  - Chọn topic, tool, agent con hoặc tri thức **dựa trên description**. Tự sinh câu hỏi để điền input còn thiếu. Activity map hiển thị khi test.
  - Hướng dẫn viết description: câu chủ động, có từ khoá, 1–2 câu, nêu cả **điều nó không làm**. Các description chồng lấn khiến việc chọn không đoán trước được.
- Agent evaluation (ms.date 05/10/2026): https://learn.microsoft.com/en-us/microsoft-copilot-studio/analytics-agent-evaluation-intro
  - Test set: sinh từ knowledge/topic, import hoặc viết tay. Có thể đơn lượt hoặc nhiều lượt.
  - Nhiều phương pháp chấm (ví dụ compare meaning, similarity) và 4 bộ đánh giá an toàn.
  - Có REST API để chạy trong CI/CD.

**Google Gemini Enterprise (trước là Agentspace / Agent Designer)**
- Workflow Builder (cập nhật 09/10/2026): https://docs.cloud.google.com/gemini/enterprise/docs/agent-designer
- Tạo bằng ngôn ngữ tự nhiên (cập nhật 09/10/2026): https://docs.cloud.google.com/gemini/enterprise/docs/workflow-builder/create-natural-language
  - Ô "Describe your agent", có thể kèm mục đích, ranh giới và hành vi mong muốn.
  - **Có thể yêu cầu Gemini đặt câu hỏi làm rõ.**
  - Gemini sinh khung (scaffold) workflow, người dùng chỉnh, thử ở Preview, rồi bấm Turn on.
  - Không phải node nào cũng sửa được bằng prompt.
- Tạo chat agent (cập nhật 11/10/2026): https://docs.cloud.google.com/gemini/enterprise/docs/agent-designer/create-agent
  - Chat pane bên trái để mô tả và tinh chỉnh; canvas có các tab **Preview / Flow / Schedule**.
  - Bấm vào node để mở form: Name, Description, Instructions, Model, Data & tools, Knowledge (Add files), Starter prompts.
  - Có thể thêm subagent. Rời trang mà chưa bấm Create thì agent lưu ở trạng thái Draft.

**Salesforce Agentforce Builder (mới)**: https://trailhead.salesforce.com/content/learn/modules/new-agentforce-builder-quick-look/explore-the-new-agentforce-builder
- Bấm New Agent rồi mô tả vai trò, loại công ty và nhiệm vụ. **Agentforce có thể hỏi lại câu hỏi bổ sung**, hoặc người dùng tự điền.
- Sau đó hệ thống sinh chi tiết agent và các subagent.

**Dify**: https://docs.dify.ai/en/use-dify/build/agent
- Nút *Generate* sinh hoặc tinh chỉnh prompt (có thể tham chiếu `current_prompt` và "Ideal Output"). **Mỗi lần sinh được lưu thành một version.**

**Relevance AI**: https://relevanceai.com/docs/agent/quick-start-guide
- Create Agent → **Invent**: mô tả nhiệm vụ, đầu ra mong muốn và các tích hợp. Hệ thống sinh prompt và gợi ý tool.
- Trang marketing https://relevanceai.com/agents nói Invent sinh cả eval (**[chưa xác minh]** trong docs).

**n8n**
- AI Workflow Builder: https://docs.n8n.io/advanced-ai/ai-workflow-builder/ và https://docs.n8n.io/build/ways-of-building-workflows/ai-workflow-builder
  - Mô tả, xem quá trình dựng, rà credential và tham số, rồi tinh chỉnh bằng prompt tiếp theo. Mỗi lần yêu cầu tốn một credit.
- AI Assistant (Cloud preview): https://docs.n8n.io/build/ways-of-building-workflows/ai-assistant
  - Prompt tốt nên nêu: trigger, các dịch vụ dùng, dữ liệu đọc/ghi, hành vi khi thành công và khi thất bại.
- (Đọc qua kết quả tìm kiếm trên docs.n8n.io, chưa mở từng trang.)

**Coze Studio** (mã nguồn mở, Apache-2.0): https://github.com/coze-dev/coze-studio
- Agent gắn workflow, knowledge, plugin, database và biến. Prompt là một loại tài nguyên.
- Các nút "Auto Optimize prompt" và tự gợi ý plugin theo persona chỉ thấy ở hướng dẫn bên thứ ba (**[chưa xác minh]**).

**AgentScope**
- AgentScope Studio có trợ lý Friday, nhưng repo ghi "no longer maintained as a standalone tool" và chuyển sang Web UI của AgentScope 2.0 ("building, running and observing agents"): https://github.com/agentscope-ai/agentscope-studio
- Không thấy builder sinh agent từ ngôn ngữ tự nhiên trong tài liệu công khai.

### 3.2 Mẫu áp dụng được
- **Hỏi để làm rõ trước khi sinh** (Agentforce, Gemini). Builder hỏi tối đa 3–5 câu có mục tiêu: việc gì, cho ai, dữ liệu nào, việc gì không được làm, khi nào chuyển cho người. Có nút "Bỏ qua, tôi tự điền".
- **Spec có cấu trúc hiển thị trước khi tạo**, map 1-1 với form: `name`, `description` (dùng để định tuyến, theo hướng dẫn Copilot Studio: 1–2 câu, có từ khoá, nêu điều *không* làm), `instructions`, `tools[]` (chỉ chọn từ catalog được cấp quyền), `knowledge[]`, `guardrails/escalation`, `model tier`, `starter prompts`, `test_cases[]`. Định dạng gần với frontmatter của Claude subagent/skills.
- **Gợi ý là đề xuất, không tự áp dụng** (Copilot Studio): mỗi tool hay nguồn tri thức được gợi ý có Add/Dismiss. Ghi lại tỉ lệ chấp nhận để đo chất lượng builder (Copilot Studio có đo chỉ số này).
- **Tinh chỉnh lặp bằng chat ("đổi X")**, mỗi lần sinh tạo một version (Dify Generate). Hiển thị **diff cấu hình** (trước/sau theo từng trường) trước khi người dùng lưu.
- **Eval trước khi publish**: builder tự sinh 5–10 test case từ spec và knowledge (giống test set của Copilot Studio). Chạy ở chế độ *Simulate* không ghi dữ liệu (Agentforce). Chỉ cho publish khi đạt ngưỡng. Lưu ý OpenAI đã dừng Evals/Agent Builder, nên không nên phụ thuộc dịch vụ eval của bên ngoài.
- **Template theo nghiệp vụ** (Gemini, n8n, Dify): tiếp nhận phản ánh, vệ sinh, kỹ thuật, kế toán… Builder bắt đầu từ template rồi chỉnh.
- **Builder chỉ được chọn tool trong catalog** mà văn phòng đã được cấp (Gemini: "tools limited to connectors admin provisions"). Không cho sinh tool mới.
- Đánh giá chính builder theo cách Copilot Studio: một bộ khoảng 250 mô tả mẫu, chấm chất lượng từng trường sinh ra.

---

## 4. Giao diện quản lý agent (không phải chat) cho người dùng nghiệp vụ

### 4.1 Các nguồn mô tả màn hình và luồng như thế nào

**Copilot Studio**
- Trang **Home/Agents**: ô mô tả; hoặc "Create blank agent".
- Trang **Overview** của agent: các khối Details (name, description), Instructions (Edit), Knowledge, Tools, Agents, Topics, Suggested prompts. Có test panel. Có danh sách gợi ý với Add/Dismiss. Nguồn: https://learn.microsoft.com/en-us/microsoft-copilot-studio/authoring-first-bot
- **Settings** → Generative AI → Orchestration. Có activity map khi test: https://learn.microsoft.com/en-us/microsoft-copilot-studio/advanced-generative-actions
- **Evaluation**: test set, chạy, điểm tổng và từng case kèm transcript và activity map: https://learn.microsoft.com/en-us/microsoft-copilot-studio/analytics-agent-evaluation-intro
- **Monitor** (ms.date 01/06/2026): https://learn.microsoft.com/en-us/microsoft-copilot-studio/analytics-overview
  - AI Summary của các insight và tóm tắt bình luận khách hàng.
  - DAU/MAU, kết quả phiên (Resolved / Escalated / Abandoned), CSAT, themes.
  - Dữ liệu giữ 360 ngày; transcript giữ 28 ngày; tải transcript được.
  - Có vai trò *Analytics Viewer* chỉ xem số liệu.
  - Hoạt động trong test panel không tính vào Monitor.
- (Versioning của Copilot Studio đi qua Power Platform Solutions; chưa đọc chi tiết, **[chưa xác minh]**.)

**Gemini Enterprise**: https://docs.cloud.google.com/gemini/enterprise/docs/agent-designer/create-agent
- Bố cục 3 phần:
  - **chat pane** bên trái để mô tả và tinh chỉnh;
  - **canvas** với các tab Preview / Flow / Schedule;
  - **panel chi tiết node** (form các trường).
- Trạng thái Draft hoặc Create. Chia sẻ tới người dùng hoặc nhóm. Tool bị giới hạn theo connector mà admin đã cấp: https://docs.cloud.google.com/gemini/enterprise/docs/agent-designer

**Salesforce Agentforce Builder**: https://trailhead.salesforce.com/content/learn/modules/new-agentforce-builder-quick-look/explore-the-new-agentforce-builder
- Bố cục gồm:
  - **Explorer** (cây tài sản: subagent, action, biến);
  - **Canvas** dạng tài liệu, chuyển qua lại với **Script** (Agent Script), hai chế độ đồng bộ với nhau;
  - **Preview**;
  - **Agentforce Assistant** (panel trò chuyện để xây, truy vấn và gỡ lỗi; đây chính là mẫu "copilot cạnh form");
  - các nút **Save** và **Commit Version**.
- Preview có 2 chế độ: **Simulate** (không chạy action, không đổi dữ liệu) và **Live Test** (chạy thật). Có Trace từng bước, giá trị biến và thời gian.
- Version: Draft, Commit (khoá lại thành snapshot), rồi Activate. **Mỗi thời điểm chỉ một version live**; muốn sửa thì lưu thành draft mới.

**Dify**
- Màn hình cấu hình agent: https://docs.dify.ai/en/use-dify/build/agent
  - Instructions (có Generate), Variables (form đầu vào), Knowledge (gắn KB, lọc theo metadata), Tools (bật/tắt, credential).
  - Agent Settings: Function Calling hoặc ReAct; Max Iterations.
  - Pane **Debug & Preview**, có "Debug as Multiple Models" (tối đa 4 model cùng lúc).
- Version control: https://docs.dify.ai/en/cloud/use-dify/build/version-control
  - Current Draft → Publish Update → Latest Version.
  - Lịch sử có lọc; đặt tên và release notes cho version.
  - **Restore nạp bản cũ vào draft** (ghi đè draft). Xoá được bản cũ, trừ draft và latest.
- Logs và giám sát (thời gian, trạng thái, token, nguồn gọi): https://docs.dify.ai/en/learn/tutorials/workflow-101/lesson-10

**ServiceNow AI Agent Studio** (bản phát hành Brazil, cập nhật 10/09/2026): https://www.servicenow.com/docs/r/intelligent-experiences/ai-agent-studio.html
- Hai tab: Agentic workflows và AI agents. Danh sách có tìm kiếm, lọc và duplicate.
- Bấm vào tên mở **Guided Setup** (wizard theo bước: tool, trigger, nơi hiển thị, quyền ACL); bước cuối là "Save and test".
- Trang Testing gồm manual test (thực thi và kiểm tra quyền truy cập) cùng **agentic evaluations** chạy nhiều lần trên dataset.
- Trang Activity có log lọc theo version. Có dashboard AI Agent Analytics.

**Intercom Fin**: https://www.intercom.com/help/en/articles/7120684-fin-ai-agent-explained
- Điều hướng theo 4 khu: **Train → Test → Deploy → Analyze**.
  - Train: Content library, Guidance, Procedures (soạn như tài liệu), Data connectors, Audiences, Tone.
  - Test: Simulations, batch test bằng hội thoại import, chấm điểm câu trả lời, Preview, **Answer inspection** (nguồn nào và thiết lập nào tạo ra câu trả lời).
  - Deploy: các kênh, quy tắc handoff sang người, giới hạn sử dụng.
  - Analyze: tỉ lệ resolution và involvement, CX Score, Topics Explorer, **Optimize dashboard với các bản sửa do AI đề xuất để người duyệt**, **Suggestions** cập nhật nội dung từ những hội thoại chưa giải quyết được.
- Không thấy mô tả về version.

**Zendesk AI agents**
- Generative procedure: viết các bước bằng văn bản tự do, Generate, xem bản đồ procedure, Update, Test procedure trong widget (chỉ với messaging), rồi Publish. Restore version cũ thành draft không ảnh hưởng bản đang live: https://support.zendesk.com/hc/en-us/articles/10040865503898-Managing-generative-procedures-for-AI-agents
- Agent phải publish riêng thì thay đổi mới có hiệu lực.
- (Đọc qua kết quả tìm kiếm trên support.zendesk.com, **[chưa xác minh]** từng chi tiết.)

**n8n**: duyệt tool theo từng tool. Trong Tools Panel có mục "Human review" chọn kênh (Chat, Slack, Teams…). Người duyệt thấy tool cùng tham số và chọn approve hoặc deny; khi deny thì agent được báo lại. Nên ghi cấu hình duyệt này vào system prompt. Nguồn: https://docs.n8n.io/build/integrate-ai/ai-examples/human-in-the-loop-for-tools (qua kết quả tìm kiếm).

**Relevance AI**: chế độ duyệt cho mỗi kết nối: *Auto run / Approval required / Let Agent decide*, cộng "max auto runs". Nguồn: https://relevanceai.com/docs/build/workforces/workforce-features/approvals-and-escalations (qua kết quả tìm kiếm). Tab **Run** hiển thị từng tool call: https://relevanceai.com/docs/agent/quick-start-guide

### 4.2 Mẫu áp dụng được
- **Bố cục 3 cột "form cạnh copilot"** (Gemini, Agentforce):
  - trái: trợ lý Builder (chat);
  - giữa: form hoặc spec của agent, chia nhóm theo mục 3.2;
  - phải: Preview/Test.

  Mỗi chỉnh sửa từ chat **điền vào form và tô sáng trường đã đổi**. Người dùng có thể sửa tay trực tiếp; chat và form luôn đồng bộ (như Canvas↔Script của Agentforce).
- **Catalog agent**: danh sách có tìm kiếm, lọc theo nghiệp vụ và trạng thái (Draft / Live / Tắt), duplicate từ template (ServiceNow, Gemini). Mỗi thẻ ghi: mục đích một câu, version live, người sở hữu, chỉ số 7 ngày.
- **Vòng đời version**: Draft → Commit/Publish (snapshot bất biến, có tên và ghi chú) → Live. Chỉ một version live mỗi lúc. Rollback bằng cách "khôi phục bản cũ thành draft rồi publish lại" (Dify, Agentforce, Zendesk). Có màn **diff giữa 2 version**.
- **Playground có 2 chế độ**: *Mô phỏng* (tool ghi bị chặn hoặc mock) và *Thật* (Agentforce). Có trace từng bước: tool nào, nguồn tri thức nào, vì sao chọn (activity map hoặc Answer inspection).
- **Trang Đánh giá**: bộ test case (tự sinh, import hoặc viết tay), chạy hàng loạt, điểm tổng và từng case. Cổng chặn publish khi điểm giảm (Copilot Studio, ServiceNow).
- **Tri thức**: tải tài liệu lên kèm trạng thái xử lý, gắn phạm vi (toà nhà hay đối tượng như Audiences của Fin), và hiển thị *Suggestions*: các khoảng trống tri thức lấy từ hội thoại chưa giải quyết, để người duyệt (Fin).
- **Tool picker**: chỉ hiện tool đã được cấp. Mỗi tool có mức duyệt *Tự chạy / Cần duyệt / Agent tự quyết* (Relevance AI) và kênh duyệt (n8n).
- **Analytics**: tỉ lệ giải quyết, chuyển người, bỏ dở; CSAT; chủ đề nổi lên; token/chi phí; một AI summary đầu trang. Có vai trò chỉ xem số liệu (Copilot Studio). Hoạt động test không tính vào analytics.
- **Điều hướng theo luồng công việc** Train → Test → Deploy → Analyze (Fin) thay vì theo cấu trúc kỹ thuật. Cách này phù hợp với người dùng không chuyên kỹ thuật.

---

## Phụ lục: những điểm cần kiểm chứng thêm
- Gateway gpt-5.x-mini có chuyển tiếp `prompt_cache_key` và `prompt_cache_retention` và trả về `cached_tokens` không. Phiên bản gpt-5.x cụ thể quyết định ngưỡng cache và TTL.
- Gateway có hỗ trợ Responses API, cụ thể là compaction và `/responses/compact`, không.
- Chi tiết core/archival/recall trên docs Letta hiện hành (docs đã đổi cấu trúc); số liệu của paper sleep-time (arXiv 2504.13171).
- Các trang help của OpenAI (GPT Builder, Workspace Agents) trả 403. Thông tin hiện chỉ lấy từ kết quả tìm kiếm.
- Coze: "Auto Optimize prompt" và tự gợi ý plugin chỉ thấy trong hướng dẫn bên thứ ba.
- Copilot Studio: cơ chế version và rollback (Power Platform Solutions) chưa đọc.
