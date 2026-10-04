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
| `routines` | Lịch chạy agent của BQL: giữ lịch và, mỗi phút, giao lượt đến hạn cho `api` đăng vào phòng nhóm | 8789 |
| `factory` | Agent Factory | 4010 |
| `operations` | Giao diện Operations (bản build), chuyển tiếp `/api/business` kèm cookie | 3020, mở ra máy chủ |
| `resident` | Ứng dụng cư dân (file tĩnh sau nginx), chuyển tiếp `/api/business` | 3011, mở ra máy chủ |
| `upgrade` | Job chạy tay: migration, cấp lại quyền cho ba role giới hạn, đăng ký tool kỹ thuật | không có |
| `audit-retention` | Job chạy theo lịch của máy chủ: xóa nhật ký cũ hơn `AUDIT_RETENTION_DAYS` | không có |
| `catalogue` | Job chạy tay sau `upgrade`: đăng ký tool của cổng tool API (báo cáo, an ninh) | không có |
| `minio` | Nơi lưu ảnh và tệp (bucket riêng tư, giao thức S3); dữ liệu nằm trong volume `minio-data` | 9000, không mở ra máy chủ |
| `storage` | Job chạy tay: tạo bucket, ghi nhận nơi lưu, chuyển ảnh của bản cũ từ volume `api-files` sang bucket | không có |

PostgreSQL cần được chuẩn bị trước (trên máy này là container PostgreSQL 17 hiện có). Stack có thêm `platform`:
dịch vụ tài khoản/kết nối OpenBot xác minh cookie nghiệp vụ trên mỗi request, cùng `users.id` và tenant. Agent nghiệp vụ
vẫn chạy ở `coordination`/`openbot`; runtime OpenBot tổng quát cần cấu hình Intelligence riêng.

## Bản hoàn thiện local ngày 05/10/2026

- `run-local.ps1`: build, upgrade bốn role, storage, catalogue, khởi động dịch vụ, rồi `report-bootstrap`.
- `report-bootstrap`: cài preset Agent Báo cáo idempotent, đánh giá sáu ca bằng runtime đã cấu hình, chỉ phát hành khi đạt.
  Admin tạo đơn vị trên UI cũng tạo sẵn preset nháp; BQL không cần dán cấu hình. Chạy lại job để đánh giá/phát hành preset mới.
- `platform`: sử dụng đăng nhập nghiệp vụ; trang `/settings/connected-accounts` có kết nối của người đang đăng nhập.
  Tạo role LOGIN riêng `NOSUPERUSER NOBYPASSRLS`; `OPENBOT_DATABASE_URL` dùng cùng database nghiệp vụ. Không dùng role owner.
  OAuth thật vẫn cần admin cấu hình client và người dùng đồng ý tại vendor.
- Ảnh từ browser đi bằng signed POST tới `S3_PUBLIC_ENDPOINT`; API kiểm size/hash/image rồi chuyển sang key ready khác.
  MinIO mở cổng 9000 trên loopback. Khi bật HTTPS, cấu hình `STORAGE_DOMAIN` và `S3_PUBLIC_ENDPOINT=https://...` cùng nhau.
- `monitor`: cổng loopback 9099, `/metrics` và `/health`; mất dịch vụ ba lần liên tiếp phát alert trong log, hồi phục phát recovery.
  Webhook là tùy chọn qua `MONITOR_ALERT_WEBHOOK`; chưa nghiệm thu gửi thông báo ra ngoài.
- `backup-verify.ps1`: dừng writers, dump hai DB/copy object/cấu hình vào volume riêng, phục hồi sang DB/bucket mới,
  đối chiếu toàn bộ số dòng/checksum, rồi khởi động writers trong `finally`. DB nguồn không bị thay thế. Volume backup chứa
  cấu hình bí mật; chỉ cấp quyền cho người vận hành. Restore vào môi trường chạy cần chạy lại upgrade/storage để cấp role/key.

Trên máy nghiệm thu: Operations `http://localhost:3022`, cư dân `http://localhost:3013`, API 8020, monitor 9099.
Tên miền/chứng chỉ công khai được hoãn theo yêu cầu người dùng. Chi tiết và giới hạn ở
[biên bản nghiệm thu](../../docs/teams/chien/COMPLETION_ACCEPTANCE_2026-10-05.md).

