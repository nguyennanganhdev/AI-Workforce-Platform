# Kiểm tra phân quyền, dữ liệu và hạn mức cho Vin Platform

Ngày: 2026-10-17. Checkout kiểm tra: `dev_Chien`. Đây là kiểm tra nguồn chỉ đọc phục vụ kế hoạch; chưa chạy production, gọi model, dùng credential hay nghiệm thu người dùng thật. Không suy ra bản đang chạy trên VPS từ checkout này.

## 1. Kết luận để đưa vào kế hoạch hai phần

Platform có thể tái sử dụng nền tảng tài khoản, storage theo chủ sở hữu, chia sẻ tài nguyên read/edit, RAG, memory và model-call ledger. Tuy nhiên, hệ thống hiện vẫn được thiết kế cho BQL/admin; chưa đủ để mở trực tiếp cho cư dân bằng cách đổi menu hoặc thêm role. Các cửa bắt buộc trước pilot cư dân: tài khoản người dùng phổ thông, liên kết định danh Domain, catalog do admin quản trị, giữ secret model ở phía server, quyền dữ liệu từ principal, quota đặt chỗ trước khi gọi model và truy xuất Knowledge theo audience.

## 2. Bằng chứng nguồn hiện có và khoảng trống

Trong các đường dẫn dưới đây, gốc mã là `platform_VP/agentscope/src/agentscope/`.

