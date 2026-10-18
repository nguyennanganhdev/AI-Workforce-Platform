# Bản sửa tài nguyên Agent/Team và công cụ BQL OP2 — 17/10/2026

## Phạm vi thực hiện

- Chuẩn bị MCP/skill/KB trong workspace riêng của version, sau đó CAS kích hoạt bản ghi agent. Publish/rollback lỗi không đổi phiên bản đang chạy. Builder chuẩn bị tất cả tài nguyên trước khi nhận claim phát hành một lần.
- Lưu workspace tài nguyên trong lịch sử version; session cá nhân và nhóm mới dùng cùng bộ tài nguyên được phát hành, ticket đã pin giữ version của nó. Lỗi lưu khai báo MCP được trả về thay vì bị bỏ qua ở bước chuẩn bị.
- Readiness API cho agent, trạng thái nhóm chưa sẵn sàng và chặn chat dùng AgentSpec chưa phát hành. Cấu hình nháp vẫn được lưu để BQL hoàn thiện.
- Sáu tool quản trị chỉ đọc: danh sách ticket phân trang, tổng hợp trạng thái, snapshot SLA, tải theo đội, tìm tài liệu, danh mục khả năng/giới hạn. Catalog MCP tăng từ 17 lên 23; ticket grant và management grant tách biệt.
- Binding Domain do người vận hành đặt theo tài khoản BQL, tenant/domain/area và site; có thể thu hẹp đến zone. Mỗi lượt chạy lấy tài khoản hiện hành từ auth DB, cấp grant đọc 15 phút, kiểm tra lại binding khi gọi tool; không tin khu do model đưa vào.
- Knowledge dạng văn bản có nguồn/version/hiệu lực, candidate/approved/retired, truy xuất lexical không embedding; có giao diện tạo kho, thêm tài liệu và xét duyệt. Giữ nguyên kho vector đang có.
- Skill nội bộ candidate/approved/revoked, snapshot/checksum archive tối đa 2 MB, cache sau khi bộ kiểm tra archive chấp nhận; dùng lại không phụ thuộc hub còn hoạt động. Builder lưu hướng dẫn sinh ra thành candidate riêng để BQL xem xét.
- Bộ bổ sung OP2: 12 tài liệu hướng dẫn phần mềm từ hợp đồng mã nguồn và tám skill workflow chờ BQL duyệt. Không chứa nội quy, giá hoặc chính sách vận hành tự đặt.

## Kiểm chứng không gọi model thật

Test bằng Docker `--network none` hoặc mạng Docker internal chỉ có PostgreSQL fixture. Không mount env thật vào container test. Model và classifier dùng provider giả. Không gọi Builder/evaluation/chat/embedding production để kiểm chứng.

- Suite Platform chính: 118 passed, 1 skipped khi chạy Redis/SQLite. Runtime nhiều agent trên PostgreSQL được chạy riêng và đạt; skip SQLite chỉ áp dụng runtime đồng thời.
- Suite kiểm tra lại sau thay đổi Builder và grant client: 66 passed.
- Suite mở rộng gồm manager client, cache integrity, publish fault injection, Builder conversation và Knowledge detail: 31 passed.
- Frontend TypeScript/Vite build và ESLint đạt; 26 test office đạt.
- Domain: kiểm tra trên PostgreSQL mới tạo, runtime role không có superuser/BYPASSRLS. Bao gồm bootstrap discovery, ticket grant, management grant, sai khu/quyền/hết hạn/thu hồi, phân trang, báo cáo và đọc tài liệu. Kết quả cuối ghi trong biên bản triển khai.

Đây là bằng chứng kỹ thuật/contract. Chất lượng câu trả lời model thật và business UAT chưa thực hiện theo lệnh cấm của người dùng.

## Triển khai và khôi phục

