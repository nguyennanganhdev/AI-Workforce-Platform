# Bản đồ dự án và trạng thái tích hợp

Ngày rà soát: 15/10/2026.

## Phạm vi và cách đọc kết quả

Rà soát cấu trúc repository, entrypoint, router, các luồng nghiệp vụ chính,
frontend, composition, migration, tài liệu và cấu trúc test. Đây là bản đồ kiến
trúc qua đọc code, không phải xác nhận đã đọc từng dòng hoặc kiểm thử mọi file.
Không đọc hay ghi lại giá trị bí mật trong `.env`.

Trạng thái lúc rà soát: nhánh `frontend/huynx`, HEAD `5f818fd`; code ngoài
`examples/web_ui` đã được đồng bộ vào working tree từ `dev_TeamHoang` commit
`2f460f6`. UI được giữ lại và đã bỏ các dòng agent trong sidebar. Đây là working
tree kết hợp hai nguồn, chưa phải một commit tích hợp hoàn chỉnh.

`rg --files` đếm 1.651 file dưới `platform_VP/agentscope` theo ignore rules hiện
tại: 812 file dưới `src/agentscope`, 307 file dưới frontend/src, 324 file dưới
tests, 93 file dưới docs. Các số này gồm tài liệu/assets nếu nằm trong thư mục
tương ứng, không phải số test case hoặc số file đã đọc chi tiết.

## 1. Ba lớp sản phẩm

1. **AgentScope framework:** agent loop, model adapters, messages/events,
   toolkits, permissions, MCP, skills, workspace, RAG, middleware, pipeline,
   realtime/TTS, console/TUI.
2. **Agent Service:** FastAPI nhiều tài khoản/phiên; cung cấp chat, quản lý agent,
   credential, session, workspace, knowledge base, lịch và channel.
3. **AI Workforce:** Leader cố định, Builder tạo agent nghiệp vụ, publish,
   điều phối nhóm, shared context, ticket và các module workflow/API đối tác.

Không phải mọi module lớp 3 đều được lắp vào ứng dụng local đang chạy.

## 2. Điểm khởi chạy và lưu trữ

- [compose.yaml](../compose.yaml): app, Redis, PostgreSQL, MinIO và minio-init.
- [Dockerfile](../Dockerfile): cài package local, chạy Alembic rồi khởi động
  `examples/agent_service/main.py`.
- [main.py](../examples/agent_service/main.py): cấu hình `RedisStorage`,
  `RedisMessageBus`, auth/business SQL, shared context SQL khi có SQL URL,
  `LocalWorkspaceManager`, S3 blob store và Qdrant in-memory.
- [create_app](../src/agentscope/app/_app.py) đăng ký router;
  [_lifespan.py](../src/agentscope/app/_lifespan.py) mở các service/worker/dispatcher.
- Frontend: [App.tsx](../examples/web_ui/frontend/src/App.tsx), React/Vite,
  mặc định gọi API cổng 8000 qua `src/api/client.ts`.
- `examples/web_ui/backend` là Express health endpoint, không phải agent runtime.

Redis giữ dữ liệu agent/session/credential và message bus ở composition local.
PostgreSQL giữ auth, nghiệp vụ và shared context; các module Workforce mở rộng
cũng có SQL repositories riêng. MinIO lưu object/file. Workspace có Docker
volume. Git reset không xóa các dữ liệu này.

Qdrant local được tạo với `location=":memory:"`; không nên suy ra vector index
knowledge base sẽ tồn tại qua restart giống dữ liệu PostgreSQL/MinIO.

## 3. Luồng chat trực tiếp

`ChatPage → ChatViewport → useMessages → POST /chat/ → ChatService → Agent`.

UI mở SSE `/sessions/{session_id}/stream` và tải lịch sử bằng API session.
Backend kiểm tra danh tính, resource ownership, lock và trạng thái phiên;
ghép model, credential, workspace, tool và middleware trước khi chạy agent.