| Chủ đề | Hiện có đã đọc từ source | Khoảng trống cho mục tiêu mới |
|---|---|---|
| Tài khoản | `app/auth/_service.py:55-58` chỉ có `PLATFORM_ADMIN`, `DOMAIN_ADMIN`, `AREA_MANAGER`. Đăng ký bắt buộc domain/area và gán `AREA_MANAGER` tại `:286-300`; đồng thời ghi membership BQL chờ xác minh tại `:363-383`. Schema HTTP yêu cầu domain/area tại `app/_router/_auth.py:31-32`. | Chưa có vai trò cư dân/người dùng Vin; không được đưa người đăng ký phổ thông vào tài khoản BQL. Tách đăng ký cá nhân khỏi đăng ký/xác minh quản lý. |
| Principal | `app/deps.py:59-103` xác minh bearer khi có AuthService và không tin `X-User-ID`; demo không cấu hình auth vẫn có fallback header. | Môi trường phục vụ cư dân phải fail closed khi thiếu auth. Bổ sung quyền và liên kết Domain do server xác định; không nhận quyền cư dân từ body/prompt. |
| Quyền tài nguyên | `app/access/_policy.py:19-28` có credential, agent, KB; `:79-87` nói rõ policy chưa quản lý user/group/share records. `app/_app.py:356-357` mặc định `DenyAllResourceAccessPolicy`. `app/_service/_access.py:254-310` trộn tài nguyên own + refs được cấp; `:505-529` chặn sửa shared read-only. | Có extension point nhưng chưa có persisted entitlement policy cho Vin. MCP và skill chưa thuộc các ResourceKind nói trên. Cần quyền `view/use/manage` tách biệt và policy tenant/audience/group. |
| Secret model dùng chung | `app/_router/_workforce_console.py:432-445` lấy key platform từ env rồi lưu thành credential owned bởi tài khoản gọi. `_dump_with_secrets` tại `app/storage/_utils.py:15-39` ghi secret thành string để runtime dùng. `app/_service/_access.py:561-570` chỉ mask data nếu viewer khác owner; `app/_router/_credential.py:49-77` trả các view này. | Theo chuỗi source này, credential platform copy sang own record có thể được owner đọc qua API. Đây là cửa P0 phải sửa trước khi mở khách hàng; không lấy secret thật để chứng minh. Không tiếp tục seed/copy key vào mỗi khách hàng. |
| Provider CRUD | `app/_router/_credential.py:79-105` cho authenticated user tạo credential; PATCH/DELETE kiểm quyền edit tại `:110-195`. | Thêm server capability gate cấm cư dân tạo/sửa/xóa provider/credential. Chỉ trả metadata model được phép và health/status, không trả secret hoặc payload kết nối. |
| MCP | `app/_router/_mcp.py:49-105` cho authenticated user kết nối URL, gửi auth và lưu MCP; DELETE tại `:247-260`. `app/_router/_schema/_hub_mcp.py:60-66,114-145` đã có projection không trả mcp_config. | Catalog chung được quản trị còn thiếu. Cư dân chỉ chọn/bind tool đã cấp, không nhập URL/header/key hay sync catalog. Cần gate cả hub install và workspace direct MCP. |
| Skill | `app/_router/_skill.py:31-39` tạo local skill bằng identity; `:42-53` review theo role quản lý; `:85-101` xóa theo owner. Hub install chỉ có auth tại `app/_router/_hub.py:234-243`. | Cấm cư dân quản trị skill, kể cả hub install/ZIP upload/workspace direct skill. Cho chọn phiên bản admin phê duyệt; revoke phải ngăn chạy bản workspace đã copy. |
| KB riêng và shared KB | `app/storage/_model/_knowledge_base.py:88-99` và `_knowledge_document.py:109-122` có owner user. `app/_service/_knowledge_base.py:405-416` kiểm edit trước ghi blob; search resolve visibility tại `:842-843`; `_require_edit` và resolve owner tại `:849-889`. | Có nền tảng KB riêng/read-only share nhưng chưa có chính sách audience Vin được lưu bền. Không đồng nghĩa mọi tài liệu nội bộ được toàn bộ cư dân đọc. |
| KB quota | Upload ghi `size` từ request, chính docstring nói không authoritative tại `app/_service/_knowledge_base.py:389-391`; ghi blob ngay tại `:413-416`. Router truyền `file.size or 0` tại `app/_router/_knowledge_base.py:650`. | Chưa thấy tổng storage quota theo người có atomic reservation trong luồng upload đã kiểm tra. Cần đo byte thật khi stream và đặt chỗ trước; kiểm quota cho inline references, upload, retry, indexing, delete. |
| RAG và audience | Manager cấp collection theo KB tại `app/rag/knowledge_base_manager/_collection_per_kb.py:80-89`; get knowledge dùng `metadata_filter=None` tại `:215-216`. Inline lexical reference chỉ search tài liệu ready/approved/còn hiệu lực tại `_lexical.py:29-48`. | ACL hiện chủ yếu cấp KB; không thể đưa tài liệu khách hàng, nhân viên, vận hành vào cùng KB rồi kỳ vọng prompt lọc quyền. Tách KB theo ACL cho pilot; thêm document ACL trước search nếu sau này cần trộn audience. |
| Catalog → runtime | Chat đã resolve shared KB qua ResourceAccessService tại `app/_service/_chat.py:1499-1554`. Nhưng readiness dùng `storage.list_knowledge_bases(user_id)`, `get_mcp`, `get_skill` theo owner tại `app/_service/_agent_readiness.py:17-46`. Studio skill installer cũng owned-only tại `app/_router/_workforce_studio.py:727-730`. | Phải thống nhất resolver qua catalog, spec validation, eval, readiness, publish binding và runtime; chỉ thêm policy vào list KB sẽ làm shared KB có mặt ở UI nhưng báo thiếu khi chạy agent. |
| Memory | `app/_agent_memory.py:143-154,176-185` lọc đúng user/agent; recall theo user/agent tại `:189-204`. | Tái dùng làm memory cá nhân, giữ độc lập với kho Vin. Không tự nâng memory cá nhân/ticket thành Knowledge chung; quyền còn hiệu lực phải được kiểm lại khi recall nguồn bị thu hồi. |
| Usage ledger | `app/_service/_model.py:105-109` attach ledger vào chat model; `app/_model_ledger.py:79-87` buộc owner; `:122-141` tổng hợp theo owner. `model/_call_observer.py:98-105` nuốt lỗi telemetry để paid call vẫn chạy. SQL ledger `app/storage/_sql/_alembic/versions/0019_model_call_ledger.py:10-20` có user/id/status/payload. | Đây là observability, không phải hạn mức cứng. Chưa có daily/monthly balance, user/group policy, atomic reserve/settle trước provider call. Không dùng ledger callback fail-open làm quota gate. |

## 3. Đề xuất tối thiểu cho phần nền tảng

Đây là thiết kế đề xuất, chưa được triển khai.

