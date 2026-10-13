# Kết quả maintain domain/MCP — 13/10/2026

## 1. Quyết định nghiệp vụ

Làm tại dự án chính, nhánh `dev_Vinhome`. Luồng mục tiêu: cư dân → domain xác thực/tiếp nhận/tạo ticket → platform tự tạo session và quản lý điều phối, tiến độ, ngoại lệ → domain thực thi nghiệp vụ và ghi dữ liệu → trả tiến độ/kết quả cho platform và cư dân.

**Không có BQL nhận/duyệt yêu cầu trước khi platform tạo session. Không triển khai màn hình/hàng đợi tiếp nhận BQL hoặc tool escalation sang BQL tại domain.** Đề xuất này trong nghiên cứu ban đầu đã được bỏ trước deploy. Các loại ticket qua điểm bàn giao hiện tại đều được xếp `start_workflow` khi bridge bật, kể cả incident an ninh thông thường; gọi bàn giao lại không tạo thêm link/lệnh start. Quyền tiếp nhận session không đồng nghĩa quyền điều động bảo vệ hoặc bỏ qua duyệt phương án, báo giá, QC và xác nhận hoàn thành hiện có.

Các thao tác cư dân đang đi trực tiếp qua API booking/thẻ/khách ngoài điểm bàn giao ticket chưa tự trở thành session. Bản này chưa tuyên bố phủ mọi dịch vụ bằng 7 tool hoặc đã kết nối platform thật.

## 2. Chức năng đã thực hiện

- Catalog đúng 7 tool sau bàn giao: `vh_ticket_get`, `vh_knowledge_search`, `vh_staff_available`, `vh_work_order_dispatch`, `vh_work_order_reschedule`, `vh_ticket_cancel`, `vh_ticket_add_note`. Không có tool tạo lại ticket hoặc xác định lại cư dân/căn hộ.
- Backend platform tự lấy grant qua `POST /api/business/platform/mcp-grants` theo ticket/start-command/workflow. Bootstrap token dành cho control-plane/discovery; không trực tiếp gọi tool nghiệp vụ. Không có BQL cấp grant thủ công trong flow hàng ngày.
- Runtime bearer có ticket/management/workflow/tool scope, hash trong DB, expiry/revocation. Retry cấp grant giữ nguyên ID/nội dung trả cùng credential/expiry; không gia hạn âm thầm. Policy phản ánh cả nghiệp vụ lẫn quyền grant.
- Lệnh ghi mới cần version, kiểm tra lại trạng thái trong transaction; receipt/hash payload chống ghi trùng hoặc đổi nội dung khi retry. Hủy/đổi lịch kiểm nguồn tin nhắn cư dân. Không diễn giải text thành nút đồng ý báo giá/kết quả.
- Typed output/error, correlation, `isError`, request/output limit, timeout, quota và Host/Origin allowlist. Mất acknowledgement không được báo chắc rằng chưa có side effect.
- Snapshot có version/ID, policy, SLA, trạng thái xác nhận cư dân riêng; lịch sử phân trang. Tra ca theo giờ hẹn và kiểm lại khi offer; không hứa đã giữ lịch từ kết quả tra nhân viên.
- Handover v1.1, declaration v2, allowlist 7 tên. Notice/SLA chống trùng qua text contract hiện có; không tự thêm event type partner chưa chấp nhận.
- DNS-01 hook DuckDNS giữ token riêng, chỉ TXT, không đổi A record. Nginx TLS dùng cùng routes; HTTP public chuyển HTTPS. Listener HTTP nội bộ riêng giữ SSH tunnel hiện hữu; cookie đăng nhập public bật Secure.

Wire contract và cách chuyển credential: [MCP_PLATFORM_V2.md](MCP_PLATFORM_V2.md).

## 3. Kiểm chứng thực tế

