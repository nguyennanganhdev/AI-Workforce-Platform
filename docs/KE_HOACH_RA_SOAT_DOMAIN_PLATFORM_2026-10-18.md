# Rà soát develop2: Domain, Platform, Docker/VPS và kế hoạch xử lý

Ngày 18/10/2026. Nền đối chiếu: `origin/develop2` tại `89c020c1`. Mọi kiểm tra trên VPS chỉ đọc. Không gọi model thật.

## 0. Kết luận nhanh

| Hạng mục | Trạng thái | Vấn đề chính |
|---|---|---|
| Platform trên VPS | Đúng bản develop2 mới nhất (runtime `a185cc2d`; sau đó chỉ có commit tài liệu) | Không có |
| Domain trên VPS | Gần mới nhất | API `9dd7504f` thiếu `094bc93b` (vé eval sandbox) và brief Leader mới trong `vinhomes-declaration.json` |
| Nhánh làm việc | Chưa thống nhất | `dev_Chien` có hơn 40 commit Vin N1/N2 chưa vào develop2 và chưa deploy |
| Reception | Chạy được, chất lượng tiếp nhận yếu | Model chạy `gpt-5.6-luna` (không phải gpt-6-luna) với `reasoning_effort=none`; bộ lọc intake dựa trên regex và từ điển cố định |
| UI tiến độ và thẻ xác nhận (cư dân) | Chưa đạt | Chỉ có spinner và một dòng chữ; sau bàn giao chỉ hiện "Đang chờ phản hồi từ bộ phận xử lý" trong 180 giây; các thẻ dùng chung một kiểu `question-card` đơn giản |
| Tách chat / Leader | Đã tách (bản sửa `a185cc2d`) | Nút "Tạo session thử" vẫn trộn phiên thử vào danh sách phiếu |
| Suy luận (reasoning) của agent | Tắt hoàn toàn | Leader và agent đều chạy `gpt-6-luna` với effort `none` qua Chat Completions |
| Memory / học từ kết quả | Chưa có dữ liệu | `agent_memories`, `memory_candidates`, `reme_memories` đều 0 dòng; 12 phiếu, chỉ 1 phiếu closed |
| Builder | Chạy được | Không xử lý agent trùng nghiệp vụ; catalog bị cắt ở 6.000 ký tự nên JSON hỏng; không thấy schema, quyền đọc/ghi của tool |
| Eval | Fail nhiều | 75/178 ca không đạt; agent mới tạo đạt 0/3, 0/4, 0/5 |
| Trang quản lý agent | Chưa đồng bộ | Danh sách và sơ đồ dùng hai API khác nhau; mặc định là danh sách; không kéo thả được node |
| Chi phí $ | Có cột nhưng luôn "Chưa xác định" | `/run/workforce/model-prices.json` trên VPS rỗng (`"prices": []`) |
| Discord | Ổn định | 3 kênh có heartbeat; không có lỗi Discord trong log |
| Thêm kênh khác | Làm được | Registry `ChannelBase` đã có DingTalk, Feishu; Telegram, Zalo, Slack là thêm một lớp mới |
| Model / MCP / Skill / Knowledge | Builder đọc được | Chỉ đọc tài nguyên của chính tài khoản; MCP chỉ có tên và mô tả, thiếu schema |

## 1. Triển khai: nhánh, Docker, VPS

**Platform** (`vagen-platform.duckdns.org`, VPS 103.238.234.172):
- app/web chạy `a185cc2d-leader-boundary-20261018`, `AWP_SOURCE_REVISION` khớp commit.
- Postgres, Redis, MinIO chạy image `e3b7f69b-vps-20261016-1`. Đây là image hạ tầng, không cần đổi.
- Đĩa đã dùng 80% (còn 7,7 GB). Có 30 thư mục release cũ trong `/opt/awp-platform/releases`.

**Domain** (`vinhome-platform.duckdns.org`, VPS 103.238.235.156):

