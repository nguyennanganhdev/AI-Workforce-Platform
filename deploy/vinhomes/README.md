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
| `operations` | Giao diện Operations (bản build), chuyển tiếp `/api/business` kèm cookie | 3020, mở ra máy chủ |
| `resident` | Ứng dụng cư dân (file tĩnh sau nginx), chuyển tiếp `/api/business` | 3011, mở ra máy chủ |
| `upgrade` | Job chạy tay: migration, cấp lại quyền cho hai role giới hạn, đăng ký tool kỹ thuật | không có |
| `catalogue` | Job chạy tay sau `upgrade`: đăng ký tool của cổng tool API (báo cáo, an ninh) | không có |

Không nằm trong stack: PostgreSQL (dùng cơ sở dữ liệu đã có sẵn role giới hạn quyền và tổ chức đầu tiên), TLS và
reverse proxy, và đăng nhập thống nhất với tài khoản OpenBot.

`coordination` và `openbot` dùng chung một không gian mạng. Lõi Supervisor chỉ gửi token của agent tới OpenBot qua
HTTPS hoặc loopback, nên hai dịch vụ gặp nhau trên loopback và không dịch vụ nào khác gọi được OpenBot.
`agents-net` chỉ giữ không gian mạng đó: nhờ vậy mỗi dịch vụ khởi động lại riêng vẫn quay về đúng chỗ.

## Chuẩn bị

1. PostgreSQL 17 có pgvector, đã có hai role giới hạn quyền (API và tool) và tổ chức đầu tiên: dựng mới bằng các
   script trong `services/vinhomes-api/scripts/`, hoặc restore bản sao lưu theo
   `docs/teams/chien/DATABASE_BACKUP_AND_ENV_2026-10-04.md`. Migration và quyền của từng bản phát hành do job
   `upgrade` lo (xem "Chạy").
2. Một cơ sở dữ liệu riêng cho checkpoint của Supervisor, chủ sở hữu là role không phải superuser. Bảng được tạo
   khi `coordination` khởi động lần đầu.
3. Kho tri thức đã phát hành (`KNOWLEDGE_BASE_ID`) và ít nhất một agent chuyên môn đã phát hành trong phòng BQL.
4. Sao `deployment.env.example` thành `deployment.env` (được git bỏ qua) và điền. Mỗi token là một giá trị ngẫu
   nhiên riêng, tối thiểu 32 ký tự: `python -c "import secrets; print(secrets.token_hex(32))"`. Trong URL kết nối,
   máy chủ cơ sở dữ liệu phải là địa chỉ container nhìn thấy được (không phải `127.0.0.1`).
5. `REPAIR_CATEGORY_CODES` là mã các nhóm dịch vụ có hóa đơn tính là sửa chữa (ví dụ `technical`). Để trống thì
   agent báo cáo không báo tổng hóa đơn sửa chữa.
6. `VINHOMES_ALLOWED_ORIGINS` là danh sách origin của hai giao diện. Thiếu origin thì đăng nhập bị từ chối với
   "Untrusted browser origin".

## Chạy

```powershell
cd deploy/vinhomes
docker compose --env-file deployment.env --profile upgrade build
docker compose --env-file deployment.env --profile upgrade run --rm upgrade
docker compose --env-file deployment.env --profile upgrade run --rm catalogue
docker compose --env-file deployment.env up -d
docker compose --env-file deployment.env ps
```

Job `upgrade` cần `MIGRATION_DATABASE_URL` (chủ sở hữu cơ sở dữ liệu); không dịch vụ đang chạy nào được cấp URL này.
Nó in `migrations-applied`, `grants-applied` kèm tên hai role (lấy từ chính URL kết nối của `api` và
`technical-tools`), rồi `technical-tools-registered`. Job `catalogue` in `gateway-tools-registered` kèm tên tool và xóa
tool mà cổng không còn phục vụ. Agent chỉ được cấp tool đã đăng ký, nên chạy lại cả hai job mỗi lần lên bản mới,
trước `up -d`.

