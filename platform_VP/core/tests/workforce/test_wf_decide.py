"""`decide`: where a workflow rests after the leader's turns (spec section 5), as a table (slice S3)."""
from __future__ import annotations

import itertools

import pytest

from awp.workforce.decide import MAX_NUDGES, Decision, Facts, decide
from awp.workforce.workflows import STATES, check

BUSY = "active"


def f(**kw) -> Facts:
    return Facts(state=kw.pop("state", BUSY), **kw)


# (facts, expected kind, state, reason) in the order of the spec: the first rule that applies wins
TABLE = [
    # 1 pending approvals (or a turn parked on one) -> awaiting_approval, whatever else is true
    (f(approvals=1), "rest", "awaiting_approval", None),
    (f(parked=True), "rest", "awaiting_approval", None),
    (f(approvals=1, workers_pending=True, said="reply", ops_open=1, outcome="resolved"), "rest", "awaiting_approval", None),
    # 2 the team is still working (or a question is open): the chain is not over
    (f(workers_pending=True), "stay", None, None),
    (f(workers_pending=True, said="reply"), "stay", None, None),
    (f(workers_pending=True, outcome="resolved"), "stay", None, None),
    # 3 what the leader said last
    (f(said="reply"), "rest", "awaiting_user", None),
    (f(said="confirmation"), "rest", "awaiting_confirmation", None),
    (f(said="reply", ops_open=2), "rest", "awaiting_user", None),
    (f(said="confirmation", outcome="resolved"), "rest", "awaiting_confirmation", None),
    # 3b confirmation is asked only for work that is over and was done (T2 review): running work is waited for, and when
    # all of it failed the resident can only answer
    (f(said="confirmation", ops_open=1), "rest", "waiting_external_event", None),
    (f(said="confirmation", ops_open=1, acted=True, failed=True), "rest", "waiting_external_event", None),
    (f(said="confirmation", acted=True, failed=True), "rest", "awaiting_user", "operation_failed"),
    (f(said="confirmation", acted=True, done=True), "rest", "awaiting_confirmation", None),
    # 3c a question the resident has not answered stands when an event wakes the leader and it only informs
    (f(said="none", owed="reply", ops_open=1), "rest", "awaiting_user", None),
    (f(owed="reply", ops_open=1), "rest", "awaiting_user", None),
    (f(said="none", owed="confirmation", ops_open=1), "rest", "waiting_external_event", None),
    (f(said="none", owed="reply", outcome="needs_human"), "attention", "needs_attention", "needs_human"),
    # 4 an operation is still tracked
    (f(ops_open=1), "rest", "waiting_external_event", None),
    (f(said="none", ops_open=1), "rest", "waiting_external_event", None),
    (f(ops_open=1, outcome="resolved", acted=True), "rest", "waiting_external_event", None),
    # 5 CaseFinalize
    (f(outcome="resolved"), "close", "closed", "answered"),
    (f(outcome="resolved", said="none"), "close", "closed", "answered"),
    (f(outcome="resolved", auto_close=False), "rest", "awaiting_confirmation", None),
    (f(outcome="resolved", acted=True), "rest", "awaiting_confirmation", None),
    (f(outcome="needs_human"), "attention", "needs_attention", "needs_human"),
    (f(outcome="cannot_resolve", acted=True), "attention", "needs_attention", "cannot_resolve"),
    # 6 it only informed the resident (expects none): the turn is finished, the workflow waits for their word
    (f(said="none"), "rest", "awaiting_user", "informed"),
    (f(said="none", nudges=MAX_NUDGES + 3), "rest", "awaiting_user", "informed"),
    (f(said="none", acted=True), "rest", "awaiting_user", "informed"),
    # 6b ...unless a side effect really happened (contract 13.2): what was done is the resident's to confirm
    (f(said="none", done=True), "rest", "awaiting_confirmation", None),
    (f(said="none", done=True, acted=True, nudges=MAX_NUDGES), "rest", "awaiting_confirmation", None),
    (f(said="none", done=True, ops_open=1), "rest", "waiting_external_event", None),
    (f(said="reply", done=True), "rest", "awaiting_user", None),
    (f(done=True), "nudge", None, None),  # a side effect and no word to the resident is still silence
    # 7 nothing at all: nudge twice, then attention with the safe reply
    (f(), "nudge", None, None),
    (f(nudges=1), "nudge", None, None),
    (f(nudges=MAX_NUDGES), "attention", "needs_attention", "leader_silent"),
    (f(nudges=MAX_NUDGES + 3), "attention", "needs_attention", "leader_silent"),
]


