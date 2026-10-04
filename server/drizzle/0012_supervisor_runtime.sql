-- The Coordination runtime (agent-coordination) runs the Supervisor of a management room and
-- keeps its checkpoints in its own store. Registering it lets the business API bind one
-- session per ticket generation. Disable the row to stop every Supervisor delegation at once.
INSERT INTO runtime_backends (code, framework, sdk_language, package_version, backend_kind, connection_secret_ref, schema_name)
VALUES ('coordination-agentscope', 'agentscope', 'python', '2.0.9', 'custom', 'COORDINATION_STATE_PATH', 'coordination')
ON CONFLICT (code) DO NOTHING;
--> statement-breakpoint
-- A Supervisor result is written by the Supervisor agent of the team, not by a person.
ALTER TABLE vh_reception_supervisor_messages ALTER COLUMN created_by DROP NOT NULL;
--> statement-breakpoint
ALTER TABLE vh_reception_supervisor_messages ADD COLUMN created_by_agent_id text;
--> statement-breakpoint
ALTER TABLE vh_reception_supervisor_messages
  ADD CONSTRAINT vh_reception_supervisor_messages_created_by_agent_fk
  FOREIGN KEY(tenant_id,created_by_agent_id) REFERENCES agents(tenant_id,id) ON DELETE RESTRICT;
--> statement-breakpoint
ALTER TABLE vh_reception_supervisor_messages
  ADD CONSTRAINT vh_reception_supervisor_messages_author_check
  CHECK(num_nonnulls(created_by,created_by_agent_id)=1);
