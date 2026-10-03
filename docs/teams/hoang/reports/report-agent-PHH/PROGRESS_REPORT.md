# Báo cáo tiến độ Report Agent — PHH

Ngày báo cáo: **03/10/2026**. Nhánh bàn giao: **`codex/report-agent-PHH`**.

## 1. Kết quả và phạm vi bàn giao

Đã xây dựng 8 tool Python cho Report Agent, gọi các HTTP API nghiệp vụ hiện có
của nhánh `dev_TeamChien`. Đã bổ sung validation, normalization metric, xử lý
lỗi/retry/deadline, metadata cho builder/runtime và kiểm thử. Đã sửa các lỗi tái
hiện được; kết quả kiểm thử cuối là **256 passed, 0 failed, 0 errors, 0 skipped**.

Phần hoàn thành là **tool wrapper và contract có thể tích hợp thử**. Chưa hoàn
thành một Report Agent chạy xuyên hệ thống: chưa đăng ký gateway/AgentScope,
chưa chạy SSO hoặc PostgreSQL thật, chưa có snapshot provenance đầy đủ, chưa
chuyển template/narrative cũ sang ba nhóm KPI mới. Vì vậy không kết luận
production-ready chỉ từ kết quả test local.

Nguồn phát triển được giữ tại commit
`9ecd1437b8c9629f51e68886e6dc17bc3da7e77e` của `dev_TeamChien`. Checkout riêng:
`F:\AI-Workforce-Platform-dev_TeamChien-report-agent`. Các thay đổi bàn giao nằm
trong `agent-report`, `server/src/reporting`, `server/tests/reporting` và docs
Team Hoàng; không sửa API nghiệp vụ, DB/migration, entrypoint hoặc root lockfile.

## 2. Tiến độ theo đầu việc

| Đầu việc | Trạng thái | Đầu ra / giới hạn |
| --- | --- | --- |
| Lấy source, tách checkout trên ổ F | Hoàn thành | Base commit được ghi rõ; giữ nguyên các checkout trước |
| Khảo sát API Report của Chiến | Hoàn thành | Mapping 8 operation tới đúng route hiện có |
| Input/context/error contract | Hoàn thành ở wrapper | Cấm extra fields; kiểm UUID/kỳ/ngày/timezone/phân trang; runtime inject session/grants |
| Catalog builder/runtime | Có metadata, chưa đăng ký hệ thống | 8 descriptor, input JSON Schema, side effect và handler key; descriptor không cấp quyền |
| HTTP adapter | Hoàn thành ở wrapper | Session cookie từ runtime, fixed routes, bounded read retry, total deadline, lỗi có cấu trúc |
| Metric normalization | Hoàn thành với aggregate API hiện tại | Kiểm thang điểm/count/mẫu số/currency; tỷ lệ bằng code; số tiền giữ Decimal chính xác |
| Export/status | Hoàn thành với API đồng bộ hiện tại | DOCX incident toàn tòa hoặc invoice issued; idempotency key giữ nguyên; không POST retry tự động |
| Kiểm thử và sửa lỗi | Hoàn thành vòng local này | 222 tool cases + 34 narrative cases; 160 tool cases thêm so với bản đầu |
| Tài liệu và bằng chứng trong Git | Hoàn thành trong gói bàn giao | Báo cáo này, lịch sử FAIL và danh sách kết quả cuối có thể xem trực tiếp trên nhánh |
| Gateway/AgentScope, SSO, PostgreSQL, concurrency thật | Chưa thực hiện | Cần kiểm thử tích hợp và dataset expected KPI độc lập trước nghiệm thu vận hành |
| Template/narrative mới, worker, export nhân viên/thực thu | Chưa thực hiện | Không coi template cũ hoặc export issued-revenue là các tính năng này |

## 3. Danh sách tool và cấu trúc code

