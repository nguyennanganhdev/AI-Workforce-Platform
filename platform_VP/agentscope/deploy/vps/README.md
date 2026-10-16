# Platform VPS: phát hành, backup và khôi phục

Phạm vi: `platform_VP/agentscope` trên develop2. Nghiệm thu phiếu thật do người
vận hành thực hiện sau deploy. Smoke hạ tầng không thay thế nghiệm thu đó.

## Gói phát hành

- Build app/web từ cùng checkout, gắn tag phát hành cố định bằng `APP_IMAGE` và
  `WEB_IMAGE`; lưu base commit, diff/hash và image ID. Không dùng `latest` cho VPS.
- Build web với `VITE_API_BASE_URL=/api`. Nginx trong web chuyển `/api/` về app,
  hỗ trợ SSE không buffer, refresh cookie, upload và download. Client giữ prefix
  `/api` cả khi gọi upload ngoài API client. URL backend riêng vẫn dùng được.
- `.dockerignore` loại `.artifacts`, runtime workspace, env, access/secret files
  và archive khỏi app image. Context web có ignore riêng.
- Gói chỉ chứa image archive, compose, scripts, runbook và manifest; không chứa
  dữ liệu local hoặc secret. Tạo `.env` riêng tại VPS với quyền `600`.

## Cấu hình VPS

Copy `.env.example` sang `.env`, tạo các secret độc lập. Lưu các tệp env/script
dạng UTF-8 không BOM, xuống dòng LF khi dùng với Bash. Cấu hình:

```dotenv
COMPOSE_PROJECT_NAME=awp-platform
APP_IMAGE=agentscope-platform:<release>
WEB_IMAGE=agentscope-platform-web:<release>
BIND_HOST=127.0.0.1
AGENTSCOPE_PORT=8000
WEB_PORT=5173
POSTGRES_PORT=5442
REDIS_PORT=6390
MINIO_API_PORT=9200
MINIO_CONSOLE_PORT=9201
PUBLIC_ORIGIN=https://<platform-domain>
WEB_API_BASE_URL=/api
AUTH_COOKIE_SECURE=true
S3_PUBLIC_ENDPOINT=https://<s3-domain>
WORKFORCE_PARTNER_API=true
```

`AGENTSCOPE_SQL_URL` phải dùng đúng password của PostgreSQL. Dùng
`nginx.conf.example` cho TLS proxy; thay domain/certificate, kiểm tra `nginx -t`
rồi mới reload. S3 dùng hostname riêng, không đổi prefix đường dẫn của presigned
URL. Không mở PostgreSQL/Redis/MinIO console/API app ra Internet.

```bash
docker load -i images.tar
docker compose -f compose.yaml -f compose.vps.yaml config --quiet
docker compose -f compose.yaml -f compose.vps.yaml up -d --no-build
```

Nếu Vinhome cùng máy, thêm `-f compose.partner-network.yaml` và đặt đúng
`PARTNER_DOCKER_NETWORK`, `PARTNER_PLATFORM_ALIAS`; nếu khác máy, cấu hình URL
HTTPS và token hợp lệ giữa hai VPS, không dùng DNS Docker `api`/`awp-platform`.
Onboard bằng declaration của đối tác, xác nhận route và kiểm tra kết nối hai chiều.
Không copy toàn bộ DB local để khởi động lại các workflow thử cũ.

Với hai VPS triển khai ngày 16/10/2026:

- Platform: `https://vagen-platform.duckdns.org`, IP `103.238.234.172`.
- S3: `https://s3.vagen-platform.duckdns.org` (cùng VPS platform).
- MCP Vinhome: `https://vinhome-platform.duckdns.org/mcp`, IP `103.238.235.156`.
- Operator onboard từ ngoài máy dùng `--platform https://vagen-platform.duckdns.org/api`;
  `--partner-url https://vagen-platform.duckdns.org` giữ contract `/workforce/v1`.
- Declaration cần `mcp_grants.vinhomes.path=/api/business/platform/mcp-grants`
  khi đi qua gateway HTTPS Vinhome; giữ `ticket_input` và `ticket_title_fields` mới.
- `local-management` và `SIM-TECH-OPERATOR` tới BQL Ocean Park 1;
  `SIM-OP2-OPERATOR` tới BQL Ocean Park 2; `SIM-OP3-OPERATOR` tới BQL Ocean Park 3.
