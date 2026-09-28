CREATE TABLE "vh_asset" (
	"id" uuid PRIMARY KEY DEFAULT gen_random_uuid() NOT NULL,
	"tenant_id" uuid NOT NULL,
	"project_id" uuid NOT NULL,
	"tower_id" uuid,
	"apartment_id" uuid,
	"code" text NOT NULL,
	"name" text NOT NULL,
	"category" text NOT NULL,
	"manufacturer" text,
	"model" text,
	"serial_number" text,
	"installed_at" timestamp with time zone,
	"warranty_until" timestamp with time zone,
	"status" text NOT NULL,
	"metadata_json" jsonb NOT NULL,
	"created_at" timestamp with time zone DEFAULT now() NOT NULL,
	"version" bigint DEFAULT 1 NOT NULL,
	"updated_at" timestamp with time zone DEFAULT now() NOT NULL,
	CONSTRAINT "vh_asset_uq_0" UNIQUE("tenant_id","project_id","code"),
	CONSTRAINT "vh_asset_uq_1" UNIQUE("tenant_id","id"),
	CONSTRAINT "vh_asset_uq_2" UNIQUE("tenant_id","project_id","id"),
	CONSTRAINT "vh_asset_status_ck" CHECK ("vh_asset"."status" in ('ACTIVE', 'OUT_OF_SERVICE', 'RETIRED')),
	CONSTRAINT "vh_asset_ck_0" CHECK (apartment_id IS NULL OR tower_id IS NOT NULL),
	CONSTRAINT "vh_asset_ck_1" CHECK (version > 0)
);
--> statement-breakpoint
ALTER TABLE "vh_asset" ENABLE ROW LEVEL SECURITY;--> statement-breakpoint
CREATE TABLE "vh_incident_asset" (
	"tenant_id" uuid NOT NULL,
	"project_id" uuid NOT NULL,
	"incident_id" uuid NOT NULL,
	"asset_id" uuid NOT NULL,
	"relationship" text NOT NULL,
	"created_at" timestamp with time zone DEFAULT now() NOT NULL,
	CONSTRAINT "vh_incident_asset_pk" PRIMARY KEY("tenant_id","incident_id","asset_id"),
	CONSTRAINT "vh_incident_asset_relationship_ck" CHECK ("vh_incident_asset"."relationship" in ('AFFECTED', 'SUSPECTED', 'CAUSAL'))
);
--> statement-breakpoint
ALTER TABLE "vh_incident_asset" ENABLE ROW LEVEL SECURITY;--> statement-breakpoint
CREATE TABLE "vh_work_appointment" (
	"id" uuid PRIMARY KEY DEFAULT gen_random_uuid() NOT NULL,
	"tenant_id" uuid NOT NULL,
	"project_id" uuid NOT NULL,
	"incident_id" uuid NOT NULL,
	"task_id" uuid NOT NULL,
	"work_order_id" uuid NOT NULL,
	"resident_report_id" uuid,
	"requested_by_user_id" text NOT NULL,
	"starts_at" timestamp with time zone NOT NULL,
	"ends_at" timestamp with time zone NOT NULL,
	"timezone" text NOT NULL,
	"status" text NOT NULL,
	"confirmed_by_user_id" text,
	"confirmed_at" timestamp with time zone,
	"cancellation_reason" text,
	"idempotency_key" text NOT NULL,
	"created_at" timestamp with time zone DEFAULT now() NOT NULL,
	"version" bigint DEFAULT 1 NOT NULL,
	"updated_at" timestamp with time zone DEFAULT now() NOT NULL,
	CONSTRAINT "vh_work_appointment_uq_0" UNIQUE("tenant_id","idempotency_key"),
	CONSTRAINT "vh_work_appointment_uq_1" UNIQUE("tenant_id","id"),
	CONSTRAINT "vh_work_appointment_uq_2" UNIQUE("tenant_id","project_id","id"),
	CONSTRAINT "vh_work_appointment_status_ck" CHECK ("vh_work_appointment"."status" in ('PROPOSED', 'CONFIRMED', 'COMPLETED', 'CANCELLED')),
	CONSTRAINT "vh_work_appointment_ck_0" CHECK (ends_at > starts_at),
	CONSTRAINT "vh_work_appointment_ck_1" CHECK (status NOT IN ('CONFIRMED','COMPLETED') OR (confirmed_by_user_id IS NOT NULL AND confirmed_at IS NOT NULL)),
	CONSTRAINT "vh_work_appointment_ck_2" CHECK (version > 0)
);
--> statement-breakpoint
ALTER TABLE "vh_work_appointment" ENABLE ROW LEVEL SECURITY;--> statement-breakpoint
CREATE TABLE "vh_work_assignment" (
	"id" uuid PRIMARY KEY DEFAULT gen_random_uuid() NOT NULL,
	"tenant_id" uuid NOT NULL,
	"project_id" uuid NOT NULL,
	"incident_id" uuid NOT NULL,
	"task_id" uuid NOT NULL,
	"work_order_id" uuid NOT NULL,
	"team_id" uuid NOT NULL,
	"team_member_id" uuid,
	"assigned_by_user_id" text NOT NULL,
	"offered_at" timestamp with time zone NOT NULL,
	"respond_by" timestamp with time zone,
	"accepted_at" timestamp with time zone,
	"ended_at" timestamp with time zone,
	"status" text NOT NULL,
	"reason" text,
	"idempotency_key" text NOT NULL,
	"created_at" timestamp with time zone DEFAULT now() NOT NULL,
	"version" bigint DEFAULT 1 NOT NULL,
	"updated_at" timestamp with time zone DEFAULT now() NOT NULL,
	CONSTRAINT "vh_work_assignment_uq_0" UNIQUE("tenant_id","idempotency_key"),
	CONSTRAINT "vh_work_assignment_uq_1" UNIQUE("tenant_id","id"),
	CONSTRAINT "vh_work_assignment_uq_2" UNIQUE("tenant_id","project_id","id"),
	CONSTRAINT "vh_work_assignment_uq_3" UNIQUE("tenant_id","project_id","incident_id","task_id","work_order_id","id"),
	CONSTRAINT "vh_work_assignment_status_ck" CHECK ("vh_work_assignment"."status" in ('OFFERED', 'ACCEPTED', 'REJECTED', 'RELEASED', 'COMPLETED')),
	CONSTRAINT "vh_work_assignment_ck_0" CHECK (respond_by IS NULL OR respond_by > offered_at),
	CONSTRAINT "vh_work_assignment_ck_1" CHECK (status<>'ACCEPTED' OR accepted_at IS NOT NULL),
	CONSTRAINT "vh_work_assignment_ck_2" CHECK (status NOT IN ('REJECTED','RELEASED','COMPLETED') OR ended_at IS NOT NULL),
	CONSTRAINT "vh_work_assignment_ck_3" CHECK (version > 0)
);
--> statement-breakpoint
ALTER TABLE "vh_work_assignment" ENABLE ROW LEVEL SECURITY;--> statement-breakpoint
CREATE TABLE "vh_work_progress" (
	"id" uuid PRIMARY KEY DEFAULT gen_random_uuid() NOT NULL,
	"tenant_id" uuid NOT NULL,
	"project_id" uuid NOT NULL,
	"incident_id" uuid NOT NULL,
	"task_id" uuid NOT NULL,
	"work_order_id" uuid NOT NULL,
	"assignment_id" uuid,
	"business_event_id" uuid NOT NULL,
	"actor_user_id" text NOT NULL,
	"stage" text NOT NULL,
	"percent_complete" integer,
	"expected_completion_at" timestamp with time zone,
	"estimated_by_user_id" text,
	"estimate_reason" text,
	"note" text NOT NULL,
	"occurred_at" timestamp with time zone NOT NULL,
	"idempotency_key" text NOT NULL,
	"created_at" timestamp with time zone DEFAULT now() NOT NULL,
	CONSTRAINT "vh_work_progress_uq_0" UNIQUE("tenant_id","idempotency_key"),
	CONSTRAINT "vh_work_progress_uq_1" UNIQUE("tenant_id","business_event_id"),
	CONSTRAINT "vh_work_progress_uq_2" UNIQUE("tenant_id","id"),
	CONSTRAINT "vh_work_progress_uq_3" UNIQUE("tenant_id","project_id","id"),
	CONSTRAINT "vh_work_progress_uq_4" UNIQUE("tenant_id","project_id","incident_id","id"),
	CONSTRAINT "vh_work_progress_stage_ck" CHECK ("vh_work_progress"."stage" in ('ACKNOWLEDGED', 'EN_ROUTE', 'ON_SITE', 'DIAGNOSING', 'WAITING_PARTS', 'WAITING_ACCESS', 'REPAIRING', 'READY_FOR_QC', 'COMPLETED')),
	CONSTRAINT "vh_work_progress_ck_0" CHECK (percent_complete IS NULL OR percent_complete BETWEEN 0 AND 100),
	CONSTRAINT "vh_work_progress_ck_1" CHECK (expected_completion_at IS NULL OR (estimated_by_user_id IS NOT NULL AND estimate_reason IS NOT NULL))
);
--> statement-breakpoint
ALTER TABLE "vh_work_progress" ENABLE ROW LEVEL SECURITY;--> statement-breakpoint
CREATE TABLE "vh_provider_event" (
	"id" uuid PRIMARY KEY DEFAULT gen_random_uuid() NOT NULL,
	"tenant_id" uuid NOT NULL,
	"provider" text NOT NULL,
	"provider_event_id" text NOT NULL,
	"event_type" text NOT NULL,
	"payload_hash" text NOT NULL,
	"sanitized_payload_json" jsonb NOT NULL,
	"signature_verified_at" timestamp with time zone NOT NULL,
	"received_at" timestamp with time zone NOT NULL,
	"subject_type" text,
	"subject_ref" text,
	"status" text NOT NULL,
	"attempt_count" integer NOT NULL,
	"processed_at" timestamp with time zone,
	"rejection_reason" text,
	"created_at" timestamp with time zone DEFAULT now() NOT NULL,
	"version" bigint DEFAULT 1 NOT NULL,
	"updated_at" timestamp with time zone DEFAULT now() NOT NULL,
	CONSTRAINT "vh_provider_event_uq_0" UNIQUE("tenant_id","provider","provider_event_id"),
	CONSTRAINT "vh_provider_event_uq_1" UNIQUE("tenant_id","id"),
	CONSTRAINT "vh_provider_event_status_ck" CHECK ("vh_provider_event"."status" in ('RECEIVED', 'PROCESSING', 'PROCESSED', 'REJECTED')),
	CONSTRAINT "vh_provider_event_ck_0" CHECK (attempt_count >= 0),
	CONSTRAINT "vh_provider_event_ck_1" CHECK (status<>'PROCESSED' OR processed_at IS NOT NULL),
	CONSTRAINT "vh_provider_event_ck_2" CHECK (signature_verified_at >= received_at),
	CONSTRAINT "vh_provider_event_ck_3" CHECK (version > 0)
);
--> statement-breakpoint
ALTER TABLE "vh_provider_event" ENABLE ROW LEVEL SECURITY;--> statement-breakpoint
CREATE TABLE "vh_notification_delivery" (
	"id" uuid PRIMARY KEY DEFAULT gen_random_uuid() NOT NULL,
	"tenant_id" uuid NOT NULL,
	"project_id" uuid NOT NULL,
	"notification_id" uuid NOT NULL,
	"report_update_id" uuid,
	"channel" text NOT NULL,
	"provider" text NOT NULL,
	"destination_ref" text NOT NULL,
	"provider_message_ref" text,
	"attempt_no" integer NOT NULL,
	"idempotency_key" text NOT NULL,
	"status" text NOT NULL,
	"available_at" timestamp with time zone NOT NULL,
	"sent_at" timestamp with time zone,
	"delivered_at" timestamp with time zone,
	"last_error_code" text,
	"created_at" timestamp with time zone DEFAULT now() NOT NULL,
	"version" bigint DEFAULT 1 NOT NULL,
	"updated_at" timestamp with time zone DEFAULT now() NOT NULL,
	CONSTRAINT "vh_notification_delivery_uq_0" UNIQUE("tenant_id","notification_id","channel","attempt_no"),
	CONSTRAINT "vh_notification_delivery_uq_1" UNIQUE("tenant_id","idempotency_key"),
	CONSTRAINT "vh_notification_delivery_uq_2" UNIQUE("provider","provider_message_ref"),
	CONSTRAINT "vh_notification_delivery_uq_3" UNIQUE("tenant_id","id"),
	CONSTRAINT "vh_notification_delivery_uq_4" UNIQUE("tenant_id","project_id","id"),
	CONSTRAINT "vh_notification_delivery_channel_ck" CHECK ("vh_notification_delivery"."channel" in ('IN_APP', 'EMAIL', 'SMS', 'PUSH', 'CHAT')),
	CONSTRAINT "vh_notification_delivery_status_ck" CHECK ("vh_notification_delivery"."status" in ('QUEUED', 'SENDING', 'DELIVERED', 'FAILED')),
	CONSTRAINT "vh_notification_delivery_ck_0" CHECK (attempt_no > 0),
	CONSTRAINT "vh_notification_delivery_ck_1" CHECK (status<>'DELIVERED' OR (delivered_at IS NOT NULL AND provider_message_ref IS NOT NULL)),
	CONSTRAINT "vh_notification_delivery_ck_2" CHECK (version > 0)
);
--> statement-breakpoint
ALTER TABLE "vh_notification_delivery" ENABLE ROW LEVEL SECURITY;--> statement-breakpoint
CREATE TABLE "vh_report_update" (
	"id" uuid PRIMARY KEY DEFAULT gen_random_uuid() NOT NULL,
	"tenant_id" uuid NOT NULL,
	"project_id" uuid NOT NULL,
	"incident_id" uuid NOT NULL,
	"report_id" uuid NOT NULL,
	"recipient_user_id" text NOT NULL,
	"business_event_id" uuid NOT NULL,
	"work_progress_id" uuid,
	"sequence_no" bigint NOT NULL,
	"incident_version" bigint NOT NULL,
	"headline" text NOT NULL,
	"public_summary" text NOT NULL,
	"public_status" text NOT NULL,
	"expected_completion_at" timestamp with time zone,
	"source_occurred_at" timestamp with time zone NOT NULL,
	"prepared_by_type" text NOT NULL,
	"prepared_by_id" text NOT NULL,
	"idempotency_key" text NOT NULL,
	"created_at" timestamp with time zone DEFAULT now() NOT NULL,
	CONSTRAINT "vh_report_update_uq_0" UNIQUE("tenant_id","report_id","sequence_no"),
	CONSTRAINT "vh_report_update_uq_1" UNIQUE("tenant_id","report_id","business_event_id"),
	CONSTRAINT "vh_report_update_uq_2" UNIQUE("tenant_id","idempotency_key"),
	CONSTRAINT "vh_report_update_uq_3" UNIQUE("tenant_id","id"),
	CONSTRAINT "vh_report_update_uq_4" UNIQUE("tenant_id","project_id","id"),
	CONSTRAINT "vh_report_update_public_status_ck" CHECK ("vh_report_update"."public_status" in ('RECEIVED', 'ASSIGNED', 'IN_PROGRESS', 'WAITING', 'RESOLVED', 'CLOSED')),
	CONSTRAINT "vh_report_update_prepared_by_type_ck" CHECK ("vh_report_update"."prepared_by_type" in ('HUMAN', 'SYSTEM', 'AGENT')),
	CONSTRAINT "vh_report_update_ck_0" CHECK (sequence_no > 0),
	CONSTRAINT "vh_report_update_ck_1" CHECK (incident_version > 0)
);
--> statement-breakpoint
ALTER TABLE "vh_report_update" ENABLE ROW LEVEL SECURITY;--> statement-breakpoint
CREATE TABLE "vh_escalation" (
	"id" uuid PRIMARY KEY DEFAULT gen_random_uuid() NOT NULL,
	"tenant_id" uuid NOT NULL,
	"project_id" uuid NOT NULL,
	"incident_id" uuid NOT NULL,
	"incident_sla_id" uuid,
	"assigned_team_id" uuid,
	"reason" text NOT NULL,
	"level" integer NOT NULL,
	"raised_by_type" text NOT NULL,
	"raised_by_id" text NOT NULL,
	"raised_at" timestamp with time zone NOT NULL,
	"status" text NOT NULL,
	"acknowledged_by_user_id" text,
	"acknowledged_at" timestamp with time zone,
	"resolved_at" timestamp with time zone,
	"resolution_note" text,
	"idempotency_key" text NOT NULL,
	"created_at" timestamp with time zone DEFAULT now() NOT NULL,
	"version" bigint DEFAULT 1 NOT NULL,
	"updated_at" timestamp with time zone DEFAULT now() NOT NULL,
	CONSTRAINT "vh_escalation_uq_0" UNIQUE("tenant_id","idempotency_key"),
	CONSTRAINT "vh_escalation_uq_1" UNIQUE("tenant_id","id"),
	CONSTRAINT "vh_escalation_uq_2" UNIQUE("tenant_id","project_id","id"),
	CONSTRAINT "vh_escalation_reason_ck" CHECK ("vh_escalation"."reason" in ('RESPONSE_BREACH', 'RESOLUTION_BREACH', 'SAFETY', 'MANUAL')),
	CONSTRAINT "vh_escalation_raised_by_type_ck" CHECK ("vh_escalation"."raised_by_type" in ('HUMAN', 'SYSTEM', 'AGENT')),
	CONSTRAINT "vh_escalation_status_ck" CHECK ("vh_escalation"."status" in ('OPEN', 'ACKNOWLEDGED', 'RESOLVED')),
	CONSTRAINT "vh_escalation_ck_0" CHECK (level > 0),
	CONSTRAINT "vh_escalation_ck_1" CHECK (status NOT IN ('ACKNOWLEDGED','RESOLVED') OR (acknowledged_by_user_id IS NOT NULL AND acknowledged_at IS NOT NULL)),
	CONSTRAINT "vh_escalation_ck_2" CHECK (status<>'RESOLVED' OR (resolved_at IS NOT NULL AND resolution_note IS NOT NULL)),
	CONSTRAINT "vh_escalation_ck_3" CHECK (version > 0)
);
--> statement-breakpoint
ALTER TABLE "vh_escalation" ENABLE ROW LEVEL SECURITY;--> statement-breakpoint
CREATE TABLE "vh_incident_sla" (
	"id" uuid PRIMARY KEY DEFAULT gen_random_uuid() NOT NULL,
	"tenant_id" uuid NOT NULL,
	"project_id" uuid NOT NULL,
	"incident_id" uuid NOT NULL,
	"policy_id" uuid NOT NULL,
	"started_at" timestamp with time zone NOT NULL,
	"response_due_at" timestamp with time zone NOT NULL,
	"resolution_due_at" timestamp with time zone NOT NULL,
	"responded_at" timestamp with time zone,
	"resolved_at" timestamp with time zone,
	"created_at" timestamp with time zone DEFAULT now() NOT NULL,
	"version" bigint DEFAULT 1 NOT NULL,
	"updated_at" timestamp with time zone DEFAULT now() NOT NULL,
	CONSTRAINT "vh_incident_sla_uq_0" UNIQUE("tenant_id","incident_id"),
	CONSTRAINT "vh_incident_sla_uq_1" UNIQUE("tenant_id","id"),
	CONSTRAINT "vh_incident_sla_uq_2" UNIQUE("tenant_id","project_id","id"),
	CONSTRAINT "vh_incident_sla_uq_3" UNIQUE("tenant_id","project_id","incident_id","id"),
	CONSTRAINT "vh_incident_sla_ck_0" CHECK (response_due_at >= started_at),
	CONSTRAINT "vh_incident_sla_ck_1" CHECK (resolution_due_at >= response_due_at),
	CONSTRAINT "vh_incident_sla_ck_2" CHECK (responded_at IS NULL OR responded_at >= started_at),
	CONSTRAINT "vh_incident_sla_ck_3" CHECK (resolved_at IS NULL OR resolved_at >= started_at),
	CONSTRAINT "vh_incident_sla_ck_4" CHECK (version > 0)
);
--> statement-breakpoint
ALTER TABLE "vh_incident_sla" ENABLE ROW LEVEL SECURITY;--> statement-breakpoint
CREATE TABLE "vh_sla_policy" (
	"id" uuid PRIMARY KEY DEFAULT gen_random_uuid() NOT NULL,
	"tenant_id" uuid NOT NULL,
	"project_id" uuid NOT NULL,
	"code" text NOT NULL,
	"version_no" integer NOT NULL,
	"category" text NOT NULL,
	"severity" text NOT NULL,
	"response_minutes" integer NOT NULL,
	"resolution_minutes" integer NOT NULL,
	"clock_type" text NOT NULL,
	"calendar_ref" text,
	"effective_from" timestamp with time zone NOT NULL,
	"effective_until" timestamp with time zone,
	"status" text NOT NULL,
	"created_at" timestamp with time zone DEFAULT now() NOT NULL,
	"version" bigint DEFAULT 1 NOT NULL,
	"updated_at" timestamp with time zone DEFAULT now() NOT NULL,
	CONSTRAINT "vh_sla_policy_uq_0" UNIQUE("tenant_id","project_id","code","version_no"),
	CONSTRAINT "vh_sla_policy_uq_1" UNIQUE("tenant_id","id"),
	CONSTRAINT "vh_sla_policy_uq_2" UNIQUE("tenant_id","project_id","id"),
	CONSTRAINT "vh_sla_policy_severity_ck" CHECK ("vh_sla_policy"."severity" in ('LOW', 'MEDIUM', 'HIGH', 'CRITICAL')),
	CONSTRAINT "vh_sla_policy_status_ck" CHECK ("vh_sla_policy"."status" in ('DRAFT', 'PUBLISHED', 'RETIRED')),
	CONSTRAINT "vh_sla_policy_ck_0" CHECK (version_no > 0),
	CONSTRAINT "vh_sla_policy_ck_1" CHECK (clock_type = 'ELAPSED'),
	CONSTRAINT "vh_sla_policy_ck_2" CHECK (response_minutes > 0),
	CONSTRAINT "vh_sla_policy_ck_3" CHECK (resolution_minutes >= response_minutes),
	CONSTRAINT "vh_sla_policy_ck_4" CHECK (effective_until IS NULL OR effective_until > effective_from),
	CONSTRAINT "vh_sla_policy_ck_5" CHECK (version > 0)
);
--> statement-breakpoint
ALTER TABLE "vh_sla_policy" ENABLE ROW LEVEL SECURITY;--> statement-breakpoint
CREATE TABLE "vh_staff_shift" (
	"id" uuid PRIMARY KEY DEFAULT gen_random_uuid() NOT NULL,
	"tenant_id" uuid NOT NULL,
	"project_id" uuid NOT NULL,
	"team_member_id" uuid NOT NULL,
	"starts_at" timestamp with time zone NOT NULL,
	"ends_at" timestamp with time zone NOT NULL,
	"status" text NOT NULL,
	"timezone" text NOT NULL,
	"created_at" timestamp with time zone DEFAULT now() NOT NULL,
	"version" bigint DEFAULT 1 NOT NULL,
	"updated_at" timestamp with time zone DEFAULT now() NOT NULL,
	CONSTRAINT "vh_staff_shift_uq_0" UNIQUE("tenant_id","id"),
	CONSTRAINT "vh_staff_shift_uq_1" UNIQUE("tenant_id","project_id","id"),
	CONSTRAINT "vh_staff_shift_status_ck" CHECK ("vh_staff_shift"."status" in ('PLANNED', 'CONFIRMED', 'COMPLETED', 'CANCELLED')),
	CONSTRAINT "vh_staff_shift_ck_0" CHECK (ends_at > starts_at),
	CONSTRAINT "vh_staff_shift_ck_1" CHECK (version > 0)
);
--> statement-breakpoint
ALTER TABLE "vh_staff_shift" ENABLE ROW LEVEL SECURITY;--> statement-breakpoint
CREATE TABLE "vh_staff_skill" (
	"id" uuid PRIMARY KEY DEFAULT gen_random_uuid() NOT NULL,
	"tenant_id" uuid NOT NULL,
	"project_id" uuid NOT NULL,
	"property_membership_id" uuid NOT NULL,
	"skill_code" text NOT NULL,
	"proficiency" text NOT NULL,
	"certificate_ref" text,
	"verified_by_user_id" text NOT NULL,
	"verified_at" timestamp with time zone NOT NULL,
	"valid_until" timestamp with time zone,
	"created_at" timestamp with time zone DEFAULT now() NOT NULL,
	"version" bigint DEFAULT 1 NOT NULL,
	"updated_at" timestamp with time zone DEFAULT now() NOT NULL,
	CONSTRAINT "vh_staff_skill_uq_0" UNIQUE("tenant_id","property_membership_id","skill_code"),
	CONSTRAINT "vh_staff_skill_uq_1" UNIQUE("tenant_id","id"),
	CONSTRAINT "vh_staff_skill_uq_2" UNIQUE("tenant_id","project_id","id"),
	CONSTRAINT "vh_staff_skill_proficiency_ck" CHECK ("vh_staff_skill"."proficiency" in ('BASIC', 'QUALIFIED', 'EXPERT')),
	CONSTRAINT "vh_staff_skill_ck_0" CHECK (valid_until IS NULL OR valid_until > verified_at),
	CONSTRAINT "vh_staff_skill_ck_1" CHECK (version > 0)
);
--> statement-breakpoint
ALTER TABLE "vh_staff_skill" ENABLE ROW LEVEL SECURITY;--> statement-breakpoint
CREATE TABLE "vh_team" (
	"id" uuid PRIMARY KEY DEFAULT gen_random_uuid() NOT NULL,
	"tenant_id" uuid NOT NULL,
	"project_id" uuid NOT NULL,
	"code" text NOT NULL,
	"name" text NOT NULL,
	"specialty" text NOT NULL,
	"status" text NOT NULL,
	"created_at" timestamp with time zone DEFAULT now() NOT NULL,
	"version" bigint DEFAULT 1 NOT NULL,
	"updated_at" timestamp with time zone DEFAULT now() NOT NULL,
	CONSTRAINT "vh_team_uq_0" UNIQUE("tenant_id","project_id","code"),
	CONSTRAINT "vh_team_uq_1" UNIQUE("tenant_id","id"),
	CONSTRAINT "vh_team_uq_2" UNIQUE("tenant_id","project_id","id"),
	CONSTRAINT "vh_team_specialty_ck" CHECK ("vh_team"."specialty" in ('TECHNICAL', 'SANITATION', 'SECURITY', 'LANDSCAPE', 'MULTI')),
	CONSTRAINT "vh_team_status_ck" CHECK ("vh_team"."status" in ('ACTIVE', 'INACTIVE')),
	CONSTRAINT "vh_team_ck_0" CHECK (version > 0)
);
--> statement-breakpoint
ALTER TABLE "vh_team" ENABLE ROW LEVEL SECURITY;--> statement-breakpoint
CREATE TABLE "vh_team_member" (
	"id" uuid PRIMARY KEY DEFAULT gen_random_uuid() NOT NULL,
	"tenant_id" uuid NOT NULL,
	"project_id" uuid NOT NULL,
	"team_id" uuid NOT NULL,
	"property_membership_id" uuid NOT NULL,
	"role" text NOT NULL,
	"valid_from" timestamp with time zone NOT NULL,
	"valid_until" timestamp with time zone,
	"status" text NOT NULL,
	"created_at" timestamp with time zone DEFAULT now() NOT NULL,
	"version" bigint DEFAULT 1 NOT NULL,
	"updated_at" timestamp with time zone DEFAULT now() NOT NULL,
	CONSTRAINT "vh_team_member_uq_0" UNIQUE("tenant_id","id"),
	CONSTRAINT "vh_team_member_uq_1" UNIQUE("tenant_id","project_id","id"),
	CONSTRAINT "vh_team_member_uq_2" UNIQUE("tenant_id","project_id","team_id","id"),
	CONSTRAINT "vh_team_member_role_ck" CHECK ("vh_team_member"."role" in ('LEAD', 'TECHNICIAN', 'DISPATCHER')),
	CONSTRAINT "vh_team_member_status_ck" CHECK ("vh_team_member"."status" in ('ACTIVE', 'INACTIVE')),
	CONSTRAINT "vh_team_member_ck_0" CHECK (valid_until IS NULL OR valid_until > valid_from),
	CONSTRAINT "vh_team_member_ck_1" CHECK (version > 0)
);
--> statement-breakpoint
ALTER TABLE "vh_team_member" ENABLE ROW LEVEL SECURITY;--> statement-breakpoint
CREATE TABLE "platform_handoff" (
	"id" uuid PRIMARY KEY DEFAULT gen_random_uuid() NOT NULL,
	"tenant_id" uuid NOT NULL,
	"source_conversation_id" uuid,
	"source_workflow_session_id" uuid,
	"target_agent_version_id" uuid NOT NULL,
	"target_workflow_session_id" uuid,
	"domain_namespace" text NOT NULL,
	"subject_type" text NOT NULL,
	"subject_ref" text NOT NULL,
	"subject_version" bigint,
	"reason" text NOT NULL,
	"context_json" jsonb NOT NULL,
	"request_hash" text NOT NULL,
	"idempotency_key" text NOT NULL,
	"correlation_id" text NOT NULL,
	"trace_id" text NOT NULL,
	"status" text NOT NULL,
	"attempt_count" integer NOT NULL,
	"next_attempt_at" timestamp with time zone NOT NULL,
	"expires_at" timestamp with time zone NOT NULL,
	"accepted_at" timestamp with time zone,
	"completed_at" timestamp with time zone,
	"last_error_code" text,
	"created_at" timestamp with time zone DEFAULT now() NOT NULL,
	"version" bigint DEFAULT 1 NOT NULL,
	"updated_at" timestamp with time zone DEFAULT now() NOT NULL,
	CONSTRAINT "platform_handoff_uq_0" UNIQUE("tenant_id","idempotency_key"),
	CONSTRAINT "platform_handoff_uq_1" UNIQUE("tenant_id","id"),
	CONSTRAINT "platform_handoff_status_ck" CHECK ("platform_handoff"."status" in ('OFFERED', 'ACCEPTED', 'COMPLETED', 'FAILED', 'EXPIRED', 'CANCELLED')),
	CONSTRAINT "platform_handoff_ck_0" CHECK (num_nonnulls(source_conversation_id, source_workflow_session_id) = 1),
	CONSTRAINT "platform_handoff_ck_1" CHECK (attempt_count >= 0),
	CONSTRAINT "platform_handoff_ck_2" CHECK (expires_at > created_at),
	CONSTRAINT "platform_handoff_ck_3" CHECK (status NOT IN ('ACCEPTED','COMPLETED') OR (target_workflow_session_id IS NOT NULL AND accepted_at IS NOT NULL)),
	CONSTRAINT "platform_handoff_ck_4" CHECK (status<>'COMPLETED' OR completed_at IS NOT NULL),
	CONSTRAINT "platform_handoff_ck_5" CHECK (version > 0)
);
--> statement-breakpoint
ALTER TABLE "platform_handoff" ENABLE ROW LEVEL SECURITY;--> statement-breakpoint
CREATE TABLE "platform_runtime_checkpoint" (
	"id" uuid PRIMARY KEY DEFAULT gen_random_uuid() NOT NULL,
	"tenant_id" uuid NOT NULL,
	"workflow_session_id" uuid NOT NULL,
	"checkpoint_no" bigint NOT NULL,
	"runtime_provider" text NOT NULL,
	"runtime_version" text NOT NULL,
	"state_schema_version" integer NOT NULL,
	"storage_ref" text NOT NULL,
	"content_hash" text NOT NULL,
	"last_message_sequence" bigint NOT NULL,
	"fencing_token" bigint NOT NULL,
	"created_by_run_id" uuid,
	"created_at" timestamp with time zone DEFAULT now() NOT NULL,
	CONSTRAINT "platform_runtime_checkpoint_uq_0" UNIQUE("tenant_id","workflow_session_id","checkpoint_no"),
	CONSTRAINT "platform_runtime_checkpoint_uq_1" UNIQUE("tenant_id","id"),
	CONSTRAINT "platform_runtime_checkpoint_ck_0" CHECK (checkpoint_no > 0),
	CONSTRAINT "platform_runtime_checkpoint_ck_1" CHECK (state_schema_version > 0),
	CONSTRAINT "platform_runtime_checkpoint_ck_2" CHECK (last_message_sequence >= 0),
	CONSTRAINT "platform_runtime_checkpoint_ck_3" CHECK (fencing_token >= 0)
);
--> statement-breakpoint
ALTER TABLE "platform_runtime_checkpoint" ENABLE ROW LEVEL SECURITY;--> statement-breakpoint
CREATE TABLE "platform_runtime_message" (
	"id" uuid PRIMARY KEY DEFAULT gen_random_uuid() NOT NULL,
	"tenant_id" uuid NOT NULL,
	"workflow_session_id" uuid NOT NULL,
	"sequence_no" bigint NOT NULL,
	"sender_participant_id" uuid,
	"recipient_participant_id" uuid,
	"agent_run_id" uuid,
	"reply_to_message_id" uuid,
	"kind" text NOT NULL,
	"body" text NOT NULL,
	"payload_json" jsonb NOT NULL,
	"schema_version" integer NOT NULL,
	"idempotency_key" text NOT NULL,
	"correlation_id" text NOT NULL,
	"created_at" timestamp with time zone DEFAULT now() NOT NULL,
	CONSTRAINT "platform_runtime_message_uq_0" UNIQUE("tenant_id","workflow_session_id","sequence_no"),
	CONSTRAINT "platform_runtime_message_uq_1" UNIQUE("tenant_id","workflow_session_id","idempotency_key"),
	CONSTRAINT "platform_runtime_message_uq_2" UNIQUE("tenant_id","id"),
	CONSTRAINT "platform_runtime_message_uq_3" UNIQUE("tenant_id","workflow_session_id","id"),
	CONSTRAINT "platform_runtime_message_kind_ck" CHECK ("platform_runtime_message"."kind" in ('REQUEST', 'FINDING', 'PROPOSAL', 'DECISION', 'SYSTEM')),
	CONSTRAINT "platform_runtime_message_ck_0" CHECK (sequence_no > 0),
	CONSTRAINT "platform_runtime_message_ck_1" CHECK (schema_version > 0),
	CONSTRAINT "platform_runtime_message_ck_2" CHECK ((kind='SYSTEM' AND sender_participant_id IS NULL AND agent_run_id IS NULL) OR (kind<>'SYSTEM' AND sender_participant_id IS NOT NULL))
);
--> statement-breakpoint
ALTER TABLE "platform_runtime_message" ENABLE ROW LEVEL SECURITY;--> statement-breakpoint
CREATE TABLE "platform_session_control" (
	"id" uuid PRIMARY KEY DEFAULT gen_random_uuid() NOT NULL,
	"tenant_id" uuid NOT NULL,
	"workflow_session_id" uuid NOT NULL,
	"parent_workflow_session_id" uuid,
	"coordinator_participant_id" uuid,
	"purpose" text NOT NULL,
	"initiation_key" text NOT NULL,
	"request_hash" text NOT NULL,
	"lease_owner" text,
	"lease_expires_at" timestamp with time zone,
	"fencing_token" bigint NOT NULL,
	"heartbeat_at" timestamp with time zone,
	"deadline_at" timestamp with time zone,
	"max_turns" integer NOT NULL,
	"max_tool_calls" integer NOT NULL,
	"stop_reason" text,
	"created_at" timestamp with time zone DEFAULT now() NOT NULL,
	"version" bigint DEFAULT 1 NOT NULL,
	"updated_at" timestamp with time zone DEFAULT now() NOT NULL,
	CONSTRAINT "platform_session_control_uq_0" UNIQUE("tenant_id","workflow_session_id"),
	CONSTRAINT "platform_session_control_uq_1" UNIQUE("tenant_id","initiation_key"),
	CONSTRAINT "platform_session_control_uq_2" UNIQUE("tenant_id","id"),
	CONSTRAINT "platform_session_control_purpose_ck" CHECK ("platform_session_control"."purpose" in ('TRIAGE', 'PLAN', 'FOLLOW_UP', 'QC', 'REPLAN')),
	CONSTRAINT "platform_session_control_ck_0" CHECK (fencing_token >= 0),
	CONSTRAINT "platform_session_control_ck_1" CHECK (max_turns > 0),
	CONSTRAINT "platform_session_control_ck_2" CHECK (max_tool_calls >= 0),
	CONSTRAINT "platform_session_control_ck_3" CHECK ((lease_owner IS NULL) = (lease_expires_at IS NULL)),
	CONSTRAINT "platform_session_control_ck_4" CHECK (parent_workflow_session_id IS NULL OR parent_workflow_session_id <> workflow_session_id),
	CONSTRAINT "platform_session_control_ck_5" CHECK (version > 0)
);
--> statement-breakpoint
ALTER TABLE "platform_session_control" ENABLE ROW LEVEL SECURITY;--> statement-breakpoint
CREATE TABLE "platform_session_participant" (
	"id" uuid PRIMARY KEY DEFAULT gen_random_uuid() NOT NULL,
	"tenant_id" uuid NOT NULL,
	"workflow_session_id" uuid NOT NULL,
	"agent_version_id" uuid NOT NULL,
	"role" text NOT NULL,
	"capability_scope_json" jsonb NOT NULL,
	"status" text NOT NULL,
	"joined_at" timestamp with time zone,
	"left_at" timestamp with time zone,
	"created_at" timestamp with time zone DEFAULT now() NOT NULL,
	"version" bigint DEFAULT 1 NOT NULL,
	"updated_at" timestamp with time zone DEFAULT now() NOT NULL,
	CONSTRAINT "platform_session_participant_uq_0" UNIQUE("tenant_id","workflow_session_id","agent_version_id"),
	CONSTRAINT "platform_session_participant_uq_1" UNIQUE("tenant_id","id"),
	CONSTRAINT "platform_session_participant_uq_2" UNIQUE("tenant_id","workflow_session_id","id"),
	CONSTRAINT "platform_session_participant_role_ck" CHECK ("platform_session_participant"."role" in ('COORDINATOR', 'SPECIALIST', 'REVIEWER')),
	CONSTRAINT "platform_session_participant_status_ck" CHECK ("platform_session_participant"."status" in ('INVITED', 'ACTIVE', 'LEFT', 'FAILED')),
	CONSTRAINT "platform_session_participant_ck_0" CHECK (left_at IS NULL OR (joined_at IS NOT NULL AND left_at >= joined_at)),
	CONSTRAINT "platform_session_participant_ck_1" CHECK (version > 0)
);
--> statement-breakpoint
ALTER TABLE "platform_session_participant" ENABLE ROW LEVEL SECURITY;--> statement-breakpoint
CREATE TABLE "platform_session_wait" (
	"id" uuid PRIMARY KEY DEFAULT gen_random_uuid() NOT NULL,
	"tenant_id" uuid NOT NULL,
	"workflow_session_id" uuid NOT NULL,
	"run_step_id" uuid,
	"participant_id" uuid,
	"wait_key" text NOT NULL,
	"wait_type" text NOT NULL,
	"expected_event_type" text,
	"expected_subject_ref" text,
	"status" text NOT NULL,
	"deadline_at" timestamp with time zone,
	"satisfied_at" timestamp with time zone,
	"response_event_ref" text,
	"created_at" timestamp with time zone DEFAULT now() NOT NULL,
	"version" bigint DEFAULT 1 NOT NULL,
	"updated_at" timestamp with time zone DEFAULT now() NOT NULL,
	CONSTRAINT "platform_session_wait_uq_0" UNIQUE("tenant_id","workflow_session_id","wait_key"),
	CONSTRAINT "platform_session_wait_uq_1" UNIQUE("tenant_id","id"),
	CONSTRAINT "platform_session_wait_wait_type_ck" CHECK ("platform_session_wait"."wait_type" in ('AGENT', 'HUMAN', 'DOMAIN_EVENT', 'TIMER')),
	CONSTRAINT "platform_session_wait_status_ck" CHECK ("platform_session_wait"."status" in ('WAITING', 'SATISFIED', 'TIMED_OUT', 'CANCELLED')),
	CONSTRAINT "platform_session_wait_ck_0" CHECK (status<>'SATISFIED' OR satisfied_at IS NOT NULL),
	CONSTRAINT "platform_session_wait_ck_1" CHECK (version > 0)
);
--> statement-breakpoint
ALTER TABLE "platform_session_wait" ENABLE ROW LEVEL SECURITY;--> statement-breakpoint
CREATE TABLE "platform_conversation" (
	"id" uuid PRIMARY KEY DEFAULT gen_random_uuid() NOT NULL,
	"tenant_id" uuid NOT NULL,
	"owner_user_id" text NOT NULL,
	"channel" text NOT NULL,
	"external_provider" text,
	"external_thread_ref" text,
	"locale" text NOT NULL,
	"status" text NOT NULL,
	"created_at" timestamp with time zone DEFAULT now() NOT NULL,
	"version" bigint DEFAULT 1 NOT NULL,
	"updated_at" timestamp with time zone DEFAULT now() NOT NULL,
	CONSTRAINT "platform_conversation_uq_0" UNIQUE("tenant_id","external_provider","external_thread_ref"),
	CONSTRAINT "platform_conversation_uq_1" UNIQUE("tenant_id","id"),
	CONSTRAINT "platform_conversation_channel_ck" CHECK ("platform_conversation"."channel" in ('WEB', 'MOBILE', 'EMAIL', 'VOICE', 'EXTERNAL')),
	CONSTRAINT "platform_conversation_status_ck" CHECK ("platform_conversation"."status" in ('OPEN', 'CLOSED', 'ARCHIVED')),
	CONSTRAINT "platform_conversation_ck_0" CHECK ((external_provider IS NULL) = (external_thread_ref IS NULL)),
	CONSTRAINT "platform_conversation_ck_1" CHECK (version > 0)
);
--> statement-breakpoint
ALTER TABLE "platform_conversation" ENABLE ROW LEVEL SECURITY;--> statement-breakpoint
CREATE TABLE "platform_conversation_message" (
	"id" uuid PRIMARY KEY DEFAULT gen_random_uuid() NOT NULL,
	"tenant_id" uuid NOT NULL,
	"conversation_id" uuid NOT NULL,
	"sequence_no" bigint NOT NULL,
	"role" text NOT NULL,
	"author_user_id" text,
	"agent_version_id" uuid,
	"body" text NOT NULL,
	"content_schema_version" integer NOT NULL,
	"metadata_json" jsonb NOT NULL,
	"idempotency_key" text NOT NULL,
	"reply_to_message_id" uuid,
	"source_event_ref" text,
	"source_subject_version" bigint,
	"created_at" timestamp with time zone DEFAULT now() NOT NULL,
	CONSTRAINT "platform_conversation_message_uq_0" UNIQUE("tenant_id","conversation_id","sequence_no"),
	CONSTRAINT "platform_conversation_message_uq_1" UNIQUE("tenant_id","conversation_id","idempotency_key"),
	CONSTRAINT "platform_conversation_message_uq_2" UNIQUE("tenant_id","id"),
	CONSTRAINT "platform_conversation_message_uq_3" UNIQUE("tenant_id","conversation_id","id"),
	CONSTRAINT "platform_conversation_message_role_ck" CHECK ("platform_conversation_message"."role" in ('USER', 'ASSISTANT', 'SYSTEM')),
	CONSTRAINT "platform_conversation_message_ck_0" CHECK (sequence_no > 0),
	CONSTRAINT "platform_conversation_message_ck_1" CHECK (content_schema_version > 0),
	CONSTRAINT "platform_conversation_message_ck_2" CHECK ((role='USER' AND author_user_id IS NOT NULL AND agent_version_id IS NULL) OR (role='ASSISTANT' AND agent_version_id IS NOT NULL AND author_user_id IS NULL) OR (role='SYSTEM' AND agent_version_id IS NULL AND author_user_id IS NULL))
);
--> statement-breakpoint
ALTER TABLE "platform_conversation_message" ENABLE ROW LEVEL SECURITY;--> statement-breakpoint
CREATE TABLE "platform_conversation_subject" (
	"tenant_id" uuid NOT NULL,
	"conversation_id" uuid NOT NULL,
	"domain_namespace" text NOT NULL,
	"subject_type" text NOT NULL,
	"subject_ref" text NOT NULL,
	"relationship" text NOT NULL,
	"created_at" timestamp with time zone DEFAULT now() NOT NULL,
	CONSTRAINT "platform_conversation_subject_pk" PRIMARY KEY("tenant_id","conversation_id","domain_namespace","subject_type","subject_ref"),
	CONSTRAINT "platform_conversation_subject_relationship_ck" CHECK ("platform_conversation_subject"."relationship" in ('INTAKE', 'TRACKING', 'FOLLOW_UP'))
);
--> statement-breakpoint
ALTER TABLE "platform_conversation_subject" ENABLE ROW LEVEL SECURITY;--> statement-breakpoint
CREATE TABLE "platform_event_receipt" (
	"id" uuid PRIMARY KEY DEFAULT gen_random_uuid() NOT NULL,
	"tenant_id" uuid NOT NULL,
	"consumer" text NOT NULL,
	"producer_namespace" text NOT NULL,
	"event_id" text NOT NULL,
	"payload_hash" text NOT NULL,
	"subject_ref" text,
	"subject_version" bigint,
	"correlation_id" text NOT NULL,
	"status" text NOT NULL,
	"attempt_count" integer NOT NULL,
	"available_at" timestamp with time zone NOT NULL,
	"lease_owner" text,
	"lease_expires_at" timestamp with time zone,
	"processed_at" timestamp with time zone,
	"last_error_code" text,
	"created_at" timestamp with time zone DEFAULT now() NOT NULL,
	"version" bigint DEFAULT 1 NOT NULL,
	"updated_at" timestamp with time zone DEFAULT now() NOT NULL,
	CONSTRAINT "platform_event_receipt_uq_0" UNIQUE("tenant_id","consumer","producer_namespace","event_id"),
	CONSTRAINT "platform_event_receipt_uq_1" UNIQUE("tenant_id","id"),
	CONSTRAINT "platform_event_receipt_status_ck" CHECK ("platform_event_receipt"."status" in ('RECEIVED', 'PROCESSING', 'PROCESSED', 'FAILED', 'DEAD_LETTER')),
	CONSTRAINT "platform_event_receipt_ck_0" CHECK (attempt_count >= 0),
	CONSTRAINT "platform_event_receipt_ck_1" CHECK ((lease_owner IS NULL) = (lease_expires_at IS NULL)),
	CONSTRAINT "platform_event_receipt_ck_2" CHECK (status<>'PROCESSED' OR processed_at IS NOT NULL),
	CONSTRAINT "platform_event_receipt_ck_3" CHECK (version > 0)
);
--> statement-breakpoint
ALTER TABLE "platform_event_receipt" ENABLE ROW LEVEL SECURITY;--> statement-breakpoint
ALTER TABLE "vh_asset" ADD CONSTRAINT "vh_asset_fk_0" FOREIGN KEY ("tenant_id") REFERENCES "public"."platform_tenant"("id") ON DELETE restrict ON UPDATE no action;--> statement-breakpoint
ALTER TABLE "vh_asset" ADD CONSTRAINT "vh_asset_fk_1" FOREIGN KEY ("tenant_id","project_id") REFERENCES "public"."vh_project"("tenant_id","id") ON DELETE restrict ON UPDATE no action;--> statement-breakpoint
ALTER TABLE "vh_asset" ADD CONSTRAINT "vh_asset_fk_2" FOREIGN KEY ("tenant_id","project_id","tower_id") REFERENCES "public"."vh_tower"("tenant_id","project_id","id") ON DELETE restrict ON UPDATE no action;--> statement-breakpoint
ALTER TABLE "vh_asset" ADD CONSTRAINT "vh_asset_fk_3" FOREIGN KEY ("tenant_id","project_id","apartment_id") REFERENCES "public"."vh_apartment"("tenant_id","project_id","id") ON DELETE restrict ON UPDATE no action;--> statement-breakpoint
ALTER TABLE "vh_incident_asset" ADD CONSTRAINT "vh_incident_asset_fk_0" FOREIGN KEY ("tenant_id") REFERENCES "public"."platform_tenant"("id") ON DELETE restrict ON UPDATE no action;--> statement-breakpoint
ALTER TABLE "vh_incident_asset" ADD CONSTRAINT "vh_incident_asset_fk_1" FOREIGN KEY ("tenant_id","project_id") REFERENCES "public"."vh_project"("tenant_id","id") ON DELETE restrict ON UPDATE no action;--> statement-breakpoint
ALTER TABLE "vh_incident_asset" ADD CONSTRAINT "vh_incident_asset_fk_2" FOREIGN KEY ("tenant_id","project_id","incident_id") REFERENCES "public"."vh_incident"("tenant_id","project_id","id") ON DELETE restrict ON UPDATE no action;--> statement-breakpoint
ALTER TABLE "vh_incident_asset" ADD CONSTRAINT "vh_incident_asset_fk_3" FOREIGN KEY ("tenant_id","project_id","asset_id") REFERENCES "public"."vh_asset"("tenant_id","project_id","id") ON DELETE restrict ON UPDATE no action;--> statement-breakpoint
ALTER TABLE "vh_work_appointment" ADD CONSTRAINT "vh_work_appointment_fk_0" FOREIGN KEY ("tenant_id") REFERENCES "public"."platform_tenant"("id") ON DELETE restrict ON UPDATE no action;--> statement-breakpoint
ALTER TABLE "vh_work_appointment" ADD CONSTRAINT "vh_work_appointment_fk_1" FOREIGN KEY ("tenant_id","project_id") REFERENCES "public"."vh_project"("tenant_id","id") ON DELETE restrict ON UPDATE no action;--> statement-breakpoint
ALTER TABLE "vh_work_appointment" ADD CONSTRAINT "vh_work_appointment_fk_2" FOREIGN KEY ("tenant_id","project_id","incident_id") REFERENCES "public"."vh_incident"("tenant_id","project_id","id") ON DELETE restrict ON UPDATE no action;--> statement-breakpoint
ALTER TABLE "vh_work_appointment" ADD CONSTRAINT "vh_work_appointment_fk_3" FOREIGN KEY ("tenant_id","project_id","incident_id","task_id") REFERENCES "public"."vh_task"("tenant_id","project_id","incident_id","id") ON DELETE restrict ON UPDATE no action;--> statement-breakpoint
ALTER TABLE "vh_work_appointment" ADD CONSTRAINT "vh_work_appointment_fk_4" FOREIGN KEY ("tenant_id","project_id","incident_id","task_id","work_order_id") REFERENCES "public"."vh_work_order"("tenant_id","project_id","incident_id","task_id","id") ON DELETE restrict ON UPDATE no action;--> statement-breakpoint
ALTER TABLE "vh_work_appointment" ADD CONSTRAINT "vh_work_appointment_fk_5" FOREIGN KEY ("tenant_id","project_id","resident_report_id") REFERENCES "public"."vh_resident_report"("tenant_id","project_id","id") ON DELETE restrict ON UPDATE no action;--> statement-breakpoint
ALTER TABLE "vh_work_appointment" ADD CONSTRAINT "vh_work_appointment_fk_6" FOREIGN KEY ("requested_by_user_id") REFERENCES "public"."users"("id") ON DELETE restrict ON UPDATE no action;--> statement-breakpoint
ALTER TABLE "vh_work_appointment" ADD CONSTRAINT "vh_work_appointment_fk_7" FOREIGN KEY ("confirmed_by_user_id") REFERENCES "public"."users"("id") ON DELETE restrict ON UPDATE no action;--> statement-breakpoint
ALTER TABLE "vh_work_assignment" ADD CONSTRAINT "vh_work_assignment_fk_0" FOREIGN KEY ("tenant_id") REFERENCES "public"."platform_tenant"("id") ON DELETE restrict ON UPDATE no action;--> statement-breakpoint
ALTER TABLE "vh_work_assignment" ADD CONSTRAINT "vh_work_assignment_fk_1" FOREIGN KEY ("tenant_id","project_id") REFERENCES "public"."vh_project"("tenant_id","id") ON DELETE restrict ON UPDATE no action;--> statement-breakpoint
ALTER TABLE "vh_work_assignment" ADD CONSTRAINT "vh_work_assignment_fk_2" FOREIGN KEY ("tenant_id","project_id","incident_id") REFERENCES "public"."vh_incident"("tenant_id","project_id","id") ON DELETE restrict ON UPDATE no action;--> statement-breakpoint
ALTER TABLE "vh_work_assignment" ADD CONSTRAINT "vh_work_assignment_fk_3" FOREIGN KEY ("tenant_id","project_id","incident_id","task_id") REFERENCES "public"."vh_task"("tenant_id","project_id","incident_id","id") ON DELETE restrict ON UPDATE no action;--> statement-breakpoint
ALTER TABLE "vh_work_assignment" ADD CONSTRAINT "vh_work_assignment_fk_4" FOREIGN KEY ("tenant_id","project_id","incident_id","task_id","work_order_id") REFERENCES "public"."vh_work_order"("tenant_id","project_id","incident_id","task_id","id") ON DELETE restrict ON UPDATE no action;--> statement-breakpoint
ALTER TABLE "vh_work_assignment" ADD CONSTRAINT "vh_work_assignment_fk_5" FOREIGN KEY ("tenant_id","project_id","team_id") REFERENCES "public"."vh_team"("tenant_id","project_id","id") ON DELETE restrict ON UPDATE no action;--> statement-breakpoint
ALTER TABLE "vh_work_assignment" ADD CONSTRAINT "vh_work_assignment_fk_6" FOREIGN KEY ("tenant_id","project_id","team_id","team_member_id") REFERENCES "public"."vh_team_member"("tenant_id","project_id","team_id","id") ON DELETE restrict ON UPDATE no action;--> statement-breakpoint
ALTER TABLE "vh_work_assignment" ADD CONSTRAINT "vh_work_assignment_fk_7" FOREIGN KEY ("assigned_by_user_id") REFERENCES "public"."users"("id") ON DELETE restrict ON UPDATE no action;--> statement-breakpoint
ALTER TABLE "vh_work_progress" ADD CONSTRAINT "vh_work_progress_fk_0" FOREIGN KEY ("tenant_id") REFERENCES "public"."platform_tenant"("id") ON DELETE restrict ON UPDATE no action;--> statement-breakpoint
ALTER TABLE "vh_work_progress" ADD CONSTRAINT "vh_work_progress_fk_1" FOREIGN KEY ("tenant_id","project_id") REFERENCES "public"."vh_project"("tenant_id","id") ON DELETE restrict ON UPDATE no action;--> statement-breakpoint
ALTER TABLE "vh_work_progress" ADD CONSTRAINT "vh_work_progress_fk_2" FOREIGN KEY ("tenant_id","project_id","incident_id") REFERENCES "public"."vh_incident"("tenant_id","project_id","id") ON DELETE restrict ON UPDATE no action;--> statement-breakpoint
ALTER TABLE "vh_work_progress" ADD CONSTRAINT "vh_work_progress_fk_3" FOREIGN KEY ("tenant_id","project_id","incident_id","task_id") REFERENCES "public"."vh_task"("tenant_id","project_id","incident_id","id") ON DELETE restrict ON UPDATE no action;--> statement-breakpoint
ALTER TABLE "vh_work_progress" ADD CONSTRAINT "vh_work_progress_fk_4" FOREIGN KEY ("tenant_id","project_id","incident_id","task_id","work_order_id") REFERENCES "public"."vh_work_order"("tenant_id","project_id","incident_id","task_id","id") ON DELETE restrict ON UPDATE no action;--> statement-breakpoint
ALTER TABLE "vh_work_progress" ADD CONSTRAINT "vh_work_progress_fk_5" FOREIGN KEY ("tenant_id","project_id","incident_id","task_id","work_order_id","assignment_id") REFERENCES "public"."vh_work_assignment"("tenant_id","project_id","incident_id","task_id","work_order_id","id") ON DELETE restrict ON UPDATE no action;--> statement-breakpoint
ALTER TABLE "vh_work_progress" ADD CONSTRAINT "vh_work_progress_fk_6" FOREIGN KEY ("tenant_id","project_id","business_event_id") REFERENCES "public"."vh_business_event"("tenant_id","project_id","id") ON DELETE restrict ON UPDATE no action;--> statement-breakpoint
ALTER TABLE "vh_work_progress" ADD CONSTRAINT "vh_work_progress_fk_7" FOREIGN KEY ("actor_user_id") REFERENCES "public"."users"("id") ON DELETE restrict ON UPDATE no action;--> statement-breakpoint
ALTER TABLE "vh_work_progress" ADD CONSTRAINT "vh_work_progress_fk_8" FOREIGN KEY ("estimated_by_user_id") REFERENCES "public"."users"("id") ON DELETE restrict ON UPDATE no action;--> statement-breakpoint
ALTER TABLE "vh_provider_event" ADD CONSTRAINT "vh_provider_event_fk_0" FOREIGN KEY ("tenant_id") REFERENCES "public"."platform_tenant"("id") ON DELETE restrict ON UPDATE no action;--> statement-breakpoint
ALTER TABLE "vh_notification_delivery" ADD CONSTRAINT "vh_notification_delivery_fk_0" FOREIGN KEY ("tenant_id") REFERENCES "public"."platform_tenant"("id") ON DELETE restrict ON UPDATE no action;--> statement-breakpoint
ALTER TABLE "vh_notification_delivery" ADD CONSTRAINT "vh_notification_delivery_fk_1" FOREIGN KEY ("tenant_id","project_id") REFERENCES "public"."vh_project"("tenant_id","id") ON DELETE restrict ON UPDATE no action;--> statement-breakpoint
ALTER TABLE "vh_notification_delivery" ADD CONSTRAINT "vh_notification_delivery_fk_2" FOREIGN KEY ("tenant_id","project_id","notification_id") REFERENCES "public"."vh_notification"("tenant_id","project_id","id") ON DELETE restrict ON UPDATE no action;--> statement-breakpoint
ALTER TABLE "vh_notification_delivery" ADD CONSTRAINT "vh_notification_delivery_fk_3" FOREIGN KEY ("tenant_id","project_id","report_update_id") REFERENCES "public"."vh_report_update"("tenant_id","project_id","id") ON DELETE restrict ON UPDATE no action;--> statement-breakpoint
ALTER TABLE "vh_report_update" ADD CONSTRAINT "vh_report_update_fk_0" FOREIGN KEY ("tenant_id") REFERENCES "public"."platform_tenant"("id") ON DELETE restrict ON UPDATE no action;--> statement-breakpoint
ALTER TABLE "vh_report_update" ADD CONSTRAINT "vh_report_update_fk_1" FOREIGN KEY ("tenant_id","project_id") REFERENCES "public"."vh_project"("tenant_id","id") ON DELETE restrict ON UPDATE no action;--> statement-breakpoint
ALTER TABLE "vh_report_update" ADD CONSTRAINT "vh_report_update_fk_2" FOREIGN KEY ("tenant_id","project_id","incident_id") REFERENCES "public"."vh_incident"("tenant_id","project_id","id") ON DELETE restrict ON UPDATE no action;--> statement-breakpoint
ALTER TABLE "vh_report_update" ADD CONSTRAINT "vh_report_update_fk_3" FOREIGN KEY ("tenant_id","project_id","report_id") REFERENCES "public"."vh_resident_report"("tenant_id","project_id","id") ON DELETE restrict ON UPDATE no action;--> statement-breakpoint
ALTER TABLE "vh_report_update" ADD CONSTRAINT "vh_report_update_fk_4" FOREIGN KEY ("recipient_user_id") REFERENCES "public"."users"("id") ON DELETE restrict ON UPDATE no action;--> statement-breakpoint
ALTER TABLE "vh_report_update" ADD CONSTRAINT "vh_report_update_fk_5" FOREIGN KEY ("tenant_id","project_id","business_event_id") REFERENCES "public"."vh_business_event"("tenant_id","project_id","id") ON DELETE restrict ON UPDATE no action;--> statement-breakpoint
ALTER TABLE "vh_report_update" ADD CONSTRAINT "vh_report_update_fk_6" FOREIGN KEY ("tenant_id","project_id","incident_id","work_progress_id") REFERENCES "public"."vh_work_progress"("tenant_id","project_id","incident_id","id") ON DELETE restrict ON UPDATE no action;--> statement-breakpoint
ALTER TABLE "vh_report_update" ADD CONSTRAINT "vh_report_update_fk_7" FOREIGN KEY ("tenant_id","incident_id","recipient_user_id","report_id") REFERENCES "public"."vh_resident_report"("tenant_id","incident_id","reporter_id","id") ON DELETE restrict ON UPDATE no action;--> statement-breakpoint
ALTER TABLE "vh_escalation" ADD CONSTRAINT "vh_escalation_fk_0" FOREIGN KEY ("tenant_id") REFERENCES "public"."platform_tenant"("id") ON DELETE restrict ON UPDATE no action;--> statement-breakpoint
ALTER TABLE "vh_escalation" ADD CONSTRAINT "vh_escalation_fk_1" FOREIGN KEY ("tenant_id","project_id") REFERENCES "public"."vh_project"("tenant_id","id") ON DELETE restrict ON UPDATE no action;--> statement-breakpoint
ALTER TABLE "vh_escalation" ADD CONSTRAINT "vh_escalation_fk_2" FOREIGN KEY ("tenant_id","project_id","incident_id") REFERENCES "public"."vh_incident"("tenant_id","project_id","id") ON DELETE restrict ON UPDATE no action;--> statement-breakpoint
ALTER TABLE "vh_escalation" ADD CONSTRAINT "vh_escalation_fk_3" FOREIGN KEY ("tenant_id","project_id","incident_id","incident_sla_id") REFERENCES "public"."vh_incident_sla"("tenant_id","project_id","incident_id","id") ON DELETE restrict ON UPDATE no action;--> statement-breakpoint
ALTER TABLE "vh_escalation" ADD CONSTRAINT "vh_escalation_fk_4" FOREIGN KEY ("tenant_id","project_id","assigned_team_id") REFERENCES "public"."vh_team"("tenant_id","project_id","id") ON DELETE restrict ON UPDATE no action;--> statement-breakpoint
ALTER TABLE "vh_escalation" ADD CONSTRAINT "vh_escalation_fk_5" FOREIGN KEY ("acknowledged_by_user_id") REFERENCES "public"."users"("id") ON DELETE restrict ON UPDATE no action;--> statement-breakpoint
ALTER TABLE "vh_incident_sla" ADD CONSTRAINT "vh_incident_sla_fk_0" FOREIGN KEY ("tenant_id") REFERENCES "public"."platform_tenant"("id") ON DELETE restrict ON UPDATE no action;--> statement-breakpoint
ALTER TABLE "vh_incident_sla" ADD CONSTRAINT "vh_incident_sla_fk_1" FOREIGN KEY ("tenant_id","project_id") REFERENCES "public"."vh_project"("tenant_id","id") ON DELETE restrict ON UPDATE no action;--> statement-breakpoint
ALTER TABLE "vh_incident_sla" ADD CONSTRAINT "vh_incident_sla_fk_2" FOREIGN KEY ("tenant_id","project_id","incident_id") REFERENCES "public"."vh_incident"("tenant_id","project_id","id") ON DELETE restrict ON UPDATE no action;--> statement-breakpoint
ALTER TABLE "vh_incident_sla" ADD CONSTRAINT "vh_incident_sla_fk_3" FOREIGN KEY ("tenant_id","project_id","policy_id") REFERENCES "public"."vh_sla_policy"("tenant_id","project_id","id") ON DELETE restrict ON UPDATE no action;--> statement-breakpoint
ALTER TABLE "vh_sla_policy" ADD CONSTRAINT "vh_sla_policy_fk_0" FOREIGN KEY ("tenant_id") REFERENCES "public"."platform_tenant"("id") ON DELETE restrict ON UPDATE no action;--> statement-breakpoint
ALTER TABLE "vh_sla_policy" ADD CONSTRAINT "vh_sla_policy_fk_1" FOREIGN KEY ("tenant_id","project_id") REFERENCES "public"."vh_project"("tenant_id","id") ON DELETE restrict ON UPDATE no action;--> statement-breakpoint
ALTER TABLE "vh_staff_shift" ADD CONSTRAINT "vh_staff_shift_fk_0" FOREIGN KEY ("tenant_id") REFERENCES "public"."platform_tenant"("id") ON DELETE restrict ON UPDATE no action;--> statement-breakpoint
ALTER TABLE "vh_staff_shift" ADD CONSTRAINT "vh_staff_shift_fk_1" FOREIGN KEY ("tenant_id","project_id") REFERENCES "public"."vh_project"("tenant_id","id") ON DELETE restrict ON UPDATE no action;--> statement-breakpoint
ALTER TABLE "vh_staff_shift" ADD CONSTRAINT "vh_staff_shift_fk_2" FOREIGN KEY ("tenant_id","project_id","team_member_id") REFERENCES "public"."vh_team_member"("tenant_id","project_id","id") ON DELETE restrict ON UPDATE no action;--> statement-breakpoint
ALTER TABLE "vh_staff_skill" ADD CONSTRAINT "vh_staff_skill_fk_0" FOREIGN KEY ("tenant_id") REFERENCES "public"."platform_tenant"("id") ON DELETE restrict ON UPDATE no action;--> statement-breakpoint
ALTER TABLE "vh_staff_skill" ADD CONSTRAINT "vh_staff_skill_fk_1" FOREIGN KEY ("tenant_id","project_id") REFERENCES "public"."vh_project"("tenant_id","id") ON DELETE restrict ON UPDATE no action;--> statement-breakpoint
ALTER TABLE "vh_staff_skill" ADD CONSTRAINT "vh_staff_skill_fk_2" FOREIGN KEY ("tenant_id","project_id","property_membership_id") REFERENCES "public"."vh_property_membership"("tenant_id","project_id","id") ON DELETE restrict ON UPDATE no action;--> statement-breakpoint
ALTER TABLE "vh_staff_skill" ADD CONSTRAINT "vh_staff_skill_fk_3" FOREIGN KEY ("verified_by_user_id") REFERENCES "public"."users"("id") ON DELETE restrict ON UPDATE no action;--> statement-breakpoint
ALTER TABLE "vh_team" ADD CONSTRAINT "vh_team_fk_0" FOREIGN KEY ("tenant_id") REFERENCES "public"."platform_tenant"("id") ON DELETE restrict ON UPDATE no action;--> statement-breakpoint
ALTER TABLE "vh_team" ADD CONSTRAINT "vh_team_fk_1" FOREIGN KEY ("tenant_id","project_id") REFERENCES "public"."vh_project"("tenant_id","id") ON DELETE restrict ON UPDATE no action;--> statement-breakpoint
ALTER TABLE "vh_team_member" ADD CONSTRAINT "vh_team_member_fk_0" FOREIGN KEY ("tenant_id") REFERENCES "public"."platform_tenant"("id") ON DELETE restrict ON UPDATE no action;--> statement-breakpoint
ALTER TABLE "vh_team_member" ADD CONSTRAINT "vh_team_member_fk_1" FOREIGN KEY ("tenant_id","project_id") REFERENCES "public"."vh_project"("tenant_id","id") ON DELETE restrict ON UPDATE no action;--> statement-breakpoint
ALTER TABLE "vh_team_member" ADD CONSTRAINT "vh_team_member_fk_2" FOREIGN KEY ("tenant_id","project_id","team_id") REFERENCES "public"."vh_team"("tenant_id","project_id","id") ON DELETE restrict ON UPDATE no action;--> statement-breakpoint
ALTER TABLE "vh_team_member" ADD CONSTRAINT "vh_team_member_fk_3" FOREIGN KEY ("tenant_id","project_id","property_membership_id") REFERENCES "public"."vh_property_membership"("tenant_id","project_id","id") ON DELETE restrict ON UPDATE no action;--> statement-breakpoint
ALTER TABLE "platform_handoff" ADD CONSTRAINT "platform_handoff_fk_0" FOREIGN KEY ("tenant_id") REFERENCES "public"."platform_tenant"("id") ON DELETE restrict ON UPDATE no action;--> statement-breakpoint
ALTER TABLE "platform_handoff" ADD CONSTRAINT "platform_handoff_fk_1" FOREIGN KEY ("tenant_id","source_conversation_id") REFERENCES "public"."platform_conversation"("tenant_id","id") ON DELETE restrict ON UPDATE no action;--> statement-breakpoint
ALTER TABLE "platform_handoff" ADD CONSTRAINT "platform_handoff_fk_2" FOREIGN KEY ("tenant_id","source_workflow_session_id") REFERENCES "public"."platform_workflow_session"("tenant_id","id") ON DELETE restrict ON UPDATE no action;--> statement-breakpoint
ALTER TABLE "platform_handoff" ADD CONSTRAINT "platform_handoff_fk_3" FOREIGN KEY ("tenant_id","target_agent_version_id") REFERENCES "public"."platform_agent_version"("tenant_id","id") ON DELETE restrict ON UPDATE no action;--> statement-breakpoint
ALTER TABLE "platform_handoff" ADD CONSTRAINT "platform_handoff_fk_4" FOREIGN KEY ("tenant_id","target_workflow_session_id") REFERENCES "public"."platform_workflow_session"("tenant_id","id") ON DELETE restrict ON UPDATE no action;--> statement-breakpoint
ALTER TABLE "platform_runtime_checkpoint" ADD CONSTRAINT "platform_runtime_checkpoint_fk_0" FOREIGN KEY ("tenant_id") REFERENCES "public"."platform_tenant"("id") ON DELETE restrict ON UPDATE no action;--> statement-breakpoint
ALTER TABLE "platform_runtime_checkpoint" ADD CONSTRAINT "platform_runtime_checkpoint_fk_1" FOREIGN KEY ("tenant_id","workflow_session_id") REFERENCES "public"."platform_workflow_session"("tenant_id","id") ON DELETE restrict ON UPDATE no action;--> statement-breakpoint
ALTER TABLE "platform_runtime_checkpoint" ADD CONSTRAINT "platform_runtime_checkpoint_fk_2" FOREIGN KEY ("tenant_id","workflow_session_id","created_by_run_id") REFERENCES "public"."platform_agent_run"("tenant_id","workflow_session_id","id") ON DELETE restrict ON UPDATE no action;--> statement-breakpoint
ALTER TABLE "platform_runtime_message" ADD CONSTRAINT "platform_runtime_message_fk_0" FOREIGN KEY ("tenant_id") REFERENCES "public"."platform_tenant"("id") ON DELETE restrict ON UPDATE no action;--> statement-breakpoint
ALTER TABLE "platform_runtime_message" ADD CONSTRAINT "platform_runtime_message_fk_1" FOREIGN KEY ("tenant_id","workflow_session_id") REFERENCES "public"."platform_workflow_session"("tenant_id","id") ON DELETE restrict ON UPDATE no action;--> statement-breakpoint
ALTER TABLE "platform_runtime_message" ADD CONSTRAINT "platform_runtime_message_fk_2" FOREIGN KEY ("tenant_id","workflow_session_id","sender_participant_id") REFERENCES "public"."platform_session_participant"("tenant_id","workflow_session_id","id") ON DELETE restrict ON UPDATE no action;--> statement-breakpoint
ALTER TABLE "platform_runtime_message" ADD CONSTRAINT "platform_runtime_message_fk_3" FOREIGN KEY ("tenant_id","workflow_session_id","recipient_participant_id") REFERENCES "public"."platform_session_participant"("tenant_id","workflow_session_id","id") ON DELETE restrict ON UPDATE no action;--> statement-breakpoint
ALTER TABLE "platform_runtime_message" ADD CONSTRAINT "platform_runtime_message_fk_4" FOREIGN KEY ("tenant_id","workflow_session_id","agent_run_id") REFERENCES "public"."platform_agent_run"("tenant_id","workflow_session_id","id") ON DELETE restrict ON UPDATE no action;--> statement-breakpoint
ALTER TABLE "platform_runtime_message" ADD CONSTRAINT "platform_runtime_message_fk_5" FOREIGN KEY ("tenant_id","workflow_session_id","reply_to_message_id") REFERENCES "public"."platform_runtime_message"("tenant_id","workflow_session_id","id") ON DELETE restrict ON UPDATE no action;--> statement-breakpoint
ALTER TABLE "platform_session_control" ADD CONSTRAINT "platform_session_control_fk_0" FOREIGN KEY ("tenant_id") REFERENCES "public"."platform_tenant"("id") ON DELETE restrict ON UPDATE no action;--> statement-breakpoint
ALTER TABLE "platform_session_control" ADD CONSTRAINT "platform_session_control_fk_1" FOREIGN KEY ("tenant_id","workflow_session_id") REFERENCES "public"."platform_workflow_session"("tenant_id","id") ON DELETE restrict ON UPDATE no action;--> statement-breakpoint
ALTER TABLE "platform_session_control" ADD CONSTRAINT "platform_session_control_fk_2" FOREIGN KEY ("tenant_id","parent_workflow_session_id") REFERENCES "public"."platform_workflow_session"("tenant_id","id") ON DELETE restrict ON UPDATE no action;--> statement-breakpoint
ALTER TABLE "platform_session_control" ADD CONSTRAINT "platform_session_control_fk_3" FOREIGN KEY ("tenant_id","workflow_session_id","coordinator_participant_id") REFERENCES "public"."platform_session_participant"("tenant_id","workflow_session_id","id") ON DELETE restrict ON UPDATE no action;--> statement-breakpoint
ALTER TABLE "platform_session_participant" ADD CONSTRAINT "platform_session_participant_fk_0" FOREIGN KEY ("tenant_id") REFERENCES "public"."platform_tenant"("id") ON DELETE restrict ON UPDATE no action;--> statement-breakpoint
ALTER TABLE "platform_session_participant" ADD CONSTRAINT "platform_session_participant_fk_1" FOREIGN KEY ("tenant_id","workflow_session_id") REFERENCES "public"."platform_workflow_session"("tenant_id","id") ON DELETE restrict ON UPDATE no action;--> statement-breakpoint
ALTER TABLE "platform_session_participant" ADD CONSTRAINT "platform_session_participant_fk_2" FOREIGN KEY ("tenant_id","agent_version_id") REFERENCES "public"."platform_agent_version"("tenant_id","id") ON DELETE restrict ON UPDATE no action;--> statement-breakpoint
ALTER TABLE "platform_session_wait" ADD CONSTRAINT "platform_session_wait_fk_0" FOREIGN KEY ("tenant_id") REFERENCES "public"."platform_tenant"("id") ON DELETE restrict ON UPDATE no action;--> statement-breakpoint
ALTER TABLE "platform_session_wait" ADD CONSTRAINT "platform_session_wait_fk_1" FOREIGN KEY ("tenant_id","workflow_session_id") REFERENCES "public"."platform_workflow_session"("tenant_id","id") ON DELETE restrict ON UPDATE no action;--> statement-breakpoint
ALTER TABLE "platform_session_wait" ADD CONSTRAINT "platform_session_wait_fk_2" FOREIGN KEY ("tenant_id","workflow_session_id","run_step_id") REFERENCES "public"."platform_run_step"("tenant_id","workflow_session_id","id") ON DELETE restrict ON UPDATE no action;--> statement-breakpoint
ALTER TABLE "platform_session_wait" ADD CONSTRAINT "platform_session_wait_fk_3" FOREIGN KEY ("tenant_id","workflow_session_id","participant_id") REFERENCES "public"."platform_session_participant"("tenant_id","workflow_session_id","id") ON DELETE restrict ON UPDATE no action;--> statement-breakpoint
ALTER TABLE "platform_conversation" ADD CONSTRAINT "platform_conversation_fk_0" FOREIGN KEY ("tenant_id") REFERENCES "public"."platform_tenant"("id") ON DELETE restrict ON UPDATE no action;--> statement-breakpoint
ALTER TABLE "platform_conversation" ADD CONSTRAINT "platform_conversation_fk_1" FOREIGN KEY ("owner_user_id") REFERENCES "public"."users"("id") ON DELETE restrict ON UPDATE no action;--> statement-breakpoint
ALTER TABLE "platform_conversation_message" ADD CONSTRAINT "platform_conversation_message_fk_0" FOREIGN KEY ("tenant_id") REFERENCES "public"."platform_tenant"("id") ON DELETE restrict ON UPDATE no action;--> statement-breakpoint
ALTER TABLE "platform_conversation_message" ADD CONSTRAINT "platform_conversation_message_fk_1" FOREIGN KEY ("tenant_id","conversation_id") REFERENCES "public"."platform_conversation"("tenant_id","id") ON DELETE restrict ON UPDATE no action;--> statement-breakpoint
ALTER TABLE "platform_conversation_message" ADD CONSTRAINT "platform_conversation_message_fk_2" FOREIGN KEY ("author_user_id") REFERENCES "public"."users"("id") ON DELETE restrict ON UPDATE no action;--> statement-breakpoint
ALTER TABLE "platform_conversation_message" ADD CONSTRAINT "platform_conversation_message_fk_3" FOREIGN KEY ("tenant_id","agent_version_id") REFERENCES "public"."platform_agent_version"("tenant_id","id") ON DELETE restrict ON UPDATE no action;--> statement-breakpoint
ALTER TABLE "platform_conversation_message" ADD CONSTRAINT "platform_conversation_message_fk_4" FOREIGN KEY ("tenant_id","conversation_id","reply_to_message_id") REFERENCES "public"."platform_conversation_message"("tenant_id","conversation_id","id") ON DELETE restrict ON UPDATE no action;--> statement-breakpoint
ALTER TABLE "platform_conversation_subject" ADD CONSTRAINT "platform_conversation_subject_fk_0" FOREIGN KEY ("tenant_id") REFERENCES "public"."platform_tenant"("id") ON DELETE restrict ON UPDATE no action;--> statement-breakpoint
ALTER TABLE "platform_conversation_subject" ADD CONSTRAINT "platform_conversation_subject_fk_1" FOREIGN KEY ("tenant_id","conversation_id") REFERENCES "public"."platform_conversation"("tenant_id","id") ON DELETE restrict ON UPDATE no action;--> statement-breakpoint
ALTER TABLE "platform_event_receipt" ADD CONSTRAINT "platform_event_receipt_fk_0" FOREIGN KEY ("tenant_id") REFERENCES "public"."platform_tenant"("id") ON DELETE restrict ON UPDATE no action;--> statement-breakpoint
CREATE INDEX "vh_asset_ix_1" ON "vh_asset" USING btree ("tenant_id","project_id");--> statement-breakpoint
CREATE INDEX "vh_asset_ix_2" ON "vh_asset" USING btree ("tenant_id","project_id","apartment_id");--> statement-breakpoint
CREATE INDEX "vh_asset_ix_3" ON "vh_asset" USING btree ("tenant_id","project_id","tower_id");--> statement-breakpoint
CREATE INDEX "vh_incident_asset_ix_1" ON "vh_incident_asset" USING btree ("tenant_id","project_id");--> statement-breakpoint
CREATE INDEX "vh_incident_asset_ix_2" ON "vh_incident_asset" USING btree ("tenant_id","project_id","asset_id");--> statement-breakpoint
CREATE INDEX "vh_incident_asset_ix_3" ON "vh_incident_asset" USING btree ("tenant_id","project_id","incident_id");--> statement-breakpoint
CREATE INDEX "vh_work_appointment_ix_0" ON "vh_work_appointment" USING btree ("confirmed_by_user_id");--> statement-breakpoint
CREATE INDEX "vh_work_appointment_ix_1" ON "vh_work_appointment" USING btree ("requested_by_user_id");--> statement-breakpoint
CREATE INDEX "vh_work_appointment_ix_3" ON "vh_work_appointment" USING btree ("tenant_id","project_id");--> statement-breakpoint
CREATE INDEX "vh_work_appointment_ix_4" ON "vh_work_appointment" USING btree ("tenant_id","project_id","incident_id");--> statement-breakpoint
CREATE INDEX "vh_work_appointment_ix_5" ON "vh_work_appointment" USING btree ("tenant_id","project_id","incident_id","task_id");--> statement-breakpoint
CREATE INDEX "vh_work_appointment_ix_6" ON "vh_work_appointment" USING btree ("tenant_id","project_id","incident_id","task_id","work_order_id");--> statement-breakpoint
CREATE INDEX "vh_work_appointment_ix_7" ON "vh_work_appointment" USING btree ("tenant_id","project_id","resident_report_id");--> statement-breakpoint
CREATE INDEX "vh_work_assignment_ix_0" ON "vh_work_assignment" USING btree ("assigned_by_user_id");--> statement-breakpoint
CREATE INDEX "vh_work_assignment_ix_2" ON "vh_work_assignment" USING btree ("tenant_id","project_id");--> statement-breakpoint
CREATE INDEX "vh_work_assignment_ix_3" ON "vh_work_assignment" USING btree ("tenant_id","project_id","incident_id");--> statement-breakpoint
CREATE INDEX "vh_work_assignment_ix_4" ON "vh_work_assignment" USING btree ("tenant_id","project_id","incident_id","task_id");--> statement-breakpoint
CREATE INDEX "vh_work_assignment_ix_5" ON "vh_work_assignment" USING btree ("tenant_id","project_id","incident_id","task_id","work_order_id");--> statement-breakpoint
CREATE INDEX "vh_work_assignment_ix_6" ON "vh_work_assignment" USING btree ("tenant_id","project_id","team_id");--> statement-breakpoint
CREATE INDEX "vh_work_assignment_ix_7" ON "vh_work_assignment" USING btree ("tenant_id","project_id","team_id","team_member_id");--> statement-breakpoint
CREATE UNIQUE INDEX "vh_work_assignment_live_0" ON "vh_work_assignment" USING btree ("tenant_id","work_order_id") WHERE status IN ('OFFERED','ACCEPTED');--> statement-breakpoint
CREATE INDEX "vh_work_progress_ix_0" ON "vh_work_progress" USING btree ("actor_user_id");--> statement-breakpoint
CREATE INDEX "vh_work_progress_ix_1" ON "vh_work_progress" USING btree ("estimated_by_user_id");--> statement-breakpoint
CREATE INDEX "vh_work_progress_ix_3" ON "vh_work_progress" USING btree ("tenant_id","project_id");--> statement-breakpoint
CREATE INDEX "vh_work_progress_ix_4" ON "vh_work_progress" USING btree ("tenant_id","project_id","business_event_id");--> statement-breakpoint
CREATE INDEX "vh_work_progress_ix_5" ON "vh_work_progress" USING btree ("tenant_id","project_id","incident_id");--> statement-breakpoint
CREATE INDEX "vh_work_progress_ix_6" ON "vh_work_progress" USING btree ("tenant_id","project_id","incident_id","task_id");--> statement-breakpoint
CREATE INDEX "vh_work_progress_ix_7" ON "vh_work_progress" USING btree ("tenant_id","project_id","incident_id","task_id","work_order_id");--> statement-breakpoint
CREATE INDEX "vh_work_progress_ix_8" ON "vh_work_progress" USING btree ("tenant_id","project_id","incident_id","task_id","work_order_id","assignment_id");--> statement-breakpoint
CREATE INDEX "vh_notification_delivery_ix_1" ON "vh_notification_delivery" USING btree ("tenant_id","project_id");--> statement-breakpoint
CREATE INDEX "vh_notification_delivery_ix_2" ON "vh_notification_delivery" USING btree ("tenant_id","project_id","notification_id");--> statement-breakpoint
CREATE INDEX "vh_notification_delivery_ix_3" ON "vh_notification_delivery" USING btree ("tenant_id","project_id","report_update_id");--> statement-breakpoint
CREATE INDEX "vh_report_update_ix_0" ON "vh_report_update" USING btree ("recipient_user_id");--> statement-breakpoint
CREATE INDEX "vh_report_update_ix_2" ON "vh_report_update" USING btree ("tenant_id","incident_id","recipient_user_id","report_id");--> statement-breakpoint
CREATE INDEX "vh_report_update_ix_3" ON "vh_report_update" USING btree ("tenant_id","project_id");--> statement-breakpoint
CREATE INDEX "vh_report_update_ix_4" ON "vh_report_update" USING btree ("tenant_id","project_id","business_event_id");--> statement-breakpoint
CREATE INDEX "vh_report_update_ix_5" ON "vh_report_update" USING btree ("tenant_id","project_id","incident_id");--> statement-breakpoint
CREATE INDEX "vh_report_update_ix_6" ON "vh_report_update" USING btree ("tenant_id","project_id","incident_id","work_progress_id");--> statement-breakpoint
CREATE INDEX "vh_report_update_ix_7" ON "vh_report_update" USING btree ("tenant_id","project_id","report_id");--> statement-breakpoint
CREATE INDEX "vh_escalation_ix_0" ON "vh_escalation" USING btree ("acknowledged_by_user_id");--> statement-breakpoint
CREATE INDEX "vh_escalation_ix_2" ON "vh_escalation" USING btree ("tenant_id","project_id");--> statement-breakpoint
CREATE INDEX "vh_escalation_ix_3" ON "vh_escalation" USING btree ("tenant_id","project_id","assigned_team_id");--> statement-breakpoint
CREATE INDEX "vh_escalation_ix_4" ON "vh_escalation" USING btree ("tenant_id","project_id","incident_id");--> statement-breakpoint
CREATE INDEX "vh_escalation_ix_5" ON "vh_escalation" USING btree ("tenant_id","project_id","incident_id","incident_sla_id");--> statement-breakpoint
CREATE INDEX "vh_incident_sla_ix_1" ON "vh_incident_sla" USING btree ("tenant_id","project_id");--> statement-breakpoint
CREATE INDEX "vh_incident_sla_ix_2" ON "vh_incident_sla" USING btree ("tenant_id","project_id","incident_id");--> statement-breakpoint
CREATE INDEX "vh_incident_sla_ix_3" ON "vh_incident_sla" USING btree ("tenant_id","project_id","policy_id");--> statement-breakpoint
CREATE INDEX "vh_sla_policy_ix_1" ON "vh_sla_policy" USING btree ("tenant_id","project_id");--> statement-breakpoint
CREATE INDEX "vh_staff_shift_ix_1" ON "vh_staff_shift" USING btree ("tenant_id","project_id");--> statement-breakpoint
CREATE INDEX "vh_staff_shift_ix_2" ON "vh_staff_shift" USING btree ("tenant_id","project_id","team_member_id");--> statement-breakpoint
CREATE INDEX "vh_staff_skill_ix_1" ON "vh_staff_skill" USING btree ("tenant_id","project_id");--> statement-breakpoint
CREATE INDEX "vh_staff_skill_ix_2" ON "vh_staff_skill" USING btree ("tenant_id","project_id","property_membership_id");--> statement-breakpoint
CREATE INDEX "vh_staff_skill_ix_3" ON "vh_staff_skill" USING btree ("verified_by_user_id");--> statement-breakpoint
CREATE INDEX "vh_team_ix_1" ON "vh_team" USING btree ("tenant_id","project_id");--> statement-breakpoint
CREATE INDEX "vh_team_member_ix_1" ON "vh_team_member" USING btree ("tenant_id","project_id");--> statement-breakpoint
CREATE INDEX "vh_team_member_ix_2" ON "vh_team_member" USING btree ("tenant_id","project_id","property_membership_id");--> statement-breakpoint
CREATE INDEX "vh_team_member_ix_3" ON "vh_team_member" USING btree ("tenant_id","project_id","team_id");--> statement-breakpoint
CREATE INDEX "platform_handoff_ix_1" ON "platform_handoff" USING btree ("tenant_id","source_conversation_id");--> statement-breakpoint
CREATE INDEX "platform_handoff_ix_2" ON "platform_handoff" USING btree ("tenant_id","source_workflow_session_id");--> statement-breakpoint
CREATE INDEX "platform_handoff_ix_3" ON "platform_handoff" USING btree ("tenant_id","target_agent_version_id");--> statement-breakpoint
CREATE INDEX "platform_handoff_ix_4" ON "platform_handoff" USING btree ("tenant_id","target_workflow_session_id");--> statement-breakpoint
CREATE INDEX "platform_runtime_checkpoint_ix_1" ON "platform_runtime_checkpoint" USING btree ("tenant_id","workflow_session_id");--> statement-breakpoint
CREATE INDEX "platform_runtime_checkpoint_ix_2" ON "platform_runtime_checkpoint" USING btree ("tenant_id","workflow_session_id","created_by_run_id");--> statement-breakpoint
CREATE INDEX "platform_runtime_message_ix_1" ON "platform_runtime_message" USING btree ("tenant_id","workflow_session_id");--> statement-breakpoint
CREATE INDEX "platform_runtime_message_ix_2" ON "platform_runtime_message" USING btree ("tenant_id","workflow_session_id","agent_run_id");--> statement-breakpoint
CREATE INDEX "platform_runtime_message_ix_3" ON "platform_runtime_message" USING btree ("tenant_id","workflow_session_id","recipient_participant_id");--> statement-breakpoint
CREATE INDEX "platform_runtime_message_ix_4" ON "platform_runtime_message" USING btree ("tenant_id","workflow_session_id","reply_to_message_id");--> statement-breakpoint
CREATE INDEX "platform_runtime_message_ix_5" ON "platform_runtime_message" USING btree ("tenant_id","workflow_session_id","sender_participant_id");--> statement-breakpoint
CREATE INDEX "platform_session_control_ix_1" ON "platform_session_control" USING btree ("tenant_id","parent_workflow_session_id");--> statement-breakpoint
CREATE INDEX "platform_session_control_ix_2" ON "platform_session_control" USING btree ("tenant_id","workflow_session_id");--> statement-breakpoint
CREATE INDEX "platform_session_control_ix_3" ON "platform_session_control" USING btree ("tenant_id","workflow_session_id","coordinator_participant_id");--> statement-breakpoint
CREATE INDEX "platform_session_participant_ix_1" ON "platform_session_participant" USING btree ("tenant_id","agent_version_id");--> statement-breakpoint
CREATE INDEX "platform_session_participant_ix_2" ON "platform_session_participant" USING btree ("tenant_id","workflow_session_id");--> statement-breakpoint
CREATE UNIQUE INDEX "platform_session_participant_live_0" ON "platform_session_participant" USING btree ("tenant_id","workflow_session_id") WHERE role='COORDINATOR' AND status IN ('INVITED','ACTIVE');--> statement-breakpoint
CREATE INDEX "platform_session_wait_ix_1" ON "platform_session_wait" USING btree ("tenant_id","workflow_session_id");--> statement-breakpoint
CREATE INDEX "platform_session_wait_ix_2" ON "platform_session_wait" USING btree ("tenant_id","workflow_session_id","participant_id");--> statement-breakpoint
CREATE INDEX "platform_session_wait_ix_3" ON "platform_session_wait" USING btree ("tenant_id","workflow_session_id","run_step_id");--> statement-breakpoint
CREATE INDEX "platform_conversation_ix_0" ON "platform_conversation" USING btree ("owner_user_id");--> statement-breakpoint
CREATE INDEX "platform_conversation_message_ix_0" ON "platform_conversation_message" USING btree ("author_user_id");--> statement-breakpoint
CREATE INDEX "platform_conversation_message_ix_2" ON "platform_conversation_message" USING btree ("tenant_id","agent_version_id");--> statement-breakpoint
CREATE INDEX "platform_conversation_message_ix_3" ON "platform_conversation_message" USING btree ("tenant_id","conversation_id");--> statement-breakpoint
CREATE INDEX "platform_conversation_message_ix_4" ON "platform_conversation_message" USING btree ("tenant_id","conversation_id","reply_to_message_id");--> statement-breakpoint
CREATE INDEX "platform_conversation_subject_ix_1" ON "platform_conversation_subject" USING btree ("tenant_id","conversation_id");--> statement-breakpoint
CREATE POLICY "vh_asset_tenant_policy" ON "vh_asset" AS PERMISSIVE FOR ALL TO public USING ("vh_asset"."tenant_id" = nullif(current_setting('app.tenant_id', true), '')::uuid) WITH CHECK ("vh_asset"."tenant_id" = nullif(current_setting('app.tenant_id', true), '')::uuid);--> statement-breakpoint
CREATE POLICY "vh_incident_asset_tenant_policy" ON "vh_incident_asset" AS PERMISSIVE FOR ALL TO public USING ("vh_incident_asset"."tenant_id" = nullif(current_setting('app.tenant_id', true), '')::uuid) WITH CHECK ("vh_incident_asset"."tenant_id" = nullif(current_setting('app.tenant_id', true), '')::uuid);--> statement-breakpoint
CREATE POLICY "vh_work_appointment_tenant_policy" ON "vh_work_appointment" AS PERMISSIVE FOR ALL TO public USING ("vh_work_appointment"."tenant_id" = nullif(current_setting('app.tenant_id', true), '')::uuid) WITH CHECK ("vh_work_appointment"."tenant_id" = nullif(current_setting('app.tenant_id', true), '')::uuid);--> statement-breakpoint
CREATE POLICY "vh_work_assignment_tenant_policy" ON "vh_work_assignment" AS PERMISSIVE FOR ALL TO public USING ("vh_work_assignment"."tenant_id" = nullif(current_setting('app.tenant_id', true), '')::uuid) WITH CHECK ("vh_work_assignment"."tenant_id" = nullif(current_setting('app.tenant_id', true), '')::uuid);--> statement-breakpoint
CREATE POLICY "vh_work_progress_tenant_policy" ON "vh_work_progress" AS PERMISSIVE FOR ALL TO public USING ("vh_work_progress"."tenant_id" = nullif(current_setting('app.tenant_id', true), '')::uuid) WITH CHECK ("vh_work_progress"."tenant_id" = nullif(current_setting('app.tenant_id', true), '')::uuid);--> statement-breakpoint
CREATE POLICY "vh_provider_event_tenant_policy" ON "vh_provider_event" AS PERMISSIVE FOR ALL TO public USING ("vh_provider_event"."tenant_id" = nullif(current_setting('app.tenant_id', true), '')::uuid) WITH CHECK ("vh_provider_event"."tenant_id" = nullif(current_setting('app.tenant_id', true), '')::uuid);--> statement-breakpoint
CREATE POLICY "vh_notification_delivery_tenant_policy" ON "vh_notification_delivery" AS PERMISSIVE FOR ALL TO public USING ("vh_notification_delivery"."tenant_id" = nullif(current_setting('app.tenant_id', true), '')::uuid) WITH CHECK ("vh_notification_delivery"."tenant_id" = nullif(current_setting('app.tenant_id', true), '')::uuid);--> statement-breakpoint
CREATE POLICY "vh_report_update_tenant_policy" ON "vh_report_update" AS PERMISSIVE FOR ALL TO public USING ("vh_report_update"."tenant_id" = nullif(current_setting('app.tenant_id', true), '')::uuid) WITH CHECK ("vh_report_update"."tenant_id" = nullif(current_setting('app.tenant_id', true), '')::uuid);--> statement-breakpoint
CREATE POLICY "vh_escalation_tenant_policy" ON "vh_escalation" AS PERMISSIVE FOR ALL TO public USING ("vh_escalation"."tenant_id" = nullif(current_setting('app.tenant_id', true), '')::uuid) WITH CHECK ("vh_escalation"."tenant_id" = nullif(current_setting('app.tenant_id', true), '')::uuid);--> statement-breakpoint
CREATE POLICY "vh_incident_sla_tenant_policy" ON "vh_incident_sla" AS PERMISSIVE FOR ALL TO public USING ("vh_incident_sla"."tenant_id" = nullif(current_setting('app.tenant_id', true), '')::uuid) WITH CHECK ("vh_incident_sla"."tenant_id" = nullif(current_setting('app.tenant_id', true), '')::uuid);--> statement-breakpoint
CREATE POLICY "vh_sla_policy_tenant_policy" ON "vh_sla_policy" AS PERMISSIVE FOR ALL TO public USING ("vh_sla_policy"."tenant_id" = nullif(current_setting('app.tenant_id', true), '')::uuid) WITH CHECK ("vh_sla_policy"."tenant_id" = nullif(current_setting('app.tenant_id', true), '')::uuid);--> statement-breakpoint
CREATE POLICY "vh_staff_shift_tenant_policy" ON "vh_staff_shift" AS PERMISSIVE FOR ALL TO public USING ("vh_staff_shift"."tenant_id" = nullif(current_setting('app.tenant_id', true), '')::uuid) WITH CHECK ("vh_staff_shift"."tenant_id" = nullif(current_setting('app.tenant_id', true), '')::uuid);--> statement-breakpoint
CREATE POLICY "vh_staff_skill_tenant_policy" ON "vh_staff_skill" AS PERMISSIVE FOR ALL TO public USING ("vh_staff_skill"."tenant_id" = nullif(current_setting('app.tenant_id', true), '')::uuid) WITH CHECK ("vh_staff_skill"."tenant_id" = nullif(current_setting('app.tenant_id', true), '')::uuid);--> statement-breakpoint
CREATE POLICY "vh_team_tenant_policy" ON "vh_team" AS PERMISSIVE FOR ALL TO public USING ("vh_team"."tenant_id" = nullif(current_setting('app.tenant_id', true), '')::uuid) WITH CHECK ("vh_team"."tenant_id" = nullif(current_setting('app.tenant_id', true), '')::uuid);--> statement-breakpoint
CREATE POLICY "vh_team_member_tenant_policy" ON "vh_team_member" AS PERMISSIVE FOR ALL TO public USING ("vh_team_member"."tenant_id" = nullif(current_setting('app.tenant_id', true), '')::uuid) WITH CHECK ("vh_team_member"."tenant_id" = nullif(current_setting('app.tenant_id', true), '')::uuid);--> statement-breakpoint
CREATE POLICY "platform_handoff_tenant_policy" ON "platform_handoff" AS PERMISSIVE FOR ALL TO public USING ("platform_handoff"."tenant_id" = nullif(current_setting('app.tenant_id', true), '')::uuid) WITH CHECK ("platform_handoff"."tenant_id" = nullif(current_setting('app.tenant_id', true), '')::uuid);--> statement-breakpoint
CREATE POLICY "platform_runtime_checkpoint_tenant_policy" ON "platform_runtime_checkpoint" AS PERMISSIVE FOR ALL TO public USING ("platform_runtime_checkpoint"."tenant_id" = nullif(current_setting('app.tenant_id', true), '')::uuid) WITH CHECK ("platform_runtime_checkpoint"."tenant_id" = nullif(current_setting('app.tenant_id', true), '')::uuid);--> statement-breakpoint
CREATE POLICY "platform_runtime_message_tenant_policy" ON "platform_runtime_message" AS PERMISSIVE FOR ALL TO public USING ("platform_runtime_message"."tenant_id" = nullif(current_setting('app.tenant_id', true), '')::uuid) WITH CHECK ("platform_runtime_message"."tenant_id" = nullif(current_setting('app.tenant_id', true), '')::uuid);--> statement-breakpoint
CREATE POLICY "platform_session_control_tenant_policy" ON "platform_session_control" AS PERMISSIVE FOR ALL TO public USING ("platform_session_control"."tenant_id" = nullif(current_setting('app.tenant_id', true), '')::uuid) WITH CHECK ("platform_session_control"."tenant_id" = nullif(current_setting('app.tenant_id', true), '')::uuid);--> statement-breakpoint
CREATE POLICY "platform_session_participant_tenant_policy" ON "platform_session_participant" AS PERMISSIVE FOR ALL TO public USING ("platform_session_participant"."tenant_id" = nullif(current_setting('app.tenant_id', true), '')::uuid) WITH CHECK ("platform_session_participant"."tenant_id" = nullif(current_setting('app.tenant_id', true), '')::uuid);--> statement-breakpoint
CREATE POLICY "platform_session_wait_tenant_policy" ON "platform_session_wait" AS PERMISSIVE FOR ALL TO public USING ("platform_session_wait"."tenant_id" = nullif(current_setting('app.tenant_id', true), '')::uuid) WITH CHECK ("platform_session_wait"."tenant_id" = nullif(current_setting('app.tenant_id', true), '')::uuid);--> statement-breakpoint
CREATE POLICY "platform_conversation_tenant_policy" ON "platform_conversation" AS PERMISSIVE FOR ALL TO public USING ("platform_conversation"."tenant_id" = nullif(current_setting('app.tenant_id', true), '')::uuid) WITH CHECK ("platform_conversation"."tenant_id" = nullif(current_setting('app.tenant_id', true), '')::uuid);--> statement-breakpoint
CREATE POLICY "platform_conversation_message_tenant_policy" ON "platform_conversation_message" AS PERMISSIVE FOR ALL TO public USING ("platform_conversation_message"."tenant_id" = nullif(current_setting('app.tenant_id', true), '')::uuid) WITH CHECK ("platform_conversation_message"."tenant_id" = nullif(current_setting('app.tenant_id', true), '')::uuid);--> statement-breakpoint
CREATE POLICY "platform_conversation_subject_tenant_policy" ON "platform_conversation_subject" AS PERMISSIVE FOR ALL TO public USING ("platform_conversation_subject"."tenant_id" = nullif(current_setting('app.tenant_id', true), '')::uuid) WITH CHECK ("platform_conversation_subject"."tenant_id" = nullif(current_setting('app.tenant_id', true), '')::uuid);--> statement-breakpoint
CREATE POLICY "platform_event_receipt_tenant_policy" ON "platform_event_receipt" AS PERMISSIVE FOR ALL TO public USING ("platform_event_receipt"."tenant_id" = nullif(current_setting('app.tenant_id', true), '')::uuid) WITH CHECK ("platform_event_receipt"."tenant_id" = nullif(current_setting('app.tenant_id', true), '')::uuid);