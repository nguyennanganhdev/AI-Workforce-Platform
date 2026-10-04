# Tính năng OpenBot có thể dùng cho BQL: kiểm tra mã nguồn ngày 05/10/2026

## Cập nhật sau khi triển khai (05/10/2026)

Bốn việc ở phần Kết luận đã làm xong; chi tiết và phần còn lại ở `tasks/todo.md`. Khi làm, ba nhận định của tài liệu
này hóa ra chưa đúng hoặc chưa đủ:

- **Routines không chạy được trong tool host.** Tool host (`technical-api/runtime.ts`) từ chối mọi lời gọi khi role
  database của nó có quyền `UPDATE` hoặc `DELETE` trên bất kỳ bảng nào, mà lịch thì phải cập nhật mỗi lần chạy. Lịch
  chạy vì thế là một dịch vụ riêng (`server/src/room-routines`) với role riêng.
- **Xóa lịch không tự xóa lượt chạy.** Trong schema này khóa ngoại của `routine_runs` là `ON DELETE RESTRICT`, khác
  với chú thích "its runs cascade" trong `routines/store.ts`. Dịch vụ xóa lượt chạy trước rồi mới xóa lịch.
- **Rủi ro ở mục 9 là thật.** Thử với role không phải superuser: `sweepAuditTrail` xóa 0 dòng khi không khai tenant,
  và xóa đúng các dòng quá hạn khi khai tenant trên kết nối.

Thêm một điều tài liệu chưa nêu: bảng `retrieval_runs` đòi một người dùng thật cho mỗi lần tra cứu, trong khi lượt chạy
của chuyên viên trong phiên Supervisor không có người. Module tri thức đã được sửa để nhận "không có người".

## Kết luận

Phần lớn tính năng OpenBot nằm trong server Hono (`server/src/index.ts`), mà bộ triển khai Vinhomes **không chạy** server này. Vì vậy câu hỏi đúng cho từng tính năng là: module nào tách ra dùng được trong một tiến trình Bun riêng (như cách tool host đang dùng `plugins/mcp.ts`), và module nào dính chặt vào server, vào đăng nhập better-auth và vào dịch vụ ngoài CopilotKit Intelligence.

Bốn việc nên làm trước:

1. **Lịch chạy định kỳ cho agent (Routines).** Bốn module lõi (`schedule.ts`, `store.ts`, `sweep.ts`, `work/queue.ts`) chỉ phụ thuộc database và có test; bảng đã có sẵn; phần "chạy lượt" có thể đi qua luồng `@agent` trong phòng mà Supervisor đang xử lý. BQL nhận báo cáo sáng tự động mà không cần hợp nhất đăng nhập.
2. **Kho tri thức cho agent của BQL.** Dịch vụ tìm kiếm (`server/src/knowledge/`) đang chạy cho Reception, nhưng chỉ cấp quyền cho cư dân. Trường `knowledge_namespace_ids` trong cấu hình agent trỏ sang bảng khác (`memory_namespaces`) và không có mã nào đọc. Cần một đường cấp quyền cho lượt chạy của chuyên viên và một nhánh trong tool gateway.
3. **Ảnh và tệp trong phòng điều phối.** Không dùng lại nguyên bộ đính kèm của OpenBot (lưu byte trong database, gắn với thread của Intelligence), nhưng dùng lại được phần kiểm tra loại tệp và giới hạn; bảng `message_files` và kho S3 của API đã có.
4. **Hai việc nhỏ về vận hành và an toàn:** dọn nhật ký theo thời hạn (`sweepAuditTrail`) và kiểm tra tham số trước khi gọi MCP ngoài (`inspectToolArguments`). Cả hai là hàm độc lập.

Danh sách ứng viên ban đầu sai ở bốn điểm: "playground" không phải nơi thử agent; "routing" không phải chọn model theo agent; "tóm tắt" và "tiêu đề" là một tính năng; không có chức năng xuất nhật ký.

## Phạm vi và cách kiểm

- Đọc tại commit `04a5131`, nhánh `dev_teamChien_HuyDo`. Không chạy dịch vụ, không chạy test, không gọi model, không truy vấn database, không đọc tệp `.env`.
- Đã đọc: route, store, bảng (`server/src/db/schema/tables.ts`, `server/drizzle/0000_grey_blockbuster.sql`), trang UI, tên tệp test và tài liệu của chủ mã (`docs/routines.md`, `docs/configuration.md`) cho từng tính năng; phía Vinhomes đọc `services/vinhomes-api/src/vinhomes_api/`, `agent-coordination/src/vinhomes/`, `agent-bot/src/`, `app/src/features/vinhomes-operations/connected/`, `deploy/vinhomes/compose.yml`, hai tệp grant.
- "Có test" trong tài liệu này nghĩa là **có tệp test trong `server/tests/`**, không phải đã chạy và thấy đạt.
- Không đọc từng dòng các tệp lớn (`plugins/store.ts` 7615 dòng, `composio-adapter.ts` 4804 dòng, `copilot.ts` 2350 dòng); với các tệp này chỉ đọc phần đầu, chữ ký hàm và đoạn liên quan.
- Bỏ qua thư mục `.codex-artifacts/` (bản sao cây mã của các phiên khác).

## Từng tính năng

### 1. Routines: agent chạy theo lịch

