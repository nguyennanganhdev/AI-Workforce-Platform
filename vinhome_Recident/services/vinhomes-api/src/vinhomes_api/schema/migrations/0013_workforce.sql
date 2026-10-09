-- Workforce is opt-in. Business tickets and workflow tracking have separate lifecycles.
CREATE TABLE vh_workforce_bindings (
 id uuid PRIMARY KEY DEFAULT gen_random_uuid(), tenant_id uuid NOT NULL REFERENCES tenants(id),
 ticket_id uuid NOT NULL, generation integer NOT NULL CHECK(generation>=0),
 resident_id text NOT NULL, team_id uuid NOT NULL, channel_id text NOT NULL,
 management_ref text NOT NULL, residence_id text NOT NULL,
 external_ticket_id text NOT NULL, external_conversation_id text NOT NULL,
 workflow_id text, conversation_id text, cursor text, state text NOT NULL DEFAULT 'accepted',
 snapshot jsonb NOT NULL DEFAULT '{}', last_error text, next_poll timestamptz NOT NULL DEFAULT now(),
 created_at timestamptz NOT NULL DEFAULT now(), updated_at timestamptz NOT NULL DEFAULT now(),
 UNIQUE(tenant_id,id), UNIQUE(tenant_id,ticket_id,generation), UNIQUE(tenant_id,workflow_id),
 FOREIGN KEY(tenant_id,ticket_id) REFERENCES tickets(tenant_id,id),
 FOREIGN KEY(tenant_id,team_id) REFERENCES integration_cases(tenant_id,id),
 FOREIGN KEY(tenant_id,channel_id) REFERENCES channels(tenant_id,id)
);
CREATE TABLE vh_workforce_outbox (
 id uuid PRIMARY KEY DEFAULT gen_random_uuid(), tenant_id uuid NOT NULL REFERENCES tenants(id),
 binding_id uuid, kind text NOT NULL CHECK(kind IN ('request','approval','close','provider')),
 external_id text NOT NULL, payload_hash text NOT NULL, source jsonb NOT NULL DEFAULT '{}',
 body jsonb, endpoint text, status text NOT NULL DEFAULT 'queued', response jsonb,
 request_id text, receipt_id text, owner text, generation integer NOT NULL DEFAULT 0,
 lease_until timestamptz, attempts integer NOT NULL DEFAULT 0, available timestamptz NOT NULL DEFAULT now(),
 last_error text, created_at timestamptz NOT NULL DEFAULT now(),
 UNIQUE(tenant_id,external_id), FOREIGN KEY(tenant_id,binding_id) REFERENCES vh_workforce_bindings(tenant_id,id)
);
CREATE INDEX vh_workforce_outbox_claim ON vh_workforce_outbox(status,available,lease_until);
CREATE TABLE vh_workforce_deliveries (
 tenant_id uuid NOT NULL REFERENCES tenants(id), binding_id uuid NOT NULL, event_id text NOT NULL,
 event_sequence bigint NOT NULL, message_id uuid, payload jsonb NOT NULL,
 created_at timestamptz NOT NULL DEFAULT now(), PRIMARY KEY(tenant_id,event_id),
 FOREIGN KEY(tenant_id,binding_id) REFERENCES vh_workforce_bindings(tenant_id,id)
);
CREATE TABLE vh_workforce_assets (
 tenant_id uuid NOT NULL REFERENCES tenants(id), binding_id uuid NOT NULL, file_id uuid NOT NULL,
 asset_id text NOT NULL, PRIMARY KEY(tenant_id,binding_id,file_id),
 FOREIGN KEY(tenant_id,binding_id) REFERENCES vh_workforce_bindings(tenant_id,id),
 FOREIGN KEY(tenant_id,file_id) REFERENCES files(tenant_id,id)
);
CREATE TABLE vh_workforce_mcp_intents (
 tenant_id uuid NOT NULL REFERENCES tenants(id), client_reference text NOT NULL, workflow_id text NOT NULL,
 ticket_id uuid NOT NULL, tool text NOT NULL, arguments_hash text NOT NULL, response jsonb NOT NULL,
 created_at timestamptz NOT NULL DEFAULT now(), PRIMARY KEY(tenant_id,client_reference),
 FOREIGN KEY(tenant_id,ticket_id) REFERENCES tickets(tenant_id,id)
);
CREATE TABLE vh_workforce_provider_jobs (
 tenant_id uuid NOT NULL REFERENCES tenants(id), external_job_id text NOT NULL, client_reference text NOT NULL,
 ticket_id uuid NOT NULL, last_status text, provider_version integer NOT NULL DEFAULT 0,
 PRIMARY KEY(tenant_id,external_job_id), UNIQUE(tenant_id,client_reference),
 FOREIGN KEY(tenant_id,ticket_id) REFERENCES tickets(tenant_id,id)
);
CREATE TABLE vh_workforce_management_grants (
 tenant_id uuid NOT NULL REFERENCES tenants(id), management_unit_id uuid NOT NULL,
 service_actor text NOT NULL, tools text[] NOT NULL DEFAULT '{}', active boolean NOT NULL DEFAULT false,
 auto_categories uuid[] NOT NULL DEFAULT '{}', PRIMARY KEY(tenant_id,management_unit_id),
 FOREIGN KEY(tenant_id,management_unit_id) REFERENCES management_units(tenant_id,id),
 FOREIGN KEY(service_actor) REFERENCES users(id)
);
DO $$ DECLARE t text; BEGIN
 FOREACH t IN ARRAY ARRAY['vh_workforce_bindings','vh_workforce_outbox','vh_workforce_deliveries',
 'vh_workforce_assets','vh_workforce_mcp_intents','vh_workforce_provider_jobs','vh_workforce_management_grants'] LOOP
  EXECUTE format('ALTER TABLE %I ENABLE ROW LEVEL SECURITY', t);
  EXECUTE format('ALTER TABLE %I FORCE ROW LEVEL SECURITY', t);
  EXECUTE format('CREATE POLICY tenant_policy ON %I USING (tenant_id=nullif(current_setting(''app.tenant_id'',true),'''')::uuid) WITH CHECK (tenant_id=nullif(current_setting(''app.tenant_id'',true),'''')::uuid)',t);
 END LOOP;
END $$;
