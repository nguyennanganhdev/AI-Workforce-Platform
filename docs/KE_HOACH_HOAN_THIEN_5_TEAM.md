# Kế hoạch hoàn thiện AI Platform Builder — giao việc cho 5 team và AI coding

**Đính chính phạm vi Team Hoàng:** phụ trách Reception agent **và năng lực Report agent để BQL tự tạo trên platform**, gồm template cấu hình, prompt, tool báo cáo, định nghĩa chỉ số và nội dung/artifact báo cáo. Chiến xây UI/API builder và cổng dữ liệu có phân quyền; Đông thực thi Report agent trong runtime AgentScope; Team 5 vận hành. Phần phân công dưới đây đã cập nhật theo phạm vi này.

Ngày rà soát: 29/09/2026. Nhánh nguồn: `develop`, commit nền `df8b4aa`. Đây là kế hoạch triển khai, không phải xác nhận các chức năng dưới đây đã hoàn thành.

## 1. Cách dùng tài liệu này

Mỗi thành viên đưa toàn bộ file này cho AI cùng **tên team và mã task**. AI đọc mục 2–7, task được giao, hợp đồng ở mục 9 và tiêu chí ở mục 12 trước khi sửa code. Nếu chưa có task, chọn task đầu tiên của team có dependency đã hoàn thành; không tự làm cả backlog.

Các đường dẫn có nhãn **MỚI** chưa có trong project lúc rà soát. Chỉ tạo khi bắt đầu task tương ứng. Tài liệu này không yêu cầu tạo ngay tất cả skeleton hoặc thay toàn bộ kiến trúc OpenBot.

Quy tắc thực thi cho AI:

1. Kiểm tra `git status`, nhánh hiện tại và `AGENTS.md` áp dụng. Không reset, checkout đè, xóa hoặc đưa vào commit thay đổi không thuộc task.
2. Chỉ sửa trong vùng sở hữu của team tại mục 5. Quy tắc đường dẫn cụ thể hơn thắng quy tắc thư mục cha. Đường dẫn chưa được phân công mặc định thuộc Team 5 và giữ nguyên khi chưa có task bảo trì.
3. Không sửa schema/migration, entrypoint hay hợp đồng chung để “làm cho test pass” nếu không sở hữu file. Viết yêu cầu tích hợp có chữ ký hàm/schema, ví dụ và test mong đợi gửi owner; trong lúc chờ, dùng mock theo hợp đồng đã chốt ở test, không đưa mock vào production.
4. Đọc code hiện tại trước khi tạo module mới. Tái sử dụng OpenBot auth, agent registry, plugin broker, channel UI và work queue khi phù hợp; không coi chúng đã đáp ứng toàn bộ nghiệp vụ mới.
5. Không tự chạy migration vào database thật, không đưa secret vào Git, không force-push hay thay remote/nhánh khác. Migration được kiểm chứng trên database test trước.
6. Không tuyên bố hoàn thành chỉ vì có bảng DB, endpoint trả 200 hoặc mock chạy được. Task phải có test và kết quả tích hợp theo tiêu chí riêng.
7. Khi bàn giao: liệt kê file sửa, hành vi đạt được, lệnh test/kết quả, dependency còn thiếu, env mới và migration nếu có. Phân biệt test đã chạy với test chưa chạy.

## 2. Mục tiêu sản phẩm và quyết định kiến trúc

- Platform cho người dùng tạo, cấu hình, kiểm thử và publish subagent; Vinhomes là domain kiểm chứng đầu tiên, không được hardcode thành toàn nền tảng.
- Bốn role: `admin`, `management` (ban quản lý), `staff` (nhân viên), `customer` (khách hàng/cư dân). Role phải đi kèm tenant và scope nghiệp vụ; “management” không mặc nhiên được đọc mọi tòa.
- Reception cố định do hệ thống cung cấp, dùng LangGraph. Subagent được tạo từ cấu hình trên platform, chạy trong groupchat dùng AgentScope 2.0 theo định hướng sản phẩm; dependency cụ thể phải được pin và kiểm chứng ở D01.
- Mỗi tài khoản management có cấu hình agent/groupchat riêng. Tài khoản người dùng, đơn vị quản lý, workspace, cấu hình groupchat và phiên groupchat xử lý ticket là các đối tượng khác nhau.
- Supervisor có **một mẫu logic dùng chung**, được khởi tạo với context của phiên xử lý. Hai ticket có thể dùng cùng mẫu nhưng không chia sẻ mutable state, thread hay memory riêng của khách hàng.
- Backend xác minh địa bàn và chọn đích quản lý/groupchat; supervisor chỉ điều phối bên trong đích đã chọn. Model không được tự quyết định tenant hoặc thẩm quyền.
- Reception/subagent đề xuất assessment; **backend triage engine** áp dụng policy đã publish để quyết định severity/priority/emergency và SLA. Dispatcher sử dụng thứ tự ưu tiên để phân công thật.
- PostgreSQL quản lý dữ liệu nghiệp vụ, metadata, ownership, audit và outbox. S3/MinIO lưu bytes ảnh/tài liệu. Framework quản lý storage nội bộ theo adapter đã chọn, không thay database nghiệp vụ.
- Tool nghiệp vụ gọi backend service/API được kiểm soát quyền. Agent không cầm credential PostgreSQL nghiệp vụ hoặc secret S3 toàn quyền. Ngoại lệ: adapter persistence framework dùng credential riêng, chỉ truy cập vùng storage được cấp.

## 3. Kết quả rà soát project hiện tại

Phạm vi khảo sát: inventory các thư mục cấp cao; manifest/config; entrypoint server, worker, supervisor, LangGraph; routing, role, schema/catalog, SQL invariants; frontend routes; Docker/CI và cấu trúc test. Đây là đánh giá kiến trúc và khoảng trống, chưa phải kiểm thử end-to-end mọi file hay xác nhận database thực đã migrate.

| Vùng hiện có | Bằng chứng trong code | Kết luận cho kế hoạch |
|---|---|---|
| `server/` | Bun + Hono, Better Auth, Drizzle; `src/app.ts`, `src/index.ts` nối nhiều module | Có nền API/auth/plugin/channel; cần bổ sung service nghiệp vụ và giảm sửa chồng entrypoint |
| `app/` | React/Vite/TanStack; routes agent, channel, admin, settings | Tái sử dụng shell; chưa có đầy đủ màn hình cư dân, BQL, nhân viên và workflow ticket V3 |
| `server/src/db/` | `tables.ts`, ba catalog JSON, invariants; 148 bảng ứng dụng | Có schema, chưa đồng nghĩa có repository/service/API cho 148 bảng; cần kiểm tra auth và invariant trên PostgreSQL thực |
| `server/drizzle/` | `0000_grey_blockbuster.sql`, snapshot/journal mới | Baseline đã tồn tại; không xóa/tái tạo lịch sử này khi các team bắt đầu dùng chung |
| `server/src/auth/`, `deployment-scope.ts` | Bốn role; bootstrap một tenant/workspace theo package | Chưa đủ onboarding BQL riêng và phân quyền đa scope; không dùng default deployment workspace làm workspace của mọi BQL |
| `server/src/routing/` | Chọn coworker theo message/roster | Không phải routing địa bàn/service coverage của ticket; xây module routing nghiệp vụ riêng |
| `agent-langgraph/` | Bot TypeScript có AG-UI, graph compile chưa gắn persistent checkpointer | Nền tham khảo, chưa phải Reception bền vững theo user/session |
| `agent-langgraph-agui/` | Python sample dùng `MemorySaver()` | Checkpoint bộ nhớ không đủ cho restart/multi-replica; không chạy song song hai Reception production |
| `supervisor/` | `src/index.ts` quản lý container qua Docker socket | **Container supervisor**, thuộc Team 5; tuyệt đối không đặt logic supervisor nghiệp vụ vào đây |
| `agent-ag2/` và adapter `agent-*` khác | Harness cho nhiều framework; `agent-ag2` phụ thuộc AG2 | AG2 không phải AgentScope. Chưa thấy runtime AgentScope nghiệp vụ trong đường chạy đã khảo sát |
| `worker/`, `server/src/work/`, `routines/` | Queue/lease và routine sweeps | Có nền job; chưa có đầy đủ dispatcher/SLA/outbox notification cho V3 |
| `server/src/plugins/` | MCP/Composio, broker, grants | Dùng làm nền tool registry; chưa có tool sửa chữa, vệ sinh và RAG theo scope Vinhomes |
| `docker-compose.yml`, `charts/`, `spire/`, `docker/` | PostgreSQL pgvector và hạ tầng OpenBot | Cần nối Reception/AgentScope, S3/MinIO, job, secret và observability; kiểm tra lại command migration trong Compose so với image production |
| `shared/` | Helper TypeScript và test dùng chung | Chưa có hợp đồng nghiệp vụ versioned dùng chung cho TS và Python |
| `desktop/`, `agent-computer/`, `assets/` | Desktop và công cụ máy tính của OpenBot | Giữ tương thích; không phải đường găng MVP nghiệp vụ căn hộ |
| `examples/fintech/`, các `examples/` khác | Tenant package mẫu và bot samples | Chỉ tham khảo; tạo fixture Vinhomes riêng, không đổi toàn bộ sample thành dữ liệu thật |
| `.github/CODEOWNERS` | Còn tài khoản maintainer upstream | Team 5 cần thay bằng GitHub team thực sau khi có danh sách; tài liệu này chưa cấu hình bảo vệ nhánh |