- **Làm gì.** Một chỉ dẫn đứng sẵn, chạy theo biểu thức cron năm trường, kết quả đăng vào một kênh như tin nhắn của Bot. Chạy với danh nghĩa người tạo (`docs/routines.md:97-105`).
- **Mức hoàn thiện.** Chạy được, có test (`server/tests/routine-*.test.ts`, `routines-store.integration.test.ts`, `builtin-routines.test.ts`). Giới hạn có sẵn: tối thiểu 15 phút một lần (`routines/schedule.ts:4`), tối đa 20 lịch đang bật mỗi người (`routines/store.ts:64`), chỉ dẫn tối đa 2000 ký tự (`store.ts:66`), tắt sau 10 lần lỗi liên tiếp (`routines/runner.ts:50`), bỏ qua lần chạy trễ quá 10 phút (`routines/sweep.ts:57`). Còn thiếu theo chính tài liệu của chủ mã: không có trang quản trị xem lịch của người khác, không có trần theo toàn hệ thống (`docs/routines.md:114-118`).
- **Điểm khác với danh sách ứng viên.** Không có màn hình hay API tạo lịch: `routines/routes.ts:18-22` nói rõ chỉ có liệt kê (`:39`), bật tắt (`:50`), xóa (`:71`). Tạo và sửa chỉ qua bốn công cụ Bot gọi trong hội thoại (`plugins/builtin-routines.ts:75`, `129`, `139`, `188`).
- **Bảng và route.** `routines` (`tables.ts:6662`), `routine_sweeps` (`:6738`), `routine_runs` (`:6754`), `work_items` (`:7266`). `/api/routines` (`app.ts:1299`), `/internal/routines/run` (`app.ts:1016-1017`, xác thực bằng `WORKER_SHARED_SECRET`). Tiến trình quét: `server/scripts/fire-routines.ts`, `charts/openbot/templates/routines/cronjob.yaml`.
- **Đăng nhập và phạm vi.** Theo người sở hữu ở mọi route; kênh phải có cả người đó và agent đó (`store.ts:330-361` nối `channels`, `channel_memberships`, `channel_agents`).
- **Thư viện ngoài.** `cron-parser` bản 5.10.0 (`node_modules/cron-parser/package.json:3`); README của gói ghi trường giây là tùy chọn (`README.md:33`) và có tùy chọn múi giờ `tz` (`README.md:81`). OpenBot tự ép đúng năm trường trước khi gọi (`schedule.ts:23-25`).
- **Vinhomes đang dùng chưa.** Chưa. Không tìm thấy "routine" trong `services/vinhomes-api/src`, `agent-coordination/src/vinhomes`, `app/src/features/vinhomes-operations`.
- **Cần xây gì.**
  - Dùng lại nguyên: `schedule.ts`, `store.ts`, `sweep.ts`, `work/queue.ts` (chỉ import database và schema). `resolveChannel` kiểm đúng ba bảng mà phòng quản lý của Vinhomes đang dùng (`v3_rooms.py:46-58`, `79-93`), nên một thành viên BQL và một agent trong phòng qua được kiểm tra mà không sửa store.
  - **Không dùng lại được:** `routines/run-turn.ts`, vì lượt chạy đi qua thread và gateway của Intelligence (`run-turn.ts:1-9`, `35-41`).
  - Thay phần chạy lượt: tiến trình quét gọi một endpoint nội bộ mới của API, endpoint này ghi tin nhắn kèm `@agent` với danh nghĩa chủ lịch, dùng lại logic của `post_room_message` (`v3_rooms.py:114-162`). Supervisor đã lấy các mention đang chờ qua `/room-mentions` (`v3_room_runtime.py:35-41`, `agent-coordination/src/vinhomes/backend.py:52`).
  - Tạo, sửa, liệt kê: thêm route vào tool host (cùng kiểu `technical-api/connection-routes.ts`) gọi `createRoutineStore`, vì `next_run_at` bắt buộc và được tính bằng `nextOccurrence` phía TypeScript; API chuyển tiếp kèm mã người dùng đã xác thực.
  - UI: một biểu mẫu trong trang Agent (agent, lịch chọn sẵn, chỉ dẫn). Phải truyền múi giờ `Asia/Ho_Chi_Minh` vì mặc định của cột là `UTC` (`tables.ts:6678`).
  - Grant cho role của tool host: ghi `routines`, `routine_runs`, `routine_sweeps`, `work_items`; đọc `channel_agents`.
- **Rủi ro chính.** Tốn model lúc không ai xem; trần 20 lịch là theo người, không theo đơn vị. Kết quả của lần chạy (`finishRun`) phải được định nghĩa lại vì lượt chạy thật diễn ra ở Supervisor chứ không ở tiến trình quét.
- **Cỡ:** vừa.

### 2. Playground của quản trị

