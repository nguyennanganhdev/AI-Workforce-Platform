-- Domain Vinhomes database. Generated once from the running schema, then kept by hand.
-- Every table has tenant_id and row level security that is forced; the API runs as a role that cannot bypass it.

--
--

--
-- Name: access_scopes access_scopes_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.access_scopes
    ADD CONSTRAINT access_scopes_pkey PRIMARY KEY (id);

--
-- Name: access_scopes access_scopes_tenant_key_uq; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.access_scopes
    ADD CONSTRAINT access_scopes_tenant_key_uq UNIQUE (tenant_id, id);

--
-- Name: account_reviews account_reviews_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.account_reviews
    ADD CONSTRAINT account_reviews_pkey PRIMARY KEY (id);

--
-- Name: account_reviews account_reviews_tenant_key_uq; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.account_reviews
    ADD CONSTRAINT account_reviews_tenant_key_uq UNIQUE (tenant_id, id);

--
-- Name: accounts accounts_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.accounts
    ADD CONSTRAINT accounts_pkey PRIMARY KEY (id);

--
-- Name: accounts accounts_unique_0; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.accounts
    ADD CONSTRAINT accounts_unique_0 UNIQUE (provider_id, account_id);

--
-- Name: agent_releases agent_releases_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.agent_releases
    ADD CONSTRAINT agent_releases_pkey PRIMARY KEY (id);

--
-- Name: agent_releases agent_releases_tenant_key_uq; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.agent_releases
    ADD CONSTRAINT agent_releases_tenant_key_uq UNIQUE (tenant_id, id);

--
-- Name: agent_runs agent_runs_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.agent_runs
    ADD CONSTRAINT agent_runs_pkey PRIMARY KEY (id);

--
-- Name: agent_runs agent_runs_tenant_key_uq; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.agent_runs
    ADD CONSTRAINT agent_runs_tenant_key_uq UNIQUE (tenant_id, id);

--
-- Name: agent_runs agent_runs_unique_0; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.agent_runs
    ADD CONSTRAINT agent_runs_unique_0 UNIQUE (tenant_id, idempotency_key);

--
-- Name: agent_teams agent_teams_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.agent_teams
    ADD CONSTRAINT agent_teams_pkey PRIMARY KEY (id);

--
-- Name: agent_teams agent_teams_tenant_key_uq; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.agent_teams
    ADD CONSTRAINT agent_teams_tenant_key_uq UNIQUE (tenant_id, id);

--
-- Name: agent_teams agent_teams_unique_0; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.agent_teams
    ADD CONSTRAINT agent_teams_unique_0 UNIQUE (ticket_id, ticket_generation);

--
-- Name: agent_teams agent_teams_unique_1; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.agent_teams
    ADD CONSTRAINT agent_teams_unique_1 UNIQUE (workspace_id, request_message_id);

--
-- Name: agent_versions agent_versions_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.agent_versions
    ADD CONSTRAINT agent_versions_pkey PRIMARY KEY (id);

--
-- Name: agent_versions agent_versions_tenant_key_uq; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.agent_versions
    ADD CONSTRAINT agent_versions_tenant_key_uq UNIQUE (tenant_id, id);

--
-- Name: agent_versions agent_versions_unique_0; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.agent_versions
    ADD CONSTRAINT agent_versions_unique_0 UNIQUE (agent_id, version_no);

--
-- Name: agents agents_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.agents
    ADD CONSTRAINT agents_pkey PRIMARY KEY (id);

--
-- Name: agents agents_tenant_key_uq; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.agents
    ADD CONSTRAINT agents_tenant_key_uq UNIQUE (tenant_id, id);

--
-- Name: audit_events audit_events_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.audit_events
    ADD CONSTRAINT audit_events_pkey PRIMARY KEY (id);

--
-- Name: audit_events audit_events_tenant_key_uq; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.audit_events
    ADD CONSTRAINT audit_events_tenant_key_uq UNIQUE (tenant_id, id);

--
-- Name: buildings buildings_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.buildings
    ADD CONSTRAINT buildings_pkey PRIMARY KEY (id);

--
-- Name: buildings buildings_tenant_key_uq; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.buildings
    ADD CONSTRAINT buildings_tenant_key_uq UNIQUE (tenant_id, id);

--
-- Name: buildings buildings_unique_0; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.buildings
    ADD CONSTRAINT buildings_unique_0 UNIQUE (site_id, code);

--
-- Name: channel_agents channel_agents_channel_id_agent_id_pk; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.channel_agents
    ADD CONSTRAINT channel_agents_channel_id_agent_id_pk PRIMARY KEY (channel_id, agent_id);

--
-- Name: channel_memberships channel_memberships_channel_id_user_id_pk; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.channel_memberships
    ADD CONSTRAINT channel_memberships_channel_id_user_id_pk PRIMARY KEY (channel_id, user_id);

--
-- Name: channels channels_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.channels
    ADD CONSTRAINT channels_pkey PRIMARY KEY (id);

--
-- Name: channels channels_tenant_key_uq; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.channels
    ADD CONSTRAINT channels_tenant_key_uq UNIQUE (tenant_id, id);

--
-- Name: dispatch_attempts dispatch_attempts_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.dispatch_attempts
    ADD CONSTRAINT dispatch_attempts_pkey PRIMARY KEY (id);

--
-- Name: dispatch_attempts dispatch_attempts_tenant_key_uq; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.dispatch_attempts
    ADD CONSTRAINT dispatch_attempts_tenant_key_uq UNIQUE (tenant_id, id);

--
-- Name: dispatch_attempts dispatch_attempts_unique_0; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.dispatch_attempts
    ADD CONSTRAINT dispatch_attempts_unique_0 UNIQUE (queue_id, idempotency_key);

--
-- Name: dispatch_attempts dispatch_attempts_unique_1; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.dispatch_attempts
    ADD CONSTRAINT dispatch_attempts_unique_1 UNIQUE (queue_id, fencing_token);

--
-- Name: dispatch_queue dispatch_queue_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.dispatch_queue
    ADD CONSTRAINT dispatch_queue_pkey PRIMARY KEY (id);

--
-- Name: dispatch_queue dispatch_queue_tenant_key_uq; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.dispatch_queue
    ADD CONSTRAINT dispatch_queue_tenant_key_uq UNIQUE (tenant_id, id);

--
-- Name: dispatch_queue dispatch_queue_unique_0; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.dispatch_queue
    ADD CONSTRAINT dispatch_queue_unique_0 UNIQUE (work_order_id);

--
-- Name: domains domains_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.domains
    ADD CONSTRAINT domains_pkey PRIMARY KEY (id);

--
-- Name: domains domains_tenant_key_uq; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.domains
    ADD CONSTRAINT domains_tenant_key_uq UNIQUE (tenant_id, id);

--
-- Name: domains domains_unique_0; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.domains
    ADD CONSTRAINT domains_unique_0 UNIQUE (tenant_id, code);

--
-- Name: event_inbox event_inbox_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.event_inbox
    ADD CONSTRAINT event_inbox_pkey PRIMARY KEY (id);

--
-- Name: event_inbox event_inbox_tenant_key_uq; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.event_inbox
    ADD CONSTRAINT event_inbox_tenant_key_uq UNIQUE (tenant_id, id);

--
-- Name: event_inbox event_inbox_unique_0; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.event_inbox
    ADD CONSTRAINT event_inbox_unique_0 UNIQUE (tenant_id, consumer, event_id);

--
-- Name: event_outbox event_outbox_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.event_outbox
    ADD CONSTRAINT event_outbox_pkey PRIMARY KEY (id);

--
-- Name: event_outbox event_outbox_tenant_key_uq; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.event_outbox
    ADD CONSTRAINT event_outbox_tenant_key_uq UNIQUE (tenant_id, id);

--
-- Name: event_outbox event_outbox_unique_0; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.event_outbox
    ADD CONSTRAINT event_outbox_unique_0 UNIQUE (event_id, topic);

--
-- Name: evidence_items evidence_items_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.evidence_items
    ADD CONSTRAINT evidence_items_pkey PRIMARY KEY (id);

--
-- Name: evidence_items evidence_items_tenant_key_uq; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.evidence_items
    ADD CONSTRAINT evidence_items_tenant_key_uq UNIQUE (tenant_id, id);

--
-- Name: evidence_items evidence_items_unique_0; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.evidence_items
    ADD CONSTRAINT evidence_items_unique_0 UNIQUE (ticket_id, file_id, purpose);

--
-- Name: execution_principals execution_principals_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.execution_principals
    ADD CONSTRAINT execution_principals_pkey PRIMARY KEY (id);

--
-- Name: execution_principals execution_principals_tenant_key_uq; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.execution_principals
    ADD CONSTRAINT execution_principals_tenant_key_uq UNIQUE (tenant_id, id);

--
-- Name: file_objects file_objects_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.file_objects
    ADD CONSTRAINT file_objects_pkey PRIMARY KEY (id);

--
-- Name: file_objects file_objects_tenant_key_uq; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.file_objects
    ADD CONSTRAINT file_objects_tenant_key_uq UNIQUE (tenant_id, id);

--
-- Name: file_objects file_objects_unique_0; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.file_objects
    ADD CONSTRAINT file_objects_unique_0 UNIQUE (location_id, object_key, version_id);

--
-- Name: file_objects file_objects_unique_1; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.file_objects
    ADD CONSTRAINT file_objects_unique_1 UNIQUE (file_id, variant, variant_revision);

--
-- Name: file_uploads file_uploads_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.file_uploads
    ADD CONSTRAINT file_uploads_pkey PRIMARY KEY (id);

--
-- Name: file_uploads file_uploads_tenant_key_uq; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.file_uploads
    ADD CONSTRAINT file_uploads_tenant_key_uq UNIQUE (tenant_id, id);

--
-- Name: file_uploads file_uploads_unique_0; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.file_uploads
    ADD CONSTRAINT file_uploads_unique_0 UNIQUE (tenant_id, requested_by, idempotency_key);

--
-- Name: file_uploads file_uploads_unique_1; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.file_uploads
    ADD CONSTRAINT file_uploads_unique_1 UNIQUE (location_id, staging_key);

--
-- Name: files files_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.files
    ADD CONSTRAINT files_pkey PRIMARY KEY (id);

--
-- Name: files files_tenant_key_uq; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.files
    ADD CONSTRAINT files_tenant_key_uq UNIQUE (tenant_id, id);

--
-- Name: incident_types incident_types_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.incident_types
    ADD CONSTRAINT incident_types_pkey PRIMARY KEY (id);

--
-- Name: incident_types incident_types_tenant_key_uq; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.incident_types
    ADD CONSTRAINT incident_types_tenant_key_uq UNIQUE (tenant_id, id);

--
-- Name: incident_types incident_types_unique_0; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.incident_types
    ADD CONSTRAINT incident_types_unique_0 UNIQUE (tenant_id, code);

--
-- Name: interruption_scopes interruption_scopes_tenant_id_interruption_id_scope_id_pk; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.interruption_scopes
    ADD CONSTRAINT interruption_scopes_tenant_id_interruption_id_scope_id_pk PRIMARY KEY (tenant_id, interruption_id, scope_id);

--
-- Name: invoice_lines invoice_lines_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.invoice_lines
    ADD CONSTRAINT invoice_lines_pkey PRIMARY KEY (id);

--
-- Name: invoice_lines invoice_lines_tenant_key_uq; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.invoice_lines
    ADD CONSTRAINT invoice_lines_tenant_key_uq UNIQUE (tenant_id, id);

--
-- Name: invoice_lines invoice_lines_unique_0; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.invoice_lines
    ADD CONSTRAINT invoice_lines_unique_0 UNIQUE (invoice_id, line_no);

--
-- Name: invoices invoices_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.invoices
    ADD CONSTRAINT invoices_pkey PRIMARY KEY (id);

--
-- Name: invoices invoices_tenant_key_uq; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.invoices
    ADD CONSTRAINT invoices_tenant_key_uq UNIQUE (tenant_id, id);

--
-- Name: invoices invoices_unique_0; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.invoices
    ADD CONSTRAINT invoices_unique_0 UNIQUE (tenant_id, invoice_no);

--
-- Name: invoices invoices_unique_1; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.invoices
    ADD CONSTRAINT invoices_unique_1 UNIQUE (provider, provider_account_ref, provider_invoice_id);

--
-- Name: management_coverage management_coverage_period_excl; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.management_coverage
    ADD CONSTRAINT management_coverage_period_excl EXCLUDE USING gist (scope_id WITH =, service_category_id WITH =, tstzrange(valid_from, valid_to, '[)'::text) WITH &&);

--
-- Name: management_coverage management_coverage_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.management_coverage
    ADD CONSTRAINT management_coverage_pkey PRIMARY KEY (id);

--
-- Name: management_coverage management_coverage_tenant_key_uq; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.management_coverage
    ADD CONSTRAINT management_coverage_tenant_key_uq UNIQUE (tenant_id, id);

--
-- Name: management_units management_units_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.management_units
    ADD CONSTRAINT management_units_pkey PRIMARY KEY (id);

--
-- Name: management_units management_units_tenant_key_uq; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.management_units
    ADD CONSTRAINT management_units_tenant_key_uq UNIQUE (tenant_id, id);

--
-- Name: management_units management_units_unique_0; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.management_units
    ADD CONSTRAINT management_units_unique_0 UNIQUE (tenant_id, code);

--
-- Name: message_files message_files_tenant_id_message_id_file_id_pk; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.message_files
    ADD CONSTRAINT message_files_tenant_id_message_id_file_id_pk PRIMARY KEY (tenant_id, message_id, file_id);

--
-- Name: message_files message_files_unique_0; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.message_files
    ADD CONSTRAINT message_files_unique_0 UNIQUE (message_id, ordinal);

--
-- Name: messages messages_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.messages
    ADD CONSTRAINT messages_pkey PRIMARY KEY (id);

--
-- Name: messages messages_tenant_key_uq; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.messages
    ADD CONSTRAINT messages_tenant_key_uq UNIQUE (tenant_id, id);

--
-- Name: messages messages_unique_0; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.messages
    ADD CONSTRAINT messages_unique_0 UNIQUE (channel_id, seq);

--
-- Name: messages messages_unique_1; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.messages
    ADD CONSTRAINT messages_unique_1 UNIQUE (channel_id, sender_user_id, client_message_id);

--
-- Name: messages messages_unique_2; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.messages
    ADD CONSTRAINT messages_unique_2 UNIQUE (channel_id, source_event_id, sender_agent_id);

--
-- Name: notification_deliveries notification_deliveries_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.notification_deliveries
    ADD CONSTRAINT notification_deliveries_pkey PRIMARY KEY (id);

--
-- Name: notification_deliveries notification_deliveries_tenant_key_uq; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.notification_deliveries
    ADD CONSTRAINT notification_deliveries_tenant_key_uq UNIQUE (tenant_id, id);

--
-- Name: notification_deliveries notification_deliveries_unique_0; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.notification_deliveries
    ADD CONSTRAINT notification_deliveries_unique_0 UNIQUE (tenant_id, user_id, channel, dedupe_key);

--
-- Name: payment_allocations payment_allocations_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.payment_allocations
    ADD CONSTRAINT payment_allocations_pkey PRIMARY KEY (id);

--
-- Name: payment_allocations payment_allocations_tenant_key_uq; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.payment_allocations
    ADD CONSTRAINT payment_allocations_tenant_key_uq UNIQUE (tenant_id, id);

--
-- Name: payment_allocations payment_allocations_unique_0; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.payment_allocations
    ADD CONSTRAINT payment_allocations_unique_0 UNIQUE (tenant_id, idempotency_key);

--
-- Name: payment_intents payment_intents_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.payment_intents
    ADD CONSTRAINT payment_intents_pkey PRIMARY KEY (id);

--
-- Name: payment_intents payment_intents_tenant_key_uq; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.payment_intents
    ADD CONSTRAINT payment_intents_tenant_key_uq UNIQUE (tenant_id, id);

--
-- Name: payment_intents payment_intents_unique_0; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.payment_intents
    ADD CONSTRAINT payment_intents_unique_0 UNIQUE (tenant_id, idempotency_key);

--
-- Name: payment_intents payment_intents_unique_1; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.payment_intents
    ADD CONSTRAINT payment_intents_unique_1 UNIQUE (provider, merchant_account_ref, provider_intent_id);

--
-- Name: payment_webhook_receipts payment_webhook_receipts_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.payment_webhook_receipts
    ADD CONSTRAINT payment_webhook_receipts_pkey PRIMARY KEY (id);

--
-- Name: payment_webhook_receipts payment_webhook_receipts_tenant_key_uq; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.payment_webhook_receipts
    ADD CONSTRAINT payment_webhook_receipts_tenant_key_uq UNIQUE (tenant_id, id);

--
-- Name: payment_webhook_receipts payment_webhook_receipts_unique_0; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.payment_webhook_receipts
    ADD CONSTRAINT payment_webhook_receipts_unique_0 UNIQUE (provider, merchant_account_ref, provider_event_id);

--
-- Name: payments payments_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.payments
    ADD CONSTRAINT payments_pkey PRIMARY KEY (id);

--
-- Name: payments payments_tenant_key_uq; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.payments
    ADD CONSTRAINT payments_tenant_key_uq UNIQUE (tenant_id, id);

--
-- Name: payments payments_unique_0; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.payments
    ADD CONSTRAINT payments_unique_0 UNIQUE (provider, merchant_account_ref, provider_transaction_id);

--
-- Name: platform_admins platform_admins_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.platform_admins
    ADD CONSTRAINT platform_admins_pkey PRIMARY KEY (user_id);

--
-- Name: runtime_backends runtime_backends_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.runtime_backends
    ADD CONSTRAINT runtime_backends_pkey PRIMARY KEY (id);

--
-- Name: runtime_backends runtime_backends_unique_0; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.runtime_backends
    ADD CONSTRAINT runtime_backends_unique_0 UNIQUE (code);

--
-- Name: runtime_identities runtime_identities_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.runtime_identities
    ADD CONSTRAINT runtime_identities_pkey PRIMARY KEY (id);

--
-- Name: runtime_identities runtime_identities_tenant_key_uq; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.runtime_identities
    ADD CONSTRAINT runtime_identities_tenant_key_uq UNIQUE (tenant_id, id);

--
-- Name: runtime_identities runtime_identities_unique_0; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.runtime_identities
    ADD CONSTRAINT runtime_identities_unique_0 UNIQUE (backend_id, principal_id);

--
-- Name: runtime_identities runtime_identities_unique_1; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.runtime_identities
    ADD CONSTRAINT runtime_identities_unique_1 UNIQUE (backend_id, runtime_user_key);

--
-- Name: runtime_identities runtime_identities_unique_2; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.runtime_identities
    ADD CONSTRAINT runtime_identities_unique_2 UNIQUE (tenant_id, id, backend_id);

--
-- Name: runtime_session_bindings runtime_session_bindings_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.runtime_session_bindings
    ADD CONSTRAINT runtime_session_bindings_pkey PRIMARY KEY (id);

--
-- Name: runtime_session_bindings runtime_session_bindings_tenant_key_uq; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.runtime_session_bindings
    ADD CONSTRAINT runtime_session_bindings_tenant_key_uq UNIQUE (tenant_id, id);

--
-- Name: runtime_session_bindings runtime_session_bindings_unique_2; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.runtime_session_bindings
    ADD CONSTRAINT runtime_session_bindings_unique_2 UNIQUE (backend_id, runtime_session_key);

--
-- Name: scoped_user_roles scoped_role_period_excl; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.scoped_user_roles
    ADD CONSTRAINT scoped_role_period_excl EXCLUDE USING gist (membership_id WITH =, scope_id WITH =, role_code WITH =, tstzrange(valid_from, valid_to, '[)'::text) WITH &&);

--
-- Name: scoped_user_roles scoped_user_roles_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.scoped_user_roles
    ADD CONSTRAINT scoped_user_roles_pkey PRIMARY KEY (id);

--
-- Name: scoped_user_roles scoped_user_roles_tenant_key_uq; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.scoped_user_roles
    ADD CONSTRAINT scoped_user_roles_tenant_key_uq UNIQUE (tenant_id, id);

--
-- Name: scoped_user_roles scoped_user_roles_unique_0; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.scoped_user_roles
    ADD CONSTRAINT scoped_user_roles_unique_0 UNIQUE (membership_id, scope_id, role_code, valid_from);

--
-- Name: security_alert_deliveries security_alert_deliveries_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.security_alert_deliveries
    ADD CONSTRAINT security_alert_deliveries_pkey PRIMARY KEY (id);

--
-- Name: security_alerts security_alerts_idempotency; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.security_alerts
    ADD CONSTRAINT security_alerts_idempotency UNIQUE (tenant_id, ticket_id, idempotency_key);

--
-- Name: security_alerts security_alerts_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.security_alerts
    ADD CONSTRAINT security_alerts_pkey PRIMARY KEY (id);

--
-- Name: security_alerts security_alerts_tenant_key; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.security_alerts
    ADD CONSTRAINT security_alerts_tenant_key UNIQUE (tenant_id, id);

--
-- Name: security_cameras security_cameras_code; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.security_cameras
    ADD CONSTRAINT security_cameras_code UNIQUE (tenant_id, building_id, code);

--
-- Name: security_cameras security_cameras_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.security_cameras
    ADD CONSTRAINT security_cameras_pkey PRIMARY KEY (id);

--
-- Name: security_cameras security_cameras_tenant_key; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.security_cameras
    ADD CONSTRAINT security_cameras_tenant_key UNIQUE (tenant_id, id);

--
-- Name: security_emergency_contacts security_contacts_order; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.security_emergency_contacts
    ADD CONSTRAINT security_contacts_order UNIQUE (tenant_id, building_id, "position");

--
-- Name: security_emergency_contacts security_contacts_tenant_key; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.security_emergency_contacts
    ADD CONSTRAINT security_contacts_tenant_key UNIQUE (tenant_id, id);

--
-- Name: security_alert_deliveries security_deliveries_order; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.security_alert_deliveries
    ADD CONSTRAINT security_deliveries_order UNIQUE (tenant_id, alert_id, "position");

--
-- Name: security_alert_deliveries security_deliveries_tenant_key; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.security_alert_deliveries
    ADD CONSTRAINT security_deliveries_tenant_key UNIQUE (tenant_id, id);

--
-- Name: security_emergency_contacts security_emergency_contacts_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.security_emergency_contacts
    ADD CONSTRAINT security_emergency_contacts_pkey PRIMARY KEY (id);

--
-- Name: service_categories service_categories_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.service_categories
    ADD CONSTRAINT service_categories_pkey PRIMARY KEY (id);

--
-- Name: service_categories service_categories_tenant_key_uq; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.service_categories
    ADD CONSTRAINT service_categories_tenant_key_uq UNIQUE (tenant_id, id);

--
-- Name: service_categories service_categories_unique_0; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.service_categories
    ADD CONSTRAINT service_categories_unique_0 UNIQUE (tenant_id, code);

--
-- Name: service_interruptions service_interruptions_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.service_interruptions
    ADD CONSTRAINT service_interruptions_pkey PRIMARY KEY (id);

--
-- Name: service_interruptions service_interruptions_tenant_key_uq; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.service_interruptions
    ADD CONSTRAINT service_interruptions_tenant_key_uq UNIQUE (tenant_id, id);

--
-- Name: sessions sessions_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.sessions
    ADD CONSTRAINT sessions_pkey PRIMARY KEY (id);

--
-- Name: sessions sessions_unique_0; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.sessions
    ADD CONSTRAINT sessions_unique_0 UNIQUE (token);

--
-- Name: sites sites_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.sites
    ADD CONSTRAINT sites_pkey PRIMARY KEY (id);

--
-- Name: sites sites_tenant_key_uq; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.sites
    ADD CONSTRAINT sites_tenant_key_uq UNIQUE (tenant_id, id);

--
-- Name: sites sites_unique_0; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.sites
    ADD CONSTRAINT sites_unique_0 UNIQUE (domain_id, code);

--
-- Name: sla_policies sla_policies_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.sla_policies
    ADD CONSTRAINT sla_policies_pkey PRIMARY KEY (id);

--
-- Name: sla_policies sla_policies_tenant_key_uq; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.sla_policies
    ADD CONSTRAINT sla_policies_tenant_key_uq UNIQUE (tenant_id, id);

--
-- Name: sla_policies sla_policies_unique_0; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.sla_policies
    ADD CONSTRAINT sla_policies_unique_0 UNIQUE (tenant_id, domain_id, management_unit_id, category_id, request_kind, priority, version_no);

--
-- Name: sla_policies sla_policy_period_excl; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.sla_policies
    ADD CONSTRAINT sla_policy_period_excl EXCLUDE USING gist (tenant_id WITH =, domain_id WITH =, management_unit_id WITH =, category_id WITH =, request_kind WITH =, priority WITH =, tstzrange(effective_from, effective_to, '[)'::text) WITH &&);

--
-- Name: staff_profiles staff_profiles_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.staff_profiles
    ADD CONSTRAINT staff_profiles_pkey PRIMARY KEY (id);

--
-- Name: staff_profiles staff_profiles_tenant_key_uq; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.staff_profiles
    ADD CONSTRAINT staff_profiles_tenant_key_uq UNIQUE (tenant_id, id);

--
-- Name: staff_profiles staff_profiles_unique_0; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.staff_profiles
    ADD CONSTRAINT staff_profiles_unique_0 UNIQUE (tenant_id, user_id);

--
-- Name: staff_profiles staff_profiles_unique_1; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.staff_profiles
    ADD CONSTRAINT staff_profiles_unique_1 UNIQUE (tenant_id, employee_code);

--
-- Name: staff_shifts staff_shifts_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.staff_shifts
    ADD CONSTRAINT staff_shifts_pkey PRIMARY KEY (id);

--
-- Name: staff_shifts staff_shifts_tenant_key_uq; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.staff_shifts
    ADD CONSTRAINT staff_shifts_tenant_key_uq UNIQUE (tenant_id, id);

--
-- Name: staff_specialties staff_specialties_tenant_id_staff_id_category_id_pk; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.staff_specialties
    ADD CONSTRAINT staff_specialties_tenant_id_staff_id_category_id_pk PRIMARY KEY (tenant_id, staff_id, category_id);

--
-- Name: storage_locations storage_locations_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.storage_locations
    ADD CONSTRAINT storage_locations_pkey PRIMARY KEY (id);

--
-- Name: storage_locations storage_locations_tenant_key_uq; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.storage_locations
    ADD CONSTRAINT storage_locations_tenant_key_uq UNIQUE (tenant_id, id);

--
-- Name: storage_locations storage_locations_unique_0; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.storage_locations
    ADD CONSTRAINT storage_locations_unique_0 UNIQUE (endpoint_ref, bucket_name, tenant_prefix);

--
-- Name: team_members team_members_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.team_members
    ADD CONSTRAINT team_members_pkey PRIMARY KEY (id);

--
-- Name: team_members team_members_tenant_key_uq; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.team_members
    ADD CONSTRAINT team_members_tenant_key_uq UNIQUE (tenant_id, id);

--
-- Name: team_members team_members_unique_0; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.team_members
    ADD CONSTRAINT team_members_unique_0 UNIQUE (team_id, agent_id);

--
-- Name: team_members team_members_unique_1; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.team_members
    ADD CONSTRAINT team_members_unique_1 UNIQUE (binding_id);

--
-- Name: tenant_memberships tenant_memberships_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.tenant_memberships
    ADD CONSTRAINT tenant_memberships_pkey PRIMARY KEY (id);

--
-- Name: tenant_memberships tenant_memberships_tenant_key_uq; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.tenant_memberships
    ADD CONSTRAINT tenant_memberships_tenant_key_uq UNIQUE (tenant_id, id);

--
-- Name: tenant_memberships tenant_memberships_unique_0; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.tenant_memberships
    ADD CONSTRAINT tenant_memberships_unique_0 UNIQUE (tenant_id, user_id);

--
-- Name: tenants tenants_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.tenants
    ADD CONSTRAINT tenants_pkey PRIMARY KEY (id);

--
-- Name: tenants tenants_unique_0; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.tenants
    ADD CONSTRAINT tenants_unique_0 UNIQUE (code);

--
-- Name: ticket_assessments ticket_assessments_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.ticket_assessments
    ADD CONSTRAINT ticket_assessments_pkey PRIMARY KEY (id);

--
-- Name: ticket_assessments ticket_assessments_tenant_key_uq; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.ticket_assessments
    ADD CONSTRAINT ticket_assessments_tenant_key_uq UNIQUE (tenant_id, id);

--
-- Name: ticket_assessments ticket_assessments_unique_0; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.ticket_assessments
    ADD CONSTRAINT ticket_assessments_unique_0 UNIQUE (ticket_id, idempotency_key);

--
-- Name: ticket_escalations ticket_escalations_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.ticket_escalations
    ADD CONSTRAINT ticket_escalations_pkey PRIMARY KEY (id);

--
-- Name: ticket_escalations ticket_escalations_tenant_key_uq; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.ticket_escalations
    ADD CONSTRAINT ticket_escalations_tenant_key_uq UNIQUE (tenant_id, id);

--
-- Name: ticket_escalations ticket_escalations_unique_0; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.ticket_escalations
    ADD CONSTRAINT ticket_escalations_unique_0 UNIQUE (ticket_id, dedupe_key);

--
-- Name: ticket_events ticket_events_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.ticket_events
    ADD CONSTRAINT ticket_events_pkey PRIMARY KEY (id);

--
-- Name: ticket_events ticket_events_tenant_key_uq; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.ticket_events
    ADD CONSTRAINT ticket_events_tenant_key_uq UNIQUE (tenant_id, id);

--
-- Name: ticket_events ticket_events_unique_0; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.ticket_events
    ADD CONSTRAINT ticket_events_unique_0 UNIQUE (ticket_id, seq);

--
-- Name: ticket_events ticket_events_unique_1; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.ticket_events
    ADD CONSTRAINT ticket_events_unique_1 UNIQUE (ticket_id, idempotency_key);

--
-- Name: ticket_files ticket_files_tenant_id_ticket_id_file_id_pk; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.ticket_files
    ADD CONSTRAINT ticket_files_tenant_id_ticket_id_file_id_pk PRIMARY KEY (tenant_id, ticket_id, file_id);

--
-- Name: ticket_reviews ticket_reviews_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.ticket_reviews
    ADD CONSTRAINT ticket_reviews_pkey PRIMARY KEY (id);

--
-- Name: ticket_reviews ticket_reviews_tenant_key_uq; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.ticket_reviews
    ADD CONSTRAINT ticket_reviews_tenant_key_uq UNIQUE (tenant_id, id);

--
-- Name: ticket_reviews ticket_reviews_unique_0; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.ticket_reviews
    ADD CONSTRAINT ticket_reviews_unique_0 UNIQUE (ticket_id, assignment_id, reviewer_user_id);

--
-- Name: ticket_routing_history ticket_routing_history_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.ticket_routing_history
    ADD CONSTRAINT ticket_routing_history_pkey PRIMARY KEY (id);

--
-- Name: ticket_routing_history ticket_routing_history_tenant_key_uq; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.ticket_routing_history
    ADD CONSTRAINT ticket_routing_history_tenant_key_uq UNIQUE (tenant_id, id);

--
-- Name: ticket_sla_adjustments ticket_sla_adjustments_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.ticket_sla_adjustments
    ADD CONSTRAINT ticket_sla_adjustments_pkey PRIMARY KEY (id);

--
-- Name: ticket_sla_adjustments ticket_sla_adjustments_tenant_key_uq; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.ticket_sla_adjustments
    ADD CONSTRAINT ticket_sla_adjustments_tenant_key_uq UNIQUE (tenant_id, id);

--
-- Name: ticket_sla_adjustments ticket_sla_adjustments_unique_0; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.ticket_sla_adjustments
    ADD CONSTRAINT ticket_sla_adjustments_unique_0 UNIQUE (cycle_id, idempotency_key);

--
-- Name: ticket_sla_adjustments ticket_sla_adjustments_unique_1; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.ticket_sla_adjustments
    ADD CONSTRAINT ticket_sla_adjustments_unique_1 UNIQUE (cycle_id, decision_id);

--
-- Name: ticket_sla_cycles ticket_sla_cycles_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.ticket_sla_cycles
    ADD CONSTRAINT ticket_sla_cycles_pkey PRIMARY KEY (id);

--
-- Name: ticket_sla_cycles ticket_sla_cycles_tenant_key_uq; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.ticket_sla_cycles
    ADD CONSTRAINT ticket_sla_cycles_tenant_key_uq UNIQUE (tenant_id, id);

--
-- Name: ticket_sla_cycles ticket_sla_cycles_unique_0; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.ticket_sla_cycles
    ADD CONSTRAINT ticket_sla_cycles_unique_0 UNIQUE (ticket_id, ticket_generation);

--
-- Name: ticket_triage_decisions ticket_triage_decisions_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.ticket_triage_decisions
    ADD CONSTRAINT ticket_triage_decisions_pkey PRIMARY KEY (id);

--
-- Name: ticket_triage_decisions ticket_triage_decisions_tenant_key_uq; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.ticket_triage_decisions
    ADD CONSTRAINT ticket_triage_decisions_tenant_key_uq UNIQUE (tenant_id, id);

--
-- Name: ticket_triage_decisions ticket_triage_decisions_unique_0; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.ticket_triage_decisions
    ADD CONSTRAINT ticket_triage_decisions_unique_0 UNIQUE (ticket_id, decision_seq);

--
-- Name: ticket_triage_decisions ticket_triage_decisions_unique_1; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.ticket_triage_decisions
    ADD CONSTRAINT ticket_triage_decisions_unique_1 UNIQUE (ticket_id, idempotency_key);

--
-- Name: ticket_triage_reviews ticket_triage_reviews_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.ticket_triage_reviews
    ADD CONSTRAINT ticket_triage_reviews_pkey PRIMARY KEY (id);

--
-- Name: ticket_triage_reviews ticket_triage_reviews_tenant_key_uq; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.ticket_triage_reviews
    ADD CONSTRAINT ticket_triage_reviews_tenant_key_uq UNIQUE (tenant_id, id);

