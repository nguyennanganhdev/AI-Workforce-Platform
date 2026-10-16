"""Helpers for the B2 tests (builder, evaluation, release): scripted agents for the sandbox and short calls of the API.

The scripts are what the fake model answers for one profile key (`fake_llm.MODE["agents"]`, or the `script` of
`enginekit.world` for the leader `supervisor`). They say nothing about a real model: they make an agent that behaves
well, and agents that do one thing wrong, so that the checks can be shown to tell them apart.
"""
from __future__ import annotations

from conftest import ADM
from fake_llm import MODE, Call

P = "/platform/v1/profiles"
B = "/platform/v1/builder/sessions"
TECH = {"key": "tech", "name": "Technician", "mission": "a technician who checks tickets.", "handles": ["tickets"],
        "refuses": ["prices"], "tools_allow": ["lookup_ticket"], "model_tier": "cheap"}
DESK = {"key": "supervisor", "name": "case-leader", "role": "leader", "mission": "the leader of a repair case.",
        "team": ["tech"], "refuses": ["legal advice"], "tools_allow": ["lookup_ticket"], "model_tier": "strong"}


# ---- scripted specialists ------------------------------------------------------------------------
def careful(c: Call):
    """Looks the thing up, says what it does not know, reports without a figure of its own."""
    if "lookup_ticket" in c.names and c.called("lookup_ticket") == 0:
        return [("lookup_ticket", {"ticket_id": "T-1001"})]
    if c.called("CaseGap") == 0:
        return [("CaseGap", {"topic": "what was asked for", "tried": "lookup_ticket"})]
    if c.called("TeamSay") == 0:
        return [("TeamSay", {"content": "I could not find what was asked; see my gap.", "to": None})]
    return "Reported."


def inventing(c: Call):
    """Reports a price and a date that no tool gave it."""
    if c.called("TeamSay") == 0:
        return [("TeamSay", {"content": "The repair costs 2000000 VND and will be done on 15/11.", "to": None})]
    return "Reported."


def silent(c: Call):
    return "I have nothing to add."


# ---- scripted leaders ------------------------------------------------------------------------------
def good_leader(c: Call):
    """Answers a greeting itself, brings the technician in for ticket work, hands back what it refuses, and says that it
    does not know when the look-up finds nothing."""
    import re
    turn = c.after_user()
    text = c.last_user.lower()
    if turn.called("CaseSay") or turn.called("CaseFinalize"):
        return "Done."
    if "hello" in text:
        return [("CaseSay", {"text": "I can help with repair requests.", "expects": "reply"})]
    if "legal advice" in text:
        return [("CaseFinalize", {"answer": "I cannot help with that; a person will follow up.", "outcome": "needs_human",
                                  "unknowns": ["outside what this desk handles"]})]
    if "whoever is responsible" in text:
        if c.called("TeamCreate") == 0:
            return [("TeamCreate", {"name": "case-team", "description": "Check the ticket"})]
        if c.called("AgentCreate") == 0:
            return [("AgentCreate", {"name": "tech", "description": "Checks the ticket", "subagent_type": "tech",
                                     "prompt": "Check the ticket and record what you find."})]
        if re.search(r"\bR\d+ \S+ reported:", c.blob):
            return [("CaseFinalize", {"answer": "The technician could not find it; a person will follow up.",
                                      "outcome": "needs_human", "unknowns": ["the ticket"]})]
        return "Waiting for the technician."
    if turn.called("lookup_ticket") == 0:
        return [("lookup_ticket", {"ticket_id": "T-1001"})]
    return [("CaseFinalize", {"answer": "I could not find that; a person will follow up.", "outcome": "needs_human",
                              "unknowns": ["what was asked for"]})]


def inventing_leader(c: Call):
    """Tries an invented fee first; the guard refuses it and it then says something true (as scripts.ungrounded)."""
    turn = c.after_user()
    if turn.called("CaseSay") == 0:
        return [("CaseSay", {"text": "The repair fee is 2000000 VND.", "expects": "reply"})]
    if turn.called("CaseSay") == 1 and turn.results("CaseSay")[0].startswith("Not sent"):
        return [("CaseSay", {"text": "I cannot give a fee yet; a person will confirm it.", "expects": "reply"})]
    return "Said."


# ---- the API ---------------------------------------------------------------------------------------------
def draft(env, body: dict, headers=ADM) -> dict:
    r = env.post(P, body, headers)
    assert r.status_code == 201, r.text
    return r.json()


def run_eval(env, key: str, version: int = 1, headers=ADM, wait: float = 90.0):
    """Start an evaluation and wait for its end: the response (200 with the finished run)."""
    return env.post(f"{P}/{key}/versions/{version}/evals", {"wait_seconds": wait}, headers)


def evaluated(env, key: str, version: int = 1, headers=ADM) -> dict:
    r = run_eval(env, key, version, headers)
    assert r.status_code == 200, r.text
    return r.json()


def publish(env, key: str, version: int = 1, headers=ADM, **body):
    """A plain publish: the gate decides (conftest.publish is the override other tests use)."""
    return env.post(f"{P}/{key}/versions/{version}/publish", body, headers)


def verdicts(run: dict) -> dict:
    """case name -> {check name: ok} of a finished run."""
    return {c["name"]: {v["check"]: v["ok"] for v in c["checks"]} for c in run["results"]}


def agents(**scripts) -> None:
    """Script the agents of these profile keys (cleared by enginekit.world when it ends)."""
    MODE["agents"] = dict(scripts)


def session(env, headers=ADM) -> str:
    r = env.post(B, {}, headers)
    assert r.status_code == 201, r.text
    return r.json()["session_id"]


def say(env, sid: str, text: str, headers=ADM):
    return env.post(f"{B}/{sid}/messages", {"text": text}, headers)


def apply(env, sid: str, items=None, headers=ADM):
    return env.post(f"{B}/{sid}/apply", {} if items is None else {"items": items}, headers)


def parallel(env, calls) -> list:
    """Send the requests [(method, path, body, headers)] at the same moment, as tasks of the app's own event loop: what
    two people pressing the button together are to the platform."""
    import asyncio

    import httpx

    async def go():
        async with httpx.AsyncClient(transport=httpx.ASGITransport(app=env.app), base_url="http://t", timeout=120) as c:
            return await asyncio.gather(*[c.request(m, path, json=body, headers=h) for m, path, body, h in calls])
    return env.http.portal.call(go)
