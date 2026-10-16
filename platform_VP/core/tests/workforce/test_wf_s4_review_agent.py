"""Regression tests of the S4 review that concern what the leader may say, ask and see around a consent: the
consent record is not proof of work, odd numbers are refusals the model can read, the figures of a partner tool are
grounded, a declined request is not pushed, and the leader is told what the resident answered. Scripted model only."""
from __future__ import annotations

import uuid as real_uuid
from types import SimpleNamespace

import consentkit as ck
import fake_llm
import pytest
from enginekit import evidence_of, world
from fake_llm import CALLS, Call
from scripts import say
from test_wf_s4_flow import TOOLS, _clean, text_of, trip  # noqa: F401 - _clean is an autouse fixture

ITEMS = [{"label": "Sunrise 2 nights", "amount": "1800000"}, {"label": "Service fee", "amount": "90000"}]


# ---- the record of a consent is the resident's word, not a system's ----------------------------------------------------
def laundering(summary: str, claim: str, then: str = "say"):
    """Asks consent with a summary that carries a marker word, then claims work that no tool ever did."""
    def script(c: Call):
        if ck.CHOOSE not in c.last_user:
            return ck.asking(c) or "Said."
        turn = c.after_user()
        if turn.called("calc_sum") == 0:
            return [("calc_sum", {"label": "booking", "values": ["1800000", "90000"]})]
        cites = [evidence_of(c.blob)[0], evidence_of(" ".join(turn.results("calc_sum")))[0]]
        if turn.called("CaseAskConsent") == 0:
            return [("CaseAskConsent", {"summary": summary, "cites": cites, "total": "1890000", "items": ITEMS})]
        ev = evidence_of(turn.results("CaseAskConsent")[-1])[:1]
        if then == "say" and turn.called("CaseSay") == 0:
            return say(claim, "none", ev)
        if then == "finalize" and turn.called("CaseFinalize") == 0:
            return [("CaseFinalize", {"answer": claim, "outcome": "resolved", "cites": ev})]
        return "Said."
    return script


def _agree(w) -> str:
    f = w.flow
    start, first, second = trip(w)
    [appr] = f.approvals(first["conversation_id"])
    assert f.decide(appr["approval_id"], f.decide_body(start, first, appr)).status_code == 202
    w.wait(lambda: w.state(first["workflow_id"])[0] != "awaiting_approval", what="the decision to be taken")
    w.quiet()
    return first["workflow_id"]


@pytest.mark.parametrize("summary", ["Sunrise 2 nights, booked on arrival", "Book Sunrise for 2 nights, booking confirmed"])
def test_a_consent_summary_cannot_unlock_a_done_claim(tmp_path, summary):
    """No tool ever booked anything. The model puts a marker word into the text the resident approves and then cites
    the record of the consent for 'has been booked'. The record says what the platform wrote, so it proves nothing."""
    with world(tmp_path, laundering(summary, "Your Sunrise hotel has been booked."), **TOOLS) as w:
        wid = _agree(w)
        said = [m[1] for m in w.messages(wid) if m[0] == "assistant"]
        assert ck.BOOKED == [] and not any("has been booked" in s for s in said), said
        [(record,)] = w.sql("select data from awp_case_items where kind='evidence' and cast(data as text) like '%resident approved%'")
        assert "booked" not in record and "confirmed" not in record  # the model's wording is not in it


def test_a_consent_record_alone_cannot_back_a_resolved_answer(tmp_path):
    """CaseFinalize(resolved) needs a tool result; the only 'result' here is the resident's own consent."""
    with world(tmp_path, laundering("Sunrise 2 nights, booked on arrival", "Your Sunrise hotel has been booked.", "finalize"),
               **TOOLS) as w:
        wid = _agree(w)
        said = [m[1] for m in w.messages(wid) if m[0] == "assistant"]
        assert ck.BOOKED == [] and not any("has been booked" in s for s in said), said
        assert w.state(wid)[0] != "awaiting_confirmation"
        assert any("must rest on a tool result" in str(c["shape"]) for c in CALLS)  # the model was told why


