"""Speaker-turn policy engine.

Determines who speaks next in a workflow session and the overall
orchestration parameters (max turns, tool call limits, strategy).

The turn policy respects:
  - platform_session_control.max_turns / max_tool_calls (collaboration.ts)
  - platform_session_control.purpose (TRIAGE | PLAN | FOLLOW_UP | QC | REPLAN)
  - platform_session_participant.role (COORDINATOR | SPECIALIST | REVIEWER)
  - One active coordinator per session (DB unique index enforced)

DEV-1 decides WHO speaks and WHEN.
DEV-2 executes the turn via AgentScope.
"""

from __future__ import annotations

import logging

from dispatcher.contracts import (
    Complexity,
    MessageKind,
    NextSpeakerDecision,
    SelectedAgent,
    SessionPurpose,
    TicketClassification,
    TurnPolicy,
    TurnResult,
    TurnStrategy,
)

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Policy defaults by complexity
# ---------------------------------------------------------------------------

_TURN_LIMITS: dict[Complexity, int] = {
    "SIMPLE": 6,
    "MODERATE": 12,
    "COMPLEX": 20,
}

_TOOL_CALL_LIMITS: dict[Complexity, int] = {
    "SIMPLE": 10,
    "MODERATE": 25,
    "COMPLEX": 50,
}

_CONSECUTIVE_LIMITS: dict[Complexity, int] = {
    "SIMPLE": 1,
    "MODERATE": 2,
    "COMPLEX": 3,
}

_TIMEOUT_SECONDS: dict[Complexity, float] = {
    "SIMPLE": 30.0,
    "MODERATE": 60.0,
    "COMPLEX": 120.0,
}


# ---------------------------------------------------------------------------
# Strategy selection
# ---------------------------------------------------------------------------

def _choose_strategy(
    classification: TicketClassification,
    agents: list[SelectedAgent],
) -> TurnStrategy:
    """Pick a turn strategy based on complexity and roster.

    - COORDINATOR_LED: a coordinator delegates to specialists in sequence.
      Used when there IS a coordinator and multiple participants.
    - ROUND_ROBIN: each participant takes turns.
      Used for simple tickets or when no coordinator is present.
    - ON_DEMAND: coordinator calls specialists as needed.
      Used for complex tickets requiring dynamic planning.
    """
    has_coordinator = any(a["role"] == "COORDINATOR" for a in agents)

    if classification["complexity"] == "COMPLEX" and has_coordinator:
        return "ON_DEMAND"
    if has_coordinator and len(agents) > 1:
        return "COORDINATOR_LED"
    return "ROUND_ROBIN"


def _choose_purpose(classification: TicketClassification) -> SessionPurpose:
    """Map classification to session purpose.

    The initial session purpose is always TRIAGE or PLAN.
    FOLLOW_UP / QC / REPLAN are for subsequent sessions.
    """
    if classification["complexity"] == "SIMPLE":
        return "PLAN"  # Simple tickets skip triage, go straight to plan
    return "TRIAGE"


# ---------------------------------------------------------------------------
# Turn policy engine
# ---------------------------------------------------------------------------