- Settings trong database Vinhome có ưu tiên hơn env. Lưu cấu hình bằng service
  `platform_settings`, xác nhận từng route rồi bật kết nối; không chỉ đổi env.
  Kiểm tra `worker_version` đã bằng `version`, customer/provider key được chấp nhận.
- Database Vinhome đang dùng là `vinhomes_release_20261015_6884e1b1`, tenant
  `11111111-1111-5111-a111-111111111111`. Xác minh lại URL database trong container
  trước khi vận hành; database mặc định của container PostgreSQL có thể khác.

Trong chế độ truy cập IP bằng HTTP, cần đặt `PUBLIC_ORIGIN=http://<ip>` và
`AUTH_COOKIE_SECURE=false`; đây chưa phải cấu hình HTTPS hoàn chỉnh. Khi bật TLS,
đổi các origin/S3/cookie đồng bộ. Web `/api` không cần build lại theo domain.

## Backup nhất quán, có gián đoạn ngắn

Entrypoint hiện tại lưu dữ liệu qua bốn kho:

| Kho | Dữ liệu cần giữ |
| --- | --- |
| PostgreSQL | Auth/RBAC, route, workflow/job, public event, shared context |
| Redis | Agent, credential, MCP/skill, session/message, AOF/RDB |
| MinIO | Tài liệu, ảnh và object đã tải lên |
| Workspace volume | Workspace agent và Qdrant trên đĩa |

Script dừng app để chặn ghi, dump PostgreSQL, dừng Redis/MinIO rồi archive
volume. Trap khởi động lại các service vốn chạy kể cả khi backup lỗi. Chạy trong
khung bảo trì và kiểm tra health sau khi hoàn thành. Không chạy đồng thời với
onboarding, migration hoặc một tiến trình khác ghi trực tiếp vào các kho này.

```bash
cd /opt/awp-platform/app
bash deploy/vps/backup.sh awp-platform /var/backups/awp-platform
# Nếu đang dùng cùng-host partner overlay:
COMPOSE_FILES=compose.yaml:compose.vps.yaml:compose.partner-network.yaml \
  bash deploy/vps/backup.sh awp-platform /var/backups/awp-platform
bash deploy/vps/verify-restore.sh /var/backups/awp-platform/<backup>
```

Backup chỉ hợp lệ khi có `COMPLETE` và toàn bộ `SHA256SUMS` khớp. Thư mục có
quyền `700`, file `600`, chứa secret: chỉ root đọc, không đưa vào Git/image hay
public download. Giữ thêm bản mã hóa ngoài VPS. Rehearsal dùng volume/container
tạm có prefix riêng, không publish cổng và `--network none`; không chạy app/model.
Script đối chiếu migration và số user/workflow/request, khởi động Redis/MinIO từ
dữ liệu phục hồi, giải nén workspace, rồi xóa đúng tài nguyên tạm vừa tạo.
Trên VPS có cấu hình tiêu chuẩn, backup còn giữ release manifest, Nginx và
`/etc/letsencrypt` để khôi phục cấu hình TLS (bao gồm private key, không public).

## Khôi phục sự cố

1. Dừng nhận traffic và dừng app/worker trước khi thao tác dữ liệu. Giữ một backup
   của trạng thái hiện tại; không ghi đè volume nguồn trong lúc diễn tập.
2. Xác minh checksum và chạy `verify-restore.sh` trên backup chọn phục hồi. Bảo đảm
   image ID được lưu vẫn có trên host (`docker load` archive phát hành nếu cần).
3. Tạo project/volume mới trống. Khôi phục `runtime.env` với quyền `600`, dùng
   image tag/ID của backup, đổi project/port và không bật partner network/traffic.
4. Restore `postgres.dump` bằng `pg_restore --exit-on-error --no-owner
   --no-privileges` vào database trống. Giải nén `redis.tar.gz`, `minio.tar.gz`,
   `workspaces.tar.gz` vào đúng ba volume mới khi các service tương ứng đang dừng.
   Không dùng `docker compose down -v` trên project cũ.
5. Kiểm tra Alembic head khớp manifest (`0017_unified_partner_case` ở bản này),
   user/workflow/request count, Redis, bucket/object và Qdrant/workspace.
6. Chỉ bật app khi đã đối chiếu các job/ticket chưa kết thúc với đối tác để tránh
   phát lại side effect. Smoke đăng nhập/refresh/upload/SSE; chuyển traffic và
   nối lại partner, sau đó người vận hành nghiệm thu phiếu thật.