| Service | Tag | So với develop2 |
|---|---|---|
| api, scheduler, platform-sync | `9dd7504f-op2-capabilities-20261017` | Thiếu `094bc93b`: `eval_fixture.py` và `platform_access.py` |
| reception | `fix-reception-assets-20261015` | Đủ (sau đó Reception chỉ đổi test) |
| resident, operations | `stability-20261016` | Đủ |

- `vinhomes-declaration.json` trên develop2 có `leader_brief` mới. Bản này cần onboard lại thì Platform mới nhận.
- `dev_Chien` chứa phần Vin N1/N2: IAM, quota, KB riêng, catalog khách hàng, Leader của cư dân. Phần này chưa vào develop2 và chưa có trên VPS. Cần chốt nhánh nền cho các việc dưới đây (câu hỏi Q1).

## 2. Domain: Reception

### 2.1 Model và suy luận

- VPS đặt `RECEPTION_MODEL=gpt-5.6-luna` và `RECEPTION_AGENT=loop`.
- `runtime/model.py` gửi `reasoning_effort: "none"` cho luna vì Chat Completions không cho dùng function tool cùng reasoning. Các nguồn thứ ba cũng xác nhận giới hạn này và khuyên dùng Responses API.
- Hệ quả: model chọn tool, mức ưu tiên và nhóm dịch vụ mà không suy luận.

**Hướng sửa:**
- Thêm adapter Responses API cho Reception: `POST /v1/responses`, tool, `reasoning.effort`, `text.format` JSON.
- Chọn adapter theo env `RECEPTION_MODEL_API=responses|chat`.
- Effort mặc định `low` cho mỗi lượt và `medium` cho bước đánh giá phiếu.
- Đếm `reasoning_tokens` vào usage.

### 2.2 Đánh giá yêu cầu thành phiếu (gate intake)

Luồng hiện tại (`reception_intake.py` và `agent/tools.py`):
1. Model phải chép NGUYÊN VĂN các ô `symptom`, `area`, `item`.
2. Server chỉ nhận ô có chuỗi con khớp tin cư dân, có xét phủ định bằng regex.
3. Ô `item` phải nằm trong từ điển 29 thiết bị (`ITEM_NAMES`), nếu không thì hỏi lại tối đa 2 lần.
4. Câu hỏi lại là 3 câu mẫu cố định.
5. Tiêu đề phiếu là dòng đầu tin cư dân; mô tả là tin cư dân ghép lại.
6. `severity` luôn là `"unknown"`. `priority` do model chọn khi không suy luận.

Hệ quả: hỏi lại thừa khi thiết bị nằm ngoài từ điển ("máy hút mùi", "bình nóng lạnh âm trần"). Phiếu gửi Leader và BQL không có tóm tắt hay lý do. Mức ưu tiên thiếu căn cứ.

**Thiết kế mới** (giữ nguyên tắc "chỉ ghi điều cư dân nói", bỏ phụ thuộc từ điển):
1. **Bước đánh giá có suy luận**, structured output. Model trả về:
   - `intent`, `category_code`, `kind`;
   - `priority` và `urgency`, mỗi mục có `reason`;
   - `safety_signals`;
   - `facts[]`: mỗi fact có `quote` (đoạn nguyên văn) và `value` (giá trị chuẩn hóa);
   - `missing[]`, một `question` tốt nhất, `summary_title`, `confidence`.
2. **Gate tất định trên server** chỉ kiểm:
   - mỗi `quote` có trong tin cư dân và không bị phủ định (giữ `found()` và `negated()`);
   - khẩn cấp theo policy;
   - tối đa 2 câu hỏi;
   - câu hỏi đúng một câu và không có mã nội bộ; nếu sai thì dùng câu mẫu.
   - Từ điển `ITEM_NAMES` chỉ còn là phương án dự phòng khi model không trả `item`.
3. **Phiếu có cấu trúc:**
   - nguyên văn lời cư dân, như hiện nay;
   - "Tóm tắt của Lễ tân", có nhãn rõ;
   - lý do mức ưu tiên;
   - danh sách fact kèm trích dẫn.
   - Leader đọc phiếu này qua `ticket_input` của declaration.