- **Làm gì.** Không phải nơi thử agent. Đây là trình soạn thành phần giao diện (HTML, CSS, JS chạy trong sandbox) ở dạng nháp, xem trước rồi phát hành để Bot dùng khi trả lời (`app/src/routes/_authed/admin/playground.tsx:29-35`, `server/src/components/sandboxed.ts:5-24`).
- **Mức hoàn thiện.** Chạy được, có test (`sandboxed-components.integration.test.ts`, `component-*.test.ts`). Route `server/src/components/sandboxed-routes.ts:33-168`; bảng `sandboxed_components` (`tables.ts:7184`), `components`.
- **Vinhomes đang dùng chưa.** Chưa, và phòng điều phối không vẽ thành phần sinh động nào (`coordination/RoomThread.tsx` chỉ in `m.body.text`).
- **Dùng cho BQL.** Không đáng làm lúc này: cần `CopilotProvider`, mà nhánh `/operations` cố ý không gắn (`app/src/routes/_authed.tsx:67-73`).
- **Thứ gần nhất với "thử agent".** Phía OpenBot: `POST /api/agents/test-connection` (`server/src/agents/routes.ts:417`) chỉ thử kết nối tới endpoint của Bot. Phía Vinhomes đã có đường chạy thử thật: `POST /rooms/{room}/agents/{agent}/evaluate` (`v3_agent_builder.py:68-121`) gọi `/internal/evaluations` của Supervisor (`agent-coordination/src/vinhomes/runtime.py:587`, `635`). Một ô "hỏi thử bản nháp" cho BQL nên dựng trên đường này, không phải trên playground. Cỡ: nhỏ đến vừa.

### 3. Skills: gói chỉ dẫn dùng lại

- **Làm gì.** Một skill gồm tên, tóm tắt, chỉ dẫn và danh sách công cụ nó cần. Skill được gán cho từng Bot; trước mỗi lượt, một lần gọi model chọn skill phù hợp và thu hẹp bộ công cụ được đưa cho Bot. Skill không cấp thêm quyền: bộ công cụ là giao của "skill khai báo" và "Bot đã được cấp" (`plugins/selection.ts:162-176`).
- **Mức hoàn thiện.** Chạy được, có test (`skill-ownership`, `skill-tools`, `skill-uninstall-grants` dạng integration; `plugin-selection.test.ts`).
- **Bảng và route.** `skills` (`tables.ts:7025`), `skill_tools` (`:7099`), `plugin_grants` (`:7138`). `POST /api/plugins/skills` (`plugins/routes.ts:2114`), `DELETE` (`:2218`), cấp cho Bot (`:2374`, `:2418`). Đọc lúc chạy: `plugins/store.ts:4895-4972`; chọn trong lượt: `copilot.ts:852-895`. UI: `_app/skills.tsx`, `admin/skills.tsx`, `app/src/components/skills/`.
- **Đăng nhập và phạm vi.** Ai đăng nhập cũng viết được skill của mình; skill toàn hệ thống chỉ quản trị viên (`plugins/routes.ts:2155-2162`). Bảng có `workspace_id` nhưng store không ghi.
- **Vinhomes đang dùng chưa.** Chưa. Cấu hình agent của BQL chỉ có một chuỗi `instructions` (`v3_agent_reviews.py:45-56`).
- **Cần xây gì.** Route skills đứng sau `requireUser` và lượt chọn skill nằm trong `copilot.ts`, nên không gọi thẳng được. Cách khả thi: API tự đọc ghi bảng `skills` theo workspace, và **ghép chỉ dẫn của skill vào `instructions` lúc phát hành phiên bản** (vì phiên bản bị ghim theo hash). `plugins/selection.ts` là hàm thuần, có thể dùng sau nếu cần thu hẹp công cụ theo câu hỏi.
- **Rủi ro chính.** Sửa một skill dùng chung không tự cập nhật các agent đã phát hành; phải phát hành lại và đánh giá lại từng agent.
- **Cỡ:** vừa. Giá trị chỉ rõ khi BQL có nhiều agent dùng chung quy định.

### 4. Channels: đính kèm, tiêu đề, giám sát lượt treo

**Đính kèm**

- **Làm gì.** Tải ảnh và tệp văn bản lên kênh, đưa vào lượt chạy cho model đọc. Tối đa 8 tệp mỗi tin (`shared/attachments.ts:10`), ảnh 8 MB (`:32`), văn bản 1 MB (`:66`) và model chỉ đọc 120.000 ký tự đầu (`:95`). Nhận PNG, JPEG, GIF, WebP (`:116`) và text, markdown, CSV, JSON (`:123`). **Không nhận PDF, Word, Excel.**
- **Mức hoàn thiện.** Chạy được, có test (`attachment-mime`, `attachment-parts`, `attachment-routes`, `attachment-store`, `attachment-sweeper`).
- **Bảng và route.** `attachments`, byte lưu trong cột `bytea` của database (`tables.ts:6511`, `:6527`). `POST /api/channels/:channelId/attachments` (`channels/attachments.ts:735`), `GET` và `DELETE /api/attachments/:id` (`:1448`, `:1635`).
- **Phạm vi.** Theo thành viên kênh và theo kênh của thread đang chạy; thread là thread của Intelligence (chú thích đầu `channels/attachments.ts`).
- **Vinhomes đang dùng chưa.** Chưa. Phòng điều phối chỉ có chữ: tin nhắn là `{"text", "mentionAgentId"}` (`v3_rooms.py:127`).
- **Cần xây gì.** Không dùng lại store và route (phụ thuộc Intelligence, lưu byte trong database trong khi dự án đã chọn S3). Dùng lại được: hằng số và phân loại trong `shared/attachments.ts`, kiểm tra byte đầu tệp trong `channels/attachment-mime.ts`. Phía Vinhomes đã có đủ móng: bảng `message_files` (`tables.ts:1455`, chưa có grant), `files`, `file_objects` và `storage.py`; mẫu tải ảnh có sẵn ở `v3_files.py:55` và `v3_conversation_images.py`. Việc phải làm: endpoint tải tệp cho phòng, `GRANT INSERT ON message_files`, ô đính kèm trong `coordination/parts.tsx`, và để agent thật sự "thấy" ảnh thì bộ chuyển của Supervisor phải gửi phần ảnh: hiện nó gửi JSON dạng chữ (`agent-coordination/src/adapters/openbot.py:143-153`) trong khi `agent-bot` đã đọc được phần ảnh (`shared/user-content.ts:24-56`).
- **Rủi ro chính.** Ảnh làm tăng token mỗi lượt và nằm ngoài sáu ca đánh giá hiện tại. `adapters/openbot.py` là mã lõi của team Đông.
- **Cỡ:** vừa nếu chỉ lưu và hiển thị; vừa đến lớn nếu agent phải đọc ảnh.

