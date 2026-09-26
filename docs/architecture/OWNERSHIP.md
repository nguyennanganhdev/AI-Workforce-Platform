# Ownership và kế hoạch bàn giao

Các tên dưới đây là **vai trò team đề xuất**, không phải giả định đã có từng đó team.
Một team có thể kiêm nhiều vai trò. Lead gán người/GitHub team thực tế trước khi bật CODEOWNERS.

| Vai trò | Sở hữu chính | Deliverable đầu tiên |
|---|---|---|
| Platform | `server/src/platform`, `shared/platform`, platform schema/OpenAPI | Tenant context, domain installation, Agent Registry/Version |
| Runtime (Platform) | `agent-runtime`, platform runtime gateway | AgentScope adapter sau Protocol, create/stream/cancel, checkpoint/resume |
| Vinhomes | `server/src/domains/vinhomes`, `shared/domains/vinhomes`, domain schema/OpenAPI | Property scope → Case/ResidentRequest → Incident/Task |
| Frontend | `app/src`, cùng reviewer Platform/Vinhomes theo feature | Nhập OpenBot shell, API client, UX theo contract |
| Integrations (Vinhomes) | `domain-tools/vinhomes`, domain integrations | MCP READ trước; WRITE sau execution grant |
| Data/DevOps | DB plumbing/migration runner, `charts`, CI | Chọn conventions từ upstream, local infra, môi trường test |
| QA (phối hợp các team) | `tests`, fixture/gold set theo domain | Contract, tenant isolation, action retry, regression/publish gate |

## Ranh giới cần review chéo

| Thay đổi | Reviewer cần có |
|---|---|
| DomainAdapter, ActorRef, subject/scope | Platform + Vinhomes |
| ActionProposal/ActionRequest, execution grant | Platform + Vinhomes + Integrations |
| Runtime DTO hoặc protocol | Platform + Runtime |
| HTTP contract dùng bởi UI | Owner backend + Frontend |
| Tenant identity, FK xuyên schema, migration | Data + owner hai phía |
| Idempotency, correlation, outbox | Platform + Vinhomes |
| Publish permission, memory access | Platform + người phụ trách security/review |

Đây là review code/contract thông thường, không yêu cầu các team chờ duyệt để viết module nội bộ.

## Thứ tự triển khai để các team làm song song

| Giai đoạn | Công việc | Phụ thuộc / tiêu chí hoàn tất |
|---|---|---|
| 0 — Khung hiện tại | Thư mục, port, Hono health, CI/import checks | `npm ci && npm run check` chạy được |
| 1 — Foundation | Nhập OpenBot; xác thực tenant; schema identity/property; review DTO và chọn ORM/migration | RequestContext từ identity thật; fixture ít nhất 2 tenant; không tin tenant/actor từ body |
| 2A — Platform | Factory/Registry/Version, catalog và evaluation gate | Agent không tự publish; version formal evaluation bất biến |
| 2B — Domain | Intake → Incident → Task; human/system flows | Domain hoạt động khi runtime không khả dụng |
| 2C — Runtime | AgentScope adapter và authenticated transport | Event/cancel/checkpoint/resume; contract TS/Python tương thích |
| 2D — UI/tools | UI theo OpenAPI, MCP READ theo scope | Có thể dùng mock trong test rõ ràng; không bypass contract |
| 3 — Side effects | Proposal → ActionRequest → Rule/Approval → Grant → MCP WRITE → WorkOrder/Evidence/QC | Retry không tạo side effect trùng; grant giả/hết hạn/sai tenant bị từ chối |
| 4 — Hoàn thiện | Memory approval/retrieval, audit, gold sets và domain mới mẫu | Qdrant không trả revision bị thu hồi; domain mới không sửa Factory schema |

2A–2D có thể chạy song song sau khi chốt phần contract liên quan. Không triển khai toàn bộ catalog
trước khi có luồng end-to-end đầu tiên. Không đưa runtime P1 vào critical path.
