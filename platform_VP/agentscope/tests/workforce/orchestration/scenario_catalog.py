"""Executable case inventory. Expected values are test oracles, not runtime output."""

CASES = []


def group(stage, action, rows):
    for title, data, expected in rows:
        index = sum(c["stage"] == stage for c in CASES) + 1
        CASES.append(dict(id=f"{stage}-S{index:03d}", stage=stage, action=action,
                          title=title, input=data, expected=expected))


group("G1", "conversation", [
    ("Tạo hội thoại nhóm với UTC", {}, "group"),
    ("Tạo chat riêng cho Hotel với múi giờ Việt Nam", {"mode": "direct", "direct_agent_id": "Hotel", "timezone": "Asia/Ho_Chi_Minh"}, "direct"),
    ("Chat riêng thiếu agent", {"mode": "direct"}, "!DIRECT_AGENT_REQUIRED"),
    ("Chat nhóm gán nhầm direct agent", {"direct_agent_id": "Hotel"}, "!DIRECT_AGENT_REQUIRED"),
    ("Từ chối mode không hỗ trợ", {"mode": "broadcast"}, "!CONVERSATION_MODE_INVALID"),
    ("Từ chối múi giờ không tồn tại", {"timezone": "wrong/zone"}, "!TIMEZONE_INVALID"),
    ("Không đọc hội thoại của manager khác", {"read_foreign": True}, "!RESOURCE_NOT_FOUND"),
    ("Scope bị thu hồi không tạo hội thoại", {"revoked": True}, "!SCOPE_REVOKED"),
])
group("G1", "router", [
    ("Yêu cầu khách sạn chỉ chọn Hotel", {"needs": ["hotel"]}, ["Hotel"]),
    ("Du lịch chọn bốn agent và loại Technical", {"needs": ["plan", "hotel", "car", "calculate"]}, ["Calculator", "Car", "Hotel", "Plan"]),
    ("Không tìm thấy năng lực yêu cầu", {"needs": ["flight"]}, "!CAPABILITY_MISSING"),
    ("Danh sách nhu cầu rỗng bị chặn", {"needs": []}, "!CAPABILITY_REQUIRED"),
    ("Agent draft không được chọn", {"mutation": "draft"}, "!CAPABILITY_MISSING"),
    ("Deployment bị thu hồi không được chọn", {"mutation": "revoked"}, "!CAPABILITY_MISSING"),
    ("Candidate manager khác không được chọn", {"mutation": "foreign"}, "!CAPABILITY_MISSING"),
    ("Manifest hash không khớp bị loại", {"mutation": "hash"}, "!CAPABILITY_MISSING"),
    ("Deployment trỏ phiên bản khác bị loại", {"mutation": "version"}, "!CAPABILITY_MISSING"),
    ("Hai agent cùng đáp ứng hotel phải làm rõ", {"mutation": "ambiguous"}, "!CAPABILITY_AMBIGUOUS"),
])
group("G1", "facts", [
    ("Lưu budget/reserve và provenance người dùng", {"facts": {"budget": 100, "reserve": 20}}, {"budget": 100, "reserve": 20}),
    ("Ngân sách bằng không hợp lệ", {"facts": {"budget": 0}}, {"budget": 0}),
    ("Budget âm bị chặn", {"facts": {"budget": -1}}, "!MONEY_INVALID"),
    ("Budget số thực bị chặn", {"facts": {"budget": 1.5}}, "!MONEY_INVALID"),
    ("Boolean không được coi là tiền", {"facts": {"budget": True}}, "!MONEY_INVALID"),
    ("Reserve vượt budget rollback toàn bộ", {"facts": {"budget": 10, "reserve": 11}}, "!RESERVE_EXCEEDS_BUDGET"),
    ("Không ghi trường dữ kiện ngoài contract", {"facts": {"password": "test-only"}}, "!FACT_FIELD_INVALID"),
    ("Nguồn dữ kiện không hợp lệ bị chặn", {"facts": {}, "source_kind": "model"}, "!FACT_SOURCE_INVALID"),
    ("Thiếu tham chiếu nguồn bị chặn", {"facts": {}, "source_ref": ""}, "!FACT_SOURCE_REQUIRED"),
    ("Tool không ghi đè budget người dùng", {"protect": True, "facts": {"budget": 80}}, "!USER_FACT_PROTECTED"),
    ("Đổi budget làm stale proposal và bỏ lựa chọn", {"invalidate": True, "facts": {"budget": 200}}, "stale-and-cleared"),
    ("Quote hết hạn đúng thời điểm hiện tại bị chặn", {"expired_proposal": True}, "!QUOTE_EXPIRED"),
])
group("G1", "handoff", [
    ("Giao task hợp lệ chỉ đạt delivered", {}, "delivered"),
    ("Task trắng bị chặn trước dispatch", {"content": "   "}, "!TASK_CONTENT_INVALID"),
    ("Task vượt 32000 ký tự bị chặn", {"content_length": 32001}, "!TASK_CONTENT_INVALID"),
    ("Timeout bằng không bị chặn", {"timeout_seconds": 0}, "!TASK_TIMEOUT_INVALID"),
    ("Timeout âm bị chặn", {"timeout_seconds": -1}, "!TASK_TIMEOUT_INVALID"),
    ("Session ngoài nhóm không được giao việc", {"sender": "foreign"}, "!SENDER_NOT_MEMBER"),
    ("Agent tự giao việc cho mình bị chặn", {"sender": "self"}, "!HANDOFF_SELF_LOOP"),
    ("Recipient không thuộc nhóm bị chặn", {"recipient": "Car"}, "!MEMBER_NOT_FOUND"),
    ("Context ref sai kiểu bị chặn", {"context_refs": [123]}, "!CONTEXT_REFS_INVALID"),
    ("Đạt tổng số handoff thì không dispatch mới", {"limit": "max_handoffs"}, "!HANDOFF_LIMIT"),
    ("Hết slot đồng thời thì không dispatch mới", {"limit": "max_concurrent"}, "!CONCURRENCY_LIMIT"),
    ("Hết ngân sách token thì không dispatch mới", {"limit": "token_limit"}, "!RUN_BUDGET_EXHAUSTED"),
])
group("G1", "runtime", [
    ("Hai hội thoại dùng Hotel có group/session riêng", {"mode": "isolation"}, True),
    ("Publish v4 không đổi pin v3 của nhóm cũ", {"mode": "version"}, ["Hotel-v3", "Hotel-v4"]),
    ("Timeout provisioning phục hồi cùng binding", {"mode": "retry"}, True),
    ("Hook trả group khác bị từ chối", {"tamper": "group_id"}, "!RUNTIME_BINDING_INVALID"),
    ("Hook trả leader session khác bị từ chối", {"tamper": "leader_session_id"}, "!RUNTIME_BINDING_INVALID"),
    ("Hook trả member session khác bị từ chối", {"tamper": "session_id"}, "!RUNTIME_BINDING_INVALID"),
    ("Hook trả member hash khác bị từ chối", {"tamper": "manifest_hash"}, "!RUNTIME_BINDING_INVALID"),
    ("Scope sai không tới provisioning hook", {"mode": "foreign"}, "!RESOURCE_NOT_FOUND"),
])

