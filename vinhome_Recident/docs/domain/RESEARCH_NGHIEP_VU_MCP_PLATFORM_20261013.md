# Nghiên cứu nghiệp vụ, MCP và kế hoạch bàn giao platform — 13/10/2026

## 1. Kết luận và giới hạn kiểm chứng

**Cập nhật quyết định sau nghiên cứu:** platform quản lý session, điều phối và ngoại lệ; không bổ sung màn hình/hàng đợi tiếp nhận BQL hoặc tool escalation ở domain. Catalog giữ **7 tool**. Kế hoạch/bàn giao hiện hành: [MCP_PLATFORM_V2.md](MCP_PLATFORM_V2.md), tiến độ: [BAO_CAO_HOAN_THIEN_MCP_20261013.md](BAO_CAO_HOAN_THIEN_MCP_20261013.md). Những bằng chứng source/deployment bên dưới là snapshot trước maintain v2.

Kiểm tra tại repository chính `E:\AI-Workforce-Platform`, nhánh `dev_Vinhome`, HEAD `8a6c167d`; mã nghiệp vụ phát hành `7fa9c027`. Hai thay đổi đã tracked bên platform được giữ nguyên. Nghiên cứu đọc source/router thật, declaration, thiết kế đã duyệt, test source, hợp đồng đối tác và chỉ kiểm tra hạ tầng bằng thao tác đọc. Không gọi model, Agent, knowledge embeddings, tool ghi production hoặc sửa tài khoản cư dân.

Kiểm tra VPS trong lượt này, ngày 13/10/2026 khoảng 14:22 UTC:

| Nội dung | Kết quả quan sát mới |
|---|---|
| API, resident, operations, scheduler, platform-sync | Tag `maintain-20261013-7fa9c027`; API image `sha256:9403c9c4c6e132283ee77c8292845a3399d08f47ede39f0059cb483a81270b7a` |
| HTTP tên miền | `HEAD http://vinhome-platform.duckdns.org/` trả 200 |
| HTTPS tên miền | Kết nối cổng 443 thất bại; gateway chỉ publish HTTP public |
| Cầu nối partner | `VINHOMES_API_PLATFORM_URL` trống ở API và platform-sync; chưa gửi workflow/sự kiện sang platform thật |
| MCP | Token đã được cấu hình; lượt này đọc source/catalog, không chạy lại tool nghiệp vụ |
| SMTP | Host chưa cấu hình ở API; gửi email thật chưa bật |
| Cookie bảo mật | API đang `SECURE_COOKIES=0`, phù hợp hiện trạng HTTP nhưng chưa đủ để công bố public an toàn |

Các kết quả 44 test API/HTTP, 38 resident, 114 staff và browser acceptance là **bằng chứng của đợt maintain trước**, không phải test chạy lại trong nghiên cứu này. Xem [báo cáo release](BAO_CAO_MAINTAIN_DOMAIN_20261013.md). Chưa có nghiệm thu partner thật hoặc chất lượng Agent; lỗi provider 401 trong audit cũ cũng không được kiểm tra lại ở lượt này.

## 2. Nguồn nào quyết định nghiệp vụ