def test_the_same_claim_is_refused_without_a_marker_word_too(tmp_path):
    """Control: the guard worked before; the tests above are about the record, not about the guard."""
    with world(tmp_path, laundering("Book Sunrise for 2 nights", "Your Sunrise hotel has been booked."), **TOOLS) as w:
        wid = _agree(w)
        assert not any("has been booked" in m[1] for m in w.messages(wid) if m[0] == "assistant")


# ---- numbers the model sends -------------------------------------------------------------------------------------------
def asks(amount, total, label="Sunrise 2 nights", extra=None):
    def script(c: Call):
        if ck.CHOOSE not in c.last_user:
            return ck.asking(c) or "Said."
        turn = c.after_user()
        if turn.called("CaseAskConsent") == 0:
            return [("CaseAskConsent", {"summary": "Book Sunrise", "cites": [evidence_of(c.blob)[0]], "total": total,
                                        "items": [{"label": label, "amount": amount}], **(extra or {})})]
        if turn.called("CaseSay") == 0:
            return say("Understood, I will not go on. Anything else?", "reply")
        return "Said."
    return script


@pytest.mark.parametrize("amount", ["NaN", "sNaN", "Infinity", "1E+5000"])
def test_a_number_that_is_no_amount_is_a_refusal_the_model_reads_not_a_failed_turn(tmp_path, amount):
    with world(tmp_path, asks(amount, amount), **TOOLS) as w:
        ck.declare(w)
        start, first = w.flow.begin(message=text_of(ck.START))
        w.flow.reply(start, first, message=text_of(ck.CHOOSE))
        wid = first["workflow_id"]
        w.wait(lambda: w.state(wid)[0] != "active", what="rest")
        w.quiet(30)
        assert w.state(wid)[0] == "awaiting_user"  # the model was told, said so, and the workflow rests
        assert w.sql("select count(*) from wf_approvals") == [(0,)] and not w.sql("select 1 from wf_turns where status='error'")
        assert any("is not an amount" in str(c["shape"]) for c in CALLS)


def test_a_huge_label_is_refused_not_stored_and_published_whole(tmp_path):
    with world(tmp_path, asks("1800000", "1800000", label="x" * 400_000), **TOOLS) as w:
        ck.declare(w)
        start, first = w.flow.begin(message=text_of(ck.START))
        w.flow.reply(start, first, message=text_of(ck.CHOOSE))
        w.quiet()
        assert w.sql("select count(*) from wf_approvals") == [(0,)]
        assert any("label is at most" in str(c["shape"]) for c in CALLS)


def test_a_quote_id_the_model_made_up_is_not_put_to_the_resident(tmp_path):
    """The partner's quote id travels to the partner and back with the decision: it has to be in what the leader cites."""
    with world(tmp_path, ck.consenting(quote="QX-9917"), **TOOLS) as w:
        start, first, second = trip(w)
        assert w.sql("select count(*) from wf_approvals") == [(0,)]
        assert any("is in none of the items you cite" in str(c["shape"]) for c in CALLS)


def test_a_partner_tool_does_not_show_the_resident_a_figure_no_evidence_states(tmp_path):
    """The look-up says 1800000; the model asks to book at 100. CaseAskConsent would refuse that figure, so does the gate."""
    def script(c: Call):
        if ck.CHOOSE not in c.last_user:
            return ck.asking(c) or "Said."
        turn = c.after_user()
        if turn.called("book_hotel") == 0:
            return [("book_hotel", {"hotel": "Sunrise", "nights": 2, "price": "100"})]
        return say("I could not book that.", "reply") if turn.called("CaseSay") == 0 else "Said."

    with world(tmp_path, script, **TOOLS) as w:
        ck.declare(w)
        start, first = w.flow.begin(message=text_of(ck.START))
        w.flow.reply(start, first, message=text_of(ck.CHOOSE))
        w.quiet()
        assert w.sql("select count(*) from wf_approvals") == [(0,)] and ck.BOOKED == []
        assert any("figures not found in the evidence of the case: 100" in str(c["shape"]) for c in CALLS)


