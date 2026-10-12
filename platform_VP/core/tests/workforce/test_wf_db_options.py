"""The database settings: pool sizing for PostgreSQL, the new environment variables, the retention warning."""
import logging

from awp.config import Settings
from awp.db import Database, engine_options
from awp.workforce import retention
from dbkit import Lab


def test_postgres_gets_a_sized_pinged_pool_with_an_explicit_isolation_level_and_sqlite_gets_nothing_extra():
    opts = engine_options("postgresql+asyncpg://u:p@h/db", pool_size=3, max_overflow=4, pool_timeout=5.0, pool_recycle=60.0)
    assert opts == {"pool_size": 3, "max_overflow": 4, "pool_timeout": 5.0, "pool_recycle": 60.0, "pool_pre_ping": True,
                    "isolation_level": "READ COMMITTED"}
    assert engine_options("sqlite+aiosqlite:///x.db", pool_size=3) == {}


def test_the_pool_settings_reach_the_engine_of_a_postgres_url():
    db = Database("postgresql+asyncpg://u:p@127.0.0.1:1/db", pool_size=3, max_overflow=4, pool_timeout=5.0, pool_recycle=60.0)
    pool = db.engine.pool
    assert (pool.size(), pool._max_overflow, pool._timeout, pool._recycle) == (3, 4, 5.0, 60.0)
    assert db.engine.dialect.name == db.dialect == "postgresql"


def test_the_environment_sets_the_new_options_and_zero_is_a_value_not_a_default():
    s = Settings.from_env({})
    assert (s.auto_create, s.db_pool_size, s.db_max_overflow, s.db_pool_timeout, s.db_pool_recycle) == (True, 10, 20, 30.0, 1800.0)
    assert (s.closed_retention_days, s.retention_every_seconds) == (90, 3600.0)
    e = Settings.from_env({"AWP_AUTO_CREATE": "0", "AWP_DB_POOL_SIZE": "4", "AWP_DB_MAX_OVERFLOW": "6", "AWP_DB_POOL_TIMEOUT": "7",
                           "AWP_DB_POOL_RECYCLE": "90", "AWP_CLOSED_RETENTION_DAYS": "0", "AWP_RETENTION_EVERY_SECONDS": "0",
                           "AWP_EVENT_RETENTION_DAYS": "0"})
    assert (e.auto_create, e.db_pool_size, e.db_max_overflow, e.db_pool_timeout, e.db_pool_recycle) == (False, 4, 6, 7.0, 90.0)
    assert (e.closed_retention_days, e.retention_every_seconds, e.event_retention_days) == (0, 0.0, 0)
    assert Settings.from_env({"AWP_AUTO_CREATE": "true"}).auto_create is True


def test_a_period_below_the_contract_minimum_is_warned_about_but_honoured(caplog):
    with caplog.at_level(logging.WARNING, logger="awp.workforce"):
        retention.warn_if_short(Settings(event_retention_days=30, inbox_retention_days=10))
    text = caplog.text
    assert "AWP_EVENT_RETENTION_DAYS=30" in text and "AWP_INBOX_RETENTION_DAYS=10" in text
    caplog.clear()
    with caplog.at_level(logging.WARNING, logger="awp.workforce"):
        retention.warn_if_short(Settings())
        retention.warn_if_short(Settings(event_retention_days=0, inbox_retention_days=0))  # off is not "short"
    assert caplog.text == ""


def test_a_claim_that_may_not_wait_still_works_where_the_database_has_one_writer(tmp_path):
    from awp.workforce import tables as t
    from awp.workforce.engine import claim_job
    from awp.workforce.events import lock_conversation

    lab = Lab(tmp_path / "wait.db")
    try:
        seeded = lab.seed()

        async def go():
            async with lab.db.engine.begin() as conn:
                assert await lock_conversation(conn, seeded["conv"]["id"], wait=False) is True
                await conn.execute(t.jobs.insert().values(id="job_w", workflow_id=seeded["wf"]["id"], kind="nudge", payload={},
                                                          status="queued", attempts=0, created_at=1.0))
            async with lab.db.engine.begin() as conn:
                return await claim_job(conn, "job_w", wait=False)
        assert lab.run(go())["status"] == "dispatched"
    finally:
        lab.close()
