"""Where a workflow rests after the leader's turns (spec section 5), as a pure function.

`decide` reads facts the database holds and returns what to do; nothing here touches I/O, so the
whole table is tested without an app. The order of the rules is the spec's: the first one that
applies wins.
"""
from __future__ import annotations

from dataclasses import dataclass

MAX_NUDGES = 2
OUTCOMES = ("resolved", "needs_human", "cannot_resolve")


@dataclass(frozen=True)
class Facts:
    state: str
    approvals: int = 0  # approvals still pending
    parked: bool = False  # the latest turn ended waiting for a permission (RequireUserConfirmEvent)
    workers_pending: bool = False  # a worker has not reported, or a question/challenge is open
    said: str | None = None  # the strongest expects of the leader's messages in this chain; None: it said nothing
    ops_open: int = 0  # operations still moving: sent, pending, or unknown with a status query to settle them
    ops_lost: int = 0  # operations nobody can find out about: unknown, and no status query to ask
    acted: bool = False  # an operation, an approval or a request for confirmation exists: more than a look-up
    done: bool = False  # a side effect really happened: an operation completed, or a tool the resident agreed to returned a result
    failed: bool = False  # actions were taken and none of them took effect (they all failed): there is nothing to confirm
    outcome: str | None = None  # the CaseFinalize outcome of this chain
    auto_close: bool = True  # route policy: a read-only answer closes by itself
    nudges: int = 0  # nudges already sent in this chain
    owed: str | None = None  # what the leader asked the resident last and they have not answered yet (reply | confirmation)


@dataclass(frozen=True)
class Decision:
    kind: str  # stay | rest | close | attention | nudge
    state: str | None = None
    reason: str | None = None
    safe_say: bool = False  # also tell the resident the route's safe reply


STAY = Decision("stay")
BUSY = ("accepted", "active")


def rest(state: str, reason: str | None = None) -> Decision:
    return Decision("rest", state, reason)


def decide(f: Facts) -> Decision:
    """What to do with a workflow whose leader has gone quiet.

    A workflow that is not working (resting, needs attention, closed) is left alone: the facts of its
    chain were already acted on, and only a new job or a worker's report starts another one.
    """
    if f.state not in BUSY:
        return STAY
    if f.approvals or f.parked:
        return rest("awaiting_approval")
    if f.workers_pending:
        return STAY  # a report wakes the leader again; this is not the end of the chain
    if f.ops_lost:  # whatever the leader said, a person has to find out what became of it (P0 item 24)
        return Decision("attention", "needs_attention", "operation_unknown", safe_say=f.said is None)
    if f.said == "reply":
        return rest("awaiting_user")
    if f.said == "confirmation":
        if f.ops_open:  # work is still going: there is nothing to confirm yet, and POST close would be refused
            return rest("waiting_external_event")
        if f.failed:  # nothing was done: closing is not what the resident can be asked for, they can only answer
            return rest("awaiting_user", "operation_failed")
        return rest("awaiting_confirmation")
    if f.owed == "reply" and f.said in (None, "none") and f.outcome is None:
        return rest("awaiting_user")  # an event woke the leader while the resident owes it an answer: the question stands
    if f.ops_open:
        return rest("waiting_external_event")
    if f.outcome == "resolved":
        if f.failed:  # "resolved" cannot stand on actions that all failed: the resident must not be asked to confirm them
            return Decision("attention", "needs_attention", "needs_human")
        if not f.acted and f.auto_close:
            return Decision("close", "closed", "answered")
        return rest("awaiting_confirmation")
    if f.outcome in ("needs_human", "cannot_resolve"):
        return Decision("attention", "needs_attention", f.outcome)
    if f.said == "none":  # it informed the resident and needs nothing: the workflow waits for their next word
        return rest("awaiting_confirmation") if f.done else rest("awaiting_user", "informed")  # what was done is theirs to confirm (contract 13.2)
    if f.nudges < MAX_NUDGES:
        return Decision("nudge")
    return Decision("attention", "needs_attention", "leader_silent", safe_say=True)
