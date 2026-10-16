# Đối chiếu contract Workforce v1 với platform core

Ngày nghiên cứu: 10/10/2026. Phạm vi: lập kế hoạch, không triển khai API hay sửa nghiệp vụ. Snapshot Git: nhánh `feat/platform-core`, HEAD `7f3e56e5bbf14b8a534fff5a949def3ec2ac12fb`. Ba file đã có thay đổi trước nghiên cứu: `docs/PLATFORM_CORE_KE_HOACH.md`, `platform_VP/core/.env.example`, `platform_VP/core/README.md`; nghiên cứu không thay đổi các file này.

## 1. Nguồn và mức độ kiểm chứng

- Nguồn yêu cầu: [CONTRACT_TICH_HOP_DOI_TAC.md](C:/Users/Lenovo/Downloads/CONTRACT_TICH_HOP_DOI_TAC.md), bản `1.3-draft`, cập nhật 10/10/2026. Chính tài liệu ghi đây là đặc tả mục tiêu, không xác nhận API đã triển khai (dòng 5).
- Nguồn triển khai hiện tại: gói `awp` ở `platform_VP/core`; kế hoạch hiện có [PLATFORM_CORE_KE_HOACH.md](../PLATFORM_CORE_KE_HOACH.md).
- Đã đọc contract toàn bộ và đối chiếu source/tests. Không gọi model trả phí, không chạy dịch vụ hay test trong lượt nghiên cứu này. Mọi nhận định “có test” bên dưới nghĩa là đọc được test trong mã, không phải báo cáo test vừa chạy.
- Contract là dữ liệu đặc tả được người dùng yêu cầu phân tích. Những câu mang tính chỉ dẫn vận hành trong tài liệu không tự cho phép cấp credential, sửa quyền, chạy giao dịch hoặc thay đổi hệ thống.

## 2. Kết luận quan trọng nhất

Contract mới đảo hướng giao tiếp so với kế hoạch cũ: **Vinhomes gọi API do platform cung cấp; platform không gửi outbound webhook và không yêu cầu Vinhomes xây REST callback.** Platform gọi MCP nghiệp vụ đã onboarding khi agent cần dữ liệu hoặc thực hiện thao tác. Với operation bất đồng bộ, backend nghiệp vụ gọi Provider Event API của platform, hoặc platform truy vấn trạng thái qua MCP nếu đã thống nhất capability. Nguồn: contract §1, §2, §3, §10.

Vì vậy không thể giữ mục “Reception nhận callback/webhook” của kế hoạch cũ làm hướng triển khai đích. [Kế hoạch cũ §3–6](../PLATFORM_CORE_KE_HOACH.md:25) mô tả webhook, `/platform/v1/intake`, domain pack, cấu hình HTTP tool; các phần đó phải được đối chiếu lại. Đặc tả mới chưa tự triển khai những API nó mô tả.

Reception vẫn là agent chat trong Vinhomes. Backend Vinhomes xác thực cư dân, giữ mapping theo từng hộp chat/ticket và gọi platform thay mặt người dùng. Platform tự chọn supervisor theo route đã xác nhận, rồi supervisor quyết định có cần chuyên viên và mời ai. Cư dân/Reception không truyền agent/group/manager nội bộ qua Customer API (contract §9.1–9.2).

## 3. Nền hiện có thực sự là gì

### 3.1 Có thể kế thừa

