CREATE EXTENSION IF NOT EXISTS vector;
--> statement-breakpoint
CREATE TYPE "public"."agent_type" AS ENUM('built_in', 'remote_ag_ui', 'remote_mastra');--> statement-breakpoint
CREATE TYPE "public"."agent_visibility" AS ENUM('public', 'private');--> statement-breakpoint
CREATE TYPE "public"."credential_kind" AS ENUM('model', 'connector', 'agent', 'mcp', 'mcp_oauth_client', 'mcp_user_token');--> statement-breakpoint
CREATE TYPE "public"."role" AS ENUM('admin', 'user');--> statement-breakpoint
CREATE TYPE "public"."routine_run_status" AS ENUM('succeeded', 'failed', 'skipped');--> statement-breakpoint
CREATE TABLE "access_scopes" (
	"id" uuid PRIMARY KEY DEFAULT gen_random_uuid() NOT NULL,
	"tenant_id" uuid NOT NULL,
	"kind" text NOT NULL,
	"management_unit_id" uuid,
	"site_id" uuid,
	"zone_id" uuid,
	"building_id" uuid,
	"created_at" timestamp with time zone DEFAULT now() NOT NULL,
	"updated_at" timestamp with time zone DEFAULT now() NOT NULL,
	CONSTRAINT "access_scopes_tenant_key_uq" UNIQUE("tenant_id","id"),
	CONSTRAINT "access_scopes_check_0" CHECK (kind IN ('tenant','management','site','zone','building'))
);
--> statement-breakpoint
ALTER TABLE "access_scopes" ENABLE ROW LEVEL SECURITY;--> statement-breakpoint
CREATE TABLE "account_reviews" (
	"id" uuid PRIMARY KEY DEFAULT gen_random_uuid() NOT NULL,
	"tenant_id" uuid NOT NULL,
	"user_id" text NOT NULL,
	"action" text NOT NULL,
	"from_status" text,
	"to_status" text NOT NULL,
	"reason" text,
	"reviewer_user_id" text,
	"decided_at" timestamp with time zone,
	"created_at" timestamp with time zone DEFAULT now() NOT NULL,
	CONSTRAINT "account_reviews_tenant_key_uq" UNIQUE("tenant_id","id"),
	CONSTRAINT "account_reviews_check_0" CHECK (action IN ('register','approve','reject','activate','suspend','delete'))
);
--> statement-breakpoint
ALTER TABLE "account_reviews" ENABLE ROW LEVEL SECURITY;--> statement-breakpoint
CREATE TABLE "accounts" (
	"id" text PRIMARY KEY NOT NULL,
	"account_id" text NOT NULL,
	"provider_id" text NOT NULL,
	"issuer" text,
	"user_id" text NOT NULL,
	"access_token" text,
	"refresh_token" text,
	"id_token" text,
	"access_token_expires_at" timestamp with time zone,
	"refresh_token_expires_at" timestamp with time zone,
	"scope" text,
	"password" text,
	"created_at" timestamp with time zone DEFAULT now() NOT NULL,
	"updated_at" timestamp with time zone DEFAULT now() NOT NULL,
	CONSTRAINT "accounts_unique_0" UNIQUE("provider_id","account_id")
);
--> statement-breakpoint
CREATE TABLE "action_policy" (
	"id" text PRIMARY KEY NOT NULL,
	"mode" text NOT NULL,
	"deny" text[] NOT NULL,
	"allow" text[] NOT NULL,
	"updated_by" text,
	"updated_at" timestamp with time zone DEFAULT now() NOT NULL,
	CONSTRAINT "action_policy_check_0" CHECK (mode IN ('enforce','dry'))
);
--> statement-breakpoint
CREATE TABLE "agent_build_answers" (
	"id" uuid PRIMARY KEY DEFAULT gen_random_uuid() NOT NULL,
	"tenant_id" uuid NOT NULL,
	"request_id" uuid NOT NULL,
	"question_key" text NOT NULL,
	"question" text NOT NULL,
	"answer" jsonb,
	"answered_by" text,
	"answered_at" timestamp with time zone,
	"created_at" timestamp with time zone DEFAULT now() NOT NULL,
	"revision_no" integer NOT NULL,
	"confirmed" boolean DEFAULT false NOT NULL,
	CONSTRAINT "agent_build_answers_tenant_key_uq" UNIQUE("tenant_id","id"),
	CONSTRAINT "agent_build_answers_unique_0" UNIQUE("request_id","question_key","revision_no")
);
--> statement-breakpoint
ALTER TABLE "agent_build_answers" ENABLE ROW LEVEL SECURITY;--> statement-breakpoint
CREATE TABLE "agent_build_requests" (
	"id" uuid PRIMARY KEY DEFAULT gen_random_uuid() NOT NULL,
	"tenant_id" uuid NOT NULL,
	"workspace_id" uuid NOT NULL,
	"requested_by" text NOT NULL,
	"channel_id" text NOT NULL,
	"proposed_name" text NOT NULL,
	"proposed_description" text NOT NULL,
	"missing_fields" jsonb NOT NULL,
	"draft_config" jsonb NOT NULL,
	"status" text NOT NULL,
	"result_agent_id" text,
	"created_at" timestamp with time zone DEFAULT now() NOT NULL,
	"updated_at" timestamp with time zone DEFAULT now() NOT NULL,
	CONSTRAINT "agent_build_requests_tenant_key_uq" UNIQUE("tenant_id","id"),
	CONSTRAINT "agent_build_requests_check_0" CHECK (status IN ('collecting','ready','confirmed','created','cancelled'))
);
--> statement-breakpoint
ALTER TABLE "agent_build_requests" ENABLE ROW LEVEL SECURITY;--> statement-breakpoint
CREATE TABLE "agent_knowledge_grants" (
	"tenant_id" uuid NOT NULL,
	"agent_id" text NOT NULL,
	"knowledge_base_id" uuid NOT NULL,
	"granted_by" text NOT NULL,
	"created_at" timestamp with time zone DEFAULT now() NOT NULL,
	CONSTRAINT "agent_knowledge_grants_tenant_id_agent_id_knowledge_base_id_pk" PRIMARY KEY("tenant_id","agent_id","knowledge_base_id")
);
--> statement-breakpoint
ALTER TABLE "agent_knowledge_grants" ENABLE ROW LEVEL SECURITY;--> statement-breakpoint
CREATE TABLE "agent_preferences" (
	"user_id" text NOT NULL,
	"agent_id" text NOT NULL,
	"hidden_at" timestamp with time zone,
	"tenant_id" uuid DEFAULT nullif(current_setting('app.tenant_id', true), '')::uuid NOT NULL,
	CONSTRAINT "agent_preferences_user_id_agent_id_pk" PRIMARY KEY("user_id","agent_id")
);
--> statement-breakpoint
ALTER TABLE "agent_preferences" ENABLE ROW LEVEL SECURITY;--> statement-breakpoint
CREATE TABLE "agent_profiles" (
	"agent_id" text PRIMARY KEY NOT NULL,
	"owner_user_id" text,
	"title" text NOT NULL,
	"role_description" text NOT NULL,
	"avatar_seed" text NOT NULL,
	"visibility" "agent_visibility" NOT NULL,
	"callback_token_hash" text,
	"callback_token_issued_at" timestamp with time zone,
	"deleted_at" timestamp with time zone,
	"created_at" timestamp with time zone DEFAULT now() NOT NULL,
	"updated_at" timestamp with time zone DEFAULT now() NOT NULL,
	"tenant_id" uuid DEFAULT nullif(current_setting('app.tenant_id', true), '')::uuid NOT NULL,
	CONSTRAINT "agent_profiles_tenant_key_uq" UNIQUE("tenant_id","agent_id")
);
--> statement-breakpoint
ALTER TABLE "agent_profiles" ENABLE ROW LEVEL SECURITY;--> statement-breakpoint
CREATE TABLE "agent_releases" (
	"id" uuid PRIMARY KEY DEFAULT gen_random_uuid() NOT NULL,
	"tenant_id" uuid NOT NULL,
	"agent_id" text NOT NULL,
	"version_id" uuid NOT NULL,
	"status" text NOT NULL,
	"published_by" text,
	"published_at" timestamp with time zone,
	"revoked_at" timestamp with time zone,
	"created_at" timestamp with time zone DEFAULT now() NOT NULL,
	"updated_at" timestamp with time zone DEFAULT now() NOT NULL,
	CONSTRAINT "agent_releases_tenant_key_uq" UNIQUE("tenant_id","id"),
	CONSTRAINT "agent_releases_check_0" CHECK (status IN ('draft','published','revoked'))
);
--> statement-breakpoint
ALTER TABLE "agent_releases" ENABLE ROW LEVEL SECURITY;--> statement-breakpoint
CREATE TABLE "agent_runs" (
	"id" uuid PRIMARY KEY DEFAULT gen_random_uuid() NOT NULL,
	"tenant_id" uuid NOT NULL,
	"channel_id" text NOT NULL,
	"agent_id" text NOT NULL,
	"version_id" uuid NOT NULL,
	"team_member_id" uuid,
	"actor_user_id" text,
	"parent_run_id" uuid,
	"trigger_event_id" uuid,
	"idempotency_key" text NOT NULL,
	"status" text NOT NULL,
	"started_at" timestamp with time zone,
	"finished_at" timestamp with time zone,
	"error_code" text,
	"input_tokens" bigint DEFAULT 0 NOT NULL,
	"output_tokens" bigint DEFAULT 0 NOT NULL,
	"estimated_cost" numeric(18, 6) DEFAULT '0' NOT NULL,
	"trace_id" text NOT NULL,
	"created_at" timestamp with time zone DEFAULT now() NOT NULL,
	"updated_at" timestamp with time zone DEFAULT now() NOT NULL,
	"binding_id" uuid NOT NULL,
	"authority_principal_id" uuid NOT NULL,
	"on_behalf_of_user_id" text,
	"policy_version" text NOT NULL,
	"authority_version" bigint NOT NULL,
	CONSTRAINT "agent_runs_tenant_key_uq" UNIQUE("tenant_id","id"),
	CONSTRAINT "agent_runs_unique_0" UNIQUE("tenant_id","idempotency_key"),
	CONSTRAINT "agent_runs_check_0" CHECK (status IN ('queued','running','interrupted','succeeded','failed','cancelled'))
);
--> statement-breakpoint
ALTER TABLE "agent_runs" ENABLE ROW LEVEL SECURITY;--> statement-breakpoint
CREATE TABLE "agent_teams" (
	"id" uuid PRIMARY KEY DEFAULT gen_random_uuid() NOT NULL,
	"tenant_id" uuid NOT NULL,
	"workspace_id" uuid NOT NULL,
	"channel_id" text NOT NULL,
	"ticket_id" uuid,
	"request_message_id" uuid,
	"ticket_generation" integer DEFAULT 0 NOT NULL,
	"supervisor_agent_id" text NOT NULL,
	"status" text NOT NULL,
	"shared_state" jsonb NOT NULL,
	"state_version" bigint DEFAULT 0 NOT NULL,
	"finished_at" timestamp with time zone,
	"created_at" timestamp with time zone DEFAULT now() NOT NULL,
	"updated_at" timestamp with time zone DEFAULT now() NOT NULL,
	"requested_by_user_id" text,
	CONSTRAINT "agent_teams_tenant_key_uq" UNIQUE("tenant_id","id"),
	CONSTRAINT "agent_teams_unique_0" UNIQUE("ticket_id","ticket_generation"),
	CONSTRAINT "agent_teams_unique_1" UNIQUE("workspace_id","request_message_id"),
	CONSTRAINT "agent_teams_check_0" CHECK (num_nonnulls(ticket_id,request_message_id)=1),
	CONSTRAINT "agent_teams_check_1" CHECK (status IN ('queued','running','waiting','completed','failed','cancelled'))
);
--> statement-breakpoint
ALTER TABLE "agent_teams" ENABLE ROW LEVEL SECURITY;--> statement-breakpoint
CREATE TABLE "agent_versions" (
	"id" uuid PRIMARY KEY DEFAULT gen_random_uuid() NOT NULL,
	"tenant_id" uuid NOT NULL,
	"agent_id" text NOT NULL,
	"version_no" integer NOT NULL,
	"runtime" text NOT NULL,
	"framework_version" text NOT NULL,
	"model_profile_id" uuid,
	"instructions" text NOT NULL,
	"config" jsonb NOT NULL,
	"config_hash" text NOT NULL,
	"created_by" text NOT NULL,
	"created_at" timestamp with time zone DEFAULT now() NOT NULL,
	CONSTRAINT "agent_versions_tenant_key_uq" UNIQUE("tenant_id","id"),
	CONSTRAINT "agent_versions_unique_0" UNIQUE("agent_id","version_no"),
	CONSTRAINT "agent_versions_check_0" CHECK (runtime IN ('langgraph','agentscope','remote'))
);
--> statement-breakpoint
ALTER TABLE "agent_versions" ENABLE ROW LEVEL SECURITY;--> statement-breakpoint
CREATE TABLE "agents" (
	"id" text PRIMARY KEY NOT NULL,
	"name" text NOT NULL,
	"type" "agent_type" NOT NULL,
	"configuration" jsonb NOT NULL,
	"package_id" uuid,
	"override" jsonb,
	"created_at" timestamp with time zone DEFAULT now() NOT NULL,
	"updated_at" timestamp with time zone DEFAULT now() NOT NULL,
	"tenant_id" uuid DEFAULT nullif(current_setting('app.tenant_id', true), '')::uuid NOT NULL,
	"workspace_id" uuid DEFAULT nullif(current_setting('app.workspace_id', true), '')::uuid,
	"purpose" text DEFAULT 'specialist' NOT NULL,
	"status" text DEFAULT 'active' NOT NULL,
	CONSTRAINT "agents_tenant_key_uq" UNIQUE("tenant_id","id"),
	CONSTRAINT "agents_unique_0" UNIQUE("tenant_id","id"),
	CONSTRAINT "agents_check_0" CHECK ((purpose='reception' AND workspace_id IS NULL) OR (purpose IN ('supervisor','specialist') AND workspace_id IS NOT NULL)),
	CONSTRAINT "agents_check_1" CHECK (purpose IN ('reception','supervisor','specialist')),
	CONSTRAINT "agents_check_2" CHECK (status IN ('draft','active','archived'))
);
--> statement-breakpoint
ALTER TABLE "agents" ENABLE ROW LEVEL SECURITY;--> statement-breakpoint
CREATE TABLE "attachments" (
	"id" uuid PRIMARY KEY DEFAULT gen_random_uuid() NOT NULL,
	"channel_id" text NOT NULL,
	"uploaded_by" text NOT NULL,
	"name" text NOT NULL,
	"mime_type" text NOT NULL,
	"size_bytes" integer NOT NULL,
	"bytes" "bytea" NOT NULL,
	"created_at" timestamp with time zone DEFAULT now() NOT NULL,
	"attached_at" timestamp with time zone,
	"upload_group" text,
	"file_id" uuid
);
--> statement-breakpoint
CREATE TABLE "audit_events" (
	"id" uuid PRIMARY KEY DEFAULT gen_random_uuid() NOT NULL,
	"actor_user_id" text,
	"initiator_kind" text DEFAULT 'person' NOT NULL,
	"initiator_id" text,
	"event_type" text NOT NULL,
	"target_type" text NOT NULL,
	"target_id" text,
	"payload" jsonb NOT NULL,
	"created_at" timestamp with time zone DEFAULT now() NOT NULL,
	"tenant_id" uuid,
	"workspace_id" uuid,
	"request_id" text,
	"correlation_id" uuid,
	"actor_snapshot" jsonb DEFAULT '{}'::jsonb NOT NULL,
	CONSTRAINT "audit_events_tenant_key_uq" UNIQUE("tenant_id","id")
);
--> statement-breakpoint
ALTER TABLE "audit_events" ENABLE ROW LEVEL SECURITY;--> statement-breakpoint
CREATE TABLE "buildings" (
	"id" uuid PRIMARY KEY DEFAULT gen_random_uuid() NOT NULL,
	"tenant_id" uuid NOT NULL,
	"site_id" uuid NOT NULL,
	"zone_id" uuid,
	"code" text NOT NULL,
	"name" text NOT NULL,
	"status" text NOT NULL,
	"created_at" timestamp with time zone DEFAULT now() NOT NULL,
	"updated_at" timestamp with time zone DEFAULT now() NOT NULL,
	CONSTRAINT "buildings_tenant_key_uq" UNIQUE("tenant_id","id"),
	CONSTRAINT "buildings_unique_0" UNIQUE("site_id","code")
);
--> statement-breakpoint
ALTER TABLE "buildings" ENABLE ROW LEVEL SECURITY;--> statement-breakpoint
CREATE TABLE "channel_agents" (
	"channel_id" text NOT NULL,
	"agent_id" text NOT NULL,
	"created_at" timestamp with time zone DEFAULT now() NOT NULL,
	"tenant_id" uuid DEFAULT nullif(current_setting('app.tenant_id', true), '')::uuid NOT NULL,
	CONSTRAINT "channel_agents_channel_id_agent_id_pk" PRIMARY KEY("channel_id","agent_id")
);
--> statement-breakpoint
ALTER TABLE "channel_agents" ENABLE ROW LEVEL SECURITY;--> statement-breakpoint
CREATE TABLE "channel_memberships" (
	"channel_id" text NOT NULL,
	"user_id" text NOT NULL,
	"pinned_at" timestamp with time zone,
	"last_read_at" timestamp with time zone,
	"created_at" timestamp with time zone DEFAULT now() NOT NULL,
	"tenant_id" uuid DEFAULT nullif(current_setting('app.tenant_id', true), '')::uuid NOT NULL,
	"last_read_seq" bigint DEFAULT 0 NOT NULL,
	CONSTRAINT "channel_memberships_channel_id_user_id_pk" PRIMARY KEY("channel_id","user_id")
);
--> statement-breakpoint
ALTER TABLE "channel_memberships" ENABLE ROW LEVEL SECURITY;--> statement-breakpoint
CREATE TABLE "channels" (
	"id" text PRIMARY KEY NOT NULL,
	"name" text NOT NULL,
	"description" text NOT NULL,
	"suggested_prompts" text[] DEFAULT '{}' NOT NULL,
	"allowed_groups" text[] DEFAULT '{}' NOT NULL,
	"package_id" uuid,
	"override" jsonb,
	"summary" text,
	"summary_at" timestamp with time zone,
	"last_message" text,
	"last_message_at" timestamp with time zone,
	"last_message_agent_id" text,
	"deleted_at" timestamp with time zone,
	"created_at" timestamp with time zone DEFAULT now() NOT NULL,
	"updated_at" timestamp with time zone DEFAULT now() NOT NULL,
	"tenant_id" uuid DEFAULT nullif(current_setting('app.tenant_id', true), '')::uuid NOT NULL,
	"workspace_id" uuid DEFAULT nullif(current_setting('app.workspace_id', true), '')::uuid,
	"kind" text DEFAULT 'management' NOT NULL,
	"created_by" text,
	"is_dispatch_default" boolean DEFAULT false NOT NULL,
	"next_message_seq" bigint DEFAULT 1 NOT NULL,
	CONSTRAINT "channels_tenant_key_uq" UNIQUE("tenant_id","id"),
	CONSTRAINT "channels_unique_0" UNIQUE("tenant_id","id"),
	CONSTRAINT "channels_check_0" CHECK ((kind='reception' AND workspace_id IS NULL) OR (kind IN ('management','agent_builder') AND workspace_id IS NOT NULL)),
	CONSTRAINT "channels_check_1" CHECK (kind IN ('reception','management','agent_builder'))
);
--> statement-breakpoint
ALTER TABLE "channels" ENABLE ROW LEVEL SECURITY;--> statement-breakpoint
CREATE TABLE "component_exclusions" (
	"component_name" text NOT NULL,
	"agent_id" text NOT NULL,
	"withheld_by" text,
	"withheld_at" timestamp with time zone DEFAULT now() NOT NULL,
	"updated_at" timestamp with time zone DEFAULT now() NOT NULL,
	"tenant_id" uuid DEFAULT nullif(current_setting('app.tenant_id', true), '')::uuid NOT NULL,
	CONSTRAINT "component_exclusions_component_name_agent_id_pk" PRIMARY KEY("component_name","agent_id")
);
--> statement-breakpoint
ALTER TABLE "component_exclusions" ENABLE ROW LEVEL SECURITY;--> statement-breakpoint
CREATE TABLE "component_functions" (
	"component_name" text NOT NULL,
	"function_name" text NOT NULL,
	"granted_by" text,
	"granted_at" timestamp with time zone DEFAULT now() NOT NULL,
	"updated_at" timestamp with time zone DEFAULT now() NOT NULL,
	CONSTRAINT "component_functions_component_name_function_name_pk" PRIMARY KEY("component_name","function_name")
);
--> statement-breakpoint
CREATE TABLE "components" (
	"name" text PRIMARY KEY NOT NULL,
	"title" text NOT NULL,
	"kind" text NOT NULL,
	"draft_description" text NOT NULL,
	"published_description" text,
	"published" boolean DEFAULT false NOT NULL,
	"published_at" timestamp with time zone,
	"updated_by" text,
	"created_at" timestamp with time zone DEFAULT now() NOT NULL,
	"updated_at" timestamp with time zone DEFAULT now() NOT NULL
);
--> statement-breakpoint
CREATE TABLE "composio_connections" (
	"toolkit" text NOT NULL,
	"user_id" text NOT NULL,
	"connected_at" timestamp with time zone DEFAULT now() NOT NULL,
	"verified" boolean DEFAULT false NOT NULL,
	"verified_at" timestamp with time zone,
	"probe_action" text,
	"updated_at" timestamp with time zone DEFAULT now() NOT NULL,
	"tenant_id" uuid DEFAULT nullif(current_setting('app.tenant_id', true), '')::uuid NOT NULL,
	CONSTRAINT "composio_connections_tenant_id_toolkit_user_id_pk" PRIMARY KEY("tenant_id","toolkit","user_id")
);
--> statement-breakpoint
ALTER TABLE "composio_connections" ENABLE ROW LEVEL SECURITY;--> statement-breakpoint
CREATE TABLE "computer_page_frame" (
	"computer_id" text NOT NULL,
	"tool_call_id" text NOT NULL,
	"url" text NOT NULL,
	"title" text,
	"frame" text NOT NULL,
	"captured_at" timestamp with time zone DEFAULT now() NOT NULL,
	"tenant_id" uuid DEFAULT nullif(current_setting('app.tenant_id', true), '')::uuid NOT NULL,
	"agent_id" text NOT NULL,
	CONSTRAINT "computer_page_frame_computer_id_tool_call_id_pk" PRIMARY KEY("computer_id","tool_call_id")
);
--> statement-breakpoint
ALTER TABLE "computer_page_frame" ENABLE ROW LEVEL SECURITY;--> statement-breakpoint
CREATE TABLE "computer_snapshot" (
	"computer_id" text PRIMARY KEY NOT NULL,
	"snapshot_id" integer NOT NULL,
	"url" text NOT NULL,
	"elements" jsonb NOT NULL,
	"taken_at" timestamp with time zone DEFAULT now() NOT NULL,
	"session" text,
	"tenant_id" uuid DEFAULT nullif(current_setting('app.tenant_id', true), '')::uuid NOT NULL,
	"agent_id" text NOT NULL,
	CONSTRAINT "computer_snapshot_tenant_key_uq" UNIQUE("tenant_id","computer_id")
);
--> statement-breakpoint
ALTER TABLE "computer_snapshot" ENABLE ROW LEVEL SECURITY;--> statement-breakpoint
CREATE TABLE "context_snapshots" (
	"id" uuid PRIMARY KEY DEFAULT gen_random_uuid() NOT NULL,
	"tenant_id" uuid NOT NULL,
	"run_id" uuid NOT NULL,
	"requested_message_id" uuid,
	"ticket_id" uuid,
	"message_ids" jsonb NOT NULL,
	"task_ids" jsonb NOT NULL,
	"retrieval_ids" jsonb NOT NULL,
	"policy_version" text NOT NULL,
	"token_budget" integer NOT NULL,
	"content_hash" text NOT NULL,
	"redacted_context" jsonb NOT NULL,
	"created_at" timestamp with time zone DEFAULT now() NOT NULL,
	CONSTRAINT "context_snapshots_tenant_key_uq" UNIQUE("tenant_id","id"),
	CONSTRAINT "context_snapshots_unique_0" UNIQUE("run_id")
);
--> statement-breakpoint
ALTER TABLE "context_snapshots" ENABLE ROW LEVEL SECURITY;--> statement-breakpoint
CREATE TABLE "credentials" (
	"id" uuid PRIMARY KEY DEFAULT gen_random_uuid() NOT NULL,
	"kind" "credential_kind" NOT NULL,
	"provider" text NOT NULL,
	"encrypted_value" text NOT NULL,
	"key_id" text NOT NULL,
	"metadata" jsonb NOT NULL,
	"revoked_at" timestamp with time zone,
	"created_at" timestamp with time zone DEFAULT now() NOT NULL,
	"updated_at" timestamp with time zone DEFAULT now() NOT NULL,
	"tenant_id" uuid,
	"workspace_id" uuid,
	"scope_kind" text DEFAULT 'platform' NOT NULL,
	CONSTRAINT "credentials_tenant_key_uq" UNIQUE("tenant_id","id"),
	CONSTRAINT "credentials_check_0" CHECK ((scope_kind='platform' AND tenant_id IS NULL AND workspace_id IS NULL) OR (scope_kind='tenant' AND tenant_id IS NOT NULL AND workspace_id IS NULL) OR (scope_kind='workspace' AND tenant_id IS NOT NULL AND workspace_id IS NOT NULL)),
	CONSTRAINT "credentials_check_1" CHECK (scope_kind IN ('platform','tenant','workspace'))
);
--> statement-breakpoint
ALTER TABLE "credentials" ENABLE ROW LEVEL SECURITY;--> statement-breakpoint
CREATE TABLE "deployment_packages" (
	"id" uuid PRIMARY KEY DEFAULT gen_random_uuid() NOT NULL,
	"source_path" text NOT NULL,
	"checksum" text NOT NULL,
	"loaded_at" timestamp with time zone DEFAULT now() NOT NULL,
	"external_tenant_key" text NOT NULL,
	"tenant_id" uuid DEFAULT nullif(current_setting('app.tenant_id', true), '')::uuid NOT NULL,
	CONSTRAINT "deployment_packages_tenant_key_uq" UNIQUE("tenant_id","id"),
	CONSTRAINT "deployment_packages_unique_0" UNIQUE("tenant_id"),
	CONSTRAINT "deployment_packages_unique_1" UNIQUE("external_tenant_key")
);
--> statement-breakpoint
ALTER TABLE "deployment_packages" ENABLE ROW LEVEL SECURITY;--> statement-breakpoint
CREATE TABLE "dispatch_attempts" (
	"id" uuid PRIMARY KEY DEFAULT gen_random_uuid() NOT NULL,
	"tenant_id" uuid NOT NULL,
	"queue_id" uuid NOT NULL,
	"work_order_id" uuid NOT NULL,
	"decision_id" uuid NOT NULL,
	"queue_version" bigint NOT NULL,
	"fencing_token" bigint NOT NULL,
	"worker_id" text NOT NULL,
	"priority_rank_snapshot" integer NOT NULL,
	"emergency_snapshot" boolean NOT NULL,
	"status" text NOT NULL,
	"claimed_at" timestamp with time zone NOT NULL,
	"lease_until" timestamp with time zone NOT NULL,
	"assignment_id" uuid,
	"finished_at" timestamp with time zone,
	"reason" text,
	"idempotency_key" text NOT NULL,
	"created_at" timestamp with time zone DEFAULT now() NOT NULL,
	"updated_at" timestamp with time zone DEFAULT now() NOT NULL,
	CONSTRAINT "dispatch_attempts_tenant_key_uq" UNIQUE("tenant_id","id"),
	CONSTRAINT "dispatch_attempts_unique_0" UNIQUE("queue_id","idempotency_key"),
	CONSTRAINT "dispatch_attempts_unique_1" UNIQUE("queue_id","fencing_token"),
	CONSTRAINT "dispatch_attempts_check_0" CHECK (priority_rank_snapshot IN (10,20,30,40)),
	CONSTRAINT "dispatch_attempts_check_1" CHECK (status<>'offered' OR assignment_id IS NOT NULL),
	CONSTRAINT "dispatch_attempts_check_2" CHECK (status IN ('claimed','offered','no_capacity','stale','expired','failed'))
);
--> statement-breakpoint
ALTER TABLE "dispatch_attempts" ENABLE ROW LEVEL SECURITY;--> statement-breakpoint
CREATE TABLE "dispatch_queue" (
	"id" uuid PRIMARY KEY DEFAULT gen_random_uuid() NOT NULL,
	"tenant_id" uuid NOT NULL,
	"work_order_id" uuid NOT NULL,
	"management_unit_id" uuid NOT NULL,
	"category_id" uuid NOT NULL,
	"queued_at" timestamp with time zone NOT NULL,
	"available_at" timestamp with time zone NOT NULL,
	"state" text NOT NULL,
	"attempts" integer DEFAULT 0 NOT NULL,
	"lease_owner" text,
	"lease_until" timestamp with time zone,
	"created_at" timestamp with time zone DEFAULT now() NOT NULL,
	"updated_at" timestamp with time zone DEFAULT now() NOT NULL,
	"priority_decision_id" uuid NOT NULL,
	"priority_rank" integer NOT NULL,
	"is_emergency" boolean NOT NULL,
	"dispatch_due_at" timestamp with time zone,
	"eligible_since" timestamp with time zone NOT NULL,
	"version" bigint DEFAULT 0 NOT NULL,
	"fencing_token" bigint DEFAULT 0 NOT NULL,
	CONSTRAINT "dispatch_queue_tenant_key_uq" UNIQUE("tenant_id","id"),
	CONSTRAINT "dispatch_queue_unique_0" UNIQUE("work_order_id"),
	CONSTRAINT "dispatch_queue_check_0" CHECK (priority_rank IN (10,20,30,40)),
	CONSTRAINT "dispatch_queue_check_1" CHECK (NOT is_emergency OR priority_rank=40),
	CONSTRAINT "dispatch_queue_check_2" CHECK (state IN ('waiting','claimed','dispatched','cancelled','dead'))
);
--> statement-breakpoint
ALTER TABLE "dispatch_queue" ENABLE ROW LEVEL SECURITY;--> statement-breakpoint
CREATE TABLE "document_acl" (
	"id" uuid PRIMARY KEY DEFAULT gen_random_uuid() NOT NULL,
	"tenant_id" uuid NOT NULL,
	"document_id" uuid NOT NULL,
	"principal_kind" text NOT NULL,
	"role_code" text,
	"user_id" text,
	"workspace_id" uuid,
	"effect" text DEFAULT 'allow' NOT NULL,
	"created_at" timestamp with time zone DEFAULT now() NOT NULL,
	"updated_at" timestamp with time zone DEFAULT now() NOT NULL,
	CONSTRAINT "document_acl_tenant_key_uq" UNIQUE("tenant_id","id"),
	CONSTRAINT "document_acl_check_0" CHECK (principal_kind IN ('role','user','workspace')),
	CONSTRAINT "document_acl_check_1" CHECK (effect IN ('allow','deny'))
);
--> statement-breakpoint
ALTER TABLE "document_acl" ENABLE ROW LEVEL SECURITY;--> statement-breakpoint
CREATE TABLE "document_scopes" (
	"tenant_id" uuid NOT NULL,
	"document_id" uuid NOT NULL,
	"scope_id" uuid NOT NULL,
	"applies_to_descendants" boolean DEFAULT true NOT NULL,
	"created_at" timestamp with time zone DEFAULT now() NOT NULL,
	CONSTRAINT "document_scopes_tenant_id_document_id_scope_id_pk" PRIMARY KEY("tenant_id","document_id","scope_id")
);
--> statement-breakpoint
ALTER TABLE "document_scopes" ENABLE ROW LEVEL SECURITY;--> statement-breakpoint
CREATE TABLE "document_versions" (
	"id" uuid PRIMARY KEY DEFAULT gen_random_uuid() NOT NULL,
	"tenant_id" uuid NOT NULL,
	"document_id" uuid NOT NULL,
	"version_no" integer NOT NULL,
	"file_id" uuid NOT NULL,
	"content_hash" text NOT NULL,
	"effective_from" timestamp with time zone NOT NULL,
	"effective_to" timestamp with time zone,
	"submitted_by" text NOT NULL,
	"extraction_config" jsonb NOT NULL,
	"created_at" timestamp with time zone DEFAULT now() NOT NULL,
	CONSTRAINT "document_versions_tenant_key_uq" UNIQUE("tenant_id","id"),
	CONSTRAINT "document_versions_unique_0" UNIQUE("document_id","version_no")
);
--> statement-breakpoint
ALTER TABLE "document_versions" ENABLE ROW LEVEL SECURITY;--> statement-breakpoint
CREATE TABLE "domains" (
	"id" uuid PRIMARY KEY DEFAULT gen_random_uuid() NOT NULL,
	"tenant_id" uuid NOT NULL,
	"code" text NOT NULL,
	"name" text NOT NULL,
	"description" text,
	"status" text NOT NULL,
	"created_at" timestamp with time zone DEFAULT now() NOT NULL,
	"updated_at" timestamp with time zone DEFAULT now() NOT NULL,
	CONSTRAINT "domains_tenant_key_uq" UNIQUE("tenant_id","id"),
	CONSTRAINT "domains_unique_0" UNIQUE("tenant_id","code")
);
--> statement-breakpoint
ALTER TABLE "domains" ENABLE ROW LEVEL SECURITY;--> statement-breakpoint
CREATE TABLE "embedding_models" (
	"id" uuid PRIMARY KEY DEFAULT gen_random_uuid() NOT NULL,
	"provider" text NOT NULL,
	"model_name" text NOT NULL,
	"model_revision" text NOT NULL,
	"dimension" integer NOT NULL,
	"distance_metric" text NOT NULL,
	"active" boolean DEFAULT true NOT NULL,
	"created_at" timestamp with time zone DEFAULT now() NOT NULL,
	"updated_at" timestamp with time zone DEFAULT now() NOT NULL,
	CONSTRAINT "embedding_models_unique_0" UNIQUE("provider","model_name","model_revision","dimension")
);
--> statement-breakpoint
CREATE TABLE "event_inbox" (
	"id" uuid PRIMARY KEY DEFAULT gen_random_uuid() NOT NULL,
	"tenant_id" uuid NOT NULL,
	"consumer" text NOT NULL,
	"event_id" uuid NOT NULL,
	"status" text NOT NULL,
	"attempts" integer DEFAULT 0 NOT NULL,
	"available_at" timestamp with time zone NOT NULL,
	"lease_owner" text,
	"lease_until" timestamp with time zone,
	"processed_at" timestamp with time zone,
	"last_error" text,
	"created_at" timestamp with time zone DEFAULT now() NOT NULL,
	"updated_at" timestamp with time zone DEFAULT now() NOT NULL,
	CONSTRAINT "event_inbox_tenant_key_uq" UNIQUE("tenant_id","id"),
	CONSTRAINT "event_inbox_unique_0" UNIQUE("tenant_id","consumer","event_id"),
	CONSTRAINT "event_inbox_check_0" CHECK (status IN ('pending','processing','done','dead'))
);
--> statement-breakpoint
ALTER TABLE "event_inbox" ENABLE ROW LEVEL SECURITY;--> statement-breakpoint
CREATE TABLE "event_outbox" (
	"id" uuid PRIMARY KEY DEFAULT gen_random_uuid() NOT NULL,
	"tenant_id" uuid NOT NULL,
	"event_id" uuid NOT NULL,
	"topic" text NOT NULL,
	"payload" jsonb NOT NULL,
	"schema_version" integer NOT NULL,
	"available_at" timestamp with time zone NOT NULL,
	"published_at" timestamp with time zone,
	"attempts" integer DEFAULT 0 NOT NULL,
	"lease_owner" text,
	"lease_until" timestamp with time zone,
	"last_error" text,
	"created_at" timestamp with time zone DEFAULT now() NOT NULL,
	CONSTRAINT "event_outbox_tenant_key_uq" UNIQUE("tenant_id","id"),
	CONSTRAINT "event_outbox_unique_0" UNIQUE("event_id","topic")
);
--> statement-breakpoint
ALTER TABLE "event_outbox" ENABLE ROW LEVEL SECURITY;--> statement-breakpoint
CREATE TABLE "evidence_items" (
	"id" uuid PRIMARY KEY DEFAULT gen_random_uuid() NOT NULL,
	"tenant_id" uuid NOT NULL,
	"ticket_id" uuid NOT NULL,
	"work_order_id" uuid,
	"assignment_id" uuid,
	"file_id" uuid NOT NULL,
	"purpose" text NOT NULL,
	"captured_at" timestamp with time zone,
	"uploaded_at" timestamp with time zone NOT NULL,
	"uploaded_by" text NOT NULL,
	"caption" text,
	"provenance" text NOT NULL,
	"supersedes_id" uuid,
	"status" text NOT NULL,
	"withdrawn_reason" text,
	"created_at" timestamp with time zone DEFAULT now() NOT NULL,
	"updated_at" timestamp with time zone DEFAULT now() NOT NULL,
	CONSTRAINT "evidence_items_tenant_key_uq" UNIQUE("tenant_id","id"),
	CONSTRAINT "evidence_items_unique_0" UNIQUE("ticket_id","file_id","purpose"),
	CONSTRAINT "evidence_items_check_0" CHECK (purpose IN ('issue','before','after','verification')),
	CONSTRAINT "evidence_items_check_1" CHECK (provenance IN ('camera','upload','import')),
	CONSTRAINT "evidence_items_check_2" CHECK (status IN ('active','withdrawn'))
);
--> statement-breakpoint
ALTER TABLE "evidence_items" ENABLE ROW LEVEL SECURITY;--> statement-breakpoint
CREATE TABLE "execution_principals" (
	"id" uuid PRIMARY KEY DEFAULT gen_random_uuid() NOT NULL,
	"tenant_id" uuid NOT NULL,
	"kind" text NOT NULL,
	"user_id" text,
	"workspace_id" uuid,
	"status" text NOT NULL,
	"authz_version" bigint DEFAULT 1 NOT NULL,
	"created_at" timestamp with time zone DEFAULT now() NOT NULL,
	"updated_at" timestamp with time zone DEFAULT now() NOT NULL,
	CONSTRAINT "execution_principals_tenant_key_uq" UNIQUE("tenant_id","id"),
	CONSTRAINT "execution_principals_check_0" CHECK ((kind='user' AND user_id IS NOT NULL AND workspace_id IS NULL) OR (kind='workspace_service' AND user_id IS NULL AND workspace_id IS NOT NULL)),
	CONSTRAINT "execution_principals_check_1" CHECK (kind IN ('user','workspace_service')),
	CONSTRAINT "execution_principals_check_2" CHECK (status IN ('active','suspended','revoked'))
);
--> statement-breakpoint
ALTER TABLE "execution_principals" ENABLE ROW LEVEL SECURITY;--> statement-breakpoint
CREATE TABLE "file_access_logs" (
	"id" uuid PRIMARY KEY DEFAULT gen_random_uuid() NOT NULL,
	"tenant_id" uuid NOT NULL,
	"file_id" uuid NOT NULL,
	"object_id" uuid,
	"actor_user_id" text,
	"actor_principal_id" uuid NOT NULL,
	"run_id" uuid,
	"action" text NOT NULL,
	"decision" text NOT NULL,
	"purpose" text NOT NULL,
	"request_id" text NOT NULL,
	"signed_url_expires_at" timestamp with time zone,
	"created_at" timestamp with time zone DEFAULT now() NOT NULL,
	CONSTRAINT "file_access_logs_tenant_key_uq" UNIQUE("tenant_id","id"),
	CONSTRAINT "file_access_logs_check_0" CHECK (action IN ('view','download','presign','upload','deny')),
	CONSTRAINT "file_access_logs_check_1" CHECK (decision IN ('allow','deny'))
);
--> statement-breakpoint
ALTER TABLE "file_access_logs" ENABLE ROW LEVEL SECURITY;--> statement-breakpoint
CREATE TABLE "file_deletion_requests" (
	"id" uuid PRIMARY KEY DEFAULT gen_random_uuid() NOT NULL,
	"tenant_id" uuid NOT NULL,
	"file_id" uuid NOT NULL,
	"requested_by" text,
	"reason" text NOT NULL,
	"not_before" timestamp with time zone NOT NULL,
	"status" text NOT NULL,
	"completed_at" timestamp with time zone,
	"failure_code" text,
	"created_at" timestamp with time zone DEFAULT now() NOT NULL,
	"updated_at" timestamp with time zone DEFAULT now() NOT NULL,
	CONSTRAINT "file_deletion_requests_tenant_key_uq" UNIQUE("tenant_id","id"),
	CONSTRAINT "file_deletion_requests_check_0" CHECK (status IN ('pending','running','blocked','completed','cancelled'))
);
--> statement-breakpoint
ALTER TABLE "file_deletion_requests" ENABLE ROW LEVEL SECURITY;--> statement-breakpoint
CREATE TABLE "file_objects" (
	"id" uuid PRIMARY KEY DEFAULT gen_random_uuid() NOT NULL,
	"tenant_id" uuid NOT NULL,
	"file_id" uuid NOT NULL,
	"location_id" uuid NOT NULL,
	"object_key" text NOT NULL,
	"version_id" text NOT NULL,
	"variant" text NOT NULL,
	"variant_revision" integer DEFAULT 1 NOT NULL,
	"source_object_id" uuid,
	"mime_type" text NOT NULL,
	"size_bytes" bigint NOT NULL,
	"sha256" text NOT NULL,
	"etag" text,
	"checksum_algorithm" text,
	"checksum_value" text,
	"checksum_type" text,
	"width_px" integer,
	"height_px" integer,
	"scan_status" text NOT NULL,
	"verified_at" timestamp with time zone,
	"encryption_mode" text NOT NULL,
	"kms_key_ref" text,
	"object_retain_until" timestamp with time zone,
	"object_legal_hold" boolean DEFAULT false NOT NULL,
	"status" text NOT NULL,
	"created_at" timestamp with time zone DEFAULT now() NOT NULL,
	"updated_at" timestamp with time zone DEFAULT now() NOT NULL,
	CONSTRAINT "file_objects_tenant_key_uq" UNIQUE("tenant_id","id"),
	CONSTRAINT "file_objects_unique_0" UNIQUE("location_id","object_key","version_id"),
	CONSTRAINT "file_objects_unique_1" UNIQUE("file_id","variant","variant_revision"),
	CONSTRAINT "file_objects_check_0" CHECK (size_bytes>=0),
	CONSTRAINT "file_objects_check_1" CHECK (sha256 ~ '^[0-9a-f]{64}$'),
	CONSTRAINT "file_objects_check_2" CHECK (variant_revision>0),
	CONSTRAINT "file_objects_check_3" CHECK (variant='original' OR source_object_id IS NOT NULL),
	CONSTRAINT "file_objects_check_4" CHECK (status<>'ready' OR (scan_status='clean' AND verified_at IS NOT NULL)),
	CONSTRAINT "file_objects_check_5" CHECK (version_id<>'' AND version_id<>'null'),
	CONSTRAINT "file_objects_check_6" CHECK (variant IN ('original','thumbnail','redacted','preview')),
	CONSTRAINT "file_objects_check_7" CHECK (scan_status IN ('pending','clean','infected','failed')),
	CONSTRAINT "file_objects_check_8" CHECK (status IN ('verifying','ready','rejected','deletion_pending','deleted','missing'))
);
--> statement-breakpoint
ALTER TABLE "file_objects" ENABLE ROW LEVEL SECURITY;--> statement-breakpoint
CREATE TABLE "file_processing_jobs" (
	"id" uuid PRIMARY KEY DEFAULT gen_random_uuid() NOT NULL,
	"tenant_id" uuid NOT NULL,
	"file_id" uuid NOT NULL,
	"upload_id" uuid,
	"object_id" uuid,
	"kind" text NOT NULL,
	"dedupe_key" text NOT NULL,
	"status" text NOT NULL,
	"available_at" timestamp with time zone NOT NULL,
	"attempts" integer DEFAULT 0 NOT NULL,
	"lease_owner" text,
	"lease_until" timestamp with time zone,
	"fencing_version" bigint DEFAULT 0 NOT NULL,
	"payload" jsonb NOT NULL,
	"finished_at" timestamp with time zone,
	"failure_code" text,
	"created_at" timestamp with time zone DEFAULT now() NOT NULL,
	"updated_at" timestamp with time zone DEFAULT now() NOT NULL,
	CONSTRAINT "file_processing_jobs_tenant_key_uq" UNIQUE("tenant_id","id"),
	CONSTRAINT "file_processing_jobs_unique_0" UNIQUE("tenant_id","dedupe_key"),
	CONSTRAINT "file_processing_jobs_check_0" CHECK (kind IN ('verify','promote','thumbnail','redact','delete','reconcile')),
	CONSTRAINT "file_processing_jobs_check_1" CHECK (status IN ('pending','running','succeeded','failed','dead','cancelled'))
);
--> statement-breakpoint
ALTER TABLE "file_processing_jobs" ENABLE ROW LEVEL SECURITY;--> statement-breakpoint
CREATE TABLE "file_upload_parts" (
	"id" uuid PRIMARY KEY DEFAULT gen_random_uuid() NOT NULL,
	"tenant_id" uuid NOT NULL,
	"upload_id" uuid NOT NULL,
	"part_number" integer NOT NULL,
	"etag" text NOT NULL,
	"size_bytes" bigint NOT NULL,
	"checksum_value" text,
	"created_at" timestamp with time zone DEFAULT now() NOT NULL,
	"updated_at" timestamp with time zone DEFAULT now() NOT NULL,
	CONSTRAINT "file_upload_parts_tenant_key_uq" UNIQUE("tenant_id","id"),
	CONSTRAINT "file_upload_parts_unique_0" UNIQUE("upload_id","part_number"),
	CONSTRAINT "file_upload_parts_check_0" CHECK (part_number BETWEEN 1 AND 10000),
	CONSTRAINT "file_upload_parts_check_1" CHECK (size_bytes>0)
);
--> statement-breakpoint
ALTER TABLE "file_upload_parts" ENABLE ROW LEVEL SECURITY;--> statement-breakpoint
CREATE TABLE "file_uploads" (
	"id" uuid PRIMARY KEY DEFAULT gen_random_uuid() NOT NULL,
	"tenant_id" uuid NOT NULL,
	"file_id" uuid NOT NULL,
	"requested_by" text NOT NULL,
	"location_id" uuid NOT NULL,
	"staging_key" text NOT NULL,
	"source_version_id" text,
	"upload_mode" text NOT NULL,
	"multipart_upload_id" text,
	"expected_size_bytes" bigint NOT NULL,
	"expected_sha256" text,
	"allowed_mime_types" text[] NOT NULL,
	"max_size_bytes" bigint NOT NULL,
	"status" text NOT NULL,
	"idempotency_key" text NOT NULL,
	"expires_at" timestamp with time zone NOT NULL,
	"finalized_at" timestamp with time zone,
	"result_object_id" uuid,
	"failure_code" text,
	"created_at" timestamp with time zone DEFAULT now() NOT NULL,
	"updated_at" timestamp with time zone DEFAULT now() NOT NULL,
	CONSTRAINT "file_uploads_tenant_key_uq" UNIQUE("tenant_id","id"),
	CONSTRAINT "file_uploads_unique_0" UNIQUE("tenant_id","requested_by","idempotency_key"),
	CONSTRAINT "file_uploads_unique_1" UNIQUE("location_id","staging_key"),
	CONSTRAINT "file_uploads_check_0" CHECK (expected_size_bytes>0 AND expected_size_bytes<=max_size_bytes),
	CONSTRAINT "file_uploads_check_1" CHECK (upload_mode<>'multipart' OR multipart_upload_id IS NOT NULL),
	CONSTRAINT "file_uploads_check_2" CHECK (upload_mode IN ('single','multipart')),
	CONSTRAINT "file_uploads_check_3" CHECK (status IN ('issued','uploading','uploaded','verifying','accepted','rejected','expired','aborted'))
);
--> statement-breakpoint
ALTER TABLE "file_uploads" ENABLE ROW LEVEL SECURITY;--> statement-breakpoint
CREATE TABLE "files" (
	"id" uuid PRIMARY KEY DEFAULT gen_random_uuid() NOT NULL,
	"tenant_id" uuid NOT NULL,
	"uploaded_by" text,
	"original_name" text NOT NULL,
	"retention_until" timestamp with time zone,
	"deleted_at" timestamp with time zone,
	"created_at" timestamp with time zone DEFAULT now() NOT NULL,
	"updated_at" timestamp with time zone DEFAULT now() NOT NULL,
	"owner_principal_id" uuid NOT NULL,
	"scope_kind" text NOT NULL,
	"ticket_id" uuid,
	"channel_id" text,
	"document_id" uuid,
	"report_id" uuid,
	"status" text NOT NULL,
	"accepted_object_id" uuid,
	"declared_mime_type" text,
	"legal_hold" boolean DEFAULT false NOT NULL,
	CONSTRAINT "files_tenant_key_uq" UNIQUE("tenant_id","id"),
	CONSTRAINT "files_check_0" CHECK (num_nonnulls(ticket_id,channel_id,document_id,report_id)=1),
	CONSTRAINT "files_check_1" CHECK ((scope_kind='ticket' AND ticket_id IS NOT NULL) OR (scope_kind='channel' AND channel_id IS NOT NULL) OR (scope_kind='document' AND document_id IS NOT NULL) OR (scope_kind='report' AND report_id IS NOT NULL)),
	CONSTRAINT "files_check_2" CHECK (status<>'ready' OR accepted_object_id IS NOT NULL),
	CONSTRAINT "files_check_3" CHECK (scope_kind IN ('ticket','channel','document','report')),
	CONSTRAINT "files_check_4" CHECK (status IN ('staged','verifying','ready','rejected','deletion_pending','deleted','missing'))
);
--> statement-breakpoint
ALTER TABLE "files" ENABLE ROW LEVEL SECURITY;--> statement-breakpoint
CREATE TABLE "incident_types" (
	"id" uuid PRIMARY KEY DEFAULT gen_random_uuid() NOT NULL,
	"tenant_id" uuid NOT NULL,
	"category_id" uuid NOT NULL,
	"code" text NOT NULL,
	"name" text NOT NULL,
	"default_priority" text NOT NULL,
	"requires_visit" boolean NOT NULL,
	"created_at" timestamp with time zone DEFAULT now() NOT NULL,
	"updated_at" timestamp with time zone DEFAULT now() NOT NULL,
	CONSTRAINT "incident_types_tenant_key_uq" UNIQUE("tenant_id","id"),
	CONSTRAINT "incident_types_unique_0" UNIQUE("tenant_id","code")
);
--> statement-breakpoint
ALTER TABLE "incident_types" ENABLE ROW LEVEL SECURITY;--> statement-breakpoint
CREATE TABLE "ingestion_jobs" (
	"id" uuid PRIMARY KEY DEFAULT gen_random_uuid() NOT NULL,
	"tenant_id" uuid NOT NULL,
	"version_id" uuid NOT NULL,
	"embedding_model_id" uuid NOT NULL,
	"status" text NOT NULL,
	"idempotency_key" text NOT NULL,
	"parser_version" text NOT NULL,
	"chunker_version" text NOT NULL,
	"attempts" integer DEFAULT 0 NOT NULL,
	"lease_owner" text,
	"lease_until" timestamp with time zone,
	"expected_chunks" integer,
	"completed_chunks" integer DEFAULT 0 NOT NULL,
	"error_code" text,
	"created_at" timestamp with time zone DEFAULT now() NOT NULL,
	"updated_at" timestamp with time zone DEFAULT now() NOT NULL,
	CONSTRAINT "ingestion_jobs_tenant_key_uq" UNIQUE("tenant_id","id"),
	CONSTRAINT "ingestion_jobs_unique_0" UNIQUE("tenant_id","idempotency_key"),
	CONSTRAINT "ingestion_jobs_check_0" CHECK (status IN ('queued','parsing','embedding','completed','failed','cancelled'))
);
--> statement-breakpoint
ALTER TABLE "ingestion_jobs" ENABLE ROW LEVEL SECURITY;--> statement-breakpoint
CREATE TABLE "intelligence_channel_mappings" (
	"user_id" text NOT NULL,
	"channel_id" text NOT NULL,
	"thread_id" text NOT NULL,
	"created_at" timestamp with time zone DEFAULT now() NOT NULL,
	"updated_at" timestamp with time zone DEFAULT now() NOT NULL,
	CONSTRAINT "intelligence_channel_mappings_user_id_channel_id_pk" PRIMARY KEY("user_id","channel_id"),
	CONSTRAINT "intelligence_channel_mappings_unique_0" UNIQUE("thread_id")
);
--> statement-breakpoint
CREATE TABLE "interruption_scopes" (
	"tenant_id" uuid NOT NULL,
	"interruption_id" uuid NOT NULL,
	"scope_id" uuid NOT NULL,
	"created_at" timestamp with time zone DEFAULT now() NOT NULL,
	CONSTRAINT "interruption_scopes_tenant_id_interruption_id_scope_id_pk" PRIMARY KEY("tenant_id","interruption_id","scope_id")
);
--> statement-breakpoint
ALTER TABLE "interruption_scopes" ENABLE ROW LEVEL SECURITY;--> statement-breakpoint
CREATE TABLE "invoice_lines" (
	"id" uuid PRIMARY KEY DEFAULT gen_random_uuid() NOT NULL,
	"tenant_id" uuid NOT NULL,
	"invoice_id" uuid NOT NULL,
	"line_no" integer NOT NULL,
	"category_id" uuid NOT NULL,
	"description" text NOT NULL,
	"quantity" numeric(12, 3) NOT NULL,
	"unit_price" numeric(18, 2) NOT NULL,
	"discount" numeric(18, 2) DEFAULT '0' NOT NULL,
	"tax_rate" numeric(9, 4) DEFAULT '0' NOT NULL,
	"net_amount" numeric(18, 2) NOT NULL,
	"tax_amount" numeric(18, 2) NOT NULL,
	"total_amount" numeric(18, 2) NOT NULL,
	"created_at" timestamp with time zone DEFAULT now() NOT NULL,
	"updated_at" timestamp with time zone DEFAULT now() NOT NULL,
	CONSTRAINT "invoice_lines_tenant_key_uq" UNIQUE("tenant_id","id"),
	CONSTRAINT "invoice_lines_unique_0" UNIQUE("invoice_id","line_no"),
	CONSTRAINT "invoice_lines_check_0" CHECK (quantity>0 AND unit_price>=0),
	CONSTRAINT "invoice_lines_check_1" CHECK (tax_rate BETWEEN 0 AND 1),
	CONSTRAINT "invoice_lines_check_2" CHECK (discount>=0),
	CONSTRAINT "invoice_lines_check_3" CHECK (total_amount=net_amount+tax_amount)
);
--> statement-breakpoint
ALTER TABLE "invoice_lines" ENABLE ROW LEVEL SECURITY;--> statement-breakpoint
CREATE TABLE "invoices" (
	"id" uuid PRIMARY KEY DEFAULT gen_random_uuid() NOT NULL,
	"tenant_id" uuid NOT NULL,
	"ticket_id" uuid NOT NULL,
	"work_order_id" uuid,
	"invoice_no" text NOT NULL,
	"issued_by_staff_id" uuid NOT NULL,
	"bill_to_user_id" text NOT NULL,
	"status" text NOT NULL,
	"currency" char(3) DEFAULT 'VND' NOT NULL,
	"subtotal" numeric(18, 2) NOT NULL,
	"tax_total" numeric(18, 2) NOT NULL,
	"discount_total" numeric(18, 2) DEFAULT '0' NOT NULL,
	"grand_total" numeric(18, 2) NOT NULL,
	"issued_at" timestamp with time zone,
	"due_at" timestamp with time zone,
	"provider" text,
	"provider_invoice_id" text,
	"legal_invoice_file_id" uuid,
	"supersedes_invoice_id" uuid,
	"created_at" timestamp with time zone DEFAULT now() NOT NULL,
	"updated_at" timestamp with time zone DEFAULT now() NOT NULL,
	"provider_account_ref" text,
	CONSTRAINT "invoices_tenant_key_uq" UNIQUE("tenant_id","id"),
	CONSTRAINT "invoices_unique_0" UNIQUE("tenant_id","invoice_no"),
	CONSTRAINT "invoices_unique_1" UNIQUE("provider","provider_account_ref","provider_invoice_id"),
	CONSTRAINT "invoices_check_0" CHECK (grand_total=subtotal+tax_total-discount_total),
	CONSTRAINT "invoices_check_1" CHECK (grand_total>=0),
	CONSTRAINT "invoices_check_2" CHECK (status IN ('draft','issued','void','replaced'))
);
--> statement-breakpoint
ALTER TABLE "invoices" ENABLE ROW LEVEL SECURITY;--> statement-breakpoint
CREATE TABLE "knowledge_bases" (
	"id" uuid PRIMARY KEY DEFAULT gen_random_uuid() NOT NULL,
	"tenant_id" uuid NOT NULL,
	"domain_id" uuid NOT NULL,
	"code" text NOT NULL,
	"name" text NOT NULL,
	"description" text,
	"status" text NOT NULL,
	"created_at" timestamp with time zone DEFAULT now() NOT NULL,
	"updated_at" timestamp with time zone DEFAULT now() NOT NULL,
	CONSTRAINT "knowledge_bases_tenant_key_uq" UNIQUE("tenant_id","id"),
	CONSTRAINT "knowledge_bases_unique_0" UNIQUE("tenant_id","code"),
	CONSTRAINT "knowledge_bases_check_0" CHECK (status IN ('active','archived'))
);
--> statement-breakpoint
ALTER TABLE "knowledge_bases" ENABLE ROW LEVEL SECURITY;--> statement-breakpoint
CREATE TABLE "knowledge_categories" (
	"id" uuid PRIMARY KEY DEFAULT gen_random_uuid() NOT NULL,
	"tenant_id" uuid NOT NULL,
	"code" text NOT NULL,
	"name" text NOT NULL,
	"parent_id" uuid,
	"created_at" timestamp with time zone DEFAULT now() NOT NULL,
	"updated_at" timestamp with time zone DEFAULT now() NOT NULL,
	CONSTRAINT "knowledge_categories_tenant_key_uq" UNIQUE("tenant_id","id"),
	CONSTRAINT "knowledge_categories_unique_0" UNIQUE("tenant_id","code")
);
--> statement-breakpoint
ALTER TABLE "knowledge_categories" ENABLE ROW LEVEL SECURITY;--> statement-breakpoint
CREATE TABLE "knowledge_chunks" (
	"id" uuid PRIMARY KEY DEFAULT gen_random_uuid() NOT NULL,
	"tenant_id" uuid NOT NULL,
	"version_id" uuid NOT NULL,
	"ordinal" integer NOT NULL,
	"text_content" text NOT NULL,
	"text_hash" text NOT NULL,
	"token_count" integer NOT NULL,
	"page_start" integer,
	"page_end" integer,
	"heading_path" text,
	"search_tsv" "tsvector" NOT NULL,
	"created_at" timestamp with time zone DEFAULT now() NOT NULL,
	CONSTRAINT "knowledge_chunks_tenant_key_uq" UNIQUE("tenant_id","id"),
	CONSTRAINT "knowledge_chunks_unique_0" UNIQUE("version_id","ordinal")
);
--> statement-breakpoint
ALTER TABLE "knowledge_chunks" ENABLE ROW LEVEL SECURITY;--> statement-breakpoint
CREATE TABLE "knowledge_documents" (
	"id" uuid PRIMARY KEY DEFAULT gen_random_uuid() NOT NULL,
	"tenant_id" uuid NOT NULL,
	"knowledge_base_id" uuid NOT NULL,
	"category_id" uuid NOT NULL,
	"code" text NOT NULL,
	"title" text NOT NULL,
	"owner_management_id" uuid,
	"status" text NOT NULL,
	"language" text DEFAULT 'vi' NOT NULL,
	"active_version_id" uuid,
	"created_at" timestamp with time zone DEFAULT now() NOT NULL,
	"updated_at" timestamp with time zone DEFAULT now() NOT NULL,
	"memory_namespace_id" uuid,
	CONSTRAINT "knowledge_documents_tenant_key_uq" UNIQUE("tenant_id","id"),
	CONSTRAINT "knowledge_documents_unique_0" UNIQUE("knowledge_base_id","code"),
	CONSTRAINT "knowledge_documents_check_0" CHECK (status IN ('draft','published','archived'))
);
--> statement-breakpoint
ALTER TABLE "knowledge_documents" ENABLE ROW LEVEL SECURITY;--> statement-breakpoint
CREATE TABLE "knowledge_embeddings" (
	"id" uuid PRIMARY KEY DEFAULT gen_random_uuid() NOT NULL,
	"tenant_id" uuid NOT NULL,
	"chunk_id" uuid NOT NULL,
	"model_id" uuid NOT NULL,
	"embedding" vector(1536) NOT NULL,
	"content_hash" text NOT NULL,
	"created_at" timestamp with time zone DEFAULT now() NOT NULL,
	CONSTRAINT "knowledge_embeddings_tenant_key_uq" UNIQUE("tenant_id","id"),
	CONSTRAINT "knowledge_embeddings_unique_0" UNIQUE("chunk_id","model_id")
);
--> statement-breakpoint
ALTER TABLE "knowledge_embeddings" ENABLE ROW LEVEL SECURITY;--> statement-breakpoint
CREATE TABLE "knowledge_reviews" (
	"id" uuid PRIMARY KEY DEFAULT gen_random_uuid() NOT NULL,
	"tenant_id" uuid NOT NULL,
	"document_version_id" uuid,
	"memory_candidate_id" uuid,
	"decision" text NOT NULL,
	"reviewer_user_id" text NOT NULL,
	"reason" text,
	"reviewed_at" timestamp with time zone NOT NULL,
	"created_at" timestamp with time zone DEFAULT now() NOT NULL,
	"subject_seq" bigint NOT NULL,
	"subject_hash" text NOT NULL,
	CONSTRAINT "knowledge_reviews_tenant_key_uq" UNIQUE("tenant_id","id"),
	CONSTRAINT "knowledge_reviews_check_0" CHECK (num_nonnulls(document_version_id,memory_candidate_id)=1),
	CONSTRAINT "knowledge_reviews_check_1" CHECK (decision IN ('approve','reject','revoke'))
);
--> statement-breakpoint
ALTER TABLE "knowledge_reviews" ENABLE ROW LEVEL SECURITY;--> statement-breakpoint
CREATE TABLE "mailbox_deliveries" (
	"id" uuid PRIMARY KEY DEFAULT gen_random_uuid() NOT NULL,
	"tenant_id" uuid NOT NULL,
	"mailbox_id" uuid NOT NULL,
	"recipient_member_id" uuid NOT NULL,
	"status" text NOT NULL,
	"attempts" integer DEFAULT 0 NOT NULL,
	"available_at" timestamp with time zone NOT NULL,
	"ack_at" timestamp with time zone,
	"last_error" text,
	"created_at" timestamp with time zone DEFAULT now() NOT NULL,
	"updated_at" timestamp with time zone DEFAULT now() NOT NULL,
	CONSTRAINT "mailbox_deliveries_tenant_key_uq" UNIQUE("tenant_id","id"),
	CONSTRAINT "mailbox_deliveries_unique_0" UNIQUE("mailbox_id","recipient_member_id"),
	CONSTRAINT "mailbox_deliveries_check_0" CHECK (status IN ('pending','delivered','acked','dead'))
);
--> statement-breakpoint
ALTER TABLE "mailbox_deliveries" ENABLE ROW LEVEL SECURITY;--> statement-breakpoint
CREATE TABLE "management_coverage" (
	"id" uuid PRIMARY KEY DEFAULT gen_random_uuid() NOT NULL,
	"tenant_id" uuid NOT NULL,
	"management_unit_id" uuid NOT NULL,
	"scope_id" uuid NOT NULL,
	"service_category_id" uuid NOT NULL,
	"valid_from" timestamp with time zone NOT NULL,
	"valid_to" timestamp with time zone,
	"priority" integer DEFAULT 0 NOT NULL,
	"created_at" timestamp with time zone DEFAULT now() NOT NULL,
	"updated_at" timestamp with time zone DEFAULT now() NOT NULL,
	CONSTRAINT "management_coverage_tenant_key_uq" UNIQUE("tenant_id","id")
);
--> statement-breakpoint
ALTER TABLE "management_coverage" ENABLE ROW LEVEL SECURITY;--> statement-breakpoint
CREATE TABLE "management_units" (
	"id" uuid PRIMARY KEY DEFAULT gen_random_uuid() NOT NULL,
	"tenant_id" uuid NOT NULL,
	"code" text NOT NULL,
	"name" text NOT NULL,
	"status" text NOT NULL,
	"contact_phone" text,
	"contact_email" text,
	"created_at" timestamp with time zone DEFAULT now() NOT NULL,
	"updated_at" timestamp with time zone DEFAULT now() NOT NULL,
	CONSTRAINT "management_units_tenant_key_uq" UNIQUE("tenant_id","id"),
	CONSTRAINT "management_units_unique_0" UNIQUE("tenant_id","code")
);
--> statement-breakpoint
ALTER TABLE "management_units" ENABLE ROW LEVEL SECURITY;--> statement-breakpoint
CREATE TABLE "mcp_servers" (
	"id" text PRIMARY KEY NOT NULL,
	"title" text NOT NULL,
	"vendor" text NOT NULL,
	"url" text NOT NULL,
	"provenance" text DEFAULT 'first-party' NOT NULL,
	"credential_id" uuid,
	"auth_scheme" text,
	"tools_refreshed_at" timestamp with time zone,
	"last_error" text,
	"added_by" text,
	"created_at" timestamp with time zone DEFAULT now() NOT NULL,
	"updated_at" timestamp with time zone DEFAULT now() NOT NULL,
	"tenant_id" uuid DEFAULT nullif(current_setting('app.tenant_id', true), '')::uuid NOT NULL,
	"workspace_id" uuid,
	CONSTRAINT "mcp_servers_tenant_key_uq" UNIQUE("tenant_id","id")
);
--> statement-breakpoint
ALTER TABLE "mcp_servers" ENABLE ROW LEVEL SECURITY;--> statement-breakpoint
CREATE TABLE "mcp_tools" (
	"server_id" text NOT NULL,
	"name" text NOT NULL,
	"description" text DEFAULT '' NOT NULL,
	"input_schema" jsonb DEFAULT '{}'::jsonb NOT NULL,
	"effect" text,
	"destructive" boolean DEFAULT false NOT NULL,
	"version" text,
	"created_at" timestamp with time zone DEFAULT now() NOT NULL,
	"tenant_id" uuid DEFAULT nullif(current_setting('app.tenant_id', true), '')::uuid NOT NULL,
	CONSTRAINT "mcp_tools_server_id_name_pk" PRIMARY KEY("server_id","name")
);
--> statement-breakpoint
ALTER TABLE "mcp_tools" ENABLE ROW LEVEL SECURITY;--> statement-breakpoint
CREATE TABLE "mcp_user_credentials" (
	"server_id" text NOT NULL,
	"user_id" text NOT NULL,
	"credential_id" uuid NOT NULL,
	"scope" text NOT NULL,
	"connected_at" timestamp with time zone DEFAULT now() NOT NULL,
	"updated_at" timestamp with time zone DEFAULT now() NOT NULL,
	"tenant_id" uuid DEFAULT nullif(current_setting('app.tenant_id', true), '')::uuid NOT NULL,
	CONSTRAINT "mcp_user_credentials_tenant_id_server_id_user_id_pk" PRIMARY KEY("tenant_id","server_id","user_id")
);
--> statement-breakpoint
ALTER TABLE "mcp_user_credentials" ENABLE ROW LEVEL SECURITY;--> statement-breakpoint
CREATE TABLE "memory_candidates" (
	"id" uuid PRIMARY KEY DEFAULT gen_random_uuid() NOT NULL,
	"tenant_id" uuid NOT NULL,
	"source_ticket_id" uuid,
	"source_run_id" uuid,
	"scope_id" uuid NOT NULL,
	"proposed_text" text NOT NULL,
	"evidence" jsonb NOT NULL,
	"pii_redacted" boolean DEFAULT false NOT NULL,
	"status" text NOT NULL,
	"proposed_by_agent_id" text,
	"reason" text NOT NULL,
	"created_at" timestamp with time zone DEFAULT now() NOT NULL,
	"updated_at" timestamp with time zone DEFAULT now() NOT NULL,
	"namespace_id" uuid NOT NULL,
	"source_binding_id" uuid,
	"subject_user_id" text,
	"proposal_revision" integer DEFAULT 1 NOT NULL,
	"proposal_hash" text NOT NULL,
	"supersedes_candidate_id" uuid,
	CONSTRAINT "memory_candidates_tenant_key_uq" UNIQUE("tenant_id","id"),
	CONSTRAINT "memory_candidates_check_0" CHECK (status IN ('pending','approved','rejected','published','revoked'))
);
--> statement-breakpoint
ALTER TABLE "memory_candidates" ENABLE ROW LEVEL SECURITY;--> statement-breakpoint
CREATE TABLE "memory_namespaces" (
	"id" uuid PRIMARY KEY DEFAULT gen_random_uuid() NOT NULL,
	"tenant_id" uuid NOT NULL,
	"owner_principal_id" uuid NOT NULL,
	"kind" text NOT NULL,
	"workspace_id" uuid,
	"team_id" uuid,
	"namespace_key" text NOT NULL,
	"purpose" text NOT NULL,
	"status" text NOT NULL,
	"retention_days" integer,
	"authz_version" bigint DEFAULT 1 NOT NULL,
	"created_at" timestamp with time zone DEFAULT now() NOT NULL,
	"updated_at" timestamp with time zone DEFAULT now() NOT NULL,
	CONSTRAINT "memory_namespaces_tenant_key_uq" UNIQUE("tenant_id","id"),
	CONSTRAINT "memory_namespaces_check_0" CHECK ((kind='personal' AND workspace_id IS NULL AND team_id IS NULL) OR (kind='workspace' AND workspace_id IS NOT NULL AND team_id IS NULL) OR (kind='team' AND workspace_id IS NOT NULL AND team_id IS NOT NULL)),
	CONSTRAINT "memory_namespaces_check_1" CHECK (kind IN ('personal','team','workspace')),
	CONSTRAINT "memory_namespaces_check_2" CHECK (status IN ('active','revoked','purging','purged'))
);
--> statement-breakpoint
ALTER TABLE "memory_namespaces" ENABLE ROW LEVEL SECURITY;--> statement-breakpoint
CREATE TABLE "memory_publications" (
	"id" uuid PRIMARY KEY DEFAULT gen_random_uuid() NOT NULL,
	"tenant_id" uuid NOT NULL,
	"candidate_id" uuid NOT NULL,
	"approval_review_id" uuid NOT NULL,
	"document_id" uuid NOT NULL,
	"version_id" uuid NOT NULL,
	"published_at" timestamp with time zone NOT NULL,
	"revoked_at" timestamp with time zone,
	"created_at" timestamp with time zone DEFAULT now() NOT NULL,
	"updated_at" timestamp with time zone DEFAULT now() NOT NULL,
	"namespace_id" uuid NOT NULL,
	CONSTRAINT "memory_publications_tenant_key_uq" UNIQUE("tenant_id","id"),
	CONSTRAINT "memory_publications_unique_0" UNIQUE("candidate_id")
);
--> statement-breakpoint
ALTER TABLE "memory_publications" ENABLE ROW LEVEL SECURITY;--> statement-breakpoint
CREATE TABLE "message_files" (
	"tenant_id" uuid NOT NULL,
	"message_id" uuid NOT NULL,
	"file_id" uuid NOT NULL,
	"ordinal" integer DEFAULT 0 NOT NULL,
	"created_at" timestamp with time zone DEFAULT now() NOT NULL,
	CONSTRAINT "message_files_tenant_id_message_id_file_id_pk" PRIMARY KEY("tenant_id","message_id","file_id"),
	CONSTRAINT "message_files_unique_0" UNIQUE("message_id","ordinal")
);
--> statement-breakpoint
ALTER TABLE "message_files" ENABLE ROW LEVEL SECURITY;--> statement-breakpoint
CREATE TABLE "message_mentions" (
	"tenant_id" uuid NOT NULL,
	"message_id" uuid NOT NULL,
	"agent_id" text NOT NULL,
	"requested_by" text NOT NULL,
	"status" text NOT NULL,
	"resolved_run_id" uuid,
	"created_at" timestamp with time zone DEFAULT now() NOT NULL,
	CONSTRAINT "message_mentions_tenant_id_message_id_agent_id_pk" PRIMARY KEY("tenant_id","message_id","agent_id"),
	CONSTRAINT "message_mentions_check_0" CHECK (status IN ('queued','running','done','failed','refused'))
);
--> statement-breakpoint
ALTER TABLE "message_mentions" ENABLE ROW LEVEL SECURITY;--> statement-breakpoint
CREATE TABLE "messages" (
	"id" uuid PRIMARY KEY DEFAULT gen_random_uuid() NOT NULL,
	"tenant_id" uuid NOT NULL,
	"channel_id" text NOT NULL,
	"seq" bigint NOT NULL,
	"sender_kind" text NOT NULL,
	"sender_user_id" text,
	"sender_agent_id" text,
	"run_id" uuid,
	"reply_to_id" uuid,
	"visibility" text NOT NULL,
	"body" jsonb NOT NULL,
	"client_message_id" text,
	"source_event_id" uuid,
	"created_at" timestamp with time zone DEFAULT now() NOT NULL,
	CONSTRAINT "messages_tenant_key_uq" UNIQUE("tenant_id","id"),
	CONSTRAINT "messages_unique_0" UNIQUE("channel_id","seq"),
	CONSTRAINT "messages_unique_1" UNIQUE("channel_id","sender_user_id","client_message_id"),
	CONSTRAINT "messages_unique_2" UNIQUE("channel_id","source_event_id","sender_agent_id"),
	CONSTRAINT "messages_check_0" CHECK (visibility IN ('room','internal','customer'))
);
--> statement-breakpoint
ALTER TABLE "messages" ENABLE ROW LEVEL SECURITY;--> statement-breakpoint
CREATE TABLE "model_profiles" (
	"id" uuid PRIMARY KEY DEFAULT gen_random_uuid() NOT NULL,
	"tenant_id" uuid NOT NULL,
	"workspace_id" uuid,
	"code" text NOT NULL,
	"provider" text NOT NULL,
	"model_name" text NOT NULL,
	"credential_id" uuid NOT NULL,
	"parameters" jsonb NOT NULL,
	"enabled" boolean DEFAULT true NOT NULL,
	"created_at" timestamp with time zone DEFAULT now() NOT NULL,
	"updated_at" timestamp with time zone DEFAULT now() NOT NULL,
	CONSTRAINT "model_profiles_tenant_key_uq" UNIQUE("tenant_id","id")
);
--> statement-breakpoint
ALTER TABLE "model_profiles" ENABLE ROW LEVEL SECURITY;--> statement-breakpoint
CREATE TABLE "notification_deliveries" (
	"id" uuid PRIMARY KEY DEFAULT gen_random_uuid() NOT NULL,
	"tenant_id" uuid NOT NULL,
	"user_id" text NOT NULL,
	"ticket_event_id" uuid,
	"message_id" uuid,
	"interruption_id" uuid,
	"channel" text NOT NULL,
	"dedupe_key" text NOT NULL,
	"payload" jsonb NOT NULL,
	"status" text NOT NULL,
	"attempts" integer DEFAULT 0 NOT NULL,
	"available_at" timestamp with time zone NOT NULL,
	"sent_at" timestamp with time zone,
	"read_at" timestamp with time zone,
	"provider_message_id" text,
	"last_error" text,
	"created_at" timestamp with time zone DEFAULT now() NOT NULL,
	"updated_at" timestamp with time zone DEFAULT now() NOT NULL,
	CONSTRAINT "notification_deliveries_tenant_key_uq" UNIQUE("tenant_id","id"),
	CONSTRAINT "notification_deliveries_unique_0" UNIQUE("tenant_id","user_id","channel","dedupe_key"),
	CONSTRAINT "notification_deliveries_check_0" CHECK (channel IN ('in_app','push','sms','email')),
	CONSTRAINT "notification_deliveries_check_1" CHECK (status IN ('pending','sent','failed','dead'))
);
--> statement-breakpoint
ALTER TABLE "notification_deliveries" ENABLE ROW LEVEL SECURITY;--> statement-breakpoint
CREATE TABLE "payment_allocations" (
	"id" uuid PRIMARY KEY DEFAULT gen_random_uuid() NOT NULL,
	"tenant_id" uuid NOT NULL,
	"payment_id" uuid NOT NULL,
	"invoice_id" uuid NOT NULL,
	"amount" numeric(18, 2) NOT NULL,
	"allocated_at" timestamp with time zone NOT NULL,
	"idempotency_key" text NOT NULL,
	"created_at" timestamp with time zone DEFAULT now() NOT NULL,
	CONSTRAINT "payment_allocations_tenant_key_uq" UNIQUE("tenant_id","id"),
	CONSTRAINT "payment_allocations_unique_0" UNIQUE("tenant_id","idempotency_key"),
	CONSTRAINT "payment_allocations_check_0" CHECK (amount>0)
);
--> statement-breakpoint
ALTER TABLE "payment_allocations" ENABLE ROW LEVEL SECURITY;--> statement-breakpoint
CREATE TABLE "payment_intents" (
	"id" uuid PRIMARY KEY DEFAULT gen_random_uuid() NOT NULL,
	"tenant_id" uuid NOT NULL,
	"invoice_id" uuid NOT NULL,
	"provider" text NOT NULL,
	"merchant_account_ref" text NOT NULL,
	"provider_intent_id" text,
	"idempotency_key" text NOT NULL,
	"amount" numeric(18, 2) NOT NULL,
	"currency" char(3) NOT NULL,
	"status" text NOT NULL,
	"qr_payload_ciphertext" text,
	"expires_at" timestamp with time zone NOT NULL,
	"paid_at" timestamp with time zone,
	"created_at" timestamp with time zone DEFAULT now() NOT NULL,
	"updated_at" timestamp with time zone DEFAULT now() NOT NULL,
	CONSTRAINT "payment_intents_tenant_key_uq" UNIQUE("tenant_id","id"),
	CONSTRAINT "payment_intents_unique_0" UNIQUE("tenant_id","idempotency_key"),
	CONSTRAINT "payment_intents_unique_1" UNIQUE("provider","merchant_account_ref","provider_intent_id"),
	CONSTRAINT "payment_intents_check_0" CHECK (status IN ('created','pending','succeeded','expired','cancelled','failed'))
);
--> statement-breakpoint
ALTER TABLE "payment_intents" ENABLE ROW LEVEL SECURITY;--> statement-breakpoint
CREATE TABLE "payment_webhook_receipts" (
	"id" uuid PRIMARY KEY DEFAULT gen_random_uuid() NOT NULL,
	"tenant_id" uuid NOT NULL,
	"provider" text NOT NULL,
	"merchant_account_ref" text NOT NULL,
	"provider_event_id" text NOT NULL,
	"raw_body_hash" text NOT NULL,
	"signature_valid" boolean NOT NULL,
	"received_at" timestamp with time zone NOT NULL,
	"payload_redacted" jsonb NOT NULL,
	"intent_id" uuid,
	"created_at" timestamp with time zone DEFAULT now() NOT NULL,
	CONSTRAINT "payment_webhook_receipts_tenant_key_uq" UNIQUE("tenant_id","id"),
	CONSTRAINT "payment_webhook_receipts_unique_0" UNIQUE("provider","merchant_account_ref","provider_event_id")
);
--> statement-breakpoint
ALTER TABLE "payment_webhook_receipts" ENABLE ROW LEVEL SECURITY;--> statement-breakpoint
CREATE TABLE "payments" (
	"id" uuid PRIMARY KEY DEFAULT gen_random_uuid() NOT NULL,
	"tenant_id" uuid NOT NULL,
	"invoice_id" uuid NOT NULL,
	"intent_id" uuid NOT NULL,
	"receipt_id" uuid,
	"provider" text NOT NULL,
	"merchant_account_ref" text NOT NULL,
	"provider_transaction_id" text NOT NULL,
	"amount" numeric(18, 2) NOT NULL,
	"currency" char(3) NOT NULL,
	"settled_at" timestamp with time zone NOT NULL,
	"reconciliation_status" text NOT NULL,
	"created_at" timestamp with time zone DEFAULT now() NOT NULL,
	CONSTRAINT "payments_tenant_key_uq" UNIQUE("tenant_id","id"),
	CONSTRAINT "payments_unique_0" UNIQUE("provider","merchant_account_ref","provider_transaction_id"),
	CONSTRAINT "payments_check_0" CHECK (amount>0),
	CONSTRAINT "payments_check_1" CHECK (reconciliation_status IN ('confirmed','review_required'))
);
--> statement-breakpoint
ALTER TABLE "payments" ENABLE ROW LEVEL SECURITY;--> statement-breakpoint
CREATE TABLE "platform_admins" (
	"user_id" text PRIMARY KEY NOT NULL,
	"granted_by" text,
	"created_at" timestamp with time zone DEFAULT now() NOT NULL
);
--> statement-breakpoint
CREATE TABLE "plugin_grants" (
	"kind" text NOT NULL,
	"ref" text NOT NULL,
	"agent_id" text NOT NULL,
	"granted_by" text,
	"granted_at" timestamp with time zone DEFAULT now() NOT NULL,
	"updated_at" timestamp with time zone DEFAULT now() NOT NULL,
	"tenant_id" uuid DEFAULT nullif(current_setting('app.tenant_id', true), '')::uuid NOT NULL,
	CONSTRAINT "plugin_grants_tenant_id_kind_ref_agent_id_pk" PRIMARY KEY("tenant_id","kind","ref","agent_id")
);
--> statement-breakpoint
ALTER TABLE "plugin_grants" ENABLE ROW LEVEL SECURITY;--> statement-breakpoint
CREATE TABLE "reception_sessions" (
	"id" uuid PRIMARY KEY DEFAULT gen_random_uuid() NOT NULL,
	"tenant_id" uuid NOT NULL,
	"channel_id" text NOT NULL,
	"customer_user_id" text NOT NULL,
	"system_agent_id" text NOT NULL,
	"workflow_version" text NOT NULL,
	"status" text NOT NULL,
	"last_event_seq" bigint DEFAULT 0 NOT NULL,
	"created_at" timestamp with time zone DEFAULT now() NOT NULL,
	"updated_at" timestamp with time zone DEFAULT now() NOT NULL,
	"binding_id" uuid NOT NULL,
	CONSTRAINT "reception_sessions_tenant_key_uq" UNIQUE("tenant_id","id"),
	CONSTRAINT "reception_sessions_unique_0" UNIQUE("channel_id"),
	CONSTRAINT "reception_sessions_unique_1" UNIQUE("binding_id"),
	CONSTRAINT "reception_sessions_check_0" CHECK (status IN ('active','waiting','closed','failed'))
);
--> statement-breakpoint
ALTER TABLE "reception_sessions" ENABLE ROW LEVEL SECURITY;--> statement-breakpoint
CREATE TABLE "reception_waits" (
	"id" uuid PRIMARY KEY DEFAULT gen_random_uuid() NOT NULL,
	"tenant_id" uuid NOT NULL,
	"session_id" uuid NOT NULL,
	"ticket_id" uuid NOT NULL,
	"interrupt_id" text,
	"generation" integer NOT NULL,
	"expected_event_types" text[] NOT NULL,
	"after_event_seq" bigint NOT NULL,
	"status" text NOT NULL,
	"resumed_event_id" uuid,
	"expires_at" timestamp with time zone,
	"created_at" timestamp with time zone DEFAULT now() NOT NULL,
	"updated_at" timestamp with time zone DEFAULT now() NOT NULL,
	"operation_id" uuid,
	CONSTRAINT "reception_waits_tenant_key_uq" UNIQUE("tenant_id","id"),
	CONSTRAINT "reception_waits_unique_0" UNIQUE("session_id","interrupt_id","generation"),
	CONSTRAINT "reception_waits_check_0" CHECK (status NOT IN ('open','resuming','consumed') OR interrupt_id IS NOT NULL)
);
--> statement-breakpoint
ALTER TABLE "reception_waits" ENABLE ROW LEVEL SECURITY;--> statement-breakpoint
CREATE TABLE "refund_allocations" (
	"id" uuid PRIMARY KEY DEFAULT gen_random_uuid() NOT NULL,
	"tenant_id" uuid NOT NULL,
	"refund_id" uuid NOT NULL,
	"payment_allocation_id" uuid NOT NULL,
	"amount" numeric(18, 2) NOT NULL,
	"created_at" timestamp with time zone DEFAULT now() NOT NULL,
	CONSTRAINT "refund_allocations_tenant_key_uq" UNIQUE("tenant_id","id"),
	CONSTRAINT "refund_allocations_unique_0" UNIQUE("refund_id","payment_allocation_id"),
	CONSTRAINT "refund_allocations_check_0" CHECK (amount>0)
);
--> statement-breakpoint
ALTER TABLE "refund_allocations" ENABLE ROW LEVEL SECURITY;--> statement-breakpoint
CREATE TABLE "refunds" (
	"id" uuid PRIMARY KEY DEFAULT gen_random_uuid() NOT NULL,
	"tenant_id" uuid NOT NULL,
	"payment_id" uuid NOT NULL,
	"amount" numeric(18, 2) NOT NULL,
	"reason" text NOT NULL,
	"status" text NOT NULL,
	"provider_refund_id" text,
	"idempotency_key" text NOT NULL,
	"requested_by" text NOT NULL,
	"approved_by" text,
	"settled_at" timestamp with time zone,
	"created_at" timestamp with time zone DEFAULT now() NOT NULL,
	"updated_at" timestamp with time zone DEFAULT now() NOT NULL,
	CONSTRAINT "refunds_tenant_key_uq" UNIQUE("tenant_id","id"),
	CONSTRAINT "refunds_unique_0" UNIQUE("tenant_id","idempotency_key"),
	CONSTRAINT "refunds_check_0" CHECK (amount>0),
	CONSTRAINT "refunds_check_1" CHECK (status IN ('requested','approved','pending','succeeded','failed'))
);
--> statement-breakpoint
ALTER TABLE "refunds" ENABLE ROW LEVEL SECURITY;--> statement-breakpoint
CREATE TABLE "report_requests" (
	"id" uuid PRIMARY KEY DEFAULT gen_random_uuid() NOT NULL,
	"tenant_id" uuid NOT NULL,
	"workspace_id" uuid NOT NULL,
	"requested_by" text NOT NULL,
	"channel_id" text NOT NULL,
	"source_message_id" uuid NOT NULL,
	"report_type" text NOT NULL,
	"scope_id" uuid NOT NULL,
	"period_from" timestamp with time zone NOT NULL,
	"period_to" timestamp with time zone NOT NULL,
	"filters" jsonb NOT NULL,
	"metric_version" text NOT NULL,
	"as_of" timestamp with time zone NOT NULL,
	"status" text NOT NULL,
	"run_id" uuid,
	"result_file_id" uuid,
	"row_count" bigint,
	"error_code" text,
	"created_at" timestamp with time zone DEFAULT now() NOT NULL,
	"updated_at" timestamp with time zone DEFAULT now() NOT NULL,
	CONSTRAINT "report_requests_tenant_key_uq" UNIQUE("tenant_id","id"),
	CONSTRAINT "report_requests_check_0" CHECK (status IN ('queued','running','completed','failed','cancelled'))
);
--> statement-breakpoint
ALTER TABLE "report_requests" ENABLE ROW LEVEL SECURITY;--> statement-breakpoint
CREATE TABLE "report_sources" (
	"id" uuid PRIMARY KEY DEFAULT gen_random_uuid() NOT NULL,
	"tenant_id" uuid NOT NULL,
	"report_id" uuid NOT NULL,
	"dataset" text NOT NULL,
	"query_template" text NOT NULL,
	"parameters" jsonb NOT NULL,
	"source_watermark" timestamp with time zone NOT NULL,
	"row_count" bigint NOT NULL,
	"result_hash" text NOT NULL,
	"snapshot_file_id" uuid,
	"created_at" timestamp with time zone DEFAULT now() NOT NULL,
	CONSTRAINT "report_sources_tenant_key_uq" UNIQUE("tenant_id","id"),
	CONSTRAINT "report_sources_unique_0" UNIQUE("report_id","dataset")
);
--> statement-breakpoint
ALTER TABLE "report_sources" ENABLE ROW LEVEL SECURITY;--> statement-breakpoint
CREATE TABLE "retrieval_hits" (
	"tenant_id" uuid NOT NULL,
	"retrieval_run_id" uuid NOT NULL,
	"chunk_id" uuid NOT NULL,
	"rank" integer NOT NULL,
	"similarity" numeric(9, 6) NOT NULL,
	"included" boolean NOT NULL,
	"created_at" timestamp with time zone DEFAULT now() NOT NULL,
	CONSTRAINT "retrieval_hits_tenant_id_retrieval_run_id_chunk_id_pk" PRIMARY KEY("tenant_id","retrieval_run_id","chunk_id"),
	CONSTRAINT "retrieval_hits_unique_0" UNIQUE("retrieval_run_id","rank")
);
--> statement-breakpoint
ALTER TABLE "retrieval_hits" ENABLE ROW LEVEL SECURITY;--> statement-breakpoint
CREATE TABLE "retrieval_runs" (
	"id" uuid PRIMARY KEY DEFAULT gen_random_uuid() NOT NULL,
	"tenant_id" uuid NOT NULL,
	"agent_run_id" uuid NOT NULL,
	"actor_user_id" text,
	"knowledge_base_id" uuid NOT NULL,
	"model_id" uuid NOT NULL,
	"query_text_redacted" text NOT NULL,
	"metadata_filter" jsonb NOT NULL,
	"authorized_document_ids" jsonb NOT NULL,
	"top_k" integer NOT NULL,
	"policy_version" text NOT NULL,
	"latency_ms" integer NOT NULL,
	"created_at" timestamp with time zone DEFAULT now() NOT NULL,
	"principal_id" uuid NOT NULL,
	"binding_id" uuid NOT NULL,
	CONSTRAINT "retrieval_runs_tenant_key_uq" UNIQUE("tenant_id","id")
);
--> statement-breakpoint
ALTER TABLE "retrieval_runs" ENABLE ROW LEVEL SECURITY;--> statement-breakpoint
CREATE TABLE "revoked_access" (
	"email" text PRIMARY KEY NOT NULL,
	"revoked_at" timestamp with time zone DEFAULT now() NOT NULL,
	"revoked_by" text NOT NULL
);
--> statement-breakpoint
CREATE TABLE "routine_runs" (
	"id" text PRIMARY KEY NOT NULL,
	"routine_id" text NOT NULL,
	"started_at" timestamp with time zone DEFAULT now() NOT NULL,
	"finished_at" timestamp with time zone,
	"status" "routine_run_status",
	"error" text,
	"tenant_id" uuid DEFAULT nullif(current_setting('app.tenant_id', true), '')::uuid NOT NULL,
	"workspace_id" uuid,
	"scheduled_for" timestamp with time zone NOT NULL,
	CONSTRAINT "routine_runs_tenant_key_uq" UNIQUE("tenant_id","id"),
	CONSTRAINT "routine_runs_unique_0" UNIQUE("routine_id","scheduled_for")
);
--> statement-breakpoint
ALTER TABLE "routine_runs" ENABLE ROW LEVEL SECURITY;--> statement-breakpoint
CREATE TABLE "routine_sweeps" (
	"id" text PRIMARY KEY NOT NULL,
	"swept_at" timestamp with time zone DEFAULT now() NOT NULL,
	"owner" text
);
--> statement-breakpoint
CREATE TABLE "routines" (
	"id" text PRIMARY KEY NOT NULL,
	"owner_user_id" text NOT NULL,
	"agent_id" text NOT NULL,
	"channel_id" text NOT NULL,
	"instruction" text NOT NULL,
	"cron" text NOT NULL,
	"timezone" text DEFAULT 'UTC' NOT NULL,
	"enabled" boolean DEFAULT true NOT NULL,
	"next_run_at" timestamp with time zone NOT NULL,
	"last_run_at" timestamp with time zone,
	"created_at" timestamp with time zone DEFAULT now() NOT NULL,
	"updated_at" timestamp with time zone DEFAULT now() NOT NULL,
	"tenant_id" uuid DEFAULT nullif(current_setting('app.tenant_id', true), '')::uuid NOT NULL,
	"workspace_id" uuid,
	CONSTRAINT "routines_tenant_key_uq" UNIQUE("tenant_id","id")
);
--> statement-breakpoint
ALTER TABLE "routines" ENABLE ROW LEVEL SECURITY;--> statement-breakpoint
CREATE TABLE "run_memory_access" (
	"id" uuid PRIMARY KEY DEFAULT gen_random_uuid() NOT NULL,
	"tenant_id" uuid NOT NULL,
	"run_id" uuid NOT NULL,
	"namespace_id" uuid NOT NULL,
	"access_mode" text NOT NULL,
	"authz_version" bigint NOT NULL,
	"policy_version" text NOT NULL,
	"created_at" timestamp with time zone DEFAULT now() NOT NULL,
	CONSTRAINT "run_memory_access_tenant_key_uq" UNIQUE("tenant_id","id"),
	CONSTRAINT "run_memory_access_unique_0" UNIQUE("run_id","namespace_id","access_mode"),
	CONSTRAINT "run_memory_access_check_0" CHECK (access_mode IN ('read','propose'))
);
--> statement-breakpoint
ALTER TABLE "run_memory_access" ENABLE ROW LEVEL SECURITY;--> statement-breakpoint
CREATE TABLE "runtime_backends" (
	"id" uuid PRIMARY KEY DEFAULT gen_random_uuid() NOT NULL,
	"code" text NOT NULL,
	"framework" text NOT NULL,
	"sdk_language" text NOT NULL,
	"package_version" text NOT NULL,
	"backend_kind" text NOT NULL,
	"connection_secret_ref" text NOT NULL,
	"schema_name" text NOT NULL,
	"enabled" boolean DEFAULT true NOT NULL,
	"created_at" timestamp with time zone DEFAULT now() NOT NULL,
	"updated_at" timestamp with time zone DEFAULT now() NOT NULL,
	CONSTRAINT "runtime_backends_unique_0" UNIQUE("code"),
	CONSTRAINT "runtime_backends_check_0" CHECK (framework IN ('langgraph','agentscope')),
	CONSTRAINT "runtime_backends_check_1" CHECK (sdk_language IN ('python','javascript','java')),
	CONSTRAINT "runtime_backends_check_2" CHECK (backend_kind IN ('postgres','sqlalchemy','custom'))
);
--> statement-breakpoint
CREATE TABLE "runtime_identities" (
	"id" uuid PRIMARY KEY DEFAULT gen_random_uuid() NOT NULL,
	"tenant_id" uuid NOT NULL,
	"backend_id" uuid NOT NULL,
	"principal_id" uuid NOT NULL,
	"runtime_user_key" text NOT NULL,
	"status" text NOT NULL,
	"created_at" timestamp with time zone DEFAULT now() NOT NULL,
	"updated_at" timestamp with time zone DEFAULT now() NOT NULL,
	CONSTRAINT "runtime_identities_tenant_key_uq" UNIQUE("tenant_id","id"),
	CONSTRAINT "runtime_identities_unique_0" UNIQUE("backend_id","principal_id"),
	CONSTRAINT "runtime_identities_unique_1" UNIQUE("backend_id","runtime_user_key"),
	CONSTRAINT "runtime_identities_unique_2" UNIQUE("tenant_id","id","backend_id"),
	CONSTRAINT "runtime_identities_check_0" CHECK (status IN ('active','revoked'))
);
--> statement-breakpoint
ALTER TABLE "runtime_identities" ENABLE ROW LEVEL SECURITY;--> statement-breakpoint
CREATE TABLE "runtime_memory_bindings" (
	"id" uuid PRIMARY KEY DEFAULT gen_random_uuid() NOT NULL,
	"tenant_id" uuid NOT NULL,
	"namespace_id" uuid NOT NULL,
	"backend_id" uuid NOT NULL,
	"runtime_namespace" jsonb NOT NULL,
	"status" text NOT NULL,
	"sync_generation" bigint DEFAULT 1 NOT NULL,
	"last_synced_at" timestamp with time zone,
	"created_at" timestamp with time zone DEFAULT now() NOT NULL,
	"updated_at" timestamp with time zone DEFAULT now() NOT NULL,
	CONSTRAINT "runtime_memory_bindings_tenant_key_uq" UNIQUE("tenant_id","id"),
	CONSTRAINT "runtime_memory_bindings_unique_0" UNIQUE("namespace_id","backend_id"),
	CONSTRAINT "runtime_memory_bindings_unique_1" UNIQUE("backend_id","runtime_namespace"),
	CONSTRAINT "runtime_memory_bindings_check_0" CHECK (status IN ('disabled','active','revoked'))
);
--> statement-breakpoint
ALTER TABLE "runtime_memory_bindings" ENABLE ROW LEVEL SECURITY;--> statement-breakpoint
CREATE TABLE "runtime_session_bindings" (
	"id" uuid PRIMARY KEY DEFAULT gen_random_uuid() NOT NULL,
	"tenant_id" uuid NOT NULL,
	"identity_id" uuid NOT NULL,
	"channel_id" text NOT NULL,
	"agent_id" text NOT NULL,
	"agent_version_id" uuid NOT NULL,
	"team_member_id" uuid,
	"audience_kind" text NOT NULL,
	"customer_user_id" text,
	"started_by_user_id" text,
	"runtime_session_key" text NOT NULL,
	"checkpoint_namespace" text DEFAULT '' NOT NULL,
	"status" text NOT NULL,
	"generation" integer DEFAULT 1 NOT NULL,
	"policy_version" text NOT NULL,
	"lock_version" bigint DEFAULT 0 NOT NULL,
	"lease_owner" text,
	"lease_until" timestamp with time zone,
	"last_access_at" timestamp with time zone,
	"expires_at" timestamp with time zone,
	"purged_at" timestamp with time zone,
	"created_at" timestamp with time zone DEFAULT now() NOT NULL,
	"updated_at" timestamp with time zone DEFAULT now() NOT NULL,
	"backend_id" uuid NOT NULL,
	CONSTRAINT "runtime_session_bindings_tenant_key_uq" UNIQUE("tenant_id","id"),
	CONSTRAINT "runtime_session_bindings_unique_2" UNIQUE("backend_id","runtime_session_key"),
	CONSTRAINT "runtime_session_bindings_check_0" CHECK ((audience_kind='personal' AND customer_user_id IS NOT NULL AND team_member_id IS NULL) OR (audience_kind='team' AND customer_user_id IS NULL AND team_member_id IS NOT NULL)),
	CONSTRAINT "runtime_session_bindings_check_1" CHECK (generation>0),
	CONSTRAINT "runtime_session_bindings_check_2" CHECK (audience_kind IN ('personal','team')),
	CONSTRAINT "runtime_session_bindings_check_3" CHECK (status IN ('provisioning','active','interrupted','closed','revoked','purging','purged','failed'))
);
--> statement-breakpoint
ALTER TABLE "runtime_session_bindings" ENABLE ROW LEVEL SECURITY;--> statement-breakpoint
CREATE TABLE "runtime_session_operations" (
	"id" uuid PRIMARY KEY DEFAULT gen_random_uuid() NOT NULL,
	"tenant_id" uuid NOT NULL,
	"binding_id" uuid NOT NULL,
	"actor_principal_id" uuid NOT NULL,
	"initiated_by_user_id" text,
	"operation" text NOT NULL,
	"idempotency_key" text NOT NULL,
	"expected_generation" integer NOT NULL,
	"expected_lock_version" bigint NOT NULL,
	"trigger_event_id" uuid,
	"interrupt_id" text,
	"status" text NOT NULL,
	"result_run_id" uuid,
	"failure_code" text,
	"finished_at" timestamp with time zone,
	"created_at" timestamp with time zone DEFAULT now() NOT NULL,
	"updated_at" timestamp with time zone DEFAULT now() NOT NULL,
	CONSTRAINT "runtime_session_operations_tenant_key_uq" UNIQUE("tenant_id","id"),
	CONSTRAINT "runtime_session_operations_unique_0" UNIQUE("binding_id","idempotency_key"),
	CONSTRAINT "runtime_session_operations_check_0" CHECK (operation IN ('invoke','resume','read','export','purge')),
	CONSTRAINT "runtime_session_operations_check_1" CHECK (status IN ('pending','running','succeeded','failed','cancelled'))
);
--> statement-breakpoint
ALTER TABLE "runtime_session_operations" ENABLE ROW LEVEL SECURITY;--> statement-breakpoint
CREATE TABLE "sandboxed_components" (
	"name" text NOT NULL,
	"title" text NOT NULL,
	"draft_description" text DEFAULT '' NOT NULL,
	"draft_html" text DEFAULT '' NOT NULL,
	"draft_css" text DEFAULT '' NOT NULL,
	"draft_js_functions" text DEFAULT '' NOT NULL,
	"draft_argument_schema" jsonb DEFAULT '{}'::jsonb NOT NULL,
	"published_description" text,
	"published_html" text,
	"published_css" text,
	"published_js_functions" text,
	"published_argument_schema" jsonb,
	"sample_arguments" jsonb DEFAULT '{}'::jsonb NOT NULL,
	"revision" integer DEFAULT 0 NOT NULL,
	"published" boolean DEFAULT false NOT NULL,
	"published_at" timestamp with time zone,
	"authored_by" text,
	"created_at" timestamp with time zone DEFAULT now() NOT NULL,
	"updated_at" timestamp with time zone DEFAULT now() NOT NULL,
	"tenant_id" uuid DEFAULT nullif(current_setting('app.tenant_id', true), '')::uuid NOT NULL,
	"workspace_id" uuid DEFAULT nullif(current_setting('app.workspace_id', true), '')::uuid NOT NULL,
	CONSTRAINT "sandboxed_components_tenant_id_name_pk" PRIMARY KEY("tenant_id","name")
);
--> statement-breakpoint
ALTER TABLE "sandboxed_components" ENABLE ROW LEVEL SECURITY;--> statement-breakpoint
CREATE TABLE "scoped_user_roles" (
	"id" uuid PRIMARY KEY DEFAULT gen_random_uuid() NOT NULL,
	"tenant_id" uuid NOT NULL,
	"membership_id" uuid NOT NULL,
	"scope_id" uuid NOT NULL,
	"role_code" text NOT NULL,
	"granted_by" text NOT NULL,
	"valid_from" timestamp with time zone NOT NULL,
	"valid_to" timestamp with time zone,
	"created_at" timestamp with time zone DEFAULT now() NOT NULL,
	"updated_at" timestamp with time zone DEFAULT now() NOT NULL,
	CONSTRAINT "scoped_user_roles_tenant_key_uq" UNIQUE("tenant_id","id"),
	CONSTRAINT "scoped_user_roles_unique_0" UNIQUE("membership_id","scope_id","role_code","valid_from"),
	CONSTRAINT "scoped_user_roles_check_0" CHECK (role_code IN ('management','staff','customer')),
	CONSTRAINT "scoped_user_roles_check_1" CHECK (valid_to IS NULL OR valid_to>valid_from)
);
--> statement-breakpoint
ALTER TABLE "scoped_user_roles" ENABLE ROW LEVEL SECURITY;--> statement-breakpoint
CREATE TABLE "service_categories" (
	"id" uuid PRIMARY KEY DEFAULT gen_random_uuid() NOT NULL,
	"tenant_id" uuid NOT NULL,
	"parent_id" uuid,
	"code" text NOT NULL,
	"name" text NOT NULL,
	"enabled" boolean DEFAULT true NOT NULL,
	"created_at" timestamp with time zone DEFAULT now() NOT NULL,
	"updated_at" timestamp with time zone DEFAULT now() NOT NULL,
	CONSTRAINT "service_categories_tenant_key_uq" UNIQUE("tenant_id","id"),
	CONSTRAINT "service_categories_unique_0" UNIQUE("tenant_id","code")
);
--> statement-breakpoint
ALTER TABLE "service_categories" ENABLE ROW LEVEL SECURITY;--> statement-breakpoint
CREATE TABLE "service_interruptions" (
	"id" uuid PRIMARY KEY DEFAULT gen_random_uuid() NOT NULL,
	"tenant_id" uuid NOT NULL,
	"work_order_id" uuid NOT NULL,
	"approval_id" uuid NOT NULL,
	"utility" text NOT NULL,
	"reason" text NOT NULL,
	"planned_start" timestamp with time zone NOT NULL,
	"planned_end" timestamp with time zone NOT NULL,
	"actual_start" timestamp with time zone,
	"actual_end" timestamp with time zone,
	"status" text NOT NULL,
	"operated_by" text,
	"created_at" timestamp with time zone DEFAULT now() NOT NULL,
	"updated_at" timestamp with time zone DEFAULT now() NOT NULL,
	CONSTRAINT "service_interruptions_tenant_key_uq" UNIQUE("tenant_id","id"),
	CONSTRAINT "service_interruptions_check_0" CHECK (utility IN ('water','power')),
	CONSTRAINT "service_interruptions_check_1" CHECK (status IN ('proposed','approved','notified','active','restored','cancelled'))
);
--> statement-breakpoint
ALTER TABLE "service_interruptions" ENABLE ROW LEVEL SECURITY;--> statement-breakpoint
CREATE TABLE "sessions" (
	"id" text PRIMARY KEY NOT NULL,
	"user_id" text NOT NULL,
	"token" text NOT NULL,
	"expires_at" timestamp with time zone NOT NULL,
	"ip_address" text,
	"user_agent" text,
	"created_at" timestamp with time zone DEFAULT now() NOT NULL,
	"updated_at" timestamp with time zone DEFAULT now() NOT NULL,
	CONSTRAINT "sessions_unique_0" UNIQUE("token")
);
--> statement-breakpoint
CREATE TABLE "sites" (
	"id" uuid PRIMARY KEY DEFAULT gen_random_uuid() NOT NULL,
	"tenant_id" uuid NOT NULL,
	"domain_id" uuid NOT NULL,
	"code" text NOT NULL,
	"name" text NOT NULL,
	"address" text NOT NULL,
	"timezone" text DEFAULT 'Asia/Ho_Chi_Minh' NOT NULL,
	"status" text NOT NULL,
	"created_at" timestamp with time zone DEFAULT now() NOT NULL,
	"updated_at" timestamp with time zone DEFAULT now() NOT NULL,
	CONSTRAINT "sites_tenant_key_uq" UNIQUE("tenant_id","id"),
	CONSTRAINT "sites_unique_0" UNIQUE("domain_id","code")
);
--> statement-breakpoint
ALTER TABLE "sites" ENABLE ROW LEVEL SECURITY;--> statement-breakpoint
CREATE TABLE "skill_tools" (
	"skill_id" text NOT NULL,
	"ref" text NOT NULL,
	"declared_by" text,
	"created_at" timestamp with time zone DEFAULT now() NOT NULL,
	"tenant_id" uuid DEFAULT nullif(current_setting('app.tenant_id', true), '')::uuid NOT NULL,
	CONSTRAINT "skill_tools_tenant_id_skill_id_ref_pk" PRIMARY KEY("tenant_id","skill_id","ref")
);
--> statement-breakpoint
ALTER TABLE "skill_tools" ENABLE ROW LEVEL SECURITY;--> statement-breakpoint
CREATE TABLE "skills" (
	"id" text PRIMARY KEY NOT NULL,
	"owner_user_id" text,
	"slug" text NOT NULL,
	"title" text NOT NULL,
	"summary" text NOT NULL,
	"instructions" text NOT NULL,
	"origin" text DEFAULT 'yours' NOT NULL,
	"installed_by" text,
	"created_at" timestamp with time zone DEFAULT now() NOT NULL,
	"updated_at" timestamp with time zone DEFAULT now() NOT NULL,
	"tenant_id" uuid DEFAULT nullif(current_setting('app.tenant_id', true), '')::uuid NOT NULL,
	"workspace_id" uuid,
	CONSTRAINT "skills_tenant_key_uq" UNIQUE("tenant_id","id")
);
--> statement-breakpoint
ALTER TABLE "skills" ENABLE ROW LEVEL SECURITY;--> statement-breakpoint
CREATE TABLE "sla_policies" (
	"id" uuid PRIMARY KEY DEFAULT gen_random_uuid() NOT NULL,
	"tenant_id" uuid NOT NULL,
	"management_unit_id" uuid NOT NULL,
	"category_id" uuid NOT NULL,
	"priority" text NOT NULL,
	"response_minutes" integer NOT NULL,
	"resolution_minutes" integer NOT NULL,
	"effective_from" timestamp with time zone NOT NULL,
	"effective_to" timestamp with time zone,
	"created_at" timestamp with time zone DEFAULT now() NOT NULL,
	"updated_at" timestamp with time zone DEFAULT now() NOT NULL,
	"domain_id" uuid NOT NULL,
	"request_kind" text NOT NULL,
	"version_no" integer NOT NULL,
	"clock_basis" text DEFAULT 'elapsed_24x7' NOT NULL,
	CONSTRAINT "sla_policies_tenant_key_uq" UNIQUE("tenant_id","id"),
	CONSTRAINT "sla_policies_unique_0" UNIQUE("tenant_id","domain_id","management_unit_id","category_id","request_kind","priority","version_no"),
	CONSTRAINT "sla_policies_check_0" CHECK (response_minutes>0 AND resolution_minutes>0),
	CONSTRAINT "sla_policies_check_1" CHECK (effective_to IS NULL OR effective_to>effective_from),
	CONSTRAINT "sla_policies_check_2" CHECK (clock_basis='elapsed_24x7'),
	CONSTRAINT "sla_policies_check_3" CHECK (request_kind IN ('incident','service_request'))
);
--> statement-breakpoint
ALTER TABLE "sla_policies" ENABLE ROW LEVEL SECURITY;--> statement-breakpoint
CREATE TABLE "sso_providers" (
	"id" text PRIMARY KEY NOT NULL,
	"issuer" text NOT NULL,
	"oidc_config" text,
	"saml_config" text,
	"user_id" text,
	"provider_id" text NOT NULL,
	"organization_id" text,
	"domain" text NOT NULL
);
--> statement-breakpoint
CREATE TABLE "staff_profiles" (
	"id" uuid PRIMARY KEY DEFAULT gen_random_uuid() NOT NULL,
	"tenant_id" uuid NOT NULL,
	"user_id" text NOT NULL,
	"management_unit_id" uuid NOT NULL,
	"employee_code" text NOT NULL,
	"availability" text NOT NULL,
	"max_concurrent_jobs" integer DEFAULT 1 NOT NULL,
	"active" boolean DEFAULT true NOT NULL,
	"created_at" timestamp with time zone DEFAULT now() NOT NULL,
	"updated_at" timestamp with time zone DEFAULT now() NOT NULL,
	CONSTRAINT "staff_profiles_tenant_key_uq" UNIQUE("tenant_id","id"),
	CONSTRAINT "staff_profiles_unique_0" UNIQUE("tenant_id","user_id"),
	CONSTRAINT "staff_profiles_unique_1" UNIQUE("tenant_id","employee_code"),
	CONSTRAINT "staff_profiles_check_0" CHECK (availability IN ('available','busy','offline','on_leave'))
);
--> statement-breakpoint
ALTER TABLE "staff_profiles" ENABLE ROW LEVEL SECURITY;--> statement-breakpoint
CREATE TABLE "staff_shifts" (
	"id" uuid PRIMARY KEY DEFAULT gen_random_uuid() NOT NULL,
	"tenant_id" uuid NOT NULL,
	"staff_id" uuid NOT NULL,
	"starts_at" timestamp with time zone NOT NULL,
	"ends_at" timestamp with time zone NOT NULL,
	"status" text NOT NULL,
	"created_at" timestamp with time zone DEFAULT now() NOT NULL,
	"updated_at" timestamp with time zone DEFAULT now() NOT NULL,
	CONSTRAINT "staff_shifts_tenant_key_uq" UNIQUE("tenant_id","id"),
	CONSTRAINT "staff_shifts_check_0" CHECK (status IN ('scheduled','available','leave','cancelled'))
);
--> statement-breakpoint
ALTER TABLE "staff_shifts" ENABLE ROW LEVEL SECURITY;--> statement-breakpoint
CREATE TABLE "staff_specialties" (
	"tenant_id" uuid NOT NULL,
	"staff_id" uuid NOT NULL,
	"category_id" uuid NOT NULL,
	"proficiency" text NOT NULL,
	"active" boolean DEFAULT true NOT NULL,
	"created_at" timestamp with time zone DEFAULT now() NOT NULL,
	CONSTRAINT "staff_specialties_tenant_id_staff_id_category_id_pk" PRIMARY KEY("tenant_id","staff_id","category_id")
);
--> statement-breakpoint
ALTER TABLE "staff_specialties" ENABLE ROW LEVEL SECURITY;--> statement-breakpoint
CREATE TABLE "storage_event_receipts" (
	"id" uuid PRIMARY KEY DEFAULT gen_random_uuid() NOT NULL,
	"tenant_id" uuid NOT NULL,
	"location_id" uuid NOT NULL,
	"provider_event_key" text NOT NULL,
	"event_type" text NOT NULL,
	"object_key" text NOT NULL,
	"version_id" text,
	"sequencer" text,
	"event_time" timestamp with time zone,
	"received_at" timestamp with time zone NOT NULL,
	"payload_hash" text NOT NULL,
	"status" text NOT NULL,
	"processed_at" timestamp with time zone,
	"created_at" timestamp with time zone DEFAULT now() NOT NULL,
	"updated_at" timestamp with time zone DEFAULT now() NOT NULL,
	CONSTRAINT "storage_event_receipts_tenant_key_uq" UNIQUE("tenant_id","id"),
	CONSTRAINT "storage_event_receipts_unique_0" UNIQUE("location_id","provider_event_key"),
	CONSTRAINT "storage_event_receipts_check_0" CHECK (status IN ('pending','done','ignored','failed'))
);
--> statement-breakpoint
ALTER TABLE "storage_event_receipts" ENABLE ROW LEVEL SECURITY;--> statement-breakpoint
CREATE TABLE "storage_locations" (
	"id" uuid PRIMARY KEY DEFAULT gen_random_uuid() NOT NULL,
	"tenant_id" uuid NOT NULL,
	"provider" text NOT NULL,
	"endpoint_ref" text NOT NULL,
	"region" text,
	"bucket_name" text NOT NULL,
	"tenant_prefix" text NOT NULL,
	"credential_secret_ref" text NOT NULL,
	"versioning_required" boolean DEFAULT true NOT NULL,
	"encryption_mode" text NOT NULL,
	"kms_key_ref" text,
	"purpose" text NOT NULL,
	"status" text NOT NULL,
	"created_at" timestamp with time zone DEFAULT now() NOT NULL,
	"updated_at" timestamp with time zone DEFAULT now() NOT NULL,
	CONSTRAINT "storage_locations_tenant_key_uq" UNIQUE("tenant_id","id"),
	CONSTRAINT "storage_locations_unique_0" UNIQUE("endpoint_ref","bucket_name","tenant_prefix"),
	CONSTRAINT "storage_locations_check_0" CHECK (purpose IN ('staging','evidence','derived','documents','reports')),
	CONSTRAINT "storage_locations_check_1" CHECK (status IN ('active','readonly','disabled'))
);
--> statement-breakpoint
ALTER TABLE "storage_locations" ENABLE ROW LEVEL SECURITY;--> statement-breakpoint
CREATE TABLE "task_dependencies" (
	"tenant_id" uuid NOT NULL,
	"task_id" uuid NOT NULL,
	"depends_on_id" uuid NOT NULL,
	"created_at" timestamp with time zone DEFAULT now() NOT NULL,
	CONSTRAINT "task_dependencies_tenant_id_task_id_depends_on_id_pk" PRIMARY KEY("tenant_id","task_id","depends_on_id")
);
--> statement-breakpoint
ALTER TABLE "task_dependencies" ENABLE ROW LEVEL SECURITY;--> statement-breakpoint
CREATE TABLE "team_mailbox" (
	"id" uuid PRIMARY KEY DEFAULT gen_random_uuid() NOT NULL,
	"tenant_id" uuid NOT NULL,
	"team_id" uuid NOT NULL,
	"sender_member_id" uuid NOT NULL,
	"recipient_member_id" uuid,
	"task_id" uuid,
	"message_kind" text NOT NULL,
	"content" jsonb NOT NULL,
	"correlation_id" uuid NOT NULL,
	"idempotency_key" text NOT NULL,
	"created_at" timestamp with time zone DEFAULT now() NOT NULL,
	CONSTRAINT "team_mailbox_tenant_key_uq" UNIQUE("tenant_id","id"),
	CONSTRAINT "team_mailbox_unique_0" UNIQUE("team_id","idempotency_key"),
	CONSTRAINT "team_mailbox_check_0" CHECK (message_kind IN ('direct','broadcast','result'))
);
--> statement-breakpoint
ALTER TABLE "team_mailbox" ENABLE ROW LEVEL SECURITY;--> statement-breakpoint
CREATE TABLE "team_members" (
	"id" uuid PRIMARY KEY DEFAULT gen_random_uuid() NOT NULL,
	"tenant_id" uuid NOT NULL,
	"team_id" uuid NOT NULL,
	"agent_id" text NOT NULL,
	"version_id" uuid NOT NULL,
	"member_kind" text NOT NULL,
	"status" text NOT NULL,
	"created_at" timestamp with time zone DEFAULT now() NOT NULL,
	"updated_at" timestamp with time zone DEFAULT now() NOT NULL,
	"binding_id" uuid,
	CONSTRAINT "team_members_tenant_key_uq" UNIQUE("tenant_id","id"),
	CONSTRAINT "team_members_unique_0" UNIQUE("team_id","agent_id"),
	CONSTRAINT "team_members_unique_1" UNIQUE("binding_id"),
	CONSTRAINT "team_members_check_0" CHECK (status IN ('provisioning','active','closed','failed'))
);
--> statement-breakpoint
ALTER TABLE "team_members" ENABLE ROW LEVEL SECURITY;--> statement-breakpoint
CREATE TABLE "team_tasks" (
	"id" uuid PRIMARY KEY DEFAULT gen_random_uuid() NOT NULL,
	"tenant_id" uuid NOT NULL,
	"team_id" uuid NOT NULL,
	"parent_task_id" uuid,
	"ticket_id" uuid,
	"title" text NOT NULL,
	"description" text NOT NULL,
	"status" text NOT NULL,
	"priority" integer DEFAULT 0 NOT NULL,
	"assigned_member_id" uuid,
	"result" jsonb,
	"version" bigint DEFAULT 0 NOT NULL,
	"lease_owner" text,
	"lease_until" timestamp with time zone,
	"idempotency_key" text NOT NULL,
	"created_at" timestamp with time zone DEFAULT now() NOT NULL,
	"updated_at" timestamp with time zone DEFAULT now() NOT NULL,
	CONSTRAINT "team_tasks_tenant_key_uq" UNIQUE("tenant_id","id"),
	CONSTRAINT "team_tasks_unique_0" UNIQUE("team_id","idempotency_key"),
	CONSTRAINT "team_tasks_check_0" CHECK (status IN ('pending','ready','running','blocked','done','failed','cancelled'))
);
--> statement-breakpoint
ALTER TABLE "team_tasks" ENABLE ROW LEVEL SECURITY;--> statement-breakpoint
CREATE TABLE "tenant_memberships" (
	"id" uuid PRIMARY KEY DEFAULT gen_random_uuid() NOT NULL,
	"tenant_id" uuid NOT NULL,
	"user_id" text NOT NULL,
	"status" text NOT NULL,
	"joined_at" timestamp with time zone,
	"ended_at" timestamp with time zone,
	"created_at" timestamp with time zone DEFAULT now() NOT NULL,
	"updated_at" timestamp with time zone DEFAULT now() NOT NULL,
	CONSTRAINT "tenant_memberships_tenant_key_uq" UNIQUE("tenant_id","id"),
	CONSTRAINT "tenant_memberships_unique_0" UNIQUE("tenant_id","user_id"),
	CONSTRAINT "tenant_memberships_check_0" CHECK (status IN ('pending','active','suspended','ended'))
);
--> statement-breakpoint
ALTER TABLE "tenant_memberships" ENABLE ROW LEVEL SECURITY;--> statement-breakpoint
CREATE TABLE "tenants" (
	"id" uuid PRIMARY KEY DEFAULT gen_random_uuid() NOT NULL,
	"code" text NOT NULL,
	"name" text NOT NULL,
	"status" text NOT NULL,
	"timezone" text DEFAULT 'Asia/Ho_Chi_Minh' NOT NULL,
	"retention_policy" jsonb DEFAULT '{}'::jsonb NOT NULL,
	"created_at" timestamp with time zone DEFAULT now() NOT NULL,
	"updated_at" timestamp with time zone DEFAULT now() NOT NULL,
	CONSTRAINT "tenants_unique_0" UNIQUE("code"),
	CONSTRAINT "tenants_check_0" CHECK (status IN ('active','suspended','closed'))
);
--> statement-breakpoint
CREATE TABLE "ticket_assessment_evidence" (
	"id" uuid PRIMARY KEY DEFAULT gen_random_uuid() NOT NULL,
	"tenant_id" uuid NOT NULL,
	"assessment_id" uuid NOT NULL,
	"fact_key" text NOT NULL,
	"message_id" uuid,
	"event_id" uuid,
	"evidence_item_id" uuid,
	"object_id" uuid,
	"source_hash" text NOT NULL,
	"excerpt_redacted" text,
	"created_at" timestamp with time zone DEFAULT now() NOT NULL,
	CONSTRAINT "ticket_assessment_evidence_tenant_key_uq" UNIQUE("tenant_id","id"),
	CONSTRAINT "ticket_assessment_evidence_check_0" CHECK (num_nonnulls(message_id,event_id,evidence_item_id)=1),
	CONSTRAINT "ticket_assessment_evidence_check_1" CHECK ((evidence_item_id IS NULL)=(object_id IS NULL))
);
--> statement-breakpoint
ALTER TABLE "ticket_assessment_evidence" ENABLE ROW LEVEL SECURITY;--> statement-breakpoint
CREATE TABLE "ticket_assessments" (
	"id" uuid PRIMARY KEY DEFAULT gen_random_uuid() NOT NULL,
	"tenant_id" uuid NOT NULL,
	"ticket_id" uuid NOT NULL,
	"ticket_generation" integer NOT NULL,
	"basis_ticket_version" bigint NOT NULL,
	"basis_decision_id" uuid,
	"stage" text NOT NULL,
	"assessor_kind" text NOT NULL,
	"assessor_user_id" text,
	"source_run_id" uuid,
	"input_schema_version" text NOT NULL,
	"facts" jsonb NOT NULL,
	"proposed_severity" text NOT NULL,
	"proposed_urgency" text NOT NULL,
	"proposed_priority" text,
	"confidence" numeric(5, 4),
	"rationale" text NOT NULL,
	"observed_at" timestamp with time zone NOT NULL,
	"submitted_at" timestamp with time zone NOT NULL,
	"idempotency_key" text NOT NULL,
	"supersedes_assessment_id" uuid,
	"created_at" timestamp with time zone DEFAULT now() NOT NULL,
	CONSTRAINT "ticket_assessments_tenant_key_uq" UNIQUE("tenant_id","id"),
	CONSTRAINT "ticket_assessments_unique_0" UNIQUE("ticket_id","idempotency_key"),
	CONSTRAINT "ticket_assessments_check_0" CHECK (ticket_generation>=0 AND basis_ticket_version>=0),
	CONSTRAINT "ticket_assessments_check_1" CHECK (confidence IS NULL OR confidence BETWEEN 0 AND 1),
	CONSTRAINT "ticket_assessments_check_2" CHECK ((assessor_kind='agent' AND source_run_id IS NOT NULL AND assessor_user_id IS NULL) OR (assessor_kind='human' AND assessor_user_id IS NOT NULL AND source_run_id IS NULL) OR (assessor_kind='system' AND assessor_user_id IS NULL AND source_run_id IS NULL)),
	CONSTRAINT "ticket_assessments_check_3" CHECK (stage IN ('intake','specialist','onsite','reassessment')),
	CONSTRAINT "ticket_assessments_check_4" CHECK (assessor_kind IN ('agent','human','system')),
	CONSTRAINT "ticket_assessments_check_5" CHECK (proposed_severity IN ('unknown','minor','moderate','major','critical','not_applicable')),
	CONSTRAINT "ticket_assessments_check_6" CHECK (proposed_urgency IN ('unknown','routine','soon','immediate'))
);
--> statement-breakpoint
ALTER TABLE "ticket_assessments" ENABLE ROW LEVEL SECURITY;--> statement-breakpoint
CREATE TABLE "ticket_escalations" (
	"id" uuid PRIMARY KEY DEFAULT gen_random_uuid() NOT NULL,
	"tenant_id" uuid NOT NULL,
	"ticket_id" uuid NOT NULL,
	"ticket_generation" integer NOT NULL,
	"decision_id" uuid,
	"sla_cycle_id" uuid,
	"review_id" uuid,
	"work_order_id" uuid,
	"required_scope_id" uuid NOT NULL,
	"reason_code" text NOT NULL,
	"dedupe_key" text NOT NULL,
	"status" text NOT NULL,
	"detected_at" timestamp with time zone NOT NULL,
	"next_notify_at" timestamp with time zone NOT NULL,
	"acknowledged_by" text,
	"acknowledged_at" timestamp with time zone,
	"resolved_by" text,
	"resolved_at" timestamp with time zone,
	"resolution_note" text,
	"assessment_id" uuid,
	"created_at" timestamp with time zone DEFAULT now() NOT NULL,
	"updated_at" timestamp with time zone DEFAULT now() NOT NULL,
	CONSTRAINT "ticket_escalations_tenant_key_uq" UNIQUE("tenant_id","id"),
	CONSTRAINT "ticket_escalations_unique_0" UNIQUE("ticket_id","dedupe_key"),
	CONSTRAINT "ticket_escalations_check_0" CHECK (reason_code IN ('emergency','response_breach','resolution_breach','review_overdue','risk_signal_pending','queue_wait','no_capacity','policy_missing')),
	CONSTRAINT "ticket_escalations_check_1" CHECK (status IN ('open','acknowledged','resolved','cancelled'))
);
--> statement-breakpoint
ALTER TABLE "ticket_escalations" ENABLE ROW LEVEL SECURITY;--> statement-breakpoint
CREATE TABLE "ticket_events" (
	"id" uuid PRIMARY KEY DEFAULT gen_random_uuid() NOT NULL,
	"tenant_id" uuid NOT NULL,
	"ticket_id" uuid NOT NULL,
	"seq" bigint NOT NULL,
	"event_type" text NOT NULL,
	"schema_version" integer DEFAULT 1 NOT NULL,
	"from_status" text,
	"to_status" text,
	"actor_kind" text NOT NULL,
	"actor_user_id" text,
	"actor_agent_id" text,
	"idempotency_key" text NOT NULL,
	"correlation_id" uuid NOT NULL,
	"causation_event_id" uuid,
	"payload" jsonb NOT NULL,
	"occurred_at" timestamp with time zone NOT NULL,
	"created_at" timestamp with time zone DEFAULT now() NOT NULL,
	CONSTRAINT "ticket_events_tenant_key_uq" UNIQUE("tenant_id","id"),
	CONSTRAINT "ticket_events_unique_0" UNIQUE("ticket_id","seq"),
	CONSTRAINT "ticket_events_unique_1" UNIQUE("ticket_id","idempotency_key")
);
--> statement-breakpoint
ALTER TABLE "ticket_events" ENABLE ROW LEVEL SECURITY;--> statement-breakpoint
CREATE TABLE "ticket_files" (
	"tenant_id" uuid NOT NULL,
	"ticket_id" uuid NOT NULL,
	"file_id" uuid NOT NULL,
	"event_id" uuid,
	"purpose" text NOT NULL,
	"uploaded_by" text NOT NULL,
	"created_at" timestamp with time zone DEFAULT now() NOT NULL,
	"evidence_id" uuid,
	CONSTRAINT "ticket_files_tenant_id_ticket_id_file_id_pk" PRIMARY KEY("tenant_id","ticket_id","file_id"),
	CONSTRAINT "ticket_files_check_0" CHECK (purpose IN ('issue','before','after','other'))
);
--> statement-breakpoint
ALTER TABLE "ticket_files" ENABLE ROW LEVEL SECURITY;--> statement-breakpoint
CREATE TABLE "ticket_reviews" (
	"id" uuid PRIMARY KEY DEFAULT gen_random_uuid() NOT NULL,
	"tenant_id" uuid NOT NULL,
	"ticket_id" uuid NOT NULL,
	"assignment_id" uuid NOT NULL,
	"reviewer_user_id" text NOT NULL,
	"staff_id" uuid NOT NULL,
	"score" smallint NOT NULL,
	"comment" text,
	"submitted_at" timestamp with time zone NOT NULL,
	"created_at" timestamp with time zone DEFAULT now() NOT NULL,
	"updated_at" timestamp with time zone DEFAULT now() NOT NULL,
	CONSTRAINT "ticket_reviews_tenant_key_uq" UNIQUE("tenant_id","id"),
	CONSTRAINT "ticket_reviews_unique_0" UNIQUE("ticket_id","assignment_id","reviewer_user_id"),
	CONSTRAINT "ticket_reviews_check_0" CHECK (score BETWEEN 1 AND 5)
);
--> statement-breakpoint
ALTER TABLE "ticket_reviews" ENABLE ROW LEVEL SECURITY;--> statement-breakpoint
CREATE TABLE "ticket_routing_history" (
	"id" uuid PRIMARY KEY DEFAULT gen_random_uuid() NOT NULL,
	"tenant_id" uuid NOT NULL,
	"ticket_id" uuid NOT NULL,
	"from_management_id" uuid,
	"to_management_id" uuid NOT NULL,
	"team_id" uuid,
	"status" text NOT NULL,
	"reason" text NOT NULL,
	"ack_event_id" uuid,
	"requested_at" timestamp with time zone NOT NULL,
	"acknowledged_at" timestamp with time zone,
	"created_at" timestamp with time zone DEFAULT now() NOT NULL,
	CONSTRAINT "ticket_routing_history_tenant_key_uq" UNIQUE("tenant_id","id"),
	CONSTRAINT "ticket_routing_history_check_0" CHECK (status IN ('requested','accepted','rejected','timeout'))
);
--> statement-breakpoint
ALTER TABLE "ticket_routing_history" ENABLE ROW LEVEL SECURITY;--> statement-breakpoint
CREATE TABLE "ticket_sla_adjustments" (
	"id" uuid PRIMARY KEY DEFAULT gen_random_uuid() NOT NULL,
	"tenant_id" uuid NOT NULL,
	"cycle_id" uuid NOT NULL,
	"decision_id" uuid NOT NULL,
	"target_policy_id" uuid NOT NULL,
	"adjustment_kind" text NOT NULL,
	"old_response_due_at" timestamp with time zone NOT NULL,
	"new_response_due_at" timestamp with time zone NOT NULL,
	"old_resolution_due_at" timestamp with time zone NOT NULL,
	"new_resolution_due_at" timestamp with time zone NOT NULL,
	"authorized_by" text,
	"reason" text NOT NULL,
	"idempotency_key" text NOT NULL,
	"created_at" timestamp with time zone DEFAULT now() NOT NULL,
	CONSTRAINT "ticket_sla_adjustments_tenant_key_uq" UNIQUE("tenant_id","id"),
	CONSTRAINT "ticket_sla_adjustments_unique_0" UNIQUE("cycle_id","idempotency_key"),
	CONSTRAINT "ticket_sla_adjustments_unique_1" UNIQUE("cycle_id","decision_id"),
	CONSTRAINT "ticket_sla_adjustments_check_0" CHECK (adjustment_kind<>'exception_extend' OR authorized_by IS NOT NULL),
	CONSTRAINT "ticket_sla_adjustments_check_1" CHECK (adjustment_kind IN ('tighten','keep','exception_extend'))
);
--> statement-breakpoint
ALTER TABLE "ticket_sla_adjustments" ENABLE ROW LEVEL SECURITY;--> statement-breakpoint
CREATE TABLE "ticket_sla_cycles" (
	"id" uuid PRIMARY KEY DEFAULT gen_random_uuid() NOT NULL,
	"tenant_id" uuid NOT NULL,
	"ticket_id" uuid NOT NULL,
	"ticket_generation" integer NOT NULL,
	"initial_policy_id" uuid NOT NULL,
	"initial_decision_id" uuid NOT NULL,
	"started_at" timestamp with time zone NOT NULL,
	"response_minutes_snapshot" integer NOT NULL,
	"resolution_minutes_snapshot" integer NOT NULL,
	"initial_response_due_at" timestamp with time zone NOT NULL,
	"initial_resolution_due_at" timestamp with time zone NOT NULL,
	"current_response_due_at" timestamp with time zone NOT NULL,
	"current_resolution_due_at" timestamp with time zone NOT NULL,
	"responded_at" timestamp with time zone,
	"resolved_at" timestamp with time zone,
	"response_breached_at" timestamp with time zone,
	"resolution_breached_at" timestamp with time zone,
	"status" text NOT NULL,
	"version" bigint DEFAULT 0 NOT NULL,
	"created_at" timestamp with time zone DEFAULT now() NOT NULL,
	"updated_at" timestamp with time zone DEFAULT now() NOT NULL,
	CONSTRAINT "ticket_sla_cycles_tenant_key_uq" UNIQUE("tenant_id","id"),
	CONSTRAINT "ticket_sla_cycles_unique_0" UNIQUE("ticket_id","ticket_generation"),
	CONSTRAINT "ticket_sla_cycles_check_0" CHECK (response_minutes_snapshot>0 AND resolution_minutes_snapshot>0),
	CONSTRAINT "ticket_sla_cycles_check_1" CHECK (ticket_generation>=0),
	CONSTRAINT "ticket_sla_cycles_check_2" CHECK (status IN ('active','resolved','cancelled'))
);
--> statement-breakpoint
ALTER TABLE "ticket_sla_cycles" ENABLE ROW LEVEL SECURITY;--> statement-breakpoint
CREATE TABLE "ticket_triage_decisions" (
	"id" uuid PRIMARY KEY DEFAULT gen_random_uuid() NOT NULL,
	"tenant_id" uuid NOT NULL,
	"ticket_id" uuid NOT NULL,
	"ticket_generation" integer NOT NULL,
	"decision_seq" integer NOT NULL,
	"assessment_id" uuid NOT NULL,
	"policy_binding_id" uuid NOT NULL,
	"policy_version_id" uuid NOT NULL,
	"matched_rule_id" uuid,
	"previous_applied_id" uuid,
	"review_id" uuid,
	"outcome" text NOT NULL,
	"decision_mode" text NOT NULL,
	"severity" text NOT NULL,
	"priority" text NOT NULL,
	"is_emergency" boolean NOT NULL,
	"evaluation_trace" jsonb NOT NULL,
	"reason" text NOT NULL,
	"basis_ticket_version" bigint NOT NULL,
	"applied_ticket_version" bigint,
	"decided_at" timestamp with time zone NOT NULL,
	"approved_by" text,
	"idempotency_key" text NOT NULL,
	"created_at" timestamp with time zone DEFAULT now() NOT NULL,
	CONSTRAINT "ticket_triage_decisions_tenant_key_uq" UNIQUE("tenant_id","id"),
	CONSTRAINT "ticket_triage_decisions_unique_0" UNIQUE("ticket_id","decision_seq"),
	CONSTRAINT "ticket_triage_decisions_unique_1" UNIQUE("ticket_id","idempotency_key"),
	CONSTRAINT "ticket_triage_decisions_check_0" CHECK (ticket_generation>=0 AND decision_seq>0),
	CONSTRAINT "ticket_triage_decisions_check_1" CHECK (NOT is_emergency OR priority='critical'),
	CONSTRAINT "ticket_triage_decisions_check_2" CHECK ((outcome='applied')=(applied_ticket_version IS NOT NULL)),
	CONSTRAINT "ticket_triage_decisions_check_3" CHECK ((decision_mode IN ('human_confirmed','human_override') AND approved_by IS NOT NULL AND review_id IS NOT NULL) OR (decision_mode IN ('automatic','provisional') AND approved_by IS NULL)),
	CONSTRAINT "ticket_triage_decisions_check_4" CHECK (outcome IN ('applied','review_required','rejected','stale')),
	CONSTRAINT "ticket_triage_decisions_check_5" CHECK (decision_mode IN ('automatic','provisional','human_confirmed','human_override')),
	CONSTRAINT "ticket_triage_decisions_check_6" CHECK (severity IN ('unknown','minor','moderate','major','critical','not_applicable')),
	CONSTRAINT "ticket_triage_decisions_check_7" CHECK (priority IN ('low','normal','high','critical'))
);
--> statement-breakpoint
ALTER TABLE "ticket_triage_decisions" ENABLE ROW LEVEL SECURITY;--> statement-breakpoint
CREATE TABLE "ticket_triage_reviews" (
	"id" uuid PRIMARY KEY DEFAULT gen_random_uuid() NOT NULL,
	"tenant_id" uuid NOT NULL,
	"ticket_id" uuid NOT NULL,
	"ticket_generation" integer NOT NULL,
	"assessment_id" uuid NOT NULL,
	"pending_decision_id" uuid NOT NULL,
	"required_scope_id" uuid NOT NULL,
	"reason_code" text NOT NULL,
	"status" text NOT NULL,
	"due_at" timestamp with time zone NOT NULL,
	"claimed_by" text,
	"claim_until" timestamp with time zone,
	"version" bigint DEFAULT 0 NOT NULL,
	"decided_by" text,
	"decided_at" timestamp with time zone,
	"decision_note" text,
	"result_decision_id" uuid,
	"created_at" timestamp with time zone DEFAULT now() NOT NULL,
	"updated_at" timestamp with time zone DEFAULT now() NOT NULL,
	CONSTRAINT "ticket_triage_reviews_tenant_key_uq" UNIQUE("tenant_id","id"),
	CONSTRAINT "ticket_triage_reviews_unique_0" UNIQUE("pending_decision_id"),
	CONSTRAINT "ticket_triage_reviews_check_0" CHECK (reason_code IN ('unknown_facts','conflict','downgrade','emergency_override','overdue_review')),
	CONSTRAINT "ticket_triage_reviews_check_1" CHECK (status IN ('pending','claimed','approved','rejected','superseded','expired'))
);
--> statement-breakpoint
ALTER TABLE "ticket_triage_reviews" ENABLE ROW LEVEL SECURITY;--> statement-breakpoint
CREATE TABLE "tickets" (
	"id" uuid PRIMARY KEY DEFAULT gen_random_uuid() NOT NULL,
	"tenant_id" uuid NOT NULL,
	"code" text NOT NULL,
	"requester_user_id" text NOT NULL,
	"channel_id" text NOT NULL,
	"unit_id" uuid,
	"site_id" uuid,
	"zone_id" uuid,
	"building_id" uuid,
	"management_unit_id" uuid,
	"coverage_id" uuid,
	"category_id" uuid,
	"incident_type_id" uuid,
	"title" text NOT NULL,
	"description" text NOT NULL,
	"priority" text,
	"status" text NOT NULL,
	"resolution_mode" text,
	"contact_name" text NOT NULL,
	"contact_phone" text NOT NULL,
	"address_snapshot" jsonb NOT NULL,
	"assigned_team_id" uuid,
	"sla_policy_id" uuid,
	"response_due_at" timestamp with time zone,
	"resolution_due_at" timestamp with time zone,
	"first_response_at" timestamp with time zone,
	"resolved_at" timestamp with time zone,
	"closed_at" timestamp with time zone,
	"version" bigint DEFAULT 0 NOT NULL,
	"last_event_seq" bigint DEFAULT 0 NOT NULL,
	"reopen_count" integer DEFAULT 0 NOT NULL,
	"created_at" timestamp with time zone DEFAULT now() NOT NULL,
	"updated_at" timestamp with time zone DEFAULT now() NOT NULL,
	"domain_id" uuid NOT NULL,
	"request_kind" text NOT NULL,
	"severity" text DEFAULT 'unknown' NOT NULL,
	"triage_status" text DEFAULT 'pending' NOT NULL,
	"current_triage_decision_id" uuid,
	"is_emergency" boolean DEFAULT false NOT NULL,
	"active_sla_cycle_id" uuid,
	CONSTRAINT "tickets_tenant_key_uq" UNIQUE("tenant_id","id"),
	CONSTRAINT "tickets_unique_0" UNIQUE("tenant_id","code"),
	CONSTRAINT "tickets_unique_1" UNIQUE("channel_id"),
	CONSTRAINT "tickets_check_0" CHECK (priority IS NULL OR priority IN ('low','normal','high','critical')),
	CONSTRAINT "tickets_check_1" CHECK (severity IN ('unknown','minor','moderate','major','critical','not_applicable')),
	CONSTRAINT "tickets_check_2" CHECK (request_kind IN ('incident','service_request')),
	CONSTRAINT "tickets_check_3" CHECK (NOT is_emergency OR priority='critical'),
	CONSTRAINT "tickets_check_4" CHECK (resolution_mode IN ('guided','onsite')),
	CONSTRAINT "tickets_check_5" CHECK (triage_status IN ('pending','provisional','confirmed','review_required'))
);
--> statement-breakpoint
ALTER TABLE "tickets" ENABLE ROW LEVEL SECURITY;--> statement-breakpoint
CREATE TABLE "triage_policy_bindings" (
	"id" uuid PRIMARY KEY DEFAULT gen_random_uuid() NOT NULL,
	"tenant_id" uuid NOT NULL,
	"domain_id" uuid NOT NULL,
	"scope_id" uuid NOT NULL,
	"category_id" uuid,
	"request_kind" text NOT NULL,
	"policy_version_id" uuid NOT NULL,
	"valid_from" timestamp with time zone NOT NULL,
	"valid_to" timestamp with time zone,
	"status" text NOT NULL,
	"configured_by" text NOT NULL,
	"created_at" timestamp with time zone DEFAULT now() NOT NULL,
	"updated_at" timestamp with time zone DEFAULT now() NOT NULL,
	CONSTRAINT "triage_policy_bindings_tenant_key_uq" UNIQUE("tenant_id","id"),
	CONSTRAINT "triage_policy_bindings_check_0" CHECK (valid_to IS NULL OR valid_to>valid_from),
	CONSTRAINT "triage_policy_bindings_check_1" CHECK (request_kind IN ('incident','service_request')),
	CONSTRAINT "triage_policy_bindings_check_2" CHECK (status IN ('active','disabled'))
);
--> statement-breakpoint
ALTER TABLE "triage_policy_bindings" ENABLE ROW LEVEL SECURITY;--> statement-breakpoint
CREATE TABLE "triage_policy_versions" (
	"id" uuid PRIMARY KEY DEFAULT gen_random_uuid() NOT NULL,
	"tenant_id" uuid NOT NULL,
	"domain_id" uuid NOT NULL,
	"policy_code" text NOT NULL,
	"version_no" integer NOT NULL,
	"status" text NOT NULL,
	"engine_version" text NOT NULL,
	"input_schema_version" text NOT NULL,
	"input_schema" jsonb NOT NULL,
	"unknown_priority" text NOT NULL,
	"review_timeout_seconds" integer NOT NULL,
	"max_fact_age_seconds" integer NOT NULL,
	"max_queue_wait_seconds" integer NOT NULL,
	"policy_hash" text NOT NULL,
	"created_by" text NOT NULL,
	"published_by" text,
	"published_at" timestamp with time zone,
	"created_at" timestamp with time zone DEFAULT now() NOT NULL,
	"updated_at" timestamp with time zone DEFAULT now() NOT NULL,
	CONSTRAINT "triage_policy_versions_tenant_key_uq" UNIQUE("tenant_id","id"),
	CONSTRAINT "triage_policy_versions_unique_0" UNIQUE("tenant_id","domain_id","policy_code","version_no"),
	CONSTRAINT "triage_policy_versions_check_0" CHECK (version_no>0),
	CONSTRAINT "triage_policy_versions_check_1" CHECK (unknown_priority IN ('normal','high','critical')),
	CONSTRAINT "triage_policy_versions_check_2" CHECK (review_timeout_seconds>0 AND max_fact_age_seconds>0 AND max_queue_wait_seconds>0),
	CONSTRAINT "triage_policy_versions_check_3" CHECK (status<>'published' OR (published_by IS NOT NULL AND published_at IS NOT NULL)),
	CONSTRAINT "triage_policy_versions_check_4" CHECK (status IN ('draft','published','retired'))
);
--> statement-breakpoint
ALTER TABLE "triage_policy_versions" ENABLE ROW LEVEL SECURITY;--> statement-breakpoint
CREATE TABLE "triage_rules" (
	"id" uuid PRIMARY KEY DEFAULT gen_random_uuid() NOT NULL,
	"tenant_id" uuid NOT NULL,
	"policy_version_id" uuid NOT NULL,
	"rule_code" text NOT NULL,
	"rule_kind" text NOT NULL,
	"precedence" integer NOT NULL,
	"condition_expr" jsonb NOT NULL,
	"severity_result" text NOT NULL,
	"priority_result" text NOT NULL,
	"requires_human_review" boolean DEFAULT false NOT NULL,
	"reason_template" text NOT NULL,
	"created_at" timestamp with time zone DEFAULT now() NOT NULL,
	CONSTRAINT "triage_rules_tenant_key_uq" UNIQUE("tenant_id","id"),
	CONSTRAINT "triage_rules_unique_0" UNIQUE("policy_version_id","rule_code"),
	CONSTRAINT "triage_rules_unique_1" UNIQUE("policy_version_id","rule_kind","precedence"),
	CONSTRAINT "triage_rules_check_0" CHECK (precedence>0),
	CONSTRAINT "triage_rules_check_1" CHECK (rule_kind<>'emergency_floor' OR severity_result<>'not_applicable'),
	CONSTRAINT "triage_rules_check_2" CHECK (rule_kind IN ('emergency_floor','decision')),
	CONSTRAINT "triage_rules_check_3" CHECK (severity_result IN ('minor','moderate','major','critical')),
	CONSTRAINT "triage_rules_check_4" CHECK (priority_result IN ('low','normal','high','critical'))
);
--> statement-breakpoint
ALTER TABLE "triage_rules" ENABLE ROW LEVEL SECURITY;--> statement-breakpoint
CREATE TABLE "unit_residents" (
	"id" uuid PRIMARY KEY DEFAULT gen_random_uuid() NOT NULL,
	"tenant_id" uuid NOT NULL,
	"unit_id" uuid NOT NULL,
	"user_id" text NOT NULL,
	"relation" text NOT NULL,
	"verification_status" text NOT NULL,
	"valid_from" timestamp with time zone NOT NULL,
	"valid_to" timestamp with time zone,
	"verified_by" text,
	"verified_at" timestamp with time zone,
	"created_at" timestamp with time zone DEFAULT now() NOT NULL,
	"updated_at" timestamp with time zone DEFAULT now() NOT NULL,
	CONSTRAINT "unit_residents_tenant_key_uq" UNIQUE("tenant_id","id"),
	CONSTRAINT "unit_residents_check_0" CHECK (relation IN ('owner','tenant','household')),
	CONSTRAINT "unit_residents_check_1" CHECK (verification_status IN ('pending','verified','rejected','expired'))
);
--> statement-breakpoint
ALTER TABLE "unit_residents" ENABLE ROW LEVEL SECURITY;--> statement-breakpoint
CREATE TABLE "units" (
	"id" uuid PRIMARY KEY DEFAULT gen_random_uuid() NOT NULL,
	"tenant_id" uuid NOT NULL,
	"site_id" uuid NOT NULL,
	"zone_id" uuid,
	"building_id" uuid,
	"code" text NOT NULL,
	"unit_kind" text NOT NULL,
	"floor" text,
	"status" text NOT NULL,
	"created_at" timestamp with time zone DEFAULT now() NOT NULL,
	"updated_at" timestamp with time zone DEFAULT now() NOT NULL,
	CONSTRAINT "units_tenant_key_uq" UNIQUE("tenant_id","id"),
	CONSTRAINT "units_check_0" CHECK (unit_kind IN ('apartment','townhouse','villa','other'))
);
--> statement-breakpoint
ALTER TABLE "units" ENABLE ROW LEVEL SECURITY;--> statement-breakpoint
CREATE TABLE "user_instructions" (
	"user_id" text PRIMARY KEY NOT NULL,
	"instructions" text NOT NULL,
	"created_at" timestamp with time zone DEFAULT now() NOT NULL,
	"updated_at" timestamp with time zone DEFAULT now() NOT NULL
);
--> statement-breakpoint
CREATE TABLE "user_roles" (
	"user_id" text NOT NULL,
	"role" "role" NOT NULL,
	"created_at" timestamp with time zone DEFAULT now() NOT NULL,
	CONSTRAINT "user_roles_user_id_role_pk" PRIMARY KEY("user_id","role")
);
--> statement-breakpoint
CREATE TABLE "users" (
	"id" text PRIMARY KEY NOT NULL,
	"email" text,
	"name" text,
	"image" text,
	"email_verified" boolean DEFAULT false NOT NULL,
	"groups" text[] DEFAULT '{}' NOT NULL,
	"onboarding_step" integer DEFAULT 0 NOT NULL,
	"onboarding_completed_at" timestamp with time zone,
	"last_signed_in_at" timestamp with time zone,
	"created_at" timestamp with time zone DEFAULT now() NOT NULL,
	"updated_at" timestamp with time zone DEFAULT now() NOT NULL,
	"phone_e164" text,
	"phone_verified_at" timestamp with time zone,
	"status" text DEFAULT 'pending' NOT NULL,
	"disabled_at" timestamp with time zone,
	"deleted_at" timestamp with time zone,
	CONSTRAINT "users_check_0" CHECK (status IN ('pending','active','suspended','deleted')),
	CONSTRAINT "users_check_1" CHECK (status='deleted' OR email IS NOT NULL OR phone_e164 IS NOT NULL)
);
--> statement-breakpoint
CREATE TABLE "verifications" (
	"id" text PRIMARY KEY NOT NULL,
	"identifier" text NOT NULL,
	"value" text NOT NULL,
	"expires_at" timestamp with time zone NOT NULL,
	"created_at" timestamp with time zone DEFAULT now() NOT NULL,
	"updated_at" timestamp with time zone DEFAULT now() NOT NULL
);
--> statement-breakpoint
CREATE TABLE "work_approval_evidence" (
	"id" uuid PRIMARY KEY DEFAULT gen_random_uuid() NOT NULL,
	"tenant_id" uuid NOT NULL,
	"approval_id" uuid NOT NULL,
	"evidence_id" uuid NOT NULL,
	"original_object_id" uuid NOT NULL,
	"sha256_snapshot" text NOT NULL,
	"created_at" timestamp with time zone DEFAULT now() NOT NULL,
	CONSTRAINT "work_approval_evidence_tenant_key_uq" UNIQUE("tenant_id","id"),
	CONSTRAINT "work_approval_evidence_unique_0" UNIQUE("approval_id","evidence_id")
);
--> statement-breakpoint
ALTER TABLE "work_approval_evidence" ENABLE ROW LEVEL SECURITY;--> statement-breakpoint
CREATE TABLE "work_approvals" (
	"id" uuid PRIMARY KEY DEFAULT gen_random_uuid() NOT NULL,
	"tenant_id" uuid NOT NULL,
	"work_order_id" uuid NOT NULL,
	"kind" text NOT NULL,
	"requested_to_user_id" text,
	"required_scope_id" uuid,
	"request_detail" jsonb NOT NULL,
	"status" text NOT NULL,
	"decided_by" text,
	"decided_at" timestamp with time zone,
	"decision_note" text,
	"expires_at" timestamp with time zone,
	"created_at" timestamp with time zone DEFAULT now() NOT NULL,
	"updated_at" timestamp with time zone DEFAULT now() NOT NULL,
	"evidence_cutoff_at" timestamp with time zone,
	"request_hash" text NOT NULL,
	"decided_event_id" uuid,
	CONSTRAINT "work_approvals_tenant_key_uq" UNIQUE("tenant_id","id"),
	CONSTRAINT "work_approvals_check_0" CHECK (num_nonnulls(requested_to_user_id,required_scope_id)=1),
	CONSTRAINT "work_approvals_check_1" CHECK (kind IN ('customer_repair','management_water_shutdown','customer_completion')),
	CONSTRAINT "work_approvals_check_2" CHECK (status IN ('pending','approved','rejected','expired','cancelled'))
);
--> statement-breakpoint
ALTER TABLE "work_approvals" ENABLE ROW LEVEL SECURITY;--> statement-breakpoint
CREATE TABLE "work_assignments" (
	"id" uuid PRIMARY KEY DEFAULT gen_random_uuid() NOT NULL,
	"tenant_id" uuid NOT NULL,
	"work_order_id" uuid NOT NULL,
	"staff_id" uuid NOT NULL,
	"assigned_by_user_id" text,
	"assigned_by_agent_id" text,
	"status" text NOT NULL,
	"offered_at" timestamp with time zone NOT NULL,
	"accepted_at" timestamp with time zone,
	"eta_at" timestamp with time zone,
	"ended_at" timestamp with time zone,
	"rejection_reason" text,
	"created_at" timestamp with time zone DEFAULT now() NOT NULL,
	"updated_at" timestamp with time zone DEFAULT now() NOT NULL,
	"offer_expires_at" timestamp with time zone,
	"dispatch_attempt_id" uuid,
	CONSTRAINT "work_assignments_tenant_key_uq" UNIQUE("tenant_id","id"),
	CONSTRAINT "work_assignments_check_0" CHECK (status IN ('offered','accepted','rejected','released','completed','cancelled'))
);
--> statement-breakpoint
ALTER TABLE "work_assignments" ENABLE ROW LEVEL SECURITY;--> statement-breakpoint
CREATE TABLE "work_items" (
	"kind" text NOT NULL,
	"key" text NOT NULL,
	"run_at" timestamp with time zone DEFAULT now() NOT NULL,
	"claimed_by" text,
	"lease_until" timestamp with time zone,
	"attempts" integer DEFAULT 0 NOT NULL,
	"finished_at" timestamp with time zone,
	"last_error" text,
	"payload" jsonb DEFAULT '{}'::jsonb NOT NULL,
	"created_at" timestamp with time zone DEFAULT now() NOT NULL,
	"updated_at" timestamp with time zone DEFAULT now() NOT NULL,
	"tenant_id" uuid,
	CONSTRAINT "work_items_kind_key_pk" PRIMARY KEY("kind","key")
);
--> statement-breakpoint
ALTER TABLE "work_items" ENABLE ROW LEVEL SECURITY;--> statement-breakpoint
CREATE TABLE "work_orders" (
	"id" uuid PRIMARY KEY DEFAULT gen_random_uuid() NOT NULL,
	"tenant_id" uuid NOT NULL,
	"ticket_id" uuid NOT NULL,
	"category_id" uuid NOT NULL,
	"description" text NOT NULL,
	"status" text NOT NULL,
	"required_specialty_id" uuid NOT NULL,
	"scheduled_at" timestamp with time zone,
	"arrived_at" timestamp with time zone,
	"started_at" timestamp with time zone,
	"completed_at" timestamp with time zone,
	"diagnosis" text,
	"repair_notes" text,
	"version" bigint DEFAULT 0 NOT NULL,
	"created_at" timestamp with time zone DEFAULT now() NOT NULL,
	"updated_at" timestamp with time zone DEFAULT now() NOT NULL,
	"required" boolean DEFAULT true NOT NULL,
	CONSTRAINT "work_orders_tenant_key_uq" UNIQUE("tenant_id","id"),
	CONSTRAINT "work_orders_check_0" CHECK (status IN ('queued','offered','accepted','en_route','arrived','awaiting_approval','in_progress','completed','rejected','cancelled'))
);
--> statement-breakpoint
ALTER TABLE "work_orders" ENABLE ROW LEVEL SECURITY;--> statement-breakpoint
CREATE TABLE "work_reassignment_requests" (
	"id" uuid PRIMARY KEY DEFAULT gen_random_uuid() NOT NULL,
	"tenant_id" uuid NOT NULL,
	"source_assignment_id" uuid NOT NULL,
	"target_work_order_id" uuid NOT NULL,
	"target_decision_id" uuid NOT NULL,
	"requested_by" text,
	"source_run_id" uuid,
	"reason" text NOT NULL,
	"status" text NOT NULL,
	"approved_by" text,
	"approved_at" timestamp with time zone,
	"safe_stop_confirmed_by" text,
	"safe_stop_confirmed_at" timestamp with time zone,
	"handover_snapshot" jsonb NOT NULL,
	"new_assignment_id" uuid,
	"expires_at" timestamp with time zone NOT NULL,
	"idempotency_key" text NOT NULL,
	"created_at" timestamp with time zone DEFAULT now() NOT NULL,
	"updated_at" timestamp with time zone DEFAULT now() NOT NULL,
	CONSTRAINT "work_reassignment_requests_tenant_key_uq" UNIQUE("tenant_id","id"),
	CONSTRAINT "work_reassignment_requests_unique_0" UNIQUE("tenant_id","idempotency_key"),
	CONSTRAINT "work_reassignment_requests_check_0" CHECK (num_nonnulls(requested_by,source_run_id)=1),
	CONSTRAINT "work_reassignment_requests_check_1" CHECK (status NOT IN ('executing','completed') OR (approved_by IS NOT NULL AND safe_stop_confirmed_by IS NOT NULL AND safe_stop_confirmed_at IS NOT NULL)),
	CONSTRAINT "work_reassignment_requests_check_2" CHECK (status<>'completed' OR new_assignment_id IS NOT NULL),
	CONSTRAINT "work_reassignment_requests_check_3" CHECK (status IN ('requested','approved','rejected','executing','completed','cancelled','expired'))
);
--> statement-breakpoint
ALTER TABLE "work_reassignment_requests" ENABLE ROW LEVEL SECURITY;--> statement-breakpoint
CREATE TABLE "workspace_members" (
	"tenant_id" uuid NOT NULL,
	"workspace_id" uuid NOT NULL,
	"user_id" text NOT NULL,
	"status" text NOT NULL,
	"joined_at" timestamp with time zone NOT NULL,
	"left_at" timestamp with time zone,
	"created_at" timestamp with time zone DEFAULT now() NOT NULL,
	CONSTRAINT "workspace_members_tenant_id_workspace_id_user_id_pk" PRIMARY KEY("tenant_id","workspace_id","user_id")
);
--> statement-breakpoint
ALTER TABLE "workspace_members" ENABLE ROW LEVEL SECURITY;--> statement-breakpoint
CREATE TABLE "workspaces" (
	"id" uuid PRIMARY KEY DEFAULT gen_random_uuid() NOT NULL,
	"tenant_id" uuid NOT NULL,
	"management_unit_id" uuid NOT NULL,
	"code" text NOT NULL,
	"name" text NOT NULL,
	"status" text NOT NULL,
	"created_at" timestamp with time zone DEFAULT now() NOT NULL,
	"updated_at" timestamp with time zone DEFAULT now() NOT NULL,
	CONSTRAINT "workspaces_tenant_key_uq" UNIQUE("tenant_id","id"),
	CONSTRAINT "workspaces_unique_0" UNIQUE("tenant_id","management_unit_id")
);
--> statement-breakpoint
ALTER TABLE "workspaces" ENABLE ROW LEVEL SECURITY;--> statement-breakpoint
CREATE TABLE "zones" (
	"id" uuid PRIMARY KEY DEFAULT gen_random_uuid() NOT NULL,
	"tenant_id" uuid NOT NULL,
	"site_id" uuid NOT NULL,
	"code" text NOT NULL,
	"name" text NOT NULL,
	"status" text NOT NULL,
	"created_at" timestamp with time zone DEFAULT now() NOT NULL,
	"updated_at" timestamp with time zone DEFAULT now() NOT NULL,
	CONSTRAINT "zones_tenant_key_uq" UNIQUE("tenant_id","id"),
	CONSTRAINT "zones_unique_0" UNIQUE("site_id","code")
);
--> statement-breakpoint
ALTER TABLE "zones" ENABLE ROW LEVEL SECURITY;--> statement-breakpoint
ALTER TABLE "access_scopes" ADD CONSTRAINT "access_scopes_tenant_id_fk" FOREIGN KEY ("tenant_id") REFERENCES "public"."tenants"("id") ON DELETE restrict ON UPDATE no action;--> statement-breakpoint
ALTER TABLE "access_scopes" ADD CONSTRAINT "access_scopes_management_unit_id_fk" FOREIGN KEY ("tenant_id","management_unit_id") REFERENCES "public"."management_units"("tenant_id","id") ON DELETE restrict ON UPDATE no action;--> statement-breakpoint
ALTER TABLE "access_scopes" ADD CONSTRAINT "access_scopes_site_id_fk" FOREIGN KEY ("tenant_id","site_id") REFERENCES "public"."sites"("tenant_id","id") ON DELETE restrict ON UPDATE no action;--> statement-breakpoint
ALTER TABLE "access_scopes" ADD CONSTRAINT "access_scopes_zone_id_fk" FOREIGN KEY ("tenant_id","zone_id") REFERENCES "public"."zones"("tenant_id","id") ON DELETE restrict ON UPDATE no action;--> statement-breakpoint
ALTER TABLE "access_scopes" ADD CONSTRAINT "access_scopes_building_id_fk" FOREIGN KEY ("tenant_id","building_id") REFERENCES "public"."buildings"("tenant_id","id") ON DELETE restrict ON UPDATE no action;--> statement-breakpoint
ALTER TABLE "account_reviews" ADD CONSTRAINT "account_reviews_tenant_id_fk" FOREIGN KEY ("tenant_id") REFERENCES "public"."tenants"("id") ON DELETE restrict ON UPDATE no action;--> statement-breakpoint
ALTER TABLE "account_reviews" ADD CONSTRAINT "account_reviews_user_id_fk" FOREIGN KEY ("user_id") REFERENCES "public"."users"("id") ON DELETE restrict ON UPDATE no action;--> statement-breakpoint
ALTER TABLE "account_reviews" ADD CONSTRAINT "account_reviews_reviewer_user_id_fk" FOREIGN KEY ("reviewer_user_id") REFERENCES "public"."users"("id") ON DELETE restrict ON UPDATE no action;--> statement-breakpoint
ALTER TABLE "accounts" ADD CONSTRAINT "accounts_user_id_fk" FOREIGN KEY ("user_id") REFERENCES "public"."users"("id") ON DELETE cascade ON UPDATE no action;--> statement-breakpoint
ALTER TABLE "agent_build_answers" ADD CONSTRAINT "agent_build_answers_tenant_id_fk" FOREIGN KEY ("tenant_id") REFERENCES "public"."tenants"("id") ON DELETE restrict ON UPDATE no action;--> statement-breakpoint
ALTER TABLE "agent_build_answers" ADD CONSTRAINT "agent_build_answers_request_id_fk" FOREIGN KEY ("tenant_id","request_id") REFERENCES "public"."agent_build_requests"("tenant_id","id") ON DELETE restrict ON UPDATE no action;--> statement-breakpoint
ALTER TABLE "agent_build_answers" ADD CONSTRAINT "agent_build_answers_answered_by_fk" FOREIGN KEY ("answered_by") REFERENCES "public"."users"("id") ON DELETE restrict ON UPDATE no action;--> statement-breakpoint
ALTER TABLE "agent_build_requests" ADD CONSTRAINT "agent_build_requests_tenant_id_fk" FOREIGN KEY ("tenant_id") REFERENCES "public"."tenants"("id") ON DELETE restrict ON UPDATE no action;--> statement-breakpoint
ALTER TABLE "agent_build_requests" ADD CONSTRAINT "agent_build_requests_workspace_id_fk" FOREIGN KEY ("tenant_id","workspace_id") REFERENCES "public"."workspaces"("tenant_id","id") ON DELETE restrict ON UPDATE no action;--> statement-breakpoint
ALTER TABLE "agent_build_requests" ADD CONSTRAINT "agent_build_requests_requested_by_fk" FOREIGN KEY ("requested_by") REFERENCES "public"."users"("id") ON DELETE restrict ON UPDATE no action;--> statement-breakpoint
ALTER TABLE "agent_build_requests" ADD CONSTRAINT "agent_build_requests_channel_id_fk" FOREIGN KEY ("tenant_id","channel_id") REFERENCES "public"."channels"("tenant_id","id") ON DELETE restrict ON UPDATE no action;--> statement-breakpoint
ALTER TABLE "agent_build_requests" ADD CONSTRAINT "agent_build_requests_result_agent_id_fk" FOREIGN KEY ("tenant_id","result_agent_id") REFERENCES "public"."agents"("tenant_id","id") ON DELETE restrict ON UPDATE no action;--> statement-breakpoint
ALTER TABLE "agent_knowledge_grants" ADD CONSTRAINT "agent_knowledge_grants_tenant_id_fk" FOREIGN KEY ("tenant_id") REFERENCES "public"."tenants"("id") ON DELETE restrict ON UPDATE no action;--> statement-breakpoint
ALTER TABLE "agent_knowledge_grants" ADD CONSTRAINT "agent_knowledge_grants_agent_id_fk" FOREIGN KEY ("tenant_id","agent_id") REFERENCES "public"."agents"("tenant_id","id") ON DELETE restrict ON UPDATE no action;--> statement-breakpoint
ALTER TABLE "agent_knowledge_grants" ADD CONSTRAINT "agent_knowledge_grants_knowledge_base_id_fk" FOREIGN KEY ("tenant_id","knowledge_base_id") REFERENCES "public"."knowledge_bases"("tenant_id","id") ON DELETE restrict ON UPDATE no action;--> statement-breakpoint
ALTER TABLE "agent_knowledge_grants" ADD CONSTRAINT "agent_knowledge_grants_granted_by_fk" FOREIGN KEY ("granted_by") REFERENCES "public"."users"("id") ON DELETE restrict ON UPDATE no action;--> statement-breakpoint
ALTER TABLE "agent_preferences" ADD CONSTRAINT "agent_preferences_user_id_fk" FOREIGN KEY ("user_id") REFERENCES "public"."users"("id") ON DELETE restrict ON UPDATE no action;--> statement-breakpoint
ALTER TABLE "agent_preferences" ADD CONSTRAINT "agent_preferences_agent_id_fk" FOREIGN KEY ("tenant_id","agent_id") REFERENCES "public"."agents"("tenant_id","id") ON DELETE restrict ON UPDATE no action;--> statement-breakpoint
ALTER TABLE "agent_preferences" ADD CONSTRAINT "agent_preferences_tenant_id_fk" FOREIGN KEY ("tenant_id") REFERENCES "public"."tenants"("id") ON DELETE restrict ON UPDATE no action;--> statement-breakpoint
ALTER TABLE "agent_profiles" ADD CONSTRAINT "agent_profiles_agent_id_fk" FOREIGN KEY ("tenant_id","agent_id") REFERENCES "public"."agents"("tenant_id","id") ON DELETE restrict ON UPDATE no action;--> statement-breakpoint
ALTER TABLE "agent_profiles" ADD CONSTRAINT "agent_profiles_owner_user_id_fk" FOREIGN KEY ("owner_user_id") REFERENCES "public"."users"("id") ON DELETE restrict ON UPDATE no action;--> statement-breakpoint
ALTER TABLE "agent_profiles" ADD CONSTRAINT "agent_profiles_tenant_id_fk" FOREIGN KEY ("tenant_id") REFERENCES "public"."tenants"("id") ON DELETE restrict ON UPDATE no action;--> statement-breakpoint
ALTER TABLE "agent_releases" ADD CONSTRAINT "agent_releases_tenant_id_fk" FOREIGN KEY ("tenant_id") REFERENCES "public"."tenants"("id") ON DELETE restrict ON UPDATE no action;--> statement-breakpoint
ALTER TABLE "agent_releases" ADD CONSTRAINT "agent_releases_agent_id_fk" FOREIGN KEY ("tenant_id","agent_id") REFERENCES "public"."agents"("tenant_id","id") ON DELETE restrict ON UPDATE no action;--> statement-breakpoint
ALTER TABLE "agent_releases" ADD CONSTRAINT "agent_releases_version_id_fk" FOREIGN KEY ("tenant_id","version_id") REFERENCES "public"."agent_versions"("tenant_id","id") ON DELETE restrict ON UPDATE no action;--> statement-breakpoint
ALTER TABLE "agent_releases" ADD CONSTRAINT "agent_releases_published_by_fk" FOREIGN KEY ("published_by") REFERENCES "public"."users"("id") ON DELETE restrict ON UPDATE no action;--> statement-breakpoint
ALTER TABLE "agent_runs" ADD CONSTRAINT "agent_runs_tenant_id_fk" FOREIGN KEY ("tenant_id") REFERENCES "public"."tenants"("id") ON DELETE restrict ON UPDATE no action;--> statement-breakpoint
ALTER TABLE "agent_runs" ADD CONSTRAINT "agent_runs_channel_id_fk" FOREIGN KEY ("tenant_id","channel_id") REFERENCES "public"."channels"("tenant_id","id") ON DELETE restrict ON UPDATE no action;--> statement-breakpoint
ALTER TABLE "agent_runs" ADD CONSTRAINT "agent_runs_agent_id_fk" FOREIGN KEY ("tenant_id","agent_id") REFERENCES "public"."agents"("tenant_id","id") ON DELETE restrict ON UPDATE no action;--> statement-breakpoint
ALTER TABLE "agent_runs" ADD CONSTRAINT "agent_runs_version_id_fk" FOREIGN KEY ("tenant_id","version_id") REFERENCES "public"."agent_versions"("tenant_id","id") ON DELETE restrict ON UPDATE no action;--> statement-breakpoint
ALTER TABLE "agent_runs" ADD CONSTRAINT "agent_runs_team_member_id_fk" FOREIGN KEY ("tenant_id","team_member_id") REFERENCES "public"."team_members"("tenant_id","id") ON DELETE restrict ON UPDATE no action;--> statement-breakpoint
ALTER TABLE "agent_runs" ADD CONSTRAINT "agent_runs_actor_user_id_fk" FOREIGN KEY ("actor_user_id") REFERENCES "public"."users"("id") ON DELETE restrict ON UPDATE no action;--> statement-breakpoint
ALTER TABLE "agent_runs" ADD CONSTRAINT "agent_runs_parent_run_id_fk" FOREIGN KEY ("tenant_id","parent_run_id") REFERENCES "public"."agent_runs"("tenant_id","id") ON DELETE restrict ON UPDATE no action;--> statement-breakpoint
ALTER TABLE "agent_runs" ADD CONSTRAINT "agent_runs_trigger_event_id_fk" FOREIGN KEY ("tenant_id","trigger_event_id") REFERENCES "public"."ticket_events"("tenant_id","id") ON DELETE restrict ON UPDATE no action;--> statement-breakpoint
ALTER TABLE "agent_runs" ADD CONSTRAINT "agent_runs_binding_id_fk" FOREIGN KEY ("tenant_id","binding_id") REFERENCES "public"."runtime_session_bindings"("tenant_id","id") ON DELETE restrict ON UPDATE no action;--> statement-breakpoint
ALTER TABLE "agent_runs" ADD CONSTRAINT "agent_runs_authority_principal_id_fk" FOREIGN KEY ("tenant_id","authority_principal_id") REFERENCES "public"."execution_principals"("tenant_id","id") ON DELETE restrict ON UPDATE no action;--> statement-breakpoint
ALTER TABLE "agent_runs" ADD CONSTRAINT "agent_runs_on_behalf_of_user_id_fk" FOREIGN KEY ("on_behalf_of_user_id") REFERENCES "public"."users"("id") ON DELETE restrict ON UPDATE no action;--> statement-breakpoint
ALTER TABLE "agent_teams" ADD CONSTRAINT "agent_teams_tenant_id_fk" FOREIGN KEY ("tenant_id") REFERENCES "public"."tenants"("id") ON DELETE restrict ON UPDATE no action;--> statement-breakpoint
ALTER TABLE "agent_teams" ADD CONSTRAINT "agent_teams_workspace_id_fk" FOREIGN KEY ("tenant_id","workspace_id") REFERENCES "public"."workspaces"("tenant_id","id") ON DELETE restrict ON UPDATE no action;--> statement-breakpoint
ALTER TABLE "agent_teams" ADD CONSTRAINT "agent_teams_channel_id_fk" FOREIGN KEY ("tenant_id","channel_id") REFERENCES "public"."channels"("tenant_id","id") ON DELETE restrict ON UPDATE no action;--> statement-breakpoint
ALTER TABLE "agent_teams" ADD CONSTRAINT "agent_teams_ticket_id_fk" FOREIGN KEY ("tenant_id","ticket_id") REFERENCES "public"."tickets"("tenant_id","id") ON DELETE restrict ON UPDATE no action;--> statement-breakpoint
ALTER TABLE "agent_teams" ADD CONSTRAINT "agent_teams_request_message_id_fk" FOREIGN KEY ("tenant_id","request_message_id") REFERENCES "public"."messages"("tenant_id","id") ON DELETE restrict ON UPDATE no action;--> statement-breakpoint
ALTER TABLE "agent_teams" ADD CONSTRAINT "agent_teams_supervisor_agent_id_fk" FOREIGN KEY ("tenant_id","supervisor_agent_id") REFERENCES "public"."agents"("tenant_id","id") ON DELETE restrict ON UPDATE no action;--> statement-breakpoint
ALTER TABLE "agent_teams" ADD CONSTRAINT "agent_teams_requested_by_user_id_fk" FOREIGN KEY ("requested_by_user_id") REFERENCES "public"."users"("id") ON DELETE restrict ON UPDATE no action;--> statement-breakpoint
ALTER TABLE "agent_versions" ADD CONSTRAINT "agent_versions_tenant_id_fk" FOREIGN KEY ("tenant_id") REFERENCES "public"."tenants"("id") ON DELETE restrict ON UPDATE no action;--> statement-breakpoint
ALTER TABLE "agent_versions" ADD CONSTRAINT "agent_versions_agent_id_fk" FOREIGN KEY ("tenant_id","agent_id") REFERENCES "public"."agents"("tenant_id","id") ON DELETE restrict ON UPDATE no action;--> statement-breakpoint
ALTER TABLE "agent_versions" ADD CONSTRAINT "agent_versions_model_profile_id_fk" FOREIGN KEY ("tenant_id","model_profile_id") REFERENCES "public"."model_profiles"("tenant_id","id") ON DELETE restrict ON UPDATE no action;--> statement-breakpoint
ALTER TABLE "agent_versions" ADD CONSTRAINT "agent_versions_created_by_fk" FOREIGN KEY ("created_by") REFERENCES "public"."users"("id") ON DELETE restrict ON UPDATE no action;--> statement-breakpoint
ALTER TABLE "agents" ADD CONSTRAINT "agents_package_id_fk" FOREIGN KEY ("tenant_id","package_id") REFERENCES "public"."deployment_packages"("tenant_id","id") ON DELETE restrict ON UPDATE no action;--> statement-breakpoint
ALTER TABLE "agents" ADD CONSTRAINT "agents_tenant_id_fk" FOREIGN KEY ("tenant_id") REFERENCES "public"."tenants"("id") ON DELETE restrict ON UPDATE no action;--> statement-breakpoint
ALTER TABLE "agents" ADD CONSTRAINT "agents_workspace_id_fk" FOREIGN KEY ("tenant_id","workspace_id") REFERENCES "public"."workspaces"("tenant_id","id") ON DELETE restrict ON UPDATE no action;--> statement-breakpoint
ALTER TABLE "attachments" ADD CONSTRAINT "attachments_channel_id_fk" FOREIGN KEY ("channel_id") REFERENCES "public"."channels"("id") ON DELETE restrict ON UPDATE no action;--> statement-breakpoint
ALTER TABLE "attachments" ADD CONSTRAINT "attachments_uploaded_by_fk" FOREIGN KEY ("uploaded_by") REFERENCES "public"."users"("id") ON DELETE restrict ON UPDATE no action;--> statement-breakpoint
ALTER TABLE "attachments" ADD CONSTRAINT "attachments_file_id_fk" FOREIGN KEY ("file_id") REFERENCES "public"."files"("id") ON DELETE restrict ON UPDATE no action;--> statement-breakpoint
ALTER TABLE "audit_events" ADD CONSTRAINT "audit_events_tenant_id_fk" FOREIGN KEY ("tenant_id") REFERENCES "public"."tenants"("id") ON DELETE restrict ON UPDATE no action;--> statement-breakpoint
ALTER TABLE "audit_events" ADD CONSTRAINT "audit_events_workspace_id_fk" FOREIGN KEY ("tenant_id","workspace_id") REFERENCES "public"."workspaces"("tenant_id","id") ON DELETE restrict ON UPDATE no action;--> statement-breakpoint
ALTER TABLE "buildings" ADD CONSTRAINT "buildings_tenant_id_fk" FOREIGN KEY ("tenant_id") REFERENCES "public"."tenants"("id") ON DELETE restrict ON UPDATE no action;--> statement-breakpoint
ALTER TABLE "buildings" ADD CONSTRAINT "buildings_site_id_fk" FOREIGN KEY ("tenant_id","site_id") REFERENCES "public"."sites"("tenant_id","id") ON DELETE restrict ON UPDATE no action;--> statement-breakpoint
ALTER TABLE "buildings" ADD CONSTRAINT "buildings_zone_id_fk" FOREIGN KEY ("tenant_id","zone_id") REFERENCES "public"."zones"("tenant_id","id") ON DELETE restrict ON UPDATE no action;--> statement-breakpoint
ALTER TABLE "channel_agents" ADD CONSTRAINT "channel_agents_channel_id_fk" FOREIGN KEY ("tenant_id","channel_id") REFERENCES "public"."channels"("tenant_id","id") ON DELETE restrict ON UPDATE no action;--> statement-breakpoint
ALTER TABLE "channel_agents" ADD CONSTRAINT "channel_agents_agent_id_fk" FOREIGN KEY ("tenant_id","agent_id") REFERENCES "public"."agents"("tenant_id","id") ON DELETE restrict ON UPDATE no action;--> statement-breakpoint
ALTER TABLE "channel_agents" ADD CONSTRAINT "channel_agents_tenant_id_fk" FOREIGN KEY ("tenant_id") REFERENCES "public"."tenants"("id") ON DELETE restrict ON UPDATE no action;--> statement-breakpoint
ALTER TABLE "channel_memberships" ADD CONSTRAINT "channel_memberships_channel_id_fk" FOREIGN KEY ("tenant_id","channel_id") REFERENCES "public"."channels"("tenant_id","id") ON DELETE restrict ON UPDATE no action;--> statement-breakpoint
ALTER TABLE "channel_memberships" ADD CONSTRAINT "channel_memberships_user_id_fk" FOREIGN KEY ("user_id") REFERENCES "public"."users"("id") ON DELETE restrict ON UPDATE no action;--> statement-breakpoint
ALTER TABLE "channel_memberships" ADD CONSTRAINT "channel_memberships_tenant_id_fk" FOREIGN KEY ("tenant_id") REFERENCES "public"."tenants"("id") ON DELETE restrict ON UPDATE no action;--> statement-breakpoint
ALTER TABLE "channels" ADD CONSTRAINT "channels_package_id_fk" FOREIGN KEY ("tenant_id","package_id") REFERENCES "public"."deployment_packages"("tenant_id","id") ON DELETE restrict ON UPDATE no action;--> statement-breakpoint
ALTER TABLE "channels" ADD CONSTRAINT "channels_last_message_agent_id_fk" FOREIGN KEY ("tenant_id","last_message_agent_id") REFERENCES "public"."agents"("tenant_id","id") ON DELETE restrict ON UPDATE no action;--> statement-breakpoint
ALTER TABLE "channels" ADD CONSTRAINT "channels_tenant_id_fk" FOREIGN KEY ("tenant_id") REFERENCES "public"."tenants"("id") ON DELETE restrict ON UPDATE no action;--> statement-breakpoint
ALTER TABLE "channels" ADD CONSTRAINT "channels_workspace_id_fk" FOREIGN KEY ("tenant_id","workspace_id") REFERENCES "public"."workspaces"("tenant_id","id") ON DELETE restrict ON UPDATE no action;--> statement-breakpoint
ALTER TABLE "channels" ADD CONSTRAINT "channels_created_by_fk" FOREIGN KEY ("created_by") REFERENCES "public"."users"("id") ON DELETE restrict ON UPDATE no action;--> statement-breakpoint
ALTER TABLE "component_exclusions" ADD CONSTRAINT "component_exclusions_component_name_fk" FOREIGN KEY ("component_name") REFERENCES "public"."components"("name") ON DELETE restrict ON UPDATE no action;--> statement-breakpoint
ALTER TABLE "component_exclusions" ADD CONSTRAINT "component_exclusions_agent_id_fk" FOREIGN KEY ("tenant_id","agent_id") REFERENCES "public"."agents"("tenant_id","id") ON DELETE restrict ON UPDATE no action;--> statement-breakpoint
ALTER TABLE "component_exclusions" ADD CONSTRAINT "component_exclusions_tenant_id_fk" FOREIGN KEY ("tenant_id") REFERENCES "public"."tenants"("id") ON DELETE restrict ON UPDATE no action;--> statement-breakpoint
ALTER TABLE "component_functions" ADD CONSTRAINT "component_functions_component_name_fk" FOREIGN KEY ("component_name") REFERENCES "public"."components"("name") ON DELETE restrict ON UPDATE no action;--> statement-breakpoint
ALTER TABLE "composio_connections" ADD CONSTRAINT "composio_connections_user_id_fk" FOREIGN KEY ("user_id") REFERENCES "public"."users"("id") ON DELETE restrict ON UPDATE no action;--> statement-breakpoint
ALTER TABLE "composio_connections" ADD CONSTRAINT "composio_connections_tenant_id_fk" FOREIGN KEY ("tenant_id") REFERENCES "public"."tenants"("id") ON DELETE restrict ON UPDATE no action;--> statement-breakpoint
ALTER TABLE "computer_page_frame" ADD CONSTRAINT "computer_page_frame_tenant_id_fk" FOREIGN KEY ("tenant_id") REFERENCES "public"."tenants"("id") ON DELETE restrict ON UPDATE no action;--> statement-breakpoint
ALTER TABLE "computer_page_frame" ADD CONSTRAINT "computer_page_frame_agent_id_fk" FOREIGN KEY ("tenant_id","agent_id") REFERENCES "public"."agents"("tenant_id","id") ON DELETE restrict ON UPDATE no action;--> statement-breakpoint
ALTER TABLE "computer_snapshot" ADD CONSTRAINT "computer_snapshot_tenant_id_fk" FOREIGN KEY ("tenant_id") REFERENCES "public"."tenants"("id") ON DELETE restrict ON UPDATE no action;--> statement-breakpoint
ALTER TABLE "computer_snapshot" ADD CONSTRAINT "computer_snapshot_agent_id_fk" FOREIGN KEY ("tenant_id","agent_id") REFERENCES "public"."agents"("tenant_id","id") ON DELETE restrict ON UPDATE no action;--> statement-breakpoint
ALTER TABLE "context_snapshots" ADD CONSTRAINT "context_snapshots_tenant_id_fk" FOREIGN KEY ("tenant_id") REFERENCES "public"."tenants"("id") ON DELETE restrict ON UPDATE no action;--> statement-breakpoint
ALTER TABLE "context_snapshots" ADD CONSTRAINT "context_snapshots_run_id_fk" FOREIGN KEY ("tenant_id","run_id") REFERENCES "public"."agent_runs"("tenant_id","id") ON DELETE restrict ON UPDATE no action;--> statement-breakpoint
ALTER TABLE "context_snapshots" ADD CONSTRAINT "context_snapshots_requested_message_id_fk" FOREIGN KEY ("tenant_id","requested_message_id") REFERENCES "public"."messages"("tenant_id","id") ON DELETE restrict ON UPDATE no action;--> statement-breakpoint
ALTER TABLE "context_snapshots" ADD CONSTRAINT "context_snapshots_ticket_id_fk" FOREIGN KEY ("tenant_id","ticket_id") REFERENCES "public"."tickets"("tenant_id","id") ON DELETE restrict ON UPDATE no action;--> statement-breakpoint
ALTER TABLE "credentials" ADD CONSTRAINT "credentials_tenant_id_fk" FOREIGN KEY ("tenant_id") REFERENCES "public"."tenants"("id") ON DELETE restrict ON UPDATE no action;--> statement-breakpoint
ALTER TABLE "credentials" ADD CONSTRAINT "credentials_workspace_id_fk" FOREIGN KEY ("tenant_id","workspace_id") REFERENCES "public"."workspaces"("tenant_id","id") ON DELETE restrict ON UPDATE no action;--> statement-breakpoint
ALTER TABLE "deployment_packages" ADD CONSTRAINT "deployment_packages_tenant_id_fk" FOREIGN KEY ("tenant_id") REFERENCES "public"."tenants"("id") ON DELETE restrict ON UPDATE no action;--> statement-breakpoint
ALTER TABLE "dispatch_attempts" ADD CONSTRAINT "dispatch_attempts_tenant_id_fk" FOREIGN KEY ("tenant_id") REFERENCES "public"."tenants"("id") ON DELETE restrict ON UPDATE no action;--> statement-breakpoint
ALTER TABLE "dispatch_attempts" ADD CONSTRAINT "dispatch_attempts_queue_id_fk" FOREIGN KEY ("tenant_id","queue_id") REFERENCES "public"."dispatch_queue"("tenant_id","id") ON DELETE restrict ON UPDATE no action;--> statement-breakpoint
ALTER TABLE "dispatch_attempts" ADD CONSTRAINT "dispatch_attempts_work_order_id_fk" FOREIGN KEY ("tenant_id","work_order_id") REFERENCES "public"."work_orders"("tenant_id","id") ON DELETE restrict ON UPDATE no action;--> statement-breakpoint
ALTER TABLE "dispatch_attempts" ADD CONSTRAINT "dispatch_attempts_decision_id_fk" FOREIGN KEY ("tenant_id","decision_id") REFERENCES "public"."ticket_triage_decisions"("tenant_id","id") ON DELETE restrict ON UPDATE no action;--> statement-breakpoint
ALTER TABLE "dispatch_attempts" ADD CONSTRAINT "dispatch_attempts_assignment_id_fk" FOREIGN KEY ("tenant_id","assignment_id") REFERENCES "public"."work_assignments"("tenant_id","id") ON DELETE restrict ON UPDATE no action;--> statement-breakpoint
ALTER TABLE "dispatch_queue" ADD CONSTRAINT "dispatch_queue_tenant_id_fk" FOREIGN KEY ("tenant_id") REFERENCES "public"."tenants"("id") ON DELETE restrict ON UPDATE no action;--> statement-breakpoint
ALTER TABLE "dispatch_queue" ADD CONSTRAINT "dispatch_queue_work_order_id_fk" FOREIGN KEY ("tenant_id","work_order_id") REFERENCES "public"."work_orders"("tenant_id","id") ON DELETE restrict ON UPDATE no action;--> statement-breakpoint
ALTER TABLE "dispatch_queue" ADD CONSTRAINT "dispatch_queue_management_unit_id_fk" FOREIGN KEY ("tenant_id","management_unit_id") REFERENCES "public"."management_units"("tenant_id","id") ON DELETE restrict ON UPDATE no action;--> statement-breakpoint
ALTER TABLE "dispatch_queue" ADD CONSTRAINT "dispatch_queue_category_id_fk" FOREIGN KEY ("tenant_id","category_id") REFERENCES "public"."service_categories"("tenant_id","id") ON DELETE restrict ON UPDATE no action;--> statement-breakpoint
ALTER TABLE "dispatch_queue" ADD CONSTRAINT "dispatch_queue_priority_decision_id_fk" FOREIGN KEY ("tenant_id","priority_decision_id") REFERENCES "public"."ticket_triage_decisions"("tenant_id","id") ON DELETE restrict ON UPDATE no action;--> statement-breakpoint
ALTER TABLE "document_acl" ADD CONSTRAINT "document_acl_tenant_id_fk" FOREIGN KEY ("tenant_id") REFERENCES "public"."tenants"("id") ON DELETE restrict ON UPDATE no action;--> statement-breakpoint
ALTER TABLE "document_acl" ADD CONSTRAINT "document_acl_document_id_fk" FOREIGN KEY ("tenant_id","document_id") REFERENCES "public"."knowledge_documents"("tenant_id","id") ON DELETE restrict ON UPDATE no action;--> statement-breakpoint
ALTER TABLE "document_acl" ADD CONSTRAINT "document_acl_user_id_fk" FOREIGN KEY ("user_id") REFERENCES "public"."users"("id") ON DELETE restrict ON UPDATE no action;--> statement-breakpoint
ALTER TABLE "document_acl" ADD CONSTRAINT "document_acl_workspace_id_fk" FOREIGN KEY ("tenant_id","workspace_id") REFERENCES "public"."workspaces"("tenant_id","id") ON DELETE restrict ON UPDATE no action;--> statement-breakpoint
ALTER TABLE "document_scopes" ADD CONSTRAINT "document_scopes_tenant_id_fk" FOREIGN KEY ("tenant_id") REFERENCES "public"."tenants"("id") ON DELETE restrict ON UPDATE no action;--> statement-breakpoint
ALTER TABLE "document_scopes" ADD CONSTRAINT "document_scopes_document_id_fk" FOREIGN KEY ("tenant_id","document_id") REFERENCES "public"."knowledge_documents"("tenant_id","id") ON DELETE restrict ON UPDATE no action;--> statement-breakpoint
ALTER TABLE "document_scopes" ADD CONSTRAINT "document_scopes_scope_id_fk" FOREIGN KEY ("tenant_id","scope_id") REFERENCES "public"."access_scopes"("tenant_id","id") ON DELETE restrict ON UPDATE no action;--> statement-breakpoint
ALTER TABLE "document_versions" ADD CONSTRAINT "document_versions_tenant_id_fk" FOREIGN KEY ("tenant_id") REFERENCES "public"."tenants"("id") ON DELETE restrict ON UPDATE no action;--> statement-breakpoint
ALTER TABLE "document_versions" ADD CONSTRAINT "document_versions_document_id_fk" FOREIGN KEY ("tenant_id","document_id") REFERENCES "public"."knowledge_documents"("tenant_id","id") ON DELETE restrict ON UPDATE no action;--> statement-breakpoint
ALTER TABLE "document_versions" ADD CONSTRAINT "document_versions_file_id_fk" FOREIGN KEY ("tenant_id","file_id") REFERENCES "public"."files"("tenant_id","id") ON DELETE restrict ON UPDATE no action;--> statement-breakpoint
ALTER TABLE "document_versions" ADD CONSTRAINT "document_versions_submitted_by_fk" FOREIGN KEY ("submitted_by") REFERENCES "public"."users"("id") ON DELETE restrict ON UPDATE no action;--> statement-breakpoint
ALTER TABLE "domains" ADD CONSTRAINT "domains_tenant_id_fk" FOREIGN KEY ("tenant_id") REFERENCES "public"."tenants"("id") ON DELETE restrict ON UPDATE no action;--> statement-breakpoint
ALTER TABLE "event_inbox" ADD CONSTRAINT "event_inbox_tenant_id_fk" FOREIGN KEY ("tenant_id") REFERENCES "public"."tenants"("id") ON DELETE restrict ON UPDATE no action;--> statement-breakpoint
ALTER TABLE "event_inbox" ADD CONSTRAINT "event_inbox_event_id_fk" FOREIGN KEY ("tenant_id","event_id") REFERENCES "public"."ticket_events"("tenant_id","id") ON DELETE restrict ON UPDATE no action;--> statement-breakpoint
ALTER TABLE "event_outbox" ADD CONSTRAINT "event_outbox_tenant_id_fk" FOREIGN KEY ("tenant_id") REFERENCES "public"."tenants"("id") ON DELETE restrict ON UPDATE no action;--> statement-breakpoint
ALTER TABLE "event_outbox" ADD CONSTRAINT "event_outbox_event_id_fk" FOREIGN KEY ("tenant_id","event_id") REFERENCES "public"."ticket_events"("tenant_id","id") ON DELETE restrict ON UPDATE no action;--> statement-breakpoint
ALTER TABLE "evidence_items" ADD CONSTRAINT "evidence_items_tenant_id_fk" FOREIGN KEY ("tenant_id") REFERENCES "public"."tenants"("id") ON DELETE restrict ON UPDATE no action;--> statement-breakpoint
ALTER TABLE "evidence_items" ADD CONSTRAINT "evidence_items_ticket_id_fk" FOREIGN KEY ("tenant_id","ticket_id") REFERENCES "public"."tickets"("tenant_id","id") ON DELETE restrict ON UPDATE no action;--> statement-breakpoint
ALTER TABLE "evidence_items" ADD CONSTRAINT "evidence_items_work_order_id_fk" FOREIGN KEY ("tenant_id","work_order_id") REFERENCES "public"."work_orders"("tenant_id","id") ON DELETE restrict ON UPDATE no action;--> statement-breakpoint
ALTER TABLE "evidence_items" ADD CONSTRAINT "evidence_items_assignment_id_fk" FOREIGN KEY ("tenant_id","assignment_id") REFERENCES "public"."work_assignments"("tenant_id","id") ON DELETE restrict ON UPDATE no action;--> statement-breakpoint
ALTER TABLE "evidence_items" ADD CONSTRAINT "evidence_items_file_id_fk" FOREIGN KEY ("tenant_id","file_id") REFERENCES "public"."files"("tenant_id","id") ON DELETE restrict ON UPDATE no action;--> statement-breakpoint
ALTER TABLE "evidence_items" ADD CONSTRAINT "evidence_items_uploaded_by_fk" FOREIGN KEY ("uploaded_by") REFERENCES "public"."users"("id") ON DELETE restrict ON UPDATE no action;--> statement-breakpoint
ALTER TABLE "evidence_items" ADD CONSTRAINT "evidence_items_supersedes_id_fk" FOREIGN KEY ("tenant_id","supersedes_id") REFERENCES "public"."evidence_items"("tenant_id","id") ON DELETE restrict ON UPDATE no action;--> statement-breakpoint
ALTER TABLE "execution_principals" ADD CONSTRAINT "execution_principals_tenant_id_fk" FOREIGN KEY ("tenant_id") REFERENCES "public"."tenants"("id") ON DELETE restrict ON UPDATE no action;--> statement-breakpoint
ALTER TABLE "execution_principals" ADD CONSTRAINT "execution_principals_user_id_fk" FOREIGN KEY ("user_id") REFERENCES "public"."users"("id") ON DELETE restrict ON UPDATE no action;--> statement-breakpoint
ALTER TABLE "execution_principals" ADD CONSTRAINT "execution_principals_workspace_id_fk" FOREIGN KEY ("tenant_id","workspace_id") REFERENCES "public"."workspaces"("tenant_id","id") ON DELETE restrict ON UPDATE no action;--> statement-breakpoint
ALTER TABLE "file_access_logs" ADD CONSTRAINT "file_access_logs_tenant_id_fk" FOREIGN KEY ("tenant_id") REFERENCES "public"."tenants"("id") ON DELETE restrict ON UPDATE no action;--> statement-breakpoint
ALTER TABLE "file_access_logs" ADD CONSTRAINT "file_access_logs_file_id_fk" FOREIGN KEY ("tenant_id","file_id") REFERENCES "public"."files"("tenant_id","id") ON DELETE restrict ON UPDATE no action;--> statement-breakpoint
ALTER TABLE "file_access_logs" ADD CONSTRAINT "file_access_logs_object_id_fk" FOREIGN KEY ("tenant_id","object_id") REFERENCES "public"."file_objects"("tenant_id","id") ON DELETE restrict ON UPDATE no action;--> statement-breakpoint
ALTER TABLE "file_access_logs" ADD CONSTRAINT "file_access_logs_actor_user_id_fk" FOREIGN KEY ("actor_user_id") REFERENCES "public"."users"("id") ON DELETE restrict ON UPDATE no action;--> statement-breakpoint
ALTER TABLE "file_access_logs" ADD CONSTRAINT "file_access_logs_actor_principal_id_fk" FOREIGN KEY ("tenant_id","actor_principal_id") REFERENCES "public"."execution_principals"("tenant_id","id") ON DELETE restrict ON UPDATE no action;--> statement-breakpoint
ALTER TABLE "file_access_logs" ADD CONSTRAINT "file_access_logs_run_id_fk" FOREIGN KEY ("tenant_id","run_id") REFERENCES "public"."agent_runs"("tenant_id","id") ON DELETE restrict ON UPDATE no action;--> statement-breakpoint
ALTER TABLE "file_deletion_requests" ADD CONSTRAINT "file_deletion_requests_tenant_id_fk" FOREIGN KEY ("tenant_id") REFERENCES "public"."tenants"("id") ON DELETE restrict ON UPDATE no action;--> statement-breakpoint
ALTER TABLE "file_deletion_requests" ADD CONSTRAINT "file_deletion_requests_file_id_fk" FOREIGN KEY ("tenant_id","file_id") REFERENCES "public"."files"("tenant_id","id") ON DELETE restrict ON UPDATE no action;--> statement-breakpoint
ALTER TABLE "file_deletion_requests" ADD CONSTRAINT "file_deletion_requests_requested_by_fk" FOREIGN KEY ("requested_by") REFERENCES "public"."users"("id") ON DELETE restrict ON UPDATE no action;--> statement-breakpoint
ALTER TABLE "file_objects" ADD CONSTRAINT "file_objects_tenant_id_fk" FOREIGN KEY ("tenant_id") REFERENCES "public"."tenants"("id") ON DELETE restrict ON UPDATE no action;--> statement-breakpoint
ALTER TABLE "file_objects" ADD CONSTRAINT "file_objects_file_id_fk" FOREIGN KEY ("tenant_id","file_id") REFERENCES "public"."files"("tenant_id","id") ON DELETE restrict ON UPDATE no action;--> statement-breakpoint
ALTER TABLE "file_objects" ADD CONSTRAINT "file_objects_location_id_fk" FOREIGN KEY ("tenant_id","location_id") REFERENCES "public"."storage_locations"("tenant_id","id") ON DELETE restrict ON UPDATE no action;--> statement-breakpoint
ALTER TABLE "file_objects" ADD CONSTRAINT "file_objects_source_object_id_fk" FOREIGN KEY ("tenant_id","source_object_id") REFERENCES "public"."file_objects"("tenant_id","id") ON DELETE restrict ON UPDATE no action;--> statement-breakpoint
ALTER TABLE "file_processing_jobs" ADD CONSTRAINT "file_processing_jobs_tenant_id_fk" FOREIGN KEY ("tenant_id") REFERENCES "public"."tenants"("id") ON DELETE restrict ON UPDATE no action;--> statement-breakpoint
ALTER TABLE "file_processing_jobs" ADD CONSTRAINT "file_processing_jobs_file_id_fk" FOREIGN KEY ("tenant_id","file_id") REFERENCES "public"."files"("tenant_id","id") ON DELETE restrict ON UPDATE no action;--> statement-breakpoint
ALTER TABLE "file_processing_jobs" ADD CONSTRAINT "file_processing_jobs_upload_id_fk" FOREIGN KEY ("tenant_id","upload_id") REFERENCES "public"."file_uploads"("tenant_id","id") ON DELETE restrict ON UPDATE no action;--> statement-breakpoint
ALTER TABLE "file_processing_jobs" ADD CONSTRAINT "file_processing_jobs_object_id_fk" FOREIGN KEY ("tenant_id","object_id") REFERENCES "public"."file_objects"("tenant_id","id") ON DELETE restrict ON UPDATE no action;--> statement-breakpoint
ALTER TABLE "file_upload_parts" ADD CONSTRAINT "file_upload_parts_tenant_id_fk" FOREIGN KEY ("tenant_id") REFERENCES "public"."tenants"("id") ON DELETE restrict ON UPDATE no action;--> statement-breakpoint
ALTER TABLE "file_upload_parts" ADD CONSTRAINT "file_upload_parts_upload_id_fk" FOREIGN KEY ("tenant_id","upload_id") REFERENCES "public"."file_uploads"("tenant_id","id") ON DELETE restrict ON UPDATE no action;--> statement-breakpoint
ALTER TABLE "file_uploads" ADD CONSTRAINT "file_uploads_tenant_id_fk" FOREIGN KEY ("tenant_id") REFERENCES "public"."tenants"("id") ON DELETE restrict ON UPDATE no action;--> statement-breakpoint
ALTER TABLE "file_uploads" ADD CONSTRAINT "file_uploads_file_id_fk" FOREIGN KEY ("tenant_id","file_id") REFERENCES "public"."files"("tenant_id","id") ON DELETE restrict ON UPDATE no action;--> statement-breakpoint
ALTER TABLE "file_uploads" ADD CONSTRAINT "file_uploads_requested_by_fk" FOREIGN KEY ("requested_by") REFERENCES "public"."users"("id") ON DELETE restrict ON UPDATE no action;--> statement-breakpoint
ALTER TABLE "file_uploads" ADD CONSTRAINT "file_uploads_location_id_fk" FOREIGN KEY ("tenant_id","location_id") REFERENCES "public"."storage_locations"("tenant_id","id") ON DELETE restrict ON UPDATE no action;--> statement-breakpoint
ALTER TABLE "file_uploads" ADD CONSTRAINT "file_uploads_result_object_id_fk" FOREIGN KEY ("tenant_id","result_object_id") REFERENCES "public"."file_objects"("tenant_id","id") ON DELETE restrict ON UPDATE no action;--> statement-breakpoint
ALTER TABLE "files" ADD CONSTRAINT "files_tenant_id_fk" FOREIGN KEY ("tenant_id") REFERENCES "public"."tenants"("id") ON DELETE restrict ON UPDATE no action;--> statement-breakpoint
ALTER TABLE "files" ADD CONSTRAINT "files_uploaded_by_fk" FOREIGN KEY ("uploaded_by") REFERENCES "public"."users"("id") ON DELETE restrict ON UPDATE no action;--> statement-breakpoint
ALTER TABLE "files" ADD CONSTRAINT "files_owner_principal_id_fk" FOREIGN KEY ("tenant_id","owner_principal_id") REFERENCES "public"."execution_principals"("tenant_id","id") ON DELETE restrict ON UPDATE no action;--> statement-breakpoint
ALTER TABLE "files" ADD CONSTRAINT "files_ticket_id_fk" FOREIGN KEY ("tenant_id","ticket_id") REFERENCES "public"."tickets"("tenant_id","id") ON DELETE restrict ON UPDATE no action;--> statement-breakpoint
ALTER TABLE "files" ADD CONSTRAINT "files_channel_id_fk" FOREIGN KEY ("tenant_id","channel_id") REFERENCES "public"."channels"("tenant_id","id") ON DELETE restrict ON UPDATE no action;--> statement-breakpoint
ALTER TABLE "files" ADD CONSTRAINT "files_document_id_fk" FOREIGN KEY ("tenant_id","document_id") REFERENCES "public"."knowledge_documents"("tenant_id","id") ON DELETE restrict ON UPDATE no action;--> statement-breakpoint
ALTER TABLE "files" ADD CONSTRAINT "files_report_id_fk" FOREIGN KEY ("tenant_id","report_id") REFERENCES "public"."report_requests"("tenant_id","id") ON DELETE restrict ON UPDATE no action;--> statement-breakpoint
ALTER TABLE "files" ADD CONSTRAINT "files_accepted_object_id_fk" FOREIGN KEY ("tenant_id","accepted_object_id") REFERENCES "public"."file_objects"("tenant_id","id") ON DELETE restrict ON UPDATE no action;--> statement-breakpoint
ALTER TABLE "incident_types" ADD CONSTRAINT "incident_types_tenant_id_fk" FOREIGN KEY ("tenant_id") REFERENCES "public"."tenants"("id") ON DELETE restrict ON UPDATE no action;--> statement-breakpoint
ALTER TABLE "incident_types" ADD CONSTRAINT "incident_types_category_id_fk" FOREIGN KEY ("tenant_id","category_id") REFERENCES "public"."service_categories"("tenant_id","id") ON DELETE restrict ON UPDATE no action;--> statement-breakpoint
ALTER TABLE "ingestion_jobs" ADD CONSTRAINT "ingestion_jobs_tenant_id_fk" FOREIGN KEY ("tenant_id") REFERENCES "public"."tenants"("id") ON DELETE restrict ON UPDATE no action;--> statement-breakpoint
ALTER TABLE "ingestion_jobs" ADD CONSTRAINT "ingestion_jobs_version_id_fk" FOREIGN KEY ("tenant_id","version_id") REFERENCES "public"."document_versions"("tenant_id","id") ON DELETE restrict ON UPDATE no action;--> statement-breakpoint
ALTER TABLE "ingestion_jobs" ADD CONSTRAINT "ingestion_jobs_embedding_model_id_fk" FOREIGN KEY ("embedding_model_id") REFERENCES "public"."embedding_models"("id") ON DELETE restrict ON UPDATE no action;--> statement-breakpoint
ALTER TABLE "intelligence_channel_mappings" ADD CONSTRAINT "intelligence_channel_mappings_user_id_fk" FOREIGN KEY ("user_id") REFERENCES "public"."users"("id") ON DELETE restrict ON UPDATE no action;--> statement-breakpoint
ALTER TABLE "intelligence_channel_mappings" ADD CONSTRAINT "intelligence_channel_mappings_channel_id_fk" FOREIGN KEY ("channel_id") REFERENCES "public"."channels"("id") ON DELETE restrict ON UPDATE no action;--> statement-breakpoint
ALTER TABLE "interruption_scopes" ADD CONSTRAINT "interruption_scopes_tenant_id_fk" FOREIGN KEY ("tenant_id") REFERENCES "public"."tenants"("id") ON DELETE restrict ON UPDATE no action;--> statement-breakpoint
ALTER TABLE "interruption_scopes" ADD CONSTRAINT "interruption_scopes_interruption_id_fk" FOREIGN KEY ("tenant_id","interruption_id") REFERENCES "public"."service_interruptions"("tenant_id","id") ON DELETE restrict ON UPDATE no action;--> statement-breakpoint
ALTER TABLE "interruption_scopes" ADD CONSTRAINT "interruption_scopes_scope_id_fk" FOREIGN KEY ("tenant_id","scope_id") REFERENCES "public"."access_scopes"("tenant_id","id") ON DELETE restrict ON UPDATE no action;--> statement-breakpoint
ALTER TABLE "invoice_lines" ADD CONSTRAINT "invoice_lines_tenant_id_fk" FOREIGN KEY ("tenant_id") REFERENCES "public"."tenants"("id") ON DELETE restrict ON UPDATE no action;--> statement-breakpoint
ALTER TABLE "invoice_lines" ADD CONSTRAINT "invoice_lines_invoice_id_fk" FOREIGN KEY ("tenant_id","invoice_id") REFERENCES "public"."invoices"("tenant_id","id") ON DELETE restrict ON UPDATE no action;--> statement-breakpoint
ALTER TABLE "invoice_lines" ADD CONSTRAINT "invoice_lines_category_id_fk" FOREIGN KEY ("tenant_id","category_id") REFERENCES "public"."service_categories"("tenant_id","id") ON DELETE restrict ON UPDATE no action;--> statement-breakpoint
ALTER TABLE "invoices" ADD CONSTRAINT "invoices_tenant_id_fk" FOREIGN KEY ("tenant_id") REFERENCES "public"."tenants"("id") ON DELETE restrict ON UPDATE no action;--> statement-breakpoint
ALTER TABLE "invoices" ADD CONSTRAINT "invoices_ticket_id_fk" FOREIGN KEY ("tenant_id","ticket_id") REFERENCES "public"."tickets"("tenant_id","id") ON DELETE restrict ON UPDATE no action;--> statement-breakpoint
ALTER TABLE "invoices" ADD CONSTRAINT "invoices_work_order_id_fk" FOREIGN KEY ("tenant_id","work_order_id") REFERENCES "public"."work_orders"("tenant_id","id") ON DELETE restrict ON UPDATE no action;--> statement-breakpoint
ALTER TABLE "invoices" ADD CONSTRAINT "invoices_issued_by_staff_id_fk" FOREIGN KEY ("tenant_id","issued_by_staff_id") REFERENCES "public"."staff_profiles"("tenant_id","id") ON DELETE restrict ON UPDATE no action;--> statement-breakpoint
ALTER TABLE "invoices" ADD CONSTRAINT "invoices_bill_to_user_id_fk" FOREIGN KEY ("bill_to_user_id") REFERENCES "public"."users"("id") ON DELETE restrict ON UPDATE no action;--> statement-breakpoint
ALTER TABLE "invoices" ADD CONSTRAINT "invoices_legal_invoice_file_id_fk" FOREIGN KEY ("tenant_id","legal_invoice_file_id") REFERENCES "public"."files"("tenant_id","id") ON DELETE restrict ON UPDATE no action;--> statement-breakpoint
ALTER TABLE "invoices" ADD CONSTRAINT "invoices_supersedes_invoice_id_fk" FOREIGN KEY ("tenant_id","supersedes_invoice_id") REFERENCES "public"."invoices"("tenant_id","id") ON DELETE restrict ON UPDATE no action;--> statement-breakpoint
ALTER TABLE "knowledge_bases" ADD CONSTRAINT "knowledge_bases_tenant_id_fk" FOREIGN KEY ("tenant_id") REFERENCES "public"."tenants"("id") ON DELETE restrict ON UPDATE no action;--> statement-breakpoint
ALTER TABLE "knowledge_bases" ADD CONSTRAINT "knowledge_bases_domain_id_fk" FOREIGN KEY ("tenant_id","domain_id") REFERENCES "public"."domains"("tenant_id","id") ON DELETE restrict ON UPDATE no action;--> statement-breakpoint
ALTER TABLE "knowledge_categories" ADD CONSTRAINT "knowledge_categories_tenant_id_fk" FOREIGN KEY ("tenant_id") REFERENCES "public"."tenants"("id") ON DELETE restrict ON UPDATE no action;--> statement-breakpoint
ALTER TABLE "knowledge_categories" ADD CONSTRAINT "knowledge_categories_parent_id_fk" FOREIGN KEY ("tenant_id","parent_id") REFERENCES "public"."knowledge_categories"("tenant_id","id") ON DELETE restrict ON UPDATE no action;--> statement-breakpoint
ALTER TABLE "knowledge_chunks" ADD CONSTRAINT "knowledge_chunks_tenant_id_fk" FOREIGN KEY ("tenant_id") REFERENCES "public"."tenants"("id") ON DELETE restrict ON UPDATE no action;--> statement-breakpoint
ALTER TABLE "knowledge_chunks" ADD CONSTRAINT "knowledge_chunks_version_id_fk" FOREIGN KEY ("tenant_id","version_id") REFERENCES "public"."document_versions"("tenant_id","id") ON DELETE restrict ON UPDATE no action;--> statement-breakpoint
ALTER TABLE "knowledge_documents" ADD CONSTRAINT "knowledge_documents_tenant_id_fk" FOREIGN KEY ("tenant_id") REFERENCES "public"."tenants"("id") ON DELETE restrict ON UPDATE no action;--> statement-breakpoint
ALTER TABLE "knowledge_documents" ADD CONSTRAINT "knowledge_documents_knowledge_base_id_fk" FOREIGN KEY ("tenant_id","knowledge_base_id") REFERENCES "public"."knowledge_bases"("tenant_id","id") ON DELETE restrict ON UPDATE no action;--> statement-breakpoint
ALTER TABLE "knowledge_documents" ADD CONSTRAINT "knowledge_documents_category_id_fk" FOREIGN KEY ("tenant_id","category_id") REFERENCES "public"."knowledge_categories"("tenant_id","id") ON DELETE restrict ON UPDATE no action;--> statement-breakpoint
ALTER TABLE "knowledge_documents" ADD CONSTRAINT "knowledge_documents_owner_management_id_fk" FOREIGN KEY ("tenant_id","owner_management_id") REFERENCES "public"."management_units"("tenant_id","id") ON DELETE restrict ON UPDATE no action;--> statement-breakpoint
ALTER TABLE "knowledge_documents" ADD CONSTRAINT "knowledge_documents_active_version_id_fk" FOREIGN KEY ("tenant_id","active_version_id") REFERENCES "public"."document_versions"("tenant_id","id") ON DELETE restrict ON UPDATE no action;--> statement-breakpoint
ALTER TABLE "knowledge_documents" ADD CONSTRAINT "knowledge_documents_memory_namespace_id_fk" FOREIGN KEY ("tenant_id","memory_namespace_id") REFERENCES "public"."memory_namespaces"("tenant_id","id") ON DELETE restrict ON UPDATE no action;--> statement-breakpoint
ALTER TABLE "knowledge_embeddings" ADD CONSTRAINT "knowledge_embeddings_tenant_id_fk" FOREIGN KEY ("tenant_id") REFERENCES "public"."tenants"("id") ON DELETE restrict ON UPDATE no action;--> statement-breakpoint
ALTER TABLE "knowledge_embeddings" ADD CONSTRAINT "knowledge_embeddings_chunk_id_fk" FOREIGN KEY ("tenant_id","chunk_id") REFERENCES "public"."knowledge_chunks"("tenant_id","id") ON DELETE restrict ON UPDATE no action;--> statement-breakpoint
ALTER TABLE "knowledge_embeddings" ADD CONSTRAINT "knowledge_embeddings_model_id_fk" FOREIGN KEY ("model_id") REFERENCES "public"."embedding_models"("id") ON DELETE restrict ON UPDATE no action;--> statement-breakpoint
ALTER TABLE "knowledge_reviews" ADD CONSTRAINT "knowledge_reviews_tenant_id_fk" FOREIGN KEY ("tenant_id") REFERENCES "public"."tenants"("id") ON DELETE restrict ON UPDATE no action;--> statement-breakpoint
ALTER TABLE "knowledge_reviews" ADD CONSTRAINT "knowledge_reviews_document_version_id_fk" FOREIGN KEY ("tenant_id","document_version_id") REFERENCES "public"."document_versions"("tenant_id","id") ON DELETE restrict ON UPDATE no action;--> statement-breakpoint
ALTER TABLE "knowledge_reviews" ADD CONSTRAINT "knowledge_reviews_memory_candidate_id_fk" FOREIGN KEY ("tenant_id","memory_candidate_id") REFERENCES "public"."memory_candidates"("tenant_id","id") ON DELETE restrict ON UPDATE no action;--> statement-breakpoint
ALTER TABLE "knowledge_reviews" ADD CONSTRAINT "knowledge_reviews_reviewer_user_id_fk" FOREIGN KEY ("reviewer_user_id") REFERENCES "public"."users"("id") ON DELETE restrict ON UPDATE no action;--> statement-breakpoint
ALTER TABLE "mailbox_deliveries" ADD CONSTRAINT "mailbox_deliveries_tenant_id_fk" FOREIGN KEY ("tenant_id") REFERENCES "public"."tenants"("id") ON DELETE restrict ON UPDATE no action;--> statement-breakpoint
ALTER TABLE "mailbox_deliveries" ADD CONSTRAINT "mailbox_deliveries_mailbox_id_fk" FOREIGN KEY ("tenant_id","mailbox_id") REFERENCES "public"."team_mailbox"("tenant_id","id") ON DELETE restrict ON UPDATE no action;--> statement-breakpoint
ALTER TABLE "mailbox_deliveries" ADD CONSTRAINT "mailbox_deliveries_recipient_member_id_fk" FOREIGN KEY ("tenant_id","recipient_member_id") REFERENCES "public"."team_members"("tenant_id","id") ON DELETE restrict ON UPDATE no action;--> statement-breakpoint
ALTER TABLE "management_coverage" ADD CONSTRAINT "management_coverage_tenant_id_fk" FOREIGN KEY ("tenant_id") REFERENCES "public"."tenants"("id") ON DELETE restrict ON UPDATE no action;--> statement-breakpoint
ALTER TABLE "management_coverage" ADD CONSTRAINT "management_coverage_management_unit_id_fk" FOREIGN KEY ("tenant_id","management_unit_id") REFERENCES "public"."management_units"("tenant_id","id") ON DELETE restrict ON UPDATE no action;--> statement-breakpoint
ALTER TABLE "management_coverage" ADD CONSTRAINT "management_coverage_scope_id_fk" FOREIGN KEY ("tenant_id","scope_id") REFERENCES "public"."access_scopes"("tenant_id","id") ON DELETE restrict ON UPDATE no action;--> statement-breakpoint
ALTER TABLE "management_coverage" ADD CONSTRAINT "management_coverage_service_category_id_fk" FOREIGN KEY ("tenant_id","service_category_id") REFERENCES "public"."service_categories"("tenant_id","id") ON DELETE restrict ON UPDATE no action;--> statement-breakpoint
ALTER TABLE "management_units" ADD CONSTRAINT "management_units_tenant_id_fk" FOREIGN KEY ("tenant_id") REFERENCES "public"."tenants"("id") ON DELETE restrict ON UPDATE no action;--> statement-breakpoint
ALTER TABLE "mcp_servers" ADD CONSTRAINT "mcp_servers_credential_id_fk" FOREIGN KEY ("credential_id") REFERENCES "public"."credentials"("id") ON DELETE restrict ON UPDATE no action;--> statement-breakpoint
ALTER TABLE "mcp_servers" ADD CONSTRAINT "mcp_servers_tenant_id_fk" FOREIGN KEY ("tenant_id") REFERENCES "public"."tenants"("id") ON DELETE restrict ON UPDATE no action;--> statement-breakpoint
ALTER TABLE "mcp_servers" ADD CONSTRAINT "mcp_servers_workspace_id_fk" FOREIGN KEY ("tenant_id","workspace_id") REFERENCES "public"."workspaces"("tenant_id","id") ON DELETE restrict ON UPDATE no action;--> statement-breakpoint
ALTER TABLE "mcp_tools" ADD CONSTRAINT "mcp_tools_server_id_fk" FOREIGN KEY ("tenant_id","server_id") REFERENCES "public"."mcp_servers"("tenant_id","id") ON DELETE restrict ON UPDATE no action;--> statement-breakpoint
ALTER TABLE "mcp_tools" ADD CONSTRAINT "mcp_tools_tenant_id_fk" FOREIGN KEY ("tenant_id") REFERENCES "public"."tenants"("id") ON DELETE restrict ON UPDATE no action;--> statement-breakpoint
ALTER TABLE "mcp_user_credentials" ADD CONSTRAINT "mcp_user_credentials_server_id_fk" FOREIGN KEY ("tenant_id","server_id") REFERENCES "public"."mcp_servers"("tenant_id","id") ON DELETE restrict ON UPDATE no action;--> statement-breakpoint
ALTER TABLE "mcp_user_credentials" ADD CONSTRAINT "mcp_user_credentials_user_id_fk" FOREIGN KEY ("user_id") REFERENCES "public"."users"("id") ON DELETE restrict ON UPDATE no action;--> statement-breakpoint
ALTER TABLE "mcp_user_credentials" ADD CONSTRAINT "mcp_user_credentials_credential_id_fk" FOREIGN KEY ("credential_id") REFERENCES "public"."credentials"("id") ON DELETE restrict ON UPDATE no action;--> statement-breakpoint
ALTER TABLE "mcp_user_credentials" ADD CONSTRAINT "mcp_user_credentials_tenant_id_fk" FOREIGN KEY ("tenant_id") REFERENCES "public"."tenants"("id") ON DELETE restrict ON UPDATE no action;--> statement-breakpoint
ALTER TABLE "memory_candidates" ADD CONSTRAINT "memory_candidates_tenant_id_fk" FOREIGN KEY ("tenant_id") REFERENCES "public"."tenants"("id") ON DELETE restrict ON UPDATE no action;--> statement-breakpoint
ALTER TABLE "memory_candidates" ADD CONSTRAINT "memory_candidates_source_ticket_id_fk" FOREIGN KEY ("tenant_id","source_ticket_id") REFERENCES "public"."tickets"("tenant_id","id") ON DELETE restrict ON UPDATE no action;--> statement-breakpoint
ALTER TABLE "memory_candidates" ADD CONSTRAINT "memory_candidates_source_run_id_fk" FOREIGN KEY ("tenant_id","source_run_id") REFERENCES "public"."agent_runs"("tenant_id","id") ON DELETE restrict ON UPDATE no action;--> statement-breakpoint
ALTER TABLE "memory_candidates" ADD CONSTRAINT "memory_candidates_scope_id_fk" FOREIGN KEY ("tenant_id","scope_id") REFERENCES "public"."access_scopes"("tenant_id","id") ON DELETE restrict ON UPDATE no action;--> statement-breakpoint
ALTER TABLE "memory_candidates" ADD CONSTRAINT "memory_candidates_proposed_by_agent_id_fk" FOREIGN KEY ("tenant_id","proposed_by_agent_id") REFERENCES "public"."agents"("tenant_id","id") ON DELETE restrict ON UPDATE no action;--> statement-breakpoint
ALTER TABLE "memory_candidates" ADD CONSTRAINT "memory_candidates_namespace_id_fk" FOREIGN KEY ("tenant_id","namespace_id") REFERENCES "public"."memory_namespaces"("tenant_id","id") ON DELETE restrict ON UPDATE no action;--> statement-breakpoint
ALTER TABLE "memory_candidates" ADD CONSTRAINT "memory_candidates_source_binding_id_fk" FOREIGN KEY ("tenant_id","source_binding_id") REFERENCES "public"."runtime_session_bindings"("tenant_id","id") ON DELETE restrict ON UPDATE no action;--> statement-breakpoint
ALTER TABLE "memory_candidates" ADD CONSTRAINT "memory_candidates_subject_user_id_fk" FOREIGN KEY ("subject_user_id") REFERENCES "public"."users"("id") ON DELETE restrict ON UPDATE no action;--> statement-breakpoint
ALTER TABLE "memory_candidates" ADD CONSTRAINT "memory_candidates_supersedes_candidate_id_fk" FOREIGN KEY ("tenant_id","supersedes_candidate_id") REFERENCES "public"."memory_candidates"("tenant_id","id") ON DELETE restrict ON UPDATE no action;--> statement-breakpoint
ALTER TABLE "memory_namespaces" ADD CONSTRAINT "memory_namespaces_tenant_id_fk" FOREIGN KEY ("tenant_id") REFERENCES "public"."tenants"("id") ON DELETE restrict ON UPDATE no action;--> statement-breakpoint
ALTER TABLE "memory_namespaces" ADD CONSTRAINT "memory_namespaces_owner_principal_id_fk" FOREIGN KEY ("tenant_id","owner_principal_id") REFERENCES "public"."execution_principals"("tenant_id","id") ON DELETE restrict ON UPDATE no action;--> statement-breakpoint
ALTER TABLE "memory_namespaces" ADD CONSTRAINT "memory_namespaces_workspace_id_fk" FOREIGN KEY ("tenant_id","workspace_id") REFERENCES "public"."workspaces"("tenant_id","id") ON DELETE restrict ON UPDATE no action;--> statement-breakpoint
ALTER TABLE "memory_namespaces" ADD CONSTRAINT "memory_namespaces_team_id_fk" FOREIGN KEY ("tenant_id","team_id") REFERENCES "public"."agent_teams"("tenant_id","id") ON DELETE restrict ON UPDATE no action;--> statement-breakpoint
ALTER TABLE "memory_publications" ADD CONSTRAINT "memory_publications_tenant_id_fk" FOREIGN KEY ("tenant_id") REFERENCES "public"."tenants"("id") ON DELETE restrict ON UPDATE no action;--> statement-breakpoint
ALTER TABLE "memory_publications" ADD CONSTRAINT "memory_publications_candidate_id_fk" FOREIGN KEY ("tenant_id","candidate_id") REFERENCES "public"."memory_candidates"("tenant_id","id") ON DELETE restrict ON UPDATE no action;--> statement-breakpoint
ALTER TABLE "memory_publications" ADD CONSTRAINT "memory_publications_approval_review_id_fk" FOREIGN KEY ("tenant_id","approval_review_id") REFERENCES "public"."knowledge_reviews"("tenant_id","id") ON DELETE restrict ON UPDATE no action;--> statement-breakpoint
ALTER TABLE "memory_publications" ADD CONSTRAINT "memory_publications_document_id_fk" FOREIGN KEY ("tenant_id","document_id") REFERENCES "public"."knowledge_documents"("tenant_id","id") ON DELETE restrict ON UPDATE no action;--> statement-breakpoint
ALTER TABLE "memory_publications" ADD CONSTRAINT "memory_publications_version_id_fk" FOREIGN KEY ("tenant_id","version_id") REFERENCES "public"."document_versions"("tenant_id","id") ON DELETE restrict ON UPDATE no action;--> statement-breakpoint
ALTER TABLE "memory_publications" ADD CONSTRAINT "memory_publications_namespace_id_fk" FOREIGN KEY ("tenant_id","namespace_id") REFERENCES "public"."memory_namespaces"("tenant_id","id") ON DELETE restrict ON UPDATE no action;--> statement-breakpoint
ALTER TABLE "message_files" ADD CONSTRAINT "message_files_tenant_id_fk" FOREIGN KEY ("tenant_id") REFERENCES "public"."tenants"("id") ON DELETE restrict ON UPDATE no action;--> statement-breakpoint
ALTER TABLE "message_files" ADD CONSTRAINT "message_files_message_id_fk" FOREIGN KEY ("tenant_id","message_id") REFERENCES "public"."messages"("tenant_id","id") ON DELETE restrict ON UPDATE no action;--> statement-breakpoint
ALTER TABLE "message_files" ADD CONSTRAINT "message_files_file_id_fk" FOREIGN KEY ("tenant_id","file_id") REFERENCES "public"."files"("tenant_id","id") ON DELETE restrict ON UPDATE no action;--> statement-breakpoint
ALTER TABLE "message_mentions" ADD CONSTRAINT "message_mentions_tenant_id_fk" FOREIGN KEY ("tenant_id") REFERENCES "public"."tenants"("id") ON DELETE restrict ON UPDATE no action;--> statement-breakpoint
ALTER TABLE "message_mentions" ADD CONSTRAINT "message_mentions_message_id_fk" FOREIGN KEY ("tenant_id","message_id") REFERENCES "public"."messages"("tenant_id","id") ON DELETE restrict ON UPDATE no action;--> statement-breakpoint
ALTER TABLE "message_mentions" ADD CONSTRAINT "message_mentions_agent_id_fk" FOREIGN KEY ("tenant_id","agent_id") REFERENCES "public"."agents"("tenant_id","id") ON DELETE restrict ON UPDATE no action;--> statement-breakpoint
ALTER TABLE "message_mentions" ADD CONSTRAINT "message_mentions_requested_by_fk" FOREIGN KEY ("requested_by") REFERENCES "public"."users"("id") ON DELETE restrict ON UPDATE no action;--> statement-breakpoint
ALTER TABLE "message_mentions" ADD CONSTRAINT "message_mentions_resolved_run_id_fk" FOREIGN KEY ("tenant_id","resolved_run_id") REFERENCES "public"."agent_runs"("tenant_id","id") ON DELETE restrict ON UPDATE no action;--> statement-breakpoint
ALTER TABLE "messages" ADD CONSTRAINT "messages_tenant_id_fk" FOREIGN KEY ("tenant_id") REFERENCES "public"."tenants"("id") ON DELETE restrict ON UPDATE no action;--> statement-breakpoint
ALTER TABLE "messages" ADD CONSTRAINT "messages_channel_id_fk" FOREIGN KEY ("tenant_id","channel_id") REFERENCES "public"."channels"("tenant_id","id") ON DELETE restrict ON UPDATE no action;--> statement-breakpoint
ALTER TABLE "messages" ADD CONSTRAINT "messages_sender_user_id_fk" FOREIGN KEY ("sender_user_id") REFERENCES "public"."users"("id") ON DELETE restrict ON UPDATE no action;--> statement-breakpoint
ALTER TABLE "messages" ADD CONSTRAINT "messages_sender_agent_id_fk" FOREIGN KEY ("tenant_id","sender_agent_id") REFERENCES "public"."agents"("tenant_id","id") ON DELETE restrict ON UPDATE no action;--> statement-breakpoint
ALTER TABLE "messages" ADD CONSTRAINT "messages_run_id_fk" FOREIGN KEY ("tenant_id","run_id") REFERENCES "public"."agent_runs"("tenant_id","id") ON DELETE restrict ON UPDATE no action;--> statement-breakpoint
ALTER TABLE "messages" ADD CONSTRAINT "messages_reply_to_id_fk" FOREIGN KEY ("tenant_id","reply_to_id") REFERENCES "public"."messages"("tenant_id","id") ON DELETE restrict ON UPDATE no action;--> statement-breakpoint
ALTER TABLE "messages" ADD CONSTRAINT "messages_source_event_id_fk" FOREIGN KEY ("tenant_id","source_event_id") REFERENCES "public"."ticket_events"("tenant_id","id") ON DELETE restrict ON UPDATE no action;--> statement-breakpoint
ALTER TABLE "model_profiles" ADD CONSTRAINT "model_profiles_tenant_id_fk" FOREIGN KEY ("tenant_id") REFERENCES "public"."tenants"("id") ON DELETE restrict ON UPDATE no action;--> statement-breakpoint
ALTER TABLE "model_profiles" ADD CONSTRAINT "model_profiles_workspace_id_fk" FOREIGN KEY ("tenant_id","workspace_id") REFERENCES "public"."workspaces"("tenant_id","id") ON DELETE restrict ON UPDATE no action;--> statement-breakpoint
ALTER TABLE "model_profiles" ADD CONSTRAINT "model_profiles_credential_id_fk" FOREIGN KEY ("credential_id") REFERENCES "public"."credentials"("id") ON DELETE restrict ON UPDATE no action;--> statement-breakpoint
ALTER TABLE "notification_deliveries" ADD CONSTRAINT "notification_deliveries_tenant_id_fk" FOREIGN KEY ("tenant_id") REFERENCES "public"."tenants"("id") ON DELETE restrict ON UPDATE no action;--> statement-breakpoint
ALTER TABLE "notification_deliveries" ADD CONSTRAINT "notification_deliveries_user_id_fk" FOREIGN KEY ("user_id") REFERENCES "public"."users"("id") ON DELETE restrict ON UPDATE no action;--> statement-breakpoint
ALTER TABLE "notification_deliveries" ADD CONSTRAINT "notification_deliveries_ticket_event_id_fk" FOREIGN KEY ("tenant_id","ticket_event_id") REFERENCES "public"."ticket_events"("tenant_id","id") ON DELETE restrict ON UPDATE no action;--> statement-breakpoint
ALTER TABLE "notification_deliveries" ADD CONSTRAINT "notification_deliveries_message_id_fk" FOREIGN KEY ("tenant_id","message_id") REFERENCES "public"."messages"("tenant_id","id") ON DELETE restrict ON UPDATE no action;--> statement-breakpoint
ALTER TABLE "notification_deliveries" ADD CONSTRAINT "notification_deliveries_interruption_id_fk" FOREIGN KEY ("tenant_id","interruption_id") REFERENCES "public"."service_interruptions"("tenant_id","id") ON DELETE restrict ON UPDATE no action;--> statement-breakpoint
ALTER TABLE "payment_allocations" ADD CONSTRAINT "payment_allocations_tenant_id_fk" FOREIGN KEY ("tenant_id") REFERENCES "public"."tenants"("id") ON DELETE restrict ON UPDATE no action;--> statement-breakpoint
ALTER TABLE "payment_allocations" ADD CONSTRAINT "payment_allocations_payment_id_fk" FOREIGN KEY ("tenant_id","payment_id") REFERENCES "public"."payments"("tenant_id","id") ON DELETE restrict ON UPDATE no action;--> statement-breakpoint
ALTER TABLE "payment_allocations" ADD CONSTRAINT "payment_allocations_invoice_id_fk" FOREIGN KEY ("tenant_id","invoice_id") REFERENCES "public"."invoices"("tenant_id","id") ON DELETE restrict ON UPDATE no action;--> statement-breakpoint
ALTER TABLE "payment_intents" ADD CONSTRAINT "payment_intents_tenant_id_fk" FOREIGN KEY ("tenant_id") REFERENCES "public"."tenants"("id") ON DELETE restrict ON UPDATE no action;--> statement-breakpoint
ALTER TABLE "payment_intents" ADD CONSTRAINT "payment_intents_invoice_id_fk" FOREIGN KEY ("tenant_id","invoice_id") REFERENCES "public"."invoices"("tenant_id","id") ON DELETE restrict ON UPDATE no action;--> statement-breakpoint
ALTER TABLE "payment_webhook_receipts" ADD CONSTRAINT "payment_webhook_receipts_tenant_id_fk" FOREIGN KEY ("tenant_id") REFERENCES "public"."tenants"("id") ON DELETE restrict ON UPDATE no action;--> statement-breakpoint
ALTER TABLE "payment_webhook_receipts" ADD CONSTRAINT "payment_webhook_receipts_intent_id_fk" FOREIGN KEY ("tenant_id","intent_id") REFERENCES "public"."payment_intents"("tenant_id","id") ON DELETE restrict ON UPDATE no action;--> statement-breakpoint
ALTER TABLE "payments" ADD CONSTRAINT "payments_tenant_id_fk" FOREIGN KEY ("tenant_id") REFERENCES "public"."tenants"("id") ON DELETE restrict ON UPDATE no action;--> statement-breakpoint
ALTER TABLE "payments" ADD CONSTRAINT "payments_invoice_id_fk" FOREIGN KEY ("tenant_id","invoice_id") REFERENCES "public"."invoices"("tenant_id","id") ON DELETE restrict ON UPDATE no action;--> statement-breakpoint
ALTER TABLE "payments" ADD CONSTRAINT "payments_intent_id_fk" FOREIGN KEY ("tenant_id","intent_id") REFERENCES "public"."payment_intents"("tenant_id","id") ON DELETE restrict ON UPDATE no action;--> statement-breakpoint
ALTER TABLE "payments" ADD CONSTRAINT "payments_receipt_id_fk" FOREIGN KEY ("tenant_id","receipt_id") REFERENCES "public"."payment_webhook_receipts"("tenant_id","id") ON DELETE restrict ON UPDATE no action;--> statement-breakpoint
ALTER TABLE "platform_admins" ADD CONSTRAINT "platform_admins_user_id_fk" FOREIGN KEY ("user_id") REFERENCES "public"."users"("id") ON DELETE restrict ON UPDATE no action;--> statement-breakpoint
ALTER TABLE "platform_admins" ADD CONSTRAINT "platform_admins_granted_by_fk" FOREIGN KEY ("granted_by") REFERENCES "public"."users"("id") ON DELETE restrict ON UPDATE no action;--> statement-breakpoint
ALTER TABLE "plugin_grants" ADD CONSTRAINT "plugin_grants_agent_id_fk" FOREIGN KEY ("tenant_id","agent_id") REFERENCES "public"."agents"("tenant_id","id") ON DELETE restrict ON UPDATE no action;--> statement-breakpoint
ALTER TABLE "plugin_grants" ADD CONSTRAINT "plugin_grants_tenant_id_fk" FOREIGN KEY ("tenant_id") REFERENCES "public"."tenants"("id") ON DELETE restrict ON UPDATE no action;--> statement-breakpoint
ALTER TABLE "reception_sessions" ADD CONSTRAINT "reception_sessions_tenant_id_fk" FOREIGN KEY ("tenant_id") REFERENCES "public"."tenants"("id") ON DELETE restrict ON UPDATE no action;--> statement-breakpoint
ALTER TABLE "reception_sessions" ADD CONSTRAINT "reception_sessions_channel_id_fk" FOREIGN KEY ("tenant_id","channel_id") REFERENCES "public"."channels"("tenant_id","id") ON DELETE restrict ON UPDATE no action;--> statement-breakpoint
ALTER TABLE "reception_sessions" ADD CONSTRAINT "reception_sessions_customer_user_id_fk" FOREIGN KEY ("customer_user_id") REFERENCES "public"."users"("id") ON DELETE restrict ON UPDATE no action;--> statement-breakpoint
ALTER TABLE "reception_sessions" ADD CONSTRAINT "reception_sessions_system_agent_id_fk" FOREIGN KEY ("tenant_id","system_agent_id") REFERENCES "public"."agents"("tenant_id","id") ON DELETE restrict ON UPDATE no action;--> statement-breakpoint
ALTER TABLE "reception_sessions" ADD CONSTRAINT "reception_sessions_binding_id_fk" FOREIGN KEY ("tenant_id","binding_id") REFERENCES "public"."runtime_session_bindings"("tenant_id","id") ON DELETE restrict ON UPDATE no action;--> statement-breakpoint
ALTER TABLE "reception_waits" ADD CONSTRAINT "reception_waits_tenant_id_fk" FOREIGN KEY ("tenant_id") REFERENCES "public"."tenants"("id") ON DELETE restrict ON UPDATE no action;--> statement-breakpoint
ALTER TABLE "reception_waits" ADD CONSTRAINT "reception_waits_session_id_fk" FOREIGN KEY ("tenant_id","session_id") REFERENCES "public"."reception_sessions"("tenant_id","id") ON DELETE restrict ON UPDATE no action;--> statement-breakpoint
ALTER TABLE "reception_waits" ADD CONSTRAINT "reception_waits_ticket_id_fk" FOREIGN KEY ("tenant_id","ticket_id") REFERENCES "public"."tickets"("tenant_id","id") ON DELETE restrict ON UPDATE no action;--> statement-breakpoint
ALTER TABLE "reception_waits" ADD CONSTRAINT "reception_waits_resumed_event_id_fk" FOREIGN KEY ("tenant_id","resumed_event_id") REFERENCES "public"."ticket_events"("tenant_id","id") ON DELETE restrict ON UPDATE no action;--> statement-breakpoint
ALTER TABLE "reception_waits" ADD CONSTRAINT "reception_waits_operation_id_fk" FOREIGN KEY ("tenant_id","operation_id") REFERENCES "public"."runtime_session_operations"("tenant_id","id") ON DELETE restrict ON UPDATE no action;--> statement-breakpoint
ALTER TABLE "refund_allocations" ADD CONSTRAINT "refund_allocations_tenant_id_fk" FOREIGN KEY ("tenant_id") REFERENCES "public"."tenants"("id") ON DELETE restrict ON UPDATE no action;--> statement-breakpoint
ALTER TABLE "refund_allocations" ADD CONSTRAINT "refund_allocations_refund_id_fk" FOREIGN KEY ("tenant_id","refund_id") REFERENCES "public"."refunds"("tenant_id","id") ON DELETE restrict ON UPDATE no action;--> statement-breakpoint
ALTER TABLE "refund_allocations" ADD CONSTRAINT "refund_allocations_payment_allocation_id_fk" FOREIGN KEY ("tenant_id","payment_allocation_id") REFERENCES "public"."payment_allocations"("tenant_id","id") ON DELETE restrict ON UPDATE no action;--> statement-breakpoint
ALTER TABLE "refunds" ADD CONSTRAINT "refunds_tenant_id_fk" FOREIGN KEY ("tenant_id") REFERENCES "public"."tenants"("id") ON DELETE restrict ON UPDATE no action;--> statement-breakpoint
ALTER TABLE "refunds" ADD CONSTRAINT "refunds_payment_id_fk" FOREIGN KEY ("tenant_id","payment_id") REFERENCES "public"."payments"("tenant_id","id") ON DELETE restrict ON UPDATE no action;--> statement-breakpoint
ALTER TABLE "refunds" ADD CONSTRAINT "refunds_requested_by_fk" FOREIGN KEY ("requested_by") REFERENCES "public"."users"("id") ON DELETE restrict ON UPDATE no action;--> statement-breakpoint
ALTER TABLE "refunds" ADD CONSTRAINT "refunds_approved_by_fk" FOREIGN KEY ("approved_by") REFERENCES "public"."users"("id") ON DELETE restrict ON UPDATE no action;--> statement-breakpoint
ALTER TABLE "report_requests" ADD CONSTRAINT "report_requests_tenant_id_fk" FOREIGN KEY ("tenant_id") REFERENCES "public"."tenants"("id") ON DELETE restrict ON UPDATE no action;--> statement-breakpoint
ALTER TABLE "report_requests" ADD CONSTRAINT "report_requests_workspace_id_fk" FOREIGN KEY ("tenant_id","workspace_id") REFERENCES "public"."workspaces"("tenant_id","id") ON DELETE restrict ON UPDATE no action;--> statement-breakpoint
ALTER TABLE "report_requests" ADD CONSTRAINT "report_requests_requested_by_fk" FOREIGN KEY ("requested_by") REFERENCES "public"."users"("id") ON DELETE restrict ON UPDATE no action;--> statement-breakpoint
ALTER TABLE "report_requests" ADD CONSTRAINT "report_requests_channel_id_fk" FOREIGN KEY ("tenant_id","channel_id") REFERENCES "public"."channels"("tenant_id","id") ON DELETE restrict ON UPDATE no action;--> statement-breakpoint
ALTER TABLE "report_requests" ADD CONSTRAINT "report_requests_source_message_id_fk" FOREIGN KEY ("tenant_id","source_message_id") REFERENCES "public"."messages"("tenant_id","id") ON DELETE restrict ON UPDATE no action;--> statement-breakpoint
ALTER TABLE "report_requests" ADD CONSTRAINT "report_requests_scope_id_fk" FOREIGN KEY ("tenant_id","scope_id") REFERENCES "public"."access_scopes"("tenant_id","id") ON DELETE restrict ON UPDATE no action;--> statement-breakpoint
ALTER TABLE "report_requests" ADD CONSTRAINT "report_requests_run_id_fk" FOREIGN KEY ("tenant_id","run_id") REFERENCES "public"."agent_runs"("tenant_id","id") ON DELETE restrict ON UPDATE no action;--> statement-breakpoint
ALTER TABLE "report_requests" ADD CONSTRAINT "report_requests_result_file_id_fk" FOREIGN KEY ("tenant_id","result_file_id") REFERENCES "public"."files"("tenant_id","id") ON DELETE restrict ON UPDATE no action;--> statement-breakpoint
ALTER TABLE "report_sources" ADD CONSTRAINT "report_sources_tenant_id_fk" FOREIGN KEY ("tenant_id") REFERENCES "public"."tenants"("id") ON DELETE restrict ON UPDATE no action;--> statement-breakpoint
ALTER TABLE "report_sources" ADD CONSTRAINT "report_sources_report_id_fk" FOREIGN KEY ("tenant_id","report_id") REFERENCES "public"."report_requests"("tenant_id","id") ON DELETE restrict ON UPDATE no action;--> statement-breakpoint
ALTER TABLE "report_sources" ADD CONSTRAINT "report_sources_snapshot_file_id_fk" FOREIGN KEY ("tenant_id","snapshot_file_id") REFERENCES "public"."files"("tenant_id","id") ON DELETE restrict ON UPDATE no action;--> statement-breakpoint
ALTER TABLE "retrieval_hits" ADD CONSTRAINT "retrieval_hits_tenant_id_fk" FOREIGN KEY ("tenant_id") REFERENCES "public"."tenants"("id") ON DELETE restrict ON UPDATE no action;--> statement-breakpoint
ALTER TABLE "retrieval_hits" ADD CONSTRAINT "retrieval_hits_retrieval_run_id_fk" FOREIGN KEY ("tenant_id","retrieval_run_id") REFERENCES "public"."retrieval_runs"("tenant_id","id") ON DELETE restrict ON UPDATE no action;--> statement-breakpoint
ALTER TABLE "retrieval_hits" ADD CONSTRAINT "retrieval_hits_chunk_id_fk" FOREIGN KEY ("tenant_id","chunk_id") REFERENCES "public"."knowledge_chunks"("tenant_id","id") ON DELETE restrict ON UPDATE no action;--> statement-breakpoint
ALTER TABLE "retrieval_runs" ADD CONSTRAINT "retrieval_runs_tenant_id_fk" FOREIGN KEY ("tenant_id") REFERENCES "public"."tenants"("id") ON DELETE restrict ON UPDATE no action;--> statement-breakpoint
ALTER TABLE "retrieval_runs" ADD CONSTRAINT "retrieval_runs_agent_run_id_fk" FOREIGN KEY ("tenant_id","agent_run_id") REFERENCES "public"."agent_runs"("tenant_id","id") ON DELETE restrict ON UPDATE no action;--> statement-breakpoint
ALTER TABLE "retrieval_runs" ADD CONSTRAINT "retrieval_runs_actor_user_id_fk" FOREIGN KEY ("actor_user_id") REFERENCES "public"."users"("id") ON DELETE restrict ON UPDATE no action;--> statement-breakpoint
ALTER TABLE "retrieval_runs" ADD CONSTRAINT "retrieval_runs_knowledge_base_id_fk" FOREIGN KEY ("tenant_id","knowledge_base_id") REFERENCES "public"."knowledge_bases"("tenant_id","id") ON DELETE restrict ON UPDATE no action;--> statement-breakpoint
ALTER TABLE "retrieval_runs" ADD CONSTRAINT "retrieval_runs_model_id_fk" FOREIGN KEY ("model_id") REFERENCES "public"."embedding_models"("id") ON DELETE restrict ON UPDATE no action;--> statement-breakpoint
ALTER TABLE "retrieval_runs" ADD CONSTRAINT "retrieval_runs_principal_id_fk" FOREIGN KEY ("tenant_id","principal_id") REFERENCES "public"."execution_principals"("tenant_id","id") ON DELETE restrict ON UPDATE no action;--> statement-breakpoint
ALTER TABLE "retrieval_runs" ADD CONSTRAINT "retrieval_runs_binding_id_fk" FOREIGN KEY ("tenant_id","binding_id") REFERENCES "public"."runtime_session_bindings"("tenant_id","id") ON DELETE restrict ON UPDATE no action;--> statement-breakpoint
ALTER TABLE "routine_runs" ADD CONSTRAINT "routine_runs_routine_id_fk" FOREIGN KEY ("tenant_id","routine_id") REFERENCES "public"."routines"("tenant_id","id") ON DELETE restrict ON UPDATE no action;--> statement-breakpoint
ALTER TABLE "routine_runs" ADD CONSTRAINT "routine_runs_tenant_id_fk" FOREIGN KEY ("tenant_id") REFERENCES "public"."tenants"("id") ON DELETE restrict ON UPDATE no action;--> statement-breakpoint
ALTER TABLE "routine_runs" ADD CONSTRAINT "routine_runs_workspace_id_fk" FOREIGN KEY ("tenant_id","workspace_id") REFERENCES "public"."workspaces"("tenant_id","id") ON DELETE restrict ON UPDATE no action;--> statement-breakpoint
ALTER TABLE "routines" ADD CONSTRAINT "routines_owner_user_id_fk" FOREIGN KEY ("owner_user_id") REFERENCES "public"."users"("id") ON DELETE restrict ON UPDATE no action;--> statement-breakpoint
ALTER TABLE "routines" ADD CONSTRAINT "routines_agent_id_fk" FOREIGN KEY ("tenant_id","agent_id") REFERENCES "public"."agents"("tenant_id","id") ON DELETE restrict ON UPDATE no action;--> statement-breakpoint
ALTER TABLE "routines" ADD CONSTRAINT "routines_channel_id_fk" FOREIGN KEY ("tenant_id","channel_id") REFERENCES "public"."channels"("tenant_id","id") ON DELETE restrict ON UPDATE no action;--> statement-breakpoint
ALTER TABLE "routines" ADD CONSTRAINT "routines_tenant_id_fk" FOREIGN KEY ("tenant_id") REFERENCES "public"."tenants"("id") ON DELETE restrict ON UPDATE no action;--> statement-breakpoint
ALTER TABLE "routines" ADD CONSTRAINT "routines_workspace_id_fk" FOREIGN KEY ("tenant_id","workspace_id") REFERENCES "public"."workspaces"("tenant_id","id") ON DELETE restrict ON UPDATE no action;--> statement-breakpoint
ALTER TABLE "run_memory_access" ADD CONSTRAINT "run_memory_access_tenant_id_fk" FOREIGN KEY ("tenant_id") REFERENCES "public"."tenants"("id") ON DELETE restrict ON UPDATE no action;--> statement-breakpoint
ALTER TABLE "run_memory_access" ADD CONSTRAINT "run_memory_access_run_id_fk" FOREIGN KEY ("tenant_id","run_id") REFERENCES "public"."agent_runs"("tenant_id","id") ON DELETE restrict ON UPDATE no action;--> statement-breakpoint
ALTER TABLE "run_memory_access" ADD CONSTRAINT "run_memory_access_namespace_id_fk" FOREIGN KEY ("tenant_id","namespace_id") REFERENCES "public"."memory_namespaces"("tenant_id","id") ON DELETE restrict ON UPDATE no action;--> statement-breakpoint
ALTER TABLE "runtime_identities" ADD CONSTRAINT "runtime_identities_tenant_id_fk" FOREIGN KEY ("tenant_id") REFERENCES "public"."tenants"("id") ON DELETE restrict ON UPDATE no action;--> statement-breakpoint
ALTER TABLE "runtime_identities" ADD CONSTRAINT "runtime_identities_backend_id_fk" FOREIGN KEY ("backend_id") REFERENCES "public"."runtime_backends"("id") ON DELETE restrict ON UPDATE no action;--> statement-breakpoint
ALTER TABLE "runtime_identities" ADD CONSTRAINT "runtime_identities_principal_id_fk" FOREIGN KEY ("tenant_id","principal_id") REFERENCES "public"."execution_principals"("tenant_id","id") ON DELETE restrict ON UPDATE no action;--> statement-breakpoint
ALTER TABLE "runtime_memory_bindings" ADD CONSTRAINT "runtime_memory_bindings_tenant_id_fk" FOREIGN KEY ("tenant_id") REFERENCES "public"."tenants"("id") ON DELETE restrict ON UPDATE no action;--> statement-breakpoint
ALTER TABLE "runtime_memory_bindings" ADD CONSTRAINT "runtime_memory_bindings_namespace_id_fk" FOREIGN KEY ("tenant_id","namespace_id") REFERENCES "public"."memory_namespaces"("tenant_id","id") ON DELETE restrict ON UPDATE no action;--> statement-breakpoint
ALTER TABLE "runtime_memory_bindings" ADD CONSTRAINT "runtime_memory_bindings_backend_id_fk" FOREIGN KEY ("backend_id") REFERENCES "public"."runtime_backends"("id") ON DELETE restrict ON UPDATE no action;--> statement-breakpoint
ALTER TABLE "runtime_session_bindings" ADD CONSTRAINT "runtime_session_bindings_tenant_id_fk" FOREIGN KEY ("tenant_id") REFERENCES "public"."tenants"("id") ON DELETE restrict ON UPDATE no action;--> statement-breakpoint
ALTER TABLE "runtime_session_bindings" ADD CONSTRAINT "runtime_session_bindings_identity_id_fk" FOREIGN KEY ("tenant_id","identity_id") REFERENCES "public"."runtime_identities"("tenant_id","id") ON DELETE restrict ON UPDATE no action;--> statement-breakpoint
ALTER TABLE "runtime_session_bindings" ADD CONSTRAINT "runtime_session_bindings_channel_id_fk" FOREIGN KEY ("tenant_id","channel_id") REFERENCES "public"."channels"("tenant_id","id") ON DELETE restrict ON UPDATE no action;--> statement-breakpoint
ALTER TABLE "runtime_session_bindings" ADD CONSTRAINT "runtime_session_bindings_agent_id_fk" FOREIGN KEY ("tenant_id","agent_id") REFERENCES "public"."agents"("tenant_id","id") ON DELETE restrict ON UPDATE no action;--> statement-breakpoint
ALTER TABLE "runtime_session_bindings" ADD CONSTRAINT "runtime_session_bindings_agent_version_id_fk" FOREIGN KEY ("tenant_id","agent_version_id") REFERENCES "public"."agent_versions"("tenant_id","id") ON DELETE restrict ON UPDATE no action;--> statement-breakpoint
ALTER TABLE "runtime_session_bindings" ADD CONSTRAINT "runtime_session_bindings_team_member_id_fk" FOREIGN KEY ("tenant_id","team_member_id") REFERENCES "public"."team_members"("tenant_id","id") ON DELETE restrict ON UPDATE no action;--> statement-breakpoint
ALTER TABLE "runtime_session_bindings" ADD CONSTRAINT "runtime_session_bindings_customer_user_id_fk" FOREIGN KEY ("customer_user_id") REFERENCES "public"."users"("id") ON DELETE restrict ON UPDATE no action;--> statement-breakpoint
ALTER TABLE "runtime_session_bindings" ADD CONSTRAINT "runtime_session_bindings_started_by_user_id_fk" FOREIGN KEY ("started_by_user_id") REFERENCES "public"."users"("id") ON DELETE restrict ON UPDATE no action;--> statement-breakpoint
ALTER TABLE "runtime_session_bindings" ADD CONSTRAINT "runtime_session_bindings_backend_id_fk" FOREIGN KEY ("backend_id") REFERENCES "public"."runtime_backends"("id") ON DELETE restrict ON UPDATE no action;--> statement-breakpoint
ALTER TABLE "runtime_session_operations" ADD CONSTRAINT "runtime_session_operations_tenant_id_fk" FOREIGN KEY ("tenant_id") REFERENCES "public"."tenants"("id") ON DELETE restrict ON UPDATE no action;--> statement-breakpoint
ALTER TABLE "runtime_session_operations" ADD CONSTRAINT "runtime_session_operations_binding_id_fk" FOREIGN KEY ("tenant_id","binding_id") REFERENCES "public"."runtime_session_bindings"("tenant_id","id") ON DELETE restrict ON UPDATE no action;--> statement-breakpoint
ALTER TABLE "runtime_session_operations" ADD CONSTRAINT "runtime_session_operations_actor_principal_id_fk" FOREIGN KEY ("tenant_id","actor_principal_id") REFERENCES "public"."execution_principals"("tenant_id","id") ON DELETE restrict ON UPDATE no action;--> statement-breakpoint
ALTER TABLE "runtime_session_operations" ADD CONSTRAINT "runtime_session_operations_initiated_by_user_id_fk" FOREIGN KEY ("initiated_by_user_id") REFERENCES "public"."users"("id") ON DELETE restrict ON UPDATE no action;--> statement-breakpoint
ALTER TABLE "runtime_session_operations" ADD CONSTRAINT "runtime_session_operations_trigger_event_id_fk" FOREIGN KEY ("tenant_id","trigger_event_id") REFERENCES "public"."ticket_events"("tenant_id","id") ON DELETE restrict ON UPDATE no action;--> statement-breakpoint
ALTER TABLE "runtime_session_operations" ADD CONSTRAINT "runtime_session_operations_result_run_id_fk" FOREIGN KEY ("tenant_id","result_run_id") REFERENCES "public"."agent_runs"("tenant_id","id") ON DELETE restrict ON UPDATE no action;--> statement-breakpoint
ALTER TABLE "sandboxed_components" ADD CONSTRAINT "sandboxed_components_tenant_id_fk" FOREIGN KEY ("tenant_id") REFERENCES "public"."tenants"("id") ON DELETE restrict ON UPDATE no action;--> statement-breakpoint
ALTER TABLE "sandboxed_components" ADD CONSTRAINT "sandboxed_components_workspace_id_fk" FOREIGN KEY ("tenant_id","workspace_id") REFERENCES "public"."workspaces"("tenant_id","id") ON DELETE restrict ON UPDATE no action;--> statement-breakpoint
ALTER TABLE "scoped_user_roles" ADD CONSTRAINT "scoped_user_roles_tenant_id_fk" FOREIGN KEY ("tenant_id") REFERENCES "public"."tenants"("id") ON DELETE restrict ON UPDATE no action;--> statement-breakpoint
ALTER TABLE "scoped_user_roles" ADD CONSTRAINT "scoped_user_roles_membership_id_fk" FOREIGN KEY ("tenant_id","membership_id") REFERENCES "public"."tenant_memberships"("tenant_id","id") ON DELETE restrict ON UPDATE no action;--> statement-breakpoint
ALTER TABLE "scoped_user_roles" ADD CONSTRAINT "scoped_user_roles_scope_id_fk" FOREIGN KEY ("tenant_id","scope_id") REFERENCES "public"."access_scopes"("tenant_id","id") ON DELETE restrict ON UPDATE no action;--> statement-breakpoint
ALTER TABLE "scoped_user_roles" ADD CONSTRAINT "scoped_user_roles_granted_by_fk" FOREIGN KEY ("granted_by") REFERENCES "public"."users"("id") ON DELETE restrict ON UPDATE no action;--> statement-breakpoint
ALTER TABLE "service_categories" ADD CONSTRAINT "service_categories_tenant_id_fk" FOREIGN KEY ("tenant_id") REFERENCES "public"."tenants"("id") ON DELETE restrict ON UPDATE no action;--> statement-breakpoint
ALTER TABLE "service_categories" ADD CONSTRAINT "service_categories_parent_id_fk" FOREIGN KEY ("tenant_id","parent_id") REFERENCES "public"."service_categories"("tenant_id","id") ON DELETE restrict ON UPDATE no action;--> statement-breakpoint
ALTER TABLE "service_interruptions" ADD CONSTRAINT "service_interruptions_tenant_id_fk" FOREIGN KEY ("tenant_id") REFERENCES "public"."tenants"("id") ON DELETE restrict ON UPDATE no action;--> statement-breakpoint
ALTER TABLE "service_interruptions" ADD CONSTRAINT "service_interruptions_work_order_id_fk" FOREIGN KEY ("tenant_id","work_order_id") REFERENCES "public"."work_orders"("tenant_id","id") ON DELETE restrict ON UPDATE no action;--> statement-breakpoint
ALTER TABLE "service_interruptions" ADD CONSTRAINT "service_interruptions_approval_id_fk" FOREIGN KEY ("tenant_id","approval_id") REFERENCES "public"."work_approvals"("tenant_id","id") ON DELETE restrict ON UPDATE no action;--> statement-breakpoint
ALTER TABLE "service_interruptions" ADD CONSTRAINT "service_interruptions_operated_by_fk" FOREIGN KEY ("operated_by") REFERENCES "public"."users"("id") ON DELETE restrict ON UPDATE no action;--> statement-breakpoint
ALTER TABLE "sessions" ADD CONSTRAINT "sessions_user_id_fk" FOREIGN KEY ("user_id") REFERENCES "public"."users"("id") ON DELETE cascade ON UPDATE no action;--> statement-breakpoint
ALTER TABLE "sites" ADD CONSTRAINT "sites_tenant_id_fk" FOREIGN KEY ("tenant_id") REFERENCES "public"."tenants"("id") ON DELETE restrict ON UPDATE no action;--> statement-breakpoint
ALTER TABLE "sites" ADD CONSTRAINT "sites_domain_id_fk" FOREIGN KEY ("tenant_id","domain_id") REFERENCES "public"."domains"("tenant_id","id") ON DELETE restrict ON UPDATE no action;--> statement-breakpoint
ALTER TABLE "skill_tools" ADD CONSTRAINT "skill_tools_skill_id_fk" FOREIGN KEY ("tenant_id","skill_id") REFERENCES "public"."skills"("tenant_id","id") ON DELETE restrict ON UPDATE no action;--> statement-breakpoint
ALTER TABLE "skill_tools" ADD CONSTRAINT "skill_tools_tenant_id_fk" FOREIGN KEY ("tenant_id") REFERENCES "public"."tenants"("id") ON DELETE restrict ON UPDATE no action;--> statement-breakpoint
ALTER TABLE "skills" ADD CONSTRAINT "skills_owner_user_id_fk" FOREIGN KEY ("owner_user_id") REFERENCES "public"."users"("id") ON DELETE restrict ON UPDATE no action;--> statement-breakpoint
ALTER TABLE "skills" ADD CONSTRAINT "skills_tenant_id_fk" FOREIGN KEY ("tenant_id") REFERENCES "public"."tenants"("id") ON DELETE restrict ON UPDATE no action;--> statement-breakpoint
ALTER TABLE "skills" ADD CONSTRAINT "skills_workspace_id_fk" FOREIGN KEY ("tenant_id","workspace_id") REFERENCES "public"."workspaces"("tenant_id","id") ON DELETE restrict ON UPDATE no action;--> statement-breakpoint
ALTER TABLE "sla_policies" ADD CONSTRAINT "sla_policies_tenant_id_fk" FOREIGN KEY ("tenant_id") REFERENCES "public"."tenants"("id") ON DELETE restrict ON UPDATE no action;--> statement-breakpoint
ALTER TABLE "sla_policies" ADD CONSTRAINT "sla_policies_management_unit_id_fk" FOREIGN KEY ("tenant_id","management_unit_id") REFERENCES "public"."management_units"("tenant_id","id") ON DELETE restrict ON UPDATE no action;--> statement-breakpoint
ALTER TABLE "sla_policies" ADD CONSTRAINT "sla_policies_category_id_fk" FOREIGN KEY ("tenant_id","category_id") REFERENCES "public"."service_categories"("tenant_id","id") ON DELETE restrict ON UPDATE no action;--> statement-breakpoint
ALTER TABLE "sla_policies" ADD CONSTRAINT "sla_policies_domain_id_fk" FOREIGN KEY ("tenant_id","domain_id") REFERENCES "public"."domains"("tenant_id","id") ON DELETE restrict ON UPDATE no action;--> statement-breakpoint
ALTER TABLE "sso_providers" ADD CONSTRAINT "sso_providers_user_id_fk" FOREIGN KEY ("user_id") REFERENCES "public"."users"("id") ON DELETE restrict ON UPDATE no action;--> statement-breakpoint
ALTER TABLE "staff_profiles" ADD CONSTRAINT "staff_profiles_tenant_id_fk" FOREIGN KEY ("tenant_id") REFERENCES "public"."tenants"("id") ON DELETE restrict ON UPDATE no action;--> statement-breakpoint
ALTER TABLE "staff_profiles" ADD CONSTRAINT "staff_profiles_user_id_fk" FOREIGN KEY ("user_id") REFERENCES "public"."users"("id") ON DELETE restrict ON UPDATE no action;--> statement-breakpoint
ALTER TABLE "staff_profiles" ADD CONSTRAINT "staff_profiles_management_unit_id_fk" FOREIGN KEY ("tenant_id","management_unit_id") REFERENCES "public"."management_units"("tenant_id","id") ON DELETE restrict ON UPDATE no action;--> statement-breakpoint
ALTER TABLE "staff_shifts" ADD CONSTRAINT "staff_shifts_tenant_id_fk" FOREIGN KEY ("tenant_id") REFERENCES "public"."tenants"("id") ON DELETE restrict ON UPDATE no action;--> statement-breakpoint
ALTER TABLE "staff_shifts" ADD CONSTRAINT "staff_shifts_staff_id_fk" FOREIGN KEY ("tenant_id","staff_id") REFERENCES "public"."staff_profiles"("tenant_id","id") ON DELETE restrict ON UPDATE no action;--> statement-breakpoint
ALTER TABLE "staff_specialties" ADD CONSTRAINT "staff_specialties_tenant_id_fk" FOREIGN KEY ("tenant_id") REFERENCES "public"."tenants"("id") ON DELETE restrict ON UPDATE no action;--> statement-breakpoint
ALTER TABLE "staff_specialties" ADD CONSTRAINT "staff_specialties_staff_id_fk" FOREIGN KEY ("tenant_id","staff_id") REFERENCES "public"."staff_profiles"("tenant_id","id") ON DELETE restrict ON UPDATE no action;--> statement-breakpoint
ALTER TABLE "staff_specialties" ADD CONSTRAINT "staff_specialties_category_id_fk" FOREIGN KEY ("tenant_id","category_id") REFERENCES "public"."service_categories"("tenant_id","id") ON DELETE restrict ON UPDATE no action;--> statement-breakpoint
ALTER TABLE "storage_event_receipts" ADD CONSTRAINT "storage_event_receipts_tenant_id_fk" FOREIGN KEY ("tenant_id") REFERENCES "public"."tenants"("id") ON DELETE restrict ON UPDATE no action;--> statement-breakpoint
ALTER TABLE "storage_event_receipts" ADD CONSTRAINT "storage_event_receipts_location_id_fk" FOREIGN KEY ("tenant_id","location_id") REFERENCES "public"."storage_locations"("tenant_id","id") ON DELETE restrict ON UPDATE no action;--> statement-breakpoint
ALTER TABLE "storage_locations" ADD CONSTRAINT "storage_locations_tenant_id_fk" FOREIGN KEY ("tenant_id") REFERENCES "public"."tenants"("id") ON DELETE restrict ON UPDATE no action;--> statement-breakpoint
ALTER TABLE "task_dependencies" ADD CONSTRAINT "task_dependencies_tenant_id_fk" FOREIGN KEY ("tenant_id") REFERENCES "public"."tenants"("id") ON DELETE restrict ON UPDATE no action;--> statement-breakpoint
ALTER TABLE "task_dependencies" ADD CONSTRAINT "task_dependencies_task_id_fk" FOREIGN KEY ("tenant_id","task_id") REFERENCES "public"."team_tasks"("tenant_id","id") ON DELETE restrict ON UPDATE no action;--> statement-breakpoint
ALTER TABLE "task_dependencies" ADD CONSTRAINT "task_dependencies_depends_on_id_fk" FOREIGN KEY ("tenant_id","depends_on_id") REFERENCES "public"."team_tasks"("tenant_id","id") ON DELETE restrict ON UPDATE no action;--> statement-breakpoint
ALTER TABLE "team_mailbox" ADD CONSTRAINT "team_mailbox_tenant_id_fk" FOREIGN KEY ("tenant_id") REFERENCES "public"."tenants"("id") ON DELETE restrict ON UPDATE no action;--> statement-breakpoint
ALTER TABLE "team_mailbox" ADD CONSTRAINT "team_mailbox_team_id_fk" FOREIGN KEY ("tenant_id","team_id") REFERENCES "public"."agent_teams"("tenant_id","id") ON DELETE restrict ON UPDATE no action;--> statement-breakpoint
ALTER TABLE "team_mailbox" ADD CONSTRAINT "team_mailbox_sender_member_id_fk" FOREIGN KEY ("tenant_id","sender_member_id") REFERENCES "public"."team_members"("tenant_id","id") ON DELETE restrict ON UPDATE no action;--> statement-breakpoint
ALTER TABLE "team_mailbox" ADD CONSTRAINT "team_mailbox_recipient_member_id_fk" FOREIGN KEY ("tenant_id","recipient_member_id") REFERENCES "public"."team_members"("tenant_id","id") ON DELETE restrict ON UPDATE no action;--> statement-breakpoint
ALTER TABLE "team_mailbox" ADD CONSTRAINT "team_mailbox_task_id_fk" FOREIGN KEY ("tenant_id","task_id") REFERENCES "public"."team_tasks"("tenant_id","id") ON DELETE restrict ON UPDATE no action;--> statement-breakpoint
ALTER TABLE "team_members" ADD CONSTRAINT "team_members_tenant_id_fk" FOREIGN KEY ("tenant_id") REFERENCES "public"."tenants"("id") ON DELETE restrict ON UPDATE no action;--> statement-breakpoint
ALTER TABLE "team_members" ADD CONSTRAINT "team_members_team_id_fk" FOREIGN KEY ("tenant_id","team_id") REFERENCES "public"."agent_teams"("tenant_id","id") ON DELETE restrict ON UPDATE no action;--> statement-breakpoint
ALTER TABLE "team_members" ADD CONSTRAINT "team_members_agent_id_fk" FOREIGN KEY ("tenant_id","agent_id") REFERENCES "public"."agents"("tenant_id","id") ON DELETE restrict ON UPDATE no action;--> statement-breakpoint
ALTER TABLE "team_members" ADD CONSTRAINT "team_members_version_id_fk" FOREIGN KEY ("tenant_id","version_id") REFERENCES "public"."agent_versions"("tenant_id","id") ON DELETE restrict ON UPDATE no action;--> statement-breakpoint
ALTER TABLE "team_members" ADD CONSTRAINT "team_members_binding_id_fk" FOREIGN KEY ("tenant_id","binding_id") REFERENCES "public"."runtime_session_bindings"("tenant_id","id") ON DELETE restrict ON UPDATE no action;--> statement-breakpoint
ALTER TABLE "team_tasks" ADD CONSTRAINT "team_tasks_tenant_id_fk" FOREIGN KEY ("tenant_id") REFERENCES "public"."tenants"("id") ON DELETE restrict ON UPDATE no action;--> statement-breakpoint
ALTER TABLE "team_tasks" ADD CONSTRAINT "team_tasks_team_id_fk" FOREIGN KEY ("tenant_id","team_id") REFERENCES "public"."agent_teams"("tenant_id","id") ON DELETE restrict ON UPDATE no action;--> statement-breakpoint
ALTER TABLE "team_tasks" ADD CONSTRAINT "team_tasks_parent_task_id_fk" FOREIGN KEY ("tenant_id","parent_task_id") REFERENCES "public"."team_tasks"("tenant_id","id") ON DELETE restrict ON UPDATE no action;--> statement-breakpoint
ALTER TABLE "team_tasks" ADD CONSTRAINT "team_tasks_ticket_id_fk" FOREIGN KEY ("tenant_id","ticket_id") REFERENCES "public"."tickets"("tenant_id","id") ON DELETE restrict ON UPDATE no action;--> statement-breakpoint
ALTER TABLE "team_tasks" ADD CONSTRAINT "team_tasks_assigned_member_id_fk" FOREIGN KEY ("tenant_id","assigned_member_id") REFERENCES "public"."team_members"("tenant_id","id") ON DELETE restrict ON UPDATE no action;--> statement-breakpoint
ALTER TABLE "tenant_memberships" ADD CONSTRAINT "tenant_memberships_tenant_id_fk" FOREIGN KEY ("tenant_id") REFERENCES "public"."tenants"("id") ON DELETE restrict ON UPDATE no action;--> statement-breakpoint
ALTER TABLE "tenant_memberships" ADD CONSTRAINT "tenant_memberships_user_id_fk" FOREIGN KEY ("user_id") REFERENCES "public"."users"("id") ON DELETE restrict ON UPDATE no action;--> statement-breakpoint
ALTER TABLE "ticket_assessment_evidence" ADD CONSTRAINT "ticket_assessment_evidence_tenant_id_fk" FOREIGN KEY ("tenant_id") REFERENCES "public"."tenants"("id") ON DELETE restrict ON UPDATE no action;--> statement-breakpoint
ALTER TABLE "ticket_assessment_evidence" ADD CONSTRAINT "ticket_assessment_evidence_assessment_id_fk" FOREIGN KEY ("tenant_id","assessment_id") REFERENCES "public"."ticket_assessments"("tenant_id","id") ON DELETE restrict ON UPDATE no action;--> statement-breakpoint
ALTER TABLE "ticket_assessment_evidence" ADD CONSTRAINT "ticket_assessment_evidence_message_id_fk" FOREIGN KEY ("tenant_id","message_id") REFERENCES "public"."messages"("tenant_id","id") ON DELETE restrict ON UPDATE no action;--> statement-breakpoint
ALTER TABLE "ticket_assessment_evidence" ADD CONSTRAINT "ticket_assessment_evidence_event_id_fk" FOREIGN KEY ("tenant_id","event_id") REFERENCES "public"."ticket_events"("tenant_id","id") ON DELETE restrict ON UPDATE no action;--> statement-breakpoint
ALTER TABLE "ticket_assessment_evidence" ADD CONSTRAINT "ticket_assessment_evidence_evidence_item_id_fk" FOREIGN KEY ("tenant_id","evidence_item_id") REFERENCES "public"."evidence_items"("tenant_id","id") ON DELETE restrict ON UPDATE no action;--> statement-breakpoint
ALTER TABLE "ticket_assessment_evidence" ADD CONSTRAINT "ticket_assessment_evidence_object_id_fk" FOREIGN KEY ("tenant_id","object_id") REFERENCES "public"."file_objects"("tenant_id","id") ON DELETE restrict ON UPDATE no action;--> statement-breakpoint
ALTER TABLE "ticket_assessments" ADD CONSTRAINT "ticket_assessments_tenant_id_fk" FOREIGN KEY ("tenant_id") REFERENCES "public"."tenants"("id") ON DELETE restrict ON UPDATE no action;--> statement-breakpoint
ALTER TABLE "ticket_assessments" ADD CONSTRAINT "ticket_assessments_ticket_id_fk" FOREIGN KEY ("tenant_id","ticket_id") REFERENCES "public"."tickets"("tenant_id","id") ON DELETE restrict ON UPDATE no action;--> statement-breakpoint
ALTER TABLE "ticket_assessments" ADD CONSTRAINT "ticket_assessments_basis_decision_id_fk" FOREIGN KEY ("tenant_id","basis_decision_id") REFERENCES "public"."ticket_triage_decisions"("tenant_id","id") ON DELETE restrict ON UPDATE no action;--> statement-breakpoint
ALTER TABLE "ticket_assessments" ADD CONSTRAINT "ticket_assessments_assessor_user_id_fk" FOREIGN KEY ("assessor_user_id") REFERENCES "public"."users"("id") ON DELETE restrict ON UPDATE no action;--> statement-breakpoint
ALTER TABLE "ticket_assessments" ADD CONSTRAINT "ticket_assessments_source_run_id_fk" FOREIGN KEY ("tenant_id","source_run_id") REFERENCES "public"."agent_runs"("tenant_id","id") ON DELETE restrict ON UPDATE no action;--> statement-breakpoint
ALTER TABLE "ticket_assessments" ADD CONSTRAINT "ticket_assessments_supersedes_assessment_id_fk" FOREIGN KEY ("tenant_id","supersedes_assessment_id") REFERENCES "public"."ticket_assessments"("tenant_id","id") ON DELETE restrict ON UPDATE no action;--> statement-breakpoint
ALTER TABLE "ticket_escalations" ADD CONSTRAINT "ticket_escalations_tenant_id_fk" FOREIGN KEY ("tenant_id") REFERENCES "public"."tenants"("id") ON DELETE restrict ON UPDATE no action;--> statement-breakpoint
ALTER TABLE "ticket_escalations" ADD CONSTRAINT "ticket_escalations_ticket_id_fk" FOREIGN KEY ("tenant_id","ticket_id") REFERENCES "public"."tickets"("tenant_id","id") ON DELETE restrict ON UPDATE no action;--> statement-breakpoint
ALTER TABLE "ticket_escalations" ADD CONSTRAINT "ticket_escalations_decision_id_fk" FOREIGN KEY ("tenant_id","decision_id") REFERENCES "public"."ticket_triage_decisions"("tenant_id","id") ON DELETE restrict ON UPDATE no action;--> statement-breakpoint
ALTER TABLE "ticket_escalations" ADD CONSTRAINT "ticket_escalations_sla_cycle_id_fk" FOREIGN KEY ("tenant_id","sla_cycle_id") REFERENCES "public"."ticket_sla_cycles"("tenant_id","id") ON DELETE restrict ON UPDATE no action;--> statement-breakpoint
ALTER TABLE "ticket_escalations" ADD CONSTRAINT "ticket_escalations_review_id_fk" FOREIGN KEY ("tenant_id","review_id") REFERENCES "public"."ticket_triage_reviews"("tenant_id","id") ON DELETE restrict ON UPDATE no action;--> statement-breakpoint
ALTER TABLE "ticket_escalations" ADD CONSTRAINT "ticket_escalations_work_order_id_fk" FOREIGN KEY ("tenant_id","work_order_id") REFERENCES "public"."work_orders"("tenant_id","id") ON DELETE restrict ON UPDATE no action;--> statement-breakpoint
ALTER TABLE "ticket_escalations" ADD CONSTRAINT "ticket_escalations_required_scope_id_fk" FOREIGN KEY ("tenant_id","required_scope_id") REFERENCES "public"."access_scopes"("tenant_id","id") ON DELETE restrict ON UPDATE no action;--> statement-breakpoint
ALTER TABLE "ticket_escalations" ADD CONSTRAINT "ticket_escalations_acknowledged_by_fk" FOREIGN KEY ("acknowledged_by") REFERENCES "public"."users"("id") ON DELETE restrict ON UPDATE no action;--> statement-breakpoint
ALTER TABLE "ticket_escalations" ADD CONSTRAINT "ticket_escalations_resolved_by_fk" FOREIGN KEY ("resolved_by") REFERENCES "public"."users"("id") ON DELETE restrict ON UPDATE no action;--> statement-breakpoint
ALTER TABLE "ticket_escalations" ADD CONSTRAINT "ticket_escalations_assessment_id_fk" FOREIGN KEY ("tenant_id","assessment_id") REFERENCES "public"."ticket_assessments"("tenant_id","id") ON DELETE restrict ON UPDATE no action;--> statement-breakpoint
ALTER TABLE "ticket_events" ADD CONSTRAINT "ticket_events_tenant_id_fk" FOREIGN KEY ("tenant_id") REFERENCES "public"."tenants"("id") ON DELETE restrict ON UPDATE no action;--> statement-breakpoint
ALTER TABLE "ticket_events" ADD CONSTRAINT "ticket_events_ticket_id_fk" FOREIGN KEY ("tenant_id","ticket_id") REFERENCES "public"."tickets"("tenant_id","id") ON DELETE restrict ON UPDATE no action;--> statement-breakpoint
ALTER TABLE "ticket_events" ADD CONSTRAINT "ticket_events_actor_user_id_fk" FOREIGN KEY ("actor_user_id") REFERENCES "public"."users"("id") ON DELETE restrict ON UPDATE no action;--> statement-breakpoint
ALTER TABLE "ticket_events" ADD CONSTRAINT "ticket_events_actor_agent_id_fk" FOREIGN KEY ("tenant_id","actor_agent_id") REFERENCES "public"."agents"("tenant_id","id") ON DELETE restrict ON UPDATE no action;--> statement-breakpoint
ALTER TABLE "ticket_events" ADD CONSTRAINT "ticket_events_causation_event_id_fk" FOREIGN KEY ("tenant_id","causation_event_id") REFERENCES "public"."ticket_events"("tenant_id","id") ON DELETE restrict ON UPDATE no action;--> statement-breakpoint
ALTER TABLE "ticket_files" ADD CONSTRAINT "ticket_files_tenant_id_fk" FOREIGN KEY ("tenant_id") REFERENCES "public"."tenants"("id") ON DELETE restrict ON UPDATE no action;--> statement-breakpoint
ALTER TABLE "ticket_files" ADD CONSTRAINT "ticket_files_ticket_id_fk" FOREIGN KEY ("tenant_id","ticket_id") REFERENCES "public"."tickets"("tenant_id","id") ON DELETE restrict ON UPDATE no action;--> statement-breakpoint
ALTER TABLE "ticket_files" ADD CONSTRAINT "ticket_files_file_id_fk" FOREIGN KEY ("tenant_id","file_id") REFERENCES "public"."files"("tenant_id","id") ON DELETE restrict ON UPDATE no action;--> statement-breakpoint
ALTER TABLE "ticket_files" ADD CONSTRAINT "ticket_files_event_id_fk" FOREIGN KEY ("tenant_id","event_id") REFERENCES "public"."ticket_events"("tenant_id","id") ON DELETE restrict ON UPDATE no action;--> statement-breakpoint
ALTER TABLE "ticket_files" ADD CONSTRAINT "ticket_files_uploaded_by_fk" FOREIGN KEY ("uploaded_by") REFERENCES "public"."users"("id") ON DELETE restrict ON UPDATE no action;--> statement-breakpoint
ALTER TABLE "ticket_files" ADD CONSTRAINT "ticket_files_evidence_id_fk" FOREIGN KEY ("tenant_id","evidence_id") REFERENCES "public"."evidence_items"("tenant_id","id") ON DELETE restrict ON UPDATE no action;--> statement-breakpoint
ALTER TABLE "ticket_reviews" ADD CONSTRAINT "ticket_reviews_tenant_id_fk" FOREIGN KEY ("tenant_id") REFERENCES "public"."tenants"("id") ON DELETE restrict ON UPDATE no action;--> statement-breakpoint
ALTER TABLE "ticket_reviews" ADD CONSTRAINT "ticket_reviews_ticket_id_fk" FOREIGN KEY ("tenant_id","ticket_id") REFERENCES "public"."tickets"("tenant_id","id") ON DELETE restrict ON UPDATE no action;--> statement-breakpoint
ALTER TABLE "ticket_reviews" ADD CONSTRAINT "ticket_reviews_assignment_id_fk" FOREIGN KEY ("tenant_id","assignment_id") REFERENCES "public"."work_assignments"("tenant_id","id") ON DELETE restrict ON UPDATE no action;--> statement-breakpoint
ALTER TABLE "ticket_reviews" ADD CONSTRAINT "ticket_reviews_reviewer_user_id_fk" FOREIGN KEY ("reviewer_user_id") REFERENCES "public"."users"("id") ON DELETE restrict ON UPDATE no action;--> statement-breakpoint
ALTER TABLE "ticket_reviews" ADD CONSTRAINT "ticket_reviews_staff_id_fk" FOREIGN KEY ("tenant_id","staff_id") REFERENCES "public"."staff_profiles"("tenant_id","id") ON DELETE restrict ON UPDATE no action;--> statement-breakpoint
ALTER TABLE "ticket_routing_history" ADD CONSTRAINT "ticket_routing_history_tenant_id_fk" FOREIGN KEY ("tenant_id") REFERENCES "public"."tenants"("id") ON DELETE restrict ON UPDATE no action;--> statement-breakpoint
ALTER TABLE "ticket_routing_history" ADD CONSTRAINT "ticket_routing_history_ticket_id_fk" FOREIGN KEY ("tenant_id","ticket_id") REFERENCES "public"."tickets"("tenant_id","id") ON DELETE restrict ON UPDATE no action;--> statement-breakpoint
ALTER TABLE "ticket_routing_history" ADD CONSTRAINT "ticket_routing_history_from_management_id_fk" FOREIGN KEY ("tenant_id","from_management_id") REFERENCES "public"."management_units"("tenant_id","id") ON DELETE restrict ON UPDATE no action;--> statement-breakpoint
ALTER TABLE "ticket_routing_history" ADD CONSTRAINT "ticket_routing_history_to_management_id_fk" FOREIGN KEY ("tenant_id","to_management_id") REFERENCES "public"."management_units"("tenant_id","id") ON DELETE restrict ON UPDATE no action;--> statement-breakpoint
ALTER TABLE "ticket_routing_history" ADD CONSTRAINT "ticket_routing_history_team_id_fk" FOREIGN KEY ("tenant_id","team_id") REFERENCES "public"."agent_teams"("tenant_id","id") ON DELETE restrict ON UPDATE no action;--> statement-breakpoint
ALTER TABLE "ticket_routing_history" ADD CONSTRAINT "ticket_routing_history_ack_event_id_fk" FOREIGN KEY ("tenant_id","ack_event_id") REFERENCES "public"."ticket_events"("tenant_id","id") ON DELETE restrict ON UPDATE no action;--> statement-breakpoint
ALTER TABLE "ticket_sla_adjustments" ADD CONSTRAINT "ticket_sla_adjustments_tenant_id_fk" FOREIGN KEY ("tenant_id") REFERENCES "public"."tenants"("id") ON DELETE restrict ON UPDATE no action;--> statement-breakpoint
ALTER TABLE "ticket_sla_adjustments" ADD CONSTRAINT "ticket_sla_adjustments_cycle_id_fk" FOREIGN KEY ("tenant_id","cycle_id") REFERENCES "public"."ticket_sla_cycles"("tenant_id","id") ON DELETE restrict ON UPDATE no action;--> statement-breakpoint
ALTER TABLE "ticket_sla_adjustments" ADD CONSTRAINT "ticket_sla_adjustments_decision_id_fk" FOREIGN KEY ("tenant_id","decision_id") REFERENCES "public"."ticket_triage_decisions"("tenant_id","id") ON DELETE restrict ON UPDATE no action;--> statement-breakpoint
ALTER TABLE "ticket_sla_adjustments" ADD CONSTRAINT "ticket_sla_adjustments_target_policy_id_fk" FOREIGN KEY ("tenant_id","target_policy_id") REFERENCES "public"."sla_policies"("tenant_id","id") ON DELETE restrict ON UPDATE no action;--> statement-breakpoint
ALTER TABLE "ticket_sla_adjustments" ADD CONSTRAINT "ticket_sla_adjustments_authorized_by_fk" FOREIGN KEY ("authorized_by") REFERENCES "public"."users"("id") ON DELETE restrict ON UPDATE no action;--> statement-breakpoint
ALTER TABLE "ticket_sla_cycles" ADD CONSTRAINT "ticket_sla_cycles_tenant_id_fk" FOREIGN KEY ("tenant_id") REFERENCES "public"."tenants"("id") ON DELETE restrict ON UPDATE no action;--> statement-breakpoint
ALTER TABLE "ticket_sla_cycles" ADD CONSTRAINT "ticket_sla_cycles_ticket_id_fk" FOREIGN KEY ("tenant_id","ticket_id") REFERENCES "public"."tickets"("tenant_id","id") ON DELETE restrict ON UPDATE no action;--> statement-breakpoint
ALTER TABLE "ticket_sla_cycles" ADD CONSTRAINT "ticket_sla_cycles_initial_policy_id_fk" FOREIGN KEY ("tenant_id","initial_policy_id") REFERENCES "public"."sla_policies"("tenant_id","id") ON DELETE restrict ON UPDATE no action;--> statement-breakpoint
ALTER TABLE "ticket_sla_cycles" ADD CONSTRAINT "ticket_sla_cycles_initial_decision_id_fk" FOREIGN KEY ("tenant_id","initial_decision_id") REFERENCES "public"."ticket_triage_decisions"("tenant_id","id") ON DELETE restrict ON UPDATE no action;--> statement-breakpoint
ALTER TABLE "ticket_triage_decisions" ADD CONSTRAINT "ticket_triage_decisions_tenant_id_fk" FOREIGN KEY ("tenant_id") REFERENCES "public"."tenants"("id") ON DELETE restrict ON UPDATE no action;--> statement-breakpoint
ALTER TABLE "ticket_triage_decisions" ADD CONSTRAINT "ticket_triage_decisions_ticket_id_fk" FOREIGN KEY ("tenant_id","ticket_id") REFERENCES "public"."tickets"("tenant_id","id") ON DELETE restrict ON UPDATE no action;--> statement-breakpoint
ALTER TABLE "ticket_triage_decisions" ADD CONSTRAINT "ticket_triage_decisions_assessment_id_fk" FOREIGN KEY ("tenant_id","assessment_id") REFERENCES "public"."ticket_assessments"("tenant_id","id") ON DELETE restrict ON UPDATE no action;--> statement-breakpoint
ALTER TABLE "ticket_triage_decisions" ADD CONSTRAINT "ticket_triage_decisions_policy_binding_id_fk" FOREIGN KEY ("tenant_id","policy_binding_id") REFERENCES "public"."triage_policy_bindings"("tenant_id","id") ON DELETE restrict ON UPDATE no action;--> statement-breakpoint
ALTER TABLE "ticket_triage_decisions" ADD CONSTRAINT "ticket_triage_decisions_policy_version_id_fk" FOREIGN KEY ("tenant_id","policy_version_id") REFERENCES "public"."triage_policy_versions"("tenant_id","id") ON DELETE restrict ON UPDATE no action;--> statement-breakpoint
ALTER TABLE "ticket_triage_decisions" ADD CONSTRAINT "ticket_triage_decisions_matched_rule_id_fk" FOREIGN KEY ("tenant_id","matched_rule_id") REFERENCES "public"."triage_rules"("tenant_id","id") ON DELETE restrict ON UPDATE no action;--> statement-breakpoint
ALTER TABLE "ticket_triage_decisions" ADD CONSTRAINT "ticket_triage_decisions_previous_applied_id_fk" FOREIGN KEY ("tenant_id","previous_applied_id") REFERENCES "public"."ticket_triage_decisions"("tenant_id","id") ON DELETE restrict ON UPDATE no action;--> statement-breakpoint
ALTER TABLE "ticket_triage_decisions" ADD CONSTRAINT "ticket_triage_decisions_review_id_fk" FOREIGN KEY ("tenant_id","review_id") REFERENCES "public"."ticket_triage_reviews"("tenant_id","id") ON DELETE restrict ON UPDATE no action;--> statement-breakpoint
ALTER TABLE "ticket_triage_decisions" ADD CONSTRAINT "ticket_triage_decisions_approved_by_fk" FOREIGN KEY ("approved_by") REFERENCES "public"."users"("id") ON DELETE restrict ON UPDATE no action;--> statement-breakpoint
ALTER TABLE "ticket_triage_reviews" ADD CONSTRAINT "ticket_triage_reviews_tenant_id_fk" FOREIGN KEY ("tenant_id") REFERENCES "public"."tenants"("id") ON DELETE restrict ON UPDATE no action;--> statement-breakpoint
ALTER TABLE "ticket_triage_reviews" ADD CONSTRAINT "ticket_triage_reviews_ticket_id_fk" FOREIGN KEY ("tenant_id","ticket_id") REFERENCES "public"."tickets"("tenant_id","id") ON DELETE restrict ON UPDATE no action;--> statement-breakpoint
ALTER TABLE "ticket_triage_reviews" ADD CONSTRAINT "ticket_triage_reviews_assessment_id_fk" FOREIGN KEY ("tenant_id","assessment_id") REFERENCES "public"."ticket_assessments"("tenant_id","id") ON DELETE restrict ON UPDATE no action;--> statement-breakpoint
ALTER TABLE "ticket_triage_reviews" ADD CONSTRAINT "ticket_triage_reviews_pending_decision_id_fk" FOREIGN KEY ("tenant_id","pending_decision_id") REFERENCES "public"."ticket_triage_decisions"("tenant_id","id") ON DELETE restrict ON UPDATE no action;--> statement-breakpoint
ALTER TABLE "ticket_triage_reviews" ADD CONSTRAINT "ticket_triage_reviews_required_scope_id_fk" FOREIGN KEY ("tenant_id","required_scope_id") REFERENCES "public"."access_scopes"("tenant_id","id") ON DELETE restrict ON UPDATE no action;--> statement-breakpoint
ALTER TABLE "ticket_triage_reviews" ADD CONSTRAINT "ticket_triage_reviews_claimed_by_fk" FOREIGN KEY ("claimed_by") REFERENCES "public"."users"("id") ON DELETE restrict ON UPDATE no action;--> statement-breakpoint
ALTER TABLE "ticket_triage_reviews" ADD CONSTRAINT "ticket_triage_reviews_decided_by_fk" FOREIGN KEY ("decided_by") REFERENCES "public"."users"("id") ON DELETE restrict ON UPDATE no action;--> statement-breakpoint
ALTER TABLE "ticket_triage_reviews" ADD CONSTRAINT "ticket_triage_reviews_result_decision_id_fk" FOREIGN KEY ("tenant_id","result_decision_id") REFERENCES "public"."ticket_triage_decisions"("tenant_id","id") ON DELETE restrict ON UPDATE no action;--> statement-breakpoint
ALTER TABLE "tickets" ADD CONSTRAINT "tickets_tenant_id_fk" FOREIGN KEY ("tenant_id") REFERENCES "public"."tenants"("id") ON DELETE restrict ON UPDATE no action;--> statement-breakpoint
ALTER TABLE "tickets" ADD CONSTRAINT "tickets_requester_user_id_fk" FOREIGN KEY ("requester_user_id") REFERENCES "public"."users"("id") ON DELETE restrict ON UPDATE no action;--> statement-breakpoint
ALTER TABLE "tickets" ADD CONSTRAINT "tickets_channel_id_fk" FOREIGN KEY ("tenant_id","channel_id") REFERENCES "public"."channels"("tenant_id","id") ON DELETE restrict ON UPDATE no action;--> statement-breakpoint
ALTER TABLE "tickets" ADD CONSTRAINT "tickets_unit_id_fk" FOREIGN KEY ("tenant_id","unit_id") REFERENCES "public"."units"("tenant_id","id") ON DELETE restrict ON UPDATE no action;--> statement-breakpoint
ALTER TABLE "tickets" ADD CONSTRAINT "tickets_site_id_fk" FOREIGN KEY ("tenant_id","site_id") REFERENCES "public"."sites"("tenant_id","id") ON DELETE restrict ON UPDATE no action;--> statement-breakpoint
ALTER TABLE "tickets" ADD CONSTRAINT "tickets_zone_id_fk" FOREIGN KEY ("tenant_id","zone_id") REFERENCES "public"."zones"("tenant_id","id") ON DELETE restrict ON UPDATE no action;--> statement-breakpoint
ALTER TABLE "tickets" ADD CONSTRAINT "tickets_building_id_fk" FOREIGN KEY ("tenant_id","building_id") REFERENCES "public"."buildings"("tenant_id","id") ON DELETE restrict ON UPDATE no action;--> statement-breakpoint
ALTER TABLE "tickets" ADD CONSTRAINT "tickets_management_unit_id_fk" FOREIGN KEY ("tenant_id","management_unit_id") REFERENCES "public"."management_units"("tenant_id","id") ON DELETE restrict ON UPDATE no action;--> statement-breakpoint
ALTER TABLE "tickets" ADD CONSTRAINT "tickets_coverage_id_fk" FOREIGN KEY ("tenant_id","coverage_id") REFERENCES "public"."management_coverage"("tenant_id","id") ON DELETE restrict ON UPDATE no action;--> statement-breakpoint
ALTER TABLE "tickets" ADD CONSTRAINT "tickets_category_id_fk" FOREIGN KEY ("tenant_id","category_id") REFERENCES "public"."service_categories"("tenant_id","id") ON DELETE restrict ON UPDATE no action;--> statement-breakpoint
ALTER TABLE "tickets" ADD CONSTRAINT "tickets_incident_type_id_fk" FOREIGN KEY ("tenant_id","incident_type_id") REFERENCES "public"."incident_types"("tenant_id","id") ON DELETE restrict ON UPDATE no action;--> statement-breakpoint
ALTER TABLE "tickets" ADD CONSTRAINT "tickets_assigned_team_id_fk" FOREIGN KEY ("tenant_id","assigned_team_id") REFERENCES "public"."agent_teams"("tenant_id","id") ON DELETE restrict ON UPDATE no action;--> statement-breakpoint
ALTER TABLE "tickets" ADD CONSTRAINT "tickets_sla_policy_id_fk" FOREIGN KEY ("tenant_id","sla_policy_id") REFERENCES "public"."sla_policies"("tenant_id","id") ON DELETE restrict ON UPDATE no action;--> statement-breakpoint
ALTER TABLE "tickets" ADD CONSTRAINT "tickets_domain_id_fk" FOREIGN KEY ("tenant_id","domain_id") REFERENCES "public"."domains"("tenant_id","id") ON DELETE restrict ON UPDATE no action;--> statement-breakpoint
ALTER TABLE "tickets" ADD CONSTRAINT "tickets_current_triage_decision_id_fk" FOREIGN KEY ("tenant_id","current_triage_decision_id") REFERENCES "public"."ticket_triage_decisions"("tenant_id","id") ON DELETE restrict ON UPDATE no action;--> statement-breakpoint
ALTER TABLE "tickets" ADD CONSTRAINT "tickets_active_sla_cycle_id_fk" FOREIGN KEY ("tenant_id","active_sla_cycle_id") REFERENCES "public"."ticket_sla_cycles"("tenant_id","id") ON DELETE restrict ON UPDATE no action;--> statement-breakpoint
ALTER TABLE "triage_policy_bindings" ADD CONSTRAINT "triage_policy_bindings_tenant_id_fk" FOREIGN KEY ("tenant_id") REFERENCES "public"."tenants"("id") ON DELETE restrict ON UPDATE no action;--> statement-breakpoint
ALTER TABLE "triage_policy_bindings" ADD CONSTRAINT "triage_policy_bindings_domain_id_fk" FOREIGN KEY ("tenant_id","domain_id") REFERENCES "public"."domains"("tenant_id","id") ON DELETE restrict ON UPDATE no action;--> statement-breakpoint
ALTER TABLE "triage_policy_bindings" ADD CONSTRAINT "triage_policy_bindings_scope_id_fk" FOREIGN KEY ("tenant_id","scope_id") REFERENCES "public"."access_scopes"("tenant_id","id") ON DELETE restrict ON UPDATE no action;--> statement-breakpoint
ALTER TABLE "triage_policy_bindings" ADD CONSTRAINT "triage_policy_bindings_category_id_fk" FOREIGN KEY ("tenant_id","category_id") REFERENCES "public"."service_categories"("tenant_id","id") ON DELETE restrict ON UPDATE no action;--> statement-breakpoint
ALTER TABLE "triage_policy_bindings" ADD CONSTRAINT "triage_policy_bindings_policy_version_id_fk" FOREIGN KEY ("tenant_id","policy_version_id") REFERENCES "public"."triage_policy_versions"("tenant_id","id") ON DELETE restrict ON UPDATE no action;--> statement-breakpoint
ALTER TABLE "triage_policy_bindings" ADD CONSTRAINT "triage_policy_bindings_configured_by_fk" FOREIGN KEY ("configured_by") REFERENCES "public"."users"("id") ON DELETE restrict ON UPDATE no action;--> statement-breakpoint
ALTER TABLE "triage_policy_versions" ADD CONSTRAINT "triage_policy_versions_tenant_id_fk" FOREIGN KEY ("tenant_id") REFERENCES "public"."tenants"("id") ON DELETE restrict ON UPDATE no action;--> statement-breakpoint
ALTER TABLE "triage_policy_versions" ADD CONSTRAINT "triage_policy_versions_domain_id_fk" FOREIGN KEY ("tenant_id","domain_id") REFERENCES "public"."domains"("tenant_id","id") ON DELETE restrict ON UPDATE no action;--> statement-breakpoint
ALTER TABLE "triage_policy_versions" ADD CONSTRAINT "triage_policy_versions_created_by_fk" FOREIGN KEY ("created_by") REFERENCES "public"."users"("id") ON DELETE restrict ON UPDATE no action;--> statement-breakpoint
ALTER TABLE "triage_policy_versions" ADD CONSTRAINT "triage_policy_versions_published_by_fk" FOREIGN KEY ("published_by") REFERENCES "public"."users"("id") ON DELETE restrict ON UPDATE no action;--> statement-breakpoint
ALTER TABLE "triage_rules" ADD CONSTRAINT "triage_rules_tenant_id_fk" FOREIGN KEY ("tenant_id") REFERENCES "public"."tenants"("id") ON DELETE restrict ON UPDATE no action;--> statement-breakpoint
ALTER TABLE "triage_rules" ADD CONSTRAINT "triage_rules_policy_version_id_fk" FOREIGN KEY ("tenant_id","policy_version_id") REFERENCES "public"."triage_policy_versions"("tenant_id","id") ON DELETE restrict ON UPDATE no action;--> statement-breakpoint
ALTER TABLE "unit_residents" ADD CONSTRAINT "unit_residents_tenant_id_fk" FOREIGN KEY ("tenant_id") REFERENCES "public"."tenants"("id") ON DELETE restrict ON UPDATE no action;--> statement-breakpoint
ALTER TABLE "unit_residents" ADD CONSTRAINT "unit_residents_unit_id_fk" FOREIGN KEY ("tenant_id","unit_id") REFERENCES "public"."units"("tenant_id","id") ON DELETE restrict ON UPDATE no action;--> statement-breakpoint
ALTER TABLE "unit_residents" ADD CONSTRAINT "unit_residents_user_id_fk" FOREIGN KEY ("user_id") REFERENCES "public"."users"("id") ON DELETE restrict ON UPDATE no action;--> statement-breakpoint
ALTER TABLE "unit_residents" ADD CONSTRAINT "unit_residents_verified_by_fk" FOREIGN KEY ("verified_by") REFERENCES "public"."users"("id") ON DELETE restrict ON UPDATE no action;--> statement-breakpoint
ALTER TABLE "units" ADD CONSTRAINT "units_tenant_id_fk" FOREIGN KEY ("tenant_id") REFERENCES "public"."tenants"("id") ON DELETE restrict ON UPDATE no action;--> statement-breakpoint
ALTER TABLE "units" ADD CONSTRAINT "units_site_id_fk" FOREIGN KEY ("tenant_id","site_id") REFERENCES "public"."sites"("tenant_id","id") ON DELETE restrict ON UPDATE no action;--> statement-breakpoint
ALTER TABLE "units" ADD CONSTRAINT "units_zone_id_fk" FOREIGN KEY ("tenant_id","zone_id") REFERENCES "public"."zones"("tenant_id","id") ON DELETE restrict ON UPDATE no action;--> statement-breakpoint
ALTER TABLE "units" ADD CONSTRAINT "units_building_id_fk" FOREIGN KEY ("tenant_id","building_id") REFERENCES "public"."buildings"("tenant_id","id") ON DELETE restrict ON UPDATE no action;--> statement-breakpoint
ALTER TABLE "user_instructions" ADD CONSTRAINT "user_instructions_user_id_fk" FOREIGN KEY ("user_id") REFERENCES "public"."users"("id") ON DELETE cascade ON UPDATE no action;--> statement-breakpoint
ALTER TABLE "user_roles" ADD CONSTRAINT "user_roles_user_id_fk" FOREIGN KEY ("user_id") REFERENCES "public"."users"("id") ON DELETE restrict ON UPDATE no action;--> statement-breakpoint
ALTER TABLE "work_approval_evidence" ADD CONSTRAINT "work_approval_evidence_tenant_id_fk" FOREIGN KEY ("tenant_id") REFERENCES "public"."tenants"("id") ON DELETE restrict ON UPDATE no action;--> statement-breakpoint
ALTER TABLE "work_approval_evidence" ADD CONSTRAINT "work_approval_evidence_approval_id_fk" FOREIGN KEY ("tenant_id","approval_id") REFERENCES "public"."work_approvals"("tenant_id","id") ON DELETE restrict ON UPDATE no action;--> statement-breakpoint
ALTER TABLE "work_approval_evidence" ADD CONSTRAINT "work_approval_evidence_evidence_id_fk" FOREIGN KEY ("tenant_id","evidence_id") REFERENCES "public"."evidence_items"("tenant_id","id") ON DELETE restrict ON UPDATE no action;--> statement-breakpoint
ALTER TABLE "work_approval_evidence" ADD CONSTRAINT "work_approval_evidence_original_object_id_fk" FOREIGN KEY ("tenant_id","original_object_id") REFERENCES "public"."file_objects"("tenant_id","id") ON DELETE restrict ON UPDATE no action;--> statement-breakpoint
ALTER TABLE "work_approvals" ADD CONSTRAINT "work_approvals_tenant_id_fk" FOREIGN KEY ("tenant_id") REFERENCES "public"."tenants"("id") ON DELETE restrict ON UPDATE no action;--> statement-breakpoint
ALTER TABLE "work_approvals" ADD CONSTRAINT "work_approvals_work_order_id_fk" FOREIGN KEY ("tenant_id","work_order_id") REFERENCES "public"."work_orders"("tenant_id","id") ON DELETE restrict ON UPDATE no action;--> statement-breakpoint
ALTER TABLE "work_approvals" ADD CONSTRAINT "work_approvals_requested_to_user_id_fk" FOREIGN KEY ("requested_to_user_id") REFERENCES "public"."users"("id") ON DELETE restrict ON UPDATE no action;--> statement-breakpoint
ALTER TABLE "work_approvals" ADD CONSTRAINT "work_approvals_required_scope_id_fk" FOREIGN KEY ("tenant_id","required_scope_id") REFERENCES "public"."access_scopes"("tenant_id","id") ON DELETE restrict ON UPDATE no action;--> statement-breakpoint
ALTER TABLE "work_approvals" ADD CONSTRAINT "work_approvals_decided_by_fk" FOREIGN KEY ("decided_by") REFERENCES "public"."users"("id") ON DELETE restrict ON UPDATE no action;--> statement-breakpoint
ALTER TABLE "work_approvals" ADD CONSTRAINT "work_approvals_decided_event_id_fk" FOREIGN KEY ("tenant_id","decided_event_id") REFERENCES "public"."ticket_events"("tenant_id","id") ON DELETE restrict ON UPDATE no action;--> statement-breakpoint
ALTER TABLE "work_assignments" ADD CONSTRAINT "work_assignments_tenant_id_fk" FOREIGN KEY ("tenant_id") REFERENCES "public"."tenants"("id") ON DELETE restrict ON UPDATE no action;--> statement-breakpoint
ALTER TABLE "work_assignments" ADD CONSTRAINT "work_assignments_work_order_id_fk" FOREIGN KEY ("tenant_id","work_order_id") REFERENCES "public"."work_orders"("tenant_id","id") ON DELETE restrict ON UPDATE no action;--> statement-breakpoint
ALTER TABLE "work_assignments" ADD CONSTRAINT "work_assignments_staff_id_fk" FOREIGN KEY ("tenant_id","staff_id") REFERENCES "public"."staff_profiles"("tenant_id","id") ON DELETE restrict ON UPDATE no action;--> statement-breakpoint
ALTER TABLE "work_assignments" ADD CONSTRAINT "work_assignments_assigned_by_user_id_fk" FOREIGN KEY ("assigned_by_user_id") REFERENCES "public"."users"("id") ON DELETE restrict ON UPDATE no action;--> statement-breakpoint
ALTER TABLE "work_assignments" ADD CONSTRAINT "work_assignments_assigned_by_agent_id_fk" FOREIGN KEY ("tenant_id","assigned_by_agent_id") REFERENCES "public"."agents"("tenant_id","id") ON DELETE restrict ON UPDATE no action;--> statement-breakpoint
ALTER TABLE "work_assignments" ADD CONSTRAINT "work_assignments_dispatch_attempt_id_fk" FOREIGN KEY ("tenant_id","dispatch_attempt_id") REFERENCES "public"."dispatch_attempts"("tenant_id","id") ON DELETE restrict ON UPDATE no action;--> statement-breakpoint
ALTER TABLE "work_items" ADD CONSTRAINT "work_items_tenant_id_fk" FOREIGN KEY ("tenant_id") REFERENCES "public"."tenants"("id") ON DELETE restrict ON UPDATE no action;--> statement-breakpoint
ALTER TABLE "work_orders" ADD CONSTRAINT "work_orders_tenant_id_fk" FOREIGN KEY ("tenant_id") REFERENCES "public"."tenants"("id") ON DELETE restrict ON UPDATE no action;--> statement-breakpoint
ALTER TABLE "work_orders" ADD CONSTRAINT "work_orders_ticket_id_fk" FOREIGN KEY ("tenant_id","ticket_id") REFERENCES "public"."tickets"("tenant_id","id") ON DELETE restrict ON UPDATE no action;--> statement-breakpoint
ALTER TABLE "work_orders" ADD CONSTRAINT "work_orders_category_id_fk" FOREIGN KEY ("tenant_id","category_id") REFERENCES "public"."service_categories"("tenant_id","id") ON DELETE restrict ON UPDATE no action;--> statement-breakpoint
ALTER TABLE "work_orders" ADD CONSTRAINT "work_orders_required_specialty_id_fk" FOREIGN KEY ("tenant_id","required_specialty_id") REFERENCES "public"."service_categories"("tenant_id","id") ON DELETE restrict ON UPDATE no action;--> statement-breakpoint
ALTER TABLE "work_reassignment_requests" ADD CONSTRAINT "work_reassignment_requests_tenant_id_fk" FOREIGN KEY ("tenant_id") REFERENCES "public"."tenants"("id") ON DELETE restrict ON UPDATE no action;--> statement-breakpoint
ALTER TABLE "work_reassignment_requests" ADD CONSTRAINT "work_reassignment_requests_source_assignment_id_fk" FOREIGN KEY ("tenant_id","source_assignment_id") REFERENCES "public"."work_assignments"("tenant_id","id") ON DELETE restrict ON UPDATE no action;--> statement-breakpoint
ALTER TABLE "work_reassignment_requests" ADD CONSTRAINT "work_reassignment_requests_target_work_order_id_fk" FOREIGN KEY ("tenant_id","target_work_order_id") REFERENCES "public"."work_orders"("tenant_id","id") ON DELETE restrict ON UPDATE no action;--> statement-breakpoint
ALTER TABLE "work_reassignment_requests" ADD CONSTRAINT "work_reassignment_requests_target_decision_id_fk" FOREIGN KEY ("tenant_id","target_decision_id") REFERENCES "public"."ticket_triage_decisions"("tenant_id","id") ON DELETE restrict ON UPDATE no action;--> statement-breakpoint
ALTER TABLE "work_reassignment_requests" ADD CONSTRAINT "work_reassignment_requests_requested_by_fk" FOREIGN KEY ("requested_by") REFERENCES "public"."users"("id") ON DELETE restrict ON UPDATE no action;--> statement-breakpoint
ALTER TABLE "work_reassignment_requests" ADD CONSTRAINT "work_reassignment_requests_source_run_id_fk" FOREIGN KEY ("tenant_id","source_run_id") REFERENCES "public"."agent_runs"("tenant_id","id") ON DELETE restrict ON UPDATE no action;--> statement-breakpoint
ALTER TABLE "work_reassignment_requests" ADD CONSTRAINT "work_reassignment_requests_approved_by_fk" FOREIGN KEY ("approved_by") REFERENCES "public"."users"("id") ON DELETE restrict ON UPDATE no action;--> statement-breakpoint
ALTER TABLE "work_reassignment_requests" ADD CONSTRAINT "work_reassignment_requests_safe_stop_confirmed_by_fk" FOREIGN KEY ("safe_stop_confirmed_by") REFERENCES "public"."users"("id") ON DELETE restrict ON UPDATE no action;--> statement-breakpoint
ALTER TABLE "work_reassignment_requests" ADD CONSTRAINT "work_reassignment_requests_new_assignment_id_fk" FOREIGN KEY ("tenant_id","new_assignment_id") REFERENCES "public"."work_assignments"("tenant_id","id") ON DELETE restrict ON UPDATE no action;--> statement-breakpoint
ALTER TABLE "workspace_members" ADD CONSTRAINT "workspace_members_tenant_id_fk" FOREIGN KEY ("tenant_id") REFERENCES "public"."tenants"("id") ON DELETE restrict ON UPDATE no action;--> statement-breakpoint
ALTER TABLE "workspace_members" ADD CONSTRAINT "workspace_members_workspace_id_fk" FOREIGN KEY ("tenant_id","workspace_id") REFERENCES "public"."workspaces"("tenant_id","id") ON DELETE restrict ON UPDATE no action;--> statement-breakpoint
ALTER TABLE "workspace_members" ADD CONSTRAINT "workspace_members_user_id_fk" FOREIGN KEY ("user_id") REFERENCES "public"."users"("id") ON DELETE restrict ON UPDATE no action;--> statement-breakpoint
ALTER TABLE "workspaces" ADD CONSTRAINT "workspaces_tenant_id_fk" FOREIGN KEY ("tenant_id") REFERENCES "public"."tenants"("id") ON DELETE restrict ON UPDATE no action;--> statement-breakpoint
ALTER TABLE "workspaces" ADD CONSTRAINT "workspaces_management_unit_id_fk" FOREIGN KEY ("tenant_id","management_unit_id") REFERENCES "public"."management_units"("tenant_id","id") ON DELETE restrict ON UPDATE no action;--> statement-breakpoint
ALTER TABLE "zones" ADD CONSTRAINT "zones_tenant_id_fk" FOREIGN KEY ("tenant_id") REFERENCES "public"."tenants"("id") ON DELETE restrict ON UPDATE no action;--> statement-breakpoint
ALTER TABLE "zones" ADD CONSTRAINT "zones_site_id_fk" FOREIGN KEY ("tenant_id","site_id") REFERENCES "public"."sites"("tenant_id","id") ON DELETE restrict ON UPDATE no action;--> statement-breakpoint
CREATE UNIQUE INDEX "access_scopes_partial_0" ON "access_scopes" USING btree ("tenant_id") WHERE kind='tenant';--> statement-breakpoint
CREATE UNIQUE INDEX "access_scopes_partial_1" ON "access_scopes" USING btree ("tenant_id","management_unit_id") WHERE kind='management';--> statement-breakpoint
CREATE UNIQUE INDEX "access_scopes_partial_2" ON "access_scopes" USING btree ("tenant_id","site_id") WHERE kind='site';--> statement-breakpoint
CREATE UNIQUE INDEX "access_scopes_partial_3" ON "access_scopes" USING btree ("tenant_id","zone_id") WHERE kind='zone';--> statement-breakpoint
CREATE UNIQUE INDEX "access_scopes_partial_4" ON "access_scopes" USING btree ("tenant_id","building_id") WHERE kind='building';--> statement-breakpoint
CREATE INDEX "account_reviews_user_id_idx" ON "account_reviews" USING btree ("tenant_id","user_id");--> statement-breakpoint
CREATE INDEX "accounts_user_id_idx" ON "accounts" USING btree ("user_id");--> statement-breakpoint
CREATE INDEX "agent_build_requests_workspace_id_idx" ON "agent_build_requests" USING btree ("tenant_id","workspace_id");--> statement-breakpoint
CREATE UNIQUE INDEX "agent_releases_partial_0" ON "agent_releases" USING btree ("agent_id") WHERE status='published' AND revoked_at IS NULL;--> statement-breakpoint
CREATE INDEX "agent_teams_ticket_id_idx" ON "agent_teams" USING btree ("tenant_id","ticket_id");--> statement-breakpoint
CREATE INDEX "agent_teams_workspace_id_idx" ON "agent_teams" USING btree ("tenant_id","workspace_id");--> statement-breakpoint
CREATE UNIQUE INDEX "agents_partial_0" ON "agents" USING btree ("tenant_id") WHERE purpose='reception' AND status='active';--> statement-breakpoint
CREATE INDEX "agents_workspace_id_idx" ON "agents" USING btree ("tenant_id","workspace_id");--> statement-breakpoint
CREATE INDEX "audit_events_workspace_id_idx" ON "audit_events" USING btree ("tenant_id","workspace_id");--> statement-breakpoint
CREATE UNIQUE INDEX "channels_partial_0" ON "channels" USING btree ("workspace_id") WHERE is_dispatch_default AND deleted_at IS NULL;--> statement-breakpoint
CREATE INDEX "channels_workspace_id_idx" ON "channels" USING btree ("tenant_id","workspace_id");--> statement-breakpoint
CREATE INDEX "context_snapshots_ticket_id_idx" ON "context_snapshots" USING btree ("tenant_id","ticket_id");--> statement-breakpoint
CREATE INDEX "context_snapshots_run_id_idx" ON "context_snapshots" USING btree ("tenant_id","run_id");--> statement-breakpoint
CREATE UNIQUE INDEX "credentials_partial_0" ON "credentials" USING btree ("kind","provider","key_id") WHERE scope_kind='platform' AND revoked_at IS NULL;--> statement-breakpoint
CREATE UNIQUE INDEX "credentials_partial_1" ON "credentials" USING btree ("tenant_id","kind","provider","key_id") WHERE scope_kind='tenant' AND revoked_at IS NULL;--> statement-breakpoint
CREATE UNIQUE INDEX "credentials_partial_2" ON "credentials" USING btree ("tenant_id","workspace_id","kind","provider","key_id") WHERE scope_kind='workspace' AND revoked_at IS NULL;--> statement-breakpoint
CREATE INDEX "credentials_workspace_id_idx" ON "credentials" USING btree ("tenant_id","workspace_id");--> statement-breakpoint
CREATE INDEX "document_acl_workspace_id_idx" ON "document_acl" USING btree ("tenant_id","workspace_id");--> statement-breakpoint
CREATE INDEX "document_acl_user_id_idx" ON "document_acl" USING btree ("tenant_id","user_id");--> statement-breakpoint
CREATE INDEX "evidence_items_ticket_id_idx" ON "evidence_items" USING btree ("tenant_id","ticket_id");--> statement-breakpoint
CREATE UNIQUE INDEX "execution_principals_partial_0" ON "execution_principals" USING btree ("tenant_id","user_id") WHERE kind='user';--> statement-breakpoint
CREATE UNIQUE INDEX "execution_principals_partial_1" ON "execution_principals" USING btree ("tenant_id","workspace_id") WHERE kind='workspace_service';--> statement-breakpoint
CREATE INDEX "execution_principals_workspace_id_idx" ON "execution_principals" USING btree ("tenant_id","workspace_id");--> statement-breakpoint
CREATE INDEX "execution_principals_user_id_idx" ON "execution_principals" USING btree ("tenant_id","user_id");--> statement-breakpoint
CREATE INDEX "file_access_logs_run_id_idx" ON "file_access_logs" USING btree ("tenant_id","run_id");--> statement-breakpoint
CREATE UNIQUE INDEX "file_deletion_requests_partial_0" ON "file_deletion_requests" USING btree ("file_id") WHERE status IN ('pending','running','blocked');--> statement-breakpoint
CREATE UNIQUE INDEX "file_uploads_partial_0" ON "file_uploads" USING btree ("file_id") WHERE status IN ('issued','uploading','uploaded','verifying');--> statement-breakpoint
CREATE INDEX "files_ticket_id_idx" ON "files" USING btree ("tenant_id","ticket_id");--> statement-breakpoint
CREATE INDEX "invoices_ticket_id_idx" ON "invoices" USING btree ("tenant_id","ticket_id");--> statement-breakpoint
CREATE UNIQUE INDEX "knowledge_reviews_partial_0" ON "knowledge_reviews" USING btree ("document_version_id","subject_seq") WHERE document_version_id IS NOT NULL;--> statement-breakpoint
CREATE UNIQUE INDEX "knowledge_reviews_partial_1" ON "knowledge_reviews" USING btree ("memory_candidate_id","subject_seq") WHERE memory_candidate_id IS NOT NULL;--> statement-breakpoint
CREATE INDEX "mcp_servers_workspace_id_idx" ON "mcp_servers" USING btree ("tenant_id","workspace_id");--> statement-breakpoint
CREATE UNIQUE INDEX "memory_candidates_partial_0" ON "memory_candidates" USING btree ("supersedes_candidate_id") WHERE supersedes_candidate_id IS NOT NULL;--> statement-breakpoint
CREATE INDEX "memory_candidates_namespace_id_idx" ON "memory_candidates" USING btree ("tenant_id","namespace_id");--> statement-breakpoint
CREATE UNIQUE INDEX "memory_namespaces_partial_0" ON "memory_namespaces" USING btree ("owner_principal_id","kind","purpose") WHERE kind='personal';--> statement-breakpoint
CREATE UNIQUE INDEX "memory_namespaces_partial_1" ON "memory_namespaces" USING btree ("team_id","purpose") WHERE kind='team';--> statement-breakpoint
CREATE UNIQUE INDEX "memory_namespaces_partial_2" ON "memory_namespaces" USING btree ("workspace_id","purpose") WHERE kind='workspace';--> statement-breakpoint
CREATE INDEX "memory_namespaces_workspace_id_idx" ON "memory_namespaces" USING btree ("tenant_id","workspace_id");--> statement-breakpoint
CREATE INDEX "memory_publications_namespace_id_idx" ON "memory_publications" USING btree ("tenant_id","namespace_id");--> statement-breakpoint
CREATE INDEX "messages_run_id_idx" ON "messages" USING btree ("tenant_id","run_id");--> statement-breakpoint
CREATE UNIQUE INDEX "model_profiles_partial_0" ON "model_profiles" USING btree ("tenant_id","code") WHERE workspace_id IS NULL;--> statement-breakpoint
CREATE UNIQUE INDEX "model_profiles_partial_1" ON "model_profiles" USING btree ("workspace_id","code") WHERE workspace_id IS NOT NULL;--> statement-breakpoint
CREATE INDEX "model_profiles_workspace_id_idx" ON "model_profiles" USING btree ("tenant_id","workspace_id");--> statement-breakpoint
CREATE INDEX "notification_deliveries_user_id_idx" ON "notification_deliveries" USING btree ("tenant_id","user_id");--> statement-breakpoint
CREATE UNIQUE INDEX "reception_waits_partial_0" ON "reception_waits" USING btree ("session_id") WHERE status IN ('preparing','open','resuming');--> statement-breakpoint
CREATE INDEX "reception_waits_ticket_id_idx" ON "reception_waits" USING btree ("tenant_id","ticket_id");--> statement-breakpoint
CREATE INDEX "report_requests_run_id_idx" ON "report_requests" USING btree ("tenant_id","run_id");--> statement-breakpoint
CREATE INDEX "report_requests_workspace_id_idx" ON "report_requests" USING btree ("tenant_id","workspace_id");--> statement-breakpoint
CREATE INDEX "routine_runs_workspace_id_idx" ON "routine_runs" USING btree ("tenant_id","workspace_id");--> statement-breakpoint
CREATE INDEX "routines_workspace_id_idx" ON "routines" USING btree ("tenant_id","workspace_id");--> statement-breakpoint
CREATE INDEX "run_memory_access_run_id_idx" ON "run_memory_access" USING btree ("tenant_id","run_id");--> statement-breakpoint
CREATE INDEX "run_memory_access_namespace_id_idx" ON "run_memory_access" USING btree ("tenant_id","namespace_id");--> statement-breakpoint
CREATE INDEX "runtime_memory_bindings_namespace_id_idx" ON "runtime_memory_bindings" USING btree ("tenant_id","namespace_id");--> statement-breakpoint
CREATE UNIQUE INDEX "runtime_session_bindings_partial_0" ON "runtime_session_bindings" USING btree ("tenant_id","channel_id","agent_id") WHERE audience_kind='personal' AND status IN ('active','provisioning','interrupted');--> statement-breakpoint
CREATE UNIQUE INDEX "runtime_session_bindings_partial_1" ON "runtime_session_bindings" USING btree ("team_member_id") WHERE audience_kind='team' AND status IN ('active','provisioning','interrupted');--> statement-breakpoint
CREATE INDEX "sandboxed_components_workspace_id_idx" ON "sandboxed_components" USING btree ("tenant_id","workspace_id");--> statement-breakpoint
CREATE INDEX "sessions_user_id_idx" ON "sessions" USING btree ("user_id");--> statement-breakpoint
CREATE UNIQUE INDEX "skills_partial_0" ON "skills" USING btree ("tenant_id","slug") WHERE workspace_id IS NULL AND owner_user_id IS NULL;--> statement-breakpoint
CREATE UNIQUE INDEX "skills_partial_1" ON "skills" USING btree ("tenant_id","owner_user_id","slug") WHERE workspace_id IS NULL AND owner_user_id IS NOT NULL;--> statement-breakpoint
CREATE UNIQUE INDEX "skills_partial_2" ON "skills" USING btree ("tenant_id","workspace_id","slug") WHERE workspace_id IS NOT NULL AND owner_user_id IS NULL;--> statement-breakpoint
CREATE UNIQUE INDEX "skills_partial_3" ON "skills" USING btree ("tenant_id","workspace_id","owner_user_id","slug") WHERE workspace_id IS NOT NULL AND owner_user_id IS NOT NULL;--> statement-breakpoint
CREATE INDEX "skills_workspace_id_idx" ON "skills" USING btree ("tenant_id","workspace_id");--> statement-breakpoint
CREATE INDEX "sso_providers_user_id_idx" ON "sso_providers" USING btree ("user_id");--> statement-breakpoint
CREATE INDEX "staff_profiles_user_id_idx" ON "staff_profiles" USING btree ("tenant_id","user_id");--> statement-breakpoint
CREATE INDEX "team_tasks_ticket_id_idx" ON "team_tasks" USING btree ("tenant_id","ticket_id");--> statement-breakpoint
CREATE INDEX "tenant_memberships_user_id_idx" ON "tenant_memberships" USING btree ("tenant_id","user_id");--> statement-breakpoint
CREATE UNIQUE INDEX "ticket_assessment_evidence_partial_0" ON "ticket_assessment_evidence" USING btree ("assessment_id","fact_key","message_id") WHERE message_id IS NOT NULL;--> statement-breakpoint
CREATE UNIQUE INDEX "ticket_assessment_evidence_partial_1" ON "ticket_assessment_evidence" USING btree ("assessment_id","fact_key","event_id") WHERE event_id IS NOT NULL;--> statement-breakpoint
CREATE UNIQUE INDEX "ticket_assessment_evidence_partial_2" ON "ticket_assessment_evidence" USING btree ("assessment_id","fact_key","evidence_item_id") WHERE evidence_item_id IS NOT NULL;--> statement-breakpoint
CREATE INDEX "ticket_assessments_ticket_id_idx" ON "ticket_assessments" USING btree ("tenant_id","ticket_id");--> statement-breakpoint
CREATE INDEX "ticket_escalations_ticket_id_idx" ON "ticket_escalations" USING btree ("tenant_id","ticket_id");--> statement-breakpoint
CREATE INDEX "ticket_events_ticket_id_idx" ON "ticket_events" USING btree ("tenant_id","ticket_id");--> statement-breakpoint
CREATE INDEX "ticket_reviews_ticket_id_idx" ON "ticket_reviews" USING btree ("tenant_id","ticket_id");--> statement-breakpoint
CREATE INDEX "ticket_routing_history_ticket_id_idx" ON "ticket_routing_history" USING btree ("tenant_id","ticket_id");--> statement-breakpoint
CREATE INDEX "ticket_sla_cycles_ticket_id_idx" ON "ticket_sla_cycles" USING btree ("tenant_id","ticket_id");--> statement-breakpoint
CREATE UNIQUE INDEX "ticket_triage_decisions_partial_0" ON "ticket_triage_decisions" USING btree ("review_id") WHERE review_id IS NOT NULL AND outcome='applied';--> statement-breakpoint
CREATE INDEX "ticket_triage_decisions_ticket_id_idx" ON "ticket_triage_decisions" USING btree ("tenant_id","ticket_id");--> statement-breakpoint
CREATE INDEX "ticket_triage_reviews_ticket_id_idx" ON "ticket_triage_reviews" USING btree ("tenant_id","ticket_id");--> statement-breakpoint
CREATE INDEX "unit_residents_user_id_idx" ON "unit_residents" USING btree ("tenant_id","user_id");--> statement-breakpoint
CREATE UNIQUE INDEX "units_partial_0" ON "units" USING btree ("building_id","code") WHERE building_id IS NOT NULL;--> statement-breakpoint
CREATE UNIQUE INDEX "units_partial_1" ON "units" USING btree ("zone_id","code") WHERE building_id IS NULL;--> statement-breakpoint
CREATE UNIQUE INDEX "users_partial_0" ON "users" USING btree (lower(email)) WHERE email IS NOT NULL;--> statement-breakpoint
CREATE UNIQUE INDEX "users_partial_1" ON "users" USING btree ("phone_e164") WHERE phone_e164 IS NOT NULL;--> statement-breakpoint
CREATE UNIQUE INDEX "work_assignments_partial_0" ON "work_assignments" USING btree ("work_order_id") WHERE status IN ('offered','accepted');--> statement-breakpoint
CREATE INDEX "work_orders_ticket_id_idx" ON "work_orders" USING btree ("tenant_id","ticket_id");--> statement-breakpoint
CREATE UNIQUE INDEX "work_reassignment_requests_partial_0" ON "work_reassignment_requests" USING btree ("source_assignment_id") WHERE status IN ('requested','approved','executing');--> statement-breakpoint
CREATE POLICY "access_scopes_tenant_policy" ON "access_scopes" AS PERMISSIVE FOR ALL TO public USING (tenant_id = nullif(current_setting('app.tenant_id', true), '')::uuid) WITH CHECK (tenant_id = nullif(current_setting('app.tenant_id', true), '')::uuid);--> statement-breakpoint
CREATE POLICY "account_reviews_tenant_policy" ON "account_reviews" AS PERMISSIVE FOR ALL TO public USING (tenant_id = nullif(current_setting('app.tenant_id', true), '')::uuid) WITH CHECK (tenant_id = nullif(current_setting('app.tenant_id', true), '')::uuid);--> statement-breakpoint
CREATE POLICY "agent_build_answers_tenant_policy" ON "agent_build_answers" AS PERMISSIVE FOR ALL TO public USING (tenant_id = nullif(current_setting('app.tenant_id', true), '')::uuid) WITH CHECK (tenant_id = nullif(current_setting('app.tenant_id', true), '')::uuid);--> statement-breakpoint
CREATE POLICY "agent_build_requests_tenant_policy" ON "agent_build_requests" AS PERMISSIVE FOR ALL TO public USING (tenant_id = nullif(current_setting('app.tenant_id', true), '')::uuid) WITH CHECK (tenant_id = nullif(current_setting('app.tenant_id', true), '')::uuid);--> statement-breakpoint
CREATE POLICY "agent_knowledge_grants_tenant_policy" ON "agent_knowledge_grants" AS PERMISSIVE FOR ALL TO public USING (tenant_id = nullif(current_setting('app.tenant_id', true), '')::uuid) WITH CHECK (tenant_id = nullif(current_setting('app.tenant_id', true), '')::uuid);--> statement-breakpoint
CREATE POLICY "agent_preferences_tenant_policy" ON "agent_preferences" AS PERMISSIVE FOR ALL TO public USING (tenant_id = nullif(current_setting('app.tenant_id', true), '')::uuid) WITH CHECK (tenant_id = nullif(current_setting('app.tenant_id', true), '')::uuid);--> statement-breakpoint
CREATE POLICY "agent_profiles_tenant_policy" ON "agent_profiles" AS PERMISSIVE FOR ALL TO public USING (tenant_id = nullif(current_setting('app.tenant_id', true), '')::uuid) WITH CHECK (tenant_id = nullif(current_setting('app.tenant_id', true), '')::uuid);--> statement-breakpoint
CREATE POLICY "agent_releases_tenant_policy" ON "agent_releases" AS PERMISSIVE FOR ALL TO public USING (tenant_id = nullif(current_setting('app.tenant_id', true), '')::uuid) WITH CHECK (tenant_id = nullif(current_setting('app.tenant_id', true), '')::uuid);--> statement-breakpoint
CREATE POLICY "agent_runs_tenant_policy" ON "agent_runs" AS PERMISSIVE FOR ALL TO public USING (tenant_id = nullif(current_setting('app.tenant_id', true), '')::uuid) WITH CHECK (tenant_id = nullif(current_setting('app.tenant_id', true), '')::uuid);--> statement-breakpoint
CREATE POLICY "agent_teams_tenant_policy" ON "agent_teams" AS PERMISSIVE FOR ALL TO public USING (tenant_id = nullif(current_setting('app.tenant_id', true), '')::uuid) WITH CHECK (tenant_id = nullif(current_setting('app.tenant_id', true), '')::uuid);--> statement-breakpoint
CREATE POLICY "agent_versions_tenant_policy" ON "agent_versions" AS PERMISSIVE FOR ALL TO public USING (tenant_id = nullif(current_setting('app.tenant_id', true), '')::uuid) WITH CHECK (tenant_id = nullif(current_setting('app.tenant_id', true), '')::uuid);--> statement-breakpoint
CREATE POLICY "agents_tenant_policy" ON "agents" AS PERMISSIVE FOR ALL TO public USING (tenant_id = nullif(current_setting('app.tenant_id', true), '')::uuid) WITH CHECK (tenant_id = nullif(current_setting('app.tenant_id', true), '')::uuid);--> statement-breakpoint
CREATE POLICY "audit_events_tenant_policy" ON "audit_events" AS PERMISSIVE FOR ALL TO public USING (tenant_id = nullif(current_setting('app.tenant_id', true), '')::uuid OR tenant_id IS NULL) WITH CHECK (tenant_id = nullif(current_setting('app.tenant_id', true), '')::uuid OR tenant_id IS NULL);--> statement-breakpoint
CREATE POLICY "buildings_tenant_policy" ON "buildings" AS PERMISSIVE FOR ALL TO public USING (tenant_id = nullif(current_setting('app.tenant_id', true), '')::uuid) WITH CHECK (tenant_id = nullif(current_setting('app.tenant_id', true), '')::uuid);--> statement-breakpoint
CREATE POLICY "channel_agents_tenant_policy" ON "channel_agents" AS PERMISSIVE FOR ALL TO public USING (tenant_id = nullif(current_setting('app.tenant_id', true), '')::uuid) WITH CHECK (tenant_id = nullif(current_setting('app.tenant_id', true), '')::uuid);--> statement-breakpoint
CREATE POLICY "channel_memberships_tenant_policy" ON "channel_memberships" AS PERMISSIVE FOR ALL TO public USING (tenant_id = nullif(current_setting('app.tenant_id', true), '')::uuid) WITH CHECK (tenant_id = nullif(current_setting('app.tenant_id', true), '')::uuid);--> statement-breakpoint
CREATE POLICY "channels_tenant_policy" ON "channels" AS PERMISSIVE FOR ALL TO public USING (tenant_id = nullif(current_setting('app.tenant_id', true), '')::uuid) WITH CHECK (tenant_id = nullif(current_setting('app.tenant_id', true), '')::uuid);--> statement-breakpoint
CREATE POLICY "component_exclusions_tenant_policy" ON "component_exclusions" AS PERMISSIVE FOR ALL TO public USING (tenant_id = nullif(current_setting('app.tenant_id', true), '')::uuid) WITH CHECK (tenant_id = nullif(current_setting('app.tenant_id', true), '')::uuid);--> statement-breakpoint
CREATE POLICY "composio_connections_tenant_policy" ON "composio_connections" AS PERMISSIVE FOR ALL TO public USING (tenant_id = nullif(current_setting('app.tenant_id', true), '')::uuid) WITH CHECK (tenant_id = nullif(current_setting('app.tenant_id', true), '')::uuid);--> statement-breakpoint
CREATE POLICY "computer_page_frame_tenant_policy" ON "computer_page_frame" AS PERMISSIVE FOR ALL TO public USING (tenant_id = nullif(current_setting('app.tenant_id', true), '')::uuid) WITH CHECK (tenant_id = nullif(current_setting('app.tenant_id', true), '')::uuid);--> statement-breakpoint
CREATE POLICY "computer_snapshot_tenant_policy" ON "computer_snapshot" AS PERMISSIVE FOR ALL TO public USING (tenant_id = nullif(current_setting('app.tenant_id', true), '')::uuid) WITH CHECK (tenant_id = nullif(current_setting('app.tenant_id', true), '')::uuid);--> statement-breakpoint
CREATE POLICY "context_snapshots_tenant_policy" ON "context_snapshots" AS PERMISSIVE FOR ALL TO public USING (tenant_id = nullif(current_setting('app.tenant_id', true), '')::uuid) WITH CHECK (tenant_id = nullif(current_setting('app.tenant_id', true), '')::uuid);--> statement-breakpoint
CREATE POLICY "credentials_tenant_policy" ON "credentials" AS PERMISSIVE FOR ALL TO public USING (tenant_id = nullif(current_setting('app.tenant_id', true), '')::uuid OR tenant_id IS NULL) WITH CHECK (tenant_id = nullif(current_setting('app.tenant_id', true), '')::uuid OR tenant_id IS NULL);--> statement-breakpoint
CREATE POLICY "deployment_packages_tenant_policy" ON "deployment_packages" AS PERMISSIVE FOR ALL TO public USING (tenant_id = nullif(current_setting('app.tenant_id', true), '')::uuid) WITH CHECK (tenant_id = nullif(current_setting('app.tenant_id', true), '')::uuid);--> statement-breakpoint
CREATE POLICY "dispatch_attempts_tenant_policy" ON "dispatch_attempts" AS PERMISSIVE FOR ALL TO public USING (tenant_id = nullif(current_setting('app.tenant_id', true), '')::uuid) WITH CHECK (tenant_id = nullif(current_setting('app.tenant_id', true), '')::uuid);--> statement-breakpoint
CREATE POLICY "dispatch_queue_tenant_policy" ON "dispatch_queue" AS PERMISSIVE FOR ALL TO public USING (tenant_id = nullif(current_setting('app.tenant_id', true), '')::uuid) WITH CHECK (tenant_id = nullif(current_setting('app.tenant_id', true), '')::uuid);--> statement-breakpoint
CREATE POLICY "document_acl_tenant_policy" ON "document_acl" AS PERMISSIVE FOR ALL TO public USING (tenant_id = nullif(current_setting('app.tenant_id', true), '')::uuid) WITH CHECK (tenant_id = nullif(current_setting('app.tenant_id', true), '')::uuid);--> statement-breakpoint
CREATE POLICY "document_scopes_tenant_policy" ON "document_scopes" AS PERMISSIVE FOR ALL TO public USING (tenant_id = nullif(current_setting('app.tenant_id', true), '')::uuid) WITH CHECK (tenant_id = nullif(current_setting('app.tenant_id', true), '')::uuid);--> statement-breakpoint
CREATE POLICY "document_versions_tenant_policy" ON "document_versions" AS PERMISSIVE FOR ALL TO public USING (tenant_id = nullif(current_setting('app.tenant_id', true), '')::uuid) WITH CHECK (tenant_id = nullif(current_setting('app.tenant_id', true), '')::uuid);--> statement-breakpoint
CREATE POLICY "domains_tenant_policy" ON "domains" AS PERMISSIVE FOR ALL TO public USING (tenant_id = nullif(current_setting('app.tenant_id', true), '')::uuid) WITH CHECK (tenant_id = nullif(current_setting('app.tenant_id', true), '')::uuid);--> statement-breakpoint
CREATE POLICY "event_inbox_tenant_policy" ON "event_inbox" AS PERMISSIVE FOR ALL TO public USING (tenant_id = nullif(current_setting('app.tenant_id', true), '')::uuid) WITH CHECK (tenant_id = nullif(current_setting('app.tenant_id', true), '')::uuid);--> statement-breakpoint
CREATE POLICY "event_outbox_tenant_policy" ON "event_outbox" AS PERMISSIVE FOR ALL TO public USING (tenant_id = nullif(current_setting('app.tenant_id', true), '')::uuid) WITH CHECK (tenant_id = nullif(current_setting('app.tenant_id', true), '')::uuid);--> statement-breakpoint
CREATE POLICY "evidence_items_tenant_policy" ON "evidence_items" AS PERMISSIVE FOR ALL TO public USING (tenant_id = nullif(current_setting('app.tenant_id', true), '')::uuid) WITH CHECK (tenant_id = nullif(current_setting('app.tenant_id', true), '')::uuid);--> statement-breakpoint
CREATE POLICY "execution_principals_tenant_policy" ON "execution_principals" AS PERMISSIVE FOR ALL TO public USING (tenant_id = nullif(current_setting('app.tenant_id', true), '')::uuid) WITH CHECK (tenant_id = nullif(current_setting('app.tenant_id', true), '')::uuid);--> statement-breakpoint
CREATE POLICY "file_access_logs_tenant_policy" ON "file_access_logs" AS PERMISSIVE FOR ALL TO public USING (tenant_id = nullif(current_setting('app.tenant_id', true), '')::uuid) WITH CHECK (tenant_id = nullif(current_setting('app.tenant_id', true), '')::uuid);--> statement-breakpoint
CREATE POLICY "file_deletion_requests_tenant_policy" ON "file_deletion_requests" AS PERMISSIVE FOR ALL TO public USING (tenant_id = nullif(current_setting('app.tenant_id', true), '')::uuid) WITH CHECK (tenant_id = nullif(current_setting('app.tenant_id', true), '')::uuid);--> statement-breakpoint
CREATE POLICY "file_objects_tenant_policy" ON "file_objects" AS PERMISSIVE FOR ALL TO public USING (tenant_id = nullif(current_setting('app.tenant_id', true), '')::uuid) WITH CHECK (tenant_id = nullif(current_setting('app.tenant_id', true), '')::uuid);--> statement-breakpoint
CREATE POLICY "file_processing_jobs_tenant_policy" ON "file_processing_jobs" AS PERMISSIVE FOR ALL TO public USING (tenant_id = nullif(current_setting('app.tenant_id', true), '')::uuid) WITH CHECK (tenant_id = nullif(current_setting('app.tenant_id', true), '')::uuid);--> statement-breakpoint
CREATE POLICY "file_upload_parts_tenant_policy" ON "file_upload_parts" AS PERMISSIVE FOR ALL TO public USING (tenant_id = nullif(current_setting('app.tenant_id', true), '')::uuid) WITH CHECK (tenant_id = nullif(current_setting('app.tenant_id', true), '')::uuid);--> statement-breakpoint
CREATE POLICY "file_uploads_tenant_policy" ON "file_uploads" AS PERMISSIVE FOR ALL TO public USING (tenant_id = nullif(current_setting('app.tenant_id', true), '')::uuid) WITH CHECK (tenant_id = nullif(current_setting('app.tenant_id', true), '')::uuid);--> statement-breakpoint
CREATE POLICY "files_tenant_policy" ON "files" AS PERMISSIVE FOR ALL TO public USING (tenant_id = nullif(current_setting('app.tenant_id', true), '')::uuid) WITH CHECK (tenant_id = nullif(current_setting('app.tenant_id', true), '')::uuid);--> statement-breakpoint
CREATE POLICY "incident_types_tenant_policy" ON "incident_types" AS PERMISSIVE FOR ALL TO public USING (tenant_id = nullif(current_setting('app.tenant_id', true), '')::uuid) WITH CHECK (tenant_id = nullif(current_setting('app.tenant_id', true), '')::uuid);--> statement-breakpoint
CREATE POLICY "ingestion_jobs_tenant_policy" ON "ingestion_jobs" AS PERMISSIVE FOR ALL TO public USING (tenant_id = nullif(current_setting('app.tenant_id', true), '')::uuid) WITH CHECK (tenant_id = nullif(current_setting('app.tenant_id', true), '')::uuid);--> statement-breakpoint
CREATE POLICY "interruption_scopes_tenant_policy" ON "interruption_scopes" AS PERMISSIVE FOR ALL TO public USING (tenant_id = nullif(current_setting('app.tenant_id', true), '')::uuid) WITH CHECK (tenant_id = nullif(current_setting('app.tenant_id', true), '')::uuid);--> statement-breakpoint
CREATE POLICY "invoice_lines_tenant_policy" ON "invoice_lines" AS PERMISSIVE FOR ALL TO public USING (tenant_id = nullif(current_setting('app.tenant_id', true), '')::uuid) WITH CHECK (tenant_id = nullif(current_setting('app.tenant_id', true), '')::uuid);--> statement-breakpoint
CREATE POLICY "invoices_tenant_policy" ON "invoices" AS PERMISSIVE FOR ALL TO public USING (tenant_id = nullif(current_setting('app.tenant_id', true), '')::uuid) WITH CHECK (tenant_id = nullif(current_setting('app.tenant_id', true), '')::uuid);--> statement-breakpoint
CREATE POLICY "knowledge_bases_tenant_policy" ON "knowledge_bases" AS PERMISSIVE FOR ALL TO public USING (tenant_id = nullif(current_setting('app.tenant_id', true), '')::uuid) WITH CHECK (tenant_id = nullif(current_setting('app.tenant_id', true), '')::uuid);--> statement-breakpoint
CREATE POLICY "knowledge_categories_tenant_policy" ON "knowledge_categories" AS PERMISSIVE FOR ALL TO public USING (tenant_id = nullif(current_setting('app.tenant_id', true), '')::uuid) WITH CHECK (tenant_id = nullif(current_setting('app.tenant_id', true), '')::uuid);--> statement-breakpoint
CREATE POLICY "knowledge_chunks_tenant_policy" ON "knowledge_chunks" AS PERMISSIVE FOR ALL TO public USING (tenant_id = nullif(current_setting('app.tenant_id', true), '')::uuid) WITH CHECK (tenant_id = nullif(current_setting('app.tenant_id', true), '')::uuid);--> statement-breakpoint
CREATE POLICY "knowledge_documents_tenant_policy" ON "knowledge_documents" AS PERMISSIVE FOR ALL TO public USING (tenant_id = nullif(current_setting('app.tenant_id', true), '')::uuid) WITH CHECK (tenant_id = nullif(current_setting('app.tenant_id', true), '')::uuid);--> statement-breakpoint
CREATE POLICY "knowledge_embeddings_tenant_policy" ON "knowledge_embeddings" AS PERMISSIVE FOR ALL TO public USING (tenant_id = nullif(current_setting('app.tenant_id', true), '')::uuid) WITH CHECK (tenant_id = nullif(current_setting('app.tenant_id', true), '')::uuid);--> statement-breakpoint
CREATE POLICY "knowledge_reviews_tenant_policy" ON "knowledge_reviews" AS PERMISSIVE FOR ALL TO public USING (tenant_id = nullif(current_setting('app.tenant_id', true), '')::uuid) WITH CHECK (tenant_id = nullif(current_setting('app.tenant_id', true), '')::uuid);--> statement-breakpoint
CREATE POLICY "mailbox_deliveries_tenant_policy" ON "mailbox_deliveries" AS PERMISSIVE FOR ALL TO public USING (tenant_id = nullif(current_setting('app.tenant_id', true), '')::uuid) WITH CHECK (tenant_id = nullif(current_setting('app.tenant_id', true), '')::uuid);--> statement-breakpoint
CREATE POLICY "management_coverage_tenant_policy" ON "management_coverage" AS PERMISSIVE FOR ALL TO public USING (tenant_id = nullif(current_setting('app.tenant_id', true), '')::uuid) WITH CHECK (tenant_id = nullif(current_setting('app.tenant_id', true), '')::uuid);--> statement-breakpoint
CREATE POLICY "management_units_tenant_policy" ON "management_units" AS PERMISSIVE FOR ALL TO public USING (tenant_id = nullif(current_setting('app.tenant_id', true), '')::uuid) WITH CHECK (tenant_id = nullif(current_setting('app.tenant_id', true), '')::uuid);--> statement-breakpoint
CREATE POLICY "mcp_servers_tenant_policy" ON "mcp_servers" AS PERMISSIVE FOR ALL TO public USING (tenant_id = nullif(current_setting('app.tenant_id', true), '')::uuid) WITH CHECK (tenant_id = nullif(current_setting('app.tenant_id', true), '')::uuid);--> statement-breakpoint
CREATE POLICY "mcp_tools_tenant_policy" ON "mcp_tools" AS PERMISSIVE FOR ALL TO public USING (tenant_id = nullif(current_setting('app.tenant_id', true), '')::uuid) WITH CHECK (tenant_id = nullif(current_setting('app.tenant_id', true), '')::uuid);--> statement-breakpoint
CREATE POLICY "mcp_user_credentials_tenant_policy" ON "mcp_user_credentials" AS PERMISSIVE FOR ALL TO public USING (tenant_id = nullif(current_setting('app.tenant_id', true), '')::uuid) WITH CHECK (tenant_id = nullif(current_setting('app.tenant_id', true), '')::uuid);--> statement-breakpoint
CREATE POLICY "memory_candidates_tenant_policy" ON "memory_candidates" AS PERMISSIVE FOR ALL TO public USING (tenant_id = nullif(current_setting('app.tenant_id', true), '')::uuid) WITH CHECK (tenant_id = nullif(current_setting('app.tenant_id', true), '')::uuid);--> statement-breakpoint
CREATE POLICY "memory_namespaces_tenant_policy" ON "memory_namespaces" AS PERMISSIVE FOR ALL TO public USING (tenant_id = nullif(current_setting('app.tenant_id', true), '')::uuid) WITH CHECK (tenant_id = nullif(current_setting('app.tenant_id', true), '')::uuid);--> statement-breakpoint
CREATE POLICY "memory_publications_tenant_policy" ON "memory_publications" AS PERMISSIVE FOR ALL TO public USING (tenant_id = nullif(current_setting('app.tenant_id', true), '')::uuid) WITH CHECK (tenant_id = nullif(current_setting('app.tenant_id', true), '')::uuid);--> statement-breakpoint
CREATE POLICY "message_files_tenant_policy" ON "message_files" AS PERMISSIVE FOR ALL TO public USING (tenant_id = nullif(current_setting('app.tenant_id', true), '')::uuid) WITH CHECK (tenant_id = nullif(current_setting('app.tenant_id', true), '')::uuid);--> statement-breakpoint
CREATE POLICY "message_mentions_tenant_policy" ON "message_mentions" AS PERMISSIVE FOR ALL TO public USING (tenant_id = nullif(current_setting('app.tenant_id', true), '')::uuid) WITH CHECK (tenant_id = nullif(current_setting('app.tenant_id', true), '')::uuid);--> statement-breakpoint
CREATE POLICY "messages_tenant_policy" ON "messages" AS PERMISSIVE FOR ALL TO public USING (tenant_id = nullif(current_setting('app.tenant_id', true), '')::uuid) WITH CHECK (tenant_id = nullif(current_setting('app.tenant_id', true), '')::uuid);--> statement-breakpoint
CREATE POLICY "model_profiles_tenant_policy" ON "model_profiles" AS PERMISSIVE FOR ALL TO public USING (tenant_id = nullif(current_setting('app.tenant_id', true), '')::uuid) WITH CHECK (tenant_id = nullif(current_setting('app.tenant_id', true), '')::uuid);--> statement-breakpoint
CREATE POLICY "notification_deliveries_tenant_policy" ON "notification_deliveries" AS PERMISSIVE FOR ALL TO public USING (tenant_id = nullif(current_setting('app.tenant_id', true), '')::uuid) WITH CHECK (tenant_id = nullif(current_setting('app.tenant_id', true), '')::uuid);--> statement-breakpoint
CREATE POLICY "payment_allocations_tenant_policy" ON "payment_allocations" AS PERMISSIVE FOR ALL TO public USING (tenant_id = nullif(current_setting('app.tenant_id', true), '')::uuid) WITH CHECK (tenant_id = nullif(current_setting('app.tenant_id', true), '')::uuid);--> statement-breakpoint
CREATE POLICY "payment_intents_tenant_policy" ON "payment_intents" AS PERMISSIVE FOR ALL TO public USING (tenant_id = nullif(current_setting('app.tenant_id', true), '')::uuid) WITH CHECK (tenant_id = nullif(current_setting('app.tenant_id', true), '')::uuid);--> statement-breakpoint
CREATE POLICY "payment_webhook_receipts_tenant_policy" ON "payment_webhook_receipts" AS PERMISSIVE FOR ALL TO public USING (tenant_id = nullif(current_setting('app.tenant_id', true), '')::uuid) WITH CHECK (tenant_id = nullif(current_setting('app.tenant_id', true), '')::uuid);--> statement-breakpoint
CREATE POLICY "payments_tenant_policy" ON "payments" AS PERMISSIVE FOR ALL TO public USING (tenant_id = nullif(current_setting('app.tenant_id', true), '')::uuid) WITH CHECK (tenant_id = nullif(current_setting('app.tenant_id', true), '')::uuid);--> statement-breakpoint
CREATE POLICY "plugin_grants_tenant_policy" ON "plugin_grants" AS PERMISSIVE FOR ALL TO public USING (tenant_id = nullif(current_setting('app.tenant_id', true), '')::uuid) WITH CHECK (tenant_id = nullif(current_setting('app.tenant_id', true), '')::uuid);--> statement-breakpoint
CREATE POLICY "reception_sessions_tenant_policy" ON "reception_sessions" AS PERMISSIVE FOR ALL TO public USING (tenant_id = nullif(current_setting('app.tenant_id', true), '')::uuid) WITH CHECK (tenant_id = nullif(current_setting('app.tenant_id', true), '')::uuid);--> statement-breakpoint
CREATE POLICY "reception_waits_tenant_policy" ON "reception_waits" AS PERMISSIVE FOR ALL TO public USING (tenant_id = nullif(current_setting('app.tenant_id', true), '')::uuid) WITH CHECK (tenant_id = nullif(current_setting('app.tenant_id', true), '')::uuid);--> statement-breakpoint
CREATE POLICY "refund_allocations_tenant_policy" ON "refund_allocations" AS PERMISSIVE FOR ALL TO public USING (tenant_id = nullif(current_setting('app.tenant_id', true), '')::uuid) WITH CHECK (tenant_id = nullif(current_setting('app.tenant_id', true), '')::uuid);--> statement-breakpoint
CREATE POLICY "refunds_tenant_policy" ON "refunds" AS PERMISSIVE FOR ALL TO public USING (tenant_id = nullif(current_setting('app.tenant_id', true), '')::uuid) WITH CHECK (tenant_id = nullif(current_setting('app.tenant_id', true), '')::uuid);--> statement-breakpoint
CREATE POLICY "report_requests_tenant_policy" ON "report_requests" AS PERMISSIVE FOR ALL TO public USING (tenant_id = nullif(current_setting('app.tenant_id', true), '')::uuid) WITH CHECK (tenant_id = nullif(current_setting('app.tenant_id', true), '')::uuid);--> statement-breakpoint
CREATE POLICY "report_sources_tenant_policy" ON "report_sources" AS PERMISSIVE FOR ALL TO public USING (tenant_id = nullif(current_setting('app.tenant_id', true), '')::uuid) WITH CHECK (tenant_id = nullif(current_setting('app.tenant_id', true), '')::uuid);--> statement-breakpoint
CREATE POLICY "retrieval_hits_tenant_policy" ON "retrieval_hits" AS PERMISSIVE FOR ALL TO public USING (tenant_id = nullif(current_setting('app.tenant_id', true), '')::uuid) WITH CHECK (tenant_id = nullif(current_setting('app.tenant_id', true), '')::uuid);--> statement-breakpoint
CREATE POLICY "retrieval_runs_tenant_policy" ON "retrieval_runs" AS PERMISSIVE FOR ALL TO public USING (tenant_id = nullif(current_setting('app.tenant_id', true), '')::uuid) WITH CHECK (tenant_id = nullif(current_setting('app.tenant_id', true), '')::uuid);--> statement-breakpoint
CREATE POLICY "routine_runs_tenant_policy" ON "routine_runs" AS PERMISSIVE FOR ALL TO public USING (tenant_id = nullif(current_setting('app.tenant_id', true), '')::uuid) WITH CHECK (tenant_id = nullif(current_setting('app.tenant_id', true), '')::uuid);--> statement-breakpoint
CREATE POLICY "routines_tenant_policy" ON "routines" AS PERMISSIVE FOR ALL TO public USING (tenant_id = nullif(current_setting('app.tenant_id', true), '')::uuid) WITH CHECK (tenant_id = nullif(current_setting('app.tenant_id', true), '')::uuid);--> statement-breakpoint
CREATE POLICY "run_memory_access_tenant_policy" ON "run_memory_access" AS PERMISSIVE FOR ALL TO public USING (tenant_id = nullif(current_setting('app.tenant_id', true), '')::uuid) WITH CHECK (tenant_id = nullif(current_setting('app.tenant_id', true), '')::uuid);--> statement-breakpoint
CREATE POLICY "runtime_identities_tenant_policy" ON "runtime_identities" AS PERMISSIVE FOR ALL TO public USING (tenant_id = nullif(current_setting('app.tenant_id', true), '')::uuid) WITH CHECK (tenant_id = nullif(current_setting('app.tenant_id', true), '')::uuid);--> statement-breakpoint
CREATE POLICY "runtime_memory_bindings_tenant_policy" ON "runtime_memory_bindings" AS PERMISSIVE FOR ALL TO public USING (tenant_id = nullif(current_setting('app.tenant_id', true), '')::uuid) WITH CHECK (tenant_id = nullif(current_setting('app.tenant_id', true), '')::uuid);--> statement-breakpoint
CREATE POLICY "runtime_session_bindings_tenant_policy" ON "runtime_session_bindings" AS PERMISSIVE FOR ALL TO public USING (tenant_id = nullif(current_setting('app.tenant_id', true), '')::uuid) WITH CHECK (tenant_id = nullif(current_setting('app.tenant_id', true), '')::uuid);--> statement-breakpoint
CREATE POLICY "runtime_session_operations_tenant_policy" ON "runtime_session_operations" AS PERMISSIVE FOR ALL TO public USING (tenant_id = nullif(current_setting('app.tenant_id', true), '')::uuid) WITH CHECK (tenant_id = nullif(current_setting('app.tenant_id', true), '')::uuid);--> statement-breakpoint
CREATE POLICY "sandboxed_components_tenant_policy" ON "sandboxed_components" AS PERMISSIVE FOR ALL TO public USING (tenant_id = nullif(current_setting('app.tenant_id', true), '')::uuid) WITH CHECK (tenant_id = nullif(current_setting('app.tenant_id', true), '')::uuid);--> statement-breakpoint
CREATE POLICY "scoped_user_roles_tenant_policy" ON "scoped_user_roles" AS PERMISSIVE FOR ALL TO public USING (tenant_id = nullif(current_setting('app.tenant_id', true), '')::uuid) WITH CHECK (tenant_id = nullif(current_setting('app.tenant_id', true), '')::uuid);--> statement-breakpoint
CREATE POLICY "service_categories_tenant_policy" ON "service_categories" AS PERMISSIVE FOR ALL TO public USING (tenant_id = nullif(current_setting('app.tenant_id', true), '')::uuid) WITH CHECK (tenant_id = nullif(current_setting('app.tenant_id', true), '')::uuid);--> statement-breakpoint
CREATE POLICY "service_interruptions_tenant_policy" ON "service_interruptions" AS PERMISSIVE FOR ALL TO public USING (tenant_id = nullif(current_setting('app.tenant_id', true), '')::uuid) WITH CHECK (tenant_id = nullif(current_setting('app.tenant_id', true), '')::uuid);--> statement-breakpoint
CREATE POLICY "sites_tenant_policy" ON "sites" AS PERMISSIVE FOR ALL TO public USING (tenant_id = nullif(current_setting('app.tenant_id', true), '')::uuid) WITH CHECK (tenant_id = nullif(current_setting('app.tenant_id', true), '')::uuid);--> statement-breakpoint
CREATE POLICY "skill_tools_tenant_policy" ON "skill_tools" AS PERMISSIVE FOR ALL TO public USING (tenant_id = nullif(current_setting('app.tenant_id', true), '')::uuid) WITH CHECK (tenant_id = nullif(current_setting('app.tenant_id', true), '')::uuid);--> statement-breakpoint
CREATE POLICY "skills_tenant_policy" ON "skills" AS PERMISSIVE FOR ALL TO public USING (tenant_id = nullif(current_setting('app.tenant_id', true), '')::uuid) WITH CHECK (tenant_id = nullif(current_setting('app.tenant_id', true), '')::uuid);--> statement-breakpoint
CREATE POLICY "sla_policies_tenant_policy" ON "sla_policies" AS PERMISSIVE FOR ALL TO public USING (tenant_id = nullif(current_setting('app.tenant_id', true), '')::uuid) WITH CHECK (tenant_id = nullif(current_setting('app.tenant_id', true), '')::uuid);--> statement-breakpoint
CREATE POLICY "staff_profiles_tenant_policy" ON "staff_profiles" AS PERMISSIVE FOR ALL TO public USING (tenant_id = nullif(current_setting('app.tenant_id', true), '')::uuid) WITH CHECK (tenant_id = nullif(current_setting('app.tenant_id', true), '')::uuid);--> statement-breakpoint
CREATE POLICY "staff_shifts_tenant_policy" ON "staff_shifts" AS PERMISSIVE FOR ALL TO public USING (tenant_id = nullif(current_setting('app.tenant_id', true), '')::uuid) WITH CHECK (tenant_id = nullif(current_setting('app.tenant_id', true), '')::uuid);--> statement-breakpoint
CREATE POLICY "staff_specialties_tenant_policy" ON "staff_specialties" AS PERMISSIVE FOR ALL TO public USING (tenant_id = nullif(current_setting('app.tenant_id', true), '')::uuid) WITH CHECK (tenant_id = nullif(current_setting('app.tenant_id', true), '')::uuid);--> statement-breakpoint
CREATE POLICY "storage_event_receipts_tenant_policy" ON "storage_event_receipts" AS PERMISSIVE FOR ALL TO public USING (tenant_id = nullif(current_setting('app.tenant_id', true), '')::uuid) WITH CHECK (tenant_id = nullif(current_setting('app.tenant_id', true), '')::uuid);--> statement-breakpoint
CREATE POLICY "storage_locations_tenant_policy" ON "storage_locations" AS PERMISSIVE FOR ALL TO public USING (tenant_id = nullif(current_setting('app.tenant_id', true), '')::uuid) WITH CHECK (tenant_id = nullif(current_setting('app.tenant_id', true), '')::uuid);--> statement-breakpoint
CREATE POLICY "task_dependencies_tenant_policy" ON "task_dependencies" AS PERMISSIVE FOR ALL TO public USING (tenant_id = nullif(current_setting('app.tenant_id', true), '')::uuid) WITH CHECK (tenant_id = nullif(current_setting('app.tenant_id', true), '')::uuid);--> statement-breakpoint
CREATE POLICY "team_mailbox_tenant_policy" ON "team_mailbox" AS PERMISSIVE FOR ALL TO public USING (tenant_id = nullif(current_setting('app.tenant_id', true), '')::uuid) WITH CHECK (tenant_id = nullif(current_setting('app.tenant_id', true), '')::uuid);--> statement-breakpoint
CREATE POLICY "team_members_tenant_policy" ON "team_members" AS PERMISSIVE FOR ALL TO public USING (tenant_id = nullif(current_setting('app.tenant_id', true), '')::uuid) WITH CHECK (tenant_id = nullif(current_setting('app.tenant_id', true), '')::uuid);--> statement-breakpoint
CREATE POLICY "team_tasks_tenant_policy" ON "team_tasks" AS PERMISSIVE FOR ALL TO public USING (tenant_id = nullif(current_setting('app.tenant_id', true), '')::uuid) WITH CHECK (tenant_id = nullif(current_setting('app.tenant_id', true), '')::uuid);--> statement-breakpoint
CREATE POLICY "tenant_memberships_tenant_policy" ON "tenant_memberships" AS PERMISSIVE FOR ALL TO public USING (tenant_id = nullif(current_setting('app.tenant_id', true), '')::uuid) WITH CHECK (tenant_id = nullif(current_setting('app.tenant_id', true), '')::uuid);--> statement-breakpoint
CREATE POLICY "ticket_assessment_evidence_tenant_policy" ON "ticket_assessment_evidence" AS PERMISSIVE FOR ALL TO public USING (tenant_id = nullif(current_setting('app.tenant_id', true), '')::uuid) WITH CHECK (tenant_id = nullif(current_setting('app.tenant_id', true), '')::uuid);--> statement-breakpoint
CREATE POLICY "ticket_assessments_tenant_policy" ON "ticket_assessments" AS PERMISSIVE FOR ALL TO public USING (tenant_id = nullif(current_setting('app.tenant_id', true), '')::uuid) WITH CHECK (tenant_id = nullif(current_setting('app.tenant_id', true), '')::uuid);--> statement-breakpoint
CREATE POLICY "ticket_escalations_tenant_policy" ON "ticket_escalations" AS PERMISSIVE FOR ALL TO public USING (tenant_id = nullif(current_setting('app.tenant_id', true), '')::uuid) WITH CHECK (tenant_id = nullif(current_setting('app.tenant_id', true), '')::uuid);--> statement-breakpoint
CREATE POLICY "ticket_events_tenant_policy" ON "ticket_events" AS PERMISSIVE FOR ALL TO public USING (tenant_id = nullif(current_setting('app.tenant_id', true), '')::uuid) WITH CHECK (tenant_id = nullif(current_setting('app.tenant_id', true), '')::uuid);--> statement-breakpoint
CREATE POLICY "ticket_files_tenant_policy" ON "ticket_files" AS PERMISSIVE FOR ALL TO public USING (tenant_id = nullif(current_setting('app.tenant_id', true), '')::uuid) WITH CHECK (tenant_id = nullif(current_setting('app.tenant_id', true), '')::uuid);--> statement-breakpoint
CREATE POLICY "ticket_reviews_tenant_policy" ON "ticket_reviews" AS PERMISSIVE FOR ALL TO public USING (tenant_id = nullif(current_setting('app.tenant_id', true), '')::uuid) WITH CHECK (tenant_id = nullif(current_setting('app.tenant_id', true), '')::uuid);--> statement-breakpoint
CREATE POLICY "ticket_routing_history_tenant_policy" ON "ticket_routing_history" AS PERMISSIVE FOR ALL TO public USING (tenant_id = nullif(current_setting('app.tenant_id', true), '')::uuid) WITH CHECK (tenant_id = nullif(current_setting('app.tenant_id', true), '')::uuid);--> statement-breakpoint
CREATE POLICY "ticket_sla_adjustments_tenant_policy" ON "ticket_sla_adjustments" AS PERMISSIVE FOR ALL TO public USING (tenant_id = nullif(current_setting('app.tenant_id', true), '')::uuid) WITH CHECK (tenant_id = nullif(current_setting('app.tenant_id', true), '')::uuid);--> statement-breakpoint
CREATE POLICY "ticket_sla_cycles_tenant_policy" ON "ticket_sla_cycles" AS PERMISSIVE FOR ALL TO public USING (tenant_id = nullif(current_setting('app.tenant_id', true), '')::uuid) WITH CHECK (tenant_id = nullif(current_setting('app.tenant_id', true), '')::uuid);--> statement-breakpoint
CREATE POLICY "ticket_triage_decisions_tenant_policy" ON "ticket_triage_decisions" AS PERMISSIVE FOR ALL TO public USING (tenant_id = nullif(current_setting('app.tenant_id', true), '')::uuid) WITH CHECK (tenant_id = nullif(current_setting('app.tenant_id', true), '')::uuid);--> statement-breakpoint
CREATE POLICY "ticket_triage_reviews_tenant_policy" ON "ticket_triage_reviews" AS PERMISSIVE FOR ALL TO public USING (tenant_id = nullif(current_setting('app.tenant_id', true), '')::uuid) WITH CHECK (tenant_id = nullif(current_setting('app.tenant_id', true), '')::uuid);--> statement-breakpoint
CREATE POLICY "tickets_tenant_policy" ON "tickets" AS PERMISSIVE FOR ALL TO public USING (tenant_id = nullif(current_setting('app.tenant_id', true), '')::uuid) WITH CHECK (tenant_id = nullif(current_setting('app.tenant_id', true), '')::uuid);--> statement-breakpoint
CREATE POLICY "triage_policy_bindings_tenant_policy" ON "triage_policy_bindings" AS PERMISSIVE FOR ALL TO public USING (tenant_id = nullif(current_setting('app.tenant_id', true), '')::uuid) WITH CHECK (tenant_id = nullif(current_setting('app.tenant_id', true), '')::uuid);--> statement-breakpoint
CREATE POLICY "triage_policy_versions_tenant_policy" ON "triage_policy_versions" AS PERMISSIVE FOR ALL TO public USING (tenant_id = nullif(current_setting('app.tenant_id', true), '')::uuid) WITH CHECK (tenant_id = nullif(current_setting('app.tenant_id', true), '')::uuid);--> statement-breakpoint
CREATE POLICY "triage_rules_tenant_policy" ON "triage_rules" AS PERMISSIVE FOR ALL TO public USING (tenant_id = nullif(current_setting('app.tenant_id', true), '')::uuid) WITH CHECK (tenant_id = nullif(current_setting('app.tenant_id', true), '')::uuid);--> statement-breakpoint
CREATE POLICY "unit_residents_tenant_policy" ON "unit_residents" AS PERMISSIVE FOR ALL TO public USING (tenant_id = nullif(current_setting('app.tenant_id', true), '')::uuid) WITH CHECK (tenant_id = nullif(current_setting('app.tenant_id', true), '')::uuid);--> statement-breakpoint
CREATE POLICY "units_tenant_policy" ON "units" AS PERMISSIVE FOR ALL TO public USING (tenant_id = nullif(current_setting('app.tenant_id', true), '')::uuid) WITH CHECK (tenant_id = nullif(current_setting('app.tenant_id', true), '')::uuid);--> statement-breakpoint
CREATE POLICY "work_approval_evidence_tenant_policy" ON "work_approval_evidence" AS PERMISSIVE FOR ALL TO public USING (tenant_id = nullif(current_setting('app.tenant_id', true), '')::uuid) WITH CHECK (tenant_id = nullif(current_setting('app.tenant_id', true), '')::uuid);--> statement-breakpoint
CREATE POLICY "work_approvals_tenant_policy" ON "work_approvals" AS PERMISSIVE FOR ALL TO public USING (tenant_id = nullif(current_setting('app.tenant_id', true), '')::uuid) WITH CHECK (tenant_id = nullif(current_setting('app.tenant_id', true), '')::uuid);--> statement-breakpoint
CREATE POLICY "work_assignments_tenant_policy" ON "work_assignments" AS PERMISSIVE FOR ALL TO public USING (tenant_id = nullif(current_setting('app.tenant_id', true), '')::uuid) WITH CHECK (tenant_id = nullif(current_setting('app.tenant_id', true), '')::uuid);--> statement-breakpoint
CREATE POLICY "work_items_tenant_policy" ON "work_items" AS PERMISSIVE FOR ALL TO public USING (tenant_id = nullif(current_setting('app.tenant_id', true), '')::uuid OR tenant_id IS NULL) WITH CHECK (tenant_id = nullif(current_setting('app.tenant_id', true), '')::uuid OR tenant_id IS NULL);--> statement-breakpoint
CREATE POLICY "work_orders_tenant_policy" ON "work_orders" AS PERMISSIVE FOR ALL TO public USING (tenant_id = nullif(current_setting('app.tenant_id', true), '')::uuid) WITH CHECK (tenant_id = nullif(current_setting('app.tenant_id', true), '')::uuid);--> statement-breakpoint
CREATE POLICY "work_reassignment_requests_tenant_policy" ON "work_reassignment_requests" AS PERMISSIVE FOR ALL TO public USING (tenant_id = nullif(current_setting('app.tenant_id', true), '')::uuid) WITH CHECK (tenant_id = nullif(current_setting('app.tenant_id', true), '')::uuid);--> statement-breakpoint
CREATE POLICY "workspace_members_tenant_policy" ON "workspace_members" AS PERMISSIVE FOR ALL TO public USING (tenant_id = nullif(current_setting('app.tenant_id', true), '')::uuid) WITH CHECK (tenant_id = nullif(current_setting('app.tenant_id', true), '')::uuid);--> statement-breakpoint
CREATE POLICY "workspaces_tenant_policy" ON "workspaces" AS PERMISSIVE FOR ALL TO public USING (tenant_id = nullif(current_setting('app.tenant_id', true), '')::uuid) WITH CHECK (tenant_id = nullif(current_setting('app.tenant_id', true), '')::uuid);--> statement-breakpoint
CREATE POLICY "zones_tenant_policy" ON "zones" AS PERMISSIVE FOR ALL TO public USING (tenant_id = nullif(current_setting('app.tenant_id', true), '')::uuid) WITH CHECK (tenant_id = nullif(current_setting('app.tenant_id', true), '')::uuid);
--> statement-breakpoint
-- Declarative schema cannot express deferred cross-row checks, exclusion constraints,
-- immutable histories or FORCE RLS. db:generate adds this source to the new baseline.
CREATE EXTENSION IF NOT EXISTS btree_gist;
--> statement-breakpoint
CREATE OR REPLACE FUNCTION app_touch_updated_at() RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN NEW.updated_at=clock_timestamp(); RETURN NEW; END $$;
--> statement-breakpoint
CREATE OR REPLACE FUNCTION app_append_only() RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN RAISE EXCEPTION '% is append-only (% refused)', TG_TABLE_NAME,TG_OP USING ERRCODE='23514'; END $$;
--> statement-breakpoint
CREATE OR REPLACE FUNCTION prevent_audit_event_mutation() RETURNS trigger LANGUAGE plpgsql AS $$
DECLARE days integer;
BEGIN
 IF TG_OP IN ('UPDATE','TRUNCATE') THEN RAISE EXCEPTION 'Audit events are append-only'; END IF;
 BEGIN days=nullif(current_setting('openbot.audit_retention_days',true),'')::integer; EXCEPTION WHEN others THEN days=NULL; END;
 IF days IS NULL OR days<1 OR OLD.created_at>=now()-make_interval(days=>days) THEN RAISE EXCEPTION 'Audit events are append-only within retention'; END IF;
 RETURN OLD;
END $$;
--> statement-breakpoint
CREATE TRIGGER audit_events_append_only BEFORE UPDATE OR DELETE ON audit_events FOR EACH ROW EXECUTE FUNCTION prevent_audit_event_mutation();
--> statement-breakpoint
CREATE TRIGGER audit_events_no_truncate BEFORE TRUNCATE ON audit_events FOR EACH STATEMENT EXECUTE FUNCTION prevent_audit_event_mutation();
--> statement-breakpoint
CREATE OR REPLACE FUNCTION app_validate_runtime_binding() RETURNS trigger LANGUAGE plpgsql AS $$
DECLARE p execution_principals; ident runtime_identities; a agents; av agent_versions; tm team_members; team agent_teams;
BEGIN
 SELECT * INTO STRICT ident FROM runtime_identities WHERE id=NEW.identity_id AND tenant_id=NEW.tenant_id;
 IF ident.backend_id<>NEW.backend_id THEN RAISE EXCEPTION 'Binding backend mismatch'; END IF;
 SELECT * INTO STRICT p FROM execution_principals WHERE id=ident.principal_id AND tenant_id=NEW.tenant_id;
 SELECT * INTO STRICT a FROM agents WHERE id=NEW.agent_id AND tenant_id=NEW.tenant_id;
 SELECT * INTO STRICT av FROM agent_versions WHERE id=NEW.agent_version_id AND agent_id=a.id AND tenant_id=NEW.tenant_id;
 IF TG_OP='UPDATE' AND (NEW.identity_id,NEW.backend_id,NEW.runtime_session_key,NEW.customer_user_id,NEW.channel_id,NEW.agent_id,NEW.agent_version_id,NEW.team_member_id)
   IS DISTINCT FROM (OLD.identity_id,OLD.backend_id,OLD.runtime_session_key,OLD.customer_user_id,OLD.channel_id,OLD.agent_id,OLD.agent_version_id,OLD.team_member_id)
 THEN RAISE EXCEPTION 'Runtime owner and identity are immutable'; END IF;
 IF NEW.audience_kind='personal' THEN
  IF p.kind<>'user' OR p.user_id IS DISTINCT FROM NEW.customer_user_id THEN RAISE EXCEPTION 'Personal binding owner mismatch'; END IF;
 ELSE
  SELECT * INTO STRICT tm FROM team_members WHERE id=NEW.team_member_id AND tenant_id=NEW.tenant_id;
  SELECT * INTO STRICT team FROM agent_teams WHERE id=tm.team_id AND tenant_id=NEW.tenant_id;
  IF p.kind<>'workspace_service' OR p.workspace_id IS DISTINCT FROM team.workspace_id OR team.channel_id<>NEW.channel_id OR tm.agent_id<>NEW.agent_id OR tm.version_id<>NEW.agent_version_id THEN RAISE EXCEPTION 'Team runtime scope mismatch'; END IF;
 END IF;
 RETURN NEW;
END $$;
--> statement-breakpoint
CREATE TRIGGER runtime_binding_scope BEFORE INSERT OR UPDATE ON runtime_session_bindings FOR EACH ROW EXECUTE FUNCTION app_validate_runtime_binding();
--> statement-breakpoint
CREATE OR REPLACE FUNCTION app_validate_memory_namespace() RETURNS trigger LANGUAGE plpgsql AS $$
DECLARE p execution_principals; team agent_teams;
BEGIN
 SELECT * INTO STRICT p FROM execution_principals WHERE id=NEW.owner_principal_id AND tenant_id=NEW.tenant_id;
 IF NEW.kind='personal' THEN
  IF p.kind<>'user' THEN RAISE EXCEPTION 'Private memory must belong to a user principal'; END IF;
 ELSE
  IF p.kind<>'workspace_service' OR p.workspace_id IS DISTINCT FROM NEW.workspace_id THEN RAISE EXCEPTION 'Shared memory workspace mismatch'; END IF;
  IF NEW.team_id IS NOT NULL THEN
   SELECT * INTO STRICT team FROM agent_teams WHERE id=NEW.team_id AND tenant_id=NEW.tenant_id;
   IF team.workspace_id<>NEW.workspace_id THEN RAISE EXCEPTION 'Memory team mismatch'; END IF;
  END IF;
 END IF;
 IF TG_OP='UPDATE' AND (NEW.owner_principal_id,NEW.kind,NEW.workspace_id,NEW.team_id,NEW.namespace_key) IS DISTINCT FROM (OLD.owner_principal_id,OLD.kind,OLD.workspace_id,OLD.team_id,OLD.namespace_key) THEN RAISE EXCEPTION 'Memory ownership is immutable'; END IF;
 RETURN NEW;
END $$;
--> statement-breakpoint
CREATE TRIGGER memory_namespace_scope BEFORE INSERT OR UPDATE ON memory_namespaces FOR EACH ROW EXECUTE FUNCTION app_validate_memory_namespace();
--> statement-breakpoint
CREATE OR REPLACE FUNCTION app_validate_file() RETURNS trigger LANGUAGE plpgsql AS $$
DECLARE obj file_objects;
BEGIN
 IF NEW.accepted_object_id IS NOT NULL THEN
  SELECT * INTO STRICT obj FROM file_objects WHERE id=NEW.accepted_object_id AND tenant_id=NEW.tenant_id;
  IF obj.file_id<>NEW.id OR obj.variant<>'original' THEN RAISE EXCEPTION 'Accepted original object belongs to a different file'; END IF;
  IF NEW.status='ready' AND (obj.status<>'ready' OR obj.scan_status<>'clean' OR obj.verified_at IS NULL) THEN RAISE EXCEPTION 'File is not verified'; END IF;
 END IF;
 IF TG_OP='UPDATE' AND OLD.accepted_object_id IS NOT NULL AND NEW.accepted_object_id IS DISTINCT FROM OLD.accepted_object_id THEN RAISE EXCEPTION 'Accepted bytes are immutable'; END IF;
 IF TG_OP='UPDATE' AND (NEW.tenant_id,NEW.owner_principal_id,NEW.scope_kind,NEW.ticket_id,NEW.channel_id,NEW.document_id,NEW.report_id) IS DISTINCT FROM (OLD.tenant_id,OLD.owner_principal_id,OLD.scope_kind,OLD.ticket_id,OLD.channel_id,OLD.document_id,OLD.report_id) THEN RAISE EXCEPTION 'File security scope is immutable'; END IF;
 RETURN NEW;
END $$;
--> statement-breakpoint
CREATE CONSTRAINT TRIGGER file_original_scope AFTER INSERT OR UPDATE ON files DEFERRABLE INITIALLY DEFERRED FOR EACH ROW EXECUTE FUNCTION app_validate_file();
--> statement-breakpoint
CREATE OR REPLACE FUNCTION app_validate_object() RETURNS trigger LANGUAGE plpgsql AS $$
DECLARE loc storage_locations; parent file_objects;
BEGIN
 SELECT * INTO STRICT loc FROM storage_locations WHERE id=NEW.location_id AND tenant_id=NEW.tenant_id;
 IF left(NEW.object_key,length(loc.tenant_prefix))<>loc.tenant_prefix THEN RAISE EXCEPTION 'Object key escapes tenant prefix'; END IF;
 IF NEW.source_object_id IS NOT NULL THEN
  SELECT * INTO STRICT parent FROM file_objects WHERE id=NEW.source_object_id AND file_id=NEW.file_id AND tenant_id=NEW.tenant_id;
  IF parent.id=NEW.id THEN RAISE EXCEPTION 'Object derivation cycle'; END IF;
 END IF;
 IF TG_OP='UPDATE' AND (NEW.file_id,NEW.location_id,NEW.object_key,NEW.version_id,NEW.sha256,NEW.size_bytes,NEW.mime_type,NEW.source_object_id,NEW.variant,NEW.variant_revision) IS DISTINCT FROM (OLD.file_id,OLD.location_id,OLD.object_key,OLD.version_id,OLD.sha256,OLD.size_bytes,OLD.mime_type,OLD.source_object_id,OLD.variant,OLD.variant_revision) THEN RAISE EXCEPTION 'Object bytes and lineage are immutable'; END IF;
 RETURN NEW;
END $$;
--> statement-breakpoint
CREATE TRIGGER object_version_scope BEFORE INSERT OR UPDATE ON file_objects FOR EACH ROW EXECUTE FUNCTION app_validate_object();
--> statement-breakpoint
CREATE OR REPLACE FUNCTION app_validate_evidence() RETURNS trigger LANGUAGE plpgsql AS $$
DECLARE f files; w work_orders; a work_assignments;
BEGIN
 SELECT * INTO STRICT f FROM files WHERE id=NEW.file_id AND tenant_id=NEW.tenant_id;
 IF f.ticket_id IS DISTINCT FROM NEW.ticket_id OR f.scope_kind<>'ticket' OR f.status<>'ready' THEN RAISE EXCEPTION 'Evidence file is not ready or belongs to another ticket'; END IF;
 IF NEW.purpose IN ('before','after') AND (NEW.work_order_id IS NULL OR NEW.assignment_id IS NULL) THEN RAISE EXCEPTION 'Before/after evidence requires assignment'; END IF;
 IF NEW.work_order_id IS NOT NULL THEN
  SELECT * INTO STRICT w FROM work_orders WHERE id=NEW.work_order_id AND ticket_id=NEW.ticket_id;
 END IF;
 IF NEW.assignment_id IS NOT NULL THEN
  SELECT * INTO STRICT a FROM work_assignments WHERE id=NEW.assignment_id AND work_order_id=NEW.work_order_id;
 END IF;
 IF TG_OP='UPDATE' AND (NEW.ticket_id,NEW.work_order_id,NEW.assignment_id,NEW.file_id,NEW.purpose,NEW.uploaded_by) IS DISTINCT FROM (OLD.ticket_id,OLD.work_order_id,OLD.assignment_id,OLD.file_id,OLD.purpose,OLD.uploaded_by) THEN RAISE EXCEPTION 'Evidence provenance is immutable'; END IF;
 RETURN NEW;
END $$;
--> statement-breakpoint
CREATE TRIGGER evidence_scope BEFORE INSERT OR UPDATE ON evidence_items FOR EACH ROW EXECUTE FUNCTION app_validate_evidence();
--> statement-breakpoint
CREATE OR REPLACE FUNCTION app_validate_triage_decision() RETURNS trigger LANGUAGE plpgsql AS $$
DECLARE a ticket_assessments; b triage_policy_bindings; t tickets; r ticket_triage_reviews;
BEGIN
 SELECT * INTO STRICT a FROM ticket_assessments WHERE id=NEW.assessment_id AND tenant_id=NEW.tenant_id;
 SELECT * INTO STRICT t FROM tickets WHERE id=NEW.ticket_id AND tenant_id=NEW.tenant_id FOR UPDATE;
 SELECT * INTO STRICT b FROM triage_policy_bindings WHERE id=NEW.policy_binding_id AND tenant_id=NEW.tenant_id;
 IF a.ticket_id<>t.id OR a.ticket_generation<>NEW.ticket_generation OR b.policy_version_id<>NEW.policy_version_id OR b.domain_id<>t.domain_id THEN RAISE EXCEPTION 'Triage decision source mismatch'; END IF;
 IF NEW.matched_rule_id IS NOT NULL AND NOT EXISTS(SELECT 1 FROM triage_rules WHERE id=NEW.matched_rule_id AND policy_version_id=NEW.policy_version_id) THEN RAISE EXCEPTION 'Rule policy mismatch'; END IF;
 IF NEW.outcome='applied' THEN
  IF t.reopen_count<>NEW.ticket_generation OR t.version<>NEW.basis_ticket_version OR t.current_triage_decision_id IS DISTINCT FROM NEW.previous_applied_id THEN RAISE EXCEPTION 'Stale triage decision' USING ERRCODE='40001'; END IF;
  IF NEW.applied_ticket_version<>t.version+1 THEN RAISE EXCEPTION 'Invalid applied version'; END IF;
  IF NEW.review_id IS NOT NULL THEN
   SELECT * INTO STRICT r FROM ticket_triage_reviews WHERE id=NEW.review_id AND ticket_id=t.id AND ticket_generation=NEW.ticket_generation;
  END IF;
  IF NEW.approved_by IS NULL AND ((array_position(ARRAY['low','normal','high','critical'],NEW.priority)<array_position(ARRAY['low','normal','high','critical'],t.priority)) OR (t.is_emergency AND NOT NEW.is_emergency) OR (array_position(ARRAY['unknown','minor','moderate','major','critical'],NEW.severity)<array_position(ARRAY['unknown','minor','moderate','major','critical'],t.severity))) THEN RAISE EXCEPTION 'Downgrade requires authorized human review'; END IF;
 END IF;
 RETURN NEW;
END $$;
--> statement-breakpoint
CREATE TRIGGER triage_decision_source BEFORE INSERT ON ticket_triage_decisions FOR EACH ROW EXECUTE FUNCTION app_validate_triage_decision();
--> statement-breakpoint
CREATE OR REPLACE FUNCTION app_check_ticket_projection() RETURNS trigger LANGUAGE plpgsql AS $$
DECLARE d ticket_triage_decisions; current_ticket tickets;
BEGIN
 -- Read final row at deferred time, rather than a stale NEW image from an earlier update.
 SELECT * INTO current_ticket FROM tickets WHERE id=NEW.id;
 IF current_ticket.current_triage_decision_id IS NOT NULL THEN
  SELECT * INTO STRICT d FROM ticket_triage_decisions WHERE id=current_ticket.current_triage_decision_id;
  IF d.ticket_id<>current_ticket.id OR d.ticket_generation<>current_ticket.reopen_count OR d.outcome<>'applied' OR (d.priority,d.severity,d.is_emergency) IS DISTINCT FROM (current_ticket.priority,current_ticket.severity,current_ticket.is_emergency) THEN RAISE EXCEPTION 'Ticket projection differs from applied decision'; END IF;
 END IF;
 RETURN NULL;
END $$;
--> statement-breakpoint
CREATE CONSTRAINT TRIGGER ticket_triage_projection AFTER INSERT OR UPDATE ON tickets DEFERRABLE INITIALLY DEFERRED FOR EACH ROW EXECUTE FUNCTION app_check_ticket_projection();
--> statement-breakpoint
CREATE OR REPLACE FUNCTION app_check_applied_decision() RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN
 IF NEW.outcome='applied' AND NOT EXISTS (
  SELECT 1 FROM tickets WHERE id=NEW.ticket_id AND current_triage_decision_id=NEW.id
   AND version>=NEW.applied_ticket_version AND reopen_count=NEW.ticket_generation
 ) THEN RAISE EXCEPTION 'Applied decision and ticket projection must commit together'; END IF;
 RETURN NULL;
END $$;
--> statement-breakpoint
CREATE CONSTRAINT TRIGGER applied_decision_projection AFTER INSERT ON ticket_triage_decisions DEFERRABLE INITIALLY DEFERRED FOR EACH ROW EXECUTE FUNCTION app_check_applied_decision();
--> statement-breakpoint
CREATE OR REPLACE FUNCTION app_policy_immutable() RETURNS trigger LANGUAGE plpgsql AS $$
DECLARE version_id uuid; state text;
BEGIN
 IF TG_TABLE_NAME='triage_policy_versions' THEN
  IF OLD.status<>'draft' AND (to_jsonb(NEW)-'status'-'updated_at') IS DISTINCT FROM (to_jsonb(OLD)-'status'-'updated_at') THEN RAISE EXCEPTION 'Published policy content is immutable'; END IF;
  IF OLD.status<>'draft' AND NEW.status='draft' THEN RAISE EXCEPTION 'Published policy cannot return to draft'; END IF;
  RETURN NEW;
 END IF;
 IF TG_OP='UPDATE' THEN
  SELECT status INTO STRICT state FROM triage_policy_versions WHERE id=OLD.policy_version_id FOR UPDATE;
  IF state<>'draft' THEN RAISE EXCEPTION 'Published rules are immutable'; END IF;
 END IF;
 IF TG_OP='DELETE' THEN version_id=OLD.policy_version_id; ELSE version_id=NEW.policy_version_id; END IF;
 SELECT status INTO STRICT state FROM triage_policy_versions WHERE id=version_id FOR UPDATE;
 IF state<>'draft' THEN RAISE EXCEPTION 'Published rules are immutable'; END IF;
 IF TG_OP='DELETE' THEN RETURN OLD; ELSE RETURN NEW; END IF;
END $$;
--> statement-breakpoint
CREATE TRIGGER policy_version_immutable BEFORE UPDATE ON triage_policy_versions FOR EACH ROW EXECUTE FUNCTION app_policy_immutable();
--> statement-breakpoint
CREATE TRIGGER policy_rule_immutable BEFORE INSERT OR UPDATE OR DELETE ON triage_rules FOR EACH ROW EXECUTE FUNCTION app_policy_immutable();
--> statement-breakpoint
ALTER TABLE triage_policy_bindings ADD CONSTRAINT triage_binding_category_excl EXCLUDE USING gist (tenant_id WITH =,domain_id WITH =,scope_id WITH =,category_id WITH =,request_kind WITH =,tstzrange(valid_from,valid_to,'[)') WITH &&) WHERE (status='active' AND category_id IS NOT NULL);
--> statement-breakpoint
ALTER TABLE triage_policy_bindings ADD CONSTRAINT triage_binding_fallback_excl EXCLUDE USING gist (tenant_id WITH =,domain_id WITH =,scope_id WITH =,request_kind WITH =,tstzrange(valid_from,valid_to,'[)') WITH &&) WHERE (status='active' AND category_id IS NULL);
--> statement-breakpoint
ALTER TABLE scoped_user_roles ADD CONSTRAINT scoped_role_period_excl EXCLUDE USING gist (membership_id WITH =,scope_id WITH =,role_code WITH =,tstzrange(valid_from,valid_to,'[)') WITH &&);
--> statement-breakpoint
ALTER TABLE management_coverage ADD CONSTRAINT management_coverage_period_excl EXCLUDE USING gist (scope_id WITH =,service_category_id WITH =,tstzrange(valid_from,valid_to,'[)') WITH &&);
--> statement-breakpoint
ALTER TABLE sla_policies ADD CONSTRAINT sla_policy_period_excl EXCLUDE USING gist (tenant_id WITH =,domain_id WITH =,management_unit_id WITH =,category_id WITH =,request_kind WITH =,priority WITH =,tstzrange(effective_from,effective_to,'[)') WITH &&);
--> statement-breakpoint
CREATE OR REPLACE FUNCTION app_embedding_dimension() RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN
 IF NOT EXISTS(SELECT 1 FROM embedding_models WHERE id=NEW.model_id AND dimension=1536 AND distance_metric='cosine') THEN RAISE EXCEPTION 'Embedding model dimension/metric mismatch'; END IF; RETURN NEW;
END $$;
--> statement-breakpoint
CREATE TRIGGER embedding_dimension BEFORE INSERT OR UPDATE ON knowledge_embeddings FOR EACH ROW EXECUTE FUNCTION app_embedding_dimension();
--> statement-breakpoint
CREATE OR REPLACE FUNCTION app_agent_version_scope() RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN
 IF NOT EXISTS(SELECT 1 FROM agent_versions WHERE id=NEW.version_id AND tenant_id=NEW.tenant_id AND agent_id=NEW.agent_id) THEN RAISE EXCEPTION 'Agent version belongs to another agent'; END IF; RETURN NEW;
END $$;
--> statement-breakpoint
CREATE TRIGGER agent_release_version BEFORE INSERT OR UPDATE ON agent_releases FOR EACH ROW EXECUTE FUNCTION app_agent_version_scope();
--> statement-breakpoint
CREATE TRIGGER team_member_version BEFORE INSERT OR UPDATE ON team_members FOR EACH ROW EXECUTE FUNCTION app_agent_version_scope();
--> statement-breakpoint
CREATE OR REPLACE FUNCTION app_assignment_capacity() RETURNS trigger LANGUAGE plpgsql AS $$
DECLARE capacity integer; used integer;
BEGIN
 IF NEW.status NOT IN ('offered','accepted') THEN RETURN NEW; END IF;
 SELECT max_concurrent_jobs INTO STRICT capacity FROM staff_profiles WHERE id=NEW.staff_id AND tenant_id=NEW.tenant_id FOR UPDATE;
 SELECT count(*) INTO used FROM work_assignments WHERE staff_id=NEW.staff_id AND id<>NEW.id AND (status='accepted' OR (status='offered' AND offer_expires_at>now()));
 IF used>=capacity THEN RAISE EXCEPTION 'Staff capacity exhausted' USING ERRCODE='23514'; END IF;
 IF NEW.status='offered' AND (NEW.offer_expires_at IS NULL OR NEW.offer_expires_at<=now()) THEN RAISE EXCEPTION 'Offer must have a future expiry'; END IF;
 IF NEW.status='accepted' AND (NEW.accepted_at IS NULL OR NEW.eta_at IS NULL) THEN RAISE EXCEPTION 'Accepted assignment requires acknowledgment and ETA'; END IF;
 RETURN NEW;
END $$;
--> statement-breakpoint
CREATE TRIGGER assignment_capacity BEFORE INSERT OR UPDATE ON work_assignments FOR EACH ROW EXECUTE FUNCTION app_assignment_capacity();

--> statement-breakpoint
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
ALTER TABLE "model_profiles" FORCE ROW LEVEL SECURITY;
--> statement-breakpoint
CREATE TRIGGER "model_profiles_touch" BEFORE UPDATE ON "model_profiles" FOR EACH ROW EXECUTE FUNCTION app_touch_updated_at();
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
ALTER TABLE "agent_build_requests" FORCE ROW LEVEL SECURITY;
--> statement-breakpoint
CREATE TRIGGER "agent_build_requests_touch" BEFORE UPDATE ON "agent_build_requests" FOR EACH ROW EXECUTE FUNCTION app_touch_updated_at();
--> statement-breakpoint
ALTER TABLE "agent_build_answers" FORCE ROW LEVEL SECURITY;
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
ALTER TABLE "reception_sessions" FORCE ROW LEVEL SECURITY;
--> statement-breakpoint
CREATE TRIGGER "reception_sessions_touch" BEFORE UPDATE ON "reception_sessions" FOR EACH ROW EXECUTE FUNCTION app_touch_updated_at();
--> statement-breakpoint
ALTER TABLE "reception_waits" FORCE ROW LEVEL SECURITY;
--> statement-breakpoint
CREATE TRIGGER "reception_waits_touch" BEFORE UPDATE ON "reception_waits" FOR EACH ROW EXECUTE FUNCTION app_touch_updated_at();
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
ALTER TABLE "report_requests" FORCE ROW LEVEL SECURITY;
--> statement-breakpoint
CREATE TRIGGER "report_requests_touch" BEFORE UPDATE ON "report_requests" FOR EACH ROW EXECUTE FUNCTION app_touch_updated_at();
--> statement-breakpoint
ALTER TABLE "report_sources" FORCE ROW LEVEL SECURITY;
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
ALTER TABLE "runtime_session_operations" FORCE ROW LEVEL SECURITY;
--> statement-breakpoint
CREATE TRIGGER "runtime_session_operations_touch" BEFORE UPDATE ON "runtime_session_operations" FOR EACH ROW EXECUTE FUNCTION app_touch_updated_at();
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
