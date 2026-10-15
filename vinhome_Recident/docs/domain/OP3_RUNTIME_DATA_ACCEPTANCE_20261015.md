# OP3: dữ liệu và kết quả nghiệm thu 15/10/2026

Người dùng chọn bổ sung OP3 và kiểm tra ca OP1. Đợt này thêm **dữ liệu mô phỏng có nhãn**, không công nhận master căn, cư trú, nhân sự hoặc chính sách được operator xác nhận.

## Đã triển khai

- Builder OP2 được mở rộng có tham số site, giữ nguyên API/default và namespace ID OP2. Chỉ chấp nhận OP2/OP3; importer từ chối profile/site không khớp hoặc row trỏ site khác trước khi kết nối database.
- Thêm **699 bản ghi mỗi môi trường**: 3 tòa/6 căn/6 cư dân, 24 staff/336 ca, 10 dịch vụ, 8 coverage, 15 SLA mô phỏng, 20 SOP/20 chunk, xe/thẻ/khách/công nợ/tiện ích/booking/cải tạo/yêu cầu dịch vụ.
- Không tạo admin, ticket, work order, workflow, payment, grant, session hoặc queue mẫu. Dữ liệu/admin/credential của OP1/OP2 được giữ nguyên.
- Sao lưu trước, thử database clone, kiểm tra HTTP với runtime role hạn chế, rồi nạp vào Docker chính và VPS. Replay không tạo trùng hoặc đổi password. Fingerprint cấu hình tích hợp trước/sau import giống nhau.
- Không đổi image hoặc schema đang chạy; dữ liệu nằm trong PostgreSQL volume hiện có. Source builder mới được dùng trong container nạp riêng, không bật seed tự động khi startup.

Template dùng chung và mô tả từng dataset: [OP3 README](../../deploy/owner-data-pilot/op3-simulation/README.md), [manifest](../../deploy/owner-data-pilot/op3-simulation/manifest.json).

## Kiểm thử

| Kiểm tra | Kết quả |
|---|---|
| Builder/namespace/roster/site guard OP2 và OP3 | 10 passed |
| API trên database clone | 30 account đăng nhập, 36 API dữ liệu căn đạt |
| Docker chính | 30 account đăng nhập, 36 API dữ liệu căn đạt |
| VPS HTTPS | 30 account đăng nhập, 36 API dữ liệu căn đạt |
| Truy cập chéo căn / danh sách admin bằng account cư dân | Bị chặn trên cả ba môi trường |
| Tra cứu tri thức cư dân/staff, có dấu/không dấu | 14 truy vấn đạt mỗi runtime, chỉ trả đúng site OP3 |
| Nạp lại / giữ cấu hình tích hợp | Đạt trên clone và hai runtime |
| Ruff source | Đạt |

Tài liệu mới giữ `unverified=true`, `operational_verified=false`; các hit đều provenance tham khảo. Không gọi Reception/Agent/model/embedding hoặc tạo ticket mới để test.

## Tổng dữ liệu sau nạp

Hai runtime có cùng số lượng dữ liệu nền bên dưới; ticket/workflow của từng môi trường vẫn độc lập.

| Nhóm | Docker chính và VPS |
|---|---:|
| Account | 72: 2 admin, 14 cư dân, 56 staff |
| Căn / cư trú | 14 / 14 |
| Ca trực | 696 |
| Dịch vụ / dịch vụ bật | 64 / 30 |
| Tài liệu / chunk | 374 / 858 |
| Xe / thẻ / khách / chứng từ công nợ | 14 / 28 / 14 / 28 |
| Tiện ích / booking | 6 / 14 |
| Hồ sơ cải tạo / yêu cầu dịch vụ | 14 / 14 |
| Travel mock products | 15, giữ nguyên |

OP1 có 2 căn/cư dân, OP2 có 6, OP3 có 6. Mỗi site có 10 dịch vụ mô phỏng bật. Không coi 37 building/28 zone gồm dữ liệu tham chiếu lịch sử và mô phỏng là master địa bàn được operator xác nhận.

## Tài khoản và tuyến OP3

- Domain local: `http://localhost:8080/login`, cư dân `resident1.c1@op3-sandbox.test` hoặc năm cư dân OP3 còn lại.
- VPS: `https://vinhome-platform.duckdns.org/login`, cùng bộ account OP3 mô phỏng.
- Staff kỹ thuật: `technician1.c1/c2/c3@op3-sandbox.test`; c1 07:00–15:00, c2 15:00–23:00, c3 23:00–07:00 Asia/Saigon.
- Platform local: `http://localhost:5173`, BQL `bql.ocean-park-3@example.com`.
- `SIM-OP3-OPERATOR` được xác nhận active, revision 2, route `6a1c2857-1d89-4162-a28a-8755e75cf099`. Các tuyến OP1/OP2 được giữ nguyên.
- Discovery vẫn 16 tool; tuyến OP3 dùng 9 tool gồm 7 điều phối và 2 đọc ngữ cảnh/availability. Không mở thêm tool Travel hoặc mutation thẻ/công nợ/booking/cải tạo.

Credential, bundle, backup, log và snapshot nằm trong thư mục ignored `deploy/runtime-access-20261015/op3`; file người dùng mở để test là `accounts-op3.secret.txt`. Không đưa credential vào Git. VPS giữ artifact riêng tại `/opt/vinhomes/releases/op3-simulation-20261015`.

Bridge VPS vẫn tắt vì chưa có endpoint Platform mà VPS truy cập được. Để test nhận ticket ở Platform local, dùng Domain local; account VPS/data đầy đủ không tự làm VPS nối vào Platform trên máy cá nhân. Không dùng bootstrap MCP token làm quyền thực thi ticket.

## Kết quả kiểm tra ca OP1 và giới hạn

- Tại thời điểm kiểm tra tối 15/10, OP1 có 8 staff nhưng 0 người trong ca. Ca kế tiếp bắt đầu **16/10/2026 13:17 Asia/Saigon**; lịch cuối hiện có kết thúc **17/10/2026 21:17**. Giữ nguyên lịch, không tự kéo staff thành trực 24 giờ. Khi ngoài ca, việc có thể phải xếp hàng.
- OP3 có 8 người đồng thời trong ca, hai người mỗi nhóm kỹ thuật/an ninh/vệ sinh/hỗ trợ. Horizon đợt này kết thúc **29/10/2026 07:00 Asia/Saigon**; đây là lịch test, không thay lịch nghỉ/ca/dự phòng thực tế.
- Cả OP1/2/3 đã có dữ liệu để test các nhóm nghiệp vụ đã nêu, nhưng hồ sơ vận hành thật vẫn thiếu: master căn/lô/phạm vi; cư trú và đồng ý sử dụng dữ liệu; nhân sự/chuyên môn/ca/dự phòng; phí/VAT/giờ/bảo hành/đặt-hủy; đầu mối/SOP/SLA có người xác nhận và hiệu lực.
- Tất cả 374 tài liệu vẫn chưa được operator xác nhận về vận hành. Travel vẫn mock. Route active, login/API và retrieval đạt không chứng minh Agent thật hoặc luồng Platform xử lý công việc đã nghiệm thu.
