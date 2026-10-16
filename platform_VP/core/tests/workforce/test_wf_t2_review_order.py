"""Regression tests for the T2 review, the part about order and load: the order events are applied in, the fair sweep, delta
versions, and the wake-ups that must not cost one model turn per event. (Findings A3, K1, K2, K3, C2, A5, S2, S4.)"""
from __future__ import annotations

import json
import re
import threading
import time
from concurrent.futures import ThreadPoolExecutor
from unittest import mock

import pytest
from conftest import ADM
from enginekit import hold_leader
from partnerkit import Partner
from scripts import say
from t1kit import configure, ops
from t2kit import DELTA, Pending, Provider, pending_world, sent_ok, tools_for, wait_status
from test_wf_t2_apply import DATA, leader_only_notes

from awp.workforce import provider_apply, provider_sweep


@pytest.fixture
def partner():
    with Partner() as p:
        yield p


def told(p) -> list[str]:
    """The integration's own words for the status of the operation, in the order the public log announced them."""
    return [e["payload"]["status"] for e in p.events("operation.status_changed") if "operation_state" in e["payload"]]


def no_tasks():
    """The task each POST starts is lost (the process died after the 202): only the sweep and the applier by hand remain."""
    return mock.patch.object(provider_sweep, "schedule", lambda *a: None)


# ---- A3: events of one operation are applied in the order they were received ------------------------------------------
def test_a_later_event_stands_back_for_an_earlier_one_of_the_same_operation_and_follows_it(tmp_path, partner):
    with pending_world(tmp_path, partner) as (w, prov, p):
        w.quiet()
        with no_tasks():
            first = p.send("x.assigned", version=1, data=DATA)[0]
            second = p.send("x.on_the_way", version=2, data={"eta_minutes": 5})[0]
        ctx = w.engine.ctx
        # the task of the second POST wins the conversation's lock first: it must not apply it ahead of the first
        assert w.run(lambda: provider_apply.apply_receipt(ctx, second, release=False)) == "accepted"
        assert prov.status_of(second) == "accepted" and prov.status_of(first) == "accepted"
        w.run(lambda: provider_apply.apply_receipt(ctx, first))  # the first applies, then lets the one that stood back go
        assert (prov.status_of(first), prov.status_of(second)) == ("applied", "applied")
        assert told(p) == ["assigned", "on_the_way"] and p.op_row()[:2] == ("pending", "on_the_way")


def test_an_earlier_event_that_never_gets_applied_is_not_waited_for_for_ever(tmp_path, partner):
    with pending_world(tmp_path, partner) as (w, prov, p):
        w.quiet()
        with no_tasks():
            first = p.send("x.assigned", version=1, data=DATA)[0]
            second = p.send("x.on_the_way", version=2, data={"eta_minutes": 5})[0]
        w.sql("update wf_provider_inbox set received_at=received_at-?", (provider_apply.ORDER_WAIT + 5,))
        w.run(lambda: provider_apply.apply_receipt(w.engine.ctx, second, release=False))  # the first one is too old to wait for
        assert prov.status_of(second) == "applied"


@pytest.mark.parametrize("run", range(3))
def test_events_sent_one_after_the_other_are_all_applied_in_order(tmp_path, partner, run):
    with pending_world(tmp_path, partner) as (w, prov, p):
        w.quiet()
        rids = [sent_ok(prov, "x.on_the_way", ref=p.ref, version=10 + i, data={"eta_minutes": i})[0] for i in range(12)]
        for rid in rids:
            wait_status(w, prov, rid)
        got = w.sql("select provider_version, ingestion_status from wf_provider_inbox order by provider_version")
        assert [s for _, s in got] == ["applied"] * 12 and p.op_row()[3] == "21"