| Tool | HTTP API | Phạm vi chính |
| --- | --- | --- |
| `get_report_filter_options` | GET `/reports/filter-options` | Building/category/employee IDs backend cho phép; DOCX |
| `get_employee_performance_summary` | GET `/reports/employee-performance` | Tòa + kỳ; cohort ngày tạo phân công, feedback ngày gửi đánh giá |
| `get_employee_feedback_details` | GET `/reports/employee-feedback` | Tòa + staff + phân trang; API hiện chưa lọc kỳ |
| `get_repair_revenue_summary` | GET `/reports/repair-revenue` | Tòa + category + kỳ; billed/collected/outstanding, giữ riêng tiền tệ |
| `get_incident_frequency_summary` | GET `/reports/incident-frequency-summary` | Tòa + kỳ + interval + category tùy chọn; count ticket incident |
| `get_report_supporting_records` | GET `/reports/supporting-records` | Tickets/work_orders/invoices theo kỳ riêng và phân trang |
| `create_report_export` | POST `/reports/exports` | `incident_frequency` hoặc `issued_revenue`, DOCX, key bắt buộc |
| `get_report_export_status` | GET `/reports/exports/{export_id}` | Trạng thái/URL tương đối; backend kiểm owner và quyền hiện tại |

Code chính:

- [contracts.py](../../../../../server/src/reporting/tools/contracts.py): input
  Pydantic strict, context runtime, error result. Context/cookie không nằm trong
  schema mà model được gọi.
- [catalog.py](../../../../../server/src/reporting/tools/catalog.py): descriptor
  phiên bản 1.0.1, permission metadata, fixed handler names.
- [facade.py](../../../../../server/src/reporting/tools/facade.py): public methods,
  query aliases, scope check, response binding, provenance/limitations.
- [client.py](../../../../../server/src/reporting/application/client.py): session
  cookie, HTTP routes, retry/deadline, Decimal JSON decoder, sanitized errors.
- [normalize.py](../../../../../server/src/reporting/metrics/normalize.py): bất
  biến KPI, số tiền, thang điểm, taxonomy group, ratio và missing data.
- [Bộ test](../../../../../server/tests/reporting/tools): HTTP fault injection,
  router FastAPI thật với SQL-result boundary giả, lifecycle export có receipt giả.
- [Hướng dẫn dùng](../../../../../agent-report/README.md) và
  [dependencies kiểm thử](../../../../../agent-report/requirements-tools-test.txt).

## 4. Lịch sử kiểm thử: giữ cả FAIL và PASS

| Mốc | Tổng ca chạy | PASS | FAIL | ERROR / SKIP | Ý nghĩa |
| --- | ---: | ---: | ---: | --- | --- |
| Trước mở rộng | 96 | 96 | 0 | 0 / 0 | 62 tool + 34 narrative; chưa có JUnit snapshot cho lần này trong gói evidence |
| Fault tests lần đầu | 175 | 132 | 43 | 0 / 0 | 8 FAIL là lỗi helper test, không phải lỗi sản phẩm |
| Baseline sửa helper và thêm group cases | 180 | 140 | 40 | 0 / 0 | 40 ca thất bại thuộc nhiều nhóm lỗi; 2 ca là yêu cầu mới cho total-deadline contract |
| Sau nhóm sửa ban đầu | 180 | 180 | 0 | 0 / 0 | Các lỗi baseline được sửa; chưa đủ để phát hiện lỗi tiền JSON number |
| Precision/syntax tiền chạy riêng | 3 | 0 | 3 | 0 / 0 | Không phải toàn bộ suite; các ca khác bị deselect |
| Boundary chạy riêng | 27 | 25 | 2 | 0 / 0 | Bắt JSON lồng sâu và lỗi OverflowError trong validation mới |
| Suite cuối | 256 | 256 | 0 | 0 / 0 | 222 tool cases + 34 narrative cases |