class TurnPolicyEngine:
    """Builds the initial turn policy and provides turn-by-turn decisions.

    The engine is stateful per session: it tracks turn count and
    determines the next speaker based on the strategy.
    """

    def build_initial_policy(
        self,
        classification: TicketClassification,
        agents: list[SelectedAgent],
    ) -> TurnPolicy:
        """Build the initial TurnPolicy for the DispatcherDecision.

        This determines the overall session parameters. DEV-2 uses this
        to configure platform_session_control.
        """
        complexity = classification["complexity"]
        strategy = _choose_strategy(classification, agents)
        purpose = _choose_purpose(classification)

        # Build speaker order based on strategy
        speaker_order = self._build_speaker_order(agents, strategy)

        # Resident @agent requests: allow only for non-critical tickets
        allow_resident = classification["severity"] not in ("HIGH", "CRITICAL")

        return TurnPolicy(
            purpose=purpose,
            max_turns=_TURN_LIMITS.get(complexity, 12),
            max_consecutive_turns=_CONSECUTIVE_LIMITS.get(complexity, 2),
            timeout_seconds=_TIMEOUT_SECONDS.get(complexity, 60.0),
            max_tool_calls=_TOOL_CALL_LIMITS.get(complexity, 25),
            speaker_order=speaker_order,
            strategy=strategy,
            allow_resident_agent_request=allow_resident,
        )

    def next_speaker(
        self,
        policy: TurnPolicy,
        agents: list[SelectedAgent],
        turn_results: list[TurnResult],
    ) -> NextSpeakerDecision | None:
        """Determine the next speaker based on strategy and turn history.

        Returns None when the session should end (max turns reached or
        all work completed).

        This is called by DEV-2 on each turn to get the next speaker
        decision from DEV-1.
        """
        current_turn = len(turn_results)
        max_turns = policy["max_turns"]

        if current_turn >= max_turns:
            logger.info("Max turns %d reached", max_turns)
            return None

        # Check total tool calls
        total_tools = sum(t["total_tool_calls"] for t in turn_results) if turn_results else 0
        if total_tools >= policy["max_tool_calls"]:
            logger.info("Max tool calls %d reached", policy["max_tool_calls"])
            return None

        strategy = policy["strategy"]
        remaining = max_turns - current_turn

        if strategy == "ROUND_ROBIN":
            return self._round_robin_next(policy, agents, turn_results, remaining)
        if strategy == "COORDINATOR_LED":
            return self._coordinator_led_next(policy, agents, turn_results, remaining)
        # ON_DEMAND
        return self._on_demand_next(policy, agents, turn_results, remaining)

    # -----------------------------------------------------------------------
    # Strategy implementations
    # -----------------------------------------------------------------------

    def _round_robin_next(
        self,
        policy: TurnPolicy,
        agents: list[SelectedAgent],
        turn_results: list[TurnResult],
        remaining: int,
    ) -> NextSpeakerDecision:
        """Each agent speaks in order, cycling through the roster."""
        order = policy["speaker_order"]
        idx = len(turn_results) % len(order)
        agent_id = order[idx]
        agent = _find_agent(agents, agent_id)

        return NextSpeakerDecision(
            participant_id=agent_id,
            agent_version_id=agent_id,
            task_input={"turn_number": len(turn_results) + 1},
            reason=f"Round-robin turn {len(turn_results) + 1}: {agent['role']}",
            remaining_turns=remaining,
            should_checkpoint=self._should_checkpoint(turn_results),
        )

    def _coordinator_led_next(
        self,
        policy: TurnPolicy,
        agents: list[SelectedAgent],
        turn_results: list[TurnResult],
        remaining: int,
    ) -> NextSpeakerDecision:
        """Coordinator goes first, then alternates with specialists.

        Pattern: COORDINATOR → SPECIALIST_1 → COORDINATOR → SPECIALIST_2 → ...
        The coordinator reviews each specialist's output.
        """
        order = policy["speaker_order"]
        turn_num = len(turn_results)

        if turn_num == 0:
            # Coordinator starts
            agent_id = order[0]
        elif turn_num % 2 == 1:
            # Odd turns: specialists
            specialist_idx = (turn_num // 2) % max(1, len(order) - 1)
            agent_id = order[1 + specialist_idx] if len(order) > 1 else order[0]
        else:
            # Even turns: coordinator reviews
            agent_id = order[0]

        agent = _find_agent(agents, agent_id)
        return NextSpeakerDecision(
            participant_id=agent_id,
            agent_version_id=agent_id,
            task_input={
                "turn_number": turn_num + 1,
                "last_result": _summarize_last_turn(turn_results),
            },
            reason=f"Coordinator-led turn {turn_num + 1}: {agent['role']}",
            remaining_turns=remaining,
            should_checkpoint=self._should_checkpoint(turn_results),
        )

    def _on_demand_next(
        self,
        policy: TurnPolicy,
        agents: list[SelectedAgent],
        turn_results: list[TurnResult],
        remaining: int,
    ) -> NextSpeakerDecision:
        """Coordinator decides who to call next based on the last message.

        For complex tickets: coordinator always gets the turn to decide
        what to do next, unless the last turn already was the coordinator.
        """
        order = policy["speaker_order"]
        turn_num = len(turn_results)

        # If last turn was a specialist, give coordinator control
        # If last turn was coordinator, pick next specialist
        if turn_results:
            last = turn_results[-1]
            last_agent = _find_agent(agents, last["participant_id"])
            if last_agent["role"] != "COORDINATOR":
                # Coordinator reviews
                agent_id = order[0]
            else:
                # Pick a specialist that hasn't gone recently
                recent_ids = {t["participant_id"] for t in turn_results[-3:]}
                for aid in order[1:]:
                    if aid not in recent_ids:
                        agent_id = aid
                        break
                else:
                    agent_id = order[1] if len(order) > 1 else order[0]
        else:
            agent_id = order[0]  # Coordinator starts

        agent = _find_agent(agents, agent_id)
        return NextSpeakerDecision(
            participant_id=agent_id,
            agent_version_id=agent_id,
            task_input={
                "turn_number": turn_num + 1,
                "last_result": _summarize_last_turn(turn_results),
            },
            reason=f"On-demand turn {turn_num + 1}: {agent['role']}",
            remaining_turns=remaining,
            should_checkpoint=self._should_checkpoint(turn_results),
        )

    # -----------------------------------------------------------------------
    # Helpers
    # -----------------------------------------------------------------------

    def _build_speaker_order(
        self,
        agents: list[SelectedAgent],
        strategy: TurnStrategy,
    ) -> list[str]:
        """Build the speaker order list.

        Coordinator always first, then specialists, then reviewers.
        """
        coordinators = [a["agent_version_id"] for a in agents if a["role"] == "COORDINATOR"]
        specialists = [a["agent_version_id"] for a in agents if a["role"] == "SPECIALIST"]
        reviewers = [a["agent_version_id"] for a in agents if a["role"] == "REVIEWER"]

        return coordinators + specialists + reviewers

    def _should_checkpoint(self, turn_results: list[TurnResult]) -> bool:
        """Decide whether to checkpoint before the next turn.

        Checkpoint when:
          - An action proposal was made in the last turn (high-risk).
          - Every 5th turn (periodic safety).
        """
        if not turn_results:
            return False

        last = turn_results[-1]
        if last["has_action_proposal"]:
            return True

        return last["turn_number"] % 5 == 0


def _find_agent(agents: list[SelectedAgent], agent_id: str) -> SelectedAgent:
    """Find an agent by version ID, falling back to the first agent."""
    for a in agents:
        if a["agent_version_id"] == agent_id:
            return a
    return agents[0]


def _summarize_last_turn(turn_results: list[TurnResult]) -> dict | None:
    """Extract summary info from the last turn for the next speaker's input."""
    if not turn_results:
        return None
    last = turn_results[-1]
    return {
        "participant_id": last["participant_id"],
        "message_kind": last["message_kind"],
        "had_proposal": last["has_action_proposal"],
    }
