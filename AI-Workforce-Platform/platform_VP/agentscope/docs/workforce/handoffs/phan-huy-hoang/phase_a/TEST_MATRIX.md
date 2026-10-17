# Phase A negative test matrix

Each row runs independently against the named real model. Expected: validation rejects the input.
JSON Schema checks structure separately; cross-field invariants require Pydantic validation.

| ID | Model | Mutation | Expected |
|---|---|---|---|
| PHA-001 | WorkflowTrigger | Remove trigger_id | ValidationError |
| PHA-002 | WorkflowTrigger | Remove workflow_id | ValidationError |
| PHA-003 | WorkflowTrigger | Remove cause | ValidationError |
| PHA-004 | WorkflowCheckpoint | Remove workflow_id | ValidationError |
| PHA-005 | WorkflowCheckpoint | Remove state_revision | ValidationError |
| PHA-006 | WorkflowCheckpoint | Remove session_refs | ValidationError |
| PHA-007 | WorkflowCheckpoint | Remove agent_version_pins | ValidationError |
| PHA-008 | WorkflowCheckpoint | Remove shared_state_ref | ValidationError |
| PHA-009 | WorkflowCheckpoint | Remove used_budget | ValidationError |
| PHA-010 | WorkflowRecord | Remove scope.tenant_id | ValidationError |
| PHA-011 | WorkflowRecord | Remove scope.domain_id | ValidationError |
| PHA-012 | WorkflowRecord | Remove scope.area_id | ValidationError |
| PHA-013 | WorkflowRecord | Remove scope.manager_account_id | ValidationError |
| PHA-014 | WorkflowRecord | Remove group_id | ValidationError |
| PHA-015 | WorkflowRecord | Remove route_id | ValidationError |
| PHA-016 | WorkflowRecord | Remove route_revision | ValidationError |
| PHA-017 | CommandClaimResult | Remove request_id | ValidationError |
| PHA-018 | CommandClaimResult | Remove is_new | ValidationError |
| PHA-019 | CommandClaimResult | Remove status | ValidationError |
| PHA-020 | ConversationEvent | Remove event_id | ValidationError |
| PHA-021 | ConversationEvent | Remove sequence | ValidationError |
| PHA-022 | ConversationEvent | Remove conversation_id | ValidationError |
| PHA-023 | ConversationEvent | Remove external_conversation_id | ValidationError |
| PHA-024 | ConversationEvent | Remove external_user_id | ValidationError |
| PHA-025 | WorkflowTrigger | Set cause.kind = 'provider_instruction' | ValidationError |
| PHA-026 | WorkflowTrigger | Remove cause.request_id | ValidationError |
| PHA-027 | WorkflowTrigger | Request cause also supplies timer identity | ValidationError |
| PHA-028 | WorkflowTrigger | Set cause = {'kind': 'approval', 'request_id': 'approval-request-A'} | ValidationError |
| PHA-029 | WorkflowTrigger | Set cause = {'kind': 'approval', 'approval_id': 'approval-A'} | ValidationError |
| PHA-030 | WorkflowTrigger | Set cause = {'kind': 'external_event', 'cause_event_id': 'inbox-A'} | ValidationError |
| PHA-031 | WorkflowTrigger | Set cause = {'kind': 'external_event', 'operation_id': 'operation-A'} | ValidationError |
| PHA-032 | WorkflowTrigger | Set cause = {'kind': 'timer', 'timer_id': ''} | ValidationError |
| PHA-033 | WorkflowTrigger | Inject scope into queued trigger | ValidationError |
| PHA-034 | WorkflowTrigger | Inject group_id into queued trigger | ValidationError |
| PHA-035 | WorkflowTrigger | Inject actor into queued trigger | ValidationError |
| PHA-036 | WorkflowTrigger | Inject credential into queued trigger | ValidationError |
| PHA-037 | WorkflowTrigger | Inject callback_url into queued trigger | ValidationError |
| PHA-038 | WorkflowTrigger | Set expected_state_revision = 0 | ValidationError |
| PHA-039 | WorkflowTrigger | Set expected_state_revision = -1 | ValidationError |
| PHA-040 | WorkflowTrigger | Set expected_state_revision = True | ValidationError |
| PHA-041 | WorkflowTrigger | Set expected_state_revision = '1' | ValidationError |
| PHA-042 | WorkflowCheckpoint | Set schema_version = 'production-v1' | ValidationError |
| PHA-043 | WorkflowCheckpoint | Set session_refs = [] | ValidationError |
| PHA-044 | WorkflowCheckpoint | Set agent_version_pins = [] | ValidationError |
| PHA-045 | WorkflowCheckpoint | Set agent_version_pins.0.version_id = '' | ValidationError |
| PHA-046 | WorkflowCheckpoint | Set protocol_pins.0.schema_hash = '' | ValidationError |
| PHA-047 | WorkflowCheckpoint | Duplicate session_refs | ValidationError |
| PHA-048 | WorkflowCheckpoint | Duplicate pending_task_ids | ValidationError |
| PHA-049 | WorkflowCheckpoint | Duplicate pending_question_ids | ValidationError |
| PHA-050 | WorkflowCheckpoint | Duplicate pending_approval_ids | ValidationError |
| PHA-051 | WorkflowCheckpoint | Duplicate operation_refs | ValidationError |
| PHA-052 | WorkflowCheckpoint | Same agent pinned to two versions | ValidationError |
| PHA-053 | WorkflowCheckpoint | Duplicate processed timer cause | ValidationError |
| PHA-054 | WorkflowCheckpoint | Set used_budget.model_turns = -1 | ValidationError |
| PHA-055 | WorkflowCheckpoint | Set used_budget.tool_calls = -1 | ValidationError |
| PHA-056 | WorkflowCheckpoint | Set used_budget.input_tokens = -1 | ValidationError |
| PHA-057 | WorkflowCheckpoint | Set used_budget.output_tokens = -1 | ValidationError |
| PHA-058 | WorkflowCheckpoint | Set used_budget.tool_calls = True | ValidationError |
| PHA-059 | WorkflowCheckpoint | Set used_budget.input_tokens = 1.5 | ValidationError |
| PHA-060 | CommandClaimResult | New claim incorrectly reports completed result | ValidationError |
| PHA-061 | CommandClaimResult | Set is_new = 'false' | ValidationError |
| PHA-062 | CommandClaimResult | Completed command has no stored result | ValidationError |
| PHA-063 | CommandClaimResult | Running command incorrectly has completed result | ValidationError |
| PHA-064 | PinnedRuntimeContext | Set checkpoint.workflow_id = 'workflow-B' | ValidationError |
| PHA-065 | PinnedRuntimeContext | Set checkpoint.state_revision = 2 | ValidationError |
| PHA-066 | PinnedRuntimeContext | Set checkpoint.agent_version_pins.0.version_id = 'unpublished-v2' | ValidationError |
| PHA-067 | RuntimeTurnResult | Candidate keeps old revision | ValidationError |
| PHA-068 | RuntimeTurnResult | Candidate skips a revision | ValidationError |
| PHA-069 | RuntimeTurnResult | Set result.messages.0.workflow_id = 'workflow-B' | ValidationError |
| PHA-070 | ConversationEvent | Set sequence = 0 | ValidationError |
| PHA-071 | ConversationEvent | Set schema_version = '2' | ValidationError |
| PHA-072 | ConversationEvent | Set scope = {'tenant_id': 'secret'} | ValidationError |
| PHA-073 | ConversationEvent | Set group_id = 'internal-group' | ValidationError |
| PHA-074 | WorkflowRecord | Provider status must not become core workflow state | ValidationError |
| PHA-075 | PartnerRequestEnvelope | Start command supplies existing workflow ID | ValidationError |
| PHA-076 | PartnerRequestEnvelope | Reply lacks workflow ID | ValidationError |
| PHA-077 | PartnerRequestEnvelope | Set scope = {'tenant_id': 'attacker'} | ValidationError |
| PHA-078 | InboundReceipt | Closed workflow still requests reply | ValidationError |
| PHA-079 | InboundReceipt | Completed request incorrectly waits for itself | ValidationError |
| PHA-080 | CloseWorkflowCommand | Set expected_revision = 0 | ValidationError |
