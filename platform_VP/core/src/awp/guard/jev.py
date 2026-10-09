"""Optional Jev gate. Off unless AWP_JEV_ENABLED is set and a key exists.

Jev (TypeSafe AI) is a small classifier that returns a calibrated probability
for a typed question. It is used here as a cheap second opinion on one
question only: is the claim supported by the cited evidence? The deterministic
checks in `checks.py` always run first and are never replaced by it.

Vendor claims about price and speed are unverified until measured on our own
data, so every call is timed and counted for that comparison.
"""
from __future__ import annotations

import logging
import os
import time
from dataclasses import dataclass, field
from typing import Protocol

log = logging.getLogger("awp.jev")


class SupportJudge(Protocol):
    async def support(self, claim: str, evidence: list[str]) -> float | None:
        """Probability in [0, 1] that the evidence supports the claim, or
        None when no opinion is available."""


@dataclass
class JudgeStats:
    calls: int = 0
    failures: int = 0
    total_seconds: float = 0.0
    input_tokens: int = 0
    blocked: int = 0

    def as_dict(self) -> dict:
        return {
            "calls": self.calls, "failures": self.failures,
            "blocked": self.blocked, "input_tokens": self.input_tokens,
            "avg_seconds": (self.total_seconds / self.calls) if self.calls else 0.0,
        }


@dataclass
class JevJudge:
    """Support judge backed by `agentscope.classifier.JevClassifierModel`."""

    model: object  # a ClassifierModelBase
    stats: JudgeStats = field(default_factory=JudgeStats)

    async def support(self, claim: str, evidence: list[str]) -> float | None:
        from agentscope.classifier import BinaryCriteria, BinaryQuestion

        question = BinaryQuestion(
            instructions=(
                "Is the CLAIM fully supported by the EVIDENCE? Do not use "
                "outside knowledge."),
            criteria=BinaryCriteria(
                true="Every fact in the claim is stated in the evidence.",
                false="The claim adds, changes or contradicts a fact."),
        )
        started = time.perf_counter()
        self.stats.calls += 1
        try:
            res = await self.model(
                state={"claim": claim, "evidence": evidence},
                questions={"supported": question})
            answer = res.content["supported"]
            if res.usage is not None:
                self.stats.input_tokens += res.usage.input_tokens
            return float(answer.probability)
        except Exception as error:  # a gate must never take the case down
            self.stats.failures += 1
            log.warning("Jev support check failed: %s", error)
            return None
        finally:
            self.stats.total_seconds += time.perf_counter() - started


def build_judge(enabled: bool, model_name: str, env: dict | None = None) -> SupportJudge | None:
    """Return a Jev judge when enabled and usable, else None (never raises)."""
    if not enabled:
        return None
    e = os.environ if env is None else env
    key = e.get("TYPESAFE_API_KEY")
    if not key:
        log.warning("AWP_JEV_ENABLED is set but TYPESAFE_API_KEY is missing; Jev off")
        return None
    try:
        from agentscope.classifier import JevClassifierModel
        from agentscope.credential import TypeSafeCredential

        cred = TypeSafeCredential(api_key=key, base_url=e.get("TYPESAFE_BASE_URL") or None)
        return JevJudge(JevClassifierModel(cred, model=model_name))
    except ImportError as error:
        log.warning("Jev unavailable (%s); install agentscope[classifier-jev]", error)
        return None