1. Giữ tài khoản Platform hiện hữu; thêm loại quyền `VIN_USER` cho cư dân/người dùng phổ thông, không tự gán BQL hay domain admin. BQL/admin giữ role và scope cũ. Khi một người có nhiều vai trò, quản lý membership/capability tách khỏi thông tin đăng nhập; quyền quản lý không truyền sang agent cá nhân bằng prompt.
2. Thêm `domain_account_links`: tenant Platform, user Platform, provider/domain, issuer, external tenant/subject, trạng thái, consent/scopes, thời điểm xác minh, revision và revoked_at; unique theo identity provider + external tenant + subject trong chính sách một chủ liên kết đã chốt. Token Domain lưu qua secret reference server, không trả browser và không đưa vào agent prompt.
3. Luồng liên kết: người đã đăng nhập Platform → giao dịch link có TTL gắn đúng user + state/nonce/PKCE khi Domain hỗ trợ → đăng nhập/consent ở Domain → callback server xác minh → đọc subject và membership từ Domain → lưu link. Nếu Domain chưa có OAuth/OIDC thì phải triển khai adapter/contract tương ứng, không giả định API key S2S hiện tại chứng minh quyền từng cư dân. Unlink/revoke/đổi cư dân căn hộ phải ngăn tool và job tương lai.
4. Dùng catalog `resource_grants` hoặc mở rộng policy hiện có, bao gồm resource kind/id, service/admin owner, tenant, audience/group/user, quyền view/use/manage, trạng thái/revision. Provider/MCP/skill: cư dân chỉ view/use; phần binding trong agent cá nhân được sửa bởi owner nhưng không sửa catalog gốc. Catalog resolver do server kiểm lại ở mỗi execution.
5. Key model platform chỉ nằm ở service/admin-owned secret; client nhận provider/model ID an toàn. Thay `_platform_credential` bằng resolve central provider reference. Di chuyển bản platform-owned key đã seed vào own records sang reference; không sửa nhầm credential BQL tự cấp. Kiểm soát toàn bộ GET/PATCH/DELETE/export/log/cache và chuẩn bị rotation nếu kết quả kiểm tra thực tế cho thấy key từng bị lộ.
6. Knowledge có ít nhất ba audience tách biệt: Vin dành cho khách hàng, nội bộ nhân viên, vận hành/quản trị có giới hạn. Phân loại trước ingest; service/admin sở hữu kho chung. Cư dân có KB riêng mặc định private. Không có thao tác cư dân share rộng/private-to-common trong pilot. Admin chỉ thấy nội dung riêng theo cơ chế hỗ trợ được cấp, không lấy khả năng quản trị hạ tầng làm quyền đọc mặc định của UI.
7. Giữ storage owner hiện tại để giảm phạm vi thay đổi; bổ sung tenant/domain identity mapping cho grants và execution. Với KB chung cho pilot, tách collection theo KB/audience đã cấp ACL; không thay schema business của Domain bằng tài khoản Platform.

### API đề xuất để người triển khai chốt contract

Các đường dẫn sau là đề xuất, không phải API đã có trong checkout. Khi triển khai có thể giữ quy ước router hiện tại nhưng phải bảo toàn các quyền và invariant này.

| API đề xuất | Chủ thể/quyền | Dữ liệu bắt buộc do server quyết định |
|---|---|---|
| `POST /auth/register-personal` | Người đăng ký theo chính sách gia nhập Platform | Vai trò mặc định `VIN_USER`, tenant, trạng thái tham gia; không nhận `role/admin/manager` tự khai |
| `GET /me/capabilities` | Mỗi người chỉ đọc quyền của mình | Effective grants, revision, giới hạn và tài nguyên có thể sử dụng |
| `POST /me/domain-links/{provider}/start` | Chủ tài khoản đã đăng nhập, có CSRF protection | Link transaction gắn user/tenant, state, nonce, TTL và provider allowlist |
| `GET /me/domain-links/{provider}/callback` | Callback khớp đúng giao dịch | Subject, external tenant, membership, consent và secret reference đã xác minh |
| `GET /me/domain-links`; `DELETE /me/domain-links/{id}` | Chủ tài khoản | Projection không có token; revoke link và thông báo cho job/grant liên quan |
| `GET /catalog/providers`; `/catalog/mcps`; `/catalog/skills`; `/catalog/knowledge` | User chỉ nhận resource view/use được cấp | ID, approved version, safe metadata, effective permission; không URL/header/secret nhạy cảm |
| `PUT /agents/{id}/bindings` | Chủ agent riêng | Revalidate mỗi resource ID/version theo catalog grants; không cho sửa tài nguyên catalog qua binding |
| `POST/PATCH/DELETE /admin/catalog/...`; `/admin/resource-grants/...` | Platform admin hoặc domain admin đúng scope | Owner/service identity, audience, version/revision và audit actor |
| `GET /me/usage` | Chủ tài khoản | Daily/monthly used, reserved, remaining, reset_at và incomplete reconciliation |
| `PUT /admin/usage-policies/{subject}` | Admin đúng tenant/scope | Group/user override, hiệu lực, policy revision và audit; không nhận override từ chat/channel |

Không cấp endpoint public gọi `reserve/settle`: đây là thao tác nội bộ do model gateway/runtime thực hiện. Browser gửi yêu cầu công việc, không gửi số token để tự trừ hoặc tự hoàn hạn mức.

## 4. Hạn mức model và Knowledge

Đây là thiết kế đề xuất. Admin phải đặt số thực tế trước pilot; không tự coi số ví dụ là cấu hình production.

