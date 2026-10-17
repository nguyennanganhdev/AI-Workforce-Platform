# Hợp đồng Domain–Platform và phân công hai người trên dev_Chien

Ngày: 18/10/2026, giờ Việt Nam. Source kiểm tra: `dev_Chien@1ec4465d7f2928f9610b02b0126d39b1443f4163`. Tài liệu này là nghiên cứu để viết **hai phần triển khai song song cho hai người**, không phải xác nhận đã triển khai, đã chạy test hay đã nghiệm thu. Chỉ đọc code/test/config công khai trong repo; không truy cập production, secret hoặc model. Không yêu cầu khôi phục JEV.

## 1. Kết luận để chia việc

**Làm rõ theo chủ dự án ngày 18/10:** khách hàng dùng chính giao diện Platform hiện có, đủ chức năng cá nhân và cách ly dữ liệu với BQL/người khác. Không tạo portal/shell/dashboard cư dân, không thiết kế lại sidebar hoặc bộ màn hình đã có. Người B chỉ bổ sung capability, dữ liệu riêng, chế độ chỉ đọc catalog và phần UI nghiệp vụ còn thiếu vào các trang/component hiện có. Provider/MCP/Skill được cấp vẫn xem/chọn/dùng được; quyền sửa cấu hình quản trị tách riêng. Trang Kênh vẫn dùng cho bot riêng. BQL/admin giữ luồng cũ; staff tác nghiệp trên Domain. Phạm vi frontend do B sở hữu là ranh giới sửa file, không phải giao làm lại UI; đối chiếu mục 0.0 Phần 2 khi review code đã làm.

**Người A sở hữu toàn bộ Domain Vinhomes**: API, app resident/staff/operations, auth/link authority, resident intake, grants, nghiệp vụ, schema/migration, worker đồng bộ và test của Domain. Người B không sửa `vinhome_Recident/**` để làm tạm adapter; gửi yêu cầu thay contract cho A.

**Người B sở hữu trải nghiệm và runtime Platform**: cửa vào cư dân/BQL/admin, Leader/team/chat, agent cá nhân/Builder, eval, lịch/kênh, adapter gọi Domain, private case projection, consent UI và vận hành user. B dùng API/grant/event contract do A cung cấp, không query DB Domain.

Phân công chốt cho hai phần: **A=nền tảng/authority + toàn bộ Domain; B=runtime/trải nghiệm + triển khai Platform**. A còn sở hữu Platform IAM/access/catalog/model gateway, toàn bộ storage/migrations/shared contracts, bootstrap/app registration và backend customer/manager authority/projections. B consume resolver/gate/storage/contract của A, gửi schema/mount delta cho A, không viết policy thứ hai. Mục 8 ghi ranh giới file cụ thể để hai người không cùng sửa hot spots.

Hợp đồng đầu tiên cần chốt trước khi chia nhánh, nhưng sau đó A làm producer và B làm consumer bằng fixtures/schema cùng phiên bản. Không chia thành “A làm xong backend toàn bộ rồi B mới bắt đầu UI”.

## 2. Source hiện có và khoảng cần thay đổi

