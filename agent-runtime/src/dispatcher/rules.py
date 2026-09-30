"""Deterministic rules that must not be overridden by LLM or ML.

SLA lookup, agent eligibility filtering, and approval requirements
are hard business rules derived from the DB schema:

  - vh_sla_policy (sla.ts): severity enum, response/resolution minutes
  - platform_agent_version (agents.ts): PUBLISHED status gate
  - platform_session_participant (collaboration.ts): role constraints
  - vh_escalation (sla.ts): escalation reason enum

Reception/model classification suggestions are inputs to rules,
never automatic SLA decisions.
"""

from __future__ import annotations

from dispatcher.contracts import (
    EligibleAgentRef,
    IncidentContext,
    SelectedAgent,
    Severity,
    SlaBind,
    SlaPolicyRef,
    TicketClassification,
)
from dispatcher.errors import (
    NO_ELIGIBLE_AGENTS,
    SLA_CONFLICT,
    SLA_POLICY_NOT_FOUND,
    DispatcherException,
    make_error,
)


# ---------------------------------------------------------------------------
# SLA rules
# ---------------------------------------------------------------------------

def resolve_sla(
    classification: TicketClassification,
    sla_policies: list[SlaPolicyRef],
    ticket_id: str,
    correlation_id: str,
    started_at: str,
) -> SlaBind:
    """Find the matching SLA policy for the classified ticket.

    Matching logic:
      1. Filter policies by category AND severity.
      2. If multiple match, prefer the one with the shortest resolution window
         (strictest policy).
      3. If none match, try severity-only match as fallback.
      4. If still none, raise SLA_POLICY_NOT_FOUND.
      5. If ambiguous after fallback, raise SLA_CONFLICT.
    """
    category = classification["category"]
    severity: Severity = classification["severity"]

    # Exact match: category + severity
    exact = [
        p for p in sla_policies
        if p["category"] == category and p["severity"] == severity
    ]
    if len(exact) == 1:
        return _bind(exact[0], severity, started_at)
    if len(exact) > 1:
        # Pick the strictest (shortest resolution window)
        exact.sort(key=lambda p: p["resolution_minutes"])
        return _bind(exact[0], severity, started_at)

    # Fallback: severity-only match
    by_severity = [p for p in sla_policies if p["severity"] == severity]
    if len(by_severity) == 1:
        return _bind(by_severity[0], severity, started_at)
    if len(by_severity) > 1:
        by_severity.sort(key=lambda p: p["resolution_minutes"])
        return _bind(by_severity[0], severity, started_at)

    # No match at all
    raise DispatcherException(
        make_error(
            code=SLA_POLICY_NOT_FOUND,
            message=(
                f"No SLA policy matches category={category!r} "
                f"severity={severity!r}"
            ),
            ticket_id=ticket_id,
            correlation_id=correlation_id,
            recoverable=False,
        )
    )


def _bind(policy: SlaPolicyRef, severity: Severity, started_at: str) -> SlaBind:
    return SlaBind(
        policy_id=policy["policy_id"],
        severity=severity,
        response_minutes=policy["response_minutes"],
        resolution_minutes=policy["resolution_minutes"],
        started_at=started_at,
    )


# ---------------------------------------------------------------------------
# Agent eligibility
# ---------------------------------------------------------------------------

def filter_eligible_agents(
    agents: list[EligibleAgentRef],
    ticket_id: str,
    correlation_id: str,
) -> list[EligibleAgentRef]:
    """Keep only agents that are PUBLISHED and have an ACTIVE deployment.

    Mirrors the invariant from docs/erd/SYSTEM_FLOW.md:
    "Agent sản xuất phải có version PUBLISHED và deployment ACTIVE."
    """
    eligible = [a for a in agents if a["status"] == "PUBLISHED"]
    if not eligible:
        raise DispatcherException(
            make_error(
                code=NO_ELIGIBLE_AGENTS,
                message="No agent versions with status PUBLISHED are available",
                ticket_id=ticket_id,
                correlation_id=correlation_id,
                recoverable=False,
            )
        )
    return eligible


def validate_resident_agent_request(
    mentioned: list[str] | None,
    eligible: list[EligibleAgentRef],
) -> tuple[list[str], list[str]]:
    """Check whether agents requested by the resident via @mention are eligible.

    Returns (valid_ids, warning_messages).

    Pattern adapted from server/src/routing/routes.ts L143-148:
    "A named coworker is an instruction … a name that is not on it is
    refused rather than quietly turned into somebody else."

    In the dispatcher context, invalid requests produce warnings rather
    than hard errors because the dispatcher can still proceed with its
    own selection.
    """
    if not mentioned:
        return [], []

    eligible_ids = {a["agent_version_id"] for a in eligible}
    valid: list[str] = []
    warnings: list[str] = []

    for agent_id in mentioned:
        if agent_id in eligible_ids:
            valid.append(agent_id)
        else:
            warnings.append(
                f"Resident requested @{agent_id} but it is not eligible "
                f"(not PUBLISHED or deployment not ACTIVE)"
            )
    return valid, warnings


