ALTER TABLE channels DROP CONSTRAINT channels_check_0;
--> statement-breakpoint
ALTER TABLE channels ADD CONSTRAINT channels_check_0 CHECK ((kind='reception' AND workspace_id IS NULL) OR (kind IN ('management','agent_builder','personal') AND workspace_id IS NOT NULL));
--> statement-breakpoint
ALTER TABLE channels DROP CONSTRAINT channels_check_1;
--> statement-breakpoint
ALTER TABLE channels ADD CONSTRAINT channels_check_1 CHECK (kind IN ('reception','management','agent_builder','personal'));
--> statement-breakpoint
CREATE TABLE vh_private_chats (
  tenant_id uuid NOT NULL DEFAULT nullif(current_setting('app.tenant_id',true),'')::uuid,
  channel_id text NOT NULL,
  parent_channel_id text NOT NULL,
  owner_user_id text NOT NULL REFERENCES users(id) ON DELETE RESTRICT,
  request_id text NOT NULL,
  created_at timestamptz NOT NULL DEFAULT now(),
  PRIMARY KEY (tenant_id,channel_id),
  UNIQUE (tenant_id,owner_user_id,request_id),
  FOREIGN KEY (tenant_id,channel_id) REFERENCES channels(tenant_id,id) ON DELETE RESTRICT,
  FOREIGN KEY (tenant_id,parent_channel_id) REFERENCES channels(tenant_id,id) ON DELETE RESTRICT
);
--> statement-breakpoint
ALTER TABLE vh_private_chats ENABLE ROW LEVEL SECURITY;
--> statement-breakpoint
ALTER TABLE vh_private_chats FORCE ROW LEVEL SECURITY;
--> statement-breakpoint
CREATE POLICY vh_private_chats_tenant ON vh_private_chats USING (tenant_id=nullif(current_setting('app.tenant_id',true),'')::uuid) WITH CHECK (tenant_id=nullif(current_setting('app.tenant_id',true),'')::uuid);
--> statement-breakpoint
CREATE TABLE vh_private_chat_sources (
  tenant_id uuid NOT NULL DEFAULT nullif(current_setting('app.tenant_id',true),'')::uuid,
  channel_id text NOT NULL,
  server_id text NOT NULL,
  enabled boolean NOT NULL DEFAULT false,
  PRIMARY KEY (tenant_id,channel_id,server_id),
  FOREIGN KEY (tenant_id,channel_id) REFERENCES vh_private_chats(tenant_id,channel_id) ON DELETE RESTRICT,
  FOREIGN KEY (tenant_id,server_id) REFERENCES mcp_servers(tenant_id,id) ON DELETE RESTRICT
);
--> statement-breakpoint
ALTER TABLE vh_private_chat_sources ENABLE ROW LEVEL SECURITY;
--> statement-breakpoint
ALTER TABLE vh_private_chat_sources FORCE ROW LEVEL SECURITY;
--> statement-breakpoint
CREATE POLICY vh_private_chat_sources_tenant ON vh_private_chat_sources USING (tenant_id=nullif(current_setting('app.tenant_id',true),'')::uuid) WITH CHECK (tenant_id=nullif(current_setting('app.tenant_id',true),'')::uuid);
