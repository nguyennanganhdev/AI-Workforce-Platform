# PHH: dependencies cần tích hợp trước khi nghiệm thu

Ngày: 10/10/2026. Branch local: `feat/wf-orchestration`. Baseline: `develop2@6bc7d60`.

Owner nhận: Nguyễn Chí Hoàng. Dependencies khác: Phó Tiến Anh, Phan Hoàng Dũng, Nguyễn Phương Đông.

## Bằng chứng hiện trạng

`src/agentscope/app/workforce/contracts/`, `foundation/`, `integrations/`, `lifecycle/`, `execution/` và `registry/` hiện chỉ có README scaffold trong checkout đã kiểm tra. Chưa có concrete DTO/ports/bootstrap của Workforce để PHH import/nối. Không tạo bộ contracts chung thứ hai hoặc sửa code của owner khác.

PHH đã viết services, metadata, SQL repository, Chat UI và tests trong vùng mình. Chưa mount route, tạo migration thật hoặc bật runtime production. Không lấy sự tồn tại callback interface làm bằng chứng tích hợp.

## 1. Contracts và UOW

Các seam trong `_repository.py` là module-local, không thay DTO/ports mục 6/17.4. Cần Foundation xuất Scope/DTO và wrapper chuyển dữ liệu typed sang internal snapshot. `CapabilityRouter` nhận được cả scope dạng tuple trong internal record và Scope dạng mapping/Pydantic tại boundary.

Repository nhận `async_sessionmaker` qua composition. UOW hiện là AsyncSession transaction; adapter Foundation phải thống nhất với shared UOW. Identity `check_scope_active(scope, uow)` phải kiểm tra membership hiện hành trong cùng transaction.

Public catalog cần trả `items` + `catalog_revision`; mỗi candidate có scope, agent_id, version_id, deployment_id, manifest_hash, status, capabilities, name. `get_version` trả immutable manifest/hash/agent/scope, `get_deployment` trả status/active_version_id/agent/scope. Nếu signature DTO chung khác, đổi adapter tại composition; không tự đổi contract chung.

Metadata hiện có: `wf_conversations`, `wf_runs`, `wf_workflows`, `wf_inbound_requests`. Conversation/run/state/member/task và workflow binding được lưu trong JSONB aggregates, kèm columns phục vụ scope/CAS/unique/FK. **Đây là schema đề xuất chưa được migration owner chốt**: kế hoạch chung còn nêu wf_messages/wf_run_members/wf_shared_states/wf_runtime_bindings/wf_partner_conversation_bindings và public event table riêng. Chí Hoàng/PHH cần thống nhất projection/normalization trước migration; chưa coi aggregate schema hiện tại thay thế các bảng đã chốt.

Chỉ Foundation tạo revision Alembic thật, export metadata vào bootstrap và kiểm tra DB mới + upgrade DB có dữ liệu. Không chạy create_all trong production. PostgreSQL locking/CAS/FK/race/restart cần integration suite thật; SQLite smoke và compile DDL không đủ bằng chứng.

## 2. Pinned AgentScope adapter

`TeamRuntimeAdapter` nhận hai hook bắt buộc:

```text
provision_pinned_group(scope, stored_run, *, idempotency_key) -> binding
send_team_task(scope, group_id, recipient_session_id, task, *, idempotency_key) -> delivery
```

Provision phải dùng TeamRecord/TeamMember invited + SessionRecord của AgentScope hiện có, session/group IDs đã persist trong run. Không tạo AgentDefinition mới. Trả đúng group/leader/member(agent/version/session/hash); retry và restart không tạo record/session thứ hai. Manual-add dùng `pending_members` riêng và `membership_operation_id` đã persist; run vẫn running, pending member chưa nhận message/task. Adapter truyền roster đích qua `stored_run.members`, gồm cả thành viên cũ và pending, rồi đối soát binding trước khi đánh dấu ready. Khóa retry là group + membership operation ID, không dùng run revision vì ACK/completion của task cũ vẫn có thể tăng revision. Concrete hook phải giữ sessions cũ/pending context, kiểm tra cancellation/fence hiện hành và chặn provisioning cũ ghi đè membership mới.

Đọc `_agent_invite.py` cho thấy tool có thể lấy chat model/workspace từ session hiện có hoặc leader session. Không dùng tool đó nguyên trạng để chứng minh version pin. Cần adapter áp đúng manifest/prompt/model/context/tool bindings của mỗi immutable version, revalidate deployment/grants tại thời điểm provisioning và dispatch. Thực thi tool vẫn qua Execution guard.

