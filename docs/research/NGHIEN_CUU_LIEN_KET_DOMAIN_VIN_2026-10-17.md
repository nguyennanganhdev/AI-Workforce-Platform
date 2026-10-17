# Nghiên cứu chuyển từ chatbot Domain sang Platform dùng chung cho người dùng Vin

Ngày khảo sát: 17–18/10/2026, Asia/Saigon. Phạm vi: mã nguồn `dev_Chien`, commit `1ec4465d7f2928f9610b02b0126d39b1443f4163`; nghiên cứu nguồn chính thức qua web. Không truy cập production, credentials hay dữ liệu cư dân; không chạy model hoặc tạo phiếu nghiệp vụ. Đây là bằng chứng nguồn và đề xuất thiết kế, **chưa phải xác nhận runtime hoặc nghiệm thu nghiệp vụ**.

## 1. Kết luận phục vụ kế hoạch triển khai

Đích sản phẩm phù hợp với việc đặt Platform làm cửa vào: mỗi người có tài khoản và không gian agent riêng, dùng Leader/team, agent cá nhân và các tài nguyên do admin công bố. Domain Vinhomes tiếp tục xác thực quyền cư trú và thực thi nghiệp vụ qua adapter; không phải chuyển mọi database nghiệp vụ thành knowledge. Kết luận thiết kế này dựa trên việc Domain hiện giữ quyền cư trú, luật tác nghiệp, xác nhận chi phí/nghiệm thu và tiến độ việc thật. [L1](../../vinhome_Recident/services/vinhomes-api/src/vinhomes_api/resident_cases.py#L15), [L2](../../vinhome_Recident/services/vinhomes-api/src/vinhomes_api/platform_work.py#L186), [L3](../../vinhome_Recident/services/vinhomes-api/src/vinhomes_api/v3_resident.py#L517)

Bốn hạng mục không thể giải quyết chỉ bằng thay menu/UI:

1. **Liên kết tài khoản có bằng chứng từ Domain**. Tài khoản Platform không tự chứng minh là cư dân; phải có kết quả đăng nhập/đồng ý tại Domain, định danh issuer + subject và quyền căn hộ được kiểm tra ở Domain. Code hiện có đăng nhập password và delegation ngắn hạn; các bề mặt đã khảo sát chưa có authorization-code account-link flow. [L4](../../vinhome_Recident/services/vinhomes-api/src/vinhomes_api/password_auth.py#L22), [L5](../../vinhome_Recident/services/vinhomes-api/src/vinhomes_api/integration.py#L283), [OIDC §5.7](https://openid.net/specs/openid-connect-core-1_0.html#ClaimStability)
2. **Resident grant trước khi có ticket**. MCP tác nghiệp hiện yêu cầu ticket đã bàn giao và `external_request_id` của start command. Một người vừa liên kết tài khoản chưa thể dùng grant ấy để đọc tài sản/cư trú hoặc tạo phiếu đầu tiên. Phải bổ sung resident-scoped adapter/grant, sau đó mới đổi sang ticket/workflow grant. [L6](../../vinhome_Recident/services/vinhomes-api/src/vinhomes_api/platform_access.py#L55), [L7](../../vinhome_Recident/services/vinhomes-api/src/vinhomes_api/platform_access.py#L89)
3. **Tách chủ sở hữu cuộc chat khỏi tuyến thực thi**. Routing cũ ánh xạ đơn vị quản lý vào scope có `manager_account_id`. Cần conversation/case riêng do khách hàng sở hữu; tuyến service/BQL ở backend không đồng nghĩa BQL được xem toàn bộ chat cá nhân. Đây là đề xuất phát triển từ routing hiện có, không phải hành vi đã triển khai. [L8](../../platform_VP/agentscope/src/agentscope/app/workforce/foundation/_partner_routing.py#L293)
4. **Đổi chứng cứ lời yêu cầu và quyết định sang nguồn Platform**. Cancel/reschedule hiện xác minh `source_message_id` trong bảng `messages` của chat Domain, đúng requester/ticket và trong 24 giờ. Nếu chỉ bỏ chatbot Domain, thao tác từ Platform sẽ không có chứng cứ hợp lệ theo gate hiện tại. [L9](../../vinhome_Recident/services/vinhomes-api/src/vinhomes_api/platform_work.py#L560)

## 2. Hiện có trong source

| Mặt cắt | Bằng chứng hiện có | Hệ quả khi chuyển Platform-first |
|---|---|---|
| Đăng nhập Domain | `/auth`, provider `vinhomes-password-v1`, opaque session cookie theo resident/field/operations; mật khẩu và token được hash. [password_auth.py:22](../../vinhome_Recident/services/vinhomes-api/src/vinhomes_api/password_auth.py#L22), [password_auth.py:34](../../vinhome_Recident/services/vinhomes-api/src/vinhomes_api/password_auth.py#L34), [password_auth.py:140](../../vinhome_Recident/services/vinhomes-api/src/vinhomes_api/password_auth.py#L140) | Có thể giữ cửa xác thực Domain để xác nhận liên kết. Không sao chép mật khẩu/cookie sang Platform. |
| Identity resolver Domain | Chấp nhận delegation `dg1_` hoặc user session; tenant/user DB context được đặt phía server. [v3_auth.py:16](../../vinhome_Recident/services/vinhomes-api/src/vinhomes_api/v3_auth.py#L16), [v3_auth.py:49](../../vinhome_Recident/services/vinhomes-api/src/vinhomes_api/v3_auth.py#L49) | Tận dụng authority resolution, không tin `resident_id` do model/browser tự khai. |
| Quyền cư trú | `unit_residents` phải verified, còn thời hạn; residence query yêu cầu domain/site/building/unit active. [resident_cases.py:15](../../vinhome_Recident/services/vinhomes-api/src/vinhomes_api/resident_cases.py#L15) | Liên kết danh tính và quyền trên căn hộ là hai lớp khác nhau; cần recheck sau chuyển nhà/thu hồi quyền. |
| Quyền tiền và sửa chữa | `ANSWERABLE` chỉ owner/tenant; household không mặc nhiên có quyền tài chính. [unit_access.py:7](../../vinhome_Recident/services/vinhomes-api/src/vinhomes_api/unit_access.py#L7), [unit_access.py:35](../../vinhome_Recident/services/vinhomes-api/src/vinhomes_api/unit_access.py#L35) | Không phát một role customer chung để mở toàn bộ quyền cư dân. |
| Delegation có thể tái dùng | `/integration/v1/delegations/self` yêu cầu phiên user Domain, client active, grants thu hẹp theo purpose/client. TTL tối đa 600 giây, tối đa 120 calls; resolve kiểm tra user/member/client active và operation catalog. [integration.py:25](../../vinhome_Recident/services/vinhomes-api/src/vinhomes_api/integration.py#L25), [integration.py:114](../../vinhome_Recident/services/vinhomes-api/src/vinhomes_api/integration.py#L114), [integration.py:283](../../vinhome_Recident/services/vinhomes-api/src/vinhomes_api/integration.py#L283) | Đây là nền tảng delegation cho adapter, chưa phải bằng chứng đã có OAuth/SSO hoặc account link lâu dài. Không lưu token ngắn hạn như một liên kết vĩnh viễn. |
| Đọc trước-ticket | Catalog delegation có `resident.me/context/tickets`; resident services thêm homes/rules/balance/visitors/cards/amenities. [integration.py:58](../../vinhome_Recident/services/vinhomes-api/src/vinhomes_api/integration.py#L58), [resident_services.py:578](../../vinhome_Recident/services/vinhomes-api/src/vinhomes_api/resident_services.py#L578) | Không cần bẻ ticket-grant để đọc trước-ticket; có thể wrap các service này bằng contract resident được phê duyệt. |
| Tạo ticket Domain | Có `/resident/chats/{channel_id}/tickets`; shared intake yêu cầu chat của requester, residence verified, coverage/category hợp lệ, Idempotency-Key và file thuộc chat. [v3_resident.py:243](../../vinhome_Recident/services/vinhomes-api/src/vinhomes_api/v3_resident.py#L243), [v3_resident.py:330](../../vinhome_Recident/services/vinhomes-api/src/vinhomes_api/v3_resident.py#L330), [v3_resident.py:438](../../vinhome_Recident/services/vinhomes-api/src/vinhomes_api/v3_resident.py#L438) | Có business service để tái sử dụng, nhưng public intake hiện phụ thuộc Domain chat. Cần facade nhận Platform session/source proof thay vì gọi thẳng helper bỏ kiểm quyền. |
| Tự bàn giao sau intake | `create_resident_ticket` gọi `platform.link_ticket`; hàm này tạo link và queue `start_workflow`. [v3_resident.py:452](../../vinhome_Recident/services/vinhomes-api/src/vinhomes_api/v3_resident.py#L452), [platform.py:214](../../vinhome_Recident/services/vinhomes-api/src/vinhomes_api/platform.py#L214), [platform.py:258](../../vinhome_Recident/services/vinhomes-api/src/vinhomes_api/platform.py#L258) | Nếu Platform đã mở case rồi gọi intake mà vẫn giữ auto-start cũ, có nguy cơ tạo workflow thứ hai. Cần nhánh `origin=platform` bind case đang có, không queue start thêm. |
| Luồng chat hiện tại | `divert()` chỉ gửi tiếp về Platform khi Domain đã có ticket/link active; emergency vẫn đi song song Reception. [platform.py:286](../../vinhome_Recident/services/vinhomes-api/src/vinhomes_api/platform.py#L286) | Luồng này không phải intake Platform-first. Khi bỏ Reception phải chuyển cả xử lý khẩn cấp và follow-up. |
| Bootstrap MCP | Có thể khám phá; gọi business tool thiếu grant bị `TICKET_GRANT_REQUIRED`. [platform_access.py:45](../../vinhome_Recident/services/vinhomes-api/src/vinhomes_api/platform_access.py#L45), [platform_mcp.py:102](../../vinhome_Recident/services/vinhomes-api/src/vinhomes_api/platform_mcp.py#L102) | Tuyệt đối không mở rộng bootstrap thành credential đọc mọi cư dân để làm demo mới. |
| Ticket MCP grant | `/platform/mcp-grants`: backend-only, tool allowlist, ticket/link active, external start command và workflow khớp, TTL và token hash. [platform_access.py:64](../../vinhome_Recident/services/vinhomes-api/src/vinhomes_api/platform_access.py#L64), [platform_access.py:89](../../vinhome_Recident/services/vinhomes-api/src/vinhomes_api/platform_access.py#L89) | Có nền tảng đúng cho execution sau ticket. Cần contract bind case Platform-origin thay điều kiện duy nhất là start command Domain. |
| Platform grant client | `_grants.scoped_client` thay bootstrap bằng workflow bearer; grant endpoint cùng origin, không follow redirect; validate ticket/workflow/tools/expiry; fail closed. [_grants.py:11](../../platform_VP/agentscope/src/agentscope/app/workforce/integrations/unified/_grants.py#L11) | Giữ exchange ở backend, ngoài model context. Mở rộng có chủ đích cho resident-session grant và Platform-origin binding. |
| Team member tools | Member đi qua case tools/ticket grant; code bỏ shared/default MCP binding của member. [_case.py:1226](../../platform_VP/agentscope/src/agentscope/app/workforce/integrations/unified/_case.py#L1226), [_case.py:1263](../../platform_VP/agentscope/src/agentscope/app/workforce/integrations/unified/_case.py#L1263) | Phải giữ server-side intersection giữa quyền user, agent và tool; custom prompt không được nâng quyền. |
| Tuyến quản lý | Route cần active, manager membership verified/revision khớp, account/domain/area active; projection chứa manager scope. [_partner_routing.py:127](../../platform_VP/agentscope/src/agentscope/app/workforce/foundation/_partner_routing.py#L127), [_partner_routing.py:293](../../platform_VP/agentscope/src/agentscope/app/workforce/foundation/_partner_routing.py#L293) | Tái dùng làm tuyến thực thi; phát triển principal/audience khách hàng riêng. Không gán customer thành manager để lách routing. |
| BQL trên Domain/Platform | Password auth chặn management-only Domain login, hướng sang Platform; management MCP là read-only, area binding, grant ngắn hạn. [password_auth.py:121](../../vinhome_Recident/services/vinhomes-api/src/vinhomes_api/password_auth.py#L121), [platform_management.py:53](../../vinhome_Recident/services/vinhomes-api/src/vinhomes_api/platform_management.py#L53), [platform_management.py:75](../../vinhome_Recident/services/vinhomes-api/src/vinhomes_api/platform_management.py#L75) | Source đã có hướng chuyển BQL sang Platform; điều này không chứng minh tất cả màn hình BQL cần cho nghiệp vụ đã hoàn tất. |
| Kết quả thật và quyết định | Ticket policy có plan/security gates, quote/completion cần cư dân. QC độc lập và onsite acceptance có hai nhánh khác nhau. [platform_work.py:186](../../vinhome_Recident/services/vinhomes-api/src/vinhomes_api/platform_work.py#L186), [v3_specialized.py:86](../../vinhome_Recident/services/vinhomes-api/src/vinhomes_api/v3_specialized.py#L86), [v3_specialized.py:138](../../vinhome_Recident/services/vinhomes-api/src/vinhomes_api/v3_specialized.py#L138) | Bỏ BQL xem/duyệt mọi chat không có nghĩa bỏ phê duyệt chi phí, luật khẩn cấp, QC hay nhân sự thực hiện. |
| Publication acknowledgement | Nút quote/completion và ảnh kết quả bị gate theo Platform đã `applied`; quyết định kiểm ticket version/pending/expiry. [platform_publication.py:7](../../vinhome_Recident/services/vinhomes-api/src/vinhomes_api/platform_publication.py#L7), [platform_publication.py:23](../../vinhome_Recident/services/vinhomes-api/src/vinhomes_api/platform_publication.py#L23), [v3_resident.py:527](../../vinhome_Recident/services/vinhomes-api/src/vinhomes_api/v3_resident.py#L527) | Platform customer UI phải hiển thị quyết định có trạng thái xác thực; lời model “đồng ý” không thay chữ ký user/click đã kiểm quyền. |
| Đồng bộ bền vững | `platform-sync` gửi commands, đọc conversation events, chuyển ticket events thành outbox và gửi signed job events; receipts phân biệt accepted với applied. [platform_sync.py:1](../../vinhome_Recident/services/vinhomes-api/src/vinhomes_api/platform_sync.py#L1), [platform_sync.py:353](../../vinhome_Recident/services/vinhomes-api/src/vinhomes_api/platform_sync.py#L353), [platform_sync.py:396](../../vinhome_Recident/services/vinhomes-api/src/vinhomes_api/platform_sync.py#L396) | Không tắt toàn bộ worker khi tắt chatbot; phải giữ progress/outbox/reconciliation đến khi adapter mới thay đủ. |
| Knowledge export Domain | Có knowledge pack với audience, phạm vi zone/building/unit-kind, hiệu lực, source, checksum/version. [integration_cases.py:230](../../vinhome_Recident/services/vinhomes-api/src/vinhomes_api/integration_cases.py#L230) | Có thể ingest phần tài liệu được phép; phải giữ metadata/thu hồi. Pack này là export cho integration client, không phải retrieval ACL hoàn chỉnh của từng cư dân. |
| Travel hiện tại | Các tool travel trong MCP tự ghi `MOCK ONLY`. [platform_mcp.py:246](../../vinhome_Recident/services/vinhomes-api/src/vinhomes_api/platform_mcp.py#L246) | Không ghi Vinpearl/VinWonders đã tích hợp booking thật. Cần partner contract, entitlement, sandbox và nghiệm thu riêng. |

## 3. Nguồn chính thức bên ngoài và cách áp dụng

### 3.1. Account linking

OAuth Security BCP yêu cầu redirect URI khớp đăng ký, bảo vệ CSRF và chống code injection. Chọn Authorization Code + PKCE, giữ state một lần ràng buộc phiên Platform, kiểm issuer khi có nhiều Domain. Không dùng luồng thu username/password Domain tại Platform. Refresh token nếu có cần chính sách bảo vệ/rotation. Đây là yêu cầu thiết kế cho phần liên kết mới; không phải bằng chứng Vinhomes đã cung cấp OAuth. [RFC 9700 §§2.1, 2.2.2, 2.4](https://www.rfc-editor.org/rfc/rfc9700.html#section-2)

PKCE dùng code verifier ngẫu nhiên và challenge `S256`; code chỉ được đổi bằng verifier tương ứng. [RFC 7636 §§4.1–4.6](https://www.rfc-editor.org/rfc/rfc7636.html#section-4)

Nếu dùng OIDC thật, dùng cặp `iss` + `sub` làm định danh external; kiểm ID Token signature, issuer, audience, expiry và nonce theo flow. Không tự ghép người bằng email/phone trùng nhau. [OIDC Core §§2, 3.1.3.7, 5.7](https://openid.net/specs/openid-connect-core-1_0.html#IDTokenValidation)

### 3.2. MCP authorization

Tài liệu MCP `latest` được đọc trong khảo sát resolve sang bản `2026-07-28`; HTTP authorization dựa trên OAuth, resource metadata và resource parameter, token phải dành cho đúng MCP server. Đây là hướng chuẩn hóa adapter mới; cần kiểm phiên bản SDK/transport đang cài trước khi cam kết tương thích. Grant tùy biến hiện tại không tự đồng nghĩa triển khai OAuth MCP đầy đủ. [MCP Authorization 2026-07-28](https://modelcontextprotocol.io/specification/2026-07-28/basic/authorization)

MCP security guidance yêu cầu consent theo client khi proxy sang dịch vụ khác và cấm token passthrough. Thiết kế Platform cần đổi quyền tại trust boundary: token Platform, token liên kết Domain, resident grant, ticket grant là các loại riêng; không chuyển nguyên Platform bearer xuống Domain và không tái dùng consent của người A cho agent/user B. [MCP Security Best Practices](https://modelcontextprotocol.io/docs/2026-07-28/tutorials/security/security_best_practices#confused-deputy-problem)

### 3.3. Discord cho agent cá nhân

OAuth Discord phân biệt cài bot với lấy user access token. Đề xuất dùng Discord app/bot do Platform quản lý, user chỉ liên kết Discord identity và chọn agent/kênh được phép; không yêu cầu người dùng nhập bot key quản trị chung. Bot install ở guild cần người có quyền; `guild_id` callback chỉ là gợi ý, cần xác minh quan hệ thực. [Discord OAuth2](https://docs.discord.com/developers/topics/oauth2#bot-authorization-flow)

Interaction cần phản hồi ban đầu trong 3 giây, token follow-up có hiệu lực 15 phút; worker agent phải ack/defer rồi xử lý async, kết quả dài hạn quay về Platform. [Discord Receiving and Responding](https://docs.discord.com/developers/interactions/receiving-and-responding#responding-to-an-interaction)

`MESSAGE_CONTENT` là privileged intent, có điều kiện bật/phê duyệt; ưu tiên slash commands/mentions được hỗ trợ cho pilot. [Discord Gateway](https://docs.discord.com/developers/events/gateway#privileged-intents)

429 phải retry theo `Retry-After`/`retry_after` và bucket headers; cần queue outbound, dedupe event và circuit breaker khi token/quyền bị thu hồi. [Discord Rate Limits](https://docs.discord.com/developers/topics/rate-limits#exceeding-a-rate-limit)

Các giới hạn thực thi và phương án channel trên là đề xuất áp dụng nguồn chính thức, không phải chứng minh connector Discord hiện đã đạt các điều kiện ấy.

## 4. Contract tối thiểu đề xuất cho Platform-first

Toàn bộ tên API/bảng trong phần này là **đề xuất**, chưa có trong source được khảo sát. Mục tiêu là tái dùng service Domain trong phần 2 qua facade có authorization, không gọi thẳng hàm nghiệp vụ bỏ checks.

### 4.1. Ba vùng dữ liệu và hai principal

| Thành phần | Nguồn quyết định | Chủ sở hữu/visibility đề xuất |
|---|---|---|
| Platform account, personal agents/chat/team, eval, lịch, quota | Platform | User sở hữu; staff/admin theo quyền vận hành được cấp, không có quyền xem chat riêng mặc định chỉ vì là BQL. |
| Cư trú, quan hệ căn hộ, billing/cards, staff/work orders, kết quả và quyết định thật | Domain | Domain xác thực mỗi operation; Platform giữ external reference và projection tối thiểu. |
| Tài liệu dùng chung/riêng | Nguồn công bố + knowledge ACL Platform | Tài liệu Vin chỉ tới audience được duyệt; private knowledge chỉ owner; dữ liệu biến động truy vấn MCP. |
| Conversation/case | Platform customer principal | Customer là chủ cuộc chat và audience; service route chỉ phục vụ execution. |
| Service route | Domain + Platform operator principal | Staff/BQL nhìn ticket/task trong scope, không tự tham gia personal team chat. |

Sự tách biệt này là đề xuất để giữ các gate hiện có: source Domain đã xác minh cư trú/quyết định, còn routing Platform hiện quản lý scope manager. [resident_cases.py:15](../../vinhome_Recident/services/vinhomes-api/src/vinhomes_api/resident_cases.py#L15), [_partner_routing.py:293](../../platform_VP/agentscope/src/agentscope/app/workforce/foundation/_partner_routing.py#L293)

### 4.2. Link lifecycle

1. Platform user đã đăng nhập chọn **Liên kết Vinhomes**. Backend tạo link intent với `user_id`, `issuer/domain_id`, client, exact callback, state hash, verifier/challenge, expiry; không để model/browser quyết định `external_subject`.
2. Browser chuyển sang màn hình Domain đăng nhập và consent scopes cụ thể. Không đưa password, session cookie hay token vào prompt/knowledge.
3. Domain trả authorization code một lần; Platform backend đổi code, xác minh issuer/audience/nonce/PKCE. Ghi `domain_account_links` gồm internal user, domain tenant/issuer, external subject, scopes, consent/version, trạng thái, created/last_checked/revoked. Unique theo policy để ngăn cùng một external subject bị link nhầm vào tài khoản Platform khác.
4. Đọc homes/entitlements từ Domain; chọn căn trong các kết quả được xác thực. Một user có thể có nhiều căn và nhiều Domain; không mặc định căn đầu tiên khi một hành động có ảnh hưởng.
5. Unlink/revoke khóa các grant, job và lịch liên quan; không xóa lịch sử nghiệp vụ chính thức. Link hết hạn/quyền cư trú đổi thì re-auth hoặc fail closed trước thao tác tiếp.

Các bước 1–3 áp dụng OAuth/OIDC theo §3.1; vòng đời, schema và policy unique là thiết kế đề xuất cho khoảng trống link hiện tại. [integration.py:283](../../vinhome_Recident/services/vinhomes-api/src/vinhomes_api/integration.py#L283)

**Chưa có Vin OAuth chính thức được chứng minh:** nếu bên Domain có IdP/OAuth/OIDC được phê duyệt thì tích hợp theo contract đó. Nếu pilot dùng Domain của repo này, triển khai authorization/link broker trên Domain hoặc dùng IdP đã được duyệt, giữ mật khẩu tại Domain. Không đặt tên một endpoint tự tạo là “Vin SSO” trước khi có chủ sở hữu Vin xác nhận.

### 4.3. Resident grant trước-ticket

Endpoint đề xuất `POST /platform/resident-grants` nhận `link_id`, `platform_subject`, `agent_id/run_id`, `conversation_id`, `residence_ref` nếu có, `tools`, purpose, TTL, audience/resource và idempotency reference. Backend-to-backend được xác thực; Domain resolve link và quyền hiện thời, giới hạn tools rồi cấp opaque token chỉ lưu hash hoặc token ký có revocation record.

Allowlist v1: identity/context/homes, knowledge-search được phép cho cư dân, ticket list/get của chính mình, prepare/create request. Có thể wrap các service read đã có; action nhỏ khác mở từng capability sau khi nghiệm thu. Không có tool sửa provider/skill/MCP, đọc toàn tenant hoặc phát grant cho người khác. Đây là đường bổ sung, không nới `platform_access.authorize()` của ticket tools. [integration.py:58](../../vinhome_Recident/services/vinhomes-api/src/vinhomes_api/integration.py#L58), [resident_services.py:578](../../vinhome_Recident/services/vinhomes-api/src/vinhomes_api/resident_services.py#L578), [platform_access.py:45](../../vinhome_Recident/services/vinhomes-api/src/vinhomes_api/platform_access.py#L45)

### 4.4. Intake và ticket binding

Luồng đề xuất:

```text
Platform user -> Leader / personal agent -> Resident adapter
  -> lấy các homes đã xác minh -> user chọn home khi cần
  -> prepare request, kiểm category/coverage, ảnh và intent
  -> user xác nhận gửi -> Domain create request/ticket idempotent
  -> bind ticket vào case/workflow Platform đang có
  -> cấp ticket/workflow/tool grant -> team gọi MCP đúng quyền
  -> staff thực hiện + các gate nghiệp vụ -> Domain outbox
  -> Platform timeline/decision controls -> user xác nhận -> Domain cập nhật
```

Các object tối thiểu:

- `CaseBinding`: Platform user, link, conversation/case/workflow/run, domain tenant, external subject, residence, ticket, execution route, permission revision, origin, trạng thái và version.
- `SourceIntent`: source message/event ID ở Platform, authenticated actor, subject/link, case/ticket, content hash, action/payload hash, nonce, issued/expiry và consent reference. Backend Domain kiểm chữ ký/single-use khi thích hợp; không tin một dòng `source_message_id` do model viết.
- `DomainCommand`: command ID + Idempotency-Key, actor/link/source proof, operation, expected version, payload. Same key + same payload trả cùng receipt; same key + khác payload trả conflict.
- `DomainResult/Event`: schema version, correlation, command/ticket/case IDs, status, canonical version/sequence, `accepted/applied/failed/outcome_unknown`, safe user summary và next action. Không gọi job thành công chỉ vì HTTP 202.

Đặc biệt: helper intake hiện kiểm `_owned_chat` và gọi `link_ticket()` tự queue start. Facade mới phải tách phần business transaction khỏi trigger Reception/bridge: `origin=domain` giữ đường cũ, `origin=platform` gắn `existing_case/workflow` trong một transaction, không sinh `start_workflow` thứ hai. Dữ liệu cần được audit bằng actual actor; không giả danh user bằng header tự chọn. [v3_resident.py:253](../../vinhome_Recident/services/vinhomes-api/src/vinhomes_api/v3_resident.py#L253), [v3_resident.py:452](../../vinhome_Recident/services/vinhomes-api/src/vinhomes_api/v3_resident.py#L452)

Phải có nhánh đổi request từ Platform sang ticket grant mà không dựa vào `external_request_id` Domain-start cũ; Domain kiểm case binding đã xác thực và chủ ticket, rồi cấp quyền sau ticket. Không tạo fake Domain start command để lách grant. [platform_access.py:89](../../vinhome_Recident/services/vinhomes-api/src/vinhomes_api/platform_access.py#L89), [_grants.py:26](../../platform_VP/agentscope/src/agentscope/app/workforce/integrations/unified/_grants.py#L26)

### 4.5. Quyết định và progress

- Chuyển quote/consent/completion card sang Platform customer UI, gọi command quyết định có user session, source proof, exact payload/quote hash, expected canonical version và idempotency. Tool model chỉ chuẩn bị/giải thích; quyết định của người dùng được ghi thành action riêng. Tái sử dụng Domain guards về owner, expiry, pending, version và result acknowledgement. [v3_resident.py:517](../../vinhome_Recident/services/vinhomes-api/src/vinhomes_api/v3_resident.py#L517), [platform_publication.py:23](../../vinhome_Recident/services/vinhomes-api/src/vinhomes_api/platform_publication.py#L23)
- Giữ `platform-sync` provider progress/outbox hoặc thay bằng event consumer tương đương có ordered delivery, dedupe, retry, receipt + dead-letter/reconcile. Chỉ retire nhánh mirror reply vào Domain chat sau khi ticket cũ và case mới đều có consumer đúng origin. [platform_sync.py:1](../../vinhome_Recident/services/vinhomes-api/src/vinhomes_api/platform_sync.py#L1), [platform_sync.py:396](../../vinhome_Recident/services/vinhomes-api/src/vinhomes_api/platform_sync.py#L396)
- Cancel/reschedule từ Platform cần source proof mới; cho legacy Domain tiếp tục dùng proof cũ trong cửa sổ chuyển đổi, không bỏ yêu cầu chứng cứ cho cả hệ thống. [platform_work.py:560](../../vinhome_Recident/services/vinhomes-api/src/vinhomes_api/platform_work.py#L560)

### 4.6. BQL không xem từng chat; người thật vẫn làm đúng vai

Thiết kế mặc định: chat cá nhân/team agent là riêng tư. BQL xem dashboard/ticket/progress thuộc phạm vi; chỉ nhận task/escalation có nội dung tối thiểu hoặc tham gia conversation hỗ trợ khi user đồng ý/chính sách vận hành cho phép và được audit. Các trường hợp ngoại lệ như khẩn cấp cần phương án trực tiếp tới hotline/đội vận hành, không chờ model hay quota còn lại.

Không cần BQL bấm duyệt mọi tin nhắn hoặc câu trả lời thông thường. Tuy nhiên Domain hiện còn plan, independent QC cho nhánh có plan, staff onsite report cho nhánh không plan, quote/completion do cư dân quyết định và cấm security dispatch khẩn cấp qua tool thông thường. Muốn thay đổi các gate này cần ADR/SOP được chủ nghiệp vụ chấp nhận; không xóa gate chỉ để khớp giao diện mới. [platform_work.py:186](../../vinhome_Recident/services/vinhomes-api/src/vinhomes_api/platform_work.py#L186), [v3_specialized.py:86](../../vinhome_Recident/services/vinhomes-api/src/vinhomes_api/v3_specialized.py#L86), [v3_specialized.py:138](../../vinhome_Recident/services/vinhomes-api/src/vinhomes_api/v3_specialized.py#L138)

## 5. Gói triển khai Domain và các điều kiện phối hợp Platform

Đây là phân rã đề xuất, không phải các tính năng đã hoàn thành.

| Thứ tự | Đầu việc của Domain / adapter | Điều kiện Platform tương ứng | Nghiệm thu có giá trị |
|---|---|---|---|
| D1 | Chốt issuer/subject/consent/link broker, revoke API, tenant và residence entitlement | Platform principal + link UI/store | Đăng nhập/consent thật; không tự link bằng phone/email; user A không link được identity B. |
| D2 | Resident-scoped grant và các read trước-ticket, chia quyền owner/tenant/household | Runtime luôn inject actor/context từ server | Đọc chính mình trước ticket; thử giả unit/user/domain bị chặn ở server. |
| D3 | Prepare/create request facade + Platform source proof, bind existing workflow, idempotent receipt | Customer-owned case và personal-team audience | User gửi 1 lần/retry/network loss vẫn chỉ 1 ticket, 1 workflow; không vào group BQL. |
| D4 | Ticket grant mới cho platform-origin, tool/action policy và grant revoke | Catalog readonly + per-run least privilege | Prompt custom không cấp thêm tool; agent/member/tool không có grant đúng bị chặn. |
| D5 | Decision facade quote/completion/reschedule/cancel, version và source proof | Card quyết định trên Platform | Hết hạn, stale, double-click, sửa payload, model tự đồng ý đều không gây side effect trái quyền. |
| D6 | Provider event origin routing, reconcile/dead-letter, không duplicate feedback | Timeline/private team stream + user notification | Mất callback, đảo thứ tự, worker restart vẫn khớp canonical trạng thái Domain; không gửi trùng. |
| D7 | Feature flag/routing theo cohort, ticket migration index, giữ staff operational paths | Mời cư dân + link hướng dẫn + rollback | Ticket cũ tiếp tục được xem/quyết định tại Platform; staff vẫn nhận/làm/báo kết quả. |
| D8 | Bỏ chatbot Reception khỏi resident app sau gate chấp nhận | Platform intake/support đủ năng lực | Không còn intake mới từ Reception ở cohort đã chuyển; link fail và emergency có đường xử lý rõ. |
| D9 | Chuẩn hóa adapter catalog để thêm Vinpearl/VinWonders/domain khác | Multi-domain account links, domains công bố capabilities | Onboard domain thứ hai bằng contract, không if/else và không mở cư trú Vinhomes sang khách du lịch. |

## 6. Bộ ca nghiệm thu và rollout

Mỗi ca phải có expected result, logs/audit không chứa secret, correlation IDs, trạng thái canonical, user/operator acceptance. Unit/contract tests là điều kiện kỹ thuật; phải thêm E2E qua hai service thực và cư dân/staff/BQL được giao vai pilot.

| Nhóm | Ca bắt buộc |
|---|---|
| Danh tính | User Platform chưa link vẫn chat cá nhân được nhưng không đọc Domain; link đúng; từ chối consent; state sai/expired/replayed; code sai verifier; issuer khác; external subject đã link người khác; unlink ngay giữa run; Domain account bị khóa. |
| Cư trú | Một người nhiều căn; hết hạn thuê; household không đọc billing như owner; sửa `unit_id`, `resident_id`, domain/tenant hoặc ticket của người khác; quyền bị thu hồi sau khi cấp token. |
| Intake | Câu hỏi chung không tạo phiếu; đủ dữ kiện mới prepare; user xác nhận; thiếu category/coverage; coverage trùng; ảnh không thuộc user/case; request retry sau timeout; Domain tạo thành công nhưng mất response; không double workflow do legacy auto-start. |
| Leader/team | User theo dõi team đúng case; member không thấy task người khác; custom prompt yêu cầu đọc mọi căn/tắt guard không có tác dụng; không hiển thị internal staff comments hoặc chat manager cho customer. |
| Hành động thật | Dispatch chuẩn; quote cần chính user; cancel/reschedule có Platform source intent; proof giả hoặc khác ticket bị chặn; stale version; staff completed chưa có đúng evidence/QC không thể đóng giả; resident reject dẫn rework. |
| Vận hành | BQL không duyệt mọi chat nhưng nhận escalation/ticket đúng scope; khẩn cấp không phụ thuộc Reception bị tắt; Domain down rõ trạng thái; retry/outcome-unknown không lặp tác động; accepted khác applied; outbox backlog/reconcile và restart không mất sự kiện. |
| Kênh và lịch | Discord event giả/replay/chưa link bị chặn; guild shared channel không lộ dữ liệu cư dân; bot bị kick/quyền thu hồi/429; agent chạy lịch kiểm link/entitlement/quota tại thời điểm chạy; không giữ grant user đã unlink. |
| Cutover | Nhiều ticket đang mở, quote pending, waiting completion và attachment/history có thể truy cập từ Platform đúng người; user đã đăng ký Domain được hướng dẫn tạo/link Platform; rollback không làm mất case/ticket. |

Rollout đề xuất:

1. **Contract sandbox**: fixtures synthetic, PKCE/link tests, authorization negative tests, event ordering/retry. Không dùng `MOCK ONLY` làm chứng cứ booking Vinpearl thật.
2. **Pilot nội bộ**: tài khoản test được xác minh, một project/nhóm căn, service ít rủi ro; Platform-first bật theo cohort. Legacy vẫn xử lý ticket chưa chuyển.
3. **Pilot cư dân thực**: cùng người dùng và staff thực hiện yêu cầu, quote, chấp nhận/từ chối, theo dõi Leader/team. Ghi cả chất lượng trả lời và kết quả nghiệp vụ, latency, lỗi quyền, quota và phản hồi người dùng.
4. **Cutover cohort**: user đã link và ticket mapping/decisions hoàn tất; tắt intake mới trên chatbot cohort, giữ deep link sang Platform. Không tự nhập mật khẩu hay tạo liên kết bằng email/phone match.
5. **Retire Reception resident flow**: sau cửa sổ ổn định và kiểm không còn legacy consumers; giữ Domain APIs, staff, scheduler và progress worker còn được dùng. Rollback là đổi routing/flag, không phục hồi snapshot cũ đè các ticket mới.
6. **Mở rộng Vin**: mỗi Domain mới phải khai báo issuer, entitlement, capability taxonomy, dữ liệu/scope, side effects/consent và owner nghiệm thu. Vinpearl/VinWonders là tích hợp tương lai cho tới khi có API và quyền truy cập chính thức.

Các bước cutover là thiết kế rút ra từ phụ thuộc bridge/auto-start/publication hiện tại; cần giữ tương thích trong giai đoạn chuyển, không chỉ ẩn chatbot rồi dừng container. [platform_sync.py:1](../../vinhome_Recident/services/vinhomes-api/src/vinhomes_api/platform_sync.py#L1), [v3_resident.py:452](../../vinhome_Recident/services/vinhomes-api/src/vinhomes_api/v3_resident.py#L452), [platform_publication.py:23](../../vinhome_Recident/services/vinhomes-api/src/vinhomes_api/platform_publication.py#L23)

## 7. Các quyết định còn cần chủ sản phẩm/chủ nghiệp vụ xác nhận

1. **Điều kiện gia nhập “người dùng Vin”**: cư dân/khách hàng/nhân viên/đối tác là các audience khác nhau. Đề xuất giai đoạn đầu người chưa link chỉ dùng personal workspace theo chính sách invite; tài liệu nội bộ không tự mở toàn bộ cho mọi khách hàng.
2. **Cửa xác thực được phép dùng**: Domain Vinhomes hiện tại của repo hay hệ thống Vinhomes/VinID/Vingroup chính thức; bên nào sở hữu issuer/link broker và phê duyệt consent scopes. Chưa có bằng chứng khảo sát về official Vin OAuth endpoint.
3. **Độc lập nghiệp vụ sau bỏ BQL thường trực**: gate nào giữ human-on-the-loop, người tiếp nhận escalation và nguồn SOP; đề xuất giữ current quote/completion/plan/QC/security rules đến khi có quyết định thay thế.
4. **Quyền xem hỗ trợ**: vai trò nào được mở đoạn chat liên quan ticket, có cần user consent và thời gian retention. Đề xuất BQL không thấy private chat/knowledge cá nhân mặc định.
5. **Mốc tắt chatbot**: theo cohort sau UAT và chuyển ticket đang mở, hay ngày cố định có migration đồng loạt. Đề xuất cohort, có rollback routing và không xóa dữ liệu legacy.

Không có quyết định nào ở trên làm thay đổi các điểm người dùng đã chốt: tài khoản Platform + liên kết Domain; cư dân chuyển sang chat trực tiếp/Leader trên Platform; provider/skill/MCP chỉ xem/chọn catalog có sẵn; knowledge chung readonly theo quyền + kho riêng có dung lượng; quota theo người/nhóm.
