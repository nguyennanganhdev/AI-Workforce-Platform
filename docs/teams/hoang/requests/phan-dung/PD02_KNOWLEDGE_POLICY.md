# PD02 — Request knowledge và policy ports

Người ghi: Phan Dũng, Team Hoàng. Ngày: 30/09/2026.
Owner đích: Dương Dũng DD02 (wrapper); Quang Q01/Q04 (retrieval);
Chiến C01/C05/C06 (policy/auth); Phan Hoàng PH02/PH05 (composition).
Đây là request trong repo, chưa gửi thông điệp hoặc xác nhận owner chấp thuận.

## Bằng chứng và phạm vi

PH01 contracts TypeScript vẫn là `0.1.0-draft.1`. PD01/PD02 hiện dùng Python
consumer proposal `0.1.0-python.draft.1`, đã test với LangGraph Python 1.2.11;
chưa có composition production nối platform TypeScript.
Không thấy file implementation trong `server/src/knowledge/`, `server/src/runtime/`
hoặc `shared/contracts/` qua `rg --files`; không có wrapper `src/tools/` hay
`src/adapters/backend/` Reception. Tìm knowledge/reception trong `server/src/app.ts`
không có mount tương ứng. Tên tool trong kế hoạch chưa được dùng làm endpoint thật.

PD02 cung cấp `run_intake` ở `agent-reception/src/graph/intake.py`;
protocol nằm ở `agent-reception/src/graph/workflow_contracts.py`:

```python
class IntakePort(Protocol):
    async def evaluate_policy(self, request: dict) -> dict: ...
    async def search_knowledge(self, request: dict) -> dict: ...
```

Đây là interface nội bộ đề xuất, không phải OpenAPI/schema đã freeze. Request gồm
JSON message `{id,text,fileIds?}`, context wire shape PH01 đã xác minh và
CancellationToken local Python trong trường `signal`.
Identity/context lấy từ PH02/backend; không nhận tenant/scope/workspace
do model hoặc browser tự chọn. `fileIds` vẫn là reference chưa có nghĩa được cấp quyền;
backend phải authorize trước khi đọc. Không truyền secret trong payload/context.

## Output và semantics cần review

- Policy: `policyVersion` và một trong `emergency|needs_staff` kèm reason,
  hoặc `knowledge_chat|clarify` kèm question. Owner phải evaluate bằng policy xác định,
  đã publish, dựa vào context/facts/provenance; không chỉ prompt/model confidence.
  Kết quả này chỉ quyết định nhánh intake, không ghi priority/severity/SLA chính thức.
- Knowledge: `{kind:"sufficient",answer,retrievalRunId,citations:[{documentId,version,chunkId}]}`
  hoặc `{kind:"insufficient"}`. Sufficient bắt buộc answer, retrievalRunId và ít nhất
  một citation có đủ ID/version. DD02 validate schema thật và normalize về consumer
  shape; graph kiểm tra các trường thiết yếu, không thay ACL/citation verification.
- Emergency/needs_staff là policy bắt buộc gọi chuyên môn, gồm khách từ chối hoặc
  self-help thất bại nếu policy áp dụng: ưu tiên trước search. Không trì hoãn vì thiếu
  ảnh/knowledge, không để retrieval đủ nguồn ghi đè kết quả này.
- Với nhánh bình thường: knowledge đủ → trả lời; insufficient → dùng câu hỏi policy,
  chưa tạo ticket. Thiếu knowledge đơn thuần không đủ lý do gọi nhân viên.
- Policy thiếu/sai hoặc port throw → review, không fallback model/mocks; exception
  message bị lọc. Knowledge lỗi không được gán thành dữ liệu rỗng hay đủ nguồn.
- Wrapper phải enforce timeout và propagate Python CancellationToken/task cancellation, xử lý 401/403/revoke,
  unavailable/rate limit theo schema lỗi owner chốt; graph không cài HTTP client,
  retry hay tự định nghĩa endpoint. Read ports phải không có mutation ngầm.

## Composition và compatibility

PH05 inject `intake` trong `ReceptionFactoryOptions(bindings=bindings, intake=intake)`
cho generic factory hoặc `WorkflowOptions(intake=intake, resolve_session=resolve_session, ...)`
cho business workflow. Generic option optional chỉ phục vụ harness PD01; production
PD02 bắt buộc port thật, không coi omitted là đã bật knowledge/policy.

Schema envelope vẫn 1 nhưng marker Python riêng `pd01-python-1` hoặc
`pd-workflow-python-1`. Không đọc/migrate checkpoint TS cũ tự động. PH03 review
namespace/topology/persistence; PH05 nối Python composition hoặc bridge với TS.
Xem [PYTHON_RUNTIME_INTEGRATION](PYTHON_RUNTIME_INTEGRATION.md).

Ở generic factory, needs_staff chuyển human_review interrupt. Trong business graph
`workflow.py`, needs_staff nối draft/profile/incident/assessment/route/ACK/wait.
Intake riêng không mutation, dispatch hoặc đóng ticket; emergency notification thật
cần backend/runtime owner nối. Budget Python không chứng minh rollback backend.

## Fixture và contract tests cần producer chạy

Consumer fixtures synthetic chỉ trong `agent-reception/tests/graph/test_intake.py`. Producer cần dùng
fixtures cùng shape hoặc thống nhất normalize/version trước freeze. Tests yêu cầu:

1. Cùng câu hỏi hai tenant → chỉ retrieval/citation đúng quyền; revoke chặn cả cache.
2. Backend user/binding đã xác minh; forged scope/file ID không được đọc dữ liệu.
3. Sufficient thiếu citation/retrieval/version → bị từ chối; insufficient không create.
4. Policy emergency → không đợi model/search/ảnh; cần chuyên môn không bị answer ghi đè.
5. Timeout/401/403/429/lost response → lỗi đã lọc; CancellationToken/task cancellation dừng coroutine hợp tác.
6. Injection trong chat/document không mở rộng scope hoặc kích hoạt mutation.
7. Composer dùng backend thật; không dùng ScriptedModel/InMemorySaver/test ports
   làm fallback production. Producer/consumer tests không thay E2E thật.