4. **Kiểm thử:**
   - golden G01–G13;
   - 20 ca intake mới: thiết bị ngoài từ điển, nhiều hạng mục, phủ định, sửa lời, khẩn cấp, dịch vụ;
   - chạy bằng model giả lập offline.
   - Bản chạy model thật: tôi chuẩn bị lệnh, bạn tự chạy.

### 2.3 UI tiến độ thời gian thực và thẻ xác nhận (resident-web)

Hiện tại:
- `ProcessingStatus` là spinner, một dòng nhãn và bộ đếm giây.
- Sau bàn giao chỉ hiện trạng thái `waiting_platform` trong 180 giây.
- Platform không gửi bước nào về Domain: Leader nhận phiếu, mời chuyên viên, giao nhân viên.

**Sửa:**
- **Hợp đồng:** Platform phát sự kiện `case.progress` với tập stage công khai: `received`, `assessing`, `specialist_review`, `staff_assigned`, `waiting_quote`, `in_progress`, `result_ready`. Không có tên agent, mã hay nội dung nội bộ. Domain lưu sự kiện vào `resident_progress` hiện có.
- **Thẻ tiến độ ghim đầu hội thoại** (stepper), tách khỏi bong bóng chat:
  - bước đã xong, bước đang chạy và thời gian ước lượng chỉ khi có dữ liệu;
  - trạng thái "cần bạn làm".
  - Bước của Reception (context, searching, request) gộp thành một dòng "Lễ tân đang xử lý".
- **Bộ thẻ xác nhận thống nhất:** ApprovalCard, QuoteCard, BookingCard, CompletionCard và QuestionCard dùng chung một khung:
  - header có icon và nhãn trạng thái;
  - phần tóm tắt và bảng chi tiết;
  - hạn trả lời (đếm ngược khi có `expires_at`);
  - nút chính và nút phụ, trạng thái đang gửi;
  - kết quả sau khi bấm, có thời điểm.
  - Đạt chuẩn trợ năng: focus, `aria-live`, vùng chạm 44 px.
- **Kiểm tra:**
  - vitest cho từng trạng thái thẻ;
  - ảnh chụp mobile và desktop trước và sau, để bạn duyệt giao diện.

## 3. Platform

### 3.1 Tách cổng chat / Workforce / Leader

Đã làm trong `a185cc2d`:
- `/chat` giữ chat cá nhân và nhóm cá nhân.
- `/workforce/leader?scope=leader` chỉ hiện phiếu cư dân. Phiếu BQL ẩn và phiếu cá nhân bị loại.
- Runtime ghi đúng nguồn (`partner_api`, `management`, `platform_chat`).

Còn lại:
- Phiên tạo bằng nút "Tạo session thử" vẫn nằm chung danh sách phiếu. Đề xuất: gắn nhãn "Thử", có bộ lọc, hoặc chuyển sang một tab riêng.
- 3 phiếu `needs_attention` ngày 16–17/10, trước bản sửa: cần đọc log hoặc sự kiện để biết nguyên nhân. Lý do không lưu trong payload workflow.

### 3.2 Context, memory, suy luận, chi phí, phối hợp agent

