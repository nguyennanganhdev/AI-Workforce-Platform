"""
Unit tests for Session Resumption (resume.py).
"""

import sys
from pathlib import Path

# Add agent-vinhomes directory to sys.path
sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

import pytest
from src.checkpointing.checkpoint import (
    SessionState,
    StageStatus,
    CheckpointManager,
    InMemoryStorage,
)
from src.checkpointing.resume import (
    SessionResumer,
    ResumeStatus,
)


@pytest.mark.asyncio
async def test_resume_non_existent_session():
    manager = CheckpointManager(InMemoryStorage())
    resumer = SessionResumer(manager)

    result = await resumer.resume_session("NON_EXISTENT_TICKET")
    assert result.status == ResumeStatus.NO_CHECKPOINT
    assert result.session_state is None


@pytest.mark.asyncio
async def test_resume_existing_session_stage_transition():
    manager = CheckpointManager(InMemoryStorage())
    resumer = SessionResumer(manager)

    state = SessionState(
        ticket_id="TK-2001",
        room_id="ROOM-200",
        stage_status=StageStatus.ROOM_MEETING
    )
    await manager.save_checkpoint(state)

    result = await resumer.resume_session("TK-2001")
    assert result.status == ResumeStatus.SUCCESS
    assert result.session_state is not None
    assert result.session_state.ticket_id == "TK-2001"
    assert result.recommended_next_stage == StageStatus.WAITING_APPROVAL


@pytest.mark.asyncio
async def test_stage_transitions_mapping():
    manager = CheckpointManager(InMemoryStorage())
    resumer = SessionResumer(manager)

    state_intake = SessionState(ticket_id="T1", room_id="R1", stage_status=StageStatus.INTAKE)
    assert resumer.determine_next_stage(state_intake) == StageStatus.RECEPTION_HANDOFF

    state_approval = SessionState(ticket_id="T2", room_id="R2", stage_status=StageStatus.WAITING_APPROVAL)
    assert resumer.determine_next_stage(state_approval) == StageStatus.EXECUTING_ACTION

    state_failed = SessionState(ticket_id="T3", room_id="R3", stage_status=StageStatus.FAILED)
    assert resumer.determine_next_stage(state_failed) == StageStatus.DISPATCH
