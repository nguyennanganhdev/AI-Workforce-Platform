# Domain local đa nghiệp vụ — dữ liệu mô phỏng

Stack riêng `vinhomes-domain-sandbox`, không ghép với `compose.yml` production. URL hiện tại **http://127.0.0.1:8087/login**; admin/staff dùng cùng cổng đăng nhập và được chuyển theo quyền. Stack local cũ cổng 8080, sandbox API cũ cổng 8097 và VPS là các database khác.

## Tạo mới

Yêu cầu Docker Linux/Compose và Python 3.11+ cho script sinh env. Từ repository:

```powershell
python vinhome_Recident/deploy/new-sandbox-env.py --output E:\Vinhomes-Deploy\business-sandbox-new\sandbox.secret.env
docker compose --env-file E:\Vinhomes-Deploy\business-sandbox-new\sandbox.secret.env -f vinhome_Recident/deploy/compose.sandbox.yml build
docker compose --env-file E:\Vinhomes-Deploy\business-sandbox-new\sandbox.secret.env -f vinhome_Recident/deploy/compose.sandbox.yml up -d --no-build
docker compose --env-file E:\Vinhomes-Deploy\business-sandbox-new\sandbox.secret.env -f vinhome_Recident/deploy/compose.sandbox.yml cp init:/sandbox/accounts.secret.json E:\Vinhomes-Deploy\business-sandbox-new\accounts.secret.json
```

Tạo env bằng chế độ exclusive, không ghi đè secret cũ và không đặt trong Git. Postgres chỉ publish `127.0.0.1:5567`, API `127.0.0.1:8098`, gateway `127.0.0.1:8087`. Nếu đã có project cùng tên thì các lệnh trên quản lý project đó; **không dùng env mới để đổi mật khẩu một volume đã có**. Muốn thêm môi trường độc lập, cần project/port/volume riêng.

Init chạy cùng network namespace với Postgres để giữ guard URL loopback; DB bắt buộc `owner_pilot_test_<32 hex>` và marker `vinhomes-synthetic-sandbox-v1`. Runtime role không có quyền owner và không đọc staging. Chưa có tài khoản thật hoặc dữ liệu thật nào được nhập.

Init tạo bundle OP1/Kỹ thuật, sau đó bổ sung business fixtures trong transaction và seed Travel mock riêng. Chạy lại giữ credentials, ticket, booking và ca đã có. Snapshot CSV đổi sẽ bị từ chối; không cập nhật âm thầm thành bộ hồ sơ mới. Khi ca đã hết, restart vẫn hoạt động nhưng **không tự gia hạn ca**: availability phải phản ánh đúng lịch. Ca thử có 3 ngày, mỗi ngày 8 giờ; refresh dữ liệu mô phỏng cần thao tác riêng có chủ đích.

## Reception

Profile mặc định không gọi model. Muốn chạy Reception, cấu hình riêng trong file secret:

- `SANDBOX_OPENAI_API_KEY` hoặc bộ provider `SANDBOX_MODEL_PROVIDER`, `SANDBOX_MODEL_API_KEY`, `SANDBOX_MODEL_BASE_URL`.
- `SANDBOX_RECEPTION_MODEL`, `SANDBOX_RECEPTION_AGENT` phù hợp runtime.
- `SANDBOX_RECEPTION_URL=http://reception:4202`.

Sau đó chạy thêm `--profile reception` trước `up`. API giữ các service/delegation key riêng do script sinh. Không đưa key provider vào handoff Platform. Trên máy hiện tại đã dùng cấu hình provider của Reception local hiện có, chưa gọi model để nghiệm thu. Healthcheck Reception chỉ chứng minh service sẵn sàng.

## Thành phần và dữ liệu

Postgres, API, scheduler, platform-sync, resident web, staff/admin web, gateway và Reception tùy profile; init chạy một lần rồi thoát. File bằng chứng dùng volume `files`, trạng thái Reception dùng `reception-state`, PostgreSQL dùng `postgres-data`, credentials/bundle dùng `private-data`. Các volume sandbox độc lập với production. Đây là stack local dùng disk volume; chưa phải gói backup/khôi phục hoặc HA production.

| Dataset | Số lượng khởi tạo |
| --- | ---: |
| Tài khoản | 11: admin 1, cư dân 2, staff 8 |
| Staff | Kỹ thuật 2, An ninh 2, Vệ sinh 2, dịch vụ cư dân 2 |
| Căn / cư trú / ca | 2 / 2 / 24 |
| Xe / thẻ / khách | 2 / 4 / 2 |
| Công nợ / dòng phí | 4 / 4; chưa có thanh toán thật |
| Tiện ích / booking | 2 / 2; booking fixture miễn phí |
| Quy định cải tạo / hồ sơ | 1 / 2, hồ sơ đang submitted |
| Yêu cầu cấp lại thẻ | 2, submitted |
| Danh mục dịch vụ / chuyên môn-category | 10 / 9 |
| Tài liệu / đoạn tri thức | 71 / 71, gồm SOP mô phỏng và Travel mock |
| Travel mock | 15 sản phẩm; không đặt chỗ thật |

