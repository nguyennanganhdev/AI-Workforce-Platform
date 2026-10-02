# Đặc tả tích hợp Agent Factory với Backend

Ngày chốt: 2026-10-02. Chủ sở hữu phần tích hợp: **team Backend**.

## 0. Thay đổi contract 2026-10-02: Skill được generate, không còn được chọn

Factory không còn chọn Skill từ catalogue. Mỗi construction tự sinh một
`generatedSkill` (procedure, tool usage guidance, constraints, completion criteria)
và đưa nó vào `AgentSpec` cùng system prompt. Tool vẫn chỉ được chọn từ catalogue.
Những điểm team BE cần biết, chi tiết ở các mục bên dưới:

| Nội dung | Trước | Bây giờ |
|---|---|---|
| `catalogue.skills` | Bắt buộc, Factory đọc và chọn | Không cần gửi. Nếu gửi, Factory bỏ qua mà không đọc hay validate |
| `catalogue.defaultToolRefs` | Không có | Tùy chọn, tối đa 4 ref, mỗi ref phải có trong `catalogue.tools`. Đây là nơi BE khai báo RAG/knowledge tool của deployment |
| `spec.schemaVersion` / `compilerVersion` | `1` | `2` cho artifact mới. Artifact `1` đã lưu vẫn đọc và chạy như cũ |
| `spec.resources[].kind` | `tool` hoặc `skill` | Artifact mới chỉ có `tool`. Không cần skill grant |
| `spec.procedure`, `spec.acceptanceCriteria` | Top-level | Nằm trong `spec.generatedSkill.procedure` / `.completionCriteria` |
| `spec.intent`, `spec.defaultTools`, `spec.generatedSkill` | Không có | Có trong artifact `2` |
| `requirements[].fulfillment` | Có `skill_instruction` | Chỉ `model_on_input` hoặc `tool` |

**Default tool là "available", không phải "required".** Factory ghi các ref BE khai
báo vào `spec.defaultTools` cho mọi agent, nhưng chỉ khi nghiệp vụ cần (một
requirement bind vào nó) thì tool đó mới xuất hiện trong `spec.resources`. Readiness
hiện tại của BE đọc `spec.resources`, nên default tool chưa được grant không chặn
agent; agent gọi nó khi chưa được grant vẫn bị lớp plugin từ chối. Factory không
tạo grant và không hardcode ref RAG nào. Khi không có ref nào được khai báo, không
tool nào được gắn và `verification.warnings` có `NO_DEFAULT_TOOL`.

**Repo chưa có RAG tool.** Tại thời điểm này không tồn tại endpoint, MCP contract
hay catalogue entry nào cho RAG. Để "mọi generated agent có RAG available", platform
cần đăng ký một tool đọc (ví dụ qua transport `builtin` đã có cho routines) rồi BE
đưa ref đó vào `defaultToolRefs`. Factory không cần thay đổi khi việc đó xong.

**Việc còn lại phía BE (ngoài phạm vi Factory, chưa làm).**
`PluginStore.factoryCatalogue` vẫn đọc bảng skills để dựng projection. Hệ quả: một
deployment có hơn 32 skill nhìn thấy được, hoặc một skill quá lớn, vẫn làm bước đọc
catalogue của BE trả `CATALOGUE_TOO_LARGE` dù construction không dùng skill nào.
BE nên ngừng project skills cho construction (vẫn giữ cho `factoryResourceFacts`
của artifact `1`). Service Factory độc lập không có phụ thuộc này.

## 1. Trạng thái bàn giao và phạm vi

Agent Factory là HTTP service độc lập, đã có authentication, model adapter và
construction pipeline. Theo yêu cầu mới, production Backend **chưa được nối với
Factory**: `server/src/index.ts` không khởi tạo HTTP client/service và không inject
Factory vào `createApp`. Các route `/api/agent-factory/*` hiện trả 404. Cấu hình
environment hoặc khởi động Factory không tự kích hoạt các route này.

Team BE chịu trách nhiệm triển khai/nối lại integration theo tài liệu này. Các
adapter, tests và kiểm tra integrity/readiness cũ được giữ làm tài liệu tham khảo;
không được hiểu là production integration đang hoạt động. Các agent đã lưu không
bị xóa, và không có grants nào được tạo để phục vụ việc bàn giao.

Không thuộc phạm vi: Frontend, DAG, multi-agent orchestration, runtime mới,
dynamic tool generation, tự cấp quyền hoặc chạy tool trong Factory.

Nguồn chuẩn khi có khác biệt:

| Nội dung | Source of truth |
|---|---|
| DTO và envelope | [`src/contracts.ts`](../src/contracts.ts) |
| Request/schema, compiler, hashing, catalogue | [`src/spec.ts`](../src/spec.ts) |
| HTTP route, authentication, status | [`src/http.ts`](../src/http.ts) |
| Pipeline/deadline/repair | [`src/service.ts`](../src/service.ts), [`src/verification.ts`](../src/verification.ts) |
| Client tham khảo | [`src/client.ts`](../src/client.ts), public entry [`src/index.ts`](../src/index.ts) |
| Model/provider environment | [`src/server.ts`](../src/server.ts), [`src/model.ts`](../src/model.ts) |

Không suy ra API hiện tại từ tài liệu tích hợp cũ.

## 2. Ranh giới trách nhiệm

| Factory sở hữu | Backend sở hữu |
|---|---|
| Parse name/role/description; normalize intent | Xác thực user, tenant và quyền tạo/quản lý agent |
| Suy luận capability requirements | Đọc catalogue đúng scope của actor/tenant |
| Resolve exact tool refs từ catalogue được cung cấp; generate skill cho agent | Lưu agent/spec/prompt/report, idempotency và audit |
| Compile AgentSpec và core system prompt | Kiểm tra integrity tại boundary HTTP, khi đọc và trước runtime |
| Static verification, semantic review, tối đa một repair | Grants, credentials, connections, readiness và runtime |
| Provider/model configuration của construction | Model/provider configuration của runtime |

Luồng team BE cần triển khai:

```text
User request -> BE authentication + authorization
             -> validate input + BE idempotency lookup
             -> read bounded actor/tenant-scoped catalogue
             -> POST Factory /v1/constructions with service bearer
             <- verified AgentSpec + prompt + hash + intent + verification
             -> BE integrity and fresh resource checks
             -> atomic persistence + creation audit
             -> READY or PENDING_RESOURCES
```

**Required resource không phải authorized resource.** Factory không nhận grant
mutations, không cấp quyền, không đọc credentials của tools và không thực thi tools.
Factory không có database hoặc tenant/user session. Catalogue gửi từ BE chính là
boundary mà BE phải kiểm soát; không chuyển catalogue tự chọn của browser tới Factory.

## 3. Cấu hình và vận hành

| Environment | Process đọc | Yêu cầu |
|---|---|---|
| `FACTORY_SERVICE_URL` | Client BE tương lai | Base URL của Factory, ví dụ `http://127.0.0.1:4010`; không gồm `/v1/constructions`, credentials, query hoặc fragment |
| `FACTORY_SERVICE_TOKEN` | Factory và client BE | Cùng một private bearer; tối thiểu 32 ký tự, dùng giá trị không chứa whitespace |
| `FACTORY_MODEL` | Factory | Tên model chính xác của provider, không tự đổi model |
| `FACTORY_MODEL_API_KEY` | Factory | Secret đúng provider, chỉ đọc từ environment |
| `FACTORY_MODEL_PROVIDER` | Factory | `openai` hoặc `openai-compatible`; mặc định `openai` |
| `FACTORY_MODEL_API_URL` | Factory | **Full Chat Completions URL**; mặc định `https://api.openai.com/v1/chat/completions` |
| `FACTORY_HOST` | Factory | Mặc định `127.0.0.1`; private container network có thể dùng `0.0.0.0` |
| `FACTORY_PORT` | Factory | Mặc định `4010`; port 0 chỉ dùng test |

Factory start/dev hiện đọc root `.env` bằng Bun `--env-file=../.env`. BE dùng cơ chế
load environment của chính BE. Việc chia sẻ file trong repo không thay thế việc
inject secret riêng cho từng process ở deployment. BE chỉ cần URL/service bearer;
không cần model API key để gọi construction. Không expose các secret này cho Frontend.

Ví dụ cấu hình, tất cả secret là placeholder:

```dotenv
FACTORY_SERVICE_URL=http://127.0.0.1:4010
FACTORY_SERVICE_TOKEN=<private-service-token-at-least-32-characters>
FACTORY_MODEL_PROVIDER=openai
FACTORY_MODEL_API_URL=https://api.openai.com/v1/chat/completions
FACTORY_MODEL_API_KEY=<openai-provider-key>
FACTORY_MODEL=<model-name>
```

Factory không fallback từ `FACTORY_MODEL_*` sang `OPENAI_API_KEY`, `OPENAI_BASE_URL`
hoặc `BOT_MODEL`. OpenAI project/service-account key được nhận diện chỉ được gửi
tới official OpenAI Chat Completions endpoint với provider `openai`. OpenRouter key
được nhận diện phải dùng `openai-compatible` và
`https://openrouter.ai/api/v1/chat/completions`. Endpoint chứa credentials/query/fragment
bị từ chối. Không redirect model request sang provider khác.

