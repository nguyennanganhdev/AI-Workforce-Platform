# Chuẩn hóa dữ liệu Domain và tài khoản — nghiệm thu 15–16/10/2026

## Phạm vi và quyết định

Nhánh `dev_Vinhome`. Người dùng chọn email `@accounts.vinhome.test`, bỏ nhãn demo/mock khỏi tên đăng nhập và tên hiển thị thông thường, giữ nguồn gốc trong quản trị. Người dùng đồng ý thông tin chưa được operator xác nhận không được Reception trình bày thành chính sách chính thức.

Phạm vi triển khai là Domain Docker chính `http://localhost:8080` và VPS `https://vinhome-platform.duckdns.org`. Database đang chạy ở cả hai là `vinhomes_release_20261015_6884e1b1`, tenant `11111111-1111-5111-a111-111111111111`, migration `0023_platform_resident_assets.sql`. Không thay dữ liệu của các sandbox khác hoặc tài khoản BQL thuộc Platform.

## Kết quả triển khai

Mỗi runtime: **487 bản ghi được chuẩn hóa, 480 bản ghi mới, 16 ca OP1 chưa bắt đầu được hủy** để thay bằng lịch mới. Sao lưu trước, kiểm tra archive và restore trên database clone trước khi cập nhật runtime. Nạp lại không thêm bản ghi, không thay password hiện có hoặc cấu hình tích hợp. Dữ liệu nằm trong PostgreSQL volume; API giữ image `vinhomes-domain-api:data-release-20261015-6884e1b1`. Module bảo trì mới được chạy qua container riêng với source được mount, không thêm auto-seed khi startup.

Tên đăng nhập/tên hiển thị, tên khu/tòa và mã căn, employee code, tên đội dịch vụ, tên tiện ích, chủ thẻ/chủ xe, mã thẻ/khách/bảng kê/cải tạo/yêu cầu và phần mô tả được tổ chức lại. ID người dùng/căn/staff/ticket và mã route operator giữ nguyên để bảo toàn liên kết. Mã tuyến kỹ thuật vẫn có thể mang prefix `SIM-`; đây là định danh tích hợp, không phải tên hiển thị cho cư dân.

Không dựng địa chỉ email của người thật hoặc thương hiệu sở hữu tên miền. `.test` là định danh đăng nhập, không phải hộp thư nhận email Internet. Tài khoản thực có nhu cầu nhận email cần địa chỉ liên hệ được xác minh riêng.

| Dataset | Mỗi Docker chính / VPS |
|---|---:|
| Khu / phân khu / tòa | 3 / 28 / 37 |
| Căn / quan hệ cư trú | 14 / 14 |
| Tài khoản | 88: 2 admin, 14 cư dân, 72 staff |
| Staff OP1 / OP2 / OP3 | 24 / 24 / 24 |
| Ca trực | 1.032: 1.015 trạng thái available, 1 leave, 16 cancelled |
| SLA / phạm vi phục vụ | 45 / 27 |
| Hồ sơ nguồn/đề xuất | 155, không có hồ sơ được operator xác nhận |
| Catalog dịch vụ / đang bật | 64 / 30 |
| Tài liệu / đoạn | 384 / 868 |
| Đoạn có embedding / chưa có | 865 / 3 |
| Xe / thẻ / lượt khách | 14 / 28 / 14 |
| Bảng kê / dòng chi tiết | 28 / 28 |
| Tiện ích / booking tiện ích | 6 / 14 |
| Chính sách / hồ sơ cải tạo | 3 / 14 |
| Yêu cầu dịch vụ mẫu | 14 |
| Sản phẩm Travel / booking Travel | 15 / 0 |
| MCP discovery | 16 tool |

OP1 có 2 cư dân, OP2 và OP3 mỗi khu 6. Mỗi khu có 6 kỹ thuật, 6 an ninh, 6 vệ sinh, 6 hỗ trợ dịch vụ. Staff mới OP1 có quyền staff trong cùng phạm vi, năng lực tối đa một công việc đồng thời, liên kết chuyên môn và người dự phòng cùng nhóm/ca. Có một ca nghỉ tương lai để kiểm thử lựa chọn người thay. Không tạo admin hoặc quyền management mới.

