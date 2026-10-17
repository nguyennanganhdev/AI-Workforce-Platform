# Phase C/C1 — Foundation production baseline

Ngày triển khai: **2026-10-11**. Owner: **Nguyễn Chí Hoàng**.

## Kết luận gate

Phase A đã hoàn thành 6/6. Trước lượt này, Phase B đã merge 5/6; code Phase B
của Phan Huy Hoàng đã được hoàn thiện và test trong working tree nhưng chưa có
commit/merge trên `develop2`. Vì vậy C1 có thể phát triển và kiểm thử trên cùng
cây mã, nhưng C0 chỉ được coi là đóng trên Git sau khi commit chứa PHH Phase B
và C1 được merge vào baseline chung.

## Output C1

- Canonical `SqlAlchemyUnitOfWork`: explicit commit, rollback mặc định,
  after-commit callback và bridge cho repository dùng AsyncSession.
- `WorkforceDatabase` và migration head `0009_workforce_foundation`.
- Membership một AREA_MANAGER/một scope; đăng ký tạo trạng thái
  `pending_verification`, chỉ membership `verified` mới resolve được Scope.
- Partner route/grant dùng exact manager account, revision và membership
  revision; không broadcast theo area và có kiểm tra residence nếu request gửi
  residence.
- Durable job SQL repository: owner namespace, idempotency hash, claim,
  lease/fencing, heartbeat, retry và terminal failure.
- Provider authentication đúng wire contract: API key + HMAC-SHA256 trên
  `<unix_timestamp>.<raw_body>`, clock skew 5 phút, signing secret lấy bằng
  secret reference, revalidate revoke/expiry/operation trước apply.
- `VerifiedProviderContext` là DTO server-only; body đối tác không được gửi
  tenant, provider integration, Scope hoặc manager ID.
- `WorkforceBootstrap` opt-in vào `create_app`/lifespan và dùng đúng message bus
  của app để tạo request-completion/public-event signals.

Migration C1 chỉ tạo bảng Foundation. Nó không đoán bảng payload của Registry,
Builder, Lifecycle, Workflow hay Execution. Owner bàn giao schema production ở
C2–C6; Nguyễn Chí Hoàng gom migration cuối ở C7.

## Public imports cho bước sau

```python
from agentscope.app.workforce.foundation import (
    HmacProviderAuth,
    SqlAlchemyUnitOfWorkFactory,
    SqlDurableJobRepository,
    SqlIdentityPort,
    SqlPartnerRoutingPort,
    WorkforceDatabase,
)
from agentscope.app.workforce.integrations.async_runtime import (
    WorkforceBootstrap,
    WorkforceFoundation,
)
```

`app.state.workforce` chỉ có giá trị trong lifespan khi caller truyền
`workforce_bootstrap`. C1 không tự bật endpoint hay provider tracking.

## Kiểm tra

```powershell
$env:PYTHONPATH = "src"
.\.venv\Scripts\python.exe -m unittest discover `
  -s tests\workforce\foundation\phase_c -p "test_*.py" -v
.\.venv\Scripts\python.exe -m unittest `
  tests.workforce.foundation.test_contracts `
  tests.workforce.foundation.async_api.test_phase_b -q
.\.venv\Scripts\alembic.exe `
  -c src\agentscope\app\storage\_sql\_alembic\alembic.ini heads
```

Kết quả tại bàn giao: **10/10 C1 tests pass**, **19/19 Foundation A/B pass**,
PHH Phase B **14/14 pass**, Registry **24/24 pass**, Auth core **4/4 pass**;
compileall và schema export pass. Migration được upgrade/downgrade bằng SQLite
test harness và Alembic có đúng một head `0009_workforce_foundation`.

Chưa chạy PostgreSQL concurrency/live provider/Redis multi-process vì không có
dedicated test DSN hoặc credential trong phiên này. Không đọc `.env`, không
thêm dependency và không gọi hệ thống đối tác.

## Gate kế tiếp

C2 thuộc Nguyễn Phương Đông. Chỉ bắt đầu trên commit chung chứa PHH Phase B và
C1. Đông dùng UOW/session factory ở trên để nối AsyncProtocolRepository thật với
Execution; không tự tạo database engine, UOW hoặc migration song song. Nếu cần
thêm bảng protocol, bàn giao metadata/constraint cho Nguyễn Chí Hoàng để đưa
vào chuỗi migration, không sửa `0009` sau khi đã merge.