1. Build app/web/Domain từ commit đã push, ghi OCI revision, kiểm tra ảnh không chứa env/credential/artifact.
2. Platform: chạy backup bốn kho PostgreSQL, Redis, MinIO và workspaces; kiểm tra checksum. Lưu image ID và env cũ riêng tư, giữ rollback tag.
3. Domain: backup DB đang được API dùng, file và cấu hình riêng tư. Dừng API/platform-sync/scheduler khi snapshot, khởi động lại; giữ image cũ. Migration mới chỉ thêm bảng binding, không sửa ticket hay tài liệu hiện hữu.
4. Deploy Domain API/platform-sync/scheduler cùng image; chạy migration và cấp SELECT bảng binding cho runtime role. Chỉ thêm binding BQL OP2 đúng site OP2 và đơn vị quản lý đã cấu hình.
5. Deploy Platform app/web. Cài bộ tài liệu/skill bổ sung bằng script `scripts/workforce/install_op2_resource_pack.py --owner <OP2-user-id>`. Script đối chiếu tài khoản active AREA_MANAGER của OP2, thêm mới theo ID xác định; chạy lại không ghi đè nội dung có sẵn.
6. Đồng bộ lại catalog MCP của OP2; health/HTTPS và API đọc cấu hình. Không gửi chat model thật hoặc dùng tool ghi ticket.
7. Nếu smoke thất bại, đổi env về image đã ghi trước release và recreate dịch vụ liên quan. Migration bổ sung tương thích ngược, giữ bảng mới; không xóa dữ liệu mới để rollback image.

## Giới hạn còn cần dữ liệu/chấp thuận nghiệp vụ

- Agent audit vẫn draft: chưa có đánh giá model hợp lệ, không phát hành giả hoặc dùng provisioning để vượt cổng.
- Tài liệu Domain unverified giữ nguyên nhãn; BQL cần cung cấp/xét duyệt SOP, nội quy và biểu phí thật. 12 tài liệu bổ sung là hướng dẫn phần mềm, không thay thế tài liệu này.
- Thẻ, khách, tiện ích, sửa chữa và thanh toán chưa được mở thêm quyền ghi diện rộng trong bản này. Tool capabilities chỉ rõ phần hiện có và phần cần chuyển người phụ trách; không tuyên bố một giao dịch chưa tích hợp đã hoàn thành.
- Du lịch vẫn mock; chưa có adapter nhà cung cấp thật.
- Workspace chuẩn bị thất bại có thể để lại thư mục chưa được tham chiếu; không chứa phiên bản active. Chỉ dọn bằng đối chiếu lịch sử version, không xóa các release cũ đang pin trong ticket.
- CAS kích hoạt từng agent; Builder chuẩn bị toàn bộ trước claim nhưng không cung cấp transaction phân tán giữa nhiều agent và nhiều kho. Sau lỗi storage đúng lúc kích hoạt cần đối chiếu trạng thái từng agent trước khi tái phát hành.

## Kết quả triển khai và kiểm tra trên VPS

Mã chạy Platform: `90ad2c90265a1d0a032cb909e35ddc37e81f30b5`, đã push `develop2`. Nhánh đã nhận cả sửa Leader/Builder được triển khai song song. Khi chuẩn bị đổi container, VPS đã chạy đúng commit này; đối chiếu 942 file `src/` và `scripts/` trong container đều khớp, nên giữ container đó. Web có 473 file giống từng byte với bản đóng gói OP2, `index.html` chỉ khác một dòng trống.

| Thành phần | Image đang chạy |
| --- | --- |
| Platform app | `agentscope-platform:90ad2c90-leader-integrated-20261017` |
| Platform web | `agentscope-platform-web:02437150-leader-integrated-20261017` |
| Domain API / platform-sync / scheduler | `vinhomes-domain-api:9dd7504f-op2-capabilities-20261017` |

App Platform và Domain healthy; worker Domain chạy. HTTPS `/api/health` và `/chat/` trả 200. Migration Platform là `0020_unified_operation_owner`; Domain đã áp dụng `0025_platform_management_grants` và cấp SELECT cho runtime role. Health và API smoke không thay thế nghiệm thu UI/model/nghiệp vụ.