group("G2", "recipient", [
    ("Target ID Hotel giữ nguyên session", {"target_agent_id": "Hotel"}, "Hotel"),
    ("Mention tên Hotel đúng duy nhất", {"mention_name": "Hotel"}, "Hotel"),
    ("Target ID ngoài nhóm bị chặn", {"target_agent_id": "Car"}, "!MEMBER_NOT_FOUND"),
    ("Tên mention không tồn tại bị chặn", {"mention_name": "Unknown"}, "!MEMBER_NOT_FOUND"),
    ("Hai thành viên trùng tên phải làm rõ", {"duplicate_name": True, "mention_name": "Same"}, "!MENTION_AMBIGUOUS"),
    ("Không target và không câu hỏi thì về leader", {}, "leader"),
    ("Một câu hỏi pending về đúng Hotel", {"questions": "one"}, "Hotel"),
    ("Hai câu hỏi pending phải làm rõ", {"questions": "two"}, "!PENDING_QUESTION_AMBIGUOUS"),
    ("Câu hỏi trỏ session ngoài nhóm bị chặn", {"questions": "foreign"}, "!QUESTION_TARGET_INVALID"),
    ("Reply message không tồn tại bị chặn", {"reply_to_message_id": "missing"}, "!MESSAGE_REFERENCE_INVALID"),
    ("Reply message của Hotel về đúng Hotel", {"reply_to_message_id": "m1", "message_agent": "Hotel"}, "Hotel"),
    ("Run và conversation không cùng scope bị chặn", {"foreign_context": True}, "!CONTEXT_BINDING_INVALID"),
])
group("G2", "entity", [
    ("Một hotel candidate được resolve duy nhất", {"ids": ["H1"]}, "H1"),
    ("Không có candidate thì không bịa entity", {"ids": []}, "!ENTITY_NOT_FOUND"),
    ("Hai candidate không reference phải làm rõ", {"ids": ["H1", "H2"]}, "!ENTITY_AMBIGUOUS"),
    ("Explicit ref chọn H2 trong hai candidate", {"ids": ["H1", "H2"], "explicit_ref": "H2"}, "H2"),
    ("Selected ref hiện tại chọn H1", {"ids": ["H1", "H2"], "selected": "H1"}, "H1"),
    ("Explicit ref ưu tiên hơn selected ref", {"ids": ["H1", "H2"], "selected": "H1", "explicit_ref": "H2"}, "H2"),
    ("Reference không tồn tại không fallback", {"ids": ["H1"], "explicit_ref": "H9"}, "!ENTITY_NOT_FOUND"),
    ("Candidate trùng ID không được chọn tùy ý", {"ids": ["H1", "H1"], "explicit_ref": "H1"}, "!ENTITY_AMBIGUOUS"),
])
group("G2", "message", [
    ("Tin hợp lệ lưu trước và gửi một lần", {}, "delivered"),
    ("Tin rỗng không gọi delivery", {"content": ""}, "!MESSAGE_INVALID"),
    ("Tin chỉ khoảng trắng bị chặn", {"content": " \n "}, "!MESSAGE_INVALID"),
    ("Tin dài đúng 32000 ký tự được gửi", {"content_length": 32000}, "delivered"),
    ("Tin dài 32001 ký tự bị chặn", {"content_length": 32001}, "!MESSAGE_INVALID"),
    ("Client message ID rỗng bị chặn", {"client_message_id": ""}, "!MESSAGE_ID_INVALID"),
    ("Client message ID 129 ký tự bị chặn", {"id_length": 129}, "!MESSAGE_ID_INVALID"),
    ("Retry cùng ID/nội dung không gửi lại", {"retry": "same"}, "one-delivery"),
    ("Cùng ID khác nội dung trả conflict", {"retry": "changed"}, "!MESSAGE_ID_CONFLICT"),
    ("Run đã hủy không nhận tin mới", {"cancelled": True}, "!RUN_UNAVAILABLE"),
    ("Tin trực tiếp đến agent ngoài nhóm bị chặn", {"target_agent_id": "Car"}, "!MEMBER_NOT_FOUND"),
    ("Hội thoại chưa có run không nhận tin", {"no_run": True}, "!RUN_REQUIRED"),
])
group("G2", "context", [
    ("Chỉ chuyển destination được chọn", {"keys": ["destination"]}, {"destination": "Ha Long"}),
    ("Không chọn field thì context rỗng", {"keys": []}, {}),
    ("Không cho chuyển private history", {"keys": ["messages"]}, "!CONTEXT_FIELD_INVALID"),
    ("Context tách rời dữ kiện gốc", {"keys": ["preferences"], "mutate": True}, ["quiet"]),
])
group("G2", "evaluation", [
    ("Mock eval trả kết quả completed", {}, "completed"),
    ("Sandbox eval đi qua backend guard", {"mode": "sandbox"}, "completed"),
    ("Không cho client dùng production eval mode", {"mode": "production"}, "!EVALUATION_MODE_INVALID"),
    ("Snapshot thiếu manifest bị chặn", {"snapshot": "missing_manifest"}, "!SNAPSHOT_INVALID"),
    ("Snapshot manager khác không tới runtime", {"snapshot": "foreign"}, "!SNAPSHOT_SCOPE_INVALID"),
    ("Guard không tồn tại không gọi runtime", {"guard_none": True}, "!EVALUATION_GUARD_REQUIRED"),
    ("Runtime thiếu tool traces bị chặn", {"result": "missing_traces"}, "!EVALUATION_RESULT_INVALID"),
    ("Runtime trả cost âm bị chặn", {"result": "negative_cost"}, "!EVALUATION_RESULT_INVALID"),
    ("Runtime thất bại phải giữ failed", {"result": "failed"}, "failed"),
    ("Runtime bị hủy phải giữ cancelled", {"result": "cancelled"}, "cancelled"),
])
group("G2", "member", [
    ("Thêm agent khác batch vào group hiện tại", {"mode": "cross_batch"}, ["Car", "Hotel"]),
    ("Thêm lại member không đổi session", {"mode": "duplicate"}, True),
    ("Thêm member thiếu lý do bị chặn", {"reason": " "}, "!SELECTION_REASON_REQUIRED"),
    ("Member chưa published không được thêm", {"mode": "draft"}, "!AGENT_NOT_PUBLISHED"),
])

