# Ghép Reception vào chat cư dân — bàn giao 02/10/2026

Gửi: Team Hoàng (chủ `agent-reception/`), Team Đông, Team Quang, Team 5.
Trạng thái: chạy được đầu-cuối trên PostgreSQL thật với model stub; **chưa chạy với LLM thật** vì repo chưa có key.

## Vì sao có thay đổi trong `agent-reception/`

Graph (`src/graph`) và bộ tool có kiểu (`src/tools`) chưa có phần ghép thành service, và hợp đồng của graph
khác backend ở ba điểm: xác thực (service bearer so với cookie cư dân), vỏ kết quả (`kind/value` so với kết quả
phẳng), và mô hình ticket (graph tạo ticket ngay ở bước draft; backend chỉ tạo ticket lúc handoff).
Theo quyết định của Chiến: **hợp đồng backend là chuẩn, lớp chuyển đổi nằm ở phía Reception.**

Phần thêm mới nằm trọn trong `agent-reception/src/runtime/` và `agent-reception/tests/runtime/`; không sửa
`src/graph`, `src/tools`, `src/prompts`. Bộ test sẵn có của team vẫn 332 đạt / 5 lỗi như trước.

## Luồng

```text
Cư dân nhắn (resident-app) → POST /resident/chats/{id}/messages (backend, commit)
  → backend mở một run cho tin nhắn đó và ký token ủy quyền (10 phút)
  → backend gọi POST {RECEPTION_URL}/v1/turns  (Bearer service token, body kèm delegation)
  → runtime chạy một lượt graph theo thread = channel, mọi lời gọi dưới đây dùng Bearer <token ủy quyền>
      policy:    POST /internal/reception/policy/evaluate        (backend quyết định)
      operation: POST /internal/reception/v1/execute
      tri thức:  POST {KNOWLEDGE_URL}/internal/knowledge/search   (khi được cấu hình)
  → runtime ghi câu trả lời: POST /internal/reception/chats/{id}/replies
  → backend đóng run (token hết hiệu lực ngay)
  → resident-app đọc hội thoại từ backend như cũ
```

Runtime không chạy được thì backend tự ghi một câu trả lời hướng cư dân dùng biểu mẫu.

## Ánh xạ operation (`runtime/backend.py`)

| Graph gọi | Backend thực hiện | Ghi chú |
|---|---|---|
| `create_ticket_draft` | `create_ticket_draft` (draft rỗng) | Graph nhận `ticket_id` = id draft, mã `DRAFT-…`, version `0` |
| `get_verified_resident_context` | `get_verified_resident_context` + `update_ticket_incident` (căn hộ) | Nhiều căn hộ thì hỏi lại; thiếu tên/số điện thoại xác minh thì báo cư dân |
| `update_ticket_incident` | `update_ticket_incident` | Model đề xuất danh mục dịch vụ từ catalog backend; đề xuất sai thì chuyển người xem xét |
| `submit_ticket_assessment` | `submit_ticket_assessment` | Mức ưu tiên là đề xuất của model; khẩn cấp do policy backend quyết định |
| `resolve_management_destination` | cùng tên | Có BQL phụ trách là đủ; chưa có Supervisor vẫn đi tiếp |
| `handoff_ticket` | `handoff_ticket` với `plan_required=false` | Backend tạo ticket; có Supervisor thì tạo team + message V2 |
| `register_supervisor_wait` | cùng tên khi có team | |
| `get_ticket_status` | cùng tên | `closed`/`cancelled` mới là hoàn tất |
| `append_ticket_information`, `request_ticket_cancellation` | message V2 khi ticket có team | Không có team: thông tin nằm trong chat; hủy chuyển người xem xét |
| `escalate_emergency` | cùng tên khi đã có ticket | Chưa có ticket: đánh dấu để ticket tạo ra ở mức critical |
| `process_self_help` | không gọi (backend trả 501) | Trả `unavailable`, graph mời hỗ trợ trực tiếp |
| `respond_supervisor_interaction`, `get_supervisor_event` | chưa hỗ trợ | Chờ Supervisor runtime |

## Thay đổi phía backend (`services/vinhomes-api`)

- `reception_delegation.py`: `start_run` mở run cho một tin nhắn, `finish_run` đóng run, `DelegatedScope` xác
  thực token và đọc lại quyền từ database ở mỗi lời gọi (xem mục Ủy quyền).
- `reception_runtime_api.py`: `/internal/reception/v1/execute`, `/v1/reconcile`, `/v1/knowledge-authorization`.
  Bọc các operation sẵn có; từ chối context, channel hay ticket nằm ngoài cuộc trò chuyện của run.
- `v3_reception_runtime.py`: catalog danh mục, policy, ghi câu trả lời, gọi runtime sau khi commit.
- `server/drizzle/0011_reception_runtime_backend.sql`: đăng ký runtime `reception-langgraph`.
  `scripts/grant_v3_api_role.sql`: quyền ghi `runtime_identities`, `runtime_session_bindings`, `agent_runs`.
