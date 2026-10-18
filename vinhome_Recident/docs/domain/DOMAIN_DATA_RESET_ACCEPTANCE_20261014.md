# Nghiệm thu làm sạch dữ liệu và tách BQL sang Platform

Ngày 14/10/2026. Nhánh thực hiện `dev_Vinhome`, checkout chính `E:\AI-Workforce-Platform`. Không sửa source Platform. Người dùng xác nhận phạm vi Ocean Park 1/2/3, giữ admin/cấu hình, xóa toàn bộ dữ liệu người dùng hiện tại.

## Kết quả đã triển khai trên VPS

- Release API/staff/resident: `real-data-20261014-a08369c049bf`.
- Database đang phục vụ: `vinhomes_clean_20261014_a08369c0`. Database cũ `vinhomes` giữ riêng để rollback, không còn là nguồn dữ liệu của API/worker/backup.
- Domain chỉ cấp mới `customer` và `staff`, admin được quản lý riêng. BQL không đăng nhập/cấp quyền vận hành tại Domain; tài khoản BQL phải được cấp bên Platform. Không tự chuyển BQL cũ thành admin, không tự dựng tài khoản Platform.
- Chặn BQL trên cả đăng nhập mật khẩu, phiên cũ và operations API. UI admin không còn lựa chọn cấp role BQL. Fixture legacy chỉ được dùng với danh tính dev/demo loopback, không bật ở production.
- Giữ admin, password hash, master key, ciphertext và cấu hình tích hợp/storage. Cầu nối Platform vẫn **tắt**; không tuyên bố đã nghiệm thu kết nối Platform/Agent.
- Bootstrap production tách khỏi seed, sample mode và auto-load tri thức mặc định tắt. Không sinh lại người/căn hộ/giao dịch giả khi restart. Reception dùng đường dẫn SQLite mới; provider/model/key giữ nguyên.
- Kho tri thức có `site_id`, search theo khu. Tenant có ba site mà thiếu khu xác định không được lấy chính sách riêng của bất kỳ khu nào. Importer master data legacy một site từ chối ghi trên tenant nhiều site.

| Dữ liệu trong database đang phục vụ | Sau chuyển |
|---|---:|
| Người dùng / admin | 1 / 1 |
| Quyền cư dân / staff / BQL | 0 / 0 / 0 |
| Căn hộ, quan hệ cư trú, staff profile | 0 |
| Ticket / work order | 0 / 0 |
| Site tham chiếu OP1/2/3 | 3 |
| Tài liệu / đoạn tri thức | 170 / 654 |
| Tài liệu quarantine, không đưa vào search | 122 |
| Tài liệu được chứng nhận đã duyệt vận hành | 0 |

164 tài liệu / 648 đoạn cũ được giữ nguyên text/vector, đối chiếu hash khi copy. Các scope zone/building cũ được giữ trong metadata archive, không giữ căn/tòa mẫu làm master data. Bổ sung ba giới thiệu dự án và ba tài liệu tiện ích công khai theo đúng site, nguồn ở [reference pack](../../deploy/reference-data/ocean-city-public-20261014.json). Các bài này là `reference`, không chứng minh phí, giờ mở cửa, quyền sử dụng hay khả năng booking.

Một mã đơn vị quản lý cấu hình cũ và ba integration client được giữ theo yêu cầu giữ cấu hình; không có coverage, staff hoặc work history mẫu đi cùng. Tên/mã đơn vị cũ không chứng minh đó là đội vận hành thật. Cần đối chiếu và thay bằng đơn vị/phạm vi/route được chủ dự án xác nhận trước khi mở dịch vụ.

## Bằng chứng kiểm tra

- **66 backend tests pass** trên PostgreSQL riêng: retire role, reset/copy, giữ admin và tri thức, cách ly site, onboarding, knowledge, MCP v2, cấu hình Platform, tài khoản, password recovery, đăng nhập và importer. Hộp thư giả; không gọi SMTP thật hoặc model.
- **9 UI tests pass**, staff typecheck và build staff/resident pass.
- **7 kiểm tra staging API** trước chuyển: health, admin login/session, danh sách admin, cấu hình encryption/MCP, catalog ba khu, onboarding trống, từ chối cấp BQL.
- **12 màn hình production** ở 375/1440px: Overview, Accounts, Units, Platform Connection, Audit, Reports; không tràn ngang, không có JavaScript exception. Kiểm tra drawer tạo tài khoản chỉ có Cư dân/Nhân viên.
- Admin đăng nhập public HTTPS thành công; tài khoản staff cũ bị 401. HTML public của hai frontend khớp dist đã build. **109 file API runtime khớp manifest**, không mismatch.
- MCP public `initialize` và `tools/list` thành công, đủ 7 tool; **0 business tool call, 0 Agent test** trong đợt này.
- API/staff/resident/reception/backup healthy; scheduler và sync worker running. Backup service trỏ database mới. PostgreSQL thử nghiệm và volume thử riêng đã được dọn, volume production giữ nguyên.

Ảnh, log kiểm thử và manifest private nằm ở `deploy/test-accounts-20261013/domain-audit/production-data-ui/` (ignored), bản release/backup VPS ở `/opt/vinhomes/releases/real-data-20261014-a08369c049bf/`. Bản dump và env trước/sau đã tải về `E:\Vinhomes-Deploy\production-data-20261014\backup-private\`, ngoài Git. Dump 9.491.288 byte, có header PGDMP và đọc được archive list; chưa dùng kết quả này để tuyên bố đã diễn tập restore hoàn chỉnh.

Backup/MinIO/bộ nhớ cũ giữ riêng cho rollback; đây là xóa khỏi hệ thống đang phục vụ, không phải xóa vật lý mọi bản sao lưu.

## Database đã chuẩn để vận hành thật chưa?

**Chưa.** Đã làm sạch nền dữ liệu, quyền và phạm vi tri thức; chưa có dữ liệu chủ quản đủ cho ba khu. Chưa được dùng danh mục phần mềm hoặc bài giới thiệu công khai để chứng nhận dịch vụ vận hành đang hoạt động.

Thứ tự tiếp theo:

1. Chủ dữ liệu bàn giao master site/zone/tòa/căn và đơn vị/phạm vi vận hành thật.
2. Hoàn thiện staging/import theo `site_code`, mã trùng giữa khu và provenance; nghiệm thu không ghi chéo khu trước khi nạp.
3. Nạp cư dân đã xác minh; staff, chuyên môn, ca trực, capacity và phạm vi thật. Không tái tạo tài khoản test trên production.
4. Chốt danh mục dịch vụ, phí, giờ, SOP/SLA, khẩn cấp/đầu mối, phê duyệt và hiệu lực; review/publish từng tài liệu. Đối chiếu sửa đổi pháp lý từng điều.
5. Cấp BQL/tenant/site scope bên Platform, map route/management ref và chốt audience tài liệu. `vh_knowledge_search` hiện trả tài liệu resident; đưa SOP staff cho Platform cần policy/capability riêng, không tự mở toàn bộ kho nội bộ.
6. Nghiệm thu luồng thật bằng người/dữ liệu pilot đã xác nhận, sau đó mở cầu nối. Agent do người dùng lựa chọn kịch bản và test riêng.

Danh sách trường dữ liệu cần bàn giao: [OWNER_DATA_REQUIREMENTS_20261014.md](OWNER_DATA_REQUIREMENTS_20261014.md). Nguồn nghiên cứu và những gì không được suy ra từ website: [RESEARCH_REAL_DATA_READINESS_20261014.md](RESEARCH_REAL_DATA_READINESS_20261014.md).
