-- P0 replacement is local-only. Never discard configured role assignments.
DO $$ BEGIN
  IF EXISTS (SELECT 1 FROM platform_role) OR EXISTS (SELECT 1 FROM platform_membership_role) THEN
    RAISE EXCEPTION '0053 requires empty legacy roles; migrate role and scope data explicitly first';
  END IF;
END $$;
--> statement-breakpoint
CREATE TABLE "auth_external_identity" (
	"id" uuid PRIMARY KEY DEFAULT gen_random_uuid() NOT NULL,
	"tenant_id" uuid DEFAULT nullif(current_setting('app.tenant_id', true), '')::uuid NOT NULL,
	"local_user_id" text NOT NULL,
	"provider" text NOT NULL,
	"issuer" text NOT NULL,
	"external_subject" text NOT NULL,
	"status" text DEFAULT 'ACTIVE' NOT NULL,
	"last_login_at" timestamp with time zone,
	"created_at" timestamp with time zone DEFAULT now() NOT NULL,
	"version" bigint DEFAULT 1 NOT NULL,
	"updated_at" timestamp with time zone DEFAULT now() NOT NULL,
	CONSTRAINT "auth_external_identity_issuer_subject_uq" UNIQUE("issuer","external_subject"),
	CONSTRAINT "auth_external_identity_status_ck" CHECK ("auth_external_identity"."status" in ('ACTIVE', 'SUSPENDED', 'REVOKED')),
	CONSTRAINT "auth_external_identity_subject_ck" CHECK (length(trim("auth_external_identity"."issuer")) > 0 AND length(trim("auth_external_identity"."external_subject")) > 0),
	CONSTRAINT "auth_external_identity_version_ck" CHECK ("auth_external_identity"."version" > 0)
);
--> statement-breakpoint
ALTER TABLE "auth_external_identity" ENABLE ROW LEVEL SECURITY;--> statement-breakpoint
CREATE TABLE "auth_permission" (
	"id" uuid PRIMARY KEY DEFAULT gen_random_uuid() NOT NULL,
	"domain_namespace" text NOT NULL,
	"code" text NOT NULL,
	"resource" text NOT NULL,
	"action" text NOT NULL,
	"risk_level" text NOT NULL,
	"description" text NOT NULL,
	"created_at" timestamp with time zone DEFAULT now() NOT NULL,
	CONSTRAINT "auth_permission_code_uq" UNIQUE("domain_namespace","code"),
	CONSTRAINT "auth_permission_risk_ck" CHECK ("auth_permission"."risk_level" in ('LOW', 'MEDIUM', 'HIGH', 'CRITICAL'))
);
--> statement-breakpoint
ALTER TABLE "auth_permission" ENABLE ROW LEVEL SECURITY;--> statement-breakpoint
CREATE TABLE "auth_role" (
	"id" uuid PRIMARY KEY DEFAULT gen_random_uuid() NOT NULL,
	"tenant_id" uuid,
	"domain_namespace" text NOT NULL,
	"code" text NOT NULL,
	"name" text NOT NULL,
	"role_type" text NOT NULL,
	"status" text DEFAULT 'ACTIVE' NOT NULL,
	"created_at" timestamp with time zone DEFAULT now() NOT NULL,
	"version" bigint DEFAULT 1 NOT NULL,
	"updated_at" timestamp with time zone DEFAULT now() NOT NULL,
	CONSTRAINT "auth_role_type_ck" CHECK ("auth_role"."role_type" in ('SYSTEM', 'CUSTOM')),
	CONSTRAINT "auth_role_status_ck" CHECK ("auth_role"."status" in ('ACTIVE', 'SUSPENDED', 'RETIRED')),
	CONSTRAINT "auth_role_ownership_ck" CHECK (("auth_role"."role_type" = 'SYSTEM' AND "auth_role"."tenant_id" IS NULL) OR ("auth_role"."role_type" = 'CUSTOM' AND "auth_role"."tenant_id" IS NOT NULL)),
	CONSTRAINT "auth_role_version_ck" CHECK ("auth_role"."version" > 0)
);
--> statement-breakpoint
ALTER TABLE "auth_role" ENABLE ROW LEVEL SECURITY;--> statement-breakpoint
CREATE TABLE "auth_role_assignment" (
	"id" uuid PRIMARY KEY DEFAULT gen_random_uuid() NOT NULL,
	"tenant_id" uuid DEFAULT nullif(current_setting('app.tenant_id', true), '')::uuid NOT NULL,
	"user_id" text NOT NULL,
	"role_id" uuid NOT NULL,
	"domain_namespace" text NOT NULL,
	"scope_type" text NOT NULL,
	"scope_ref" text NOT NULL,
	"valid_from" timestamp with time zone NOT NULL,
	"valid_until" timestamp with time zone,
	"status" text DEFAULT 'ACTIVE' NOT NULL,
	"created_at" timestamp with time zone DEFAULT now() NOT NULL,
	"version" bigint DEFAULT 1 NOT NULL,
	"updated_at" timestamp with time zone DEFAULT now() NOT NULL,
	CONSTRAINT "auth_role_assignment_period_uq" UNIQUE("tenant_id","user_id","role_id","domain_namespace","scope_type","scope_ref","valid_from"),
	CONSTRAINT "auth_role_assignment_status_ck" CHECK ("auth_role_assignment"."status" in ('ACTIVE', 'SUSPENDED', 'REVOKED')),
	CONSTRAINT "auth_role_assignment_scope_ck" CHECK ("auth_role_assignment"."scope_type" in ('TENANT', 'DOMAIN', 'PROJECT', 'TOWER', 'APARTMENT', 'RESOURCE')),
	CONSTRAINT "auth_role_assignment_period_ck" CHECK ("auth_role_assignment"."valid_until" IS NULL OR "auth_role_assignment"."valid_until" > "auth_role_assignment"."valid_from"),
	CONSTRAINT "auth_role_assignment_ref_ck" CHECK (length(trim("auth_role_assignment"."scope_ref")) > 0),
	CONSTRAINT "auth_role_assignment_version_ck" CHECK ("auth_role_assignment"."version" > 0)
);
--> statement-breakpoint
ALTER TABLE "auth_role_assignment" ENABLE ROW LEVEL SECURITY;--> statement-breakpoint
CREATE TABLE "auth_role_permission" (
	"role_id" uuid NOT NULL,
	"permission_id" uuid NOT NULL,
	"created_at" timestamp with time zone DEFAULT now() NOT NULL,
	CONSTRAINT "auth_role_permission_role_id_permission_id_pk" PRIMARY KEY("role_id","permission_id")
);
--> statement-breakpoint
ALTER TABLE "auth_role_permission" ENABLE ROW LEVEL SECURITY;--> statement-breakpoint
DROP POLICY "platform_membership_role_tenant_policy" ON "platform_membership_role" CASCADE;--> statement-breakpoint
DROP TABLE "platform_membership_role" CASCADE;--> statement-breakpoint
DROP POLICY "platform_role_tenant_policy" ON "platform_role" CASCADE;--> statement-breakpoint
DROP TABLE "platform_role" CASCADE;--> statement-breakpoint
ALTER TABLE "auth_external_identity" ADD CONSTRAINT "auth_external_identity_tenant_id_platform_tenant_id_fk" FOREIGN KEY ("tenant_id") REFERENCES "public"."platform_tenant"("id") ON DELETE restrict ON UPDATE no action;--> statement-breakpoint
ALTER TABLE "auth_external_identity" ADD CONSTRAINT "auth_external_identity_local_user_id_users_id_fk" FOREIGN KEY ("local_user_id") REFERENCES "public"."users"("id") ON DELETE restrict ON UPDATE no action;--> statement-breakpoint
ALTER TABLE "auth_role" ADD CONSTRAINT "auth_role_tenant_id_platform_tenant_id_fk" FOREIGN KEY ("tenant_id") REFERENCES "public"."platform_tenant"("id") ON DELETE restrict ON UPDATE no action;--> statement-breakpoint
ALTER TABLE "auth_role_assignment" ADD CONSTRAINT "auth_role_assignment_tenant_id_platform_tenant_id_fk" FOREIGN KEY ("tenant_id") REFERENCES "public"."platform_tenant"("id") ON DELETE restrict ON UPDATE no action;--> statement-breakpoint
ALTER TABLE "auth_role_assignment" ADD CONSTRAINT "auth_role_assignment_role_id_auth_role_id_fk" FOREIGN KEY ("role_id") REFERENCES "public"."auth_role"("id") ON DELETE restrict ON UPDATE no action;--> statement-breakpoint
ALTER TABLE "auth_role_assignment" ADD CONSTRAINT "auth_role_assignment_membership_fk" FOREIGN KEY ("tenant_id","user_id") REFERENCES "public"."platform_tenant_membership"("tenant_id","user_id") ON DELETE restrict ON UPDATE no action;--> statement-breakpoint
ALTER TABLE "auth_role_permission" ADD CONSTRAINT "auth_role_permission_role_id_auth_role_id_fk" FOREIGN KEY ("role_id") REFERENCES "public"."auth_role"("id") ON DELETE restrict ON UPDATE no action;--> statement-breakpoint
ALTER TABLE "auth_role_permission" ADD CONSTRAINT "auth_role_permission_permission_id_auth_permission_id_fk" FOREIGN KEY ("permission_id") REFERENCES "public"."auth_permission"("id") ON DELETE restrict ON UPDATE no action;--> statement-breakpoint
CREATE INDEX "auth_external_identity_user_ix" ON "auth_external_identity" USING btree ("tenant_id","local_user_id");--> statement-breakpoint
CREATE UNIQUE INDEX "auth_role_global_code_uq" ON "auth_role" USING btree ("domain_namespace","code") WHERE "auth_role"."tenant_id" IS NULL;--> statement-breakpoint
CREATE UNIQUE INDEX "auth_role_tenant_code_uq" ON "auth_role" USING btree ("tenant_id","domain_namespace","code") WHERE "auth_role"."tenant_id" IS NOT NULL;--> statement-breakpoint
CREATE INDEX "auth_role_assignment_context_ix" ON "auth_role_assignment" USING btree ("tenant_id","user_id","status","valid_until");--> statement-breakpoint
CREATE INDEX "auth_role_assignment_role_ix" ON "auth_role_assignment" USING btree ("role_id");--> statement-breakpoint
CREATE INDEX "auth_role_permission_permission_ix" ON "auth_role_permission" USING btree ("permission_id");--> statement-breakpoint
CREATE POLICY "auth_external_identity_tenant_policy" ON "auth_external_identity" AS PERMISSIVE FOR ALL TO public USING ("auth_external_identity"."tenant_id" = nullif(current_setting('app.tenant_id', true), '')::uuid) WITH CHECK ("auth_external_identity"."tenant_id" = nullif(current_setting('app.tenant_id', true), '')::uuid);--> statement-breakpoint
CREATE POLICY "auth_permission_read_policy" ON "auth_permission" AS PERMISSIVE FOR SELECT TO public USING (true);--> statement-breakpoint
CREATE POLICY "auth_role_read_policy" ON "auth_role" AS PERMISSIVE FOR SELECT TO public USING ("auth_role"."tenant_id" IS NULL OR "auth_role"."tenant_id" = nullif(current_setting('app.tenant_id', true), '')::uuid);--> statement-breakpoint
CREATE POLICY "auth_role_write_policy" ON "auth_role" AS PERMISSIVE FOR ALL TO public USING ("auth_role"."tenant_id" = nullif(current_setting('app.tenant_id', true), '')::uuid) WITH CHECK ("auth_role"."tenant_id" = nullif(current_setting('app.tenant_id', true), '')::uuid);--> statement-breakpoint
CREATE POLICY "auth_role_assignment_tenant_policy" ON "auth_role_assignment" AS PERMISSIVE FOR ALL TO public USING ("auth_role_assignment"."tenant_id" = nullif(current_setting('app.tenant_id', true), '')::uuid) WITH CHECK ("auth_role_assignment"."tenant_id" = nullif(current_setting('app.tenant_id', true), '')::uuid);--> statement-breakpoint
CREATE POLICY "auth_role_permission_read_policy" ON "auth_role_permission" AS PERMISSIVE FOR SELECT TO public USING (EXISTS (SELECT 1 FROM auth_role r WHERE r.id = "auth_role_permission"."role_id"));--> statement-breakpoint
CREATE POLICY "auth_role_permission_write_policy" ON "auth_role_permission" AS PERMISSIVE FOR ALL TO public USING (EXISTS (SELECT 1 FROM auth_role r WHERE r.id = "auth_role_permission"."role_id" AND r.tenant_id = nullif(current_setting('app.tenant_id', true), '')::uuid)) WITH CHECK (EXISTS (SELECT 1 FROM auth_role r WHERE r.id = "auth_role_permission"."role_id" AND r.tenant_id = nullif(current_setting('app.tenant_id', true), '')::uuid));
--> statement-breakpoint
ALTER TABLE auth_external_identity FORCE ROW LEVEL SECURITY;
--> statement-breakpoint
ALTER TABLE auth_role FORCE ROW LEVEL SECURITY;
--> statement-breakpoint
ALTER TABLE auth_permission FORCE ROW LEVEL SECURITY;
--> statement-breakpoint
ALTER TABLE auth_role_permission FORCE ROW LEVEL SECURITY;
--> statement-breakpoint
ALTER TABLE auth_role_assignment FORCE ROW LEVEL SECURITY;
--> statement-breakpoint
CREATE FUNCTION auth_p0_identity_guard() RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN
  IF TG_OP = 'UPDATE' THEN
    IF NEW.id IS DISTINCT FROM OLD.id OR NEW.created_at IS DISTINCT FROM OLD.created_at
       OR NEW.tenant_id IS DISTINCT FROM OLD.tenant_id THEN
      RAISE EXCEPTION 'Authorization identity/tenant is immutable' USING ERRCODE = '23514';
    END IF;
    IF TG_TABLE_NAME = 'auth_external_identity' THEN
      IF
      (NEW.local_user_id IS DISTINCT FROM OLD.local_user_id OR NEW.issuer IS DISTINCT FROM OLD.issuer
       OR NEW.external_subject IS DISTINCT FROM OLD.external_subject OR NEW.provider IS DISTINCT FROM OLD.provider) THEN
      RAISE EXCEPTION 'SSO subject mapping is immutable; revoke and provision explicitly' USING ERRCODE = '23514';
    END IF;
    END IF;
    IF TG_TABLE_NAME = 'auth_role' THEN
      IF
      (NEW.domain_namespace IS DISTINCT FROM OLD.domain_namespace OR NEW.code IS DISTINCT FROM OLD.code
       OR NEW.role_type IS DISTINCT FROM OLD.role_type) THEN
      RAISE EXCEPTION 'Role identity is immutable' USING ERRCODE = '23514';
    END IF;
    END IF;
    IF TG_TABLE_NAME = 'auth_role_assignment' THEN
      IF
      (NEW.user_id IS DISTINCT FROM OLD.user_id OR NEW.role_id IS DISTINCT FROM OLD.role_id
       OR NEW.domain_namespace IS DISTINCT FROM OLD.domain_namespace
       OR NEW.scope_type IS DISTINCT FROM OLD.scope_type OR NEW.scope_ref IS DISTINCT FROM OLD.scope_ref
       OR NEW.valid_from IS DISTINCT FROM OLD.valid_from) THEN
      RAISE EXCEPTION 'Revoke assignment before changing its actor, role or scope' USING ERRCODE = '23514';
    END IF;
    END IF;
    IF NEW.version NOT IN (OLD.version, OLD.version + 1) THEN
      RAISE EXCEPTION 'Invalid authorization version' USING ERRCODE = '23514';
    END IF;
    NEW.version := OLD.version + 1;
    NEW.updated_at := clock_timestamp();
  END IF;
  RETURN NEW;