Không cộng các FAIL giữa các mốc thành số lỗi độc lập: nhiều ca cùng root cause,
có ca được chạy lại, và có ca kiểm yêu cầu hardening mới. Không dùng skip/xfail
để chuyển lỗi thành PASS. Các số ở những lần có JUnit được trích từ kết quả chạy,
không viết tay để phù hợp với kết luận.

Xem [lịch sử từng test FAIL](FAILURE_HISTORY.md),
[failure-history.json](evidence/failure-history.json) và
[final-results.json](evidence/final-results.json). JSON cuối chứa kết quả từng
test, theo file, để đối chiếu tên case thay vì chỉ đọc tổng số PASS.

### 4.1. Hai thiếu sót của bộ test đầu

1. Test mock idempotency trả cùng ID ở hai lần gọi. Điều này chỉ chứng minh
   wrapper giữ key; không chứng minh logic backend tránh insert trùng. Đã thêm
   test chạy router thật với fake repository lưu request hash/receipt và đếm insert.
2. Test route đầu dùng scope giả admin và fixture tần suất thiếu grouping fields.
   Đã thêm nhánh BQL không phải admin, stale/revoked grants, owner guard và fixture
   đủ ngày/category/incident type; không nới validator để giữ fixture thiếu PASS.

Helper `run_payload` của test fault lần đầu tự thêm metadata khi `agentContext`
bị xóa. 8 case “missing_meta” vì vậy thất bại do chính test. Đã thêm cơ chế gửi
raw payload và chạy lại trước khi ghi baseline 40 FAIL.

**Cách đọc `KeyError: 'error'` trong bảng FAIL:** nhiều test mong một structured
failure nhưng wrapper lại nhận payload sai và trả success. Test truy cập
`result['error']` rồi KeyError. Đây là lỗi assertion do guard thiếu, không phải
bằng chứng wrapper tự văng KeyError trong production.

## 5. Lỗi tìm được, cách sửa và kiểm tra sau sửa

| Nhóm | Trước sửa / phản ví dụ | Cách sửa | Kiểm tra sau sửa |
| --- | --- | --- | --- |
| Operation sai loại | List/dict làm membership lookup văng TypeError | Kiểm loại string trước lookup; operation lạ trả error không gửi HTTP | `test_unknown_operation_is_sanitized_without_http` PASS |
| Điểm ngoài thang | Feedback 0/6, average 0/5.1/999/"6" được nhận | Feedback integer và average trong 1–5, dựa CHECK của ticket_reviews | Các ca feedback/average rating PASS; null khi không có đánh giá vẫn hợp lệ |
| Metric/identity thiếu/sai | Staff ID rỗng/sai UUID; numeric cực lớn; field bắt buộc thiếu | Canonical UUID, count miền bigint, numeric bounds, trường bắt buộc và cohort/mẫu số | Identity, huge numeric, required metric cases PASS; không tự điền 0 |
| Tiền JSON number mất chữ số | `9007199254740993.01` thành `9007199254740994.0` | `parse_float=Decimal` trước float; kết quả JSON-safe giữ chuỗi chính xác | Exact numeric-money case PASS; `json.dumps(..., allow_nan=False)` dùng được |
| Chuỗi tiền sai cú pháp/miền | `1_000`, whitespace, `1e10000` được nhận | Kiểm cú pháp số, giới hạn text/exponent/scale trước format; không round/clamp | Money syntax/range cases PASS; tiền tệ không cộng chung |
| Aggregate doanh thu mâu thuẫn | Outstanding > billed; work count > invoice count; currency sai | Kiểm các bất biến, currency `[A-Z]{3}`, counts; không ép aggregate outstanding bằng hiệu hai tổng | Invariant cases PASS; overpayment cùng invoice chưa trả vẫn PASS |
| Pagination không tiến | Empty page trả lại cursor cũ; short page vẫn báo nextOffset | Cursor kế tiếp chỉ khi page đủ limit; page ngắn kết thúc bằng null | Loop/short page cases bị chặn; full/terminal page cases PASS |
| Filter options sai | Primitive trong categories/employees, ID trùng, format chưa hỗ trợ | Kiểm record ID và uniqueness, grants tòa, chỉ advertise DOCX hiện có | Filter fault cases PASS |
| Metadata sai/mâu thuẫn | facts/missingFields sai shape; facts.status khác result.status; resource khác input | Kiểm shape/type, bind facts tới result và resource tới query | Fault matrix cả 8 route và contradiction cases PASS |
| Export contract thiếu | kind/execution/downloadUrl bị thiếu vẫn được nhận | Kiểm đầy đủ contract synchronous; ready/failed; URL cố định tương đối | Missing status fields/foreign URL/binding cases PASS |
| Frequency group không đủ | Thiếu ngày/category, ngày sai, nhóm trùng, group giả có count 0 | Kiểm group keys, taxonomy IDs, nhãn, ngày và uniqueness; sum count khớp total | Group faults PASS; taxonomy null và tuần bắt đầu trước kỳ vẫn PASS |
| Timeout config/deadline | Bool/string/null không bị reject sạch; chưa có total budget | Validate config và deadline toàn HTTP request/retry/backoff <= 60s; timeout write vẫn unknown | Invalid config, slow transport và deadline-backoff cases PASS |
| JSON quá sâu | RecursionError từ decode hoặc chuyển số thoát boundary | Trả contract error cho ValueError/RecursionError; không retry malformed response | Deep JSON 600/1200-level cases PASS |
| Regression trong quá trình sửa | Validation mới gọi math.isfinite trên int quá lớn gây OverflowError | Kiểm miền trước math.isfinite | Huge-budget regression PASS; không ghi thành lỗi baseline cũ |

