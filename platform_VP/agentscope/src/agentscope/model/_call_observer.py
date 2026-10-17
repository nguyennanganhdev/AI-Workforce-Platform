"""Per-provider-attempt measurements, without prompts, results or credentials.

The application attaches a durable sink to models it creates. The core stays
usable without an application/sink. Attribution is copied before awaiting the
provider, so lazy streams retain the initiating scope after that scope exits.
"""

from __future__ import annotations

import asyncio
import time
import uuid
from contextlib import contextmanager
from functools import wraps
from contextvars import ContextVar
from datetime import UTC, datetime

from .._logging import logger

_attribution: ContextVar[dict] = ContextVar("model_call_attribution", default={})
_recording_failures = 0
_provider_attempt: ContextVar[tuple | None] = ContextVar("provider_quota_attempt", default=None)


async def authorize_provider_payload(model, payload):
    """Adapter hook immediately before SDK IO; direct unscoped calls deny."""
    guard = getattr(model, "_quota_guard", None)
    if guard is not None:
        current = _provider_attempt.get()
        if current is None or current[0] is not model:
            from ..app.vin_platform import PlatformError
            raise PlatformError("PROVIDER_ATTEMPT_REQUIRED", 403)
        await guard.outbound(model, payload, current[1])


@contextmanager
def usage_scope(**attributes):
    """Add server-owned attribution; nested scopes override specific fields."""

    token = _attribution.set({**_attribution.get(), **attributes})
    try:
        yield
    finally:
        _attribution.reset(token)


def recording_failures() -> int:
    """A process-local diagnostic, not a durable count across restarts."""

    return _recording_failures


def usage_purpose(purpose):
    """Scope an awaited operation that consumes its own model streams."""
    def decorate(function):
        @wraps(function)
        async def wrapped(*args, **kwargs):
            with usage_scope(purpose=purpose):
                return await function(*args, **kwargs)
        return wrapped
    return decorate


def provider_metadata(response, transport=None):
    """Allowlisted SDK reconciliation fields; never persist raw headers/body."""
    usage = getattr(response, "usage", None)
    details = getattr(usage, "output_tokens_details", None) or getattr(usage, "completion_tokens_details", None)
    input_details = getattr(usage, "input_tokens_details", None) or getattr(usage, "prompt_tokens_details", None)
    http = getattr(transport, "response", None)
    headers = getattr(http, "headers", {}) or {}
    return {"provider_response_id": getattr(response, "id", None),
            "provider_model": getattr(response, "model", None),
            "provider_request_id": getattr(response, "_request_id", None) or headers.get("x-request-id"),
            "service_tier": getattr(response, "service_tier", None),
            "cache_usage_reported": input_details is not None,
            "reasoning_tokens": getattr(details, "reasoning_tokens", None)}