Các kiểm chứng schema được ghi trong `docs/DATABASE_IMPLEMENTATION_V3.md` là kết quả đợt trước, không thay kết quả CI cho commit mới. Không giả định `.env`, PostgreSQL, MinIO hoặc mọi test integration đang sẵn sàng.

Tài liệu V3 còn tham chiếu bản Reviewed V2 nhưng file Markdown V2 không có trong `docs/` lúc rà soát. Dùng `server/src/db/design/v2.json`, `v3.json`, `merged.json` để đối chiếu dữ liệu; C01 phải phục hồi nguồn thiết kế hoặc ghi lại nguồn chuẩn. Không suy diễn từ đường dẫn tài liệu không tồn tại.

## 4. Các khoảng trống cần giải quyết trước khi xây tính năng

### 4.1. Groupchat riêng cho từng BQL chưa được mô hình hóa đầy đủ

`workspaces` hiện có `management_unit_id`, chưa có ownership trực tiếp theo tài khoản. `workspace_members` biểu diễn thành viên, không đủ chứng minh chủ workspace. `agent_teams` có `ticket_id`, `ticket_generation`, `requested_by_user_id` và state thực thi; không được mặc nhiên dùng một row làm cả cấu hình groupchat lâu dài lẫn phiên mọi ticket.

C02 phải thiết kế phần mở rộng, tên dưới đây là **đề xuất, chưa phải bảng có sẵn**:

- Quyền sở hữu workspace theo membership management của tenant, cùng quy trình đổi chủ/thu hồi. Không dùng `created_by` làm quyền sở hữu lâu dài.
- `groupchat_definitions`, `groupchat_versions`, `groupchat_version_members`: cấu hình và roster có phiên bản, owner workspace, supervisor template/release hệ thống; cấu hình published bất biến.
- `routing_destinations`, `routing_bindings`: liên kết domain + service category/request kind + coverage/scope + thời gian hiệu lực với đơn vị quản lý, tài khoản chịu trách nhiệm, workspace và groupchat version.
- Mở rộng `agent_teams` hoặc quan hệ tương đương để pin groupchat version/destination của phiên ticket, không sao chép tùy ý vào JSON thiếu ràng buộc.

Chiến đối chiếu khả năng tái sử dụng bảng hiện có trước khi chốt tên. Đông review cấu hình runtime; Hoàng review kết quả routing. Mỗi nguồn quan hệ chỉ có một nơi chính thức, không vừa FK vừa hai JSON tự cập nhật.

Nếu hai BQL cùng quản lý một tòa: cấu hình rõ người/nhóm trực, loại dịch vụ và quy tắc fallback. Nếu nhiều đích vẫn đồng hạng hoặc không có đích, đưa vào hàng chờ cần xử lý; không chọn ID đầu tiên hay để LLM đoán. Chuyển BQL phải tạo routing event và handoff, không đổi chủ thread cũ.

### 4.2. Không xem CHECK/trigger hiện tại là hệ thống phân quyền hoàn chỉnh

RLS hiện chủ yếu theo tenant. Backend phải kiểm tra scope, assignment, ACL và trạng thái account trong từng hành động. Rà soát `approved_by`/review khi hạ mức: có user ID không đồng nghĩa đã được phê duyệt hợp lệ. Các bảng global/legacy không tự được bảo vệ như bảng tenant.

### 4.3. Có bảng cho nghiệp vụ rộng hơn MVP

Không coi mọi bảng có sẵn là yêu cầu sản phẩm. Payment/refund chưa được người dùng yêu cầu và không thuộc backlog bắt buộc; không tự triển khai hoặc drop bảng. Ghi nhận chi phí sửa thực tế để học giá không cần invoice/payment/refund. Report agent đã được xác nhận thuộc Team Hoàng và MVP; service interruption cần đối chiếu nghiệp vụ trước triển khai.

### 4.4. Học kinh nghiệm từ ticket — phạm vi đã xác nhận

Đọc cùng [thiết kế học kinh nghiệm, self-help và giá](THIET_KE_HOC_KINH_NGHIEM_SELF_HELP_GIA.md). Phạm vi này dùng long-term knowledge memory/RAG và thống kê giá có xác nhận, không cần RL training hoặc tự thay trọng số model.

- Nhân viên kỹ thuật viết quy trình từ work order đã xử lý; hệ thống tự lưu candidate và nguồn. Nội dung cho cư dân cần người có thẩm quyền xác nhận điều kiện áp dụng trước publish. Tự lưu không đồng nghĩa tự phát hành nội dung chưa kiểm chứng.
- Reception tìm quy trình phù hợp và đề nghị khách tự thực hiện. Khách từ chối, không đủ điều kiện, thất bại hoặc phát sinh dấu hiệu cần chuyên môn thì chuyển onsite. Không bắt khách thử sửa mới được gọi nhân viên; không tự pause SLA.
- Giá lấy từ actual cost đã xác nhận, so sánh đúng phạm vi sửa/địa bàn/thời gian/tiền tệ. Tool thống kê trả khoảng tham khảo; Reception diễn đạt đúng số và điều kiện, không bịa giá khi thiếu mẫu.
- Quang phụ trách pipeline học và truy xuất; Chiến phụ trách schema/API/quyền/UI; Hoàng tích hợp Reception; Đông phối hợp kỹ thuật viên; Team 5 vận hành và kiểm thử.
- Đề xuất sửa `memory_candidates` và thêm 6 bảng: `repair_procedure_versions`, `ticket_self_help_attempts`, `repair_cost_observations`, `repair_price_reference_versions`, `repair_price_reference_samples`, `repair_price_estimates`. C13 triển khai sau khi chốt thiết kế; schema 148 bảng hiện tại chưa đổi.

## 5. Phân quyền thư mục — quy tắc bắt buộc

Tên Team 5 tạm thời là **Platform/QA/DevOps**; người phụ trách thực tế do dự án bổ nhiệm. Mỗi team tự viết unit/component test trong vùng của mình; Team 5 không viết thay toàn bộ test nghiệp vụ.

