# Kế hoạch hoàn thiện domain Vinhomes sau kiểm thử ngày 13/10/2026

Trạng thái: **kế hoạch, chưa triển khai các hạng mục bên dưới**.

Phạm vi: `vinhome_Recident` tại `E:\AI-Workforce-Platform`, nhánh `dev_Vinhome`. Chỉ sửa domain và bộ Docker/deploy của domain; tích hợp platform là một mốc riêng khi có thông tin kết nối. Không dùng worktree mới.

Căn cứ: báo cáo kiểm thử `deploy/test-accounts-20261013/domain-audit/DOMAIN_AUDIT_20261013.md` và hợp đồng [NOI_WORKFORCE_V1.md](NOI_WORKFORCE_V1.md). Báo cáo và các file chứa tài khoản/snapshot nằm trong thư mục riêng đã được ignore; chúng không đi cùng bản clone Git thông thường. Tài liệu này không chứa credential.

## 1. Kết luận và mục tiêu

Ưu tiên hoàn thiện onboarding cư dân, cấu hình AI và onboarding nhân viên. Domain có nền nghiệp vụ đã được kiểm tra, nhưng chưa đủ điều kiện kết luận hoàn chỉnh chỉ từ container healthy hoặc các bộ test logic.

Mục tiêu nghiệm thu độc lập: **tài khoản cư dân mới đăng ký → admin duyệt và xác minh đúng căn hộ → đăng nhập bằng mật khẩu của mình → sử dụng Reception thật → tạo yêu cầu → BQL giao cho nhân viên mới có hồ sơ hợp lệ → xử lý, báo giá, bằng chứng, QC → cư dân xác nhận đóng hoặc yêu cầu làm lại**. Mọi bước giữ đúng phân quyền và lịch sử.

Mục tiêu hosting: tên miền phục vụ landing page, login, ứng dụng và MCP trên HTTPS; image đang chạy khớp bản phát hành; dữ liệu hiện có được bảo toàn; có kiểm tra phục hồi và đường quay lại bản cũ.

## 2. Baseline đã có — không làm lại

| Phần | Kết quả từ đợt audit 13/10/2026 | Giới hạn |
|---|---|---|
| Kiểm thử | 832 test đạt, 17 bỏ qua; TypeScript đạt | Một ca E2E nguyên bản chạy riêng còn lỗi endpoint legacy 404; số test không phải số chức năng độc lập |
| UI | 24 màn hình, bốn vai trò, viewport 1440/390 px không ghi nhận lỗi render hoặc tràn ngang | Chưa nhấn mọi thao tác ghi trên production |
| Nghiệp vụ | Chuỗi ticket/work order/báo giá/evidence/QC/đóng/làm lại đã chạy trên môi trường riêng | Chưa chứng minh toàn luồng AI/partner thật |
| MCP | 23 tools; discovery hoạt động; thiếu/sai Bearer bị 401 | Chưa nghiệm thu toàn bộ tools ghi hoặc workflow platform |
| Docker/VPS | Các container có healthcheck được kiểm tra đều healthy; các file API đã đối chiếu khớp source sau chuẩn hóa xuống dòng | Model upstream vẫn 401; hosting đang HTTP |
| Dữ liệu | 721 users, 16 password accounts ở cuối audit | Không tự cấp mật khẩu cho toàn bộ user mẫu |
| File riêng | Rule Git/Docker ignore đã bổ sung, commit `73bd1268` đã push | Không commit account export, env, snapshot hoặc log riêng |

Landing page và đường dẫn ứng dụng đã có; kế hoạch này không thiết kế lại toàn bộ giao diện. Các con số là snapshot của audit, cần kiểm tra lại lúc phát hành.

## 3. Danh sách cập nhật và thứ tự thực hiện

