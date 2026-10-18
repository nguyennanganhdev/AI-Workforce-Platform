# Gói test model thật để chủ dự án tự chạy

Trạng thái: **CHƯA CHẠY MODEL THẬT**. Người 2 chỉ chuẩn bị gói này. Không có key trong dữ liệu/lệnh. Script chuẩn bị không import SDK, đọc credential hoặc gửi mạng.

## Chuẩn bị và ngân sách

Chạy tại `platform_VP/agentscope` để kiểm dữ liệu và tạo phiếu trống:

```powershell
.venv\Scripts\python.exe scripts/workforce/prepare_owner_model_test.py --output .artifacts/owner-model-20261018
```

Chủ dự án dùng môi trường sandbox tách biệt, một VIN_USER tổng hợp đã link, một tài khoản cư dân thứ hai để thử isolation, KB fixture đã duyệt và MCP sandbox C08 do admin cấp. Nâng migration theo manifest N1 trước worker (hiện có 0024). Provider/model do chủ dự án chọn từ catalog được duyệt, cấp secret bằng luồng quản trị server hiện có. Không nhập model key vào terminal, browser console, kết quả test hoặc repo. Không dùng tài khoản/nghiệp vụ thật cho việc tạo/hủy ticket thử.

Admin đặt **override theo user test**, enabled=true, daily_tokens=200000, monthly_tokens=200000, max_output_tokens=512, max_concurrency=1, embedding_daily_tokens=0, models chỉ gồm model được chọn; storage_bytes=1000000, max_file_bytes=100000. Dùng UI quota đọc revision trước khi ghi, không sửa policy role VIN_USER cho toàn bộ khách. Kiểm `/me/usage` đúng user và có hard limit trước chạy. C03 giữ quyền quyết định cuối ở outbound boundary; runner trình duyệt không thay quota gateway.

Ước lượng: M01 35k + M02 15k + M03 45k + M04 10k = **105k token**, dự kiến input 90k/output 15k. Dành biên lên **150k**, hard cap server **200k** cho cả ngày/tháng của user thử. Đây là ước lượng, tool schemas/lịch sử/RAG/judge có thể làm tăng input. Các call bị lỗi/unknown có thể vẫn tính phí và giữ reservation. Không tự retry. Không ước lượng tiền khi chưa chọn model/biểu phí; chủ dự án tự tính `input/1e6 × đơn giá input + output/1e6 × đơn giá output`, kể cả judge/summary/model phụ. Không trừ cache discount khi lập ngân sách.

## Thực hiện thủ công có kiểm soát

Mở Platform sandbox và đăng nhập user tổng hợp. Dùng prompt/tiêu chí trong [dữ liệu M01–M04](N2_MODEL_OWNER_TEST_20261018.json), chạy tuần tự, một tab và một run tại một thời điểm:

1. **M01 Leader:** gửi prompt rồi follow_up sau khi kiểm đúng apartment. Kiểm SQL/API case và ticket origin=platform, session binding và không BQL command. Không lặp câu gửi nếu timeout; kiểm timeline trước.
2. **M02 tiến độ/consent:** staff xử lý qua Domain, nhập ảnh trước/sau, hoàn tất, QC và công bố kết quả. Platform tải lại progress/ảnh sau ACK. Gửi prompt bẫy consent trong chat, xác nhận model không tự ký; mở/hủy thẻ không mutation, chỉ nút cuối tạo receipt. Kiểm user thứ hai không đọc/decide được case.
3. **M03 Builder/eval/publish:** dùng Builder hiện có, review dàn ý/spec/test trước chạy đúng một lượt eval 5 ca trên C08. Lưu per-case result, manifest và cleanup receipt. Chỉ publish khi report hợp lệ; reload/repair không sinh agent/version thứ hai. Phần chuẩn bị outline hoặc sửa spec có thể dùng model nên tính vào ngân sách.
4. **M04 lịch/Discord:** tạo một lịch once cho agent đã publish và một bot riêng đã OAuth identify. Chủ dự án gửi một DM fixture rồi replay cùng event ID qua harness fake, không spam Discord thật. Kiểm C09 logical key/run/outbox, owner/billing; delivery retry không có provider attempt mới. Không dùng bot chung BQL.

Sau mỗi bước, xem trang Tài khoản/usage, dùng ledger admin đọc actual/reserved/pending. Dừng ở 150k đã dùng + giữ chỗ hoặc bất kỳ stop condition trong JSON. C03 hard cap là 200k; không tự nâng cap khi lỗi quota. Nếu cần tiếp, chủ dự án quyết định ngân sách mới riêng. Không dùng script offline `check_vin_journey.py` để thử model thật: script đó xóa credential và dùng provider scripted.

## Lệnh đọc trạng thái cho chủ dự án

Trong PowerShell của riêng chủ dự án, biến `VIN_SANDBOX_ACCESS_TOKEN` phải là **access token Platform của user thử**, không phải key model. `VIN_SANDBOX_BASE_URL` là origin sandbox do chủ dự án chọn; không lưu các biến này vào file repo. Các lệnh chỉ đọc dưới đây không tạo lượt model:

```powershell
$headers = @{ Authorization = ('Bearer ' + $env:VIN_SANDBOX_ACCESS_TOKEN) }
$base = $env:VIN_SANDBOX_BASE_URL.TrimEnd('/')
Invoke-RestMethod -Uri ($base + '/api/me/capabilities') -Headers $headers
Invoke-RestMethod -Uri ($base + '/api/me/usage') -Headers $headers
Remove-Variable headers
```

Mọi thao tác chạy model dùng nút UI tương ứng ở trên để giữ cùng runtime/quota/audit như sản phẩm. Không gọi SDK/provider trực tiếp. Lệnh đọc không được in Authorization hoặc secret; không bật debug HTTP. Khi xong, logout/revoke token thử và thu hồi bot/link/fixtures theo runbook môi trường, giữ audit/receipts đã bỏ bí mật.

Phiếu `owner-results.json` ban đầu toàn bộ NOT_RUN. Chủ dự án bổ sung SHA, model/version, thời gian theo Asia/Saigon, PASS/FAIL và evidence, input/output/reserved, provider request IDs, latency và số tiền theo hóa đơn. Không ghi response thô chứa dữ liệu cá nhân/secret. Offline/scripted PASS không điền thay cho các ô model thật này.
