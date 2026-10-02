"""
Session Checkpointing Module for Agent-Vinhomes (DEV-4).
Defines session state dataclasses and storage backend adapters (Redis / InMemory).
"""

from dataclasses import dataclass, field, asdict
from enum import Enum
from typing import Dict, Any, List, Optional, Protocol, Union
import json
import time
import asyncio
import logging

logger = logging.getLogger(__name__)


class StageStatus(str, Enum):
    """Execution stage status in the 5-step workflow."""
    INTAKE = "intake"                     # Lễ tân intake ticket
    RECEPTION_HANDOFF = "reception_handoff" # DEV-3 gateway transfer
    DISPATCH = "dispatch"                 # DEV-1 ticket classification / SLA
    ROOM_MEETING = "room_meeting"         # DEV-2 Agent Team Service room session
    WAITING_APPROVAL = "waiting_approval" # Pending human/supervisor approval
    EXECUTING_ACTION = "executing_action"# ActionExecutor executing WRITE operation
    COMPLETED = "completed"               # Ticket resolution sent back to reception
    FAILED = "failed"                     # Unrecoverable error state


@dataclass
class SessionState:
    """Complete snapshot of a ticket session across runtime stages."""
    ticket_id: str
    room_id: str
    participants: List[str] = field(default_factory=list)
    current_turn: int = 0
    active_agent: Optional[str] = None
    approved_decisions: List[Dict[str, Any]] = field(default_factory=list)
    stage_status: StageStatus = StageStatus.INTAKE
    metadata: Dict[str, Any] = field(default_factory=dict)
    history: List[Dict[str, Any]] = field(default_factory=list)
    created_at: float = field(default_factory=time.time)
    updated_at: float = field(default_factory=time.time)

    def to_dict(self) -> Dict[str, Any]:
        """Convert session state to dictionary."""
        data = asdict(self)
        if isinstance(self.stage_status, StageStatus):
            data["stage_status"] = self.stage_status.value
        return data

    def to_json(self) -> str:
        """Serialize session state to JSON string."""
        return json.dumps(self.to_dict(), ensure_ascii=False)

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "SessionState":
        """Reconstruct SessionState from dictionary."""
        data_copy = dict(data)
        if "stage_status" in data_copy and isinstance(data_copy["stage_status"], str):
            data_copy["stage_status"] = StageStatus(data_copy["stage_status"])
        return cls(**data_copy)

    @classmethod
    def from_json(cls, json_str: str) -> "SessionState":
        """Deserialize SessionState from JSON string."""
        return cls.from_dict(json.loads(json_str))


class StorageBackend(Protocol):
    """Abstract protocol for checkpoint persistence backend."""

    async def save(self, key: str, value: str, ttl: Optional[int] = None) -> bool:
        ...

    async def load(self, key: str) -> Optional[str]:
        ...

    async def delete(self, key: str) -> bool:
        ...

    async def exists(self, key: str) -> bool:
        ...


class InMemoryStorage:
    """In-memory fallback storage for development and unit testing."""

    def __init__(self):
        self._store: Dict[str, str] = {}

    async def save(self, key: str, value: str, ttl: Optional[int] = None) -> bool:
        self._store[key] = value
        return True

    async def load(self, key: str) -> Optional[str]:
        return self._store.get(key)

    async def delete(self, key: str) -> bool:
        if key in self._store:
            del self._store[key]
            return True
        return False

    async def exists(self, key: str) -> bool:
        return key in self._store