`coordination` và `openbot` dùng chung một không gian mạng. Lõi Supervisor chỉ gửi token của agent tới OpenBot qua
HTTPS hoặc loopback, nên hai dịch vụ gặp nhau trên loopback và không dịch vụ nào khác gọi được OpenBot.
`agents-net` chỉ giữ không gian mạng đó: nhờ vậy mỗi dịch vụ khởi động lại riêng vẫn quay về đúng chỗ.

## Chuẩn bị

1. PostgreSQL 17 có pgvector, đã có hai role giới hạn quyền (API và tool) và tổ chức đầu tiên: dựng mới bằng các
   script trong `services/vinhomes-api/scripts/`, hoặc restore bản sao lưu theo
   `docs/teams/chien/DATABASE_BACKUP_AND_ENV_2026-10-04.md`. Migration và quyền của từng bản phát hành do job
   `upgrade` lo (xem "Chạy").
   Thêm role thứ ba cho dịch vụ lịch chạy (`ROUTINES_DATABASE_URL`), tạo một lần bằng tài khoản chủ:
   `CREATE ROLE vinhomes_routines LOGIN PASSWORD '…' NOSUPERUSER NOBYPASSRLS;`. Không dùng chung role của
   `technical-tools`: dịch vụ đó từ chối chạy nếu role của nó được sửa hoặc xóa dữ liệu, còn lịch thì phải cập nhật
   mỗi lần chạy.
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
docker compose --env-file deployment.env --profile upgrade run --rm storage
docker compose --env-file deployment.env up -d
docker compose --env-file deployment.env ps
```

Job `upgrade` cần `MIGRATION_DATABASE_URL` (chủ sở hữu cơ sở dữ liệu); không dịch vụ đang chạy nào được cấp URL này.
Nó in `migrations-applied`, `grants-applied` kèm tên ba role (lấy từ chính URL kết nối của `api`,
`technical-tools` và `routines`), rồi `technical-tools-registered`. Job `catalogue` in `gateway-tools-registered` kèm tên tool và xóa
tool mà cổng không còn phục vụ. Agent chỉ được cấp tool đã đăng ký, nên chạy lại cả hai job mỗi lần lên bản mới,
trước `up -d`.

### Lịch chạy agent

Trong trang Agent, BQL đặt lịch cho một agent đã phát hành: chỉ dẫn, ngày lặp lại và giờ (múi giờ Việt Nam). Đến giờ,
`routines` mở một lượt chạy và giao cho `api`; `api` đăng chỉ dẫn vào phòng nhóm dưới tên người đặt lịch, nhắc agent
đó, và Supervisor trả lời như mọi câu hỏi khác trong phòng. Kết quả của câu hỏi (đã trả lời, lỗi) đóng lượt chạy.

- Giới hạn có sẵn của nền tảng: mỗi lịch cách nhau ít nhất 15 phút, mỗi người tối đa 20 lịch đang bật, một lịch lỗi
  10 lần liên tiếp thì tự tắt. Lượt đến hạn khi `routines` ngừng quá 10 phút thì bỏ qua, không chạy bù.
- Trước mỗi lượt, `api` kiểm lại quyền của người đặt lịch và bản phát hành của agent; không còn thì lượt đó ghi lỗi
  kèm lý do và không có gì được đăng.
- Lượt mà agent không trả lời trong 10 phút được ghi "bỏ qua".
- `ROUTINES_SERVICE_TOKEN` là token chung của `api` và `routines` (cả hai chiều).

### Kho tri thức cho agent của BQL

Job `catalogue` đăng ký thêm tool đọc `knowledge.search` (nhóm "Tri thức" trong trang Agent). Agent được cấp tool này
tra cứu kho tri thức đã phát hành (`KNOWLEDGE_BASE_ID`) cho một tòa nhà trong phạm vi của đơn vị; đơn vị phụ trách
nhiều tòa thì agent phải nêu `building_id`. Dịch vụ `knowledge` vẫn hỏi lại `api` ai đang tìm, như với Lễ tân; `api`
trả lời bằng quyền của đúng lượt chạy đang gọi tool, và lượt chạy đã kết thúc thì không tra cứu được nữa. Tài liệu
phát hành cho phạm vi của đơn vị quản lý (áp dụng cho cấp dưới) chỉ agent của đơn vị đó đọc được.

### Ảnh và tệp trong phòng nhóm

Thành viên phòng nhóm đính kèm ảnh (PNG, JPEG, GIF, WebP, tới 8 MB) và tệp văn bản (txt, md, csv, json, tới 1 MB),
tối đa 8 tệp một tin. Tệp nằm cùng bucket với ảnh của yêu cầu và chỉ được đọc qua `api` bởi thành viên của phòng.
Agent được nhắc trong tin có tệp nhận nội dung tệp văn bản (tối đa 20.000 ký tự) và tên ảnh; agent chưa xem được ảnh.
Tệp đã tải lên nhưng không gửi kèm tin nào vẫn nằm trong bucket, chưa có bước dọn.

### Model theo vai trò

Mỗi vai trò có model, nhà cung cấp, khóa và địa chỉ riêng. Để trống thì mọi vai trò dùng OpenAI với `OPENAI_API_KEY`.

| Vai trò | Model | Nhà cung cấp và khóa |
|---|---|---|
| Lễ tân | `RECEPTION_MODEL` | `RECEPTION_MODEL_PROVIDER`, `RECEPTION_MODEL_API_KEY`, `RECEPTION_MODEL_BASE_URL` |
| Supervisor | `COORDINATION_MODEL` | `COORDINATION_MODEL_PROVIDER`, `COORDINATION_MODEL_API_KEY`, `COORDINATION_MODEL_BASE_URL` |
| Agent chuyên môn | `SPECIALIST_MODEL` | `SPECIALIST_MODEL_API_KEY` và `SPECIALIST_MODEL_BASE_URL` (đặt cả hai) |
| Factory | `FACTORY_MODEL` | dùng `OPENAI_API_KEY` |
| Embedding tri thức | cố định theo kho đã nhập | `EMBEDDING_API_KEY`, `EMBEDDING_BASE_URL` |

`PROVIDER` nhận `openai`, `google`, `deepseek`, `groq`, `anthropic` hoặc `custom`; với `custom` phải đặt `BASE_URL`. Các
nhà cung cấp này được gọi qua giao thức chat-completions tương thích OpenAI. `OPENAI_API_KEY` chỉ được gửi tới OpenAI:
vai trò dùng nhà cung cấp khác mà thiếu khóa riêng thì dịch vụ không khởi động. Supervisor từ chối câu trả lời ghi tên
model khác tên đã cấu hình; nếu nhà cung cấp trả tên khác (ví dụ alias), khai tên đó ở `COORDINATION_MODEL_ANSWERS_AS`.

Giới hạn đã biết: `anthropic` đi qua lớp tương thích của Anthropic, lớp này bỏ qua yêu cầu trả JSON nên chỉ dùng để
thử. Chưa vai trò nào được chạy thử với khóa thật của Google, DeepSeek, Groq hay Anthropic; phần đã kiểm là dịch vụ
gửi đúng khóa, đúng địa chỉ và đúng tham số cho từng nhà cung cấp. Quản trị viên xem model đang chạy ở màn "Model".

Kết nối ngoài cho agent của BQL (máy chủ MCP theo địa chỉ https, do quản trị viên thêm ở màn "Kết nối ngoài"):
`technical-tools` giữ khóa `CONNECTIONS_KEY` để mã hóa khóa truy cập của từng kết nối và là nơi duy nhất gọi ra máy chủ
MCP, nên container này cần đi được ra internet tới các địa chỉ đó. Để trống `CONNECTIONS_KEY` thì màn hình báo chưa
cấu hình, các phần khác không đổi. Đổi `CONNECTIONS_KEY` thì mọi khóa đã lưu không mở được nữa: phải nhập lại từng kết nối.

### Ảnh và tệp trên MinIO/S3

Ảnh cư dân gửi và ảnh thi công nằm trong một bucket riêng tư. Cơ sở dữ liệu giữ khóa object (`file_objects.object_key`)
và nơi lưu (`storage_locations`: provider `s3`, tên bucket). Nội dung ảnh luôn đi qua `api`, nơi kiểm quyền của người
hỏi; bucket không mở ra ngoài và hai giao diện không gọi thẳng MinIO.

- `S3_ACCESS_KEY` và `S3_SECRET_KEY` là khóa của riêng API. Với MinIO đi kèm, đặt thêm tài khoản quản trị của MinIO ở
  `S3_ADMIN_ACCESS_KEY` và `S3_ADMIN_SECRET_KEY`: job `storage` dùng nó để tạo bucket và cấp cho khóa của API quyền
  đọc, ghi, xóa trên đúng bucket đó, không hơn (job in `"scopedKey": true`). API không bao giờ cầm tài khoản quản trị.
  Muốn dùng dịch vụ S3 khác thì đặt `S3_ENDPOINT`, để trống `S3_ADMIN_*` và dùng khóa đã được cấp quyền sẵn.
- Chạy job `storage` một lần sau `upgrade`, và chạy lại sau khi khôi phục cơ sở dữ liệu. Job in `object-storage-ready`
  kèm số file đã chuyển. Lên từ bản lưu ảnh trong volume `api-files`: job chép từng file vào bucket với cùng khóa rồi
  đổi bản ghi nơi lưu sang bucket; bản ghi của từng ảnh không đổi. Thiếu một file trên đĩa thì job dừng và không đổi gì
  (`--allow-missing` để chuyển phần còn lại). File trong volume không bị xóa: xóa volume sau khi đã kiểm.
- Image `minio/minio` chính thức không còn trên Docker Hub; compose dùng `cgr.dev/chainguard/minio` và cho đổi bằng
  `MINIO_IMAGE`. Kiểm tra sức khỏe dùng lệnh `mc` có sẵn trong image này; đổi sang image không có `mc` thì phải đổi
  lệnh kiểm tra.
- Chạy không có `VINHOMES_API_S3_ENDPOINT` (ví dụ chạy local) thì API vẫn lưu ra đĩa như trước.

Chín dịch vụ phải ở trạng thái `healthy` (`agents-net` không có kiểm tra sức khỏe). Lần chạy thử, cả stack sẵn sàng
sau khoảng 30 giây. Operations ở `http://<máy chủ>:3020/operations`, ứng dụng cư dân ở `http://<máy chủ>:3011`;
đổi cổng bằng `OPERATIONS_PORT`, `RESIDENT_PORT`, và origin tương ứng phải có trong `VINHOMES_ALLOWED_ORIGINS`.

