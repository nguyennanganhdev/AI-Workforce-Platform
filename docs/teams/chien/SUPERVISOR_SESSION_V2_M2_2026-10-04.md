# Supervisor gọi agent chuyên môn vào phòng — kết quả M2

Ngày 04/10/2026. Nhánh `dev_teamChien_HuyDo`. Tiếp theo `SUPERVISOR_SESSION_V2_M0_M1_2026-10-03.md`.

## Chạy được gì

Cư dân báo sự cố → Lễ tân tạo yêu cầu, gán danh mục và bàn giao → Supervisor (lõi của Team Đông) nhận, trả
`accepted` → mở phòng với agent chuyên môn đã phát hành của đúng danh mục → giao việc → agent trả lời → Supervisor
ghi nhận việc đã xong → dừng với lý do `analysis_ready` → Ban quản lý đọc phân tích trên Operations và lập
phương án. Đã chạy thật với `gpt-5.4-mini` trên database dùng-rồi-bỏ: từ lúc bàn giao tới lúc có phân tích mất
khoảng 8 giây.

Chưa làm: Supervisor đề xuất phương án, hỏi lại cư dân, hai lần duyệt, giao việc cho nhân viên, nghiệm thu
(M3); agent gọi tool (cổng tool); tạm dừng và chạy tiếp từ Operations (M4).

## Bốn quyết định của điều phối (04/10)

1. Chỉ dẫn của agent kỹ thuật: Team Chiến soạn bản đầu từ `docs/teams/quang/general.md`, đi đúng luồng nháp →
   đánh giá → admin duyệt. Team Quang rà soát và sở hữu về sau (`docs/teams/quang/agent/`).
2. Model: Supervisor và agent chuyên môn dùng `gpt-5.4-mini` với khóa của Lễ tân, có giới hạn cho mỗi phiên.
3. Admin duyệt là phát hành. Admin thu hồi được. Phiên đang chạy giữ phiên bản đã nhận.
4. Agent được mời theo danh mục của ticket: backend chỉ đưa ra agent đã phát hành trong phòng Ban quản lý có
   khai báo danh mục đó.

## Ai được mời vào phòng

- BQL tạo agent nháp trong phòng của mình và khai báo cấu hình, trong đó có `service_categories` (ví dụ
  `technical`, `security`). Bản đánh giá phải đạt mọi ca mới nộp được. Admin duyệt thì backend tạo
  `agent_versions` và `agent_releases` trạng thái `published`.
- Khi Supervisor hỏi khung nhìn của một phiên, backend trả `specialists`: agent `specialist` đang hoạt động trong
  phòng Ban quản lý, có bản phát hành chưa bị thu hồi, và `service_categories` chứa danh mục của ticket. Ticket
  không có danh mục thì không ai được mời và Ban quản lý xử lý tay như trước.
- Phòng được mở với **tất cả** agent được đưa ra. Lý do: lõi của Team Đông yêu cầu người đọc dữ liệu ticket phải
  nằm trong phòng, nên không mở được với một phần danh sách. Model chỉ quyết định giao việc gì cho ai và đánh
  giá câu trả lời. Mở phòng và dừng khi mọi việc đã xong không cần gọi model.

## Contract thêm vào `/internal/coordination/v1`

| Thao tác | API | Vào → ra | Từ chối |
|---|---|---|---|
| Khung nhìn (mở rộng) | `GET /teams/{id}/view` | thêm `category`, `specialists[]` (`agent_version_id`, `agent_id`, `name`, `role`, `description`, `service_categories`, `tools`) | như cũ |
| Nhận agent vào phòng | `POST /teams/{id}/members` | `agent_version_id` → thành viên: `member_id`, `binding_id`, `role`, ... | 409 nếu không được đưa ra cho phiên này hoặc agent đã là thành viên với phiên bản khác |
| Lượt chạy của một lượt nói | `POST /teams/{id}/members/{member}/runs` | `operation_id` → `run_id` (cùng `operation_id` trả cùng run) | 404 không phải thành viên; 409 phiên bản đã bị thu hồi |
| Chứng thực trước mỗi lần gọi | `GET /teams/{id}/members/{member}/release` | → đã đánh giá, đã duyệt, đã phát hành, chưa thu hồi; hash chỉ dẫn và cấu hình; chỉ dẫn; `tool_descriptors` (hiện rỗng) | 409 phiên bản đã bị thu hồi |
| Xin phép | `POST /teams/{id}/authorize` | nay nhận kênh `reception` và `room` | 409 với `backend`, `draft` |
| Phản chiếu phòng | `POST /teams/{id}/room` | việc, câu trả lời của agent, lượt đã kết thúc → `team_tasks`, tin nhắn trong phòng Ban quản lý, `agent_runs` | 409 nếu việc hoặc câu trả lời thuộc agent không phải thành viên |

Gọi lại `POST /teams/{id}/room` bao nhiêu lần cũng được: việc khóa theo `task_id`, câu trả lời theo mã tin nhắn
của phòng. Thu hồi: `POST /admin/agents/{agent_id}/release/revoke` (admin).

## Phía Supervisor (`agent-coordination/src/vinhomes`)

- `Authority.inspect` dựng danh mục từ `specialists`. `Resolver` gọi `members` và `runs`. `Releases` lấy chứng
  thực của backend và thêm nơi OpenBot chạy. `Specialists` gọi agent qua `OpenbotAdapter` của Team Đông.
- Mỗi lượt, Bot (`agent-bot`, cổng 4200) nhận chỉ dẫn đã phát hành của agent. Bot không giữ agent nào.
- Lượt hỏng chắc chắn (câu trả lời rỗng) được lập kế hoạch lại tối đa 2 lần; sau đó phiên dừng với
  `AGENT_FAILURE`. Kết quả chưa rõ (mất kết nối giữa chừng) được hỏi lại 3 lần rồi giữ cho người xử lý.
