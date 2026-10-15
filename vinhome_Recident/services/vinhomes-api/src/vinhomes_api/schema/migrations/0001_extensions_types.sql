-- Domain Vinhomes database. Generated once from the running schema, then kept by hand.
-- Every table has tenant_id and row level security that is forced; the API runs as a role that cannot bypass it.

create extension if not exists btree_gist;

create type public.agent_type as enum ('built_in', 'remote_ag_ui', 'remote_mastra');
