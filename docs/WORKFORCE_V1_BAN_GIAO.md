# Workforce v1: tài liệu bàn giao (Docker)

Cập nhật: 13/10/2026 (Docker 0.3.0: PostgreSQL, Redis, MinIO và hai bản sao API). Viết cho hai người đọc:

- **Người vận hành platform**: chạy, dừng, nâng cấp, sao lưu, xoay khóa, xử lý workflow cần người (mục 1 đến 9).
- **Người tích hợp phía đối tác**: gọi API công khai `/workforce/v1` (mục 10).

Tài liệu này nói về *chạy platform bằng Docker trên một máy*. Ý nghĩa từng biến môi trường, migration và các vòng quét nền ở `docs/WORKFORCE_V1_VAN_HANH.md`; từng bước nối một đối tác ở `docs/WORKFORCE_V1_HUONG_DAN_KET_NOI.md`. Mọi lệnh dưới đây chạy trong thư mục `platform_VP/deploy` trừ khi ghi khác.

**Mức độ sẵn sàng, nói thẳng.** Gói này đã chạy thật trên Docker với một **model kịch bản** và một **MCP mẫu** (`platform_VP/deploy/SMOKE_RESULT.md`). Chưa có lần chạy nào với model thật, MCP thật của đối tác hay hạ tầng production. Mục 9 liệt kê đủ cái đã chứng minh và cái chưa.

## 1. Cái gì chạy

| Dịch vụ (compose) | Image | Việc | Trạng thái |
|---|---|---|---|
| `postgres` | `postgres:16-alpine` | Hai database: `awp` (bảng `awp_*`, `wf_*`) và `awp_storage` (phiên và tin nhắn của AgentScope) | **đang dùng** |
| `migrate` | `awp-platform:<tag>` | Chạy một lần trước mỗi lần API khởi động: `python -m awp migrate --storage` rồi `--check`. API chỉ khởi động khi job này thoát 0 | **đang dùng** |
| `redis` | `redis:7-alpine` | Bus chung của các tiến trình API (`AWP_REDIS_URL`): khóa phiên và hàng đợi đánh thức của AgentScope, tín hiệu giữa các bản sao, bộ đếm luồng SSE. Không giữ dữ liệu nghiệp vụ nào | **đang dùng** |
| `api` | `awp-platform:<tag>` | Platform: `/workforce/v1` (đối tác), `/platform/v1` (admin, manager), `/console` (trang quản trị), engine workflow và các vòng quét nền, tất cả trong một tiến trình | **đang dùng** |
| `api2` | `awp-platform:<tag>` | Bản sao thứ hai của `api` (cùng image, cùng cấu hình, cùng DB, Redis và volume workspace), chỉ với `--profile two` | tùy chọn |
| `fake-model`, `fake-mcp` | `awp-platform:<tag>` | Model kịch bản và MCP mẫu, chỉ với `--profile demo` | chỉ để thử |
| `minio` | `cgr.dev/chainguard/minio` | Bucket private cho ảnh; API dùng `AWP_ASSET_BACKEND=s3` và `AWP_S3_*` | **đang dùng** |

Image `awp-platform` (`platform_VP/Dockerfile`): `python:3.12-slim`, cài `awp` và AgentScope từ nguồn trong repo, 102 gói bên thứ ba ghim phiên bản và hash ở `deploy/requirements.lock` (đúng phiên bản của venv phát triển), chạy bằng user `awp` (uid 10001), không chứa bí mật. Thư mục duy nhất tiến trình ghi là `/var/lib/awp` (volume `workspaces`).

Cổng trên máy chủ, **tất cả chỉ bind `127.0.0.1`**: API `8800`, bản sao thứ hai `8801`, PostgreSQL `5590` (đổi trong `deploy/.env`: `AWP_HOST_PORT`, `AWP_HOST_PORT2`, `AWP_PG_HOST_PORT`). Redis không publish cổng nào. MinIO `9190`/`9191` chạy cùng stack. Muốn cho máy khác gọi tới thì đặt một reverse proxy có TLS phía trước; platform không tự làm TLS.

**Địa chỉ ảnh:** `AWP_S3_ENDPOINT=http://minio:9000` dùng trong stack. `AWP_S3_PUBLIC_ENDPOINT` là địa chỉ ký vào link mà MCP/model sẽ đọc; mặc định cũng là `http://minio:9000` cho demo nội bộ. Khi tích hợp bên ngoài, đặt thành endpoint HTTPS họ truy cập được; không sửa host của link sau khi ký. Nếu đã có `deploy/.env` từ 0.2.0, thêm các biến phần 6 của `.env.example` với secret MinIO hiện có; script không ghi đè file cũ.