**Tóm tắt và tiêu đề**

- Là **một** tính năng: tiêu đề ba đến sáu từ cho kênh, lưu ở `channels.summary` (`tables.ts:6167`). `channels/summary.ts` xếp việc qua `work_items` (`:23`) và đọc hội thoại từ Intelligence (`:36`); `channels/titler.ts:29-73` là một lần gọi model. Có test (`channel-summary.integration.test.ts`, `channel-titler.test.ts`).
- Chỉ `titler.ts` tách dùng được (nhận model, khóa, `fetch`). Với BQL, danh sách phiên đã lấy tên từ ticket, nên giá trị thấp. Cỡ: nhỏ, không ưu tiên.

**Giám sát lượt treo**

- `channels/stall-guard.ts` và `turn-watchdog.ts` bọc luồng trả lời của Bot, sau một khoảng im lặng thì ghi `RUN_ERROR` và đóng luồng; cấu hình `AGENT_STALL_TIMEOUT_MS`. Có test (`stall-guard.test.ts`).
- Viết cho runtime TypeScript của OpenBot. Supervisor của Vinhomes là Python và tự đọc luồng trong `adapters/openbot.py`; không gọi được module này. Chỉ nên mượn ý tưởng (đo im lặng, không đo tổng thời gian). Không xác minh được Supervisor hiện xử lý luồng treo ra sao ngoài timeout của HTTP client.

### 5. Plugins và kết nối

- **Làm gì.** Danh mục máy chủ công cụ cố định trong mã: Google Drive qua REST (`plugins/catalogue.ts:164`), Notion qua MCP (`:225`), Routines nội bộ (`:281`), Tavily tìm web (`:303`); thêm MCP tùy chỉnh theo URL (`plugins/routes.ts:368`) và ứng dụng qua Composio (`:626`, `:718`). Mỗi người tự kết nối tài khoản của mình qua OAuth (`:986`, callback `:1960`, `plugins/oauth.ts`). Mọi lời gọi đi qua một cửa: kiểm quyền, chính sách, ghi nhật ký.
- **Mức hoàn thiện.** Chạy được, nhiều test (`plugin-*.test.ts`, `composio-*.test.ts`, `google-drive-rest.test.ts`, `tavily-rest.test.ts`). Composio cần `COMPOSIO_API_KEY`; Tavily cần `TAVILY_API_KEY` (`plugins/tavily-rest.ts:107`); Google Drive cần quản trị viên đăng ký OAuth client (`plugins/routes.ts:439`). Tài liệu: `docs/plugins/`.
- **Bảng.** `mcp_servers` (`tables.ts:6808`), `mcp_tools` (`:6874`), `composio_connections` (`:6921`), `mcp_user_credentials` (`:6969`), `plugin_grants` (`:7138`), `credentials` (`:6347`).
- **Vinhomes đang dùng gì.** Đã dùng: `plugins/mcp.ts`, `plugins/catalogue.ts` (`customUrlRefusal`) và `credentials.ts` trong tool host (`technical-api/connection-routes.ts:2-4`); API quản lý kết nối ở `v3_connections.py`, gateway gọi ở `v3_tool_gateway.py:200-212`. Chưa dùng: Drive, Notion, Tavily, Composio, OAuth theo người.
- **Cần xây gì, theo từng phần.**

| Phần | Điểm nối | Vướng gì | Cỡ |
|---|---|---|---|
| Kiểm tra tham số trước khi gọi ra ngoài | `inspectToolArguments` (`plugins/content-governance.ts:149`), tệp không import gì; gọi trong `/call` của `connection-routes.ts:89-98` | Không vướng. Chỉ phát hiện thông tin xác thực, không phát hiện dữ liệu cá nhân (chú thích đầu tệp). | nhỏ |
| Tìm web bằng Tavily | `tavily-rest.ts` cùng dạng `listTools`/`callTool` với `mcp.ts`; thêm nhánh trong tool host và dòng trong `mcp_tools` | Một khóa chung cho cả hệ thống; nội dung web đi vào câu trả lời cho cư dân nếu không giới hạn agent nào được dùng | nhỏ |
| Google Drive bằng tài khoản dùng chung của đơn vị | `google-drive-rest.ts` nhận token đã giải mã | Phải có luồng lấy và làm mới token OAuth; luồng hiện có (`plugins/oauth.ts`) gắn trạng thái với người dùng better-auth | vừa đến lớn |
| Kết nối theo từng người (OAuth, Composio) | `plugins/routes.ts:986`, `mcp_user_credentials` | Cần phiên better-auth của người dùng | lớn |