@pytest.mark.parametrize("facts,kind,state,reason", TABLE, ids=[str(i) for i in range(len(TABLE))])
def test_the_spec_table(facts, kind, state, reason):
    d = decide(facts)
    assert (d.kind, d.state, d.reason) == (kind, state, reason)


def test_only_the_silent_leader_gets_the_safe_reply():
    assert decide(f(nudges=MAX_NUDGES)).safe_say is True
    assert not any(decide(facts).safe_say for facts, kind, *_ in TABLE if kind != "attention")
    assert decide(f(outcome="needs_human")).safe_say is False  # its own answer was already sent


@pytest.mark.parametrize("state", [s for s in STATES if s not in ("accepted", "active")])
def test_a_workflow_that_is_not_working_is_left_alone(state):
    for facts in (f(state=state), f(state=state, said="reply"), f(state=state, outcome="resolved"),
                  f(state=state, approvals=1)):
        assert decide(facts) == Decision("stay")


def test_accepted_is_busy_too():
    assert decide(f(state="accepted", said="reply")).state == "awaiting_user"


def test_every_combination_obeys_the_rules_of_the_spec():
    """3000 combinations of the facts: not a second copy of the table but the properties it must keep."""
    said = (None, "none", "reply", "confirmation")
    outcomes = (None, "resolved", "needs_human", "cannot_resolve")
    n = 0
    for approvals, parked, workers, s, ops, acted, out, auto, nudges, done, failed, owed in itertools.product(
            (0, 1), (False, True), (False, True), said, (0, 2), (False, True), outcomes, (False, True), (0, 1, 2),
            (False, True), (False, True), (None, "reply")):
        facts = f(approvals=approvals, parked=parked, workers_pending=workers, said=s, ops_open=ops,
                  acted=acted, outcome=out, auto_close=auto, nudges=nudges, done=done, failed=failed, owed=owed)
        d = decide(facts)
        n += 1
        if d.state:  # every move is one the state machine allows
            assert d.state in STATES
            check(BUSY, d.state)
        if approvals or parked:
            assert d.state == "awaiting_approval"
        elif workers:
            assert d.kind == "stay"
        else:
            assert d.kind != "stay"  # a working leader with nobody to wait for always ends somewhere
        if d.kind == "close":  # only a plain look-up that the policy lets close by itself
            assert out == "resolved" and not acted and auto and not (approvals or parked or workers or ops)
            assert s not in ("reply", "confirmation")
        if d.kind == "nudge":
            assert nudges < MAX_NUDGES and out is None and s is None and not (ops or workers or approvals or parked)
        if d.reason == "informed":  # the leader spoke and asked for nothing: never nudged, never silent
            assert s == "none" and out is None and not (ops or workers or approvals or parked or done)
        if d.reason == "leader_silent":
            assert nudges >= MAX_NUDGES and out is None and s is None
        if d.state == "waiting_external_event":
            assert ops and s != "reply" and not (owed == "reply" and out is None and s in (None, "none"))
        if s == "confirmation" and not (approvals or parked or workers):  # only work that is over is asked to be confirmed
            assert (d.state == "waiting_external_event") == bool(ops)
            assert d.state != "awaiting_confirmation" or not (ops or failed)
        if d.reason == "operation_failed":
            assert s == "confirmation" and failed and not ops
    assert n == 2 * 2 * 2 * 4 * 2 * 2 * 4 * 2 * 3 * 2 * 2 * 2