Agent trong `src/agentscope/agent/_agent.py` thực hiện reasoning/acting,
kiểm tra permission, xử lý xác nhận, gọi công cụ, lưu context và phát event.
Model adapter gọi nhà cung cấp. Model fallback được cấu hình theo session;
lỗi gọi model chính sau retry có thể chuyển sang fallback. Không suy ra mọi
lỗi giữa chừng của stream đều được phục hồi tự động.

Agent là cấu hình hành vi; session là cuộc hội thoại và cấu hình chạy; model là
bộ suy luận; credential là key/base URL. Tạo agent không tự tạo một model mới.

## 4. Agent thường và agent Workforce

### Tạo nhanh trên UI hiện tại

`QuickAgentDialog → POST /agent/`: lưu tên, system prompt, context/ReAct/invite
config. Model được gắn ở session. AgentData mặc định có `system_role=business`,
`lifecycle_state=draft`, `execution_mode=None`.

### Builder/Leader phía backend

[_workforce_console.py](../src/agentscope/app/_router/_workforce_console.py)
cung cấp `/workforce/console/builder/*`, quản lý agent nghiệp vụ,
`/leader/bootstrap` và `/leader/tickets`.

Builder có hội thoại, đề xuất agent, lựa chọn MCP/knowledge, sinh skill,
đánh giá và publish. Leader bootstrap tạo/tái sử dụng bản ghi có vai trò hệ
thống `leader`; đặt tên agent thường thành “Leader” không tạo quyền này.

[_toolkit.py](../src/agentscope/app/_service/_toolkit.py) áp dụng:

- Chỉ Leader hệ thống được cấp TeamCreate/TeamDelete và quyền mời thành viên.
- Agent được mời phải là business, published, invitable và có mô tả.
- Worker trong nhóm dùng TeamSay; business agent standalone không có team tools.
- Agent có execution contract dùng MCP bindings đã chọn; Leader không kế thừa
  MCP nghiệp vụ của worker.

**Lệch UI–backend cần xử lý:** GroupChatDialog hiện cho chọn agent bất kỳ làm
trưởng nhóm và bật invitable cho thành viên, nhưng không đảm bảo vai trò Leader
hệ thống hoặc publish. Do đó không thể kết luận tạo nhóm sẽ chạy chỉ từ việc
tạo session thành công. Frontend hiện chưa tìm thấy lời gọi `/workforce/console`.

## 5. Shared context và điều phối

TeamSay, HandoffDispatcher, WakeupDispatcher và middleware phối hợp các agent.
Shared context giữ fact/constraint/decision/output, task, bằng chứng nguồn,
handoff, pending question và ngân sách. Có cách ly task/references/isolated,
summary có dẫn nguồn, đo token, chống lặp và durable replay.

Worker có thể hỏi đồng đội; đề xuất hỏi khách phải qua reply owner. Hoàn tất
trao đổi nội bộ không đồng nghĩa đóng ticket nghiệp vụ.

Xem [RUNTIME_COLLABORATION](workforce/RUNTIME_COLLABORATION.md) và
[SHARED_CONTEXT](workforce/KE_HOACH_SHARED_CONTEXT.md), đối chiếu runtime/tests
khi checklist cũ khác phần trạng thái mới.

## 6. Ba nhóm API nghiệp vụ cần phân biệt

| Nhóm | Trạng thái local đã quan sát | Ý nghĩa |
| --- | --- | --- |
| `/partner/*`, `/tickets`, `/memories/*` | Có trong OpenAPI | Area Platform: mapping cư dân, ticket theo area, memory có duyệt |
| `/workforce/console/*` | Có trong OpenAPI | Builder và Leader dùng trực tiếp trên platform |
| `/workforce/v1/*` | Không có trong OpenAPI | Workflow/customer/provider-event API cần composition mở rộng |

OpenAPI local có 102 path tại thời điểm rà soát. Có route không có nghĩa mọi
endpoint đã được chạy end-to-end hoặc đã có credential/tool phù hợp.

