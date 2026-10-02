DO $$
DECLARE status_constraint text;
BEGIN
  SELECT conname INTO status_constraint
  FROM pg_constraint
  WHERE conrelid='vh_ticket_plans'::regclass AND contype='c'
    AND pg_get_constraintdef(oid) ILIKE '%management_pending%'
    AND pg_get_constraintdef(oid) ILIKE '%resident_pending%'
  LIMIT 1;
  IF status_constraint IS NOT NULL THEN
    EXECUTE format('ALTER TABLE vh_ticket_plans DROP CONSTRAINT %I',status_constraint);
  END IF;
END $$;
--> statement-breakpoint
ALTER TABLE vh_ticket_plans
  ADD CONSTRAINT vh_ticket_plans_status_check
  CHECK(status IN ('management_pending','resident_pending','approved','rejected','revision_requested'));
--> statement-breakpoint
CREATE TABLE vh_reception_supervisor_messages (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  tenant_id uuid NOT NULL,
  direction text NOT NULL,
  message_id text NOT NULL,
  correlation_id text NOT NULL,
  ticket_id uuid NOT NULL,
  team_id uuid NOT NULL,
  ticket_generation integer NOT NULL,
  message_type text NOT NULL,
  payload jsonb NOT NULL,
  payload_hash text NOT NULL,
  response_body jsonb NOT NULL,
  created_by text NOT NULL,
  created_at timestamptz NOT NULL DEFAULT now(),
  CONSTRAINT vh_reception_supervisor_messages_tenant_id_fk
    FOREIGN KEY(tenant_id) REFERENCES tenants(id) ON DELETE RESTRICT,
  CONSTRAINT vh_reception_supervisor_messages_ticket_id_fk
    FOREIGN KEY(tenant_id,ticket_id) REFERENCES tickets(tenant_id,id) ON DELETE RESTRICT,
  CONSTRAINT vh_reception_supervisor_messages_team_id_fk
    FOREIGN KEY(tenant_id,team_id) REFERENCES agent_teams(tenant_id,id) ON DELETE RESTRICT,
  CONSTRAINT vh_reception_supervisor_messages_created_by_fk
    FOREIGN KEY(created_by) REFERENCES users(id) ON DELETE RESTRICT,
  CONSTRAINT vh_reception_supervisor_messages_tenant_key_uq UNIQUE(tenant_id,id),
  CONSTRAINT vh_reception_supervisor_messages_message_id_uq UNIQUE(tenant_id,message_id),
  CONSTRAINT vh_reception_supervisor_messages_direction_check
    CHECK(direction IN ('reception_to_supervisor','supervisor_to_reception')),
  CONSTRAINT vh_reception_supervisor_messages_generation_check CHECK(ticket_generation>=0),
  CONSTRAINT vh_reception_supervisor_messages_message_id_check CHECK(length(message_id) BETWEEN 1 AND 200),
  CONSTRAINT vh_reception_supervisor_messages_correlation_id_check CHECK(length(correlation_id) BETWEEN 1 AND 200),
  CONSTRAINT vh_reception_supervisor_messages_payload_check CHECK(jsonb_typeof(payload)='object'),
  CONSTRAINT vh_reception_supervisor_messages_response_check CHECK(jsonb_typeof(response_body)='object'),
  CONSTRAINT vh_reception_supervisor_messages_hash_check CHECK(payload_hash ~ '^[0-9a-f]{64}$'),
  CONSTRAINT vh_reception_supervisor_messages_type_check CHECK(
    (direction='reception_to_supervisor' AND message_type IN
      ('ticket_submitted','information_provided','plan_approved','plan_rejected','plan_change_requested','cancel_requested'))
    OR
    (direction='supervisor_to_reception' AND message_type IN
      ('accepted','in_progress','information_requested','plan_approval_requested','completed','failed','cancelled'))
  )
);
--> statement-breakpoint
CREATE INDEX vh_reception_supervisor_messages_team_page_idx
  ON vh_reception_supervisor_messages(tenant_id,team_id,created_at DESC,id DESC);
--> statement-breakpoint
CREATE INDEX vh_reception_supervisor_messages_ticket_page_idx
  ON vh_reception_supervisor_messages(tenant_id,ticket_id,ticket_generation,created_at DESC,id DESC);
