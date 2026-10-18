# Sửa ranh giới chat cá nhân và Workforce Leader

## Nền mã được đối chiếu

Ngày 18/10/2026, VPS Platform chạy app/web `agentscope-platform:fe56707a-20261018` và `agentscope-platform-web:fe56707a-20261018`. Commit `fe56707a966864ec7915be30421762d30cba4d15` thuộc `develop2`.

Nhánh `origin/develop` ở `22b15ff93dab736546b37373c8b0a68d62a4d358`, chưa có module console/partner Leader hiện hành. Không thay nền production bằng nhánh này trong một bản sửa lỗi phiên. Các thay đổi N1/N2 trên `dev_Chien` được giữ riêng. Bản sửa nằm trong worktree/nhánh `fix/leader-personal-boundary-20261018`, dựa đúng mã VPS, chờ chốt nhánh phát hành theo yêu cầu người dùng.

## Nguyên nhân đã tái hiện

1. Bootstrap Leader dùng session mới nhất của agent, kể cả phiên BQL nội bộ bị ẩn khỏi danh sách. Ở tài khoản OP2, phiên được chọn là `472588cef25e0a5b3ff16e6f7e29609d`, trong khi phiên phiếu là `836ef67dcb2341568c3d6482a6f1d8c7`. Phiên nội bộ không có team; viewport không tìm được nó trong danh sách hiển thị, dẫn đến lịch sử/nhóm sai với dòng phiếu được nhìn thấy.
2. Danh sách Leader lấy mọi phiên của agent, nên hiện cả direct chat và phiên thành viên nhóm cá nhân. Test Redis và SQLite tái hiện việc lẫn danh sách; sửa lọc không xóa hay chuyển lịch sử cá nhân.
3. Runtime gắn `source=platform_chat` cho cả phiên xử lý phiếu đối tác và trao đổi BQL theo phiếu. Test kiểm tra prompt sau khi lắp runtime tái hiện ba ca sai nguồn.
4. Phiếu “Rò nước gần tủ điện” đã closed ở Domain, cùng link workflow closed. Các ID ticket/request/workflow khớp; HTTP 409 cấp grant là đúng. Platform vẫn chuẩn bị toàn bộ tool, gồm quyền ghi, trước khi lọc tool cho BQL; việc bị từ chối grant làm cả phiên BQL lỗi setup.

## Thay đổi

- Dùng cùng điều kiện phân loại cho bootstrap và `GET /sessions/?scope=leader`: bỏ personal, hidden management và các origin không phải phiên mở từ user. Các phiên phiếu cũ và phiên thử của Leader vẫn được giữ.
- Leader sidebar và viewport gửi `scope=leader`; React Query có cache key riêng với danh sách chat thường.
- Runtime lấy nguồn đối thoại từ middleware server: `partner_api` cho case/worker đối tác, `management` cho trao đổi BQL theo phiếu, giữ `platform_chat` cho chat thông thường. Không suy diễn audience từ nội dung người dùng.
- BQL chỉ xin grant cho các tool đọc trong hợp đồng/roster đã pin. Có `CaseEvidence` để đọc nguồn đã lưu trong cùng phiếu.
- Khi Domain trả 409 cho grant, phiên BQL chỉ còn nguồn lưu và chỉ dẫn rõ dữ liệu không phải trạng thái hiện hành. Không dùng bootstrap để gọi nghiệp vụ, không cấp grant mới ngoài scope, không mở lại phiếu. Luồng thực thi của agent vẫn dừng khi Domain thu hồi quyền; lỗi 401/403/5xx không bị chuyển thành quyền truy cập.

## Bằng chứng và giới hạn

- Test trước sửa: ba ca bootstrap/list lỗi; ba ca nguồn prompt lỗi; hai ca grant BQL lỗi vì yêu cầu cả tool ghi.
- Test sau sửa được ghi trong artifact riêng của bản sửa; dùng Docker network none, provider/transport giả, không mount env thật vào test offline.
- Bộ hồi quy cuối: 26 passed, gồm phân loại phiên Redis/SQL, nguồn prompt sau lắp runtime, grant đọc BQL, đọc bằng chứng khi 409 và luồng thao tác vẫn dừng khi grant bị thu hồi. Bộ chat cá nhân/nhóm và runtime liên quan: 49 passed, 1 SQLite skip; skip không được coi là nghiệm thu runtime đồng thời PostgreSQL.
- Frontend TypeScript/Vite build và kiểm tra production API `/api` đạt; ESLint đạt; 26 test văn phòng đạt. Chưa có phiên browser production khả dụng để thao tác UI bằng tay.
- Suite case đối tác đầy đủ: 38 passed, 7 subtests passed, gồm quyền tool, giao việc, sự kiện nhân viên, approval/resume, kết quả và đóng phiếu bằng provider/transport giả. Lượt chạy mở rộng đầu đã dừng để chạy lại suite này riêng với log tiến độ; chỉ lượt hoàn tất được tính là PASS.
- Preflight candidate chạy trong tiến trình Python riêng trên VPS, dùng SQL read-only; không thay file/container đang phục vụ. Phiếu closed chỉ có `CaseEvidence`; phiếu open có `CaseEvidence`, `vh_ticket_get`, `vh_knowledge_search`, `vh_staff_available`. Không gọi các tool nghiệp vụ hoặc model/embedding.
- Không xóa error message/lịch sử để làm như phiên cũ chưa từng lỗi. Không thay phiên bản agent hay trạng thái ticket/approval của cư dân.
- Chưa deploy cho đến khi chốt nền nhánh: yêu cầu mới nhắc `develop`, trong khi Docker/VPS hiện hành là `develop2`. Browser/UI thật và chất lượng trả lời model chưa được nghiệm thu.

## Bản sửa để kiểm tra

Mã ứng dụng đã commit/push: `a185cc2db41c2935446d89de5ad5e0b9fb543b4a`, nhánh `fix/leader-personal-boundary-20261018`. Image candidate app/web: `agentscope-platform:a185cc2d-leader-boundary-20261018` và `agentscope-platform-web:a185cc2d-leader-boundary-20261018`, build trên bản chuẩn `fe56707a`; chưa dùng cho container production.

Gói Docker: `E:\AWP-Releases\leader-boundary-a185cc2d-20261018`, có source, log test, checksum và script chỉ nạp image. Archive image SHA256: `06bd2a400a3201802f3806e5e679d8dc73b09c28510987583083b27ecf5d94a2`. Kiểm tra import candidate đạt; không có `.env` hay credential môi trường trong image. Source archive không chứa env thật, `.artifacts` hoặc node_modules.