| ID | Mức | Hạng mục | Phụ thuộc | Điều kiện hoàn tất |
|---|---|---|---|---|
| U0 | Trước thay đổi | Chốt baseline, backup và môi trường kiểm thử riêng | Quyền truy cập hiện có | Backup phục hồi thử được; ghi nhận SHA, image và cấu hình không chứa secret |
| U1 | P1 | Duyệt cư dân kèm xác minh/liên kết căn hộ | U0 | Đăng ký mới đi hết onboarding; không truy cập căn hộ khác |
| U2 | P1 | Sửa provider Reception trên VPS | Endpoint/model/key hợp lệ, U0 | Provider và chat thật đạt, không trả fallback vì lỗi xác thực |
| U3 | P1 | Tạo staff kèm hồ sơ/chuyên môn/ca làm | U0, dữ liệu nhân sự | Staff mới xuất hiện đúng phạm vi và nhận việc theo điều kiện hợp lệ |
| U4 | P2 | Phân trang và tìm kiếm account phía server | U0 | Tìm được account ngoài 200 dòng; tổng và bộ lọc đúng phạm vi |
| U5 | Trước phát hành public đầy đủ | HTTPS và cookie an toàn | DNS, kết nối cổng 80/443, U0 | HTTPS hợp lệ, đường dẫn và MCP hoạt động, gia hạn chứng chỉ có kiểm tra |
| U6 | P2 | Quên mật khẩu self-service | U5, dịch vụ gửi email | Link dùng một lần, hết hạn đúng, đổi mật khẩu và thu hồi phiên cũ |
| U7 | Cùng U1/U3 | Thông báo trạng thái và giao diện mobile | Hợp đồng onboarding | Phân biệt chờ duyệt/chờ căn hộ/đã sẵn sàng; đồng bộ template Vinhomes |
| U8 | Cổng nghiệm thu mỗi đợt | Cập nhật E2E và các test đang bỏ qua | Hợp đồng hiện tại; U1–U7 theo phạm vi đợt | Ca bắt buộc thực sự chạy; toàn luồng tài khoản mới đạt |
| U9 | Sau nghiệm thu | Đóng gói, deploy và kiểm tra bản chạy | U8 của đợt tương ứng | Tag/digest khớp release, kiểm tra public đạt, dữ liệu nguyên vẹn |
| U10 | Có điều kiện | Nối platform và nghiệm thu partner | URL, key, callback và hợp đồng được cung cấp | Luồng MCP/ủy quyền/callback thật đạt; không cần sửa mã platform trong phạm vi này |

U5 là điều kiện phát hành public đầy đủ, dù trong audit được xếp P2. U2 có thể chuẩn bị độc lập với U1/U3; việc thử SMTP và partner phụ thuộc thông tin bên ngoài. Không cam kết ngày hoàn tất trước khi xác minh các phụ thuộc đó.

### U0. Chuẩn bị và bảo toàn dữ liệu

- Ghi nhận branch/commit, trạng thái Git, image/tag/digest, biến cấu hình cần thiết dưới dạng đã che secret, schema version và số liệu baseline.
- Sao lưu PostgreSQL, object MinIO, trạng thái Reception có lưu trữ và env theo quyền truy cập riêng. Kiểm tra phục hồi vào môi trường riêng, không ghi đè database đang dùng.
- Dùng database, bucket và account kiểm thử riêng. Production chỉ kiểm tra đọc và các thao tác đã xác định phạm vi; không seed lại thế giới mẫu.
- Giữ nguyên `.gitignore` ở root và các thay đổi khác của người dùng. Khi commit, stage danh sách file thuộc từng hạng mục.

### U1. Hoàn thiện duyệt cư dân

Vấn đề hiện tại: admin duyệt membership nhưng không tạo quan hệ căn hộ đã xác minh. Account được duyệt vẫn bị chặn tại màn xác minh.

**Cập nhật backend:**

- Dùng mô hình hiện có: user/account, membership, vai trò customer và `unit_residents`. Rà soát endpoint quản lý căn hộ hiện hữu để tái sử dụng; chỉ bổ sung API còn thiếu, không tạo mô hình cư trú song song.
- Cho người có quyền chọn đúng căn hộ và quan hệ `owner`/`tenant`/`household`, xác minh và ghi lịch sử. Kiểm tra tenant, phạm vi căn hộ và quyền người duyệt phía server.
- Duyệt kèm liên kết phải nhất quán trong transaction. Vẫn có thể duyệt tài khoản trước khi có căn hộ, nhưng phản hồi và UI phải thể hiện rõ chưa sẵn sàng dùng nghiệp vụ cư dân.
- Lặp thao tác không tạo quan hệ trùng; xử lý hai người duyệt đồng thời, căn hộ không hợp lệ, nhiều căn hộ và thay đổi/thu hồi quan hệ. Không đặt quy tắc một căn hộ chỉ có một cư dân.
- Trả thông tin trạng thái đủ để UI phân biệt membership pending, active nhưng chưa có căn hộ đã xác minh, và resident sẵn sàng. Không dùng một cờ active để đại diện cả ba.