`create_app` chỉ mount nhóm mở rộng khi truyền `workforce_bootstrap`.
`examples/agent_service/main.py` hiện không truyền nó.
`PhaseCRuntimeDependencies` yêu cầu các adapter auth, Leader, MCP, evaluator,
release, shared-context model resolver... `LeaderTurnRunner` là interface cần
engine được deployment cung cấp, không phải một implementation gọi model sẵn.

Trong `app/workforce`: contracts định nghĩa DTO/ports; foundation lo scope,
transaction/job; registry có event protocols; builder có proposal/capability
selection; lifecycle lo evaluation/release; orchestration quản lý workflow,
checkpoint/continuation; execution lo policy/approval/idempotency/MCP/external
operations; assets quản lý tài sản; integrations ghép các module.

## 7. Frontend thật và demo

- App routes: chat, agents, schedule, channel, credential, MCP, skill, knowledge.
- `pages/mock`: kịch bản và playback; không gọi backend để tạo câu trả lời.
- `session-office/preview-adapter.ts`: roster từ agent/session nhưng
  `motion: 'demo'`, phase idle. Chưa phản ánh trạng thái thực thi live.
- Có component BuilderPanel, TicketTimeline, EventChannelsPanel và transport
  Workforce; sự tồn tại của component không chứng minh nó được mount vào App.
  BuilderPanel hiện có demo dùng fakeClient.
- SearchPalette tìm mọi agent trong danh sách đã tải, nhưng session chỉ thuộc
  agent đang mở. Đây chưa phải tìm kiếm tất cả session của tài khoản.
- Sidebar đã bỏ dòng agent theo yêu cầu, giữ demo và group conversations.

## 8. Test và vận hành

Repository có tests cho framework, auth/storage, chat, tool permissions,
team/shared context và Workforce. Có test dùng mock/in-memory, có test cần SQL
hoặc provider; không được đánh đồng số test với mức hoàn thiện production.

Lần cập nhật backend ngay trước rà soát: 66 test thuộc team_turn, chat_consent,
team_collaboration, service_wakeup_dispatcher đạt. Backend health OK; UI HTTP
200. Chưa chạy toàn bộ 324 file tests và chưa kiểm thử toàn bộ sản phẩm với
model/MCP thật trong lần rà soát này.

Các điểm lệch đã đọc thấy, chưa sửa:

1. `scripts/workforce/check_phase_d_environment.py` yêu cầu migration head
   `0012_workforce_assets`, trong khi chuỗi source đã tới
   `0015_shared_context_backfill`.
2. `.github/workflows/workforce-phase-d.yml` ở gốc repo cũng so phiên bản restore
   với `0012`; runbook event delivery còn nhắc `0011`.
3. Workflow bên trong `platform_VP/agentscope/.github/workflows` không được
   GitHub tự nhận như workflow gốc của repository này.
4. Image MinIO trong compose không pull được ở lần chạy trước. Backend mới đã
   chạy bằng `up -d --build --no-deps app` với MinIO cũ đang healthy; deploy từ
   máy trống vẫn cần xử lý vấn đề image đó.
5. Nhiều README vẫn ghi “chưa triển khai” dù thư mục đã có source/test; không
   dùng riêng các dòng này để kết luận trạng thái hiện hành.

## 9. Hướng tích hợp phù hợp với trạng thái hiện tại

Giữ giao diện đang chọn, nối nghiệp vụ đã có theo từng luồng:

1. Chốt chat trực tiếp và session thực trước; giữ demo có nhãn rõ.
2. Nối Builder prepare/publish và danh sách agent nghiệp vụ vào UI.
3. Dùng Leader bootstrap/tickets thay việc cho agent thường tự làm trưởng nhóm.
4. Kiểm thử published specialist, MCP thực, approval và shared context.
5. Đưa event backend vào adapter Văn phòng.
6. Nếu cần API đối tác mở rộng, hoàn thiện deployment adapters và
   WorkforceBootstrap, kiểm thử riêng với SQL, provider-event và continuation.

Đây là thứ tự đề xuất, không phải các thay đổi đã thực hiện trong lần đọc code.
