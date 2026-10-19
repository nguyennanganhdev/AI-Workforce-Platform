"""Embedding budget at the actual provider-attempt boundary."""

import asyncio
from uuid import uuid4

from ._contracts import PlatformError


async def embedding_attempt(model, inputs, kwargs):
    service, user_id = model._vin_authority, model._vin_user_id
    if "_openai" not in type(model).__module__ or not all(isinstance(item, str) for item in inputs):
        raise PlatformError("EMBEDDING_QUOTA_ADAPTER_UNSUPPORTED", 403)
    if set(kwargs) - {"dimensions", "encoding_format"}:
        raise PlatformError("UNBOUNDED_PROVIDER_OVERRIDE", 403)
    from ._context import execution_context
    inherited = execution_context.get()
    context = inherited.model_copy(update={"purpose": "embedding"}) if inherited is not None else await service.context(user_id, purpose="embedding")
    from ._model_guard import entitled_model
    private = await entitled_model(service, context, model._vin_credential_id, model.model)
    ident = uuid4().hex
    budget = sum(len(item.encode("utf-8")) for item in inputs) + 32 * len(inputs)
    await service.quota.reserve(context, budget=max(1, budget), purpose="embedding", model=model.model, attempt_id=ident,
                                private_credential_id=model._vin_credential_id if private else None)
    model.client.max_retries = 0
    try:
        await asyncio.shield(service.quota.mark_dispatched(context.tenant_id, ident))
        result = await model._call_api(inputs, **kwargs)
    except BaseException as exc:
        code = getattr(exc, "status_code", None) or getattr(getattr(exc, "response", None), "status_code", None)
        rejected = isinstance(code, int) and 400 <= code < 500
        await asyncio.shield(service.quota.settle(context.tenant_id, ident, 0 if rejected else None))
        raise
    tokens = getattr(getattr(result, "usage", None), "tokens", None)
    await service.quota.settle(context.tenant_id, ident,
        tokens if isinstance(tokens, int) and not isinstance(tokens, bool) and tokens >= 0 else None)
    return result