Tên project compose là `awp-platform`: container `awp-platform-<dịch vụ>-1`, volume `awp-platform_pgdata`, `awp-platform_redisdata`, `awp-platform_workspaces`.

**Hai bản sao.** `docker compose --profile two up -d` chạy thêm `api2`. Hai bản sao ngang hàng: request, sự kiện provider và luồng SSE vào bản nào cũng được, và khi một bản chết bản kia nhận việc đang dở của nó sau `AWP_WF_LEASE_SECONDS` (60 giây). Trước chúng cần một reverse proxy chia tải (compose này không có); client SSE bị đứt thì nối lại, vào bản nào cũng được, bằng `Last-Event-ID`. Thêm bản sao thứ ba là thêm một service như `api2`. Chi tiết và giới hạn: `docs/WORKFORCE_V1_VAN_HANH.md` mục 11.

## 2. Khởi động lần đầu

Cần: Docker có Compose v2 (đã thử với Docker 29.6, Compose v5.3), Python 3.9 trở lên trên máy chủ để chạy hai script (chỉ dùng thư viện chuẩn).

```
cd platform_VP/deploy
python init_env.py                 # sinh deploy/.env: khóa admin, AWP_SECRET_KEY, mật khẩu DB; in khóa admin MỘT lần
# sửa deploy/models.yaml (script chép từ core/models.example.yaml) và thêm khóa model vào deploy/.env, ví dụ OPENAI_API_KEY=...
docker compose build               # image awp-platform:<AWP_IMAGE_TAG>
docker compose up -d               # postgres, redis, minio -> migrate -> api   (thêm --profile two để có bản sao thứ hai)
docker compose ps                  # api phải (healthy), migrate phải Exited (0)
curl http://127.0.0.1:8800/platform/v1/health
```

- `init_env.py` **không bao giờ ghi đè** `deploy/.env` đang có (thoát mã 1). Tệp đó chứa bí mật và bị git bỏ qua; giải thích từng biến ở `deploy/.env.example`.
- Mật khẩu PostgreSQL chỉ được áp khi volume dữ liệu được tạo lần đầu. Đổi mật khẩu sau đó: mục 6.
- Sau khi API lên, mở `http://127.0.0.1:8800/console` và đăng nhập bằng khóa admin, hoặc làm theo `docs/WORKFORCE_V1_HUONG_DAN_KET_NOI.md`.

**Chạy thử không cần khóa model** (model kịch bản, MCP mẫu; không dùng cho production):

```
python init_env.py --demo
docker compose build
docker compose --profile demo up -d
python smoke.py --docker           # 23 bước, gồm upload ảnh MinIO; in PASS/FAIL từng bước
docker compose --profile demo down -v
```

`smoke.py` đi hết hướng dẫn nối bằng HTTP: trang console lấy từ container, hồ sơ leader, đánh giá, cổng phát hành, client, khóa, manager, integration, route, bật MCP và phát hiện tool, kích hoạt tool, đối tác xác nhận route, `start_workflow`, SSE, approval, sự kiện provider có chữ ký, xác nhận, đóng, rồi kiểm rằng không gì xảy ra hai lần. Nó tạo dữ liệu thử (client `Smoke partner …`, hồ sơ `smoke_leader_…`) trong tenant của khóa admin: **đừng chạy trên database production**.

## 3. Dừng, khởi động lại, xem log

| Việc | Lệnh |
|---|---|
| Xem trạng thái | `docker compose ps -a` |
| Log API | `docker compose logs -f --tail 200 api` (log xoay vòng: 5 tệp, mỗi tệp 10 MB) |
| Dừng API | `docker compose stop api` |
| Dừng tất cả, giữ dữ liệu | `docker compose down` |
| Khởi động lại | `docker compose up -d` |
| **Xóa cả dữ liệu** | `docker compose down -v` (xóa volume: mất database và workspace) |

Dừng API là **tắt êm**: nhận SIGTERM, ngừng nhận request, chờ các request đang chạy tối đa `AWP_SHUTDOWN_SECONDS` (mặc định 20 giây), rồi dừng engine và đóng kết nối DB. Không có luồng SSE nào mở thì mất chưa tới 1 giây; có luồng SSE mở thì mất đủ 20 giây (luồng bị cắt, client nối lại bằng `Last-Event-ID`). Compose chờ tối đa 45 giây (`stop_grace_period`) trước khi giết.

