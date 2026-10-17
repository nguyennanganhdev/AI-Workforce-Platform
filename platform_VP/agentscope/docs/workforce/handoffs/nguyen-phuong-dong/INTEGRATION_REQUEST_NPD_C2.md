# Integration request — Registry C2 → C3/C7

Ngày: **2026-10-11**. Producer: Registry / Nguyễn Phương Đông.
Baseline đầu vào: `a4c2fddac720bb155efaa01eb91266b95f7b7181`.

## Phan Hoàng Dũng — C3 Execution

- Khởi tạo `SqlAsyncProtocolProvider` bằng canonical UOW factory C1.
- Bind `AsyncProtocolService` theo Scope đọc từ persisted ExternalOperation.
- Inject loader đọc provider inbox thật; loader phải đối chiếu actor, tenant,
  provider integration, envelope hash, inbox ID và received-at.
- Persist đủ `VerifiedProviderContext`; không rút thành dict thiếu credential,
  signing key hoặc thời gian xác thực.
- Truyền `protocol_provider.resolve_detail` vào `ExecutionProtocolAdapter`.
- Không dùng fake `FakeAsyncProtocolPort` trong production composition.

## Bùi Hữu Nghĩa — C3 Builder

- Dùng `AsyncProtocolPort.get_snapshot` và
  `validate_capability_coverage`; không query bảng trực tiếp.
- Recheck current enabled protocol/catalog revision trước tạo hoặc sửa draft.
- Manifest chỉ lưu exact snapshot ref/hash; không lưu current pointer động.

## Nguyễn Chí Hoàng — C7 migration/composition

Tạo migration mới sau head thực tế, không sửa `0009`. Thu metadata từ
`registry/event_protocols/_tables.py`:

- `wf_async_protocol_versions`, unique
  `uq_wf_proto_version_identity` trên full Scope + tool version + protocol ID +
  protocol version; index `ix_wf_proto_version_hash`.
- `wf_async_protocol_heads`, unique `uq_wf_proto_head_scope_tool` trên full
  Scope + tool version; check revision >= 1; index
  `ix_wf_proto_head_enabled`; foreign key
  `fk_wf_proto_head_current_version` trỏ tới đúng immutable version, không
  cascade-delete.
- Version content là immutable JSON. Head giữ full snapshot reference,
  enabled state và revision CAS; không cascade-delete version đang được
  operation/workflow pin.

Root composition inject cùng `WorkforceDatabase.uows` cho Foundation, Registry
và Execution. Không tạo engine hoặc transaction manager thứ hai.

## Giới hạn bàn giao

C2 đã chứng minh SQL semantics bằng SQLite và chuẩn bị PostgreSQL concurrency
gate. Chưa có DSN để chạy gate PostgreSQL, chưa có provider inbox C3 và chưa có
root production bootstrap C7; không gọi đó là E2E production.