1. Hồ sơ agent có mission, handles/refuses, instructions, tool allowlist, specialist team, knowledge, memory và model tier; có draft/publish/retire theo tenant/key/version. Nguồn: [profiles/models.py](../../platform_VP/core/src/awp/profiles/models.py:15), [profiles/store.py](../../platform_VP/core/src/awp/profiles/store.py:28).
2. Leader hiện **đã tự quyết định gọi chuyên viên**, bằng `TeamCreate`, `AgentCreate`, `AgentInvite`, `TeamSay`. Đây không còn là fixed-team pipeline của worktree `dev_platform` cũ. Nguồn: [profiles/compile.py](../../platform_VP/core/src/awp/profiles/compile.py:10), [leader_prompt](../../platform_VP/core/src/awp/profiles/compile.py:94).
3. Case file lưu evidence/fact/question/answer/challenge/decision/report; session binding phân leader/worker; ref uniqueness có retry khi nhiều writer cùng chọn số. Nguồn: [db.py](../../platform_VP/core/src/awp/db.py:20), [casefile/store.py](../../platform_VP/core/src/awp/casefile/store.py:129).
4. Giao thức trao đổi agent có `CaseAsk`, `CaseAnswer`, `CaseChallenge`, `CaseDecide`, `CaseRead`, `CaseGap`; chỉ leader quyết định và finalize. Nguồn: [protocol/tools.py](../../platform_VP/core/src/awp/protocol/tools.py:183).
5. Digest theo cursor từng session, nêu thành viên, câu hỏi/challenge còn chờ và phần mới; không nhét raw evidence của người khác vào digest, có `CaseRead` để xem thêm. Nguồn: [casefile/digest.py](../../platform_VP/core/src/awp/casefile/digest.py:62), [middleware/room.py](../../platform_VP/core/src/awp/middleware/room.py:100).
6. Guard kiểm con số/mã dựa trên evidence được dẫn, phrase rule theo domain, phân lời người yêu cầu và dữ liệu từ hệ thống; Jev tùy chọn. Nó không chứng minh mọi câu văn đều đúng, không thay thế schema/state/permission. Nguồn: [guard/checks.py](../../platform_VP/core/src/awp/guard/checks.py:77), [protocol/tools.py](../../platform_VP/core/src/awp/protocol/tools.py:368).
7. Multi-model catalog, tier routing, usage ledger và cost theo case/agent/model đã có; lọc schema tool theo vai. Nguồn: [providers.py](../../platform_VP/core/src/awp/providers.py:83), [cost.py](../../platform_VP/core/src/awp/cost.py:17), [middleware/room.py](../../platform_VP/core/src/awp/middleware/room.py:227).
8. AgentScope service được dựng và gắn middleware/tool qua điểm mở rộng, không sửa vendor SDK. Nguồn: [app.py](../../platform_VP/core/src/awp/app.py:35).

### 3.2 Có mã nhưng chưa đủ cho contract mới

- Public router hiện chỉ `/platform/v1`; intake và follow-up đều khai báo HTTP 202, trả case/status, không phải command representation Workforce v1. Nguồn: [router.py](../../platform_VP/core/src/awp/router.py:17), [router.py](../../platform_VP/core/src/awp/router.py:49).
- Security hiện parse Bearer từ cấu hình process, principal gồm tenant/domain/admin. Chưa có ApiKey partner/provider, operation grants, management-route confirmation, expiry/revocation store hoặc audience theo cư dân. Kiểm ownership case chỉ tenant/domain. Nguồn: [security.py](../../platform_VP/core/src/awp/security.py:21), [security.py](../../platform_VP/core/src/awp/security.py:44), [router.py](../../platform_VP/core/src/awp/router.py:35).
- `CaseIntake` hiện cho bên gửi chọn `leader_profile`, `callback_url`, `confirm_with`, budget; default leader là dict domain→key trong process. Các field này không được phép đưa nguyên sang Customer API mới. Nguồn: [intake/models.py](../../platform_VP/core/src/awp/intake/models.py:17), [intake/service.py](../../platform_VP/core/src/awp/intake/service.py:78).
- Default leader đang được đăng ký qua `DomainPack`; contract mới cần onboarding route→manager/workspace và policy đã publish, không bắt buộc code domain bên trong core. Nguồn: [packs.py](../../platform_VP/core/src/awp/packs.py:1), [app.py](../../platform_VP/core/src/awp/app.py:112).
- Dedupe hiện theo tenant/domain/message_id hoặc external_ref, không lưu canonical payload hash, command/resource và audience tuple. `submit` gặp external_ref cũ trả replay, chưa phát hiện cùng ID khác body như contract yêu cầu. Nguồn: [intake/service.py](../../platform_VP/core/src/awp/intake/service.py:91), [casefile/store.py](../../platform_VP/core/src/awp/casefile/store.py:207).
- `CaseFinalize` đóng case ngay sau kết luận; `confirm_with` là request kind tự khai báo, không phải approval/close API có CAS, hash/quote, audience và persisted result. Nguồn: [protocol/tools.py](../../platform_VP/core/src/awp/protocol/tools.py:368), [intake/service.py](../../platform_VP/core/src/awp/intake/service.py:202).
- Có durable outbox cho callback/request nhưng delivery quét pending không có lease/claim; callback dùng HMAC raw body khác Provider Event signature mới có timestamp/key-id. Nó không phải public replay log. Nguồn: [db.py](../../platform_VP/core/src/awp/db.py:125), [intake/service.py](../../platform_VP/core/src/awp/intake/service.py:219).
- RAG middleware gắn KB và long-term AgenticMemory middleware có mã. Tuy nhiên memory folder là `memory/{tenant}/{profile.key}`, dùng chung qua nhiều case; field `scope` chưa tham gia chọn folder. Không đủ bảo đảm audience isolation nếu agent ghi dữ liệu cư dân. Nguồn: [middleware/__init__.py](../../platform_VP/core/src/awp/middleware/__init__.py:39), [middleware/__init__.py](../../platform_VP/core/src/awp/middleware/__init__.py:57).
- Registry specialist đọc mọi tenant nhưng keyed chỉ bằng `profile.key`; tenant sau có thể ghi đè template cùng key của tenant trước. Phiên đang chạy cũng chưa có manifest pin toàn bộ profile/tool/policy/model/integration. Nguồn: [runtime.py](../../platform_VP/core/src/awp/runtime.py:135), [profiles/store.py](../../platform_VP/core/src/awp/profiles/store.py:103).
- Usage budget mới kiểm sau model call, trạng thái wrap-up nằm trong set process. Cần reservation/admission theo DB để tránh nhiều agent gọi đồng thời vượt ngân sách và mất giới hạn khi restart. Nguồn: [runtime.py](../../platform_VP/core/src/awp/runtime.py:51), [middleware/room.py](../../platform_VP/core/src/awp/middleware/room.py:264).

