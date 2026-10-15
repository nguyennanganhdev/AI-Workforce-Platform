-- The domain's view of an outside system (see docs/domain/HOP_DONG_TICH_HOP.md).
--
-- Replaces the agent-shaped tables (agents, agent_versions, agent_releases, agent_runs, agent_teams,
-- team_members, channel_agents, runtime_backends, runtime_identities, runtime_session_bindings) with three
-- things the domain actually needs to know about a caller that is not a person:
--   integration_clients  who may call, and what it may do
--   delegations          a short permission to act on behalf of one person
--   integration_cases    a request handed to a client to work on (was agent_teams)
-- Columns that named an agent now name a client. Rows are carried over, so a database built from
-- 0001..0005 migrates in place.

-- ===== integration_clients =====

CREATE TABLE public.integration_clients (
    tenant_id uuid DEFAULT (NULLIF(current_setting('app.tenant_id'::text, true), ''::text))::uuid NOT NULL,
    id text NOT NULL,
    name text NOT NULL,
    kind text NOT NULL,
    status text DEFAULT 'active' NOT NULL,
    accepts_cases boolean DEFAULT false NOT NULL,
    levels jsonb DEFAULT '{}'::jsonb NOT NULL,
    secret_hash text,
    secret_hash_next text,
    created_at timestamp with time zone DEFAULT now() NOT NULL,
    updated_at timestamp with time zone DEFAULT now() NOT NULL,
    CONSTRAINT integration_clients_pkey PRIMARY KEY (tenant_id, id),
    CONSTRAINT integration_clients_kind_check CHECK (kind IN ('reception', 'platform')),
    CONSTRAINT integration_clients_status_check CHECK (status IN ('active', 'disabled')),
    CONSTRAINT integration_clients_levels_check CHECK (jsonb_typeof(levels) = 'object'),
    CONSTRAINT integration_clients_tenant_id_fk FOREIGN KEY (tenant_id) REFERENCES public.tenants(id) ON DELETE RESTRICT
);
CREATE UNIQUE INDEX integration_clients_one_reception ON public.integration_clients (tenant_id) WHERE kind = 'reception' AND status = 'active';
CREATE UNIQUE INDEX integration_clients_one_case_taker ON public.integration_clients (tenant_id) WHERE accepts_cases AND status = 'active';
CREATE UNIQUE INDEX integration_clients_secret_hash_uq ON public.integration_clients (secret_hash) WHERE secret_hash IS NOT NULL;
ALTER TABLE public.integration_clients ENABLE ROW LEVEL SECURITY;
ALTER TABLE ONLY public.integration_clients FORCE ROW LEVEL SECURITY;
CREATE POLICY integration_clients_tenant_policy ON public.integration_clients
    USING ((tenant_id = (NULLIF(current_setting('app.tenant_id'::text, true), ''::text))::uuid))
    WITH CHECK ((tenant_id = (NULLIF(current_setting('app.tenant_id'::text, true), ''::text))::uuid));
CREATE TRIGGER integration_clients_touch BEFORE UPDATE ON public.integration_clients FOR EACH ROW EXECUTE FUNCTION public.app_touch_updated_at();

-- Reception and the one active Supervisor become clients; every other agent is kept but disabled.
INSERT INTO public.integration_clients (tenant_id, id, name, kind, status, accepts_cases, levels)
SELECT a.tenant_id, a.id, a.name,
       CASE WHEN a.purpose = 'reception' THEN 'reception' ELSE 'platform' END,
       CASE WHEN a.status = 'active' AND a.purpose IN ('reception', 'supervisor') THEN 'active' ELSE 'disabled' END,
       a.purpose = 'supervisor' AND a.status = 'active'
         AND a.id = (SELECT min(b.id) FROM public.agents b WHERE b.tenant_id = a.tenant_id AND b.purpose = 'supervisor' AND b.status = 'active'),
       '{}'::jsonb
FROM public.agents a;

-- ===== columns that named an agent now name a client =====

