# ERD quan hệ toàn dự án

Tất cả bảng và FK thực tế; chia sơ đồ chi tiết theo module tại [catalog](README.md). Cạnh này là FK, không phải luồng gọi API. Tham chiếu mềm domain/runtime được giải thích tại [system flow](../02_BUSINESS_ANALYSIS_IMPLEMENTATION.md).

## authorization

Fields and constraints: [authorization](authorization.md).

```mermaid
erDiagram
  auth_external_identity
  platform_tenant ||--o{ auth_external_identity : "ownership"
  users ||--o{ auth_external_identity : "local_user_id"
  auth_permission
  auth_role
  platform_tenant |o--o{ auth_role : "ownership"
  auth_role_assignment
  platform_tenant ||--o{ auth_role_assignment : "ownership"
  auth_role ||--o{ auth_role_assignment : "role_id"
  platform_tenant_membership ||--o{ auth_role_assignment : "user_id"
  auth_role_permission
  auth_role ||--o{ auth_role_permission : "role_id"
  auth_permission ||--o{ auth_role_permission : "permission_id"
```

## foundation-core

Fields and constraints: [foundation-core](foundation-core.md).

```mermaid
erDiagram
  accounts
  users ||--o{ accounts : "user_id"
  agents
  platform_tenant ||--o{ agents : "ownership"
  deployment_packages |o--o{ agents : "package_id"
  attachments
  platform_tenant ||--o{ attachments : "ownership"
  channels ||--o{ attachments : "channel_id"
  users ||--o{ attachments : "uploaded_by"
  channels ||--o{ attachments : "channel_id"
  audit_events
  platform_tenant ||--o{ audit_events : "ownership"
  channel_agents
  platform_tenant ||--o{ channel_agents : "ownership"
  channels ||--o{ channel_agents : "channel_id"
  agents ||--o{ channel_agents : "agent_id"
  channels ||--o{ channel_agents : "channel_id"
  agents ||--o{ channel_agents : "agent_id"
  channel_memberships
  platform_tenant ||--o{ channel_memberships : "ownership"
  channels ||--o{ channel_memberships : "channel_id"
  users ||--o{ channel_memberships : "user_id"
  channels ||--o{ channel_memberships : "channel_id"
  platform_tenant_membership ||--o{ channel_memberships : "user_id"
  channels
  users |o--o{ channels : "created_by_user_id"
  platform_tenant ||--o{ channels : "ownership"
  deployment_packages |o--o{ channels : "package_id"
  agents |o--o{ channels : "last_message_agent_id"
  agents |o--o{ channels : "last_message_agent_id"
  credentials
  platform_tenant ||--o{ credentials : "ownership"
  deployment_packages
  intelligence_channel_mappings
  platform_tenant ||--o{ intelligence_channel_mappings : "ownership"
  users ||--o{ intelligence_channel_mappings : "user_id"
  channels ||--o{ intelligence_channel_mappings : "channel_id"
  channels ||--o{ intelligence_channel_mappings : "channel_id"
  revoked_access
  sessions
  users ||--o{ sessions : "user_id"
  sso_providers
  users |o--o{ sso_providers : "user_id"
  user_instructions
  users ||--o| user_instructions : "user_id"
  user_roles
  users ||--o{ user_roles : "user_id"
  users
  verifications
```

## foundation-computer

Fields and constraints: [foundation-computer](foundation-computer.md).

```mermaid
erDiagram
  action_policy
  computer_page_frame
  computer_snapshot
```

## foundation-coworker

Fields and constraints: [foundation-coworker](foundation-coworker.md).

```mermaid
erDiagram
  agent_preferences
  platform_tenant ||--o{ agent_preferences : "ownership"
  users ||--o{ agent_preferences : "user_id"
  agents ||--o{ agent_preferences : "agent_id"
  agents ||--o{ agent_preferences : "agent_id"
  agent_profiles
  platform_tenant ||--o{ agent_profiles : "ownership"
  agents ||--o| agent_profiles : "agent_id"
  users |o--o{ agent_profiles : "owner_user_id"
  agents ||--o| agent_profiles : "agent_id"
  routine_runs
  platform_tenant ||--o{ routine_runs : "ownership"
  routines ||--o{ routine_runs : "routine_id"
  routines ||--o{ routine_runs : "routine_id"
  routine_sweeps
  routines
  platform_tenant ||--o{ routines : "ownership"
  users ||--o{ routines : "owner_user_id"
  agents ||--o{ routines : "agent_id"
  agents ||--o{ routines : "agent_id"
```

## foundation-components

Fields and constraints: [foundation-components](foundation-components.md).

```mermaid
erDiagram
  component_exclusions
  components ||--o{ component_exclusions : "component_name"
  agents ||--o{ component_exclusions : "agent_id"
  component_functions
  components ||--o{ component_functions : "component_name"
  components
```

## foundation-plugins

Fields and constraints: [foundation-plugins](foundation-plugins.md).

```mermaid
erDiagram
  composio_connections
  platform_tenant ||--o{ composio_connections : "ownership"
  mcp_servers
  platform_tenant ||--o{ mcp_servers : "ownership"
  credentials |o--o{ mcp_servers : "credential_id"
  credentials |o--o{ mcp_servers : "credential_id"
  mcp_tools
  platform_tenant ||--o{ mcp_tools : "ownership"
  mcp_servers ||--o{ mcp_tools : "server_id"
  mcp_servers ||--o{ mcp_tools : "server_id"
  mcp_user_credentials
  platform_tenant ||--o{ mcp_user_credentials : "ownership"
  mcp_servers ||--o{ mcp_user_credentials : "server_id"
  users ||--o{ mcp_user_credentials : "user_id"
  credentials ||--o{ mcp_user_credentials : "credential_id"
  mcp_servers ||--o{ mcp_user_credentials : "server_id"
  credentials ||--o{ mcp_user_credentials : "credential_id"
  plugin_grants
  platform_tenant ||--o{ plugin_grants : "ownership"
  agents ||--o{ plugin_grants : "agent_id"
  agents ||--o{ plugin_grants : "agent_id"
  sandboxed_components
  platform_tenant ||--o{ sandboxed_components : "ownership"
  skill_tools
  platform_tenant ||--o{ skill_tools : "ownership"
  skills ||--o{ skill_tools : "skill_id"
  skills ||--o{ skill_tools : "skill_id"
  skills
  platform_tenant ||--o{ skills : "ownership"
  users |o--o{ skills : "owner_user_id"
```

