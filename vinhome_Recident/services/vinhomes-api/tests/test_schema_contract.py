"""What the domain database promises, checked on a database built only from vinhomes_api/schema."""

import asyncio
import re
from pathlib import Path
from uuid import uuid4

import asyncpg
import pytest
from test_resident_contract import TENANT, sql
from test_resident_contract import database as database  # noqa: F401 -- pytest fixture export

from vinhomes_api import database as tool

SRC = Path(__file__).resolve().parents[1] / "src" / "vinhomes_api"
# Identity tables shared by every tenant: a person signs in before any tenant is chosen.
GLOBAL_TABLES = {"accounts", "platform_admins", "sessions", "state_transitions", "tenants", "users", "schema_migrations"}
# Tables of the platform that must never come back into this package's SQL.
PLATFORM_TABLES = {
    "knowledge_bases", "knowledge_documents", "knowledge_chunks", "knowledge_embeddings", "knowledge_reviews",
    "agent_knowledge_grants", "agent_profiles", "agent_preferences", "mcp_servers", "mcp_tools", "mcp_user_credentials",
    "skills", "skill_tools", "routines", "routine_runs", "routine_sweeps", "memory_candidates", "memory_namespaces",
    "memory_publications", "retrieval_runs", "retrieval_hits", "admin_model_registry", "admin_role_models", "credentials",
    "deployment_packages", "team_tasks", "team_mailbox", "composio_connections", "plugin_grants", "vh_agent_reviews",
    "vh_agent_skills", "vh_private_chats", "vh_session_sources",
    # Agent-shaped tables replaced by integration_clients, delegations and integration_cases (migration 0006).
    "agents", "agent_versions", "agent_releases", "agent_runs", "agent_teams", "team_members", "channel_agents",
    "runtime_backends", "runtime_identities", "runtime_session_bindings",
}


def _connect(url: str):
    return asyncpg.connect(url.replace("postgresql+asyncpg:", "postgresql:"))


def test_every_tenant_table_has_forced_row_level_security_and_a_policy(database):
    rows = sql(database, """
        select c.relname, c.relrowsecurity, c.relforcerowsecurity,
               exists(select 1 from information_schema.columns k where k.table_schema='public'
                      and k.table_name=c.relname and k.column_name='tenant_id') as has_tenant,
               (select count(*) from pg_policies p where p.schemaname='public' and p.tablename=c.relname) as policies
        from pg_class c where c.relnamespace='public'::regnamespace and c.relkind='r' order by 1""")
    assert len(rows) > 100
    problems = []
    for row in rows:
        if row["relname"] in GLOBAL_TABLES:
            continue
        if not (row["has_tenant"] and row["relrowsecurity"] and row["relforcerowsecurity"] and row["policies"] >= 1):
            problems.append(row["relname"])
    assert problems == []
    assert {r["relname"] for r in rows if not r["has_tenant"]} <= GLOBAL_TABLES


def test_no_platform_table_exists_in_the_domain_database(database):
    names = {r["relname"] for r in sql(database, "select relname from pg_class where relnamespace='public'::regnamespace and relkind='r'")}
    assert names & PLATFORM_TABLES == set()
    assert "vector" not in {r["extname"] for r in sql(database, "select extname from pg_extension")}


def test_the_backend_sql_never_names_a_platform_table():
    pattern = re.compile(r"\b(?:from|join|into|update|table)\s+(?:public\.)?([a-z_][a-z0-9_]*)", re.I)
    found = {}
    for path in SRC.rglob("*.py"):
        for name in pattern.findall(path.read_text(encoding="utf-8")):
            if name.lower() in PLATFORM_TABLES:
                found.setdefault(name.lower(), set()).add(path.name)
    assert found == {}


def test_a_tenant_reads_and_writes_only_its_own_rows(database):
    async def run():
        connection = await _connect(database["runtime"])
        try:
            async def visible(tenant):
                async with connection.transaction():
                    if tenant:
                        await connection.execute("select set_config('app.tenant_id',$1,true)", str(tenant))
                    return await connection.fetchval("select count(*) from tickets")

            own, other, none = await visible(TENANT), await visible(uuid4()), await visible(None)
            with pytest.raises(asyncpg.PostgresError):
                async with connection.transaction():
                    await connection.execute("select set_config('app.tenant_id',$1,true)", str(TENANT))
                    await connection.execute("insert into ticket_events(id,tenant_id) values(gen_random_uuid(),$1)", uuid4())
            return own, other, none
        finally:
            await connection.close()

    own, other, none = asyncio.run(run())
    assert own > 0 and other == 0 and none == 0


def test_the_runtime_role_cannot_bypass_row_level_security(database):
    async def run():
        connection = await _connect(database["runtime"])
        try:
            return await connection.fetchrow("select rolsuper, rolbypassrls, rolcreaterole, rolcreatedb from pg_roles where rolname=current_user")
        finally:
            await connection.close()

    flags = asyncio.run(run())
    assert not any(flags.values())


def test_the_audit_trail_is_append_only(database):
    event = sql(database, """insert into audit_events(tenant_id,initiator_kind,initiator_id,event_type,target_type,target_id,payload)
        values($1,'system','schema-contract','contract.test','test','t','{}') returning id""", TENANT)[0]["id"]
    with pytest.raises(asyncpg.PostgresError):
        sql(database, "update audit_events set event_type='tampered' where id=$1 returning id", event)
    with pytest.raises(asyncpg.PostgresError):
        sql(database, "delete from audit_events where id=$1 returning id", event)


def test_migrations_run_once_and_refuse_a_changed_file(database, tmp_path, monkeypatch):
    admin = database["admin"]
    assert asyncio.run(tool.migrate(admin)) == []
    names = [r["name"] for r in sql(database, "select name from schema_migrations order by name")]
    assert names == [p.name for p in tool.migration_files()]
    copy = tmp_path / "schema"
    (copy / "migrations").mkdir(parents=True)
    for path in tool.migration_files():
        (copy / "migrations" / path.name).write_text(path.read_text(encoding="utf-8") + ("\n-- edited\n" if path.name.startswith("0005") else ""), encoding="utf-8")
    monkeypatch.setattr(tool, "SCHEMA", copy)
    with pytest.raises(SystemExit):
        asyncio.run(tool.migrate(admin))
