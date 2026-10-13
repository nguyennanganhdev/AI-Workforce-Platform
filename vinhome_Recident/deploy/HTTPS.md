# HTTPS với gateway Nginx của domain

Không dùng Caddy. Giữ một lớp gateway tới API, `TRUSTED_PROXY_HOPS=1`. Cần tên miền trỏ đúng VPS và kết nối từ Internet tới cổng 80/443.

## DuckDNS DNS-01

Với `vinhome-platform.duckdns.org`, có thể dùng Certbot trên host với `duckdns-acme-hook.py` khi HTTP-01 không xác minh được. Lưu riêng token tài khoản tại `/etc/vinhomes/duckdns-token.secret`, thư mục0700/file0600, không đưa vào env của API/Agent hoặc Git. Hook chỉ cập nhật TXT, không đổi bản ghi IP; không ghi đè TXT khác đang dùng.

```bash
certbot certonly --manual --preferred-challenges dns --non-interactive \
  --manual-auth-hook 'python3 /opt/vinhomes/deploy/duckdns-acme-hook.py auth' \
  --manual-cleanup-hook 'python3 /opt/vinhomes/deploy/duckdns-acme-hook.py cleanup' \
  --config-dir /srv/vinhomes-tls --work-dir /srv/vinhomes-certbot-work \
  --logs-dir /srv/vinhomes-certbot-logs \
  -d vinhome-platform.duckdns.org --agree-tos --register-unsafely-without-email
```

Certbot lưu hooks để renew. VPS phải truy cập HTTPS DuckDNS API và truy vấn DNS được; chứng chỉ đã cấp không chứng minh tự động gia hạn đã sẵn sàng. Nếu dùng `DUCKDNS_HTTPS_PROXY` qua relay SSH loopback để xử lý tạm sự cố mạng, không lưu relay thành phụ thuộc vận hành. Cần kiểm tra `renew --dry-run` bằng đường mạng trực tiếp trước khi xác nhận gia hạn tự động hoàn chỉnh. Theo dõi hạn chứng chỉ và lỗi timer trong thời gian chờ xử lý kết nối.

## Cấp chứng chỉ trước khi bật TLS

Thực hiện ở root thư mục `vinhome_Recident` trên Linux; giữ env hiện có nếu đã deploy, không tạo lại secret hoặc seed dữ liệu.

1. Tạo `/srv/vinhomes-acme`, `/srv/vinhomes-tls`, `/srv/vinhomes-certbot-work`, `/srv/vinhomes-certbot-logs`. Thư mục chứng chỉ/work/log chỉ root truy cập; webroot phải đọc được bởi Nginx.
2. Khởi động/recreate gateway với `compose.yml` và `compose.tls-bootstrap.yml`; base template phục vụ `/.well-known/acme-challenge/` từ webroot.
3. Đặt một file thử dưới webroot và đọc từ máy ngoài VPS qua HTTP tên miền. Nếu không đọc được, xử lý mạng/DNS trước; không lặp yêu cầu cấp chứng chỉ mù.
4. Dùng Certbot webroot với domain thật, cấu hình email quản trị nếu có. Ví dụ không khai email dưới đây dành cho bootstrap; không gửi email thật từ ứng dụng:

```bash
docker run --rm \
  -v /srv/vinhomes-acme:/var/www/acme \
  -v /srv/vinhomes-tls:/etc/letsencrypt \
  -v /srv/vinhomes-certbot-work:/var/lib/letsencrypt \
  -v /srv/vinhomes-certbot-logs:/var/log/letsencrypt \
  certbot/certbot certonly --webroot -w /var/www/acme \
  -d vinhome-platform.duckdns.org --non-interactive --agree-tos --register-unsafely-without-email
```

## Bật gateway TLS

```bash
python3 deploy/configure-tls.py --domain vinhome-platform.duckdns.org
docker compose --env-file deploy/deployment.env -f deploy/compose.yml -f deploy/compose.tls.yml up -d --no-deps gateway
```

