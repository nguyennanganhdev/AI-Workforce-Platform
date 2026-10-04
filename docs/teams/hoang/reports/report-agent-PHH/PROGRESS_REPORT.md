# Báo cáo Report Agent PHH

Ngày 04/10/2026 • Bản tool 2.0.0 • Nhánh dev_TeamHoang-HuyHoang

Phạm vi đã thực hiện gồm chọn đúng tòa hoặc phân khu, cộng hóa đơn sửa chữa đã phát hành, tổng hợp ticket và tần suất từng loại sự cố, và tổng hợp đánh giá sao của khách hàng cho nhân viên được chọn. Tool chỉ đọc và tổng hợp dữ liệu backend đã có.

| Tool | Chức năng |
| --- | --- |
| filter_report_scope | Trả tòa hoặc toàn phân khu được phép; chọn theo ID hoặc tên khớp chính xác. |
| get_repair_bill_summary | Đọc đủ hóa đơn trong kỳ; kiểm nhóm sửa chữa rồi cộng grand_total theo từng tiền tệ. |
| get_ticket_frequency_summary | Tổng số ticket và số incident của từng loại; tính tỷ trọng trên số incident. |
| get_employee_star_summary | Đếm lượt đánh giá 1–5 sao, phân bố sao và trung bình cho các nhân viên đã chọn. |

### Kết quả và trạng thái

173/173 test tool đạt; 34/34 test hồi quy phần narrative cũ đạt; không có test skip hoặc xfail. Ruff và kiểm tra định dạng đạt. Kết quả ghi nhận trước commit/push bản 2.0.0. Kết quả test cũ 256 ca không dùng để nghiệm thu phạm vi mới.

169 ca dùng HTTP giả lập. Bốn ca gọi router FastAPI thật từ checkout backend dev_TeamChien, với SQL và xác thực giả lập. Nhánh dev_TeamHoang-HuyHoang chưa chứa backend này. Chưa kiểm chứng PostgreSQL, SSO, RLS hoặc luồng AgentScope chạy thật; catalog Python chưa được đăng ký vào gateway.

### Cách đọc kết quả chung

Input tool là JSON nghiệp vụ; không nhận cookie, quyền tòa hay cấu hình nhóm sửa chữa từ model. Thành công trả outcome, operation, data, sources và limitations; các tool tổng hợp có thêm scope và period. outcome=empty là đọc thành công nhưng không có dữ liệu phù hợp. Lỗi trả outcome=failure, error và retryable; không trả tổng tạm như dữ liệu đầy đủ.

Các ví dụ trong báo cáo là dữ liệu kiểm thử. input-output-examples.json chứa toàn bộ input, output và query API; tool-contracts.json chứa JSON Schema đầy đủ. Không dùng số liệu ví dụ để báo cáo tình hình kinh doanh thực tế.


## Chọn tòa hoặc phân khu

Tool filter_report_scope đọc danh mục hiện tại và các tòa backend cho phép, giao với quyền đã xác thực ở runtime. Kết quả giúp người gọi lấy scope_id hợp lệ cho ba tool tổng hợp.

### Endpoint và input

GET /catalogs trả zones và buildings; GET /reports/filter-options trả buildings và employees được phép. Không cần query cho hai lần đọc này.

| Trường input | Quy tắc |
| --- | --- |
| scope_type | Tùy chọn: building hoặc zone. |
| scope_id | UUID; cần scope_type; dùng ID hoặc name, không dùng đồng thời. |
| name | Tên chính xác, 1–200 ký tự không trống; cần scope_type. |
| {} | Liệt kê các lựa chọn được phép. |

```json
{
  "scope_type": "building",
  "name": "S1.01"
}
```

### Output của ví dụ

```json
{
  "data": [
    {
      "scope_type": "building",
      "scope_id": "11111111-1111-4111-8111-111111111111",
      "scope_name": "S1.01",
      "building_ids": [
        "11111111-1111-4111-8111-111111111111"
      ]
    }
  ],
  "employee_options": [
    {
      "staff_id": "55555555-5555-4555-8555-555555555555",
      "staff_name": "A"
    }
  ]
}
```

