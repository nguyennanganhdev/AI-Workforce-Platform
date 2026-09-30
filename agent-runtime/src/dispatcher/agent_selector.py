"""Agent selection from the eligible pool.

The selector receives the already-filtered eligible agents (from
rules.filter_eligible_agents) and the ticket classification, then
delegates to rules.build_selected_agents for the deterministic
role-assignment logic.

This module adds the orchestration-aware wrapper: it validates
the resident's @agent requests, builds warnings, and assembles
the final list with evidence for the DecisionReasoning.

Mirrors the pattern from server/src/routing/routes.ts L143-148 for
@mention validation: an invalid agent request produces a warning,
not a hard error.
"""

from __future__ import annotations

import logging

from dispatcher.contracts import (
    EligibleAgentRef,
    ReportContext,
    SelectedAgent,
    TicketClassification,
)
from dispatcher.errors import (
    NO_ELIGIBLE_AGENTS,
    DispatcherException,
    make_error,
)
from dispatcher.rules import (
    build_selected_agents,
    filter_eligible_agents,
    validate_resident_agent_request,
)

logger = logging.getLogger(__name__)


class AgentSelector:
    """Selects agents for a workflow session based on classification and rules.

    The selector DOES NOT call the Core API — it receives the eligible
    agents list from DEV-3 via the TicketReport.  All eligibility checks
    (PUBLISHED status, ACTIVE deployment) are enforced in rules.py.
    """

    def select(
        self,
        eligible_agents: list[EligibleAgentRef],
        classification: TicketClassification,
        report: ReportContext,
        ticket_id: str,
        correlation_id: str,
    ) -> tuple[list[SelectedAgent], list[str], list[str]]:
        """Select agents and return (selected, evidence, warnings).

        Returns:
            selected: The agents to include in the workflow session.
            evidence: Reasoning strings for DecisionReasoning.agent_selection_evidence.
            warnings: Warning strings for DecisionReasoning.warnings.

        Raises:
            DispatcherException: When no eligible agents remain after filtering.
        """
        # 1. Hard eligibility filter (rules.py)
        filtered = filter_eligible_agents(
            eligible_agents, ticket_id, correlation_id,
        )

        # 2. Validate resident @agent requests (rules.py)
        mentioned = report.get("resident_mentioned_agents")
        valid_requests, mention_warnings = validate_resident_agent_request(
            mentioned, filtered,
        )

        # 3. Build the roster with role assignments (rules.py)
        selected = build_selected_agents(
            filtered, classification, valid_requests,
        )

        if not selected:
            raise DispatcherException(
                make_error(
                    code=NO_ELIGIBLE_AGENTS,
                    message=(
                        "No agents could be assigned roles for "
                        f"category={classification['category']!r}"
                    ),
                    ticket_id=ticket_id,
                    correlation_id=correlation_id,
                )
            )

        # 4. Build evidence
        evidence = [
            f"Filtered {len(filtered)} eligible agents from {len(eligible_agents)} total",
            f"Selected {len(selected)} agents for session",
        ]
        for agent in selected:
            evidence.append(
                f"  {agent['role']}: {agent['agent_version_id']} — "
                f"{agent['selection_reason']}"
            )

        if valid_requests:
            evidence.append(
                f"Resident @mentions honoured: {', '.join(valid_requests)}"
            )

        logger.info(
            "Agent selection: %d eligible → %d selected for ticket %s",
            len(filtered), len(selected), ticket_id,
        )

        return selected, evidence, mention_warnings