Base gateway cần bind public cổng 80; overlay bổ sung cổng 443. Đặt `VINHOMES_BIND_ADDRESS=0.0.0.0`, `GATEWAY_PORT=80`, `HTTPS_PORT=443` ở VPS nếu dùng Compose gốc. Nếu có override hosting hiện hữu, giữ nguyên binding đó và kiểm tra cấu hình hợp nhất trước khi áp dụng. API/PostgreSQL vẫn bind loopback, MinIO không publish.

TLS template được render từ cùng base template, giữ các location ứng dụng/MCP/upload. HTTP chuyển 308 sang HTTPS, ngoại trừ challenge và `/healthz`. File render là artifact ignored, cần tạo lại khi cập nhật base gateway.

Overlay còn có listener HTTP nội bộ riêng8081, publish **chỉ127.0.0.1** bằng `GATEWAY_PRIVATE_PORT` để giữ SSH tunnel. Nếu VPS đang dùng host8080 cho tunnel, đặt `GATEWAY_PRIVATE_PORT=8080` và bỏ mapping cũ `127.0.0.1:8080:8080` khỏi base compose. PublicHTTP80 vẫn redirect; không dùng Host header để quyết định một request là private. Listener này phục vụ quản trị/MCP qua SSH, không thay HTTPS cho đăng nhập browser khi bật cookieSecure.

Sau khi HTTPS public hoạt động, cập nhật env riêng:

```dotenv
VINHOMES_PUBLIC_URL=https://vinhome-platform.duckdns.org
VINHOMES_ALLOWED_ORIGINS=https://vinhome-platform.duckdns.org
SECURE_COOKIES=1
TRUSTED_PROXY_HOPS=1
```

Recreate API để nhận env. Cập nhật MCP handoff sang `https://vinhome-platform.duckdns.org/mcp`; không thay hoặc in key chỉ để đổi URL. Kiểm tra landing/login, session, cookie Secure, upload và MCP trên HTTPS từ máy ngoài.

## Gia hạn

Chạy `certbot renew` bằng cùng bốn volume trên theo systemd timer/cron hai lần mỗi ngày. Khi renew thành công, chạy `docker exec vinhomes-domain-gateway-1 nginx -t` rồi `nginx -s reload`. Chỉ reload khi kiểm tra cấu hình đạt. Thử `renew --dry-run` sau setup, lưu log riêng và theo dõi hạn chứng chỉ. Không mount Docker socket vào container Certbot.

Nếu dùng Certbot cài trên host (như VPS hiện tại), sau khi cấp chứng chỉ thành công:

```bash
install -m 755 deploy/renew-tls.sh /usr/local/sbin/vinhomes-renew-tls
install -m 644 deploy/vinhomes-tls-renew.service /etc/systemd/system/
install -m 644 deploy/vinhomes-tls-renew.timer /etc/systemd/system/
systemctl daemon-reload
systemctl enable --now vinhomes-tls-renew.timer
```

Script dùng thư mục chứng chỉ `/srv/vinhomes-tls` và deploy hook chỉ reload sau khi có chứng chỉ mới. Chưa cấp được chứng chỉ thì không bật timer như một dấu hiệu HTTPS đã hoàn tất.

Nguồn kỹ thuật: [Nginx HTTPS](https://nginx.org/en/docs/http/configuring_https_servers.html), [Certbot webroot và renewal](https://eff-certbot.readthedocs.io/en/stable/using.html#webroot), [Let's Encrypt challenge types](https://letsencrypt.org/docs/challenge-types/).

Nếu CA không truy cập được challenge dù kiểm tra nội bộ đạt, chưa coi HTTPS hoàn tất. Giữ bản HTTP trước đó và cấu hình cookie phù hợp, báo rõ phần mạng/xác minh còn vướng; không dùng chứng chỉ tự ký để thay nghiệm thu public.
