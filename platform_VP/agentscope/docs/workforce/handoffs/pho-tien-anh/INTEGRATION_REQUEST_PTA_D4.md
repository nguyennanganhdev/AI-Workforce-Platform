# Điểm ghép D4 — Phó Tiến Anh

> **Cập nhật 12/10/2026:** PR #73 đã merge vào `develop2@35cec29`. Nguyễn Chí
> Hoàng đã hoàn thành, commit và merge phần migration/API/auth/composition/CI
> qua commit/PR chứa cập nhật status này. Tài liệu này là input lịch sử; trạng
> thái thực thi mới nhất nằm tại
> `../nguyen-chi-hoang/PHASE_D_D4_INTEGRATION.md`.

Ngày **12/10/2026**.

## NCH — additive migration, auth/composition và CI tích hợp cuối Phase D

Import metadata từ `lifecycle.releases.get_release_metadata()`. Thêm revision
mới sau head đã merge; không sửa migration `0010_workforce_runtime` đã phát hành
và không import mutable runtime metadata vào nội dung migration đã đóng băng.

| Bảng | Key/nội dung |
|---|---|
| `wf_release_candidates` | PK Scope + draft_id; agent_id, revision, frozen input + hash |
| `wf_published_versions` | PK Scope + version_id; agent_id, immutable PublishedVersion JSON + hash |
| `wf_agent_deployments` | PK Scope + deployment_id (= stable agent_id); active version, revision, archived/enabled |
| `wf_release_commands` | PK Scope + command_id; request hash và committed result; publish/rollback dùng cùng namespace |

Không có cascade/delete hoặc runtime create_all. Schema local ở
[phase_d/schemas.json](phase_d/schemas.json); model/table definitions là nguồn
chuẩn. Source A/C metadata/schema cũ không đổi. Cần upgrade/downgrade/upgrade,
PostgreSQL row-lock gates và review DDL trước rollout. Downgrade có pending
workflow/version references không được dùng làm rollback vận hành.

Ghép service với Foundation UOW và IdentityPort thật:

```python
releases = SqlReleaseService(database.uows, transactional_validator, identity)
# Manager endpoint resolves identity.resolve_manager(authenticated_principal),
# enforces owner action and loads current ReleaseContext from server config.
await releases.stage_candidate(scope, frozen, expected_revision, canonical_uow)
result = await releases.publish_selected(scope, selections, context, command_id)
```

Chỉ manager endpoint có quyền publish/rollback/settings; không expose mutation
cho partner/grant submit/read. `ReleaseContext` không lấy từ request body.
Service recheck current membership trong UOW trước mutation và idempotent replay.
`stage_candidate(..., uow=...)` không commit: canonical draft writer phải gọi
trong cùng transaction với **mọi edit**, cùng stable IDs/revision và snapshot
mới cho re-eval. Không đồng bộ mirror bằng job hoặc gọi hook sau commit.

`PublishedCatalogPort` có service concrete qua `list_candidates`, `get_version`,
`get_deployment`. Composition bootstrap phải chọn current version từ catalog,
ghi nguyên version/protocol refs vào checkpoint, tạo session/group riêng từng
ticket. Runtime lookup exact version không thay bằng current head.

Lệnh CI owner suite:

```bash
PYTHONPATH=src:tests/workforce/fixtures python -m pytest tests/workforce/lifecycle/releases --import-mode=importlib -q -rs
```

`WORKFORCE_TEST_POSTGRES_URL` phải là DSN test riêng. Bốn gates tạo schema
ngẫu nhiên và chỉ drop schema đó: concurrent publish, same-command retry,
edit bị serialize với publish, cancellation bị serialize với publish commit.
Local skip không được tính là pass CI PostgreSQL.

## NPD/NCH + Lifecycle — transactional dependency validator

Seam local đã có, chưa promote shared:

```text
ReleaseValidator.validate(scope, manifest, canonical_uow)
  -> (ValidationReport, dependency_payload)
```

Callback resolve current tools/protocol heads, exact protocol detail và immutable
policy theo Scope, dùng lại AsyncDraftValidator/validate_async_draft semantics.
Phải lock/CAS các head/availability/credential/policy revision liên quan tới
commit; các writer của Registry phải cùng tuân theo lock/CAS này. Không có
model/provider call, không commit caller UOW. Signature shared RegistryPort
hiện chưa có `uow` cho các read nên cần adapter transaction-bound/owner hook;
không dùng nhiều independent reads rồi tuyên bố atomic dependency validation.

Tests D4 dùng C2 SQL repo trong transaction-bound facade, SQL head lock và
test-only tool/policy catalog. Đây là minh họa kiểm thử, không concrete adapter
production. Không copy fixture vào production. Publish/rollback fail closed khi
dependency/policy hash hoặc suite/runtime/context khác evaluation. Protocol
v1 của operation đang chạy vẫn cần retained exact resolver sau revise/disable.

## PHH — guard và usage/checkpoint retention

```python
authorization = PinnedVersionAuthorization(existing_authorization, releases)
# Inject into WorkflowService.authorization before production bootstrap.
```

Giữ delegate actor/route/consent checks. Adapter kiểm tra version availability
và full protocol refs; PHH ExecutionGuard đã gọi authorize_trigger trước
effect và trước final commit. Final UOW giữ deployment lock để disable không
lọt khe validation→commit. Không áp published-catalog guard cho eval candidate
chưa publish; isolated eval giữ auth/guard C5 riêng.

`VersionUsageReader.references(scope, version_id) -> Sequence[str]` cần adapter
owner đọc workflow/checkpoint/group/operation refs chính xác. Lifecycle chỉ gọi
port. `retention_references` không cho phép xóa: D4 chưa có purge/TTL và giữ
toàn bộ version/evaluation, kể cả sau close/archive/rollback/disable. Purge sau
này phải thêm replay/audit retention và serialize usage allocation với deletion.

Sau revoke agent, provider fact vẫn được PHD commit; adapter trả false cho
public delivery/wakeup. Agent disabled khi approval job đã enqueue sẽ được PHH
đưa blocked_authorization với zero model/tool call, pin không đổi.

## PHD — E2E tích hợp cuối Phase D

Tái dùng exports và [test_long_wait.py](../../../../tests/workforce/lifecycle/releases/test_long_wait.py):
raw signed HTTP, provider inbox, workflow/checkpoint/lease/evidence thật với
D3CaseDriver; published v1, chờ 200 ngày bằng clock, v2/rollback/archive,
protocol revise+disable, worker reload rồi event resume v1; duplicate/idle
không thêm calls. Ca revoke giữ operation completed nhưng không public output.

E2E cuối cần ghép catalog bootstrap thật, manager release API, transactional resolver
và migration sau khi NCH cung cấp; chạy toàn lát cắt Customer POST → Leader →
ExternalOperation → Provider Event → resume → event log/SSE → close. Tests D4
không tự mở phase mới hoặc nhận task sandbox. Canonical concurrent-build uniqueness
ở yêu cầu BHN-D3-WRITE chưa được chứng minh bởi release CAS này.
