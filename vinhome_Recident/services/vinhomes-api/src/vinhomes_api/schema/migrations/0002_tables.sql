-- Domain Vinhomes database. Generated once from the running schema, then kept by hand.
-- Every table has tenant_id and row level security that is forced; the API runs as a role that cannot bypass it.

--
--

--
-- Name: access_scopes; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.access_scopes (
    id uuid DEFAULT gen_random_uuid() NOT NULL,
    tenant_id uuid NOT NULL,
    kind text NOT NULL,
    management_unit_id uuid,
    site_id uuid,
    zone_id uuid,
    building_id uuid,
    created_at timestamp with time zone DEFAULT now() NOT NULL,
    updated_at timestamp with time zone DEFAULT now() NOT NULL,
    CONSTRAINT access_scopes_check_0 CHECK ((kind = ANY (ARRAY['tenant'::text, 'management'::text, 'site'::text, 'zone'::text, 'building'::text])))
);

ALTER TABLE ONLY public.access_scopes FORCE ROW LEVEL SECURITY;

--
-- Name: account_reviews; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.account_reviews (
    id uuid DEFAULT gen_random_uuid() NOT NULL,
    tenant_id uuid NOT NULL,
    user_id text NOT NULL,
    action text NOT NULL,
    from_status text,
    to_status text NOT NULL,
    reason text,
    reviewer_user_id text,
    decided_at timestamp with time zone,
    created_at timestamp with time zone DEFAULT now() NOT NULL,
    CONSTRAINT account_reviews_check_0 CHECK ((action = ANY (ARRAY['register'::text, 'approve'::text, 'reject'::text, 'activate'::text, 'suspend'::text, 'delete'::text])))
);

ALTER TABLE ONLY public.account_reviews FORCE ROW LEVEL SECURITY;

--
-- Name: accounts; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.accounts (
    id text NOT NULL,
    account_id text NOT NULL,
    provider_id text NOT NULL,
    issuer text,
    user_id text NOT NULL,
    access_token text,
    refresh_token text,
    id_token text,
    access_token_expires_at timestamp with time zone,
    refresh_token_expires_at timestamp with time zone,
    scope text,
    password text,
    created_at timestamp with time zone DEFAULT now() NOT NULL,
    updated_at timestamp with time zone DEFAULT now() NOT NULL
);

--
-- Name: agent_releases; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.agent_releases (
    id uuid DEFAULT gen_random_uuid() NOT NULL,
    tenant_id uuid NOT NULL,
    agent_id text NOT NULL,
    version_id uuid NOT NULL,
    status text NOT NULL,
    published_by text,
    published_at timestamp with time zone,
    revoked_at timestamp with time zone,
    created_at timestamp with time zone DEFAULT now() NOT NULL,
    updated_at timestamp with time zone DEFAULT now() NOT NULL,
    CONSTRAINT agent_releases_check_0 CHECK ((status = ANY (ARRAY['draft'::text, 'published'::text, 'revoked'::text])))
);

ALTER TABLE ONLY public.agent_releases FORCE ROW LEVEL SECURITY;

--
-- Name: agent_runs; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.agent_runs (
    id uuid DEFAULT gen_random_uuid() NOT NULL,
    tenant_id uuid NOT NULL,
    channel_id text NOT NULL,
    agent_id text NOT NULL,
    version_id uuid NOT NULL,
    team_member_id uuid,
    actor_user_id text,
    parent_run_id uuid,
    trigger_event_id uuid,
    idempotency_key text NOT NULL,
    status text NOT NULL,
    started_at timestamp with time zone,
    finished_at timestamp with time zone,
    error_code text,
    input_tokens bigint DEFAULT 0 NOT NULL,
    output_tokens bigint DEFAULT 0 NOT NULL,
    estimated_cost numeric(18,6) DEFAULT '0'::numeric NOT NULL,
    trace_id text NOT NULL,
    created_at timestamp with time zone DEFAULT now() NOT NULL,
    updated_at timestamp with time zone DEFAULT now() NOT NULL,
    binding_id uuid NOT NULL,
    authority_principal_id uuid NOT NULL,
    on_behalf_of_user_id text,
    policy_version text NOT NULL,
    authority_version bigint NOT NULL,
    CONSTRAINT agent_runs_check_0 CHECK ((status = ANY (ARRAY['queued'::text, 'running'::text, 'interrupted'::text, 'succeeded'::text, 'failed'::text, 'cancelled'::text])))
);

ALTER TABLE ONLY public.agent_runs FORCE ROW LEVEL SECURITY;

--
-- Name: agent_teams; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.agent_teams (
    id uuid DEFAULT gen_random_uuid() NOT NULL,
    tenant_id uuid NOT NULL,
    workspace_id uuid NOT NULL,
    channel_id text NOT NULL,
    ticket_id uuid,
    request_message_id uuid,
    ticket_generation integer DEFAULT 0 NOT NULL,
    supervisor_agent_id text NOT NULL,
    status text NOT NULL,
    shared_state jsonb NOT NULL,
    state_version bigint DEFAULT 0 NOT NULL,
    finished_at timestamp with time zone,
    created_at timestamp with time zone DEFAULT now() NOT NULL,
    updated_at timestamp with time zone DEFAULT now() NOT NULL,
    requested_by_user_id text,
    CONSTRAINT agent_teams_check_0 CHECK ((num_nonnulls(ticket_id, request_message_id) = 1)),
    CONSTRAINT agent_teams_check_1 CHECK ((status = ANY (ARRAY['queued'::text, 'running'::text, 'waiting'::text, 'completed'::text, 'failed'::text, 'cancelled'::text])))
);

ALTER TABLE ONLY public.agent_teams FORCE ROW LEVEL SECURITY;

--
-- Name: agent_versions; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.agent_versions (
    id uuid DEFAULT gen_random_uuid() NOT NULL,
    tenant_id uuid NOT NULL,
    agent_id text NOT NULL,
    version_no integer NOT NULL,
    runtime text NOT NULL,
    framework_version text NOT NULL,
    instructions text NOT NULL,
    config jsonb NOT NULL,
    config_hash text NOT NULL,
    created_by text NOT NULL,
    created_at timestamp with time zone DEFAULT now() NOT NULL,
    CONSTRAINT agent_versions_check_0 CHECK ((runtime = ANY (ARRAY['langgraph'::text, 'agentscope'::text, 'remote'::text])))
);

ALTER TABLE ONLY public.agent_versions FORCE ROW LEVEL SECURITY;

--
-- Name: agents; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.agents (
    id text NOT NULL,
    name text NOT NULL,
    type public.agent_type NOT NULL,
    configuration jsonb NOT NULL,
    override jsonb,
    created_at timestamp with time zone DEFAULT now() NOT NULL,
    updated_at timestamp with time zone DEFAULT now() NOT NULL,
    tenant_id uuid DEFAULT (NULLIF(current_setting('app.tenant_id'::text, true), ''::text))::uuid NOT NULL,
    workspace_id uuid DEFAULT (NULLIF(current_setting('app.workspace_id'::text, true), ''::text))::uuid,
    purpose text DEFAULT 'specialist'::text NOT NULL,
    status text DEFAULT 'active'::text NOT NULL,
    CONSTRAINT agents_check_0 CHECK ((((purpose = 'reception'::text) AND (workspace_id IS NULL)) OR ((purpose = ANY (ARRAY['supervisor'::text, 'specialist'::text])) AND (workspace_id IS NOT NULL)))),
    CONSTRAINT agents_check_1 CHECK ((purpose = ANY (ARRAY['reception'::text, 'supervisor'::text, 'specialist'::text]))),
    CONSTRAINT agents_check_2 CHECK ((status = ANY (ARRAY['draft'::text, 'active'::text, 'archived'::text])))
);

ALTER TABLE ONLY public.agents FORCE ROW LEVEL SECURITY;

--
-- Name: audit_events; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.audit_events (
    id uuid DEFAULT gen_random_uuid() NOT NULL,
    actor_user_id text,
    initiator_kind text DEFAULT 'person'::text NOT NULL,
    initiator_id text,
    event_type text NOT NULL,
    target_type text NOT NULL,
    target_id text,
    payload jsonb NOT NULL,
    created_at timestamp with time zone DEFAULT now() NOT NULL,
    tenant_id uuid,
    workspace_id uuid,
    request_id text,
    correlation_id uuid,
    actor_snapshot jsonb DEFAULT '{}'::jsonb NOT NULL
);

ALTER TABLE ONLY public.audit_events FORCE ROW LEVEL SECURITY;

--
-- Name: buildings; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.buildings (
    id uuid DEFAULT gen_random_uuid() NOT NULL,
    tenant_id uuid NOT NULL,
    site_id uuid NOT NULL,
    zone_id uuid,
    code text NOT NULL,
    name text NOT NULL,
    status text NOT NULL,
    created_at timestamp with time zone DEFAULT now() NOT NULL,
    updated_at timestamp with time zone DEFAULT now() NOT NULL
);

ALTER TABLE ONLY public.buildings FORCE ROW LEVEL SECURITY;

--
-- Name: channel_agents; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.channel_agents (
    channel_id text NOT NULL,
    agent_id text NOT NULL,
    created_at timestamp with time zone DEFAULT now() NOT NULL,
    tenant_id uuid DEFAULT (NULLIF(current_setting('app.tenant_id'::text, true), ''::text))::uuid NOT NULL
);

ALTER TABLE ONLY public.channel_agents FORCE ROW LEVEL SECURITY;

--
-- Name: channel_memberships; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.channel_memberships (
    channel_id text NOT NULL,
    user_id text NOT NULL,
    pinned_at timestamp with time zone,
    last_read_at timestamp with time zone,
    created_at timestamp with time zone DEFAULT now() NOT NULL,
    tenant_id uuid DEFAULT (NULLIF(current_setting('app.tenant_id'::text, true), ''::text))::uuid NOT NULL,
    last_read_seq bigint DEFAULT 0 NOT NULL
);

ALTER TABLE ONLY public.channel_memberships FORCE ROW LEVEL SECURITY;

--
-- Name: channels; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.channels (
    id text NOT NULL,
    name text NOT NULL,
    description text NOT NULL,
    suggested_prompts text[] DEFAULT '{}'::text[] NOT NULL,
    allowed_groups text[] DEFAULT '{}'::text[] NOT NULL,
    override jsonb,
    summary text,
    summary_at timestamp with time zone,
    last_message text,
    last_message_at timestamp with time zone,
    last_message_agent_id text,
    deleted_at timestamp with time zone,
    created_at timestamp with time zone DEFAULT now() NOT NULL,
    updated_at timestamp with time zone DEFAULT now() NOT NULL,
    tenant_id uuid DEFAULT (NULLIF(current_setting('app.tenant_id'::text, true), ''::text))::uuid NOT NULL,
    workspace_id uuid DEFAULT (NULLIF(current_setting('app.workspace_id'::text, true), ''::text))::uuid,
    kind text DEFAULT 'management'::text NOT NULL,
    created_by text,
    is_dispatch_default boolean DEFAULT false NOT NULL,
    next_message_seq bigint DEFAULT 1 NOT NULL,
    CONSTRAINT channels_check_0 CHECK ((((kind = 'reception'::text) AND (workspace_id IS NULL)) OR ((kind = ANY (ARRAY['management'::text, 'agent_builder'::text, 'personal'::text])) AND (workspace_id IS NOT NULL)))),
    CONSTRAINT channels_check_1 CHECK ((kind = ANY (ARRAY['reception'::text, 'management'::text, 'agent_builder'::text, 'personal'::text])))
);

ALTER TABLE ONLY public.channels FORCE ROW LEVEL SECURITY;

--
-- Name: dispatch_attempts; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.dispatch_attempts (
    id uuid DEFAULT gen_random_uuid() NOT NULL,
    tenant_id uuid NOT NULL,
    queue_id uuid NOT NULL,
    work_order_id uuid NOT NULL,
    decision_id uuid NOT NULL,
    queue_version bigint NOT NULL,
    fencing_token bigint NOT NULL,
    worker_id text NOT NULL,
    priority_rank_snapshot integer NOT NULL,
    emergency_snapshot boolean NOT NULL,
    status text NOT NULL,
    claimed_at timestamp with time zone NOT NULL,
    lease_until timestamp with time zone NOT NULL,
    assignment_id uuid,
    finished_at timestamp with time zone,
    reason text,
    idempotency_key text NOT NULL,
    created_at timestamp with time zone DEFAULT now() NOT NULL,
    updated_at timestamp with time zone DEFAULT now() NOT NULL,
    CONSTRAINT dispatch_attempts_check_0 CHECK ((priority_rank_snapshot = ANY (ARRAY[10, 20, 30, 40]))),
    CONSTRAINT dispatch_attempts_check_1 CHECK (((status <> 'offered'::text) OR (assignment_id IS NOT NULL))),
    CONSTRAINT dispatch_attempts_check_2 CHECK ((status = ANY (ARRAY['claimed'::text, 'offered'::text, 'no_capacity'::text, 'stale'::text, 'expired'::text, 'failed'::text])))
);

ALTER TABLE ONLY public.dispatch_attempts FORCE ROW LEVEL SECURITY;