# ---- K1: the sweep is fair -------------------------------------------------------------------------------------------
def test_events_that_match_nothing_cannot_keep_the_sweep_from_those_that_do(tmp_path, partner):
    with pending_world(tmp_path, partner, wf_rate_per_minute=0, wf_quarantine_max=50) as (w, prov, p):
        w.quiet()
        stranger = Provider(w.env, w.env.client(domain="other", name="Other")["client_id"])
        with no_tasks():
            for i in range(12):  # a flood of valid, signed events about nothing that exists, from two providers
                assert stranger.send("x.on_the_way", ref=f"NOPE-{i}", data={"eta_minutes": 1})[0].status_code == 202
                assert prov.send("x.on_the_way", ref=f"cr_unknown_{i}", data={"eta_minutes": 1})[0].status_code == 202
            rids = [p.send("x.on_the_way", version=v, data={"eta_minutes": v})[0] for v in (1, 2, 3)]  # the real news, newest
        w.run(lambda: provider_sweep.apply_pending(w.engine.ctx, 5))  # a small page: it has to go on to the next ones
        assert [prov.status_of(r) for r in rids] == ["applied"] * 3
        assert w.sql("select count(*) from wf_provider_inbox where ingestion_status='quarantined'") == [(24,)]


def test_one_pass_of_the_sweep_applies_every_event_that_waits_whatever_the_page_size(tmp_path, partner):
    with pending_world(tmp_path, partner) as (w, prov, p):
        w.quiet()
        with no_tasks():
            rids = [p.send("x.on_the_way", version=v, data={"eta_minutes": v})[0] for v in range(1, 13)]
        assert w.run(lambda: provider_sweep.apply_pending(w.engine.ctx, 4)) >= 4
        assert [prov.status_of(r) for r in rids] == ["applied"] * 12


def test_a_quarantined_event_is_looked_at_less_often_as_it_ages_and_at_once_when_it_is_young(tmp_path, partner):
    with pending_world(tmp_path, partner) as (w, prov, p):
        w.quiet()
        rid = prov.send("x.on_the_way", ref="cr_unknown", data={"eta_minutes": 1})[0].json()["receipt_id"]
        w.sql("update wf_provider_inbox set checked_at=NULL")
        assert w.run(lambda: provider_sweep.apply_pending(w.engine.ctx)) == 1  # young: every pass
        w.sql("update wf_provider_inbox set received_at=received_at-1000, checked_at=?", (time.time(),))
        assert w.run(lambda: provider_sweep.apply_pending(w.engine.ctx)) == 0  # old and looked at a moment ago: not now
        w.sql("update wf_provider_inbox set checked_at=?", (time.time() - provider_sweep.QUIET - 1,))
        assert w.run(lambda: provider_sweep.apply_pending(w.engine.ctx)) == 1  # old, and long since looked at
        assert prov.status_of(rid) == "quarantined"


def test_one_integration_cannot_fill_the_waiting_room_with_events_that_match_nothing(tmp_path, partner):
    with pending_world(tmp_path, partner, wf_rate_per_minute=0, wf_quarantine_max=3) as (w, prov, p):
        w.quiet()
        stored = []
        for i in range(3):
            r, body = prov.send("x.on_the_way", ref=f"cr_unknown_{i}", data={"eta_minutes": 1})
            assert r.status_code == 202
            stored.append(body)
        r, body = prov.send("x.on_the_way", ref="cr_unknown_3", data={"eta_minutes": 1})
        err = r.json()["error"]
        assert (r.status_code, err["code"], err["retryable"]) == (429, "RATE_LIMITED", True) and r.headers["Retry-After"]
        assert w.sql("select count(*) from wf_provider_inbox") == [(3,)]  # the refused one was not stored
        again = prov.post(stored[0])  # the same bytes again: a retry of a stored event is still answered
        assert again.status_code == 202 and again.json()["duplicate"] is True
        assert sent_ok(prov, "x.on_the_way", ref=p.ref, version=1, data={"eta_minutes": 1})  # an event that matches is not refused
        other = Provider(w.env, w.env.client(domain="other", name="Other")["client_id"])
        assert other.send("x.on_the_way", ref="NOPE", data={"eta_minutes": 1})[0].status_code == 202  # nor another integration