Tiến trình chết đột ngột (kể cả `kill -9`): Docker tự khởi động lại container (`restart: unless-stopped`). Workflow đang chờ cư dân hoặc chờ đối tác tiếp tục ngay từ đúng trạng thái đã lưu. Việc tiến trình chết **đang làm dở** (một lượt của agent, một lời gọi đối tác) được tiến trình khác, hoặc chính nó sau khi lên lại, nhận sau khi lease của tiến trình chết hết hạn (tối đa `AWP_WF_LEASE_SECONDS`, 60 giây): lượt chưa nói gì với cư dân thì chạy lại, lời gọi đối tác dở thì gửi lại cùng `client_reference` nếu tool khai `idempotency_arg`, không thì workflow sang `needs_attention` (`operation_unknown`). Đã thử thật trên Docker và bằng bộ test giết tiến trình (mục 9).

## 4. Nâng cấp và rollback

**Nâng cấp** (một bản sao API nên có thời gian ngừng: job `migrate` khoảng 7 giây, API lên khoảng 3 giây trong lần đo):

```
# 1. sao lưu trước (mục 5)
# 2. lấy mã mới, đặt tag mới trong deploy/.env: AWP_IMAGE_TAG=0.2.0
docker compose build
docker compose up -d               # migrate chạy trước; thất bại thì API cũ đã dừng và API mới KHÔNG khởi động
docker compose logs migrate        # phải kết thúc bằng "up to date at revision ..."
```

Nếu `migrate` thất bại: đọc log của nó, **đừng** đặt `AWP_AUTO_CREATE=1` để "cho chạy tạm". Platform cố ý từ chối khởi động trên database không ở đúng revision.

**Rollback**:

- Bản mới **không** có migration mới: đặt lại `AWP_IMAGE_TAG` cũ, `docker compose up -d` (image cũ còn trên máy nếu chưa xóa).
- Bản mới **đã** chạy migration: image cũ sẽ từ chối database mới hơn mã của nó. Cách chắc chắn là khôi phục bản sao lưu lấy trước khi nâng cấp (mục 5), rồi mới chạy image cũ. Hạ revision bằng tay chỉ có ở dạng hàm (`awp.migrate.downgrade(url, revision)`), chưa có lệnh dòng lệnh.

Rollback một **agent** (không phải rollback platform) là việc khác: `POST /platform/v1/profiles/{key}/rollback`, xem `docs/WORKFORCE_V1_VAN_HANH.md` mục 9.

Quy trình nâng cấp và rollback ở mục này **chưa được chạy thử** (mới có một tag image).

## 5. Sao lưu và khôi phục

Bốn thứ phải sao lưu, và để riêng bí mật:

1. **Hai database, cùng một thời điểm** (workflow tham chiếu phiên AgentScope bằng id; hai bản lệch nhau để lại workflow mất phiên):

```
mkdir -p backups
docker compose exec -T postgres pg_dump -U awp -Fc awp         > backups/awp-$(date +%F).dump
docker compose exec -T postgres pg_dump -U awp -Fc awp_storage > backups/awp_storage-$(date +%F).dump
```

Hai lệnh `pg_dump` liền nhau trên một hệ đang nhận request có thể lệch nhau vài giây. Muốn khớp tuyệt đối: dừng mọi bản sao API (`docker compose --profile two stop api api2`) trước, rồi sao lưu database, workspace và ảnh trong cùng khoảng dừng.

2. **Volume workspace** (bộ nhớ dài hạn và offload ngữ cảnh theo workflow):

```
docker run --rm -v awp-platform_workspaces:/data:ro python:3.12-slim tar -czf - -C /data . > backups/workspaces-$(date +%F).tgz
```

(Trong Git Bash trên Windows đặt `MSYS_NO_PATHCONV=1` trước lệnh này.)

3. **`deploy/.env`**, cất ở nơi giữ bí mật, **không** để chung với bản dump. Mất `AWP_SECRET_KEY` là mất mọi bí mật đã niêm trong database (khóa ký provider, header MCP): phải tạo lại.

4. **Volume MinIO** (`awp-platform_miniodata`): giữ nguyên bytes mà `wf_assets` tham chiếu. Dừng API và MinIO trước khi lấy bản tar; nếu dùng S3 bên ngoài thì dùng snapshot/backup của dịch vụ đó. Khôi phục database mà bỏ mất object ảnh sẽ để lại metadata không đọc được ảnh.