async def observed_call(model, call, *args, **kwargs):
    """Observe exactly one adapter invocation, including each retry/fallback."""

    sink = getattr(model, "_usage_sink", None)
    guard = getattr(model, "_quota_guard", None)
    if sink is None and guard is None:
        return await call(*args, **kwargs)
    started = time.monotonic()
    attributes = {**getattr(model, "_usage_attributes", {}), **_attribution.get()}
    allowed = {"user_id", "agent_id", "session_id", "team_id", "workflow_id", "purpose", "operation_id"}
    record = {
        "id": uuid.uuid4().hex,
        "started_at": datetime.now(UTC).isoformat(),
        "ended_at": None,
        "status": "started",
        "provider": getattr(model, "_usage_provider", type(model).__module__),
        "endpoint_id": getattr(model, "_usage_endpoint_id", "unknown"),
        "model": str(kwargs.get("model_name") or (args[0] if args else model.model)),
        "service_tier": "unknown",
        "requested_service_tier": str((getattr(model, "extra_body", None) or {}).get("service_tier") or "provider_default"),
        "provider_response_id": None,
        "provider_request_id": None,
        "usage_complete": False,
        "usage_reason": "not_reported",
        "input_tokens": None,
        "cached_input_tokens": None,
        "cache_creation_input_tokens": None,
        "output_tokens": None,
        "latency_ms": None,
        **{key: str(value) for key, value in attributes.items() if key in allowed and value is not None},
    }
    record.setdefault("purpose", "unclassified")

    guard_context = None
    if guard is not None:
        # Authorization/reservation errors deliberately propagate before IO.
        guard_context = await guard.before(model, args, kwargs, attributes, record["id"])

    async def persist():
        global _recording_failures
        if sink is None:
            return
        try:
            await sink(record)
        except Exception:  # noqa: BLE001 - telemetry cannot break a paid call
            _recording_failures += 1
            logger.exception("Could not persist model-call ledger event %s", record["id"])

    def capture(response):
        # IDs are provider reconciliation identifiers only. Never copy arbitrary
        # response/usage metadata: it may contain user data or gateway secrets.
        metadata = {**(getattr(getattr(response, "usage", None), "metadata", None) or {}),
                    **(getattr(response, "metadata", None) or {})}
        provider_id = metadata.get("provider_response_id")
        if provider_id:
            record["provider_response_id"] = str(provider_id)[:255]
        if metadata.get("provider_request_id"):
            record["provider_request_id"] = str(metadata["provider_request_id"])[:255]
        if metadata.get("service_tier"):
            record["service_tier"] = str(metadata["service_tier"])[:80]
        if metadata.get("provider_model"):
            record["provider_model"] = str(metadata["provider_model"])[:255]
        record["reasoning_tokens"] = metadata.get("reasoning_tokens")
        usage = getattr(response, "usage", None)
        if usage is not None:
            names = {"input_tokens": "input_tokens", "output_tokens": "output_tokens",
                     "cached_input_tokens": "cache_input_tokens", "cache_creation_input_tokens": "cache_creation_input_tokens"}
            values = {key: getattr(usage, attr, None) for key, attr in names.items()}
            valid = all(isinstance(value, int) and not isinstance(value, bool) and value >= 0 for value in values.values())
            valid = valid and values["cached_input_tokens"] <= values["input_tokens"]
            if valid:
                record.update(values)
                record["usage_complete"] = metadata.get("cache_usage_reported", True) is True
                record["usage_reason"] = "provider_reported" if record["usage_complete"] else "cache_usage_not_reported"
            else:
                record["usage_reason"] = "invalid_provider_usage"

    async def finish(status, error=None):
        record["status"] = status
        record["ended_at"] = datetime.now(UTC).isoformat()
        record["latency_ms"] = round((time.monotonic() - started) * 1000, 3)
        if status != "completed":
            record["usage_complete"] = False
            record["usage_reason"] = "interrupted_or_failed_usage_unknown"
        if error is not None:
            record["error_type"] = type(error).__name__[:100]
            request_id = getattr(error, "request_id", None)
            if request_id:
                record["provider_request_id"] = str(request_id)[:255]
        if guard is not None:
            # A cancelled/failed attempt keeps its reserved budget pending
            # reconciliation. Unlike telemetry, this is not fail-open.
            await asyncio.shield(guard.finish(guard_context, record))
        await persist()

    await persist()  # A durable started row makes worker crashes visible as backlog.
    attempt_token = _provider_attempt.set((model, guard_context)) if guard is not None else None
    try:
        result = await call(*args, **kwargs)
    except BaseException as exc:
        await finish("cancelled" if isinstance(exc, asyncio.CancelledError) else "failed", exc)
        raise
    finally:
        if attempt_token is not None:
            _provider_attempt.reset(attempt_token)
    if not hasattr(result, "__aiter__"):
        capture(result)
        await finish("completed")
        return result

    async def stream():
        try:
            async for response in result:
                capture(response)
                yield response
        except BaseException as exc:
            await finish("cancelled" if isinstance(exc, (asyncio.CancelledError, GeneratorExit)) else "failed", exc)
            raise
        else:
            await finish("completed")
        finally:
            if record["status"] == "started":
                await finish("cancelled")
            close = getattr(result, "aclose", None)
            if close is not None:
                await close()

    return stream()