## foundation-work

Fields and constraints: [foundation-work](foundation-work.md).

```mermaid
erDiagram
  work_items
```

## foundation-voice

Fields and constraints: [foundation-voice](foundation-voice.md).

```mermaid
erDiagram
  voice_sessions
  platform_tenant ||--o{ voice_sessions : "ownership"
  channels ||--o{ voice_sessions : "channel_id"
  users ||--o{ voice_sessions : "user_id"
  channels ||--o{ voice_sessions : "channel_id"
```

## platform-identity

Fields and constraints: [platform-identity](platform-identity.md).

```mermaid
erDiagram
  platform_tenant
  platform_tenant_membership
  platform_tenant ||--o{ platform_tenant_membership : "ownership"
  users ||--o{ platform_tenant_membership : "user_id"
```

## platform-domains

Fields and constraints: [platform-domains](platform-domains.md).

```mermaid
erDiagram
  platform_domain_installation
  platform_tenant ||--o{ platform_domain_installation : "ownership"
  platform_domain_package ||--o{ platform_domain_installation : "domain_package_id"
  platform_domain_package
```

## platform-agents

Fields and constraints: [platform-agents](platform-agents.md).

```mermaid
erDiagram
  platform_agent_change_request
  platform_tenant ||--o{ platform_agent_change_request : "ownership"
  agents ||--o{ platform_agent_change_request : "agent_id"
  users ||--o{ platform_agent_change_request : "requested_by"
  platform_agent_spec
  platform_tenant ||--o{ platform_agent_spec : "ownership"
  platform_agent_version ||--o| platform_agent_spec : "agent_version_id"
  platform_agent_version
  platform_tenant ||--o{ platform_agent_version : "ownership"
  agents ||--o{ platform_agent_version : "agent_id"
  users ||--o{ platform_agent_version : "created_by"
```

## platform-capabilities

Fields and constraints: [platform-capabilities](platform-capabilities.md).

```mermaid
erDiagram
  platform_capability
  platform_tenant ||--o{ platform_capability : "ownership"
  users ||--o{ platform_capability : "owner_id"
  platform_mcp_server_version
  platform_tenant ||--o{ platform_mcp_server_version : "ownership"
  mcp_servers ||--o{ platform_mcp_server_version : "mcp_server_id"
  platform_model_profile
  platform_tenant ||--o{ platform_model_profile : "ownership"
  platform_skill_version
  platform_tenant ||--o{ platform_skill_version : "ownership"
  skills ||--o{ platform_skill_version : "skill_id"
  platform_tool
  mcp_servers |o--o{ platform_tool : "mcp_server_id"
  platform_tenant ||--o{ platform_tool : "ownership"
  platform_tool_version
  platform_tenant ||--o{ platform_tool_version : "ownership"
  platform_tool ||--o{ platform_tool_version : "tool_id"
  platform_mcp_server_version |o--o{ platform_tool_version : "mcp_server_version_id"
```

## platform-bindings

Fields and constraints: [platform-bindings](platform-bindings.md).

```mermaid
erDiagram
  platform_agent_capability_binding
  platform_tenant ||--o{ platform_agent_capability_binding : "ownership"
  platform_agent_version ||--o{ platform_agent_capability_binding : "agent_version_id"
  platform_capability ||--o{ platform_agent_capability_binding : "capability_id"
  platform_agent_knowledge_binding
  platform_tenant ||--o{ platform_agent_knowledge_binding : "ownership"
  platform_agent_version ||--o{ platform_agent_knowledge_binding : "agent_version_id"
  platform_knowledge_base ||--o{ platform_agent_knowledge_binding : "knowledge_base_id"
  platform_agent_model_binding
  platform_tenant ||--o{ platform_agent_model_binding : "ownership"
  platform_agent_version ||--o| platform_agent_model_binding : "agent_version_id"
  platform_model_profile ||--o{ platform_agent_model_binding : "model_profile_id"
  platform_agent_policy_binding
  platform_tenant ||--o{ platform_agent_policy_binding : "ownership"
  platform_agent_version ||--o{ platform_agent_policy_binding : "agent_version_id"
  platform_policy_version ||--o{ platform_agent_policy_binding : "policy_version_id"
  platform_agent_skill_binding
  platform_tenant ||--o{ platform_agent_skill_binding : "ownership"
  platform_agent_version ||--o{ platform_agent_skill_binding : "agent_version_id"
  platform_skill_version ||--o{ platform_agent_skill_binding : "skill_version_id"
  platform_agent_tool_binding
  platform_tenant ||--o{ platform_agent_tool_binding : "ownership"
  platform_agent_version ||--o{ platform_agent_tool_binding : "agent_version_id"
  platform_tool_version ||--o{ platform_agent_tool_binding : "tool_version_id"
```

## platform-knowledge

Fields and constraints: [platform-knowledge](platform-knowledge.md).

```mermaid
erDiagram
  platform_knowledge_base
  platform_tenant ||--o{ platform_knowledge_base : "ownership"
  users ||--o{ platform_knowledge_base : "owner_id"
  platform_knowledge_revision
  platform_tenant ||--o{ platform_knowledge_revision : "ownership"
  platform_knowledge_source ||--o{ platform_knowledge_revision : "knowledge_source_id"
  users |o--o{ platform_knowledge_revision : "approved_by"
  platform_knowledge_source
  platform_tenant ||--o{ platform_knowledge_source : "ownership"
  platform_knowledge_base ||--o{ platform_knowledge_source : "knowledge_base_id"
  users ||--o{ platform_knowledge_source : "owner_id"
```

## platform-policies

Fields and constraints: [platform-policies](platform-policies.md).

```mermaid
erDiagram
  platform_policy
  platform_tenant ||--o{ platform_policy : "ownership"
  users ||--o{ platform_policy : "owner_id"
  platform_policy_version
  platform_tenant ||--o{ platform_policy_version : "ownership"
  platform_policy ||--o{ platform_policy_version : "policy_id"
```

## platform-evaluation

Fields and constraints: [platform-evaluation](platform-evaluation.md).

