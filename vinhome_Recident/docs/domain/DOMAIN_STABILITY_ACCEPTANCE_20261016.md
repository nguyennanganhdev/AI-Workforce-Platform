# Nghiệm thu ổn định Domain — 16/10/2026

Phạm vi: nhánh `dev_Vinhome`, Domain tại Docker chính `http://localhost:8080` và VPS `https://vinhome-platform.duckdns.org`. Đã tái hiện và sửa lỗi logout, bổ sung hồi quy tiếp nhận yêu cầu, nâng schema và triển khai cùng bộ image lên hai môi trường. Không kiểm thử key, endpoint, onboarding, grant hay Agent Platform thật trong đợt này. Không thay đổi source Platform.

## Kết quả và giới hạn

Các kiểm thử Domain dưới đây đạt. Đây không phải nghiệm thu toàn bộ vận hành production hoặc chất lượng hội thoại với provider thật. Reception được kiểm thử bằng model giả; các kiểm thử giao tiếp Platform chỉ dùng transport giả cùng key fixture trong database riêng. Bridge VPS tiếp tục tắt; Docker local giữ cấu hình bridge đã có. Không đổi key hoặc thử gửi ticket mới từ hai database chính sang Platform.

## Logout và đăng nhập

Trước sửa, logout từ Operations đưa URL tới `/login` nhưng trang trắng. Tái hiện hai lần bằng Chrome headless; các asset staff vẫn trả 200 và không có JavaScript exception. Reload tài liệu thì trang login xuất hiện. Nguyên nhân là redirect cùng origin bên trong TanStack Router vẫn giữ SPA staff, trong khi `/login` thuộc app cư dân.

- Route `/operations/login` hiện dùng `reloadDocument: true` khi rời SPA staff; preview riêng vẫn giữ trang login preview.
- Hồ sơ cư dân trước đây chỉ có liên kết “Quản lý đăng nhập”. Đã thay bằng nút Đăng xuất: POST thu hồi session trước, sau đó `location.replace('/login')`. Lỗi mạng/server hiển thị tại chỗ và cho phép thử lại, không giả vờ đã đăng xuất.
- Chrome kiểm tra ba role admin/staff/customer, ở 1.280 px và 390 px; logout có form login, session cũ trả 401, Back không cho tiếp tục dùng trang cần đăng nhập. Kiểm tra thêm ba lần đăng nhập bằng form và truy cập trang bảo vệ sau khi thu hồi session. Mỗi runtime đạt 9 ca, không có page error hoặc tràn ngang trong các ca kiểm tra.
- HTML của `/login` và `/operations/`, cùng JS/CSS đầu vào được tải từ gateway, có SHA-256 trùng dist đã đóng gói. Đã xem ảnh chụp desktop/mobile của trang đăng nhập VPS.

401 ở API cần xác thực sau logout là hành vi đúng. Các cảnh báo `Permissions-Policy` về tính năng quảng cáo mà trình duyệt không nhận diện không gây ra lỗi điều hướng này; không đổi header để che nguyên nhân.

## Reception và nội dung ticket

Đã tái hiện việc hệ thống hỏi lại thiết bị khi model bỏ sót `item`, dù lời cư dân đã nêu rõ thiết bị hoặc vị trí. Trường hợp câu trả lời ngắn còn bị phụ thuộc vào model lặp lại chi tiết đã lưu.

- Bổ sung khôi phục các tên thiết bị/vị trí thông dụng xuất hiện nguyên văn trong câu báo lỗi hoặc câu trả lời làm rõ, sau khi đã có hiện tượng được báo. Mỗi chi tiết vẫn phải đi qua kiểm tra nguồn `source_message_id`, phủ định và mức cụ thể hiện có.
- Giữ chi tiết đã xác thực, không rút “chân vòi lavabo” thành một từ kém cụ thể hơn. Lời đính chính mới không bị claim cũ của model xóa mất.
- Không suy ra chẩn đoán, mức ưu tiên, danh tính hoặc căn hộ. Không biến câu giả định/câu hỏi thành chi tiết đã khẳng định; không kéo thiết bị trong tin cũ sang thay cho báo khẩn cấp mới.
- Từ ngoài danh mục tên thông dụng vẫn đi qua cơ chế claim nguyên văn của model. Thông tin thật sự thiếu vẫn được hỏi theo quy tắc hiện có; không bỏ kiểm tra chỉ để tạo ticket.

