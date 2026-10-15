# OP2: dữ liệu Docker/VPS và tuyến Platform

Kiểm tra ngày 15/10/2026, Asia/Saigon. Phạm vi là mở rộng **mô phỏng OP2**, không công nhận hồ sơ vận hành thật.

## Ảnh hưởng của cleanup

Docker Domain chính và VPS vẫn dùng API image `data-release-20261015-6884e1b1`, schema đến 0023. Cleanup/0024 trên nhánh chưa rollout vào image/DB đang chạy. Không reset database, thay env, admin, provider key hoặc volume. `/`, `/login`, `/api/business/ready` trả 200 trên local và HTTPS VPS; các container Domain có healthcheck đều healthy.

Hai mock container thuộc stack cũ `awp-platform-fake-mcp/model` hiện restart vì thiếu `/demo/fake_*.py`; không nằm trong stack `awp-develop2` đang test. Không tự phục hồi Platform cũ sau yêu cầu gỡ source. Nhãn Compose cũ trên PostgreSQL còn trỏ checkout cũ; các thao tác recreate phải dùng Compose/env hiện tại tại `vinhome_Recident/deploy` và đúng project `vinhomes-domain`.

## Trước khi bổ sung

Hai môi trường có 12 account (2 admin, 2 cư dân, 8 staff), 2 căn/cư trú, 24 ca, 44 dịch vụ (10 bật), 334 tài liệu/818 chunk. Căn/cư trú/staff/dịch vụ bật đều thuộc OP1. OP2/3 có danh mục tham chiếu công khai, chưa có người/căn hoặc dịch vụ được bật.

Local chỉ xác nhận tuyến `SIM-TECH-OPERATOR` về `quanly.demo@example.com`. Account Platform `bql.ocean-park-2@example.com` thuộc `ocean-park-2` đã verified membership nhưng chưa có tuyến đối tác. Vì vậy gửi từ cư dân OP1 không vào hàng đợi OP2.

VPS có bridge database override `enabled=false`, URL rỗng, không có route xác nhận. Container healthy không chứng minh VPS đang gửi được sang Platform.

## Đã bổ sung và kiểm tra

Thêm **699 bản ghi mỗi môi trường** từ template mô phỏng sạch, gồm 30 account (6 cư dân, 24 staff), 3 tòa/6 căn, 336 ca, 10 dịch vụ, 20 SOP và dữ liệu thẻ/khách/công nợ/tiện ích/cải tạo. Xem [bộ OP2](../../deploy/owner-data-pilot/op2-simulation/README.md).

| Nhóm | Trước | Sau, mỗi môi trường |
|---|---:|---:|
| Account / admin | 12 / 2 | 42 / 2 |
| Căn / cư trú | 2 / 2 | 8 / 8 |
| Staff / ca trực | 8 / 24 | 32 / 360 |
| Dịch vụ / dịch vụ bật | 44 / 10 | 54 / 20 |
| Tài liệu / chunk | 334 / 818 | 354 / 838 |
| Xe / thẻ / khách | 2 / 4 / 2 | 8 / 16 / 8 |
| Chứng từ công nợ | 4 | 16 |
| Tiện ích / booking | 2 / 2 | 4 / 8 |
| Hồ sơ cải tạo / yêu cầu dịch vụ | 2 / 2 | 8 / 8 |
| Travel mock products | 15 | 15 |

Ca OP2 có tám người đồng thời; mỗi nhóm kỹ thuật/an ninh/vệ sinh/hỗ trợ có hai người. Cả tám chuyên môn category được phủ ở thời điểm kiểm tra. Lịch đợt này kết thúc **29/10/2026 07:00 Asia/Saigon**; cần cấp lịch mới sau đó, không kéo dài ca nhân sự thật bằng fixture.

Đã backup trước nạp, kiểm tra archive, clone database để nghiệm thu, rồi nạp transaction giữ FK/RLS/transition. Replay trên clone/local/VPS đều không sinh bản ghi mới hoặc đổi mật khẩu. So fingerprint cấu hình tích hợp trước/sau import bằng nhau; xác nhận tuyến local là thao tác riêng sau import. Không tạo ticket/workflow mới.

