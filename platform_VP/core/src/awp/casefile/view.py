"""Fold the append-only items into the current state of the case."""
from __future__ import annotations

from dataclasses import dataclass, field

from .store import Item


@dataclass
class FactView:
    item: Item
    status: str = "asserted"  # asserted | challenged | defended | retracted


@dataclass
class CaseView:
    evidence: dict[str, Item] = field(default_factory=dict)
    facts: dict[str, FactView] = field(default_factory=dict)
    questions: dict[str, Item] = field(default_factory=dict)
    challenges: dict[str, Item] = field(default_factory=dict)
    answers_to: dict[str, Item] = field(default_factory=dict)  # target ref -> last answer
    gaps: list[Item] = field(default_factory=list)
    decisions: list[Item] = field(default_factory=list)
    reports: dict[str, Item] = field(default_factory=dict)  # author -> last report
    final: Item | None = None
    challenge_rounds: dict[str, int] = field(default_factory=dict)  # fact ref -> count
    # Evidence of an operation (data["op"]) that no longer stands where the evidence said it did: a provider reported the
    # work done and then reopened it. What it proves is withdrawn; its figures can still be cited.
    withdrawn: set[str] = field(default_factory=set)

    def open_questions(self) -> list[Item]:
        return [q for ref, q in self.questions.items() if ref not in self.answers_to]

    def open_challenges(self) -> list[Item]:
        return [c for ref, c in self.challenges.items() if ref not in self.answers_to]

    def live_facts(self) -> dict[str, FactView]:
        return {r: f for r, f in self.facts.items() if f.status != "retracted"}


def build_view(items: list[Item]) -> CaseView:
    v = CaseView()
    for it in items:
        k = it.kind
        if k == "evidence":
            v.evidence[it.ref] = it
        elif k == "fact":
            v.facts[it.ref] = FactView(it)
        elif k == "question":
            v.questions[it.ref] = it
        elif k == "challenge":
            v.challenges[it.ref] = it
            target = it.data.get("fact")
            if target in v.facts:
                v.challenge_rounds[target] = v.challenge_rounds.get(target, 0) + 1
                if v.facts[target].status != "retracted":
                    v.facts[target].status = "challenged"
        elif k == "answer":
            ref = it.data.get("to_ref")
            if not ref:
                continue
            v.answers_to[ref] = it
            ch = v.challenges.get(ref)
            if ch is not None:
                fact = v.facts.get(ch.data.get("fact"))
                if fact is not None:
                    fact.status = "retracted" if it.data.get("retract") else "defended"
        elif k == "gap":
            v.gaps.append(it)
        elif k == "decision":
            v.decisions.append(it)
            for ref in it.data.get("retract", []):
                if ref in v.facts:
                    v.facts[ref].status = "retracted"
            for ref in it.data.get("keep", []):
                if ref in v.facts and v.facts[ref].status != "retracted":
                    v.facts[ref].status = "defended"
            settled = set(it.data.get("retract", [])) | set(it.data.get("keep", []))
            for cref, ch in v.challenges.items():
                if ch.data.get("fact") in settled and cref not in v.answers_to:
                    v.answers_to[cref] = it
        elif k == "report":
            v.reports[it.author] = it
        elif k == "final":
            v.final = it
    return v
