# Chốt phạm vi MCP, nhân viên Vệ sinh và dữ liệu CSKH — 2026-10-14

Phạm vi source: `dev_Vinhome`, domain `vinhome_Recident`. Không sửa Platform. Chủ dự án xác nhận bổ sung Vệ sinh ngay, dùng cùng Local Management và phạm vi Kỹ thuật hiện tại; cho phép tạo tài khoản nhân viên, chuyên môn, ca và phạm vi khởi tạo. Không chạy model/Agent/provider thật trong đợt nghiệm thu này.

## 1. Phạm vi nghiệp vụ chốt

| Nhóm | Tiếp nhận ticket/session | Platform thực thi | Điều kiện còn giữ |
|---|---|---|---|
| Kỹ thuật | Domain xác thực, đóng gói ticket; bridge gửi start_workflow | Tra cứu, tìm staff, giao việc, đổi lịch, hủy trong giới hạn, ghi chú | Chuyên môn, ca, tải, quyền theo tòa; báo giá/nghiệm thu do cư dân quyết định; ticket yêu cầu plan giữ bước duyệt hiện có |
| Vệ sinh theo phản ánh | Cùng luồng ticket, mã `sanitation` | Cùng bộ 7 tool, giao nhân viên Vệ sinh đúng phạm vi | Phương án/chi phí phải được xác nhận theo luồng hiện tại; ảnh trước/sau và nghiệm thu; không coi vệ sinh mặc định miễn phí |
| An ninh | Ticket vẫn được bàn giao khi bridge bật | Tra cứu/ghi chú; điều động giữ quyền BQL hiện có | `SECURITY_MANAGEMENT_ONLY`; không bỏ quyền điều động an ninh để giả định đã tự động hóa |
| Vệ sinh định kỳ, hóa chất, trên cao, cảnh quan | Chưa có adapter Platform được nghiệm thu | Chưa mở tool riêng | Cần SOP an toàn, nhân sự/chứng nhận, lịch, phạm vi, tiêu chí nghiệm thu và quyền duyệt riêng |
| Booking, thẻ, khách, công nợ | Chức năng riêng tại domain | Không xuất thao tác Reception sang MCP Platform | Cần route/adapter/ủy quyền và chống trùng giao dịch trước khi mở rộng |

**Không có bước BQL duyệt từng yêu cầu cư dân trước khi tạo session.** Quyền duyệt kế hoạch đặc biệt, điều động An ninh, báo giá và nghiệm thu là các quyền nghiệp vụ khác, không phải hàng đợi tiếp nhận BQL.

Tuyến được chốt: `management_ref=local-management`. Bảy tòa hiện có coverage Kỹ thuật: `S1.01`, `S1.02`, `S2.01`, `S2.05`, `R1.02`, `HA2`, `SB1`. Vệ sinh dùng đúng bảy scope này, không tự mở rộng sang cả 16 tòa trong DB. Tài khoản khởi tạo mang role **staff** và specialty **sanitation**, không cần role RBAC mới hoặc quyền management/admin.

## 2. Bộ MCP bàn giao chính thức: 7 tool

| Tool | Cung cấp gì | Quyền/gate |
|---|---|---|
| `vh_ticket_get` | Snapshot ticket, phiên bản, công việc, người nhận/ETA, báo giá, mốc tiến độ, số ảnh, trạng thái xác nhận cư dân | Chỉ ticket trong grant; luôn đọc mới trước lệnh ghi |
| `vh_knowledge_search` | Đoạn tài liệu nghiệp vụ theo ticket/khu và nguồn/provenance | Phân biệt tài liệu tham khảo và đã duyệt; không tự tạo phí/giờ/hotline |
| `vh_staff_available` | Người phù hợp chuyên môn, đơn vị, scope, ca và tải hiện tại/giờ hẹn | Chỉ là ảnh chụp khả dụng, chưa giữ chỗ |
| `vh_work_order_dispatch` | Tạo work order, mời staff; trả pending/queued/failed | CAS ticket_version, receipt/client_reference; không bypass plan/An ninh; queued chưa có người nhận |
| `vh_work_order_reschedule` | Đổi lịch work order trong điều kiện cho phép | CAS + source_message_id hợp lệ từ chính cư dân/ticket; không bịa sự đồng ý |
| `vh_ticket_cancel` | Hủy khi trạng thái/quyền cho phép | CAS + nguồn yêu cầu cư dân; chặn An ninh và công việc đã tới hiện trường theo policy |
| `vh_ticket_add_note` | Chuyển thông tin bổ sung trong phạm vi ticket | CAS, receipt; ghi chú không thay thao tác giao việc hoặc đồng ý báo giá |