OP1 bắt đầu lịch mới từ 15/10 lúc 23:00 giờ Việt Nam: nhóm 1 23:00–07:00, nhóm 2 07:00–15:00, nhóm 3 15:00–23:00. Lịch kết thúc 29/10 lúc 23:00. OP2/OP3 giữ lịch hiện có, nhóm 1 07:00–15:00, nhóm 2 15:00–23:00, nhóm 3 23:00–07:00, kết thúc 29/10 lúc 07:00. Khi kiểm tra, mỗi khu có 8 người trong ca; khả năng nhận việc còn phụ thuộc availability/capacity/công việc đang giữ. Đây là roster dự án, chưa phải phân công nhân sự thật.

## Dịch vụ, SOP và CSKH

- Chuẩn hóa 30 policy dịch vụ: điều kiện cư trú/phạm vi, phí hoặc báo giá, VAT, lịch ca, đặt/hủy, bảo hành, đầu mối, phiên bản và trạng thái chờ operator xác nhận. Không tự thu/hoàn tiền hoặc coi mức thuế giả định là quy định chính thức.
- Biên tập lại 60 SOP cư dân/staff theo giao tiếp hiện tại: Domain tiếp nhận và cập nhật, Platform quản lý điều phối/tiến độ, cư dân quyết định phương án/chi phí và hoàn thành/xử lý lại. Phân biệt tra cứu với xác nhận đặt chỗ, công nợ với thanh toán, và booking tiện ích nội khu với vé nhà cung cấp bên ngoài.
- Rà thêm 15 SOP staff hành chính: thẻ, khách, công nợ, booking và cải tạo. Các quy trình này yêu cầu đối soát hồ sơ/quyền/điều kiện thay vì bắt buộc ETA/di chuyển/ảnh trước-sau như công việc hiện trường. Có revision nội dung riêng và tạo lại embedding của 15 đoạn thay đổi.
- Thêm 12 hồ sơ quản trị: địa bàn, cư trú, roster/dự phòng/nghỉ và liên kết catalog theo ba khu. Hồ sơ cư trú do dự án sinh không tạo bằng chứng đồng ý của người thật.
- Thêm 10 tài liệu/đoạn có nguồn theo site: đi VinBus đến Vinmec, tra cứu tuyến liên khu, điều kiện quyền lợi Vinmec OP2/OP3, phân biệt Wave Park OP2/Water Park OP3. Không nhập giá/giờ/ETA biến động hoặc tự cấp quyền lợi cá nhân. Nguồn và giới hạn: [nghiên cứu](RESEARCH_CLEAN_DATA_NORMALIZATION_20261015.md); dữ liệu nhập: [JSON](../../deploy/owner-data-pilot/customer-care-reference-20261015.json).

Tất cả **384 tài liệu vẫn `unverified=true`**, 155 hồ sơ nguồn đều `operational_verified=false`. Các nguồn gốc, manifest và giới hạn được giữ. Dữ liệu sạch về cấu trúc/hiển thị không tạo xác nhận của đơn vị vận hành. Travel vẫn là mô phỏng, chưa nối nhà cung cấp giao dịch thật.

## Embedding và cấu hình triển khai

Đã tạo embedding cho **217 đoạn còn thiếu đủ điều kiện**, dùng đúng `text-embedding-3-large`, 1.536 chiều và input heading/body của pipeline hiện tại. Local gọi 10 batch; VPS dùng lại cache có khóa theo hash input để không gọi provider lặp. Không đệm, cắt hoặc pha vector model khác. Ba đoạn còn thiếu thuộc tài liệu `quarantined` đang bị loại khỏi retrieval, được giữ nguyên.

Sau hiệu đính SOP hành chính, tạo lại embedding cho 15 đoạn bằng một batch bổ sung và áp dụng cache cùng hash lên VPS. Số cuối vẫn là 865/868 đoạn có embedding; 3 đoạn cách ly không được đưa trở lại retrieval.

Đã bật cấu hình semantic search cho API ở cả hai nơi bằng env riêng. Khóa embedding cũ của VPS trả HTTP 401; đã thay riêng cấu hình embedding bằng khóa OpenAI đang hoạt động ở local. Không đổi model/key của Reception trong đợt này. Sau đổi, retrieval VPS tìm thấy tài liệu mới đúng khu/đối tượng như local.

