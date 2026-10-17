"""Authorize the final SDK payload, after formatting and parameter merging."""

import asyncio
import json

from ._contracts import PlatformError


async def entitled_model(service, context, credential_id, model_name):
    entries = await service.catalog(context, "credential", "execute")
    entry = next((r for r in entries if r["resource_id"] == credential_id
                  and r["environment"] == context.environment), None)
    if entry is None or model_name not in entry["model_names"]:
        raise PlatformError("MODEL_NOT_ENTITLED", 403)


def text_payload(payload):
    # The SDK merges extra_body after ordinary arguments. No hidden input/output
    # or hosted-tool billing fields can bypass the final-payload reservation.
    extra = payload.get("extra_body") or {}
    if not isinstance(extra, dict) or set(extra) - {"reasoning", "reasoning_effort", "service_tier", "enable_thinking"}:
        raise PlatformError("UNBOUNDED_PROVIDER_OVERRIDE", 403)
    if payload.get("n", 1) != 1 or any(payload.get(k) for k in (
        "audio", "previous_response_id", "conversation", "background", "prompt", "file_ids")):
        raise PlatformError("MODEL_QUOTA_BOUND_REQUIRED", 403)
    if set(payload.get("modalities") or ["text"]) != {"text"}:
        raise PlatformError("MULTIMODAL_QUOTA_BOUND_REQUIRED", 403)
    for tool in payload.get("tools") or []:
        if tool.get("type") != "function":
            raise PlatformError("HOSTED_TOOL_QUOTA_BOUND_REQUIRED", 403)
    serialized = json.dumps(payload, ensure_ascii=False, allow_nan=False)
    if any(marker in serialized for marker in ('"image_url"', '"input_image"', '"input_audio"', '"input_file"', '"file_url"')):
        raise PlatformError("MULTIMODAL_QUOTA_BOUND_REQUIRED", 403)
    return serialized


class ModelQuotaGuard:
    def __init__(self, service, user_id, credential_id):
        self.service, self.user_id, self.credential_id = service, user_id, credential_id

    async def before(self, model, args, kwargs, attributes, attempt_id):
        from ._context import execution_context
        inherited = execution_context.get()
        context = inherited.model_copy(update={"purpose": attributes.get("purpose", "chat")}) if inherited is not None else await self.service.context(self.user_id, purpose=attributes.get("purpose", "chat"))
        if "_openai_chat" not in type(model).__module__ and "_openai_response" not in type(model).__module__:
            raise PlatformError("MODEL_QUOTA_ADAPTER_UNSUPPORTED", 403)
        return {"context": context, "id": attempt_id, "reserved": False, "dispatched": False}

    async def outbound(self, model, payload, attempt):
        if attempt["reserved"]:
            raise PlatformError("ATTEMPT_ALREADY_DISPATCHED", 409)
        context = attempt["context"]
        policy, _ = await self.service.quota.policy(context)
        await entitled_model(self.service, context, self.credential_id, payload["model"])
        text_payload(payload)
        cap = policy.max_output_tokens
        for key in ("max_tokens", "max_completion_tokens", "max_output_tokens"):
            if key in payload:
                value = payload[key]
                if isinstance(value, bool) or not isinstance(value, int) or value < 1:
                    raise PlatformError("INVALID_OUTPUT_LIMIT", 422)
                cap = min(cap, value)
        for key in ("max_tokens", "max_completion_tokens", "max_output_tokens"):
            payload.pop(key, None)
        payload["max_output_tokens" if "_openai_response" in type(model).__module__ else "max_completion_tokens"] = cap
        serialized = text_payload(payload)
        model.client.max_retries = 0
        items = payload.get("messages", payload.get("input", []))
        budget = len(serialized.encode("utf-8")) + 1024 + 64 * (len(items) + len(payload.get("tools") or [])) + cap
        reservation = asyncio.create_task(self.service.quota.reserve(context, budget=budget, purpose=context.purpose,
            model=payload["model"], attempt_id=attempt["id"]))
        try:
            await asyncio.shield(reservation)
        except asyncio.CancelledError:
            await reservation
            attempt["reserved"] = True
            raise
        attempt["reserved"] = True

    async def dispatched(self, attempt):
        # From this boundary onwards a cancellation may have reached the SDK.
        attempt["dispatched"] = True
        await asyncio.shield(self.service.quota.mark_dispatched(attempt["context"].tenant_id, attempt["id"]))

    async def finish(self, attempt, record):
        if not attempt["reserved"]:
            return
        values = [record.get("input_tokens"), record.get("output_tokens")]
        valid = record["status"] == "completed" and all(
            isinstance(n, int) and not isinstance(n, bool) and n >= 0 for n in values)
        rejected = 400 <= (record.get("provider_http_status") or 0) < 500
        actual = sum(values) if valid else 0 if rejected or not attempt["dispatched"] else None
        await self.service.quota.settle(attempt["context"].tenant_id, record["id"], actual,
            provider_request_id=record.get("provider_request_id"))