**Cập nhật UI:** thêm chọn căn hộ/quan hệ và trạng thái xác minh trong màn admin account đang dùng; hiển thị rõ thiếu thông tin nào; giải thích cần đăng nhập lại khi phiên bị thu hồi sau thay đổi quyền.

**Vùng source:** `services/vinhomes-api/src/vinhomes_api/password_auth.py`, các API quản lý residency hiện hữu, `v3_resident.py`; `apps/staff-web/src/features/vinhomes-operations/connected/admin/Accounts.tsx`, `apps/staff-web/src/lib/admin/queries.ts`; `apps/resident-web/src/features/auth/auth-service.ts`, `ResidentAccountStatus.tsx`.

**Nghiệm thu:** đăng ký mới → pending → duyệt và xác minh căn hộ → đăng nhập lại → `/resident/me` có đúng căn hộ → mở ứng dụng và tạo yêu cầu được. Resident/staff/management không có quyền quản lý account bị từ chối; không đọc/ghi chéo tenant/căn hộ; thao tác lặp và đồng thời có kết quả nhất quán.

**Account đang báo lỗi:** `chiendao278@gmail.com` đã active nhưng có 0 căn hộ đã xác minh. Chỉ hoàn tất dữ liệu khi biết căn hộ thật và quan hệ cư trú; không gán căn hộ mẫu và không tự đổi mật khẩu gốc. Audit đã tái hiện login bằng bản sao với mật khẩu tạm, chưa thử mật khẩu gốc trên production.

### U2. Làm Reception chạy với provider thật

- Xác minh riêng `RECEPTION_MODEL_PROVIDER`, `RECEPTION_MODEL`, `RECEPTION_MODEL_API_KEY`, `RECEPTION_MODEL_BASE_URL` từ mạng VPS. HTTP 401 hiện tại chỉ chứng minh upstream từ chối xác thực; cần kiểm tra key, endpoint và cơ chế xác thực trước khi kết luận nguyên nhân.
- Chốt cấu hình deploy tại `deploy/deployment.env`; agent `.env` local đang khác production. Không sao chép mù cấu hình local nếu endpoint không reachable từ VPS.
- Giữ cấu hình chat Reception tách khỏi embeddings/RAG; không thay global endpoint chỉ để sửa lỗi chat.
- Sau khi cấu hình hợp lệ, recreate dịch vụ chịu ảnh hưởng. Nếu thay mã xử lý lỗi/diagnostics, build image Reception tương ứng.
- Giữ healthcheck tiến trình; bổ sung trạng thái provider suy giảm/log hoặc metric phân biệt fallback với kết quả AI thật. Không gọi model có tính phí ở mỗi lần healthcheck và không xuất key ra log/UI.

**Nghiệm thu:** provider 200 có cấu trúc phản hồi hợp lệ; model hỗ trợ tools/JSON mà runtime dùng; chat mới có trả lời thật; thử tra cứu tri thức đúng phạm vi và tạo/chuyển yêu cầu theo luồng domain đang hỗ trợ. Giả lập 401, timeout, 429/5xx để kiểm tra phản hồi và retry có giới hạn, không tạo ticket trùng. Provider hoạt động không đồng nghĩa platform leader đã kết nối.

**Vùng source/config:** `deploy/compose.yml`, env example nếu cần; `agents/reception/src/runtime/model.py`, runtime hiện hữu và API Reception nếu cần thông tin trạng thái. Credential thật chỉ nằm trong env riêng.

### U3. Hoàn thiện tài khoản nhân viên

- Tái sử dụng `staff_profiles`, `staff_specialties`, `staff_shifts`, role/scope hiện có. Tạo account và hồ sơ bằng một thao tác có kiểm soát, hoặc cho hoàn thiện hồ sơ account đã có; tránh hồ sơ trùng.
- Admin nhập đơn vị quản lý, mã nhân viên, chuyên môn, ca làm và thông số năng lực mà schema hỗ trợ. Kiểm tra thời gian ca, phạm vi đơn vị và giá trị hợp lệ.
- Hiển thị rõ account đăng nhập được nhưng chưa đủ điều kiện giao việc. Không tự sinh ca làm/chuyên môn giả để làm catalog có dữ liệu.
- Việc giao việc phải xét hồ sơ active, scope, chuyên môn, ca hợp lệ và giới hạn việc đồng thời; việc đã nhận và lịch sử không bị mất khi đổi role/khóa account.