| Lớp kiểm tra | Kết quả | Phạm vi |
|---|---|---|
| Regression API/domain r5 | 53 passed, 106.55 giây | Account/onboarding/admin/password recovery/RBAC/browser origin/dispatch/notification/MCP; PostgreSQL và MinIO riêng |
| Kiểm tra bổ sung bản cuối r7 | 18 passed, 19.15 giây | MCP/grant tự động/CAS/receipt/scope/Host/quota, handover an ninh idempotent, vẫn chặn dispatch vượt quyền, hook DNS offline |
| HTTP nghiệp vụ r5 | 2 passed | Báo giá → bằng chứng → QC → resolved → cư dân đồng ý đóng hoặc yêu cầu làm lại; kiểm cả MCP snapshot xác nhận |
| Resident UI hiện tại | 38 passed / 9 files | Chạy từng file riêng; không còn màn hình BQL thử nghiệm |
| Staff UI hiện tại | 114 passed / 19 files | Chạy từng file riêng; không cộng hai test đã bỏ cùng màn hình BQL |
| Typecheck | Hai web đạt | Source frontend không thay đổi so với bản đã deploy trước maintain này |
| Production HTTPS | Đạt | Landing, login, forgot-password, operations, API ready trả 200; HTTP root308 sang HTTPS; certificate được client ngoài VPS xác minh |
| Production auth | Đạt | Account test khác account người dùng đã yêu cầu bỏ qua: login/session/logout, cookie Secure/HttpOnly, logout xong session401 |
| Production MCP | Đạt ở mức domain | Initialize protocol2025-03-26, đúng7 tool có outputSchema; bootstrap gọi nghiệp vụ bị từ chối; cấp grant không auth bị401; SSH tunnel cũ vẫn dùng được |

53 và18 là hai lượt test có phần giao nhau, không cộng thành71 test độc lập. Lượt18 bổ sung xác minh thay đổi sau lượt53. Không chạy Agent, model/provider API hoặc embeddings; không coi fixture/mock partner là nghiệm thu platform thật.

## 4. Docker/VPS đã cập nhật

- Source chức năng: `25f580e7bc03f8b762b4250abe63622021cc287b`, đã push `origin/dev_Vinhome`.
- API image: `vinhomes-domain-api:mcp-v2-20261013-25f580e7`.
- Image ID: `sha256:16fe7be30023d00003aaa3fff76af6af1160d3d6aa35cd7f9c7bb50545e29b09`.
- API, scheduler và platform-sync đã dùng image này. API/gateway healthy; scheduler/platform-sync running, chưa có healthcheck riêng.
- Source `platform.py` trong container có SHA256 `ebd04c10ba8e53b3c7f0e697e1982122a4f9f8eced80073393ef41298b54b5d6`, khớp byte source commit.
- Migration `0018_platform_mcp_grants` đã chạy; runtime API không superuser/không bypassRLS, grant table FORCE RLS, chỉ SELECT/INSERT, không UPDATE.
- Nginx public80/443; private HTTP host127.0.0.1:8080 → container8081; SSH localhost18080 vẫn hoạt động. API/PostgreSQL giữ loopback; MinIO không public.
- Giữ nguyên container/image resident, operations, Reception, PostgreSQL, MinIO và backup. Frontend served entrypoint đã so byte với container, không chỉ dựa vào tag/build local.
- Backup domain trước release đã chạy; lưu thêm PostgreSQL custom dump riêng và kiểm tra `pg_restore --list`. Không gọi đây là một lần full restore mới.

| Dữ liệu nghiệp vụ | Trước | Sau deploy |
|---|---:|---:|
| users | 721 | 721 |
| accounts | 16 | 16 |
| tenant_memberships | 721 | 721 |
| unit_residents | 690 | 690 |
| staff_profiles | 26 | 26 |
| tickets | 939 | 939 |
| work_orders | 677 | 677 |
| files | 33 | 33 |

