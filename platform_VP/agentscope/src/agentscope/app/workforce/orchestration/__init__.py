"""PHH orchestration services; dependencies are supplied by composition root.

This package never supplies an in-memory production repository, credentials,
an LLM, or a replacement for the shared Workforce contracts.
"""

from ._conversations import ConversationService
from ._handoff import HandoffService
from ._router_agent import CapabilityRouter
from ._runs import RunService
from ._state import SharedStateService
from ._team_adapter import TeamRuntimeAdapter
from ._members import MemberService
from ._messages import MessageService
from ._evaluation import EvaluationRunner

__all__ = [
    "ConversationService", "HandoffService", "CapabilityRouter", "RunService",
    "SharedStateService", "TeamRuntimeAdapter", "MemberService", "MessageService", "EvaluationRunner",
]