--
-- Name: dispatch_queue; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.dispatch_queue (
    id uuid DEFAULT gen_random_uuid() NOT NULL,
    tenant_id uuid NOT NULL,
    work_order_id uuid NOT NULL,
    management_unit_id uuid NOT NULL,
    category_id uuid NOT NULL,
    queued_at timestamp with time zone NOT NULL,
    available_at timestamp with time zone NOT NULL,
    state text NOT NULL,
    attempts integer DEFAULT 0 NOT NULL,
    lease_owner text,
    lease_until timestamp with time zone,
    created_at timestamp with time zone DEFAULT now() NOT NULL,
    updated_at timestamp with time zone DEFAULT now() NOT NULL,
    priority_decision_id uuid NOT NULL,
    priority_rank integer NOT NULL,
    is_emergency boolean NOT NULL,
    dispatch_due_at timestamp with time zone,
    eligible_since timestamp with time zone NOT NULL,
    version bigint DEFAULT 0 NOT NULL,
    fencing_token bigint DEFAULT 0 NOT NULL,
    CONSTRAINT dispatch_queue_check_0 CHECK ((priority_rank = ANY (ARRAY[10, 20, 30, 40]))),
    CONSTRAINT dispatch_queue_check_1 CHECK (((NOT is_emergency) OR (priority_rank = 40))),
    CONSTRAINT dispatch_queue_check_2 CHECK ((state = ANY (ARRAY['waiting'::text, 'claimed'::text, 'dispatched'::text, 'cancelled'::text, 'dead'::text])))
);

ALTER TABLE ONLY public.dispatch_queue FORCE ROW LEVEL SECURITY;

--
-- Name: domains; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.domains (
    id uuid DEFAULT gen_random_uuid() NOT NULL,
    tenant_id uuid NOT NULL,
    code text NOT NULL,
    name text NOT NULL,
    description text,
    status text NOT NULL,
    created_at timestamp with time zone DEFAULT now() NOT NULL,
    updated_at timestamp with time zone DEFAULT now() NOT NULL
);

ALTER TABLE ONLY public.domains FORCE ROW LEVEL SECURITY;

--
-- Name: event_inbox; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.event_inbox (
    id uuid DEFAULT gen_random_uuid() NOT NULL,
    tenant_id uuid NOT NULL,
    consumer text NOT NULL,
    event_id uuid NOT NULL,
    status text NOT NULL,
    attempts integer DEFAULT 0 NOT NULL,
    available_at timestamp with time zone NOT NULL,
    lease_owner text,
    lease_until timestamp with time zone,
    processed_at timestamp with time zone,
    last_error text,
    created_at timestamp with time zone DEFAULT now() NOT NULL,
    updated_at timestamp with time zone DEFAULT now() NOT NULL,
    CONSTRAINT event_inbox_check_0 CHECK ((status = ANY (ARRAY['pending'::text, 'processing'::text, 'done'::text, 'dead'::text])))
);

ALTER TABLE ONLY public.event_inbox FORCE ROW LEVEL SECURITY;

--
-- Name: event_outbox; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.event_outbox (
    id uuid DEFAULT gen_random_uuid() NOT NULL,
    tenant_id uuid NOT NULL,
    event_id uuid NOT NULL,
    topic text NOT NULL,
    payload jsonb NOT NULL,
    schema_version integer NOT NULL,
    available_at timestamp with time zone NOT NULL,
    published_at timestamp with time zone,
    attempts integer DEFAULT 0 NOT NULL,
    lease_owner text,
    lease_until timestamp with time zone,
    last_error text,
    created_at timestamp with time zone DEFAULT now() NOT NULL
);

ALTER TABLE ONLY public.event_outbox FORCE ROW LEVEL SECURITY;

--
-- Name: evidence_items; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.evidence_items (
    id uuid DEFAULT gen_random_uuid() NOT NULL,
    tenant_id uuid NOT NULL,
    ticket_id uuid NOT NULL,
    work_order_id uuid,
    assignment_id uuid,
    file_id uuid NOT NULL,
    purpose text NOT NULL,
    captured_at timestamp with time zone,
    uploaded_at timestamp with time zone NOT NULL,
    uploaded_by text NOT NULL,
    caption text,
    provenance text NOT NULL,
    supersedes_id uuid,
    status text NOT NULL,
    withdrawn_reason text,
    created_at timestamp with time zone DEFAULT now() NOT NULL,
    updated_at timestamp with time zone DEFAULT now() NOT NULL,
    CONSTRAINT evidence_items_check_0 CHECK ((purpose = ANY (ARRAY['issue'::text, 'before'::text, 'after'::text, 'verification'::text]))),
    CONSTRAINT evidence_items_check_1 CHECK ((provenance = ANY (ARRAY['camera'::text, 'upload'::text, 'import'::text]))),
    CONSTRAINT evidence_items_check_2 CHECK ((status = ANY (ARRAY['active'::text, 'withdrawn'::text])))
);

ALTER TABLE ONLY public.evidence_items FORCE ROW LEVEL SECURITY;

--
-- Name: execution_principals; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.execution_principals (
    id uuid DEFAULT gen_random_uuid() NOT NULL,
    tenant_id uuid NOT NULL,
    kind text NOT NULL,
    user_id text,
    workspace_id uuid,
    status text NOT NULL,
    authz_version bigint DEFAULT 1 NOT NULL,
    created_at timestamp with time zone DEFAULT now() NOT NULL,
    updated_at timestamp with time zone DEFAULT now() NOT NULL,
    CONSTRAINT execution_principals_check_0 CHECK ((((kind = 'user'::text) AND (user_id IS NOT NULL) AND (workspace_id IS NULL)) OR ((kind = 'workspace_service'::text) AND (user_id IS NULL) AND (workspace_id IS NOT NULL)))),
    CONSTRAINT execution_principals_check_1 CHECK ((kind = ANY (ARRAY['user'::text, 'workspace_service'::text]))),
    CONSTRAINT execution_principals_check_2 CHECK ((status = ANY (ARRAY['active'::text, 'suspended'::text, 'revoked'::text])))
);

ALTER TABLE ONLY public.execution_principals FORCE ROW LEVEL SECURITY;

--
-- Name: file_objects; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.file_objects (
    id uuid DEFAULT gen_random_uuid() NOT NULL,
    tenant_id uuid NOT NULL,
    file_id uuid NOT NULL,
    location_id uuid NOT NULL,
    object_key text NOT NULL,
    version_id text NOT NULL,
    variant text NOT NULL,
    variant_revision integer DEFAULT 1 NOT NULL,
    source_object_id uuid,
    mime_type text NOT NULL,
    size_bytes bigint NOT NULL,
    sha256 text NOT NULL,
    etag text,
    checksum_algorithm text,
    checksum_value text,
    checksum_type text,
    width_px integer,
    height_px integer,
    scan_status text NOT NULL,
    verified_at timestamp with time zone,
    encryption_mode text NOT NULL,
    kms_key_ref text,
    object_retain_until timestamp with time zone,
    object_legal_hold boolean DEFAULT false NOT NULL,
    status text NOT NULL,
    created_at timestamp with time zone DEFAULT now() NOT NULL,
    updated_at timestamp with time zone DEFAULT now() NOT NULL,
    CONSTRAINT file_objects_check_0 CHECK ((size_bytes >= 0)),
    CONSTRAINT file_objects_check_1 CHECK ((sha256 ~ '^[0-9a-f]{64}$'::text)),
    CONSTRAINT file_objects_check_2 CHECK ((variant_revision > 0)),
    CONSTRAINT file_objects_check_3 CHECK (((variant = 'original'::text) OR (source_object_id IS NOT NULL))),
    CONSTRAINT file_objects_check_4 CHECK (((status <> 'ready'::text) OR ((scan_status = 'clean'::text) AND (verified_at IS NOT NULL)))),
    CONSTRAINT file_objects_check_5 CHECK (((version_id <> ''::text) AND (version_id <> 'null'::text))),
    CONSTRAINT file_objects_check_6 CHECK ((variant = ANY (ARRAY['original'::text, 'thumbnail'::text, 'redacted'::text, 'preview'::text]))),
    CONSTRAINT file_objects_check_7 CHECK ((scan_status = ANY (ARRAY['pending'::text, 'clean'::text, 'infected'::text, 'failed'::text]))),
    CONSTRAINT file_objects_check_8 CHECK ((status = ANY (ARRAY['verifying'::text, 'ready'::text, 'rejected'::text, 'deletion_pending'::text, 'deleted'::text, 'missing'::text])))
);

ALTER TABLE ONLY public.file_objects FORCE ROW LEVEL SECURITY;

--
-- Name: file_uploads; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.file_uploads (
    id uuid DEFAULT gen_random_uuid() NOT NULL,
    tenant_id uuid NOT NULL,
    file_id uuid NOT NULL,
    requested_by text NOT NULL,
    location_id uuid NOT NULL,
    staging_key text NOT NULL,
    source_version_id text,
    upload_mode text NOT NULL,
    multipart_upload_id text,
    expected_size_bytes bigint NOT NULL,
    expected_sha256 text,
    allowed_mime_types text[] NOT NULL,
    max_size_bytes bigint NOT NULL,
    status text NOT NULL,
    idempotency_key text NOT NULL,
    expires_at timestamp with time zone NOT NULL,
    finalized_at timestamp with time zone,
    result_object_id uuid,
    failure_code text,
    created_at timestamp with time zone DEFAULT now() NOT NULL,
    updated_at timestamp with time zone DEFAULT now() NOT NULL,
    CONSTRAINT file_uploads_check_0 CHECK (((expected_size_bytes > 0) AND (expected_size_bytes <= max_size_bytes))),
    CONSTRAINT file_uploads_check_1 CHECK (((upload_mode <> 'multipart'::text) OR (multipart_upload_id IS NOT NULL))),
    CONSTRAINT file_uploads_check_2 CHECK ((upload_mode = ANY (ARRAY['single'::text, 'multipart'::text]))),
    CONSTRAINT file_uploads_check_3 CHECK ((status = ANY (ARRAY['issued'::text, 'uploading'::text, 'uploaded'::text, 'verifying'::text, 'accepted'::text, 'rejected'::text, 'expired'::text, 'aborted'::text])))
);

ALTER TABLE ONLY public.file_uploads FORCE ROW LEVEL SECURITY;

--
-- Name: files; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.files (
    id uuid DEFAULT gen_random_uuid() NOT NULL,
    tenant_id uuid NOT NULL,
    uploaded_by text,
    original_name text NOT NULL,
    retention_until timestamp with time zone,
    deleted_at timestamp with time zone,
    created_at timestamp with time zone DEFAULT now() NOT NULL,
    updated_at timestamp with time zone DEFAULT now() NOT NULL,
    owner_principal_id uuid NOT NULL,
    scope_kind text NOT NULL,
    ticket_id uuid,
    channel_id text,
    status text NOT NULL,
    accepted_object_id uuid,
    declared_mime_type text,
    legal_hold boolean DEFAULT false NOT NULL,
    unit_id uuid,
    CONSTRAINT files_check_0 CHECK ((num_nonnulls(ticket_id, channel_id, unit_id) = 1)),
    CONSTRAINT files_check_1 CHECK ((((scope_kind = 'ticket'::text) AND (ticket_id IS NOT NULL)) OR ((scope_kind = 'channel'::text) AND (channel_id IS NOT NULL)) OR ((scope_kind = 'resident'::text) AND (unit_id IS NOT NULL)))),
    CONSTRAINT files_check_2 CHECK (((status <> 'ready'::text) OR (accepted_object_id IS NOT NULL))),
    CONSTRAINT files_check_3 CHECK ((scope_kind = ANY (ARRAY['ticket'::text, 'channel'::text, 'resident'::text]))),
    CONSTRAINT files_check_4 CHECK ((status = ANY (ARRAY['staged'::text, 'verifying'::text, 'ready'::text, 'rejected'::text, 'deletion_pending'::text, 'deleted'::text, 'missing'::text])))
);

ALTER TABLE ONLY public.files FORCE ROW LEVEL SECURITY;

--
-- Name: incident_types; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.incident_types (
    id uuid DEFAULT gen_random_uuid() NOT NULL,
    tenant_id uuid NOT NULL,
    category_id uuid NOT NULL,
    code text NOT NULL,
    name text NOT NULL,
    default_priority text NOT NULL,
    requires_visit boolean NOT NULL,
    created_at timestamp with time zone DEFAULT now() NOT NULL,
    updated_at timestamp with time zone DEFAULT now() NOT NULL
);

ALTER TABLE ONLY public.incident_types FORCE ROW LEVEL SECURITY;

--
-- Name: interruption_scopes; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.interruption_scopes (
    tenant_id uuid NOT NULL,
    interruption_id uuid NOT NULL,
    scope_id uuid NOT NULL,
    created_at timestamp with time zone DEFAULT now() NOT NULL
);

ALTER TABLE ONLY public.interruption_scopes FORCE ROW LEVEL SECURITY;

--
-- Name: invoice_lines; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.invoice_lines (
    id uuid DEFAULT gen_random_uuid() NOT NULL,
    tenant_id uuid NOT NULL,
    invoice_id uuid NOT NULL,
    line_no integer NOT NULL,
    category_id uuid NOT NULL,
    description text NOT NULL,
    quantity numeric(12,3) NOT NULL,
    unit_price numeric(18,2) NOT NULL,
    discount numeric(18,2) DEFAULT '0'::numeric NOT NULL,
    tax_rate numeric(9,4) DEFAULT '0'::numeric NOT NULL,
    net_amount numeric(18,2) NOT NULL,
    tax_amount numeric(18,2) NOT NULL,
    total_amount numeric(18,2) NOT NULL,
    created_at timestamp with time zone DEFAULT now() NOT NULL,
    updated_at timestamp with time zone DEFAULT now() NOT NULL,
    CONSTRAINT invoice_lines_check_0 CHECK (((quantity > (0)::numeric) AND (unit_price >= (0)::numeric))),
    CONSTRAINT invoice_lines_check_1 CHECK (((tax_rate >= (0)::numeric) AND (tax_rate <= (1)::numeric))),
    CONSTRAINT invoice_lines_check_2 CHECK ((discount >= (0)::numeric)),
    CONSTRAINT invoice_lines_check_3 CHECK ((total_amount = (net_amount + tax_amount)))
);