--
-- Name: ticket_triage_reviews ticket_triage_reviews_unique_0; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.ticket_triage_reviews
    ADD CONSTRAINT ticket_triage_reviews_unique_0 UNIQUE (pending_decision_id);

--
-- Name: tickets tickets_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.tickets
    ADD CONSTRAINT tickets_pkey PRIMARY KEY (id);

--
-- Name: tickets tickets_tenant_key_uq; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.tickets
    ADD CONSTRAINT tickets_tenant_key_uq UNIQUE (tenant_id, id);

--
-- Name: tickets tickets_unique_0; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.tickets
    ADD CONSTRAINT tickets_unique_0 UNIQUE (tenant_id, code);

--
-- Name: triage_policy_bindings triage_binding_category_excl; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.triage_policy_bindings
    ADD CONSTRAINT triage_binding_category_excl EXCLUDE USING gist (tenant_id WITH =, domain_id WITH =, scope_id WITH =, category_id WITH =, request_kind WITH =, tstzrange(valid_from, valid_to, '[)'::text) WITH &&) WHERE (((status = 'active'::text) AND (category_id IS NOT NULL)));

--
-- Name: triage_policy_bindings triage_binding_fallback_excl; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.triage_policy_bindings
    ADD CONSTRAINT triage_binding_fallback_excl EXCLUDE USING gist (tenant_id WITH =, domain_id WITH =, scope_id WITH =, request_kind WITH =, tstzrange(valid_from, valid_to, '[)'::text) WITH &&) WHERE (((status = 'active'::text) AND (category_id IS NULL)));

--
-- Name: triage_policy_bindings triage_policy_bindings_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.triage_policy_bindings
    ADD CONSTRAINT triage_policy_bindings_pkey PRIMARY KEY (id);

--
-- Name: triage_policy_bindings triage_policy_bindings_tenant_key_uq; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.triage_policy_bindings
    ADD CONSTRAINT triage_policy_bindings_tenant_key_uq UNIQUE (tenant_id, id);

--
-- Name: triage_policy_versions triage_policy_versions_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.triage_policy_versions
    ADD CONSTRAINT triage_policy_versions_pkey PRIMARY KEY (id);

--
-- Name: triage_policy_versions triage_policy_versions_tenant_key_uq; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.triage_policy_versions
    ADD CONSTRAINT triage_policy_versions_tenant_key_uq UNIQUE (tenant_id, id);

--
-- Name: triage_policy_versions triage_policy_versions_unique_0; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.triage_policy_versions
    ADD CONSTRAINT triage_policy_versions_unique_0 UNIQUE (tenant_id, domain_id, policy_code, version_no);

--
-- Name: triage_rules triage_rules_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.triage_rules
    ADD CONSTRAINT triage_rules_pkey PRIMARY KEY (id);

--
-- Name: triage_rules triage_rules_tenant_key_uq; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.triage_rules
    ADD CONSTRAINT triage_rules_tenant_key_uq UNIQUE (tenant_id, id);

--
-- Name: triage_rules triage_rules_unique_0; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.triage_rules
    ADD CONSTRAINT triage_rules_unique_0 UNIQUE (policy_version_id, rule_code);

--
-- Name: triage_rules triage_rules_unique_1; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.triage_rules
    ADD CONSTRAINT triage_rules_unique_1 UNIQUE (policy_version_id, rule_kind, precedence);

--
-- Name: unit_residents unit_residents_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.unit_residents
    ADD CONSTRAINT unit_residents_pkey PRIMARY KEY (id);

--
-- Name: unit_residents unit_residents_tenant_key_uq; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.unit_residents
    ADD CONSTRAINT unit_residents_tenant_key_uq UNIQUE (tenant_id, id);

--
-- Name: units units_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.units
    ADD CONSTRAINT units_pkey PRIMARY KEY (id);

--
-- Name: units units_tenant_key_uq; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.units
    ADD CONSTRAINT units_tenant_key_uq UNIQUE (tenant_id, id);

--
-- Name: vh_command_receipt uq_vh_command_receipt_tenant_actor_command_key; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.vh_command_receipt
    ADD CONSTRAINT uq_vh_command_receipt_tenant_actor_command_key UNIQUE (tenant_id, actor_type, actor_id, command_type, idempotency_key);

--
-- Name: users users_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.users
    ADD CONSTRAINT users_pkey PRIMARY KEY (id);

--
-- Name: vh_assets vh_assets_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.vh_assets
    ADD CONSTRAINT vh_assets_pkey PRIMARY KEY (id);

--
-- Name: vh_assets vh_assets_tenant_id_building_id_code_key; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.vh_assets
    ADD CONSTRAINT vh_assets_tenant_id_building_id_code_key UNIQUE (tenant_id, building_id, code);

--
-- Name: vh_assets vh_assets_tenant_id_id_key; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.vh_assets
    ADD CONSTRAINT vh_assets_tenant_id_id_key UNIQUE (tenant_id, id);

--
-- Name: vh_budget_approvals vh_budget_approvals_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.vh_budget_approvals
    ADD CONSTRAINT vh_budget_approvals_pkey PRIMARY KEY (id);

--
-- Name: vh_budget_approvals vh_budget_approvals_tenant_id_id_key; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.vh_budget_approvals
    ADD CONSTRAINT vh_budget_approvals_tenant_id_id_key UNIQUE (tenant_id, id);

--
-- Name: vh_cleaning_plans vh_cleaning_plans_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.vh_cleaning_plans
    ADD CONSTRAINT vh_cleaning_plans_pkey PRIMARY KEY (id);

--
-- Name: vh_cleaning_plans vh_cleaning_plans_tenant_id_id_key; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.vh_cleaning_plans
    ADD CONSTRAINT vh_cleaning_plans_tenant_id_id_key UNIQUE (tenant_id, id);

--
-- Name: vh_cleaning_plans vh_cleaning_plans_tenant_id_work_order_id_key; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.vh_cleaning_plans
    ADD CONSTRAINT vh_cleaning_plans_tenant_id_work_order_id_key UNIQUE (tenant_id, work_order_id);

--
-- Name: vh_command_receipt vh_command_receipt_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.vh_command_receipt
    ADD CONSTRAINT vh_command_receipt_pkey PRIMARY KEY (id);

--
-- Name: vh_contractor_updates vh_contractor_updates_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.vh_contractor_updates
    ADD CONSTRAINT vh_contractor_updates_pkey PRIMARY KEY (id);

--
-- Name: vh_contractor_updates vh_contractor_updates_tenant_id_id_key; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.vh_contractor_updates
    ADD CONSTRAINT vh_contractor_updates_tenant_id_id_key UNIQUE (tenant_id, id);

--
-- Name: vh_contractor_updates vh_contractor_updates_tenant_id_work_order_id_key; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.vh_contractor_updates
    ADD CONSTRAINT vh_contractor_updates_tenant_id_work_order_id_key UNIQUE (tenant_id, work_order_id);

--
-- Name: vh_conversation_uploads vh_conversation_uploads_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.vh_conversation_uploads
    ADD CONSTRAINT vh_conversation_uploads_pkey PRIMARY KEY (id);

--
-- Name: vh_conversation_uploads vh_conversation_uploads_tenant_id_channel_id_requested_by_i_key; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.vh_conversation_uploads
    ADD CONSTRAINT vh_conversation_uploads_tenant_id_channel_id_requested_by_i_key UNIQUE (tenant_id, channel_id, requested_by, idempotency_key);

--
-- Name: vh_conversation_uploads vh_conversation_uploads_tenant_id_file_id_key; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.vh_conversation_uploads
    ADD CONSTRAINT vh_conversation_uploads_tenant_id_file_id_key UNIQUE (tenant_id, file_id);

--
-- Name: vh_conversation_uploads vh_conversation_uploads_tenant_id_id_key; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.vh_conversation_uploads
    ADD CONSTRAINT vh_conversation_uploads_tenant_id_id_key UNIQUE (tenant_id, id);

--
-- Name: vh_maintenance_records vh_maintenance_records_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.vh_maintenance_records
    ADD CONSTRAINT vh_maintenance_records_pkey PRIMARY KEY (id);

--
-- Name: vh_maintenance_records vh_maintenance_records_tenant_id_asset_id_work_order_id_key; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.vh_maintenance_records
    ADD CONSTRAINT vh_maintenance_records_tenant_id_asset_id_work_order_id_key UNIQUE (tenant_id, asset_id, work_order_id);

--
-- Name: vh_maintenance_records vh_maintenance_records_tenant_id_id_key; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.vh_maintenance_records
    ADD CONSTRAINT vh_maintenance_records_tenant_id_id_key UNIQUE (tenant_id, id);

--
-- Name: vh_operational_requests vh_operational_requests_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.vh_operational_requests
    ADD CONSTRAINT vh_operational_requests_pkey PRIMARY KEY (id);

--
-- Name: vh_operational_requests vh_operational_requests_tenant_id_id_key; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.vh_operational_requests
    ADD CONSTRAINT vh_operational_requests_tenant_id_id_key UNIQUE (tenant_id, id);

--
-- Name: vh_operational_requests vh_operational_requests_tenant_id_work_order_id_idempotency_key; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.vh_operational_requests
    ADD CONSTRAINT vh_operational_requests_tenant_id_work_order_id_idempotency_key UNIQUE (tenant_id, work_order_id, idempotency_key);

--
-- Name: vh_qc_redo_orders vh_qc_redo_orders_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.vh_qc_redo_orders
    ADD CONSTRAINT vh_qc_redo_orders_pkey PRIMARY KEY (id);

--
-- Name: vh_qc_redo_orders vh_qc_redo_orders_tenant_id_id_key; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.vh_qc_redo_orders
    ADD CONSTRAINT vh_qc_redo_orders_tenant_id_id_key UNIQUE (tenant_id, id);

--
-- Name: vh_qc_redo_orders vh_qc_redo_orders_tenant_id_qc_result_id_key; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.vh_qc_redo_orders
    ADD CONSTRAINT vh_qc_redo_orders_tenant_id_qc_result_id_key UNIQUE (tenant_id, qc_result_id);

--
-- Name: vh_qc_redo_orders vh_qc_redo_orders_tenant_id_redo_work_order_id_key; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.vh_qc_redo_orders
    ADD CONSTRAINT vh_qc_redo_orders_tenant_id_redo_work_order_id_key UNIQUE (tenant_id, redo_work_order_id);

--
-- Name: vh_qc_results vh_qc_results_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.vh_qc_results
    ADD CONSTRAINT vh_qc_results_pkey PRIMARY KEY (id);

--
-- Name: vh_qc_results vh_qc_results_tenant_id_id_key; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.vh_qc_results
    ADD CONSTRAINT vh_qc_results_tenant_id_id_key UNIQUE (tenant_id, id);

--
-- Name: vh_reception_supervisor_messages vh_reception_supervisor_messages_message_id_uq; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.vh_reception_supervisor_messages
    ADD CONSTRAINT vh_reception_supervisor_messages_message_id_uq UNIQUE (tenant_id, message_id);

--
-- Name: vh_reception_supervisor_messages vh_reception_supervisor_messages_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.vh_reception_supervisor_messages
    ADD CONSTRAINT vh_reception_supervisor_messages_pkey PRIMARY KEY (id);

--
-- Name: vh_reception_supervisor_messages vh_reception_supervisor_messages_tenant_key_uq; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.vh_reception_supervisor_messages
    ADD CONSTRAINT vh_reception_supervisor_messages_tenant_key_uq UNIQUE (tenant_id, id);

--
-- Name: vh_reception_supervisor_pending vh_reception_supervisor_pending_message_uq; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.vh_reception_supervisor_pending
    ADD CONSTRAINT vh_reception_supervisor_pending_message_uq UNIQUE (tenant_id, supervisor_message_id);

--
-- Name: vh_reception_supervisor_pending vh_reception_supervisor_pending_pk; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.vh_reception_supervisor_pending
    ADD CONSTRAINT vh_reception_supervisor_pending_pk PRIMARY KEY (tenant_id, ticket_id, ticket_generation);

--
-- Name: vh_report_exports vh_report_exports_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.vh_report_exports
    ADD CONSTRAINT vh_report_exports_pkey PRIMARY KEY (id);

--
-- Name: vh_report_exports vh_report_exports_tenant_id_created_by_idempotency_key_key; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.vh_report_exports
    ADD CONSTRAINT vh_report_exports_tenant_id_created_by_idempotency_key_key UNIQUE (tenant_id, created_by, idempotency_key);

--
-- Name: vh_report_exports vh_report_exports_tenant_id_id_key; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.vh_report_exports
    ADD CONSTRAINT vh_report_exports_tenant_id_id_key UNIQUE (tenant_id, id);

--
-- Name: vh_resident_case_tickets vh_resident_case_tickets_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.vh_resident_case_tickets
    ADD CONSTRAINT vh_resident_case_tickets_pkey PRIMARY KEY (tenant_id, case_id, ticket_id);

--
-- Name: vh_resident_cases vh_resident_cases_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.vh_resident_cases
    ADD CONSTRAINT vh_resident_cases_pkey PRIMARY KEY (id);

--
-- Name: vh_resident_cases vh_resident_cases_tenant_id_channel_id_key; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.vh_resident_cases
    ADD CONSTRAINT vh_resident_cases_tenant_id_channel_id_key UNIQUE (tenant_id, channel_id);

--
-- Name: vh_resident_cases vh_resident_cases_tenant_id_code_key; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.vh_resident_cases
    ADD CONSTRAINT vh_resident_cases_tenant_id_code_key UNIQUE (tenant_id, code);

--
-- Name: vh_resident_cases vh_resident_cases_tenant_id_id_key; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.vh_resident_cases
    ADD CONSTRAINT vh_resident_cases_tenant_id_id_key UNIQUE (tenant_id, id);

--
-- Name: vh_resident_command_receipts vh_resident_command_receipts_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.vh_resident_command_receipts
    ADD CONSTRAINT vh_resident_command_receipts_pkey PRIMARY KEY (tenant_id, actor_id, operation, resource, key);

--
-- Name: vh_resident_outbox vh_resident_outbox_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.vh_resident_outbox
    ADD CONSTRAINT vh_resident_outbox_pkey PRIMARY KEY (id);

--
-- Name: vh_resident_outbox vh_resident_outbox_tenant_id_event_id_key; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.vh_resident_outbox
    ADD CONSTRAINT vh_resident_outbox_tenant_id_event_id_key UNIQUE (tenant_id, event_id);

--
-- Name: vh_resident_outbox vh_resident_outbox_tenant_id_id_key; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.vh_resident_outbox
    ADD CONSTRAINT vh_resident_outbox_tenant_id_id_key UNIQUE (tenant_id, id);

--
-- Name: vh_resident_photos vh_resident_photos_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.vh_resident_photos
    ADD CONSTRAINT vh_resident_photos_pkey PRIMARY KEY (tenant_id, file_id);

--
-- Name: vh_resident_public_events vh_resident_public_events_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.vh_resident_public_events
    ADD CONSTRAINT vh_resident_public_events_pkey PRIMARY KEY (id);

--
-- Name: vh_resident_public_events vh_resident_public_events_tenant_id_id_key; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.vh_resident_public_events
    ADD CONSTRAINT vh_resident_public_events_tenant_id_id_key UNIQUE (tenant_id, id);

--
-- Name: vh_resident_resolution_photos vh_resident_resolution_photos_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.vh_resident_resolution_photos
    ADD CONSTRAINT vh_resident_resolution_photos_pkey PRIMARY KEY (tenant_id, resolution_id, file_id);

--
-- Name: vh_resident_resolution_responses vh_resident_resolution_responses_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.vh_resident_resolution_responses
    ADD CONSTRAINT vh_resident_resolution_responses_pkey PRIMARY KEY (id);

--
-- Name: vh_resident_resolution_responses vh_resident_resolution_responses_tenant_id_id_key; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.vh_resident_resolution_responses
    ADD CONSTRAINT vh_resident_resolution_responses_tenant_id_id_key UNIQUE (tenant_id, id);

--
-- Name: vh_resident_resolution_responses vh_resident_resolution_responses_tenant_id_resolution_id_key; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.vh_resident_resolution_responses
    ADD CONSTRAINT vh_resident_resolution_responses_tenant_id_resolution_id_key UNIQUE (tenant_id, resolution_id);

--
-- Name: vh_resident_resolutions vh_resident_resolutions_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.vh_resident_resolutions
    ADD CONSTRAINT vh_resident_resolutions_pkey PRIMARY KEY (id);

--
-- Name: vh_resident_resolutions vh_resident_resolutions_tenant_id_case_id_id_key; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.vh_resident_resolutions
    ADD CONSTRAINT vh_resident_resolutions_tenant_id_case_id_id_key UNIQUE (tenant_id, case_id, id);

--
-- Name: vh_resident_resolutions vh_resident_resolutions_tenant_id_id_key; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.vh_resident_resolutions
    ADD CONSTRAINT vh_resident_resolutions_tenant_id_id_key UNIQUE (tenant_id, id);

--
-- Name: vh_resident_submissions vh_resident_submissions_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.vh_resident_submissions
    ADD CONSTRAINT vh_resident_submissions_pkey PRIMARY KEY (id);

--
-- Name: vh_resident_submissions vh_resident_submissions_tenant_id_id_key; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.vh_resident_submissions
    ADD CONSTRAINT vh_resident_submissions_tenant_id_id_key UNIQUE (tenant_id, id);

--
-- Name: vh_security_checkpoints vh_security_checkpoints_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.vh_security_checkpoints
    ADD CONSTRAINT vh_security_checkpoints_pkey PRIMARY KEY (id);

--
-- Name: vh_security_checkpoints vh_security_checkpoints_tenant_id_id_key; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.vh_security_checkpoints
    ADD CONSTRAINT vh_security_checkpoints_tenant_id_id_key UNIQUE (tenant_id, id);

--
-- Name: vh_security_handovers vh_security_handovers_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.vh_security_handovers
    ADD CONSTRAINT vh_security_handovers_pkey PRIMARY KEY (id);

--
-- Name: vh_security_handovers vh_security_handovers_tenant_id_id_key; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.vh_security_handovers
    ADD CONSTRAINT vh_security_handovers_tenant_id_id_key UNIQUE (tenant_id, id);

--
-- Name: vh_security_incidents vh_security_incidents_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.vh_security_incidents
    ADD CONSTRAINT vh_security_incidents_pkey PRIMARY KEY (id);

--
-- Name: vh_security_incidents vh_security_incidents_tenant_id_id_key; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.vh_security_incidents
    ADD CONSTRAINT vh_security_incidents_tenant_id_id_key UNIQUE (tenant_id, id);

--
-- Name: vh_sensor_readings vh_sensor_readings_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.vh_sensor_readings
    ADD CONSTRAINT vh_sensor_readings_pkey PRIMARY KEY (id);

--
-- Name: vh_sensor_readings vh_sensor_readings_tenant_id_id_key; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.vh_sensor_readings
    ADD CONSTRAINT vh_sensor_readings_tenant_id_id_key UNIQUE (tenant_id, id);

--
-- Name: vh_technical_measurements vh_technical_measurements_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.vh_technical_measurements
    ADD CONSTRAINT vh_technical_measurements_pkey PRIMARY KEY (id);

--
-- Name: vh_technical_measurements vh_technical_measurements_tenant_id_id_key; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.vh_technical_measurements
    ADD CONSTRAINT vh_technical_measurements_tenant_id_id_key UNIQUE (tenant_id, id);

--
-- Name: vh_ticket_plans vh_ticket_plans_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.vh_ticket_plans
    ADD CONSTRAINT vh_ticket_plans_pkey PRIMARY KEY (id);

--
-- Name: vh_ticket_plans vh_ticket_plans_tenant_id_id_key; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.vh_ticket_plans
    ADD CONSTRAINT vh_ticket_plans_tenant_id_id_key UNIQUE (tenant_id, id);

--
-- Name: vh_ticket_plans vh_ticket_plans_tenant_id_ticket_id_idempotency_key_key; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.vh_ticket_plans
    ADD CONSTRAINT vh_ticket_plans_tenant_id_ticket_id_idempotency_key_key UNIQUE (tenant_id, ticket_id, idempotency_key);

--
-- Name: work_approvals work_approvals_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.work_approvals
    ADD CONSTRAINT work_approvals_pkey PRIMARY KEY (id);

--
-- Name: work_approvals work_approvals_tenant_key_uq; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.work_approvals
    ADD CONSTRAINT work_approvals_tenant_key_uq UNIQUE (tenant_id, id);

--
-- Name: work_assignments work_assignments_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.work_assignments
    ADD CONSTRAINT work_assignments_pkey PRIMARY KEY (id);

--
-- Name: work_assignments work_assignments_tenant_key_uq; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.work_assignments
    ADD CONSTRAINT work_assignments_tenant_key_uq UNIQUE (tenant_id, id);

--
-- Name: work_orders work_orders_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.work_orders
    ADD CONSTRAINT work_orders_pkey PRIMARY KEY (id);

--
-- Name: work_orders work_orders_tenant_key_uq; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.work_orders
    ADD CONSTRAINT work_orders_tenant_key_uq UNIQUE (tenant_id, id);

--
-- Name: workspace_members workspace_members_tenant_id_workspace_id_user_id_pk; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.workspace_members
    ADD CONSTRAINT workspace_members_tenant_id_workspace_id_user_id_pk PRIMARY KEY (tenant_id, workspace_id, user_id);

--
-- Name: workspaces workspaces_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.workspaces
    ADD CONSTRAINT workspaces_pkey PRIMARY KEY (id);

--
-- Name: workspaces workspaces_tenant_key_uq; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.workspaces
    ADD CONSTRAINT workspaces_tenant_key_uq UNIQUE (tenant_id, id);

--
-- Name: workspaces workspaces_unique_0; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.workspaces
    ADD CONSTRAINT workspaces_unique_0 UNIQUE (tenant_id, management_unit_id);

--
-- Name: zones zones_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.zones
    ADD CONSTRAINT zones_pkey PRIMARY KEY (id);

--
-- Name: zones zones_tenant_key_uq; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.zones
    ADD CONSTRAINT zones_tenant_key_uq UNIQUE (tenant_id, id);

--
-- Name: zones zones_unique_0; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.zones
    ADD CONSTRAINT zones_unique_0 UNIQUE (site_id, code);

--
-- Name: access_scopes_partial_0; Type: INDEX; Schema: public; Owner: -
--

CREATE UNIQUE INDEX access_scopes_partial_0 ON public.access_scopes USING btree (tenant_id) WHERE (kind = 'tenant'::text);

--
-- Name: access_scopes_partial_1; Type: INDEX; Schema: public; Owner: -
--

CREATE UNIQUE INDEX access_scopes_partial_1 ON public.access_scopes USING btree (tenant_id, management_unit_id) WHERE (kind = 'management'::text);

--
-- Name: access_scopes_partial_2; Type: INDEX; Schema: public; Owner: -
--

CREATE UNIQUE INDEX access_scopes_partial_2 ON public.access_scopes USING btree (tenant_id, site_id) WHERE (kind = 'site'::text);

--
-- Name: access_scopes_partial_3; Type: INDEX; Schema: public; Owner: -
--

CREATE UNIQUE INDEX access_scopes_partial_3 ON public.access_scopes USING btree (tenant_id, zone_id) WHERE (kind = 'zone'::text);

--
-- Name: access_scopes_partial_4; Type: INDEX; Schema: public; Owner: -
--

CREATE UNIQUE INDEX access_scopes_partial_4 ON public.access_scopes USING btree (tenant_id, building_id) WHERE (kind = 'building'::text);

--
-- Name: account_reviews_user_id_idx; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX account_reviews_user_id_idx ON public.account_reviews USING btree (tenant_id, user_id);

--
-- Name: accounts_user_id_idx; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX accounts_user_id_idx ON public.accounts USING btree (user_id);

--
-- Name: agent_releases_partial_0; Type: INDEX; Schema: public; Owner: -
--

CREATE UNIQUE INDEX agent_releases_partial_0 ON public.agent_releases USING btree (version_id) WHERE ((status = 'published'::text) AND (revoked_at IS NULL));

--
-- Name: agent_teams_ticket_id_idx; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX agent_teams_ticket_id_idx ON public.agent_teams USING btree (tenant_id, ticket_id);

--
-- Name: agent_teams_workspace_id_idx; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX agent_teams_workspace_id_idx ON public.agent_teams USING btree (tenant_id, workspace_id);

--
-- Name: agents_partial_0; Type: INDEX; Schema: public; Owner: -
--

CREATE UNIQUE INDEX agents_partial_0 ON public.agents USING btree (tenant_id) WHERE ((purpose = 'reception'::text) AND (status = 'active'::text));

--
-- Name: agents_workspace_id_idx; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX agents_workspace_id_idx ON public.agents USING btree (tenant_id, workspace_id);

--
-- Name: audit_events_workspace_id_idx; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX audit_events_workspace_id_idx ON public.audit_events USING btree (tenant_id, workspace_id);

--
-- Name: channels_partial_0; Type: INDEX; Schema: public; Owner: -
--

CREATE UNIQUE INDEX channels_partial_0 ON public.channels USING btree (workspace_id) WHERE (is_dispatch_default AND (deleted_at IS NULL));

--
-- Name: channels_workspace_id_idx; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX channels_workspace_id_idx ON public.channels USING btree (tenant_id, workspace_id);

--
-- Name: dispatch_queue_priority_idx; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX dispatch_queue_priority_idx ON public.dispatch_queue USING btree (tenant_id, management_unit_id, is_emergency DESC, priority_rank DESC, dispatch_due_at, eligible_since, id) WHERE (state = 'waiting'::text);

--
-- Name: escalation_notify_idx; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX escalation_notify_idx ON public.ticket_escalations USING btree (tenant_id, next_notify_at) WHERE (status = ANY (ARRAY['open'::text, 'acknowledged'::text]));

--
-- Name: evidence_items_ticket_id_idx; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX evidence_items_ticket_id_idx ON public.evidence_items USING btree (tenant_id, ticket_id);

--
-- Name: execution_principals_partial_0; Type: INDEX; Schema: public; Owner: -
--

CREATE UNIQUE INDEX execution_principals_partial_0 ON public.execution_principals USING btree (tenant_id, user_id) WHERE (kind = 'user'::text);

--
-- Name: execution_principals_partial_1; Type: INDEX; Schema: public; Owner: -
--

CREATE UNIQUE INDEX execution_principals_partial_1 ON public.execution_principals USING btree (tenant_id, workspace_id) WHERE (kind = 'workspace_service'::text);

--
-- Name: execution_principals_user_id_idx; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX execution_principals_user_id_idx ON public.execution_principals USING btree (tenant_id, user_id);

--
-- Name: execution_principals_workspace_id_idx; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX execution_principals_workspace_id_idx ON public.execution_principals USING btree (tenant_id, workspace_id);

--
-- Name: file_uploads_partial_0; Type: INDEX; Schema: public; Owner: -
--

CREATE UNIQUE INDEX file_uploads_partial_0 ON public.file_uploads USING btree (file_id) WHERE (status = ANY (ARRAY['issued'::text, 'uploading'::text, 'uploaded'::text, 'verifying'::text]));

--
-- Name: files_ticket_id_idx; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX files_ticket_id_idx ON public.files USING btree (tenant_id, ticket_id);

--
-- Name: invoices_ticket_id_idx; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX invoices_ticket_id_idx ON public.invoices USING btree (tenant_id, ticket_id);

--
-- Name: ix_vh_command_receipt_tenant_created; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_vh_command_receipt_tenant_created ON public.vh_command_receipt USING btree (tenant_id, created_at);

--
-- Name: messages_run_id_idx; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX messages_run_id_idx ON public.messages USING btree (tenant_id, run_id);

--
-- Name: notification_deliveries_user_id_idx; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX notification_deliveries_user_id_idx ON public.notification_deliveries USING btree (tenant_id, user_id);

--
-- Name: runtime_session_bindings_partial_0; Type: INDEX; Schema: public; Owner: -
--

CREATE UNIQUE INDEX runtime_session_bindings_partial_0 ON public.runtime_session_bindings USING btree (tenant_id, channel_id, agent_id) WHERE ((audience_kind = 'personal'::text) AND (status = ANY (ARRAY['active'::text, 'provisioning'::text, 'interrupted'::text])));

--
-- Name: runtime_session_bindings_partial_1; Type: INDEX; Schema: public; Owner: -
--

CREATE UNIQUE INDEX runtime_session_bindings_partial_1 ON public.runtime_session_bindings USING btree (team_member_id) WHERE ((audience_kind = 'team'::text) AND (status = ANY (ARRAY['active'::text, 'provisioning'::text, 'interrupted'::text])));

--
-- Name: sessions_user_id_idx; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX sessions_user_id_idx ON public.sessions USING btree (user_id);

--
-- Name: staff_profiles_user_id_idx; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX staff_profiles_user_id_idx ON public.staff_profiles USING btree (tenant_id, user_id);

--
-- Name: tenant_memberships_user_id_idx; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX tenant_memberships_user_id_idx ON public.tenant_memberships USING btree (tenant_id, user_id);

--
-- Name: ticket_assessments_ticket_id_idx; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ticket_assessments_ticket_id_idx ON public.ticket_assessments USING btree (tenant_id, ticket_id);

--
-- Name: ticket_escalations_ticket_id_idx; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ticket_escalations_ticket_id_idx ON public.ticket_escalations USING btree (tenant_id, ticket_id);

--
-- Name: ticket_events_ticket_id_idx; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ticket_events_ticket_id_idx ON public.ticket_events USING btree (tenant_id, ticket_id);

--
-- Name: ticket_reviews_ticket_id_idx; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ticket_reviews_ticket_id_idx ON public.ticket_reviews USING btree (tenant_id, ticket_id);

--
-- Name: ticket_routing_history_ticket_id_idx; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ticket_routing_history_ticket_id_idx ON public.ticket_routing_history USING btree (tenant_id, ticket_id);

--
-- Name: ticket_sla_cycles_ticket_id_idx; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ticket_sla_cycles_ticket_id_idx ON public.ticket_sla_cycles USING btree (tenant_id, ticket_id);

--
-- Name: ticket_triage_decisions_partial_0; Type: INDEX; Schema: public; Owner: -
--

CREATE UNIQUE INDEX ticket_triage_decisions_partial_0 ON public.ticket_triage_decisions USING btree (review_id) WHERE ((review_id IS NOT NULL) AND (outcome = 'applied'::text));

--
-- Name: ticket_triage_decisions_ticket_id_idx; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ticket_triage_decisions_ticket_id_idx ON public.ticket_triage_decisions USING btree (tenant_id, ticket_id);

--
-- Name: ticket_triage_reviews_ticket_id_idx; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ticket_triage_reviews_ticket_id_idx ON public.ticket_triage_reviews USING btree (tenant_id, ticket_id);

--
-- Name: triage_reviews_due_idx; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX triage_reviews_due_idx ON public.ticket_triage_reviews USING btree (tenant_id, due_at) WHERE (status = ANY (ARRAY['pending'::text, 'claimed'::text]));

--
-- Name: unit_residents_user_id_idx; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX unit_residents_user_id_idx ON public.unit_residents USING btree (tenant_id, user_id);

--
-- Name: units_partial_0; Type: INDEX; Schema: public; Owner: -
--

CREATE UNIQUE INDEX units_partial_0 ON public.units USING btree (building_id, code) WHERE (building_id IS NOT NULL);

--
-- Name: units_partial_1; Type: INDEX; Schema: public; Owner: -
--

CREATE UNIQUE INDEX units_partial_1 ON public.units USING btree (zone_id, code) WHERE (building_id IS NULL);

--
-- Name: users_partial_0; Type: INDEX; Schema: public; Owner: -
--

CREATE UNIQUE INDEX users_partial_0 ON public.users USING btree (lower(email)) WHERE (email IS NOT NULL);

--
-- Name: users_partial_1; Type: INDEX; Schema: public; Owner: -
--

CREATE UNIQUE INDEX users_partial_1 ON public.users USING btree (phone_e164) WHERE (phone_e164 IS NOT NULL);

--
-- Name: vh_one_pending_plan; Type: INDEX; Schema: public; Owner: -
--

CREATE UNIQUE INDEX vh_one_pending_plan ON public.vh_ticket_plans USING btree (tenant_id, ticket_id) WHERE (status = ANY (ARRAY['management_pending'::text, 'resident_pending'::text]));

--
-- Name: vh_reception_supervisor_messages_team_page_idx; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX vh_reception_supervisor_messages_team_page_idx ON public.vh_reception_supervisor_messages USING btree (tenant_id, team_id, created_at DESC, id DESC);

--
-- Name: vh_reception_supervisor_messages_ticket_page_idx; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX vh_reception_supervisor_messages_ticket_page_idx ON public.vh_reception_supervisor_messages USING btree (tenant_id, ticket_id, ticket_generation, created_at DESC, id DESC);

--
-- Name: vh_reception_supervisor_pending_team_idx; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX vh_reception_supervisor_pending_team_idx ON public.vh_reception_supervisor_pending USING btree (tenant_id, team_id, created_at DESC);

--
-- Name: vh_resident_case_tickets_source; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX vh_resident_case_tickets_source ON public.vh_resident_case_tickets USING btree (tenant_id, ticket_id);

--
-- Name: vh_resident_cases_owner_page; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX vh_resident_cases_owner_page ON public.vh_resident_cases USING btree (tenant_id, requester_user_id, created_at DESC, id DESC);

--
-- Name: vh_resident_events_page; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX vh_resident_events_page ON public.vh_resident_public_events USING btree (tenant_id, case_id, occurred_at, id);

--
-- Name: work_assignments_partial_0; Type: INDEX; Schema: public; Owner: -
--

CREATE UNIQUE INDEX work_assignments_partial_0 ON public.work_assignments USING btree (work_order_id) WHERE (status = ANY (ARRAY['offered'::text, 'accepted'::text]));

--
-- Name: work_orders_ticket_id_idx; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX work_orders_ticket_id_idx ON public.work_orders USING btree (tenant_id, ticket_id);

--
-- Name: access_scopes access_scopes_touch; Type: TRIGGER; Schema: public; Owner: -
--

CREATE TRIGGER access_scopes_touch BEFORE UPDATE ON public.access_scopes FOR EACH ROW EXECUTE FUNCTION public.app_touch_updated_at();

