# Dữ liệu vận hành Ocean Park 1, 2, 3 cần bàn giao

Quyết định chủ dự án ngày 14/10/2026: BQL sử dụng Platform. Domain có admin cấu hình, cư dân và staff; không cấp mới vai trò đăng nhập `management`. Đơn vị quản lý (`management_units`) vẫn là pháp nhân/đội nhận route, không phải role người dùng. Không tự chuyển tài khoản BQL cũ thành admin.

## Dữ liệu nào được xem là thật

Nguồn công khai của Vinhomes xác nhận tên dự án/tiện ích giới thiệu, không thay thế hồ sơ vận hành đang hiệu lực. Xem [nghiên cứu nguồn chính thức](RESEARCH_REAL_DATA_READINESS_20261014.md). Không dùng hotline bán hàng làm đầu mối BQL, không dùng giá vé chiến dịch làm biểu phí cư dân, không suy ra danh sách căn hộ/cư dân/nhân sự từ website.

Database trước đợt làm sạch có 1 site, 8 zone, 16 building, 380 unit, 940 ticket và 678 work order. Có 694 người dùng ID `mock-*`. Các số này là bằng chứng dữ liệu mẫu, không phải số liệu khai thác thật. Snapshot trước chuyển đổi phải được giữ riêng cùng env/master key và image tag.

Kho tri thức có 164 tài liệu / 648 đoạn của OP1: 115 tài liệu cư dân, 49 tài liệu staff. Bundle có 44 tài liệu chứa URL, 12 chỉ mô tả nguồn, 108 không có trường nguồn, 0 hồ sơ duyệt. Bản `unverified=false` không chứng minh đã được BQL duyệt. Giữ nội dung để nghiên cứu; tài liệu thiếu nguồn/phạm vi chuyển sang quarantine. Không chuyển tài liệu OP1 thành chính sách OP2/3.

## Bộ dữ liệu cần cung cấp

Mỗi bộ phải có `site_code` (`ocean-park-1/2/3`), đơn vị sở hữu dữ liệu, ngày xuất, phiên bản, nguồn và người xác nhận. Chuyển danh sách cá nhân qua file riêng ngoài Git, không đưa vào tài liệu nghiên cứu hay chat.

| Ưu tiên | Bộ dữ liệu | Trường tối thiểu và quyết định cần chốt |
|---|---|---|
| P0 | Địa bàn chính thức | Site, zone, tòa/dãy, căn/lô, mã chuẩn, địa chỉ hiện hành, loại tài sản, trạng thái và đơn vị quản lý. Không tự gộp Masteri vào phạm vi Vinhomes. |
| P0 | Đơn vị/route vận hành | Mã đơn vị, site/tòa phụ trách, nhóm dịch vụ, đơn vị trực tiếp/nhà thầu, route ID/revision Platform, thời gian hiệu lực và người xác nhận. |
| P0 | Cư dân | Định danh đăng nhập, mã căn/lô, quan hệ owner/tenant/household, hiệu lực cư trú, bằng chứng xác minh và người xác minh. Không thu thập thông tin cá nhân không cần thiết. |
| P0 | Nhân sự | Mã nhân viên, định danh đăng nhập, đơn vị, chuyên môn, site/tòa phụ trách, năng lực đồng thời, trạng thái, ca trực có múi giờ, người dự phòng. BQL nhận quyền trong Platform, không trong Domain. |
| P0 | Danh mục dịch vụ | Mã/tên dịch vụ, site/zone/tòa, đối tượng sử dụng, điều kiện tiếp nhận, thông tin cần hỏi, đội xử lý, lịch phục vụ, có phí/khảo sát/bảo hành hay không. Danh mục phần mềm Kỹ thuật/An ninh/Vệ sinh chưa phải danh mục dịch vụ chính thức. |
| P0 | SOP và phân quyền | Quy trình thường/khẩn cấp, điều kiện giao việc, di chuyển/đến nơi, vào căn, khảo sát, phương án/chi phí, thay đổi lịch, từ chối, ảnh trước/sau, kết quả và làm lại. Chỉ rõ bước nào cần cư dân đồng ý; agent không duyệt thay. |
| P0 | SLA và danh bạ | Thời hạn phản hồi/giải quyết, cách tính ngoài giờ/ngày nghỉ, đầu mối trực/escalation, phạm vi và hiệu lực. Không dùng số phút/hotline seed làm cam kết thật. |
| P0 | Knowledge đã duyệt | File/URL gốc, mã tài liệu, version, hash, title, audience, site/zone/tòa, effective_from/until, approved_by/at, document_reference. `sources` phải là URL/chứng từ có thể đối chiếu. |
| P1 | Biểu phí và bảo hành | Mã dịch vụ, phạm vi, đơn vị tính, giá, tiền tệ, VAT, trường hợp miễn/ngoại lệ, hiệu lực, văn bản ban hành; điều kiện bảo hành và bên chịu chi phí. |
| P1 | Tiện ích và lịch | Danh mục, vị trí, giờ/ngày nghỉ, quyền cư dân/khách, hạn mức, đặt/hủy/đóng cửa, phí, đơn vị vận hành. Tách tiện ích công khai phục vụ du khách khỏi tiện ích theo quyền cư dân. |
| P1 | Tài sản/bảo trì | Mã tài sản, vị trí, thiết bị, bảo hành, lịch bảo dưỡng, lịch sử đã xác minh, nhà cung cấp, SOP an toàn và quyền đọc. |
| P2 | Thẻ/khách/xe/công nợ | Chỉ nạp từ hệ thống chủ quản có quyền và mapping mã; không dùng số mẫu, không mở thêm MCP để agent tự truy cập toàn bộ hộ dân. |

