"""Deterministic grounding checks. No model is involved in this file.

The one rule that holds in every domain: an agent may only state a number
or a code that appears in the evidence it cites. A route adds phrase
rules on top (for example "do not say the work is finished unless the
system says so").

A figure is compared as a whole token, never as a substring of a larger
number: "5000" is not supported by "1250000". Separators are ignored
("1.500.000" equals "1500000"). Numbers written with single spaces
("0901 234 567") also match when joined ("0901234567").
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any

_NUMBER = re.compile(r"\d+(?:[.,:/\-]\d+)*")
_LIST_MARKER = re.compile(r"(?m)^\s*\d+[.)]\s")
_EVIDENCE_ID = re.compile(r"^E\d+$")
_MAX_JOIN = 4


def digits(text: str) -> str:
    return re.sub(r"\D", "", text)


def figures(text: str) -> list[str]:
    """Numbers, dates, hours, phone numbers and codes written in `text`."""
    return _NUMBER.findall(_LIST_MARKER.sub("", text))


def _supported_digits(sources: list[str]) -> set[str]:
    """Digit strings a claim may use: each source number, and runs of numbers
    that are separated by single spaces joined together."""
    known: set[str] = set()
    for text in sources:
        matches = list(_NUMBER.finditer(text))
        for i, m in enumerate(matches):
            joined = digits(m.group())
            known.add(joined)
            end = m.end()
            for nxt in matches[i + 1:i + _MAX_JOIN]:
                if text[end:nxt.start()] != " ":
                    break
                joined += digits(nxt.group())
                known.add(joined)
                end = nxt.end()
    return known


def figures_missing(text: str, sources: list[str]) -> list[str]:
    """Figures in `text` that no source states."""
    known = _supported_digits(sources)
    return [f for f in figures(text) if digits(f) not in known]


def leaves(value: Any) -> list[str]:
    if isinstance(value, dict):
        return [x for v in value.values() for x in leaves(v)]
    if isinstance(value, list):
        return [x for v in value for x in leaves(v)]
    return [str(value)]


def figures_text(fields: dict) -> str:
    """What the guard reads of structured data: its values, without keys or indexes."""
    return "\n".join(leaves(fields))


# An amount written out ("two million", "hai triệu", "hai trieu") has no digits for `figures_missing` to
# compare, so a model could state an unsourced price in words. The magnitude words give it away.
_AMOUNT_WORDS = re.compile(r"\b(?:thousand|million|billion|ngh[iì]n|ng[aà]n|tri[eệ]u|tỷ)\b", re.I)


def written_amounts(text: str) -> list[str]:
    """Magnitude words that write an amount out in words, which no source can be compared with."""
    return sorted({m.group().lower() for m in _AMOUNT_WORDS.finditer(text)})


# "I cannot confirm that it has been booked" denies the claim, it does not make it. A phrase counts only when no
# negation stands before it in its own clause (a comma or a full stop ends the clause: "No worries, it has been
# fixed" is still a claim). Found with a real model: refusing the honest sentence pushed it to a vaguer, wrong one.
_NEGATION = re.compile(r"\b(?:not|cannot|unable|never|no|without|whether|chưa|không|chẳng|chua|khong)\b|n't\b", re.I)
_CLAUSE_END = re.compile(r"[.!?;,:\n]")


def claims(low: str, phrase: str) -> bool:
    """Does `low` (lower case) state `phrase`, rather than deny it?"""
    at = low.find(phrase)
    while at != -1:
        clause = _CLAUSE_END.split(low[:at])[-1]
        if not _NEGATION.search(clause):
            return True
        at = low.find(phrase, at + 1)
    return False


@dataclass
class PhraseRule:
    """Forbid `phrases` unless the trusted evidence contains one of `unless`."""

    phrases: tuple[str, ...]
    reason: str
    unless: tuple[str, ...] = ()


@dataclass
class Rules:
    """Rules of a route, applied after the generic figure check."""

    phrase_rules: list[PhraseRule] = field(default_factory=list)
    forbidden_words: tuple[str, ...] = ()  # words that must not reach the reader
    # Sent instead of an answer that could not be grounded after repeated tries.
    safe_reply: str = "I could not verify this with the information available. A person will follow up."


def check_text(text: str, sources: list[str], rules: Rules | None = None,
               trusted: list[str] | None = None) -> list[str]:
    """Return human-readable reasons the text is not grounded (empty = ok).

    `sources` are all cited items. `trusted` are the ones that come from tools
    or the domain's own systems (not from what a requester typed); phrase
    rules look for their `unless` markers only there. Defaults to `sources`.
    """
    problems: list[str] = []
    missing = figures_missing(text, sources)
    if missing:
        problems.append(
            "figures not found in the cited evidence: " + ", ".join(missing[:5]))
    if rules:
        low = text.lower()
        evidence = " ".join(sources if trusted is None else trusted).lower()
        for w in rules.forbidden_words:
            if re.search(rf"\b{re.escape(w.lower())}\b", low):
                problems.append(f"uses an internal word: {w}")
        for rule in rules.phrase_rules:
            hit = next((p for p in rule.phrases if claims(low, p.lower())), None)
            if hit and not any(u.lower() in evidence for u in rule.unless):
                problems.append(f"{rule.reason} (phrase: '{hit}')")
    return problems


def split_refs(refs: list[str]) -> tuple[list[str], list[str]]:
    """Split cited ids into evidence ids and fact ids; unknown shapes are dropped."""
    ev = [r for r in refs if _EVIDENCE_ID.match(r)]
    fa = [r for r in refs if re.match(r"^F\d+$", r)]
    return ev, fa
