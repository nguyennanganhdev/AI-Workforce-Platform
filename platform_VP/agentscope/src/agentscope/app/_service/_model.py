# -*- coding: utf-8 -*-
"""Model service: builds a ChatModelBase from stored credential + config."""
import inspect
import os

from fastapi import HTTPException

from ._access import ResourceAccessService
from ..storage import ChatModelConfig
from ...credential import CredentialFactory, OpenAICredential
from ...model import ChatModelBase, GeminiChatModel, OpenAIResponseModel
from ..._logging import logger


def _timeout_kwargs(model_cls: type) -> dict:
    """A per-call deadline for the provider SDK client.

    SDK defaults are about ten minutes per read plus retries, while the
    run's heartbeat keeps the session lock alive the whole time; one hung
    provider then blocks the session. Gemini's client takes its timeout
    another way and keeps its default.
    """
    if issubclass(model_cls, GeminiChatModel) or (
        "client_kwargs" not in inspect.signature(model_cls.__init__).parameters
    ):
        return {}
    seconds = float(os.getenv("MODEL_CALL_TIMEOUT_SECONDS", "300"))
    return {"client_kwargs": {"timeout": seconds}}


async def get_model(
    user_id: str,
    config: ChatModelConfig,
    access: ResourceAccessService,
    *,
    default_reasoning_effort: str | None = None,
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
    credential_record = await access.resolve_credential(
        user_id,
        config.credential_id,
    )

    credential = CredentialFactory.from_dict(credential_record.data)
    model_cls = credential.get_chat_model_class()
    if isinstance(credential, OpenAICredential) and config.model == "gpt-6-luna":
        # Luna requires Responses for tool calls with reasoning enabled.
        model_cls = OpenAIResponseModel
        if config.parameters.get("reasoning_effort") not in (
            None, "none", "low", "medium", "high", "xhigh", "max",
        ):
            raise HTTPException(
                status_code=422,
                detail=(
                    "gpt-6-luna reasoning_effort must be one of: "
                    "none, low, medium, high, xhigh, max."
                ),
            )
    raw_parameters = dict(config.parameters or {})
    if (
        default_reasoning_effort is not None
        and model_cls is OpenAIResponseModel
        and raw_parameters.get("reasoning_effort") is None
    ):
        # A role default (Leader medium, members low) when the user chose none.
        raw_parameters["reasoning_effort"] = default_reasoning_effort
    parameters = (
        model_cls.Parameters(**raw_parameters)
        if raw_parameters
        else None
    )
    model = model_cls(
        credential=credential,
        model=config.model,
        parameters=parameters,
        **_timeout_kwargs(model_cls),
    )

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

    return model