```
docker compose stop minio
docker run --rm -v awp-platform_miniodata:/data:ro python:3.12-slim tar -czf - -C /data . > backups/minio-$(date +%F).tgz
docker compose --profile two up -d
```

Thư mục `deploy/backups/` bị git bỏ qua. Ba lệnh sao lưu database/workspace đã chạy trên stack thử ở B4; quy trình sao lưu/khôi phục MinIO mới này chưa được diễn tập.

**Khôi phục** (thứ tự; **chưa được chạy thử**, hãy diễn tập trước khi cần):

```
docker compose stop api
docker compose exec -T postgres dropdb   -U awp --if-exists awp
docker compose exec -T postgres createdb -U awp -O awp awp
docker compose exec -T postgres pg_restore -U awp -d awp --no-owner < backups/awp-NGAY.dump
# làm tương tự với awp_storage; giải nén workspaces vào volume nếu có dùng
docker compose up -d               # migrate --check phải qua
```

Dữ liệu tăng theo thời gian và lịch dọn (retention): `docs/WORKFORCE_V1_VAN_HANH.md` mục 5 và 6.

## 6. Xoay khóa

| Khóa | Cách xoay | Lưu ý |
|---|---|---|
| Khóa admin (`AWP_ADMIN_KEYS`) | Thêm cặp `khóa-mới:tenant` (ngăn bằng `;`), `docker compose up -d --force-recreate api`, chuyển người dùng sang khóa mới, bỏ cặp cũ, khởi động lại lần nữa | Hai khóa cùng tenant dùng song song được. Nhãn người làm trong lịch sử (`admin:<8 ký tự>`) suy ra từ khóa nên đổi theo khóa |
| Khóa đối tác (`dp_…`) | Không gián đoạn: `POST /platform/v1/wf/clients/{client_id}/keys` (khóa mới), đối tác chuyển sang, rồi `POST /platform/v1/wf/keys/{key_id}/revoke` khóa cũ | `POST …/keys/{key_id}/rotate` cũng được nhưng **thu hồi khóa cũ ngay lập tức**: đối tác bị 401 cho tới khi dùng khóa mới |
| Khóa manager (`mk_…`) | `POST /platform/v1/wf/managers/{id}/keys` rồi `…/keys/{key_id}/revoke` | Tắt cả tài khoản: `…/managers/{id}/disable` |
| Khóa API và khóa ký của provider | `POST /platform/v1/wf/integrations/{id}/signing-keys` (khóa ký mới, hiện một lần), backend đối tác chuyển sang, `…/signing-keys/{key_id}/revoke`. Khóa API của provider xoay như khóa đối tác | Sự kiện ký bằng khóa đã thu hồi bị từ chối |
| Token của MCP đối tác (header) | `PUT /platform/v1/wf/routes/{route_id}/mcp` với header mới (thay cả bộ server của route) | `GET` chỉ trả tên header, không trả giá trị |
| Mật khẩu PostgreSQL | `docker compose exec postgres psql -U awp -c "ALTER ROLE awp PASSWORD '...'"`, sửa **ba** chỗ trong `deploy/.env` (`POSTGRES_PASSWORD` và mật khẩu trong hai URL), `docker compose up -d --force-recreate api` | Dùng ký tự an toàn trong URL (chữ, số) |
| `AWP_SECRET_KEY` | **Không xoay định kỳ.** Đổi khóa không niêm lại dữ liệu cũ: sau khi đổi phải tạo lại mọi khóa ký provider và ghi lại header của mọi MCP server | Chỉ đổi khi khóa bị lộ; chưa có công cụ niêm lại |
| Khóa model (`OPENAI_API_KEY`…) | Sửa `deploy/.env`, `docker compose up -d --force-recreate api` | `GET /platform/v1/models` cho biết model nào còn dùng được |

Các dòng trong bảng này lấy từ mã và tài liệu; **chưa dòng nào được diễn tập trên stack Docker** trong bước B4.

## 7. Workflow cần người: `attention_reason` và cách xử lý

Tìm: `GET /platform/v1/wf/workflows?state=needs_attention` (hoặc màn hình Vận hành của console). Mỗi dòng có `attention_reason`. Xem thêm quanh nó: `GET /platform/v1/wf/operations?workflow_id=…`, `…/approvals?workflow_id=…`, `…/receipts?workflow_id=…`, và hồ sơ vụ `GET /platform/v1/cases/{case_id}/items`.