- `v3_reception_operations.py`: `handoff_ticket` nhận `plan_required` (mặc định `true`); BQL chưa có
  Supervisor thì vẫn tạo ticket, `team` và `handoff` là `null`.
- `v3_reception.py`: context cư dân thêm `building_code`, `domain_name`.

## Ủy quyền

Service token (`VINHOMES_API_RECEPTION_SERVICE_TOKEN` = `RECEPTION_SERVICE_TOKEN`) chỉ chứng minh lời gọi
`/v1/turns` đến từ backend. Nó **không** thao tác thay cư dân được: các route `/internal/reception/*` chỉ nhận
token ủy quyền.

Với mỗi tin nhắn cư dân, backend (trong transaction mang danh cư dân đó):

1. Lấy hoặc tạo `execution_principals` (kind `user`) và `runtime_identities` của cư dân trên runtime
   `reception-langgraph`.
2. Lấy hoặc tạo một `runtime_session_bindings` kiểu `personal` cho cặp (cuộc trò chuyện, agent Lễ tân). Một cuộc
   trò chuyện giữ một binding qua mọi lượt; graph dùng id này làm `bindingId`.
3. Tạo một `agent_runs` trạng thái `running`, khóa idempotency `reception-turn:<message id>`.
4. Ký token HMAC bằng `RECEPTION_DELEGATION_KEY` (chỉ backend giữ), hạn 10 phút, chứa run, binding, principal,
   phiên bản quyền. Ghi audit `reception.delegation_issued`.

Mỗi lời gọi của runtime, backend kiểm chữ ký và hạn, rồi đọc lại từ database: run còn `running`, binding và
identity còn `active`, cư dân còn hoạt động, còn là thành viên tenant và còn sở hữu cuộc trò chuyện, agent Lễ tân
còn `active`, runtime còn `enabled`. Sai một điều kiện là 403. Kết thúc lượt, backend chuyển run sang
`succeeded`/`failed`, nên token chết cùng lượt chat.

Runtime giữ token trong bộ nhớ theo cuộc trò chuyện đang xử lý, không ghi vào checkpoint hay log.

Tắt toàn bộ Reception ngay lập tức: `update runtime_backends set enabled=false where code='reception-langgraph'`.

## Giới hạn cần biết

1. Policy khẩn cấp là danh sách từ khóa có dấu. Tin nhắn không dấu sẽ không tự kích hoạt khẩn cấp; graph hỏi lại.
2. Báo khẩn cấp trước khi có ticket chỉ là cờ nội bộ; BQL nhận thông báo khi ticket được tạo.
3. Trạng thái hội thoại lưu SQLite cục bộ: một replica. Nhiều replica cần checkpointer PostgreSQL.
4. Tìm tri thức: runtime gửi token ủy quyền tới `search_knowledge` v1; server hỏi lại backend ở
   `/internal/reception/v1/knowledge-authorization`. Đường này mới kiểm với stub đúng schema: chưa có dữ liệu
   tri thức, chưa có `agent_knowledge_grants` cho agent Lễ tân, chưa có key embedding. Server mount route khi
   `KNOWLEDGE_ENABLED=1` (`server/src/knowledge/runtime.ts`).
5. Ticket do Reception tạo đi luồng trực tiếp (BQL tạo phiếu, không có bước duyệt kế hoạch).
6. Backend chết giữa lượt thì run nằm lại ở `running`; token vẫn hết hạn sau 10 phút. Chưa có job dọn run treo.
7. Phiên bản agent Lễ tân (`agent_versions`) được tạo tự động ở lần đầu, nội dung chỉ là bản ghi định danh;
   khi Agent Factory quản lý phiên bản thật thì binding mới sẽ dùng phiên bản mới nhất.

## Đề nghị Team Hoàng

- Rà `runtime/backend.py` và `runtime/service.py`; nếu đồng ý hợp đồng này thì PD11 (graph gọi bộ tool mới)
  có thể đổi thành: giữ graph, coi lớp chuyển đổi là cổng tool chính thức.
- Cho biết model và nhà cung cấp dùng để nghiệm thu; cần chạy lại bộ eval tiếng Việt với LLM thật.

## Chạy lại kiểm thử

Backend: `pytest` trong `services/vinhomes-api` (cần PostgreSQL thử; xem `tests/test_resident_contract.py`).
Đầu-cuối: bật backend (demo, có `RECEPTION_DELEGATION_KEY`), runtime và `tests/runtime/fake_llm.py`, rồi
`RECEPTION_E2E_BACKEND_URL=… RECEPTION_E2E_TOKEN=… pytest tests/runtime/test_resident_chat_e2e.py` trong `agent-reception`.
