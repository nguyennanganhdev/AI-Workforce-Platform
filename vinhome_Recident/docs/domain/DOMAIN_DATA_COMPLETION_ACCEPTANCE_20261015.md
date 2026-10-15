# Nghiệm thu bổ sung dữ liệu Domain — 15/10/2026

Phạm vi: nhánh `dev_Vinhome`, pilot **OP1 → The Sapphire 1 → S1.01 → Kỹ thuật**. Đây là nghiệm thu nghiên cứu, chuẩn bị dữ liệu và nhập tài liệu tham khảo; **chưa phải nghiệm thu vận hành thật hoặc Agent/Platform thật**.

**Cập nhật mới nhất, vòng 3 cùng ngày:** đã thêm 3 reference lịch sử OP1 có thể tra cứu và lưu cách ly 3 bản từ mẫu hợp đồng lô thương mại. Hiện VPS **314 tài liệu / 798 đoạn**, local **176 / 660**; **89 kiểm thử đạt**. Bộ pilot vẫn có 108 trường/hạng mục owner còn thiếu. Số liệu database dưới đây là sau cả ba vòng; bằng chứng từng vòng được giữ riêng.

## Đã hoàn thành

1. Kiểm kê riêng local và VPS, xác định database đang được API sử dụng. Không dùng database cũ trên VPS hoặc dữ liệu test local làm bằng chứng vận hành.
2. Nghiên cứu nguồn chính thức, bổ sung bốn tài liệu tham khảo có URL, phạm vi áp dụng và SHA-256 snapshot: bàn giao Sapphire cơ bản, Sapphire tối thiểu, bàn giao thô căn thương mại dịch vụ OP1 và mô tả kênh ứng dụng Vinhomes Resident chính thức. Mô tả ứng dụng thương hiệu không chứng minh Domain AI này đã có các tính năng/API tương ứng.
3. Nạp bốn tài liệu vào **cả local và VPS** sau backup. Nhập lại không tạo trùng hoặc sửa nội dung. Tra cứu bằng quyền runtime tìm được nội dung mới tại OP1; cùng truy vấn tại OP2/OP3 không trả các bản ghi mới này. Không tạo embedding hoặc gọi model.
4. Điền trước [bộ candidate](../../deploy/owner-data-pilot/op1-technical/README.md): **12 dòng / 128 ô có giá trị**, trong 5/10 dataset. Có một phân khu, một tòa từ nguồn công khai; một tuyến đề xuất; ba nhóm tiếp nhận điện, nước, điều hòa/thông gió; sáu khung SOP phần mềm cho cư dân/staff. Các mã proposal và mã tham chiếu nội bộ không phải mã dịch vụ/master do đơn vị vận hành cấp.
5. Sinh [108 trường/hạng mục còn thiếu](../../deploy/owner-data-pilot/op1-technical/missing-data.csv), tách rõ dữ kiện công khai, khung phần mềm và hồ sơ cần chủ dữ liệu cung cấp. Năm CSV đơn vị, căn, cư dân, nhân sự, ca trực vẫn chỉ có header. Không tạo tên người, quyền cư trú, căn, ca, phí, SLA hoặc chữ ký xác nhận giả.
6. Nâng script tạo candidate, giữ cơ chế từ chối ghi đè thư mục đã điền. Compiler chỉ bổ sung cho phép đúng trang Google Play của `com.vinhomes.resident`; URL có credentials, fragment, HTTP hoặc nguồn ngoài danh sách bị từ chối.
7. Chuẩn hóa bằng chứng JSON về LF trước khi tính hash, tránh khác biệt Windows/Linux hoặc Git checkout làm hỏng tham chiếu hồ sơ. Kiểm thử kiểm tra cả byte xuống dòng và SHA-256 của file sinh ra.

Nguồn, diễn giải và giới hạn nằm trong [nghiên cứu nguồn](RESEARCH_DOMAIN_DATA_COMPLETION_20261015.md) và [gói JSON nhập reference](../../deploy/reference-data/op1-technical-public-20261015.json). Tiêu chuẩn bàn giao chưa có ngày hiệu lực xác minh; không suy ra bảo hành, thiết bị thực tế hoặc quyền sửa chữa của từng căn.