```mermaid
erDiagram
  platform_eval_assertion
  platform_tenant ||--o{ platform_eval_assertion : "ownership"
  platform_eval_run ||--o{ platform_eval_assertion : "eval_run_id"
  platform_eval_case ||--o{ platform_eval_assertion : "eval_case_id"
  platform_eval_case
  platform_tenant ||--o{ platform_eval_case : "ownership"
  platform_eval_suite ||--o{ platform_eval_case : "eval_suite_id"
  platform_eval_evidence
  platform_tenant ||--o{ platform_eval_evidence : "ownership"
  platform_eval_run ||--o{ platform_eval_evidence : "eval_run_id"
  platform_eval_assertion |o--o{ platform_eval_evidence : "eval_run_id + eval_assertion_id"
  platform_eval_run
  platform_tenant ||--o{ platform_eval_run : "ownership"
  platform_agent_version ||--o{ platform_eval_run : "agent_version_id"
  platform_eval_suite ||--o{ platform_eval_run : "eval_suite_id"
  platform_eval_suite
  platform_tenant ||--o{ platform_eval_suite : "ownership"
  users ||--o{ platform_eval_suite : "owner_id"
  platform_publish_approval
  platform_tenant ||--o{ platform_publish_approval : "ownership"
  platform_publish_gate ||--o{ platform_publish_approval : "publish_gate_id"
  users ||--o{ platform_publish_approval : "reviewer_id"
  platform_publish_gate
  platform_tenant ||--o{ platform_publish_gate : "ownership"
  platform_agent_version ||--o{ platform_publish_gate : "agent_version_id"
  platform_publish_gate_result
  platform_tenant ||--o{ platform_publish_gate_result : "ownership"
  platform_publish_gate ||--o{ platform_publish_gate_result : "publish_gate_id"
  platform_regression_baseline
  platform_tenant ||--o{ platform_regression_baseline : "ownership"
  agents ||--o{ platform_regression_baseline : "agent_id"
  platform_agent_version ||--o{ platform_regression_baseline : "agent_id + baseline_agent_version_id"
  platform_eval_suite ||--o{ platform_regression_baseline : "eval_suite_id"
  users ||--o{ platform_regression_baseline : "accepted_by"
  platform_agent_version ||--o{ platform_regression_baseline : "agent_id + baseline_agent_version_id"
```

## platform-deployments

Fields and constraints: [platform-deployments](platform-deployments.md).

```mermaid
erDiagram
  platform_agent_deployment
  platform_tenant ||--o{ platform_agent_deployment : "ownership"
  platform_agent_version ||--o{ platform_agent_deployment : "agent_version_id"
  platform_domain_installation |o--o{ platform_agent_deployment : "domain_installation_id"
  platform_agent_deployment |o--o{ platform_agent_deployment : "previous_deployment_id"
```

## platform-runtime

Fields and constraints: [platform-runtime](platform-runtime.md).

```mermaid
erDiagram
  platform_action_proposal
  platform_tenant ||--o{ platform_action_proposal : "ownership"
  platform_runtime_decision ||--o{ platform_action_proposal : "workflow_session_id + runtime_decision_id"
  platform_workflow_session ||--o{ platform_action_proposal : "workflow_session_id"
  platform_agent_run |o--o{ platform_action_proposal : "workflow_session_id + producer_agent_run_id"
  platform_agent_run
  platform_tenant ||--o{ platform_agent_run : "ownership"
  platform_workflow_session ||--o{ platform_agent_run : "workflow_session_id"
  platform_run_step ||--o{ platform_agent_run : "workflow_session_id + run_step_id"
  agents ||--o{ platform_agent_run : "agent_id"
  platform_agent_version ||--o{ platform_agent_run : "agent_id + agent_version_id"
  platform_execution_grant_ref
  platform_tenant ||--o{ platform_execution_grant_ref : "ownership"
  platform_action_proposal ||--o{ platform_execution_grant_ref : "action_proposal_id"
  platform_run_step
  platform_tenant ||--o{ platform_run_step : "ownership"
  platform_workflow_session ||--o{ platform_run_step : "workflow_session_id"
  platform_run_step_dependency
  platform_tenant ||--o{ platform_run_step_dependency : "ownership"
  platform_workflow_session ||--o{ platform_run_step_dependency : "workflow_session_id"
  platform_run_step ||--o{ platform_run_step_dependency : "workflow_session_id + run_step_id"
  platform_run_step ||--o{ platform_run_step_dependency : "workflow_session_id + depends_on_run_step_id"
  platform_runtime_artifact
  platform_tenant ||--o{ platform_runtime_artifact : "ownership"
  platform_agent_run ||--o{ platform_runtime_artifact : "agent_run_id"
  platform_runtime_decision
  platform_tenant ||--o{ platform_runtime_decision : "ownership"
  platform_workflow_session ||--o{ platform_runtime_decision : "workflow_session_id"
  platform_agent_run |o--o{ platform_runtime_decision : "workflow_session_id + created_by_run_id"
  platform_tool_call
  platform_tenant ||--o{ platform_tool_call : "ownership"
  platform_agent_run ||--o{ platform_tool_call : "agent_run_id"
  platform_tool_version ||--o{ platform_tool_call : "tool_version_id"
  platform_workflow_session
  platform_tenant ||--o{ platform_workflow_session : "ownership"
```

## platform-memory

Fields and constraints: [platform-memory](platform-memory.md).

```mermaid
erDiagram
  platform_memory_item
  platform_tenant ||--o{ platform_memory_item : "ownership"
  platform_memory_namespace ||--o{ platform_memory_item : "memory_namespace_id"
  platform_memory_namespace
  platform_tenant ||--o{ platform_memory_namespace : "ownership"
  platform_memory_review
  platform_tenant ||--o{ platform_memory_review : "ownership"
  platform_memory_revision ||--o{ platform_memory_review : "memory_revision_id"
  users ||--o{ platform_memory_review : "reviewer_id"
  platform_memory_revision
  platform_tenant ||--o{ platform_memory_revision : "ownership"
  platform_memory_item ||--o{ platform_memory_revision : "memory_item_id"
  platform_memory_vector_ref
  platform_tenant ||--o{ platform_memory_vector_ref : "ownership"
  platform_memory_revision ||--o| platform_memory_vector_ref : "memory_revision_id"
```

## platform-audit

Fields and constraints: [platform-audit](platform-audit.md).

```mermaid
erDiagram
  platform_audit_event
  platform_tenant ||--o{ platform_audit_event : "ownership"
  platform_idempotency_record
  platform_tenant ||--o{ platform_idempotency_record : "ownership"
  platform_outbox_event
  platform_tenant ||--o{ platform_outbox_event : "ownership"
```

