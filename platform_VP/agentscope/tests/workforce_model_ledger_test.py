"""Call evidence stays separate across models, tiers, owners and attempts."""
import asyncio
import copy
import json
import os
from datetime import UTC, datetime
from types import SimpleNamespace

import pytest

from agentscope.app._model_ledger import aggregate, attach_ledger, observability, priced
from agentscope.app.storage import AsyncSQLAlchemyStorage, RedisStorage
from agentscope.model import ChatResponse, ChatUsage
from agentscope.model._call_observer import observed_call, usage_scope


@pytest.fixture(params=["sqlite", "redis"] + (["postgres"] if os.getenv("P2_TEST_POSTGRES_URL") else []))
async def store(request):
    if request.param in {"sqlite", "postgres"}:
        url = os.environ["P2_TEST_POSTGRES_URL"] if request.param == "postgres" else "sqlite+aiosqlite:///:memory:"
        storage = AsyncSQLAlchemyStorage(url, create_tables=True)
        await storage.__aenter__()
        if request.param == "postgres":
            from sqlalchemy import text
            async with storage._engine.begin() as connection:
                await connection.execute(text("TRUNCATE model_call_ledger"))
        yield storage
        await storage.__aexit__(None, None, None)
    else:
        import fakeredis.aioredis
        storage = RedisStorage()
        storage._client = fakeredis.aioredis.FakeRedis(decode_responses=True)
        yield storage
        await storage._client.aclose()


@pytest.mark.asyncio
async def test_call_stream_scope_missing_usage_and_failed_attempt_persist(store):
    model = attach_ledger(SimpleNamespace(model="first", extra_body=None), store, "u",
                          provider="test", url="https://user:secret@example.test/v1?token=secret")
    async def response(*args, **kwargs):
        return ChatResponse(content=[], is_last=True, usage=ChatUsage(input_tokens=100, output_tokens=20, time=0, cache_input_tokens=40),
            metadata={"provider_response_id": "resp-real", "provider_request_id": "req-real"})
    with usage_scope(purpose="eval", workflow_id="w"):
        await observed_call(model, response, "first")
    model.model = "second"
    async def stream(*args):
        async def chunks():
            yield ChatResponse(content=[], is_last=False)
        return chunks()
    with usage_scope(purpose="shared_summary"):
        lazy = await observed_call(model, stream, "second")
    _ = [chunk async for chunk in lazy]
    async def fail(*args):
        raise RuntimeError("sensitive provider response must not be recorded")
    with pytest.raises(RuntimeError):
        await observed_call(model, fail, "second")
    calls = await store.list_model_calls("u", since="2000", limit=100)
    assert len(calls) == 3
    assert calls[0]["provider_response_id"] == "resp-real" and calls[0]["workflow_id"] == "w"
    assert calls[1]["purpose"] == "shared_summary" and not calls[1]["usage_complete"]
    assert calls[2]["status"] == "failed" and calls[2]["error_type"] == "RuntimeError"
    assert "secret" not in json.dumps(calls) and "sensitive provider" not in json.dumps(calls)
    view = await observability(store, "u")
    assert len(view["by_model"]) == 2 and view["calls_missing_usage"] == 2
    assert view["est_cost_usd"] is None and not view["cost_complete"]
    assert await store.list_model_calls("other", since="2000") == []
    tampered = copy.deepcopy(calls[0]);tampered["input_tokens"] = 999
    with pytest.raises(ValueError, match="immutable"):
        await store.record_model_call("u", tampered)


