"""Embedding budget at the actual provider-attempt boundary."""

import asyncio
from uuid import uuid4

from ._contracts import PlatformError


async def embedding_attempt(model, inputs, kwargs):
    service, user_id = model._vin_authority, model._vin_user_id
    if "_openai" not in type(model).__module__ or not all(isinstance(item, str) for item in inputs):
        raise PlatformError("EMBEDDING_QUOTA_ADAPTER_UNSUPPORTED", 403)
    from ._context import execution_context
    inherited = execution_context.get()
    context = inherited.model_copy(update={"purpose": "embedding"}) if inherited is not None else await service.context(user_id, purpose="embedding")
    ident = uuid4().hex
    budget = sum(len(item.encode("utf-8")) for item in inputs) + 32 * len(inputs)
    await service.quota.reserve(context, budget=max(1, budget), purpose="embedding", model=model.model, attempt_id=ident)
    model.client.max_retries = 0
    try:
        result = await model._call_api(inputs, **kwargs)
    except BaseException:
        await asyncio.shield(service.quota.settle(context.tenant_id, ident, None))
        raise
    tokens = getattr(getattr(result, "usage", None), "tokens", None)
    await service.quota.settle(context.tenant_id, ident,
        tokens if isinstance(tokens, int) and not isinstance(tokens, bool) and tokens >= 0 else None)
    return result