## Database VPS hiện có

Snapshot sau import, database **`vinhomes_clean_20261014_a08369c0`**, Compose project `vinhomes-domain`. Các số liệu dưới đây không phải số lượng dữ liệu được owner xác nhận.

| Nhóm | Số lượng | Chất lượng / trạng thái |
|---|---:|---|
| Site | 3 | OP1, OP2, OP3 |
| Phân khu / tòa | 25 / 30 | Tham khảo, chưa active; 30 tòa đều thuộc OP1 |
| Căn / quan hệ cư trú | 0 / 0 | Chưa có master căn và hồ sơ xác minh |
| User / account / admin | 1 / 1 / 1 | Một admin, không có cư dân/staff |
| Nhân sự / chuyên môn / ca | 0 / 0 / 0 | Chưa đủ để phân công việc thật |
| Đơn vị / coverage | 2 / 3 | Cấu hình nền, không chứng minh đơn vị/nhân sự thật |
| Owner proposal records | 113 | 0 bản ghi được xác nhận vận hành |
| Catalog dịch vụ | 34 | 0 dịch vụ bật vận hành |
| Operational staging batches / records | 0 / 0 | Chưa nhập bộ owner hoàn chỉnh |
| Tài liệu / đoạn tri thức | **314 / 798** | Tăng tổng 16 / 16 qua ba vòng, gồm 3 bản cách ly mới |
| Tài liệu reference / quarantined | 189 / 125 | Toàn bộ 314 còn cờ `unverified`; reference không phải quy định đã duyệt |
| Travel mock catalog / booking | 15 / 0 | Mô phỏng, không phải nhà cung cấp/đặt chỗ thật |
| Ticket / work order / MCP grant | 0 / 0 / 0 | Chưa có luồng nghiệp vụ đang chạy |
| Platform connection setting | 1 | `enabled=false`, URL chưa cấu hình |
| Migration mới nhất | 0023 | Có staging 0022 và resident assets 0023 |

Hai `management_units` là **Local Management** (cấu hình bootstrap, chưa xác minh đơn vị pháp lý) và **Nhà cung cấp Travel MÔ PHỎNG**. Không tính chúng là hai đơn vị vận hành đã được xác nhận. Ba coverage nền không thay hồ sơ tuyến/phân công thật.

| Khu | Phân khu | Tòa | Tài liệu sau import | Dịch vụ bật vận hành |
|---|---:|---:|---:|---:|
| OP1 | 9 | 30 | 241 | 0 |
| OP2 | 8 | 0 | 35 | 0 |
| OP3 | 8 | 0 | 38 | 0 |

Local dùng database `vinhomes`: **176 tài liệu / 660 đoạn** sau ba vòng import, 720 user nhưng chỉ 15 account; 380 căn, 690 quan hệ cư trú, 26 staff và 1.405 ca, 945 ticket và 683 work order là dữ liệu lịch sử phục vụ test. Không chuyển dữ liệu này sang VPS hoặc gọi là hồ sơ thật. Số liệu local và VPS khác nhau có chủ đích.

## Bằng chứng kiểm thử và triển khai

- **89 kiểm thử đạt**, gồm candidate, nguồn tham khảo, nhập knowledge, pilot/staging, handoff v1, owner proposals, MCP v2 và schema; tăng hai ca ở vòng 2 và năm ca ở vòng 3. Ruff đạt cho Python thay đổi. Một cảnh báo Starlette TestClient, không có lỗi trong bộ đã chạy.
- PostgreSQL test riêng được tạo và gỡ cùng volume sau kiểm thử. Candidate thiếu hồ sơ trả `valid=false`; không được nhập staging hoặc mở dịch vụ thật. Happy case staging dùng dữ liệu synthetic chỉ ở database test riêng, không phải hồ sơ sản xuất.
- Runtime tìm đúng tài liệu mới tại OP1: ba nhóm truy vấn có lần lượt **2 / 1 / 1** kết quả mới. OP2 và OP3 đều **0** ở cùng các truy vấn. Đây là kiểm thử truy xuất dữ liệu, không phải đánh giá chất lượng hội thoại Agent.
- Backup PostgreSQL dạng custom trước import: local **9.561.326 byte**, VPS **6.270.353 byte**. Đã kiểm tra header và danh mục `pg_restore --list`; chưa chạy khôi phục toàn bộ backup.
- Đối chiếu fingerprint bảo toàn dữ liệu cũ. Trên VPS có thay đổi độc lập ở `platform_connection_settings.worker_seen_at` do worker heartbeat; đã đối chiếu bản COPY từ backup và xác nhận các cột cấu hình/credential khác giữ nguyên. Không coi timestamp heartbeat là dữ liệu bị importer sửa.
- Không thay Compose, credentials, API image hay Reception image trong đợt nhập dữ liệu này. Dữ liệu knowledge nằm trong PostgreSQL, không cần rebuild image để bản đang chạy đọc được. Không chạy bootstrap/seed để tránh phục hồi dữ liệu demo.
- **0 cuộc gọi Agent/model/embedding; không nghiệm thu Platform E2E**. Không tạo tài khoản, master căn, nhân sự, ca hoặc bật tuyến/dịch vụ từ bộ candidate.