# ---- K2, K3, C2: delta versions --------------------------------------------------------------------------------------
def test_a_version_that_is_old_news_still_counts_as_seen_so_the_next_one_is_not_a_gap(tmp_path, partner):
    with pending_world(tmp_path, partner, leader_only_notes, schema=DELTA, wf_delta_hold_seconds=1) as (w, prov, p):
        w.quiet()
        p.applied("x.on_the_way", version=1, data={"eta_minutes": 5})
        rid2, _ = p.send("x.assigned", version=2, data=DATA)  # lower rank than on_the_way: old news
        assert wait_status(w, prov, rid2, "rejected")["error"]["code"] == "STALE_EVENT"
        assert p.op_row()[3] == "2"  # the version was consumed, though the operation did not move
        rid3, _ = p.send("x.on_the_way", version=3, data={"eta_minutes": 9})  # nothing is missing
        wait_status(w, prov, rid3)
        time.sleep(1.5)
        w.run(w.engine.sweep)
        assert prov.status_of(rid3) == "applied" and p.state() == "waiting_external_event"


def test_a_delta_stream_that_starts_above_one_waits_for_the_events_before_it(tmp_path, partner):
    with pending_world(tmp_path, partner, schema=DELTA) as (w, prov, p):
        w.quiet()
        rid2, _ = p.send("x.on_the_way", version=2, data={"eta_minutes": 5})
        assert wait_status(w, prov, rid2, "processing")["ingestion_status"] == "processing"  # not taken as the start yet
        assert p.op_row()[3] is None
        rid1, _ = p.send("x.assigned", version=1, data=DATA)  # sent first, arrived second
        wait_status(w, prov, rid1)
        wait_status(w, prov, rid2)
        assert p.op_row()[:2] == ("pending", "on_the_way") and p.op_row()[3] == "2"
        assert told(p) == ["assigned", "on_the_way"]


def test_a_job_only_callback_that_waits_for_the_tools_answer_is_applied_before_the_next_version(tmp_path, partner):
    partner.delay = 3
    with pending_world(tmp_path, partner, begin=False, schema=DELTA, wf_delta_first_seconds=60) as (w, prov, _):
        out: list = []
        th = threading.Thread(target=lambda: out.append(w.flow.start()))
        th.start()
        row = w.wait(lambda: ops(w), 10, "the operation row")[0]
        rid1, _ = sent_ok(prov, "x.assigned", job="JOB-1", version=1, data=DATA)  # knows only the partner's job id
        assert prov.status_of(rid1) == "quarantined"
        rid2, _ = sent_ok(prov, "x.on_the_way", ref=row["reference"], version=2, data={"eta_minutes": 5})
        assert wait_status(w, prov, rid2, "processing")["ingestion_status"] == "processing"
        th.join(30)
        w.wait(lambda: ops(w)[0]["job"] == "JOB-1", 10, "the job id")
        w.run(w.engine.sweep)
        wait_status(w, prov, rid1)
        wait_status(w, prov, rid2)
        assert w.sql("select provider_version, normalized_status from wf_operations") == [("2", "on_the_way")]
        assert w.sql("select event_type from wf_provider_inbox where ingestion_status='applied' order by applied_at") == [
            ("x.assigned",), ("x.on_the_way",)]


def test_a_first_delta_event_above_one_is_the_start_once_nothing_earlier_came(tmp_path, partner):
    with pending_world(tmp_path, partner, schema=DELTA, wf_delta_first_seconds=1) as (w, prov, p):
        w.quiet()
        rid, _ = p.send("x.on_the_way", version=7, data={"eta_minutes": 5})
        assert prov.status_of(rid) in ("accepted", "processing")
        time.sleep(1.2)
        w.run(w.engine.sweep)
        wait_status(w, prov, rid)
        assert p.op_row()[3] == "7"
        rid8, _ = p.send("x.on_the_way", version=8, data={"eta_minutes": 4})
        wait_status(w, prov, rid8)  # and the stream goes on from there


