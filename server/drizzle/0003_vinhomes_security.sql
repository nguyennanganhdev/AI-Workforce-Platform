CREATE TABLE "security_alert_deliveries" (
	"id" uuid PRIMARY KEY DEFAULT gen_random_uuid() NOT NULL,
	"tenant_id" uuid NOT NULL,
	"alert_id" uuid NOT NULL,
	"contact_id" uuid NOT NULL,
	"recipient_user_id" text NOT NULL,
	"position" integer NOT NULL,
	"ack_timeout_seconds" integer NOT NULL,
	"status" text DEFAULT 'waiting' NOT NULL,
	"notified_at" timestamp with time zone,
	"deadline_at" timestamp with time zone,
	"acknowledged_at" timestamp with time zone,
	CONSTRAINT "security_deliveries_tenant_key" UNIQUE("tenant_id","id"),
	CONSTRAINT "security_deliveries_order" UNIQUE("tenant_id","alert_id","position"),
	CONSTRAINT "security_deliveries_status" CHECK (status IN ('waiting','pending','acknowledged','timed_out','cancelled') AND position > 0 AND ack_timeout_seconds BETWEEN 5 AND 3600)
);
--> statement-breakpoint
ALTER TABLE "security_alert_deliveries" ENABLE ROW LEVEL SECURITY;--> statement-breakpoint
CREATE TABLE "security_alerts" (
	"id" uuid PRIMARY KEY DEFAULT gen_random_uuid() NOT NULL,
	"tenant_id" uuid NOT NULL,
	"ticket_id" uuid NOT NULL,
	"created_by" text NOT NULL,
	"message" text NOT NULL,
	"idempotency_key" text NOT NULL,
	"request_hash" text NOT NULL,
	"status" text DEFAULT 'open' NOT NULL,
	"version" integer DEFAULT 0 NOT NULL,
	"created_at" timestamp with time zone DEFAULT now() NOT NULL,
	"updated_at" timestamp with time zone DEFAULT now() NOT NULL,
	CONSTRAINT "security_alerts_tenant_key" UNIQUE("tenant_id","id"),
	CONSTRAINT "security_alerts_idempotency" UNIQUE("tenant_id","ticket_id","idempotency_key"),
	CONSTRAINT "security_alerts_status" CHECK (status IN ('open','acknowledged','exhausted') AND version >= 0)
);
--> statement-breakpoint
ALTER TABLE "security_alerts" ENABLE ROW LEVEL SECURITY;--> statement-breakpoint
CREATE TABLE "security_cameras" (
	"id" uuid PRIMARY KEY DEFAULT gen_random_uuid() NOT NULL,
	"tenant_id" uuid NOT NULL,
	"building_id" uuid NOT NULL,
	"code" text NOT NULL,
	"name" text NOT NULL,
	"location" text NOT NULL,
	"status" text NOT NULL,
	"created_at" timestamp with time zone DEFAULT now() NOT NULL,
	CONSTRAINT "security_cameras_tenant_key" UNIQUE("tenant_id","id"),
	CONSTRAINT "security_cameras_code" UNIQUE("tenant_id","building_id","code"),
	CONSTRAINT "security_cameras_status" CHECK (status IN ('online','offline','maintenance'))
);
--> statement-breakpoint
ALTER TABLE "security_cameras" ENABLE ROW LEVEL SECURITY;--> statement-breakpoint
CREATE TABLE "security_emergency_contacts" (
	"id" uuid PRIMARY KEY DEFAULT gen_random_uuid() NOT NULL,
	"tenant_id" uuid NOT NULL,
	"building_id" uuid NOT NULL,
	"user_id" text NOT NULL,
	"name" text NOT NULL,
	"role_label" text NOT NULL,
	"phone" text NOT NULL,
	"position" integer NOT NULL,
	"ack_timeout_seconds" integer DEFAULT 60 NOT NULL,
	"status" text DEFAULT 'active' NOT NULL,
	CONSTRAINT "security_contacts_tenant_key" UNIQUE("tenant_id","id"),
	CONSTRAINT "security_contacts_order" UNIQUE("tenant_id","building_id","position"),
	CONSTRAINT "security_contacts_values" CHECK (position > 0 AND ack_timeout_seconds BETWEEN 5 AND 3600 AND status IN ('active','disabled'))
);
--> statement-breakpoint
ALTER TABLE "security_emergency_contacts" ENABLE ROW LEVEL SECURITY;--> statement-breakpoint
ALTER TABLE security_cameras FORCE ROW LEVEL SECURITY;
ALTER TABLE security_emergency_contacts FORCE ROW LEVEL SECURITY;
ALTER TABLE security_alerts FORCE ROW LEVEL SECURITY;
ALTER TABLE security_alert_deliveries FORCE ROW LEVEL SECURITY;
--> statement-breakpoint
ALTER TABLE "work_approvals" DROP CONSTRAINT "work_approvals_check_1";--> statement-breakpoint
ALTER TABLE "security_alert_deliveries" ADD CONSTRAINT "security_alert_deliveries_tenant_id_tenants_id_fk" FOREIGN KEY ("tenant_id") REFERENCES "public"."tenants"("id") ON DELETE no action ON UPDATE no action;--> statement-breakpoint
ALTER TABLE "security_alert_deliveries" ADD CONSTRAINT "security_alert_deliveries_recipient_user_id_users_id_fk" FOREIGN KEY ("recipient_user_id") REFERENCES "public"."users"("id") ON DELETE no action ON UPDATE no action;--> statement-breakpoint
ALTER TABLE "security_alert_deliveries" ADD CONSTRAINT "security_alert_deliveries_tenant_id_alert_id_security_alerts_tenant_id_id_fk" FOREIGN KEY ("tenant_id","alert_id") REFERENCES "public"."security_alerts"("tenant_id","id") ON DELETE no action ON UPDATE no action;--> statement-breakpoint
ALTER TABLE "security_alert_deliveries" ADD CONSTRAINT "security_alert_deliveries_tenant_id_contact_id_security_emergency_contacts_tenant_id_id_fk" FOREIGN KEY ("tenant_id","contact_id") REFERENCES "public"."security_emergency_contacts"("tenant_id","id") ON DELETE no action ON UPDATE no action;--> statement-breakpoint
ALTER TABLE "security_alerts" ADD CONSTRAINT "security_alerts_tenant_id_tenants_id_fk" FOREIGN KEY ("tenant_id") REFERENCES "public"."tenants"("id") ON DELETE no action ON UPDATE no action;--> statement-breakpoint
ALTER TABLE "security_alerts" ADD CONSTRAINT "security_alerts_created_by_users_id_fk" FOREIGN KEY ("created_by") REFERENCES "public"."users"("id") ON DELETE no action ON UPDATE no action;--> statement-breakpoint
ALTER TABLE "security_alerts" ADD CONSTRAINT "security_alerts_tenant_id_ticket_id_tickets_tenant_id_id_fk" FOREIGN KEY ("tenant_id","ticket_id") REFERENCES "public"."tickets"("tenant_id","id") ON DELETE no action ON UPDATE no action;--> statement-breakpoint
ALTER TABLE "security_cameras" ADD CONSTRAINT "security_cameras_tenant_id_tenants_id_fk" FOREIGN KEY ("tenant_id") REFERENCES "public"."tenants"("id") ON DELETE no action ON UPDATE no action;--> statement-breakpoint
ALTER TABLE "security_cameras" ADD CONSTRAINT "security_cameras_tenant_id_building_id_buildings_tenant_id_id_fk" FOREIGN KEY ("tenant_id","building_id") REFERENCES "public"."buildings"("tenant_id","id") ON DELETE no action ON UPDATE no action;--> statement-breakpoint
ALTER TABLE "security_emergency_contacts" ADD CONSTRAINT "security_emergency_contacts_tenant_id_tenants_id_fk" FOREIGN KEY ("tenant_id") REFERENCES "public"."tenants"("id") ON DELETE no action ON UPDATE no action;--> statement-breakpoint
ALTER TABLE "security_emergency_contacts" ADD CONSTRAINT "security_emergency_contacts_user_id_users_id_fk" FOREIGN KEY ("user_id") REFERENCES "public"."users"("id") ON DELETE no action ON UPDATE no action;--> statement-breakpoint
ALTER TABLE "security_emergency_contacts" ADD CONSTRAINT "security_emergency_contacts_tenant_id_building_id_buildings_tenant_id_id_fk" FOREIGN KEY ("tenant_id","building_id") REFERENCES "public"."buildings"("tenant_id","id") ON DELETE no action ON UPDATE no action;--> statement-breakpoint
ALTER TABLE "work_approvals" ADD CONSTRAINT "work_approvals_check_1" CHECK (kind IN ('customer_repair','management_water_shutdown','customer_completion','management_security_dispatch','management_security_cancel'));--> statement-breakpoint
CREATE POLICY "security_deliveries_tenant" ON "security_alert_deliveries" AS PERMISSIVE FOR ALL TO public USING (tenant_id = nullif(current_setting('app.tenant_id', true), '')::uuid) WITH CHECK (tenant_id = nullif(current_setting('app.tenant_id', true), '')::uuid);--> statement-breakpoint
CREATE POLICY "security_alerts_tenant" ON "security_alerts" AS PERMISSIVE FOR ALL TO public USING (tenant_id = nullif(current_setting('app.tenant_id', true), '')::uuid) WITH CHECK (tenant_id = nullif(current_setting('app.tenant_id', true), '')::uuid);--> statement-breakpoint
CREATE POLICY "security_cameras_tenant" ON "security_cameras" AS PERMISSIVE FOR ALL TO public USING (tenant_id = nullif(current_setting('app.tenant_id', true), '')::uuid) WITH CHECK (tenant_id = nullif(current_setting('app.tenant_id', true), '')::uuid);--> statement-breakpoint
CREATE POLICY "security_contacts_tenant" ON "security_emergency_contacts" AS PERMISSIVE FOR ALL TO public USING (tenant_id = nullif(current_setting('app.tenant_id', true), '')::uuid) WITH CHECK (tenant_id = nullif(current_setting('app.tenant_id', true), '')::uuid);
