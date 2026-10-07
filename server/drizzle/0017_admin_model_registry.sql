-- Registered provider models and tenant role defaults. Credentials remain environment references.
CREATE TABLE admin_model_registry (
 id uuid PRIMARY KEY DEFAULT gen_random_uuid(), tenant_id uuid NOT NULL REFERENCES tenants(id),
 name text NOT NULL CHECK(length(name) BETWEEN 1 AND 120), provider text NOT NULL,
 kind text NOT NULL CHECK(kind IN ('chat','embedding')), credential_env text NOT NULL,
 base_url_env text, allowed boolean NOT NULL DEFAULT false, dimension integer,
 check_status text NOT NULL DEFAULT 'unchecked' CHECK(check_status IN ('unchecked','ok','error')),
 latency_ms integer, checked_at timestamptz, created_at timestamptz NOT NULL DEFAULT now(),
 created_by text NOT NULL REFERENCES users(id), UNIQUE(tenant_id,id), UNIQUE(tenant_id,provider,name,kind)
);
--> statement-breakpoint
CREATE TABLE admin_role_models (
 tenant_id uuid NOT NULL REFERENCES tenants(id), role text NOT NULL CHECK(role IN ('reception','supervisor','specialist','factory','embedding')),
 model_id uuid NOT NULL, updated_at timestamptz NOT NULL DEFAULT now(), updated_by text NOT NULL REFERENCES users(id),
 PRIMARY KEY(tenant_id,role), FOREIGN KEY(tenant_id,model_id) REFERENCES admin_model_registry(tenant_id,id)
);
--> statement-breakpoint
ALTER TABLE admin_model_registry ENABLE ROW LEVEL SECURITY;
--> statement-breakpoint
ALTER TABLE admin_model_registry FORCE ROW LEVEL SECURITY;
--> statement-breakpoint
CREATE POLICY admin_model_registry_tenant ON admin_model_registry USING(tenant_id=nullif(current_setting('app.tenant_id',true),'')::uuid) WITH CHECK(tenant_id=nullif(current_setting('app.tenant_id',true),'')::uuid);
--> statement-breakpoint
ALTER TABLE admin_role_models ENABLE ROW LEVEL SECURITY;
--> statement-breakpoint
ALTER TABLE admin_role_models FORCE ROW LEVEL SECURITY;
--> statement-breakpoint
CREATE POLICY admin_role_models_tenant ON admin_role_models USING(tenant_id=nullif(current_setting('app.tenant_id',true),'')::uuid) WITH CHECK(tenant_id=nullif(current_setting('app.tenant_id',true),'')::uuid);
--> statement-breakpoint
DO $$ BEGIN IF EXISTS(SELECT 1 FROM pg_roles WHERE rolname='vinhomes_v3_api') THEN GRANT SELECT,INSERT,UPDATE,DELETE ON admin_model_registry,admin_role_models TO vinhomes_v3_api; END IF; END $$;
