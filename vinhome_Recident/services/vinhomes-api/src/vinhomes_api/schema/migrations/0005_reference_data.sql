-- Rows the application needs in every database, whatever the tenant.
-- The Reception agent is registered here as the one runtime that may be delegated a resident's turn.
insert into runtime_backends(code, framework, sdk_language, package_version, backend_kind, connection_secret_ref, schema_name, enabled)
values ('reception-langgraph', 'langgraph', 'python', '1.1.6', 'custom', 'RECEPTION_STATE_PATH', 'reception', true)
on conflict do nothing;