| Mục | Hiện trạng (code và VPS) | Việc cần làm |
|---|---|---|
| Suy luận | `_apply_reasoning_effort`: Chat Completions bỏ qua; nếu `WORKFORCE_MODEL_NAME=gpt-6-luna` thì thoát luôn, kể cả khi dùng Responses. `_model.py` hạ Responses về Chat khi credential có `base_url`, trừ khi `OPENAI_CHAT_API=responses`. VPS: effort Leader và agent đều `none`. | Chuyển credential OpenAI sang `OpenAIResponseModel` và bỏ điều kiện thoát cho luna. Effort: Leader `medium`, agent `low`, builder và judge `medium`. Truyền lại reasoning items (Đợt 3.1 của kế hoạch 15/10). Bật trước trên room_eval offline, rồi bạn chạy thử thật. |
| Context chung / riêng | Đã có: TeamSay rút gọn, `SharedTaskState`, nén lịch sử riêng của Leader, recall đặt sau history, Leader còn 2 lần gọi mỗi phiếu. `team_shared_context_snapshots` có 5.240 dòng cho 29 context. | Giới hạn số snapshot giữ lại cho mỗi context, hoặc dọn snapshot cũ. Đo lại prefix cache khi bật Responses. |
| Knowledge riêng agent | Spec agent có `knowledge` và `skills`; runtime đọc KB theo spec. | Không cần sửa, chỉ kiểm khi Builder gắn sai KB (mục 3.3). |
| Memory / học tăng cường | Chỉ học khi cư dân xác nhận đóng phiếu. VPS có 1 phiếu closed, nên 0 memory. | Thêm nguồn học có gate: BQL đóng phiếu có ghi chú, và ca eval đã sửa thành công (chỉ là ứng viên, chờ duyệt). Kiểm toàn bộ đường đi bằng kịch bản offline đến khi có bản ghi `agent_memories`. |
| Agent phản biện nhau | Chưa có bước phản biện có cấu trúc; thành viên chỉ báo cáo cho Leader. | Thêm "vòng phản biện" một lượt, chỉ cho quyết định rủi ro (thao tác ghi, báo giá, đóng phiếu, khẩn cấp). Một thành viên khác trả JSON `{agree, issues[], evidence_codes[]}`. Leader phải xử lý từng issue trước khi gửi cư dân. Báo cáo thành viên chuyển sang structured output (Đợt 3.2). |
| Chi phí vào/ra | Ledger đủ token, cache và latency. Thiếu bảng giá; chưa tách `reasoning_tokens`. | Xem mục 3.5. |
| Độ trễ suy nghĩ | Có p50/p95 theo model. | Thêm p50/p95 theo vai trò (Leader, thành viên, builder, judge), có cột thời gian suy luận khi provider trả về. |

### 3.3 Builder

Đang ổn:
- Chọn tool MCP theo ID có trong catalog.
- Gắn KB và skill theo ID.
- Mỗi tool chỉ thuộc một agent.
- 5 test mỗi agent, có ca an toàn.
- Chạy eval trước khi phát hành.

Vấn đề:
1. **Agent trùng nghiệp vụ:**
   - Builder không được biết danh sách agent đang có.
   - Server chỉ tính `reuse_similarity` (Jaccard theo từ) rồi hiển thị con số, không dẫn tới quyết định nào.
   - Module `ReuseMatcher` của nhóm (`workforce/builder/_reuse_matcher.py`) không được console dùng.
2. **Catalog bị cắt:** `json.dumps(...)[:6000]` cắt ngang JSON. Thư viện KB hoặc skill lớn thì phần sau bị mất và JSON hỏng.
3. **Thiếu thông tin tool:** Builder chỉ thấy tên và mô tả tool, không thấy:
   - input schema;
   - đọc/ghi, cần đồng ý;
   - cần ticket grant.
   - Vì vậy Builder sinh test đòi tool chạy mà không có ticket.

**Sửa:**
- **Đưa roster agent hiện có vào prompt** (tên, mục tiêu, tool, phiên bản).
  - Mỗi agent dự kiến phải chọn `create`, `update_existing(agent_id)` hoặc `reuse_existing(agent_id)`.
  - Server tính độ trùng: Jaccard trên mục tiêu kết hợp tỷ lệ trùng tool. Trên ngưỡng thì chặn `create`, trừ khi người dùng xác nhận.
  - UI hiện: "Đã có *Agent Vệ Sinh* làm việc tương tự (82%) — Cập nhật agent đó / Dùng lại trong nhóm / Vẫn tạo mới".
  - Nếu chọn "Cập nhật" thì tạo bản nháp mới của agent cũ, đi qua quy trình kiểm thử và phát hành như hiện nay.
- **Catalog gọn và hợp lệ:**
  - mỗi tool có tóm tắt schema (tên tham số, tham số bắt buộc) và cờ `read_only`, `requires_consent`, `ticket_scoped`;
  - KB và skill liệt kê đủ danh sách tên và mô tả rút gọn, không cắt chuỗi JSON;
  - quá ngân sách token thì xếp hạng theo độ liên quan với yêu cầu.

### 3.4 Eval (sinh case và chấm)

