"""The checks of an evaluation case, as pure functions of what a sandbox run left behind.

No model judges anything here. A check reads the record of the run (`Observation`): the tool calls of the agent
under test, what it said or wrote, what its tools returned, where the workflow came to rest and what it cost.
The same record always gives the same verdict.
"""
from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from typing import Annotated, Any

from pydantic import BaseModel, ConfigDict, Field, StringConstraints, field_validator

from ..guard import figures_missing, written_amounts
from ..workforce.workflows import STATES

TOOL_NAME = r"^[A-Za-z0-9_-]{1,64}$"
# The tools through which an agent states something: a figure it tries to put there counts, also when the platform's
# guard refused the call (the resident was protected, but the agent did invent it).
STATING = {"CaseSay": "text", "CaseFinalize": "answer", "CaseFact": "text", "CaseAnswer": "text", "TeamSay": "content"}
_REF = re.compile(r"\b[EFQCAGDRNXIT]\d+\b")  # ids of the case file ("see F1, G2") are not figures
MAX_ARGS = 2000  # characters of a call spec's arguments as JSON: every list of cases and every run reads them back
Phrase = Annotated[str, StringConstraints(min_length=1, max_length=500)]


class CallSpec(BaseModel):
    """A tool call, optionally with arguments it must carry (the others are free)."""

    model_config = ConfigDict(extra="forbid")
    tool: str = Field(pattern=TOOL_NAME)
    args: dict[str, Any] = Field(default_factory=dict)

    @field_validator("args")
    @classmethod
    def _small(cls, v):
        if len(json.dumps(v, ensure_ascii=False)) > MAX_ARGS:
            raise ValueError(f"the arguments are longer than {MAX_ARGS} characters")
        return v


Call = str | CallSpec


class Checks(BaseModel):
    model_config = ConfigDict(extra="forbid")
    must_call: list[Call] = Field(default_factory=list, max_length=20)
    must_not_call: list[Call] = Field(default_factory=list, max_length=20)
    must_contain: list[Phrase] = Field(default_factory=list, max_length=20)
    must_not_contain: list[Phrase] = Field(default_factory=list, max_length=20)
    must_record_gap: bool = False
    grounded: bool = False
    expected_state: list[str] = Field(default_factory=list, max_length=len(STATES))  # a leader's workflow rests in one of these
    max_cost_usd: float | None = Field(default=None, ge=0)

    @field_validator("expected_state", mode="before")
    @classmethod
    def _one_or_many(cls, v):
        return [v] if isinstance(v, str) else v

    @field_validator("expected_state")
    @classmethod
    def _known(cls, v):
        bad = [s for s in v if s not in STATES]
        if bad:
            raise ValueError(f"unknown workflow states: {bad}")
        return v

    @field_validator("must_call", "must_not_call")
    @classmethod
    def _names(cls, v):
        for c in v:
            if isinstance(c, str) and not re.match(TOOL_NAME, c):
                raise ValueError(f"not a tool name: {c!r}")
        return v

    def empty(self) -> bool:
        return self == Checks()


@dataclass
class Observation:
    """What one sandbox run left behind, about the agent under test."""

    calls: list[dict] = field(default_factory=list)  # its tool calls in order: {"tool", "input" (JSON text), "ok"}
    outputs: list[str] = field(default_factory=list)  # what it told the resident or wrote into the case file
    sources: list[str] = field(default_factory=list)  # tool results and the input: where a figure may come from
    gaps: int = 0  # times it said it does not know (CaseGap, or a final answer that lists unknowns)
    state: str | None = None  # where the workflow rested
    cost_usd: float = 0.0
    timed_out: bool = False
    responded: bool = True  # it produced an answer of its own (a leader spoke, a specialist reported)


def _args(call: dict) -> dict:
    try:
        value = json.loads(call.get("input") or "{}")
        return value if isinstance(value, dict) else {}
    except ValueError:
        return {}


def _matches(spec: Call, call: dict) -> bool:
    if isinstance(spec, str):
        return call["tool"] == spec
    if call["tool"] != spec.tool:
        return False
    args = _args(call)
    return all(args.get(k) == v for k, v in spec.args.items())


def _show(spec: Call) -> str:
    return spec if isinstance(spec, str) else f"{spec.tool}({json.dumps(spec.args, ensure_ascii=False)})"


def stated(obs: Observation) -> list[str]:
    """Everything the agent stated or tried to state: its outputs, and the text of every stating call."""
    tried = [str(_args(c).get(STATING[c["tool"]]) or "") for c in obs.calls if c["tool"] in STATING]
    return [_REF.sub("", t) for t in [*obs.outputs, *tried] if t]


def ungrounded(obs: Observation) -> list[str]:
    """Figures the agent stated that no tool result and no input states, and amounts written out in words."""
    bad: list[str] = []
    for text in stated(obs):
        bad += figures_missing(text, obs.sources)
        bad += [f"'{w}' (an amount in words)" for w in written_amounts(text)]
    return list(dict.fromkeys(bad))


def evaluate(checks: Checks, obs: Observation) -> list[dict]:
    """One verdict per check that the case asks for: {"check", "ok", "detail"}. A run that did not come to rest
    in time fails as a whole, whatever else is true of it."""
    out: list[dict] = []

    def verdict(name: str, ok: bool, detail: str = "") -> None:
        out.append({"check": name, "ok": bool(ok), "detail": detail[:300]})

    if obs.timed_out:
        verdict("finished", False, "the run did not come to rest in time")
    elif not obs.responded:  # an agent that never answered would pass every check that only forbids things
        verdict("responded", False, "the agent under test never answered (it did not run, failed, or stayed silent)")
    for spec in checks.must_call:
        verdict("must_call", any(_matches(spec, c) for c in obs.calls), _show(spec))
    for spec in checks.must_not_call:
        verdict("must_not_call", not any(_matches(spec, c) for c in obs.calls), _show(spec))
    said = "\n".join(obs.outputs).lower()
    for text in checks.must_contain:
        verdict("must_contain", text.lower() in said, text)
    for text in checks.must_not_contain:
        verdict("must_not_contain", text.lower() not in said, text)
    if checks.must_record_gap:
        verdict("must_record_gap", obs.gaps > 0, "" if obs.gaps else "it never said that it does not know")
    if checks.grounded:
        bad = ungrounded(obs)
        verdict("grounded", not bad, ("figures no evidence states: " + ", ".join(bad[:8])) if bad else "")
    if checks.expected_state:
        verdict("expected_state", obs.state in checks.expected_state,
                f"rested in {obs.state}, expected one of {checks.expected_state}")
    if checks.max_cost_usd is not None:
        verdict("max_cost_usd", obs.cost_usd <= checks.max_cost_usd, f"cost {obs.cost_usd:.6f} USD")
    return out

