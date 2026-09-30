# Phan Dũng — Bàn giao tổng PD01–PD08 Python

Ngày 30/09/2026. Nhánh `dev_TeamHoang_PhanDung` đã được người dùng cho phép.
Code PD01–PD08 hiện dùng Python; platform Reception/server runtime của owner khác
vẫn TypeScript và chưa gọi các module Python. Không commit/push hoặc sửa owner khác.

## Trạng thái

| Task | Phần PD đã có bằng Python | Dependency còn mở |
|---|---|---|
| PD01 | Versioned state/factory/bindings/interrupt/stream | PH freeze Python contract/persistence/runtime bridge |
| PD02 | Knowledge/policy intake, no ticket khi sufficient | DD02/Quang/Chiến API/RAG/policy thật |
| PD03 | Stable draft guard, verified profile, incident/file questions | DD02/DD03/C03/C04/C07/PH02/PH03 |
| PD04 | Official assessment → backend route → schema-v1 handoff | DD03/DD04/C05/Đông/PH05 |
| PD05 | ACK/register/wait/resume/reconcile/recover và active dialogue | PH03/PH04/C06/C08 durable runtime, DD05 |
| PD06 | 12 synthetic Vietnamese consumer evals | Model/policy/E2E eval thật |
| PD07 | Template/config/schema/prompt/two BQL examples | DD07/C09/C14/PH07/Đông publish/runtime |
| PD08 | Narrative/lineage/semantic layout và 4 previews | DD08/C14 real data, PH08 DOCX/storage/export |

Hoàn thành phần consumer độc lập PD; chưa nghiệm thu production integration.
Không có production mock/default fake model/tool/checkpointer.

## File hiện tại

- Reception graph: `agent-reception/src/graph/{__init__,budget,decision,factory,intake,state,workflow,workflow_contracts,workflow_validation}.py`.
- Reception prompts: `agent-reception/src/prompts/{__init__,pd01,workflow}.py`.
- Graph tests: `agent-reception/tests/graph/{conftest,workflow_fixture,test_factory,test_intake,test_workflow,test_workflow_failures}.py`.
- Evals: `agent-reception/tests/evals/test_reception.py`, `reception.vi.json`.
- Report config: `agent-report/schemas/{__init__,config}.py`, `config-v1.schema.json`.
- Report template/prompt/config examples: `agent-report/templates/{operations-v1,metric-contracts-v1}.json`,
  `agent-report/prompts/report-v1.md`, `agent-report/examples/management-{a,b}.json`.
- Preview generator: `agent-report/examples/generate_preview.py`, `preview-{complete,partial,empty,error}.html`.
- Server reporting modules: `server/src/reporting/{narrative,layouts}/{__init__,operations}.py`.
- Report tests: `server/tests/reporting/narrative/test_operations.py`.

27 Python files thay thế 22 TypeScript files do PD viết và bổ sung init/test setup.
Bảng đối chiếu file đã xóa ở [PYTHON_MIGRATION](PYTHON_MIGRATION.md).
Không sửa backend/HTTP/auth/persistence, DB/migration/UI/Supervisor/entrypoint/worker,
shared contracts hoặc manifest/lockfile của owner khác.

## Lệnh và kết quả đã chạy

Từ repo root, Python 3.11.9, LangGraph 1.2.11, langgraph-checkpoint 4.2.0,
LangChain Core 1.6.0, pytest 9.1.1; không cài thêm dependency:

```powershell
python -B -m pytest -q -p no:cacheprovider agent-reception/tests/graph agent-reception/tests/evals server/tests/reporting/narrative
python -B agent-report/examples/generate_preview.py
python -B -m ruff check agent-reception/src/graph agent-reception/src/prompts agent-reception/tests/graph agent-reception/tests/evals agent-report/schemas agent-report/examples server/src/reporting/narrative server/src/reporting/layouts server/tests/reporting/narrative
python -B -m ruff format --check agent-reception/src/graph agent-reception/src/prompts agent-reception/tests/graph agent-reception/tests/evals agent-report/schemas agent-report/examples server/src/reporting/narrative server/src/reporting/layouts server/tests/reporting/narrative
git diff --check
```

Kết quả lượt chuyển Python: **137 pass, 0 fail**; gồm 12 eval tiếng Việt. AST parse
27 files đạt; không còn TS trong các folder PD đã chuyển. Ruff lint/format đạt,
preview tạo đủ 4 trạng thái. Runtime TypeScript còn lại chạy riêng: **25 pass, 0 fail**,
47 assertions/5 files; Reception `tsc --noEmit` đạt. Bootstrap tests cần rerun ngoài
sandbox sau approval vì EPERM spawn; rerun đạt, không sửa tests owner khác.
Không chạy full server suite hoặc network/service integration.

Lượt chỉnh tài liệu sau chuyển đổi chỉ kiểm tra collect-only, đường dẫn/API/lệnh,
Markdown links và diff; không ghi các kết quả code test trên thành lần chạy mới.

## Giới hạn và request

Python symbols snake_case nhưng wire JSON giữ PH01/schema-v1; consumer contract
`0.1.0-python.draft.1`, generic marker `pd01-python-1`, business marker
`pd-workflow-python-1`. Từ chối checkpoint TS/topology khác, không reset/migrate tự động.
PH chốt package namespace/dependency pins/transport/deployment và persistent saver.
TS không import trực tiếp `.py`; production cần bridge hoặc Python composition owner.

Chưa real backend tools/ACL/files, RAG/policy/model, durable restart/multi-replica/
fencing/inbox/outbox/revoke; chưa Report publish/consistent snapshot/grants revoke,
DOCX/storage/export/download. Unit/consumer mocks chỉ ở tests; preview synthetic chỉ
examples chạy thủ công. Owner guard không thay auth; timeout không chứng minh rollback.

Thiết kế: [WORKFLOW_DESIGN](WORKFLOW_DESIGN.md).
Requests: [PYTHON_RUNTIME_INTEGRATION](../../requests/phan-dung/PYTHON_RUNTIME_INTEGRATION.md),
[PD03_PD08_INTEGRATION](../../requests/phan-dung/PD03_PD08_INTEGRATION.md).
Handoff riêng: [PD01](PD01.md), [PD02](PD02.md), [PD03](PD03.md), [PD04](PD04.md),
[PD05](PD05.md), [PD06](PD06.md), [PD07](PD07.md), [PD08](PD08.md).
