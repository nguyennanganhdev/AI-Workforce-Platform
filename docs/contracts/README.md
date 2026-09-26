# Contract-first handoff

**Trạng thái:** draft contract cho các team bắt đầu tích hợp; chưa phải API business ổn định.

| Contract | Nguồn |
|---|---|
| Actor / tenant / subject / scope | `shared/platform/context.ts` |
| DomainAdapter / evidence / capability | `shared/platform/domain-contracts.ts` |
| ActionProposal / validation / receipt | `shared/platform/action-contracts.ts` |
| Runtime transport | `shared/platform/runtime-contracts.ts` + Python `src/contracts/runtime.py` |
| Runtime implementation interface | `agent-runtime/src/runtime/base.py` |
| Event envelope | Hai file `events.ts` riêng ở shared platform và Vinhomes |
| Incident/Task/WorkOrder status | `shared/domains/vinhomes/state-machines.ts` |
| HTTP hiện có | [platform.openapi.yaml](platform.openapi.yaml) |
| HTTP domain | [vinhomes.openapi.yaml](domains/vinhomes.openapi.yaml), chưa có path |

Các contract AgentSpec/capability/evaluation, property/intake/action/work-order/evidence sẽ thêm
khi triển khai use case tương ứng theo ERD; không dựng DTO đầy đủ khi schema validation chưa được review.

## Conventions draft

- JSON dùng camelCase; timestamp UTC ISO 8601. ID là opaque string, persistence có thể dùng UUID theo ERD.
- RequestContext mang tenantId/actor/correlationId/traceId và được tạo sau authentication.
- Subject dùng namespace + subjectType + subjectId; tenant lấy từ trusted context và kiểm tra tại domain.
- ActionProposal mang producer snapshot và idempotencyKey; correlation/trace/actor nằm trong RequestContext.
- So với ví dụ `target` trong ERD, draft dùng `subject: DomainSubjectRef`; mapper domain chịu trách nhiệm chuyển sang target nghiệp vụ.
- Idempotency theo `(tenant_id, idempotency_key)` từ ERD. Key phải phân biệt command; cùng key khác payload bị từ chối.
- Evidence chỉ lộ fileObjectId đã kiểm quyền; URL truy cập/signed URL do file service cấp sau authorization.
- RuntimeSessionRef chứa tenantId; transport vẫn phải xác thực service và authorize session, không tin ID từ client.
- Runtime DTO được mirror TS/Python bằng tay ở phase khung. Trước khi mở transport, chọn schema validation/codegen và thêm contract round-trip test.
- TypeScript interface, Python TypedDict và status union **không thay thế runtime validation hoặc transition guard**.

## Khi sửa contract chung

Owner producer và consumer review cùng PR; cập nhật TS/Python/OpenAPI tương ứng.
Breaking change phải có version/migration plan trước khi consumer được deploy độc lập.
Execution grant chưa có wire format: Vinhomes + Integrations chốt signing/verifying, expiry,
payload binding, replay protection và idempotency trước MCP WRITE đầu tiên.
