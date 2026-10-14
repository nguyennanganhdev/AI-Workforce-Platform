# D4 — Publish pin, long wait và vòng đời version

Ngày: **12/10/2026**. Owner: **Phó Tiến Anh**

## Đầu vào và phạm vi

Đọc kế hoạch 1.4.3, tài liệu API đối tác, điều phối C/D, README/STATUS/A/B/C5
của PTA và handoff/integration requests từ NCH, NPD, BHN, PHH, PHD. Tài liệu
điều phối chung còn ghi trạng thái cũ D3 chưa mở; lượt này thực hiện D4 theo
chỉ dẫn và trình tự mới của người dùng, không tự sửa trạng thái chung.

- A/B/C5: dùng lại scoped validator, frozen snapshot/suite/gates, SQL report,
  RuntimeEvaluationRunner và kiểm tra committed evidence trước release.
- NCH C1/C7/D1: canonical UOW, IdentityPort, jobs/worker; không thêm migration,
  dependency hoặc CI trong vùng owner khác.
- NPD C2/D2: current protocol head và immutable exact version. Drift/disable
  chặn selection/publish mới; operation/workflow cũ giữ normalizer exact pin.
- BHN C3/D3: giữ schema/policy, full Scope và metadata/ref; dùng selection CAS
  và không phát hành draft ngoài danh sách. Candidate staging không thay thế
  business-key allocation/unique constraint của canonical writer.
- PHH C4/D2: dùng continuation/ExecutionGuard/authorization và persisted
  workflow/checkpoint; không có runtime thứ hai hay viết vào wf_workflows.
- PHD C6/D3: dùng D3CaseDriver, raw HMAC ingress/inbox/processor, approval/query
  adapters và shared ticket fixture; không sửa assertions/fixture owner khác.

## Output

`src/agentscope/app/workforce/lifecycle/releases/` cung cấp:

| Export | Hành vi |
|---|---|
| `SqlReleaseService` | Stage candidate CAS, atomic publish selections/idempotency, rollback/current compatibility, scoped catalog và availability |
| `ReleaseSelection`, `ReleaseContext`, `PublishedVersion` | DTO local dùng shared Scope/Manifest/FrozenEvaluation; context hiện hành lấy từ server |
| `ReleaseValidator` | Bắt buộc current dependency validation trong injected UOW; không có fallback fake thành công |
| `PinnedVersionAuthorization` | Adapter WorkflowAuthorization: recheck exact agent/protocol pins, archive cho old pin, disable/revoke chặn continuation |
| `VersionUsageReader`, `retention_references` | PHH cung cấp usage/checkpoint refs theo Scope; Lifecycle không scan bảng PHH |
| `get_release_metadata`, `phase_d_schema_bundle` | Bốn bảng additive và [schema local](phase_d/schemas.json), `pta-release-1` |

`check_persisted_release(..., uow=None)` nay hỗ trợ injected UOW. Khi release
truyền UOW, repository đọc report/case/observation/evidence trong cùng transaction
và khóa cancellation marker tới commit. Không commit UOW của caller; caller
vẫn kiểm soát activation. Signature cũ và artifact A/C được giữ nguyên.

Publish giữ candidate version ID và toàn bộ frozen input; không đổi manifest/hash
sau eval. Candidate revision/deployment revision và command payload được kiểm tra
phía server. Một item stale làm rollback cả danh sách. Versions không ghi đè;
request mất response sau commit replay cùng kết quả, không tạo version khác.

Archive chỉ chặn catalog/publish/rollback mới. Exact lookup/continuation old pin
vẫn được phép nếu agent/owner còn active. Disable/revoke chặn model/tool tại
guard; PHH ghi blocked_authorization khi job đang chờ chạy. Provider fact thực
vẫn được Execution lưu nhưng không public message/wakeup sau revoke.

Rollback chỉ đổi deployment head sau ownership, current dependency và retained
evaluation check. Run/checkpoint đang chờ giữ version/protocol/session cũ. D4
giữ version/eval vô thời hạn, không thêm purge/TTL; không xóa reference theo tuổi
workflow hoặc theo publish/archive. Public history/inbox retention vẫn thuộc
PHH/PHD/Foundation theo policy chung.

