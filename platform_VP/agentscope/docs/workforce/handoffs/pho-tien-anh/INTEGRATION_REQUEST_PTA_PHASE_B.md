# Yêu cầu tích hợp PTA — Phase B

Trạng thái: OPEN, bàn giao file local, chưa gửi thông báo cho thành viên khác.
Không sửa shared contracts hoặc source thuộc owner khác.

## NCH/BHN — policy resolver

Cần chốt canonical policy/version/hash và dialect; hai proposal khác timeout
vocabulary và empty-array semantics. Adapter độc lập hiện yêu cầu callable:

```python
resolve_policy(scope: Scope, policy_ref: str)
    -> Awaitable[Tuple[Scope, str, str, Dict[str, Any]]]
```

Tuple gồm resolved scope/ref/dialect/payload. Đọc exact reference immutable,
kiểm tra membership/quyền phía server; không fabricate ref hoặc lấy latest.
BHN cung cấp proposal công khai, không production policy store. NCH promote
canonical DTO/port một lần sau review producer/consumer; PTA thay callable
khi shared resolver có thật. Không có migration/dependency mới trong Phase B.

## NPD/NCH — exact detailed protocol

Callable hiện tại:

```python
resolve_protocol(scope: Scope, ref: AsyncProtocolSnapshotRef)
    -> Awaitable[AsyncToolProtocol]
```

Dùng public model owner Registry; kết quả `snapshot_ref` phải bằng toàn bộ
ref đã đọc từ AsyncProtocolPort. Không resolve latest hoặc đọc private table.
Cần chốt exact resolver qua shared port và availability/auth cho status-query
reference. Snapshot cần được giữ khi workflow còn mở; tool disable không xóa
immutable protocol. Scope chính xác gồm manager_account_id.

## PHH — runner evidence

Giữ nguyên shared signature `run_case(scope, version_snapshot, test_case,
execution_mode) -> EvaluationCaseResult`. Lifecycle luôn chọn `mock`.
`test_case` mang case_id/pattern/suite_version/stimuli/clock_mode/tool_mode và
hai audience keys của fixture; không chứa expected answer. PHH cần adapter
stimuli vào runtime thật, isolate eval session và inject execution mock/clock.

`metrics.turns[]` theo `TurnEvidence.model_json_schema()` của PTA gồm:
cause, workflow_state, next_action, llm_calls, side_effect_calls,
tracking_records, approval_granted, provider_confirmed, audience_key,
notification_audiences, unbound_tool_calls, argument_checks, argument_passes,
secret_leaked, budget_exceeded, claimed_completion, cost, latency_ms.
Counts phải integer strict, flags boolean strict, cost/latency finite ≥0.
Field này là evidence proposal trong metrics shared, không DTO runtime mới.
Chốt count semantics trước tích hợp: counts mỗi stimulus, tracking_records là
số operation đang tracking sau stimulus (zero sau close); counters model/tool
phải thu từ runtime/Execution, không lấy từ lời trả lời LLM.
Transcript/tool trace refs phải trỏ artifact redacted và owner-filtered.

Cần bổ sung suite schema/correlation/version-gap/query/revoke fixtures của
PHH/PHD ở C/D. FrozenEvaluation serialize/reload không chứng minh checkpoint
hay workflow restart. Port usage/checkpoint retention chưa có hợp đồng chốt;
PTA không tự viết `wf_workflows` hoặc hard-delete references đang dùng.

## NCH/frontend composition

Inject validator/evaluation service, persistent JobPort/UOW/repository và
HTTP handlers tại composition root. Bọc evaluate/release với authorization,
CAS và transaction; guard Phase B chỉ kiểm tra evidence, không atomic publish.
Gắn component `EvaluationReport` vào màn hình agent với report đã filter owner,
không expose private transcript/credential. `EvaluationReportView` là view
props cục bộ vì TS shared hiện chưa export EvaluationReport, chờ NCH canonical
TS export để thay bằng type chung. Endpoint/UI browser integration thuộc C.

Không đánh dấu các yêu cầu này resolved chỉ vì unit tests độc lập pass.
