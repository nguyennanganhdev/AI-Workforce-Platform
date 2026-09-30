"""
Session Resumption Module for Agent-Vinhomes (DEV-4).
Provides state restoration and workflow stage recovery.
"""

from dataclasses import dataclass
from enum import Enum
from typing import Optional, Dict, Any
import logging

from .checkpoint import CheckpointManager, SessionState, StageStatus

logger = logging.getLogger(__name__)


class ResumeStatus(str, Enum):
    SUCCESS = "success"
    NO_CHECKPOINT = "no_checkpoint"
    INVALID_STAGE = "invalid_stage"
    RESUME_FAILED = "resume_failed"


@dataclass
class ResumeResult:
    """Outcome of attempting to resume a session."""
    status: ResumeStatus
    session_state: Optional[SessionState] = None
    recommended_next_stage: Optional[StageStatus] = None
    message: str = ""


class SessionResumer:
    """
    Handles session restoration and determines appropriate recovery path
    for interrupting/resuming ticket execution mid-flow.
    """

    def __init__(self, checkpoint_manager: CheckpointManager):
        self.checkpoint_manager = checkpoint_manager

    def determine_next_stage(self, state: SessionState) -> StageStatus:
        """
        Determines the next execution stage based on current session stage status.
        """
        status_transitions = {
            StageStatus.INTAKE: StageStatus.RECEPTION_HANDOFF,
            StageStatus.RECEPTION_HANDOFF: StageStatus.DISPATCH,
            StageStatus.DISPATCH: StageStatus.ROOM_MEETING,
            StageStatus.ROOM_MEETING: StageStatus.WAITING_APPROVAL,
            StageStatus.WAITING_APPROVAL: StageStatus.EXECUTING_ACTION,
            StageStatus.EXECUTING_ACTION: StageStatus.COMPLETED,
            StageStatus.COMPLETED: StageStatus.COMPLETED,
            StageStatus.FAILED: StageStatus.DISPATCH,  # Re-evaluate dispatch on failure
        }
        return status_transitions.get(state.stage_status, state.stage_status)

    async def resume_session(
        self,
        identifier: str,
        expected_stage: Optional[StageStatus] = None
    ) -> ResumeResult:
        """
        Attempts to load a saved checkpoint and validate session resumption.

        Args:
            identifier: ticket_id or room_id
            expected_stage: optional stage expectation for validation

        Returns:
            ResumeResult with loaded state and recommendation
        """
        state = await self.checkpoint_manager.load_checkpoint(identifier)
        if not state:
            logger.warning(f"No checkpoint found for identifier: {identifier}")
            return ResumeResult(
                status=ResumeStatus.NO_CHECKPOINT,
                message=f"No checkpoint found for identifier '{identifier}'"
            )

        if expected_stage and state.stage_status != expected_stage:
            logger.info(
                f"Checkpoint stage mismatch for {identifier}: "
                f"expected {expected_stage.value}, found {state.stage_status.value}"
            )

        next_stage = self.determine_next_stage(state)
        
        logger.info(
            f"Successfully resumed session for ticket={state.ticket_id}, "
            f"current_stage={state.stage_status.value}, next_stage={next_stage.value}"
        )

        return ResumeResult(
            status=ResumeStatus.SUCCESS,
            session_state=state,
            recommended_next_stage=next_stage,
            message=f"Session resumed at stage {state.stage_status.value}"
        )