- **Rủi ro chính.** Mỗi kết nối là một nơi dữ liệu của cư dân có thể rời hệ thống. Quyết định trước đây của chủ dự án là MCP theo URL, một tài khoản chung cho mỗi đơn vị, công cụ do quản trị viên duyệt từng cái; ba dòng đầu của bảng không đổi quyết định đó.

### 6. Nhà cung cấp danh tính và SSO

- **Làm gì.** Quản trị viên đăng ký nhà cung cấp SAML hoặc OIDC; người dùng đăng nhập theo tên miền email. Ngoài ra có Google, Microsoft Entra, Okta cấu hình bằng biến môi trường.
- **Mức hoàn thiện.** Chạy được trong OpenBot, có test (`encrypt-sso-config.test.ts`, `identity-provider-audit.test.ts`). Đăng ký do plugin `@better-auth/sso` làm (`auth/index.ts:181-190`); cấu hình được mã hóa (`auth/encrypt-sso-config.ts`); liệt kê và xóa ở `app.ts:852-890` qua `auth/identity-provider-store.ts`. Bảng `sso_providers` (`tables.ts:5987`). UI `admin/identity-providers.tsx`.
- **Vinhomes đang dùng chưa.** Chưa. `password_auth.py:1` ghi rõ "independent of OpenBot SSO".
- **Cần xây gì.** Đây là việc hợp nhất đăng nhập. Hai hướng: (a) chạy phần xử lý `/api/auth/*` của better-auth và để API nghiệp vụ chấp nhận phiên better-auth trong bảng `sessions` dùng chung; (b) viết một `AuthService` thứ hai cho OpenBot đọc cookie `vinhomes_session`. Hướng (a) mới đem SSO đến cho BQL. Cả hai đụng `password_auth.py`, `v3_auth.py` và trang đăng nhập.
- **Rủi ro chính.** Sai ở đây là mất kiểm soát truy cập. Test đăng nhập mật khẩu hiện là loại phải bật tay nên thay đổi dễ lọt.
- **Cỡ:** lớn. Chỉ làm khi Vinhomes yêu cầu đăng nhập bằng tài khoản công ty.

### 7. Kho tri thức (RAG) cho agent

- **Làm gì.** Nạp tài liệu Markdown thành đoạn, nhúng vector 1536 chiều, tìm kiếm lai (vector và từ khóa), lọc theo phạm vi và danh sách quyền, trả đoạn văn kèm trích dẫn; ngưỡng tương đồng 0,35 (`knowledge/retrieve.ts:26`).
- **Nguồn gốc.** Theo chú thích trong mã, đây là module do các team dự án viết, không phải tính năng OpenBot bỏ không (`knowledge/routes.ts:12-17`, `knowledge/types.ts:10-13`). Không có remote upstream để đối chiếu.
- **Mức hoàn thiện.** Chạy được, có test (`server/tests/knowledge/`, 9 tệp và thư mục `eval`). Một route: `POST /internal/knowledge/search` (`knowledge/routes.ts:62`). Chạy riêng bằng `knowledge/serve.ts`, là dịch vụ `knowledge` trong compose.
- **Bảng.** `knowledge_bases`, `knowledge_documents`, `document_versions`, `document_scopes`, `document_acl`, `knowledge_chunks`, `knowledge_embeddings`, `retrieval_runs`, `retrieval_hits` (`tables.ts:4583-5299`), `agent_knowledge_grants` (`:1252`).
- **Đăng nhập và phạm vi.** Dịch vụ không tin thân yêu cầu; nó hỏi API tại một đường dẫn viết cứng `/internal/reception/v1/knowledge-authorization` (`knowledge/runtime.ts:32`) và chỉ phục vụ **một** kho theo biến `KNOWLEDGE_BASE_ID` (`runtime.ts:57`). Phía API, đường này đòi agent có dòng trong `agent_knowledge_grants` và người hỏi là **cư dân đã xác minh** (`reception_runtime_api.py:63-88`). Lệnh phát hành kho chỉ cấp quyền cho agent có `purpose = 'reception'` (`knowledge/publish.ts:146-149`).
- **Vinhomes đang dùng chưa.** Reception dùng. Agent của BQL thì không.
- **Sự thật về `knowledge_namespace_ids`.** Trường này được kiểm với bảng `memory_namespaces`, không phải `knowledge_bases` (`v3_agent_reviews.py:49`, `86-94`). UI chỉ chuyển lại giá trị cũ (`ManagedAgents.tsx:167`); Agent Factory luôn ghi mảng rỗng (`v3_agent_builder.py:184`); API xuất nó thành `knowledge_grants` cho Supervisor (`v3_coordination.py:520`); phía Supervisor chỉ có hai khai báo kiểu (`agent-coordination/src/agents/releases.py:30`, `supervisor/models.py:224`) và không tìm thấy chỗ nào đọc. Tức là có đường ống, không có người dùng.
- **Cần xây gì.**
  - Một route cấp quyền cho lượt chạy của chuyên viên (dựa trên `run_authority` ở `v3_tool_gateway.py:33-66`: phiên bản đã phát hành, workspace, các tòa nhà đơn vị phụ trách), trả cùng dạng mà `knowledge/runtime.ts:9-16` kiểm.
  - Cho đường dẫn cấp quyền trong `knowledge/runtime.ts` thành cấu hình, hoặc chạy thêm một bản dịch vụ cho chuyên viên.
  - Một nhánh `knowledge` trong `v3_tool_gateway.py:180-214` và một dòng công cụ đọc trong `mcp_tools`, để trang Agent tự hiện ô chọn.
  - Ghi `agent_knowledge_grants` khi phát hành (cần grant `INSERT`).
  - Quyết định số phận `knowledge_namespace_ids`: bỏ, hoặc đổi nghĩa cho đúng tên.
