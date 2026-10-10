# G3: 55 kịch bản kiểm thử — API đối tác và workflow — PHH-13–17

Ngày cập nhật: 10/10/2026. 50 kịch bản tự động local + 5 kịch bản nghiệm thu tích hợp.

## Phạm vi và bằng chứng

- Nguồn duy nhất của 50 ca tự động: `tests/workforce/orchestration/scenario_catalog.py`.
- Mỗi ID được pytest collect và chạy độc lập tại `test_scenario_matrix.py::test_scenario[ID]`; không đếm subtest hoặc assertion thành kịch bản mới.
- Trạng thái dưới đây được đọc từ `PYTEST_RESULTS.xml`, không được suy ra từ việc đã viết code.
- Fixture local: scope tenant/domain/area/manager; catalog Plan/Hotel/Car/Calculator/Technical v3 published, deployment active; repo trong bộ nhớ có rollback và khóa toàn cục; runtime/identity/jobs là fake.
- PASS local không chứng minh PostgreSQL, HTTP, model, browser, worker hay provider thật. 5 ca tích hợp bên dưới không được tính vào số test đã pass.
- PASS local: kết quả/mã lỗi đúng oracle và mọi assertion về state/call count/rollback của ca đều đạt. Gate tích hợp vẫn mở cho tới khi có môi trường và bằng chứng tương ứng.

## Cách chạy

Từ gốc `platform_VP/agentscope`:

```powershell
.\.venv\Scripts\python.exe -m pytest tests/workforce/orchestration/test_scenario_matrix.py -q -k "G3"
```

Chạy toàn bộ và cập nhật danh mục bằng kết quả thực:

```powershell
.\.venv\Scripts\python.exe -m pytest tests/workforce/orchestration -q --junitxml=docs/workforce/handoffs/phan-huy-hoang/PYTEST_RESULTS.xml
.\.venv\Scripts\python.exe tests/workforce/orchestration/render_scenario_catalog.py
```

## Bước thực hiện theo nhóm

- **policy**: Gọi continuation với policy/outcome/http_pending; effect mặc định side_effect, outcome mặc định rỗng. So sánh đúng cặp workflow_state/next_action hoặc mã lỗi.
- **http_status**: Gọi post_status với request status; so sánh 200/202. Đây là helper thuần, không phải request HTTP thật.
- **checkpoint**: Checkpoint mặc định awaiting_user, revision=1, fence=7, group=g1/session=s1. Áp cause theo input; kiểm tra state/invoke/revision, giữ pins và không mutate bản gốc.
- **close**: Checkpoint revision=1; gọi close với options; kiểm tra closed/none, không invoke; close lặp không tăng revision và không gọi provider.
- **ingress**: Envelope schema 1, start_workflow, req-1/ticket/chat/user; actor mặc định authenticated-test-actor. Áp patch/remove/retry/enqueue failure; kiểm tra receipt, một job và rollback.
- **event**: Event e1/m1, sequence=10, conversation=c1, workflow=w1, audience partner/user/ticket/chat; payload có credential giả. Áp thay đổi và kiểm tra projection/SSE/cursor.

## 50 ca tự động

Input `{}` sử dụng fixture mặc định của nhóm ở trên. `!CODE` nghĩa là phải ném lỗi nghiệp vụ đúng CODE; tuyệt đối không trả thành công.

