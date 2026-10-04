# Nghiên cứu hoàn thiện sáu khoảng trống triển khai — 05/10/2026

Phạm vi: đọc mã ở nhánh `dev_teamChien_HuyDo`, HEAD quan sát `04a5131`, đối chiếu tài liệu chính thức được mở ngày 05/10/2026. Đây là cơ sở thiết kế và tiêu chí nghiệm thu; chưa phải bằng chứng chạy model, trình duyệt, máy chủ ngoài hoặc khôi phục thực tế. Không đọc hay ghi giá trị bí mật `.env`; không thay đổi Git refs hoặc dịch vụ. Không tìm thấy `AGENTS.md` khi kiểm tra danh sách file trong checkout.

Phạm vi đã được người dùng làm rõ trong phiên: Docker local đủ cho đợt hoàn thiện trước; bật CI và gộp PR #31 sau khi checks pass. Vì vậy domain/chứng chỉ public và máy chủ ngoài được giữ thành acceptance tiếp theo, không ngăn hoàn thiện các phần local có thể kiểm ngay.

## 1. Model thật, MCP và luồng mới

Nguồn repo:

- [Reception model adapter](../../../agent-reception/src/runtime/model.py) đã tách provider, URL và key theo vai trò, có `ainvoke` JSON và `complete` tool calls.
- [Coordination provider selection](../../../agent-coordination/src/vinhomes/models.py) và [planner adapter](../../../agent-coordination/src/vinhomes/ports.py) có cấu hình riêng; phân biệt planner với specialist Bot.
- [Bot streaming](../../../agent-bot/src/index.ts) nhận `delta.content` và các mảnh `delta.tool_calls`, chuyển sang AG-UI; trong mã đã đọc chưa giữ metadata suy luận của provider.
- [Tool gateway](../../../services/vinhomes-api/src/vinhomes_api/v3_tool_gateway.py) kiểm agent run, pinned version, release chưa thu hồi, principal/authz version, room actor, coverage và tool grant trước khi đọc dữ liệu. Tool báo cáo không phải đường gọi MCP từ trình duyệt: gateway chạy facade Python trong transaction đã xác thực.