- **Phương án rẻ hơn.** API đã có `GET /knowledge/search` tìm theo từ khóa cho vai trò quản lý và nhân viên (`v3_knowledge.py:19-74`). Dùng nó trong gateway thì không cần dịch vụ vector, nhưng truy vấn đòi một người dùng cụ thể; lượt chạy trong phiên của Supervisor có thể không có người dùng (`v3_tool_gateway.py:52-57`), nên chỉ hợp với hỏi đáp trong phòng.
- **Rủi ro chính.** Phạm vi: chuyên viên của đơn vị này không được đọc tài liệu chỉ dành cho tòa nhà của đơn vị khác. Ngưỡng 0,35 được chọn trên bộ câu hỏi của cư dân; câu hỏi của BQL có thể cần đo lại.
- **Cỡ:** vừa.

### 8. Routing

- **Làm gì.** Không phải chọn model theo agent. `server/src/routing/` quyết định **tin nhắn không gắn `@` thuộc về Bot nào** khi tạo kênh, bằng một lần gọi model của hệ thống, và ghi `channel.routed` vào nhật ký (`routing/routes.ts:47-59`, `routing/classify.ts:1-14`). `routing/model.ts:17-24` chỉ là hàm gọi model dùng chung.
- **Mức hoàn thiện.** Chạy được, có test (`routing-classify`, `routing-routes`, `routing-model-url`, `routing-limits-validation`). Gắn ở `app.ts:1192`.
- **Vinhomes đang dùng chưa.** Chưa, và không cần: Supervisor đã chọn chuyên viên theo danh mục dịch vụ của ticket.
- **Chọn model theo agent có ở đâu.** Không có trong mã chạy. OpenBot dùng một model cho cả hệ thống (`copilot.ts:161-171`); `agent-bot` đọc một biến `BOT_MODEL` (`agent-bot/src/index.ts:47`, `141`); Supervisor truyền một `COORDINATION_OPENBOT_MODEL` cho mọi chuyên viên (`agent-coordination/src/vinhomes/runtime.py:113`). Chỉ có schema chờ sẵn: bảng `model_profiles` (`tables.ts:917`) và cột `agent_versions.model_profile_id` (`:997`); không tìm thấy mã nào đọc hai thứ này trong `server/src`, `app/src`, `services/vinhomes-api/src`, `agent-coordination/src`, `agent-factory/src`.
- **Cần xây gì nếu muốn.** `agent-bot` nhận tên model theo từng yêu cầu thay vì hằng số; phiên bản agent mang `model_profile_id`; API ghi `model_profiles`; trang Model của quản trị viên hiện chỉ đọc (`v3_admin.py:65-93`) phải thành ghi được. Mỗi lần đổi model là một lần đánh giá lại.
- **Cỡ:** vừa đến lớn. Chưa cần khi mọi chuyên viên vẫn dùng chung một model.

### 9. Nhật ký: thời hạn lưu và xuất

- **Thời hạn lưu.** `sweepAuditTrail` xóa theo lô 5000 dòng các dòng cũ hơn N ngày, giữ khóa advisory để chỉ một tiến trình quét (`audit-retention.ts:60-112`); mặc định tắt, bật bằng `AUDIT_RETENTION_DAYS` (`config.ts:1164`); gắn ở `index.ts:321`. Database chặn mọi `UPDATE` và chỉ cho `DELETE` khi giao dịch khai báo thời hạn và dòng nằm ngoài thời hạn (`server/drizzle/0000_grey_blockbuster.sql:3524-3535`). Có test (`audit-retention.integration.test.ts`).
- **Xuất.** Không tìm thấy. Đã tìm `csv`, `export`, `download`, `Content-Disposition` trong `server/src/audit.ts`, `app/src/routes/_authed/admin/audit.tsx`, `app/src/lib/audit/` và toàn bộ `server/src`. Chỉ có đọc có lọc và phân trang (`audit.ts:497-515`, route `app.ts:635-655`).
- **Tài liệu lệch mã.** `audit-retention.ts:17` ghi "See migration 0007", nhưng trigger nằm ở migration gốc `0000`; `0007_reception_supervisor_v2.sql` không có chữ "audit".
- **Vinhomes đang dùng gì.** Cùng bảng `audit_events`: API ghi (`v3_audit.py:16-20`, `v3_tool_gateway.py:226-229`) và trang Nhật ký đọc (`v3_admin.py:95-107`). Chưa có gì xóa dòng cũ.
- **Cần xây gì.** Một job Bun trong compose gọi `sweepAuditTrail`, cùng kiểu job `upgrade`. Role chạy job phải có quyền `DELETE` trên `audit_events`; `vinhomes_v3_api` chỉ có `INSERT, UPDATE` (`grant_v3_api_role.sql:18`). Xuất tệp thì viết mới trong `v3_admin.py`.
- **Rủi ro chính (suy ra từ mã, chưa chạy).** `audit_events` bật `FORCE ROW LEVEL SECURITY` (`0000_grey_blockbuster.sql:4049`) với chính sách "tenant hiện tại hoặc tenant rỗng" (`:3395`). `sweepAuditTrail` mở kết nối riêng và chỉ đặt `openbot.audit_retention_days`, không đặt `app.tenant_id`. Nếu role không phải superuser, lệnh xóa có thể chỉ thấy các dòng không có tenant, tức không dọn được gì của Vinhomes. Phải thử trên bản sao database trước khi tin.
- **Cỡ:** nhỏ (thêm một dòng đặt tenant nếu rủi ro trên là thật).

