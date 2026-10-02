# Request — assess_request, policy, self-help và chuyển khẩn

Phan Dũng, 30/09/2026. Owner nhận: DD02–DD06, PH02–PH06, Chiến C05/C06/C13,
Quang Q01/Q04/Q07/Q08, Đông và Team 5 qua đầu mối Hoàng. Request trong repo,
chưa gửi thông điệp hoặc có xác nhận owner chấp thuận.

## Code consumer và khoảng trống thực

`agent-reception/src/graph/workflow.py` hiện có node thứ hai `assess_request` và
`agent-reception/src/graph/assessment.py` cung cấp ASSESSMENT_SCHEMA/validator/guard.
WorkflowOptions thêm `request_policy`; không inject thì review với
REQUEST_POLICY_UNAVAILABLE, không dùng LLM làm policy hoặc fallback test port.
Không tìm thấy implementation producer cho request policy/self-help/emergency
operations trong vùng runtime/tool Reception đã kiểm tra. C13 design hiện mô tả
attempt gắn ticket; luồng người dùng mới muốn offer self-help trước ticket. Owner
phải chốt lifecycle theo session/channel hoặc cách tương thích, không tạo ticket
ẩn/bịa ID/FK để lấp gap. PD không sửa DB/migration hoặc HTTP client.

## Policy port bắt buộc

`RequestPolicyPort.evaluate_request(request)` là async Python proposal.
Request gồm message, history có giới hạn, context đã authorize, active_ticket_id,
ticket snapshot, self_help attempt (nếu có), assessment và CancellationToken signal.

- Preflight `assessment=None`: backend phải đọc dữ liệu hiện tại và lịch sử để
  đánh giá emergency độc lập LLM. Confirmed emergency bỏ qua classification LLM và
  retrieval, chuyển ngay node emergency_handoff. Không coi LLM là emergency detector duy nhất.
- Bình thường: LLM trả structured proposal đã validate; backend evaluate lần hai
  với assessment để kiểm tra signals/explicit staff/declined/failed/eligibility.
  Đây là read-only policy evaluation, không âm thầm ghi mutation/dispatch.

Response bắt buộc:

```json
{
  "policy_version": "opaque-published-version",
  "emergency": false,
  "staff_required": false,
  "self_help_allowed": false,
  "missing_information": ["Câu hỏi về dữ kiện còn thiếu"],
  "handoff_reason": "needs_staff"
}
```

handoff_reason thuộc needs_staff/self_help_declined/self_help_failed/emergency;
boolean strict, không dùng confidence score làm policy. Staff_required xác nhận
các trường hợp khách yêu cầu nhân viên/chuyên môn/policy từ chối hoặc thất bại.
Emergency có thể kèm `safety_guidance={approved:true,answer,retrievalRunId,citations}`;
citations gồm documentId/version/chunkId. Backend chốt approval/ACL/freshness/phạm vi
cho hướng dẫn an toàn tại preflight, không cần chờ RAG mới. Guidance sai shape hoặc
chưa approved bị bỏ, không được dùng làm lý do trì hoãn alert emergency đã xác nhận.

Model output chỉ có intent, proposed_action, explicit_staff_request,
self_help_declined, self_help_failed, emergency_signals, missing_information, reason.
Code tạo state.decision.next_action sau policy/active ticket guards. Backend không
tin proposal như quyền/scope/chẩn đoán chính thức. Thiếu policy/schema/error chuyển
review, không giả producer đã tồn tại.

## Semantic capability process_self_help (tên cần DD/PH/Q/C13 chốt)

Input: channel_id, reception_session_id, source_message `{id,text,fileIds?}`,
policy_version, assessment (validated decision), attempt trước đó nếu có.
Tool request vẫn context/idempotencyKey/timeoutMs/signal. Graph checkpoint plan trước
invoke; unknown/timeout cần reconcile cùng key/input, không gọi lại mutation tùy ý.

Producer thực hiện authorized procedure lookup + eligibility/current approval/revoke
checks và lifecycle offer/consent/decline/result. Có thể bind nhiều API thật sau port;
không tự đăng ký tool tên trong tài liệu. Status:

- `offered`: policy_version, attempt_id, procedure; chỉ hỏi consent, chưa in steps.
- `accepted`: cùng attempt/procedure version, consent_recorded=true,
  consent_source_message_id đúng tin nhắn hiện tại; backend xác minh cư dân đồng ý
  và ghi consent nguyên tử. Im lặng/LLM flag không phải consent.
- `succeeded/declined/failed/stopped`: policy_version, attempt_id, recorded=true,
  source_message_id đúng tin nhắn kết quả. Succeeded chỉ ghi nhận lời khách,
  không đóng ticket bằng LLM. Declined/failed/stopped chuyển ticket sau ACK lifecycle.
- `unavailable/revoked/expired`: policy_version; graph hỏi lựa chọn xác minh/hỗ trợ,
  không tạo ticket sửa chữa chỉ vì retrieval không có kết quả.

Procedure cho offered/accepted bắt buộc approved=true, eligible=true, policy_version
đúng, version, expires_at timezone-aware còn hiệu lực, steps[] không rỗng,
stop_conditions[] không rỗng, retrievalRunId và citations[] có ID/version/chunk.
Backend kiểm tra link approval-document-version/hashes, audience/tenant/file grants
và revoke tại mỗi lần chạy. Graph không thay backend ACL hoặc kiểm chứng nội dung
hướng dẫn thật. Đổi procedure giữa attempt phải offer/consent lại; graph không âm
thầm đổi version. Staff-required/eligibility false không được trả accepted/offered.

## Semantic capability escalate_emergency (tên cần DD/PH/C05/C06 chốt)

Input: channel_id, reception_session_id, source_message, policy_version;
thêm ticket_id/ticket_generation/ticket_version khi active ticket tồn tại.
Không backend destination/workspace lấy từ LLM. Producer authorize context và ghi
durable emergency notification/handoff/escalation theo policy, không đợi ảnh/profile.
Nếu chưa có ticket, chốt session alert correlation trước draft; không sinh ticket ẩn.
Nếu có ticket, nâng mức theo official policy trên ticket đó, kể cả terminal lifecycle
(C05 chốt reopen/review transition hợp lệ); không tạo ticket mới hoặc tự sửa DB.

Success output: persisted=true, enqueued=true, operation_id, policy_version đúng;
kèm updated Ticket khi active. Graph giữ ticket ID/generation, refresh incident/
official assessment/route/ACK sau alert. Partial/lost ACK giữ pending để reconcile;
không nói đã chuyển thành công khi chỉ accepted/unknown. Safety guidance đã duyệt
vẫn có trong reply nếu response alert chưa rõ. Hiện stream emit sau graph invocation,
chưa có transport push safety message tức thời trước khi chờ ACK/network budget;
PH phải chốt output flush/priority transport nếu yêu cầu realtime safety delivery.

## Compatibility và tests producer cần bổ sung

Topology mới dùng `pd-workflow-python-2`; từ chối checkpoint v1/TS, không reset.
PH03 chốt namespace/migration/quyền/retention; history tối đa 24 entries là dialogue
scoped trong checkpoint, không thay full durable chat history. Không đẩy raw
context/checkpoint/reason nội bộ ra UI. Giá vẫn dùng authorized knowledge/price
capability producer; không tự tính hoặc seed giá, không báo giá xác nhận.

Required integration: policy preflight/recheck và schema parity; giá/information
không create; explicit staff được policy xác nhận; ambiguous incident hỏi rõ;
approved consent thật, procedure revoke/expiry/version đổi, decline/failure audit;
emergency trước LLM/retrieval/ảnh, alert-before-draft correlation, same-ticket escalation,
lost/duplicate alert và fencing; ACL/revoke/cross-tenant, two replicas/restart;
LLM structured quality/latency/token/price answers có điều kiện và nguồn. Test fake
ports chỉ nằm trong tests, không production fallback. Requests runtime/backend cũ
vẫn mở; không nghiệm thu producer chỉ bằng Python consumer tests.
