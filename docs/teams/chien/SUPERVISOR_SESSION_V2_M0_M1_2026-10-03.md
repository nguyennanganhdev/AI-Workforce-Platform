# Supervisor, groupchat và session V2 — kết quả M0 và lát cắt đầu của M1

Ngày 03/10/2026. Nhánh làm việc: `dev_teamChien_HuyDo`. Kế hoạch gốc:
`KE_HOACH_SUPERVISOR_GROUPCHAT_SESSION_V2_2026-10-03.md` (các "bước" và "mốc" dưới đây là của kế hoạch đó).

## Đã làm tới đâu

| Bước trong kế hoạch | Trạng thái | Ghi chú |
|---|---|---|
| 0. Baseline, test, vùng sở hữu | Xong | Mục "Baseline" |
| 1. Session và contract | Xong cho luồng Reception V2; phần sự kiện backend và phòng chưa chốt | Mục "Session" và "Bảng contract" |
| 2. Persistence | Một phần | Dùng kho phát triển của Team Đông (file SQLite); chưa có kho PostgreSQL |
| 3. Adapter thật và runtime tối thiểu | Xong cho `ticket_submitted → accepted` | Mục "Runtime" |
| 4. Supervisor và specialist chạy model thật | Chưa | Chưa có specialist nào được xuất bản; chưa gọi model |
| 5. Luồng V2 trọn vòng | Mới bước 5.1 | Hỏi lại, phương án, duyệt, hoàn tất, hủy: chưa |
| 6. Quản lý session trên platform | Một phần | Operations hiện thời điểm Supervisor tiếp nhận và lý do tạm dừng; chưa có pause/resume/stop |
| 7. Nghiệm thu lỗi, triển khai giới hạn | Một phần | Mục "Ma trận nghiệm thu" |

Kết quả chạy được: cư dân báo sự cố qua chat, Lễ tân tạo yêu cầu và bàn giao; Supervisor thật (lõi của Team
Đông) nhận yêu cầu qua backend, tạo phiên có lưu bền, trả `accepted`; vì phòng chưa có agent chuyên môn nên nó
dừng với lý do rõ ràng và Ban quản lý xử lý tiếp như hiện nay. Chưa có bước nào do model quyết định.

## Baseline (bước 0)