## vinhomes-property

Fields and constraints: [vinhomes-property](vinhomes-property.md).

```mermaid
erDiagram
  vh_apartment
  platform_tenant ||--o{ vh_apartment : "ownership"
  vh_project ||--o{ vh_apartment : "ownership"
  vh_tower ||--o{ vh_apartment : "tower_id"
  vh_membership_application
  platform_tenant ||--o{ vh_membership_application : "ownership"
  vh_project ||--o{ vh_membership_application : "ownership"
  vh_apartment ||--o{ vh_membership_application : "requested_apartment_id"
  users ||--o{ vh_membership_application : "applicant_user_id"
  users |o--o{ vh_membership_application : "reviewed_by"
  vh_project
  platform_tenant ||--o{ vh_project : "ownership"
  vh_property_membership
  platform_tenant ||--o{ vh_property_membership : "ownership"
  vh_project ||--o{ vh_property_membership : "ownership"
  users ||--o{ vh_property_membership : "user_id"
  vh_tower |o--o{ vh_property_membership : "tower_id"
  vh_apartment |o--o{ vh_property_membership : "tower_id + apartment_id"
  users ||--o{ vh_property_membership : "granted_by_user_id"
  platform_tenant_membership ||--o{ vh_property_membership : "user_id"
  vh_tower
  platform_tenant ||--o{ vh_tower : "ownership"
  vh_project ||--o{ vh_tower : "ownership"
```

## vinhomes-intake

Fields and constraints: [vinhomes-intake](vinhomes-intake.md).

```mermaid
erDiagram
  vh_case
  platform_tenant ||--o{ vh_case : "ownership"
  vh_project ||--o{ vh_case : "ownership"
  users ||--o{ vh_case : "resident_user_id"
  vh_apartment |o--o{ vh_case : "apartment_id"
  vh_property_membership ||--o{ vh_case : "opened_by_membership_id"
  vh_property_membership ||--o{ vh_case : "resident_user_id + opened_by_membership_id"
  vh_property_membership |o--o{ vh_case : "apartment_id + opened_by_membership_id"
  vh_feedback
  platform_tenant ||--o{ vh_feedback : "ownership"
  vh_project ||--o{ vh_feedback : "ownership"
  vh_resident_report ||--o{ vh_feedback : "report_id"
  users ||--o{ vh_feedback : "author_user_id"
  vh_resident_report ||--o| vh_feedback : "author_user_id + report_id"
  vh_resident_confirmation
  platform_tenant ||--o{ vh_resident_confirmation : "ownership"
  vh_project ||--o{ vh_resident_confirmation : "ownership"
  vh_resident_report ||--o{ vh_resident_confirmation : "report_id"
  vh_incident ||--o{ vh_resident_confirmation : "incident_id"
  users ||--o{ vh_resident_confirmation : "confirmed_by_user_id"
  vh_resident_report ||--o{ vh_resident_confirmation : "incident_id + confirmed_by_user_id + report_id"
  vh_resident_report
  platform_tenant ||--o{ vh_resident_report : "ownership"
  vh_project ||--o{ vh_resident_report : "ownership"
  vh_case ||--o{ vh_resident_report : "case_id"
  vh_incident |o--o{ vh_resident_report : "incident_id"
  users ||--o{ vh_resident_report : "reporter_id"
  vh_property_membership ||--o{ vh_resident_report : "reporter_membership_id"
  vh_apartment |o--o{ vh_resident_report : "apartment_id"
  vh_property_membership ||--o{ vh_resident_report : "reporter_id + reporter_membership_id"
  vh_property_membership |o--o{ vh_resident_report : "apartment_id + reporter_membership_id"
  vh_resident_request
  platform_tenant ||--o{ vh_resident_request : "ownership"
  vh_project ||--o{ vh_resident_request : "ownership"
  vh_case ||--o{ vh_resident_request : "case_id"
  users ||--o{ vh_resident_request : "submitted_by"
```

## vinhomes-operations

Fields and constraints: [vinhomes-operations](vinhomes-operations.md).

```mermaid
erDiagram
  vh_action_approval
  platform_tenant ||--o{ vh_action_approval : "ownership"
  vh_project ||--o{ vh_action_approval : "ownership"
  vh_action_request ||--o{ vh_action_approval : "action_request_id"
  users |o--o{ vh_action_approval : "reviewer_id"
  vh_action_request ||--o{ vh_action_approval : "action_request_id + action_payload_hash"
  vh_action_request ||--o{ vh_action_approval : "action_request_id + policy_version"
  vh_action_request
  platform_tenant ||--o{ vh_action_request : "ownership"
  vh_project ||--o{ vh_action_request : "ownership"
  vh_incident ||--o{ vh_action_request : "incident_id"
  vh_task ||--o{ vh_action_request : "incident_id + task_id"
  vh_checklist
  platform_tenant ||--o{ vh_checklist : "ownership"
  vh_checklist_version
  platform_tenant ||--o{ vh_checklist_version : "ownership"
  vh_checklist ||--o{ vh_checklist_version : "checklist_id"
  users ||--o{ vh_checklist_version : "created_by"
  vh_execution_grant
  platform_tenant ||--o{ vh_execution_grant : "ownership"
  vh_project ||--o{ vh_execution_grant : "ownership"
  vh_action_request ||--o{ vh_execution_grant : "action_request_id"
  vh_action_request ||--o{ vh_execution_grant : "action_request_id + action_payload_hash"
  vh_action_request ||--o{ vh_execution_grant : "action_request_id + policy_version"
  vh_incident
  platform_tenant ||--o{ vh_incident : "ownership"
  vh_project ||--o{ vh_incident : "ownership"
  vh_tower |o--o{ vh_incident : "tower_id"
  users |o--o{ vh_incident : "owner_user_id"
  users |o--o{ vh_incident : "closed_by_user_id"
  vh_incident_relation
  platform_tenant ||--o{ vh_incident_relation : "ownership"
  vh_project ||--o{ vh_incident_relation : "ownership"
  vh_incident ||--o{ vh_incident_relation : "source_incident_id"
  vh_incident ||--o{ vh_incident_relation : "target_incident_id"
  users ||--o{ vh_incident_relation : "created_by"
  vh_rule_evaluation
  platform_tenant ||--o{ vh_rule_evaluation : "ownership"
  vh_project ||--o{ vh_rule_evaluation : "ownership"
  vh_action_request ||--o{ vh_rule_evaluation : "action_request_id"
  vh_action_request ||--o{ vh_rule_evaluation : "action_request_id + action_payload_hash"
  vh_task
  platform_tenant ||--o{ vh_task : "ownership"
  vh_project ||--o{ vh_task : "ownership"
  vh_incident ||--o{ vh_task : "incident_id"
  vh_work_order
  platform_tenant ||--o{ vh_work_order : "ownership"
  vh_project ||--o{ vh_work_order : "ownership"
  vh_incident ||--o{ vh_work_order : "incident_id"
  vh_task ||--o{ vh_work_order : "incident_id + task_id"
  vh_action_request ||--o{ vh_work_order : "incident_id + task_id + action_request_id"
  vh_work_order |o--o{ vh_work_order : "incident_id + task_id + redo_of_work_order_id"
  vh_checklist_version |o--o{ vh_work_order : "checklist_version_id"
```

