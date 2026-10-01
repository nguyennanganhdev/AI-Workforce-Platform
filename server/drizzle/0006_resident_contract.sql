-- Resident Case is the public intake aggregate; canonical tickets/work orders
-- remain the operations aggregate. Extension tables follow 0001/0004 SQL ownership.
ALTER TABLE files ADD COLUMN unit_id uuid;
--> statement-breakpoint
ALTER TABLE files ADD CONSTRAINT files_unit_id_fk FOREIGN KEY (tenant_id,unit_id) REFERENCES units(tenant_id,id);
--> statement-breakpoint
ALTER TABLE files DROP CONSTRAINT files_check_0;
--> statement-breakpoint
ALTER TABLE files ADD CONSTRAINT files_check_0 CHECK (num_nonnulls(ticket_id,channel_id,document_id,report_id,unit_id)=1);
--> statement-breakpoint
ALTER TABLE files DROP CONSTRAINT files_check_1;
--> statement-breakpoint
ALTER TABLE files ADD CONSTRAINT files_check_1 CHECK (
 (scope_kind='ticket' AND ticket_id IS NOT NULL) OR (scope_kind='channel' AND channel_id IS NOT NULL)
 OR (scope_kind='document' AND document_id IS NOT NULL) OR (scope_kind='report' AND report_id IS NOT NULL)
 OR (scope_kind='resident' AND unit_id IS NOT NULL));
--> statement-breakpoint
ALTER TABLE files DROP CONSTRAINT files_check_3;
--> statement-breakpoint
ALTER TABLE files ADD CONSTRAINT files_check_3 CHECK (scope_kind IN ('ticket','channel','document','report','resident'));
--> statement-breakpoint
CREATE OR REPLACE FUNCTION app_validate_file() RETURNS trigger LANGUAGE plpgsql AS $$
DECLARE obj file_objects;
BEGIN
 IF NEW.accepted_object_id IS NOT NULL THEN
  SELECT * INTO STRICT obj FROM file_objects WHERE id=NEW.accepted_object_id AND tenant_id=NEW.tenant_id;
  IF obj.file_id<>NEW.id OR obj.variant<>'original' THEN RAISE EXCEPTION 'Accepted original object belongs to a different file'; END IF;
  IF NEW.status='ready' AND (obj.status<>'ready' OR obj.scan_status<>'clean' OR obj.verified_at IS NULL) THEN RAISE EXCEPTION 'File is not verified'; END IF;
 END IF;
 IF TG_OP='UPDATE' AND OLD.accepted_object_id IS NOT NULL AND NEW.accepted_object_id IS DISTINCT FROM OLD.accepted_object_id THEN RAISE EXCEPTION 'Accepted bytes are immutable'; END IF;
 IF TG_OP='UPDATE' AND (NEW.tenant_id,NEW.owner_principal_id,NEW.scope_kind,NEW.ticket_id,NEW.channel_id,NEW.document_id,NEW.report_id,NEW.unit_id) IS DISTINCT FROM (OLD.tenant_id,OLD.owner_principal_id,OLD.scope_kind,OLD.ticket_id,OLD.channel_id,OLD.document_id,OLD.report_id,OLD.unit_id) THEN RAISE EXCEPTION 'File security scope is immutable'; END IF;
 RETURN NEW;