Gói 4 reference vòng đầu SHA-256: `bdc88143a91a9f57366c95ef851bd05cb858e01c8b386a3d2a34da620949ce2a`.

Backup VPS SHA-256: `50f86282e90d4efc9b6284cd94c99ed36567f4b957753768fddcb3e4d8675fc7`.

Backup local SHA-256: `22f0af4f2fb048c8ad92803a087f1afc874ad9b62c58009484db87b896d4a61d`.

Bằng chứng riêng trên máy: `E:\Vinhomes-Deploy\data-completion-20261015\` (inventory, source snapshots, candidate, backup, kết quả import và log test). VPS: `/opt/vinhomes/releases/data-completion-20261015/`. File chứa cấu hình bí mật/backup không đưa vào Git hoặc chuyển cho Platform.

## Bổ sung vòng 2: hỗ trợ cư dân và hoạt động theo khu

Gói [resident-support-public-20261015.json](../../deploy/reference-data/resident-support-public-20261015.json) gồm:

| Khu | Nội dung mới | Giới hạn |
|---|---|---|
| OP1 | Kênh liên hệ công khai `1900 2323 89`; phân loại chuyên môn M&E điện/nước/điều hòa | Số công khai trên website dự án, không xác nhận trực kỹ thuật/an ninh/giờ. M&E là mô tả tuyển dụng thương hiệu, không phải roster OP1 |
| OP2 | Kênh liên hệ trên The Empire; mô tả Empire Park, Silk Park, Kingdom Avenue/Empire Square | Không suy ra nhánh, giờ, quyền dùng, giá, lịch sự kiện hoặc khả năng booking hiện hành |
| OP3 | Phân biệt Tropical Lagoon/Four Seasons/Olympics/Aqua Bay; loại hình Aquarium/BBQ Garden/Marina Square | Mô tả quảng bá, không cam kết mở cửa, an toàn cá nhân, phí, độ tuổi hoặc chỗ còn trống |

Sáu bản ghi mở rộng tri thức, không tạo master tiện ích trùng tên hoặc kích hoạt dịch vụ. Mô tả CSKH lịch sử chỉ lưu trong [nghiên cứu vòng 2](RESEARCH_DOMAIN_REFERENCE_EXPANSION_20261015.md), không nhập kho trả lời cư dân. Câu trả lời phí/giờ/đầu mối trong FAQ nhúng Market OP2/OP3 có `is_active:false` bị loại khỏi gói nhập; hostname chính thức không đủ chứng minh nội dung đó đang được xuất bản hoặc có hiệu lực.

Vòng 2 đã kiểm tra **18 tổ hợp truy vấn/site trên VPS**, cả 6 nội dung đều tìm thấy tại site tương ứng, **0 rò rỉ sang site khác**. Local kiểm tra 6 truy vấn trong OP1, tìm được 2 nội dung OP1, không trả nội dung mới OP2/3. Nhập lần hai `changed=0`. Fingerprint dữ liệu cũ giữ nguyên; chỉ loại timestamp heartbeat `worker_seen_at` khỏi so sánh, vẫn đối chiếu các cột cấu hình còn lại. Không gọi Agent/model/embedding.

Backup trước vòng 2: local **9.568.650 byte**, SHA-256 `b70ebaeed39fefe7742f0cc810d7f59ac8a7c35008c9e40f3097ae1b886069cb`; VPS **6.276.560 byte**, SHA-256 `bf42df65b7443635000f9657d36c3a499080ccad0167c775c7b8af2967b9245f`. Đã kiểm tra header và `pg_restore --list`, chưa chạy full restore. Gói 6 reference SHA-256 `21312bbf1a4ad6f5e466b62e76458412ee82303aec6176bd5e3c8cbbeb9bceb8`.

Bằng chứng vòng 2: `E:\Vinhomes-Deploy\reference-expansion-20261015\` và `/opt/vinhomes/releases/reference-expansion-20261015/`. Nạp vào PostgreSQL dùng API image đang chạy; không rebuild image, thay Compose hay cấu hình Platform. Danh sách thiếu 108 mục vẫn giữ nguyên vì chưa có xác nhận vận hành mới.

## Bổ sung vòng 3: hồ sơ lịch sử đúng cụm pilot

Đã đối chiếu 5 PDF gốc; các hồ sơ scan được render và đọc trang 1–2. [Gói dữ liệu mới](../../deploy/reference-data/op1-legal-technical-public-20261015.json) có 6 bản ghi:

| Nội dung | Cách sử dụng |
|---|---|
| Đối chiếu mã cụm B3-CT02: S1.01 ↔ L27M-2, S1.02 ↔ L27M-1, S1.03 ↔ Z28; hai khối L27M 27 tầng, Z28 28 tầng | Reference lịch sử từ thông báo nghiệm thu 12/11/2020; lưu 3 mục crosswalk trong metadata, không tạo căn hoặc đổi master |
| Hồ sơ chấp thuận nghiệm thu PCCC số 2550/PCCC&CNCH-P4 ngày 02/11/2020 | Reference lịch sử đúng cụm; không dùng để cam kết an toàn/thiết bị hoạt động hiện tại hoặc làm SOP ứng phó |
| Vai trò chủ đầu tư trong bản công khai OP1 ngày 21/06/2022 | Reference lịch sử; không tự gán pháp nhân phát triển Đô thị Gia Lâm thành operator hiện tại của tuyến Kỹ thuật |
| Ba bản tóm tắt ghi nhận lỗi bàn giao, hồ sơ bảo hành và hồ sơ cải tạo của mẫu **lô thương mại** | **Quarantined**, không được retrieval cho cư dân; không áp thời hạn, phí/ký quỹ hoặc bước duyệt của lô thương mại cho căn hộ S1.01 |

Đây là 3 nội dung mới có thể tra cứu và 3 bản lưu đối soát, không phải 6 SOP được kích hoạt. Compiler chỉ nhận trạng thái `reference`/`quarantined`, từ chối nguồn công khai tự gắn `approved`/`active` và từ chối mở retrieval cho mẫu thương mại trong pilot dân cư. Các bản đã có giữ nguyên ID/nội dung; runtime đã có bộ lọc quarantine nên không cần rebuild API image.

Nguồn và trang PDF: [nghiên cứu thủ tục kỹ thuật](RESEARCH_TECHNICAL_PROCEDURES_20261015.md). `source_issued_at` lưu ngày ghi trên văn bản, `source_published_at` vẫn null khi không biết ngày đăng; không suy ngày hiệu lực từ tên file. Không nhập tên người đại diện, tài khoản nhận tiền, hồ sơ người mua hoặc điều khoản thời hạn thành dữ liệu phục vụ cư dân.

Trên VPS, 18 tổ hợp query/site xác nhận 3 reference xuất hiện tại OP1; **0 bản thương mại cách ly xuất hiện**, không lẫn sang OP2/OP3. Local kiểm tra cùng 6 query tại OP1, chỉ 3 reference truy xuất được. Nhập lại `changed=0`; fingerprint toàn bộ dữ liệu được bảo vệ giữ nguyên ngoài heartbeat độc lập đã loại rõ khỏi so sánh. **0 cuộc gọi Agent/model/embedding**.

Backup vòng 3: local **9.571.983 byte**, SHA-256 `6c105e7ea6a29c83b101d51aa684c3e3c16cddbc9bd1a39ce095ba8b9378e8a6`; VPS **6.283.905 byte**, SHA-256 `584de313dca4188eaf265f8026280e7aac03802f688dcd3281542badc53e53df`. Kiểm tra header và `pg_restore --list`, chưa chạy full restore. Gói dữ liệu SHA-256 `ceccab0b1d5ca32333adac4b36a6be6aae616ce314f9d6b5002f30e8eb61fdb1`.

Bằng chứng: `E:\Vinhomes-Deploy\technical-procedures-20261015\` và `/opt/vinhomes/releases/technical-procedures-20261015/`. Danh sách thiếu vẫn **108 mục**: dịch vụ 39, SOP 48, và 21 mục về owner/địa bàn/tuyến/căn/cư trú/nhân sự/ca. Đối chiếu mã xây dựng làm tốt hơn bằng chứng địa bàn, nhưng không thay các xác nhận vận hành còn trống. Chưa tìm được nguồn gốc HomeCare hoặc SOP căn hộ hiện hành đủ điều kiện để nhập giá, lịch, SLA, roster hay mở tuyến.

## Còn thiếu gì để vận hành thật

| Ưu tiên | Dữ liệu/công việc cần bổ sung | Điều kiện hoàn tất |
|---|---|---|
| P0 | Đơn vị pháp lý, đầu mối vận hành, mã phân khu/tòa/căn và phạm vi thực tế | Văn bản có thẩm quyền, hiệu lực và mapping master rõ ràng; không tự sinh số căn từ số tầng |
| P0 | Hồ sơ cư trú | Danh sách tối thiểu được phép xử lý, căn, quan hệ, thời hạn và tham chiếu xác minh; không cần chuyển toàn bộ giấy tờ định danh |
| P0 | Nhân sự Kỹ thuật, chuyên môn, capacity, dự phòng và ca | Nhân viên chính/dự phòng thật, phạm vi và ca có hiệu lực, người dự phòng phủ ca chính |
| P0 | Dịch vụ điện/nước/HVAC | Chốt khả năng cung cấp, điều kiện, bảng phí/VAT, giờ, bảo hành, đặt/hủy, đầu mối và trách nhiệm từng loại thiết bị |
| P0 | SOP cư dân/staff | Chốt an toàn, khẩn cấp/chuyển cấp, ưu tiên, SLA, tiêu chí nghiệm thu; không dùng tiêu chuẩn bàn giao làm quy trình sửa chữa |
| P0 | Tuyến Platform và quyền MCP | URL/contract revision, route, scopes/grant và sự kiện hai backend đã nghiệm thu; cấu hình hiện tại chưa bật |
| P0 | Publisher staging → master/quyền/knowledge | **Chưa có**; cần triển khai đối soát, version/hiệu lực, activate/revoke và kiểm thử trên bộ owner đủ hồ sơ |
| P1 | OP2/OP3 | Sau nghiệm thu pilot, bổ sung master tòa/dãy/căn và chuỗi owner/nhân sự/dịch vụ/SOP riêng; không sao chép tiêu chuẩn OP1 |

`missing-data.csv` có **108 trường/hạng mục**, không phải 108 bản ghi đã nghiên cứu được. Nội dung đã điền là candidate, chưa thay số lượng master hoặc dịch vụ hoạt động trong database.

Platform chỉ nhận ngữ cảnh cần thiết từ ticket và truy cập MCP theo grant. Không bàn giao hàng loạt CSV cư dân, roster/ca hoặc hồ sơ xác minh. Platform quản lý session, giao việc, tiến độ và phản hồi; Domain giữ dữ liệu nguồn/quyền, ảnh và quyết định của cư dân. Không thêm bước BQL duyệt yêu cầu ở Domain.

**Kết luận:** phần có thể bổ sung từ nguồn công khai và khung phần mềm đã được thực hiện, nhập reference và kiểm thử. Dữ liệu production hiện sạch khỏi người/căn/ca demo, nhưng chưa đủ chuỗi vận hành thật. Hoàn thiện chuỗi này phụ thuộc hồ sơ có thẩm quyền và publisher; không thể thay bằng dữ liệu tự sinh được ghi là thật.