Đoạn trên trích các trường nghiệp vụ; envelope đầy đủ và danh sách employee_options nằm trong file ví dụ JSON. Scope gồm scope_type, scope_id, scope_name, building_ids. Employee options không chứng minh mỗi người thuộc mọi tòa trong danh sách.

### Quy tắc chống chọn sai phạm vi

Tên được chuẩn hóa Unicode NFC, chữ hoa/thường và khoảng trắng; không dùng fuzzy match. “sepharin” hoặc “Zurich” chỉ hợp lệ nếu backend thật có đúng tên đó. Tên trùng trả REPORT_SCOPE_AMBIGUOUS kèm lựa chọn được phép. Chỉ cho chọn toàn phân khu khi được phép đọc tất cả tòa active trong phân khu; có quyền một phần thì trả REPORT_SCOPE_INCOMPLETE. Membership là hiện tại, chưa phản ánh lịch sử.


## Tổng hợp hóa đơn sửa chữa

Tool get_repair_bill_summary dùng hóa đơn đã có, không tạo hóa đơn và không tính lại giá từ dòng dịch vụ. Tổng giá cần thanh toán được lấy từ grand_total của danh sách hóa đơn issued trong kỳ; kết quả không đại diện tiền khách đã thực trả.

### Input

```json
{
  "scope_type": "zone",
  "scope_id": "33333333-3333-4333-8333-333333333333",
  "from_date": "2026-09-01",
  "to_date": "2026-10-01"
}
```

scope_type là building hoặc zone; scope_id lấy từ tool lọc. from_date và to_date theo YYYY-MM-DD, from_date < to_date, tối đa 3660 ngày. Kỳ [from,to) tính theo issued_at. Timezone lọc ngày của API phụ thuộc DB/session và chưa được công bố trong response; output period.timezone=null.

### Endpoint và cách tổng hợp

- Mỗi tòa: GET /reports/supporting-records với buildingId, fromDate, toDate, kind=invoices, limit=100, offset=0; tiếp tục theo nextOffset đến hết.
- Mỗi hóa đơn: GET /invoices/{invoice_id} để đọc invoice, lines và category_id. Runtime cung cấp repair_category_ids đã được xác nhận; thiếu cấu hình trả REPORT_REPAIR_CATEGORIES_REQUIRED trước HTTP.
- Tất cả dòng thuộc nhóm sửa chữa thì cộng grand_total danh sách đúng một lần. Không có dòng sửa chữa thì bỏ qua. Có cả sửa chữa và dịch vụ khác thì trả REPORT_MIXED_INVOICE; không cộng toàn giá một bill trộn.
- Dùng Decimal và trả chuỗi số tiền; tách từng currency. Kiểm ID, status, currency, ticket, work order và issued_at giữa danh sách/chi tiết. Dòng trùng hoặc hóa đơn trùng bị chặn.
### Output data của ví dụ

```json
{
  "basis": "issued_repair_invoice_grand_total",
  "items": [
    {
      "currency": "VND",
      "invoice_count": 2,
      "billed_amount": "9007199254740993.02"
    }
  ]
}
```

Không dùng trường tiền trong invoice detail để cộng: test router thật ghi nhận serializer của API chi tiết làm tròn một Decimal lớn. Backend chưa được sửa serializer trong công việc này. Hai lần đọc chưa có snapshot nên chưa chứng minh giá/nhóm dịch vụ nhất quán cùng một thời điểm. Nếu cần tổng phần sửa chữa của bill trộn, phải chốt cách chia thuế/giảm giá trước khi triển khai.


## Tổng hợp ticket và tần suất sự cố

Tool get_ticket_frequency_summary tổng hợp tất cả ticket được tạo trong kỳ và số ticket incident theo từng loại sự cố. Tần suất ở đây là số lần xuất hiện trong kỳ; share là tỷ trọng trong tổng incident, không phải số lần mỗi ngày hoặc mỗi cư dân.

### Input

```json
{
  "scope_type": "zone",
  "scope_id": "33333333-3333-4333-8333-333333333333",
  "from_date": "2026-09-01",
  "to_date": "2026-10-01"
}
```