## 4. Ma trận gap theo API và hành vi

| Contract mục tiêu | Hiện tại | Phần cần làm |
|---|---|---|
| §5–6 credential ApiKey, purpose, grants, limits | Bearer tenant/domain; errors dạng detail | Credential store, secret verification, revoke/rotate/expiry, public error envelope, rate/payload limits |
| §8.1 POST route confirm | Chưa có route aggregate | Pending→active CAS, đúng partner, external ref unique trong namespace, pin manager/workspace |
| §8.2 PUT residence | Chưa có | Residence membership mapping có revision, active route validation; không chuyển workflow cũ khi remap |
| §9.1–9.2 POST requests | Intake/follow-up legacy | Strict schema, start/reply binding, persisted request+workflow+job, canonical idempotency; 200 hoặc deadline202 |
| §9.3 GET request | GET case legacy | Per-command result/error/message ID; request_status tách workflow_state; tính next_action |
| §9.4 snapshot | Chưa có public conversation | Snapshot nhất quán state/messages/approvals/cursor đúng audience |
| §9.5 event history | Case items chỉ admin | Public safe projection, sequence theo conversation, cursor auth/expiry410, retention |
| §9.6 SSE | AgentScope chat stream không phải public workflow replay | DB replay→live, same event/message IDs, heartbeat không LLM, revalidate revoked grant≤60s |
| §9.8 approval decision | confirm_with/request kind | Approval tied workflow/run/call/audience, args hash/quote/expiry/CAS, common request namespace |
| §9.9 close | Leader CaseFinalize đóng | Explicit close command, idempotency trước CAS, atomically close+event, stop-tracking≠cancel operation |
| §10 provider job-events/receipts | Không có | Raw-body signature, provider grants, durable inbox+job, dedupe/hash, receipts, correlation/quarantine/reconcile |
| §10.3 operation ordering | Không có external operation aggregate | Per-integration schema/transition/version; gap handling, no regression, late event không reopen |
| §12 retention/isolation | Có durable case file, chưa public audience model | Protected retention/purge policy và per-client/route/user/ticket/conversation filtering |

Nguồn cho “chưa có”: toàn bộ [router.py](../../platform_VP/core/src/awp/router.py:17) và [DB schema hiện tại](../../platform_VP/core/src/awp/db.py:20) không chứa các aggregate/API tương ứng. Các tính năng chung của AgentScope không mặc nhiên đáp ứng contract Workforce v1.

## 5. Durable runtime và 20 session

Hiện `app.py` mặc định `InMemoryMessageBus`, local workspaces và SQLite; `IntakeService._spawn` dùng `asyncio.create_task`. Case file được lưu nhưng điều đó không bảo đảm một command đã tiếp nhận sẽ được xử lý lại an toàn sau crash. Nguồn: [app.py](../../platform_VP/core/src/awp/app.py:51), [intake/service.py](../../platform_VP/core/src/awp/intake/service.py:290), [config.py](../../platform_VP/core/src/awp/config.py:21).

