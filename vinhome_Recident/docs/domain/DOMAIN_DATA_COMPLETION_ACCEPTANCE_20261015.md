# Nghiệm thu bổ sung dữ liệu Domain — 15/10/2026

Phạm vi: nhánh `dev_Vinhome`, pilot **OP1 → The Sapphire 1 → S1.01 → Kỹ thuật**. Đây là nghiệm thu nghiên cứu, chuẩn bị dữ liệu và nhập tài liệu tham khảo; **chưa phải nghiệm thu vận hành thật hoặc Agent/Platform thật**.

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
| Tài liệu / đoạn tri thức | **302 / 786** | Tăng 4 / 4 trong đợt này |
| Tài liệu reference / quarantined | 180 / 122 | Toàn bộ 302 còn cờ `unverified`; reference không phải quy định đã duyệt |
| Travel mock catalog / booking | 15 / 0 | Mô phỏng, không phải nhà cung cấp/đặt chỗ thật |
| Ticket / work order / MCP grant | 0 / 0 / 0 | Chưa có luồng nghiệp vụ đang chạy |
| Platform connection setting | 1 | `enabled=false`, URL chưa cấu hình |
| Migration mới nhất | 0023 | Có staging 0022 và resident assets 0023 |

Hai `management_units` là **Local Management** (cấu hình bootstrap, chưa xác minh đơn vị pháp lý) và **Nhà cung cấp Travel MÔ PHỎNG**. Không tính chúng là hai đơn vị vận hành đã được xác nhận. Ba coverage nền không thay hồ sơ tuyến/phân công thật.

| Khu | Phân khu | Tòa | Tài liệu sau import | Dịch vụ bật vận hành |
|---|---:|---:|---:|---:|
| OP1 | 9 | 30 | 233 | 0 |
| OP2 | 8 | 0 | 33 | 0 |
| OP3 | 8 | 0 | 36 | 0 |

Local dùng database `vinhomes`: **168 tài liệu / 652 đoạn** sau import, 720 user nhưng chỉ 15 account; 380 căn, 690 quan hệ cư trú, 26 staff và 1.405 ca, 945 ticket và 683 work order là dữ liệu lịch sử phục vụ test. Không chuyển dữ liệu này sang VPS hoặc gọi là hồ sơ thật. Số liệu local và VPS khác nhau có chủ đích.

## Bằng chứng kiểm thử và triển khai

- **82 kiểm thử đạt**, gồm candidate, nguồn tham khảo, nhập knowledge, pilot/staging, handoff v1, owner proposals, MCP v2 và schema. Ruff đạt cho Python thay đổi. Một cảnh báo Starlette TestClient, không có lỗi trong bộ đã chạy.
- PostgreSQL test riêng được tạo và gỡ cùng volume sau kiểm thử. Candidate thiếu hồ sơ trả `valid=false`; không được nhập staging hoặc mở dịch vụ thật. Happy case staging dùng dữ liệu synthetic chỉ ở database test riêng, không phải hồ sơ sản xuất.
- Runtime tìm đúng tài liệu mới tại OP1: ba nhóm truy vấn có lần lượt **2 / 1 / 1** kết quả mới. OP2 và OP3 đều **0** ở cùng các truy vấn. Đây là kiểm thử truy xuất dữ liệu, không phải đánh giá chất lượng hội thoại Agent.
- Backup PostgreSQL dạng custom trước import: local **9.561.326 byte**, VPS **6.270.353 byte**. Đã kiểm tra header và danh mục `pg_restore --list`; chưa chạy khôi phục toàn bộ backup.
- Đối chiếu fingerprint bảo toàn dữ liệu cũ. Trên VPS có thay đổi độc lập ở `platform_connection_settings.worker_seen_at` do worker heartbeat; đã đối chiếu bản COPY từ backup và xác nhận các cột cấu hình/credential khác giữ nguyên. Không coi timestamp heartbeat là dữ liệu bị importer sửa.
- Không thay Compose, credentials, API image hay Reception image trong đợt nhập dữ liệu này. Dữ liệu knowledge nằm trong PostgreSQL, không cần rebuild image để bản đang chạy đọc được. Không chạy bootstrap/seed để tránh phục hồi dữ liệu demo.
- **0 cuộc gọi Agent/model/embedding; không nghiệm thu Platform E2E**. Không tạo tài khoản, master căn, nhân sự, ca hoặc bật tuyến/dịch vụ từ bộ candidate.

Gói knowledge SHA-256: `bdc88143a91a9f57366c95ef851bd05cb858e01c8b386a3d2a34da620949ce2a`.

Backup VPS SHA-256: `50f86282e90d4efc9b6284cd94c99ed36567f4b957753768fddcb3e4d8675fc7`.

Backup local SHA-256: `22f0af4f2fb048c8ad92803a087f1afc874ad9b62c58009484db87b896d4a61d`.

Bằng chứng riêng trên máy: `E:\Vinhomes-Deploy\data-completion-20261015\` (inventory, source snapshots, candidate, backup, kết quả import và log test). VPS: `/opt/vinhomes/releases/data-completion-20261015/`. File chứa cấu hình bí mật/backup không đưa vào Git hoặc chuyển cho Platform.

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
