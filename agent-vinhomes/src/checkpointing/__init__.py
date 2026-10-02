"""
Checkpointing and Recovery Module for Agent-Vinhomes (DEV-4).
Provides session checkpointing, state resumption, retry idempotency, and failure recovery.
"""

from .checkpoint import (
    SessionState,
    StageStatus,
    CheckpointManager,
    StorageBackend,
    InMemoryStorage,
    RedisStorageAdapter,
)
from .resume import SessionResumer, ResumeResult, ResumeStatus
from .retry import RetryPolicy, IdempotencyHandler, DuplicateActionError, execute_with_retry
from .recovery import (
    FailureSeverity,
    FailureRecord,
    RecoveryAction,
    FailureRecoveryManager,
)

__all__ = [
    "SessionState",
    "StageStatus",
    "CheckpointManager",
    "StorageBackend",
    "InMemoryStorage",
    "RedisStorageAdapter",
    "SessionResumer",
    "ResumeResult",
    "ResumeStatus",
    "RetryPolicy",
    "IdempotencyHandler",
    "DuplicateActionError",
    "execute_with_retry",
    "FailureSeverity",
    "FailureRecord",
    "RecoveryAction",
    "FailureRecoveryManager",
]
