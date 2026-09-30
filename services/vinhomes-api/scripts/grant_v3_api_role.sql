-- Run as the database owner after creating LOGIN role vinhomes_v3_api.
-- Keep the role subject to tenant row level security.
GRANT CONNECT ON DATABASE vinhomes_v3 TO vinhomes_v3_api;
GRANT USAGE ON SCHEMA public TO vinhomes_v3_api;
GRANT SELECT ON ALL TABLES IN SCHEMA public TO vinhomes_v3_api;
GRANT INSERT, UPDATE ON
  channels, tickets, ticket_events, ticket_assessments,
  ticket_triage_decisions, ticket_triage_reviews,
  work_orders, work_assignments, work_approvals,
  evidence_items, execution_principals, files, file_objects, ticket_files,
  vh_qc_results, vh_cleaning_plans, vh_security_checkpoints,
  vh_security_incidents, vh_security_handovers, vh_contractor_updates,
  vh_budget_approvals
TO vinhomes_v3_api;
GRANT SELECT, INSERT ON vh_qc_redo_orders TO vinhomes_v3_api;
GRANT USAGE, SELECT ON ALL SEQUENCES IN SCHEMA public TO vinhomes_v3_api;
