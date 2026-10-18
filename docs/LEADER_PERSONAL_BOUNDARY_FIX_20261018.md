# Sửa ranh giới chat cá nhân và Workforce Leader

## Nền mã được đối chiếu

Ngày 18/10/2026, VPS Platform chạy app/web `agentscope-platform:fe56707a-20261018` và `agentscope-platform-web:fe56707a-20261018`. Commit `fe56707a966864ec7915be30421762d30cba4d15` thuộc `develop2`.

Nhánh `origin/develop` ở `22b15ff93dab736546b37373c8b0a68d62a4d358`, chưa có module console/partner Leader hiện hành. Người dùng đã chốt “Sửa đúng bản VPS hiện tại (develop2)”. Bản sửa dựa đúng mã VPS, đã push vào `develop2`; các thay đổi N1/N2 trên `dev_Chien` được giữ riêng bằng worktree `fix/leader-personal-boundary-20261018`.

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
- CI [39106769386](https://github.com/nguyennanganhdev/AI-Workforce-Platform/actions/runs/39106769386) tại `46fe98eb6ae5639f94428d213465cd6d50dc9846` đạt; đối chiếu đủ 10 JUnit: 1.533 tests, 0 failures, 0 errors, 0 skipped. Không suy ra PASS chỉ từ trạng thái job có `continue-on-error`.
- Đã deploy app/web trên VPS ngày 18/10/2026. Browser/UI production và chất lượng trả lời model chưa được nghiệm thu; không gọi model thật để test.

## Bản sửa để kiểm tra

Mã ứng dụng đã commit/push: `a185cc2db41c2935446d89de5ad5e0b9fb543b4a`, đã vào `develop2`. Image production app/web: `agentscope-platform:a185cc2d-leader-boundary-20261018` và `agentscope-platform-web:a185cc2d-leader-boundary-20261018`, build trên bản chuẩn `fe56707a`. Commit sau đó chỉ bổ sung tài liệu và chỉnh khoảng trắng test, không đổi mã runtime trong image.

Gói Docker: `E:\AWP-Releases\leader-boundary-a185cc2d-20261018`, có source, log test, checksum và script chỉ nạp image. Archive image SHA256: `801109ac5d544910500e5527d680d95ba4cf24b8e1b1395f7764a29623ae2fb4`. Kiểm tra import và hash 859 file nguồn đạt; `AWP_SOURCE_REVISION` khớp commit runtime. Không có `.env` hay credential môi trường trong image. Source archive không chứa env thật, `.artifacts` hoặc node_modules.

## Bằng chứng triển khai VPS

- Backup: `/var/backups/awp-platform/leader-boundary-a185cc2d-20261018/20261018T071509Z-awp-platform`, gồm đủ bốn kho và image phục hồi. Restore thử trong container riêng đạt: migration `0020_unified_operation_owner`, PostgreSQL counts khớp, 461 khóa Redis không TTL khớp cả giá trị, MinIO và workspace phục hồi được. Kiểm tra Redis dùng manifest khóa/giá trị bền vững để không nhầm khóa TTL hết hạn thành mất dữ liệu.
- Chỉ thay app/web; giữ nguyên ID container PostgreSQL/Redis/MinIO, mounts, networks và runtime env ngoài biến phiên bản nguồn. App healthy; HTTPS `/api/health`, `/chat/`, `/workforce/leader` trả 200. 859 file nguồn trong container khớp commit, chuẩn hóa CRLF/LF khi đối chiếu.
- Docker image ID trên VPS: app `sha256:b363055eca26b84b11dfda1af9e320b123a6452e3e807216b27f468db394b170`; web `sha256:a260402c0405d0f95616930d80d5238f9d80780d299071317ed1ab27ca5cb9fe`. Hai ID khớp config của archive đã kiểm checksum.
- Kiểm tra API bằng quyền tài khoản BQL Ocean Park 2: bootstrap chọn `836ef67dcb2341568c3d6482a6f1d8c7`; danh sách `scope=leader` có 6 phiên, không chứa 2 phiên personal và 2 phiên BQL ẩn. Phiếu được chọn có đúng team, 3 thành viên và 12 tin nhắn lịch sử. Danh sách thông thường vẫn có 8 phiên, giữ các phiên personal và 1 nhóm cá nhân; truy cập không xác thực trả 401.
- Kiểm tra setup runtime bằng code đang chạy: phiếu closed chỉ có `CaseEvidence`, báo không có truy xuất hiện hành; phiếu open có `CaseEvidence`, `vh_ticket_get`, `vh_knowledge_search`, `vh_staff_available`, đều read-only. Chỉ trao đổi grant điều khiển, không thực thi các tool nghiệp vụ.
- Hash agent/session/team/message của tài khoản OP2 khớp trước và sau deploy, đồng thời khớp trước và sau kiểm tra API. Không xóa lỗi cũ khỏi lịch sử, không gửi chat, không sửa ticket/approval, không gọi model/embedding để test. Việc đạt health/API/setup không thay thế nghiệm thu nghiệp vụ bằng model.
- Evidence riêng trên VPS: `/opt/awp-platform/releases/leader-boundary-a185cc2d-20261018/{vps-deployment.json,runtime-verification.json,restore-evidence.json,ci-verification.json}`; bản sao các file đã loại thông tin nhạy cảm nằm trong gói phát hành. Backup/env/inspect chứa bí mật chỉ giữ riêng trên VPS.
