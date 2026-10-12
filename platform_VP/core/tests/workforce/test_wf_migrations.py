"""Alembic: the migrations build the schema the models describe, go down again, and never drift from the models (the CI
guard of the last test). Run on SQLite, and on PostgreSQL with AWP_TEST_PG_URL set (tests/dbtest.py)."""
import asyncio

import pytest

import dbtest
from awp import migrate
from awp.app import build_app
from awp.config import Settings
from awp.db import Database, metadata
from awp.providers import ModelCatalog
from awp.workforce import tables  # noqa: F401  (the wf_* tables on the metadata)

MODEL_TABLES = set(metadata.tables)


@pytest.fixture
def blank(tmp_path):
    return dbtest.empty(tmp_path)


def tables_of(db) -> set[str]:
    con = dbtest.connect(db)
    try:
        return con.tables()
    finally:
        con.close()


def test_upgrade_builds_every_table_of_the_models_and_nothing_else(blank):
    assert tables_of(blank) <= {"awp_alembic_version"} | set()
    migrate.upgrade(blank.url)
    assert tables_of(blank) == MODEL_TABLES | {"awp_alembic_version"}
    assert {"awp_cases", "wf_workflows", "wf_provider_inbox", "wf_leases"} <= MODEL_TABLES
    assert asyncio.run(migrate.current(blank.url)) == migrate.head()
    migrate.upgrade(blank.url)  # at head already: nothing to do, no error


def test_downgrade_removes_them_again_and_the_upgrade_can_be_repeated(blank):
    migrate.upgrade(blank.url)
    migrate.downgrade(blank.url, "base")
    assert tables_of(blank) <= {"awp_alembic_version"}
    assert asyncio.run(migrate.current(blank.url)) is None
    migrate.upgrade(blank.url)
    assert tables_of(blank) == MODEL_TABLES | {"awp_alembic_version"}


def test_the_migrated_schema_has_the_constraints_the_tables_module_declares(blank):
    """Partial unique indexes and checks are the ones create_all makes: the same rows are refused."""
    migrate.upgrade(blank.url)
    con = dbtest.connect(blank)
    try:
        route = dict(client_id="c1", external_management_ref="REF", revision=1, leader_profile="x", config="{}", created_at=1)
        ins = lambda i, status: con.execute(  # noqa: E731
            "insert into wf_routes (id, status, client_id, external_management_ref, revision, leader_profile, config, "
            "created_at) values (?, ?, ?, ?, ?, ?, ?, ?)", (i, status, *route.values()))
        ins("r1", "active")
        ins("r2", "pending")
        with pytest.raises(dbtest.IntegrityError):
            ins("r3", "active")  # one active route per ref
        with pytest.raises(dbtest.IntegrityError):  # the key must belong to exactly one owner
            con.execute("insert into wf_keys (key_id, kind, secret_hash, operations, routes, status, created_at) "
                        "values ('k', 'customer', 'h', '[]', '[]', 'active', 1)")
        con.execute("insert into wf_jobs (id, workflow_id, kind, payload, status, attempts, created_at) "
                    "values ('j1', 'w', 'nudge', '{}', 'dispatched', 0, 1)")
        with pytest.raises(dbtest.IntegrityError):  # one dispatched job per workflow
            con.execute("insert into wf_jobs (id, workflow_id, kind, payload, status, attempts, created_at) "
                        "values ('j2', 'w', 'nudge', '{}', 'dispatched', 0, 1)")
    finally:
        con.close()


# ---- the drift guard -------------------------------------------------------------------------------------------------
def test_models_and_migrations_never_drift(blank):
    """Autogenerate, run against the migrated database, must find nothing to do. When this fails, a table, column,
    index or constraint of awp/db.py or workforce/tables.py changed without a new revision: write one
    (`alembic revision --autogenerate` with the config of awp.migrate) and keep the initial one as it is."""
    migrate.upgrade(blank.url)
    assert migrate.drift(blank.url) == []
    assert migrate.check(blank.url) == []