Vệ sinh mở rộng **nghiệp vụ và dữ liệu**, không tăng số tool. Không đưa vào catalog: tạo ticket, xác định lại căn hộ/cư dân, phê duyệt thay cư dân, cấp thẻ, đăng ký khách, tạo booking hoặc sửa công nợ. Các hàm Python nội bộ không nằm trong allowlist không phải tool được cung cấp ra MCP.

### Transport và bảo mật phải nối ở backend Platform

- Endpoint MCP: `https://vinhome-platform.duckdns.org/mcp`, Streamable HTTP, schema `vinhomes-mcp-v2`.
- Bootstrap token chỉ discovery/control plane, không được gọi nghiệp vụ. Không đưa token/grant vào prompt.
- Backend nhận start_workflow và tạo workflow, gọi `POST /api/business/platform/mcp-grants` bằng bootstrap Bearer, gửi `ticket_id`, `external_request_id`, `workflow_id`, `grant_request_id`, danh sách tool và TTL. Mỗi workflow giữ grant riêng trong transport. Không dùng một grant ticket cho toàn bộ server MCP.
- Retry cấp grant dùng cùng grant_request_id/payload; retry lệnh ghi dùng cùng client_reference/payload. Lệnh mới đọc ticket_version mới. Kiểm tra `isError`, `structuredContent`, mã lỗi/retryable; HTTP200 không đồng nghĩa nghiệp vụ thành công.
- Cư dân tự quyết định báo giá và hoàn thành bằng UI domain. Nếu Platform có lớp consent công cụ riêng, phải phân biệt nó với các quyết định nghiệp vụ này; không biến cấu hình quyền một lần thành BQL duyệt từng ticket.

## 3. Agent gửi việc cho staff và nhận phản hồi

1. Reception tạo ticket đủ thông tin → domain xếp `start_workflow` → Platform tạo session và grant.
2. Agent đọc snapshot, tra nhân sự, dispatch. Domain tạo work order/assignment, gửi thông báo; staff mở `/operations/my-tasks`. Agent không gọi trực tiếp trình duyệt hay giả đăng nhập staff.
3. Staff nhận việc với ETA hoặc từ chối có lý do. Công việc đã nhận ở hàng đợi; một người không bắt đầu hai việc đang thực hiện cùng lúc (HTTP409).
4. Staff di chuyển, đến nơi, trình phương án/chi phí; cư dân quyết định. Staff gửi ảnh trước/sau, kết quả, ảnh nghiệm thu theo đúng work_order_id. Công việc có plan giữ gate duyệt hiện có.
5. Domain phát outbox, ký HMAC-SHA256 trên timestamp và byte body, gửi `POST /workforce/v1/provider/job-events`. Payload mang `client_reference`, `external_job_id`, `provider_version`, `external_event_id`. Retry giữ nguyên body; nhận receipt rồi đối soát. Không đồng nhất completed với cư dân đã chấp nhận.
6. Các sự kiện: offered, accepted, declined, offer_expired, unassigned, rescheduled, en_route, arrived, started, completed, cancelled, quote_ready, quote_approved, quote_rejected, result_published (đều prefix `job.`). Cư dân xác nhận thì domain đóng ticket và gửi close_workflow; chưa đạt thì mở lại theo policy.

