"""What only a real PostgreSQL can show: deadlocks and serialization failures between two sessions, the lock order that
prevents them, sequence allocation and job claims under real concurrency. Skipped on SQLite (it has one writer, so none of
this can happen there); run with AWP_TEST_PG_URL set (tests/dbtest.py)."""
import asyncio

import pytest
from sqlalchemy import select, text, update
from sqlalchemy.exc import DBAPIError

import dbtest
from awp.workforce import tables as t
from awp.workforce.engine import LockBusy, claim_job
from awp.workforce.events import emit, lock_conversation
from awp.workforce.workflows import retryable
from dbkit import Lab

pytestmark = pytest.mark.skipif(not dbtest.IS_PG, reason="needs a real PostgreSQL server (AWP_TEST_PG_URL)")


@pytest.fixture
def lab(tmp_path):
    lab = Lab(tmp_path / "pg.db")
    yield lab
    lab.close()


def together(lab, coros):
    async def go():
        return await asyncio.gather(*coros)
    return lab.run(go())


def sqlstate(e: BaseException) -> str | None:
    orig = getattr(e, "orig", None)
    return getattr(orig, "sqlstate", None) or getattr(getattr(orig, "__cause__", None), "sqlstate", None)


# ---- a deadlock between two sessions, for real -------------------------------------------------------------------
async def _crossed(lab, first, second):
    """Two transactions take the same two rows in opposite orders. Returns the exceptions (None for the one that won)."""
    a_has, b_has = asyncio.Event(), asyncio.Event()

    async def tx(mine, other, i_have, other_has):
        async with lab.db.engine.begin() as conn:
            await lock(conn, mine)
            i_have.set()
            await other_has.wait()
            await asyncio.sleep(0.2)  # the other one now waits for `mine`: ours is the call that closes the circle
            await lock(conn, other)

    async def lock(conn, cid):
        await conn.execute(update(t.conversations).where(t.conversations.c.id == cid).values(
            last_sequence=t.conversations.c.last_sequence + 1))

    return await asyncio.gather(tx(first, second, a_has, b_has), tx(second, first, b_has, a_has), return_exceptions=True)


def test_a_real_deadlock_is_detected_by_the_database_and_classified_retryable(lab):
    a, b = lab.seed()["conv"]["id"], lab.seed()["conv"]["id"]
    outcome = lab.run(_crossed(lab, a, b))
    lost = [o for o in outcome if isinstance(o, BaseException)]
    assert len(lost) == 1 and sum(o is None for o in outcome) == 1  # one was chosen as the victim, the other went through
    assert isinstance(lost[0], DBAPIError) and sqlstate(lost[0]) == "40P01"
    assert retryable(lost[0])  # the helper that every retry loop of the services calls, on the real exception


def test_a_real_serialization_failure_is_retryable(lab):
    cid = lab.seed()["conv"]["id"]

    async def go():
        async with lab.db.engine.connect() as c1:
            c1 = await c1.execution_options(isolation_level="REPEATABLE READ")
            await c1.execute(select(t.conversations.c.last_sequence).where(t.conversations.c.id == cid))  # the snapshot
            async with lab.db.engine.begin() as c2:  # someone else changes the row and commits
                await c2.execute(update(t.conversations).where(t.conversations.c.id == cid).values(last_sequence=7))
            with pytest.raises(DBAPIError) as e:
                await c1.execute(update(t.conversations).where(t.conversations.c.id == cid).values(last_sequence=9))
            await c1.rollback()
            return e.value

    err = lab.run(go())
    assert sqlstate(err) == "40001" and retryable(err)


def test_ordinary_database_errors_are_not_retryable(lab):
    async def go():
        async with lab.db.engine.connect() as conn:
            with pytest.raises(DBAPIError) as e:
                await conn.execute(text("select 1/0"))
            return e.value

    assert not retryable(lab.run(go()))


