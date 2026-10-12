"""The event schema of a provider integration (spec 7.3): what each event type means in the partner's words, which
of its data may be shown, and the ordering rules that keep an old event from undoing a later one.

Pure: nothing here reads the database. `Rule` is one entry of `wf_integrations.event_schema`; `public` and `render`
are the ONLY ways provider data leaves the inbox (for the resident, for the public log, for the model), so what a
provider adds to `data` beyond the schema's `public_fields` is stored for audit and never shown to anyone.
"""
from __future__ import annotations

import json
import math
import string
from dataclasses import dataclass
from decimal import Decimal, InvalidOperation
from typing import Any, NamedTuple

from .jobs import clean, verified
from .partner_result import DONE_WORDS

FIELD_CAP = 200  # characters of one text value
BLOB_CAP = 3000  # serialized size of one structured value (a list of cost lines, say)
MESSAGE_CAP = 1000
EVIDENCE_CAP = 4000
DEPTH, WIDTH = 3, 50
COUNT_MAX = 10**9


@dataclass(frozen=True)
class Rule:
    event_type: str
    status: str  # the partner's word for the state this event reports (a label the admin chose)
    rank: int
    terminal: bool
    outcome: str | None
    public_status: str | None
    public_fields: tuple[str, ...]
    message: str | None
    wake: bool
    evidence: bool
    reopen: bool
    types: tuple[tuple[str, str], ...] = ()  # (field, "text" | "count") the admin declared

    @property
    def keeps_evidence(self) -> bool:
        """The case file records what the event said when the schema asks for it, and always when the leader is woken (it is
        handed the fields, so it must be able to cite them) or the event says the work is done (the platform's mark)."""
        return self.evidence or self.wake or self.done

    @property
    def done(self) -> bool:
        """A terminal event that says the work was carried out (the outcome, else the status, is a word of DONE_WORDS)."""
        return self.terminal and (self.outcome or self.status).lower() in DONE_WORDS

    @property
    def op_status(self) -> str:
        """What the operation becomes: still moving, or finished one way or the other."""
        return ("completed" if self.done else "failed") if self.terminal else "pending"


def mode_of(schema: dict) -> str:
    return schema.get("version_mode", "snapshot")


def rule_of(schema: dict, event_type: str) -> Rule | None:
    d = (schema.get("events") or {}).get(event_type)
    if d is None:
        return None
    return Rule(event_type, d["status"], d["rank"], bool(d.get("terminal")), d.get("outcome"), d.get("public_status"),
                tuple(d.get("public_fields") or ()), d.get("message"), bool(d.get("wake")), bool(d.get("evidence")),
                bool(d.get("reopen")), tuple((d.get("field_types") or {}).items()))


def placeholders(message: str | None) -> list[str]:
    return [n for _, n, _, _ in string.Formatter().parse(message or "") if n]


def plain(value: Any, kind: str = "text") -> str | None:
    """What a value may print as inside a sentence, or None when it is not fit to be printed there: nothing, a yes/no, a
    negative or non-finite number, a count that is not a whole number, a line that is empty or longer than FIELD_CAP.
    A resident reads the result, so it never says 'about  minutes' or 'about true minutes'."""
    if isinstance(value, bool) or value is None:
        return None
    if kind == "count":
        return str(value) if isinstance(value, int) and 0 <= value <= COUNT_MAX else None
    if isinstance(value, (int, float)):
        return _shown(value) if math.isfinite(value) and value >= 0 else None
    if isinstance(value, str):
        line = " ".join(clean(value, 10 * FIELD_CAP).split())
        return line if line and len(line) <= FIELD_CAP else None
    return None


def data_errors(rule: Rule, data: dict) -> list[dict]:
    """What is wrong with `data` for this event type: a value the message needs must be there and fit to be printed, and a
    field the schema typed must have that type wherever it is sent."""
    kinds = dict(rule.types)
    bad = []
    for name in dict.fromkeys(placeholders(rule.message)):
        if name not in data or plain(data[name], kinds.get(name, "text")) is None:
            bad.append({"field": f"data.{name}", "reason": "required by the event schema's message, as a plain value"})
    for name, kind in kinds.items():
        if name in data and plain(data[name], kind) is None and not any(b["field"] == f"data.{name}" for b in bad):
            bad.append({"field": f"data.{name}", "reason": f"must be a {'whole number of 0 or more' if kind == 'count' else 'plain value'}"})
    return bad


# ---- what may leave the inbox ----------------------------------------------------------------------------------
def _safe(value: Any, depth: int = 0) -> Any:
    if isinstance(value, bool) or value is None:
        return value
    if isinstance(value, int):
        return value
    if isinstance(value, float):
        return value if math.isfinite(value) else None
    if isinstance(value, str):
        return clean(value, FIELD_CAP)
    if depth >= DEPTH:
        return "[too deep]"
    if isinstance(value, list):
        cut = [f"[{len(value) - WIDTH} more not shown]"] if len(value) > WIDTH else []
        return [*(_safe(x, depth + 1) for x in value[:WIDTH]), *cut]
    if isinstance(value, dict):
        out = {clean(str(k), 40): _safe(v, depth + 1) for k, v in list(value.items())[:WIDTH]}
        return {**out, "[more]": f"{len(value) - WIDTH} more not shown"} if len(value) > WIDTH else out
    return None