Số liệu thật trên VPS:
- 178 ca: 103 đạt, 75 không đạt.
- Tiêu chí trượt nhiều nhất: `task_completion` 21 lần, `tool_use` 16 lần.
- 6 ca lỗi môi trường `TICKET_GRANT_REQUIRED`.
- Agent mới đạt 0/3, 0/4, 0/5. Agent điều phối, kỹ thuật, an ninh, vệ sinh của BQL đạt hầu hết.

Nguyên nhân:
1. **Tool Vinhomes cần ticket grant.** VPS để trống `WORKFORCE_EVAL_SANDBOXES`, nên ca nào cần đọc dữ liệu (knowledge, ticket, amenity) cũng lỗi, hoặc agent trả lời "thiếu mã ticket".
2. **Test sinh ra không bám thực tế:**
   - đòi chuyển cho "agent du lịch" không có trong roster;
   - đòi cụm từ nguyên văn như "Tổng doanh thu đúng theo dữ liệu";
   - đòi tool mà agent không được cấp.
3. **Agent thành viên chỉ gửi TeamSay cho Leader**, không viết câu trả lời. Bộ chấm coi là chưa hoàn thành; TeamSay mô phỏng còn bị chấm trượt `tool_use`.
4. **Quy tắc chấm:** một ca chỉ đạt khi cả 4 tiêu chí và mọi kiểm tra chuỗi đều đạt. Bộ chấm dùng cùng model, không suy luận.
5. **Giới hạn bước:** `max_steps=4`, nên ca nhiều bước dễ hết lượt.

**Sửa (sandbox để sau, theo ý bạn):**
- **Sinh test có căn cứ.** Builder nhận:
  - schema và cờ của tool đã cấp;
  - roster thật;
  - ngữ cảnh ca: có hay không có phiếu bàn giao.
  - Bỏ kiểm tra chuỗi nguyên văn dài; `must_include` chỉ cho token ngắn (số, mã). Còn lại chuyển thành tiêu chí ngữ nghĩa cho bộ chấm.
- **Chế độ "fixture ca" khi chưa có sandbox:**
  - mỗi ca nhận một phiếu bàn giao giả;
  - tool đọc có `ticket_scoped` trả dữ liệu giả đúng schema, ghi nhãn `fixture`;
  - tool ghi vẫn chạy mô phỏng.
  - Báo cáo ghi rõ "dữ liệu giả, chưa kiểm trên dữ liệu thật".
- **Chấm công bằng:**
  - judge chạy effort `medium`;
  - tiêu chí được phép `not_applicable`;
  - ca đạt khi `task_completion`, `evidence`, `scope_safety` đạt; `tool_use` chỉ để tham khảo, trừ khi ca có `expect_tool`;
  - TeamSay gửi Leader được tính là câu trả lời của thành viên.
  - `max_steps` tăng lên 6.
- **Vòng tự sửa:**
  1. Ca trượt được phân loại: lỗi agent, lỗi thiết kế test hoặc lỗi môi trường.
  2. Lỗi agent: Builder đề xuất sửa prompt hoặc luật. Lỗi test: đề xuất sửa test.
  3. Chạy lại tối đa 2 vòng.
  4. Người dùng xem diff và duyệt; không tự phát hành.
- **UI eval:**
  - thanh quy trình: Sinh case → Chạy → Chấm → Đề xuất sửa → Chạy lại, mỗi bước có số ca và thời gian;
  - bảng tóm tắt: số đạt và trượt theo loại lỗi;
  - mỗi ca là một thẻ có chip kết quả từng tiêu chí;
  - dòng thời gian của ca: khách nói → agent → tool (đọc thật / fixture / mô phỏng) → trả lời → bộ chấm;
  - bộ lọc "chỉ ca trượt";
  - nút "Áp dụng đề xuất sửa".

### 3.5 Trang quản lý agent: sơ đồ, đồng bộ, chi phí $

Hiện tại:
- Danh sách lấy `studioApi.listAgents()`; sơ đồ lấy `agentApi.list()` qua `useAgents`. Hai nguồn khác nhau, không có cache chung, nên xóa ở danh sách thì sơ đồ không đổi.
- Mặc định mở danh sách.
- Node không kéo được ("nothing to drag").
- Cạnh có hiệu ứng (streak, dots) nhưng chưa nối với sự kiện handoff thật.