| Mặt cắt | Sự thật source đã kiểm tra | Hệ quả cho hai người |
|---|---|---|
| Domain user auth | `v3_auth._actor_id` resolve session hoặc delegation, không phải nhận resident ID tùy ý. [v3_auth.py:16](../../vinhome_Recident/services/vinhomes-api/src/vinhomes_api/v3_auth.py#L16) | A cấp link/grant từ authority thật; B gửi context được server xác thực, không tự giả `X-User-ID`. |
| Delegation cũ | `/integration/v1/delegations/self` từ phiên Domain login, TTL tối đa 600s, catalog/purpose giới hạn và recheck user/member/client. [integration.py:25](../../vinhome_Recident/services/vinhomes-api/src/vinhomes_api/integration.py#L25), [integration.py:114](../../vinhome_Recident/services/vinhomes-api/src/vinhomes_api/integration.py#L114), [integration.py:283](../../vinhome_Recident/services/vinhomes-api/src/vinhomes_api/integration.py#L283) | Có thể tái dùng business read, chưa phải account-link authorization-code flow đã hoàn chỉnh. |
| Resident self | Có `resident.me/context/tickets` trong integration catalog; có services homes/rules/balance/cards/visitors/amenities. [integration.py:58](../../vinhome_Recident/services/vinhomes-api/src/vinhomes_api/integration.py#L58), [resident_services.py:578](../../vinhome_Recident/services/vinhomes-api/src/vinhomes_api/resident_services.py#L578) | A bọc thành resident API/grant trước-ticket; B không ép tạo fake ticket chỉ để hỏi tài sản/cư trú. |
| API request/case đã có | Contract resident v0.1 dùng base `/api/domains/vinhomes/resident`; có `/me`, `/requests`, `/requests/{id}/confirm`, `/reopen`. [resident_contract.py:17](../../vinhome_Recident/services/vinhomes-api/src/vinhomes_api/resident_contract.py#L17), [resident_api.py:114](../../vinhome_Recident/services/vinhomes-api/src/vinhomes_api/resident_api.py#L114), [resident_api.py:163](../../vinhome_Recident/services/vinhomes-api/src/vinhomes_api/resident_api.py#L163), [resident_api.py:223](../../vinhome_Recident/services/vinhomes-api/src/vinhomes_api/resident_api.py#L223) | Có case public projection để tận dụng; không đồng nhất case Domain với workflow/conversation Platform. |
| Ticket intake cũ | `/resident/chats/{channel_id}/tickets` gọi shared helper kiểm chat owner, residence và coverage. Helper cuối cùng tự gọi `platform.link_ticket()`. [v3_resident.py:243](../../vinhome_Recident/services/vinhomes-api/src/vinhomes_api/v3_resident.py#L243), [v3_resident.py:253](../../vinhome_Recident/services/vinhomes-api/src/vinhomes_api/v3_resident.py#L253), [v3_resident.py:330](../../vinhome_Recident/services/vinhomes-api/src/vinhomes_api/v3_resident.py#L330), [v3_resident.py:452](../../vinhome_Recident/services/vinhomes-api/src/vinhomes_api/v3_resident.py#L452) | A tách intake business transaction khỏi legacy auto-start. B gửi existing case/workflow + source proof; không gọi thẳng helper bypass chat ownership. |
| Case materialization cũ | Route operations materialize case dùng actual actor riêng và requester riêng rồi gọi helper tạo ticket. [resident_api.py:286](../../vinhome_Recident/services/vinhomes-api/src/vinhomes_api/resident_api.py#L286) | Là ví dụ giữ actor audit đúng; không sao chép đường operations này cho cư dân mà bỏ operator authorization. |
| Legacy bridge binding | `platform_links` bắt buộc `channel_id`, user, management ref; platform command có start/reply/approval/close. [0014_platform.sql:12](../../vinhome_Recident/services/vinhomes-api/src/vinhomes_api/schema/migrations/0014_platform.sql:12), [0014_platform.sql:43](../../vinhome_Recident/services/vinhomes-api/src/vinhomes_api/schema/migrations/0014_platform.sql:43) | A phải migrate hoặc thêm binding chuẩn cho Platform-origin; không ghi session Platform giả vào trường Domain chat rồi coi là hợp lệ. |
| Ticket MCP grants | Issuer hiện join `platform_commands.kind='start_workflow'`, external command ID và active link; runtime client còn parse external_request UUID. [platform_access.py:89](../../vinhome_Recident/services/vinhomes-api/src/vinhomes_api/platform_access.py#L89), [_grants.py:26](../../platform_VP/agentscope/src/agentscope/app/workforce/integrations/unified/_grants.py#L26) | Chỉ thêm origin binding chưa đủ. A bổ sung authority và shared exchange có discriminated origin/reference; B runtime consume exchange đó. |
| Source intent cũ | Cancel/reschedule kiểm `source_message_id` thuộc `messages` Domain, requester, ticket và 24h. [platform_work.py:560](../../vinhome_Recident/services/vinhomes-api/src/vinhomes_api/platform_work.py#L560) | A nhận proof Platform được ký và kiểm tương đương; B ký proof từ user session/server message, không từ model text. |
| Job events không bao hết case | `provider_events()` trả None nếu work không có `platform_operations.client_reference`, tức không phải việc Platform dispatch. [platform.py:730](../../vinhome_Recident/services/vinhomes-api/src/vinhomes_api/platform.py#L730) | Phải có case events cho intake/manual work/consent/exception, bên cạnh operation-correlated job events hiện có. |
| Publication | Quote/completion/ảnh có gate theo đúng event/job đã `applied`, không chỉ nhận HTTP202. [platform_publication.py:7](../../vinhome_Recident/services/vinhomes-api/src/vinhomes_api/platform_publication.py#L7), [platform_publication.py:23](../../vinhome_Recident/services/vinhomes-api/src/vinhomes_api/platform_publication.py#L23), [platform_sync.py:450](../../vinhome_Recident/services/vinhomes-api/src/vinhomes_api/platform_sync.py#L450) | A xuất decision projection và kiểm acknowledgement; B render card sau projection bền vững, ack không cần model. |
| BQL read | Có sáu tool management; grant theo explicit Platform tenant/domain/area/user → Domain management/site/zone binding. [platform_mcp.py:139](../../vinhome_Recident/services/vinhomes-api/src/vinhomes_api/platform_mcp.py#L139), [platform_management.py:67](../../vinhome_Recident/services/vinhomes-api/src/vinhomes_api/platform_management.py#L67), [0025_platform_management_grants.sql:2](../../vinhome_Recident/services/vinhomes-api/src/vinhomes_api/schema/migrations/0025_platform_management_grants.sql:2) | Giữ đường đọc BQL riêng. Nó không cấp quyền thực thi ticket/QC/approval. |
| BQL ở Platform | `manager_clients` chỉ cho `AREA_MANAGER active`, đọc current area từ auth DB mỗi run, clone client riêng. [management_mcp.py:12](../../platform_VP/agentscope/src/agentscope/app/_service/_management_mcp.py#L12) | DOMAIN_ADMIN/PLATFORM_ADMIN không tự có quyền dữ liệu Domain. BQL đa membership về sau cần resolver mới, không chọn area bằng prompt. |
| BQL không còn Domain login mặc định | Password auth từ chối management-only account; operations connection non-demo nhận staff hoặc admin. [password_auth.py:121](../../vinhome_Recident/services/vinhomes-api/src/vinhomes_api/password_auth.py#L121), [v3_auth.py:60](../../vinhome_Recident/services/vinhomes-api/src/vinhomes_api/v3_auth.py#L60) | Không ghi chung “BQL quay lại app Domain duyệt là xong”. Nếu cần human action trên Platform, A phải bổ sung operator action facade có quyền thật. |
| Nhân viên Domain | `my-work-orders` chỉ người được phân công, scope DB giới hạn. Assignment response chỉ assigned staff; QC độc lập và onsite report là hai nhánh. [v3_operations.py:107](../../vinhome_Recident/services/vinhomes-api/src/vinhomes_api/v3_operations.py#L107), [v3_mutations.py:681](../../vinhome_Recident/services/vinhomes-api/src/vinhomes_api/v3_mutations.py#L681), [v3_specialized.py:86](../../vinhome_Recident/services/vinhomes-api/src/vinhomes_api/v3_specialized.py#L86), [v3_specialized.py:138](../../vinhome_Recident/services/vinhomes-api/src/vinhomes_api/v3_specialized.py#L138) | Giữ app staff/technical/security và service nghiệp vụ; chỉ chuyển customer/BQL điểm vào, không xóa hệ thống thực hiện việc thật. |

## 3. Tách official service worker khỏi resident principal

Source cũ chạy partner ticket dưới manager Leader: `_case_session()` tạo session/binding có `manager_account_id`; `_share()` và context reader cũng truy xuất Shared Context theo manager owner. [runner.py:551](../../platform_VP/agentscope/src/agentscope/app/workforce/integrations/unified/_runner.py#L551), [case.py:1071](../../platform_VP/agentscope/src/agentscope/app/workforce/integrations/unified/_case.py#L1071), [case.py:1119](../../platform_VP/agentscope/src/agentscope/app/workforce/integrations/unified/_case.py#L1119)

Template trong `_agent_templates.py` là **starter AgentSpec có field editable và tool IDs để trống**, không phải official service identity hay bằng chứng một Domain đã được tích hợp. [agent_templates.py:1](../../platform_VP/agentscope/src/agentscope/app/_agent_templates.py#L1)

Thiết kế đề xuất phải có execution context rõ, không đổi nghĩa `manager_account_id`:

```json
{
  "schema_version": "vin.execution.v1",
  "runtime_owner_id": "service-or-personal-resource-owner",
  "acting_platform_user_id": "authenticated-user",
  "acting_domain_subject": "verified-linked-subject",
  "billing_subject_id": "quota-owner",
  "customer_workspace_id": "private-workspace",
  "case_id": "platform-case",
  "workflow_id": "same-existing-workflow",
  "domain_binding_id": "authority-binding",
  "execution_mode": "resident_service",
  "authorization_revision": 1,
  "environment": "sandbox-or-production"
}
```

Đây là mẫu contract mới. Các quy tắc producer/consumer:

- A cung cấp principal/capability/link/grant policy và schema. B tạo context từ authenticated request/job claim, không từ prompt, tool args hoặc owner của AgentRecord.
- Official service agent/version có thể do service sở hữu, nhưng mỗi run/session/Shared Context/memory/cache được partition theo customer + case + environment. Không dùng một session của service/manager cho nhiều cư dân.
- User dùng official capability không được quyền sửa agent/version/package/tool của service. Clone template thành agent cá nhân chỉ tạo tài nguyên của user, không clone authority/credential hoặc `official` flag.
- Quyền runtime là giao của entitlement user + link Domain + case/ticket authority + allowlist official capability + environment; custom prompt không thể làm rộng giao quyền này.
- Operation đang pending sau unlink cần service reconciliation grant chỉ đọc trạng thái operation cụ thể đã chấp nhận. Nó không cho tiếp tục mutation mới, đọc hồ sơ khác hoặc gửi private data tới một customer đã mất quyền.
- Handoff cho người thật tạo exception/task tối thiểu, có scope/receiver. Không tự đưa BQL vào personal team hoặc mở toàn bộ conversation. `share_attention()` hiện chỉ ghi lỗi vào room, không tự chứng minh đã có hàng đợi operator đúng quyền. [case.py:1096](../../platform_VP/agentscope/src/agentscope/app/workforce/integrations/unified/_case.py#L1096)

## 4. Contract HTTP mới đề xuất cho lane Domain

**Tất cả route `/platform/v1/...` trong mục này là đề xuất, chưa tồn tại ở HEAD.** Route hiện có của Domain là `/platform/mcp-grants`, `/platform/management-grants`, `/integration/v1/...`, resident contract v0.1 và `/mcp`; đừng ghi nhầm prefix mới thành tính năng đã triển khai. [platform_access.py:64](../../vinhome_Recident/services/vinhomes-api/src/vinhomes_api/platform_access.py#L64), [platform_management.py:75](../../vinhome_Recident/services/vinhomes-api/src/vinhomes_api/platform_management.py#L75), [integration_cases.py:31](../../vinhome_Recident/services/vinhomes-api/src/vinhomes_api/integration_cases.py#L31), [platform_mcp.py:294](../../vinhome_Recident/services/vinhomes-api/src/vinhomes_api/platform_mcp.py#L294)

Prefix trên là path nội bộ API Domain. Gateway public prefix phải được ghi riêng trong deployment manifest; không suy prefix từ port như heuristic management client hiện tại. [management_mcp.py:34](../../platform_VP/agentscope/src/agentscope/app/_service/_management_mcp.py#L34)

| API đề xuất | Request/authority tối thiểu | Response và rule bắt buộc | Producer / consumer |
|---|---|---|---|
| `GET /platform/v1/links/authorize` | Client đăng ký, exact redirect, state, PKCE challenge, nonce, scopes; user đăng nhập/consent tại Domain | Code một lần, TTL ngắn, bound client/redirect/challenge/subject; không trả password/session | A Domain producer; B mở redirect từ Platform link intent |
| `POST /platform/v1/links/token` | Backend client auth + code/verifier/redirect; xác thực link transaction của Platform | Link ID, issuer/subject, granted scopes, consent version, expiry, opaque server credential/reference; private no-store | A phát; B backend exchange, không frontend/model |
| `POST /platform/v1/links/{id}/revoke` | Chính user đã link hoặc trusted Domain revoke authority | Idempotent receipt, authorization revision mới; revoke active grants, event invalidation | A authority; B ngừng job/call mới và dọn cache |
| `POST /platform/v1/resident-grants` | Client auth + link, acting user, conversation/run, tool list, residence tùy operation, purpose, env, TTL, request ID | Token ngắn hạn, subject/resource/tools/env/revision khớp; Domain recheck account + entitlements | A phát; B runtime inject token ngoài prompt |
| `GET /platform/v1/self/context` | Resident bearer; không có user ID tự chọn | Subject display tối thiểu, homes/relation/capabilities, current revision, missing entitlements | A reuse verified services; B cho user chọn home khi cần |
| `POST /platform/v1/requests/prepare` | Resident grant, residence ref, service/category, user content, source proof, attachments đã authorize | Draft/prepare ID, normalized preview, missing fields, allowed next actions, canonical rules; chưa tạo việc thật | A xác minh; B render confirmation |
| `POST /platform/v1/requests` | Resident grant + prepare ID/version + explicit user confirmation + Idempotency-Key + Platform existing case/workflow descriptor | Ticket/domain case/binding IDs, canonical version, receipt, origin, route reference; retry same payload same result | A transaction; B bind private case và giữ original workflow |
| `POST /platform/v1/cases/{binding_id}/ticket-grants` | Client auth + active link/subject + Platform-origin binding + allowed tools, TTL/env/request ID | Ticket/workflow/subject/resource scoped bearer; không yêu cầu fake Domain-start command | A grant authority và shared `_grants` exchange; B runtime gọi interface đó |
| `GET /platform/v1/cases/{binding_id}` | Resident bearer hoặc exact reconciliation scope | Canonical snapshot, safe progress/evidence refs, pending decision, versions/sequences và `next_action` | A projection; B render, không đọc nội bộ staff |
| `POST /platform/v1/cases/{binding_id}/commands` | Action allowlist, expected version, source intent, exact args/hash, consent proof, idempotency | Command receipt/status; action-specific checks; cùng key khác payload → 409 | A service rules; B endpoint user/session hoặc tool theo mode |
| `GET /platform/v1/operations/{command_id}` | Owner subject + bound case hoặc reconciliation service grant chỉ operation đó | Durable result, `pending/applied/failed/unknown`, retry guidance; không khởi động mutation | A authority; B repair timeout không gọi lại với key mới |
| `GET /platform/v1/cases/{binding_id}/events` | Resident/service exact case grant + signed cursor, limit | Ordered committed events, next cursor, has_more; mất cursor → snapshot/reset marker | A producer; B consume/replay idempotent |
| `POST /platform/v1/cases/{binding_id}/projection-acks` | Trusted Platform consumer + exact event/projection IDs, hash và canonical version | Applied acknowledgement idempotent; không coi accepted queue là customer đã nhận/đồng ý | A lưu gate; B ack sau durable projection, không cần LLM |
| `GET /platform/v1/management/exceptions` | Operator read grant đã bind tenant/domain/area/management unit | Exceptions phân trang đúng scope, safe summary, reason, SLA, required capability; không personal transcript | A producer; B BQL inbox |
| `POST /platform/v1/operator-grants` | Trusted client + current operator identity/membership + exact case/resource/actions, purpose, TTL/env | Read/action grant riêng với allowed operations và scope; không nâng management-read token | A authority; B broker từ authenticated operator |
| `POST /platform/v1/management/exceptions/{id}/commands` | Operator grant, expected version, action, exact args, user/operator consent, idempotency | Acknowledge/escalate/assign/propose/QC theo quyền thật; independent reviewer checks; audit actor | A enforce; B UI nhận việc/quyết định |

Không nhất thiết giữ mọi route thành endpoint riêng nếu service hiện có đáp ứng an toàn; có thể gộp prepare/create/command trong một contract có discriminator. Nhưng hai người phải đóng băng shape/semantics trước khi code producer và consumer; không để frontend phụ thuộc tên giả chưa có OpenAPI.

### 4.1. Platform-origin transaction và grant exchange

`origin=platform` là discriminator được server xác thực từ client/binding, không phải cờ do user hoặc model tự dùng để bỏ gate. A xác minh signed descriptor `{platform_tenant, customer_subject, link, case, workflow, audience, nonce, expires_at}` và lưu immutable binding cùng receipt tạo ticket. Sau đó:

1. Tái dùng residence/category/coverage, attachments và business validation từ intake service.
2. Tạo canonical request/ticket và Platform-origin binding trong cùng transaction Domain; không queue `start_workflow` và không tạo conversation/group mới ở Platform.
3. Ticket-grant issuer xác thực binding này thay điều kiện `platform_commands.start_workflow`; `origin=domain` tiếp tục contract cũ.
4. Khi response mất, cùng idempotency request trả cùng ticket/binding. B không start workflow lần nữa hoặc thay reference.
5. Nếu Platform projection chưa bind được sau Domain commit, B repair từ receipt; không xóa ticket thật để “rollback giao diện”.

Các ràng buộc này là đề xuất sửa ba phụ thuộc source: auto-link helper, non-null Domain channel binding và Domain-start grant exchange. [v3_resident.py:452](../../vinhome_Recident/services/vinhomes-api/src/vinhomes_api/v3_resident.py#L452), [0014_platform.sql:12](../../vinhome_Recident/services/vinhomes-api/src/vinhomes_api/schema/migrations/0014_platform.sql:12), [platform_access.py:89](../../vinhome_Recident/services/vinhomes-api/src/vinhomes_api/platform_access.py#L89)

### 4.2. SourceIntent dùng chung

Mẫu mới: `intent_id`, `issuer/client_id`, `platform_user`, `domain_subject/link_id`, `case/ticket`, `source_event_id`, `source_content_hash`, `action`, `payload_hash`, `expected_version`, `consent_kind`, `nonce`, `iat/exp`, `environment`, `authorization_revision`, signature/key ID.

Backend Platform tạo proof sau xác thực user/callback actor và exact action; model chỉ gửi đề xuất. Domain kiểm issuer, audience, signature, TTL, nonce/replay, link/revision, payload/hash/version và business ownership; không tin `source_event_id` hoặc `consent=true` đứng một mình. Mutation scheduler/Discord phải đi cùng contract này, không có đường BYPASS riêng cho user thường. A giữ compatibility source Domain cũ, B tạo source Platform mới. [platform_work.py:560](../../vinhome_Recident/services/vinhomes-api/src/vinhomes_api/platform_work.py#L560), [v3_resident.py:527](../../vinhome_Recident/services/vinhomes-api/src/vinhomes_api/v3_resident.py#L527)

## 5. Contract sự kiện: tách job progress và case progress

**Đang có:** `ProviderEventEnvelope` schema_version `1`, external event/job/client reference, type, provider_version, time, data và attachments; yêu cầu job ID hoặc client reference. Domain `event_body()` dựng lại cùng bytes khi retry, worker gửi ordered và theo receipt. [execution contract:29](../../platform_VP/agentscope/src/agentscope/app/workforce/contracts/_execution.py#L29), [platform.py:749](../../vinhome_Recident/services/vinhomes-api/src/vinhomes_api/platform.py#L749), [platform_sync.py:396](../../vinhome_Recident/services/vinhomes-api/src/vinhomes_api/platform_sync.py#L396)

**Không tự mở rộng nghĩa:** case tạo từ resident, staff tạo work thủ công, quote, independent QC, SLA escalation hoặc link revoked có thể chưa có external operation. Không bịa client_reference/external_job để nhét các sự kiện đó vào job protocol. [platform.py:730](../../vinhome_Recident/services/vinhomes-api/src/vinhomes_api/platform.py#L730)

Đề xuất case event envelope mới, producer A và consumer B:

```json
{
  "schema_version": "vin.case-event.v1",
  "event_id": "immutable-domain-event-id",
  "domain_tenant_id": "domain-tenant",
  "binding_id": "validated-platform-case-binding",
  "ticket_id": "canonical-ticket",
  "sequence": 42,
  "ticket_version": 7,
  "event_type": "case.quote_ready",
  "occurred_at": "2026-10-18T02:00:00Z",
  "audience": "customer",
  "data": {"decision_id": "quote-approval", "summary": "safe-projection", "expires_at": "2026-10-18T03:00:00Z"},
  "evidence_refs": [],
  "correlation_id": "same-trace"
}
```

Tên event đề xuất v1: `case.created`, `case.updated`, `case.work_progress`, `case.quote_ready`, `case.decision_recorded`, `case.result_published`, `case.reopened`, `case.closed`, `case.needs_attention`, `link.revoked`. Bảng payload từng event phải có JSON schema, audience whitelist, PII masking và sample hợp lệ/không hợp lệ. Không mặc định `data` tùy ý được gửi vào prompt/customer timeline.

- Events được phát từ outbox cùng transaction business; ordering theo binding/ticket, dedupe bằng issuer/tenant/event ID, không dùng clock phía client làm thứ tự.
- Consumer B kiểm producer/signature/hash/audience/binding/sequence trước ghi; receipt phân biệt `accepted`, `duplicate`, `applied`, `rejected` và cần reason ổn định. `applied` là projection bền vững, chưa phải user đã đọc hoặc đồng ý.
- Snapshot có `last_sequence` và active decisions; gap/cursor-expiry repair trước khi tiếp tục. Có replay cho case không do Platform dispatch; không chỉ dựa job-operation projection.
- Quote/result quyết định được mở khi exact projection đã applied theo rule Domain. Ảnh/citation/download kiểm lại chủ thể và quyền hiện tại; URL không chứa bearer grant.
- Worker A giữ `platform-sync` job progress/receipt/reconcile cho legacy và operation hiện hữu; chỉ tắt nhánh mirror chat Reception theo origin/cohort sau consumer mới đạt. Tách service delivery retry khỏi model/tool run.

Đường projection cũ phía Platform còn enqueue theo manager Scope và share vào room; A đổi authority/projection producer, B đổi runtime room consumer theo explicit customer/operational audience, không chỉ thay user ID trên response. [provider.py:298](../../platform_VP/agentscope/src/agentscope/app/workforce/integrations/unified/_provider.py#L298), [case.py:1119](../../platform_VP/agentscope/src/agentscope/app/workforce/integrations/unified/_case.py#L1119)

## 6. BQL: báo cáo đọc và xử lý ngoại lệ là hai quyền khác nhau

### 6.1. Sáu tool đọc hiện có

| Tool hiện có | Nguồn dữ liệu / giới hạn thực tế |
|---|---|
| `vh_management_ticket_list` | Ticket summary phân trang theo tenant/site/zone/management unit và created-time interval. |
| `vh_management_ticket_summary` | Đếm ticket theo status trong đúng filter đó. |
| `vh_management_sla_report` | Snapshot first-response/resolution deadlines, gồm missing deadlines; không tính lại mọi SLA cycle. |
| `vh_management_workload` | Ticket đang mở theo assigned team; chỉ ticket tạo trong khoảng báo cáo. |
| `vh_management_knowledge_search` | Search tài liệu/chunk trong site/zone, mặc định không lấy unverified. |
| `vh_management_capabilities` | Cho biết management reads, action cần ticket grant, travel mock và unsupported writes/human fallback. |

Tất cả nguồn tại [platform_mcp.py:139](../../vinhome_Recident/services/vinhomes-api/src/vinhomes_api/platform_mcp.py#L139), [platform_management.py:103](../../vinhome_Recident/services/vinhomes-api/src/vinhomes_api/platform_management.py#L103). Báo cáo nhận từ–đến `YYYY-MM-DD`, end exclusive, tối đa 93 ngày, ngày theo UTC+7; không tự đổi nghĩa thành báo cáo all-time. Chỉ có grant đọc không cho đọc chi tiết `vh_ticket_get` hoặc dispatch; có test trực tiếp cho việc này. [test_platform_management.py:16](../../vinhome_Recident/services/vinhomes-api/tests/test_platform_management.py#L16)

### 6.2. Exceptions và action bridge mới

Đề xuất A expose exception queue theo **operator binding/capability**; B render trên workspace nghiệp vụ BQL, tách khỏi personal chats. Exception gồm case/ticket refs, safe reason, SLA, action cần làm, assigned operator/team, expected version và evidence refs tối thiểu. Quyền `can_view_exception`, `can_claim`, `can_propose`, `can_assign`, `can_approve_budget`, `can_qc`, `can_resolve_attention` tách riêng; admin Platform không mặc nhiên được dùng mọi quyền Domain.

Không chuyển management-read grant thành write token. Operator-grant exchange phải kiểm current Platform membership, explicit Domain binding và capability theo action. Domain audit actor là operator thật + service client, không ghi service admin như người nghiệm thu. QC vẫn kiểm reviewer độc lập, job completed và evidence theo rule hiện có; user/resident không thể tự chọn mình làm QC bằng prompt/route. [platform_management.py:75](../../vinhome_Recident/services/vinhomes-api/src/vinhomes_api/platform_management.py#L75), [v3_specialized.py:86](../../vinhome_Recident/services/vinhomes-api/src/vinhomes_api/v3_specialized.py#L86)

Báo cáo không đồng nghĩa cấp quyền chat/file cá nhân. Hỗ trợ cần xem thêm đoạn chat phải có policy/consent/phạm vi/thời hạn/audit; mặc định BQL xem case projection và task, không thấy raw prompt, private KB, Shared Context cá nhân hoặc model reasoning.

## 7. Test source có thể dùng làm điểm bắt đầu

Các file sau **đang tồn tại**; tên test minh họa hành vi source, không phải kết quả chạy trong đợt nghiên cứu này.

| Nhóm | Test hiện có | Bổ sung hai người cần làm |
|---|---|---|
| Link/delegation | [test_integration_auth.py:58](../../vinhome_Recident/services/vinhomes-api/tests/test_integration_auth.py#L58), [:122](../../vinhome_Recident/services/vinhomes-api/tests/test_integration_auth.py#L122), [:145](../../vinhome_Recident/services/vinhomes-api/tests/test_integration_auth.py#L145) | A authorization-code/PKCE, link collision/revoke, current entitlements; B callback/session/link UI và source proof actor. |
| Self/private request | [test_resident_contract.py:162](../../vinhome_Recident/services/vinhomes-api/tests/test_resident_contract.py#L162), [:209](../../vinhome_Recident/services/vinhomes-api/tests/test_resident_contract.py#L209), [:279](../../vinhome_Recident/services/vinhomes-api/tests/test_resident_contract.py#L279) | A pre-ticket self, prepare/create no Domain-chat fake identity; B đúng personal owner và customer audience. |
| Grant/source proof | [test_platform_mcp_v2.py:58](../../vinhome_Recident/services/vinhomes-api/tests/test_platform_mcp_v2.py#L58), [:79](../../vinhome_Recident/services/vinhomes-api/tests/test_platform_mcp_v2.py#L79), [:104](../../vinhome_Recident/services/vinhomes-api/tests/test_platform_mcp_v2.py#L104), [:160](../../vinhome_Recident/services/vinhomes-api/tests/test_platform_mcp_v2.py#L160); [test_ticket_mcp_grants.py:20](../../platform_VP/agentscope/tests/workforce/integrations/test_ticket_mcp_grants.py#L20) | A Platform-origin grant without Domain start command, wrong subject/tools/env/revision; B exchange/revoke and never shared-client mutation. |
| Duplicate workflow/retry | [test_platform_bridge.py:449](../../vinhome_Recident/services/vinhomes-api/tests/test_platform_bridge.py#L449), [:537](../../vinhome_Recident/services/vinhomes-api/tests/test_platform_bridge.py#L537), [:999](../../vinhome_Recident/services/vinhomes-api/tests/test_platform_bridge.py#L999), [:1105](../../vinhome_Recident/services/vinhomes-api/tests/test_platform_bridge.py#L1105) | Platform-origin retry/response loss → một canonical ticket, một original workflow, không start command thứ hai; legacy test vẫn đúng. |
| Publication/decisions | [test_platform_bridge.py:818](../../vinhome_Recident/services/vinhomes-api/tests/test_platform_bridge.py#L818), [:833](../../vinhome_Recident/services/vinhomes-api/tests/test_platform_bridge.py#L833), [:849](../../vinhome_Recident/services/vinhomes-api/tests/test_platform_bridge.py#L849) | Quote/result projection đúng event/job, accepted chưa mở card, stale consent version, replay/double click; negative case event của người khác. |
| Events/workers | [test_platform_bridge.py:1260](../../vinhome_Recident/services/vinhomes-api/tests/test_platform_bridge.py#L1260), [:1365](../../vinhome_Recident/services/vinhomes-api/tests/test_platform_bridge.py#L1365), [:1402](../../vinhome_Recident/services/vinhomes-api/tests/test_platform_bridge.py#L1402) | A manual staff work/case events, outbox ordering/replay; B dedupe/gap recovery/customer projection và reconciliation khi owner mất quyền. |
| Staff còn hoạt động | [test_staff_dispatch.py:89](../../vinhome_Recident/services/vinhomes-api/tests/test_staff_dispatch.py#L89), [:104](../../vinhome_Recident/services/vinhomes-api/tests/test_staff_dispatch.py#L104), [test_staff_notifications.py:16](../../vinhome_Recident/services/vinhomes-api/tests/test_staff_notifications.py#L16), [test_platform_tools.py:280](../../vinhome_Recident/services/vinhomes-api/tests/test_platform_tools.py#L280), [:481](../../vinhome_Recident/services/vinhomes-api/tests/test_platform_tools.py#L481) | A giữ dispatch/staff assignments/progress/QC, B end-to-end receive; không tắt staff app khi tắt chatbot. |
| BQL read/zone/action separation | [test_platform_management.py:16](../../vinhome_Recident/services/vinhomes-api/tests/test_platform_management.py#L16), [:49](../../vinhome_Recident/services/vinhomes-api/tests/test_platform_management.py#L49), [management_mcp_test.py:13](../../platform_VP/agentscope/tests/management_mcp_test.py#L13) | A operator action grants và area/membership revoke; B workspace switch, summaries scope, exception queue/private chat separation. |
| Emergency | [test_platform_bridge.py:572](../../vinhome_Recident/services/vinhomes-api/tests/test_platform_bridge.py#L572), [test_platform_mcp_v2.py:205](../../vinhome_Recident/services/vinhomes-api/tests/test_platform_mcp_v2.py#L205), [test_platform_tools.py:626](../../vinhome_Recident/services/vinhomes-api/tests/test_platform_tools.py#L626) | A/B đường emergency không cần model/quota, trước-ticket và model/Domain unavailable có hotline/handoff cấu hình; giữ cấm guard dispatch không được phép. |

Domain integration fixtures yêu cầu PostgreSQL local disposable với runtime role không superuser/BYPASSRLS; thiếu URL thì test skip, không được báo pass. [test_resident_contract.py:1](../../vinhome_Recident/services/vinhomes-api/tests/test_resident_contract.py#L1), [test_resident_contract.py:54](../../vinhome_Recident/services/vinhomes-api/tests/test_resident_contract.py#L54)

Nhóm UI Domain đã có `vinhome_Recident/apps/staff-web/tests/connected-operations-ui.test.tsx`, `operations-field-work.test.tsx`, `operations-auth.test.ts`, `resident-connected-ui.test.tsx`, `platform-connection.test.tsx`; A giữ regression của các bề mặt còn chạy, chỉ retire customer chatbot intake theo cohort sau E2E. Đây là danh mục file hiện có, không phải xác nhận các test đã chạy ở turn này.

## 8. Fileowner đề xuất để hai người không sửa chồng

Đây là fileowner dùng cho hai phần A=nền tảng/authority + Domain và B=runtime/trải nghiệm + triển khai Platform. Tài liệu không tự sửa CODEOWNERS; hai người ghi allowlist PR và ngoại lệ bằng review.

| Khu vực/file | Một fileowner | Interface người còn lại dùng |
|---|---|---|
| `vinhome_Recident/**` gồm services, agents Reception, apps resident/staff, deploy, schema/migrations/tests | A | B chỉ consumer HTTP/MCP/events + fixtures đã công bố; không sửa Domain DB/seed để làm test xanh. |
| Domain/Platform contract schemas, OpenAPI, event samples và compatibility suite producer | A | B consumer validation/test fixture; version/hash pin trong adapter. |
| Platform `auth/**`, `access/**`, catalog, shared `workforce/contracts/**` và `workforce/foundation/**` | A | B gọi principal/capability/entitlement resolver; không duplicate policy trong UI/runtime. |
| Toàn bộ Platform `storage/**`, không chỉ SQL; tất cả adapter/model serialization và alembic | A | B gửi schema/persistence delta; A cung cấp storage methods và migration compatibility. |
| Mọi migration SQL của hai lane | A author/merge owner | B gửi nhu cầu schema; A kiểm revisions và cấp storage API. Không để hai nhánh tự lấy cùng migration number. |
| Platform quota/catalog/credential/Knowledge authority, central `_service/_model` và model adapters | A | B model/agent/runtime consume resolver/gate; tên interface đóng băng từ contract kickoff. |
| Platform `_app`, `_lifespan`, dependencies, app/router registration và entrypoint | A | B gửi mount/dependency delta cho A; không cùng sửa bootstrap. |
| `workforce/integrations/unified/_composition.py`, `_grants.py`, `_partner_setup.py`, `_tables.py` | A | B dùng shared grant exchange/composition interface đã chốt, không fork quyền riêng trong runtime. |
| Backend customer/manager authority và projections mới; manager grant resolver | A | B gửi view/runtime needs, consume DTO/projection/gate; A kiểm scope và persistence. |
| `_service/_chat.py`; chat/session/agent/workspace routers; console/studio/readiness/publish/eval | B | A cung cấp helper/middleware signature và contract test, tránh cùng sửa file lớn. |
| Personal/team/memory; runtime toolkit integration | B | A cung cấp access/model/storage contracts; B partition đúng principal/environment và tích hợp mọi đường call. |
| Unified `_case.py`, `_runner.py`, `_readiness.py`, `_quality.py`, `_recovery.py`, `_close.py`, `_approvals.py` | B | A sở hữu schema/authority/projection producer; B tách actor/owner/billing/audience trong runtime. |
| Channel/scheduler runtime và deploy Platform | B | A cung cấp quota/access/link/grant APIs và app registration; B gửi schema/mount delta cho A. |
| `platform_VP/agentscope/examples/web_ui/frontend/**` | B | B dùng Platform DTO an toàn, không gọi Domain owner DB/control secret từ browser. |
| Domain schemas/migrations vs Platform UI generated client | A schema, B generated client | Update schema fixture trước; generated code không sửa tay tạo contract khác. |
| File chung ngoài allowlist như CI root/workspace lock cần cả hai lane | Chốt một fileowner trước khi sửa | B và A gửi delta cho fileowner; không reformat/reinstall toàn monorepo làm tăng conflict. |

Các file chưa có trong allowlist cần chốt một owner trước khi sửa. Đặc biệt provider ingress/projection thuộc authority A khi thay customer/manager projection; runtime append/share trong `_case.py` thuộc B. Hai người thống nhất interface và contract test, không sửa chéo để vượt một gate đang thiếu.

## 9. Trình tự song song và gói bàn giao

| Mốc | A giao gì | B triển khai đồng thời | Gate tích hợp |
|---|---|---|---|
| C0 — contract kickoff | Execution/link/case/intent/grant/event v1; source facts vs proposals; DTO/errors/samples; fileowner | Adapter stub/generated client, views theo capability, tests consumer | Schema compile/negative examples; producer/consumer agree semantics, không cần Domain thật đã deploy. |
| C1 — identity + gates | Link issuer/revoke, pre-ticket grants, nền tảng authority/quota nếu thuộc lane A | Onboarding/link UI, runtime user context, personal agent/KB/eval/lịch/kênh theo interfaces | Không có resident thành BQL; service owner không được dùng làm acting subject. |
| C2 — intake vertical slice | Prepare/create/binding + Platform-origin grant transaction | Customer Leader/service-case adapter/timeline/source intent | Một link thật/sandbox → một ticket → same workflow; retry/mất response không trùng. |
| C3 — việc thật + projection | Staff/dispatch/QC retained, job/case events, pending decisions, applied-ack gate | Event consumer, customer decision UI, BQL summary/exception workspace | Manual work và Platform work đều hiện đúng; quote/completion và người thật xác nhận đúng nguồn. |
| C4 — rollout | Migration origin/legacy compatibility, reconcile, backfill/quarantine, Domain cutover flags | User migration/help, capability flags, UI rollback và monitoring | Ticket cũ/pending decision tiếp tục; emergency không mất; hai lane ký E2E trước tắt chatbot cohort. |

Gói A tối thiểu: OpenAPI/schema + JSON samples + error catalog; fixture factory/reset sandbox; migrations/rollback-safe expand plan; service endpoints và health/version manifest; contract tests; Domain/staff operational runbook. Gói B: consumer version lock + adapters, safe UI flows, model/identity/quota integration, projection/replay tests, browser-role evidence, service/worker ownership và release flags.

Mỗi lần thay contract: A tăng version hoặc sửa theo backward-compatible rule đã chốt; B có compatibility test và mốc migrate. Contract đang dùng không được đổi nghĩa âm thầm. Sandbox có fake provider được ghi rõ; chưa có official OAuth/booking thật thì không gọi là tích hợp Vin chính thức đã nghiệm thu.

## 10. Những lỗi handoff phải tránh

1. Coi starter template hoặc agent tên Vinhomes là official service đã có quyền.
2. Đưa cư dân vào manager-owned group để tận dụng UI cũ, hoặc thay `manager_account_id` bằng customer ID cho qua kiểm tra.
3. Tạo ticket Platform-origin nhưng vẫn auto-start workflow legacy hoặc fake Domain-start command để lấy grant.
4. Bỏ `source_message_id` gate mà không thay bằng signed SourceIntent đã xác minh.
5. Chỉ giữ provider job events rồi bỏ sót manual staff work/intake/consent/exception chưa có operation reference.
6. Cho BQL read grant làm QC/dispatch/approval, hoặc coi admin Platform có quyền toàn dữ liệu Domain.
7. Tắt `platform-sync`, staff app hoặc emergency Reception branch cùng lúc ẩn chatbot mà chưa có consumer thay thế.
8. Hai người cùng sửa migration/contracts hoặc các runtime file lớn; consumer mock được trình bày như route producer đã có.
9. Đồng nhất accepted/applied/user-read/resident-accepted/completed; các trạng thái này có chứng cứ khác nhau.
10. Báo test pass khi PostgreSQL fixture đã skip, hoặc coi health/discovery/offline test thay pilot nghiệp vụ thật.