| Team | Được sửa trực tiếp | Không sửa trực tiếp / bàn giao cho owner |
|---|---|---|
| **Hoàng — Reception + Report agent** | `agent-reception/**`; **MỚI** `agent-report/**`, `server/src/reporting/**`, `server/tests/reporting/**`, `worker/src/jobs/reporting/**`; `agent-langgraph/**` khi cần reuse; `docs/teams/hoang/**` | Không sửa DB/migration, backend ticket/routing, UI, `shared/contracts/**`, server/worker entrypoint; gửi yêu cầu owner tích hợp |
| **Chiến — Backend + Frontend** | `server/src/**` và `server/tests/**` **trừ các folder reporting của Hoàng và knowledge/technical-tools của Quang**; `server/package.json`, `server/tsconfig.json`, `server/drizzle.config.ts`; `server/drizzle/**`; `server/scripts/**`; `scripts/generate-db-schema.py`, `scripts/generate-app-config.ts`; `app/**`; `shared/contracts/**`, `examples/vinhomes/**`, `docs/teams/chien/**`, `worker/src/jobs/business/**` | Không sửa runtime agent, worker entrypoint/deployment, root lockfile, thư mục Hoàng/Quang; đăng ký module/job qua yêu cầu tích hợp |
| **Đông — Coordination** | **MỚI** `agent-coordination/**`, `docs/teams/dong/**` | Không sửa `supervisor/**` (Docker); không sửa DB, API, tool implementation hoặc UI; technical agent runtime nằm ở team này |
| **Quang — Technical tools + RAG** | **MỚI** `server/src/knowledge/**`, `server/src/technical-tools/**`, `server/tests/knowledge/**`, `server/tests/technical-tools/**`, `worker/src/jobs/knowledge/**`, `docs/teams/quang/**` | Không sửa schema/migration, server entrypoint/auth/storage, package server hoặc root lockfile; dependency mới gửi Chiến/Team 5 |
| **Team 5 — Platform/QA/DevOps** | `.github/**`, `docker/**`, `charts/**`, `spire/**`, `supervisor/**`, `tests/**`; `worker/**` trừ `jobs/business/**`, `jobs/knowledge/**`, `jobs/reporting/**`; root `Dockerfile*`, `docker-compose*.yml`, `.env.example`, `.gitignore`, `.gitattributes`, `package.json`, `bun.lock`, `bunfig.toml`, `tsconfig.base.json`, formatter config; `scripts/**` trừ các file Chiến; `docs/teams/platform/**`, `docs/integration/**` | Không thay business rule/model prompt hoặc sửa migration để CI qua; không đổi hợp đồng API một mình |

Quy tắc bao phủ phần còn lại:

- `shared/**` ngoài `shared/contracts/**`, adapter `agent-*` ngoài vùng Hoàng/Đông, `desktop/**`, `agent-computer/**`, `assets/**`, `examples/**` ngoài Vinhomes và tài liệu chung: Team 5 bảo trì, mặc định giữ nguyên. Team chuyên môn gửi yêu cầu nếu cần đổi.
- `docs/KE_HOACH_HOAN_THIEN_5_TEAM.md`: Team 5 quản lý phiên bản kế hoạch, thay phân công phải có các owner liên quan thống nhất.
- `server/src/db/**`, catalog và generator: **Chiến là owner duy nhất**, kể cả bảng RAG, memory hay runtime. Quang/Đông/Hoàng sở hữu yêu cầu sử dụng chứ không tự sinh migration.
- `server/src/app.ts`, `server/src/index.ts`: chỉ Chiến nối module. `worker/src/index.ts`: chỉ Team 5 nối job; business job Chiến, ingestion job Quang và reporting job Hoàng xuất handler/factory nhận dependency, không tự chạy loop lúc import.
- Root `bun.lock`: Team 5 tổng hợp dependency từ workspace manifests và kiểm chứng `bun install --frozen-lockfile`; mỗi runtime riêng sở hữu manifest/lockfile nằm trong folder của mình. Không regenerate tất cả lockfile để sửa một dependency.
- Generated file (`app/src/routeTree.gen.ts` nếu được router tạo, `app/src/lib/generated/**`, `tables.ts`, `generated-invariants.sql`) phải sinh bằng công cụ owner, không sửa tay làm lệch nguồn. Kiểm tra đúng tên script/file hiện tại trước khi chạy.
- `.env`, secret, dữ liệu local và `.codex-artifacts/**`: không phải vùng bàn giao code của bất kỳ team nào.

Folder mới dự kiến:

```text
agent-reception/                 # Hoàng; LangGraph TypeScript service
  src/{graph,tools,adapters,persistence}/
  tests/
agent-report/                    # Hoàng; template/config/prompt/tool manifest, không tạo runtime thứ hai
  templates/
  schemas/
  prompts/
  examples/
  tests/
server/src/reporting/            # Hoàng; application service/metrics/tools/rendering qua ports
server/tests/reporting/          # Hoàng; unit/contract tests của reporting
worker/src/jobs/reporting/       # Hoàng; handler export báo cáo, Team 5 đăng ký worker
agent-coordination/              # Đông; Python service dùng AgentScope đã pin
  src/{supervisor,agents,groupchat,adapters,persistence}/
  tests/
shared/contracts/                # Chiến; OpenAPI/JSON Schema và fixture dùng chung TS/Python
server/src/platform/             # Chiến; memberships/scopes/workspaces/agent-builder
server/src/business/             # Chiến; tickets/routing/triage/dispatch/sla/approvals
server/src/runtime/              # Chiến; bindings/operation API, gateway và event ingress
server/src/storage/              # Chiến; file metadata, upload authorization, evidence
server/src/notifications/        # Chiến; notification service/outbox producers
server/src/knowledge/            # Quang; RAG/ingestion/ACL-aware retrieval
server/src/technical-tools/      # Quang; tool adapters qua service ports của backend
worker/src/jobs/business/        # Chiến; SLA/dispatch/notification job handlers
worker/src/jobs/knowledge/       # Quang; ingestion và tổng hợp giá job handlers
tests/platform-e2e/              # Team 5; kiểm thử xuyên dịch vụ
docs/teams/{hoang,chien,dong,quang,platform}/
```

Các folder trong cây này trừ folder cha hiện có đều là **đề xuất MỚI**. Chiến có thể tái sử dụng module hiện hữu qua import; không di chuyển hàng loạt code cũ để làm cây thư mục khớp tài liệu.

## 6. Backlog theo team, có dependency và đầu ra

Quy ước: H = Hoàng, C = Chiến, D = Đông, Q = Quang, P = Team 5. P0 là nền tảng bắt buộc; P1 là MVP chạy thật; P2 là hoàn thiện sau MVP. Dependency là điều kiện để **đóng task**, không ngăn làm test/mock hợp đồng trước.

### 6.1. Team Hoàng

Team Hoàng sở hữu hai năng lực: Reception cố định và Report agent do BQL tự tạo từ template. Không biến Report agent thành một node Reception hoặc một agent cố định dùng chung mọi BQL. Phân công ba thành viên tại `docs/teams/hoang/PHAN_CONG_3_THANH_VIEN.md`.