Thang điểm được đối chiếu với `ticket_reviews_check_0` trong migration hiện có.
Phần lớn payload sai được chủ động inject để kiểm boundary; đây không phải bằng
chứng database production đã trả chúng. API hiện thường serialize NUMERIC thành
chuỗi; lỗi số JSON cho thấy dạng input được wrapper nhận hỗ trợ chưa được đọc đúng.

Miền decimal hỗ trợ: text tối đa 128 ký tự, adjusted exponent <= 38, scale <= 38.
Ngoài miền trả contract error; không khẳng định bao phủ toàn PostgreSQL NUMERIC.

## 6. Export, quyền và dữ liệu hợp lệ dễ bị chặn nhầm

Các kiểm tra lifecycle dùng router FastAPI thật và fake repository có trạng thái:

- Cùng actor/key/payload: report ID giữ nguyên, insert count là 1.
- Cùng actor/key nhưng đổi payload: 409 conflict, không insert thêm.
- Hai actor dùng cùng key: receipt riêng; actor B không đọc export của A.
- Quyền runtime còn stale nhưng backend không cho tòa: bị từ chối trước query report.
- Thu hồi quyền sau export: status, replay và download bị chặn; không đọc content.
- DOCX của hai kind chứa đúng kind/kỳ; invoice export không giả có collected revenue.
- POST timeout/5xx/decode lỗi: không tự retry, `execution_unknown=true`.
- Cancel sau khi đã gửi POST: CancelledError truyền lên runtime, không retry;
  runtime vẫn phải persist pending/key trước side effect.

Fake repository **không** mô phỏng transaction, advisory lock hoặc RLS. Các ca
trên kiểm logic route/wrapper, chưa chứng minh concurrency và commit thật.

Đã giữ các trường hợp hợp lệ: weekly bucket trước fromDate; taxonomy null;
staff chưa có completed jobs nhưng có feedback cohort khác; tiền tệ tách riêng;
invoice trả dư cùng tồn tại invoice chưa trả. Không ép
`outstanding = max(sum(billed) - sum(collected), 0)` vì backend tính từng invoice.

## 7. Coverage và chất lượng kiểm thử

