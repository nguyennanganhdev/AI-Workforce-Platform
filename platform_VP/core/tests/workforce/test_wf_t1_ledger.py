"""The operation ledger and the recovery of what a crash leaves (slice T1; spec 8; P0 items 21-24).

The tools are built the way an agent gets them and called by hand on the app's own loop, so the steps of the body
can be stopped one by one: a `Crash` is a BaseException, which nothing in the body may catch, like a killed process.
Then the sweep's reconcile runs, as it would after a restart. Scripted model only; a real MCP server.
"""
from __future__ import annotations

import asyncio
import contextlib

import pytest
from enginekit import world
from partnerkit import Partner
from t1kit import SETTINGS, TOOLS, Crash, configure, crash_at, ops, quiet_leader, tools_of

from awp.workforce import ledger
from awp.workforce.reconcile import reconcile


@pytest.fixture
def partner():
    with Partner() as p:
        yield p


@contextlib.contextmanager
def room(tmp_path, partner, tools=None, **over):
    """A world with one workflow at rest and the standard tools on the fake partner."""
    with world(tmp_path, quiet_leader, **TOOLS, **{**SETTINGS, **over}) as w:
        configure(w, partner, tools)
        w.flow.begin()
        yield w


def words(chunk) -> str:
    return chunk.content[0].text


def call(w, tool, **args):
    async def go():
        return await tool.call(**args)
    return w.run(go)


def dies(w, tool, **args) -> bool:
    """Call `tool` and say whether it was killed on the way. The Crash is caught on the app's loop: a BaseException
    that reaches the portal takes the loop down with it, which a killed process would, but the test must not."""
    async def go():
        try:
            await tool.call(**args)
        except Crash:
            return True
        return False
    return w.run(go)


def sweep(w, grace: float = 0.0) -> int:
    return w.run(lambda: reconcile(w.engine, grace=grace))


def state(w) -> tuple:
    return w.sql("select state, attention_reason from wf_workflows")[0]


# ---- the same call twice ---------------------------------------------------------------------------------------------
def test_identical_calls_at_the_same_moment_from_two_agents_make_one_effect(tmp_path, partner):
    with room(tmp_path, partner) as w:
        a, b = tools_of(w), tools_of(w)  # the tools of two agents

        async def go():
            return await asyncio.gather(*[(a if i % 2 else b)["partner_repair"].call(slot="mon") for i in range(8)])
        answers = [words(x) for x in w.run(go)]
        assert len(partner.of("book_repair")) == 1 and partner.effects == ["repair"] and len(ops(w)) == 1
        assert sum(x.startswith("PENDING: the partner accepted") for x in answers) == 1
        assert all(x.startswith(("PENDING", "IN PROGRESS")) for x in answers)
        assert ledger.INFLIGHT == set()


def test_the_same_arguments_in_another_order_are_the_same_call(tmp_path, partner):
    with room(tmp_path, partner) as w:
        t = tools_of(w)["partner_hotel"]
        call(w, t, hotel="Sunrise", nights=2)
        again = call(w, t, nights=2, hotel="Sunrise")
        assert words(again).startswith("ALREADY DONE") and len(partner.of("book_hotel")) == 1


def test_a_repeat_on_purpose_needs_a_changed_argument_or_a_nonce_and_the_partner_never_sees_the_nonce(tmp_path, partner):
    with room(tmp_path, partner) as w:
        t = tools_of(w)["partner_hotel"]
        first = call(w, t, hotel="Sunrise", nights=2)
        assert "confirmed" in words(first) and len(partner.of("book_hotel")) == 1
        again = call(w, t, hotel="Sunrise", nights=2)  # nothing changed: it was done, it is not done again
        assert words(again).startswith("ALREADY DONE") and "idempotency_nonce" in words(again)
        assert len(partner.of("book_hotel")) == 1
        assert "confirmed" in words(call(w, t, hotel="Sunrise", nights=3))  # a changed argument is a new request
        assert "confirmed" in words(call(w, t, hotel="Sunrise", nights=2, idempotency_nonce="again"))  # so is a nonce
        assert len(partner.of("book_hotel")) == 3 and len(ops(w)) == 3
        assert all(set(c["args"]) == {"hotel", "nights", "client_reference"} for c in partner.of("book_hotel"))
        assert len({c["args"]["client_reference"] for c in partner.of("book_hotel")}) == 3
        assert words(call(w, t, hotel="Sunrise", nights=2, idempotency_nonce="again")).startswith("ALREADY DONE")
        assert len(partner.of("book_hotel")) == 3


