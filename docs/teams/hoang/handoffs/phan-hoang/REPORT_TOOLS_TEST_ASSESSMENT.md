# Đánh giá Report tools sau mở rộng kiểm thử

Ngày 03/10/2026. Báo cáo kiểm thử trước bàn giao; nhánh bàn giao `codex/report-agent-PHH`.

**Kết luận:** wrapper đã được sửa sau các lỗi tái hiện bằng test và bộ kiểm thử
local cuối đều đạt. Chưa đủ bằng chứng để kết luận chạy production an toàn hoặc
KPI đúng trên database thật. Coverage và số test không thay thế kiểm thử nghiệp vụ.

Ruff check/format check đạt. Whitespace được kiểm trực tiếp trên các file mới;
Ở thời điểm đo ban đầu, `git diff --check` không xác minh các file còn untracked; trước commit cần kiểm staged diff.

## Kết quả và bằng chứng

| Lần kiểm tra | Kết quả | Diễn giải |
| --- | --- | --- |
| Bản trước đợt mở rộng | 62 tool tests + 34 narrative tests đạt | Chưa bắt được nhiều phản hồi sai hoặc dữ liệu khác thường |
| Lần đầu thêm fault tests | 43 fail / 132 pass | Có 8 fail do helper test tự thêm lại metadata; đã sửa helper, không tính là lỗi sản phẩm |
| Baseline đã sửa helper, thêm kiểm tra nhóm sự cố | 40 fail / 140 pass | 40 là số ca thất bại, không phải 40 lỗi độc lập; có 2 ca yêu cầu bổ sung contract total deadline |
| Kiểm tra tiền dạng JSON number | 3 fail | Bắt mất chữ số và chấp nhận chuỗi số sai cú pháp |
| Kiểm tra boundary sau sửa ban đầu | 2 fail / 25 pass | Bắt JSON lồng sâu và OverflowError do validation timeout mới gây ra |
| Lần cuối | **256 pass, 0 fail, 0 error, 0 skip** | 222 tool tests + 34 narrative tests; tăng thêm 160 ca tool so với bản trước |

Phạm vi coverage chỉ gồm `reporting.tools`, `reporting.application`,
`reporting.metrics`: **421/437 dòng lệnh (96,34%)**, **165/178 nhánh (92,70%)**;
chỉ số kết hợp **95,28%**. Không loại dòng bằng pragma và không dùng xfail/skip để
che lỗi. Đây không phải coverage toàn repository hoặc phần SQL/backend.

Log và JUnit XML giữ trong `.codex-artifacts`: `report-before-fixes`,
`report-baseline-corrected`, `report-money-before`, `report-boundaries-before`,
`report-final-tests`; có cả `report-coverage.json` và source trước sửa trong
`report-source-before-fixes.zip`. ZIP bằng chứng: `Report-Agent-Test-Evidence.zip`.

## Lỗi và thiếu sót đã sửa

| Nhóm | Phản ví dụ / tác động | Sửa |
| --- | --- | --- |
| Mất chính xác số tiền | JSON number `9007199254740993.01` trở thành `9007199254740994.0` | Đọc fractional JSON bằng Decimal trước khi có float; giữ chuỗi chính xác khi trả về |
| Exception thoát boundary | Operation là list/dict làm TypeError; JSON lồng sâu làm RecursionError | Kiểm loại operation; trả lỗi contract có cấu trúc khi decode/convert JSON không hợp lệ |
| Điểm đánh giá sai thang | Nhận điểm 0/6 và average_rating > 5 | Áp dụng thang 1–5 theo CHECK của ticket_reviews; không coi thiếu điểm là 0 |
| Metric/identity thiếu hoặc sai | Staff ID rỗng/sai UUID, số quá lớn, metric bắt buộc bị thiếu | Kiểm UUID, count trong miền bigint, trường bắt buộc và quan hệ mẫu số/cohort |
| Doanh thu tự mâu thuẫn | Outstanding vượt billed; số công việc vượt số hóa đơn; currency không hợp lệ | Kiểm các bất biến này và currency viết hoa; không cộng khác tiền tệ |
| Số tiền không giới hạn | `1e10000`, `1_000`, chuỗi có whitespace được nhận | Giới hạn miền số và cú pháp trước khi format; lỗi được trả rõ, không clamp/round |
| Phân trang không tiến | Trang rỗng trả cursor cũ hoặc trang ngắn vẫn có nextOffset | Áp dụng contract: trang đủ limit mới có cursor kế tiếp; trang ngắn kết thúc |
| Filter/metadata sai | Category/employee là primitive, ID trùng, format chưa hỗ trợ; facts mâu thuẫn với result | Kiểm shape, uniqueness, định dạng DOCX và ràng buộc metadata |
| Export thiếu trạng thái đầy đủ | Missing kind/execution/downloadUrl vẫn được nhận | Kiểm đúng contract export đồng bộ hiện tại; không nhận trạng thái worker chưa có |
| Nhóm sự cố không đủ căn cứ | Có tổng nhưng thiếu ngày/nhóm hoặc nhóm trùng | Kiểm ngày, taxonomy IDs, nhãn và uniqueness; không gộp/double count |
| Thiếu deadline tổng | HTTP timeout từng pha không giới hạn cả retry/backoff | Bổ sung deadline cho toàn request/retries, tối đa 60 giây; POST timeout vẫn execution_unknown |
| Lỗi phát sinh trong đợt sửa | Hàm validation timeout mới gọi math.isfinite trên int quá lớn và văng OverflowError | Kiểm miền trước khi chuyển/đánh giá float; giữ test regression |

