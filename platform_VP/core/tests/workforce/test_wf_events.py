"""The event log: sequence allocation, envelope, history, cursors, retention (contract 9.5-9.7, 12)."""
import asyncio
import time

import pytest
from sqlalchemy import insert, select, update

from awp.workforce import tables as t
from awp.workforce.errors import WorkforceError
from awp.workforce.events import PUBLIC, emit, history, last_event_id, public_event, resolve_cursor
from awp.workforce.retention import DAY, purge_events
from dbkit import Lab


@pytest.fixture
def lab(tmp_path):
    lab = Lab(tmp_path / "lab.db")
    yield lab
    lab.close()


async def _emit_n(lab, conv, n, kind="workflow.status_changed", wf=None):
    for i in range(n):
        async with lab.db.engine.begin() as conn:
            await emit(conn, conv["id"], kind, {"i": i}, workflow=wf)


async def _conv_row(lab, cid):
    async with lab.db.engine.connect() as conn:
        return (await conn.execute(select(t.conversations).where(t.conversations.c.id == cid))).mappings().one()


async def _last(lab, cid):
    async with lab.db.engine.connect() as conn:
        return await last_event_id(conn, cid)


def test_emit_numbers_events_from_one_and_builds_the_public_envelope(lab):
    s = lab.seed()
    conv, wf = s["conv"], s["wf"]

    async def go():
        async with lab.db.engine.begin() as conn:
            a = await emit(conn, conv["id"], "request.accepted", {"request_id": "req_1"}, workflow=wf)
            b = await emit(conn, conv["id"], "assistant.message", {"message_id": "msg_1", "text": "hi"},
                           workflow={**wf, "ticket_id": "tkt_9"})
        return a, b

    a, b = lab.run(go())
    assert (a.sequence, b.sequence) == (1, 2)
    assert a.event_id.startswith("evt_") and len(a.event_id) == 36 and a.event_id != b.event_id
    row = lab.one(t.events, event_id=b.event_id)
    env = public_event(row, lab.one(t.conversations, id=conv["id"]))
    assert list(env) == ["schema_version", "event_id", "sequence", "event_type", "occurred_at", "recorded_at",
                         "conversation_id", "external_ticket_id", "external_conversation_id",
                         "external_user_id", "workflow_id", "ticket_id", "payload"]
    assert env["schema_version"] == "1" and env["sequence"] == 2 and env["ticket_id"] == "tkt_9"
    assert env["external_ticket_id"] == conv["external_ticket_id"]
    assert env["external_conversation_id"] == conv["external_conversation_id"]
    assert env["external_user_id"] == "resident-1" and env["workflow_id"] == wf["id"]
    assert env["payload"] == {"message_id": "msg_1", "text": "hi"}
    assert env["occurred_at"].endswith("Z") and env["recorded_at"].endswith("Z")
    assert lab.one(t.conversations, id=conv["id"])["last_sequence"] == 2


def test_only_the_public_event_types_can_be_emitted(lab):
    s = lab.seed()
    assert len(PUBLIC) == 11

    async def go():
        async with lab.db.engine.begin() as conn:
            await emit(conn, s["conv"]["id"], "internal.debug", {})

    with pytest.raises(ValueError):
        lab.run(go())
    assert lab.rows(t.events) == []


def test_a_hundred_concurrent_writers_get_strictly_increasing_gap_free_sequences(lab):
    s = lab.seed()

    async def one(i):
        async with lab.db.engine.begin() as conn:
            ev = await emit(conn, s["conv"]["id"], "workflow.status_changed", {"i": i})
            if i % 7 == 3:  # a writer that fails after taking a number gives it back
                raise RuntimeError("boom")
        return ev.sequence

    async def go():
        return await asyncio.gather(*(one(i) for i in range(100)), return_exceptions=True)

    out = lab.run(go())
    good = sorted(x for x in out if isinstance(x, int))
    assert len(good) == 100 - len([i for i in range(100) if i % 7 == 3])
    assert good == list(range(1, len(good) + 1))
    stored = [r["sequence"] for r in sorted(lab.rows(t.events), key=lambda r: r["sequence"])]
    assert stored == good
    assert lab.one(t.conversations, id=s["conv"]["id"])["last_sequence"] == len(good)


def test_commit_order_is_sequence_order_with_many_events_per_transaction(lab):
    s = lab.seed()

    async def one(i):
        async with lab.db.engine.begin() as conn:
            for j in range(3):
                await emit(conn, s["conv"]["id"], "workflow.status_changed", {"i": i, "j": j})

    async def go():
        await asyncio.gather(*(one(i) for i in range(20)))

    lab.run(go())
    rows = sorted(lab.rows(t.events), key=lambda r: r["sequence"])
    assert [r["sequence"] for r in rows] == list(range(1, 61))
    for k in range(0, 60, 3):  # one transaction's three events are neighbours
        assert len({r["payload"]["i"] for r in rows[k:k + 3]}) == 1


def test_history_pages_with_next_cursor_and_has_more(lab):
    s = lab.seed()
    conv = s["conv"]
    lab.run(_emit_n(lab, conv, 7))

    async def pages():
        out, cursor = [], None
        while True:
            row = await _conv_row(lab, conv["id"])
            async with lab.db.engine.connect() as conn:
                page = await history(conn, row, cursor, 3)
            out.append(page)
            if not page["has_more"]:
                return out
            cursor = page["next_cursor"]

    out = lab.run(pages())
    assert [len(p["items"]) for p in out] == [3, 3, 1]
    assert [p["has_more"] for p in out] == [True, True, False]
    assert [i["sequence"] for p in out for i in p["items"]] == list(range(1, 8))
    assert out[0]["next_cursor"] == out[0]["items"][-1]["event_id"]


