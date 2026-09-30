# PH01 — Request review và dependency C01/C06/P01

Owner yêu cầu: Phan Hoàng. Ngày: 30/09/2026.
Trạng thái: bản yêu cầu trong repo, **chưa có xác nhận/gửi ngoài repo**.
Không sửa file của owner khác hoặc tự đóng dependency.

## PD01 / DD01 — chốt port nội bộ

Người review: Phan Dũng, Dương Dũng. Nguồn:
[type proposal](../../../../../agent-reception/src/contracts/index.ts),
[semantic](../../integration/PH01_CONTRACTS.md).

- PD01 review `ReceptionGraphFactory<State, Operations>` và graph read/run/stream/resume,
  state envelope v1, cách tách resident reply/backend resume. Đề xuất business state
  trong folder sở hữu; test bằng fake dependencies tại `tests/support/fakes.ts`.
- DD01 review operation catalog, required timeout/idempotency, accepted/success,
  unknown mutation outcome và cancellation. Không lấy identity từ model input.
- Fixture hiện có chỉ tổng hợp: service-test/resident-test/tenant-test và tool echo;
  không phải fixture đã freeze với backend.
- Test mong đợi: graph consumer compile với port; invalid input/response bị từ chối;
  accepted không thành completed; timeout không tạo mutation thứ hai với key mới.
- Đang chặn: freeze/commit interface và integration graph/tool thật. PH01 unit/capability
  test có thể tiếp tục độc lập, không coi mock là backend integration.

## C01 / C06 — hợp đồng backend và binding

Owner cung cấp: Chiến. Xin schema/version/fixtures chính thức cho port tương đương
`resolveAuthorizedReceptionContext`, resolve framework binding và service auth;
**đây là tên nhu cầu, chưa phải endpoint hoặc API đã tồn tại**.

Input cần chốt: service token đúng audience/expiry, operation read/run/resume/cancel,
opaque session/binding reference và correlation/request ID. Identity/tenant/quyền
được server resolve từ authenticated context, không tin ID tự nhận từ browser.

Output cần chốt: execution principal, initiating user, tenant, binding/run ID,
permissions, mapping framework thread/namespace chỉ phía server, contract version;
typed errors không lộ tài nguyên khác user và không chứa token/PII.

Auth/idempotency/error semantics cần chốt: quyền mới bị revoke, token hết hạn,
cross-tenant/user, stale binding/generation, key dedup cho start/resume/cancel,
lease/fencing và truy hồi mutation chưa rõ kết quả. Event schema C01/C08 cần có
source verification, event ID, aggregate version, ticket/generation và interrupt.

Fixture/test mong đợi: hai user cùng tenant, hai tenant, một user hai ticket;
user B read/resume binding A bị từ chối; duplicate/out-of-order event không resume
sai; timeout dùng lại key; revoke có hiệu lực trước read/run/resume.

Đang chặn: PH02 auth/binding và PH03 durable recovery. `shared/contracts/` hiện
chỉ có `.gitkeep`; không tự tạo platform DTO trong Reception để thay thế C01.

## P01 — toolchain và CI runtime riêng

Owner cung cấp: Team 5. Package Reception độc lập, `packageManager: bun@1.3.14`,
direct dependencies pin exact, `bun.lock` riêng. Xin CI chạy từ `agent-reception/`:

```sh
bun install --frozen-lockfile --ignore-scripts
bun run test
bun run typecheck
```

Đây là job process, không có request/response HTTP. Auth: không cần API key/model,
backend hoặc DB thật cho test. Idempotency: cài frozen không thay lock; lỗi install,
test/typecheck phải làm job fail. Fixture gồm model/tool tổng hợp và MemorySaver
chỉ trong test; không inject production secrets vào job này.

Xin chốt image/runtime Bun, command start, HOST/PORT và liveness `/health` cho
deployment; health không chứng minh backend/model readiness. Root manifest,
lockfile, CI và deployment do Team 5 cập nhật. Không bị chặn chạy local PH01;
chưa xác nhận CI/deployment thật.