--
-- Name: accounts accounts_touch; Type: TRIGGER; Schema: public; Owner: -
--

CREATE TRIGGER accounts_touch BEFORE UPDATE ON public.accounts FOR EACH ROW EXECUTE FUNCTION public.app_touch_updated_at();

--
-- Name: agent_releases agent_release_version; Type: TRIGGER; Schema: public; Owner: -
--

CREATE TRIGGER agent_release_version BEFORE INSERT OR UPDATE ON public.agent_releases FOR EACH ROW EXECUTE FUNCTION public.app_agent_version_scope();

--
-- Name: agent_releases agent_releases_touch; Type: TRIGGER; Schema: public; Owner: -
--

CREATE TRIGGER agent_releases_touch BEFORE UPDATE ON public.agent_releases FOR EACH ROW EXECUTE FUNCTION public.app_touch_updated_at();

--
-- Name: agent_runs agent_runs_touch; Type: TRIGGER; Schema: public; Owner: -
--

CREATE TRIGGER agent_runs_touch BEFORE UPDATE ON public.agent_runs FOR EACH ROW EXECUTE FUNCTION public.app_touch_updated_at();

--
-- Name: agent_teams agent_teams_touch; Type: TRIGGER; Schema: public; Owner: -
--

CREATE TRIGGER agent_teams_touch BEFORE UPDATE ON public.agent_teams FOR EACH ROW EXECUTE FUNCTION public.app_touch_updated_at();

--
-- Name: agent_versions agent_versions_immutable; Type: TRIGGER; Schema: public; Owner: -
--

CREATE TRIGGER agent_versions_immutable BEFORE DELETE OR UPDATE ON public.agent_versions FOR EACH ROW EXECUTE FUNCTION public.app_append_only();

--
-- Name: agent_versions agent_versions_no_truncate; Type: TRIGGER; Schema: public; Owner: -
--

CREATE TRIGGER agent_versions_no_truncate BEFORE TRUNCATE ON public.agent_versions FOR EACH STATEMENT EXECUTE FUNCTION public.app_append_only();

--
-- Name: agents agents_touch; Type: TRIGGER; Schema: public; Owner: -
--

CREATE TRIGGER agents_touch BEFORE UPDATE ON public.agents FOR EACH ROW EXECUTE FUNCTION public.app_touch_updated_at();

--
-- Name: ticket_triage_decisions applied_decision_projection; Type: TRIGGER; Schema: public; Owner: -
--

CREATE CONSTRAINT TRIGGER applied_decision_projection AFTER INSERT ON public.ticket_triage_decisions DEFERRABLE INITIALLY DEFERRED FOR EACH ROW EXECUTE FUNCTION public.app_check_applied_decision();

--
-- Name: work_assignments assignment_capacity; Type: TRIGGER; Schema: public; Owner: -
--

CREATE TRIGGER assignment_capacity BEFORE INSERT OR UPDATE ON public.work_assignments FOR EACH ROW EXECUTE FUNCTION public.app_assignment_capacity();

--
-- Name: audit_events audit_events_append_only; Type: TRIGGER; Schema: public; Owner: -
--

CREATE TRIGGER audit_events_append_only BEFORE DELETE OR UPDATE ON public.audit_events FOR EACH ROW EXECUTE FUNCTION public.prevent_audit_event_mutation();

--
-- Name: audit_events audit_events_no_truncate; Type: TRIGGER; Schema: public; Owner: -
--

CREATE TRIGGER audit_events_no_truncate BEFORE TRUNCATE ON public.audit_events FOR EACH STATEMENT EXECUTE FUNCTION public.prevent_audit_event_mutation();

--
-- Name: buildings buildings_touch; Type: TRIGGER; Schema: public; Owner: -
--

CREATE TRIGGER buildings_touch BEFORE UPDATE ON public.buildings FOR EACH ROW EXECUTE FUNCTION public.app_touch_updated_at();

--
-- Name: channels channels_touch; Type: TRIGGER; Schema: public; Owner: -
--

CREATE TRIGGER channels_touch BEFORE UPDATE ON public.channels FOR EACH ROW EXECUTE FUNCTION public.app_touch_updated_at();

--
-- Name: dispatch_attempts dispatch_attempts_touch; Type: TRIGGER; Schema: public; Owner: -
--

CREATE TRIGGER dispatch_attempts_touch BEFORE UPDATE ON public.dispatch_attempts FOR EACH ROW EXECUTE FUNCTION public.app_touch_updated_at();

--
-- Name: dispatch_queue dispatch_queue_touch; Type: TRIGGER; Schema: public; Owner: -
--

CREATE TRIGGER dispatch_queue_touch BEFORE UPDATE ON public.dispatch_queue FOR EACH ROW EXECUTE FUNCTION public.app_touch_updated_at();

--
-- Name: domains domains_touch; Type: TRIGGER; Schema: public; Owner: -
--

CREATE TRIGGER domains_touch BEFORE UPDATE ON public.domains FOR EACH ROW EXECUTE FUNCTION public.app_touch_updated_at();

--
-- Name: event_inbox event_inbox_touch; Type: TRIGGER; Schema: public; Owner: -
--

CREATE TRIGGER event_inbox_touch BEFORE UPDATE ON public.event_inbox FOR EACH ROW EXECUTE FUNCTION public.app_touch_updated_at();

--
-- Name: evidence_items evidence_items_touch; Type: TRIGGER; Schema: public; Owner: -
--

CREATE TRIGGER evidence_items_touch BEFORE UPDATE ON public.evidence_items FOR EACH ROW EXECUTE FUNCTION public.app_touch_updated_at();

--
-- Name: evidence_items evidence_scope; Type: TRIGGER; Schema: public; Owner: -
--

CREATE TRIGGER evidence_scope BEFORE INSERT OR UPDATE ON public.evidence_items FOR EACH ROW EXECUTE FUNCTION public.app_validate_evidence();

--
-- Name: execution_principals execution_principals_touch; Type: TRIGGER; Schema: public; Owner: -
--

CREATE TRIGGER execution_principals_touch BEFORE UPDATE ON public.execution_principals FOR EACH ROW EXECUTE FUNCTION public.app_touch_updated_at();

--
-- Name: file_objects file_objects_touch; Type: TRIGGER; Schema: public; Owner: -
--

CREATE TRIGGER file_objects_touch BEFORE UPDATE ON public.file_objects FOR EACH ROW EXECUTE FUNCTION public.app_touch_updated_at();

--
-- Name: files file_original_scope; Type: TRIGGER; Schema: public; Owner: -
--

CREATE CONSTRAINT TRIGGER file_original_scope AFTER INSERT OR UPDATE ON public.files DEFERRABLE INITIALLY DEFERRED FOR EACH ROW EXECUTE FUNCTION public.app_validate_file();

--
-- Name: file_uploads file_uploads_touch; Type: TRIGGER; Schema: public; Owner: -
--

CREATE TRIGGER file_uploads_touch BEFORE UPDATE ON public.file_uploads FOR EACH ROW EXECUTE FUNCTION public.app_touch_updated_at();

--
-- Name: files files_touch; Type: TRIGGER; Schema: public; Owner: -
--

CREATE TRIGGER files_touch BEFORE UPDATE ON public.files FOR EACH ROW EXECUTE FUNCTION public.app_touch_updated_at();

--
-- Name: incident_types incident_types_touch; Type: TRIGGER; Schema: public; Owner: -
--

CREATE TRIGGER incident_types_touch BEFORE UPDATE ON public.incident_types FOR EACH ROW EXECUTE FUNCTION public.app_touch_updated_at();

--
-- Name: invoice_lines invoice_lines_touch; Type: TRIGGER; Schema: public; Owner: -
--

CREATE TRIGGER invoice_lines_touch BEFORE UPDATE ON public.invoice_lines FOR EACH ROW EXECUTE FUNCTION public.app_touch_updated_at();

--
-- Name: invoices invoices_touch; Type: TRIGGER; Schema: public; Owner: -
--

CREATE TRIGGER invoices_touch BEFORE UPDATE ON public.invoices FOR EACH ROW EXECUTE FUNCTION public.app_touch_updated_at();

--
-- Name: management_coverage management_coverage_touch; Type: TRIGGER; Schema: public; Owner: -
--

CREATE TRIGGER management_coverage_touch BEFORE UPDATE ON public.management_coverage FOR EACH ROW EXECUTE FUNCTION public.app_touch_updated_at();

--
-- Name: management_units management_units_touch; Type: TRIGGER; Schema: public; Owner: -
--

CREATE TRIGGER management_units_touch BEFORE UPDATE ON public.management_units FOR EACH ROW EXECUTE FUNCTION public.app_touch_updated_at();

--
-- Name: notification_deliveries notification_deliveries_touch; Type: TRIGGER; Schema: public; Owner: -
--

CREATE TRIGGER notification_deliveries_touch BEFORE UPDATE ON public.notification_deliveries FOR EACH ROW EXECUTE FUNCTION public.app_touch_updated_at();

--
-- Name: file_objects object_version_scope; Type: TRIGGER; Schema: public; Owner: -
--

CREATE TRIGGER object_version_scope BEFORE INSERT OR UPDATE ON public.file_objects FOR EACH ROW EXECUTE FUNCTION public.app_validate_object();

--
-- Name: payment_allocations payment_allocations_immutable; Type: TRIGGER; Schema: public; Owner: -
--

CREATE TRIGGER payment_allocations_immutable BEFORE DELETE OR UPDATE ON public.payment_allocations FOR EACH ROW EXECUTE FUNCTION public.app_append_only();

--
-- Name: payment_allocations payment_allocations_no_truncate; Type: TRIGGER; Schema: public; Owner: -
--

CREATE TRIGGER payment_allocations_no_truncate BEFORE TRUNCATE ON public.payment_allocations FOR EACH STATEMENT EXECUTE FUNCTION public.app_append_only();

--
-- Name: payment_intents payment_intents_touch; Type: TRIGGER; Schema: public; Owner: -
--

CREATE TRIGGER payment_intents_touch BEFORE UPDATE ON public.payment_intents FOR EACH ROW EXECUTE FUNCTION public.app_touch_updated_at();

--
-- Name: triage_rules policy_rule_immutable; Type: TRIGGER; Schema: public; Owner: -
--

CREATE TRIGGER policy_rule_immutable BEFORE INSERT OR DELETE OR UPDATE ON public.triage_rules FOR EACH ROW EXECUTE FUNCTION public.app_policy_immutable();

--
-- Name: triage_policy_versions policy_version_immutable; Type: TRIGGER; Schema: public; Owner: -
--

CREATE TRIGGER policy_version_immutable BEFORE UPDATE ON public.triage_policy_versions FOR EACH ROW EXECUTE FUNCTION public.app_policy_immutable();

--
-- Name: runtime_backends runtime_backends_touch; Type: TRIGGER; Schema: public; Owner: -
--

CREATE TRIGGER runtime_backends_touch BEFORE UPDATE ON public.runtime_backends FOR EACH ROW EXECUTE FUNCTION public.app_touch_updated_at();

--
-- Name: runtime_session_bindings runtime_binding_scope; Type: TRIGGER; Schema: public; Owner: -
--

CREATE TRIGGER runtime_binding_scope BEFORE INSERT OR UPDATE ON public.runtime_session_bindings FOR EACH ROW EXECUTE FUNCTION public.app_validate_runtime_binding();

--
-- Name: runtime_session_bindings runtime_session_bindings_touch; Type: TRIGGER; Schema: public; Owner: -
--

CREATE TRIGGER runtime_session_bindings_touch BEFORE UPDATE ON public.runtime_session_bindings FOR EACH ROW EXECUTE FUNCTION public.app_touch_updated_at();

--
-- Name: scoped_user_roles scoped_user_roles_touch; Type: TRIGGER; Schema: public; Owner: -
--

CREATE TRIGGER scoped_user_roles_touch BEFORE UPDATE ON public.scoped_user_roles FOR EACH ROW EXECUTE FUNCTION public.app_touch_updated_at();

--
-- Name: service_categories service_categories_touch; Type: TRIGGER; Schema: public; Owner: -
--

CREATE TRIGGER service_categories_touch BEFORE UPDATE ON public.service_categories FOR EACH ROW EXECUTE FUNCTION public.app_touch_updated_at();

--
-- Name: service_interruptions service_interruptions_touch; Type: TRIGGER; Schema: public; Owner: -
--

CREATE TRIGGER service_interruptions_touch BEFORE UPDATE ON public.service_interruptions FOR EACH ROW EXECUTE FUNCTION public.app_touch_updated_at();

--
-- Name: sessions sessions_touch; Type: TRIGGER; Schema: public; Owner: -
--

CREATE TRIGGER sessions_touch BEFORE UPDATE ON public.sessions FOR EACH ROW EXECUTE FUNCTION public.app_touch_updated_at();

--
-- Name: sites sites_touch; Type: TRIGGER; Schema: public; Owner: -
--

CREATE TRIGGER sites_touch BEFORE UPDATE ON public.sites FOR EACH ROW EXECUTE FUNCTION public.app_touch_updated_at();

--
-- Name: sla_policies sla_policies_touch; Type: TRIGGER; Schema: public; Owner: -
--

CREATE TRIGGER sla_policies_touch BEFORE UPDATE ON public.sla_policies FOR EACH ROW EXECUTE FUNCTION public.app_touch_updated_at();

--
-- Name: staff_profiles staff_profiles_touch; Type: TRIGGER; Schema: public; Owner: -
--

CREATE TRIGGER staff_profiles_touch BEFORE UPDATE ON public.staff_profiles FOR EACH ROW EXECUTE FUNCTION public.app_touch_updated_at();

--
-- Name: staff_shifts staff_shifts_touch; Type: TRIGGER; Schema: public; Owner: -
--

CREATE TRIGGER staff_shifts_touch BEFORE UPDATE ON public.staff_shifts FOR EACH ROW EXECUTE FUNCTION public.app_touch_updated_at();

--
-- Name: storage_locations storage_locations_touch; Type: TRIGGER; Schema: public; Owner: -
--

CREATE TRIGGER storage_locations_touch BEFORE UPDATE ON public.storage_locations FOR EACH ROW EXECUTE FUNCTION public.app_touch_updated_at();

--
-- Name: team_members team_member_version; Type: TRIGGER; Schema: public; Owner: -
--

CREATE TRIGGER team_member_version BEFORE INSERT OR UPDATE ON public.team_members FOR EACH ROW EXECUTE FUNCTION public.app_agent_version_scope();

--
-- Name: team_members team_members_touch; Type: TRIGGER; Schema: public; Owner: -
--

CREATE TRIGGER team_members_touch BEFORE UPDATE ON public.team_members FOR EACH ROW EXECUTE FUNCTION public.app_touch_updated_at();

--
-- Name: tenant_memberships tenant_memberships_touch; Type: TRIGGER; Schema: public; Owner: -
--

CREATE TRIGGER tenant_memberships_touch BEFORE UPDATE ON public.tenant_memberships FOR EACH ROW EXECUTE FUNCTION public.app_touch_updated_at();

--
-- Name: tenants tenants_touch; Type: TRIGGER; Schema: public; Owner: -
--

CREATE TRIGGER tenants_touch BEFORE UPDATE ON public.tenants FOR EACH ROW EXECUTE FUNCTION public.app_touch_updated_at();

--
-- Name: ticket_assessments ticket_assessments_immutable; Type: TRIGGER; Schema: public; Owner: -
--

CREATE TRIGGER ticket_assessments_immutable BEFORE DELETE OR UPDATE ON public.ticket_assessments FOR EACH ROW EXECUTE FUNCTION public.app_append_only();

--
-- Name: ticket_assessments ticket_assessments_no_truncate; Type: TRIGGER; Schema: public; Owner: -
--

CREATE TRIGGER ticket_assessments_no_truncate BEFORE TRUNCATE ON public.ticket_assessments FOR EACH STATEMENT EXECUTE FUNCTION public.app_append_only();

--
-- Name: ticket_escalations ticket_escalations_touch; Type: TRIGGER; Schema: public; Owner: -
--

CREATE TRIGGER ticket_escalations_touch BEFORE UPDATE ON public.ticket_escalations FOR EACH ROW EXECUTE FUNCTION public.app_touch_updated_at();

--
-- Name: ticket_events ticket_events_immutable; Type: TRIGGER; Schema: public; Owner: -
--

CREATE TRIGGER ticket_events_immutable BEFORE DELETE OR UPDATE ON public.ticket_events FOR EACH ROW EXECUTE FUNCTION public.app_append_only();

--
-- Name: ticket_events ticket_events_no_truncate; Type: TRIGGER; Schema: public; Owner: -
--

CREATE TRIGGER ticket_events_no_truncate BEFORE TRUNCATE ON public.ticket_events FOR EACH STATEMENT EXECUTE FUNCTION public.app_append_only();

--
-- Name: ticket_reviews ticket_reviews_touch; Type: TRIGGER; Schema: public; Owner: -
--

CREATE TRIGGER ticket_reviews_touch BEFORE UPDATE ON public.ticket_reviews FOR EACH ROW EXECUTE FUNCTION public.app_touch_updated_at();

--
-- Name: ticket_sla_adjustments ticket_sla_adjustments_immutable; Type: TRIGGER; Schema: public; Owner: -
--

CREATE TRIGGER ticket_sla_adjustments_immutable BEFORE DELETE OR UPDATE ON public.ticket_sla_adjustments FOR EACH ROW EXECUTE FUNCTION public.app_append_only();

--
-- Name: ticket_sla_adjustments ticket_sla_adjustments_no_truncate; Type: TRIGGER; Schema: public; Owner: -
--

CREATE TRIGGER ticket_sla_adjustments_no_truncate BEFORE TRUNCATE ON public.ticket_sla_adjustments FOR EACH STATEMENT EXECUTE FUNCTION public.app_append_only();

--
-- Name: ticket_sla_cycles ticket_sla_cycles_touch; Type: TRIGGER; Schema: public; Owner: -
--

CREATE TRIGGER ticket_sla_cycles_touch BEFORE UPDATE ON public.ticket_sla_cycles FOR EACH ROW EXECUTE FUNCTION public.app_touch_updated_at();

--
-- Name: ticket_triage_decisions ticket_triage_decisions_immutable; Type: TRIGGER; Schema: public; Owner: -
--

CREATE TRIGGER ticket_triage_decisions_immutable BEFORE DELETE OR UPDATE ON public.ticket_triage_decisions FOR EACH ROW EXECUTE FUNCTION public.app_append_only();

--
-- Name: ticket_triage_decisions ticket_triage_decisions_no_truncate; Type: TRIGGER; Schema: public; Owner: -
--

CREATE TRIGGER ticket_triage_decisions_no_truncate BEFORE TRUNCATE ON public.ticket_triage_decisions FOR EACH STATEMENT EXECUTE FUNCTION public.app_append_only();

--
-- Name: tickets ticket_triage_projection; Type: TRIGGER; Schema: public; Owner: -
--

CREATE CONSTRAINT TRIGGER ticket_triage_projection AFTER INSERT OR UPDATE ON public.tickets DEFERRABLE INITIALLY DEFERRED FOR EACH ROW EXECUTE FUNCTION public.app_check_ticket_projection();

--
-- Name: ticket_triage_reviews ticket_triage_reviews_touch; Type: TRIGGER; Schema: public; Owner: -
--

CREATE TRIGGER ticket_triage_reviews_touch BEFORE UPDATE ON public.ticket_triage_reviews FOR EACH ROW EXECUTE FUNCTION public.app_touch_updated_at();

--
-- Name: tickets tickets_touch; Type: TRIGGER; Schema: public; Owner: -
--

CREATE TRIGGER tickets_touch BEFORE UPDATE ON public.tickets FOR EACH ROW EXECUTE FUNCTION public.app_touch_updated_at();

--
-- Name: ticket_triage_decisions triage_decision_source; Type: TRIGGER; Schema: public; Owner: -
--

CREATE TRIGGER triage_decision_source BEFORE INSERT ON public.ticket_triage_decisions FOR EACH ROW EXECUTE FUNCTION public.app_validate_triage_decision();

--
-- Name: triage_policy_bindings triage_policy_bindings_touch; Type: TRIGGER; Schema: public; Owner: -
--

CREATE TRIGGER triage_policy_bindings_touch BEFORE UPDATE ON public.triage_policy_bindings FOR EACH ROW EXECUTE FUNCTION public.app_touch_updated_at();

--
-- Name: triage_policy_versions triage_policy_versions_touch; Type: TRIGGER; Schema: public; Owner: -
--

CREATE TRIGGER triage_policy_versions_touch BEFORE UPDATE ON public.triage_policy_versions FOR EACH ROW EXECUTE FUNCTION public.app_touch_updated_at();

--
-- Name: unit_residents unit_residents_touch; Type: TRIGGER; Schema: public; Owner: -
--

CREATE TRIGGER unit_residents_touch BEFORE UPDATE ON public.unit_residents FOR EACH ROW EXECUTE FUNCTION public.app_touch_updated_at();

--
-- Name: units units_touch; Type: TRIGGER; Schema: public; Owner: -
--

CREATE TRIGGER units_touch BEFORE UPDATE ON public.units FOR EACH ROW EXECUTE FUNCTION public.app_touch_updated_at();

--
-- Name: users users_touch; Type: TRIGGER; Schema: public; Owner: -
--

CREATE TRIGGER users_touch BEFORE UPDATE ON public.users FOR EACH ROW EXECUTE FUNCTION public.app_touch_updated_at();

--
-- Name: vh_reception_supervisor_messages vh_reception_supervisor_message_immutable; Type: TRIGGER; Schema: public; Owner: -
--

CREATE TRIGGER vh_reception_supervisor_message_immutable BEFORE DELETE OR UPDATE ON public.vh_reception_supervisor_messages FOR EACH ROW EXECUTE FUNCTION public.vh_reception_supervisor_message_immutable();

--
-- Name: vh_resident_command_receipts vh_resident_receipt_immutable; Type: TRIGGER; Schema: public; Owner: -
--

CREATE TRIGGER vh_resident_receipt_immutable BEFORE DELETE OR UPDATE ON public.vh_resident_command_receipts FOR EACH ROW EXECUTE FUNCTION public.vh_resident_immutable();

--
-- Name: vh_resident_resolutions vh_resident_resolution_immutable; Type: TRIGGER; Schema: public; Owner: -
--

CREATE TRIGGER vh_resident_resolution_immutable BEFORE DELETE OR UPDATE ON public.vh_resident_resolutions FOR EACH ROW EXECUTE FUNCTION public.vh_resident_immutable();

--
-- Name: vh_resident_resolution_responses vh_resident_response_immutable; Type: TRIGGER; Schema: public; Owner: -
--

CREATE TRIGGER vh_resident_response_immutable BEFORE DELETE OR UPDATE ON public.vh_resident_resolution_responses FOR EACH ROW EXECUTE FUNCTION public.vh_resident_immutable();

--
-- Name: work_approvals work_approvals_touch; Type: TRIGGER; Schema: public; Owner: -
--

CREATE TRIGGER work_approvals_touch BEFORE UPDATE ON public.work_approvals FOR EACH ROW EXECUTE FUNCTION public.app_touch_updated_at();

--
-- Name: work_assignments work_assignments_touch; Type: TRIGGER; Schema: public; Owner: -
--

CREATE TRIGGER work_assignments_touch BEFORE UPDATE ON public.work_assignments FOR EACH ROW EXECUTE FUNCTION public.app_touch_updated_at();

--
-- Name: work_orders work_orders_touch; Type: TRIGGER; Schema: public; Owner: -
--

CREATE TRIGGER work_orders_touch BEFORE UPDATE ON public.work_orders FOR EACH ROW EXECUTE FUNCTION public.app_touch_updated_at();

--
-- Name: workspaces workspaces_touch; Type: TRIGGER; Schema: public; Owner: -
--

CREATE TRIGGER workspaces_touch BEFORE UPDATE ON public.workspaces FOR EACH ROW EXECUTE FUNCTION public.app_touch_updated_at();

--
-- Name: zones zones_touch; Type: TRIGGER; Schema: public; Owner: -
--

CREATE TRIGGER zones_touch BEFORE UPDATE ON public.zones FOR EACH ROW EXECUTE FUNCTION public.app_touch_updated_at();

--
-- Name: access_scopes access_scopes_building_id_fk; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.access_scopes
    ADD CONSTRAINT access_scopes_building_id_fk FOREIGN KEY (tenant_id, building_id) REFERENCES public.buildings(tenant_id, id) ON DELETE RESTRICT;

--
-- Name: access_scopes access_scopes_management_unit_id_fk; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.access_scopes
    ADD CONSTRAINT access_scopes_management_unit_id_fk FOREIGN KEY (tenant_id, management_unit_id) REFERENCES public.management_units(tenant_id, id) ON DELETE RESTRICT;

--
-- Name: access_scopes access_scopes_site_id_fk; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.access_scopes
    ADD CONSTRAINT access_scopes_site_id_fk FOREIGN KEY (tenant_id, site_id) REFERENCES public.sites(tenant_id, id) ON DELETE RESTRICT;

--
-- Name: access_scopes access_scopes_tenant_id_fk; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.access_scopes
    ADD CONSTRAINT access_scopes_tenant_id_fk FOREIGN KEY (tenant_id) REFERENCES public.tenants(id) ON DELETE RESTRICT;

--
-- Name: access_scopes access_scopes_zone_id_fk; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.access_scopes
    ADD CONSTRAINT access_scopes_zone_id_fk FOREIGN KEY (tenant_id, zone_id) REFERENCES public.zones(tenant_id, id) ON DELETE RESTRICT;

--
-- Name: account_reviews account_reviews_reviewer_user_id_fk; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.account_reviews
    ADD CONSTRAINT account_reviews_reviewer_user_id_fk FOREIGN KEY (reviewer_user_id) REFERENCES public.users(id) ON DELETE RESTRICT;

--
-- Name: account_reviews account_reviews_tenant_id_fk; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.account_reviews
    ADD CONSTRAINT account_reviews_tenant_id_fk FOREIGN KEY (tenant_id) REFERENCES public.tenants(id) ON DELETE RESTRICT;

--
-- Name: account_reviews account_reviews_user_id_fk; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.account_reviews
    ADD CONSTRAINT account_reviews_user_id_fk FOREIGN KEY (user_id) REFERENCES public.users(id) ON DELETE RESTRICT;

--
-- Name: accounts accounts_user_id_fk; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.accounts
    ADD CONSTRAINT accounts_user_id_fk FOREIGN KEY (user_id) REFERENCES public.users(id) ON DELETE CASCADE;

--
-- Name: agent_releases agent_releases_agent_id_fk; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.agent_releases
    ADD CONSTRAINT agent_releases_agent_id_fk FOREIGN KEY (tenant_id, agent_id) REFERENCES public.agents(tenant_id, id) ON DELETE RESTRICT;

--
-- Name: agent_releases agent_releases_published_by_fk; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.agent_releases
    ADD CONSTRAINT agent_releases_published_by_fk FOREIGN KEY (published_by) REFERENCES public.users(id) ON DELETE RESTRICT;

--
-- Name: agent_releases agent_releases_tenant_id_fk; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.agent_releases
    ADD CONSTRAINT agent_releases_tenant_id_fk FOREIGN KEY (tenant_id) REFERENCES public.tenants(id) ON DELETE RESTRICT;

--
-- Name: agent_releases agent_releases_version_id_fk; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.agent_releases
    ADD CONSTRAINT agent_releases_version_id_fk FOREIGN KEY (tenant_id, version_id) REFERENCES public.agent_versions(tenant_id, id) ON DELETE RESTRICT;

--
-- Name: agent_runs agent_runs_actor_user_id_fk; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.agent_runs
    ADD CONSTRAINT agent_runs_actor_user_id_fk FOREIGN KEY (actor_user_id) REFERENCES public.users(id) ON DELETE RESTRICT;

--
-- Name: agent_runs agent_runs_agent_id_fk; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.agent_runs
    ADD CONSTRAINT agent_runs_agent_id_fk FOREIGN KEY (tenant_id, agent_id) REFERENCES public.agents(tenant_id, id) ON DELETE RESTRICT;

--
-- Name: agent_runs agent_runs_authority_principal_id_fk; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.agent_runs
    ADD CONSTRAINT agent_runs_authority_principal_id_fk FOREIGN KEY (tenant_id, authority_principal_id) REFERENCES public.execution_principals(tenant_id, id) ON DELETE RESTRICT;

--
-- Name: agent_runs agent_runs_binding_id_fk; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.agent_runs
    ADD CONSTRAINT agent_runs_binding_id_fk FOREIGN KEY (tenant_id, binding_id) REFERENCES public.runtime_session_bindings(tenant_id, id) ON DELETE RESTRICT;

--
-- Name: agent_runs agent_runs_channel_id_fk; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.agent_runs
    ADD CONSTRAINT agent_runs_channel_id_fk FOREIGN KEY (tenant_id, channel_id) REFERENCES public.channels(tenant_id, id) ON DELETE RESTRICT;

--
-- Name: agent_runs agent_runs_on_behalf_of_user_id_fk; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.agent_runs
    ADD CONSTRAINT agent_runs_on_behalf_of_user_id_fk FOREIGN KEY (on_behalf_of_user_id) REFERENCES public.users(id) ON DELETE RESTRICT;

--
-- Name: agent_runs agent_runs_parent_run_id_fk; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.agent_runs
    ADD CONSTRAINT agent_runs_parent_run_id_fk FOREIGN KEY (tenant_id, parent_run_id) REFERENCES public.agent_runs(tenant_id, id) ON DELETE RESTRICT;

--
-- Name: agent_runs agent_runs_team_member_id_fk; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.agent_runs
    ADD CONSTRAINT agent_runs_team_member_id_fk FOREIGN KEY (tenant_id, team_member_id) REFERENCES public.team_members(tenant_id, id) ON DELETE RESTRICT;

--
-- Name: agent_runs agent_runs_tenant_id_fk; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.agent_runs
    ADD CONSTRAINT agent_runs_tenant_id_fk FOREIGN KEY (tenant_id) REFERENCES public.tenants(id) ON DELETE RESTRICT;

--
-- Name: agent_runs agent_runs_trigger_event_id_fk; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.agent_runs
    ADD CONSTRAINT agent_runs_trigger_event_id_fk FOREIGN KEY (tenant_id, trigger_event_id) REFERENCES public.ticket_events(tenant_id, id) ON DELETE RESTRICT;

--
-- Name: agent_runs agent_runs_version_id_fk; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.agent_runs
    ADD CONSTRAINT agent_runs_version_id_fk FOREIGN KEY (tenant_id, version_id) REFERENCES public.agent_versions(tenant_id, id) ON DELETE RESTRICT;

--
-- Name: agent_teams agent_teams_channel_id_fk; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.agent_teams
    ADD CONSTRAINT agent_teams_channel_id_fk FOREIGN KEY (tenant_id, channel_id) REFERENCES public.channels(tenant_id, id) ON DELETE RESTRICT;

--
-- Name: agent_teams agent_teams_request_message_id_fk; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.agent_teams
    ADD CONSTRAINT agent_teams_request_message_id_fk FOREIGN KEY (tenant_id, request_message_id) REFERENCES public.messages(tenant_id, id) ON DELETE RESTRICT;

--
-- Name: agent_teams agent_teams_requested_by_user_id_fk; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.agent_teams
    ADD CONSTRAINT agent_teams_requested_by_user_id_fk FOREIGN KEY (requested_by_user_id) REFERENCES public.users(id) ON DELETE RESTRICT;

--
-- Name: agent_teams agent_teams_supervisor_agent_id_fk; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.agent_teams
    ADD CONSTRAINT agent_teams_supervisor_agent_id_fk FOREIGN KEY (tenant_id, supervisor_agent_id) REFERENCES public.agents(tenant_id, id) ON DELETE RESTRICT;

--
-- Name: agent_teams agent_teams_tenant_id_fk; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.agent_teams
    ADD CONSTRAINT agent_teams_tenant_id_fk FOREIGN KEY (tenant_id) REFERENCES public.tenants(id) ON DELETE RESTRICT;

--
-- Name: agent_teams agent_teams_ticket_id_fk; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.agent_teams
    ADD CONSTRAINT agent_teams_ticket_id_fk FOREIGN KEY (tenant_id, ticket_id) REFERENCES public.tickets(tenant_id, id) ON DELETE RESTRICT;

--
-- Name: agent_teams agent_teams_workspace_id_fk; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.agent_teams
    ADD CONSTRAINT agent_teams_workspace_id_fk FOREIGN KEY (tenant_id, workspace_id) REFERENCES public.workspaces(tenant_id, id) ON DELETE RESTRICT;

--
-- Name: agent_versions agent_versions_agent_id_fk; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.agent_versions
    ADD CONSTRAINT agent_versions_agent_id_fk FOREIGN KEY (tenant_id, agent_id) REFERENCES public.agents(tenant_id, id) ON DELETE RESTRICT;

--
-- Name: agent_versions agent_versions_created_by_fk; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.agent_versions
    ADD CONSTRAINT agent_versions_created_by_fk FOREIGN KEY (created_by) REFERENCES public.users(id) ON DELETE RESTRICT;

--
-- Name: agent_versions agent_versions_tenant_id_fk; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.agent_versions
    ADD CONSTRAINT agent_versions_tenant_id_fk FOREIGN KEY (tenant_id) REFERENCES public.tenants(id) ON DELETE RESTRICT;


--
-- Name: agents agents_tenant_id_fk; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.agents
    ADD CONSTRAINT agents_tenant_id_fk FOREIGN KEY (tenant_id) REFERENCES public.tenants(id) ON DELETE RESTRICT;

--
-- Name: agents agents_workspace_id_fk; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.agents
    ADD CONSTRAINT agents_workspace_id_fk FOREIGN KEY (tenant_id, workspace_id) REFERENCES public.workspaces(tenant_id, id) ON DELETE RESTRICT;

--
-- Name: audit_events audit_events_tenant_id_fk; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.audit_events
    ADD CONSTRAINT audit_events_tenant_id_fk FOREIGN KEY (tenant_id) REFERENCES public.tenants(id) ON DELETE RESTRICT;

