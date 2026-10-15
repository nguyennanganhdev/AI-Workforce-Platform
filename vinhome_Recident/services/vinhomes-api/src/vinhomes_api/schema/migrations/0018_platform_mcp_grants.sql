-- Ticket-scoped MCP grants and deduplicated platform notices. No human approval queue.
CREATE UNIQUE INDEX platform_commands_domain_notice_uq ON public.platform_commands(tenant_id,ticket_id,(body->>'domain_notice_key')) WHERE body ? 'domain_notice_key';

CREATE TABLE public.platform_mcp_grants (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id uuid NOT NULL DEFAULT nullif(current_setting('app.tenant_id',true),'')::uuid REFERENCES public.tenants(id),
    ticket_id uuid NOT NULL,
    management_ref text NOT NULL,
    workflow_id text,
    request_hash text,
    token_hash text NOT NULL UNIQUE CHECK (length(token_hash)=64),
    tools text[] NOT NULL CHECK (cardinality(tools)>0),
    expires_at timestamptz NOT NULL,
    revoked_at timestamptz,
    created_at timestamptz NOT NULL DEFAULT now(),
    FOREIGN KEY (tenant_id,ticket_id) REFERENCES public.platform_links(tenant_id,ticket_id)
);
ALTER TABLE public.platform_mcp_grants ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.platform_mcp_grants FORCE ROW LEVEL SECURITY;
CREATE POLICY platform_mcp_grants_tenant ON public.platform_mcp_grants USING (tenant_id=nullif(current_setting('app.tenant_id',true),'')::uuid) WITH CHECK (tenant_id=nullif(current_setting('app.tenant_id',true),'')::uuid);