### 10. Phần còn lại trong `server/src` và `app/src/routes/_authed`

| Thư mục hoặc trang | Thực tế | Dùng cho BQL |
|---|---|---|
| `server/src/notifications/`, `platform/`, `runtime/`, `storage/` | Rỗng, chỉ có `.gitkeep`. | Không có gì để dùng. Thông báo của Vinhomes do API tự ghi vào `notification_deliveries` với kênh `in_app`; schema cho phép thêm `push`, `sms`, `email` (`0000_grey_blockbuster.sql:1318`) nhưng không tìm thấy mã gửi ba kênh đó. |
| `server/src/work/` | Hàng đợi bền trên `work_items`: nhận việc bằng `for update skip locked`, thuê theo đồng hồ database, đếm số lần thử (`work/queue.ts`). Có test. | Dùng được cho mọi việc nền của Vinhomes; Routines ở mục 1 đã cần nó. Cỡ nhỏ. |
| `server/src/people/`, `admin/people.tsx` | Danh sách người đã đăng nhập, đổi vai trò, thu hồi truy cập (`app.ts:661-850`). Có test. | Trùng với trang Tài khoản của Vinhomes (`password_auth.py:222-281`). Không dùng. |
| `server/src/computer/`, `admin/computers.tsx`, `admin/boundaries.tsx` | Máy tính có trình duyệt cho Bot, mọi thao tác qua cổng kiểm chính sách CEL và ghi nhật ký. Hoàn chỉnh, nhiều test. | Cần hạ tầng riêng (container cho từng Bot, dịch vụ supervisor). Không liên quan tới nghiệp vụ tòa nhà hiện tại. Lớn, không đề xuất. |
| `server/src/components/`, `admin/components/`, `admin/playground.tsx` | Xem mục 2. | Không đề xuất. |
| `server/src/host-access/` | Cho Bot thao tác trên máy của người dùng qua ứng dụng desktop. Có test. | Không liên quan. |
| `server/src/agents/` | Hồ sơ Bot, chuyển việc giữa các Bot (`handoff.ts`), hỏi lại con người (`escalation.ts`), Agent Factory (`factory.ts`). | Vinhomes đã có phần tương ứng riêng: Supervisor điều phối, và API gọi dịch vụ Factory trực tiếp (`v3_agent_builder.py:123-190`). Factory không sinh ca đánh giá: không tìm thấy trong `agent-factory/src`. |
| `server/src/user-instructions.ts`, trang Settings | Chỉ dẫn đứng sẵn của từng người, ghép vào mọi lượt chạy; bảng `user_instructions` (`tables.ts:5960`). | Ý tưởng hợp với "ghi chú của đơn vị" cho mọi agent, nhưng với phiên bản bị ghim thì phải ghép lúc phát hành, giống Skills. Nhỏ, chưa ưu tiên. |
| `server/src/technical-tools/`, `security-tools/`, `reporting/`, `technical-api/`, `business/`, `vinhomes/` | Mã của các team dự án, không phải tính năng OpenBot. | Ngoài phạm vi câu hỏi. |

## Điều kiện chung

Gần như mục nào ở trên cũng dựa vào các điều kiện này.

