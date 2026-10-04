# Report Agent tools

Nhánh `dev_TeamHoang-HuyHoang` tách từ `dev_TeamHoang` tại `975565a1`; chỉ đưa sang Report tools 2.0.0, test và docs.

Phạm vi hiện tại chỉ gồm bốn tool đọc API backend đã có, bản descriptor `2.0.0`.
Tool không tạo hóa đơn, ghi dữ liệu hay gọi employee-performance/export/repair-revenue.

| Tool | Chức năng | Endpoint hiện có |
| --- | --- | --- |
| `filter_report_scope` | Chọn đúng tòa hoặc toàn phân khu có quyền | `GET /catalogs`, `GET /reports/filter-options` |
| `get_repair_bill_summary` | Đọc đủ hóa đơn issued, kiểm nhóm sửa chữa, cộng grand_total theo currency | Scope APIs; `GET /reports/supporting-records?kind=invoices`; `GET /invoices/{invoice_id}` |
| `get_ticket_frequency_summary` | Tổng ticket và số/tỷ trọng từng loại incident | Scope APIs; `GET /reports/supporting-records?kind=tickets`; `GET /reports/incident-frequency-summary` |
| `get_employee_star_summary` | Phân bố sao và trung bình từ review của nhân viên được chọn | Scope APIs; `GET /reports/employee-feedback` |

## Input và output

Filter nhận `{}` để liệt kê, hoặc `scope_type` + `scope_id`/`name`.
Tên chỉ khớp sau NFC/casefold/chuẩn hóa khoảng trắng; không đoán tên khu.
Nếu tên trùng, trả `REPORT_SCOPE_AMBIGUOUS` với candidates được phép.
Phân khu chỉ hợp lệ khi có quyền mọi tòa active; thiếu một tòa không báo subtotal như toàn khu.

Ba summary nhận `scope_type`, `scope_id`, `from_date`, `to_date` theo YYYY-MM-DD.
Kỳ `[from,to)`, tối đa 3660 ngày. Stars thêm `staff_ids` bắt buộc (1–100 UUID không trùng).
Input strict, cấm field ngoài schema; không nhận cookie/quyền/repair categories do model khai.

Output chung: `outcome`, `operation`, `data`, `sources`, `limitations`.
Summary thêm `scope`, `period`; failure chỉ có `outcome=failure`, `error`, `retryable` và candidates nếu có.
Không có dữ liệu phù hợp sau khi đọc đủ nguồn thì `empty`; không thay lỗi hoặc dữ liệu thiếu bằng 0.

- Bills: `data.basis=issued_repair_invoice_grand_total`, `items` gồm `currency`, `invoice_count`, `billed_amount` là chuỗi Decimal.
- Tickets: `total_ticket_count`, `incident_ticket_count`, `non_incident_ticket_count`, `share_basis=incident_ticket_count`; mỗi item có `incident_type_id` nullable, `incident_type_name`, `ticket_count`, `share` (0..1).
- Stars: `basis=customer_review_submission`, `total_rating_count`, `average_stars` nullable; items có `staff_id`, `staff_name` nullable, `rating_count`, `star_counts` đủ 1..5 và `average_stars` nullable.

Schema đầy đủ: [tool-contracts.json](../docs/teams/hoang/reports/report-agent-PHH/tool-contracts.json).
Input/output/query mẫu đầy đủ: [input-output-examples.json](../docs/teams/hoang/reports/report-agent-PHH/input-output-examples.json).
Ví dụ là dữ liệu test, không phải số liệu kinh doanh.

## Tích hợp runtime

```python
from reporting.application.client import ReportBackend
from reporting.tools import ReportTools, RuntimeContext
from reporting.tools.catalog import tool_descriptors

# All verified_* values are injected by your authenticated runtime,
# not by tool arguments or model output.
backend = ReportBackend("https://your-business-api.example")
tools = ReportTools(backend, RuntimeContext(
    principal_id=verified_user_id,
    allowed_building_ids=tuple(verified_building_ids),
    session_cookie=verified_session_cookie,
    repair_category_ids=tuple(verified_repair_category_ids),
))
descriptors = tool_descriptors()
try:
    result = await tools.get_repair_bill_summary({
        "scope_type": "building", "scope_id": verified_building_ids[0],
        "from_date": "2026-09-01", "to_date": "2026-10-01",
    })
finally:
    await backend.aclose()
```

Runtime phải kiểm `reports:read` và inject context từ phiên xác thực. Cookie BQL được gửi đến backend;
backend kiểm quyền ở mỗi lần gọi. Thiếu nhóm sửa chữa runtime trả `REPORT_REPAIR_CATEGORIES_REQUIRED` trước HTTP.
Danh mục API hiện không có cờ tự phân loại “repair”, nên không hardcode ID hoặc đoán qua tên.

Catalog Python chưa đăng ký vào `FIRST_PARTY_TOOLS` (hiện rỗng) hoặc AgentScope gateway;
owner runtime cần nối descriptor và handler `reporting.<operation>` qua cổng Python.
Phần narrative/layout/template `operations-v1` có sẵn chưa được chuyển sang output của bốn tool này.
34 test narrative chỉ là hồi quy, không phải proof tích hợp tool mới.

## Phân trang và tính số liệu