Khởi động từ root repo, theo Bun 1.3.14 được pin:

```sh
rtk bunx bun@1.3.14 run --cwd agent-factory start
```

Với BE trong container, loopback của container không phải Factory trên host: dùng
private service DNS/reachable URL. Endpoint construction dành cho BE/service callers,
không mở trực tiếp cho browser. Với kết nối không phải loopback, team triển khai cần
bảo vệ service bearer bằng HTTPS hoặc private network có bảo vệ tương đương.

## 4. HTTP contract

### 4.1 Health

```http
GET /health
```

Không yêu cầu bearer. Response 200:

```json
{"status":"ok","service":"agent-factory"}
```

Đây là liveness của HTTP process. Không xác nhận model credential, provider quota,
semantic quality hoặc readiness của agent. Model readiness cần construction smoke.

### 4.2 Construction request

```http
POST /v1/constructions
Authorization: Bearer <FACTORY_SERVICE_TOKEN>
Content-Type: application/json
```

Body strict, đúng hai field `request` và `catalogue`:

```json
{
  "request": {
    "name": "Notes",
    "role": "Summarizer",
    "description": "Summarize only the text supplied by the user."
  },
  "catalogue": {"tools": [], "defaultToolRefs": []}
}
```

| Request field | Contract |
|---|---|
| `name` | String sau trim, 1–80 ký tự |
| `role` | String sau trim, 1–120 ký tự |
| `description` | String sau trim, 1–1.000 ký tự; có thể là tiếng Việt |

Không thêm `agentId`, `ownerId`, `tenantId`, `model`, `grants`, `credentials`,
`systemPrompt` hoặc `runtime` vào request. Context identity/tenant giữ trong BE.
Factory không có endpoint đọc persisted agent hoặc recheck readiness, không có
Factory-owned idempotency. `Idempotency-Key` của user request là trách nhiệm BE;
gửi header đó sang Factory không tạo bảo đảm idempotency.

Catalogue DTO là `FactoryCatalogueProjection`; **không gửi fingerprint** trong body:

| Tool field | Type/ý nghĩa |
|---|---|
| `kind` | Literal `tool` |
| `ref` | Exact ref từ catalogue; convention hiện tại `serverId/toolName` |
| `name`, `title`, `description` | Metadata thật của resource |
| `inputSchema` | JSON object; giữ nguyên properties và required argument names |
| `outputSchema` | Hiện tại phải là `null` |
| `effect` | `read` hoặc `write`; không suy ra quyền từ field này |
| `destructive` | Boolean từ metadata hiện có |

| Catalogue field | Type/ý nghĩa |
|---|---|
| `tools` | Bắt buộc. Array các tool ở bảng trên |
| `defaultToolRefs` | Tùy chọn. Tối đa 4 ref không trùng, mỗi ref phải là một `tools[].ref`. Sai → 422 `INVALID_CATALOGUE` |
| `skills` | Không dùng. Được chấp nhận để projection cũ của BE vẫn parse, và bị bỏ qua mà không đọc |

Refs là identifiers để exact-match, không tự đổi slug/case, không invent ref khi
resource thiếu. Refs không được trùng. Catalogue là metadata của
resources có thể được lựa chọn; resource chưa được grant vẫn có thể xuất hiện để
Factory khai báo requirement và BE trả pending. Không đưa access tokens, credentials,
connection secrets hay grant decisions vào catalogue. Nếu resource cần thiết không
available, giữ đúng catalogue thực tế và xử lý construction refusal; không tự chế tool.

Factory giới hạn 64 tools và 4 default tools; catalogue 96 KiB (bao gồm snapshot được
normalize/fingerprint, không tính `skills`), toàn request 128 KiB. Spec chọn tối đa 8 tools.
Individual generated text tối đa 4.096 ký tự, các list thông thường tối đa 32 items;
compiled core prompt tối đa 16 KiB. Catalogue quá lớn phải được xử lý có chủ đích ở BE,
không truncate instructions/schema hoặc cắt bỏ resource ngẫu nhiên để vượt validator.

### 4.3 Response thành công

HTTP **200** là construction thành công, chưa có persisted agent hay quyền thực thi:

```ts
interface FactoryConstructionResponse {
  spec: AgentSpec;
  systemPrompt: string;
  specHash: string;
  intent: IntentNormalizationResult;
  verification: VerificationResult;
}
```

Các field quan trọng của `AgentSpec`:

| Field | Contract |
|---|---|
| `schemaVersion`, `compilerVersion` | Literal `2` cho artifact mới. `1` chỉ còn ở artifact đã lưu (xem `LegacyAgentSpec`) |
| `identity` | Request đã validate/trim; model không được đổi name/role/description |
| `intent` | `normalizedGoal`, `taskType`, `explicitRequirements`, `inferredRequirements`: cách construction đọc request |
| `goal`, `responsibilities`, `constraints` | Behavior được compile, có source provenance ở statements |
| `generatedSkill` | `name`, `objective`, `procedure[]`, `toolUsageGuidance[{toolRef, whenToUse, purpose, guidance}]`, `constraints[]`, `completionCriteria[]`. Text khai báo, không phải code, không cần grant |
| `requirements` | Capability requirements với `id`, `need`, `fulfillment`, `source` |
| `resources` | Required tools: `kind: "tool"`, `ref`, `requirementIds`, `fingerprint`, `argumentSources` |
| `defaultTools` | `[{ref, fingerprint}]` đúng theo `catalogue.defaultToolRefs`; available, không required |
| `inputContract` | `ag_ui_messages`, string schema, named input facts và missing behavior |
| `outputContract` | `ag_ui_messages`, string schema, expectations, enforcement `prompt_only` |
| `runtimeProfile` | Literal `openbot_builtin_v1` |

Mọi `toolUsageGuidance[].toolRef` là một ref trong `resources` hoặc `defaultTools`,
và mỗi tool trong `resources` có đúng một guidance entry. Factory từ chối skill nhắc
tới tool khác của catalogue, chứa code/command hoặc giá trị có dạng secret. Cùng các
kiểm tra đó chạy lại trong `createFactoryClient` và `parseStoredFactoryConfiguration`.

`required resources` nằm trong **`spec.resources`**, không có top-level
`requiredResources` riêng. Không tự thêm version, endpoint, credentials, grants hoặc
DAG fields vào DTO. Text output contract không phải JSON/schema enforcement của runtime.

`intent` gồm `originalInput`, `normalizedGoal`, `taskType`, `explicitRequirements`,
`inferredRequirements`, `confidence`, `missingInformation`. Intent được normalize
bằng tiếng Anh theo prompt, còn identity giữ nội dung request. Task type là label mô
tả công việc, không phải capability ontology/ref. HIGH có missingInformation rỗng;
LOW dừng construction với NEEDS_INPUT. Bốn field mô tả nghiệp vụ được giữ trong
`spec.intent` và compile vào prompt; `confidence`, `missingInformation` và
`originalInput` chỉ có ở response, không nằm trong AgentSpec.

BE chỉ nhận success khi `verification.construction === "PASS"`,
`semanticReview.verdict === "PASS"`, issues và criterionFindings rỗng;
`verification.specHash` phải bằng `specHash`. `attempts` là 1 hoặc 2: generation ban
đầu và tối đa một repair. Semantic review ghi modelRef, không chứa provider key.
Static validation và semantic review diễn ra trong Factory; success không được
Backend diễn giải thành authorization hoặc permission to execute.

### 4.4 Error response và mapping

```ts
interface FactoryHttpError {
  error: string;
  code: string;
  issues: Array<{
    code: string;
    path: string;
    sourceStage: "request" | "draft" | "resources" | "compiler" | "access" | "dependency";
    evidenceRefs: string[];
    message: string;
  }>;
  retryable: boolean;
}
```

`issues` có thể rỗng ở lỗi HTTP/auth. Factory envelope không có `constructionId`;
field đó chỉ xuất hiện trong error DTO của BE adapter. `retryable` ở Factory hiện
được tính từ status >= 500, không phải chỉ thị tự động retry.

| Factory HTTP | Code/trường hợp | BE xử lý |
|---|---|---|
| 400 | INVALID_BODY, INVALID_REQUEST | Từ chối input/body, không persist |
| 401 | UNAUTHENTICATED | Lỗi service auth/config; client tham khảo chuyển thành dependency failure an toàn, BE 503 |
| 404 | NOT_FOUND | Sai Factory URL/path; không fallback |
| 405 | METHOD_NOT_ALLOWED; Allow: POST | Sai phương thức gọi |
| 413 | BODY_TOO_LARGE | Sửa request/catalogue payload; không truncate spec |
| 415 | UNSUPPORTED_MEDIA_TYPE | Gửi application/json |
| 422 | INVALID_CATALOGUE hoặc construction refusal | Đọc issue codes, không persist artifact |
| 503 | Model/reviewer không khả dụng, timeout theo call hoặc cancellation | Safe dependency failure, không persist |
| 504 | DEADLINE_EXCEEDED | Hết deadline; không persist muộn |
| 500 | INTERNAL_ERROR | Safe dependency failure |