class RedisStorageAdapter:
    """
    Adapter wrapping Redis / AgentScope Storage.
    Falls back gracefully to InMemoryStorage if redis client is unavailable.
    """

    def __init__(self, redis_client: Any = None, key_prefix: str = "vinhomes:session:"):
        self.redis_client = redis_client
        self.key_prefix = key_prefix
        self._fallback = InMemoryStorage()

    def _make_key(self, key: str) -> str:
        if key.startswith(self.key_prefix):
            return key
        return f"{self.key_prefix}{key}"

    async def save(self, key: str, value: str, ttl: Optional[int] = None) -> bool:
        full_key = self._make_key(key)
        if self.redis_client is not None:
            try:
                if asyncio.iscoroutinefunction(getattr(self.redis_client, "set", None)):
                    if ttl:
                        await self.redis_client.set(full_key, value, ex=ttl)
                    else:
                        await self.redis_client.set(full_key, value)
                else:
                    if ttl:
                        self.redis_client.set(full_key, value, ex=ttl)
                    else:
                        self.redis_client.set(full_key, value)
                return True
            except Exception as e:
                logger.warning(f"Redis save failed for {full_key}, using fallback: {e}")

        return await self._fallback.save(full_key, value, ttl)

    async def load(self, key: str) -> Optional[str]:
        full_key = self._make_key(key)
        if self.redis_client is not None:
            try:
                if asyncio.iscoroutinefunction(getattr(self.redis_client, "get", None)):
                    val = await self.redis_client.get(full_key)
                else:
                    val = self.redis_client.get(full_key)

                if val is not None:
                    if isinstance(val, bytes):
                        return val.decode("utf-8")
                    return str(val)
            except Exception as e:
                logger.warning(f"Redis load failed for {full_key}, using fallback: {e}")

        return await self._fallback.load(full_key)

    async def delete(self, key: str) -> bool:
        full_key = self._make_key(key)
        if self.redis_client is not None:
            try:
                if asyncio.iscoroutinefunction(getattr(self.redis_client, "delete", None)):
                    await self.redis_client.delete(full_key)
                else:
                    self.redis_client.delete(full_key)
                return True
            except Exception as e:
                logger.warning(f"Redis delete failed for {full_key}, using fallback: {e}")

        return await self._fallback.delete(full_key)

    async def exists(self, key: str) -> bool:
        full_key = self._make_key(key)
        if self.redis_client is not None:
            try:
                if asyncio.iscoroutinefunction(getattr(self.redis_client, "exists", None)):
                    res = await self.redis_client.exists(full_key)
                else:
                    res = self.redis_client.exists(full_key)
                return bool(res)
            except Exception as e:
                logger.warning(f"Redis exists failed for {full_key}, using fallback: {e}")

        return await self._fallback.exists(full_key)


class CheckpointManager:
    """High-level manager for creating, updating, loading, and deleting session checkpoints."""

    def __init__(self, storage: Optional[Union[StorageBackend, RedisStorageAdapter]] = None):
        self.storage = storage or InMemoryStorage()

    def _get_checkpoint_key(self, identifier: str) -> str:
        return f"checkpoint:{identifier}"

    async def save_checkpoint(self, state: SessionState, ttl: Optional[int] = None) -> bool:
        """Save session state checkpoint indexed by ticket_id and room_id."""
        state.updated_at = time.time()
        serialized = state.to_json()
        
        # Save under ticket_id
        ticket_key = self._get_checkpoint_key(state.ticket_id)
        saved_ticket = await self.storage.save(ticket_key, serialized, ttl=ttl)

        # Save under room_id if room_id is specified
        if state.room_id:
            room_key = self._get_checkpoint_key(state.room_id)
            await self.storage.save(room_key, serialized, ttl=ttl)

        return saved_ticket

    async def load_checkpoint(self, identifier: str) -> Optional[SessionState]:
        """Load session state by ticket_id or room_id."""
        key = self._get_checkpoint_key(identifier)
        json_str = await self.storage.load(key)
        if not json_str:
            return None
        try:
            return SessionState.from_json(json_str)
        except Exception as e:
            logger.error(f"Failed to deserialize checkpoint for {identifier}: {e}")
            return None

    async def delete_checkpoint(self, identifier: str) -> bool:
        """Delete checkpoint for identifier."""
        key = self._get_checkpoint_key(identifier)
        return await self.storage.delete(key)