### HTTPS

Hai giao diện mặc định chỉ nghe trên `VINHOMES_BIND_ADDRESS` bằng http. Để mở ra ngoài, chạy thêm dịch vụ `proxy`
(Caddy, cấu hình ở `Caddyfile`):

```bash
docker compose --env-file deployment.env --profile tls up -d
```

- Đặt `OPERATIONS_DOMAIN` và `RESIDENT_DOMAIN` là tên miền của từng giao diện, trỏ về máy chủ; cổng 80 và 443 phải tới
  được máy chủ để Caddy tự xin và gia hạn chứng chỉ. Chứng chỉ nằm trong volume `caddy-data`.
- Đặt `SECURE_COOKIES=1` để cookie phiên chỉ được gửi qua https, và ghi hai địa chỉ `https://…` vào
  `VINHOMES_ALLOWED_ORIGINS`. Khi đã bật, đăng nhập qua cổng http 3020/3011 không còn dùng được.
- `PROXY_TLS=tls internal` để thử trên tên không công khai (trình duyệt sẽ cảnh báo chứng chỉ);
  `PROXY_TLS=tls /certs/site.pem /certs/site.key` để dùng chứng chỉ có sẵn (gắn thư mục vào dịch vụ `proxy`).
- API (cổng 8000) không đi qua proxy: hai giao diện gọi nó trong mạng nội bộ. Giữ `VINHOMES_BIND_ADDRESS=127.0.0.1`.

