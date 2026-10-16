"""Fixes after the S2 review, concurrency: one lock order for every writer, no torn snapshot, no
spurious 503 for valid replies, deterministic idempotency between twins, claim_job under a busy workflow."""
import asyncio
import json
import random
import re
import threading
import time
import uuid
from collections import Counter
from concurrent.futures import ThreadPoolExecutor

import pytest
from sqlalchemy import event, insert

from conftest import build, build_live, _flow, _wire_engine
from dbkit import Lab
from fake_engine import Plan
from test_wf_errors import assert_envelope

from awp.workforce import tables as t
from awp.workforce.engine import claim_job, finish_job
from awp.workforce.events import lock_conversation
from awp.workforce.workflows import StateConflict, retryable


def code(r):
    return (r.status_code, r.json().get("error", {}).get("code") if r.status_code >= 400 else "")


def par(fns):
    with ThreadPoolExecutor(len(fns)) as ex:
        return [f.result() for f in [ex.submit(f) for f in fns]]


# ---- one lock order ---------------------------------------------------------------------------
# the row locks: an UPDATE of either row, or (PostgreSQL's lock_conversation) a SELECT ... FOR UPDATE of the conversation
LOCKS = re.compile(r"^\s*(?:UPDATE (wf_conversations|wf_workflows)\b|SELECT .*?\s+FROM (wf_conversations)\b.*\bFOR UPDATE)",
                   re.I | re.S)


def record(env):
    log = []

    @event.listens_for(env.app.state.wf.db.engine.sync_engine, "before_cursor_execute")
    def _(conn, cursor, statement, params, context, executemany):
        m = LOCKS.match(statement)
        if m:
            log.append(m.group(1) or m.group(2))
    return log


def first_order(log):
    seen = []
    for x in log:
        if x not in seen:
            seen.append(x)
    return tuple(seen)


def test_every_write_path_locks_the_conversation_before_the_workflow(tmp_path):
    """SQLite has one writer and hides an inversion; on Postgres two writers that take these two rows in
    opposite orders deadlock. The order each path first touches them in must be the same."""
    with build(tmp_path, wire=_wire_engine, wf_wait_seconds=0.5, wf_rate_per_minute=0) as env:
        flow = _flow(env)
        flow.engine.plan = Plan(say=("ok",), state="awaiting_user")
        st, s = flow.begin()
        log = record(env)
        orders = {}

        log.clear()
        assert flow.reply(st, s)[0].status_code == 200  # service and engine turn
        orders["reply"] = first_order(log)

        log.clear()
        flow.engine.plan = Plan(say=("ok",), state="awaiting_confirmation")
        assert flow.reply(st, s)[0].status_code == 200
        wf = flow.get(f"/conversations/{s['conversation_id']}").json()["workflows"][0]
        log.clear()
        r, _ = flow.close(s, st, revision=wf["revision"])
        assert r.status_code == 200, r.text
        orders["close"] = first_order(log)

        st2, s2 = flow.begin()  # a workflow whose route is suspended: the reply blocks it
        assert env.post(f"/platform/v1/wf/routes/{flow.route['route_id']}/suspend").status_code == 200
        log.clear()
        assert flow.reply(st2, s2)[0].status_code == 403
        orders["block"] = first_order(log)
        assert set(orders.values()) == {("wf_conversations", "wf_workflows")}, orders


def test_the_engine_claim_takes_the_conversation_lock_first(tmp_path):
    lab = Lab(tmp_path / "x.db")
    try:
        wid = lab.seed()["wf"]["id"]
        log = []

        @event.listens_for(lab.db.engine.sync_engine, "before_cursor_execute")
        def _(conn, cursor, statement, params, context, executemany):
            m = LOCKS.match(statement) or re.match(r"^\s*UPDATE (wf_jobs)\b", statement, re.I)
            if m:
                log.append(m.group(1) or m.group(2))

        async def go():
            async with lab.db.engine.begin() as c:
                await c.execute(insert(t.jobs).values(id="job_a", workflow_id=wid, kind="resident_message",
                                                      status="queued", payload={}, attempts=0, created_at=1.0))
            async with lab.db.engine.begin() as c:
                return await claim_job(c, "job_a")
        assert lab.run(go()) is not None
        assert log[:2] == ["wf_conversations", "wf_jobs"], log
    finally:
        lab.close()


def test_locking_a_conversation_that_does_not_exist_is_an_error(tmp_path):
    lab = Lab(tmp_path / "x.db")
    try:
        async def go():
            async with lab.db.engine.begin() as c:
                await lock_conversation(c, "conv_nope")
        with pytest.raises(LookupError):
            lab.run(go())
    finally:
        lab.close()