**Sửa:**
- **Một nguồn dữ liệu:** React Query key `['studio','agents']`. Sơ đồ dựng từ chính danh sách đó cộng Leader. Xóa, phát hành, ngừng hay tạo agent đều làm mới cả hai view.
- **Mặc định mở sơ đồ.** Danh sách là tab thứ hai, hoặc panel bên cạnh có cùng lựa chọn: chọn ở danh sách thì node sáng lên.
- **Kéo thả node:** lưu vị trí theo người dùng (server-side user prefs; fallback localStorage). Có nút "Sắp xếp lại" và "Vừa màn hình".
- **Hiệu ứng 2.5D/3D:**
  - mặt phẳng phối cảnh nghiêng, node có độ sâu và bóng;
  - hạt sáng chạy trên cạnh theo sự kiện handoff thật (`team_handoffs`, room stream): Leader → agent khi giao việc, agent → agent khi TeamSay, agent → Leader khi báo cáo;
  - pulse khi agent đang chạy, hover để làm nổi đường đi;
  - có công tắc tắt hiệu ứng cho máy yếu và `prefers-reduced-motion`.
  - Dùng React Flow sẵn có cộng CSS 3D và framer-motion. Không cần three.js cho sơ đồ; `Office3D` vẫn dành cho phòng làm việc của phiên.
- **Chi phí $:**
  - nạp bảng giá vào `model-prices.json`;
  - tính lại chi phí khi đọc cho các lần gọi cũ chưa có giá (giá snapshot theo `effective_from`);
  - hiện $ theo agent, theo phiếu, theo ngày, kèm tổng $ ước tính / tháng;
  - tách `reasoning_tokens`.
  - Định dạng `$0.0123` khi dưới 1 USD.
  - Giá gpt-6-luna từ nguồn thứ ba: $0.10 / 1M input, $0.50 / 1M output, cached $0.01. Chưa đối chiếu được với trang giá chính thức của OpenAI, cần bạn xác nhận (Q4).

### 3.6 Kênh kết nối

- Discord ổn định: 3 kênh có heartbeat (khóa liveness TTL 26 s, liên tục làm mới); không có lỗi Discord trong log app.
  - discord.py tự kết nối lại; vòng lặp có backoff 1–30 s.
  - Đã có: token mã hóa, allowlist, phê duyệt qua nút.
- **Thêm kênh khác:** làm được.
  - Mỗi kênh là một lớp `ChannelBase` (`channel_type`, `Credentials`, `Config`, `start_listening`, `send_response`), đăng ký trong `create_app(channels=[...])`.
  - Form trên web tự sinh từ JSON Schema.
  - Hiện đăng ký DingTalk, Discord, Feishu.
  - Thêm Telegram, Zalo OA hoặc Slack: khoảng 300–600 dòng mỗi kênh, cộng test.
  - Đề xuất ẩn DingTalk và Feishu nếu không dùng ở Việt Nam (Q5).

### 3.7 Trang Model, MCP, Skill, Knowledge và Builder

- Builder đọc được:
  - MCP đang bật (tool đã khám phá);
  - KB của tài khoản;
  - skill đã duyệt và đang bật;
  - model theo credential người dùng chọn.
- Còn thiếu:
  - schema và cờ của tool (mục 3.3);
  - catalog bị cắt (mục 3.3);
  - tài nguyên chia sẻ: Builder chỉ đọc theo `user_id`. Trên VPS, MCP nằm ở tài khoản `fbcc…` còn KB và skill ở `600f…`, nên Builder của một tài khoản không thấy đủ cả ba loại. Cần dùng `ResourceAccessService` để đọc cả tài nguyên được chia sẻ.

## 4. Kế hoạch triển khai

Mỗi đợt: một nhánh từ nhánh nền, commit theo lát, PR, test tự động. Model thật chỉ do bạn chạy.

