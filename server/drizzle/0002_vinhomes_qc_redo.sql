CREATE TABLE vh_qc_redo_orders (
 id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
 tenant_id uuid NOT NULL,
 qc_result_id uuid NOT NULL,
 source_work_order_id uuid NOT NULL,
 redo_work_order_id uuid NOT NULL,
 created_by text NOT NULL REFERENCES users(id),
 created_at timestamptz NOT NULL DEFAULT now(),
 UNIQUE (tenant_id,id),
 UNIQUE (tenant_id,qc_result_id),
 UNIQUE (tenant_id,redo_work_order_id),
 FOREIGN KEY (tenant_id,qc_result_id) REFERENCES vh_qc_results(tenant_id,id),
 FOREIGN KEY (tenant_id,source_work_order_id) REFERENCES work_orders(tenant_id,id),
 FOREIGN KEY (tenant_id,redo_work_order_id) REFERENCES work_orders(tenant_id,id)
);
--> statement-breakpoint
ALTER TABLE vh_qc_redo_orders ENABLE ROW LEVEL SECURITY;
ALTER TABLE vh_qc_redo_orders FORCE ROW LEVEL SECURITY;
CREATE POLICY vh_qc_redo_orders_tenant ON vh_qc_redo_orders
  USING (tenant_id=nullif(current_setting('app.tenant_id',true),'')::uuid)
  WITH CHECK (tenant_id=nullif(current_setting('app.tenant_id',true),'')::uuid);