Các session_id truyền vào HandoffService là **trusted runtime context**; không bind từ request body. Dịch vụ HTTP/LLM không được tự chọn session gửi/ACK/complete. Kết quả delivery chỉ ACK transport; worker callback mới complete business task.

## 3. Message, Evaluation và UI wiring

- MessageService `deliver_message(scope, persisted_message, idempotency_key=message_id)` cần enqueue/bus adapter có dedupe/recovery, revalidate group/member và session hiện hành trước send. Retry pending message hiện tái dùng ID; chưa có durable scanner tự phục hồi delivery.
- EvaluationRunner dùng cùng invoke-runtime entrypoint và Execution guard production; backend guard factory cấp mode mock/sandbox, fixed clock và toolkit riêng. Chưa có concrete factory/hook, case persistence hay cost integration thật.
- Chat UI là controlled component `WorkforceChat`, timeline là `TicketTimeline`; callbacks phải gọi API thật. ApprovalCard thật và shared/event_transport chưa có để import. Cần owner nối shell/global API, UI test/build/lint toàn app. Không mount demo/fake success vào production.
- PHH còn phải hoàn thiện group usage API/membership history, pending-question lifecycle, proposal writing, direct context transfer và run cancel/resume/finish orchestration.

## 4. Ticket ingress / durable jobs

`TicketIngress` là service cho route ticketed, chưa phải HTTP endpoint đầy đủ. Partner guard bridge cần:

```text
authorize(authenticated_partner_actor, envelope, operation, uow)
  -> {scope, audience, route_id, route_revision, timezone}
```

Bridge dùng PartnerRoutingPort.resolve/revalidate và machine auth của Foundation; kiểm tra grant/purpose/residence/current membership trong cùng UOW. Không tin envelope để cấp scope/audience. `operation` là submit_request hoặc reply. Audience gồm partner_client_id, external_user_id, external_ticket_id, external_conversation_id, các refs đã xác minh nếu có. Scope từ Foundation có đủ 4 trường.

JobPort enqueue phải ghi job/outbox bằng **chính UOW hiện tại**, không tự commit, không trực tiếp gọi model. Payload workflow_turn chứa persisted request/workflow/conversation/group IDs và message text envelope. Worker chỉ dùng binding đã lưu; không route lại bằng management ref hiện hành hoặc LLM. Bounded-wait + GET result + HTTP status/error mapping còn cần PHH triển khai sau khi chốt ports/result signal/read auth.

Unique namespace request là tenant + partner client + external_request_id; binding unique tenant/client/user/ticket và tenant/client/user/chat. PostgreSQL contention handler còn phải bắt unique conflict, rollback và đọc receipt/conflict chuẩn; không trả lỗi SQL/raw payload ra ngoài.

Non-ticketed route chưa triển khai; không giả định mọi integration đều cần external_ticket_id. Schema timezone/message tham chiếu contract đối tác: message {type: text, text: ...}, schema_version="1", timezone explicit hoặc default route hợp lệ.

## 5. Workflow/public event còn cần nối

Pure lifecycle/checkpoint/projection đã có tests; chưa có durable scheduler, worker claim/lease/fence UOW, timer, Execution operation guard, atomic checkpoint/message/event/outbox commit, public event repository, result waiter hoặc SSE reader.

Chí Hoàng cung cấp JobPort/RuntimeContinuationPort/PublicEventSignalPort/shared transport, Dũng cung cấp verified operation/progress/correlation và fake partner exports, Đông cung cấp protocol normalization/capabilities. PHH tiếp tục triển khai phần thuộc workflows/partner_events sau khi contracts được chốt.

Gate yêu cầu: ba lifecycle pattern qua HTTP thật; A1/B1/A2/B2 giữ group/session/context riêng; close/reply/event race; crash/lost signal/sleep race; replay/history/snapshot/retention; proxy/slow consumers/auth revoke <=60s; worker restart trên PostgreSQL. Không coi các pure/fake tests hiện tại là PASS cho gate này.

## Điều kiện để đóng request tích hợp

Ghi exports/version, file/hooks đã nối, migration revision, tests và kết quả thực. Trạng thái ban đầu: **OPEN / chưa có xác nhận từ owner**. Việc có tài liệu này không có nghĩa đã nhắn owner hoặc integration đã được thực hiện.