--
-- Name: audit_events audit_events_workspace_id_fk; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.audit_events
    ADD CONSTRAINT audit_events_workspace_id_fk FOREIGN KEY (tenant_id, workspace_id) REFERENCES public.workspaces(tenant_id, id) ON DELETE RESTRICT;

--
-- Name: runtime_session_bindings binding_identity_backend_fk; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.runtime_session_bindings
    ADD CONSTRAINT binding_identity_backend_fk FOREIGN KEY (tenant_id, identity_id, backend_id) REFERENCES public.runtime_identities(tenant_id, id, backend_id);

--
-- Name: buildings buildings_site_id_fk; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.buildings
    ADD CONSTRAINT buildings_site_id_fk FOREIGN KEY (tenant_id, site_id) REFERENCES public.sites(tenant_id, id) ON DELETE RESTRICT;

--
-- Name: buildings buildings_tenant_id_fk; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.buildings
    ADD CONSTRAINT buildings_tenant_id_fk FOREIGN KEY (tenant_id) REFERENCES public.tenants(id) ON DELETE RESTRICT;

--
-- Name: buildings buildings_zone_id_fk; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.buildings
    ADD CONSTRAINT buildings_zone_id_fk FOREIGN KEY (tenant_id, zone_id) REFERENCES public.zones(tenant_id, id) ON DELETE RESTRICT;

--
-- Name: channel_agents channel_agents_agent_id_fk; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.channel_agents
    ADD CONSTRAINT channel_agents_agent_id_fk FOREIGN KEY (tenant_id, agent_id) REFERENCES public.agents(tenant_id, id) ON DELETE RESTRICT;

--
-- Name: channel_agents channel_agents_channel_id_fk; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.channel_agents
    ADD CONSTRAINT channel_agents_channel_id_fk FOREIGN KEY (tenant_id, channel_id) REFERENCES public.channels(tenant_id, id) ON DELETE RESTRICT;

--
-- Name: channel_agents channel_agents_tenant_id_fk; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.channel_agents
    ADD CONSTRAINT channel_agents_tenant_id_fk FOREIGN KEY (tenant_id) REFERENCES public.tenants(id) ON DELETE RESTRICT;

--
-- Name: channel_memberships channel_memberships_channel_id_fk; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.channel_memberships
    ADD CONSTRAINT channel_memberships_channel_id_fk FOREIGN KEY (tenant_id, channel_id) REFERENCES public.channels(tenant_id, id) ON DELETE RESTRICT;

--
-- Name: channel_memberships channel_memberships_tenant_id_fk; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.channel_memberships
    ADD CONSTRAINT channel_memberships_tenant_id_fk FOREIGN KEY (tenant_id) REFERENCES public.tenants(id) ON DELETE RESTRICT;

--
-- Name: channel_memberships channel_memberships_user_id_fk; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.channel_memberships
    ADD CONSTRAINT channel_memberships_user_id_fk FOREIGN KEY (user_id) REFERENCES public.users(id) ON DELETE RESTRICT;

--
-- Name: channels channels_created_by_fk; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.channels
    ADD CONSTRAINT channels_created_by_fk FOREIGN KEY (created_by) REFERENCES public.users(id) ON DELETE RESTRICT;

--
-- Name: channels channels_last_message_agent_id_fk; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.channels
    ADD CONSTRAINT channels_last_message_agent_id_fk FOREIGN KEY (tenant_id, last_message_agent_id) REFERENCES public.agents(tenant_id, id) ON DELETE RESTRICT;


--
-- Name: channels channels_tenant_id_fk; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.channels
    ADD CONSTRAINT channels_tenant_id_fk FOREIGN KEY (tenant_id) REFERENCES public.tenants(id) ON DELETE RESTRICT;

--
-- Name: channels channels_workspace_id_fk; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.channels
    ADD CONSTRAINT channels_workspace_id_fk FOREIGN KEY (tenant_id, workspace_id) REFERENCES public.workspaces(tenant_id, id) ON DELETE RESTRICT;

--
-- Name: dispatch_attempts dispatch_attempts_assignment_id_fk; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.dispatch_attempts
    ADD CONSTRAINT dispatch_attempts_assignment_id_fk FOREIGN KEY (tenant_id, assignment_id) REFERENCES public.work_assignments(tenant_id, id) ON DELETE RESTRICT;

--
-- Name: dispatch_attempts dispatch_attempts_decision_id_fk; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.dispatch_attempts
    ADD CONSTRAINT dispatch_attempts_decision_id_fk FOREIGN KEY (tenant_id, decision_id) REFERENCES public.ticket_triage_decisions(tenant_id, id) ON DELETE RESTRICT;

--
-- Name: dispatch_attempts dispatch_attempts_queue_id_fk; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.dispatch_attempts
    ADD CONSTRAINT dispatch_attempts_queue_id_fk FOREIGN KEY (tenant_id, queue_id) REFERENCES public.dispatch_queue(tenant_id, id) ON DELETE RESTRICT;

--
-- Name: dispatch_attempts dispatch_attempts_tenant_id_fk; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.dispatch_attempts
    ADD CONSTRAINT dispatch_attempts_tenant_id_fk FOREIGN KEY (tenant_id) REFERENCES public.tenants(id) ON DELETE RESTRICT;

--
-- Name: dispatch_attempts dispatch_attempts_work_order_id_fk; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.dispatch_attempts
    ADD CONSTRAINT dispatch_attempts_work_order_id_fk FOREIGN KEY (tenant_id, work_order_id) REFERENCES public.work_orders(tenant_id, id) ON DELETE RESTRICT;

--
-- Name: dispatch_queue dispatch_queue_category_id_fk; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.dispatch_queue
    ADD CONSTRAINT dispatch_queue_category_id_fk FOREIGN KEY (tenant_id, category_id) REFERENCES public.service_categories(tenant_id, id) ON DELETE RESTRICT;

--
-- Name: dispatch_queue dispatch_queue_management_unit_id_fk; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.dispatch_queue
    ADD CONSTRAINT dispatch_queue_management_unit_id_fk FOREIGN KEY (tenant_id, management_unit_id) REFERENCES public.management_units(tenant_id, id) ON DELETE RESTRICT;

--
-- Name: dispatch_queue dispatch_queue_priority_decision_id_fk; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.dispatch_queue
    ADD CONSTRAINT dispatch_queue_priority_decision_id_fk FOREIGN KEY (tenant_id, priority_decision_id) REFERENCES public.ticket_triage_decisions(tenant_id, id) ON DELETE RESTRICT;

--
-- Name: dispatch_queue dispatch_queue_tenant_id_fk; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.dispatch_queue
    ADD CONSTRAINT dispatch_queue_tenant_id_fk FOREIGN KEY (tenant_id) REFERENCES public.tenants(id) ON DELETE RESTRICT;

--
-- Name: dispatch_queue dispatch_queue_work_order_id_fk; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.dispatch_queue
    ADD CONSTRAINT dispatch_queue_work_order_id_fk FOREIGN KEY (tenant_id, work_order_id) REFERENCES public.work_orders(tenant_id, id) ON DELETE RESTRICT;

--
-- Name: domains domains_tenant_id_fk; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.domains
    ADD CONSTRAINT domains_tenant_id_fk FOREIGN KEY (tenant_id) REFERENCES public.tenants(id) ON DELETE RESTRICT;

--
-- Name: event_inbox event_inbox_event_id_fk; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.event_inbox
    ADD CONSTRAINT event_inbox_event_id_fk FOREIGN KEY (tenant_id, event_id) REFERENCES public.ticket_events(tenant_id, id) ON DELETE RESTRICT;

--
-- Name: event_inbox event_inbox_tenant_id_fk; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.event_inbox
    ADD CONSTRAINT event_inbox_tenant_id_fk FOREIGN KEY (tenant_id) REFERENCES public.tenants(id) ON DELETE RESTRICT;

--
-- Name: event_outbox event_outbox_event_id_fk; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.event_outbox
    ADD CONSTRAINT event_outbox_event_id_fk FOREIGN KEY (tenant_id, event_id) REFERENCES public.ticket_events(tenant_id, id) ON DELETE RESTRICT;

--
-- Name: event_outbox event_outbox_tenant_id_fk; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.event_outbox
    ADD CONSTRAINT event_outbox_tenant_id_fk FOREIGN KEY (tenant_id) REFERENCES public.tenants(id) ON DELETE RESTRICT;

--
-- Name: evidence_items evidence_items_assignment_id_fk; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.evidence_items
    ADD CONSTRAINT evidence_items_assignment_id_fk FOREIGN KEY (tenant_id, assignment_id) REFERENCES public.work_assignments(tenant_id, id) ON DELETE RESTRICT;

--
-- Name: evidence_items evidence_items_file_id_fk; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.evidence_items
    ADD CONSTRAINT evidence_items_file_id_fk FOREIGN KEY (tenant_id, file_id) REFERENCES public.files(tenant_id, id) ON DELETE RESTRICT;

--
-- Name: evidence_items evidence_items_supersedes_id_fk; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.evidence_items
    ADD CONSTRAINT evidence_items_supersedes_id_fk FOREIGN KEY (tenant_id, supersedes_id) REFERENCES public.evidence_items(tenant_id, id) ON DELETE RESTRICT;

--
-- Name: evidence_items evidence_items_tenant_id_fk; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.evidence_items
    ADD CONSTRAINT evidence_items_tenant_id_fk FOREIGN KEY (tenant_id) REFERENCES public.tenants(id) ON DELETE RESTRICT;

--
-- Name: evidence_items evidence_items_ticket_id_fk; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.evidence_items
    ADD CONSTRAINT evidence_items_ticket_id_fk FOREIGN KEY (tenant_id, ticket_id) REFERENCES public.tickets(tenant_id, id) ON DELETE RESTRICT;

--
-- Name: evidence_items evidence_items_uploaded_by_fk; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.evidence_items
    ADD CONSTRAINT evidence_items_uploaded_by_fk FOREIGN KEY (uploaded_by) REFERENCES public.users(id) ON DELETE RESTRICT;

--
-- Name: evidence_items evidence_items_work_order_id_fk; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.evidence_items
    ADD CONSTRAINT evidence_items_work_order_id_fk FOREIGN KEY (tenant_id, work_order_id) REFERENCES public.work_orders(tenant_id, id) ON DELETE RESTRICT;

--
-- Name: execution_principals execution_principals_tenant_id_fk; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.execution_principals
    ADD CONSTRAINT execution_principals_tenant_id_fk FOREIGN KEY (tenant_id) REFERENCES public.tenants(id) ON DELETE RESTRICT;

--
-- Name: execution_principals execution_principals_user_id_fk; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.execution_principals
    ADD CONSTRAINT execution_principals_user_id_fk FOREIGN KEY (user_id) REFERENCES public.users(id) ON DELETE RESTRICT;

--
-- Name: execution_principals execution_principals_workspace_id_fk; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.execution_principals
    ADD CONSTRAINT execution_principals_workspace_id_fk FOREIGN KEY (tenant_id, workspace_id) REFERENCES public.workspaces(tenant_id, id) ON DELETE RESTRICT;

--
-- Name: file_objects file_objects_file_id_fk; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.file_objects
    ADD CONSTRAINT file_objects_file_id_fk FOREIGN KEY (tenant_id, file_id) REFERENCES public.files(tenant_id, id) ON DELETE RESTRICT;

--
-- Name: file_objects file_objects_location_id_fk; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.file_objects
    ADD CONSTRAINT file_objects_location_id_fk FOREIGN KEY (tenant_id, location_id) REFERENCES public.storage_locations(tenant_id, id) ON DELETE RESTRICT;

--
-- Name: file_objects file_objects_source_object_id_fk; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.file_objects
    ADD CONSTRAINT file_objects_source_object_id_fk FOREIGN KEY (tenant_id, source_object_id) REFERENCES public.file_objects(tenant_id, id) ON DELETE RESTRICT;

--
-- Name: file_objects file_objects_tenant_id_fk; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.file_objects
    ADD CONSTRAINT file_objects_tenant_id_fk FOREIGN KEY (tenant_id) REFERENCES public.tenants(id) ON DELETE RESTRICT;

--
-- Name: file_uploads file_uploads_file_id_fk; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.file_uploads
    ADD CONSTRAINT file_uploads_file_id_fk FOREIGN KEY (tenant_id, file_id) REFERENCES public.files(tenant_id, id) ON DELETE RESTRICT;

--
-- Name: file_uploads file_uploads_location_id_fk; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.file_uploads
    ADD CONSTRAINT file_uploads_location_id_fk FOREIGN KEY (tenant_id, location_id) REFERENCES public.storage_locations(tenant_id, id) ON DELETE RESTRICT;

--
-- Name: file_uploads file_uploads_requested_by_fk; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.file_uploads
    ADD CONSTRAINT file_uploads_requested_by_fk FOREIGN KEY (requested_by) REFERENCES public.users(id) ON DELETE RESTRICT;

--
-- Name: file_uploads file_uploads_result_object_id_fk; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.file_uploads
    ADD CONSTRAINT file_uploads_result_object_id_fk FOREIGN KEY (tenant_id, result_object_id) REFERENCES public.file_objects(tenant_id, id) ON DELETE RESTRICT;

--
-- Name: file_uploads file_uploads_tenant_id_fk; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.file_uploads
    ADD CONSTRAINT file_uploads_tenant_id_fk FOREIGN KEY (tenant_id) REFERENCES public.tenants(id) ON DELETE RESTRICT;

--
-- Name: files files_accepted_object_id_fk; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.files
    ADD CONSTRAINT files_accepted_object_id_fk FOREIGN KEY (tenant_id, accepted_object_id) REFERENCES public.file_objects(tenant_id, id) ON DELETE RESTRICT;

--
-- Name: files files_channel_id_fk; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.files
    ADD CONSTRAINT files_channel_id_fk FOREIGN KEY (tenant_id, channel_id) REFERENCES public.channels(tenant_id, id) ON DELETE RESTRICT;


--
-- Name: files files_owner_principal_id_fk; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.files
    ADD CONSTRAINT files_owner_principal_id_fk FOREIGN KEY (tenant_id, owner_principal_id) REFERENCES public.execution_principals(tenant_id, id) ON DELETE RESTRICT;

--
-- Name: files files_tenant_id_fk; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.files
    ADD CONSTRAINT files_tenant_id_fk FOREIGN KEY (tenant_id) REFERENCES public.tenants(id) ON DELETE RESTRICT;

--
-- Name: files files_ticket_id_fk; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.files
    ADD CONSTRAINT files_ticket_id_fk FOREIGN KEY (tenant_id, ticket_id) REFERENCES public.tickets(tenant_id, id) ON DELETE RESTRICT;

--
-- Name: files files_unit_id_fk; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.files
    ADD CONSTRAINT files_unit_id_fk FOREIGN KEY (tenant_id, unit_id) REFERENCES public.units(tenant_id, id);

--
-- Name: files files_uploaded_by_fk; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.files
    ADD CONSTRAINT files_uploaded_by_fk FOREIGN KEY (uploaded_by) REFERENCES public.users(id) ON DELETE RESTRICT;

--
-- Name: incident_types incident_types_category_id_fk; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.incident_types
    ADD CONSTRAINT incident_types_category_id_fk FOREIGN KEY (tenant_id, category_id) REFERENCES public.service_categories(tenant_id, id) ON DELETE RESTRICT;

--
-- Name: incident_types incident_types_tenant_id_fk; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.incident_types
    ADD CONSTRAINT incident_types_tenant_id_fk FOREIGN KEY (tenant_id) REFERENCES public.tenants(id) ON DELETE RESTRICT;

--
-- Name: interruption_scopes interruption_scopes_interruption_id_fk; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.interruption_scopes
    ADD CONSTRAINT interruption_scopes_interruption_id_fk FOREIGN KEY (tenant_id, interruption_id) REFERENCES public.service_interruptions(tenant_id, id) ON DELETE RESTRICT;

--
-- Name: interruption_scopes interruption_scopes_scope_id_fk; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.interruption_scopes
    ADD CONSTRAINT interruption_scopes_scope_id_fk FOREIGN KEY (tenant_id, scope_id) REFERENCES public.access_scopes(tenant_id, id) ON DELETE RESTRICT;

--
-- Name: interruption_scopes interruption_scopes_tenant_id_fk; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.interruption_scopes
    ADD CONSTRAINT interruption_scopes_tenant_id_fk FOREIGN KEY (tenant_id) REFERENCES public.tenants(id) ON DELETE RESTRICT;

--
-- Name: invoice_lines invoice_lines_category_id_fk; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.invoice_lines
    ADD CONSTRAINT invoice_lines_category_id_fk FOREIGN KEY (tenant_id, category_id) REFERENCES public.service_categories(tenant_id, id) ON DELETE RESTRICT;

--
-- Name: invoice_lines invoice_lines_invoice_id_fk; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.invoice_lines
    ADD CONSTRAINT invoice_lines_invoice_id_fk FOREIGN KEY (tenant_id, invoice_id) REFERENCES public.invoices(tenant_id, id) ON DELETE RESTRICT;

--
-- Name: invoice_lines invoice_lines_tenant_id_fk; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.invoice_lines
    ADD CONSTRAINT invoice_lines_tenant_id_fk FOREIGN KEY (tenant_id) REFERENCES public.tenants(id) ON DELETE RESTRICT;

--
-- Name: invoices invoices_bill_to_user_id_fk; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.invoices
    ADD CONSTRAINT invoices_bill_to_user_id_fk FOREIGN KEY (bill_to_user_id) REFERENCES public.users(id) ON DELETE RESTRICT;

--
-- Name: invoices invoices_issued_by_staff_id_fk; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.invoices
    ADD CONSTRAINT invoices_issued_by_staff_id_fk FOREIGN KEY (tenant_id, issued_by_staff_id) REFERENCES public.staff_profiles(tenant_id, id) ON DELETE RESTRICT;

--
-- Name: invoices invoices_legal_invoice_file_id_fk; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.invoices
    ADD CONSTRAINT invoices_legal_invoice_file_id_fk FOREIGN KEY (tenant_id, legal_invoice_file_id) REFERENCES public.files(tenant_id, id) ON DELETE RESTRICT;

--
-- Name: invoices invoices_supersedes_invoice_id_fk; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.invoices
    ADD CONSTRAINT invoices_supersedes_invoice_id_fk FOREIGN KEY (tenant_id, supersedes_invoice_id) REFERENCES public.invoices(tenant_id, id) ON DELETE RESTRICT;

--
-- Name: invoices invoices_tenant_id_fk; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.invoices
    ADD CONSTRAINT invoices_tenant_id_fk FOREIGN KEY (tenant_id) REFERENCES public.tenants(id) ON DELETE RESTRICT;

--
-- Name: invoices invoices_ticket_id_fk; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.invoices
    ADD CONSTRAINT invoices_ticket_id_fk FOREIGN KEY (tenant_id, ticket_id) REFERENCES public.tickets(tenant_id, id) ON DELETE RESTRICT;

--
-- Name: invoices invoices_work_order_id_fk; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.invoices
    ADD CONSTRAINT invoices_work_order_id_fk FOREIGN KEY (tenant_id, work_order_id) REFERENCES public.work_orders(tenant_id, id) ON DELETE RESTRICT;

--
-- Name: management_coverage management_coverage_management_unit_id_fk; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.management_coverage
    ADD CONSTRAINT management_coverage_management_unit_id_fk FOREIGN KEY (tenant_id, management_unit_id) REFERENCES public.management_units(tenant_id, id) ON DELETE RESTRICT;

--
-- Name: management_coverage management_coverage_scope_id_fk; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.management_coverage
    ADD CONSTRAINT management_coverage_scope_id_fk FOREIGN KEY (tenant_id, scope_id) REFERENCES public.access_scopes(tenant_id, id) ON DELETE RESTRICT;

--
-- Name: management_coverage management_coverage_service_category_id_fk; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.management_coverage
    ADD CONSTRAINT management_coverage_service_category_id_fk FOREIGN KEY (tenant_id, service_category_id) REFERENCES public.service_categories(tenant_id, id) ON DELETE RESTRICT;

--
-- Name: management_coverage management_coverage_tenant_id_fk; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.management_coverage
    ADD CONSTRAINT management_coverage_tenant_id_fk FOREIGN KEY (tenant_id) REFERENCES public.tenants(id) ON DELETE RESTRICT;

--
-- Name: management_units management_units_tenant_id_fk; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.management_units
    ADD CONSTRAINT management_units_tenant_id_fk FOREIGN KEY (tenant_id) REFERENCES public.tenants(id) ON DELETE RESTRICT;

--
-- Name: message_files message_files_file_id_fk; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.message_files
    ADD CONSTRAINT message_files_file_id_fk FOREIGN KEY (tenant_id, file_id) REFERENCES public.files(tenant_id, id) ON DELETE RESTRICT;

--
-- Name: message_files message_files_message_id_fk; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.message_files
    ADD CONSTRAINT message_files_message_id_fk FOREIGN KEY (tenant_id, message_id) REFERENCES public.messages(tenant_id, id) ON DELETE RESTRICT;

--
-- Name: message_files message_files_tenant_id_fk; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.message_files
    ADD CONSTRAINT message_files_tenant_id_fk FOREIGN KEY (tenant_id) REFERENCES public.tenants(id) ON DELETE RESTRICT;

--
-- Name: messages messages_channel_id_fk; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.messages
    ADD CONSTRAINT messages_channel_id_fk FOREIGN KEY (tenant_id, channel_id) REFERENCES public.channels(tenant_id, id) ON DELETE RESTRICT;

--
-- Name: messages messages_reply_to_id_fk; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.messages
    ADD CONSTRAINT messages_reply_to_id_fk FOREIGN KEY (tenant_id, reply_to_id) REFERENCES public.messages(tenant_id, id) ON DELETE RESTRICT;

--
-- Name: messages messages_run_id_fk; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.messages
    ADD CONSTRAINT messages_run_id_fk FOREIGN KEY (tenant_id, run_id) REFERENCES public.agent_runs(tenant_id, id) ON DELETE RESTRICT;

--
-- Name: messages messages_sender_agent_id_fk; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.messages
    ADD CONSTRAINT messages_sender_agent_id_fk FOREIGN KEY (tenant_id, sender_agent_id) REFERENCES public.agents(tenant_id, id) ON DELETE RESTRICT;

--
-- Name: messages messages_sender_user_id_fk; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.messages
    ADD CONSTRAINT messages_sender_user_id_fk FOREIGN KEY (sender_user_id) REFERENCES public.users(id) ON DELETE RESTRICT;

--
-- Name: messages messages_source_event_id_fk; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.messages
    ADD CONSTRAINT messages_source_event_id_fk FOREIGN KEY (tenant_id, source_event_id) REFERENCES public.ticket_events(tenant_id, id) ON DELETE RESTRICT;

--
-- Name: messages messages_tenant_id_fk; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.messages
    ADD CONSTRAINT messages_tenant_id_fk FOREIGN KEY (tenant_id) REFERENCES public.tenants(id) ON DELETE RESTRICT;

--
-- Name: notification_deliveries notification_deliveries_interruption_id_fk; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.notification_deliveries
    ADD CONSTRAINT notification_deliveries_interruption_id_fk FOREIGN KEY (tenant_id, interruption_id) REFERENCES public.service_interruptions(tenant_id, id) ON DELETE RESTRICT;

--
-- Name: notification_deliveries notification_deliveries_message_id_fk; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.notification_deliveries
    ADD CONSTRAINT notification_deliveries_message_id_fk FOREIGN KEY (tenant_id, message_id) REFERENCES public.messages(tenant_id, id) ON DELETE RESTRICT;

--
-- Name: notification_deliveries notification_deliveries_tenant_id_fk; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.notification_deliveries
    ADD CONSTRAINT notification_deliveries_tenant_id_fk FOREIGN KEY (tenant_id) REFERENCES public.tenants(id) ON DELETE RESTRICT;

--
-- Name: notification_deliveries notification_deliveries_ticket_event_id_fk; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.notification_deliveries
    ADD CONSTRAINT notification_deliveries_ticket_event_id_fk FOREIGN KEY (tenant_id, ticket_event_id) REFERENCES public.ticket_events(tenant_id, id) ON DELETE RESTRICT;

--
-- Name: notification_deliveries notification_deliveries_user_id_fk; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.notification_deliveries
    ADD CONSTRAINT notification_deliveries_user_id_fk FOREIGN KEY (user_id) REFERENCES public.users(id) ON DELETE RESTRICT;

--
-- Name: payment_allocations payment_allocations_invoice_id_fk; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.payment_allocations
    ADD CONSTRAINT payment_allocations_invoice_id_fk FOREIGN KEY (tenant_id, invoice_id) REFERENCES public.invoices(tenant_id, id) ON DELETE RESTRICT;

--
-- Name: payment_allocations payment_allocations_payment_id_fk; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.payment_allocations
    ADD CONSTRAINT payment_allocations_payment_id_fk FOREIGN KEY (tenant_id, payment_id) REFERENCES public.payments(tenant_id, id) ON DELETE RESTRICT;

--
-- Name: payment_allocations payment_allocations_tenant_id_fk; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.payment_allocations
    ADD CONSTRAINT payment_allocations_tenant_id_fk FOREIGN KEY (tenant_id) REFERENCES public.tenants(id) ON DELETE RESTRICT;

--
-- Name: payment_intents payment_intents_invoice_id_fk; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.payment_intents
    ADD CONSTRAINT payment_intents_invoice_id_fk FOREIGN KEY (tenant_id, invoice_id) REFERENCES public.invoices(tenant_id, id) ON DELETE RESTRICT;

--
-- Name: payment_intents payment_intents_tenant_id_fk; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.payment_intents
    ADD CONSTRAINT payment_intents_tenant_id_fk FOREIGN KEY (tenant_id) REFERENCES public.tenants(id) ON DELETE RESTRICT;

--
-- Name: payment_webhook_receipts payment_webhook_receipts_intent_id_fk; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.payment_webhook_receipts
    ADD CONSTRAINT payment_webhook_receipts_intent_id_fk FOREIGN KEY (tenant_id, intent_id) REFERENCES public.payment_intents(tenant_id, id) ON DELETE RESTRICT;

--
-- Name: payment_webhook_receipts payment_webhook_receipts_tenant_id_fk; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.payment_webhook_receipts
    ADD CONSTRAINT payment_webhook_receipts_tenant_id_fk FOREIGN KEY (tenant_id) REFERENCES public.tenants(id) ON DELETE RESTRICT;

--
-- Name: payments payments_intent_id_fk; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.payments
    ADD CONSTRAINT payments_intent_id_fk FOREIGN KEY (tenant_id, intent_id) REFERENCES public.payment_intents(tenant_id, id) ON DELETE RESTRICT;

--
-- Name: payments payments_invoice_id_fk; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.payments
    ADD CONSTRAINT payments_invoice_id_fk FOREIGN KEY (tenant_id, invoice_id) REFERENCES public.invoices(tenant_id, id) ON DELETE RESTRICT;

--
-- Name: payments payments_receipt_id_fk; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.payments
    ADD CONSTRAINT payments_receipt_id_fk FOREIGN KEY (tenant_id, receipt_id) REFERENCES public.payment_webhook_receipts(tenant_id, id) ON DELETE RESTRICT;

--
-- Name: payments payments_tenant_id_fk; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.payments
    ADD CONSTRAINT payments_tenant_id_fk FOREIGN KEY (tenant_id) REFERENCES public.tenants(id) ON DELETE RESTRICT;

--
-- Name: platform_admins platform_admins_granted_by_fk; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.platform_admins
    ADD CONSTRAINT platform_admins_granted_by_fk FOREIGN KEY (granted_by) REFERENCES public.users(id) ON DELETE RESTRICT;

--
-- Name: platform_admins platform_admins_user_id_fk; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.platform_admins
    ADD CONSTRAINT platform_admins_user_id_fk FOREIGN KEY (user_id) REFERENCES public.users(id) ON DELETE RESTRICT;

--
-- Name: runtime_identities runtime_identities_backend_id_fk; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.runtime_identities
    ADD CONSTRAINT runtime_identities_backend_id_fk FOREIGN KEY (backend_id) REFERENCES public.runtime_backends(id) ON DELETE RESTRICT;

--
-- Name: runtime_identities runtime_identities_principal_id_fk; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.runtime_identities
    ADD CONSTRAINT runtime_identities_principal_id_fk FOREIGN KEY (tenant_id, principal_id) REFERENCES public.execution_principals(tenant_id, id) ON DELETE RESTRICT;

--
-- Name: runtime_identities runtime_identities_tenant_id_fk; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.runtime_identities
    ADD CONSTRAINT runtime_identities_tenant_id_fk FOREIGN KEY (tenant_id) REFERENCES public.tenants(id) ON DELETE RESTRICT;

--
-- Name: runtime_session_bindings runtime_session_bindings_agent_id_fk; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.runtime_session_bindings
    ADD CONSTRAINT runtime_session_bindings_agent_id_fk FOREIGN KEY (tenant_id, agent_id) REFERENCES public.agents(tenant_id, id) ON DELETE RESTRICT;

--
-- Name: runtime_session_bindings runtime_session_bindings_agent_version_id_fk; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.runtime_session_bindings
    ADD CONSTRAINT runtime_session_bindings_agent_version_id_fk FOREIGN KEY (tenant_id, agent_version_id) REFERENCES public.agent_versions(tenant_id, id) ON DELETE RESTRICT;

--
-- Name: runtime_session_bindings runtime_session_bindings_backend_id_fk; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.runtime_session_bindings
    ADD CONSTRAINT runtime_session_bindings_backend_id_fk FOREIGN KEY (backend_id) REFERENCES public.runtime_backends(id) ON DELETE RESTRICT;

--
-- Name: runtime_session_bindings runtime_session_bindings_channel_id_fk; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.runtime_session_bindings
    ADD CONSTRAINT runtime_session_bindings_channel_id_fk FOREIGN KEY (tenant_id, channel_id) REFERENCES public.channels(tenant_id, id) ON DELETE RESTRICT;

--
-- Name: runtime_session_bindings runtime_session_bindings_customer_user_id_fk; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.runtime_session_bindings
    ADD CONSTRAINT runtime_session_bindings_customer_user_id_fk FOREIGN KEY (customer_user_id) REFERENCES public.users(id) ON DELETE RESTRICT;

--
-- Name: runtime_session_bindings runtime_session_bindings_identity_id_fk; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.runtime_session_bindings
    ADD CONSTRAINT runtime_session_bindings_identity_id_fk FOREIGN KEY (tenant_id, identity_id) REFERENCES public.runtime_identities(tenant_id, id) ON DELETE RESTRICT;

--
-- Name: runtime_session_bindings runtime_session_bindings_started_by_user_id_fk; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.runtime_session_bindings
    ADD CONSTRAINT runtime_session_bindings_started_by_user_id_fk FOREIGN KEY (started_by_user_id) REFERENCES public.users(id) ON DELETE RESTRICT;

--
-- Name: runtime_session_bindings runtime_session_bindings_team_member_id_fk; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.runtime_session_bindings
    ADD CONSTRAINT runtime_session_bindings_team_member_id_fk FOREIGN KEY (tenant_id, team_member_id) REFERENCES public.team_members(tenant_id, id) ON DELETE RESTRICT;

--
-- Name: runtime_session_bindings runtime_session_bindings_tenant_id_fk; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.runtime_session_bindings
    ADD CONSTRAINT runtime_session_bindings_tenant_id_fk FOREIGN KEY (tenant_id) REFERENCES public.tenants(id) ON DELETE RESTRICT;

--
-- Name: scoped_user_roles scoped_user_roles_granted_by_fk; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.scoped_user_roles
    ADD CONSTRAINT scoped_user_roles_granted_by_fk FOREIGN KEY (granted_by) REFERENCES public.users(id) ON DELETE RESTRICT;

--
-- Name: scoped_user_roles scoped_user_roles_membership_id_fk; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.scoped_user_roles
    ADD CONSTRAINT scoped_user_roles_membership_id_fk FOREIGN KEY (tenant_id, membership_id) REFERENCES public.tenant_memberships(tenant_id, id) ON DELETE RESTRICT;

--
-- Name: scoped_user_roles scoped_user_roles_scope_id_fk; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.scoped_user_roles
    ADD CONSTRAINT scoped_user_roles_scope_id_fk FOREIGN KEY (tenant_id, scope_id) REFERENCES public.access_scopes(tenant_id, id) ON DELETE RESTRICT;

--
-- Name: scoped_user_roles scoped_user_roles_tenant_id_fk; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.scoped_user_roles
    ADD CONSTRAINT scoped_user_roles_tenant_id_fk FOREIGN KEY (tenant_id) REFERENCES public.tenants(id) ON DELETE RESTRICT;

--
-- Name: security_alert_deliveries security_alert_deliveries_recipient_user_id_users_id_fk; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.security_alert_deliveries
    ADD CONSTRAINT security_alert_deliveries_recipient_user_id_users_id_fk FOREIGN KEY (recipient_user_id) REFERENCES public.users(id);

--
-- Name: security_alert_deliveries security_alert_deliveries_tenant_id_alert_id_security_alerts_te; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.security_alert_deliveries
    ADD CONSTRAINT security_alert_deliveries_tenant_id_alert_id_security_alerts_te FOREIGN KEY (tenant_id, alert_id) REFERENCES public.security_alerts(tenant_id, id);

--
-- Name: security_alert_deliveries security_alert_deliveries_tenant_id_contact_id_security_emergen; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.security_alert_deliveries
    ADD CONSTRAINT security_alert_deliveries_tenant_id_contact_id_security_emergen FOREIGN KEY (tenant_id, contact_id) REFERENCES public.security_emergency_contacts(tenant_id, id);

--
-- Name: security_alert_deliveries security_alert_deliveries_tenant_id_tenants_id_fk; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.security_alert_deliveries
    ADD CONSTRAINT security_alert_deliveries_tenant_id_tenants_id_fk FOREIGN KEY (tenant_id) REFERENCES public.tenants(id);

--
-- Name: security_alerts security_alerts_created_by_users_id_fk; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.security_alerts
    ADD CONSTRAINT security_alerts_created_by_users_id_fk FOREIGN KEY (created_by) REFERENCES public.users(id);

