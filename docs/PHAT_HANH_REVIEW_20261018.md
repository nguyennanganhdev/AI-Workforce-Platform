# Phát hành bản rà soát 18/10/2026

Nhánh `feat/review-plan-20261018` (từ `develop2@89c020c1`). Kế hoạch và trạng thái: `docs/KE_HOACH_RA_SOAT_DOMAIN_PLATFORM_2026-10-18.md`.

Không lượt kiểm thử nào gọi model thật. Chất lượng trả lời do chủ dự án nghiệm thu trên UI.

## Đã triển khai

| Nơi | Thành phần | Image | Trước đó |
|---|---|---|---|
| Platform `vagen-platform.duckdns.org` | app, web | app `agentscope-platform:ff9cf617-review-20261018`, web `agentscope-platform-web:ff9cf617-review-20261018-fix1` | `a185cc2d-leader-boundary-20261018` |
| Domain `vinhome-platform.duckdns.org` | api, scheduler, platform-sync | `vinhomes-domain-api:cce8448e-review-20261018` | `9dd7504f-op2-capabilities-20261017` |
| Domain | reception | `vinhomes-domain-reception:cce8448e-review-20261018` | `fix-reception-assets-20261015-…` |
| Domain | resident | `vinhomes-domain-resident:cce8448e-review-20261018` | `stability-20261016-…` |

**Sửa web ngày 18/10, khoảng 22:10:** image web đầu tiên được build từ Git Bash. Git Bash đổi `VITE_API_BASE_URL=/api` thành `C:/Program Files/Git/api`, nên trang đăng nhập Platform báo "Cannot reach the server". Đã build lại web từ PowerShell với giá trị mặc định `/api` (`agentscope-platform-web:ff9cf617-review-20261018-fix1`) và chỉ đổi service `web`. `.env` trước khi sửa: `env.before-webfix`. Dockerfile web nay từ chối giá trị không bắt đầu bằng `/` hoặc `http(s)://`. Domain không bị ảnh hưởng (đã quét bundle).

Commit `cce8448e` và `ff9cf617` chỉ khác nhau ở phần Platform: kênh Telegram/Zalo và phiên thử Leader. Image Domain không đổi giữa hai commit.

### Cấu hình đã đổi

**Platform `.env`:**
- `WORKFORCE_REASONING_EFFORT_LEADER=medium`
- `WORKFORCE_REASONING_EFFORT_AGENT=low`
- `WORKFORCE_REASONING_EFFORT_BUILDER=medium`
- `WORKFORCE_REASONING_EFFORT_JUDGE=medium`
- `WORKFORCE_MAX_OUTPUT_TOKENS=16384`
- `WORKFORCE_PRICE_CATALOG_FILE=./deploy/vps/model-prices.gpt-6-luna.json`
- `compose.yaml` mới.

**Route Platform:** cả 4 route có thêm trường `Đánh giá của Lễ tân` trong `ticket_input.fields`. Workflow đã mở giữ snapshot cũ; chỉ phiếu mới nhận trường này.

**Domain `deployment.env`:**
- `RECEPTION_MODEL=gpt-6-luna` (Responses API, mặc định cho OpenAI)
- `RECEPTION_REASONING_EFFORT=low`
- `RECEPTION_ASSESSMENT_REASONING_EFFORT=medium`
- `compose.yml` mới.

### Kiểm chứng sau deploy

**Platform:**
- HTTPS `/`, `/api/health`, `/chat/`, `/workforce/leader`, `/workforce/agents`, `/channel` trả 200.
- Webhook của kênh không tồn tại trả 404.
- Env effort và bảng giá đúng trong container. Không có lỗi trong log.
- 3 kênh Discord vẫn có heartbeat.

**Domain:**
- `/`, `/login`, `/api/health`, `/operations/login` trả 200.
- Reception đọc cấu hình `gpt-6-luna responses low medium`. Không có lỗi trong log API, platform-sync và Reception.

## Sao lưu và quay lại

**Sao lưu trước deploy:**
- Platform: `/var/backups/awp-platform/review-ff9cf617-review-20261018/` (PostgreSQL, Redis, MinIO, workspace).
- Bản cũ của `.env`, `compose.yaml`, ảnh image cũ và config route nằm trong `/opt/awp-platform/releases/review-ff9cf617-review-20261018/` (`env.before`, `compose.yaml.before`, `images.before`, `routes.before.json`).
- Domain: bản dump `vinhomes-20261018-214320.dump` trong volume backup.
- Bản cũ của `deployment.env`, `compose.yml` và danh sách image nằm trong `/opt/vinhomes/releases/review-cce8448e-review-20261018/`.

**Quay lại Platform:**
```bash
cd /opt/awp-platform/app
REL=/opt/awp-platform/releases/review-ff9cf617-review-20261018
cp $REL/env.before .env && cp $REL/compose.yaml.before compose.yaml
docker compose -p awp-platform --env-file .env -f compose.yaml -f compose.vps.yaml up -d --no-deps app web
```
Trường route mới không làm hỏng bản cũ, vì bản cũ chỉ đọc các trường nó biết. Nếu cần trả route như cũ, dùng `routes.before.json`.

**Quay lại Domain:**
```bash
cd /opt/vinhomes/deploy
REL=/opt/vinhomes/releases/review-cce8448e-review-20261018
cp $REL/deployment.env.before deployment.env && cp $REL/compose.yml.before compose.yml
docker compose -p vinhomes-domain --env-file deployment.env -f compose.yml -f compose.tls.yml up -d --no-deps api scheduler platform-sync reception resident
```

## Việc nên thử trên UI

1. **Cư dân** (Domain):
   - Báo một sự cố có thiết bị ngoài từ điển cũ (ví dụ "máy hút mùi chảy nước"). Lễ tân không hỏi thừa; hỏi đúng một câu khi thiếu vị trí.
   - Sau khi bàn giao, thẻ tiến độ ghim đầu chat hiện 5 bước và trạng thái "Ban quản lý đang xử lý".
   - Báo giá và đồng ý hiện bằng thẻ mới.
2. **Leader** (Platform):
   - Phiếu mới có dòng "Đánh giá của Lễ tân".
   - Leader suy luận (effort medium) và kiểm tra chéo trước thao tác ghi hoặc báo giá.
   - Tab "Phiên thử" tách khỏi "Phiếu cư dân".
3. **Builder:**
   - Mô tả một agent trùng nghiệp vụ với agent đang có: dàn ý yêu cầu chọn Cập nhật / Dùng lại / Tạo mới.
   - Chốt dàn ý: eval chạy với phiếu giả lập khi chưa có sandbox.
   - Nếu trượt, bấm "Để Builder sửa theo kết quả eval".
4. **Quản lý agent:**
   - Trang mở bằng sơ đồ 3D; kéo agent để sắp xếp; chọn ở danh sách thì node sáng lên.
   - Gỡ agent thì node biến mất. Chi phí $ hiện theo agent.
   - "Hoạt động và chi phí" hiện tổng USD (các lần gọi gpt-6-luna từ 01/10 đã được tính giá).
5. **Kênh:**
   - Tạo kênh Telegram (Bot ID + token từ BotFather) hoặc Zalo OA.
   - Với Zalo, sao chép Webhook URL trong chi tiết kênh dán vào Zalo Developers.
   - DingTalk/Feishu không còn trong danh sách tạo mới.

Chưa nghiệm thu: chất lượng trả lời model; kết nối bot/OA thật; sandbox eval (để giai đoạn sau, theo quyết định ngày 18/10).