Bốn trường và quy tắc kỳ giống tool hóa đơn, nhưng cohort theo created_at của ticket. Không nhận category filter hoặc interval do model chọn; tool dùng summary theo tháng rồi cộng cả kỳ. period.timezone=null do API chưa công bố timezone DB/session.

### Endpoint và phép tính

- GET /reports/supporting-records với kind=tickets, buildingId, fromDate, toDate, limit=100 và toàn bộ offset của từng tòa: đếm ID ticket duy nhất.
- GET /reports/incident-frequency-summary với buildingId, fromDate, toDate, interval=month: lấy incident_count theo tháng, category và incident_type_id.
- Gộp incident_count theo incident_type_id qua các tháng, category và tòa. share = số incident của loại / tổng incident. Loại chưa phân loại giữ ID null và nhãn từ backend.
- Kiểm tổng các bucket bằng totalTickets của API. Nếu incident vượt tổng ticket đọc được thì trả REPORT_SOURCE_INCONSISTENT. non_incident = tổng ticket − incident; không khẳng định tất cả non_incident là service_request.
### Output data của ví dụ

```json
{
  "total_ticket_count": 5,
  "incident_ticket_count": 4,
  "non_incident_ticket_count": 1,
  "share_basis": "incident_ticket_count",
  "items": [
    {
      "incident_type_id": "66666666-6666-4666-8666-666666666666",
      "incident_type_name": "Điện",
      "ticket_count": 4,
      "share": 1.0
    }
  ]
}
```

Đây là phép cộng kết quả hiện có của backend; không đếm message và không suy diễn loại incident từ tiêu đề ticket. Hai API đọc riêng có thể lệch khi dữ liệu đổi; kiểm tổng không chứng minh snapshot hoặc quan hệ từng ticket với từng bucket.


## Đánh giá nhân viên theo sao

Tool get_employee_star_summary chỉ báo cáo sao khách hàng đã gửi. Không dùng /reports/employee-performance và không suy ra SLA, tốc độ xử lý, rework hay “hiệu suất” từ điểm sao.

### Input và endpoint

```json
{
  "scope_type": "zone",
  "scope_id": "33333333-3333-4333-8333-333333333333",
  "from_date": "2026-09-01",
  "to_date": "2026-10-01",
  "staff_ids": [
    "55555555-5555-4555-8555-555555555555"
  ]
}
```

staff_ids là danh sách bắt buộc 1–100 UUID không trùng; người gọi chọn từ employee_options hoặc nguồn ID đã xác nhận. Báo cáo chỉ bao gồm các ID được chọn, không tự khẳng định đã bao phủ toàn bộ nhân viên.

Mỗi cặp tòa/nhân viên: GET /reports/employee-feedback với buildingId, staffId, limit=100, offset=0 và đọc đến hết nextOffset. API này chưa nhận fromDate/toDate, nên tool đọc đủ lịch sử rồi lọc submitted_at theo ngày UTC trong [from,to). Output period.timezone=UTC.

### Output data của ví dụ

```json
{
  "basis": "customer_review_submission",
  "total_rating_count": 2,
  "average_stars": "4.50",
  "items": [
    {
      "staff_id": "55555555-5555-4555-8555-555555555555",
      "staff_name": "A",
      "rating_count": 2,
      "star_counts": {
        "1": 0,
        "2": 0,
        "3": 0,
        "4": 1,
        "5": 1
      },
      "average_stars": "4.50"
    }
  ]
}
```

### Cách tính và dữ liệu rỗng

Mỗi lượt phải có score là số nguyên 1–5 và submitted_at có timezone. star_counts chứa đủ năm mức, rating_count là số lượt trong kỳ. Điểm mỗi người bằng tổng sao / số lượt; điểm chung tính trên toàn bộ lượt, không lấy trung bình các trung bình nhân viên. Làm tròn 2 chữ số theo HALF_UP. Không có lượt thì average_stars=null và outcome=empty, không gán 0 sao.