## Rollback và kiểm tra sau deploy

- Trước mỗi lần nâng cấp: backup đủ bốn kho, lưu env/compose và image ID bản cũ.
- Migration chạy tự động khi app khởi động. Không downgrade/xóa dữ liệu tùy tiện.
  Chỉ quay image cũ khi tương thích schema mới; nếu không, phục hồi backup trên
  project mới và chuyển traffic sau khi kiểm tra. Giữ nguyên workflow/protocol pin.
- Xác minh image ID, `/api/health`, HTML và JS thực sự đang phục vụ qua HTTPS;
  đăng nhập/refresh/logout, upload/download/presigned URL và SSE qua proxy.
- Kiểm tra route, MCP xác thực, model credential và phiên bản declaration. Chạy
  một backup + restore rehearsal trên chính VPS, rồi lập lịch hàng ngày ngoài
  giờ sử dụng. Cảnh báo khi backup/health thất bại và theo dõi dung lượng đĩa.
- Để dùng lịch 03:30 giờ Việt Nam: copy `awp-platform-backup.service` và `.timer`
  vào `/etc/systemd/system/`, chạy `systemctl daemon-reload` rồi `systemctl enable
  --now awp-platform-backup.timer`. Nếu có partner overlay, đặt
  `COMPOSE_FILES=compose.yaml:compose.vps.yaml:compose.partner-network.yaml` trong
  `/etc/awp-platform-backup.env` (quyền `600`). Xem kết quả bằng `systemctl status
  awp-platform-backup.service` và `journalctl -u awp-platform-backup.service`.
  Backup không tự xóa bản cũ; kiểm tra dung lượng và chuyển bản mã hóa ra ngoài
  VPS theo chính sách lưu trữ của người vận hành.
- Chỉ ghi `DEPLOYED` sau khi smoke VPS đạt. Ghi riêng `USER_UAT_PENDING` cho
  phiếu thật chưa nghiệm thu; không coi test tự động là model/partner UAT.


## Tài khoản và phạm vi vận hành

- Quản trị Platform: `platform.admin` / `admin@accounts.vagen.test`.
- Mỗi domain có một `DOMAIN_ADMIN`; Vinhome dùng `vinhome.admin` /
  `admin@accounts.vinhome.test` để quản trị tài khoản và khu.
- Mỗi khu có một `AREA_MANAGER` nhận ticket: `vinhome.op1.bql`,
  `vinhome.op2.bql`, `vinhome.op3.bql`, email tương ứng
  `op1.bql@accounts.vinhome.test` đến `op3.bql@accounts.vinhome.test`.
  Giữ BQL theo khu vì route, agent và quyền xử lý gắn với UUID/phạm vi khu.
  Đuôi `.test` là định danh đăng nhập nội bộ, không phải hộp thư.
- Tên/email mới khi seed lấy từ `scripts/workforce/seed_platform_data.py`.
  Seed không tự đổi tài khoản đã tồn tại. Khi chuẩn hóa tài khoản đang chạy,
  backup trước, giữ UUID/role/domain/area, dùng kế hoạch riêng tư với
  `scripts/workforce/normalize_platform_accounts.py --plan <private-plan>`.
  Script chạy bằng môi trường ứng dụng và URL PostgreSQL nội bộ.
- Sau đổi mật khẩu hàng loạt, thu hồi refresh session **và** đổi
  `AUTH_JWT_SECRET` rồi recreate app: access token hiện được xác minh stateless.
  Giữ các khóa tích hợp đối tác; không tạo lại account hoặc route theo tên mới.
- Đăng nhập hiện hành lưu tại `/opt/awp-platform/ACCESS.secret.md` và
  `/opt/awp-platform/admin.secret.env`, quyền `600`; backup tự lưu hai file này
  nếu có. Không đưa kế hoạch, mật khẩu, JWT key vào source hoặc image.
  Dùng bản script operator trên host khi image cũ chưa chứa phiên bản mới.
- BQL đã tạo nhưng chưa nối partner chỉ là cấu hình sẵn. Ghi rõ trạng thái trong
  bàn giao; không coi đó là bằng chứng chạy ticket thật. Không đổi mật khẩu
  nhân viên/cư dân Domain khi chỉ xoay mật khẩu Platform.
