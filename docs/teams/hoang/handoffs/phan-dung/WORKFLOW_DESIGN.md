# Thiết kế graph Reception — Phan Dũng

Ngày 30/09/2026. Implementation hiện tại: `agent-reception/src/graph/workflow.py`.
Factory: `create_reception_workflow_factory`, consumer version `pd-workflow-python-1`.
`factory.py` giữ PD01/PD02 harness với marker `pd01-python-1`. Không tự migrate
checkpoint TypeScript. Xem [handoff chuyển Python](PYTHON_MIGRATION.md).

```mermaid
flowchart TD
  START --> receive_message
  receive_message -->|Chưa active ticket| answer_or_escalate
  receive_message -->|Thiếu verified profile| load_resident_context
  receive_message -->|Chưa handoff| collect_incident_details
  receive_message -->|Có ACK| active_ticket_dialogue
  answer_or_escalate -->|Knowledge đủ| END
  answer_or_escalate -->|Cần chuyên môn| create_ticket_draft
  answer_or_escalate -->|Thiếu dữ kiện| wait_for_resident
  create_ticket_draft --> execute_operation
  execute_operation -->|Draft success| load_resident_context
  load_resident_context --> execute_operation
  execute_operation -->|Verified profile| collect_incident_details
  collect_incident_details --> execute_operation
  execute_operation -->|Incident đủ| submit_assessment
  submit_assessment --> execute_operation
  execute_operation -->|Official triage| resolve_management_destination
  resolve_management_destination --> execute_operation
  execute_operation -->|Backend route resolved| handoff_to_supervisor
  handoff_to_supervisor --> execute_operation
  execute_operation -->|ACK persisted + enqueued| wait_for_supervisor
  wait_for_supervisor -->|Chưa đăng ký| execute_operation
  execute_operation -->|Registered| wait_for_supervisor
  execute_operation -->|Buffered event| process_supervisor_event
  wait_for_supervisor -->|Event đã validate → resume| process[Áp dụng event]
  process_supervisor_event --> process
  process -->|Yêu cầu cư dân| wait_for_resident
  process -->|Đang xử lý| wait_for_supervisor
  process -->|Supervisor completed| status[Backend status/evidence confirmation]
  status -->|Confirmed| END
  status -->|Chưa confirmed| wait_for_supervisor
  active_ticket_dialogue -->|Bổ sung, status, cancel, interaction| execute_operation
  active_ticket_dialogue -->|Sự cố mới| END
  wait_for_supervisor -->|Resident resume| receive_message
  wait_for_resident -->|Resident resume| receive_message
  execute_operation -->|Unknown hoặc accepted| wait_for_operation
  wait_for_operation -->|Authorized reconcile cùng key/input| execute_operation
  execute_operation -->|Rejected/unresolved policy hoặc route| human_review
```

Các cạnh đi qua execute_operation biểu diễn plan đã checkpoint và projection output;
plan.after chọn node tiếp theo. Các node chỉ thực hiện business orchestration, không
tự xây HTTP client/auth/persistence/backend. Interrupt operation/resident/review là
khác Supervisor wait sau ACK. `process` trong sơ đồ là helper `_apply_event`, không node
LangGraph riêng; event resume được validate trước consume interrupt.

Hồ sơ chỉ từ verified backend; route từ ticket/backend scope. Model chỉ trích
intent/incident/facts customer_report hoặc agent_inference/interaction answers.
Không có model-supplied tool, tenant, workspace, file IDs hoặc official triage.
Active ticket không quay lại create draft. Unknown mutation không sinh key mới.
Supervisor completed gọi backend status, không tin customer_message để đóng ticket.

Chưa mount runtime production; request chốt contracts và integration ở
[PD03_PD08_INTEGRATION](../../requests/phan-dung/PD03_PD08_INTEGRATION.md).
Graph tests dùng LangGraph Python thật + synthetic ports + InMemorySaver trong tests;
không chứng minh durable storage, auth, actual event delivery hoặc hai replica.