def test_history_with_nothing_new_echoes_the_cursor(lab):
    s = lab.seed()
    lab.run(_emit_n(lab, s["conv"], 2))
    last = lab.run(_last(lab, s["conv"]["id"]))

    async def go():
        row = await _conv_row(lab, s["conv"]["id"])
        async with lab.db.engine.connect() as conn:
            return await history(conn, row, last, 100)

    assert lab.run(go()) == {"items": [], "next_cursor": last, "has_more": False}


def test_a_cursor_is_found_by_id_never_by_comparing_ids(lab):
    s = lab.seed()
    cid = s["conv"]["id"]
    ids = ["evt_zzzz", "evt_aaaa", "evt_mmmm"]  # string order is the opposite of log order

    async def go():
        async with lab.db.engine.begin() as conn:
            for n, eid in enumerate(ids, 1):
                await conn.execute(insert(t.events).values(
                    event_id=eid, conversation_id=cid, sequence=n, event_type="workflow.status_changed",
                    payload={}, occurred_at=1.0, recorded_at=1.0))
            await conn.execute(update(t.conversations).where(t.conversations.c.id == cid).values(last_sequence=3))
        row = await _conv_row(lab, cid)
        async with lab.db.engine.connect() as conn:
            return [i["event_id"] for i in (await history(conn, row, "evt_zzzz", 100))["items"]]

    assert lab.run(go()) == ["evt_aaaa", "evt_mmmm"]


def test_foreign_and_unknown_cursors_are_the_same_422(lab):
    a, b = lab.seed(), lab.seed()
    lab.run(_emit_n(lab, a["conv"], 1))
    lab.run(_emit_n(lab, b["conv"], 1))
    foreign = lab.rows(t.events, conversation_id=b["conv"]["id"])[0]["event_id"]

    async def attempt(cursor):
        row = await _conv_row(lab, a["conv"]["id"])
        async with lab.db.engine.connect() as conn:
            return await resolve_cursor(conn, row, cursor)

    errs = []
    for cursor in (foreign, "evt_nothing"):
        with pytest.raises(WorkforceError) as e:
            lab.run(attempt(cursor))
        errs.append((e.value.http, e.value.code, e.value.details))
    assert errs[0] == errs[1] and errs[0][:2] == (422, "VALIDATION_FAILED")


def _age(lab, cid, days):
    async def go():
        async with lab.db.engine.begin() as conn:
            await conn.execute(update(t.events).where(t.events.c.conversation_id == cid).values(
                recorded_at=time.time() - days * DAY, occurred_at=time.time() - days * DAY))
    lab.run(go())


def test_purge_drops_old_events_of_closed_workflows_and_leaves_tombstones(lab):
    s = lab.seed(state="closed", closed_at=time.time() - 100 * DAY)
    cid = s["conv"]["id"]
    lab.run(_emit_n(lab, s["conv"], 6))
    _age(lab, cid, 100)
    ids = [r["event_id"] for r in sorted(lab.rows(t.events), key=lambda r: r["sequence"])]

    assert lab.run(purge_events(lab.db, 90)) == {"conversations": 1, "events": 5}
    assert [r["event_id"] for r in lab.rows(t.events)] == [ids[-1]]  # the newest stays as the anchor
    assert sorted(r["event_id"] for r in lab.rows(t.event_tombstones)) == sorted(ids[:5])
    assert lab.one(t.conversations, id=cid)["purged_through"] == 5
    assert lab.run(purge_events(lab.db, 90)) == {"conversations": 0, "events": 0}  # nothing left to do

    async def attempt(cursor):
        row = await _conv_row(lab, cid)
        async with lab.db.engine.connect() as conn:
            return await history(conn, row, cursor, 100)

    for cursor in (ids[0], ids[4], None):  # a purged cursor, and "from the start"
        with pytest.raises(WorkforceError) as e:
            lab.run(attempt(cursor))
        assert (e.value.http, e.value.code) == (410, "EVENT_CURSOR_EXPIRED")
        assert e.value.details["snapshot_url"] == f"/workforce/v1/partner/conversations/{cid}"
    page = lab.run(attempt(ids[-1]))  # the anchor still resumes
    assert page["items"] == [] and page["next_cursor"] == ids[-1]


def test_purge_never_touches_open_workflows_or_recent_closes(lab):
    open_ = lab.seed(state="waiting_external_event")
    recent = lab.seed(state="closed", closed_at=time.time() - 10 * DAY)
    for s in (open_, recent):
        lab.run(_emit_n(lab, s["conv"], 4))
        _age(lab, s["conv"]["id"], 400)  # old events, but the workflow is open / closed recently
    assert lab.run(purge_events(lab.db, 90)) == {"conversations": 0, "events": 0}
    assert len(lab.rows(t.events)) == 8 and lab.rows(t.event_tombstones) == []


def test_purge_keeps_events_newer_than_the_window_in_an_old_conversation(lab):
    s = lab.seed(state="closed", closed_at=time.time() - 100 * DAY)
    cid = s["conv"]["id"]
    lab.run(_emit_n(lab, s["conv"], 6))

    async def old_head():  # events 1-3 are old; 4-6 are inside the window (e.g. a late provider event)
        async with lab.db.engine.begin() as conn:
            await conn.execute(update(t.events).where(t.events.c.sequence <= 3).values(
                recorded_at=time.time() - 100 * DAY))
    lab.run(old_head())
    assert lab.run(purge_events(lab.db, 90)) == {"conversations": 1, "events": 3}
    assert sorted(r["sequence"] for r in lab.rows(t.events)) == [4, 5, 6]
    assert lab.one(t.conversations, id=cid)["purged_through"] == 3
