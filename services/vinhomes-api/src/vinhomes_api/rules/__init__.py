"""Deterministic Vinhomes domain rule evaluation."""

from .engine import A5RuleEngine, RuleDecision, RuleDefinition, RuleEvaluation
from .demo import (
    DEMO_MATERIAL_APPROVAL_THRESHOLD_MINOR,
    DEMO_RULE_VERSION,
    build_demo_rule_engine,
)

__all__ = [
    "A5RuleEngine",
    "DEMO_MATERIAL_APPROVAL_THRESHOLD_MINOR",
    "DEMO_RULE_VERSION",
    "RuleDecision",
    "RuleDefinition",
    "RuleEvaluation",
    "build_demo_rule_engine",
]
