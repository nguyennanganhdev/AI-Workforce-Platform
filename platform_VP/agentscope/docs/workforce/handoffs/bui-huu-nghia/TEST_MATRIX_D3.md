# Ma trận kiểm thử D3 — Bùi Hữu Nghĩa

Ngày chạy: **2026-10-12**. Baseline triển khai `278ea4a`. Implementation
`f1f195f` đã merge qua PR #71 vào `develop2` tại `58c00f2`. Phạm vi: Builder
consumer; không phải full-platform Phase D.

Các tên method dưới đây thuộc suite tương ứng:

- **D-M**: [MissingCapabilityTests](../../../../tests/workforce/builder/phase_d/test_missing_capability.py), 11 tests.
- **D-R**: [ReuseTests](../../../../tests/workforce/builder/phase_d/test_reuse.py), 11 tests.
- **D-C**: [ConcurrentBuildTests](../../../../tests/workforce/builder/phase_d/test_concurrent_build.py), 12 tests.
- **D-U**: [BuilderD3UiTests](../../../../tests/workforce/builder/phase_d/test_ui.py), 8 browser tests, gồm 4 case mới và 4 hành vi A/B được dùng lại.
- **B**: [PhaseBTests](../../../../tests/workforce/builder/async_capabilities/test_phase_b.py).
- **C3**: [BuilderProtocolTests](../../../../tests/workforce/builder/phase_c/test_integration.py).

Mọi hàng **Pass** là evidence hành vi consumer ở lần chạy này, không là evidence
row-lock/unique constraint của PostgreSQL. Không đếm subtests thành test độc lập.

