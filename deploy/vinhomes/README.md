# Triển khai các dịch vụ Vinhomes bằng Docker Compose (một máy)

Người đọc: người dựng hoặc vận hành stack trên một máy chủ. Đã chạy thử ngày 04/10/2026 trên Docker Desktop
(Windows) với bản sao cơ sở dữ liệu đăng nhập thật; chưa phải nghiệm thu production.

## Stack gồm gì

| Dịch vụ | Việc | Cổng trong mạng compose |
|---|---|---|
| `api` | API nghiệp vụ, đăng nhập bằng mật khẩu, cổng tool cho agent | 8000 (cổng duy nhất mở ra máy chủ) |
| `reception` | Agent Lễ tân | 4202 |
| `coordination` | Supervisor và phòng nhóm; checkpoint nằm trong PostgreSQL riêng | 4300 |
| `openbot` | Nơi agent chuyên môn chạy | 4200, chỉ loopback |
| `agents-net` | Giữ không gian mạng chung của `coordination` và `openbot` | không có |
| `knowledge` | Tra cứu tri thức cho Lễ tân | 8787 |
| `technical-tools` | Tool đọc kỹ thuật | 8788 |
| `factory` | Agent Factory | 4010 |

Không nằm trong stack: PostgreSQL (dùng cơ sở dữ liệu đã migrate, có sẵn role giới hạn quyền), hai giao diện
(Operations và ứng dụng cư dân), và đăng nhập thống nhất với tài khoản OpenBot.

`coordination` và `openbot` dùng chung một không gian mạng. Lõi Supervisor chỉ gửi token của agent tới OpenBot qua
HTTPS hoặc loopback, nên hai dịch vụ gặp nhau trên loopback và không dịch vụ nào khác gọi được OpenBot.
`agents-net` chỉ giữ không gian mạng đó: nhờ vậy mỗi dịch vụ khởi động lại riêng vẫn quay về đúng chỗ.

## Chuẩn bị

1. PostgreSQL 17 có pgvector, đã chạy `server/scripts/migrate.ts` tới migration mới nhất và cấp quyền bằng
   `services/vinhomes-api/scripts/grant_v3_api_role.sql`, `server/scripts/grant_technical_api_role.sql`.
2. Một cơ sở dữ liệu riêng cho checkpoint của Supervisor, chủ sở hữu là role không phải superuser. Bảng được tạo
   khi `coordination` khởi động lần đầu.
3. Kho tri thức đã phát hành (`KNOWLEDGE_BASE_ID`) và ít nhất một agent chuyên môn đã phát hành trong phòng BQL.
4. Sao `deployment.env.example` thành `deployment.env` (được git bỏ qua) và điền. Mỗi token là một giá trị ngẫu
   nhiên riêng, tối thiểu 32 ký tự: `python -c "import secrets; print(secrets.token_hex(32))"`. Trong URL kết nối,
   máy chủ cơ sở dữ liệu phải là địa chỉ container nhìn thấy được (không phải `127.0.0.1`).
5. `VINHOMES_ALLOWED_ORIGINS` là danh sách origin của hai giao diện. Thiếu origin thì đăng nhập bị từ chối với
   "Untrusted browser origin".

## Chạy

```powershell
cd deploy/vinhomes
docker compose --env-file deployment.env build
docker compose --env-file deployment.env up -d
docker compose --env-file deployment.env ps
```

Bảy dịch vụ phải ở trạng thái `healthy` (`agents-net` không có kiểm tra sức khỏe). Lần chạy thử, cả stack sẵn sàng
sau khoảng 30 giây.

Giao diện Operations bản build: `cd app; bun run build`, rồi chạy `bun serve.ts` với `VINHOMES_API_URL` trỏ tới
`api`. Đường `/api/business` được chuyển tiếp kèm cookie đăng nhập.

## Kiểm tra sau khi chạy

1. `GET /ready` của `api` trả 200; gọi `/operations/me` khi chưa đăng nhập trả 401.
2. Đăng nhập bằng một tài khoản BQL thật, `/operations/me` trả đúng vai trò.
3. Cư dân gửi một yêu cầu trong chat: Lễ tân trả mã ticket, phiên của ticket có agent tham gia và tới
   `waiting_management` kèm phương án.
4. BQL duyệt phương án: cư dân nhận câu hỏi đồng ý phương án trong hội thoại.
5. Cư dân hỏi một câu về quy định: câu trả lời có dòng nguồn.

## Khôi phục và quay lui

- Khởi động lại `coordination` hoặc `openbot` riêng lẻ không làm mất phiên: checkpoint nằm trong PostgreSQL.
  Quyết định BQL đưa ra trong lúc Supervisor dừng được xử lý khi nó chạy lại.
- Nếu `coordination` báo `unhealthy` sau khi máy chủ hoặc Docker khởi động lại:
  `docker compose --env-file deployment.env up -d --force-recreate agents-net openbot coordination`.
- Quay lui mã: đặt `VINHOMES_IMAGE_TAG` về tag trước rồi `up -d`. Image được gắn tag theo biến này, nên build bản
  mới với tag mới trước khi chạy.
- Migration chỉ đi tới. Sao lưu cơ sở dữ liệu trước khi migrate
  (`docs/teams/chien/DATABASE_BACKUP_AND_ENV_2026-10-04.md`); quay lui dữ liệu là restore bản sao lưu đó.
- Trạng thái của Lễ tân nằm trong volume `reception-state`; `down -v` xóa volume này.

## Đã kiểm chứng và chưa kiểm chứng

Đã chạy trên bản sao cơ sở dữ liệu đăng nhập thật, model thật: build 7 image, cả 7 dịch vụ `healthy`, năm bước kiểm
tra ở trên, khởi động lại riêng từng dịch vụ `openbot` và `coordination`, đăng nhập qua `app/serve.ts` với cookie thật.

Chưa kiểm chứng: `factory` mới qua kiểm tra sức khỏe, chưa tạo agent trong container; chưa đóng gói hai giao diện;
chưa có TLS, reverse proxy, giới hạn tài nguyên, thu thập log tập trung hay cảnh báo; chưa thử khởi động lại cả máy
chủ; chưa chạy hai bản `coordination` song song.
