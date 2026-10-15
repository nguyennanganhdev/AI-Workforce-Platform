-- The bridge to the AI platform (Workforce v1), see docs/domain/NOI_WORKFORCE_V1.md section 4.
-- The domain talks to the platform as a partner: what it sends waits in a table until the platform took it, and
-- what the platform sends is written once. Every table is empty, and unused, while VINHOMES_API_PLATFORM_URL is unset.
--
--   platform_links       one row per ticket handed to the platform: which workflow, and where reading its events stopped
--   platform_commands    what the domain still has to tell the platform; the row id is the external_request_id
--   platform_inbox       platform messages and events already written into the resident's chat
--   platform_approvals   what the platform asked the resident to agree to
--   platform_operations  actions the platform's agent ran through a tool, by the reference the platform gave
--   platform_outbox      staff progress still to be reported to the platform, one row per ticket event

CREATE TABLE public.platform_links (
    ticket_id uuid NOT NULL,
    tenant_id uuid DEFAULT (NULLIF(current_setting('app.tenant_id'::text, true), ''::text))::uuid NOT NULL,
    channel_id text NOT NULL,
    user_id text NOT NULL,
    management_ref text NOT NULL,
    -- The platform's ids, known once it accepted the start command.
    conversation_id text,
    workflow_id text,
    state text,
    next_action text,
    revision integer,
    -- event_id of the last platform event applied.
    cursor text,
    status text DEFAULT 'pending' NOT NULL,
    created_at timestamp with time zone DEFAULT now() NOT NULL,
    updated_at timestamp with time zone DEFAULT now() NOT NULL,
    CONSTRAINT platform_links_pkey PRIMARY KEY (ticket_id),
    CONSTRAINT platform_links_tenant_key_uq UNIQUE (tenant_id, ticket_id),
    CONSTRAINT platform_links_tenant_id_fk FOREIGN KEY (tenant_id) REFERENCES public.tenants(id) ON DELETE RESTRICT,
    CONSTRAINT platform_links_ticket_id_fk FOREIGN KEY (tenant_id, ticket_id) REFERENCES public.tickets(tenant_id, id) ON DELETE RESTRICT,
    CONSTRAINT platform_links_status_check CHECK (status = ANY (ARRAY['pending'::text, 'open'::text, 'closed'::text, 'failed'::text]))
);
CREATE INDEX platform_links_channel_idx ON public.platform_links (tenant_id, channel_id);
ALTER TABLE public.platform_links ENABLE ROW LEVEL SECURITY;
ALTER TABLE ONLY public.platform_links FORCE ROW LEVEL SECURITY;
CREATE POLICY platform_links_tenant_policy ON public.platform_links
    USING ((tenant_id = (NULLIF(current_setting('app.tenant_id'::text, true), ''::text))::uuid))
    WITH CHECK ((tenant_id = (NULLIF(current_setting('app.tenant_id'::text, true), ''::text))::uuid));
CREATE TRIGGER platform_links_touch BEFORE UPDATE ON public.platform_links FOR EACH ROW EXECUTE FUNCTION public.app_touch_updated_at();

CREATE TABLE public.platform_commands (
    id uuid DEFAULT gen_random_uuid() NOT NULL,
    tenant_id uuid DEFAULT (NULLIF(current_setting('app.tenant_id'::text, true), ''::text))::uuid NOT NULL,
    ticket_id uuid NOT NULL,
    kind text NOT NULL,
    body jsonb NOT NULL,
    status text DEFAULT 'pending' NOT NULL,
    attempts integer DEFAULT 0 NOT NULL,
    next_attempt_at timestamp with time zone DEFAULT now() NOT NULL,
    last_error text,
    result jsonb,
    created_at timestamp with time zone DEFAULT now() NOT NULL,
    updated_at timestamp with time zone DEFAULT now() NOT NULL,
    CONSTRAINT platform_commands_pkey PRIMARY KEY (id),
    CONSTRAINT platform_commands_tenant_id_fk FOREIGN KEY (tenant_id) REFERENCES public.tenants(id) ON DELETE RESTRICT,
    CONSTRAINT platform_commands_ticket_id_fk FOREIGN KEY (tenant_id, ticket_id) REFERENCES public.platform_links(tenant_id, ticket_id) ON DELETE RESTRICT,
    CONSTRAINT platform_commands_kind_check CHECK (kind = ANY (ARRAY['start_workflow'::text, 'workflow_reply'::text, 'approval_decision'::text, 'close'::text])),
    CONSTRAINT platform_commands_status_check CHECK (status = ANY (ARRAY['pending'::text, 'done'::text, 'failed'::text]))
);
-- The sender takes the oldest unsent command of each ticket.
CREATE INDEX platform_commands_pending_idx ON public.platform_commands (tenant_id, ticket_id, created_at) WHERE status = 'pending';
ALTER TABLE public.platform_commands ENABLE ROW LEVEL SECURITY;
ALTER TABLE ONLY public.platform_commands FORCE ROW LEVEL SECURITY;
CREATE POLICY platform_commands_tenant_policy ON public.platform_commands
    USING ((tenant_id = (NULLIF(current_setting('app.tenant_id'::text, true), ''::text))::uuid))
    WITH CHECK ((tenant_id = (NULLIF(current_setting('app.tenant_id'::text, true), ''::text))::uuid));
