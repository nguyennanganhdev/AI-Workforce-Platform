-- Explicit operator binding: a Platform BQL account can read only this zone.
CREATE TABLE platform_management_bindings (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id uuid NOT NULL REFERENCES tenants(id),
    platform_tenant text NOT NULL,
    platform_domain text NOT NULL,
    platform_area text NOT NULL,
    platform_user text NOT NULL,
    management_unit_id uuid NOT NULL REFERENCES management_units(id),
    site_id uuid NOT NULL REFERENCES sites(id),
    zone_id uuid REFERENCES zones(id),
    active boolean NOT NULL DEFAULT true,
    created_at timestamptz NOT NULL DEFAULT now(),
    UNIQUE(tenant_id, platform_tenant, platform_domain, platform_area, platform_user)
);
ALTER TABLE platform_management_bindings ENABLE ROW LEVEL SECURITY;
ALTER TABLE platform_management_bindings FORCE ROW LEVEL SECURITY;
CREATE POLICY platform_management_tenant ON platform_management_bindings
    USING (tenant_id=nullif(current_setting('app.tenant_id',true),'')::uuid)
    WITH CHECK (tenant_id=nullif(current_setting('app.tenant_id',true),'')::uuid);
