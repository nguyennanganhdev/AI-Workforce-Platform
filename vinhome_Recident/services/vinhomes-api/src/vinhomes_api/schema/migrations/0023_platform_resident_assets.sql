-- Durable customer-image references. Presigned URLs and credentials are never stored here.
CREATE TABLE public.platform_resident_assets (
    tenant_id uuid NOT NULL REFERENCES public.tenants(id),
    ticket_id uuid NOT NULL,
    file_id uuid NOT NULL,
    destination_hash text NOT NULL,
    source_sha256 text NOT NULL,
    asset_id text NOT NULL,
    created_at timestamptz NOT NULL DEFAULT now(),
    PRIMARY KEY (tenant_id,ticket_id,file_id,destination_hash),
    FOREIGN KEY (tenant_id,ticket_id) REFERENCES public.tickets(tenant_id,id),
    FOREIGN KEY (tenant_id,file_id) REFERENCES public.files(tenant_id,id)
);
ALTER TABLE public.platform_resident_assets ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.platform_resident_assets FORCE ROW LEVEL SECURITY;
CREATE POLICY tenant_policy ON public.platform_resident_assets
    USING (tenant_id=nullif(current_setting('app.tenant_id',true),'')::uuid)
    WITH CHECK (tenant_id=nullif(current_setting('app.tenant_id',true),'')::uuid);
