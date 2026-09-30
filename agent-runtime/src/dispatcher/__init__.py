"""Dispatcher — ticket classification, agent selection, and orchestration.

Owner: DEV-1.

Receives a TicketReport from DEV-3 (Core API / Reception gateway),
classifies the ticket, selects eligible agents, determines orchestration
policy, and returns a DispatcherDecision to DEV-2 (Agent Team Service).

ML prediction signals are advisory and never override SLA rules,
agent eligibility checks, or approval requirements.
"""

from dispatcher.contracts import (
    DispatcherDecision,
    DispatcherError,
    NextSpeakerDecision,
    TicketReport,
    TurnResult,
)
from dispatcher.decision import build_decision
from dispatcher.ticket_classifier import TicketClassifier
from dispatcher.agent_selector import AgentSelector
from dispatcher.turn_policy import TurnPolicyEngine

__all__ = [
    # Contracts
    "TicketReport",
    "DispatcherDecision",
    "DispatcherError",
    "NextSpeakerDecision",
    "TurnResult",
    # Services
    "TicketClassifier",
    "AgentSelector",
    "TurnPolicyEngine",
    "build_decision",
]