ALTER TABLE ONLY public.invoice_lines FORCE ROW LEVEL SECURITY;

--
-- Name: invoices; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.invoices (
    id uuid DEFAULT gen_random_uuid() NOT NULL,
    tenant_id uuid NOT NULL,
    ticket_id uuid NOT NULL,
    work_order_id uuid,
    invoice_no text NOT NULL,
    issued_by_staff_id uuid NOT NULL,
    bill_to_user_id text NOT NULL,
    status text NOT NULL,
    currency character(3) DEFAULT 'VND'::bpchar NOT NULL,
    subtotal numeric(18,2) NOT NULL,
    tax_total numeric(18,2) NOT NULL,
    discount_total numeric(18,2) DEFAULT '0'::numeric NOT NULL,
    grand_total numeric(18,2) NOT NULL,
    issued_at timestamp with time zone,
    due_at timestamp with time zone,
    provider text,
    provider_invoice_id text,
    legal_invoice_file_id uuid,
    supersedes_invoice_id uuid,
    created_at timestamp with time zone DEFAULT now() NOT NULL,
    updated_at timestamp with time zone DEFAULT now() NOT NULL,
    provider_account_ref text,
    CONSTRAINT invoices_check_0 CHECK ((grand_total = ((subtotal + tax_total) - discount_total))),
    CONSTRAINT invoices_check_1 CHECK ((grand_total >= (0)::numeric)),
    CONSTRAINT invoices_check_2 CHECK ((status = ANY (ARRAY['draft'::text, 'issued'::text, 'void'::text, 'replaced'::text])))
);

ALTER TABLE ONLY public.invoices FORCE ROW LEVEL SECURITY;

--
-- Name: management_coverage; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.management_coverage (
    id uuid DEFAULT gen_random_uuid() NOT NULL,
    tenant_id uuid NOT NULL,
    management_unit_id uuid NOT NULL,
    scope_id uuid NOT NULL,
    service_category_id uuid NOT NULL,
    valid_from timestamp with time zone NOT NULL,
    valid_to timestamp with time zone,
    priority integer DEFAULT 0 NOT NULL,
    created_at timestamp with time zone DEFAULT now() NOT NULL,
    updated_at timestamp with time zone DEFAULT now() NOT NULL
);

ALTER TABLE ONLY public.management_coverage FORCE ROW LEVEL SECURITY;

--
-- Name: management_units; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.management_units (
    id uuid DEFAULT gen_random_uuid() NOT NULL,
    tenant_id uuid NOT NULL,
    code text NOT NULL,
    name text NOT NULL,
    status text NOT NULL,
    contact_phone text,
    contact_email text,
    created_at timestamp with time zone DEFAULT now() NOT NULL,
    updated_at timestamp with time zone DEFAULT now() NOT NULL
);

ALTER TABLE ONLY public.management_units FORCE ROW LEVEL SECURITY;

--
-- Name: message_files; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.message_files (
    tenant_id uuid NOT NULL,
    message_id uuid NOT NULL,
    file_id uuid NOT NULL,
    ordinal integer DEFAULT 0 NOT NULL,
    created_at timestamp with time zone DEFAULT now() NOT NULL
);

ALTER TABLE ONLY public.message_files FORCE ROW LEVEL SECURITY;

--
-- Name: messages; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.messages (
    id uuid DEFAULT gen_random_uuid() NOT NULL,
    tenant_id uuid NOT NULL,
    channel_id text NOT NULL,
    seq bigint NOT NULL,
    sender_kind text NOT NULL,
    sender_user_id text,
    sender_agent_id text,
    run_id uuid,
    reply_to_id uuid,
    visibility text NOT NULL,
    body jsonb NOT NULL,
    client_message_id text,
    source_event_id uuid,
    created_at timestamp with time zone DEFAULT now() NOT NULL,
    CONSTRAINT messages_check_0 CHECK ((visibility = ANY (ARRAY['room'::text, 'internal'::text, 'customer'::text])))
);

ALTER TABLE ONLY public.messages FORCE ROW LEVEL SECURITY;

--
-- Name: notification_deliveries; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.notification_deliveries (
    id uuid DEFAULT gen_random_uuid() NOT NULL,
    tenant_id uuid NOT NULL,
    user_id text NOT NULL,
    ticket_event_id uuid,
    message_id uuid,
    interruption_id uuid,
    channel text NOT NULL,
    dedupe_key text NOT NULL,
    payload jsonb NOT NULL,
    status text NOT NULL,
    attempts integer DEFAULT 0 NOT NULL,
    available_at timestamp with time zone NOT NULL,
    sent_at timestamp with time zone,
    read_at timestamp with time zone,
    provider_message_id text,
    last_error text,
    created_at timestamp with time zone DEFAULT now() NOT NULL,
    updated_at timestamp with time zone DEFAULT now() NOT NULL,
    CONSTRAINT notification_deliveries_check_0 CHECK ((channel = ANY (ARRAY['in_app'::text, 'push'::text, 'sms'::text, 'email'::text]))),
    CONSTRAINT notification_deliveries_check_1 CHECK ((status = ANY (ARRAY['pending'::text, 'sent'::text, 'failed'::text, 'dead'::text])))
);

ALTER TABLE ONLY public.notification_deliveries FORCE ROW LEVEL SECURITY;

--
-- Name: payment_allocations; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.payment_allocations (
    id uuid DEFAULT gen_random_uuid() NOT NULL,
    tenant_id uuid NOT NULL,
    payment_id uuid NOT NULL,
    invoice_id uuid NOT NULL,
    amount numeric(18,2) NOT NULL,
    allocated_at timestamp with time zone NOT NULL,
    idempotency_key text NOT NULL,
    created_at timestamp with time zone DEFAULT now() NOT NULL,
    CONSTRAINT payment_allocations_check_0 CHECK ((amount > (0)::numeric))
);

ALTER TABLE ONLY public.payment_allocations FORCE ROW LEVEL SECURITY;

--
-- Name: payment_intents; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.payment_intents (
    id uuid DEFAULT gen_random_uuid() NOT NULL,
    tenant_id uuid NOT NULL,
    invoice_id uuid NOT NULL,
    provider text NOT NULL,
    merchant_account_ref text NOT NULL,
    provider_intent_id text,
    idempotency_key text NOT NULL,
    amount numeric(18,2) NOT NULL,
    currency character(3) NOT NULL,
    status text NOT NULL,
    qr_payload_ciphertext text,
    expires_at timestamp with time zone NOT NULL,
    paid_at timestamp with time zone,
    created_at timestamp with time zone DEFAULT now() NOT NULL,
    updated_at timestamp with time zone DEFAULT now() NOT NULL,
    CONSTRAINT payment_intents_check_0 CHECK ((status = ANY (ARRAY['created'::text, 'pending'::text, 'succeeded'::text, 'expired'::text, 'cancelled'::text, 'failed'::text])))
);

ALTER TABLE ONLY public.payment_intents FORCE ROW LEVEL SECURITY;

--
-- Name: payment_webhook_receipts; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.payment_webhook_receipts (
    id uuid DEFAULT gen_random_uuid() NOT NULL,
    tenant_id uuid NOT NULL,
    provider text NOT NULL,
    merchant_account_ref text NOT NULL,
    provider_event_id text NOT NULL,
    raw_body_hash text NOT NULL,
    signature_valid boolean NOT NULL,
    received_at timestamp with time zone NOT NULL,
    payload_redacted jsonb NOT NULL,
    intent_id uuid,
    created_at timestamp with time zone DEFAULT now() NOT NULL
);

ALTER TABLE ONLY public.payment_webhook_receipts FORCE ROW LEVEL SECURITY;

--
-- Name: payments; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.payments (
    id uuid DEFAULT gen_random_uuid() NOT NULL,
    tenant_id uuid NOT NULL,
    invoice_id uuid NOT NULL,
    intent_id uuid NOT NULL,
    receipt_id uuid,
    provider text NOT NULL,
    merchant_account_ref text NOT NULL,
    provider_transaction_id text NOT NULL,
    amount numeric(18,2) NOT NULL,
    currency character(3) NOT NULL,
    settled_at timestamp with time zone NOT NULL,
    reconciliation_status text NOT NULL,
    created_at timestamp with time zone DEFAULT now() NOT NULL,
    CONSTRAINT payments_check_0 CHECK ((amount > (0)::numeric)),
    CONSTRAINT payments_check_1 CHECK ((reconciliation_status = ANY (ARRAY['confirmed'::text, 'review_required'::text])))
);

ALTER TABLE ONLY public.payments FORCE ROW LEVEL SECURITY;

--
-- Name: platform_admins; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.platform_admins (
    user_id text NOT NULL,
    granted_by text,
    created_at timestamp with time zone DEFAULT now() NOT NULL
);

--
-- Name: runtime_backends; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.runtime_backends (
    id uuid DEFAULT gen_random_uuid() NOT NULL,
    code text NOT NULL,
    framework text NOT NULL,
    sdk_language text NOT NULL,
    package_version text NOT NULL,
    backend_kind text NOT NULL,
    connection_secret_ref text NOT NULL,
    schema_name text NOT NULL,
    enabled boolean DEFAULT true NOT NULL,
    created_at timestamp with time zone DEFAULT now() NOT NULL,
    updated_at timestamp with time zone DEFAULT now() NOT NULL,
    CONSTRAINT runtime_backends_check_0 CHECK ((framework = ANY (ARRAY['langgraph'::text, 'agentscope'::text]))),
    CONSTRAINT runtime_backends_check_1 CHECK ((sdk_language = ANY (ARRAY['python'::text, 'javascript'::text, 'java'::text]))),
    CONSTRAINT runtime_backends_check_2 CHECK ((backend_kind = ANY (ARRAY['postgres'::text, 'sqlalchemy'::text, 'custom'::text])))
);

--
-- Name: runtime_identities; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.runtime_identities (
    id uuid DEFAULT gen_random_uuid() NOT NULL,
    tenant_id uuid NOT NULL,
    backend_id uuid NOT NULL,
    principal_id uuid NOT NULL,
    runtime_user_key text NOT NULL,
    status text NOT NULL,
    created_at timestamp with time zone DEFAULT now() NOT NULL,
    updated_at timestamp with time zone DEFAULT now() NOT NULL,
    CONSTRAINT runtime_identities_check_0 CHECK ((status = ANY (ARRAY['active'::text, 'revoked'::text])))
);

ALTER TABLE ONLY public.runtime_identities FORCE ROW LEVEL SECURITY;

--
-- Name: runtime_session_bindings; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.runtime_session_bindings (
    id uuid DEFAULT gen_random_uuid() NOT NULL,
    tenant_id uuid NOT NULL,
    identity_id uuid NOT NULL,
    channel_id text NOT NULL,
    agent_id text NOT NULL,
    agent_version_id uuid NOT NULL,
    team_member_id uuid,
    audience_kind text NOT NULL,
    customer_user_id text,
    started_by_user_id text,
    runtime_session_key text NOT NULL,
    checkpoint_namespace text DEFAULT ''::text NOT NULL,
    status text NOT NULL,
    generation integer DEFAULT 1 NOT NULL,
    policy_version text NOT NULL,
    lock_version bigint DEFAULT 0 NOT NULL,
    lease_owner text,
    lease_until timestamp with time zone,
    last_access_at timestamp with time zone,
    expires_at timestamp with time zone,
    purged_at timestamp with time zone,
    created_at timestamp with time zone DEFAULT now() NOT NULL,
    updated_at timestamp with time zone DEFAULT now() NOT NULL,
    backend_id uuid NOT NULL,
    CONSTRAINT runtime_session_bindings_check_0 CHECK ((((audience_kind = 'personal'::text) AND (customer_user_id IS NOT NULL) AND (team_member_id IS NULL)) OR ((audience_kind = 'team'::text) AND (customer_user_id IS NULL) AND (team_member_id IS NOT NULL)))),
    CONSTRAINT runtime_session_bindings_check_1 CHECK ((generation > 0)),
    CONSTRAINT runtime_session_bindings_check_2 CHECK ((audience_kind = ANY (ARRAY['personal'::text, 'team'::text]))),
    CONSTRAINT runtime_session_bindings_check_3 CHECK ((status = ANY (ARRAY['provisioning'::text, 'active'::text, 'interrupted'::text, 'closed'::text, 'revoked'::text, 'purging'::text, 'purged'::text, 'failed'::text])))
);

ALTER TABLE ONLY public.runtime_session_bindings FORCE ROW LEVEL SECURITY;

--
-- Name: scoped_user_roles; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.scoped_user_roles (
    id uuid DEFAULT gen_random_uuid() NOT NULL,
    tenant_id uuid NOT NULL,
    membership_id uuid NOT NULL,
    scope_id uuid NOT NULL,
    role_code text NOT NULL,
    granted_by text NOT NULL,
    valid_from timestamp with time zone NOT NULL,
    valid_to timestamp with time zone,
    created_at timestamp with time zone DEFAULT now() NOT NULL,
    updated_at timestamp with time zone DEFAULT now() NOT NULL,
    CONSTRAINT scoped_user_roles_check_0 CHECK ((role_code = ANY (ARRAY['management'::text, 'staff'::text, 'customer'::text]))),
    CONSTRAINT scoped_user_roles_check_1 CHECK (((valid_to IS NULL) OR (valid_to > valid_from)))
);

ALTER TABLE ONLY public.scoped_user_roles FORCE ROW LEVEL SECURITY;

