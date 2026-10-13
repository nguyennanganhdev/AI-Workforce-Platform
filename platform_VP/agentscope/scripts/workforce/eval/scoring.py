"""Deterministic checks for one collaboration scenario.

Pure functions only (no network) so they are unit-tested and give the same
verdict on every run. An optional LLM judge in ``run_collab_eval.py`` adds a
rubric score on top; it never replaces these checks.
"""

from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass, field

_SCALED = re.compile(
    r"(\d+(?:[.,]\d+)?)\s*(triệu|trieu|tr\b|million|m\b|nghìn|nghin|ngàn|ngan|k\b)",
    re.IGNORECASE,
)
_PLAIN = re.compile(r"\d{1,3}(?:[.,\s]\d{3})+|\d+")


def fold(text: str) -> str:
    """Lower-case and strip Vietnamese accents for tolerant matching."""

    decomposed = unicodedata.normalize("NFKD", text.casefold()).replace("đ", "d")
    return "".join(c for c in decomposed if not unicodedata.combining(c))


def amounts(text: str) -> set[int]:
    """Every money-like integer in ``text`` (``9.500.000``, ``9,5 triệu``, ``250k``)."""

    found: set[int] = set()
    for number, unit in _SCALED.findall(text):
        value = float(number.replace(",", "."))
        unit = fold(unit)
        scale = 1_000_000 if unit.startswith(("trieu", "tr", "million", "m")) else 1_000
        found.add(round(value * scale))
    without_scaled = _SCALED.sub(" ", text)
    for token in _PLAIN.findall(without_scaled):
        digits = re.sub(r"[.,\s]", "", token)
        if digits:
            found.add(int(digits))
    return found


@dataclass
class CheckResult:
    name: str
    passed: bool
    detail: str = ""


@dataclass
class ScenarioVerdict:
    scenario_id: str
    checks: list[CheckResult] = field(default_factory=list)

    @property
    def passed(self) -> bool:
        return all(check.passed for check in self.checks)

    @property
    def score(self) -> float:
        if not self.checks:
            return 0.0
        return round(sum(c.passed for c in self.checks) / len(self.checks), 3)


def check_answer(answer: str, spec: dict) -> list[CheckResult]:
    """Apply the answer checks declared for one turn of a scenario."""

    results: list[CheckResult] = []
    folded = fold(answer)

    for phrase in spec.get("must_include_all", []):
        ok = fold(phrase) in folded
        results.append(CheckResult(f"có '{phrase}'", ok))

    any_of = spec.get("must_include_any", [])
    if any_of:
        hit = next((p for p in any_of if fold(p) in folded), None)
        results.append(
            CheckResult(
                "có một trong " + ", ".join(repr(p) for p in any_of),
                hit is not None,
                hit or "",
            )
        )

    for phrase in spec.get("must_not_include", []):
        ok = fold(phrase) not in folded
        results.append(CheckResult(f"không bịa '{phrase}'", ok))

    wanted_amounts = spec.get("amounts_any", [])
    if wanted_amounts:
        present = amounts(answer)
        hit = next((a for a in wanted_amounts if a in present), None)
        results.append(
            CheckResult(
                "có số tiền " + " hoặc ".join(f"{a:,}" for a in wanted_amounts),
                hit is not None,
                f"{hit:,}" if hit else "",
            )
        )

    for amount in spec.get("amounts_all", []):
        results.append(CheckResult(f"có số tiền {amount:,}", amount in amounts(answer)))

    if spec.get("expect_question"):
        results.append(CheckResult("hỏi lại khách", "?" in answer))
    if spec.get("expect_no_question"):
        results.append(CheckResult("không hỏi lại khi đã đủ thông tin", "?" not in answer))
    if spec.get("not_incomplete", True):
        incomplete = any(
            marker in folded
            for marker in (
                fold("Nhóm chưa hoàn tất yêu cầu"),
                "the team did not finish",
            )
        )
        results.append(CheckResult("không bị dừng giữa chừng", not incomplete))
    return results


def check_metrics(metrics: dict, spec: dict) -> list[CheckResult]:
    """Apply collaboration/cost limits declared for a scenario."""

    results: list[CheckResult] = []
    total = metrics.get("total", {})
    tokens = int(total.get("input_tokens", 0)) + int(total.get("output_tokens", 0))
    if "max_total_tokens" in spec:
        results.append(
            CheckResult(
                f"tổng token ≤ {spec['max_total_tokens']:,}",
                tokens <= spec["max_total_tokens"],
                f"{tokens:,}",
            )
        )
    branches = metrics.get("branches", [])
    if "min_agents" in spec:
        workers = [b for b in branches if b.get("model_calls", 0) > 0]
        results.append(
            CheckResult(
                f"≥ {spec['min_agents']} agent tham gia",
                len(workers) >= spec["min_agents"],
                str(len(workers)),
            )
        )
    if spec.get("no_stopped_branch", True) and branches:
        stopped = [b for b in branches if b.get("status") == "stopped"]
        results.append(
            CheckResult(
                "không nhánh nào bị runtime dừng",
                not stopped,
                "; ".join(f"{b.get('agent_name')}: {b.get('reason')}" for b in stopped),
            )
        )
    return results


def summarize(metrics: dict) -> dict:
    """Flatten the numbers reported per scenario in the report table."""

    total = metrics.get("total", {})
    branches = metrics.get("branches", [])
    events = metrics.get("event_counts", {})
    return {
        "input_tokens": int(total.get("input_tokens", 0)),
        "cached_input_tokens": int(total.get("cached_input_tokens", 0)),
        "output_tokens": int(total.get("output_tokens", 0)),
        "cache_hit_ratio": float(total.get("cache_hit_ratio", 0.0)),
        "model_calls": int(total.get("calls", 0)),
        "agents": len([b for b in branches if b.get("model_calls", 0) > 0]),
        "exchanges": sum(int(b.get("exchanges", 0)) for b in branches),
        "evidence_rejections": sum(int(b.get("evidence_rejections", 0)) for b in branches),
        "verifications": sum(int(b.get("verifications", 0)) for b in branches),
        "stopped_branches": len([b for b in branches if b.get("status") == "stopped"]),
        "peer_questions": int(events.get("question", 0)),
        "peer_answers": int(events.get("answer", 0)),
    }