1. Quyết định mới nhất đã duyệt trong [NOI_WORKFORCE_V1.md, mục 1](NOI_WORKFORCE_V1.md#1-quyết-định-của-chủ-sản-phẩm-1110): Reception tạo ticket `plan_required=False`, platform điều phối, nhân viên thao tác trong domain, cư dân tự bấm báo giá và xác nhận kết quả. Source Reception cũng truyền `False` [S1, S2].
2. Catalog `/mcp` hiện hành là 7 tool đăng ký trong `platform_mcp.py`, không phải toàn bộ hàm tồn tại trong `platform_work.py` [S3].
3. `HOP_DONG_TICH_HOP.md` mô tả luồng REST `/integration/v1` có client/delegation/case và bộ thao tác rộng. Router này còn tồn tại nhưng **không phải cơ chế quyền của `/mcp` hiện tại**. Case REST dùng `integration_cases`, còn Workforce dùng `platform_links`; client MCP `platform` được tạo với `accepts_cases=false` [S4, S5]. Không lấy 45 thao tác REST làm 45 tool MCP đã cấp.
4. Hợp đồng bên platform được cung cấp tại `C:\Users\Lenovo\Downloads\CONTRACT_TICH_HOP_DOI_TAC.md`: bản `1.3-draft`, cập nhật 10/10/2026, tự ghi là **đặc tả mục tiêu chưa xác nhận triển khai**. Tài liệu quy định partner chủ động gọi API/history, không có webhook ngược; message v1 chỉ nhận text, attachment cần capability riêng; MCP nằm ngoài hợp đồng đó. Không coi ví dụ/API trong tài liệu là bằng chứng platform production có sẵn [S6].
5. `NGHIEP_VU_VINHOMES.md` là tài liệu lịch sử: còn nhận định không có password recovery, danh sách tối đa 200 và SLA chưa có; một số phần đã có chú thích cập nhật, một số phần chưa đồng bộ. Source/release mới phải được ưu tiên [S7, S8].

**Ranh giới thống nhất:** domain sở hữu identity, căn hộ, quyền, ticket, lịch sử, staff, ảnh, báo giá, duyệt và kết quả thật. Platform sở hữu workflow/điều phối, dùng tool trong phạm vi ticket được bàn giao. BQL, cư dân và nhân viên vẫn quyết định/thao tác các bước thuộc quyền của mình. Không đưa database hoặc credential người dùng cho platform.

## 3. Các vấn đề còn lại, mức độ và cách xử lý

| Mã | Vấn đề xác định được | Tác động và hướng giải quyết | Ưu tiên |
|---|---|---|---|
| R01 | HTTPS chưa hoạt động; token MCP đang tồn tại | Hoàn tất TLS/gia hạn/Secure cookie trước khi chuyển Bearer qua Internet. Trong thời gian chờ dùng SSH tunnel. Nguyên nhân CA timeout trước đây chưa được chứng minh là firewall nhà cung cấp | P0 |
| R02 | Outbound partner chưa cấu hình; hợp đồng partner là draft | Chốt bản contract/runtime URL và quyền; nghiệm thu request/reply/approval/event/close bằng fixture không Agent trước. MCP discovery không chứng minh end-to-end | P0 trước go-live partner |
| R03 | `/mcp` dùng một Bearer theo integration/tenant; `_ticket` chỉ kiểm tenant + link pending/open | Có scope thật, nhưng chưa cô lập từng workflow/management route. Chốt grant server-side theo route/ticket, khả năng thu hồi và bằng chứng actor/intent cho thao tác cư dân. Không dựa vào UUID hay prompt. REST delegation hiện có không tự bảo vệ MCP [S3, S4, S9] | P1 |
| R04 | `vh_ticket_get` chưa trả version, ID từng work order, policy/allowed actions, trạng thái escalation hay plan [S9] | Platform phải đoán điều gì được làm hoặc biết sau một lần bị từ chối. Bổ sung dữ liệu vào tool hiện hữu; server vẫn tái kiểm quyền khi ghi, không coi `allowed_actions` là giấy phép | P1 |
| R05 | `ticket_get` trả `status=completed` cho cả resolved và closed [S9:131–152] | Đây là trạng thái kết quả công việc; resolved vẫn có thể chờ cư dân, chưa chứng minh ticket đóng. Làm rõ `work_result_published`, `resident_confirmation_pending`, `ticket_closed`, trạng thái xác nhận có bằng chứng. Giữ tương thích hoặc version hóa trước khi đổi field cũ | P1 |
| R06 | Một số lỗi nghiệp vụ là text, một số là JSON `status=failed`; output schema chỉ bao chuỗi [S3, nghiên cứu kỹ thuật] | Client khó phân biệt quyền, xung đột trạng thái, lỗi tạm thời và parse. Chuẩn hóa code/retryable/correlation, output có schema; thương lượng tương thích vì platform có thể đang đọc status cũ. Exception quanh commit không đủ để luôn hứa “không có gì thay đổi”; trường hợp outcome chưa rõ phải replay cùng reference để đối soát, không tạo reference mới | P1 |
| R07 | Đề xuất chuyển BQL được bỏ theo quyết định mới | Platform quản lý session/attention; không tạo queue hoặc bước BQL duyệt yêu cầu tại domain | Không triển khai |
| R08 | SLA scheduler tạo event `ticket.sla_warning/breached`, nhưng không có mapping này trong `platform.PROGRESS` [S10, S11] | Đã có cảnh báo domain, chưa có đường đánh thức platform chủ động cho hạn xử lý. Hoàn thiện bằng sự kiện/polling bounded, không cần thêm tool tính SLA riêng. Chưa chứng minh cảnh báo phản hồi và cơ chế tạm dừng/gia hạn đầy đủ | P1/P2 |
| R09 | Provider events chỉ gửi nếu work order có `client_reference` trong operations của MCP [S11:628–644] | Việc BQL tự tạo hoặc được tạo từ phương án không tự thuộc job tracking này. Nếu muốn platform tiếp tục theo dõi sau chuyển BQL, cần contract binding/adopt operation hoặc event ticket riêng; không tự bịa reference | P2, bắt buộc nếu mở nhánh này |
| R10 | `vh_staff_available` tra ca hiện tại; dispatch có lịch hẹn tương lai [S9:314–334,390–439] | Không phải tra khả năng phục vụ tại giờ hẹn. Cần thêm tham số thời điểm vào tool hiện hữu và trạng thái lịch hẹn được xác nhận/chỉ là mong muốn; kiểm lại capacity lúc chào/nhận việc | P2 |
| R11 | Snapshot trả toàn bộ work orders và milestones không phân trang [S9:101–154] | Ticket có lịch sử dài có thể vượt ngân sách payload/timeout. Giới hạn recent history, cursor và snapshot version; kiểm thử tải thực tế. Declaration có timeout 8s không đồng nghĩa server đã cưỡng chế mọi giới hạn | P2 |
| R12 | `tools_allow=["vh_*"]`, README platform còn câu “đủ 10 công cụ” trong khi catalog là 7 [S12] | Đổi sang allowlist rõ ràng khi triển khai, đồng bộ doc/catalog/declaration và revoke grant cũ. Không để tool mới tự được cấp bởi wildcard | P1 |
| R13 | Các trang connected `security`, `sanitation`, `contractor`, `approvals`, `evidence` vẫn có placeholder [S13] | Chưa thể tuyên bố domain phủ mọi nghiệp vụ đầy đủ. Flow hiện trường/QC đang chạy ở trang khác; placeholder không có nghĩa các backend tương ứng đều thiếu. Nếu thêm phê duyệt phương án hoặc escalation phải có màn hình thật cho người xử lý | P2 theo scope |
| R14 | SMTP thật chưa bật theo lựa chọn chủ dự án | Code/reset qua fake mailbox đã có; delivery thật và HTTPS link còn chờ. Không phải phần platform cần thêm tool | Deferred đã thống nhất |

R03 là khoảng trống kiểm soát theo nhu cầu phân quyền chi tiết, **không phải kết luận mọi tenant bị lộ**: server có tenant RLS và active-link checks. DNS/Origin/Host, protocol version và schema/error cần đánh giá theo từng lớp middleware; xem [nghiên cứu MCP chính thức](RESEARCH_MCP_PLATFORM_SOURCES_20261013.md), không suy từ một flag thành lỗ hổng đã khai thác.

Thiết kế grant mới phải xử lý cả lúc link `pending`: platform có thể gọi MCP trong lượt start trước khi domain nhận được `workflow_id`. Cần binding theo handover/command do backend cấp rồi liên kết workflow đã xác minh; không ép workflow_id đã lưu trước mọi call và gây deadlock, cũng không tin ID do model tự khai. Cách truyền binding cần hai bên thống nhất thay vì tự thêm field không được partner hỗ trợ.

## 4. Ma trận nghiệp vụ và nhu cầu thực sự

| Tình huống sau bàn giao | Hiện có | Điều cần thêm/củng cố | Ai quyết định |
|---|---|---|---|
| Sửa chữa/vệ sinh đơn giản | get → staff_available → dispatch; staff nhận và thực hiện | Policy/capability rõ, lịch hẹn và trạng thái mới nhất | Platform gọi trong grant; nhân viên tự nhận |
| Không có nhân viên / từ chối / hết offer | Queue và scheduler tự chào lại, job.unassigned | Notice quá hạn sang Platform; không dispatch trùng, không mở queue BQL | Domain giữ queue công việc; Platform quản lý session/attention |
| Cư dân đổi lịch | reschedule chặn khi đã lên đường | Bằng chứng yêu cầu cư dân, lịch tương lai/khả năng phục vụ, stale version | Cư dân đề nghị, domain kiểm luật |
| Cư dân hủy | cancel chặn arrived/in_progress/completed và work an ninh | Intent binding; Platform quản lý ngoại lệ khi bị chặn, không lách qua thao tác khác | Domain kiểm luật; Platform theo dõi yêu cầu |
| Cư dân bổ sung mô tả/ảnh | note, ảnh domain gắn ticket; platform biết số ảnh | Read model rõ nguồn nội dung; không đưa URL ảnh trực tiếp | Cư dân và nhân viên trong scope |
| Báo giá và từ chối báo giá | ticket_get + thẻ + sự kiện quote | Ghi rõ approval ID/expiry/status và yêu cầu mới chuyển note, không tự sửa báo giá | Nhân viên lập; cư dân bấm |
| Làm xong/QC/cư dân chưa đồng ý | result_published → thẻ xác nhận → closed hoặc rework | Tách 3 nghĩa “làm xong”, “có kết quả”, “cư dân xác nhận”; tracking vòng làm lại | Nhân viên/BQL báo kết quả; cư dân xác nhận |
| Khẩn cấp/an ninh | Mọi ticket bàn giao đều đến Platform; xử lý khẩn tại chỗ giữ nguyên; security dispatch bị chặn | Phân biệt tiếp nhận session với quyền điều động; không cần BQL duyệt đầu vào | Platform theo dõi; BQL giữ quyền điều động an ninh hiện có |
| Hạn xử lý sắp đến/quá hạn | Deadline trong get; domain sweep emit cảnh báo | Notice/poll sang Platform; chống nhắc trùng, không tự đổi priority/deadline | Domain tính hạn; Platform quản lý attention |
| Cần phương án, nhiều đội, khóa nước/ngân sách | Backend REST plan/approval có; MCP dispatch từ chối requiresPlan | **Nhánh mở rộng**, không thuộc flow Workforce hiện tại. Chuyển BQL trước; chỉ thêm proposal tool sau khi chốt nghiệp vụ/UI/tracking | BQL/cư dân giữ các bước duyệt |
| Hỏi công nợ, khách, thẻ, booking | Domain/Reception có nghiệp vụ riêng; 7-tool route không làm | Hướng dẫn sang tính năng domain. Nếu muốn trợ lý khác, cấp route/grant riêng bằng yêu cầu riêng | Domain/Reception, không gộp vào ticket sửa chữa |

## 5. Đề xuất catalog MCP

### 5.1 Giữ 7 tool, nâng chất lượng 3 tool hiện hữu

Giữ `vh_ticket_get`, `vh_knowledge_search`, `vh_staff_available`, `vh_work_order_dispatch`, `vh_work_order_reschedule`, `vh_ticket_cancel`, `vh_ticket_add_note`.

- **ticket_get:** thêm ID/version/read_at, policy version, `requires_plan`, trạng thái xác nhận, các action cho phép cùng lý do bị chặn, SLA deadline/breach và cursor lịch sử. Trạng thái phải do domain tính; identity vẫn lấy từ bàn giao. Không thêm tool resident_context để bù hoặc hàng đợi escalation BQL.
- **staff_available:** thời điểm dự kiến theo timezone có kiểm tra, cửa sổ ca và lý do không có candidate, phân biệt khả năng hiện tại với đặt lịch được bảo đảm. Không gửi roster toàn bộ cư dân/nhân viên.
- **knowledge_search:** giữ scope ticket, trả tên tài liệu, phiên bản, hiệu lực, đoạn tham chiếu và audience được phép; xem kết quả là dữ liệu không đáng tin để ra lệnh. Nghiên cứu này không gọi embeddings. Không tạo thêm tool search quy định trùng chức năng.

### 5.2 Không thêm tool BQL trong scope hiện tại

Theo quyết định cập nhật của chủ dự án, platform quản lý session và ngoại lệ. Đề xuất `vh_ticket_escalate` và hàng đợi BQL trong bản nghiên cứu ban đầu đã được bỏ trước deploy. Không tạo thêm cổng duyệt yêu cầu; catalog mục tiêu hiện tại vẫn 7 tool. Domain gửi notice/SLA và giữ nguồn sự thật nghiệp vụ; platform xử lý attention theo workflow của nó.

### 5.3 Các tool chỉ cân nhắc có điều kiện

| Tool dự kiến | Điều kiện mở | Không được làm |
|---|---|---|
| `vh_ticket_plan_propose` | Chủ dự án quyết định mở nhánh phương án; UI BQL/cư dân thật; category/specialty refs hợp lệ; scope bridge khác case REST được xử lý; liên kết work order/event đã chốt | Không duyệt phương án, chi phí hoặc tự dispatch trước đủ duyệt |
| `vh_ticket_asset_context` | Ticket đã có asset binding đáng tin; có use case sửa thiết bị chung cần lịch sử/bảo hành/đo đạc | Không cho tùy ý duyệt mọi tài sản/tòa hoặc ghi số đo giả |
| Evidence/asset read | Platform có attachment capability, actor scope, retention và short-lived access contract | Không phát URL MinIO public, không ảnh khuôn mặt/giấy tờ, không nhận URL tùy ý |

Không đưa ba nhóm này vào roadmap bắt buộc chỉ để tăng tool count. Nếu plan được mở, ưu tiên đọc trạng thái plan trong `ticket_get`, không cần thêm một tool list-plan trùng snapshot. REST `propose_plan` có quy tắc hữu ích nhưng không gọi thẳng bằng MCP token: nó yêu cầu `integration_cases`/client nhận case mà flow Workforce hiện không cấp [S4].

Không cung cấp tool tạo ticket/xác định căn hộ, resident global search, công nợ cả hộ, visitor/card/booking cho route điều phối này; không cung cấp approve quote/plan, QC pass, close thay cư dân, thanh toán, cấp quyền hoặc SQL tự do.

## 6. Domain cần gửi sẵn gì, không nên biến thành tool

Outer request hiện đã có schema_version, external request/user/ticket/conversation, management ref, timezone và text message; không phải thiếu toàn bộ định danh. Text ticket hiện có tên/quan hệ cư trú, loại yêu cầu, mô tả, căn/tòa/phân khu, ưu tiên/khẩn cấp, số ảnh và thời gian tạo [S5, S14].

Đề xuất làm rõ bản **handover v1.1** bên domain:

| Nhóm | Nội dung cần chuẩn hóa | Cách bàn giao |
|---|---|---|
| Binding | Các external IDs và route có sẵn; ticket version, handover version, source timestamp | Outer fields chỉ dùng field partner đã nhận; nội dung bổ sung vào text có format được chốt |
| Nghiệp vụ | category code, vị trí cụ thể trong căn/khu chung, mô tả gốc và phần Reception đã xác nhận | Từ dữ liệu có thật; thiếu thì ghi unknown, không suy ra |
| Thời gian | Giờ cư dân yêu cầu, timezone, mức đã xác nhận; response/resolution deadline khi có | RFC3339 cho máy khi contract cho phép; giờ hiển thị giữ tương thích |
| Policy | Direct dispatch hay cần người xử lý, scope được cấp, version policy | Chỉ dẫn ban đầu; quyền luôn tính lại server-side lúc gọi tool |
| Safety | Reception đánh giá; domain đã ghi cảnh báo/đang chờ/chưa xác nhận tiếp nhận | Không gọi chung “đã báo BQL” nếu chưa có receipt tương ứng |
| Consent | Chỉ dẫn cư dân về lịch/hủy, ID tin nhắn/actor đã xác thực, approval được phép hiển thị | Tham chiếu do backend tạo; model không tự chứng nhận đồng ý |
| Evidence | Số ảnh/loại bằng chứng; thiếu ảnh nào cần nhân viên/cư dân bổ sung | Ảnh vẫn ở domain; không thêm attachment field khi partner chưa cấp capability |

Không gửi điện thoại, mật khẩu, giấy tờ, key, dữ liệu nhà khác hoặc ghi chú nội bộ. Không tự thêm JSON `context`/`metadata`/attachment vào API partner draft nếu chưa hỗ trợ. JSON Schema nội bộ có thể dùng kiểm tra serializer, rồi render sang `message.text`; schema nội bộ không phải endpoint công khai đã tồn tại.

## 7. Bộ tài liệu cần cung cấp thêm cho platform

Chia tài liệu kỹ thuật chia sẻ được và credential cấp riêng. **Không gửi nguyên repo/DB dump/account export hoặc .env production.**

| Hồ sơ | Đã có | Cần bổ sung/hoàn chỉnh |
|---|---|---|
| 01. Integration manifest và version | declaration + deploy README | Catalog chính xác 7/8 theo release, SHA, protocol/SDK version thương lượng, môi trường, URL, deadline/size/rate thật, compatibility/deprecation |
| 02. Nghiệp vụ và ma trận quyền | NOI_WORKFORCE; golden legacy | Ma trận ở mục 4, người quyết định, direct-dispatch policy; phân biệt legacy REST và Workforce MCP; các action cấm |
| 03. Handover contract | Mapping IDs + text đang gửi | Schema nội bộ + renderer text version; dữ liệu bắt buộc/unknown, ví dụ đã ẩn danh, consent/source references, nguyên tắc không có ảnh |
| 04. MCP catalog máy đọc được | declaration + private discovery | Input/output schema theo nghiệp vụ, error codes/retryable, trạng thái, example success/refusal/replay; test khớp tools/list/declaration/grants |
| 05. State machine | NOI_WORKFORCE | Sơ đồ ticket/work order/quote/resident-confirmation/workflow riêng; rework, cancel, stop-tracking, manual takeover; completed không đồng nghĩa closed |
| 06. Event contract | PROGRESS + declaration 15 loại event | JSON Schema từng event/version, operation binding, snapshot/rank/seq, HMAC raw bytes, receipt 202 vs processed, late/replay/out-of-order, cursor recovery; SLA/escalation chỉ thêm sau chốt contract |
| 07. Auth và credential lifecycle | Hai bên có hướng dẫn key cơ bản | Phân biệt customer API key, provider API key/HMAC và inbound MCP Bearer; scope/grant/expiry/revoke/rotation, TLS/private access, revoke grant cũ; không chứa secret |
| 08. Knowledge pack | Knowledge scope/search đã có | Tài liệu đang hiệu lực theo zone/building/audience: SOP sửa chữa/vệ sinh, an toàn khẩn cấp, phí/bảo hành, giờ phục vụ, SLA/escalation. Mỗi tài liệu có owner/version/effective dates/nguồn được BQL xác nhận |
| 09. Acceptance pack | Test source/evidence maintain | Fixture giả danh + request/response/event chuẩn, positive/negative matrix mục 9; test deterministic không model; đánh dấu phần Agent do chủ dự án tự test |
| 10. Operations runbook | deploy README/HTTPS/backup | Monitoring command/outbox/queue/escalation, retry/reconcile, restore/rollback, who-to-contact, ownership/SLO và cách bàn giao khi platform down |

Gói credential riêng đang ignored không phải tài liệu hợp đồng: chỉ chuyển qua kênh riêng được thống nhất; không chép token vào Markdown/Git. Các schema/runbook mới trong bảng là **deliverable cần làm**, chưa tuyên bố đã hoàn tất chỉ vì có tên trong kế hoạch.

Knowledge về phí, hotline, SLA, phạm vi bảo hành hoặc quyền vào căn phải có dữ liệu thật được BQL xác nhận. Nghiên cứu source không thể chứng minh các con số mẫu là chính sách chính thức Vinhomes; không tự điền từ website bất kỳ hoặc dùng seed làm policy production.

## 8. Kế hoạch triển khai theo thứ tự phụ thuộc

| Đợt | Công việc cụ thể | Điều kiện hoàn thành |
|---|---|---|
| A — Chốt contract và hạ tầng | Sửa doc sai/mâu thuẫn; pin phiên bản contract/protocol; HTTPS/gia hạn/cookie; thay wildcard tool grants; thống nhất error/output compatibility | HTTP→HTTPS, cert/renewal kiểm được; không chuyển token public HTTP; catalog/declaration/grant khớp; partner ký nhận version |
| B — Củng cố 7 tool | Bổ sung snapshot IDs/version/policy/confirmation; scope grant theo route/ticket, revocation và intent; chuẩn hóa errors/schema; giới hạn history/payload; concurrency/CAS không phá receipt replay | Không truy cập chéo route/workflow ngoài grant; stale write/giả intent bị chặn; retry thành công không ghi lại; resolved không bị đọc thành resident accepted |
| C — Ngoại lệ do platform quản lý | Giữ catalog7, notice/SLA chống trùng; nghiệm thu attention/recovery cùng platform | Không có queue hay bước BQL duyệt mới; không vô hiệu xử lý khẩn cấp hiện có |
| D — Theo dõi vận hành | SLA warning/breach chuyển đúng kênh; status refresh/reconcile; lịch tương lai; contract BQL-created job nếu cần theo dõi tiếp | Không event orphan hoặc state lùi; không spam; deadline không do model đặt; thao tác BQL không làm leader chờ vô hạn |
| E — Nghiệm thu partner không Agent | Sandbox route/credential thật; adapter deterministic của hai đội; outbox/history/receipt/revision; cập nhật handoff pack và config môi trường | Matrix mục 9 đạt, evidence có IDs/hash ẩn danh; rollback/restore; bật bridge trên pilot có giám sát khi có endpoint/config đã cấp |
| F — Mở rộng có quyết định riêng | Phương án nhiều bước/đội, assets, attachment capability hoặc dịch vụ cư dân route khác | Chốt actor/approval/UI/contract trước; không thêm tool chỉ vì backend có endpoint |

SMTP thật có thể làm song song sau khi được cấp cấu hình và HTTPS; provider/Agent test vẫn do chủ dự án. Không cần thay hoặc test Agent để thực hiện A–D. Giai đoạn E không được dùng “stub đạt” để thay nghiệm thu partner runtime thật; các API không tồn tại theo draft phải ghi blocker và thống nhất adapter/version.

Mỗi đợt: thay đổi domain có phạm vi → test định hướng nghiệp vụ → build/tag Docker bất biến → backup → deploy → đối chiếu image/source/bundle + migration → smoke bằng fixture riêng → cập nhật báo cáo và handoff. Không gộp sửa platform source vào nhánh domain, không reset production và không dùng cư dân thật để thử ghi.

## 9. Bộ nghiệm thu cần chạy khi triển khai

1. **Binding/quyền:** ticket không bàn giao; tenant/management grant khác; ID workflow giả; link đóng; grant hết hạn/thu hồi; cư dân bị khóa/đổi cư trú được xử lý theo policy rõ. Công việc BQL hợp lệ không bị vô hiệu tùy tiện vì người báo chuyển nhà.
2. **Intent:** chữ “tôi đồng ý” không thay nút báo giá; cancel/reschedule phải tham chiếu đúng yêu cầu của cư dân; nội dung ticket hoặc đoạn knowledge không thể đổi ticket_id/grant.
3. **Receipt/CAS:** replay cùng reference+payload sau timeout/close trả receipt hợp lệ không ghi thêm; khác payload/tool/ticket conflict; hai client concurrent; không lộ receipt vượt grant. Ràng buộc hash mới và receipt lịch sử NULL có test riêng.
4. **Direct dispatch:** đủ người, hết người, từ chối, offer hết hạn, lịch tương lai và capacity đồng thời; không tạo work order thứ hai cho việc đang queue; security/requiresPlan bị chặn.
5. **Kết quả:** work completed chưa phải resident accepted; report/QC pass rồi resolved; cư dân đồng ý đóng; chưa đạt mở lại/làm lại với correlation vòng mới; lịch sử cũ không ghi đè.
6. **Tiếp nhận/ngoại lệ:** start_workflow idempotent cho cả ticket an ninh thông thường; không có BQL duyệt đầu vào; notice/SLA retry/dedupe sang Platform; Agent/bridge chết vẫn có fallback domain.
7. **Event/reconcile:** HMAC sai/skew; retry raw bytes; 202 receipt chưa đồng nghĩa apply; event trùng/sai thứ tự/đến sau close; cursor410 snapshot; BQL job không có operation cần đường phục hồi đã chốt.
8. **Transport/schema:** handshake protocol hai bên; 401/403; Origin/Host qua proxy hợp lệ và không hợp lệ; typed output/tool error; payload/history lớn; timeout; key rotation/revoke; TLS.
9. **UI/vận hành:** cư dân/staff đúng scope, mobile320/390/768; không thêm màn hình tiếp nhận BQL; login/backup/restore/rollback; metrics queue age/failed commands/rejected events không chứa secret.

Chỉ kiểm các lớp có thay đổi và integration liên quan. Không chạy package Agent, provider API, embedding hoặc Reception chat; test bằng fixture/schema/mock transport/database riêng. Bài nghiệm thu leader thật được tách để chủ dự án thực hiện sau.

## 10. Những quyết định/dữ liệu còn cần từ hai bên

- **Platform:** endpoint sandbox/production, phiên bản triển khai thực tế, supported MCP protocol/SDK, route mapping, operation/consent capabilities, giới hạn và event schema chấp nhận; key qua kênh riêng. Tài liệu draft chưa đủ xác nhận những việc này.
- **Platform/chủ dự án:** ownership session/attention, cảnh báo thiếu nguồn lực, SLA và quy tắc ngoài giờ tại Platform; không cần thiết kế queue tiếp nhận BQL ở domain. Không tự điền SLA/hotline/chi phí từ seed.
- **Nhánh tương lai:** có muốn mở phương án BQL duyệt/nhiều đội hoặc platform xem ảnh hay không. Mặc định giữ quyết định direct dispatch + text-only hiện có, chưa mở plan/evidence tools.
- **Hosting:** giải quyết ACME HTTP hoặc cấu hình DNS challenge riêng để hoàn tất TLS; không cần gửi secret vào chat. SMTP production vẫn để sau như đã thống nhất.

## 11. Chỉ mục nguồn và độ tin cậy

Các đường dẫn source sau tương đối với `vinhome_Recident`; số dòng ứng với HEAD khảo sát, không phải cam kết runtime platform khác nhánh. Những thay đổi so với source dưới đây trong kế hoạch đều là **đề xuất**.

| Nguồn | Bằng chứng |
|---|---|
| S1 | [NOI_WORKFORCE_V1.md](NOI_WORKFORCE_V1.md):7–24,124–144,174–180 — quyết định và boundary hiện hành |
| S2 | `agents/reception/src/runtime/backend.py:327`; `agents/reception/src/agent/tools.py:153` — truyền plan_required false; chỉ đọc source |
| S3 | `services/vinhomes-api/src/vinhomes_api/platform_mcp.py:33–124,141–159` — wrappers, catalog7, token guard |
| S4 | `services/vinhomes-api/src/vinhomes_api/integration_cases.py:42–74,131–197`; `integration.py:26–33`; [HOP_DONG_TICH_HOP.md](HOP_DONG_TICH_HOP.md):30–96,112 — cơ chế REST/case khác MCP |
| S5 | `services/vinhomes-api/src/vinhomes_api/platform.py:186–235`; [NOI_WORKFORCE_V1.md](NOI_WORKFORCE_V1.md):57 — link/text và client accepts_cases false |
| S6 | `C:\Users\Lenovo\Downloads\CONTRACT_TICH_HOP_DOI_TAC.md`:3–31,92–135,184–188,900–981 — contract1.3-draft, text-only, onboarding/receipts; nguồn ngoài repo, chưa xác minh runtime |
| S7 | [NGHIEP_VU_VINHOMES.md](NGHIEP_VU_VINHOMES.md):169–195,771–776,923 — snapshot cũ và chú thích cập nhật, không dùng độc lập làm hiện trạng |
| S8 | [BAO_CAO_MAINTAIN_DOMAIN_20261013.md](BAO_CAO_MAINTAIN_DOMAIN_20261013.md):13–25,48–67,90–99 — bằng chứng kiểm thử/deploy đợt trước |
| S9 | `services/vinhomes-api/src/vinhomes_api/platform_work.py:70–154,314–334,348–441,444–527` — guard, snapshot, ca hiện tại, receipt, hành động |
| S10 | `services/vinhomes-api/src/vinhomes_api/jobs.py:20–38` — warning80% hạn xử lý và breached qua event_outbox |
| S11 | `services/vinhomes-api/src/vinhomes_api/platform.py:615–654` — mapping/binding operation và ký body; `platform_sync.py:255–323` — nguồn lấy context |
| S12 | `deploy/platform/vinhomes-declaration.json:32,82–88,95–152`; `deploy/platform/README.md:75–77,113–117` — catalog/grants/doc cần đồng bộ |
| S13 | `apps/staff-web/src/features/vinhomes-operations/connected/ConnectedOperations.tsx:358–365,479–485` — các path vẫn placeholder; không suy mọi route backend thiếu |
| S14 | `services/vinhomes-api/src/vinhomes_api/platform_sync.py:68–81` — outer request/binding và text message |
| S15 | `services/vinhomes-api/src/vinhomes_api/v3_plans.py:44–103,151–180,209–300` — plan backend + quyết định con người; chưa là tool của currentMCP |

Nguồn giao thức MCP chính thức, phiên bản thương lượng, những thay đổi ở latest và cách áp dụng từng yêu cầu được dẫn riêng trong [RESEARCH_MCP_PLATFORM_SOURCES_20261013.md](RESEARCH_MCP_PLATFORM_SOURCES_20261013.md). Kết quả source audit này không chứng nhận quy trình chính thức của toàn bộ thương hiệu Vinhomes hoặc mọi module của platform.