ALTER TABLE public.channels DROP CONSTRAINT channels_last_message_agent_id_fk;
ALTER TABLE public.channels RENAME COLUMN last_message_agent_id TO last_message_client_id;
ALTER TABLE public.channels ADD CONSTRAINT channels_last_message_client_id_fk FOREIGN KEY (tenant_id, last_message_client_id) REFERENCES public.integration_clients(tenant_id, id) ON DELETE RESTRICT;

ALTER TABLE public.messages DROP CONSTRAINT messages_sender_agent_id_fk;
ALTER TABLE public.messages RENAME COLUMN sender_agent_id TO sender_client_id;
ALTER TABLE public.messages ADD CONSTRAINT messages_sender_client_id_fk FOREIGN KEY (tenant_id, sender_client_id) REFERENCES public.integration_clients(tenant_id, id) ON DELETE RESTRICT;

ALTER TABLE public.ticket_events DROP CONSTRAINT ticket_events_actor_agent_id_fk;
ALTER TABLE public.ticket_events RENAME COLUMN actor_agent_id TO actor_client_id;
ALTER TABLE public.ticket_events ADD CONSTRAINT ticket_events_actor_client_id_fk FOREIGN KEY (tenant_id, actor_client_id) REFERENCES public.integration_clients(tenant_id, id) ON DELETE RESTRICT;

ALTER TABLE public.work_assignments DROP CONSTRAINT work_assignments_assigned_by_agent_id_fk;
ALTER TABLE public.work_assignments RENAME COLUMN assigned_by_agent_id TO assigned_by_client_id;
ALTER TABLE public.work_assignments ADD CONSTRAINT work_assignments_assigned_by_client_id_fk FOREIGN KEY (tenant_id, assigned_by_client_id) REFERENCES public.integration_clients(tenant_id, id) ON DELETE RESTRICT;

ALTER TABLE public.vh_ticket_plans DROP CONSTRAINT vh_ticket_plans_proposed_by_agent_fk;
ALTER TABLE public.vh_ticket_plans RENAME COLUMN proposed_by_agent_id TO proposed_by_client_id;
ALTER TABLE public.vh_ticket_plans ADD CONSTRAINT vh_ticket_plans_proposed_by_client_fk FOREIGN KEY (tenant_id, proposed_by_client_id) REFERENCES public.integration_clients(tenant_id, id) ON DELETE RESTRICT;

ALTER TABLE public.vh_reception_supervisor_messages DROP CONSTRAINT vh_reception_supervisor_messages_created_by_agent_fk;
ALTER TABLE public.vh_reception_supervisor_messages RENAME COLUMN created_by_agent_id TO created_by_client_id;
ALTER TABLE public.vh_reception_supervisor_messages ADD CONSTRAINT vh_reception_supervisor_messages_created_by_client_fk FOREIGN KEY (tenant_id, created_by_client_id) REFERENCES public.integration_clients(tenant_id, id) ON DELETE RESTRICT;

-- ===== delegations (was agent_runs) =====