- Giới hạn mỗi phiên: 8 lượt nói, 400.000 đơn vị trong sổ ngân sách của Team Đông (tính dư theo số byte).

## Chạy

```powershell
# agent-coordination/.env: thêm COORDINATION_MODEL, COORDINATION_OPENBOT_URL, MANAGED_AGENT_TOKEN (xem .env.example)
agent-coordination\scripts\start_openbot.ps1                 # Bot trên 4200
agent-coordination\scripts\start_vinhomes.ps1 [-Connected]   # Supervisor trên 4300
# Phát hành agent kỹ thuật (backend và Bot phải đang chạy):
agent-coordination\scripts\publish_agent.ps1 docs\teams\quang\agent\technical-agent.json -Room management-room -Approve
agent-coordination\scripts\publish_agent.ps1 docs\teams\quang\agent\technical-agent.json -Room bql-sapphire -Connected -Approve
```

Không đặt `COORDINATION_MODEL` thì hành vi như M1: nhận ticket, trả `accepted`, chuyển cho Ban quản lý.
Database đã có từ trước cần chạy lại `scripts/grant_v3_api_role.sql` (thêm quyền trên `agent_releases`).

Lưu ý: một file trạng thái mới trên database cũ sẽ đọc lại toàn bộ hàng chờ. Message của phiên đã xong bị bỏ
qua, nhưng ticket còn mở sẽ được xử lý và có gọi model.

## Đã kiểm

| Việc | Kết quả |
|---|---|
| Backend (`services/vinhomes-api`) | 63 đạt, 6 bỏ qua; có 2 test mới cho danh mục, thu hồi, vào phòng, phản chiếu |
| `agent-coordination` | 423 đạt; 16 test của gói `vinhomes` (5 mới: vào phòng, lượt hỏng chạy lại, agent hỏng liên tục, phiên bản bị thu hồi, không có model) |
| Màn Operations | `connected-operations-ui.test.tsx` 6 đạt; lint không thêm lỗi |
| Đánh giá agent kỹ thuật, model thật | 8/8 ca đạt, hai lần liên tiếp |
| Đầu-cuối, model thật, database dùng-rồi-bỏ | Lễ tân thật tạo ticket → Supervisor → agent kỹ thuật trả lời → Operations đọc được |

Chưa kiểm: hai Supervisor chạy song song; restart giữa một lượt nói; đầu-cuối tự động có agent chuyên môn với
model giả (hiện chỉ có test ở từng phía và lần chạy thật).

## Gửi các team

**Team Đông** (không sửa lõi của các bạn; mọi thứ dưới đây được bọc trong `src/vinhomes`):

1. `runtime/model.py` (`ProviderModel`) không gọi được `gpt-5.4-mini`: gửi `max_tokens` (model trả 400, cần
   `max_completion_tokens`) và so tên model trả về bằng tuyệt đối (nhà cung cấp trả `gpt-5.4-mini-2026-03-17`).
   Gói `vinhomes` dùng `PlannerModel` riêng với cùng sổ ngân sách.
2. `adapters/openbot.py` gửi `context: []`, nên Bot không có chỉ dẫn của agent. Gói `vinhomes` đưa chỉ dẫn vào
   `context` qua HTTP client truyền cho adapter.
3. Adapter bắt câu trả lời phải là JSON `{"content": ...}`. Model viết JSON đó sai (thừa `"}` ở cuối) trong
   khoảng 25–50% lần chạy thật. Adapter trong tiến trình của các bạn nhận văn bản thường; adapter từ xa thì không.
   Gói `vinhomes` cho Bot trả lời văn bản thường rồi tự dựng đối tượng JSON trước khi adapter đọc.
4. Giới hạn 2 lượt liên tiếp của cùng một agent chặn phòng chỉ có một agent chuyên môn. Gói `vinhomes` đặt
   `max_consecutive_turns` bằng `max_turns`.
5. Một `thread_id` chỉ dùng được cho một `source_run_id` (`thread_owner`), nên mỗi lượt nói là một thread riêng.
6. `ReleasedSession.runtime` chỉ nhận `openbot-chat-completions`; bảng `agent_versions.runtime` chỉ nhận
   `langgraph`, `agentscope`, `remote`. Hiện backend ghi `agentscope` và runtime tự điền giá trị các bạn cần.

**Team Quang:** agent kỹ thuật bản đầu và 8 ca đánh giá ở `docs/teams/quang/agent/`. Bản này chưa có tool nào.
Cần các bạn rà chỉ dẫn, thay 8 ca bằng bộ dữ liệu chuẩn 16 mã, và chốt cách phân biệt `TECH.ARCH.PAINT_MOISTURE`
với `TECH.PLUMB.CONCEALED_LEAK` (ca "tường ố, ẩm lan dần" model xếp vào mã đầu). Cổng tool là bước kế tiếp:
14 tool trong `server/src/technical-tools` chưa được nối vào server và 11 cổng dữ liệu còn bản `poc`.

**Team Phái:** đầu ra của Agent Factory đi vào đúng luồng này: tạo nháp (`POST /rooms/{room}/agents`), lưu cấu
hình (`PUT .../configuration`, có `service_categories`), nộp đánh giá, admin duyệt. Agent an ninh cần một bản
chỉ dẫn khai báo `service_categories: ["security"]`; tool an ninh chờ cùng cổng tool.

**Team Hoàng:** không đổi gì. Danh mục mà Lễ tân gán cho ticket nay quyết định agent nào được mời.
