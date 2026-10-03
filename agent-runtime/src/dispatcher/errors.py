"""Error definitions for the dispatcher.

Error codes follow the pattern established by the OpenBot routing layer
in server/src/routing/classify.ts (RoutingUndecided), adapted for the
runtime dispatcher context.
"""

from __future__ import annotations

from dispatcher.contracts import DispatcherError


# ---------------------------------------------------------------------------
# Named error codes — countable in audit / observability, not free text.
# ---------------------------------------------------------------------------

INVALID_TICKET = "INVALID_TICKET"
NO_ELIGIBLE_AGENTS = "NO_ELIGIBLE_AGENTS"
SLA_POLICY_NOT_FOUND = "SLA_POLICY_NOT_FOUND"
AGENT_UNAVAILABLE = "AGENT_UNAVAILABLE"
INVALID_AGENT_REQUEST = "INVALID_AGENT_REQUEST"
MODEL_FAILURE = "MODEL_FAILURE"
CLASSIFICATION_TIMEOUT = "CLASSIFICATION_TIMEOUT"
SLA_CONFLICT = "SLA_CONFLICT"
CHECKPOINT_REQUIRED = "CHECKPOINT_REQUIRED"
INTERNAL_ERROR = "INTERNAL_ERROR"


def make_error(
    *,
    code: str,
    message: str,
    ticket_id: str,
    correlation_id: str,
    recoverable: bool = False,
    fallback_action: str | None = None,
) -> DispatcherError:
    """Build a DispatcherError dict with the standard shape."""
    return DispatcherError(
        error_code=code,
        message=message,
        ticket_id=ticket_id,
        correlation_id=correlation_id,
        recoverable=recoverable,
        fallback_action=fallback_action,
    )


class DispatcherException(Exception):
    """Raised when the dispatcher encounters a non-recoverable condition.

    Carries the structured DispatcherError so callers can inspect the code
    without parsing a message string.
    """

    def __init__(self, error: DispatcherError) -> None:
        self.error = error
        super().__init__(error["message"])