## vinhomes-files

Fields and constraints: [vinhomes-files](vinhomes-files.md).

```mermaid
erDiagram
  vh_file_object
  platform_tenant ||--o{ vh_file_object : "ownership"
  users ||--o{ vh_file_object : "uploaded_by_user_id"
```

## vinhomes-evidence

Fields and constraints: [vinhomes-evidence](vinhomes-evidence.md).

```mermaid
erDiagram
  vh_evidence_ref
  platform_tenant ||--o{ vh_evidence_ref : "ownership"
  vh_project ||--o{ vh_evidence_ref : "ownership"
  vh_incident ||--o{ vh_evidence_ref : "incident_id"
  vh_task |o--o{ vh_evidence_ref : "incident_id + task_id"
  vh_work_order |o--o{ vh_evidence_ref : "incident_id + task_id + work_order_id"
  vh_file_object ||--o{ vh_evidence_ref : "file_id"
  users ||--o{ vh_evidence_ref : "uploaded_by"
  vh_qc_result
  platform_tenant ||--o{ vh_qc_result : "ownership"
  vh_project ||--o{ vh_qc_result : "ownership"
  vh_incident ||--o{ vh_qc_result : "incident_id"
  vh_task ||--o{ vh_qc_result : "incident_id + task_id"
  vh_work_order ||--o{ vh_qc_result : "incident_id + task_id + work_order_id"
  users ||--o{ vh_qc_result : "checked_by"
  vh_qc_result_evidence
  platform_tenant ||--o{ vh_qc_result_evidence : "ownership"
  vh_project ||--o{ vh_qc_result_evidence : "ownership"
  vh_incident ||--o{ vh_qc_result_evidence : "incident_id"
  vh_qc_result ||--o{ vh_qc_result_evidence : "incident_id + qc_result_id"
  vh_evidence_ref ||--o{ vh_qc_result_evidence : "incident_id + evidence_ref_id"
  vh_root_cause_evidence
  platform_tenant ||--o{ vh_root_cause_evidence : "ownership"
  vh_project ||--o{ vh_root_cause_evidence : "ownership"
  vh_root_cause_finding ||--o{ vh_root_cause_evidence : "root_cause_finding_id"
  vh_evidence_ref ||--o{ vh_root_cause_evidence : "evidence_ref_id"
  vh_root_cause_finding
  platform_tenant ||--o{ vh_root_cause_finding : "ownership"
  vh_project ||--o{ vh_root_cause_finding : "ownership"
  vh_incident ||--o{ vh_root_cause_finding : "incident_id"
  vh_root_cause_incident
  platform_tenant ||--o{ vh_root_cause_incident : "ownership"
  vh_project ||--o{ vh_root_cause_incident : "ownership"
  vh_root_cause_finding ||--o{ vh_root_cause_incident : "root_cause_finding_id"
  vh_incident ||--o{ vh_root_cause_incident : "related_incident_id"
```

## vinhomes-attachments

Fields and constraints: [vinhomes-attachments](vinhomes-attachments.md).

```mermaid
erDiagram
  vh_membership_application_file
  platform_tenant ||--o{ vh_membership_application_file : "ownership"
  vh_project ||--o{ vh_membership_application_file : "ownership"
  vh_membership_application ||--o{ vh_membership_application_file : "application_id"
  vh_file_object ||--o{ vh_membership_application_file : "file_id"
  vh_pet_document
  platform_tenant ||--o{ vh_pet_document : "ownership"
  vh_project ||--o{ vh_pet_document : "ownership"
  vh_pet_profile ||--o{ vh_pet_document : "pet_id"
  vh_file_object ||--o{ vh_pet_document : "file_id"
  vh_report_attachment
  platform_tenant ||--o{ vh_report_attachment : "ownership"
  vh_project ||--o{ vh_report_attachment : "ownership"
  vh_resident_report ||--o{ vh_report_attachment : "report_id"
  vh_file_object ||--o{ vh_report_attachment : "file_id"
  vh_request_attachment
  platform_tenant ||--o{ vh_request_attachment : "ownership"
  vh_project ||--o{ vh_request_attachment : "ownership"
  vh_resident_request ||--o{ vh_request_attachment : "request_id"
  vh_file_object ||--o{ vh_request_attachment : "file_id"
  vh_service_request_file
  platform_tenant ||--o{ vh_service_request_file : "ownership"
  vh_project ||--o{ vh_service_request_file : "ownership"
  vh_service_request ||--o{ vh_service_request_file : "request_id"
  vh_file_object ||--o{ vh_service_request_file : "file_id"
```

## vinhomes-communication

Fields and constraints: [vinhomes-communication](vinhomes-communication.md).

```mermaid
erDiagram
  vh_business_event
  platform_tenant ||--o{ vh_business_event : "ownership"
  vh_project ||--o{ vh_business_event : "ownership"
  vh_incident |o--o{ vh_business_event : "incident_id"
  vh_message
  platform_tenant ||--o{ vh_message : "ownership"
  vh_project ||--o{ vh_message : "ownership"
  vh_incident ||--o{ vh_message : "incident_id"
  vh_resident_report |o--o{ vh_message : "resident_report_id"
  vh_resident_report |o--o{ vh_message : "incident_id + resident_report_id"
  vh_notification
  platform_tenant ||--o{ vh_notification : "ownership"
  vh_project ||--o{ vh_notification : "ownership"
  vh_business_event |o--o{ vh_notification : "business_event_id"
  users ||--o{ vh_notification : "recipient_id"
```

