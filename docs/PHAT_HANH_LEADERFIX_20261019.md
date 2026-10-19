# Phát hành Platform 19/10/2026: key riêng, bảo mật máy chủ, giao diện Leader

Triển khai lúc khoảng 17:10 (giờ VN) lên `vagen-platform.duckdns.org`. Nhánh `fix/leader-key-ui-20261019` (PR #108).

| Thành phần | Image | Commit |
| --- | --- | --- |
| app | `agentscope-platform:41813cd1-leaderfix-20261019` | `41813cd1` (lớp mỏng trên image `0321c727`, chỉ chép 5 file Python) |
| web | `agentscope-platform-web:0321c727-leaderfix-20261019` | `0321c727` (`VITE_VIN_EXPERIENCE_ENABLED=true`, API `/api`) |

Bản trước đó: `40d2383b-develop2-20261019` (app và web).

## Thay đổi chính

- **Key riêng của người dùng:**
  - Được ưu tiên hơn provider nền tảng cho Leader, Builder, thành viên team, agent từ gói và ticket cũ.
  - Không trừ quota token của nền tảng; vẫn giữ giới hạn chạy song song qua lớp quota của nền tảng.
  - Dùng được với mọi provider: OpenAI, Anthropic, Gemini, DeepSeek…
- **Bảo mật:**
  - Bash/Read/Write của workspace local chỉ dành cho quản trị nền tảng.
  - MCP của khách phải là HTTP; MCP kiểu stdio bị từ chối.
  - `base_url`/`host` của key và URL của MCP phải là địa chỉ công khai.
  - Chủ kênh Discord: khách phải tự nhập Discord ID của mình, và ID đó phải là chủ bot.
- **Giao diện Leader:**
  - Thinking, công cụ và trao đổi giữa agent được gom vào dòng "Quá trình xử lý".
  - Chat và Văn phòng hiển thị luân phiên, không cùng lúc.
  - Panel Nhóm có mục "Context và mức sử dụng".
- **Sửa lỗi khác:**
  - Hết quota hiện thông báo rõ ràng.
  - Cài lại gói không còn lỗi 500.
  - Leader cá nhân giữ chỉ dẫn an toàn khi chạy ở chế độ nhóm.
  - Xoá được trường tuỳ chọn của key.
  - Thông báo TeamSay ở chế độ nhóm hướng dẫn đúng cách trả lời khách.

## Gỡ 9 bản sao "Model của platform"

Thực hiện bằng script `remove_platform_key_copies.py` (chế độ `dry`/`apply`; chỉ in số đếm, không in key):
- Catalog `vin-platform-openai` liệt kê thêm `text-embedding-3-small`.
- Cấp quyền `role:AREA_MANAGER` dùng provider nền tảng (view, bind, execute).
- Đặt chính sách quota mặc định cho `role:VIN_USER` và `role:AREA_MANAGER`: 300k token/ngày, model `gpt-6-luna` và `text-embedding-3-small`.
- Trỏ về `vin-platform-openai`: 164 session, 2 kho tri thức, 3 kênh, 1 lịch chạy. Không có xung đột ghi.
- Xoá 9 bản sao. Lần chạy thử sau khi áp dụng không còn bản sao nào.

## Backup và rollback

Các file liên quan:
- Backup (PostgreSQL, Redis, MinIO, workspace): `/var/backups/awp-platform/leaderfix-0321c727-20261019/`.
- Release: `/opt/awp-platform/releases/leaderfix-0321c727-20261019/`, gồm:
  - `deploy.sh`, `deployment.json`, `copy-removal.json`, `images.before`;
  - `private/env.before` và các file compose trước khi đổi.
- Image cũ được gắn tag `awp-rollback/app:before-leaderfix-20261019` và `awp-rollback/web:before-leaderfix-20261019`.

Rollback image:

```sh
REL=/opt/awp-platform/releases/leaderfix-0321c727-20261019
cp $REL/private/env.before /opt/awp-platform/app/.env
cd /opt/awp-platform/app && docker compose -p awp-platform --env-file .env -f compose.yaml -f compose.vps.yaml up -d --no-build --no-deps --pull never app web
```

Việc gỡ bản sao chỉ hoàn tác được bằng cách khôi phục Redis từ bản backup ở trên.

## Kiểm chứng

- **Kiểm tra lúc deploy:**
  - Khoá deploy được giữ.
  - Nhãn revision của image khớp commit.
  - Hash các file trong lớp mỏng khớp.
  - App và web đều healthy.
  - Các route `/`, `/login`, `/register`, `/workforce/leader`, `/credential` và `/api/health` trả về 200, cả nội bộ lẫn qua HTTPS.
  - Bundle web không chứa `Program Files`.
- **Phân giải model (đã kiểm, không gọi model):**
  - Tài khoản tự đăng ký đang có key riêng dùng key đó, model `gpt-4o-mini`.
  - Tài khoản BQL dùng `vin-platform-openai`, model `gpt-6-luna`.
- **Số lần gọi model thật:** 0. Nghiệm thu với model thật do chủ dự án thực hiện trên giao diện.

## Còn mở

- `platform-sync` trên VPS Domain (`103.238.235.156`) gọi `/workforce/v1/partner/.../event-history` bằng một key đối tác không còn hợp lệ, khoảng 2.000 lần trong vài phút, và luôn nhận 401. Cần cấp key đối tác mới và cập nhật cấu hình bên Domain.
- Địa chỉ người dùng nhập chỉ được kiểm khi ghi cấu hình. DNS rebinding hoặc redirect lúc chạy chưa bị chặn.
- Tài khoản bị khoá nhưng có key riêng không còn bị lớp quota chặn. Việc chặn dựa vào phiên đăng nhập.
- Request `/workspace/mcp` lỗi 500 ("cancel scope") khi kết nối tới MCP playwright.
- Kết quả của team chưa tự được học vào memory dài hạn: chế độ nhóm không có cổng xác minh, nên hook học không được gọi. Đây là quyết định thiết kế.
- Component `RoomActivity` không được dùng ở đâu.
