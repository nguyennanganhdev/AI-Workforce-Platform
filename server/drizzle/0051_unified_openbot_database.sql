-- Forward migration for the user-confirmed empty local development database.
-- Refuse populated business/runtime data; never silently discard or invent identity mappings.
DO $$ DECLARE r record; occupied boolean;
BEGIN
  FOR r IN SELECT tablename FROM pg_tables WHERE schemaname='public' AND
    (tablename LIKE 'platform\_%' ESCAPE '\' OR tablename LIKE 'vh\_%' ESCAPE '\'
      OR tablename = ANY(ARRAY['agent_preferences','agent_profiles','agents','attachments','audit_events','channel_agents','channel_memberships','channels','composio_connections','credentials','intelligence_channel_mappings','mcp_servers','mcp_tools','mcp_user_credentials','plugin_grants','routine_runs','routines','sandboxed_components','skill_tools','skills','voice_sessions']))
  LOOP
    EXECUTE format('SELECT EXISTS(SELECT 1 FROM %I LIMIT 1)',r.tablename) INTO occupied;
    IF occupied THEN RAISE EXCEPTION '0051 requires empty local data; table % is populated. Export and map data explicitly before upgrade.',r.tablename; END IF;
  END LOOP;
END $$;
--> statement-breakpoint
ALTER TABLE "platform_agent_change_request" DROP CONSTRAINT IF EXISTS "platform_agent_change_request_fk_1";
--> statement-breakpoint
ALTER TABLE "platform_agent_version" DROP CONSTRAINT IF EXISTS "platform_agent_version_fk_1";
--> statement-breakpoint
ALTER TABLE "platform_mcp_server_version" DROP CONSTRAINT IF EXISTS "platform_mcp_server_version_fk_1";
--> statement-breakpoint
ALTER TABLE "platform_skill_version" DROP CONSTRAINT IF EXISTS "platform_skill_version_fk_1";
--> statement-breakpoint
ALTER TABLE "platform_regression_baseline" DROP CONSTRAINT IF EXISTS "platform_regression_baseline_fk_1";
--> statement-breakpoint
ALTER TABLE "platform_regression_baseline" DROP CONSTRAINT IF EXISTS "platform_regression_baseline_fk_2";
--> statement-breakpoint
ALTER TABLE "platform_regression_baseline" DROP CONSTRAINT IF EXISTS "platform_regression_baseline_fk_5";
--> statement-breakpoint
ALTER TABLE "platform_agent_run" DROP CONSTRAINT IF EXISTS "platform_agent_run_fk_3";
--> statement-breakpoint
ALTER TABLE "platform_agent_run" DROP CONSTRAINT IF EXISTS "platform_agent_run_fk_4";
--> statement-breakpoint
CREATE TABLE "channel_messages" (
	"id" uuid PRIMARY KEY DEFAULT gen_random_uuid() NOT NULL,
	"tenant_id" uuid NOT NULL,
	"channel_id" text NOT NULL,
	"sequence_no" bigint NOT NULL,
	"role" text NOT NULL,
	"author_user_id" text,
	"author_agent_id" text,
	"content_parts" jsonb DEFAULT '[]'::jsonb NOT NULL,
	"agent_version_id" uuid,
	"body" text NOT NULL,
	"content_schema_version" integer NOT NULL,
	"metadata_json" jsonb NOT NULL,
	"idempotency_key" text NOT NULL,
	"reply_to_message_id" uuid,
	"source_event_ref" text,
	"source_subject_version" bigint,
	"created_at" timestamp with time zone DEFAULT now() NOT NULL,
	CONSTRAINT "channel_messages_uq_0" UNIQUE("tenant_id","channel_id","sequence_no"),
	CONSTRAINT "channel_messages_uq_1" UNIQUE("tenant_id","channel_id","idempotency_key"),
	CONSTRAINT "channel_messages_uq_2" UNIQUE("tenant_id","id"),
	CONSTRAINT "channel_messages_uq_3" UNIQUE("tenant_id","channel_id","id"),
	CONSTRAINT "channel_messages_parts_ck" CHECK (jsonb_typeof(content_parts) = 'array'),
	CONSTRAINT "channel_messages_role_ck" CHECK ("channel_messages"."role" in ('USER', 'ASSISTANT', 'SYSTEM')),
	CONSTRAINT "channel_messages_ck_0" CHECK (sequence_no > 0),
	CONSTRAINT "channel_messages_ck_1" CHECK (content_schema_version > 0),
	CONSTRAINT "channel_messages_ck_2" CHECK ((role='USER' AND author_user_id IS NOT NULL AND author_agent_id IS NULL AND agent_version_id IS NULL) OR (role='ASSISTANT' AND author_agent_id IS NOT NULL AND author_user_id IS NULL) OR (role='SYSTEM' AND author_user_id IS NULL AND author_agent_id IS NULL AND agent_version_id IS NULL))
);
--> statement-breakpoint
ALTER TABLE "channel_messages" ENABLE ROW LEVEL SECURITY;--> statement-breakpoint
CREATE TABLE "channel_subjects" (
	"tenant_id" uuid NOT NULL,
	"channel_id" text NOT NULL,
	"domain_namespace" text NOT NULL,
	"subject_type" text NOT NULL,
	"subject_ref" text NOT NULL,
	"relationship" text NOT NULL,
	"created_at" timestamp with time zone DEFAULT now() NOT NULL,
	CONSTRAINT "channel_subjects_pk" PRIMARY KEY("tenant_id","channel_id","domain_namespace","subject_type","subject_ref"),
	CONSTRAINT "channel_subjects_relationship_ck" CHECK ("channel_subjects"."relationship" in ('INTAKE', 'TRACKING', 'FOLLOW_UP'))
);
--> statement-breakpoint
ALTER TABLE "channel_subjects" ENABLE ROW LEVEL SECURITY;--> statement-breakpoint
ALTER TABLE "agents" ENABLE ROW LEVEL SECURITY;--> statement-breakpoint
ALTER TABLE "attachments" ENABLE ROW LEVEL SECURITY;--> statement-breakpoint
ALTER TABLE "audit_events" ENABLE ROW LEVEL SECURITY;--> statement-breakpoint
ALTER TABLE "channel_agents" ENABLE ROW LEVEL SECURITY;--> statement-breakpoint
ALTER TABLE "channel_memberships" ENABLE ROW LEVEL SECURITY;--> statement-breakpoint
ALTER TABLE "channels" ENABLE ROW LEVEL SECURITY;--> statement-breakpoint
ALTER TABLE "credentials" ENABLE ROW LEVEL SECURITY;--> statement-breakpoint
ALTER TABLE "intelligence_channel_mappings" ENABLE ROW LEVEL SECURITY;--> statement-breakpoint
ALTER TABLE "agent_preferences" ENABLE ROW LEVEL SECURITY;--> statement-breakpoint
ALTER TABLE "agent_profiles" ENABLE ROW LEVEL SECURITY;--> statement-breakpoint
ALTER TABLE "routine_runs" ENABLE ROW LEVEL SECURITY;--> statement-breakpoint
ALTER TABLE "routines" ENABLE ROW LEVEL SECURITY;--> statement-breakpoint
ALTER TABLE "composio_connections" ENABLE ROW LEVEL SECURITY;--> statement-breakpoint
ALTER TABLE "mcp_servers" ENABLE ROW LEVEL SECURITY;--> statement-breakpoint
ALTER TABLE "mcp_tools" ENABLE ROW LEVEL SECURITY;--> statement-breakpoint
ALTER TABLE "mcp_user_credentials" ENABLE ROW LEVEL SECURITY;--> statement-breakpoint
ALTER TABLE "plugin_grants" ENABLE ROW LEVEL SECURITY;--> statement-breakpoint
ALTER TABLE "sandboxed_components" ENABLE ROW LEVEL SECURITY;--> statement-breakpoint
ALTER TABLE "skill_tools" ENABLE ROW LEVEL SECURITY;--> statement-breakpoint
ALTER TABLE "skills" ENABLE ROW LEVEL SECURITY;--> statement-breakpoint
ALTER TABLE "voice_sessions" ENABLE ROW LEVEL SECURITY;--> statement-breakpoint
DROP POLICY "platform_agent_tenant_policy" ON "platform_agent" CASCADE;--> statement-breakpoint
DROP TABLE "platform_agent" CASCADE;--> statement-breakpoint
DROP POLICY "platform_mcp_server_tenant_policy" ON "platform_mcp_server" CASCADE;--> statement-breakpoint
DROP TABLE "platform_mcp_server" CASCADE;--> statement-breakpoint
DROP POLICY "platform_skill_tenant_policy" ON "platform_skill" CASCADE;--> statement-breakpoint
DROP TABLE "platform_skill" CASCADE;--> statement-breakpoint
DROP POLICY "platform_conversation_tenant_policy" ON "platform_conversation" CASCADE;--> statement-breakpoint
DROP TABLE "platform_conversation" CASCADE;--> statement-breakpoint
DROP POLICY "platform_conversation_message_tenant_policy" ON "platform_conversation_message" CASCADE;--> statement-breakpoint
DROP TABLE "platform_conversation_message" CASCADE;--> statement-breakpoint
DROP POLICY "platform_conversation_subject_tenant_policy" ON "platform_conversation_subject" CASCADE;--> statement-breakpoint
DROP TABLE "platform_conversation_subject" CASCADE;--> statement-breakpoint
ALTER TABLE "platform_handoff" DROP CONSTRAINT IF EXISTS "platform_handoff_ck_0";--> statement-breakpoint
ALTER TABLE "platform_agent_change_request" DROP CONSTRAINT IF EXISTS "platform_agent_change_request_fk_1";
--> statement-breakpoint
ALTER TABLE "platform_agent_version" DROP CONSTRAINT IF EXISTS "platform_agent_version_fk_1";
--> statement-breakpoint
ALTER TABLE "platform_mcp_server_version" DROP CONSTRAINT IF EXISTS "platform_mcp_server_version_fk_1";
--> statement-breakpoint
ALTER TABLE "platform_skill_version" DROP CONSTRAINT IF EXISTS "platform_skill_version_fk_1";
--> statement-breakpoint
ALTER TABLE "platform_regression_baseline" DROP CONSTRAINT IF EXISTS "platform_regression_baseline_fk_1";
--> statement-breakpoint
ALTER TABLE "platform_agent_run" DROP CONSTRAINT IF EXISTS "platform_agent_run_fk_3";
--> statement-breakpoint
ALTER TABLE "platform_handoff" DROP CONSTRAINT IF EXISTS "platform_handoff_fk_1";
--> statement-breakpoint
DROP INDEX "skills_slug_key";--> statement-breakpoint
DROP INDEX "platform_handoff_ix_1";--> statement-breakpoint
ALTER TABLE "platform_agent_change_request" ALTER COLUMN "agent_id" SET DATA TYPE text;--> statement-breakpoint
ALTER TABLE "platform_agent_version" ALTER COLUMN "agent_id" SET DATA TYPE text;--> statement-breakpoint
ALTER TABLE "platform_mcp_server_version" ALTER COLUMN "mcp_server_id" SET DATA TYPE text;--> statement-breakpoint
ALTER TABLE "platform_skill_version" ALTER COLUMN "skill_id" SET DATA TYPE text;--> statement-breakpoint
ALTER TABLE "platform_regression_baseline" ALTER COLUMN "agent_id" SET DATA TYPE text;--> statement-breakpoint
ALTER TABLE "platform_agent_run" ALTER COLUMN "agent_id" SET DATA TYPE text;--> statement-breakpoint
ALTER TABLE "agents" ADD COLUMN "description" text;--> statement-breakpoint
ALTER TABLE "agents" ADD COLUMN "domain_namespace" text;--> statement-breakpoint
ALTER TABLE "agents" ADD COLUMN "status" text DEFAULT 'ACTIVE' NOT NULL;--> statement-breakpoint
ALTER TABLE "agents" ADD COLUMN "revision" bigint DEFAULT 1 NOT NULL;--> statement-breakpoint
ALTER TABLE "agents" ADD COLUMN "tenant_id" uuid DEFAULT nullif(current_setting('app.tenant_id', true), '')::uuid NOT NULL;--> statement-breakpoint
ALTER TABLE "attachments" ADD COLUMN "tenant_id" uuid DEFAULT nullif(current_setting('app.tenant_id', true), '')::uuid NOT NULL;--> statement-breakpoint
ALTER TABLE "audit_events" ADD COLUMN "tenant_id" uuid DEFAULT nullif(current_setting('app.tenant_id', true), '')::uuid NOT NULL;--> statement-breakpoint
ALTER TABLE "channel_agents" ADD COLUMN "tenant_id" uuid DEFAULT nullif(current_setting('app.tenant_id', true), '')::uuid NOT NULL;--> statement-breakpoint
ALTER TABLE "channel_memberships" ADD COLUMN "tenant_id" uuid DEFAULT nullif(current_setting('app.tenant_id', true), '')::uuid NOT NULL;--> statement-breakpoint
ALTER TABLE "channels" ADD COLUMN "channel_kind" text DEFAULT 'RESIDENT' NOT NULL;--> statement-breakpoint
ALTER TABLE "channels" ADD COLUMN "locale" text DEFAULT 'vi-VN' NOT NULL;--> statement-breakpoint
ALTER TABLE "channels" ADD COLUMN "created_by_user_id" text;--> statement-breakpoint
ALTER TABLE "channels" ADD COLUMN "status" text DEFAULT 'ACTIVE' NOT NULL;--> statement-breakpoint
ALTER TABLE "channels" ADD COLUMN "revision" bigint DEFAULT 1 NOT NULL;--> statement-breakpoint
ALTER TABLE "channels" ADD COLUMN "tenant_id" uuid DEFAULT nullif(current_setting('app.tenant_id', true), '')::uuid NOT NULL;--> statement-breakpoint
ALTER TABLE "credentials" ADD COLUMN "tenant_id" uuid DEFAULT nullif(current_setting('app.tenant_id', true), '')::uuid NOT NULL;--> statement-breakpoint
ALTER TABLE "intelligence_channel_mappings" ADD COLUMN "tenant_id" uuid DEFAULT nullif(current_setting('app.tenant_id', true), '')::uuid NOT NULL;--> statement-breakpoint
ALTER TABLE "agent_preferences" ADD COLUMN "tenant_id" uuid DEFAULT nullif(current_setting('app.tenant_id', true), '')::uuid NOT NULL;--> statement-breakpoint
ALTER TABLE "agent_profiles" ADD COLUMN "tenant_id" uuid DEFAULT nullif(current_setting('app.tenant_id', true), '')::uuid NOT NULL;--> statement-breakpoint
ALTER TABLE "routine_runs" ADD COLUMN "tenant_id" uuid DEFAULT nullif(current_setting('app.tenant_id', true), '')::uuid NOT NULL;--> statement-breakpoint
ALTER TABLE "routines" ADD COLUMN "tenant_id" uuid DEFAULT nullif(current_setting('app.tenant_id', true), '')::uuid NOT NULL;--> statement-breakpoint
ALTER TABLE "composio_connections" ADD COLUMN "tenant_id" uuid DEFAULT nullif(current_setting('app.tenant_id', true), '')::uuid NOT NULL;--> statement-breakpoint
ALTER TABLE "mcp_servers" ADD COLUMN "status" text DEFAULT 'ACTIVE' NOT NULL;--> statement-breakpoint
ALTER TABLE "mcp_servers" ADD COLUMN "revision" bigint DEFAULT 1 NOT NULL;--> statement-breakpoint
ALTER TABLE "mcp_servers" ADD COLUMN "tenant_id" uuid DEFAULT nullif(current_setting('app.tenant_id', true), '')::uuid NOT NULL;--> statement-breakpoint
ALTER TABLE "mcp_tools" ADD COLUMN "tenant_id" uuid DEFAULT nullif(current_setting('app.tenant_id', true), '')::uuid NOT NULL;--> statement-breakpoint
ALTER TABLE "mcp_user_credentials" ADD COLUMN "tenant_id" uuid DEFAULT nullif(current_setting('app.tenant_id', true), '')::uuid NOT NULL;--> statement-breakpoint
ALTER TABLE "plugin_grants" ADD COLUMN "tenant_id" uuid DEFAULT nullif(current_setting('app.tenant_id', true), '')::uuid NOT NULL;--> statement-breakpoint
ALTER TABLE "sandboxed_components" ADD COLUMN "tenant_id" uuid DEFAULT nullif(current_setting('app.tenant_id', true), '')::uuid NOT NULL;--> statement-breakpoint
ALTER TABLE "skill_tools" ADD COLUMN "tenant_id" uuid DEFAULT nullif(current_setting('app.tenant_id', true), '')::uuid NOT NULL;--> statement-breakpoint
ALTER TABLE "skills" ADD COLUMN "status" text DEFAULT 'ACTIVE' NOT NULL;--> statement-breakpoint
ALTER TABLE "skills" ADD COLUMN "revision" bigint DEFAULT 1 NOT NULL;--> statement-breakpoint
ALTER TABLE "skills" ADD COLUMN "tenant_id" uuid DEFAULT nullif(current_setting('app.tenant_id', true), '')::uuid NOT NULL;--> statement-breakpoint
ALTER TABLE "voice_sessions" ADD COLUMN "tenant_id" uuid DEFAULT nullif(current_setting('app.tenant_id', true), '')::uuid NOT NULL;--> statement-breakpoint
ALTER TABLE "platform_tool" ADD COLUMN "provider_type" text NOT NULL;--> statement-breakpoint
ALTER TABLE "platform_tool" ADD COLUMN "mcp_server_id" text;--> statement-breakpoint
ALTER TABLE "platform_tool" ADD COLUMN "mcp_tool_name" text;--> statement-breakpoint
ALTER TABLE "platform_tool" ADD COLUMN "handler_key" text;--> statement-breakpoint
ALTER TABLE "platform_handoff" ADD COLUMN "source_channel_id" text;--> statement-breakpoint
ALTER TABLE "agents" ADD CONSTRAINT "agents_tenant_id_key" UNIQUE("tenant_id","id");--> statement-breakpoint
ALTER TABLE "attachments" ADD CONSTRAINT "attachments_tenant_pk" UNIQUE("tenant_id","id");--> statement-breakpoint
ALTER TABLE "audit_events" ADD CONSTRAINT "audit_events_tenant_pk" UNIQUE("tenant_id","id");--> statement-breakpoint
ALTER TABLE "channels" ADD CONSTRAINT "channels_tenant_id_key" UNIQUE("tenant_id","id");--> statement-breakpoint
ALTER TABLE "credentials" ADD CONSTRAINT "credentials_tenant_id_key" UNIQUE("tenant_id","id");--> statement-breakpoint
ALTER TABLE "intelligence_channel_mappings" ADD CONSTRAINT "intelligence_channel_mappings_tenant_pk" UNIQUE("tenant_id","user_id","channel_id");--> statement-breakpoint
ALTER TABLE "agent_preferences" ADD CONSTRAINT "agent_preferences_tenant_pk" UNIQUE("tenant_id","user_id","agent_id");--> statement-breakpoint
ALTER TABLE "agent_profiles" ADD CONSTRAINT "agent_profiles_tenant_pk" UNIQUE("tenant_id","agent_id");--> statement-breakpoint
ALTER TABLE "routine_runs" ADD CONSTRAINT "routine_runs_tenant_pk" UNIQUE("tenant_id","id");--> statement-breakpoint
ALTER TABLE "routines" ADD CONSTRAINT "routines_tenant_pk" UNIQUE("tenant_id","id");--> statement-breakpoint
ALTER TABLE "composio_connections" ADD CONSTRAINT "composio_connections_tenant_pk" UNIQUE("tenant_id","toolkit","user_id");--> statement-breakpoint
ALTER TABLE "mcp_servers" ADD CONSTRAINT "mcp_servers_tenant_id_key" UNIQUE("tenant_id","id");--> statement-breakpoint
ALTER TABLE "mcp_tools" ADD CONSTRAINT "mcp_tools_tenant_pk" UNIQUE("tenant_id","server_id","name");--> statement-breakpoint
ALTER TABLE "mcp_user_credentials" ADD CONSTRAINT "mcp_user_credentials_tenant_pk" UNIQUE("tenant_id","server_id","user_id");--> statement-breakpoint
ALTER TABLE "plugin_grants" ADD CONSTRAINT "plugin_grants_tenant_pk" UNIQUE("tenant_id","kind","ref","agent_id");--> statement-breakpoint
ALTER TABLE "sandboxed_components" ADD CONSTRAINT "sandboxed_components_tenant_pk" UNIQUE("tenant_id","name");--> statement-breakpoint
ALTER TABLE "skill_tools" ADD CONSTRAINT "skill_tools_tenant_pk" UNIQUE("tenant_id","skill_id","ref");--> statement-breakpoint
ALTER TABLE "skills" ADD CONSTRAINT "skills_tenant_id_key" UNIQUE("tenant_id","id");--> statement-breakpoint
ALTER TABLE "voice_sessions" ADD CONSTRAINT "voice_sessions_tenant_pk" UNIQUE("tenant_id","id");--> statement-breakpoint
ALTER TABLE "platform_tool" ADD CONSTRAINT "platform_tool_mcp_identity_key" UNIQUE("tenant_id","mcp_server_id","mcp_tool_name");--> statement-breakpoint
ALTER TABLE "platform_tool" ADD CONSTRAINT "platform_tool_handler_key" UNIQUE("tenant_id","provider_type","handler_key");--> statement-breakpoint
ALTER TABLE "channel_messages" ADD CONSTRAINT "channel_messages_agent_fk" FOREIGN KEY ("tenant_id","author_agent_id") REFERENCES "public"."agents"("tenant_id","id") ON DELETE restrict ON UPDATE no action;--> statement-breakpoint
ALTER TABLE "channel_messages" ADD CONSTRAINT "channel_messages_agent_version_fk" FOREIGN KEY ("tenant_id","author_agent_id","agent_version_id") REFERENCES "public"."platform_agent_version"("tenant_id","agent_id","id") ON DELETE restrict ON UPDATE no action;--> statement-breakpoint
ALTER TABLE "channel_messages" ADD CONSTRAINT "channel_messages_fk_0" FOREIGN KEY ("tenant_id") REFERENCES "public"."platform_tenant"("id") ON DELETE restrict ON UPDATE no action;--> statement-breakpoint
ALTER TABLE "channel_messages" ADD CONSTRAINT "channel_messages_fk_1" FOREIGN KEY ("tenant_id","channel_id") REFERENCES "public"."channels"("tenant_id","id") ON DELETE restrict ON UPDATE no action;--> statement-breakpoint
ALTER TABLE "channel_messages" ADD CONSTRAINT "channel_messages_fk_2" FOREIGN KEY ("author_user_id") REFERENCES "public"."users"("id") ON DELETE restrict ON UPDATE no action;--> statement-breakpoint
ALTER TABLE "channel_messages" ADD CONSTRAINT "channel_messages_fk_3" FOREIGN KEY ("tenant_id","agent_version_id") REFERENCES "public"."platform_agent_version"("tenant_id","id") ON DELETE restrict ON UPDATE no action;--> statement-breakpoint
ALTER TABLE "channel_messages" ADD CONSTRAINT "channel_messages_fk_4" FOREIGN KEY ("tenant_id","channel_id","reply_to_message_id") REFERENCES "public"."channel_messages"("tenant_id","channel_id","id") ON DELETE restrict ON UPDATE no action;--> statement-breakpoint
ALTER TABLE "channel_subjects" ADD CONSTRAINT "channel_subjects_fk_0" FOREIGN KEY ("tenant_id") REFERENCES "public"."platform_tenant"("id") ON DELETE restrict ON UPDATE no action;--> statement-breakpoint
ALTER TABLE "channel_subjects" ADD CONSTRAINT "channel_subjects_fk_1" FOREIGN KEY ("tenant_id","channel_id") REFERENCES "public"."channels"("tenant_id","id") ON DELETE restrict ON UPDATE no action;--> statement-breakpoint
CREATE INDEX "channel_messages_ix_0" ON "channel_messages" USING btree ("author_user_id");--> statement-breakpoint
CREATE INDEX "channel_messages_ix_2" ON "channel_messages" USING btree ("tenant_id","agent_version_id");--> statement-breakpoint
CREATE INDEX "channel_messages_ix_3" ON "channel_messages" USING btree ("tenant_id","channel_id");--> statement-breakpoint
CREATE INDEX "channel_messages_ix_4" ON "channel_messages" USING btree ("tenant_id","channel_id","reply_to_message_id");--> statement-breakpoint
CREATE INDEX "channel_subjects_ix_1" ON "channel_subjects" USING btree ("tenant_id","channel_id");--> statement-breakpoint
ALTER TABLE "agents" ADD CONSTRAINT "agents_tenant_id_platform_tenant_id_fk" FOREIGN KEY ("tenant_id") REFERENCES "public"."platform_tenant"("id") ON DELETE restrict ON UPDATE no action;--> statement-breakpoint
ALTER TABLE "attachments" ADD CONSTRAINT "attachments_tenant_id_platform_tenant_id_fk" FOREIGN KEY ("tenant_id") REFERENCES "public"."platform_tenant"("id") ON DELETE restrict ON UPDATE no action;--> statement-breakpoint
ALTER TABLE "attachments" ADD CONSTRAINT "attachments_scope_fk_0" FOREIGN KEY ("tenant_id","channel_id") REFERENCES "public"."channels"("tenant_id","id") ON DELETE restrict ON UPDATE no action;--> statement-breakpoint
ALTER TABLE "audit_events" ADD CONSTRAINT "audit_events_tenant_id_platform_tenant_id_fk" FOREIGN KEY ("tenant_id") REFERENCES "public"."platform_tenant"("id") ON DELETE restrict ON UPDATE no action;--> statement-breakpoint
ALTER TABLE "channel_agents" ADD CONSTRAINT "channel_agents_tenant_id_platform_tenant_id_fk" FOREIGN KEY ("tenant_id") REFERENCES "public"."platform_tenant"("id") ON DELETE restrict ON UPDATE no action;--> statement-breakpoint
ALTER TABLE "channel_agents" ADD CONSTRAINT "channel_agents_channel_scope_fk" FOREIGN KEY ("tenant_id","channel_id") REFERENCES "public"."channels"("tenant_id","id") ON DELETE restrict ON UPDATE no action;--> statement-breakpoint
ALTER TABLE "channel_agents" ADD CONSTRAINT "channel_agents_agent_scope_fk" FOREIGN KEY ("tenant_id","agent_id") REFERENCES "public"."agents"("tenant_id","id") ON DELETE restrict ON UPDATE no action;--> statement-breakpoint
ALTER TABLE "channel_memberships" ADD CONSTRAINT "channel_memberships_tenant_id_platform_tenant_id_fk" FOREIGN KEY ("tenant_id") REFERENCES "public"."platform_tenant"("id") ON DELETE restrict ON UPDATE no action;--> statement-breakpoint
ALTER TABLE "channel_memberships" ADD CONSTRAINT "channel_memberships_channel_scope_fk" FOREIGN KEY ("tenant_id","channel_id") REFERENCES "public"."channels"("tenant_id","id") ON DELETE restrict ON UPDATE no action;--> statement-breakpoint
ALTER TABLE "channel_memberships" ADD CONSTRAINT "channel_memberships_member_scope_fk" FOREIGN KEY ("tenant_id","user_id") REFERENCES "public"."platform_tenant_membership"("tenant_id","user_id") ON DELETE restrict ON UPDATE no action;--> statement-breakpoint
ALTER TABLE "channels" ADD CONSTRAINT "channels_created_by_user_id_users_id_fk" FOREIGN KEY ("created_by_user_id") REFERENCES "public"."users"("id") ON DELETE restrict ON UPDATE no action;--> statement-breakpoint
ALTER TABLE "channels" ADD CONSTRAINT "channels_tenant_id_platform_tenant_id_fk" FOREIGN KEY ("tenant_id") REFERENCES "public"."platform_tenant"("id") ON DELETE restrict ON UPDATE no action;--> statement-breakpoint
ALTER TABLE "channels" ADD CONSTRAINT "channels_scope_fk_0" FOREIGN KEY ("tenant_id","last_message_agent_id") REFERENCES "public"."agents"("tenant_id","id") ON DELETE restrict ON UPDATE no action;--> statement-breakpoint
ALTER TABLE "credentials" ADD CONSTRAINT "credentials_tenant_id_platform_tenant_id_fk" FOREIGN KEY ("tenant_id") REFERENCES "public"."platform_tenant"("id") ON DELETE restrict ON UPDATE no action;--> statement-breakpoint
ALTER TABLE "intelligence_channel_mappings" ADD CONSTRAINT "intelligence_channel_mappings_tenant_id_platform_tenant_id_fk" FOREIGN KEY ("tenant_id") REFERENCES "public"."platform_tenant"("id") ON DELETE restrict ON UPDATE no action;--> statement-breakpoint
ALTER TABLE "intelligence_channel_mappings" ADD CONSTRAINT "intelligence_channel_mappings_scope_fk_0" FOREIGN KEY ("tenant_id","channel_id") REFERENCES "public"."channels"("tenant_id","id") ON DELETE restrict ON UPDATE no action;--> statement-breakpoint
ALTER TABLE "agent_preferences" ADD CONSTRAINT "agent_preferences_tenant_id_platform_tenant_id_fk" FOREIGN KEY ("tenant_id") REFERENCES "public"."platform_tenant"("id") ON DELETE restrict ON UPDATE no action;--> statement-breakpoint
ALTER TABLE "agent_preferences" ADD CONSTRAINT "agent_preferences_scope_fk_0" FOREIGN KEY ("tenant_id","agent_id") REFERENCES "public"."agents"("tenant_id","id") ON DELETE restrict ON UPDATE no action;--> statement-breakpoint
ALTER TABLE "agent_profiles" ADD CONSTRAINT "agent_profiles_tenant_id_platform_tenant_id_fk" FOREIGN KEY ("tenant_id") REFERENCES "public"."platform_tenant"("id") ON DELETE restrict ON UPDATE no action;--> statement-breakpoint
ALTER TABLE "agent_profiles" ADD CONSTRAINT "agent_profiles_scope_fk_0" FOREIGN KEY ("tenant_id","agent_id") REFERENCES "public"."agents"("tenant_id","id") ON DELETE restrict ON UPDATE no action;--> statement-breakpoint
ALTER TABLE "routine_runs" ADD CONSTRAINT "routine_runs_tenant_id_platform_tenant_id_fk" FOREIGN KEY ("tenant_id") REFERENCES "public"."platform_tenant"("id") ON DELETE restrict ON UPDATE no action;--> statement-breakpoint
ALTER TABLE "routine_runs" ADD CONSTRAINT "routine_runs_scope_fk_0" FOREIGN KEY ("tenant_id","routine_id") REFERENCES "public"."routines"("tenant_id","id") ON DELETE restrict ON UPDATE no action;--> statement-breakpoint
ALTER TABLE "routines" ADD CONSTRAINT "routines_tenant_id_platform_tenant_id_fk" FOREIGN KEY ("tenant_id") REFERENCES "public"."platform_tenant"("id") ON DELETE restrict ON UPDATE no action;--> statement-breakpoint
ALTER TABLE "routines" ADD CONSTRAINT "routines_scope_fk_0" FOREIGN KEY ("tenant_id","agent_id") REFERENCES "public"."agents"("tenant_id","id") ON DELETE restrict ON UPDATE no action;--> statement-breakpoint
ALTER TABLE "composio_connections" ADD CONSTRAINT "composio_connections_tenant_id_platform_tenant_id_fk" FOREIGN KEY ("tenant_id") REFERENCES "public"."platform_tenant"("id") ON DELETE restrict ON UPDATE no action;--> statement-breakpoint
ALTER TABLE "mcp_servers" ADD CONSTRAINT "mcp_servers_tenant_id_platform_tenant_id_fk" FOREIGN KEY ("tenant_id") REFERENCES "public"."platform_tenant"("id") ON DELETE restrict ON UPDATE no action;--> statement-breakpoint
ALTER TABLE "mcp_servers" ADD CONSTRAINT "mcp_servers_scope_fk_0" FOREIGN KEY ("tenant_id","credential_id") REFERENCES "public"."credentials"("tenant_id","id") ON DELETE restrict ON UPDATE no action;--> statement-breakpoint
ALTER TABLE "mcp_tools" ADD CONSTRAINT "mcp_tools_tenant_id_platform_tenant_id_fk" FOREIGN KEY ("tenant_id") REFERENCES "public"."platform_tenant"("id") ON DELETE restrict ON UPDATE no action;--> statement-breakpoint
ALTER TABLE "mcp_tools" ADD CONSTRAINT "mcp_tools_scope_fk_0" FOREIGN KEY ("tenant_id","server_id") REFERENCES "public"."mcp_servers"("tenant_id","id") ON DELETE restrict ON UPDATE no action;--> statement-breakpoint
ALTER TABLE "mcp_user_credentials" ADD CONSTRAINT "mcp_user_credentials_tenant_id_platform_tenant_id_fk" FOREIGN KEY ("tenant_id") REFERENCES "public"."platform_tenant"("id") ON DELETE restrict ON UPDATE no action;--> statement-breakpoint
ALTER TABLE "mcp_user_credentials" ADD CONSTRAINT "mcp_user_credentials_scope_fk_0" FOREIGN KEY ("tenant_id","server_id") REFERENCES "public"."mcp_servers"("tenant_id","id") ON DELETE restrict ON UPDATE no action;--> statement-breakpoint
ALTER TABLE "mcp_user_credentials" ADD CONSTRAINT "mcp_user_credentials_scope_fk_1" FOREIGN KEY ("tenant_id","credential_id") REFERENCES "public"."credentials"("tenant_id","id") ON DELETE restrict ON UPDATE no action;--> statement-breakpoint
ALTER TABLE "plugin_grants" ADD CONSTRAINT "plugin_grants_tenant_id_platform_tenant_id_fk" FOREIGN KEY ("tenant_id") REFERENCES "public"."platform_tenant"("id") ON DELETE restrict ON UPDATE no action;--> statement-breakpoint
ALTER TABLE "plugin_grants" ADD CONSTRAINT "plugin_grants_scope_fk_0" FOREIGN KEY ("tenant_id","agent_id") REFERENCES "public"."agents"("tenant_id","id") ON DELETE restrict ON UPDATE no action;--> statement-breakpoint
ALTER TABLE "sandboxed_components" ADD CONSTRAINT "sandboxed_components_tenant_id_platform_tenant_id_fk" FOREIGN KEY ("tenant_id") REFERENCES "public"."platform_tenant"("id") ON DELETE restrict ON UPDATE no action;--> statement-breakpoint
ALTER TABLE "skill_tools" ADD CONSTRAINT "skill_tools_tenant_id_platform_tenant_id_fk" FOREIGN KEY ("tenant_id") REFERENCES "public"."platform_tenant"("id") ON DELETE restrict ON UPDATE no action;--> statement-breakpoint
ALTER TABLE "skill_tools" ADD CONSTRAINT "skill_tools_scope_fk_0" FOREIGN KEY ("tenant_id","skill_id") REFERENCES "public"."skills"("tenant_id","id") ON DELETE restrict ON UPDATE no action;--> statement-breakpoint
ALTER TABLE "skills" ADD CONSTRAINT "skills_tenant_id_platform_tenant_id_fk" FOREIGN KEY ("tenant_id") REFERENCES "public"."platform_tenant"("id") ON DELETE restrict ON UPDATE no action;--> statement-breakpoint
ALTER TABLE "voice_sessions" ADD CONSTRAINT "voice_sessions_tenant_id_platform_tenant_id_fk" FOREIGN KEY ("tenant_id") REFERENCES "public"."platform_tenant"("id") ON DELETE restrict ON UPDATE no action;--> statement-breakpoint
ALTER TABLE "voice_sessions" ADD CONSTRAINT "voice_sessions_scope_fk_0" FOREIGN KEY ("tenant_id","channel_id") REFERENCES "public"."channels"("tenant_id","id") ON DELETE restrict ON UPDATE no action;--> statement-breakpoint
ALTER TABLE "platform_agent_change_request" ADD CONSTRAINT "platform_agent_change_request_fk_1" FOREIGN KEY ("tenant_id","agent_id") REFERENCES "public"."agents"("tenant_id","id") ON DELETE restrict ON UPDATE no action;--> statement-breakpoint
ALTER TABLE "platform_agent_version" ADD CONSTRAINT "platform_agent_version_fk_1" FOREIGN KEY ("tenant_id","agent_id") REFERENCES "public"."agents"("tenant_id","id") ON DELETE restrict ON UPDATE no action;--> statement-breakpoint
ALTER TABLE "platform_mcp_server_version" ADD CONSTRAINT "platform_mcp_server_version_fk_1" FOREIGN KEY ("tenant_id","mcp_server_id") REFERENCES "public"."mcp_servers"("tenant_id","id") ON DELETE restrict ON UPDATE no action;--> statement-breakpoint
ALTER TABLE "platform_skill_version" ADD CONSTRAINT "platform_skill_version_fk_1" FOREIGN KEY ("tenant_id","skill_id") REFERENCES "public"."skills"("tenant_id","id") ON DELETE restrict ON UPDATE no action;--> statement-breakpoint
ALTER TABLE "platform_tool" ADD CONSTRAINT "platform_tool_mcp_fk" FOREIGN KEY ("tenant_id","mcp_server_id") REFERENCES "public"."mcp_servers"("tenant_id","id") ON DELETE restrict ON UPDATE no action;--> statement-breakpoint
ALTER TABLE "platform_regression_baseline" ADD CONSTRAINT "platform_regression_baseline_fk_1" FOREIGN KEY ("tenant_id","agent_id") REFERENCES "public"."agents"("tenant_id","id") ON DELETE restrict ON UPDATE no action;--> statement-breakpoint
ALTER TABLE "platform_agent_run" ADD CONSTRAINT "platform_agent_run_fk_3" FOREIGN KEY ("tenant_id","agent_id") REFERENCES "public"."agents"("tenant_id","id") ON DELETE restrict ON UPDATE no action;--> statement-breakpoint
ALTER TABLE "platform_handoff" ADD CONSTRAINT "platform_handoff_fk_1" FOREIGN KEY ("tenant_id","source_channel_id") REFERENCES "public"."channels"("tenant_id","id") ON DELETE restrict ON UPDATE no action;--> statement-breakpoint
CREATE UNIQUE INDEX "skills_slug_key" ON "skills" USING btree ("tenant_id","slug");--> statement-breakpoint
CREATE INDEX "platform_handoff_ix_1" ON "platform_handoff" USING btree ("tenant_id","source_channel_id");--> statement-breakpoint
ALTER TABLE "platform_handoff" DROP COLUMN "source_conversation_id";--> statement-breakpoint
ALTER TABLE "agents" ADD CONSTRAINT "agents_status_ck" CHECK (status IN ('ACTIVE','SUSPENDED','RETIRED'));--> statement-breakpoint
ALTER TABLE "agents" ADD CONSTRAINT "agents_revision_ck" CHECK (revision > 0);--> statement-breakpoint
ALTER TABLE "channels" ADD CONSTRAINT "channels_status_ck" CHECK (status IN ('ACTIVE','CLOSED','ARCHIVED'));--> statement-breakpoint
ALTER TABLE "channels" ADD CONSTRAINT "channels_revision_ck" CHECK (revision > 0);--> statement-breakpoint
ALTER TABLE "channels" ADD CONSTRAINT "channels_kind_ck" CHECK (channel_kind IN ('RESIDENT','STAFF','INTERNAL'));--> statement-breakpoint
ALTER TABLE "mcp_servers" ADD CONSTRAINT "mcp_servers_status_ck" CHECK (status IN ('ACTIVE','SUSPENDED','RETIRED'));--> statement-breakpoint
ALTER TABLE "mcp_servers" ADD CONSTRAINT "mcp_servers_revision_ck" CHECK (revision > 0);--> statement-breakpoint
ALTER TABLE "skills" ADD CONSTRAINT "skills_status_ck" CHECK (status IN ('ACTIVE','SUSPENDED','RETIRED'));--> statement-breakpoint
ALTER TABLE "skills" ADD CONSTRAINT "skills_revision_ck" CHECK (revision > 0);--> statement-breakpoint
ALTER TABLE "platform_tool" ADD CONSTRAINT "platform_tool_provider_ck" CHECK ((provider_type = 'MCP' AND mcp_server_id IS NOT NULL AND mcp_tool_name IS NOT NULL AND handler_key IS NULL) OR (provider_type IN ('DOMAIN','BUILTIN') AND mcp_server_id IS NULL AND mcp_tool_name IS NULL AND handler_key IS NOT NULL));--> statement-breakpoint
ALTER TABLE "platform_handoff" ADD CONSTRAINT "platform_handoff_ck_0" CHECK (num_nonnulls(source_channel_id, source_workflow_session_id) = 1);--> statement-breakpoint
CREATE POLICY "agents_tenant_policy" ON "agents" AS PERMISSIVE FOR ALL TO public USING ("agents"."tenant_id" = nullif(current_setting('app.tenant_id', true), '')::uuid) WITH CHECK ("agents"."tenant_id" = nullif(current_setting('app.tenant_id', true), '')::uuid);--> statement-breakpoint
CREATE POLICY "attachments_tenant_policy" ON "attachments" AS PERMISSIVE FOR ALL TO public USING ("attachments"."tenant_id" = nullif(current_setting('app.tenant_id', true), '')::uuid) WITH CHECK ("attachments"."tenant_id" = nullif(current_setting('app.tenant_id', true), '')::uuid);--> statement-breakpoint
CREATE POLICY "audit_events_tenant_policy" ON "audit_events" AS PERMISSIVE FOR ALL TO public USING ("audit_events"."tenant_id" = nullif(current_setting('app.tenant_id', true), '')::uuid) WITH CHECK ("audit_events"."tenant_id" = nullif(current_setting('app.tenant_id', true), '')::uuid);--> statement-breakpoint
CREATE POLICY "channel_agents_tenant_policy" ON "channel_agents" AS PERMISSIVE FOR ALL TO public USING ("channel_agents"."tenant_id" = nullif(current_setting('app.tenant_id', true), '')::uuid) WITH CHECK ("channel_agents"."tenant_id" = nullif(current_setting('app.tenant_id', true), '')::uuid);--> statement-breakpoint
CREATE POLICY "channel_memberships_tenant_policy" ON "channel_memberships" AS PERMISSIVE FOR ALL TO public USING ("channel_memberships"."tenant_id" = nullif(current_setting('app.tenant_id', true), '')::uuid) WITH CHECK ("channel_memberships"."tenant_id" = nullif(current_setting('app.tenant_id', true), '')::uuid);--> statement-breakpoint
CREATE POLICY "channels_tenant_policy" ON "channels" AS PERMISSIVE FOR ALL TO public USING ("channels"."tenant_id" = nullif(current_setting('app.tenant_id', true), '')::uuid) WITH CHECK ("channels"."tenant_id" = nullif(current_setting('app.tenant_id', true), '')::uuid);--> statement-breakpoint
CREATE POLICY "credentials_tenant_policy" ON "credentials" AS PERMISSIVE FOR ALL TO public USING ("credentials"."tenant_id" = nullif(current_setting('app.tenant_id', true), '')::uuid) WITH CHECK ("credentials"."tenant_id" = nullif(current_setting('app.tenant_id', true), '')::uuid);--> statement-breakpoint
CREATE POLICY "intelligence_channel_mappings_tenant_policy" ON "intelligence_channel_mappings" AS PERMISSIVE FOR ALL TO public USING ("intelligence_channel_mappings"."tenant_id" = nullif(current_setting('app.tenant_id', true), '')::uuid) WITH CHECK ("intelligence_channel_mappings"."tenant_id" = nullif(current_setting('app.tenant_id', true), '')::uuid);--> statement-breakpoint
CREATE POLICY "agent_preferences_tenant_policy" ON "agent_preferences" AS PERMISSIVE FOR ALL TO public USING ("agent_preferences"."tenant_id" = nullif(current_setting('app.tenant_id', true), '')::uuid) WITH CHECK ("agent_preferences"."tenant_id" = nullif(current_setting('app.tenant_id', true), '')::uuid);--> statement-breakpoint
CREATE POLICY "agent_profiles_tenant_policy" ON "agent_profiles" AS PERMISSIVE FOR ALL TO public USING ("agent_profiles"."tenant_id" = nullif(current_setting('app.tenant_id', true), '')::uuid) WITH CHECK ("agent_profiles"."tenant_id" = nullif(current_setting('app.tenant_id', true), '')::uuid);--> statement-breakpoint
CREATE POLICY "routine_runs_tenant_policy" ON "routine_runs" AS PERMISSIVE FOR ALL TO public USING ("routine_runs"."tenant_id" = nullif(current_setting('app.tenant_id', true), '')::uuid) WITH CHECK ("routine_runs"."tenant_id" = nullif(current_setting('app.tenant_id', true), '')::uuid);--> statement-breakpoint
CREATE POLICY "routines_tenant_policy" ON "routines" AS PERMISSIVE FOR ALL TO public USING ("routines"."tenant_id" = nullif(current_setting('app.tenant_id', true), '')::uuid) WITH CHECK ("routines"."tenant_id" = nullif(current_setting('app.tenant_id', true), '')::uuid);--> statement-breakpoint
CREATE POLICY "composio_connections_tenant_policy" ON "composio_connections" AS PERMISSIVE FOR ALL TO public USING ("composio_connections"."tenant_id" = nullif(current_setting('app.tenant_id', true), '')::uuid) WITH CHECK ("composio_connections"."tenant_id" = nullif(current_setting('app.tenant_id', true), '')::uuid);--> statement-breakpoint
CREATE POLICY "mcp_servers_tenant_policy" ON "mcp_servers" AS PERMISSIVE FOR ALL TO public USING ("mcp_servers"."tenant_id" = nullif(current_setting('app.tenant_id', true), '')::uuid) WITH CHECK ("mcp_servers"."tenant_id" = nullif(current_setting('app.tenant_id', true), '')::uuid);--> statement-breakpoint
CREATE POLICY "mcp_tools_tenant_policy" ON "mcp_tools" AS PERMISSIVE FOR ALL TO public USING ("mcp_tools"."tenant_id" = nullif(current_setting('app.tenant_id', true), '')::uuid) WITH CHECK ("mcp_tools"."tenant_id" = nullif(current_setting('app.tenant_id', true), '')::uuid);--> statement-breakpoint
CREATE POLICY "mcp_user_credentials_tenant_policy" ON "mcp_user_credentials" AS PERMISSIVE FOR ALL TO public USING ("mcp_user_credentials"."tenant_id" = nullif(current_setting('app.tenant_id', true), '')::uuid) WITH CHECK ("mcp_user_credentials"."tenant_id" = nullif(current_setting('app.tenant_id', true), '')::uuid);--> statement-breakpoint
CREATE POLICY "plugin_grants_tenant_policy" ON "plugin_grants" AS PERMISSIVE FOR ALL TO public USING ("plugin_grants"."tenant_id" = nullif(current_setting('app.tenant_id', true), '')::uuid) WITH CHECK ("plugin_grants"."tenant_id" = nullif(current_setting('app.tenant_id', true), '')::uuid);--> statement-breakpoint
CREATE POLICY "sandboxed_components_tenant_policy" ON "sandboxed_components" AS PERMISSIVE FOR ALL TO public USING ("sandboxed_components"."tenant_id" = nullif(current_setting('app.tenant_id', true), '')::uuid) WITH CHECK ("sandboxed_components"."tenant_id" = nullif(current_setting('app.tenant_id', true), '')::uuid);--> statement-breakpoint
CREATE POLICY "skill_tools_tenant_policy" ON "skill_tools" AS PERMISSIVE FOR ALL TO public USING ("skill_tools"."tenant_id" = nullif(current_setting('app.tenant_id', true), '')::uuid) WITH CHECK ("skill_tools"."tenant_id" = nullif(current_setting('app.tenant_id', true), '')::uuid);--> statement-breakpoint
CREATE POLICY "skills_tenant_policy" ON "skills" AS PERMISSIVE FOR ALL TO public USING ("skills"."tenant_id" = nullif(current_setting('app.tenant_id', true), '')::uuid) WITH CHECK ("skills"."tenant_id" = nullif(current_setting('app.tenant_id', true), '')::uuid);--> statement-breakpoint
CREATE POLICY "voice_sessions_tenant_policy" ON "voice_sessions" AS PERMISSIVE FOR ALL TO public USING ("voice_sessions"."tenant_id" = nullif(current_setting('app.tenant_id', true), '')::uuid) WITH CHECK ("voice_sessions"."tenant_id" = nullif(current_setting('app.tenant_id', true), '')::uuid);--> statement-breakpoint
CREATE POLICY "channel_messages_tenant_policy" ON "channel_messages" AS PERMISSIVE FOR ALL TO public USING ("channel_messages"."tenant_id" = nullif(current_setting('app.tenant_id', true), '')::uuid) WITH CHECK ("channel_messages"."tenant_id" = nullif(current_setting('app.tenant_id', true), '')::uuid);--> statement-breakpoint
CREATE POLICY "channel_subjects_tenant_policy" ON "channel_subjects" AS PERMISSIVE FOR ALL TO public USING ("channel_subjects"."tenant_id" = nullif(current_setting('app.tenant_id', true), '')::uuid) WITH CHECK ("channel_subjects"."tenant_id" = nullif(current_setting('app.tenant_id', true), '')::uuid);
--> statement-breakpoint
ALTER TABLE "platform_regression_baseline" ADD CONSTRAINT "platform_regression_baseline_fk_2" FOREIGN KEY ("tenant_id","agent_id","baseline_agent_version_id") REFERENCES "platform_agent_version" ("tenant_id","agent_id","id") ON DELETE restrict ON UPDATE no action;
--> statement-breakpoint
ALTER TABLE "platform_regression_baseline" ADD CONSTRAINT "platform_regression_baseline_fk_5" FOREIGN KEY ("tenant_id","agent_id","baseline_agent_version_id") REFERENCES "platform_agent_version" ("tenant_id","agent_id","id") ON DELETE restrict ON UPDATE no action;
--> statement-breakpoint
ALTER TABLE "platform_agent_run" ADD CONSTRAINT "platform_agent_run_fk_4" FOREIGN KEY ("tenant_id","agent_id","agent_version_id") REFERENCES "platform_agent_version" ("tenant_id","agent_id","id") ON DELETE restrict ON UPDATE no action;
