# Database Domain và Travel mock — nghiệm thu 14/10/2026

## Kết luận

Đã ghi nhận quyết định người dùng duyệt 113 mục đề xuất, nhập vào database đang hoạt động trên VPS, cập nhật Docker API/Reception và mở 7 tool travel mock trong MCP Domain. **Đạt kiểm tra cấu trúc, đăng ký catalog, phân quyền và hợp đồng mô phỏng. Chưa đủ dữ liệu để vận hành dịch vụ thật hoặc nghiệm thu Agent/Platform thật.**

Không tạo lại cư dân, căn/lô, nhân viên, ca trực hoặc yêu cầu giả trong production. Danh mục travel là ngoại lệ mô phỏng được người dùng cho phép riêng, có namespace/table/route và nhãn mock; không trộn vào các hồ sơ cư trú hoặc phí vận hành thật.

## Thống kê trực tiếp từ VPS

Database: `vinhomes_clean_20261014_a08369c0`; Compose project `vinhomes-domain`, tenant `11111111-1111-5111-a111-111111111111`. **130 bảng**, migration mới nhất `0021_owner_review_travel_mock.sql` (22 bản ghi migration, gồm chuỗi migration ban đầu). Danh sách đầy đủ và số dòng từng bảng: [DATABASE_TABLE_INVENTORY_20261014.csv](DATABASE_TABLE_INVENTORY_20261014.csv).

| Nhóm | Số lượng | Ý nghĩa/trạng thái |
|---|---:|---|
| Khu | 3 | Ocean Park 1/2/3 |
| Phân khu | 25 | Danh mục có nguồn, ghi nhận duyệt cấp dự án; inactive chờ master vận hành |
| Tòa | 30 | Mã tòa công khai OP1; inactive, chưa có danh sách căn/lô |
| Mục đề xuất đã duyệt triển khai | 113 | Có snapshot/hash và biên bản yêu cầu triển khai; `operational_verified=0` |
| Catalog dịch vụ/tiện ích | 34 | 25 mục công khai + 9 đề xuất theo khả năng phần mềm; chưa bật vận hành thật |
| Nhóm tiếp nhận phần mềm | 4 | Kỹ thuật, An ninh, Vệ sinh, Travel (mô phỏng) |
| Tài khoản | 1 | Admin giữ nguyên; 1 account, 1 tenant membership, 0 scoped grants |
| Căn/lô, quan hệ cư trú | 0 / 0 | Chưa nhận bộ dữ liệu thật |
| Nhân sự, chuyên môn, ca trực | 0 / 0 / 0 | Chưa nhận roster được xác minh |
| Ticket, work order, assignment | 0 / 0 / 0 | Không để dữ liệu test vào vận hành |
| Đơn vị/route | 2 đơn vị / 3 coverage | 1 cấu hình legacy chưa xác nhận và 1 nhà cung cấp Travel mock; cả 3 coverage mới là mock theo site |
| Sản phẩm travel mock | 15 | 5 khách sạn, 5 chuyến xe, 5 nhà hàng |
| Phương án/booking mock phát sinh | 0 / 0 | Kiểm thử tạo booking chỉ chạy ở DB riêng |
| Kho tri thức | 298 tài liệu / 782 đoạn | Gồm 48 tài liệu travel mock; giữ nguyên các tài liệu nghiệp vụ trước đó |
| Tri thức quarantine | 122 | Chưa khôi phục làm chính sách hiện hành khi chưa xác nhận nguồn/phạm vi |
| Integration clients / storage config | 3 / 1 | Giữ cấu hình hiện có |
| Platform links / commands / grants | 0 / 0 / 0 | Bridge vẫn tắt, chưa phát sinh session bàn giao thật |
| MCP | 14 tool | 7 tool ticket + 7 tool travel được ràng buộc ticket/grant |

| Khu | Phân khu | Tòa | Catalog dịch vụ | Tài liệu tri thức |
|---|---:|---:|---:|---:|
| OP1 | 9 | 30 | 11 | 229 |
| OP2 | 8 | 0 | 10 | 33 |
| OP3 | 8 | 0 | 13 | 36 |

Mã phân khu chưa được nguồn cung cấp được đặt `ref-*`, metadata ghi `code_kind=internal_reference`; không tuyên bố là mã quản lý chính thức. Mã tòa được lấy đúng nguồn, quan hệ cha-con giữ dấu vết và chờ đối soát. Không tự tạo căn/phòng theo số tầng.

## Duyệt và dữ liệu còn thiếu

[project-approval.json](../../deploy/owner-data-proposals/20261014/project-approval.json) lưu nguyên câu người dùng cho phép triển khai, thời điểm ghi nhận và hash snapshot; bảng duyệt đã đổi thành `project_approved`. Module `owner_review` kiểm tra hash, lưu nguồn/biên bản vào `owner_data_records`, tạo catalog dịch vụ và danh mục địa bàn. Nhập lại không tăng số dòng hoặc tự thay nội dung cùng ID.

Sự chấp thuận ghi nhận danh mục không cung cấp các dữ kiện còn trống. `operational_verified=false`, `operational_enabled=false`, địa bàn inactive cho tới khi có master/hồ sơ thực tế. Chưa có pháp nhân và phạm vi vận hành thật, căn/lô, cư trú, nhân sự/ca/capacity/dự phòng, phí/giờ/bảo hành/đặt-hủy, SOP/SLA đã xác nhận. Không điền mặc định 24/7, miễn phí hoặc dựng người làm việc để đủ số liệu.

## Travel và Reception