Tất cả người/căn/ca/phí/VAT/giờ/SLA/quy định là **mô phỏng**, được gắn tên/mã SIM, metadata/marker và provenance. Có source snapshot và transaction guard; không được coi là xác nhận của đơn vị vận hành. Nạp thẻ/khách/đơn/công nợ đi qua chuyển trạng thái hợp lệ, không tắt trigger database.

## Platform và MCP

- Platform chạy Docker dùng `http://host.docker.internal:8087/mcp`; client trên host dùng `http://127.0.0.1:8087/mcp`.
- Control-plane: `POST /api/business/platform/mcp-grants`, chỉ backend giữ token bootstrap. Mỗi workflow gửi `ticket_id`, `external_request_id`, `workflow_id`, `grant_request_id`, danh sách tool và TTL để nhận Bearer riêng. **Không gắn bootstrap token cho model rồi mong thực thi tool được.**
- Model dùng grant đã bind đúng ticket/workflow/management_ref và chỉ những tool backend cho phép. Grant hết hạn/thu hồi/sai ticket bị từ chối.
- Operator pilot là `SIM-TECH-OPERATOR`, tuyến Travel riêng `travel-mock`. Platform cần khai báo route tương ứng; không dùng dữ liệu hồ sơ người/căn/ca để xác định lại cư dân.
- Bridge outbound mặc định tắt. Có thể cấu hình tại UI admin Domain, cung cấp URL/key hai chiều theo contract và bật tuyến sau khi đối soát Platform. Worker đã chạy nhưng không có nghĩa đã tạo session thật.

Env sinh sẵn khóa mã hóa độc lập cho phần cấu hình kết nối ở admin. Không đổi khóa này khi đã lưu credential kết nối. API admin kết nối và cơ chế mã hóa đã được kiểm tra trên stack local hiện tại; không cần sửa source Platform để khám phá MCP.

MCP local có **16 tool**: 14 tool ticket/Travel trước đó và:

| Tool mới | Chức năng |
| --- | --- |
| `vh_service_context(ticket_id, section)` | `cards`, `visitors`, `billing`, `amenities`, `renovation`, `service_requests`, `services`; chỉ ngữ cảnh căn/ticket đang được cấp quyền |
| `vh_amenity_availability(ticket_id, amenity_ref, date)` | Slot của tiện ích trong khu của ticket, không giữ chỗ |

Không xuất QR/điện thoại khách, mask số thẻ, hạn chế form details; công nợ kiểm tra lại quyền owner/tenant hiện tại. Tool tra cứu không tạo ticket/cư trú/booking/thẻ, không trả hồ sơ cá nhân hàng loạt, không thanh toán/xóa nợ/duyệt giấy phép. Các thao tác nhạy cảm bổ sung cần contract xác nhận, version/idempotency và audit riêng trước khi expose.

MCP giao được An ninh thường theo grant/chuyên môn/ca. An ninh khẩn cấp tiếp tục bị chặn giao việc thường để chuyển người điều phối. Quyền Kỹ thuật khẩn cấp theo luồng hiện có được giữ. Không tạo role BQL tại Domain; Platform quản lý session và tiến độ, cư dân giữ quyền đồng ý báo giá/nghiệm thu.

## Kiểm tra và quản lý

```powershell
docker compose --env-file E:\Vinhomes-Deploy\business-sandbox-new\sandbox.secret.env -f vinhome_Recident/deploy/compose.sandbox.yml --profile reception ps
docker compose --env-file E:\Vinhomes-Deploy\business-sandbox-new\sandbox.secret.env -f vinhome_Recident/deploy/compose.sandbox.yml logs --tail 50 api scheduler platform-sync
```

Cookie riêng `vinhomes_session_local_business_sandbox` tránh thay cookie các Domain local khác. Không chạy `down -v` khi muốn giữ dữ liệu. Các file `.secret.*`, log và dump để ngoài Git.

Test backend: cấu hình `RESIDENT_TEST_ADMIN_URL`/`RESIDENT_TEST_RUNTIME_URL` cho Postgres loopback, bỏ `OWNER_SANDBOX_CONNECTION_FILE` khi chạy `tests/test_service_context.py`. Test tự tạo/xóa DB riêng và không chạy Agent/provider.
