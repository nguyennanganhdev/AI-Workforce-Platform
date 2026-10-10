# Integration request — BHN Phase B

Ngày 2026-10-10. Liên quan BHN-03/07/09/11/12/13/14. Đây là yêu cầu bàn giao trong repo, chưa gửi thông báo tới thành viên khác.

## Chí Hoàng + Tiến Anh: canonical policy

Builder đã lấy schema proposal của Anh làm chuẩn: tất cả trường bắt buộc; capabilities/event_types/required_facts minItems=1; human_confirmation boolean; timeout_behavior=status_query|needs_attention; không có timeout_seconds. Schema test validate output Builder bằng schema Anh. Không đổi signatures hay DTO chung trong nhánh này.

Cần canonical DTO và nơi lưu/resolve immutable policy reference/version/hash. Manifest hiện chỉ có async_policy_ref/protocol_snapshot_hashes. Confirm preview chưa ghi policy ref giả hoặc tạo draft. Đề nghị chốt producer/consumer, schema export và migration nếu cần trước Phase C.

## Đông + Anh + Chí Hoàng: detailed snapshot và query-only

AsyncProtocolPort.get_snapshot hiện chỉ trả reference/capabilities; consumer còn cần exact hash metadata: correlation, event types và per-event fact allowlist, completion policy, positive operation timeout và pinned status-query tool version.

Builder đang dùng local injected interface:

```python
async def read(scope: Scope, snapshot: AsyncProtocolSnapshotRef) -> ProtocolReadiness
```

ProtocolReadiness là local preview view, không đề nghị owner copy DTO riêng này. Owner chốt detailed shared DTO/accessor hoặc adapter sang readiness view. Content phải được resolve theo exact ref/hash, không lấy current config thay bản đã pin. Scope-first vẫn giữ nguyên.

Query-only sample của Đông không có event_mappings. Schema policy Anh bắt buộc event_types không rỗng. Cần thống nhất event_types có mô tả normalized status updates từ query hay chỉ Provider Event. Builder không tự coi terminal_statuses là event_types. Hiện query-only với policy event types không có metadata bị block POLICY_EVENT_SEMANTICS_UNRESOLVED. Không sửa schema Anh để né vấn đề này.

Status-query tool cũng cần available/read-only, pinned version/hash và binding trong selection; tests đã kiểm tra. Cần producer xác nhận mapping/facts của query theo exact protocol và tool output schema trước live integration.

## Anh + Chí Hoàng: reuse coverage và draft handoff

Builder preview thêm marker `builder.async:<canonical JSON intent/policy>` vào BusinessProfile.required_constraints. Đây là representation tạm của preview, được ghi rõ, không thay shared contract. Same-business candidate thiếu coverage policy marker được đề xuất revise cùng identity. Cần chốt typed async profile/coverage hoặc normalization/hash chung; không nên dùng marker này làm business_key production khi chưa review producer/consumer.

Draft create/update/revision/validation và race allocation vẫn theo canonical DraftPort, thuộc Lifecycle. Phase B confirm chỉ xác nhận proposal và recheck Registry/Reuse; chưa chứng minh atomic identity allocation. Khi nối Phase C, Lifecycle vẫn revalidate trong transaction và xử lý AGENT_ALREADY_EXISTS/AGENT_BUILD_IN_PROGRESS/REUSE_DECISION_STALE; không tạo clone/retry mù.

## Chí Hoàng: HTTP/UI composition

Public Builder exports và signatures nằm trong PHASE_B.md. UI BuilderPanel nhận injected BuilderClient với prepare/confirm/cancel. Backend context dựng Scope từ principal/membership; không đưa Scope, secret hoặc fake selection vào client body.

Preview session hiện process-local, không phục hồi sau restart. Cần nối durable builder repository/job/auth trước HTTP production. Root routes, dependency/lockfile, migrations và global TypeScript không được sửa trong nhánh Nghĩa. Owner composition gắn component và endpoints thật ở Phase C; chưa dùng conversation SSE làm build events.

## Evidence

Samples/schema: phase-a.schema.json; frontend builder/tests/proposals.json (5 generated fake scenarios). Behavior tests: tests/workforce/builder/async_capabilities/test_phase_b.py. UI checks: test_ui.py dùng Edge headless. Xem PHASE_B.md để chạy lại và đọc giới hạn của bằng chứng.