--> statement-breakpoint
CREATE TABLE vh_reception_supervisor_pending (
  tenant_id uuid NOT NULL,
  ticket_id uuid NOT NULL,
  team_id uuid NOT NULL,
  ticket_generation integer NOT NULL,
  correlation_id text NOT NULL,
  pending_kind text NOT NULL,
  supervisor_message_id text NOT NULL,
  plan_id uuid,
  plan_version bigint,
  created_at timestamptz NOT NULL DEFAULT now(),
  CONSTRAINT vh_reception_supervisor_pending_tenant_id_fk
    FOREIGN KEY(tenant_id) REFERENCES tenants(id) ON DELETE RESTRICT,
  CONSTRAINT vh_reception_supervisor_pending_ticket_id_fk
    FOREIGN KEY(tenant_id,ticket_id) REFERENCES tickets(tenant_id,id) ON DELETE RESTRICT,
  CONSTRAINT vh_reception_supervisor_pending_team_id_fk
    FOREIGN KEY(tenant_id,team_id) REFERENCES agent_teams(tenant_id,id) ON DELETE RESTRICT,
  CONSTRAINT vh_reception_supervisor_pending_plan_id_fk
    FOREIGN KEY(tenant_id,plan_id) REFERENCES vh_ticket_plans(tenant_id,id) ON DELETE RESTRICT,
  CONSTRAINT vh_reception_supervisor_pending_pk PRIMARY KEY(tenant_id,ticket_id,ticket_generation),
  CONSTRAINT vh_reception_supervisor_pending_message_uq UNIQUE(tenant_id,supervisor_message_id),
  CONSTRAINT vh_reception_supervisor_pending_generation_check CHECK(ticket_generation>=0),
  CONSTRAINT vh_reception_supervisor_pending_correlation_check CHECK(length(correlation_id) BETWEEN 1 AND 200),
  CONSTRAINT vh_reception_supervisor_pending_kind_check CHECK(pending_kind IN ('information','plan_approval')),
  CONSTRAINT vh_reception_supervisor_pending_plan_check CHECK(
    (pending_kind='information' AND plan_id IS NULL AND plan_version IS NULL)
    OR
    (pending_kind='plan_approval' AND plan_id IS NOT NULL AND plan_version IS NOT NULL)
  )
);
--> statement-breakpoint
CREATE INDEX vh_reception_supervisor_pending_team_idx
  ON vh_reception_supervisor_pending(tenant_id,team_id,created_at DESC);
--> statement-breakpoint
CREATE FUNCTION vh_reception_supervisor_message_immutable() RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN
  RAISE EXCEPTION 'Reception/Supervisor V2 messages are immutable';
END $$;
--> statement-breakpoint
CREATE TRIGGER vh_reception_supervisor_message_immutable
  BEFORE UPDATE OR DELETE ON vh_reception_supervisor_messages
  FOR EACH ROW EXECUTE FUNCTION vh_reception_supervisor_message_immutable();
--> statement-breakpoint
ALTER TABLE vh_reception_supervisor_messages ENABLE ROW LEVEL SECURITY;
--> statement-breakpoint
ALTER TABLE vh_reception_supervisor_messages FORCE ROW LEVEL SECURITY;
--> statement-breakpoint
CREATE POLICY vh_reception_supervisor_messages_tenant_policy
  ON vh_reception_supervisor_messages
  USING(tenant_id=nullif(current_setting('app.tenant_id',true),'')::uuid)
  WITH CHECK(tenant_id=nullif(current_setting('app.tenant_id',true),'')::uuid);
--> statement-breakpoint
ALTER TABLE vh_reception_supervisor_pending ENABLE ROW LEVEL SECURITY;
--> statement-breakpoint
ALTER TABLE vh_reception_supervisor_pending FORCE ROW LEVEL SECURITY;
--> statement-breakpoint
CREATE POLICY vh_reception_supervisor_pending_tenant_policy
  ON vh_reception_supervisor_pending
  USING(tenant_id=nullif(current_setting('app.tenant_id',true),'')::uuid)
  WITH CHECK(tenant_id=nullif(current_setting('app.tenant_id',true),'')::uuid);