Ví dụ issue codes 422: NEEDS_INPUT, BLOCKED_RESOURCE, UNKNOWN_RESOURCE,
UNSUPPORTED_CONTRACT, UNSUPPORTED_RUNTIME_PROFILE, REPAIR_SCOPE_VIOLATION, ATTEMPTS_EXHAUSTED.
BE phải dựa vào status + structured codes/stage thay vì parse message prose;
danh sách codes trong bảng không phải exhaustive enum. NEEDS_INPUT để BE xin thêm
thông tin, missing resources để sửa catalogue/config đúng scope; không LLM-retry
permission/access failures. Không forward raw provider/proxy diagnostics cho user.

Không retry hay follow redirect mặc định. Client tham khảo chỉ forward structured
refusal 422; các HTTP/proxy/auth failures ngoài contract được sanitize. Invalid
artifact 200 trở thành ARTIFACT_INVALID, adapter BE hiện map 409; HTTP/network/auth
dependency failure map 503, deadline map 504. Không đánh đồng 503 với user chưa login.

## 5. Kiểm tra bắt buộc ở boundary Backend

Trước persistence, BE phải kiểm tra tất cả các mục sau, không chỉ tin HTTP 200:

1. Response JSON đúng schema strict và version/runtime profile được hỗ trợ.
2. `spec.identity` và `intent.originalInput` bằng request **đã validate/trim**;
   không dùng identity do caller/model chọn để gán owner hoặc tenant.
3. Intent success không có confidence LOW; confidence và missingInformation nhất quán.
4. Construction và semantic review PASS, không còn blocking issues/findings.
5. Mọi `spec.resources` exact-match kind/ref/fingerprint trong catalogue snapshot
   mà BE đã gửi; không có ref do Factory tự invent hoặc resource ngoài scope.
6. `specHash === hashAgentSpec(spec) === verification.specHash`.
7. `systemPrompt === renderCorePrompt(spec)`, không append/chỉnh sửa core prompt
   trước khi kiểm tra hoặc persist. Runtime-owned guidance được compose ở runtime.
8. Đọc lại resource facts đúng owner/scope ngay trước save. Resource bị xóa/thay đổi
   fingerprint phải bị từ chối/reconstruct; không tự cập nhật fingerprint cho spec cũ.
9. Error/cancellation không thể dẫn tới late commit hoặc artifact partial.

SDK `createFactoryClient` hiện thực các kiểm tra response/request/snapshot/hash/prompt
ở boundary HTTP. Fresh resource facts và persistence là trách nhiệm của BE sau client.
Không xem model review là thay thế cho các kiểm tra deterministic này.

Hash là SHA-256, lowercase hex, trên UTF-8 của JSON canonical của repository:
object keys sort, array order giữ nguyên, primitive/string serialization theo
`JSON.stringify`; không hash raw HTTP body hoặc JSON pretty-print. Tool fingerprint
bao gồm kind/ref/name/title/description/inputSchema/outputSchema/effect/destructive.
Skill fingerprint (chỉ dùng cho readiness của artifact `1`) bao gồm
kind/ref/title/description/instructions và toolRefs đã sort.
Không bỏ field khi tính fingerprint. Backend khác ngôn ngữ cần parity với helper và
fixtures, đặc biệt Unicode/number serialization; không tự coi đây là một chuẩn
canonical JSON khác rồi thay thuật toán.

Không persist `specHash` như chứng cứ đủ nếu spec/prompt đã bị thay đổi. Kiểm tra
hash/prompt lại khi read và trước runtime, sử dụng immutable artifact. Edit/copy
generated agent phải đi theo chính sách reconstruction; không biến artifact verified
thành prompt chỉnh tay vẫn mang trạng thái PASS.

## 6. Use cases Backend cần hoàn thiện

### 6.1 Tạo và lưu idempotently

- Xác thực user và quyền tạo trong deployment/tenant hiện tại.
- Validate name/role/description; nhận `Idempotency-Key` bounded từ caller.
- Scope key theo actor và tenant/deployment thích hợp. Cùng key và cùng request
  replay agent đã lưu; cùng key và khác request trả conflict. Retry không gọi lại
  Factory nếu đã có stored construction. Đảm bảo concurrent requests không tạo hai rows.
- Lấy catalogue đúng scope từ infrastructure hiện có; không tạo một registry riêng.
- Gọi Factory bằng HTTP. **Không** inject `complete`/`constructAgentSpec` như fallback
  khi Factory/auth/model không khả dụng.