--
-- Name: security_alerts security_alerts_tenant_id_tenants_id_fk; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.security_alerts
    ADD CONSTRAINT security_alerts_tenant_id_tenants_id_fk FOREIGN KEY (tenant_id) REFERENCES public.tenants(id);

--
-- Name: security_alerts security_alerts_tenant_id_ticket_id_tickets_tenant_id_id_fk; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.security_alerts
    ADD CONSTRAINT security_alerts_tenant_id_ticket_id_tickets_tenant_id_id_fk FOREIGN KEY (tenant_id, ticket_id) REFERENCES public.tickets(tenant_id, id);

--
-- Name: security_cameras security_cameras_tenant_id_building_id_buildings_tenant_id_id_f; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.security_cameras
    ADD CONSTRAINT security_cameras_tenant_id_building_id_buildings_tenant_id_id_f FOREIGN KEY (tenant_id, building_id) REFERENCES public.buildings(tenant_id, id);

--
-- Name: security_cameras security_cameras_tenant_id_tenants_id_fk; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.security_cameras
    ADD CONSTRAINT security_cameras_tenant_id_tenants_id_fk FOREIGN KEY (tenant_id) REFERENCES public.tenants(id);

--
-- Name: security_emergency_contacts security_emergency_contacts_tenant_id_building_id_buildings_ten; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.security_emergency_contacts
    ADD CONSTRAINT security_emergency_contacts_tenant_id_building_id_buildings_ten FOREIGN KEY (tenant_id, building_id) REFERENCES public.buildings(tenant_id, id);

--
-- Name: security_emergency_contacts security_emergency_contacts_tenant_id_tenants_id_fk; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.security_emergency_contacts
    ADD CONSTRAINT security_emergency_contacts_tenant_id_tenants_id_fk FOREIGN KEY (tenant_id) REFERENCES public.tenants(id);

--
-- Name: security_emergency_contacts security_emergency_contacts_user_id_users_id_fk; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.security_emergency_contacts
    ADD CONSTRAINT security_emergency_contacts_user_id_users_id_fk FOREIGN KEY (user_id) REFERENCES public.users(id);

--
-- Name: service_categories service_categories_parent_id_fk; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.service_categories
    ADD CONSTRAINT service_categories_parent_id_fk FOREIGN KEY (tenant_id, parent_id) REFERENCES public.service_categories(tenant_id, id) ON DELETE RESTRICT;

--
-- Name: service_categories service_categories_tenant_id_fk; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.service_categories
    ADD CONSTRAINT service_categories_tenant_id_fk FOREIGN KEY (tenant_id) REFERENCES public.tenants(id) ON DELETE RESTRICT;

--
-- Name: service_interruptions service_interruptions_approval_id_fk; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.service_interruptions
    ADD CONSTRAINT service_interruptions_approval_id_fk FOREIGN KEY (tenant_id, approval_id) REFERENCES public.work_approvals(tenant_id, id) ON DELETE RESTRICT;

--
-- Name: service_interruptions service_interruptions_operated_by_fk; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.service_interruptions
    ADD CONSTRAINT service_interruptions_operated_by_fk FOREIGN KEY (operated_by) REFERENCES public.users(id) ON DELETE RESTRICT;

--
-- Name: service_interruptions service_interruptions_tenant_id_fk; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.service_interruptions
    ADD CONSTRAINT service_interruptions_tenant_id_fk FOREIGN KEY (tenant_id) REFERENCES public.tenants(id) ON DELETE RESTRICT;

--
-- Name: service_interruptions service_interruptions_work_order_id_fk; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.service_interruptions
    ADD CONSTRAINT service_interruptions_work_order_id_fk FOREIGN KEY (tenant_id, work_order_id) REFERENCES public.work_orders(tenant_id, id) ON DELETE RESTRICT;

--
-- Name: sessions sessions_user_id_fk; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.sessions
    ADD CONSTRAINT sessions_user_id_fk FOREIGN KEY (user_id) REFERENCES public.users(id) ON DELETE CASCADE;

--
-- Name: sites sites_domain_id_fk; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.sites
    ADD CONSTRAINT sites_domain_id_fk FOREIGN KEY (tenant_id, domain_id) REFERENCES public.domains(tenant_id, id) ON DELETE RESTRICT;

--
-- Name: sites sites_tenant_id_fk; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.sites
    ADD CONSTRAINT sites_tenant_id_fk FOREIGN KEY (tenant_id) REFERENCES public.tenants(id) ON DELETE RESTRICT;

--
-- Name: sla_policies sla_policies_category_id_fk; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.sla_policies
    ADD CONSTRAINT sla_policies_category_id_fk FOREIGN KEY (tenant_id, category_id) REFERENCES public.service_categories(tenant_id, id) ON DELETE RESTRICT;

--
-- Name: sla_policies sla_policies_domain_id_fk; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.sla_policies
    ADD CONSTRAINT sla_policies_domain_id_fk FOREIGN KEY (tenant_id, domain_id) REFERENCES public.domains(tenant_id, id) ON DELETE RESTRICT;

--
-- Name: sla_policies sla_policies_management_unit_id_fk; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.sla_policies
    ADD CONSTRAINT sla_policies_management_unit_id_fk FOREIGN KEY (tenant_id, management_unit_id) REFERENCES public.management_units(tenant_id, id) ON DELETE RESTRICT;

--
-- Name: sla_policies sla_policies_tenant_id_fk; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.sla_policies
    ADD CONSTRAINT sla_policies_tenant_id_fk FOREIGN KEY (tenant_id) REFERENCES public.tenants(id) ON DELETE RESTRICT;

--
-- Name: staff_profiles staff_profiles_management_unit_id_fk; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.staff_profiles
    ADD CONSTRAINT staff_profiles_management_unit_id_fk FOREIGN KEY (tenant_id, management_unit_id) REFERENCES public.management_units(tenant_id, id) ON DELETE RESTRICT;

--
-- Name: staff_profiles staff_profiles_tenant_id_fk; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.staff_profiles
    ADD CONSTRAINT staff_profiles_tenant_id_fk FOREIGN KEY (tenant_id) REFERENCES public.tenants(id) ON DELETE RESTRICT;

--
-- Name: staff_profiles staff_profiles_user_id_fk; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.staff_profiles
    ADD CONSTRAINT staff_profiles_user_id_fk FOREIGN KEY (user_id) REFERENCES public.users(id) ON DELETE RESTRICT;

--
-- Name: staff_shifts staff_shifts_staff_id_fk; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.staff_shifts
    ADD CONSTRAINT staff_shifts_staff_id_fk FOREIGN KEY (tenant_id, staff_id) REFERENCES public.staff_profiles(tenant_id, id) ON DELETE RESTRICT;

--
-- Name: staff_shifts staff_shifts_tenant_id_fk; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.staff_shifts
    ADD CONSTRAINT staff_shifts_tenant_id_fk FOREIGN KEY (tenant_id) REFERENCES public.tenants(id) ON DELETE RESTRICT;

--
-- Name: staff_specialties staff_specialties_category_id_fk; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.staff_specialties
    ADD CONSTRAINT staff_specialties_category_id_fk FOREIGN KEY (tenant_id, category_id) REFERENCES public.service_categories(tenant_id, id) ON DELETE RESTRICT;

--
-- Name: staff_specialties staff_specialties_staff_id_fk; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.staff_specialties
    ADD CONSTRAINT staff_specialties_staff_id_fk FOREIGN KEY (tenant_id, staff_id) REFERENCES public.staff_profiles(tenant_id, id) ON DELETE RESTRICT;

--
-- Name: staff_specialties staff_specialties_tenant_id_fk; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.staff_specialties
    ADD CONSTRAINT staff_specialties_tenant_id_fk FOREIGN KEY (tenant_id) REFERENCES public.tenants(id) ON DELETE RESTRICT;

--
-- Name: storage_locations storage_locations_tenant_id_fk; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.storage_locations
    ADD CONSTRAINT storage_locations_tenant_id_fk FOREIGN KEY (tenant_id) REFERENCES public.tenants(id) ON DELETE RESTRICT;

--
-- Name: team_members team_members_agent_id_fk; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.team_members
    ADD CONSTRAINT team_members_agent_id_fk FOREIGN KEY (tenant_id, agent_id) REFERENCES public.agents(tenant_id, id) ON DELETE RESTRICT;

--
-- Name: team_members team_members_binding_id_fk; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.team_members
    ADD CONSTRAINT team_members_binding_id_fk FOREIGN KEY (tenant_id, binding_id) REFERENCES public.runtime_session_bindings(tenant_id, id) ON DELETE RESTRICT;

--
-- Name: team_members team_members_team_id_fk; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.team_members
    ADD CONSTRAINT team_members_team_id_fk FOREIGN KEY (tenant_id, team_id) REFERENCES public.agent_teams(tenant_id, id) ON DELETE RESTRICT;

--
-- Name: team_members team_members_tenant_id_fk; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.team_members
    ADD CONSTRAINT team_members_tenant_id_fk FOREIGN KEY (tenant_id) REFERENCES public.tenants(id) ON DELETE RESTRICT;

--
-- Name: team_members team_members_version_id_fk; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.team_members
    ADD CONSTRAINT team_members_version_id_fk FOREIGN KEY (tenant_id, version_id) REFERENCES public.agent_versions(tenant_id, id) ON DELETE RESTRICT;

--
-- Name: tenant_memberships tenant_memberships_tenant_id_fk; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.tenant_memberships
    ADD CONSTRAINT tenant_memberships_tenant_id_fk FOREIGN KEY (tenant_id) REFERENCES public.tenants(id) ON DELETE RESTRICT;

--
-- Name: tenant_memberships tenant_memberships_user_id_fk; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.tenant_memberships
    ADD CONSTRAINT tenant_memberships_user_id_fk FOREIGN KEY (user_id) REFERENCES public.users(id) ON DELETE RESTRICT;

--
-- Name: ticket_assessments ticket_assessments_assessor_user_id_fk; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.ticket_assessments
    ADD CONSTRAINT ticket_assessments_assessor_user_id_fk FOREIGN KEY (assessor_user_id) REFERENCES public.users(id) ON DELETE RESTRICT;

--
-- Name: ticket_assessments ticket_assessments_basis_decision_id_fk; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.ticket_assessments
    ADD CONSTRAINT ticket_assessments_basis_decision_id_fk FOREIGN KEY (tenant_id, basis_decision_id) REFERENCES public.ticket_triage_decisions(tenant_id, id) ON DELETE RESTRICT;

--
-- Name: ticket_assessments ticket_assessments_source_run_id_fk; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.ticket_assessments
    ADD CONSTRAINT ticket_assessments_source_run_id_fk FOREIGN KEY (tenant_id, source_run_id) REFERENCES public.agent_runs(tenant_id, id) ON DELETE RESTRICT;

--
-- Name: ticket_assessments ticket_assessments_supersedes_assessment_id_fk; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.ticket_assessments
    ADD CONSTRAINT ticket_assessments_supersedes_assessment_id_fk FOREIGN KEY (tenant_id, supersedes_assessment_id) REFERENCES public.ticket_assessments(tenant_id, id) ON DELETE RESTRICT;

--
-- Name: ticket_assessments ticket_assessments_tenant_id_fk; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.ticket_assessments
    ADD CONSTRAINT ticket_assessments_tenant_id_fk FOREIGN KEY (tenant_id) REFERENCES public.tenants(id) ON DELETE RESTRICT;

--
-- Name: ticket_assessments ticket_assessments_ticket_id_fk; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.ticket_assessments
    ADD CONSTRAINT ticket_assessments_ticket_id_fk FOREIGN KEY (tenant_id, ticket_id) REFERENCES public.tickets(tenant_id, id) ON DELETE RESTRICT;

--
-- Name: ticket_escalations ticket_escalations_acknowledged_by_fk; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.ticket_escalations
    ADD CONSTRAINT ticket_escalations_acknowledged_by_fk FOREIGN KEY (acknowledged_by) REFERENCES public.users(id) ON DELETE RESTRICT;

--
-- Name: ticket_escalations ticket_escalations_assessment_id_fk; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.ticket_escalations
    ADD CONSTRAINT ticket_escalations_assessment_id_fk FOREIGN KEY (tenant_id, assessment_id) REFERENCES public.ticket_assessments(tenant_id, id) ON DELETE RESTRICT;

--
-- Name: ticket_escalations ticket_escalations_decision_id_fk; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.ticket_escalations
    ADD CONSTRAINT ticket_escalations_decision_id_fk FOREIGN KEY (tenant_id, decision_id) REFERENCES public.ticket_triage_decisions(tenant_id, id) ON DELETE RESTRICT;

--
-- Name: ticket_escalations ticket_escalations_required_scope_id_fk; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.ticket_escalations
    ADD CONSTRAINT ticket_escalations_required_scope_id_fk FOREIGN KEY (tenant_id, required_scope_id) REFERENCES public.access_scopes(tenant_id, id) ON DELETE RESTRICT;

--
-- Name: ticket_escalations ticket_escalations_resolved_by_fk; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.ticket_escalations
    ADD CONSTRAINT ticket_escalations_resolved_by_fk FOREIGN KEY (resolved_by) REFERENCES public.users(id) ON DELETE RESTRICT;

--
-- Name: ticket_escalations ticket_escalations_review_id_fk; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.ticket_escalations
    ADD CONSTRAINT ticket_escalations_review_id_fk FOREIGN KEY (tenant_id, review_id) REFERENCES public.ticket_triage_reviews(tenant_id, id) ON DELETE RESTRICT;

--
-- Name: ticket_escalations ticket_escalations_sla_cycle_id_fk; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.ticket_escalations
    ADD CONSTRAINT ticket_escalations_sla_cycle_id_fk FOREIGN KEY (tenant_id, sla_cycle_id) REFERENCES public.ticket_sla_cycles(tenant_id, id) ON DELETE RESTRICT;

--
-- Name: ticket_escalations ticket_escalations_tenant_id_fk; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.ticket_escalations
    ADD CONSTRAINT ticket_escalations_tenant_id_fk FOREIGN KEY (tenant_id) REFERENCES public.tenants(id) ON DELETE RESTRICT;

--
-- Name: ticket_escalations ticket_escalations_ticket_id_fk; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.ticket_escalations
    ADD CONSTRAINT ticket_escalations_ticket_id_fk FOREIGN KEY (tenant_id, ticket_id) REFERENCES public.tickets(tenant_id, id) ON DELETE RESTRICT;

--
-- Name: ticket_escalations ticket_escalations_work_order_id_fk; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.ticket_escalations
    ADD CONSTRAINT ticket_escalations_work_order_id_fk FOREIGN KEY (tenant_id, work_order_id) REFERENCES public.work_orders(tenant_id, id) ON DELETE RESTRICT;

--
-- Name: ticket_events ticket_events_actor_agent_id_fk; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.ticket_events
    ADD CONSTRAINT ticket_events_actor_agent_id_fk FOREIGN KEY (tenant_id, actor_agent_id) REFERENCES public.agents(tenant_id, id) ON DELETE RESTRICT;

--
-- Name: ticket_events ticket_events_actor_user_id_fk; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.ticket_events
    ADD CONSTRAINT ticket_events_actor_user_id_fk FOREIGN KEY (actor_user_id) REFERENCES public.users(id) ON DELETE RESTRICT;

--
-- Name: ticket_events ticket_events_causation_event_id_fk; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.ticket_events
    ADD CONSTRAINT ticket_events_causation_event_id_fk FOREIGN KEY (tenant_id, causation_event_id) REFERENCES public.ticket_events(tenant_id, id) ON DELETE RESTRICT;

--
-- Name: ticket_events ticket_events_tenant_id_fk; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.ticket_events
    ADD CONSTRAINT ticket_events_tenant_id_fk FOREIGN KEY (tenant_id) REFERENCES public.tenants(id) ON DELETE RESTRICT;

--
-- Name: ticket_events ticket_events_ticket_id_fk; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.ticket_events
    ADD CONSTRAINT ticket_events_ticket_id_fk FOREIGN KEY (tenant_id, ticket_id) REFERENCES public.tickets(tenant_id, id) ON DELETE RESTRICT;

--
-- Name: ticket_files ticket_files_event_id_fk; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.ticket_files
    ADD CONSTRAINT ticket_files_event_id_fk FOREIGN KEY (tenant_id, event_id) REFERENCES public.ticket_events(tenant_id, id) ON DELETE RESTRICT;

--
-- Name: ticket_files ticket_files_evidence_id_fk; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.ticket_files
    ADD CONSTRAINT ticket_files_evidence_id_fk FOREIGN KEY (tenant_id, evidence_id) REFERENCES public.evidence_items(tenant_id, id) ON DELETE RESTRICT;

--
-- Name: ticket_files ticket_files_file_id_fk; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.ticket_files
    ADD CONSTRAINT ticket_files_file_id_fk FOREIGN KEY (tenant_id, file_id) REFERENCES public.files(tenant_id, id) ON DELETE RESTRICT;

--
-- Name: ticket_files ticket_files_tenant_id_fk; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.ticket_files
    ADD CONSTRAINT ticket_files_tenant_id_fk FOREIGN KEY (tenant_id) REFERENCES public.tenants(id) ON DELETE RESTRICT;

--
-- Name: ticket_files ticket_files_ticket_id_fk; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.ticket_files
    ADD CONSTRAINT ticket_files_ticket_id_fk FOREIGN KEY (tenant_id, ticket_id) REFERENCES public.tickets(tenant_id, id) ON DELETE RESTRICT;

--
-- Name: ticket_files ticket_files_uploaded_by_fk; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.ticket_files
    ADD CONSTRAINT ticket_files_uploaded_by_fk FOREIGN KEY (uploaded_by) REFERENCES public.users(id) ON DELETE RESTRICT;

--
-- Name: ticket_reviews ticket_reviews_assignment_id_fk; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.ticket_reviews
    ADD CONSTRAINT ticket_reviews_assignment_id_fk FOREIGN KEY (tenant_id, assignment_id) REFERENCES public.work_assignments(tenant_id, id) ON DELETE RESTRICT;

--
-- Name: ticket_reviews ticket_reviews_reviewer_user_id_fk; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.ticket_reviews
    ADD CONSTRAINT ticket_reviews_reviewer_user_id_fk FOREIGN KEY (reviewer_user_id) REFERENCES public.users(id) ON DELETE RESTRICT;

--
-- Name: ticket_reviews ticket_reviews_staff_id_fk; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.ticket_reviews
    ADD CONSTRAINT ticket_reviews_staff_id_fk FOREIGN KEY (tenant_id, staff_id) REFERENCES public.staff_profiles(tenant_id, id) ON DELETE RESTRICT;

--
-- Name: ticket_reviews ticket_reviews_tenant_id_fk; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.ticket_reviews
    ADD CONSTRAINT ticket_reviews_tenant_id_fk FOREIGN KEY (tenant_id) REFERENCES public.tenants(id) ON DELETE RESTRICT;

--
-- Name: ticket_reviews ticket_reviews_ticket_id_fk; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.ticket_reviews
    ADD CONSTRAINT ticket_reviews_ticket_id_fk FOREIGN KEY (tenant_id, ticket_id) REFERENCES public.tickets(tenant_id, id) ON DELETE RESTRICT;

--
-- Name: ticket_routing_history ticket_routing_history_ack_event_id_fk; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.ticket_routing_history
    ADD CONSTRAINT ticket_routing_history_ack_event_id_fk FOREIGN KEY (tenant_id, ack_event_id) REFERENCES public.ticket_events(tenant_id, id) ON DELETE RESTRICT;

--
-- Name: ticket_routing_history ticket_routing_history_from_management_id_fk; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.ticket_routing_history
    ADD CONSTRAINT ticket_routing_history_from_management_id_fk FOREIGN KEY (tenant_id, from_management_id) REFERENCES public.management_units(tenant_id, id) ON DELETE RESTRICT;

--
-- Name: ticket_routing_history ticket_routing_history_team_id_fk; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.ticket_routing_history
    ADD CONSTRAINT ticket_routing_history_team_id_fk FOREIGN KEY (tenant_id, team_id) REFERENCES public.agent_teams(tenant_id, id) ON DELETE RESTRICT;

--
-- Name: ticket_routing_history ticket_routing_history_tenant_id_fk; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.ticket_routing_history
    ADD CONSTRAINT ticket_routing_history_tenant_id_fk FOREIGN KEY (tenant_id) REFERENCES public.tenants(id) ON DELETE RESTRICT;

--
-- Name: ticket_routing_history ticket_routing_history_ticket_id_fk; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.ticket_routing_history
    ADD CONSTRAINT ticket_routing_history_ticket_id_fk FOREIGN KEY (tenant_id, ticket_id) REFERENCES public.tickets(tenant_id, id) ON DELETE RESTRICT;

--
-- Name: ticket_routing_history ticket_routing_history_to_management_id_fk; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.ticket_routing_history
    ADD CONSTRAINT ticket_routing_history_to_management_id_fk FOREIGN KEY (tenant_id, to_management_id) REFERENCES public.management_units(tenant_id, id) ON DELETE RESTRICT;

--
-- Name: ticket_sla_adjustments ticket_sla_adjustments_authorized_by_fk; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.ticket_sla_adjustments
    ADD CONSTRAINT ticket_sla_adjustments_authorized_by_fk FOREIGN KEY (authorized_by) REFERENCES public.users(id) ON DELETE RESTRICT;

--
-- Name: ticket_sla_adjustments ticket_sla_adjustments_cycle_id_fk; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.ticket_sla_adjustments
    ADD CONSTRAINT ticket_sla_adjustments_cycle_id_fk FOREIGN KEY (tenant_id, cycle_id) REFERENCES public.ticket_sla_cycles(tenant_id, id) ON DELETE RESTRICT;

--
-- Name: ticket_sla_adjustments ticket_sla_adjustments_decision_id_fk; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.ticket_sla_adjustments
    ADD CONSTRAINT ticket_sla_adjustments_decision_id_fk FOREIGN KEY (tenant_id, decision_id) REFERENCES public.ticket_triage_decisions(tenant_id, id) ON DELETE RESTRICT;

--
-- Name: ticket_sla_adjustments ticket_sla_adjustments_target_policy_id_fk; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.ticket_sla_adjustments
    ADD CONSTRAINT ticket_sla_adjustments_target_policy_id_fk FOREIGN KEY (tenant_id, target_policy_id) REFERENCES public.sla_policies(tenant_id, id) ON DELETE RESTRICT;

--
-- Name: ticket_sla_adjustments ticket_sla_adjustments_tenant_id_fk; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.ticket_sla_adjustments
    ADD CONSTRAINT ticket_sla_adjustments_tenant_id_fk FOREIGN KEY (tenant_id) REFERENCES public.tenants(id) ON DELETE RESTRICT;

--
-- Name: ticket_sla_cycles ticket_sla_cycles_initial_decision_id_fk; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.ticket_sla_cycles
    ADD CONSTRAINT ticket_sla_cycles_initial_decision_id_fk FOREIGN KEY (tenant_id, initial_decision_id) REFERENCES public.ticket_triage_decisions(tenant_id, id) ON DELETE RESTRICT;

--
-- Name: ticket_sla_cycles ticket_sla_cycles_initial_policy_id_fk; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.ticket_sla_cycles
    ADD CONSTRAINT ticket_sla_cycles_initial_policy_id_fk FOREIGN KEY (tenant_id, initial_policy_id) REFERENCES public.sla_policies(tenant_id, id) ON DELETE RESTRICT;

--
-- Name: ticket_sla_cycles ticket_sla_cycles_tenant_id_fk; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.ticket_sla_cycles
    ADD CONSTRAINT ticket_sla_cycles_tenant_id_fk FOREIGN KEY (tenant_id) REFERENCES public.tenants(id) ON DELETE RESTRICT;

--
-- Name: ticket_sla_cycles ticket_sla_cycles_ticket_id_fk; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.ticket_sla_cycles
    ADD CONSTRAINT ticket_sla_cycles_ticket_id_fk FOREIGN KEY (tenant_id, ticket_id) REFERENCES public.tickets(tenant_id, id) ON DELETE RESTRICT;

--
-- Name: ticket_triage_decisions ticket_triage_decisions_approved_by_fk; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.ticket_triage_decisions
    ADD CONSTRAINT ticket_triage_decisions_approved_by_fk FOREIGN KEY (approved_by) REFERENCES public.users(id) ON DELETE RESTRICT;

--
-- Name: ticket_triage_decisions ticket_triage_decisions_assessment_id_fk; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.ticket_triage_decisions
    ADD CONSTRAINT ticket_triage_decisions_assessment_id_fk FOREIGN KEY (tenant_id, assessment_id) REFERENCES public.ticket_assessments(tenant_id, id) ON DELETE RESTRICT;

--
-- Name: ticket_triage_decisions ticket_triage_decisions_matched_rule_id_fk; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.ticket_triage_decisions
    ADD CONSTRAINT ticket_triage_decisions_matched_rule_id_fk FOREIGN KEY (tenant_id, matched_rule_id) REFERENCES public.triage_rules(tenant_id, id) ON DELETE RESTRICT;

--
-- Name: ticket_triage_decisions ticket_triage_decisions_policy_binding_id_fk; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.ticket_triage_decisions
    ADD CONSTRAINT ticket_triage_decisions_policy_binding_id_fk FOREIGN KEY (tenant_id, policy_binding_id) REFERENCES public.triage_policy_bindings(tenant_id, id) ON DELETE RESTRICT;

--
-- Name: ticket_triage_decisions ticket_triage_decisions_policy_version_id_fk; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.ticket_triage_decisions
    ADD CONSTRAINT ticket_triage_decisions_policy_version_id_fk FOREIGN KEY (tenant_id, policy_version_id) REFERENCES public.triage_policy_versions(tenant_id, id) ON DELETE RESTRICT;

--
-- Name: ticket_triage_decisions ticket_triage_decisions_previous_applied_id_fk; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.ticket_triage_decisions
    ADD CONSTRAINT ticket_triage_decisions_previous_applied_id_fk FOREIGN KEY (tenant_id, previous_applied_id) REFERENCES public.ticket_triage_decisions(tenant_id, id) ON DELETE RESTRICT;

--
-- Name: ticket_triage_decisions ticket_triage_decisions_review_id_fk; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.ticket_triage_decisions
    ADD CONSTRAINT ticket_triage_decisions_review_id_fk FOREIGN KEY (tenant_id, review_id) REFERENCES public.ticket_triage_reviews(tenant_id, id) ON DELETE RESTRICT;

--
-- Name: ticket_triage_decisions ticket_triage_decisions_tenant_id_fk; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.ticket_triage_decisions
    ADD CONSTRAINT ticket_triage_decisions_tenant_id_fk FOREIGN KEY (tenant_id) REFERENCES public.tenants(id) ON DELETE RESTRICT;

--
-- Name: ticket_triage_decisions ticket_triage_decisions_ticket_id_fk; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.ticket_triage_decisions
    ADD CONSTRAINT ticket_triage_decisions_ticket_id_fk FOREIGN KEY (tenant_id, ticket_id) REFERENCES public.tickets(tenant_id, id) ON DELETE RESTRICT;

--
-- Name: ticket_triage_reviews ticket_triage_reviews_assessment_id_fk; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.ticket_triage_reviews
    ADD CONSTRAINT ticket_triage_reviews_assessment_id_fk FOREIGN KEY (tenant_id, assessment_id) REFERENCES public.ticket_assessments(tenant_id, id) ON DELETE RESTRICT;

--
-- Name: ticket_triage_reviews ticket_triage_reviews_claimed_by_fk; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.ticket_triage_reviews
    ADD CONSTRAINT ticket_triage_reviews_claimed_by_fk FOREIGN KEY (claimed_by) REFERENCES public.users(id) ON DELETE RESTRICT;

--
-- Name: ticket_triage_reviews ticket_triage_reviews_decided_by_fk; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.ticket_triage_reviews
    ADD CONSTRAINT ticket_triage_reviews_decided_by_fk FOREIGN KEY (decided_by) REFERENCES public.users(id) ON DELETE RESTRICT;

--
-- Name: ticket_triage_reviews ticket_triage_reviews_pending_decision_id_fk; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.ticket_triage_reviews
    ADD CONSTRAINT ticket_triage_reviews_pending_decision_id_fk FOREIGN KEY (tenant_id, pending_decision_id) REFERENCES public.ticket_triage_decisions(tenant_id, id) ON DELETE RESTRICT;

--
-- Name: ticket_triage_reviews ticket_triage_reviews_required_scope_id_fk; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.ticket_triage_reviews
    ADD CONSTRAINT ticket_triage_reviews_required_scope_id_fk FOREIGN KEY (tenant_id, required_scope_id) REFERENCES public.access_scopes(tenant_id, id) ON DELETE RESTRICT;

--
-- Name: ticket_triage_reviews ticket_triage_reviews_result_decision_id_fk; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.ticket_triage_reviews
    ADD CONSTRAINT ticket_triage_reviews_result_decision_id_fk FOREIGN KEY (tenant_id, result_decision_id) REFERENCES public.ticket_triage_decisions(tenant_id, id) ON DELETE RESTRICT;

--
-- Name: ticket_triage_reviews ticket_triage_reviews_tenant_id_fk; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.ticket_triage_reviews
    ADD CONSTRAINT ticket_triage_reviews_tenant_id_fk FOREIGN KEY (tenant_id) REFERENCES public.tenants(id) ON DELETE RESTRICT;

--
-- Name: ticket_triage_reviews ticket_triage_reviews_ticket_id_fk; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.ticket_triage_reviews
    ADD CONSTRAINT ticket_triage_reviews_ticket_id_fk FOREIGN KEY (tenant_id, ticket_id) REFERENCES public.tickets(tenant_id, id) ON DELETE RESTRICT;

--
-- Name: tickets tickets_active_sla_cycle_id_fk; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.tickets
    ADD CONSTRAINT tickets_active_sla_cycle_id_fk FOREIGN KEY (tenant_id, active_sla_cycle_id) REFERENCES public.ticket_sla_cycles(tenant_id, id) ON DELETE RESTRICT;

--
-- Name: tickets tickets_assigned_team_id_fk; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.tickets
    ADD CONSTRAINT tickets_assigned_team_id_fk FOREIGN KEY (tenant_id, assigned_team_id) REFERENCES public.agent_teams(tenant_id, id) ON DELETE RESTRICT;

--
-- Name: tickets tickets_building_id_fk; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.tickets
    ADD CONSTRAINT tickets_building_id_fk FOREIGN KEY (tenant_id, building_id) REFERENCES public.buildings(tenant_id, id) ON DELETE RESTRICT;

--
-- Name: tickets tickets_category_id_fk; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.tickets
    ADD CONSTRAINT tickets_category_id_fk FOREIGN KEY (tenant_id, category_id) REFERENCES public.service_categories(tenant_id, id) ON DELETE RESTRICT;

--
-- Name: tickets tickets_channel_id_fk; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.tickets
    ADD CONSTRAINT tickets_channel_id_fk FOREIGN KEY (tenant_id, channel_id) REFERENCES public.channels(tenant_id, id) ON DELETE RESTRICT;

--
-- Name: tickets tickets_coverage_id_fk; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.tickets
    ADD CONSTRAINT tickets_coverage_id_fk FOREIGN KEY (tenant_id, coverage_id) REFERENCES public.management_coverage(tenant_id, id) ON DELETE RESTRICT;

--
-- Name: tickets tickets_current_triage_decision_id_fk; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.tickets
    ADD CONSTRAINT tickets_current_triage_decision_id_fk FOREIGN KEY (tenant_id, current_triage_decision_id) REFERENCES public.ticket_triage_decisions(tenant_id, id) ON DELETE RESTRICT;

--
-- Name: tickets tickets_domain_id_fk; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.tickets
    ADD CONSTRAINT tickets_domain_id_fk FOREIGN KEY (tenant_id, domain_id) REFERENCES public.domains(tenant_id, id) ON DELETE RESTRICT;

--
-- Name: tickets tickets_incident_type_id_fk; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.tickets
    ADD CONSTRAINT tickets_incident_type_id_fk FOREIGN KEY (tenant_id, incident_type_id) REFERENCES public.incident_types(tenant_id, id) ON DELETE RESTRICT;

--
-- Name: tickets tickets_management_unit_id_fk; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.tickets
    ADD CONSTRAINT tickets_management_unit_id_fk FOREIGN KEY (tenant_id, management_unit_id) REFERENCES public.management_units(tenant_id, id) ON DELETE RESTRICT;

--
-- Name: tickets tickets_requester_user_id_fk; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.tickets
    ADD CONSTRAINT tickets_requester_user_id_fk FOREIGN KEY (requester_user_id) REFERENCES public.users(id) ON DELETE RESTRICT;

--
-- Name: tickets tickets_site_id_fk; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.tickets
    ADD CONSTRAINT tickets_site_id_fk FOREIGN KEY (tenant_id, site_id) REFERENCES public.sites(tenant_id, id) ON DELETE RESTRICT;

--
-- Name: tickets tickets_sla_policy_id_fk; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.tickets
    ADD CONSTRAINT tickets_sla_policy_id_fk FOREIGN KEY (tenant_id, sla_policy_id) REFERENCES public.sla_policies(tenant_id, id) ON DELETE RESTRICT;

--
-- Name: tickets tickets_tenant_id_fk; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.tickets
    ADD CONSTRAINT tickets_tenant_id_fk FOREIGN KEY (tenant_id) REFERENCES public.tenants(id) ON DELETE RESTRICT;

--
-- Name: tickets tickets_unit_id_fk; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.tickets
    ADD CONSTRAINT tickets_unit_id_fk FOREIGN KEY (tenant_id, unit_id) REFERENCES public.units(tenant_id, id) ON DELETE RESTRICT;

--
-- Name: tickets tickets_zone_id_fk; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.tickets
    ADD CONSTRAINT tickets_zone_id_fk FOREIGN KEY (tenant_id, zone_id) REFERENCES public.zones(tenant_id, id) ON DELETE RESTRICT;

--
-- Name: triage_policy_bindings triage_policy_bindings_category_id_fk; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.triage_policy_bindings
    ADD CONSTRAINT triage_policy_bindings_category_id_fk FOREIGN KEY (tenant_id, category_id) REFERENCES public.service_categories(tenant_id, id) ON DELETE RESTRICT;

