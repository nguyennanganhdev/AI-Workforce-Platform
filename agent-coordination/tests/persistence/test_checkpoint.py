"""
Unit tests for Session State Checkpointing (checkpoint.py).
"""

import sys
from pathlib import Path

# Add agent-coordination/src directory to sys.path
sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "src"))

import pytest
import asyncio
from persistence.checkpoint import (
    SessionState,
    StageStatus,
    CheckpointManager,
    InMemoryStorage,
    RedisStorageAdapter,
)
from groupchat.models import ScopeState, Snapshot, Context, TurnPolicy


@pytest.mark.asyncio
async def test_session_state_serialization():
    state = SessionState(
        ticket_id="TK-1001",
        room_id="ROOM-88",
        participants=["reception", "dev-1"],
        current_turn=2,
        active_agent="dev-1",
        stage_status=StageStatus.ROOM_MEETING,
        metadata={"priority": "high"}
    )

    json_str = state.to_json()
    assert "TK-1001" in json_str
    assert "ROOM-88" in json_str

    reconstructed = SessionState.from_json(json_str)
    assert reconstructed.ticket_id == state.ticket_id
    assert reconstructed.room_id == state.room_id
    assert reconstructed.participants == state.participants
    assert reconstructed.stage_status == StageStatus.ROOM_MEETING
    assert reconstructed.metadata == {"priority": "high"}


@pytest.mark.asyncio
async def test_checkpoint_manager_save_and_load():
    storage = InMemoryStorage()
    manager = CheckpointManager(storage=storage)

    state = SessionState(
        ticket_id="TK-1002",
        room_id="ROOM-99",
        participants=["dev-1", "dev-2"],
        current_turn=1,
        stage_status=StageStatus.DISPATCH
    )

    success = await manager.save_checkpoint(state)
    assert success is True

    # Load by ticket_id
    loaded_ticket = await manager.load_checkpoint("TK-1002")
    assert loaded_ticket is not None
    assert loaded_ticket.ticket_id == "TK-1002"
    assert loaded_ticket.stage_status == StageStatus.DISPATCH

    # Load by room_id
    loaded_room = await manager.load_checkpoint("ROOM-99")
    assert loaded_room is not None
    assert loaded_room.ticket_id == "TK-1002"


@pytest.mark.asyncio
async def test_checkpoint_manager_delete():
    storage = InMemoryStorage()
    manager = CheckpointManager(storage=storage)

    state = SessionState(ticket_id="TK-1003", room_id="ROOM-100")
    await manager.save_checkpoint(state)

    deleted = await manager.delete_checkpoint("TK-1003")
    assert deleted is True

    loaded = await manager.load_checkpoint("TK-1003")
    assert loaded is None


@pytest.mark.asyncio
async def test_redis_storage_fallback():
    # Test RedisStorageAdapter gracefully falls back to InMemoryStorage when no Redis client is provided
    adapter = RedisStorageAdapter(redis_client=None)

    saved = await adapter.save("test_key", "test_value")
    assert saved is True

    val = await adapter.load("test_key")
    assert val == "test_value"

    exists = await adapter.exists("test_key")
    assert exists is True

    deleted = await adapter.delete("test_key")
    assert deleted is True


@pytest.mark.asyncio
async def test_scope_state_synchronization_dev2():
    # Verify synchronization with DEV-2 (Tiến Anh) ScopeState & Snapshot models
    manager = CheckpointManager(InMemoryStorage())

    ctx = Context(
        tenant_id="tenant-1",
        principal_id="principal-1",
        domain_id="domain-1",
        workspace_id="workspace-1",
        ticket_id="TK-DEV2-001",
        ticket_generation=1,
        binding_id="binding-1",
        run_id="run-1",
    )

    snapshot = Snapshot(
        room_id="ROOM-DEV2-888",
        scope=ctx,
        groupchat_version_id="gchat-v1",
        participants=[],
        policy=TurnPolicy(),
        room_state="running",
    )

    scope_state = ScopeState(snapshot=snapshot, fence=10)

    saved = await manager.save_scope_state(scope_state, key="ROOM-DEV2-888")
    assert saved is True

    loaded = await manager.load_scope_state("ROOM-DEV2-888")
    assert loaded is not None
    assert loaded.snapshot.room_id == "ROOM-DEV2-888"
    assert loaded.snapshot.scope.ticket_id == "TK-DEV2-001"
    assert loaded.fence == 10
