# Report Agent tools — PHH

Bản này bổ sung 8 Python tools gọi API thật của `dev_TeamChien`; không có SQL,
không tạo API nghiệp vụ mới và không thay entrypoint server/runtime. Được phát triển
trên commit `9ecd1437b8c9629f51e68886e6dc17bc3da7e77e`.

| Tool | API |
| --- | --- |
| `get_report_filter_options` | GET `/reports/filter-options` |
| `get_employee_performance_summary` | GET `/reports/employee-performance` |
| `get_employee_feedback_details` | GET `/reports/employee-feedback` |
| `get_repair_revenue_summary` | GET `/reports/repair-revenue` |
| `get_incident_frequency_summary` | GET `/reports/incident-frequency-summary` |
| `get_report_supporting_records` | GET `/reports/supporting-records` |
| `create_report_export` | POST `/reports/exports` |
| `get_report_export_status` | GET `/reports/exports/{export_id}` |

## Tích hợp Python

Python >= 3.11; cài `requirements-tools.txt`. Thêm `server/src` vào PYTHONPATH.
Runtime tạo context sau khi xác thực người dùng, lấy building grants từ backend
và giữ cookie trong vùng tin cậy. Không lấy context từ message, prompt hay tool input.
Mỗi phiên/người gọi có một `ReportTools`; backend kiểm tra lại quyền ở mọi request.
Không dùng service account admin để thay cookie của BQL.

```python
from reporting.application.client import ReportBackend
from reporting.tools import ReportTools, RuntimeContext
from reporting.tools.catalog import tool_descriptors

backend = ReportBackend("https://your-business-api.example")
tools = ReportTools(backend, RuntimeContext(
    principal_id=verified_user_id,
    allowed_building_ids=tuple(verified_building_ids),
    session_cookie=verified_session_cookie,
))
# Register descriptors + handlers with AgentScope's authenticated tool gateway.
# These descriptors advertise capabilities; they do not grant permissions.
descriptors = tool_descriptors()
result = await tools.get_employee_performance_summary({
    "building_id": verified_building_ids[0],
    "from_date": "2026-09-01", "to_date": "2026-10-01",
    "timezone": "Asia/Ho_Chi_Minh",
})
await backend.aclose()
```

`invoke(operation, arguments)` là boundary chung; tám method tên riêng dùng cùng
validation. Schema từ catalog chỉ chứa input nghiệp vụ, cấm field ngoài schema.
Runtime phải kiểm tra tool grants và inject context riêng. Catalog chưa được nối
vào `FIRST_PARTY_TOOLS`/AgentScope; owner runtime cần đăng ký handler
`reporting.<operation>`. Đây là module Python, không import trực tiếp vào Hono TS.

## Đọc kết quả

- `success`: API trả dữ liệu đúng contract; không đồng nghĩa đã có snapshot đầy đủ.
- `partial`: một số metric nghiệp vụ không có, ví dụ mẫu số SLA bằng 0 hoặc thiếu điểm.
- `empty`: truy vấn thành công với items rỗng; khác `failure`.
- `failure`: lỗi input/quyền/HTTP/contract. Không trả raw HTTP body hoặc credential.
- `missing_data`, `limitations` luôn phải được agent giữ lại khi diễn giải.

Tỷ lệ đúng hạn = `on_time_count / timed_completion_count`, dạng fraction 0..1;
share = ticket nhóm / tổng ticket của filter. Mẫu số rỗng trả null. Số tiền giữ
Decimal dưới dạng chuỗi, không cộng giữa các tiền tệ. Nhân viên dùng cohort ngày
tạo phân công, feedback ngày gửi đánh giá, thời lượng không trừ pause. Doanh thu
dùng hóa đơn issued trong kỳ và phân bổ thanh toán xác nhận trước toDate, không
phải doanh thu theo ngày hoàn thành hay cashflow chỉ trong kỳ.

