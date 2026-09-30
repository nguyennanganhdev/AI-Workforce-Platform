"""
Unit tests for Retry Policy & Idempotency Control (retry.py).
"""

import sys
from pathlib import Path

# Add agent-coordination/src directory to sys.path
sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "src"))

import pytest
import asyncio
from persistence.checkpoint import InMemoryStorage
from persistence.retry import (
    IdempotencyHandler,
    RetryPolicy,
    DuplicateActionError,
    execute_with_retry,
)


@pytest.mark.asyncio
async def test_idempotency_handler_record_and_check():
    handler = IdempotencyHandler(InMemoryStorage())
    key = "action_req_001"

    is_proc = await handler.is_processed(key)
    assert is_proc is False

    res = {"status": "success", "ticket_id": "TK-3001"}
    recorded = await handler.record_action(key, res)
    assert recorded is True

    is_proc_after = await handler.is_processed(key)
    assert is_proc_after is True

    cached = await handler.get_cached_result(key)
    assert cached == res


@pytest.mark.asyncio
async def test_execute_with_retry_success():
    handler = IdempotencyHandler(InMemoryStorage())
    key = "key_success_1"

    call_count = 0

    async def sample_action():
        nonlocal call_count
        call_count += 1
        return {"action": "write_db", "status": "ok"}

    res = await execute_with_retry(
        func=sample_action,
        idempotency_key=key,
        idempotency_handler=handler
    )

    assert res == {"action": "write_db", "status": "ok"}
    assert call_count == 1

    # Second call with same idempotency_key should return cached result without re-executing action
    res_cached = await execute_with_retry(
        func=sample_action,
        idempotency_key=key,
        idempotency_handler=handler
    )
    assert res_cached == {"action": "write_db", "status": "ok"}
    assert call_count == 1  # Action function was NOT called a second time


@pytest.mark.asyncio
async def test_execute_with_retry_backoff():
    policy = RetryPolicy(max_retries=3, initial_delay=0.01, backoff_factor=1.5)
    attempts = 0

    async def flaky_action():
        nonlocal attempts
        attempts += 1
        if attempts < 3:
            raise ConnectionError("Network temporary issue")
        return {"status": "recovered"}

    res = await execute_with_retry(
        func=flaky_action,
        retry_policy=policy
    )

    assert res == {"status": "recovered"}
    assert attempts == 3