--
-- Name: security_alert_deliveries; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.security_alert_deliveries (
    id uuid DEFAULT gen_random_uuid() NOT NULL,
    tenant_id uuid NOT NULL,
    alert_id uuid NOT NULL,
    contact_id uuid NOT NULL,
    recipient_user_id text NOT NULL,
    "position" integer NOT NULL,
    ack_timeout_seconds integer NOT NULL,
    status text DEFAULT 'waiting'::text NOT NULL,
    notified_at timestamp with time zone,
    deadline_at timestamp with time zone,
    acknowledged_at timestamp with time zone,
    CONSTRAINT security_deliveries_status CHECK (((status = ANY (ARRAY['waiting'::text, 'pending'::text, 'acknowledged'::text, 'timed_out'::text, 'cancelled'::text])) AND ("position" > 0) AND ((ack_timeout_seconds >= 5) AND (ack_timeout_seconds <= 3600))))
);

ALTER TABLE ONLY public.security_alert_deliveries FORCE ROW LEVEL SECURITY;

--
-- Name: security_alerts; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.security_alerts (
    id uuid DEFAULT gen_random_uuid() NOT NULL,
    tenant_id uuid NOT NULL,
    ticket_id uuid NOT NULL,
    created_by text NOT NULL,
    message text NOT NULL,
    idempotency_key text NOT NULL,
    request_hash text NOT NULL,
    status text DEFAULT 'open'::text NOT NULL,
    version integer DEFAULT 0 NOT NULL,
    created_at timestamp with time zone DEFAULT now() NOT NULL,
    updated_at timestamp with time zone DEFAULT now() NOT NULL,
    CONSTRAINT security_alerts_status CHECK (((status = ANY (ARRAY['open'::text, 'acknowledged'::text, 'exhausted'::text])) AND (version >= 0)))
);

ALTER TABLE ONLY public.security_alerts FORCE ROW LEVEL SECURITY;

--
-- Name: security_cameras; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.security_cameras (
    id uuid DEFAULT gen_random_uuid() NOT NULL,
    tenant_id uuid NOT NULL,
    building_id uuid NOT NULL,
    code text NOT NULL,
    name text NOT NULL,
    location text NOT NULL,
    status text NOT NULL,
    created_at timestamp with time zone DEFAULT now() NOT NULL,
    CONSTRAINT security_cameras_status CHECK ((status = ANY (ARRAY['online'::text, 'offline'::text, 'maintenance'::text])))
);

ALTER TABLE ONLY public.security_cameras FORCE ROW LEVEL SECURITY;

--
-- Name: security_emergency_contacts; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.security_emergency_contacts (
    id uuid DEFAULT gen_random_uuid() NOT NULL,
    tenant_id uuid NOT NULL,
    building_id uuid NOT NULL,
    user_id text NOT NULL,
    name text NOT NULL,
    role_label text NOT NULL,
    phone text NOT NULL,
    "position" integer NOT NULL,
    ack_timeout_seconds integer DEFAULT 60 NOT NULL,
    status text DEFAULT 'active'::text NOT NULL,
    CONSTRAINT security_contacts_values CHECK ((("position" > 0) AND ((ack_timeout_seconds >= 5) AND (ack_timeout_seconds <= 3600)) AND (status = ANY (ARRAY['active'::text, 'disabled'::text]))))
);

ALTER TABLE ONLY public.security_emergency_contacts FORCE ROW LEVEL SECURITY;

--
-- Name: service_categories; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.service_categories (
    id uuid DEFAULT gen_random_uuid() NOT NULL,
    tenant_id uuid NOT NULL,
    parent_id uuid,
    code text NOT NULL,
    name text NOT NULL,
    enabled boolean DEFAULT true NOT NULL,
    created_at timestamp with time zone DEFAULT now() NOT NULL,
    updated_at timestamp with time zone DEFAULT now() NOT NULL
);

ALTER TABLE ONLY public.service_categories FORCE ROW LEVEL SECURITY;

--
-- Name: service_interruptions; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.service_interruptions (
    id uuid DEFAULT gen_random_uuid() NOT NULL,
    tenant_id uuid NOT NULL,
    work_order_id uuid NOT NULL,
    approval_id uuid NOT NULL,
    utility text NOT NULL,
    reason text NOT NULL,
    planned_start timestamp with time zone NOT NULL,
    planned_end timestamp with time zone NOT NULL,
    actual_start timestamp with time zone,
    actual_end timestamp with time zone,
    status text NOT NULL,
    operated_by text,
    created_at timestamp with time zone DEFAULT now() NOT NULL,
    updated_at timestamp with time zone DEFAULT now() NOT NULL,
    CONSTRAINT service_interruptions_check_0 CHECK ((utility = ANY (ARRAY['water'::text, 'power'::text]))),
    CONSTRAINT service_interruptions_check_1 CHECK ((status = ANY (ARRAY['proposed'::text, 'approved'::text, 'notified'::text, 'active'::text, 'restored'::text, 'cancelled'::text])))
);

ALTER TABLE ONLY public.service_interruptions FORCE ROW LEVEL SECURITY;

--
-- Name: sessions; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.sessions (
    id text NOT NULL,
    user_id text NOT NULL,
    token text NOT NULL,
    expires_at timestamp with time zone NOT NULL,
    ip_address text,
    user_agent text,
    created_at timestamp with time zone DEFAULT now() NOT NULL,
    updated_at timestamp with time zone DEFAULT now() NOT NULL
);

--
-- Name: sites; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.sites (
    id uuid DEFAULT gen_random_uuid() NOT NULL,
    tenant_id uuid NOT NULL,
    domain_id uuid NOT NULL,
    code text NOT NULL,
    name text NOT NULL,
    address text NOT NULL,
    timezone text DEFAULT 'Asia/Ho_Chi_Minh'::text NOT NULL,
    status text NOT NULL,
    created_at timestamp with time zone DEFAULT now() NOT NULL,
    updated_at timestamp with time zone DEFAULT now() NOT NULL
);

ALTER TABLE ONLY public.sites FORCE ROW LEVEL SECURITY;

--
-- Name: sla_policies; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.sla_policies (
    id uuid DEFAULT gen_random_uuid() NOT NULL,
    tenant_id uuid NOT NULL,
    management_unit_id uuid NOT NULL,
    category_id uuid NOT NULL,
    priority text NOT NULL,
    response_minutes integer NOT NULL,
    resolution_minutes integer NOT NULL,
    effective_from timestamp with time zone NOT NULL,
    effective_to timestamp with time zone,
    created_at timestamp with time zone DEFAULT now() NOT NULL,
    updated_at timestamp with time zone DEFAULT now() NOT NULL,
    domain_id uuid NOT NULL,
    request_kind text NOT NULL,
    version_no integer NOT NULL,
    clock_basis text DEFAULT 'elapsed_24x7'::text NOT NULL,
    CONSTRAINT sla_policies_check_0 CHECK (((response_minutes > 0) AND (resolution_minutes > 0))),
    CONSTRAINT sla_policies_check_1 CHECK (((effective_to IS NULL) OR (effective_to > effective_from))),
    CONSTRAINT sla_policies_check_2 CHECK ((clock_basis = 'elapsed_24x7'::text)),
    CONSTRAINT sla_policies_check_3 CHECK ((request_kind = ANY (ARRAY['incident'::text, 'service_request'::text])))
);

ALTER TABLE ONLY public.sla_policies FORCE ROW LEVEL SECURITY;

--
-- Name: staff_profiles; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.staff_profiles (
    id uuid DEFAULT gen_random_uuid() NOT NULL,
    tenant_id uuid NOT NULL,
    user_id text NOT NULL,
    management_unit_id uuid NOT NULL,
    employee_code text NOT NULL,
    availability text NOT NULL,
    max_concurrent_jobs integer DEFAULT 1 NOT NULL,
    active boolean DEFAULT true NOT NULL,
    created_at timestamp with time zone DEFAULT now() NOT NULL,
    updated_at timestamp with time zone DEFAULT now() NOT NULL,
    CONSTRAINT staff_profiles_check_0 CHECK ((availability = ANY (ARRAY['available'::text, 'busy'::text, 'offline'::text, 'on_leave'::text])))
);

ALTER TABLE ONLY public.staff_profiles FORCE ROW LEVEL SECURITY;

--
-- Name: staff_shifts; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.staff_shifts (
    id uuid DEFAULT gen_random_uuid() NOT NULL,
    tenant_id uuid NOT NULL,
    staff_id uuid NOT NULL,
    starts_at timestamp with time zone NOT NULL,
    ends_at timestamp with time zone NOT NULL,
    status text NOT NULL,
    created_at timestamp with time zone DEFAULT now() NOT NULL,
    updated_at timestamp with time zone DEFAULT now() NOT NULL,
    CONSTRAINT staff_shifts_check_0 CHECK ((status = ANY (ARRAY['scheduled'::text, 'available'::text, 'leave'::text, 'cancelled'::text])))
);

ALTER TABLE ONLY public.staff_shifts FORCE ROW LEVEL SECURITY;

--
-- Name: staff_specialties; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.staff_specialties (
    tenant_id uuid NOT NULL,
    staff_id uuid NOT NULL,
    category_id uuid NOT NULL,
    proficiency text NOT NULL,
    active boolean DEFAULT true NOT NULL,
    created_at timestamp with time zone DEFAULT now() NOT NULL
);

ALTER TABLE ONLY public.staff_specialties FORCE ROW LEVEL SECURITY;

--
-- Name: storage_locations; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.storage_locations (
    id uuid DEFAULT gen_random_uuid() NOT NULL,
    tenant_id uuid NOT NULL,
    provider text NOT NULL,
    endpoint_ref text NOT NULL,
    region text,
    bucket_name text NOT NULL,
    tenant_prefix text NOT NULL,
    credential_secret_ref text NOT NULL,
    versioning_required boolean DEFAULT true NOT NULL,
    encryption_mode text NOT NULL,
    kms_key_ref text,
    purpose text NOT NULL,
    status text NOT NULL,
    created_at timestamp with time zone DEFAULT now() NOT NULL,
    updated_at timestamp with time zone DEFAULT now() NOT NULL,
    CONSTRAINT storage_locations_check_0 CHECK ((purpose = ANY (ARRAY['staging'::text, 'evidence'::text, 'derived'::text, 'documents'::text, 'reports'::text]))),
    CONSTRAINT storage_locations_check_1 CHECK ((status = ANY (ARRAY['active'::text, 'readonly'::text, 'disabled'::text])))
);

ALTER TABLE ONLY public.storage_locations FORCE ROW LEVEL SECURITY;

--
-- Name: team_members; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.team_members (
    id uuid DEFAULT gen_random_uuid() NOT NULL,
    tenant_id uuid NOT NULL,
    team_id uuid NOT NULL,
    agent_id text NOT NULL,
    version_id uuid NOT NULL,
    member_kind text NOT NULL,
    status text NOT NULL,
    created_at timestamp with time zone DEFAULT now() NOT NULL,
    updated_at timestamp with time zone DEFAULT now() NOT NULL,
    binding_id uuid,
    CONSTRAINT team_members_check_0 CHECK ((status = ANY (ARRAY['provisioning'::text, 'active'::text, 'closed'::text, 'failed'::text])))
);

ALTER TABLE ONLY public.team_members FORCE ROW LEVEL SECURITY;

--
-- Name: tenant_memberships; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.tenant_memberships (
    id uuid DEFAULT gen_random_uuid() NOT NULL,
    tenant_id uuid NOT NULL,
    user_id text NOT NULL,
    status text NOT NULL,
    joined_at timestamp with time zone,
    ended_at timestamp with time zone,
    created_at timestamp with time zone DEFAULT now() NOT NULL,
    updated_at timestamp with time zone DEFAULT now() NOT NULL,
    CONSTRAINT tenant_memberships_check_0 CHECK ((status = ANY (ARRAY['pending'::text, 'active'::text, 'suspended'::text, 'ended'::text])))
);

ALTER TABLE ONLY public.tenant_memberships FORCE ROW LEVEL SECURITY;

--
-- Name: tenants; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.tenants (
    id uuid DEFAULT gen_random_uuid() NOT NULL,
    code text NOT NULL,
    name text NOT NULL,
    status text NOT NULL,
    timezone text DEFAULT 'Asia/Ho_Chi_Minh'::text NOT NULL,
    retention_policy jsonb DEFAULT '{}'::jsonb NOT NULL,
    created_at timestamp with time zone DEFAULT now() NOT NULL,
    updated_at timestamp with time zone DEFAULT now() NOT NULL,
    CONSTRAINT tenants_check_0 CHECK ((status = ANY (ARRAY['active'::text, 'suspended'::text, 'closed'::text])))
);