group("G3", "policy", [
    ("Read-only terminal được auto-close", {"policy": {"effect": "read_only", "auto_close": True}, "outcome": {"terminal": True}}, ["closed", "none"]),
    ("Read-only không auto-close chờ xác nhận", {"policy": {"effect": "read_only"}, "outcome": {"terminal": True}}, ["awaiting_confirmation", "confirm_close"]),
    ("Side effect terminal vẫn chờ xác nhận", {"policy": {"effect": "side_effect", "auto_close": True}, "outcome": {"terminal": True}}, ["awaiting_confirmation", "confirm_close"]),
    ("Thiếu dữ kiện chờ user", {"outcome": {"needs_user": True}}, ["awaiting_user", "submit_reply"]),
    ("Cần phê duyệt chờ approval", {"outcome": {"needs_approval": True}}, ["awaiting_approval", "submit_approval"]),
    ("Operation pending có tracking thì chờ event", {"policy": {"effect": "side_effect", "tracking_protocol": "v1"}, "outcome": {"operation_pending": True}}, ["waiting_external_event", "watch_events"]),
    ("Operation pending thiếu tracking bị chặn", {"outcome": {"operation_pending": True}}, "!TRACKING_CAPABILITY_MISSING"),
    ("Create unknown cần đối soát kể cả terminal", {"outcome": {"creation_status": "unknown", "terminal": True}}, ["needs_attention", "resolve_attention"]),
    ("Lượt chưa xong quá HTTP deadline trả watch_request", {"http_pending": True}, ["active", "watch_request"]),
    ("Outcome chưa đầy đủ không báo thành công", {}, "!TURN_OUTCOME_INCOMPLETE"),
    ("Policy effect không hợp lệ bị chặn", {"policy": {"effect": "unknown"}}, "!POLICY_EFFECT_INVALID"),
    ("Attention ưu tiên hơn user/approval", {"outcome": {"needs_attention": True, "needs_user": True, "needs_approval": True}}, ["needs_attention", "resolve_attention"]),
])
group("G3", "http_status", [
    ("Accepted trả HTTP 202", {"status": "accepted"}, 202),
    ("Queued trả HTTP 202", {"status": "queued"}, 202),
    ("Running trả HTTP 202", {"status": "running"}, 202),
    ("Completed trả HTTP 200", {"status": "completed"}, 200),
    ("Failed có kết quả cuối trả HTTP 200", {"status": "failed"}, 200),
    ("Blocked có kết quả cuối trả HTTP 200", {"status": "blocked"}, 200),
])
group("G3", "checkpoint", [
    ("User reply hợp lệ kích hoạt runtime", {}, "active"),
    ("Approval result chỉ khi đang chờ approval", {"state": "awaiting_approval", "kind": "approval_result"}, "active"),
    ("User text không thay thế approval", {"state": "awaiting_approval"}, "!APPROVAL_REQUIRED"),
    ("Approval ngoài trạng thái chờ bị chặn", {"kind": "approval_result"}, "!APPROVAL_NOT_PENDING"),
    ("Worker fence cũ không sửa checkpoint", {"fence": 6}, "!STALE_WORKER"),
    ("Revision cũ không sửa checkpoint", {"revision": 0}, "!REVISION_CONFLICT"),
    ("Workflow closed không nhận cause mới", {"state": "closed"}, "!WORKFLOW_CLOSED"),
    ("Workflow blocked không tự chạy lại", {"state": "blocked_authorization"}, "!WORKFLOW_BLOCKED"),
    ("Progress không đánh thức session đang HITL", {"kind": "operation_progress", "pending_hitl": True}, "queued-without-runtime"),
    ("Timer không giả thành user reply trong HITL", {"kind": "timer", "pending_hitl": True}, "queued-without-runtime"),
    ("Cause trùng không tăng revision lần hai", {"duplicate": True}, "idempotent"),
    ("Cause ngoài allowlist bị chặn", {"kind": "model_text"}, "!CAUSE_INVALID"),
])
group("G3", "close", [
    ("Close workflow không operation pending", {}, "closed"),
    ("Close lần hai giữ revision", {"twice": True}, "idempotent"),
    ("Close stale revision bị chặn", {"expected_revision": 0}, "!REVISION_CONFLICT"),
    ("Close khi pending cần xác nhận stop tracking", {"operation_pending": True}, "!STOP_TRACKING_CONFIRMATION_REQUIRED"),
    ("Stop tracking không gọi hủy operation", {"operation_pending": True, "stop_tracking_only": True}, "closed"),
])
group("G3", "ingress", [
    ("Start ticket trả receipt và đúng một job", {}, "accepted-once"),
    ("Retry cùng request trả cùng receipt", {"mode": "retry"}, "same-receipt"),
    ("Cùng request ID khác message bị chặn", {"mode": "conflict"}, "!REQUEST_ID_CONFLICT"),
    ("Enqueue lỗi rollback command/binding/job", {"mode": "rollback"}, "empty-storage"),
    ("Partner chưa xác thực bị chặn", {"actor": "unverified"}, "!AUTHENTICATION_REQUIRED"),
    ("Payload giả tenant không cấp quyền", {"patch": {"tenant_id": "other"}}, "!AUTHORITY_FIELD_FORBIDDEN"),
    ("Start thiếu ticket ID bị chặn", {"remove": "external_ticket_id"}, "!EXTERNAL_TICKET_REQUIRED"),
    ("Reply thiếu workflow reference bị chặn", {"patch": {"command_type": "workflow_reply"}}, "!WORKFLOW_REFERENCE_REQUIRED"),
])
group("G3", "event", [
    ("Public message giữ ID và loại credential", {}, "public-message"),
    ("Audience ticket khác không xem event", {"mode": "foreign_audience"}, "!AUDIENCE_FORBIDDEN"),
    ("Event workflow khác bị chặn", {"mode": "foreign_workflow"}, "!WORKFLOW_BINDING_MISMATCH"),
    ("Event nội bộ không được public", {"mode": "internal"}, "!EVENT_NOT_PUBLIC"),
    ("SSE event ID chèn newline bị chặn", {"mode": "sse_injection"}, "!EVENT_ID_INVALID"),
    ("Cursor đúng tại retention floor được đọc", {"mode": "cursor_boundary"}, 10),
    ("Cursor trước retention floor báo expired", {"mode": "cursor_expired"}, "!EVENT_CURSOR_EXPIRED"),
])