## Export và giới hạn backend

Export hiện chỉ có DOCX đồng bộ cho `incident_frequency` toàn tòa và
`issued_revenue` theo category; không xuất hiệu suất hoặc thực thu. Tool từ chối
category cho incident export để không âm thầm bỏ filter. Giữ nguyên
`idempotency_key` cho cùng payload khi thử lại; đổi payload cần key mới. POST không
retry tự động. Nếu timeout/5xx/decode lỗi sau POST, `execution_unknown=true`:
chưa biết đã tạo file hay chưa; không báo chắc chắn thất bại hoặc tạo key khác.
GET mặc định retry tối đa 2 lần cho transport/502/503/504; toàn request/retry/backoff có deadline mặc định 60 giây; không retry 401/403/409/422.
Cancellation truyền lên runtime.

Backend chưa trả snapshot/as_of/metric version/timezone thống kê; tool trả null
và ghi hạn chế, không lấy giờ máy làm watermark. Date API là `[fromDate,toDate)`;
timezone yêu cầu được ghi nhận nhưng chưa áp dụng phía DB. Supporting records
có phân trang, chưa chứng minh mọi nguồn của KPI; feedback chưa lọc kỳ.
Template/narrative cũ `operations-v1` còn dùng 4 metric ticket/SLA/assignment/outcome:
không đưa kết quả các tool mới vào template đó như thể cùng contract.

Download URL chỉ là đường dẫn backend tương đối đã kiểm tra; tải bằng session
hiện tại qua `/reports/exports/{id}/content` để backend kiểm lại quyền.
Không đưa cookie vào URL, không tự đọc URL tùy ý từ response.

## Kiểm thử

Cài `agent-report/requirements-tools-test.txt` trước khi chạy. Kiểm thử route
FastAPI dùng router thật của nhánh này với SQL result boundary giả; không chứng
minh SQL trên PostgreSQL hoặc SSO thật.

```powershell
python -B -m pytest -q -p no:cacheprovider server/tests/reporting/tools
python -B -m ruff check server/src/reporting/tools server/src/reporting/application server/src/reporting/metrics server/tests/reporting/tools
```

Tests dùng HTTP mock rõ ràng. Kiểm tra mapping 8 API, scope hai BQL, input giả,
đọc rỗng/lỗi, số liệu bất hợp lệ, precision, retry, idempotency và trạng thái
export. Không tự fallback sang mock khi backend thật lỗi. Chưa xác nhận luồng
AgentScope/SSO/PostgreSQL thật trên môi trường deployment.


## Kiểm thử mở rộng ngày 03/10/2026

222 tool tests + 34 narrative tests: **256 passed, 0 skipped**. Đã sửa các lỗi
boundary, precision JSON number, phân trang, thang điểm, metadata và deadline.
Line coverage 96,34%; branch coverage 92,70%, chỉ trong ba module tool/application/metrics.
Xem `docs/teams/hoang/handoffs/phan-hoang/REPORT_TOOLS_TEST_ASSESSMENT.md` để đọc
các lần FAIL trước sửa, giới hạn còn lại và các kiểm tra chưa có.

Không coi tỷ lệ coverage là bằng chứng KPI/SQL/SSO/AgentScope production đã đúng.
Số tiền được decode bằng Decimal rồi giữ chuỗi; count là integer và tỷ lệ xử lý
dùng số thực. Miền decimal hỗ trợ có giới hạn (128 ký tự; exponent/scale <= 38)
để không mở rộng scientific notation vô hạn. Ngoài miền trả contract error.

## Báo cáo bàn giao

[Báo cáo tiến độ PHH](../docs/teams/hoang/reports/report-agent-PHH/PROGRESS_REPORT.md)
bao gồm tiến độ, từng nhóm lỗi, sửa đổi, kết quả sau sửa và evidence được version hóa.
Nhánh bàn giao: `codex/report-agent-PHH`.