Hướng đề xuất: PostgreSQL cho control state, migration có phiên bản, durable job có claim/lease/fencing, mỗi workflow chỉ một lượt mutate hợp lệ tại một thời điểm. DB giữ checkpoint, public events, operation intent và dedupe. Redis chỉ đánh thức worker/SSE, không làm nguồn replay. Checkpoint phải ghi pin của profile, policy, tool manifest và operation đang chờ. Khi chờ người dùng hoặc external event, giải phóng lượt model/worker/transaction.

POST chỉ chờ persisted result đến deadline; hết hạn trả 202 nhưng job tiếp tục, không cancel job theo HTTP disconnect. Trước side effect: ghi intent và `client_reference`, args hash, authorization/approval; provider nhận idempotency key. Nếu timeout sau khi gửi mà chưa rõ tool có tác động hay chưa, dùng lookup/reconcile, không tạo công việc lần hai.

Đây là yêu cầu thiết kế bổ sung suy ra từ contract §3, §9.1, §9.6, §10, §11, không phải mã đã có.

## 6. Ranh giới nối Vinhomes

Luồng đích:

```text
Cư dân ↔ Reception agent/backend Vinhomes
                  │ Customer API: request/reply/approval/close; GET/SSE/history
                  ▼
          Platform Workforce API → route → leader → specialists
                  │ MCP tool đã onboarding
                  ▼
          Backend nghiệp vụ Vinhomes → nhân viên thực tế
                  │ Provider Event API khi operation pending
                  └──────────────────────► Platform
```

Platform không điều động bằng câu chat hay gọi REST tùy ý. Chỉ được nói “đã giao thợ/đã chuyển lời” khi tool đã xác nhận và có operation/evidence. Quyền điều động thực tế, bước BQL duyệt và cư dân đồng ý phải do capability/policy nghiệp vụ đã onboarding quyết định; contract API mới không tự cấp quyền đó.

Legacy Vinhomes hiện cung cấp `/integration/v1/cases/inbox`, `/cases/{ticket_id}/results`, `/plans`, `/events` theo hướng platform làm client của domain. Nguồn: [HOP_DONG_TICH_HOP §5–6](../../vinhome_Recident/docs/domain/HOP_DONG_TICH_HOP.md:147), [integration_cases.py](../../vinhome_Recident/services/vinhomes-api/src/vinhomes_api/integration_cases.py:31). Đây không phải Customer API/Provider API mới. Nếu tái sử dụng nghiệp vụ bên trong để xây MCP thì domain adapter phải giữ authorization, delegation, idempotency và human gates; không tiếp tục poll inbox cũ làm giao diện hợp đồng mới.

Tìm các dấu hiệu triển khai `FastMCP`, `mcp.server`, `streamable_http`, `/mcp`, `mcp_server` trong `vinhome_Recident/services/vinhomes-api/src` và `vinhome_Recident/agents/reception/src` không có kết quả. Đây là kết quả tìm trong hai phạm vi source này, không phải bằng chứng tuyệt đối rằng không có MCP ở nơi khác hoặc môi trường ngoài repo. REST tool catalog có sẵn không tự trở thành MCP server chạy được.

Bên Vinhomes cần client server-side cho Workforce API, mapping record theo từng external ticket/chat, chuẩn hóa công cụ MCP, và provider outbox nếu triển khai external tracking. Reception tiếp tục trò chuyện ở Vinhomes; kết quả POST/SSE/history được đưa về đúng hộp chat, dedupe message_id. Nhân viên vẫn dùng app/backend nghiệp vụ; không giữ key platform.

Đề xuất mapping lưu `(partner_client, external_user_id, external_ticket_id, external_conversation_id)` → `workflow_id, conversation_id, ticket_id(nullable), revision, cursor`. Không lưu “workflow gần nhất của user”. Platform ticket ID không thay ID ticket Vinhomes.

## 7. Thứ tự triển khai có điểm nghiệm thu

