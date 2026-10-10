# Async evaluation — Phase A và Phase B

Chủ sở hữu: Phó Tiến Anh. Giữ nguyên `phase_a_schema_bundle()`.

Phase B exports: `AsyncDraftValidator` / `validate_async_draft` kiểm tra scoped
policy/tool/protocol dependencies; `freeze_evaluation` tạo JSON evidence có hash;
`lifecycle_suite` cung cấp expected turns versioned; `AsyncEvaluationService`
gọi shared EvaluationRunnerPort bằng mock execution; `grade_case` và
`check_release_evidence` fail closed khi hard gate/evidence/staleness sai.
Không có fake runner trong production hoặc persistence/runtime thứ hai.

[Bàn giao Phase B](../../../../../../docs/workforce/handoffs/pho-tien-anh/PHASE_B.md)
bao gồm hợp đồng evidence, policy dialect, lệnh test và giới hạn tích hợp C/D.