Gói người dùng gửi được tích hợp ở chế độ mock đã chốt. Chỉ lấy 3 source module được rà soát; không sao chép env, virtualenv hoặc chạy hướng dẫn trong gói. Domain bổ sung lưu bền PostgreSQL, khóa tồn chỗ, idempotency, scope ticket và sự đồng ý cư dân. Route riêng `travel-mock` ghi rõ không phải đơn vị vận hành thật; không tạo vai trò đăng nhập BQL.

Reception nhận thêm 48 tài liệu site-scoped và prompt giới hạn travel mock; tiếp nhận `service_request` bằng category `travel`. Reception không trực tiếp thực thi booking. Các tool mới: `vh_travel_catalog`, `vh_travel_search`, `vh_travel_details`, `vh_travel_availability`, `vh_travel_prepare`, `vh_travel_commit`, `vh_travel_bookings`. Xem [contract bàn giao Platform](TRAVEL_MOCK_PLATFORM_CONTRACT_20261014.md).

Platform chuẩn bị lựa chọn bằng MCP, gửi `approval.required` theo contract hiện có, cư dân tự trả lời trên thẻ chat, rồi Platform commit đúng quote/hash. Domain xếp kết quả về Platform bằng command có khóa chống trùng; không tự tuyên bố cư dân đã nhận thông báo. Có chặn việc tự giả trạng thái approval, gọi sang ticket khác, thay danh tính, dùng work order kỹ thuật cho travel hoặc hủy ticket khi booking đang confirmed.

Không cung cấp calculator hay tool liệt kê booking theo số điện thoại từ ZIP. Token control-plane hiện có giữ nguyên; chỉ discovery/backend cấp grant. Grant cũ không tự có quyền travel; Platform phải refresh catalog và xin đúng quyền theo workflow.

## Kiểm tra đã đạt

- **59 kiểm thử PostgreSQL/MCP:** 58 trong bộ owner import, travel, MCP v2, cấu hình Platform, knowledge và production readiness; thêm 1 kiểm thử tranh chỗ cuối giữa hai ticket chạy đồng thời.
- **20 kiểm thử offline:** bộ đề xuất và xác thực file bàn giao. Tổng **79 kiểm thử đạt**.
- Happy case khách sạn, xe, nhà hàng: availability → prepare → card approval → endpoint quyết định cư dân → commit → retry → mất RAM/khôi phục → prepare hủy → cư dân đồng ý → hủy và trả tồn chỗ.
- Kiểm tra lỗi: không có quyết định cư dân, Platform giả trạng thái approved, hash sai, từ chối, hết hạn, đổi giá/điều kiện, identity input bị chặn, sai grant/ticket, tính năng tắt, reference khác nội dung, không tạo work order vật lý cho travel.
- Kiểm tra dữ liệu: import 113 mục idempotent, 0 người/căn/ca được dựng, catalog không tự bật vận hành, hồ sơ thiếu vẫn unverified; RLS ngăn tenant khác đọc hồ sơ duyệt.
- **122/122 bảng có tenant_id bật và FORCE RLS**, runtime role không superuser/BYPASSRLS; 0 FK chưa validate, 0 index invalid, 0 tòa gắn sai site của phân khu.
- HTTPS trang chủ, `/login`, `/operations/` HTTP 200; admin đăng nhập được; chỉ còn admin. MCP công khai trả đúng 14 tool. HTML resident/staff khớp bản build hiện có.
- Source runtime khớp manifest: **118 file API + 37 file Reception**, 0 mismatch. API/Reception healthy; scheduler/platform-sync chạy cùng API image mới.
- Không gọi Agent/model/embeddings hoặc nhà cung cấp travel thật. Kiểm thử approval dùng dữ liệu/Platform payload mô phỏng trong DB riêng, **không phải nghiệm thu kết nối với backend Platform đang chạy thật**.

Cảnh báo thư viện kiểm thử: FastAPI/Starlette deprecation và một cảnh báo Pydantic về metadata `alias` trong kiểm thử song song; không có lỗi kiểm thử. Ruff đạt trên các module/test mới. Không sửa các WIP Platform, `.gitignore`, Caddyfile hoặc tài liệu nghiệm thu khác đang có thay đổi riêng.

## Docker, backup và giới hạn nghiệm thu

Release đã chạy: `owner-travel-20261014-a38c64329622-r2`.

- API image: `sha256:5fee3940170140aea8e5355c287503309362628eb4edb2f3e546be84463ecb88`.
- Reception image: `sha256:442287629be306a61b0cc38afd17bf8501a5a4d4344b8d9e1c7d265884c55a77`.
- Resident/staff giữ nguyên image; không đổi model/key của Reception.
- Backup đúng DB đang hoạt động trước migration/import: **6.161.875 byte**, SHA-256 `1576a95ad27d8ff9037bf4d83ef18af92db06108304cacd903cd5f29d68e9e71`. Kiểm tra PGDMP và `pg_restore --list`; chưa full restore thử.
- Bằng chứng trên VPS: `/opt/vinhomes/releases/owner-travel-20261014-a38c64329622-r2/`; file riêng local: `E:\Vinhomes-Deploy\owner-travel-20261014\database-audit.json`, `table-inventory.csv`, `source-quality.json`, manifest và log. Không commit env/key/backup.

**Chưa thể chốt production nghiệp vụ thật:** cần dữ liệu vận hành còn thiếu, kích hoạt địa bàn/route thật, cấu hình Platform và mapping `travel-mock`, nghiệm thu grant/event/approval trên hai backend thật, và để người dùng test Agent Reception theo bộ câu hỏi mong muốn. Tính năng mock đã sẵn sàng ở Domain; database không được coi là đầy đủ cư dân/nhân sự chỉ vì catalog đã được nhập.