| ID | Nhóm / kịch bản | Input hoặc thay đổi fixture | Expected result | Gate / kết quả JUnit |
|---|---|---|---|---|
| G3-S001 | policy: Read-only terminal được auto-close | `{"policy":{"effect":"read_only","auto_close":true},"outcome":{"terminal":true}}` | `["closed","none"]` | G3-LOCAL / PASS |
| G3-S002 | policy: Read-only không auto-close chờ xác nhận | `{"policy":{"effect":"read_only"},"outcome":{"terminal":true}}` | `["awaiting_confirmation","confirm_close"]` | G3-LOCAL / PASS |
| G3-S003 | policy: Side effect terminal vẫn chờ xác nhận | `{"policy":{"effect":"side_effect","auto_close":true},"outcome":{"terminal":true}}` | `["awaiting_confirmation","confirm_close"]` | G3-LOCAL / PASS |
| G3-S004 | policy: Thiếu dữ kiện chờ user | `{"outcome":{"needs_user":true}}` | `["awaiting_user","submit_reply"]` | G3-LOCAL / PASS |
| G3-S005 | policy: Cần phê duyệt chờ approval | `{"outcome":{"needs_approval":true}}` | `["awaiting_approval","submit_approval"]` | G3-LOCAL / PASS |
| G3-S006 | policy: Operation pending có tracking thì chờ event | `{"policy":{"effect":"side_effect","tracking_protocol":"v1"},"outcome":{"operation_pending":true}}` | `["waiting_external_event","watch_events"]` | G3-LOCAL / PASS |
| G3-S007 | policy: Operation pending thiếu tracking bị chặn | `{"outcome":{"operation_pending":true}}` | `!TRACKING_CAPABILITY_MISSING` | G3-LOCAL / PASS |
| G3-S008 | policy: Create unknown cần đối soát kể cả terminal | `{"outcome":{"creation_status":"unknown","terminal":true}}` | `["needs_attention","resolve_attention"]` | G3-LOCAL / PASS |
| G3-S009 | policy: Lượt chưa xong quá HTTP deadline trả watch_request | `{"http_pending":true}` | `["active","watch_request"]` | G3-LOCAL / PASS |
| G3-S010 | policy: Outcome chưa đầy đủ không báo thành công | `{}` | `!TURN_OUTCOME_INCOMPLETE` | G3-LOCAL / PASS |
| G3-S011 | policy: Policy effect không hợp lệ bị chặn | `{"policy":{"effect":"unknown"}}` | `!POLICY_EFFECT_INVALID` | G3-LOCAL / PASS |
| G3-S012 | policy: Attention ưu tiên hơn user/approval | `{"outcome":{"needs_attention":true,"needs_user":true,"needs_approval":true}}` | `["needs_attention","resolve_attention"]` | G3-LOCAL / PASS |
| G3-S013 | http_status: Accepted trả HTTP 202 | `{"status":"accepted"}` | `202` | G3-LOCAL / PASS |
| G3-S014 | http_status: Queued trả HTTP 202 | `{"status":"queued"}` | `202` | G3-LOCAL / PASS |
| G3-S015 | http_status: Running trả HTTP 202 | `{"status":"running"}` | `202` | G3-LOCAL / PASS |
| G3-S016 | http_status: Completed trả HTTP 200 | `{"status":"completed"}` | `200` | G3-LOCAL / PASS |
| G3-S017 | http_status: Failed có kết quả cuối trả HTTP 200 | `{"status":"failed"}` | `200` | G3-LOCAL / PASS |
| G3-S018 | http_status: Blocked có kết quả cuối trả HTTP 200 | `{"status":"blocked"}` | `200` | G3-LOCAL / PASS |
| G3-S019 | checkpoint: User reply hợp lệ kích hoạt runtime | `{}` | `active` | G3-LOCAL / PASS |
| G3-S020 | checkpoint: Approval result chỉ khi đang chờ approval | `{"state":"awaiting_approval","kind":"approval_result"}` | `active` | G3-LOCAL / PASS |
| G3-S021 | checkpoint: User text không thay thế approval | `{"state":"awaiting_approval"}` | `!APPROVAL_REQUIRED` | G3-LOCAL / PASS |
| G3-S022 | checkpoint: Approval ngoài trạng thái chờ bị chặn | `{"kind":"approval_result"}` | `!APPROVAL_NOT_PENDING` | G3-LOCAL / PASS |
| G3-S023 | checkpoint: Worker fence cũ không sửa checkpoint | `{"fence":6}` | `!STALE_WORKER` | G3-LOCAL / PASS |
| G3-S024 | checkpoint: Revision cũ không sửa checkpoint | `{"revision":0}` | `!REVISION_CONFLICT` | G3-LOCAL / PASS |
| G3-S025 | checkpoint: Workflow closed không nhận cause mới | `{"state":"closed"}` | `!WORKFLOW_CLOSED` | G3-LOCAL / PASS |
| G3-S026 | checkpoint: Workflow blocked không tự chạy lại | `{"state":"blocked_authorization"}` | `!WORKFLOW_BLOCKED` | G3-LOCAL / PASS |
| G3-S027 | checkpoint: Progress không đánh thức session đang HITL | `{"kind":"operation_progress","pending_hitl":true}` | `queued-without-runtime` | G3-LOCAL / PASS |
| G3-S028 | checkpoint: Timer không giả thành user reply trong HITL | `{"kind":"timer","pending_hitl":true}` | `queued-without-runtime` | G3-LOCAL / PASS |
| G3-S029 | checkpoint: Cause trùng không tăng revision lần hai | `{"duplicate":true}` | `idempotent` | G3-LOCAL / PASS |
| G3-S030 | checkpoint: Cause ngoài allowlist bị chặn | `{"kind":"model_text"}` | `!CAUSE_INVALID` | G3-LOCAL / PASS |
| G3-S031 | close: Close workflow không operation pending | `{}` | `closed` | G3-LOCAL / PASS |
| G3-S032 | close: Close lần hai giữ revision | `{"twice":true}` | `idempotent` | G3-LOCAL / PASS |
| G3-S033 | close: Close stale revision bị chặn | `{"expected_revision":0}` | `!REVISION_CONFLICT` | G3-LOCAL / PASS |
| G3-S034 | close: Close khi pending cần xác nhận stop tracking | `{"operation_pending":true}` | `!STOP_TRACKING_CONFIRMATION_REQUIRED` | G3-LOCAL / PASS |
| G3-S035 | close: Stop tracking không gọi hủy operation | `{"operation_pending":true,"stop_tracking_only":true}` | `closed` | G3-LOCAL / PASS |
| G3-S036 | ingress: Start ticket trả receipt và đúng một job | `{}` | `accepted-once` | G3-LOCAL / PASS |
| G3-S037 | ingress: Retry cùng request trả cùng receipt | `{"mode":"retry"}` | `same-receipt` | G3-LOCAL / PASS |
| G3-S038 | ingress: Cùng request ID khác message bị chặn | `{"mode":"conflict"}` | `!REQUEST_ID_CONFLICT` | G3-LOCAL / PASS |
| G3-S039 | ingress: Enqueue lỗi rollback command/binding/job | `{"mode":"rollback"}` | `empty-storage` | G3-LOCAL / PASS |
| G3-S040 | ingress: Partner chưa xác thực bị chặn | `{"actor":"unverified"}` | `!AUTHENTICATION_REQUIRED` | G3-LOCAL / PASS |
| G3-S041 | ingress: Payload giả tenant không cấp quyền | `{"patch":{"tenant_id":"other"}}` | `!AUTHORITY_FIELD_FORBIDDEN` | G3-LOCAL / PASS |
| G3-S042 | ingress: Start thiếu ticket ID bị chặn | `{"remove":"external_ticket_id"}` | `!EXTERNAL_TICKET_REQUIRED` | G3-LOCAL / PASS |
| G3-S043 | ingress: Reply thiếu workflow reference bị chặn | `{"patch":{"command_type":"workflow_reply"}}` | `!WORKFLOW_REFERENCE_REQUIRED` | G3-LOCAL / PASS |
| G3-S044 | event: Public message giữ ID và loại credential | `{}` | `public-message` | G3-LOCAL / PASS |
| G3-S045 | event: Audience ticket khác không xem event | `{"mode":"foreign_audience"}` | `!AUDIENCE_FORBIDDEN` | G3-LOCAL / PASS |
| G3-S046 | event: Event workflow khác bị chặn | `{"mode":"foreign_workflow"}` | `!WORKFLOW_BINDING_MISMATCH` | G3-LOCAL / PASS |
| G3-S047 | event: Event nội bộ không được public | `{"mode":"internal"}` | `!EVENT_NOT_PUBLIC` | G3-LOCAL / PASS |
| G3-S048 | event: SSE event ID chèn newline bị chặn | `{"mode":"sse_injection"}` | `!EVENT_ID_INVALID` | G3-LOCAL / PASS |
| G3-S049 | event: Cursor đúng tại retention floor được đọc | `{"mode":"cursor_boundary"}` | `10` | G3-LOCAL / PASS |
| G3-S050 | event: Cursor trước retention floor báo expired | `{"mode":"cursor_expired"}` | `!EVENT_CURSOR_EXPIRED` | G3-LOCAL / PASS |

