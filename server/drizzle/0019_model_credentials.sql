-- A model's API key may be entered in the app and kept sealed (AES-GCM, key held by the API's deployment),
-- instead of naming an environment variable. A unit's own model (workspace_id) serves only that unit's agents.
ALTER TABLE admin_model_registry ALTER COLUMN credential_env DROP NOT NULL;
--> statement-breakpoint
ALTER TABLE admin_model_registry ADD COLUMN credential_sealed text, ADD COLUMN credential_hint text, ADD COLUMN workspace_id uuid;
--> statement-breakpoint
ALTER TABLE admin_model_registry ADD CONSTRAINT admin_model_registry_one_credential CHECK ((credential_env IS NULL) <> (credential_sealed IS NULL));
--> statement-breakpoint
ALTER TABLE admin_model_registry ADD CONSTRAINT admin_model_registry_unit_sealed CHECK (workspace_id IS NULL OR (credential_sealed IS NOT NULL AND kind = 'chat'));
--> statement-breakpoint
ALTER TABLE admin_model_registry ADD CONSTRAINT admin_model_registry_workspace_fkey FOREIGN KEY (tenant_id, workspace_id) REFERENCES workspaces(tenant_id, id);
--> statement-breakpoint
ALTER TABLE admin_model_registry DROP CONSTRAINT admin_model_registry_tenant_id_provider_name_kind_key;
--> statement-breakpoint
CREATE UNIQUE INDEX admin_model_registry_scope_name ON admin_model_registry (tenant_id, coalesce(workspace_id, '00000000-0000-0000-0000-000000000000'::uuid), provider, name, kind);
--> statement-breakpoint
DO $$ BEGIN IF EXISTS(SELECT 1 FROM pg_roles WHERE rolname='vinhomes_v3_api') THEN GRANT DELETE ON admin_model_registry TO vinhomes_v3_api; END IF; END $$;