--
-- Name: ticket_assessments; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.ticket_assessments (
    id uuid DEFAULT gen_random_uuid() NOT NULL,
    tenant_id uuid NOT NULL,
    ticket_id uuid NOT NULL,
    ticket_generation integer NOT NULL,
    basis_ticket_version bigint NOT NULL,
    basis_decision_id uuid,
    stage text NOT NULL,
    assessor_kind text NOT NULL,
    assessor_user_id text,
    source_run_id uuid,
    input_schema_version text NOT NULL,
    facts jsonb NOT NULL,
    proposed_severity text NOT NULL,
    proposed_urgency text NOT NULL,
    proposed_priority text,
    confidence numeric(5,4),
    rationale text NOT NULL,
    observed_at timestamp with time zone NOT NULL,
    submitted_at timestamp with time zone NOT NULL,
    idempotency_key text NOT NULL,
    supersedes_assessment_id uuid,
    created_at timestamp with time zone DEFAULT now() NOT NULL,
    CONSTRAINT ticket_assessments_check_0 CHECK (((ticket_generation >= 0) AND (basis_ticket_version >= 0))),
    CONSTRAINT ticket_assessments_check_1 CHECK (((confidence IS NULL) OR ((confidence >= (0)::numeric) AND (confidence <= (1)::numeric)))),
    CONSTRAINT ticket_assessments_check_2 CHECK ((((assessor_kind = 'agent'::text) AND (source_run_id IS NOT NULL) AND (assessor_user_id IS NULL)) OR ((assessor_kind = 'human'::text) AND (assessor_user_id IS NOT NULL) AND (source_run_id IS NULL)) OR ((assessor_kind = 'system'::text) AND (assessor_user_id IS NULL) AND (source_run_id IS NULL)))),
    CONSTRAINT ticket_assessments_check_3 CHECK ((stage = ANY (ARRAY['intake'::text, 'specialist'::text, 'onsite'::text, 'reassessment'::text]))),
    CONSTRAINT ticket_assessments_check_4 CHECK ((assessor_kind = ANY (ARRAY['agent'::text, 'human'::text, 'system'::text]))),
    CONSTRAINT ticket_assessments_check_5 CHECK ((proposed_severity = ANY (ARRAY['unknown'::text, 'minor'::text, 'moderate'::text, 'major'::text, 'critical'::text, 'not_applicable'::text]))),
    CONSTRAINT ticket_assessments_check_6 CHECK ((proposed_urgency = ANY (ARRAY['unknown'::text, 'routine'::text, 'soon'::text, 'immediate'::text])))
);

ALTER TABLE ONLY public.ticket_assessments FORCE ROW LEVEL SECURITY;

--
-- Name: ticket_escalations; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.ticket_escalations (
    id uuid DEFAULT gen_random_uuid() NOT NULL,
    tenant_id uuid NOT NULL,
    ticket_id uuid NOT NULL,
    ticket_generation integer NOT NULL,
    decision_id uuid,
    sla_cycle_id uuid,
    review_id uuid,
    work_order_id uuid,
    required_scope_id uuid NOT NULL,
    reason_code text NOT NULL,
    dedupe_key text NOT NULL,
    status text NOT NULL,
    detected_at timestamp with time zone NOT NULL,
    next_notify_at timestamp with time zone NOT NULL,
    acknowledged_by text,
    acknowledged_at timestamp with time zone,
    resolved_by text,
    resolved_at timestamp with time zone,
    resolution_note text,
    assessment_id uuid,
    created_at timestamp with time zone DEFAULT now() NOT NULL,
    updated_at timestamp with time zone DEFAULT now() NOT NULL,
    CONSTRAINT ticket_escalations_check_0 CHECK ((reason_code = ANY (ARRAY['emergency'::text, 'response_breach'::text, 'resolution_breach'::text, 'review_overdue'::text, 'risk_signal_pending'::text, 'queue_wait'::text, 'no_capacity'::text, 'policy_missing'::text]))),
    CONSTRAINT ticket_escalations_check_1 CHECK ((status = ANY (ARRAY['open'::text, 'acknowledged'::text, 'resolved'::text, 'cancelled'::text])))
);

ALTER TABLE ONLY public.ticket_escalations FORCE ROW LEVEL SECURITY;

--
-- Name: ticket_events; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.ticket_events (
    id uuid DEFAULT gen_random_uuid() NOT NULL,
    tenant_id uuid NOT NULL,
    ticket_id uuid NOT NULL,
    seq bigint NOT NULL,
    event_type text NOT NULL,
    schema_version integer DEFAULT 1 NOT NULL,
    from_status text,
    to_status text,
    actor_kind text NOT NULL,
    actor_user_id text,
    actor_agent_id text,
    idempotency_key text NOT NULL,
    correlation_id uuid NOT NULL,
    causation_event_id uuid,
    payload jsonb NOT NULL,
    occurred_at timestamp with time zone NOT NULL,
    created_at timestamp with time zone DEFAULT now() NOT NULL
);

ALTER TABLE ONLY public.ticket_events FORCE ROW LEVEL SECURITY;

--
-- Name: ticket_files; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.ticket_files (
    tenant_id uuid NOT NULL,
    ticket_id uuid NOT NULL,
    file_id uuid NOT NULL,
    event_id uuid,
    purpose text NOT NULL,
    uploaded_by text NOT NULL,
    created_at timestamp with time zone DEFAULT now() NOT NULL,
    evidence_id uuid,
    CONSTRAINT ticket_files_check_0 CHECK ((purpose = ANY (ARRAY['issue'::text, 'before'::text, 'after'::text, 'other'::text])))
);

ALTER TABLE ONLY public.ticket_files FORCE ROW LEVEL SECURITY;

--
-- Name: ticket_reviews; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.ticket_reviews (
    id uuid DEFAULT gen_random_uuid() NOT NULL,
    tenant_id uuid NOT NULL,
    ticket_id uuid NOT NULL,
    assignment_id uuid NOT NULL,
    reviewer_user_id text NOT NULL,
    staff_id uuid NOT NULL,
    score smallint NOT NULL,
    comment text,
    submitted_at timestamp with time zone NOT NULL,
    created_at timestamp with time zone DEFAULT now() NOT NULL,
    updated_at timestamp with time zone DEFAULT now() NOT NULL,
    CONSTRAINT ticket_reviews_check_0 CHECK (((score >= 1) AND (score <= 5)))
);

ALTER TABLE ONLY public.ticket_reviews FORCE ROW LEVEL SECURITY;

--
-- Name: ticket_routing_history; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.ticket_routing_history (
    id uuid DEFAULT gen_random_uuid() NOT NULL,
    tenant_id uuid NOT NULL,
    ticket_id uuid NOT NULL,
    from_management_id uuid,
    to_management_id uuid NOT NULL,
    team_id uuid,
    status text NOT NULL,
    reason text NOT NULL,
    ack_event_id uuid,
    requested_at timestamp with time zone NOT NULL,
    acknowledged_at timestamp with time zone,
    created_at timestamp with time zone DEFAULT now() NOT NULL,
    CONSTRAINT ticket_routing_history_check_0 CHECK ((status = ANY (ARRAY['requested'::text, 'accepted'::text, 'rejected'::text, 'timeout'::text])))
);

ALTER TABLE ONLY public.ticket_routing_history FORCE ROW LEVEL SECURITY;

--
-- Name: ticket_sla_adjustments; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.ticket_sla_adjustments (
    id uuid DEFAULT gen_random_uuid() NOT NULL,
    tenant_id uuid NOT NULL,
    cycle_id uuid NOT NULL,
    decision_id uuid NOT NULL,
    target_policy_id uuid NOT NULL,
    adjustment_kind text NOT NULL,
    old_response_due_at timestamp with time zone NOT NULL,
    new_response_due_at timestamp with time zone NOT NULL,
    old_resolution_due_at timestamp with time zone NOT NULL,
    new_resolution_due_at timestamp with time zone NOT NULL,
    authorized_by text,
    reason text NOT NULL,
    idempotency_key text NOT NULL,
    created_at timestamp with time zone DEFAULT now() NOT NULL,
    CONSTRAINT ticket_sla_adjustments_check_0 CHECK (((adjustment_kind <> 'exception_extend'::text) OR (authorized_by IS NOT NULL))),
    CONSTRAINT ticket_sla_adjustments_check_1 CHECK ((adjustment_kind = ANY (ARRAY['tighten'::text, 'keep'::text, 'exception_extend'::text])))
);

ALTER TABLE ONLY public.ticket_sla_adjustments FORCE ROW LEVEL SECURITY;

--
-- Name: ticket_sla_cycles; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.ticket_sla_cycles (
    id uuid DEFAULT gen_random_uuid() NOT NULL,
    tenant_id uuid NOT NULL,
    ticket_id uuid NOT NULL,
    ticket_generation integer NOT NULL,
    initial_policy_id uuid NOT NULL,
    initial_decision_id uuid NOT NULL,
    started_at timestamp with time zone NOT NULL,
    response_minutes_snapshot integer NOT NULL,
    resolution_minutes_snapshot integer NOT NULL,
    initial_response_due_at timestamp with time zone NOT NULL,
    initial_resolution_due_at timestamp with time zone NOT NULL,
    current_response_due_at timestamp with time zone NOT NULL,
    current_resolution_due_at timestamp with time zone NOT NULL,
    responded_at timestamp with time zone,
    resolved_at timestamp with time zone,
    response_breached_at timestamp with time zone,
    resolution_breached_at timestamp with time zone,
    status text NOT NULL,
    version bigint DEFAULT 0 NOT NULL,
    created_at timestamp with time zone DEFAULT now() NOT NULL,
    updated_at timestamp with time zone DEFAULT now() NOT NULL,
    CONSTRAINT ticket_sla_cycles_check_0 CHECK (((response_minutes_snapshot > 0) AND (resolution_minutes_snapshot > 0))),
    CONSTRAINT ticket_sla_cycles_check_1 CHECK ((ticket_generation >= 0)),
    CONSTRAINT ticket_sla_cycles_check_2 CHECK ((status = ANY (ARRAY['active'::text, 'resolved'::text, 'cancelled'::text])))
);

ALTER TABLE ONLY public.ticket_sla_cycles FORCE ROW LEVEL SECURITY;

--
-- Name: ticket_triage_decisions; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.ticket_triage_decisions (
    id uuid DEFAULT gen_random_uuid() NOT NULL,
    tenant_id uuid NOT NULL,
    ticket_id uuid NOT NULL,
    ticket_generation integer NOT NULL,
    decision_seq integer NOT NULL,
    assessment_id uuid NOT NULL,
    policy_binding_id uuid NOT NULL,
    policy_version_id uuid NOT NULL,
    matched_rule_id uuid,
    previous_applied_id uuid,
    review_id uuid,
    outcome text NOT NULL,
    decision_mode text NOT NULL,
    severity text NOT NULL,
    priority text NOT NULL,
    is_emergency boolean NOT NULL,
    evaluation_trace jsonb NOT NULL,
    reason text NOT NULL,
    basis_ticket_version bigint NOT NULL,
    applied_ticket_version bigint,
    decided_at timestamp with time zone NOT NULL,
    approved_by text,
    idempotency_key text NOT NULL,
    created_at timestamp with time zone DEFAULT now() NOT NULL,
    CONSTRAINT ticket_triage_decisions_check_0 CHECK (((ticket_generation >= 0) AND (decision_seq > 0))),
    CONSTRAINT ticket_triage_decisions_check_1 CHECK (((NOT is_emergency) OR (priority = 'critical'::text))),
    CONSTRAINT ticket_triage_decisions_check_2 CHECK (((outcome = 'applied'::text) = (applied_ticket_version IS NOT NULL))),
    CONSTRAINT ticket_triage_decisions_check_3 CHECK ((((decision_mode = ANY (ARRAY['human_confirmed'::text, 'human_override'::text])) AND (approved_by IS NOT NULL) AND (review_id IS NOT NULL)) OR ((decision_mode = ANY (ARRAY['automatic'::text, 'provisional'::text])) AND (approved_by IS NULL)))),
    CONSTRAINT ticket_triage_decisions_check_4 CHECK ((outcome = ANY (ARRAY['applied'::text, 'review_required'::text, 'rejected'::text, 'stale'::text]))),
    CONSTRAINT ticket_triage_decisions_check_5 CHECK ((decision_mode = ANY (ARRAY['automatic'::text, 'provisional'::text, 'human_confirmed'::text, 'human_override'::text]))),
    CONSTRAINT ticket_triage_decisions_check_6 CHECK ((severity = ANY (ARRAY['unknown'::text, 'minor'::text, 'moderate'::text, 'major'::text, 'critical'::text, 'not_applicable'::text]))),
    CONSTRAINT ticket_triage_decisions_check_7 CHECK ((priority = ANY (ARRAY['low'::text, 'normal'::text, 'high'::text, 'critical'::text])))
);

ALTER TABLE ONLY public.ticket_triage_decisions FORCE ROW LEVEL SECURITY;

--
-- Name: ticket_triage_reviews; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.ticket_triage_reviews (
    id uuid DEFAULT gen_random_uuid() NOT NULL,
    tenant_id uuid NOT NULL,
    ticket_id uuid NOT NULL,
    ticket_generation integer NOT NULL,
    assessment_id uuid NOT NULL,
    pending_decision_id uuid NOT NULL,
    required_scope_id uuid NOT NULL,
    reason_code text NOT NULL,
    status text NOT NULL,
    due_at timestamp with time zone NOT NULL,
    claimed_by text,
    claim_until timestamp with time zone,
    version bigint DEFAULT 0 NOT NULL,
    decided_by text,
    decided_at timestamp with time zone,
    decision_note text,
    result_decision_id uuid,
    created_at timestamp with time zone DEFAULT now() NOT NULL,
    updated_at timestamp with time zone DEFAULT now() NOT NULL,
    CONSTRAINT ticket_triage_reviews_check_0 CHECK ((reason_code = ANY (ARRAY['unknown_facts'::text, 'conflict'::text, 'downgrade'::text, 'emergency_override'::text, 'overdue_review'::text]))),
    CONSTRAINT ticket_triage_reviews_check_1 CHECK ((status = ANY (ARRAY['pending'::text, 'claimed'::text, 'approved'::text, 'rejected'::text, 'superseded'::text, 'expired'::text])))
);

ALTER TABLE ONLY public.ticket_triage_reviews FORCE ROW LEVEL SECURITY;