- Validate artifact, đọc fresh facts và persist spec/prompt/verification/readiness
  trong transaction. Chỉ công bố success sau commit. Thông tin thiếu grants/connections
  là pending có thể persist; RESOURCE_CHANGED/RESOURCE_MISSING không được save như ready.
- Audit metadata outcome/hash/resource refs/issue codes; không log bearer, provider/tool
  key, raw provider response, prompt hoặc completion vào audit.

Với adapter/store đang có, canonical storage là:

```ts
// Type của agents.configuration, với DTO từ Factory contracts.
type StoredGeneratedConfiguration = {
  systemPrompt: string;
  factory: {
    spec: AgentSpec;
    verification: VerificationResult;
    state: "ready" | "pending_resources";
    requestHash: string; // BE-derived SHA-256
    creationKeyHash: string; // BE-derived SHA-256
  };
};
```

Shape minh họa TypeScript, không phải JSON request gửi Factory. Dùng profile/store
transaction hiện có, không dual-write một AgentSpec khác làm nguồn chuẩn. `specHash`
top-level của response được đối chiếu rồi đã có trong verification. Owner, visibility,
agent ID và idempotency fields do BE xác định, không lấy từ Factory. Intent không
phải persisted configuration field hiện tại. Nếu team chọn storage khác, phải giữ
integrity/readiness/transaction invariants và version compatibility; đó là quyết định BE.

### 6.2 Readiness, read/recheck và runtime

`READY`/`PENDING_RESOURCES` là tên nghiệp vụ; JSON/storage hiện dùng `ready`/
`pending_resources`. Đánh giá theo **stored creator/owner**, không dùng connection
của admin đang inspect để thay connection của owner.

Mỗi required resource cần exists, fingerprint khớp, granted cho agent, configured
và connected đúng owner. Blockers của adapter hiện có: RESOURCE_MISSING,
RESOURCE_CHANGED, GRANT_REQUIRED, CONFIGURATION_REQUIRED, CONNECTION_REQUIRED;
owner bị mất có OWNER_UNAVAILABLE. Có blocker thì pending, không runtime-executable.
Spec không cần external resources vẫn có thể ready nếu mọi điều kiện khác hợp lệ.

Read/recheck chỉ dùng stored artifact và fresh resource facts. Không gọi model,
không recompile bằng model, không cấp grants. Recheck nhận expected `specHash`
để không ghi readiness vào artifact đã đổi. Resource fingerprint đổi cần reconstruct,
không sửa hash hoặc spec trong recheck. Runtime load kiểm tra integrity và fresh owner
access trước execution; execution-time tool/grant authorization vẫn là authority cuối.
Read chỉ trả fresh assessment, không ghi state. Stored pending vẫn bị runtime gate
chặn cho tới khi explicit recheck cập nhật stored readiness, kể cả khi grants đã có.

### 6.3 API phía BE, sau khi team BE nối lại

Factory không yêu cầu tên route user-facing cụ thể. Để tái dùng adapter hiện có,
team BE có thể triển khai lại contract sau:

| Route BE (hiện unmounted) | Input | Response sau tích hợp |
|---|---|---|
| POST `/api/agent-factory/constructions` | Auth user, Idempotency-Key; body chỉ name/role/description | 201 ready hoặc 202 pending; `{agent,spec,verification,readiness}` |
| GET `/api/agent-factory/:agentId` | Auth owner/admin | 200, intact stored artifact và fresh readiness |
| POST `/api/agent-factory/:agentId/recheck` | Auth owner/admin; body `{specHash}` | 200 ready; adapter hiện trả 409 RESOURCES_PENDING nếu pending |

Giới hạn adapter BE hiện có: Idempotency-Key printable ASCII, 1–128 ký tự;
body tối đa 32 KiB; expected hash là 64 lowercase hex. Invalid artifact/conflict là
409, storage/dependency failure là 503, deadline là 504; không lưu agent khi lỗi.
Factory-only errors không được pass-through thành user authentication error.

Nếu team BE đổi API phía user, tự sở hữu contract đó; **không đổi Factory wire DTO
chỉ để khớp naming/storage của BE**. Tài liệu này không yêu cầu triển khai Frontend.

## 7. HTTP client, deadlines và điểm ghép trong repository

Public helpers cho BE TypeScript: `createFactoryClient`, `prepareFactoryCatalogue`,
`hashAgentSpec`, `renderCorePrompt`, `parseStoredFactoryConfiguration` qua
`agent-factory/src/index.ts`; DTO types qua contracts hoặc public type exports.
Production BE không import sâu vào Factory implementation hoặc gọi core constructor.
Factory production chỉ import nội bộ, Zod và standard APIs; không import BE/DB/Hono.

