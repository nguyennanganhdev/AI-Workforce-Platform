# Thành viên làm việc thẳng với nhau, không qua Leader

Ngày 19/10/2026. Nhánh `feat/peer-collab-20261019`, tách từ `develop2@6072fcce`,
đã merge `develop2@28aaf71f` (PR #111). Code: `60cf5481`; bản deploy: `ad34f87a`.

## Vấn đề

Trong phòng của phiếu và kênh, các agent chỉ trao đổi ngang bằng câu hỏi rồi
câu trả lời. Mọi kết quả phải về Leader:

- Worker không có loại tin "handoff"; trường người nhận chỉ dùng cho câu hỏi.
- Kết quả không ghi người nhận tự đi về Leader.
- Kết quả có người nhận vẫn được gửi thêm một bản cho Leader, làm Leader tốn
  thêm một lượt model.
- Chế độ peer chỉ bật cho chat của người dùng trên web.

## Thay đổi

**Chế độ collaborative cho phiếu và kênh.** Team mới của phiếu đối tác và của
kênh có cờ `TeamData.direct_member_routing=true`. Thành viên làm việc thẳng với
nhau; Leader vẫn là người duy nhất trả lời khách. Không bật peer đầy đủ cho
phiếu, vì phiếu bắt buộc Leader gửi một tin CaseSay kèm mã E.

**Worker có loại "handoff".** Worker chuyển một phần việc cho một đồng đội rồi
ngủ chờ. Đồng đội gửi kết quả không ghi người nhận thì kết quả về người đã
chuyển việc. Không được handoff cho Leader. Phần việc được chuyển hiện trong
ledger của phòng, có tên đồng đội nhận.

**Worker được ghi người nhận khi gửi kết quả.** Chỉ người nhận đó nhận.

**Leader không nhận bản sao** khi kết quả hoặc câu trả lời đã có đồng đội là
người nhận. Leader vẫn tính thành viên đó đã xong khi chờ báo cáo.

**Lỗi luôn đến Leader.** Runtime chỉ dừng nhánh việc lỗi khi lỗi đã giao cho
Leader; bỏ bước này thì Leader chờ đến hết giờ.

**Worker có hai việc phải ghi người nhận.** Worker vừa có việc Leader giao,
vừa nhận phần việc đồng đội chuyển, phải ghi `to` khi gửi kết quả để runtime
biết kết quả trả cho việc nào.

**Công tắc quay lui.** `WORKFORCE_TEAM_COLLABORATION=reviewed` rồi khởi động lại
app: mọi team collaborative, kể cả team đã tạo, quay về định tuyến cũ. Team của
chat cá nhân (peer) không đổi.

**Quay lui ảnh an toàn.** Dùng cờ riêng thay vì thêm giá trị thứ ba cho
`collaboration_mode`. Bản cũ chỉ chấp nhận `reviewed`/`peer`; giá trị mới sẽ làm
bản cũ không đọc được team. Bản cũ bỏ qua cờ và trường `assigned_by` của ledger.

## Không đổi

- Team tạo trước bản này và nhóm BQL vẫn theo định tuyến cũ.
- Phiên thử của Leader vẫn chạy peer, khác với phiếu thật.
- Giao diện không đổi: tin "handoff" của worker hiện với nhãn "Giao việc".

## File

| File | Nội dung |
| --- | --- |
| `storage/_model/_team.py` | Cờ `direct_member_routing`, công tắc quay lui |
| `storage/_model/_team_context.py` | `TaskAssignment.assigned_by` |
| `_tool/_team_say.py` | Handoff, kết quả về người chuyển việc, bỏ bản sao cho Leader |
| `_shared_context.py` | Handoff là phụ thuộc như câu hỏi; ledger; đếm kết quả gửi đồng đội |
| `_service/_chat.py`, `_service/_toolkit.py` | Bật mô tả và lời nhắc cho worker khi team cho phép |
| `_tool/_team_create.py`, `unified/_runner.py` | Team mới của kênh và phiếu bật cờ |
| `unified/_case.py` | Policy thành viên phòng: báo cho người đã giao việc |
| `compose.yaml`, `.env.example` | Truyền `WORKFORCE_TEAM_COLLABORATION` |
| `tests/team_direct_collaboration_test.py` | 16 test mới |

## Kiểm thử

Chỉ dùng storage và model giả lập; không gọi model thật.

| Bộ test | develop2 | Nhánh |
| --- | --- | --- |
| Team, chat, toolkit, shared context liên quan | 355 đạt, 2 lỗi | 371 đạt, 2 lỗi |
| `tests/workforce/integrations` | 105 đạt | 105 đạt |
| `tests/workforce/console` | 265 đạt, 28 bỏ qua | 265 đạt, 28 bỏ qua |
| `tests/workforce/orchestration` | 269 đạt | 269 đạt |

Hai lỗi có sẵn trên develop2: `service_chat_locking_test` (waiter) và
`workspace_daytona_test` (gỡ rồi thêm lại MCP). Sau khi merge PR #111, 223 test
team và invite đều đạt. Ruff không có cảnh báo mới.

Chưa chạy: phòng phiếu end-to-end trên Docker (`offline_partner_e2e/drive_room.py`)
và phiên với model thật.

## Deploy 19/10/2026

Chỉ deploy app, dạng overlay chép đè 9 file lên ảnh đang chạy. Web giữ nguyên.

| Mục | Giá trị |
| --- | --- |
| App trước | `agentscope-platform:28aaf71f-invitefix-20261019` |
| App sau | `agentscope-platform:ad34f87a-peercollab-20261019` |
| Web | `agentscope-platform-web:28aaf71f-invitefix-20261019` (không đổi) |
| Thư mục release | `/opt/awp-platform/releases/peercollab-ad34f87a-20261019` |
| Sao lưu | `/var/backups/awp-platform/peercollab-ad34f87a-20261019` (675 MB) |
| Tag quay lui | `awp-rollback/app:before-peercollab-20261019` |

Script kiểm tra trước khi đổi: app đang chạy đúng ảnh nền, 9 file trong ảnh nền
trùng nội dung commit nền (bỏ qua CRLF), file trong ảnh mới trùng overlay.
Lần chạy đầu dừng ở bước này vì trong lúc chuẩn bị đã có người deploy
`28aaf71f-invitefix`; nhánh được merge develop2 rồi đóng gói lại.

Sau deploy: app healthy; `/`, `/login`, `/workforce/leader`, `/api/health` trả
200 qua domain; app nhận `WORKFORCE_TEAM_COLLABORATION=collaborative`; không có
lỗi trong log 30 phút đầu. `compose.yaml` trên VPS có thêm dòng truyền biến này.

## Quay lui

Tắt định tuyến thẳng, giữ ảnh mới:

```bash
cd /opt/awp-platform/app
echo WORKFORCE_TEAM_COLLABORATION=reviewed >> .env
docker compose -p awp-platform --env-file .env -f compose.yaml -f compose.vps.yaml up -d --no-deps app
```

Quay lại ảnh trước:

```bash
cd /opt/awp-platform/releases/peercollab-ad34f87a-20261019
cp private/env.before /opt/awp-platform/app/.env
cp private/compose.yaml.before /opt/awp-platform/app/compose.yaml
docker compose -p awp-platform --env-file /opt/awp-platform/app/.env   -f /opt/awp-platform/app/compose.yaml -f /opt/awp-platform/app/compose.vps.yaml   up -d --no-build --no-deps --pull never app
```

Ảnh trước đọc được team tạo sau deploy: cờ `direct_member_routing` và trường
`assigned_by` bị bỏ qua, team chạy như `reviewed`.

## Cách thử trên giao diện

1. Mở một phiếu mới hoặc nhắn vào kênh để Leader lập phòng mới.
2. Chọn yêu cầu cần hai thành viên, một người dùng kết quả của người kia.
3. Trong dòng thời gian của phòng, xem tin "Giao việc" hoặc kết quả đi thẳng
   giữa hai thành viên, không qua Leader.
4. Leader vẫn gửi khách đúng một câu trả lời cuối.
