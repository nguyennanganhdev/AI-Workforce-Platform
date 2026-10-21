# -*- coding: utf-8 -*-
"""The OpenRouter credential."""
from typing import Literal, Type, TYPE_CHECKING

from pydantic import ConfigDict, Field, SecretStr

from ._base import CredentialBase

if TYPE_CHECKING:
    from ..model import ChatModelBase

OPENROUTER_BASE_URL = "https://openrouter.ai/api/v1"


class OpenRouterCredential(CredentialBase):
    """An OpenRouter key: one key for GPT, Claude, Gemini, Qwen, DeepSeek
    and the other models OpenRouter serves, billed to the key owner's
    OpenRouter credits. Usually created by the "Connect OpenRouter"
    sign-in rather than pasted."""

    model_config = ConfigDict(
        title="OpenRouter",
    )

    type: Literal["openrouter_credential"] = "openrouter_credential"
    """The credential type."""

    api_key: SecretStr = Field(
        description="The OpenRouter API key.",
    )
    """The API key."""

    base_url: str = Field(
        default=OPENROUTER_BASE_URL,
        description="The base URL for the OpenRouter API.",
    )
    """The base URL for the OpenRouter API."""

    @property
    def organization(self) -> None:
        """OpenRouter has no organization; the OpenAI client reads one."""
        return None

    @classmethod
    def get_chat_model_class(cls) -> Type["ChatModelBase"]:
        """Return the OpenRouterChatModel class."""
        from ..model import OpenRouterChatModel

        return OpenRouterChatModel
