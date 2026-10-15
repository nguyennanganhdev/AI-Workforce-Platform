-- Runtime configuration is tenant-scoped. The encryption key stays outside PostgreSQL.
CREATE TABLE public.platform_connection_settings (
    tenant_id uuid PRIMARY KEY REFERENCES public.tenants(id),
    version integer NOT NULL DEFAULT 1 CHECK (version > 0),
    enabled boolean NOT NULL DEFAULT false,
    url text NOT NULL DEFAULT '',
    credentials_ciphertext text NOT NULL,
    routes jsonb NOT NULL DEFAULT '{}',
    last_check jsonb,
    updated_by text NOT NULL REFERENCES public.users(id),
    updated_at timestamptz NOT NULL DEFAULT now(),
    worker_seen_at timestamptz,
    worker_version integer
);
ALTER TABLE public.platform_connection_settings ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.platform_connection_settings FORCE ROW LEVEL SECURITY;
CREATE POLICY platform_connection_tenant ON public.platform_connection_settings
    USING (tenant_id=nullif(current_setting('app.tenant_id',true),'')::uuid)
    WITH CHECK (tenant_id=nullif(current_setting('app.tenant_id',true),'')::uuid);