def test_the_arguments_of_a_partner_tool_are_bounded(tmp_path):
    def script(c: Call):
        if ck.CHOOSE not in c.last_user:
            return ck.asking(c) or "Said."
        turn = c.after_user()
        if turn.called("book_hotel") == 0:
            return [("book_hotel", {"hotel": "S" * 20_000, "nights": 2, "price": "1800000"})]
        return say("I could not book that.", "reply") if turn.called("CaseSay") == 0 else "Said."

    with world(tmp_path, script, **TOOLS) as w:
        ck.declare(w)
        start, first = w.flow.begin(message=text_of(ck.START))
        w.flow.reply(start, first, message=text_of(ck.CHOOSE))
        w.quiet()
        assert w.sql("select count(*) from wf_approvals") == [(0,)] and ck.BOOKED == []


# ---- what the leader may tell the resident about the end ---------------------------------------------------------------
def claims_closed(text: str):
    def script(c: Call):
        if ck.CHOOSE not in c.last_user:
            return ck.asking(c) or "Said."
        turn = c.after_user()
        if turn.called("book_hotel") == 0:
            return [("book_hotel", ck.BOOK)]
        ev = evidence_of(" ".join(turn.results("book_hotel")))
        if turn.called("CaseSay") == 0:
            return say(text, "none", ev[:1])
        return "Said."
    return script


@pytest.mark.parametrize("text", ["Booked: BK-77. Your request is closed.", "Booked: BK-77. I have closed your ticket.",
                                  "Booked: BK-77. Yêu cầu của bạn đã đóng."])
def test_the_resident_is_not_told_the_request_is_closed_when_only_the_partner_can_close_it(tmp_path, text):
    with world(tmp_path, claims_closed(text), **TOOLS) as w:
        wid = _agree(w)
        said = [m[1] for m in w.messages(wid) if m[0] == "assistant"]
        assert not any("clos" in s.lower() or "đã đóng" in s for s in said), said
        assert any("only the partner can close" in str(c["shape"]) for c in CALLS)  # the model was told why
        assert w.state(wid)[0] != "closed"


def test_the_words_about_a_shop_being_closed_are_not_caught(tmp_path):
    with world(tmp_path, claims_closed("Booked: BK-77. The pool is closed on Mondays."), **TOOLS) as w:
        wid = _agree(w)
        assert any("pool is closed" in m[1] for m in w.messages(wid) if m[0] == "assistant")


# ---- the leader is told what the resident answered, and does not push -----------------------------------------------
def states_in(call: dict) -> list[str]:
    return [t for role, t, _ in call["shape"] if "<workflow-state" in t]


def test_the_state_block_tells_the_leader_what_the_resident_just_decided(tmp_path):
    """Compaction may drop what the resident answered; our database does not."""
    with world(tmp_path, ck.trip, **TOOLS) as w:
        f = w.flow
        start, first, second = trip(w)
        [appr] = f.approvals(first["conversation_id"])
        assert f.decide(appr["approval_id"], f.decide_body(start, first, appr, decision="reject")).status_code == 202
        w.wait_state(first["workflow_id"], "awaiting_user")
        w.quiet()
        seen = len(CALLS)
        r = f.reply(start, first, message=text_of("So what is the position on my booking?"))[0]
        assert r.status_code == 200, r.text
        calls = [c for c in CALLS[seen:] if 'key="supervisor"' in c["sys"] or "case-leader" in c["sys"]]
        block = states_in(calls[0])[-1]
        assert f"{appr['approval_id']} book_hotel the resident DECLINED" in block, block


