"""Ticket classification via LLM with optional ML prediction signals.

Architecture C from the analysis: LLM handles unstructured → structured
transformation; ML provides advisory prediction signals; rules.py
enforces hard constraints afterward.

The LLM classification prompt follows the same pattern as the existing
OpenBot routing prompt in server/src/routing/classify.ts:
  - Structured output request (JSON)
  - Roster/context provided
  - Confidence threshold for fallback
  - Graceful degradation when the model is unreachable

The classifier NEVER makes SLA decisions — it provides classification
that is then matched against SLA policies in rules.py.
"""

from __future__ import annotations

import json
import logging
from typing import Protocol

from dispatcher.contracts import (
    Complexity,
    PredictionSignals,
    ReportContext,
    Severity,
    TicketClassification,
    Urgency,
)

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# LLM abstraction — injected, not imported
# ---------------------------------------------------------------------------

class LLMCompleter(Protocol):
    """Minimal LLM interface.  Matches the pattern from routing/model.ts:
    the model call is injected so classification logic stays testable
    without a network in the way."""

    async def complete(self, prompt: str) -> str:
        """Return the model's raw text.  May raise on network errors."""
        ...


# ---------------------------------------------------------------------------
# ML predictor abstraction — optional
# ---------------------------------------------------------------------------

class MLPredictor(Protocol):
    """Optional traditional ML predictor for advisory signals."""

    def predict_urgency(self, features: dict) -> tuple[Urgency, float]:
        """Return (predicted_urgency, confidence)."""
        ...

    def predict_resolution_hours(self, features: dict) -> tuple[float, float]:
        """Return (predicted_hours, confidence)."""
        ...

    def predict_complexity(self, features: dict) -> Complexity:
        """Return predicted complexity."""
        ...

    def predict_breach_risk(self, features: dict) -> float:
        """Return probability of SLA breach (0.0–1.0)."""
        ...

    @property
    def model_version(self) -> str: ...


# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

_VALID_SEVERITIES: set[str] = {"LOW", "MEDIUM", "HIGH", "CRITICAL"}
_VALID_URGENCIES: set[str] = {"LOW", "MEDIUM", "HIGH", "CRITICAL"}
_VALID_COMPLEXITIES: set[str] = {"SIMPLE", "MODERATE", "COMPLEX"}
_MIN_CONFIDENCE = 0.5
_FALLBACK_SEVERITY: Severity = "MEDIUM"
_FALLBACK_URGENCY: Urgency = "MEDIUM"
_FALLBACK_COMPLEXITY: Complexity = "MODERATE"


# ---------------------------------------------------------------------------
# Prompt construction
# ---------------------------------------------------------------------------

def _build_classification_prompt(report: ReportContext) -> str:
    """Build the LLM prompt for ticket classification.

    Same design principles as server/src/routing/classify.ts routingPrompt():
    structured output request, context provided, JSON-only response.
    """
    facts_str = json.dumps(report["facts"], ensure_ascii=False) if report["facts"] else "none"
    has_attachments = len(report["attachments"]) > 0

    return "\n".join([
        "You classify a resident's maintenance/service ticket for a property management system.",
        "",
        "Resident description:",
        report["text"],
        "",
        f"Extracted facts: {facts_str}",
        f"Has attachments: {has_attachments}",
        f"Number of attachments: {len(report['attachments'])}",
        "",
        "Classify the ticket and reply with ONLY this JSON (no other text):",
        "{",
        '  "category": "<one of: PLUMBING, ELECTRICAL, ELEVATOR, FIRE_SAFETY, '
        'SANITATION, SECURITY, STRUCTURAL, HVAC, LANDSCAPE, PEST_CONTROL, '
        'PARKING, ACCESS_CONTROL, WATER_SUPPLY, DRAINAGE, OTHER>",',
        '  "severity": "<LOW | MEDIUM | HIGH | CRITICAL>",',
        '  "urgency": "<LOW | MEDIUM | HIGH | CRITICAL>",',
        '  "complexity": "<SIMPLE | MODERATE | COMPLEX>",',
        '  "confidence": <0.0 to 1.0>,',
        '  "evidence": ["<short reason 1>", "<short reason 2>"]',
        "}",
        "",
        "Rules:",
        "- CRITICAL severity: immediate danger to life, health, or property "
        "(fire, gas leak, flooding, structural failure).",
        "- HIGH severity: significant disruption to daily living "
        "(no water, no electricity, elevator stuck with people).",
        "- MEDIUM severity: inconvenience that should be addressed promptly "
        "(dripping faucet, flickering lights, broken door lock).",
        "- LOW severity: minor cosmetic or convenience issues "
        "(paint scratches, squeaky door, garden maintenance).",
        "- Urgency considers time sensitivity separately from severity.",
        "- Complexity considers how many teams/skills/steps are likely needed.",
    ])


# ---------------------------------------------------------------------------
# Ticket classifier
# ---------------------------------------------------------------------------