INTEGRATION = {
    "G1": [
        ("Leader/Planner thật", "Yêu cầu tiếng Việt: đi Bãi Cháy, ngân sách 10 triệu, thiếu ngày/số người", "Chọn đúng subset; hỏi phần thiếu; không gọi booking; lưu transcript", "Runtime AgentScope + catalog + Execution sandbox"),
        ("CAS trên PostgreSQL", "Hai process cập nhật budget cùng revision", "Một commit, một conflict; không mất facts/provenance", "PostgreSQL + hai kết nối độc lập"),
        ("Crash sau provisioning", "Dừng worker sau tạo session, trước lưu ACK; khởi động lại", "Giữ group/session/version; không tạo phiên thứ hai", "Worker + PostgreSQL + concrete adapter"),
        ("Thu hồi quyền khi dispatch", "Revoke grant sau lưu task, trước tool execution", "Runtime guard chặn side effect; ghi trạng thái có thể đối soát", "Identity/Execution adapter thật"),
        ("Giới hạn chi phí thực", "Hai task đang chạy cùng gần hết ngân sách", "Execution áp giới hạn/reservation đã chốt; usage được đối soát một lần", "Model sandbox + token/cost metering"),
    ],
    "G2": [
        ("UI đổi hội thoại", "Draft/retry ở A; chuyển B rồi gửi", "Không gửi draft/target/client ID của A vào B", "Browser + shell + API thật"),
        ("Hành trình approval", "Chọn quote; cần approval; approve rồi retry do mất mạng", "Đúng approval/ticket; side effect chỉ một lần", "Browser + Execution ApprovalCard + sandbox"),
        ("Eval bằng runtime thật", "Chạy bộ câu hỏi có đáp án/rubric qua mock và sandbox", "Transcript/traces/cost thật; không coi completed là đúng đáp án", "Evaluation/runtime/guard composition"),
        ("Private context transfer", "Chọn một fact từ direct chat để chuyển group", "Chỉ fact được cho phép được chuyển; không lộ private history", "Context transfer API + hai phiên browser"),
        ("Ngắt kết nối rồi tiếp tục", "Mất mạng trong lúc gửi và cancel/resume", "Hiển thị đúng trạng thái server; retry không nhân tin/task", "Browser transport + backend cancel/resume"),
    ],
    "G3": [
        ("Ingress đua unique constraint", "Hai process start cùng request/ticket trên PostgreSQL", "Một binding/job; receipt giống nhau; không trả lỗi SQL thô", "PostgreSQL + HTTP + transaction conflict handler"),
        ("Worker fencing sau crash", "Lease hết hạn khi worker cũ chưa kết thúc; worker mới tiếp quản", "Chỉ worker hợp lệ commit; không lặp side effect", "Durable worker/lease/fence + Execution"),
        ("SSE mất signal và reconnect", "Commit event rồi crash trước signal; client reconnect cursor", "DB catch-up đủ event; message dedupe; không đọc chéo ticket", "Public event log + SSE + proxy"),
        ("Close đua reply/status", "Gửi close/reply/provider progress đồng thời", "CAS xác định kết quả; không reopen; facts operation vẫn đúng quyền", "HTTP + PostgreSQL + provider fixture"),
        ("Stream revoke/slow consumer", "Thu hồi token khi stream mở; làm client đọc chậm", "Thu hồi theo mục tiêu 60 giây; queue bounded; replay được", "Proxy + auth + retention + stream transport"),
    ],
}
