# Triển khai platform trên cùng VPS với Vinhome

> VPS platform riêng triển khai ngày 16/10/2026: `103.238.234.172`,
> `https://vagen-platform.duckdns.org`. Xem [runbook VPS mới](../../deploy/vps/README.md).
> Vinhome vẫn ở `103.238.235.156`; hai bên kết nối HTTPS. Phần dưới là hướng dẫn
> lịch sử cho bố trí cùng host, không áp dụng nguyên lệnh Docker network cho VPS mới.

Người đọc: người vận hành platform · VPS `103.238.235.156` (Vinhome:
`https://vinhome-platform.duckdns.org`).

> **Trạng thái từ 14/10/2026 16:21: platform đã được gỡ khỏi VPS.** PM quyết
> định VPS chỉ chạy domain Vinhome; platform được test ở máy dev trước (xem
> `HUONG_DAN_TEST_PLATFORM.md` mục 8). Đã làm:
> - `docker compose -p awp-platform down` và xoá image platform;
> - **giữ** volume `awp-platform_*` và `/opt/awp-platform/app` để có thể
>   khôi phục;
> - tắt cầu nối Vinhome bằng `VINHOMES_API_PLATFORM_URL=` (bản trước:
>   `deployment.env.bak-before-platform-removal-20261014`), rồi khởi động lại
>   `api` và `platform-sync`.
>
> Muốn chạy lại trên VPS: `docker load` image mới, `docker compose up -d` trong
> `/opt/awp-platform/app`, đặt lại URL rồi khởi động lại hai service như bước 7.
> Phần dưới đây mô tả cách đã làm ngày 14/10.

## Bố trí

| Thứ | Ở đâu |
|---|---|
| Platform (develop2) | `/opt/awp-platform/app`, compose project `awp-platform`; mọi cổng chỉ mở trên `127.0.0.1` (API 8000, web 5173, Postgres 5442, Redis 6390, MinIO 9200/9201) |
| Vinhome | `/opt/vinhomes`, compose project `vinhomes-domain`, không đổi |
| Nối hai bên | Container `app` của platform tham gia mạng `vinhomes-domain_default` với tên `awp-platform` (`compose.partner-network.yaml`) |
| Vinhome → platform | `http://awp-platform:8000` (biến `VINHOMES_API_PLATFORM_URL`) |
| Platform → MCP Vinhome | `http://api:8000/mcp` (mạng nội bộ, có token Bearer, không qua Internet) |
| Model | OpenAI: `gpt-5.4-mini` (nền), `gpt-5.5` (cao) |

VPS không kéo được image từ Docker Hub: image được build ở máy dev rồi chép lên
(`docker save | gzip`, sau đó `docker load`). PostgreSQL (pgvector), MinIO và
nginx dùng chung image Vinhome đã có.

## Các bước (đã làm ngày 14/10)

1. Chép image lên rồi chạy `docker load < releases/awp-images-<commit>.tar.gz`.
2. `/opt/awp-platform/app` chứa `compose.yaml`, `compose.partner-network.yaml`
   và `.env` (`chmod 600`). `.env` có bí mật sinh riêng cho VPS và key OpenAI;
   `COMPOSE_PROJECT_NAME=awp-platform`,
   `PARTNER_DOCKER_NETWORK=vinhomes-domain_default`,
   `WORKFORCE_PARTNER_API=true`, `BIND_HOST=127.0.0.1`.
3. Chạy:
   ```bash
   docker compose -f compose.yaml -f compose.partner-network.yaml --profile demo up -d --no-build
   ```
4. Tạo tài khoản quản lý demo, credential OpenAI và MCP demo bằng
   `scripts/workforce/bootstrap_demo.py` (chạy trong container `app`).
5. MCP của Vinhome chống DNS-rebinding: Host `api:8000` phải nằm trong danh
   sách cho phép. Thêm `MCP_ALLOWED_HOSTS=api:8000` vào
   `/opt/vinhomes/deploy/deployment.env`. Compose của Vinhome đưa biến này vào
   `VINHOMES_API_MCP_ALLOWED_HOSTS`; đây là cấu hình có sẵn, không sửa code.
   Sau đó khởi động lại `api` như bước 7. Thiếu bước này thì onboarding trả
   `MCP_UNREACHABLE` (421 Invalid Host header).
6. Onboard Vinhome từ bộ khai báo của chính Vinhome
   (`/opt/vinhomes/deploy/platform/vinhomes-declaration.json`) bằng
   `scripts/workforce/onboard_partner.py`. Các tham số:
   - `--mcp-url http://api:8000/mcp`;
   - `--partner-url http://awp-platform:8000`;
   - `--management-refs local-management`;
   - MCP token lấy từ `VINHOMES_API_PLATFORM_MCP_TOKEN` của Vinhome.
