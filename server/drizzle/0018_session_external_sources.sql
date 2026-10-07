CREATE TABLE vh_session_sources (
  tenant_id uuid NOT NULL DEFAULT nullif(current_setting('app.tenant_id',true),'')::uuid,
  team_id uuid NOT NULL,
  actor_user_id text NOT NULL REFERENCES users(id),
  server_id text NOT NULL,
  enabled boolean NOT NULL DEFAULT false,
  updated_at timestamptz NOT NULL DEFAULT now(),
  PRIMARY KEY (tenant_id,team_id,actor_user_id,server_id),
  FOREIGN KEY (tenant_id,team_id) REFERENCES agent_teams(tenant_id,id),
  FOREIGN KEY (tenant_id,server_id) REFERENCES mcp_servers(tenant_id,id)
);
--> statement-breakpoint
ALTER TABLE vh_session_sources ENABLE ROW LEVEL SECURITY;
--> statement-breakpoint
ALTER TABLE vh_session_sources FORCE ROW LEVEL SECURITY;
--> statement-breakpoint
CREATE POLICY vh_session_sources_tenant ON vh_session_sources USING (tenant_id=nullif(current_setting('app.tenant_id',true),'')::uuid) WITH CHECK (tenant_id=nullif(current_setting('app.tenant_id',true),'')::uuid);
--> statement-breakpoint
ALTER TABLE vh_external_call_confirmations ADD COLUMN session_id uuid;
--> statement-breakpoint
ALTER TABLE vh_external_call_confirmations ADD COLUMN request_message_id uuid;
--> statement-breakpoint
ALTER TABLE vh_external_call_confirmations ADD CONSTRAINT vh_external_call_session_pair CHECK ((session_id IS NULL) = (request_message_id IS NULL));
--> statement-breakpoint
ALTER TABLE vh_external_call_confirmations ADD CONSTRAINT vh_external_call_session_fk FOREIGN KEY (tenant_id,session_id) REFERENCES agent_teams(tenant_id,id);
--> statement-breakpoint
ALTER TABLE vh_external_call_confirmations ADD CONSTRAINT vh_external_call_message_fk FOREIGN KEY (tenant_id,request_message_id) REFERENCES messages(tenant_id,id);