## vinhomes-services

Fields and constraints: [vinhomes-services](vinhomes-services.md).

```mermaid
erDiagram
  vh_access_card
  platform_tenant ||--o{ vh_access_card : "ownership"
  vh_project ||--o{ vh_access_card : "ownership"
  vh_property_membership ||--o{ vh_access_card : "membership_id"
  vh_camera_request
  platform_tenant ||--o{ vh_camera_request : "ownership"
  vh_project ||--o{ vh_camera_request : "ownership"
  vh_apartment ||--o{ vh_camera_request : "apartment_id"
  vh_property_membership ||--o{ vh_camera_request : "requester_membership_id"
  vh_map_place ||--o{ vh_camera_request : "location_place_id"
  users |o--o{ vh_camera_request : "reviewed_by"
  vh_property_membership ||--o{ vh_camera_request : "apartment_id + requester_membership_id"
  vh_charging_session
  platform_tenant ||--o{ vh_charging_session : "ownership"
  vh_project ||--o{ vh_charging_session : "ownership"
  vh_apartment ||--o{ vh_charging_session : "apartment_id"
  vh_property_membership ||--o{ vh_charging_session : "requested_by_membership_id"
  vh_map_place ||--o{ vh_charging_session : "station_place_id"
  vh_property_membership ||--o{ vh_charging_session : "apartment_id + requested_by_membership_id"
  vh_construction_permit
  platform_tenant ||--o{ vh_construction_permit : "ownership"
  vh_project ||--o{ vh_construction_permit : "ownership"
  vh_service_request ||--o{ vh_construction_permit : "service_request_id"
  vh_face_enrollment
  platform_tenant ||--o{ vh_face_enrollment : "ownership"
  vh_project ||--o{ vh_face_enrollment : "ownership"
  vh_property_membership ||--o{ vh_face_enrollment : "membership_id"
  vh_handover
  platform_tenant ||--o{ vh_handover : "ownership"
  vh_project ||--o{ vh_handover : "ownership"
  vh_apartment ||--o{ vh_handover : "apartment_id"
  vh_property_membership ||--o{ vh_handover : "resident_membership_id"
  vh_checklist_version |o--o{ vh_handover : "checklist_version_id"
  vh_property_membership ||--o{ vh_handover : "apartment_id + resident_membership_id"
  vh_intercom_event
  platform_tenant ||--o{ vh_intercom_event : "ownership"
  vh_project ||--o{ vh_intercom_event : "ownership"
  vh_apartment ||--o{ vh_intercom_event : "apartment_id"
  vh_visitor_pass |o--o{ vh_intercom_event : "visitor_pass_id"
  vh_parking_permit
  platform_tenant ||--o{ vh_parking_permit : "ownership"
  vh_project ||--o{ vh_parking_permit : "ownership"
  vh_apartment ||--o{ vh_parking_permit : "apartment_id"
  vh_property_membership ||--o{ vh_parking_permit : "membership_id"
  vh_property_membership ||--o{ vh_parking_permit : "apartment_id + membership_id"
  vh_pet_profile
  platform_tenant ||--o{ vh_pet_profile : "ownership"
  vh_project ||--o{ vh_pet_profile : "ownership"
  vh_apartment ||--o{ vh_pet_profile : "apartment_id"
  vh_property_membership ||--o{ vh_pet_profile : "owner_membership_id"
  vh_property_membership ||--o{ vh_pet_profile : "apartment_id + owner_membership_id"
  vh_service_request
  platform_tenant ||--o{ vh_service_request : "ownership"
  vh_project ||--o{ vh_service_request : "ownership"
  vh_apartment ||--o{ vh_service_request : "apartment_id"
  vh_property_membership ||--o{ vh_service_request : "requester_membership_id"
  vh_property_membership ||--o{ vh_service_request : "apartment_id + requester_membership_id"
  vh_visitor_pass
  platform_tenant ||--o{ vh_visitor_pass : "ownership"
  vh_project ||--o{ vh_visitor_pass : "ownership"
  vh_service_request ||--o{ vh_visitor_pass : "service_request_id"
```

## vinhomes-booking

Fields and constraints: [vinhomes-booking](vinhomes-booking.md).

```mermaid
erDiagram
  vh_booking
  platform_tenant ||--o{ vh_booking : "ownership"
  vh_project ||--o{ vh_booking : "ownership"
  vh_time_slot ||--o{ vh_booking : "slot_id"
  vh_apartment ||--o{ vh_booking : "apartment_id"
  vh_property_membership ||--o{ vh_booking : "booked_by_membership_id"
  vh_property_membership ||--o{ vh_booking : "apartment_id + booked_by_membership_id"
  vh_facility
  platform_tenant ||--o{ vh_facility : "ownership"
  vh_project ||--o{ vh_facility : "ownership"
  vh_map_place |o--o{ vh_facility : "place_id"
  vh_time_slot
  platform_tenant ||--o{ vh_time_slot : "ownership"
  vh_project ||--o{ vh_time_slot : "ownership"
  vh_facility ||--o{ vh_time_slot : "facility_id"
```

## vinhomes-billing

Fields and constraints: [vinhomes-billing](vinhomes-billing.md).

```mermaid
erDiagram
  vh_fee_schedule
  platform_tenant ||--o{ vh_fee_schedule : "ownership"
  vh_project ||--o{ vh_fee_schedule : "ownership"
  vh_invoice
  platform_tenant ||--o{ vh_invoice : "ownership"
  vh_project ||--o{ vh_invoice : "ownership"
  vh_apartment ||--o{ vh_invoice : "apartment_id"
  users ||--o{ vh_invoice : "billed_to_user_id"
  vh_invoice_line
  platform_tenant ||--o{ vh_invoice_line : "ownership"
  vh_project ||--o{ vh_invoice_line : "ownership"
  vh_invoice ||--o{ vh_invoice_line : "invoice_id"
  vh_fee_schedule |o--o{ vh_invoice_line : "fee_schedule_id"
  vh_loyalty_balance
  platform_tenant ||--o{ vh_loyalty_balance : "ownership"
  users ||--o{ vh_loyalty_balance : "user_id"
  vh_payment_allocation
  platform_tenant ||--o{ vh_payment_allocation : "ownership"
  vh_project ||--o{ vh_payment_allocation : "ownership"
  vh_payment_attempt ||--o{ vh_payment_allocation : "invoice_id + payment_attempt_id"
  vh_invoice ||--o{ vh_payment_allocation : "invoice_id"
  vh_payment_attempt
  platform_tenant ||--o{ vh_payment_attempt : "ownership"
  vh_project ||--o{ vh_payment_attempt : "ownership"
  vh_invoice ||--o{ vh_payment_attempt : "invoice_id"
  users ||--o{ vh_payment_attempt : "initiated_by_user_id"
```