1. **Chốt contract và quyền:** route→manager/workspace/default leader, credential purposes, ticketed binding, consent/dispatch scope. Nghiệm thu bằng schema/OpenAPI và negative cases, không model.
2. **Control plane + durable persistence:** client/credential/grants/route/residence/request/conversation/workflow/job/event/operation/approval/receipt; migration và invariants. Nghiệm thu concurrent create/idempotency/CAS/revoke/remap và crash recovery.
3. **Customer API end-to-end tối thiểu:** POST start/reply, GET request/snapshot, strict tuple binding, deadline200/202, common command dedupe; bridge vào leader orchestration đã có. Nghiệm thu một read-only và một interactive workflow bằng scripted model.
4. **Event read model:** history/SSE replay/live/cursor410/auth, safe public projection. Nghiệm thu event trước firstSSE, reconnect, same message qua POST/SSE, hai chat cùng user, revoked stream.
5. **MCP + approvals + operations:** tool discovery/allowlist/version pin/intent/idempotency, approval endpoint, sync confirmed vs async pending, unknown-outcome reconcile. Nghiệm thu không có side effect trước consent, không duplicate call sau restart/timeout.
6. **Provider Event API + close:** signature, inbox/receipt/version/quarantine, transition validator, explicit close/CAS/race. Nghiệm thu early callback, late/out-of-order events, close-vs-reply-vs-event và stop tracking không hủy nghiệp vụ.
7. **Hoàn thiện agent isolation/cost/admin:** registry tenant-safe, memory audience-safe, digest + task ownership, budgets reserved across workers, UI vận hành/pin/attention/recovery. Nghiệm thu 20 workflow đồng thời trên PostgreSQL + bus đa process.
8. **Nối domain:** Vinhomes client + MCP + provider outbox/cư dân UI; sandbox kiểm tra cư dân→Reception→leader→MCP→nhân viên→event→Reception→close. Chỉ đo model thật và bật production sau evidence riêng.

Nên kiểm sửa registry/memory trước test nhiều tenant, và triển khai durable queue trước nhận traffic thật. Có thể chia bước 2–6 thành vertical slices nhưng không gọi intake legacy là Workforce v1 chỉ bằng đổi prefix.

Phân vùng thay đổi dự kiến:

| Package | Trách nhiệm được đề xuất |
|---|---|
| `platform_VP/core/src/awp` | Workforce API, auth/control plane, workflow runtime, durable jobs/events, approvals/operations, MCP client/gates, hồ sơ/knowledge/memory/cost |
| `platform_VP/core/tests` | Contract tests, scripted-model orchestration, race/crash/replay/isolation và tải sandbox |
| `vinhome_Recident/agents/reception/src` | Chuyển yêu cầu/reply từ agent Reception sang Workforce client, tiếp nhận kết quả đúng hội thoại; không thay bằng agent chat platform |
| `vinhome_Recident/services/vinhomes-api/src/vinhomes_api` | Client server-side/mapping, MCP nghiệp vụ hoặc entrypoint riêng của domain, provider outbox và schema event; giữ luật phân quyền/phân công/duyệt |
| `vinhome_Recident/apps` | Hiển thị next_action, trạng thái, approval/confirm; dedupe bubble và theo dõi đúng hộp chat nếu backend/UI cần thay đổi |
| `platform_VP/agentscope/src` | Giữ nguyên vendor; ưu tiên extension hooks có sẵn, chỉ đề xuất sửa nếu tìm thấy giới hạn cụ thể không giải quyết được bằng wrapper |

Request command là một lần tiếp nhận, workflow là vòng xử lý dài hạn, external operation là việc tại hệ thống nghiệp vụ. Ba aggregate và trạng thái này phải tách. Close workflow dừng vòng theo dõi, không tự đóng ticket nghiệp vụ, nghiệm thu, hủy thợ hoặc thanh toán ở Vinhomes.

## 8. Những điểm cần xác nhận hoặc phụ lục trước triển khai

### Quyết định của chủ dự án