def test_a_request_the_partner_refused_is_not_sent_again_unless_it_is_changed(tmp_path, partner):
    with room(tmp_path, partner) as w:
        t = tools_of(w)["partner_reject"]
        assert words(call(w, t)).startswith("FAILED:")
        again = words(call(w, t))
        assert again.startswith("FAILED earlier") and len(partner.of("rejecting_action")) == 1
        assert words(call(w, t, idempotency_nonce="second try")).startswith("FAILED:")
        assert len(partner.of("rejecting_action")) == 2


def test_pending_and_unknown_requests_answer_from_the_row_without_calling_the_partner(tmp_path, partner):
    with room(tmp_path, partner) as w:
        tools = tools_of(w)
        call(w, tools["partner_repair"], slot="mon")
        again = words(call(w, tools["partner_repair"], slot="mon"))
        assert again.startswith("PENDING: this same request is already with the partner") and "JOB-1" in again
        call(w, tools["partner_nostatus"], thing="x")  # no readable status: unknown
        again = words(call(w, tools["partner_nostatus"], thing="x"))
        assert again.startswith("UNKNOWN: this same request was sent before") and "Do not retry" in again
        assert len(partner.of("book_repair")) == 1 and len(partner.of("no_status_action")) == 1


def test_a_request_that_never_reached_the_partner_may_be_made_again_with_the_same_row(tmp_path):
    p = Partner().start()
    port = p.port
    try:
        with room(tmp_path, p) as w:
            t = tools_of(w)["partner_hotel"]
            p.stop()
            first = words(call(w, t, hotel="Sunrise", nights=2))
            assert first.startswith("FAILED:")
            [op] = ops(w)
            assert op["status"] == "failed"
            assert w.sql("select result from wf_operations")[0][0].count('"sent": false') == 1
            ref = op["reference"]
            p2 = Partner(port=port).start()  # the partner is back
            try:
                second = words(call(w, t, hotel="Sunrise", nights=2))
                assert "confirmed" in second
                [op] = ops(w)
                assert (op["status"], op["reference"]) == ("completed", ref)  # the same row, the same reference
                assert p2.effects == ["hotel"]
            finally:
                p2.stop()
    finally:
        p.stop()


def test_an_action_on_a_closed_workflow_is_refused_before_anything_is_written(tmp_path, partner):
    with room(tmp_path, partner) as w:
        t = tools_of(w)["partner_hotel"]
        w.sql("update wf_workflows set state='closed', closed_at=1")
        assert "closed" in words(call(w, t, hotel="Sunrise", nights=2))
        assert ops(w) == [] and partner.calls == []


# ---- the body stops at each step -------------------------------------------------------------------------------------
def test_a_crash_before_the_row_is_written_leaves_nothing_and_the_call_then_works(tmp_path, partner, monkeypatch):
    with room(tmp_path, partner) as w:
        t = tools_of(w)["partner_repair"]
        crash_at(monkeypatch, ledger, "begin")
        assert dies(w, t, slot="mon")
        assert ops(w) == [] and partner.calls == [] and ledger.INFLIGHT == set()
        monkeypatch.undo()
        assert words(call(w, t, slot="mon")).startswith("PENDING:")
        assert partner.effects == ["repair"] and len(ops(w)) == 1


def stopped_at(w, monkeypatch, tool, step: str, **args):
    """Run `tool` and kill it at `step`: after the row is written (before the call leaves), or after the partner
    answered (before the answer is recorded)."""
    crash_at(monkeypatch, ledger, "mark_sent" if step == "intent" else "finish")
    assert dies(w, tool, **args)
    monkeypatch.undo()
    assert ledger.INFLIGHT == set()
    return ops(w)


@pytest.mark.parametrize("step,intended_calls", [("intent", 0), ("sent", 1)])
def test_without_a_way_to_ask_or_resend_a_crashed_call_is_unknown_and_a_person_is_asked(tmp_path, partner, monkeypatch, step, intended_calls):
    with room(tmp_path, partner) as w:
        t = tools_of(w)["partner_hotel"]
        [op] = stopped_at(w, monkeypatch, t, step, hotel="Sunrise", nights=2)
        assert op["status"] == ("intent" if step == "intent" else "sent")
        assert len(partner.of("book_hotel")) == intended_calls
        assert sweep(w, grace=3600) == 0  # not old enough: it may still be on its way
        assert sweep(w) == 1
        [op] = ops(w)
        assert op["status"] == "unknown" and state(w) == ("needs_attention", "operation_unknown")
        assert len(partner.of("book_hotel")) == intended_calls  # nothing was sent to find out
        later = words(call(w, tools_of(w)["partner_hotel"], hotel="Sunrise", nights=2))  # a restarted process, same call
        assert later.startswith("UNKNOWN: this same request was sent before")
        assert len(partner.of("book_hotel")) == intended_calls


