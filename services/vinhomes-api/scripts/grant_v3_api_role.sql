-- Run as the database owner after creating LOGIN role vinhomes_v3_api.
-- Keep the role subject to tenant row level security.
GRANT CONNECT ON DATABASE vinhomes_v3 TO vinhomes_v3_api;
GRANT USAGE ON SCHEMA public TO vinhomes_v3_api;
-- Password/session APIs are part of every packaged deployment, not only the local setup script.
GRANT INSERT,UPDATE,DELETE ON sessions TO vinhomes_v3_api;
GRANT INSERT,UPDATE ON accounts,users,tenant_memberships,scoped_user_roles,access_scopes TO vinhomes_v3_api;
GRANT SELECT ON ALL TABLES IN SCHEMA public TO vinhomes_v3_api;
GRANT INSERT, UPDATE ON
  channels, channel_memberships, messages, message_mentions, channel_agents, agents,
  tickets, ticket_events, ticket_routing_history, ticket_assessments,
  ticket_triage_decisions, ticket_triage_reviews,
  work_orders, work_assignments, work_approvals, service_interruptions,
  interruption_scopes, notification_deliveries, memory_candidates, knowledge_reviews,
  evidence_items, execution_principals, files, file_objects, ticket_files,
  vh_qc_results, vh_cleaning_plans, vh_security_checkpoints,
  vh_security_incidents, vh_security_handovers, vh_contractor_updates,
  vh_budget_approvals,
  vh_command_receipt,
  security_cameras,security_emergency_contacts,security_alerts,security_alert_deliveries,
  users,tenant_memberships,account_reviews,scoped_user_roles,audit_events,
  vh_ticket_plans,vh_assets,vh_sensor_readings,vh_technical_measurements,
  vh_maintenance_records,vh_operational_requests,vh_agent_reviews,vh_report_exports,
  vh_conversation_uploads
TO vinhomes_v3_api;
GRANT SELECT, INSERT ON vh_qc_redo_orders TO vinhomes_v3_api;
-- An administrator moves a management account between units: it leaves the rooms of the old one.
GRANT DELETE ON channel_memberships TO vinhomes_v3_api;
-- Platform administrators provision a management unit and its room atomically.
GRANT INSERT ON management_units,management_coverage,access_scopes,workspaces,workspace_members TO vinhomes_v3_api;
GRANT INSERT,UPDATE ON file_uploads TO vinhomes_v3_api;
GRANT INSERT, UPDATE ON invoices,invoice_lines,payment_intents TO vinhomes_v3_api;
GRANT INSERT ON payments,payment_allocations,ticket_reviews TO vinhomes_v3_api;
GRANT INSERT ON agent_versions TO vinhomes_v3_api;
-- External MCP connections an administrator sets up for agents: the server, the tools it allowed,
-- and the sealed token (the tool host holds the key; this role only stores the sealed form).
GRANT INSERT, UPDATE, DELETE ON mcp_servers, mcp_tools TO vinhomes_v3_api;
GRANT INSERT, UPDATE ON credentials TO vinhomes_v3_api;
-- Admin approval publishes a version; an admin can revoke it.
GRANT INSERT,UPDATE ON agent_releases TO vinhomes_v3_api;
GRANT INSERT,UPDATE ON agent_teams,team_members,team_tasks TO vinhomes_v3_api;
-- One run per resident message, bound to the conversation's Reception session.
GRANT INSERT ON runtime_identities,runtime_session_bindings TO vinhomes_v3_api;
-- Completed one-off room conversations close their personal binding before the next turn.
GRANT UPDATE (status) ON runtime_session_bindings TO vinhomes_v3_api;
GRANT INSERT,UPDATE ON agent_runs TO vinhomes_v3_api;
-- The knowledge search service audits every retrieval under this role.
GRANT INSERT ON retrieval_runs,retrieval_hits TO vinhomes_v3_api;
GRANT INSERT ON team_mailbox TO vinhomes_v3_api;
GRANT INSERT,UPDATE ON vh_resident_cases,vh_resident_photos,vh_resident_outbox TO vinhomes_v3_api;
GRANT SELECT,INSERT ON vh_reception_supervisor_messages TO vinhomes_v3_api;
GRANT SELECT,INSERT,UPDATE,DELETE ON vh_reception_supervisor_pending TO vinhomes_v3_api;
GRANT INSERT ON vh_resident_submissions,vh_resident_case_tickets,vh_resident_resolutions,
  vh_resident_resolution_photos,vh_resident_resolution_responses,vh_resident_public_events,
  vh_resident_command_receipts TO vinhomes_v3_api;
-- SELECT FOR UPDATE serializes dispatch capacity checks on the staff row.
GRANT UPDATE (availability) ON staff_profiles TO vinhomes_v3_api;
-- Photos and files attached to a message of a management room.
GRANT INSERT ON message_files TO vinhomes_v3_api;
-- A schedule's run is closed by what became of its mention in the room; the schedule service keeps the rest.
GRANT UPDATE (status, finished_at, error) ON routine_runs TO vinhomes_v3_api;
GRANT USAGE, SELECT ON ALL SEQUENCES IN SCHEMA public TO vinhomes_v3_api;