Tên lấy từ employee options hiện tại; ID có feedback nhưng thiếu tên thì trả staff_name=null. Có đánh giá nhưng chưa có công việc vẫn được đếm. Điểm sao phản ánh ý kiến khách; mẫu ít, thiên lệch người phản hồi và so sánh giữa loại công việc chưa được xử lý. Tool không tự xếp hạng nhân viên.


## Các API hiện có và cách gọi

Các API dưới đây có trong backend dev_TeamChien đã đối chiếu. Nhánh dev_TeamHoang-HuyHoang chưa chứa backend này; tool gọi base_url của deployment backend. Không thêm API nghiệp vụ mới; mọi đường dẫn là tương đối với base_url.

| GET endpoint | Input API | Output API được dùng |
| --- | --- | --- |
| /catalogs | Không query. | zones: id,name; buildings: id,name,zone_id. |
| /reports/filter-options | Không query. | buildings: id; employees: id,name; agentContext. |
| /reports/supporting-records | buildingId, fromDate, toDate, kind=invoices hoặc tickets, limit=100, offset. | items, nextOffset, agentContext. Invoice: id,status,grand_total,currency,ticket_id,work_order_id,issued_at. |
| /invoices/{invoice_id} | UUID trong path. | invoice và lines: id,invoice_id,category_id; các trường tiền detail không dùng để tính. |
| /reports/incident-frequency-summary | buildingId, fromDate, toDate, interval=month. | buildingId, interval, totalTickets, items: period,category_id,incident_type_id,incident_type,incident_count; agentContext. |
| /reports/employee-feedback | buildingId, staffId, limit=100, offset; không có ngày. | items: id,score,submitted_at; nextOffset; agentContext. |

### Context runtime và giới hạn

Runtime xác thực rồi inject principal_id, allowed_building_ids và session_cookie; riêng hóa đơn cần repair_category_ids. Descriptors yêu cầu reports:read nhưng không tự cấp quyền. Backend kiểm quyền mỗi request. Client dùng HTTPS hoặc HTTP loopback, không theo redirect và không trả raw HTTP body/cookie trong lỗi.

Một operation có tối đa 60 giây tính cả scope, phân trang, chi tiết và retry. Mặc định request timeout 15 giây, retry GET tối đa 2 lần cho transport/502/503/504. Mỗi luồng phân trang tối đa 100 trang; toàn operation tối đa 10.000 bản ghi ID duy nhất. Giới hạn có thể cấu hình trong khoảng cho phép. Chạm giới hạn hoặc timeout trả failure, không trả tổng thiếu.

### Các lỗi cần xử lý

REPORT_INPUT_INVALID; REPORT_SCOPE_NOT_FOUND / AMBIGUOUS / INCOMPLETE; REPORT_REPAIR_CATEGORIES_REQUIRED; REPORT_MIXED_INVOICE; REPORT_SOURCE_DUPLICATED / INCONSISTENT; REPORT_DATA_LIMIT_REACHED; AUTHENTICATION_REQUIRED; REPORT_SCOPE_FORBIDDEN; BACKEND_UNAVAILABLE; BACKEND_CONTRACT_INVALID. Với lỗi, agent cần giữ mã và hạn chế trong giải thích; không thay bằng số 0.


## Kết quả kiểm thử

| Nhóm | Kết quả cuối | Phạm vi chứng minh |
| --- | --- | --- |
| Scope | 20 đạt | Tên/ID chính xác, tên trùng, quyền thiếu một tòa, quyền bị thu hồi, catalog sai. |
| Composition | 31 đạt | Đọc nhiều trang, cộng tiền, loại bill khác, bill trộn, sao/UTC, dữ liệu rỗng, bỏ tool cũ. |
| Adversarial | 118 đạt | Input sai, JSON sai/trùng, tiền lớn, timestamp, binding/cursor sai, HTTP lỗi, retry, deadline, cancellation. |
| Router hiện có | 4 đạt | Bốn operation qua router FastAPI thật; SQL và auth vẫn giả lập. |
| Narrative cũ | 34 đạt | Hồi quy riêng; không chứng minh template cũ đã dùng bốn tool mới. |

### Những hành vi đã kiểm chứng