# ---- the lock order: conversation first -------------------------------------------------------------------------
async def _writer(lab, conv_id, wf_id, rounds, conversation_first):
    """One write path: the conversation row and the workflow row, in the order given. Returns how many rounds a
    deadlock cost it."""
    lost = 0
    for _ in range(rounds):
        try:
            async with lab.db.engine.begin() as conn:
                await conn.execute(text("set local deadlock_timeout = '50ms'"))  # the server's default waits a second to look
                if conversation_first:
                    await lock_conversation(conn, conv_id)
                await conn.execute(update(t.workflows).where(t.workflows.c.id == wf_id).values(revision=t.workflows.c.revision + 1))
                await asyncio.sleep(0.002)
                await emit(conn, conv_id, "workflow.status_changed", {"state": "active"})  # takes the conversation row
        except DBAPIError as e:
            assert retryable(e) and sqlstate(e) == "40P01"
            lost += 1
    return lost


def test_taking_the_conversation_first_never_deadlocks_and_the_opposite_order_does(lab):
    s = lab.seed()
    cid, wid = s["conv"]["id"], s["wf"]["id"]
    ordered = together(lab, [_writer(lab, cid, wid, 25, True) for _ in range(6)])
    assert sum(ordered) == 0  # the rule of events.lock_conversation, six writers racing 25 rounds each
    # the control: the same writers with half of them touching the workflow first (the order the rule forbids)
    mixed = together(lab, [_writer(lab, cid, wid, 25, i % 2 == 0) for i in range(6)])
    assert sum(mixed) > 0, "the control found no deadlock: this test would pass whatever the order"
    # whoever lost retried nothing here, so the rows hold exactly the rounds that committed
    assert lab.one(t.conversations, id=cid)["last_sequence"] == len(lab.rows(t.events, conversation_id=cid))


# ---- sequence allocation and claims under real concurrency -------------------------------------------------------
def test_sequences_are_dense_and_follow_commit_order_with_forty_concurrent_writers(lab):
    cid = lab.seed()["conv"]["id"]

    async def one(i):
        async with lab.db.engine.begin() as conn:
            return (await emit(conn, cid, "workflow.status_changed", {"i": i})).sequence

    got = together(lab, [one(i) for i in range(40)])
    assert sorted(got) == list(range(1, 41))
    rows = lab.rows(t.events, conversation_id=cid)
    assert sorted(r["sequence"] for r in rows) == list(range(1, 41))


def _job(lab, wid, jid, status="queued", at=1.0):
    async def go():
        async with lab.db.engine.begin() as conn:
            await conn.execute(t.jobs.insert().values(id=jid, workflow_id=wid, kind="resident_message", payload={},
                                                      status=status, attempts=0, created_at=at))
    lab.run(go())


def test_twenty_claims_of_one_job_give_it_to_exactly_one(lab):
    s = lab.seed()
    _job(lab, s["wf"]["id"], "job_a")

    async def claim():
        async with lab.db.engine.begin() as conn:
            return await claim_job(conn, "job_a")

    got = together(lab, [claim() for _ in range(20)])
    assert sum(g is not None for g in got) == 1
    assert lab.one(t.jobs, id="job_a")["status"] == "dispatched" and lab.one(t.jobs, id="job_a")["attempts"] == 1


def test_a_claim_that_must_not_wait_says_busy_while_another_transaction_holds_the_conversation(lab):
    s = lab.seed()
    cid, wid = s["conv"]["id"], s["wf"]["id"]
    _job(lab, wid, "job_b")

    async def go():
        async with lab.db.engine.begin() as holder:
            await lock_conversation(holder, cid)  # a reply, say, in the middle of its transaction
            async with lab.db.engine.begin() as conn:
                with pytest.raises(LockBusy):
                    await claim_job(conn, "job_b", wait=False)
                assert not await lock_conversation(conn, cid, wait=False)  # and so does the bare lock
        async with lab.db.engine.begin() as conn:  # the holder is gone: the same claim goes through
            return await claim_job(conn, "job_b", wait=False)

    assert lab.run(go()) is not None


def test_jobs_of_different_workflows_are_claimed_in_parallel_without_waiting_for_each_other(lab):
    seeds = [lab.seed() for _ in range(8)]
    for i, s in enumerate(seeds):
        _job(lab, s["wf"]["id"], f"job_{i}")

    async def claim(i):
        async with lab.db.engine.begin() as conn:
            return await claim_job(conn, f"job_{i}", wait=False)

    assert all(together(lab, [claim(i) for i in range(8)]))