| ID / task liên quan | Fault / test evidence | Kết quả và giới hạn |
|---|---|---|
| M01 / BHN-03/07 | D-M `test_missing_required_at_prepare_and_deleted_before_confirm` | Pass: unavailable/absent block; xóa tool làm refresh revision 2 needs_input, không làm đổi proposal cũ |
| M02 / BHN-03/14 | B `test_optional_capability_is_visible_without_blocking`; D-U `test_optional_missing_keeps_confirmation_available` | Pass: optional missing không trở thành covered và không chặn confirm |
| M03 / BHN-03 | D-M `test_repeated_or_exhausted_cursor_fails_closed_with_bounded_queries`; B `test_pagination_optional_coverage_and_disabled_tools` | Pass: cursor loop/budget có giới hạn; catalog phân trang dùng được |
| M04 / BHN-07/13 | D-M `test_invalid_schema_and_wrong_effect_are_not_confirmable`; C3 effect/mode/tool-version regressions | Pass: blocker trước confirm; không chờ tới Lifecycle mới biết mismatch |
| M05 / BHN-12/13 | B `test_tracking_create_only_missing_details_and_facts`; C3 `test_missing_required_event_fact_is_blocked_with_real_metadata`; Registry configuration tests | Pass: thiếu metadata/facts/correlation/timeout bị chặn ở schema/readiness đúng tầng |
| M06 / BHN-13 | D-M `test_query_dependency_faults_refresh_and_keep_tracking_requirement` | Pass: query bị xóa/disable/mất capability/đổi effect/version đều refresh needs_input, không giảm tracking |
| M07 / BHN-12/14 | C3 read-only/terminal/pending-create-only/query-only tests; D-U inherited missing/query-only | Pass: read-only/terminal không ép polling; pending/query-only giữ blocking semantics đã chốt |
| M08 / BHN-03/13 | C3 multi-capability/query-fallback/dedup/secondary-drift regressions | Pass: một binding/version, giữ coverage và kiểm tra capability phụ |
| P01 / BHN-07/11/13 | D-M `test_mapping_drift_refreshes_pin_and_requires_confirmation` | Pass: notice + revision 2 + pin mới; old revision bị từ chối, cần confirm lại |
| P02 / BHN-07/13 | D-M `test_drift_after_confirm_stops_test_caller_before_draft_handoff` | Pass: pin/hash stale chặn caller test trước DraftPort; manifest không bị rewrite |
| P03 / BHN-13 | D-M `test_disable_at_each_gate_preserves_old_pin_without_write` | Pass: prepare/confirm/prewrite bị PermissionError; replay confirm không bỏ qua prewrite gate |
| P04 / BHN-13 | D-M disable test; ordering test | Pass: exact old metadata/pin vẫn đọc được sau revise/disable; không cấp new-build availability |
| P05 / BHN-09/13 | D-M `test_scope_dimensions_and_forged_hash_are_rejected`; D-C scope isolation | Pass: đủ 4 chiều Scope; forged hash; proposal/candidate không dùng chéo manager |
| P06 / BHN-13 | D-M mapping test và `test_ordering_only_drift_keeps_old_metadata_and_blocks_stale_prewrite` | Pass: current đổi mapping/ordering, old pin giữ metadata; consumer không normalize event |
| R01 / BHN-09/10 | D-R `test_all_reused_preserves_identity_and_exact_validation_arguments` | Pass: completed_reused, identity/version cũ, exact profile/Scope/decision/revision gửi port |
| R02 / BHN-10/11 | D-R draft resume và missing draft reference tests | Pass sau fix: draft_id hợp lệ → resume; draft_id thiếu → clarify/block dù có old published version |
| R03 / BHN-09/13 | D-R `test_missing_capability_or_policy_revises_same_identity`, `test_candidate_missing_required_capability_is_revised_with_diagnosis` | Pass: revise cùng identity, missing policy/capability hiện rõ; business/policy equivalence rộng hơn vẫn là kết luận provider theo port |
| R04 / BHN-09/10 | D-R blocked/inactive/metadata test | Pass: repair/block; credential blocker không chuyển create để clone |
| R05 / BHN-09/10 | D-R ambiguity/partial/uncertain test | Pass: clarify; thiếu version/draft reference không suy ra ready |
| R06 / BHN-09 | D-R different-business test; D-C same-business/two-scope | Pass: theo match_type của provider, không gộp theo display similarity; cùng area khác manager không reuse chéo |
| R07 / BHN-09/10 | D-R mixed-batch và conflicting-policy tests; B duplicate-item questions | Pass: mixed reuse/create, gộp exact duplicate; policy/câu hỏi khác không bị bỏ |
| R08 / BHN-11 | D-R `test_changed_reuse_availability_refreshes_to_repair_not_create`; D-C three canonical conflicts | Pass: refresh candidates/revision/decision, user confirm lại |
| C01 / BHN-11 | D-C `test_same_message_serializes_and_conflicting_payload_is_rejected` | Pass: extraction 1 lần, same payload cùng proposal; khác payload → IDEMPOTENCY_CONFLICT, phạm vi một service |
| C02 / BHN-11 | D-C `test_two_edits_same_revision_have_one_winner` | Pass: một edit revision 2; bên thua REVISION_CONFLICT, không lost update |
| C03 / BHN-11 | D-C `test_two_confirms_replay_one_reuse_validation` | Pass: replay kết quả, validate_decisions 1 lần; không chứng minh reservation DB |
| C04 / BHN-11 | D-C edit↔confirm, cancel↔confirm, confirm↔cancel và cancel↔edit tests | Pass: thứ tự lock được điều khiển bằng barrier; không hồi sinh entry hoặc ghi đè confirmed proposal |
| C05 / BHN-11 | D-C `test_two_instances_refresh_each_canonical_conflict_and_require_reconfirmation` | Pass với canonical-port double: cả ALREADY_EXISTS/BUILD_IN_PROGRESS/STALE đều refresh; không phải hai actual DB writes |
| C06 / BHN-07/13 | D-M `test_protocol_drift_during_dependency_reads_is_not_hidden`, after-confirm/ordering tests | Pass: observe old pin trong prepare, confirm recheck current và refresh; prewrite từ chối stale. Khoảng check→write/ABA chưa atomic |
| C07 / BHN-02/11 | D-C extraction cancellation/schema-error/timeout retry và port prepare failure retry | Pass: không cache success dở dang, retry cùng message được, lock/tasks được giải phóng |
| C08 / BHN-09/11 | D-C `test_scope_isolation_for_same_message_and_business_in_one_service` | Pass: idempotency riêng từng Scope; wrong-scope confirm/cancel bị từ chối; cancel A không làm mất B |
| U01 / BHN-14 | D-U refresh/permission/optional/late-confirm cùng reuse/revise/mobile từ A/B | **8 pass trên Edge headless**; demo/client fake, không HTTP production. Không lỗi JavaScript; mobile không tràn ngang |

## Suite totals và loại evidence

| Nhóm | Lần chạy mới | Thật / fake |
|---|---|---|
| Builder D3 backend | **34 pass** | Proposal/selector/readiness/hook + C1 UOW/C2 SQL protocol/Lifecycle validator thật; SQLite facade, model/catalog/reuse/policy/caller/draft spy là test doubles |
| Builder A/B/C3 + D3 + shared contracts | **100 pass** | 31 A/B + 26 C3 + 34 D3 + 9 contracts; browser không nằm trong số 100 |
| Builder D3 browser | **8 pass** | Edge headless + Vite owned demo + fault client fake; 4 case D3 mới và 4 regression A/B |
| Registry A/B/C2/D2 | **30 pass, 1 skip** | SQL functional + protocol/normalizer contracts; PostgreSQL DSN chưa cấu hình |
| Foundation D1 supervisor | **2 pass** | Restart harness đã bàn giao; không thêm worker Builder |
| Black/compile/import/ESLint/TypeScript/ownership | Xem PHASE_D_D3.md | Checks chỉ vùng sửa, core Builder không eager-import SQLAlchemy |

Chưa xác minh: distributed build-session persistence, hai canonical DB writes
với uniqueness/lock PostgreSQL, atomic protocol-check + draft-write, production
Builder HTTP wiring, C6 E2E chạy lại và CI run mới. Đây là giới hạn platform/seam,
không chuyển thành task viết provider/migration hoặc D4 của Nghĩa.
