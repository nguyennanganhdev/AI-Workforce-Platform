-- Platform-first customer linking. Every table remains tenant/RLS scoped.
ALTER TABLE platform_links ADD COLUMN origin text NOT NULL DEFAULT 'domain' CHECK(origin IN ('domain','platform'));
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
    revision integer NOT NULL DEFAULT 1,
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
CREATE TABLE platform_customer_projection_acks (
    tenant_id uuid NOT NULL REFERENCES tenants(id),
    case_id uuid NOT NULL REFERENCES vh_resident_cases(id),
    link_id uuid NOT NULL REFERENCES platform_customer_links(id),
    link_revision integer NOT NULL,
    canonical_version bigint NOT NULL,
    content_hash text NOT NULL,
    applied_at timestamptz NOT NULL DEFAULT now(),
    PRIMARY KEY(tenant_id,case_id,link_id,link_revision,canonical_version)
);
ALTER TABLE platform_mcp_grants ADD COLUMN customer_link_id uuid REFERENCES platform_customer_links(id);
ALTER TABLE platform_mcp_grants ADD COLUMN customer_link_revision integer;
-- Durable per-case order also covers manual staff events and pre-ticket cases.
ALTER TABLE vh_resident_cases ADD COLUMN event_sequence bigint NOT NULL DEFAULT 0;
ALTER TABLE vh_resident_public_events ADD COLUMN sequence bigint;
ALTER TABLE vh_resident_public_events ADD COLUMN canonical_version bigint NOT NULL DEFAULT 1;
WITH numbered AS (
  SELECT id,row_number() OVER(PARTITION BY tenant_id,case_id ORDER BY occurred_at,id) AS seq
  FROM vh_resident_public_events
) UPDATE vh_resident_public_events e SET sequence=n.seq FROM numbered n WHERE n.id=e.id;
UPDATE vh_resident_cases c SET event_sequence=coalesce((SELECT max(sequence) FROM vh_resident_public_events e WHERE e.case_id=c.id AND e.tenant_id=c.tenant_id),0);
ALTER TABLE vh_resident_public_events ALTER COLUMN sequence SET NOT NULL;
CREATE UNIQUE INDEX vh_resident_public_events_sequence ON vh_resident_public_events(tenant_id,case_id,sequence);
CREATE FUNCTION customer_case_event_sequence() RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN
  UPDATE vh_resident_cases SET event_sequence=event_sequence+1 WHERE id=NEW.case_id AND tenant_id=NEW.tenant_id RETURNING event_sequence INTO NEW.sequence;
  SELECT c.version+coalesce(sum(t.version),0) INTO NEW.canonical_version FROM vh_resident_cases c
    LEFT JOIN vh_resident_case_tickets ct ON ct.case_id=c.id AND ct.tenant_id=c.tenant_id
    LEFT JOIN tickets t ON t.id=ct.ticket_id AND t.tenant_id=ct.tenant_id
    WHERE c.id=NEW.case_id AND c.tenant_id=NEW.tenant_id GROUP BY c.id;
  RETURN NEW;
END $$;
CREATE TRIGGER customer_case_sequence BEFORE INSERT ON vh_resident_public_events FOR EACH ROW EXECUTE FUNCTION customer_case_event_sequence();
DO $$
DECLARE tab text;
BEGIN
    FOREACH tab IN ARRAY ARRAY['platform_customer_clients','platform_customer_codes',
      'platform_customer_links','platform_customer_grants','platform_customer_cases','platform_customer_projection_acks'] LOOP
        EXECUTE format('ALTER TABLE %I ENABLE ROW LEVEL SECURITY',tab);
        EXECUTE format('ALTER TABLE %I FORCE ROW LEVEL SECURITY',tab);
        EXECUTE format('CREATE POLICY customer_tenant ON %I USING (tenant_id=nullif(current_setting(''app.tenant_id'',true),'''')::uuid) WITH CHECK (tenant_id=nullif(current_setting(''app.tenant_id'',true),'''')::uuid)',tab);
    END LOOP;
END $$;