Ca tích hợp mới dùng database riêng: cư dân gửi “Ở bếp vòi lavabo bị rò nước từ sáng; đèn LED trên trần nhấp nháy liên tục. Kiểm tra cả hai giúp tôi.” kèm ảnh; model chỉ cung cấp hiện tượng/vị trí. Intake đạt ready, không hỏi lại; draft và ticket giữ nguyên cả hai hạng mục, ảnh được gắn vào đúng ticket. Những ca này chứng minh cơ chế backend, không chứng minh model thật luôn chọn đúng công cụ hoặc hiểu mọi diễn đạt.

Đã kiểm tra bộ test đóng gói: nội dung, ngữ cảnh cư dân đã xác minh, ảnh ban đầu/bổ sung, ảnh không kèm chữ, quyền truy cập, retry/idempotency, tránh trùng và thứ tự nhiều gói ảnh. Transport Platform trong test là giả, không xác nhận Platform thật đã nhận.

## Schema và Docker/VPS

Trước cập nhật, runtime dùng schema `0023` trong khi source có `0024_platform_command_order.sql`. Đã thử nâng 0023 → 0024 trên database riêng: giữ lệnh cũ, identity tiếp tục đúng sau backfill, migrate lần hai không thay đổi. Migration bổ sung `enqueue_seq` để lệnh bắt đầu đứng trước gói ảnh tiếp theo, không dựa vào UUID ngẫu nhiên khi cùng timestamp. Bộ test còn ép thứ tự UUID ngược với thứ tự chèn để kiểm tra ca 11 ảnh tách thành 10 + 1.

Release đang chạy: **`stability-20261016-196861080a3d`** cho `vinhomes-domain-api`, `vinhomes-domain-resident` và `vinhomes-domain-operations`; scheduler/platform-sync dùng cùng image API mới. Image Reception hiện có được giữ nguyên vì sửa intake nằm ở API. Cả hai runtime dùng schema `0024` sau cập nhật và đã cấp lại quyền schema cho role API hạn chế.

Trước migration có backup database định dạng PGDMP và bản sao env/image. Compose env của các service được đối chiếu trước và sau; không đổi cấu hình nghiệp vụ, secrets hoặc database đích. Không seed/reset hoặc xóa volume. Container Postgres, MinIO, Reception, gateway và backup được giữ nguyên; reload Nginx sau khi upstream được thay.

| Dữ liệu sau triển khai | Docker chính | VPS |
|---|---:|---:|
| User | 88 | 88 |
| Căn/lô | 14 | 14 |
| Hồ sơ staff | 72 | 72 |
| Tài liệu | 384 | 384 |
| Đoạn tri thức | 868 | 868 |
| Ticket | 4 | 1 |
| Work order | 1 | 0 |
| Platform link | 4 | 0 |
| Platform command | 5 | 0 |

Các số trên không đổi qua triển khai. Hai stack đều có 10 service đang chạy; tám service có healthcheck đều healthy. Scheduler/platform-sync không khai báo healthcheck, không tính “Up” của chúng là chứng minh đã giao dịch thành công với hệ thống ngoài.

## Kiểm thử

| Kiểm tra | Kết quả |
|---|---|
| Backend đầy đủ, database riêng với role hạn chế | **432 passed, 10 skipped**, không failed; khoảng 9 phút 10 giây ở lượt cuối |
| Reception offline, model giả | **381 passed, 10 skipped, 1 xfailed** |
| UI, chạy tách process từng file | **173 passed / 33 file** |
| Typecheck | Resident, staff, shared đạt |
| Build | Resident và staff đạt |
| HTTP nghiệp vụ, server/database riêng | **2 passed**: hoàn tất/retry/quyết định đồng thời và xử lý lại |
| MinIO thật, bucket kiểm thử riêng | **4 passed** |
| Direct upload thật qua MinIO | **1 passed**: checksum, finalize/replay, không ghi đè file đã chấp nhận |
| Nâng cấp 0023 → 0024 | Đạt; giữ lệnh, sequence và khả năng chạy lại |
| Chrome Docker chính | **9/9 đạt**; login/logout/session/Back, desktop/mobile, served artifact |
| Chrome VPS HTTPS | **9/9 đạt**, cùng bộ kiểm tra |
| Ruff ở file Python thay đổi và `git diff --check` | Đạt |