Gemini có endpoint Chat Completions tương thích OpenAI, streaming và function calling. Cần kiểm vòng gọi tool nhiều bước và giữ provider metadata nếu model yêu cầu; một câu chào không nghiệm thu được MCP. [Google official compatibility documentation](https://ai.google.dev/gemini-api/docs/openai).

DeepSeek thinking tool loop yêu cầu gửi lại `reasoning_content` trong các request tiếp theo có `tools`; thiếu có thể bị 400. Suy luận từ mã Bot đang đọc: adapter chỉ chuyển text/tool events chưa đủ để chứng minh tương thích chế độ đó. Có thể thử chế độ không thinking trước, hoặc thêm việc giữ metadata ở runtime theo đúng contract provider. [DeepSeek official thinking documentation](https://api-docs.deepseek.com/guides/thinking_mode/).

Claude compatibility được nhà cung cấp định vị cho thử/so sánh; `response_format` và `strict` bị bỏ qua. Vì Reception và planner yêu cầu JSON, phải validate đầu ra và giữ fail-closed behavior; hỗ trợ URL/key không chứng minh JSON contract đã qua nghiệm thu. Với cấu hình production cần cân nhắc native Messages/Structured Outputs theo nhu cầu thực tế. [Anthropic official compatibility documentation](https://platform.claude.com/docs/en/cli-sdks-libraries/libraries/openai-sdk).

Nghiệm thu tối thiểu:

1. Với từng provider có credential dùng được, ghi image/commit, tên model cấu hình và model trả về, provider, thời điểm, request/run ID và token usage an toàn; không lưu key hoặc payload có dữ liệu cá nhân.
2. Từ resident UI mới: tạo ticket qua chat → hỏi bổ sung → supervisor lập phương án → BQL duyệt → resident đồng ý → đúng một work order. Khởi động lại runtime ở một điểm giữa luồng và chứng minh không nhân đôi tác dụng.
3. Agent báo cáo được phát hành: model thực chọn ít nhất một tool, gateway thực trả dữ liệu đúng phạm vi, assistant dùng kết quả. Có audit/tool-call ID chứng minh, không dùng câu trả lời tự khai đã gọi tool.
4. Negative cases: user bị suspended, release bị revoked, tòa ngoài coverage, tool chưa grant, MCP lỗi hoặc model hết quota. Phải từ chối/ghi lỗi rõ, không fabricate dữ liệu hay tự retry tác dụng không rõ kết quả.
5. Ghi tách mức bằng chứng: unit/contract test; provider smoke; agent + gateway; browser E2E. Thiếu key/quota chỉ là blocked acceptance, không là pass.

## 2. Máy chủ ngoài, TLS, backup, giám sát, CI và PR

Nguồn repo: [Compose](../../../deploy/vinhomes/compose.yml), [Caddyfile](../../../deploy/vinhomes/Caddyfile), [runbook](../../../deploy/vinhomes/README.md). Đã có profile TLS, volumes và healthchecks. Caddyfile hiện route hai giao diện, chưa route endpoint upload S3 công khai. Runbook đang ghi bằng chứng Docker Desktop/TLS nội bộ và ghi rõ chưa có hội thoại thật Gemini/DeepSeek, domain thật, restore. Không nâng các bằng chứng này thành nghiệm thu ngoài máy phát triển.

Đường dẫn `server/scripts/vinhomes-upgrade.ts` trong Compose là đường dẫn trong image: [Dockerfile.tools](../../../deploy/vinhomes/Dockerfile.tools) COPY [deploy/vinhomes/upgrade.ts](../../../deploy/vinhomes/upgrade.ts) tới đó để resolve server packages. Đây là mapping hợp lệ; không đổi chỉ vì file không nằm cùng path trong source checkout.

Caddy tự xin/gia hạn chứng chỉ public khi DNS A/AAAA về đúng host, cổng 80/443 tới Caddy và thư mục dữ liệu ghi được, bền vững. Chứng chỉ `tls internal` không thay thế chứng chỉ public đáng tin cậy. Nghiệm thu từ máy khác phải xác minh hostname, chuỗi tin cậy và HTTPS redirect. [Caddy official automatic HTTPS documentation](https://caddyserver.com/docs/automatic-https).

`pg_dump -Fc` phải restore bằng `pg_restore`; dump một DB không chứa cluster roles/tablespaces. Cần bảo toàn hoặc tái tạo roles/grants bằng quy trình riêng; `pg_dumpall --globals-only` là một lựa chọn. Hai DB không tự có snapshot đồng bộ. [PostgreSQL official backup documentation](https://www.postgresql.org/docs/current/backup-dump.html).

Thiết kế nghiệm thu backup theo repo:

- Backup nghiệp vụ + checkpoint Supervisor + bucket/file + `CONNECTIONS_KEY` và các bí mật cần khôi phục, cùng manifest phiên bản/checksum; giữ Reception state nếu muốn tiếp tục hội thoại đang dở.
- Tránh tar volume MinIO đang ghi; quiesce writes cho backup đồng bộ hoặc dùng giải pháp snapshot/object backup phù hợp. Restore vào DB, bucket và network cô lập; không ghi đè hệ đang chạy.
- Chạy app trên bản restore, đối chiếu số bản ghi quan trọng, RLS/grants, hash ảnh, phiên đang dở và agent release. Resume Supervisor không sinh work order thứ hai. Ghi thời gian backup và restore để có RPO/RTO thực đo.
- Có bản sao ngoài host nguồn mới nghiệm thu được mất máy chủ; bản restore local chỉ chứng minh quy trình restore local.

Prometheus alert rules đánh giá điều kiện, `for` điều khiển khoảng chờ firing; gửi notification cần Alertmanager hoặc receiver thực. [Prometheus official alerting rules](https://prometheus.io/docs/prometheus/latest/configuration/alerting_rules/). [Alertmanager official configuration](https://prometheus.io/docs/alerting/latest/configuration/).

Giám sát cần endpoint/API unreachable, model quota/auth failure, runtime unknown/stuck outcome, backup quá hạn, storage lỗi và certificate expiration. Nghiệm thu một lỗi có chủ đích trong môi trường cô lập, ghi alert pending/firing và receiver nhận thực; chỉ có healthcheck/config YAML chưa đủ. Không gửi Slack/email thật nếu chưa có chỉ thị người dùng cho kênh đó.

CI từng được quyết định tắt; người dùng đã đổi quyết định trong phiên này, yêu cầu bật CI và merge PR #31 khi checks pass. Merge cần đọc state/base/head/checks/conflicts hiện thời và thực hiện checks trên head cuối; không dùng số PR hoặc commit trong tài liệu làm bằng chứng đã merge.

## 3. Admin tạo đơn vị quản lý từ UI

[Admin API](../../../services/vinhomes-api/src/vinhomes_api/v3_admin.py) tự mô tả read-only; [UnitsPage](../../../app/src/features/vinhomes-operations/connected/admin/Platform.tsx) chỉ render danh sách. [Provision script](../../../services/vinhomes-api/scripts/provision_connected.py) đang tạo `management_units`, `access_scopes`, `management_coverage`, `workspaces`, room/channel và membership theo fixture.

Đơn vị mới phải tạo được bundle có thể sử dụng, trong một transaction: unit → management scope → coverage các tòa/category được chọn → workspace → management channel; thêm manager/membership nếu form có chọn người. Không sao chép dữ liệu demo như tòa/căn hộ/ca trực năm năm của script vào API production. Dùng actor/tenant đã xác thực, admin check, kiểm các ID cùng tenant, uniqueness và idempotency; không nhận tenant hoặc role authority từ body.

Nghiệm thu: admin tạo unit qua UI hiện có; unit hiện ngay; tài khoản BQL gán vào unit thấy đúng room/coverage; user thường bị 403; building/category sai tenant bị từ chối; retry không tạo đôi; audit chứa actor và IDs. Giữ form/UI conventions của màn hiện có.

## 4. Agent báo cáo tự xuất hiện ở triển khai mới

[tool_catalogue.register](../../../services/vinhomes-api/src/vinhomes_api/tool_catalogue.py) chỉ đăng ký `mcp_servers`/`mcp_tools`, không tạo agent. Provision script đang tạo Supervisor và Reception, chưa tạo report agent. [create_agent](../../../services/vinhomes-api/src/vinhomes_api/v3_room_agents.py) trả `draft` và `execution: record-only`; [agent review lifecycle](../../../services/vinhomes-api/src/vinhomes_api/v3_agent_reviews.py) sở hữu version/release/approve/revoke. [Factory/evaluation endpoints](../../../services/vinhomes-api/src/vinhomes_api/v3_agent_builder.py) chỉ tự ghi runtime-verified evidence sau round thực.

Bootstrap ít rủi ro: idempotent per workspace, tạo/bind draft agent cùng preset instructions và bốn grant báo cáo đúng catalogue hiện tại, để BQL hoàn tất eval/review/publish bằng flow hiện có. Nếu muốn auto-publish trusted built-in phải ghi nguồn artifact/version/evaluation có thật và policy system release riêng; không ghi `_runtime_verified=true` hoặc fake cases cho lần triển khai mới.

Exact preset đã lưu: [docs/teams/hoang/agent/report-agent.md](../hoang/agent/report-agent.md) là instructions bản 2 hiện tại, [README của preset](../hoang/agent/README.md) chứa mô tả và sáu ca đánh giá đã dùng. Chỉ dẫn yêu cầu gọi `reporting__filter_report_scope` với `{}` trước, lấy IDs từ tool, kỳ `[from_date,to_date)`, phân biệt `empty`/`failure`, không tự ghi số 0 khi lỗi, từ chối writes/dự báo và kết thúc bằng `— Agent Báo cáo`. Bootstrap giữ `service_categories=[]`: agent này trả lời room mention, không tự được Supervisor mời vào mọi phiên nghiệp vụ. `agent-report/examples/management-a.json` là report template synthetic, không phải agent runtime configuration. Sáu ca preset kiểm identity/refusal/clarification; vẫn cần thêm ca model gọi tool thật để nghiệm thu mục 1.

[Report module README](../../../agent-report/README.md) định nghĩa bốn tool hiện tại: `filter_report_scope`, `get_repair_bill_summary`, `get_ticket_frequency_summary`, `get_employee_star_summary`. [Research/progress 04/10](BQL_B1_B6_PROGRESS_2026-10-04.md) ghi tên tool cũ không còn hợp lệ và repair category cần cấu hình theo nghiệp vụ; bootstrap phải dùng descriptors thực, không copy tool cũ từ historical config.

Nghiệm thu: DB mới sau upgrade/catalogue/bootstrap có agent trong mỗi active management room; chạy lại không tạo đôi, không ghi đè cấu hình đã sửa hoặc auto-reactivate release đã revoke; grants đều tồn tại và read-only; draft/published states hiển thị đúng. Model tool-call acceptance vẫn thuộc mục 1.

## 5. Hợp nhất đăng nhập và kết nối theo từng người

[password_auth](../../../services/vinhomes-api/src/vinhomes_api/password_auth.py) dùng `vinhomes-password-v1`, cookie `vinhomes_session`, token hash namespace `vinhomes-v1:` và tự mô tả độc lập SSO OpenBot. [OpenBot auth](../../../server/src/auth/index.ts) dùng Better Auth trên cùng users/accounts/sessions schema; chia sẻ table không làm cookie/hash/password scheme tương thích.

Seam đã có: [v3_auth._actor_id](../../../services/vinhomes-api/src/vinhomes_api/v3_auth.py) khi không password/demo/fixed-user sẽ GET `settings.auth_url` với cookie, lấy `session.user.id`, sau đó V3 vẫn kiểm active user, tenant membership và scoped role. [V3Settings](../../../services/vinhomes-api/src/vinhomes_api/v3_config.py) hiện cấm đồng thời password auth + auth URL. [OpenBot request guard](../../../server/src/auth/guards.ts) tắt cookie cache khi kiểm session và đọc role DB hiện thời. Có thể dùng seam này hoặc explicit session bridge, nhưng phải xác định login/logout/password-change/revocation behavior xuyên hai app.

Better Auth `getSession` là nơi kiểm phiên chuẩn; nếu dùng cache phải xét cửa sổ revocation, và server có thể yêu cầu `disableCookieCache`. [Better Auth official session management](https://better-auth.com/docs/concepts/session-management). [Better Auth Hono integration](https://better-auth.com/docs/integrations/hono).

Hợp nhất identity chưa tự giải quyết credential MCP theo người. [v3_connections](../../../services/vinhomes-api/src/vinhomes_api/v3_connections.py) hiện lưu token sealed gắn server/workspace, dùng chung theo nhóm. [OpenBot OAuth flow](../../../server/src/plugins/oauth.ts) có state gắn `userId` nhưng phải kiểm actual store/resolver trước khi dùng lại. Implementation phải chọn đúng credential bằng verified actor + server/resource + scope, bảo đảm user B không nhận token của user A, và có revoke/reconnect riêng.

OpenBot đã có phần per-user: [plugin store](../../../server/src/plugins/store.ts) `connectionTokenFor` kiểm `mcpUserCredentials` theo `(serverId, actorId)` và từ chối actor trống/chưa kết nối; `swapUserCredential` lưu refresh token vào vault encrypted với kind `mcp_user_token`, provider=server, keyId=user, rồi cập nhật pointer trong cùng transaction. [Schema](../../../server/src/db/schema/tables.ts) có `mcp_user_credentials` với tenant/server/user/credential/scope. Nên tái sử dụng canonical `users.id` và resolver này, không tạo kho token theo người thứ hai chỉ để nối login.

Khuyến nghị phù hợp tài khoản mật khẩu đang có, dưới dạng seam để implementation quyết định:

1. Tạo adapter `AuthService` cho OpenBot nhận business session authority: `getSession({headers})` trích duy nhất `vinhomes_session`, gọi fixed configured `/auth/session` trên API và lấy `user.id`; DB role repository của OpenBot vẫn tự kiểm roles/status hiện thời. Không tin role/user ID từ browser header/body, không chuyển mọi cookie cho authority.
2. Nếu có Better Auth provider, có thể bọc provider hiện tại để xác thực từng cookie namespace theo authority sở hữu nó. Khi hai session hợp lệ trỏ hai `users.id` khác nhau, từ chối hoặc buộc chọn account; không âm thầm dùng account có role mạnh hơn.
3. Cấu hình business authority riêng thay vì bật giả Google/Entra/Okta: [server config](../../../server/src/config.ts) hiện không cho Better Auth secret/base URL khi chưa có provider. Giữ validation cho provider, instantiate adapter qua nhánh riêng tại [server index](../../../server/src/index.ts). Không mở single-user fallback cho Docker phục vụ nhiều tài khoản.
4. `/api/auth/get-session` và `/api/me` trên OpenBot phải phản ánh same user từ adapter; sign-out cần revoke business session và xóa đúng cookie trên origin đang dùng, cùng Better Auth session khi có. Xác định đổi mật khẩu/suspend/revoke/session expiry với fresh checks và tests, không rewrite password hash để tương thích.
5. Hai origin khác hostname không tự chia sẻ host-only cookie. Ưu tiên same-origin proxy local cho app/API hoặc single-use expiring handoff; không đặt cookie `.example.com` để thử giải quyết bằng cách mở rộng mọi subdomain. Nếu có handoff phải bảo vệ state/Origin và actor mismatch theo precedent [organization auth](../../../server/src/auth/organization.ts).

Giới hạn Docker stack quan sát: [Dockerfile.operations](../../../deploy/vinhomes/Dockerfile.operations) chỉ mang app build + [app/serve.ts](../../../app/serve.ts). `businessTarget` chuyển `/api/business` tới business API, còn các `/api/*` khác tới loopback 3001. Compose `openbot` là **agent-bot** 4200/AG-UI, không phải platform server có Better Auth, vault và plugin OAuth. Vì vậy muốn nghiệm thu unified auth/per-user connections của full OpenBot trong Docker cần thêm platform server/proxy/runtime đúng vào stack, hoặc mô tả chính xác acceptance hẹp chỉ business API/technical host. Không coi agent-bot health 200 là full server auth integration.

MCP không cho dùng token passthrough chưa kiểm issuer/audience; OAuth proxy cần per-user/per-client consent và redirect/state validation. Không chuyển cookie/token nghiệp vụ nguyên trạng sang bên thứ ba. [MCP official security best practices](https://modelcontextprotocol.io/docs/2025-11-25/tutorials/security/security_best_practices).

Nghiệm thu: login một lần vào cả hai app nhận cùng `users.id`; logout/suspend/password change làm mất quyền theo chính sách đã chọn; không nhập identity/role bằng header do trình duyệt cung cấp. Hai tài khoản kết nối cùng một MCP độc lập; audit quy trách nhiệm actor thật; chỉ gửi credential của user đúng tới đúng resource và không lộ secret trong UI/log.

## 6. Ảnh upload trực tiếp MinIO

Nguồn repo: [storage abstraction](../../../services/vinhomes-api/src/vinhomes_api/storage.py), [conversation upload lifecycle](../../../services/vinhomes-api/src/vinhomes_api/v3_conversation_images.py), [ticket evidence](../../../services/vinhomes-api/src/vinhomes_api/v3_files.py). Backend hiện nhận bytes qua API rồi `put_object`; conversation đã có initiate/PUT/complete và expected size/SHA-256 nhưng `uploadUrl` trỏ API, field `storage` vẫn ghi `local-demo`. Complete yêu cầu `uploaded` do API PUT ghi; direct upload phải thay điều kiện đó bằng xác minh object thực.

MinIO SDK có presigned PUT và presigned POST policy; POST policy hỗ trợ điều kiện kích thước. CORS cần origin/method/header của app thực nếu browser gọi khác origin. Phải đối chiếu phiên bản SDK/image đã pin trước khi dùng API CORS mới. [MinIO official Python API](https://github.com/minio/minio-py/blob/master/docs/API.md).

Presigned upload mang quyền của signer và có thể ghi đè object cùng key. URL phải giữ nguyên host/path/parameters đã ký; content-type phải đúng khi đã ký. [AWS official presigned upload documentation](https://docs.aws.amazon.com/AmazonS3/latest/userguide/PresignedUrlUploadObject.html). Suy luận implementation: URL cũ còn hiệu lực có thể sửa object vừa nghiệm thu; cần upload vào key staging riêng rồi server-side copy/promote sang key accepted, hoặc pin version thật và mọi đường đọc dùng version đó.

Thiết kế tối thiểu:

1. API initiate kiểm tenant/actor/owned chat hoặc visible ticket, cấp object key random có tenant prefix, expected size/hash/mime, expiry ngắn. Không nhận bucket/key tùy ý từ browser.
2. Dùng signing endpoint browser-reachable riêng với internal endpoint; `http://minio:9000` trong Compose không truy cập được từ browser máy ngoài. Caddy/proxy phải giữ Host và path ký; không ký rồi đổi hostname trong URL.
3. Browser PUT trực tiếp bằng fetch không gửi cookie API sang object host; chỉ metadata/initiate/complete đi qua API. Tránh tự prefix `/api/business` vào absolute upload URL.
4. Complete kiểm actual stat, size, SHA-256 và decode image bằng `validate_image`, promote/pin content rồi ghi `file_objects` và trạng thái ready trong transaction có idempotency. S3 ETag không được coi là SHA-256 nếu không có bảo đảm tương ứng. API đọc để validate không làm biến đổi ý nghĩa upload trực tiếp: bytes từ browser đi tới MinIO.
5. Không dùng UUID tự sinh làm S3 version ID thực. Giữ bucket private; download vẫn có kiểm quyền hoặc URL download có expiry riêng. Cleanup uploads hết hạn/lỗi không có reference.

Nghiệm thu: network trace browser chứng minh bytes gửi object endpoint, API chỉ metadata; ảnh trước/sau trong ticket và ảnh resident chat đều tới bucket; retry/complete idempotent; sai size/hash/mime/quyền/expiry bị từ chối; URL cũ không sửa ảnh ready; đọc lại hash đúng; fallback local vẫn hoạt động nếu được cấu hình. Không gọi direct upload hoàn tất khi chỉ một route chat đã chuyển còn ticket evidence vẫn đi API.

## Kết quả của nghiên cứu

Các khoảng trống 3, 4 và 6 có seams cụ thể trong repo để triển khai. Mục 5 cần xác định đồng thời session authority và credential authority theo actor; chia sẻ cookie không đủ. Mục 1 và phần ngoài host của mục 2 chỉ được đóng bằng lần chạy thực trên môi trường/credential dùng được. Tài liệu này không thay thế việc đọc branch/PR state hiện thời hoặc các checks của implementation.