--
-- Name: tickets; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.tickets (
    id uuid DEFAULT gen_random_uuid() NOT NULL,
    tenant_id uuid NOT NULL,
    code text NOT NULL,
    requester_user_id text NOT NULL,
    channel_id text NOT NULL,
    unit_id uuid,
    site_id uuid,
    zone_id uuid,
    building_id uuid,
    management_unit_id uuid,
    coverage_id uuid,
    category_id uuid,
    incident_type_id uuid,
    title text NOT NULL,
    description text NOT NULL,
    priority text,
    status text NOT NULL,
    resolution_mode text,
    contact_name text NOT NULL,
    contact_phone text NOT NULL,
    address_snapshot jsonb NOT NULL,
    assigned_team_id uuid,
    sla_policy_id uuid,
    response_due_at timestamp with time zone,
    resolution_due_at timestamp with time zone,
    first_response_at timestamp with time zone,
    resolved_at timestamp with time zone,
    closed_at timestamp with time zone,
    version bigint DEFAULT 0 NOT NULL,
    last_event_seq bigint DEFAULT 0 NOT NULL,
    reopen_count integer DEFAULT 0 NOT NULL,
    created_at timestamp with time zone DEFAULT now() NOT NULL,
    updated_at timestamp with time zone DEFAULT now() NOT NULL,
    domain_id uuid NOT NULL,
    request_kind text NOT NULL,
    severity text DEFAULT 'unknown'::text NOT NULL,
    triage_status text DEFAULT 'pending'::text NOT NULL,
    current_triage_decision_id uuid,
    is_emergency boolean DEFAULT false NOT NULL,
    active_sla_cycle_id uuid,
    CONSTRAINT tickets_check_0 CHECK (((priority IS NULL) OR (priority = ANY (ARRAY['low'::text, 'normal'::text, 'high'::text, 'critical'::text])))),
    CONSTRAINT tickets_check_1 CHECK ((severity = ANY (ARRAY['unknown'::text, 'minor'::text, 'moderate'::text, 'major'::text, 'critical'::text, 'not_applicable'::text]))),
    CONSTRAINT tickets_check_2 CHECK ((request_kind = ANY (ARRAY['incident'::text, 'service_request'::text]))),
    CONSTRAINT tickets_check_3 CHECK (((NOT is_emergency) OR (priority = 'critical'::text))),
    CONSTRAINT tickets_check_4 CHECK ((resolution_mode = ANY (ARRAY['guided'::text, 'onsite'::text]))),
    CONSTRAINT tickets_check_5 CHECK ((triage_status = ANY (ARRAY['pending'::text, 'provisional'::text, 'confirmed'::text, 'review_required'::text])))
);

ALTER TABLE ONLY public.tickets FORCE ROW LEVEL SECURITY;

--
-- Name: triage_policy_bindings; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.triage_policy_bindings (
    id uuid DEFAULT gen_random_uuid() NOT NULL,
    tenant_id uuid NOT NULL,
    domain_id uuid NOT NULL,
    scope_id uuid NOT NULL,
    category_id uuid,
    request_kind text NOT NULL,
    policy_version_id uuid NOT NULL,
    valid_from timestamp with time zone NOT NULL,
    valid_to timestamp with time zone,
    status text NOT NULL,
    configured_by text NOT NULL,
    created_at timestamp with time zone DEFAULT now() NOT NULL,
    updated_at timestamp with time zone DEFAULT now() NOT NULL,
    CONSTRAINT triage_policy_bindings_check_0 CHECK (((valid_to IS NULL) OR (valid_to > valid_from))),
    CONSTRAINT triage_policy_bindings_check_1 CHECK ((request_kind = ANY (ARRAY['incident'::text, 'service_request'::text]))),
    CONSTRAINT triage_policy_bindings_check_2 CHECK ((status = ANY (ARRAY['active'::text, 'disabled'::text])))
);

ALTER TABLE ONLY public.triage_policy_bindings FORCE ROW LEVEL SECURITY;

--
-- Name: triage_policy_versions; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.triage_policy_versions (
    id uuid DEFAULT gen_random_uuid() NOT NULL,
    tenant_id uuid NOT NULL,
    domain_id uuid NOT NULL,
    policy_code text NOT NULL,
    version_no integer NOT NULL,
    status text NOT NULL,
    engine_version text NOT NULL,
    input_schema_version text NOT NULL,
    input_schema jsonb NOT NULL,
    unknown_priority text NOT NULL,
    review_timeout_seconds integer NOT NULL,
    max_fact_age_seconds integer NOT NULL,
    max_queue_wait_seconds integer NOT NULL,
    policy_hash text NOT NULL,
    created_by text NOT NULL,
    published_by text,
    published_at timestamp with time zone,
    created_at timestamp with time zone DEFAULT now() NOT NULL,
    updated_at timestamp with time zone DEFAULT now() NOT NULL,
    CONSTRAINT triage_policy_versions_check_0 CHECK ((version_no > 0)),
    CONSTRAINT triage_policy_versions_check_1 CHECK ((unknown_priority = ANY (ARRAY['normal'::text, 'high'::text, 'critical'::text]))),
    CONSTRAINT triage_policy_versions_check_2 CHECK (((review_timeout_seconds > 0) AND (max_fact_age_seconds > 0) AND (max_queue_wait_seconds > 0))),
    CONSTRAINT triage_policy_versions_check_3 CHECK (((status <> 'published'::text) OR ((published_by IS NOT NULL) AND (published_at IS NOT NULL)))),
    CONSTRAINT triage_policy_versions_check_4 CHECK ((status = ANY (ARRAY['draft'::text, 'published'::text, 'retired'::text])))
);

ALTER TABLE ONLY public.triage_policy_versions FORCE ROW LEVEL SECURITY;

--
-- Name: triage_rules; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.triage_rules (
    id uuid DEFAULT gen_random_uuid() NOT NULL,
    tenant_id uuid NOT NULL,
    policy_version_id uuid NOT NULL,
    rule_code text NOT NULL,
    rule_kind text NOT NULL,
    precedence integer NOT NULL,
    condition_expr jsonb NOT NULL,
    severity_result text NOT NULL,
    priority_result text NOT NULL,
    requires_human_review boolean DEFAULT false NOT NULL,
    reason_template text NOT NULL,
    created_at timestamp with time zone DEFAULT now() NOT NULL,
    CONSTRAINT triage_rules_check_0 CHECK ((precedence > 0)),
    CONSTRAINT triage_rules_check_1 CHECK (((rule_kind <> 'emergency_floor'::text) OR (severity_result <> 'not_applicable'::text))),
    CONSTRAINT triage_rules_check_2 CHECK ((rule_kind = ANY (ARRAY['emergency_floor'::text, 'decision'::text]))),
    CONSTRAINT triage_rules_check_3 CHECK ((severity_result = ANY (ARRAY['minor'::text, 'moderate'::text, 'major'::text, 'critical'::text]))),
    CONSTRAINT triage_rules_check_4 CHECK ((priority_result = ANY (ARRAY['low'::text, 'normal'::text, 'high'::text, 'critical'::text])))
);

ALTER TABLE ONLY public.triage_rules FORCE ROW LEVEL SECURITY;

--
-- Name: unit_residents; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.unit_residents (
    id uuid DEFAULT gen_random_uuid() NOT NULL,
    tenant_id uuid NOT NULL,
    unit_id uuid NOT NULL,
    user_id text NOT NULL,
    relation text NOT NULL,
    verification_status text NOT NULL,
    valid_from timestamp with time zone NOT NULL,
    valid_to timestamp with time zone,
    verified_by text,
    verified_at timestamp with time zone,
    created_at timestamp with time zone DEFAULT now() NOT NULL,
    updated_at timestamp with time zone DEFAULT now() NOT NULL,
    CONSTRAINT unit_residents_check_0 CHECK ((relation = ANY (ARRAY['owner'::text, 'tenant'::text, 'household'::text]))),
    CONSTRAINT unit_residents_check_1 CHECK ((verification_status = ANY (ARRAY['pending'::text, 'verified'::text, 'rejected'::text, 'expired'::text])))
);

ALTER TABLE ONLY public.unit_residents FORCE ROW LEVEL SECURITY;

--
-- Name: units; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.units (
    id uuid DEFAULT gen_random_uuid() NOT NULL,
    tenant_id uuid NOT NULL,
    site_id uuid NOT NULL,
    zone_id uuid,
    building_id uuid,
    code text NOT NULL,
    unit_kind text NOT NULL,
    floor text,
    status text NOT NULL,
    created_at timestamp with time zone DEFAULT now() NOT NULL,
    updated_at timestamp with time zone DEFAULT now() NOT NULL,
    CONSTRAINT units_check_0 CHECK ((unit_kind = ANY (ARRAY['apartment'::text, 'townhouse'::text, 'villa'::text, 'other'::text])))
);

ALTER TABLE ONLY public.units FORCE ROW LEVEL SECURITY;

--
-- Name: users; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.users (
    id text NOT NULL,
    email text,
    name text,
    image text,
    email_verified boolean DEFAULT false NOT NULL,
    groups text[] DEFAULT '{}'::text[] NOT NULL,
    onboarding_step integer DEFAULT 0 NOT NULL,
    onboarding_completed_at timestamp with time zone,
    last_signed_in_at timestamp with time zone,
    created_at timestamp with time zone DEFAULT now() NOT NULL,
    updated_at timestamp with time zone DEFAULT now() NOT NULL,
    phone_e164 text,
    phone_verified_at timestamp with time zone,
    status text DEFAULT 'pending'::text NOT NULL,
    disabled_at timestamp with time zone,
    deleted_at timestamp with time zone,
    CONSTRAINT users_check_0 CHECK ((status = ANY (ARRAY['pending'::text, 'active'::text, 'suspended'::text, 'deleted'::text]))),
    CONSTRAINT users_check_1 CHECK (((status = 'deleted'::text) OR (email IS NOT NULL) OR (phone_e164 IS NOT NULL)))
);

--
-- Name: vh_assets; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.vh_assets (
    id uuid DEFAULT gen_random_uuid() NOT NULL,
    tenant_id uuid NOT NULL,
    building_id uuid NOT NULL,
    code text NOT NULL,
    name text NOT NULL,
    details jsonb DEFAULT '{}'::jsonb NOT NULL,
    status text NOT NULL,
    created_at timestamp with time zone DEFAULT now() NOT NULL,
    CONSTRAINT vh_assets_status_check CHECK ((status = ANY (ARRAY['active'::text, 'inactive'::text])))
);

ALTER TABLE ONLY public.vh_assets FORCE ROW LEVEL SECURITY;

--
-- Name: vh_budget_approvals; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.vh_budget_approvals (
    id uuid DEFAULT gen_random_uuid() NOT NULL,
    tenant_id uuid NOT NULL,
    work_order_id uuid NOT NULL,
    requested_by text NOT NULL,
    reviewer_user_id text NOT NULL,
    amount_vnd numeric(18,2) NOT NULL,
    purpose text NOT NULL,
    status text NOT NULL,
    version bigint DEFAULT 0 NOT NULL,
    decided_by text,
    decided_at timestamp with time zone,
    decision_note text,
    created_at timestamp with time zone DEFAULT now() NOT NULL,
    updated_at timestamp with time zone DEFAULT now() NOT NULL,
    CONSTRAINT vh_budget_approvals_amount_vnd_check CHECK ((amount_vnd > (0)::numeric)),
    CONSTRAINT vh_budget_approvals_status_check CHECK ((status = ANY (ARRAY['pending'::text, 'approved'::text, 'rejected'::text, 'cancelled'::text])))
);

ALTER TABLE ONLY public.vh_budget_approvals FORCE ROW LEVEL SECURITY;

--
-- Name: vh_cleaning_plans; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.vh_cleaning_plans (
    id uuid DEFAULT gen_random_uuid() NOT NULL,
    tenant_id uuid NOT NULL,
    work_order_id uuid NOT NULL,
    plan jsonb NOT NULL,
    status text NOT NULL,
    version bigint DEFAULT 0 NOT NULL,
    updated_by text NOT NULL,
    created_at timestamp with time zone DEFAULT now() NOT NULL,
    updated_at timestamp with time zone DEFAULT now() NOT NULL,
    CONSTRAINT vh_cleaning_plans_status_check CHECK ((status = ANY (ARRAY['draft'::text, 'in_progress'::text, 'completed'::text, 'cancelled'::text])))
);

ALTER TABLE ONLY public.vh_cleaning_plans FORCE ROW LEVEL SECURITY;

--
-- Name: vh_command_receipt; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.vh_command_receipt (
    id uuid DEFAULT gen_random_uuid() NOT NULL,
    tenant_id uuid NOT NULL,
    actor_type character varying(16) NOT NULL,
    actor_id character varying(128) NOT NULL,
    command_type character varying(128) NOT NULL,
    idempotency_key character varying(128) NOT NULL,
    payload_hash character varying(72) NOT NULL,
    subject_type character varying(128) NOT NULL,
    subject_id character varying(128),
    response_json jsonb,
    status character varying(16) NOT NULL,
    created_at timestamp with time zone DEFAULT now() NOT NULL,
    completed_at timestamp with time zone,
    CONSTRAINT vh_command_receipt_status_check CHECK (((status)::text = ANY (ARRAY[('IN_PROGRESS'::character varying)::text, ('COMPLETED'::character varying)::text])))
);

ALTER TABLE ONLY public.vh_command_receipt FORCE ROW LEVEL SECURITY;