def test_late_news_of_a_finished_operation_never_waits_and_never_troubles_the_workflow(tmp_path, partner):
    with pending_world(tmp_path, partner, schema=DELTA, wf_delta_hold_seconds=1) as (w, prov, p):
        w.quiet()
        p.applied("x.finished_quietly", version=1)
        assert p.state() == "awaiting_confirmation"
        rid, _ = p.send("x.on_the_way", version=3, data={"eta_minutes": 5})  # version 2 never arrives
        assert wait_status(w, prov, rid, "rejected")["error"]["code"] == "STALE_EVENT"  # at once, not after an hour
        time.sleep(1.5)
        w.run(w.engine.sweep)
        assert p.state() == "awaiting_confirmation" and p.op_row()[3] == "1"  # (version 3 was no step of the stream)
        rid2, _ = p.send("x.reopened", version=2, data={})  # the correction that was really next still applies
        wait_status(w, prov, rid2)
        assert p.state() == "waiting_external_event"


# ---- A5: one model turn for the news that came while the leader was busy ----------------------------------------------
def busy_leader(turns: list):
    """The first turn is the action; a provider wake records what it was handed and says it. The model is slow."""
    def script(c):
        turn = c.after_user()
        if "<provider-event" in c.last_user:
            if turn.called("CaseSay") == 0:
                turns.append(c.last_user)
                ev = re.findall(r'evidence="(E\d+)"', c.last_user)
                return say("Update for you.", "none", ev[-1:])
            return "Said."
        if "<resident-message" in c.last_user and "partner_repair" in c.blob:
            return say("Noted your message.", "none") if turn.called("CaseSay") == 0 else "Said."
        if turn.called("partner_repair") == 0:
            return [("partner_repair", {"slot": "mon"})]
        return say("I asked for a plumber; it is pending.", "none") if turn.called("CaseSay") == 0 else "Said."
    return script


def reply_while_slow(w, p) -> threading.Event:
    """Send a reply and hold the leader in the middle of its turn until the returned gate is set."""
    gate = hold_leader()
    threading.Thread(target=lambda: w.flow.reply(p.start, p.first), daemon=True).start()
    w.wait(lambda: w.sql("select 1 from wf_turns where status='running'"), what="the leader to be in the middle of its turn")
    return gate


@pytest.mark.slow
def test_wakes_queued_for_one_operation_become_one_turn_that_lists_them_newest_last(tmp_path, partner):
    turns: list = []
    with pending_world(tmp_path, partner, busy_leader(turns)) as (w, prov, p):
        w.quiet()
        gate = reply_while_slow(w, p)
        r1, _ = p.send("x.progress", version=1, data={"note": "plumber is working"})
        r2, _ = p.send("x.completed", version=2, job=p.job, data={"summary": "Pipe replaced"})
        wait_status(w, prov, r1)
        wait_status(w, prov, r2)
        assert p.jobs() == 1  # the second event joined the job that waited
        gate.set()
        w.quiet(60)
        [text] = turns  # one model turn for both
        assert text.index('type="x.progress"') < text.index('type="x.completed"')
        assert "2 reports came while you were busy" in text and "confirm that it is finished" in text
        assert len([m for m in w.messages(p.wid) if m[1] == "Update for you."]) == 1


def test_a_burst_of_wake_events_costs_a_few_turns_not_one_each(tmp_path, partner):
    turns: list = []
    with pending_world(tmp_path, partner, busy_leader(turns)) as (w, prov, p):
        w.quiet()
        gate = hold_leader()
        first = p.send("x.progress", version=1, data={"note": "step 0"})[0]
        w.wait(lambda: w.sql("select 1 from wf_turns where status='running'"), what="the leader to be handed the first one")
        rids = [p.send("x.progress", version=2 + i, data={"note": f"step {i + 1}"})[0] for i in range(11)]
        for rid in [first, *rids]:
            wait_status(w, prov, rid)
        gate.set()
        w.quiet(90)
        assert len(turns) <= 3 and p.jobs() <= 3, (len(turns), p.jobs())
        assert "older reports are left out" in turns[-1] and 'note: step 11' in turns[-1]  # the newest is there, last