Supporting records dùng query camelCase `buildingId,fromDate,toDate,kind,limit=100,offset`.
Tool theo `nextOffset` đến hết mọi tòa; kiểm metadata `agentContext` khớp query và ID không trùng.
Invoice detail đọc từng hóa đơn để kiểm identity/status/currency và category của lines.
Chỉ toàn bộ line thuộc repair categories mới cộng **grand_total của danh sách** đúng một lần.
Bill không có sửa chữa bị bỏ qua; bill trộn bị chặn `REPORT_MIXED_INVOICE`, không cộng giá toàn bill.
Không cộng tiền khác currency, không dùng giá line để tính lại bill, không báo số này là thực thu.
Test router thật ghi nhận Decimal ở detail bị serialize thành JSON float làm tròn; tool không dùng tiền detail để tính.
Backend serializer chưa sửa; chưa có snapshot để đối chiếu hai lần đọc.

Ticket summary dùng interval=month, gộp theo incident_type_id qua tháng/category/tòa;
share tính lại trên tổng incident, không cộng share backend. Số totalTickets của frequency API chỉ là incident,
không phải mọi ticket. Mọi ticket được đếm riêng từ supporting records theo created_at.
Nếu incident vượt tổng ticket trả `REPORT_SOURCE_INCONSISTENT`; non_incident không khẳng định là service_request.

Feedback API không nhận fromDate/toDate; đọc đủ history theo mỗi tòa/staff rồi lọc submitted_at theo UTC.
Sao phải nguyên 1..5, average là weighted theo số lượt, HALF_UP 2dp; không lượt thì null, không phải 0 sao.
Không tự lọc người thiếu công việc; tên thiếu là null. Chỉ gồm staff_ids đã chọn, không có xếp hạng/SLA/rework.

## Hạn chế và lỗi

Hóa đơn lọc issued_at, ticket lọc created_at theo timezone DB/session chưa được API công bố;
period.timezone=null. Sao lọc UTC và period.timezone=UTC. Không có input timezone giả làm backend đã áp dụng.
Danh mục tòa/phân khu là membership hiện tại; nhiều API/trang chưa có snapshot nhất quán hoặc lineage đầy đủ từng KPI.

Client HTTPS (hoặc HTTP loopback), không follow redirect. GET retry tối đa 2 lần cho transport/502/503/504.
Một operation mặc định tối đa 60 giây **gồm toàn bộ scope, page, detail, retry và backoff**;
request timeout 15 giây. max_pages=100 cho từng luồng, max_records=10000 ID cho toàn operation.
Chạm cap/deadline hoặc một nguồn lỗi trả failure, không trả phần đã đọc như báo cáo đủ.
Cancellation truyền lên runtime; raw HTTP body và cookie không xuất hiện trong lỗi.

Đánh giá thẳng: chưa nghiệm thu database/auth/RLS thật, chưa wiring runtime, chưa load test;
N+1 detail và feedback history có thể vượt budget. Chưa xử lý bill trộn, timezone thống nhất hay snapshot.

## Backend dependency của nhánh Hoàng

Base `dev_TeamHoang` hiện chưa chứa `services/vinhomes-api`. Production tool vẫn gọi backend được triển khai
qua `base_url`; việc push nhánh này không tạo backend hoặc nối gateway thật.
Các API đã đối chiếu thuộc `dev_TeamChien` tại `9ecd1437`.

Test `test_existing_routes.py` cần source backend trong checkout bên ngoài. Trước khi chạy đủ suite, thiết lập:

```powershell
$env:REPORT_SOURCE_REPO = 'F:/AI-Workforce-Platform-dev_TeamChien-report-agent'
```

Đường dẫn phải trỏ tới checkout chứa `services/vinhomes-api/src`; thay bằng đường dẫn trên máy bạn.
Nếu thiếu source backend, bốn ca router không thể chạy. Không skip chúng hoặc gọi suite đã đầy đủ.
173 test trên nhánh Hoàng đã chạy với backend source bên ngoài, SQL/auth giả lập; 34 narrative regression chạy trên source nhánh Hoàng.
Chi tiết nguồn test trong `evidence/final-results.json` và [BRANCH_HANDOFF.md](../docs/teams/hoang/reports/report-agent-PHH/BRANCH_HANDOFF.md).

## Kiểm thử

```powershell
python -m pip install -r agent-report/requirements-tools-test.txt
python -B -m pytest -q -p no:cacheprovider server/tests/reporting/tools
python -B -m pytest -q -p no:cacheprovider server/tests/reporting/narrative
python -B -m ruff check --no-cache --select E,F,I,UP,B,PIE --ignore E501 server/src/reporting/tools server/src/reporting/application server/src/reporting/metrics server/tests/reporting/tools
python -B -m ruff format --no-cache --check server/src/reporting/tools server/src/reporting/application server/src/reporting/metrics server/tests/reporting/tools
```

04/10/2026: 173 tool PASS (169 HTTP fake + 4 router thật/SQL-auth fake), 34 narrative regression PASS;
0 fail/error/skip. Coverage phạm vi tools/application/metrics: statement 91,20%; branch 80,99%; combined 88,46%.
Không coi test local hoặc router với fake SQL là proof PostgreSQL, SSO, RLS hoặc production.

Báo cáo chi tiết: [PROGRESS_REPORT.md](../docs/teams/hoang/reports/report-agent-PHH/PROGRESS_REPORT.md).
Fail và sửa: [FAILURE_HISTORY.md](../docs/teams/hoang/reports/report-agent-PHH/FAILURE_HISTORY.md).
Bằng chứng machine-readable: `evidence/final-results.json`, `failure-history.json`, `coverage-summary.json` trong cùng thư mục báo cáo.
Các wrapper/tài liệu nghiệm thu cũ đã được thay hoặc xóa; không dùng kết quả 256 ca cũ để nghiệm thu bản 2.0.0.