def test_revision_0002_keeps_the_rows_that_were_there_working_as_they_did(blank):
    """The tool store and managers (0002) on a database that already holds servers, tools and routes: the servers stay
    on, the tools stay manual and active, the routes have no manager; and the step can be taken back."""
    migrate.upgrade(blank.url, "0001_initial")
    con = dbtest.connect(blank)
    try:
        con.execute("insert into wf_mcp_servers (route_id, name, url, transport, timeout) values ('r1', 'p', 'http://x/mcp', "
                    "'streamable_http', 8.0)")
        con.execute("insert into wf_tools (route_id, name, server, mcp_tool, kind, read_only, requires_consent, tracking, "
                    "call_timeout) values ('r1', 't', 'p', 'm', 'action', ?, ?, 'none', 8.0)", (False, False))
        con.execute("insert into wf_routes (id, status, client_id, external_management_ref, revision, leader_profile, config, "
                    "created_at) values ('r1', 'active', 'c1', 'REF', 1, 'x', '{}', 1)")
        migrate.upgrade(blank.url)
        assert {"wf_managers", "wf_manager_keys"} <= con.tables()
        assert con.execute("select enabled, last_discovered_at, last_error from wf_mcp_servers") == [(True, None, None)]
        assert con.execute("select source, status, schema, discovered_at, consent_waiver, requires_consent from wf_tools") == [
            ("manual", "active", None, None, None, False)]
        assert con.execute("select manager_id from wf_routes") == [(None,)]
        assert migrate.drift(blank.url) == []
        migrate.downgrade(blank.url, "0001_initial")
        assert not {"wf_managers", "wf_manager_keys"} & con.tables()
        assert "enabled" not in con.columns("wf_mcp_servers") and "manager_id" not in con.columns("wf_routes")
        assert con.execute("select name, kind from wf_tools") == [("t", "action")]  # the rows themselves are untouched
    finally:
        con.close()


def test_revision_0003_keeps_one_published_version_of_a_key_and_then_enforces_it(blank):
    """A database in which two publishers once both won (the race 0003 closes): the newest stays published, the older
    is retired as publishing the newest would have made it, and from then on the database refuses a second one."""
    migrate.upgrade(blank.url, "0002_tool_store_managers")
    con = dbtest.connect(blank)
    try:
        ins = lambda i, tenant, key, version, status: con.execute(  # noqa: E731
            "insert into awp_profiles (id, tenant, key, version, status, data, created_at) values (?, ?, ?, ?, ?, '{}', 1)",
            (i, tenant, key, version, status))
        ins("p1", "ta", "desk", 1, "published")
        ins("p2", "ta", "desk", 2, "published")
        ins("p3", "ta", "desk", 3, "draft")
        ins("p4", "tb", "desk", 1, "published")  # another tenant's key of the same name is its own
        ins("p5", "ta", "tech", 1, "published")
        con.execute("insert into wf_mcp_servers (route_id, name, url, transport, timeout, enabled) values ('r1', 'p', "
                    "'http://x/mcp', 'streamable_http', 8.0, ?)", (True,))
        migrate.upgrade(blank.url)
        assert con.execute("select id, status from awp_profiles order by id") == [
            ("p1", "retired"), ("p2", "published"), ("p3", "draft"), ("p4", "published"), ("p5", "published")]
        assert con.execute("select revision from wf_mcp_servers") == [(0,)]
        with pytest.raises(dbtest.IntegrityError):
            con.execute("update awp_profiles set status = 'published' where id = 'p3'")
        ins("p6", "ta", "desk", 4, "retired")  # any number of retired ones and drafts
        assert migrate.drift(blank.url) == []
        migrate.downgrade(blank.url, "0002_tool_store_managers")
        assert "revision" not in con.columns("wf_mcp_servers")
        con.execute("update awp_profiles set status = 'published' where id = 'p3'")  # the index went with the revision
    finally:
        con.close()