**Nghiệm thu:** tạo staff mới → đăng nhập → có trong catalog đúng phạm vi → giao/nhận việc phù hợp. Thiếu hồ sơ/chuyên môn/ca hoặc đang hết năng lực thì không được coi là sẵn sàng; staff khác không thay đổi work order của người được giao.

**Vùng source:** API account, catalog/dispatch hiện hữu, màn connected admin account và form hồ sơ nhân viên. Chỉ thêm migration mới nếu ràng buộc hiện tại chưa đủ.

### U4. Danh sách account đầy đủ

- Thay giới hạn cố định 200 bằng API phân trang có page size giới hạn, thứ tự ổn định và metadata tổng số theo cùng bộ lọc/quyền. Giữ định dạng `items` và bổ sung metadata để giảm tác động tới client.
- Chuyển tìm kiếm/lọc vai trò, trạng thái và trạng thái onboarding sang server; UI có chuyển trang, loading, empty/error và giữ bộ lọc khi chuyển trang.
- Hiển thị khả năng đăng nhập bằng password riêng với readiness nghiệp vụ. Không suy diễn mọi user có password hoặc tự tạo password account.
- Thao tác hàng loạt, nếu đang có, phải nêu rõ tập account được chọn; không vô tình áp dụng cho các dòng chưa tải.

**Nghiệm thu:** fixture trên 200 account tìm được người ở trang cuối; không trùng/mất dòng khi phân trang trên dữ liệu ổn định; tổng khớp bộ lọc; tenant khác không xuất hiện; dữ liệu thay đổi thì UI có thể tải lại nhất quán.

### U5. HTTPS cho hosting và MCP

- Tiếp tục dùng Nginx gateway hiện có, không đưa Caddy trở lại. Bổ sung cấu hình TLS và cơ chế cấp/gia hạn chứng chỉ tự động phù hợp hạ tầng hiện tại.
- Xác minh DNS và khả năng truy cập cổng public 80/443 từ bên ngoài. Nếu xác minh qua HTTP bị chặn, kiểm tra nguyên nhân và lựa chọn cách xác minh DNS được hỗ trợ; không mặc định lỗi do firewall nhà cung cấp.
- Kiểm tra HTTPS trước, sau đó cập nhật public origin/allowed origins và bật `Secure` cookie; HTTP chuyển hướng HTTPS. Cấu hình trusted proxy theo chuỗi proxy thực tế.
- Giữ hoạt động `/`, `/login`, `/resident`, `/operations`, upload và MCP; kiểm tra chuyển tiếp Authorization, kết nối streaming và timeout hiện hữu.
- Cập nhật MCP handoff riêng sang URL HTTPS; kiểm tra key hiện tại, chỉ rotate nếu có lý do cụ thể. Không đưa secret handoff vào Git hoặc image.

**Nghiệm thu:** chứng chỉ hợp lệ trên máy ngoài VPS, login/session/logout và MCP hoạt động qua HTTPS, không mixed content hoặc redirect loop, cookie có thuộc tính đúng, quy trình gia hạn có kiểm tra và cảnh báo lỗi. Thử public endpoint trực tiếp, không chỉ qua SSH tunnel.

### U6. Khôi phục mật khẩu self-service

- Nối nút quên mật khẩu với API yêu cầu reset và xác nhận password mới; dùng email gửi link tới origin HTTPS đã cấu hình.
- Tận dụng cơ chế reset hiện hữu nếu có đủ bảo đảm. Token phải lưu dạng hash, có thời hạn, dùng một lần và có giới hạn tần suất; không gửi password qua email.
- Phản hồi yêu cầu reset thống nhất để tránh tiết lộ email tồn tại. Đổi password thành công phải vô hiệu token đã dùng và thu hồi session cũ; ghi audit không chứa token/password.
- Dịch vụ email dùng sender hợp lệ và credential riêng. Kiểm tra gửi thật vào hộp thư kiểm thử khi triển khai, không gửi tới các cư dân khác để thử.

**Nghiệm thu:** email kiểm thử nhận link đúng domain; link hợp lệ đổi được password; token hết hạn/đã dùng bị từ chối; password cũ và session cũ không dùng được; link không đăng nhập thành admin hoặc bỏ qua trạng thái cư trú.

### U7. Trạng thái, template và mobile