| Task | Mức | Công việc và đầu ra | Dependency | Nghiệm thu |
|---|---|---|---|---|
| H01 | P0 | Reception service tại `agent-reception/`; tái sử dụng mẫu LangGraph/AG-UI, cấu hình model, healthcheck, structured state và client backend | C01, P01 | Contract tests không cần model thật; người dùng không cấu hình lại system Reception thành agent tùy ý |
| H02 | P0 | Graph intake: nhận mô tả → hỏi thiếu facts → xác minh căn hộ/context qua API → tạo ticket có idempotency | H01, C03, C04 | Cư dân nhiều căn hộ phải chọn; từ chối unit không có quyền; gửi lại request không tạo ticket trùng |
| H03 | P1 | Tools: lấy context cư dân, tạo/xem/bổ sung ticket, submit assessment, lấy trạng thái, hỏi xác nhận; ảnh dùng file ID đã authorized | H02, C05, C07 | Tool schema rõ ràng; không tự UPDATE DB; không dùng role/tenant trong prompt làm quyền |
| H04 | P1 | Durable checkpointer, binding resolver, interrupt/resume, ownership và concurrency guard, restart recovery | C06, P02 | Restart vẫn resume đúng; user B không mở được thread A; duplicate resume chỉ xử lý một lần |
| H05 | P1 | Theo dõi ticket và thông báo tiến độ có recipient correlation; không giữ HTTP request chờ công việc nhiều giờ | C08, D04 | Hai ticket đồng thời không trả nhầm người; event lặp không lặp message |
| H06 | P1/P2 | Bộ eval tiếng Việt: thiếu thông tin, mô tả mơ hồ, dấu hiệu khẩn, ảnh không rõ, prompt injection; tối ưu hỏi và chi phí | P04, C05 | Có dataset/expected outcome theo policy, báo lỗi định lượng; không dùng model confidence như xác suất chuẩn |
| H07 | P1 | Reception self-help/giá: tra quy trình và estimate, hỏi đồng ý, hướng dẫn đúng version, ghi outcome, chuyển onsite | C13, Q07, Q08, H03, H04 | Khách từ chối được gọi kỹ thuật ngay; không hướng dẫn tự sửa khi không đủ điều kiện; thiếu dữ liệu giá phải hỏi thêm hoặc từ chối ước lượng |
| H08 | P0/P1 | Report agent template: config schema, bộ câu hỏi tạo agent, prompt, metric/output catalog, ví dụ preview và version | C01, C09 contract, D02 contract | BQL tạo agent riêng từ template mà không viết code; chỉ cấu hình phạm vi/tool được cấp; bản publish bất biến |
| H09 | P1 | Report tools/application service: validate kỳ/scope, lập yêu cầu, lấy dataset snapshot qua authorized ports, tính chỉ số xác định, source lineage và kết quả | C14, H08, C04/C05/C08 dữ liệu | Không SQL tùy ý/LLM tính KPI; đúng timezone/denominator/as_of; không rò dữ liệu hoặc tổng hợp ngoài scope |
| H10 | P1 | Nội dung báo cáo, render DOCX, job/export artifacts, preview, provenance và test chất lượng report; adapter đăng ký tool cho AgentScope | H09, C07, C09, C14, D08, P03 | Tạo agent → publish → gọi report → nhận file đúng quyền; số khớp nguồn, retry không nhân đôi, báo thiếu dữ liệu; DOCX render kiểm tra trước bàn giao |

Hoàng không chịu trách nhiệm tự xác định đội kỹ thuật cuối cùng hay ghi priority chính thức. Reception vẫn gửi cảnh báo theo emergency policy khi thiếu ảnh; không chờ upload hoàn tất mới báo sự cố đủ dấu hiệu khẩn.

### 6.2. Team Chiến

Chia nội bộ thành C-BE (backend/database), C-FE (frontend), C-INT (tích hợp). Một người tích hợp entrypoint/schema tại một thời điểm; frontend không tự đổi DTO.

| Task | Mức | Công việc và đầu ra | Dependency | Nghiệm thu |
|---|---|---|---|---|
| C01 | P0 | Đối chiếu catalog/schema/baseline và V3; OpenAPI/JSON Schema v1; state machine ticket; phân quyền action × role × scope; fixture | P01 phối hợp | Contract version, ví dụ lỗi/idempotency/pagination; ghi rõ nguồn thiết kế và gap chưa xử lý |
| C02 | P0 | Mô hình ownership BQL, cấu hình groupchat versioned và routing destination/binding; migration tiếp nối baseline | C01, D01 review | Hai BQL cùng đơn vị vẫn tách workspace cấu hình; không routing mơ hồ; schema có FK/UQ/hiệu lực thích hợp |
| C03 | P0 | Onboarding tenant/domain/site/zone/building/unit/resident; management/staff/customer grants theo scope; workspace ownership và service identity | C01, C02 | Không leo quyền bằng request ID; thu hồi account/grant chặn ngay; admin có audit; management không đọc ngoài scope |
| C04 | P1 | Ticket service/state machine, routing địa bàn, generation/version, work order, chuyển tuyến, idempotency và transaction outbox | C02, C03 | Đúng domain/BQL/groupchat; không có đích vào review; retry không tạo trùng ticket/work order |
| C05 | P1 | Engine triage theo V3: fact validation, policy selection, emergency floor, unknown handling, review, atomic apply, SLA cycles | C01, C04 | Không hạ mức tự động; phê duyệt đúng scope; concurrent assessment không ghi đè kết quả mới; trace pin policy |
| C06 | P0/P1 | Runtime gateway, execution principal/bindings/session operations, lease/fencing, memory access authorization, signed service context | C01, C03 | Client không tự chọn framework key; bắt đầu/resume/cancel/retry có idempotency; không lộ checkpoint/memory chéo user |
| C07 | P1 | File API, multipart/presigned upload, finalize xác minh size/hash/version/type/scan, evidence trước-sau và quyền download | C03, P02 | S3 object chưa xác minh không trở thành evidence hợp lệ; không nhận object key tùy ý; retry finalize an toàn |
| C08 | P1 | Dispatcher, staff shift/skill/capacity, offer/accept/ETA/timeout/reassign, SLA/escalation, notification/outbox consumers | C04, C05, P03 | Ưu tiên ảnh hưởng phân công thực tế; hai worker không double-assign; chống starvation; retry có DLQ và audit |
| C09 | P1 | Agent builder: CRUD draft, model/tool/knowledge grants, schema validation, preview, publish immutable release, rollback | C02, C03, D02, Q01 | BQL chỉ sửa agent của mình; publish pin tool/agent/group version; agent đang chạy không tự đổi theo draft |
| C10 | P1 | UI customer: Reception/ticket/trạng thái/ảnh; management: builder/groupchat/queue/review; staff: nhận việc/ETA/evidence; admin: domain/scope/policy | C03–C09 theo màn hình | Có loading/error/empty/permission states; UI dùng API thực; thao tác trái quyền bị backend từ chối |
| C11 | P2, cần xác nhận phạm vi | Service interruption và phạm vi thông báo; feedback/ticket review. Report chuyển sang H08–H10/C14, không gồm payment/refund | C04, C07, C08 | Thông báo đúng đối tượng; không tự triển khai chỉ vì schema có bảng |
| C12 | P1/P2 | Rà soát legacy writers, chuyển attachment/runtime mapping cần thiết; truy vấn tenant-aware; hardening invariant/migration | C06, C07, P04 | Không có hai nguồn trạng thái chính thức; dữ liệu cũ có kế hoạch chuyển đổi; API không còn dùng legacy role để cấp quyền |
| C13 | P0/P1 | Schema học kinh nghiệm, migration tăng dần; API/UI ghi procedure và actual cost, review/publish/revoke; eligibility/attempt/handoff, price reference và estimate audit | C01, C03, C04, C05, C06, C07, C08 | Có nguồn work order/tác giả/version; phân quyền duyệt; đồng bộ outcome/event/dispatch; tiền tính đúng, không phụ thuộc payment/refund; test tenant/concurrency |

C14 thuộc Team Chiến, là dependency backend riêng của Report agent:

| Task | Mức | Công việc và đầu ra | Dependency | Nghiệm thu |
|---|---|---|---|---|
| C14 | P0/P1 | UI/API tích hợp template Report vào builder C09; reporting data ports/repositories có scope; persistence request/source/artifact, contract, migration nếu thiếu; mount module Hoàng | C01, C03, C07; H08 contract | BQL preview/publish agent riêng; query scope do server resolve; source snapshot đọc nhất quán; download kiểm tra lại quyền; không bắt Hoàng sửa DB/UI |

### 6.3. Team Đông

**D08 thuộc Team Đông**, bên cạnh D01–D07:

| Task | Mức | Công việc và đầu ra | Dependency | Nghiệm thu |
|---|---|---|---|---|
| D08 | P1 | Nạp Report template/release do Hoàng cung cấp, bind tools có grant và thực thi AgentScope trong groupchat BQL | H08, D02, C06, C14 | Mỗi BQL có agent/run/context riêng; supervisor điều phối đúng instance; retry/cancel/timeout không công bố báo cáo trái quyền |