# ---- claim_job ---------------------------------------------------------------------------------
def test_a_job_of_a_workflow_with_a_dispatched_job_is_not_claimed_and_is_later(tmp_path):
    lab = Lab(tmp_path / "x.db")
    try:
        wid = lab.seed()["wf"]["id"]

        async def go():
            async with lab.db.engine.begin() as c:
                for j in ("job_a", "job_b"):
                    await c.execute(insert(t.jobs).values(id=j, workflow_id=wid, kind="resident_message",
                                                          status="queued", payload={}, attempts=0, created_at=1.0))
            out = []
            async with lab.db.engine.begin() as c:
                out.append(await claim_job(c, "job_a"))
            async with lab.db.engine.begin() as c:
                out.append(await claim_job(c, "job_b"))  # None, not an IntegrityError
            async with lab.db.engine.begin() as c:
                await finish_job(c, "job_a")
            async with lab.db.engine.begin() as c:
                out.append(await claim_job(c, "job_b"))
            async with lab.db.engine.begin() as c:
                out.append(await claim_job(c, "job_b"))  # already dispatched
                out.append(await claim_job(c, "job_unknown"))
            return out
        a, b, b2, again, unknown = lab.run(go())
        assert a is not None and b is None and b2 is not None and b2["attempts"] == 1
        assert again is None and unknown is None
        assert lab.one(t.jobs, id="job_b")["status"] == "dispatched"
    finally:
        lab.close()


# ---- snapshot ----------------------------------------------------------------------------------
def test_a_snapshot_that_cannot_be_read_steadily_is_a_retryable_503_never_a_torn_200(tmp_path, monkeypatch):
    from awp.workforce import reads
    with build(tmp_path, wire=_wire_engine, wf_wait_seconds=0.5, wf_rate_per_minute=0) as env:
        flow = _flow(env)
        flow.engine.plan = Plan(say=("a",), state="awaiting_user")
        st, s = flow.begin()
        cid, wid = s["conversation_id"], s["workflow_id"]
        real = reads.last_event_id

        def late():
            con = env.raw()
            try:
                seq = con.execute("update wf_conversations set last_sequence=last_sequence+1 where id=? "
                                  "returning last_sequence", (cid,))[0][0]
                mid, now = "msg_" + uuid.uuid4().hex, time.time()
                con.execute("insert into wf_events(event_id,conversation_id,sequence,event_type,workflow_id,payload,"
                            "occurred_at,recorded_at) values(?,?,?,?,?,?,?,?)",
                            ("evt_" + uuid.uuid4().hex, cid, seq, "assistant.message", wid,
                             json.dumps({"message_id": mid, "text": "late"}), now, now))
                con.execute("insert into wf_messages(id,conversation_id,workflow_id,sender,text,asset_ids,sequence,"
                            "created_at) values(?,?,?,?,?,?,?,?)",
                            (mid, cid, wid, "assistant", "late", "[]", seq, now))
            finally:
                con.close()

        async def writer_then_read(conn, conversation_id):
            # a committed assistant message lands between the data reads and the cursor read, every time. Written from a
            # worker thread: a synchronous write here would hold the app's loop still (conftest.just_before says why)
            await asyncio.to_thread(late)
            return await real(conn, conversation_id)

        monkeypatch.setattr(reads, "last_event_id", writer_then_read)
        err = assert_envelope(flow.snapshot(cid), 503, "INTERNAL_ERROR")
        assert err["retryable"] is True
        monkeypatch.setattr(reads, "last_event_id", real)
        snap = flow.snapshot(cid).json()  # quiet again: a whole picture
        hist = flow.history(cid, limit=500).json()["items"]
        assert snap["snapshot_cursor"] == hist[-1]["event_id"]
        assert hist[-1]["payload"]["message_id"] in {m["message_id"] for m in snap["messages"]}


# ---- valid replies are not refused for an internal race -------------------------------------------------
@pytest.mark.slow
def test_a_burst_of_replies_to_one_chat_is_never_a_5xx(tmp_path):
    with build_live(tmp_path, wire=_wire_engine, wf_wait_seconds=0.3, wf_rate_per_minute=0) as env:
        flow = _flow(env)
        flow.engine.plan = Plan(say=("ok",), state="awaiting_user", delay=0.0)
        st, s = flow.begin()
        total = Counter()
        for _ in range(8):
            bodies = [flow.reply_body(s, st) for _ in range(12)]
            with ThreadPoolExecutor(12) as ex:
                total.update(code(r) for r in ex.map(flow.post, bodies))
        assert not [k for k in total if k[0] >= 500], total
        assert sum(total.values()) == 96 and not flow.engine.errors