CREATE TRIGGER platform_commands_touch BEFORE UPDATE ON public.platform_commands FOR EACH ROW EXECUTE FUNCTION public.app_touch_updated_at();

CREATE TABLE public.platform_inbox (
    tenant_id uuid DEFAULT (NULLIF(current_setting('app.tenant_id'::text, true), ''::text))::uuid NOT NULL,
    -- message_id or event_id of the platform; the primary key is what keeps a chat line from being written twice.
    platform_id text NOT NULL,
    ticket_id uuid NOT NULL,
    chat_message_id uuid,
    created_at timestamp with time zone DEFAULT now() NOT NULL,
    updated_at timestamp with time zone DEFAULT now() NOT NULL,
    CONSTRAINT platform_inbox_pkey PRIMARY KEY (tenant_id, platform_id),
    CONSTRAINT platform_inbox_tenant_id_fk FOREIGN KEY (tenant_id) REFERENCES public.tenants(id) ON DELETE RESTRICT,
    CONSTRAINT platform_inbox_ticket_id_fk FOREIGN KEY (tenant_id, ticket_id) REFERENCES public.platform_links(tenant_id, ticket_id) ON DELETE RESTRICT
);
ALTER TABLE public.platform_inbox ENABLE ROW LEVEL SECURITY;
ALTER TABLE ONLY public.platform_inbox FORCE ROW LEVEL SECURITY;
CREATE POLICY platform_inbox_tenant_policy ON public.platform_inbox
    USING ((tenant_id = (NULLIF(current_setting('app.tenant_id'::text, true), ''::text))::uuid))
    WITH CHECK ((tenant_id = (NULLIF(current_setting('app.tenant_id'::text, true), ''::text))::uuid));
CREATE TRIGGER platform_inbox_touch BEFORE UPDATE ON public.platform_inbox FOR EACH ROW EXECUTE FUNCTION public.app_touch_updated_at();

CREATE TABLE public.platform_approvals (
    approval_id text NOT NULL,
    tenant_id uuid DEFAULT (NULLIF(current_setting('app.tenant_id'::text, true), ''::text))::uuid NOT NULL,
    ticket_id uuid NOT NULL,
    summary jsonb NOT NULL,
    arguments_hash text NOT NULL,
    quote_ref text,
    expected_revision integer NOT NULL,
    expires_at timestamp with time zone,
    status text DEFAULT 'pending' NOT NULL,
    created_at timestamp with time zone DEFAULT now() NOT NULL,
    updated_at timestamp with time zone DEFAULT now() NOT NULL,
    CONSTRAINT platform_approvals_pkey PRIMARY KEY (approval_id),
    CONSTRAINT platform_approvals_tenant_id_fk FOREIGN KEY (tenant_id) REFERENCES public.tenants(id) ON DELETE RESTRICT,
    CONSTRAINT platform_approvals_ticket_id_fk FOREIGN KEY (tenant_id, ticket_id) REFERENCES public.platform_links(tenant_id, ticket_id) ON DELETE RESTRICT,
    CONSTRAINT platform_approvals_status_check CHECK (status = ANY (ARRAY['pending'::text, 'approved'::text, 'rejected'::text, 'expired'::text]))
);
ALTER TABLE public.platform_approvals ENABLE ROW LEVEL SECURITY;
ALTER TABLE ONLY public.platform_approvals FORCE ROW LEVEL SECURITY;
CREATE POLICY platform_approvals_tenant_policy ON public.platform_approvals
    USING ((tenant_id = (NULLIF(current_setting('app.tenant_id'::text, true), ''::text))::uuid))
    WITH CHECK ((tenant_id = (NULLIF(current_setting('app.tenant_id'::text, true), ''::text))::uuid));
CREATE TRIGGER platform_approvals_touch BEFORE UPDATE ON public.platform_approvals FOR EACH ROW EXECUTE FUNCTION public.app_touch_updated_at();