## vinhomes-content

Fields and constraints: [vinhomes-content](vinhomes-content.md).

```mermaid
erDiagram
  vh_community_event
  platform_tenant ||--o{ vh_community_event : "ownership"
  vh_project ||--o{ vh_community_event : "ownership"
  vh_map_place |o--o{ vh_community_event : "place_id"
  vh_content_item
  platform_tenant ||--o{ vh_content_item : "ownership"
  vh_project ||--o{ vh_content_item : "ownership"
  vh_event_registration
  platform_tenant ||--o{ vh_event_registration : "ownership"
  vh_project ||--o{ vh_event_registration : "ownership"
  vh_community_event ||--o{ vh_event_registration : "event_id"
  vh_property_membership ||--o{ vh_event_registration : "membership_id"
  vh_map_place
  platform_tenant ||--o{ vh_map_place : "ownership"
  vh_project ||--o{ vh_map_place : "ownership"
  vh_tower |o--o{ vh_map_place : "tower_id"
  vh_miniapp_catalog
  platform_tenant ||--o{ vh_miniapp_catalog : "ownership"
  vh_project ||--o{ vh_miniapp_catalog : "ownership"
  vh_offer
  platform_tenant ||--o{ vh_offer : "ownership"
  vh_project ||--o{ vh_offer : "ownership"
  vh_sensor_reading
  platform_tenant ||--o{ vh_sensor_reading : "ownership"
  vh_project ||--o{ vh_sensor_reading : "ownership"
  vh_map_place ||--o{ vh_sensor_reading : "place_id"
  vh_transit_route
  platform_tenant ||--o{ vh_transit_route : "ownership"
  vh_project ||--o{ vh_transit_route : "ownership"
  vh_transit_route_stop
  platform_tenant ||--o{ vh_transit_route_stop : "ownership"
  vh_project ||--o{ vh_transit_route_stop : "ownership"
  vh_transit_route ||--o{ vh_transit_route_stop : "route_id"
  vh_transit_stop ||--o{ vh_transit_route_stop : "stop_id"
  vh_transit_stop
  platform_tenant ||--o{ vh_transit_stop : "ownership"
  vh_project ||--o{ vh_transit_stop : "ownership"
```

## vinhomes-delivery

Fields and constraints: [vinhomes-delivery](vinhomes-delivery.md).

```mermaid
erDiagram
  vh_command_receipt
  platform_tenant ||--o{ vh_command_receipt : "ownership"
  users ||--o{ vh_command_receipt : "actor_user_id"
  vh_outbox
  platform_tenant ||--o{ vh_outbox : "ownership"
  vh_project ||--o{ vh_outbox : "ownership"
  vh_business_event ||--o{ vh_outbox : "business_event_id"
```

## platform-conversations

Fields and constraints: [platform-conversations](platform-conversations.md).

```mermaid
erDiagram
  channel_messages
  agents |o--o{ channel_messages : "author_agent_id"
  platform_agent_version |o--o{ channel_messages : "author_agent_id + agent_version_id"
  platform_tenant ||--o{ channel_messages : "ownership"
  channels ||--o{ channel_messages : "channel_id"
  users |o--o{ channel_messages : "author_user_id"
  platform_agent_version |o--o{ channel_messages : "agent_version_id"
  channel_messages |o--o{ channel_messages : "channel_id + reply_to_message_id"
  channel_subjects
  platform_tenant ||--o{ channel_subjects : "ownership"
  channels ||--o{ channel_subjects : "channel_id"
```

## platform-collaboration

Fields and constraints: [platform-collaboration](platform-collaboration.md).

```mermaid
erDiagram
  platform_handoff
  platform_tenant ||--o{ platform_handoff : "ownership"
  channels |o--o{ platform_handoff : "source_channel_id"
  platform_workflow_session |o--o{ platform_handoff : "source_workflow_session_id"
  platform_agent_version ||--o{ platform_handoff : "target_agent_version_id"
  platform_workflow_session |o--o{ platform_handoff : "target_workflow_session_id"
  platform_runtime_checkpoint
  platform_tenant ||--o{ platform_runtime_checkpoint : "ownership"
  platform_workflow_session ||--o{ platform_runtime_checkpoint : "workflow_session_id"
  platform_agent_run |o--o{ platform_runtime_checkpoint : "workflow_session_id + created_by_run_id"
  platform_runtime_message
  platform_tenant ||--o{ platform_runtime_message : "ownership"
  platform_workflow_session ||--o{ platform_runtime_message : "workflow_session_id"
  platform_session_participant |o--o{ platform_runtime_message : "workflow_session_id + sender_participant_id"
  platform_session_participant |o--o{ platform_runtime_message : "workflow_session_id + recipient_participant_id"
  platform_agent_run |o--o{ platform_runtime_message : "workflow_session_id + agent_run_id"
  platform_runtime_message |o--o{ platform_runtime_message : "workflow_session_id + reply_to_message_id"
  platform_session_control
  platform_tenant ||--o{ platform_session_control : "ownership"
  platform_workflow_session ||--o| platform_session_control : "workflow_session_id"
  platform_workflow_session |o--o{ platform_session_control : "parent_workflow_session_id"
  platform_session_participant |o--o{ platform_session_control : "workflow_session_id + coordinator_participant_id"
  platform_session_participant
  platform_tenant ||--o{ platform_session_participant : "ownership"
  platform_workflow_session ||--o{ platform_session_participant : "workflow_session_id"
  platform_agent_version ||--o{ platform_session_participant : "agent_version_id"
  platform_session_wait
  platform_tenant ||--o{ platform_session_wait : "ownership"
  platform_workflow_session ||--o{ platform_session_wait : "workflow_session_id"
  platform_run_step |o--o{ platform_session_wait : "workflow_session_id + run_step_id"
  platform_session_participant |o--o{ platform_session_wait : "workflow_session_id + participant_id"
```

## platform-event-delivery

Fields and constraints: [platform-event-delivery](platform-event-delivery.md).