## Kiểm tra sau khi chạy

1. `GET /ready` của `api` trả 200; gọi `/operations/me` khi chưa đăng nhập trả 401.
2. Đăng nhập bằng một tài khoản BQL thật, `/operations/me` trả đúng vai trò.
3. Cư dân gửi một yêu cầu trong chat: Lễ tân trả mã ticket, phiên của ticket có agent tham gia và tới
   `waiting_management` kèm phương án.
4. BQL duyệt phương án: cư dân nhận câu hỏi đồng ý phương án trong hội thoại.
5. Cư dân hỏi một câu về quy định: câu trả lời có dòng nguồn.

## Sao lưu

Ba thứ phải sao lưu cùng lúc; thiếu một thứ thì bản sao lưu không dùng được trọn vẹn:

1. Hai cơ sở dữ liệu (nghiệp vụ và checkpoint của Supervisor), bằng `pg_dump -Fc` với tài khoản chủ.
2. Ảnh và tệp: volume `minio-data` (hoặc bucket trên dịch vụ S3 đang dùng). Ví dụ, khi `minio` đã dừng:
   `docker run --rm -v vinhomes_minio-data:/data:ro -v "$PWD":/backup alpine tar czf /backup/minio-data.tgz -C /data .`
3. File `deployment.env`. `CONNECTIONS_KEY` mở các khóa kết nối đã lưu; mất nó thì phải nhập lại từng kết nối.

