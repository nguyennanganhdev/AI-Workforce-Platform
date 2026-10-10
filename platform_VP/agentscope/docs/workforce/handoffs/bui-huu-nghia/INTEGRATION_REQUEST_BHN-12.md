# BHN-12 — Canonical requirement/policy, manifest và evaluation snapshot

- **Task ID:** BHN-12; liên quan BHN-09–14.
- **Người gửi / người nhận:** Bùi Hữu Nghĩa → Nguyễn Chí Hoàng (contracts), Phó Tiến Anh (Lifecycle/reuse).
- **Trạng thái:** chờ review/chốt, chưa canonical; chưa có xác nhận của owner.

## Hiện trạng và lý do

Cập nhật sau pull `a99d506`: đã có AgentManifest(spec, business_profile, async_policy_ref, protocol_snapshot_hashes), AgentSpec.model_config_ref, BusinessProfile và ReuseDecision canonical. Chưa có AsyncHandlingPolicy typed hoặc validator/ref persistence. [canonical_samples.json](phase_a/canonical_samples.json) cung cấp mẫu shape version 1 theo yêu cầu bàn giao mới của Chí Hoàng; [PULL_UPDATE.md](phase_a/PULL_UPDATE.md) ghi mapping và giới hạn.

Mục 17.4 đã yêu cầu AsyncHandlingPolicy nhưng DTO này chưa có trong export mới. Builder cần một schema structured output và policy thống nhất để Lifecycle validate/pin/evaluate, không tạo DTO production thứ hai trong module Builder. execution_policy hiện là JsonObject, schema-valid không chứng minh policy hợp lệ.

## File/module của người nhận cần sửa

- Chí Hoàng: `contracts/async_api/`, DTO AgentSpec/AgentManifest và shared TypeScript liên quan.
- Tiến Anh: `lifecycle/async_evaluation/`, validator/snapshot và public AgentReusePort/DraftPort exports.
- Migration chỉ Chí Hoàng thực hiện sau khi các owner thống nhất metadata; Phase A chưa yêu cầu Alembic revision.

## Port/export/hook đề xuất

- Promote/revise `$defs.Requirement`, `$defs.AsyncHandlingPolicy`, `$defs.SingleAgentRequirements` trong [schema review](phase_a/builder.schema.json); giữ BusinessProfile/AgentSpec/ReuseDecision canonical hiện có trong kế hoạch.
- Vị trí đề xuất: `AgentSpec.execution_policy.async_handling`. Chốt alias/type thực tế trước triển khai; không thêm workflow/job vào manifest.
- Policy fields gồm capabilities/event_types/required_facts/effect/tracking/completion/human_confirmation/close_policy/timeout_behavior/max_wait_seconds. Trường mới, enum và timeout bounds cần owner xác nhận. Đặc biệt chốt effect aggregation khi agent có nhiều capability khác effect.
- Predicate completion dùng fact equality; validate type/value từ schema protocol, không eval biểu thức. Cùng một agent có thể đi sync hoặc pending theo output tool, không force lifecycle cố định.
- Snapshot eval giữ manifest/policy hash và mỗi tool-version protocol snapshot/hash; đổi policy/protocol cần validate/eval mới. Version published và operation cũ giữ pin.

## Input/output + error + scope

- Builder gửi manifest + ReuseDecision qua DraftPort đúng mục 6.3; Lifecycle trả draft/validation report canonical, không trả success cho manifest chỉ schema-valid nhưng thiếu capability.
- AgentReusePort.find_candidates/get_candidate cần trả business_profile, trạng thái ready/draft/blocked/inactive, covered/missing requirements, policy và các reference protocol/tool đủ để so compatibility; không trả raw credential.
- Scope đủ bốn trường; cùng area khác manager không phải candidate. Protocol/catalog invalidation không biến agent cũ thành identity mới.
- Errors giữ MISSING_REQUIRED_CAPABILITY, AGENT_ALREADY_EXISTS, AGENT_BUILD_IN_PROGRESS, REUSE_DECISION_STALE. Error details chỉ reference đúng scope.
- Chốt validator cho required_facts chứa predicate facts; event names/value thật, selection coverage đúng requirement; runtime model option phải resolve trước create/revise.

## Transaction / retry / concurrency

find_candidates và validate_decisions không giữ chỗ. Lifecycle recheck uniqueness/reuse/catalog/scope khi tạo identity/draft; expected_revision cho update. Hai build cùng nghiệp vụ phải một identity, request còn lại nhận conflict/reference. Không giữ transaction qua model/eval. Publish pin đúng snapshot/hash/revision đã eval, không cập nhật snapshot vì protocol đổi.

## Ví dụ caller trong module của tôi

```python
await reuse_port.validate_decisions(
    scope, [business_profile], decisions, expected_agent_catalog_revision,
)
draft = await draft_port.create_draft(scope, manifest, decision)
# Reuse returns existing references; no new draft for action=reuse.
# Resume/revise use the existing identity and expected revision as applicable.
```

Agent catalog revision ở caller không phải tool catalog revision; cả hai là int. requirements của canonical validate_decisions là Sequence[BusinessProfile]. get_candidate và DraftPort vẫn trả object, cần Lifecycle chốt aggregate DTO. Vị trí đề xuất execution_policy.async_handling cần thống nhất với async_policy_ref đã có: ref trỏ đâu, payload/hash được pin thế nào; chưa tự tạo bảng/ref hay nhét policy vào open JSON rồi gọi đã validated.

## Test chứng minh yêu cầu

Proposal schema tests: side effect không auto-close, confirmed booking không bắt tracking, policy không chứa runtime IDs, tracking cần timeout/facts/channel. Cần Lifecycle tests tiếp theo: required tracking không hạ xuống create-only, reuse đầy đủ, revise cùng identity, blocked connection không clone, catalog stale và concurrency, eval hash đổi làm publish bị chặn. Chưa chạy Lifecycle tests.

## Phần đã hoàn thành và đang chờ

Đã bàn giao schema/samples/prompt, semantic validation checklist và reuse decision table trong [Phase A](phase_a/README.md). Chờ xác nhận nơi đặt policy, schema canonical, snapshot semantics và reuse exports. Sau freeze sẽ chuyển test sang export chung; không publish package schema từ handoff.