7. Dán 5 dòng của `platform.env` vào `/opt/vinhomes/deploy/deployment.env`
   (bản cũ: `deployment.env.bak-awp-20261014`), rồi khởi động lại đúng hai
   service của Vinhome, **giữ đúng tag image đang chạy** (ngày 14/10:
   `staff-mcp-20261014-1d76ea3c`; tag trong `deployment.env` đã cũ):
   ```bash
   cd /opt/vinhomes/deploy
   VINHOMES_API_IMAGE_TAG=<tag đang chạy> docker compose --env-file deployment.env \
     -f compose.yml -f compose.tls.yml up -d --no-deps api platform-sync
   ```
8. Xác nhận route bằng khoá khách hàng, rồi kiểm tra trạng thái:
   ```bash
   docker compose ... exec platform-sync python -m vinhomes_api.platform confirm-routes --route local-management=<route_id>:<revision>
   docker compose ... exec platform-sync python -m vinhomes_api.platform status
   ```

## Vào giao diện platform

Cổng chỉ mở trên VPS. Từ máy mình, mở đường hầm SSH rồi vào
`http://localhost:5173`:

```bash
ssh -i ~/.ssh/vinhomes_vps_103_238_235_156 -N -L 5173:127.0.0.1:5173 -L 8000:127.0.0.1:8000 root@103.238.235.156
```

Tài khoản quản lý demo và các khoá nằm trong
`/opt/awp-platform/ACCESS.secret.md` (`chmod 600`), không commit.

## Đổi khoá, cập nhật, gỡ

- **Đổi khoá Vinhome:** chạy lại `onboard_partner.py` với `--new-keys`, dán lại
  `platform.env`, rồi khởi động lại `api` và `platform-sync` như bước 7.
- **Cập nhật platform:** build image mới ở máy dev, chép lên, `docker load`,
  rồi chạy lại bước 3. Migration chạy tự động.
- **Tắt nối:** để `VINHOMES_API_PLATFORM_URL=` trống trong `deployment.env` rồi
  làm lại bước 7. Cầu nối Vinhome tắt, Lễ tân xử lý như trước.
- **Gỡ platform:** `docker compose ... down` (thêm `-v` nếu muốn xoá dữ liệu).

## Ghi chú ngày 14/10

- 2 liên kết thử cũ (12/10, tài khoản `mock-an`) có workflow nằm trên platform
  thử trước đây. Cầu nối đọc lại chúng mỗi giây và nhận 404, nên đã được đặt
  `platform_links.status='closed'`. Hai phiếu vẫn mở, Lễ tân xử lý như thường.
- Kết quả kiểm tra: route `local-management` **active**; cầu nối **bật**
  (`http://awp-platform:8000`); khoá khách hàng và khoá provider **được chấp
  nhận**.

## Cập nhật 16/10 (develop2 #94, Vinhome #95)

Triển khai lại platform với bản mới:

1. Kéo `develop2` vào `/opt/awp-platform/app`. Thêm vào `.env` các biến mới có
   trong `.env.example`:
   - `OPENAI_CHAT_API=responses`: OpenAI dùng Responses API. Model suy nghĩ
     trả tóm tắt suy nghĩ, hiện thành thinking. Đặt `chat_completions` để quay
     lại Chat Completions.
   - `WORKFORCE_REASONING_EFFORT_LEADER` / `_AGENT` (ví dụ `low`): có tác dụng
     trên Responses API, chỉ với model suy nghĩ.
   - `PARTNER_DOCKER_NETWORK`: tên mạng Docker thật của Vinhome trên VPS
     (`docker network ls`). `PARTNER_PLATFORM_ALIAS`: tên Vinhome gọi platform,
     phải khớp `VINHOMES_API_PLATFORM_URL`.
   - `BIND_HOST=127.0.0.1`: chỉ mở cổng trên máy, đặt reverse proxy phía trước.
2. Build và khởi động:
   `docker compose -f compose.yaml -f compose.partner-network.yaml up -d --build`.
3. Đăng ký lại tuyến Vinhome bằng bản khai báo mới (`ticket_input`,
   `ticket_title_fields`, `leader_brief`), chạy `scripts/workforce/onboard_partner.py`
   như bước 6. Khoá cũ giữ nguyên; lần chạy lại chỉ cập nhật agent, tool, sự kiện
   và cấu hình tuyến.
4. Kiểm tra: `curl http://127.0.0.1:8000/health` trả 200; Vinhome gọi được
   `http://<PARTNER_PLATFORM_ALIAS>:8000/health`; gửi một phiếu thử từ ứng dụng
   cư dân và xem session mới trên trang Leader.

Nếu key OpenAI thuộc tổ chức chưa xác minh, tóm tắt suy nghĩ bị từ chối: platform
tự gọi lại không kèm tóm tắt (log `Reasoning summaries refused`), agent vẫn chạy.

