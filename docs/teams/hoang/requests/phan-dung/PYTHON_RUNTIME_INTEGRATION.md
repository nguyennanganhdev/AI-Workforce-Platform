# Phan Dũng — Request nối composition Python

> Cập nhật assess_request: topology business graph `pd-workflow-python-2`, RequestPolicyPort bắt buộc khi chạy; hai capability self-help/emergency chưa bind backend. Xem [thiết kế và contract mới](ASSESS_REQUEST_POLICY_SELF_HELP.md).

Ngày 30/09/2026. Theo yêu cầu người dùng, toàn bộ 22 file TypeScript do PD viết
trong graph/prompt/tests Reception và schema/example/narrative/layout/tests Report
đã được chuyển sang Python. Không sửa runtime/package/contracts của owner khác.
Các dependency backend trong PD02_KNOWLEDGE_POLICY và PD03_PD08_INTEGRATION vẫn mở.

## PH01–PH06 / Team Đông / Team 5

- Chốt contract Python và cách runtime TypeScript gọi Python: Python process/service
  hoặc port toàn runtime theo quyết định owner. Chưa tạo transport/entrypoint mới.
- Module consumer: `src.graph` khi `agent-reception` nằm trên Python import path.
  Chốt package namespace/manifest/dependency lock/CI/deployment do owner quản lý;
  graph không tự sửa `sys.path`, không tự cài package hoặc tạo RAM saver mặc định.
- API async: factory `.create(GraphDependencies(model, tools, checkpointer))`;
  `.run(request)`, `.resume(request)`, `.read(context)`, `.stream(request)`;
  business graph thêm `.recover(request)` để đối soát plan sau abort/crash.
  Model là LangChain Python với `ainvoke(messages)`; tool port là
  `async invoke(request)`; policy là `evaluate_policy`/`search_knowledge`;
  session resolver là `resolve_session(context, signal)`.
- Wire JSON giữ `operationId`, `interruptId`, `source`, `context`, `fileIds`,
  `idempotencyKey`, `timeoutMs` và schema Reception–Supervisor v1. Python symbol
  dùng snake_case. `CancellationToken` là đối tượng local Python, không gửi qua JSON.
- `GraphDependencies.checkpointer` bắt buộc là async-compatible LangGraph Python
  saver thực. Tests dùng InMemorySaver riêng, không cung cấp default production saver.
- Python marker: `0.1.0-python.draft.1`, generic `runtime_version= pd01-python-1`,
  business `workflow_version=pd-workflow-python-2`. PH03 phải chốt namespace mới,
  retention/dedup/lease/fencing và migration có kiểm soát; Python từ chối checkpoint
  TypeScript hoặc topology khác, không reset session tự động.
- Thread key là compact JSON tuple `[checkpoint.namespace, checkpoint.threadId]`,
  root `checkpoint_ns=""`; message payload canonical JSON là fingerprint chống replay
  xung đột. Owner cần chốt retention và dữ liệu checkpoint chứa PII trước production.
- PH04/DD05 cung cấp authorized event lookup, durable register wait, wrapper
  `interaction_revision`, reconciliation theo đúng key/input. Event được validate
  trước consume interrupt; không gọi lại mutation khi outcome chưa rõ.
- Budget cancel coroutine/token không chứng minh rollback backend. Port phải tôn
  trọng cancellation, timeout và idempotency; I/O đồng bộ chặn event loop hoặc coroutine
  nuốt cancellation cần owner xử lý ở adapter/process. Không claim hard process kill.

## DD01–DD08 / Chiến / Quang

`workflow_contracts.py` chứa TypedDict/protocol và `OPERATION_INPUTS` cho 14 semantic
operations; đây vẫn là proposal consumer. Chốt tên tool, response decoder và HTTP
mapping theo backend thật, không đăng ký tool bằng tên kế hoạch một cách tự động.
Giữ schema-v1, profile verified, ACL file/scope/grants và snapshot lineage; xác nhận
not_applied khác unknown. Các validator nằm trong `workflow_validation.py` và
`agent-report/schemas/config.py`; không chuyển test fake ports vào production.

## PH07–PH08 / DD07–DD08

- Report Python imports: `schemas.config` từ `agent-report`,
  `reporting.narrative.operations` và `reporting.layouts.operations` từ `server/src`.
  Owner chốt package namespace tránh collision và bridge sang server TypeScript.
- `validate_report_config`, `build_report_narrative`, `render_report_preview`
  giữ JSON config/snapshot/source format. Preview HTML chỉ chạy local.
- `OPERATIONS_LAYOUT` là semantic layout cho renderer PH08, chưa xuất DOCX,
  chưa lưu storage/export/download, chưa gọi real metric tools.
- Python 3.11.9 đã kiểm tra với langgraph 1.2.11, langgraph-checkpoint 4.2.0,
  langchain-core 1.6.0, pytest 9.1.1. Timezone Windows cần tzdata; môi trường test
  hiện có tzdata. Owner pin dependency trong manifest/lock của mình.

## Nghiệm thu cần owner thực hiện

Producer/consumer contract tests trên API thật; resident → draft → profile →
incident → route → ACK → wait → Supervisor event → resume → status confirmation;
process restart, lost response/early event/two replicas/revoke/reroute; Report real
grants/snapshot sources → DOCX/export/download với quyền tải lại. Unit/consumer test
182 pass ở lượt assess_request không thay các kiểm chứng integration này.

Các handoff PD01–PD08 và PD_ALL_VERIFICATION hiện mô tả code/API Python; lệnh pytest
chạy từ repo root. Bảng TS → Python trong PYTHON_MIGRATION chỉ là lịch sử chuyển file,
không yêu cầu owner import lại các file TS đã xóa.

Hai semantic capabilities bổ sung process_self_help/escalate_emergency và RequestPolicyPort
bắt buộc được mô tả trong [ASSESS_REQUEST_POLICY_SELF_HELP](ASSESS_REQUEST_POLICY_SELF_HELP.md).