Trạng thái của Lễ tân (volume `reception-state`) là bộ nhớ hội thoại đang dở; mất nó thì cư dân bắt đầu lại cuộc trò
chuyện, yêu cầu đã ghi nhận không mất. Chưa có lịch sao lưu tự động: đặt lịch bằng công cụ của máy chủ.

## Dọn dẹp định kỳ: nhật ký và tệp chưa gửi

Hai job chạy một lần rồi thoát; chạy lại bao nhiêu lần cũng được. Không dịch vụ nào tự gọi chúng: máy chủ hẹn giờ.

**Nhật ký.** Bảng nhật ký (`audit_events`) chỉ thêm, không sửa; mặc định giữ mãi. Đặt `AUDIT_RETENTION_DAYS` (số
ngày, từ 1); để trống thì job không xóa gì:

```bash
docker compose --env-file deployment.env --profile upgrade run --rm audit-retention
```

Job in một dòng `audit-retention-swept` kèm số dòng đã xóa. Cơ sở dữ liệu tự từ chối xóa dòng còn trong thời hạn đã
khai. Job chạy bằng tài khoản chủ như các job `upgrade`, nên không dịch vụ đang chạy nào có quyền xóa nhật ký.
Trước khi dọn, quản trị viên lấy bản sao ở màn Nhật ký ("Xuất tệp CSV": chọn khoảng ngày, tối đa 50.000 sự kiện một
tệp; mỗi lần xuất cũng được ghi vào nhật ký).

**Tệp chưa gửi.** Tệp được tải lên phòng nhóm trước khi tin nhắn được gửi; tin không gửi thì tệp nằm lại. Job dưới
đây xóa tệp đã tải lên hơn một ngày mà không gắn vào tin nào (xóa nội dung trong bucket, rồi ghi tệp là đã xóa), và in
`room-files-cleaned` kèm số tệp. Nó chỉ dùng role và khóa lưu trữ của chính `api`:

```bash
docker compose --env-file deployment.env --profile upgrade run --rm room-file-cleanup
```

**Hẹn giờ.** Mỗi ngày một lần, vào giờ ít người dùng. `-T` để lệnh chạy được khi không có màn hình điều khiển. Trên
Linux, thêm vào `crontab -e` của tài khoản được chạy Docker (đổi đường dẫn cho đúng nơi đặt mã):

```cron
15 2 * * * cd /opt/vinhomes/deploy/vinhomes && docker compose --env-file deployment.env --profile upgrade run --rm -T audit-retention >> /var/log/vinhomes-jobs.log 2>&1
30 2 * * * cd /opt/vinhomes/deploy/vinhomes && docker compose --env-file deployment.env --profile upgrade run --rm -T room-file-cleanup >> /var/log/vinhomes-jobs.log 2>&1
```

Trên Windows, tạo hai tác vụ bằng Task Scheduler (chạy PowerShell với quyền của tài khoản dùng Docker Desktop):

```powershell
$run = 'cd /d C:\vinhomes\deploy\vinhomes && docker compose --env-file deployment.env --profile upgrade run --rm -T {0} >> C:\vinhomes\jobs.log 2>&1'
schtasks /Create /TN "Vinhomes audit retention" /SC DAILY /ST 02:15 /TR ("cmd /c " + ($run -f 'audit-retention'))
schtasks /Create /TN "Vinhomes room file cleanup" /SC DAILY /ST 02:30 /TR ("cmd /c " + ($run -f 'room-file-cleanup'))
```

Các dòng hẹn giờ trên là mẫu, chưa chạy thử trên máy chủ thật. Chạy thử một tác vụ ngay bằng
`schtasks /Run /TN "Vinhomes audit retention"` (Windows) hoặc dán lệnh sau dấu sao vào terminal (Linux).
Kiểm tra sau lần chạy đầu: tệp log có dòng `audit-retention-swept` và `room-files-cleaned`. Job thoát với mã khác 0
khi không tới được cơ sở dữ liệu hoặc bucket; lần chạy sau làm lại từ đầu, không mất gì.