CREATE TABLE public.delegations (
    id uuid DEFAULT gen_random_uuid() NOT NULL,
    tenant_id uuid NOT NULL,
    client_id text NOT NULL,
    user_id text NOT NULL,
    purpose text NOT NULL,
    persona text DEFAULT 'resident' NOT NULL,
    levels text[] DEFAULT '{}' NOT NULL,
    token_hash text,
    channel_id text,
    status text DEFAULT 'active' NOT NULL,
    idempotency_key text NOT NULL,
    correlation_id text NOT NULL,
    expires_at timestamp with time zone NOT NULL,
    finished_at timestamp with time zone,
    error_code text,
    calls bigint DEFAULT 0 NOT NULL,
    input_tokens bigint DEFAULT 0 NOT NULL,
    output_tokens bigint DEFAULT 0 NOT NULL,
    created_at timestamp with time zone DEFAULT now() NOT NULL,
    updated_at timestamp with time zone DEFAULT now() NOT NULL,
    CONSTRAINT delegations_pkey PRIMARY KEY (id),
    CONSTRAINT delegations_tenant_key_uq UNIQUE (tenant_id, id),
    CONSTRAINT delegations_idempotency_uq UNIQUE (tenant_id, idempotency_key),
    CONSTRAINT delegations_purpose_check CHECK (purpose IN ('reception_turn', 'resident_assistant', 'staff_assistant')),
    CONSTRAINT delegations_status_check CHECK (status IN ('active', 'finished', 'failed', 'revoked')),
    CONSTRAINT delegations_persona_check CHECK (persona IN ('resident', 'staff')),
    CONSTRAINT delegations_levels_check CHECK (levels <@ ARRAY['read', 'draft', 'act_small', 'propose']::text[]),
    CONSTRAINT delegations_tenant_id_fk FOREIGN KEY (tenant_id) REFERENCES public.tenants(id) ON DELETE RESTRICT,
    CONSTRAINT delegations_client_id_fk FOREIGN KEY (tenant_id, client_id) REFERENCES public.integration_clients(tenant_id, id) ON DELETE RESTRICT,
    CONSTRAINT delegations_user_id_fk FOREIGN KEY (user_id) REFERENCES public.users(id) ON DELETE RESTRICT,
    CONSTRAINT delegations_channel_id_fk FOREIGN KEY (tenant_id, channel_id) REFERENCES public.channels(tenant_id, id) ON DELETE RESTRICT
);
CREATE UNIQUE INDEX delegations_token_hash_uq ON public.delegations (token_hash) WHERE token_hash IS NOT NULL;
CREATE INDEX delegations_user_idx ON public.delegations (tenant_id, user_id, created_at DESC);
CREATE INDEX delegations_active_idx ON public.delegations (tenant_id, expires_at) WHERE status = 'active';
ALTER TABLE public.delegations ENABLE ROW LEVEL SECURITY;
ALTER TABLE ONLY public.delegations FORCE ROW LEVEL SECURITY;
CREATE POLICY delegations_tenant_policy ON public.delegations
    USING ((tenant_id = (NULLIF(current_setting('app.tenant_id'::text, true), ''::text))::uuid))
    WITH CHECK ((tenant_id = (NULLIF(current_setting('app.tenant_id'::text, true), ''::text))::uuid));
CREATE TRIGGER delegations_touch BEFORE UPDATE ON public.delegations FOR EACH ROW EXECUTE FUNCTION public.app_touch_updated_at();

INSERT INTO public.delegations (id, tenant_id, client_id, user_id, purpose, channel_id, status, idempotency_key, correlation_id,
                                expires_at, finished_at, error_code, input_tokens, output_tokens, created_at)
SELECT r.id, r.tenant_id, r.agent_id, COALESCE(r.actor_user_id, r.on_behalf_of_user_id), 'reception_turn', r.channel_id,
       CASE r.status WHEN 'succeeded' THEN 'finished' WHEN 'failed' THEN 'failed' WHEN 'cancelled' THEN 'revoked' ELSE 'active' END,
       r.idempotency_key, r.trace_id, COALESCE(r.started_at, r.created_at) + interval '10 minutes',
       r.finished_at, r.error_code, r.input_tokens, r.output_tokens, r.created_at
FROM public.agent_runs r
WHERE COALESCE(r.actor_user_id, r.on_behalf_of_user_id) IS NOT NULL;

ALTER TABLE public.messages DROP CONSTRAINT messages_run_id_fk;
UPDATE public.messages SET run_id = NULL WHERE run_id IS NOT NULL AND NOT EXISTS (SELECT 1 FROM public.delegations d WHERE d.id = messages.run_id);
ALTER TABLE public.messages RENAME COLUMN run_id TO delegation_id;
ALTER INDEX public.messages_run_id_idx RENAME TO messages_delegation_id_idx;
ALTER TABLE public.messages ADD CONSTRAINT messages_delegation_id_fk FOREIGN KEY (tenant_id, delegation_id) REFERENCES public.delegations(tenant_id, id) ON DELETE RESTRICT;

