"""Explicit demo-only Field Operations rules; never treat these as production policy."""

from ..db.action_request import RequestedByType
from .engine import A5RuleEngine, RuleDecision, RuleDefinition


DEMO_RULE_VERSION = "field-operations-demo-v1"
DEMO_MATERIAL_APPROVAL_THRESHOLD_MINOR = 500_000


def build_demo_rule_engine() -> A5RuleEngine:
    return A5RuleEngine(
        [
            RuleDefinition(
                action_type="CLEAN_AREA",
                decision=RuleDecision.ALLOW,
                reason_code="DEMO_ROUTINE_ACTION",
                rule_version=DEMO_RULE_VERSION,
                allowed_requester_types=frozenset(
                    {RequestedByType.HUMAN, RequestedByType.AGENT}
                ),
            ),
            RuleDefinition(
                action_type="WATER_PLANTS",
                decision=RuleDecision.ALLOW,
                reason_code="DEMO_ROUTINE_ACTION",
                rule_version=DEMO_RULE_VERSION,
                allowed_requester_types=frozenset(
                    {RequestedByType.HUMAN, RequestedByType.AGENT}
                ),
            ),
            RuleDefinition(
                action_type="HIGH_RISK_MAINTENANCE",
                decision=RuleDecision.REQUIRE_APPROVAL,
                reason_code="DEMO_HIGH_RISK_APPROVAL",
                rule_version=DEMO_RULE_VERSION,
            ),
            RuleDefinition(
                action_type="MATERIAL_PURCHASE",
                decision=RuleDecision.ALLOW,
                reason_code="DEMO_MATERIAL_WITHIN_LIMIT",
                rule_version=DEMO_RULE_VERSION,
                allowed_requester_types=frozenset({RequestedByType.HUMAN}),
                amount_field="amountMinor",
                currency_field="currency",
                threshold_minor=DEMO_MATERIAL_APPROVAL_THRESHOLD_MINOR,
                threshold_currency="VND",
                threshold_reason_code="DEMO_MATERIAL_COST_APPROVAL_REQUIRED",
            ),
            RuleDefinition(
                action_type="PROHIBITED_ACTION",
                decision=RuleDecision.DENY,
                reason_code="DEMO_PROHIBITED_ACTION",
                rule_version=DEMO_RULE_VERSION,
            ),
        ],
        default_rule_version=DEMO_RULE_VERSION,
    )
