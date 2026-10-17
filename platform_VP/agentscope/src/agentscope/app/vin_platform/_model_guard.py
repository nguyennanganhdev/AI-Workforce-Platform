"""Fail-closed model boundary, independent of best-effort usage telemetry."""

import json

from ._contracts import PlatformError


class ModelQuotaGuard:
    def __init__(self, service, user_id):
        self.service, self.user_id = service, user_id

    async def before(self, model, args, kwargs, attributes, attempt_id):
        from ._context import execution_context
        inherited = execution_context.get()
        context = inherited.model_copy(update={"purpose": attributes.get("purpose", "chat")}) if inherited is not None else await self.service.context(self.user_id, purpose=attributes.get("purpose", "chat"))
        policy, _ = await self.service.quota.policy(context)
        module = type(model).__module__
        if "_openai_chat" not in module and "_openai_response" not in module:
            raise PlatformError("MODEL_QUOTA_ADAPTER_UNSUPPORTED", 403)
        # Re-format the complete payload (including retrieved chunks/tool results),
        # and bound text tokens by UTF-8 bytes. Media needs a tested separate bound.
        messages = kwargs.get("messages") or []
        for msg in messages:
            for block in msg.get_content_blocks():
                if getattr(block, "type", "") in {"image", "audio", "video", "file"}:
                    raise PlatformError("MULTIMODAL_QUOTA_BOUND_REQUIRED", 403)
        formatted = await model.formatter.format(messages)
        serialized = json.dumps({**kwargs, "messages": formatted, "extra": getattr(model, "extra_body", None)},
            ensure_ascii=False, default=str)
        # URLs/base64 can carry media in custom formatters; fail closed too.
        if any(marker in serialized for marker in ('"image_url"', '"input_image"', '"input_audio"', '"input_file"')):
            raise PlatformError("MULTIMODAL_QUOTA_BOUND_REQUIRED", 403)
        output = min(policy.max_output_tokens, int(getattr(model.parameters, "max_tokens", None) or policy.max_output_tokens))
        model.parameters.max_tokens = output
        for key in ("max_tokens", "max_completion_tokens", "max_output_tokens"):
            if key in kwargs:
                kwargs[key] = min(output, int(kwargs[key]))
        # Hidden SDK retries are otherwise invisible quota attempts.
        if getattr(model, "client", None) is not None:
            model.client.max_retries = 0
        bound = len(serialized.encode("utf-8")) + 512 + 32 * len(messages) + 32 * len(kwargs.get("tools") or []) + output
        model_name = str(args[0] if args else model.model)
        await self.service.quota.reserve(context, budget=bound, purpose=context.purpose,
            model=model_name, attempt_id=attempt_id)
        return context

    async def finish(self, context, record):
        values = [record.get("input_tokens"), record.get("output_tokens")]
        valid = record["status"] == "completed" and all(
            isinstance(n, int) and not isinstance(n, bool) and n >= 0 for n in values)
        await self.service.quota.settle(context.tenant_id, record["id"], sum(values) if valid else None,
            provider_request_id=record.get("provider_request_id"))