## Kiểm chứng

Ma trận D4 gồm **28 tests SQL/mock** và **4 PostgreSQL gates**. Long-wait
fixture tiến shared clock 200 ngày, dispose pool, dựng worker mới và đọc lại
DB. Workflow pending vẫn có checkpoint/version/protocol/session pin v1 qua
publish v2/rollback/archive/protocol revise+disable; signed event cũ được apply
một lần, không create lại. Idle/duplicate không thêm model/provider call.

Lệnh từ `platform_VP/agentscope`:

```bash
PYTHONPATH=src:tests/workforce/fixtures:tests/workforce/registry/event_protocols:tests/workforce/orchestration/async_workflows .venv/bin/python -m pytest tests/workforce/lifecycle tests/workforce/foundation tests/workforce/builder tests/workforce/registry tests/workforce/orchestration/phase_c --import-mode=importlib -q -rs
PYTHONPATH=src:tests/workforce/fixtures:tests/workforce/registry/event_protocols .venv/bin/python -m pytest tests/workforce/execution tests/workforce/e2e --import-mode=importlib -q -rs
PYTHONPATH=src .venv/bin/python -m unittest discover -s tests/workforce/orchestration/async_workflows -t . -p 'test_*.py' -q
.venv/bin/python -m black --check src/agentscope/app/workforce/lifecycle/releases src/agentscope/app/workforce/lifecycle/async_evaluation/_jobs.py src/agentscope/app/workforce/lifecycle/async_evaluation/_repository.py tests/workforce/lifecycle/releases
.venv/bin/python -m flake8 --jobs=1 --max-line-length=88 src/agentscope/app/workforce/lifecycle/releases src/agentscope/app/workforce/lifecycle/async_evaluation/_jobs.py src/agentscope/app/workforce/lifecycle/async_evaluation/_repository.py tests/workforce/lifecycle/releases
.venv/bin/python -m mypy src/agentscope/app/workforce/lifecycle/releases src/agentscope/app/workforce/lifecycle/async_evaluation/_jobs.py src/agentscope/app/workforce/lifecycle/async_evaluation/_repository.py --follow-imports=skip --ignore-missing-imports --disallow-untyped-defs --disallow-incomplete-defs
```

Kết quả: **233 passed, 17 skipped, 213 subtests passed** ở nhóm
Lifecycle/Foundation/Builder/Registry/C4; **134 passed, 8 skipped, 3 subtests
passed** ở Execution/E2E. Trong đó D4 **28 pass**, **4 PostgreSQL skip**.
Black/Flake8/mypy **8 source files** pass. Skips còn lại cần PostgreSQL,
Builder demo URL hoặc full-platform factory; không tính skip là pass.
Kết quả và giới hạn được ghi ở [STATUS.md](STATUS.md).
Type hints phần mới dùng `typing`. JSON Schema/DDL SQLite và PostgreSQL compile;
DTO package import không eager-load SQLAlchemy. Không thay UI/dependency.

## Ranh giới bàn giao

**Cập nhật sau merge:** PR #73 đã merge tại `develop2@35cec29`. Migration,
manager API/auth, transactional validator, catalog/bootstrap, usage reader và CI
đã được Nguyễn Chí Hoàng hoàn thành, commit và merge qua commit/PR chứa cập nhật
status tại
`../nguyen-chi-hoang/PHASE_D_D4_INTEGRATION.md`. Đoạn dưới mô tả trạng thái tại
thời điểm Phó Tiến Anh bàn giao, không còn là trạng thái mới nhất.

Đã có code D4 và regression SQL/mock trong phạm vi Lifecycle. Migration
additive, manager API/auth wiring, transactional dependency adapter, catalog/
bootstrap composition và usage reader production cần owner ghép theo
[INTEGRATION_REQUEST_PTA_D4.md](INTEGRATION_REQUEST_PTA_D4.md).