--
-- Name: vh_contractor_updates; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.vh_contractor_updates (
    id uuid DEFAULT gen_random_uuid() NOT NULL,
    tenant_id uuid NOT NULL,
    work_order_id uuid NOT NULL,
    status text NOT NULL,
    worker_name text,
    materials jsonb DEFAULT '[]'::jsonb NOT NULL,
    note text,
    version bigint DEFAULT 0 NOT NULL,
    updated_by text NOT NULL,
    created_at timestamp with time zone DEFAULT now() NOT NULL,
    updated_at timestamp with time zone DEFAULT now() NOT NULL,
    CONSTRAINT vh_contractor_updates_status_check CHECK ((status = ANY (ARRAY['pending'::text, 'accepted'::text, 'rejected'::text, 'in_progress'::text, 'completed'::text])))
);

ALTER TABLE ONLY public.vh_contractor_updates FORCE ROW LEVEL SECURITY;

--
-- Name: vh_conversation_uploads; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.vh_conversation_uploads (
    id uuid DEFAULT gen_random_uuid() NOT NULL,
    tenant_id uuid NOT NULL,
    file_id uuid NOT NULL,
    channel_id text NOT NULL,
    requested_by text NOT NULL,
    location_id uuid NOT NULL,
    object_key text NOT NULL,
    expected_size bigint NOT NULL,
    expected_sha256 text NOT NULL,
    mime_type text NOT NULL,
    status text NOT NULL,
    idempotency_key text NOT NULL,
    request_hash text NOT NULL,
    created_at timestamp with time zone DEFAULT now() NOT NULL,
    CONSTRAINT vh_conversation_uploads_expected_sha256_check CHECK ((expected_sha256 ~ '^[a-f0-9]{64}$'::text)),
    CONSTRAINT vh_conversation_uploads_expected_size_check CHECK (((expected_size > 0) AND (expected_size <= 10485760))),
    CONSTRAINT vh_conversation_uploads_status_check CHECK ((status = ANY (ARRAY['issued'::text, 'uploaded'::text, 'ready'::text])))
);

ALTER TABLE ONLY public.vh_conversation_uploads FORCE ROW LEVEL SECURITY;

--
-- Name: vh_maintenance_records; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.vh_maintenance_records (
    id uuid DEFAULT gen_random_uuid() NOT NULL,
    tenant_id uuid NOT NULL,
    asset_id uuid NOT NULL,
    work_order_id uuid NOT NULL,
    note text NOT NULL,
    confirmed_by text NOT NULL,
    created_at timestamp with time zone DEFAULT now() NOT NULL
);

ALTER TABLE ONLY public.vh_maintenance_records FORCE ROW LEVEL SECURITY;

--
-- Name: vh_operational_requests; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.vh_operational_requests (
    id uuid DEFAULT gen_random_uuid() NOT NULL,
    tenant_id uuid NOT NULL,
    work_order_id uuid NOT NULL,
    kind text NOT NULL,
    details jsonb NOT NULL,
    reason text NOT NULL,
    requested_by text NOT NULL,
    status text NOT NULL,
    version bigint DEFAULT 0 NOT NULL,
    idempotency_key text NOT NULL,
    request_hash text NOT NULL,
    decided_by text,
    decision_note text,
    decided_at timestamp with time zone,
    created_at timestamp with time zone DEFAULT now() NOT NULL,
    updated_at timestamp with time zone DEFAULT now() NOT NULL,
    CONSTRAINT vh_operational_requests_kind_check CHECK ((kind = ANY (ARRAY['utility_isolation'::text, 'area_restriction'::text, 'apartment_entry'::text, 'vendor_dispatch'::text]))),
    CONSTRAINT vh_operational_requests_status_check CHECK ((status = ANY (ARRAY['pending'::text, 'approved'::text, 'rejected'::text, 'completed'::text, 'cancelled'::text])))
);

ALTER TABLE ONLY public.vh_operational_requests FORCE ROW LEVEL SECURITY;

--
-- Name: vh_qc_redo_orders; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.vh_qc_redo_orders (
    id uuid DEFAULT gen_random_uuid() NOT NULL,
    tenant_id uuid NOT NULL,
    qc_result_id uuid NOT NULL,
    source_work_order_id uuid NOT NULL,
    redo_work_order_id uuid NOT NULL,
    created_by text NOT NULL,
    created_at timestamp with time zone DEFAULT now() NOT NULL
);

ALTER TABLE ONLY public.vh_qc_redo_orders FORCE ROW LEVEL SECURITY;

--
-- Name: vh_qc_results; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.vh_qc_results (
    id uuid DEFAULT gen_random_uuid() NOT NULL,
    tenant_id uuid NOT NULL,
    work_order_id uuid NOT NULL,
    outcome text NOT NULL,
    criteria jsonb NOT NULL,
    redo_required boolean DEFAULT false NOT NULL,
    note text,
    checked_by text NOT NULL,
    checked_at timestamp with time zone DEFAULT now() NOT NULL,
    created_at timestamp with time zone DEFAULT now() NOT NULL,
    CONSTRAINT vh_qc_results_check CHECK (((NOT redo_required) OR (outcome = 'fail'::text))),
    CONSTRAINT vh_qc_results_outcome_check CHECK ((outcome = ANY (ARRAY['pass'::text, 'fail'::text, 'inconclusive'::text])))
);

ALTER TABLE ONLY public.vh_qc_results FORCE ROW LEVEL SECURITY;

--
-- Name: vh_reception_supervisor_messages; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.vh_reception_supervisor_messages (
    id uuid DEFAULT gen_random_uuid() NOT NULL,
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
    created_by text,
    created_at timestamp with time zone DEFAULT now() NOT NULL,
    created_by_agent_id text,
    CONSTRAINT vh_reception_supervisor_messages_author_check CHECK ((num_nonnulls(created_by, created_by_agent_id) = 1)),
    CONSTRAINT vh_reception_supervisor_messages_correlation_id_check CHECK (((length(correlation_id) >= 1) AND (length(correlation_id) <= 200))),
    CONSTRAINT vh_reception_supervisor_messages_direction_check CHECK ((direction = ANY (ARRAY['reception_to_supervisor'::text, 'supervisor_to_reception'::text]))),
    CONSTRAINT vh_reception_supervisor_messages_generation_check CHECK ((ticket_generation >= 0)),
    CONSTRAINT vh_reception_supervisor_messages_hash_check CHECK ((payload_hash ~ '^[0-9a-f]{64}$'::text)),
    CONSTRAINT vh_reception_supervisor_messages_message_id_check CHECK (((length(message_id) >= 1) AND (length(message_id) <= 200))),
    CONSTRAINT vh_reception_supervisor_messages_payload_check CHECK ((jsonb_typeof(payload) = 'object'::text)),
    CONSTRAINT vh_reception_supervisor_messages_response_check CHECK ((jsonb_typeof(response_body) = 'object'::text)),
    CONSTRAINT vh_reception_supervisor_messages_type_check CHECK ((((direction = 'reception_to_supervisor'::text) AND (message_type = ANY (ARRAY['ticket_submitted'::text, 'information_provided'::text, 'plan_approved'::text, 'plan_rejected'::text, 'plan_change_requested'::text, 'cancel_requested'::text]))) OR ((direction = 'supervisor_to_reception'::text) AND (message_type = ANY (ARRAY['accepted'::text, 'in_progress'::text, 'information_requested'::text, 'plan_approval_requested'::text, 'completed'::text, 'failed'::text, 'cancelled'::text])))))
);

ALTER TABLE ONLY public.vh_reception_supervisor_messages FORCE ROW LEVEL SECURITY;

--
-- Name: vh_reception_supervisor_pending; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.vh_reception_supervisor_pending (
    tenant_id uuid NOT NULL,
    ticket_id uuid NOT NULL,
    team_id uuid NOT NULL,
    ticket_generation integer NOT NULL,
    correlation_id text NOT NULL,
    pending_kind text NOT NULL,
    supervisor_message_id text NOT NULL,
    plan_id uuid,
    plan_version bigint,
    created_at timestamp with time zone DEFAULT now() NOT NULL,
    CONSTRAINT vh_reception_supervisor_pending_correlation_check CHECK (((length(correlation_id) >= 1) AND (length(correlation_id) <= 200))),
    CONSTRAINT vh_reception_supervisor_pending_generation_check CHECK ((ticket_generation >= 0)),
    CONSTRAINT vh_reception_supervisor_pending_kind_check CHECK ((pending_kind = ANY (ARRAY['information'::text, 'plan_approval'::text]))),
    CONSTRAINT vh_reception_supervisor_pending_plan_check CHECK ((((pending_kind = 'information'::text) AND (plan_id IS NULL) AND (plan_version IS NULL)) OR ((pending_kind = 'plan_approval'::text) AND (plan_id IS NOT NULL) AND (plan_version IS NOT NULL))))
);

ALTER TABLE ONLY public.vh_reception_supervisor_pending FORCE ROW LEVEL SECURITY;

--
-- Name: vh_report_exports; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.vh_report_exports (
    id uuid DEFAULT gen_random_uuid() NOT NULL,
    tenant_id uuid NOT NULL,
    building_id uuid NOT NULL,
    created_by text NOT NULL,
    kind text NOT NULL,
    filters jsonb NOT NULL,
    status text NOT NULL,
    content bytea,
    error_code text,
    idempotency_key text NOT NULL,
    request_hash text NOT NULL,
    created_at timestamp with time zone DEFAULT now() NOT NULL,
    CONSTRAINT vh_report_exports_check CHECK ((((status = 'ready'::text) AND (content IS NOT NULL)) OR ((status = 'failed'::text) AND (content IS NULL)))),
    CONSTRAINT vh_report_exports_kind_check CHECK ((kind = ANY (ARRAY['incident_frequency'::text, 'issued_revenue'::text]))),
    CONSTRAINT vh_report_exports_status_check CHECK ((status = ANY (ARRAY['ready'::text, 'failed'::text])))
);

ALTER TABLE ONLY public.vh_report_exports FORCE ROW LEVEL SECURITY;

--
-- Name: vh_resident_case_tickets; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.vh_resident_case_tickets (
    tenant_id uuid NOT NULL,
    case_id uuid NOT NULL,
    ticket_id uuid NOT NULL,
    linked_by text NOT NULL,
    created_at timestamp with time zone DEFAULT now() NOT NULL
);

ALTER TABLE ONLY public.vh_resident_case_tickets FORCE ROW LEVEL SECURITY;

--
-- Name: vh_resident_cases; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.vh_resident_cases (
    id uuid DEFAULT gen_random_uuid() NOT NULL,
    tenant_id uuid NOT NULL,
    requester_user_id text NOT NULL,
    unit_id uuid NOT NULL,
    building_id uuid NOT NULL,
    site_id uuid NOT NULL,
    domain_id uuid NOT NULL,
    channel_id text NOT NULL,
    code text NOT NULL,
    title text NOT NULL,
    description text NOT NULL,
    location_description text NOT NULL,
    location_label text NOT NULL,
    status text DEFAULT 'received'::text NOT NULL,
    version bigint DEFAULT 1 NOT NULL,
    current_resolution_id uuid,
    created_at timestamp with time zone DEFAULT now() NOT NULL,
    updated_at timestamp with time zone DEFAULT now() NOT NULL,
    CONSTRAINT vh_resident_cases_check CHECK (((status <> ALL (ARRAY['confirmation'::text, 'completed'::text])) OR (current_resolution_id IS NOT NULL))),
    CONSTRAINT vh_resident_cases_description_check CHECK (((length(description) >= 8) AND (length(description) <= 5000))),
    CONSTRAINT vh_resident_cases_location_description_check CHECK (((length(location_description) >= 3) AND (length(location_description) <= 500))),
    CONSTRAINT vh_resident_cases_status_check CHECK ((status = ANY (ARRAY['received'::text, 'processing'::text, 'confirmation'::text, 'completed'::text]))),
    CONSTRAINT vh_resident_cases_title_check CHECK (((length(title) >= 1) AND (length(title) <= 90))),
    CONSTRAINT vh_resident_cases_version_check CHECK ((version >= 1))
);

ALTER TABLE ONLY public.vh_resident_cases FORCE ROW LEVEL SECURITY;

--
-- Name: vh_resident_command_receipts; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.vh_resident_command_receipts (
    tenant_id uuid NOT NULL,
    actor_id text NOT NULL,
    operation text NOT NULL,
    resource text NOT NULL,
    key text NOT NULL,
    request_hash text NOT NULL,
    response_status integer NOT NULL,
    response_body jsonb NOT NULL,
    result_id uuid NOT NULL,
    created_at timestamp with time zone DEFAULT now() NOT NULL,
    CONSTRAINT vh_resident_command_receipts_key_check CHECK (((length(key) >= 8) AND (length(key) <= 128)))
);

ALTER TABLE ONLY public.vh_resident_command_receipts FORCE ROW LEVEL SECURITY;

--
-- Name: vh_resident_outbox; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.vh_resident_outbox (
    id uuid DEFAULT gen_random_uuid() NOT NULL,
    tenant_id uuid NOT NULL,
    case_id uuid NOT NULL,
    event_id uuid NOT NULL,
    event_type text NOT NULL,
    payload jsonb NOT NULL,
    created_at timestamp with time zone DEFAULT now() NOT NULL,
    delivered_at timestamp with time zone
);

ALTER TABLE ONLY public.vh_resident_outbox FORCE ROW LEVEL SECURITY;

--
-- Name: vh_resident_photos; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.vh_resident_photos (
    tenant_id uuid NOT NULL,
    file_id uuid NOT NULL,
    unit_id uuid NOT NULL,
    uploaded_by text NOT NULL,
    case_id uuid,
    expires_at timestamp with time zone DEFAULT (now() + '24:00:00'::interval) NOT NULL,
    created_at timestamp with time zone DEFAULT now() NOT NULL
);

ALTER TABLE ONLY public.vh_resident_photos FORCE ROW LEVEL SECURITY;

