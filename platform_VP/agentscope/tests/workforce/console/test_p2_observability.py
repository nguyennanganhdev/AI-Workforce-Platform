"""Owner isolation, ordered pagination and timezone-normalized export."""
from datetime import UTC, datetime
import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from agentscope.app._router._workforce_studio import workforce_studio_router
from agentscope.app.deps import get_current_user_id, get_storage


def test_owner_export_and_metrics_do_not_read_other_owners():
    calls = [{"id": str(i), "status": "completed", "started_at": datetime.now(UTC).isoformat(),
              "purpose": "eval", "model": model, "provider": "test", "endpoint_id": "e", "service_tier": "standard",
              "input_tokens": 100, "cached_input_tokens": 20, "output_tokens": 10,
              "usage_complete": True, "cost_complete": False, "cost_usd": None} for i, model in enumerate(["m1", "m2"])]
    class Storage:
        async def list_model_calls(self, owner, **kw):
            assert owner == "owner-1"
            if "until" in kw:
                assert kw["since"] == "2026-10-15T17:00:00+00:00"
            start = kw.get("offset", 0)
            return calls[start:start + kw.get("limit", 200)]
    app = FastAPI(); app.include_router(workforce_studio_router)
    app.dependency_overrides[get_current_user_id] = lambda: "owner-1"
    app.dependency_overrides[get_storage] = lambda: Storage()
    with TestClient(app) as client:
        root = "/workforce/console/studio"
        metrics = client.get(root + "/observability").json()
        assert len(metrics["by_model"]) == 2 and metrics["calls"] == 2
        assert metrics["est_cost_usd"] is None and metrics["calls_unpriced"] == 2
        params = {"since": "2026-10-16T00:00:00+07:00", "until": "2026-10-17T00:00:00+07:00", "limit": 1}
        first = client.get(root + "/model-calls", params=params).json()
        assert first["calls"][0]["id"] == "0" and first["next_offset"] == 1
        second = client.get(root + "/model-calls", params={**params, "offset": 1}).json()
        assert second["calls"][0]["id"] == "1" and second["next_offset"] is None
        assert client.get(root + "/model-calls", params={**params, "until": "2026-10-16"}).status_code == 422


@pytest.mark.asyncio
@pytest.mark.parametrize("condition", ["complete", "historical", "unpriced", "missing"])
async def test_success_cost_excludes_stop_tracking_and_unknown_history(monkeypatch, condition):
    from types import SimpleNamespace
    from agentscope.app.workforce.integrations.unified._quality import ticket_quality
    monkeypatch.setenv("WORKFORCE_LEDGER_STARTED_AT", "2099-01-01T00:00:00+00:00" if condition == "historical" else "2000-01-01T00:00:00+00:00")
    now = datetime.now(UTC)
    responses = iter([
        [("success", "closed", now), ("stopped", "closed", now), ("pending", "awaiting_user", now)],
        [("success", {"payload": {"reason": "resident_confirmed"}}), ("stopped", {"payload": {"reason": "stop_tracking"}})],
        [("success", "say", "confirmation"), ("pending", "say", "confirmation")], [],
    ])
    class Uow:
        async def __aenter__(self): return self
        async def __aexit__(self, *_): pass
        async def execute(self, _query):
            data = next(responses)
            return SimpleNamespace(all=lambda: data)
    calls = [{"workflow_id": wid, "purpose": "runtime", "model": "fixture-model", "status": "completed",
              "input_tokens": 10, "cached_input_tokens": 2, "output_tokens": 1, "usage_complete": True,
              "cost_complete": True, "cost_usd": cost} for wid, cost in [("success", "1"), ("stopped", "3"), ("pending", "5")]]
    if condition == "unpriced": calls[0].update(cost_complete=False, cost_usd=None)
    if condition == "missing": calls = calls[1:]
    class Storage:
        async def list_model_calls(self, owner, **_):
            assert owner == "owner-1"
            return calls
    result = await ticket_quality(Uow, Storage(), None, "owner-1")
    assert (result["closed_confirmed"], result["closed_other"], result["open"]) == (1, 1, 1)
    if condition == "complete":
        assert result["est_cost_usd"] == 9 and result["cost_per_confirmed_usd"] == 1
    else:
        assert result["est_cost_usd"] is None and result["cost_per_confirmed_usd"] is None


def test_calls_recorded_before_the_catalog_are_priced_when_read(tmp_path, monkeypatch):
    """The confirmed gpt-6-luna price reaches calls the ledger kept unpriced."""
    import shutil
    from pathlib import Path
    from agentscope.app._model_ledger import costed

    catalog = Path(__file__).parents[3] / "deploy" / "vps" / "model-prices.gpt-6-luna.json"
    shutil.copy(catalog, tmp_path / "prices.json")
    monkeypatch.setenv("WORKFORCE_PRICE_CATALOG", str(tmp_path / "prices.json"))
    base = {"provider": "openai_credential", "endpoint_id": "bf7d5842201d21325a6f9dc5", "model": "gpt-6-luna",
            "started_at": "2026-10-16T08:00:00+00:00", "status": "completed", "usage_complete": True,
            "input_tokens": 1_000_000, "cached_input_tokens": 400_000, "output_tokens": 100_000,
            "price": None, "price_reason": "unknown_price", "cost_usd": None, "cost_complete": False}
    standard, flex, running, other = costed([
        {**base, "service_tier": "default"}, {**base, "service_tier": "flex"},
        {**base, "service_tier": "default", "status": "started"}, {**base, "model": "gpt-5.5", "service_tier": "default"}])
    # 600k uncached x $0.10 + 400k cached x $0.01 + 100k out x $0.50 = $0.114
    assert float(standard["cost_usd"]) == pytest.approx(0.114) and standard["cost_complete"]
    assert float(flex["cost_usd"]) == pytest.approx(0.057)
    assert running["cost_usd"] is None and other["cost_usd"] is None