- 101 hóa đơn được đọc qua nhiều trang và cộng đủ 1,01 trong dữ liệu test; chạm giới hạn trang thì failure, không báo tổng của 100 dòng đầu.
- Số tiền 9007199254740993.01 cộng 0.01 giữ chính xác 9007199254740993.02. Detail tiền bị làm tròn không được dùng thay giá danh sách.
- Sáu review của hai nhân viên cho điểm chung 2,17 theo số lượt, không lấy trung bình 4,50 và 1,00. Đúng biên kỳ UTC và không có sao trả null.
- 403/401, cursor lặp, JSON hỏng, ID trùng, incident lớn hơn total và bill trộn đều không trở thành success hoặc tổng bằng 0. Retry đọc không dùng response cũ khi lần cuối thất bại.
### Coverage và giới hạn nghiệm thu

Coverage chỉ đo tools/application/metrics: 601/659 statement được chạy (91,20%); 196/242 nhánh (80,99%); tỷ lệ gộp line+branch 88,46%. Còn 58 statement và 46 nhánh chưa chạy. Không đo backend, RLS hay runtime. Test pass và coverage không đủ để gọi tích hợp thật hoàn tất.

Bốn ca router dùng ASGITransport, router thực tế từ checkout backend dev_TeamChien và SQL fake trả Decimal/datetime; dependency xác thực bị override. SQL fake không thực thi WHERE/join/RLS và không kiểm phiên SSO. 34 ca narrative giữ logic cũ đạt nhưng chưa chứng minh narrative hiểu output mới. Test load, thay đổi dữ liệu giữa các trang và dữ liệu thực tế chưa chạy.


## Các test fail và cách sửa

### Lịch sử fail và sửa

Lần 1: 155 đạt, 1 fail trên 156 ca. test_total_deadline_includes_scope_reads giả định gửi được hai HTTP request trong 40 ms; timer Windows chỉ cho một lần đọc trước deadline. Tool đã trả BACKEND_UNAVAILABLE đúng. Sửa thời lượng fixture và budget để kiểm hai lần đọc scope vượt tổng deadline. Test này đạt ở lần cuối; đây là lỗi test, không phải lỗi nghiệp vụ đã chứng minh.

Lần 2: 159 đạt, 1 fail trên 160 ca. Ca get_repair_bill_summary qua router thật gặp phép trừ str−int vì SQL fake trả grand_total dạng chuỗi. Đổi fake thành Decimal theo kiểu NUMERIC của SQL. Không ghi lỗi fixture này thành lỗi database thật.

Lần 3: chạy riêng bốn ca router, 3 đạt và 1 fail hóa đơn. Với Decimal fake đã đúng, invoice detail serialize 9007199254740993.01 thành số JSON bị làm tròn; so sánh số tiền detail/list khiến consumer trả BACKEND_CONTRACT_INVALID. Sửa consumer lấy giá từ supporting-records và chỉ dùng detail cho identity/category. Giữ ca router và thêm regression mất chính xác; ca này đạt. Serializer backend vẫn chưa sửa.

Lần 4: đổi issued_at trong SQL fake sang datetime, bốn ca router có 3 đạt và 1 fail hóa đơn. List trả UTC dạng Z, detail trả +00:00; consumer so sánh chuỗi nên từ chối cùng một thời điểm. Đây là lỗi tool. Sửa parse timestamp có timezone và so sánh thời điểm. Thêm ba ca Z/+00:00/+07:00; vẫn giữ test chặn thời điểm khác. Ca router và ba ca mới đạt ở lần cuối.

### Kết quả sau sửa

Hai biến thể test đòi kiểm giá tiền detail được thay bằng regression bảo toàn giá danh sách, vì detail không còn là nguồn tiền. Thêm 11 ca dữ liệu rỗng/retry và ba ca timestamp; tổng cuối 173 ca tool đạt. 34 ca narrative hồi quy đạt. Không có skip hoặc xfail. Lint từng báo import/unused/startswith và import sau chuẩn bị path; đã sửa và kiểm lại đạt.