```mermaid
erDiagram
  platform_event_receipt
  platform_tenant ||--o{ platform_event_receipt : "ownership"
```

## vinhomes-workforce

Fields and constraints: [vinhomes-workforce](vinhomes-workforce.md).

```mermaid
erDiagram
  vh_staff_shift
  platform_tenant ||--o{ vh_staff_shift : "ownership"
  vh_project ||--o{ vh_staff_shift : "ownership"
  vh_team_member ||--o{ vh_staff_shift : "team_member_id"
  vh_staff_skill
  platform_tenant ||--o{ vh_staff_skill : "ownership"
  vh_project ||--o{ vh_staff_skill : "ownership"
  vh_property_membership ||--o{ vh_staff_skill : "property_membership_id"
  users ||--o{ vh_staff_skill : "verified_by_user_id"
  vh_team
  platform_tenant ||--o{ vh_team : "ownership"
  vh_project ||--o{ vh_team : "ownership"
  vh_team_member
  platform_tenant ||--o{ vh_team_member : "ownership"
  vh_project ||--o{ vh_team_member : "ownership"
  vh_team ||--o{ vh_team_member : "team_id"
  vh_property_membership ||--o{ vh_team_member : "property_membership_id"
```

## vinhomes-assets

Fields and constraints: [vinhomes-assets](vinhomes-assets.md).

```mermaid
erDiagram
  vh_asset
  platform_tenant ||--o{ vh_asset : "ownership"
  vh_project ||--o{ vh_asset : "ownership"
  vh_tower |o--o{ vh_asset : "tower_id"
  vh_apartment |o--o{ vh_asset : "apartment_id"
  vh_incident_asset
  platform_tenant ||--o{ vh_incident_asset : "ownership"
  vh_project ||--o{ vh_incident_asset : "ownership"
  vh_incident ||--o{ vh_incident_asset : "incident_id"
  vh_asset ||--o{ vh_incident_asset : "asset_id"
```

## vinhomes-dispatch

Fields and constraints: [vinhomes-dispatch](vinhomes-dispatch.md).

```mermaid
erDiagram
  vh_work_appointment
  platform_tenant ||--o{ vh_work_appointment : "ownership"
  vh_project ||--o{ vh_work_appointment : "ownership"
  vh_incident ||--o{ vh_work_appointment : "incident_id"
  vh_task ||--o{ vh_work_appointment : "incident_id + task_id"
  vh_work_order ||--o{ vh_work_appointment : "incident_id + task_id + work_order_id"
  vh_resident_report |o--o{ vh_work_appointment : "resident_report_id"
  users ||--o{ vh_work_appointment : "requested_by_user_id"
  users |o--o{ vh_work_appointment : "confirmed_by_user_id"
  vh_work_assignment
  platform_tenant ||--o{ vh_work_assignment : "ownership"
  vh_project ||--o{ vh_work_assignment : "ownership"
  vh_incident ||--o{ vh_work_assignment : "incident_id"
  vh_task ||--o{ vh_work_assignment : "incident_id + task_id"
  vh_work_order ||--o{ vh_work_assignment : "incident_id + task_id + work_order_id"
  vh_team ||--o{ vh_work_assignment : "team_id"
  vh_team_member |o--o{ vh_work_assignment : "team_id + team_member_id"
  users ||--o{ vh_work_assignment : "assigned_by_user_id"
  vh_work_progress
  platform_tenant ||--o{ vh_work_progress : "ownership"
  vh_project ||--o{ vh_work_progress : "ownership"
  vh_incident ||--o{ vh_work_progress : "incident_id"
  vh_task ||--o{ vh_work_progress : "incident_id + task_id"
  vh_work_order ||--o{ vh_work_progress : "incident_id + task_id + work_order_id"
  vh_work_assignment |o--o{ vh_work_progress : "incident_id + task_id + work_order_id + assignment_id"
  vh_business_event ||--o{ vh_work_progress : "business_event_id"
  users ||--o{ vh_work_progress : "actor_user_id"
  users |o--o{ vh_work_progress : "estimated_by_user_id"
```

## vinhomes-resident-updates

Fields and constraints: [vinhomes-resident-updates](vinhomes-resident-updates.md).

```mermaid
erDiagram
  vh_notification_delivery
  platform_tenant ||--o{ vh_notification_delivery : "ownership"
  vh_project ||--o{ vh_notification_delivery : "ownership"
  vh_notification ||--o{ vh_notification_delivery : "notification_id"
  vh_report_update |o--o{ vh_notification_delivery : "report_update_id"
  vh_report_update
  platform_tenant ||--o{ vh_report_update : "ownership"
  vh_project ||--o{ vh_report_update : "ownership"
  vh_incident ||--o{ vh_report_update : "incident_id"
  vh_resident_report ||--o{ vh_report_update : "report_id"
  users ||--o{ vh_report_update : "recipient_user_id"
  vh_business_event ||--o{ vh_report_update : "business_event_id"
  vh_work_progress |o--o{ vh_report_update : "incident_id + work_progress_id"
  vh_resident_report ||--o{ vh_report_update : "incident_id + recipient_user_id + report_id"
```

## vinhomes-provider-events

Fields and constraints: [vinhomes-provider-events](vinhomes-provider-events.md).

```mermaid
erDiagram
  vh_provider_event
  platform_tenant ||--o{ vh_provider_event : "ownership"
```

## vinhomes-sla

Fields and constraints: [vinhomes-sla](vinhomes-sla.md).

```mermaid
erDiagram
  vh_escalation
  platform_tenant ||--o{ vh_escalation : "ownership"
  vh_project ||--o{ vh_escalation : "ownership"
  vh_incident ||--o{ vh_escalation : "incident_id"
  vh_incident_sla |o--o{ vh_escalation : "incident_id + incident_sla_id"
  vh_team |o--o{ vh_escalation : "assigned_team_id"
  users |o--o{ vh_escalation : "acknowledged_by_user_id"
  vh_incident_sla
  platform_tenant ||--o{ vh_incident_sla : "ownership"
  vh_project ||--o{ vh_incident_sla : "ownership"
  vh_incident ||--o{ vh_incident_sla : "incident_id"
  vh_sla_policy ||--o{ vh_incident_sla : "policy_id"
  vh_sla_policy
  platform_tenant ||--o{ vh_sla_policy : "ownership"
  vh_project ||--o{ vh_sla_policy : "ownership"
```
