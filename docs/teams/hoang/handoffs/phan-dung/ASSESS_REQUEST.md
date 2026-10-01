# Handoff — assess_request và Reception system prompt

Phan Dũng, 30/09/2026, nhánh dev_TeamHoang_PhanDung đã được phép.
Hoàn thành code consumer, validators, prompt và tests; backend/runtime integration
chưa có. Không sửa DB/migration/runtime entrypoint/UI/Supervisor/package/lockfile.

## File sửa/thêm

- `agent-reception/src/graph/workflow.py`: receive_message → assess_request;
  bounded dialogue history, deterministic routes, retrieve_self_help/emergency_handoff,
  response guards và giữ active ticket kể cả terminal.
- `agent-reception/src/graph/assessment.py`: schema strict, parser, policy guard và
  approved procedure expiry/source validation.
- `agent-reception/src/graph/workflow_contracts.py`, `__init__.py`: Python public API,
  RequestPolicyPort, RequestAssessment/ReceptionDecision, inputs hai capability mới;
  workflow marker tăng `pd-workflow-python-2`.
- `agent-reception/src/prompts/workflow.py`: RECEPTION_SYSTEM_PROMPT dùng chung,
  ASSESS_REQUEST_PROMPT và RESIDENT_TURN_PROMPT; prompt version pd-reception-python-2.
- `agent-reception/tests/graph/test_assessment.py`, `workflow_fixture.py`:
  synthetic model/policy/tools chỉ test; `tests/evals/reception.vi.json` thêm expected
  emergency alert trước draft.
- Docs design/current handoff/request cập nhật marker và luồng; request mới
  ASSESS_REQUEST_POLICY_SELF_HELP mô tả producer API/compatibility/tests còn thiếu.

## Hành vi

LLM phân tích current message + history scoped (24 entries) và schema ở HumanMessage,
system prompt riêng node, trả proposal strict JSON. Code validate trước state.decision;
next_action do code/policy guard quyết định, không cho LLM chọn tool/tenant/workspace.
Khẩn cấp policy preflight confirmed bỏ qua LLM/retrieval; nonemergency recheck policy
với proposal. Policy missing → review, không default model/mock policy.

Information/giá → knowledge có nguồn; insufficient hỏi/xác minh, không draft sửa chữa.
Incident chưa rõ → hỏi, resume đánh giá lại với câu hỏi cũ và lịch sử. Staff policy
confirmed → draft. Self-help → backend lifecycle/approved procedure; offer chưa in
steps, accepted có recorded consent đúng message/version mới phát steps và stop
conditions; success ghi nhận kết quả, decline/failure/stopped → ticket. Missing,
revoked/expired procedure không tự biến thành yêu cầu điều nhân viên.

Emergency → checkpointed alert capability trước draft/profile/ảnh. Active ticket
emergency update cùng ID/generation, official reassessment/rerouting sau ACK; không
ticket thứ hai. Active follow-up vẫn append/status/cancel/interaction; thông tin
độc lập có thể trả lời knowledge và giữ ID. Sự cố không liên quan hướng dẫn chat mới;
terminal ticket vẫn gắn chat. Tool lost/partial ACK không nói thành công hoặc đổi key.

## Kiểm thử và giới hạn

Lệnh từ repo root:

```powershell
python -B -m pytest -q -p no:cacheprovider agent-reception/tests/graph agent-reception/tests/evals server/tests/reporting/narrative
python -B -m ruff check agent-reception/src/graph agent-reception/src/prompts agent-reception/tests/graph agent-reception/tests/evals
python -B -m ruff format --check agent-reception/src/graph agent-reception/src/prompts agent-reception/tests/graph agent-reception/tests/evals
git diff --check
```

Consumer tests dùng LangGraph Python thật, fake model/ports/InMemorySaver chỉ tests.
**182 test Python pass, 0 fail**, Ruff lint/format đạt; không phải real policy/LLM/self-help approval/
backend dispatch/realtime transport hoặc durable multi-replica evidence.

RequestPolicyPort/semantic process_self_help/escalate_emergency chưa bind backend;
C13 session-before-ticket attempt gap cần owner chốt, không tạo mock/ID giả hoặc
migration PD. Platform TS chưa gọi Python. LangGraph topology p2 cần PH namespace/
migration rõ ràng. Stream hiện phát output sau invocation, chưa transport push safety
trước network ACK. Prompt không thay ACL, policy, approval, telemetry redaction.
Request: [ASSESS_REQUEST_POLICY_SELF_HELP](../../requests/phan-dung/ASSESS_REQUEST_POLICY_SELF_HELP.md).
