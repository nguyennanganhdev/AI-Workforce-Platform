-- Rights of the API's runtime role (called :role by the tool that applies this file).
-- The role must be a plain LOGIN role: not a superuser, no BYPASSRLS, so tenant row level security always applies.
-- Least privilege: read everywhere, write only where the code writes.
GRANT USAGE ON SCHEMA public TO :role;
GRANT INSERT,UPDATE,DELETE ON sessions TO :role;
GRANT INSERT,DELETE ON sign_in_attempts TO :role;
GRANT INSERT,UPDATE ON unit_residents,staff_profiles,staff_specialties,staff_shifts TO :role;
GRANT INSERT,UPDATE,DELETE ON password_reset_tokens TO :role;
GRANT INSERT,UPDATE ON accounts, users, tenant_memberships, scoped_user_roles, access_scopes TO :role;
GRANT SELECT ON ALL TABLES IN SCHEMA public TO :role;
-- Owner CSV staging contains personal records; neither the API, Reception nor MCP can read it.
REVOKE ALL ON owner_operational_batches,owner_operational_records FROM :role;
GRANT INSERT, UPDATE ON channels, channel_memberships, messages, integration_clients, tickets, ticket_events, ticket_routing_history, ticket_assessments, ticket_triage_decisions, ticket_triage_reviews, work_orders, work_assignments, work_approvals, service_interruptions, interruption_scopes, notification_deliveries, evidence_items, execution_principals, files, file_objects, ticket_files, vh_qc_results, vh_cleaning_plans, vh_security_checkpoints, vh_security_incidents, vh_security_handovers, vh_contractor_updates, vh_budget_approvals, vh_command_receipt, security_cameras, security_emergency_contacts, security_alerts, security_alert_deliveries, users, tenant_memberships, account_reviews, scoped_user_roles, audit_events, vh_ticket_plans, vh_assets, vh_sensor_readings, vh_technical_measurements, vh_maintenance_records, vh_operational_requests, vh_report_exports, vh_conversation_uploads TO :role;
GRANT SELECT, INSERT ON vh_qc_redo_orders TO :role;
GRANT DELETE ON channel_memberships TO :role;
GRANT INSERT ON management_units, management_coverage, access_scopes, workspaces, workspace_members TO :role;
GRANT INSERT,UPDATE ON file_uploads TO :role;
GRANT INSERT, UPDATE ON invoices, invoice_lines, payment_intents TO :role;
GRANT INSERT ON payments, payment_allocations, ticket_reviews TO :role;
GRANT INSERT,UPDATE ON integration_cases TO :role;
-- Entities of the golden scenarios: the API writes only what a person or an agent for them may do.
GRANT INSERT,UPDATE ON visitor_passes, access_cards, service_requests, amenity_bookings, announcements TO :role;
GRANT INSERT ON service_request_events, access_events, amenity_closures, event_outbox TO :role;
GRANT INSERT,UPDATE ON delegations TO :role;
GRANT INSERT,UPDATE ON vh_resident_cases, vh_resident_photos, vh_resident_outbox TO :role;
GRANT SELECT,INSERT ON vh_reception_supervisor_messages TO :role;
GRANT SELECT,INSERT,UPDATE,DELETE ON vh_reception_supervisor_pending TO :role;
GRANT INSERT ON vh_resident_submissions, vh_resident_case_tickets, vh_resident_resolutions, vh_resident_resolution_photos, vh_resident_resolution_responses, vh_resident_public_events, vh_resident_command_receipts TO :role;
GRANT UPDATE (availability) ON staff_profiles TO :role;
GRANT INSERT ON message_files TO :role;
-- The bridge to the AI platform: the API queues, the sync worker (same role) sends and records.
GRANT INSERT,UPDATE ON platform_links, platform_commands, platform_inbox, platform_approvals, platform_operations, platform_outbox TO :role;
GRANT INSERT ON platform_resident_assets TO :role;
-- Trusted platform control-plane issues grants automatically; only the operator may revoke via DB.
GRANT SELECT,INSERT ON platform_mcp_grants TO :role;
GRANT UPDATE(revoked_at) ON platform_mcp_grants TO :role;
GRANT SELECT ON platform_management_bindings TO :role;
-- Registered customer clients are provisioned by the database operator only.
GRANT INSERT,UPDATE ON platform_customer_codes,platform_customer_links,platform_customer_grants TO :role;
GRANT DELETE ON platform_customer_grants TO :role;
GRANT INSERT ON platform_customer_cases TO :role;
GRANT INSERT ON platform_customer_projection_acks TO :role;
GRANT UPDATE(content_hash,applied_at) ON platform_customer_projection_acks TO :role;
GRANT INSERT,UPDATE ON travel_mock_intents,travel_mock_bookings TO :role;
GRANT INSERT,UPDATE ON platform_connection_settings TO :role;
GRANT DELETE ON users, accounts, tenant_memberships, scoped_user_roles, workspace_members TO :role;
GRANT USAGE, SELECT ON ALL SEQUENCES IN SCHEMA public TO :role;
