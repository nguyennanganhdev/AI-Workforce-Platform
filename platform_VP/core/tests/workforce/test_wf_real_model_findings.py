"""Defects a real model exposed (gpt-5.4-mini, 13/10/2026) that the scripted model never reached."""
from __future__ import annotations

import pytest

from awp.guard.checks import check_text, claims
from awp.workforce.lookup import rules_of

RULES = rules_of({})


@pytest.mark.parametrize("text", [
    "I cannot confirm that the repair visit for Monday has been booked because provider confirmation is not available.",
    "The visit has not been booked yet.",
    "I could not verify whether the pipe has been fixed.",
    "Tôi chưa thể xác nhận việc đã hoàn thành.",
    "Thợ chưa báo là đã sửa xong.",
])
def test_denying_that_work_is_done_is_not_a_claim_that_it_is(text):
    assert check_text(text, ["Please book a repair visit for Monday."], RULES, []) == []


@pytest.mark.parametrize("text", [
    "The repair visit has been booked.",
    "No worries, the pipe has been fixed.",          # the negation is in another clause
    "I am not sure when. The visit has been booked.",  # and in another sentence
    "Không sao, thợ đã sửa xong.",
    "It has not been cancelled: it has been booked.",
])
def test_a_claim_that_work_is_done_still_needs_the_systems_word(text):
    assert any("work is not done" in p for p in check_text(text, ["Please book a repair visit."], RULES, []))


def test_a_phrase_counts_when_any_of_its_uses_is_a_claim():
    low = "it has not been booked. correction: it has been booked."
    assert claims(low, "has been booked")
    assert not claims("it has not been booked.", "has been booked")


def test_an_informing_line_needs_something_new_to_inform_about(tmp_path):
    """gpt-5.4-mini sent five 'still pending' lines in one turn. A second informing line is sent only when a tool
    result or an event was recorded since the last one."""
    from enginekit import world
    import scripts
    from test_wf_s3_guard import evidence, started
    from test_wf_say import ok

    with world(tmp_path, scripts.interactive) as w:
        room, _ = started(w)  # the leader has said one thing already
        out = room.say("Your request is still pending.")
        assert not ok(out) and "Nothing new has happened" in out[0]
        assert not ok(room.say("There is still no update."))
        evidence(w, room, "lookup_ticket", "T-1001: status assigned")
        assert ok(room.say("Your request has an update: it is assigned."))
        assert not ok(room.say("It remains assigned."))
        assert ok(room.say("Is tomorrow morning fine for you?", "reply"))  # asking is not informing again