## 5 ca tích hợp cần môi trường thật

Owner triển khai/test phần PHH: Phan Huy Hoàng. Foundation cung cấp contracts/auth/migration/runtime/worker theo phân công; Execution cung cấp guard/approval/provider fixture. Các dependency chưa được coi là đã bàn giao.

| ID | Kịch bản | Input / thao tác | Expected result / điều kiện PASS | Suite hoặc runner cần có | Gate / trạng thái |
|---|---|---|---|---|---|
| G3-I001 | Ingress đua unique constraint | Hai process start cùng request/ticket trên PostgreSQL | Một binding/job; receipt giống nhau; không trả lỗi SQL thô | PostgreSQL + HTTP + transaction conflict handler | G3-INTEGRATION / NOT_RUN — thiếu tích hợp/môi trường |
| G3-I002 | Worker fencing sau crash | Lease hết hạn khi worker cũ chưa kết thúc; worker mới tiếp quản | Chỉ worker hợp lệ commit; không lặp side effect | Durable worker/lease/fence + Execution | G3-INTEGRATION / NOT_RUN — thiếu tích hợp/môi trường |
| G3-I003 | SSE mất signal và reconnect | Commit event rồi crash trước signal; client reconnect cursor | DB catch-up đủ event; message dedupe; không đọc chéo ticket | Public event log + SSE + proxy | G3-INTEGRATION / NOT_RUN — thiếu tích hợp/môi trường |
| G3-I004 | Close đua reply/status | Gửi close/reply/provider progress đồng thời | CAS xác định kết quả; không reopen; facts operation vẫn đúng quyền | HTTP + PostgreSQL + provider fixture | G3-INTEGRATION / NOT_RUN — thiếu tích hợp/môi trường |
| G3-I005 | Stream revoke/slow consumer | Thu hồi token khi stream mở; làm client đọc chậm | Thu hồi theo mục tiêu 60 giây; queue bounded; replay được | Proxy + auth + retention + stream transport | G3-INTEGRATION / NOT_RUN — thiếu tích hợp/môi trường |

Khi nghiệm thu tích hợp, lưu test ID, phiên bản/build, fixture, log đã loại secret, kết quả thực và người/owner xác nhận. Không đổi NOT_RUN thành PASS từ test fake tương tự.