--
-- Name: triage_policy_bindings triage_policy_bindings_configured_by_fk; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.triage_policy_bindings
    ADD CONSTRAINT triage_policy_bindings_configured_by_fk FOREIGN KEY (configured_by) REFERENCES public.users(id) ON DELETE RESTRICT;

--
-- Name: triage_policy_bindings triage_policy_bindings_domain_id_fk; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.triage_policy_bindings
    ADD CONSTRAINT triage_policy_bindings_domain_id_fk FOREIGN KEY (tenant_id, domain_id) REFERENCES public.domains(tenant_id, id) ON DELETE RESTRICT;

--
-- Name: triage_policy_bindings triage_policy_bindings_policy_version_id_fk; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.triage_policy_bindings
    ADD CONSTRAINT triage_policy_bindings_policy_version_id_fk FOREIGN KEY (tenant_id, policy_version_id) REFERENCES public.triage_policy_versions(tenant_id, id) ON DELETE RESTRICT;

--
-- Name: triage_policy_bindings triage_policy_bindings_scope_id_fk; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.triage_policy_bindings
    ADD CONSTRAINT triage_policy_bindings_scope_id_fk FOREIGN KEY (tenant_id, scope_id) REFERENCES public.access_scopes(tenant_id, id) ON DELETE RESTRICT;

--
-- Name: triage_policy_bindings triage_policy_bindings_tenant_id_fk; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.triage_policy_bindings
    ADD CONSTRAINT triage_policy_bindings_tenant_id_fk FOREIGN KEY (tenant_id) REFERENCES public.tenants(id) ON DELETE RESTRICT;

--
-- Name: triage_policy_versions triage_policy_versions_created_by_fk; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.triage_policy_versions
    ADD CONSTRAINT triage_policy_versions_created_by_fk FOREIGN KEY (created_by) REFERENCES public.users(id) ON DELETE RESTRICT;

--
-- Name: triage_policy_versions triage_policy_versions_domain_id_fk; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.triage_policy_versions
    ADD CONSTRAINT triage_policy_versions_domain_id_fk FOREIGN KEY (tenant_id, domain_id) REFERENCES public.domains(tenant_id, id) ON DELETE RESTRICT;

--
-- Name: triage_policy_versions triage_policy_versions_published_by_fk; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.triage_policy_versions
    ADD CONSTRAINT triage_policy_versions_published_by_fk FOREIGN KEY (published_by) REFERENCES public.users(id) ON DELETE RESTRICT;

--
-- Name: triage_policy_versions triage_policy_versions_tenant_id_fk; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.triage_policy_versions
    ADD CONSTRAINT triage_policy_versions_tenant_id_fk FOREIGN KEY (tenant_id) REFERENCES public.tenants(id) ON DELETE RESTRICT;

--
-- Name: triage_rules triage_rules_policy_version_id_fk; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.triage_rules
    ADD CONSTRAINT triage_rules_policy_version_id_fk FOREIGN KEY (tenant_id, policy_version_id) REFERENCES public.triage_policy_versions(tenant_id, id) ON DELETE RESTRICT;

--
-- Name: triage_rules triage_rules_tenant_id_fk; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.triage_rules
    ADD CONSTRAINT triage_rules_tenant_id_fk FOREIGN KEY (tenant_id) REFERENCES public.tenants(id) ON DELETE RESTRICT;

--
-- Name: unit_residents unit_residents_tenant_id_fk; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.unit_residents
    ADD CONSTRAINT unit_residents_tenant_id_fk FOREIGN KEY (tenant_id) REFERENCES public.tenants(id) ON DELETE RESTRICT;

--
-- Name: unit_residents unit_residents_unit_id_fk; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.unit_residents
    ADD CONSTRAINT unit_residents_unit_id_fk FOREIGN KEY (tenant_id, unit_id) REFERENCES public.units(tenant_id, id) ON DELETE RESTRICT;

--
-- Name: unit_residents unit_residents_user_id_fk; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.unit_residents
    ADD CONSTRAINT unit_residents_user_id_fk FOREIGN KEY (user_id) REFERENCES public.users(id) ON DELETE RESTRICT;

--
-- Name: unit_residents unit_residents_verified_by_fk; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.unit_residents
    ADD CONSTRAINT unit_residents_verified_by_fk FOREIGN KEY (verified_by) REFERENCES public.users(id) ON DELETE RESTRICT;

--
-- Name: units units_building_id_fk; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.units
    ADD CONSTRAINT units_building_id_fk FOREIGN KEY (tenant_id, building_id) REFERENCES public.buildings(tenant_id, id) ON DELETE RESTRICT;

--
-- Name: units units_site_id_fk; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.units
    ADD CONSTRAINT units_site_id_fk FOREIGN KEY (tenant_id, site_id) REFERENCES public.sites(tenant_id, id) ON DELETE RESTRICT;

--
-- Name: units units_tenant_id_fk; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.units
    ADD CONSTRAINT units_tenant_id_fk FOREIGN KEY (tenant_id) REFERENCES public.tenants(id) ON DELETE RESTRICT;

--
-- Name: units units_zone_id_fk; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.units
    ADD CONSTRAINT units_zone_id_fk FOREIGN KEY (tenant_id, zone_id) REFERENCES public.zones(tenant_id, id) ON DELETE RESTRICT;

--
-- Name: vh_assets vh_assets_tenant_id_building_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.vh_assets
    ADD CONSTRAINT vh_assets_tenant_id_building_id_fkey FOREIGN KEY (tenant_id, building_id) REFERENCES public.buildings(tenant_id, id);

--
-- Name: vh_assets vh_assets_tenant_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.vh_assets
    ADD CONSTRAINT vh_assets_tenant_id_fkey FOREIGN KEY (tenant_id) REFERENCES public.tenants(id);

--
-- Name: vh_budget_approvals vh_budget_approvals_decided_by_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.vh_budget_approvals
    ADD CONSTRAINT vh_budget_approvals_decided_by_fkey FOREIGN KEY (decided_by) REFERENCES public.users(id);

--
-- Name: vh_budget_approvals vh_budget_approvals_requested_by_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.vh_budget_approvals
    ADD CONSTRAINT vh_budget_approvals_requested_by_fkey FOREIGN KEY (requested_by) REFERENCES public.users(id);

--
-- Name: vh_budget_approvals vh_budget_approvals_reviewer_user_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.vh_budget_approvals
    ADD CONSTRAINT vh_budget_approvals_reviewer_user_id_fkey FOREIGN KEY (reviewer_user_id) REFERENCES public.users(id);

--
-- Name: vh_budget_approvals vh_budget_approvals_tenant_id_work_order_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.vh_budget_approvals
    ADD CONSTRAINT vh_budget_approvals_tenant_id_work_order_id_fkey FOREIGN KEY (tenant_id, work_order_id) REFERENCES public.work_orders(tenant_id, id);

--
-- Name: vh_cleaning_plans vh_cleaning_plans_tenant_id_work_order_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.vh_cleaning_plans
    ADD CONSTRAINT vh_cleaning_plans_tenant_id_work_order_id_fkey FOREIGN KEY (tenant_id, work_order_id) REFERENCES public.work_orders(tenant_id, id);

--
-- Name: vh_cleaning_plans vh_cleaning_plans_updated_by_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.vh_cleaning_plans
    ADD CONSTRAINT vh_cleaning_plans_updated_by_fkey FOREIGN KEY (updated_by) REFERENCES public.users(id);

--
-- Name: vh_command_receipt vh_command_receipt_tenant_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.vh_command_receipt
    ADD CONSTRAINT vh_command_receipt_tenant_id_fkey FOREIGN KEY (tenant_id) REFERENCES public.tenants(id);

--
-- Name: vh_contractor_updates vh_contractor_updates_tenant_id_work_order_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.vh_contractor_updates
    ADD CONSTRAINT vh_contractor_updates_tenant_id_work_order_id_fkey FOREIGN KEY (tenant_id, work_order_id) REFERENCES public.work_orders(tenant_id, id);

--
-- Name: vh_contractor_updates vh_contractor_updates_updated_by_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.vh_contractor_updates
    ADD CONSTRAINT vh_contractor_updates_updated_by_fkey FOREIGN KEY (updated_by) REFERENCES public.users(id);

--
-- Name: vh_conversation_uploads vh_conversation_uploads_requested_by_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.vh_conversation_uploads
    ADD CONSTRAINT vh_conversation_uploads_requested_by_fkey FOREIGN KEY (requested_by) REFERENCES public.users(id);

--
-- Name: vh_conversation_uploads vh_conversation_uploads_tenant_id_channel_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.vh_conversation_uploads
    ADD CONSTRAINT vh_conversation_uploads_tenant_id_channel_id_fkey FOREIGN KEY (tenant_id, channel_id) REFERENCES public.channels(tenant_id, id);

--
-- Name: vh_conversation_uploads vh_conversation_uploads_tenant_id_file_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.vh_conversation_uploads
    ADD CONSTRAINT vh_conversation_uploads_tenant_id_file_id_fkey FOREIGN KEY (tenant_id, file_id) REFERENCES public.files(tenant_id, id);

--
-- Name: vh_conversation_uploads vh_conversation_uploads_tenant_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.vh_conversation_uploads
    ADD CONSTRAINT vh_conversation_uploads_tenant_id_fkey FOREIGN KEY (tenant_id) REFERENCES public.tenants(id);

--
-- Name: vh_conversation_uploads vh_conversation_uploads_tenant_id_location_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.vh_conversation_uploads
    ADD CONSTRAINT vh_conversation_uploads_tenant_id_location_id_fkey FOREIGN KEY (tenant_id, location_id) REFERENCES public.storage_locations(tenant_id, id);

--
-- Name: vh_maintenance_records vh_maintenance_records_confirmed_by_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.vh_maintenance_records
    ADD CONSTRAINT vh_maintenance_records_confirmed_by_fkey FOREIGN KEY (confirmed_by) REFERENCES public.users(id);

--
-- Name: vh_maintenance_records vh_maintenance_records_tenant_id_asset_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.vh_maintenance_records
    ADD CONSTRAINT vh_maintenance_records_tenant_id_asset_id_fkey FOREIGN KEY (tenant_id, asset_id) REFERENCES public.vh_assets(tenant_id, id);

--
-- Name: vh_maintenance_records vh_maintenance_records_tenant_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.vh_maintenance_records
    ADD CONSTRAINT vh_maintenance_records_tenant_id_fkey FOREIGN KEY (tenant_id) REFERENCES public.tenants(id);

--
-- Name: vh_maintenance_records vh_maintenance_records_tenant_id_work_order_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.vh_maintenance_records
    ADD CONSTRAINT vh_maintenance_records_tenant_id_work_order_id_fkey FOREIGN KEY (tenant_id, work_order_id) REFERENCES public.work_orders(tenant_id, id);

--
-- Name: vh_operational_requests vh_operational_requests_decided_by_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.vh_operational_requests
    ADD CONSTRAINT vh_operational_requests_decided_by_fkey FOREIGN KEY (decided_by) REFERENCES public.users(id);

--
-- Name: vh_operational_requests vh_operational_requests_requested_by_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.vh_operational_requests
    ADD CONSTRAINT vh_operational_requests_requested_by_fkey FOREIGN KEY (requested_by) REFERENCES public.users(id);

--
-- Name: vh_operational_requests vh_operational_requests_tenant_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.vh_operational_requests
    ADD CONSTRAINT vh_operational_requests_tenant_id_fkey FOREIGN KEY (tenant_id) REFERENCES public.tenants(id);

--
-- Name: vh_operational_requests vh_operational_requests_tenant_id_work_order_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.vh_operational_requests
    ADD CONSTRAINT vh_operational_requests_tenant_id_work_order_id_fkey FOREIGN KEY (tenant_id, work_order_id) REFERENCES public.work_orders(tenant_id, id);

--
-- Name: vh_qc_redo_orders vh_qc_redo_orders_created_by_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.vh_qc_redo_orders
    ADD CONSTRAINT vh_qc_redo_orders_created_by_fkey FOREIGN KEY (created_by) REFERENCES public.users(id);

--
-- Name: vh_qc_redo_orders vh_qc_redo_orders_tenant_id_qc_result_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.vh_qc_redo_orders
    ADD CONSTRAINT vh_qc_redo_orders_tenant_id_qc_result_id_fkey FOREIGN KEY (tenant_id, qc_result_id) REFERENCES public.vh_qc_results(tenant_id, id);

--
-- Name: vh_qc_redo_orders vh_qc_redo_orders_tenant_id_redo_work_order_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.vh_qc_redo_orders
    ADD CONSTRAINT vh_qc_redo_orders_tenant_id_redo_work_order_id_fkey FOREIGN KEY (tenant_id, redo_work_order_id) REFERENCES public.work_orders(tenant_id, id);

--
-- Name: vh_qc_redo_orders vh_qc_redo_orders_tenant_id_source_work_order_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.vh_qc_redo_orders
    ADD CONSTRAINT vh_qc_redo_orders_tenant_id_source_work_order_id_fkey FOREIGN KEY (tenant_id, source_work_order_id) REFERENCES public.work_orders(tenant_id, id);

--
-- Name: vh_qc_results vh_qc_results_checked_by_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.vh_qc_results
    ADD CONSTRAINT vh_qc_results_checked_by_fkey FOREIGN KEY (checked_by) REFERENCES public.users(id);

--
-- Name: vh_qc_results vh_qc_results_tenant_id_work_order_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.vh_qc_results
    ADD CONSTRAINT vh_qc_results_tenant_id_work_order_id_fkey FOREIGN KEY (tenant_id, work_order_id) REFERENCES public.work_orders(tenant_id, id);

--
-- Name: vh_reception_supervisor_messages vh_reception_supervisor_messages_created_by_agent_fk; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.vh_reception_supervisor_messages
    ADD CONSTRAINT vh_reception_supervisor_messages_created_by_agent_fk FOREIGN KEY (tenant_id, created_by_agent_id) REFERENCES public.agents(tenant_id, id) ON DELETE RESTRICT;

--
-- Name: vh_reception_supervisor_messages vh_reception_supervisor_messages_created_by_fk; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.vh_reception_supervisor_messages
    ADD CONSTRAINT vh_reception_supervisor_messages_created_by_fk FOREIGN KEY (created_by) REFERENCES public.users(id) ON DELETE RESTRICT;

--
-- Name: vh_reception_supervisor_messages vh_reception_supervisor_messages_team_id_fk; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.vh_reception_supervisor_messages
    ADD CONSTRAINT vh_reception_supervisor_messages_team_id_fk FOREIGN KEY (tenant_id, team_id) REFERENCES public.agent_teams(tenant_id, id) ON DELETE RESTRICT;

--
-- Name: vh_reception_supervisor_messages vh_reception_supervisor_messages_tenant_id_fk; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.vh_reception_supervisor_messages
    ADD CONSTRAINT vh_reception_supervisor_messages_tenant_id_fk FOREIGN KEY (tenant_id) REFERENCES public.tenants(id) ON DELETE RESTRICT;

--
-- Name: vh_reception_supervisor_messages vh_reception_supervisor_messages_ticket_id_fk; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.vh_reception_supervisor_messages
    ADD CONSTRAINT vh_reception_supervisor_messages_ticket_id_fk FOREIGN KEY (tenant_id, ticket_id) REFERENCES public.tickets(tenant_id, id) ON DELETE RESTRICT;

--
-- Name: vh_reception_supervisor_pending vh_reception_supervisor_pending_plan_id_fk; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.vh_reception_supervisor_pending
    ADD CONSTRAINT vh_reception_supervisor_pending_plan_id_fk FOREIGN KEY (tenant_id, plan_id) REFERENCES public.vh_ticket_plans(tenant_id, id) ON DELETE RESTRICT;

--
-- Name: vh_reception_supervisor_pending vh_reception_supervisor_pending_team_id_fk; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.vh_reception_supervisor_pending
    ADD CONSTRAINT vh_reception_supervisor_pending_team_id_fk FOREIGN KEY (tenant_id, team_id) REFERENCES public.agent_teams(tenant_id, id) ON DELETE RESTRICT;

--
-- Name: vh_reception_supervisor_pending vh_reception_supervisor_pending_tenant_id_fk; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.vh_reception_supervisor_pending
    ADD CONSTRAINT vh_reception_supervisor_pending_tenant_id_fk FOREIGN KEY (tenant_id) REFERENCES public.tenants(id) ON DELETE RESTRICT;

--
-- Name: vh_reception_supervisor_pending vh_reception_supervisor_pending_ticket_id_fk; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.vh_reception_supervisor_pending
    ADD CONSTRAINT vh_reception_supervisor_pending_ticket_id_fk FOREIGN KEY (tenant_id, ticket_id) REFERENCES public.tickets(tenant_id, id) ON DELETE RESTRICT;

--
-- Name: vh_report_exports vh_report_exports_created_by_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.vh_report_exports
    ADD CONSTRAINT vh_report_exports_created_by_fkey FOREIGN KEY (created_by) REFERENCES public.users(id);

--
-- Name: vh_report_exports vh_report_exports_tenant_id_building_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.vh_report_exports
    ADD CONSTRAINT vh_report_exports_tenant_id_building_id_fkey FOREIGN KEY (tenant_id, building_id) REFERENCES public.buildings(tenant_id, id);

--
-- Name: vh_report_exports vh_report_exports_tenant_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.vh_report_exports
    ADD CONSTRAINT vh_report_exports_tenant_id_fkey FOREIGN KEY (tenant_id) REFERENCES public.tenants(id);

--
-- Name: vh_resident_case_tickets vh_resident_case_tickets_linked_by_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.vh_resident_case_tickets
    ADD CONSTRAINT vh_resident_case_tickets_linked_by_fkey FOREIGN KEY (linked_by) REFERENCES public.users(id);

--
-- Name: vh_resident_case_tickets vh_resident_case_tickets_tenant_id_case_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.vh_resident_case_tickets
    ADD CONSTRAINT vh_resident_case_tickets_tenant_id_case_id_fkey FOREIGN KEY (tenant_id, case_id) REFERENCES public.vh_resident_cases(tenant_id, id);

--
-- Name: vh_resident_case_tickets vh_resident_case_tickets_tenant_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.vh_resident_case_tickets
    ADD CONSTRAINT vh_resident_case_tickets_tenant_id_fkey FOREIGN KEY (tenant_id) REFERENCES public.tenants(id);

--
-- Name: vh_resident_case_tickets vh_resident_case_tickets_tenant_id_ticket_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.vh_resident_case_tickets
    ADD CONSTRAINT vh_resident_case_tickets_tenant_id_ticket_id_fkey FOREIGN KEY (tenant_id, ticket_id) REFERENCES public.tickets(tenant_id, id);

--
-- Name: vh_resident_cases vh_resident_cases_requester_user_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.vh_resident_cases
    ADD CONSTRAINT vh_resident_cases_requester_user_id_fkey FOREIGN KEY (requester_user_id) REFERENCES public.users(id);

--
-- Name: vh_resident_cases vh_resident_cases_resolution_fk; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.vh_resident_cases
    ADD CONSTRAINT vh_resident_cases_resolution_fk FOREIGN KEY (tenant_id, id, current_resolution_id) REFERENCES public.vh_resident_resolutions(tenant_id, case_id, id);

--
-- Name: vh_resident_cases vh_resident_cases_tenant_id_building_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.vh_resident_cases
    ADD CONSTRAINT vh_resident_cases_tenant_id_building_id_fkey FOREIGN KEY (tenant_id, building_id) REFERENCES public.buildings(tenant_id, id);

--
-- Name: vh_resident_cases vh_resident_cases_tenant_id_channel_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.vh_resident_cases
    ADD CONSTRAINT vh_resident_cases_tenant_id_channel_id_fkey FOREIGN KEY (tenant_id, channel_id) REFERENCES public.channels(tenant_id, id);

--
-- Name: vh_resident_cases vh_resident_cases_tenant_id_domain_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.vh_resident_cases
    ADD CONSTRAINT vh_resident_cases_tenant_id_domain_id_fkey FOREIGN KEY (tenant_id, domain_id) REFERENCES public.domains(tenant_id, id);

--
-- Name: vh_resident_cases vh_resident_cases_tenant_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.vh_resident_cases
    ADD CONSTRAINT vh_resident_cases_tenant_id_fkey FOREIGN KEY (tenant_id) REFERENCES public.tenants(id);

--
-- Name: vh_resident_cases vh_resident_cases_tenant_id_site_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.vh_resident_cases
    ADD CONSTRAINT vh_resident_cases_tenant_id_site_id_fkey FOREIGN KEY (tenant_id, site_id) REFERENCES public.sites(tenant_id, id);

--
-- Name: vh_resident_cases vh_resident_cases_tenant_id_unit_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.vh_resident_cases
    ADD CONSTRAINT vh_resident_cases_tenant_id_unit_id_fkey FOREIGN KEY (tenant_id, unit_id) REFERENCES public.units(tenant_id, id);

--
-- Name: vh_resident_command_receipts vh_resident_command_receipts_actor_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.vh_resident_command_receipts
    ADD CONSTRAINT vh_resident_command_receipts_actor_id_fkey FOREIGN KEY (actor_id) REFERENCES public.users(id);

--
-- Name: vh_resident_command_receipts vh_resident_command_receipts_tenant_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.vh_resident_command_receipts
    ADD CONSTRAINT vh_resident_command_receipts_tenant_id_fkey FOREIGN KEY (tenant_id) REFERENCES public.tenants(id);

--
-- Name: vh_resident_outbox vh_resident_outbox_tenant_id_case_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.vh_resident_outbox
    ADD CONSTRAINT vh_resident_outbox_tenant_id_case_id_fkey FOREIGN KEY (tenant_id, case_id) REFERENCES public.vh_resident_cases(tenant_id, id);

--
-- Name: vh_resident_outbox vh_resident_outbox_tenant_id_event_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.vh_resident_outbox
    ADD CONSTRAINT vh_resident_outbox_tenant_id_event_id_fkey FOREIGN KEY (tenant_id, event_id) REFERENCES public.vh_resident_public_events(tenant_id, id);

--
-- Name: vh_resident_outbox vh_resident_outbox_tenant_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.vh_resident_outbox
    ADD CONSTRAINT vh_resident_outbox_tenant_id_fkey FOREIGN KEY (tenant_id) REFERENCES public.tenants(id);

--
-- Name: vh_resident_photos vh_resident_photos_tenant_id_case_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.vh_resident_photos
    ADD CONSTRAINT vh_resident_photos_tenant_id_case_id_fkey FOREIGN KEY (tenant_id, case_id) REFERENCES public.vh_resident_cases(tenant_id, id);

--
-- Name: vh_resident_photos vh_resident_photos_tenant_id_file_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.vh_resident_photos
    ADD CONSTRAINT vh_resident_photos_tenant_id_file_id_fkey FOREIGN KEY (tenant_id, file_id) REFERENCES public.files(tenant_id, id);

--
-- Name: vh_resident_photos vh_resident_photos_tenant_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.vh_resident_photos
    ADD CONSTRAINT vh_resident_photos_tenant_id_fkey FOREIGN KEY (tenant_id) REFERENCES public.tenants(id);

--
-- Name: vh_resident_photos vh_resident_photos_tenant_id_unit_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.vh_resident_photos
    ADD CONSTRAINT vh_resident_photos_tenant_id_unit_id_fkey FOREIGN KEY (tenant_id, unit_id) REFERENCES public.units(tenant_id, id);

--
-- Name: vh_resident_photos vh_resident_photos_uploaded_by_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.vh_resident_photos
    ADD CONSTRAINT vh_resident_photos_uploaded_by_fkey FOREIGN KEY (uploaded_by) REFERENCES public.users(id);

--
-- Name: vh_resident_public_events vh_resident_public_events_tenant_id_case_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.vh_resident_public_events
    ADD CONSTRAINT vh_resident_public_events_tenant_id_case_id_fkey FOREIGN KEY (tenant_id, case_id) REFERENCES public.vh_resident_cases(tenant_id, id);

--
-- Name: vh_resident_public_events vh_resident_public_events_tenant_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.vh_resident_public_events
    ADD CONSTRAINT vh_resident_public_events_tenant_id_fkey FOREIGN KEY (tenant_id) REFERENCES public.tenants(id);

--
-- Name: vh_resident_resolution_photos vh_resident_resolution_photos_tenant_id_file_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.vh_resident_resolution_photos
    ADD CONSTRAINT vh_resident_resolution_photos_tenant_id_file_id_fkey FOREIGN KEY (tenant_id, file_id) REFERENCES public.files(tenant_id, id);

--
-- Name: vh_resident_resolution_photos vh_resident_resolution_photos_tenant_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.vh_resident_resolution_photos
    ADD CONSTRAINT vh_resident_resolution_photos_tenant_id_fkey FOREIGN KEY (tenant_id) REFERENCES public.tenants(id);

--
-- Name: vh_resident_resolution_photos vh_resident_resolution_photos_tenant_id_resolution_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.vh_resident_resolution_photos
    ADD CONSTRAINT vh_resident_resolution_photos_tenant_id_resolution_id_fkey FOREIGN KEY (tenant_id, resolution_id) REFERENCES public.vh_resident_resolutions(tenant_id, id);

--
-- Name: vh_resident_resolution_responses vh_resident_resolution_respon_tenant_id_case_id_resolution_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.vh_resident_resolution_responses
    ADD CONSTRAINT vh_resident_resolution_respon_tenant_id_case_id_resolution_fkey FOREIGN KEY (tenant_id, case_id, resolution_id) REFERENCES public.vh_resident_resolutions(tenant_id, case_id, id);

--
-- Name: vh_resident_resolution_responses vh_resident_resolution_responses_actor_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.vh_resident_resolution_responses
    ADD CONSTRAINT vh_resident_resolution_responses_actor_id_fkey FOREIGN KEY (actor_id) REFERENCES public.users(id);

--
-- Name: vh_resident_resolution_responses vh_resident_resolution_responses_tenant_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.vh_resident_resolution_responses
    ADD CONSTRAINT vh_resident_resolution_responses_tenant_id_fkey FOREIGN KEY (tenant_id) REFERENCES public.tenants(id);

--
-- Name: vh_resident_resolutions vh_resident_resolutions_published_by_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.vh_resident_resolutions
    ADD CONSTRAINT vh_resident_resolutions_published_by_fkey FOREIGN KEY (published_by) REFERENCES public.users(id);

--
-- Name: vh_resident_resolutions vh_resident_resolutions_tenant_id_case_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.vh_resident_resolutions
    ADD CONSTRAINT vh_resident_resolutions_tenant_id_case_id_fkey FOREIGN KEY (tenant_id, case_id) REFERENCES public.vh_resident_cases(tenant_id, id);

--
-- Name: vh_resident_resolutions vh_resident_resolutions_tenant_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.vh_resident_resolutions
    ADD CONSTRAINT vh_resident_resolutions_tenant_id_fkey FOREIGN KEY (tenant_id) REFERENCES public.tenants(id);

--
-- Name: vh_resident_submissions vh_resident_submissions_submitted_by_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.vh_resident_submissions
    ADD CONSTRAINT vh_resident_submissions_submitted_by_fkey FOREIGN KEY (submitted_by) REFERENCES public.users(id);

--
-- Name: vh_resident_submissions vh_resident_submissions_tenant_id_case_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.vh_resident_submissions
    ADD CONSTRAINT vh_resident_submissions_tenant_id_case_id_fkey FOREIGN KEY (tenant_id, case_id) REFERENCES public.vh_resident_cases(tenant_id, id);

--
-- Name: vh_resident_submissions vh_resident_submissions_tenant_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.vh_resident_submissions
    ADD CONSTRAINT vh_resident_submissions_tenant_id_fkey FOREIGN KEY (tenant_id) REFERENCES public.tenants(id);

--
-- Name: vh_security_checkpoints vh_security_checkpoints_guard_user_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.vh_security_checkpoints
    ADD CONSTRAINT vh_security_checkpoints_guard_user_id_fkey FOREIGN KEY (guard_user_id) REFERENCES public.users(id);

--
-- Name: vh_security_checkpoints vh_security_checkpoints_tenant_id_site_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.vh_security_checkpoints
    ADD CONSTRAINT vh_security_checkpoints_tenant_id_site_id_fkey FOREIGN KEY (tenant_id, site_id) REFERENCES public.sites(tenant_id, id);

--
-- Name: vh_security_handovers vh_security_handovers_from_user_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.vh_security_handovers
    ADD CONSTRAINT vh_security_handovers_from_user_id_fkey FOREIGN KEY (from_user_id) REFERENCES public.users(id);

--
-- Name: vh_security_handovers vh_security_handovers_tenant_id_site_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.vh_security_handovers
    ADD CONSTRAINT vh_security_handovers_tenant_id_site_id_fkey FOREIGN KEY (tenant_id, site_id) REFERENCES public.sites(tenant_id, id);

--
-- Name: vh_security_handovers vh_security_handovers_to_user_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.vh_security_handovers
    ADD CONSTRAINT vh_security_handovers_to_user_id_fkey FOREIGN KEY (to_user_id) REFERENCES public.users(id);

--
-- Name: vh_security_incidents vh_security_incidents_reported_by_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.vh_security_incidents
    ADD CONSTRAINT vh_security_incidents_reported_by_fkey FOREIGN KEY (reported_by) REFERENCES public.users(id);

--
-- Name: vh_security_incidents vh_security_incidents_tenant_id_site_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.vh_security_incidents
    ADD CONSTRAINT vh_security_incidents_tenant_id_site_id_fkey FOREIGN KEY (tenant_id, site_id) REFERENCES public.sites(tenant_id, id);

--
-- Name: vh_security_incidents vh_security_incidents_tenant_id_ticket_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.vh_security_incidents
    ADD CONSTRAINT vh_security_incidents_tenant_id_ticket_id_fkey FOREIGN KEY (tenant_id, ticket_id) REFERENCES public.tickets(tenant_id, id);

--
-- Name: vh_sensor_readings vh_sensor_readings_recorded_by_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.vh_sensor_readings
    ADD CONSTRAINT vh_sensor_readings_recorded_by_fkey FOREIGN KEY (recorded_by) REFERENCES public.users(id);

--
-- Name: vh_sensor_readings vh_sensor_readings_tenant_id_asset_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.vh_sensor_readings
    ADD CONSTRAINT vh_sensor_readings_tenant_id_asset_id_fkey FOREIGN KEY (tenant_id, asset_id) REFERENCES public.vh_assets(tenant_id, id);

--
-- Name: vh_sensor_readings vh_sensor_readings_tenant_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.vh_sensor_readings
    ADD CONSTRAINT vh_sensor_readings_tenant_id_fkey FOREIGN KEY (tenant_id) REFERENCES public.tenants(id);

--
-- Name: vh_technical_measurements vh_technical_measurements_recorded_by_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.vh_technical_measurements
    ADD CONSTRAINT vh_technical_measurements_recorded_by_fkey FOREIGN KEY (recorded_by) REFERENCES public.users(id);

--
-- Name: vh_technical_measurements vh_technical_measurements_tenant_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.vh_technical_measurements
    ADD CONSTRAINT vh_technical_measurements_tenant_id_fkey FOREIGN KEY (tenant_id) REFERENCES public.tenants(id);

--
-- Name: vh_technical_measurements vh_technical_measurements_tenant_id_work_order_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.vh_technical_measurements
    ADD CONSTRAINT vh_technical_measurements_tenant_id_work_order_id_fkey FOREIGN KEY (tenant_id, work_order_id) REFERENCES public.work_orders(tenant_id, id);

--
-- Name: vh_ticket_plans vh_ticket_plans_management_by_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.vh_ticket_plans
    ADD CONSTRAINT vh_ticket_plans_management_by_fkey FOREIGN KEY (management_by) REFERENCES public.users(id);

--
-- Name: vh_ticket_plans vh_ticket_plans_proposed_by_agent_fk; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.vh_ticket_plans
    ADD CONSTRAINT vh_ticket_plans_proposed_by_agent_fk FOREIGN KEY (tenant_id, proposed_by_agent_id) REFERENCES public.agents(tenant_id, id) ON DELETE RESTRICT;

--
-- Name: vh_ticket_plans vh_ticket_plans_proposed_by_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.vh_ticket_plans
    ADD CONSTRAINT vh_ticket_plans_proposed_by_fkey FOREIGN KEY (proposed_by) REFERENCES public.users(id);

--
-- Name: vh_ticket_plans vh_ticket_plans_resident_by_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.vh_ticket_plans
    ADD CONSTRAINT vh_ticket_plans_resident_by_fkey FOREIGN KEY (resident_by) REFERENCES public.users(id);

--
-- Name: vh_ticket_plans vh_ticket_plans_tenant_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.vh_ticket_plans
    ADD CONSTRAINT vh_ticket_plans_tenant_id_fkey FOREIGN KEY (tenant_id) REFERENCES public.tenants(id);

--
-- Name: vh_ticket_plans vh_ticket_plans_tenant_id_ticket_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.vh_ticket_plans
    ADD CONSTRAINT vh_ticket_plans_tenant_id_ticket_id_fkey FOREIGN KEY (tenant_id, ticket_id) REFERENCES public.tickets(tenant_id, id);

--
-- Name: work_approvals work_approvals_decided_by_fk; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.work_approvals
    ADD CONSTRAINT work_approvals_decided_by_fk FOREIGN KEY (decided_by) REFERENCES public.users(id) ON DELETE RESTRICT;

--
-- Name: work_approvals work_approvals_decided_event_id_fk; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.work_approvals
    ADD CONSTRAINT work_approvals_decided_event_id_fk FOREIGN KEY (tenant_id, decided_event_id) REFERENCES public.ticket_events(tenant_id, id) ON DELETE RESTRICT;

--
-- Name: work_approvals work_approvals_requested_to_user_id_fk; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.work_approvals
    ADD CONSTRAINT work_approvals_requested_to_user_id_fk FOREIGN KEY (requested_to_user_id) REFERENCES public.users(id) ON DELETE RESTRICT;

--
-- Name: work_approvals work_approvals_required_scope_id_fk; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.work_approvals
    ADD CONSTRAINT work_approvals_required_scope_id_fk FOREIGN KEY (tenant_id, required_scope_id) REFERENCES public.access_scopes(tenant_id, id) ON DELETE RESTRICT;

