"""Policy reads must not serialize every user of a shared role/group."""

import asyncio

import pytest
from sqlalchemy import event
from sqlalchemy.dialects import postgresql

from vin_fixtures import authority as authority, seed_policy_catalog  # noqa: F401


@pytest.mark.asyncio
async def test_shared_policy_selects_do_not_request_exclusive_row_locks(authority):
    alice = await seed_policy_catalog(authority)
    bob = await authority.context("bob")
    policy_selects = []
    def observe(conn, clause, multiparams, params, options):
        if getattr(clause, "is_select", False):
            sql = str(clause.compile(dialect=postgresql.dialect()))
            if "vin_quota_policies" in sql:
                policy_selects.append(sql)
    event.listen(authority.engine.sync_engine, "before_execute", observe)
    try:
        ids = await asyncio.gather(*[authority.quota.reserve(context, budget=100, purpose="chat", model="test-model")
            for context in (alice, bob)])
        assert len(set(ids)) == 2
        assert policy_selects and all("FOR UPDATE" not in sql for sql in policy_selects)
    finally:
        event.remove(authority.engine.sync_engine, "before_execute", observe)