Người vận hành kết thúc bằng `POST /platform/v1/wf/workflows/{id}/resolve` với `{"action": "resume"}` hoặc `{"action": "close"}`:

- `resume`: workflow về `active` và leader được bảo làm tiếp. Các operation `unknown` được đánh dấu là người đã xem và không còn giữ workflow lại. **Platform không gọi lại đối tác**: nếu việc phải làm lại thì đó là quyết định của leader ở lượt sau, hoặc của người.
- `close`: đóng workflow (`close_reason = operator_closed`) và ngừng theo dõi mọi thứ còn mở. **Không gọi gì sang đối tác**: việc đã gửi đi vẫn nằm ở phía họ.

Các lý do có thật trong mã (`platform_VP/core/src/awp/workforce/`):

| `attention_reason` | Khi nào xảy ra (tệp) | Việc cần làm |
|---|---|---|
| `leader_silent` | Leader kết thúc lượt mà không nói gì với cư dân, đã nhắc hết số lần (`decide.py`). Cư dân nhận câu `safe_reply` của route | Đọc hồ sơ vụ xem leader kẹt ở đâu (thiếu tool, hướng dẫn mơ hồ). `resume` để thử lại; lặp lại nhiều lần thì sửa hồ sơ agent |
| `engine_error` | Một job của workflow thất bại quá `AWP_WF_JOB_ATTEMPTS` lần (`runner.py`): ví dụ model trả lỗi hoặc lỗi nội bộ | Xem log API quanh thời điểm đó và `GET /platform/v1/models`. Sửa nguyên nhân (khóa model, hạn mức) rồi `resume` |
| `operation_unknown` | Một hành động đã gửi sang đối tác nhưng không biết kết quả (hết giờ, mất kết nối) và không có cách hỏi lại (`reconcile.py`, `decide.py`) | **Hỏi đối tác trước** bằng `client_reference` của operation: việc có được ghi nhận không. Rồi `resume` (leader đi tiếp với điều đã biết) hoặc `close`. Đừng `resume` khi chưa biết, vì leader có thể yêu cầu lại |
| `operation_failed` | Đối tác báo việc kết thúc mà không làm được, và không có sự kiện nào đánh thức leader (`provider_effects.py`) | Xem biên nhận và operation. `resume` để leader báo cư dân và đề xuất cách khác, hoặc `close` |
| `needs_human` | Leader tự kết luận cần người (`CaseFinalize` với `needs_human`), hoặc nói "đã xong" trên các hành động đều thất bại (`decide.py`) | Đọc `unknowns` trong hồ sơ vụ. Người xử lý phần còn thiếu ngoài hệ thống rồi `close`, hoặc bổ sung dữ liệu rồi `resume` |
| `cannot_resolve` | Leader kết luận không giải quyết được (`decide.py`) | Như trên; thường là `close` sau khi người liên hệ cư dân |
| `stalled` | Workflow `accepted`/`active` mà không có gì chạy quá `AWP_CASE_STALL_SECONDS` (900 giây) (`expiry.py`). Request đang chờ được báo thất bại | Xem log (tiến trình có bị treo, model có trả lời không). `resume` |
| `external_timeout` | Chờ sự kiện bên ngoài quá `AWP_REQUEST_TIMEOUT_HOURS` (72 giờ) không có tin (`expiry.py`) | Hỏi đối tác về job (`external_job_id`, `client_reference`). Còn chờ được thì `resume`; không còn gì để chờ thì `close` |
| `provider_gap` | Sự kiện kiểu `delta` thiếu sự kiện đứng trước quá `AWP_WF_DELTA_HOLD_SECONDS` (3600 giây) (`provider_apply.py`) | Yêu cầu backend đối tác gửi lại sự kiện bị thiếu (cùng `external_event_id`). Xem `GET /platform/v1/wf/receipts?workflow_id=…` |

Hai trạng thái gần giống nhưng **không** xử lý bằng `resolve` (lệnh đó trả 409 nếu workflow không ở `needs_attention`):

