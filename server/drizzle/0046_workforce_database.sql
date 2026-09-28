CREATE TABLE "vh_membership_application_file" (
	"tenant_id" uuid NOT NULL,
	"project_id" uuid NOT NULL,
	"application_id" uuid NOT NULL,
	"file_id" uuid NOT NULL,
	"created_at" timestamp with time zone DEFAULT now() NOT NULL,
	CONSTRAINT "vh_membership_application_file_tenant_id_application_id_file_id_pk" PRIMARY KEY("tenant_id","application_id","file_id")
);
--> statement-breakpoint
ALTER TABLE "vh_membership_application_file" ENABLE ROW LEVEL SECURITY;--> statement-breakpoint
CREATE TABLE "vh_pet_document" (
	"tenant_id" uuid NOT NULL,
	"project_id" uuid NOT NULL,
	"pet_id" uuid NOT NULL,
	"file_id" uuid NOT NULL,
	"created_at" timestamp with time zone DEFAULT now() NOT NULL,
	CONSTRAINT "vh_pet_document_tenant_id_pet_id_file_id_pk" PRIMARY KEY("tenant_id","pet_id","file_id")
);
--> statement-breakpoint
ALTER TABLE "vh_pet_document" ENABLE ROW LEVEL SECURITY;--> statement-breakpoint
CREATE TABLE "vh_report_attachment" (
	"tenant_id" uuid NOT NULL,
	"project_id" uuid NOT NULL,
	"report_id" uuid NOT NULL,
	"file_id" uuid NOT NULL,
	"created_at" timestamp with time zone DEFAULT now() NOT NULL,
	CONSTRAINT "vh_report_attachment_tenant_id_report_id_file_id_pk" PRIMARY KEY("tenant_id","report_id","file_id")
);
--> statement-breakpoint
ALTER TABLE "vh_report_attachment" ENABLE ROW LEVEL SECURITY;--> statement-breakpoint
CREATE TABLE "vh_request_attachment" (
	"tenant_id" uuid NOT NULL,
	"project_id" uuid NOT NULL,
	"request_id" uuid NOT NULL,
	"file_id" uuid NOT NULL,
	"caption" text,
	"created_at" timestamp with time zone DEFAULT now() NOT NULL,
	CONSTRAINT "vh_request_attachment_tenant_id_request_id_file_id_pk" PRIMARY KEY("tenant_id","request_id","file_id")
);
--> statement-breakpoint
ALTER TABLE "vh_request_attachment" ENABLE ROW LEVEL SECURITY;--> statement-breakpoint
CREATE TABLE "vh_service_request_file" (
	"tenant_id" uuid NOT NULL,
	"project_id" uuid NOT NULL,
	"request_id" uuid NOT NULL,
	"file_id" uuid NOT NULL,
	"created_at" timestamp with time zone DEFAULT now() NOT NULL,
	CONSTRAINT "vh_service_request_file_tenant_id_request_id_file_id_pk" PRIMARY KEY("tenant_id","request_id","file_id")
);
--> statement-breakpoint
ALTER TABLE "vh_service_request_file" ENABLE ROW LEVEL SECURITY;--> statement-breakpoint
CREATE TABLE "vh_fee_schedule" (
	"id" uuid PRIMARY KEY DEFAULT gen_random_uuid() NOT NULL,
	"tenant_id" uuid NOT NULL,
	"project_id" uuid NOT NULL,
	"code" text NOT NULL,
	"version_no" integer NOT NULL,
	"effective_from" timestamp with time zone NOT NULL,
	"effective_until" timestamp with time zone,
	"description" text NOT NULL,
	"amount_minor" bigint NOT NULL,
	"currency" char(3) NOT NULL,
	"billing_unit" text NOT NULL,
	"status" text NOT NULL,
	"created_at" timestamp with time zone DEFAULT now() NOT NULL,
	"version" bigint DEFAULT 1 NOT NULL,
	"updated_at" timestamp with time zone DEFAULT now() NOT NULL,
	CONSTRAINT "vh_fee_schedule_uq_0" UNIQUE("tenant_id","project_id","code","version_no"),
	CONSTRAINT "vh_fee_schedule_uq_1" UNIQUE("tenant_id","id"),
	CONSTRAINT "vh_fee_schedule_uq_2" UNIQUE("tenant_id","project_id","id"),
	CONSTRAINT "vh_fee_schedule_status_ck" CHECK ("vh_fee_schedule"."status" in ('DRAFT', 'PUBLISHED', 'RETIRED')),
	CONSTRAINT "vh_fee_schedule_ck_0" CHECK (version_no > 0),
	CONSTRAINT "vh_fee_schedule_ck_1" CHECK (amount_minor >= 0),
	CONSTRAINT "vh_fee_schedule_ck_2" CHECK (effective_until IS NULL OR effective_until > effective_from),
	CONSTRAINT "vh_fee_schedule_ck_3" CHECK (currency ~ '^[A-Z]{3}$'),
	CONSTRAINT "vh_fee_schedule_ck_4" CHECK (version > 0)
);
--> statement-breakpoint
ALTER TABLE "vh_fee_schedule" ENABLE ROW LEVEL SECURITY;--> statement-breakpoint
CREATE TABLE "vh_invoice" (
	"id" uuid PRIMARY KEY DEFAULT gen_random_uuid() NOT NULL,
	"tenant_id" uuid NOT NULL,
	"project_id" uuid NOT NULL,
	"apartment_id" uuid NOT NULL,
	"billed_to_user_id" text NOT NULL,
	"invoice_number" text NOT NULL,
	"period_start" date NOT NULL,
	"period_end" date NOT NULL,
	"due_at" timestamp with time zone NOT NULL,
	"total_minor" bigint NOT NULL,
	"currency" char(3) NOT NULL,
	"status" text NOT NULL,
	"created_at" timestamp with time zone DEFAULT now() NOT NULL,
	"version" bigint DEFAULT 1 NOT NULL,
	"updated_at" timestamp with time zone DEFAULT now() NOT NULL,
	CONSTRAINT "vh_invoice_uq_0" UNIQUE("tenant_id","invoice_number"),
	CONSTRAINT "vh_invoice_uq_1" UNIQUE("tenant_id","id"),
	CONSTRAINT "vh_invoice_uq_2" UNIQUE("tenant_id","project_id","id"),
	CONSTRAINT "vh_invoice_status_ck" CHECK ("vh_invoice"."status" in ('DRAFT', 'ISSUED', 'PARTIALLY_PAID', 'PAID', 'VOID')),
	CONSTRAINT "vh_invoice_ck_0" CHECK (period_end >= period_start),
	CONSTRAINT "vh_invoice_ck_1" CHECK (total_minor >= 0),
	CONSTRAINT "vh_invoice_ck_2" CHECK (currency ~ '^[A-Z]{3}$'),
	CONSTRAINT "vh_invoice_ck_3" CHECK (version > 0)
);
--> statement-breakpoint
ALTER TABLE "vh_invoice" ENABLE ROW LEVEL SECURITY;--> statement-breakpoint
CREATE TABLE "vh_invoice_line" (
	"id" uuid PRIMARY KEY DEFAULT gen_random_uuid() NOT NULL,
	"tenant_id" uuid NOT NULL,
	"project_id" uuid NOT NULL,
	"invoice_id" uuid NOT NULL,
	"fee_schedule_id" uuid,
	"description" text NOT NULL,
	"quantity" numeric NOT NULL,
	"unit_price_minor" bigint NOT NULL,
	"total_minor" bigint NOT NULL,
	"created_at" timestamp with time zone DEFAULT now() NOT NULL,
	"version" bigint DEFAULT 1 NOT NULL,
	"updated_at" timestamp with time zone DEFAULT now() NOT NULL,
	CONSTRAINT "vh_invoice_line_uq_0" UNIQUE("tenant_id","id"),
	CONSTRAINT "vh_invoice_line_uq_1" UNIQUE("tenant_id","project_id","id"),
	CONSTRAINT "vh_invoice_line_ck_0" CHECK (quantity > 0),
	CONSTRAINT "vh_invoice_line_ck_1" CHECK (unit_price_minor >= 0),
	CONSTRAINT "vh_invoice_line_ck_2" CHECK (total_minor >= 0),
	CONSTRAINT "vh_invoice_line_ck_3" CHECK (total_minor = round(quantity * unit_price_minor)),
	CONSTRAINT "vh_invoice_line_ck_4" CHECK (version > 0)
);
--> statement-breakpoint
ALTER TABLE "vh_invoice_line" ENABLE ROW LEVEL SECURITY;--> statement-breakpoint
CREATE TABLE "vh_loyalty_account" (
	"id" uuid PRIMARY KEY DEFAULT gen_random_uuid() NOT NULL,
	"tenant_id" uuid NOT NULL,
	"user_id" text NOT NULL,
	"provider" text NOT NULL,
	"external_account_ref" text,
	"status" text NOT NULL,
	"created_at" timestamp with time zone DEFAULT now() NOT NULL,
	"version" bigint DEFAULT 1 NOT NULL,
	"updated_at" timestamp with time zone DEFAULT now() NOT NULL,
	CONSTRAINT "vh_loyalty_account_uq_0" UNIQUE("tenant_id","user_id","provider"),
	CONSTRAINT "vh_loyalty_account_uq_1" UNIQUE("tenant_id","id"),
	CONSTRAINT "vh_loyalty_account_status_ck" CHECK ("vh_loyalty_account"."status" in ('ACTIVE', 'SUSPENDED', 'CLOSED')),
	CONSTRAINT "vh_loyalty_account_ck_0" CHECK (version > 0)
);
--> statement-breakpoint
ALTER TABLE "vh_loyalty_account" ENABLE ROW LEVEL SECURITY;--> statement-breakpoint
CREATE TABLE "vh_loyalty_entry" (
	"id" uuid PRIMARY KEY DEFAULT gen_random_uuid() NOT NULL,
	"tenant_id" uuid NOT NULL,
	"account_id" uuid NOT NULL,
	"points_delta" bigint NOT NULL,
	"reason" text NOT NULL,
	"provider_event_id" text NOT NULL,
	"occurred_at" timestamp with time zone NOT NULL,
	"created_at" timestamp with time zone DEFAULT now() NOT NULL,
	CONSTRAINT "vh_loyalty_entry_uq_0" UNIQUE("tenant_id","provider_event_id"),
	CONSTRAINT "vh_loyalty_entry_uq_1" UNIQUE("tenant_id","id"),
	CONSTRAINT "vh_loyalty_entry_ck_0" CHECK (points_delta <> 0)
);
--> statement-breakpoint
ALTER TABLE "vh_loyalty_entry" ENABLE ROW LEVEL SECURITY;--> statement-breakpoint
CREATE TABLE "vh_payment_allocation" (
	"tenant_id" uuid NOT NULL,
	"project_id" uuid NOT NULL,
	"payment_attempt_id" uuid NOT NULL,
	"invoice_id" uuid NOT NULL,
	"amount_minor" bigint NOT NULL,
	"created_at" timestamp with time zone DEFAULT now() NOT NULL,
	CONSTRAINT "vh_payment_allocation_tenant_id_payment_attempt_id_invoice_id_pk" PRIMARY KEY("tenant_id","payment_attempt_id","invoice_id"),
	CONSTRAINT "vh_payment_allocation_ck_0" CHECK (amount_minor > 0)
);
--> statement-breakpoint
ALTER TABLE "vh_payment_allocation" ENABLE ROW LEVEL SECURITY;--> statement-breakpoint
CREATE TABLE "vh_payment_attempt" (
	"id" uuid PRIMARY KEY DEFAULT gen_random_uuid() NOT NULL,
	"tenant_id" uuid NOT NULL,
	"project_id" uuid NOT NULL,
	"invoice_id" uuid NOT NULL,
	"initiated_by_user_id" text NOT NULL,
	"amount_minor" bigint NOT NULL,
	"currency" char(3) NOT NULL,
	"provider" text NOT NULL,
	"provider_payment_ref" text,
	"idempotency_key" text NOT NULL,
	"status" text NOT NULL,
	"confirmed_at" timestamp with time zone,
	"created_at" timestamp with time zone DEFAULT now() NOT NULL,
	"version" bigint DEFAULT 1 NOT NULL,
	"updated_at" timestamp with time zone DEFAULT now() NOT NULL,
	CONSTRAINT "vh_payment_attempt_uq_0" UNIQUE("tenant_id","idempotency_key"),
	CONSTRAINT "vh_payment_attempt_uq_1" UNIQUE("provider","provider_payment_ref"),
	CONSTRAINT "vh_payment_attempt_uq_2" UNIQUE("tenant_id","id"),
	CONSTRAINT "vh_payment_attempt_uq_3" UNIQUE("tenant_id","project_id","id"),
	CONSTRAINT "vh_payment_attempt_uq_4" UNIQUE("tenant_id","project_id","invoice_id","id"),
	CONSTRAINT "vh_payment_attempt_status_ck" CHECK ("vh_payment_attempt"."status" in ('PENDING', 'REQUIRES_ACTION', 'SUCCEEDED', 'FAILED', 'CANCELLED', 'SIMULATED')),
	CONSTRAINT "vh_payment_attempt_ck_0" CHECK (amount_minor > 0),
	CONSTRAINT "vh_payment_attempt_ck_1" CHECK (status <> 'SUCCEEDED' OR (provider_payment_ref IS NOT NULL AND confirmed_at IS NOT NULL)),
	CONSTRAINT "vh_payment_attempt_ck_2" CHECK (currency ~ '^[A-Z]{3}$'),
	CONSTRAINT "vh_payment_attempt_ck_3" CHECK (version > 0)
);
--> statement-breakpoint
ALTER TABLE "vh_payment_attempt" ENABLE ROW LEVEL SECURITY;--> statement-breakpoint
CREATE TABLE "vh_booking" (
	"id" uuid PRIMARY KEY DEFAULT gen_random_uuid() NOT NULL,
	"tenant_id" uuid NOT NULL,
	"project_id" uuid NOT NULL,
	"slot_id" uuid NOT NULL,
	"apartment_id" uuid NOT NULL,
	"booked_by_membership_id" uuid NOT NULL,
	"party_size" integer NOT NULL,
	"status" text NOT NULL,
	"hold_expires_at" timestamp with time zone,
	"price_minor" bigint NOT NULL,
	"currency" char(3) NOT NULL,
	"cancelled_at" timestamp with time zone,
	"cancellation_reason" text,
	"created_at" timestamp with time zone DEFAULT now() NOT NULL,
	"version" bigint DEFAULT 1 NOT NULL,
	"updated_at" timestamp with time zone DEFAULT now() NOT NULL,
	CONSTRAINT "vh_booking_uq_0" UNIQUE("tenant_id","id"),
	CONSTRAINT "vh_booking_uq_1" UNIQUE("tenant_id","project_id","id"),
	CONSTRAINT "vh_booking_status_ck" CHECK ("vh_booking"."status" in ('HELD', 'CONFIRMED', 'CANCELLED', 'EXPIRED', 'COMPLETED')),
	CONSTRAINT "vh_booking_ck_0" CHECK (party_size > 0),
	CONSTRAINT "vh_booking_ck_1" CHECK (price_minor >= 0),
	CONSTRAINT "vh_booking_ck_2" CHECK (status <> 'HELD' OR hold_expires_at IS NOT NULL),
	CONSTRAINT "vh_booking_ck_3" CHECK (currency ~ '^[A-Z]{3}$'),
	CONSTRAINT "vh_booking_ck_4" CHECK (version > 0)
);
--> statement-breakpoint
ALTER TABLE "vh_booking" ENABLE ROW LEVEL SECURITY;--> statement-breakpoint
CREATE TABLE "vh_facility" (
	"id" uuid PRIMARY KEY DEFAULT gen_random_uuid() NOT NULL,
	"tenant_id" uuid NOT NULL,
	"project_id" uuid NOT NULL,
	"place_id" uuid,
	"code" text NOT NULL,
	"name" text NOT NULL,
	"category" text NOT NULL,
	"capacity" integer NOT NULL,
	"fee_minor" bigint NOT NULL,
	"currency" char(3) NOT NULL,
	"booking_policy_json" jsonb NOT NULL,
	"exclusive_resource" boolean NOT NULL,
	"status" text NOT NULL,
	"created_at" timestamp with time zone DEFAULT now() NOT NULL,
	"version" bigint DEFAULT 1 NOT NULL,
	"updated_at" timestamp with time zone DEFAULT now() NOT NULL,
	CONSTRAINT "vh_facility_uq_0" UNIQUE("tenant_id","project_id","code"),
	CONSTRAINT "vh_facility_uq_1" UNIQUE("tenant_id","id"),
	CONSTRAINT "vh_facility_uq_2" UNIQUE("tenant_id","project_id","id"),
	CONSTRAINT "vh_facility_status_ck" CHECK ("vh_facility"."status" in ('ACTIVE', 'MAINTENANCE', 'RETIRED')),
	CONSTRAINT "vh_facility_ck_0" CHECK (capacity > 0),
	CONSTRAINT "vh_facility_ck_1" CHECK (fee_minor >= 0),
	CONSTRAINT "vh_facility_ck_2" CHECK (currency ~ '^[A-Z]{3}$'),
	CONSTRAINT "vh_facility_ck_3" CHECK (version > 0)
);
--> statement-breakpoint
ALTER TABLE "vh_facility" ENABLE ROW LEVEL SECURITY;--> statement-breakpoint
CREATE TABLE "vh_time_slot" (
	"id" uuid PRIMARY KEY DEFAULT gen_random_uuid() NOT NULL,
	"tenant_id" uuid NOT NULL,
	"project_id" uuid NOT NULL,
	"facility_id" uuid NOT NULL,
	"starts_at" timestamp with time zone NOT NULL,
	"ends_at" timestamp with time zone NOT NULL,
	"capacity" integer NOT NULL,
	"status" text NOT NULL,
	"created_at" timestamp with time zone DEFAULT now() NOT NULL,
	"version" bigint DEFAULT 1 NOT NULL,
	"updated_at" timestamp with time zone DEFAULT now() NOT NULL,
	CONSTRAINT "vh_time_slot_uq_0" UNIQUE("tenant_id","facility_id","starts_at","ends_at"),
	CONSTRAINT "vh_time_slot_uq_1" UNIQUE("tenant_id","id"),
	CONSTRAINT "vh_time_slot_uq_2" UNIQUE("tenant_id","project_id","id"),
	CONSTRAINT "vh_time_slot_status_ck" CHECK ("vh_time_slot"."status" in ('OPEN', 'BLOCKED')),
	CONSTRAINT "vh_time_slot_ck_0" CHECK (ends_at > starts_at),
	CONSTRAINT "vh_time_slot_ck_1" CHECK (capacity > 0),
	CONSTRAINT "vh_time_slot_ck_2" CHECK (version > 0)
);
--> statement-breakpoint
ALTER TABLE "vh_time_slot" ENABLE ROW LEVEL SECURITY;--> statement-breakpoint
CREATE TABLE "vh_business_event" (
	"id" uuid PRIMARY KEY DEFAULT gen_random_uuid() NOT NULL,
	"tenant_id" uuid NOT NULL,
	"project_id" uuid NOT NULL,
	"incident_id" uuid,
	"subject_type" text NOT NULL,
	"subject_id" uuid NOT NULL,
	"event_type" text NOT NULL,
	"actor_type" text NOT NULL,
	"actor_id" text NOT NULL,
	"actor_version" text,
	"data" jsonb NOT NULL,
	"correlation_id" text NOT NULL,
	"occurred_at" timestamp with time zone NOT NULL,
	"visibility" text NOT NULL,
	"schema_version" integer NOT NULL,
	"subject_version" bigint NOT NULL,
	"created_at" timestamp with time zone DEFAULT now() NOT NULL,
	CONSTRAINT "vh_business_event_uq_0" UNIQUE("tenant_id","id"),
	CONSTRAINT "vh_business_event_uq_1" UNIQUE("tenant_id","project_id","id"),
	CONSTRAINT "vh_business_event_actor_type_ck" CHECK ("vh_business_event"."actor_type" in ('HUMAN', 'SYSTEM', 'AUTOMATION', 'AGENT', 'EXTERNAL_SERVICE')),
	CONSTRAINT "vh_business_event_visibility_ck" CHECK ("vh_business_event"."visibility" in ('INTERNAL', 'RESIDENT_VISIBLE')),
	CONSTRAINT "vh_business_event_ck_0" CHECK (schema_version > 0),
	CONSTRAINT "vh_business_event_ck_1" CHECK (subject_version > 0)
);
--> statement-breakpoint
ALTER TABLE "vh_business_event" ENABLE ROW LEVEL SECURITY;--> statement-breakpoint
CREATE TABLE "vh_message" (
	"id" uuid PRIMARY KEY DEFAULT gen_random_uuid() NOT NULL,
	"tenant_id" uuid NOT NULL,
	"project_id" uuid NOT NULL,
	"incident_id" uuid NOT NULL,
	"resident_report_id" uuid,
	"body" text NOT NULL,
	"author_type" text NOT NULL,
	"author_id" text NOT NULL,
	"visibility" text NOT NULL,
	"created_at" timestamp with time zone DEFAULT now() NOT NULL,
	CONSTRAINT "vh_message_uq_0" UNIQUE("tenant_id","id"),
	CONSTRAINT "vh_message_uq_1" UNIQUE("tenant_id","project_id","id"),
	CONSTRAINT "vh_message_author_type_ck" CHECK ("vh_message"."author_type" in ('HUMAN', 'SYSTEM', 'AGENT')),
	CONSTRAINT "vh_message_visibility_ck" CHECK ("vh_message"."visibility" in ('INTERNAL', 'RESIDENT_VISIBLE'))
);
--> statement-breakpoint
ALTER TABLE "vh_message" ENABLE ROW LEVEL SECURITY;--> statement-breakpoint
CREATE TABLE "vh_notification" (
	"id" uuid PRIMARY KEY DEFAULT gen_random_uuid() NOT NULL,
	"tenant_id" uuid NOT NULL,
	"project_id" uuid NOT NULL,
	"business_event_id" uuid,
	"recipient_id" text NOT NULL,
	"type" text NOT NULL,
	"subject_type" text NOT NULL,
	"subject_id" uuid NOT NULL,
	"title" text NOT NULL,
	"body" text NOT NULL,
	"read_at" timestamp with time zone,
	"delivery_status" text NOT NULL,
	"dedupe_key" text NOT NULL,
	"created_at" timestamp with time zone DEFAULT now() NOT NULL,
	"version" bigint DEFAULT 1 NOT NULL,
	"updated_at" timestamp with time zone DEFAULT now() NOT NULL,
	CONSTRAINT "vh_notification_uq_0" UNIQUE("tenant_id","recipient_id","dedupe_key"),
	CONSTRAINT "vh_notification_uq_1" UNIQUE("tenant_id","id"),
	CONSTRAINT "vh_notification_uq_2" UNIQUE("tenant_id","project_id","id"),
	CONSTRAINT "vh_notification_delivery_status_ck" CHECK ("vh_notification"."delivery_status" in ('QUEUED', 'DELIVERED', 'FAILED')),
	CONSTRAINT "vh_notification_ck_0" CHECK (version > 0)
);
--> statement-breakpoint
ALTER TABLE "vh_notification" ENABLE ROW LEVEL SECURITY;--> statement-breakpoint
CREATE TABLE "vh_community_event" (
	"id" uuid PRIMARY KEY DEFAULT gen_random_uuid() NOT NULL,
	"tenant_id" uuid NOT NULL,
	"project_id" uuid NOT NULL,
	"place_id" uuid,
	"title" text NOT NULL,
	"starts_at" timestamp with time zone NOT NULL,
	"ends_at" timestamp with time zone NOT NULL,
	"registration_closes_at" timestamp with time zone NOT NULL,
	"capacity" integer NOT NULL,
	"status" text NOT NULL,
	"created_at" timestamp with time zone DEFAULT now() NOT NULL,
	"version" bigint DEFAULT 1 NOT NULL,
	"updated_at" timestamp with time zone DEFAULT now() NOT NULL,
	CONSTRAINT "vh_community_event_uq_0" UNIQUE("tenant_id","id"),
	CONSTRAINT "vh_community_event_uq_1" UNIQUE("tenant_id","project_id","id"),
	CONSTRAINT "vh_community_event_status_ck" CHECK ("vh_community_event"."status" in ('DRAFT', 'PUBLISHED', 'CANCELLED', 'COMPLETED')),
	CONSTRAINT "vh_community_event_ck_0" CHECK (ends_at > starts_at),
	CONSTRAINT "vh_community_event_ck_1" CHECK (capacity > 0),
	CONSTRAINT "vh_community_event_ck_2" CHECK (registration_closes_at <= starts_at),
	CONSTRAINT "vh_community_event_ck_3" CHECK (version > 0)
);
--> statement-breakpoint
ALTER TABLE "vh_community_event" ENABLE ROW LEVEL SECURITY;--> statement-breakpoint
CREATE TABLE "vh_content_item" (
	"id" uuid PRIMARY KEY DEFAULT gen_random_uuid() NOT NULL,
	"tenant_id" uuid NOT NULL,
	"project_id" uuid NOT NULL,
	"title" text NOT NULL,
	"kind" text NOT NULL,
	"body" text NOT NULL,
	"status" text NOT NULL,
	"published_at" timestamp with time zone,
	"expires_at" timestamp with time zone,
	"created_at" timestamp with time zone DEFAULT now() NOT NULL,
	"version" bigint DEFAULT 1 NOT NULL,
	"updated_at" timestamp with time zone DEFAULT now() NOT NULL,
	CONSTRAINT "vh_content_item_uq_0" UNIQUE("tenant_id","id"),
	CONSTRAINT "vh_content_item_uq_1" UNIQUE("tenant_id","project_id","id"),
	CONSTRAINT "vh_content_item_kind_ck" CHECK ("vh_content_item"."kind" in ('NEWS', 'HANDBOOK', 'NOTICE')),
	CONSTRAINT "vh_content_item_status_ck" CHECK ("vh_content_item"."status" in ('DRAFT', 'PUBLISHED', 'ARCHIVED')),
	CONSTRAINT "vh_content_item_ck_0" CHECK (status <> 'PUBLISHED' OR published_at IS NOT NULL),
	CONSTRAINT "vh_content_item_ck_1" CHECK (expires_at IS NULL OR expires_at > published_at),
	CONSTRAINT "vh_content_item_ck_2" CHECK (version > 0)
);
--> statement-breakpoint
ALTER TABLE "vh_content_item" ENABLE ROW LEVEL SECURITY;--> statement-breakpoint
CREATE TABLE "vh_event_registration" (
	"id" uuid PRIMARY KEY DEFAULT gen_random_uuid() NOT NULL,
	"tenant_id" uuid NOT NULL,
	"project_id" uuid NOT NULL,
	"event_id" uuid NOT NULL,
	"membership_id" uuid NOT NULL,
	"guest_count" integer NOT NULL,
	"status" text NOT NULL,
	"created_at" timestamp with time zone DEFAULT now() NOT NULL,
	"version" bigint DEFAULT 1 NOT NULL,
	"updated_at" timestamp with time zone DEFAULT now() NOT NULL,
	CONSTRAINT "vh_event_registration_uq_0" UNIQUE("tenant_id","event_id","membership_id"),
	CONSTRAINT "vh_event_registration_uq_1" UNIQUE("tenant_id","id"),
	CONSTRAINT "vh_event_registration_uq_2" UNIQUE("tenant_id","project_id","id"),
	CONSTRAINT "vh_event_registration_status_ck" CHECK ("vh_event_registration"."status" in ('REGISTERED', 'CANCELLED', 'ATTENDED')),
	CONSTRAINT "vh_event_registration_ck_0" CHECK (guest_count >= 0),
	CONSTRAINT "vh_event_registration_ck_1" CHECK (version > 0)
);
--> statement-breakpoint
ALTER TABLE "vh_event_registration" ENABLE ROW LEVEL SECURITY;--> statement-breakpoint
CREATE TABLE "vh_map_place" (
	"id" uuid PRIMARY KEY DEFAULT gen_random_uuid() NOT NULL,
	"tenant_id" uuid NOT NULL,
	"project_id" uuid NOT NULL,
	"tower_id" uuid,
	"name" text NOT NULL,
	"category" text NOT NULL,
	"address" text NOT NULL,
	"latitude" numeric,
	"longitude" numeric,
	"status" text NOT NULL,
	"created_at" timestamp with time zone DEFAULT now() NOT NULL,
	"version" bigint DEFAULT 1 NOT NULL,
	"updated_at" timestamp with time zone DEFAULT now() NOT NULL,
	CONSTRAINT "vh_map_place_uq_0" UNIQUE("tenant_id","id"),
	CONSTRAINT "vh_map_place_uq_1" UNIQUE("tenant_id","project_id","id"),
	CONSTRAINT "vh_map_place_status_ck" CHECK ("vh_map_place"."status" in ('ACTIVE', 'RETIRED')),
	CONSTRAINT "vh_map_place_ck_0" CHECK ((latitude IS NULL) = (longitude IS NULL)),
	CONSTRAINT "vh_map_place_ck_1" CHECK (latitude IS NULL OR latitude BETWEEN -90 AND 90),
	CONSTRAINT "vh_map_place_ck_2" CHECK (longitude IS NULL OR longitude BETWEEN -180 AND 180),
	CONSTRAINT "vh_map_place_ck_3" CHECK (version > 0)
);
--> statement-breakpoint
ALTER TABLE "vh_map_place" ENABLE ROW LEVEL SECURITY;--> statement-breakpoint
CREATE TABLE "vh_miniapp_catalog" (
	"id" uuid PRIMARY KEY DEFAULT gen_random_uuid() NOT NULL,
	"tenant_id" uuid NOT NULL,
	"project_id" uuid NOT NULL,
	"code" text NOT NULL,
	"name" text NOT NULL,
	"description" text NOT NULL,
	"destination_url" text NOT NULL,
	"status" text NOT NULL,
	"created_at" timestamp with time zone DEFAULT now() NOT NULL,
	"version" bigint DEFAULT 1 NOT NULL,
	"updated_at" timestamp with time zone DEFAULT now() NOT NULL,
	CONSTRAINT "vh_miniapp_catalog_uq_0" UNIQUE("tenant_id","project_id","code"),
	CONSTRAINT "vh_miniapp_catalog_uq_1" UNIQUE("tenant_id","id"),
	CONSTRAINT "vh_miniapp_catalog_uq_2" UNIQUE("tenant_id","project_id","id"),
	CONSTRAINT "vh_miniapp_catalog_status_ck" CHECK ("vh_miniapp_catalog"."status" in ('ACTIVE', 'DISABLED')),
	CONSTRAINT "vh_miniapp_catalog_ck_0" CHECK (version > 0)
);
--> statement-breakpoint
ALTER TABLE "vh_miniapp_catalog" ENABLE ROW LEVEL SECURITY;--> statement-breakpoint
CREATE TABLE "vh_offer" (
	"id" uuid PRIMARY KEY DEFAULT gen_random_uuid() NOT NULL,
	"tenant_id" uuid NOT NULL,
	"project_id" uuid NOT NULL,
	"merchant_name" text NOT NULL,
	"title" text NOT NULL,
	"terms" text NOT NULL,
	"starts_at" timestamp with time zone NOT NULL,
	"expires_at" timestamp with time zone NOT NULL,
	"destination_url" text,
	"status" text NOT NULL,
	"created_at" timestamp with time zone DEFAULT now() NOT NULL,
	"version" bigint DEFAULT 1 NOT NULL,
	"updated_at" timestamp with time zone DEFAULT now() NOT NULL,
	CONSTRAINT "vh_offer_uq_0" UNIQUE("tenant_id","id"),
	CONSTRAINT "vh_offer_uq_1" UNIQUE("tenant_id","project_id","id"),
	CONSTRAINT "vh_offer_status_ck" CHECK ("vh_offer"."status" in ('DRAFT', 'PUBLISHED', 'EXPIRED', 'RETIRED')),
	CONSTRAINT "vh_offer_ck_0" CHECK (expires_at > starts_at),
	CONSTRAINT "vh_offer_ck_1" CHECK (version > 0)
);
--> statement-breakpoint
ALTER TABLE "vh_offer" ENABLE ROW LEVEL SECURITY;--> statement-breakpoint
CREATE TABLE "vh_sensor_reading" (
	"id" uuid PRIMARY KEY DEFAULT gen_random_uuid() NOT NULL,
	"tenant_id" uuid NOT NULL,
	"project_id" uuid NOT NULL,
	"place_id" uuid NOT NULL,
	"sensor_code" text NOT NULL,
	"metric" text NOT NULL,
	"value" numeric NOT NULL,
	"unit" text NOT NULL,
	"observed_at" timestamp with time zone NOT NULL,
	"source" text NOT NULL,
	"quality" text NOT NULL,
	"created_at" timestamp with time zone DEFAULT now() NOT NULL,
	CONSTRAINT "vh_sensor_reading_uq_0" UNIQUE("tenant_id","project_id","sensor_code","metric","observed_at"),
	CONSTRAINT "vh_sensor_reading_uq_1" UNIQUE("tenant_id","id"),
	CONSTRAINT "vh_sensor_reading_uq_2" UNIQUE("tenant_id","project_id","id"),
	CONSTRAINT "vh_sensor_reading_quality_ck" CHECK ("vh_sensor_reading"."quality" in ('VALID', 'STALE', 'INVALID'))
);
--> statement-breakpoint
ALTER TABLE "vh_sensor_reading" ENABLE ROW LEVEL SECURITY;--> statement-breakpoint
CREATE TABLE "vh_transit_route" (
	"id" uuid PRIMARY KEY DEFAULT gen_random_uuid() NOT NULL,
	"tenant_id" uuid NOT NULL,
	"project_id" uuid NOT NULL,
	"code" text NOT NULL,
	"name" text NOT NULL,
	"operator" text NOT NULL,
	"timetable_json" jsonb NOT NULL,
	"timetable_version" integer NOT NULL,
	"effective_from" timestamp with time zone NOT NULL,
	"status" text NOT NULL,
	"created_at" timestamp with time zone DEFAULT now() NOT NULL,
	"version" bigint DEFAULT 1 NOT NULL,
	"updated_at" timestamp with time zone DEFAULT now() NOT NULL,
	CONSTRAINT "vh_transit_route_uq_0" UNIQUE("tenant_id","project_id","code"),
	CONSTRAINT "vh_transit_route_uq_1" UNIQUE("tenant_id","id"),
	CONSTRAINT "vh_transit_route_uq_2" UNIQUE("tenant_id","project_id","id"),
	CONSTRAINT "vh_transit_route_status_ck" CHECK ("vh_transit_route"."status" in ('ACTIVE', 'SUSPENDED', 'RETIRED')),
	CONSTRAINT "vh_transit_route_ck_0" CHECK (timetable_version > 0),
	CONSTRAINT "vh_transit_route_ck_1" CHECK (version > 0)
);
--> statement-breakpoint
ALTER TABLE "vh_transit_route" ENABLE ROW LEVEL SECURITY;--> statement-breakpoint
CREATE TABLE "vh_transit_route_stop" (
	"tenant_id" uuid NOT NULL,
	"project_id" uuid NOT NULL,
	"route_id" uuid NOT NULL,
	"stop_id" uuid NOT NULL,
	"sequence_no" integer NOT NULL,
	"created_at" timestamp with time zone DEFAULT now() NOT NULL,
	CONSTRAINT "vh_transit_route_stop_tenant_id_route_id_sequence_no_pk" PRIMARY KEY("tenant_id","route_id","sequence_no"),
	CONSTRAINT "vh_transit_route_stop_ck_0" CHECK (sequence_no > 0)
);
--> statement-breakpoint
ALTER TABLE "vh_transit_route_stop" ENABLE ROW LEVEL SECURITY;--> statement-breakpoint
CREATE TABLE "vh_transit_stop" (
	"id" uuid PRIMARY KEY DEFAULT gen_random_uuid() NOT NULL,
	"tenant_id" uuid NOT NULL,
	"project_id" uuid NOT NULL,
	"name" text NOT NULL,
	"latitude" numeric NOT NULL,
	"longitude" numeric NOT NULL,
	"created_at" timestamp with time zone DEFAULT now() NOT NULL,
	"version" bigint DEFAULT 1 NOT NULL,
	"updated_at" timestamp with time zone DEFAULT now() NOT NULL,
	CONSTRAINT "vh_transit_stop_uq_0" UNIQUE("tenant_id","id"),
	CONSTRAINT "vh_transit_stop_uq_1" UNIQUE("tenant_id","project_id","id"),
	CONSTRAINT "vh_transit_stop_ck_0" CHECK (latitude BETWEEN -90 AND 90),
	CONSTRAINT "vh_transit_stop_ck_1" CHECK (longitude BETWEEN -180 AND 180),
	CONSTRAINT "vh_transit_stop_ck_2" CHECK (version > 0)
);
--> statement-breakpoint
ALTER TABLE "vh_transit_stop" ENABLE ROW LEVEL SECURITY;--> statement-breakpoint
CREATE TABLE "vh_command_receipt" (
	"id" uuid PRIMARY KEY DEFAULT gen_random_uuid() NOT NULL,
	"tenant_id" uuid NOT NULL,
	"idempotency_key" text NOT NULL,
	"command_type" text NOT NULL,
	"actor_user_id" text NOT NULL,
	"payload_hash" text NOT NULL,
	"subject_type" text NOT NULL,
	"subject_id" uuid,
	"response_json" jsonb,
	"status" text NOT NULL,
	"completed_at" timestamp with time zone,
	"expires_at" timestamp with time zone,
	"created_at" timestamp with time zone DEFAULT now() NOT NULL,
	"version" bigint DEFAULT 1 NOT NULL,
	"updated_at" timestamp with time zone DEFAULT now() NOT NULL,
	CONSTRAINT "vh_command_receipt_uq_0" UNIQUE("tenant_id","actor_user_id","command_type","idempotency_key"),
	CONSTRAINT "vh_command_receipt_uq_1" UNIQUE("tenant_id","id"),
	CONSTRAINT "vh_command_receipt_status_ck" CHECK ("vh_command_receipt"."status" in ('IN_PROGRESS', 'COMPLETED')),
	CONSTRAINT "vh_command_receipt_completed_ck" CHECK (status <> 'COMPLETED' OR (completed_at IS NOT NULL AND response_json IS NOT NULL)),
	CONSTRAINT "vh_command_receipt_version_ck" CHECK (version > 0)
);
--> statement-breakpoint
ALTER TABLE "vh_command_receipt" ENABLE ROW LEVEL SECURITY;--> statement-breakpoint
CREATE TABLE "vh_outbox" (
	"id" uuid PRIMARY KEY DEFAULT gen_random_uuid() NOT NULL,
	"tenant_id" uuid NOT NULL,
	"project_id" uuid NOT NULL,
	"business_event_id" uuid NOT NULL,
	"destination" text NOT NULL,
	"payload_json" jsonb NOT NULL,
	"attempt_count" integer NOT NULL,
	"available_at" timestamp with time zone NOT NULL,
	"locked_until" timestamp with time zone,
	"delivered_at" timestamp with time zone,
	"last_error_code" text,
	"created_at" timestamp with time zone DEFAULT now() NOT NULL,
	"version" bigint DEFAULT 1 NOT NULL,
	"updated_at" timestamp with time zone DEFAULT now() NOT NULL,
	CONSTRAINT "vh_outbox_uq_0" UNIQUE("tenant_id","business_event_id","destination"),
	CONSTRAINT "vh_outbox_uq_1" UNIQUE("tenant_id","id"),
	CONSTRAINT "vh_outbox_uq_2" UNIQUE("tenant_id","project_id","id"),
	CONSTRAINT "vh_outbox_ck_0" CHECK (attempt_count >= 0),
	CONSTRAINT "vh_outbox_ck_1" CHECK (version > 0)
);
--> statement-breakpoint
ALTER TABLE "vh_outbox" ENABLE ROW LEVEL SECURITY;--> statement-breakpoint
CREATE TABLE "vh_evidence_ref" (
	"id" uuid PRIMARY KEY DEFAULT gen_random_uuid() NOT NULL,
	"tenant_id" uuid NOT NULL,
	"project_id" uuid NOT NULL,
	"incident_id" uuid NOT NULL,
	"task_id" uuid,
	"work_order_id" uuid,
	"file_id" uuid NOT NULL,
	"kind" text NOT NULL,
	"capture_phase" text NOT NULL,
	"metadata" jsonb NOT NULL,
	"uploaded_by" text NOT NULL,
	"visibility" text NOT NULL,
	"created_at" timestamp with time zone DEFAULT now() NOT NULL,
	CONSTRAINT "vh_evidence_ref_uq_0" UNIQUE("tenant_id","id"),
	CONSTRAINT "vh_evidence_ref_uq_1" UNIQUE("tenant_id","project_id","id"),
	CONSTRAINT "vh_evidence_ref_uq_2" UNIQUE("tenant_id","project_id","incident_id","id"),
	CONSTRAINT "vh_evidence_ref_capture_phase_ck" CHECK ("vh_evidence_ref"."capture_phase" in ('BEFORE', 'AFTER', 'QC', 'OTHER')),
	CONSTRAINT "vh_evidence_ref_visibility_ck" CHECK ("vh_evidence_ref"."visibility" in ('INTERNAL', 'RESIDENT_VISIBLE')),
	CONSTRAINT "vh_evidence_ref_ck_0" CHECK (work_order_id IS NULL OR task_id IS NOT NULL)
);
--> statement-breakpoint
ALTER TABLE "vh_evidence_ref" ENABLE ROW LEVEL SECURITY;--> statement-breakpoint
CREATE TABLE "vh_qc_result" (
	"id" uuid PRIMARY KEY DEFAULT gen_random_uuid() NOT NULL,
	"tenant_id" uuid NOT NULL,
	"project_id" uuid NOT NULL,
	"incident_id" uuid NOT NULL,
	"task_id" uuid NOT NULL,
	"work_order_id" uuid NOT NULL,
	"outcome" text NOT NULL,
	"criteria" jsonb NOT NULL,
	"failed_criteria" jsonb NOT NULL,
	"redo_required" boolean NOT NULL,
	"note" text,
	"checked_by" text NOT NULL,
	"checked_at" timestamp with time zone NOT NULL,
	"created_at" timestamp with time zone DEFAULT now() NOT NULL,
	CONSTRAINT "vh_qc_result_uq_0" UNIQUE("tenant_id","id"),
	CONSTRAINT "vh_qc_result_uq_1" UNIQUE("tenant_id","project_id","id"),
	CONSTRAINT "vh_qc_result_uq_2" UNIQUE("tenant_id","project_id","incident_id","id"),
	CONSTRAINT "vh_qc_result_outcome_ck" CHECK ("vh_qc_result"."outcome" in ('PASS', 'FAIL', 'INCONCLUSIVE')),
	CONSTRAINT "vh_qc_result_ck_0" CHECK (NOT redo_required OR outcome = 'FAIL')
);
--> statement-breakpoint
ALTER TABLE "vh_qc_result" ENABLE ROW LEVEL SECURITY;--> statement-breakpoint
CREATE TABLE "vh_qc_result_evidence" (
	"tenant_id" uuid NOT NULL,
	"project_id" uuid NOT NULL,
	"incident_id" uuid NOT NULL,
	"qc_result_id" uuid NOT NULL,
	"evidence_ref_id" uuid NOT NULL,
	"created_at" timestamp with time zone DEFAULT now() NOT NULL,
	CONSTRAINT "vh_qc_result_evidence_tenant_id_qc_result_id_evidence_ref_id_pk" PRIMARY KEY("tenant_id","qc_result_id","evidence_ref_id")
);
--> statement-breakpoint
ALTER TABLE "vh_qc_result_evidence" ENABLE ROW LEVEL SECURITY;--> statement-breakpoint
CREATE TABLE "vh_root_cause_evidence" (
	"tenant_id" uuid NOT NULL,
	"project_id" uuid NOT NULL,
	"root_cause_finding_id" uuid NOT NULL,
	"evidence_ref_id" uuid NOT NULL,
	"created_at" timestamp with time zone DEFAULT now() NOT NULL,
	CONSTRAINT "vh_root_cause_evidence_tenant_id_root_cause_finding_id_evidence_ref_id_pk" PRIMARY KEY("tenant_id","root_cause_finding_id","evidence_ref_id")
);
--> statement-breakpoint
ALTER TABLE "vh_root_cause_evidence" ENABLE ROW LEVEL SECURITY;--> statement-breakpoint
CREATE TABLE "vh_root_cause_finding" (
	"id" uuid PRIMARY KEY DEFAULT gen_random_uuid() NOT NULL,
	"tenant_id" uuid NOT NULL,
	"project_id" uuid NOT NULL,
	"incident_id" uuid NOT NULL,
	"suspected_domain" text NOT NULL,
	"description" text NOT NULL,
	"status" text NOT NULL,
	"created_by_type" text NOT NULL,
	"created_by_id" text NOT NULL,
	"created_at" timestamp with time zone DEFAULT now() NOT NULL,
	"version" bigint DEFAULT 1 NOT NULL,
	"updated_at" timestamp with time zone DEFAULT now() NOT NULL,
	CONSTRAINT "vh_root_cause_finding_uq_0" UNIQUE("tenant_id","id"),
	CONSTRAINT "vh_root_cause_finding_uq_1" UNIQUE("tenant_id","project_id","id"),
	CONSTRAINT "vh_root_cause_finding_suspected_domain_ck" CHECK ("vh_root_cause_finding"."suspected_domain" in ('TECHNICAL', 'SECURITY', 'PROCESS', 'SANITATION', 'UNKNOWN')),
	CONSTRAINT "vh_root_cause_finding_status_ck" CHECK ("vh_root_cause_finding"."status" in ('PROPOSED', 'CONFIRMED', 'REJECTED')),
	CONSTRAINT "vh_root_cause_finding_created_by_type_ck" CHECK ("vh_root_cause_finding"."created_by_type" in ('HUMAN', 'SYSTEM', 'AGENT')),
	CONSTRAINT "vh_root_cause_finding_ck_0" CHECK (version > 0)
);
--> statement-breakpoint
ALTER TABLE "vh_root_cause_finding" ENABLE ROW LEVEL SECURITY;--> statement-breakpoint
CREATE TABLE "vh_root_cause_incident" (
	"tenant_id" uuid NOT NULL,
	"project_id" uuid NOT NULL,
	"root_cause_finding_id" uuid NOT NULL,
	"related_incident_id" uuid NOT NULL,
	"relation_type" text NOT NULL,
	"created_at" timestamp with time zone DEFAULT now() NOT NULL,
	CONSTRAINT "vh_root_cause_incident_tenant_id_root_cause_finding_id_related_incident_id_pk" PRIMARY KEY("tenant_id","root_cause_finding_id","related_incident_id")
);
--> statement-breakpoint
ALTER TABLE "vh_root_cause_incident" ENABLE ROW LEVEL SECURITY;--> statement-breakpoint
CREATE TABLE "vh_file_object" (
	"id" uuid PRIMARY KEY DEFAULT gen_random_uuid() NOT NULL,
	"tenant_id" uuid NOT NULL,
	"storage_provider" text NOT NULL,
	"storage_key" text NOT NULL,
	"mime_type" text NOT NULL,
	"size_bytes" bigint NOT NULL,
	"checksum" text NOT NULL,
	"uploaded_by_user_id" text NOT NULL,
	"upload_status" text NOT NULL,
	"visibility" text NOT NULL,
	"original_filename" text NOT NULL,
	"uploaded_at" timestamp with time zone,
	"created_at" timestamp with time zone DEFAULT now() NOT NULL,
	"version" bigint DEFAULT 1 NOT NULL,
	"updated_at" timestamp with time zone DEFAULT now() NOT NULL,
	CONSTRAINT "vh_file_object_uq_0" UNIQUE("storage_provider","storage_key"),
	CONSTRAINT "vh_file_object_uq_1" UNIQUE("tenant_id","id"),
	CONSTRAINT "vh_file_object_upload_status_ck" CHECK ("vh_file_object"."upload_status" in ('PENDING', 'UPLOADED', 'QUARANTINED', 'AVAILABLE', 'REJECTED')),
	CONSTRAINT "vh_file_object_visibility_ck" CHECK ("vh_file_object"."visibility" in ('PRIVATE', 'RESIDENT_VISIBLE', 'INTERNAL')),
	CONSTRAINT "vh_file_object_ck_0" CHECK (size_bytes >= 0),
	CONSTRAINT "vh_file_object_ck_1" CHECK (version > 0)
);
--> statement-breakpoint
ALTER TABLE "vh_file_object" ENABLE ROW LEVEL SECURITY;--> statement-breakpoint
CREATE TABLE "vh_case" (
	"id" uuid PRIMARY KEY DEFAULT gen_random_uuid() NOT NULL,
	"tenant_id" uuid NOT NULL,
	"project_id" uuid NOT NULL,
	"resident_user_id" text NOT NULL,
	"apartment_id" uuid,
	"opened_by_membership_id" uuid NOT NULL,
	"status" text NOT NULL,
	"summary" text NOT NULL,
	"opened_at" timestamp with time zone NOT NULL,
	"closed_at" timestamp with time zone,
	"created_at" timestamp with time zone DEFAULT now() NOT NULL,
	"version" bigint DEFAULT 1 NOT NULL,
	"updated_at" timestamp with time zone DEFAULT now() NOT NULL,
	CONSTRAINT "vh_case_uq_0" UNIQUE("tenant_id","id"),
	CONSTRAINT "vh_case_uq_1" UNIQUE("tenant_id","project_id","id"),
	CONSTRAINT "vh_case_status_ck" CHECK ("vh_case"."status" in ('OPEN', 'CLARIFYING', 'READY', 'TICKETED', 'CLOSED', 'CANCELLED')),
	CONSTRAINT "vh_case_ck_0" CHECK (version > 0)
);
--> statement-breakpoint
ALTER TABLE "vh_case" ENABLE ROW LEVEL SECURITY;--> statement-breakpoint
CREATE TABLE "vh_feedback" (
	"id" uuid PRIMARY KEY DEFAULT gen_random_uuid() NOT NULL,
	"tenant_id" uuid NOT NULL,
	"project_id" uuid NOT NULL,
	"report_id" uuid NOT NULL,
	"author_user_id" text NOT NULL,
	"rating" integer NOT NULL,
	"comment" text,
	"created_at" timestamp with time zone DEFAULT now() NOT NULL,
	CONSTRAINT "vh_feedback_uq_0" UNIQUE("tenant_id","report_id","author_user_id"),
	CONSTRAINT "vh_feedback_uq_1" UNIQUE("tenant_id","id"),
	CONSTRAINT "vh_feedback_uq_2" UNIQUE("tenant_id","project_id","id"),
	CONSTRAINT "vh_feedback_ck_0" CHECK (rating BETWEEN 1 AND 5)
);
--> statement-breakpoint
ALTER TABLE "vh_feedback" ENABLE ROW LEVEL SECURITY;--> statement-breakpoint
CREATE TABLE "vh_issue_candidate" (
	"id" uuid PRIMARY KEY DEFAULT gen_random_uuid() NOT NULL,
	"tenant_id" uuid NOT NULL,
	"project_id" uuid NOT NULL,
	"case_id" uuid NOT NULL,
	"source_request_id" uuid,
	"domain" text NOT NULL,
	"category" text NOT NULL,
	"severity" text NOT NULL,
	"normalized_summary" text NOT NULL,
	"location_json" jsonb NOT NULL,
	"confidence" numeric,
	"identified_by_type" text NOT NULL,
	"identified_by_id" text NOT NULL,
	"status" text NOT NULL,
	"required_fields_json" jsonb NOT NULL,
	"missing_fields_json" jsonb NOT NULL,
	"created_at" timestamp with time zone DEFAULT now() NOT NULL,
	"version" bigint DEFAULT 1 NOT NULL,
	"updated_at" timestamp with time zone DEFAULT now() NOT NULL,
	CONSTRAINT "vh_issue_candidate_uq_0" UNIQUE("tenant_id","id"),
	CONSTRAINT "vh_issue_candidate_uq_1" UNIQUE("tenant_id","project_id","id"),
	CONSTRAINT "vh_issue_candidate_uq_2" UNIQUE("tenant_id","project_id","case_id","id"),
	CONSTRAINT "vh_issue_candidate_severity_ck" CHECK ("vh_issue_candidate"."severity" in ('LOW', 'MEDIUM', 'HIGH', 'CRITICAL')),
	CONSTRAINT "vh_issue_candidate_identified_by_type_ck" CHECK ("vh_issue_candidate"."identified_by_type" in ('HUMAN', 'SYSTEM', 'AGENT')),
	CONSTRAINT "vh_issue_candidate_status_ck" CHECK ("vh_issue_candidate"."status" in ('DETECTED', 'NEEDS_CLARIFICATION', 'READY', 'MERGED', 'DISCARDED', 'MATERIALIZED')),
	CONSTRAINT "vh_issue_candidate_ck_0" CHECK (confidence IS NULL OR (confidence >= 0 AND confidence <= 1)),
	CONSTRAINT "vh_issue_candidate_ck_1" CHECK (version > 0)
);
--> statement-breakpoint
ALTER TABLE "vh_issue_candidate" ENABLE ROW LEVEL SECURITY;--> statement-breakpoint
CREATE TABLE "vh_issue_relation" (
	"tenant_id" uuid NOT NULL,
	"project_id" uuid NOT NULL,
	"source_issue_id" uuid NOT NULL,
	"target_issue_id" uuid NOT NULL,
	"relation_type" text NOT NULL,
	"reason" text NOT NULL,
	"created_at" timestamp with time zone DEFAULT now() NOT NULL,
	CONSTRAINT "vh_issue_relation_tenant_id_source_issue_id_target_issue_id_relation_type_pk" PRIMARY KEY("tenant_id","source_issue_id","target_issue_id","relation_type"),
	CONSTRAINT "vh_issue_relation_relation_type_ck" CHECK ("vh_issue_relation"."relation_type" in ('SPLIT_FROM', 'MERGED_INTO', 'RELATED', 'DEPENDS_ON')),
	CONSTRAINT "vh_issue_relation_ck_0" CHECK (source_issue_id <> target_issue_id)
);
--> statement-breakpoint
ALTER TABLE "vh_issue_relation" ENABLE ROW LEVEL SECURITY;--> statement-breakpoint
CREATE TABLE "vh_resident_confirmation" (
	"id" uuid PRIMARY KEY DEFAULT gen_random_uuid() NOT NULL,
	"tenant_id" uuid NOT NULL,
	"project_id" uuid NOT NULL,
	"report_id" uuid NOT NULL,
	"incident_id" uuid NOT NULL,
	"resolution_version" bigint NOT NULL,
	"response" text NOT NULL,
	"note" text,
	"confirmed_by_user_id" text NOT NULL,
	"created_at" timestamp with time zone DEFAULT now() NOT NULL,
	CONSTRAINT "vh_resident_confirmation_uq_0" UNIQUE("tenant_id","report_id","resolution_version"),
	CONSTRAINT "vh_resident_confirmation_uq_1" UNIQUE("tenant_id","id"),
	CONSTRAINT "vh_resident_confirmation_uq_2" UNIQUE("tenant_id","project_id","id"),
	CONSTRAINT "vh_resident_confirmation_response_ck" CHECK ("vh_resident_confirmation"."response" in ('ACCEPTED', 'REOPEN_REQUESTED')),
	CONSTRAINT "vh_resident_confirmation_ck_0" CHECK (resolution_version > 0)
);
--> statement-breakpoint
ALTER TABLE "vh_resident_confirmation" ENABLE ROW LEVEL SECURITY;--> statement-breakpoint
CREATE TABLE "vh_resident_report" (
	"id" uuid PRIMARY KEY DEFAULT gen_random_uuid() NOT NULL,
	"tenant_id" uuid NOT NULL,
	"project_id" uuid NOT NULL,
	"case_id" uuid NOT NULL,
	"issue_candidate_id" uuid,
	"incident_id" uuid,
	"reporter_id" text NOT NULL,
	"reporter_membership_id" uuid NOT NULL,
	"apartment_id" uuid,
	"category" text NOT NULL,
	"description" text NOT NULL,
	"location_json" jsonb NOT NULL,
	"status" text NOT NULL,
	"created_at" timestamp with time zone DEFAULT now() NOT NULL,
	"version" bigint DEFAULT 1 NOT NULL,
	"updated_at" timestamp with time zone DEFAULT now() NOT NULL,
	CONSTRAINT "vh_resident_report_uq_0" UNIQUE("tenant_id","issue_candidate_id"),
	CONSTRAINT "vh_resident_report_uq_1" UNIQUE("tenant_id","id"),
	CONSTRAINT "vh_resident_report_uq_2" UNIQUE("tenant_id","project_id","id"),
	CONSTRAINT "vh_resident_report_uq_3" UNIQUE("tenant_id","incident_id","reporter_id","id"),
	CONSTRAINT "vh_resident_report_uq_4" UNIQUE("tenant_id","reporter_id","id"),
	CONSTRAINT "vh_resident_report_uq_5" UNIQUE("tenant_id","incident_id","id"),
	CONSTRAINT "vh_resident_report_status_ck" CHECK ("vh_resident_report"."status" in ('SUBMITTED', 'LINKED', 'WITHDRAWN')),
	CONSTRAINT "vh_resident_report_ck_0" CHECK ((status = 'LINKED') = (incident_id IS NOT NULL)),
	CONSTRAINT "vh_resident_report_ck_1" CHECK (version > 0)
);
--> statement-breakpoint
ALTER TABLE "vh_resident_report" ENABLE ROW LEVEL SECURITY;--> statement-breakpoint
CREATE TABLE "vh_resident_request" (
	"id" uuid PRIMARY KEY DEFAULT gen_random_uuid() NOT NULL,
	"tenant_id" uuid NOT NULL,
	"project_id" uuid NOT NULL,
	"case_id" uuid NOT NULL,
	"channel" text NOT NULL,
	"request_type" text NOT NULL,
	"raw_content_ref" text,
	"sanitized_content" text NOT NULL,
	"idempotency_key" text NOT NULL,
	"submitted_by" text NOT NULL,
	"created_at" timestamp with time zone DEFAULT now() NOT NULL,
	CONSTRAINT "vh_resident_request_uq_0" UNIQUE("tenant_id","idempotency_key"),
	CONSTRAINT "vh_resident_request_uq_1" UNIQUE("tenant_id","id"),
	CONSTRAINT "vh_resident_request_uq_2" UNIQUE("tenant_id","project_id","id"),
	CONSTRAINT "vh_resident_request_uq_3" UNIQUE("tenant_id","project_id","case_id","id")
);
--> statement-breakpoint
ALTER TABLE "vh_resident_request" ENABLE ROW LEVEL SECURITY;--> statement-breakpoint
CREATE TABLE "vh_action_approval" (
	"id" uuid PRIMARY KEY DEFAULT gen_random_uuid() NOT NULL,
	"tenant_id" uuid NOT NULL,
	"project_id" uuid NOT NULL,
	"action_request_id" uuid NOT NULL,
	"action_payload_hash" text NOT NULL,
	"policy_version" text NOT NULL,
	"status" text NOT NULL,
	"requested_by_id" text NOT NULL,
	"reviewer_id" text,
	"expires_at" timestamp with time zone NOT NULL,
	"decided_at" timestamp with time zone,
	"reason" text,
	"created_at" timestamp with time zone DEFAULT now() NOT NULL,
	"version" bigint DEFAULT 1 NOT NULL,
	"updated_at" timestamp with time zone DEFAULT now() NOT NULL,
	CONSTRAINT "vh_action_approval_uq_0" UNIQUE("tenant_id","id"),
	CONSTRAINT "vh_action_approval_uq_1" UNIQUE("tenant_id","project_id","id"),
	CONSTRAINT "vh_action_approval_status_ck" CHECK ("vh_action_approval"."status" in ('PENDING', 'APPROVED', 'REJECTED', 'EXPIRED')),
	CONSTRAINT "vh_action_approval_ck_0" CHECK (status NOT IN ('APPROVED','REJECTED') OR (reviewer_id IS NOT NULL AND decided_at IS NOT NULL)),
	CONSTRAINT "vh_action_approval_ck_1" CHECK (version > 0)
);
--> statement-breakpoint
ALTER TABLE "vh_action_approval" ENABLE ROW LEVEL SECURITY;--> statement-breakpoint
CREATE TABLE "vh_action_request" (
	"id" uuid PRIMARY KEY DEFAULT gen_random_uuid() NOT NULL,
	"tenant_id" uuid NOT NULL,
	"project_id" uuid NOT NULL,
	"incident_id" uuid NOT NULL,
	"task_id" uuid NOT NULL,
	"requested_by_type" text NOT NULL,
	"requested_by_id" text NOT NULL,
	"requested_by_version" text,
	"action_type" text NOT NULL,
	"target_type" text NOT NULL,
	"target_id" text,
	"payload" jsonb NOT NULL,
	"payload_hash" text NOT NULL,
	"policy_version" text NOT NULL,
	"expected_subject_version" bigint NOT NULL,
	"idempotency_key" text NOT NULL,
	"status" text NOT NULL,
	"correlation_id" text NOT NULL,
	"trace_id" text NOT NULL,
	"created_at" timestamp with time zone DEFAULT now() NOT NULL,
	"version" bigint DEFAULT 1 NOT NULL,
	"updated_at" timestamp with time zone DEFAULT now() NOT NULL,
	CONSTRAINT "vh_action_request_uq_0" UNIQUE("tenant_id","idempotency_key"),
	CONSTRAINT "vh_action_request_uq_1" UNIQUE("tenant_id","id"),
	CONSTRAINT "vh_action_request_uq_2" UNIQUE("tenant_id","project_id","id"),
	CONSTRAINT "vh_action_request_uq_3" UNIQUE("tenant_id","project_id","incident_id","task_id","id"),
	CONSTRAINT "vh_action_request_uq_4" UNIQUE("tenant_id","id","payload_hash"),
	CONSTRAINT "vh_action_request_uq_5" UNIQUE("tenant_id","id","policy_version"),
	CONSTRAINT "vh_action_request_requested_by_type_ck" CHECK ("vh_action_request"."requested_by_type" in ('HUMAN', 'SYSTEM', 'AUTOMATION', 'AGENT', 'EXTERNAL_SERVICE')),
	CONSTRAINT "vh_action_request_status_ck" CHECK ("vh_action_request"."status" in ('PROPOSED', 'DENIED', 'AWAITING_APPROVAL', 'AUTHORIZED', 'REJECTED', 'EXPIRED', 'EXECUTING', 'SUCCEEDED', 'FAILED')),
	CONSTRAINT "vh_action_request_ck_0" CHECK (expected_subject_version > 0),
	CONSTRAINT "vh_action_request_ck_1" CHECK (version > 0)
);
--> statement-breakpoint
ALTER TABLE "vh_action_request" ENABLE ROW LEVEL SECURITY;--> statement-breakpoint
CREATE TABLE "vh_checklist" (
	"id" uuid PRIMARY KEY DEFAULT gen_random_uuid() NOT NULL,
	"tenant_id" uuid NOT NULL,
	"code" text NOT NULL,
	"name" text NOT NULL,
	"category" text NOT NULL,
	"status" text NOT NULL,
	"created_at" timestamp with time zone DEFAULT now() NOT NULL,
	"version" bigint DEFAULT 1 NOT NULL,
	"updated_at" timestamp with time zone DEFAULT now() NOT NULL,
	CONSTRAINT "vh_checklist_uq_0" UNIQUE("tenant_id","code"),
	CONSTRAINT "vh_checklist_uq_1" UNIQUE("tenant_id","id"),
	CONSTRAINT "vh_checklist_status_ck" CHECK ("vh_checklist"."status" in ('ACTIVE', 'RETIRED')),
	CONSTRAINT "vh_checklist_ck_0" CHECK (version > 0)
);
--> statement-breakpoint
ALTER TABLE "vh_checklist" ENABLE ROW LEVEL SECURITY;--> statement-breakpoint
CREATE TABLE "vh_checklist_version" (
	"id" uuid PRIMARY KEY DEFAULT gen_random_uuid() NOT NULL,
	"tenant_id" uuid NOT NULL,
	"checklist_id" uuid NOT NULL,
	"version_no" integer NOT NULL,
	"criteria_json" jsonb NOT NULL,
	"status" text NOT NULL,
	"published_at" timestamp with time zone,
	"created_by" text NOT NULL,
	"created_at" timestamp with time zone DEFAULT now() NOT NULL,
	"version" bigint DEFAULT 1 NOT NULL,
	"updated_at" timestamp with time zone DEFAULT now() NOT NULL,
	CONSTRAINT "vh_checklist_version_uq_0" UNIQUE("tenant_id","checklist_id","version_no"),
	CONSTRAINT "vh_checklist_version_uq_1" UNIQUE("tenant_id","id"),
	CONSTRAINT "vh_checklist_version_status_ck" CHECK ("vh_checklist_version"."status" in ('DRAFT', 'PUBLISHED', 'RETIRED')),
	CONSTRAINT "vh_checklist_version_ck_0" CHECK (version_no > 0),
	CONSTRAINT "vh_checklist_version_ck_1" CHECK (version > 0)
);
--> statement-breakpoint
ALTER TABLE "vh_checklist_version" ENABLE ROW LEVEL SECURITY;--> statement-breakpoint
CREATE TABLE "vh_execution_grant" (
	"id" uuid PRIMARY KEY DEFAULT gen_random_uuid() NOT NULL,
	"tenant_id" uuid NOT NULL,
	"project_id" uuid NOT NULL,
	"action_request_id" uuid NOT NULL,
	"action_payload_hash" text NOT NULL,
	"policy_version" text NOT NULL,
	"token_hash" text NOT NULL,
	"expires_at" timestamp with time zone NOT NULL,
	"consumed_at" timestamp with time zone,
	"status" text NOT NULL,
	"created_at" timestamp with time zone DEFAULT now() NOT NULL,
	"version" bigint DEFAULT 1 NOT NULL,
	"updated_at" timestamp with time zone DEFAULT now() NOT NULL,
	CONSTRAINT "vh_execution_grant_uq_0" UNIQUE("tenant_id","token_hash"),
	CONSTRAINT "vh_execution_grant_uq_1" UNIQUE("tenant_id","id"),
	CONSTRAINT "vh_execution_grant_uq_2" UNIQUE("tenant_id","project_id","id"),
	CONSTRAINT "vh_execution_grant_status_ck" CHECK ("vh_execution_grant"."status" in ('ACTIVE', 'CONSUMED', 'EXPIRED', 'REVOKED')),
	CONSTRAINT "vh_execution_grant_ck_0" CHECK (status <> 'CONSUMED' OR consumed_at IS NOT NULL),
	CONSTRAINT "vh_execution_grant_ck_1" CHECK (version > 0)
);
--> statement-breakpoint
ALTER TABLE "vh_execution_grant" ENABLE ROW LEVEL SECURITY;--> statement-breakpoint
CREATE TABLE "vh_incident" (
	"id" uuid PRIMARY KEY DEFAULT gen_random_uuid() NOT NULL,
	"tenant_id" uuid NOT NULL,
	"project_id" uuid NOT NULL,
	"tower_id" uuid,
	"category" text NOT NULL,
	"title" text NOT NULL,
	"location_json" jsonb NOT NULL,
	"severity" text NOT NULL,
	"status" text NOT NULL,
	"stage" text NOT NULL,
	"owner_user_id" text,
	"sla_due_at" timestamp with time zone,
	"resolved_at" timestamp with time zone,
	"resolution_version" bigint,
	"closed_at" timestamp with time zone,
	"closed_by_user_id" text,
	"closure_reason" text,
	"created_at" timestamp with time zone DEFAULT now() NOT NULL,
	"version" bigint DEFAULT 1 NOT NULL,
	"updated_at" timestamp with time zone DEFAULT now() NOT NULL,
	CONSTRAINT "vh_incident_uq_0" UNIQUE("tenant_id","id"),
	CONSTRAINT "vh_incident_uq_1" UNIQUE("tenant_id","project_id","id"),
	CONSTRAINT "vh_incident_severity_ck" CHECK ("vh_incident"."severity" in ('LOW', 'MEDIUM', 'HIGH', 'CRITICAL')),
	CONSTRAINT "vh_incident_status_ck" CHECK ("vh_incident"."status" in ('NEW', 'OPEN', 'RESOLVED', 'CLOSED')),
	CONSTRAINT "vh_incident_stage_ck" CHECK ("vh_incident"."stage" in ('INTAKE', 'TRIAGE', 'PLANNING', 'EXECUTION', 'QC', 'RESIDENT_CONFIRMATION')),
	CONSTRAINT "vh_incident_ck_0" CHECK (status NOT IN ('RESOLVED','CLOSED') OR (resolved_at IS NOT NULL AND resolution_version IS NOT NULL)),
	CONSTRAINT "vh_incident_ck_1" CHECK (status <> 'CLOSED' OR (closed_at IS NOT NULL AND closed_by_user_id IS NOT NULL AND closure_reason IS NOT NULL)),
	CONSTRAINT "vh_incident_ck_2" CHECK (version > 0)
);
--> statement-breakpoint
ALTER TABLE "vh_incident" ENABLE ROW LEVEL SECURITY;--> statement-breakpoint
CREATE TABLE "vh_incident_relation" (
	"tenant_id" uuid NOT NULL,
	"project_id" uuid NOT NULL,
	"source_incident_id" uuid NOT NULL,
	"target_incident_id" uuid NOT NULL,
	"relation_type" text NOT NULL,
	"reason" text NOT NULL,
	"created_by" text NOT NULL,
	"created_at" timestamp with time zone DEFAULT now() NOT NULL,
	CONSTRAINT "vh_incident_relation_tenant_id_source_incident_id_target_incident_id_relation_type_pk" PRIMARY KEY("tenant_id","source_incident_id","target_incident_id","relation_type"),
	CONSTRAINT "vh_incident_relation_relation_type_ck" CHECK ("vh_incident_relation"."relation_type" in ('RELATED', 'DUPLICATE', 'CAUSED_BY', 'BLOCKS', 'RECURRING_WITH')),
	CONSTRAINT "vh_incident_relation_ck_0" CHECK (source_incident_id <> target_incident_id)
);
--> statement-breakpoint
ALTER TABLE "vh_incident_relation" ENABLE ROW LEVEL SECURITY;--> statement-breakpoint
CREATE TABLE "vh_rule_evaluation" (
	"id" uuid PRIMARY KEY DEFAULT gen_random_uuid() NOT NULL,
	"tenant_id" uuid NOT NULL,
	"project_id" uuid NOT NULL,
	"action_request_id" uuid NOT NULL,
	"action_payload_hash" text NOT NULL,
	"decision" text NOT NULL,
	"reason_code" text NOT NULL,
	"rule_version" text NOT NULL,
	"evaluated_at" timestamp with time zone NOT NULL,
	"correlation_id" text NOT NULL,
	"created_at" timestamp with time zone DEFAULT now() NOT NULL,
	CONSTRAINT "vh_rule_evaluation_uq_0" UNIQUE("tenant_id","id"),
	CONSTRAINT "vh_rule_evaluation_uq_1" UNIQUE("tenant_id","project_id","id"),
	CONSTRAINT "vh_rule_evaluation_decision_ck" CHECK ("vh_rule_evaluation"."decision" in ('ALLOW', 'REQUIRE_APPROVAL', 'DENY'))
);
--> statement-breakpoint
ALTER TABLE "vh_rule_evaluation" ENABLE ROW LEVEL SECURITY;--> statement-breakpoint
CREATE TABLE "vh_task" (
	"id" uuid PRIMARY KEY DEFAULT gen_random_uuid() NOT NULL,
	"tenant_id" uuid NOT NULL,
	"project_id" uuid NOT NULL,
	"incident_id" uuid NOT NULL,
	"title" text NOT NULL,
	"domain_type" text NOT NULL,
	"domain_data" jsonb NOT NULL,
	"domain_schema_version" integer NOT NULL,
	"assignee_type" text NOT NULL,
	"assignee_id" text,
	"status" text NOT NULL,
	"priority" integer NOT NULL,
	"required" boolean NOT NULL,
	"due_at" timestamp with time zone,
	"created_at" timestamp with time zone DEFAULT now() NOT NULL,
	"version" bigint DEFAULT 1 NOT NULL,
	"updated_at" timestamp with time zone DEFAULT now() NOT NULL,
	CONSTRAINT "vh_task_uq_0" UNIQUE("tenant_id","id"),
	CONSTRAINT "vh_task_uq_1" UNIQUE("tenant_id","project_id","id"),
	CONSTRAINT "vh_task_uq_2" UNIQUE("tenant_id","project_id","incident_id","id"),
	CONSTRAINT "vh_task_assignee_type_ck" CHECK ("vh_task"."assignee_type" in ('HUMAN', 'SYSTEM', 'AUTOMATION', 'EXTERNAL_SERVICE')),
	CONSTRAINT "vh_task_status_ck" CHECK ("vh_task"."status" in ('OPEN', 'ASSIGNED', 'IN_PROGRESS', 'BLOCKED', 'DONE', 'CANCELLED')),
	CONSTRAINT "vh_task_ck_0" CHECK (domain_schema_version > 0),
	CONSTRAINT "vh_task_ck_1" CHECK (priority >= 0),
	CONSTRAINT "vh_task_ck_2" CHECK (version > 0)
);
--> statement-breakpoint
ALTER TABLE "vh_task" ENABLE ROW LEVEL SECURITY;--> statement-breakpoint
CREATE TABLE "vh_task_dependency" (
	"tenant_id" uuid NOT NULL,
	"project_id" uuid NOT NULL,
	"incident_id" uuid NOT NULL,
	"task_id" uuid NOT NULL,
	"depends_on_task_id" uuid NOT NULL,
	"dependency_type" text NOT NULL,
	"required" boolean NOT NULL,
	"created_at" timestamp with time zone DEFAULT now() NOT NULL,
	CONSTRAINT "vh_task_dependency_tenant_id_task_id_depends_on_task_id_pk" PRIMARY KEY("tenant_id","task_id","depends_on_task_id"),
	CONSTRAINT "vh_task_dependency_dependency_type_ck" CHECK ("vh_task_dependency"."dependency_type" in ('FINISH_TO_START', 'FINISH_TO_FINISH')),
	CONSTRAINT "vh_task_dependency_ck_0" CHECK (task_id <> depends_on_task_id)
);
--> statement-breakpoint
ALTER TABLE "vh_task_dependency" ENABLE ROW LEVEL SECURITY;--> statement-breakpoint
CREATE TABLE "vh_work_order" (
	"id" uuid PRIMARY KEY DEFAULT gen_random_uuid() NOT NULL,
	"tenant_id" uuid NOT NULL,
	"project_id" uuid NOT NULL,
	"incident_id" uuid NOT NULL,
	"task_id" uuid NOT NULL,
	"action_request_id" uuid NOT NULL,
	"executor_type" text NOT NULL,
	"executor_id" text,
	"status" text NOT NULL,
	"attempt_no" integer NOT NULL,
	"redo_of_work_order_id" uuid,
	"checklist_version_id" uuid,
	"execution_started_at" timestamp with time zone,
	"execution_completed_at" timestamp with time zone,
	"result" jsonb NOT NULL,
	"created_at" timestamp with time zone DEFAULT now() NOT NULL,
	"version" bigint DEFAULT 1 NOT NULL,
	"updated_at" timestamp with time zone DEFAULT now() NOT NULL,
	CONSTRAINT "vh_work_order_uq_0" UNIQUE("tenant_id","task_id","attempt_no"),
	CONSTRAINT "vh_work_order_uq_1" UNIQUE("tenant_id","redo_of_work_order_id"),
	CONSTRAINT "vh_work_order_uq_2" UNIQUE("tenant_id","id"),
	CONSTRAINT "vh_work_order_uq_3" UNIQUE("tenant_id","project_id","id"),
	CONSTRAINT "vh_work_order_uq_4" UNIQUE("tenant_id","project_id","incident_id","task_id","id"),
	CONSTRAINT "vh_work_order_executor_type_ck" CHECK ("vh_work_order"."executor_type" in ('HUMAN', 'SYSTEM', 'AUTOMATION', 'EXTERNAL_SERVICE')),
	CONSTRAINT "vh_work_order_status_ck" CHECK ("vh_work_order"."status" in ('OPEN', 'ASSIGNED', 'IN_PROGRESS', 'COMPLETED', 'FAILED', 'CANCELLED')),
	CONSTRAINT "vh_work_order_ck_0" CHECK (attempt_no > 0),
	CONSTRAINT "vh_work_order_ck_1" CHECK (redo_of_work_order_id IS NULL OR redo_of_work_order_id <> id),
	CONSTRAINT "vh_work_order_ck_2" CHECK (execution_completed_at IS NULL OR execution_completed_at >= execution_started_at),
	CONSTRAINT "vh_work_order_ck_3" CHECK (version > 0)
);
--> statement-breakpoint
ALTER TABLE "vh_work_order" ENABLE ROW LEVEL SECURITY;--> statement-breakpoint
CREATE TABLE "vh_apartment" (
	"id" uuid PRIMARY KEY DEFAULT gen_random_uuid() NOT NULL,
	"tenant_id" uuid NOT NULL,
	"project_id" uuid NOT NULL,
	"tower_id" uuid NOT NULL,
	"code" text NOT NULL,
	"floor" integer NOT NULL,
	"status" text NOT NULL,
	"created_at" timestamp with time zone DEFAULT now() NOT NULL,
	"version" bigint DEFAULT 1 NOT NULL,
	"updated_at" timestamp with time zone DEFAULT now() NOT NULL,
	CONSTRAINT "vh_apartment_uq_0" UNIQUE("tenant_id","tower_id","code"),
	CONSTRAINT "vh_apartment_uq_1" UNIQUE("tenant_id","id"),
	CONSTRAINT "vh_apartment_uq_2" UNIQUE("tenant_id","project_id","id"),
	CONSTRAINT "vh_apartment_uq_3" UNIQUE("tenant_id","project_id","tower_id","id"),
	CONSTRAINT "vh_apartment_status_ck" CHECK ("vh_apartment"."status" in ('ACTIVE', 'VACANT', 'RETIRED')),
	CONSTRAINT "vh_apartment_ck_0" CHECK (version > 0)
);
--> statement-breakpoint
ALTER TABLE "vh_apartment" ENABLE ROW LEVEL SECURITY;--> statement-breakpoint
CREATE TABLE "vh_membership_application" (
	"id" uuid PRIMARY KEY DEFAULT gen_random_uuid() NOT NULL,
	"tenant_id" uuid NOT NULL,
	"project_id" uuid NOT NULL,
	"requested_apartment_id" uuid NOT NULL,
	"applicant_user_id" text NOT NULL,
	"requested_role" text NOT NULL,
	"status" text NOT NULL,
	"reviewed_by" text,
	"reviewed_at" timestamp with time zone,
	"decision_note" text,
	"created_at" timestamp with time zone DEFAULT now() NOT NULL,
	"version" bigint DEFAULT 1 NOT NULL,
	"updated_at" timestamp with time zone DEFAULT now() NOT NULL,
	CONSTRAINT "vh_membership_application_uq_0" UNIQUE("tenant_id","id"),
	CONSTRAINT "vh_membership_application_uq_1" UNIQUE("tenant_id","project_id","id"),
	CONSTRAINT "vh_membership_application_requested_role_ck" CHECK ("vh_membership_application"."requested_role" in ('OWNER', 'TENANT', 'HOUSEHOLD')),
	CONSTRAINT "vh_membership_application_status_ck" CHECK ("vh_membership_application"."status" in ('PENDING', 'APPROVED', 'REJECTED', 'WITHDRAWN')),
	CONSTRAINT "vh_membership_application_ck_0" CHECK (version > 0)
);
--> statement-breakpoint
ALTER TABLE "vh_membership_application" ENABLE ROW LEVEL SECURITY;--> statement-breakpoint
CREATE TABLE "vh_project" (
	"id" uuid PRIMARY KEY DEFAULT gen_random_uuid() NOT NULL,
	"tenant_id" uuid NOT NULL,
	"code" text NOT NULL,
	"name" text NOT NULL,
	"status" text NOT NULL,
	"created_at" timestamp with time zone DEFAULT now() NOT NULL,
	"version" bigint DEFAULT 1 NOT NULL,
	"updated_at" timestamp with time zone DEFAULT now() NOT NULL,
	CONSTRAINT "vh_project_uq_0" UNIQUE("tenant_id","code"),
	CONSTRAINT "vh_project_uq_1" UNIQUE("tenant_id","id"),
	CONSTRAINT "vh_project_status_ck" CHECK ("vh_project"."status" in ('ACTIVE', 'SUSPENDED', 'RETIRED')),
	CONSTRAINT "vh_project_ck_0" CHECK (version > 0)
);
--> statement-breakpoint
ALTER TABLE "vh_project" ENABLE ROW LEVEL SECURITY;--> statement-breakpoint
CREATE TABLE "vh_property_membership" (
	"id" uuid PRIMARY KEY DEFAULT gen_random_uuid() NOT NULL,
	"tenant_id" uuid NOT NULL,
	"project_id" uuid NOT NULL,
	"user_id" text NOT NULL,
	"tower_id" uuid,
	"apartment_id" uuid,
	"membership_type" text NOT NULL,
	"resident_role" text,
	"granted_by_user_id" text NOT NULL,
	"valid_from" timestamp with time zone NOT NULL,
	"valid_until" timestamp with time zone,
	"revoked_at" timestamp with time zone,
	"status" text NOT NULL,
	"created_at" timestamp with time zone DEFAULT now() NOT NULL,
	"version" bigint DEFAULT 1 NOT NULL,
	"updated_at" timestamp with time zone DEFAULT now() NOT NULL,
	CONSTRAINT "vh_property_membership_uq_0" UNIQUE("tenant_id","id"),
	CONSTRAINT "vh_property_membership_uq_1" UNIQUE("tenant_id","project_id","id"),
	CONSTRAINT "vh_property_membership_uq_2" UNIQUE("tenant_id","project_id","apartment_id","id"),
	CONSTRAINT "vh_property_membership_uq_3" UNIQUE("tenant_id","project_id","user_id","id"),
	CONSTRAINT "vh_property_membership_membership_type_ck" CHECK ("vh_property_membership"."membership_type" in ('RESIDENT', 'MANAGER', 'STAFF', 'CONTRACTOR')),
	CONSTRAINT "vh_property_membership_resident_role_ck" CHECK ("vh_property_membership"."resident_role" in ('OWNER', 'TENANT', 'HOUSEHOLD')),
	CONSTRAINT "vh_property_membership_status_ck" CHECK ("vh_property_membership"."status" in ('ACTIVE', 'SUSPENDED', 'REVOKED')),
	CONSTRAINT "vh_property_membership_ck_0" CHECK (valid_until IS NULL OR valid_until > valid_from),
	CONSTRAINT "vh_property_membership_ck_1" CHECK ((membership_type = 'RESIDENT' AND apartment_id IS NOT NULL AND resident_role IS NOT NULL) OR (membership_type <> 'RESIDENT' AND resident_role IS NULL)),
	CONSTRAINT "vh_property_membership_ck_2" CHECK (apartment_id IS NULL OR tower_id IS NOT NULL),
	CONSTRAINT "vh_property_membership_ck_3" CHECK (status <> 'REVOKED' OR revoked_at IS NOT NULL),
	CONSTRAINT "vh_property_membership_ck_4" CHECK (version > 0)
);
--> statement-breakpoint
ALTER TABLE "vh_property_membership" ENABLE ROW LEVEL SECURITY;--> statement-breakpoint
CREATE TABLE "vh_tower" (
	"id" uuid PRIMARY KEY DEFAULT gen_random_uuid() NOT NULL,
	"tenant_id" uuid NOT NULL,
	"project_id" uuid NOT NULL,
	"code" text NOT NULL,
	"name" text NOT NULL,
	"status" text NOT NULL,
	"created_at" timestamp with time zone DEFAULT now() NOT NULL,
	"version" bigint DEFAULT 1 NOT NULL,
	"updated_at" timestamp with time zone DEFAULT now() NOT NULL,
	CONSTRAINT "vh_tower_uq_0" UNIQUE("tenant_id","project_id","code"),
	CONSTRAINT "vh_tower_uq_1" UNIQUE("tenant_id","id"),
	CONSTRAINT "vh_tower_uq_2" UNIQUE("tenant_id","project_id","id"),
	CONSTRAINT "vh_tower_status_ck" CHECK ("vh_tower"."status" in ('ACTIVE', 'RETIRED')),
	CONSTRAINT "vh_tower_ck_0" CHECK (version > 0)
);
--> statement-breakpoint
ALTER TABLE "vh_tower" ENABLE ROW LEVEL SECURITY;--> statement-breakpoint
CREATE TABLE "vh_access_card" (
	"id" uuid PRIMARY KEY DEFAULT gen_random_uuid() NOT NULL,
	"tenant_id" uuid NOT NULL,
	"project_id" uuid NOT NULL,
	"membership_id" uuid NOT NULL,
	"card_token_ref" text NOT NULL,
	"issued_at" timestamp with time zone,
	"expires_at" timestamp with time zone,
	"status" text NOT NULL,
	"created_at" timestamp with time zone DEFAULT now() NOT NULL,
	"version" bigint DEFAULT 1 NOT NULL,
	"updated_at" timestamp with time zone DEFAULT now() NOT NULL,
	CONSTRAINT "vh_access_card_uq_0" UNIQUE("card_token_ref"),
	CONSTRAINT "vh_access_card_uq_1" UNIQUE("tenant_id","id"),
	CONSTRAINT "vh_access_card_uq_2" UNIQUE("tenant_id","project_id","id"),
	CONSTRAINT "vh_access_card_status_ck" CHECK ("vh_access_card"."status" in ('REQUESTED', 'ACTIVE', 'SUSPENDED', 'REVOKED')),
	CONSTRAINT "vh_access_card_ck_0" CHECK (version > 0)
);
--> statement-breakpoint
ALTER TABLE "vh_access_card" ENABLE ROW LEVEL SECURITY;--> statement-breakpoint
CREATE TABLE "vh_camera_request" (
	"id" uuid PRIMARY KEY DEFAULT gen_random_uuid() NOT NULL,
	"tenant_id" uuid NOT NULL,
	"project_id" uuid NOT NULL,
	"apartment_id" uuid NOT NULL,
	"requester_membership_id" uuid NOT NULL,
	"location_place_id" uuid NOT NULL,
	"from_at" timestamp with time zone NOT NULL,
	"to_at" timestamp with time zone NOT NULL,
	"purpose" text NOT NULL,
	"status" text NOT NULL,
	"reviewed_by" text,
	"expires_at" timestamp with time zone,
	"created_at" timestamp with time zone DEFAULT now() NOT NULL,
	"version" bigint DEFAULT 1 NOT NULL,
	"updated_at" timestamp with time zone DEFAULT now() NOT NULL,
	CONSTRAINT "vh_camera_request_uq_0" UNIQUE("tenant_id","id"),
	CONSTRAINT "vh_camera_request_uq_1" UNIQUE("tenant_id","project_id","id"),
	CONSTRAINT "vh_camera_request_status_ck" CHECK ("vh_camera_request"."status" in ('SUBMITTED', 'APPROVED', 'REJECTED', 'FULFILLED', 'EXPIRED')),
	CONSTRAINT "vh_camera_request_ck_0" CHECK (to_at > from_at),
	CONSTRAINT "vh_camera_request_ck_1" CHECK (version > 0)
);
--> statement-breakpoint
ALTER TABLE "vh_camera_request" ENABLE ROW LEVEL SECURITY;--> statement-breakpoint
CREATE TABLE "vh_charging_session" (
	"id" uuid PRIMARY KEY DEFAULT gen_random_uuid() NOT NULL,
	"tenant_id" uuid NOT NULL,
	"project_id" uuid NOT NULL,
	"apartment_id" uuid NOT NULL,
	"requested_by_membership_id" uuid NOT NULL,
	"station_place_id" uuid NOT NULL,
	"connector_code" text NOT NULL,
	"started_at" timestamp with time zone,
	"ended_at" timestamp with time zone,
	"energy_wh" bigint,
	"amount_minor" bigint,
	"currency" char(3) NOT NULL,
	"provider_ref" text,
	"status" text NOT NULL,
	"created_at" timestamp with time zone DEFAULT now() NOT NULL,
	"version" bigint DEFAULT 1 NOT NULL,
	"updated_at" timestamp with time zone DEFAULT now() NOT NULL,
	CONSTRAINT "vh_charging_session_uq_0" UNIQUE("provider_ref"),
	CONSTRAINT "vh_charging_session_uq_1" UNIQUE("tenant_id","id"),
	CONSTRAINT "vh_charging_session_uq_2" UNIQUE("tenant_id","project_id","id"),
	CONSTRAINT "vh_charging_session_status_ck" CHECK ("vh_charging_session"."status" in ('REQUESTED', 'ACTIVE', 'COMPLETED', 'FAILED', 'CANCELLED')),
	CONSTRAINT "vh_charging_session_ck_0" CHECK (energy_wh IS NULL OR energy_wh >= 0),
	CONSTRAINT "vh_charging_session_ck_1" CHECK (amount_minor IS NULL OR amount_minor >= 0),
	CONSTRAINT "vh_charging_session_ck_2" CHECK (ended_at IS NULL OR ended_at >= started_at),
	CONSTRAINT "vh_charging_session_ck_3" CHECK (currency ~ '^[A-Z]{3}$'),
	CONSTRAINT "vh_charging_session_ck_4" CHECK (version > 0)
);
--> statement-breakpoint
ALTER TABLE "vh_charging_session" ENABLE ROW LEVEL SECURITY;--> statement-breakpoint
CREATE TABLE "vh_construction_permit" (
	"id" uuid PRIMARY KEY DEFAULT gen_random_uuid() NOT NULL,
	"tenant_id" uuid NOT NULL,
	"project_id" uuid NOT NULL,
	"service_request_id" uuid NOT NULL,
	"contractor_name" text NOT NULL,
	"start_date" date NOT NULL,
	"end_date" date NOT NULL,
	"permitted_hours_json" jsonb NOT NULL,
	"status" text NOT NULL,
	"created_at" timestamp with time zone DEFAULT now() NOT NULL,
	"version" bigint DEFAULT 1 NOT NULL,
	"updated_at" timestamp with time zone DEFAULT now() NOT NULL,
	CONSTRAINT "vh_construction_permit_uq_0" UNIQUE("tenant_id","service_request_id"),
	CONSTRAINT "vh_construction_permit_uq_1" UNIQUE("tenant_id","id"),
	CONSTRAINT "vh_construction_permit_uq_2" UNIQUE("tenant_id","project_id","id"),
	CONSTRAINT "vh_construction_permit_status_ck" CHECK ("vh_construction_permit"."status" in ('PENDING', 'APPROVED', 'REJECTED', 'EXPIRED', 'REVOKED')),
	CONSTRAINT "vh_construction_permit_ck_0" CHECK (end_date >= start_date),
	CONSTRAINT "vh_construction_permit_ck_1" CHECK (version > 0)
);
--> statement-breakpoint
ALTER TABLE "vh_construction_permit" ENABLE ROW LEVEL SECURITY;--> statement-breakpoint
CREATE TABLE "vh_face_enrollment" (
	"id" uuid PRIMARY KEY DEFAULT gen_random_uuid() NOT NULL,
	"tenant_id" uuid NOT NULL,
	"project_id" uuid NOT NULL,
	"membership_id" uuid NOT NULL,
	"consent_version" text NOT NULL,
	"consented_at" timestamp with time zone NOT NULL,
	"provider_subject_ref" text,
	"status" text NOT NULL,
	"revoked_at" timestamp with time zone,
	"deletion_requested_at" timestamp with time zone,
	"deletion_confirmed_at" timestamp with time zone,
	"created_at" timestamp with time zone DEFAULT now() NOT NULL,
	"version" bigint DEFAULT 1 NOT NULL,
	"updated_at" timestamp with time zone DEFAULT now() NOT NULL,
	CONSTRAINT "vh_face_enrollment_uq_0" UNIQUE("tenant_id","id"),
	CONSTRAINT "vh_face_enrollment_uq_1" UNIQUE("tenant_id","project_id","id"),
	CONSTRAINT "vh_face_enrollment_status_ck" CHECK ("vh_face_enrollment"."status" in ('PENDING', 'ACTIVE', 'REJECTED', 'REVOKED')),
	CONSTRAINT "vh_face_enrollment_ck_0" CHECK (version > 0)
);
--> statement-breakpoint
ALTER TABLE "vh_face_enrollment" ENABLE ROW LEVEL SECURITY;--> statement-breakpoint
CREATE TABLE "vh_handover" (
	"id" uuid PRIMARY KEY DEFAULT gen_random_uuid() NOT NULL,
	"tenant_id" uuid NOT NULL,
	"project_id" uuid NOT NULL,
	"apartment_id" uuid NOT NULL,
	"resident_membership_id" uuid NOT NULL,
	"scheduled_at" timestamp with time zone NOT NULL,
	"completed_at" timestamp with time zone,
	"checklist_version_id" uuid,
	"status" text NOT NULL,
	"note" text,
	"created_at" timestamp with time zone DEFAULT now() NOT NULL,
	"version" bigint DEFAULT 1 NOT NULL,
	"updated_at" timestamp with time zone DEFAULT now() NOT NULL,
	CONSTRAINT "vh_handover_uq_0" UNIQUE("tenant_id","id"),
	CONSTRAINT "vh_handover_uq_1" UNIQUE("tenant_id","project_id","id"),
	CONSTRAINT "vh_handover_status_ck" CHECK ("vh_handover"."status" in ('SCHEDULED', 'CONFIRMED', 'COMPLETED', 'CANCELLED')),
	CONSTRAINT "vh_handover_ck_0" CHECK (version > 0)
);
--> statement-breakpoint
ALTER TABLE "vh_handover" ENABLE ROW LEVEL SECURITY;--> statement-breakpoint
CREATE TABLE "vh_intercom_event" (
	"id" uuid PRIMARY KEY DEFAULT gen_random_uuid() NOT NULL,
	"tenant_id" uuid NOT NULL,
	"project_id" uuid NOT NULL,
	"apartment_id" uuid NOT NULL,
	"visitor_pass_id" uuid,
	"provider_event_id" text NOT NULL,
	"event_type" text NOT NULL,
	"occurred_at" timestamp with time zone NOT NULL,
	"outcome" text NOT NULL,
	"created_at" timestamp with time zone DEFAULT now() NOT NULL,
	CONSTRAINT "vh_intercom_event_uq_0" UNIQUE("tenant_id","provider_event_id"),
	CONSTRAINT "vh_intercom_event_uq_1" UNIQUE("tenant_id","id"),
	CONSTRAINT "vh_intercom_event_uq_2" UNIQUE("tenant_id","project_id","id")
);
--> statement-breakpoint
ALTER TABLE "vh_intercom_event" ENABLE ROW LEVEL SECURITY;--> statement-breakpoint
CREATE TABLE "vh_parking_permit" (
	"id" uuid PRIMARY KEY DEFAULT gen_random_uuid() NOT NULL,
	"tenant_id" uuid NOT NULL,
	"project_id" uuid NOT NULL,
	"apartment_id" uuid NOT NULL,
	"membership_id" uuid NOT NULL,
	"vehicle_plate" text NOT NULL,
	"vehicle_type" text NOT NULL,
	"valid_from" timestamp with time zone NOT NULL,
	"valid_until" timestamp with time zone,
	"status" text NOT NULL,
	"created_at" timestamp with time zone DEFAULT now() NOT NULL,
	"version" bigint DEFAULT 1 NOT NULL,
	"updated_at" timestamp with time zone DEFAULT now() NOT NULL,
	CONSTRAINT "vh_parking_permit_uq_0" UNIQUE("tenant_id","id"),
	CONSTRAINT "vh_parking_permit_uq_1" UNIQUE("tenant_id","project_id","id"),
	CONSTRAINT "vh_parking_permit_status_ck" CHECK ("vh_parking_permit"."status" in ('PENDING', 'ACTIVE', 'SUSPENDED', 'EXPIRED', 'REVOKED')),
	CONSTRAINT "vh_parking_permit_ck_0" CHECK (valid_until IS NULL OR valid_until > valid_from),
	CONSTRAINT "vh_parking_permit_ck_1" CHECK (version > 0)
);
--> statement-breakpoint
ALTER TABLE "vh_parking_permit" ENABLE ROW LEVEL SECURITY;--> statement-breakpoint
CREATE TABLE "vh_pet_profile" (
	"id" uuid PRIMARY KEY DEFAULT gen_random_uuid() NOT NULL,
	"tenant_id" uuid NOT NULL,
	"project_id" uuid NOT NULL,
	"apartment_id" uuid NOT NULL,
	"owner_membership_id" uuid NOT NULL,
	"name" text NOT NULL,
	"species" text NOT NULL,
	"breed" text,
	"vaccination_valid_until" date,
	"status" text NOT NULL,
	"created_at" timestamp with time zone DEFAULT now() NOT NULL,
	"version" bigint DEFAULT 1 NOT NULL,
	"updated_at" timestamp with time zone DEFAULT now() NOT NULL,
	CONSTRAINT "vh_pet_profile_uq_0" UNIQUE("tenant_id","id"),
	CONSTRAINT "vh_pet_profile_uq_1" UNIQUE("tenant_id","project_id","id"),
	CONSTRAINT "vh_pet_profile_status_ck" CHECK ("vh_pet_profile"."status" in ('PENDING', 'REGISTERED', 'REJECTED', 'ARCHIVED')),
	CONSTRAINT "vh_pet_profile_ck_0" CHECK (version > 0)
);
--> statement-breakpoint
ALTER TABLE "vh_pet_profile" ENABLE ROW LEVEL SECURITY;--> statement-breakpoint
CREATE TABLE "vh_service_request" (
	"id" uuid PRIMARY KEY DEFAULT gen_random_uuid() NOT NULL,
	"tenant_id" uuid NOT NULL,
	"project_id" uuid NOT NULL,
	"apartment_id" uuid NOT NULL,
	"requester_membership_id" uuid NOT NULL,
	"service_type" text NOT NULL,
	"requested_start_at" timestamp with time zone NOT NULL,
	"requested_end_at" timestamp with time zone,
	"details_json" jsonb NOT NULL,
	"details_schema_version" integer NOT NULL,
	"status" text NOT NULL,
	"decision_reason" text,
	"created_at" timestamp with time zone DEFAULT now() NOT NULL,
	"version" bigint DEFAULT 1 NOT NULL,
	"updated_at" timestamp with time zone DEFAULT now() NOT NULL,
	CONSTRAINT "vh_service_request_uq_0" UNIQUE("tenant_id","id"),
	CONSTRAINT "vh_service_request_uq_1" UNIQUE("tenant_id","project_id","id"),
	CONSTRAINT "vh_service_request_status_ck" CHECK ("vh_service_request"."status" in ('DRAFT', 'SUBMITTED', 'APPROVED', 'REJECTED', 'IN_PROGRESS', 'COMPLETED', 'CANCELLED')),
	CONSTRAINT "vh_service_request_ck_0" CHECK (details_schema_version > 0),
	CONSTRAINT "vh_service_request_ck_1" CHECK (requested_end_at IS NULL OR requested_end_at > requested_start_at),
	CONSTRAINT "vh_service_request_ck_2" CHECK (version > 0)
);
--> statement-breakpoint
ALTER TABLE "vh_service_request" ENABLE ROW LEVEL SECURITY;--> statement-breakpoint
CREATE TABLE "vh_visitor_pass" (
	"id" uuid PRIMARY KEY DEFAULT gen_random_uuid() NOT NULL,
	"tenant_id" uuid NOT NULL,
	"project_id" uuid NOT NULL,
	"service_request_id" uuid NOT NULL,
	"visitor_name" text NOT NULL,
	"vehicle_plate" text,
	"valid_from" timestamp with time zone NOT NULL,
	"valid_until" timestamp with time zone NOT NULL,
	"pass_token_ref" text,
	"status" text NOT NULL,
	"created_at" timestamp with time zone DEFAULT now() NOT NULL,
	"version" bigint DEFAULT 1 NOT NULL,
	"updated_at" timestamp with time zone DEFAULT now() NOT NULL,
	CONSTRAINT "vh_visitor_pass_uq_0" UNIQUE("tenant_id","service_request_id"),
	CONSTRAINT "vh_visitor_pass_uq_1" UNIQUE("pass_token_ref"),
	CONSTRAINT "vh_visitor_pass_uq_2" UNIQUE("tenant_id","id"),
	CONSTRAINT "vh_visitor_pass_uq_3" UNIQUE("tenant_id","project_id","id"),
	CONSTRAINT "vh_visitor_pass_status_ck" CHECK ("vh_visitor_pass"."status" in ('REQUESTED', 'ACTIVE', 'EXPIRED', 'REVOKED')),
	CONSTRAINT "vh_visitor_pass_ck_0" CHECK (valid_until > valid_from),
	CONSTRAINT "vh_visitor_pass_ck_1" CHECK (version > 0)
);
--> statement-breakpoint
ALTER TABLE "vh_visitor_pass" ENABLE ROW LEVEL SECURITY;--> statement-breakpoint
CREATE TABLE "platform_agent" (
	"id" uuid PRIMARY KEY DEFAULT gen_random_uuid() NOT NULL,
	"tenant_id" uuid NOT NULL,
	"name" text NOT NULL,
	"slug" text NOT NULL,
	"description" text,
	"owner_type" text NOT NULL,
	"owner_id" text NOT NULL,
	"domain_namespace" text,
	"status" text NOT NULL,
	"created_at" timestamp with time zone DEFAULT now() NOT NULL,
	"version" bigint DEFAULT 1 NOT NULL,
	"updated_at" timestamp with time zone DEFAULT now() NOT NULL,
	CONSTRAINT "platform_agent_uq_0" UNIQUE("tenant_id","slug"),
	CONSTRAINT "platform_agent_uq_1" UNIQUE("tenant_id","id"),
	CONSTRAINT "platform_agent_owner_type_ck" CHECK ("platform_agent"."owner_type" in ('USER', 'TEAM', 'SYSTEM')),
	CONSTRAINT "platform_agent_status_ck" CHECK ("platform_agent"."status" in ('ACTIVE', 'SUSPENDED', 'RETIRED')),
	CONSTRAINT "platform_agent_ck_0" CHECK (version > 0)
);
--> statement-breakpoint
ALTER TABLE "platform_agent" ENABLE ROW LEVEL SECURITY;--> statement-breakpoint
CREATE TABLE "platform_agent_change_request" (
	"id" uuid PRIMARY KEY DEFAULT gen_random_uuid() NOT NULL,
	"tenant_id" uuid NOT NULL,
	"agent_id" uuid NOT NULL,
	"requested_by" text NOT NULL,
	"request_type" text NOT NULL,
	"description" text NOT NULL,
	"status" text NOT NULL,
	"created_at" timestamp with time zone DEFAULT now() NOT NULL,
	"version" bigint DEFAULT 1 NOT NULL,
	"updated_at" timestamp with time zone DEFAULT now() NOT NULL,
	CONSTRAINT "platform_agent_change_request_uq_0" UNIQUE("tenant_id","id"),
	CONSTRAINT "platform_agent_change_request_status_ck" CHECK ("platform_agent_change_request"."status" in ('OPEN', 'ACCEPTED', 'REJECTED', 'IMPLEMENTED')),
	CONSTRAINT "platform_agent_change_request_ck_0" CHECK (version > 0)
);
--> statement-breakpoint
ALTER TABLE "platform_agent_change_request" ENABLE ROW LEVEL SECURITY;--> statement-breakpoint
CREATE TABLE "platform_agent_spec" (
	"id" uuid PRIMARY KEY DEFAULT gen_random_uuid() NOT NULL,
	"tenant_id" uuid NOT NULL,
	"agent_version_id" uuid NOT NULL,
	"schema_version" integer NOT NULL,
	"goal" text NOT NULL,
	"instructions" text NOT NULL,
	"input_schema" jsonb NOT NULL,
	"output_schema" jsonb NOT NULL,
	"runtime_profile" text NOT NULL,
	"risk_level" text NOT NULL,
	"spec_json" jsonb NOT NULL,
	"created_at" timestamp with time zone DEFAULT now() NOT NULL,
	"version" bigint DEFAULT 1 NOT NULL,
	"updated_at" timestamp with time zone DEFAULT now() NOT NULL,
	CONSTRAINT "platform_agent_spec_uq_0" UNIQUE("tenant_id","agent_version_id"),
	CONSTRAINT "platform_agent_spec_uq_1" UNIQUE("tenant_id","id"),
	CONSTRAINT "platform_agent_spec_risk_level_ck" CHECK ("platform_agent_spec"."risk_level" in ('LOW', 'MEDIUM', 'HIGH', 'CRITICAL')),
	CONSTRAINT "platform_agent_spec_ck_0" CHECK (schema_version > 0),
	CONSTRAINT "platform_agent_spec_ck_1" CHECK (version > 0)
);
--> statement-breakpoint
ALTER TABLE "platform_agent_spec" ENABLE ROW LEVEL SECURITY;--> statement-breakpoint
CREATE TABLE "platform_agent_version" (
	"id" uuid PRIMARY KEY DEFAULT gen_random_uuid() NOT NULL,
	"tenant_id" uuid NOT NULL,
	"agent_id" uuid NOT NULL,
	"version_no" integer NOT NULL,
	"status" text NOT NULL,
	"spec_hash" text NOT NULL,
	"created_by" text NOT NULL,
	"published_at" timestamp with time zone,
	"suspended_at" timestamp with time zone,
	"retired_at" timestamp with time zone,
	"created_at" timestamp with time zone DEFAULT now() NOT NULL,
	"version" bigint DEFAULT 1 NOT NULL,
	"updated_at" timestamp with time zone DEFAULT now() NOT NULL,
	CONSTRAINT "platform_agent_version_uq_0" UNIQUE("tenant_id","agent_id","version_no"),
	CONSTRAINT "platform_agent_version_uq_1" UNIQUE("tenant_id","id"),
	CONSTRAINT "platform_agent_version_uq_2" UNIQUE("tenant_id","agent_id","id"),
	CONSTRAINT "platform_agent_version_status_ck" CHECK ("platform_agent_version"."status" in ('DRAFT', 'NEEDS_INPUT', 'READY_FOR_EVAL', 'EVALUATING', 'READY_FOR_REVIEW', 'READY_FOR_PUBLISH', 'PUBLISHED', 'SUSPENDED', 'RETIRED')),
	CONSTRAINT "platform_agent_version_ck_0" CHECK (version_no > 0),
	CONSTRAINT "platform_agent_version_ck_1" CHECK (version > 0)
);
--> statement-breakpoint
ALTER TABLE "platform_agent_version" ENABLE ROW LEVEL SECURITY;--> statement-breakpoint
CREATE TABLE "platform_audit_event" (
	"id" uuid PRIMARY KEY DEFAULT gen_random_uuid() NOT NULL,
	"tenant_id" uuid NOT NULL,
	"event_type" text NOT NULL,
	"subject_type" text NOT NULL,
	"subject_ref" text NOT NULL,
	"actor_type" text NOT NULL,
	"actor_id" text NOT NULL,
	"actor_version" text,
	"data_json" jsonb NOT NULL,
	"correlation_id" text NOT NULL,
	"trace_id" text NOT NULL,
	"occurred_at" timestamp with time zone NOT NULL,
	"created_at" timestamp with time zone DEFAULT now() NOT NULL,
	CONSTRAINT "platform_audit_event_uq_0" UNIQUE("tenant_id","id"),
	CONSTRAINT "platform_audit_event_actor_type_ck" CHECK ("platform_audit_event"."actor_type" in ('HUMAN', 'SYSTEM', 'AUTOMATION', 'AGENT', 'EXTERNAL_SERVICE'))
);
--> statement-breakpoint
ALTER TABLE "platform_audit_event" ENABLE ROW LEVEL SECURITY;--> statement-breakpoint
CREATE TABLE "platform_idempotency_record" (
	"id" uuid PRIMARY KEY DEFAULT gen_random_uuid() NOT NULL,
	"tenant_id" uuid NOT NULL,
	"idempotency_key" text NOT NULL,
	"operation" text NOT NULL,
	"actor_id" text NOT NULL,
	"request_hash" text NOT NULL,
	"response_json" jsonb,
	"status" text NOT NULL,
	"expires_at" timestamp with time zone NOT NULL,
	"created_at" timestamp with time zone DEFAULT now() NOT NULL,
	"version" bigint DEFAULT 1 NOT NULL,
	"updated_at" timestamp with time zone DEFAULT now() NOT NULL,
	CONSTRAINT "platform_idempotency_record_uq_0" UNIQUE("tenant_id","idempotency_key"),
	CONSTRAINT "platform_idempotency_record_uq_1" UNIQUE("tenant_id","id"),
	CONSTRAINT "platform_idempotency_record_status_ck" CHECK ("platform_idempotency_record"."status" in ('IN_PROGRESS', 'SUCCEEDED', 'FAILED')),
	CONSTRAINT "platform_idempotency_record_ck_0" CHECK (version > 0)
);
--> statement-breakpoint
ALTER TABLE "platform_idempotency_record" ENABLE ROW LEVEL SECURITY;--> statement-breakpoint
CREATE TABLE "platform_outbox_event" (
	"id" uuid PRIMARY KEY DEFAULT gen_random_uuid() NOT NULL,
	"tenant_id" uuid NOT NULL,
	"aggregate_type" text NOT NULL,
	"aggregate_id" text NOT NULL,
	"event_type" text NOT NULL,
	"payload_json" jsonb NOT NULL,
	"status" text NOT NULL,
	"attempt_count" integer NOT NULL,
	"available_at" timestamp with time zone NOT NULL,
	"locked_until" timestamp with time zone,
	"published_at" timestamp with time zone,
	"last_error_code" text,
	"created_at" timestamp with time zone DEFAULT now() NOT NULL,
	"version" bigint DEFAULT 1 NOT NULL,
	"updated_at" timestamp with time zone DEFAULT now() NOT NULL,
	CONSTRAINT "platform_outbox_event_uq_0" UNIQUE("tenant_id","id"),
	CONSTRAINT "platform_outbox_event_status_ck" CHECK ("platform_outbox_event"."status" in ('PENDING', 'PROCESSING', 'PUBLISHED', 'FAILED')),
	CONSTRAINT "platform_outbox_event_ck_0" CHECK (attempt_count >= 0),
	CONSTRAINT "platform_outbox_event_ck_1" CHECK (version > 0)
);
--> statement-breakpoint
ALTER TABLE "platform_outbox_event" ENABLE ROW LEVEL SECURITY;--> statement-breakpoint
CREATE TABLE "platform_agent_capability_binding" (
	"tenant_id" uuid NOT NULL,
	"agent_version_id" uuid NOT NULL,
	"capability_id" uuid NOT NULL,
	"scope_json" jsonb NOT NULL,
	"constraints_json" jsonb NOT NULL,
	"created_at" timestamp with time zone DEFAULT now() NOT NULL,
	CONSTRAINT "platform_agent_capability_binding_tenant_id_agent_version_id_capability_id_pk" PRIMARY KEY("tenant_id","agent_version_id","capability_id")
);
--> statement-breakpoint
ALTER TABLE "platform_agent_capability_binding" ENABLE ROW LEVEL SECURITY;--> statement-breakpoint
CREATE TABLE "platform_agent_knowledge_binding" (
	"tenant_id" uuid NOT NULL,
	"agent_version_id" uuid NOT NULL,
	"knowledge_base_id" uuid NOT NULL,
	"scope_json" jsonb NOT NULL,
	"retrieval_policy_json" jsonb NOT NULL,
	"created_at" timestamp with time zone DEFAULT now() NOT NULL,
	CONSTRAINT "platform_agent_knowledge_binding_tenant_id_agent_version_id_knowledge_base_id_pk" PRIMARY KEY("tenant_id","agent_version_id","knowledge_base_id")
);
--> statement-breakpoint
ALTER TABLE "platform_agent_knowledge_binding" ENABLE ROW LEVEL SECURITY;--> statement-breakpoint
CREATE TABLE "platform_agent_model_binding" (
	"tenant_id" uuid NOT NULL,
	"agent_version_id" uuid NOT NULL,
	"model_profile_id" uuid NOT NULL,
	"constraints_json" jsonb NOT NULL,
	"created_at" timestamp with time zone DEFAULT now() NOT NULL,
	CONSTRAINT "platform_agent_model_binding_tenant_id_agent_version_id_pk" PRIMARY KEY("tenant_id","agent_version_id")
);
--> statement-breakpoint
ALTER TABLE "platform_agent_model_binding" ENABLE ROW LEVEL SECURITY;--> statement-breakpoint
CREATE TABLE "platform_agent_policy_binding" (
	"tenant_id" uuid NOT NULL,
	"agent_version_id" uuid NOT NULL,
	"policy_version_id" uuid NOT NULL,
	"phase" text NOT NULL,
	"config_json" jsonb NOT NULL,
	"created_at" timestamp with time zone DEFAULT now() NOT NULL,
	CONSTRAINT "platform_agent_policy_binding_tenant_id_agent_version_id_policy_version_id_phase_pk" PRIMARY KEY("tenant_id","agent_version_id","policy_version_id","phase"),
	CONSTRAINT "platform_agent_policy_binding_phase_ck" CHECK ("platform_agent_policy_binding"."phase" in ('PRE_RUN', 'PRE_TOOL', 'POST_TOOL', 'OUTPUT'))
);
--> statement-breakpoint
ALTER TABLE "platform_agent_policy_binding" ENABLE ROW LEVEL SECURITY;--> statement-breakpoint
CREATE TABLE "platform_agent_skill_binding" (
	"tenant_id" uuid NOT NULL,
	"agent_version_id" uuid NOT NULL,
	"skill_version_id" uuid NOT NULL,
	"config_json" jsonb NOT NULL,
	"created_at" timestamp with time zone DEFAULT now() NOT NULL,
	CONSTRAINT "platform_agent_skill_binding_tenant_id_agent_version_id_skill_version_id_pk" PRIMARY KEY("tenant_id","agent_version_id","skill_version_id")
);
--> statement-breakpoint
ALTER TABLE "platform_agent_skill_binding" ENABLE ROW LEVEL SECURITY;--> statement-breakpoint
CREATE TABLE "platform_agent_tool_binding" (
	"tenant_id" uuid NOT NULL,
	"agent_version_id" uuid NOT NULL,
	"tool_version_id" uuid NOT NULL,
	"allowed_scope" jsonb NOT NULL,
	"constraints_json" jsonb NOT NULL,
	"approval_policy_ref" text,
	"created_at" timestamp with time zone DEFAULT now() NOT NULL,
	CONSTRAINT "platform_agent_tool_binding_tenant_id_agent_version_id_tool_version_id_pk" PRIMARY KEY("tenant_id","agent_version_id","tool_version_id")
);
--> statement-breakpoint
ALTER TABLE "platform_agent_tool_binding" ENABLE ROW LEVEL SECURITY;--> statement-breakpoint
CREATE TABLE "platform_capability" (
	"id" uuid PRIMARY KEY DEFAULT gen_random_uuid() NOT NULL,
	"tenant_id" uuid NOT NULL,
	"code" text NOT NULL,
	"name" text NOT NULL,
	"type" text NOT NULL,
	"description" text,
	"risk_level" text NOT NULL,
	"owner_id" text NOT NULL,
	"status" text NOT NULL,
	"created_at" timestamp with time zone DEFAULT now() NOT NULL,
	"version" bigint DEFAULT 1 NOT NULL,
	"updated_at" timestamp with time zone DEFAULT now() NOT NULL,
	CONSTRAINT "platform_capability_uq_0" UNIQUE("tenant_id","code"),
	CONSTRAINT "platform_capability_uq_1" UNIQUE("tenant_id","id"),
	CONSTRAINT "platform_capability_risk_level_ck" CHECK ("platform_capability"."risk_level" in ('LOW', 'MEDIUM', 'HIGH', 'CRITICAL')),
	CONSTRAINT "platform_capability_status_ck" CHECK ("platform_capability"."status" in ('ACTIVE', 'SUSPENDED', 'RETIRED')),
	CONSTRAINT "platform_capability_ck_0" CHECK (version > 0)
);
--> statement-breakpoint
ALTER TABLE "platform_capability" ENABLE ROW LEVEL SECURITY;--> statement-breakpoint
CREATE TABLE "platform_mcp_server" (
	"id" uuid PRIMARY KEY DEFAULT gen_random_uuid() NOT NULL,
	"tenant_id" uuid NOT NULL,
	"name" text NOT NULL,
	"endpoint_ref" text NOT NULL,
	"owner_id" text NOT NULL,
	"status" text NOT NULL,
	"created_at" timestamp with time zone DEFAULT now() NOT NULL,
	"version" bigint DEFAULT 1 NOT NULL,
	"updated_at" timestamp with time zone DEFAULT now() NOT NULL,
	CONSTRAINT "platform_mcp_server_uq_0" UNIQUE("tenant_id","id"),
	CONSTRAINT "platform_mcp_server_status_ck" CHECK ("platform_mcp_server"."status" in ('ACTIVE', 'SUSPENDED', 'RETIRED')),
	CONSTRAINT "platform_mcp_server_ck_0" CHECK (version > 0)
);
--> statement-breakpoint
ALTER TABLE "platform_mcp_server" ENABLE ROW LEVEL SECURITY;--> statement-breakpoint
CREATE TABLE "platform_mcp_server_version" (
	"id" uuid PRIMARY KEY DEFAULT gen_random_uuid() NOT NULL,
	"tenant_id" uuid NOT NULL,
	"mcp_server_id" uuid NOT NULL,
	"version_no" integer NOT NULL,
	"schema_hash" text NOT NULL,
	"fingerprint" text NOT NULL,
	"security_status" text NOT NULL,
	"created_at" timestamp with time zone DEFAULT now() NOT NULL,
	"version" bigint DEFAULT 1 NOT NULL,
	"updated_at" timestamp with time zone DEFAULT now() NOT NULL,
	CONSTRAINT "platform_mcp_server_version_uq_0" UNIQUE("tenant_id","mcp_server_id","version_no"),
	CONSTRAINT "platform_mcp_server_version_uq_1" UNIQUE("tenant_id","id"),
	CONSTRAINT "platform_mcp_server_version_security_status_ck" CHECK ("platform_mcp_server_version"."security_status" in ('PENDING', 'APPROVED', 'REJECTED', 'REVOKED')),
	CONSTRAINT "platform_mcp_server_version_ck_0" CHECK (version_no > 0),
	CONSTRAINT "platform_mcp_server_version_ck_1" CHECK (version > 0)
);
--> statement-breakpoint
ALTER TABLE "platform_mcp_server_version" ENABLE ROW LEVEL SECURITY;--> statement-breakpoint
CREATE TABLE "platform_model_profile" (
	"id" uuid PRIMARY KEY DEFAULT gen_random_uuid() NOT NULL,
	"tenant_id" uuid NOT NULL,
	"code" text NOT NULL,
	"provider_ref" text NOT NULL,
	"model_ref" text NOT NULL,
	"config_json" jsonb NOT NULL,
	"status" text NOT NULL,
	"created_at" timestamp with time zone DEFAULT now() NOT NULL,
	"version" bigint DEFAULT 1 NOT NULL,
	"updated_at" timestamp with time zone DEFAULT now() NOT NULL,
	CONSTRAINT "platform_model_profile_uq_0" UNIQUE("tenant_id","code"),
	CONSTRAINT "platform_model_profile_uq_1" UNIQUE("tenant_id","id"),
	CONSTRAINT "platform_model_profile_status_ck" CHECK ("platform_model_profile"."status" in ('ACTIVE', 'SUSPENDED', 'RETIRED')),
	CONSTRAINT "platform_model_profile_ck_0" CHECK (version > 0)
);
--> statement-breakpoint
ALTER TABLE "platform_model_profile" ENABLE ROW LEVEL SECURITY;--> statement-breakpoint
CREATE TABLE "platform_skill" (
	"id" uuid PRIMARY KEY DEFAULT gen_random_uuid() NOT NULL,
	"tenant_id" uuid NOT NULL,
	"name" text NOT NULL,
	"owner_id" text NOT NULL,
	"status" text NOT NULL,
	"created_at" timestamp with time zone DEFAULT now() NOT NULL,
	"version" bigint DEFAULT 1 NOT NULL,
	"updated_at" timestamp with time zone DEFAULT now() NOT NULL,
	CONSTRAINT "platform_skill_uq_0" UNIQUE("tenant_id","id"),
	CONSTRAINT "platform_skill_status_ck" CHECK ("platform_skill"."status" in ('ACTIVE', 'SUSPENDED', 'RETIRED')),
	CONSTRAINT "platform_skill_ck_0" CHECK (version > 0)
);
--> statement-breakpoint
ALTER TABLE "platform_skill" ENABLE ROW LEVEL SECURITY;--> statement-breakpoint
CREATE TABLE "platform_skill_version" (
	"id" uuid PRIMARY KEY DEFAULT gen_random_uuid() NOT NULL,
	"tenant_id" uuid NOT NULL,
	"skill_id" uuid NOT NULL,
	"version_no" integer NOT NULL,
	"content_ref" text NOT NULL,
	"checksum" text NOT NULL,
	"created_at" timestamp with time zone DEFAULT now() NOT NULL,
	CONSTRAINT "platform_skill_version_uq_0" UNIQUE("tenant_id","skill_id","version_no"),
	CONSTRAINT "platform_skill_version_uq_1" UNIQUE("tenant_id","id"),
	CONSTRAINT "platform_skill_version_ck_0" CHECK (version_no > 0)
);
--> statement-breakpoint
ALTER TABLE "platform_skill_version" ENABLE ROW LEVEL SECURITY;--> statement-breakpoint
CREATE TABLE "platform_tool" (
	"id" uuid PRIMARY KEY DEFAULT gen_random_uuid() NOT NULL,
	"tenant_id" uuid NOT NULL,
	"code" text NOT NULL,
	"name" text NOT NULL,
	"effect_type" text NOT NULL,
	"risk_level" text NOT NULL,
	"created_at" timestamp with time zone DEFAULT now() NOT NULL,
	"version" bigint DEFAULT 1 NOT NULL,
	"updated_at" timestamp with time zone DEFAULT now() NOT NULL,
	CONSTRAINT "platform_tool_uq_0" UNIQUE("tenant_id","code"),
	CONSTRAINT "platform_tool_uq_1" UNIQUE("tenant_id","id"),
	CONSTRAINT "platform_tool_effect_type_ck" CHECK ("platform_tool"."effect_type" in ('READ', 'WRITE', 'EXTERNAL_SIDE_EFFECT')),
	CONSTRAINT "platform_tool_risk_level_ck" CHECK ("platform_tool"."risk_level" in ('LOW', 'MEDIUM', 'HIGH', 'CRITICAL')),
	CONSTRAINT "platform_tool_ck_0" CHECK (version > 0)
);
--> statement-breakpoint
ALTER TABLE "platform_tool" ENABLE ROW LEVEL SECURITY;--> statement-breakpoint
CREATE TABLE "platform_tool_version" (
	"id" uuid PRIMARY KEY DEFAULT gen_random_uuid() NOT NULL,
	"tenant_id" uuid NOT NULL,
	"tool_id" uuid NOT NULL,
	"mcp_server_version_id" uuid,
	"version_no" integer NOT NULL,
	"input_schema" jsonb NOT NULL,
	"output_schema" jsonb NOT NULL,
	"fingerprint" text NOT NULL,
	"status" text NOT NULL,
	"created_at" timestamp with time zone DEFAULT now() NOT NULL,
	"version" bigint DEFAULT 1 NOT NULL,
	"updated_at" timestamp with time zone DEFAULT now() NOT NULL,
	CONSTRAINT "platform_tool_version_uq_0" UNIQUE("tenant_id","tool_id","version_no"),
	CONSTRAINT "platform_tool_version_uq_1" UNIQUE("tenant_id","id"),
	CONSTRAINT "platform_tool_version_status_ck" CHECK ("platform_tool_version"."status" in ('DRAFT', 'APPROVED', 'REVOKED')),
	CONSTRAINT "platform_tool_version_ck_0" CHECK (version_no > 0),
	CONSTRAINT "platform_tool_version_ck_1" CHECK (version > 0)
);
--> statement-breakpoint
ALTER TABLE "platform_tool_version" ENABLE ROW LEVEL SECURITY;--> statement-breakpoint
CREATE TABLE "platform_agent_deployment" (
	"id" uuid PRIMARY KEY DEFAULT gen_random_uuid() NOT NULL,
	"tenant_id" uuid NOT NULL,
	"agent_version_id" uuid NOT NULL,
	"domain_installation_id" uuid,
	"environment" text NOT NULL,
	"scope_type" text NOT NULL,
	"scope_ref" text NOT NULL,
	"status" text NOT NULL,
	"deployed_at" timestamp with time zone NOT NULL,
	"retired_at" timestamp with time zone,
	"previous_deployment_id" uuid,
	"created_at" timestamp with time zone DEFAULT now() NOT NULL,
	"version" bigint DEFAULT 1 NOT NULL,
	"updated_at" timestamp with time zone DEFAULT now() NOT NULL,
	CONSTRAINT "platform_agent_deployment_uq_0" UNIQUE("tenant_id","id"),
	CONSTRAINT "platform_agent_deployment_status_ck" CHECK ("platform_agent_deployment"."status" in ('ACTIVE', 'SUSPENDED', 'RETIRED')),
	CONSTRAINT "platform_agent_deployment_ck_0" CHECK (version > 0)
);
--> statement-breakpoint
ALTER TABLE "platform_agent_deployment" ENABLE ROW LEVEL SECURITY;--> statement-breakpoint
CREATE TABLE "platform_domain_installation" (
	"id" uuid PRIMARY KEY DEFAULT gen_random_uuid() NOT NULL,
	"tenant_id" uuid NOT NULL,
	"domain_package_id" uuid NOT NULL,
	"environment" text NOT NULL,
	"config_json" jsonb NOT NULL,
	"status" text NOT NULL,
	"installed_at" timestamp with time zone NOT NULL,
	"created_at" timestamp with time zone DEFAULT now() NOT NULL,
	"version" bigint DEFAULT 1 NOT NULL,
	"updated_at" timestamp with time zone DEFAULT now() NOT NULL,
	CONSTRAINT "platform_domain_installation_uq_0" UNIQUE("tenant_id","domain_package_id","environment"),
	CONSTRAINT "platform_domain_installation_uq_1" UNIQUE("tenant_id","id"),
	CONSTRAINT "platform_domain_installation_status_ck" CHECK ("platform_domain_installation"."status" in ('ENABLED', 'DISABLED')),
	CONSTRAINT "platform_domain_installation_ck_0" CHECK (version > 0)
);
--> statement-breakpoint
ALTER TABLE "platform_domain_installation" ENABLE ROW LEVEL SECURITY;--> statement-breakpoint
CREATE TABLE "platform_domain_package" (
	"id" uuid PRIMARY KEY DEFAULT gen_random_uuid() NOT NULL,
	"namespace" text NOT NULL,
	"name" text NOT NULL,
	"package_version" text NOT NULL,
	"contract_version" text NOT NULL,
	"status" text NOT NULL,
	"metadata_json" jsonb NOT NULL,
	"created_at" timestamp with time zone DEFAULT now() NOT NULL,
	"version" bigint DEFAULT 1 NOT NULL,
	"updated_at" timestamp with time zone DEFAULT now() NOT NULL,
	CONSTRAINT "platform_domain_package_uq_0" UNIQUE("namespace","package_version"),
	CONSTRAINT "platform_domain_package_status_ck" CHECK ("platform_domain_package"."status" in ('ACTIVE', 'DEPRECATED', 'RETIRED')),
	CONSTRAINT "platform_domain_package_ck_0" CHECK (version > 0)
);
--> statement-breakpoint
CREATE TABLE "platform_eval_assertion" (
	"id" uuid PRIMARY KEY DEFAULT gen_random_uuid() NOT NULL,
	"tenant_id" uuid NOT NULL,
	"eval_run_id" uuid NOT NULL,
	"eval_case_id" uuid NOT NULL,
	"assertion_type" text NOT NULL,
	"status" text NOT NULL,
	"score" numeric,
	"expected_json" jsonb NOT NULL,
	"actual_json" jsonb NOT NULL,
	"failure_reason" text,
	"created_at" timestamp with time zone DEFAULT now() NOT NULL,
	CONSTRAINT "platform_eval_assertion_uq_0" UNIQUE("tenant_id","id"),
	CONSTRAINT "platform_eval_assertion_uq_1" UNIQUE("tenant_id","eval_run_id","id"),
	CONSTRAINT "platform_eval_assertion_status_ck" CHECK ("platform_eval_assertion"."status" in ('PASS', 'FAIL', 'ERROR', 'SKIPPED'))
);
--> statement-breakpoint
ALTER TABLE "platform_eval_assertion" ENABLE ROW LEVEL SECURITY;--> statement-breakpoint
CREATE TABLE "platform_eval_case" (
	"id" uuid PRIMARY KEY DEFAULT gen_random_uuid() NOT NULL,
	"tenant_id" uuid NOT NULL,
	"eval_suite_id" uuid NOT NULL,
	"case_code" text NOT NULL,
	"input_json" jsonb NOT NULL,
	"expected_json" jsonb NOT NULL,
	"severity" text NOT NULL,
	"tags" text[] NOT NULL,
	"created_at" timestamp with time zone DEFAULT now() NOT NULL,
	"version" bigint DEFAULT 1 NOT NULL,
	"updated_at" timestamp with time zone DEFAULT now() NOT NULL,
	CONSTRAINT "platform_eval_case_uq_0" UNIQUE("tenant_id","eval_suite_id","case_code"),
	CONSTRAINT "platform_eval_case_uq_1" UNIQUE("tenant_id","id"),
	CONSTRAINT "platform_eval_case_severity_ck" CHECK ("platform_eval_case"."severity" in ('LOW', 'MEDIUM', 'HIGH', 'CRITICAL')),
	CONSTRAINT "platform_eval_case_ck_0" CHECK (version > 0)
);
--> statement-breakpoint
ALTER TABLE "platform_eval_case" ENABLE ROW LEVEL SECURITY;--> statement-breakpoint
CREATE TABLE "platform_eval_evidence" (
	"id" uuid PRIMARY KEY DEFAULT gen_random_uuid() NOT NULL,
	"tenant_id" uuid NOT NULL,
	"eval_run_id" uuid NOT NULL,
	"eval_assertion_id" uuid,
	"evidence_type" text NOT NULL,
	"artifact_ref" text NOT NULL,
	"trace_id" text NOT NULL,
	"created_at" timestamp with time zone DEFAULT now() NOT NULL,
	CONSTRAINT "platform_eval_evidence_uq_0" UNIQUE("tenant_id","id")
);
--> statement-breakpoint
ALTER TABLE "platform_eval_evidence" ENABLE ROW LEVEL SECURITY;--> statement-breakpoint
CREATE TABLE "platform_eval_run" (
	"id" uuid PRIMARY KEY DEFAULT gen_random_uuid() NOT NULL,
	"tenant_id" uuid NOT NULL,
	"agent_version_id" uuid NOT NULL,
	"eval_suite_id" uuid NOT NULL,
	"status" text NOT NULL,
	"environment_snapshot" jsonb NOT NULL,
	"model_snapshot" jsonb NOT NULL,
	"started_at" timestamp with time zone,
	"completed_at" timestamp with time zone,
	"created_at" timestamp with time zone DEFAULT now() NOT NULL,
	"version" bigint DEFAULT 1 NOT NULL,
	"updated_at" timestamp with time zone DEFAULT now() NOT NULL,
	CONSTRAINT "platform_eval_run_uq_0" UNIQUE("tenant_id","id"),
	CONSTRAINT "platform_eval_run_status_ck" CHECK ("platform_eval_run"."status" in ('PENDING', 'RUNNING', 'PASSED', 'FAILED', 'CANCELLED')),
	CONSTRAINT "platform_eval_run_ck_0" CHECK (completed_at IS NULL OR completed_at >= started_at),
	CONSTRAINT "platform_eval_run_ck_1" CHECK (version > 0)
);
--> statement-breakpoint
ALTER TABLE "platform_eval_run" ENABLE ROW LEVEL SECURITY;--> statement-breakpoint
CREATE TABLE "platform_eval_suite" (
	"id" uuid PRIMARY KEY DEFAULT gen_random_uuid() NOT NULL,
	"tenant_id" uuid NOT NULL,
	"name" text NOT NULL,
	"version_no" integer NOT NULL,
	"type" text NOT NULL,
	"owner_id" text NOT NULL,
	"status" text NOT NULL,
	"created_at" timestamp with time zone DEFAULT now() NOT NULL,
	"version" bigint DEFAULT 1 NOT NULL,
	"updated_at" timestamp with time zone DEFAULT now() NOT NULL,
	CONSTRAINT "platform_eval_suite_uq_0" UNIQUE("tenant_id","name","version_no"),
	CONSTRAINT "platform_eval_suite_uq_1" UNIQUE("tenant_id","id"),
	CONSTRAINT "platform_eval_suite_status_ck" CHECK ("platform_eval_suite"."status" in ('DRAFT', 'ACTIVE', 'RETIRED')),
	CONSTRAINT "platform_eval_suite_ck_0" CHECK (version_no > 0),
	CONSTRAINT "platform_eval_suite_ck_1" CHECK (version > 0)
);
--> statement-breakpoint
ALTER TABLE "platform_eval_suite" ENABLE ROW LEVEL SECURITY;--> statement-breakpoint
CREATE TABLE "platform_publish_approval" (
	"id" uuid PRIMARY KEY DEFAULT gen_random_uuid() NOT NULL,
	"tenant_id" uuid NOT NULL,
	"publish_gate_id" uuid NOT NULL,
	"approval_type" text NOT NULL,
	"reviewer_id" text NOT NULL,
	"status" text NOT NULL,
	"reason" text,
	"decided_at" timestamp with time zone NOT NULL,
	"created_at" timestamp with time zone DEFAULT now() NOT NULL,
	CONSTRAINT "platform_publish_approval_uq_0" UNIQUE("tenant_id","publish_gate_id","approval_type"),
	CONSTRAINT "platform_publish_approval_uq_1" UNIQUE("tenant_id","id"),
	CONSTRAINT "platform_publish_approval_approval_type_ck" CHECK ("platform_publish_approval"."approval_type" in ('DOMAIN', 'EVALUATION', 'SECURITY', 'PLATFORM')),
	CONSTRAINT "platform_publish_approval_status_ck" CHECK ("platform_publish_approval"."status" in ('APPROVED', 'REJECTED'))
);
--> statement-breakpoint
ALTER TABLE "platform_publish_approval" ENABLE ROW LEVEL SECURITY;--> statement-breakpoint
CREATE TABLE "platform_publish_gate" (
	"id" uuid PRIMARY KEY DEFAULT gen_random_uuid() NOT NULL,
	"tenant_id" uuid NOT NULL,
	"agent_version_id" uuid NOT NULL,
	"status" text NOT NULL,
	"completed_at" timestamp with time zone,
	"created_at" timestamp with time zone DEFAULT now() NOT NULL,
	"version" bigint DEFAULT 1 NOT NULL,
	"updated_at" timestamp with time zone DEFAULT now() NOT NULL,
	CONSTRAINT "platform_publish_gate_uq_0" UNIQUE("tenant_id","id"),
	CONSTRAINT "platform_publish_gate_status_ck" CHECK ("platform_publish_gate"."status" in ('PENDING', 'PASSED', 'FAILED')),
	CONSTRAINT "platform_publish_gate_ck_0" CHECK (version > 0)
);
--> statement-breakpoint
ALTER TABLE "platform_publish_gate" ENABLE ROW LEVEL SECURITY;--> statement-breakpoint
CREATE TABLE "platform_publish_gate_result" (
	"id" uuid PRIMARY KEY DEFAULT gen_random_uuid() NOT NULL,
	"tenant_id" uuid NOT NULL,
	"publish_gate_id" uuid NOT NULL,
	"gate_type" text NOT NULL,
	"status" text NOT NULL,
	"evidence_ref" text NOT NULL,
	"details_json" jsonb NOT NULL,
	"created_at" timestamp with time zone DEFAULT now() NOT NULL,
	CONSTRAINT "platform_publish_gate_result_uq_0" UNIQUE("tenant_id","publish_gate_id","gate_type"),
	CONSTRAINT "platform_publish_gate_result_uq_1" UNIQUE("tenant_id","id"),
	CONSTRAINT "platform_publish_gate_result_gate_type_ck" CHECK ("platform_publish_gate_result"."gate_type" in ('CONTRACT', 'QUALITY', 'SAFETY', 'REGRESSION')),
	CONSTRAINT "platform_publish_gate_result_status_ck" CHECK ("platform_publish_gate_result"."status" in ('PASS', 'FAIL'))
);
--> statement-breakpoint
ALTER TABLE "platform_publish_gate_result" ENABLE ROW LEVEL SECURITY;--> statement-breakpoint
CREATE TABLE "platform_regression_baseline" (
	"id" uuid PRIMARY KEY DEFAULT gen_random_uuid() NOT NULL,
	"tenant_id" uuid NOT NULL,
	"agent_id" uuid NOT NULL,
	"baseline_agent_version_id" uuid NOT NULL,
	"eval_suite_id" uuid NOT NULL,
	"accepted_by" text NOT NULL,
	"accepted_at" timestamp with time zone NOT NULL,
	"status" text NOT NULL,
	"created_at" timestamp with time zone DEFAULT now() NOT NULL,
	"version" bigint DEFAULT 1 NOT NULL,
	"updated_at" timestamp with time zone DEFAULT now() NOT NULL,
	CONSTRAINT "platform_regression_baseline_uq_0" UNIQUE("tenant_id","id"),
	CONSTRAINT "platform_regression_baseline_status_ck" CHECK ("platform_regression_baseline"."status" in ('ACTIVE', 'RETIRED')),
	CONSTRAINT "platform_regression_baseline_ck_0" CHECK (version > 0)
);
--> statement-breakpoint
ALTER TABLE "platform_regression_baseline" ENABLE ROW LEVEL SECURITY;--> statement-breakpoint
CREATE TABLE "platform_membership_role" (
	"tenant_id" uuid NOT NULL,
	"membership_id" uuid NOT NULL,
	"role_id" uuid NOT NULL,
	"scope_json" jsonb NOT NULL,
	"created_at" timestamp with time zone DEFAULT now() NOT NULL,
	CONSTRAINT "platform_membership_role_tenant_id_membership_id_role_id_pk" PRIMARY KEY("tenant_id","membership_id","role_id")
);
--> statement-breakpoint
ALTER TABLE "platform_membership_role" ENABLE ROW LEVEL SECURITY;--> statement-breakpoint
CREATE TABLE "platform_role" (
	"id" uuid PRIMARY KEY DEFAULT gen_random_uuid() NOT NULL,
	"tenant_id" uuid NOT NULL,
	"code" text NOT NULL,
	"name" text NOT NULL,
	"scope_type" text NOT NULL,
	"created_at" timestamp with time zone DEFAULT now() NOT NULL,
	"version" bigint DEFAULT 1 NOT NULL,
	"updated_at" timestamp with time zone DEFAULT now() NOT NULL,
	CONSTRAINT "platform_role_uq_0" UNIQUE("tenant_id","code"),
	CONSTRAINT "platform_role_uq_1" UNIQUE("tenant_id","id"),
	CONSTRAINT "platform_role_scope_type_ck" CHECK ("platform_role"."scope_type" in ('TENANT', 'DOMAIN', 'PROJECT', 'RESOURCE')),
	CONSTRAINT "platform_role_ck_0" CHECK (version > 0)
);
--> statement-breakpoint
ALTER TABLE "platform_role" ENABLE ROW LEVEL SECURITY;--> statement-breakpoint
CREATE TABLE "platform_tenant" (
	"id" uuid PRIMARY KEY DEFAULT gen_random_uuid() NOT NULL,
	"code" text NOT NULL,
	"name" text NOT NULL,
	"status" text NOT NULL,
	"created_at" timestamp with time zone DEFAULT now() NOT NULL,
	"version" bigint DEFAULT 1 NOT NULL,
	"updated_at" timestamp with time zone DEFAULT now() NOT NULL,
	CONSTRAINT "platform_tenant_uq_0" UNIQUE("code"),
	CONSTRAINT "platform_tenant_status_ck" CHECK ("platform_tenant"."status" in ('ACTIVE', 'SUSPENDED', 'RETIRED')),
	CONSTRAINT "platform_tenant_ck_0" CHECK (version > 0)
);
--> statement-breakpoint
ALTER TABLE "platform_tenant" ENABLE ROW LEVEL SECURITY;--> statement-breakpoint
CREATE TABLE "platform_tenant_membership" (
	"id" uuid PRIMARY KEY DEFAULT gen_random_uuid() NOT NULL,
	"tenant_id" uuid NOT NULL,
	"user_id" text NOT NULL,
	"status" text NOT NULL,
	"valid_from" timestamp with time zone NOT NULL,
	"valid_until" timestamp with time zone,
	"created_at" timestamp with time zone DEFAULT now() NOT NULL,
	"version" bigint DEFAULT 1 NOT NULL,
	"updated_at" timestamp with time zone DEFAULT now() NOT NULL,
	CONSTRAINT "platform_tenant_membership_uq_0" UNIQUE("tenant_id","user_id"),
	CONSTRAINT "platform_tenant_membership_uq_1" UNIQUE("tenant_id","id"),
	CONSTRAINT "platform_tenant_membership_status_ck" CHECK ("platform_tenant_membership"."status" in ('ACTIVE', 'SUSPENDED', 'REVOKED')),
	CONSTRAINT "platform_tenant_membership_ck_0" CHECK (valid_until IS NULL OR valid_until > valid_from),
	CONSTRAINT "platform_tenant_membership_ck_1" CHECK (version > 0)
);
--> statement-breakpoint
ALTER TABLE "platform_tenant_membership" ENABLE ROW LEVEL SECURITY;--> statement-breakpoint
CREATE TABLE "platform_knowledge_base" (
	"id" uuid PRIMARY KEY DEFAULT gen_random_uuid() NOT NULL,
	"tenant_id" uuid NOT NULL,
	"name" text NOT NULL,
	"classification" text NOT NULL,
	"owner_id" text NOT NULL,
	"status" text NOT NULL,
	"created_at" timestamp with time zone DEFAULT now() NOT NULL,
	"version" bigint DEFAULT 1 NOT NULL,
	"updated_at" timestamp with time zone DEFAULT now() NOT NULL,
	CONSTRAINT "platform_knowledge_base_uq_0" UNIQUE("tenant_id","id"),
	CONSTRAINT "platform_knowledge_base_classification_ck" CHECK ("platform_knowledge_base"."classification" in ('PUBLIC', 'INTERNAL', 'CONFIDENTIAL', 'RESTRICTED')),
	CONSTRAINT "platform_knowledge_base_status_ck" CHECK ("platform_knowledge_base"."status" in ('ACTIVE', 'SUSPENDED', 'RETIRED')),
	CONSTRAINT "platform_knowledge_base_ck_0" CHECK (version > 0)
);
--> statement-breakpoint
ALTER TABLE "platform_knowledge_base" ENABLE ROW LEVEL SECURITY;--> statement-breakpoint
CREATE TABLE "platform_knowledge_revision" (
	"id" uuid PRIMARY KEY DEFAULT gen_random_uuid() NOT NULL,
	"tenant_id" uuid NOT NULL,
	"knowledge_source_id" uuid NOT NULL,
	"revision_no" integer NOT NULL,
	"content_hash" text NOT NULL,
	"storage_ref" text NOT NULL,
	"status" text NOT NULL,
	"approved_by" text,
	"approved_at" timestamp with time zone,
	"created_at" timestamp with time zone DEFAULT now() NOT NULL,
	"version" bigint DEFAULT 1 NOT NULL,
	"updated_at" timestamp with time zone DEFAULT now() NOT NULL,
	CONSTRAINT "platform_knowledge_revision_uq_0" UNIQUE("tenant_id","knowledge_source_id","revision_no"),
	CONSTRAINT "platform_knowledge_revision_uq_1" UNIQUE("tenant_id","id"),
	CONSTRAINT "platform_knowledge_revision_status_ck" CHECK ("platform_knowledge_revision"."status" in ('DRAFT', 'APPROVED', 'REJECTED', 'REVOKED')),
	CONSTRAINT "platform_knowledge_revision_ck_0" CHECK (revision_no > 0),
	CONSTRAINT "platform_knowledge_revision_ck_1" CHECK (status <> 'APPROVED' OR (approved_by IS NOT NULL AND approved_at IS NOT NULL)),
	CONSTRAINT "platform_knowledge_revision_ck_2" CHECK (version > 0)
);
--> statement-breakpoint
ALTER TABLE "platform_knowledge_revision" ENABLE ROW LEVEL SECURITY;--> statement-breakpoint
CREATE TABLE "platform_knowledge_source" (
	"id" uuid PRIMARY KEY DEFAULT gen_random_uuid() NOT NULL,
	"tenant_id" uuid NOT NULL,
	"knowledge_base_id" uuid NOT NULL,
	"source_type" text NOT NULL,
	"uri" text NOT NULL,
	"title" text NOT NULL,
	"owner_id" text NOT NULL,
	"created_at" timestamp with time zone DEFAULT now() NOT NULL,
	"version" bigint DEFAULT 1 NOT NULL,
	"updated_at" timestamp with time zone DEFAULT now() NOT NULL,
	CONSTRAINT "platform_knowledge_source_uq_0" UNIQUE("tenant_id","id"),
	CONSTRAINT "platform_knowledge_source_ck_0" CHECK (version > 0)
);
--> statement-breakpoint
ALTER TABLE "platform_knowledge_source" ENABLE ROW LEVEL SECURITY;--> statement-breakpoint
CREATE TABLE "platform_memory_item" (
	"id" uuid PRIMARY KEY DEFAULT gen_random_uuid() NOT NULL,
	"tenant_id" uuid NOT NULL,
	"memory_namespace_id" uuid NOT NULL,
	"memory_type" text NOT NULL,
	"source_type" text NOT NULL,
	"source_ref" text NOT NULL,
	"status" text NOT NULL,
	"created_at" timestamp with time zone DEFAULT now() NOT NULL,
	"version" bigint DEFAULT 1 NOT NULL,
	"updated_at" timestamp with time zone DEFAULT now() NOT NULL,
	CONSTRAINT "platform_memory_item_uq_0" UNIQUE("tenant_id","id"),
	CONSTRAINT "platform_memory_item_status_ck" CHECK ("platform_memory_item"."status" in ('DRAFT', 'ACTIVE', 'REDACTED', 'RETIRED')),
	CONSTRAINT "platform_memory_item_ck_0" CHECK (version > 0)
);
--> statement-breakpoint
ALTER TABLE "platform_memory_item" ENABLE ROW LEVEL SECURITY;--> statement-breakpoint
CREATE TABLE "platform_memory_namespace" (
	"id" uuid PRIMARY KEY DEFAULT gen_random_uuid() NOT NULL,
	"tenant_id" uuid NOT NULL,
	"namespace_type" text NOT NULL,
	"subject_ref" text NOT NULL,
	"retention_policy" jsonb NOT NULL,
	"status" text NOT NULL,
	"created_at" timestamp with time zone DEFAULT now() NOT NULL,
	"version" bigint DEFAULT 1 NOT NULL,
	"updated_at" timestamp with time zone DEFAULT now() NOT NULL,
	CONSTRAINT "platform_memory_namespace_uq_0" UNIQUE("tenant_id","namespace_type","subject_ref"),
	CONSTRAINT "platform_memory_namespace_uq_1" UNIQUE("tenant_id","id"),
	CONSTRAINT "platform_memory_namespace_namespace_type_ck" CHECK ("platform_memory_namespace"."namespace_type" in ('TENANT', 'DOMAIN', 'USER', 'AGENT')),
	CONSTRAINT "platform_memory_namespace_status_ck" CHECK ("platform_memory_namespace"."status" in ('ACTIVE', 'SUSPENDED', 'RETIRED')),
	CONSTRAINT "platform_memory_namespace_ck_0" CHECK (version > 0)
);
--> statement-breakpoint
ALTER TABLE "platform_memory_namespace" ENABLE ROW LEVEL SECURITY;--> statement-breakpoint
CREATE TABLE "platform_memory_review" (
	"id" uuid PRIMARY KEY DEFAULT gen_random_uuid() NOT NULL,
	"tenant_id" uuid NOT NULL,
	"memory_revision_id" uuid NOT NULL,
	"reviewer_id" text NOT NULL,
	"decision" text NOT NULL,
	"reason" text NOT NULL,
	"reviewed_at" timestamp with time zone NOT NULL,
	"created_at" timestamp with time zone DEFAULT now() NOT NULL,
	CONSTRAINT "platform_memory_review_uq_0" UNIQUE("tenant_id","id"),
	CONSTRAINT "platform_memory_review_decision_ck" CHECK ("platform_memory_review"."decision" in ('APPROVED', 'REJECTED', 'REVOKED'))
);
--> statement-breakpoint
ALTER TABLE "platform_memory_review" ENABLE ROW LEVEL SECURITY;--> statement-breakpoint
CREATE TABLE "platform_memory_revision" (
	"id" uuid PRIMARY KEY DEFAULT gen_random_uuid() NOT NULL,
	"tenant_id" uuid NOT NULL,
	"memory_item_id" uuid NOT NULL,
	"revision_no" integer NOT NULL,
	"content_ref" text NOT NULL,
	"content_hash" text NOT NULL,
	"redaction_status" text NOT NULL,
	"created_at" timestamp with time zone DEFAULT now() NOT NULL,
	CONSTRAINT "platform_memory_revision_uq_0" UNIQUE("tenant_id","memory_item_id","revision_no"),
	CONSTRAINT "platform_memory_revision_uq_1" UNIQUE("tenant_id","id"),
	CONSTRAINT "platform_memory_revision_redaction_status_ck" CHECK ("platform_memory_revision"."redaction_status" in ('CLEAN', 'REDACTED', 'BLOCKED')),
	CONSTRAINT "platform_memory_revision_ck_0" CHECK (revision_no > 0)
);
--> statement-breakpoint
ALTER TABLE "platform_memory_revision" ENABLE ROW LEVEL SECURITY;--> statement-breakpoint
CREATE TABLE "platform_memory_vector_ref" (
	"id" uuid PRIMARY KEY DEFAULT gen_random_uuid() NOT NULL,
	"tenant_id" uuid NOT NULL,
	"memory_revision_id" uuid NOT NULL,
	"qdrant_collection" text NOT NULL,
	"qdrant_point_id" uuid NOT NULL,
	"embedding_model" text NOT NULL,
	"dimension" integer NOT NULL,
	"sync_status" text NOT NULL,
	"created_at" timestamp with time zone DEFAULT now() NOT NULL,
	"version" bigint DEFAULT 1 NOT NULL,
	"updated_at" timestamp with time zone DEFAULT now() NOT NULL,
	CONSTRAINT "platform_memory_vector_ref_uq_0" UNIQUE("tenant_id","memory_revision_id"),
	CONSTRAINT "platform_memory_vector_ref_uq_1" UNIQUE("qdrant_collection","qdrant_point_id"),
	CONSTRAINT "platform_memory_vector_ref_uq_2" UNIQUE("tenant_id","id"),
	CONSTRAINT "platform_memory_vector_ref_sync_status_ck" CHECK ("platform_memory_vector_ref"."sync_status" in ('PENDING', 'SYNCED', 'DELETE_PENDING', 'DELETED', 'FAILED')),
	CONSTRAINT "platform_memory_vector_ref_ck_0" CHECK (dimension > 0),
	CONSTRAINT "platform_memory_vector_ref_ck_1" CHECK (version > 0)
);
--> statement-breakpoint
ALTER TABLE "platform_memory_vector_ref" ENABLE ROW LEVEL SECURITY;--> statement-breakpoint
CREATE TABLE "platform_policy" (
	"id" uuid PRIMARY KEY DEFAULT gen_random_uuid() NOT NULL,
	"tenant_id" uuid NOT NULL,
	"code" text NOT NULL,
	"name" text NOT NULL,
	"policy_type" text NOT NULL,
	"owner_id" text NOT NULL,
	"status" text NOT NULL,
	"created_at" timestamp with time zone DEFAULT now() NOT NULL,
	"version" bigint DEFAULT 1 NOT NULL,
	"updated_at" timestamp with time zone DEFAULT now() NOT NULL,
	CONSTRAINT "platform_policy_uq_0" UNIQUE("tenant_id","code"),
	CONSTRAINT "platform_policy_uq_1" UNIQUE("tenant_id","id"),
	CONSTRAINT "platform_policy_status_ck" CHECK ("platform_policy"."status" in ('ACTIVE', 'SUSPENDED', 'RETIRED')),
	CONSTRAINT "platform_policy_ck_0" CHECK (version > 0)
);
--> statement-breakpoint
ALTER TABLE "platform_policy" ENABLE ROW LEVEL SECURITY;--> statement-breakpoint
CREATE TABLE "platform_policy_version" (
	"id" uuid PRIMARY KEY DEFAULT gen_random_uuid() NOT NULL,
	"tenant_id" uuid NOT NULL,
	"policy_id" uuid NOT NULL,
	"version_no" integer NOT NULL,
	"language" text NOT NULL,
	"content_ref" text NOT NULL,
	"content_hash" text NOT NULL,
	"status" text NOT NULL,
	"created_at" timestamp with time zone DEFAULT now() NOT NULL,
	"version" bigint DEFAULT 1 NOT NULL,
	"updated_at" timestamp with time zone DEFAULT now() NOT NULL,
	CONSTRAINT "platform_policy_version_uq_0" UNIQUE("tenant_id","policy_id","version_no"),
	CONSTRAINT "platform_policy_version_uq_1" UNIQUE("tenant_id","id"),
	CONSTRAINT "platform_policy_version_status_ck" CHECK ("platform_policy_version"."status" in ('DRAFT', 'PUBLISHED', 'RETIRED')),
	CONSTRAINT "platform_policy_version_ck_0" CHECK (version_no > 0),
	CONSTRAINT "platform_policy_version_ck_1" CHECK (version > 0)
);
--> statement-breakpoint
ALTER TABLE "platform_policy_version" ENABLE ROW LEVEL SECURITY;--> statement-breakpoint
CREATE TABLE "platform_action_proposal" (
	"id" uuid PRIMARY KEY DEFAULT gen_random_uuid() NOT NULL,
	"tenant_id" uuid NOT NULL,
	"runtime_decision_id" uuid NOT NULL,
	"workflow_session_id" uuid NOT NULL,
	"producer_agent_run_id" uuid,
	"action_type" text NOT NULL,
	"target_json" jsonb NOT NULL,
	"payload_json" jsonb NOT NULL,
	"payload_hash" text NOT NULL,
	"idempotency_key" text NOT NULL,
	"status" text NOT NULL,
	"correlation_id" text NOT NULL,
	"trace_id" text NOT NULL,
	"created_at" timestamp with time zone DEFAULT now() NOT NULL,
	"version" bigint DEFAULT 1 NOT NULL,
	"updated_at" timestamp with time zone DEFAULT now() NOT NULL,
	CONSTRAINT "platform_action_proposal_uq_0" UNIQUE("tenant_id","idempotency_key"),
	CONSTRAINT "platform_action_proposal_uq_1" UNIQUE("tenant_id","id"),
	CONSTRAINT "platform_action_proposal_status_ck" CHECK ("platform_action_proposal"."status" in ('PROPOSED', 'ACCEPTED', 'REJECTED')),
	CONSTRAINT "platform_action_proposal_ck_0" CHECK (version > 0)
);
--> statement-breakpoint
ALTER TABLE "platform_action_proposal" ENABLE ROW LEVEL SECURITY;--> statement-breakpoint
CREATE TABLE "platform_agent_run" (
	"id" uuid PRIMARY KEY DEFAULT gen_random_uuid() NOT NULL,
	"tenant_id" uuid NOT NULL,
	"workflow_session_id" uuid NOT NULL,
	"run_step_id" uuid NOT NULL,
	"agent_id" uuid NOT NULL,
	"agent_version_id" uuid NOT NULL,
	"status" text NOT NULL,
	"input_snapshot" jsonb NOT NULL,
	"output_snapshot" jsonb NOT NULL,
	"trace_id" text NOT NULL,
	"started_at" timestamp with time zone,
	"completed_at" timestamp with time zone,
	"created_at" timestamp with time zone DEFAULT now() NOT NULL,
	"version" bigint DEFAULT 1 NOT NULL,
	"updated_at" timestamp with time zone DEFAULT now() NOT NULL,
	CONSTRAINT "platform_agent_run_uq_0" UNIQUE("tenant_id","id"),
	CONSTRAINT "platform_agent_run_uq_1" UNIQUE("tenant_id","workflow_session_id","id"),
	CONSTRAINT "platform_agent_run_status_ck" CHECK ("platform_agent_run"."status" in ('PENDING', 'RUNNING', 'COMPLETED', 'FAILED', 'CANCELLED')),
	CONSTRAINT "platform_agent_run_ck_0" CHECK (version > 0)
);
--> statement-breakpoint
ALTER TABLE "platform_agent_run" ENABLE ROW LEVEL SECURITY;--> statement-breakpoint
CREATE TABLE "platform_execution_grant_ref" (
	"id" uuid PRIMARY KEY DEFAULT gen_random_uuid() NOT NULL,
	"tenant_id" uuid NOT NULL,
	"action_proposal_id" uuid NOT NULL,
	"domain_namespace" text NOT NULL,
	"domain_action_ref" text NOT NULL,
	"grant_ref" text NOT NULL,
	"payload_hash" text NOT NULL,
	"expires_at" timestamp with time zone NOT NULL,
	"status" text NOT NULL,
	"created_at" timestamp with time zone DEFAULT now() NOT NULL,
	"version" bigint DEFAULT 1 NOT NULL,
	"updated_at" timestamp with time zone DEFAULT now() NOT NULL,
	CONSTRAINT "platform_execution_grant_ref_uq_0" UNIQUE("tenant_id","domain_namespace","grant_ref"),
	CONSTRAINT "platform_execution_grant_ref_uq_1" UNIQUE("tenant_id","id"),
	CONSTRAINT "platform_execution_grant_ref_status_ck" CHECK ("platform_execution_grant_ref"."status" in ('ACTIVE', 'CONSUMED', 'REVOKED', 'EXPIRED')),
	CONSTRAINT "platform_execution_grant_ref_ck_0" CHECK (version > 0)
);
--> statement-breakpoint
ALTER TABLE "platform_execution_grant_ref" ENABLE ROW LEVEL SECURITY;--> statement-breakpoint
CREATE TABLE "platform_run_step" (
	"id" uuid PRIMARY KEY DEFAULT gen_random_uuid() NOT NULL,
	"tenant_id" uuid NOT NULL,
	"workflow_session_id" uuid NOT NULL,
	"step_key" text NOT NULL,
	"step_type" text NOT NULL,
	"status" text NOT NULL,
	"input_json" jsonb NOT NULL,
	"output_json" jsonb NOT NULL,
	"attempt_no" integer NOT NULL,
	"started_at" timestamp with time zone,
	"completed_at" timestamp with time zone,
	"created_at" timestamp with time zone DEFAULT now() NOT NULL,
	"version" bigint DEFAULT 1 NOT NULL,
	"updated_at" timestamp with time zone DEFAULT now() NOT NULL,
	CONSTRAINT "platform_run_step_uq_0" UNIQUE("tenant_id","workflow_session_id","step_key","attempt_no"),
	CONSTRAINT "platform_run_step_uq_1" UNIQUE("tenant_id","id"),
	CONSTRAINT "platform_run_step_uq_2" UNIQUE("tenant_id","workflow_session_id","id"),
	CONSTRAINT "platform_run_step_status_ck" CHECK ("platform_run_step"."status" in ('PENDING', 'READY', 'RUNNING', 'WAITING', 'COMPLETED', 'FAILED', 'CANCELLED')),
	CONSTRAINT "platform_run_step_ck_0" CHECK (attempt_no > 0),
	CONSTRAINT "platform_run_step_ck_1" CHECK (version > 0)
);
--> statement-breakpoint
ALTER TABLE "platform_run_step" ENABLE ROW LEVEL SECURITY;--> statement-breakpoint
CREATE TABLE "platform_run_step_dependency" (
	"tenant_id" uuid NOT NULL,
	"workflow_session_id" uuid NOT NULL,
	"run_step_id" uuid NOT NULL,
	"depends_on_run_step_id" uuid NOT NULL,
	"required" boolean NOT NULL,
	"created_at" timestamp with time zone DEFAULT now() NOT NULL,
	CONSTRAINT "platform_run_step_dependency_tenant_id_run_step_id_depends_on_run_step_id_pk" PRIMARY KEY("tenant_id","run_step_id","depends_on_run_step_id"),
	CONSTRAINT "platform_run_step_dependency_ck_0" CHECK (run_step_id <> depends_on_run_step_id)
);
--> statement-breakpoint
ALTER TABLE "platform_run_step_dependency" ENABLE ROW LEVEL SECURITY;--> statement-breakpoint
CREATE TABLE "platform_runtime_artifact" (
	"id" uuid PRIMARY KEY DEFAULT gen_random_uuid() NOT NULL,
	"tenant_id" uuid NOT NULL,
	"agent_run_id" uuid NOT NULL,
	"artifact_type" text NOT NULL,
	"payload_json" jsonb NOT NULL,
	"storage_ref" text,
	"created_at" timestamp with time zone DEFAULT now() NOT NULL,
	CONSTRAINT "platform_runtime_artifact_uq_0" UNIQUE("tenant_id","id")
);
--> statement-breakpoint
ALTER TABLE "platform_runtime_artifact" ENABLE ROW LEVEL SECURITY;--> statement-breakpoint
CREATE TABLE "platform_runtime_decision" (
	"id" uuid PRIMARY KEY DEFAULT gen_random_uuid() NOT NULL,
	"tenant_id" uuid NOT NULL,
	"workflow_session_id" uuid NOT NULL,
	"decision_type" text NOT NULL,
	"payload_json" jsonb NOT NULL,
	"created_by_run_id" uuid,
	"created_at" timestamp with time zone DEFAULT now() NOT NULL,
	CONSTRAINT "platform_runtime_decision_uq_0" UNIQUE("tenant_id","id"),
	CONSTRAINT "platform_runtime_decision_uq_1" UNIQUE("tenant_id","workflow_session_id","id")
);
--> statement-breakpoint
ALTER TABLE "platform_runtime_decision" ENABLE ROW LEVEL SECURITY;--> statement-breakpoint
CREATE TABLE "platform_tool_call" (
	"id" uuid PRIMARY KEY DEFAULT gen_random_uuid() NOT NULL,
	"tenant_id" uuid NOT NULL,
	"agent_run_id" uuid NOT NULL,
	"tool_version_id" uuid NOT NULL,
	"request_json" jsonb NOT NULL,
	"response_json" jsonb NOT NULL,
	"decision" text NOT NULL,
	"status" text NOT NULL,
	"started_at" timestamp with time zone,
	"completed_at" timestamp with time zone,
	"created_at" timestamp with time zone DEFAULT now() NOT NULL,
	"version" bigint DEFAULT 1 NOT NULL,
	"updated_at" timestamp with time zone DEFAULT now() NOT NULL,
	CONSTRAINT "platform_tool_call_uq_0" UNIQUE("tenant_id","id"),
	CONSTRAINT "platform_tool_call_decision_ck" CHECK ("platform_tool_call"."decision" in ('ALLOW', 'DENY', 'REQUIRE_APPROVAL')),
	CONSTRAINT "platform_tool_call_status_ck" CHECK ("platform_tool_call"."status" in ('PENDING', 'RUNNING', 'SUCCEEDED', 'FAILED', 'DENIED')),
	CONSTRAINT "platform_tool_call_ck_0" CHECK (version > 0)
);
--> statement-breakpoint
ALTER TABLE "platform_tool_call" ENABLE ROW LEVEL SECURITY;--> statement-breakpoint
CREATE TABLE "platform_workflow_session" (
	"id" uuid PRIMARY KEY DEFAULT gen_random_uuid() NOT NULL,
	"tenant_id" uuid NOT NULL,
	"domain_namespace" text NOT NULL,
	"subject_type" text NOT NULL,
	"subject_ref" text NOT NULL,
	"subject_version" bigint,
	"runtime_provider" text NOT NULL,
	"environment" text NOT NULL,
	"status" text NOT NULL,
	"plan_snapshot" jsonb NOT NULL,
	"started_at" timestamp with time zone,
	"completed_at" timestamp with time zone,
	"trace_id" text NOT NULL,
	"created_at" timestamp with time zone DEFAULT now() NOT NULL,
	"version" bigint DEFAULT 1 NOT NULL,
	"updated_at" timestamp with time zone DEFAULT now() NOT NULL,
	CONSTRAINT "platform_workflow_session_uq_0" UNIQUE("tenant_id","id"),
	CONSTRAINT "platform_workflow_session_status_ck" CHECK ("platform_workflow_session"."status" in ('PENDING', 'RUNNING', 'WAITING', 'COMPLETED', 'FAILED', 'CANCELLED')),
	CONSTRAINT "platform_workflow_session_ck_0" CHECK (version > 0),
	CONSTRAINT "platform_workflow_session_environment_ck" CHECK ("platform_workflow_session"."environment" in ('DEVELOPMENT', 'STAGING', 'PRODUCTION'))
);
--> statement-breakpoint
ALTER TABLE "platform_workflow_session" ENABLE ROW LEVEL SECURITY;--> statement-breakpoint
ALTER TABLE "vh_membership_application_file" ADD CONSTRAINT "vh_membership_application_file_fk_0" FOREIGN KEY ("tenant_id") REFERENCES "public"."platform_tenant"("id") ON DELETE restrict ON UPDATE no action;--> statement-breakpoint
ALTER TABLE "vh_membership_application_file" ADD CONSTRAINT "vh_membership_application_file_fk_1" FOREIGN KEY ("tenant_id","project_id") REFERENCES "public"."vh_project"("tenant_id","id") ON DELETE restrict ON UPDATE no action;--> statement-breakpoint
ALTER TABLE "vh_membership_application_file" ADD CONSTRAINT "vh_membership_application_file_fk_2" FOREIGN KEY ("tenant_id","project_id","application_id") REFERENCES "public"."vh_membership_application"("tenant_id","project_id","id") ON DELETE restrict ON UPDATE no action;--> statement-breakpoint
ALTER TABLE "vh_membership_application_file" ADD CONSTRAINT "vh_membership_application_file_fk_3" FOREIGN KEY ("tenant_id","file_id") REFERENCES "public"."vh_file_object"("tenant_id","id") ON DELETE restrict ON UPDATE no action;--> statement-breakpoint
ALTER TABLE "vh_pet_document" ADD CONSTRAINT "vh_pet_document_fk_0" FOREIGN KEY ("tenant_id") REFERENCES "public"."platform_tenant"("id") ON DELETE restrict ON UPDATE no action;--> statement-breakpoint
ALTER TABLE "vh_pet_document" ADD CONSTRAINT "vh_pet_document_fk_1" FOREIGN KEY ("tenant_id","project_id") REFERENCES "public"."vh_project"("tenant_id","id") ON DELETE restrict ON UPDATE no action;--> statement-breakpoint
ALTER TABLE "vh_pet_document" ADD CONSTRAINT "vh_pet_document_fk_2" FOREIGN KEY ("tenant_id","project_id","pet_id") REFERENCES "public"."vh_pet_profile"("tenant_id","project_id","id") ON DELETE restrict ON UPDATE no action;--> statement-breakpoint
ALTER TABLE "vh_pet_document" ADD CONSTRAINT "vh_pet_document_fk_3" FOREIGN KEY ("tenant_id","file_id") REFERENCES "public"."vh_file_object"("tenant_id","id") ON DELETE restrict ON UPDATE no action;--> statement-breakpoint
ALTER TABLE "vh_report_attachment" ADD CONSTRAINT "vh_report_attachment_fk_0" FOREIGN KEY ("tenant_id") REFERENCES "public"."platform_tenant"("id") ON DELETE restrict ON UPDATE no action;--> statement-breakpoint
ALTER TABLE "vh_report_attachment" ADD CONSTRAINT "vh_report_attachment_fk_1" FOREIGN KEY ("tenant_id","project_id") REFERENCES "public"."vh_project"("tenant_id","id") ON DELETE restrict ON UPDATE no action;--> statement-breakpoint
ALTER TABLE "vh_report_attachment" ADD CONSTRAINT "vh_report_attachment_fk_2" FOREIGN KEY ("tenant_id","project_id","report_id") REFERENCES "public"."vh_resident_report"("tenant_id","project_id","id") ON DELETE restrict ON UPDATE no action;--> statement-breakpoint
ALTER TABLE "vh_report_attachment" ADD CONSTRAINT "vh_report_attachment_fk_3" FOREIGN KEY ("tenant_id","file_id") REFERENCES "public"."vh_file_object"("tenant_id","id") ON DELETE restrict ON UPDATE no action;--> statement-breakpoint
ALTER TABLE "vh_request_attachment" ADD CONSTRAINT "vh_request_attachment_fk_0" FOREIGN KEY ("tenant_id") REFERENCES "public"."platform_tenant"("id") ON DELETE restrict ON UPDATE no action;--> statement-breakpoint
ALTER TABLE "vh_request_attachment" ADD CONSTRAINT "vh_request_attachment_fk_1" FOREIGN KEY ("tenant_id","project_id") REFERENCES "public"."vh_project"("tenant_id","id") ON DELETE restrict ON UPDATE no action;--> statement-breakpoint
ALTER TABLE "vh_request_attachment" ADD CONSTRAINT "vh_request_attachment_fk_2" FOREIGN KEY ("tenant_id","project_id","request_id") REFERENCES "public"."vh_resident_request"("tenant_id","project_id","id") ON DELETE restrict ON UPDATE no action;--> statement-breakpoint
ALTER TABLE "vh_request_attachment" ADD CONSTRAINT "vh_request_attachment_fk_3" FOREIGN KEY ("tenant_id","file_id") REFERENCES "public"."vh_file_object"("tenant_id","id") ON DELETE restrict ON UPDATE no action;--> statement-breakpoint
ALTER TABLE "vh_service_request_file" ADD CONSTRAINT "vh_service_request_file_fk_0" FOREIGN KEY ("tenant_id") REFERENCES "public"."platform_tenant"("id") ON DELETE restrict ON UPDATE no action;--> statement-breakpoint
ALTER TABLE "vh_service_request_file" ADD CONSTRAINT "vh_service_request_file_fk_1" FOREIGN KEY ("tenant_id","project_id") REFERENCES "public"."vh_project"("tenant_id","id") ON DELETE restrict ON UPDATE no action;--> statement-breakpoint
ALTER TABLE "vh_service_request_file" ADD CONSTRAINT "vh_service_request_file_fk_2" FOREIGN KEY ("tenant_id","project_id","request_id") REFERENCES "public"."vh_service_request"("tenant_id","project_id","id") ON DELETE restrict ON UPDATE no action;--> statement-breakpoint
ALTER TABLE "vh_service_request_file" ADD CONSTRAINT "vh_service_request_file_fk_3" FOREIGN KEY ("tenant_id","file_id") REFERENCES "public"."vh_file_object"("tenant_id","id") ON DELETE restrict ON UPDATE no action;--> statement-breakpoint
ALTER TABLE "vh_fee_schedule" ADD CONSTRAINT "vh_fee_schedule_fk_0" FOREIGN KEY ("tenant_id") REFERENCES "public"."platform_tenant"("id") ON DELETE restrict ON UPDATE no action;--> statement-breakpoint
ALTER TABLE "vh_fee_schedule" ADD CONSTRAINT "vh_fee_schedule_fk_1" FOREIGN KEY ("tenant_id","project_id") REFERENCES "public"."vh_project"("tenant_id","id") ON DELETE restrict ON UPDATE no action;--> statement-breakpoint
ALTER TABLE "vh_invoice" ADD CONSTRAINT "vh_invoice_fk_0" FOREIGN KEY ("tenant_id") REFERENCES "public"."platform_tenant"("id") ON DELETE restrict ON UPDATE no action;--> statement-breakpoint
ALTER TABLE "vh_invoice" ADD CONSTRAINT "vh_invoice_fk_1" FOREIGN KEY ("tenant_id","project_id") REFERENCES "public"."vh_project"("tenant_id","id") ON DELETE restrict ON UPDATE no action;--> statement-breakpoint
ALTER TABLE "vh_invoice" ADD CONSTRAINT "vh_invoice_fk_2" FOREIGN KEY ("tenant_id","project_id","apartment_id") REFERENCES "public"."vh_apartment"("tenant_id","project_id","id") ON DELETE restrict ON UPDATE no action;--> statement-breakpoint
ALTER TABLE "vh_invoice" ADD CONSTRAINT "vh_invoice_fk_3" FOREIGN KEY ("billed_to_user_id") REFERENCES "public"."users"("id") ON DELETE restrict ON UPDATE no action;--> statement-breakpoint
ALTER TABLE "vh_invoice_line" ADD CONSTRAINT "vh_invoice_line_fk_0" FOREIGN KEY ("tenant_id") REFERENCES "public"."platform_tenant"("id") ON DELETE restrict ON UPDATE no action;--> statement-breakpoint
ALTER TABLE "vh_invoice_line" ADD CONSTRAINT "vh_invoice_line_fk_1" FOREIGN KEY ("tenant_id","project_id") REFERENCES "public"."vh_project"("tenant_id","id") ON DELETE restrict ON UPDATE no action;--> statement-breakpoint
ALTER TABLE "vh_invoice_line" ADD CONSTRAINT "vh_invoice_line_fk_2" FOREIGN KEY ("tenant_id","project_id","invoice_id") REFERENCES "public"."vh_invoice"("tenant_id","project_id","id") ON DELETE restrict ON UPDATE no action;--> statement-breakpoint
ALTER TABLE "vh_invoice_line" ADD CONSTRAINT "vh_invoice_line_fk_3" FOREIGN KEY ("tenant_id","project_id","fee_schedule_id") REFERENCES "public"."vh_fee_schedule"("tenant_id","project_id","id") ON DELETE restrict ON UPDATE no action;--> statement-breakpoint
ALTER TABLE "vh_loyalty_account" ADD CONSTRAINT "vh_loyalty_account_fk_0" FOREIGN KEY ("tenant_id") REFERENCES "public"."platform_tenant"("id") ON DELETE restrict ON UPDATE no action;--> statement-breakpoint
ALTER TABLE "vh_loyalty_account" ADD CONSTRAINT "vh_loyalty_account_fk_1" FOREIGN KEY ("user_id") REFERENCES "public"."users"("id") ON DELETE restrict ON UPDATE no action;--> statement-breakpoint
ALTER TABLE "vh_loyalty_entry" ADD CONSTRAINT "vh_loyalty_entry_fk_0" FOREIGN KEY ("tenant_id") REFERENCES "public"."platform_tenant"("id") ON DELETE restrict ON UPDATE no action;--> statement-breakpoint
ALTER TABLE "vh_loyalty_entry" ADD CONSTRAINT "vh_loyalty_entry_fk_1" FOREIGN KEY ("tenant_id","account_id") REFERENCES "public"."vh_loyalty_account"("tenant_id","id") ON DELETE restrict ON UPDATE no action;--> statement-breakpoint
ALTER TABLE "vh_payment_allocation" ADD CONSTRAINT "vh_payment_allocation_fk_0" FOREIGN KEY ("tenant_id") REFERENCES "public"."platform_tenant"("id") ON DELETE restrict ON UPDATE no action;--> statement-breakpoint
ALTER TABLE "vh_payment_allocation" ADD CONSTRAINT "vh_payment_allocation_fk_1" FOREIGN KEY ("tenant_id","project_id") REFERENCES "public"."vh_project"("tenant_id","id") ON DELETE restrict ON UPDATE no action;--> statement-breakpoint
ALTER TABLE "vh_payment_allocation" ADD CONSTRAINT "vh_payment_allocation_fk_2" FOREIGN KEY ("tenant_id","project_id","invoice_id","payment_attempt_id") REFERENCES "public"."vh_payment_attempt"("tenant_id","project_id","invoice_id","id") ON DELETE restrict ON UPDATE no action;--> statement-breakpoint
ALTER TABLE "vh_payment_allocation" ADD CONSTRAINT "vh_payment_allocation_fk_3" FOREIGN KEY ("tenant_id","project_id","invoice_id") REFERENCES "public"."vh_invoice"("tenant_id","project_id","id") ON DELETE restrict ON UPDATE no action;--> statement-breakpoint
ALTER TABLE "vh_payment_attempt" ADD CONSTRAINT "vh_payment_attempt_fk_0" FOREIGN KEY ("tenant_id") REFERENCES "public"."platform_tenant"("id") ON DELETE restrict ON UPDATE no action;--> statement-breakpoint
ALTER TABLE "vh_payment_attempt" ADD CONSTRAINT "vh_payment_attempt_fk_1" FOREIGN KEY ("tenant_id","project_id") REFERENCES "public"."vh_project"("tenant_id","id") ON DELETE restrict ON UPDATE no action;--> statement-breakpoint
ALTER TABLE "vh_payment_attempt" ADD CONSTRAINT "vh_payment_attempt_fk_2" FOREIGN KEY ("tenant_id","project_id","invoice_id") REFERENCES "public"."vh_invoice"("tenant_id","project_id","id") ON DELETE restrict ON UPDATE no action;--> statement-breakpoint
ALTER TABLE "vh_payment_attempt" ADD CONSTRAINT "vh_payment_attempt_fk_3" FOREIGN KEY ("initiated_by_user_id") REFERENCES "public"."users"("id") ON DELETE restrict ON UPDATE no action;--> statement-breakpoint
ALTER TABLE "vh_booking" ADD CONSTRAINT "vh_booking_fk_0" FOREIGN KEY ("tenant_id") REFERENCES "public"."platform_tenant"("id") ON DELETE restrict ON UPDATE no action;--> statement-breakpoint
ALTER TABLE "vh_booking" ADD CONSTRAINT "vh_booking_fk_1" FOREIGN KEY ("tenant_id","project_id") REFERENCES "public"."vh_project"("tenant_id","id") ON DELETE restrict ON UPDATE no action;--> statement-breakpoint
ALTER TABLE "vh_booking" ADD CONSTRAINT "vh_booking_fk_2" FOREIGN KEY ("tenant_id","project_id","slot_id") REFERENCES "public"."vh_time_slot"("tenant_id","project_id","id") ON DELETE restrict ON UPDATE no action;--> statement-breakpoint
ALTER TABLE "vh_booking" ADD CONSTRAINT "vh_booking_fk_3" FOREIGN KEY ("tenant_id","project_id","apartment_id") REFERENCES "public"."vh_apartment"("tenant_id","project_id","id") ON DELETE restrict ON UPDATE no action;--> statement-breakpoint
ALTER TABLE "vh_booking" ADD CONSTRAINT "vh_booking_fk_4" FOREIGN KEY ("tenant_id","project_id","booked_by_membership_id") REFERENCES "public"."vh_property_membership"("tenant_id","project_id","id") ON DELETE restrict ON UPDATE no action;--> statement-breakpoint
ALTER TABLE "vh_booking" ADD CONSTRAINT "vh_booking_fk_5" FOREIGN KEY ("tenant_id","project_id","apartment_id","booked_by_membership_id") REFERENCES "public"."vh_property_membership"("tenant_id","project_id","apartment_id","id") ON DELETE restrict ON UPDATE no action;--> statement-breakpoint
ALTER TABLE "vh_facility" ADD CONSTRAINT "vh_facility_fk_0" FOREIGN KEY ("tenant_id") REFERENCES "public"."platform_tenant"("id") ON DELETE restrict ON UPDATE no action;--> statement-breakpoint
ALTER TABLE "vh_facility" ADD CONSTRAINT "vh_facility_fk_1" FOREIGN KEY ("tenant_id","project_id") REFERENCES "public"."vh_project"("tenant_id","id") ON DELETE restrict ON UPDATE no action;--> statement-breakpoint
ALTER TABLE "vh_facility" ADD CONSTRAINT "vh_facility_fk_2" FOREIGN KEY ("tenant_id","project_id","place_id") REFERENCES "public"."vh_map_place"("tenant_id","project_id","id") ON DELETE restrict ON UPDATE no action;--> statement-breakpoint
ALTER TABLE "vh_time_slot" ADD CONSTRAINT "vh_time_slot_fk_0" FOREIGN KEY ("tenant_id") REFERENCES "public"."platform_tenant"("id") ON DELETE restrict ON UPDATE no action;--> statement-breakpoint
ALTER TABLE "vh_time_slot" ADD CONSTRAINT "vh_time_slot_fk_1" FOREIGN KEY ("tenant_id","project_id") REFERENCES "public"."vh_project"("tenant_id","id") ON DELETE restrict ON UPDATE no action;--> statement-breakpoint
ALTER TABLE "vh_time_slot" ADD CONSTRAINT "vh_time_slot_fk_2" FOREIGN KEY ("tenant_id","project_id","facility_id") REFERENCES "public"."vh_facility"("tenant_id","project_id","id") ON DELETE restrict ON UPDATE no action;--> statement-breakpoint
ALTER TABLE "vh_business_event" ADD CONSTRAINT "vh_business_event_fk_0" FOREIGN KEY ("tenant_id") REFERENCES "public"."platform_tenant"("id") ON DELETE restrict ON UPDATE no action;--> statement-breakpoint
ALTER TABLE "vh_business_event" ADD CONSTRAINT "vh_business_event_fk_1" FOREIGN KEY ("tenant_id","project_id") REFERENCES "public"."vh_project"("tenant_id","id") ON DELETE restrict ON UPDATE no action;--> statement-breakpoint
ALTER TABLE "vh_business_event" ADD CONSTRAINT "vh_business_event_fk_2" FOREIGN KEY ("tenant_id","project_id","incident_id") REFERENCES "public"."vh_incident"("tenant_id","project_id","id") ON DELETE restrict ON UPDATE no action;--> statement-breakpoint
ALTER TABLE "vh_message" ADD CONSTRAINT "vh_message_fk_0" FOREIGN KEY ("tenant_id") REFERENCES "public"."platform_tenant"("id") ON DELETE restrict ON UPDATE no action;--> statement-breakpoint
ALTER TABLE "vh_message" ADD CONSTRAINT "vh_message_fk_1" FOREIGN KEY ("tenant_id","project_id") REFERENCES "public"."vh_project"("tenant_id","id") ON DELETE restrict ON UPDATE no action;--> statement-breakpoint
ALTER TABLE "vh_message" ADD CONSTRAINT "vh_message_fk_2" FOREIGN KEY ("tenant_id","project_id","incident_id") REFERENCES "public"."vh_incident"("tenant_id","project_id","id") ON DELETE restrict ON UPDATE no action;--> statement-breakpoint
ALTER TABLE "vh_message" ADD CONSTRAINT "vh_message_fk_3" FOREIGN KEY ("tenant_id","project_id","resident_report_id") REFERENCES "public"."vh_resident_report"("tenant_id","project_id","id") ON DELETE restrict ON UPDATE no action;--> statement-breakpoint
ALTER TABLE "vh_message" ADD CONSTRAINT "vh_message_fk_4" FOREIGN KEY ("tenant_id","incident_id","resident_report_id") REFERENCES "public"."vh_resident_report"("tenant_id","incident_id","id") ON DELETE restrict ON UPDATE no action;--> statement-breakpoint
ALTER TABLE "vh_notification" ADD CONSTRAINT "vh_notification_fk_0" FOREIGN KEY ("tenant_id") REFERENCES "public"."platform_tenant"("id") ON DELETE restrict ON UPDATE no action;--> statement-breakpoint
ALTER TABLE "vh_notification" ADD CONSTRAINT "vh_notification_fk_1" FOREIGN KEY ("tenant_id","project_id") REFERENCES "public"."vh_project"("tenant_id","id") ON DELETE restrict ON UPDATE no action;--> statement-breakpoint
ALTER TABLE "vh_notification" ADD CONSTRAINT "vh_notification_fk_2" FOREIGN KEY ("tenant_id","project_id","business_event_id") REFERENCES "public"."vh_business_event"("tenant_id","project_id","id") ON DELETE restrict ON UPDATE no action;--> statement-breakpoint
ALTER TABLE "vh_notification" ADD CONSTRAINT "vh_notification_fk_3" FOREIGN KEY ("recipient_id") REFERENCES "public"."users"("id") ON DELETE restrict ON UPDATE no action;--> statement-breakpoint
ALTER TABLE "vh_community_event" ADD CONSTRAINT "vh_community_event_fk_0" FOREIGN KEY ("tenant_id") REFERENCES "public"."platform_tenant"("id") ON DELETE restrict ON UPDATE no action;--> statement-breakpoint
ALTER TABLE "vh_community_event" ADD CONSTRAINT "vh_community_event_fk_1" FOREIGN KEY ("tenant_id","project_id") REFERENCES "public"."vh_project"("tenant_id","id") ON DELETE restrict ON UPDATE no action;--> statement-breakpoint
ALTER TABLE "vh_community_event" ADD CONSTRAINT "vh_community_event_fk_2" FOREIGN KEY ("tenant_id","project_id","place_id") REFERENCES "public"."vh_map_place"("tenant_id","project_id","id") ON DELETE restrict ON UPDATE no action;--> statement-breakpoint
ALTER TABLE "vh_content_item" ADD CONSTRAINT "vh_content_item_fk_0" FOREIGN KEY ("tenant_id") REFERENCES "public"."platform_tenant"("id") ON DELETE restrict ON UPDATE no action;--> statement-breakpoint
ALTER TABLE "vh_content_item" ADD CONSTRAINT "vh_content_item_fk_1" FOREIGN KEY ("tenant_id","project_id") REFERENCES "public"."vh_project"("tenant_id","id") ON DELETE restrict ON UPDATE no action;--> statement-breakpoint
ALTER TABLE "vh_event_registration" ADD CONSTRAINT "vh_event_registration_fk_0" FOREIGN KEY ("tenant_id") REFERENCES "public"."platform_tenant"("id") ON DELETE restrict ON UPDATE no action;--> statement-breakpoint
ALTER TABLE "vh_event_registration" ADD CONSTRAINT "vh_event_registration_fk_1" FOREIGN KEY ("tenant_id","project_id") REFERENCES "public"."vh_project"("tenant_id","id") ON DELETE restrict ON UPDATE no action;--> statement-breakpoint
ALTER TABLE "vh_event_registration" ADD CONSTRAINT "vh_event_registration_fk_2" FOREIGN KEY ("tenant_id","project_id","event_id") REFERENCES "public"."vh_community_event"("tenant_id","project_id","id") ON DELETE restrict ON UPDATE no action;--> statement-breakpoint
ALTER TABLE "vh_event_registration" ADD CONSTRAINT "vh_event_registration_fk_3" FOREIGN KEY ("tenant_id","project_id","membership_id") REFERENCES "public"."vh_property_membership"("tenant_id","project_id","id") ON DELETE restrict ON UPDATE no action;--> statement-breakpoint
ALTER TABLE "vh_map_place" ADD CONSTRAINT "vh_map_place_fk_0" FOREIGN KEY ("tenant_id") REFERENCES "public"."platform_tenant"("id") ON DELETE restrict ON UPDATE no action;--> statement-breakpoint
ALTER TABLE "vh_map_place" ADD CONSTRAINT "vh_map_place_fk_1" FOREIGN KEY ("tenant_id","project_id") REFERENCES "public"."vh_project"("tenant_id","id") ON DELETE restrict ON UPDATE no action;--> statement-breakpoint
ALTER TABLE "vh_map_place" ADD CONSTRAINT "vh_map_place_fk_2" FOREIGN KEY ("tenant_id","project_id","tower_id") REFERENCES "public"."vh_tower"("tenant_id","project_id","id") ON DELETE restrict ON UPDATE no action;--> statement-breakpoint
ALTER TABLE "vh_miniapp_catalog" ADD CONSTRAINT "vh_miniapp_catalog_fk_0" FOREIGN KEY ("tenant_id") REFERENCES "public"."platform_tenant"("id") ON DELETE restrict ON UPDATE no action;--> statement-breakpoint
ALTER TABLE "vh_miniapp_catalog" ADD CONSTRAINT "vh_miniapp_catalog_fk_1" FOREIGN KEY ("tenant_id","project_id") REFERENCES "public"."vh_project"("tenant_id","id") ON DELETE restrict ON UPDATE no action;--> statement-breakpoint
ALTER TABLE "vh_offer" ADD CONSTRAINT "vh_offer_fk_0" FOREIGN KEY ("tenant_id") REFERENCES "public"."platform_tenant"("id") ON DELETE restrict ON UPDATE no action;--> statement-breakpoint
ALTER TABLE "vh_offer" ADD CONSTRAINT "vh_offer_fk_1" FOREIGN KEY ("tenant_id","project_id") REFERENCES "public"."vh_project"("tenant_id","id") ON DELETE restrict ON UPDATE no action;--> statement-breakpoint
ALTER TABLE "vh_sensor_reading" ADD CONSTRAINT "vh_sensor_reading_fk_0" FOREIGN KEY ("tenant_id") REFERENCES "public"."platform_tenant"("id") ON DELETE restrict ON UPDATE no action;--> statement-breakpoint
ALTER TABLE "vh_sensor_reading" ADD CONSTRAINT "vh_sensor_reading_fk_1" FOREIGN KEY ("tenant_id","project_id") REFERENCES "public"."vh_project"("tenant_id","id") ON DELETE restrict ON UPDATE no action;--> statement-breakpoint
ALTER TABLE "vh_sensor_reading" ADD CONSTRAINT "vh_sensor_reading_fk_2" FOREIGN KEY ("tenant_id","project_id","place_id") REFERENCES "public"."vh_map_place"("tenant_id","project_id","id") ON DELETE restrict ON UPDATE no action;--> statement-breakpoint
ALTER TABLE "vh_transit_route" ADD CONSTRAINT "vh_transit_route_fk_0" FOREIGN KEY ("tenant_id") REFERENCES "public"."platform_tenant"("id") ON DELETE restrict ON UPDATE no action;--> statement-breakpoint
ALTER TABLE "vh_transit_route" ADD CONSTRAINT "vh_transit_route_fk_1" FOREIGN KEY ("tenant_id","project_id") REFERENCES "public"."vh_project"("tenant_id","id") ON DELETE restrict ON UPDATE no action;--> statement-breakpoint
ALTER TABLE "vh_transit_route_stop" ADD CONSTRAINT "vh_transit_route_stop_fk_0" FOREIGN KEY ("tenant_id") REFERENCES "public"."platform_tenant"("id") ON DELETE restrict ON UPDATE no action;--> statement-breakpoint
ALTER TABLE "vh_transit_route_stop" ADD CONSTRAINT "vh_transit_route_stop_fk_1" FOREIGN KEY ("tenant_id","project_id") REFERENCES "public"."vh_project"("tenant_id","id") ON DELETE restrict ON UPDATE no action;--> statement-breakpoint
ALTER TABLE "vh_transit_route_stop" ADD CONSTRAINT "vh_transit_route_stop_fk_2" FOREIGN KEY ("tenant_id","project_id","route_id") REFERENCES "public"."vh_transit_route"("tenant_id","project_id","id") ON DELETE restrict ON UPDATE no action;--> statement-breakpoint
ALTER TABLE "vh_transit_route_stop" ADD CONSTRAINT "vh_transit_route_stop_fk_3" FOREIGN KEY ("tenant_id","project_id","stop_id") REFERENCES "public"."vh_transit_stop"("tenant_id","project_id","id") ON DELETE restrict ON UPDATE no action;--> statement-breakpoint
ALTER TABLE "vh_transit_stop" ADD CONSTRAINT "vh_transit_stop_fk_0" FOREIGN KEY ("tenant_id") REFERENCES "public"."platform_tenant"("id") ON DELETE restrict ON UPDATE no action;--> statement-breakpoint
ALTER TABLE "vh_transit_stop" ADD CONSTRAINT "vh_transit_stop_fk_1" FOREIGN KEY ("tenant_id","project_id") REFERENCES "public"."vh_project"("tenant_id","id") ON DELETE restrict ON UPDATE no action;--> statement-breakpoint
ALTER TABLE "vh_command_receipt" ADD CONSTRAINT "vh_command_receipt_fk_0" FOREIGN KEY ("tenant_id") REFERENCES "public"."platform_tenant"("id") ON DELETE restrict ON UPDATE no action;--> statement-breakpoint
ALTER TABLE "vh_command_receipt" ADD CONSTRAINT "vh_command_receipt_actor_fk" FOREIGN KEY ("actor_user_id") REFERENCES "public"."users"("id") ON DELETE restrict ON UPDATE no action;--> statement-breakpoint
ALTER TABLE "vh_outbox" ADD CONSTRAINT "vh_outbox_fk_0" FOREIGN KEY ("tenant_id") REFERENCES "public"."platform_tenant"("id") ON DELETE restrict ON UPDATE no action;--> statement-breakpoint
ALTER TABLE "vh_outbox" ADD CONSTRAINT "vh_outbox_fk_1" FOREIGN KEY ("tenant_id","project_id") REFERENCES "public"."vh_project"("tenant_id","id") ON DELETE restrict ON UPDATE no action;--> statement-breakpoint
ALTER TABLE "vh_outbox" ADD CONSTRAINT "vh_outbox_fk_2" FOREIGN KEY ("tenant_id","project_id","business_event_id") REFERENCES "public"."vh_business_event"("tenant_id","project_id","id") ON DELETE restrict ON UPDATE no action;--> statement-breakpoint
ALTER TABLE "vh_evidence_ref" ADD CONSTRAINT "vh_evidence_ref_fk_0" FOREIGN KEY ("tenant_id") REFERENCES "public"."platform_tenant"("id") ON DELETE restrict ON UPDATE no action;--> statement-breakpoint
ALTER TABLE "vh_evidence_ref" ADD CONSTRAINT "vh_evidence_ref_fk_1" FOREIGN KEY ("tenant_id","project_id") REFERENCES "public"."vh_project"("tenant_id","id") ON DELETE restrict ON UPDATE no action;--> statement-breakpoint
ALTER TABLE "vh_evidence_ref" ADD CONSTRAINT "vh_evidence_ref_fk_2" FOREIGN KEY ("tenant_id","project_id","incident_id") REFERENCES "public"."vh_incident"("tenant_id","project_id","id") ON DELETE restrict ON UPDATE no action;--> statement-breakpoint
ALTER TABLE "vh_evidence_ref" ADD CONSTRAINT "vh_evidence_ref_fk_3" FOREIGN KEY ("tenant_id","project_id","incident_id","task_id") REFERENCES "public"."vh_task"("tenant_id","project_id","incident_id","id") ON DELETE restrict ON UPDATE no action;--> statement-breakpoint
ALTER TABLE "vh_evidence_ref" ADD CONSTRAINT "vh_evidence_ref_fk_4" FOREIGN KEY ("tenant_id","project_id","incident_id","task_id","work_order_id") REFERENCES "public"."vh_work_order"("tenant_id","project_id","incident_id","task_id","id") ON DELETE restrict ON UPDATE no action;--> statement-breakpoint
ALTER TABLE "vh_evidence_ref" ADD CONSTRAINT "vh_evidence_ref_fk_5" FOREIGN KEY ("tenant_id","file_id") REFERENCES "public"."vh_file_object"("tenant_id","id") ON DELETE restrict ON UPDATE no action;--> statement-breakpoint
ALTER TABLE "vh_evidence_ref" ADD CONSTRAINT "vh_evidence_ref_fk_6" FOREIGN KEY ("uploaded_by") REFERENCES "public"."users"("id") ON DELETE restrict ON UPDATE no action;--> statement-breakpoint
ALTER TABLE "vh_qc_result" ADD CONSTRAINT "vh_qc_result_fk_0" FOREIGN KEY ("tenant_id") REFERENCES "public"."platform_tenant"("id") ON DELETE restrict ON UPDATE no action;--> statement-breakpoint
ALTER TABLE "vh_qc_result" ADD CONSTRAINT "vh_qc_result_fk_1" FOREIGN KEY ("tenant_id","project_id") REFERENCES "public"."vh_project"("tenant_id","id") ON DELETE restrict ON UPDATE no action;--> statement-breakpoint
ALTER TABLE "vh_qc_result" ADD CONSTRAINT "vh_qc_result_fk_2" FOREIGN KEY ("tenant_id","project_id","incident_id") REFERENCES "public"."vh_incident"("tenant_id","project_id","id") ON DELETE restrict ON UPDATE no action;--> statement-breakpoint
ALTER TABLE "vh_qc_result" ADD CONSTRAINT "vh_qc_result_fk_3" FOREIGN KEY ("tenant_id","project_id","incident_id","task_id") REFERENCES "public"."vh_task"("tenant_id","project_id","incident_id","id") ON DELETE restrict ON UPDATE no action;--> statement-breakpoint
ALTER TABLE "vh_qc_result" ADD CONSTRAINT "vh_qc_result_fk_4" FOREIGN KEY ("tenant_id","project_id","incident_id","task_id","work_order_id") REFERENCES "public"."vh_work_order"("tenant_id","project_id","incident_id","task_id","id") ON DELETE restrict ON UPDATE no action;--> statement-breakpoint
ALTER TABLE "vh_qc_result" ADD CONSTRAINT "vh_qc_result_fk_5" FOREIGN KEY ("checked_by") REFERENCES "public"."users"("id") ON DELETE restrict ON UPDATE no action;--> statement-breakpoint
ALTER TABLE "vh_qc_result_evidence" ADD CONSTRAINT "vh_qc_result_evidence_fk_0" FOREIGN KEY ("tenant_id") REFERENCES "public"."platform_tenant"("id") ON DELETE restrict ON UPDATE no action;--> statement-breakpoint
ALTER TABLE "vh_qc_result_evidence" ADD CONSTRAINT "vh_qc_result_evidence_fk_1" FOREIGN KEY ("tenant_id","project_id") REFERENCES "public"."vh_project"("tenant_id","id") ON DELETE restrict ON UPDATE no action;--> statement-breakpoint
ALTER TABLE "vh_qc_result_evidence" ADD CONSTRAINT "vh_qc_result_evidence_fk_2" FOREIGN KEY ("tenant_id","project_id","incident_id") REFERENCES "public"."vh_incident"("tenant_id","project_id","id") ON DELETE restrict ON UPDATE no action;--> statement-breakpoint
ALTER TABLE "vh_qc_result_evidence" ADD CONSTRAINT "vh_qc_result_evidence_fk_3" FOREIGN KEY ("tenant_id","project_id","incident_id","qc_result_id") REFERENCES "public"."vh_qc_result"("tenant_id","project_id","incident_id","id") ON DELETE restrict ON UPDATE no action;--> statement-breakpoint
ALTER TABLE "vh_qc_result_evidence" ADD CONSTRAINT "vh_qc_result_evidence_fk_4" FOREIGN KEY ("tenant_id","project_id","incident_id","evidence_ref_id") REFERENCES "public"."vh_evidence_ref"("tenant_id","project_id","incident_id","id") ON DELETE restrict ON UPDATE no action;--> statement-breakpoint
ALTER TABLE "vh_root_cause_evidence" ADD CONSTRAINT "vh_root_cause_evidence_fk_0" FOREIGN KEY ("tenant_id") REFERENCES "public"."platform_tenant"("id") ON DELETE restrict ON UPDATE no action;--> statement-breakpoint
ALTER TABLE "vh_root_cause_evidence" ADD CONSTRAINT "vh_root_cause_evidence_fk_1" FOREIGN KEY ("tenant_id","project_id") REFERENCES "public"."vh_project"("tenant_id","id") ON DELETE restrict ON UPDATE no action;--> statement-breakpoint
ALTER TABLE "vh_root_cause_evidence" ADD CONSTRAINT "vh_root_cause_evidence_fk_2" FOREIGN KEY ("tenant_id","project_id","root_cause_finding_id") REFERENCES "public"."vh_root_cause_finding"("tenant_id","project_id","id") ON DELETE restrict ON UPDATE no action;--> statement-breakpoint
ALTER TABLE "vh_root_cause_evidence" ADD CONSTRAINT "vh_root_cause_evidence_fk_3" FOREIGN KEY ("tenant_id","project_id","evidence_ref_id") REFERENCES "public"."vh_evidence_ref"("tenant_id","project_id","id") ON DELETE restrict ON UPDATE no action;--> statement-breakpoint
ALTER TABLE "vh_root_cause_finding" ADD CONSTRAINT "vh_root_cause_finding_fk_0" FOREIGN KEY ("tenant_id") REFERENCES "public"."platform_tenant"("id") ON DELETE restrict ON UPDATE no action;--> statement-breakpoint
ALTER TABLE "vh_root_cause_finding" ADD CONSTRAINT "vh_root_cause_finding_fk_1" FOREIGN KEY ("tenant_id","project_id") REFERENCES "public"."vh_project"("tenant_id","id") ON DELETE restrict ON UPDATE no action;--> statement-breakpoint
ALTER TABLE "vh_root_cause_finding" ADD CONSTRAINT "vh_root_cause_finding_fk_2" FOREIGN KEY ("tenant_id","project_id","incident_id") REFERENCES "public"."vh_incident"("tenant_id","project_id","id") ON DELETE restrict ON UPDATE no action;--> statement-breakpoint
ALTER TABLE "vh_root_cause_incident" ADD CONSTRAINT "vh_root_cause_incident_fk_0" FOREIGN KEY ("tenant_id") REFERENCES "public"."platform_tenant"("id") ON DELETE restrict ON UPDATE no action;--> statement-breakpoint
ALTER TABLE "vh_root_cause_incident" ADD CONSTRAINT "vh_root_cause_incident_fk_1" FOREIGN KEY ("tenant_id","project_id") REFERENCES "public"."vh_project"("tenant_id","id") ON DELETE restrict ON UPDATE no action;--> statement-breakpoint
ALTER TABLE "vh_root_cause_incident" ADD CONSTRAINT "vh_root_cause_incident_fk_2" FOREIGN KEY ("tenant_id","project_id","root_cause_finding_id") REFERENCES "public"."vh_root_cause_finding"("tenant_id","project_id","id") ON DELETE restrict ON UPDATE no action;--> statement-breakpoint
ALTER TABLE "vh_root_cause_incident" ADD CONSTRAINT "vh_root_cause_incident_fk_3" FOREIGN KEY ("tenant_id","project_id","related_incident_id") REFERENCES "public"."vh_incident"("tenant_id","project_id","id") ON DELETE restrict ON UPDATE no action;--> statement-breakpoint
ALTER TABLE "vh_file_object" ADD CONSTRAINT "vh_file_object_fk_0" FOREIGN KEY ("tenant_id") REFERENCES "public"."platform_tenant"("id") ON DELETE restrict ON UPDATE no action;--> statement-breakpoint
ALTER TABLE "vh_file_object" ADD CONSTRAINT "vh_file_object_fk_1" FOREIGN KEY ("uploaded_by_user_id") REFERENCES "public"."users"("id") ON DELETE restrict ON UPDATE no action;--> statement-breakpoint
ALTER TABLE "vh_case" ADD CONSTRAINT "vh_case_fk_0" FOREIGN KEY ("tenant_id") REFERENCES "public"."platform_tenant"("id") ON DELETE restrict ON UPDATE no action;--> statement-breakpoint
ALTER TABLE "vh_case" ADD CONSTRAINT "vh_case_fk_1" FOREIGN KEY ("tenant_id","project_id") REFERENCES "public"."vh_project"("tenant_id","id") ON DELETE restrict ON UPDATE no action;--> statement-breakpoint
ALTER TABLE "vh_case" ADD CONSTRAINT "vh_case_fk_2" FOREIGN KEY ("resident_user_id") REFERENCES "public"."users"("id") ON DELETE restrict ON UPDATE no action;--> statement-breakpoint
ALTER TABLE "vh_case" ADD CONSTRAINT "vh_case_fk_3" FOREIGN KEY ("tenant_id","project_id","apartment_id") REFERENCES "public"."vh_apartment"("tenant_id","project_id","id") ON DELETE restrict ON UPDATE no action;--> statement-breakpoint
ALTER TABLE "vh_case" ADD CONSTRAINT "vh_case_fk_4" FOREIGN KEY ("tenant_id","project_id","opened_by_membership_id") REFERENCES "public"."vh_property_membership"("tenant_id","project_id","id") ON DELETE restrict ON UPDATE no action;--> statement-breakpoint
ALTER TABLE "vh_case" ADD CONSTRAINT "vh_case_fk_5" FOREIGN KEY ("tenant_id","project_id","resident_user_id","opened_by_membership_id") REFERENCES "public"."vh_property_membership"("tenant_id","project_id","user_id","id") ON DELETE restrict ON UPDATE no action;--> statement-breakpoint
ALTER TABLE "vh_case" ADD CONSTRAINT "vh_case_fk_6" FOREIGN KEY ("tenant_id","project_id","apartment_id","opened_by_membership_id") REFERENCES "public"."vh_property_membership"("tenant_id","project_id","apartment_id","id") ON DELETE restrict ON UPDATE no action;--> statement-breakpoint
ALTER TABLE "vh_feedback" ADD CONSTRAINT "vh_feedback_fk_0" FOREIGN KEY ("tenant_id") REFERENCES "public"."platform_tenant"("id") ON DELETE restrict ON UPDATE no action;--> statement-breakpoint
ALTER TABLE "vh_feedback" ADD CONSTRAINT "vh_feedback_fk_1" FOREIGN KEY ("tenant_id","project_id") REFERENCES "public"."vh_project"("tenant_id","id") ON DELETE restrict ON UPDATE no action;--> statement-breakpoint
ALTER TABLE "vh_feedback" ADD CONSTRAINT "vh_feedback_fk_2" FOREIGN KEY ("tenant_id","project_id","report_id") REFERENCES "public"."vh_resident_report"("tenant_id","project_id","id") ON DELETE restrict ON UPDATE no action;--> statement-breakpoint
ALTER TABLE "vh_feedback" ADD CONSTRAINT "vh_feedback_fk_3" FOREIGN KEY ("author_user_id") REFERENCES "public"."users"("id") ON DELETE restrict ON UPDATE no action;--> statement-breakpoint
ALTER TABLE "vh_feedback" ADD CONSTRAINT "vh_feedback_fk_4" FOREIGN KEY ("tenant_id","author_user_id","report_id") REFERENCES "public"."vh_resident_report"("tenant_id","reporter_id","id") ON DELETE restrict ON UPDATE no action;--> statement-breakpoint
ALTER TABLE "vh_issue_candidate" ADD CONSTRAINT "vh_issue_candidate_fk_0" FOREIGN KEY ("tenant_id") REFERENCES "public"."platform_tenant"("id") ON DELETE restrict ON UPDATE no action;--> statement-breakpoint
ALTER TABLE "vh_issue_candidate" ADD CONSTRAINT "vh_issue_candidate_fk_1" FOREIGN KEY ("tenant_id","project_id") REFERENCES "public"."vh_project"("tenant_id","id") ON DELETE restrict ON UPDATE no action;--> statement-breakpoint
ALTER TABLE "vh_issue_candidate" ADD CONSTRAINT "vh_issue_candidate_fk_2" FOREIGN KEY ("tenant_id","project_id","case_id") REFERENCES "public"."vh_case"("tenant_id","project_id","id") ON DELETE restrict ON UPDATE no action;--> statement-breakpoint
ALTER TABLE "vh_issue_candidate" ADD CONSTRAINT "vh_issue_candidate_fk_3" FOREIGN KEY ("tenant_id","project_id","case_id","source_request_id") REFERENCES "public"."vh_resident_request"("tenant_id","project_id","case_id","id") ON DELETE restrict ON UPDATE no action;--> statement-breakpoint
ALTER TABLE "vh_issue_relation" ADD CONSTRAINT "vh_issue_relation_fk_0" FOREIGN KEY ("tenant_id") REFERENCES "public"."platform_tenant"("id") ON DELETE restrict ON UPDATE no action;--> statement-breakpoint
ALTER TABLE "vh_issue_relation" ADD CONSTRAINT "vh_issue_relation_fk_1" FOREIGN KEY ("tenant_id","project_id") REFERENCES "public"."vh_project"("tenant_id","id") ON DELETE restrict ON UPDATE no action;--> statement-breakpoint
ALTER TABLE "vh_issue_relation" ADD CONSTRAINT "vh_issue_relation_fk_2" FOREIGN KEY ("tenant_id","project_id","source_issue_id") REFERENCES "public"."vh_issue_candidate"("tenant_id","project_id","id") ON DELETE restrict ON UPDATE no action;--> statement-breakpoint
ALTER TABLE "vh_issue_relation" ADD CONSTRAINT "vh_issue_relation_fk_3" FOREIGN KEY ("tenant_id","project_id","target_issue_id") REFERENCES "public"."vh_issue_candidate"("tenant_id","project_id","id") ON DELETE restrict ON UPDATE no action;--> statement-breakpoint
ALTER TABLE "vh_resident_confirmation" ADD CONSTRAINT "vh_resident_confirmation_fk_0" FOREIGN KEY ("tenant_id") REFERENCES "public"."platform_tenant"("id") ON DELETE restrict ON UPDATE no action;--> statement-breakpoint
ALTER TABLE "vh_resident_confirmation" ADD CONSTRAINT "vh_resident_confirmation_fk_1" FOREIGN KEY ("tenant_id","project_id") REFERENCES "public"."vh_project"("tenant_id","id") ON DELETE restrict ON UPDATE no action;--> statement-breakpoint
ALTER TABLE "vh_resident_confirmation" ADD CONSTRAINT "vh_resident_confirmation_fk_2" FOREIGN KEY ("tenant_id","project_id","report_id") REFERENCES "public"."vh_resident_report"("tenant_id","project_id","id") ON DELETE restrict ON UPDATE no action;--> statement-breakpoint
ALTER TABLE "vh_resident_confirmation" ADD CONSTRAINT "vh_resident_confirmation_fk_3" FOREIGN KEY ("tenant_id","project_id","incident_id") REFERENCES "public"."vh_incident"("tenant_id","project_id","id") ON DELETE restrict ON UPDATE no action;--> statement-breakpoint
ALTER TABLE "vh_resident_confirmation" ADD CONSTRAINT "vh_resident_confirmation_fk_4" FOREIGN KEY ("confirmed_by_user_id") REFERENCES "public"."users"("id") ON DELETE restrict ON UPDATE no action;--> statement-breakpoint
ALTER TABLE "vh_resident_confirmation" ADD CONSTRAINT "vh_resident_confirmation_fk_5" FOREIGN KEY ("tenant_id","incident_id","confirmed_by_user_id","report_id") REFERENCES "public"."vh_resident_report"("tenant_id","incident_id","reporter_id","id") ON DELETE restrict ON UPDATE no action;--> statement-breakpoint
ALTER TABLE "vh_resident_report" ADD CONSTRAINT "vh_resident_report_fk_0" FOREIGN KEY ("tenant_id") REFERENCES "public"."platform_tenant"("id") ON DELETE restrict ON UPDATE no action;--> statement-breakpoint
ALTER TABLE "vh_resident_report" ADD CONSTRAINT "vh_resident_report_fk_1" FOREIGN KEY ("tenant_id","project_id") REFERENCES "public"."vh_project"("tenant_id","id") ON DELETE restrict ON UPDATE no action;--> statement-breakpoint
ALTER TABLE "vh_resident_report" ADD CONSTRAINT "vh_resident_report_fk_2" FOREIGN KEY ("tenant_id","project_id","case_id") REFERENCES "public"."vh_case"("tenant_id","project_id","id") ON DELETE restrict ON UPDATE no action;--> statement-breakpoint
ALTER TABLE "vh_resident_report" ADD CONSTRAINT "vh_resident_report_fk_3" FOREIGN KEY ("tenant_id","project_id","case_id","issue_candidate_id") REFERENCES "public"."vh_issue_candidate"("tenant_id","project_id","case_id","id") ON DELETE restrict ON UPDATE no action;--> statement-breakpoint
ALTER TABLE "vh_resident_report" ADD CONSTRAINT "vh_resident_report_fk_4" FOREIGN KEY ("tenant_id","project_id","incident_id") REFERENCES "public"."vh_incident"("tenant_id","project_id","id") ON DELETE restrict ON UPDATE no action;--> statement-breakpoint
ALTER TABLE "vh_resident_report" ADD CONSTRAINT "vh_resident_report_fk_5" FOREIGN KEY ("reporter_id") REFERENCES "public"."users"("id") ON DELETE restrict ON UPDATE no action;--> statement-breakpoint
ALTER TABLE "vh_resident_report" ADD CONSTRAINT "vh_resident_report_fk_6" FOREIGN KEY ("tenant_id","project_id","reporter_membership_id") REFERENCES "public"."vh_property_membership"("tenant_id","project_id","id") ON DELETE restrict ON UPDATE no action;--> statement-breakpoint
ALTER TABLE "vh_resident_report" ADD CONSTRAINT "vh_resident_report_fk_7" FOREIGN KEY ("tenant_id","project_id","apartment_id") REFERENCES "public"."vh_apartment"("tenant_id","project_id","id") ON DELETE restrict ON UPDATE no action;--> statement-breakpoint
ALTER TABLE "vh_resident_report" ADD CONSTRAINT "vh_resident_report_fk_8" FOREIGN KEY ("tenant_id","project_id","reporter_id","reporter_membership_id") REFERENCES "public"."vh_property_membership"("tenant_id","project_id","user_id","id") ON DELETE restrict ON UPDATE no action;--> statement-breakpoint
ALTER TABLE "vh_resident_report" ADD CONSTRAINT "vh_resident_report_fk_9" FOREIGN KEY ("tenant_id","project_id","apartment_id","reporter_membership_id") REFERENCES "public"."vh_property_membership"("tenant_id","project_id","apartment_id","id") ON DELETE restrict ON UPDATE no action;--> statement-breakpoint
ALTER TABLE "vh_resident_request" ADD CONSTRAINT "vh_resident_request_fk_0" FOREIGN KEY ("tenant_id") REFERENCES "public"."platform_tenant"("id") ON DELETE restrict ON UPDATE no action;--> statement-breakpoint
ALTER TABLE "vh_resident_request" ADD CONSTRAINT "vh_resident_request_fk_1" FOREIGN KEY ("tenant_id","project_id") REFERENCES "public"."vh_project"("tenant_id","id") ON DELETE restrict ON UPDATE no action;--> statement-breakpoint
ALTER TABLE "vh_resident_request" ADD CONSTRAINT "vh_resident_request_fk_2" FOREIGN KEY ("tenant_id","project_id","case_id") REFERENCES "public"."vh_case"("tenant_id","project_id","id") ON DELETE restrict ON UPDATE no action;--> statement-breakpoint
ALTER TABLE "vh_resident_request" ADD CONSTRAINT "vh_resident_request_fk_3" FOREIGN KEY ("submitted_by") REFERENCES "public"."users"("id") ON DELETE restrict ON UPDATE no action;--> statement-breakpoint
ALTER TABLE "vh_action_approval" ADD CONSTRAINT "vh_action_approval_fk_0" FOREIGN KEY ("tenant_id") REFERENCES "public"."platform_tenant"("id") ON DELETE restrict ON UPDATE no action;--> statement-breakpoint
ALTER TABLE "vh_action_approval" ADD CONSTRAINT "vh_action_approval_fk_1" FOREIGN KEY ("tenant_id","project_id") REFERENCES "public"."vh_project"("tenant_id","id") ON DELETE restrict ON UPDATE no action;--> statement-breakpoint
ALTER TABLE "vh_action_approval" ADD CONSTRAINT "vh_action_approval_fk_2" FOREIGN KEY ("tenant_id","project_id","action_request_id") REFERENCES "public"."vh_action_request"("tenant_id","project_id","id") ON DELETE restrict ON UPDATE no action;--> statement-breakpoint
ALTER TABLE "vh_action_approval" ADD CONSTRAINT "vh_action_approval_fk_3" FOREIGN KEY ("reviewer_id") REFERENCES "public"."users"("id") ON DELETE restrict ON UPDATE no action;--> statement-breakpoint
ALTER TABLE "vh_action_approval" ADD CONSTRAINT "vh_action_approval_fk_4" FOREIGN KEY ("tenant_id","action_request_id","action_payload_hash") REFERENCES "public"."vh_action_request"("tenant_id","id","payload_hash") ON DELETE restrict ON UPDATE no action;--> statement-breakpoint
ALTER TABLE "vh_action_approval" ADD CONSTRAINT "vh_action_approval_fk_5" FOREIGN KEY ("tenant_id","action_request_id","policy_version") REFERENCES "public"."vh_action_request"("tenant_id","id","policy_version") ON DELETE restrict ON UPDATE no action;--> statement-breakpoint
ALTER TABLE "vh_action_request" ADD CONSTRAINT "vh_action_request_fk_0" FOREIGN KEY ("tenant_id") REFERENCES "public"."platform_tenant"("id") ON DELETE restrict ON UPDATE no action;--> statement-breakpoint
ALTER TABLE "vh_action_request" ADD CONSTRAINT "vh_action_request_fk_1" FOREIGN KEY ("tenant_id","project_id") REFERENCES "public"."vh_project"("tenant_id","id") ON DELETE restrict ON UPDATE no action;--> statement-breakpoint
ALTER TABLE "vh_action_request" ADD CONSTRAINT "vh_action_request_fk_2" FOREIGN KEY ("tenant_id","project_id","incident_id") REFERENCES "public"."vh_incident"("tenant_id","project_id","id") ON DELETE restrict ON UPDATE no action;--> statement-breakpoint
ALTER TABLE "vh_action_request" ADD CONSTRAINT "vh_action_request_fk_3" FOREIGN KEY ("tenant_id","project_id","incident_id","task_id") REFERENCES "public"."vh_task"("tenant_id","project_id","incident_id","id") ON DELETE restrict ON UPDATE no action;--> statement-breakpoint
ALTER TABLE "vh_checklist" ADD CONSTRAINT "vh_checklist_fk_0" FOREIGN KEY ("tenant_id") REFERENCES "public"."platform_tenant"("id") ON DELETE restrict ON UPDATE no action;--> statement-breakpoint
ALTER TABLE "vh_checklist_version" ADD CONSTRAINT "vh_checklist_version_fk_0" FOREIGN KEY ("tenant_id") REFERENCES "public"."platform_tenant"("id") ON DELETE restrict ON UPDATE no action;--> statement-breakpoint
ALTER TABLE "vh_checklist_version" ADD CONSTRAINT "vh_checklist_version_fk_1" FOREIGN KEY ("tenant_id","checklist_id") REFERENCES "public"."vh_checklist"("tenant_id","id") ON DELETE restrict ON UPDATE no action;--> statement-breakpoint
ALTER TABLE "vh_checklist_version" ADD CONSTRAINT "vh_checklist_version_fk_2" FOREIGN KEY ("created_by") REFERENCES "public"."users"("id") ON DELETE restrict ON UPDATE no action;--> statement-breakpoint
ALTER TABLE "vh_execution_grant" ADD CONSTRAINT "vh_execution_grant_fk_0" FOREIGN KEY ("tenant_id") REFERENCES "public"."platform_tenant"("id") ON DELETE restrict ON UPDATE no action;--> statement-breakpoint
ALTER TABLE "vh_execution_grant" ADD CONSTRAINT "vh_execution_grant_fk_1" FOREIGN KEY ("tenant_id","project_id") REFERENCES "public"."vh_project"("tenant_id","id") ON DELETE restrict ON UPDATE no action;--> statement-breakpoint
ALTER TABLE "vh_execution_grant" ADD CONSTRAINT "vh_execution_grant_fk_2" FOREIGN KEY ("tenant_id","project_id","action_request_id") REFERENCES "public"."vh_action_request"("tenant_id","project_id","id") ON DELETE restrict ON UPDATE no action;--> statement-breakpoint
ALTER TABLE "vh_execution_grant" ADD CONSTRAINT "vh_execution_grant_fk_3" FOREIGN KEY ("tenant_id","action_request_id","action_payload_hash") REFERENCES "public"."vh_action_request"("tenant_id","id","payload_hash") ON DELETE restrict ON UPDATE no action;--> statement-breakpoint
ALTER TABLE "vh_execution_grant" ADD CONSTRAINT "vh_execution_grant_fk_4" FOREIGN KEY ("tenant_id","action_request_id","policy_version") REFERENCES "public"."vh_action_request"("tenant_id","id","policy_version") ON DELETE restrict ON UPDATE no action;--> statement-breakpoint
ALTER TABLE "vh_incident" ADD CONSTRAINT "vh_incident_fk_0" FOREIGN KEY ("tenant_id") REFERENCES "public"."platform_tenant"("id") ON DELETE restrict ON UPDATE no action;--> statement-breakpoint
ALTER TABLE "vh_incident" ADD CONSTRAINT "vh_incident_fk_1" FOREIGN KEY ("tenant_id","project_id") REFERENCES "public"."vh_project"("tenant_id","id") ON DELETE restrict ON UPDATE no action;--> statement-breakpoint
ALTER TABLE "vh_incident" ADD CONSTRAINT "vh_incident_fk_2" FOREIGN KEY ("tenant_id","project_id","tower_id") REFERENCES "public"."vh_tower"("tenant_id","project_id","id") ON DELETE restrict ON UPDATE no action;--> statement-breakpoint
ALTER TABLE "vh_incident" ADD CONSTRAINT "vh_incident_fk_3" FOREIGN KEY ("owner_user_id") REFERENCES "public"."users"("id") ON DELETE restrict ON UPDATE no action;--> statement-breakpoint
ALTER TABLE "vh_incident" ADD CONSTRAINT "vh_incident_fk_4" FOREIGN KEY ("closed_by_user_id") REFERENCES "public"."users"("id") ON DELETE restrict ON UPDATE no action;--> statement-breakpoint
ALTER TABLE "vh_incident_relation" ADD CONSTRAINT "vh_incident_relation_fk_0" FOREIGN KEY ("tenant_id") REFERENCES "public"."platform_tenant"("id") ON DELETE restrict ON UPDATE no action;--> statement-breakpoint
ALTER TABLE "vh_incident_relation" ADD CONSTRAINT "vh_incident_relation_fk_1" FOREIGN KEY ("tenant_id","project_id") REFERENCES "public"."vh_project"("tenant_id","id") ON DELETE restrict ON UPDATE no action;--> statement-breakpoint
ALTER TABLE "vh_incident_relation" ADD CONSTRAINT "vh_incident_relation_fk_2" FOREIGN KEY ("tenant_id","project_id","source_incident_id") REFERENCES "public"."vh_incident"("tenant_id","project_id","id") ON DELETE restrict ON UPDATE no action;--> statement-breakpoint
ALTER TABLE "vh_incident_relation" ADD CONSTRAINT "vh_incident_relation_fk_3" FOREIGN KEY ("tenant_id","project_id","target_incident_id") REFERENCES "public"."vh_incident"("tenant_id","project_id","id") ON DELETE restrict ON UPDATE no action;--> statement-breakpoint
ALTER TABLE "vh_incident_relation" ADD CONSTRAINT "vh_incident_relation_fk_4" FOREIGN KEY ("created_by") REFERENCES "public"."users"("id") ON DELETE restrict ON UPDATE no action;--> statement-breakpoint
ALTER TABLE "vh_rule_evaluation" ADD CONSTRAINT "vh_rule_evaluation_fk_0" FOREIGN KEY ("tenant_id") REFERENCES "public"."platform_tenant"("id") ON DELETE restrict ON UPDATE no action;--> statement-breakpoint
ALTER TABLE "vh_rule_evaluation" ADD CONSTRAINT "vh_rule_evaluation_fk_1" FOREIGN KEY ("tenant_id","project_id") REFERENCES "public"."vh_project"("tenant_id","id") ON DELETE restrict ON UPDATE no action;--> statement-breakpoint
ALTER TABLE "vh_rule_evaluation" ADD CONSTRAINT "vh_rule_evaluation_fk_2" FOREIGN KEY ("tenant_id","project_id","action_request_id") REFERENCES "public"."vh_action_request"("tenant_id","project_id","id") ON DELETE restrict ON UPDATE no action;--> statement-breakpoint
ALTER TABLE "vh_rule_evaluation" ADD CONSTRAINT "vh_rule_evaluation_fk_3" FOREIGN KEY ("tenant_id","action_request_id","action_payload_hash") REFERENCES "public"."vh_action_request"("tenant_id","id","payload_hash") ON DELETE restrict ON UPDATE no action;--> statement-breakpoint
ALTER TABLE "vh_task" ADD CONSTRAINT "vh_task_fk_0" FOREIGN KEY ("tenant_id") REFERENCES "public"."platform_tenant"("id") ON DELETE restrict ON UPDATE no action;--> statement-breakpoint
ALTER TABLE "vh_task" ADD CONSTRAINT "vh_task_fk_1" FOREIGN KEY ("tenant_id","project_id") REFERENCES "public"."vh_project"("tenant_id","id") ON DELETE restrict ON UPDATE no action;--> statement-breakpoint
ALTER TABLE "vh_task" ADD CONSTRAINT "vh_task_fk_2" FOREIGN KEY ("tenant_id","project_id","incident_id") REFERENCES "public"."vh_incident"("tenant_id","project_id","id") ON DELETE restrict ON UPDATE no action;--> statement-breakpoint
ALTER TABLE "vh_task_dependency" ADD CONSTRAINT "vh_task_dependency_fk_0" FOREIGN KEY ("tenant_id") REFERENCES "public"."platform_tenant"("id") ON DELETE restrict ON UPDATE no action;--> statement-breakpoint
ALTER TABLE "vh_task_dependency" ADD CONSTRAINT "vh_task_dependency_fk_1" FOREIGN KEY ("tenant_id","project_id") REFERENCES "public"."vh_project"("tenant_id","id") ON DELETE restrict ON UPDATE no action;--> statement-breakpoint
ALTER TABLE "vh_task_dependency" ADD CONSTRAINT "vh_task_dependency_fk_2" FOREIGN KEY ("tenant_id","project_id","incident_id") REFERENCES "public"."vh_incident"("tenant_id","project_id","id") ON DELETE restrict ON UPDATE no action;--> statement-breakpoint
ALTER TABLE "vh_task_dependency" ADD CONSTRAINT "vh_task_dependency_fk_3" FOREIGN KEY ("tenant_id","project_id","incident_id","task_id") REFERENCES "public"."vh_task"("tenant_id","project_id","incident_id","id") ON DELETE restrict ON UPDATE no action;--> statement-breakpoint
ALTER TABLE "vh_task_dependency" ADD CONSTRAINT "vh_task_dependency_fk_4" FOREIGN KEY ("tenant_id","project_id","incident_id","depends_on_task_id") REFERENCES "public"."vh_task"("tenant_id","project_id","incident_id","id") ON DELETE restrict ON UPDATE no action;--> statement-breakpoint
ALTER TABLE "vh_work_order" ADD CONSTRAINT "vh_work_order_fk_0" FOREIGN KEY ("tenant_id") REFERENCES "public"."platform_tenant"("id") ON DELETE restrict ON UPDATE no action;--> statement-breakpoint
ALTER TABLE "vh_work_order" ADD CONSTRAINT "vh_work_order_fk_1" FOREIGN KEY ("tenant_id","project_id") REFERENCES "public"."vh_project"("tenant_id","id") ON DELETE restrict ON UPDATE no action;--> statement-breakpoint
ALTER TABLE "vh_work_order" ADD CONSTRAINT "vh_work_order_fk_2" FOREIGN KEY ("tenant_id","project_id","incident_id") REFERENCES "public"."vh_incident"("tenant_id","project_id","id") ON DELETE restrict ON UPDATE no action;--> statement-breakpoint
ALTER TABLE "vh_work_order" ADD CONSTRAINT "vh_work_order_fk_3" FOREIGN KEY ("tenant_id","project_id","incident_id","task_id") REFERENCES "public"."vh_task"("tenant_id","project_id","incident_id","id") ON DELETE restrict ON UPDATE no action;--> statement-breakpoint
ALTER TABLE "vh_work_order" ADD CONSTRAINT "vh_work_order_fk_4" FOREIGN KEY ("tenant_id","project_id","incident_id","task_id","action_request_id") REFERENCES "public"."vh_action_request"("tenant_id","project_id","incident_id","task_id","id") ON DELETE restrict ON UPDATE no action;--> statement-breakpoint
ALTER TABLE "vh_work_order" ADD CONSTRAINT "vh_work_order_fk_5" FOREIGN KEY ("tenant_id","project_id","incident_id","task_id","redo_of_work_order_id") REFERENCES "public"."vh_work_order"("tenant_id","project_id","incident_id","task_id","id") ON DELETE restrict ON UPDATE no action;--> statement-breakpoint
ALTER TABLE "vh_work_order" ADD CONSTRAINT "vh_work_order_fk_6" FOREIGN KEY ("tenant_id","checklist_version_id") REFERENCES "public"."vh_checklist_version"("tenant_id","id") ON DELETE restrict ON UPDATE no action;--> statement-breakpoint
ALTER TABLE "vh_apartment" ADD CONSTRAINT "vh_apartment_fk_0" FOREIGN KEY ("tenant_id") REFERENCES "public"."platform_tenant"("id") ON DELETE restrict ON UPDATE no action;--> statement-breakpoint
ALTER TABLE "vh_apartment" ADD CONSTRAINT "vh_apartment_fk_1" FOREIGN KEY ("tenant_id","project_id") REFERENCES "public"."vh_project"("tenant_id","id") ON DELETE restrict ON UPDATE no action;--> statement-breakpoint
ALTER TABLE "vh_apartment" ADD CONSTRAINT "vh_apartment_fk_2" FOREIGN KEY ("tenant_id","project_id","tower_id") REFERENCES "public"."vh_tower"("tenant_id","project_id","id") ON DELETE restrict ON UPDATE no action;--> statement-breakpoint
ALTER TABLE "vh_membership_application" ADD CONSTRAINT "vh_membership_application_fk_0" FOREIGN KEY ("tenant_id") REFERENCES "public"."platform_tenant"("id") ON DELETE restrict ON UPDATE no action;--> statement-breakpoint
ALTER TABLE "vh_membership_application" ADD CONSTRAINT "vh_membership_application_fk_1" FOREIGN KEY ("tenant_id","project_id") REFERENCES "public"."vh_project"("tenant_id","id") ON DELETE restrict ON UPDATE no action;--> statement-breakpoint
ALTER TABLE "vh_membership_application" ADD CONSTRAINT "vh_membership_application_fk_2" FOREIGN KEY ("tenant_id","project_id","requested_apartment_id") REFERENCES "public"."vh_apartment"("tenant_id","project_id","id") ON DELETE restrict ON UPDATE no action;--> statement-breakpoint
ALTER TABLE "vh_membership_application" ADD CONSTRAINT "vh_membership_application_fk_3" FOREIGN KEY ("applicant_user_id") REFERENCES "public"."users"("id") ON DELETE restrict ON UPDATE no action;--> statement-breakpoint
ALTER TABLE "vh_membership_application" ADD CONSTRAINT "vh_membership_application_fk_4" FOREIGN KEY ("reviewed_by") REFERENCES "public"."users"("id") ON DELETE restrict ON UPDATE no action;--> statement-breakpoint
ALTER TABLE "vh_project" ADD CONSTRAINT "vh_project_fk_0" FOREIGN KEY ("tenant_id") REFERENCES "public"."platform_tenant"("id") ON DELETE restrict ON UPDATE no action;--> statement-breakpoint
ALTER TABLE "vh_property_membership" ADD CONSTRAINT "vh_property_membership_fk_0" FOREIGN KEY ("tenant_id") REFERENCES "public"."platform_tenant"("id") ON DELETE restrict ON UPDATE no action;--> statement-breakpoint
ALTER TABLE "vh_property_membership" ADD CONSTRAINT "vh_property_membership_fk_1" FOREIGN KEY ("tenant_id","project_id") REFERENCES "public"."vh_project"("tenant_id","id") ON DELETE restrict ON UPDATE no action;--> statement-breakpoint
ALTER TABLE "vh_property_membership" ADD CONSTRAINT "vh_property_membership_fk_2" FOREIGN KEY ("user_id") REFERENCES "public"."users"("id") ON DELETE restrict ON UPDATE no action;--> statement-breakpoint
ALTER TABLE "vh_property_membership" ADD CONSTRAINT "vh_property_membership_fk_3" FOREIGN KEY ("tenant_id","project_id","tower_id") REFERENCES "public"."vh_tower"("tenant_id","project_id","id") ON DELETE restrict ON UPDATE no action;--> statement-breakpoint
ALTER TABLE "vh_property_membership" ADD CONSTRAINT "vh_property_membership_fk_4" FOREIGN KEY ("tenant_id","project_id","tower_id","apartment_id") REFERENCES "public"."vh_apartment"("tenant_id","project_id","tower_id","id") ON DELETE restrict ON UPDATE no action;--> statement-breakpoint
ALTER TABLE "vh_property_membership" ADD CONSTRAINT "vh_property_membership_fk_5" FOREIGN KEY ("granted_by_user_id") REFERENCES "public"."users"("id") ON DELETE restrict ON UPDATE no action;--> statement-breakpoint
ALTER TABLE "vh_property_membership" ADD CONSTRAINT "vh_property_membership_fk_6" FOREIGN KEY ("tenant_id","user_id") REFERENCES "public"."platform_tenant_membership"("tenant_id","user_id") ON DELETE restrict ON UPDATE no action;--> statement-breakpoint
ALTER TABLE "vh_tower" ADD CONSTRAINT "vh_tower_fk_0" FOREIGN KEY ("tenant_id") REFERENCES "public"."platform_tenant"("id") ON DELETE restrict ON UPDATE no action;--> statement-breakpoint
ALTER TABLE "vh_tower" ADD CONSTRAINT "vh_tower_fk_1" FOREIGN KEY ("tenant_id","project_id") REFERENCES "public"."vh_project"("tenant_id","id") ON DELETE restrict ON UPDATE no action;--> statement-breakpoint
ALTER TABLE "vh_access_card" ADD CONSTRAINT "vh_access_card_fk_0" FOREIGN KEY ("tenant_id") REFERENCES "public"."platform_tenant"("id") ON DELETE restrict ON UPDATE no action;--> statement-breakpoint
ALTER TABLE "vh_access_card" ADD CONSTRAINT "vh_access_card_fk_1" FOREIGN KEY ("tenant_id","project_id") REFERENCES "public"."vh_project"("tenant_id","id") ON DELETE restrict ON UPDATE no action;--> statement-breakpoint
ALTER TABLE "vh_access_card" ADD CONSTRAINT "vh_access_card_fk_2" FOREIGN KEY ("tenant_id","project_id","membership_id") REFERENCES "public"."vh_property_membership"("tenant_id","project_id","id") ON DELETE restrict ON UPDATE no action;--> statement-breakpoint
ALTER TABLE "vh_camera_request" ADD CONSTRAINT "vh_camera_request_fk_0" FOREIGN KEY ("tenant_id") REFERENCES "public"."platform_tenant"("id") ON DELETE restrict ON UPDATE no action;--> statement-breakpoint
ALTER TABLE "vh_camera_request" ADD CONSTRAINT "vh_camera_request_fk_1" FOREIGN KEY ("tenant_id","project_id") REFERENCES "public"."vh_project"("tenant_id","id") ON DELETE restrict ON UPDATE no action;--> statement-breakpoint
ALTER TABLE "vh_camera_request" ADD CONSTRAINT "vh_camera_request_fk_2" FOREIGN KEY ("tenant_id","project_id","apartment_id") REFERENCES "public"."vh_apartment"("tenant_id","project_id","id") ON DELETE restrict ON UPDATE no action;--> statement-breakpoint
ALTER TABLE "vh_camera_request" ADD CONSTRAINT "vh_camera_request_fk_3" FOREIGN KEY ("tenant_id","project_id","requester_membership_id") REFERENCES "public"."vh_property_membership"("tenant_id","project_id","id") ON DELETE restrict ON UPDATE no action;--> statement-breakpoint
ALTER TABLE "vh_camera_request" ADD CONSTRAINT "vh_camera_request_fk_4" FOREIGN KEY ("tenant_id","project_id","location_place_id") REFERENCES "public"."vh_map_place"("tenant_id","project_id","id") ON DELETE restrict ON UPDATE no action;--> statement-breakpoint
ALTER TABLE "vh_camera_request" ADD CONSTRAINT "vh_camera_request_fk_5" FOREIGN KEY ("reviewed_by") REFERENCES "public"."users"("id") ON DELETE restrict ON UPDATE no action;--> statement-breakpoint
ALTER TABLE "vh_camera_request" ADD CONSTRAINT "vh_camera_request_fk_6" FOREIGN KEY ("tenant_id","project_id","apartment_id","requester_membership_id") REFERENCES "public"."vh_property_membership"("tenant_id","project_id","apartment_id","id") ON DELETE restrict ON UPDATE no action;--> statement-breakpoint
ALTER TABLE "vh_charging_session" ADD CONSTRAINT "vh_charging_session_fk_0" FOREIGN KEY ("tenant_id") REFERENCES "public"."platform_tenant"("id") ON DELETE restrict ON UPDATE no action;--> statement-breakpoint
ALTER TABLE "vh_charging_session" ADD CONSTRAINT "vh_charging_session_fk_1" FOREIGN KEY ("tenant_id","project_id") REFERENCES "public"."vh_project"("tenant_id","id") ON DELETE restrict ON UPDATE no action;--> statement-breakpoint
ALTER TABLE "vh_charging_session" ADD CONSTRAINT "vh_charging_session_fk_2" FOREIGN KEY ("tenant_id","project_id","apartment_id") REFERENCES "public"."vh_apartment"("tenant_id","project_id","id") ON DELETE restrict ON UPDATE no action;--> statement-breakpoint
ALTER TABLE "vh_charging_session" ADD CONSTRAINT "vh_charging_session_fk_3" FOREIGN KEY ("tenant_id","project_id","requested_by_membership_id") REFERENCES "public"."vh_property_membership"("tenant_id","project_id","id") ON DELETE restrict ON UPDATE no action;--> statement-breakpoint
ALTER TABLE "vh_charging_session" ADD CONSTRAINT "vh_charging_session_fk_4" FOREIGN KEY ("tenant_id","project_id","station_place_id") REFERENCES "public"."vh_map_place"("tenant_id","project_id","id") ON DELETE restrict ON UPDATE no action;--> statement-breakpoint
ALTER TABLE "vh_charging_session" ADD CONSTRAINT "vh_charging_session_fk_5" FOREIGN KEY ("tenant_id","project_id","apartment_id","requested_by_membership_id") REFERENCES "public"."vh_property_membership"("tenant_id","project_id","apartment_id","id") ON DELETE restrict ON UPDATE no action;--> statement-breakpoint
ALTER TABLE "vh_construction_permit" ADD CONSTRAINT "vh_construction_permit_fk_0" FOREIGN KEY ("tenant_id") REFERENCES "public"."platform_tenant"("id") ON DELETE restrict ON UPDATE no action;--> statement-breakpoint
ALTER TABLE "vh_construction_permit" ADD CONSTRAINT "vh_construction_permit_fk_1" FOREIGN KEY ("tenant_id","project_id") REFERENCES "public"."vh_project"("tenant_id","id") ON DELETE restrict ON UPDATE no action;--> statement-breakpoint
ALTER TABLE "vh_construction_permit" ADD CONSTRAINT "vh_construction_permit_fk_2" FOREIGN KEY ("tenant_id","project_id","service_request_id") REFERENCES "public"."vh_service_request"("tenant_id","project_id","id") ON DELETE restrict ON UPDATE no action;--> statement-breakpoint
ALTER TABLE "vh_face_enrollment" ADD CONSTRAINT "vh_face_enrollment_fk_0" FOREIGN KEY ("tenant_id") REFERENCES "public"."platform_tenant"("id") ON DELETE restrict ON UPDATE no action;--> statement-breakpoint
ALTER TABLE "vh_face_enrollment" ADD CONSTRAINT "vh_face_enrollment_fk_1" FOREIGN KEY ("tenant_id","project_id") REFERENCES "public"."vh_project"("tenant_id","id") ON DELETE restrict ON UPDATE no action;--> statement-breakpoint
ALTER TABLE "vh_face_enrollment" ADD CONSTRAINT "vh_face_enrollment_fk_2" FOREIGN KEY ("tenant_id","project_id","membership_id") REFERENCES "public"."vh_property_membership"("tenant_id","project_id","id") ON DELETE restrict ON UPDATE no action;--> statement-breakpoint
ALTER TABLE "vh_handover" ADD CONSTRAINT "vh_handover_fk_0" FOREIGN KEY ("tenant_id") REFERENCES "public"."platform_tenant"("id") ON DELETE restrict ON UPDATE no action;--> statement-breakpoint
ALTER TABLE "vh_handover" ADD CONSTRAINT "vh_handover_fk_1" FOREIGN KEY ("tenant_id","project_id") REFERENCES "public"."vh_project"("tenant_id","id") ON DELETE restrict ON UPDATE no action;--> statement-breakpoint
ALTER TABLE "vh_handover" ADD CONSTRAINT "vh_handover_fk_2" FOREIGN KEY ("tenant_id","project_id","apartment_id") REFERENCES "public"."vh_apartment"("tenant_id","project_id","id") ON DELETE restrict ON UPDATE no action;--> statement-breakpoint
ALTER TABLE "vh_handover" ADD CONSTRAINT "vh_handover_fk_3" FOREIGN KEY ("tenant_id","project_id","resident_membership_id") REFERENCES "public"."vh_property_membership"("tenant_id","project_id","id") ON DELETE restrict ON UPDATE no action;--> statement-breakpoint
ALTER TABLE "vh_handover" ADD CONSTRAINT "vh_handover_fk_4" FOREIGN KEY ("tenant_id","checklist_version_id") REFERENCES "public"."vh_checklist_version"("tenant_id","id") ON DELETE restrict ON UPDATE no action;--> statement-breakpoint
ALTER TABLE "vh_handover" ADD CONSTRAINT "vh_handover_fk_5" FOREIGN KEY ("tenant_id","project_id","apartment_id","resident_membership_id") REFERENCES "public"."vh_property_membership"("tenant_id","project_id","apartment_id","id") ON DELETE restrict ON UPDATE no action;--> statement-breakpoint
ALTER TABLE "vh_intercom_event" ADD CONSTRAINT "vh_intercom_event_fk_0" FOREIGN KEY ("tenant_id") REFERENCES "public"."platform_tenant"("id") ON DELETE restrict ON UPDATE no action;--> statement-breakpoint
ALTER TABLE "vh_intercom_event" ADD CONSTRAINT "vh_intercom_event_fk_1" FOREIGN KEY ("tenant_id","project_id") REFERENCES "public"."vh_project"("tenant_id","id") ON DELETE restrict ON UPDATE no action;--> statement-breakpoint
ALTER TABLE "vh_intercom_event" ADD CONSTRAINT "vh_intercom_event_fk_2" FOREIGN KEY ("tenant_id","project_id","apartment_id") REFERENCES "public"."vh_apartment"("tenant_id","project_id","id") ON DELETE restrict ON UPDATE no action;--> statement-breakpoint
ALTER TABLE "vh_intercom_event" ADD CONSTRAINT "vh_intercom_event_fk_3" FOREIGN KEY ("tenant_id","project_id","visitor_pass_id") REFERENCES "public"."vh_visitor_pass"("tenant_id","project_id","id") ON DELETE restrict ON UPDATE no action;--> statement-breakpoint
ALTER TABLE "vh_parking_permit" ADD CONSTRAINT "vh_parking_permit_fk_0" FOREIGN KEY ("tenant_id") REFERENCES "public"."platform_tenant"("id") ON DELETE restrict ON UPDATE no action;--> statement-breakpoint
ALTER TABLE "vh_parking_permit" ADD CONSTRAINT "vh_parking_permit_fk_1" FOREIGN KEY ("tenant_id","project_id") REFERENCES "public"."vh_project"("tenant_id","id") ON DELETE restrict ON UPDATE no action;--> statement-breakpoint
ALTER TABLE "vh_parking_permit" ADD CONSTRAINT "vh_parking_permit_fk_2" FOREIGN KEY ("tenant_id","project_id","apartment_id") REFERENCES "public"."vh_apartment"("tenant_id","project_id","id") ON DELETE restrict ON UPDATE no action;--> statement-breakpoint
ALTER TABLE "vh_parking_permit" ADD CONSTRAINT "vh_parking_permit_fk_3" FOREIGN KEY ("tenant_id","project_id","membership_id") REFERENCES "public"."vh_property_membership"("tenant_id","project_id","id") ON DELETE restrict ON UPDATE no action;--> statement-breakpoint
ALTER TABLE "vh_parking_permit" ADD CONSTRAINT "vh_parking_permit_fk_4" FOREIGN KEY ("tenant_id","project_id","apartment_id","membership_id") REFERENCES "public"."vh_property_membership"("tenant_id","project_id","apartment_id","id") ON DELETE restrict ON UPDATE no action;--> statement-breakpoint
ALTER TABLE "vh_pet_profile" ADD CONSTRAINT "vh_pet_profile_fk_0" FOREIGN KEY ("tenant_id") REFERENCES "public"."platform_tenant"("id") ON DELETE restrict ON UPDATE no action;--> statement-breakpoint
ALTER TABLE "vh_pet_profile" ADD CONSTRAINT "vh_pet_profile_fk_1" FOREIGN KEY ("tenant_id","project_id") REFERENCES "public"."vh_project"("tenant_id","id") ON DELETE restrict ON UPDATE no action;--> statement-breakpoint
ALTER TABLE "vh_pet_profile" ADD CONSTRAINT "vh_pet_profile_fk_2" FOREIGN KEY ("tenant_id","project_id","apartment_id") REFERENCES "public"."vh_apartment"("tenant_id","project_id","id") ON DELETE restrict ON UPDATE no action;--> statement-breakpoint
ALTER TABLE "vh_pet_profile" ADD CONSTRAINT "vh_pet_profile_fk_3" FOREIGN KEY ("tenant_id","project_id","owner_membership_id") REFERENCES "public"."vh_property_membership"("tenant_id","project_id","id") ON DELETE restrict ON UPDATE no action;--> statement-breakpoint
ALTER TABLE "vh_pet_profile" ADD CONSTRAINT "vh_pet_profile_fk_4" FOREIGN KEY ("tenant_id","project_id","apartment_id","owner_membership_id") REFERENCES "public"."vh_property_membership"("tenant_id","project_id","apartment_id","id") ON DELETE restrict ON UPDATE no action;--> statement-breakpoint
ALTER TABLE "vh_service_request" ADD CONSTRAINT "vh_service_request_fk_0" FOREIGN KEY ("tenant_id") REFERENCES "public"."platform_tenant"("id") ON DELETE restrict ON UPDATE no action;--> statement-breakpoint
ALTER TABLE "vh_service_request" ADD CONSTRAINT "vh_service_request_fk_1" FOREIGN KEY ("tenant_id","project_id") REFERENCES "public"."vh_project"("tenant_id","id") ON DELETE restrict ON UPDATE no action;--> statement-breakpoint
ALTER TABLE "vh_service_request" ADD CONSTRAINT "vh_service_request_fk_2" FOREIGN KEY ("tenant_id","project_id","apartment_id") REFERENCES "public"."vh_apartment"("tenant_id","project_id","id") ON DELETE restrict ON UPDATE no action;--> statement-breakpoint
ALTER TABLE "vh_service_request" ADD CONSTRAINT "vh_service_request_fk_3" FOREIGN KEY ("tenant_id","project_id","requester_membership_id") REFERENCES "public"."vh_property_membership"("tenant_id","project_id","id") ON DELETE restrict ON UPDATE no action;--> statement-breakpoint
ALTER TABLE "vh_service_request" ADD CONSTRAINT "vh_service_request_fk_4" FOREIGN KEY ("tenant_id","project_id","apartment_id","requester_membership_id") REFERENCES "public"."vh_property_membership"("tenant_id","project_id","apartment_id","id") ON DELETE restrict ON UPDATE no action;--> statement-breakpoint
ALTER TABLE "vh_visitor_pass" ADD CONSTRAINT "vh_visitor_pass_fk_0" FOREIGN KEY ("tenant_id") REFERENCES "public"."platform_tenant"("id") ON DELETE restrict ON UPDATE no action;--> statement-breakpoint
ALTER TABLE "vh_visitor_pass" ADD CONSTRAINT "vh_visitor_pass_fk_1" FOREIGN KEY ("tenant_id","project_id") REFERENCES "public"."vh_project"("tenant_id","id") ON DELETE restrict ON UPDATE no action;--> statement-breakpoint
ALTER TABLE "vh_visitor_pass" ADD CONSTRAINT "vh_visitor_pass_fk_2" FOREIGN KEY ("tenant_id","project_id","service_request_id") REFERENCES "public"."vh_service_request"("tenant_id","project_id","id") ON DELETE restrict ON UPDATE no action;--> statement-breakpoint
ALTER TABLE "platform_agent" ADD CONSTRAINT "platform_agent_fk_0" FOREIGN KEY ("tenant_id") REFERENCES "public"."platform_tenant"("id") ON DELETE restrict ON UPDATE no action;--> statement-breakpoint
ALTER TABLE "platform_agent_change_request" ADD CONSTRAINT "platform_agent_change_request_fk_0" FOREIGN KEY ("tenant_id") REFERENCES "public"."platform_tenant"("id") ON DELETE restrict ON UPDATE no action;--> statement-breakpoint
ALTER TABLE "platform_agent_change_request" ADD CONSTRAINT "platform_agent_change_request_fk_1" FOREIGN KEY ("tenant_id","agent_id") REFERENCES "public"."platform_agent"("tenant_id","id") ON DELETE restrict ON UPDATE no action;--> statement-breakpoint
ALTER TABLE "platform_agent_change_request" ADD CONSTRAINT "platform_agent_change_request_fk_2" FOREIGN KEY ("requested_by") REFERENCES "public"."users"("id") ON DELETE restrict ON UPDATE no action;--> statement-breakpoint
ALTER TABLE "platform_agent_spec" ADD CONSTRAINT "platform_agent_spec_fk_0" FOREIGN KEY ("tenant_id") REFERENCES "public"."platform_tenant"("id") ON DELETE restrict ON UPDATE no action;--> statement-breakpoint
ALTER TABLE "platform_agent_spec" ADD CONSTRAINT "platform_agent_spec_fk_1" FOREIGN KEY ("tenant_id","agent_version_id") REFERENCES "public"."platform_agent_version"("tenant_id","id") ON DELETE restrict ON UPDATE no action;--> statement-breakpoint
ALTER TABLE "platform_agent_version" ADD CONSTRAINT "platform_agent_version_fk_0" FOREIGN KEY ("tenant_id") REFERENCES "public"."platform_tenant"("id") ON DELETE restrict ON UPDATE no action;--> statement-breakpoint
ALTER TABLE "platform_agent_version" ADD CONSTRAINT "platform_agent_version_fk_1" FOREIGN KEY ("tenant_id","agent_id") REFERENCES "public"."platform_agent"("tenant_id","id") ON DELETE restrict ON UPDATE no action;--> statement-breakpoint
ALTER TABLE "platform_agent_version" ADD CONSTRAINT "platform_agent_version_fk_2" FOREIGN KEY ("created_by") REFERENCES "public"."users"("id") ON DELETE restrict ON UPDATE no action;--> statement-breakpoint
ALTER TABLE "platform_audit_event" ADD CONSTRAINT "platform_audit_event_fk_0" FOREIGN KEY ("tenant_id") REFERENCES "public"."platform_tenant"("id") ON DELETE restrict ON UPDATE no action;--> statement-breakpoint
ALTER TABLE "platform_idempotency_record" ADD CONSTRAINT "platform_idempotency_record_fk_0" FOREIGN KEY ("tenant_id") REFERENCES "public"."platform_tenant"("id") ON DELETE restrict ON UPDATE no action;--> statement-breakpoint
ALTER TABLE "platform_outbox_event" ADD CONSTRAINT "platform_outbox_event_fk_0" FOREIGN KEY ("tenant_id") REFERENCES "public"."platform_tenant"("id") ON DELETE restrict ON UPDATE no action;--> statement-breakpoint
ALTER TABLE "platform_agent_capability_binding" ADD CONSTRAINT "platform_agent_capability_binding_fk_0" FOREIGN KEY ("tenant_id") REFERENCES "public"."platform_tenant"("id") ON DELETE restrict ON UPDATE no action;--> statement-breakpoint
ALTER TABLE "platform_agent_capability_binding" ADD CONSTRAINT "platform_agent_capability_binding_fk_1" FOREIGN KEY ("tenant_id","agent_version_id") REFERENCES "public"."platform_agent_version"("tenant_id","id") ON DELETE restrict ON UPDATE no action;--> statement-breakpoint
ALTER TABLE "platform_agent_capability_binding" ADD CONSTRAINT "platform_agent_capability_binding_fk_2" FOREIGN KEY ("tenant_id","capability_id") REFERENCES "public"."platform_capability"("tenant_id","id") ON DELETE restrict ON UPDATE no action;--> statement-breakpoint
ALTER TABLE "platform_agent_knowledge_binding" ADD CONSTRAINT "platform_agent_knowledge_binding_fk_0" FOREIGN KEY ("tenant_id") REFERENCES "public"."platform_tenant"("id") ON DELETE restrict ON UPDATE no action;--> statement-breakpoint
ALTER TABLE "platform_agent_knowledge_binding" ADD CONSTRAINT "platform_agent_knowledge_binding_fk_1" FOREIGN KEY ("tenant_id","agent_version_id") REFERENCES "public"."platform_agent_version"("tenant_id","id") ON DELETE restrict ON UPDATE no action;--> statement-breakpoint
ALTER TABLE "platform_agent_knowledge_binding" ADD CONSTRAINT "platform_agent_knowledge_binding_fk_2" FOREIGN KEY ("tenant_id","knowledge_base_id") REFERENCES "public"."platform_knowledge_base"("tenant_id","id") ON DELETE restrict ON UPDATE no action;--> statement-breakpoint
ALTER TABLE "platform_agent_model_binding" ADD CONSTRAINT "platform_agent_model_binding_fk_0" FOREIGN KEY ("tenant_id") REFERENCES "public"."platform_tenant"("id") ON DELETE restrict ON UPDATE no action;--> statement-breakpoint
ALTER TABLE "platform_agent_model_binding" ADD CONSTRAINT "platform_agent_model_binding_fk_1" FOREIGN KEY ("tenant_id","agent_version_id") REFERENCES "public"."platform_agent_version"("tenant_id","id") ON DELETE restrict ON UPDATE no action;--> statement-breakpoint
ALTER TABLE "platform_agent_model_binding" ADD CONSTRAINT "platform_agent_model_binding_fk_2" FOREIGN KEY ("tenant_id","model_profile_id") REFERENCES "public"."platform_model_profile"("tenant_id","id") ON DELETE restrict ON UPDATE no action;--> statement-breakpoint
ALTER TABLE "platform_agent_policy_binding" ADD CONSTRAINT "platform_agent_policy_binding_fk_0" FOREIGN KEY ("tenant_id") REFERENCES "public"."platform_tenant"("id") ON DELETE restrict ON UPDATE no action;--> statement-breakpoint
ALTER TABLE "platform_agent_policy_binding" ADD CONSTRAINT "platform_agent_policy_binding_fk_1" FOREIGN KEY ("tenant_id","agent_version_id") REFERENCES "public"."platform_agent_version"("tenant_id","id") ON DELETE restrict ON UPDATE no action;--> statement-breakpoint
ALTER TABLE "platform_agent_policy_binding" ADD CONSTRAINT "platform_agent_policy_binding_fk_2" FOREIGN KEY ("tenant_id","policy_version_id") REFERENCES "public"."platform_policy_version"("tenant_id","id") ON DELETE restrict ON UPDATE no action;--> statement-breakpoint
ALTER TABLE "platform_agent_skill_binding" ADD CONSTRAINT "platform_agent_skill_binding_fk_0" FOREIGN KEY ("tenant_id") REFERENCES "public"."platform_tenant"("id") ON DELETE restrict ON UPDATE no action;--> statement-breakpoint
ALTER TABLE "platform_agent_skill_binding" ADD CONSTRAINT "platform_agent_skill_binding_fk_1" FOREIGN KEY ("tenant_id","agent_version_id") REFERENCES "public"."platform_agent_version"("tenant_id","id") ON DELETE restrict ON UPDATE no action;--> statement-breakpoint
ALTER TABLE "platform_agent_skill_binding" ADD CONSTRAINT "platform_agent_skill_binding_fk_2" FOREIGN KEY ("tenant_id","skill_version_id") REFERENCES "public"."platform_skill_version"("tenant_id","id") ON DELETE restrict ON UPDATE no action;--> statement-breakpoint
ALTER TABLE "platform_agent_tool_binding" ADD CONSTRAINT "platform_agent_tool_binding_fk_0" FOREIGN KEY ("tenant_id") REFERENCES "public"."platform_tenant"("id") ON DELETE restrict ON UPDATE no action;--> statement-breakpoint
ALTER TABLE "platform_agent_tool_binding" ADD CONSTRAINT "platform_agent_tool_binding_fk_1" FOREIGN KEY ("tenant_id","agent_version_id") REFERENCES "public"."platform_agent_version"("tenant_id","id") ON DELETE restrict ON UPDATE no action;--> statement-breakpoint
ALTER TABLE "platform_agent_tool_binding" ADD CONSTRAINT "platform_agent_tool_binding_fk_2" FOREIGN KEY ("tenant_id","tool_version_id") REFERENCES "public"."platform_tool_version"("tenant_id","id") ON DELETE restrict ON UPDATE no action;--> statement-breakpoint
ALTER TABLE "platform_capability" ADD CONSTRAINT "platform_capability_fk_0" FOREIGN KEY ("tenant_id") REFERENCES "public"."platform_tenant"("id") ON DELETE restrict ON UPDATE no action;--> statement-breakpoint
ALTER TABLE "platform_capability" ADD CONSTRAINT "platform_capability_fk_1" FOREIGN KEY ("owner_id") REFERENCES "public"."users"("id") ON DELETE restrict ON UPDATE no action;--> statement-breakpoint
ALTER TABLE "platform_mcp_server" ADD CONSTRAINT "platform_mcp_server_fk_0" FOREIGN KEY ("tenant_id") REFERENCES "public"."platform_tenant"("id") ON DELETE restrict ON UPDATE no action;--> statement-breakpoint
ALTER TABLE "platform_mcp_server" ADD CONSTRAINT "platform_mcp_server_fk_1" FOREIGN KEY ("owner_id") REFERENCES "public"."users"("id") ON DELETE restrict ON UPDATE no action;--> statement-breakpoint
ALTER TABLE "platform_mcp_server_version" ADD CONSTRAINT "platform_mcp_server_version_fk_0" FOREIGN KEY ("tenant_id") REFERENCES "public"."platform_tenant"("id") ON DELETE restrict ON UPDATE no action;--> statement-breakpoint
ALTER TABLE "platform_mcp_server_version" ADD CONSTRAINT "platform_mcp_server_version_fk_1" FOREIGN KEY ("tenant_id","mcp_server_id") REFERENCES "public"."platform_mcp_server"("tenant_id","id") ON DELETE restrict ON UPDATE no action;--> statement-breakpoint
ALTER TABLE "platform_model_profile" ADD CONSTRAINT "platform_model_profile_fk_0" FOREIGN KEY ("tenant_id") REFERENCES "public"."platform_tenant"("id") ON DELETE restrict ON UPDATE no action;--> statement-breakpoint
ALTER TABLE "platform_skill" ADD CONSTRAINT "platform_skill_fk_0" FOREIGN KEY ("tenant_id") REFERENCES "public"."platform_tenant"("id") ON DELETE restrict ON UPDATE no action;--> statement-breakpoint
ALTER TABLE "platform_skill" ADD CONSTRAINT "platform_skill_fk_1" FOREIGN KEY ("owner_id") REFERENCES "public"."users"("id") ON DELETE restrict ON UPDATE no action;--> statement-breakpoint
ALTER TABLE "platform_skill_version" ADD CONSTRAINT "platform_skill_version_fk_0" FOREIGN KEY ("tenant_id") REFERENCES "public"."platform_tenant"("id") ON DELETE restrict ON UPDATE no action;--> statement-breakpoint
ALTER TABLE "platform_skill_version" ADD CONSTRAINT "platform_skill_version_fk_1" FOREIGN KEY ("tenant_id","skill_id") REFERENCES "public"."platform_skill"("tenant_id","id") ON DELETE restrict ON UPDATE no action;--> statement-breakpoint
ALTER TABLE "platform_tool" ADD CONSTRAINT "platform_tool_fk_0" FOREIGN KEY ("tenant_id") REFERENCES "public"."platform_tenant"("id") ON DELETE restrict ON UPDATE no action;--> statement-breakpoint
ALTER TABLE "platform_tool_version" ADD CONSTRAINT "platform_tool_version_fk_0" FOREIGN KEY ("tenant_id") REFERENCES "public"."platform_tenant"("id") ON DELETE restrict ON UPDATE no action;--> statement-breakpoint
ALTER TABLE "platform_tool_version" ADD CONSTRAINT "platform_tool_version_fk_1" FOREIGN KEY ("tenant_id","tool_id") REFERENCES "public"."platform_tool"("tenant_id","id") ON DELETE restrict ON UPDATE no action;--> statement-breakpoint
ALTER TABLE "platform_tool_version" ADD CONSTRAINT "platform_tool_version_fk_2" FOREIGN KEY ("tenant_id","mcp_server_version_id") REFERENCES "public"."platform_mcp_server_version"("tenant_id","id") ON DELETE restrict ON UPDATE no action;--> statement-breakpoint
ALTER TABLE "platform_agent_deployment" ADD CONSTRAINT "platform_agent_deployment_fk_0" FOREIGN KEY ("tenant_id") REFERENCES "public"."platform_tenant"("id") ON DELETE restrict ON UPDATE no action;--> statement-breakpoint
ALTER TABLE "platform_agent_deployment" ADD CONSTRAINT "platform_agent_deployment_fk_1" FOREIGN KEY ("tenant_id","agent_version_id") REFERENCES "public"."platform_agent_version"("tenant_id","id") ON DELETE restrict ON UPDATE no action;--> statement-breakpoint
ALTER TABLE "platform_agent_deployment" ADD CONSTRAINT "platform_agent_deployment_fk_2" FOREIGN KEY ("tenant_id","domain_installation_id") REFERENCES "public"."platform_domain_installation"("tenant_id","id") ON DELETE restrict ON UPDATE no action;--> statement-breakpoint
ALTER TABLE "platform_agent_deployment" ADD CONSTRAINT "platform_agent_deployment_fk_3" FOREIGN KEY ("tenant_id","previous_deployment_id") REFERENCES "public"."platform_agent_deployment"("tenant_id","id") ON DELETE restrict ON UPDATE no action;--> statement-breakpoint
ALTER TABLE "platform_domain_installation" ADD CONSTRAINT "platform_domain_installation_fk_0" FOREIGN KEY ("tenant_id") REFERENCES "public"."platform_tenant"("id") ON DELETE restrict ON UPDATE no action;--> statement-breakpoint
ALTER TABLE "platform_domain_installation" ADD CONSTRAINT "platform_domain_installation_fk_1" FOREIGN KEY ("domain_package_id") REFERENCES "public"."platform_domain_package"("id") ON DELETE restrict ON UPDATE no action;--> statement-breakpoint
ALTER TABLE "platform_eval_assertion" ADD CONSTRAINT "platform_eval_assertion_fk_0" FOREIGN KEY ("tenant_id") REFERENCES "public"."platform_tenant"("id") ON DELETE restrict ON UPDATE no action;--> statement-breakpoint
ALTER TABLE "platform_eval_assertion" ADD CONSTRAINT "platform_eval_assertion_fk_1" FOREIGN KEY ("tenant_id","eval_run_id") REFERENCES "public"."platform_eval_run"("tenant_id","id") ON DELETE restrict ON UPDATE no action;--> statement-breakpoint
ALTER TABLE "platform_eval_assertion" ADD CONSTRAINT "platform_eval_assertion_fk_2" FOREIGN KEY ("tenant_id","eval_case_id") REFERENCES "public"."platform_eval_case"("tenant_id","id") ON DELETE restrict ON UPDATE no action;--> statement-breakpoint
ALTER TABLE "platform_eval_case" ADD CONSTRAINT "platform_eval_case_fk_0" FOREIGN KEY ("tenant_id") REFERENCES "public"."platform_tenant"("id") ON DELETE restrict ON UPDATE no action;--> statement-breakpoint
ALTER TABLE "platform_eval_case" ADD CONSTRAINT "platform_eval_case_fk_1" FOREIGN KEY ("tenant_id","eval_suite_id") REFERENCES "public"."platform_eval_suite"("tenant_id","id") ON DELETE restrict ON UPDATE no action;--> statement-breakpoint
ALTER TABLE "platform_eval_evidence" ADD CONSTRAINT "platform_eval_evidence_fk_0" FOREIGN KEY ("tenant_id") REFERENCES "public"."platform_tenant"("id") ON DELETE restrict ON UPDATE no action;--> statement-breakpoint
ALTER TABLE "platform_eval_evidence" ADD CONSTRAINT "platform_eval_evidence_fk_1" FOREIGN KEY ("tenant_id","eval_run_id") REFERENCES "public"."platform_eval_run"("tenant_id","id") ON DELETE restrict ON UPDATE no action;--> statement-breakpoint
ALTER TABLE "platform_eval_evidence" ADD CONSTRAINT "platform_eval_evidence_fk_2" FOREIGN KEY ("tenant_id","eval_run_id","eval_assertion_id") REFERENCES "public"."platform_eval_assertion"("tenant_id","eval_run_id","id") ON DELETE restrict ON UPDATE no action;--> statement-breakpoint
ALTER TABLE "platform_eval_run" ADD CONSTRAINT "platform_eval_run_fk_0" FOREIGN KEY ("tenant_id") REFERENCES "public"."platform_tenant"("id") ON DELETE restrict ON UPDATE no action;--> statement-breakpoint
ALTER TABLE "platform_eval_run" ADD CONSTRAINT "platform_eval_run_fk_1" FOREIGN KEY ("tenant_id","agent_version_id") REFERENCES "public"."platform_agent_version"("tenant_id","id") ON DELETE restrict ON UPDATE no action;--> statement-breakpoint
ALTER TABLE "platform_eval_run" ADD CONSTRAINT "platform_eval_run_fk_2" FOREIGN KEY ("tenant_id","eval_suite_id") REFERENCES "public"."platform_eval_suite"("tenant_id","id") ON DELETE restrict ON UPDATE no action;--> statement-breakpoint
ALTER TABLE "platform_eval_suite" ADD CONSTRAINT "platform_eval_suite_fk_0" FOREIGN KEY ("tenant_id") REFERENCES "public"."platform_tenant"("id") ON DELETE restrict ON UPDATE no action;--> statement-breakpoint
ALTER TABLE "platform_eval_suite" ADD CONSTRAINT "platform_eval_suite_fk_1" FOREIGN KEY ("owner_id") REFERENCES "public"."users"("id") ON DELETE restrict ON UPDATE no action;--> statement-breakpoint
ALTER TABLE "platform_publish_approval" ADD CONSTRAINT "platform_publish_approval_fk_0" FOREIGN KEY ("tenant_id") REFERENCES "public"."platform_tenant"("id") ON DELETE restrict ON UPDATE no action;--> statement-breakpoint
ALTER TABLE "platform_publish_approval" ADD CONSTRAINT "platform_publish_approval_fk_1" FOREIGN KEY ("tenant_id","publish_gate_id") REFERENCES "public"."platform_publish_gate"("tenant_id","id") ON DELETE restrict ON UPDATE no action;--> statement-breakpoint
ALTER TABLE "platform_publish_approval" ADD CONSTRAINT "platform_publish_approval_fk_2" FOREIGN KEY ("reviewer_id") REFERENCES "public"."users"("id") ON DELETE restrict ON UPDATE no action;--> statement-breakpoint
ALTER TABLE "platform_publish_gate" ADD CONSTRAINT "platform_publish_gate_fk_0" FOREIGN KEY ("tenant_id") REFERENCES "public"."platform_tenant"("id") ON DELETE restrict ON UPDATE no action;--> statement-breakpoint
ALTER TABLE "platform_publish_gate" ADD CONSTRAINT "platform_publish_gate_fk_1" FOREIGN KEY ("tenant_id","agent_version_id") REFERENCES "public"."platform_agent_version"("tenant_id","id") ON DELETE restrict ON UPDATE no action;--> statement-breakpoint
ALTER TABLE "platform_publish_gate_result" ADD CONSTRAINT "platform_publish_gate_result_fk_0" FOREIGN KEY ("tenant_id") REFERENCES "public"."platform_tenant"("id") ON DELETE restrict ON UPDATE no action;--> statement-breakpoint
ALTER TABLE "platform_publish_gate_result" ADD CONSTRAINT "platform_publish_gate_result_fk_1" FOREIGN KEY ("tenant_id","publish_gate_id") REFERENCES "public"."platform_publish_gate"("tenant_id","id") ON DELETE restrict ON UPDATE no action;--> statement-breakpoint
ALTER TABLE "platform_regression_baseline" ADD CONSTRAINT "platform_regression_baseline_fk_0" FOREIGN KEY ("tenant_id") REFERENCES "public"."platform_tenant"("id") ON DELETE restrict ON UPDATE no action;--> statement-breakpoint
ALTER TABLE "platform_regression_baseline" ADD CONSTRAINT "platform_regression_baseline_fk_1" FOREIGN KEY ("tenant_id","agent_id") REFERENCES "public"."platform_agent"("tenant_id","id") ON DELETE restrict ON UPDATE no action;--> statement-breakpoint
ALTER TABLE "platform_regression_baseline" ADD CONSTRAINT "platform_regression_baseline_fk_2" FOREIGN KEY ("tenant_id","agent_id","baseline_agent_version_id") REFERENCES "public"."platform_agent_version"("tenant_id","agent_id","id") ON DELETE restrict ON UPDATE no action;--> statement-breakpoint
ALTER TABLE "platform_regression_baseline" ADD CONSTRAINT "platform_regression_baseline_fk_3" FOREIGN KEY ("tenant_id","eval_suite_id") REFERENCES "public"."platform_eval_suite"("tenant_id","id") ON DELETE restrict ON UPDATE no action;--> statement-breakpoint
ALTER TABLE "platform_regression_baseline" ADD CONSTRAINT "platform_regression_baseline_fk_4" FOREIGN KEY ("accepted_by") REFERENCES "public"."users"("id") ON DELETE restrict ON UPDATE no action;--> statement-breakpoint
ALTER TABLE "platform_regression_baseline" ADD CONSTRAINT "platform_regression_baseline_fk_5" FOREIGN KEY ("tenant_id","agent_id","baseline_agent_version_id") REFERENCES "public"."platform_agent_version"("tenant_id","agent_id","id") ON DELETE restrict ON UPDATE no action;--> statement-breakpoint
ALTER TABLE "platform_membership_role" ADD CONSTRAINT "platform_membership_role_fk_0" FOREIGN KEY ("tenant_id") REFERENCES "public"."platform_tenant"("id") ON DELETE restrict ON UPDATE no action;--> statement-breakpoint
ALTER TABLE "platform_membership_role" ADD CONSTRAINT "platform_membership_role_fk_1" FOREIGN KEY ("tenant_id","membership_id") REFERENCES "public"."platform_tenant_membership"("tenant_id","id") ON DELETE restrict ON UPDATE no action;--> statement-breakpoint
ALTER TABLE "platform_membership_role" ADD CONSTRAINT "platform_membership_role_fk_2" FOREIGN KEY ("tenant_id","role_id") REFERENCES "public"."platform_role"("tenant_id","id") ON DELETE restrict ON UPDATE no action;--> statement-breakpoint
ALTER TABLE "platform_role" ADD CONSTRAINT "platform_role_fk_0" FOREIGN KEY ("tenant_id") REFERENCES "public"."platform_tenant"("id") ON DELETE restrict ON UPDATE no action;--> statement-breakpoint
ALTER TABLE "platform_tenant_membership" ADD CONSTRAINT "platform_tenant_membership_fk_0" FOREIGN KEY ("tenant_id") REFERENCES "public"."platform_tenant"("id") ON DELETE restrict ON UPDATE no action;--> statement-breakpoint
ALTER TABLE "platform_tenant_membership" ADD CONSTRAINT "platform_tenant_membership_fk_1" FOREIGN KEY ("user_id") REFERENCES "public"."users"("id") ON DELETE restrict ON UPDATE no action;--> statement-breakpoint
ALTER TABLE "platform_knowledge_base" ADD CONSTRAINT "platform_knowledge_base_fk_0" FOREIGN KEY ("tenant_id") REFERENCES "public"."platform_tenant"("id") ON DELETE restrict ON UPDATE no action;--> statement-breakpoint
ALTER TABLE "platform_knowledge_base" ADD CONSTRAINT "platform_knowledge_base_fk_1" FOREIGN KEY ("owner_id") REFERENCES "public"."users"("id") ON DELETE restrict ON UPDATE no action;--> statement-breakpoint
ALTER TABLE "platform_knowledge_revision" ADD CONSTRAINT "platform_knowledge_revision_fk_0" FOREIGN KEY ("tenant_id") REFERENCES "public"."platform_tenant"("id") ON DELETE restrict ON UPDATE no action;--> statement-breakpoint
ALTER TABLE "platform_knowledge_revision" ADD CONSTRAINT "platform_knowledge_revision_fk_1" FOREIGN KEY ("tenant_id","knowledge_source_id") REFERENCES "public"."platform_knowledge_source"("tenant_id","id") ON DELETE restrict ON UPDATE no action;--> statement-breakpoint
ALTER TABLE "platform_knowledge_revision" ADD CONSTRAINT "platform_knowledge_revision_fk_2" FOREIGN KEY ("approved_by") REFERENCES "public"."users"("id") ON DELETE restrict ON UPDATE no action;--> statement-breakpoint
ALTER TABLE "platform_knowledge_source" ADD CONSTRAINT "platform_knowledge_source_fk_0" FOREIGN KEY ("tenant_id") REFERENCES "public"."platform_tenant"("id") ON DELETE restrict ON UPDATE no action;--> statement-breakpoint
ALTER TABLE "platform_knowledge_source" ADD CONSTRAINT "platform_knowledge_source_fk_1" FOREIGN KEY ("tenant_id","knowledge_base_id") REFERENCES "public"."platform_knowledge_base"("tenant_id","id") ON DELETE restrict ON UPDATE no action;--> statement-breakpoint
ALTER TABLE "platform_knowledge_source" ADD CONSTRAINT "platform_knowledge_source_fk_2" FOREIGN KEY ("owner_id") REFERENCES "public"."users"("id") ON DELETE restrict ON UPDATE no action;--> statement-breakpoint
ALTER TABLE "platform_memory_item" ADD CONSTRAINT "platform_memory_item_fk_0" FOREIGN KEY ("tenant_id") REFERENCES "public"."platform_tenant"("id") ON DELETE restrict ON UPDATE no action;--> statement-breakpoint
ALTER TABLE "platform_memory_item" ADD CONSTRAINT "platform_memory_item_fk_1" FOREIGN KEY ("tenant_id","memory_namespace_id") REFERENCES "public"."platform_memory_namespace"("tenant_id","id") ON DELETE restrict ON UPDATE no action;--> statement-breakpoint
ALTER TABLE "platform_memory_namespace" ADD CONSTRAINT "platform_memory_namespace_fk_0" FOREIGN KEY ("tenant_id") REFERENCES "public"."platform_tenant"("id") ON DELETE restrict ON UPDATE no action;--> statement-breakpoint
ALTER TABLE "platform_memory_review" ADD CONSTRAINT "platform_memory_review_fk_0" FOREIGN KEY ("tenant_id") REFERENCES "public"."platform_tenant"("id") ON DELETE restrict ON UPDATE no action;--> statement-breakpoint
ALTER TABLE "platform_memory_review" ADD CONSTRAINT "platform_memory_review_fk_1" FOREIGN KEY ("tenant_id","memory_revision_id") REFERENCES "public"."platform_memory_revision"("tenant_id","id") ON DELETE restrict ON UPDATE no action;--> statement-breakpoint
ALTER TABLE "platform_memory_review" ADD CONSTRAINT "platform_memory_review_fk_2" FOREIGN KEY ("reviewer_id") REFERENCES "public"."users"("id") ON DELETE restrict ON UPDATE no action;--> statement-breakpoint
ALTER TABLE "platform_memory_revision" ADD CONSTRAINT "platform_memory_revision_fk_0" FOREIGN KEY ("tenant_id") REFERENCES "public"."platform_tenant"("id") ON DELETE restrict ON UPDATE no action;--> statement-breakpoint
ALTER TABLE "platform_memory_revision" ADD CONSTRAINT "platform_memory_revision_fk_1" FOREIGN KEY ("tenant_id","memory_item_id") REFERENCES "public"."platform_memory_item"("tenant_id","id") ON DELETE restrict ON UPDATE no action;--> statement-breakpoint
ALTER TABLE "platform_memory_vector_ref" ADD CONSTRAINT "platform_memory_vector_ref_fk_0" FOREIGN KEY ("tenant_id") REFERENCES "public"."platform_tenant"("id") ON DELETE restrict ON UPDATE no action;--> statement-breakpoint
ALTER TABLE "platform_memory_vector_ref" ADD CONSTRAINT "platform_memory_vector_ref_fk_1" FOREIGN KEY ("tenant_id","memory_revision_id") REFERENCES "public"."platform_memory_revision"("tenant_id","id") ON DELETE restrict ON UPDATE no action;--> statement-breakpoint
ALTER TABLE "platform_policy" ADD CONSTRAINT "platform_policy_fk_0" FOREIGN KEY ("tenant_id") REFERENCES "public"."platform_tenant"("id") ON DELETE restrict ON UPDATE no action;--> statement-breakpoint
ALTER TABLE "platform_policy" ADD CONSTRAINT "platform_policy_fk_1" FOREIGN KEY ("owner_id") REFERENCES "public"."users"("id") ON DELETE restrict ON UPDATE no action;--> statement-breakpoint
ALTER TABLE "platform_policy_version" ADD CONSTRAINT "platform_policy_version_fk_0" FOREIGN KEY ("tenant_id") REFERENCES "public"."platform_tenant"("id") ON DELETE restrict ON UPDATE no action;--> statement-breakpoint
ALTER TABLE "platform_policy_version" ADD CONSTRAINT "platform_policy_version_fk_1" FOREIGN KEY ("tenant_id","policy_id") REFERENCES "public"."platform_policy"("tenant_id","id") ON DELETE restrict ON UPDATE no action;--> statement-breakpoint
ALTER TABLE "platform_action_proposal" ADD CONSTRAINT "platform_action_proposal_fk_0" FOREIGN KEY ("tenant_id") REFERENCES "public"."platform_tenant"("id") ON DELETE restrict ON UPDATE no action;--> statement-breakpoint
ALTER TABLE "platform_action_proposal" ADD CONSTRAINT "platform_action_proposal_fk_1" FOREIGN KEY ("tenant_id","workflow_session_id","runtime_decision_id") REFERENCES "public"."platform_runtime_decision"("tenant_id","workflow_session_id","id") ON DELETE restrict ON UPDATE no action;--> statement-breakpoint
ALTER TABLE "platform_action_proposal" ADD CONSTRAINT "platform_action_proposal_fk_2" FOREIGN KEY ("tenant_id","workflow_session_id") REFERENCES "public"."platform_workflow_session"("tenant_id","id") ON DELETE restrict ON UPDATE no action;--> statement-breakpoint
ALTER TABLE "platform_action_proposal" ADD CONSTRAINT "platform_action_proposal_fk_3" FOREIGN KEY ("tenant_id","workflow_session_id","producer_agent_run_id") REFERENCES "public"."platform_agent_run"("tenant_id","workflow_session_id","id") ON DELETE restrict ON UPDATE no action;--> statement-breakpoint
ALTER TABLE "platform_agent_run" ADD CONSTRAINT "platform_agent_run_fk_0" FOREIGN KEY ("tenant_id") REFERENCES "public"."platform_tenant"("id") ON DELETE restrict ON UPDATE no action;--> statement-breakpoint
ALTER TABLE "platform_agent_run" ADD CONSTRAINT "platform_agent_run_fk_1" FOREIGN KEY ("tenant_id","workflow_session_id") REFERENCES "public"."platform_workflow_session"("tenant_id","id") ON DELETE restrict ON UPDATE no action;--> statement-breakpoint
ALTER TABLE "platform_agent_run" ADD CONSTRAINT "platform_agent_run_fk_2" FOREIGN KEY ("tenant_id","workflow_session_id","run_step_id") REFERENCES "public"."platform_run_step"("tenant_id","workflow_session_id","id") ON DELETE restrict ON UPDATE no action;--> statement-breakpoint
ALTER TABLE "platform_agent_run" ADD CONSTRAINT "platform_agent_run_fk_3" FOREIGN KEY ("tenant_id","agent_id") REFERENCES "public"."platform_agent"("tenant_id","id") ON DELETE restrict ON UPDATE no action;--> statement-breakpoint
ALTER TABLE "platform_agent_run" ADD CONSTRAINT "platform_agent_run_fk_4" FOREIGN KEY ("tenant_id","agent_id","agent_version_id") REFERENCES "public"."platform_agent_version"("tenant_id","agent_id","id") ON DELETE restrict ON UPDATE no action;--> statement-breakpoint
ALTER TABLE "platform_execution_grant_ref" ADD CONSTRAINT "platform_execution_grant_ref_fk_0" FOREIGN KEY ("tenant_id") REFERENCES "public"."platform_tenant"("id") ON DELETE restrict ON UPDATE no action;--> statement-breakpoint
ALTER TABLE "platform_execution_grant_ref" ADD CONSTRAINT "platform_execution_grant_ref_fk_1" FOREIGN KEY ("tenant_id","action_proposal_id") REFERENCES "public"."platform_action_proposal"("tenant_id","id") ON DELETE restrict ON UPDATE no action;--> statement-breakpoint
ALTER TABLE "platform_run_step" ADD CONSTRAINT "platform_run_step_fk_0" FOREIGN KEY ("tenant_id") REFERENCES "public"."platform_tenant"("id") ON DELETE restrict ON UPDATE no action;--> statement-breakpoint
ALTER TABLE "platform_run_step" ADD CONSTRAINT "platform_run_step_fk_1" FOREIGN KEY ("tenant_id","workflow_session_id") REFERENCES "public"."platform_workflow_session"("tenant_id","id") ON DELETE restrict ON UPDATE no action;--> statement-breakpoint
ALTER TABLE "platform_run_step_dependency" ADD CONSTRAINT "platform_run_step_dependency_fk_0" FOREIGN KEY ("tenant_id") REFERENCES "public"."platform_tenant"("id") ON DELETE restrict ON UPDATE no action;--> statement-breakpoint
ALTER TABLE "platform_run_step_dependency" ADD CONSTRAINT "platform_run_step_dependency_fk_1" FOREIGN KEY ("tenant_id","workflow_session_id") REFERENCES "public"."platform_workflow_session"("tenant_id","id") ON DELETE restrict ON UPDATE no action;--> statement-breakpoint
ALTER TABLE "platform_run_step_dependency" ADD CONSTRAINT "platform_run_step_dependency_fk_2" FOREIGN KEY ("tenant_id","workflow_session_id","run_step_id") REFERENCES "public"."platform_run_step"("tenant_id","workflow_session_id","id") ON DELETE restrict ON UPDATE no action;--> statement-breakpoint
ALTER TABLE "platform_run_step_dependency" ADD CONSTRAINT "platform_run_step_dependency_fk_3" FOREIGN KEY ("tenant_id","workflow_session_id","depends_on_run_step_id") REFERENCES "public"."platform_run_step"("tenant_id","workflow_session_id","id") ON DELETE restrict ON UPDATE no action;--> statement-breakpoint
ALTER TABLE "platform_runtime_artifact" ADD CONSTRAINT "platform_runtime_artifact_fk_0" FOREIGN KEY ("tenant_id") REFERENCES "public"."platform_tenant"("id") ON DELETE restrict ON UPDATE no action;--> statement-breakpoint
ALTER TABLE "platform_runtime_artifact" ADD CONSTRAINT "platform_runtime_artifact_fk_1" FOREIGN KEY ("tenant_id","agent_run_id") REFERENCES "public"."platform_agent_run"("tenant_id","id") ON DELETE restrict ON UPDATE no action;--> statement-breakpoint
ALTER TABLE "platform_runtime_decision" ADD CONSTRAINT "platform_runtime_decision_fk_0" FOREIGN KEY ("tenant_id") REFERENCES "public"."platform_tenant"("id") ON DELETE restrict ON UPDATE no action;--> statement-breakpoint
ALTER TABLE "platform_runtime_decision" ADD CONSTRAINT "platform_runtime_decision_fk_1" FOREIGN KEY ("tenant_id","workflow_session_id") REFERENCES "public"."platform_workflow_session"("tenant_id","id") ON DELETE restrict ON UPDATE no action;--> statement-breakpoint
ALTER TABLE "platform_runtime_decision" ADD CONSTRAINT "platform_runtime_decision_fk_2" FOREIGN KEY ("tenant_id","workflow_session_id","created_by_run_id") REFERENCES "public"."platform_agent_run"("tenant_id","workflow_session_id","id") ON DELETE restrict ON UPDATE no action;--> statement-breakpoint
ALTER TABLE "platform_tool_call" ADD CONSTRAINT "platform_tool_call_fk_0" FOREIGN KEY ("tenant_id") REFERENCES "public"."platform_tenant"("id") ON DELETE restrict ON UPDATE no action;--> statement-breakpoint
ALTER TABLE "platform_tool_call" ADD CONSTRAINT "platform_tool_call_fk_1" FOREIGN KEY ("tenant_id","agent_run_id") REFERENCES "public"."platform_agent_run"("tenant_id","id") ON DELETE restrict ON UPDATE no action;--> statement-breakpoint
ALTER TABLE "platform_tool_call" ADD CONSTRAINT "platform_tool_call_fk_2" FOREIGN KEY ("tenant_id","tool_version_id") REFERENCES "public"."platform_tool_version"("tenant_id","id") ON DELETE restrict ON UPDATE no action;--> statement-breakpoint
ALTER TABLE "platform_workflow_session" ADD CONSTRAINT "platform_workflow_session_fk_0" FOREIGN KEY ("tenant_id") REFERENCES "public"."platform_tenant"("id") ON DELETE restrict ON UPDATE no action;--> statement-breakpoint
CREATE INDEX "vh_membership_application_file_ix_0" ON "vh_membership_application_file" USING btree ("tenant_id","project_id","application_id");--> statement-breakpoint
CREATE INDEX "vh_membership_application_file_ix_1" ON "vh_membership_application_file" USING btree ("tenant_id","project_id");--> statement-breakpoint
CREATE INDEX "vh_membership_application_file_ix_2" ON "vh_membership_application_file" USING btree ("tenant_id","file_id");--> statement-breakpoint
CREATE INDEX "vh_pet_document_ix_0" ON "vh_pet_document" USING btree ("tenant_id","file_id");--> statement-breakpoint
CREATE INDEX "vh_pet_document_ix_1" ON "vh_pet_document" USING btree ("tenant_id","project_id");--> statement-breakpoint
CREATE INDEX "vh_pet_document_ix_2" ON "vh_pet_document" USING btree ("tenant_id","project_id","pet_id");--> statement-breakpoint
CREATE INDEX "vh_report_attachment_ix_0" ON "vh_report_attachment" USING btree ("tenant_id","project_id","report_id");--> statement-breakpoint
CREATE INDEX "vh_report_attachment_ix_1" ON "vh_report_attachment" USING btree ("tenant_id","project_id");--> statement-breakpoint
CREATE INDEX "vh_report_attachment_ix_2" ON "vh_report_attachment" USING btree ("tenant_id","file_id");--> statement-breakpoint
CREATE INDEX "vh_request_attachment_ix_0" ON "vh_request_attachment" USING btree ("tenant_id","project_id","request_id");--> statement-breakpoint
CREATE INDEX "vh_request_attachment_ix_1" ON "vh_request_attachment" USING btree ("tenant_id","project_id");--> statement-breakpoint
CREATE INDEX "vh_request_attachment_ix_2" ON "vh_request_attachment" USING btree ("tenant_id","file_id");--> statement-breakpoint
CREATE INDEX "vh_service_request_file_ix_0" ON "vh_service_request_file" USING btree ("tenant_id","project_id","request_id");--> statement-breakpoint
CREATE INDEX "vh_service_request_file_ix_1" ON "vh_service_request_file" USING btree ("tenant_id","project_id");--> statement-breakpoint
CREATE INDEX "vh_service_request_file_ix_2" ON "vh_service_request_file" USING btree ("tenant_id","file_id");--> statement-breakpoint
CREATE INDEX "vh_fee_schedule_ix_0" ON "vh_fee_schedule" USING btree ("tenant_id","project_id");--> statement-breakpoint
CREATE INDEX "vh_invoice_ix_0" ON "vh_invoice" USING btree ("billed_to_user_id");--> statement-breakpoint
CREATE INDEX "vh_invoice_ix_1" ON "vh_invoice" USING btree ("tenant_id","apartment_id","status","due_at");--> statement-breakpoint
CREATE INDEX "vh_invoice_ix_2" ON "vh_invoice" USING btree ("tenant_id","project_id","apartment_id");--> statement-breakpoint
CREATE INDEX "vh_invoice_ix_3" ON "vh_invoice" USING btree ("tenant_id","project_id");--> statement-breakpoint
CREATE INDEX "vh_invoice_line_ix_0" ON "vh_invoice_line" USING btree ("tenant_id","project_id","invoice_id");--> statement-breakpoint
CREATE INDEX "vh_invoice_line_ix_1" ON "vh_invoice_line" USING btree ("tenant_id","project_id");--> statement-breakpoint
CREATE INDEX "vh_invoice_line_ix_2" ON "vh_invoice_line" USING btree ("tenant_id","project_id","fee_schedule_id");--> statement-breakpoint
CREATE INDEX "vh_loyalty_account_ix_0" ON "vh_loyalty_account" USING btree ("user_id");--> statement-breakpoint
CREATE INDEX "vh_loyalty_entry_ix_0" ON "vh_loyalty_entry" USING btree ("tenant_id","account_id");--> statement-breakpoint
CREATE INDEX "vh_payment_allocation_ix_0" ON "vh_payment_allocation" USING btree ("tenant_id","project_id","invoice_id","payment_attempt_id");--> statement-breakpoint
CREATE INDEX "vh_payment_allocation_ix_1" ON "vh_payment_allocation" USING btree ("tenant_id","project_id","invoice_id");--> statement-breakpoint
CREATE INDEX "vh_payment_allocation_ix_2" ON "vh_payment_allocation" USING btree ("tenant_id","project_id");--> statement-breakpoint
CREATE INDEX "vh_payment_attempt_ix_0" ON "vh_payment_attempt" USING btree ("tenant_id","project_id","invoice_id");--> statement-breakpoint
CREATE INDEX "vh_payment_attempt_ix_1" ON "vh_payment_attempt" USING btree ("tenant_id","project_id");--> statement-breakpoint
CREATE INDEX "vh_payment_attempt_ix_2" ON "vh_payment_attempt" USING btree ("initiated_by_user_id");--> statement-breakpoint
CREATE INDEX "vh_booking_ix_0" ON "vh_booking" USING btree ("tenant_id","apartment_id","created_at");--> statement-breakpoint
CREATE INDEX "vh_booking_ix_1" ON "vh_booking" USING btree ("tenant_id","slot_id","status","hold_expires_at");--> statement-breakpoint
CREATE INDEX "vh_booking_ix_2" ON "vh_booking" USING btree ("tenant_id","project_id");--> statement-breakpoint
CREATE INDEX "vh_booking_ix_3" ON "vh_booking" USING btree ("tenant_id","project_id","slot_id");--> statement-breakpoint
CREATE INDEX "vh_booking_ix_4" ON "vh_booking" USING btree ("tenant_id","project_id","booked_by_membership_id");--> statement-breakpoint
CREATE INDEX "vh_booking_ix_5" ON "vh_booking" USING btree ("tenant_id","project_id","apartment_id");--> statement-breakpoint
CREATE UNIQUE INDEX "vh_booking_live_member_slot_uq" ON "vh_booking" USING btree ("tenant_id","slot_id","booked_by_membership_id") WHERE "vh_booking"."status" IN ('HELD', 'CONFIRMED');--> statement-breakpoint
CREATE INDEX "vh_facility_ix_0" ON "vh_facility" USING btree ("tenant_id","project_id","place_id");--> statement-breakpoint
CREATE INDEX "vh_facility_ix_1" ON "vh_facility" USING btree ("tenant_id","project_id");--> statement-breakpoint
CREATE INDEX "vh_time_slot_ix_0" ON "vh_time_slot" USING btree ("tenant_id","project_id","facility_id");--> statement-breakpoint
CREATE INDEX "vh_time_slot_ix_1" ON "vh_time_slot" USING btree ("tenant_id","project_id");--> statement-breakpoint
CREATE INDEX "vh_business_event_ix_0" ON "vh_business_event" USING btree ("tenant_id","incident_id","occurred_at");--> statement-breakpoint
CREATE INDEX "vh_business_event_ix_1" ON "vh_business_event" USING btree ("tenant_id","project_id");--> statement-breakpoint
CREATE INDEX "vh_business_event_ix_2" ON "vh_business_event" USING btree ("tenant_id","project_id","incident_id");--> statement-breakpoint
CREATE INDEX "vh_message_ix_0" ON "vh_message" USING btree ("tenant_id","project_id","resident_report_id");--> statement-breakpoint
CREATE INDEX "vh_message_ix_1" ON "vh_message" USING btree ("tenant_id","project_id");--> statement-breakpoint
CREATE INDEX "vh_message_ix_2" ON "vh_message" USING btree ("tenant_id","project_id","incident_id");--> statement-breakpoint
CREATE INDEX "vh_notification_ix_0" ON "vh_notification" USING btree ("recipient_id");--> statement-breakpoint
CREATE INDEX "vh_notification_ix_1" ON "vh_notification" USING btree ("tenant_id","project_id","business_event_id");--> statement-breakpoint
CREATE INDEX "vh_notification_ix_2" ON "vh_notification" USING btree ("tenant_id","recipient_id","read_at","created_at");--> statement-breakpoint
CREATE INDEX "vh_notification_ix_3" ON "vh_notification" USING btree ("tenant_id","project_id");--> statement-breakpoint
CREATE INDEX "vh_community_event_ix_0" ON "vh_community_event" USING btree ("tenant_id","project_id","place_id");--> statement-breakpoint
CREATE INDEX "vh_community_event_ix_1" ON "vh_community_event" USING btree ("tenant_id","project_id");--> statement-breakpoint
CREATE INDEX "vh_content_item_ix_0" ON "vh_content_item" USING btree ("tenant_id","project_id");--> statement-breakpoint
CREATE INDEX "vh_content_item_ix_1" ON "vh_content_item" USING btree ("tenant_id","project_id","status","published_at");--> statement-breakpoint
CREATE INDEX "vh_event_registration_ix_0" ON "vh_event_registration" USING btree ("tenant_id","project_id","event_id");--> statement-breakpoint
CREATE INDEX "vh_event_registration_ix_1" ON "vh_event_registration" USING btree ("tenant_id","project_id","membership_id");--> statement-breakpoint
CREATE INDEX "vh_event_registration_ix_2" ON "vh_event_registration" USING btree ("tenant_id","project_id");--> statement-breakpoint
CREATE INDEX "vh_event_registration_ix_3" ON "vh_event_registration" USING btree ("tenant_id","event_id","status");--> statement-breakpoint
CREATE INDEX "vh_map_place_ix_0" ON "vh_map_place" USING btree ("tenant_id","project_id","tower_id");--> statement-breakpoint
CREATE INDEX "vh_map_place_ix_1" ON "vh_map_place" USING btree ("tenant_id","project_id");--> statement-breakpoint
CREATE INDEX "vh_miniapp_catalog_ix_0" ON "vh_miniapp_catalog" USING btree ("tenant_id","project_id");--> statement-breakpoint
CREATE INDEX "vh_offer_ix_0" ON "vh_offer" USING btree ("tenant_id","project_id");--> statement-breakpoint
CREATE INDEX "vh_sensor_reading_ix_0" ON "vh_sensor_reading" USING btree ("tenant_id","project_id","place_id");--> statement-breakpoint
CREATE INDEX "vh_sensor_reading_ix_1" ON "vh_sensor_reading" USING btree ("tenant_id","project_id");--> statement-breakpoint
CREATE INDEX "vh_transit_route_ix_0" ON "vh_transit_route" USING btree ("tenant_id","project_id");--> statement-breakpoint
CREATE INDEX "vh_transit_route_stop_ix_0" ON "vh_transit_route_stop" USING btree ("tenant_id","project_id");--> statement-breakpoint
CREATE INDEX "vh_transit_route_stop_ix_1" ON "vh_transit_route_stop" USING btree ("tenant_id","project_id","stop_id");--> statement-breakpoint
CREATE INDEX "vh_transit_route_stop_ix_2" ON "vh_transit_route_stop" USING btree ("tenant_id","project_id","route_id");--> statement-breakpoint
CREATE INDEX "vh_transit_stop_ix_0" ON "vh_transit_stop" USING btree ("tenant_id","project_id");--> statement-breakpoint
CREATE INDEX "vh_outbox_ix_0" ON "vh_outbox" USING btree ("tenant_id","project_id","business_event_id");--> statement-breakpoint
CREATE INDEX "vh_outbox_ix_1" ON "vh_outbox" USING btree ("tenant_id","project_id");--> statement-breakpoint
CREATE INDEX "vh_outbox_pending_ix" ON "vh_outbox" USING btree ("available_at") WHERE "vh_outbox"."delivered_at" IS NULL;--> statement-breakpoint
CREATE INDEX "vh_evidence_ref_ix_0" ON "vh_evidence_ref" USING btree ("tenant_id","project_id","incident_id","task_id","work_order_id");--> statement-breakpoint
CREATE INDEX "vh_evidence_ref_ix_1" ON "vh_evidence_ref" USING btree ("tenant_id","project_id");--> statement-breakpoint
CREATE INDEX "vh_evidence_ref_ix_2" ON "vh_evidence_ref" USING btree ("tenant_id","project_id","incident_id","task_id");--> statement-breakpoint
CREATE INDEX "vh_evidence_ref_ix_3" ON "vh_evidence_ref" USING btree ("tenant_id","project_id","incident_id");--> statement-breakpoint
CREATE INDEX "vh_evidence_ref_ix_4" ON "vh_evidence_ref" USING btree ("uploaded_by");--> statement-breakpoint
CREATE INDEX "vh_evidence_ref_ix_5" ON "vh_evidence_ref" USING btree ("tenant_id","file_id");--> statement-breakpoint
CREATE INDEX "vh_qc_result_ix_0" ON "vh_qc_result" USING btree ("tenant_id","project_id","incident_id","task_id","work_order_id");--> statement-breakpoint
CREATE INDEX "vh_qc_result_ix_1" ON "vh_qc_result" USING btree ("tenant_id","project_id");--> statement-breakpoint
CREATE INDEX "vh_qc_result_ix_2" ON "vh_qc_result" USING btree ("tenant_id","project_id","incident_id","task_id");--> statement-breakpoint
CREATE INDEX "vh_qc_result_ix_3" ON "vh_qc_result" USING btree ("tenant_id","project_id","incident_id");--> statement-breakpoint
CREATE INDEX "vh_qc_result_ix_4" ON "vh_qc_result" USING btree ("checked_by");--> statement-breakpoint
CREATE INDEX "vh_qc_result_evidence_ix_0" ON "vh_qc_result_evidence" USING btree ("tenant_id","project_id","incident_id","evidence_ref_id");--> statement-breakpoint
CREATE INDEX "vh_qc_result_evidence_ix_1" ON "vh_qc_result_evidence" USING btree ("tenant_id","project_id","incident_id","qc_result_id");--> statement-breakpoint
CREATE INDEX "vh_qc_result_evidence_ix_2" ON "vh_qc_result_evidence" USING btree ("tenant_id","project_id");--> statement-breakpoint
CREATE INDEX "vh_qc_result_evidence_ix_3" ON "vh_qc_result_evidence" USING btree ("tenant_id","project_id","incident_id");--> statement-breakpoint
CREATE INDEX "vh_root_cause_evidence_ix_0" ON "vh_root_cause_evidence" USING btree ("tenant_id","project_id","evidence_ref_id");--> statement-breakpoint
CREATE INDEX "vh_root_cause_evidence_ix_1" ON "vh_root_cause_evidence" USING btree ("tenant_id","project_id");--> statement-breakpoint
CREATE INDEX "vh_root_cause_evidence_ix_2" ON "vh_root_cause_evidence" USING btree ("tenant_id","project_id","root_cause_finding_id");--> statement-breakpoint
CREATE INDEX "vh_root_cause_finding_ix_0" ON "vh_root_cause_finding" USING btree ("tenant_id","project_id");--> statement-breakpoint
CREATE INDEX "vh_root_cause_finding_ix_1" ON "vh_root_cause_finding" USING btree ("tenant_id","project_id","incident_id");--> statement-breakpoint
CREATE INDEX "vh_root_cause_incident_ix_0" ON "vh_root_cause_incident" USING btree ("tenant_id","project_id","related_incident_id");--> statement-breakpoint
CREATE INDEX "vh_root_cause_incident_ix_1" ON "vh_root_cause_incident" USING btree ("tenant_id","project_id");--> statement-breakpoint
CREATE INDEX "vh_root_cause_incident_ix_2" ON "vh_root_cause_incident" USING btree ("tenant_id","project_id","root_cause_finding_id");--> statement-breakpoint
CREATE INDEX "vh_file_object_ix_0" ON "vh_file_object" USING btree ("uploaded_by_user_id");--> statement-breakpoint
CREATE INDEX "vh_case_ix_0" ON "vh_case" USING btree ("tenant_id","project_id","opened_by_membership_id");--> statement-breakpoint
CREATE INDEX "vh_case_ix_1" ON "vh_case" USING btree ("resident_user_id");--> statement-breakpoint
CREATE INDEX "vh_case_ix_2" ON "vh_case" USING btree ("tenant_id","project_id","apartment_id");--> statement-breakpoint
CREATE INDEX "vh_case_ix_3" ON "vh_case" USING btree ("tenant_id","project_id");--> statement-breakpoint
CREATE INDEX "vh_feedback_ix_0" ON "vh_feedback" USING btree ("author_user_id");--> statement-breakpoint
CREATE INDEX "vh_feedback_ix_1" ON "vh_feedback" USING btree ("tenant_id","project_id","report_id");--> statement-breakpoint
CREATE INDEX "vh_feedback_ix_2" ON "vh_feedback" USING btree ("tenant_id","project_id");--> statement-breakpoint
CREATE INDEX "vh_issue_candidate_ix_0" ON "vh_issue_candidate" USING btree ("tenant_id","project_id","case_id","source_request_id");--> statement-breakpoint
CREATE INDEX "vh_issue_candidate_ix_1" ON "vh_issue_candidate" USING btree ("tenant_id","case_id","status");--> statement-breakpoint
CREATE INDEX "vh_issue_candidate_ix_2" ON "vh_issue_candidate" USING btree ("tenant_id","project_id","case_id");--> statement-breakpoint
CREATE INDEX "vh_issue_candidate_ix_3" ON "vh_issue_candidate" USING btree ("tenant_id","project_id");--> statement-breakpoint
CREATE INDEX "vh_issue_relation_ix_0" ON "vh_issue_relation" USING btree ("tenant_id","project_id","target_issue_id");--> statement-breakpoint
CREATE INDEX "vh_issue_relation_ix_1" ON "vh_issue_relation" USING btree ("tenant_id","project_id");--> statement-breakpoint
CREATE INDEX "vh_issue_relation_ix_2" ON "vh_issue_relation" USING btree ("tenant_id","project_id","source_issue_id");--> statement-breakpoint
CREATE INDEX "vh_resident_confirmation_ix_0" ON "vh_resident_confirmation" USING btree ("tenant_id","incident_id","resolution_version");--> statement-breakpoint
CREATE INDEX "vh_resident_confirmation_ix_1" ON "vh_resident_confirmation" USING btree ("tenant_id","project_id");--> statement-breakpoint
CREATE INDEX "vh_resident_confirmation_ix_2" ON "vh_resident_confirmation" USING btree ("tenant_id","project_id","incident_id");--> statement-breakpoint
CREATE INDEX "vh_resident_confirmation_ix_3" ON "vh_resident_confirmation" USING btree ("confirmed_by_user_id");--> statement-breakpoint
CREATE INDEX "vh_resident_confirmation_ix_4" ON "vh_resident_confirmation" USING btree ("tenant_id","project_id","report_id");--> statement-breakpoint
CREATE INDEX "vh_resident_report_ix_0" ON "vh_resident_report" USING btree ("tenant_id","reporter_id","created_at");--> statement-breakpoint
CREATE INDEX "vh_resident_report_ix_1" ON "vh_resident_report" USING btree ("tenant_id","project_id","case_id","issue_candidate_id");--> statement-breakpoint
CREATE INDEX "vh_resident_report_ix_2" ON "vh_resident_report" USING btree ("tenant_id","project_id");--> statement-breakpoint
CREATE INDEX "vh_resident_report_ix_3" ON "vh_resident_report" USING btree ("tenant_id","project_id","incident_id");--> statement-breakpoint
CREATE INDEX "vh_resident_report_ix_4" ON "vh_resident_report" USING btree ("reporter_id");--> statement-breakpoint
CREATE INDEX "vh_resident_report_ix_5" ON "vh_resident_report" USING btree ("tenant_id","project_id","case_id");--> statement-breakpoint
CREATE INDEX "vh_resident_report_ix_6" ON "vh_resident_report" USING btree ("tenant_id","project_id","apartment_id");--> statement-breakpoint
CREATE INDEX "vh_resident_report_ix_7" ON "vh_resident_report" USING btree ("tenant_id","project_id","reporter_membership_id");--> statement-breakpoint
CREATE INDEX "vh_resident_request_ix_0" ON "vh_resident_request" USING btree ("tenant_id","project_id","case_id");--> statement-breakpoint
CREATE INDEX "vh_resident_request_ix_1" ON "vh_resident_request" USING btree ("tenant_id","case_id","created_at");--> statement-breakpoint
CREATE INDEX "vh_resident_request_ix_2" ON "vh_resident_request" USING btree ("tenant_id","project_id");--> statement-breakpoint
CREATE INDEX "vh_resident_request_ix_3" ON "vh_resident_request" USING btree ("submitted_by");--> statement-breakpoint
CREATE INDEX "vh_action_approval_ix_0" ON "vh_action_approval" USING btree ("tenant_id","project_id","action_request_id");--> statement-breakpoint
CREATE INDEX "vh_action_approval_ix_1" ON "vh_action_approval" USING btree ("reviewer_id");--> statement-breakpoint
CREATE INDEX "vh_action_approval_ix_2" ON "vh_action_approval" USING btree ("tenant_id","status","expires_at");--> statement-breakpoint
CREATE INDEX "vh_action_approval_ix_3" ON "vh_action_approval" USING btree ("tenant_id","project_id");--> statement-breakpoint
CREATE INDEX "vh_action_request_ix_0" ON "vh_action_request" USING btree ("tenant_id","project_id","incident_id","task_id");--> statement-breakpoint
CREATE INDEX "vh_action_request_ix_1" ON "vh_action_request" USING btree ("tenant_id","incident_id","status");--> statement-breakpoint
CREATE INDEX "vh_action_request_ix_2" ON "vh_action_request" USING btree ("tenant_id","project_id");--> statement-breakpoint
CREATE INDEX "vh_action_request_ix_3" ON "vh_action_request" USING btree ("tenant_id","project_id","incident_id");--> statement-breakpoint
CREATE INDEX "vh_checklist_version_ix_0" ON "vh_checklist_version" USING btree ("created_by");--> statement-breakpoint
CREATE INDEX "vh_checklist_version_ix_1" ON "vh_checklist_version" USING btree ("tenant_id","checklist_id");--> statement-breakpoint
CREATE INDEX "vh_execution_grant_ix_0" ON "vh_execution_grant" USING btree ("tenant_id","project_id","action_request_id");--> statement-breakpoint
CREATE INDEX "vh_execution_grant_ix_1" ON "vh_execution_grant" USING btree ("tenant_id","project_id");--> statement-breakpoint
CREATE INDEX "vh_incident_ix_0" ON "vh_incident" USING btree ("tenant_id","project_id","tower_id");--> statement-breakpoint
CREATE INDEX "vh_incident_ix_1" ON "vh_incident" USING btree ("tenant_id","project_id");--> statement-breakpoint
CREATE INDEX "vh_incident_ix_2" ON "vh_incident" USING btree ("closed_by_user_id");--> statement-breakpoint
CREATE INDEX "vh_incident_ix_3" ON "vh_incident" USING btree ("tenant_id","project_id","status","severity");--> statement-breakpoint
CREATE INDEX "vh_incident_ix_4" ON "vh_incident" USING btree ("owner_user_id");--> statement-breakpoint
CREATE INDEX "vh_incident_ix_5" ON "vh_incident" USING btree ("tenant_id","tower_id","status");--> statement-breakpoint
CREATE INDEX "vh_incident_relation_ix_0" ON "vh_incident_relation" USING btree ("tenant_id","project_id","target_incident_id");--> statement-breakpoint
CREATE INDEX "vh_incident_relation_ix_1" ON "vh_incident_relation" USING btree ("tenant_id","project_id","source_incident_id");--> statement-breakpoint
CREATE INDEX "vh_incident_relation_ix_2" ON "vh_incident_relation" USING btree ("created_by");--> statement-breakpoint
CREATE INDEX "vh_incident_relation_ix_3" ON "vh_incident_relation" USING btree ("tenant_id","project_id");--> statement-breakpoint
CREATE INDEX "vh_rule_evaluation_ix_0" ON "vh_rule_evaluation" USING btree ("tenant_id","project_id","action_request_id");--> statement-breakpoint
CREATE INDEX "vh_rule_evaluation_ix_1" ON "vh_rule_evaluation" USING btree ("tenant_id","project_id");--> statement-breakpoint
CREATE INDEX "vh_task_ix_0" ON "vh_task" USING btree ("tenant_id","incident_id","status");--> statement-breakpoint
CREATE INDEX "vh_task_ix_1" ON "vh_task" USING btree ("tenant_id","project_id");--> statement-breakpoint
CREATE INDEX "vh_task_ix_2" ON "vh_task" USING btree ("tenant_id","project_id","incident_id");--> statement-breakpoint
CREATE INDEX "vh_task_dependency_ix_0" ON "vh_task_dependency" USING btree ("tenant_id","project_id","incident_id","task_id");--> statement-breakpoint
CREATE INDEX "vh_task_dependency_ix_1" ON "vh_task_dependency" USING btree ("tenant_id","project_id","incident_id","depends_on_task_id");--> statement-breakpoint
CREATE INDEX "vh_task_dependency_ix_2" ON "vh_task_dependency" USING btree ("tenant_id","project_id");--> statement-breakpoint
CREATE INDEX "vh_task_dependency_ix_3" ON "vh_task_dependency" USING btree ("tenant_id","project_id","incident_id");--> statement-breakpoint
CREATE INDEX "vh_work_order_ix_0" ON "vh_work_order" USING btree ("tenant_id","checklist_version_id");--> statement-breakpoint
CREATE INDEX "vh_work_order_ix_1" ON "vh_work_order" USING btree ("tenant_id","project_id","incident_id","task_id","redo_of_work_order_id");--> statement-breakpoint
CREATE INDEX "vh_work_order_ix_2" ON "vh_work_order" USING btree ("tenant_id","project_id");--> statement-breakpoint
CREATE INDEX "vh_work_order_ix_3" ON "vh_work_order" USING btree ("tenant_id","project_id","incident_id","task_id");--> statement-breakpoint
CREATE INDEX "vh_work_order_ix_4" ON "vh_work_order" USING btree ("tenant_id","project_id","incident_id");--> statement-breakpoint
CREATE INDEX "vh_work_order_ix_5" ON "vh_work_order" USING btree ("tenant_id","project_id","incident_id","task_id","action_request_id");--> statement-breakpoint
CREATE INDEX "vh_apartment_ix_0" ON "vh_apartment" USING btree ("tenant_id","project_id","tower_id");--> statement-breakpoint
CREATE INDEX "vh_apartment_ix_1" ON "vh_apartment" USING btree ("tenant_id","project_id");--> statement-breakpoint
CREATE INDEX "vh_membership_application_ix_0" ON "vh_membership_application" USING btree ("applicant_user_id");--> statement-breakpoint
CREATE INDEX "vh_membership_application_ix_1" ON "vh_membership_application" USING btree ("reviewed_by");--> statement-breakpoint
CREATE INDEX "vh_membership_application_ix_2" ON "vh_membership_application" USING btree ("tenant_id","project_id");--> statement-breakpoint
CREATE INDEX "vh_membership_application_ix_3" ON "vh_membership_application" USING btree ("tenant_id","project_id","requested_apartment_id");--> statement-breakpoint
CREATE INDEX "vh_property_membership_ix_0" ON "vh_property_membership" USING btree ("user_id");--> statement-breakpoint
CREATE INDEX "vh_property_membership_ix_1" ON "vh_property_membership" USING btree ("tenant_id","project_id","tower_id");--> statement-breakpoint
CREATE INDEX "vh_property_membership_ix_2" ON "vh_property_membership" USING btree ("tenant_id","user_id","status","valid_from","valid_until");--> statement-breakpoint
CREATE INDEX "vh_property_membership_ix_3" ON "vh_property_membership" USING btree ("tenant_id","project_id");--> statement-breakpoint
CREATE INDEX "vh_property_membership_ix_4" ON "vh_property_membership" USING btree ("tenant_id","project_id","tower_id","apartment_id");--> statement-breakpoint
CREATE INDEX "vh_property_membership_ix_5" ON "vh_property_membership" USING btree ("granted_by_user_id");--> statement-breakpoint
CREATE INDEX "vh_tower_ix_0" ON "vh_tower" USING btree ("tenant_id","project_id");--> statement-breakpoint
CREATE INDEX "vh_access_card_ix_0" ON "vh_access_card" USING btree ("tenant_id","project_id","membership_id");--> statement-breakpoint
CREATE INDEX "vh_access_card_ix_1" ON "vh_access_card" USING btree ("tenant_id","project_id");--> statement-breakpoint
CREATE INDEX "vh_camera_request_ix_0" ON "vh_camera_request" USING btree ("tenant_id","project_id","location_place_id");--> statement-breakpoint
CREATE INDEX "vh_camera_request_ix_1" ON "vh_camera_request" USING btree ("tenant_id","project_id");--> statement-breakpoint
CREATE INDEX "vh_camera_request_ix_2" ON "vh_camera_request" USING btree ("tenant_id","project_id","requester_membership_id");--> statement-breakpoint
CREATE INDEX "vh_camera_request_ix_3" ON "vh_camera_request" USING btree ("tenant_id","project_id","apartment_id");--> statement-breakpoint
CREATE INDEX "vh_camera_request_ix_4" ON "vh_camera_request" USING btree ("reviewed_by");--> statement-breakpoint
CREATE INDEX "vh_charging_session_ix_0" ON "vh_charging_session" USING btree ("tenant_id","project_id","station_place_id");--> statement-breakpoint
CREATE INDEX "vh_charging_session_ix_1" ON "vh_charging_session" USING btree ("tenant_id","project_id","apartment_id");--> statement-breakpoint
CREATE INDEX "vh_charging_session_ix_2" ON "vh_charging_session" USING btree ("tenant_id","project_id");--> statement-breakpoint
CREATE INDEX "vh_charging_session_ix_3" ON "vh_charging_session" USING btree ("tenant_id","project_id","requested_by_membership_id");--> statement-breakpoint
CREATE INDEX "vh_construction_permit_ix_0" ON "vh_construction_permit" USING btree ("tenant_id","project_id","service_request_id");--> statement-breakpoint
CREATE INDEX "vh_construction_permit_ix_1" ON "vh_construction_permit" USING btree ("tenant_id","project_id");--> statement-breakpoint
CREATE INDEX "vh_face_enrollment_ix_0" ON "vh_face_enrollment" USING btree ("tenant_id","project_id","membership_id");--> statement-breakpoint
CREATE INDEX "vh_face_enrollment_ix_1" ON "vh_face_enrollment" USING btree ("tenant_id","project_id");--> statement-breakpoint
CREATE INDEX "vh_handover_ix_0" ON "vh_handover" USING btree ("tenant_id","checklist_version_id");--> statement-breakpoint
CREATE INDEX "vh_handover_ix_1" ON "vh_handover" USING btree ("tenant_id","project_id","apartment_id");--> statement-breakpoint
CREATE INDEX "vh_handover_ix_2" ON "vh_handover" USING btree ("tenant_id","project_id","resident_membership_id");--> statement-breakpoint
CREATE INDEX "vh_handover_ix_3" ON "vh_handover" USING btree ("tenant_id","project_id");--> statement-breakpoint
CREATE INDEX "vh_intercom_event_ix_0" ON "vh_intercom_event" USING btree ("tenant_id","project_id","visitor_pass_id");--> statement-breakpoint
CREATE INDEX "vh_intercom_event_ix_1" ON "vh_intercom_event" USING btree ("tenant_id","project_id","apartment_id");--> statement-breakpoint
CREATE INDEX "vh_intercom_event_ix_2" ON "vh_intercom_event" USING btree ("tenant_id","project_id");--> statement-breakpoint
CREATE INDEX "vh_parking_permit_ix_0" ON "vh_parking_permit" USING btree ("tenant_id","project_id","membership_id");--> statement-breakpoint
CREATE INDEX "vh_parking_permit_ix_1" ON "vh_parking_permit" USING btree ("tenant_id","project_id","apartment_id");--> statement-breakpoint
CREATE INDEX "vh_parking_permit_ix_2" ON "vh_parking_permit" USING btree ("tenant_id","project_id");--> statement-breakpoint
CREATE UNIQUE INDEX "vh_parking_active_plate_uq" ON "vh_parking_permit" USING btree ("tenant_id","project_id","vehicle_plate") WHERE "vh_parking_permit"."status" = 'ACTIVE';--> statement-breakpoint
CREATE INDEX "vh_pet_profile_ix_0" ON "vh_pet_profile" USING btree ("tenant_id","project_id","apartment_id");--> statement-breakpoint
CREATE INDEX "vh_pet_profile_ix_1" ON "vh_pet_profile" USING btree ("tenant_id","project_id");--> statement-breakpoint
CREATE INDEX "vh_pet_profile_ix_2" ON "vh_pet_profile" USING btree ("tenant_id","project_id","owner_membership_id");--> statement-breakpoint
CREATE INDEX "vh_service_request_ix_0" ON "vh_service_request" USING btree ("tenant_id","project_id","apartment_id");--> statement-breakpoint
CREATE INDEX "vh_service_request_ix_1" ON "vh_service_request" USING btree ("tenant_id","project_id","requester_membership_id");--> statement-breakpoint
CREATE INDEX "vh_service_request_ix_2" ON "vh_service_request" USING btree ("tenant_id","project_id");--> statement-breakpoint
CREATE INDEX "vh_service_request_ix_3" ON "vh_service_request" USING btree ("tenant_id","apartment_id","status","created_at");--> statement-breakpoint
CREATE INDEX "vh_visitor_pass_ix_0" ON "vh_visitor_pass" USING btree ("tenant_id","project_id","service_request_id");--> statement-breakpoint
CREATE INDEX "vh_visitor_pass_ix_1" ON "vh_visitor_pass" USING btree ("tenant_id","project_id");--> statement-breakpoint
CREATE INDEX "platform_agent_change_request_ix_0" ON "platform_agent_change_request" USING btree ("tenant_id","agent_id");--> statement-breakpoint
CREATE INDEX "platform_agent_change_request_ix_1" ON "platform_agent_change_request" USING btree ("requested_by");--> statement-breakpoint
CREATE INDEX "platform_agent_version_ix_0" ON "platform_agent_version" USING btree ("created_by");--> statement-breakpoint
CREATE INDEX "platform_agent_version_ix_1" ON "platform_agent_version" USING btree ("tenant_id","agent_id");--> statement-breakpoint
CREATE INDEX "platform_audit_event_ix_0" ON "platform_audit_event" USING btree ("tenant_id","subject_type","subject_ref","occurred_at");--> statement-breakpoint
CREATE INDEX "platform_outbox_event_ix_0" ON "platform_outbox_event" USING btree ("tenant_id","status","available_at");--> statement-breakpoint
CREATE INDEX "platform_agent_capability_binding_ix_0" ON "platform_agent_capability_binding" USING btree ("tenant_id","agent_version_id");--> statement-breakpoint
CREATE INDEX "platform_agent_capability_binding_ix_1" ON "platform_agent_capability_binding" USING btree ("tenant_id","capability_id");--> statement-breakpoint
CREATE INDEX "platform_agent_knowledge_binding_ix_0" ON "platform_agent_knowledge_binding" USING btree ("tenant_id","agent_version_id");--> statement-breakpoint
CREATE INDEX "platform_agent_knowledge_binding_ix_1" ON "platform_agent_knowledge_binding" USING btree ("tenant_id","knowledge_base_id");--> statement-breakpoint
CREATE INDEX "platform_agent_model_binding_ix_0" ON "platform_agent_model_binding" USING btree ("tenant_id","model_profile_id");--> statement-breakpoint
CREATE INDEX "platform_agent_policy_binding_ix_0" ON "platform_agent_policy_binding" USING btree ("tenant_id","agent_version_id");--> statement-breakpoint
CREATE INDEX "platform_agent_policy_binding_ix_1" ON "platform_agent_policy_binding" USING btree ("tenant_id","policy_version_id");--> statement-breakpoint
CREATE INDEX "platform_agent_skill_binding_ix_0" ON "platform_agent_skill_binding" USING btree ("tenant_id","agent_version_id");--> statement-breakpoint
CREATE INDEX "platform_agent_skill_binding_ix_1" ON "platform_agent_skill_binding" USING btree ("tenant_id","skill_version_id");--> statement-breakpoint
CREATE INDEX "platform_agent_tool_binding_ix_0" ON "platform_agent_tool_binding" USING btree ("tenant_id","agent_version_id");--> statement-breakpoint
CREATE INDEX "platform_agent_tool_binding_ix_1" ON "platform_agent_tool_binding" USING btree ("tenant_id","tool_version_id");--> statement-breakpoint
CREATE INDEX "platform_capability_ix_0" ON "platform_capability" USING btree ("owner_id");--> statement-breakpoint
CREATE INDEX "platform_mcp_server_ix_0" ON "platform_mcp_server" USING btree ("owner_id");--> statement-breakpoint
CREATE INDEX "platform_mcp_server_version_ix_0" ON "platform_mcp_server_version" USING btree ("tenant_id","mcp_server_id");--> statement-breakpoint
CREATE INDEX "platform_skill_ix_0" ON "platform_skill" USING btree ("owner_id");--> statement-breakpoint
CREATE INDEX "platform_skill_version_ix_0" ON "platform_skill_version" USING btree ("tenant_id","skill_id");--> statement-breakpoint
CREATE INDEX "platform_tool_version_ix_0" ON "platform_tool_version" USING btree ("tenant_id","mcp_server_version_id");--> statement-breakpoint
CREATE INDEX "platform_tool_version_ix_1" ON "platform_tool_version" USING btree ("tenant_id","tool_id");--> statement-breakpoint
CREATE INDEX "platform_agent_deployment_ix_0" ON "platform_agent_deployment" USING btree ("tenant_id","agent_version_id");--> statement-breakpoint
CREATE INDEX "platform_agent_deployment_ix_1" ON "platform_agent_deployment" USING btree ("tenant_id","domain_installation_id");--> statement-breakpoint
CREATE INDEX "platform_agent_deployment_ix_2" ON "platform_agent_deployment" USING btree ("tenant_id","previous_deployment_id");--> statement-breakpoint
CREATE INDEX "platform_domain_installation_ix_0" ON "platform_domain_installation" USING btree ("domain_package_id");--> statement-breakpoint
CREATE INDEX "platform_eval_assertion_ix_0" ON "platform_eval_assertion" USING btree ("tenant_id","eval_case_id");--> statement-breakpoint
CREATE INDEX "platform_eval_assertion_ix_1" ON "platform_eval_assertion" USING btree ("tenant_id","eval_run_id");--> statement-breakpoint
CREATE INDEX "platform_eval_case_ix_0" ON "platform_eval_case" USING btree ("tenant_id","eval_suite_id");--> statement-breakpoint
CREATE INDEX "platform_eval_evidence_ix_0" ON "platform_eval_evidence" USING btree ("tenant_id","eval_run_id");--> statement-breakpoint
CREATE INDEX "platform_eval_evidence_ix_1" ON "platform_eval_evidence" USING btree ("tenant_id","eval_run_id","eval_assertion_id");--> statement-breakpoint
CREATE INDEX "platform_eval_run_ix_0" ON "platform_eval_run" USING btree ("tenant_id","agent_version_id");--> statement-breakpoint
CREATE INDEX "platform_eval_run_ix_1" ON "platform_eval_run" USING btree ("tenant_id","eval_suite_id");--> statement-breakpoint
CREATE INDEX "platform_eval_suite_ix_0" ON "platform_eval_suite" USING btree ("owner_id");--> statement-breakpoint
CREATE INDEX "platform_publish_approval_ix_0" ON "platform_publish_approval" USING btree ("tenant_id","publish_gate_id");--> statement-breakpoint
CREATE INDEX "platform_publish_approval_ix_1" ON "platform_publish_approval" USING btree ("reviewer_id");--> statement-breakpoint
CREATE INDEX "platform_publish_gate_ix_0" ON "platform_publish_gate" USING btree ("tenant_id","agent_version_id");--> statement-breakpoint
CREATE INDEX "platform_publish_gate_result_ix_0" ON "platform_publish_gate_result" USING btree ("tenant_id","publish_gate_id");--> statement-breakpoint
CREATE INDEX "platform_regression_baseline_ix_0" ON "platform_regression_baseline" USING btree ("accepted_by");--> statement-breakpoint
CREATE INDEX "platform_regression_baseline_ix_1" ON "platform_regression_baseline" USING btree ("tenant_id","agent_id","baseline_agent_version_id");--> statement-breakpoint
CREATE INDEX "platform_regression_baseline_ix_2" ON "platform_regression_baseline" USING btree ("tenant_id","eval_suite_id");--> statement-breakpoint
CREATE INDEX "platform_regression_baseline_ix_3" ON "platform_regression_baseline" USING btree ("tenant_id","agent_id");--> statement-breakpoint
CREATE INDEX "platform_membership_role_ix_0" ON "platform_membership_role" USING btree ("tenant_id","role_id");--> statement-breakpoint
CREATE INDEX "platform_membership_role_ix_1" ON "platform_membership_role" USING btree ("tenant_id","membership_id");--> statement-breakpoint
CREATE INDEX "platform_tenant_membership_ix_0" ON "platform_tenant_membership" USING btree ("user_id");--> statement-breakpoint
CREATE INDEX "platform_knowledge_base_ix_0" ON "platform_knowledge_base" USING btree ("owner_id");--> statement-breakpoint
CREATE INDEX "platform_knowledge_revision_ix_0" ON "platform_knowledge_revision" USING btree ("tenant_id","knowledge_source_id");--> statement-breakpoint
CREATE INDEX "platform_knowledge_revision_ix_1" ON "platform_knowledge_revision" USING btree ("approved_by");--> statement-breakpoint
CREATE INDEX "platform_knowledge_source_ix_0" ON "platform_knowledge_source" USING btree ("owner_id");--> statement-breakpoint
CREATE INDEX "platform_knowledge_source_ix_1" ON "platform_knowledge_source" USING btree ("tenant_id","knowledge_base_id");--> statement-breakpoint
CREATE INDEX "platform_memory_item_ix_0" ON "platform_memory_item" USING btree ("tenant_id","memory_namespace_id");--> statement-breakpoint
CREATE INDEX "platform_memory_review_ix_0" ON "platform_memory_review" USING btree ("reviewer_id");--> statement-breakpoint
CREATE INDEX "platform_memory_review_ix_1" ON "platform_memory_review" USING btree ("tenant_id","memory_revision_id");--> statement-breakpoint
CREATE INDEX "platform_memory_revision_ix_0" ON "platform_memory_revision" USING btree ("tenant_id","memory_item_id");--> statement-breakpoint
CREATE INDEX "platform_policy_ix_0" ON "platform_policy" USING btree ("owner_id");--> statement-breakpoint
CREATE INDEX "platform_policy_version_ix_0" ON "platform_policy_version" USING btree ("tenant_id","policy_id");--> statement-breakpoint
CREATE INDEX "platform_action_proposal_ix_0" ON "platform_action_proposal" USING btree ("tenant_id","workflow_session_id","runtime_decision_id");--> statement-breakpoint
CREATE INDEX "platform_action_proposal_ix_1" ON "platform_action_proposal" USING btree ("tenant_id","workflow_session_id","producer_agent_run_id");--> statement-breakpoint
CREATE INDEX "platform_action_proposal_ix_2" ON "platform_action_proposal" USING btree ("tenant_id","workflow_session_id");--> statement-breakpoint
CREATE INDEX "platform_agent_run_ix_0" ON "platform_agent_run" USING btree ("tenant_id","agent_id","agent_version_id");--> statement-breakpoint
CREATE INDEX "platform_agent_run_ix_1" ON "platform_agent_run" USING btree ("tenant_id","workflow_session_id");--> statement-breakpoint
CREATE INDEX "platform_agent_run_ix_2" ON "platform_agent_run" USING btree ("tenant_id","workflow_session_id","run_step_id");--> statement-breakpoint
CREATE INDEX "platform_agent_run_ix_3" ON "platform_agent_run" USING btree ("tenant_id","agent_id");--> statement-breakpoint
CREATE INDEX "platform_execution_grant_ref_ix_0" ON "platform_execution_grant_ref" USING btree ("tenant_id","action_proposal_id");--> statement-breakpoint
CREATE INDEX "platform_run_step_ix_0" ON "platform_run_step" USING btree ("tenant_id","workflow_session_id");--> statement-breakpoint
CREATE INDEX "platform_run_step_dependency_ix_0" ON "platform_run_step_dependency" USING btree ("tenant_id","workflow_session_id","depends_on_run_step_id");--> statement-breakpoint
CREATE INDEX "platform_run_step_dependency_ix_1" ON "platform_run_step_dependency" USING btree ("tenant_id","workflow_session_id");--> statement-breakpoint
CREATE INDEX "platform_run_step_dependency_ix_2" ON "platform_run_step_dependency" USING btree ("tenant_id","workflow_session_id","run_step_id");--> statement-breakpoint
CREATE INDEX "platform_runtime_artifact_ix_0" ON "platform_runtime_artifact" USING btree ("tenant_id","agent_run_id");--> statement-breakpoint
CREATE INDEX "platform_runtime_decision_ix_0" ON "platform_runtime_decision" USING btree ("tenant_id","workflow_session_id","created_by_run_id");--> statement-breakpoint
CREATE INDEX "platform_runtime_decision_ix_1" ON "platform_runtime_decision" USING btree ("tenant_id","workflow_session_id");--> statement-breakpoint
CREATE INDEX "platform_tool_call_ix_0" ON "platform_tool_call" USING btree ("tenant_id","agent_run_id");--> statement-breakpoint
CREATE INDEX "platform_tool_call_ix_1" ON "platform_tool_call" USING btree ("tenant_id","tool_version_id");--> statement-breakpoint
CREATE INDEX "platform_workflow_session_ix_0" ON "platform_workflow_session" USING btree ("tenant_id","domain_namespace","subject_ref");--> statement-breakpoint
CREATE INDEX "platform_workflow_session_ix_1" ON "platform_workflow_session" USING btree ("tenant_id","status","created_at");--> statement-breakpoint
CREATE POLICY "vh_membership_application_file_tenant_policy" ON "vh_membership_application_file" AS PERMISSIVE FOR ALL TO public USING ("vh_membership_application_file"."tenant_id" = nullif(current_setting('app.tenant_id', true), '')::uuid) WITH CHECK ("vh_membership_application_file"."tenant_id" = nullif(current_setting('app.tenant_id', true), '')::uuid);--> statement-breakpoint
CREATE POLICY "vh_pet_document_tenant_policy" ON "vh_pet_document" AS PERMISSIVE FOR ALL TO public USING ("vh_pet_document"."tenant_id" = nullif(current_setting('app.tenant_id', true), '')::uuid) WITH CHECK ("vh_pet_document"."tenant_id" = nullif(current_setting('app.tenant_id', true), '')::uuid);--> statement-breakpoint
CREATE POLICY "vh_report_attachment_tenant_policy" ON "vh_report_attachment" AS PERMISSIVE FOR ALL TO public USING ("vh_report_attachment"."tenant_id" = nullif(current_setting('app.tenant_id', true), '')::uuid) WITH CHECK ("vh_report_attachment"."tenant_id" = nullif(current_setting('app.tenant_id', true), '')::uuid);--> statement-breakpoint
CREATE POLICY "vh_request_attachment_tenant_policy" ON "vh_request_attachment" AS PERMISSIVE FOR ALL TO public USING ("vh_request_attachment"."tenant_id" = nullif(current_setting('app.tenant_id', true), '')::uuid) WITH CHECK ("vh_request_attachment"."tenant_id" = nullif(current_setting('app.tenant_id', true), '')::uuid);--> statement-breakpoint
CREATE POLICY "vh_service_request_file_tenant_policy" ON "vh_service_request_file" AS PERMISSIVE FOR ALL TO public USING ("vh_service_request_file"."tenant_id" = nullif(current_setting('app.tenant_id', true), '')::uuid) WITH CHECK ("vh_service_request_file"."tenant_id" = nullif(current_setting('app.tenant_id', true), '')::uuid);--> statement-breakpoint
CREATE POLICY "vh_fee_schedule_tenant_policy" ON "vh_fee_schedule" AS PERMISSIVE FOR ALL TO public USING ("vh_fee_schedule"."tenant_id" = nullif(current_setting('app.tenant_id', true), '')::uuid) WITH CHECK ("vh_fee_schedule"."tenant_id" = nullif(current_setting('app.tenant_id', true), '')::uuid);--> statement-breakpoint
CREATE POLICY "vh_invoice_tenant_policy" ON "vh_invoice" AS PERMISSIVE FOR ALL TO public USING ("vh_invoice"."tenant_id" = nullif(current_setting('app.tenant_id', true), '')::uuid) WITH CHECK ("vh_invoice"."tenant_id" = nullif(current_setting('app.tenant_id', true), '')::uuid);--> statement-breakpoint
CREATE POLICY "vh_invoice_line_tenant_policy" ON "vh_invoice_line" AS PERMISSIVE FOR ALL TO public USING ("vh_invoice_line"."tenant_id" = nullif(current_setting('app.tenant_id', true), '')::uuid) WITH CHECK ("vh_invoice_line"."tenant_id" = nullif(current_setting('app.tenant_id', true), '')::uuid);--> statement-breakpoint
CREATE POLICY "vh_loyalty_account_tenant_policy" ON "vh_loyalty_account" AS PERMISSIVE FOR ALL TO public USING ("vh_loyalty_account"."tenant_id" = nullif(current_setting('app.tenant_id', true), '')::uuid) WITH CHECK ("vh_loyalty_account"."tenant_id" = nullif(current_setting('app.tenant_id', true), '')::uuid);--> statement-breakpoint
CREATE POLICY "vh_loyalty_entry_tenant_policy" ON "vh_loyalty_entry" AS PERMISSIVE FOR ALL TO public USING ("vh_loyalty_entry"."tenant_id" = nullif(current_setting('app.tenant_id', true), '')::uuid) WITH CHECK ("vh_loyalty_entry"."tenant_id" = nullif(current_setting('app.tenant_id', true), '')::uuid);--> statement-breakpoint
CREATE POLICY "vh_payment_allocation_tenant_policy" ON "vh_payment_allocation" AS PERMISSIVE FOR ALL TO public USING ("vh_payment_allocation"."tenant_id" = nullif(current_setting('app.tenant_id', true), '')::uuid) WITH CHECK ("vh_payment_allocation"."tenant_id" = nullif(current_setting('app.tenant_id', true), '')::uuid);--> statement-breakpoint
CREATE POLICY "vh_payment_attempt_tenant_policy" ON "vh_payment_attempt" AS PERMISSIVE FOR ALL TO public USING ("vh_payment_attempt"."tenant_id" = nullif(current_setting('app.tenant_id', true), '')::uuid) WITH CHECK ("vh_payment_attempt"."tenant_id" = nullif(current_setting('app.tenant_id', true), '')::uuid);--> statement-breakpoint
CREATE POLICY "vh_booking_tenant_policy" ON "vh_booking" AS PERMISSIVE FOR ALL TO public USING ("vh_booking"."tenant_id" = nullif(current_setting('app.tenant_id', true), '')::uuid) WITH CHECK ("vh_booking"."tenant_id" = nullif(current_setting('app.tenant_id', true), '')::uuid);--> statement-breakpoint
CREATE POLICY "vh_facility_tenant_policy" ON "vh_facility" AS PERMISSIVE FOR ALL TO public USING ("vh_facility"."tenant_id" = nullif(current_setting('app.tenant_id', true), '')::uuid) WITH CHECK ("vh_facility"."tenant_id" = nullif(current_setting('app.tenant_id', true), '')::uuid);--> statement-breakpoint
CREATE POLICY "vh_time_slot_tenant_policy" ON "vh_time_slot" AS PERMISSIVE FOR ALL TO public USING ("vh_time_slot"."tenant_id" = nullif(current_setting('app.tenant_id', true), '')::uuid) WITH CHECK ("vh_time_slot"."tenant_id" = nullif(current_setting('app.tenant_id', true), '')::uuid);--> statement-breakpoint
CREATE POLICY "vh_business_event_tenant_policy" ON "vh_business_event" AS PERMISSIVE FOR ALL TO public USING ("vh_business_event"."tenant_id" = nullif(current_setting('app.tenant_id', true), '')::uuid) WITH CHECK ("vh_business_event"."tenant_id" = nullif(current_setting('app.tenant_id', true), '')::uuid);--> statement-breakpoint
CREATE POLICY "vh_message_tenant_policy" ON "vh_message" AS PERMISSIVE FOR ALL TO public USING ("vh_message"."tenant_id" = nullif(current_setting('app.tenant_id', true), '')::uuid) WITH CHECK ("vh_message"."tenant_id" = nullif(current_setting('app.tenant_id', true), '')::uuid);--> statement-breakpoint
CREATE POLICY "vh_notification_tenant_policy" ON "vh_notification" AS PERMISSIVE FOR ALL TO public USING ("vh_notification"."tenant_id" = nullif(current_setting('app.tenant_id', true), '')::uuid) WITH CHECK ("vh_notification"."tenant_id" = nullif(current_setting('app.tenant_id', true), '')::uuid);--> statement-breakpoint
CREATE POLICY "vh_community_event_tenant_policy" ON "vh_community_event" AS PERMISSIVE FOR ALL TO public USING ("vh_community_event"."tenant_id" = nullif(current_setting('app.tenant_id', true), '')::uuid) WITH CHECK ("vh_community_event"."tenant_id" = nullif(current_setting('app.tenant_id', true), '')::uuid);--> statement-breakpoint
CREATE POLICY "vh_content_item_tenant_policy" ON "vh_content_item" AS PERMISSIVE FOR ALL TO public USING ("vh_content_item"."tenant_id" = nullif(current_setting('app.tenant_id', true), '')::uuid) WITH CHECK ("vh_content_item"."tenant_id" = nullif(current_setting('app.tenant_id', true), '')::uuid);--> statement-breakpoint
CREATE POLICY "vh_event_registration_tenant_policy" ON "vh_event_registration" AS PERMISSIVE FOR ALL TO public USING ("vh_event_registration"."tenant_id" = nullif(current_setting('app.tenant_id', true), '')::uuid) WITH CHECK ("vh_event_registration"."tenant_id" = nullif(current_setting('app.tenant_id', true), '')::uuid);--> statement-breakpoint
CREATE POLICY "vh_map_place_tenant_policy" ON "vh_map_place" AS PERMISSIVE FOR ALL TO public USING ("vh_map_place"."tenant_id" = nullif(current_setting('app.tenant_id', true), '')::uuid) WITH CHECK ("vh_map_place"."tenant_id" = nullif(current_setting('app.tenant_id', true), '')::uuid);--> statement-breakpoint
CREATE POLICY "vh_miniapp_catalog_tenant_policy" ON "vh_miniapp_catalog" AS PERMISSIVE FOR ALL TO public USING ("vh_miniapp_catalog"."tenant_id" = nullif(current_setting('app.tenant_id', true), '')::uuid) WITH CHECK ("vh_miniapp_catalog"."tenant_id" = nullif(current_setting('app.tenant_id', true), '')::uuid);--> statement-breakpoint
CREATE POLICY "vh_offer_tenant_policy" ON "vh_offer" AS PERMISSIVE FOR ALL TO public USING ("vh_offer"."tenant_id" = nullif(current_setting('app.tenant_id', true), '')::uuid) WITH CHECK ("vh_offer"."tenant_id" = nullif(current_setting('app.tenant_id', true), '')::uuid);--> statement-breakpoint
CREATE POLICY "vh_sensor_reading_tenant_policy" ON "vh_sensor_reading" AS PERMISSIVE FOR ALL TO public USING ("vh_sensor_reading"."tenant_id" = nullif(current_setting('app.tenant_id', true), '')::uuid) WITH CHECK ("vh_sensor_reading"."tenant_id" = nullif(current_setting('app.tenant_id', true), '')::uuid);--> statement-breakpoint
CREATE POLICY "vh_transit_route_tenant_policy" ON "vh_transit_route" AS PERMISSIVE FOR ALL TO public USING ("vh_transit_route"."tenant_id" = nullif(current_setting('app.tenant_id', true), '')::uuid) WITH CHECK ("vh_transit_route"."tenant_id" = nullif(current_setting('app.tenant_id', true), '')::uuid);--> statement-breakpoint
CREATE POLICY "vh_transit_route_stop_tenant_policy" ON "vh_transit_route_stop" AS PERMISSIVE FOR ALL TO public USING ("vh_transit_route_stop"."tenant_id" = nullif(current_setting('app.tenant_id', true), '')::uuid) WITH CHECK ("vh_transit_route_stop"."tenant_id" = nullif(current_setting('app.tenant_id', true), '')::uuid);--> statement-breakpoint
CREATE POLICY "vh_transit_stop_tenant_policy" ON "vh_transit_stop" AS PERMISSIVE FOR ALL TO public USING ("vh_transit_stop"."tenant_id" = nullif(current_setting('app.tenant_id', true), '')::uuid) WITH CHECK ("vh_transit_stop"."tenant_id" = nullif(current_setting('app.tenant_id', true), '')::uuid);--> statement-breakpoint
CREATE POLICY "vh_command_receipt_tenant_policy" ON "vh_command_receipt" AS PERMISSIVE FOR ALL TO public USING ("vh_command_receipt"."tenant_id" = nullif(current_setting('app.tenant_id', true), '')::uuid) WITH CHECK ("vh_command_receipt"."tenant_id" = nullif(current_setting('app.tenant_id', true), '')::uuid);--> statement-breakpoint
CREATE POLICY "vh_outbox_tenant_policy" ON "vh_outbox" AS PERMISSIVE FOR ALL TO public USING ("vh_outbox"."tenant_id" = nullif(current_setting('app.tenant_id', true), '')::uuid) WITH CHECK ("vh_outbox"."tenant_id" = nullif(current_setting('app.tenant_id', true), '')::uuid);--> statement-breakpoint
CREATE POLICY "vh_evidence_ref_tenant_policy" ON "vh_evidence_ref" AS PERMISSIVE FOR ALL TO public USING ("vh_evidence_ref"."tenant_id" = nullif(current_setting('app.tenant_id', true), '')::uuid) WITH CHECK ("vh_evidence_ref"."tenant_id" = nullif(current_setting('app.tenant_id', true), '')::uuid);--> statement-breakpoint
CREATE POLICY "vh_qc_result_tenant_policy" ON "vh_qc_result" AS PERMISSIVE FOR ALL TO public USING ("vh_qc_result"."tenant_id" = nullif(current_setting('app.tenant_id', true), '')::uuid) WITH CHECK ("vh_qc_result"."tenant_id" = nullif(current_setting('app.tenant_id', true), '')::uuid);--> statement-breakpoint
CREATE POLICY "vh_qc_result_evidence_tenant_policy" ON "vh_qc_result_evidence" AS PERMISSIVE FOR ALL TO public USING ("vh_qc_result_evidence"."tenant_id" = nullif(current_setting('app.tenant_id', true), '')::uuid) WITH CHECK ("vh_qc_result_evidence"."tenant_id" = nullif(current_setting('app.tenant_id', true), '')::uuid);--> statement-breakpoint
CREATE POLICY "vh_root_cause_evidence_tenant_policy" ON "vh_root_cause_evidence" AS PERMISSIVE FOR ALL TO public USING ("vh_root_cause_evidence"."tenant_id" = nullif(current_setting('app.tenant_id', true), '')::uuid) WITH CHECK ("vh_root_cause_evidence"."tenant_id" = nullif(current_setting('app.tenant_id', true), '')::uuid);--> statement-breakpoint
CREATE POLICY "vh_root_cause_finding_tenant_policy" ON "vh_root_cause_finding" AS PERMISSIVE FOR ALL TO public USING ("vh_root_cause_finding"."tenant_id" = nullif(current_setting('app.tenant_id', true), '')::uuid) WITH CHECK ("vh_root_cause_finding"."tenant_id" = nullif(current_setting('app.tenant_id', true), '')::uuid);--> statement-breakpoint
CREATE POLICY "vh_root_cause_incident_tenant_policy" ON "vh_root_cause_incident" AS PERMISSIVE FOR ALL TO public USING ("vh_root_cause_incident"."tenant_id" = nullif(current_setting('app.tenant_id', true), '')::uuid) WITH CHECK ("vh_root_cause_incident"."tenant_id" = nullif(current_setting('app.tenant_id', true), '')::uuid);--> statement-breakpoint
CREATE POLICY "vh_file_object_tenant_policy" ON "vh_file_object" AS PERMISSIVE FOR ALL TO public USING ("vh_file_object"."tenant_id" = nullif(current_setting('app.tenant_id', true), '')::uuid) WITH CHECK ("vh_file_object"."tenant_id" = nullif(current_setting('app.tenant_id', true), '')::uuid);--> statement-breakpoint
CREATE POLICY "vh_case_tenant_policy" ON "vh_case" AS PERMISSIVE FOR ALL TO public USING ("vh_case"."tenant_id" = nullif(current_setting('app.tenant_id', true), '')::uuid) WITH CHECK ("vh_case"."tenant_id" = nullif(current_setting('app.tenant_id', true), '')::uuid);--> statement-breakpoint
CREATE POLICY "vh_feedback_tenant_policy" ON "vh_feedback" AS PERMISSIVE FOR ALL TO public USING ("vh_feedback"."tenant_id" = nullif(current_setting('app.tenant_id', true), '')::uuid) WITH CHECK ("vh_feedback"."tenant_id" = nullif(current_setting('app.tenant_id', true), '')::uuid);--> statement-breakpoint
CREATE POLICY "vh_issue_candidate_tenant_policy" ON "vh_issue_candidate" AS PERMISSIVE FOR ALL TO public USING ("vh_issue_candidate"."tenant_id" = nullif(current_setting('app.tenant_id', true), '')::uuid) WITH CHECK ("vh_issue_candidate"."tenant_id" = nullif(current_setting('app.tenant_id', true), '')::uuid);--> statement-breakpoint
CREATE POLICY "vh_issue_relation_tenant_policy" ON "vh_issue_relation" AS PERMISSIVE FOR ALL TO public USING ("vh_issue_relation"."tenant_id" = nullif(current_setting('app.tenant_id', true), '')::uuid) WITH CHECK ("vh_issue_relation"."tenant_id" = nullif(current_setting('app.tenant_id', true), '')::uuid);--> statement-breakpoint
CREATE POLICY "vh_resident_confirmation_tenant_policy" ON "vh_resident_confirmation" AS PERMISSIVE FOR ALL TO public USING ("vh_resident_confirmation"."tenant_id" = nullif(current_setting('app.tenant_id', true), '')::uuid) WITH CHECK ("vh_resident_confirmation"."tenant_id" = nullif(current_setting('app.tenant_id', true), '')::uuid);--> statement-breakpoint
CREATE POLICY "vh_resident_report_tenant_policy" ON "vh_resident_report" AS PERMISSIVE FOR ALL TO public USING ("vh_resident_report"."tenant_id" = nullif(current_setting('app.tenant_id', true), '')::uuid) WITH CHECK ("vh_resident_report"."tenant_id" = nullif(current_setting('app.tenant_id', true), '')::uuid);--> statement-breakpoint
CREATE POLICY "vh_resident_request_tenant_policy" ON "vh_resident_request" AS PERMISSIVE FOR ALL TO public USING ("vh_resident_request"."tenant_id" = nullif(current_setting('app.tenant_id', true), '')::uuid) WITH CHECK ("vh_resident_request"."tenant_id" = nullif(current_setting('app.tenant_id', true), '')::uuid);--> statement-breakpoint
CREATE POLICY "vh_action_approval_tenant_policy" ON "vh_action_approval" AS PERMISSIVE FOR ALL TO public USING ("vh_action_approval"."tenant_id" = nullif(current_setting('app.tenant_id', true), '')::uuid) WITH CHECK ("vh_action_approval"."tenant_id" = nullif(current_setting('app.tenant_id', true), '')::uuid);--> statement-breakpoint
CREATE POLICY "vh_action_request_tenant_policy" ON "vh_action_request" AS PERMISSIVE FOR ALL TO public USING ("vh_action_request"."tenant_id" = nullif(current_setting('app.tenant_id', true), '')::uuid) WITH CHECK ("vh_action_request"."tenant_id" = nullif(current_setting('app.tenant_id', true), '')::uuid);--> statement-breakpoint
CREATE POLICY "vh_checklist_tenant_policy" ON "vh_checklist" AS PERMISSIVE FOR ALL TO public USING ("vh_checklist"."tenant_id" = nullif(current_setting('app.tenant_id', true), '')::uuid) WITH CHECK ("vh_checklist"."tenant_id" = nullif(current_setting('app.tenant_id', true), '')::uuid);--> statement-breakpoint
CREATE POLICY "vh_checklist_version_tenant_policy" ON "vh_checklist_version" AS PERMISSIVE FOR ALL TO public USING ("vh_checklist_version"."tenant_id" = nullif(current_setting('app.tenant_id', true), '')::uuid) WITH CHECK ("vh_checklist_version"."tenant_id" = nullif(current_setting('app.tenant_id', true), '')::uuid);--> statement-breakpoint
CREATE POLICY "vh_execution_grant_tenant_policy" ON "vh_execution_grant" AS PERMISSIVE FOR ALL TO public USING ("vh_execution_grant"."tenant_id" = nullif(current_setting('app.tenant_id', true), '')::uuid) WITH CHECK ("vh_execution_grant"."tenant_id" = nullif(current_setting('app.tenant_id', true), '')::uuid);--> statement-breakpoint
CREATE POLICY "vh_incident_tenant_policy" ON "vh_incident" AS PERMISSIVE FOR ALL TO public USING ("vh_incident"."tenant_id" = nullif(current_setting('app.tenant_id', true), '')::uuid) WITH CHECK ("vh_incident"."tenant_id" = nullif(current_setting('app.tenant_id', true), '')::uuid);--> statement-breakpoint
CREATE POLICY "vh_incident_relation_tenant_policy" ON "vh_incident_relation" AS PERMISSIVE FOR ALL TO public USING ("vh_incident_relation"."tenant_id" = nullif(current_setting('app.tenant_id', true), '')::uuid) WITH CHECK ("vh_incident_relation"."tenant_id" = nullif(current_setting('app.tenant_id', true), '')::uuid);--> statement-breakpoint
CREATE POLICY "vh_rule_evaluation_tenant_policy" ON "vh_rule_evaluation" AS PERMISSIVE FOR ALL TO public USING ("vh_rule_evaluation"."tenant_id" = nullif(current_setting('app.tenant_id', true), '')::uuid) WITH CHECK ("vh_rule_evaluation"."tenant_id" = nullif(current_setting('app.tenant_id', true), '')::uuid);--> statement-breakpoint
CREATE POLICY "vh_task_tenant_policy" ON "vh_task" AS PERMISSIVE FOR ALL TO public USING ("vh_task"."tenant_id" = nullif(current_setting('app.tenant_id', true), '')::uuid) WITH CHECK ("vh_task"."tenant_id" = nullif(current_setting('app.tenant_id', true), '')::uuid);--> statement-breakpoint
CREATE POLICY "vh_task_dependency_tenant_policy" ON "vh_task_dependency" AS PERMISSIVE FOR ALL TO public USING ("vh_task_dependency"."tenant_id" = nullif(current_setting('app.tenant_id', true), '')::uuid) WITH CHECK ("vh_task_dependency"."tenant_id" = nullif(current_setting('app.tenant_id', true), '')::uuid);--> statement-breakpoint
CREATE POLICY "vh_work_order_tenant_policy" ON "vh_work_order" AS PERMISSIVE FOR ALL TO public USING ("vh_work_order"."tenant_id" = nullif(current_setting('app.tenant_id', true), '')::uuid) WITH CHECK ("vh_work_order"."tenant_id" = nullif(current_setting('app.tenant_id', true), '')::uuid);--> statement-breakpoint
CREATE POLICY "vh_apartment_tenant_policy" ON "vh_apartment" AS PERMISSIVE FOR ALL TO public USING ("vh_apartment"."tenant_id" = nullif(current_setting('app.tenant_id', true), '')::uuid) WITH CHECK ("vh_apartment"."tenant_id" = nullif(current_setting('app.tenant_id', true), '')::uuid);--> statement-breakpoint
CREATE POLICY "vh_membership_application_tenant_policy" ON "vh_membership_application" AS PERMISSIVE FOR ALL TO public USING ("vh_membership_application"."tenant_id" = nullif(current_setting('app.tenant_id', true), '')::uuid) WITH CHECK ("vh_membership_application"."tenant_id" = nullif(current_setting('app.tenant_id', true), '')::uuid);--> statement-breakpoint
CREATE POLICY "vh_project_tenant_policy" ON "vh_project" AS PERMISSIVE FOR ALL TO public USING ("vh_project"."tenant_id" = nullif(current_setting('app.tenant_id', true), '')::uuid) WITH CHECK ("vh_project"."tenant_id" = nullif(current_setting('app.tenant_id', true), '')::uuid);--> statement-breakpoint
CREATE POLICY "vh_property_membership_tenant_policy" ON "vh_property_membership" AS PERMISSIVE FOR ALL TO public USING ("vh_property_membership"."tenant_id" = nullif(current_setting('app.tenant_id', true), '')::uuid) WITH CHECK ("vh_property_membership"."tenant_id" = nullif(current_setting('app.tenant_id', true), '')::uuid);--> statement-breakpoint
CREATE POLICY "vh_tower_tenant_policy" ON "vh_tower" AS PERMISSIVE FOR ALL TO public USING ("vh_tower"."tenant_id" = nullif(current_setting('app.tenant_id', true), '')::uuid) WITH CHECK ("vh_tower"."tenant_id" = nullif(current_setting('app.tenant_id', true), '')::uuid);--> statement-breakpoint
CREATE POLICY "vh_access_card_tenant_policy" ON "vh_access_card" AS PERMISSIVE FOR ALL TO public USING ("vh_access_card"."tenant_id" = nullif(current_setting('app.tenant_id', true), '')::uuid) WITH CHECK ("vh_access_card"."tenant_id" = nullif(current_setting('app.tenant_id', true), '')::uuid);--> statement-breakpoint
CREATE POLICY "vh_camera_request_tenant_policy" ON "vh_camera_request" AS PERMISSIVE FOR ALL TO public USING ("vh_camera_request"."tenant_id" = nullif(current_setting('app.tenant_id', true), '')::uuid) WITH CHECK ("vh_camera_request"."tenant_id" = nullif(current_setting('app.tenant_id', true), '')::uuid);--> statement-breakpoint
CREATE POLICY "vh_charging_session_tenant_policy" ON "vh_charging_session" AS PERMISSIVE FOR ALL TO public USING ("vh_charging_session"."tenant_id" = nullif(current_setting('app.tenant_id', true), '')::uuid) WITH CHECK ("vh_charging_session"."tenant_id" = nullif(current_setting('app.tenant_id', true), '')::uuid);--> statement-breakpoint
CREATE POLICY "vh_construction_permit_tenant_policy" ON "vh_construction_permit" AS PERMISSIVE FOR ALL TO public USING ("vh_construction_permit"."tenant_id" = nullif(current_setting('app.tenant_id', true), '')::uuid) WITH CHECK ("vh_construction_permit"."tenant_id" = nullif(current_setting('app.tenant_id', true), '')::uuid);--> statement-breakpoint
CREATE POLICY "vh_face_enrollment_tenant_policy" ON "vh_face_enrollment" AS PERMISSIVE FOR ALL TO public USING ("vh_face_enrollment"."tenant_id" = nullif(current_setting('app.tenant_id', true), '')::uuid) WITH CHECK ("vh_face_enrollment"."tenant_id" = nullif(current_setting('app.tenant_id', true), '')::uuid);--> statement-breakpoint
CREATE POLICY "vh_handover_tenant_policy" ON "vh_handover" AS PERMISSIVE FOR ALL TO public USING ("vh_handover"."tenant_id" = nullif(current_setting('app.tenant_id', true), '')::uuid) WITH CHECK ("vh_handover"."tenant_id" = nullif(current_setting('app.tenant_id', true), '')::uuid);--> statement-breakpoint
CREATE POLICY "vh_intercom_event_tenant_policy" ON "vh_intercom_event" AS PERMISSIVE FOR ALL TO public USING ("vh_intercom_event"."tenant_id" = nullif(current_setting('app.tenant_id', true), '')::uuid) WITH CHECK ("vh_intercom_event"."tenant_id" = nullif(current_setting('app.tenant_id', true), '')::uuid);--> statement-breakpoint
CREATE POLICY "vh_parking_permit_tenant_policy" ON "vh_parking_permit" AS PERMISSIVE FOR ALL TO public USING ("vh_parking_permit"."tenant_id" = nullif(current_setting('app.tenant_id', true), '')::uuid) WITH CHECK ("vh_parking_permit"."tenant_id" = nullif(current_setting('app.tenant_id', true), '')::uuid);--> statement-breakpoint
CREATE POLICY "vh_pet_profile_tenant_policy" ON "vh_pet_profile" AS PERMISSIVE FOR ALL TO public USING ("vh_pet_profile"."tenant_id" = nullif(current_setting('app.tenant_id', true), '')::uuid) WITH CHECK ("vh_pet_profile"."tenant_id" = nullif(current_setting('app.tenant_id', true), '')::uuid);--> statement-breakpoint
CREATE POLICY "vh_service_request_tenant_policy" ON "vh_service_request" AS PERMISSIVE FOR ALL TO public USING ("vh_service_request"."tenant_id" = nullif(current_setting('app.tenant_id', true), '')::uuid) WITH CHECK ("vh_service_request"."tenant_id" = nullif(current_setting('app.tenant_id', true), '')::uuid);--> statement-breakpoint
CREATE POLICY "vh_visitor_pass_tenant_policy" ON "vh_visitor_pass" AS PERMISSIVE FOR ALL TO public USING ("vh_visitor_pass"."tenant_id" = nullif(current_setting('app.tenant_id', true), '')::uuid) WITH CHECK ("vh_visitor_pass"."tenant_id" = nullif(current_setting('app.tenant_id', true), '')::uuid);--> statement-breakpoint
CREATE POLICY "platform_agent_tenant_policy" ON "platform_agent" AS PERMISSIVE FOR ALL TO public USING ("platform_agent"."tenant_id" = nullif(current_setting('app.tenant_id', true), '')::uuid) WITH CHECK ("platform_agent"."tenant_id" = nullif(current_setting('app.tenant_id', true), '')::uuid);--> statement-breakpoint
CREATE POLICY "platform_agent_change_request_tenant_policy" ON "platform_agent_change_request" AS PERMISSIVE FOR ALL TO public USING ("platform_agent_change_request"."tenant_id" = nullif(current_setting('app.tenant_id', true), '')::uuid) WITH CHECK ("platform_agent_change_request"."tenant_id" = nullif(current_setting('app.tenant_id', true), '')::uuid);--> statement-breakpoint
CREATE POLICY "platform_agent_spec_tenant_policy" ON "platform_agent_spec" AS PERMISSIVE FOR ALL TO public USING ("platform_agent_spec"."tenant_id" = nullif(current_setting('app.tenant_id', true), '')::uuid) WITH CHECK ("platform_agent_spec"."tenant_id" = nullif(current_setting('app.tenant_id', true), '')::uuid);--> statement-breakpoint
CREATE POLICY "platform_agent_version_tenant_policy" ON "platform_agent_version" AS PERMISSIVE FOR ALL TO public USING ("platform_agent_version"."tenant_id" = nullif(current_setting('app.tenant_id', true), '')::uuid) WITH CHECK ("platform_agent_version"."tenant_id" = nullif(current_setting('app.tenant_id', true), '')::uuid);--> statement-breakpoint
CREATE POLICY "platform_audit_event_tenant_policy" ON "platform_audit_event" AS PERMISSIVE FOR ALL TO public USING ("platform_audit_event"."tenant_id" = nullif(current_setting('app.tenant_id', true), '')::uuid) WITH CHECK ("platform_audit_event"."tenant_id" = nullif(current_setting('app.tenant_id', true), '')::uuid);--> statement-breakpoint
CREATE POLICY "platform_idempotency_record_tenant_policy" ON "platform_idempotency_record" AS PERMISSIVE FOR ALL TO public USING ("platform_idempotency_record"."tenant_id" = nullif(current_setting('app.tenant_id', true), '')::uuid) WITH CHECK ("platform_idempotency_record"."tenant_id" = nullif(current_setting('app.tenant_id', true), '')::uuid);--> statement-breakpoint
CREATE POLICY "platform_outbox_event_tenant_policy" ON "platform_outbox_event" AS PERMISSIVE FOR ALL TO public USING ("platform_outbox_event"."tenant_id" = nullif(current_setting('app.tenant_id', true), '')::uuid) WITH CHECK ("platform_outbox_event"."tenant_id" = nullif(current_setting('app.tenant_id', true), '')::uuid);--> statement-breakpoint
CREATE POLICY "platform_agent_capability_binding_tenant_policy" ON "platform_agent_capability_binding" AS PERMISSIVE FOR ALL TO public USING ("platform_agent_capability_binding"."tenant_id" = nullif(current_setting('app.tenant_id', true), '')::uuid) WITH CHECK ("platform_agent_capability_binding"."tenant_id" = nullif(current_setting('app.tenant_id', true), '')::uuid);--> statement-breakpoint
CREATE POLICY "platform_agent_knowledge_binding_tenant_policy" ON "platform_agent_knowledge_binding" AS PERMISSIVE FOR ALL TO public USING ("platform_agent_knowledge_binding"."tenant_id" = nullif(current_setting('app.tenant_id', true), '')::uuid) WITH CHECK ("platform_agent_knowledge_binding"."tenant_id" = nullif(current_setting('app.tenant_id', true), '')::uuid);--> statement-breakpoint
CREATE POLICY "platform_agent_model_binding_tenant_policy" ON "platform_agent_model_binding" AS PERMISSIVE FOR ALL TO public USING ("platform_agent_model_binding"."tenant_id" = nullif(current_setting('app.tenant_id', true), '')::uuid) WITH CHECK ("platform_agent_model_binding"."tenant_id" = nullif(current_setting('app.tenant_id', true), '')::uuid);--> statement-breakpoint
CREATE POLICY "platform_agent_policy_binding_tenant_policy" ON "platform_agent_policy_binding" AS PERMISSIVE FOR ALL TO public USING ("platform_agent_policy_binding"."tenant_id" = nullif(current_setting('app.tenant_id', true), '')::uuid) WITH CHECK ("platform_agent_policy_binding"."tenant_id" = nullif(current_setting('app.tenant_id', true), '')::uuid);--> statement-breakpoint
CREATE POLICY "platform_agent_skill_binding_tenant_policy" ON "platform_agent_skill_binding" AS PERMISSIVE FOR ALL TO public USING ("platform_agent_skill_binding"."tenant_id" = nullif(current_setting('app.tenant_id', true), '')::uuid) WITH CHECK ("platform_agent_skill_binding"."tenant_id" = nullif(current_setting('app.tenant_id', true), '')::uuid);--> statement-breakpoint
CREATE POLICY "platform_agent_tool_binding_tenant_policy" ON "platform_agent_tool_binding" AS PERMISSIVE FOR ALL TO public USING ("platform_agent_tool_binding"."tenant_id" = nullif(current_setting('app.tenant_id', true), '')::uuid) WITH CHECK ("platform_agent_tool_binding"."tenant_id" = nullif(current_setting('app.tenant_id', true), '')::uuid);--> statement-breakpoint
CREATE POLICY "platform_capability_tenant_policy" ON "platform_capability" AS PERMISSIVE FOR ALL TO public USING ("platform_capability"."tenant_id" = nullif(current_setting('app.tenant_id', true), '')::uuid) WITH CHECK ("platform_capability"."tenant_id" = nullif(current_setting('app.tenant_id', true), '')::uuid);--> statement-breakpoint
CREATE POLICY "platform_mcp_server_tenant_policy" ON "platform_mcp_server" AS PERMISSIVE FOR ALL TO public USING ("platform_mcp_server"."tenant_id" = nullif(current_setting('app.tenant_id', true), '')::uuid) WITH CHECK ("platform_mcp_server"."tenant_id" = nullif(current_setting('app.tenant_id', true), '')::uuid);--> statement-breakpoint
CREATE POLICY "platform_mcp_server_version_tenant_policy" ON "platform_mcp_server_version" AS PERMISSIVE FOR ALL TO public USING ("platform_mcp_server_version"."tenant_id" = nullif(current_setting('app.tenant_id', true), '')::uuid) WITH CHECK ("platform_mcp_server_version"."tenant_id" = nullif(current_setting('app.tenant_id', true), '')::uuid);--> statement-breakpoint
CREATE POLICY "platform_model_profile_tenant_policy" ON "platform_model_profile" AS PERMISSIVE FOR ALL TO public USING ("platform_model_profile"."tenant_id" = nullif(current_setting('app.tenant_id', true), '')::uuid) WITH CHECK ("platform_model_profile"."tenant_id" = nullif(current_setting('app.tenant_id', true), '')::uuid);--> statement-breakpoint
CREATE POLICY "platform_skill_tenant_policy" ON "platform_skill" AS PERMISSIVE FOR ALL TO public USING ("platform_skill"."tenant_id" = nullif(current_setting('app.tenant_id', true), '')::uuid) WITH CHECK ("platform_skill"."tenant_id" = nullif(current_setting('app.tenant_id', true), '')::uuid);--> statement-breakpoint
CREATE POLICY "platform_skill_version_tenant_policy" ON "platform_skill_version" AS PERMISSIVE FOR ALL TO public USING ("platform_skill_version"."tenant_id" = nullif(current_setting('app.tenant_id', true), '')::uuid) WITH CHECK ("platform_skill_version"."tenant_id" = nullif(current_setting('app.tenant_id', true), '')::uuid);--> statement-breakpoint
CREATE POLICY "platform_tool_tenant_policy" ON "platform_tool" AS PERMISSIVE FOR ALL TO public USING ("platform_tool"."tenant_id" = nullif(current_setting('app.tenant_id', true), '')::uuid) WITH CHECK ("platform_tool"."tenant_id" = nullif(current_setting('app.tenant_id', true), '')::uuid);--> statement-breakpoint
CREATE POLICY "platform_tool_version_tenant_policy" ON "platform_tool_version" AS PERMISSIVE FOR ALL TO public USING ("platform_tool_version"."tenant_id" = nullif(current_setting('app.tenant_id', true), '')::uuid) WITH CHECK ("platform_tool_version"."tenant_id" = nullif(current_setting('app.tenant_id', true), '')::uuid);--> statement-breakpoint
CREATE POLICY "platform_agent_deployment_tenant_policy" ON "platform_agent_deployment" AS PERMISSIVE FOR ALL TO public USING ("platform_agent_deployment"."tenant_id" = nullif(current_setting('app.tenant_id', true), '')::uuid) WITH CHECK ("platform_agent_deployment"."tenant_id" = nullif(current_setting('app.tenant_id', true), '')::uuid);--> statement-breakpoint
CREATE POLICY "platform_domain_installation_tenant_policy" ON "platform_domain_installation" AS PERMISSIVE FOR ALL TO public USING ("platform_domain_installation"."tenant_id" = nullif(current_setting('app.tenant_id', true), '')::uuid) WITH CHECK ("platform_domain_installation"."tenant_id" = nullif(current_setting('app.tenant_id', true), '')::uuid);--> statement-breakpoint
CREATE POLICY "platform_eval_assertion_tenant_policy" ON "platform_eval_assertion" AS PERMISSIVE FOR ALL TO public USING ("platform_eval_assertion"."tenant_id" = nullif(current_setting('app.tenant_id', true), '')::uuid) WITH CHECK ("platform_eval_assertion"."tenant_id" = nullif(current_setting('app.tenant_id', true), '')::uuid);--> statement-breakpoint
CREATE POLICY "platform_eval_case_tenant_policy" ON "platform_eval_case" AS PERMISSIVE FOR ALL TO public USING ("platform_eval_case"."tenant_id" = nullif(current_setting('app.tenant_id', true), '')::uuid) WITH CHECK ("platform_eval_case"."tenant_id" = nullif(current_setting('app.tenant_id', true), '')::uuid);--> statement-breakpoint
CREATE POLICY "platform_eval_evidence_tenant_policy" ON "platform_eval_evidence" AS PERMISSIVE FOR ALL TO public USING ("platform_eval_evidence"."tenant_id" = nullif(current_setting('app.tenant_id', true), '')::uuid) WITH CHECK ("platform_eval_evidence"."tenant_id" = nullif(current_setting('app.tenant_id', true), '')::uuid);--> statement-breakpoint
CREATE POLICY "platform_eval_run_tenant_policy" ON "platform_eval_run" AS PERMISSIVE FOR ALL TO public USING ("platform_eval_run"."tenant_id" = nullif(current_setting('app.tenant_id', true), '')::uuid) WITH CHECK ("platform_eval_run"."tenant_id" = nullif(current_setting('app.tenant_id', true), '')::uuid);--> statement-breakpoint
CREATE POLICY "platform_eval_suite_tenant_policy" ON "platform_eval_suite" AS PERMISSIVE FOR ALL TO public USING ("platform_eval_suite"."tenant_id" = nullif(current_setting('app.tenant_id', true), '')::uuid) WITH CHECK ("platform_eval_suite"."tenant_id" = nullif(current_setting('app.tenant_id', true), '')::uuid);--> statement-breakpoint
CREATE POLICY "platform_publish_approval_tenant_policy" ON "platform_publish_approval" AS PERMISSIVE FOR ALL TO public USING ("platform_publish_approval"."tenant_id" = nullif(current_setting('app.tenant_id', true), '')::uuid) WITH CHECK ("platform_publish_approval"."tenant_id" = nullif(current_setting('app.tenant_id', true), '')::uuid);--> statement-breakpoint
CREATE POLICY "platform_publish_gate_tenant_policy" ON "platform_publish_gate" AS PERMISSIVE FOR ALL TO public USING ("platform_publish_gate"."tenant_id" = nullif(current_setting('app.tenant_id', true), '')::uuid) WITH CHECK ("platform_publish_gate"."tenant_id" = nullif(current_setting('app.tenant_id', true), '')::uuid);--> statement-breakpoint
CREATE POLICY "platform_publish_gate_result_tenant_policy" ON "platform_publish_gate_result" AS PERMISSIVE FOR ALL TO public USING ("platform_publish_gate_result"."tenant_id" = nullif(current_setting('app.tenant_id', true), '')::uuid) WITH CHECK ("platform_publish_gate_result"."tenant_id" = nullif(current_setting('app.tenant_id', true), '')::uuid);--> statement-breakpoint
CREATE POLICY "platform_regression_baseline_tenant_policy" ON "platform_regression_baseline" AS PERMISSIVE FOR ALL TO public USING ("platform_regression_baseline"."tenant_id" = nullif(current_setting('app.tenant_id', true), '')::uuid) WITH CHECK ("platform_regression_baseline"."tenant_id" = nullif(current_setting('app.tenant_id', true), '')::uuid);--> statement-breakpoint
CREATE POLICY "platform_membership_role_tenant_policy" ON "platform_membership_role" AS PERMISSIVE FOR ALL TO public USING ("platform_membership_role"."tenant_id" = nullif(current_setting('app.tenant_id', true), '')::uuid) WITH CHECK ("platform_membership_role"."tenant_id" = nullif(current_setting('app.tenant_id', true), '')::uuid);--> statement-breakpoint
CREATE POLICY "platform_role_tenant_policy" ON "platform_role" AS PERMISSIVE FOR ALL TO public USING ("platform_role"."tenant_id" = nullif(current_setting('app.tenant_id', true), '')::uuid) WITH CHECK ("platform_role"."tenant_id" = nullif(current_setting('app.tenant_id', true), '')::uuid);--> statement-breakpoint
CREATE POLICY "platform_tenant_tenant_policy" ON "platform_tenant" AS PERMISSIVE FOR ALL TO public USING ("platform_tenant"."id" = nullif(current_setting('app.tenant_id', true), '')::uuid) WITH CHECK ("platform_tenant"."id" = nullif(current_setting('app.tenant_id', true), '')::uuid);--> statement-breakpoint
CREATE POLICY "platform_tenant_membership_tenant_policy" ON "platform_tenant_membership" AS PERMISSIVE FOR ALL TO public USING ("platform_tenant_membership"."tenant_id" = nullif(current_setting('app.tenant_id', true), '')::uuid) WITH CHECK ("platform_tenant_membership"."tenant_id" = nullif(current_setting('app.tenant_id', true), '')::uuid);--> statement-breakpoint
CREATE POLICY "platform_knowledge_base_tenant_policy" ON "platform_knowledge_base" AS PERMISSIVE FOR ALL TO public USING ("platform_knowledge_base"."tenant_id" = nullif(current_setting('app.tenant_id', true), '')::uuid) WITH CHECK ("platform_knowledge_base"."tenant_id" = nullif(current_setting('app.tenant_id', true), '')::uuid);--> statement-breakpoint
CREATE POLICY "platform_knowledge_revision_tenant_policy" ON "platform_knowledge_revision" AS PERMISSIVE FOR ALL TO public USING ("platform_knowledge_revision"."tenant_id" = nullif(current_setting('app.tenant_id', true), '')::uuid) WITH CHECK ("platform_knowledge_revision"."tenant_id" = nullif(current_setting('app.tenant_id', true), '')::uuid);--> statement-breakpoint
CREATE POLICY "platform_knowledge_source_tenant_policy" ON "platform_knowledge_source" AS PERMISSIVE FOR ALL TO public USING ("platform_knowledge_source"."tenant_id" = nullif(current_setting('app.tenant_id', true), '')::uuid) WITH CHECK ("platform_knowledge_source"."tenant_id" = nullif(current_setting('app.tenant_id', true), '')::uuid);--> statement-breakpoint
CREATE POLICY "platform_memory_item_tenant_policy" ON "platform_memory_item" AS PERMISSIVE FOR ALL TO public USING ("platform_memory_item"."tenant_id" = nullif(current_setting('app.tenant_id', true), '')::uuid) WITH CHECK ("platform_memory_item"."tenant_id" = nullif(current_setting('app.tenant_id', true), '')::uuid);--> statement-breakpoint
CREATE POLICY "platform_memory_namespace_tenant_policy" ON "platform_memory_namespace" AS PERMISSIVE FOR ALL TO public USING ("platform_memory_namespace"."tenant_id" = nullif(current_setting('app.tenant_id', true), '')::uuid) WITH CHECK ("platform_memory_namespace"."tenant_id" = nullif(current_setting('app.tenant_id', true), '')::uuid);--> statement-breakpoint
CREATE POLICY "platform_memory_review_tenant_policy" ON "platform_memory_review" AS PERMISSIVE FOR ALL TO public USING ("platform_memory_review"."tenant_id" = nullif(current_setting('app.tenant_id', true), '')::uuid) WITH CHECK ("platform_memory_review"."tenant_id" = nullif(current_setting('app.tenant_id', true), '')::uuid);--> statement-breakpoint
CREATE POLICY "platform_memory_revision_tenant_policy" ON "platform_memory_revision" AS PERMISSIVE FOR ALL TO public USING ("platform_memory_revision"."tenant_id" = nullif(current_setting('app.tenant_id', true), '')::uuid) WITH CHECK ("platform_memory_revision"."tenant_id" = nullif(current_setting('app.tenant_id', true), '')::uuid);--> statement-breakpoint
CREATE POLICY "platform_memory_vector_ref_tenant_policy" ON "platform_memory_vector_ref" AS PERMISSIVE FOR ALL TO public USING ("platform_memory_vector_ref"."tenant_id" = nullif(current_setting('app.tenant_id', true), '')::uuid) WITH CHECK ("platform_memory_vector_ref"."tenant_id" = nullif(current_setting('app.tenant_id', true), '')::uuid);--> statement-breakpoint
CREATE POLICY "platform_policy_tenant_policy" ON "platform_policy" AS PERMISSIVE FOR ALL TO public USING ("platform_policy"."tenant_id" = nullif(current_setting('app.tenant_id', true), '')::uuid) WITH CHECK ("platform_policy"."tenant_id" = nullif(current_setting('app.tenant_id', true), '')::uuid);--> statement-breakpoint
CREATE POLICY "platform_policy_version_tenant_policy" ON "platform_policy_version" AS PERMISSIVE FOR ALL TO public USING ("platform_policy_version"."tenant_id" = nullif(current_setting('app.tenant_id', true), '')::uuid) WITH CHECK ("platform_policy_version"."tenant_id" = nullif(current_setting('app.tenant_id', true), '')::uuid);--> statement-breakpoint
CREATE POLICY "platform_action_proposal_tenant_policy" ON "platform_action_proposal" AS PERMISSIVE FOR ALL TO public USING ("platform_action_proposal"."tenant_id" = nullif(current_setting('app.tenant_id', true), '')::uuid) WITH CHECK ("platform_action_proposal"."tenant_id" = nullif(current_setting('app.tenant_id', true), '')::uuid);--> statement-breakpoint
CREATE POLICY "platform_agent_run_tenant_policy" ON "platform_agent_run" AS PERMISSIVE FOR ALL TO public USING ("platform_agent_run"."tenant_id" = nullif(current_setting('app.tenant_id', true), '')::uuid) WITH CHECK ("platform_agent_run"."tenant_id" = nullif(current_setting('app.tenant_id', true), '')::uuid);--> statement-breakpoint
CREATE POLICY "platform_execution_grant_ref_tenant_policy" ON "platform_execution_grant_ref" AS PERMISSIVE FOR ALL TO public USING ("platform_execution_grant_ref"."tenant_id" = nullif(current_setting('app.tenant_id', true), '')::uuid) WITH CHECK ("platform_execution_grant_ref"."tenant_id" = nullif(current_setting('app.tenant_id', true), '')::uuid);--> statement-breakpoint
CREATE POLICY "platform_run_step_tenant_policy" ON "platform_run_step" AS PERMISSIVE FOR ALL TO public USING ("platform_run_step"."tenant_id" = nullif(current_setting('app.tenant_id', true), '')::uuid) WITH CHECK ("platform_run_step"."tenant_id" = nullif(current_setting('app.tenant_id', true), '')::uuid);--> statement-breakpoint
CREATE POLICY "platform_run_step_dependency_tenant_policy" ON "platform_run_step_dependency" AS PERMISSIVE FOR ALL TO public USING ("platform_run_step_dependency"."tenant_id" = nullif(current_setting('app.tenant_id', true), '')::uuid) WITH CHECK ("platform_run_step_dependency"."tenant_id" = nullif(current_setting('app.tenant_id', true), '')::uuid);--> statement-breakpoint
CREATE POLICY "platform_runtime_artifact_tenant_policy" ON "platform_runtime_artifact" AS PERMISSIVE FOR ALL TO public USING ("platform_runtime_artifact"."tenant_id" = nullif(current_setting('app.tenant_id', true), '')::uuid) WITH CHECK ("platform_runtime_artifact"."tenant_id" = nullif(current_setting('app.tenant_id', true), '')::uuid);--> statement-breakpoint
CREATE POLICY "platform_runtime_decision_tenant_policy" ON "platform_runtime_decision" AS PERMISSIVE FOR ALL TO public USING ("platform_runtime_decision"."tenant_id" = nullif(current_setting('app.tenant_id', true), '')::uuid) WITH CHECK ("platform_runtime_decision"."tenant_id" = nullif(current_setting('app.tenant_id', true), '')::uuid);--> statement-breakpoint
CREATE POLICY "platform_tool_call_tenant_policy" ON "platform_tool_call" AS PERMISSIVE FOR ALL TO public USING ("platform_tool_call"."tenant_id" = nullif(current_setting('app.tenant_id', true), '')::uuid) WITH CHECK ("platform_tool_call"."tenant_id" = nullif(current_setting('app.tenant_id', true), '')::uuid);--> statement-breakpoint
CREATE POLICY "platform_workflow_session_tenant_policy" ON "platform_workflow_session" AS PERMISSIVE FOR ALL TO public USING ("platform_workflow_session"."tenant_id" = nullif(current_setting('app.tenant_id', true), '')::uuid) WITH CHECK ("platform_workflow_session"."tenant_id" = nullif(current_setting('app.tenant_id', true), '')::uuid);