ALTER TABLE public.ticket_assessments DROP CONSTRAINT ticket_assessments_source_run_id_fk;
UPDATE public.ticket_assessments SET source_run_id = NULL WHERE source_run_id IS NOT NULL AND NOT EXISTS (SELECT 1 FROM public.delegations d WHERE d.id = ticket_assessments.source_run_id);
ALTER TABLE public.ticket_assessments RENAME COLUMN source_run_id TO source_delegation_id;
ALTER TABLE public.ticket_assessments ADD CONSTRAINT ticket_assessments_source_delegation_id_fk FOREIGN KEY (tenant_id, source_delegation_id) REFERENCES public.delegations(tenant_id, id) ON DELETE RESTRICT;

-- ===== integration_cases (was agent_teams) =====

CREATE TABLE public.integration_cases (
    id uuid DEFAULT gen_random_uuid() NOT NULL,
    tenant_id uuid NOT NULL,
    workspace_id uuid NOT NULL,
    channel_id text NOT NULL,
    ticket_id uuid,
    request_message_id uuid,
    ticket_generation integer DEFAULT 0 NOT NULL,
    client_id text NOT NULL,
    status text NOT NULL,
    finished_at timestamp with time zone,
    created_at timestamp with time zone DEFAULT now() NOT NULL,
    updated_at timestamp with time zone DEFAULT now() NOT NULL,
    requested_by_user_id text,
    CONSTRAINT integration_cases_pkey PRIMARY KEY (id),
    CONSTRAINT integration_cases_tenant_key_uq UNIQUE (tenant_id, id),
    CONSTRAINT integration_cases_ticket_uq UNIQUE (ticket_id, ticket_generation),
    CONSTRAINT integration_cases_request_uq UNIQUE (workspace_id, request_message_id),
    CONSTRAINT integration_cases_target_check CHECK (num_nonnulls(ticket_id, request_message_id) = 1),
    CONSTRAINT integration_cases_status_check CHECK (status IN ('queued', 'running', 'waiting', 'completed', 'failed', 'cancelled')),
    CONSTRAINT integration_cases_tenant_id_fk FOREIGN KEY (tenant_id) REFERENCES public.tenants(id) ON DELETE RESTRICT,
    CONSTRAINT integration_cases_client_id_fk FOREIGN KEY (tenant_id, client_id) REFERENCES public.integration_clients(tenant_id, id) ON DELETE RESTRICT,
    CONSTRAINT integration_cases_channel_id_fk FOREIGN KEY (tenant_id, channel_id) REFERENCES public.channels(tenant_id, id) ON DELETE RESTRICT,
    CONSTRAINT integration_cases_ticket_id_fk FOREIGN KEY (tenant_id, ticket_id) REFERENCES public.tickets(tenant_id, id) ON DELETE RESTRICT,
    CONSTRAINT integration_cases_request_message_id_fk FOREIGN KEY (tenant_id, request_message_id) REFERENCES public.messages(tenant_id, id) ON DELETE RESTRICT,
    CONSTRAINT integration_cases_workspace_id_fk FOREIGN KEY (tenant_id, workspace_id) REFERENCES public.workspaces(tenant_id, id) ON DELETE RESTRICT,
    CONSTRAINT integration_cases_requested_by_user_id_fk FOREIGN KEY (requested_by_user_id) REFERENCES public.users(id) ON DELETE RESTRICT
);
CREATE INDEX integration_cases_ticket_id_idx ON public.integration_cases (tenant_id, ticket_id);
CREATE INDEX integration_cases_workspace_id_idx ON public.integration_cases (tenant_id, workspace_id);
CREATE INDEX integration_cases_client_idx ON public.integration_cases (tenant_id, client_id, created_at);
ALTER TABLE public.integration_cases ENABLE ROW LEVEL SECURITY;
ALTER TABLE ONLY public.integration_cases FORCE ROW LEVEL SECURITY;
CREATE POLICY integration_cases_tenant_policy ON public.integration_cases
    USING ((tenant_id = (NULLIF(current_setting('app.tenant_id'::text, true), ''::text))::uuid))
    WITH CHECK ((tenant_id = (NULLIF(current_setting('app.tenant_id'::text, true), ''::text))::uuid));