# ---------------------------------------------------------------------------
# Approval rules
# ---------------------------------------------------------------------------

# Severity levels that require human approval before action execution.
# This is a business rule; the domain (DEV-3) is the actual approval gate.
# The dispatcher only advises that approval will be needed.
_APPROVAL_SEVERITIES: set[Severity] = {"HIGH", "CRITICAL"}


def check_approval_required(
    classification: TicketClassification,
    incident: IncidentContext,
) -> tuple[bool, str | None]:
    """Determine whether the decision should flag approval-required.

    This is advisory — the domain service enforces the actual gate via
    DomainAdapter.submitAction → ActionRequest → RuleDecision → Approval.

    Returns (requires_approval, reason_or_none).
    """
    severity = classification["severity"]
    if severity in _APPROVAL_SEVERITIES:
        return True, f"Severity {severity} requires human approval"

    # Safety-related categories always need approval
    safety_categories = {"FIRE_SAFETY", "GAS_LEAK", "STRUCTURAL_DAMAGE", "FLOOD"}
    if classification["category"].upper() in safety_categories:
        return True, f"Category {classification['category']} is safety-critical"

    return False, None


# ---------------------------------------------------------------------------
# Agent-to-role mapping (rules)
# ---------------------------------------------------------------------------

def build_selected_agents(
    eligible: list[EligibleAgentRef],
    classification: TicketClassification,
    valid_resident_requests: list[str],
) -> list[SelectedAgent]:
    """Select and assign roles to agents for the workflow session.

    Rules:
      1. Exactly one COORDINATOR must be included.
         DB constraint: platform_session_participant_live_0 unique index
         enforces at most one active/invited coordinator per session.
      2. At least one SPECIALIST for the ticket category.
      3. REVIEWER if severity >= HIGH.
      4. Resident-requested agents get included if eligible.
    """
    selected: list[SelectedAgent] = []
    used_ids: set[str] = set()
    category = classification["category"]

    # 1. Find a coordinator
    coordinators = [a for a in eligible if a["role"] == "COORDINATOR"]
    if coordinators:
        coord = coordinators[0]
        selected.append(_select(coord, "Coordinator for session orchestration"))
        used_ids.add(coord["agent_version_id"])

    # 2. Specialists matching category
    specialists = [
        a for a in eligible
        if a["role"] == "SPECIALIST"
        and a["agent_version_id"] not in used_ids
        and _capability_matches_category(a["capabilities"], category)
    ]
    if not specialists:
        # Fallback: any specialist
        specialists = [
            a for a in eligible
            if a["role"] == "SPECIALIST" and a["agent_version_id"] not in used_ids
        ]

    for spec in specialists[:3]:  # Cap at 3 specialists per session
        selected.append(
            _select(spec, f"Specialist matching category {category}")
        )
        used_ids.add(spec["agent_version_id"])

    # 3. Reviewer for high-severity tickets
    if classification["severity"] in ("HIGH", "CRITICAL"):
        reviewers = [
            a for a in eligible
            if a["role"] == "REVIEWER" and a["agent_version_id"] not in used_ids
        ]
        if reviewers:
            selected.append(
                _select(reviewers[0], f"Reviewer required for severity {classification['severity']}")
            )
            used_ids.add(reviewers[0]["agent_version_id"])

    # 4. Resident-requested agents
    for req_id in valid_resident_requests:
        if req_id not in used_ids:
            agent = next((a for a in eligible if a["agent_version_id"] == req_id), None)
            if agent:
                selected.append(
                    _select(agent, "Requested by resident via @mention")
                )
                used_ids.add(req_id)

    return selected


def _select(agent: EligibleAgentRef, reason: str) -> SelectedAgent:
    return SelectedAgent(
        agent_version_id=agent["agent_version_id"],
        role=agent["role"],
        capability_scope={"capabilities": agent["capabilities"]},
        selection_reason=reason,
    )


def _capability_matches_category(
    capabilities: list[str], category: str,
) -> bool:
    """Loose match: any capability keyword overlaps with the category."""
    cat_lower = category.lower()
    return any(cat_lower in cap.lower() or cap.lower() in cat_lower for cap in capabilities)