Ví dụ **chưa được wire vào production**, dành cho team BE:

```ts
import {
  createFactoryClient,
  prepareFactoryCatalogue,
  type AgentCreationRequest,
  type FactoryCatalogueProjection,
} from "../../agent-factory/src/index.js"; // Ví dụ đặt ở server/src/

const construct = createFactoryClient({
  url: process.env.FACTORY_SERVICE_URL ?? "",
  token: process.env.FACTORY_SERVICE_TOKEN ?? "",
});

async function constructOverHttp(
  request: AgentCreationRequest,
  projection: FactoryCatalogueProjection,
  signal: AbortSignal,
) {
  const catalogue = prepareFactoryCatalogue(projection);
  if (!catalogue.ok) return catalogue;
  // projection do BE đọc; client bỏ fingerprint khi serialize HTTP body.
  return construct(request, catalogue.value, { signal, timeoutMs: 90_000 });
}
```

Function trên chưa persist hoặc authorize, và không tạo grants. Nếu dùng adapter
repository, điểm ghép tương lai là `createAgentFactoryService({store,profiles,
auditStore,constructSpec:createFactoryClient(...)})`, rồi inject optional service vào
`createApp`. Chỉ team BE thực hiện bước này. Không dùng nhánh local completion injection.

| Giới hạn | Hiện tại |
|---|---|
| Factory total construction deadline | Tối đa 90 giây |
| Mỗi generation/review/repair model call | Tối đa 20 giây |
| Generation attempts | 2, tức tối đa một repair |
| Client total deadline | Cap 90 giây; nhận caller cancellation/remaining budget |
| Client response body limit | 1 MiB |
| Client retries/redirects | Không retry; redirect bị từ chối |
| Factory HTTP idle timeout | 120 giây |

BE nên dùng một end-to-end budget, trừ thời gian catalogue/fresh facts và persist;
propagate cancellation qua HTTP và transaction. Đặt socket/reverse-proxy timeout
đủ dài cho deadline trả structured error, ví dụ 120 giây trên construction route.
Timeout route này đã bị gỡ khỏi production BE; team phải cấu hình lại khi nối.
Không tăng hạn mức để che model lỗi hoặc tạo retry vô hạn.

## 8. Request/response mẫu để team BE dùng

- [Request Web Researcher](examples/web-researcher-request.json): exact input tiếng Việt,
  metadata tool Tavily lấy từ catalogue hiện có, và một `defaultToolRefs` minh họa.
- [Verified response Web Researcher](examples/web-researcher-response.json): artifact
  `schemaVersion 2` do pipeline thật tạo ra qua `POST /v1/constructions`, với model
  là **fixture offline** (`modelRef: fixture/offline`). Đây không phải output của
  model thật; mẫu trước đó từ `openai/gpt-4.1` thuộc contract cũ và đã được thay.

Đây là fixture minh họa, **không phải whitelist hoặc thuật toán hardcode của Backend**.
BE thực tế gửi catalogue hiện tại đúng scope. Không copy fixture để thay catalogue
production, không mặc định Tavily có sẵn ở mọi deployment. Tool
`example-knowledge/query` trong mẫu **không tồn tại**: nó chỉ cho thấy hình dạng của
một default tool do BE khai báo.
Full response là JSON hợp lệ, không dùng placeholder thay spec/hash/prompt.
Sample không chứa credentials, grants, agent ID, persistence hoặc readiness.

Input nghiệp vụ trong mẫu:

```json
{
  "name": "Web Researcher",
  "role": "Internet Research Agent",
  "description": "Tìm kiếm thông tin trên Internet và tổng hợp câu trả lời có dẫn nguồn."
}
```

Kết quả kỳ vọng: intent hiểu internet search + synthesis + citations; research
requirements; resolve exact catalogue refs nếu available; verified spec + resources.
Sau save, agent chưa có grants phải pending. Không yêu cầu core hardcode sample,
không nới validator để sample pass. Smoke này chỉ construction; không chứng minh
Tavily call/runtime response đã thực hiện.

## 9. Acceptance tests và trình tự triển khai của team BE