def test_revision_0004_adds_the_release_tables_and_dates_the_versions_that_were_live(blank):
    """A version that is published or retired when 0004 arrives was live once: it gets a `published_at`, which is what a
    rollback to it shows; a draft gets none."""
    migrate.upgrade(blank.url, "0003_store_revision_published")
    con = dbtest.connect(blank)
    try:
        ins = lambda i, version, status, at: con.execute(  # noqa: E731
            "insert into awp_profiles (id, tenant, key, version, status, data, created_at) values (?, 'ta', 'desk', ?, ?, '{}', ?)",
            (i, version, status, at))
        ins("p1", 1, "retired", 100.5)
        ins("p2", 2, "published", 200.25)
        ins("p3", 3, "draft", 300.0)
        new = {"awp_profile_events", "awp_builder_sessions", "awp_eval_cases", "awp_eval_runs"}
        assert not new & con.tables()
        migrate.upgrade(blank.url)
        assert new <= con.tables()
        assert con.execute("select id, published_at, published_by from awp_profiles order by id") == [
            ("p1", 100.5, None), ("p2", 200.25, None), ("p3", None, None)]
        con.execute("insert into awp_eval_cases (id, tenant, key, name, input, fixtures, checks, created_at, updated_at) "
                    "values ('c1', 'ta', 'desk', 'n', 'i', '{}', '{}', 1, 1)")
        with pytest.raises(dbtest.IntegrityError):  # one name per profile key of a tenant
            con.execute("insert into awp_eval_cases (id, tenant, key, name, input, fixtures, checks, created_at, updated_at) "
                        "values ('c2', 'ta', 'desk', 'n', 'i', '{}', '{}', 1, 1)")
        assert migrate.drift(blank.url) == []
        migrate.downgrade(blank.url, "0003_store_revision_published")
        assert not new & con.tables() and "published_at" not in con.columns("awp_profiles")
        assert con.execute("select id, status from awp_profiles order by id") == [("p1", "retired"), ("p2", "published"), ("p3", "draft")]
    finally:
        con.close()


def test_revision_0005_gives_every_key_one_holder_and_ends_the_runs_nobody_runs(blank):
    """Keys that exist get their holder: the tenant whose version is live, else one with a draft, else one with retired
    versions only. A run that says `running` during an upgrade has no process; ending it makes room for the index that
    allows one running run per version."""
    migrate.upgrade(blank.url, "0004_builder_evals_release")
    con = dbtest.connect(blank)
    try:
        ins = lambda i, tenant, key, status: con.execute(  # noqa: E731
            "insert into awp_profiles (id, tenant, key, version, status, data, created_at) values (?, ?, ?, 1, ?, '{}', 1)",
            (i, tenant, key, status))
        ins("p1", "tb", "desk", "published")  # live for tb, and (the old race) a draft of ta's: the live one holds it
        ins("p2", "ta", "desk", "draft")
        ins("p3", "tb", "tech", "retired")  # retired for tb, a draft for ta: ta's
        ins("p4", "ta", "tech", "draft")
        ins("p5", "tb", "old", "retired")  # only retired versions: still somebody's until another tenant takes it
        run = lambda i, status: con.execute(  # noqa: E731
            "insert into awp_eval_runs (id, tenant, key, version, profile_hash, status, results, cost_usd, started_by, deadline, "
            "created_at) values (?, 'ta', 'tech', 1, 'h', ?, '[]', 0, 'a', 9e9, 1)", (i, status))
        run("r1", "running")
        run("r2", "running")  # two at once: what the missing index allowed
        run("r3", "passed")
        migrate.upgrade(blank.url)
        assert con.execute("select key, tenant from awp_profile_keys order by key") == [("desk", "tb"), ("old", "tb"), ("tech", "ta")]
        assert con.execute("select id, status, cases_hash from awp_eval_runs order by id") == [
            ("r1", "error", None), ("r2", "error", None), ("r3", "passed", None)]
        run("r4", "running")
        with pytest.raises(dbtest.IntegrityError):
            run("r5", "running")
        with pytest.raises(dbtest.IntegrityError):
            con.execute("insert into awp_profile_keys (key, tenant) values ('desk', 'ta')")
        assert migrate.drift(blank.url) == []
        migrate.downgrade(blank.url, "0004_builder_evals_release")
        assert "awp_profile_keys" not in con.tables() and "cases_hash" not in con.columns("awp_eval_runs")
        run("r5", "running")  # the index went with the revision
    finally:
        con.close()


def test_the_guard_can_fail(blank):
    migrate.upgrade(blank.url)
    con = dbtest.connect(blank)
    try:
        con.execute("alter table wf_jobs add column stray text")
        con.execute("create index ix_stray on wf_jobs (kind, status)")
    finally:
        con.close()
    found = " ".join(map(str, migrate.drift(blank.url)))
    assert "stray" in found and "ix_stray" in found
    assert any("differs from the models" in p for p in migrate.check(blank.url))


def test_check_names_a_database_that_is_not_at_head(blank):
    problems = migrate.check(blank.url)
    assert problems and "python -m awp migrate" in problems[0]


