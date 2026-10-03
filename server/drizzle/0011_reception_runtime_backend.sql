-- The Reception runtime (agent-reception) keeps its LangGraph checkpoints in its own
-- store. Registering it lets the business API bind one session per resident
-- conversation and one agent run per resident message. Disable the row to stop
-- every Reception delegation at once.
INSERT INTO runtime_backends (code, framework, sdk_language, package_version, backend_kind, connection_secret_ref, schema_name)
VALUES ('reception-langgraph', 'langgraph', 'python', '1.1.6', 'custom', 'RECEPTION_STATE_PATH', 'reception')
ON CONFLICT (code) DO NOTHING;