@pytest.mark.parametrize("step", ["intent", "sent"])
def test_with_an_idempotency_argument_a_crashed_call_is_sent_again_with_the_same_reference(tmp_path, partner, monkeypatch, step):
    with room(tmp_path, partner) as w:
        t = tools_of(w)["partner_repair_keyed"]
        [op] = stopped_at(w, monkeypatch, t, step, slot="mon")
        ref = op["reference"]
        assert sweep(w) == 1
        [op] = ops(w)
        assert (op["status"], op["reference"], op["job"]) == ("pending", ref, "JOB-1")
        assert {c["args"]["client_reference"] for c in partner.of("book_repair")} == {ref}
        assert partner.effects == ["repair"]  # the partner makes the second sending a no-op, so there is one effect
        assert len(partner.of("book_repair")) == (1 if step == "intent" else 2)
        assert state(w)[0] != "needs_attention"


def test_with_a_status_query_a_crashed_call_is_asked_about_and_what_the_partner_says_is_applied(tmp_path, partner, monkeypatch):
    with room(tmp_path, partner) as w:
        t = tools_of(w)["partner_repair_q"]
        [op] = stopped_at(w, monkeypatch, t, "sent", slot="mon")  # the partner did get it
        partner.status_of[op["reference"]] = "completed"
        assert sweep(w) == 1
        [op] = ops(w)
        assert (op["status"], op["partner_status"], op["job"]) == ("completed", "completed", "JOB-1")
        assert len(partner.of("book_repair")) == 1 and len(partner.of("repair_status")) == 1  # asked, never resent
        [job] = w.sql("select kind, status from wf_jobs where kind='provider_wake'")
        assert job == ("provider_wake", "queued") or job == ("provider_wake", "done")


def test_with_a_status_query_a_call_the_partner_never_got_is_not_resent_and_needs_a_person(tmp_path, partner, monkeypatch):
    with room(tmp_path, partner) as w:
        t = tools_of(w)["partner_repair_q"]
        stopped_at(w, monkeypatch, t, "intent", slot="mon")  # it never left
        assert sweep(w) == 1
        [op] = ops(w)
        assert op["status"] == "unknown" and state(w) == ("needs_attention", "operation_unknown")
        assert partner.of("book_repair") == [] and len(partner.of("repair_status")) == 1


def test_a_live_call_in_this_process_is_never_taken_for_a_crash(tmp_path, partner, monkeypatch):
    with room(tmp_path, partner) as w:
        t = tools_of(w)["partner_hotel"]
        [op] = stopped_at(w, monkeypatch, t, "sent", hotel="Sunrise", nights=2)
        ledger.INFLIGHT.add(op["id"])
        try:
            assert sweep(w) == 1 and ops(w)[0]["status"] == "sent"  # looked at, left alone
        finally:
            ledger.INFLIGHT.discard(op["id"])
        assert sweep(w) == 1 and ops(w)[0]["status"] == "unknown"


def test_a_status_query_is_repeated_only_after_its_pause_and_a_still_pending_operation_makes_no_news(tmp_path, partner):
    with room(tmp_path, partner) as w:
        t = tools_of(w)["partner_repair_q"]
        assert words(call(w, t, slot="mon")).startswith("PENDING:")
        before = w.sql("select count(*) from wf_events where event_type='operation.status_changed'")[0][0]
        rev = w.sql("select revision from wf_workflows")[0][0]
        assert w.run(lambda: reconcile(w.engine, poll=3600)) == 0  # asked a moment ago
        assert w.run(lambda: reconcile(w.engine, poll=0.0)) == 1
        assert len(partner.of("repair_status")) == 1 and ops(w)[0]["status"] == "pending"
        assert w.sql("select count(*) from wf_events where event_type='operation.status_changed'")[0][0] == before
        assert w.sql("select revision from wf_workflows")[0][0] == rev
        [op] = ops(w)
        partner.status_of[op["reference"]] = "failed"
        assert w.run(lambda: reconcile(w.engine, poll=0.0)) == 1
        assert ops(w)[0]["status"] == "failed"
        assert w.sql("select count(*) from wf_jobs where kind='provider_wake'")[0][0] == 1


