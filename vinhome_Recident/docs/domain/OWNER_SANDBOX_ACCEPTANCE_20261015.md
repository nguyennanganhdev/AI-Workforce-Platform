# Nghiệm thu dữ liệu mô phỏng OP1/Kỹ thuật — 15/10/2026

## Kết quả

Đã tạo và nạp bộ mô phỏng đủ sáu nhóm dữ liệu vào PostgreSQL sandbox local riêng. Đã kiểm tra một happy case hoàn thành công việc bằng Domain API/MCP thật và Platform giả lập. Không thay đổi production VPS, không gọi Agent/OpenAI/embedding, không xác nhận thay đơn vị vận hành.

Hướng dẫn tái tạo: [SANDBOX.md](../../deploy/owner-data-pilot/op1-technical/SANDBOX.md). Source: `deploy/prepare-owner-sandbox.py`, `deploy/start-owner-sandbox.py`, `vinhomes_api/owner_sandbox.py`; kiểm thử `tests/test_owner_sandbox.py`.

## Database đã nạp

| Nhóm | Số lượng tại sandbox |
| --- | ---: |
| Site tham khảo từ bootstrap | 3; chỉ OP1 có dữ liệu pilot |
| Đơn vị / phân khu / tòa | 1 / 1 / 1 |
| Căn / cư trú | 2 / 2 |
| Tài khoản | 5: admin 1, cư dân 2, staff kỹ thuật 2 |
| Nhân sự / ca trực / tuyến phạm vi | 2 / 6 / 1 |
| Dịch vụ / SOP mô phỏng / SLA category | 3 / 6 / 1 |
| Batch / dòng nguồn staging | 1 / 25 |
| Ticket / work order sau nghiệm thu | 1 đã đóng / 1 hoàn thành |
| Bằng chứng | 3: trước, sau, xác minh kết quả |
| MCP grant / sự kiện tiến độ | 1 / 9, đều sent tới HTTP stub |
| Role BQL Domain | 0 |

Sandbox hiện tại: `E:\Vinhomes-Deploy\owner-sandbox-final-20261015`. API chạy riêng tại `http://127.0.0.1:8097`, không phải URL frontend/VPS. Mật khẩu chỉ trong `accounts.secret.json`; không đưa vào Git/tài liệu.

## Bằng chứng nghiệm thu

- **94 test đạt, 1 cảnh báo deprecation thư viện, 51,43 giây** trong 8 file: owner sandbox, domain data completion, owner pilot, owner data handoff, owner proposals, MCP v2, knowledge, schema contract. 5 test của module mới nằm trong tổng 94; không cộng hai lần.
- Chạy riêng 5 test trên DB sandbox giữ lại: đạt trong **13,19 giây**. Các DB regression là DB disposable khác và đã được dọn.
- API đang chạy được kiểm tra qua HTTP: `/health`, `/ready`, đăng nhập và endpoint tương ứng cư dân/staff/admin đều **200**.
- Ba ảnh được giữ trong thư mục `files/` riêng của sandbox, đối chiếu SHA256 với DB. Cư dân của ticket đọc cả 3 ảnh qua API đang chạy được **200**; cư dân còn lại nhận **404** cả 3 ảnh. Không để DB giữ lại phụ thuộc thư mục ảnh tạm của pytest.
- Nạp bị từ chối khi target là production hoặc remote; thiếu marker bị từ chối. Lỗi sau khi đã insert admin rollback về 0 người/0 căn. Runtime không superuser/BYPASSRLS và không đọc được hai bảng staging. Chạy nạp lại bị từ chối.
- Happy case tạo ticket từ các operation tiếp nhận, áp dụng SLA `service_request/normal` 30/240 phút; backend cấp grant theo workflow/ticket, MCP `vh_work_order_dispatch` tạo và mời staff trực tiếp, không có bước BQL duyệt ticket.
- Replay cùng lệnh MCP không tạo work order thứ hai; grant không đọc ticket khác. Staff khác không phản hồi assignment của đồng nghiệp. Cư dân khác không đọc hoặc duyệt ticket này.
- Staff nhận với ETA → di chuyển → đến nơi → báo giá mô phỏng 125.000 VND. Cư dân chưa được duyệt khi Platform chưa nhận/publish báo giá; sau đồng bộ mới đồng ý được. Không hoàn thành nếu thiếu ảnh; đủ ảnh trước/sau/xác minh mới gửi kết quả nghiệm thu.
- 9 sự kiện có thứ tự/chữ ký/receipt: `job.offered`, `job.accepted`, `job.en_route`, `job.arrived`, `job.quote_ready`, `job.quote_approved`, `job.started`, `job.completed`, `job.result_published`. Không xuất email hoặc CSV cư trú/nhân sự trong payload tiến độ.
- Domain chưa mở xác nhận hoàn thành trước khi Platform giả lập gửi trạng thái/kết quả. Sau đó cư dân xác nhận, ticket và workflow đóng; replay quyết định trả cùng receipt.

Evidence máy local: `acceptance-data.json`, `acceptance-flow.json`, `regression.private.xml`, `regression.private.log` trong thư mục sandbox. API log và secret không commit.

## Giới hạn

Đây là nghiệm thu dữ liệu và contract nghiệp vụ trên backend Domain, **không phải hai backend production thật hoặc nghiệm thu Agent/UI**. `FakePlatform` là HTTP stub kiểm tra request/sự kiện/chữ ký; không có session Agent thật. API độc lập giữ tắt kết nối Platform/Reception. Không sửa frontend hiện hành hoặc mở quyền MCP toàn tenant.

Phí/VAT/SLA/cư dân/căn/staff/ca đều mô phỏng. Ba dịch vụ và sáu SOP đủ cho pilot OP1/Kỹ thuật, chưa phải danh mục đầy đủ mọi dịch vụ OP1/2/3. **108 mục thiếu hồ sơ thật vẫn chưa đóng**; bộ mô phỏng cho phép kiểm tra sáu nhóm trước khi nhận dữ liệu thực tế.