- `blocked_authorization` (route bị đình chỉ) và `blocked_route_changed` (route bị thay): workflow giữ route cũ. Xem `docs/WORKFORCE_V1_HUONG_DAN_KET_NOI.md` mục 3. Cách đưa một workflow ra khỏi hai trạng thái này chưa được kiểm trong bước B4.
- Biên nhận sự kiện provider có `ingestion_status = needs_attention` (mã `UNMATCHED_EVENT`: quá `AWP_WF_QUARANTINE_SECONDS` vẫn không nối được operation; `VERSION_CONFLICT`, `VERSION_GAP`, `JOB_CORRELATION_MISMATCH`): xem `GET /platform/v1/wf/receipts?status=needs_attention`, làm việc với backend đối tác. Biên nhận cần người không tự đưa workflow sang `needs_attention`, trừ trường hợp `provider_gap` ở trên.

## 8. Giới hạn hiện tại

- **Nhiều bản sao cần Redis.** Với `AWP_REDIS_URL` (compose đặt sẵn) chạy được nhiều tiến trình API trên một database; đã chạy thật hai. Bỏ `AWP_REDIS_URL` thì chỉ được một tiến trình: tiến trình thứ hai từ chối khởi động, và sau một lần chết đột ngột tiến trình lên lại chờ tối đa 60 giây. Vẫn tính riêng theo từng tiến trình: rate limit theo khóa API, cache danh sách tool của MCP, cờ "vụ đã hết ngân sách".
- **Phục hồi sau khi một bản sao chết mất tới một lease** (60 giây mặc định) cho việc bản sao đó đang làm dở. Một tiến trình *treo* lâu hơn lease mà chưa chết bị coi là đã chết (hiếm; có thể làm một tin bị nói hai lần).
- **Ảnh:** upload qua `/workforce/v1/partner/assets` cần capability và quyền `attach_asset`. MinIO lưu bytes, PostgreSQL lưu metadata; bucket private, link có thời hạn. Chỉ nhận PNG/JPEG/GIF/WebP qua magic bytes; chưa decode/scan malware, chưa tạo thumbnail hay bỏ EXIF.
- **Workspace là volume cục bộ** của một máy: các bản sao phải ở trên cùng máy (hoặc dùng chung một đĩa, chưa kiểm).
- **Không TLS, không cân bằng tải**: cổng chỉ ở `127.0.0.1`; hai bản sao là hai cổng, chia tải là việc của reverse proxy đặt phía trước. Console phải được phục vụ qua HTTPS khi ra khỏi máy phát triển (khóa nằm trong header của mọi lời gọi).
- **Nâng cấp có thời gian ngừng** (migration chạy trước khi API mới lên; nâng cấp lần lượt từng bản sao trên hai phiên bản mã chưa được thử, đừng làm khi bản mới có migration).
- **Dừng khi có luồng SSE mở mất 20 giây** (`AWP_SHUTDOWN_SECONDS`) và ghi một traceback `CancelledError` cho mỗi luồng bị cắt.
- **Pool kết nối**: mỗi tiến trình mở tối đa `2 × (AWP_DB_POOL_SIZE + AWP_DB_MAX_OVERFLOW)` = 40 kết nối (`deploy/.env.example` đặt 10 + 10 để hai bản sao vừa trong `max_connections = 100` mặc định của PostgreSQL).
- Giới hạn theo khóa API: 600 request/phút **trong mỗi tiến trình**; 20 luồng SSE **trên cả fleet** (đếm qua Redis). Body tối đa 256 KiB, một tin nhắn 20.000 ký tự, một lời gọi tool tối đa 9 giây, schema một tool MCP tối đa 32 KiB, approval sống 24 giờ.
- **MCP ở địa chỉ nội bộ bị chặn** (chống SSRF) trừ khi `AWP_MCP_ALLOW_PRIVATE=1`. Profile demo bật biến này vì MCP mẫu nằm trong mạng compose; production để `0`.
- **Dữ liệu sandbox của các lần đánh giá không tự dọn** (`docs/WORKFORCE_V1_VAN_HANH.md` mục 9).
- **Image 606 MB trên đĩa** (129 MB nén): phần lớn là phụ thuộc bắt buộc của AgentScope (numpy, SDK của các nhà cung cấp model, gRPC của OpenTelemetry).
- `core/pyproject.toml` khai `uvicorn` và `cryptography`; bản Docker vẫn dùng dependency lock có hash.
- `docs/openapi.json` ghi `info.version = 2.0.10dev`: đó là phiên bản AgentScope. Phiên bản hợp đồng đối tác nằm ở `schema_version` trong từng request.

## 9. Cái đã chứng minh và cái chưa

**Đã chạy thật trên Docker** (chi tiết, bản ghi nguyên văn và image id ở `platform_VP/deploy/SMOKE_RESULT.md`):