def public(rule: Rule, data: dict) -> dict:
    """The fields of `data` the schema allows, cleaned and bounded. Nothing else of `data` goes anywhere."""
    out: dict[str, Any] = {}
    for name in rule.public_fields:
        if name in data:
            value = _safe(data[name])
            if len(json.dumps(value, ensure_ascii=False)) > BLOB_CAP:
                value = "[too long]"
            out[name] = value
    return out


def _shown(value: Any) -> str:
    return value if isinstance(value, str) else json.dumps(value, ensure_ascii=False, separators=(",", ":"))


def render(rule: Rule, data: dict) -> str | None:
    """The message of the schema with its placeholders filled from allowed fields, or None when there is none or a value is
    not fit to print (plain). One line per value, no control characters, no platform tags, bounded: a resident reads it."""
    if not rule.message:
        return None
    kinds, values = dict(rule.types), {}
    for name in placeholders(rule.message):
        text = plain(data.get(name), kinds.get(name, "text")) if name in rule.public_fields else None
        if text is None:
            return None
        values[name] = text
    return rule.message.format(**values)[:MESSAGE_CAP]


def quotes(fields: dict) -> bool:
    """The event states a cost (the lines and the total CaseAskConsent works with): an earlier cost is no longer the one."""
    return "items" in fields or "total" in fields


def cost_note(fields: dict) -> str:
    """A cost list whose total is not the sum of its lines is said so, wherever it is shown: the leader asks the resident
    to agree to a figure and must not pick one of the two without telling."""
    items, total = fields.get("items"), fields.get("total")
    if not isinstance(items, list) or isinstance(total, bool) or not isinstance(total, (int, float)):
        return ""
    try:
        amounts = [Decimal(str(i["amount"])) for i in items if isinstance(i, dict) and not isinstance(i.get("amount"), bool)]
        if len(amounts) != len(items):
            return ""  # a cut list or lines without an amount: no sum to compare
        added, said = sum(amounts, Decimal(0)), Decimal(str(total))
    except (InvalidOperation, KeyError, ValueError):
        return ""
    if added == said:
        return ""
    return (f"NOTE: the provider's total ({_shown(total)}) is not the sum of its own lines ({added.normalize():f}). Tell the "
            "resident so and do not ask them to agree to either figure until it is clear.")


def evidence_text(rule: Rule, fields: dict) -> str:
    """What the case file records of the event, built from allowed fields only. A finished-and-done event carries the platform's
    own mark (jobs.verified) in front: it is what lets the leader say the work is done."""
    body = "; ".join(f"{k}: {_shown(v)}" for k, v in fields.items())
    note = cost_note(fields)
    text = f"{rule.event_type}: status {rule.status}" + (f"; {body}" if body else "") + (f" ({note})" if note else "")
    mark = verified(rule.outcome or rule.status) if rule.done else ""
    return mark + text[:EVIDENCE_CAP]


# ---- ordering (contract 10.3) ----------------------------------------------------------------------------------
class Seen(NamedTuple):
    """What the operation already holds. `version` is the highest provider version the platform has consumed: applied, or
    judged old news in its turn (so the provider's next version is the next one, not a gap)."""
    status: str  # intent | sent | pending | unknown | completed | failed
    rank: int | None
    version: int | None


class Verdict(NamedTuple):
    kind: str  # apply | duplicate | stale | conflict | hold
    code: str | None = None
    consume: bool = False  # stale, but the version was the next one in line: it counts as seen
    first: bool = False  # a hold for the start of a delta stream, not for a gap in the middle of it


APPLY, DUPLICATE, HOLD = Verdict("apply"), Verdict("duplicate"), Verdict("hold", "VERSION_GAP")
WAIT_FIRST = Verdict("hold", "VERSION_GAP", first=True)
STALE, CONFLICT = Verdict("stale", "STALE_EVENT"), Verdict("conflict", "VERSION_CONFLICT")
STALE_SEEN = Verdict("stale", "STALE_EVENT", consume=True)


def verdict(rule: Rule, mode: str, version: int | None, seen: Seen, same: bool, aged: bool = False) -> Verdict:
    """Whether an event may change the operation. `same`: the platform already consumed an event with this version (or, without
    versions, the last one applied) of this type and these data. `aged`: the wait for the start of a delta stream is over.

    A version that is not higher never moves anything back. The same version with other content is a conflict, with the same
    content a duplicate. A finished operation is only changed by an event type the schema declares a correction (`reopen`),
    and that is settled before any wait: late news of finished work never holds. In delta mode a version must follow the one
    before it: a gap holds the event, and so does the first event of an operation when it is not version 1 (the earlier
    ones may be on their way) until `aged`. Then the rank: a lower one is old news. Without versions only the rank and the
    finished state decide (the time of the event proves nothing).
    """
    cur = seen.version
    finished = seen.status in ("completed", "failed") and not rule.reopen
    in_line = False  # the version is the next one: whatever is decided, it was seen
    if version is not None and cur is not None:
        if version < cur:
            return STALE
        if version == cur:
            return DUPLICATE if same else CONFLICT
        if mode == "delta":
            if version != cur + 1:
                return STALE if finished else HOLD
            in_line = True
    elif version is not None and mode == "delta":
        if version > 1 and not aged:
            return STALE if finished else WAIT_FIRST
        in_line = True
    stale = STALE_SEEN if in_line else STALE
    if rule.reopen:
        return APPLY
    if finished:
        return stale
    if seen.rank is not None and rule.rank < seen.rank:
        return stale
    if version is None and seen.rank == rule.rank and same:
        return DUPLICATE
    return APPLY
