# Phan Dũng — Bàn giao chuyển Python

Ngày 30/09/2026; nhánh `dev_TeamHoang_PhanDung` đã được người dùng cho phép.
Đã chuyển toàn bộ 22 file TypeScript do PD viết sang Python trong phạm vi giao.
Đã xóa các bản TS đó sau khi test Python pass. Giữ nguyên owner runtime/contracts,
backend, DB/migration, UI/Supervisor/worker entrypoint và manifest/lockfile.
Không commit/push; chưa có production composition Python.

## File chuyển đổi

| File TypeScript đã bỏ | File Python thay thế |
|---|---|
| `agent-reception/src/graph/factory.ts` | `factory.py` |
| `agent-reception/src/graph/state.ts` | `state.py` |
| `agent-reception/src/graph/decision.ts` | `decision.py` |
| `agent-reception/src/graph/index.ts` | `__init__.py` |
| `agent-reception/src/graph/budget.ts` | `budget.py` |
| `agent-reception/src/graph/intake.ts` | `intake.py` |
| `agent-reception/src/graph/workflow-contracts.ts` | `workflow_contracts.py` |
| `agent-reception/src/graph/workflow-validation.ts` | `workflow_validation.py` |
| `agent-reception/src/graph/workflow.ts` | `workflow.py` |
| `agent-reception/src/prompts/pd01.ts` | `pd01.py` |
| `agent-reception/src/prompts/workflow.ts` | `workflow.py` |
| `agent-reception/tests/graph/factory.test.ts` | `test_factory.py` |
| `agent-reception/tests/graph/intake.test.ts` | `test_intake.py` |
| `agent-reception/tests/graph/workflow.fixture.ts` | `workflow_fixture.py` |
| `agent-reception/tests/graph/workflow.test.ts` | `test_workflow.py` |
| `agent-reception/tests/graph/workflow-failures.test.ts` | `test_workflow_failures.py` |
| `agent-reception/tests/evals/reception.test.ts` | `test_reception.py` |
| `agent-report/schemas/config.ts` | `config.py` |
| `agent-report/examples/generate-preview.ts` | `generate_preview.py` |
| `server/src/reporting/narrative/operations.ts` | `operations.py` |
| `server/src/reporting/layouts/operations.ts` | `operations.py` |
| `server/tests/reporting/narrative/operations.test.ts` | `test_operations.py` |

Tên thay thế ở cột phải nằm cùng folder cột trái. Thêm package init trong
Reception prompts, Report schemas, server narrative/layouts; thêm
`agent-reception/tests/graph/conftest.py` cho import test. Tổng 27 file Python.
Giữ JSON schemas/templates/config/dataset và Markdown prompts; sinh lại 4 HTML
previews bằng Python. Docs hiện tại sửa: WORKFLOW_DESIGN, PD_ALL_VERIFICATION,
PD03_PD08_INTEGRATION; thêm handoff này và PYTHON_RUNTIME_INTEGRATION request.
Handoff PD01–PD08 và các request đã được cập nhật trực tiếp theo đường dẫn/API/test
Python hiện tại. Bảng ở trên giữ lịch sử ánh xạ TS đã xóa; không phải file đang tồn tại.

## Hành vi và API

Generic PD01 và business graph dùng StateGraph/Command/interrupt của LangGraph
Python thật. Business graph giữ 8 node cơ bản và helper plan/execute/wait/review;
checkpoint plan trước gọi port, active_ticket_id chỉ từ backend success,
verified profile/official triage/backend route trước schema-v1 handoff, ACK
persisted+enqueued trước wait, authorized event validation trước resume.
Unknown/lost response/timeout giữ pending; reconciliation dùng key/input cũ.
Supervisor completed vẫn cần status confirmation backend. Knowledge đủ không
tạo ticket; resident/model không tự cấp quyền, profile, route hay staff_verified.
Report giữ version/grants/snapshot lineage và phân biệt 0 với missing/error.

Python function names snake_case; wire JSON giữ format cũ. Version riêng chặn
đọc checkpoint TS: `pd01-python-1` / `pd-workflow-python-1` và
contract `0.1.0-python.draft.1`. Request owner nêu import paths và dependency pins.