def test_exact_versioned_prices_and_unknowns_never_become_zero(tmp_path, monkeypatch):
    call = {"provider": "test", "endpoint_id": "e", "model": "m", "service_tier": "flex",
            "started_at": "2026-10-16T01:00:00+00:00", "usage_complete": True,
            "input_tokens": 1000, "cached_input_tokens": 500, "output_tokens": 100,
            "cache_creation_input_tokens": 0}
    price = {"version": "contract-v1", "source": "operator-test-contract", "provider": "test", "endpoint_id": "e",
             "model": "m", "service_tier": "flex", "effective_from": "2026-10-01T00:00:00+00:00", "currency": "USD",
             "input_per_million": "2", "cached_input_per_million": "1", "output_per_million": "4"}
    path = tmp_path / "prices.json";path.write_text(json.dumps({"prices": [price]}))
    monkeypatch.setenv("WORKFORCE_PRICE_CATALOG", str(path))
    result = priced(call)
    assert result["cost_usd"] == "0.0019" and result["price"]["version"] == "contract-v1"
    for key, value in [("model", "other"), ("endpoint_id", "other"), ("service_tier", "standard"),
                       ("started_at", "2026-09-01T00:00:00+00:00"), ("usage_complete", False), ("cache_creation_input_tokens", 12)]:
        unknown = priced({**call, key: value})
        assert unknown["cost_usd"] is None and not unknown["cost_complete"]
    price["version"] = "changed";path.write_text(json.dumps({"prices": [price]}))
    assert result["price"]["version"] == "contract-v1"  # historical snapshot is stable
    path.write_text(json.dumps({"prices": [price, price]}))
    assert priced(call)["price_reason"] == "invalid_price_catalog"


@pytest.mark.asyncio
async def test_cancelled_or_abandoned_stream_does_not_claim_complete_usage(store):
    model = attach_ledger(SimpleNamespace(model="m", extra_body=None), store, "u", provider="test", url="https://example.test")
    async def provider(*args):
        async def chunks():
            yield ChatResponse(content=[], is_last=False)
            raise asyncio.CancelledError()
        return chunks()
    stream = await observed_call(model, provider, "m")
    with pytest.raises(asyncio.CancelledError):
        _ = [x async for x in stream]
    rows = await store.list_model_calls("u", since="2000")
    assert rows[0]["status"] == "cancelled" and not rows[0]["usage_complete"]
    assert aggregate(rows)["est_cost_usd"] is None


@pytest.mark.asyncio
async def test_public_model_and_structured_output_each_record_exactly_one_sdk_attempt(store):
    from unittest.mock import AsyncMock, MagicMock
    from pydantic import BaseModel
    from agentscope.message import UserMsg
    from model_openai_response_test import _make_model, _mock_completion

    class Result(BaseModel):
        ok: bool
    first = _mock_completion(text="ok", response_id="response-1")
    second = _mock_completion(function_calls=[{"id": "f1", "call_id": "c1", "name": "generate_structured_output", "arguments": '{"ok":true}'}], response_id="response-2")
    for index, value in enumerate([first, second]):
        value._request_id = f"request-{index}"
        value.service_tier = "flex"
        value.model = "provider-model-revision"
        value.usage.input_tokens_details = SimpleNamespace(cached_tokens=3)
        value.usage.output_tokens_details = SimpleNamespace(reasoning_tokens=1)
    model = attach_ledger(_make_model(stream=False), store, "u", provider="test", url="https://example.test")
    model.client = MagicMock()
    model.client.responses.create = AsyncMock(side_effect=[first, second])
    await model(messages=[UserMsg(name="u", content="ok")])
    result = await model.generate_structured_output([UserMsg(name="u", content="ok")], Result)
    assert result.content == {"ok": True}
    calls = await store.list_model_calls("u", since="2000")
    assert len(calls) == model.client.responses.create.await_count == 2
    assert [c["provider_response_id"] for c in calls] == ["response-1", "response-2"]
    assert all(c["usage_complete"] and c["cached_input_tokens"] == 3 and c["service_tier"] == "flex" for c in calls)
    assert all(c["provider_model"] == "provider-model-revision" for c in calls)


@pytest.mark.asyncio
async def test_recording_failure_prevents_claiming_complete_totals(monkeypatch):
    from agentscope.app import _model_ledger as ledger
    from unittest.mock import AsyncMock
    monkeypatch.setattr(ledger, "recording_failures", lambda: 1)
    storage = SimpleNamespace(list_model_calls=AsyncMock(return_value=[
        {"status": "completed", "model": "m", "provider": "p", "endpoint_id": "e", "service_tier": "flex",
         "purpose": "eval", "usage_complete": True, "cost_complete": True, "cost_usd": "1",
         "input_tokens": 100, "cached_input_tokens": 0, "output_tokens": 10}]))
    view = await observability(storage, "u")
    assert not view["cost_complete"] and not view["usage_complete"] and view["est_cost_usd"] is None
    assert view["known_cost_usd"] == 1 and view["coverage"]["recording_failures_current_process"] == 1