| Task | Mức | Công việc và đầu ra | Dependency | Nghiệm thu |
|---|---|---|---|---|
| D01 | P0 | Spike AgentScope: pin phiên bản, runtime service Python, kiểm chứng message/group orchestration, persistence và phục hồi; viết ADR | C01, P01 | Demo hai phiên độc lập; ghi rõ framework làm được gì và phần app phải tự viết; AG2 không bị đổi tên thành AgentScope |
| D02 | P0/P1 | Loader agent/group config đã publish; supervisor template hệ thống; tạo technical/service subagent từ cấu hình allowlist | C02, C06, Q01 | Không cần viết Python riêng cho mỗi BQL; cấu hình sai bị từ chối; không chạy arbitrary code do người dùng nhập |
| D03 | P1 | Orchestration plan/delegate/tool result/assessment proposal; tách team tasks/mailbox khỏi ticket state chính thức | D02, C04, C05, Q02 | Supervisor không tự ghi priority hoặc vượt thẩm quyền; kết quả có source run và task correlation |
| D04 | P1 | Durable run, checkpoint/state adapter, shared team context, interrupt/approval/resume, timeout/cancel/retry, fencing và outbox callback | C06, C08, P03 | Restart không gọi lại tác vụ ngoại vi đã hoàn thành; duplicate callback không double-complete; isolate theo ticket/generation |
| D05 | P1 | Human handoff và completion: yêu cầu review/evidence/approval, tổng hợp trả Reception, reopen theo generation mới | D03, D04, C07 | Không đóng việc chỉ dựa lời model; không resume generation cũ vào ticket đã reopen |
| D06 | P2 | Nhiều loại subagent/domain, kiểm soát chi phí và giới hạn vòng lặp, evaluation trace; update agent chỉ ảnh hưởng run mới | P04, C09 | Chặn loop, có budget/time limit; rollback version không làm mất audit |
| D07 | P1 | Supervisor yêu cầu nhân viên ghi và xác nhận procedure/chi phí sau xử lý, submit qua tool backend; trace nguồn và review workflow | C13, D03, D05, Q01 | Agent không giả nhân viên, tự duyệt quy trình hoặc đoán actual cost; retry không nhân đôi contribution |

Đông sở hữu **technical agent runtime**, còn Quang sở hữu các tool technical agent gọi. Memory chung chỉ chung trong scope team/phiên được cấp, không phải một global list dùng cho mọi groupchat.

### 6.4. Team Quang

| Task | Mức | Công việc và đầu ra | Dependency | Nghiệm thu |
|---|---|---|---|---|
| Q01 | P0 | Tool catalog: tên/version/input/output/side effects/quyền/timeout/idempotency; typed service ports; contract fixtures | C01, D01 | Hợp đồng dùng được từ Python/TS; không phụ thuộc gọi trực tiếp class nội bộ của framework |
| Q02 | P1 | Tool đọc lịch sử thiết bị/sự cố, tra hướng dẫn, đề xuất công việc/vật tư, tìm nhân viên phù hợp, yêu cầu phân công và evidence qua backend | C04, C07, C08, Q01 | “Đề xuất” khác “đã thực hiện”; mutation do backend authorize; không vượt capacity/approval; tool không tự cam kết vật tư chưa có dữ liệu |
| Q03 | P1 | Ingestion: source/version/hash, parse, chunk, embedding, lifecycle, retry, publish/tombstone; job handler | C07, P03 | Reingest không nhân đôi version/chunk; tài liệu xóa/thu hồi không còn truy xuất; failed job có lý do và retry |
| Q04 | P1 | Retrieval theo tenant/domain/workspace/document ACL trước khi chọn kết quả; citations đến version/chunk; retrieval audit | C03, C06, Q03 | Tài liệu không đủ quyền không đi vào prompt; không chỉ lọc sau top-k; câu trả lời không đủ nguồn phải thể hiện thiếu dữ liệu |
| Q05 | P1/P2 | Memory candidate/publication theo policy, sensitivity/retention và quyền; không tự biến mọi chat thành tri thức dùng chung | C06, Q04, D04/H04 | Memory cá nhân không xuất hiện trong group khác; thu hồi quyền có hiệu lực với cache; publish có provenance |
| Q06 | P1/P2 | Dataset/eval RAG, tiếng Việt, adversarial docs, latency/cost; tối ưu chỉ sau baseline | P04, Q04 | Báo recall@k/citation correctness/leakage; đổi embedding phải xử lý dimension/model version và reindex |
| Q07 | P1 | Procedure learning: chuẩn hóa và khử PII candidate, publish/ingestion theo review, retrieval có eligibility metadata, revoke/cache và provenance | C13, Q03, Q04, Q05 | Chưa duyệt không dùng cho cư dân; pin version; không chọn chỉ theo vector similarity; namespace đúng scope |
| Q08 | P1 | Tổng hợp giá: chọn mẫu độc lập, nhóm tương đồng, policy thuật toán có version, publish reference và tool estimate có cấu trúc | C13, Q01 | Chỉ verified actual cost; truy vết mẫu; mẫu thiếu/cũ/rút bị từ chối; không lộ chi phí riêng; không dùng LLM tính tiền |

Schema hiện dùng embedding vector dimension cố định và có trigger kiểm tra model. Q03/Q06 phải đối chiếu dimension thực trước khi chọn model; đổi model/dimension là yêu cầu schema cho Chiến, không tự bỏ constraint.

### 6.5. Team 5 — Platform/QA/DevOps

| Task | Mức | Công việc và đầu ra | Dependency | Nghiệm thu |
|---|---|---|---|---|
| P01 | P0 | Toolchain/manifest/lock, CI baseline, fixture runner, branch ownership, CODEOWNERS thực, documented local setup | Không | Fresh clone cài reproducible; CI kiểm tra đủ workspace/runtime riêng; không chỉ root workspaces vì agent runtime chưa thuộc root workspaces |
| P02 | P0/P1 | PostgreSQL/pgvector/btree_gist, runtime DB role, MinIO/S3, secret, network và framework storage namespace; backup/restore | C01, H01, D01 | Bootstrap local/staging từ đầu; runtime không có superuser/BYPASSRLS; backup restore thử thành công |
| P03 | P1 | Host worker handlers, retry/backoff/lease/DLQ, health/readiness, graceful shutdown, deployment Reception/Coordination/RAG jobs | C06, C08, Q03, D04 | Worker chết giữa tác vụ vẫn recover; nhiều replica không chạy đúp side effect; schema init framework không race |
| P04 | P1 | E2E/contract/security/load/evaluation harness; fixtures 2 BQL + 2 khách + 2 domain; dashboard trace/latency/cost/SLA | C01, các service P1 | Mục 12 đạt; có log bằng chứng và test negative cross-tenant/user; không gửi PII/secret nguyên văn vào telemetry |
| P05 | P1/P2 | Alert/on-call, backup retention, deployment canary/rollback, data migration rehearsal, runbook sự cố | P02–P04 | Có người xử lý alert, thử mất worker/storage/model, rollback app phù hợp version DB; không tự chạy down migration mất dữ liệu |
| P06 | P2 | Feedback/eval governance cùng team agent; load/quota/cost theo tenant; đóng gói demo domain thứ hai | H06, D06, Q06, C11 | Có báo cáo chất lượng theo version; quy trình duyệt release; chưa tự huấn luyện online từ feedback người dùng |
| P07 | P1 | E2E học kinh nghiệm và giá; vận hành ingestion/aggregate jobs, invalidation, theo dõi self-help outcome và estimated-vs-actual | C13, H07, D07, Q07, Q08, P04 | Kiểm chứng publish → retrieve → hướng dẫn/handoff; giá có nguồn; restart/retry/revoke an toàn; không đánh đồng giảm dispatch với thành công |

## 7. Quy tắc database, migration và quyền ghi