Lỗi timer và Decimal fixture được ghi rõ là lỗi test. Hai lỗi consumer liên quan serialize tiền và so sánh timestamp đã được tái hiện qua router hiện có. Chưa có bằng chứng dữ liệu production đã từng bị sai, và chưa sửa API backend. evidence/failure-history.json giữ kết quả trước sửa, nguyên nhân, cách sửa và case cuối tương ứng; final-results.json giữ tên từng test và hash source.


## Review và hướng tiếp theo

### Đánh giá công việc hiện tại

Phạm vi code đã đúng hơn yêu cầu, nhưng phần dùng thật còn thiếu. Python facade và schema tồn tại riêng; FIRST_PARTY_TOOLS vẫn rỗng. Chưa có handler gateway, luồng chọn nhân viên, nguồn cấu hình nhóm sửa chữa hoặc báo cáo chạy với phiên đăng nhập thật. Không nên đánh dấu toàn bộ Report Agent đã hoàn thành.

- Báo cáo hóa đơn phụ thuộc category IDs được xác nhận. Bill trộn bị chặn nên chưa phục vụ trường hợp sửa chữa chung với dịch vụ khác. Đây là giới hạn công khai, không phải đã hỗ trợ đầy đủ mọi hóa đơn.
- Cách đọc chi tiết từng hóa đơn và lịch sử từng cặp tòa/nhân viên tốn nhiều request. Deadline 60 giây và scan cap có thể từ chối tập lớn. Chưa có đo tải hoặc thời gian với dữ liệu thật.
- Phân trang offset và nhiều API đọc riêng chưa có snapshot. Có thể gặp bản ghi bị đổi/di chuyển giữa trang mà không phát hiện bằng kiểm trùng. Metadata nguồn chỉ nêu path, chưa truy ngược đầy đủ từng KPI.
- Kỳ hóa đơn/ticket dùng timezone backend chưa công bố; kỳ sao dùng UTC. Chưa thể quảng bá cả ba loại báo cáo cùng kỳ theo giờ Việt Nam. Sao cũng chưa đủ để kết luận năng suất hoặc xếp hạng công bằng.
### Thứ tự công việc tiếp theo

| Ưu tiên | Việc cần làm và tiêu chí |
| --- | --- |
| 1 | Backend/nghiệp vụ xác nhận category sửa chữa, nghĩa chính xác của grand_total và chính sách bill trộn; có fixture đúng schema từ dữ liệu đã ẩn thông tin. |
| 2 | Runtime inject context đã xác thực, đăng ký bốn descriptor/handler; UI/agent chọn đúng scope và staff_ids. Test người chỉ có một tòa không báo toàn khu. |
| 3 | Chạy với PostgreSQL và hai tài khoản BQL khác quyền; kiểm RLS, tenant, quyền bị thu hồi, đủ trang, dữ liệu rỗng và lỗi backend thật. |
| 4 | Chốt timezone, snapshot và số lượng dữ liệu. Đo request/độ trễ; nếu cần, phối hợp backend batch invoice classification và feedback có lọc kỳ. |

### Nguồn và file người khác cần đọc

PROGRESS_REPORT.md là bản văn bản của báo cáo này. tool-contracts.json là schema đăng ký; input-output-examples.json là input/output/query mẫu đầy đủ. FAILURE_HISTORY.md và evidence/*.json lưu kết quả, các fail và hash source đã kiểm thử.

Code: server/src/reporting/tools/{catalog,contracts,facade}.py; application/client.py; metrics/normalize.py. API đối chiếu: services/vinhomes-api/src/vinhomes_api/{v3_operations,v3_report_jobs,v3_billing}.py. Cách tích hợp và chạy test nằm trong agent-report/README.md.

Bản làm việc: F:\AI-Workforce-Platform-dev_TeamHoang-HuyHoang. Nhánh mới tách từ dev_TeamHoang tại 975565a1; đưa sang riêng Report tools 2.0.0 từ 518178a. Backend API đối chiếu tại dev_TeamChien 9ecd1437 là dependency bên ngoài, chưa có trong nhánh này. Narrative/layout/template có sẵn giữ nguyên. Nhánh mới có một commit Report, không mang lịch sử hai commit Report cũ.