- Đồng bộ `ResidentAccountStatus` với logo/tokens Vinhomes đang dùng; tách nội dung “chờ duyệt tài khoản” và “đã duyệt, chờ xác minh căn hộ”. Hiển thị hướng xử lý cụ thể và tải lại trạng thái khi người dùng thử lại.
- Form mới của admin/staff có lỗi theo trường, thông báo lưu thành công/thất bại và ngăn submit trùng trong lúc xử lý.
- Kiểm tra 320, 390, 768 và 1440 px; danh sách/form dài không làm mất nút chính; hỗ trợ bàn phím, focus, label và trạng thái loading rõ.
- Bảo toàn landing/login, đường dẫn đang dùng và các liên kết hash cũ được hỗ trợ. Không thiết kế lại phần đã được nghiệm thu ngoài phạm vi cần sửa.

### U8. Kiểm thử và CI theo hợp đồng hiện tại

- Cập nhật `services/vinhomes-api/tests/test_resident_integration.py` theo hợp đồng domain hiện tại; bỏ phụ thuộc `/tickets/{id}/session` và close-approval legacy chỉ sau khi thay bằng assertion nghiệp vụ tương đương. Không khôi phục API cũ để làm test xanh.
- Test onboarding phải bắt đầu bằng account mới, không chỉ dùng account mẫu có sẵn unit/profile. Bổ sung các ca quyền, transaction, retry/đồng thời và thay đổi trạng thái nêu ở U1/U3/U4/U6.
- Tham số hóa bootstrap/URL cho các test HTTP còn ràng buộc database local. Chạy PostgreSQL với quyền ứng dụng thực tế, MinIO thật và dịch vụ riêng cho ca ghi dữ liệu.
- Phân loại 17 ca skip: fixture cần cấp để chạy, ca legacy cần sửa/loại bỏ có giải thích, và ca thuộc runtime không sử dụng. Không đổi skip sang pass hoặc xóa assertion chỉ để tăng số test xanh.
- CI chạy kiểm tra API, Reception, UI, TypeScript và E2E nghiệp vụ bắt buộc. Fake provider dùng cho CI thường lệ; probe provider thật là bước nghiệm thu được kiểm soát, không chạy mù trong mỗi test.
- Sau U1/U2/U3, chạy toàn chuỗi tài khoản mới ở mục 1, cả nhánh đóng thành công và làm lại. Partner workflow có cổng nghiệm thu riêng ở U10.

**Đầu ra:** kết quả test theo SHA, danh sách skip có lý do, ảnh UI và evidence private đã che dữ liệu; báo cáo tách kết quả local/môi trường riêng/production/public endpoint.

### U9. Đóng gói Docker và deploy từng đợt

1. Chốt commit theo danh sách file cho phép; xác nhận không có env/account export/snapshot trong Git và build context.
2. Build các image thực sự bị thay đổi: API, Reception, resident-web, staff-web; kiểm tra gateway khi đổi TLS. Dùng lockfile hiện có và tag theo release/SHA, ghi digest; không dựa vào `latest` để chứng minh bản đang chạy.
3. Chạy U8 trên image ứng viên. Mọi migration là file mới, ưu tiên bổ sung tương thích ngược; không sửa checksum migration đã áp.
4. Backup ngay trước phát hành và ghi version schema/image/cấu hình. Triển khai theo cửa sổ phù hợp, tránh chạy tải kiểm thử nặng cùng lúc với phục vụ người dùng trên VPS 4 GB.
5. Áp migration cần thiết và recreate đúng service; không `down -v`, reset DB, ghi đè object storage hoặc đổi dịch vụ platform.
6. Kiểm tra health/readiness, log đã che secret, image/digest thực tế, asset frontend được phục vụ, HTTPS public, các vai trò, onboarding và MCP. Không dùng một local build để kết luận VPS đã update.
7. Kiểm tra thêm CPU/RAM/swap, dung lượng, lỗi 5xx/provider và tác vụ backup sau deploy. Giữ bản cũ tới khi nghiệm thu đạt.

**Rollback:** giữ manifest/image/env của bản trước. Quay về image cũ khi migration tương thích; nếu schema không tương thích thì phải có phương án riêng trước khi deploy. Restore DB là thao tác khác, có thể mất dữ liệu phát sinh sau backup; không tự restore đè dữ liệu đang dùng chỉ vì rollback ứng dụng.

### U10. Nối platform sau khi có thông tin

