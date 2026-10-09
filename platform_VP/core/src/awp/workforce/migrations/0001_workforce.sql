CREATE TABLE IF NOT EXISTS awp_wf_approvals (
	id VARCHAR(200) NOT NULL,
	workflow_id VARCHAR(200) NOT NULL,
	operation_id VARCHAR(200) NOT NULL,
	status VARCHAR(200) NOT NULL,
	arguments_hash VARCHAR(200) NOT NULL,
	quote_ref VARCHAR(200) NOT NULL,
	revision INTEGER NOT NULL,
	expires FLOAT NOT NULL,
	summary VARCHAR(4000) NOT NULL,
	PRIMARY KEY (id)
);
CREATE TABLE IF NOT EXISTS awp_wf_assets (
	id VARCHAR(200) NOT NULL,
	client_id VARCHAR(200) NOT NULL,
	route_id VARCHAR(200) NOT NULL,
	user_id VARCHAR(200) NOT NULL,
	external_ticket_id VARCHAR(200) NOT NULL,
	external_conversation_id VARCHAR(200) NOT NULL,
	object_key VARCHAR(200) NOT NULL,
	status VARCHAR(200) NOT NULL,
	workflow_id VARCHAR(200),
	metadata JSON NOT NULL,
	created FLOAT NOT NULL,
	expires FLOAT NOT NULL,
	PRIMARY KEY (id)
);
CREATE TABLE IF NOT EXISTS awp_wf_audit (
	id VARCHAR(200) NOT NULL,
	tenant VARCHAR(200) NOT NULL,
	actor VARCHAR(200) NOT NULL,
	action VARCHAR(200) NOT NULL,
	resource VARCHAR(200) NOT NULL,
	data JSON NOT NULL,
	created FLOAT NOT NULL,
	PRIMARY KEY (id)
);
CREATE TABLE IF NOT EXISTS awp_wf_clients (
	id VARCHAR(200) NOT NULL,
	tenant VARCHAR(200) NOT NULL,
	purpose VARCHAR(200) NOT NULL,
	key_hash VARCHAR(200) NOT NULL,
	status VARCHAR(200) NOT NULL,
	expires FLOAT,
	operations JSON NOT NULL,
	settings JSON NOT NULL,
	PRIMARY KEY (id)
);
CREATE TABLE IF NOT EXISTS awp_wf_conversations (
	id VARCHAR(200) NOT NULL,
	client_id VARCHAR(200) NOT NULL,
	route_id VARCHAR(200) NOT NULL,
	user_id VARCHAR(200) NOT NULL,
	external_ticket_id VARCHAR(200) NOT NULL,
	external_conversation_id VARCHAR(200) NOT NULL,
	sequence INTEGER NOT NULL,
	purged_through INTEGER NOT NULL,
	latest_event_id VARCHAR(200),
	PRIMARY KEY (id),
	CONSTRAINT uq_wf_conversations_0 UNIQUE (client_id, external_conversation_id),
	CONSTRAINT uq_wf_conversations_1 UNIQUE (client_id, external_ticket_id)
);
CREATE TABLE IF NOT EXISTS awp_wf_events (
	id VARCHAR(200) NOT NULL,
	conversation_id VARCHAR(200) NOT NULL,
	workflow_id VARCHAR(200) NOT NULL,
	sequence INTEGER NOT NULL,
	event_type VARCHAR(200) NOT NULL,
	payload JSON NOT NULL,
	occurred FLOAT NOT NULL,
	recorded FLOAT NOT NULL,
	PRIMARY KEY (id),
	CONSTRAINT uq_wf_events_0 UNIQUE (conversation_id, sequence)
);
CREATE INDEX IF NOT EXISTS ix_wf_events_retention ON awp_wf_events (workflow_id, recorded);
CREATE TABLE IF NOT EXISTS awp_wf_integrations (
	id VARCHAR(200) NOT NULL,
	tenant VARCHAR(200) NOT NULL,
	status VARCHAR(200) NOT NULL,
	revision INTEGER NOT NULL,
	config JSON NOT NULL,
	PRIMARY KEY (id)
);
CREATE TABLE IF NOT EXISTS awp_wf_jobs (
	id VARCHAR(200) NOT NULL,
	workflow_id VARCHAR(200) NOT NULL,
	request_id VARCHAR(200) NOT NULL,
	kind VARCHAR(200) NOT NULL,
	status VARCHAR(200) NOT NULL,
	payload JSON NOT NULL,
	owner VARCHAR(200),
	lease_until FLOAT NOT NULL,
	generation INTEGER NOT NULL,
	attempts INTEGER NOT NULL,
	available FLOAT NOT NULL,
	PRIMARY KEY (id)
);
CREATE INDEX IF NOT EXISTS ix_wf_jobs_claim ON awp_wf_jobs (status, available, lease_until);
CREATE INDEX IF NOT EXISTS ix_wf_jobs_workflow ON awp_wf_jobs (workflow_id, status);
CREATE TABLE IF NOT EXISTS awp_wf_knowledge (
	id VARCHAR(200) NOT NULL,
	tenant VARCHAR(200) NOT NULL,
	knowledge_base_id VARCHAR(200) NOT NULL,
	document_key VARCHAR(200) NOT NULL,
	version INTEGER NOT NULL,
	status VARCHAR(200) NOT NULL,
	sha256 VARCHAR(200) NOT NULL,
	title VARCHAR(300) NOT NULL,
	text TEXT NOT NULL,
	source VARCHAR(2000) NOT NULL,
	created FLOAT NOT NULL,
	PRIMARY KEY (id),
	CONSTRAINT uq_wf_knowledge_0 UNIQUE (tenant, knowledge_base_id, document_key, version)
);
CREATE INDEX IF NOT EXISTS ix_wf_knowledge_scope ON awp_wf_knowledge (tenant, knowledge_base_id, status);
CREATE TABLE IF NOT EXISTS awp_wf_memory (
	workflow_id VARCHAR(200) NOT NULL,
	profile_key VARCHAR(200) NOT NULL,
	key VARCHAR(200) NOT NULL,
	text VARCHAR(8000) NOT NULL,
	updated FLOAT NOT NULL,
	PRIMARY KEY (workflow_id, profile_key, key)
);
CREATE TABLE IF NOT EXISTS awp_wf_messages (
	id VARCHAR(200) NOT NULL,
	conversation_id VARCHAR(200) NOT NULL,
	workflow_id VARCHAR(200) NOT NULL,
	sequence INTEGER NOT NULL,
	payload JSON NOT NULL,
	PRIMARY KEY (id)
);
CREATE INDEX IF NOT EXISTS ix_wf_messages_conversation ON awp_wf_messages (conversation_id, sequence);
CREATE TABLE IF NOT EXISTS awp_wf_operations (
	id VARCHAR(200) NOT NULL,
	workflow_id VARCHAR(200) NOT NULL,
	integration_id VARCHAR(200) NOT NULL,
	client_reference VARCHAR(200) NOT NULL,
	external_job_id VARCHAR(200),
	status VARCHAR(200) NOT NULL,
	provider_version INTEGER NOT NULL,
	data JSON NOT NULL,
	created FLOAT NOT NULL,
	PRIMARY KEY (id),
	CONSTRAINT uq_wf_operations_0 UNIQUE (integration_id, client_reference),
	CONSTRAINT uq_wf_operations_1 UNIQUE (integration_id, external_job_id)
);
CREATE INDEX IF NOT EXISTS ix_wf_operations_workflow ON awp_wf_operations (workflow_id, status);
CREATE TABLE IF NOT EXISTS awp_wf_rate_limits (
	id VARCHAR(200) NOT NULL,
	"window" INTEGER NOT NULL,
	count INTEGER NOT NULL,
	PRIMARY KEY (id)
);
CREATE TABLE IF NOT EXISTS awp_wf_receipts (
	id VARCHAR(200) NOT NULL,
	integration_id VARCHAR(200) NOT NULL,
	external_id VARCHAR(200) NOT NULL,
	payload_hash VARCHAR(200) NOT NULL,
	status VARCHAR(200) NOT NULL,
	body JSON NOT NULL,
	policy JSON NOT NULL,
	received FLOAT NOT NULL,
	applied FLOAT,
	error JSON,
	PRIMARY KEY (id),
	CONSTRAINT uq_wf_receipts_0 UNIQUE (integration_id, external_id)
);
CREATE TABLE IF NOT EXISTS awp_wf_requests (
	id VARCHAR(200) NOT NULL,
	client_id VARCHAR(200) NOT NULL,
	external_id VARCHAR(200) NOT NULL,
	payload_hash VARCHAR(200) NOT NULL,
	command VARCHAR(200) NOT NULL,
	workflow_id VARCHAR(200) NOT NULL,
	status VARCHAR(200) NOT NULL,
	body JSON NOT NULL,
	result JSON,
	error JSON,
	created FLOAT NOT NULL,
	completed FLOAT,
	PRIMARY KEY (id),
	CONSTRAINT uq_wf_requests_0 UNIQUE (client_id, external_id)
);
CREATE INDEX IF NOT EXISTS ix_wf_requests_workflow ON awp_wf_requests (workflow_id, status);
CREATE TABLE IF NOT EXISTS awp_wf_reservations (
	id VARCHAR(200) NOT NULL,
	workflow_id VARCHAR(200) NOT NULL,
	status VARCHAR(200) NOT NULL,
	micros INTEGER NOT NULL,
	tokens INTEGER NOT NULL,
	actual_micros INTEGER,
	actual_tokens INTEGER,
	created FLOAT NOT NULL,
	PRIMARY KEY (id)
);
CREATE TABLE IF NOT EXISTS awp_wf_residences (
	client_id VARCHAR(200) NOT NULL,
	residence_id VARCHAR(200) NOT NULL,
	user_id VARCHAR(200) NOT NULL,
	route_id VARCHAR(200) NOT NULL,
	status VARCHAR(200) NOT NULL,
	revision INTEGER NOT NULL,
	updated FLOAT NOT NULL,
	PRIMARY KEY (client_id, residence_id, user_id)
);
CREATE TABLE IF NOT EXISTS awp_wf_routes (
	id VARCHAR(200) NOT NULL,
	client_id VARCHAR(200) NOT NULL,
	external_ref VARCHAR(200) NOT NULL,
	status VARCHAR(200) NOT NULL,
	revision INTEGER NOT NULL,
	config JSON NOT NULL,
	PRIMARY KEY (id),
	CONSTRAINT uq_wf_routes_0 UNIQUE (client_id, external_ref)
);
CREATE TABLE IF NOT EXISTS awp_wf_session_fences (
	id VARCHAR(200) NOT NULL,
	job_id VARCHAR(200) NOT NULL,
	owner VARCHAR(200) NOT NULL,
	generation INTEGER NOT NULL,
	role VARCHAR(200) NOT NULL,
	PRIMARY KEY (id)
);
CREATE TABLE IF NOT EXISTS awp_wf_workflows (
	id VARCHAR(200) NOT NULL,
	conversation_id VARCHAR(200) NOT NULL,
	state VARCHAR(200) NOT NULL,
	revision INTEGER NOT NULL,
	snapshot JSON NOT NULL,
	case_id VARCHAR(200),
	closed_at FLOAT,
	created FLOAT NOT NULL,
	updated FLOAT NOT NULL,
	PRIMARY KEY (id),
	UNIQUE (case_id)
);
CREATE INDEX IF NOT EXISTS ix_wf_workflows_conversation ON awp_wf_workflows (conversation_id);