END $$;
--> statement-breakpoint
CREATE TABLE vh_resident_cases (
 id uuid PRIMARY KEY DEFAULT gen_random_uuid(), tenant_id uuid NOT NULL REFERENCES tenants(id),
 requester_user_id text NOT NULL REFERENCES users(id), unit_id uuid NOT NULL, building_id uuid NOT NULL,
 site_id uuid NOT NULL, domain_id uuid NOT NULL, channel_id text NOT NULL,
 code text NOT NULL, title text NOT NULL CHECK(length(title) BETWEEN 1 AND 90),
 description text NOT NULL CHECK(length(description) BETWEEN 8 AND 5000),
 location_description text NOT NULL CHECK(length(location_description) BETWEEN 3 AND 500),
 location_label text NOT NULL, status text NOT NULL DEFAULT 'received' CHECK(status IN ('received','processing','confirmation','completed')),
 version bigint NOT NULL DEFAULT 1 CHECK(version>=1), current_resolution_id uuid,
 created_at timestamptz NOT NULL DEFAULT now(), updated_at timestamptz NOT NULL DEFAULT now(),
 UNIQUE(tenant_id,id), UNIQUE(tenant_id,code), UNIQUE(tenant_id,channel_id),
 FOREIGN KEY(tenant_id,unit_id) REFERENCES units(tenant_id,id),
 FOREIGN KEY(tenant_id,building_id) REFERENCES buildings(tenant_id,id),
 FOREIGN KEY(tenant_id,site_id) REFERENCES sites(tenant_id,id),
 FOREIGN KEY(tenant_id,domain_id) REFERENCES domains(tenant_id,id),
 FOREIGN KEY(tenant_id,channel_id) REFERENCES channels(tenant_id,id),
 CHECK(status NOT IN ('confirmation','completed') OR current_resolution_id IS NOT NULL)
);
--> statement-breakpoint
CREATE INDEX vh_resident_cases_owner_page ON vh_resident_cases(tenant_id,requester_user_id,created_at DESC,id DESC);
--> statement-breakpoint
CREATE TABLE vh_resident_submissions (
 id uuid PRIMARY KEY DEFAULT gen_random_uuid(), tenant_id uuid NOT NULL REFERENCES tenants(id), case_id uuid NOT NULL,
 submitted_by text NOT NULL REFERENCES users(id), description text NOT NULL, location_description text NOT NULL,
 created_at timestamptz NOT NULL DEFAULT now(), UNIQUE(tenant_id,id),
 FOREIGN KEY(tenant_id,case_id) REFERENCES vh_resident_cases(tenant_id,id)
);
--> statement-breakpoint
CREATE TABLE vh_resident_case_tickets (
 tenant_id uuid NOT NULL REFERENCES tenants(id), case_id uuid NOT NULL, ticket_id uuid NOT NULL,
 linked_by text NOT NULL REFERENCES users(id), created_at timestamptz NOT NULL DEFAULT now(),
 PRIMARY KEY(tenant_id,case_id,ticket_id),
 FOREIGN KEY(tenant_id,case_id) REFERENCES vh_resident_cases(tenant_id,id),
 FOREIGN KEY(tenant_id,ticket_id) REFERENCES tickets(tenant_id,id)
);
--> statement-breakpoint
CREATE INDEX vh_resident_case_tickets_source ON vh_resident_case_tickets(tenant_id,ticket_id);
--> statement-breakpoint
CREATE TABLE vh_resident_photos (
 tenant_id uuid NOT NULL REFERENCES tenants(id), file_id uuid NOT NULL, unit_id uuid NOT NULL,
 uploaded_by text NOT NULL REFERENCES users(id), case_id uuid, expires_at timestamptz NOT NULL DEFAULT now()+interval '24 hours',
 created_at timestamptz NOT NULL DEFAULT now(), PRIMARY KEY(tenant_id,file_id),
 FOREIGN KEY(tenant_id,file_id) REFERENCES files(tenant_id,id),
 FOREIGN KEY(tenant_id,unit_id) REFERENCES units(tenant_id,id),
 FOREIGN KEY(tenant_id,case_id) REFERENCES vh_resident_cases(tenant_id,id)
);
--> statement-breakpoint
CREATE TABLE vh_resident_resolutions (
 id uuid PRIMARY KEY DEFAULT gen_random_uuid(), tenant_id uuid NOT NULL REFERENCES tenants(id), case_id uuid NOT NULL,
 summary text NOT NULL CHECK(length(summary) BETWEEN 8 AND 5000), published_by text NOT NULL REFERENCES users(id),
 basis_versions jsonb NOT NULL CHECK(jsonb_typeof(basis_versions)='object'),
 published_at timestamptz NOT NULL DEFAULT now(), UNIQUE(tenant_id,id), UNIQUE(tenant_id,case_id,id),
 FOREIGN KEY(tenant_id,case_id) REFERENCES vh_resident_cases(tenant_id,id)
);
--> statement-breakpoint
ALTER TABLE vh_resident_cases ADD CONSTRAINT vh_resident_cases_resolution_fk
 FOREIGN KEY(tenant_id,id,current_resolution_id) REFERENCES vh_resident_resolutions(tenant_id,case_id,id);