Mười bài backend bị skip gồm bốn bài cần MinIO, hai bài cần URL HTTP riêng và bốn bài password deployment cũ gắn cứng vào môi trường `.local-connected` cổng 3020/database 5544. Bốn bài MinIO và hai bài HTTP đã chạy riêng như bảng trên. Bốn bài deployment cũ không chạy lên database chính; đăng nhập/thu hồi phiên hiện tại được kiểm tra qua browser ba role ở cả hai runtime, cùng các test auth/onboarding chạy trong database riêng. Không cộng các bài chạy lại vào tổng “432 passed”. `xfailed` của Reception được giữ đúng trạng thái kỳ vọng, không tính là pass: port kiểu mới `src/tools` chưa tương thích envelope của graph; runtime hiện dùng `src/runtime/backend.py`. Đây là phần hợp nhất kiến trúc còn lại, chưa chuyển runtime sang port mới trong bản sửa này.

Các cảnh báo test hiện có gồm deprecation Starlette/httpx, metadata alias Pydantic và cache pytest không ghi được vì workspace mount read-only; không có bài failed trong lượt cuối. Fixture Toolbox của bài kiểm thử loop được cập nhật thuộc tính progress tùy chọn để khớp contract runtime, không sửa code chạy Agent vì lỗi fixture.

## Tài liệu và dữ liệu nghiệp vụ

Đã sửa [hướng dẫn connected runtime](../resident-web/07-connected-runtime.md): role admin/staff/customer hiện hành, logout qua hai ứng dụng, hostname cookie nhất quán, luồng Platform điều phối thay cho BQL duyệt tiếp nhận. [README triển khai](../../deploy/README.md) dẫn tới dữ liệu/tài khoản hiện tại và tách mục thế giới mẫu khỏi Docker chính/VPS. Kiểm tra ba tài liệu liên quan không có liên kết file nội bộ bị hỏng.

[Nghiệm thu chuẩn hóa dữ liệu](OPERATING_DATA_NORMALIZATION_ACCEPTANCE_20261016.md) là snapshot dữ liệu hiện hành. Các báo cáo theo ngày trước đó là lịch sử, không dùng số tool/database hoặc kết quả tích hợp cũ để khẳng định trạng thái hiện tại. Bộ dữ liệu vẫn giữ provenance: 384 tài liệu chưa được operator xác nhận, các hồ sơ đề xuất không trở thành hồ sơ cư trú/nhân sự/chính sách thật do sửa tên hiển thị. Các phí, giờ, SLA, pháp nhân, quyền cư trú và ca thật cần đơn vị vận hành xác nhận; Travel vẫn mô phỏng.

Chưa chạy provider Reception thật, chưa nghiệm thu lại Platform thật hoặc gửi email SMTP thật. Ba giới hạn này không được gọi là đã hoàn tất bằng thành công của bộ test offline. Theo yêu cầu hiện tại, không thử key/kết nối Platform.

## Bằng chứng và Git

Bằng chứng local nằm trong thư mục ignored `deploy/runtime-access-20261015/domain-stability/`: XML/log kiểm thử, Chrome JSON/ảnh chụp, manifest source/dist/image, checksum archive, backup và kết quả triển khai. Artifact VPS nằm tại `/opt/vinhomes/releases/domain-stability-stability-20261016-196861080a3d`; thư mục/file tạo với umask 077. Không đưa env, password, token, dump hoặc log riêng vào Git/tài liệu công khai.

Tại thời điểm nghiệm thu runtime, các thay đổi source/test/docs còn ở working tree `dev_Vinhome`; bước commit/PR được thực hiện sau nghiệm thu theo yêu cầu riêng. Image phát hành được định danh bằng manifest/hash; trạng thái commit và CI mới nhất xem PR #93 vào `develop2`. PR giữ toàn bộ cây `platform_VP` của nhánh đích, không mang lịch sử xóa Platform cũ ở nhánh Domain sang nhánh đích. Tài khoản, env và bằng chứng riêng tiếp tục nằm ngoài Git.
