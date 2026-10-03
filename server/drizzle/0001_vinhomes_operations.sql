CREATE TABLE vh_qc_results (
 id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
 tenant_id uuid NOT NULL,
 work_order_id uuid NOT NULL,
 outcome text NOT NULL CHECK (outcome IN ('pass','fail','inconclusive')),
 criteria jsonb NOT NULL,
 redo_required boolean NOT NULL DEFAULT false,
 note text,
 checked_by text NOT NULL REFERENCES users(id),
 checked_at timestamptz NOT NULL DEFAULT now(),
 created_at timestamptz NOT NULL DEFAULT now(),
 UNIQUE (tenant_id,id),
 FOREIGN KEY (tenant_id,work_order_id) REFERENCES work_orders(tenant_id,id),
 CHECK (NOT redo_required OR outcome='fail')
);
--> statement-breakpoint
CREATE TABLE vh_cleaning_plans (
 id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
 tenant_id uuid NOT NULL,
 work_order_id uuid NOT NULL,
 plan jsonb NOT NULL,
 status text NOT NULL CHECK (status IN ('draft','in_progress','completed','cancelled')),
 version bigint NOT NULL DEFAULT 0,
 updated_by text NOT NULL REFERENCES users(id),
 created_at timestamptz NOT NULL DEFAULT now(),
 updated_at timestamptz NOT NULL DEFAULT now(),
 UNIQUE (tenant_id,id), UNIQUE (tenant_id,work_order_id),
 FOREIGN KEY (tenant_id,work_order_id) REFERENCES work_orders(tenant_id,id)
);
--> statement-breakpoint
CREATE TABLE vh_security_checkpoints (
 id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
 tenant_id uuid NOT NULL,
 site_id uuid NOT NULL,
 name text NOT NULL,
 location text NOT NULL,
 sort_order integer NOT NULL DEFAULT 0,
 status text NOT NULL CHECK (status IN ('pending','checked','missed')),
 checked_at timestamptz,
 guard_user_id text REFERENCES users(id),
 notes text,
 created_at timestamptz NOT NULL DEFAULT now(),
 updated_at timestamptz NOT NULL DEFAULT now(),
 UNIQUE (tenant_id,id),
 FOREIGN KEY (tenant_id,site_id) REFERENCES sites(tenant_id,id)
);
--> statement-breakpoint
CREATE TABLE vh_security_incidents (
 id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
 tenant_id uuid NOT NULL,
 site_id uuid NOT NULL,
 ticket_id uuid,
 title text NOT NULL,
 location text NOT NULL,
 severity text NOT NULL CHECK (severity IN ('p1','p2','p3','p4')),
 report jsonb NOT NULL,
 status text NOT NULL CHECK (status IN ('investigating','resolved','escalated_to_police')),
 reported_by text NOT NULL REFERENCES users(id),
 reported_at timestamptz NOT NULL DEFAULT now(),
 created_at timestamptz NOT NULL DEFAULT now(),
 updated_at timestamptz NOT NULL DEFAULT now(),
 UNIQUE (tenant_id,id),
 FOREIGN KEY (tenant_id,site_id) REFERENCES sites(tenant_id,id),
 FOREIGN KEY (tenant_id,ticket_id) REFERENCES tickets(tenant_id,id)
);
--> statement-breakpoint
CREATE TABLE vh_security_handovers (
 id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
 tenant_id uuid NOT NULL,
 site_id uuid NOT NULL,
 shift_name text NOT NULL CHECK (shift_name IN ('ca_sang','ca_chieu','ca_dem')),
 shift_date date NOT NULL,
 payload jsonb NOT NULL,
 from_user_id text NOT NULL REFERENCES users(id),
 to_user_id text NOT NULL REFERENCES users(id),
 confirmed boolean NOT NULL DEFAULT false,
 created_at timestamptz NOT NULL DEFAULT now(),
 updated_at timestamptz NOT NULL DEFAULT now(),
 UNIQUE (tenant_id,id),
 FOREIGN KEY (tenant_id,site_id) REFERENCES sites(tenant_id,id)
);
--> statement-breakpoint
CREATE TABLE vh_contractor_updates (
 id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
 tenant_id uuid NOT NULL,
 work_order_id uuid NOT NULL,
 status text NOT NULL CHECK (status IN ('pending','accepted','rejected','in_progress','completed')),
 worker_name text,
 materials jsonb NOT NULL DEFAULT '[]'::jsonb,
 note text,
 version bigint NOT NULL DEFAULT 0,
 updated_by text NOT NULL REFERENCES users(id),
 created_at timestamptz NOT NULL DEFAULT now(),
 updated_at timestamptz NOT NULL DEFAULT now(),
 UNIQUE (tenant_id,id), UNIQUE (tenant_id,work_order_id),
 FOREIGN KEY (tenant_id,work_order_id) REFERENCES work_orders(tenant_id,id)
);
--> statement-breakpoint
CREATE TABLE vh_budget_approvals (
 id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
 tenant_id uuid NOT NULL,
 work_order_id uuid NOT NULL,
 requested_by text NOT NULL REFERENCES users(id),
 reviewer_user_id text NOT NULL REFERENCES users(id),
 amount_vnd numeric(18,2) NOT NULL CHECK (amount_vnd>0),
 purpose text NOT NULL,
 status text NOT NULL CHECK (status IN ('pending','approved','rejected','cancelled')),
 version bigint NOT NULL DEFAULT 0,
 decided_by text REFERENCES users(id),
 decided_at timestamptz,
 decision_note text,
 created_at timestamptz NOT NULL DEFAULT now(),
 updated_at timestamptz NOT NULL DEFAULT now(),
 UNIQUE (tenant_id,id),
 FOREIGN KEY (tenant_id,work_order_id) REFERENCES work_orders(tenant_id,id)
);
--> statement-breakpoint
ALTER TABLE vh_qc_results ENABLE ROW LEVEL SECURITY;
ALTER TABLE vh_qc_results FORCE ROW LEVEL SECURITY;
CREATE POLICY vh_qc_results_tenant ON vh_qc_results USING (tenant_id=nullif(current_setting('app.tenant_id',true),'')::uuid) WITH CHECK (tenant_id=nullif(current_setting('app.tenant_id',true),'')::uuid);
--> statement-breakpoint
ALTER TABLE vh_cleaning_plans ENABLE ROW LEVEL SECURITY;
ALTER TABLE vh_cleaning_plans FORCE ROW LEVEL SECURITY;
CREATE POLICY vh_cleaning_plans_tenant ON vh_cleaning_plans USING (tenant_id=nullif(current_setting('app.tenant_id',true),'')::uuid) WITH CHECK (tenant_id=nullif(current_setting('app.tenant_id',true),'')::uuid);
--> statement-breakpoint
ALTER TABLE vh_security_checkpoints ENABLE ROW LEVEL SECURITY;
ALTER TABLE vh_security_checkpoints FORCE ROW LEVEL SECURITY;
CREATE POLICY vh_security_checkpoints_tenant ON vh_security_checkpoints USING (tenant_id=nullif(current_setting('app.tenant_id',true),'')::uuid) WITH CHECK (tenant_id=nullif(current_setting('app.tenant_id',true),'')::uuid);
--> statement-breakpoint
ALTER TABLE vh_security_incidents ENABLE ROW LEVEL SECURITY;
ALTER TABLE vh_security_incidents FORCE ROW LEVEL SECURITY;
CREATE POLICY vh_security_incidents_tenant ON vh_security_incidents USING (tenant_id=nullif(current_setting('app.tenant_id',true),'')::uuid) WITH CHECK (tenant_id=nullif(current_setting('app.tenant_id',true),'')::uuid);
--> statement-breakpoint
ALTER TABLE vh_security_handovers ENABLE ROW LEVEL SECURITY;
ALTER TABLE vh_security_handovers FORCE ROW LEVEL SECURITY;
CREATE POLICY vh_security_handovers_tenant ON vh_security_handovers USING (tenant_id=nullif(current_setting('app.tenant_id',true),'')::uuid) WITH CHECK (tenant_id=nullif(current_setting('app.tenant_id',true),'')::uuid);
--> statement-breakpoint
ALTER TABLE vh_contractor_updates ENABLE ROW LEVEL SECURITY;
ALTER TABLE vh_contractor_updates FORCE ROW LEVEL SECURITY;
CREATE POLICY vh_contractor_updates_tenant ON vh_contractor_updates USING (tenant_id=nullif(current_setting('app.tenant_id',true),'')::uuid) WITH CHECK (tenant_id=nullif(current_setting('app.tenant_id',true),'')::uuid);
--> statement-breakpoint
ALTER TABLE vh_budget_approvals ENABLE ROW LEVEL SECURITY;
ALTER TABLE vh_budget_approvals FORCE ROW LEVEL SECURITY;
CREATE POLICY vh_budget_approvals_tenant ON vh_budget_approvals USING (tenant_id=nullif(current_setting('app.tenant_id',true),'')::uuid) WITH CHECK (tenant_id=nullif(current_setting('app.tenant_id',true),'')::uuid);
