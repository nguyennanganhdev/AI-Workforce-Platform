-- Project approval does not invent missing operational facts. Mock travel stays in separate tables.
ALTER TABLE public.zones ADD COLUMN metadata jsonb NOT NULL DEFAULT '{}';
ALTER TABLE public.buildings ADD COLUMN metadata jsonb NOT NULL DEFAULT '{}';
ALTER TABLE public.management_units ADD COLUMN metadata jsonb NOT NULL DEFAULT '{}';

CREATE TABLE public.owner_data_records (
    id uuid PRIMARY KEY,
    tenant_id uuid NOT NULL REFERENCES public.tenants(id),
    site_id uuid NOT NULL,
    dataset text NOT NULL CHECK (dataset IN ('geography','services','staffing_requirements','data_requests')),
    proposal_code text NOT NULL,
    title text NOT NULL,
    source_hash text NOT NULL,
    proposal jsonb NOT NULL,
    project_approval jsonb NOT NULL,
    operational_verified boolean NOT NULL DEFAULT false,
    created_at timestamptz NOT NULL DEFAULT now(),
    UNIQUE (tenant_id,id),
    UNIQUE (tenant_id,site_id,dataset,proposal_code),
    FOREIGN KEY (tenant_id,site_id) REFERENCES public.sites(tenant_id,id)
);
CREATE TABLE public.domain_service_catalog (
    id uuid PRIMARY KEY,
    tenant_id uuid NOT NULL REFERENCES public.tenants(id),
    site_id uuid NOT NULL,
    title text NOT NULL,
    category_code text,
    policy jsonb NOT NULL,
    operational_enabled boolean NOT NULL DEFAULT false,
    FOREIGN KEY (tenant_id,id) REFERENCES public.owner_data_records(tenant_id,id),
    FOREIGN KEY (tenant_id,site_id) REFERENCES public.sites(tenant_id,id)
);
CREATE TABLE public.travel_mock_catalog (
    tenant_id uuid NOT NULL REFERENCES public.tenants(id),
    kind text NOT NULL CHECK (kind IN ('hotel','bus','restaurant')),
    service_id text NOT NULL,
    provider_mode text NOT NULL DEFAULT 'mock' CHECK (provider_mode='mock'),
    data jsonb NOT NULL,
    source_hash text NOT NULL,
    PRIMARY KEY (tenant_id,kind,service_id)
);
CREATE TABLE public.travel_mock_intents (
    id uuid PRIMARY KEY,
    tenant_id uuid NOT NULL REFERENCES public.tenants(id),
    ticket_id uuid NOT NULL,
    client_reference text NOT NULL,
    request_hash text NOT NULL,
    kind text NOT NULL CHECK (kind IN ('hotel','bus','restaurant')),
    operation text NOT NULL CHECK (operation IN ('book','cancel')),
    selection jsonb NOT NULL,
    quote jsonb NOT NULL,
    arguments_hash text NOT NULL,
    provider_mode text NOT NULL DEFAULT 'mock' CHECK (provider_mode='mock'),
    expires_at timestamptz NOT NULL,
    commit_reference text,
    approval_id text,
    result jsonb,
    created_at timestamptz NOT NULL DEFAULT now(),
    UNIQUE (tenant_id,id),
    UNIQUE (tenant_id,ticket_id,client_reference),
    FOREIGN KEY (tenant_id,ticket_id) REFERENCES public.tickets(tenant_id,id)
);
CREATE TABLE public.travel_mock_bookings (
    id uuid PRIMARY KEY,
    tenant_id uuid NOT NULL REFERENCES public.tenants(id),
    ticket_id uuid NOT NULL,
    intent_id uuid NOT NULL,
    kind text NOT NULL CHECK (kind IN ('hotel','bus','restaurant')),
    provider_booking_id text NOT NULL,
    provider_mode text NOT NULL DEFAULT 'mock' CHECK (provider_mode='mock'),
    status text NOT NULL CHECK (status IN ('confirmed','cancelled')),
    data jsonb NOT NULL,
    created_at timestamptz NOT NULL DEFAULT now(),
    updated_at timestamptz NOT NULL DEFAULT now(),
    UNIQUE (tenant_id,id),
    UNIQUE (tenant_id,intent_id),
    UNIQUE (tenant_id,kind,provider_booking_id),
    FOREIGN KEY (tenant_id,ticket_id) REFERENCES public.tickets(tenant_id,id),
    FOREIGN KEY (tenant_id,intent_id) REFERENCES public.travel_mock_intents(tenant_id,id)
);
CREATE INDEX travel_mock_bookings_ticket_idx ON public.travel_mock_bookings(tenant_id,ticket_id);
CREATE UNIQUE INDEX travel_mock_commit_reference_uq ON public.travel_mock_intents(tenant_id,ticket_id,commit_reference) WHERE commit_reference IS NOT NULL;

DO $$ DECLARE tab text; BEGIN
    FOREACH tab IN ARRAY ARRAY['owner_data_records','domain_service_catalog','travel_mock_catalog','travel_mock_intents','travel_mock_bookings'] LOOP
        EXECUTE format('ALTER TABLE public.%I ENABLE ROW LEVEL SECURITY',tab);
        EXECUTE format('ALTER TABLE public.%I FORCE ROW LEVEL SECURITY',tab);
        EXECUTE format('CREATE POLICY tenant_policy ON public.%I USING (tenant_id=nullif(current_setting(''app.tenant_id'',true),'''')::uuid) WITH CHECK (tenant_id=nullif(current_setting(''app.tenant_id'',true),'''')::uuid)',tab);
    END LOOP;
END $$;
