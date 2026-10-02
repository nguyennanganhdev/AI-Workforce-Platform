ALTER TABLE tickets DROP CONSTRAINT IF EXISTS tickets_unique_1;
--> statement-breakpoint
CREATE TABLE vh_ticket_plans (
 id uuid PRIMARY KEY DEFAULT gen_random_uuid(), tenant_id uuid NOT NULL REFERENCES tenants(id),
 ticket_id uuid NOT NULL, proposed_by text NOT NULL REFERENCES users(id),
 title text NOT NULL, steps jsonb NOT NULL, estimated_amount numeric(18,2) NOT NULL CHECK(estimated_amount>=0),
 status text NOT NULL CHECK(status IN ('management_pending','resident_pending','approved','rejected')),
 version bigint NOT NULL DEFAULT 0, idempotency_key text NOT NULL, request_hash text NOT NULL,
 management_by text REFERENCES users(id), management_note text, management_at timestamptz,
 resident_by text REFERENCES users(id), resident_note text, resident_at timestamptz,
 created_at timestamptz NOT NULL DEFAULT now(), updated_at timestamptz NOT NULL DEFAULT now(),
 UNIQUE(tenant_id,id), UNIQUE(tenant_id,ticket_id,idempotency_key),
 FOREIGN KEY(tenant_id,ticket_id) REFERENCES tickets(tenant_id,id)
);
CREATE UNIQUE INDEX vh_one_pending_plan ON vh_ticket_plans(tenant_id,ticket_id) WHERE status IN ('management_pending','resident_pending');
--> statement-breakpoint
CREATE TABLE vh_assets (
 id uuid PRIMARY KEY DEFAULT gen_random_uuid(), tenant_id uuid NOT NULL REFERENCES tenants(id),
 building_id uuid NOT NULL, code text NOT NULL, name text NOT NULL, details jsonb NOT NULL DEFAULT '{}',
 status text NOT NULL CHECK(status IN ('active','inactive')), created_at timestamptz NOT NULL DEFAULT now(),
 UNIQUE(tenant_id,id), UNIQUE(tenant_id,building_id,code), FOREIGN KEY(tenant_id,building_id) REFERENCES buildings(tenant_id,id)
);
--> statement-breakpoint
CREATE TABLE vh_sensor_readings (
 id uuid PRIMARY KEY DEFAULT gen_random_uuid(), tenant_id uuid NOT NULL REFERENCES tenants(id), asset_id uuid NOT NULL,
 parameter text NOT NULL, value numeric NOT NULL, unit text NOT NULL, measured_at timestamptz NOT NULL,
 source text NOT NULL, recorded_by text NOT NULL REFERENCES users(id), created_at timestamptz NOT NULL DEFAULT now(),
 UNIQUE(tenant_id,id), FOREIGN KEY(tenant_id,asset_id) REFERENCES vh_assets(tenant_id,id)
);
--> statement-breakpoint
CREATE TABLE vh_technical_measurements (
 id uuid PRIMARY KEY DEFAULT gen_random_uuid(), tenant_id uuid NOT NULL REFERENCES tenants(id), work_order_id uuid NOT NULL,
 parameter text NOT NULL, value numeric NOT NULL, unit text NOT NULL, note text NOT NULL,
 recorded_by text NOT NULL REFERENCES users(id), measured_at timestamptz NOT NULL, created_at timestamptz NOT NULL DEFAULT now(),
 UNIQUE(tenant_id,id), FOREIGN KEY(tenant_id,work_order_id) REFERENCES work_orders(tenant_id,id)
);
--> statement-breakpoint
CREATE TABLE vh_maintenance_records (
 id uuid PRIMARY KEY DEFAULT gen_random_uuid(), tenant_id uuid NOT NULL REFERENCES tenants(id), asset_id uuid NOT NULL,
 work_order_id uuid NOT NULL, note text NOT NULL, confirmed_by text NOT NULL REFERENCES users(id),
 created_at timestamptz NOT NULL DEFAULT now(), UNIQUE(tenant_id,id), UNIQUE(tenant_id,asset_id,work_order_id),
 FOREIGN KEY(tenant_id,asset_id) REFERENCES vh_assets(tenant_id,id), FOREIGN KEY(tenant_id,work_order_id) REFERENCES work_orders(tenant_id,id)
);
--> statement-breakpoint
CREATE TABLE vh_operational_requests (
 id uuid PRIMARY KEY DEFAULT gen_random_uuid(), tenant_id uuid NOT NULL REFERENCES tenants(id), work_order_id uuid NOT NULL,
 kind text NOT NULL CHECK(kind IN ('utility_isolation','area_restriction','apartment_entry','vendor_dispatch')),
 details jsonb NOT NULL, reason text NOT NULL, requested_by text NOT NULL REFERENCES users(id),
 status text NOT NULL CHECK(status IN ('pending','approved','rejected','completed','cancelled')),
 version bigint NOT NULL DEFAULT 0, idempotency_key text NOT NULL, request_hash text NOT NULL,
 decided_by text REFERENCES users(id), decision_note text, decided_at timestamptz,
 created_at timestamptz NOT NULL DEFAULT now(), updated_at timestamptz NOT NULL DEFAULT now(),
 UNIQUE(tenant_id,id), UNIQUE(tenant_id,work_order_id,idempotency_key), FOREIGN KEY(tenant_id,work_order_id) REFERENCES work_orders(tenant_id,id)
);
--> statement-breakpoint
CREATE TABLE vh_agent_reviews (
 id uuid PRIMARY KEY DEFAULT gen_random_uuid(), tenant_id uuid NOT NULL REFERENCES tenants(id), agent_id text NOT NULL,
 submitted_by text NOT NULL REFERENCES users(id), config_hash text NOT NULL, evaluation jsonb NOT NULL,
 status text NOT NULL CHECK(status IN ('pending','approved','rejected')), version bigint NOT NULL DEFAULT 0,
 decided_by text REFERENCES users(id), decision_note text, decided_at timestamptz,
 created_at timestamptz NOT NULL DEFAULT now(), updated_at timestamptz NOT NULL DEFAULT now(),
 UNIQUE(tenant_id,id), FOREIGN KEY(tenant_id,agent_id) REFERENCES agents(tenant_id,id)
);
CREATE UNIQUE INDEX vh_agent_pending_review ON vh_agent_reviews(tenant_id,agent_id) WHERE status='pending';
--> statement-breakpoint
CREATE TABLE vh_report_exports (
 id uuid PRIMARY KEY DEFAULT gen_random_uuid(), tenant_id uuid NOT NULL REFERENCES tenants(id), building_id uuid NOT NULL,
 created_by text NOT NULL REFERENCES users(id), kind text NOT NULL CHECK(kind IN ('incident_frequency','issued_revenue')),
 filters jsonb NOT NULL, status text NOT NULL CHECK(status IN ('ready','failed')), content bytea,
 error_code text, idempotency_key text NOT NULL, request_hash text NOT NULL, created_at timestamptz NOT NULL DEFAULT now(),
 UNIQUE(tenant_id,id), UNIQUE(tenant_id,created_by,idempotency_key), FOREIGN KEY(tenant_id,building_id) REFERENCES buildings(tenant_id,id),
 CHECK((status='ready' AND content IS NOT NULL) OR (status='failed' AND content IS NULL))
);
--> statement-breakpoint
CREATE TABLE vh_conversation_uploads (
 id uuid PRIMARY KEY DEFAULT gen_random_uuid(), tenant_id uuid NOT NULL REFERENCES tenants(id), file_id uuid NOT NULL,
 channel_id text NOT NULL, requested_by text NOT NULL REFERENCES users(id), location_id uuid NOT NULL,
 object_key text NOT NULL, expected_size bigint NOT NULL CHECK(expected_size>0 AND expected_size<=10485760),
 expected_sha256 text NOT NULL CHECK(expected_sha256 ~ '^[a-f0-9]{64}$'), mime_type text NOT NULL,
 status text NOT NULL CHECK(status IN ('issued','uploaded','ready')), idempotency_key text NOT NULL, request_hash text NOT NULL,
 created_at timestamptz NOT NULL DEFAULT now(), UNIQUE(tenant_id,id), UNIQUE(tenant_id,file_id), UNIQUE(tenant_id,channel_id,requested_by,idempotency_key),
 FOREIGN KEY(tenant_id,file_id) REFERENCES files(tenant_id,id), FOREIGN KEY(tenant_id,channel_id) REFERENCES channels(tenant_id,id),
 FOREIGN KEY(tenant_id,location_id) REFERENCES storage_locations(tenant_id,id)
);
--> statement-breakpoint
DO $$ DECLARE name text; BEGIN
 FOREACH name IN ARRAY ARRAY['vh_ticket_plans','vh_assets','vh_sensor_readings','vh_technical_measurements','vh_maintenance_records','vh_operational_requests','vh_agent_reviews','vh_report_exports','vh_conversation_uploads'] LOOP
  EXECUTE format('ALTER TABLE %I ENABLE ROW LEVEL SECURITY',name);
  EXECUTE format('ALTER TABLE %I FORCE ROW LEVEL SECURITY',name);
  EXECUTE format('CREATE POLICY tenant_scope ON %I USING (tenant_id=nullif(current_setting(''app.tenant_id'',true),'''')::uuid) WITH CHECK (tenant_id=nullif(current_setting(''app.tenant_id'',true),'''')::uuid)',name);
 END LOOP;
END $$;
