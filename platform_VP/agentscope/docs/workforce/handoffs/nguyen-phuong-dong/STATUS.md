# Trạng thái — Nguyễn Phương Đông

## Cập nhật Phase D/D2 — 2026-10-12

Nguyễn Chí Hoàng đã thực hiện thay lane D2 trên baseline
`develop2@5e66ea0`. Protocol drift/disable/exact pinned snapshot đã có acceptance
SQL và **30 pass, 1 PostgreSQL gate skip, 76 subtests pass**. Thay đổi còn trong
working tree, chưa merge. Xem [PHASE_D_D2.md](PHASE_D_D2.md).

## Cập nhật Phase C/C2 — 2026-10-11

Owner theo kế hoạch: **Nguyễn Phương Đông**. Người thực hiện thay trong lượt
này: **Nguyễn Chí Hoàng**. Baseline đầu vào:
`dev_TeamHoang@a4c2fddac720bb155efaa01eb91266b95f7b7181`.

C2 đã được triển khai và kiểm tra trong working tree, chưa commit/push/merge:

- SQL metadata cho `wf_async_protocol_versions` và
  `wf_async_protocol_heads`, tách immutable version khỏi current/enabled head.
- `SqlAsyncProtocolRepository` dùng UOW C1, full Scope isolation, exact old-pin,
  immutable conflict, revision CAS và PostgreSQL row lock.
- `SqlAsyncProtocolProvider` bind `AsyncProtocolService` theo Scope và cung cấp
  exact detail resolver cho `ExecutionProtocolAdapter`.
- Không sửa Execution, migration `0009`, shared contract hoặc root bootstrap.
  Provider inbox loader thật vẫn là output C3 của Phan Hoàng Dũng; migration và
  composition cuối vẫn thuộc C7 của Nguyễn Chí Hoàng.

Kiểm tra Registry hiện tại: **29 pass, 1 PostgreSQL gate skip**. Gate bị skip vì
chưa có `WORKFORCE_TEST_POSTGRES_URL`; SQLite không được dùng để tuyên bố đã
chứng minh PostgreSQL concurrency. Regression Foundation **19/19** và
Orchestration **14/14** pass. Bộ Execution cũ cần `pytest`, nhưng `.venv` hiện
không có runner này; test tích hợp trực tiếp với `ExecutionProtocolAdapter`
trong suite Registry đã pass.

Chi tiết: [PHASE_C_C2.md](PHASE_C_C2.md). Yêu cầu tích hợp cho các bước sau:
[INTEGRATION_REQUEST_NPD_C2.md](INTEGRATION_REQUEST_NPD_C2.md).

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

## Điều phối Phase C — cập nhật sau khi triển khai C2 ngày 2026-10-11

Bạn là owner **C2**, người code ngay sau C1. C2 đã dùng đúng commit chung chứa
đủ Phase B và C1 nêu ở phần cập nhật trên; không lấy lại output từ branch cũ.

Output C1 có thể dùng: `SqlAlchemyUnitOfWorkFactory`,
`SqlDurableJobRepository`, `SqlIdentityPort`, `SqlPartnerRoutingPort`,
`VerifiedProviderContext`, `WorkforceBootstrap`; migration head nền là
`0009_workforce_foundation`. Không tạo engine/UOW/migration riêng trong Registry.

Phạm vi C2 đã hoàn thành ở phía Registry: nối `AsyncProtocolRepository`
production bằng injected session/UOW, exact pinned detail resolver và hợp đồng
normalizer nhận context từ persisted provider inbox. Test đã nối Registry SQL
thật với Execution adapter; inbox persistence/loader thật không thuộc Registry
và được bàn giao cho C3/Execution. Table metadata, unique/CAS/index và public
exports đã có cho C7; migration `0009` không bị sửa.

C2 phải được review/merge và commit đầu ra phải được ghi vào tài liệu trước khi
mở hai lane C3. Việc code xong trong working tree không tự động mở gate C3.

Theo dõi thứ tự tại [../PHASE_C_SEQUENCE.md](../PHASE_C_SEQUENCE.md).
