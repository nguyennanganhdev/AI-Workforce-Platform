# Kết quả maintain domain Vinhomes — 13/10/2026

## Kết luận

**Đã triển khai các cập nhật domain và MCP lên Docker/VPS, nghiệm thu luồng nghiệp vụ không có Agent. Chưa hoàn tất HTTPS public vì CA timeout khi xác minh.** SMTP thật và test Agent/partner được để lại theo yêu cầu chủ dự án.

Phạm vi: dự án chính `E:\AI-Workforce-Platform`, nhánh `dev_Vinhome`; VPS `103.238.235.156`, tên miền `vinhome-platform.duckdns.org`. Kế hoạch/phạm vi đã chốt: [KE_HOACH_MAINTAIN_DOMAIN_20261013.md](KE_HOACH_MAINTAIN_DOMAIN_20261013.md).

Commit mã triển khai: `7fa9c02793728683d44f0d311c4701e772bf73fc`, đã push `origin/dev_Vinhome`. Tag chạy thực tế: `maintain-20261013-7fa9c027`; image ID giữ nguyên so với bản đã kiểm thử.

## 1. Đã cập nhật

| Hạng mục | Kết quả |
|---|---|
| Cư dân | Admin chọn căn hộ và quan hệ cư trú, xác minh cùng transaction duyệt account; retry không tạo trùng, sai căn hộ rollback; thu hồi liên kết giữ lịch sử và thu hồi phiên |
| Staff | Form/API hồ sơ nhân viên, đơn vị, mã nhân viên, chuyên môn, năng lực và ca làm; kiểm tra mã trùng/ca chồng lấn; đổi đơn vị khi còn việc bị chặn; khóa/chuyển role vô hiệu hồ sơ nhận việc |
| Account | Phân trang, tổng số, tìm kiếm/lọc server; UI chuyển trang và giới hạn bulk/CSV theo dữ liệu đang hiển thị; phân biệt active với đã xác minh căn hộ/có hồ sơ staff |
| Trạng thái cư dân | Phân biệt chờ duyệt và đã duyệt nhưng chờ căn hộ; đồng bộ logo Vinhomes; hướng dẫn đăng nhập lại sau thay đổi quyền |
| Khôi phục password | API/UI request và confirm, link 15 phút, token hash dùng một lần; đổi password thu hồi session/token cũ; kiểm thử hộp thư giả; SMTP thiếu cấu hình trả 503 rõ ràng |
| MCP | Catalog và declaration còn 7 tool cho ticket đã bàn giao; tool cư dân/căn hộ, khách, thẻ và booking không còn được đăng ký vào `/mcp` |
| Receipt MCP | Thêm hash nội dung cho lệnh mới; retry không ghi lặp, đổi nội dung cùng reference bị từ chối; receipt lịch sử chưa có hash giữ replay kết quả cũ |
| Docker | API và hai frontend đã build/deploy; API/init/scheduler/platform-sync dùng cùng tag; API bind loopback ngay cả khi gateway mở public |
| File riêng | Root Git ignore phần `platform_VP` chưa tracked; bảo vệ env/export/handoff/test artifact; không untrack hoặc commit thay đổi platform đã tracked |
| CI | Workflow kiểm tra domain/API/UI và HTTP E2E, không chạy Agent/model; hai job business-api và frontend đã đạt trên commit mã triển khai — [GitHub Actions 38395267306](https://github.com/nguyennanganhdev/AI-Workforce-Platform/actions/runs/38395267306) |

Migration mới: `0016_password_reset_tokens.sql`, `0017_platform_operation_payload.sql`. Các migration cũ được giữ nguyên. Đã áp migration và cấp quyền runtime đúng bảng cần ghi, vẫn giữ RLS theo tenant.

Account cư dân từng được báo lỗi được giữ nguyên theo yêu cầu mới. Không gán căn hộ mẫu, đổi password hoặc sửa quyền của account đó.

## 2. MCP sau maintain

| Tool | Trách nhiệm |
|---|---|
| `vh_ticket_get` | Đọc trạng thái xử lý mới nhất |
| `vh_knowledge_search` | Tra tài liệu liên quan trong scope ticket |
| `vh_staff_available` | Tìm staff phù hợp |
| `vh_work_order_dispatch` | Tạo/giao work order cho ticket hiện hữu |
| `vh_work_order_reschedule` | Đổi lịch khi trạng thái cho phép |
| `vh_ticket_cancel` | Hủy khi luật nghiệp vụ cho phép |
| `vh_ticket_add_note` | Bổ sung thông tin xử lý |

Domain đóng gói thông tin cư dân/căn hộ trong bàn giao. Platform không tạo lại ticket hoặc xác định lại identity; không được duyệt báo giá, tự QC hay xác nhận hoàn thành thay cư dân. Các bước duyệt hiện có được giữ nguyên.

Production đã kiểm tra Bearer và discovery, catalog đúng 7 tool; lời gọi các tool đã loại bị từ chối. Kiểm thử ghi/idempotency/scope chạy trên database riêng, không gọi tool ghi trên production.

Bộ handoff riêng trong `deploy/platform-handoff-20261013` và ZIP đã được cập nhật declaration/discovery 7 tool; giữ credential trong file ignored. Bên platform cần refresh catalog/grants trước khi dùng. Chưa tự áp cấu hình hoặc chạy leader phía platform.

## 3. Kiểm thử

| Nhóm | Kết quả cuối |
|---|---|
| Backend và HTTP nghiệp vụ | **44 ca độc lập đạt, 0 lỗi, 0 skip** trong phạm vi đã chọn |
| Resident frontend | **38 đạt, 0 lỗi** |
| Staff/BQL/admin frontend | **114 đạt, 0 lỗi**; file bị ảnh hưởng được chạy lại sau cập nhật |
| TypeScript và build hai frontend | Đạt |
| Form mới trên bundle | 320/390/768/1440 px: gửi đúng payload cư trú/staff, không tràn ngang/lỗi JavaScript |
| UI production | 24 màn hình, bốn vai trò đăng nhập 200; không ghi nhận lỗi JS/HTTP hoặc tràn ngang desktop/mobile |
| Public HTTP | `/`, `/login`, `/forgot-password`, `/operations/accounts`, API readiness đều 200; HTML hai frontend khớp bundle build |

44 ca backend/HTTP được gộp theo classname + test name từ các JUnit cuối, không cộng trùng các lượt regression/kiểm tra lại. Đây là phạm vi nghiệp vụ/auth/storage/MCP cần cho thay đổi, không phải toàn bộ test Agent của repository.

Luồng đã chạy với account cư dân và staff mới trên PostgreSQL riêng: đăng ký → pending → admin duyệt/xác minh đúng căn → đăng nhập lại → tạo ticket bằng API nghiệp vụ → BQL tạo/giao work order → staff nhận/đến nơi → báo giá → cư dân đồng ý → ảnh trước/sau → completed → QC → cư dân xác nhận đóng. Ca thiếu ảnh, sai actor/version và retry được kiểm tra. HTTP E2E còn kiểm tra hai quyết định đồng thời và nhánh làm lại giữ lịch sử.

Test không gửi chat message tới Reception, không gọi provider/model, không chạy test package Agent hoặc workflow leader thật. Browser production chỉ được phép đọc dữ liệu và login/logout; các lệnh ghi khác bị chặn trước khi rời trình duyệt. Kiểm tra production không thay thế nghiệm thu Agent sau này.

Một số lần chạy đầu phát hiện lỗi fixture quyền ghi, quyền xuất JUnit, API HTTP chưa ready và assertion UI cũ. Các lỗi đã được sửa/chạy lại; bảng ghi kết quả cuối, không gộp các lần lỗi thành pass. Warning còn lại chủ yếu từ dependency deprecation và pytest cache trên source mount read-only.

## 4. Deployment và dữ liệu

Đã build ba image `vinhomes-domain-api`, `vinhomes-domain-resident`, `vinhomes-domain-operations`; các tiến trình scheduler/platform-sync dùng image API mới. Docker Hub timeout nên API dựa trên image production có sẵn với dependency không đổi, hai web được đóng gói từ dist đã build theo lockfile. Image ID/source hash và asset phục vụ thực tế được kiểm tra, không chỉ xác nhận container healthy.

Đã backup PostgreSQL/MinIO bằng tác vụ hiện hữu, giữ thêm snapshot database và cấu hình trước release ở thư mục riêng trên VPS. Snapshot pg_dump đã được khôi phục thử vào PostgreSQL riêng và đối chiếu số dòng khớp baseline; database phục hồi thử được gỡ sau kiểm tra. Không restore đè production. Các test nghiệp vụ tạo database mới có migrate/seed/role riêng, không dùng account production để test ghi.

| Dữ liệu | Trước deploy | Sau deploy |
|---|---:|---:|
| Users | 721 | 721 |
| Password accounts | 16 | 16 |
| Memberships | 721 | 721 |
| Quan hệ cư trú | 690 | 690 |
| Hồ sơ staff | 26 | 26 |
| Tickets | 939 | 939 |
| Work orders | 677 | 677 |
| Files | 33 | 33 |

Reception, PostgreSQL, MinIO và backup giữ nguyên container ID. Không recreate Reception, không đổi provider/key/model. Không seed/reset hoặc xóa volume production. Account production được kiểm tra phân trang tới offset 600: trả 121 dòng cuối, tổng 721; tìm kiếm server tìm đúng account ngoài trang đầu.

Đã dọn 15 container và network kiểm thử riêng trên VPS; giữ nguyên container/volume production. HTTP tên miền và IP đều trả 200 sau khi chốt tag phát hành.

Tag/image ID, source hash, manifest và JUnit chi tiết nằm trong evidence riêng `deploy/test-accounts-20261013/domain-audit` và `/opt/vinhomes/releases/maintain-20261013`; không commit env, account export, snapshot hoặc log riêng. Báo cáo này có thể chia sẻ mà không chứa credential.

## 5. Phần còn lại

1. **HTTPS public chưa hoàn tất.** HTTP challenge đọc được từ máy kiểm tra, nhưng Let's Encrypt báo timeout khi kết nối tới VPS. Chưa xác nhận nguyên nhân cụ thể thuộc firewall, routing hay chính sách mạng. Đã chuẩn bị gateway Nginx TLS, bootstrap và script/timer renewal; chưa bật Secure cookie, redirect HTTPS hoặc timer gia hạn như thể đã có chứng chỉ. Cần mở đường xác minh CA hoặc cấu hình DNS challenge DuckDNS. Xem [deploy/HTTPS.md](../../deploy/HTTPS.md).
2. **SMTP thật để sau theo lựa chọn chủ dự án.** Code và hộp thư giả đã đạt; production giữ gửi email tắt. Khi có host/port/sender/credential riêng, cấu hình và kiểm tra delivery thật trên HTTPS.
3. **Agent/provider do chủ dự án tự test.** Lỗi provider 401 trong audit trước chưa được sửa hoặc kiểm tra lại trong đợt này; không tuyên bố AI đã hoạt động. Không thay global endpoint embeddings.
4. **Partner platform thật chưa nối.** Outbound URL vẫn trống; MCP discovery độc lập đã hoạt động. Khi có cấu hình, import catalog 7 tool và nghiệm thu ủy quyền/workflow/callback ở một đợt riêng.

Vì còn mục 1, chưa kết luận hosting public hoàn chỉnh 100%. Trước khi HTTPS đạt, dùng SSH tunnel cho MCP có Bearer; không dùng HTTP Internet để chuyển credential. Các tính năng ngoài MVP như thanh toán thật không được bổ sung trong đợt maintain này.
