# Sandbox OP1/Kỹ thuật

Bộ dữ liệu này phục vụ lựa chọn của chủ dự án ngày 15/10/2026: tạo dữ liệu mô phỏng đầy đủ trong sandbox để nghiệm thu luồng. **Không phải hồ sơ vận hành Vinhomes xác nhận.** Không thay bộ `owner_candidate`, không nạp người/căn/phí/SLA giả lên VPS.

## Phạm vi và dữ liệu

| Dataset | Số dòng | Nội dung |
| --- | ---: | --- |
| operators | 1 | Đơn vị kỹ thuật mô phỏng, đầu mối nội bộ |
| zones / buildings | 1 / 1 | Phân khu/tòa `SIM`, địa chỉ ghi rõ giả lập |
| units / residents | 2 / 2 | Hai căn, hai cư dân owner/tenant, quan hệ và thời hạn giả lập |
| coverage | 1 | Tuyến OP1/Kỹ thuật, operator và route revision 1 giả lập |
| staff | 2 | Kỹ thuật viên cùng phạm vi, dự phòng cho nhau, tối đa 1 việc/người |
| shifts | 6 | Mỗi người 3 ca, 8 giờ/ca; ca dự phòng trùng cửa sổ ca chính |
| services | 3 | Điện, nước, điều hòa; đủ điều kiện, phí/VAT, giờ, bảo hành, đặt/hủy, đầu mối |
| sops | 6 | Mỗi dịch vụ có SOP cư dân và staff, đủ an toàn/chuyển cấp/SLA/bằng chứng/nghiệm thu |

Tổng **25 dòng nguồn**, 10 CSV, manifest và bằng chứng SHA256. Mỗi bản ghi có trường nguồn/review/hiệu lực nhưng review ghi rõ `SIMULATION-REVIEWER-NOT-OPERATOR`. Các số tiền, VAT giả định, SLA 30/240 phút và bảo hành là tham số kịch bản; không phải chính sách thật.

