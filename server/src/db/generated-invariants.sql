-- Generated companion DDL. Included by db:generate, not a migration journal.
CREATE TRIGGER "tenants_touch" BEFORE UPDATE ON "tenants" FOR EACH ROW EXECUTE FUNCTION app_touch_updated_at();
--> statement-breakpoint
ALTER TABLE "tenant_memberships" FORCE ROW LEVEL SECURITY;
--> statement-breakpoint
CREATE TRIGGER "tenant_memberships_touch" BEFORE UPDATE ON "tenant_memberships" FOR EACH ROW EXECUTE FUNCTION app_touch_updated_at();
--> statement-breakpoint
ALTER TABLE "access_scopes" FORCE ROW LEVEL SECURITY;
--> statement-breakpoint
CREATE TRIGGER "access_scopes_touch" BEFORE UPDATE ON "access_scopes" FOR EACH ROW EXECUTE FUNCTION app_touch_updated_at();
--> statement-breakpoint
ALTER TABLE "scoped_user_roles" FORCE ROW LEVEL SECURITY;
--> statement-breakpoint
CREATE TRIGGER "scoped_user_roles_touch" BEFORE UPDATE ON "scoped_user_roles" FOR EACH ROW EXECUTE FUNCTION app_touch_updated_at();
--> statement-breakpoint
ALTER TABLE "account_reviews" FORCE ROW LEVEL SECURITY;
--> statement-breakpoint
ALTER TABLE "domains" FORCE ROW LEVEL SECURITY;
--> statement-breakpoint
CREATE TRIGGER "domains_touch" BEFORE UPDATE ON "domains" FOR EACH ROW EXECUTE FUNCTION app_touch_updated_at();
--> statement-breakpoint
ALTER TABLE "sites" FORCE ROW LEVEL SECURITY;
--> statement-breakpoint
CREATE TRIGGER "sites_touch" BEFORE UPDATE ON "sites" FOR EACH ROW EXECUTE FUNCTION app_touch_updated_at();
--> statement-breakpoint
ALTER TABLE "zones" FORCE ROW LEVEL SECURITY;
--> statement-breakpoint
CREATE TRIGGER "zones_touch" BEFORE UPDATE ON "zones" FOR EACH ROW EXECUTE FUNCTION app_touch_updated_at();
--> statement-breakpoint
ALTER TABLE "buildings" FORCE ROW LEVEL SECURITY;
--> statement-breakpoint
CREATE TRIGGER "buildings_touch" BEFORE UPDATE ON "buildings" FOR EACH ROW EXECUTE FUNCTION app_touch_updated_at();
--> statement-breakpoint
ALTER TABLE "units" FORCE ROW LEVEL SECURITY;
--> statement-breakpoint
CREATE TRIGGER "units_touch" BEFORE UPDATE ON "units" FOR EACH ROW EXECUTE FUNCTION app_touch_updated_at();
--> statement-breakpoint
ALTER TABLE "unit_residents" FORCE ROW LEVEL SECURITY;
--> statement-breakpoint
CREATE TRIGGER "unit_residents_touch" BEFORE UPDATE ON "unit_residents" FOR EACH ROW EXECUTE FUNCTION app_touch_updated_at();
--> statement-breakpoint
ALTER TABLE "management_units" FORCE ROW LEVEL SECURITY;
--> statement-breakpoint
CREATE TRIGGER "management_units_touch" BEFORE UPDATE ON "management_units" FOR EACH ROW EXECUTE FUNCTION app_touch_updated_at();
--> statement-breakpoint
ALTER TABLE "management_coverage" FORCE ROW LEVEL SECURITY;
--> statement-breakpoint
CREATE TRIGGER "management_coverage_touch" BEFORE UPDATE ON "management_coverage" FOR EACH ROW EXECUTE FUNCTION app_touch_updated_at();
--> statement-breakpoint
ALTER TABLE "workspaces" FORCE ROW LEVEL SECURITY;
--> statement-breakpoint
CREATE TRIGGER "workspaces_touch" BEFORE UPDATE ON "workspaces" FOR EACH ROW EXECUTE FUNCTION app_touch_updated_at();
--> statement-breakpoint
ALTER TABLE "workspace_members" FORCE ROW LEVEL SECURITY;
--> statement-breakpoint
ALTER TABLE "agent_versions" FORCE ROW LEVEL SECURITY;
--> statement-breakpoint
CREATE TRIGGER "agent_versions_immutable" BEFORE UPDATE OR DELETE ON "agent_versions" FOR EACH ROW EXECUTE FUNCTION app_append_only();
--> statement-breakpoint
CREATE TRIGGER "agent_versions_no_truncate" BEFORE TRUNCATE ON "agent_versions" FOR EACH STATEMENT EXECUTE FUNCTION app_append_only();
--> statement-breakpoint
ALTER TABLE "agent_releases" FORCE ROW LEVEL SECURITY;
--> statement-breakpoint
CREATE TRIGGER "agent_releases_touch" BEFORE UPDATE ON "agent_releases" FOR EACH ROW EXECUTE FUNCTION app_touch_updated_at();
--> statement-breakpoint
ALTER TABLE "agent_knowledge_grants" FORCE ROW LEVEL SECURITY;
--> statement-breakpoint
ALTER TABLE "messages" FORCE ROW LEVEL SECURITY;
--> statement-breakpoint
ALTER TABLE "message_mentions" FORCE ROW LEVEL SECURITY;
--> statement-breakpoint
ALTER TABLE "message_files" FORCE ROW LEVEL SECURITY;
--> statement-breakpoint
ALTER TABLE "agent_teams" FORCE ROW LEVEL SECURITY;
--> statement-breakpoint
CREATE TRIGGER "agent_teams_touch" BEFORE UPDATE ON "agent_teams" FOR EACH ROW EXECUTE FUNCTION app_touch_updated_at();
--> statement-breakpoint
ALTER TABLE "team_members" FORCE ROW LEVEL SECURITY;
--> statement-breakpoint
CREATE TRIGGER "team_members_touch" BEFORE UPDATE ON "team_members" FOR EACH ROW EXECUTE FUNCTION app_touch_updated_at();
--> statement-breakpoint
ALTER TABLE "team_tasks" FORCE ROW LEVEL SECURITY;
--> statement-breakpoint
CREATE TRIGGER "team_tasks_touch" BEFORE UPDATE ON "team_tasks" FOR EACH ROW EXECUTE FUNCTION app_touch_updated_at();
--> statement-breakpoint
ALTER TABLE "task_dependencies" FORCE ROW LEVEL SECURITY;
--> statement-breakpoint
ALTER TABLE "team_mailbox" FORCE ROW LEVEL SECURITY;
--> statement-breakpoint
ALTER TABLE "mailbox_deliveries" FORCE ROW LEVEL SECURITY;
--> statement-breakpoint
CREATE TRIGGER "mailbox_deliveries_touch" BEFORE UPDATE ON "mailbox_deliveries" FOR EACH ROW EXECUTE FUNCTION app_touch_updated_at();
--> statement-breakpoint
ALTER TABLE "agent_runs" FORCE ROW LEVEL SECURITY;
--> statement-breakpoint
CREATE TRIGGER "agent_runs_touch" BEFORE UPDATE ON "agent_runs" FOR EACH ROW EXECUTE FUNCTION app_touch_updated_at();
--> statement-breakpoint
ALTER TABLE "context_snapshots" FORCE ROW LEVEL SECURITY;
--> statement-breakpoint
CREATE TRIGGER "context_snapshots_immutable" BEFORE UPDATE OR DELETE ON "context_snapshots" FOR EACH ROW EXECUTE FUNCTION app_append_only();
--> statement-breakpoint
CREATE TRIGGER "context_snapshots_no_truncate" BEFORE TRUNCATE ON "context_snapshots" FOR EACH STATEMENT EXECUTE FUNCTION app_append_only();
--> statement-breakpoint
ALTER TABLE "event_outbox" FORCE ROW LEVEL SECURITY;
--> statement-breakpoint
ALTER TABLE "event_inbox" FORCE ROW LEVEL SECURITY;
--> statement-breakpoint
CREATE TRIGGER "event_inbox_touch" BEFORE UPDATE ON "event_inbox" FOR EACH ROW EXECUTE FUNCTION app_touch_updated_at();
--> statement-breakpoint
ALTER TABLE "notification_deliveries" FORCE ROW LEVEL SECURITY;
--> statement-breakpoint
CREATE TRIGGER "notification_deliveries_touch" BEFORE UPDATE ON "notification_deliveries" FOR EACH ROW EXECUTE FUNCTION app_touch_updated_at();
--> statement-breakpoint
ALTER TABLE "service_categories" FORCE ROW LEVEL SECURITY;
--> statement-breakpoint
CREATE TRIGGER "service_categories_touch" BEFORE UPDATE ON "service_categories" FOR EACH ROW EXECUTE FUNCTION app_touch_updated_at();
--> statement-breakpoint
ALTER TABLE "incident_types" FORCE ROW LEVEL SECURITY;
--> statement-breakpoint
CREATE TRIGGER "incident_types_touch" BEFORE UPDATE ON "incident_types" FOR EACH ROW EXECUTE FUNCTION app_touch_updated_at();
--> statement-breakpoint
ALTER TABLE "sla_policies" FORCE ROW LEVEL SECURITY;
--> statement-breakpoint
CREATE TRIGGER "sla_policies_touch" BEFORE UPDATE ON "sla_policies" FOR EACH ROW EXECUTE FUNCTION app_touch_updated_at();
--> statement-breakpoint
ALTER TABLE "staff_profiles" FORCE ROW LEVEL SECURITY;
--> statement-breakpoint
CREATE TRIGGER "staff_profiles_touch" BEFORE UPDATE ON "staff_profiles" FOR EACH ROW EXECUTE FUNCTION app_touch_updated_at();
--> statement-breakpoint
ALTER TABLE "staff_specialties" FORCE ROW LEVEL SECURITY;
--> statement-breakpoint
ALTER TABLE "staff_shifts" FORCE ROW LEVEL SECURITY;
--> statement-breakpoint
CREATE TRIGGER "staff_shifts_touch" BEFORE UPDATE ON "staff_shifts" FOR EACH ROW EXECUTE FUNCTION app_touch_updated_at();
--> statement-breakpoint
ALTER TABLE "tickets" FORCE ROW LEVEL SECURITY;
--> statement-breakpoint
CREATE TRIGGER "tickets_touch" BEFORE UPDATE ON "tickets" FOR EACH ROW EXECUTE FUNCTION app_touch_updated_at();
--> statement-breakpoint
ALTER TABLE "ticket_events" FORCE ROW LEVEL SECURITY;
--> statement-breakpoint
CREATE TRIGGER "ticket_events_immutable" BEFORE UPDATE OR DELETE ON "ticket_events" FOR EACH ROW EXECUTE FUNCTION app_append_only();
--> statement-breakpoint
CREATE TRIGGER "ticket_events_no_truncate" BEFORE TRUNCATE ON "ticket_events" FOR EACH STATEMENT EXECUTE FUNCTION app_append_only();
--> statement-breakpoint
ALTER TABLE "ticket_routing_history" FORCE ROW LEVEL SECURITY;
--> statement-breakpoint
ALTER TABLE "ticket_files" FORCE ROW LEVEL SECURITY;
--> statement-breakpoint
ALTER TABLE "work_orders" FORCE ROW LEVEL SECURITY;
--> statement-breakpoint
CREATE TRIGGER "work_orders_touch" BEFORE UPDATE ON "work_orders" FOR EACH ROW EXECUTE FUNCTION app_touch_updated_at();
--> statement-breakpoint
ALTER TABLE "work_assignments" FORCE ROW LEVEL SECURITY;
--> statement-breakpoint
CREATE TRIGGER "work_assignments_touch" BEFORE UPDATE ON "work_assignments" FOR EACH ROW EXECUTE FUNCTION app_touch_updated_at();
--> statement-breakpoint
ALTER TABLE "dispatch_queue" FORCE ROW LEVEL SECURITY;
--> statement-breakpoint
CREATE TRIGGER "dispatch_queue_touch" BEFORE UPDATE ON "dispatch_queue" FOR EACH ROW EXECUTE FUNCTION app_touch_updated_at();
--> statement-breakpoint
ALTER TABLE "work_approvals" FORCE ROW LEVEL SECURITY;
--> statement-breakpoint
CREATE TRIGGER "work_approvals_touch" BEFORE UPDATE ON "work_approvals" FOR EACH ROW EXECUTE FUNCTION app_touch_updated_at();
--> statement-breakpoint
ALTER TABLE "service_interruptions" FORCE ROW LEVEL SECURITY;
--> statement-breakpoint
CREATE TRIGGER "service_interruptions_touch" BEFORE UPDATE ON "service_interruptions" FOR EACH ROW EXECUTE FUNCTION app_touch_updated_at();
--> statement-breakpoint
ALTER TABLE "interruption_scopes" FORCE ROW LEVEL SECURITY;
--> statement-breakpoint
ALTER TABLE "ticket_reviews" FORCE ROW LEVEL SECURITY;
--> statement-breakpoint
CREATE TRIGGER "ticket_reviews_touch" BEFORE UPDATE ON "ticket_reviews" FOR EACH ROW EXECUTE FUNCTION app_touch_updated_at();
--> statement-breakpoint
ALTER TABLE "invoices" FORCE ROW LEVEL SECURITY;
--> statement-breakpoint
CREATE TRIGGER "invoices_touch" BEFORE UPDATE ON "invoices" FOR EACH ROW EXECUTE FUNCTION app_touch_updated_at();
--> statement-breakpoint
ALTER TABLE "invoice_lines" FORCE ROW LEVEL SECURITY;
--> statement-breakpoint
CREATE TRIGGER "invoice_lines_touch" BEFORE UPDATE ON "invoice_lines" FOR EACH ROW EXECUTE FUNCTION app_touch_updated_at();
--> statement-breakpoint
ALTER TABLE "payment_intents" FORCE ROW LEVEL SECURITY;
--> statement-breakpoint
CREATE TRIGGER "payment_intents_touch" BEFORE UPDATE ON "payment_intents" FOR EACH ROW EXECUTE FUNCTION app_touch_updated_at();
--> statement-breakpoint
ALTER TABLE "payment_webhook_receipts" FORCE ROW LEVEL SECURITY;
--> statement-breakpoint
ALTER TABLE "payments" FORCE ROW LEVEL SECURITY;
--> statement-breakpoint
ALTER TABLE "refunds" FORCE ROW LEVEL SECURITY;
--> statement-breakpoint
CREATE TRIGGER "refunds_touch" BEFORE UPDATE ON "refunds" FOR EACH ROW EXECUTE FUNCTION app_touch_updated_at();
--> statement-breakpoint
ALTER TABLE "files" FORCE ROW LEVEL SECURITY;
--> statement-breakpoint
CREATE TRIGGER "files_touch" BEFORE UPDATE ON "files" FOR EACH ROW EXECUTE FUNCTION app_touch_updated_at();
--> statement-breakpoint
ALTER TABLE "knowledge_bases" FORCE ROW LEVEL SECURITY;
--> statement-breakpoint
CREATE TRIGGER "knowledge_bases_touch" BEFORE UPDATE ON "knowledge_bases" FOR EACH ROW EXECUTE FUNCTION app_touch_updated_at();
--> statement-breakpoint
ALTER TABLE "knowledge_categories" FORCE ROW LEVEL SECURITY;
--> statement-breakpoint
CREATE TRIGGER "knowledge_categories_touch" BEFORE UPDATE ON "knowledge_categories" FOR EACH ROW EXECUTE FUNCTION app_touch_updated_at();
--> statement-breakpoint
ALTER TABLE "knowledge_documents" FORCE ROW LEVEL SECURITY;
--> statement-breakpoint
CREATE TRIGGER "knowledge_documents_touch" BEFORE UPDATE ON "knowledge_documents" FOR EACH ROW EXECUTE FUNCTION app_touch_updated_at();
--> statement-breakpoint
ALTER TABLE "document_versions" FORCE ROW LEVEL SECURITY;
--> statement-breakpoint
ALTER TABLE "document_scopes" FORCE ROW LEVEL SECURITY;
--> statement-breakpoint
ALTER TABLE "document_acl" FORCE ROW LEVEL SECURITY;
--> statement-breakpoint
CREATE TRIGGER "document_acl_touch" BEFORE UPDATE ON "document_acl" FOR EACH ROW EXECUTE FUNCTION app_touch_updated_at();
--> statement-breakpoint
ALTER TABLE "knowledge_reviews" FORCE ROW LEVEL SECURITY;
--> statement-breakpoint
ALTER TABLE "ingestion_jobs" FORCE ROW LEVEL SECURITY;
--> statement-breakpoint
CREATE TRIGGER "ingestion_jobs_touch" BEFORE UPDATE ON "ingestion_jobs" FOR EACH ROW EXECUTE FUNCTION app_touch_updated_at();
--> statement-breakpoint
ALTER TABLE "knowledge_chunks" FORCE ROW LEVEL SECURITY;
--> statement-breakpoint
CREATE TRIGGER "knowledge_chunks_immutable" BEFORE UPDATE OR DELETE ON "knowledge_chunks" FOR EACH ROW EXECUTE FUNCTION app_append_only();
--> statement-breakpoint
CREATE TRIGGER "knowledge_chunks_no_truncate" BEFORE TRUNCATE ON "knowledge_chunks" FOR EACH STATEMENT EXECUTE FUNCTION app_append_only();
--> statement-breakpoint
CREATE TRIGGER "embedding_models_touch" BEFORE UPDATE ON "embedding_models" FOR EACH ROW EXECUTE FUNCTION app_touch_updated_at();
--> statement-breakpoint
ALTER TABLE "knowledge_embeddings" FORCE ROW LEVEL SECURITY;
--> statement-breakpoint
ALTER TABLE "retrieval_runs" FORCE ROW LEVEL SECURITY;
--> statement-breakpoint
ALTER TABLE "retrieval_hits" FORCE ROW LEVEL SECURITY;
--> statement-breakpoint
ALTER TABLE "memory_candidates" FORCE ROW LEVEL SECURITY;
--> statement-breakpoint
CREATE TRIGGER "memory_candidates_touch" BEFORE UPDATE ON "memory_candidates" FOR EACH ROW EXECUTE FUNCTION app_touch_updated_at();
--> statement-breakpoint
ALTER TABLE "memory_publications" FORCE ROW LEVEL SECURITY;
--> statement-breakpoint
CREATE TRIGGER "memory_publications_touch" BEFORE UPDATE ON "memory_publications" FOR EACH ROW EXECUTE FUNCTION app_touch_updated_at();
--> statement-breakpoint
CREATE TRIGGER "components_touch" BEFORE UPDATE ON "components" FOR EACH ROW EXECUTE FUNCTION app_touch_updated_at();
--> statement-breakpoint
ALTER TABLE "component_exclusions" FORCE ROW LEVEL SECURITY;
--> statement-breakpoint
CREATE TRIGGER "component_exclusions_touch" BEFORE UPDATE ON "component_exclusions" FOR EACH ROW EXECUTE FUNCTION app_touch_updated_at();
--> statement-breakpoint
CREATE TRIGGER "component_functions_touch" BEFORE UPDATE ON "component_functions" FOR EACH ROW EXECUTE FUNCTION app_touch_updated_at();
--> statement-breakpoint
CREATE TRIGGER "action_policy_touch" BEFORE UPDATE ON "action_policy" FOR EACH ROW EXECUTE FUNCTION app_touch_updated_at();
--> statement-breakpoint
ALTER TABLE "computer_snapshot" FORCE ROW LEVEL SECURITY;
--> statement-breakpoint
ALTER TABLE "computer_page_frame" FORCE ROW LEVEL SECURITY;
--> statement-breakpoint
CREATE TRIGGER "users_touch" BEFORE UPDATE ON "users" FOR EACH ROW EXECUTE FUNCTION app_touch_updated_at();
--> statement-breakpoint
CREATE TRIGGER "sessions_touch" BEFORE UPDATE ON "sessions" FOR EACH ROW EXECUTE FUNCTION app_touch_updated_at();
--> statement-breakpoint
CREATE TRIGGER "accounts_touch" BEFORE UPDATE ON "accounts" FOR EACH ROW EXECUTE FUNCTION app_touch_updated_at();
--> statement-breakpoint
CREATE TRIGGER "verifications_touch" BEFORE UPDATE ON "verifications" FOR EACH ROW EXECUTE FUNCTION app_touch_updated_at();
--> statement-breakpoint
CREATE TRIGGER "user_instructions_touch" BEFORE UPDATE ON "user_instructions" FOR EACH ROW EXECUTE FUNCTION app_touch_updated_at();
--> statement-breakpoint
ALTER TABLE "deployment_packages" FORCE ROW LEVEL SECURITY;
--> statement-breakpoint
ALTER TABLE "agents" FORCE ROW LEVEL SECURITY;
--> statement-breakpoint
CREATE TRIGGER "agents_touch" BEFORE UPDATE ON "agents" FOR EACH ROW EXECUTE FUNCTION app_touch_updated_at();
--> statement-breakpoint
ALTER TABLE "channels" FORCE ROW LEVEL SECURITY;
--> statement-breakpoint
CREATE TRIGGER "channels_touch" BEFORE UPDATE ON "channels" FOR EACH ROW EXECUTE FUNCTION app_touch_updated_at();
--> statement-breakpoint
ALTER TABLE "channel_memberships" FORCE ROW LEVEL SECURITY;
--> statement-breakpoint
ALTER TABLE "channel_agents" FORCE ROW LEVEL SECURITY;
--> statement-breakpoint
ALTER TABLE "credentials" FORCE ROW LEVEL SECURITY;
--> statement-breakpoint
CREATE TRIGGER "credentials_touch" BEFORE UPDATE ON "credentials" FOR EACH ROW EXECUTE FUNCTION app_touch_updated_at();
--> statement-breakpoint
ALTER TABLE "audit_events" FORCE ROW LEVEL SECURITY;
--> statement-breakpoint
CREATE TRIGGER "intelligence_channel_mappings_touch" BEFORE UPDATE ON "intelligence_channel_mappings" FOR EACH ROW EXECUTE FUNCTION app_touch_updated_at();
--> statement-breakpoint
ALTER TABLE "agent_profiles" FORCE ROW LEVEL SECURITY;
--> statement-breakpoint
CREATE TRIGGER "agent_profiles_touch" BEFORE UPDATE ON "agent_profiles" FOR EACH ROW EXECUTE FUNCTION app_touch_updated_at();
--> statement-breakpoint
ALTER TABLE "agent_preferences" FORCE ROW LEVEL SECURITY;
--> statement-breakpoint
ALTER TABLE "routines" FORCE ROW LEVEL SECURITY;
--> statement-breakpoint
CREATE TRIGGER "routines_touch" BEFORE UPDATE ON "routines" FOR EACH ROW EXECUTE FUNCTION app_touch_updated_at();
--> statement-breakpoint
ALTER TABLE "routine_runs" FORCE ROW LEVEL SECURITY;
--> statement-breakpoint
ALTER TABLE "mcp_servers" FORCE ROW LEVEL SECURITY;
--> statement-breakpoint
CREATE TRIGGER "mcp_servers_touch" BEFORE UPDATE ON "mcp_servers" FOR EACH ROW EXECUTE FUNCTION app_touch_updated_at();
--> statement-breakpoint
ALTER TABLE "mcp_tools" FORCE ROW LEVEL SECURITY;
--> statement-breakpoint
ALTER TABLE "composio_connections" FORCE ROW LEVEL SECURITY;
--> statement-breakpoint
CREATE TRIGGER "composio_connections_touch" BEFORE UPDATE ON "composio_connections" FOR EACH ROW EXECUTE FUNCTION app_touch_updated_at();
--> statement-breakpoint
ALTER TABLE "mcp_user_credentials" FORCE ROW LEVEL SECURITY;
--> statement-breakpoint
CREATE TRIGGER "mcp_user_credentials_touch" BEFORE UPDATE ON "mcp_user_credentials" FOR EACH ROW EXECUTE FUNCTION app_touch_updated_at();
--> statement-breakpoint
ALTER TABLE "skills" FORCE ROW LEVEL SECURITY;
--> statement-breakpoint
CREATE TRIGGER "skills_touch" BEFORE UPDATE ON "skills" FOR EACH ROW EXECUTE FUNCTION app_touch_updated_at();
--> statement-breakpoint
ALTER TABLE "skill_tools" FORCE ROW LEVEL SECURITY;
--> statement-breakpoint
ALTER TABLE "plugin_grants" FORCE ROW LEVEL SECURITY;
--> statement-breakpoint
CREATE TRIGGER "plugin_grants_touch" BEFORE UPDATE ON "plugin_grants" FOR EACH ROW EXECUTE FUNCTION app_touch_updated_at();
--> statement-breakpoint
ALTER TABLE "sandboxed_components" FORCE ROW LEVEL SECURITY;
--> statement-breakpoint
CREATE TRIGGER "sandboxed_components_touch" BEFORE UPDATE ON "sandboxed_components" FOR EACH ROW EXECUTE FUNCTION app_touch_updated_at();
--> statement-breakpoint
ALTER TABLE "work_items" FORCE ROW LEVEL SECURITY;
--> statement-breakpoint
CREATE TRIGGER "work_items_touch" BEFORE UPDATE ON "work_items" FOR EACH ROW EXECUTE FUNCTION app_touch_updated_at();
--> statement-breakpoint
CREATE TRIGGER "runtime_backends_touch" BEFORE UPDATE ON "runtime_backends" FOR EACH ROW EXECUTE FUNCTION app_touch_updated_at();
--> statement-breakpoint
ALTER TABLE "execution_principals" FORCE ROW LEVEL SECURITY;
--> statement-breakpoint
CREATE TRIGGER "execution_principals_touch" BEFORE UPDATE ON "execution_principals" FOR EACH ROW EXECUTE FUNCTION app_touch_updated_at();
--> statement-breakpoint
ALTER TABLE "runtime_identities" FORCE ROW LEVEL SECURITY;
--> statement-breakpoint
ALTER TABLE "runtime_session_bindings" FORCE ROW LEVEL SECURITY;
--> statement-breakpoint
CREATE TRIGGER "runtime_session_bindings_touch" BEFORE UPDATE ON "runtime_session_bindings" FOR EACH ROW EXECUTE FUNCTION app_touch_updated_at();
--> statement-breakpoint
ALTER TABLE "memory_namespaces" FORCE ROW LEVEL SECURITY;
--> statement-breakpoint
CREATE TRIGGER "memory_namespaces_touch" BEFORE UPDATE ON "memory_namespaces" FOR EACH ROW EXECUTE FUNCTION app_touch_updated_at();
--> statement-breakpoint
ALTER TABLE "runtime_memory_bindings" FORCE ROW LEVEL SECURITY;
--> statement-breakpoint
CREATE TRIGGER "runtime_memory_bindings_touch" BEFORE UPDATE ON "runtime_memory_bindings" FOR EACH ROW EXECUTE FUNCTION app_touch_updated_at();
--> statement-breakpoint
ALTER TABLE "run_memory_access" FORCE ROW LEVEL SECURITY;
--> statement-breakpoint
ALTER TABLE "storage_locations" FORCE ROW LEVEL SECURITY;
--> statement-breakpoint
CREATE TRIGGER "storage_locations_touch" BEFORE UPDATE ON "storage_locations" FOR EACH ROW EXECUTE FUNCTION app_touch_updated_at();
--> statement-breakpoint
ALTER TABLE "file_objects" FORCE ROW LEVEL SECURITY;
--> statement-breakpoint
CREATE TRIGGER "file_objects_touch" BEFORE UPDATE ON "file_objects" FOR EACH ROW EXECUTE FUNCTION app_touch_updated_at();
--> statement-breakpoint
ALTER TABLE "file_uploads" FORCE ROW LEVEL SECURITY;
--> statement-breakpoint
CREATE TRIGGER "file_uploads_touch" BEFORE UPDATE ON "file_uploads" FOR EACH ROW EXECUTE FUNCTION app_touch_updated_at();
--> statement-breakpoint
ALTER TABLE "file_upload_parts" FORCE ROW LEVEL SECURITY;
--> statement-breakpoint
CREATE TRIGGER "file_upload_parts_touch" BEFORE UPDATE ON "file_upload_parts" FOR EACH ROW EXECUTE FUNCTION app_touch_updated_at();
--> statement-breakpoint
ALTER TABLE "file_processing_jobs" FORCE ROW LEVEL SECURITY;
--> statement-breakpoint
CREATE TRIGGER "file_processing_jobs_touch" BEFORE UPDATE ON "file_processing_jobs" FOR EACH ROW EXECUTE FUNCTION app_touch_updated_at();
--> statement-breakpoint
ALTER TABLE "storage_event_receipts" FORCE ROW LEVEL SECURITY;
--> statement-breakpoint
CREATE TRIGGER "storage_event_receipts_touch" BEFORE UPDATE ON "storage_event_receipts" FOR EACH ROW EXECUTE FUNCTION app_touch_updated_at();
--> statement-breakpoint
ALTER TABLE "file_access_logs" FORCE ROW LEVEL SECURITY;
--> statement-breakpoint
CREATE TRIGGER "file_access_logs_immutable" BEFORE UPDATE OR DELETE ON "file_access_logs" FOR EACH ROW EXECUTE FUNCTION app_append_only();
--> statement-breakpoint
CREATE TRIGGER "file_access_logs_no_truncate" BEFORE TRUNCATE ON "file_access_logs" FOR EACH STATEMENT EXECUTE FUNCTION app_append_only();
--> statement-breakpoint
ALTER TABLE "file_deletion_requests" FORCE ROW LEVEL SECURITY;
--> statement-breakpoint
CREATE TRIGGER "file_deletion_requests_touch" BEFORE UPDATE ON "file_deletion_requests" FOR EACH ROW EXECUTE FUNCTION app_touch_updated_at();
--> statement-breakpoint
ALTER TABLE "evidence_items" FORCE ROW LEVEL SECURITY;
--> statement-breakpoint
CREATE TRIGGER "evidence_items_touch" BEFORE UPDATE ON "evidence_items" FOR EACH ROW EXECUTE FUNCTION app_touch_updated_at();
--> statement-breakpoint
ALTER TABLE "payment_allocations" FORCE ROW LEVEL SECURITY;
--> statement-breakpoint
CREATE TRIGGER "payment_allocations_immutable" BEFORE UPDATE OR DELETE ON "payment_allocations" FOR EACH ROW EXECUTE FUNCTION app_append_only();
--> statement-breakpoint
CREATE TRIGGER "payment_allocations_no_truncate" BEFORE TRUNCATE ON "payment_allocations" FOR EACH STATEMENT EXECUTE FUNCTION app_append_only();
--> statement-breakpoint
ALTER TABLE "refund_allocations" FORCE ROW LEVEL SECURITY;
--> statement-breakpoint
CREATE TRIGGER "refund_allocations_immutable" BEFORE UPDATE OR DELETE ON "refund_allocations" FOR EACH ROW EXECUTE FUNCTION app_append_only();
--> statement-breakpoint
CREATE TRIGGER "refund_allocations_no_truncate" BEFORE TRUNCATE ON "refund_allocations" FOR EACH STATEMENT EXECUTE FUNCTION app_append_only();
--> statement-breakpoint
ALTER TABLE "work_approval_evidence" FORCE ROW LEVEL SECURITY;
--> statement-breakpoint
CREATE TRIGGER "work_approval_evidence_immutable" BEFORE UPDATE OR DELETE ON "work_approval_evidence" FOR EACH ROW EXECUTE FUNCTION app_append_only();
--> statement-breakpoint
CREATE TRIGGER "work_approval_evidence_no_truncate" BEFORE TRUNCATE ON "work_approval_evidence" FOR EACH STATEMENT EXECUTE FUNCTION app_append_only();
--> statement-breakpoint
ALTER TABLE "triage_policy_versions" FORCE ROW LEVEL SECURITY;
--> statement-breakpoint
CREATE TRIGGER "triage_policy_versions_touch" BEFORE UPDATE ON "triage_policy_versions" FOR EACH ROW EXECUTE FUNCTION app_touch_updated_at();
--> statement-breakpoint
ALTER TABLE "triage_policy_bindings" FORCE ROW LEVEL SECURITY;
--> statement-breakpoint
CREATE TRIGGER "triage_policy_bindings_touch" BEFORE UPDATE ON "triage_policy_bindings" FOR EACH ROW EXECUTE FUNCTION app_touch_updated_at();
--> statement-breakpoint
ALTER TABLE "triage_rules" FORCE ROW LEVEL SECURITY;
--> statement-breakpoint
ALTER TABLE "ticket_assessments" FORCE ROW LEVEL SECURITY;
--> statement-breakpoint
CREATE TRIGGER "ticket_assessments_immutable" BEFORE UPDATE OR DELETE ON "ticket_assessments" FOR EACH ROW EXECUTE FUNCTION app_append_only();
--> statement-breakpoint
CREATE TRIGGER "ticket_assessments_no_truncate" BEFORE TRUNCATE ON "ticket_assessments" FOR EACH STATEMENT EXECUTE FUNCTION app_append_only();
--> statement-breakpoint
ALTER TABLE "ticket_assessment_evidence" FORCE ROW LEVEL SECURITY;
--> statement-breakpoint
CREATE TRIGGER "ticket_assessment_evidence_immutable" BEFORE UPDATE OR DELETE ON "ticket_assessment_evidence" FOR EACH ROW EXECUTE FUNCTION app_append_only();
--> statement-breakpoint
CREATE TRIGGER "ticket_assessment_evidence_no_truncate" BEFORE TRUNCATE ON "ticket_assessment_evidence" FOR EACH STATEMENT EXECUTE FUNCTION app_append_only();
--> statement-breakpoint
ALTER TABLE "ticket_triage_decisions" FORCE ROW LEVEL SECURITY;
--> statement-breakpoint
CREATE TRIGGER "ticket_triage_decisions_immutable" BEFORE UPDATE OR DELETE ON "ticket_triage_decisions" FOR EACH ROW EXECUTE FUNCTION app_append_only();
--> statement-breakpoint
CREATE TRIGGER "ticket_triage_decisions_no_truncate" BEFORE TRUNCATE ON "ticket_triage_decisions" FOR EACH STATEMENT EXECUTE FUNCTION app_append_only();
--> statement-breakpoint
ALTER TABLE "ticket_triage_reviews" FORCE ROW LEVEL SECURITY;
--> statement-breakpoint
CREATE TRIGGER "ticket_triage_reviews_touch" BEFORE UPDATE ON "ticket_triage_reviews" FOR EACH ROW EXECUTE FUNCTION app_touch_updated_at();
--> statement-breakpoint
ALTER TABLE "ticket_sla_cycles" FORCE ROW LEVEL SECURITY;
--> statement-breakpoint
CREATE TRIGGER "ticket_sla_cycles_touch" BEFORE UPDATE ON "ticket_sla_cycles" FOR EACH ROW EXECUTE FUNCTION app_touch_updated_at();
--> statement-breakpoint
ALTER TABLE "ticket_sla_adjustments" FORCE ROW LEVEL SECURITY;
--> statement-breakpoint
CREATE TRIGGER "ticket_sla_adjustments_immutable" BEFORE UPDATE OR DELETE ON "ticket_sla_adjustments" FOR EACH ROW EXECUTE FUNCTION app_append_only();
--> statement-breakpoint
CREATE TRIGGER "ticket_sla_adjustments_no_truncate" BEFORE TRUNCATE ON "ticket_sla_adjustments" FOR EACH STATEMENT EXECUTE FUNCTION app_append_only();
--> statement-breakpoint
ALTER TABLE "ticket_escalations" FORCE ROW LEVEL SECURITY;
--> statement-breakpoint
CREATE TRIGGER "ticket_escalations_touch" BEFORE UPDATE ON "ticket_escalations" FOR EACH ROW EXECUTE FUNCTION app_touch_updated_at();
--> statement-breakpoint
ALTER TABLE "dispatch_attempts" FORCE ROW LEVEL SECURITY;
--> statement-breakpoint
CREATE TRIGGER "dispatch_attempts_touch" BEFORE UPDATE ON "dispatch_attempts" FOR EACH ROW EXECUTE FUNCTION app_touch_updated_at();
--> statement-breakpoint
ALTER TABLE "work_reassignment_requests" FORCE ROW LEVEL SECURITY;
--> statement-breakpoint
CREATE TRIGGER "work_reassignment_requests_touch" BEFORE UPDATE ON "work_reassignment_requests" FOR EACH ROW EXECUTE FUNCTION app_touch_updated_at();
--> statement-breakpoint
ALTER TABLE runtime_session_bindings ADD CONSTRAINT binding_identity_backend_fk FOREIGN KEY(tenant_id,identity_id,backend_id) REFERENCES runtime_identities(tenant_id,id,backend_id);
--> statement-breakpoint
CREATE INDEX dispatch_queue_priority_idx ON dispatch_queue(tenant_id,management_unit_id,is_emergency DESC,priority_rank DESC,dispatch_due_at,eligible_since,id) WHERE state='waiting';
--> statement-breakpoint
CREATE INDEX triage_reviews_due_idx ON ticket_triage_reviews(tenant_id,due_at) WHERE status IN ('pending','claimed');
--> statement-breakpoint
CREATE INDEX escalation_notify_idx ON ticket_escalations(tenant_id,next_notify_at) WHERE status IN ('open','acknowledged');
--> statement-breakpoint
CREATE INDEX knowledge_chunks_search_idx ON knowledge_chunks USING gin(search_tsv);