Kết nối ngoài cho agent của BQL (máy chủ MCP theo địa chỉ https, do quản trị viên thêm ở màn "Kết nối ngoài"):
`technical-tools` giữ khóa `CONNECTIONS_KEY` để mã hóa khóa truy cập của từng kết nối và là nơi duy nhất gọi ra máy chủ
MCP, nên container này cần đi được ra internet tới các địa chỉ đó. Để trống `CONNECTIONS_KEY` thì màn hình báo chưa
cấu hình, các phần khác không đổi. Đổi `CONNECTIONS_KEY` thì mọi khóa đã lưu không mở được nữa: phải nhập lại từng kết nối.

Ảnh cư dân gửi và ảnh thi công nằm trong volume `api-files` (gắn vào `/var/lib/vinhomes/files` của `api`). API chỉ
lưu file ra đĩa khi đang nghe trên loopback; trong container quy tắc đó được mở bằng cài đặt riêng
`VINHOMES_API_VOLUME_FILE_STORAGE=1`, compose đã đặt sẵn. Cách lưu này chỉ dùng cho một máy chủ và một bản `api`.

Chín dịch vụ phải ở trạng thái `healthy` (`agents-net` không có kiểm tra sức khỏe). Lần chạy thử, cả stack sẵn sàng
sau khoảng 30 giây. Operations ở `http://<máy chủ>:3020/operations`, ứng dụng cư dân ở `http://<máy chủ>:3011`;
đổi cổng bằng `OPERATIONS_PORT`, `RESIDENT_PORT`, và origin tương ứng phải có trong `VINHOMES_ALLOWED_ORIGINS`.

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
- Trạng thái của Lễ tân nằm trong volume `reception-state`, ảnh nằm trong volume `api-files`; `down -v` xóa cả
  hai. Sao lưu cơ sở dữ liệu mà không sao lưu `api-files` thì bản ghi ảnh còn nhưng file mất.

## Đã kiểm chứng và chưa kiểm chứng

Lần chạy 04/10/2026 (đêm), build lại cả 9 image từ mã hiện tại, trên bản sao cơ sở dữ liệu đăng nhập thật:

- Job `upgrade` và `catalogue`: từ danh mục tool rỗng, hai job đăng ký lại đủ 14 tool kỹ thuật, 4 tool báo cáo và
  2 tool an ninh.
- Cả 9 dịch vụ `healthy`; gọi `/operations/me` khi chưa đăng nhập trả 401.
- Qua hai giao diện trong container, bằng trình duyệt và tài khoản thật: BQL mở phiên từ chuông thông báo và duyệt
  phương án trong màn Điều phối; một yêu cầu đi từ phân công, kỹ thuật viên nhận việc, báo giá, cư dân đồng ý, tải ảnh
  trước/sau (2 file nằm trong volume `api-files`), gửi kết quả, cư dân xác nhận, tới BQL duyệt đóng phiên.
- Thay container `api` trong lúc stack đang chạy: ứng dụng cư dân gọi lại được API sau vài giây (nginx hỏi lại DNS
  của Docker). Trước khi sửa, cư dân nhận 502 cho tới khi container `resident` khởi động lại.

Lần chạy trước đó trong ngày, khi khóa model còn số dư, đã kiểm trong container: cư dân gửi yêu cầu trong chat, trả lời
hai câu hỏi của Supervisor, BQL duyệt phương án, cư dân đồng ý, đúng một phiếu thi công được tạo; khởi động lại riêng
`openbot` và `coordination`.

Chưa kiểm chứng: các bước cần model trên image mới (khóa model hết số dư từ tối 04/10): phiên mới do Supervisor lập
phương án, agent báo cáo gọi tool, hỏi agent trong phiên. `factory` mới qua kiểm tra sức khỏe, chưa tạo agent trong
container. Chưa có TLS, reverse proxy, giới hạn tài nguyên, thu thập log tập trung hay cảnh báo; chưa thử khởi động
lại cả máy chủ; chưa chạy hai bản `coordination` song song. Lưu ảnh ra volume chỉ dùng cho một máy chủ.
