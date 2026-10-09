"""The room digest: a short, per-agent view of what the others did.

Built for the tail of the prompt so the static prefix stays cacheable. Only
items added since the agent's last view are listed in full.
"""
from __future__ import annotations

from .store import Item
from .view import CaseView

_RULES = (
    "Rules: cite evidence ids (E..) for every fact (CaseFact); say so with "
    "CaseGap when you cannot find something; challenge a peer's fact with "
    "CaseChallenge (max {rounds} rounds per fact, then the leader decides); "
    "only the leader decides."
)


def _clip(text: str, n: int) -> str:
    text = " ".join(str(text).split())
    return text if len(text) <= n else text[: n - 1] + "…"


def describe(it: Item, width: int = 160) -> str:
    d = it.data
    if it.kind == "fact":
        ev = ",".join(d.get("evidence", []))
        return f"{it.ref} {it.author}: {_clip(d.get('text', ''), width)} [{ev}]"
    if it.kind == "evidence":
        return f"{it.ref} {it.author} ran {d.get('tool', '?')}: {_clip(d.get('text', ''), width)}"
    if it.kind == "question":
        return f"{it.ref} {it.author} asks {it.addressee}: {_clip(d.get('text', ''), width)}"
    if it.kind == "challenge":
        return (f"{it.ref} {it.author} challenges {d.get('fact')} "
                f"(author {it.addressee}): {_clip(d.get('reason', ''), width)}")
    if it.kind == "answer":
        tag = " RETRACTED" if d.get("retract") else ""
        return f"{it.ref} {it.author} answers {d.get('to_ref')}{tag}: {_clip(d.get('text', ''), width)}"
    if it.kind == "gap":
        return f"{it.ref} {it.author} does not know: {_clip(d.get('topic', ''), width)} (tried: {_clip(d.get('tried', ''), 80)})"
    if it.kind == "decision":
        return f"{it.ref} leader decided: {_clip(d.get('text', ''), width)}"
    if it.kind == "report":
        return f"{it.ref} {it.author} reported: {_clip(d.get('summary', ''), width)}"
    return f"{it.ref} {it.author}: {_clip(str(d), width)}"


def render_digest(
    *, case_id: str, summary: str, viewer: str, role: str, view: CaseView,
    new_items: list[Item], members: list[dict], max_chars: int, max_rounds: int,
) -> str:
    """Return the digest text, or an empty string when there is nothing new."""
    waiting = []
    for q in view.open_questions():
        if q.addressee == viewer:
            waiting.append(f"{q.ref} from {q.author}: {_clip(q.data.get('text', ''), 140)}")
    for c in view.open_challenges():
        if c.addressee == viewer:
            waiting.append(f"{c.ref} on your {c.data.get('fact')}: {_clip(c.data.get('reason', ''), 140)}")

    # Tool output of others stays out of the digest (cost); CaseRead has it.
    visible_new = [i for i in new_items if i.kind != "evidence" and i.author != viewer]
    if not waiting and not visible_new:
        return ""

    status = []
    for m in members:
        name = m["agent_name"] or m["agent_id"][:6]
        if name == viewer:
            continue
        rep = view.reports.get(name)
        pend = sum(1 for q in view.open_questions() if q.addressee == name)
        state = f"reported {rep.ref}" if rep else "working"
        if pend:
            state += f", {pend} question(s) waiting"
        status.append(f"{name}({m['role']}): {state}")

    head = [f'<room-digest case="{case_id}" you="{viewer}" role="{role}">',
            f"Ticket: {_clip(summary, 220)}"]
    if status:
        head.append("Members: " + "; ".join(status))
    if waiting:
        head.append("WAITING ON YOU: " + " | ".join(waiting))
    tail = ["</room-digest>"]
    rules = _RULES.format(rounds=max_rounds)

    lines = [describe(i) for i in visible_new]
    budget = max_chars - sum(len(x) + 1 for x in head + tail) - len(rules) - 40
    kept: list[str] = []
    for line in reversed(lines):  # newest first when trimming
        if budget - len(line) - 1 < 0:
            break
        kept.append(line)
        budget -= len(line) + 1
    kept.reverse()
    dropped = len(lines) - len(kept)
    body = []
    if kept or dropped:
        body.append("New since your last view:")
        if dropped:
            body.append(f"(+{dropped} older item(s); use CaseRead to see them)")
        body.extend(kept)
    body.append(rules)
    return "\n".join(head + body + tail)
