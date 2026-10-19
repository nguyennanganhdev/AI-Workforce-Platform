# -*- coding: utf-8 -*-
"""The OpenAI credential."""
import os
from typing import Literal, Type, TYPE_CHECKING

from pydantic import ConfigDict, Field, SecretStr

from ._base import CredentialBase

if TYPE_CHECKING:
    from ..embedding import EmbeddingModelBase
    from ..model import ChatModelBase
    from ..realtime import RealtimeModelBase
    from ..tts import TTSModelBase


class OpenAICredential(CredentialBase):
    """The OpenAI credential model."""

    model_config = ConfigDict(
        title="OpenAI API",
    )

    type: Literal["openai_credential"] = "openai_credential"
    """The credential type."""

    api_key: SecretStr = Field(
        description="The OpenAI API key.",
    )
    """The API key."""

    organization: str | None = Field(
        default=None,
        description="The OpenAI organization ID.",
    )
    """The OpenAI organization ID."""

    base_url: str | None = Field(
        default=None,
        description=(
            "The base URL for the OpenAI API. "
            "Can be used for OpenAI-compatible endpoints."
        ),
    )
    """Custom base URL for OpenAI-compatible endpoints."""

    @classmethod
    def get_chat_model_class(cls) -> Type["ChatModelBase"]:
        """The Responses API model (reasoning effort works with tools there,
        and the reply carries a reasoning summary), or Chat Completions when
        ``OPENAI_CHAT_API=chat_completions`` (OpenAI-compatible gateways and
        the scripted test model only speak that)."""
        from ..model import OpenAIChatModel, OpenAIResponseModel

        if os.getenv("OPENAI_CHAT_API", "responses").strip().lower() == "chat_completions":
            return OpenAIChatModel
        return OpenAIResponseModel

    @classmethod
    def get_embedding_model_class(cls) -> Type["EmbeddingModelBase"]:
        """Return the OpenAIEmbeddingModel class."""
        from ..embedding import OpenAIEmbeddingModel

        return OpenAIEmbeddingModel

    @classmethod
    def get_tts_model_classes(cls) -> list[Type["TTSModelBase"]]:
        """Return the OpenAI TTS model classes."""
        from ..tts import OpenAITTSModel

        return [OpenAITTSModel]

    @classmethod
    def get_realtime_model_classes(cls) -> list[Type["RealtimeModelBase"]]:
        """Return the OpenAI realtime model classes."""
        from ..realtime import OpenAIRealtimeModel

        return [OpenAIRealtimeModel]
