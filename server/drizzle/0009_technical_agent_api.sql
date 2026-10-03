-- Technical A2 transport persistence. Output records are append-only; grants are provisioned by the backend owner.
CREATE TABLE vh_technical_agent_grants (
 tenant_id uuid NOT NULL REFERENCES tenants(id), agent_id text NOT NULL REFERENCES agents(id),
 capability text NOT NULL, scope_id uuid NOT NULL,
 PRIMARY KEY(tenant_id,agent_id,capability,scope_id),
 FOREIGN KEY(tenant_id,scope_id) REFERENCES access_scopes(tenant_id,id)
);
CREATE TABLE vh_technical_sop_profiles (
 tenant_id uuid NOT NULL REFERENCES tenants(id), document_code text NOT NULL, version_no integer NOT NULL,
 issue_codes jsonb NOT NULL, excerpt text NOT NULL, acceptance_criteria jsonb NOT NULL,
 PRIMARY KEY(tenant_id,document_code,version_no)
);
CREATE TABLE vh_technical_sensors (
 tenant_id uuid NOT NULL REFERENCES tenants(id), sensor_id text NOT NULL, building_id uuid NOT NULL,
 asset_id text, metric text NOT NULL, unit text NOT NULL,
 PRIMARY KEY(tenant_id,sensor_id), FOREIGN KEY(tenant_id,building_id) REFERENCES buildings(tenant_id,id)
);
CREATE TABLE vh_technical_sensor_samples (
 id uuid PRIMARY KEY DEFAULT gen_random_uuid(), tenant_id uuid NOT NULL, sensor_id text NOT NULL,
 value numeric NOT NULL, unit text NOT NULL, observed_at timestamptz NOT NULL,
 quality text NOT NULL CHECK(quality IN('good','uncertain','bad','unknown')),
 FOREIGN KEY(tenant_id,sensor_id) REFERENCES vh_technical_sensors(tenant_id,sensor_id)
);
CREATE INDEX vh_technical_samples_time ON vh_technical_sensor_samples(tenant_id,sensor_id,observed_at);
CREATE TABLE vh_technical_measurement_records (
 tenant_id uuid NOT NULL REFERENCES tenants(id), id text NOT NULL, building_id uuid NOT NULL,
 work_order_id uuid NOT NULL, asset_id text, payload jsonb NOT NULL,
 PRIMARY KEY(tenant_id,id), FOREIGN KEY(tenant_id,building_id) REFERENCES buildings(tenant_id,id),
 FOREIGN KEY(tenant_id,work_order_id) REFERENCES work_orders(tenant_id,id)
);
CREATE TABLE vh_technical_executor_results (
 tenant_id uuid NOT NULL REFERENCES tenants(id), id text NOT NULL, building_id uuid NOT NULL,
 work_order_id uuid NOT NULL, payload jsonb NOT NULL,
 PRIMARY KEY(tenant_id,id), FOREIGN KEY(tenant_id,building_id) REFERENCES buildings(tenant_id,id),
 FOREIGN KEY(tenant_id,work_order_id) REFERENCES work_orders(tenant_id,id)
);
CREATE TABLE vh_technical_maintenance_events (
 tenant_id uuid NOT NULL REFERENCES tenants(id), id text NOT NULL, building_id uuid NOT NULL,
 asset_id text NOT NULL, work_order_id uuid, supersedes_event_id text, occurred_at timestamptz NOT NULL,
 payload jsonb NOT NULL, PRIMARY KEY(tenant_id,id), UNIQUE(tenant_id,supersedes_event_id),
 FOREIGN KEY(tenant_id,building_id) REFERENCES buildings(tenant_id,id),
 FOREIGN KEY(tenant_id,work_order_id) REFERENCES work_orders(tenant_id,id),
 FOREIGN KEY(tenant_id,supersedes_event_id) REFERENCES vh_technical_maintenance_events(tenant_id,id)
);
CREATE TABLE vh_technical_approval_requests (
 tenant_id uuid NOT NULL REFERENCES tenants(id), id text NOT NULL, building_id uuid NOT NULL,
 incident_id uuid NOT NULL, kind text NOT NULL CHECK(kind IN('power_isolation','area_restriction','apartment_entry','vendor_dispatch')),
 status text NOT NULL DEFAULT 'pending' CHECK(status IN('pending','approved','rejected','cancelled','completed')),
 payload jsonb NOT NULL, PRIMARY KEY(tenant_id,id),
 FOREIGN KEY(tenant_id,building_id) REFERENCES buildings(tenant_id,id),
 FOREIGN KEY(tenant_id,incident_id) REFERENCES tickets(tenant_id,id)
);
CREATE TABLE vh_technical_vendors (
 tenant_id uuid NOT NULL REFERENCES tenants(id), id text NOT NULL, payload jsonb NOT NULL, PRIMARY KEY(tenant_id,id)
);
CREATE TABLE vh_technical_api_receipts (
 tenant_id uuid NOT NULL REFERENCES tenants(id), actor_id text NOT NULL, tool text NOT NULL,
 idempotency_key text NOT NULL, payload_hash text NOT NULL, outcome jsonb NOT NULL, response jsonb NOT NULL,
 created_at timestamptz NOT NULL DEFAULT now(), PRIMARY KEY(tenant_id,actor_id,tool,idempotency_key)
);
CREATE TABLE vh_technical_api_audit (
 id uuid PRIMARY KEY DEFAULT gen_random_uuid(), tenant_id uuid NOT NULL REFERENCES tenants(id),
 metadata jsonb NOT NULL, created_at timestamptz NOT NULL DEFAULT now()
);
--> statement-breakpoint
CREATE FUNCTION vh_technical_append_only() RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN RAISE EXCEPTION 'Technical agent records are append-only'; END $$;
--> statement-breakpoint
DO $$ DECLARE name text; BEGIN
 FOREACH name IN ARRAY ARRAY['vh_technical_agent_grants','vh_technical_sop_profiles','vh_technical_sensors',
 'vh_technical_sensor_samples','vh_technical_measurement_records','vh_technical_executor_results',
 'vh_technical_maintenance_events','vh_technical_approval_requests','vh_technical_vendors',
 'vh_technical_api_receipts','vh_technical_api_audit'] LOOP
  EXECUTE format('ALTER TABLE %I ENABLE ROW LEVEL SECURITY',name);
  EXECUTE format('ALTER TABLE %I FORCE ROW LEVEL SECURITY',name);
  EXECUTE format('CREATE POLICY tenant_scope ON %I USING(tenant_id=nullif(current_setting(''app.tenant_id'',true),'''')::uuid) WITH CHECK(tenant_id=nullif(current_setting(''app.tenant_id'',true),'''')::uuid)',name);
 END LOOP;
 FOREACH name IN ARRAY ARRAY['vh_technical_sensor_samples','vh_technical_measurement_records',
 'vh_technical_executor_results','vh_technical_maintenance_events','vh_technical_api_receipts','vh_technical_api_audit'] LOOP
  EXECUTE format('CREATE TRIGGER append_only BEFORE UPDATE OR DELETE ON %I FOR EACH ROW EXECUTE FUNCTION vh_technical_append_only()',name);
 END LOOP;
END $$;