CREATE TRIGGER integration_cases_touch BEFORE UPDATE ON public.integration_cases FOR EACH ROW EXECUTE FUNCTION public.app_touch_updated_at();

INSERT INTO public.integration_cases (id, tenant_id, workspace_id, channel_id, ticket_id, request_message_id, ticket_generation,
                                      client_id, status, finished_at, created_at, updated_at, requested_by_user_id)
SELECT id, tenant_id, workspace_id, channel_id, ticket_id, request_message_id, ticket_generation,
       supervisor_agent_id, status, finished_at, created_at, updated_at, requested_by_user_id
FROM public.agent_teams;

ALTER TABLE public.ticket_routing_history DROP CONSTRAINT ticket_routing_history_team_id_fk;
ALTER TABLE public.ticket_routing_history ADD CONSTRAINT ticket_routing_history_team_id_fk FOREIGN KEY (tenant_id, team_id) REFERENCES public.integration_cases(tenant_id, id) ON DELETE RESTRICT;
ALTER TABLE public.tickets DROP CONSTRAINT tickets_assigned_team_id_fk;
ALTER TABLE public.tickets ADD CONSTRAINT tickets_assigned_team_id_fk FOREIGN KEY (tenant_id, assigned_team_id) REFERENCES public.integration_cases(tenant_id, id) ON DELETE RESTRICT;
ALTER TABLE public.vh_reception_supervisor_messages DROP CONSTRAINT vh_reception_supervisor_messages_team_id_fk;
ALTER TABLE public.vh_reception_supervisor_messages ADD CONSTRAINT vh_reception_supervisor_messages_team_id_fk FOREIGN KEY (tenant_id, team_id) REFERENCES public.integration_cases(tenant_id, id) ON DELETE RESTRICT;
ALTER TABLE public.vh_reception_supervisor_pending DROP CONSTRAINT vh_reception_supervisor_pending_team_id_fk;
ALTER TABLE public.vh_reception_supervisor_pending ADD CONSTRAINT vh_reception_supervisor_pending_team_id_fk FOREIGN KEY (tenant_id, team_id) REFERENCES public.integration_cases(tenant_id, id) ON DELETE RESTRICT;

-- ===== drop the agent-shaped tables, their functions and the enum =====

ALTER TABLE public.runtime_session_bindings DROP CONSTRAINT runtime_session_bindings_team_member_id_fk;
DROP TABLE public.agent_runs;
DROP TABLE public.team_members;
DROP TABLE public.runtime_session_bindings;
DROP TABLE public.runtime_identities;
DROP TABLE public.runtime_backends;
DROP TABLE public.channel_agents;
DROP TABLE public.agent_releases;
DROP TABLE public.agent_versions;
DROP TABLE public.agent_teams;
DROP TABLE public.agents;
DROP FUNCTION public.app_agent_version_scope();
DROP FUNCTION public.app_validate_runtime_binding();
DROP TYPE public.agent_type;

-- ===== a cursor for the events a client reads =====
-- The outbox carried only ticket events (event_id pointed at ticket_events). Announcements, passes and
-- deadlines are events too, so event_id becomes a plain id and the topic says what it is.

ALTER TABLE public.event_outbox DROP CONSTRAINT event_outbox_event_id_fk;

ALTER TABLE public.event_outbox ADD COLUMN seq bigint GENERATED ALWAYS AS IDENTITY;
CREATE UNIQUE INDEX event_outbox_seq_uq ON public.event_outbox (tenant_id, seq);
-- One warning of a kind per ticket: a producer that runs twice must not tell a client twice.
ALTER TABLE public.event_outbox ADD COLUMN dedupe_key text;
CREATE UNIQUE INDEX event_outbox_dedupe_uq ON public.event_outbox (tenant_id, dedupe_key) WHERE dedupe_key IS NOT NULL;
