"""Deterministic policy lookup for A5 action proposals; no model inference."""

from datetime import datetime, timezone
from enum import StrEnum

from pydantic import BaseModel, ConfigDict, Field, model_validator

from ..db.action_request import RequestedByType


class RuleDecision(StrEnum):
    ALLOW = "ALLOW"
    REQUIRE_APPROVAL = "REQUIRE_APPROVAL"
    DENY = "DENY"


class RuleDefinition(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    action_type: str = Field(min_length=1)
    decision: RuleDecision
    reason_code: str = Field(min_length=1)
    rule_version: str = Field(min_length=1)
    allowed_requester_types: frozenset[RequestedByType] | None = None
    amount_field: str | None = None
    currency_field: str | None = None
    threshold_minor: int | None = Field(default=None, gt=0, strict=True)
    threshold_currency: str = "VND"
    threshold_reason_code: str = "APPROVAL_THRESHOLD_EXCEEDED"

    @model_validator(mode="after")
    def validate_threshold_configuration(self) -> "RuleDefinition":
        if self.threshold_minor is not None and (not self.amount_field or not self.currency_field):
            raise ValueError("amount_field and currency_field are required when threshold_minor is set")
        if self.threshold_minor is None and (self.amount_field is not None or self.currency_field is not None):
            raise ValueError("amount_field and currency_field require threshold_minor")
        if len(self.threshold_currency) != 3 or not self.threshold_currency.isalpha():
            raise ValueError("threshold_currency must be a three-letter currency code")
        return self


class RuleEvaluation(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    decision: RuleDecision
    reason_code: str
    rule_version: str
    correlation_id: str
    evaluated_at: datetime


class A5RuleEngine:
    """Evaluate explicit versioned rules; unknown actions are denied."""

    def __init__(
        self,
        rules: list[RuleDefinition],
        *,
        default_rule_version: str = "a5-v1",
    ) -> None:
        if not default_rule_version.strip():
            raise ValueError("default_rule_version must not be empty")
        self._default_rule_version = default_rule_version
        self._rules: dict[str, RuleDefinition] = {}
        for rule in rules:
            if rule.action_type in self._rules:
                raise ValueError(f"duplicate rule for action type: {rule.action_type}")
            self._rules[rule.action_type] = rule

    def evaluate(
        self,
        *,
        action_type: str,
        requested_by_type: RequestedByType,
        correlation_id: str,
        payload: dict[str, object] | None = None,
    ) -> RuleEvaluation:
        action_code = action_type.strip()
        if not action_code:
            return self._result(
                decision=RuleDecision.DENY,
                reason_code="INVALID_ACTION_TYPE",
                rule_version=self._default_rule_version,
                correlation_id=correlation_id,
            )

        rule = self._rules.get(action_code)
        if rule is None:
            return self._result(
                decision=RuleDecision.DENY,
                reason_code="NO_MATCHING_RULE",
                rule_version=self._default_rule_version,
                correlation_id=correlation_id,
            )

        if (
            rule.allowed_requester_types is not None
            and requested_by_type not in rule.allowed_requester_types
        ):
            return self._result(
                decision=RuleDecision.DENY,
                reason_code="REQUESTER_TYPE_NOT_ALLOWED",
                rule_version=rule.rule_version,
                correlation_id=correlation_id,
            )

        if rule.threshold_minor is not None:
            assert rule.amount_field is not None and rule.currency_field is not None
            amount = (payload or {}).get(rule.amount_field)
            currency = (payload or {}).get(rule.currency_field)
            if type(amount) is not int or amount <= 0:
                return self._result(
                    decision=RuleDecision.DENY,
                    reason_code="INVALID_OR_MISSING_AMOUNT",
                    rule_version=rule.rule_version,
                    correlation_id=correlation_id,
                )
            if currency != rule.threshold_currency:
                return self._result(
                    decision=RuleDecision.DENY,
                    reason_code="UNSUPPORTED_COST_CURRENCY",
                    rule_version=rule.rule_version,
                    correlation_id=correlation_id,
                )
            if amount > rule.threshold_minor:
                return self._result(
                    decision=RuleDecision.REQUIRE_APPROVAL,
                    reason_code=rule.threshold_reason_code,
                    rule_version=rule.rule_version,
                    correlation_id=correlation_id,
                )

        return self._result(
            decision=rule.decision,
            reason_code=rule.reason_code,
            rule_version=rule.rule_version,
            correlation_id=correlation_id,
        )

    @staticmethod
    def _result(
        *,
        decision: RuleDecision,
        reason_code: str,
        rule_version: str,
        correlation_id: str,
    ) -> RuleEvaluation:
        return RuleEvaluation(
            decision=decision,
            reason_code=reason_code,
            rule_version=rule_version,
            correlation_id=correlation_id,
            evaluated_at=datetime.now(timezone.utc),
        )