| Nhóm | Test bắt buộc |
|---|---|
| Factory độc lập | Health 200; missing/wrong token 401; valid bearer + malformed body 400; correct construction 200 |
| Body/catalogue | Extra fields/secrets bị reject; payload overflow; duplicate/out-of-scope/invented refs; required tool arguments |
| Provider | Đúng model/key/endpoint; credential mismatch bị chặn; không log/forward secret; không redirect |
| Response integrity | Sai identity/hash/prompt/fingerprint, FAIL review hoặc malformed response phải bị từ chối, không writes |
| Backend persistence | Auth/scoping, atomic save, reload integrity, concurrent idempotent create, replay/conflict/deleted-key behavior |
| Authorization/readiness | Required resource chưa grant vẫn pending; không tạo grants; owner facts thay vì admin facts; revoked/changed/missing resources bị chặn |
| HTTP dependency | Factory down/wrong token/cancellation/deadline không tạo row, không late save, không direct/in-process fallback |
| Read/recheck/runtime | Không gọi Factory/model; expected hash check; pending/corrupt agent không chạy; final tool authorization giữ nguyên |
| Real model | Input Web Researcher qua BE HTTP, kiểm tra intent/resources/verification, persisted artifact và readiness đúng grants |
| Regression/static | Existing agent/profile/runtime/auth/model tests, module và BE typecheck, architecture checks |

Trình tự:

1. Chốt actor/tenant scoping, storage transaction/idempotency và error mapping BE.
2. Implement HTTP client/adapter boundary, kiểm tra success/error/integrity bằng fixtures.
3. Wire production composition/routes và socket timeout; giữ no-fallback.
4. Verify against separate migrated test DB, không chạy destructive regression vào DB ứng dụng.
5. Chạy real Factory + real model smoke qua BE; kiểm tra secret-free audit và grants không đổi.
6. Chỉ thực hiện runtime E2E sau khi được cấp grants/connections một cách rõ ràng.

Các command có thật trong repo:

```sh
rtk bunx bun@1.3.14 run --cwd agent-factory check
rtk bunx bun@1.3.14 run typecheck
rtk bunx bun@1.3.14 run typecheck:workforce
rtk bunx bun@1.3.14 run check:architecture
rtk env TEST_DATABASE_URL=<dedicated-test-url> bunx bun@1.3.14 test \
  server/tests/agent-factory-routes.test.ts \
  server/tests/agent-factory.integration.test.ts \
  server/tests/agent-factory-runtime.integration.test.ts
```

Các integration tests hiện inject service/client riêng trong test; pass không có
nghĩa production đã reconnect. Script lịch sử
`server/scripts/factory-http-smoke.ts` chỉ dùng sau reconnection với local single-user
BE; hiện script fail rõ ràng trước paid model work khi route chưa mount. Không dùng
script này như Factory standalone smoke hay như bằng chứng production wiring hiện tại.

Checklist DoD của team BE:

- [ ] Production tạo agent bằng real Factory HTTP, không chỉ injection trong test.
- [ ] Auth/schema/timeout/no-fallback/error contracts được verify.
- [ ] Integrity, scoped catalogue/fresh facts và atomic persistence pass.
- [ ] Idempotency và read/recheck không gọi model khi replay/inspect.
- [ ] Không có automatic grants; readiness/runtime theo current owner access.
- [ ] Real-model smoke và relevant regressions/typechecks/architecture pass.
- [ ] Có executed evidence, command exit status và blocker/limitation còn lại.

## 10. Những phần đã có để tái dùng và những phần không được tự nối lại

| File | Vai trò lúc bàn giao |
|---|---|
| `agent-factory/src/*` | Service/core/DTO/client vẫn hoạt động độc lập |
| `server/src/agents/factory.ts` | Adapter/use cases/readiness tham khảo, giữ stored-artifact guards |
| `server/src/agents/factory-routes.ts` | Optional route adapter, không mount trong production |
| `server/src/app.ts` | Optional `agentFactory` injection seam, hiện không được cấp service |
| `server/src/agents/profile-store.ts` | Existing transactional persistence/integrity mechanics |
| `server/src/plugins/store.ts` | Existing catalogue/grants/fresh resource facts |
| `server/src/index.ts` | **Không Factory HTTP client/service injection**, runtime integrity/readiness vẫn giữ |

Không xóa guards của stored generated agents để làm BE “hết phụ thuộc”; chúng bảo
vệ dữ liệu/runtime hiện có và không gọi Factory HTTP. Không sửa Frontend hoặc mount
lại BE endpoints như một phần của việc đọc tài liệu này. Việc integration là công
việc tiếp theo của team BE, cần evidence mới khi hoàn thành.

Các kết quả ghép BE/live smoke trước lần gỡ được giữ ở
[HTTP verification](http-integration-verification.md) như lịch sử. Trạng thái hiện
tại là standalone Factory; production BE routes 404. Tài liệu này và JSON examples
là gói bàn giao để triển khai integration tiếp theo.
