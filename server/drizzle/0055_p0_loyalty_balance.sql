-- No local loyalty state is carried across this P0 aggregate change.
DO $$ BEGIN
  IF EXISTS (SELECT 1 FROM vh_loyalty_account) OR EXISTS (SELECT 1 FROM vh_loyalty_entry) THEN
    RAISE EXCEPTION '0055 requires empty legacy loyalty data; migrate it explicitly first';
  END IF;
END $$;
--> statement-breakpoint
CREATE TABLE "vh_loyalty_balance" (
	"id" uuid PRIMARY KEY DEFAULT gen_random_uuid() NOT NULL,
	"tenant_id" uuid NOT NULL,
	"user_id" text NOT NULL,
	"program" text NOT NULL,
	"balance" bigint DEFAULT 0 NOT NULL,
	"tier" text NOT NULL,
	"provider_ref" text,
	"created_at" timestamp with time zone DEFAULT now() NOT NULL,
	"version" bigint DEFAULT 1 NOT NULL,
	"updated_at" timestamp with time zone DEFAULT now() NOT NULL,
	CONSTRAINT "vh_loyalty_balance_user_program_uq" UNIQUE("tenant_id","user_id","program"),
	CONSTRAINT "vh_loyalty_balance_tenant_id_uq" UNIQUE("tenant_id","id"),
	CONSTRAINT "vh_loyalty_balance_nonnegative_ck" CHECK ("vh_loyalty_balance"."balance" >= 0),
	CONSTRAINT "vh_loyalty_balance_version_ck" CHECK ("vh_loyalty_balance"."version" > 0)
);
--> statement-breakpoint
ALTER TABLE "vh_loyalty_balance" ENABLE ROW LEVEL SECURITY;--> statement-breakpoint
DROP POLICY "vh_loyalty_account_tenant_policy" ON "vh_loyalty_account" CASCADE;--> statement-breakpoint
DROP TABLE "vh_loyalty_account" CASCADE;--> statement-breakpoint
DROP POLICY "vh_loyalty_entry_tenant_policy" ON "vh_loyalty_entry" CASCADE;--> statement-breakpoint
DROP TABLE "vh_loyalty_entry" CASCADE;--> statement-breakpoint
ALTER TABLE "vh_loyalty_balance" ADD CONSTRAINT "vh_loyalty_balance_tenant_fk" FOREIGN KEY ("tenant_id") REFERENCES "public"."platform_tenant"("id") ON DELETE restrict ON UPDATE no action;--> statement-breakpoint
ALTER TABLE "vh_loyalty_balance" ADD CONSTRAINT "vh_loyalty_balance_user_fk" FOREIGN KEY ("user_id") REFERENCES "public"."users"("id") ON DELETE restrict ON UPDATE no action;--> statement-breakpoint
CREATE INDEX "vh_loyalty_balance_user_ix" ON "vh_loyalty_balance" USING btree ("user_id");--> statement-breakpoint
CREATE POLICY "vh_loyalty_balance_tenant_policy" ON "vh_loyalty_balance" AS PERMISSIVE FOR ALL TO public USING ("vh_loyalty_balance"."tenant_id" = nullif(current_setting('app.tenant_id', true), '')::uuid) WITH CHECK ("vh_loyalty_balance"."tenant_id" = nullif(current_setting('app.tenant_id', true), '')::uuid);
--> statement-breakpoint
ALTER TABLE vh_loyalty_balance FORCE ROW LEVEL SECURITY;
