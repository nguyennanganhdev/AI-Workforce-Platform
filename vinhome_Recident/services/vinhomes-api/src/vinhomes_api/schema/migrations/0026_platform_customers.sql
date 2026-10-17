-- Platform-first customer linking. Every table remains tenant/RLS scoped.
CREATE TABLE platform_customer_clients (
    tenant_id uuid NOT NULL REFERENCES tenants(id),
    client_id text NOT NULL,
    secret_hash text NOT NULL,
    redirect_uri text NOT NULL,
    issuer text NOT NULL,
    active boolean NOT NULL DEFAULT false,
    PRIMARY KEY (tenant_id,client_id)
);
CREATE TABLE platform_customer_codes (
    id uuid PRIMARY KEY,
    tenant_id uuid NOT NULL REFERENCES tenants(id),
    client_id text NOT NULL,
    user_id text NOT NULL REFERENCES users(id),
    platform_user_id text NOT NULL,
    state text NOT NULL,
    challenge text NOT NULL,
    redirect_uri text NOT NULL,
    csrf_hash text NOT NULL,
    code_hash text UNIQUE,
    expires_at timestamptz NOT NULL,
    used_at timestamptz,
    FOREIGN KEY (tenant_id,client_id) REFERENCES platform_customer_clients(tenant_id,client_id)
);
CREATE TABLE platform_customer_links (
    id uuid PRIMARY KEY,
    tenant_id uuid NOT NULL REFERENCES tenants(id),
    client_id text NOT NULL,
    user_id text NOT NULL REFERENCES users(id),
    platform_user_id text NOT NULL,
    token_hash text NOT NULL UNIQUE,
    scopes text[] NOT NULL,
    active boolean NOT NULL DEFAULT true,
    expires_at timestamptz NOT NULL,
    UNIQUE(tenant_id,client_id,user_id),
    FOREIGN KEY (tenant_id,client_id) REFERENCES platform_customer_clients(tenant_id,client_id)
);
CREATE TABLE platform_customer_grants (
    id uuid PRIMARY KEY,
    tenant_id uuid NOT NULL REFERENCES tenants(id),
    link_id uuid NOT NULL REFERENCES platform_customer_links(id),
    token_hash text NOT NULL UNIQUE,
    expires_at timestamptz NOT NULL,
    calls integer NOT NULL DEFAULT 0 CHECK(calls>=0 AND calls<=120)
);
CREATE TABLE platform_customer_cases (
    tenant_id uuid NOT NULL REFERENCES tenants(id),
    client_id text NOT NULL,
    platform_case_id text NOT NULL,
    platform_workflow_id text NOT NULL,
    case_id uuid NOT NULL REFERENCES vh_resident_cases(id),
    user_id text NOT NULL REFERENCES users(id),
    link_id uuid NOT NULL REFERENCES platform_customer_links(id),
    PRIMARY KEY (tenant_id,client_id,platform_case_id),
    UNIQUE(tenant_id,client_id,case_id),
    FOREIGN KEY (tenant_id,client_id) REFERENCES platform_customer_clients(tenant_id,client_id)
);
CREATE INDEX platform_customer_codes_expiry ON platform_customer_codes(tenant_id,expires_at);
CREATE INDEX platform_customer_grants_link ON platform_customer_grants(tenant_id,link_id);
DO $$
DECLARE tab text;
BEGIN
    FOREACH tab IN ARRAY ARRAY['platform_customer_clients','platform_customer_codes',
      'platform_customer_links','platform_customer_grants','platform_customer_cases'] LOOP
        EXECUTE format('ALTER TABLE %I ENABLE ROW LEVEL SECURITY',tab);
        EXECUTE format('ALTER TABLE %I FORCE ROW LEVEL SECURITY',tab);
        EXECUTE format('CREATE POLICY customer_tenant ON %I USING (tenant_id=nullif(current_setting(''app.tenant_id'',true),'''')::uuid) WITH CHECK (tenant_id=nullif(current_setting(''app.tenant_id'',true),'''')::uuid)',tab);
    END LOOP;
END $$;
