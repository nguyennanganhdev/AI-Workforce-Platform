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
