# Reception API, RAG và tình trạng tích hợp — 02/10/2026

## Mốc kiểm tra

Fetch remote hiện tại: beHuy `6b8e166`, Team Quang `6094b53`, `phuc_rag` `d68b9c7`, Team Hoàng `975565a`, Factory `649d3f0`, Đông `fec1746`, DEV-3 `9077390`, DEV-5 `b1f1684`, checkpoint `56ca8f3`. Các mốc Factory/Đông không đổi so với báo cáo trước. Không merge hoặc sửa runtime/database trong lượt này; giữ nguyên hai file nghiệp vụ/test đang được sửa trong workspace.

## 1. beHuy tổ chức API Reception như thế nào?

### Cổng operation dành cho agent

- `POST /internal/reception/operations/execute`: nhận `operation`, `input`, `context`, `idempotency_key`; chạy nghiệp vụ và lưu receipt PostgreSQL.
- `POST /internal/reception/operations/reconcile`: tra kết quả đã ghi khi caller không chắc request trước đã hoàn tất; không thực hiện lại nghiệp vụ.

14 operation được khai báo trong `services/vinhomes-api/src/vinhomes_api/v3_reception_operations.py`:

| Nhóm | Operation |
| --- | --- |
| Danh tính/nơi ở | `get_verified_resident_context` |
| Nháp và assessment | `create_ticket_draft`, `update_ticket_incident`, `submit_ticket_assessment` |
| Tìm BQL/bàn giao | `resolve_management_destination`, `handoff_ticket` |
| Theo dõi Supervisor | `register_supervisor_wait`, `get_supervisor_event` |
| Phản hồi cư dân | `append_ticket_information`, `respond_supervisor_interaction`, `request_ticket_cancellation` |
| Trạng thái/khẩn cấp | `get_ticket_status`, `escalate_emergency` |
| Self-help | `process_self_help` — hiện trả 501, chưa nối RAG/eligibility |

Draft chưa phải ticket. Handoff tạo ticket/team/message V2; waiting hiện là polling. Idempotency đối chiếu operation/input, receipt được lưu; context tenant/principal không tự cấp quyền, được đối chiếu danh tính server. Không suy ra agent có thể gọi chỉ bằng một token bất kỳ.

### API tài nguyên và trao đổi V2

- `/resident/context`, `/resident/chats`, messages, ticket-drafts, tickets/progress, ảnh upload, approvals/plans và notifications là các tài nguyên liên quan.
- Reception V2: `POST /api/domains/vinhomes/resident/reception-supervisor/messages`; `GET /api/domains/vinhomes/resident/reception-supervisor/tickets/{ticket_id}/results`.
- Supervisor: `GET /api/domains/vinhomes/operations/resident-cases/reception-supervisor/teams/{team_id}/inbox`; `POST /api/domains/vinhomes/operations/resident-cases/reception-supervisor/results`.
- Đây là API validate/persist; không tự chạy LLM/Supervisor. Proxy Hono dành cho Reception được nhắc trong tài liệu beHuy nhưng chính tài liệu ghi chưa thuộc commit API-only.

## 2. Các chỗ chưa khớp với Reception Team Hoàng

1. `agent-reception/src/tools/backend.py` gửi service `Authorization: Bearer ...`. `_actor_id` trên beHuy remote hiện dùng demo/dev actor hoặc chuyển tiếp **cookie** sang Hono auth; chưa có nhánh xác thực service bearer và delegation/binding tương ứng. Đường gọi trực tiếp chưa khớp auth.
2. `tools/validation.py` bên Hoàng đòi response `kind=success` + `value`, hoặc `accepted`/`failure`. beHuy `execute` trả kết quả nghiệp vụ phẳng + `replayed` + `agentContext`; `reconcile` trả `found/status/result`. Cần chốt envelope/adapter; cùng path chưa có nghĩa client parse được.
3. RAG Quang trả `hits` + `insufficientSources`. `graph/intake.py` bên Hoàng nhận nội bộ `kind=sufficient`, `answer`, `citations` có `documentId/version/chunkId`. Đây là hai tầng khác nhau: cần adapter truy xuất và bước Reception tổng hợp câu trả lời có nguồn; không truyền response RAG nguyên xi vào `valid_knowledge`.

Các kết luận trên dựa trên source hai nhánh; chưa chạy request xuyên hai dịch vụ trong lượt này. Chi tiết lỗi evidence Supervisor ở báo cáo `REVIEW_BEHUY_2026-10-02.md` vẫn cần xử lý khi tích hợp.

## 3. RAG Team Quang: đã có pipeline, chưa mount production

Nguồn `server/src/knowledge/**` trên `dev_TeamQuang` và handoff ngày 01/10:

```text
Markdown + metadata/phạm vi
  → chia chunk theo heading
  → embedding text-embedding-3-large / 1536 chiều
  → PostgreSQL document/version/chunk/vector
Câu hỏi + AuthorizedContext do backend cấp
  → lọc scope/ACL trong SQL trước xếp hạng
  → tìm vector + từ khóa tiếng Việt có/không dấu, gộp RRF
  → ngưỡng similarity 0.35 và thông tin nguồn/độ tin cậy
  → hits + retrievalRunId → Reception viết câu trả lời có trích dẫn
```

Contract `search_knowledge` v1.0.0: `POST /internal/knowledge/search`, body `{query, topK?, scopeId?}`. Không nhận tenant/user/role tùy ý. Có 409 `scope_required` để hỏi lại khi nhiều nơi ở; nguồn không đủ trả `insufficientSources=true`. Tool trả đoạn tài liệu, không trả lời thay Reception. Similarity không phải xác suất câu trả lời đúng.

**Đã có code:** ingestion/version/hash/tombstone, chunk metadata, OpenAI embedding adapter, hybrid retrieval, audit `retrieval_runs/retrieval_hits`, JSON Schema handoff, route factory, CLI dev và worker handler factory.

**Còn cần ghép:**

- `createKnowledgeRoutes` chưa được mount trong `server/src/app.ts`/`index.ts` của nhánh Quang; worker ingestion chưa đăng ký ở worker entrypoint.
- Backend implement `AuthorizeKnowledgeSearch`: xác thực caller/delegation, agent knowledge grant, cư dân/tòa, ancestors scope, tenant/workspace/run/principal/binding thật.
- Catalog/domain/knowledge base và file registration thật; thay dữ liệu `rag-dev-*`. CLI dev có tạo runtime audit fixtures với FK checks tắt, không dùng làm bootstrap production.
- Chốt ACL default: Quang cho phép trong scope khi không có allow ACL, deny khớp thì chặn; API knowledge của beHuy yêu cầu allow ACL. Hai policy chưa thống nhất.
- Ingestion hiện thêm scope nhưng chưa gỡ scope cũ khi tài liệu đổi phạm vi; phải xử lý trước khi nghiệm thu thu hồi quyền tài liệu.
- Q07/Q08 self-help/giá còn chờ phần C13 theo handoff; tìm tài liệu thông thường không thay quy trình đủ điều kiện/đồng ý/an toàn/giá.

Trên beHuy `server/src/knowledge/` chỉ có `.gitkeep`. `GET /knowledge/search` của FastAPI là tìm full-text cho Operations, dùng management/staff scope và ACL; **không phải** RAG hybrid cho cư dân của Quang và không thay thế được endpoint POST nói trên.

## 4. Bằng chứng

Trong lượt này chạy 7 file test knowledge (embedder, eval-metrics, markdown, pipeline, routes, source-directory, source-metadata): **62 pass, 0 fail, 167 assertions**. Chạy trên checkout DEV-3 có thư mục knowledge trùng source nhánh Quang (đã đối chiếu diff). Đây là unit/contract với dependency test; chưa gọi embedding thật hoặc chạy `pg-store.integration.test.ts`.

Handoff Quang ghi đã ingest 118 tài liệu/348 chunks và eval 93 câu, recall@1 82,4%, chặn 13/14 câu lạc đề. Đó là số liệu team ghi ở lần chạy trước, chưa tái đo trong lượt này; không dùng làm tỷ lệ chất lượng production.

Factory/DEV1–5 chưa có commit mới so với `TIEN_DO_OPENBOT_SUPERVISOR_AGENTSCOPE_2026-10-02.md`. Kết quả 63 test Factory và Coordination 330 pass/6 fail/1 skip là kiểm thử lượt trước, không chạy lại vì source không đổi.

## 5. Thứ tự triển khai đề nghị

1. Chiến/beHuy + Hoàng chốt auth delegation và envelope execute/reconcile; có test consumer gọi API thật trước khi ghép UI/LLM.
2. Chiến + Quang mount RAG và implement authorization/scopes/grants/audit IDs thật; thống nhất ACL và xử lý scope bị thu hồi, dùng runtime role hạn chế.
3. Hoàng nối `search_knowledge`, xử lý 409/chưa đủ nguồn, tổng hợp đáp án và citations đúng contract; nghiệm thu FAQ cư dân đúng tòa trước.
4. Chiến + Hoàng + Đông nối handoff V2/plan/decision/result vào durable inbox/worker; giữ quyền nghiệp vụ ở backend, sửa các lỗi đã review.
5. Hoàn thiện AgentScope loader/tools, checkpoint và DEV-5 production composition; nối Factory publish khi cần tạo subagent. FAQ Reception + RAG có thể nghiệm thu độc lập trước khi toàn bộ Factory/Supervisor hoàn tất.

Chưa merge tự động hoặc dùng mock/demo thay bằng chứng nghiệm thu theo yêu cầu kiểm tra này.