CREATE TABLE public.platform_operations (
    -- Given by the platform (cr_...): the same reference again gets `answer` back and nothing is done twice.
    client_reference text NOT NULL,
    tenant_id uuid DEFAULT (NULLIF(current_setting('app.tenant_id'::text, true), ''::text))::uuid NOT NULL,
    ticket_id uuid NOT NULL,
    tool text NOT NULL,
    -- Only for the tool that dispatches work: progress of this work order is reported under this reference.
    work_order_id uuid,
    answer jsonb NOT NULL,
    created_at timestamp with time zone DEFAULT now() NOT NULL,
    updated_at timestamp with time zone DEFAULT now() NOT NULL,
    CONSTRAINT platform_operations_pkey PRIMARY KEY (client_reference),
    CONSTRAINT platform_operations_tenant_id_fk FOREIGN KEY (tenant_id) REFERENCES public.tenants(id) ON DELETE RESTRICT,
    CONSTRAINT platform_operations_ticket_id_fk FOREIGN KEY (tenant_id, ticket_id) REFERENCES public.platform_links(tenant_id, ticket_id) ON DELETE RESTRICT,
    CONSTRAINT platform_operations_work_order_id_fk FOREIGN KEY (tenant_id, work_order_id) REFERENCES public.work_orders(tenant_id, id) ON DELETE RESTRICT
);
CREATE UNIQUE INDEX platform_operations_work_order_uq ON public.platform_operations (tenant_id, work_order_id) WHERE work_order_id IS NOT NULL;
ALTER TABLE public.platform_operations ENABLE ROW LEVEL SECURITY;
ALTER TABLE ONLY public.platform_operations FORCE ROW LEVEL SECURITY;
CREATE POLICY platform_operations_tenant_policy ON public.platform_operations
    USING ((tenant_id = (NULLIF(current_setting('app.tenant_id'::text, true), ''::text))::uuid))
    WITH CHECK ((tenant_id = (NULLIF(current_setting('app.tenant_id'::text, true), ''::text))::uuid));
CREATE TRIGGER platform_operations_touch BEFORE UPDATE ON public.platform_operations FOR EACH ROW EXECUTE FUNCTION public.app_touch_updated_at();

CREATE TABLE public.platform_outbox (
    -- ticket_events.id, sent as external_event_id.
    event_id uuid NOT NULL,
    tenant_id uuid DEFAULT (NULLIF(current_setting('app.tenant_id'::text, true), ''::text))::uuid NOT NULL,
    ticket_id uuid NOT NULL,
    client_reference text NOT NULL,
    external_job_id text NOT NULL,
    event_type text NOT NULL,
    -- ticket_events.seq and occurred_at.
    provider_version bigint NOT NULL,
    occurred_at timestamp with time zone NOT NULL,
    data jsonb NOT NULL,
    status text DEFAULT 'pending' NOT NULL,
    attempts integer DEFAULT 0 NOT NULL,
    next_attempt_at timestamp with time zone DEFAULT now() NOT NULL,
    receipt jsonb,
    created_at timestamp with time zone DEFAULT now() NOT NULL,
    updated_at timestamp with time zone DEFAULT now() NOT NULL,
    CONSTRAINT platform_outbox_pkey PRIMARY KEY (event_id),
    CONSTRAINT platform_outbox_tenant_id_fk FOREIGN KEY (tenant_id) REFERENCES public.tenants(id) ON DELETE RESTRICT,
    CONSTRAINT platform_outbox_ticket_id_fk FOREIGN KEY (tenant_id, ticket_id) REFERENCES public.platform_links(tenant_id, ticket_id) ON DELETE RESTRICT,
    CONSTRAINT platform_outbox_status_check CHECK (status = ANY (ARRAY['pending'::text, 'sent'::text, 'rejected'::text]))
);
CREATE INDEX platform_outbox_ticket_idx ON public.platform_outbox (tenant_id, ticket_id, provider_version);
ALTER TABLE public.platform_outbox ENABLE ROW LEVEL SECURITY;
ALTER TABLE ONLY public.platform_outbox FORCE ROW LEVEL SECURITY;
CREATE POLICY platform_outbox_tenant_policy ON public.platform_outbox
    USING ((tenant_id = (NULLIF(current_setting('app.tenant_id'::text, true), ''::text))::uuid))
    WITH CHECK ((tenant_id = (NULLIF(current_setting('app.tenant_id'::text, true), ''::text))::uuid));
CREATE TRIGGER platform_outbox_touch BEFORE UPDATE ON public.platform_outbox FOR EACH ROW EXECUTE FUNCTION public.app_touch_updated_at();
