# Toàn bộ 682 khóa ngoại PostgreSQL

Nguồn: catalog live `vinhomes_v3`, kiểm ngày 04/10/2026. Mỗi dòng là một FK; các cột tenant_id/id trong một constraint được tính là một quan hệ, không tính từng cột thành FK riêng.

| Bảng con · FK | Bảng cha · cột đích | Ràng buộc |
|---|---|---|
| `access_scopes(tenant_id,building_id)` | `buildings(tenant_id,id)` | `FOREIGN KEY (tenant_id, building_id) REFERENCES buildings(tenant_id, id) ON DELETE RESTRICT` |
| `access_scopes(tenant_id,management_unit_id)` | `management_units(tenant_id,id)` | `FOREIGN KEY (tenant_id, management_unit_id) REFERENCES management_units(tenant_id, id) ON DELETE RESTRICT` |
| `access_scopes(tenant_id,site_id)` | `sites(tenant_id,id)` | `FOREIGN KEY (tenant_id, site_id) REFERENCES sites(tenant_id, id) ON DELETE RESTRICT` |
| `access_scopes(tenant_id)` | `tenants(id)` | `FOREIGN KEY (tenant_id) REFERENCES tenants(id) ON DELETE RESTRICT` |
| `access_scopes(tenant_id,zone_id)` | `zones(tenant_id,id)` | `FOREIGN KEY (tenant_id, zone_id) REFERENCES zones(tenant_id, id) ON DELETE RESTRICT` |
| `account_reviews(reviewer_user_id)` | `users(id)` | `FOREIGN KEY (reviewer_user_id) REFERENCES users(id) ON DELETE RESTRICT` |
| `account_reviews(tenant_id)` | `tenants(id)` | `FOREIGN KEY (tenant_id) REFERENCES tenants(id) ON DELETE RESTRICT` |
| `account_reviews(user_id)` | `users(id)` | `FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE RESTRICT` |
| `accounts(user_id)` | `users(id)` | `FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE` |
| `agent_build_answers(answered_by)` | `users(id)` | `FOREIGN KEY (answered_by) REFERENCES users(id) ON DELETE RESTRICT` |
| `agent_build_answers(tenant_id,request_id)` | `agent_build_requests(tenant_id,id)` | `FOREIGN KEY (tenant_id, request_id) REFERENCES agent_build_requests(tenant_id, id) ON DELETE RESTRICT` |
| `agent_build_answers(tenant_id)` | `tenants(id)` | `FOREIGN KEY (tenant_id) REFERENCES tenants(id) ON DELETE RESTRICT` |
| `agent_build_requests(tenant_id,channel_id)` | `channels(tenant_id,id)` | `FOREIGN KEY (tenant_id, channel_id) REFERENCES channels(tenant_id, id) ON DELETE RESTRICT` |
| `agent_build_requests(requested_by)` | `users(id)` | `FOREIGN KEY (requested_by) REFERENCES users(id) ON DELETE RESTRICT` |
| `agent_build_requests(tenant_id,result_agent_id)` | `agents(tenant_id,id)` | `FOREIGN KEY (tenant_id, result_agent_id) REFERENCES agents(tenant_id, id) ON DELETE RESTRICT` |
| `agent_build_requests(tenant_id)` | `tenants(id)` | `FOREIGN KEY (tenant_id) REFERENCES tenants(id) ON DELETE RESTRICT` |
| `agent_build_requests(tenant_id,workspace_id)` | `workspaces(tenant_id,id)` | `FOREIGN KEY (tenant_id, workspace_id) REFERENCES workspaces(tenant_id, id) ON DELETE RESTRICT` |
| `agent_knowledge_grants(tenant_id,agent_id)` | `agents(tenant_id,id)` | `FOREIGN KEY (tenant_id, agent_id) REFERENCES agents(tenant_id, id) ON DELETE RESTRICT` |
| `agent_knowledge_grants(granted_by)` | `users(id)` | `FOREIGN KEY (granted_by) REFERENCES users(id) ON DELETE RESTRICT` |
| `agent_knowledge_grants(tenant_id,knowledge_base_id)` | `knowledge_bases(tenant_id,id)` | `FOREIGN KEY (tenant_id, knowledge_base_id) REFERENCES knowledge_bases(tenant_id, id) ON DELETE RESTRICT` |
| `agent_knowledge_grants(tenant_id)` | `tenants(id)` | `FOREIGN KEY (tenant_id) REFERENCES tenants(id) ON DELETE RESTRICT` |
| `agent_preferences(tenant_id,agent_id)` | `agents(tenant_id,id)` | `FOREIGN KEY (tenant_id, agent_id) REFERENCES agents(tenant_id, id) ON DELETE RESTRICT` |
| `agent_preferences(tenant_id)` | `tenants(id)` | `FOREIGN KEY (tenant_id) REFERENCES tenants(id) ON DELETE RESTRICT` |
| `agent_preferences(user_id)` | `users(id)` | `FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE RESTRICT` |
| `agent_profiles(tenant_id,agent_id)` | `agents(tenant_id,id)` | `FOREIGN KEY (tenant_id, agent_id) REFERENCES agents(tenant_id, id) ON DELETE RESTRICT` |
| `agent_profiles(owner_user_id)` | `users(id)` | `FOREIGN KEY (owner_user_id) REFERENCES users(id) ON DELETE RESTRICT` |
| `agent_profiles(tenant_id)` | `tenants(id)` | `FOREIGN KEY (tenant_id) REFERENCES tenants(id) ON DELETE RESTRICT` |
| `agent_releases(tenant_id,agent_id)` | `agents(tenant_id,id)` | `FOREIGN KEY (tenant_id, agent_id) REFERENCES agents(tenant_id, id) ON DELETE RESTRICT` |
| `agent_releases(published_by)` | `users(id)` | `FOREIGN KEY (published_by) REFERENCES users(id) ON DELETE RESTRICT` |
| `agent_releases(tenant_id)` | `tenants(id)` | `FOREIGN KEY (tenant_id) REFERENCES tenants(id) ON DELETE RESTRICT` |
| `agent_releases(tenant_id,version_id)` | `agent_versions(tenant_id,id)` | `FOREIGN KEY (tenant_id, version_id) REFERENCES agent_versions(tenant_id, id) ON DELETE RESTRICT` |
| `agent_runs(actor_user_id)` | `users(id)` | `FOREIGN KEY (actor_user_id) REFERENCES users(id) ON DELETE RESTRICT` |
| `agent_runs(tenant_id,agent_id)` | `agents(tenant_id,id)` | `FOREIGN KEY (tenant_id, agent_id) REFERENCES agents(tenant_id, id) ON DELETE RESTRICT` |
| `agent_runs(tenant_id,authority_principal_id)` | `execution_principals(tenant_id,id)` | `FOREIGN KEY (tenant_id, authority_principal_id) REFERENCES execution_principals(tenant_id, id) ON DELETE RESTRICT` |
| `agent_runs(tenant_id,binding_id)` | `runtime_session_bindings(tenant_id,id)` | `FOREIGN KEY (tenant_id, binding_id) REFERENCES runtime_session_bindings(tenant_id, id) ON DELETE RESTRICT` |
| `agent_runs(tenant_id,channel_id)` | `channels(tenant_id,id)` | `FOREIGN KEY (tenant_id, channel_id) REFERENCES channels(tenant_id, id) ON DELETE RESTRICT` |
| `agent_runs(on_behalf_of_user_id)` | `users(id)` | `FOREIGN KEY (on_behalf_of_user_id) REFERENCES users(id) ON DELETE RESTRICT` |
| `agent_runs(tenant_id,parent_run_id)` | `agent_runs(tenant_id,id)` | `FOREIGN KEY (tenant_id, parent_run_id) REFERENCES agent_runs(tenant_id, id) ON DELETE RESTRICT` |
| `agent_runs(tenant_id,team_member_id)` | `team_members(tenant_id,id)` | `FOREIGN KEY (tenant_id, team_member_id) REFERENCES team_members(tenant_id, id) ON DELETE RESTRICT` |
| `agent_runs(tenant_id)` | `tenants(id)` | `FOREIGN KEY (tenant_id) REFERENCES tenants(id) ON DELETE RESTRICT` |
| `agent_runs(tenant_id,trigger_event_id)` | `ticket_events(tenant_id,id)` | `FOREIGN KEY (tenant_id, trigger_event_id) REFERENCES ticket_events(tenant_id, id) ON DELETE RESTRICT` |
| `agent_runs(tenant_id,version_id)` | `agent_versions(tenant_id,id)` | `FOREIGN KEY (tenant_id, version_id) REFERENCES agent_versions(tenant_id, id) ON DELETE RESTRICT` |
| `agent_teams(tenant_id,channel_id)` | `channels(tenant_id,id)` | `FOREIGN KEY (tenant_id, channel_id) REFERENCES channels(tenant_id, id) ON DELETE RESTRICT` |
| `agent_teams(tenant_id,request_message_id)` | `messages(tenant_id,id)` | `FOREIGN KEY (tenant_id, request_message_id) REFERENCES messages(tenant_id, id) ON DELETE RESTRICT` |
| `agent_teams(requested_by_user_id)` | `users(id)` | `FOREIGN KEY (requested_by_user_id) REFERENCES users(id) ON DELETE RESTRICT` |
| `agent_teams(tenant_id,supervisor_agent_id)` | `agents(tenant_id,id)` | `FOREIGN KEY (tenant_id, supervisor_agent_id) REFERENCES agents(tenant_id, id) ON DELETE RESTRICT` |
| `agent_teams(tenant_id)` | `tenants(id)` | `FOREIGN KEY (tenant_id) REFERENCES tenants(id) ON DELETE RESTRICT` |
| `agent_teams(tenant_id,ticket_id)` | `tickets(tenant_id,id)` | `FOREIGN KEY (tenant_id, ticket_id) REFERENCES tickets(tenant_id, id) ON DELETE RESTRICT` |
| `agent_teams(tenant_id,workspace_id)` | `workspaces(tenant_id,id)` | `FOREIGN KEY (tenant_id, workspace_id) REFERENCES workspaces(tenant_id, id) ON DELETE RESTRICT` |
| `agent_versions(tenant_id,agent_id)` | `agents(tenant_id,id)` | `FOREIGN KEY (tenant_id, agent_id) REFERENCES agents(tenant_id, id) ON DELETE RESTRICT` |
| `agent_versions(created_by)` | `users(id)` | `FOREIGN KEY (created_by) REFERENCES users(id) ON DELETE RESTRICT` |
| `agent_versions(tenant_id,model_profile_id)` | `model_profiles(tenant_id,id)` | `FOREIGN KEY (tenant_id, model_profile_id) REFERENCES model_profiles(tenant_id, id) ON DELETE RESTRICT` |
| `agent_versions(tenant_id)` | `tenants(id)` | `FOREIGN KEY (tenant_id) REFERENCES tenants(id) ON DELETE RESTRICT` |
| `agents(tenant_id,package_id)` | `deployment_packages(tenant_id,id)` | `FOREIGN KEY (tenant_id, package_id) REFERENCES deployment_packages(tenant_id, id) ON DELETE RESTRICT` |
| `agents(tenant_id)` | `tenants(id)` | `FOREIGN KEY (tenant_id) REFERENCES tenants(id) ON DELETE RESTRICT` |
| `agents(tenant_id,workspace_id)` | `workspaces(tenant_id,id)` | `FOREIGN KEY (tenant_id, workspace_id) REFERENCES workspaces(tenant_id, id) ON DELETE RESTRICT` |
| `attachments(channel_id)` | `channels(id)` | `FOREIGN KEY (channel_id) REFERENCES channels(id) ON DELETE RESTRICT` |
| `attachments(file_id)` | `files(id)` | `FOREIGN KEY (file_id) REFERENCES files(id) ON DELETE RESTRICT` |
| `attachments(uploaded_by)` | `users(id)` | `FOREIGN KEY (uploaded_by) REFERENCES users(id) ON DELETE RESTRICT` |
| `audit_events(tenant_id)` | `tenants(id)` | `FOREIGN KEY (tenant_id) REFERENCES tenants(id) ON DELETE RESTRICT` |
| `audit_events(tenant_id,workspace_id)` | `workspaces(tenant_id,id)` | `FOREIGN KEY (tenant_id, workspace_id) REFERENCES workspaces(tenant_id, id) ON DELETE RESTRICT` |
| `buildings(tenant_id,site_id)` | `sites(tenant_id,id)` | `FOREIGN KEY (tenant_id, site_id) REFERENCES sites(tenant_id, id) ON DELETE RESTRICT` |
| `buildings(tenant_id)` | `tenants(id)` | `FOREIGN KEY (tenant_id) REFERENCES tenants(id) ON DELETE RESTRICT` |
| `buildings(tenant_id,zone_id)` | `zones(tenant_id,id)` | `FOREIGN KEY (tenant_id, zone_id) REFERENCES zones(tenant_id, id) ON DELETE RESTRICT` |
| `channel_agents(tenant_id,agent_id)` | `agents(tenant_id,id)` | `FOREIGN KEY (tenant_id, agent_id) REFERENCES agents(tenant_id, id) ON DELETE RESTRICT` |
| `channel_agents(tenant_id,channel_id)` | `channels(tenant_id,id)` | `FOREIGN KEY (tenant_id, channel_id) REFERENCES channels(tenant_id, id) ON DELETE RESTRICT` |
| `channel_agents(tenant_id)` | `tenants(id)` | `FOREIGN KEY (tenant_id) REFERENCES tenants(id) ON DELETE RESTRICT` |
| `channel_memberships(tenant_id,channel_id)` | `channels(tenant_id,id)` | `FOREIGN KEY (tenant_id, channel_id) REFERENCES channels(tenant_id, id) ON DELETE RESTRICT` |
| `channel_memberships(tenant_id)` | `tenants(id)` | `FOREIGN KEY (tenant_id) REFERENCES tenants(id) ON DELETE RESTRICT` |
| `channel_memberships(user_id)` | `users(id)` | `FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE RESTRICT` |
| `channels(created_by)` | `users(id)` | `FOREIGN KEY (created_by) REFERENCES users(id) ON DELETE RESTRICT` |
| `channels(tenant_id,last_message_agent_id)` | `agents(tenant_id,id)` | `FOREIGN KEY (tenant_id, last_message_agent_id) REFERENCES agents(tenant_id, id) ON DELETE RESTRICT` |
| `channels(tenant_id,package_id)` | `deployment_packages(tenant_id,id)` | `FOREIGN KEY (tenant_id, package_id) REFERENCES deployment_packages(tenant_id, id) ON DELETE RESTRICT` |
| `channels(tenant_id)` | `tenants(id)` | `FOREIGN KEY (tenant_id) REFERENCES tenants(id) ON DELETE RESTRICT` |
| `channels(tenant_id,workspace_id)` | `workspaces(tenant_id,id)` | `FOREIGN KEY (tenant_id, workspace_id) REFERENCES workspaces(tenant_id, id) ON DELETE RESTRICT` |
| `component_exclusions(tenant_id,agent_id)` | `agents(tenant_id,id)` | `FOREIGN KEY (tenant_id, agent_id) REFERENCES agents(tenant_id, id) ON DELETE RESTRICT` |
| `component_exclusions(component_name)` | `components(name)` | `FOREIGN KEY (component_name) REFERENCES components(name) ON DELETE RESTRICT` |
| `component_exclusions(tenant_id)` | `tenants(id)` | `FOREIGN KEY (tenant_id) REFERENCES tenants(id) ON DELETE RESTRICT` |
| `component_functions(component_name)` | `components(name)` | `FOREIGN KEY (component_name) REFERENCES components(name) ON DELETE RESTRICT` |
| `composio_connections(tenant_id)` | `tenants(id)` | `FOREIGN KEY (tenant_id) REFERENCES tenants(id) ON DELETE RESTRICT` |
| `composio_connections(user_id)` | `users(id)` | `FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE RESTRICT` |
| `computer_page_frame(tenant_id,agent_id)` | `agents(tenant_id,id)` | `FOREIGN KEY (tenant_id, agent_id) REFERENCES agents(tenant_id, id) ON DELETE RESTRICT` |
| `computer_page_frame(tenant_id)` | `tenants(id)` | `FOREIGN KEY (tenant_id) REFERENCES tenants(id) ON DELETE RESTRICT` |
| `computer_snapshot(tenant_id,agent_id)` | `agents(tenant_id,id)` | `FOREIGN KEY (tenant_id, agent_id) REFERENCES agents(tenant_id, id) ON DELETE RESTRICT` |
| `computer_snapshot(tenant_id)` | `tenants(id)` | `FOREIGN KEY (tenant_id) REFERENCES tenants(id) ON DELETE RESTRICT` |
| `context_snapshots(tenant_id,requested_message_id)` | `messages(tenant_id,id)` | `FOREIGN KEY (tenant_id, requested_message_id) REFERENCES messages(tenant_id, id) ON DELETE RESTRICT` |
| `context_snapshots(tenant_id,run_id)` | `agent_runs(tenant_id,id)` | `FOREIGN KEY (tenant_id, run_id) REFERENCES agent_runs(tenant_id, id) ON DELETE RESTRICT` |
| `context_snapshots(tenant_id)` | `tenants(id)` | `FOREIGN KEY (tenant_id) REFERENCES tenants(id) ON DELETE RESTRICT` |
| `context_snapshots(tenant_id,ticket_id)` | `tickets(tenant_id,id)` | `FOREIGN KEY (tenant_id, ticket_id) REFERENCES tickets(tenant_id, id) ON DELETE RESTRICT` |
| `credentials(tenant_id)` | `tenants(id)` | `FOREIGN KEY (tenant_id) REFERENCES tenants(id) ON DELETE RESTRICT` |
| `credentials(tenant_id,workspace_id)` | `workspaces(tenant_id,id)` | `FOREIGN KEY (tenant_id, workspace_id) REFERENCES workspaces(tenant_id, id) ON DELETE RESTRICT` |
| `deployment_packages(tenant_id)` | `tenants(id)` | `FOREIGN KEY (tenant_id) REFERENCES tenants(id) ON DELETE RESTRICT` |
| `dispatch_attempts(tenant_id,assignment_id)` | `work_assignments(tenant_id,id)` | `FOREIGN KEY (tenant_id, assignment_id) REFERENCES work_assignments(tenant_id, id) ON DELETE RESTRICT` |
| `dispatch_attempts(tenant_id,decision_id)` | `ticket_triage_decisions(tenant_id,id)` | `FOREIGN KEY (tenant_id, decision_id) REFERENCES ticket_triage_decisions(tenant_id, id) ON DELETE RESTRICT` |
| `dispatch_attempts(tenant_id,queue_id)` | `dispatch_queue(tenant_id,id)` | `FOREIGN KEY (tenant_id, queue_id) REFERENCES dispatch_queue(tenant_id, id) ON DELETE RESTRICT` |
| `dispatch_attempts(tenant_id)` | `tenants(id)` | `FOREIGN KEY (tenant_id) REFERENCES tenants(id) ON DELETE RESTRICT` |
| `dispatch_attempts(tenant_id,work_order_id)` | `work_orders(tenant_id,id)` | `FOREIGN KEY (tenant_id, work_order_id) REFERENCES work_orders(tenant_id, id) ON DELETE RESTRICT` |
| `dispatch_queue(tenant_id,category_id)` | `service_categories(tenant_id,id)` | `FOREIGN KEY (tenant_id, category_id) REFERENCES service_categories(tenant_id, id) ON DELETE RESTRICT` |
| `dispatch_queue(tenant_id,management_unit_id)` | `management_units(tenant_id,id)` | `FOREIGN KEY (tenant_id, management_unit_id) REFERENCES management_units(tenant_id, id) ON DELETE RESTRICT` |
| `dispatch_queue(tenant_id,priority_decision_id)` | `ticket_triage_decisions(tenant_id,id)` | `FOREIGN KEY (tenant_id, priority_decision_id) REFERENCES ticket_triage_decisions(tenant_id, id) ON DELETE RESTRICT` |
| `dispatch_queue(tenant_id)` | `tenants(id)` | `FOREIGN KEY (tenant_id) REFERENCES tenants(id) ON DELETE RESTRICT` |
| `dispatch_queue(tenant_id,work_order_id)` | `work_orders(tenant_id,id)` | `FOREIGN KEY (tenant_id, work_order_id) REFERENCES work_orders(tenant_id, id) ON DELETE RESTRICT` |
| `document_acl(tenant_id,document_id)` | `knowledge_documents(tenant_id,id)` | `FOREIGN KEY (tenant_id, document_id) REFERENCES knowledge_documents(tenant_id, id) ON DELETE RESTRICT` |
| `document_acl(tenant_id)` | `tenants(id)` | `FOREIGN KEY (tenant_id) REFERENCES tenants(id) ON DELETE RESTRICT` |
| `document_acl(user_id)` | `users(id)` | `FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE RESTRICT` |
| `document_acl(tenant_id,workspace_id)` | `workspaces(tenant_id,id)` | `FOREIGN KEY (tenant_id, workspace_id) REFERENCES workspaces(tenant_id, id) ON DELETE RESTRICT` |
| `document_scopes(tenant_id,document_id)` | `knowledge_documents(tenant_id,id)` | `FOREIGN KEY (tenant_id, document_id) REFERENCES knowledge_documents(tenant_id, id) ON DELETE RESTRICT` |
| `document_scopes(tenant_id,scope_id)` | `access_scopes(tenant_id,id)` | `FOREIGN KEY (tenant_id, scope_id) REFERENCES access_scopes(tenant_id, id) ON DELETE RESTRICT` |
| `document_scopes(tenant_id)` | `tenants(id)` | `FOREIGN KEY (tenant_id) REFERENCES tenants(id) ON DELETE RESTRICT` |
| `document_versions(tenant_id,document_id)` | `knowledge_documents(tenant_id,id)` | `FOREIGN KEY (tenant_id, document_id) REFERENCES knowledge_documents(tenant_id, id) ON DELETE RESTRICT` |
| `document_versions(tenant_id,file_id)` | `files(tenant_id,id)` | `FOREIGN KEY (tenant_id, file_id) REFERENCES files(tenant_id, id) ON DELETE RESTRICT` |
| `document_versions(submitted_by)` | `users(id)` | `FOREIGN KEY (submitted_by) REFERENCES users(id) ON DELETE RESTRICT` |
| `document_versions(tenant_id)` | `tenants(id)` | `FOREIGN KEY (tenant_id) REFERENCES tenants(id) ON DELETE RESTRICT` |
| `domains(tenant_id)` | `tenants(id)` | `FOREIGN KEY (tenant_id) REFERENCES tenants(id) ON DELETE RESTRICT` |
| `event_inbox(tenant_id,event_id)` | `ticket_events(tenant_id,id)` | `FOREIGN KEY (tenant_id, event_id) REFERENCES ticket_events(tenant_id, id) ON DELETE RESTRICT` |
| `event_inbox(tenant_id)` | `tenants(id)` | `FOREIGN KEY (tenant_id) REFERENCES tenants(id) ON DELETE RESTRICT` |
| `event_outbox(tenant_id,event_id)` | `ticket_events(tenant_id,id)` | `FOREIGN KEY (tenant_id, event_id) REFERENCES ticket_events(tenant_id, id) ON DELETE RESTRICT` |
| `event_outbox(tenant_id)` | `tenants(id)` | `FOREIGN KEY (tenant_id) REFERENCES tenants(id) ON DELETE RESTRICT` |
| `evidence_items(tenant_id,assignment_id)` | `work_assignments(tenant_id,id)` | `FOREIGN KEY (tenant_id, assignment_id) REFERENCES work_assignments(tenant_id, id) ON DELETE RESTRICT` |
| `evidence_items(tenant_id,file_id)` | `files(tenant_id,id)` | `FOREIGN KEY (tenant_id, file_id) REFERENCES files(tenant_id, id) ON DELETE RESTRICT` |
| `evidence_items(tenant_id,supersedes_id)` | `evidence_items(tenant_id,id)` | `FOREIGN KEY (tenant_id, supersedes_id) REFERENCES evidence_items(tenant_id, id) ON DELETE RESTRICT` |
| `evidence_items(tenant_id)` | `tenants(id)` | `FOREIGN KEY (tenant_id) REFERENCES tenants(id) ON DELETE RESTRICT` |
| `evidence_items(tenant_id,ticket_id)` | `tickets(tenant_id,id)` | `FOREIGN KEY (tenant_id, ticket_id) REFERENCES tickets(tenant_id, id) ON DELETE RESTRICT` |
| `evidence_items(uploaded_by)` | `users(id)` | `FOREIGN KEY (uploaded_by) REFERENCES users(id) ON DELETE RESTRICT` |
| `evidence_items(tenant_id,work_order_id)` | `work_orders(tenant_id,id)` | `FOREIGN KEY (tenant_id, work_order_id) REFERENCES work_orders(tenant_id, id) ON DELETE RESTRICT` |
| `execution_principals(tenant_id)` | `tenants(id)` | `FOREIGN KEY (tenant_id) REFERENCES tenants(id) ON DELETE RESTRICT` |
| `execution_principals(user_id)` | `users(id)` | `FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE RESTRICT` |
| `execution_principals(tenant_id,workspace_id)` | `workspaces(tenant_id,id)` | `FOREIGN KEY (tenant_id, workspace_id) REFERENCES workspaces(tenant_id, id) ON DELETE RESTRICT` |
| `file_access_logs(tenant_id,actor_principal_id)` | `execution_principals(tenant_id,id)` | `FOREIGN KEY (tenant_id, actor_principal_id) REFERENCES execution_principals(tenant_id, id) ON DELETE RESTRICT` |
| `file_access_logs(actor_user_id)` | `users(id)` | `FOREIGN KEY (actor_user_id) REFERENCES users(id) ON DELETE RESTRICT` |
| `file_access_logs(tenant_id,file_id)` | `files(tenant_id,id)` | `FOREIGN KEY (tenant_id, file_id) REFERENCES files(tenant_id, id) ON DELETE RESTRICT` |
| `file_access_logs(tenant_id,object_id)` | `file_objects(tenant_id,id)` | `FOREIGN KEY (tenant_id, object_id) REFERENCES file_objects(tenant_id, id) ON DELETE RESTRICT` |
| `file_access_logs(tenant_id,run_id)` | `agent_runs(tenant_id,id)` | `FOREIGN KEY (tenant_id, run_id) REFERENCES agent_runs(tenant_id, id) ON DELETE RESTRICT` |
| `file_access_logs(tenant_id)` | `tenants(id)` | `FOREIGN KEY (tenant_id) REFERENCES tenants(id) ON DELETE RESTRICT` |
| `file_deletion_requests(tenant_id,file_id)` | `files(tenant_id,id)` | `FOREIGN KEY (tenant_id, file_id) REFERENCES files(tenant_id, id) ON DELETE RESTRICT` |
| `file_deletion_requests(requested_by)` | `users(id)` | `FOREIGN KEY (requested_by) REFERENCES users(id) ON DELETE RESTRICT` |
| `file_deletion_requests(tenant_id)` | `tenants(id)` | `FOREIGN KEY (tenant_id) REFERENCES tenants(id) ON DELETE RESTRICT` |
| `file_objects(tenant_id,file_id)` | `files(tenant_id,id)` | `FOREIGN KEY (tenant_id, file_id) REFERENCES files(tenant_id, id) ON DELETE RESTRICT` |
| `file_objects(tenant_id,location_id)` | `storage_locations(tenant_id,id)` | `FOREIGN KEY (tenant_id, location_id) REFERENCES storage_locations(tenant_id, id) ON DELETE RESTRICT` |
| `file_objects(tenant_id,source_object_id)` | `file_objects(tenant_id,id)` | `FOREIGN KEY (tenant_id, source_object_id) REFERENCES file_objects(tenant_id, id) ON DELETE RESTRICT` |
| `file_objects(tenant_id)` | `tenants(id)` | `FOREIGN KEY (tenant_id) REFERENCES tenants(id) ON DELETE RESTRICT` |
| `file_processing_jobs(tenant_id,file_id)` | `files(tenant_id,id)` | `FOREIGN KEY (tenant_id, file_id) REFERENCES files(tenant_id, id) ON DELETE RESTRICT` |
| `file_processing_jobs(tenant_id,object_id)` | `file_objects(tenant_id,id)` | `FOREIGN KEY (tenant_id, object_id) REFERENCES file_objects(tenant_id, id) ON DELETE RESTRICT` |
| `file_processing_jobs(tenant_id)` | `tenants(id)` | `FOREIGN KEY (tenant_id) REFERENCES tenants(id) ON DELETE RESTRICT` |
| `file_processing_jobs(tenant_id,upload_id)` | `file_uploads(tenant_id,id)` | `FOREIGN KEY (tenant_id, upload_id) REFERENCES file_uploads(tenant_id, id) ON DELETE RESTRICT` |
| `file_upload_parts(tenant_id)` | `tenants(id)` | `FOREIGN KEY (tenant_id) REFERENCES tenants(id) ON DELETE RESTRICT` |
| `file_upload_parts(tenant_id,upload_id)` | `file_uploads(tenant_id,id)` | `FOREIGN KEY (tenant_id, upload_id) REFERENCES file_uploads(tenant_id, id) ON DELETE RESTRICT` |
| `file_uploads(tenant_id,file_id)` | `files(tenant_id,id)` | `FOREIGN KEY (tenant_id, file_id) REFERENCES files(tenant_id, id) ON DELETE RESTRICT` |
| `file_uploads(tenant_id,location_id)` | `storage_locations(tenant_id,id)` | `FOREIGN KEY (tenant_id, location_id) REFERENCES storage_locations(tenant_id, id) ON DELETE RESTRICT` |
| `file_uploads(requested_by)` | `users(id)` | `FOREIGN KEY (requested_by) REFERENCES users(id) ON DELETE RESTRICT` |
| `file_uploads(tenant_id,result_object_id)` | `file_objects(tenant_id,id)` | `FOREIGN KEY (tenant_id, result_object_id) REFERENCES file_objects(tenant_id, id) ON DELETE RESTRICT` |
| `file_uploads(tenant_id)` | `tenants(id)` | `FOREIGN KEY (tenant_id) REFERENCES tenants(id) ON DELETE RESTRICT` |
| `files(tenant_id,accepted_object_id)` | `file_objects(tenant_id,id)` | `FOREIGN KEY (tenant_id, accepted_object_id) REFERENCES file_objects(tenant_id, id) ON DELETE RESTRICT` |
| `files(tenant_id,channel_id)` | `channels(tenant_id,id)` | `FOREIGN KEY (tenant_id, channel_id) REFERENCES channels(tenant_id, id) ON DELETE RESTRICT` |
| `files(tenant_id,document_id)` | `knowledge_documents(tenant_id,id)` | `FOREIGN KEY (tenant_id, document_id) REFERENCES knowledge_documents(tenant_id, id) ON DELETE RESTRICT` |
| `files(tenant_id,owner_principal_id)` | `execution_principals(tenant_id,id)` | `FOREIGN KEY (tenant_id, owner_principal_id) REFERENCES execution_principals(tenant_id, id) ON DELETE RESTRICT` |
| `files(tenant_id,report_id)` | `report_requests(tenant_id,id)` | `FOREIGN KEY (tenant_id, report_id) REFERENCES report_requests(tenant_id, id) ON DELETE RESTRICT` |
| `files(tenant_id)` | `tenants(id)` | `FOREIGN KEY (tenant_id) REFERENCES tenants(id) ON DELETE RESTRICT` |
| `files(tenant_id,ticket_id)` | `tickets(tenant_id,id)` | `FOREIGN KEY (tenant_id, ticket_id) REFERENCES tickets(tenant_id, id) ON DELETE RESTRICT` |
| `files(tenant_id,unit_id)` | `units(tenant_id,id)` | `FOREIGN KEY (tenant_id, unit_id) REFERENCES units(tenant_id, id)` |
| `files(uploaded_by)` | `users(id)` | `FOREIGN KEY (uploaded_by) REFERENCES users(id) ON DELETE RESTRICT` |
| `incident_types(tenant_id,category_id)` | `service_categories(tenant_id,id)` | `FOREIGN KEY (tenant_id, category_id) REFERENCES service_categories(tenant_id, id) ON DELETE RESTRICT` |
| `incident_types(tenant_id)` | `tenants(id)` | `FOREIGN KEY (tenant_id) REFERENCES tenants(id) ON DELETE RESTRICT` |
| `ingestion_jobs(embedding_model_id)` | `embedding_models(id)` | `FOREIGN KEY (embedding_model_id) REFERENCES embedding_models(id) ON DELETE RESTRICT` |
| `ingestion_jobs(tenant_id)` | `tenants(id)` | `FOREIGN KEY (tenant_id) REFERENCES tenants(id) ON DELETE RESTRICT` |
| `ingestion_jobs(tenant_id,version_id)` | `document_versions(tenant_id,id)` | `FOREIGN KEY (tenant_id, version_id) REFERENCES document_versions(tenant_id, id) ON DELETE RESTRICT` |
| `intelligence_channel_mappings(channel_id)` | `channels(id)` | `FOREIGN KEY (channel_id) REFERENCES channels(id) ON DELETE RESTRICT` |
| `intelligence_channel_mappings(user_id)` | `users(id)` | `FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE RESTRICT` |
| `interruption_scopes(tenant_id,interruption_id)` | `service_interruptions(tenant_id,id)` | `FOREIGN KEY (tenant_id, interruption_id) REFERENCES service_interruptions(tenant_id, id) ON DELETE RESTRICT` |
| `interruption_scopes(tenant_id,scope_id)` | `access_scopes(tenant_id,id)` | `FOREIGN KEY (tenant_id, scope_id) REFERENCES access_scopes(tenant_id, id) ON DELETE RESTRICT` |
| `interruption_scopes(tenant_id)` | `tenants(id)` | `FOREIGN KEY (tenant_id) REFERENCES tenants(id) ON DELETE RESTRICT` |
| `invoice_lines(tenant_id,category_id)` | `service_categories(tenant_id,id)` | `FOREIGN KEY (tenant_id, category_id) REFERENCES service_categories(tenant_id, id) ON DELETE RESTRICT` |
| `invoice_lines(tenant_id,invoice_id)` | `invoices(tenant_id,id)` | `FOREIGN KEY (tenant_id, invoice_id) REFERENCES invoices(tenant_id, id) ON DELETE RESTRICT` |
| `invoice_lines(tenant_id)` | `tenants(id)` | `FOREIGN KEY (tenant_id) REFERENCES tenants(id) ON DELETE RESTRICT` |
| `invoices(bill_to_user_id)` | `users(id)` | `FOREIGN KEY (bill_to_user_id) REFERENCES users(id) ON DELETE RESTRICT` |
| `invoices(tenant_id,issued_by_staff_id)` | `staff_profiles(tenant_id,id)` | `FOREIGN KEY (tenant_id, issued_by_staff_id) REFERENCES staff_profiles(tenant_id, id) ON DELETE RESTRICT` |
| `invoices(tenant_id,legal_invoice_file_id)` | `files(tenant_id,id)` | `FOREIGN KEY (tenant_id, legal_invoice_file_id) REFERENCES files(tenant_id, id) ON DELETE RESTRICT` |
| `invoices(tenant_id,supersedes_invoice_id)` | `invoices(tenant_id,id)` | `FOREIGN KEY (tenant_id, supersedes_invoice_id) REFERENCES invoices(tenant_id, id) ON DELETE RESTRICT` |
| `invoices(tenant_id)` | `tenants(id)` | `FOREIGN KEY (tenant_id) REFERENCES tenants(id) ON DELETE RESTRICT` |
| `invoices(tenant_id,ticket_id)` | `tickets(tenant_id,id)` | `FOREIGN KEY (tenant_id, ticket_id) REFERENCES tickets(tenant_id, id) ON DELETE RESTRICT` |
| `invoices(tenant_id,work_order_id)` | `work_orders(tenant_id,id)` | `FOREIGN KEY (tenant_id, work_order_id) REFERENCES work_orders(tenant_id, id) ON DELETE RESTRICT` |
| `knowledge_bases(tenant_id,domain_id)` | `domains(tenant_id,id)` | `FOREIGN KEY (tenant_id, domain_id) REFERENCES domains(tenant_id, id) ON DELETE RESTRICT` |
| `knowledge_bases(tenant_id)` | `tenants(id)` | `FOREIGN KEY (tenant_id) REFERENCES tenants(id) ON DELETE RESTRICT` |
| `knowledge_categories(tenant_id,parent_id)` | `knowledge_categories(tenant_id,id)` | `FOREIGN KEY (tenant_id, parent_id) REFERENCES knowledge_categories(tenant_id, id) ON DELETE RESTRICT` |
| `knowledge_categories(tenant_id)` | `tenants(id)` | `FOREIGN KEY (tenant_id) REFERENCES tenants(id) ON DELETE RESTRICT` |
| `knowledge_chunks(tenant_id)` | `tenants(id)` | `FOREIGN KEY (tenant_id) REFERENCES tenants(id) ON DELETE RESTRICT` |
| `knowledge_chunks(tenant_id,version_id)` | `document_versions(tenant_id,id)` | `FOREIGN KEY (tenant_id, version_id) REFERENCES document_versions(tenant_id, id) ON DELETE RESTRICT` |
| `knowledge_documents(tenant_id,active_version_id)` | `document_versions(tenant_id,id)` | `FOREIGN KEY (tenant_id, active_version_id) REFERENCES document_versions(tenant_id, id) ON DELETE RESTRICT` |
| `knowledge_documents(tenant_id,category_id)` | `knowledge_categories(tenant_id,id)` | `FOREIGN KEY (tenant_id, category_id) REFERENCES knowledge_categories(tenant_id, id) ON DELETE RESTRICT` |
| `knowledge_documents(tenant_id,knowledge_base_id)` | `knowledge_bases(tenant_id,id)` | `FOREIGN KEY (tenant_id, knowledge_base_id) REFERENCES knowledge_bases(tenant_id, id) ON DELETE RESTRICT` |
| `knowledge_documents(tenant_id,memory_namespace_id)` | `memory_namespaces(tenant_id,id)` | `FOREIGN KEY (tenant_id, memory_namespace_id) REFERENCES memory_namespaces(tenant_id, id) ON DELETE RESTRICT` |
| `knowledge_documents(tenant_id,owner_management_id)` | `management_units(tenant_id,id)` | `FOREIGN KEY (tenant_id, owner_management_id) REFERENCES management_units(tenant_id, id) ON DELETE RESTRICT` |
| `knowledge_documents(tenant_id)` | `tenants(id)` | `FOREIGN KEY (tenant_id) REFERENCES tenants(id) ON DELETE RESTRICT` |
| `knowledge_embeddings(tenant_id,chunk_id)` | `knowledge_chunks(tenant_id,id)` | `FOREIGN KEY (tenant_id, chunk_id) REFERENCES knowledge_chunks(tenant_id, id) ON DELETE RESTRICT` |
| `knowledge_embeddings(model_id)` | `embedding_models(id)` | `FOREIGN KEY (model_id) REFERENCES embedding_models(id) ON DELETE RESTRICT` |
| `knowledge_embeddings(tenant_id)` | `tenants(id)` | `FOREIGN KEY (tenant_id) REFERENCES tenants(id) ON DELETE RESTRICT` |
| `knowledge_reviews(tenant_id,document_version_id)` | `document_versions(tenant_id,id)` | `FOREIGN KEY (tenant_id, document_version_id) REFERENCES document_versions(tenant_id, id) ON DELETE RESTRICT` |
| `knowledge_reviews(tenant_id,memory_candidate_id)` | `memory_candidates(tenant_id,id)` | `FOREIGN KEY (tenant_id, memory_candidate_id) REFERENCES memory_candidates(tenant_id, id) ON DELETE RESTRICT` |
| `knowledge_reviews(reviewer_user_id)` | `users(id)` | `FOREIGN KEY (reviewer_user_id) REFERENCES users(id) ON DELETE RESTRICT` |
| `knowledge_reviews(tenant_id)` | `tenants(id)` | `FOREIGN KEY (tenant_id) REFERENCES tenants(id) ON DELETE RESTRICT` |
| `mailbox_deliveries(tenant_id,mailbox_id)` | `team_mailbox(tenant_id,id)` | `FOREIGN KEY (tenant_id, mailbox_id) REFERENCES team_mailbox(tenant_id, id) ON DELETE RESTRICT` |
| `mailbox_deliveries(tenant_id,recipient_member_id)` | `team_members(tenant_id,id)` | `FOREIGN KEY (tenant_id, recipient_member_id) REFERENCES team_members(tenant_id, id) ON DELETE RESTRICT` |
| `mailbox_deliveries(tenant_id)` | `tenants(id)` | `FOREIGN KEY (tenant_id) REFERENCES tenants(id) ON DELETE RESTRICT` |
| `management_coverage(tenant_id,management_unit_id)` | `management_units(tenant_id,id)` | `FOREIGN KEY (tenant_id, management_unit_id) REFERENCES management_units(tenant_id, id) ON DELETE RESTRICT` |
| `management_coverage(tenant_id,scope_id)` | `access_scopes(tenant_id,id)` | `FOREIGN KEY (tenant_id, scope_id) REFERENCES access_scopes(tenant_id, id) ON DELETE RESTRICT` |
| `management_coverage(tenant_id,service_category_id)` | `service_categories(tenant_id,id)` | `FOREIGN KEY (tenant_id, service_category_id) REFERENCES service_categories(tenant_id, id) ON DELETE RESTRICT` |
| `management_coverage(tenant_id)` | `tenants(id)` | `FOREIGN KEY (tenant_id) REFERENCES tenants(id) ON DELETE RESTRICT` |
| `management_units(tenant_id)` | `tenants(id)` | `FOREIGN KEY (tenant_id) REFERENCES tenants(id) ON DELETE RESTRICT` |
| `mcp_servers(credential_id)` | `credentials(id)` | `FOREIGN KEY (credential_id) REFERENCES credentials(id) ON DELETE RESTRICT` |
| `mcp_servers(tenant_id)` | `tenants(id)` | `FOREIGN KEY (tenant_id) REFERENCES tenants(id) ON DELETE RESTRICT` |
| `mcp_servers(tenant_id,workspace_id)` | `workspaces(tenant_id,id)` | `FOREIGN KEY (tenant_id, workspace_id) REFERENCES workspaces(tenant_id, id) ON DELETE RESTRICT` |
| `mcp_tools(tenant_id,server_id)` | `mcp_servers(tenant_id,id)` | `FOREIGN KEY (tenant_id, server_id) REFERENCES mcp_servers(tenant_id, id) ON DELETE RESTRICT` |
| `mcp_tools(tenant_id)` | `tenants(id)` | `FOREIGN KEY (tenant_id) REFERENCES tenants(id) ON DELETE RESTRICT` |
| `mcp_user_credentials(credential_id)` | `credentials(id)` | `FOREIGN KEY (credential_id) REFERENCES credentials(id) ON DELETE RESTRICT` |
| `mcp_user_credentials(tenant_id,server_id)` | `mcp_servers(tenant_id,id)` | `FOREIGN KEY (tenant_id, server_id) REFERENCES mcp_servers(tenant_id, id) ON DELETE RESTRICT` |
| `mcp_user_credentials(tenant_id)` | `tenants(id)` | `FOREIGN KEY (tenant_id) REFERENCES tenants(id) ON DELETE RESTRICT` |
| `mcp_user_credentials(user_id)` | `users(id)` | `FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE RESTRICT` |
| `memory_candidates(tenant_id,namespace_id)` | `memory_namespaces(tenant_id,id)` | `FOREIGN KEY (tenant_id, namespace_id) REFERENCES memory_namespaces(tenant_id, id) ON DELETE RESTRICT` |
| `memory_candidates(tenant_id,proposed_by_agent_id)` | `agents(tenant_id,id)` | `FOREIGN KEY (tenant_id, proposed_by_agent_id) REFERENCES agents(tenant_id, id) ON DELETE RESTRICT` |
| `memory_candidates(tenant_id,scope_id)` | `access_scopes(tenant_id,id)` | `FOREIGN KEY (tenant_id, scope_id) REFERENCES access_scopes(tenant_id, id) ON DELETE RESTRICT` |
| `memory_candidates(tenant_id,source_binding_id)` | `runtime_session_bindings(tenant_id,id)` | `FOREIGN KEY (tenant_id, source_binding_id) REFERENCES runtime_session_bindings(tenant_id, id) ON DELETE RESTRICT` |
| `memory_candidates(tenant_id,source_run_id)` | `agent_runs(tenant_id,id)` | `FOREIGN KEY (tenant_id, source_run_id) REFERENCES agent_runs(tenant_id, id) ON DELETE RESTRICT` |
| `memory_candidates(tenant_id,source_ticket_id)` | `tickets(tenant_id,id)` | `FOREIGN KEY (tenant_id, source_ticket_id) REFERENCES tickets(tenant_id, id) ON DELETE RESTRICT` |
| `memory_candidates(subject_user_id)` | `users(id)` | `FOREIGN KEY (subject_user_id) REFERENCES users(id) ON DELETE RESTRICT` |
| `memory_candidates(tenant_id,supersedes_candidate_id)` | `memory_candidates(tenant_id,id)` | `FOREIGN KEY (tenant_id, supersedes_candidate_id) REFERENCES memory_candidates(tenant_id, id) ON DELETE RESTRICT` |
| `memory_candidates(tenant_id)` | `tenants(id)` | `FOREIGN KEY (tenant_id) REFERENCES tenants(id) ON DELETE RESTRICT` |
| `memory_namespaces(tenant_id,owner_principal_id)` | `execution_principals(tenant_id,id)` | `FOREIGN KEY (tenant_id, owner_principal_id) REFERENCES execution_principals(tenant_id, id) ON DELETE RESTRICT` |
| `memory_namespaces(tenant_id,team_id)` | `agent_teams(tenant_id,id)` | `FOREIGN KEY (tenant_id, team_id) REFERENCES agent_teams(tenant_id, id) ON DELETE RESTRICT` |
| `memory_namespaces(tenant_id)` | `tenants(id)` | `FOREIGN KEY (tenant_id) REFERENCES tenants(id) ON DELETE RESTRICT` |
| `memory_namespaces(tenant_id,workspace_id)` | `workspaces(tenant_id,id)` | `FOREIGN KEY (tenant_id, workspace_id) REFERENCES workspaces(tenant_id, id) ON DELETE RESTRICT` |
| `memory_publications(tenant_id,approval_review_id)` | `knowledge_reviews(tenant_id,id)` | `FOREIGN KEY (tenant_id, approval_review_id) REFERENCES knowledge_reviews(tenant_id, id) ON DELETE RESTRICT` |
| `memory_publications(tenant_id,candidate_id)` | `memory_candidates(tenant_id,id)` | `FOREIGN KEY (tenant_id, candidate_id) REFERENCES memory_candidates(tenant_id, id) ON DELETE RESTRICT` |
| `memory_publications(tenant_id,document_id)` | `knowledge_documents(tenant_id,id)` | `FOREIGN KEY (tenant_id, document_id) REFERENCES knowledge_documents(tenant_id, id) ON DELETE RESTRICT` |
| `memory_publications(tenant_id,namespace_id)` | `memory_namespaces(tenant_id,id)` | `FOREIGN KEY (tenant_id, namespace_id) REFERENCES memory_namespaces(tenant_id, id) ON DELETE RESTRICT` |
| `memory_publications(tenant_id)` | `tenants(id)` | `FOREIGN KEY (tenant_id) REFERENCES tenants(id) ON DELETE RESTRICT` |
| `memory_publications(tenant_id,version_id)` | `document_versions(tenant_id,id)` | `FOREIGN KEY (tenant_id, version_id) REFERENCES document_versions(tenant_id, id) ON DELETE RESTRICT` |
| `message_files(tenant_id,file_id)` | `files(tenant_id,id)` | `FOREIGN KEY (tenant_id, file_id) REFERENCES files(tenant_id, id) ON DELETE RESTRICT` |
| `message_files(tenant_id,message_id)` | `messages(tenant_id,id)` | `FOREIGN KEY (tenant_id, message_id) REFERENCES messages(tenant_id, id) ON DELETE RESTRICT` |
| `message_files(tenant_id)` | `tenants(id)` | `FOREIGN KEY (tenant_id) REFERENCES tenants(id) ON DELETE RESTRICT` |
| `message_mentions(tenant_id,agent_id)` | `agents(tenant_id,id)` | `FOREIGN KEY (tenant_id, agent_id) REFERENCES agents(tenant_id, id) ON DELETE RESTRICT` |
| `message_mentions(tenant_id,message_id)` | `messages(tenant_id,id)` | `FOREIGN KEY (tenant_id, message_id) REFERENCES messages(tenant_id, id) ON DELETE RESTRICT` |
| `message_mentions(requested_by)` | `users(id)` | `FOREIGN KEY (requested_by) REFERENCES users(id) ON DELETE RESTRICT` |
| `message_mentions(tenant_id,resolved_run_id)` | `agent_runs(tenant_id,id)` | `FOREIGN KEY (tenant_id, resolved_run_id) REFERENCES agent_runs(tenant_id, id) ON DELETE RESTRICT` |
| `message_mentions(tenant_id)` | `tenants(id)` | `FOREIGN KEY (tenant_id) REFERENCES tenants(id) ON DELETE RESTRICT` |
| `messages(tenant_id,channel_id)` | `channels(tenant_id,id)` | `FOREIGN KEY (tenant_id, channel_id) REFERENCES channels(tenant_id, id) ON DELETE RESTRICT` |
| `messages(tenant_id,reply_to_id)` | `messages(tenant_id,id)` | `FOREIGN KEY (tenant_id, reply_to_id) REFERENCES messages(tenant_id, id) ON DELETE RESTRICT` |
| `messages(tenant_id,run_id)` | `agent_runs(tenant_id,id)` | `FOREIGN KEY (tenant_id, run_id) REFERENCES agent_runs(tenant_id, id) ON DELETE RESTRICT` |
| `messages(tenant_id,sender_agent_id)` | `agents(tenant_id,id)` | `FOREIGN KEY (tenant_id, sender_agent_id) REFERENCES agents(tenant_id, id) ON DELETE RESTRICT` |
| `messages(sender_user_id)` | `users(id)` | `FOREIGN KEY (sender_user_id) REFERENCES users(id) ON DELETE RESTRICT` |
| `messages(tenant_id,source_event_id)` | `ticket_events(tenant_id,id)` | `FOREIGN KEY (tenant_id, source_event_id) REFERENCES ticket_events(tenant_id, id) ON DELETE RESTRICT` |
| `messages(tenant_id)` | `tenants(id)` | `FOREIGN KEY (tenant_id) REFERENCES tenants(id) ON DELETE RESTRICT` |
| `model_profiles(credential_id)` | `credentials(id)` | `FOREIGN KEY (credential_id) REFERENCES credentials(id) ON DELETE RESTRICT` |
| `model_profiles(tenant_id)` | `tenants(id)` | `FOREIGN KEY (tenant_id) REFERENCES tenants(id) ON DELETE RESTRICT` |
| `model_profiles(tenant_id,workspace_id)` | `workspaces(tenant_id,id)` | `FOREIGN KEY (tenant_id, workspace_id) REFERENCES workspaces(tenant_id, id) ON DELETE RESTRICT` |
| `notification_deliveries(tenant_id,interruption_id)` | `service_interruptions(tenant_id,id)` | `FOREIGN KEY (tenant_id, interruption_id) REFERENCES service_interruptions(tenant_id, id) ON DELETE RESTRICT` |
| `notification_deliveries(tenant_id,message_id)` | `messages(tenant_id,id)` | `FOREIGN KEY (tenant_id, message_id) REFERENCES messages(tenant_id, id) ON DELETE RESTRICT` |
| `notification_deliveries(tenant_id)` | `tenants(id)` | `FOREIGN KEY (tenant_id) REFERENCES tenants(id) ON DELETE RESTRICT` |
| `notification_deliveries(tenant_id,ticket_event_id)` | `ticket_events(tenant_id,id)` | `FOREIGN KEY (tenant_id, ticket_event_id) REFERENCES ticket_events(tenant_id, id) ON DELETE RESTRICT` |
| `notification_deliveries(user_id)` | `users(id)` | `FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE RESTRICT` |
| `payment_allocations(tenant_id,invoice_id)` | `invoices(tenant_id,id)` | `FOREIGN KEY (tenant_id, invoice_id) REFERENCES invoices(tenant_id, id) ON DELETE RESTRICT` |
| `payment_allocations(tenant_id,payment_id)` | `payments(tenant_id,id)` | `FOREIGN KEY (tenant_id, payment_id) REFERENCES payments(tenant_id, id) ON DELETE RESTRICT` |
| `payment_allocations(tenant_id)` | `tenants(id)` | `FOREIGN KEY (tenant_id) REFERENCES tenants(id) ON DELETE RESTRICT` |
| `payment_intents(tenant_id,invoice_id)` | `invoices(tenant_id,id)` | `FOREIGN KEY (tenant_id, invoice_id) REFERENCES invoices(tenant_id, id) ON DELETE RESTRICT` |
| `payment_intents(tenant_id)` | `tenants(id)` | `FOREIGN KEY (tenant_id) REFERENCES tenants(id) ON DELETE RESTRICT` |
| `payment_webhook_receipts(tenant_id,intent_id)` | `payment_intents(tenant_id,id)` | `FOREIGN KEY (tenant_id, intent_id) REFERENCES payment_intents(tenant_id, id) ON DELETE RESTRICT` |
| `payment_webhook_receipts(tenant_id)` | `tenants(id)` | `FOREIGN KEY (tenant_id) REFERENCES tenants(id) ON DELETE RESTRICT` |
| `payments(tenant_id,intent_id)` | `payment_intents(tenant_id,id)` | `FOREIGN KEY (tenant_id, intent_id) REFERENCES payment_intents(tenant_id, id) ON DELETE RESTRICT` |
| `payments(tenant_id,invoice_id)` | `invoices(tenant_id,id)` | `FOREIGN KEY (tenant_id, invoice_id) REFERENCES invoices(tenant_id, id) ON DELETE RESTRICT` |
| `payments(tenant_id,receipt_id)` | `payment_webhook_receipts(tenant_id,id)` | `FOREIGN KEY (tenant_id, receipt_id) REFERENCES payment_webhook_receipts(tenant_id, id) ON DELETE RESTRICT` |
| `payments(tenant_id)` | `tenants(id)` | `FOREIGN KEY (tenant_id) REFERENCES tenants(id) ON DELETE RESTRICT` |
| `platform_admins(granted_by)` | `users(id)` | `FOREIGN KEY (granted_by) REFERENCES users(id) ON DELETE RESTRICT` |
| `platform_admins(user_id)` | `users(id)` | `FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE RESTRICT` |
| `plugin_grants(tenant_id,agent_id)` | `agents(tenant_id,id)` | `FOREIGN KEY (tenant_id, agent_id) REFERENCES agents(tenant_id, id) ON DELETE RESTRICT` |
| `plugin_grants(tenant_id)` | `tenants(id)` | `FOREIGN KEY (tenant_id) REFERENCES tenants(id) ON DELETE RESTRICT` |
| `reception_sessions(tenant_id,binding_id)` | `runtime_session_bindings(tenant_id,id)` | `FOREIGN KEY (tenant_id, binding_id) REFERENCES runtime_session_bindings(tenant_id, id) ON DELETE RESTRICT` |
| `reception_sessions(tenant_id,channel_id)` | `channels(tenant_id,id)` | `FOREIGN KEY (tenant_id, channel_id) REFERENCES channels(tenant_id, id) ON DELETE RESTRICT` |
| `reception_sessions(customer_user_id)` | `users(id)` | `FOREIGN KEY (customer_user_id) REFERENCES users(id) ON DELETE RESTRICT` |
| `reception_sessions(tenant_id,system_agent_id)` | `agents(tenant_id,id)` | `FOREIGN KEY (tenant_id, system_agent_id) REFERENCES agents(tenant_id, id) ON DELETE RESTRICT` |
| `reception_sessions(tenant_id)` | `tenants(id)` | `FOREIGN KEY (tenant_id) REFERENCES tenants(id) ON DELETE RESTRICT` |
| `reception_waits(tenant_id,operation_id)` | `runtime_session_operations(tenant_id,id)` | `FOREIGN KEY (tenant_id, operation_id) REFERENCES runtime_session_operations(tenant_id, id) ON DELETE RESTRICT` |
| `reception_waits(tenant_id,resumed_event_id)` | `ticket_events(tenant_id,id)` | `FOREIGN KEY (tenant_id, resumed_event_id) REFERENCES ticket_events(tenant_id, id) ON DELETE RESTRICT` |
| `reception_waits(tenant_id,session_id)` | `reception_sessions(tenant_id,id)` | `FOREIGN KEY (tenant_id, session_id) REFERENCES reception_sessions(tenant_id, id) ON DELETE RESTRICT` |
| `reception_waits(tenant_id)` | `tenants(id)` | `FOREIGN KEY (tenant_id) REFERENCES tenants(id) ON DELETE RESTRICT` |
| `reception_waits(tenant_id,ticket_id)` | `tickets(tenant_id,id)` | `FOREIGN KEY (tenant_id, ticket_id) REFERENCES tickets(tenant_id, id) ON DELETE RESTRICT` |
| `refund_allocations(tenant_id,payment_allocation_id)` | `payment_allocations(tenant_id,id)` | `FOREIGN KEY (tenant_id, payment_allocation_id) REFERENCES payment_allocations(tenant_id, id) ON DELETE RESTRICT` |
| `refund_allocations(tenant_id,refund_id)` | `refunds(tenant_id,id)` | `FOREIGN KEY (tenant_id, refund_id) REFERENCES refunds(tenant_id, id) ON DELETE RESTRICT` |
| `refund_allocations(tenant_id)` | `tenants(id)` | `FOREIGN KEY (tenant_id) REFERENCES tenants(id) ON DELETE RESTRICT` |
| `refunds(approved_by)` | `users(id)` | `FOREIGN KEY (approved_by) REFERENCES users(id) ON DELETE RESTRICT` |
| `refunds(tenant_id,payment_id)` | `payments(tenant_id,id)` | `FOREIGN KEY (tenant_id, payment_id) REFERENCES payments(tenant_id, id) ON DELETE RESTRICT` |
| `refunds(requested_by)` | `users(id)` | `FOREIGN KEY (requested_by) REFERENCES users(id) ON DELETE RESTRICT` |
| `refunds(tenant_id)` | `tenants(id)` | `FOREIGN KEY (tenant_id) REFERENCES tenants(id) ON DELETE RESTRICT` |
| `report_requests(tenant_id,channel_id)` | `channels(tenant_id,id)` | `FOREIGN KEY (tenant_id, channel_id) REFERENCES channels(tenant_id, id) ON DELETE RESTRICT` |
| `report_requests(requested_by)` | `users(id)` | `FOREIGN KEY (requested_by) REFERENCES users(id) ON DELETE RESTRICT` |
| `report_requests(tenant_id,result_file_id)` | `files(tenant_id,id)` | `FOREIGN KEY (tenant_id, result_file_id) REFERENCES files(tenant_id, id) ON DELETE RESTRICT` |
| `report_requests(tenant_id,run_id)` | `agent_runs(tenant_id,id)` | `FOREIGN KEY (tenant_id, run_id) REFERENCES agent_runs(tenant_id, id) ON DELETE RESTRICT` |
| `report_requests(tenant_id,scope_id)` | `access_scopes(tenant_id,id)` | `FOREIGN KEY (tenant_id, scope_id) REFERENCES access_scopes(tenant_id, id) ON DELETE RESTRICT` |
| `report_requests(tenant_id,source_message_id)` | `messages(tenant_id,id)` | `FOREIGN KEY (tenant_id, source_message_id) REFERENCES messages(tenant_id, id) ON DELETE RESTRICT` |
| `report_requests(tenant_id)` | `tenants(id)` | `FOREIGN KEY (tenant_id) REFERENCES tenants(id) ON DELETE RESTRICT` |
| `report_requests(tenant_id,workspace_id)` | `workspaces(tenant_id,id)` | `FOREIGN KEY (tenant_id, workspace_id) REFERENCES workspaces(tenant_id, id) ON DELETE RESTRICT` |
| `report_sources(tenant_id,report_id)` | `report_requests(tenant_id,id)` | `FOREIGN KEY (tenant_id, report_id) REFERENCES report_requests(tenant_id, id) ON DELETE RESTRICT` |
| `report_sources(tenant_id,snapshot_file_id)` | `files(tenant_id,id)` | `FOREIGN KEY (tenant_id, snapshot_file_id) REFERENCES files(tenant_id, id) ON DELETE RESTRICT` |
| `report_sources(tenant_id)` | `tenants(id)` | `FOREIGN KEY (tenant_id) REFERENCES tenants(id) ON DELETE RESTRICT` |
| `retrieval_hits(tenant_id,chunk_id)` | `knowledge_chunks(tenant_id,id)` | `FOREIGN KEY (tenant_id, chunk_id) REFERENCES knowledge_chunks(tenant_id, id) ON DELETE RESTRICT` |
| `retrieval_hits(tenant_id,retrieval_run_id)` | `retrieval_runs(tenant_id,id)` | `FOREIGN KEY (tenant_id, retrieval_run_id) REFERENCES retrieval_runs(tenant_id, id) ON DELETE RESTRICT` |
| `retrieval_hits(tenant_id)` | `tenants(id)` | `FOREIGN KEY (tenant_id) REFERENCES tenants(id) ON DELETE RESTRICT` |
| `retrieval_runs(actor_user_id)` | `users(id)` | `FOREIGN KEY (actor_user_id) REFERENCES users(id) ON DELETE RESTRICT` |
| `retrieval_runs(tenant_id,agent_run_id)` | `agent_runs(tenant_id,id)` | `FOREIGN KEY (tenant_id, agent_run_id) REFERENCES agent_runs(tenant_id, id) ON DELETE RESTRICT` |
| `retrieval_runs(tenant_id,binding_id)` | `runtime_session_bindings(tenant_id,id)` | `FOREIGN KEY (tenant_id, binding_id) REFERENCES runtime_session_bindings(tenant_id, id) ON DELETE RESTRICT` |
| `retrieval_runs(tenant_id,knowledge_base_id)` | `knowledge_bases(tenant_id,id)` | `FOREIGN KEY (tenant_id, knowledge_base_id) REFERENCES knowledge_bases(tenant_id, id) ON DELETE RESTRICT` |
| `retrieval_runs(model_id)` | `embedding_models(id)` | `FOREIGN KEY (model_id) REFERENCES embedding_models(id) ON DELETE RESTRICT` |
| `retrieval_runs(tenant_id,principal_id)` | `execution_principals(tenant_id,id)` | `FOREIGN KEY (tenant_id, principal_id) REFERENCES execution_principals(tenant_id, id) ON DELETE RESTRICT` |
| `retrieval_runs(tenant_id)` | `tenants(id)` | `FOREIGN KEY (tenant_id) REFERENCES tenants(id) ON DELETE RESTRICT` |
| `routine_runs(tenant_id,routine_id)` | `routines(tenant_id,id)` | `FOREIGN KEY (tenant_id, routine_id) REFERENCES routines(tenant_id, id) ON DELETE RESTRICT` |
| `routine_runs(tenant_id)` | `tenants(id)` | `FOREIGN KEY (tenant_id) REFERENCES tenants(id) ON DELETE RESTRICT` |
| `routine_runs(tenant_id,workspace_id)` | `workspaces(tenant_id,id)` | `FOREIGN KEY (tenant_id, workspace_id) REFERENCES workspaces(tenant_id, id) ON DELETE RESTRICT` |
| `routines(tenant_id,agent_id)` | `agents(tenant_id,id)` | `FOREIGN KEY (tenant_id, agent_id) REFERENCES agents(tenant_id, id) ON DELETE RESTRICT` |
| `routines(tenant_id,channel_id)` | `channels(tenant_id,id)` | `FOREIGN KEY (tenant_id, channel_id) REFERENCES channels(tenant_id, id) ON DELETE RESTRICT` |
| `routines(owner_user_id)` | `users(id)` | `FOREIGN KEY (owner_user_id) REFERENCES users(id) ON DELETE RESTRICT` |
| `routines(tenant_id)` | `tenants(id)` | `FOREIGN KEY (tenant_id) REFERENCES tenants(id) ON DELETE RESTRICT` |
| `routines(tenant_id,workspace_id)` | `workspaces(tenant_id,id)` | `FOREIGN KEY (tenant_id, workspace_id) REFERENCES workspaces(tenant_id, id) ON DELETE RESTRICT` |
| `run_memory_access(tenant_id,namespace_id)` | `memory_namespaces(tenant_id,id)` | `FOREIGN KEY (tenant_id, namespace_id) REFERENCES memory_namespaces(tenant_id, id) ON DELETE RESTRICT` |
| `run_memory_access(tenant_id,run_id)` | `agent_runs(tenant_id,id)` | `FOREIGN KEY (tenant_id, run_id) REFERENCES agent_runs(tenant_id, id) ON DELETE RESTRICT` |
| `run_memory_access(tenant_id)` | `tenants(id)` | `FOREIGN KEY (tenant_id) REFERENCES tenants(id) ON DELETE RESTRICT` |
| `runtime_identities(backend_id)` | `runtime_backends(id)` | `FOREIGN KEY (backend_id) REFERENCES runtime_backends(id) ON DELETE RESTRICT` |
| `runtime_identities(tenant_id,principal_id)` | `execution_principals(tenant_id,id)` | `FOREIGN KEY (tenant_id, principal_id) REFERENCES execution_principals(tenant_id, id) ON DELETE RESTRICT` |
| `runtime_identities(tenant_id)` | `tenants(id)` | `FOREIGN KEY (tenant_id) REFERENCES tenants(id) ON DELETE RESTRICT` |
| `runtime_memory_bindings(backend_id)` | `runtime_backends(id)` | `FOREIGN KEY (backend_id) REFERENCES runtime_backends(id) ON DELETE RESTRICT` |
| `runtime_memory_bindings(tenant_id,namespace_id)` | `memory_namespaces(tenant_id,id)` | `FOREIGN KEY (tenant_id, namespace_id) REFERENCES memory_namespaces(tenant_id, id) ON DELETE RESTRICT` |
| `runtime_memory_bindings(tenant_id)` | `tenants(id)` | `FOREIGN KEY (tenant_id) REFERENCES tenants(id) ON DELETE RESTRICT` |
| `runtime_session_bindings(tenant_id,identity_id,backend_id)` | `runtime_identities(tenant_id,id,backend_id)` | `FOREIGN KEY (tenant_id, identity_id, backend_id) REFERENCES runtime_identities(tenant_id, id, backend_id)` |
| `runtime_session_bindings(tenant_id,agent_id)` | `agents(tenant_id,id)` | `FOREIGN KEY (tenant_id, agent_id) REFERENCES agents(tenant_id, id) ON DELETE RESTRICT` |
| `runtime_session_bindings(tenant_id,agent_version_id)` | `agent_versions(tenant_id,id)` | `FOREIGN KEY (tenant_id, agent_version_id) REFERENCES agent_versions(tenant_id, id) ON DELETE RESTRICT` |
| `runtime_session_bindings(backend_id)` | `runtime_backends(id)` | `FOREIGN KEY (backend_id) REFERENCES runtime_backends(id) ON DELETE RESTRICT` |
| `runtime_session_bindings(tenant_id,channel_id)` | `channels(tenant_id,id)` | `FOREIGN KEY (tenant_id, channel_id) REFERENCES channels(tenant_id, id) ON DELETE RESTRICT` |
| `runtime_session_bindings(customer_user_id)` | `users(id)` | `FOREIGN KEY (customer_user_id) REFERENCES users(id) ON DELETE RESTRICT` |
| `runtime_session_bindings(tenant_id,identity_id)` | `runtime_identities(tenant_id,id)` | `FOREIGN KEY (tenant_id, identity_id) REFERENCES runtime_identities(tenant_id, id) ON DELETE RESTRICT` |
| `runtime_session_bindings(started_by_user_id)` | `users(id)` | `FOREIGN KEY (started_by_user_id) REFERENCES users(id) ON DELETE RESTRICT` |
| `runtime_session_bindings(tenant_id,team_member_id)` | `team_members(tenant_id,id)` | `FOREIGN KEY (tenant_id, team_member_id) REFERENCES team_members(tenant_id, id) ON DELETE RESTRICT` |
| `runtime_session_bindings(tenant_id)` | `tenants(id)` | `FOREIGN KEY (tenant_id) REFERENCES tenants(id) ON DELETE RESTRICT` |
| `runtime_session_operations(tenant_id,actor_principal_id)` | `execution_principals(tenant_id,id)` | `FOREIGN KEY (tenant_id, actor_principal_id) REFERENCES execution_principals(tenant_id, id) ON DELETE RESTRICT` |
| `runtime_session_operations(tenant_id,binding_id)` | `runtime_session_bindings(tenant_id,id)` | `FOREIGN KEY (tenant_id, binding_id) REFERENCES runtime_session_bindings(tenant_id, id) ON DELETE RESTRICT` |
| `runtime_session_operations(initiated_by_user_id)` | `users(id)` | `FOREIGN KEY (initiated_by_user_id) REFERENCES users(id) ON DELETE RESTRICT` |
| `runtime_session_operations(tenant_id,result_run_id)` | `agent_runs(tenant_id,id)` | `FOREIGN KEY (tenant_id, result_run_id) REFERENCES agent_runs(tenant_id, id) ON DELETE RESTRICT` |
| `runtime_session_operations(tenant_id)` | `tenants(id)` | `FOREIGN KEY (tenant_id) REFERENCES tenants(id) ON DELETE RESTRICT` |
| `runtime_session_operations(tenant_id,trigger_event_id)` | `ticket_events(tenant_id,id)` | `FOREIGN KEY (tenant_id, trigger_event_id) REFERENCES ticket_events(tenant_id, id) ON DELETE RESTRICT` |
| `sandboxed_components(tenant_id)` | `tenants(id)` | `FOREIGN KEY (tenant_id) REFERENCES tenants(id) ON DELETE RESTRICT` |
| `sandboxed_components(tenant_id,workspace_id)` | `workspaces(tenant_id,id)` | `FOREIGN KEY (tenant_id, workspace_id) REFERENCES workspaces(tenant_id, id) ON DELETE RESTRICT` |
| `scoped_user_roles(granted_by)` | `users(id)` | `FOREIGN KEY (granted_by) REFERENCES users(id) ON DELETE RESTRICT` |
| `scoped_user_roles(tenant_id,membership_id)` | `tenant_memberships(tenant_id,id)` | `FOREIGN KEY (tenant_id, membership_id) REFERENCES tenant_memberships(tenant_id, id) ON DELETE RESTRICT` |
| `scoped_user_roles(tenant_id,scope_id)` | `access_scopes(tenant_id,id)` | `FOREIGN KEY (tenant_id, scope_id) REFERENCES access_scopes(tenant_id, id) ON DELETE RESTRICT` |
| `scoped_user_roles(tenant_id)` | `tenants(id)` | `FOREIGN KEY (tenant_id) REFERENCES tenants(id) ON DELETE RESTRICT` |
| `security_alert_deliveries(recipient_user_id)` | `users(id)` | `FOREIGN KEY (recipient_user_id) REFERENCES users(id)` |
| `security_alert_deliveries(tenant_id,alert_id)` | `security_alerts(tenant_id,id)` | `FOREIGN KEY (tenant_id, alert_id) REFERENCES security_alerts(tenant_id, id)` |
| `security_alert_deliveries(tenant_id,contact_id)` | `security_emergency_contacts(tenant_id,id)` | `FOREIGN KEY (tenant_id, contact_id) REFERENCES security_emergency_contacts(tenant_id, id)` |
| `security_alert_deliveries(tenant_id)` | `tenants(id)` | `FOREIGN KEY (tenant_id) REFERENCES tenants(id)` |
| `security_alerts(created_by)` | `users(id)` | `FOREIGN KEY (created_by) REFERENCES users(id)` |
| `security_alerts(tenant_id)` | `tenants(id)` | `FOREIGN KEY (tenant_id) REFERENCES tenants(id)` |
| `security_alerts(tenant_id,ticket_id)` | `tickets(tenant_id,id)` | `FOREIGN KEY (tenant_id, ticket_id) REFERENCES tickets(tenant_id, id)` |
| `security_cameras(tenant_id,building_id)` | `buildings(tenant_id,id)` | `FOREIGN KEY (tenant_id, building_id) REFERENCES buildings(tenant_id, id)` |
| `security_cameras(tenant_id)` | `tenants(id)` | `FOREIGN KEY (tenant_id) REFERENCES tenants(id)` |
| `security_emergency_contacts(tenant_id,building_id)` | `buildings(tenant_id,id)` | `FOREIGN KEY (tenant_id, building_id) REFERENCES buildings(tenant_id, id)` |
| `security_emergency_contacts(tenant_id)` | `tenants(id)` | `FOREIGN KEY (tenant_id) REFERENCES tenants(id)` |
| `security_emergency_contacts(user_id)` | `users(id)` | `FOREIGN KEY (user_id) REFERENCES users(id)` |
| `service_categories(tenant_id,parent_id)` | `service_categories(tenant_id,id)` | `FOREIGN KEY (tenant_id, parent_id) REFERENCES service_categories(tenant_id, id) ON DELETE RESTRICT` |
| `service_categories(tenant_id)` | `tenants(id)` | `FOREIGN KEY (tenant_id) REFERENCES tenants(id) ON DELETE RESTRICT` |
| `service_interruptions(tenant_id,approval_id)` | `work_approvals(tenant_id,id)` | `FOREIGN KEY (tenant_id, approval_id) REFERENCES work_approvals(tenant_id, id) ON DELETE RESTRICT` |
| `service_interruptions(operated_by)` | `users(id)` | `FOREIGN KEY (operated_by) REFERENCES users(id) ON DELETE RESTRICT` |
| `service_interruptions(tenant_id)` | `tenants(id)` | `FOREIGN KEY (tenant_id) REFERENCES tenants(id) ON DELETE RESTRICT` |
| `service_interruptions(tenant_id,work_order_id)` | `work_orders(tenant_id,id)` | `FOREIGN KEY (tenant_id, work_order_id) REFERENCES work_orders(tenant_id, id) ON DELETE RESTRICT` |
| `sessions(user_id)` | `users(id)` | `FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE` |
| `sites(tenant_id,domain_id)` | `domains(tenant_id,id)` | `FOREIGN KEY (tenant_id, domain_id) REFERENCES domains(tenant_id, id) ON DELETE RESTRICT` |
| `sites(tenant_id)` | `tenants(id)` | `FOREIGN KEY (tenant_id) REFERENCES tenants(id) ON DELETE RESTRICT` |
| `skill_tools(tenant_id,skill_id)` | `skills(tenant_id,id)` | `FOREIGN KEY (tenant_id, skill_id) REFERENCES skills(tenant_id, id) ON DELETE RESTRICT` |
| `skill_tools(tenant_id)` | `tenants(id)` | `FOREIGN KEY (tenant_id) REFERENCES tenants(id) ON DELETE RESTRICT` |
| `skills(owner_user_id)` | `users(id)` | `FOREIGN KEY (owner_user_id) REFERENCES users(id) ON DELETE RESTRICT` |
| `skills(tenant_id)` | `tenants(id)` | `FOREIGN KEY (tenant_id) REFERENCES tenants(id) ON DELETE RESTRICT` |
| `skills(tenant_id,workspace_id)` | `workspaces(tenant_id,id)` | `FOREIGN KEY (tenant_id, workspace_id) REFERENCES workspaces(tenant_id, id) ON DELETE RESTRICT` |
| `sla_policies(tenant_id,category_id)` | `service_categories(tenant_id,id)` | `FOREIGN KEY (tenant_id, category_id) REFERENCES service_categories(tenant_id, id) ON DELETE RESTRICT` |
| `sla_policies(tenant_id,domain_id)` | `domains(tenant_id,id)` | `FOREIGN KEY (tenant_id, domain_id) REFERENCES domains(tenant_id, id) ON DELETE RESTRICT` |
| `sla_policies(tenant_id,management_unit_id)` | `management_units(tenant_id,id)` | `FOREIGN KEY (tenant_id, management_unit_id) REFERENCES management_units(tenant_id, id) ON DELETE RESTRICT` |
| `sla_policies(tenant_id)` | `tenants(id)` | `FOREIGN KEY (tenant_id) REFERENCES tenants(id) ON DELETE RESTRICT` |
| `sso_providers(user_id)` | `users(id)` | `FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE RESTRICT` |
| `staff_profiles(tenant_id,management_unit_id)` | `management_units(tenant_id,id)` | `FOREIGN KEY (tenant_id, management_unit_id) REFERENCES management_units(tenant_id, id) ON DELETE RESTRICT` |
| `staff_profiles(tenant_id)` | `tenants(id)` | `FOREIGN KEY (tenant_id) REFERENCES tenants(id) ON DELETE RESTRICT` |
| `staff_profiles(user_id)` | `users(id)` | `FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE RESTRICT` |
| `staff_shifts(tenant_id,staff_id)` | `staff_profiles(tenant_id,id)` | `FOREIGN KEY (tenant_id, staff_id) REFERENCES staff_profiles(tenant_id, id) ON DELETE RESTRICT` |
| `staff_shifts(tenant_id)` | `tenants(id)` | `FOREIGN KEY (tenant_id) REFERENCES tenants(id) ON DELETE RESTRICT` |
| `staff_specialties(tenant_id,category_id)` | `service_categories(tenant_id,id)` | `FOREIGN KEY (tenant_id, category_id) REFERENCES service_categories(tenant_id, id) ON DELETE RESTRICT` |
| `staff_specialties(tenant_id,staff_id)` | `staff_profiles(tenant_id,id)` | `FOREIGN KEY (tenant_id, staff_id) REFERENCES staff_profiles(tenant_id, id) ON DELETE RESTRICT` |
| `staff_specialties(tenant_id)` | `tenants(id)` | `FOREIGN KEY (tenant_id) REFERENCES tenants(id) ON DELETE RESTRICT` |
| `storage_event_receipts(tenant_id,location_id)` | `storage_locations(tenant_id,id)` | `FOREIGN KEY (tenant_id, location_id) REFERENCES storage_locations(tenant_id, id) ON DELETE RESTRICT` |
| `storage_event_receipts(tenant_id)` | `tenants(id)` | `FOREIGN KEY (tenant_id) REFERENCES tenants(id) ON DELETE RESTRICT` |
| `storage_locations(tenant_id)` | `tenants(id)` | `FOREIGN KEY (tenant_id) REFERENCES tenants(id) ON DELETE RESTRICT` |
| `task_dependencies(tenant_id,depends_on_id)` | `team_tasks(tenant_id,id)` | `FOREIGN KEY (tenant_id, depends_on_id) REFERENCES team_tasks(tenant_id, id) ON DELETE RESTRICT` |
| `task_dependencies(tenant_id,task_id)` | `team_tasks(tenant_id,id)` | `FOREIGN KEY (tenant_id, task_id) REFERENCES team_tasks(tenant_id, id) ON DELETE RESTRICT` |
| `task_dependencies(tenant_id)` | `tenants(id)` | `FOREIGN KEY (tenant_id) REFERENCES tenants(id) ON DELETE RESTRICT` |
| `team_mailbox(tenant_id,recipient_member_id)` | `team_members(tenant_id,id)` | `FOREIGN KEY (tenant_id, recipient_member_id) REFERENCES team_members(tenant_id, id) ON DELETE RESTRICT` |
| `team_mailbox(tenant_id,sender_member_id)` | `team_members(tenant_id,id)` | `FOREIGN KEY (tenant_id, sender_member_id) REFERENCES team_members(tenant_id, id) ON DELETE RESTRICT` |
| `team_mailbox(tenant_id,task_id)` | `team_tasks(tenant_id,id)` | `FOREIGN KEY (tenant_id, task_id) REFERENCES team_tasks(tenant_id, id) ON DELETE RESTRICT` |
| `team_mailbox(tenant_id,team_id)` | `agent_teams(tenant_id,id)` | `FOREIGN KEY (tenant_id, team_id) REFERENCES agent_teams(tenant_id, id) ON DELETE RESTRICT` |
| `team_mailbox(tenant_id)` | `tenants(id)` | `FOREIGN KEY (tenant_id) REFERENCES tenants(id) ON DELETE RESTRICT` |
| `team_members(tenant_id,agent_id)` | `agents(tenant_id,id)` | `FOREIGN KEY (tenant_id, agent_id) REFERENCES agents(tenant_id, id) ON DELETE RESTRICT` |
| `team_members(tenant_id,binding_id)` | `runtime_session_bindings(tenant_id,id)` | `FOREIGN KEY (tenant_id, binding_id) REFERENCES runtime_session_bindings(tenant_id, id) ON DELETE RESTRICT` |
| `team_members(tenant_id,team_id)` | `agent_teams(tenant_id,id)` | `FOREIGN KEY (tenant_id, team_id) REFERENCES agent_teams(tenant_id, id) ON DELETE RESTRICT` |
| `team_members(tenant_id)` | `tenants(id)` | `FOREIGN KEY (tenant_id) REFERENCES tenants(id) ON DELETE RESTRICT` |
| `team_members(tenant_id,version_id)` | `agent_versions(tenant_id,id)` | `FOREIGN KEY (tenant_id, version_id) REFERENCES agent_versions(tenant_id, id) ON DELETE RESTRICT` |
| `team_tasks(tenant_id,assigned_member_id)` | `team_members(tenant_id,id)` | `FOREIGN KEY (tenant_id, assigned_member_id) REFERENCES team_members(tenant_id, id) ON DELETE RESTRICT` |
| `team_tasks(tenant_id,parent_task_id)` | `team_tasks(tenant_id,id)` | `FOREIGN KEY (tenant_id, parent_task_id) REFERENCES team_tasks(tenant_id, id) ON DELETE RESTRICT` |
| `team_tasks(tenant_id,team_id)` | `agent_teams(tenant_id,id)` | `FOREIGN KEY (tenant_id, team_id) REFERENCES agent_teams(tenant_id, id) ON DELETE RESTRICT` |
| `team_tasks(tenant_id)` | `tenants(id)` | `FOREIGN KEY (tenant_id) REFERENCES tenants(id) ON DELETE RESTRICT` |
| `team_tasks(tenant_id,ticket_id)` | `tickets(tenant_id,id)` | `FOREIGN KEY (tenant_id, ticket_id) REFERENCES tickets(tenant_id, id) ON DELETE RESTRICT` |
| `tenant_memberships(tenant_id)` | `tenants(id)` | `FOREIGN KEY (tenant_id) REFERENCES tenants(id) ON DELETE RESTRICT` |
| `tenant_memberships(user_id)` | `users(id)` | `FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE RESTRICT` |
| `ticket_assessment_evidence(tenant_id,assessment_id)` | `ticket_assessments(tenant_id,id)` | `FOREIGN KEY (tenant_id, assessment_id) REFERENCES ticket_assessments(tenant_id, id) ON DELETE RESTRICT` |
| `ticket_assessment_evidence(tenant_id,event_id)` | `ticket_events(tenant_id,id)` | `FOREIGN KEY (tenant_id, event_id) REFERENCES ticket_events(tenant_id, id) ON DELETE RESTRICT` |
| `ticket_assessment_evidence(tenant_id,evidence_item_id)` | `evidence_items(tenant_id,id)` | `FOREIGN KEY (tenant_id, evidence_item_id) REFERENCES evidence_items(tenant_id, id) ON DELETE RESTRICT` |
| `ticket_assessment_evidence(tenant_id,message_id)` | `messages(tenant_id,id)` | `FOREIGN KEY (tenant_id, message_id) REFERENCES messages(tenant_id, id) ON DELETE RESTRICT` |
| `ticket_assessment_evidence(tenant_id,object_id)` | `file_objects(tenant_id,id)` | `FOREIGN KEY (tenant_id, object_id) REFERENCES file_objects(tenant_id, id) ON DELETE RESTRICT` |
| `ticket_assessment_evidence(tenant_id)` | `tenants(id)` | `FOREIGN KEY (tenant_id) REFERENCES tenants(id) ON DELETE RESTRICT` |
| `ticket_assessments(assessor_user_id)` | `users(id)` | `FOREIGN KEY (assessor_user_id) REFERENCES users(id) ON DELETE RESTRICT` |
| `ticket_assessments(tenant_id,basis_decision_id)` | `ticket_triage_decisions(tenant_id,id)` | `FOREIGN KEY (tenant_id, basis_decision_id) REFERENCES ticket_triage_decisions(tenant_id, id) ON DELETE RESTRICT` |
| `ticket_assessments(tenant_id,source_run_id)` | `agent_runs(tenant_id,id)` | `FOREIGN KEY (tenant_id, source_run_id) REFERENCES agent_runs(tenant_id, id) ON DELETE RESTRICT` |
| `ticket_assessments(tenant_id,supersedes_assessment_id)` | `ticket_assessments(tenant_id,id)` | `FOREIGN KEY (tenant_id, supersedes_assessment_id) REFERENCES ticket_assessments(tenant_id, id) ON DELETE RESTRICT` |
| `ticket_assessments(tenant_id)` | `tenants(id)` | `FOREIGN KEY (tenant_id) REFERENCES tenants(id) ON DELETE RESTRICT` |
| `ticket_assessments(tenant_id,ticket_id)` | `tickets(tenant_id,id)` | `FOREIGN KEY (tenant_id, ticket_id) REFERENCES tickets(tenant_id, id) ON DELETE RESTRICT` |
| `ticket_escalations(acknowledged_by)` | `users(id)` | `FOREIGN KEY (acknowledged_by) REFERENCES users(id) ON DELETE RESTRICT` |
| `ticket_escalations(tenant_id,assessment_id)` | `ticket_assessments(tenant_id,id)` | `FOREIGN KEY (tenant_id, assessment_id) REFERENCES ticket_assessments(tenant_id, id) ON DELETE RESTRICT` |
| `ticket_escalations(tenant_id,decision_id)` | `ticket_triage_decisions(tenant_id,id)` | `FOREIGN KEY (tenant_id, decision_id) REFERENCES ticket_triage_decisions(tenant_id, id) ON DELETE RESTRICT` |
| `ticket_escalations(tenant_id,required_scope_id)` | `access_scopes(tenant_id,id)` | `FOREIGN KEY (tenant_id, required_scope_id) REFERENCES access_scopes(tenant_id, id) ON DELETE RESTRICT` |
| `ticket_escalations(resolved_by)` | `users(id)` | `FOREIGN KEY (resolved_by) REFERENCES users(id) ON DELETE RESTRICT` |
| `ticket_escalations(tenant_id,review_id)` | `ticket_triage_reviews(tenant_id,id)` | `FOREIGN KEY (tenant_id, review_id) REFERENCES ticket_triage_reviews(tenant_id, id) ON DELETE RESTRICT` |
| `ticket_escalations(tenant_id,sla_cycle_id)` | `ticket_sla_cycles(tenant_id,id)` | `FOREIGN KEY (tenant_id, sla_cycle_id) REFERENCES ticket_sla_cycles(tenant_id, id) ON DELETE RESTRICT` |
| `ticket_escalations(tenant_id)` | `tenants(id)` | `FOREIGN KEY (tenant_id) REFERENCES tenants(id) ON DELETE RESTRICT` |
| `ticket_escalations(tenant_id,ticket_id)` | `tickets(tenant_id,id)` | `FOREIGN KEY (tenant_id, ticket_id) REFERENCES tickets(tenant_id, id) ON DELETE RESTRICT` |
| `ticket_escalations(tenant_id,work_order_id)` | `work_orders(tenant_id,id)` | `FOREIGN KEY (tenant_id, work_order_id) REFERENCES work_orders(tenant_id, id) ON DELETE RESTRICT` |
| `ticket_events(tenant_id,actor_agent_id)` | `agents(tenant_id,id)` | `FOREIGN KEY (tenant_id, actor_agent_id) REFERENCES agents(tenant_id, id) ON DELETE RESTRICT` |
| `ticket_events(actor_user_id)` | `users(id)` | `FOREIGN KEY (actor_user_id) REFERENCES users(id) ON DELETE RESTRICT` |
| `ticket_events(tenant_id,causation_event_id)` | `ticket_events(tenant_id,id)` | `FOREIGN KEY (tenant_id, causation_event_id) REFERENCES ticket_events(tenant_id, id) ON DELETE RESTRICT` |
| `ticket_events(tenant_id)` | `tenants(id)` | `FOREIGN KEY (tenant_id) REFERENCES tenants(id) ON DELETE RESTRICT` |
| `ticket_events(tenant_id,ticket_id)` | `tickets(tenant_id,id)` | `FOREIGN KEY (tenant_id, ticket_id) REFERENCES tickets(tenant_id, id) ON DELETE RESTRICT` |
| `ticket_files(tenant_id,event_id)` | `ticket_events(tenant_id,id)` | `FOREIGN KEY (tenant_id, event_id) REFERENCES ticket_events(tenant_id, id) ON DELETE RESTRICT` |
| `ticket_files(tenant_id,evidence_id)` | `evidence_items(tenant_id,id)` | `FOREIGN KEY (tenant_id, evidence_id) REFERENCES evidence_items(tenant_id, id) ON DELETE RESTRICT` |
| `ticket_files(tenant_id,file_id)` | `files(tenant_id,id)` | `FOREIGN KEY (tenant_id, file_id) REFERENCES files(tenant_id, id) ON DELETE RESTRICT` |
| `ticket_files(tenant_id)` | `tenants(id)` | `FOREIGN KEY (tenant_id) REFERENCES tenants(id) ON DELETE RESTRICT` |
| `ticket_files(tenant_id,ticket_id)` | `tickets(tenant_id,id)` | `FOREIGN KEY (tenant_id, ticket_id) REFERENCES tickets(tenant_id, id) ON DELETE RESTRICT` |
| `ticket_files(uploaded_by)` | `users(id)` | `FOREIGN KEY (uploaded_by) REFERENCES users(id) ON DELETE RESTRICT` |
| `ticket_reviews(tenant_id,assignment_id)` | `work_assignments(tenant_id,id)` | `FOREIGN KEY (tenant_id, assignment_id) REFERENCES work_assignments(tenant_id, id) ON DELETE RESTRICT` |
| `ticket_reviews(reviewer_user_id)` | `users(id)` | `FOREIGN KEY (reviewer_user_id) REFERENCES users(id) ON DELETE RESTRICT` |
| `ticket_reviews(tenant_id,staff_id)` | `staff_profiles(tenant_id,id)` | `FOREIGN KEY (tenant_id, staff_id) REFERENCES staff_profiles(tenant_id, id) ON DELETE RESTRICT` |
| `ticket_reviews(tenant_id)` | `tenants(id)` | `FOREIGN KEY (tenant_id) REFERENCES tenants(id) ON DELETE RESTRICT` |
| `ticket_reviews(tenant_id,ticket_id)` | `tickets(tenant_id,id)` | `FOREIGN KEY (tenant_id, ticket_id) REFERENCES tickets(tenant_id, id) ON DELETE RESTRICT` |
| `ticket_routing_history(tenant_id,ack_event_id)` | `ticket_events(tenant_id,id)` | `FOREIGN KEY (tenant_id, ack_event_id) REFERENCES ticket_events(tenant_id, id) ON DELETE RESTRICT` |
| `ticket_routing_history(tenant_id,from_management_id)` | `management_units(tenant_id,id)` | `FOREIGN KEY (tenant_id, from_management_id) REFERENCES management_units(tenant_id, id) ON DELETE RESTRICT` |
| `ticket_routing_history(tenant_id,team_id)` | `agent_teams(tenant_id,id)` | `FOREIGN KEY (tenant_id, team_id) REFERENCES agent_teams(tenant_id, id) ON DELETE RESTRICT` |
| `ticket_routing_history(tenant_id)` | `tenants(id)` | `FOREIGN KEY (tenant_id) REFERENCES tenants(id) ON DELETE RESTRICT` |
| `ticket_routing_history(tenant_id,ticket_id)` | `tickets(tenant_id,id)` | `FOREIGN KEY (tenant_id, ticket_id) REFERENCES tickets(tenant_id, id) ON DELETE RESTRICT` |
| `ticket_routing_history(tenant_id,to_management_id)` | `management_units(tenant_id,id)` | `FOREIGN KEY (tenant_id, to_management_id) REFERENCES management_units(tenant_id, id) ON DELETE RESTRICT` |
| `ticket_sla_adjustments(authorized_by)` | `users(id)` | `FOREIGN KEY (authorized_by) REFERENCES users(id) ON DELETE RESTRICT` |
| `ticket_sla_adjustments(tenant_id,cycle_id)` | `ticket_sla_cycles(tenant_id,id)` | `FOREIGN KEY (tenant_id, cycle_id) REFERENCES ticket_sla_cycles(tenant_id, id) ON DELETE RESTRICT` |
| `ticket_sla_adjustments(tenant_id,decision_id)` | `ticket_triage_decisions(tenant_id,id)` | `FOREIGN KEY (tenant_id, decision_id) REFERENCES ticket_triage_decisions(tenant_id, id) ON DELETE RESTRICT` |
| `ticket_sla_adjustments(tenant_id,target_policy_id)` | `sla_policies(tenant_id,id)` | `FOREIGN KEY (tenant_id, target_policy_id) REFERENCES sla_policies(tenant_id, id) ON DELETE RESTRICT` |
| `ticket_sla_adjustments(tenant_id)` | `tenants(id)` | `FOREIGN KEY (tenant_id) REFERENCES tenants(id) ON DELETE RESTRICT` |
| `ticket_sla_cycles(tenant_id,initial_decision_id)` | `ticket_triage_decisions(tenant_id,id)` | `FOREIGN KEY (tenant_id, initial_decision_id) REFERENCES ticket_triage_decisions(tenant_id, id) ON DELETE RESTRICT` |
| `ticket_sla_cycles(tenant_id,initial_policy_id)` | `sla_policies(tenant_id,id)` | `FOREIGN KEY (tenant_id, initial_policy_id) REFERENCES sla_policies(tenant_id, id) ON DELETE RESTRICT` |
| `ticket_sla_cycles(tenant_id)` | `tenants(id)` | `FOREIGN KEY (tenant_id) REFERENCES tenants(id) ON DELETE RESTRICT` |
| `ticket_sla_cycles(tenant_id,ticket_id)` | `tickets(tenant_id,id)` | `FOREIGN KEY (tenant_id, ticket_id) REFERENCES tickets(tenant_id, id) ON DELETE RESTRICT` |
| `ticket_triage_decisions(approved_by)` | `users(id)` | `FOREIGN KEY (approved_by) REFERENCES users(id) ON DELETE RESTRICT` |
| `ticket_triage_decisions(tenant_id,assessment_id)` | `ticket_assessments(tenant_id,id)` | `FOREIGN KEY (tenant_id, assessment_id) REFERENCES ticket_assessments(tenant_id, id) ON DELETE RESTRICT` |
| `ticket_triage_decisions(tenant_id,matched_rule_id)` | `triage_rules(tenant_id,id)` | `FOREIGN KEY (tenant_id, matched_rule_id) REFERENCES triage_rules(tenant_id, id) ON DELETE RESTRICT` |
| `ticket_triage_decisions(tenant_id,policy_binding_id)` | `triage_policy_bindings(tenant_id,id)` | `FOREIGN KEY (tenant_id, policy_binding_id) REFERENCES triage_policy_bindings(tenant_id, id) ON DELETE RESTRICT` |
| `ticket_triage_decisions(tenant_id,policy_version_id)` | `triage_policy_versions(tenant_id,id)` | `FOREIGN KEY (tenant_id, policy_version_id) REFERENCES triage_policy_versions(tenant_id, id) ON DELETE RESTRICT` |
| `ticket_triage_decisions(tenant_id,previous_applied_id)` | `ticket_triage_decisions(tenant_id,id)` | `FOREIGN KEY (tenant_id, previous_applied_id) REFERENCES ticket_triage_decisions(tenant_id, id) ON DELETE RESTRICT` |
| `ticket_triage_decisions(tenant_id,review_id)` | `ticket_triage_reviews(tenant_id,id)` | `FOREIGN KEY (tenant_id, review_id) REFERENCES ticket_triage_reviews(tenant_id, id) ON DELETE RESTRICT` |
| `ticket_triage_decisions(tenant_id)` | `tenants(id)` | `FOREIGN KEY (tenant_id) REFERENCES tenants(id) ON DELETE RESTRICT` |
| `ticket_triage_decisions(tenant_id,ticket_id)` | `tickets(tenant_id,id)` | `FOREIGN KEY (tenant_id, ticket_id) REFERENCES tickets(tenant_id, id) ON DELETE RESTRICT` |
| `ticket_triage_reviews(tenant_id,assessment_id)` | `ticket_assessments(tenant_id,id)` | `FOREIGN KEY (tenant_id, assessment_id) REFERENCES ticket_assessments(tenant_id, id) ON DELETE RESTRICT` |
| `ticket_triage_reviews(claimed_by)` | `users(id)` | `FOREIGN KEY (claimed_by) REFERENCES users(id) ON DELETE RESTRICT` |
| `ticket_triage_reviews(decided_by)` | `users(id)` | `FOREIGN KEY (decided_by) REFERENCES users(id) ON DELETE RESTRICT` |
| `ticket_triage_reviews(tenant_id,pending_decision_id)` | `ticket_triage_decisions(tenant_id,id)` | `FOREIGN KEY (tenant_id, pending_decision_id) REFERENCES ticket_triage_decisions(tenant_id, id) ON DELETE RESTRICT` |
| `ticket_triage_reviews(tenant_id,required_scope_id)` | `access_scopes(tenant_id,id)` | `FOREIGN KEY (tenant_id, required_scope_id) REFERENCES access_scopes(tenant_id, id) ON DELETE RESTRICT` |
| `ticket_triage_reviews(tenant_id,result_decision_id)` | `ticket_triage_decisions(tenant_id,id)` | `FOREIGN KEY (tenant_id, result_decision_id) REFERENCES ticket_triage_decisions(tenant_id, id) ON DELETE RESTRICT` |
| `ticket_triage_reviews(tenant_id)` | `tenants(id)` | `FOREIGN KEY (tenant_id) REFERENCES tenants(id) ON DELETE RESTRICT` |
| `ticket_triage_reviews(tenant_id,ticket_id)` | `tickets(tenant_id,id)` | `FOREIGN KEY (tenant_id, ticket_id) REFERENCES tickets(tenant_id, id) ON DELETE RESTRICT` |
| `tickets(tenant_id,active_sla_cycle_id)` | `ticket_sla_cycles(tenant_id,id)` | `FOREIGN KEY (tenant_id, active_sla_cycle_id) REFERENCES ticket_sla_cycles(tenant_id, id) ON DELETE RESTRICT` |
| `tickets(tenant_id,assigned_team_id)` | `agent_teams(tenant_id,id)` | `FOREIGN KEY (tenant_id, assigned_team_id) REFERENCES agent_teams(tenant_id, id) ON DELETE RESTRICT` |
| `tickets(tenant_id,building_id)` | `buildings(tenant_id,id)` | `FOREIGN KEY (tenant_id, building_id) REFERENCES buildings(tenant_id, id) ON DELETE RESTRICT` |
| `tickets(tenant_id,category_id)` | `service_categories(tenant_id,id)` | `FOREIGN KEY (tenant_id, category_id) REFERENCES service_categories(tenant_id, id) ON DELETE RESTRICT` |
| `tickets(tenant_id,channel_id)` | `channels(tenant_id,id)` | `FOREIGN KEY (tenant_id, channel_id) REFERENCES channels(tenant_id, id) ON DELETE RESTRICT` |
| `tickets(tenant_id,coverage_id)` | `management_coverage(tenant_id,id)` | `FOREIGN KEY (tenant_id, coverage_id) REFERENCES management_coverage(tenant_id, id) ON DELETE RESTRICT` |
| `tickets(tenant_id,current_triage_decision_id)` | `ticket_triage_decisions(tenant_id,id)` | `FOREIGN KEY (tenant_id, current_triage_decision_id) REFERENCES ticket_triage_decisions(tenant_id, id) ON DELETE RESTRICT` |
| `tickets(tenant_id,domain_id)` | `domains(tenant_id,id)` | `FOREIGN KEY (tenant_id, domain_id) REFERENCES domains(tenant_id, id) ON DELETE RESTRICT` |
| `tickets(tenant_id,incident_type_id)` | `incident_types(tenant_id,id)` | `FOREIGN KEY (tenant_id, incident_type_id) REFERENCES incident_types(tenant_id, id) ON DELETE RESTRICT` |
| `tickets(tenant_id,management_unit_id)` | `management_units(tenant_id,id)` | `FOREIGN KEY (tenant_id, management_unit_id) REFERENCES management_units(tenant_id, id) ON DELETE RESTRICT` |
| `tickets(requester_user_id)` | `users(id)` | `FOREIGN KEY (requester_user_id) REFERENCES users(id) ON DELETE RESTRICT` |
| `tickets(tenant_id,site_id)` | `sites(tenant_id,id)` | `FOREIGN KEY (tenant_id, site_id) REFERENCES sites(tenant_id, id) ON DELETE RESTRICT` |
| `tickets(tenant_id,sla_policy_id)` | `sla_policies(tenant_id,id)` | `FOREIGN KEY (tenant_id, sla_policy_id) REFERENCES sla_policies(tenant_id, id) ON DELETE RESTRICT` |
| `tickets(tenant_id)` | `tenants(id)` | `FOREIGN KEY (tenant_id) REFERENCES tenants(id) ON DELETE RESTRICT` |
| `tickets(tenant_id,unit_id)` | `units(tenant_id,id)` | `FOREIGN KEY (tenant_id, unit_id) REFERENCES units(tenant_id, id) ON DELETE RESTRICT` |
| `tickets(tenant_id,zone_id)` | `zones(tenant_id,id)` | `FOREIGN KEY (tenant_id, zone_id) REFERENCES zones(tenant_id, id) ON DELETE RESTRICT` |
| `triage_policy_bindings(tenant_id,category_id)` | `service_categories(tenant_id,id)` | `FOREIGN KEY (tenant_id, category_id) REFERENCES service_categories(tenant_id, id) ON DELETE RESTRICT` |
| `triage_policy_bindings(configured_by)` | `users(id)` | `FOREIGN KEY (configured_by) REFERENCES users(id) ON DELETE RESTRICT` |
| `triage_policy_bindings(tenant_id,domain_id)` | `domains(tenant_id,id)` | `FOREIGN KEY (tenant_id, domain_id) REFERENCES domains(tenant_id, id) ON DELETE RESTRICT` |
| `triage_policy_bindings(tenant_id,policy_version_id)` | `triage_policy_versions(tenant_id,id)` | `FOREIGN KEY (tenant_id, policy_version_id) REFERENCES triage_policy_versions(tenant_id, id) ON DELETE RESTRICT` |
| `triage_policy_bindings(tenant_id,scope_id)` | `access_scopes(tenant_id,id)` | `FOREIGN KEY (tenant_id, scope_id) REFERENCES access_scopes(tenant_id, id) ON DELETE RESTRICT` |
| `triage_policy_bindings(tenant_id)` | `tenants(id)` | `FOREIGN KEY (tenant_id) REFERENCES tenants(id) ON DELETE RESTRICT` |
| `triage_policy_versions(created_by)` | `users(id)` | `FOREIGN KEY (created_by) REFERENCES users(id) ON DELETE RESTRICT` |
| `triage_policy_versions(tenant_id,domain_id)` | `domains(tenant_id,id)` | `FOREIGN KEY (tenant_id, domain_id) REFERENCES domains(tenant_id, id) ON DELETE RESTRICT` |
| `triage_policy_versions(published_by)` | `users(id)` | `FOREIGN KEY (published_by) REFERENCES users(id) ON DELETE RESTRICT` |
| `triage_policy_versions(tenant_id)` | `tenants(id)` | `FOREIGN KEY (tenant_id) REFERENCES tenants(id) ON DELETE RESTRICT` |
| `triage_rules(tenant_id,policy_version_id)` | `triage_policy_versions(tenant_id,id)` | `FOREIGN KEY (tenant_id, policy_version_id) REFERENCES triage_policy_versions(tenant_id, id) ON DELETE RESTRICT` |
| `triage_rules(tenant_id)` | `tenants(id)` | `FOREIGN KEY (tenant_id) REFERENCES tenants(id) ON DELETE RESTRICT` |
| `unit_residents(tenant_id)` | `tenants(id)` | `FOREIGN KEY (tenant_id) REFERENCES tenants(id) ON DELETE RESTRICT` |
| `unit_residents(tenant_id,unit_id)` | `units(tenant_id,id)` | `FOREIGN KEY (tenant_id, unit_id) REFERENCES units(tenant_id, id) ON DELETE RESTRICT` |
| `unit_residents(user_id)` | `users(id)` | `FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE RESTRICT` |
| `unit_residents(verified_by)` | `users(id)` | `FOREIGN KEY (verified_by) REFERENCES users(id) ON DELETE RESTRICT` |
| `units(tenant_id,building_id)` | `buildings(tenant_id,id)` | `FOREIGN KEY (tenant_id, building_id) REFERENCES buildings(tenant_id, id) ON DELETE RESTRICT` |
| `units(tenant_id,site_id)` | `sites(tenant_id,id)` | `FOREIGN KEY (tenant_id, site_id) REFERENCES sites(tenant_id, id) ON DELETE RESTRICT` |
| `units(tenant_id)` | `tenants(id)` | `FOREIGN KEY (tenant_id) REFERENCES tenants(id) ON DELETE RESTRICT` |
| `units(tenant_id,zone_id)` | `zones(tenant_id,id)` | `FOREIGN KEY (tenant_id, zone_id) REFERENCES zones(tenant_id, id) ON DELETE RESTRICT` |
| `user_instructions(user_id)` | `users(id)` | `FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE` |
| `user_roles(user_id)` | `users(id)` | `FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE RESTRICT` |
| `vh_agent_reviews(decided_by)` | `users(id)` | `FOREIGN KEY (decided_by) REFERENCES users(id)` |
| `vh_agent_reviews(submitted_by)` | `users(id)` | `FOREIGN KEY (submitted_by) REFERENCES users(id)` |
| `vh_agent_reviews(tenant_id,agent_id)` | `agents(tenant_id,id)` | `FOREIGN KEY (tenant_id, agent_id) REFERENCES agents(tenant_id, id)` |
| `vh_agent_reviews(tenant_id)` | `tenants(id)` | `FOREIGN KEY (tenant_id) REFERENCES tenants(id)` |
| `vh_assets(tenant_id,building_id)` | `buildings(tenant_id,id)` | `FOREIGN KEY (tenant_id, building_id) REFERENCES buildings(tenant_id, id)` |
| `vh_assets(tenant_id)` | `tenants(id)` | `FOREIGN KEY (tenant_id) REFERENCES tenants(id)` |
| `vh_budget_approvals(decided_by)` | `users(id)` | `FOREIGN KEY (decided_by) REFERENCES users(id)` |
| `vh_budget_approvals(requested_by)` | `users(id)` | `FOREIGN KEY (requested_by) REFERENCES users(id)` |
| `vh_budget_approvals(reviewer_user_id)` | `users(id)` | `FOREIGN KEY (reviewer_user_id) REFERENCES users(id)` |
| `vh_budget_approvals(tenant_id,work_order_id)` | `work_orders(tenant_id,id)` | `FOREIGN KEY (tenant_id, work_order_id) REFERENCES work_orders(tenant_id, id)` |
| `vh_cleaning_plans(tenant_id,work_order_id)` | `work_orders(tenant_id,id)` | `FOREIGN KEY (tenant_id, work_order_id) REFERENCES work_orders(tenant_id, id)` |
| `vh_cleaning_plans(updated_by)` | `users(id)` | `FOREIGN KEY (updated_by) REFERENCES users(id)` |
| `vh_command_receipt(tenant_id)` | `tenants(id)` | `FOREIGN KEY (tenant_id) REFERENCES tenants(id)` |
| `vh_contractor_updates(tenant_id,work_order_id)` | `work_orders(tenant_id,id)` | `FOREIGN KEY (tenant_id, work_order_id) REFERENCES work_orders(tenant_id, id)` |
| `vh_contractor_updates(updated_by)` | `users(id)` | `FOREIGN KEY (updated_by) REFERENCES users(id)` |
| `vh_conversation_uploads(requested_by)` | `users(id)` | `FOREIGN KEY (requested_by) REFERENCES users(id)` |
| `vh_conversation_uploads(tenant_id,channel_id)` | `channels(tenant_id,id)` | `FOREIGN KEY (tenant_id, channel_id) REFERENCES channels(tenant_id, id)` |
| `vh_conversation_uploads(tenant_id,file_id)` | `files(tenant_id,id)` | `FOREIGN KEY (tenant_id, file_id) REFERENCES files(tenant_id, id)` |
| `vh_conversation_uploads(tenant_id)` | `tenants(id)` | `FOREIGN KEY (tenant_id) REFERENCES tenants(id)` |
| `vh_conversation_uploads(tenant_id,location_id)` | `storage_locations(tenant_id,id)` | `FOREIGN KEY (tenant_id, location_id) REFERENCES storage_locations(tenant_id, id)` |
| `vh_maintenance_records(confirmed_by)` | `users(id)` | `FOREIGN KEY (confirmed_by) REFERENCES users(id)` |
| `vh_maintenance_records(tenant_id,asset_id)` | `vh_assets(tenant_id,id)` | `FOREIGN KEY (tenant_id, asset_id) REFERENCES vh_assets(tenant_id, id)` |
| `vh_maintenance_records(tenant_id)` | `tenants(id)` | `FOREIGN KEY (tenant_id) REFERENCES tenants(id)` |
| `vh_maintenance_records(tenant_id,work_order_id)` | `work_orders(tenant_id,id)` | `FOREIGN KEY (tenant_id, work_order_id) REFERENCES work_orders(tenant_id, id)` |
| `vh_operational_requests(decided_by)` | `users(id)` | `FOREIGN KEY (decided_by) REFERENCES users(id)` |
| `vh_operational_requests(requested_by)` | `users(id)` | `FOREIGN KEY (requested_by) REFERENCES users(id)` |
| `vh_operational_requests(tenant_id)` | `tenants(id)` | `FOREIGN KEY (tenant_id) REFERENCES tenants(id)` |
| `vh_operational_requests(tenant_id,work_order_id)` | `work_orders(tenant_id,id)` | `FOREIGN KEY (tenant_id, work_order_id) REFERENCES work_orders(tenant_id, id)` |
| `vh_qc_redo_orders(created_by)` | `users(id)` | `FOREIGN KEY (created_by) REFERENCES users(id)` |
| `vh_qc_redo_orders(tenant_id,qc_result_id)` | `vh_qc_results(tenant_id,id)` | `FOREIGN KEY (tenant_id, qc_result_id) REFERENCES vh_qc_results(tenant_id, id)` |
| `vh_qc_redo_orders(tenant_id,redo_work_order_id)` | `work_orders(tenant_id,id)` | `FOREIGN KEY (tenant_id, redo_work_order_id) REFERENCES work_orders(tenant_id, id)` |
| `vh_qc_redo_orders(tenant_id,source_work_order_id)` | `work_orders(tenant_id,id)` | `FOREIGN KEY (tenant_id, source_work_order_id) REFERENCES work_orders(tenant_id, id)` |
| `vh_qc_results(checked_by)` | `users(id)` | `FOREIGN KEY (checked_by) REFERENCES users(id)` |
| `vh_qc_results(tenant_id,work_order_id)` | `work_orders(tenant_id,id)` | `FOREIGN KEY (tenant_id, work_order_id) REFERENCES work_orders(tenant_id, id)` |
| `vh_reception_supervisor_messages(tenant_id,created_by_agent_id)` | `agents(tenant_id,id)` | `FOREIGN KEY (tenant_id, created_by_agent_id) REFERENCES agents(tenant_id, id) ON DELETE RESTRICT` |
| `vh_reception_supervisor_messages(created_by)` | `users(id)` | `FOREIGN KEY (created_by) REFERENCES users(id) ON DELETE RESTRICT` |
| `vh_reception_supervisor_messages(tenant_id,team_id)` | `agent_teams(tenant_id,id)` | `FOREIGN KEY (tenant_id, team_id) REFERENCES agent_teams(tenant_id, id) ON DELETE RESTRICT` |
| `vh_reception_supervisor_messages(tenant_id)` | `tenants(id)` | `FOREIGN KEY (tenant_id) REFERENCES tenants(id) ON DELETE RESTRICT` |
| `vh_reception_supervisor_messages(tenant_id,ticket_id)` | `tickets(tenant_id,id)` | `FOREIGN KEY (tenant_id, ticket_id) REFERENCES tickets(tenant_id, id) ON DELETE RESTRICT` |
| `vh_reception_supervisor_pending(tenant_id,plan_id)` | `vh_ticket_plans(tenant_id,id)` | `FOREIGN KEY (tenant_id, plan_id) REFERENCES vh_ticket_plans(tenant_id, id) ON DELETE RESTRICT` |
| `vh_reception_supervisor_pending(tenant_id,team_id)` | `agent_teams(tenant_id,id)` | `FOREIGN KEY (tenant_id, team_id) REFERENCES agent_teams(tenant_id, id) ON DELETE RESTRICT` |
| `vh_reception_supervisor_pending(tenant_id)` | `tenants(id)` | `FOREIGN KEY (tenant_id) REFERENCES tenants(id) ON DELETE RESTRICT` |
| `vh_reception_supervisor_pending(tenant_id,ticket_id)` | `tickets(tenant_id,id)` | `FOREIGN KEY (tenant_id, ticket_id) REFERENCES tickets(tenant_id, id) ON DELETE RESTRICT` |
| `vh_report_exports(created_by)` | `users(id)` | `FOREIGN KEY (created_by) REFERENCES users(id)` |
| `vh_report_exports(tenant_id,building_id)` | `buildings(tenant_id,id)` | `FOREIGN KEY (tenant_id, building_id) REFERENCES buildings(tenant_id, id)` |
| `vh_report_exports(tenant_id)` | `tenants(id)` | `FOREIGN KEY (tenant_id) REFERENCES tenants(id)` |
| `vh_resident_case_tickets(linked_by)` | `users(id)` | `FOREIGN KEY (linked_by) REFERENCES users(id)` |
| `vh_resident_case_tickets(tenant_id,case_id)` | `vh_resident_cases(tenant_id,id)` | `FOREIGN KEY (tenant_id, case_id) REFERENCES vh_resident_cases(tenant_id, id)` |
| `vh_resident_case_tickets(tenant_id)` | `tenants(id)` | `FOREIGN KEY (tenant_id) REFERENCES tenants(id)` |
| `vh_resident_case_tickets(tenant_id,ticket_id)` | `tickets(tenant_id,id)` | `FOREIGN KEY (tenant_id, ticket_id) REFERENCES tickets(tenant_id, id)` |
| `vh_resident_cases(requester_user_id)` | `users(id)` | `FOREIGN KEY (requester_user_id) REFERENCES users(id)` |
| `vh_resident_cases(tenant_id,id,current_resolution_id)` | `vh_resident_resolutions(tenant_id,case_id,id)` | `FOREIGN KEY (tenant_id, id, current_resolution_id) REFERENCES vh_resident_resolutions(tenant_id, case_id, id)` |
| `vh_resident_cases(tenant_id,building_id)` | `buildings(tenant_id,id)` | `FOREIGN KEY (tenant_id, building_id) REFERENCES buildings(tenant_id, id)` |
| `vh_resident_cases(tenant_id,channel_id)` | `channels(tenant_id,id)` | `FOREIGN KEY (tenant_id, channel_id) REFERENCES channels(tenant_id, id)` |
| `vh_resident_cases(tenant_id,domain_id)` | `domains(tenant_id,id)` | `FOREIGN KEY (tenant_id, domain_id) REFERENCES domains(tenant_id, id)` |
| `vh_resident_cases(tenant_id)` | `tenants(id)` | `FOREIGN KEY (tenant_id) REFERENCES tenants(id)` |
| `vh_resident_cases(tenant_id,site_id)` | `sites(tenant_id,id)` | `FOREIGN KEY (tenant_id, site_id) REFERENCES sites(tenant_id, id)` |
| `vh_resident_cases(tenant_id,unit_id)` | `units(tenant_id,id)` | `FOREIGN KEY (tenant_id, unit_id) REFERENCES units(tenant_id, id)` |
| `vh_resident_command_receipts(actor_id)` | `users(id)` | `FOREIGN KEY (actor_id) REFERENCES users(id)` |
| `vh_resident_command_receipts(tenant_id)` | `tenants(id)` | `FOREIGN KEY (tenant_id) REFERENCES tenants(id)` |
| `vh_resident_outbox(tenant_id,case_id)` | `vh_resident_cases(tenant_id,id)` | `FOREIGN KEY (tenant_id, case_id) REFERENCES vh_resident_cases(tenant_id, id)` |
| `vh_resident_outbox(tenant_id,event_id)` | `vh_resident_public_events(tenant_id,id)` | `FOREIGN KEY (tenant_id, event_id) REFERENCES vh_resident_public_events(tenant_id, id)` |
| `vh_resident_outbox(tenant_id)` | `tenants(id)` | `FOREIGN KEY (tenant_id) REFERENCES tenants(id)` |
| `vh_resident_photos(tenant_id,case_id)` | `vh_resident_cases(tenant_id,id)` | `FOREIGN KEY (tenant_id, case_id) REFERENCES vh_resident_cases(tenant_id, id)` |
| `vh_resident_photos(tenant_id,file_id)` | `files(tenant_id,id)` | `FOREIGN KEY (tenant_id, file_id) REFERENCES files(tenant_id, id)` |
| `vh_resident_photos(tenant_id)` | `tenants(id)` | `FOREIGN KEY (tenant_id) REFERENCES tenants(id)` |
| `vh_resident_photos(tenant_id,unit_id)` | `units(tenant_id,id)` | `FOREIGN KEY (tenant_id, unit_id) REFERENCES units(tenant_id, id)` |
| `vh_resident_photos(uploaded_by)` | `users(id)` | `FOREIGN KEY (uploaded_by) REFERENCES users(id)` |
| `vh_resident_public_events(tenant_id,case_id)` | `vh_resident_cases(tenant_id,id)` | `FOREIGN KEY (tenant_id, case_id) REFERENCES vh_resident_cases(tenant_id, id)` |
| `vh_resident_public_events(tenant_id)` | `tenants(id)` | `FOREIGN KEY (tenant_id) REFERENCES tenants(id)` |
| `vh_resident_resolution_photos(tenant_id,file_id)` | `files(tenant_id,id)` | `FOREIGN KEY (tenant_id, file_id) REFERENCES files(tenant_id, id)` |
| `vh_resident_resolution_photos(tenant_id)` | `tenants(id)` | `FOREIGN KEY (tenant_id) REFERENCES tenants(id)` |
| `vh_resident_resolution_photos(tenant_id,resolution_id)` | `vh_resident_resolutions(tenant_id,id)` | `FOREIGN KEY (tenant_id, resolution_id) REFERENCES vh_resident_resolutions(tenant_id, id)` |
| `vh_resident_resolution_responses(tenant_id,case_id,resolution_id)` | `vh_resident_resolutions(tenant_id,case_id,id)` | `FOREIGN KEY (tenant_id, case_id, resolution_id) REFERENCES vh_resident_resolutions(tenant_id, case_id, id)` |
| `vh_resident_resolution_responses(actor_id)` | `users(id)` | `FOREIGN KEY (actor_id) REFERENCES users(id)` |
| `vh_resident_resolution_responses(tenant_id)` | `tenants(id)` | `FOREIGN KEY (tenant_id) REFERENCES tenants(id)` |
| `vh_resident_resolutions(published_by)` | `users(id)` | `FOREIGN KEY (published_by) REFERENCES users(id)` |
| `vh_resident_resolutions(tenant_id,case_id)` | `vh_resident_cases(tenant_id,id)` | `FOREIGN KEY (tenant_id, case_id) REFERENCES vh_resident_cases(tenant_id, id)` |
| `vh_resident_resolutions(tenant_id)` | `tenants(id)` | `FOREIGN KEY (tenant_id) REFERENCES tenants(id)` |
| `vh_resident_submissions(submitted_by)` | `users(id)` | `FOREIGN KEY (submitted_by) REFERENCES users(id)` |
| `vh_resident_submissions(tenant_id,case_id)` | `vh_resident_cases(tenant_id,id)` | `FOREIGN KEY (tenant_id, case_id) REFERENCES vh_resident_cases(tenant_id, id)` |
| `vh_resident_submissions(tenant_id)` | `tenants(id)` | `FOREIGN KEY (tenant_id) REFERENCES tenants(id)` |
| `vh_security_checkpoints(guard_user_id)` | `users(id)` | `FOREIGN KEY (guard_user_id) REFERENCES users(id)` |
| `vh_security_checkpoints(tenant_id,site_id)` | `sites(tenant_id,id)` | `FOREIGN KEY (tenant_id, site_id) REFERENCES sites(tenant_id, id)` |
| `vh_security_handovers(from_user_id)` | `users(id)` | `FOREIGN KEY (from_user_id) REFERENCES users(id)` |
| `vh_security_handovers(tenant_id,site_id)` | `sites(tenant_id,id)` | `FOREIGN KEY (tenant_id, site_id) REFERENCES sites(tenant_id, id)` |
| `vh_security_handovers(to_user_id)` | `users(id)` | `FOREIGN KEY (to_user_id) REFERENCES users(id)` |
| `vh_security_incidents(reported_by)` | `users(id)` | `FOREIGN KEY (reported_by) REFERENCES users(id)` |
| `vh_security_incidents(tenant_id,site_id)` | `sites(tenant_id,id)` | `FOREIGN KEY (tenant_id, site_id) REFERENCES sites(tenant_id, id)` |
| `vh_security_incidents(tenant_id,ticket_id)` | `tickets(tenant_id,id)` | `FOREIGN KEY (tenant_id, ticket_id) REFERENCES tickets(tenant_id, id)` |
| `vh_sensor_readings(recorded_by)` | `users(id)` | `FOREIGN KEY (recorded_by) REFERENCES users(id)` |
| `vh_sensor_readings(tenant_id,asset_id)` | `vh_assets(tenant_id,id)` | `FOREIGN KEY (tenant_id, asset_id) REFERENCES vh_assets(tenant_id, id)` |
| `vh_sensor_readings(tenant_id)` | `tenants(id)` | `FOREIGN KEY (tenant_id) REFERENCES tenants(id)` |
| `vh_technical_agent_grants(agent_id)` | `agents(id)` | `FOREIGN KEY (agent_id) REFERENCES agents(id)` |
| `vh_technical_agent_grants(tenant_id)` | `tenants(id)` | `FOREIGN KEY (tenant_id) REFERENCES tenants(id)` |
| `vh_technical_agent_grants(tenant_id,scope_id)` | `access_scopes(tenant_id,id)` | `FOREIGN KEY (tenant_id, scope_id) REFERENCES access_scopes(tenant_id, id)` |
| `vh_technical_api_audit(tenant_id)` | `tenants(id)` | `FOREIGN KEY (tenant_id) REFERENCES tenants(id)` |
| `vh_technical_api_receipts(tenant_id)` | `tenants(id)` | `FOREIGN KEY (tenant_id) REFERENCES tenants(id)` |
| `vh_technical_approval_requests(tenant_id,building_id)` | `buildings(tenant_id,id)` | `FOREIGN KEY (tenant_id, building_id) REFERENCES buildings(tenant_id, id)` |
| `vh_technical_approval_requests(tenant_id)` | `tenants(id)` | `FOREIGN KEY (tenant_id) REFERENCES tenants(id)` |
| `vh_technical_approval_requests(tenant_id,incident_id)` | `tickets(tenant_id,id)` | `FOREIGN KEY (tenant_id, incident_id) REFERENCES tickets(tenant_id, id)` |
| `vh_technical_executor_results(tenant_id,building_id)` | `buildings(tenant_id,id)` | `FOREIGN KEY (tenant_id, building_id) REFERENCES buildings(tenant_id, id)` |
| `vh_technical_executor_results(tenant_id)` | `tenants(id)` | `FOREIGN KEY (tenant_id) REFERENCES tenants(id)` |
| `vh_technical_executor_results(tenant_id,work_order_id)` | `work_orders(tenant_id,id)` | `FOREIGN KEY (tenant_id, work_order_id) REFERENCES work_orders(tenant_id, id)` |
| `vh_technical_maintenance_events(tenant_id,supersedes_event_id)` | `vh_technical_maintenance_events(tenant_id,id)` | `FOREIGN KEY (tenant_id, supersedes_event_id) REFERENCES vh_technical_maintenance_events(tenant_id, id)` |
| `vh_technical_maintenance_events(tenant_id,building_id)` | `buildings(tenant_id,id)` | `FOREIGN KEY (tenant_id, building_id) REFERENCES buildings(tenant_id, id)` |
| `vh_technical_maintenance_events(tenant_id)` | `tenants(id)` | `FOREIGN KEY (tenant_id) REFERENCES tenants(id)` |
| `vh_technical_maintenance_events(tenant_id,work_order_id)` | `work_orders(tenant_id,id)` | `FOREIGN KEY (tenant_id, work_order_id) REFERENCES work_orders(tenant_id, id)` |
| `vh_technical_measurement_records(tenant_id,building_id)` | `buildings(tenant_id,id)` | `FOREIGN KEY (tenant_id, building_id) REFERENCES buildings(tenant_id, id)` |
| `vh_technical_measurement_records(tenant_id)` | `tenants(id)` | `FOREIGN KEY (tenant_id) REFERENCES tenants(id)` |
| `vh_technical_measurement_records(tenant_id,work_order_id)` | `work_orders(tenant_id,id)` | `FOREIGN KEY (tenant_id, work_order_id) REFERENCES work_orders(tenant_id, id)` |
| `vh_technical_measurements(recorded_by)` | `users(id)` | `FOREIGN KEY (recorded_by) REFERENCES users(id)` |
| `vh_technical_measurements(tenant_id)` | `tenants(id)` | `FOREIGN KEY (tenant_id) REFERENCES tenants(id)` |
| `vh_technical_measurements(tenant_id,work_order_id)` | `work_orders(tenant_id,id)` | `FOREIGN KEY (tenant_id, work_order_id) REFERENCES work_orders(tenant_id, id)` |
| `vh_technical_sensor_samples(tenant_id,sensor_id)` | `vh_technical_sensors(tenant_id,sensor_id)` | `FOREIGN KEY (tenant_id, sensor_id) REFERENCES vh_technical_sensors(tenant_id, sensor_id)` |
| `vh_technical_sensors(tenant_id,building_id)` | `buildings(tenant_id,id)` | `FOREIGN KEY (tenant_id, building_id) REFERENCES buildings(tenant_id, id)` |
| `vh_technical_sensors(tenant_id)` | `tenants(id)` | `FOREIGN KEY (tenant_id) REFERENCES tenants(id)` |
| `vh_technical_sop_profiles(tenant_id)` | `tenants(id)` | `FOREIGN KEY (tenant_id) REFERENCES tenants(id)` |
| `vh_technical_vendors(tenant_id)` | `tenants(id)` | `FOREIGN KEY (tenant_id) REFERENCES tenants(id)` |
| `vh_ticket_plans(management_by)` | `users(id)` | `FOREIGN KEY (management_by) REFERENCES users(id)` |
| `vh_ticket_plans(proposed_by)` | `users(id)` | `FOREIGN KEY (proposed_by) REFERENCES users(id)` |
| `vh_ticket_plans(resident_by)` | `users(id)` | `FOREIGN KEY (resident_by) REFERENCES users(id)` |
| `vh_ticket_plans(tenant_id)` | `tenants(id)` | `FOREIGN KEY (tenant_id) REFERENCES tenants(id)` |
| `vh_ticket_plans(tenant_id,ticket_id)` | `tickets(tenant_id,id)` | `FOREIGN KEY (tenant_id, ticket_id) REFERENCES tickets(tenant_id, id)` |
| `work_approval_evidence(tenant_id,approval_id)` | `work_approvals(tenant_id,id)` | `FOREIGN KEY (tenant_id, approval_id) REFERENCES work_approvals(tenant_id, id) ON DELETE RESTRICT` |
| `work_approval_evidence(tenant_id,evidence_id)` | `evidence_items(tenant_id,id)` | `FOREIGN KEY (tenant_id, evidence_id) REFERENCES evidence_items(tenant_id, id) ON DELETE RESTRICT` |
| `work_approval_evidence(tenant_id,original_object_id)` | `file_objects(tenant_id,id)` | `FOREIGN KEY (tenant_id, original_object_id) REFERENCES file_objects(tenant_id, id) ON DELETE RESTRICT` |
| `work_approval_evidence(tenant_id)` | `tenants(id)` | `FOREIGN KEY (tenant_id) REFERENCES tenants(id) ON DELETE RESTRICT` |
| `work_approvals(decided_by)` | `users(id)` | `FOREIGN KEY (decided_by) REFERENCES users(id) ON DELETE RESTRICT` |
| `work_approvals(tenant_id,decided_event_id)` | `ticket_events(tenant_id,id)` | `FOREIGN KEY (tenant_id, decided_event_id) REFERENCES ticket_events(tenant_id, id) ON DELETE RESTRICT` |
| `work_approvals(requested_to_user_id)` | `users(id)` | `FOREIGN KEY (requested_to_user_id) REFERENCES users(id) ON DELETE RESTRICT` |
| `work_approvals(tenant_id,required_scope_id)` | `access_scopes(tenant_id,id)` | `FOREIGN KEY (tenant_id, required_scope_id) REFERENCES access_scopes(tenant_id, id) ON DELETE RESTRICT` |
| `work_approvals(tenant_id)` | `tenants(id)` | `FOREIGN KEY (tenant_id) REFERENCES tenants(id) ON DELETE RESTRICT` |
| `work_approvals(tenant_id,work_order_id)` | `work_orders(tenant_id,id)` | `FOREIGN KEY (tenant_id, work_order_id) REFERENCES work_orders(tenant_id, id) ON DELETE RESTRICT` |
| `work_assignments(tenant_id,assigned_by_agent_id)` | `agents(tenant_id,id)` | `FOREIGN KEY (tenant_id, assigned_by_agent_id) REFERENCES agents(tenant_id, id) ON DELETE RESTRICT` |
| `work_assignments(assigned_by_user_id)` | `users(id)` | `FOREIGN KEY (assigned_by_user_id) REFERENCES users(id) ON DELETE RESTRICT` |
| `work_assignments(tenant_id,dispatch_attempt_id)` | `dispatch_attempts(tenant_id,id)` | `FOREIGN KEY (tenant_id, dispatch_attempt_id) REFERENCES dispatch_attempts(tenant_id, id) ON DELETE RESTRICT` |
| `work_assignments(tenant_id,staff_id)` | `staff_profiles(tenant_id,id)` | `FOREIGN KEY (tenant_id, staff_id) REFERENCES staff_profiles(tenant_id, id) ON DELETE RESTRICT` |
| `work_assignments(tenant_id)` | `tenants(id)` | `FOREIGN KEY (tenant_id) REFERENCES tenants(id) ON DELETE RESTRICT` |
| `work_assignments(tenant_id,work_order_id)` | `work_orders(tenant_id,id)` | `FOREIGN KEY (tenant_id, work_order_id) REFERENCES work_orders(tenant_id, id) ON DELETE RESTRICT` |
| `work_items(tenant_id)` | `tenants(id)` | `FOREIGN KEY (tenant_id) REFERENCES tenants(id) ON DELETE RESTRICT` |
| `work_orders(tenant_id,category_id)` | `service_categories(tenant_id,id)` | `FOREIGN KEY (tenant_id, category_id) REFERENCES service_categories(tenant_id, id) ON DELETE RESTRICT` |
| `work_orders(tenant_id,required_specialty_id)` | `service_categories(tenant_id,id)` | `FOREIGN KEY (tenant_id, required_specialty_id) REFERENCES service_categories(tenant_id, id) ON DELETE RESTRICT` |
| `work_orders(tenant_id)` | `tenants(id)` | `FOREIGN KEY (tenant_id) REFERENCES tenants(id) ON DELETE RESTRICT` |
| `work_orders(tenant_id,ticket_id)` | `tickets(tenant_id,id)` | `FOREIGN KEY (tenant_id, ticket_id) REFERENCES tickets(tenant_id, id) ON DELETE RESTRICT` |
| `work_reassignment_requests(approved_by)` | `users(id)` | `FOREIGN KEY (approved_by) REFERENCES users(id) ON DELETE RESTRICT` |
| `work_reassignment_requests(tenant_id,new_assignment_id)` | `work_assignments(tenant_id,id)` | `FOREIGN KEY (tenant_id, new_assignment_id) REFERENCES work_assignments(tenant_id, id) ON DELETE RESTRICT` |
| `work_reassignment_requests(requested_by)` | `users(id)` | `FOREIGN KEY (requested_by) REFERENCES users(id) ON DELETE RESTRICT` |
| `work_reassignment_requests(safe_stop_confirmed_by)` | `users(id)` | `FOREIGN KEY (safe_stop_confirmed_by) REFERENCES users(id) ON DELETE RESTRICT` |
| `work_reassignment_requests(tenant_id,source_assignment_id)` | `work_assignments(tenant_id,id)` | `FOREIGN KEY (tenant_id, source_assignment_id) REFERENCES work_assignments(tenant_id, id) ON DELETE RESTRICT` |
| `work_reassignment_requests(tenant_id,source_run_id)` | `agent_runs(tenant_id,id)` | `FOREIGN KEY (tenant_id, source_run_id) REFERENCES agent_runs(tenant_id, id) ON DELETE RESTRICT` |
| `work_reassignment_requests(tenant_id,target_decision_id)` | `ticket_triage_decisions(tenant_id,id)` | `FOREIGN KEY (tenant_id, target_decision_id) REFERENCES ticket_triage_decisions(tenant_id, id) ON DELETE RESTRICT` |
| `work_reassignment_requests(tenant_id,target_work_order_id)` | `work_orders(tenant_id,id)` | `FOREIGN KEY (tenant_id, target_work_order_id) REFERENCES work_orders(tenant_id, id) ON DELETE RESTRICT` |
| `work_reassignment_requests(tenant_id)` | `tenants(id)` | `FOREIGN KEY (tenant_id) REFERENCES tenants(id) ON DELETE RESTRICT` |
| `workspace_members(tenant_id)` | `tenants(id)` | `FOREIGN KEY (tenant_id) REFERENCES tenants(id) ON DELETE RESTRICT` |
| `workspace_members(user_id)` | `users(id)` | `FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE RESTRICT` |
| `workspace_members(tenant_id,workspace_id)` | `workspaces(tenant_id,id)` | `FOREIGN KEY (tenant_id, workspace_id) REFERENCES workspaces(tenant_id, id) ON DELETE RESTRICT` |
| `workspaces(tenant_id,management_unit_id)` | `management_units(tenant_id,id)` | `FOREIGN KEY (tenant_id, management_unit_id) REFERENCES management_units(tenant_id, id) ON DELETE RESTRICT` |
| `workspaces(tenant_id)` | `tenants(id)` | `FOREIGN KEY (tenant_id) REFERENCES tenants(id) ON DELETE RESTRICT` |
| `zones(tenant_id,site_id)` | `sites(tenant_id,id)` | `FOREIGN KEY (tenant_id, site_id) REFERENCES sites(tenant_id, id) ON DELETE RESTRICT` |
| `zones(tenant_id)` | `tenants(id)` | `FOREIGN KEY (tenant_id) REFERENCES tenants(id) ON DELETE RESTRICT` |
