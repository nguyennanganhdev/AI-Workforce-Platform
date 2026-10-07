ALTER TABLE mcp_servers ADD COLUMN status text NOT NULL DEFAULT 'active' CHECK(status IN ('active','suspended','pending'));
--> statement-breakpoint
ALTER TABLE mcp_servers ADD COLUMN suspension_reason text;
--> statement-breakpoint
CREATE TABLE vh_connection_policy(tenant_id uuid PRIMARY KEY REFERENCES tenants(id),require_approval boolean NOT NULL DEFAULT false,updated_at timestamptz NOT NULL DEFAULT now());
--> statement-breakpoint
ALTER TABLE vh_connection_policy ENABLE ROW LEVEL SECURITY;
--> statement-breakpoint
ALTER TABLE vh_connection_policy FORCE ROW LEVEL SECURITY;
--> statement-breakpoint
CREATE POLICY vh_connection_policy_tenant ON vh_connection_policy USING(tenant_id=nullif(current_setting('app.tenant_id',true),'')::uuid) WITH CHECK(tenant_id=nullif(current_setting('app.tenant_id',true),'')::uuid);
--> statement-breakpoint
CREATE TABLE vh_external_call_confirmations(id uuid PRIMARY KEY DEFAULT gen_random_uuid(),tenant_id uuid NOT NULL REFERENCES tenants(id),actor_user_id text NOT NULL REFERENCES users(id),channel_id text NOT NULL,agent_id text NOT NULL,version_id uuid NOT NULL,connection_id text NOT NULL,tool_name text NOT NULL,arguments jsonb NOT NULL,arguments_hash text NOT NULL,status text NOT NULL DEFAULT 'pending' CHECK(status IN ('pending','cancelled','executing','succeeded','failed','uncertain')),result jsonb,created_at timestamptz NOT NULL DEFAULT now(),expires_at timestamptz NOT NULL DEFAULT now()+interval '15 minutes',decided_at timestamptz,UNIQUE(tenant_id,id),FOREIGN KEY(tenant_id,channel_id) REFERENCES channels(tenant_id,id),FOREIGN KEY(tenant_id,connection_id) REFERENCES mcp_servers(tenant_id,id),FOREIGN KEY(tenant_id,version_id) REFERENCES agent_versions(tenant_id,id));
--> statement-breakpoint
ALTER TABLE vh_external_call_confirmations ENABLE ROW LEVEL SECURITY;
--> statement-breakpoint
ALTER TABLE vh_external_call_confirmations FORCE ROW LEVEL SECURITY;
--> statement-breakpoint
CREATE POLICY vh_external_call_confirmations_tenant ON vh_external_call_confirmations USING(tenant_id=nullif(current_setting('app.tenant_id',true),'')::uuid) WITH CHECK(tenant_id=nullif(current_setting('app.tenant_id',true),'')::uuid);
--> statement-breakpoint
CREATE TABLE vh_agent_skills(id uuid PRIMARY KEY DEFAULT gen_random_uuid(),tenant_id uuid NOT NULL REFERENCES tenants(id),workspace_id uuid,created_by text NOT NULL REFERENCES users(id),name text NOT NULL CHECK(length(name) BETWEEN 1 AND 160),description text NOT NULL DEFAULT '',instructions text NOT NULL CHECK(length(instructions) BETWEEN 1 AND 20000),created_at timestamptz NOT NULL DEFAULT now(),updated_at timestamptz NOT NULL DEFAULT now(),UNIQUE(tenant_id,id),FOREIGN KEY(tenant_id,workspace_id) REFERENCES workspaces(tenant_id,id));
--> statement-breakpoint
ALTER TABLE vh_agent_skills ENABLE ROW LEVEL SECURITY;
--> statement-breakpoint
ALTER TABLE vh_agent_skills FORCE ROW LEVEL SECURITY;
--> statement-breakpoint
CREATE POLICY vh_agent_skills_tenant ON vh_agent_skills USING(tenant_id=nullif(current_setting('app.tenant_id',true),'')::uuid) WITH CHECK(tenant_id=nullif(current_setting('app.tenant_id',true),'')::uuid);
--> statement-breakpoint
CREATE INDEX vh_external_call_pending ON vh_external_call_confirmations(tenant_id,channel_id,actor_user_id) WHERE status='pending';
