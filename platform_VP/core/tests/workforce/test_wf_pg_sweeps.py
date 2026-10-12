"""On PostgreSQL the sweeps and the engine's claim do not queue behind a conversation somebody else is working on
(`FOR UPDATE SKIP LOCKED`): they pass it by and come back, holding no connection meanwhile."""
from __future__ import annotations

import asyncio
import time

import consentkit as ck
import pytest
from enginekit import world
from test_wf_s4_flow import TOOLS, _clean, trip  # noqa: F401 - _clean is an autouse fixture

import dbtest

pytestmark = pytest.mark.skipif(not dbtest.IS_PG, reason="SKIP LOCKED is PostgreSQL's; SQLite has one writer for the whole file")


def test_the_expiry_sweep_passes_by_a_locked_conversation_and_expires_the_approval_when_it_is_free(tmp_path):
    with world(tmp_path, ck.trip, sweep_every=3600, **TOOLS) as w:
        f = w.flow
        start, first, second = trip(w)
        conv = first["conversation_id"]
        [appr] = f.approvals(conv)
        w.sql("update wf_approvals set expires_at=?", (time.time() - 5,))
        holder = w.env.raw()  # a reply, say, in the middle of its transaction
        try:
            holder.execute("begin")
            holder.execute("select id from wf_conversations where id = ? for update", (conv,))
            started = time.monotonic()
            w.run(lambda: asyncio.wait_for(w.engine.sweep(), 30))  # would wait for ever if it queued behind the lock
            assert time.monotonic() - started < 15
            assert w.sql("select status from wf_approvals where id=?", (appr["approval_id"],)) == [("pending",)]
        finally:
            holder.execute("commit")
            holder.close()
        w.run(w.engine.sweep)
        assert w.sql("select status from wf_approvals where id=?", (appr["approval_id"],)) == [("expired",)]
