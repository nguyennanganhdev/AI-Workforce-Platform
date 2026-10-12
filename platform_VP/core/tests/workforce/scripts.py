"""Leader scripts for the engine tests: what the scripted model answers at each step of a turn.

A script is called with a `Call` (tests/fake_llm.py) for every model request of the leader. It looks at
what started the turn (`c.last_user`) and what the turn did so far (`c.after_user()`), and answers with
a list of (tool, arguments) or plain text. The ids it cites are the ones the room hands out: E1 is what
the resident said first (tool "resident"), E2 the next evidence of the workflow, and so on.
"""
from __future__ import annotations

from enginekit import evidence_of
from fake_llm import Call

TICKET = "Ticket T-1001: leaking pipe, status waiting for plumber."


def say(text: str, expects: str = "none", cites: list[str] | None = None) -> list:
    return [("CaseSay", {"text": text, "expects": expects, "cites": cites or []})]


def lookup(c: Call):
    """Read-only: look the ticket up, answer with CaseFinalize."""
    turn = c.after_user()
    if turn.called("lookup_ticket") == 0:
        return [("lookup_ticket", {"ticket_id": "T-1001"})]
    ev = evidence_of(" ".join(turn.results("lookup_ticket")))
    if turn.called("CaseFinalize") == 0:
        return [("CaseFinalize", {"answer": TICKET, "outcome": "resolved", "cites": ev[:1]})]
    return "Done."


def interactive(c: Call):
    """First message: ask when. Second (it names 14): echo the figure it was given, ask to confirm."""
    if c.after_user().called("CaseSay"):
        return "Said."
    if "14 gi" in c.last_user:  # not just "14": the message id in the text is random hex
        return say("Noted: 14. Can you confirm?", "confirmation", ["E2"])
    return say("What time suits you?", "reply")


def silent(c: Call):
    return "I thought about it."


def nudged_once(c: Call):
    """Silent until it is nudged, then it speaks."""
    if "<platform-nudge" in c.last_user and not c.after_user().called("CaseSay"):
        return say("Sorry, what do you need?", "reply")
    return "Hmm."


def consult(c: Call):
    """Brings in the technician; says nothing until the technician's report wakes it."""
    import re
    if c.called("TeamCreate") == 0:
        return [("TeamCreate", {"name": "case-team", "description": "Check the ticket"})]
    if c.called("AgentCreate") == 0:
        return [("AgentCreate", {"name": "tech", "description": "Checks the ticket", "subagent_type": "tech",
                                 "prompt": "Look up ticket T-1001 and record what you find."})]
    facts = re.findall(r"\b(F\d+) tech:", c.blob)
    if facts and not c.after_user().called("CaseSay"):
        return say("Ticket T-1001 is waiting for the plumber.", "reply", facts[:1])
    return "Waiting for the specialists."


def ungrounded(c: Call):
    """Invents a fee first; once the guard refuses it, says only what it can stand behind."""
    turn = c.after_user()
    refused = [r for r in turn.results("CaseSay") if r.startswith("Not sent")]
    if turn.called("CaseSay") == 0:
        return say("The repair fee is 2000000 VND.", "reply")
    if refused and turn.called("CaseSay") == 1:
        return say("I cannot give a fee yet; a person will confirm it.", "reply")
    return "Said."


def two_answers(c: Call):
    if c.after_user().called("CaseSay"):
        return "Said."
    return say("Second answer." if "SECOND" in c.last_user else "First answer.", "reply")


def topics(c: Call):
    """One answer per ticket, by what the resident asked about: the two tickets must never mix."""
    if c.after_user().called("CaseSay"):
        return "Said."
    if "hotel" in c.last_user:
        return say("Hotel: which night do you want?", "reply")
    return say("Pipe: we will send a plumber.", "reply")


def obedient(c: Call):
    """Does what the resident's text says, so the guard (not the script) has to stop it."""
    turn = c.after_user()
    if turn.called("CaseSay") == 0:
        return say("Done, your pipe is fixed.", "reply")
    if turn.called("CaseSay") == 1 and turn.results("CaseSay")[0].startswith("Not sent"):
        return say("I have noted your request; nothing is done yet.", "reply")
    return "Said."


def budget(c: Call):
    """Looks something up; once the budget is spent it can only wrap up."""
    if "budget for this case is spent" in c.blob:
        if c.after_user().called("CaseFinalize"):
            return "Done."
        return [("CaseFinalize", {"answer": "I could not verify this.", "outcome": "needs_human",
                                  "unknowns": ["budget spent before the ticket was checked"]})]
    return [("lookup_ticket", {"ticket_id": "T-1001"})]
