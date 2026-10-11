# C3 — Protocol validation ↔ Builder

Ngày: **2026-10-11**. Owner: **Bùi Hữu Nghĩa**. Branch: `feat/wf-builder`.
Baseline: `67ff8715e4a40a37538b727442b3b66f2c9223e1`, chứa C1/C2.
Thay đổi hiện chưa commit/push.

## Trạng thái và phạm vi

**Đã triển khai và kiểm thử C3 theo trình tự chung; code sẵn sàng review/bàn giao.**
C3 chỉ nối protocol validation thật vào Builder Phase B. Đầu vào là C1/C2 và
contracts/validator Phase B đã merge; không chờ C5 hoặc toàn bộ Builder production.
Xem [PLAN_C3.md](PLAN_C3.md) và [trình tự chung](../PHASE_C_SEQUENCE.md).

Đã gỡ phần mở rộng trước đó: SQL session/message, durable service, manifest
generator, draft journal/recovery và DDL Builder. `ProposalService`/reuse giữ
logic Phase B, session vẫn process-local, confirm không tự tạo draft. UI Phase B
không đổi. Không sửa module của thành viên khác, migration/root/dependency.

## Output

Import từ `agentscope.app.workforce.builder`:

| Export | C3 sử dụng |
|---|---|
| `RegistryProtocolReadiness` | Public exact `resolve_detail(scope, ref)` C2 → readiness có correlation, event/per-event facts, completion, timeout và query version; kiểm tra ref/hash |
| `RegistryCapabilitySelector` | Tận dụng checks Phase B với provider C2; pin terminal external protocol mà không ép polling |
| `ProtocolBuildValidator` | Hook kiểm tra capability/binding/protocol pins, current enabled protocol và validator Lifecycle trước create/update draft |

Không có DB engine/table, policy writer, draft provider hoặc background worker
mới trong Builder. Scope ở caller phải được resolve từ principal/membership C1.

## Wiring và trách nhiệm caller

Ví dụ dependency injection, không phải script production chạy độc lập:

```python
from agentscope.app.workforce.builder import (
    ProposalService, ProtocolBuildValidator, RequirementExtractor,
    RegistryCapabilitySelector, RegistryProtocolReadiness,
)

# C1/C7 resolve/check active identity trước khi vào Builder.
# C2 provider dùng canonical workforce_database.uows.
readiness = RegistryProtocolReadiness(protocol_provider.resolve_detail)
selector = RegistryCapabilitySelector(registry_port, scoped_protocol_port, readiness)
builder = ProposalService(RequirementExtractor(structured_model), selector, reuse_port)
prewrite = ProtocolBuildValidator(selector, async_draft_validator.validate)

# item phải lấy từ proposal server-held đã được confirm đúng revision.
# manifest lấy từ đường build server, không nhận selection tự khai từ UI.
report, evidence = await prewrite.validate(scope, confirmed_item, manifest)
if not report.valid:
    raise ValueError("Draft protocol validation failed")
# Sau gate này, caller dùng canonical DraftPort.create_draft/update_draft.
# Hook chỉ validate, không sở hữu transaction/identity/persistence của Lifecycle.
```

Tạo/bind protocol port theo đúng server Scope, không dùng port manager A cho
request manager B. Builder chỉ dùng `get_snapshot`, capability coverage và exact
resolver; không query trực tiếp Registry tables. Loader normalization của C2 là
dependency composition, Builder không triển khai inbox loader hoặc normalize event.

`ProtocolBuildValidator.validate(scope, item, manifest)`:

- Chặn unresolved requirement/selection blockers.
- So agent key, capabilities, bindings và protocol hashes với item server-held.
- Recheck current enabled protocol qua selector rồi gọi validator Lifecycle.
- Nếu report valid, so policy payload/ref được resolve với policy đã đề xuất.
- Trả `(report, evidence)`; invalid report hoặc exception phải chặn draft write.
  Hook không xác minh user confirmation thay caller và không đảm bảo atomic
  protocol-check + Lifecycle-write; Lifecycle/composition giữ trách nhiệm đó.