def test_twins_with_the_same_id_and_another_body_always_meet_idempotency_conflict(tmp_path):
    with build(tmp_path, wire=_wire_engine, wf_wait_seconds=0.2, wf_rate_per_minute=0) as env:
        flow = _flow(env)
        seen = Counter()
        for i in range(24):
            for kind in ("text", "ticket"):  # another text, or another ticket on the same chat
                a = flow.start_body(external_request_id=f"same-{kind}-{i}", external_ticket_id=f"T{kind}{i}",
                                    external_conversation_id=f"C{kind}{i}")
                b = (dict(a, message={"type": "text", "text": "different"}) if kind == "text"
                     else dict(a, external_ticket_id=f"T{kind}{i}b"))
                ra, rb = par([lambda: flow.post(a), lambda: flow.post(b)])
                seen[tuple(sorted([code(ra), code(rb)]))] += 1
        assert all(k[1] == (409, "IDEMPOTENCY_CONFLICT") and k[0][0] < 400 for k in seen), seen


# ---- chaos: replies, replays, closes and reads at once, then the invariants of the database ------------
def invariants(env):
    q, out = env.sql, []
    for cid, last in q("select id,last_sequence from wf_conversations"):
        seqs = [r[0] for r in q("select sequence from wf_events where conversation_id=? order by sequence", (cid,))]
        if seqs != list(range(1, last + 1)):
            out.append(("sequence gap", cid, last))
        kinds = [r[0] for r in q("select event_type from wf_events where conversation_id=? order by sequence", (cid,))]
        if "workflow.closed" in kinds and (kinds.count("workflow.closed") != 1
                                           or kinds.index("workflow.closed") != len(kinds) - 1):
            out.append(("event after close or closed twice", cid, kinds[-4:]))
    for (wid,) in q("select id from wf_workflows where state='closed'"):
        if q("select 1 from wf_jobs where workflow_id=? and status in ('queued','dispatched')", (wid,)) or q(
                "select 1 from wf_requests where workflow_id=? and status in ('accepted','queued','running')", (wid,)):
            out.append(("closed but open work", wid))
    if q("select 1 from wf_requests group by client_id, external_request_id having count(*) > 1"):
        out.append("duplicate request ids")
    if q("select 1 from wf_jobs group by request_id having count(*) > 1"):
        out.append("two jobs for one request")
    for wid, rev in q("select id,revision from wf_workflows"):
        n = q("select count(*) from wf_events where workflow_id=? and event_type in ('workflow.status_changed',"
              "'workflow.awaiting_user','workflow.needs_attention','workflow.closed')", (wid,))[0][0]
        if rev != 1 + n:
            out.append(("revision vs events", wid, rev, n))
    return out


def test_concurrent_replies_closes_and_replays_leave_a_coherent_database(tmp_path):
    with build(tmp_path, wire=_wire_engine, wf_wait_seconds=0.3, wf_rate_per_minute=0) as env:
        flow = _flow(env)
        flow.engine.plan = Plan(say=("ok",), state="awaiting_user", delay=0.02)
        wfs = [(s, st) for st, s in (flow.begin() for _ in range(4))]
        results, lock, sent = Counter(), threading.Lock(), []

        def worker(i):
            rnd = random.Random(i)
            for _ in range(15):
                s, st = rnd.choice(wfs)
                k = rnd.random()
                if k < 0.5:
                    r, body = flow.reply(st, s)
                    sent.append(body)
                elif k < 0.7 and sent:
                    r = flow.post(rnd.choice(sent))
                elif k < 0.74:
                    rev = flow.get(f"/conversations/{s['conversation_id']}").json()["workflows"][0]["revision"]
                    r, _ = flow.close(s, st, revision=rev)
                else:
                    r = flow.request(s["request_id"])
                with lock:
                    results[code(r)] += 1
        with ThreadPoolExecutor(10) as ex:
            list(ex.map(worker, range(10)))
        assert not [k for k in results if k[0] >= 500], results
        assert invariants(env) == []


# ---- what is worth repeating ---------------------------------------------------------------------------------
def test_only_lost_races_and_database_verdicts_are_retried():
    class Orig(Exception):
        def __init__(self, sqlstate=None):
            self.sqlstate = sqlstate

    class Db(Exception):
        def __init__(self, orig):
            self.orig = orig

    from sqlalchemy.exc import IntegrityError
    assert retryable(StateConflict("wf")) and retryable(IntegrityError("s", {}, Exception("x")))
    assert retryable(Db(Orig("40P01"))) and retryable(Db(Orig("40001")))
    assert not retryable(Db(Orig("23505"))) and not retryable(Db(Orig())) and not retryable(ValueError("x"))
