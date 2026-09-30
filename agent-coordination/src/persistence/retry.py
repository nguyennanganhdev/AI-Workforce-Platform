"""
Retry Policy & Idempotency Control Module for Agent Coordination (DEV-4).
Prevents duplicate action executions and handles retry mechanics.
"""

from dataclasses import dataclass
from typing import Dict, Any, Optional, Callable, Type, Tuple
import asyncio
import time
import logging
import inspect

from .checkpoint import StorageBackend, InMemoryStorage

logger = logging.getLogger(__name__)


class DuplicateActionError(Exception):
    """Raised when an action with an already processed idempotency key is executed again."""
    def __init__(self, idempotency_key: str, cached_result: Optional[Dict[str, Any]] = None):
        super().__init__(f"Action with idempotency_key '{idempotency_key}' has already been processed.")
        self.idempotency_key = idempotency_key
        self.cached_result = cached_result


class IdempotencyHandler:
    """
    Manages action idempotency keys to ensure side-effects (e.g., WRITE operations)
    are executed at most once.
    """

    def __init__(self, storage: Optional[StorageBackend] = None):
        self.storage = storage or InMemoryStorage()

    def _make_key(self, idempotency_key: str) -> str:
        return f"idempotency:{idempotency_key}"

    async def is_processed(self, idempotency_key: str) -> bool:
        """Check if an idempotency key has already been processed."""
        key = self._make_key(idempotency_key)
        return await self.storage.exists(key)

    async def get_cached_result(self, idempotency_key: str) -> Optional[Dict[str, Any]]:
        """Retrieve cached result of an idempotent action if available."""
        key = self._make_key(idempotency_key)
        json_str = await self.storage.load(key)
        if json_str:
            import json
            try:
                return json.loads(json_str)
            except Exception as e:
                logger.error(f"Failed to parse cached idempotency result for {idempotency_key}: {e}")
        return None

    async def record_action(
        self,
        idempotency_key: str,
        result: Dict[str, Any],
        ttl: Optional[int] = 86400  # Default 24 hours TTL
    ) -> bool:
        """Record completed action and its result under the idempotency key."""
        import json
        key = self._make_key(idempotency_key)
        serialized = json.dumps(result, ensure_ascii=False)
        return await self.storage.save(key, serialized, ttl=ttl)


@dataclass
class RetryPolicy:
    """Configuration for action execution retries."""
    max_retries: int = 3
    initial_delay: float = 0.1
    backoff_factor: float = 2.0
    retryable_exceptions: Tuple[Type[Exception], ...] = (Exception,)


async def execute_with_retry(
    func: Callable[..., Any],
    idempotency_key: Optional[str] = None,
    retry_policy: Optional[RetryPolicy] = None,
    idempotency_handler: Optional[IdempotencyHandler] = None,
    *args: Any,
    **kwargs: Any
) -> Dict[str, Any]:
    """
    Executes an async function with idempotency check and retry policy.

    Args:
        func: Async function to execute
        idempotency_key: Optional unique key to guarantee idempotency
        retry_policy: Retry parameters (attempts, delays)
        idempotency_handler: Storage handler for idempotency keys

    Returns:
        Result dictionary of the execution
    """
    policy = retry_policy or RetryPolicy()

    # Check idempotency first if key and handler are provided
    if idempotency_key and idempotency_handler:
        if await idempotency_handler.is_processed(idempotency_key):
            cached = await idempotency_handler.get_cached_result(idempotency_key)
            logger.warning(f"Prevented duplicate execution for idempotency_key: {idempotency_key}")
            if cached is not None:
                return cached
            raise DuplicateActionError(idempotency_key, cached)

    attempt = 0
    delay = policy.initial_delay

    while True:
        try:
            attempt += 1
            if inspect.iscoroutinefunction(func):
                result = await func(*args, **kwargs)
            else:
                result = func(*args, **kwargs)

            # Ensure result is dict format
            if not isinstance(result, dict):
                result = {"result": result}

            # Record success in idempotency handler
            if idempotency_key and idempotency_handler:
                await idempotency_handler.record_action(idempotency_key, result)

            return result

        except policy.retryable_exceptions as exc:
            if attempt >= policy.max_retries:
                logger.error(
                    f"Execution failed after {attempt} attempts for idempotency_key={idempotency_key}: {exc}"
                )
                raise exc

            logger.warning(
                f"Attempt {attempt}/{policy.max_retries} failed ({exc}). Retrying in {delay}s..."
            )
            await asyncio.sleep(delay)
            delay *= policy.backoff_factor