@pytest.mark.slow
def test_news_that_came_after_the_wake_without_a_wake_of_its_own_is_said_to_have_moved_on(tmp_path, partner):
    turns: list = []
    with pending_world(tmp_path, partner, busy_leader(turns)) as (w, prov, p):
        w.quiet()
        gate = reply_while_slow(w, p)
        r1, _ = p.send("x.progress", version=1, data={"note": "plumber is working"})
        wait_status(w, prov, r1)
        r2, _ = p.send("x.finished_quietly", version=2)  # terminal, done, and it wakes nobody
        wait_status(w, prov, r2)
        gate.set()
        w.quiet(60)
        [text] = turns
        assert "Since the last report the operation is completed" in text and "confirm that it is finished" in text


# ---- S2: a revoked key no longer speaks for its provider -------------------------------------------------------------
@pytest.mark.parametrize("which", ["api", "signing"])
def test_events_queued_by_a_key_that_was_revoked_are_refused_when_the_sweep_gets_to_them(tmp_path, partner, which):
    with pending_world(tmp_path, partner) as (w, prov, p):
        w.quiet()
        rid, _ = p.send("x.completed", version=1, job="LATE-1", ref=None, data={"summary": "attacker says all done"})
        assert prov.status_of(rid) == "quarantined"
        if which == "api":
            assert w.env.post(f"/platform/v1/wf/keys/{prov.api_key.split('.')[0][3:]}/revoke").status_code == 200
        else:
            assert w.env.post(f"/platform/v1/wf/integrations/{prov.id}/signing-keys/{prov.key_id}/revoke").status_code == 200
        w.sql("update wf_operations set external_job_id='LATE-1' where workflow_id=?", (p.wid,))  # the tool's answer arrives
        w.run(w.engine.sweep)
        w.run(w.engine.sweep)
        status, error = w.sql("select ingestion_status, error from wf_provider_inbox where receipt_id=?", (rid,))[0]
        row = (status, json.loads(error)["code"])
        assert row == ("rejected", "KEY_REVOKED") and p.op_row()[0] == "pending"
        assert p.jobs() == 0


def test_an_event_of_a_key_that_is_still_good_is_not_touched_by_the_check(tmp_path, partner):
    with pending_world(tmp_path, partner) as (w, prov, p):
        w.quiet()
        other_key, _ = prov.other_signing_key()
        w.env.post(f"/platform/v1/wf/integrations/{prov.id}/signing-keys/{other_key}/revoke")  # an unrelated key
        assert p.applied("x.on_the_way", version=1, data={"eta_minutes": 5})["ingestion_status"] == "applied"


# ---- S4: a tool that names no integration belongs to the client's only one ---------------------------------------------
def test_with_two_integrations_a_tool_bound_to_none_is_followed_by_neither(tmp_path, partner):
    with pending_world(tmp_path, partner, begin=False) as (w, prov, _):
        configure(w, partner, tools_for(None))  # one integration: an unbound tool is that one's
        start, first = w.flow.begin()
        p = Pending(w, partner, prov, start, first)
        w.quiet()
        assert p.applied("x.on_the_way", version=1, data={"eta_minutes": 5})["ingestion_status"] == "applied"
        stranger = Provider(w.env, w.flow.client["client_id"])  # a second provider of the same client
        for who in (stranger, prov):
            r, _ = who.send("x.completed", ref=p.ref, version=2, data={"summary": "done by someone else"})
            assert r.status_code == 202 and r.json()["ingestion_status"] == "quarantined"  # nobody is given the operation
        assert p.op_row()[0] == "pending"


def test_a_tool_that_follows_events_must_name_its_integration_once_there_are_two(tmp_path, partner):
    with pending_world(tmp_path, partner, begin=False) as (w, prov, _):
        url = f"/platform/v1/wf/routes/{w.flow.route['route_id']}/tools"
        Provider(w.env, w.flow.client["client_id"])  # the second integration
        r = w.env.http.put(url, headers=ADM, json={"tools": tools_for(None)})
        assert r.status_code == 422 and "partner_repair" in r.text
        assert w.env.http.put(url, headers=ADM, json={"tools": tools_for(prov.id)}).status_code == 200