| Điều kiện | Sự thật trong mã | Hệ quả |
|---|---|---|
| Server OpenBot không chạy trong bộ Vinhomes | `deploy/vinhomes/compose.yml` chỉ có `api`, `reception`, `coordination`, `knowledge`, `technical-tools` (`bun server/src/technical-api/serve.ts`, dòng 168), `factory`, `openbot` (là `agent-bot`, dòng 201–205), hai UI. Không có dịch vụ nào chạy `server/src/index.ts`. | Mọi route `/api/...` của OpenBot (routines, plugins, skills, channels, audit, admin) không tồn tại với BQL. |
| Server OpenBot cần CopilotKit Intelligence | `docs/configuration.md:18-29`: thiếu `INTELLIGENCE_API_URL`, `INTELLIGENCE_GATEWAY_WS_URL`, `INTELLIGENCE_API_KEY` thì server không khởi động; `server/src/config.ts:871-888`. | Bật nguyên server OpenBot cho BQL kéo theo một dịch vụ ngoài mà dự án chưa dùng. |
| Hai đăng nhập tách rời | OpenBot: better-auth với Google, Microsoft, Okta và SSO (`server/src/auth/index.ts:154-191`, `226-240`); **không tìm thấy** đăng nhập mật khẩu trong `server/src/auth/`. API nghiệp vụ: cookie `vinhomes_session`, provider `vinhomes-password-v1`, token băm có tiền tố `vinhomes-v1:` (`password_auth.py:21-23`, `45-46`). | Tài khoản BQL không có phiên better-auth, nên không qua được `requireUser` (`server/src/auth/guards.ts:47-60`). |
| Vai trò đọc cùng bảng | `server/src/auth/roles.ts:29-58` đọc `platform_admins`, `scoped_user_roles`, `tenant_memberships`, đúng các bảng API dùng. | Nếu hợp nhất đăng nhập, không phải dựng lại phân quyền. Điểm nối là kiểu `AuthService` (`guards.ts:14-31`); `auth/organization.ts` là ví dụ một cách cài đặt thứ hai. |
| Tenant và workspace | Server OpenBot tự sinh tenant và một workspace từ khóa gói tenant (`server/src/db/deployment-scope.ts:14-23`, `server/src/index.ts:188-192`). Các module tách riêng nhận tenant qua `createDatabase(url, { tenantId })` (`server/src/db/client.ts:107-151`). Các store `routines/store.ts`, `plugins/store.ts`, `work/queue.ts`, `channels/attachments.ts` không ghi `workspace_id` (không tìm thấy chuỗi `workspaceId` trong bốn tệp). | Dùng module tách riêng thì truyền được tenant của Vinhomes. Phân tách theo đơn vị quản lý (workspace) phải do phía Vinhomes tự kiểm, như `v3_agent_reviews.py:75-83` đang làm với kết nối ngoài. |
| Quyền database | `vinhomes_v3_api`: `SELECT` mọi bảng, `INSERT/UPDATE` theo danh sách (`grant_v3_api_role.sql:5-22`); danh sách **không có** `routines`, `routine_runs`, `work_items`, `skills`, `plugin_grants`, `attachments`, `message_files`, `agent_knowledge_grants`, `model_profiles`. `vinhomes_technical_api` chỉ đọc và ghi vài bảng kỹ thuật (`grant_technical_api_role.sql:3-18`). | Mỗi tính năng ở trên cần thêm grant; không cần đổi schema trừ khi ghi rõ. |
| Phiên bản agent bị ghim | Lượt chạy mang `prompt_hash`, `config_hash` của phiên bản đã phát hành (`v3_coordination.py:518-519`). | Mọi thứ làm đổi chỉ dẫn hoặc công cụ của agent phải đi qua đánh giá và phát hành, không nạp động lúc chạy. |
| Ngôn ngữ | Câu chữ OpenBot là tiếng Anh, kể cả câu gửi vào kênh (`routines/runner.ts:52-53`) và mô tả lịch (`routines/schedule.ts:254-340`). | Giao diện BQL phải tự viết câu tiếng Việt; không hiển thị thẳng chuỗi của OpenBot. |

## Thứ tự đề xuất

1. **Routines.** Thấy ngay giá trị với BQL (báo cáo đầu ngày từ agent Báo cáo đã có), không cần hợp nhất đăng nhập, bốn module lõi dùng nguyên, và dựng luôn hàng đợi `work_items` cho các việc nền sau này.
2. **Kho tri thức cho agent BQL.** Tăng chất lượng trả lời nhiều nhất, dữ liệu và dịch vụ đã chạy; làm sau Routines vì phải thống nhất luật phạm vi cho chuyên viên trước khi viết mã.
3. **Kiểm tra tham số gọi MCP ngoài và dọn nhật ký.** Hai việc nhỏ, làm xen được bất cứ lúc nào; việc dọn nhật ký phải thử trên bản sao database trước.
4. **Ảnh và tệp trong phòng điều phối.** Làm phần lưu và hiển thị trước; phần cho agent đọc ảnh chờ thống nhất với team Đông vì đụng bộ chuyển lõi.
5. **Tavily.** Nhỏ, nhưng cần chủ dự án quyết định có cho agent đọc web hay không.
6. **Skills, rồi model theo agent.** Chỉ đáng làm khi BQL có nhiều agent; cả hai buộc phải đánh giá lại agent sau mỗi thay đổi.
7. **SSO và kết nối theo từng người.** Lớn, phụ thuộc quyết định hợp nhất đăng nhập; để cuối.

Không đề xuất: máy tính cho Bot và trang Boundaries, thành phần giao diện và Playground, định tuyến ý định, host-access, trang People.

## Chưa xác minh

- Không chạy test nào; không biết các test nêu trên có đạt trên schema hiện tại hay không.
- Không truy vấn database: không biết `memory_namespaces`, `agent_knowledge_grants`, `model_profiles`, `routines` hiện có dòng nào.
- Rủi ro `FORCE ROW LEVEL SECURITY` với `sweepAuditTrail` (mục 9) là suy luận từ mã và migration, chưa thử.
- Nhận định "bốn module Routines dùng nguyên được trong tool host" dựa trên danh sách import và truy vấn của `resolveChannel`; chưa chạy thử với role hạn chế và dữ liệu phòng của Vinhomes.
- Chưa đọc hết `plugins/store.ts`, `composio-adapter.ts`, `copilot.ts`; mô tả Composio và luồng OAuth dựa trên chú thích đầu tệp và chữ ký route. Chưa đọc ba tệp trong `docs/plugins/` (`composio.md`, `google-drive.md`, `notion.md`).
- Không xác minh được module nào là của OpenBot gốc và module nào do team thêm ngoài chú thích trong mã, vì lịch sử git là các lần nhập gộp và không có remote upstream.
- Không xác minh Supervisor hiện phát hiện luồng trả lời bị treo bằng cách nào (mục 4).
- Không kiểm tra hành vi thật của `@better-auth/sso` hay `@modelcontextprotocol/sdk` trong `node_modules`; chỉ đọc cách mã dự án gọi chúng. Với `cron-parser` chỉ đọc README và số phiên bản.
