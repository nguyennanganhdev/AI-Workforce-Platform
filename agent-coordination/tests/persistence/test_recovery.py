"""
Unit tests for Failure Recovery & Propagation (recovery.py).
"""

import sys
from pathlib import Path

# Add agent-coordination/src directory to sys.path
sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "src"))

import pytest
from persistence.checkpoint import (
    SessionState,
    StageStatus,
    CheckpointManager,
    InMemoryStorage,
)
from persistence.recovery import (
    FailureRecoveryManager,
    FailureSeverity,
    RecoveryAction,
)


@pytest.mark.asyncio
async def test_failure_classification():
    manager = CheckpointManager(InMemoryStorage())
    recovery_mgr = FailureRecoveryManager(manager)

    conn_err = ConnectionError("Connection reset by peer")
    assert recovery_mgr.classify_failure(conn_err) == FailureSeverity.TRANSIENT

    val_err = ValueError("Schema validation failed for payload")
    assert recovery_mgr.classify_failure(val_err) == FailureSeverity.NON_RETRYABLE

    perm_err = PermissionError("Unauthorized access to action executor")
    assert recovery_mgr.classify_failure(perm_err) == FailureSeverity.CRITICAL_ESCALATE


@pytest.mark.asyncio
async def test_handle_failure_transient_retry():
    manager = CheckpointManager(InMemoryStorage())
    recovery_mgr = FailureRecoveryManager(manager)

    state = SessionState(ticket_id="TK-4001", room_id="R-400", stage_status=StageStatus.ROOM_MEETING)
    await manager.save_checkpoint(state)

    outcome = await recovery_mgr.handle_failure(
        session_state=state,
        step_name="agent_invite",
        error=TimeoutError("Request timed out"),
        attempt_count=1
    )

    assert outcome["severity"] == FailureSeverity.TRANSIENT.value
    assert outcome["action"] == RecoveryAction.RETRY_STEP.value

    # Check updated checkpoint in storage
    reloaded = await manager.load_checkpoint("TK-4001")
    assert reloaded is not None
    assert len(reloaded.history) == 1
    assert reloaded.history[0]["record"]["step"] == "agent_invite"


@pytest.mark.asyncio
async def test_handle_failure_escalate_human():
    manager = CheckpointManager(InMemoryStorage())
    recovery_mgr = FailureRecoveryManager(manager)

    state = SessionState(ticket_id="TK-4002", room_id="R-401", stage_status=StageStatus.EXECUTING_ACTION)
    await manager.save_checkpoint(state)

    outcome = await recovery_mgr.handle_failure(
        session_state=state,
        step_name="execute_write_mcp",
        error=PermissionError("Forbidden execution grant"),
        attempt_count=1
    )

    assert outcome["severity"] == FailureSeverity.CRITICAL_ESCALATE.value
    assert outcome["action"] == RecoveryAction.ESCALATE_HUMAN.value
