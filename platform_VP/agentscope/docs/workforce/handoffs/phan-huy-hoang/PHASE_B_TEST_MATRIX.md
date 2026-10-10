# Phase B test matrix

Gate MB local: all rows pass, no skip. Inputs are defined in each referenced test body; fake clock, atomic UOW, runtime, operation and signals are test-only.

| ID | Input/scenario | Expected | Suite |
|---|---|---|---|
| B001 | start reserves binding and checkpoint job atomically | Assert behavior and committed projection in test body | `test_phase_b.test_B001_start_reserves_binding_and_checkpoint_job_atomically` |
| B002 | retry reuses group and job | Assert behavior and committed projection in test body | `test_phase_b.test_B002_retry_reuses_group_and_job` |
| B003 | two tickets same user and agent have separate sessions | Assert behavior and committed projection in test body | `test_phase_b.test_B003_two_tickets_same_user_and_agent_have_separate_sessions` |
| B004 | start commit failure rolls back | Reject/discard; asserted durable state remains isolated | `test_phase_b.test_B004_start_commit_failure_rolls_back` |
| B005 | reply keeps group session and pins | Assert behavior and committed projection in test body | `test_phase_b.test_B005_reply_keeps_group_session_and_pins` |
| B006 | reply to other ticket is denied | Reject/discard; asserted durable state remains isolated | `test_phase_b.test_B006_reply_to_other_ticket_is_denied` |
| B007 | reply stale revision does not enqueue | Assert behavior and committed projection in test body | `test_phase_b.test_B007_reply_stale_revision_does_not_enqueue` |
| B008 | reply changed content same id conflicts | Reject/discard; asserted durable state remains isolated | `test_phase_b.test_B008_reply_changed_content_same_id_conflicts` |
| B009 | revoked actor cannot reply | Reject/discard; asserted durable state remains isolated | `test_phase_b.test_B009_revoked_actor_cannot_reply` |
| B010 | provider credential cannot read customer events | Reject/discard; asserted durable state remains isolated | `test_phase_b.test_B010_provider_credential_cannot_read_customer_events` |
| B011 | pending request runs once and persists processed cause | Assert behavior and committed projection in test body | `test_phase_b.test_B011_pending_request_runs_once_and_persists_processed_cause` |
| B012 | message id is identical in result event and snapshot | Assert behavior and committed projection in test body | `test_phase_b.test_B012_message_id_is_identical_in_result_event_and_snapshot` |
| B013 | response only published read only auto closes | Assert behavior and committed projection in test body | `test_phase_b.test_B013_response_only_published_read_only_auto_closes` |
| B014 | interactive cannot auto close | Reject/discard; asserted durable state remains isolated | `test_phase_b.test_B014_interactive_cannot_auto_close` |
| B015 | approval wait requires real pending ref | Assert behavior and committed projection in test body | `test_phase_b.test_B015_approval_wait_requires_real_pending_ref` |
| B016 | wait requires tracking pattern and pending operation | Assert behavior and committed projection in test body | `test_phase_b.test_B016_wait_requires_tracking_pattern_and_pending_operation` |
| B017 | terminal operation cannot enter external wait | Reject/discard; asserted durable state remains isolated | `test_phase_b.test_B017_terminal_operation_cannot_enter_external_wait` |
| B018 | no operation cannot enter external wait | Reject/discard; asserted durable state remains isolated | `test_phase_b.test_B018_no_operation_cannot_enter_external_wait` |
| B019 | interleaved turns keep correct group and messages | Assert behavior and committed projection in test body | `test_phase_b.test_B019_interleaved_turns_keep_correct_group_and_messages` |
| B020 | unbound trigger is rejected before runtime | Reject/discard; asserted durable state remains isolated | `test_phase_b.test_B020_unbound_trigger_is_rejected_before_runtime` |
| B021 | forged approval cannot resume | Reject/discard; asserted durable state remains isolated | `test_phase_b.test_B021_forged_approval_cannot_resume` |
| B022 | verified approval preserves other pins | Assert behavior and committed projection in test body | `test_phase_b.test_B022_verified_approval_preserves_other_pins` |
| B023 | lease prevents two workers running same workflow | Assert behavior and committed projection in test body | `test_phase_b.test_B023_lease_prevents_two_workers_running_same_workflow` |
| B024 | expired lease candidate cannot commit | Reject/discard; asserted durable state remains isolated | `test_phase_b.test_B024_expired_lease_candidate_cannot_commit` |
| B025 | replaced fence candidate cannot commit | Reject/discard; asserted durable state remains isolated | `test_phase_b.test_B025_replaced_fence_candidate_cannot_commit` |
| B026 | close during turn discards late message | Reject/discard; asserted durable state remains isolated | `test_phase_b.test_B026_close_during_turn_discards_late_message` |
| B027 | runtime guard blocks side effect after close | Assert behavior and committed projection in test body | `test_phase_b.test_B027_runtime_guard_blocks_side_effect_after_close` |
| B028 | runtime exception releases lease | Assert behavior and committed projection in test body | `test_phase_b.test_B028_runtime_exception_releases_lease` |
| B029 | commit failure can retry from last checkpoint | Reject/discard; asserted durable state remains isolated | `test_phase_b.test_B029_commit_failure_can_retry_from_last_checkpoint` |
| B030 | revoked grant during runtime discards result | Reject/discard; asserted durable state remains isolated | `test_phase_b.test_B030_revoked_grant_during_runtime_discards_result` |
| B031 | event fault rolls back checkpoint result and messages | Reject/discard; asserted durable state remains isolated | `test_phase_b.test_B031_event_fault_rolls_back_checkpoint_result_and_messages` |
| B032 | signal loss still keeps result replayable | Assert behavior and committed projection in test body | `test_phase_b.test_B032_signal_loss_still_keeps_result_replayable` |
| B033 | external event applies fact and checkpoint without llm | Assert behavior and committed projection in test body | `test_phase_b.test_B033_external_event_applies_fact_and_checkpoint_without_llm` |
| B034 | duplicate external event no new job or event | Assert behavior and committed projection in test body | `test_phase_b.test_B034_duplicate_external_event_no_new_job_or_event` |
| B035 | old provider version does not revert status | Assert behavior and committed projection in test body | `test_phase_b.test_B035_old_provider_version_does_not_revert_status` |
| B036 | external event during approval keeps HITL | Assert behavior and committed projection in test body | `test_phase_b.test_B036_external_event_during_approval_keeps_HITL` |
| B037 | wait time does not spend tokens | Assert behavior and committed projection in test body | `test_phase_b.test_B037_wait_time_does_not_spend_tokens` |
| B038 | external event commit failure rolls back all | Reject/discard; asserted durable state remains isolated | `test_phase_b.test_B038_external_event_commit_failure_rolls_back_all` |
| B039 | close is idempotent and no duplicate public close | Assert behavior and committed projection in test body | `test_phase_b.test_B039_close_is_idempotent_and_no_duplicate_public_close` |
| B040 | close wrong revision is rejected | Reject/discard; asserted durable state remains isolated | `test_phase_b.test_B040_close_wrong_revision_is_rejected` |
| B041 | close wrong ticket is rejected | Reject/discard; asserted durable state remains isolated | `test_phase_b.test_B041_close_wrong_ticket_is_rejected` |
| B042 | close does not close other workflow | Assert behavior and committed projection in test body | `test_phase_b.test_B042_close_does_not_close_other_workflow` |
| B043 | closed workflow reply cannot reopen | Reject/discard; asserted durable state remains isolated | `test_phase_b.test_B043_closed_workflow_reply_cannot_reopen` |
| B044 | closed turn uses no model | Assert behavior and committed projection in test body | `test_phase_b.test_B044_closed_turn_uses_no_model` |
| B045 | pending operation requires explicit stop tracking | Assert behavior and committed projection in test body | `test_phase_b.test_B045_pending_operation_requires_explicit_stop_tracking` |
| B046 | pending approval cannot be bypassed by stop tracking | Reject/discard; asserted durable state remains isolated | `test_phase_b.test_B046_pending_approval_cannot_be_bypassed_by_stop_tracking` |
| B047 | close event failure rolls back state | Reject/discard; asserted durable state remains isolated | `test_phase_b.test_B047_close_event_failure_rolls_back_state` |
| B048 | history paginates in order | Assert behavior and committed projection in test body | `test_phase_b.test_B048_history_paginates_in_order` |
| B049 | foreign cursor never reads from start | Assert behavior and committed projection in test body | `test_phase_b.test_B049_foreign_cursor_never_reads_from_start` |
| B050 | expired cursor requires snapshot | Reject/discard; asserted durable state remains isolated | `test_phase_b.test_B050_expired_cursor_requires_snapshot` |
| B051 | snapshot and history recheck revoked grant | Assert behavior and committed projection in test body | `test_phase_b.test_B051_snapshot_and_history_recheck_revoked_grant` |
| B052 | replay rejects repository cross conversation leak | Reject/discard; asserted durable state remains isolated | `test_phase_b.test_B052_replay_rejects_repository_cross_conversation_leak` |
| B053 | sse replays durable records before wait | Assert behavior and committed projection in test body | `test_phase_b.test_B053_sse_replays_durable_records_before_wait` |
| B054 | sse lost signal catches up from log after heartbeat | Assert behavior and committed projection in test body | `test_phase_b.test_B054_sse_lost_signal_catches_up_from_log_after_heartbeat` |
| B055 | sse revocation checked on next replay page | Assert behavior and committed projection in test body | `test_phase_b.test_B055_sse_revocation_checked_on_next_replay_page` |
| B056 | injected uow does not commit or notify early | Assert behavior and committed projection in test body | `test_phase_b.test_B056_injected_uow_does_not_commit_or_notify_early` |
| B057 | runtime does not hold open transaction | Assert behavior and committed projection in test body | `test_phase_b.test_B057_runtime_does_not_hold_open_transaction` |
| B058 | new instance resumes checkpoint without rebuild | Assert behavior and committed projection in test body | `test_phase_b.test_B058_new_instance_resumes_checkpoint_without_rebuild` |
| B059 | external event after close cannot create trigger | Reject/discard; asserted durable state remains isolated | `test_phase_b.test_B059_external_event_after_close_cannot_create_trigger` |
| B060 | parallel claims run model once | Assert behavior and committed projection in test body | `test_phase_b.test_B060_parallel_claims_run_model_once` |
| B061 | Reject runtime mutation candidate.trigger_id | Reject/discard; asserted durable state remains isolated | `test_phase_b.test_B061_runtime_boundary` |
| B062 | Reject runtime mutation candidate.expected_state_revision | Reject/discard; asserted durable state remains isolated | `test_phase_b.test_B062_runtime_boundary` |
| B063 | Reject runtime mutation candidate.checkpoint.workflow_id | Reject/discard; asserted durable state remains isolated | `test_phase_b.test_B063_runtime_boundary` |
| B064 | Reject runtime mutation candidate.checkpoint.session_refs | Reject/discard; asserted durable state remains isolated | `test_phase_b.test_B064_runtime_boundary` |
| B065 | Reject runtime mutation candidate.checkpoint.agent_version_pins | Reject/discard; asserted durable state remains isolated | `test_phase_b.test_B065_runtime_boundary` |
| B066 | Reject runtime mutation candidate.checkpoint.protocol_pins | Reject/discard; asserted durable state remains isolated | `test_phase_b.test_B066_runtime_boundary` |
| B067 | Reject runtime mutation candidate.checkpoint.last_processed_causes | Reject/discard; asserted durable state remains isolated | `test_phase_b.test_B067_runtime_boundary` |
| B068 | Reject runtime mutation candidate.checkpoint.used_budget.model_turns | Reject/discard; asserted durable state remains isolated | `test_phase_b.test_B068_runtime_boundary` |
| B069 | Reject runtime mutation candidate.checkpoint.used_budget.tool_calls | Reject/discard; asserted durable state remains isolated | `test_phase_b.test_B069_runtime_boundary` |
| B070 | Reject runtime mutation candidate.checkpoint.used_budget.input_tokens | Reject/discard; asserted durable state remains isolated | `test_phase_b.test_B070_runtime_boundary` |
| B071 | Reject runtime mutation candidate.result.messages.0.workflow_id | Reject/discard; asserted durable state remains isolated | `test_phase_b.test_B071_runtime_boundary` |
| B072 | event provider integration id | Assert behavior and committed projection in test body | `test_phase_b.test_B072_event_provider_integration_id` |
| B073 | event protocol schema hash | Assert behavior and committed projection in test body | `test_phase_b.test_B073_event_protocol_schema_hash` |
| B074 | event external job id | Assert behavior and committed projection in test body | `test_phase_b.test_B074_event_external_job_id` |
| B075 | event client reference | Assert behavior and committed projection in test body | `test_phase_b.test_B075_event_client_reference` |
| B076 | invalid page limit | Reject/discard; asserted durable state remains isolated | `test_phase_b.test_B076_invalid_page_limit` |
| B077 | invalid page limit | Reject/discard; asserted durable state remains isolated | `test_phase_b.test_B077_invalid_page_limit` |
| B078 | invalid page limit | Reject/discard; asserted durable state remains isolated | `test_phase_b.test_B078_invalid_page_limit` |
| B079 | invalid page limit | Reject/discard; asserted durable state remains isolated | `test_phase_b.test_B079_invalid_page_limit` |
| B080 | invalid page limit | Reject/discard; asserted durable state remains isolated | `test_phase_b.test_B080_invalid_page_limit` |
| B081 | pending post has watch request | Assert behavior and committed projection in test body | `test_phase_b_ingress.test_B081_pending_post_has_watch_request` |
| B082 | completed post same message as event | Assert behavior and committed projection in test body | `test_phase_b_ingress.test_B082_completed_post_same_message_as_event` |
| B083 | retry post never rebuilds | Assert behavior and committed projection in test body | `test_phase_b_ingress.test_B083_retry_post_never_rebuilds` |
| B084 | same request changed content conflicts | Reject/discard; asserted durable state remains isolated | `test_phase_b_ingress.test_B084_same_request_changed_content_conflicts` |
| B085 | actor cannot impersonate user | Reject/discard; asserted durable state remains isolated | `test_phase_b_ingress.test_B085_actor_cannot_impersonate_user` |
| B086 | other user cannot read result | Reject/discard; asserted durable state remains isolated | `test_phase_b_ingress.test_B086_other_user_cannot_read_result` |
| B087 | result revalidates grant | Assert behavior and committed projection in test body | `test_phase_b_ingress.test_B087_result_revalidates_grant` |
| B088 | wait deadline returns pending | Assert behavior and committed projection in test body | `test_phase_b_ingress.test_B088_wait_deadline_returns_pending` |
| B089 | signal wakes and rereads result | Assert behavior and committed projection in test body | `test_phase_b_ingress.test_B089_signal_wakes_and_rereads_result` |
| B090 | atomic post failure leaves no claim | Reject/discard; asserted durable state remains isolated | `test_phase_b_ingress.test_B090_atomic_post_failure_leaves_no_claim` |
| B091 | reply keeps group without bootstrap | Assert behavior and committed projection in test body | `test_phase_b_ingress.test_B091_reply_keeps_group_without_bootstrap` |
| B092 | interleaved post results keep own message | Assert behavior and committed projection in test body | `test_phase_b_ingress.test_B092_interleaved_post_results_keep_own_message` |
| B093 | close before result returns none action | Assert behavior and committed projection in test body | `test_phase_b_ingress.test_B093_close_before_result_returns_none_action` |
| B094 | naive wait deadline rejected | Reject/discard; asserted durable state remains isolated | `test_phase_b_ingress.test_B094_naive_wait_deadline_rejected` |
| B095 | scope injection rejected | Reject/discard; asserted durable state remains isolated | `test_phase_b_ingress.test_B095_scope_injection_rejected` |
| B096 | start checkpoint ref is persisted | Assert behavior and committed projection in test body | `test_phase_b_review.test_B096_start_checkpoint_ref_is_persisted` |
| B097 | conflicting duplicate inbox hash is rejected | Reject/discard; asserted durable state remains isolated | `test_phase_b_review.test_B097_conflicting_duplicate_inbox_hash_is_rejected` |
| B098 | both correlations must match | Assert behavior and committed projection in test body | `test_phase_b_review.test_B098_both_correlations_must_match` |
| B099 | pending approval cannot disappear on plain reply | Reject/discard; asserted durable state remains isolated | `test_phase_b_review.test_B099_pending_approval_cannot_disappear_on_plain_reply` |
| B100 | resolving A cannot remove pending B | Reject/discard; asserted durable state remains isolated | `test_phase_b_review.test_B100_resolving_A_cannot_remove_pending_B` |
| B101 | runtime cannot discard pending operation | Reject/discard; asserted durable state remains isolated | `test_phase_b_review.test_B101_runtime_cannot_discard_pending_operation` |
| B102 | foreign operation is rejected even when not waiting | Reject/discard; asserted durable state remains isolated | `test_phase_b_review.test_B102_foreign_operation_is_rejected_even_when_not_waiting` |
| B103 | read only guard rejects write side effect | Reject/discard; asserted durable state remains isolated | `test_phase_b_review.test_B103_read_only_guard_rejects_write_side_effect` |
| B104 | plain close requires confirmation state | Assert behavior and committed projection in test body | `test_phase_b_review.test_B104_plain_close_requires_confirmation_state` |
| B105 | same conversation wrong workflow event is rejected | Reject/discard; asserted durable state remains isolated | `test_phase_b_review.test_B105_same_conversation_wrong_workflow_event_is_rejected` |
| B106 | full MB lifecycle request progress confirmation close | Assert behavior and committed projection in test body | `test_phase_b_review.test_B106_full_MB_lifecycle_request_progress_confirmation_close` |
| B107 | close uses shared command namespace | Assert behavior and committed projection in test body | `test_phase_b_review.test_B107_close_uses_shared_command_namespace` |
| B108 | close retry ignores old revision after claim | Assert behavior and committed projection in test body | `test_phase_b_review.test_B108_close_retry_ignores_old_revision_after_claim` |
| B109 | all state projections are defined | Assert behavior and committed projection in test body | `test_phase_b_review.test_B109_all_state_projections_are_defined` |
| B110 | opaque ids cannot collide in job dedupe key | Reject/discard; asserted durable state remains isolated | `test_phase_b_review.test_B110_opaque_ids_cannot_collide_in_job_dedupe_key` |
| B111 | runtime message naive time is rejected | Reject/discard; asserted durable state remains isolated | `test_phase_b_review.test_B111_runtime_message_naive_time_is_rejected` |
| B112 | new start cannot implicitly reply to bound ticket | Reject/discard; asserted durable state remains isolated | `test_phase_b_review.test_B112_new_start_cannot_implicitly_reply_to_bound_ticket` |
| UI001 | POST then SSE produces one bubble | Explicit expect assertions; mismatch fails before cursor/state write | `timeline.test.ts` |
| UI002 | SSE then POST produces one bubble | Explicit expect assertions; mismatch fails before cursor/state write | `timeline.test.ts` |
| UI003 | repeated event is deduped | Explicit expect assertions; mismatch fails before cursor/state write | `timeline.test.ts` |
| UI004 | identity participates in cache key | Explicit expect assertions; mismatch fails before cursor/state write | `timeline.test.ts` |
| UI005 | ticket participates in cache key | Explicit expect assertions; mismatch fails before cursor/state write | `timeline.test.ts` |
| UI006 | message conflict fails without mutation | Explicit expect assertions; mismatch fails before cursor/state write | `timeline.test.ts` |
| UI007 | status is a card, never an assistant bubble | Explicit expect assertions; mismatch fails before cursor/state write | `timeline.test.ts` |
| UI008 | workflow closed cannot reopen | Explicit expect assertions; mismatch fails before cursor/state write | `timeline.test.ts` |
| UI009 | older receipt cannot regress status | Explicit expect assertions; mismatch fails before cursor/state write | `timeline.test.ts` |
| UI010 | snapshot catch-up dedupes next POST | Explicit expect assertions; mismatch fails before cursor/state write | `timeline.test.ts` |
| UI011 | sequence reversal fails | Explicit expect assertions; mismatch fails before cursor/state write | `timeline.test.ts` |
| UI012 | approvals have independent ids | Explicit expect assertions; mismatch fails before cursor/state write | `timeline.test.ts` |
| UI013 | closed stream cannot introduce new assistant message | Explicit expect assertions; mismatch fails before cursor/state write | `timeline.test.ts` |
| UI014 | snapshot foreign message fails | Explicit expect assertions; mismatch fails before cursor/state write | `timeline.test.ts` |
| UI015 | snapshot older revision fails | Explicit expect assertions; mismatch fails before cursor/state write | `timeline.test.ts` |
| UI016 | invalid timestamp fails | Explicit expect assertions; mismatch fails before cursor/state write | `timeline.test.ts` |
| UI017 | unknown event fails without cursor advancement | Explicit expect assertions; mismatch fails before cursor/state write | `timeline.test.ts` |
| UI018 | failed receipt for other ticket cannot update state | Explicit expect assertions; mismatch fails before cursor/state write | `timeline.test.ts` |
| UI019 | invalid closed event fails | Explicit expect assertions; mismatch fails before cursor/state write | `timeline.test.ts` |
| UI020 | status revision conflict fails | Explicit expect assertions; mismatch fails before cursor/state write | `timeline.test.ts` |
| UI026 | follower applies event and stops on abort | Explicit expect assertions; mismatch fails before cursor/state write | `timeline.test.ts` |
| UI027 | wrong binding stops before cursor is saved | Explicit expect assertions; mismatch fails before cursor/state write | `timeline.test.ts` |
| UI028 | 410 recovers snapshot and uses fresh cursor | Explicit expect assertions; mismatch fails before cursor/state write | `timeline.test.ts` |
| UI029 | denied stream stops and clears its cursor | Explicit expect assertions; mismatch fails before cursor/state write | `timeline.test.ts` |
| UI030 | close API rejects other ticket before fetch | Explicit expect assertions; mismatch fails before cursor/state write | `timeline.test.ts` |
| UI031 | close API uses exact workflow and revision | Explicit expect assertions; mismatch fails before cursor/state write | `timeline.test.ts` |
| UI032 | abort during snapshot never updates detached chat | Explicit expect assertions; mismatch fails before cursor/state write | `timeline.test.ts` |
| UI033 | renders waiting and reconnecting independently | Explicit expect assertions; mismatch fails before cursor/state write | `timeline-render.test.tsx` |
| UI034 | closed ticket disables close and cannot offer stop tracking | Explicit expect assertions; mismatch fails before cursor/state write | `timeline-render.test.tsx` |
| UI035 | assistant text is escaped and labeled | Explicit expect assertions; mismatch fails before cursor/state write | `timeline-render.test.tsx` |
| UI036 | reuses Execution ApprovalCard only for approval bound to this timeline | Explicit expect assertions; mismatch fails before cursor/state write | `timeline-render.test.tsx` |
| UI021 | Mutate event conversation_id to B after valid A control | Reject; A state unchanged | `timeline.test.ts` |
| UI022 | Mutate event workflow_id to B after valid A control | Reject; A state unchanged | `timeline.test.ts` |
| UI023 | Mutate event external_user_id to B after valid A control | Reject; A state unchanged | `timeline.test.ts` |
| UI024 | Mutate event external_conversation_id to B after valid A control | Reject; A state unchanged | `timeline.test.ts` |
| UI025 | Mutate event external_ticket_id to B after valid A control | Reject; A state unchanged | `timeline.test.ts` |