| Đợt | Nội dung | Kiểm chứng |
|---|---|---|
| A. Đồng bộ triển khai (0,5 ngày) | Chốt nhánh nền (Q1); deploy API Domain `094bc93b`; onboard lại declaration; dọn release cũ trên VPS Platform | `docker ps` có tag mới; `/api/health` 200; checksum nguồn khớp commit |
| B. Suy luận cho Platform và Reception (1–1,5 ngày) | Responses API cho credential OpenAI; bỏ điều kiện thoát luna; effort theo vai trò; đếm reasoning token; adapter Responses cho Reception | Unit test request body; room_eval offline; bạn chạy 1 lệnh thật có tool (bài học 15/10) |
| C. Reception: đánh giá phiếu (2 ngày) | Bước đánh giá có suy luận và gate trích dẫn; phiếu có cấu trúc; câu hỏi do model sinh, có kiểm | 20 ca intake mới và G01–G13 pass offline; test backend intake |
| D. UI cư dân (2 ngày) | Sự kiện `case.progress` (Platform → Domain); thẻ tiến độ ghim; bộ thẻ xác nhận thống nhất | vitest; ảnh trước/sau để bạn duyệt |
| E. Builder (1,5 ngày) | Roster và quyết định create/update/reuse; catalog có schema, không cắt; đọc tài nguyên chia sẻ | Test builder với model giả: trùng thì chặn, sửa thì tạo bản nháp |
| F. Eval (2 ngày) | Sinh test có căn cứ; fixture ca; chấm công bằng; vòng tự sửa; UI quy trình | Bộ ca trượt từ VPS (đã ẩn danh) chạy lại offline; tỷ lệ "lỗi thiết kế test" về 0 |
| G. Trang agent (2 ngày) | Một nguồn dữ liệu; mặc định sơ đồ; kéo thả và lưu vị trí; hiệu ứng 2.5D theo handoff thật; chi phí $ | Test frontend: xóa ở danh sách thì node mất; tsc sạch; ảnh để bạn duyệt |
| H. Phối hợp và memory (2 ngày) | Vòng phản biện cho quyết định rủi ro; báo cáo thành viên có cấu trúc; thêm nguồn học có gate; tiết chế snapshot | room_eval offline: số lần gọi, token, pass^k; có bản ghi memory sau kịch bản đóng phiếu |
| I. Kênh mới (tùy Q5) | Một kênh (ví dụ Telegram) theo `ChannelBase` | Test với transport giả |

Thứ tự đề xuất: A → B → C → F → E → G → D → H → I. B ảnh hưởng chất lượng của mọi mục khác. F và E giải quyết việc "eval toàn fail".

## 5. Câu hỏi cần bạn quyết

- **Q1. Nhánh nền:** làm trên `develop2` (đang chạy VPS) hay `dev_Chien` (có Vin N1/N2, chưa deploy)? Nếu là `dev_Chien` thì cần merge vào develop2 và deploy trước.
- **Q2. Model Reception:** VPS đang chạy `gpt-5.6-luna`, không phải `gpt-6-luna`. Có đổi sang `gpt-6-luna` không?
- **Q3. Mức suy luận:** đồng ý Leader `medium`, agent và Reception `low`, bước đánh giá phiếu, builder và judge `medium` không? Chi phí output và độ trễ sẽ tăng; tôi sẽ đo bằng offline rồi bạn chạy thử thật.
- **Q4. Bảng giá:** xác nhận giá gpt-6-luna ($0.10 / $0.50 / cached $0.01 cho 1M token) và giá của các model khác bạn dùng (gpt-5.6-luna, gpt-5.5…), hoặc gửi link trang giá chính thức.
- **Q5. Kênh mới:** cần kênh nào trước: Telegram, Zalo OA hay Slack? Có ẩn DingTalk và Feishu không?
- **Q6. Sơ đồ 3D:** chọn 2.5D trên React Flow (nhẹ, kéo thả tốt), hay 3D thật bằng three.js (ấn tượng hơn nhưng nặng và kéo thả khó hơn)?
- **Q7. Phiên thử của Leader:** ẩn khỏi danh sách phiếu, hay giữ chung nhưng có nhãn "Thử"?