Phần lớn ca phản hồi sai được chủ động đưa vào bằng fault injection, không phải
bằng chứng PostgreSQL production đã trả dữ liệu đó. API hiện thường serialize
NUMERIC thành chuỗi; lỗi tiền dạng JSON number cho thấy decoder trước đây không
đúng với một dạng dữ liệu mà chính wrapper đã nhận hỗ trợ.

## Các test được làm mạnh hơn

Test idempotency cũ trả cùng ID từ mock hai lần: chỉ chứng minh wrapper giữ key,
chưa chứng minh backend không insert hai bản. Test mới chạy router FastAPI thật
với fake repository có lưu request hash/receipt, đếm insert, kiểm replay và 409
khi đổi payload cùng key. Hai principal dùng cùng key có receipt riêng.

Test cũ chạy route dưới scope giả admin. Test mới chạy nhánh BQL không phải admin,
giữ quyền local bị stale nhưng backend từ chối, thu hồi quyền trước status/replay/
download, kiểm owner khác không đọc export. Các test này vẫn chưa chứng minh SQL,
transaction, advisory lock, tenant RLS hoặc SSO thật.

Kiểm cả dữ liệu hợp lệ dễ bị chặn nhầm: bucket tuần bắt đầu trước kỳ báo cáo;
taxonomy null; không có công việc hoàn thành nhưng có feedback của cohort khác;
hai tiền tệ giữ riêng; một invoice trả dư cùng một invoice chưa trả. Đặc biệt,
không ép outstanding = max(tổng billed − tổng collected, 0), vì backend tính theo
từng invoice và hai tổng có thể che nhau.

Test download kiểm bytes DOCX và nội dung kind/kỳ. Chưa render Word để đánh giá
bố cục. POST cancellation sau khi đã gửi vẫn truyền CancelledError, không retry;
runtime phải giữ pending/key trước side effect, phần lưu trạng thái này chưa có.

## Những phần còn yếu hoặc chưa được chứng minh

1. **Chưa test PostgreSQL thật:** chưa xác minh cohort SQL, timezone DB, join/RLS,
   isolation, rollback và export đồng thời. Fake repository không mô phỏng các cơ chế này.
2. **Chưa test SSO/gateway/AgentScope thật:** wrapper chưa mount vào runtime chung.
   Gateway còn phải kiểm tool allowlist và quyền `reports:read/write`; descriptor
   không tự cấp quyền. Context/cookie phải cùng đến từ session đã xác thực.
3. **Thiếu provenance backend:** snapshot/as_of/metric_version/timezone còn null;
   không được coi các con số là lịch sử tại một thời điểm đã xác minh.
4. **Giới hạn nghiệp vụ còn nguyên:** feedback chưa lọc kỳ; supporting records
   chưa chứng minh lineage mỗi KPI; doanh thu theo invoice issued, chưa theo ngày
   hoàn thành; thực thu trước cuối kỳ không phải cashflow riêng trong kỳ.
5. **Export chưa đầy đủ:** chỉ DOCX đồng bộ cho incident toàn tòa hoặc giá trị
   invoice issued; chưa có báo cáo nhân viên/thực thu, worker hoặc consumer template mới.
6. **Output schema còn tổng quát:** catalog chưa mô tả chi tiết từng data payload.
   Wrapper kiểm một số trường/bất biến, chưa có schema đầy đủ cho mọi field trong
   supporting records. Quyền và nội dung từng record vẫn phụ thuộc backend.
7. **Không phải load/security audit toàn hệ thống:** chưa đo bộ nhớ với body lớn,
   giới hạn response size, tải đồng thời, network thật, fuzz không giới hạn hoặc
   kiểm prompt injection qua model thật. Comments là dữ liệu, runtime vẫn phải
   tách chúng khỏi instructions.

Miền decimal được wrapper hỗ trợ: text tối đa 128 ký tự, adjusted exponent <= 38
và scale tối đa 38. Giá trị ngoài miền trả contract error; đây là giới hạn của
wrapper, không phải khẳng định toàn bộ miền PostgreSQL NUMERIC đều được hỗ trợ.

Các nhánh chưa cover được giữ hiển thị trong JSON report, gồm guard/config,
nhánh private route không đi qua facade và một số nhánh phòng vệ. Không thêm
test giả chỉ để đạt 100%.

**Cổng tiếp theo:** dataset có expected KPI độc lập chạy trên PostgreSQL thật;
hai BQL khác tenant/quyền, revoke giữa run/download; export cạnh tranh cùng key;
AgentScope/gateway/persistence thực tế. Chỉ sau những kiểm tra này mới đánh giá
khả năng vận hành production. Bản hiện tại phù hợp để review và tích hợp thử.

## Bằng chứng trong repository

[Báo cáo bàn giao PHH](../../reports/report-agent-PHH/PROGRESS_REPORT.md) và
[lịch sử từng FAIL](../../reports/report-agent-PHH/FAILURE_HISTORY.md) có evidence
JSON được commit để người review trên GitHub không phụ thuộc `.codex-artifacts` local.
