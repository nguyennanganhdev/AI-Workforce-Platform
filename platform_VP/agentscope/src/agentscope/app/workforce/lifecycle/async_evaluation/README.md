# Async evaluation — Validation, runtime và report

Chủ sở hữu: Phó Tiến Anh. Giữ nguyên `phase_a_schema_bundle()`.

Phase B exports: `AsyncDraftValidator` / `validate_async_draft` kiểm tra scoped
policy/tool/protocol dependencies; `freeze_evaluation` tạo JSON evidence có hash;
`lifecycle_suite` cung cấp expected turns versioned; `AsyncEvaluationService`
gọi shared EvaluationRunnerPort bằng mock execution; `grade_case` và
`check_release_evidence` fail closed khi hard gate/evidence/staleness sai.
Không có fake runner trong production hoặc persistence/runtime thứ hai.

[Bàn giao Phase B](../../../../../../docs/workforce/handoffs/pho-tien-anh/PHASE_B.md)
bao gồm hợp đồng evidence, policy dialect, lệnh test và giới hạn tích hợp C/D.

C5 bổ sung `RuntimeEvaluationRunner`, `SqlRuntimeEvidenceWriter`,
`SqlEvaluationRepository`, `EvaluationJobService`/`EvaluationJobHandler` và
`check_persisted_release`. Dùng canonical UOW/jobs của C1 và public runtime
context/evidence C4; callback driver phải chạy production commands/guards với
model/provider mock và fixed clock. Case association được bind trong bootstrap
UOW. Replay đọc SQL evidence/observations, không chạy lại completed turn.

Suite mới `pta-lifecycle-2` giữ operation references/confirmation sau close và
một Leader turn khi timer thực sự có trigger; frozen suite cũ giữ nguyên.
Schema export `phase_c_schema_bundle()` và lazy SQL `get_metadata()` cho C7.
Không chạy DDL, mount API hoặc tự publish trong adapter.

[C5 handoff](../../../../../../docs/workforce/handoffs/pho-tien-anh/PHASE_C_C5.md)
và [composition/metadata](../../../../../../docs/workforce/handoffs/pho-tien-anh/INTEGRATION_REQUEST_PTA_C5.md).