--> statement-breakpoint
CREATE TABLE vh_resident_resolution_photos (
 tenant_id uuid NOT NULL REFERENCES tenants(id), resolution_id uuid NOT NULL, file_id uuid NOT NULL,
 PRIMARY KEY(tenant_id,resolution_id,file_id),
 FOREIGN KEY(tenant_id,resolution_id) REFERENCES vh_resident_resolutions(tenant_id,id),
 FOREIGN KEY(tenant_id,file_id) REFERENCES files(tenant_id,id)
);
--> statement-breakpoint
CREATE TABLE vh_resident_resolution_responses (
 id uuid PRIMARY KEY DEFAULT gen_random_uuid(), tenant_id uuid NOT NULL REFERENCES tenants(id), case_id uuid NOT NULL,
 resolution_id uuid NOT NULL, actor_id text NOT NULL REFERENCES users(id),
 decision text NOT NULL CHECK(decision IN ('confirm','reopen')), reason text,
 created_at timestamptz NOT NULL DEFAULT now(), UNIQUE(tenant_id,id), UNIQUE(tenant_id,resolution_id),
 FOREIGN KEY(tenant_id,case_id,resolution_id) REFERENCES vh_resident_resolutions(tenant_id,case_id,id),
 CHECK(decision<>'reopen' OR length(reason) BETWEEN 8 AND 2000)
);
--> statement-breakpoint
CREATE TABLE vh_resident_public_events (
 id uuid PRIMARY KEY DEFAULT gen_random_uuid(), tenant_id uuid NOT NULL REFERENCES tenants(id), case_id uuid NOT NULL,
 label text NOT NULL, note text, occurred_at timestamptz NOT NULL DEFAULT clock_timestamp(),
 UNIQUE(tenant_id,id), FOREIGN KEY(tenant_id,case_id) REFERENCES vh_resident_cases(tenant_id,id)
);
--> statement-breakpoint
CREATE INDEX vh_resident_events_page ON vh_resident_public_events(tenant_id,case_id,occurred_at,id);
--> statement-breakpoint
CREATE TABLE vh_resident_command_receipts (
 tenant_id uuid NOT NULL REFERENCES tenants(id), actor_id text NOT NULL REFERENCES users(id),
 operation text NOT NULL, resource text NOT NULL, key text NOT NULL CHECK(length(key) BETWEEN 8 AND 128),
 request_hash text NOT NULL, response_status integer NOT NULL, response_body jsonb NOT NULL,
 result_id uuid NOT NULL, created_at timestamptz NOT NULL DEFAULT now(),
 PRIMARY KEY(tenant_id,actor_id,operation,resource,key)
);
--> statement-breakpoint
CREATE TABLE vh_resident_outbox (
 id uuid PRIMARY KEY DEFAULT gen_random_uuid(), tenant_id uuid NOT NULL REFERENCES tenants(id), case_id uuid NOT NULL,
 event_id uuid NOT NULL, event_type text NOT NULL, payload jsonb NOT NULL,
 created_at timestamptz NOT NULL DEFAULT now(), delivered_at timestamptz,
 UNIQUE(tenant_id,id), UNIQUE(tenant_id,event_id),
 FOREIGN KEY(tenant_id,case_id) REFERENCES vh_resident_cases(tenant_id,id),
 FOREIGN KEY(tenant_id,event_id) REFERENCES vh_resident_public_events(tenant_id,id)
);
--> statement-breakpoint
-- Immutable receipts/results preserve replay and the history of a rework.
CREATE FUNCTION vh_resident_immutable() RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN RAISE EXCEPTION 'Resident receipt or historical record is immutable'; END $$;
--> statement-breakpoint
CREATE TRIGGER vh_resident_resolution_immutable BEFORE UPDATE OR DELETE ON vh_resident_resolutions FOR EACH ROW EXECUTE FUNCTION vh_resident_immutable();
--> statement-breakpoint
CREATE TRIGGER vh_resident_response_immutable BEFORE UPDATE OR DELETE ON vh_resident_resolution_responses FOR EACH ROW EXECUTE FUNCTION vh_resident_immutable();
--> statement-breakpoint
CREATE TRIGGER vh_resident_receipt_immutable BEFORE UPDATE OR DELETE ON vh_resident_command_receipts FOR EACH ROW EXECUTE FUNCTION vh_resident_immutable();
--> statement-breakpoint
DO $$ DECLARE name text; BEGIN
 FOREACH name IN ARRAY ARRAY['vh_resident_cases','vh_resident_submissions','vh_resident_case_tickets','vh_resident_photos','vh_resident_resolutions','vh_resident_resolution_photos','vh_resident_resolution_responses','vh_resident_public_events','vh_resident_command_receipts','vh_resident_outbox'] LOOP
  EXECUTE format('ALTER TABLE %I ENABLE ROW LEVEL SECURITY',name);
  EXECUTE format('ALTER TABLE %I FORCE ROW LEVEL SECURITY',name);
  EXECUTE format('CREATE POLICY tenant_scope ON %I USING (tenant_id=nullif(current_setting(''app.tenant_id'',true),'''')::uuid) WITH CHECK (tenant_id=nullif(current_setting(''app.tenant_id'',true),'''')::uuid)',name);
 END LOOP;
END $$;