- [CI 39033342233](https://github.com/nguyennanganhdev/AI-Workforce-Platform/actions/runs/39033342233): kiểm tra đủ 10 JUnit, **1.580 test, 0 failure/error/skip**. D7 automated PASS; sandbox nghiệp vụ NOT_VERIFIED.
- Docker offline: 467 test và 23 subtest của console/evaluation/chat/team/Leader đạt. 11 lỗi ban đầu do image kiểm thử thiếu `lupa` cho `fakeredis[lua]`; cài đúng dependency rồi chạy lại toàn bộ suite đạt, không sửa Redis production để chiều fixture.
- Bộ OP2/publish fault injection/quyền/Knowledge/skill: 46 passed, 1 skipped trên SQLite. Runtime nhóm đồng thời được chạy riêng trên PostgreSQL và đạt; skip không được dùng làm bằng chứng PostgreSQL.
- Domain đã qua suite 32 test onboarding/MCP/management/travel và 6 test service context chạy riêng trên PostgreSQL fixture với runtime role hạn chế.
- Backup Platform mới: `/opt/awp-platform/backups/20261017T124108Z-awp-platform`, COMPLETE và 48 checksum hợp lệ. Khôi phục thử trong container cách ly đạt: migration/count PostgreSQL khớp, Redis/MinIO sẵn sàng, cả bốn kho PostgreSQL/Redis/MinIO/workspace phục hồi được; không khởi động app/model đã restore. Dữ liệu backup giữ riêng khỏi gói phát hành. Backup Domain trước sửa tại `/opt/vinhomes/backup/op2-before-9dd7504f-20261017`; bổ sung snapshot volume thật của api-files/MinIO sau deploy, checksum riêng `VOLUME_SHA256SUMS`, không gọi đó là snapshot trước deploy.

### Tài nguyên OP2 đã cấu hình

- Tạo kho lexical `Hướng dẫn Platform OP2` (`33673f23a9e6505d89f574f9de8c206f`) với **12 tài liệu kỹ thuật approved**, có nguồn/version; không tạo embedding. Gọi API search riêng kho này trả 3 kết quả có nguồn. Chạy lại installer tạo 0 bản trùng và không ghi đè tài liệu đã có.
- Thêm **8 skill workflow candidate, disabled**, chờ BQL duyệt. Hai skill có sẵn giữ nguyên; không tự gắn skill chưa duyệt vào agent.
- Đồng bộ catalog MCP tài khoản OP2: **23 tool**, gồm 6 tool quản trị chỉ đọc. Platform đọc danh tính hiện hành từ auth DB, lấy grant qua HTTPS Domain và gọi thành công cả 6 tool. Tại thời điểm kiểm tra, khoảng 01/10–18/10 trả tổng 9 ticket trong scope; kết quả có thể thay đổi theo dữ liệu. Truy vấn Knowledge Domain mặc định approved-only trả 0 vì chưa có tài liệu được xác minh; không tự nâng nhãn 384 tài liệu cũ.
- Snapshot runtime hiện hành không còn ba draft audit của lần khảo sát đầu. Tạo lại đúng ba cấu hình audit thuộc BQL OP2 bằng API, không khôi phục đè Redis và không đụng lịch sử người khác:

| Vai trò | Agent ID |
| --- | --- |
| Tiếp nhận / điều phối | `2e52d19342144f99b478e2b047f45815` |
| Chuyên viên | `f67f8562157b47a4a9de3269f810b469` |
| Phản biện | `d0cda1f417084a06ad071424f73fd1c0` |

Nhóm `AUDIT OP2 17-10 - Nhom xu ly va phan bien`: `e683899fc52e4d4c97e7a1fd7b531943`; phiên cá nhân: `b2aa1d89a5ca4fc2975cd6544649a3a4`. Các draft đã chọn kho lexical mới và 6 tool quản trị; chưa chọn skill candidate. Cả ba vẫn draft v0, `can_publish=false`, nhóm `ready=false`; không vượt cổng đánh giá. Ledger ba agent mới có **0 model call**. Đối chiếu hash trước/sau xác nhận **9 agent có sẵn không đổi** trong các bước cấu hình này.

### Gói Docker và việc còn cần nghiệm thu

Gói giao nhận: `E:\AWP-Releases\op2-capabilities-20261017-90ad2c90`. `platform-images.tar.gz` và `domain-images.tar.gz` chứa đúng image đang chạy nêu trên; có `Load-Images.ps1`, checksum, source và bằng chứng CI/API. Không chứa `.env`, credential hoặc backup dữ liệu khách hàng. Image đã chuyển và nạp trực tiếp lên VPS; không publish vào registry chưa được chỉ định.

Các sửa kỹ thuật đã chạy trên VPS. K01/K02 vẫn cần SOP/nội quy/biểu phí thật do BQL xét duyệt; M03 còn cần hợp đồng workflow và adapter ghi cho hệ thống nguồn/nhà cung cấp. Bộ tài liệu kỹ thuật và capabilities không thay các tích hợp đó. Chưa chạy chat/evaluation/embedding bằng model thật, chưa nghiệm thu thao tác UI thủ công hoặc chất lượng thảo luận của model. Những phần này được giữ nguyên trạng thái chưa nghiệm thu theo lệnh cấm kiểm thử model.
