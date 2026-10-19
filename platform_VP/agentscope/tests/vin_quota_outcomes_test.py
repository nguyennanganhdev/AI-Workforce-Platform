"""Stop/rejection/unknown outcomes with fake SDK calls and real quota SQL."""

import asyncio
from unittest.mock import AsyncMock

import httpx
import pytest
from openai import BadRequestError
from sqlalchemy import select

from vin_fixtures import authority as authority  # noqa: F401
from vin_provider_boundary_test import model_for
from agentscope.app.vin_platform import _tables as t
from agentscope.app.vin_platform._reconciliation import reconcile_pending
from agentscope.model._call_observer import observed_call


@pytest.mark.asyncio
async def test_stop_three_times_releases_slots_and_keeps_unknown_tokens(authority):
    model, endpoint, _ = await model_for(authority)
    endpoint.side_effect = asyncio.CancelledError()
    for _ in range(3):
        with pytest.raises(asyncio.CancelledError):
            await observed_call(model, model._call_api, "test-model", messages=[])
    context = await authority.context("alice")
    usage = await authority.quota.usage(context)
    assert usage["pending_reconciliation"] == 3
    assert all(b["used"] == 0 and b["reserved"] > 0 for b in usage["buckets"])
    endpoint.side_effect = None
    await observed_call(model, model._call_api, "test-model", messages=[])
    assert endpoint.await_count == 4
    async with authority.engine.connect() as db:
        assert (await db.execute(select(t.subjects.c.active_calls))).scalar_one() == 0
    await model.client.close()


@pytest.mark.asyncio
async def test_definite_4xx_releases_tokens_and_cancel_before_sdk_is_zero(authority):
    model, endpoint, _ = await model_for(authority)
    response = httpx.Response(400, request=httpx.Request("POST", "https://fixture.invalid"))
    endpoint.side_effect = BadRequestError("fixture rejection", response=response, body=None)
    with pytest.raises(BadRequestError):
        await observed_call(model, model._call_api, "test-model", messages=[])
    guard = model._quota_guard
    attempt = await guard.before(model, (), {}, {}, "cancel-before-dispatch")
    await guard.outbound(model, {"model": "test-model", "messages": []}, attempt)
    await guard.finish(attempt, {"id": attempt["id"], "status": "cancelled"})
    usage = await authority.quota.usage(await authority.context("alice"))
    assert usage["pending_reconciliation"] == 0
    assert all(b["used"] == b["reserved"] == 0 for b in usage["buckets"])
    assert endpoint.await_count == 1
    await model.client.close()


@pytest.mark.asyncio
async def test_pending_reconciliation_uses_saved_receipt_without_provider_retry(authority):
    model, endpoint, _ = await model_for(authority)
    endpoint.side_effect = httpx.ReadTimeout("fixture lost response")
    with pytest.raises(httpx.ReadTimeout):
        await observed_call(model, model._call_api, "test-model", messages=[])
    async with authority.engine.connect() as db:
        attempt = (await db.execute(select(t.attempts))).mappings().one()
    authority.storage.list_model_calls = AsyncMock(return_value=[{"id": attempt["id"], "status": "completed",
        "input_tokens": 10, "output_tokens": 5, "provider_request_id": "fixture-receipt-1"}])
    assert (await reconcile_pending(authority))["settled"] == 1
    assert (await reconcile_pending(authority))["scanned"] == 0
    assert endpoint.await_count == 1
    async with authority.engine.connect() as db:
        assert (await db.execute(select(t.subjects.c.active_calls))).scalar_one() == 0
    await model.client.close()


@pytest.mark.asyncio
async def test_pending_budget_cannot_be_refunded_without_receipt(authority):
    model, endpoint, _ = await model_for(authority)
    endpoint.side_effect = httpx.ReadTimeout("fixture unknown")
    with pytest.raises(httpx.ReadTimeout):
        await observed_call(model, model._call_api, "test-model", messages=[])
    before = await authority.quota.usage(await authority.context("alice"))
    authority.storage.list_model_calls = AsyncMock(return_value=[])
    assert (await reconcile_pending(authority))["pending"] == 1
    after = await authority.quota.usage(await authority.context("alice"))
    assert before["buckets"] == after["buckets"]
    assert endpoint.await_count == 1
    await model.client.close()