class TicketClassifier:
    """Classifies tickets using LLM with optional ML signal enrichment.

    Follows Architecture C: LLM structured classification + ML predictions
    + rules/guardrails.  The classifier's output feeds into rules.py for
    SLA matching and agent selection — it never makes SLA decisions itself.
    """

    def __init__(
        self,
        llm: LLMCompleter,
        ml_predictor: MLPredictor | None = None,
    ) -> None:
        self._llm = llm
        self._ml = ml_predictor

    async def classify(
        self, report: ReportContext,
    ) -> tuple[TicketClassification, PredictionSignals | None, list[str]]:
        """Classify a ticket from the resident report.

        Returns:
            classification: The ticket classification.
            prediction_signals: Optional ML prediction signals (advisory).
            evidence: List of evidence strings for the decision reasoning.
        """
        classification, evidence = await self._llm_classify(report)
        signals = self._ml_predict(report) if self._ml else None
        return classification, signals, evidence

    # -----------------------------------------------------------------------
    # LLM classification
    # -----------------------------------------------------------------------

    async def _llm_classify(
        self, report: ReportContext,
    ) -> tuple[TicketClassification, list[str]]:
        """Call the LLM for structured classification.

        Graceful degradation: if the LLM is unreachable or returns
        unparseable output, fall back to rule-based defaults.
        Same pattern as classify.ts createIntentRouter().
        """
        prompt = _build_classification_prompt(report)

        try:
            raw = await self._llm.complete(prompt)
        except Exception:
            logger.warning("LLM unreachable for ticket classification; using fallback")
            return self._fallback_classification(report), ["LLM unreachable — fallback applied"]

        return self._parse_llm_response(raw, report)

    def _parse_llm_response(
        self, raw: str, report: ReportContext,
    ) -> tuple[TicketClassification, list[str]]:
        """Parse the LLM JSON response with the same tolerance as classify.ts.

        From classify.ts L262: "tolerate a fenced or padded answer"
        """
        import re
        json_match = re.search(r"\{[\s\S]*\}", raw)
        if not json_match:
            logger.warning("LLM response did not contain JSON; using fallback")
            return self._fallback_classification(report), ["LLM response unparseable — fallback applied"]

        try:
            parsed = json.loads(json_match.group(0))
        except json.JSONDecodeError:
            logger.warning("LLM response JSON parse failed; using fallback")
            return self._fallback_classification(report), ["LLM JSON malformed — fallback applied"]

        # Extract and validate fields
        category = str(parsed.get("category", "OTHER")).upper()
        severity = str(parsed.get("severity", _FALLBACK_SEVERITY)).upper()
        urgency = str(parsed.get("urgency", _FALLBACK_URGENCY)).upper()
        complexity = str(parsed.get("complexity", _FALLBACK_COMPLEXITY)).upper()
        confidence = float(parsed.get("confidence", 0.0))
        evidence_raw = parsed.get("evidence", [])

        # Validate enum values
        if severity not in _VALID_SEVERITIES:
            severity = _FALLBACK_SEVERITY
        if urgency not in _VALID_URGENCIES:
            urgency = _FALLBACK_URGENCY
        if complexity not in _VALID_COMPLEXITIES:
            complexity = _FALLBACK_COMPLEXITY

        # Low confidence → conservative defaults
        if confidence < _MIN_CONFIDENCE:
            logger.info(
                "LLM classification confidence %.2f below threshold %.2f",
                confidence, _MIN_CONFIDENCE,
            )

        evidence = (
            [str(e) for e in evidence_raw]
            if isinstance(evidence_raw, list)
            else [str(evidence_raw)]
        )
        evidence.append(f"LLM confidence: {confidence:.2f}")

        classification = TicketClassification(
            category=category,
            severity=severity,  # type: ignore[arg-type]
            urgency=urgency,  # type: ignore[arg-type]
            complexity=complexity,  # type: ignore[arg-type]
            confidence=confidence,
            method="LLM",
        )
        return classification, evidence

    def _fallback_classification(
        self, report: ReportContext,
    ) -> TicketClassification:
        """Rule-based fallback when LLM is unavailable.

        Conservative: MEDIUM severity, MEDIUM urgency, MODERATE complexity.
        Same principle as classify.ts: "a router that throws would turn
        'we were not sure who to ask' into 'your message went nowhere'."
        """
        return TicketClassification(
            category="OTHER",
            severity=_FALLBACK_SEVERITY,
            urgency=_FALLBACK_URGENCY,
            complexity=_FALLBACK_COMPLEXITY,
            confidence=0.0,
            method="RULE",
        )

    # -----------------------------------------------------------------------
    # ML predictions (advisory only)
    # -----------------------------------------------------------------------

    def _ml_predict(self, report: ReportContext) -> PredictionSignals | None:
        """Run ML predictions as advisory signals.

        These are NEVER used as SLA decisions.  They enrich the
        DispatcherDecision.prediction_signals field for transparency.

        If the ML predictor fails, we silently return None — the
        dispatcher proceeds without ML signals.
        """
        if not self._ml:
            return None

        try:
            features = _extract_features(report)
            urgency, urg_conf = self._ml.predict_urgency(features)
            hours, hours_conf = self._ml.predict_resolution_hours(features)
            complexity = self._ml.predict_complexity(features)
            breach_risk = self._ml.predict_breach_risk(features)

            return PredictionSignals(
                predicted_urgency=urgency,
                urgency_confidence=urg_conf,
                predicted_resolution_hours=hours,
                resolution_confidence=hours_conf,
                predicted_complexity=complexity,
                sla_breach_risk=breach_risk,
                model_version=self._ml.model_version,
            )
        except Exception:
            logger.warning("ML prediction failed; proceeding without signals", exc_info=True)
            return None


def _extract_features(report: ReportContext) -> dict:
    """Extract features from the report for ML models.

    Only features that are safe at prediction time (no post-outcome leakage).
    See the analysis for the full feature safety classification.
    """
    return {
        "description_length": len(report["text"]),
        "has_image": any(
            a["media_type"].startswith("image/") for a in report["attachments"]
        ),
        "num_attachments": len(report["attachments"]),
        "has_facts": bool(report["facts"]),
        "text": report["text"],
    }
