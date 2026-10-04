-- A separate non-superuser, non-BYPASSRLS LOGIN role for the account/connector host.
GRANT USAGE ON SCHEMA public TO vinhomes_business_connections;
GRANT SELECT ON users,platform_admins,tenant_memberships,scoped_user_roles,
  agents,agent_profiles,agent_preferences,action_policy TO vinhomes_business_connections;
GRANT SELECT,INSERT,UPDATE ON credentials TO vinhomes_business_connections;
GRANT SELECT,INSERT,UPDATE,DELETE ON mcp_servers,mcp_tools,mcp_user_credentials,
  composio_connections,plugin_grants,skills,skill_tools TO vinhomes_business_connections;
GRANT INSERT ON audit_events TO vinhomes_business_connections;