## Hành vi đã kiểm chứng

- Read-only không đòi event channel/protocol.
- Terminal create-only có exact protocol pin, không tự thêm tracking/polling.
- Tracking dùng correlation, event/fact metadata, timeout và query binding thật.
- Old immutable pin vẫn đọc được; current pin thay đổi làm recheck thất bại.
  Proposal Phase B confirm refresh revision và yêu cầu xác nhận lại khi drift.
- Disable trước confirm/pre-write chặn; wrong Scope hoặc detail lệch hash chặn.
- Manifest lệch pin/binding hoặc resolved policy đổi human_confirmation bị chặn.
- Query-only chưa có event/fact semantics block `POLICY_EVENT_SEMANTICS_UNRESOLVED`;
  create-only pending block `CREATE_ONLY_PENDING_POLICY_UNRESOLVED`. Đây là
  supported blocking behavior theo contract hiện hữu, không tự hạ yêu cầu.

## Kiểm tra

Từ `platform_VP/agentscope`:

```powershell
.\.venv\Scripts\python.exe -m unittest tests.workforce.builder.phase_c.test_integration -v
.\.venv\Scripts\python.exe -m unittest tests.workforce.builder.async_capabilities.test_phase_a tests.workforce.builder.async_capabilities.test_phase_b -q
.\.venv\Scripts\python.exe -m unittest discover -s tests/workforce/registry/event_protocols -p 'test_*.py' -q
.\.venv\Scripts\python.exe -m unittest tests.workforce.foundation.phase_c.test_foundation tests.workforce.foundation.test_contracts tests.workforce.foundation.async_api.test_phase_b -q
.\.venv\Scripts\python.exe -m unittest discover -s tests/workforce/lifecycle/async_evaluation -p 'test_*.py' -q
```

| Suite/check | Kết quả |
|---|---|
| C3 protocol → Builder | 16 pass |
| Builder A/B regression | 31 pass |
| Registry | 29 pass, 1 PostgreSQL gate skipped |
| Foundation A/B/C1 | 29 pass |
| Lifecycle | 24 pass, 1 baseline failure |
| Compileall / Black changed Python files / whitespace / ownership | Pass |
| Import Builder core | Không eager-load sqlalchemy |

Suite C3 đã thay thế suite 35 test rộng trước đó. Các số cũ không áp dụng cho
bản C3 đã thu gọn. Dùng C1 UOW và C2 SQL repository/provider cùng
`AsyncDraftValidator` thật; SQLite qua async facade của test Foundation. Model,
tool catalog/reuse và immutable policy resolver là test doubles trong tests của
Nghĩa. Không có draft write, policy store hoặc production fake trong C3 code.
Loader test raise nếu normalization bị gọi.

Lifecycle baseline failure:
`ValidationTests.test_builder_query_only_dialect_explicit`,
`tests/workforce/lifecycle/async_evaluation/test_phase_b.py:262`.
Fixture dùng policy legacy; đã tái hiện cùng lỗi với Builder nguyên bản HEAD.
Không sửa test/schema của Anh hoặc nới policy để che lỗi.

## Giới hạn bàn giao

Chưa có dedicated PostgreSQL DSN; không tuyên bố row-lock/concurrency PostgreSQL,
production runtime, kill/restart E2E hoặc hoàn thành Phase D. C2 đang dùng
PermissionError cho cả disable/wrong Scope; consumer chặn, không phân loại bằng
message. Ref chưa có head revision; recheck current pin không phải atomic CAS
xuyên module. Root/API/migration thuộc C7; không là blocker review C3 này.

Không cần thêm output C5 của Anh. Các lưu ý phối hợp, không phải danh sách
blocker C3, nằm trong [INTEGRATION_REQUEST_BHN_C3.md](INTEGRATION_REQUEST_BHN_C3.md).
