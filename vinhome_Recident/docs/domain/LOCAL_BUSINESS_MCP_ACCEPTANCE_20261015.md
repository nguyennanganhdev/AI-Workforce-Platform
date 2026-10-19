# Nghiệm thu Domain local đa nghiệp vụ/MCP — 15/10/2026

## Đã thực hiện

1. Tạo bộ dữ liệu mô phỏng đủ cư dân/căn, các nhóm staff/chuyên môn/dự phòng/ca, thẻ/xe/khách, công nợ, tiện ích/booking, hồ sơ cải tạo, danh mục dịch vụ và SOP trong database sandbox riêng.
2. Thêm `vh_service_context` và `vh_amenity_availability`, MCP local tăng từ **14 lên 16 tool**. Tra cứu theo ticket, tái kiểm tra quyền cư trú/công nợ, giới hạn địa bàn, che thông tin không cần thiết.
3. Cho Platform giao An ninh thường theo grant hiện có; An ninh khẩn cấp giữ chuyển cấp. Không thêm role BQL Domain; không mở tool tạo ticket/xác định cư dân hay tác vụ Reception cho Platform.
4. Sửa đường tạo ticket qua biểu mẫu cư dân để tự xếp lệnh handoff khi bridge được bật. Luồng Reception dùng cùng cơ chế idempotent nên không tạo hai start command. Biểu mẫu trực tiếp không đặt cờ BQL-plan.
5. Build/deploy stack Docker local riêng, có web/API/Reception/worker và dữ liệu bền; thêm cookie namespace để bảo toàn đăng nhập các stack local khác. Tách layer dependency API giúp sửa source không tải lại toàn bộ dependencies.

Không thay VPS, stack `vinhomes-domain` cũ hoặc source Platform. Không tự gọi Agent/model/embedding.

## Runtime đã kiểm tra

- Project: `vinhomes-domain-sandbox`; DB `owner_pilot_test_<32 hex>` do env riêng sinh, lấy tên đầy đủ trong private env. Không dùng DB production hoặc sandbox cũ.
- URL web/login: **http://127.0.0.1:8087/login**; admin/staff `/operations/login`; API loopback 8098; Postgres loopback 5567.
- 8 container chạy: PostgreSQL, API, Reception, resident, operations, gateway, scheduler, platform-sync. 6 container có healthcheck đều healthy; hai worker không khai báo healthcheck và có restart count 0 tại nghiệm thu. Init exited thành công.
- API image: `vinhomes-domain-api:business-sandbox-20261015-v1`, ID `sha256:d3f3ae77ce1f94675f8c105b496795d7b4287f476de8fa1c07a50f1e50cc6cb2` tại snapshot nghiệm thu. Source 8 module thay đổi trong container khớp hash checkout. HTML resident và staff/admin qua gateway khớp bytes trong image.
- 11 tài khoản đăng nhập bằng mật khẩu thật qua gateway đạt; các endpoint dữ liệu nghiệp vụ trả 200. Cookie sandbox riêng hoạt động.
- Trang cấu hình kết nối admin có khóa mã hóa riêng, API `/admin/platform-connection` trả 200 và kiểm tra encrypt/decrypt đạt. Chưa bật bridge để gọi session/Agent thật.
- Restart init giữ nguyên 11 credentials và lịch sử; thử validator báo ca đã trôi qua vẫn replay được snapshot đã xác minh, không tự gia hạn ca hay reset mật khẩu. Thay source snapshot bị từ chối.

## Thống kê DB local

| Nhóm | Số lượng |
| --- | ---: |
| Tài khoản | 11: 1 admin, 2 cư dân, 8 staff |
| Cư trú / staff / ca trực | 2 / 8 / 24 |
| Category / coverage | 9 / 11, gồm Travel mock |
| Xe / thẻ / khách | 2 / 4 / 2 |
| Công nợ / dòng phí | 4 / 4 |
| Tiện ích / booking | 2 / 2 |
| Quy định / hồ sơ cải tạo | 1 / 2 |
| Yêu cầu cấp lại thẻ | 2 |
| Dịch vụ / tài liệu / đoạn tri thức | 10 / 71 / 71 |
| Travel mock | 15 sản phẩm |
| Ticket/work order smoke | 1 / 1 tại snapshot |

Hai căn có công nợ mô phỏng khác nhau 160.000 và 270.000 VND để kiểm tra phân quyền. Booking fixture miễn phí; không giả tạo giao dịch thanh toán/biên lai. Các hồ sơ cải tạo submitted, chưa giả lập người có thẩm quyền duyệt thành giấy phép thật.

## Kết quả test

- **200 test hồi quy đạt**, 1 cảnh báo deprecation thư viện, 196,88 giây: 11 module owner/data/schema/knowledge/MCP/Platform tools/bridge. Test dùng DB disposable, Platform HTTP stub và các double, không model thật.
- Sau bổ sung cookie namespace: **6/6 test module mới đạt**, 51,32 giây; năm ca nằm trong bộ 200, một ca cookie bổ sung. Không cộng thành 206 test độc lập.
- Kiểm tra live bằng **MCP SDK bên trong `awp-develop2-app-1`**: tools/list 16; cấp grant qua endpoint backend; đọc billing đúng căn 160.000 VND; ticket khác bị chặn; MCP giao việc trả pending và tạo work order trong Domain. Dùng ticket fixture và one-time backend handover; không bật bridge outbound để tạo session AI thật.
- Public HTTP local `/`, `/login`, `/operations/login`, `/api/business/ready` trả 200. Không chỉ kiểm tra image tag hoặc build thành công.

## Bàn giao và việc còn lại

Hướng dẫn: [SANDBOX_LOCAL.md](../../deploy/SANDBOX_LOCAL.md). Artifact riêng tại `E:\Vinhomes-Deploy\business-sandbox-20261015\`: `accounts.secret.json`, `accounts-list.txt`, `platform-handoff.secret.json`, `mcp-server.secret.json`, `sandbox.secret.env`, `data-inventory.json`, `docker-verification.json`, `live-acceptance.json` và các log riêng. Handoff Platform không chứa mật khẩu DB hoặc key model. File server bootstrap chỉ dùng backend discovery; model cần grant riêng theo ticket.

- Đây là **đủ dữ liệu mô phỏng để kiểm thử các nhóm nghiệp vụ nêu trên**, chưa phải bộ dữ liệu vận hành thật OP1/2/3. 108 mục cần owner xác nhận vẫn mở.
- Model key của Reception đã cấu hình theo bản local hiện có, nhưng chưa nghiệm thu hội thoại/Agent; healthcheck không chứng minh chất lượng model hay key còn quota.
- Platform thật chưa được nghiệm thu tạo session/Agent → staff → phản hồi cư dân. Cần cấu hình route `SIM-TECH-OPERATOR`/`travel-mock`, URL/key hai chiều trong admin, backend tự cấp/làm mới grant và chạy bộ câu hỏi do chủ dự án chọn.
- 16 tool đủ xử lý ticket/giao việc, tra cứu CSKH bảy nhóm và Travel mock. Chưa expose tác vụ cấp/hủy thẻ, đăng ký khách, đặt/hủy tiện ích, thanh toán/xóa nợ hoặc duyệt cải tạo qua MCP. Những thao tác này phải giữ quyền/đồng ý/audit; không coi một câu trả lời tra cứu là đã thực hiện giao dịch.
- Stack local dùng file volume, chưa phải gói production có backup/restore drill, HA, quy trình dữ liệu thật hoặc toàn bộ dịch vụ OP1/2/3.