- Chiến là owner vật lý của **toàn bộ 148 bảng hiện tại và mọi bảng mở rộng**. Chỉ service backend được giao quyền mới thực hiện mutation nghiệp vụ. Runtime agent gửi command qua API.
- Bảng auth/scope/domain/workspace/agent config: Chiến; backend cấp quyền đọc cấu hình đã publish cho runtime.
- `tickets`, assessment/decision/review, SLA, dispatch, work order/assignment/approval, actual cost/price estimate: service nghiệp vụ Chiến. Hoàng/Đông/Quang gửi command, không tự ghi projection.
- Reporting application/tools/metrics/rendering thuộc Hoàng; persistence `report_requests`/`report_sources`, authorized dataset queries, DB schema và quyền thuộc Chiến C14. Application gọi ports được inject; không tự SQL hoặc bỏ qua quyền. Repository implementation C14 đặt ngoài `server/src/reporting/**`, ví dụ `server/src/business/report-data/**`.
- `agent_teams`, `team_members`, tasks/mailbox, `agent_runs`, context, execution principals và runtime/memory bindings: API runtime của Chiến là cổng ghi; Đông/Hoàng sở hữu adapter và đề xuất lifecycle. Cần quyền đọc/ghi theo đúng operation, không một generic CRUD endpoint mở toàn bộ.
- Knowledge/embedding/retrieval/memory candidate-publication: Quang triển khai repository trong module knowledge, luôn chạy với authorized context và quyền từ Chiến. Quyền publish memory và quyền sửa ACL vẫn do backend kiểm tra.
- Storage/evidence metadata: Chiến; Quang truy cập tài liệu qua authorized storage adapter. Team 5 vận hành bucket/lifecycle, không sửa trạng thái DB bằng script thủ công.
- Checkpoint/session storage nội bộ LangGraph/AgentScope: adapter Hoàng/Đông sở hữu setup theo **phiên bản framework đã pin**; Team 5 chạy setup. Không mặc định AgentScope tự tạo PostgreSQL tables hay tự định nghĩa supervisor. Ghi chính xác tên storage/table sau spike, không bịa tên framework table vào schema app.
- Không thêm `user_id` trực tiếp vào bảng do framework quản lý nếu adapter không hỗ trợ. Dùng binding app → identity/principal → user/workspace → opaque framework key, enforce ở gateway, kể cả list/history/delete/resume.
- Baseline `0000_grey_blockbuster.sql` đã publish: mọi thay đổi tiếp theo phải là migration tăng dần. Không ghi đè baseline, xóa journal, regenerate từ rỗng hoặc dùng `db:push` thay migration.
- Sửa `invariants.sql`/`generated-invariants.sql` sau baseline **phải có custom migration** cập nhật function/trigger; wrapper hiện chỉ nối SQL này ở baseline đầu tiên.
- Review constraint khi nâng cấp thực: nullable composite keys, khoảng hiệu lực fallback, ownership chuyển giao, append-only/retention, phê duyệt downgrade và hai quyết định liên tiếp trong transaction. Có test cho semantics nghiệp vụ, không chỉ kiểm tra SQL parse được.

## 8. Thứ tự triển khai và các mốc bàn giao

Không ước lượng ngày khi chưa biết số người/năng lực. Mỗi mốc đóng bằng kết quả chạy được; các team có thể song song sau khi contract của dependency đã chốt.

| Mốc | Công việc song song | Điều kiện kết thúc |
|---|---|---|
| M0 — Chuẩn hóa nền | C01/C02/C03/C06 thiết kế; H01; D01; Q01; P01/P02 | Contract v1 + fixture, ownership mapping, schema nâng cấp và các service healthcheck; hai runtime có persistence plan |
| M1 — Một luồng xuyên hệ thống | C04/C07, H02/H03, D02/D03, Q02 bản tối thiểu, P03 | Cư dân gửi yêu cầu → đúng BQL/group → tool backend → cập nhật trạng thái → trả đúng cư dân; ảnh lên MinIO thật |
| M2 — Ưu tiên và bền vững | C05/C08, H04/H05, D04/D05, Q03/Q04, P04 | Triage/SLA/dispatch chạy thật; restart/retry/isolation test qua; không còn mock trong đường chạy nghiệm thu |
| M3 — Builder, Reception, Report và học kinh nghiệm | C09/C10/C12/C13/C14, D02/D07/D08, H06–H10, Q05/Q06/Q07/Q08, P04/P05/P07 | Hai BQL có group riêng và tự tạo Report agent; report đúng scope/nguồn; self-help/giá có căn cứ; UAT Vinhomes |
| M4 — Hoàn thiện và mở rộng domain | C11 khi được xác nhận, D06, Q05/Q06, H06, P05/P06 | Domain thứ hai bằng cấu hình/adapter; interruption theo phạm vi được duyệt; release có runbook; Report MVP đã ở M3; không gồm payment/refund mặc định |

**MVP nghiệm thu = M0 đến M3**, bao gồm học quy trình tự sửa và giá tham khảo. C13 chốt contract/schema từ M0, xây ghi nhận dữ liệu ở M1–M2; Q07/Q08/H07/D07/P07 tích hợp và nghiệm thu ở M3. M4 không phải yêu cầu xây mọi bảng đã có. Không triển khai RL training cho hai luồng này.

## 9. Hợp đồng tích hợp v1 — thiết kế để các team bắt đầu thống nhất

Đây là hợp đồng **đề xuất cần C01 hiện thực thành schema và test**, không phải khẳng định endpoint đã tồn tại. Chiến xuất OpenAPI/JSON Schema để Python và TypeScript dùng cùng payload; không coi một file TypeScript type là đủ validate request runtime.

### 9.1. Context và envelope

Backend xác thực session người dùng hoặc service credential có giới hạn. Sau đó resolve context:

```json
{
  "contract_version": "1",
  "request_id": "opaque-id",
  "trace_id": "opaque-id",
  "idempotency_key": "opaque-id",
  "context": {
    "tenant_id": "tenant-uuid",
    "principal_id": "principal-uuid",
    "initiated_by_user_id": "application-user-id",
    "domain_id": "domain-uuid",
    "workspace_id": "workspace-uuid",
    "ticket_id": "ticket-uuid",
    "ticket_generation": 0,
    "binding_id": "binding-uuid",
    "run_id": "run-uuid"
  },
  "payload": {}
}
```

Các giá trị trên chỉ minh họa, không phải fixture ID hợp lệ. `users.id` hiện là application ID dạng text, không áp UUID cho mọi ID. Field không có trước khi tạo ticket/binding được bỏ theo schema từng operation; scheduled job có service principal và có thể không có initiated user. Không gán user giả để vượt NOT NULL.

`context` là kết quả backend resolve hoặc credential ký có audience/expiry; không copy nguyên JSON client gửi rồi tin. Phân biệt người khởi tạo, khách yêu cầu, principal đang thực thi và người duyệt; tuyệt đối không thay thế lẫn nhau để ghi audit.

Response có `request_id`, `status`, `data` hoặc `error` gồm `code`, `message`, `retryable`, `details` đã lọc. `accepted` chỉ nghĩa đã nhận, không nghĩa tác vụ hoàn thành. Các lỗi chuẩn: forbidden, not_found (theo chính sách che tài nguyên), validation_error, conflict/stale_version, routing_unresolved, policy_missing, rate_limited, unavailable. HTTP mapping và schema do C01 chốt.

Mutation có `idempotency_key`; lưu hash payload và kết quả. Cùng key khác payload phải conflict, không trả nhầm kết quả. Bản ghi hiện tại có expected version/generation; reject stale command. Retry không được tạo thêm external side effect.

### 9.2. Danh mục API/port cần chốt

| Nhóm/namespace dự kiến | Producer/owner | Consumer | Trách nhiệm |
|---|---|---|---|
| `/api/platform/*` | Chiến | UI | Membership, scope, workspace, agent/group config và publish |
| `/api/tickets/*` | Chiến | UI; agent qua tool gateway | Create/read/update facts, assessment, review, work order/assignment/evidence, lịch sử đúng quyền |
| `/api/files/*` | Chiến | UI, Reception, ingestion | Initiate/complete upload và authorized download; client không chọn bucket/key/tenant tùy ý |
| `/internal/runtime/*` | Chiến | Hoàng/Đông | Resolve binding, start/resume/cancel/result, task/mailbox, memory access; chỉ service auth và delegated quyền phù hợp |
| `/internal/tools/*` | Chiến mount, Quang/H tools đăng ký | Agent runtime | Tool allowlist + grant checks + idempotency; không expose raw SQL/shell hay toàn bộ MCP vô điều kiện |
| `/internal/knowledge/*` | Quang module, Chiến mount | Agent tools, UI API qua gateway | Query/ingestion/status với ACL, citation và retrieval log |
| Reception run endpoint | Hoàng | Gateway Chiến | AG-UI adapter + context đã xác minh, interrupt và stream lỗi có cấu trúc |
| Coordination run endpoint | Đông | Gateway/worker | Nhận destination/group release đã pin, ticket context tối thiểu, nhận lại resume event |
| Report template/catalog và report operations | Hoàng module, Chiến mount/UI/persistence | Builder, Report agent runtime Đông | Config/version, authorized snapshot, metrics, sources, trạng thái/artifact; không SQL tùy ý |