**Giới hạn hiện tại:** provider events chỉ gắn công việc được tạo qua MCP với client_reference; chưa có cơ chế nhận quản lý công việc BQL tạo ngoài MCP. Không được nói mọi công việc thủ công đã tự theo dõi tại Platform.

### Điểm chưa nghiệm thu phía Platform

Đối chiếu đọc-only checkout `E:\AI-Workforce-Platform-develop2`, nhánh `feat/wf-remaining`, HEAD `11657984` ngày kiểm tra: `integrations/unified/_composition.py` chỉ gắn router unified và onboarding; tài liệu/source nêu provider job events, partner approval và waiting_external_event chưa gắn vào mode unified. Implementation async runtime có ở module khác không chứng minh mode đang deploy đã sử dụng nó. Chưa thấy adapter gọi mcp-grants trong source được đối chiếu.

Trên VPS domain, `VINHOMES_API_PLATFORM_URL` vẫn chưa cấu hình. Vì vậy chưa có nghiệm thu **Platform thật → staff → callback → Agent tiếp tục session**. Không bật bridge tới một endpoint giả định. Cần Platform cung cấp URL/version/mode đang chạy, route, customer/provider credentials qua file riêng, cơ chế grant theo workflow và endpoint nhận/receipt sự kiện đã gắn thật.

## 4. Dữ liệu đang có và còn thiếu

Snapshot VPS trước bổ sung Vệ sinh:

| Hạng mục | Số lượng / tình trạng |
|---|---|
| Khu/tòa | 8 khu, 16 tòa; coverage nghiệp vụ hiện chỉ 7 tòa |
| Staff | 26 profile; 17 chuyên môn Kỹ thuật, 9 An ninh; chưa có Vệ sinh |
| Ca | 1.405 bản ghi lịch sử/lịch, không có nghĩa 1.405 ca đang trực |
| Tiện ích | 5 bản ghi |
| Sổ tay / chính sách / thông báo | 34 / 6 / 30 |
| RAG | 164 tài liệu, 648 chunks: 115 resident, 49 staff |
| Nội dung đã duyệt theo schema hiện tại | **0**; cả 164 tài liệu được provenance xếp `reference` |
| Đầu mối Local Management | Chưa có contact_phone/contact_email |

Có dữ liệu mẫu và nội dung để tra cứu không đồng nghĩa có danh mục/phí/giờ hoạt động đã được chủ sở hữu xác nhận. Trong 115 tài liệu resident: 101 thiếu sources; cả 115 thiếu trường review approved_by/effective_from/document_reference mới. Các thống kê cũ dùng metadata legacy không thay cho kiểm tra review namespace hiện tại.

Khu có dữ liệu tòa: Sapphire4, Zenpark2, Hải Âu1, Sao Biển1, Pavilion2, Masteri Waterfront6; Ngọc Trai và San Hô chưa có tòa. Không suy ra toàn bộ các khu đó đã có tuyến dịch vụ hoặc dữ liệu chính thức.

### Chủ dự án cần bổ sung

- **Nhân sự:** họ tên, employee_code, email đăng nhập, đội/đơn vị, tòa/khu phụ trách, chuyên môn/chứng chỉ, ca có ngày giờ/timezone, ngày nghỉ, công suất. Không gửi mật khẩu vào chat. Ca và tên account khởi tạo phải được thay/xác nhận trước vận hành thực tế.
- **Danh mục dịch vụ:** phạm vi mỗi khu/tòa, đối tượng được dùng, mô tả, ngoài phạm vi, điều kiện và bước duyệt, SLA/khẩn cấp, giờ phục vụ/ngoài giờ.
- **Phí:** bảng phí nguồn gốc, VAT, vật tư/tiền công, trường hợp miễn phí, ngày hiệu lực/hết hiệu lực; không dùng giá demo làm biểu phí.
- **Đầu mối:** BQL, kỹ thuật, an ninh, vệ sinh, khẩn cấp/ngoài giờ; số liên hệ và người chịu trách nhiệm xác nhận.
- **SOP Vệ sinh:** loại công việc, dụng cụ/hóa chất cho phép, kiểm soát khu vực trơn ướt/chất thải, điều kiện cần plan/an toàn, checklist, ảnh bắt buộc, tiêu chí đạt/chưa đạt và xử lý làm lại.
- **Nguồn xét duyệt:** tài liệu/link gốc, mã/phiên bản văn bản, người duyệt, ngày duyệt, hiệu lực, audience và scope. Nạp metadata.sources + metadata.review; không chạy embedding/model trong đợt kiểm tra này.

