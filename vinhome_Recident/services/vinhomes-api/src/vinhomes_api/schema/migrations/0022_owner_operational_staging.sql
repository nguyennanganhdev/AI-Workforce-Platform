-- Private owner handoff staging. Validation/staging never activates people, routes or service policies.
CREATE TABLE public.owner_operational_batches (
    id uuid PRIMARY KEY,
    tenant_id uuid NOT NULL REFERENCES public.tenants(id),
    bundle_code text NOT NULL,
    version text NOT NULL,
    snapshot_sha256 text NOT NULL,
    manifest jsonb NOT NULL,
    counts jsonb NOT NULL,
    staged_by text NOT NULL REFERENCES public.users(id),
    status text NOT NULL DEFAULT 'staged' CHECK (status='staged'),
    created_at timestamptz NOT NULL DEFAULT now(),
    UNIQUE (tenant_id,id),
    UNIQUE (tenant_id,bundle_code,version)
);
CREATE TABLE public.owner_operational_records (
    tenant_id uuid NOT NULL REFERENCES public.tenants(id),
    batch_id uuid NOT NULL,
    dataset text NOT NULL CHECK (dataset IN ('operators','zones','buildings','units','coverage','residents','staff','shifts','services','sops')),
    ordinal integer NOT NULL CHECK (ordinal>0),
    data jsonb NOT NULL,
    PRIMARY KEY (tenant_id,batch_id,dataset,ordinal),
    FOREIGN KEY (tenant_id,batch_id) REFERENCES public.owner_operational_batches(tenant_id,id) ON DELETE CASCADE
);
DO $$ DECLARE tab text; BEGIN
    FOREACH tab IN ARRAY ARRAY['owner_operational_batches','owner_operational_records'] LOOP
        EXECUTE format('ALTER TABLE public.%I ENABLE ROW LEVEL SECURITY',tab);
        EXECUTE format('ALTER TABLE public.%I FORCE ROW LEVEL SECURITY',tab);
        EXECUTE format('CREATE POLICY tenant_policy ON public.%I USING (tenant_id=nullif(current_setting(''app.tenant_id'',true),'''')::uuid) WITH CHECK (tenant_id=nullif(current_setting(''app.tenant_id'',true),'''')::uuid)',tab);
    END LOOP;
END $$;
