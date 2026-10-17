# -*- coding: utf-8 -*-
"""Model service: builds a ChatModelBase from stored credential + config."""
import os

from ._access import ResourceAccessService
from ..storage import ChatModelConfig
from ...credential import CredentialFactory
from ...model import ChatModelBase, OpenAIChatModel, OpenAIResponseModel
from ..._logging import logger


def runtime_model_config(config: ChatModelConfig) -> ChatModelConfig:
    """Deployment policy applies to runtime, summaries, evaluation and learning."""
    name = os.getenv("WORKFORCE_MODEL_NAME", "").strip()
    if not name:
        return config
    parameters = {**config.parameters}
    parameters["max_tokens"] = min(
        int(parameters.get("max_tokens") or 4096),
        int(os.getenv("WORKFORCE_MAX_OUTPUT_TOKENS", "4096")),
    )
    if name == "gpt-6-luna":
        # Luna function calling over Chat Completions requires effort=none.
        # Explicitly send it; omitting it leaves the provider's default active.
        parameters.update(thinking_enable=True, reasoning_effort="none")
        parameters.pop("temperature", None)
        parameters.pop("top_p", None)
    return config.model_copy(update={"model": name, "parameters": parameters})


async def get_model(
    user_id: str,
    config: ChatModelConfig,
    access: ResourceAccessService,
) -> ChatModelBase:
    """Build a chat model instance from a stored credential and config.

    Credentials are resolved through :class:`ResourceAccessService` so
    both the viewer's own credentials and any shared to them via the
    resource access policy work. Runtime paths use
    :meth:`ResourceAccessService.resolve_credential` which returns the
    raw record (not the masked view) — required for making real
    provider calls.

    Args:
        user_id (`str`):
            The viewer's user id. May differ from the credential owner
            when the credential is shared.
        config (`ChatModelConfig`):
            The chat model configuration.
        access (`ResourceAccessService`):
            Injected resource access service.

    Returns:
        `ChatModelBase`:
            The model instance.

    Raises:
        `HTTPException`:
            404 when the credential is neither owned by ``user_id`` nor
            shared to them.
    """
    config = runtime_model_config(config)
    credential_record = await access.resolve_credential(
        user_id,
        config.credential_id,
    )

    credential = CredentialFactory.from_dict(credential_record.data)
    model_cls = credential.get_chat_model_class()
    if (
        model_cls is OpenAIResponseModel
        and getattr(credential, "base_url", None)
        and os.getenv("OPENAI_CHAT_API", "").strip().lower() != "responses"
    ):
        # An OpenAI-compatible gateway (or the scripted test model) speaks
        # Chat Completions; OPENAI_CHAT_API=responses says it speaks both.
        model_cls = OpenAIChatModel
    parameters = (
        model_cls.Parameters(**config.parameters)
        if config.parameters
        else None
    )
    model = model_cls(
        credential=credential,
        model=config.model,
        parameters=parameters,
    )
    authority = getattr(getattr(access, "_storage", None), "vin_platform_service", None)
    if authority is not None:
        from ..vin_platform._model_guard import ModelQuotaGuard
        model._quota_guard = ModelQuotaGuard(authority, user_id, config.credential_id)

    # Override the context size and the formatter's input types with the
    # built-in model card's when one matches; custom models have no card,
    # so keep the defaults.
    try:
        for card in model_cls.list_models():
            if card.name == config.model:
                model.context_size = card.context_size
                model.formatter.input_types = card.input_types
                break
    except Exception:  # pylint: disable=broad-except
        logger.debug(
            "Failed to look up model card for %s, using defaults.",
            config.model,
        )

    from .._model_ledger import attach_ledger
    if not hasattr(access, "_storage"):
        return model
    return attach_ledger(model, access._storage, user_id,
        provider=str(credential_record.data.get("type") or type(credential).__name__),
        url=str(getattr(credential, "base_url", None) or
                ("https://api.openai.com/v1" if "openai" in type(credential).__name__.lower() else
                 "unknown://" + type(credential).__name__.lower())))