--
-- Name: vh_resident_public_events; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.vh_resident_public_events (
    id uuid DEFAULT gen_random_uuid() NOT NULL,
    tenant_id uuid NOT NULL,
    case_id uuid NOT NULL,
    label text NOT NULL,
    note text,
    occurred_at timestamp with time zone DEFAULT clock_timestamp() NOT NULL
);

ALTER TABLE ONLY public.vh_resident_public_events FORCE ROW LEVEL SECURITY;

--
-- Name: vh_resident_resolution_photos; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.vh_resident_resolution_photos (
    tenant_id uuid NOT NULL,
    resolution_id uuid NOT NULL,
    file_id uuid NOT NULL
);

ALTER TABLE ONLY public.vh_resident_resolution_photos FORCE ROW LEVEL SECURITY;

--
-- Name: vh_resident_resolution_responses; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.vh_resident_resolution_responses (
    id uuid DEFAULT gen_random_uuid() NOT NULL,
    tenant_id uuid NOT NULL,
    case_id uuid NOT NULL,
    resolution_id uuid NOT NULL,
    actor_id text NOT NULL,
    decision text NOT NULL,
    reason text,
    created_at timestamp with time zone DEFAULT now() NOT NULL,
    CONSTRAINT vh_resident_resolution_responses_check CHECK (((decision <> 'reopen'::text) OR ((length(reason) >= 8) AND (length(reason) <= 2000)))),
    CONSTRAINT vh_resident_resolution_responses_decision_check CHECK ((decision = ANY (ARRAY['confirm'::text, 'reopen'::text])))
);

ALTER TABLE ONLY public.vh_resident_resolution_responses FORCE ROW LEVEL SECURITY;

--
-- Name: vh_resident_resolutions; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.vh_resident_resolutions (
    id uuid DEFAULT gen_random_uuid() NOT NULL,
    tenant_id uuid NOT NULL,
    case_id uuid NOT NULL,
    summary text NOT NULL,
    published_by text NOT NULL,
    basis_versions jsonb NOT NULL,
    published_at timestamp with time zone DEFAULT now() NOT NULL,
    CONSTRAINT vh_resident_resolutions_basis_versions_check CHECK ((jsonb_typeof(basis_versions) = 'object'::text)),
    CONSTRAINT vh_resident_resolutions_summary_check CHECK (((length(summary) >= 8) AND (length(summary) <= 5000)))
);

ALTER TABLE ONLY public.vh_resident_resolutions FORCE ROW LEVEL SECURITY;

--
-- Name: vh_resident_submissions; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.vh_resident_submissions (
    id uuid DEFAULT gen_random_uuid() NOT NULL,
    tenant_id uuid NOT NULL,
    case_id uuid NOT NULL,
    submitted_by text NOT NULL,
    description text NOT NULL,
    location_description text NOT NULL,
    created_at timestamp with time zone DEFAULT now() NOT NULL
);

ALTER TABLE ONLY public.vh_resident_submissions FORCE ROW LEVEL SECURITY;

--
-- Name: vh_security_checkpoints; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.vh_security_checkpoints (
    id uuid DEFAULT gen_random_uuid() NOT NULL,
    tenant_id uuid NOT NULL,
    site_id uuid NOT NULL,
    name text NOT NULL,
    location text NOT NULL,
    sort_order integer DEFAULT 0 NOT NULL,
    status text NOT NULL,
    checked_at timestamp with time zone,
    guard_user_id text,
    notes text,
    created_at timestamp with time zone DEFAULT now() NOT NULL,
    updated_at timestamp with time zone DEFAULT now() NOT NULL,
    CONSTRAINT vh_security_checkpoints_status_check CHECK ((status = ANY (ARRAY['pending'::text, 'checked'::text, 'missed'::text])))
);

ALTER TABLE ONLY public.vh_security_checkpoints FORCE ROW LEVEL SECURITY;

--
-- Name: vh_security_handovers; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.vh_security_handovers (
    id uuid DEFAULT gen_random_uuid() NOT NULL,
    tenant_id uuid NOT NULL,
    site_id uuid NOT NULL,
    shift_name text NOT NULL,
    shift_date date NOT NULL,
    payload jsonb NOT NULL,
    from_user_id text NOT NULL,
    to_user_id text NOT NULL,
    confirmed boolean DEFAULT false NOT NULL,
    created_at timestamp with time zone DEFAULT now() NOT NULL,
    updated_at timestamp with time zone DEFAULT now() NOT NULL,
    CONSTRAINT vh_security_handovers_shift_name_check CHECK ((shift_name = ANY (ARRAY['ca_sang'::text, 'ca_chieu'::text, 'ca_dem'::text])))
);

ALTER TABLE ONLY public.vh_security_handovers FORCE ROW LEVEL SECURITY;

--
-- Name: vh_security_incidents; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.vh_security_incidents (
    id uuid DEFAULT gen_random_uuid() NOT NULL,
    tenant_id uuid NOT NULL,
    site_id uuid NOT NULL,
    ticket_id uuid,
    title text NOT NULL,
    location text NOT NULL,
    severity text NOT NULL,
    report jsonb NOT NULL,
    status text NOT NULL,
    reported_by text NOT NULL,
    reported_at timestamp with time zone DEFAULT now() NOT NULL,
    created_at timestamp with time zone DEFAULT now() NOT NULL,
    updated_at timestamp with time zone DEFAULT now() NOT NULL,
    CONSTRAINT vh_security_incidents_severity_check CHECK ((severity = ANY (ARRAY['p1'::text, 'p2'::text, 'p3'::text, 'p4'::text]))),
    CONSTRAINT vh_security_incidents_status_check CHECK ((status = ANY (ARRAY['investigating'::text, 'resolved'::text, 'escalated_to_police'::text])))
);

ALTER TABLE ONLY public.vh_security_incidents FORCE ROW LEVEL SECURITY;

--
-- Name: vh_sensor_readings; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.vh_sensor_readings (
    id uuid DEFAULT gen_random_uuid() NOT NULL,
    tenant_id uuid NOT NULL,
    asset_id uuid NOT NULL,
    parameter text NOT NULL,
    value numeric NOT NULL,
    unit text NOT NULL,
    measured_at timestamp with time zone NOT NULL,
    source text NOT NULL,
    recorded_by text NOT NULL,
    created_at timestamp with time zone DEFAULT now() NOT NULL
);

ALTER TABLE ONLY public.vh_sensor_readings FORCE ROW LEVEL SECURITY;

--
-- Name: vh_technical_measurements; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.vh_technical_measurements (
    id uuid DEFAULT gen_random_uuid() NOT NULL,
    tenant_id uuid NOT NULL,
    work_order_id uuid NOT NULL,
    parameter text NOT NULL,
    value numeric NOT NULL,
    unit text NOT NULL,
    note text NOT NULL,
    recorded_by text NOT NULL,
    measured_at timestamp with time zone NOT NULL,
    created_at timestamp with time zone DEFAULT now() NOT NULL
);

ALTER TABLE ONLY public.vh_technical_measurements FORCE ROW LEVEL SECURITY;

--
-- Name: vh_ticket_plans; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.vh_ticket_plans (
    id uuid DEFAULT gen_random_uuid() NOT NULL,
    tenant_id uuid NOT NULL,
    ticket_id uuid NOT NULL,
    proposed_by text,
    title text NOT NULL,
    steps jsonb NOT NULL,
    estimated_amount numeric(18,2) NOT NULL,
    status text NOT NULL,
    version bigint DEFAULT 0 NOT NULL,
    idempotency_key text NOT NULL,
    request_hash text NOT NULL,
    management_by text,
    management_note text,
    management_at timestamp with time zone,
    resident_by text,
    resident_note text,
    resident_at timestamp with time zone,
    created_at timestamp with time zone DEFAULT now() NOT NULL,
    updated_at timestamp with time zone DEFAULT now() NOT NULL,
    proposed_by_agent_id text,
    proposal jsonb,
    CONSTRAINT vh_ticket_plans_author_check CHECK ((num_nonnulls(proposed_by, proposed_by_agent_id) = 1)),
    CONSTRAINT vh_ticket_plans_estimated_amount_check CHECK ((estimated_amount >= (0)::numeric)),
    CONSTRAINT vh_ticket_plans_status_check CHECK ((status = ANY (ARRAY['management_pending'::text, 'resident_pending'::text, 'approved'::text, 'rejected'::text, 'revision_requested'::text])))
);

ALTER TABLE ONLY public.vh_ticket_plans FORCE ROW LEVEL SECURITY;

--
-- Name: work_approvals; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.work_approvals (
    id uuid DEFAULT gen_random_uuid() NOT NULL,
    tenant_id uuid NOT NULL,
    work_order_id uuid NOT NULL,
    kind text NOT NULL,
    requested_to_user_id text,
    required_scope_id uuid,
    request_detail jsonb NOT NULL,
    status text NOT NULL,
    decided_by text,
    decided_at timestamp with time zone,
    decision_note text,
    expires_at timestamp with time zone,
    created_at timestamp with time zone DEFAULT now() NOT NULL,
    updated_at timestamp with time zone DEFAULT now() NOT NULL,
    evidence_cutoff_at timestamp with time zone,
    request_hash text NOT NULL,
    decided_event_id uuid,
    CONSTRAINT work_approvals_check_0 CHECK ((num_nonnulls(requested_to_user_id, required_scope_id) = 1)),
    CONSTRAINT work_approvals_check_1 CHECK ((kind = ANY (ARRAY['customer_repair'::text, 'management_water_shutdown'::text, 'customer_completion'::text, 'management_security_dispatch'::text, 'management_security_cancel'::text]))),
    CONSTRAINT work_approvals_check_2 CHECK ((status = ANY (ARRAY['pending'::text, 'approved'::text, 'rejected'::text, 'expired'::text, 'cancelled'::text])))
);

ALTER TABLE ONLY public.work_approvals FORCE ROW LEVEL SECURITY;

--
-- Name: work_assignments; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.work_assignments (
    id uuid DEFAULT gen_random_uuid() NOT NULL,
    tenant_id uuid NOT NULL,
    work_order_id uuid NOT NULL,
    staff_id uuid NOT NULL,
    assigned_by_user_id text,
    assigned_by_agent_id text,
    status text NOT NULL,
    offered_at timestamp with time zone NOT NULL,
    accepted_at timestamp with time zone,
    eta_at timestamp with time zone,
    ended_at timestamp with time zone,
    rejection_reason text,
    created_at timestamp with time zone DEFAULT now() NOT NULL,
    updated_at timestamp with time zone DEFAULT now() NOT NULL,
    offer_expires_at timestamp with time zone,
    dispatch_attempt_id uuid,
    CONSTRAINT work_assignments_check_0 CHECK ((status = ANY (ARRAY['offered'::text, 'accepted'::text, 'rejected'::text, 'released'::text, 'completed'::text, 'cancelled'::text])))
);

ALTER TABLE ONLY public.work_assignments FORCE ROW LEVEL SECURITY;

--
-- Name: work_orders; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.work_orders (
    id uuid DEFAULT gen_random_uuid() NOT NULL,
    tenant_id uuid NOT NULL,
    ticket_id uuid NOT NULL,
    category_id uuid NOT NULL,
    description text NOT NULL,
    status text NOT NULL,
    required_specialty_id uuid NOT NULL,
    scheduled_at timestamp with time zone,
    arrived_at timestamp with time zone,
    started_at timestamp with time zone,
    completed_at timestamp with time zone,
    diagnosis text,
    repair_notes text,
    version bigint DEFAULT 0 NOT NULL,
    created_at timestamp with time zone DEFAULT now() NOT NULL,
    updated_at timestamp with time zone DEFAULT now() NOT NULL,
    required boolean DEFAULT true NOT NULL,
    CONSTRAINT work_orders_check_0 CHECK ((status = ANY (ARRAY['queued'::text, 'offered'::text, 'accepted'::text, 'en_route'::text, 'arrived'::text, 'awaiting_approval'::text, 'in_progress'::text, 'completed'::text, 'rejected'::text, 'cancelled'::text])))
);

ALTER TABLE ONLY public.work_orders FORCE ROW LEVEL SECURITY;

--
-- Name: workspace_members; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.workspace_members (
    tenant_id uuid NOT NULL,
    workspace_id uuid NOT NULL,
    user_id text NOT NULL,
    status text NOT NULL,
    joined_at timestamp with time zone NOT NULL,
    left_at timestamp with time zone,
    created_at timestamp with time zone DEFAULT now() NOT NULL
);

ALTER TABLE ONLY public.workspace_members FORCE ROW LEVEL SECURITY;

--
-- Name: workspaces; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.workspaces (
    id uuid DEFAULT gen_random_uuid() NOT NULL,
    tenant_id uuid NOT NULL,
    management_unit_id uuid NOT NULL,
    code text NOT NULL,
    name text NOT NULL,
    status text NOT NULL,
    created_at timestamp with time zone DEFAULT now() NOT NULL,
    updated_at timestamp with time zone DEFAULT now() NOT NULL
);

ALTER TABLE ONLY public.workspaces FORCE ROW LEVEL SECURITY;

--
-- Name: zones; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.zones (
    id uuid DEFAULT gen_random_uuid() NOT NULL,
    tenant_id uuid NOT NULL,
    site_id uuid NOT NULL,
    code text NOT NULL,
    name text NOT NULL,
    status text NOT NULL,
    created_at timestamp with time zone DEFAULT now() NOT NULL,
    updated_at timestamp with time zone DEFAULT now() NOT NULL
);

ALTER TABLE ONLY public.zones FORCE ROW LEVEL SECURITY;

--
--