## Test đã chạy

Từ repo root với Python 3.11.9, LangGraph 1.2.11, checkpoint 4.2.0,
LangChain Core 1.6.0, pytest 9.1.1; không cài thêm dependency:

```powershell
python -B -m pytest -q -p no:cacheprovider agent-reception/tests/graph agent-reception/tests/evals server/tests/reporting/narrative
python -B agent-report/examples/generate_preview.py
python -B -m ruff check agent-reception/src/graph agent-reception/src/prompts agent-reception/tests/graph agent-reception/tests/evals agent-report/schemas agent-report/examples server/src/reporting/narrative server/src/reporting/layouts server/tests/reporting/narrative
python -B -m ruff format --check agent-reception/src/graph agent-reception/src/prompts agent-reception/tests/graph agent-reception/tests/evals agent-report/schemas agent-report/examples server/src/reporting/narrative server/src/reporting/layouts server/tests/reporting/narrative
git diff --check
```

- **137 Python tests pass**: graph/intake/recovery, 12 Vietnamese synthetic evals,
  Report validation/lineage/layout. Mocks/model/RAM saver chỉ ở tests; generator
  synthetic chỉ examples chạy thủ công. Không pytest-asyncio cần thiết; mỗi test
  async chạy qua asyncio.run. `-B`/no-cache giữ workspace không có pycache test.
- Preview command pass, tạo complete/partial/empty/error HTML.
- Ruff lint/format pass cho 27 file Python.
- Regression runtime TS còn lại: **25 pass, 0 fail**, 5 files, 47 assertions,
  chạy Bun 1.3.14 từ agent-reception ngoài sandbox sau approval. Lần sandbox có
  2 bootstrap fail vì EPERM spawn; rerun ngoài sandbox pass.
- Typecheck Reception TS còn lại `tsc --noEmit` pass. Không chạy full server suite.
- Ownership/import inventory: không còn TS trong các folder code/test PD nêu trên;
  không production importer ngoài scope trỏ tới TS bị xóa. `git diff --check` pass.

Không so sánh trực tiếp count 137 với count 138 TS cũ: TS cũ gồm runtime tests;
Python port tập trung consumer PD, runtime TS còn lại được chạy riêng.

## Dependency và phần chưa tích hợp thật

DD/PH/Chiến/Quang backend tools, policy/RAG, ACL và persistent saver/wait registry/
event lookup/reconciliation chưa được nối production; không mock production.
Entrypoint/runtime Reception và server còn TS của owner khác, chưa gọi Python graph
hoặc Report modules. Chưa có DOCX renderer, storage/export/download, E2E backend/
Supervisor thật hoặc multi-replica/crash integration. PH phải chốt manifest/package
namespace/Python deployment/transport/checkpoint migration. Không chuyển toàn server
hay runtime của owner khác sang Python dưới tên task PD.

Request: [PYTHON_RUNTIME_INTEGRATION](../../requests/phan-dung/PYTHON_RUNTIME_INTEGRATION.md).
Thiết kế node: [WORKFLOW_DESIGN](WORKFLOW_DESIGN.md).

## Cập nhật tài liệu sau chuyển đổi

Đã đồng bộ handoff PD01–PD08, PD_ALL_VERIFICATION, WORKFLOW_DESIGN, handoff này,
requests PD01_DEPENDENCIES/PD02_KNOWLEDGE_POLICY/PD03_PD08_INTEGRATION và
PYTHON_RUNTIME_INTEGRATION, cùng prompt Report. Chữ ký composition chuyển sang
Python dataclass/protocol/async, lệnh kiểm thử PD dùng pytest/Ruff, version marker
riêng và dependency cầu nối platform TypeScript vẫn được nêu rõ.
Kiểm tra docs: pytest collect-only nhận 137 tests; rà đường dẫn Python, local
Markdown links, tên API và git diff check. Lượt sửa tài liệu không chạy lại suite
code hoặc tuyên bố thêm integration production.