Đường dẫn cụ thể có thể đổi ở C01 trước khi freeze. Không đổi âm thầm sau khi team khác dùng; thay breaking phải tăng version và cung cấp contract migration.

### 9.3. Events và độ tin cậy

Tối thiểu có sự kiện tạo ticket, áp dụng triage, routing thành công/chưa xác định, yêu cầu dispatch, assignment offered/accepted/expired, yêu cầu approval, run waiting/completed/failed, evidence verified, ticket resolved/closed/reopened và notification requested. C01 chốt event names thành catalog, không hardcode mỗi team một kiểu.

Envelope: `event_id`, `event_type`, `schema_version`, `tenant_id`, `aggregate_id`, `aggregate_version`, `occurred_at`, `correlation_id`, `causation_id`, `payload`. Payload chỉ mang dữ liệu cần thiết; không phát ảnh bytes, secret hoặc raw checkpoint.

Producer ghi business change + `event_outbox` trong cùng transaction. Consumer dedup bằng inbox/idempotency; xử lý out-of-order theo aggregate version và có DLQ. Không hứa exactly-once qua mạng; cần at-least-once + idempotent effects. Không bắt buộc thêm Kafka/Redis khi work queue/outbox hiện có đáp ứng được.

### 9.4. Hợp đồng học kinh nghiệm và giá (C13)

C13 hiện thực operations: submit/review/publish/revoke procedure; kiểm tra self-help eligibility; offer/accept/decline/finish attempt; submit/verify/correct actual cost; build/publish/invalidate price reference; request price estimate. Không expose raw observation cho khách.

Quang cung cấp tools `find_self_help_procedure`, `estimate_repair_price`; Hoàng gọi backend operations cho lifecycle attempt. Tên là đề xuất phải đăng ký ở Q01. Eligibility trả allowed/reason/missing_facts/procedure_version; estimate trả status/range/currency/assumptions/inclusions/exclusions/reference_version/expiry. Context và quyền theo mục 9.1.

Events bổ sung: procedure submitted/published/revoked, self-help declined/succeeded/failed/stopped, actual cost verified/corrected/withdrawn, price reference published/invalidated. Mutation có idempotency; Quang viết ingestion/aggregation, Team 5 host; Chiến giữ nguyên tử dữ liệu nghiệp vụ + outbox. Việc cấp tool không cho phép agent tự duyệt nội dung.

### 9.5. Report agent — hợp đồng và luồng tạo agent

1. BQL chọn template Report hoặc mô tả nhu cầu; UI builder của Chiến dùng config schema và câu hỏi H08 của Hoàng để thu thập tên agent, loại báo cáo, bộ chỉ số, kỳ/timezone, phạm vi hợp lệ, định dạng và cách trình bày.
2. Backend xác minh owner workspace, metric/tool allowlist và quyền dữ liệu; preview trên dữ liệu trong scope. Publish qua agent_versions/releases hiện có, pin template/config/tool/metric versions. Không dùng prompt của BQL làm quyền truy cập.
3. Đông nạp cấu hình trong AgentScope như subagent do BQL tạo. Hoàng cung cấp nội dung chuyên biệt và tool báo cáo; không viết thêm scheduler/groupchat runtime tại `agent-report/`.
4. Report tool của Hoàng gọi authorized data/persistence ports của Chiến; ghi request, snapshot nguồn, as_of, metric_version. Backend chịu trách nhiệm consistent snapshot/watermark; không hứa as_of là time travel nếu không có lịch sử dữ liệu.
5. Metrics do code tính; LLM chỉ diễn giải, không bịa số hoặc biến thiếu dữ liệu thành 0. Job Hoàng tạo DOCX qua storage service Chiến; Team 5 host worker. Trả file qua permission-checked API, không public bucket URL.

MVP báo cáo: lượng ticket theo trạng thái/loại/kỳ, SLA, phân công và kết quả xử lý. Từng metric phải định nghĩa thời điểm tính, mẫu số, reopen/cancel, timezone và kỳ `[from,to)`. Có thể thêm actual cost/self-help khi C13 sẵn sàng; không coi đó là báo cáo doanh thu/payment. Báo cáo lịch định kỳ, email tự động và dashboard tùy biến ngoài MVP cho tới khi được xác nhận.

Tái sử dụng `report_requests`, `report_sources`, agent versions/releases và file metadata. Gap phải C14 rà soát: pin agent/template/config version, idempotency/cancel/retry, schema filters, quyền nguồn và source_message_id hiện NOT NULL cho báo cáo chạy không từ chat. MVP dùng nguồn message thật, không sinh message ID giả. Hoàng đề xuất; chỉ Chiến sửa catalog/schema/migration.

Ports tối thiểu: create request, fetch authorized dataset snapshot, persist sources/result, get status/cancel, authorize artifact. H09 chốt request/result schema với C14; tools có version và idempotency. API persistence chỉ cho phép lifecycle hợp lệ; không cấp generic SQL hoặc generic CRUD mọi bảng.

Nghiệm thu: hai BQL tạo hai Report agent từ cùng template với cấu hình riêng; số liệu khác theo quyền, file truy được nguồn; grant bị thu hồi giữa run/export chặn truy cập; dữ liệu rỗng khác lỗi truy vấn; prompt injection không mở rộng scope; retry không phát hành nhiều artifact chính thức.

### 9.6. Tool và RAG

- Tool descriptor: `name`, `version`, schema input/output, required permission/grants, side-effect class, timeout, retry policy và idempotency requirement. Không tự khởi tạo tool chỉ vì model nêu tên.
- Tool trả dữ liệu/operation ID có provenance. Technical agent và supervisor không báo “đã gọi nhân viên” nếu backend chỉ trả danh sách gợi ý.
- RAG query nhận query và authorized context; backend tính tập scope/ACL, không nhận danh sách quyền tự khai. Kết quả có document/version/chunk ID, citation, score và retrieval_run_id; score không phải độ đúng của câu trả lời.
- Prompt injection trong tài liệu/ảnh/chat là dữ liệu không đáng tin, không được nâng quyền hoặc thay system instruction. Citation phải kiểm tra lại quyền khi mở.

## 10. Hai luồng nghiệm thu cụ thể

### A. Rò nước tại căn hộ thuộc BQL A

1. Khách A đăng nhập; backend xác minh tenancy/căn hộ, Reception tạo binding của khách A.
2. Reception hỏi dữ kiện thiết yếu, tạo ticket và assessment có provenance; ảnh có thể được bổ sung sau.
3. Triage engine chọn policy theo domain/scope/category, chạy emergency floor, áp dụng quyết định và SLA cùng event transaction.
4. Routing chọn destination của BQL A và group version đã publish. Backend tạo team instance/ticket generation và runtime binding; template supervisor được Đông nạp vào instance này.
5. Technical subagent gọi tool Quang để lấy quy trình/RAG và đề xuất bước xử lý. Backend dispatcher chọn nhân viên đủ kỹ năng/ca/capacity theo queue; nhân viên nhận việc và cung cấp ETA.
6. Ảnh trước/sau được xác minh, người có quyền nghiệm thu; trạng thái ticket và thông báo đến đúng khách A. Chỉ đóng khi điều kiện nghiệp vụ đã đạt.