Hai cư dân được gắn số liên hệ mô phỏng thuộc dải NANPA 555-0100–0199, dùng để đáp ứng ngữ cảnh liên hệ của API bàn giao ticket. [NANPA xác định dải này dành cho số hư cấu, không hoạt động](https://www.nanpa.com/numbering/555-line-numbers). Không dùng số thuê bao Việt Nam tự bịa, không gửi OTP/SMS.

## Tạo sandbox mới

Cần Docker Linux và môi trường Python của `services/vinhomes-api` đã cài dependency. Ví dụ trên máy hiện tại:

```powershell
$python = 'E:\Vinhomes-Deploy\owner-pilot-test-venv\Scripts\python.exe'
& $python vinhome_Recident/deploy/start-owner-sandbox.py --output E:\Vinhomes-Deploy\owner-sandbox-new
& $python E:\Vinhomes-Deploy\owner-sandbox-new\run-api.py
```

Thư mục output phải mới/trống, nằm ngoài repository. Script tạo container/volume PostgreSQL có nhãn `vinhomes.data_mode=synthetic_test`, cổng DB chỉ bind `127.0.0.1`, database `owner_pilot_test_<32 hex>`, runtime role không superuser/BYPASSRLS và API cấu hình loopback `127.0.0.1:8097`. Script thứ nhất chuẩn bị DB; script thứ hai chạy API. Cổng 8097 phải còn trống khi chạy API.

Không sửa URL trong env production. API sandbox không cấu hình Reception, model, embedding, Platform hoặc object storage ngoài. Khi gửi chat mà chưa cấu hình Agent, đây không phải môi trường nghiệm thu chất lượng câu trả lời CSKH.

| File riêng | Mục đích |
| --- | --- |
| `bundle/` | 10 CSV, manifest, nhãn và bằng chứng mô phỏng |
| `accounts.secret.json` | 1 admin, 2 cư dân, 2 staff và mật khẩu ngẫu nhiên |
| `connections.secret.json` | Kết nối owner/runtime, chỉ dùng tại máy sandbox |
| `api.secret.json` | Cấu hình API, key riêng cho sandbox |
| `state.json` | Container/volume/DB/port, không chứa mật khẩu |
| `acceptance-data.json` | Báo cáo kiểm tra dữ liệu và hash |
| `files/` | File upload thử nghiệm của API khi chạy riêng |

API trực tiếp: `http://127.0.0.1:8097/docs`. Script không dựng/cập nhật frontend hiện hành. Tài khoản sandbox không đăng nhập được vào VPS vì nằm ở DB khác.

## Cách nạp và bảo vệ dữ liệu

`vinhomes_api.owner_sandbox.materialize()` chỉ nhận bundle `synthetic_test` đầy đủ, DB loopback đúng tên và database comment `vinhomes-synthetic-sandbox-v1`. DB phải chưa có dữ liệu vận hành. Việc nạp master/quyền/tài khoản/ca/dịch vụ/SOP/SLA và 25 dòng nguồn staging nằm trong cùng transaction; lỗi phải rollback toàn bộ. Chạy lại bị từ chối để bảo toàn mật khẩu và lịch sử.

SOP và bản ghi nguồn giữ `unverified`/`operational_verified=false`; tên hiển thị có `[MÔ PHỎNG]`. Ba dịch vụ chỉ bật trong DB sandbox. Staging owner-only; runtime/MCP không đọc toàn bộ CSV. Route revision và người dự phòng lưu trong snapshot, chưa phải tuyến đã xác nhận với Platform thật hoặc cơ chế tự động ưu tiên người dự phòng cụ thể. Hai staff cùng có chuyên môn/phạm vi/ca nên đủ điều kiện cho bộ điều phối hiện tại.

Importer thật `owner_operational` vẫn chỉ staging; không biến dữ liệu mô phỏng thành hồ sơ thật hoặc publisher production.

## Kiểm thử

`tests/test_owner_sandbox.py` kiểm tra đầy đủ dữ liệu, từ chối sai DB trước kết nối, marker, rollback lỗi muộn, đăng nhập 5 tài khoản, runtime không đọc staging, và happy case thực thi qua Domain API/MCP.

Mặc định cần `RESIDENT_TEST_ADMIN_URL`/`RESIDENT_TEST_RUNTIME_URL` trỏ PostgreSQL local; mỗi lượt tạo rồi xóa DB thử riêng, không seed lịch sử legacy. Có thể nghiệm thu và giữ kết quả trong **sandbox mới, đã materialize**:

```powershell
$env:OWNER_SANDBOX_CONNECTION_FILE = 'E:\Vinhomes-Deploy\owner-sandbox-new\connections.secret.json'
& $python -m pytest vinhome_Recident/services/vinhomes-api/tests/test_owner_sandbox.py -q
Remove-Item Env:\OWNER_SANDBOX_CONNECTION_FILE
```

Chế độ giữ DB có ghi ticket/work order/ảnh/sự kiện vào sandbox này; không dùng để chạy lặp trên DB đã có nghiệm thu. Khi cần chạy lặp, dùng chế độ disposable mặc định hoặc tạo sandbox mới. TestClient sử dụng định danh local cho các bước nghiệp vụ; việc đăng nhập bằng mật khẩu được kiểm tra riêng cho cả 5 tài khoản.

Luồng: API tiếp nhận → ticket → worker bàn giao HTTP tới `FakePlatform` → backend cấp grant workflow/ticket → MCP giao việc → staff nhận ETA/di chuyển/đến nơi/báo giá → Platform giả lập nhận sự kiện → cư dân đồng ý → staff làm/gửi ảnh trước/sau/nghiệm thu → Platform giả lập gửi kết quả → cư dân xác nhận → ticket/workflow đóng. Mock transport kiểm tra nội dung, chữ ký và receipt, không kết nối Platform thật. Không gọi Agent/model/embedding.

## Chuyển sang vận hành thật

Các thiếu hụt thật trong `missing-data.csv` vẫn chờ hồ sơ: operator/phạm vi/địa chỉ/master căn; cư trú và liên hệ được phép dùng; nhân sự/chuyên môn/ca/dự phòng; biểu phí/VAT/giờ/bảo hành/đặt-hủy; SOP/an toàn/chuyển cấp/SLA; route/grant/endpoint đã xác nhận giữa hai backend. Không đánh dấu 108 mục đó là đã được Vinhomes xác nhận chỉ vì sandbox chạy được.
