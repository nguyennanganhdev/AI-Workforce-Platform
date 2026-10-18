"""Owner-scoped provider-call ledger and immutable price snapshots.

Prices are operator supplied, exact provider/endpoint/model/tier matches.
Unknown usage or prices never become zero-cost calls. No prompt is stored.
"""
from __future__ import annotations

import copy
import hashlib
import json
import math
import os
from collections import defaultdict
from datetime import UTC, datetime, timedelta
from decimal import Decimal, InvalidOperation
from pathlib import Path
from urllib.parse import urlsplit

from ..model._call_observer import recording_failures


def endpoint_id(url: str) -> str:
    parsed = urlsplit(url)
    # Query/userinfo can contain credentials and must not affect attribution.
    normalized = f"{parsed.scheme.lower()}://{(parsed.hostname or '').lower()}:{parsed.port or (443 if parsed.scheme == 'https' else 80)}{parsed.path.rstrip('/')}"
    return hashlib.sha256(normalized.encode()).hexdigest()[:24]


def price_snapshot(call: dict) -> dict | None:
    path = os.getenv("WORKFORCE_PRICE_CATALOG", "").strip()
    if not path:
        return None
    catalog = json.loads(Path(path).read_text(encoding="utf-8"))
    matches = []
    for price in catalog.get("prices", []):
        if any(price.get(k) != call.get(k) for k in ("provider", "endpoint_id", "model", "service_tier")):
            continue
        if not price.get("version") or not price.get("source") or price.get("currency") != "USD":
            continue
        at = datetime.fromisoformat(call["started_at"])
        start = datetime.fromisoformat(price["effective_from"])
        end = datetime.fromisoformat(price["effective_until"]) if price.get("effective_until") else None
        if start.tzinfo is None or (end is not None and end.tzinfo is None):
            raise ValueError("Price effective times must include timezone")
        if at < start or (end is not None and at >= end):
            continue
        for key in ("input_per_million", "cached_input_per_million", "output_per_million"):
            value = Decimal(str(price[key]))
            if not value.is_finite() or value < 0:
                raise ValueError("Invalid price")
        matches.append(price)
    if len(matches) > 1:
        raise ValueError("Overlapping price versions")
    return copy.deepcopy(matches[0]) if matches else None


def priced(call: dict) -> dict:
    call = copy.deepcopy(call)
    call.update(price=None, price_reason="unknown_price", cost_usd=None, cost_complete=False)
    try:
        price = price_snapshot(call)
    except (OSError, ValueError, KeyError, TypeError, InvalidOperation):
        call["price_reason"] = "invalid_price_catalog"
        return call
    if price is None:
        return call
    call.update(price=price, price_reason="versioned_catalog")
    # Cache creation is billed differently by some providers; do not guess.
    if not call.get("usage_complete") or call.get("cache_creation_input_tokens", 0):
        return call
    inputs = call["input_tokens"] - call["cached_input_tokens"]
    cost = (Decimal(inputs) * Decimal(str(price["input_per_million"]))
            + Decimal(call["cached_input_tokens"]) * Decimal(str(price["cached_input_per_million"]))
            + Decimal(call["output_tokens"]) * Decimal(str(price["output_per_million"]))) / 1_000_000
    call.update(cost_usd=str(cost), cost_complete=True)
    return call


def costed(calls: list[dict]) -> list[dict]:
    """Calls recorded before their price was in the catalog, priced from the
    catalog version effective at the call's start; recorded snapshots stay."""
    return [priced(call) if call.get("price") is None and not call.get("cost_complete") and call.get("status") != "started" else call
            for call in calls]


def attach_ledger(model, storage, user_id: str, *, provider: str, url: str):
    async def sink(record):
        if record.get("user_id") != user_id:
            raise ValueError("Model ledger owner cannot be overridden")
        await storage.record_model_call(user_id, priced(record))

    model._usage_sink = sink
    model._usage_attributes = {"user_id": user_id, "purpose": "unclassified"}
    model._usage_provider = provider
    model._usage_endpoint_id = endpoint_id(url)
    return model


def percentile(values: list[float], quantile: float) -> float | None:
    if not values:
        return None
    ordered = sorted(values)
    return ordered[max(0, math.ceil(len(ordered) * quantile) - 1)]


def aggregate(calls: list[dict]) -> dict:
    complete = bool(calls) and all(c.get("usage_complete") is True for c in calls)
    costs = bool(calls) and all(c.get("cost_complete") is True for c in calls)
    tokens = {key: sum(c.get(key) or 0 for c in calls) for key in
              ("input_tokens", "cached_input_tokens", "output_tokens")}
    known = sum((Decimal(c["cost_usd"]) for c in calls if c.get("cost_complete")), Decimal(0))
    latencies = [c["latency_ms"] for c in calls if c.get("latency_ms") is not None]
    return {"calls": len(calls), **tokens,
            "completed_calls": sum(c["status"] == "completed" for c in calls),
            "failed_calls": sum(c["status"] == "failed" for c in calls),
            "cancelled_calls": sum(c["status"] == "cancelled" for c in calls),
            "pending_calls": sum(c["status"] == "started" for c in calls),
            "p50_ms": percentile(latencies, .50), "p95_ms": percentile(latencies, .95),
            "failure_rate": sum(c["status"] in {"failed", "cancelled"} for c in calls) / len(calls) if calls else None,
            "cache_hit_ratio": tokens["cached_input_tokens"] / tokens["input_tokens"] if tokens["input_tokens"] else None,
            "usage_complete": complete, "cost_complete": costs,
            "calls_missing_usage": sum(not c.get("usage_complete") for c in calls),
            "calls_unpriced": sum(c.get("price") is None for c in calls),
            "calls_costed": sum(c.get("cost_complete") is True for c in calls),
            "calls_unknown_purpose": sum(c.get("purpose") == "unclassified" for c in calls),
            "known_cost_usd": float(known), "est_cost_usd": float(known) if costs else None}


async def observability(storage, user_id: str, days: int = 30) -> dict:
    since = (datetime.now(UTC) - timedelta(days=days)).isoformat()
    calls = costed(await storage.list_model_calls(user_id, since=since, limit=20001))
    truncated = len(calls) > 20000
    calls = calls[:20000]
    groups, purposes = defaultdict(list), defaultdict(list)
    for call in calls:
        groups[tuple(call.get(k) for k in ("provider", "endpoint_id", "model", "service_tier"))].append(call)
        purposes[call["purpose"]].append(call)
    metrics = aggregate(calls)
    if truncated or recording_failures():
        metrics.update(usage_complete=False, cost_complete=False, est_cost_usd=None)
    return {"days": days, "window_since": since, **metrics,
            "by_model": [{**dict(zip(("provider", "endpoint_id", "model", "service_tier"), key)), **aggregate(rows)}
                         for key, rows in sorted(groups.items())],
            "by_purpose": [{"purpose": key, **aggregate(rows)} for key, rows in sorted(purposes.items())],
            "backlog": {"model_calls_started": sum(c["status"] == "started" for c in calls)},
            "coverage": {"truncated": truncated, "before_ledger_unknown": True,
                         "recording_started_at": os.getenv("WORKFORCE_LEDGER_STARTED_AT") or None,
                         "recording_failures_current_process": recording_failures(), "scope": "authenticated_owner"}}