def test_stamp_adopts_a_database_that_create_all_built_and_refuses_one_that_differs(tmp_path):
    db = dbtest.empty(tmp_path, "adopt.db")

    async def build():
        d = Database(db.url)
        await d.create_all()
        await d.dispose()

    asyncio.run(build())
    assert asyncio.run(migrate.current(db.url)) is None
    migrate.stamp(db.url)
    assert migrate.check(db.url) == []
    other = dbtest.empty(tmp_path, "adopt2.db")
    asyncio.run(_partial(other))
    with pytest.raises(RuntimeError, match="cannot stamp"):
        migrate.stamp(other.url)


async def _partial(db):
    d = Database(db.url)
    async with d.engine.begin() as conn:
        await conn.run_sync(lambda c: metadata.tables["wf_clients"].create(c))
    await d.dispose()


# ---- the command line --------------------------------------------------------------------------------------------------
def run_cli(monkeypatch, db, *argv):
    from awp import __main__ as cli

    monkeypatch.setenv("AWP_DB_URL", db.url)
    return cli.main(["migrate", *argv])


def test_the_command_migrates_checks_and_reports(blank, monkeypatch, capsys):
    with pytest.raises(SystemExit) as bad:
        run_cli(monkeypatch, blank, "--check")  # nothing migrated yet
    assert bad.value.code == 1 and "python -m awp migrate" in capsys.readouterr().err
    assert run_cli(monkeypatch, blank) == 0
    assert tables_of(blank) == MODEL_TABLES | {"awp_alembic_version"}
    assert run_cli(monkeypatch, blank, "--check") == 0
    assert "up to date" in capsys.readouterr().out


def test_the_command_can_also_bring_agentscopes_storage_to_head(tmp_path, monkeypatch):
    db = dbtest.empty(tmp_path, "storage.db")
    monkeypatch.setenv("AWP_AGENTSCOPE_DB_URL", db.url)
    assert run_cli(monkeypatch, dbtest.empty(tmp_path, "awp.db"), "--storage") == 0
    have = tables_of(db)
    assert {"agents", "sessions", "alembic_version"} <= have  # AgentScope's tables and AgentScope's own history


def test_both_histories_can_live_in_one_database(tmp_path, monkeypatch):
    """The awp version table has its own name, so the two schemas may share a database."""
    db = dbtest.empty(tmp_path, "shared.db")
    monkeypatch.setenv("AWP_AGENTSCOPE_DB_URL", db.url)
    assert run_cli(monkeypatch, db, "--storage") == 0
    assert migrate.check(db.url) == []
    assert {"awp_alembic_version", "alembic_version", "agents", "wf_workflows"} <= tables_of(db)


# ---- AWP_AUTO_CREATE ---------------------------------------------------------------------------------------------------
def start(tmp_path, awp, scope, **over):
    from fastapi.testclient import TestClient

    app = build_app(Settings(db_url=awp.url, agentscope_db_url=scope.url, workspace_dir=str(tmp_path / "ws"),
                             admin_keys={"k": "ta"}, **over), catalog=ModelCatalog([]))
    with TestClient(app):
        pass


def test_auto_create_is_on_by_default_and_makes_the_tables(tmp_path):
    awp, scope = dbtest.empty(tmp_path, "a.db"), dbtest.empty(tmp_path, "s.db")
    assert Settings().auto_create is True and Settings.from_env({"AWP_AUTO_CREATE": "0"}).auto_create is False
    start(tmp_path, awp, scope)
    assert MODEL_TABLES <= tables_of(awp)


def test_without_auto_create_the_app_refuses_a_database_that_is_not_at_head(tmp_path):
    awp, scope = dbtest.empty(tmp_path, "a.db"), dbtest.empty(tmp_path, "s.db")
    with pytest.raises(RuntimeError, match="python -m awp migrate"):
        start(tmp_path, awp, scope, auto_create=False)
    assert not (MODEL_TABLES & tables_of(awp))  # and it made nothing


def test_without_auto_create_a_migrated_database_starts_and_is_left_alone(tmp_path):
    awp, scope = dbtest.empty(tmp_path, "a.db"), dbtest.empty(tmp_path, "s.db")
    migrate.upgrade(awp.url)
    migrate.upgrade_storage(scope.url)  # AgentScope's tables are made by its own scripts too
    start(tmp_path, awp, scope, auto_create=False)
    assert migrate.check(awp.url) == []