- Giữ `VINHOMES_API_PLATFORM_URL` chưa cấu hình cho tới khi có endpoint/key/callback và quy tắc xác thực thống nhất. Trạng thái bridge tắt hiện tại là phạm vi đã chọn, không phải lỗi MCP discovery.
- Cập nhật cấu hình domain và bộ handoff riêng. Kiểm tra platform thực sự truy cập được MCP HTTPS, danh sách 23 tools và các schema đúng hợp đồng.
- Nghiệm thu quyền tenant/resource, token ủy quyền hết hạn, lệnh ghi có retry/idempotency, callback trùng/đến sai thứ tự, workflow leader thật và dữ liệu cập nhật tại domain.
- Khi platform không reachable, giao diện/diagnostics phải phản ánh đúng trạng thái và giữ dữ liệu bền vững theo hợp đồng; không tuyên bố workflow đã hoàn thành chỉ vì nhận request.

## 4. Các mốc phát hành đề xuất

| Mốc | Nội dung | Cổng chấp nhận |
|---|---|---|
| A — sửa luồng tài khoản và AI | U0, U1, U2, U3, U4, U7 và U8 liên quan | Account mới dùng được đúng nghiệp vụ; provider thật đạt; regression không lỗi; dữ liệu production được bảo toàn |
| B — chốt vận hành public | U5, U6, U8 toàn phạm vi, U9 | HTTPS, khôi phục password, backup/restore, full flow và kiểm tra bản chạy/public endpoint đạt |
| C — tích hợp platform | U10 và U8/U9 liên quan | Partner thật đạt, có evidence cả request/callback/quyền và recovery |

U5 có thể chuẩn bị sớm; mốc A nên nghiệm thu trong môi trường riêng hoặc qua kết nối quản trị bảo vệ trước khi mở rộng sử dụng public. Không coi mốc A đã đủ an toàn public khi HTTPS còn thiếu. Nếu tất cả phụ thuộc sẵn sàng, có thể gộp A/B thành một release sau nghiệm thu.

## 5. Thông tin cần bổ sung

| Thông tin | Đang có/chưa có | Dùng cho |
|---|---|---|
| VPS, SSH, tên miền | Đã có từ quá trình deploy | U0/U5/U9; kiểm tra lại kết nối lúc thực hiện |
| Căn hộ thật và quan hệ cư trú của account đang báo lỗi | Chưa có | Hoàn tất dữ liệu account sau U1; không cản việc xây luồng onboarding |
| Endpoint/model/key Reception có thể dùng từ VPS | Cấu hình hiện tại bị 401; cấu hình local khác | U2; lưu/cập nhật qua env riêng, không gửi key vào chat |
| Đơn vị, mã nhân viên, chuyên môn và ca làm | Cần chốt cho staff thật | U3; fixture riêng đủ để phát triển và test |
| Dịch vụ gửi email và sender | Chưa chốt | U6; credential riêng, email nhận kiểm thử được chỉ định |
| URL/key/callback platform | Cung cấp sau theo yêu cầu trước | U10; không chặn nghiệm thu domain độc lập |

Không cần gửi lại password account, private key SSH hoặc dữ liệu xuất toàn bộ người dùng để lập kế hoạch.

## 6. Điều kiện tuyên bố hoàn thiện

- [ ] Onboarding cư dân mới hoàn tất; account được duyệt không bị thông báo sai là còn chờ duyệt.
- [ ] Account báo lỗi được liên kết đúng căn hộ sau khi có dữ liệu thật và người dùng kiểm tra bằng password của mình.
- [ ] Reception trả lời qua provider thật, tools/context đúng phạm vi; fallback được nhận diện khi upstream lỗi.
- [ ] Staff mới có hồ sơ đúng và được giao/nhận việc theo điều kiện hợp lệ.
- [ ] Danh sách account phân trang/tìm kiếm đầy đủ; reset password self-service đạt.
- [ ] Canonical E2E mới và regression chạy trên bản ứng viên; không còn ca legacy thất bại chưa giải thích.
- [ ] Landing, login, ứng dụng và MCP chạy trên HTTPS public; UI mới đạt kiểm tra mobile.
- [ ] Image/asset thực tế trên VPS khớp release; migration, backup/restore và rollback được kiểm tra.
- [ ] Không mất dữ liệu hiện có, không mở rộng quyền sai, không commit/đóng gói credential.
- [ ] Nếu tuyên bố đã nối platform: hoàn tất thêm U10; discovery MCP không thay thế nghiệm thu partner.

Mỗi mốc kết thúc bằng báo cáo: thay đổi, SHA/tag/digest, kết quả kiểm thử, kết quả VPS/public và phần còn phụ thuộc. Chưa đánh dấu các checkbox chỉ từ kế hoạch này.