- Commit gốc khi bắt đầu: `137fd18` (`develop` sau khi gộp PR #25). Python 3.12.13, AgentScope 2.0.9.
- Test `agent-coordination` trước khi sửa: 386 đạt, 8 hỏng. Tám test hỏng không thuộc phạm vi này:
  6 test so schema đã công bố với model (`tests/groupchat/test_contracts.py`), 1 test đọc file
  `docs/teams/dong/workflow-proposals/contribution.schema.json` không có trong repo, 1 test hardening.
  Trên Windows phải đặt `PYTHONUTF8=1`, nếu không bộ test lỗi ngay lúc nạp vì đọc file UTF-8 bằng cp1252.
- Sau khi thêm 11 test của gói `vinhomes`: 397 đạt, vẫn 8 test hỏng đó.
- Backend: 58 → 61 đạt. Đầu-cuối với model giả: 9/9 ở cả hai chế độ Lễ tân, có dịch vụ Supervisor chạy cùng.

Kiểm kê trước khi viết mới:

| Thành phần | Đã có, dùng lại | Thiếu (bằng chứng) | Đã thêm |
|---|---|---|---|
| Lõi Supervisor, planner, reception flow | `agent-coordination/src/supervisor/` | — | Không sửa |
| Kho trạng thái, inbox, lease | `persistence/sqlite.py` (chỉ cho phát triển) | Kho production: không có implementation | Thêm bảng con trỏ inbox trong lớp con |
| Trao đổi V2 ở backend | `v3_reception_supervisor.py`: lưu message, inbox, kết quả, pending | Chỉ nhận người dùng đã đăng nhập; `created_by` bắt buộc là người | `v3_coordination.py`, migration 0012 |
| Danh tính dịch vụ cho nhóm agent | Bảng `execution_principals`, `runtime_session_bindings` (loại `team`) | Không có mã nào cấp binding/run cho Supervisor | `session_context` trong `v3_coordination.py` |
| Composition | `runtime/composition.py` cần 17 ràng buộc do "Platform" cấp | Không có factory nào; `/ready` luôn 503 | Gói `src/vinhomes` (composition riêng, kéo inbox) |
| Phòng, specialist, model | `groupchat/`, `adapters/agentscope_adapter.py`, `runtime/model.py` | Chưa có agent nào được xuất bản; `server/src/platform` trống | Chưa nối; các cổng từ chối rõ ràng |

## Session (bước 1)

- Một session cho mỗi `(tenant, ticket, generation)`: một dòng `agent_teams`, tạo lúc Lễ tân bàn giao. Phòng là
  phòng Ban quản lý của đơn vị quản lý phụ trách; một phòng chứa nhiều session.
- Khi runtime xác minh message đầu tiên, backend cấp cho session: một `runtime_session_bindings` (loại `team`,
  gắn với thành viên Supervisor của nhóm, khóa `coordination:<team id>`) và một `agent_runs`
  (`supervisor-session:<team id>`). `binding_id` và `run_id` trong `Context` của runtime là hai dòng này và giữ
  nguyên suốt session.
- Phiên bản Supervisor được ghim từ `team_members.version_id` của backend, không lấy bản mới nhất.
- Session nội bộ kết thúc không đóng ticket: trạng thái `completed` của `agent_teams` chỉ do Ban quản lý duyệt đóng.
- Ticket mở lại (generation mới): nhóm cũ bị từ chối ở mọi lời gọi (409).

Trạng thái `agent_teams.status` theo kết quả V2: `accepted`, `in_progress` → `running`; `information_requested`,
`plan_approval_requested` → `waiting`; `failed` → `failed`; `cancelled` → `cancelled`.

## Bảng contract: runtime ↔ backend (`/internal/coordination/v1`)

Mọi lời gọi mang `Authorization: Bearer <VINHOMES_API_COORDINATION_SERVICE_TOKEN>`. Token chỉ chứng minh bên gọi là
runtime. Mỗi lời gọi nêu một team và backend kiểm lại: workspace còn hoạt động và có danh tính dịch vụ, agent
Supervisor còn hoạt động và là thành viên của nhóm, ticket còn đúng generation.

| Thao tác | API | Vào → ra | Từ chối | Chống lặp | Đối soát |
|---|---|---|---|---|---|
| Đọc hàng chờ | `GET /inbox?cursor` | → message V2 theo thứ tự, `next_cursor` | 401, 503 | Runtime chép vào inbox riêng theo `(tenant, message_id)` | Đọc không phải là đã xử lý; con trỏ lưu bền |
| Xác minh | `POST /reception/verify` | `team_id`, `message_id` → message đã lưu, `context`, `supervisor_run_id` | 403 nhóm không hợp lệ, 404 không có message, 409 nhóm đã xong hoặc sai generation | Cùng nhóm luôn trả cùng binding và run | Runtime so message nhận với bản đã lưu, lệch thì giữ lại cho người xử lý |
| Gửi kết quả | `POST /reception/send` | message V2 → `message_id`, `status`, `replayed` | 409 sai phiên bản, đang có yêu cầu chờ cư dân, ticket đã kết thúc | Cùng id cùng nội dung → `replayed`; cùng id khác nội dung → 409 | `GET /teams/{id}/results/{message_id}` |
| Khung nhìn | `GET /teams/{id}/view` | → `context`, phiên bản ticket, trạng thái, yêu cầu đang chờ, specialist đã xuất bản | 403, 409 | Chỉ đọc | — |
| Xin phép trước khi gửi | `POST /teams/{id}/authorize` | `action_id`, `channel`, `operation` → `authorized` | 409 nhóm đã xong; 409 với kênh `room`, `backend`, `draft` (chưa có contract) | Chỉ đọc | — |
| Báo trạng thái | `POST /teams/{id}/status` | `phase`, `pause_reason`, `state_version` | 403, 409 | Ghi đè, không đổi phiên bản session | — |

Kết quả V2 từ runtime được kiểm bằng đúng hàm kiểm của kết quả do người vận hành gửi (`accept_supervisor_result`).
`accepted` và `in_progress` chỉ ghi vào phòng Ban quản lý; `information_requested`, `plan_approval_requested`,
`completed`, `failed`, `cancelled` còn được Lễ tân chuyển vào hội thoại của cư dân.

## Runtime (bước 3)

- Gói `agent-coordination/src/vinhomes`: `backend.py` (client HTTP, phân biệt từ chối với kết quả chưa rõ),
  `ports.py` (ReceptionPort, Authority, và các cổng chưa có contract), `runtime.py` (kéo inbox, worker, dịch vụ).
- Chạy: `agent-coordination/scripts/start_vinhomes.ps1` (thêm `-Connected` khi backend chạy đăng nhập thật).
  Cổng 4300: `/health`, `/ready`, `/sessions` (mỗi session một dòng: mã ticket, pha, lý do dừng; không có nội
  dung của cư dân).
- Backend cần `VINHOMES_API_COORDINATION_SERVICE_TOKEN` (đặt trong `.local-v3-faker/coordination.env` hoặc
  `.local-connected/coordination.env`); runtime cần `COORDINATION_BACKEND_URL` và `COORDINATION_SERVICE_TOKEN`
  trong `agent-coordination/.env`. Hai token phải giống nhau và khác token của Lễ tân.
- Xử lý lỗi: backend không tới được → thử lại cùng message, không giới hạn số lần; backend từ chối hoặc message
  không khớp → giữ lại (`blocked`) cho người xử lý, không bỏ; kết quả gửi đi chưa rõ → tra theo `message_id`,
  có thì ghi nhận, chưa có thì gửi lại đúng nội dung cũ.

## Ma trận nghiệm thu (mục 8 của kế hoạch)

| Tình huống | Đã kiểm | Bằng test nào |
|---|---|---|
| Luồng bình thường | Chỉ `ticket_submitted → accepted` | `test_the_supervisor_receives_the_ticket_reception_handed_over` (đầu-cuối) |
| Cùng message gửi lại | Có | `test_a_message_read_again_or_after_a_restart_is_handled_once` |
| Cùng ID khác nội dung | Có | `test_the_supervisor_receives_a_ticket_and_accepts_it` (409) |
| Backend đã commit nhưng mất ACK | Có | `test_a_lost_reply_is_reconciled_by_message_id[stored]` |
| Mất yêu cầu trước khi tới backend | Có | `test_a_lost_reply_is_reconciled_by_message_id[dropped]` |
| Restart | Có, ở mức mở lại file trạng thái | `test_a_message_read_again_or_after_a_restart_is_handled_once` |
| Sai generation | Có | `test_a_supervisor_question_reaches_the_resident_and_a_stale_team_is_refused` |
| Thu hồi quyền giữa phiên | Có | `test_a_team_that_lost_its_authority_sends_nothing` |
| Hai session không lẫn nhau | Có | `test_two_tickets_are_two_sessions` |
| Hai worker cùng xử lý | Chưa | Lease và CAS của kho đã có test của Team Đông; chưa chạy hai tiến trình với composition này |
| Quyết định trùng, phản hồi phương án cũ, restart khi chờ duyệt, hủy, QC, reopen sang session mới, rollback | Chưa | Cần luồng phương án và duyệt (bước 5) |
| Model lỗi, lặp, vượt giới hạn | Chưa | Chưa gọi model (bước 4) |

## Cần làm rõ

1. **Bản schema V2 của lead.** Kế hoạch dẫn tới file trên máy khác; tôi chỉ có `docs/SCHEMA_RECEPTION_SUPERVISOR_V1.md`
   trong repo và validator của backend. Cần file của lead để so và ghi khác biệt.
2. **Kho trạng thái production.** Kho hiện tại là file SQLite trên một máy. Đề xuất: schema `coordination` riêng
   trong PostgreSQL, role riêng, cùng giao diện với kho hiện có. Cần chốt trước khi chạy nhiều bản.
3. **Specialist đầu tiên.** Phòng chưa có agent chuyên môn nào được xuất bản và Agent Factory chưa nối backend.
   Đề xuất cho bước 4: một specialist điện nước không dùng tool, chạy trong tiến trình; phiên bản ghi vào
   `agent_versions` và `agent_releases` bằng script cho tới khi Agent Factory nối.
4. **Model.** Tài liệu Team Đông yêu cầu `gpt-5.6-luna`; Lễ tân đang dùng `gpt-5.4-mini`. Cần chốt model, nguồn
   khóa và ngân sách cho Supervisor.
5. **Tác giả của phương án.** `vh_ticket_plans.proposed_by` bắt buộc là người dùng có vai trò quản lý. Supervisor
   đề xuất phương án thì ghi tác giả là agent (như đã làm với kết quả V2) hay dùng bảng riêng?
6. **Sự kiện từ backend tới Supervisor** (Ban quản lý duyệt, phân công, hoàn thành). Thiết kế của Team Đông là
   backend đẩy vào `/v2/events`; lát cắt này dùng kéo vì backend đã có inbox bền. Đề xuất dùng cùng cách kéo.
7. **Màn quản lý session.** Quản lý theo ticket (như hiện nay) hay theo phòng? Đề xuất: theo ticket, lọc theo phòng.
8. **Rà mã.** Gói `src/vinhomes` nằm trong thư mục của Team Đông nhưng không sửa lõi của họ; cần họ rà.

## Việc tiếp theo

1. Kho PostgreSQL cho checkpoint, inbox, journal (bước 2), kèm test hai tiến trình và kill giữa chừng.
2. Một specialist và model thật (bước 4): `ParticipantResolver`, loader phiên bản đã ghim, cổng gọi agent.
3. Hỏi lại cư dân (`information_requested` ↔ `information_provided`): backend lưu câu hỏi của Supervisor và
   Lễ tân gửi `information_provided` khi cư dân trả lời.
4. Phương án và hai lần duyệt (bước 5.3–5.5), rồi theo dõi công việc và hoàn tất.
5. Pause, resume, stop trên Operations (bước 6).
