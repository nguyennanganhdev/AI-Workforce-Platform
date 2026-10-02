"""
Failure Recovery & Propagation Module for Agent-Vinhomes (DEV-4).
Manages error classification, escalation, and session recovery actions.
"""

from dataclasses import dataclass, field
from enum import Enum
from typing import Dict, Any, Optional
import time
import logging

from .checkpoint import SessionState, StageStatus, CheckpointManager

logger = logging.getLogger(__name__)


class FailureSeverity(str, Enum):
    TRANSIENT = "transient"          # Network glitch or timeout -> Retryable
    NON_RETRYABLE = "non_retryable"  # Schema/validation error -> Replan / Dispatch fallback
    CRITICAL_ESCALATE = "critical_escalate" # Security violation or unhandled -> Human escalation


class RecoveryAction(str, Enum):
    RETRY_STEP = "retry_step"
    REPLAN_DISPATCH = "replan_dispatch"
    ESCALATE_HUMAN = "escalate_human"
    MARK_FAILED = "mark_failed"


@dataclass
class FailureRecord:
    """Detailed log of a failure event during session execution."""
    ticket_id: str
    step_name: str
    error_message: str
    error_type: str
    severity: FailureSeverity
    attempt_count: int = 1
    timestamp: float = field(default_factory=time.time)
    metadata: Dict[str, Any] = field(default_factory=dict)


class FailureRecoveryManager:
    """
    Evaluates failure severity and determines appropriate recovery actions.
    Updates session state checkpoint accordingly.
    """

    def __init__(self, checkpoint_manager: CheckpointManager):
        self.checkpoint_manager = checkpoint_manager

    def classify_failure(self, error: Exception) -> FailureSeverity:
        """Classifies exception into FailureSeverity based on error characteristics."""
        err_str = str(error).lower()
        err_type = type(error).__name__.lower()

        # 1. Security / Auth errors take highest priority (CRITICAL_ESCALATE)
        if isinstance(error, PermissionError) or "permission" in err_str or "unauthorized" in err_str or "forbidden" in err_str:
            return FailureSeverity.CRITICAL_ESCALATE

        # 2. Transient network / connection errors (TRANSIENT)
        if isinstance(error, (TimeoutError, ConnectionError)) or "timeout" in err_str or "connection" in err_str or "network" in err_str or "timeout" in err_type or "connection" in err_type:
            return FailureSeverity.TRANSIENT

        # 3. Validation / Schema errors (NON_RETRYABLE)
        if isinstance(error, (ValueError, TypeError)) or "valueerror" in err_type or "schema" in err_str or "validation" in err_str:
            return FailureSeverity.NON_RETRYABLE

        return FailureSeverity.NON_RETRYABLE

    def determine_recovery_action(
        self,
        severity: FailureSeverity,
        attempt_count: int,
        max_transient_attempts: int = 3
    ) -> RecoveryAction:
        """Determines recovery action based on severity and attempt count."""
        if severity == FailureSeverity.TRANSIENT:
            if attempt_count < max_transient_attempts:
                return RecoveryAction.RETRY_STEP
            return RecoveryAction.REPLAN_DISPATCH
        elif severity == FailureSeverity.NON_RETRYABLE:
            return RecoveryAction.REPLAN_DISPATCH
        elif severity == FailureSeverity.CRITICAL_ESCALATE:
            return RecoveryAction.ESCALATE_HUMAN

        return RecoveryAction.MARK_FAILED

    async def handle_failure(
        self,
        session_state: SessionState,
        step_name: str,
        error: Exception,
        attempt_count: int = 1
    ) -> Dict[str, Any]:
        """
        Handles failure event: records error details, updates session state,
        persists checkpoint, and returns recommended recovery action.
        """
        severity = self.classify_failure(error)
        action = self.determine_recovery_action(severity, attempt_count)

        record = FailureRecord(
            ticket_id=session_state.ticket_id,
            step_name=step_name,
            error_message=str(error),
            error_type=type(error).__name__,
            severity=severity,
            attempt_count=attempt_count,
        )

        session_state.history.append({
            "type": "failure_event",
            "record": {
                "step": record.step_name,
                "error": record.error_message,
                "severity": record.severity.value,
                "action": action.value,
                "timestamp": record.timestamp,
            }
        })

        if action == RecoveryAction.MARK_FAILED:
            session_state.stage_status = StageStatus.FAILED
        elif action == RecoveryAction.REPLAN_DISPATCH:
            session_state.stage_status = StageStatus.DISPATCH

        await self.checkpoint_manager.save_checkpoint(session_state)

        logger.error(
            f"Failure handled for ticket={session_state.ticket_id} at step '{step_name}': "
            f"severity={severity.value}, action={action.value}"
        )

        return {
            "ticket_id": session_state.ticket_id,
            "severity": severity.value,
            "action": action.value,
            "updated_stage": session_state.stage_status.value,
            "failure_record": record,
        }
