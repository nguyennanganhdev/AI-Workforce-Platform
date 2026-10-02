# PH01 — Đề xuất port nội bộ Reception

Owner: Phan Hoàng. Ngày: 30/09/2026. Trạng thái: `0.1.0-draft.1`, chưa freeze.
Nguồn type: [contracts/index.ts](../../../../agent-reception/src/contracts/index.ts).
Consumer cần review: Phan Dũng PD01, Dương Dũng DD01, backend Chiến C06.
Không coi tài liệu này là xác nhận đồng thuận hoặc hợp đồng API chính thức.

## Ranh giới và thứ tự gọi

1. PH02 xác minh service identity, lấy context/binding được backend authorize.
   Không cast payload browser/model thành `VerifiedReceptionContext`; không lấy
   tenant, user, permission hoặc framework thread key từ nội dung hội thoại.
2. Entrypoint PH04 inject model, `ReceptionToolPort<Operations>` và checkpointer
   vào factory PD01. Production dùng checkpointer bền vững PH03; không fallback RAM.
3. PD01 gọi tool theo catalog DD01/DD02. Runtime type/schema của request và response
   do DD01 validate theo C01; generic TypeScript chỉ bảo vệ lúc compile.
4. PH03 xử lý checkpoint/lease/fencing và resume; PD01 xử lý state/hội thoại.
   Không tạo DB pool/HTTP server trong graph hoặc tool.

## Semantic cần giữ

| Port | Quy ước |
|---|---|
| `VerifiedReceptionContext` | `principalId` là execution/service principal, `initiatedBy` là user; `requestId` dùng correlation. `checkpoint.threadId/namespace` được backend resolve, chỉ lưu nội bộ và không suy ra từ ID browser. Tên type không phải bằng chứng auth. PH02 phải kiểm tra lại ownership cho read/run/resume. |
| `ReceptionToolPort` | Catalog ánh xạ operation sang input/output cụ thể. `timeoutMs` là budget dương do caller chọn, DD01 validate/enforce; `signal` hủy request đang chạy. |
| Idempotency | Key thuộc operation bền vững, lưu trước side effect, giữ qua retry; không dùng mỗi `runId`. PH03 và DD01 chốt persistence/reconciliation. |
| Tool result | `success` là kết quả hoàn thành; `accepted` chỉ nhận operation; `failure` có `retryable` và `outcome`. `unknown` cần truy hồi kết quả theo cùng key, không khẳng định mutation thất bại. Mã lỗi map từ C01, chưa tự đặt API mới. |
| Graph read/run/resume | Mọi thao tác có context đã xác minh. `completed` nghĩa lượt graph hoàn tất, không tự đóng ticket. State chi tiết vẫn thuộc PD01. |
| Graph stream | Dùng stream **hoặc** run/resume cho một operation, không gọi cả hai làm chạy hai lần. Stream nhận start hoặc resume request; gửi delta và đúng một terminal result. Result là dữ liệu nội bộ, PH02 phải map/allowlist trước khi gửi UI; không phát full state/checkpoint. |
| Interrupt/resume | Không giữ HTTP chờ nhân viên; persist interrupt rồi kết thúc stream. Resident reply khác backend event. PH03 kiểm tra interrupt, binding, ticket, generation và version trước resume; duplicate event không thực thi lại. |
| Cancellation | `AbortSignal` hủy lượt đang chạy là hợp đồng hiện có. Durable cancel/revoke và cleanup side effect còn phải chốt PH03/C06; abort không rollback mutation đã hoàn thành. |

`ReceptionResumeEvent` hiện mang khóa định danh/version, không sao chép DTO sự kiện
backend. Event adapter PH03 validate nguồn và ánh xạ từ C01/C08; nội dung cần thiết
đọc lại qua authorized tools. Browser không được tự chọn `source.kind = backend`.

## State version và tương thích

Envelope bắt buộc `schemaVersion: 1`. PH01 không đặt intake/facts/assessment state
thay PD01. PD01 bổ sung business shape và chốt bản đầu tiên trước khi lưu checkpoint
production. Đổi shape phá tương thích phải tăng state/contract version, có migration
được test hoặc từ chối resume phiên cũ có kiểm soát. Không reset phiên/ticket âm thầm.
PH03 phải kiểm tra version trước khi đọc/resume; hiện mới có type envelope,
chưa có production checkpoint reader/migration.

## Bằng chứng và việc cần review

- `tests/runtime/contracts.typecheck.ts`: consumer gọi được các port; sai operation,
  payload, timeout, checkpointer hoặc schema version bị TypeScript từ chối.
- `tests/integration/framework-capabilities.test.ts`: framework LangGraph đã pin
  chạy được model/tool injection và checkpoint/stream/interrupt/resume trong test.
- Chưa có graph PD01 hay backend DD01 thực để chạy contract integration liên module.
- Chưa freeze event/result mapping, state chi tiết, durable cancellation, framework
  binding lookup và timeout policy. Theo dõi tại [request](../requests/phan-hoang/PH01_DEPENDENCIES.md).