def test_a_finished_operation_is_never_changed_by_a_late_answer(tmp_path, partner):
    with room(tmp_path, partner) as w:
        t = tools_of(w)["partner_hotel"]
        call(w, t, hotel="Sunrise", nights=2)
        [op] = ops(w)
        from awp.workforce.partner_result import UNKNOWN, PartnerResult
        late = w.run(lambda: ledger.finish(w.rt.db, op["id"], PartnerResult(UNKNOWN, "late", error="timeout")))
        assert late["status"] == "completed" and ops(w)[0]["status"] == "completed"


# ---- the one deadline over the whole body ---------------------------------------------------------------------------
def test_the_whole_body_is_under_one_deadline_so_a_slow_ledger_cannot_push_it_past_the_offload(tmp_path, partner, monkeypatch):
    with room(tmp_path, partner) as w:
        t = tools_of(w)["partner_slow"]
        t.total = 3.0
        real = ledger.begin

        async def slow_begin(*a, **k):
            await asyncio.sleep(1.0)  # time spent before the partner is even called
            return await real(*a, **k)
        monkeypatch.setattr(ledger, "begin", slow_begin)
        given = []
        real_call = t.client.call

        async def spy(*a, **k):
            given.append(k["timeout"])
            return await real_call(*a, **k)
        monkeypatch.setattr(t.client, "call", spy)
        partner.delay = 20
        out = words(call(w, t, seconds=20))
        assert out.startswith("UNKNOWN:") and ops(w)[0]["status"] == "unknown"
        # the partner got what was LEFT of the one budget (a second went to the ledger), not a whole new budget
        assert given and given[0] <= t.total - 1.0 + 0.01, given


def test_a_body_that_cannot_get_the_call_out_in_time_says_not_sent_and_may_be_tried_again(tmp_path, partner, monkeypatch):
    with room(tmp_path, partner) as w:
        t = tools_of(w)["partner_hotel"]  # 8 s
        real = ledger.mark_sent

        outlived = []

        async def stuck(*a, **k):
            await asyncio.sleep(30)
            outlived.append(1)  # only reached if nothing stopped the wait
        monkeypatch.setattr(ledger, "mark_sent", stuck)
        t.total = 1.0
        out = words(call(w, t, hotel="Sunrise", nights=2))
        assert out.startswith("Not sent") and partner.calls == [] and outlived == []  # the deadline cut it, not the 30 s
        [op] = ops(w)
        assert op["status"] == "failed" and ledger.INFLIGHT == set()  # provably not sent: the row says so
        monkeypatch.setattr(ledger, "mark_sent", real)
        assert "confirmed" in words(call(w, t, hotel="Sunrise", nights=2))
        assert len(ops(w)) == 1 and partner.effects == ["hotel"]


def test_a_cancelled_call_records_unknown_before_it_lets_go(tmp_path, partner):
    with room(tmp_path, partner) as w:
        t = tools_of(w)["partner_slow"]
        partner.delay = 20

        async def go():
            task = asyncio.ensure_future(t.call(seconds=20))
            for _ in range(2000):  # the call is out when the partner has it
                if partner.of("slow_action"):
                    break
                await asyncio.sleep(0.01)
            task.cancel()
            with pytest.raises(asyncio.CancelledError):
                await task
        w.run(go)
        assert ops(w)[0]["status"] == "unknown" and ledger.INFLIGHT == set()


def test_the_agent_class_keeps_partner_tools_out_of_the_background(tmp_path, partner):
    """allow_offload = False is honoured by the policy that wraps the framework's offload middleware."""
    from awp.offload import OffloadPolicy, PolicyAgent
    from awp.workforce.partner_tools import PartnerTool

    with room(tmp_path, partner) as w:
        assert w.env.app.state.custom_agent_cls is PolicyAgent
        built = tools_of(w)
        assert all(t.allow_offload is False for t in built.values()) and PartnerTool.allow_offload is False

        class Inner:
            def __init__(self):
                self.seen = []

            async def on_acting(self, agent, kw, nxt):
                self.seen.append(kw["tool_call"].name)
                yield "inner"

        class Toolkit:
            async def get_tool(self, name):
                return built["partner_repair"] if name == "partner_repair" else object()

        class Agent:
            toolkit = Toolkit()

        class Call:
            def __init__(self, name):
                self.name = name

        async def nxt(**kw):
            yield "direct"

        async def go(name):
            inner = Inner()
            got = [x async for x in OffloadPolicy(inner).on_acting(Agent(), {"tool_call": Call(name)}, nxt)]
            return got, inner.seen
        assert w.run(lambda: go("partner_repair")) == (["direct"], [])  # straight through, never offered to the offload
        assert w.run(lambda: go("Other")) == (["inner"], ["Other"])  # any other tool is the framework's business