Kiểm tra HTTP trên clone, Docker chính và VPS: **30/30 account đăng nhập và gọi API đúng quyền**, sáu cư dân gọi **36 API dữ liệu căn** thành công; đọc công nợ căn khác và danh sách account admin bị chặn. Bốn test builder/guard/roster/scoping đạt; Ruff source đạt. Không gọi Reception/Agent/provider/embedding.

Tra cứu trực tiếp bằng runtime role: **14 truy vấn mỗi môi trường** cho audience cư dân/staff, có dấu/không dấu và các nhóm dịch vụ đều có kết quả đúng site OP2. Chỉ mục gồm tiêu đề, nội dung và dạng bỏ dấu giống pipeline tri thức chính; không đổi embedding. Tất cả hit giữ provenance tham khảo, không nâng thành tài liệu operator phê duyệt.

Log, backup, bundle và credential riêng: `E:\Vinhomes-Deploy\domain-runtime-audit-20261015`; VPS: `/opt/vinhomes/releases/op2-simulation-20261015`. Credential dùng thử nằm ở file ignored `deploy/runtime-access-20261015/accounts-op2.secret.json` và `.txt`, không đưa vào PR.

## Đăng nhập và tuyến OP2

| Thành phần | Dùng gì |
|---|---|
| Domain để test với Platform local | `http://localhost:8080/login` |
| Cư dân OP2 | `resident1.c1@op2-sandbox.test` hoặc 5 account cư dân OP2 còn lại |
| Staff kỹ thuật | `technician1.c1/c2/c3@op2-sandbox.test`, chọn đúng ca |
| Platform local | `http://localhost:5173` |
| BQL nhận OP2 | `bql.ocean-park-2@example.com` |
| External management ref | `SIM-OP2-OPERATOR` |
| Route xác nhận | `4bc3bf77-a692-4a33-9f14-103d1a3251cc`, active, revision 2 |

Platform gọi MCP local qua mạng Docker dùng `http://api:8000/mcp`. Discovery 16 tool; tuyến OP2 được khai báo 9 tool: 7 điều phối và 2 đọc ngữ cảnh/availability. Không tự mở Travel hoặc thao tác cấp thẻ, thanh toán/xóa nợ, booking/cải tạo qua MCP. Platform dùng grant đúng ticket/workflow, không dùng bootstrap token làm quyền thực thi.

Tuyến OP1 được giữ nguyên. Account Domain không phải account BQL trên Platform: Domain bàn giao ngữ cảnh người gửi, còn route/quyền xác định BQL nhận. Chưa gửi ticket mới để tránh tự chạy Agent trong khi người dùng test; route active và dữ liệu/API đạt chưa phải nghiệm thu Agent thật.

## Giới hạn còn lại

- VPS đã có account/data OP2 và login HTTPS đạt, nhưng bridge vẫn tắt. Muốn VPS gửi sang Platform cần endpoint Platform mà VPS truy cập được, client/key/route riêng và MCP trỏ đúng VPS. Không dùng URL Docker local cho VPS.
- OP1 có khoảng trống ca ở thời điểm kiểm tra; OP3 vẫn chưa có account/căn/staff/dịch vụ bật. Chưa mở rộng các phần đó trong đợt OP2 này.
- Toàn bộ 354 tài liệu vẫn `unverified=true` về vận hành; nguồn công khai và dữ liệu mô phỏng không thay phê duyệt operator. 20 chunk mới tra cứu full text, không gọi embedding provider.
- Cần master địa bàn/căn thực tế; hồ sơ cư trú được phép sử dụng; danh sách nhân sự/phạm vi/ca/dự phòng; bảng phí/VAT/giờ/bảo hành/đặt-hủy; đầu mối khẩn cấp; SOP/SLA có phiên bản/hiệu lực và người xác nhận.
- Travel là mock. Thẻ/khách/công nợ/tiện ích/cải tạo có dữ liệu và API/UI, không đồng nghĩa toàn bộ hành động được cấp sang Platform.