1. Có lấy contract `1.3-draft` làm đích duy nhất và bỏ outbound webhook/poll inbox cũ khỏi luồng tích hợp mới không? Khuyến nghị có; giữ legacy riêng chỉ khi cần migration rõ.
2. Đợt triển khai cho phép sửa cả backend/Reception Vinhomes để tạo client/MCP/provider outbox, hay chỉ hoàn thiện platform + sandbox giả rồi bàn giao domain? Contract mới đòi phần việc ở cả hai bên nhưng không tự cấp quyền sửa domain.
3. Thợ được điều động tự động trong trường hợp nào, bước nào cần BQL/cư dân phê duyệt? Cần danh sách capability cụ thể; không suy quyền từ ví dụ plumbing.
4. V1 cần ảnh/tệp ngay hay chỉ text theo contract? Ảnh/file chưa có upload contract; nếu cần phải bổ sung asset scope/auth/size/retention, không tự tải URL trong message.
5. Mặc định long-term memory được giữ loại dữ liệu nào qua workflow? Khuyến nghị chỉ tri thức được kiểm duyệt hoặc memory có audience scope; session evidence riêng không trở thành shared specialist memory.

### Chỗ contract cần làm rõ bằng schema/quy tắc, phần lớn là quyết định kỹ thuật

- §9.8 `expected_revision` là revision của approval hay workflow? Ví dụ không nói rõ; cần chỉ định và có GET/snapshot hiển thị đúng revision, arguments_hash, quote_ref, expiry để client gửi decision.
- §8.2 initial `expected_revision` khi tạo residence chưa mô tả; residence ID có thể có nhiều cư dân và cùng nhãn căn hộ ở hai route. Cần namespace/ownership model và quy tắc compare-and-swap idempotent khi body lặp.
- §9.9 close response dùng `state/revision`, trong khi §3 nói response luôn có `workflow_state/next_action`; approval response §9.8 không có workflow_state/next_action. Cần chốt envelope/chỗ ngoại lệ trước freeze OpenAPI.
- §9.3 có blocked_authorization/blocked_route_changed nhưng mapping next_action chưa đầy đủ; closed→none phải phân biệt pending close representation. Cần state/action matrix toàn bộ.
- §9.4 nói snapshot có pending approvals nhưng JSON ví dụ chưa có; snapshot pagination của message cũng chưa chốt. Không suy từ ví dụ thiếu field rằng approval không cần trả.
- MCP nằm ngoài public API contract nhưng vận hành bắt buộc có protocol onboarding: transport/auth, read/write classification, JSON schema, authorization/consent, args hash/idempotency key/client_reference, sync terminal vs pending, status lookup, error/unknown outcome/cancel. API public đủ không có nghĩa đã có protocol dùng tool an toàn.
- Provider event ordering cần chốt event là full snapshot hay delta, version gap xử lý, correction/reopen, một workflow nhiều external jobs, quarantine TTL/retry/DLQ. §10 quy định nguyên tắc nhưng chưa có schema onboarding cụ thể.
- API hủy việc nghiệp vụ không có endpoint riêng ở contract; close không hủy job. Cần phân biệt user chat yêu cầu hủy → tool có quyền/approval với đóng vòng theo dõi. Không tự thêm public cancel API.
- Manager verification/admin route creation, grants remap/revocation UX và cấu hình policy mặc định không nằm trong partner API; cần thiết kế control plane nội bộ, không đưa internal IDs vào partner requests.
- POST wait 25s, rate limits, retention exception và môi trường thực cần điền onboarding §15; kỹ thuật có thể giữ default đã nêu để sandbox, không cần hỏi lại mọi con số.

## 9. Test có trong mã và phần chưa chứng minh

[test_e2e.py](../../platform_VP/core/tests/test_e2e.py:1) ghi rõ real AgentScope service nhưng scripted model. [support.py](../../platform_VP/core/tests/support.py:50) dùng DemoPack, tools local read-only, delivery vào list; không chạy Vinhomes thật. Test room kiểm peer question/answer, grounding refusal, reports, cost, tool pruning, profile publish, model tier, budget, watchdog và callback signature. [test_requests.py](../../platform_VP/core/tests/test_requests.py:131) mô phỏng field staff qua `pack.requests` và structured reply; không chứng minh app nhân viên thật được giao việc. [Memory test](../../platform_VP/core/tests/test_e2e.py:185) xác nhận profile mới chạy và folder tồn tại, không kiểm cross-audience leakage hay retrieval quality.

Không có test Workforce v1 trong router/schema hiện tại vì API mới chưa triển khai. Không có bằng chứng từ lượt nghiên cứu này về PostgreSQL đa worker, Redis replay, 20 session, MCP domain thật, model thật, chất lượng tiếng Việt, chi phí thật hoặc production acceptance. Tài liệu README nói 34 test; nghiên cứu không dùng con số đó làm kết quả chạy hiện tại.
