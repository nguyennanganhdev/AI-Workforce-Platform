# Cổng tool cho agent chuyên môn, và khảo sát các nhánh chưa vào `develop`

Ngày 04/10/2026. Nhánh `dev_teamChien_HuyDo` (PR #31). Tiếp theo `SUPERVISOR_SESSION_V2_M2_2026-10-04.md`.

## Phần 1 — Cổng tool (M2b)

### Chạy được gì

Agent kỹ thuật trong phòng của Supervisor gọi được ba tool đọc của Team Quang: `technical.get_active_outage`
(gián đoạn điện, nước đang diễn ra), `utility_schedule.read` (lịch cắt điện, nước) và `sop_kb.retrieve` (SOP).
Đã chạy thật với `gpt-5.4-mini` trên bản đăng nhập thật: cư dân báo nước yếu, agent tra gián đoạn và SOP, ghi rõ
kết quả từng lần tra trong phân tích, Ban quản lý đọc được trên Operations.

Tool ghi và tool tạo yêu cầu (đo đạc, kết quả thi công, khóa van, vào căn hộ, gọi nhà thầu) **chưa mở** cho
phiên điều phối.

### Đường đi của một lần gọi tool

```
Bot (model) xin gọi tool
  → Supervisor (agent-coordination, ToolGateway): gửi mã lượt chạy của lượt nói + tên tool + tham số
  → Dịch vụ tool (server/src/technical-api/serve.ts, cổng 8788)
       đọc database: lượt chạy còn chạy? thành viên còn trong phiên? phiên bản còn phát hành?
       tool có trong cấu hình đã duyệt? tòa nhà có trong phạm vi BQL phụ trách?
  → Tool host của Team Quang (kiểm tra tham số, phạm vi tòa nhà, ghi sổ kiểm toán)
  → trả phong bì kết quả cho model
```

- **Ai quyết định quyền:** dịch vụ tool, từ dòng `agent_runs` mà backend đã mở cho lượt nói. Supervisor không
  giữ quyền nào; token dịch vụ chỉ chứng minh bên gọi là runtime.
- **Danh tính:** không có người dùng và không có vai trò. Tài liệu chỉ đọc được khi được cấp cho workspace của
  BQL; các tool dành cho vai trò quản lý vẫn đóng.
- **Phạm vi:** các scope mà đơn vị quản lý của workspace đang phụ trách (`management_coverage`).
- **Thu hồi:** thu hồi bản phát hành thì lần gọi tool kế tiếp bị từ chối.
- **Dịch vụ tool không trả lời:** agent được báo tool không khả dụng và ghi "chưa tra được". Phiên không bị treo,
  vì tool đọc không làm thay đổi gì.
- **Sổ kiểm toán:** mỗi lần gọi một dòng `vh_technical_api_audit` (tool, kết quả, mã lượt chạy, tòa nhà).

### Thành phần

| Phần | Vị trí | Ghi chú |
|---|---|---|
| Nhận diện lượt chạy của phiên | `server/src/technical-api/session.ts` | Dùng lại API kỹ thuật có sẵn (transaction, role giới hạn, kiểm toán, biên nhận) |
| Route và dịch vụ | `server/src/technical-api/session-routes.ts`, `serve.ts` | `GET /internal/technical/v1/tools`, `POST /internal/technical/v1/call` |
| Quyền database | `server/scripts/grant_technical_api_role.sql` | Thêm SELECT trên `agent_runs`, `team_members`, `agent_teams`, `agent_releases`, `workspaces`, `management_coverage` |
| Cài đặt | `services/vinhomes-api/scripts/setup_session_tools.py` | Tạo role chỉ đọc và chèn, đăng ký 14 tool vào `mcp_servers`/`mcp_tools`, ghi `technical-api.env` |
| Khởi động | `services/vinhomes-api/scripts/start_technical_tools.ps1 [-Connected]` | Cổng 8788 |
| Backend | `GET /internal/coordination/v1/teams/{id}/members/{member}/release` | Trả `tool_descriptors` của các tool đọc đã cấp, lấy từ catalogue |
| Supervisor | `agent-coordination/src/vinhomes/ports.py` (`ToolGateway`) | Bật khi có `COORDINATION_TOOLS_URL` và `COORDINATION_TOOLS_TOKEN` |
| Phát hành agent | `agent-coordination/src/vinhomes/publish.py` | Cấp tool theo `tools` trong định nghĩa; ca đánh giá có `tool_results`, `must_call`, `must_not_call` |

### Chạy

```powershell
python services\vinhomes-api\scripts\setup_session_tools.py [--connected]   # một lần cho mỗi database
services\vinhomes-api\scripts\start_technical_tools.ps1 [-Connected]        # dịch vụ tool, cổng 8788
agent-coordination\scripts\start_vinhomes.ps1 [-Connected]                  # tự nhận cấu hình tool
agent-coordination\scripts\publish_agent.ps1 docs\teams\quang\agent\technical-agent.json -Room <phòng> [-Connected] -Approve
```

Database được khôi phục từ bản sao cũ thì phải chạy lại `setup_session_tools.py` và phát hành lại agent.

### Đã kiểm

| Việc | Kết quả |
|---|---|
| Backend | 64 đạt, 6 bỏ qua |
| `agent-coordination` | 428 đạt (21 của gói `vinhomes`; mới: gọi tool rồi trả lời, dịch vụ tool không trả lời, tool không được cấp, hỏi thêm trong phiên, câu hỏi cho phiên chưa có phòng) |
| `server`: `technical-session.routes`, `technical-api.routes`, `technical-tools` | 893 đạt; kiểm tra kiểu 0 lỗi |
| Chạy thật, database dùng-rồi-bỏ | Agent gọi `sop_kb.retrieve`, dịch vụ tool chấp nhận theo lượt chạy, có dòng kiểm toán |
| Trình duyệt, tài khoản thật | 8/8 bước tới khi BQL thấy phân tích có kết quả tra cứu |

Chưa kiểm bằng test tự động: câu truy vấn nhận diện lượt chạy (`session.ts`) chỉ được kiểm qua các lần chạy thật.

### Điều cần biết

1. **Độ ổn định của agent có tool.** Bộ đánh giá có 10 ca (nay là 11, thêm ca câu hỏi tiếp theo; hai lần chạy
   bộ 11 ca đều đạt đủ). Qua 7 lần chạy thật, 4 lần đạt 10/10 và 3 lần hỏng
   đúng một ca (mỗi lần một ca khác: không gọi SOP khi bắt buộc, hoặc diễn đạt khác mẫu). Agent chỉ được nộp
   duyệt ở lần đạt đủ. Nguyên nhân là model nhỏ không theo quy trình một cách tuyệt đối; `agent-bot` không cho
   đặt temperature. Đề xuất: dùng model mạnh hơn cho agent chuyên môn, hoặc cho `agent-bot` nhận temperature.
2. **Dữ liệu.** Database local chưa có SOP và chưa có gián đoạn nào, nên tool trả "không có" hoặc `NOT_FOUND`
   và agent ghi đúng như vậy. Cần Team Quang nạp SOP (`vh_technical_sop_profiles` và tài liệu tri thức được cấp
   cho workspace của BQL).
3. **Phiên bản agent.** Agent đã duyệt không sửa được cấu hình, nên bản có tool là một agent mới cùng tên; công
   cụ phát hành thu hồi agent cũ sau khi duyệt bản mới. Chưa có luồng "phiên bản 2 của cùng một agent".

## Phần 2 — Khảo sát các nhánh (gộp thử lên nền `dev_TeamChien`)

| Nhánh | Thêm gì | Gộp thử | Test | Nhận định |
|---|---|---|---|---|
| `devTeamDong/dev3` (PR #24 vào `dev_TeamDong`) | 23 file adapter: xác thực nguồn HMAC, cổng nhận từ Lễ tân, client quyền, cấp quyền tool phía Coordination | Sạch | 423 test cũ đạt; 4 file test mới không nạp được (`No module named 'backend'`) | Là phía gọi của các contract mà backend chưa có (`tool.grant.verify`, events). Dùng được khi backend đẩy sự kiện cho Supervisor (M3). Cần Team Đông sửa đường import test |
| `dev_TeamDong_checkpointing` (PR #10) | `persistence/checkpoint.py`, `resume.py`, `recovery.py`, `retry.py` và thư mục `agent-vinhomes/` | Xung đột ở 5 file `__init__.py` | Chưa chạy | Thiết kế cũ hơn `persistence/sqlite.py` đang có trên `develop`; cần Team Đông quyết giữ bản nào trước khi làm kho PostgreSQL |
| `devTeamDong/dev5` (PR #22) | `main.py`, `config.py`, test ghép với dữ liệu giả, trên nền cũ | Xung đột ở 8 file | Chưa chạy | Đã bị thay bởi `main.py` và composition trên `develop` |
| `devTeamDong/tiendo-ml-engineer` (PR #9) | `agent-runtime/src/dispatcher`: phân loại ticket và chọn agent bằng luật và model ML (2 file `.joblib`) | Sạch | Chưa chạy (cần cài thư viện ML) | Gói riêng, Supervisor hiện không dùng. Có thể thành nguồn gợi ý danh mục khi Lễ tân không gán được |
| `dev_TeamQuang_ddhung04` | 23 tài liệu dữ liệu kỹ thuật: danh mục sự cố, ca biên, ma trận kiểm tra, luồng mẫu | Sạch | Không có mã | Nên gộp. Là nguồn để thay 10 ca đánh giá của agent kỹ thuật và để nạp SOP |
| `codex/report-agent-PHH` | 8 tool báo cáo (Python) gọi `/reports/*`, 6 file test | Sạch | Chưa chạy | Gộp được; cần cổng tool tương tự cho agent báo cáo |
| `devTeamPhai` | Agent Factory, 22 tool an ninh | 2 xung đột, đã xử lý | Xem PR #32 | Đã đưa lên `develop` mới ở nhánh `integration/devTeamPhai-on-develop`, PR nháp #32 |

Các nhánh chính của Team Đông, Quang, Hoàng (`dev_TeamDong`, `dev_TeamQuang`, `dev_TeamHoang`) không còn gì ngoài
`develop`.

### Nhánh Team Phái (PR #32)

- Đạt trên cây đã gộp: kiểm tra kiểu `server` 0 lỗi; tool an ninh 289 test; tool kỹ thuật 882; tri thức 63.
- Chưa đạt: `agent-factory-routes` 18 hỏng và `agent-factory.integration` 1 hỏng vì plugin store của OpenBot chèn
  vào `mcp_servers` không có `tenant_id` (schema của `develop` bắt buộc; lỗi cùng loại đã có trên `develop`);
  `agent-factory-ui` 11 hỏng vì test tìm nhãn tiếng Anh trên giao diện đã chuyển tiếng Việt.
- Phải ghim `jose` về `6.2.10` để `server` qua kiểm tra kiểu.
- Tool an ninh chạy với dữ liệu giả; bản thật cần backend có `security/v0.3/query` và token ký bằng JWKS.

## Phần 3 — Hỏi thêm agent trong phiên, và danh sách phiên theo phòng

Ban quản lý mở ticket trên Operations, đọc phân tích của agent, rồi hỏi thêm ngay trong khung "Phiên điều phối".
Agent trả lời trong chính phòng của phiên đó, thấy ticket và câu trả lời trước của mình. Đã chạy thật trên bản
đăng nhập thật: hỏi, khoảng 10 giây sau câu trả lời hiện trong khung phiên.

| Thao tác | API | Ghi chú |
|---|---|---|
| BQL hỏi agent | `POST /tickets/{id}/session/questions` (`text`, `client_message_id`, `agent_id` khi phiên có nhiều agent) | Cần quyền quản lý trên ticket; mỗi phiên một câu hỏi đang chờ; gửi lại cùng `client_message_id` không tạo câu thứ hai |
| Runtime lấy câu hỏi | `GET /internal/coordination/v1/mentions` | Chỉ câu đang chờ; câu của phiên không còn hiện hành bị đánh dấu từ chối |
| Runtime báo kết quả | `POST /internal/coordination/v1/teams/{id}/mentions/{message_id}` (`done` hoặc `failed`) | Gọi lại được; chỉ câu đang chờ mới đổi |
| Phiên của phòng | `GET /rooms/{room}/teams` | Thêm mã ticket, tiêu đề và trạng thái Supervisor báo |

- Câu hỏi là một lượt nói riêng của agent trong phòng (lệnh `mention_agent` của Team Đông), có lượt chạy riêng ở
  backend. Phiên của Supervisor không bị đánh thức và không tốn quyết định nào của model Supervisor.
- Kết quả được ghi lại ở runtime trước khi báo cho backend, nên báo hỏng thì lần sau báo lại, không hỏi agent lần hai.
- Agent đã bị thu hồi thì không trả lời được; câu hỏi hiện là "agent không trả lời được".
- Màn "Nhóm ban quản lý" liệt kê các phiên của phòng với mã ticket và trạng thái.

Chưa làm trong mục này: tạm dừng, chạy tiếp và dừng phiên. Hiện Supervisor luôn dừng sau khi có phân tích, nên
"chạy tiếp" chỉ có nghĩa khi có luồng phương án (mục 2 dưới đây). Lời gọi `@agent` gõ tự do trong phòng chung (không
gắn ticket) vẫn chỉ được xếp hàng.

## Phần 4 — Admin duyệt và thu hồi agent trên Operations

Trang "Tài khoản" của admin có thêm hai khối: **Agent chờ duyệt** (mô tả, danh mục phục vụ, tool được cấp, chỉ
dẫn, kết quả từng ca đánh giá; duyệt hoặc từ chối kèm ghi chú) và **Agent đã phát hành** (thu hồi kèm lý do).
Duyệt là phát hành. API: `GET /admin/agent-reviews`, `POST /admin/agent-reviews/{id}/decision`,
`GET /admin/agent-releases` (mới), `POST /admin/agents/{id}/release/revoke`.

Theo quyết định của điều phối, tạo nháp và chạy đánh giá vẫn dùng `publish_agent.ps1` cho tới khi nối Agent
Factory. Agent chuyên môn chạy `gpt-5.5` (`COORDINATION_OPENBOT_MODEL`), Supervisor giữ `gpt-5.4-mini`. Với
`gpt-5.5`, bộ 11 ca chạy ba lần: hai lần đạt đủ, một lần hỏng một ca vì cách diễn đạt; ca đó chạy riêng 6/6 đạt.

## Việc tiếp theo

1. Luồng phiên bản 2 của cùng một agent; BQL tự tạo và cấu hình agent trên màn hình; nối Agent Factory.
2. Phương án, hỏi lại cư dân, hai lần duyệt (cần backend cấp `ticket_version` mới cho mỗi yêu cầu chờ); kèm tạm
   dừng, chạy tiếp, dừng phiên.
3. Mở tool ghi cho phiên: đối soát kết quả chưa rõ theo mã lần gọi.
4. Agent an ninh và bộ chuyển cho tool an ninh; tool báo cáo.
5. Triển khai: Dockerfile và compose cho các dịch vụ của ta, kho PostgreSQL cho Supervisor. CI để sau, theo
   quyết định của điều phối.