- Image build từ nguồn trong repo với phụ thuộc ghim; `pip check` sạch; chạy bằng user không phải root.
- Từ volume rỗng: PostgreSQL tạo hai database, job `migrate` đưa cả hai lịch sử migration lên mới nhất và `--check` qua, API lên với `AWP_AUTO_CREATE=0`. 17,8 giây cho cả stack; riêng API 3,2 giây.
- `smoke.py` (B4): 21/21 bước qua HTTP, gồm đánh giá thật trong sandbox, phát hành qua cổng, kho tool tự phát hiện từ MCP, hành động cần cư dân đồng ý, sự kiện provider có chữ ký (chữ ký sai bị 401), idempotency của request, quyết định và sự kiện, đóng bởi đối tác.
- Giết tiến trình API bằng SIGKILL hai lần giữa một workflow (lúc chờ cư dân đồng ý, lúc chờ đối tác): workflow tiếp tục đúng trạng thái, MCP mẫu được gọi đúng một lần, không sự kiện hay tin nhắn nào lặp.
- **P5b, image `0.2.0`, Redis đã nối, hai bản sao** (mục 10 của `SMOKE_RESULT.md`): `smoke.py` 22/22 bước (thêm bước console) qua bản sao 1 trong khi luồng SSE đọc từ bản sao 2; một bản sao bị `docker kill -s KILL` **ngay trong lời gọi đối tác đã được cư dân duyệt** và không lên lại, workflow đi hết qua bản sao còn lại, đối tác giữ đúng một job, không tin hay sự kiện nào lặp. Chạy cả hai chiều (giết bản đang chạy lượt; giết bản giữ job).
- Tắt êm bằng SIGTERM, có và không có luồng SSE mở.
- Ba lệnh sao lưu ở mục 5.

**Đã chứng minh bằng bộ test của repo, không phải trên Docker**: `docs/WORKFORCE_V1_KIEM_THU_TUAN_THU.md` (12 dòng của hợp đồng 13.9 và 13 ý của 14.3; model kịch bản, MCP giả, SQLite một tiến trình; tài liệu đó tự ghi rõ là bằng chứng mô phỏng). Từ P5b có thêm **bộ test giết tiến trình thật** (18 test, marker `multiproc`: platform chạy thành hai hoặc ba tiến trình HĐH trên PostgreSQL và Redis, một tiến trình bị `TerminateProcess`/`SIGKILL` giữa lời gọi model, trong lời gọi đối tác trước và sau khi đối tác trả lời, khi đang đỗ trên approval, sau khi agent nhận quyết định, giữa commit event và giao SSE, khi đang chờ provider) và hai kịch bản có tên của chủ dự án (M5 booking có kiểm soát, M7 ticket nhiều lượt) chạy cả một tiến trình lẫn fleet. Số liệu: `docs/WORKFORCE_V1_QUYET_DINH.md`, mục P5b.

**Chưa chứng minh:**

- **Model thật.** Mọi "leader" trong smoke và trong bộ test là kịch bản. Chưa biết model thật có gọi đúng tool, có xin đồng ý, có nói đúng tiếng Việt, tốn bao nhiêu. `smoke.py` chạy được với model thật (bỏ `--demo`, khai model trong `deploy/models.yaml`) nhưng **chưa ai chạy**, và các kiểm tra của nó viết cho câu trả lời kịch bản nên có thể đỏ với model thật dù hệ thống đúng.
- **MCP thật và backend thật của đối tác.** Chỉ có server mẫu ba tool.
- **Hạ tầng production**: TLS, reverse proxy, giám sát, cảnh báo, tải, nhiều máy, PostgreSQL được quản lý, giới hạn tài nguyên container.
- **Hơn hai bản sao, nhiều máy, mất Redis hay PostgreSQL giữa chừng**: chưa thử.
- **Giết giữa một lời gọi model** hoặc **giữa commit và giao SSE** trên container thật: chỉ có trong bộ test giết tiến trình (tiến trình thật, không phải container). Trên Docker mới giết ở một điểm (trong lời gọi đã duyệt). Giết đúng giữa một giao dịch database đang ghi: chưa thử ở đâu.
- **Khôi phục từ bản sao lưu, nâng cấp, rollback, xoay khóa** trên stack Docker: có quy trình viết ở trên, chưa diễn tập.
- **Tải**: smoke chạy từng workflow một.

## 10. Cho người tích hợp phía đối tác

Đối tác chỉ gọi `/workforce/v1` và không cần biết gì về Docker. Thứ tự làm việc:

1. Người vận hành platform tạo client, khóa, manager, route và khai MCP server của đối tác (`docs/WORKFORCE_V1_HUONG_DAN_KET_NOI.md` mục 1 đến 5), rồi giao cho đối tác: địa chỉ platform, khóa `dp_<id>.<secret>` (hiện một lần), `route_id` và `revision` của route, và nếu có sự kiện tiến độ thì khóa API cùng khóa ký của provider.
2. Đối tác xác nhận route: `POST /workforce/v1/partner/routes/{route_id}/confirm`. Route chưa xác nhận trả `403 ROUTE_NOT_AUTHORIZED` cho mọi request.
3. Gửi `start_workflow`, đọc `workflow_state` và `next_action`, làm theo: `submit_reply`, `submit_approval`, `watch_events` (SSE), `confirm_close`. Bảng đầy đủ ở hướng dẫn nối mục 6; lỗi thường gặp ở mục 7.
4. Backend nghiệp vụ gửi sự kiện có chữ ký HMAC tới `POST /workforce/v1/provider/job-events` (mẫu mã ở hướng dẫn nối mục 5).

Tài liệu để viết mã: hợp đồng `docs/contract/CONTRACT_TICH_HOP_DOI_TAC.md` (chuẩn), mô tả máy đọc được `docs/openapi.json` (xuất từ container; phần đối tác là 11 đường dẫn dưới `/workforce`), và `platform_VP/deploy/smoke.py`: một client mẫu chỉ dùng thư viện chuẩn của Python, đi đủ một workflow (các hàm `start`, `sse`, `approve`, `provider_post`, `close`). Khi hợp đồng và `openapi.json` khác nhau thì hợp đồng đúng.

Điều đối tác phải tự bảo đảm (platform không làm thay được): tool hành động của MCP phải **idempotent theo `client_reference`**; gửi lại sự kiện phải giữ nguyên `external_event_id` và nội dung; đồng hồ lệch không quá 5 phút khi ký.

## 11. Thay đổi mã ứng dụng của bước B4

Một thay đổi, trong `platform_VP/core/src/awp/__main__.py`: `uvicorn.run(...)` nhận thêm `timeout_graceful_shutdown` (biến `AWP_SHUTDOWN_SECONDS`, mặc định 20). Thiếu nó, một luồng SSE đang mở làm SIGTERM không bao giờ tắt xong và container bị giết sau thời gian chờ (đo được: 45,6 giây rồi SIGKILL). Không sửa tệp nào khác của ứng dụng; `core/pyproject.toml` không đổi.

## 12. Tệp của gói triển khai

| Tệp | Việc |
|---|---|
| `platform_VP/Dockerfile`, `platform_VP/.dockerignore` | Image |
| `platform_VP/deploy/compose.yml` | Các dịch vụ (Redis đã nối; `api2` ở profile `two`) |
| `platform_VP/deploy/.env.example`, `init_env.py` | Biến môi trường và sinh bí mật |
| `platform_VP/deploy/requirements.in`, `requirements.lock` | Phụ thuộc trực tiếp và bản ghim (cách sinh lại ở đầu tệp lock) |
| `platform_VP/deploy/models.demo.yaml`, `demo/fake_model.py`, `demo/fake_mcp.py` | Profile demo |
| `platform_VP/deploy/smoke.py`, `SMOKE_RESULT.md` | Script khói (`--sse-base`, `--failover-to`, `--kill` cho hai bản sao) và kết quả các lần chạy 12/10/2026 |
| `docs/openapi.json` | OpenAPI xuất từ container |

## 13. Tài liệu liên quan

- `docs/WORKFORCE_V1_VAN_HANH.md`: biến môi trường, migration, bí mật, vòng quét nền, retention, đánh giá và phát hành agent, console.
- `docs/WORKFORCE_V1_HUONG_DAN_KET_NOI.md`: nối một đối tác từng bước.
- `docs/contract/CONTRACT_TICH_HOP_DOI_TAC.md`: hợp đồng với đối tác.
- `docs/WORKFORCE_V1_KIEM_THU_TUAN_THU.md`: kiểm thử tuân thủ hợp đồng (mô phỏng).
- `docs/MVP_DAC_TA_BO_SUNG.md` mục 8: đặc tả của bước này. `docs/WORKFORCE_V1_QUYET_DINH.md`: các quyết định.
- `platform_VP/deploy/SMOKE_RESULT.md`: kết quả chạy thật trên Docker.
