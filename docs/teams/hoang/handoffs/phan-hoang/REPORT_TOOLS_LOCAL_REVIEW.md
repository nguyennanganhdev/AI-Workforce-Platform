# Report Agent — bản local để kiểm tra

Ngày: 03/10/2026. Ghi chú checkout local; nhánh bàn giao `codex/report-agent-PHH`.

## Vị trí và nguồn

- Checkout riêng: `F:\AI-Workforce-Platform-dev_TeamChien-report-agent`.
- Nguồn GitHub: `origin/dev_TeamChien` tại `9ecd1437b8c9629f51e68886e6dc17bc3da7e77e`.
- Nhánh làm việc ban đầu: `codex/report-agent-tools`; nhánh bàn giao: `codex/report-agent-PHH`.
- Không sửa checkout `F:\AI-Workforce-Platform` hoặc bản Team Hoàng hiện có.

## Đã làm

8 tool Python cho bộ lọc, hiệu suất nhân viên, phản hồi, doanh thu sửa chữa,
tần suất sự cố, bản ghi đối chiếu, tạo export và xem trạng thái. Tool gọi đúng
HTTP API đang có trên nhánh Chiến, không thêm backend hoặc truy cập database.

- Input cấm field ngoài schema, kiểm kỳ/ngày/timezone/UUID/phân trang.
- Runtime inject cookie và building grants; model không tự khai danh tính/quyền.
- Backend kiểm lại quyền mỗi lần gọi, kể cả status/download sau khi thu hồi quyền.
- Tỷ lệ được tính bằng code, mẫu số rỗng là null, số tiền không mất precision.
- Dữ liệu rỗng khác lỗi HTTP; thiếu provenance được ghi rõ, không bịa snapshot/as_of.
- GET retry có giới hạn; POST không tự retry. Giữ key khi timeout chưa rõ kết quả.
- Export từ chối định dạng, report kind hoặc category filter chưa được API hỗ trợ.
- Catalog có JSON Schema và metadata để owner runtime đăng ký 8 handler.

## File để đọc

| Vị trí | Nội dung |
| --- | --- |
| `agent-report/README.md` | Hướng dẫn dùng và giới hạn |
| `server/src/reporting/tools/contracts.py` | Input/context/errors |
| `server/src/reporting/tools/catalog.py` | 8 descriptor cho builder/runtime |
| `server/src/reporting/tools/facade.py` | Tool wrapper/mapping/output |
| `server/src/reporting/application/client.py` | HTTP/auth/retry/error handling |
| `server/src/reporting/metrics/normalize.py` | Kiểm tra KPI/Decimal/tỷ lệ |
| `server/tests/reporting/tools/` | Contract và route integration tests |
| `agent-report/requirements-tools*.txt` | Dependencies riêng; không đổi root lockfile |

## Kết quả xác minh

`222` bài test tool đều đạt, gồm gọi cả 8 route FastAPI thật với SQL result boundary
giả và kiểm vòng đời export có lưu receipt. Chạy chung với `34` bài narrative hiện có: **256 passed**. Ruff check,
Ruff format check và kiểm tra whitespace trực tiếp trên các file mới đều đạt.
Ở lần đo ban đầu, file còn untracked nên `git diff --check` riêng chưa xác minh chúng; staged diff được kiểm trước commit. Bộ test mới không bị skip.

Các ca chính: giả scope/SQL/URL/cookie bị chặn trước HTTP; hai BQL giữ riêng
cookie và grants; backend thu hồi quyền; đồng bộ đúng query alias; số Decimal
thật được FastAPI serialize; mẫu số 0; dữ liệu rỗng; tổng ticket không khớp;
retry có giới hạn; key giữ nguyên; export timeout/5xx/decode lỗi không tạo retry
tự động; không nhận URL tải ngoài backend; cancellation truyền lên runtime.

Để chạy lại trên máy hiện tại, mở PowerShell trong checkout riêng:

```powershell
$env:PYTHONPATH = '.codex-artifacts\report-python'
$env:PYTEST_DISABLE_PLUGIN_AUTOLOAD = '1'
& 'C:\Users\hoang\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe' -B -m pytest -q -p no:cacheprovider server/tests/reporting/tools server/tests/reporting/narrative
& 'C:\Users\hoang\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe' -B -m ruff check --no-cache server/src/reporting/tools server/src/reporting/application server/src/reporting/metrics server/tests/reporting/tools
& 'C:\Users\hoang\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe' -B -m ruff format --no-cache --check server/src/reporting/tools server/src/reporting/application server/src/reporting/metrics server/tests/reporting/tools
```

Môi trường kiểm thử chỉ nằm trong `.codex-artifacts/report-python` (git ignored).
Máy khác cài `agent-report/requirements-tools-test.txt` và dùng Python >= 3.11.

## Giới hạn và tích hợp tiếp

Chưa chạy PostgreSQL/SSO/AgentScope deployment thật. SQL và quyền trong database
không được chứng minh bằng mock. Các module này sẵn cho runtime inject backend
và authenticated context; chưa sửa registry/entrypoint chung của Chiến/Đông.

Backend còn thiếu snapshot, as_of, metric version và timezone thống kê. API
feedback chưa lọc kỳ; supporting records chưa tạo lineage đầy đủ. Doanh thu
theo hóa đơn issued, không theo ngày hoàn thành; thực thu là các phân bổ xác nhận
trước cuối kỳ, không phải cashflow chỉ trong kỳ. Export chỉ DOCX đồng bộ cho
incident frequency toàn tòa hoặc giá trị hóa đơn issued theo category; chưa
xuất hiệu suất nhân viên/thực thu. Template/narrative cũ chưa tương thích với
ba nhóm báo cáo mới; cần tích hợp consumer theo contract mới, không relabel.

Bản ZIP review trong `.codex-artifacts/Report-Agent-Review.zip` chỉ chứa file mới
của thay đổi này, không chứa repository đầy đủ, dependencies hoặc credential.


## Đánh giá sau test mở rộng

Xem [REPORT_TOOLS_TEST_ASSESSMENT.md](REPORT_TOOLS_TEST_ASSESSMENT.md): lưu cả
log FAIL trước sửa, lỗi phát sinh trong quá trình sửa, coverage và giới hạn chưa
chứng minh. 96 test trước đây chưa đủ để phát hiện các lỗi mới; kết quả hiện tại
không xác nhận production-ready.

Báo cáo tiến độ và evidence trong Git nằm tại
[PROGRESS_REPORT.md](../../reports/report-agent-PHH/PROGRESS_REPORT.md).
