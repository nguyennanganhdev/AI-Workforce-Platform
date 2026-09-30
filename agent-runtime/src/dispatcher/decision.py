"""Assemble the final DispatcherDecision from classification, selection,
turn policy, SLA, and prediction signals.

This is the composition point that brings together all dispatcher
sub-modules.  It calls each module in the correct order and produces
the single DispatcherDecision that DEV-2 consumes.

The decision builder:
  - Does NOT call the LLM or ML models directly.
  - Does NOT access the database.
  - Receives pre-computed results and assembles them.
  - Enforces the rule: reception/model classification suggestions
    must NOT automatically become SLA decisions.
"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone

from dispatcher.agent_selector import AgentSelector
from dispatcher.contracts import (
    DecisionReasoning,
    DispatcherDecision,
    PredictionSignals,
    TicketReport,
)
from dispatcher.errors import (
    INTERNAL_ERROR,
    INVALID_TICKET,
    DispatcherException,
    make_error,
)
from dispatcher.rules import check_approval_required, resolve_sla
from dispatcher.ticket_classifier import TicketClassifier
from dispatcher.turn_policy import TurnPolicyEngine


async def build_decision(
    ticket: TicketReport,
    classifier: TicketClassifier,
    selector: AgentSelector,
    policy_engine: TurnPolicyEngine,
) -> DispatcherDecision:
    """Build a complete DispatcherDecision from a TicketReport.

    This is the main entry point that DEV-5 wires at the composition root.

    Flow:
      1. Validate input.
      2. Classify ticket (LLM + optional ML).
      3. Select agents (rules).
      4. Resolve SLA (rules).
      5. Determine turn policy.
      6. Check approval requirements.
      7. Assemble decision.

    Raises:
        DispatcherException: On unrecoverable errors with structured error codes.
    """
    ticket_id = ticket["ticket_id"]
    correlation_id = ticket["correlation_id"]

    # 1. Validate input
    _validate_ticket(ticket)

    # 2. Classify
    classification, signals, classification_evidence = await classifier.classify(
        ticket["report"],
    )

    # 3. Select agents
    selected, selection_evidence, warnings = selector.select(
        eligible_agents=ticket["eligible_agents"],
        classification=classification,
        report=ticket["report"],
        ticket_id=ticket_id,
        correlation_id=correlation_id,
    )

    # 4. Resolve SLA (rules — NEVER from LLM/ML predictions)
    started_at = datetime.now(timezone.utc).isoformat()
    sla = resolve_sla(
        classification=classification,
        sla_policies=ticket["sla_policies"],
        ticket_id=ticket_id,
        correlation_id=correlation_id,
        started_at=started_at,
    )
    sla_evidence = [
        f"SLA policy {sla['policy_id']} matched: "
        f"response={sla['response_minutes']}min, "
        f"resolution={sla['resolution_minutes']}min",
        f"Severity for SLA: {sla['severity']}",
    ]

    # 5. Turn policy
    turn_policy = policy_engine.build_initial_policy(classification, selected)

    # 6. Approval check
    requires_approval, approval_reason = check_approval_required(
        classification, ticket["incident"],
    )

    # 7. Assemble
    reasoning = DecisionReasoning(
        classification_evidence=classification_evidence,
        agent_selection_evidence=selection_evidence,
        sla_match_evidence=sla_evidence,
        warnings=warnings,
    )

    return DispatcherDecision(
        version=1,
        decision_id=str(uuid.uuid4()),
        ticket_id=ticket_id,
        correlation_id=correlation_id,
        classification=classification,
        selected_agents=selected,
        turn_policy=turn_policy,
        sla=sla,
        prediction_signals=signals,
        requires_approval=requires_approval,
        approval_reason=approval_reason,
        reasoning=reasoning,
    )


def _validate_ticket(ticket: TicketReport) -> None:
    """Validate basic structure of the incoming ticket report."""
    errors: list[str] = []

    if not ticket.get("ticket_id"):
        errors.append("ticket_id is required")
    if not ticket.get("tenant_id"):
        errors.append("tenant_id is required")
    if not ticket.get("correlation_id"):
        errors.append("correlation_id is required")
    if not ticket.get("report"):
        errors.append("report is required")
    if not ticket.get("report", {}).get("text", "").strip():
        errors.append("report.text must not be empty")
    if not ticket.get("incident"):
        errors.append("incident context is required")
    if not ticket.get("eligible_agents"):
        errors.append("eligible_agents list is required (may be empty)")

    if errors:
        raise DispatcherException(
            make_error(
                code=INVALID_TICKET,
                message=f"Invalid ticket: {'; '.join(errors)}",
                ticket_id=ticket.get("ticket_id", "unknown"),
                correlation_id=ticket.get("correlation_id", "unknown"),
                recoverable=False,
            )
        )