END $$;
--> statement-breakpoint
CREATE TRIGGER auth_external_identity_guard BEFORE UPDATE ON auth_external_identity
FOR EACH ROW EXECUTE FUNCTION auth_p0_identity_guard();
--> statement-breakpoint
CREATE TRIGGER auth_role_identity_guard BEFORE UPDATE ON auth_role
FOR EACH ROW EXECUTE FUNCTION auth_p0_identity_guard();
--> statement-breakpoint
CREATE TRIGGER auth_role_assignment_identity_guard BEFORE UPDATE ON auth_role_assignment
FOR EACH ROW EXECUTE FUNCTION auth_p0_identity_guard();
--> statement-breakpoint
CREATE FUNCTION auth_p0_assignment_guard() RETURNS trigger LANGUAGE plpgsql AS $$
DECLARE r auth_role%ROWTYPE;
BEGIN
  SELECT * INTO r FROM auth_role WHERE id = NEW.role_id FOR SHARE;
  IF NOT FOUND OR (r.tenant_id IS NOT NULL AND r.tenant_id <> NEW.tenant_id)
     OR r.domain_namespace <> NEW.domain_namespace THEN
    RAISE EXCEPTION 'Role must belong to the assignment tenant and namespace' USING ERRCODE = '23514';
  END IF;
  IF NEW.status = 'ACTIVE' AND r.status <> 'ACTIVE' THEN
    RAISE EXCEPTION 'Cannot activate an assignment to an inactive role' USING ERRCODE = '23514';
  END IF;
  IF NEW.scope_type = 'TENANT' AND NEW.scope_ref <> NEW.tenant_id::text THEN
    RAISE EXCEPTION 'Tenant scope must reference the assignment tenant' USING ERRCODE = '23514';
  END IF;
  RETURN NEW;