Phát hiện file `deploy/deployment.env` local mà Compose đang tham chiếu không còn. Đã khôi phục từ bản sao gần nhất và đối chiếu giá trị runtime; image tất cả service đang chạy khớp trước khi phục hồi. Trước khi tạo lại API, so sánh Compose environment để chỉ cho phép thay khóa embedding; image, database và network giữ nguyên. Reload Nginx sau khi đổi container API trên VPS để cập nhật upstream. Các cổng truy cập đã kiểm tra lại.

## Nghiệm thu

| Kiểm tra | Kết quả |
|---|---|
| Kiểm thử cấu trúc, quyền, ca, dữ liệu nguồn, phân biệt SOP và guard | 6 passed; Ruff đạt |
| Database clone với runtime role hạn chế | 28 login đại diện role/khu, 84 API dữ liệu căn đạt |
| Docker chính | 28 login, 84 API dữ liệu căn đạt |
| VPS HTTPS | 28 login, 84 API dữ liệu căn đạt |
| 16 staff OP1 mới | Tất cả đăng nhập, session đúng role staff và đọc được việc được cấp quyền trên cả Docker chính/VPS |
| Sau tạo lại API | 3 role đăng nhập lại ở mỗi runtime; `/ready` 200 |
| File tài khoản đầy đủ | 88/88 mật khẩu khớp hash trong database local |
| Quyền chéo căn và admin bằng account cư dân | Bị chặn trên clone và hai runtime |
| Retrieval mới theo khu/đối tượng | 6 truy vấn mỗi runtime, có nội dung mới, không lẫn site/quarantine và không nâng thành approved |
| Email/tên người dùng còn demo/sandbox/mô phỏng | 0; 88/88 email đúng namespace mới |
| MCP sau tạo lại API | HTTP 200, 16 tool trên cả hai runtime |
| Index invalid / FK chưa validate | 0 / 0 trên cả hai |
| Import lại / giữ mật khẩu cũ / giữ cấu hình tích hợp | Đạt |

Lịch sử trước/sau import được giữ: local 4 ticket, 1 work order, 4 Platform links, 1 grant; VPS 1 ticket, 0 work order/link/grant. Không tạo ticket/work order, giả lập nghiệm thu cư dân hoặc chạy hội thoại Agent thật để lấy kết quả. Có gọi model embedding cho nạp tri thức và kiểm tra truy xuất; đó không phải nghiệm thu Agent Reception/Platform end-to-end.

## Platform và giới hạn còn lại

Người dùng đã chỉ định URL Platform `http://vagen-platform.duckdns.org`, sau đó chốt **chưa tích hợp, hoàn thiện Domain trước**. Đợt này không onboarding, cấp key/grant/route mới hoặc tạo session Platform. Local giữ cấu hình bridge cũ; **bridge VPS giữ tắt**. URL Platform sẽ được nghiệm thu cùng key/route trong đợt tích hợp sau. Discovery 16 tool của Domain không được coi là nghiệm thu xử lý nghiệp vụ trên Platform.

Thông tin chưa có hồ sơ thật: master căn/địa chỉ/pháp nhân/phạm vi, cư trú và quyền xử lý dữ liệu, nhân sự/chuyên môn/ca, bảng phí/thuế/giờ/bảo hành, SOP/SLA được operator xác nhận. Đợt này hoàn thiện bộ dữ liệu dự án để test, không thay các hồ sơ còn thiếu bằng xác nhận giả.

## Tài khoản và bằng chứng riêng

File cho người sử dụng: `deploy/runtime-access-20261015/clean-data/ACCOUNTS_CURRENT.secret.txt`; bản CSV/JSON cùng thư mục. Có khu/phạm vi, tòa/căn, role, chuyên môn, ca, người dự phòng và URL local/VPS. Mật khẩu cũ giữ nguyên; 16 tài khoản staff mới được sinh riêng. Các file tài khoản cũ của sandbox khác không phải danh sách đăng nhập mới cho Docker chính/VPS.

Thư mục này được Git ignore, chứa plan, snapshot trước, backup, cache embedding và log kiểm tra; không commit credential/env hoặc dữ liệu cá nhân. Artifact VPS: `/opt/vinhomes/releases/operating-data-20261015`, quyền thư mục 700 và file secret 600. Database clone và bản sao lưu được giữ; container kiểm tra được dừng sau nghiệm thu.