| Chỉ số | Kết quả | Phạm vi |
| --- | --- | --- |
| Dòng lệnh | 421/437 = 96,34% | Ba module tools/application/metrics |
| Nhánh | 165/178 = 92,70% | Cùng phạm vi |
| Kết hợp | 95,28% | Chỉ số do coverage.py tính |
| Lint/format | PASS | Code/test Python của thay đổi |
| Whitespace | PASS | File mới; kiểm staged diff trước commit |

[coverage-summary.json](evidence/coverage-summary.json) ghi số theo file và
danh sách dòng/nhánh chưa cover. Không loại dòng bằng pragma. Không thêm test
giả chỉ để đạt 100%. Coverage không đo SQL semantics, dataset cohort, quyền DB,
model behavior, tải thật hoặc chất lượng trình bày DOCX.

## 8. Cách chạy lại

Từ repo root, với Python >= 3.11 và môi trường riêng:

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r agent-report/requirements-tools-test.txt
$env:PYTEST_DISABLE_PLUGIN_AUTOLOAD = '1'
.\.venv\Scripts\python.exe -B -m pytest -q -p no:cacheprovider server/tests/reporting/tools server/tests/reporting/narrative
.\.venv\Scripts\python.exe -B -m ruff check --no-cache server/src/reporting/tools server/src/reporting/application server/src/reporting/metrics server/tests/reporting/tools
.\.venv\Scripts\python.exe -B -m ruff format --no-cache --check server/src/reporting/tools server/src/reporting/application server/src/reporting/metrics server/tests/reporting/tools
```

Đo coverage riêng; đặt tên data file khác tên JSON output để không bị nhầm file:

```powershell
$env:COVERAGE_FILE = '.coverage-report-tools'
.\.venv\Scripts\python.exe -B -m coverage run --branch --source=reporting.tools,reporting.application,reporting.metrics -m pytest -q -p no:cacheprovider server/tests/reporting/tools server/tests/reporting/narrative
.\.venv\Scripts\python.exe -B -m coverage report -m
```

Các test chọn trên không cần PostgreSQL/model credentials; transport hoặc SQL
result boundary được fake rõ. Không có fallback production sang fake backend.

## 9. Việc còn lại và điều kiện nghiệm thu tiếp

| Việc còn lại | Bằng chứng cần có trước khi coi hoàn thành |
| --- | --- |
| KPI trên PostgreSQL thật | Dataset expected độc lập; boundary [from,to), timezone, cohort/rework, payment allocations và taxonomy |
| Authorization/SSO/gateway | Hai BQL khác tenant/quyền; context/cookie cùng session; gateway kiểm allowlist/reports:read/write; revoke giữa run/download |
| Snapshot/source lineage | Snapshot ID/as_of/metric_version/watermark thực, nguồn mỗi KPI; không lấy giờ máy thay watermark |
| Export concurrency/persistence | Cạnh tranh cùng key trên DB thật; commit/rollback/recovery; pending key persist trước write/cancel |
| Report Agent consumer | Runtime thực đăng ký handler; config phiên bản; narrative không bịa metric/nguồn và giữ missing-data |
| Export/narrative đầy đủ | Báo cáo nhân viên/thực thu, template ba nhóm KPI, renderer được kiểm bố cục; worker nếu sản phẩm yêu cầu |
| Payload/load/security | Body size/memory limits, đồng thời/network thật, gateway tool grants, injection qua model thật |

Các giới hạn API vẫn còn: feedback chưa lọc kỳ; supporting records chưa chứng
minh mọi source của KPI; revenue theo invoice issued, không phải ngày hoàn thành;
collected là allocations xác nhận trước cuối kỳ, không phải cashflow riêng trong
kỳ; export chỉ đồng bộ DOCX. Output schema catalog còn tổng quát, chưa mô tả đủ
mọi field data. Những điểm này không được đổi thành trạng thái hoàn thành bởi
test mock PASS.