Mẫu thu thập: `deploy/data-templates/resident-service-catalog.csv`; các CSV category/coverage/staff/shifts dùng importer trong `NAP_DU_LIEU.md`. Bảng thu thập nội dung không tự nhập vào RAG khi chưa biên tập/duyệt.

## 5. UI staff và các sửa đổi đợt này

- Luồng connected dùng **Việc của tôi**, bốn nhóm Đang làm/Hàng đợi/Chờ xác nhận/Lịch sử, dùng được cho staff specialty sanitation. Trang `/operations/sanitation` riêng vẫn là giao diện chưa nối backend, không dùng nó làm bằng chứng vệ sinh định kỳ đã hoàn thiện.
- Sửa bộ chọn staff để kiểm tra active membership/role/scope theo ticket ở MCP lookup, auto-offer, manual dispatch và planned offer. Nhập nhân sự Vệ sinh bắt buộc building_codes; không cấp toàn tenant ngầm.
- Bỏ danh mục giá vật tư demo khỏi form báo giá connected; nhập tay chi phí cho từng việc và nói rõ chưa có bảng phí chính thức.
- Copy phân công dùng “bộ phận điều phối”, phù hợp điều phối Platform; khóa ETA khi đang lưu, giữ CTA44px và input16px, ảnh theo work order, không mất draft vì đổi version khi poll.
- Sửa lượt ảnh trùng không có nội dung: source_message_id không tạo ra lượt Platform mới.
- Chưa có realtime push/mobile background notification được nghiệm thu; UI hiện polling. Nên bổ sung sau khi provider-event pipeline thật đạt, cùng thời hạn offer/ETA/SLA và xử lý mất mạng rõ hơn.

## 6. TLS: chưa đạt tự gia hạn trực tiếp

DNS-01 direct renew dry-run exit1: DuckDNS HTTPS timeout/TXT rỗng. HTTP-01 reconfigure cũng bị CA timeout, dù máy triển khai đọc được challenge200. Cấu hình renewal/chứng chỉ đang dùng được giữ nguyên; chưa chuyển sang HTTP-01 và chưa chứng minh gia hạn tự động.