### B. Đặt vệ sinh tại căn hộ thuộc BQL B, chạy đồng thời

1. Khách B xác minh căn hộ và lịch dịch vụ; ticket dùng `request_kind` dịch vụ, mức severity theo policy (có thể `not_applicable`), không suy luận mọi dịch vụ là sự cố.
2. Routing chọn workspace/group version của BQL B. Supervisor cùng template với A nhưng instance, team state, binding và memory khác.
3. Subagent dịch vụ gọi tool lấy lịch/năng lực phù hợp; backend xử lý slot/phân công/xác nhận và ảnh hoàn thành.
4. Nếu nhân lực dùng chung với ticket A, dispatcher áp dụng policy ưu tiên và quy tắc công bằng; không âm thầm bỏ lịch vệ sinh đã cam kết.

Cả hai luồng phải chạy đồng thời khi restart một runtime, gửi callback lặp và cố dùng thread/file ID của khách khác. Domain thứ hai dùng customer-to-scope mapping riêng, không bắt buộc có `unit_id`; code điều phối chung không hardcode building để cấp quyền.

## 11. Cơ chế phối hợp để tránh sửa chồng file

- Baseline tích hợp là `develop`. Theo yêu cầu hiện tại, AI chỉ thao tác trên `develop` và không tự tạo/sửa nhánh khác. Mỗi team dùng clone/worktree do người điều phối chuẩn bị riêng; không để nhiều AI sửa cùng một working directory.
- Trước khi tích hợp, người điều phối lấy thay đổi mới, giải quyết conflict và chạy kiểm tra; commit chỉ chứa task của một owner. Không force-push snapshot của một team đè code team khác như thao tác thay project trước đây.
- Nếu sau này dự án cho phép feature branch/PR, Team 5 cập nhật quy trình và branch protection; tài liệu này không tự cấp quyền đổi chính sách Git hiện tại.
- Ghi yêu cầu ngoài scope tại `docs/teams/<team>/requests/<task-id>.md`: owner đích, lý do, chữ ký API/schema mong đợi, compatibility, fixture và test. Owner đích triển khai trong vùng của mình; không cần dừng các phần độc lập của task.
- Hợp đồng C01 có changelog; mỗi runtime pin version. Shared contract thay đổi cần owner và consumer review.
- Không tổ chức quyền chỉ bằng CODEOWNERS: đó là review routing. Team 5 cần cấu hình kiểm tra changed paths trong CI và branch policy nếu muốn enforce thật; chưa có bằng chứng các cơ chế này đã bật.
- Bàn giao task qua `docs/teams/<team>/handoffs/<task-id>.md`: done/partial/blocked, files, commands, outputs, API version, migration/env, known limitations. Không tự đánh dấu dependency xong vì chỉ thấy file tồn tại.

## 12. Tiêu chí hoàn thành và kiểm thử bắt buộc

| Nhóm | Kiểm thử bắt buộc | Owner |
|---|---|---|
| Ownership/RBAC | Hai tenant, hai BQL cùng đơn vị, staff ngoài assignment, customer nhiều căn hộ, role bị thu hồi; không IDOR | Chiến + Team 5 |
| Routing | Đúng domain/scope/category/hiệu lực; binding trùng/thiếu/expired; chuyển BQL đang chạy; không model guessing | Chiến |
| Session/memory | Sai user/thread/key, list/history/delete chéo quyền, hai ticket một khách, nhiều khách trong hai team, restart và revoke | Hoàng + Đông + Chiến |
| Triage/SLA | Unknown facts, emergency floor, human downgrade, missing policy, stale assessment, concurrent apply, reopen, pause/resume SLA | Chiến |
| Dispatch | Hai worker claim cùng job; capacity race; offer hết hạn; reassignment cần approval; fairness và deadline | Chiến + Team 5 |
| Storage | Sai tenant prefix, forged complete request, hash/size/version mismatch, object chưa scan, presigned expiry, orphan cleanup | Chiến + Team 5 |
| RAG | ACL trước truy xuất, revoked docs/cached result, injection, citation tới version đúng, embedding mismatch, reindex/delete | Quang |
| Agent builder | Draft/published pinning, unauthorized tool grants, group version mismatch, update giữa run, sandbox test trước publish | Chiến + Đông |
| Report builder và báo cáo | Hai BQL tạo agent riêng; scope/metric allowlist; kỳ/timezone/reopen; số liệu và nguồn khớp; snapshot/hash; missing khác zero; revoke giữa run/download; DOCX render; retry/cancel | Hoàng + Chiến + Đông + Team 5 |
| Reliability | Outbox atomicity, inbox dedup, event out-of-order, retry sau timeout, lease fencing, model/storage outage | Team 5 + owner service |
| Học kinh nghiệm/self-help/giá | Quy trình chưa duyệt, không đủ điều kiện tự sửa, khách từ chối/thất bại, revoke giữa phiên, giá thiếu/cũ/trùng/revision, không lộ mẫu riêng, khoảng giá khớp tool | Quang + Chiến + Hoàng + Đông + Team 5 |

Lệnh nền hiện có, chạy từ root với Bun đã cài và cấu hình đúng:

```powershell
bun install --frozen-lockfile
bun run generate:app-config
bun run typecheck
bun run --cwd server db:check
bun run --cwd server db:verify
```

`db:check`/`db:verify` không thay database thật. `db:verify` hiện kiểm thử schema trên PostgreSQL WASM, không thay PostgreSQL integration suite. Test real DB bắt buộc `TEST_DATABASE_URL` trỏ database test riêng và baseline/migration đã áp dụng; không fallback sang `DATABASE_URL` production. Team 5 chuẩn hóa lệnh contract/e2e cho các runtime mới ở P01/P04; tài liệu không đưa lệnh giả khi package chưa tồn tại.

Mỗi PR/commit tích hợp cần: typecheck/lint phù hợp package; unit test hành vi mới; contract test producer/consumer; PostgreSQL integration khi đổi SQL/concurrency; E2E cho mốc sản phẩm; migration forward trên DB test; log không lộ secret. Không bỏ test lỗi hoặc đổi expectation cho vừa implementation mà chưa đối chiếu nghiệp vụ.

Ngưỡng vận hành cần chốt ở M0: số tenant/user/agent đồng thời, p95 latency từng API/run, throughput, timeout, token/cost quota, SLA domain, RPO/RTO và thời hạn lưu ảnh/memory. Team 5 đề xuất theo đo tải; chủ sản phẩm duyệt. Chưa có số liệu thì báo thiếu, không tự tuyên bố “production ready”.

## 13. Mẫu prompt giao cho AI của thành viên

```text
Bạn làm việc trong project AI Platform Builder, nhánh develop.
Đọc docs/KE_HOACH_HOAN_THIEN_5_TEAM.md trước khi sửa code.
Nếu task học kinh nghiệm/giá, đọc thêm docs/THIET_KE_HOC_KINH_NGHIEM_SELF_HELP_GIA.md.
Team của tôi: <Hoàng | Chiến | Đông | Quang | Platform>.
Task được giao: <H01/C04/D02/Q03/P02...>.
Phần được giao trong task nếu có: <mô tả>.

Kiểm tra code và dependency thực tế; không coi kế hoạch là chức năng đã tồn tại.
Chỉ sửa vùng sở hữu của team, tuân thủ ngoại lệ đường dẫn và hợp đồng chung.
Không sửa nhánh khác, force-push, chạy migration lên DB thật hay đưa secret vào Git.
Nếu cần thay file của team khác, ghi integration request với interface và test,
rồi tiếp tục phần độc lập trong phạm vi của mình. Không tạo production mock.
Triển khai task tới tiêu chí nghiệm thu; chạy test phù hợp và ghi handoff.
Báo chính xác phần hoàn thành, chưa kiểm chứng và dependency còn thiếu.
```

Định nghĩa “hoàn thiện project”: các mốc đã chọn có luồng thật qua UI/API/runtime/storage, phân quyền đúng, dữ liệu bền vững, retry an toàn và bằng chứng test; không chỉ đủ file/folder hoặc đủ 148 bảng.