def declined_then_asks_again(c: Call):
    if ck.CHOOSE not in c.last_user:
        return ck.asking(c) or "Said."
    turn = c.after_user()
    if turn.called("calc_sum") == 0:
        return [("calc_sum", {"label": "booking", "values": ["1800000", "90000"]})]
    cites = [evidence_of(c.blob)[0], evidence_of(" ".join(turn.results("calc_sum")))[0]]
    ask = {"summary": "Book Sunrise for 2 nights", "cites": cites, "total": "1890000", "items": ITEMS}
    if turn.called("CaseAskConsent") < 3:
        return [("CaseAskConsent", ask)]  # asks again whatever the answer was
    return say("Understood.", "reply")


def test_a_refusal_is_not_asked_again_until_the_resident_has_written(tmp_path):
    with world(tmp_path, declined_then_asks_again, **TOOLS) as w:
        f = w.flow
        start, first, second = trip(w)
        [appr] = f.approvals(first["conversation_id"])
        assert f.decide(appr["approval_id"], f.decide_body(start, first, appr, decision="reject")).status_code == 202
        w.wait_state(first["workflow_id"], "awaiting_user")
        w.quiet()
        assert w.sql("select status from wf_approvals") == [("rejected",)]  # the two asks after the refusal were turned away
        assert sum("declined exactly this" in str(c["shape"]) for c in CALLS) >= 1
        # once the resident writes again, the same request may be put to them again
        f.reply(start, first, message=text_of(f"{ck.CHOOSE} I changed my mind."))
        w.wait(lambda: len(f.approvals(first["conversation_id"])) == 1, what="a new ask after the resident wrote")


# ---- a model server that repeats its tool call ids ---------------------------------------------------------------------
QUEUE: list[str] = []


def fixed_ids(out):
    """The model server numbers its tool calls by position only for book_hotel: the id repeats in every reply."""
    if isinstance(out, list):
        QUEUE[:] = ["c" * 32, *("bookcall0".ljust(32, "0") if n == "book_hotel" else real_uuid.uuid4().hex for n, _ in out)]
    return out


def stub():
    return SimpleNamespace(hex=QUEUE.pop(0) if QUEUE else real_uuid.uuid4().hex)


def two_rounds(c: Call):
    """Each message of the resident books once (first Sunrise, then Lotus)."""
    def inner():
        if "Lotus" in c.last_user:
            want, key = ck.BOOK2, "Lotus"
        elif ck.CHOOSE in c.last_user:
            want, key = ck.BOOK, "Sunrise"
        else:
            return ck.asking(c) or "Said."
        turn = c.after_user()
        if turn.called("book_hotel") == 0:
            return [("book_hotel", want)]
        got = " ".join(turn.results("book_hotel"))
        if turn.called("CaseSay") == 0:
            if "BK-77" in got:
                return say(f"Booked: BK-77 ({key}). Anything else?", "reply", evidence_of(got)[:1])
            return say(f"The {key} booking did not happen: {got[:60]}", "reply")
        return "Said."
    return fixed_ids(inner())


def test_a_repeated_tool_call_id_does_not_carry_a_verdict_to_a_new_request(tmp_path, monkeypatch):
    monkeypatch.setattr(fake_llm, "uuid", SimpleNamespace(uuid4=stub))
    with world(tmp_path, two_rounds, **TOOLS) as w:
        f = w.flow
        start, first, second = trip(w)
        [appr] = f.approvals(first["conversation_id"])
        assert f.decide(appr["approval_id"], f.decide_body(start, first, appr)).status_code == 202
        w.wait_state(first["workflow_id"], "awaiting_user")
        w.quiet()
        assert len(ck.BOOKED) == 1
        f.reply(start, first, message=text_of("Lotus too please."))  # a different hotel, the same call id
        w.wait(lambda: len(f.approvals(first["conversation_id"])) == 1, 20, "the second ask")
        assert w.sql("select count(distinct tool_call_id), count(*) from wf_approvals") == [(1, 2)]
