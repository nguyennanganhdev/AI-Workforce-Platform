# Trạng thái — Nguyễn Phương Đông

Ngày kiểm tra: 2026-10-10. Branch: `codex/npd-phase-b`.
Baseline: `develop2@53a139b`. Thay đổi Phase B chưa commit/push.
Phase A đã bàn giao qua PR #46 và các sửa review ở baseline hiện tại.

## Tiến độ

**Đã triển khai phần độc lập Phase B của NPD-10–12 theo mục 17.9:** scoped
protocol service, repository boundary, deterministic normalizer production,
detailed pinned snapshot và readiness UI. Fake persistence/auth chỉ trong tests;
production không có storage/auth giả mặc định.

NPD-10–12 chưa hoàn thành nghiệm thu runtime/DB/API/E2E của Phase C/D.
NPD-01–09 catalog/connection/endpoint/API chưa triển khai trong lượt này.
Gate endpoint MCP/SDK còn mở, độc lập với Phase B protocol.

## Files, exports và phạm vi

- registry/event_protocols: giữ models Phase A; thêm AsyncProtocolRepository,
  AsyncProtocolService, normalizer. Service conform AsyncProtocolPort chung;
  thêm publish/CAS-enable và detailed accessor theo exact ref/hash.
- integrations/event_channels: EventChannelsPanel và view model/readiness;
  tái sử dụng Alert/Badge/Button/Table, inject data/retry từ caller.
- tests/workforce/registry/event_protocols: fake repository, service tests;
  fake Phase A dùng normalizer mới. Node self-check dùng Vite/React SSR sẵn có.
- [PHASE_B.md](PHASE_B.md), [INTEGRATION_REQUEST_NPD_PHASE_B.md](INTEGRATION_REQUEST_NPD_PHASE_B.md).
- Không thêm dependency hoặc sửa shared contracts/core MCP/migration/global
  routing/module owner khác. Schema/hash/sample Phase A giữ nguyên và còn test.

## Bằng chứng kiểm tra

Python 3.11.16, virtualenv `/tmp/npd-phase-a-venv`; frontend dùng dependencies
đã cài trong repo. Từ platform_VP/agentscope:

```bash
python -m pytest tests/workforce/registry/event_protocols tests/workforce/foundation/test_contracts.py tests/workforce/execution -q
python -m unittest discover -s tests/workforce/registry/event_protocols -p 'test_*.py' -v
node tests/workforce/registry/event_protocols/test_event_channels.mjs
```

- Pytest: **93 passed, 1 skipped, 73 subtests passed**; Registry 23 tests,
  Foundation contracts 9 tests và regression Execution. PostgreSQL concurrency
  skipped vì chưa có WORKFORCE_TEST_POSTGRES_URL.
- Node: readiness và render house components pass: loading/empty/error/retry,
  create-only/query-only/approval, drift/disable, provider/correlation chưa sẵn
  sàng và không render credential field.
- Unittest discover: **23 tests OK**. TypeScript build, ESLint lane, Vite build,
  Black (79 cột), flake8, add-trailing-comma, compileall và git diff --check: pass.
  Vite còn cảnh báo mime-types/path và chunk lớn ở ứng dụng hiện hữu.

Service tests kiểm tra full Scope isolation, immutable version conflict,
idempotency/CAS, publish không tự bật protocol, disable chặn call mới nhưng
nhận event pin cũ, forged ref/caller mutation, capability coverage, context đọc
lại mỗi event/retry, tenant/namespace/purpose sai, grant error, inbox/time thiếu,
ordering metadata, JSON không hữu hạn và UOW không tự commit. Fake repo chỉ
chứng minh semantics trong process, không chứng minh DB CAS.

## Điểm nối và việc tiếp theo

Phase C: PostgreSQL/session/UOW/migration/composition từ Foundation và verified
inbox reader từ Execution. Context DTO chung chưa bổ sung; callback bắt buộc là
điểm inject nội bộ, không thay wire DTO. Scope/actor từ auth/operation, không từ body.
Execution còn dictionary/hooks ngoài port; chốt adapter trước nối runtime.
UI chưa có API readiness/root route; shell inject transport/token/data khi owner
bàn giao. Requests Phase A/endpoint chưa tự được đóng.

Chưa kiểm tra PostgreSQL concurrency, HTTP/MCP/provider thật, worker/bootstrap,
browser/E2E hoặc sandbox provider; chưa chứng minh gate MB/MC/MD. Không gửi
thông báo sang chat/thành viên khác hoặc tự sửa file của owner khác.
