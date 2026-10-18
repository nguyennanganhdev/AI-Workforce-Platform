-- Single-use password recovery. Only token digests are persisted; no email or password in this table.
CREATE TABLE public.password_reset_tokens (
    token_hash text PRIMARY KEY,
    tenant_id uuid NOT NULL REFERENCES public.tenants(id),
    user_id text NOT NULL REFERENCES public.users(id),
    created_at timestamptz NOT NULL DEFAULT now(),
    expires_at timestamptz NOT NULL,
    used_at timestamptz
);
CREATE INDEX password_reset_tokens_user_idx ON public.password_reset_tokens(tenant_id,user_id);
ALTER TABLE public.password_reset_tokens ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.password_reset_tokens FORCE ROW LEVEL SECURITY;
CREATE POLICY password_reset_tokens_tenant_policy ON public.password_reset_tokens
    USING (tenant_id=nullif(current_setting('app.tenant_id',true),'')::uuid)
    WITH CHECK (tenant_id=nullif(current_setting('app.tenant_id',true),'')::uuid);