Login/logout acceptance tạo/xóa session theo nghiệp vụ; số trên là các bảng nghiệp vụ đã đối chiếu, không phải tuyên bố mọi byte DB bất biến. Đã lưu evidence riêng rồi gỡ12 container test và network test; không chạm volume/container production.

## 5. HTTPS và gia hạn: phần nào đã đạt

Trang đang dùng: **https://vinhome-platform.duckdns.org/**. Chứng chỉ Let's Encrypt thật có hạn đến **11/01/2027 15:17:20UTC**. TLS/cookieSecure/login đã xác minh từ máy ngoài VPS, kể cả sau khi dừng relay DNS tạm. Không dùng Caddy.

Đã cài timer `vinhomes-tls-renew.timer` active, script dùng đúng custom config/work/log dirs. Tuy nhiên **gia hạn tự động chưa được nghiệm thu**:

1. VPS truy cập HTTPS DuckDNS trực tiếp vẫn thất bại; OUTPUT chain ACCEPT chưa chứng minh nguyên nhân thuộc nhà cung cấp.
2. Staging DNS-01 từng đạt và chứng chỉ production cấp thành công qua relay SSH loopback tạm, TLS end-to-end. Lượt `renew --dry-run` sau deploy thất bại với ACME `authorization must be pending`; không báo lượt này đạt hoặc suy ra nguyên nhân cuối cùng khi chưa chốt.
3. Relay/proxy SSH tạm đã dừng, không lưu thành dependency server. Cần xử lý mạng DuckDNS và kiểm `renew --dry-run` trực tiếp trước khi xác nhận vận hành gia hạn hoàn chỉnh; theo dõi hạn chứng chỉ và log timer trong thời gian chờ.

Runbook: [deploy/HTTPS.md](../../deploy/HTTPS.md). Certbot hướng dẫn kiểm renew bằng dry-run và manual hooks tại [tài liệu chính thức](https://eff-certbot.readthedocs.io/en/stable/using.html#manual).

## 6. Bàn giao platform và việc còn lại

Bộ riêng `deploy/platform-handoff-20261013/` đã refresh HTTPS, declaration7 tool, live tools-discovery/outputSchema, wire contract, request cấp grant mẫu và template MCP runtime theo workflow; ZIP đã cập nhật. Secret/bootstrap nằm trong folder ignored, không vào commit hoặc tài liệu public.

| Việc tiếp theo | Bên thực hiện / điều kiện |
|---|---|
| Chốt URL/version/contract/protocol của platform thật | Nhóm platform cung cấp; cấu hình ngoài model/prompt |
| Adapter lấy grant và gắn bearer từng session | Backend platform; không dùng chung bootstrap để gọi tool nghiệp vụ |
| Onboarding/ủy quyền route một lần, bật bridge và nghiệm thu | Hai bên phối hợp trên sandbox trước; đây không phải BQL duyệt từng ticket |
| Kiểm ticket → session → MCP → progress → resident confirmation thật | Chỉ sau khi có adapter/endpoint; domain fixture không thay bài này |
| Hoàn tất renew trực tiếp | Xử lý kết nối DuckDNS và lỗi staging, kiểm dry-run, theo dõi hạn cert |
| SMTP production | Cấu hình riêng sau theo quyết định chủ dự án; hiện vẫn tắt |
| Agent/provider/leader | Chủ dự án tự cấu hình/test; không tự chạy trong đợt này |
| Route dịch vụ ngoài ticket, ảnh/attachment, adoption job thủ công, phương án nhiều đội | Ngoài scope hiện tại; chốt contract trước khi mở rộng |

`VINHOMES_API_PLATFORM_URL` trên API/platform-sync vẫn trống, nên outbound bridge chưa bật. Kết quả đợt này là **domain đã triển khai và kiểm chứng phần MCP v2/HTTPS**, chưa phải platform thật đã quản lý session end-to-end hoặc gia hạn chứng chỉ đã tự động hoàn chỉnh. Thay đổi riêng bên platform và việc xóa Caddyfile trong working tree không nằm trong commit này.