--
-- Name: work_approvals work_approvals_tenant_id_fk; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.work_approvals
    ADD CONSTRAINT work_approvals_tenant_id_fk FOREIGN KEY (tenant_id) REFERENCES public.tenants(id) ON DELETE RESTRICT;

--
-- Name: work_approvals work_approvals_work_order_id_fk; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.work_approvals
    ADD CONSTRAINT work_approvals_work_order_id_fk FOREIGN KEY (tenant_id, work_order_id) REFERENCES public.work_orders(tenant_id, id) ON DELETE RESTRICT;

--
-- Name: work_assignments work_assignments_assigned_by_agent_id_fk; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.work_assignments
    ADD CONSTRAINT work_assignments_assigned_by_agent_id_fk FOREIGN KEY (tenant_id, assigned_by_agent_id) REFERENCES public.agents(tenant_id, id) ON DELETE RESTRICT;

--
-- Name: work_assignments work_assignments_assigned_by_user_id_fk; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.work_assignments
    ADD CONSTRAINT work_assignments_assigned_by_user_id_fk FOREIGN KEY (assigned_by_user_id) REFERENCES public.users(id) ON DELETE RESTRICT;

--
-- Name: work_assignments work_assignments_dispatch_attempt_id_fk; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.work_assignments
    ADD CONSTRAINT work_assignments_dispatch_attempt_id_fk FOREIGN KEY (tenant_id, dispatch_attempt_id) REFERENCES public.dispatch_attempts(tenant_id, id) ON DELETE RESTRICT;

--
-- Name: work_assignments work_assignments_staff_id_fk; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.work_assignments
    ADD CONSTRAINT work_assignments_staff_id_fk FOREIGN KEY (tenant_id, staff_id) REFERENCES public.staff_profiles(tenant_id, id) ON DELETE RESTRICT;

--
-- Name: work_assignments work_assignments_tenant_id_fk; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.work_assignments
    ADD CONSTRAINT work_assignments_tenant_id_fk FOREIGN KEY (tenant_id) REFERENCES public.tenants(id) ON DELETE RESTRICT;

--
-- Name: work_assignments work_assignments_work_order_id_fk; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.work_assignments
    ADD CONSTRAINT work_assignments_work_order_id_fk FOREIGN KEY (tenant_id, work_order_id) REFERENCES public.work_orders(tenant_id, id) ON DELETE RESTRICT;

--
-- Name: work_orders work_orders_category_id_fk; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.work_orders
    ADD CONSTRAINT work_orders_category_id_fk FOREIGN KEY (tenant_id, category_id) REFERENCES public.service_categories(tenant_id, id) ON DELETE RESTRICT;

--
-- Name: work_orders work_orders_required_specialty_id_fk; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.work_orders
    ADD CONSTRAINT work_orders_required_specialty_id_fk FOREIGN KEY (tenant_id, required_specialty_id) REFERENCES public.service_categories(tenant_id, id) ON DELETE RESTRICT;

--
-- Name: work_orders work_orders_tenant_id_fk; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.work_orders
    ADD CONSTRAINT work_orders_tenant_id_fk FOREIGN KEY (tenant_id) REFERENCES public.tenants(id) ON DELETE RESTRICT;

--
-- Name: work_orders work_orders_ticket_id_fk; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.work_orders
    ADD CONSTRAINT work_orders_ticket_id_fk FOREIGN KEY (tenant_id, ticket_id) REFERENCES public.tickets(tenant_id, id) ON DELETE RESTRICT;

--
-- Name: workspace_members workspace_members_tenant_id_fk; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.workspace_members
    ADD CONSTRAINT workspace_members_tenant_id_fk FOREIGN KEY (tenant_id) REFERENCES public.tenants(id) ON DELETE RESTRICT;

--
-- Name: workspace_members workspace_members_user_id_fk; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.workspace_members
    ADD CONSTRAINT workspace_members_user_id_fk FOREIGN KEY (user_id) REFERENCES public.users(id) ON DELETE RESTRICT;

--
-- Name: workspace_members workspace_members_workspace_id_fk; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.workspace_members
    ADD CONSTRAINT workspace_members_workspace_id_fk FOREIGN KEY (tenant_id, workspace_id) REFERENCES public.workspaces(tenant_id, id) ON DELETE RESTRICT;

--
-- Name: workspaces workspaces_management_unit_id_fk; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.workspaces
    ADD CONSTRAINT workspaces_management_unit_id_fk FOREIGN KEY (tenant_id, management_unit_id) REFERENCES public.management_units(tenant_id, id) ON DELETE RESTRICT;

--
-- Name: workspaces workspaces_tenant_id_fk; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.workspaces
    ADD CONSTRAINT workspaces_tenant_id_fk FOREIGN KEY (tenant_id) REFERENCES public.tenants(id) ON DELETE RESTRICT;

--
-- Name: zones zones_site_id_fk; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.zones
    ADD CONSTRAINT zones_site_id_fk FOREIGN KEY (tenant_id, site_id) REFERENCES public.sites(tenant_id, id) ON DELETE RESTRICT;

--
-- Name: zones zones_tenant_id_fk; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.zones
    ADD CONSTRAINT zones_tenant_id_fk FOREIGN KEY (tenant_id) REFERENCES public.tenants(id) ON DELETE RESTRICT;

--
-- Name: access_scopes; Type: ROW SECURITY; Schema: public; Owner: -
--

ALTER TABLE public.access_scopes ENABLE ROW LEVEL SECURITY;

--
-- Name: access_scopes access_scopes_tenant_policy; Type: POLICY; Schema: public; Owner: -
--

CREATE POLICY access_scopes_tenant_policy ON public.access_scopes USING ((tenant_id = (NULLIF(current_setting('app.tenant_id'::text, true), ''::text))::uuid)) WITH CHECK ((tenant_id = (NULLIF(current_setting('app.tenant_id'::text, true), ''::text))::uuid));

--
-- Name: account_reviews; Type: ROW SECURITY; Schema: public; Owner: -
--

ALTER TABLE public.account_reviews ENABLE ROW LEVEL SECURITY;

--
-- Name: account_reviews account_reviews_tenant_policy; Type: POLICY; Schema: public; Owner: -
--

CREATE POLICY account_reviews_tenant_policy ON public.account_reviews USING ((tenant_id = (NULLIF(current_setting('app.tenant_id'::text, true), ''::text))::uuid)) WITH CHECK ((tenant_id = (NULLIF(current_setting('app.tenant_id'::text, true), ''::text))::uuid));

--
-- Name: agent_releases; Type: ROW SECURITY; Schema: public; Owner: -
--

ALTER TABLE public.agent_releases ENABLE ROW LEVEL SECURITY;

--
-- Name: agent_releases agent_releases_tenant_policy; Type: POLICY; Schema: public; Owner: -
--

CREATE POLICY agent_releases_tenant_policy ON public.agent_releases USING ((tenant_id = (NULLIF(current_setting('app.tenant_id'::text, true), ''::text))::uuid)) WITH CHECK ((tenant_id = (NULLIF(current_setting('app.tenant_id'::text, true), ''::text))::uuid));

--
-- Name: agent_runs; Type: ROW SECURITY; Schema: public; Owner: -
--

ALTER TABLE public.agent_runs ENABLE ROW LEVEL SECURITY;

--
-- Name: agent_runs agent_runs_tenant_policy; Type: POLICY; Schema: public; Owner: -
--

CREATE POLICY agent_runs_tenant_policy ON public.agent_runs USING ((tenant_id = (NULLIF(current_setting('app.tenant_id'::text, true), ''::text))::uuid)) WITH CHECK ((tenant_id = (NULLIF(current_setting('app.tenant_id'::text, true), ''::text))::uuid));

--
-- Name: agent_teams; Type: ROW SECURITY; Schema: public; Owner: -
--

ALTER TABLE public.agent_teams ENABLE ROW LEVEL SECURITY;

--
-- Name: agent_teams agent_teams_tenant_policy; Type: POLICY; Schema: public; Owner: -
--

CREATE POLICY agent_teams_tenant_policy ON public.agent_teams USING ((tenant_id = (NULLIF(current_setting('app.tenant_id'::text, true), ''::text))::uuid)) WITH CHECK ((tenant_id = (NULLIF(current_setting('app.tenant_id'::text, true), ''::text))::uuid));

--
-- Name: agent_versions; Type: ROW SECURITY; Schema: public; Owner: -
--

ALTER TABLE public.agent_versions ENABLE ROW LEVEL SECURITY;

--
-- Name: agent_versions agent_versions_tenant_policy; Type: POLICY; Schema: public; Owner: -
--

CREATE POLICY agent_versions_tenant_policy ON public.agent_versions USING ((tenant_id = (NULLIF(current_setting('app.tenant_id'::text, true), ''::text))::uuid)) WITH CHECK ((tenant_id = (NULLIF(current_setting('app.tenant_id'::text, true), ''::text))::uuid));

--
-- Name: agents; Type: ROW SECURITY; Schema: public; Owner: -
--

ALTER TABLE public.agents ENABLE ROW LEVEL SECURITY;

--
-- Name: agents agents_tenant_policy; Type: POLICY; Schema: public; Owner: -
--

CREATE POLICY agents_tenant_policy ON public.agents USING ((tenant_id = (NULLIF(current_setting('app.tenant_id'::text, true), ''::text))::uuid)) WITH CHECK ((tenant_id = (NULLIF(current_setting('app.tenant_id'::text, true), ''::text))::uuid));

--
-- Name: audit_events; Type: ROW SECURITY; Schema: public; Owner: -
--

ALTER TABLE public.audit_events ENABLE ROW LEVEL SECURITY;

--
-- Name: audit_events audit_events_tenant_policy; Type: POLICY; Schema: public; Owner: -
--

CREATE POLICY audit_events_tenant_policy ON public.audit_events USING (((tenant_id = (NULLIF(current_setting('app.tenant_id'::text, true), ''::text))::uuid) OR (tenant_id IS NULL))) WITH CHECK (((tenant_id = (NULLIF(current_setting('app.tenant_id'::text, true), ''::text))::uuid) OR (tenant_id IS NULL)));

--
-- Name: buildings; Type: ROW SECURITY; Schema: public; Owner: -
--

ALTER TABLE public.buildings ENABLE ROW LEVEL SECURITY;

--
-- Name: buildings buildings_tenant_policy; Type: POLICY; Schema: public; Owner: -
--

CREATE POLICY buildings_tenant_policy ON public.buildings USING ((tenant_id = (NULLIF(current_setting('app.tenant_id'::text, true), ''::text))::uuid)) WITH CHECK ((tenant_id = (NULLIF(current_setting('app.tenant_id'::text, true), ''::text))::uuid));

--
-- Name: channel_agents; Type: ROW SECURITY; Schema: public; Owner: -
--

ALTER TABLE public.channel_agents ENABLE ROW LEVEL SECURITY;

--
-- Name: channel_agents channel_agents_tenant_policy; Type: POLICY; Schema: public; Owner: -
--

CREATE POLICY channel_agents_tenant_policy ON public.channel_agents USING ((tenant_id = (NULLIF(current_setting('app.tenant_id'::text, true), ''::text))::uuid)) WITH CHECK ((tenant_id = (NULLIF(current_setting('app.tenant_id'::text, true), ''::text))::uuid));

--
-- Name: channel_memberships; Type: ROW SECURITY; Schema: public; Owner: -
--

ALTER TABLE public.channel_memberships ENABLE ROW LEVEL SECURITY;

--
-- Name: channel_memberships channel_memberships_tenant_policy; Type: POLICY; Schema: public; Owner: -
--

CREATE POLICY channel_memberships_tenant_policy ON public.channel_memberships USING ((tenant_id = (NULLIF(current_setting('app.tenant_id'::text, true), ''::text))::uuid)) WITH CHECK ((tenant_id = (NULLIF(current_setting('app.tenant_id'::text, true), ''::text))::uuid));

--
-- Name: channels; Type: ROW SECURITY; Schema: public; Owner: -
--

ALTER TABLE public.channels ENABLE ROW LEVEL SECURITY;

--
-- Name: channels channels_tenant_policy; Type: POLICY; Schema: public; Owner: -
--

CREATE POLICY channels_tenant_policy ON public.channels USING ((tenant_id = (NULLIF(current_setting('app.tenant_id'::text, true), ''::text))::uuid)) WITH CHECK ((tenant_id = (NULLIF(current_setting('app.tenant_id'::text, true), ''::text))::uuid));

--
-- Name: dispatch_attempts; Type: ROW SECURITY; Schema: public; Owner: -
--

ALTER TABLE public.dispatch_attempts ENABLE ROW LEVEL SECURITY;

--
-- Name: dispatch_attempts dispatch_attempts_tenant_policy; Type: POLICY; Schema: public; Owner: -
--

CREATE POLICY dispatch_attempts_tenant_policy ON public.dispatch_attempts USING ((tenant_id = (NULLIF(current_setting('app.tenant_id'::text, true), ''::text))::uuid)) WITH CHECK ((tenant_id = (NULLIF(current_setting('app.tenant_id'::text, true), ''::text))::uuid));

--
-- Name: dispatch_queue; Type: ROW SECURITY; Schema: public; Owner: -
--

ALTER TABLE public.dispatch_queue ENABLE ROW LEVEL SECURITY;

--
-- Name: dispatch_queue dispatch_queue_tenant_policy; Type: POLICY; Schema: public; Owner: -
--

CREATE POLICY dispatch_queue_tenant_policy ON public.dispatch_queue USING ((tenant_id = (NULLIF(current_setting('app.tenant_id'::text, true), ''::text))::uuid)) WITH CHECK ((tenant_id = (NULLIF(current_setting('app.tenant_id'::text, true), ''::text))::uuid));

--
-- Name: domains; Type: ROW SECURITY; Schema: public; Owner: -
--

ALTER TABLE public.domains ENABLE ROW LEVEL SECURITY;

--
-- Name: domains domains_tenant_policy; Type: POLICY; Schema: public; Owner: -
--

CREATE POLICY domains_tenant_policy ON public.domains USING ((tenant_id = (NULLIF(current_setting('app.tenant_id'::text, true), ''::text))::uuid)) WITH CHECK ((tenant_id = (NULLIF(current_setting('app.tenant_id'::text, true), ''::text))::uuid));

--
-- Name: event_inbox; Type: ROW SECURITY; Schema: public; Owner: -
--

ALTER TABLE public.event_inbox ENABLE ROW LEVEL SECURITY;

--
-- Name: event_inbox event_inbox_tenant_policy; Type: POLICY; Schema: public; Owner: -
--

CREATE POLICY event_inbox_tenant_policy ON public.event_inbox USING ((tenant_id = (NULLIF(current_setting('app.tenant_id'::text, true), ''::text))::uuid)) WITH CHECK ((tenant_id = (NULLIF(current_setting('app.tenant_id'::text, true), ''::text))::uuid));

--
-- Name: event_outbox; Type: ROW SECURITY; Schema: public; Owner: -
--

ALTER TABLE public.event_outbox ENABLE ROW LEVEL SECURITY;

--
-- Name: event_outbox event_outbox_tenant_policy; Type: POLICY; Schema: public; Owner: -
--

CREATE POLICY event_outbox_tenant_policy ON public.event_outbox USING ((tenant_id = (NULLIF(current_setting('app.tenant_id'::text, true), ''::text))::uuid)) WITH CHECK ((tenant_id = (NULLIF(current_setting('app.tenant_id'::text, true), ''::text))::uuid));

--
-- Name: evidence_items; Type: ROW SECURITY; Schema: public; Owner: -
--

ALTER TABLE public.evidence_items ENABLE ROW LEVEL SECURITY;

--
-- Name: evidence_items evidence_items_tenant_policy; Type: POLICY; Schema: public; Owner: -
--

CREATE POLICY evidence_items_tenant_policy ON public.evidence_items USING ((tenant_id = (NULLIF(current_setting('app.tenant_id'::text, true), ''::text))::uuid)) WITH CHECK ((tenant_id = (NULLIF(current_setting('app.tenant_id'::text, true), ''::text))::uuid));

--
-- Name: execution_principals; Type: ROW SECURITY; Schema: public; Owner: -
--

ALTER TABLE public.execution_principals ENABLE ROW LEVEL SECURITY;

--
-- Name: execution_principals execution_principals_tenant_policy; Type: POLICY; Schema: public; Owner: -
--

CREATE POLICY execution_principals_tenant_policy ON public.execution_principals USING ((tenant_id = (NULLIF(current_setting('app.tenant_id'::text, true), ''::text))::uuid)) WITH CHECK ((tenant_id = (NULLIF(current_setting('app.tenant_id'::text, true), ''::text))::uuid));

--
-- Name: file_objects; Type: ROW SECURITY; Schema: public; Owner: -
--

ALTER TABLE public.file_objects ENABLE ROW LEVEL SECURITY;

--
-- Name: file_objects file_objects_tenant_policy; Type: POLICY; Schema: public; Owner: -
--

CREATE POLICY file_objects_tenant_policy ON public.file_objects USING ((tenant_id = (NULLIF(current_setting('app.tenant_id'::text, true), ''::text))::uuid)) WITH CHECK ((tenant_id = (NULLIF(current_setting('app.tenant_id'::text, true), ''::text))::uuid));

--
-- Name: file_uploads; Type: ROW SECURITY; Schema: public; Owner: -
--

ALTER TABLE public.file_uploads ENABLE ROW LEVEL SECURITY;

--
-- Name: file_uploads file_uploads_tenant_policy; Type: POLICY; Schema: public; Owner: -
--

CREATE POLICY file_uploads_tenant_policy ON public.file_uploads USING ((tenant_id = (NULLIF(current_setting('app.tenant_id'::text, true), ''::text))::uuid)) WITH CHECK ((tenant_id = (NULLIF(current_setting('app.tenant_id'::text, true), ''::text))::uuid));

--
-- Name: files; Type: ROW SECURITY; Schema: public; Owner: -
--

ALTER TABLE public.files ENABLE ROW LEVEL SECURITY;

--
-- Name: files files_tenant_policy; Type: POLICY; Schema: public; Owner: -
--

CREATE POLICY files_tenant_policy ON public.files USING ((tenant_id = (NULLIF(current_setting('app.tenant_id'::text, true), ''::text))::uuid)) WITH CHECK ((tenant_id = (NULLIF(current_setting('app.tenant_id'::text, true), ''::text))::uuid));

--
-- Name: incident_types; Type: ROW SECURITY; Schema: public; Owner: -
--

ALTER TABLE public.incident_types ENABLE ROW LEVEL SECURITY;

--
-- Name: incident_types incident_types_tenant_policy; Type: POLICY; Schema: public; Owner: -
--

CREATE POLICY incident_types_tenant_policy ON public.incident_types USING ((tenant_id = (NULLIF(current_setting('app.tenant_id'::text, true), ''::text))::uuid)) WITH CHECK ((tenant_id = (NULLIF(current_setting('app.tenant_id'::text, true), ''::text))::uuid));

--
-- Name: interruption_scopes; Type: ROW SECURITY; Schema: public; Owner: -
--

ALTER TABLE public.interruption_scopes ENABLE ROW LEVEL SECURITY;

--
-- Name: interruption_scopes interruption_scopes_tenant_policy; Type: POLICY; Schema: public; Owner: -
--

CREATE POLICY interruption_scopes_tenant_policy ON public.interruption_scopes USING ((tenant_id = (NULLIF(current_setting('app.tenant_id'::text, true), ''::text))::uuid)) WITH CHECK ((tenant_id = (NULLIF(current_setting('app.tenant_id'::text, true), ''::text))::uuid));

--
-- Name: invoice_lines; Type: ROW SECURITY; Schema: public; Owner: -
--

ALTER TABLE public.invoice_lines ENABLE ROW LEVEL SECURITY;

--
-- Name: invoice_lines invoice_lines_tenant_policy; Type: POLICY; Schema: public; Owner: -
--

CREATE POLICY invoice_lines_tenant_policy ON public.invoice_lines USING ((tenant_id = (NULLIF(current_setting('app.tenant_id'::text, true), ''::text))::uuid)) WITH CHECK ((tenant_id = (NULLIF(current_setting('app.tenant_id'::text, true), ''::text))::uuid));

--
-- Name: invoices; Type: ROW SECURITY; Schema: public; Owner: -
--

ALTER TABLE public.invoices ENABLE ROW LEVEL SECURITY;

--
-- Name: invoices invoices_tenant_policy; Type: POLICY; Schema: public; Owner: -
--

CREATE POLICY invoices_tenant_policy ON public.invoices USING ((tenant_id = (NULLIF(current_setting('app.tenant_id'::text, true), ''::text))::uuid)) WITH CHECK ((tenant_id = (NULLIF(current_setting('app.tenant_id'::text, true), ''::text))::uuid));

--
-- Name: management_coverage; Type: ROW SECURITY; Schema: public; Owner: -
--

ALTER TABLE public.management_coverage ENABLE ROW LEVEL SECURITY;

--
-- Name: management_coverage management_coverage_tenant_policy; Type: POLICY; Schema: public; Owner: -
--

CREATE POLICY management_coverage_tenant_policy ON public.management_coverage USING ((tenant_id = (NULLIF(current_setting('app.tenant_id'::text, true), ''::text))::uuid)) WITH CHECK ((tenant_id = (NULLIF(current_setting('app.tenant_id'::text, true), ''::text))::uuid));

--
-- Name: management_units; Type: ROW SECURITY; Schema: public; Owner: -
--

ALTER TABLE public.management_units ENABLE ROW LEVEL SECURITY;

--
-- Name: management_units management_units_tenant_policy; Type: POLICY; Schema: public; Owner: -
--

CREATE POLICY management_units_tenant_policy ON public.management_units USING ((tenant_id = (NULLIF(current_setting('app.tenant_id'::text, true), ''::text))::uuid)) WITH CHECK ((tenant_id = (NULLIF(current_setting('app.tenant_id'::text, true), ''::text))::uuid));

--
-- Name: message_files; Type: ROW SECURITY; Schema: public; Owner: -
--

ALTER TABLE public.message_files ENABLE ROW LEVEL SECURITY;

--
-- Name: message_files message_files_tenant_policy; Type: POLICY; Schema: public; Owner: -
--

CREATE POLICY message_files_tenant_policy ON public.message_files USING ((tenant_id = (NULLIF(current_setting('app.tenant_id'::text, true), ''::text))::uuid)) WITH CHECK ((tenant_id = (NULLIF(current_setting('app.tenant_id'::text, true), ''::text))::uuid));

--
-- Name: messages; Type: ROW SECURITY; Schema: public; Owner: -
--

ALTER TABLE public.messages ENABLE ROW LEVEL SECURITY;

--
-- Name: messages messages_tenant_policy; Type: POLICY; Schema: public; Owner: -
--

CREATE POLICY messages_tenant_policy ON public.messages USING ((tenant_id = (NULLIF(current_setting('app.tenant_id'::text, true), ''::text))::uuid)) WITH CHECK ((tenant_id = (NULLIF(current_setting('app.tenant_id'::text, true), ''::text))::uuid));

--
-- Name: notification_deliveries; Type: ROW SECURITY; Schema: public; Owner: -
--

ALTER TABLE public.notification_deliveries ENABLE ROW LEVEL SECURITY;

--
-- Name: notification_deliveries notification_deliveries_tenant_policy; Type: POLICY; Schema: public; Owner: -
--

CREATE POLICY notification_deliveries_tenant_policy ON public.notification_deliveries USING ((tenant_id = (NULLIF(current_setting('app.tenant_id'::text, true), ''::text))::uuid)) WITH CHECK ((tenant_id = (NULLIF(current_setting('app.tenant_id'::text, true), ''::text))::uuid));

--
-- Name: payment_allocations; Type: ROW SECURITY; Schema: public; Owner: -
--

ALTER TABLE public.payment_allocations ENABLE ROW LEVEL SECURITY;

--
-- Name: payment_allocations payment_allocations_tenant_policy; Type: POLICY; Schema: public; Owner: -
--

CREATE POLICY payment_allocations_tenant_policy ON public.payment_allocations USING ((tenant_id = (NULLIF(current_setting('app.tenant_id'::text, true), ''::text))::uuid)) WITH CHECK ((tenant_id = (NULLIF(current_setting('app.tenant_id'::text, true), ''::text))::uuid));

--
-- Name: payment_intents; Type: ROW SECURITY; Schema: public; Owner: -
--

ALTER TABLE public.payment_intents ENABLE ROW LEVEL SECURITY;

--
-- Name: payment_intents payment_intents_tenant_policy; Type: POLICY; Schema: public; Owner: -
--

CREATE POLICY payment_intents_tenant_policy ON public.payment_intents USING ((tenant_id = (NULLIF(current_setting('app.tenant_id'::text, true), ''::text))::uuid)) WITH CHECK ((tenant_id = (NULLIF(current_setting('app.tenant_id'::text, true), ''::text))::uuid));

--
-- Name: payment_webhook_receipts; Type: ROW SECURITY; Schema: public; Owner: -
--

ALTER TABLE public.payment_webhook_receipts ENABLE ROW LEVEL SECURITY;

--
-- Name: payment_webhook_receipts payment_webhook_receipts_tenant_policy; Type: POLICY; Schema: public; Owner: -
--

CREATE POLICY payment_webhook_receipts_tenant_policy ON public.payment_webhook_receipts USING ((tenant_id = (NULLIF(current_setting('app.tenant_id'::text, true), ''::text))::uuid)) WITH CHECK ((tenant_id = (NULLIF(current_setting('app.tenant_id'::text, true), ''::text))::uuid));

--
-- Name: payments; Type: ROW SECURITY; Schema: public; Owner: -
--

ALTER TABLE public.payments ENABLE ROW LEVEL SECURITY;

--
-- Name: payments payments_tenant_policy; Type: POLICY; Schema: public; Owner: -
--

CREATE POLICY payments_tenant_policy ON public.payments USING ((tenant_id = (NULLIF(current_setting('app.tenant_id'::text, true), ''::text))::uuid)) WITH CHECK ((tenant_id = (NULLIF(current_setting('app.tenant_id'::text, true), ''::text))::uuid));

--
-- Name: runtime_identities; Type: ROW SECURITY; Schema: public; Owner: -
--

ALTER TABLE public.runtime_identities ENABLE ROW LEVEL SECURITY;

--
-- Name: runtime_identities runtime_identities_tenant_policy; Type: POLICY; Schema: public; Owner: -
--

CREATE POLICY runtime_identities_tenant_policy ON public.runtime_identities USING ((tenant_id = (NULLIF(current_setting('app.tenant_id'::text, true), ''::text))::uuid)) WITH CHECK ((tenant_id = (NULLIF(current_setting('app.tenant_id'::text, true), ''::text))::uuid));

--
-- Name: runtime_session_bindings; Type: ROW SECURITY; Schema: public; Owner: -
--

ALTER TABLE public.runtime_session_bindings ENABLE ROW LEVEL SECURITY;

--
-- Name: runtime_session_bindings runtime_session_bindings_tenant_policy; Type: POLICY; Schema: public; Owner: -
--

CREATE POLICY runtime_session_bindings_tenant_policy ON public.runtime_session_bindings USING ((tenant_id = (NULLIF(current_setting('app.tenant_id'::text, true), ''::text))::uuid)) WITH CHECK ((tenant_id = (NULLIF(current_setting('app.tenant_id'::text, true), ''::text))::uuid));

--
-- Name: scoped_user_roles; Type: ROW SECURITY; Schema: public; Owner: -
--

ALTER TABLE public.scoped_user_roles ENABLE ROW LEVEL SECURITY;

--
-- Name: scoped_user_roles scoped_user_roles_tenant_policy; Type: POLICY; Schema: public; Owner: -
--

CREATE POLICY scoped_user_roles_tenant_policy ON public.scoped_user_roles USING ((tenant_id = (NULLIF(current_setting('app.tenant_id'::text, true), ''::text))::uuid)) WITH CHECK ((tenant_id = (NULLIF(current_setting('app.tenant_id'::text, true), ''::text))::uuid));

--
-- Name: security_alert_deliveries; Type: ROW SECURITY; Schema: public; Owner: -
--

ALTER TABLE public.security_alert_deliveries ENABLE ROW LEVEL SECURITY;

--
-- Name: security_alerts; Type: ROW SECURITY; Schema: public; Owner: -
--

ALTER TABLE public.security_alerts ENABLE ROW LEVEL SECURITY;

--
-- Name: security_alerts security_alerts_tenant; Type: POLICY; Schema: public; Owner: -
--

CREATE POLICY security_alerts_tenant ON public.security_alerts USING ((tenant_id = (NULLIF(current_setting('app.tenant_id'::text, true), ''::text))::uuid)) WITH CHECK ((tenant_id = (NULLIF(current_setting('app.tenant_id'::text, true), ''::text))::uuid));

--
-- Name: security_cameras; Type: ROW SECURITY; Schema: public; Owner: -
--

ALTER TABLE public.security_cameras ENABLE ROW LEVEL SECURITY;

--
-- Name: security_cameras security_cameras_tenant; Type: POLICY; Schema: public; Owner: -
--

CREATE POLICY security_cameras_tenant ON public.security_cameras USING ((tenant_id = (NULLIF(current_setting('app.tenant_id'::text, true), ''::text))::uuid)) WITH CHECK ((tenant_id = (NULLIF(current_setting('app.tenant_id'::text, true), ''::text))::uuid));

--
-- Name: security_emergency_contacts security_contacts_tenant; Type: POLICY; Schema: public; Owner: -
--

CREATE POLICY security_contacts_tenant ON public.security_emergency_contacts USING ((tenant_id = (NULLIF(current_setting('app.tenant_id'::text, true), ''::text))::uuid)) WITH CHECK ((tenant_id = (NULLIF(current_setting('app.tenant_id'::text, true), ''::text))::uuid));

--
-- Name: security_alert_deliveries security_deliveries_tenant; Type: POLICY; Schema: public; Owner: -
--

CREATE POLICY security_deliveries_tenant ON public.security_alert_deliveries USING ((tenant_id = (NULLIF(current_setting('app.tenant_id'::text, true), ''::text))::uuid)) WITH CHECK ((tenant_id = (NULLIF(current_setting('app.tenant_id'::text, true), ''::text))::uuid));

--
-- Name: security_emergency_contacts; Type: ROW SECURITY; Schema: public; Owner: -
--

ALTER TABLE public.security_emergency_contacts ENABLE ROW LEVEL SECURITY;

--
-- Name: service_categories; Type: ROW SECURITY; Schema: public; Owner: -
--

ALTER TABLE public.service_categories ENABLE ROW LEVEL SECURITY;

--
-- Name: service_categories service_categories_tenant_policy; Type: POLICY; Schema: public; Owner: -
--

CREATE POLICY service_categories_tenant_policy ON public.service_categories USING ((tenant_id = (NULLIF(current_setting('app.tenant_id'::text, true), ''::text))::uuid)) WITH CHECK ((tenant_id = (NULLIF(current_setting('app.tenant_id'::text, true), ''::text))::uuid));

--
-- Name: service_interruptions; Type: ROW SECURITY; Schema: public; Owner: -
--

ALTER TABLE public.service_interruptions ENABLE ROW LEVEL SECURITY;

--
-- Name: service_interruptions service_interruptions_tenant_policy; Type: POLICY; Schema: public; Owner: -
--

CREATE POLICY service_interruptions_tenant_policy ON public.service_interruptions USING ((tenant_id = (NULLIF(current_setting('app.tenant_id'::text, true), ''::text))::uuid)) WITH CHECK ((tenant_id = (NULLIF(current_setting('app.tenant_id'::text, true), ''::text))::uuid));

--
-- Name: sites; Type: ROW SECURITY; Schema: public; Owner: -
--

ALTER TABLE public.sites ENABLE ROW LEVEL SECURITY;

--
-- Name: sites sites_tenant_policy; Type: POLICY; Schema: public; Owner: -
--

CREATE POLICY sites_tenant_policy ON public.sites USING ((tenant_id = (NULLIF(current_setting('app.tenant_id'::text, true), ''::text))::uuid)) WITH CHECK ((tenant_id = (NULLIF(current_setting('app.tenant_id'::text, true), ''::text))::uuid));

--
-- Name: sla_policies; Type: ROW SECURITY; Schema: public; Owner: -
--

ALTER TABLE public.sla_policies ENABLE ROW LEVEL SECURITY;

--
-- Name: sla_policies sla_policies_tenant_policy; Type: POLICY; Schema: public; Owner: -
--

CREATE POLICY sla_policies_tenant_policy ON public.sla_policies USING ((tenant_id = (NULLIF(current_setting('app.tenant_id'::text, true), ''::text))::uuid)) WITH CHECK ((tenant_id = (NULLIF(current_setting('app.tenant_id'::text, true), ''::text))::uuid));

--
-- Name: staff_profiles; Type: ROW SECURITY; Schema: public; Owner: -
--

ALTER TABLE public.staff_profiles ENABLE ROW LEVEL SECURITY;

--
-- Name: staff_profiles staff_profiles_tenant_policy; Type: POLICY; Schema: public; Owner: -
--

CREATE POLICY staff_profiles_tenant_policy ON public.staff_profiles USING ((tenant_id = (NULLIF(current_setting('app.tenant_id'::text, true), ''::text))::uuid)) WITH CHECK ((tenant_id = (NULLIF(current_setting('app.tenant_id'::text, true), ''::text))::uuid));

--
-- Name: staff_shifts; Type: ROW SECURITY; Schema: public; Owner: -
--

ALTER TABLE public.staff_shifts ENABLE ROW LEVEL SECURITY;

--
-- Name: staff_shifts staff_shifts_tenant_policy; Type: POLICY; Schema: public; Owner: -
--

CREATE POLICY staff_shifts_tenant_policy ON public.staff_shifts USING ((tenant_id = (NULLIF(current_setting('app.tenant_id'::text, true), ''::text))::uuid)) WITH CHECK ((tenant_id = (NULLIF(current_setting('app.tenant_id'::text, true), ''::text))::uuid));

--
-- Name: staff_specialties; Type: ROW SECURITY; Schema: public; Owner: -
--