END $$;
--> statement-breakpoint
CREATE TRIGGER auth_role_assignment_scope_guard BEFORE INSERT OR UPDATE ON auth_role_assignment
FOR EACH ROW EXECUTE FUNCTION auth_p0_assignment_guard();

--> statement-breakpoint
INSERT INTO auth_permission(domain_namespace,code,resource,action,risk_level,description) VALUES ('PLATFORM','assistant.use','assistant','use','LOW','assistant.use');
--> statement-breakpoint
INSERT INTO auth_permission(domain_namespace,code,resource,action,risk_level,description) VALUES ('PLATFORM','platform.agent.create','platform.agent','create','LOW','platform.agent.create');
--> statement-breakpoint
INSERT INTO auth_permission(domain_namespace,code,resource,action,risk_level,description) VALUES ('PLATFORM','platform.agent.deploy','platform.agent','deploy','HIGH','platform.agent.deploy');
--> statement-breakpoint
INSERT INTO auth_permission(domain_namespace,code,resource,action,risk_level,description) VALUES ('PLATFORM','platform.agent.edit','platform.agent','edit','LOW','platform.agent.edit');
--> statement-breakpoint
INSERT INTO auth_permission(domain_namespace,code,resource,action,risk_level,description) VALUES ('PLATFORM','platform.agent.publish','platform.agent','publish','HIGH','platform.agent.publish');
--> statement-breakpoint
INSERT INTO auth_permission(domain_namespace,code,resource,action,risk_level,description) VALUES ('PLATFORM','platform.agent.read','platform.agent','read','LOW','platform.agent.read');
--> statement-breakpoint
INSERT INTO auth_permission(domain_namespace,code,resource,action,risk_level,description) VALUES ('PLATFORM','platform.authorization.manage','platform.authorization','manage','HIGH','platform.authorization.manage');
--> statement-breakpoint
INSERT INTO auth_permission(domain_namespace,code,resource,action,risk_level,description) VALUES ('PLATFORM','platform.capability.manage','platform.capability','manage','HIGH','platform.capability.manage');
--> statement-breakpoint
INSERT INTO auth_permission(domain_namespace,code,resource,action,risk_level,description) VALUES ('PLATFORM','platform.capability.read','platform.capability','read','LOW','platform.capability.read');
--> statement-breakpoint
INSERT INTO auth_permission(domain_namespace,code,resource,action,risk_level,description) VALUES ('PLATFORM','platform.domain.manage','platform.domain','manage','HIGH','platform.domain.manage');
--> statement-breakpoint
INSERT INTO auth_permission(domain_namespace,code,resource,action,risk_level,description) VALUES ('PLATFORM','platform.eval.read','platform.eval','read','LOW','platform.eval.read');
--> statement-breakpoint
INSERT INTO auth_permission(domain_namespace,code,resource,action,risk_level,description) VALUES ('PLATFORM','platform.eval.review','platform.eval','review','LOW','platform.eval.review');
--> statement-breakpoint
INSERT INTO auth_permission(domain_namespace,code,resource,action,risk_level,description) VALUES ('PLATFORM','platform.eval.run','platform.eval','run','LOW','platform.eval.run');
--> statement-breakpoint
INSERT INTO auth_permission(domain_namespace,code,resource,action,risk_level,description) VALUES ('PLATFORM','platform.security.review','platform.security','review','LOW','platform.security.review');
--> statement-breakpoint
INSERT INTO auth_permission(domain_namespace,code,resource,action,risk_level,description) VALUES ('VINHOMES','vh.approval.decide.operational','vh.approval.decide','operational','LOW','vh.approval.decide.operational');
--> statement-breakpoint
INSERT INTO auth_permission(domain_namespace,code,resource,action,risk_level,description) VALUES ('VINHOMES','vh.audit.read','vh.audit','read','LOW','vh.audit.read');
--> statement-breakpoint
INSERT INTO auth_permission(domain_namespace,code,resource,action,risk_level,description) VALUES ('VINHOMES','vh.booking.create','vh.booking','create','LOW','vh.booking.create');
--> statement-breakpoint
INSERT INTO auth_permission(domain_namespace,code,resource,action,risk_level,description) VALUES ('VINHOMES','vh.evidence.upload','vh.evidence','upload','LOW','vh.evidence.upload');
--> statement-breakpoint
INSERT INTO auth_permission(domain_namespace,code,resource,action,risk_level,description) VALUES ('VINHOMES','vh.incident.assign','vh.incident','assign','LOW','vh.incident.assign');
--> statement-breakpoint
INSERT INTO auth_permission(domain_namespace,code,resource,action,risk_level,description) VALUES ('VINHOMES','vh.incident.create','vh.incident','create','LOW','vh.incident.create');
--> statement-breakpoint
INSERT INTO auth_permission(domain_namespace,code,resource,action,risk_level,description) VALUES ('VINHOMES','vh.incident.read','vh.incident','read','LOW','vh.incident.read');
--> statement-breakpoint
INSERT INTO auth_permission(domain_namespace,code,resource,action,risk_level,description) VALUES ('VINHOMES','vh.incident.read_own','vh.incident','read_own','LOW','vh.incident.read_own');
--> statement-breakpoint
INSERT INTO auth_permission(domain_namespace,code,resource,action,risk_level,description) VALUES ('VINHOMES','vh.incident.update','vh.incident','update','LOW','vh.incident.update');
--> statement-breakpoint
INSERT INTO auth_permission(domain_namespace,code,resource,action,risk_level,description) VALUES ('VINHOMES','vh.invoice.read','vh.invoice','read','LOW','vh.invoice.read');
--> statement-breakpoint
INSERT INTO auth_permission(domain_namespace,code,resource,action,risk_level,description) VALUES ('VINHOMES','vh.invoice.read_own','vh.invoice','read_own','LOW','vh.invoice.read_own');
--> statement-breakpoint
INSERT INTO auth_permission(domain_namespace,code,resource,action,risk_level,description) VALUES ('VINHOMES','vh.payment.reconcile','vh.payment','reconcile','HIGH','vh.payment.reconcile');
--> statement-breakpoint
INSERT INTO auth_permission(domain_namespace,code,resource,action,risk_level,description) VALUES ('VINHOMES','vh.profile.read','vh.profile','read','LOW','vh.profile.read');
--> statement-breakpoint
INSERT INTO auth_permission(domain_namespace,code,resource,action,risk_level,description) VALUES ('VINHOMES','vh.qc.review','vh.qc','review','LOW','vh.qc.review');
--> statement-breakpoint
INSERT INTO auth_permission(domain_namespace,code,resource,action,risk_level,description) VALUES ('VINHOMES','vh.task.assign','vh.task','assign','LOW','vh.task.assign');
--> statement-breakpoint
INSERT INTO auth_permission(domain_namespace,code,resource,action,risk_level,description) VALUES ('VINHOMES','vh.task.create','vh.task','create','LOW','vh.task.create');
--> statement-breakpoint
INSERT INTO auth_permission(domain_namespace,code,resource,action,risk_level,description) VALUES ('VINHOMES','vh.task.read_assigned','vh.task','read_assigned','LOW','vh.task.read_assigned');
--> statement-breakpoint
INSERT INTO auth_permission(domain_namespace,code,resource,action,risk_level,description) VALUES ('VINHOMES','vh.workorder.execute','vh.workorder','execute','HIGH','vh.workorder.execute');
--> statement-breakpoint
INSERT INTO auth_role(domain_namespace,code,name,role_type,status) VALUES ('VINHOMES','VH_RESIDENT','VH_RESIDENT','SYSTEM','ACTIVE');
--> statement-breakpoint
INSERT INTO auth_role_permission(role_id,permission_id) SELECT r.id,p.id FROM auth_role r CROSS JOIN auth_permission p WHERE r.tenant_id IS NULL AND r.code='VH_RESIDENT' AND r.domain_namespace='VINHOMES' AND p.code IN ('assistant.use','vh.profile.read','vh.incident.create','vh.incident.read_own','vh.booking.create','vh.invoice.read_own');
--> statement-breakpoint
INSERT INTO auth_role(domain_namespace,code,name,role_type,status) VALUES ('VINHOMES','VH_BQL_MANAGER','VH_BQL_MANAGER','SYSTEM','ACTIVE');
--> statement-breakpoint
INSERT INTO auth_role_permission(role_id,permission_id) SELECT r.id,p.id FROM auth_role r CROSS JOIN auth_permission p WHERE r.tenant_id IS NULL AND r.code='VH_BQL_MANAGER' AND r.domain_namespace='VINHOMES' AND p.code IN ('vh.incident.read','vh.incident.update','vh.incident.assign','vh.task.create','vh.task.assign','vh.approval.decide.operational','vh.qc.review','vh.audit.read');
--> statement-breakpoint
INSERT INTO auth_role(domain_namespace,code,name,role_type,status) VALUES ('VINHOMES','VH_BQL_OPERATOR','VH_BQL_OPERATOR','SYSTEM','ACTIVE');
--> statement-breakpoint
INSERT INTO auth_role_permission(role_id,permission_id) SELECT r.id,p.id FROM auth_role r CROSS JOIN auth_permission p WHERE r.tenant_id IS NULL AND r.code='VH_BQL_OPERATOR' AND r.domain_namespace='VINHOMES' AND p.code IN ('vh.incident.read','vh.incident.update','vh.task.create','vh.task.assign');
--> statement-breakpoint
INSERT INTO auth_role(domain_namespace,code,name,role_type,status) VALUES ('VINHOMES','VH_TECHNICIAN','VH_TECHNICIAN','SYSTEM','ACTIVE');
--> statement-breakpoint
INSERT INTO auth_role_permission(role_id,permission_id) SELECT r.id,p.id FROM auth_role r CROSS JOIN auth_permission p WHERE r.tenant_id IS NULL AND r.code='VH_TECHNICIAN' AND r.domain_namespace='VINHOMES' AND p.code IN ('vh.task.read_assigned','vh.workorder.execute','vh.evidence.upload');
--> statement-breakpoint
INSERT INTO auth_role(domain_namespace,code,name,role_type,status) VALUES ('VINHOMES','VH_CLEANING_STAFF','VH_CLEANING_STAFF','SYSTEM','ACTIVE');
--> statement-breakpoint
INSERT INTO auth_role_permission(role_id,permission_id) SELECT r.id,p.id FROM auth_role r CROSS JOIN auth_permission p WHERE r.tenant_id IS NULL AND r.code='VH_CLEANING_STAFF' AND r.domain_namespace='VINHOMES' AND p.code IN ('vh.task.read_assigned','vh.workorder.execute','vh.evidence.upload');
--> statement-breakpoint
INSERT INTO auth_role(domain_namespace,code,name,role_type,status) VALUES ('VINHOMES','VH_SECURITY_STAFF','VH_SECURITY_STAFF','SYSTEM','ACTIVE');
--> statement-breakpoint
INSERT INTO auth_role_permission(role_id,permission_id) SELECT r.id,p.id FROM auth_role r CROSS JOIN auth_permission p WHERE r.tenant_id IS NULL AND r.code='VH_SECURITY_STAFF' AND r.domain_namespace='VINHOMES' AND p.code IN ('vh.task.read_assigned','vh.workorder.execute','vh.evidence.upload');
--> statement-breakpoint
INSERT INTO auth_role(domain_namespace,code,name,role_type,status) VALUES ('VINHOMES','VH_FINANCE_STAFF','VH_FINANCE_STAFF','SYSTEM','ACTIVE');
--> statement-breakpoint
INSERT INTO auth_role_permission(role_id,permission_id) SELECT r.id,p.id FROM auth_role r CROSS JOIN auth_permission p WHERE r.tenant_id IS NULL AND r.code='VH_FINANCE_STAFF' AND r.domain_namespace='VINHOMES' AND p.code IN ('vh.invoice.read','vh.payment.reconcile');
--> statement-breakpoint
INSERT INTO auth_role(domain_namespace,code,name,role_type,status) VALUES ('PLATFORM','AGENT_BUILDER','AGENT_BUILDER','SYSTEM','ACTIVE');
--> statement-breakpoint
INSERT INTO auth_role_permission(role_id,permission_id) SELECT r.id,p.id FROM auth_role r CROSS JOIN auth_permission p WHERE r.tenant_id IS NULL AND r.code='AGENT_BUILDER' AND r.domain_namespace='PLATFORM' AND p.code IN ('platform.agent.read','platform.agent.create','platform.agent.edit','platform.capability.read');
--> statement-breakpoint
INSERT INTO auth_role(domain_namespace,code,name,role_type,status) VALUES ('PLATFORM','AGENT_MANAGER','AGENT_MANAGER','SYSTEM','ACTIVE');
--> statement-breakpoint
INSERT INTO auth_role_permission(role_id,permission_id) SELECT r.id,p.id FROM auth_role r CROSS JOIN auth_permission p WHERE r.tenant_id IS NULL AND r.code='AGENT_MANAGER' AND r.domain_namespace='PLATFORM' AND p.code IN ('platform.agent.read','platform.agent.create','platform.agent.edit','platform.capability.read','platform.eval.read','platform.eval.run');
--> statement-breakpoint
INSERT INTO auth_role(domain_namespace,code,name,role_type,status) VALUES ('PLATFORM','AGENT_PUBLISHER','AGENT_PUBLISHER','SYSTEM','ACTIVE');
--> statement-breakpoint
INSERT INTO auth_role_permission(role_id,permission_id) SELECT r.id,p.id FROM auth_role r CROSS JOIN auth_permission p WHERE r.tenant_id IS NULL AND r.code='AGENT_PUBLISHER' AND r.domain_namespace='PLATFORM' AND p.code IN ('platform.agent.read','platform.agent.publish','platform.agent.deploy');
--> statement-breakpoint
INSERT INTO auth_role(domain_namespace,code,name,role_type,status) VALUES ('PLATFORM','EVALUATION_REVIEWER','EVALUATION_REVIEWER','SYSTEM','ACTIVE');
--> statement-breakpoint
INSERT INTO auth_role_permission(role_id,permission_id) SELECT r.id,p.id FROM auth_role r CROSS JOIN auth_permission p WHERE r.tenant_id IS NULL AND r.code='EVALUATION_REVIEWER' AND r.domain_namespace='PLATFORM' AND p.code IN ('platform.agent.read','platform.eval.read','platform.eval.review');
--> statement-breakpoint
INSERT INTO auth_role(domain_namespace,code,name,role_type,status) VALUES ('PLATFORM','SECURITY_REVIEWER','SECURITY_REVIEWER','SYSTEM','ACTIVE');
--> statement-breakpoint
INSERT INTO auth_role_permission(role_id,permission_id) SELECT r.id,p.id FROM auth_role r CROSS JOIN auth_permission p WHERE r.tenant_id IS NULL AND r.code='SECURITY_REVIEWER' AND r.domain_namespace='PLATFORM' AND p.code IN ('platform.agent.read','platform.security.review');
--> statement-breakpoint
INSERT INTO auth_role(domain_namespace,code,name,role_type,status) VALUES ('PLATFORM','PLATFORM_ADMIN','PLATFORM_ADMIN','SYSTEM','ACTIVE');
--> statement-breakpoint
INSERT INTO auth_role_permission(role_id,permission_id) SELECT r.id,p.id FROM auth_role r CROSS JOIN auth_permission p WHERE r.tenant_id IS NULL AND r.code='PLATFORM_ADMIN' AND r.domain_namespace='PLATFORM' AND p.code IN ('platform.authorization.manage','platform.domain.manage','platform.capability.manage');