## Hệ thống phải đáp ứng trước khi nạp dữ liệu thật

- Giữ nguyên tenant boundary; site là phạm vi riêng trong tenant. Knowledge có `site_id`; search không có khu xác định không trả chính sách riêng của bất kỳ khu nào khi có nhiều site.
- Bootstrap production không tạo người, căn hộ, ca trực, ticket, công nợ hoặc SLA giả. `VINHOMES_SAMPLE_WORLD=0`, `VINHOMES_LOAD_KNOWLEDGE=0`; môi trường test riêng được phép giữ fixture.
- Import hiện tại là importer legacy một site. Khi tenant có nhiều site, nó phải từ chối toàn bộ trước khi ghi. Cần nâng cấp importer/staging cho `site_code` và mã trùng giữa các site trước khi nạp roster/master data thật; không dùng CSV cũ cho cả ba khu.
- Dữ liệu nghiên cứu không được tự nâng thành `approved`. Các tài liệu pháp lý cũ giữ làm archive, đối chiếu sửa đổi từng điều; không xóa toàn bộ vì một văn bản đã có bản sửa đổi.
- Kiểm tra dữ liệu qua staging: code unique trong đúng phạm vi, FK hợp lệ, hồ sơ có nguồn/hiệu lực, ca không chồng, không cấp quyền chéo khu; chỉ publish sau khi chủ dữ liệu xác nhận.

## Bàn giao cho Platform

Giữ catalog MCP xử lý ticket, không đưa tool tạo ticket, xác định lại cư dân/căn hộ hoặc toàn bộ roster sang Platform. Ticket bàn giao chứa định danh/phạm vi đã xác minh. Platform quản lý session, BQL, giao việc và tiến độ; staff phản hồi tại Domain, Domain gửi sự kiện về Platform, cư dân quyết định ở các bước cần đồng ý.

Bộ bàn giao gồm: ma trận route/site/dịch vụ, capability và approval policy, SOP/SLA theo version, catalog 7 tool + schema/lỗi, event/state contract, tài liệu tri thức đúng audience/phạm vi, runbook phục hồi và bộ nghiệm thu. URL/key/HMAC cấp riêng qua màn hình admin; không đưa DB dump, account export hoặc env production cho agent.

## Làm sạch và quay lại

`python -m vinhomes_api.production_reset --target-database <tên_mới>` chỉ chuẩn bị database riêng từ nguồn OP1 đã audit, không xóa database nguồn và không tự kích hoạt. Giữ admin, cấu hình storage/integration/route và nội dung/vector tri thức; không giữ phiên đăng nhập, cư dân, nhân sự, căn hộ hoặc giao dịch. Tài liệu phạm vi cũ giữ scope snapshot trong metadata và quarantine cho tới khi có master data thật.

Trước chuyển: pg_dump, kiểm tra archive đọc được, sao lưu env/master key/Compose/image tag. Kiểm tra database mới, cấp quyền runtime, nghiệm thu đăng nhập admin và cách ly khu; sau đó mới chuyển `VINHOMES_DATABASE_NAME` và recreate API/worker/UI. Database cũ và MinIO cũ chỉ giữ riêng cho rollback, không còn là nguồn dữ liệu của ứng dụng. Không xóa backup trong đợt này.