Chi tiết, lệnh nghiệm thu trực tiếp và yêu cầu kiểm tra mạng nằm trong `deploy/HTTPS.md`. Không dùng timer active, proxy từ máy cá nhân hoặc chứng chỉ đang còn hạn để thay bằng chứng dry-run exit0. [DuckDNS TXT API](https://www.duckdns.org/spec.jsp), [Certbot renewal](https://eff-certbot.readthedocs.io/en/stable/using.html#renewing-certificates), [Let’s Encrypt challenge types](https://letsencrypt.org/docs/challenge-types/).

## 7. Bằng chứng kiểm thử và triển khai

Source chức năng **`1d76ea3c4095f793f9e54488341bb8d50fc00936`**, đã push `origin/dev_Vinhome`. Các image API/Reception/Resident/Operations dùng tag **`staff-mcp-20261014-1d76ea3c`**. Đã đối chiếu hash các module thay đổi trong container, index.html và **61 asset JS/CSS đang được phục vụ** (Resident17, Staff44) với artifact dự kiến.

- **126/126** kiểm thử PostgreSQL riêng: import, platform_tools, platform_bridge, platform_mcp_v2, staff_dispatch. Có full flow Kỹ thuật và Vệ sinh: nhận việc → di chuyển/đến nơi → báo giá/cư dân duyệt → ảnh trước/sau → nghiệm thu → cư dân xác nhận/đóng workflow; lỗi quyền, sai chuyên môn, busy409, nguồn cư dân, grant/CAS/retry, event signing/receipt/replay. FakePlatform, không model thật.
- **119 UI tests** đạt: lần chạy chung114 pass, 5 chưa chạy do hook import timeout10s; chạy riêng file đó với hook timeout30s đạt5/5. TypeScript/build staff đạt. Không gọi đây là một lần chạy chung119/119 không có retry.
- **20 tình huống browser** trên bundle VPS, API fixtures bị chặn/mock toàn bộ: 4 trạng thái staff × 5 viewport320×740,375×812,390×844,768×1024,844×390. Không overflow/JS error; nút thao tác chính ≥44px (file input dùng label80px); bản nháp giữ khi poll/version đổi. Đã xem ảnh render.
- **Live smoke** tài khoản Vệ sinh: login200, role staff, category sanitation có trong catalog, đọc danh sách việc riêng200, truy cập quản trị accounts403; UI đã tải xong ở320/375/768/1440, không tràn ngang/JS error. Không tạo ticket/work order thật và không chạy Agent.
- **MCP live:** tools/list đúng7 tool; anonymous401; bootstrap business call bị từ chối với TICKET_GRANT_REQUIRED. Không cấp grant hoặc chạy hành động trên ticket thật chỉ để smoke.
- [CI38515165777](https://github.com/nguyennanganhdev/AI-Workforce-Platform/actions/runs/38515165777): reception-cskh, business-api, frontend đều success trên SHA chức năng.
- API/Reception/Resident/Operations/Gateway/PostgreSQL/MinIO/Backup healthy; scheduler/platform-sync running (không khai báo healthcheck riêng). Backup trước release và sau thêm staff đều exit0. Test PostgreSQL/anonymous volume đã gỡ sau đối chiếu khác volume production.

### Dữ liệu Vệ sinh đã triển khai

Một account `Nhân viên Vệ sinh 01 (khởi tạo)`, role staff, specialty sanitation, available, công suất1. Có đúng **7 building grants, 7 coverage cùng Local Management, 7 ca mẫu08:00–17:00 +07:00 từ14/10 đến20/10/2026**. Đây là account/lịch khởi tạo theo yêu cầu, chưa thay cho danh sách nhân sự/ca chính thức. Không đổi nhân viên Kỹ thuật thành Vệ sinh. Dữ liệu import riêng có thể kiểm tra tại `/opt/vinhomes/audits/sanitation-20261014/import`.

Credentials lưu **ignored** tại `vinhome_Recident/deploy/test-accounts-20261013/sanitation-20261014/accounts.txt` và accounts.json; không có password/key trong Git hoặc tài liệu này. Khi bổ sung nhân sự thật, dùng chức năng quản trị/sửa profile và ca, không chạy importer add-only để giả định đã cập nhật row cũ.

Sau triển khai: users722, accounts17, memberships722, staff27, shifts1412, categories3, coverage21. **Tickets939, work_orders677, files33, knowledge164/648 không đổi.** Gateway/DB/MinIO không bị thay container trong release source; dữ liệu trước release không mất.

Bằng chứng private: `/opt/vinhomes/releases/staff-mcp-20261014-1d76ea3c/` (manifest, image IDs, hash, dump/config trước release); `/opt/vinhomes/audits/tls-staff-20261014/`; `/opt/vinhomes/audits/sanitation-20261014/`; local ignored `deploy/test-accounts-20261013/domain-audit/staff-mobile-20261014/`.

**Chưa hoàn tất hai gate bên ngoài:** TLS direct renew dry-run exit0, và kết nối Platform production có grant transport/provider event receiver. Kiểm thử isolated PostgreSQL + FakePlatform chỉ chứng minh hợp đồng phía domain. Bridge vẫn tắt vì thiếu URL Platform; không tuyên bố integration E2E thật hoặc chất lượng Agent đã được nghiệm thu.