- `usage_policies`: tenant, user hoặc group, hiệu lực, daily/monthly token cap, max output/call, max concurrency và storage bytes; giá trị riêng người dùng ghi đè mặc định nhóm. Ghi rõ cap nhóm là mức mặc định cho từng thành viên hay pool tổng; nếu có pool tổng phải reserve cả pool và user.
- `usage_reservations`: operation/call ID, user, policy revision, daily bucket, monthly bucket, reserved tokens, state, expiry và provider reconciliation ID. Dùng transaction/atomic CAS để đặt chỗ đồng thời trước từng provider attempt; count đủ input/output/reasoning mà provider tính, không đếm cached input hai lần.
- Model được phép dùng phải có cách tính/bảo thủ giới hạn input và `max_output_tokens` thực thi ở provider; reserve đủ trần cho outbound request cuối cùng sau khi thêm RAG/tools. Model/adapter chưa kiểm soát được trần không được dùng trong nhóm áp dụng quota cứng. Không chỉ ước lượng từ câu hỏi người dùng đầu tiên.
- `usage_settlements`: reconcile actual usage về ledger; retries/fallback/fan-out/Leader workers/summaries/learning/Builder/eval/schedule/channel đều quy về người khởi tạo/chủ job do server xác định. Không thể vượt quota bằng gọi agent con hoặc đổi UI entry point.
- Reset daily/monthly theo `Asia/Ho_Chi_Minh` được cấu hình rõ; reservation gắn kỳ tại thời điểm tạo. Quota hết trả mã lỗi ổn định, số còn lại/reset_at, dừng tạo paid call và giữ kết quả công việc đang có. Chính sách giữ/dừng job và resume phải có trạng thái bền.
- Call timeout/crash/usage thiếu không được tự hoàn hết reservation; đưa về pending reconciliation theo provider request ID, dùng hạn mức bảo thủ để không chi tiếp không kiểm soát. Lỗi quota store chặn paid call mới; ledger metric có thể tiếp tục best-effort.
- Embedding/indexing cần budget riêng và gắn người upload; quota token chat không tự bao phủ storage hay embedding. Knowledge bytes phải reserve từ streaming limit và commit số thật; retry/delete/re-index không double charge hoặc tăng quota giả.

## 5. Những ca nghiệm thu bắt buộc

1. Cư dân đăng ký tài khoản cá nhân không có quyền BQL; người đang dùng BQL/admin vẫn đăng nhập và hoạt động theo scope cũ.
2. Người A không thể đọc/chạy/sửa agent, chat, file, KB, memory, usage hay lịch của B bằng đổi ID; test API trực tiếp, SSE/WebSocket và signed download token.
3. Danh tính Domain không được tự khai: thay external user/unit/domain ID trong payload/prompt không thay actor. Một user có nhiều link Domain chỉ truy cập subject/scope tương ứng; unlink và membership revoked có hiệu lực với job đã xếp lịch.
4. Cư dân thấy được model/MCP/skill đã cấp và bind vào agent, nhưng POST/PATCH/DELETE/sync/hub install/direct workspace upload không sửa hoặc thêm catalog được. Tool không được cấp không thể chạy bằng raw spec.
5. Response `/credential`, API model/catalog, errors, export và client cache không có key platform, kể cả bản legacy từng seed thành own record. Không dùng key thật trong fixture test.
6. Vin KB read-only search và citation/download hoạt động; upload/edit/delete bị từ chối; tài liệu nhân viên/BQL không có trong search candidates hoặc download của cư dân. Private KB chỉ owner đọc; revoke quyền chặn cả runtime đã publish và download token cũ theo policy.
7. Shared resource đi trọn catalog → chọn KB/skill/tool → validate → eval → publish → readiness → chat thật; không chỉ test thấy resource trong danh sách. Private KB không cần BQL duyệt để dùng cá nhân; đưa lên kho chung là một quy trình khác.
8. Hai tab, nhiều workers và fan-out cùng chạm số token cuối không vượt cap; retry/fallback có reservation riêng; hết ngày/tháng đúng timezone, policy override đúng ưu tiên. Worker chết sau provider call không hoàn quota sai rồi cho chi tiếp.
9. Quota đầy qua chat thì Builder/eval/schedule/channel/learning cũng không tạo paid call; việc đang làm có trạng thái rõ để user tiếp tục sau reset/nâng hạn mức.
10. Storage upload đồng thời, inline reference, file lớn, sai declared size, retry job và xóa tài liệu tuân quota byte thật; private document không bị ingest vào kho Vin.

Mức kiểm tra của tài liệu này là **đã đọc source**. Chưa chạy các ca trên; đây là gate cho người triển khai, không phải báo cáo chúng đã đạt.