ALTER TABLE public.staff_specialties ENABLE ROW LEVEL SECURITY;

--
-- Name: staff_specialties staff_specialties_tenant_policy; Type: POLICY; Schema: public; Owner: -
--

CREATE POLICY staff_specialties_tenant_policy ON public.staff_specialties USING ((tenant_id = (NULLIF(current_setting('app.tenant_id'::text, true), ''::text))::uuid)) WITH CHECK ((tenant_id = (NULLIF(current_setting('app.tenant_id'::text, true), ''::text))::uuid));

--
-- Name: storage_locations; Type: ROW SECURITY; Schema: public; Owner: -
--

ALTER TABLE public.storage_locations ENABLE ROW LEVEL SECURITY;

--
-- Name: storage_locations storage_locations_tenant_policy; Type: POLICY; Schema: public; Owner: -
--

CREATE POLICY storage_locations_tenant_policy ON public.storage_locations USING ((tenant_id = (NULLIF(current_setting('app.tenant_id'::text, true), ''::text))::uuid)) WITH CHECK ((tenant_id = (NULLIF(current_setting('app.tenant_id'::text, true), ''::text))::uuid));

--
-- Name: team_members; Type: ROW SECURITY; Schema: public; Owner: -
--

ALTER TABLE public.team_members ENABLE ROW LEVEL SECURITY;

--
-- Name: team_members team_members_tenant_policy; Type: POLICY; Schema: public; Owner: -
--

CREATE POLICY team_members_tenant_policy ON public.team_members USING ((tenant_id = (NULLIF(current_setting('app.tenant_id'::text, true), ''::text))::uuid)) WITH CHECK ((tenant_id = (NULLIF(current_setting('app.tenant_id'::text, true), ''::text))::uuid));

--
-- Name: tenant_memberships; Type: ROW SECURITY; Schema: public; Owner: -
--

ALTER TABLE public.tenant_memberships ENABLE ROW LEVEL SECURITY;

--
-- Name: tenant_memberships tenant_memberships_tenant_policy; Type: POLICY; Schema: public; Owner: -
--

CREATE POLICY tenant_memberships_tenant_policy ON public.tenant_memberships USING ((tenant_id = (NULLIF(current_setting('app.tenant_id'::text, true), ''::text))::uuid)) WITH CHECK ((tenant_id = (NULLIF(current_setting('app.tenant_id'::text, true), ''::text))::uuid));

--
-- Name: vh_assets tenant_scope; Type: POLICY; Schema: public; Owner: -
--

CREATE POLICY tenant_scope ON public.vh_assets USING ((tenant_id = (NULLIF(current_setting('app.tenant_id'::text, true), ''::text))::uuid)) WITH CHECK ((tenant_id = (NULLIF(current_setting('app.tenant_id'::text, true), ''::text))::uuid));

--
-- Name: vh_conversation_uploads tenant_scope; Type: POLICY; Schema: public; Owner: -
--

CREATE POLICY tenant_scope ON public.vh_conversation_uploads USING ((tenant_id = (NULLIF(current_setting('app.tenant_id'::text, true), ''::text))::uuid)) WITH CHECK ((tenant_id = (NULLIF(current_setting('app.tenant_id'::text, true), ''::text))::uuid));

--
-- Name: vh_maintenance_records tenant_scope; Type: POLICY; Schema: public; Owner: -
--

CREATE POLICY tenant_scope ON public.vh_maintenance_records USING ((tenant_id = (NULLIF(current_setting('app.tenant_id'::text, true), ''::text))::uuid)) WITH CHECK ((tenant_id = (NULLIF(current_setting('app.tenant_id'::text, true), ''::text))::uuid));

--
-- Name: vh_operational_requests tenant_scope; Type: POLICY; Schema: public; Owner: -
--

CREATE POLICY tenant_scope ON public.vh_operational_requests USING ((tenant_id = (NULLIF(current_setting('app.tenant_id'::text, true), ''::text))::uuid)) WITH CHECK ((tenant_id = (NULLIF(current_setting('app.tenant_id'::text, true), ''::text))::uuid));

--
-- Name: vh_report_exports tenant_scope; Type: POLICY; Schema: public; Owner: -
--

CREATE POLICY tenant_scope ON public.vh_report_exports USING ((tenant_id = (NULLIF(current_setting('app.tenant_id'::text, true), ''::text))::uuid)) WITH CHECK ((tenant_id = (NULLIF(current_setting('app.tenant_id'::text, true), ''::text))::uuid));

--
-- Name: vh_resident_case_tickets tenant_scope; Type: POLICY; Schema: public; Owner: -
--

CREATE POLICY tenant_scope ON public.vh_resident_case_tickets USING ((tenant_id = (NULLIF(current_setting('app.tenant_id'::text, true), ''::text))::uuid)) WITH CHECK ((tenant_id = (NULLIF(current_setting('app.tenant_id'::text, true), ''::text))::uuid));

--
-- Name: vh_resident_cases tenant_scope; Type: POLICY; Schema: public; Owner: -
--

CREATE POLICY tenant_scope ON public.vh_resident_cases USING ((tenant_id = (NULLIF(current_setting('app.tenant_id'::text, true), ''::text))::uuid)) WITH CHECK ((tenant_id = (NULLIF(current_setting('app.tenant_id'::text, true), ''::text))::uuid));

--
-- Name: vh_resident_command_receipts tenant_scope; Type: POLICY; Schema: public; Owner: -
--

CREATE POLICY tenant_scope ON public.vh_resident_command_receipts USING ((tenant_id = (NULLIF(current_setting('app.tenant_id'::text, true), ''::text))::uuid)) WITH CHECK ((tenant_id = (NULLIF(current_setting('app.tenant_id'::text, true), ''::text))::uuid));

--
-- Name: vh_resident_outbox tenant_scope; Type: POLICY; Schema: public; Owner: -
--

CREATE POLICY tenant_scope ON public.vh_resident_outbox USING ((tenant_id = (NULLIF(current_setting('app.tenant_id'::text, true), ''::text))::uuid)) WITH CHECK ((tenant_id = (NULLIF(current_setting('app.tenant_id'::text, true), ''::text))::uuid));

--
-- Name: vh_resident_photos tenant_scope; Type: POLICY; Schema: public; Owner: -
--

CREATE POLICY tenant_scope ON public.vh_resident_photos USING ((tenant_id = (NULLIF(current_setting('app.tenant_id'::text, true), ''::text))::uuid)) WITH CHECK ((tenant_id = (NULLIF(current_setting('app.tenant_id'::text, true), ''::text))::uuid));

--
-- Name: vh_resident_public_events tenant_scope; Type: POLICY; Schema: public; Owner: -
--

CREATE POLICY tenant_scope ON public.vh_resident_public_events USING ((tenant_id = (NULLIF(current_setting('app.tenant_id'::text, true), ''::text))::uuid)) WITH CHECK ((tenant_id = (NULLIF(current_setting('app.tenant_id'::text, true), ''::text))::uuid));

--
-- Name: vh_resident_resolution_photos tenant_scope; Type: POLICY; Schema: public; Owner: -
--

CREATE POLICY tenant_scope ON public.vh_resident_resolution_photos USING ((tenant_id = (NULLIF(current_setting('app.tenant_id'::text, true), ''::text))::uuid)) WITH CHECK ((tenant_id = (NULLIF(current_setting('app.tenant_id'::text, true), ''::text))::uuid));

--
-- Name: vh_resident_resolution_responses tenant_scope; Type: POLICY; Schema: public; Owner: -
--

CREATE POLICY tenant_scope ON public.vh_resident_resolution_responses USING ((tenant_id = (NULLIF(current_setting('app.tenant_id'::text, true), ''::text))::uuid)) WITH CHECK ((tenant_id = (NULLIF(current_setting('app.tenant_id'::text, true), ''::text))::uuid));

--
-- Name: vh_resident_resolutions tenant_scope; Type: POLICY; Schema: public; Owner: -
--

CREATE POLICY tenant_scope ON public.vh_resident_resolutions USING ((tenant_id = (NULLIF(current_setting('app.tenant_id'::text, true), ''::text))::uuid)) WITH CHECK ((tenant_id = (NULLIF(current_setting('app.tenant_id'::text, true), ''::text))::uuid));

--
-- Name: vh_resident_submissions tenant_scope; Type: POLICY; Schema: public; Owner: -
--

CREATE POLICY tenant_scope ON public.vh_resident_submissions USING ((tenant_id = (NULLIF(current_setting('app.tenant_id'::text, true), ''::text))::uuid)) WITH CHECK ((tenant_id = (NULLIF(current_setting('app.tenant_id'::text, true), ''::text))::uuid));

--
-- Name: vh_sensor_readings tenant_scope; Type: POLICY; Schema: public; Owner: -
--

CREATE POLICY tenant_scope ON public.vh_sensor_readings USING ((tenant_id = (NULLIF(current_setting('app.tenant_id'::text, true), ''::text))::uuid)) WITH CHECK ((tenant_id = (NULLIF(current_setting('app.tenant_id'::text, true), ''::text))::uuid));

--
-- Name: vh_technical_measurements tenant_scope; Type: POLICY; Schema: public; Owner: -
--

CREATE POLICY tenant_scope ON public.vh_technical_measurements USING ((tenant_id = (NULLIF(current_setting('app.tenant_id'::text, true), ''::text))::uuid)) WITH CHECK ((tenant_id = (NULLIF(current_setting('app.tenant_id'::text, true), ''::text))::uuid));

--
-- Name: vh_ticket_plans tenant_scope; Type: POLICY; Schema: public; Owner: -
--

CREATE POLICY tenant_scope ON public.vh_ticket_plans USING ((tenant_id = (NULLIF(current_setting('app.tenant_id'::text, true), ''::text))::uuid)) WITH CHECK ((tenant_id = (NULLIF(current_setting('app.tenant_id'::text, true), ''::text))::uuid));

--
-- Name: ticket_assessments; Type: ROW SECURITY; Schema: public; Owner: -
--

ALTER TABLE public.ticket_assessments ENABLE ROW LEVEL SECURITY;

--
-- Name: ticket_assessments ticket_assessments_tenant_policy; Type: POLICY; Schema: public; Owner: -
--

CREATE POLICY ticket_assessments_tenant_policy ON public.ticket_assessments USING ((tenant_id = (NULLIF(current_setting('app.tenant_id'::text, true), ''::text))::uuid)) WITH CHECK ((tenant_id = (NULLIF(current_setting('app.tenant_id'::text, true), ''::text))::uuid));

--
-- Name: ticket_escalations; Type: ROW SECURITY; Schema: public; Owner: -
--

ALTER TABLE public.ticket_escalations ENABLE ROW LEVEL SECURITY;

--
-- Name: ticket_escalations ticket_escalations_tenant_policy; Type: POLICY; Schema: public; Owner: -
--

CREATE POLICY ticket_escalations_tenant_policy ON public.ticket_escalations USING ((tenant_id = (NULLIF(current_setting('app.tenant_id'::text, true), ''::text))::uuid)) WITH CHECK ((tenant_id = (NULLIF(current_setting('app.tenant_id'::text, true), ''::text))::uuid));

--
-- Name: ticket_events; Type: ROW SECURITY; Schema: public; Owner: -
--

ALTER TABLE public.ticket_events ENABLE ROW LEVEL SECURITY;

--
-- Name: ticket_events ticket_events_tenant_policy; Type: POLICY; Schema: public; Owner: -
--

CREATE POLICY ticket_events_tenant_policy ON public.ticket_events USING ((tenant_id = (NULLIF(current_setting('app.tenant_id'::text, true), ''::text))::uuid)) WITH CHECK ((tenant_id = (NULLIF(current_setting('app.tenant_id'::text, true), ''::text))::uuid));

--
-- Name: ticket_files; Type: ROW SECURITY; Schema: public; Owner: -
--

ALTER TABLE public.ticket_files ENABLE ROW LEVEL SECURITY;

--
-- Name: ticket_files ticket_files_tenant_policy; Type: POLICY; Schema: public; Owner: -
--

CREATE POLICY ticket_files_tenant_policy ON public.ticket_files USING ((tenant_id = (NULLIF(current_setting('app.tenant_id'::text, true), ''::text))::uuid)) WITH CHECK ((tenant_id = (NULLIF(current_setting('app.tenant_id'::text, true), ''::text))::uuid));

--
-- Name: ticket_reviews; Type: ROW SECURITY; Schema: public; Owner: -
--

ALTER TABLE public.ticket_reviews ENABLE ROW LEVEL SECURITY;

--
-- Name: ticket_reviews ticket_reviews_tenant_policy; Type: POLICY; Schema: public; Owner: -
--

CREATE POLICY ticket_reviews_tenant_policy ON public.ticket_reviews USING ((tenant_id = (NULLIF(current_setting('app.tenant_id'::text, true), ''::text))::uuid)) WITH CHECK ((tenant_id = (NULLIF(current_setting('app.tenant_id'::text, true), ''::text))::uuid));

--
-- Name: ticket_routing_history; Type: ROW SECURITY; Schema: public; Owner: -
--

ALTER TABLE public.ticket_routing_history ENABLE ROW LEVEL SECURITY;

--
-- Name: ticket_routing_history ticket_routing_history_tenant_policy; Type: POLICY; Schema: public; Owner: -
--

CREATE POLICY ticket_routing_history_tenant_policy ON public.ticket_routing_history USING ((tenant_id = (NULLIF(current_setting('app.tenant_id'::text, true), ''::text))::uuid)) WITH CHECK ((tenant_id = (NULLIF(current_setting('app.tenant_id'::text, true), ''::text))::uuid));

--
-- Name: ticket_sla_adjustments; Type: ROW SECURITY; Schema: public; Owner: -
--

ALTER TABLE public.ticket_sla_adjustments ENABLE ROW LEVEL SECURITY;

--
-- Name: ticket_sla_adjustments ticket_sla_adjustments_tenant_policy; Type: POLICY; Schema: public; Owner: -
--

CREATE POLICY ticket_sla_adjustments_tenant_policy ON public.ticket_sla_adjustments USING ((tenant_id = (NULLIF(current_setting('app.tenant_id'::text, true), ''::text))::uuid)) WITH CHECK ((tenant_id = (NULLIF(current_setting('app.tenant_id'::text, true), ''::text))::uuid));

--
-- Name: ticket_sla_cycles; Type: ROW SECURITY; Schema: public; Owner: -
--

ALTER TABLE public.ticket_sla_cycles ENABLE ROW LEVEL SECURITY;

--
-- Name: ticket_sla_cycles ticket_sla_cycles_tenant_policy; Type: POLICY; Schema: public; Owner: -
--

CREATE POLICY ticket_sla_cycles_tenant_policy ON public.ticket_sla_cycles USING ((tenant_id = (NULLIF(current_setting('app.tenant_id'::text, true), ''::text))::uuid)) WITH CHECK ((tenant_id = (NULLIF(current_setting('app.tenant_id'::text, true), ''::text))::uuid));

--
-- Name: ticket_triage_decisions; Type: ROW SECURITY; Schema: public; Owner: -
--

ALTER TABLE public.ticket_triage_decisions ENABLE ROW LEVEL SECURITY;

--
-- Name: ticket_triage_decisions ticket_triage_decisions_tenant_policy; Type: POLICY; Schema: public; Owner: -
--

CREATE POLICY ticket_triage_decisions_tenant_policy ON public.ticket_triage_decisions USING ((tenant_id = (NULLIF(current_setting('app.tenant_id'::text, true), ''::text))::uuid)) WITH CHECK ((tenant_id = (NULLIF(current_setting('app.tenant_id'::text, true), ''::text))::uuid));

--
-- Name: ticket_triage_reviews; Type: ROW SECURITY; Schema: public; Owner: -
--

ALTER TABLE public.ticket_triage_reviews ENABLE ROW LEVEL SECURITY;

--
-- Name: ticket_triage_reviews ticket_triage_reviews_tenant_policy; Type: POLICY; Schema: public; Owner: -
--

CREATE POLICY ticket_triage_reviews_tenant_policy ON public.ticket_triage_reviews USING ((tenant_id = (NULLIF(current_setting('app.tenant_id'::text, true), ''::text))::uuid)) WITH CHECK ((tenant_id = (NULLIF(current_setting('app.tenant_id'::text, true), ''::text))::uuid));

--
-- Name: tickets; Type: ROW SECURITY; Schema: public; Owner: -
--

ALTER TABLE public.tickets ENABLE ROW LEVEL SECURITY;

--
-- Name: tickets tickets_tenant_policy; Type: POLICY; Schema: public; Owner: -
--

CREATE POLICY tickets_tenant_policy ON public.tickets USING ((tenant_id = (NULLIF(current_setting('app.tenant_id'::text, true), ''::text))::uuid)) WITH CHECK ((tenant_id = (NULLIF(current_setting('app.tenant_id'::text, true), ''::text))::uuid));

--
-- Name: triage_policy_bindings; Type: ROW SECURITY; Schema: public; Owner: -
--

ALTER TABLE public.triage_policy_bindings ENABLE ROW LEVEL SECURITY;

--
-- Name: triage_policy_bindings triage_policy_bindings_tenant_policy; Type: POLICY; Schema: public; Owner: -
--

CREATE POLICY triage_policy_bindings_tenant_policy ON public.triage_policy_bindings USING ((tenant_id = (NULLIF(current_setting('app.tenant_id'::text, true), ''::text))::uuid)) WITH CHECK ((tenant_id = (NULLIF(current_setting('app.tenant_id'::text, true), ''::text))::uuid));

--
-- Name: triage_policy_versions; Type: ROW SECURITY; Schema: public; Owner: -
--

ALTER TABLE public.triage_policy_versions ENABLE ROW LEVEL SECURITY;

--
-- Name: triage_policy_versions triage_policy_versions_tenant_policy; Type: POLICY; Schema: public; Owner: -
--

CREATE POLICY triage_policy_versions_tenant_policy ON public.triage_policy_versions USING ((tenant_id = (NULLIF(current_setting('app.tenant_id'::text, true), ''::text))::uuid)) WITH CHECK ((tenant_id = (NULLIF(current_setting('app.tenant_id'::text, true), ''::text))::uuid));

--
-- Name: triage_rules; Type: ROW SECURITY; Schema: public; Owner: -
--

ALTER TABLE public.triage_rules ENABLE ROW LEVEL SECURITY;

--
-- Name: triage_rules triage_rules_tenant_policy; Type: POLICY; Schema: public; Owner: -
--

CREATE POLICY triage_rules_tenant_policy ON public.triage_rules USING ((tenant_id = (NULLIF(current_setting('app.tenant_id'::text, true), ''::text))::uuid)) WITH CHECK ((tenant_id = (NULLIF(current_setting('app.tenant_id'::text, true), ''::text))::uuid));

--
-- Name: unit_residents; Type: ROW SECURITY; Schema: public; Owner: -
--

ALTER TABLE public.unit_residents ENABLE ROW LEVEL SECURITY;

--
-- Name: unit_residents unit_residents_tenant_policy; Type: POLICY; Schema: public; Owner: -
--

CREATE POLICY unit_residents_tenant_policy ON public.unit_residents USING ((tenant_id = (NULLIF(current_setting('app.tenant_id'::text, true), ''::text))::uuid)) WITH CHECK ((tenant_id = (NULLIF(current_setting('app.tenant_id'::text, true), ''::text))::uuid));

--
-- Name: units; Type: ROW SECURITY; Schema: public; Owner: -
--

ALTER TABLE public.units ENABLE ROW LEVEL SECURITY;

--
-- Name: units units_tenant_policy; Type: POLICY; Schema: public; Owner: -
--

CREATE POLICY units_tenant_policy ON public.units USING ((tenant_id = (NULLIF(current_setting('app.tenant_id'::text, true), ''::text))::uuid)) WITH CHECK ((tenant_id = (NULLIF(current_setting('app.tenant_id'::text, true), ''::text))::uuid));

--
-- Name: vh_assets; Type: ROW SECURITY; Schema: public; Owner: -
--

ALTER TABLE public.vh_assets ENABLE ROW LEVEL SECURITY;

--
-- Name: vh_budget_approvals; Type: ROW SECURITY; Schema: public; Owner: -
--

ALTER TABLE public.vh_budget_approvals ENABLE ROW LEVEL SECURITY;

--
-- Name: vh_budget_approvals vh_budget_approvals_tenant; Type: POLICY; Schema: public; Owner: -
--

CREATE POLICY vh_budget_approvals_tenant ON public.vh_budget_approvals USING ((tenant_id = (NULLIF(current_setting('app.tenant_id'::text, true), ''::text))::uuid)) WITH CHECK ((tenant_id = (NULLIF(current_setting('app.tenant_id'::text, true), ''::text))::uuid));

--
-- Name: vh_cleaning_plans; Type: ROW SECURITY; Schema: public; Owner: -
--

ALTER TABLE public.vh_cleaning_plans ENABLE ROW LEVEL SECURITY;

--
-- Name: vh_cleaning_plans vh_cleaning_plans_tenant; Type: POLICY; Schema: public; Owner: -
--

CREATE POLICY vh_cleaning_plans_tenant ON public.vh_cleaning_plans USING ((tenant_id = (NULLIF(current_setting('app.tenant_id'::text, true), ''::text))::uuid)) WITH CHECK ((tenant_id = (NULLIF(current_setting('app.tenant_id'::text, true), ''::text))::uuid));

--
-- Name: vh_command_receipt; Type: ROW SECURITY; Schema: public; Owner: -
--

ALTER TABLE public.vh_command_receipt ENABLE ROW LEVEL SECURITY;

--
-- Name: vh_command_receipt vh_command_receipt_tenant_policy; Type: POLICY; Schema: public; Owner: -
--

CREATE POLICY vh_command_receipt_tenant_policy ON public.vh_command_receipt USING ((tenant_id = (NULLIF(current_setting('app.tenant_id'::text, true), ''::text))::uuid)) WITH CHECK ((tenant_id = (NULLIF(current_setting('app.tenant_id'::text, true), ''::text))::uuid));

--
-- Name: vh_contractor_updates; Type: ROW SECURITY; Schema: public; Owner: -
--

ALTER TABLE public.vh_contractor_updates ENABLE ROW LEVEL SECURITY;

--
-- Name: vh_contractor_updates vh_contractor_updates_tenant; Type: POLICY; Schema: public; Owner: -
--

CREATE POLICY vh_contractor_updates_tenant ON public.vh_contractor_updates USING ((tenant_id = (NULLIF(current_setting('app.tenant_id'::text, true), ''::text))::uuid)) WITH CHECK ((tenant_id = (NULLIF(current_setting('app.tenant_id'::text, true), ''::text))::uuid));

--
-- Name: vh_conversation_uploads; Type: ROW SECURITY; Schema: public; Owner: -
--

ALTER TABLE public.vh_conversation_uploads ENABLE ROW LEVEL SECURITY;

--
-- Name: vh_maintenance_records; Type: ROW SECURITY; Schema: public; Owner: -
--

ALTER TABLE public.vh_maintenance_records ENABLE ROW LEVEL SECURITY;

--
-- Name: vh_operational_requests; Type: ROW SECURITY; Schema: public; Owner: -
--

ALTER TABLE public.vh_operational_requests ENABLE ROW LEVEL SECURITY;

--
-- Name: vh_qc_redo_orders; Type: ROW SECURITY; Schema: public; Owner: -
--

ALTER TABLE public.vh_qc_redo_orders ENABLE ROW LEVEL SECURITY;

--
-- Name: vh_qc_redo_orders vh_qc_redo_orders_tenant; Type: POLICY; Schema: public; Owner: -
--

CREATE POLICY vh_qc_redo_orders_tenant ON public.vh_qc_redo_orders USING ((tenant_id = (NULLIF(current_setting('app.tenant_id'::text, true), ''::text))::uuid)) WITH CHECK ((tenant_id = (NULLIF(current_setting('app.tenant_id'::text, true), ''::text))::uuid));

--
-- Name: vh_qc_results; Type: ROW SECURITY; Schema: public; Owner: -
--

ALTER TABLE public.vh_qc_results ENABLE ROW LEVEL SECURITY;

--
-- Name: vh_qc_results vh_qc_results_tenant; Type: POLICY; Schema: public; Owner: -
--

CREATE POLICY vh_qc_results_tenant ON public.vh_qc_results USING ((tenant_id = (NULLIF(current_setting('app.tenant_id'::text, true), ''::text))::uuid)) WITH CHECK ((tenant_id = (NULLIF(current_setting('app.tenant_id'::text, true), ''::text))::uuid));

--
-- Name: vh_reception_supervisor_messages; Type: ROW SECURITY; Schema: public; Owner: -
--

ALTER TABLE public.vh_reception_supervisor_messages ENABLE ROW LEVEL SECURITY;

--
-- Name: vh_reception_supervisor_messages vh_reception_supervisor_messages_tenant_policy; Type: POLICY; Schema: public; Owner: -
--

CREATE POLICY vh_reception_supervisor_messages_tenant_policy ON public.vh_reception_supervisor_messages USING ((tenant_id = (NULLIF(current_setting('app.tenant_id'::text, true), ''::text))::uuid)) WITH CHECK ((tenant_id = (NULLIF(current_setting('app.tenant_id'::text, true), ''::text))::uuid));

--
-- Name: vh_reception_supervisor_pending; Type: ROW SECURITY; Schema: public; Owner: -
--

ALTER TABLE public.vh_reception_supervisor_pending ENABLE ROW LEVEL SECURITY;

--
-- Name: vh_reception_supervisor_pending vh_reception_supervisor_pending_tenant_policy; Type: POLICY; Schema: public; Owner: -
--

CREATE POLICY vh_reception_supervisor_pending_tenant_policy ON public.vh_reception_supervisor_pending USING ((tenant_id = (NULLIF(current_setting('app.tenant_id'::text, true), ''::text))::uuid)) WITH CHECK ((tenant_id = (NULLIF(current_setting('app.tenant_id'::text, true), ''::text))::uuid));

--
-- Name: vh_report_exports; Type: ROW SECURITY; Schema: public; Owner: -
--

ALTER TABLE public.vh_report_exports ENABLE ROW LEVEL SECURITY;

--
-- Name: vh_resident_case_tickets; Type: ROW SECURITY; Schema: public; Owner: -
--

ALTER TABLE public.vh_resident_case_tickets ENABLE ROW LEVEL SECURITY;

--
-- Name: vh_resident_cases; Type: ROW SECURITY; Schema: public; Owner: -
--

ALTER TABLE public.vh_resident_cases ENABLE ROW LEVEL SECURITY;

--
-- Name: vh_resident_command_receipts; Type: ROW SECURITY; Schema: public; Owner: -
--

ALTER TABLE public.vh_resident_command_receipts ENABLE ROW LEVEL SECURITY;

--
-- Name: vh_resident_outbox; Type: ROW SECURITY; Schema: public; Owner: -
--

ALTER TABLE public.vh_resident_outbox ENABLE ROW LEVEL SECURITY;

--
-- Name: vh_resident_photos; Type: ROW SECURITY; Schema: public; Owner: -
--

ALTER TABLE public.vh_resident_photos ENABLE ROW LEVEL SECURITY;

--
-- Name: vh_resident_public_events; Type: ROW SECURITY; Schema: public; Owner: -
--

ALTER TABLE public.vh_resident_public_events ENABLE ROW LEVEL SECURITY;

--
-- Name: vh_resident_resolution_photos; Type: ROW SECURITY; Schema: public; Owner: -
--

ALTER TABLE public.vh_resident_resolution_photos ENABLE ROW LEVEL SECURITY;

--
-- Name: vh_resident_resolution_responses; Type: ROW SECURITY; Schema: public; Owner: -
--

ALTER TABLE public.vh_resident_resolution_responses ENABLE ROW LEVEL SECURITY;

--
-- Name: vh_resident_resolutions; Type: ROW SECURITY; Schema: public; Owner: -
--

ALTER TABLE public.vh_resident_resolutions ENABLE ROW LEVEL SECURITY;

--
-- Name: vh_resident_submissions; Type: ROW SECURITY; Schema: public; Owner: -
--

ALTER TABLE public.vh_resident_submissions ENABLE ROW LEVEL SECURITY;

--
-- Name: vh_security_checkpoints; Type: ROW SECURITY; Schema: public; Owner: -
--

ALTER TABLE public.vh_security_checkpoints ENABLE ROW LEVEL SECURITY;

--
-- Name: vh_security_checkpoints vh_security_checkpoints_tenant; Type: POLICY; Schema: public; Owner: -
--

CREATE POLICY vh_security_checkpoints_tenant ON public.vh_security_checkpoints USING ((tenant_id = (NULLIF(current_setting('app.tenant_id'::text, true), ''::text))::uuid)) WITH CHECK ((tenant_id = (NULLIF(current_setting('app.tenant_id'::text, true), ''::text))::uuid));

--
-- Name: vh_security_handovers; Type: ROW SECURITY; Schema: public; Owner: -
--

ALTER TABLE public.vh_security_handovers ENABLE ROW LEVEL SECURITY;

--
-- Name: vh_security_handovers vh_security_handovers_tenant; Type: POLICY; Schema: public; Owner: -
--

CREATE POLICY vh_security_handovers_tenant ON public.vh_security_handovers USING ((tenant_id = (NULLIF(current_setting('app.tenant_id'::text, true), ''::text))::uuid)) WITH CHECK ((tenant_id = (NULLIF(current_setting('app.tenant_id'::text, true), ''::text))::uuid));

--
-- Name: vh_security_incidents; Type: ROW SECURITY; Schema: public; Owner: -
--

ALTER TABLE public.vh_security_incidents ENABLE ROW LEVEL SECURITY;

--
-- Name: vh_security_incidents vh_security_incidents_tenant; Type: POLICY; Schema: public; Owner: -
--

CREATE POLICY vh_security_incidents_tenant ON public.vh_security_incidents USING ((tenant_id = (NULLIF(current_setting('app.tenant_id'::text, true), ''::text))::uuid)) WITH CHECK ((tenant_id = (NULLIF(current_setting('app.tenant_id'::text, true), ''::text))::uuid));

--
-- Name: vh_sensor_readings; Type: ROW SECURITY; Schema: public; Owner: -
--

ALTER TABLE public.vh_sensor_readings ENABLE ROW LEVEL SECURITY;

--
-- Name: vh_technical_measurements; Type: ROW SECURITY; Schema: public; Owner: -
--

ALTER TABLE public.vh_technical_measurements ENABLE ROW LEVEL SECURITY;

--
-- Name: vh_ticket_plans; Type: ROW SECURITY; Schema: public; Owner: -
--

ALTER TABLE public.vh_ticket_plans ENABLE ROW LEVEL SECURITY;

--
-- Name: work_approvals; Type: ROW SECURITY; Schema: public; Owner: -
--

ALTER TABLE public.work_approvals ENABLE ROW LEVEL SECURITY;

--
-- Name: work_approvals work_approvals_tenant_policy; Type: POLICY; Schema: public; Owner: -
--

CREATE POLICY work_approvals_tenant_policy ON public.work_approvals USING ((tenant_id = (NULLIF(current_setting('app.tenant_id'::text, true), ''::text))::uuid)) WITH CHECK ((tenant_id = (NULLIF(current_setting('app.tenant_id'::text, true), ''::text))::uuid));

--
-- Name: work_assignments; Type: ROW SECURITY; Schema: public; Owner: -
--

ALTER TABLE public.work_assignments ENABLE ROW LEVEL SECURITY;

--
-- Name: work_assignments work_assignments_tenant_policy; Type: POLICY; Schema: public; Owner: -
--

CREATE POLICY work_assignments_tenant_policy ON public.work_assignments USING ((tenant_id = (NULLIF(current_setting('app.tenant_id'::text, true), ''::text))::uuid)) WITH CHECK ((tenant_id = (NULLIF(current_setting('app.tenant_id'::text, true), ''::text))::uuid));

--
-- Name: work_orders; Type: ROW SECURITY; Schema: public; Owner: -
--

ALTER TABLE public.work_orders ENABLE ROW LEVEL SECURITY;

--
-- Name: work_orders work_orders_tenant_policy; Type: POLICY; Schema: public; Owner: -
--

CREATE POLICY work_orders_tenant_policy ON public.work_orders USING ((tenant_id = (NULLIF(current_setting('app.tenant_id'::text, true), ''::text))::uuid)) WITH CHECK ((tenant_id = (NULLIF(current_setting('app.tenant_id'::text, true), ''::text))::uuid));

--
-- Name: workspace_members; Type: ROW SECURITY; Schema: public; Owner: -
--

ALTER TABLE public.workspace_members ENABLE ROW LEVEL SECURITY;

--
-- Name: workspace_members workspace_members_tenant_policy; Type: POLICY; Schema: public; Owner: -
--

CREATE POLICY workspace_members_tenant_policy ON public.workspace_members USING ((tenant_id = (NULLIF(current_setting('app.tenant_id'::text, true), ''::text))::uuid)) WITH CHECK ((tenant_id = (NULLIF(current_setting('app.tenant_id'::text, true), ''::text))::uuid));

--
-- Name: workspaces; Type: ROW SECURITY; Schema: public; Owner: -
--

ALTER TABLE public.workspaces ENABLE ROW LEVEL SECURITY;

--
-- Name: workspaces workspaces_tenant_policy; Type: POLICY; Schema: public; Owner: -
--

CREATE POLICY workspaces_tenant_policy ON public.workspaces USING ((tenant_id = (NULLIF(current_setting('app.tenant_id'::text, true), ''::text))::uuid)) WITH CHECK ((tenant_id = (NULLIF(current_setting('app.tenant_id'::text, true), ''::text))::uuid));

--
-- Name: zones; Type: ROW SECURITY; Schema: public; Owner: -
--

ALTER TABLE public.zones ENABLE ROW LEVEL SECURITY;

--
-- Name: zones zones_tenant_policy; Type: POLICY; Schema: public; Owner: -
--

CREATE POLICY zones_tenant_policy ON public.zones USING ((tenant_id = (NULLIF(current_setting('app.tenant_id'::text, true), ''::text))::uuid)) WITH CHECK ((tenant_id = (NULLIF(current_setting('app.tenant_id'::text, true), ''::text))::uuid));

--
--
