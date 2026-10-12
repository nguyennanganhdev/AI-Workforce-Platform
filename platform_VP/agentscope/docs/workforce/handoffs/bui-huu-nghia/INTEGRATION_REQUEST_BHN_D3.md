# Yêu cầu phối hợp D3 — Bùi Hữu Nghĩa

Ngày **2026-10-12**. Baseline `278ea4a`. D3 Builder consumer đã code/test;
file này ghi điểm phối hợp, không giao thêm task D4 cho Nghĩa.

## D3-CI — Nguyễn Chí Hoàng

File cần owner sửa: `.github/workflows/workforce-phase-d.yml` **ở repo root**.
Workflow hiện chạy C7/D1/D2/Registry/Orchestration/C6, chưa chạy Builder D3.

Đề nghị thêm command riêng sau install dependencies, working directory
`platform_VP/agentscope`:

```sh
python -m unittest tests.workforce.builder.async_capabilities.test_phase_a tests.workforce.builder.async_capabilities.test_phase_b tests.workforce.builder.phase_c.test_integration tests.workforce.builder.phase_d.test_missing_capability tests.workforce.builder.phase_d.test_reuse tests.workforce.builder.phase_d.test_concurrent_build tests.workforce.foundation.test_contracts -q
```

Local command có **100 pass**. Đây là suite deterministic không gọi MCP/model
trả phí. Browser demo suite chạy riêng nếu CI đã có Playwright/browser; không
tự thêm runner/dependency vào PR của Nghĩa. Chí Hoàng sở hữu environment checker,
test DSN và global CI; local thiếu `pytest`, `aiosqlite`, DSN không được che bằng
trạng thái “CI pass”.

## D3-WRITE — Phó Tiến Anh (provider), Nguyễn Chí Hoàng (composition/DB), Phan Hoàng Dũng (E2E)

Trigger: hai Builder instances cùng prepare từ agent catalog cũ, cả hai muốn
tạo identity/draft cùng nghiệp vụ trong một Scope.

Consumer đã có: `ProposalService.confirm` recheck decisions và refresh khi port
trả `AGENT_ALREADY_EXISTS`, `AGENT_BUILD_IN_PROGRESS`, `REUSE_DECISION_STALE`.
`ProtocolBuildValidator.validate(scope, item, manifest)` giữ pin/coverage/policy
trước handoff. D3 dùng fake để xác minh phản ứng và revision/reconfirmation.

Public boundary giữ nguyên shared contract:

```text
AgentReusePort.validate_decisions(scope, requirements, reuse_decisions, expected_catalog_revision)
DraftPort.create_draft(scope, manifest, reuse_decision, batch_id?)
DraftPort.update_draft(scope, draft_id, expected_revision, manifest, reuse_decision)
```

Không coi validate_decisions là reservation; không giữ LLM call trong DB transaction.
Khi canonical provider/wiring có sẵn, owner cần evidence PostgreSQL cho:

- Một identity chuẩn theo `(tenant, domain, area, manager, business_key)`.
- Writer thua nhận conflict/reference hợp lệ trong đúng Scope, không clone.
- Recheck dependency/reuse và uniqueness/CAS trong write transaction phù hợp;
  Builder prewrite check riêng không bảo đảm atomicity xuyên module.
- Resume/revise trả `agent_id/draft_id/version_id` đúng trạng thái. Candidate
  DRAFT không có draft_id hiện bị Builder `CANDIDATE_METADATA_REQUIRED` block.

Reproducer phía consumer:
`ConcurrentBuildTests.test_two_instances_refresh_each_canonical_conflict_and_require_reconfirmation`
và `ReuseTests.test_draft_candidate_without_draft_reference_blocks_even_with_old_version`.
Test ở `tests/workforce/builder/phase_d/`; không patch provider/DB của người khác.

Đây là giới hạn cần evidence cho full-platform concurrent-write gate, **không
yêu cầu output D4 mới để mở D3 consumer**. Dũng sở hữu E2E assertion actual writes;
Tiến Anh sở hữu provider Lifecycle; Chí Hoàng sở hữu migration/composition/CI.
