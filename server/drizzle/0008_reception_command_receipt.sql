-- Durable Reception operation receipts belong to the canonical V3 database.
CREATE TABLE vh_command_receipt (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  tenant_id uuid NOT NULL REFERENCES tenants(id),
  actor_type varchar(16) NOT NULL,
  actor_id varchar(128) NOT NULL,
  command_type varchar(128) NOT NULL,
  idempotency_key varchar(128) NOT NULL,
  payload_hash varchar(72) NOT NULL,
  subject_type varchar(128) NOT NULL,
  subject_id varchar(128),
  response_json jsonb,
  status varchar(16) NOT NULL CHECK (status IN ('IN_PROGRESS','COMPLETED')),
  created_at timestamptz NOT NULL DEFAULT now(),
  completed_at timestamptz,
  CONSTRAINT uq_vh_command_receipt_tenant_actor_command_key
    UNIQUE (tenant_id,actor_type,actor_id,command_type,idempotency_key)
);
--> statement-breakpoint
CREATE INDEX ix_vh_command_receipt_tenant_created ON vh_command_receipt(tenant_id,created_at);
--> statement-breakpoint
ALTER TABLE vh_command_receipt ENABLE ROW LEVEL SECURITY;
--> statement-breakpoint
ALTER TABLE vh_command_receipt FORCE ROW LEVEL SECURITY;
--> statement-breakpoint
CREATE POLICY vh_command_receipt_tenant_policy ON vh_command_receipt
  USING (tenant_id=nullif(current_setting('app.tenant_id',true),'')::uuid)
  WITH CHECK (tenant_id=nullif(current_setting('app.tenant_id',true),'')::uuid);