## Khôi phục và quay lui

- Khởi động lại `coordination` hoặc `openbot` riêng lẻ không làm mất phiên: checkpoint nằm trong PostgreSQL.
  Quyết định BQL đưa ra trong lúc Supervisor dừng được xử lý khi nó chạy lại.
- Nếu `coordination` báo `unhealthy` sau khi máy chủ hoặc Docker khởi động lại:
  `docker compose --env-file deployment.env up -d --force-recreate agents-net openbot coordination`.
- Quay lui mã: đặt `VINHOMES_IMAGE_TAG` về tag trước rồi `up -d`. Image được gắn tag theo biến này, nên build bản
  mới với tag mới trước khi chạy.
- Migration chỉ đi tới. Sao lưu cơ sở dữ liệu trước khi migrate
  (`docs/teams/chien/DATABASE_BACKUP_AND_ENV_2026-10-04.md`); quay lui dữ liệu là restore bản sao lưu đó.
- Trạng thái của Lễ tân nằm trong volume `reception-state`, ảnh nằm trong volume `minio-data`; `down -v` xóa cả
  hai. Sao lưu cơ sở dữ liệu mà không sao lưu bucket thì bản ghi ảnh còn nhưng file mất.

## Đã kiểm chứng và chưa kiểm chứng

Lần chạy 05/10/2026 (đợt 3), build lại 9 image từ một bản sao sạch của nhánh, trên bản sao cơ sở dữ liệu đăng nhập
thật đã bị thu lại các quyền của bản này trước khi chạy job:

- Job `upgrade` in `grants-applied` với ba role; job `catalogue` đăng ký thêm `knowledge.search`; job `storage` chuyển
  8 ảnh; job `audit-retention` in `audit-retention-swept` (0 dòng, vì không có dòng nào quá hạn). 11 dịch vụ `healthy`,
  có `routines`.
- Lịch chạy: đặt lịch qua giao diện vận hành (https), cho lịch đến hạn, `routines` giao lượt chạy, `api` đăng câu hỏi
  vào phòng nhóm, Supervisor nhận; lượt chạy đóng "lỗi" vì khóa model bị từ chối; xóa lịch xóa cả lượt chạy.
- Tệp phòng nhóm: tải ảnh và tệp văn bản, gửi kèm tin, tệp nằm trong bucket và đọc lại đúng nội dung; trang phòng
  nhóm hiện ảnh.
- Role của `technical-tools` vẫn không có quyền sửa, xóa trên bảng nào; role của `routines` chỉ được sửa bốn bảng lịch.

Chưa kiểm ở lần này: một lượt chạy theo lịch mà agent trả lời được, tra cứu kho tri thức của agent BQL với embedding
thật, và agent đọc tệp đính kèm (đều cần khóa model dùng được).

Lần chạy 05/10/2026, build lại cả 9 image, trên bản sao cơ sở dữ liệu đăng nhập thật, có `proxy` với chứng chỉ nội bộ:

- Job `storage`: tạo bucket, cấp khóa riêng cho API (`"scopedKey": true`), chuyển 6 ảnh cũ từ đĩa sang bucket; chạy lại
  không chuyển gì thêm. 10 dịch vụ `healthy` (9 dịch vụ cũ và `minio`).
- Qua https: đăng nhập được, cookie phiên có cờ Secure và HttpOnly; năm màn quản trị mở được; ảnh cũ tải được từ bucket;
  ảnh mới tải lên rồi tải về đúng nội dung; ứng dụng cư dân và đường `/api/business` của nó trả 200.
- Lễ tân đặt `deepseek`, Supervisor đặt `google` với khóa không dùng được: các dịch vụ vẫn khởi động và màn Model báo
  đúng nhà cung cấp từng vai trò. Chưa có hội thoại thật với các nhà cung cấp này.
- Lệnh nén volume `minio-data` trong mục Sao lưu chạy được.

Chưa kiểm ở lần này: tên miền thật với chứng chỉ Let's Encrypt, khôi phục từ bản sao lưu, và mọi bước cần model.
Trên Docker Desktop cho Windows, truy cập cổng đã mở qua `::1` bị treo; dùng `127.0.0.1`.

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
