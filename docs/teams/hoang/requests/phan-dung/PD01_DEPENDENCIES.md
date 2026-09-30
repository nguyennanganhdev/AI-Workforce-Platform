# PD01 — Request chốt interface và tích hợp graph

Người ghi: Phan Dũng, Team Hoàng. Ngày: 30/09/2026.
Owner nhận: Phan Hoàng PH01–PH04, Dương Dũng DD01/DD02; Chiến C01/C06 qua đầu mối Hoàng.
Đây là request trong repo, chưa xác nhận owner đã nhận/chấp thuận qua kênh khác.

## Hiện trạng thực

- Đã đọc `agent-reception/src/contracts/index.ts`: `0.1.0-draft.1`, state schema `1`.
  Consumer PD01 sử dụng nguyên interface này; không sửa hoặc freeze file chung.
- PH01 đã có manifest/lockfile, model factory và port checkpointer. Graph PD01 mới
  nằm ở `agent-reception/src/graph/`; chưa được nối vào entrypoint production.
- `shared/contracts/` hiện chỉ có `.gitkeep`; không có OpenAPI/JSON Schema C01 để
  pin hoặc claim tích hợp. Folder backend/tools của DD01/DD02 chưa tồn tại trong checkout.
- Chưa có durable saver/binding resolver/event ingress PH02/PH03.

## Chữ ký cần owner triển khai/review

Factory export từ `agent-reception/src/graph/index.ts`:

```ts
createReceptionGraphFactory<Operations extends ReceptionToolOperations>(
  options: ReceptionFactoryOptions<Operations>,
): ReceptionGraphFactory<ReceptionBusinessState, Operations>
```

PH04 inject `model`, `tools`, `checkpointer` theo draft PH01, không dùng fixture hay
`MemorySaver` làm fallback production. Options `bindings` là allowlist theo đúng
operation catalog DD01, không phải API/DTO backend mới. Mỗi binding cần:

```ts
ToolBinding<Input, Output> = {
  description: string;
  inputSchema: JsonValue; // schema từ contract/version DD01/C01
  parseInput(value: unknown): Input;
  parseOutput(value: unknown): Output;
  confirmedFacts?(output: Output): readonly Fact[];
  ticket?(output: Output): { id: string; generation: number; aggregateVersion: number } | null;
  reconcile?(request: ReceptionToolRequest<string, Input>): Promise<ReceptionToolResult<Output>>;
}
```

`confirmedFacts` chỉ trích trường backend đã xác minh, không đưa assessment/suy luận
của model thành xác nhận. `parseInput`/`parseOutput` cần validation theo contract thật;
không chỉ cast TypeScript. Schema catalog phục vụ model; runtime vẫn phải validate.
Identity lấy từ context PH02 xác minh, không lấy từ input model.

`reconcile` phải kiểm tra kết quả thao tác đã nhận/mất response bằng authorized
read/status operation. Graph gửi lại **cùng input/key/timeout**, context và signal
của lượt resume hiện tại. Callback không được blind-retry mutation chưa rõ kết quả.
Chưa có callback: resume trả `RECONCILIATION_UNAVAILABLE`, giữ interrupt/pending,
không gọi mock hoặc kết luận thành công. Chữ ký API status/idempotency lookup và
auth/error semantics cần DD01/C01 chốt, PD01 không tự đặt endpoint.

## Quy ước checkpoint cần Phan Hoàng review

LangGraph **1.4.10** đặt lại `checkpoint_ns` về chuỗi rỗng với graph gốc
(`node_modules/@langchain/langgraph/dist/pregel/loop.js`). PD01 hiện ánh xạ:

```ts
thread_id = JSON.stringify([context.checkpoint.namespace, context.checkpoint.threadId]);
checkpoint_ns = "";
```

Hai khóa đều do backend resolve; không lấy từ browser/model. Test cùng thread ID
nhưng namespace khác đã tách dữ liệu. PH03 cần review/freeze ánh xạ này trước khi
có checkpoint production; không đổi codec âm thầm sau khi lưu dữ liệu.

Key tool hiện là JSON tuple `[bindingId, rootOperationId, toolSequence]`, không dùng
run ID và không cho model tự đặt. Graph checkpoint plan trước node side effect,
chạy `durability: "sync"`. DD01/C01 cần xác nhận format/độ dài key hoặc đề xuất codec
chung được owner phê duyệt. Trong resume, root operation ID được giữ nguyên.
Chưa có dedup start-operation từ PH02/PH03: không gọi lại cả `run` và `stream` cho
một operation, không replay start đã hoàn tất để kỳ vọng dedup tự động.

## Auth, event, recovery và các test nghiệm thu cần owner bổ sung

- PH02 authorize trước **mọi** read/run/resume; service principal khác user.
  Guard owner của graph chỉ là kiểm tra bổ sung, không chứng minh quyền.
- PH03 validate nguồn event, binding/interrupt/ticket/generation/version, inbox
  dedup, lease/fencing và quyền vừa bị thu hồi. Graph kiểm tra khóa đang chờ và
  ticket đã biết; khi chưa có ticket, PH03 phải resolve correlation trước resume.
  Event chỉ báo có thay đổi; `reconcile` đọc lại kết quả qua tool có quyền.
- Sau abort/crash giữa tool call, plan/key vẫn ở checkpoint; PD01 không tự chạy lại
  node pending chưa có interrupt. PH03 cần recovery/reconciliation cho khoảng này,
  không reset state hay sinh key mới. Test required: saver bền vững + restart,
  lost response, hai replica, callback lặp/stale, revoke giữa run/resume.
- PH02 map/allowlist graph result trước khi đưa UI; result/state là dữ liệu nội bộ.
  Stream PD01 phát một đoạn reply sau bước graph và đúng một terminal result;
  chưa có token streaming model hoặc AG-UI adapter.
- Handoff PD01 là trạng thái chờ người review, không tự gọi dispatch/đóng ticket/
  pause SLA. DD02/PD02/PD03/PH04 nối operations nghiệp vụ thật.

Fixture `verify_unit` và các ID `*-synthetic` trong
`agent-reception/tests/graph/factory.test.ts` **chỉ dành cho test**. Expected tests:
accepted/unknown không thành completion; reconciliation giữ key; schema lỗi không
thành confirmed; forbidden → handoff; consumer graph factory dùng đúng draft PH01.
Không đăng ký `verify_unit` làm operation production từ fixture này.

## Phần độc lập đã tiếp tục

State/factory/prompt control protocol, interrupt/resume nội bộ, bounded questions,
tool allowlist, provenance và unit tests không cần LLM/network đã triển khai.
Handoff ở `docs/teams/hoang/handoffs/phan-dung/PD01.md` ghi kết quả chạy thực.
Việc freeze contract và tích hợp backend/checkpoint/transport thật vẫn mở.
